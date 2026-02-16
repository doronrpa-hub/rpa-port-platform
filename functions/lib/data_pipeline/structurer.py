"""
Step 3: STRUCTURE — Parse extracted text into queryable Firestore documents.

Uses Gemini Flash (cheapest LLM) to extract structured fields from raw text.
Each source type has its own extraction prompt and output schema.

Session 27 — Assignment 14C
"""

import json
import logging
import re

logger = logging.getLogger("rcb.pipeline.structurer")


def structure_with_llm(full_text, source_type, metadata=None, get_secret_func=None):
    """
    Use LLM to parse extracted text into structured fields.

    Args:
        full_text: str — extracted text content
        source_type: str — "directive", "pre_ruling", etc.
        metadata: dict — additional context (source_url, date, etc.)
        get_secret_func: callable — to retrieve GEMINI_API_KEY

    Returns:
        dict — structured fields for this source type, or {} on failure
    """
    if not full_text or len(full_text.strip()) < 50:
        return {}

    prompt_template = STRUCTURING_PROMPTS.get(source_type)
    if not prompt_template:
        logger.warning(f"No structuring prompt for source_type: {source_type}")
        return _fallback_structure(full_text, source_type, metadata)

    # Get Gemini key
    gemini_key = None
    if get_secret_func:
        try:
            gemini_key = get_secret_func("GEMINI_API_KEY")
        except Exception:
            pass

    if not gemini_key:
        logger.info("No Gemini key — using fallback structurer")
        return _fallback_structure(full_text, source_type, metadata)

    # Build prompt
    text_sample = full_text[:8000]  # Fit in context window
    meta_str = json.dumps(metadata or {}, ensure_ascii=False, default=str)
    user_prompt = prompt_template.format(full_text=text_sample, metadata=meta_str)

    # Call Gemini Flash
    try:
        from lib.classification_agents import call_gemini_fast

        system_prompt = (
            "You are a data extraction expert for Israeli customs classification. "
            "Extract structured fields from the given text. "
            "Respond ONLY with valid JSON. No explanations."
        )
        raw = call_gemini_fast(gemini_key, system_prompt, user_prompt, max_tokens=1500)

        if raw:
            structured = _parse_json_response(raw)
            if structured:
                return structured
    except Exception as e:
        logger.warning(f"Gemini structuring failed: {e}")

    return _fallback_structure(full_text, source_type, metadata)


# ═══════════════════════════════════════════
#  PROMPTS PER SOURCE TYPE
# ═══════════════════════════════════════════

STRUCTURING_PROMPTS = {
    "directive": """Extract from this Israeli customs classification directive (הנחיית סיווג):
- directive_id (if mentioned, otherwise "")
- title (Hebrew, up to 200 chars)
- date_issued (YYYY-MM-DD if found, otherwise "")
- hs_codes_mentioned (ALL HS codes found, as array of strings)
- chapters_covered (array of integers — chapter numbers)
- key_terms (5-15 terms in Hebrew AND English for search)
- summary (2 sentences in Hebrew summarizing the directive)

Document text:
{full_text}

Additional metadata: {metadata}

Respond ONLY with valid JSON object.""",

    "pre_ruling": """Extract from this Israeli customs pre-ruling (החלטת מוקדמת / פרה-רולינג):
- ruling_id (if found, otherwise "")
- product_description (Hebrew)
- product_description_en (English if available, otherwise "")
- hs_code_assigned (format: XX.XX.XXXXXX/X or as found)
- ruling_date (YYYY-MM-DD if found)
- chapter (integer — chapter number)
- heading (format: XX.XX)
- key_terms (5-15 terms in Hebrew and English for search)
- reasoning_summary (2 sentences in Hebrew)
- rules_applied (array — classification rules mentioned, e.g., "כלל 3(א)")

Document text:
{full_text}

Additional metadata: {metadata}

Respond ONLY with valid JSON object.""",

    "customs_decision": """Extract from this customs decision/ruling:
- decision_id (if found)
- product_description (Hebrew if available)
- hs_code (the code discussed or assigned)
- decision_date (YYYY-MM-DD if found)
- authority (which authority issued it — רשות המכס, etc.)
- key_terms (5-15 terms for search)
- reasoning_summary (2 sentences)
- hs_codes_discussed (array — all HS codes mentioned)

Document text:
{full_text}

Additional metadata: {metadata}

Respond ONLY with valid JSON object.""",

    "court_precedent": """Extract from this court case about customs classification:
- case_id (if found)
- case_name (e.g., "VIVO")
- court (which court — e.g., "בית משפט מחוזי חיפה")
- date (YYYY-MM-DD if found)
- hs_codes_discussed (array of all HS codes mentioned)
- key_terms (5-15 terms for search)
- ruling_summary (2-3 sentences)

Document text:
{full_text}

Additional metadata: {metadata}

Respond ONLY with valid JSON object.""",

    "customs_ordinance": """Extract from this section of the Israeli Customs Ordinance (פקודת המכס):
- section_number (e.g., "152")
- title (Hebrew)
- key_terms (5-10 terms for search)
- applies_to (array — what this section regulates, e.g., ["temporary_import"])
- summary (1-2 sentences)

Document text:
{full_text}

Additional metadata: {metadata}

Respond ONLY with valid JSON object.""",

    "procedure": """Extract from this customs procedure document:
- title (Hebrew)
- procedure_type (import/export/both/general)
- key_terms (5-10 terms for search)
- summary (2 sentences)
- applicable_codes (array of HS codes if any are mentioned)

Document text:
{full_text}

Additional metadata: {metadata}

Respond ONLY with valid JSON object.""",

    "tariff_uk": """Extract from this UK tariff entry:
- uk_code (the UK commodity code)
- description (English)
- chapter (integer)
- heading (format: XX.XX)
- duty_rate (if shown)
- key_terms (5-10 terms for search)
- notes (any relevant notes)

Document text:
{full_text}

Additional metadata: {metadata}

Respond ONLY with valid JSON object.""",

    "tariff_usa": """Extract from this US HTS tariff entry:
- hts_code (the US HTS code)
- description (English)
- chapter (integer)
- heading (format: XX.XX)
- duty_rate (if shown)
- key_terms (5-10 terms for search)

Document text:
{full_text}

Additional metadata: {metadata}

Respond ONLY with valid JSON object.""",

    "tariff_eu": """Extract from this EU TARIC tariff entry:
- taric_code (the EU code)
- description (English)
- chapter (integer)
- heading (format: XX.XX)
- duty_rate (if shown)
- key_terms (5-10 terms for search)

Document text:
{full_text}

Additional metadata: {metadata}

Respond ONLY with valid JSON object.""",
}


# ═══════════════════════════════════════════
#  FALLBACK STRUCTURER (no LLM needed)
# ═══════════════════════════════════════════

def _fallback_structure(full_text, source_type, metadata=None):
    """
    Extract structured fields without LLM using regex patterns.
    Works for basic documents when Gemini is unavailable.
    """
    result = {
        "key_terms": _extract_key_terms(full_text),
        "summary": full_text[:300].strip(),
    }

    # Try to extract HS codes
    hs_pattern = r'\b(\d{2})[.\s]?(\d{2})[.\s]?(\d{2,6})\b'
    hs_matches = re.findall(hs_pattern, full_text)
    if hs_matches:
        codes = list(set(f"{m[0]}.{m[1]}.{m[2]}" for m in hs_matches))
        result["hs_codes_mentioned"] = codes[:20]
        # Extract chapters
        chapters = list(set(int(m[0]) for m in hs_matches if m[0].isdigit()))
        result["chapters_covered"] = sorted(chapters)

    # Extract dates
    date_pattern = r'(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})'
    date_matches = re.findall(date_pattern, full_text[:2000])
    if date_matches:
        d, m, y = date_matches[0]
        y = f"20{y}" if len(y) == 2 else y
        result["date_found"] = f"{y}-{m.zfill(2)}-{d.zfill(2)}"

    # Add metadata fields
    if metadata:
        if metadata.get("source_url"):
            result["source_url"] = metadata["source_url"]

    return result


def _extract_key_terms(text, max_terms=15):
    """Extract key terms from text using word frequency."""
    if not text:
        return []

    # Hebrew and English stop words
    stop_words = {
        "the", "and", "for", "that", "this", "with", "from", "are", "was",
        "have", "has", "not", "but", "all", "can", "will", "one", "been",
        "של", "את", "על", "עם", "או", "הוא", "היא", "אם", "כי", "לא",
        "גם", "אל", "זה", "זו", "אשר", "כל", "עד", "מן", "אין", "יש",
    }

    words = re.split(r'[^\w\u0590-\u05FF]+', text.lower())
    words = [w for w in words if len(w) > 2 and w not in stop_words]

    # Count frequency
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1

    # Sort by frequency, take top N
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:max_terms]]


# ═══════════════════════════════════════════
#  JSON PARSING HELPERS
# ═══════════════════════════════════════════

def _parse_json_response(raw):
    """Parse JSON from LLM response, handling common issues."""
    if not raw:
        return None

    # Strip markdown code fences
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None
