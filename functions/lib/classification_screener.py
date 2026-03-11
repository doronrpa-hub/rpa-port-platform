"""
Classification Screener — Stage 2 of the reasoning engine.

Given candidate headings from identify_product(), loads chapter notes
for those chapters, uses AI to generate the exact screening questions
needed to classify this specific product, checks what's already known,
and returns what's missing.

INPUT:  product name, candidates from Stage 1, known_attributes dict
OUTPUT: ScreeningResult with answered/missing questions and readiness flag

Does NOT touch broker_engine.py.
"""

import json
import logging
import re
import time

import requests

logger = logging.getLogger('rcb.screener')

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 1500
_TIMEOUT = 30  # seconds — Haiku is fast
_MAX_CANDIDATES = 3
_MAX_CHAPTERS = 5  # safety cap on chapter_notes reads

# Attribute keys the AI may reference — normalized for cross-checking
_KNOWN_ATTRIBUTE_ALIASES = {
    # material
    'material': 'material', 'חומר': 'material', 'made_of': 'material',
    'composition': 'material', 'הרכב': 'material',
    # function / use
    'function': 'function', 'use': 'function', 'שימוש': 'function',
    'purpose': 'function', 'ייעוד': 'function',
    # weight
    'weight': 'weight', 'משקל': 'weight', 'mass': 'weight',
    'weight_kg': 'weight',
    # dimensions
    'dimensions': 'dimensions', 'size': 'dimensions', 'מידות': 'dimensions',
    # power
    'power': 'power', 'wattage': 'power', 'הספק': 'power', 'voltage': 'power',
    # origin
    'origin': 'origin', 'country': 'origin', 'מקור': 'origin',
    'country_of_origin': 'origin',
    # form / state
    'form': 'form', 'state': 'form', 'צורה': 'form', 'מצב': 'form',
    'condition': 'form', 'raw': 'form', 'processed': 'form',
    # quantity
    'quantity': 'quantity', 'count': 'quantity', 'כמות': 'quantity',
    # frequency (for electronics)
    'frequency': 'frequency', 'תדר': 'frequency', 'ghz': 'frequency',
    'mhz': 'frequency',
    # capacity
    'capacity': 'capacity', 'volume': 'capacity', 'נפח': 'capacity',
    'liters': 'capacity',
    # motor / engine
    'motor': 'motor', 'engine': 'motor', 'מנוע': 'motor',
    'engine_type': 'motor', 'cc': 'motor', 'displacement': 'motor',
}


# ---------------------------------------------------------------------------
#  Chapter notes loader
# ---------------------------------------------------------------------------

def _load_chapter_notes(db, chapters):
    """
    Load chapter notes from Firestore for given chapter numbers.

    Returns: dict of chapter -> {preamble, notes, inclusions, exclusions, ...}
    """
    if db is None:
        return {}

    loaded = {}
    for ch in chapters[:_MAX_CHAPTERS]:
        ch_str = str(ch).zfill(2)
        doc_id = f'chapter_{ch_str}'
        try:
            doc = db.collection('chapter_notes').document(doc_id).get()
            if doc.exists:
                data = doc.to_dict()
                loaded[ch_str] = data
                logger.info('[screener] loaded chapter_notes/%s', doc_id)
            else:
                logger.info('[screener] chapter_notes/%s not found', doc_id)
        except Exception as e:
            logger.warning('[screener] chapter_notes/%s error: %s', doc_id, e)

    return loaded


def _format_chapter_notes_for_prompt(chapter_notes):
    """Format chapter notes into a concise text block for the AI prompt."""
    parts = []
    for ch, data in sorted(chapter_notes.items()):
        lines = [f"## Chapter {ch}"]

        preamble = data.get('preamble', '') or data.get('preamble_en', '')
        if preamble:
            lines.append(f"Preamble: {preamble[:500]}")

        for field, label in [
            ('notes', 'Notes'), ('notes_en', 'Notes (EN)'),
            ('inclusions', 'Includes (כולל)'),
            ('exclusions', 'Excludes (אינו כולל)'),
        ]:
            val = data.get(field, [])
            if isinstance(val, list) and val:
                text = '; '.join(str(v) for v in val if v)
                if text:
                    lines.append(f"{label}: {text[:600]}")
            elif isinstance(val, str) and val.strip():
                lines.append(f"{label}: {val[:600]}")

        definitions = data.get('definitions', [])
        if isinstance(definitions, list) and definitions:
            defs_text = '; '.join(str(d) for d in definitions[:5] if d)
            if defs_text:
                lines.append(f"Definitions: {defs_text[:400]}")

        if len(lines) > 1:  # more than just the header
            parts.append('\n'.join(lines))

    return '\n\n'.join(parts)


# ---------------------------------------------------------------------------
#  AI prompt + call
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an experienced Israeli customs broker analyzing a product for HS classification.

Given candidate headings and their chapter notes, identify ONLY the questions whose answers would change which heading is correct. Do NOT ask generic questions. Every question must distinguish between at least 2 of the candidate headings.

Return ONLY valid JSON — no markdown, no explanation, no code fences.

JSON format:
{
  "questions": [
    {
      "question": "the screening question in English",
      "question_he": "the same question in Hebrew",
      "attribute_key": "one of: material, function, weight, dimensions, power, origin, form, quantity, frequency, capacity, motor",
      "distinguishes_between": ["HHHH", "HHHH"],
      "why": "one sentence explaining why this matters for classification"
    }
  ]
}

Rules:
- Maximum 5 questions
- attribute_key must be from the allowed list above
- distinguishes_between must contain 4-digit heading codes from the candidates
- If the chapter notes already make the classification obvious, return {"questions": []}
- Focus on physical characteristics, material composition, and intended use
- Never ask about price, brand, or commercial details"""


def _build_user_prompt(product, candidates, chapter_notes_text, known_attrs):
    """Build the user prompt for the AI call."""
    parts = [f"Product: {product}"]

    parts.append("\nCandidate headings:")
    for c in candidates:
        desc = c.get('description_en') or c.get('description_he') or c.get('description', '')
        sources = ', '.join(c.get('sources', []))
        parts.append(
            f"  {c['heading']} — {desc[:120]} "
            f"(confidence: {c.get('confidence_level', '?')}, sources: {sources})"
        )

    if chapter_notes_text:
        parts.append(f"\nChapter notes:\n{chapter_notes_text}")

    if known_attrs:
        parts.append("\nAlready known attributes:")
        for k, v in known_attrs.items():
            parts.append(f"  {k}: {v}")
        parts.append("\nDo NOT ask about attributes already known above.")

    return '\n'.join(parts)


def _call_haiku(api_key, system_prompt, user_prompt):
    """Call Claude Haiku for fast/cheap screening question generation."""
    if not api_key:
        logger.warning('[screener] no API key — returning empty questions')
        return None

    try:
        resp = requests.post(
            _API_URL,
            headers={
                'x-api-key': api_key.strip(),
                'content-type': 'application/json',
                'anthropic-version': '2023-06-01',
            },
            json={
                'model': _MODEL,
                'max_tokens': _MAX_TOKENS,
                'system': system_prompt,
                'messages': [{'role': 'user', 'content': user_prompt}],
            },
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            text = data.get('content', [{}])[0].get('text', '')
            return text
        else:
            logger.warning('[screener] Haiku API %d: %s',
                           resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.warning('[screener] Haiku call error: %s', e)
        return None


def _parse_ai_response(raw_text):
    """Parse AI JSON response into list of question dicts."""
    if not raw_text:
        return []

    # Strip markdown code fences if present
    text = raw_text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                logger.warning('[screener] could not parse AI response')
                return []
        else:
            return []

    questions = parsed.get('questions', [])
    if not isinstance(questions, list):
        return []

    # Validate each question
    valid = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        if not q.get('question'):
            continue
        if not q.get('attribute_key'):
            continue
        dist = q.get('distinguishes_between', [])
        if not isinstance(dist, list):
            continue
        # Normalize heading codes to 4 digits
        dist = [str(h)[:4] for h in dist if h]
        valid.append({
            'question': str(q['question']),
            'question_he': str(q.get('question_he', '')),
            'attribute_key': str(q['attribute_key']).lower().strip(),
            'distinguishes_between': dist,
            'why': str(q.get('why', '')),
        })

    return valid[:5]  # cap at 5


# ---------------------------------------------------------------------------
#  Cross-check: known_attributes vs questions
# ---------------------------------------------------------------------------

def _normalize_key(key):
    """Normalize an attribute key to canonical form."""
    k = str(key).lower().strip()
    return _KNOWN_ATTRIBUTE_ALIASES.get(k, k)


def _cross_check(questions, known_attrs):
    """
    Split questions into answered (already known) and missing (still needed).

    Returns: (answered_dict, missing_list)
    """
    if not known_attrs:
        return {}, questions

    # Normalize known attribute keys
    known_normalized = {}
    for k, v in known_attrs.items():
        norm_k = _normalize_key(k)
        if v and str(v).strip():
            known_normalized[norm_k] = v

    answered = {}
    missing = []

    for q in questions:
        attr_key = _normalize_key(q['attribute_key'])
        if attr_key in known_normalized:
            answered[attr_key] = known_normalized[attr_key]
        else:
            missing.append(q)

    return answered, missing


# ---------------------------------------------------------------------------
#  Main entry point
# ---------------------------------------------------------------------------

def screen_candidates(product, candidates, known_attributes=None, db=None,
                      api_key=None):
    """
    Screen candidate headings to determine what info is needed for classification.

    Args:
        product:          raw product string
        candidates:       list from identify_product() (Stage 1)
        known_attributes: dict of already-known product attributes
        db:               Firestore client (for chapter_notes)
        api_key:          Anthropic API key (for Claude Haiku)

    Returns:
        dict with keys: product, candidates, chapter_notes_loaded,
        answered, missing, confidence, ready_for_traversal
    """
    t0 = time.monotonic()
    known_attributes = known_attributes or {}

    if not product or not candidates:
        return {
            'product': product or '',
            'candidates': [],
            'chapter_notes_loaded': [],
            'answered': {},
            'missing': [],
            'confidence': 'NEEDS_INFO',
            'ready_for_traversal': False,
        }

    # Step 1: Take top N candidates
    top_candidates = candidates[:_MAX_CANDIDATES]

    # Step 2: Get unique chapters
    chapters = list(dict.fromkeys(
        c.get('chapter', c.get('heading', '')[:2])
        for c in top_candidates
        if c.get('chapter') or c.get('heading')
    ))

    # Step 3: Load chapter notes
    chapter_notes = _load_chapter_notes(db, chapters)
    chapter_notes_text = _format_chapter_notes_for_prompt(chapter_notes)

    # Step 4: AI call
    user_prompt = _build_user_prompt(
        product, top_candidates, chapter_notes_text, known_attributes
    )
    raw_response = _call_haiku(api_key, _SYSTEM_PROMPT, user_prompt)
    questions = _parse_ai_response(raw_response)

    # Step 5: Cross-check against known attributes
    answered, missing = _cross_check(questions, known_attributes)

    # Step 6: Determine confidence
    if not missing:
        if len(top_candidates) == 1:
            confidence = 'HIGH'
        elif answered:
            # All AI questions answered — ready to proceed
            confidence = 'HIGH'
        else:
            # No questions generated (notes made it obvious) or no AI key
            confidence = 'MEDIUM' if api_key else 'MEDIUM'
    elif len(missing) <= 2:
        confidence = 'MEDIUM'
    else:
        confidence = 'NEEDS_INFO'

    ready = len(missing) == 0

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        '[screener] DONE in %dms | %d candidates | %d chapters loaded | '
        '%d questions | %d answered | %d missing | confidence=%s | ready=%s',
        elapsed_ms, len(top_candidates), len(chapter_notes),
        len(questions), len(answered), len(missing), confidence, ready,
    )

    return {
        'product': product,
        'candidates': top_candidates,
        'chapter_notes_loaded': sorted(chapter_notes.keys()),
        'answered': answered,
        'missing': missing,
        'confidence': confidence,
        'ready_for_traversal': ready,
    }
