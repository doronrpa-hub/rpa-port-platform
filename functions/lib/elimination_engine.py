"""
Elimination Engine — Deterministic tariff tree walker for HS code classification.
====================================================================================

Phase 3 of the RCB target architecture (Block D). Walks the Israeli customs tariff
tree deterministically, eliminating HS code candidates level by level using section
scope, chapter exclusions/inclusions, GIR rules, and AI consultation. The method
has final say — AI participates but cannot override deterministic rules.

Session 33, Blocks D1-D8. 2,282 lines. D9 (pipeline wiring) in separate session.

Architecture — Pipeline Levels (executed in order)
--------------------------------------------------
Level 0  ENRICH            (D1)  Resolve chapter→section for each candidate via
                                  TariffCache. Candidates without valid section are
                                  kept alive (conservative).

Level 1  SECTION SCOPE     (D1)  Group candidates by section, compare section
                                  keywords against product. Requires >=5 section
                                  keywords and zero overlap to eliminate (very
                                  conservative — avoids false positives).

Level 2a PREAMBLE SCOPE    (D2)  Load chapter preamble from chapter_notes. Check
                                  if product falls outside preamble scope statement.

Level 2b CHAPTER EXCL/INCL (D1+D2) Parse exclusions[] and inclusions[] from
                                  chapter_notes. Match product keywords against each
                                  rule's text. Exclusions eliminate, inclusions boost
                                  confidence. Conditional exclusions (exception
                                  clauses with "except"/"למעט") handled.

Level 2c CROSS-CHAPTER     (D2)  When an exclusion says "see chapter X", boost
         REDIRECT                 candidates in chapter X (they were pointed to).

Level 2d DEFINITION MATCH  (D2)  Parse "in this chapter, X means Y" definitions.
                                  Match product against defined terms. Products
                                  matching a definition get boosted.

Level 3  GIR 1 HEADING     (D3)  Composite score = 0.5×keyword_overlap +
         MATCH                    0.25×specificity + 0.25×attribute_match.
                                  Specificity: penalizes vague/others/n.e.s.
                                  headings (score 0.1-0.3). Specific headings score
                                  0.5-0.9. Attribute: matches material/form/use
                                  terms. Bottom 30% of survivors eliminated (if >3
                                  survive). At least 1 survivor always preserved.

Level 3b SUBHEADING NOTES  (D3)  Apply subheading-level rules from chapter_notes
                                  subheading_rules field.

Level 4a GIR 3 TIEBREAK    (D4)  Only fires when >1 survivor remains.
                                  3א: Most specific heading description wins.
                                  3ב: Essential character (material composition
                                      dominance, >=60% threshold for confident
                                      elimination).
                                  3ג: Last numerical order (fallback only).
                                  Each sub-rule only fires if the previous didn't
                                  resolve to a single winner.

Level 4b OTHERS GATE +     (D5)  Detect "אחרים"/"others"/"n.e.s." catch-all
         PRINCIPALLY              headings. Suppress when specific alternatives
                                  exist. "באופן עיקרי"/"principally" test: verify
                                  product meets material composition requirement.

Level 4c AI CONSULTATION   (D6)  Fires only when >3 survivors remain. Gemini Flash
                                  primary, Claude fallback via call_ai(). Structured
                                  JSON prompt. No-op when API keys missing.

Level 5  BUILD RESULT      (D1)  Assemble EliminationResult dict from survivors,
                                  eliminated candidates, and elimination steps.

Level 6  DEVIL'S ADVOCATE  (D7)  Per-survivor counter-arguments. Identifies
                                  strongest alternative and risk areas. Results
                                  stored as challenges[] in result. No-op when
                                  API keys missing.

Level 7  ELIMINATION LOG   (D8)  Write full audit trail to Firestore
                                  `elimination_log` collection. Failure-safe
                                  (try/except, never breaks classification).

Data Structures (all plain dicts, no external deps)
----------------------------------------------------
ProductInfo:  description, description_he, material, form, use,
              origin_country, seller_name, keywords (auto-extracted)

HSCandidate:  hs_code, section, chapter, heading, subheading,
              confidence, source, description, description_en, duty_rate,
              alive (bool), elimination_reason, eliminated_at_level

EliminationStep: level, action, rule_type, rule_ref, rule_text,
                 candidates_before, candidates_after, eliminated_codes,
                 kept_codes, reasoning

EliminationResult: survivors[], eliminated[], steps[], challenges[],
                   sections_checked[], chapters_checked[],
                   input_count, survivor_count, needs_ai, needs_questions,
                   timestamp

Dependencies (reads from, does NOT modify)
-------------------------------------------
- chapter_notes collection     — exclusions, inclusions, preamble, definitions
- tariff_structure collection  — section↔chapter mapping, section scope text
- tariff collection            — heading descriptions for GIR 1 matching
- classification_agents.call_ai() — D6/D7 AI routing (Gemini/Claude)

Writes to:
- elimination_log collection (D8) — one doc per elimination run

Public API
----------
    eliminate(db, product_info, candidates, api_key=None, gemini_key=None)
        -> EliminationResult dict
    candidates_from_pre_classify(pre_classify_result)
        -> list[HSCandidate dict]
    make_product_info(item_dict)
        -> ProductInfo dict

Reused patterns (not reinvented):
    _CHAPTER_REF_RE — from justification_engine.py:522
    _STOP_WORDS     — from intelligence.py:1371-1378
    _WORD_SPLIT_RE  — from intelligence.py
    Chapter/section Firestore reads — same fields as tool_executors.py
"""

import json
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Hebrew chapter reference regex — same pattern as justification_engine.py:522
_CHAPTER_REF_RE = re.compile(
    r'(?:chapter|פרק|בפרק|לפרק)\s*(\d{1,2})', re.IGNORECASE
)

# Bilingual stop words — same list as intelligence.py:1371-1378
_STOP_WORDS = {
    "the", "a", "an", "of", "for", "and", "or", "with", "to", "from",
    "in", "on", "by", "is", "are", "was", "were", "be", "been", "new",
    "used", "set", "pcs", "piece", "pieces", "item", "items", "type",
    "את", "של", "על", "עם", "או", "גם", "כי", "אם", "לא", "יש", "זה",
    "אל", "הם", "הוא", "היא", "בין", "כל", "מן", "אשר", "עד", "רק",
}

# Word splitter — keeps Hebrew characters (U+0590-U+05FF)
_WORD_SPLIT_RE = re.compile(r'[^\w\u0590-\u05FF]+')

# ── D2: Chapter note patterns ──

# Definition patterns: "in this chapter, 'X' means..."
_DEFINITION_RE = re.compile(
    r'(?:בפרק\s+זה|לעניין\s+פרק\s+זה|לצורך\s+פרק\s+זה|'
    r'in\s+this\s+chapter|for\s+the\s+purposes?\s+of\s+this\s+chapter)',
    re.IGNORECASE
)

# Exception/conditional patterns inside exclusions ("except", "unless")
_EXCEPTION_RE = re.compile(
    r'(?:למעט|אלא\s+אם|פרט\s+ל|חוץ\s+מ|'
    r'except\s+(?:for|that|where|when)|unless|other\s+than|excluding)',
    re.IGNORECASE
)

# Heading reference in note text: "heading 73.26" or "פרט 73.26"
_HEADING_REF_RE = re.compile(
    r'(?:heading|פרט|בפרט|לפרט)\s*(\d{2})[.\s]?(\d{2})',
    re.IGNORECASE
)

# ── D3: Specificity indicator patterns ──

# Vague/catch-all heading indicators
_VAGUE_HEADING_RE = re.compile(
    r'(?:אחר|אחרים|אחרות|other|others|not\s+elsewhere|n\.?e\.?s|'
    r'שלא\s+פורט|שלא\s+נכלל|miscellaneous|not\s+specified)',
    re.IGNORECASE
)

# Specific material terms that indicate heading precision
_MATERIAL_TERMS = {
    "steel", "iron", "aluminum", "aluminium", "copper", "plastic", "rubber",
    "glass", "wood", "paper", "leather", "cotton", "silk", "wool", "ceramic",
    "concrete", "cement", "zinc", "tin", "lead", "nickel", "titanium",
    "פלדה", "ברזל", "אלומיניום", "נחושת", "פלסטיק", "גומי",
    "זכוכית", "עץ", "נייר", "עור", "כותנה", "משי", "צמר", "קרמיקה",
    "בטון", "מלט", "אבץ", "בדיל", "עופרת", "ניקל", "טיטניום",
}

# Form/shape terms that indicate heading precision
_FORM_TERMS = {
    "bar", "rod", "wire", "tube", "pipe", "plate", "sheet", "strip",
    "foil", "powder", "profile", "angle", "section", "bolt", "screw",
    "nail", "nut", "spring", "chain", "container", "box", "tank",
    "מוט", "חוט", "צינור", "לוח", "יריעה", "רצועה", "גליל",
    "אבקה", "פרופיל", "זווית", "בורג", "אום", "קפיץ", "שרשרת",
    "מיכל", "קופסה", "תיבה",
}


# ═══════════════════════════════════════════════════════════════════════════════
# KEYWORD EXTRACTION (reuses intelligence.py pattern)
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_keywords(text):
    """Extract meaningful keywords from text. Bilingual (Hebrew + English)."""
    if not text:
        return []
    words = _WORD_SPLIT_RE.split(text.lower())
    keywords = [w for w in words if len(w) > 2 and w not in _STOP_WORDS]
    return keywords[:15]


def _keyword_overlap(text_a, text_b):
    """Calculate keyword overlap score between two texts.

    Returns (overlap_count, overlap_ratio) where ratio is relative to the
    shorter keyword list. Conservative: 0 overlap if either text is empty.
    """
    kw_a = set(_extract_keywords(text_a))
    kw_b = set(_extract_keywords(text_b))
    if not kw_a or not kw_b:
        return 0, 0.0
    overlap = kw_a & kw_b
    ratio = len(overlap) / min(len(kw_a), len(kw_b))
    return len(overlap), ratio


# ═══════════════════════════════════════════════════════════════════════════════
# HS CODE UTILITIES (reuses justification_engine.py:42-44 pattern)
# ═══════════════════════════════════════════════════════════════════════════════

def _clean_hs(hs_code):
    """Strip dots/slashes/spaces from HS code string."""
    return str(hs_code).replace(".", "").replace("/", "").replace(" ", "").strip()


def _chapter_from_hs(hs_code):
    """Extract 2-digit zero-padded chapter from HS code."""
    clean = _clean_hs(hs_code)
    if not clean:
        return ""
    return clean[:2].zfill(2)


def _heading_from_hs(hs_code):
    """Extract 4-digit heading from HS code."""
    clean = _clean_hs(hs_code)
    return clean[:4] if len(clean) >= 4 else ""


def _subheading_from_hs(hs_code):
    """Extract 6-digit subheading from HS code."""
    clean = _clean_hs(hs_code)
    return clean[:6] if len(clean) >= 6 else ""


# ═══════════════════════════════════════════════════════════════════════════════
# TARIFF CACHE — per-request in-memory cache for Firestore reads
# ═══════════════════════════════════════════════════════════════════════════════

class TariffCache:
    """In-memory cache for tariff data used during a single elimination run.

    One instance per eliminate() call. Not shared across requests.
    Caches chapter_notes, tariff_structure, and heading data to avoid
    repeated Firestore reads.
    """

    def __init__(self, db):
        self._db = db
        self._chapter_notes = {}      # chapter "84" -> dict
        self._section_data = {}        # section "XVI" -> dict
        self._chapter_to_section = {}  # chapter "84" -> "XVI"
        self._headings = {}            # heading "8471" -> dict

    def get_chapter_notes(self, chapter):
        """Fetch chapter notes from chapter_notes collection.
        Same collection/fields as tool_executors.py:205-251."""
        chapter = str(chapter).zfill(2)
        if chapter in self._chapter_notes:
            return self._chapter_notes[chapter]

        doc_id = f"chapter_{chapter}"
        try:
            doc = self._db.collection("chapter_notes").document(doc_id).get()
            if doc.exists:
                data = doc.to_dict()
                result = {
                    "found": True,
                    "chapter": chapter,
                    "chapter_title_he": data.get("chapter_title_he", ""),
                    "chapter_description_he": data.get("chapter_description_he", ""),
                    "preamble": data.get("preamble", ""),
                    "preamble_en": data.get("preamble_en", ""),
                    "notes": data.get("notes", []),
                    "notes_en": data.get("notes_en", []),
                    "exclusions": data.get("exclusions", []),
                    "inclusions": data.get("inclusions", []),
                    "keywords": data.get("keywords", [])[:50],
                }
            else:
                result = {"found": False, "chapter": chapter}
        except Exception as e:
            logger.warning(f"TariffCache: chapter_notes read failed for {chapter}: {e}")
            result = {"found": False, "chapter": chapter, "error": str(e)}

        self._chapter_notes[chapter] = result
        return result

    def get_section_data(self, section):
        """Fetch section data from tariff_structure collection.
        Doc IDs: section_I through section_XXII."""
        section = str(section).upper()
        if section in self._section_data:
            return self._section_data[section]

        doc_id = f"section_{section}"
        try:
            doc = self._db.collection("tariff_structure").document(doc_id).get()
            if doc.exists:
                data = doc.to_dict()
                result = {
                    "found": True,
                    "section": section,
                    "name_he": data.get("name_he", ""),
                    "name_en": data.get("name_en", ""),
                    "chapters": data.get("chapters", []),
                    "chapter_names": data.get("chapter_names", {}),
                }
            else:
                result = {"found": False, "section": section}
        except Exception as e:
            logger.warning(f"TariffCache: section read failed for {section}: {e}")
            result = {"found": False, "section": section, "error": str(e)}

        self._section_data[section] = result
        return result

    def get_chapter_section(self, chapter):
        """Resolve chapter -> section mapping from tariff_structure.
        Doc IDs: chapter_01 through chapter_98."""
        chapter = str(chapter).zfill(2)
        if chapter in self._chapter_to_section:
            return self._chapter_to_section[chapter]

        doc_id = f"chapter_{chapter}"
        section = ""
        try:
            doc = self._db.collection("tariff_structure").document(doc_id).get()
            if doc.exists:
                section = doc.to_dict().get("section", "")
        except Exception as e:
            logger.warning(f"TariffCache: chapter->section lookup failed for {chapter}: {e}")

        self._chapter_to_section[chapter] = section
        return section

    def get_heading_docs(self, heading):
        """Fetch tariff docs for a 4-digit heading.
        Queries tariff collection by heading field, limit 10."""
        heading = str(heading)
        if heading in self._headings:
            return self._headings[heading]

        results = []
        try:
            docs = list(
                self._db.collection("tariff")
                .where("heading", "==", heading)
                .limit(10)
                .stream()
            )
            for doc in docs:
                data = doc.to_dict()
                results.append({
                    "hs_code": data.get("hs_code", ""),
                    "description_he": data.get("description_he", ""),
                    "description_en": data.get("description_en", ""),
                    "duty_rate": data.get("duty_rate", ""),
                })
        except Exception as e:
            logger.warning(f"TariffCache: heading lookup failed for {heading}: {e}")

        self._headings[heading] = results
        return results


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURE BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

def make_product_info(item_dict):
    """Build a ProductInfo dict from an invoice item dict.

    Accepts various field name conventions (description/item_description,
    material/materials, etc.) and normalizes them.
    """
    desc = (
        item_dict.get("description")
        or item_dict.get("item_description")
        or item_dict.get("product_name")
        or ""
    )
    desc_he = (
        item_dict.get("description_he")
        or item_dict.get("item_description_he")
        or ""
    )
    combined_desc = f"{desc} {desc_he}".strip()

    return {
        "description": desc,
        "description_he": desc_he,
        "material": item_dict.get("material") or item_dict.get("materials") or "",
        "form": item_dict.get("form") or item_dict.get("product_form") or "",
        "use": item_dict.get("use") or item_dict.get("intended_use") or "",
        "origin_country": item_dict.get("origin_country") or item_dict.get("country") or "",
        "seller_name": item_dict.get("seller_name") or item_dict.get("supplier") or "",
        "keywords": _extract_keywords(combined_desc),
    }


def candidates_from_pre_classify(pre_classify_result):
    """Convert pre_classify() output into a list of HSCandidate dicts.

    pre_classify returns: {candidates: [{hs_code, confidence, source,
    description, duty_rate, reasoning}], ...}
    """
    raw_candidates = (pre_classify_result or {}).get("candidates", [])
    results = []
    for c in raw_candidates:
        hs = _clean_hs(c.get("hs_code", ""))
        if not hs or len(hs) < 4:
            continue
        results.append({
            "hs_code": hs,
            "section": "",       # filled by Level 0 ENRICH
            "chapter": _chapter_from_hs(hs),
            "heading": _heading_from_hs(hs),
            "subheading": _subheading_from_hs(hs),
            "confidence": c.get("confidence", 0),
            "source": c.get("source", "unknown"),
            "description": c.get("description", ""),
            "description_en": c.get("description_en", ""),
            "duty_rate": c.get("duty_rate", ""),
            "alive": True,
            "elimination_reason": "",
            "eliminated_at_level": "",
        })
    return results


def _make_step(level, action, rule_type, rule_ref, rule_text,
               candidates_before, candidates_after,
               eliminated_codes, kept_codes, reasoning):
    """Build an EliminationStep dict."""
    return {
        "level": level,
        "action": action,
        "rule_type": rule_type,
        "rule_ref": rule_ref,
        "rule_text": rule_text,
        "candidates_before": candidates_before,
        "candidates_after": candidates_after,
        "eliminated_codes": eliminated_codes,
        "kept_codes": kept_codes,
        "reasoning": reasoning,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 0: ENRICH — resolve section for each candidate
# ═══════════════════════════════════════════════════════════════════════════════

def _enrich_candidates(cache, candidates):
    """For each candidate, resolve section from tariff_structure."""
    for c in candidates:
        if not c.get("section") and c.get("chapter"):
            c["section"] = cache.get_chapter_section(c["chapter"])
    return candidates


# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 1: SECTION SCOPE — lightweight section-level filtering
# ═══════════════════════════════════════════════════════════════════════════════

def _apply_section_scope(cache, product_info, candidates, steps):
    """Eliminate candidates whose section scope clearly doesn't match the product.

    Conservative: only eliminates when product keywords have ZERO overlap
    with section name/description. When in doubt, keeps the candidate alive.
    """
    product_kw = set(product_info.get("keywords", []))
    if not product_kw:
        return candidates

    # Group candidates by section
    sections_seen = {}
    for c in candidates:
        if not c["alive"]:
            continue
        sec = c.get("section", "")
        if sec:
            sections_seen.setdefault(sec, []).append(c)

    for section, section_candidates in sections_seen.items():
        sec_data = cache.get_section_data(section)
        if not sec_data.get("found"):
            continue

        # Build section text from name + chapter names + chapter keywords
        sec_text_parts = [
            sec_data.get("name_he", ""),
            sec_data.get("name_en", ""),
        ]
        chapter_names = sec_data.get("chapter_names", {})
        if isinstance(chapter_names, dict):
            sec_text_parts.extend(chapter_names.values())
        # Also include chapter-level keywords from chapter_notes
        for sc in section_candidates:
            ch_notes = cache.get_chapter_notes(sc.get("chapter", ""))
            if ch_notes.get("found"):
                sec_text_parts.append(ch_notes.get("chapter_title_he", ""))
                sec_text_parts.append(ch_notes.get("chapter_description_he", ""))
                ch_kw = ch_notes.get("keywords", [])
                if ch_kw:
                    sec_text_parts.extend(str(k) for k in ch_kw[:20])
        sec_text = " ".join(sec_text_parts)

        # Need enough section text to make a meaningful comparison
        sec_keywords = _extract_keywords(sec_text)
        if len(sec_keywords) < 5:
            continue  # Not enough signal to eliminate at section level

        overlap_count, overlap_ratio = _keyword_overlap(
            " ".join(product_kw), sec_text
        )

        # Only eliminate if ZERO keyword overlap — very conservative
        if overlap_count == 0 and len(product_kw) >= 2:
            before_count = sum(1 for c in candidates if c["alive"])
            eliminated = []
            for c in section_candidates:
                c["alive"] = False
                c["elimination_reason"] = f"Section {section} scope mismatch: no keyword overlap with product"
                c["eliminated_at_level"] = "section"
                eliminated.append(c["hs_code"])
            after_count = sum(1 for c in candidates if c["alive"])

            steps.append(_make_step(
                level="section",
                action="eliminate",
                rule_type="preamble_scope",
                rule_ref=f"Section {section}",
                rule_text=sec_data.get("name_he", "") or sec_data.get("name_en", ""),
                candidates_before=before_count,
                candidates_after=after_count,
                eliminated_codes=eliminated,
                kept_codes=[],
                reasoning=f"Product keywords {list(product_kw)[:5]} have zero overlap with section {section} scope",
            ))

    return candidates


# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 2: CHAPTER EXCLUSIONS / INCLUSIONS — most impactful level
# ═══════════════════════════════════════════════════════════════════════════════

def _check_exclusion_match(product_info, exclusion_text):
    """Check if a chapter exclusion applies to this product.

    Uses keyword overlap between product description and exclusion text.
    Conservative: requires meaningful overlap (>=2 keywords or high ratio).
    Returns (matches, score) tuple.
    """
    combined = " ".join([
        product_info.get("description", ""),
        product_info.get("description_he", ""),
        product_info.get("material", ""),
        product_info.get("use", ""),
    ])
    overlap_count, overlap_ratio = _keyword_overlap(combined, exclusion_text)

    # Conservative threshold: need at least 2 overlapping keywords
    # OR high ratio (>0.5) with at least 1 keyword
    if overlap_count >= 2 or (overlap_count >= 1 and overlap_ratio > 0.5):
        return True, overlap_count
    return False, 0


def _check_inclusion_match(product_info, inclusion_text):
    """Check if a chapter inclusion applies to this product.

    Same logic as exclusion matching but used for boosting confidence.
    Returns (matches, score) tuple.
    """
    combined = " ".join([
        product_info.get("description", ""),
        product_info.get("description_he", ""),
        product_info.get("material", ""),
        product_info.get("use", ""),
    ])
    overlap_count, overlap_ratio = _keyword_overlap(combined, inclusion_text)

    if overlap_count >= 2 or (overlap_count >= 1 and overlap_ratio > 0.5):
        return True, overlap_count
    return False, 0


def _exclusion_points_elsewhere(exclusion_text, current_chapter):
    """Check if an exclusion references another chapter (e.g. 'see chapter 73').

    Uses the Hebrew chapter reference regex from justification_engine.py:522.
    Returns list of referenced chapters (zero-padded) that aren't the current one.
    """
    refs = _CHAPTER_REF_RE.findall(str(exclusion_text))
    other_chapters = []
    for ref in refs:
        padded = ref.zfill(2)
        if padded != str(current_chapter).zfill(2):
            other_chapters.append(padded)
    return other_chapters


# ── D2: Enhanced chapter note analysis ──

def _has_exception_clause(text):
    """Check if an exclusion/note text contains an exception clause.

    E.g., "this chapter does not cover X, except for Y" — the "except for Y"
    part means we can't blindly eliminate based on X.
    """
    return bool(_EXCEPTION_RE.search(str(text)))


def _split_at_exception(text):
    """Split exclusion text into (main_clause, exception_clause).

    Returns (main, exception) where exception may be empty string.
    """
    text = str(text)
    m = _EXCEPTION_RE.search(text)
    if not m:
        return text, ""
    return text[:m.start()].strip(), text[m.start():].strip()


def _extract_definitions(notes_text):
    """Extract defined terms from chapter notes preamble/notes.

    Looks for patterns like "in this chapter, 'X' means..." and returns
    a list of (defined_term_context, full_note_text) tuples. The context
    is the text around the definition that describes what it covers.
    """
    definitions = []
    # Search each note for definition patterns
    items = notes_text if isinstance(notes_text, list) else [notes_text]
    for item in items:
        item_str = str(item)
        if _DEFINITION_RE.search(item_str):
            definitions.append(item_str)
    return definitions


def _extract_heading_refs(text):
    """Extract heading references (XX.XX format) from note text.

    Returns list of 4-digit heading strings (e.g., ['7326', '8310']).
    """
    refs = _HEADING_REF_RE.findall(str(text))
    return [f"{ch}{hd}" for ch, hd in refs]


def _apply_preamble_scope(cache, product_info, candidates, steps):
    """D2: Use chapter preamble to score chapter-level relevance.

    If a chapter preamble clearly describes what the chapter covers,
    match the product against it. High match = boost, very low match
    on a detailed preamble = signal for elimination (but conservative).
    """
    alive = [c for c in candidates if c["alive"]]
    if len(alive) <= 1:
        return candidates

    product_text = " ".join([
        product_info.get("description", ""),
        product_info.get("description_he", ""),
        product_info.get("material", ""),
        product_info.get("use", ""),
    ])

    chapters_seen = set()
    chapter_preamble_scores = {}  # chapter -> (overlap_count, overlap_ratio)

    for c in alive:
        chapter = c.get("chapter", "")
        if not chapter or chapter in chapters_seen:
            continue
        chapters_seen.add(chapter)

        notes = cache.get_chapter_notes(chapter)
        if not notes.get("found"):
            continue

        preamble = notes.get("preamble", "")
        preamble_en = notes.get("preamble_en", "")
        preamble_text = f"{preamble} {preamble_en}".strip()
        if not preamble_text or len(preamble_text) < 20:
            continue

        overlap_count, overlap_ratio = _keyword_overlap(product_text, preamble_text)
        chapter_preamble_scores[chapter] = (overlap_count, overlap_ratio)

    # If we have scores for multiple chapters, boost the best-matching ones
    if len(chapter_preamble_scores) < 2:
        return candidates

    best_overlap = max(s[0] for s in chapter_preamble_scores.values())
    if best_overlap == 0:
        return candidates

    boosted_chapters = []
    for chapter, (overlap_count, overlap_ratio) in chapter_preamble_scores.items():
        if overlap_count >= 2 and overlap_ratio >= 0.3:
            # Boost candidates in this well-matching chapter
            boost = min(10, 3 + overlap_count * 2)
            for c in candidates:
                if c["alive"] and c["chapter"] == chapter:
                    c["confidence"] = min(100, c.get("confidence", 0) + boost)
            boosted_chapters.append(chapter)

    if boosted_chapters:
        steps.append(_make_step(
            level="chapter",
            action="boost",
            rule_type="preamble_scope",
            rule_ref="D2 preamble scope match",
            rule_text="",
            candidates_before=sum(1 for c in candidates if c["alive"]),
            candidates_after=sum(1 for c in candidates if c["alive"]),
            eliminated_codes=[],
            kept_codes=[c["hs_code"] for c in candidates
                        if c["alive"] and c["chapter"] in boosted_chapters],
            reasoning=(
                f"Preamble scope boost for chapters {boosted_chapters} "
                f"(best overlap={best_overlap})"
            ),
        ))

    return candidates


def _apply_cross_chapter_boost(candidates, steps):
    """D2: When a candidate was eliminated with a cross-chapter redirect,
    boost the target chapter's survivors.

    E.g., if ch84 exclusion says 'see chapter 85' and we eliminated ch84
    candidates, boost ch85 candidates.
    """
    # Collect redirect targets from eliminated candidates
    redirect_targets = {}  # target_chapter -> list of source_chapters
    for c in candidates:
        if not c["alive"] and c.get("eliminated_at_level") == "chapter":
            reason = c.get("elimination_reason", "")
            # Extract chapter references from elimination reason
            refs = _CHAPTER_REF_RE.findall(reason)
            source_ch = c.get("chapter", "")
            for ref in refs:
                target = ref.zfill(2)
                if target != source_ch:
                    redirect_targets.setdefault(target, []).append(source_ch)

    if not redirect_targets:
        return candidates

    boosted = []
    for target_chapter, source_chapters in redirect_targets.items():
        for c in candidates:
            if c["alive"] and c["chapter"] == target_chapter:
                boost = min(10, 5 * len(source_chapters))
                c["confidence"] = min(100, c.get("confidence", 0) + boost)
                boosted.append(c["hs_code"])

    if boosted:
        steps.append(_make_step(
            level="chapter",
            action="boost",
            rule_type="exclusion",
            rule_ref="D2 cross-chapter redirect boost",
            rule_text="",
            candidates_before=sum(1 for c in candidates if c["alive"]),
            candidates_after=sum(1 for c in candidates if c["alive"]),
            eliminated_codes=[],
            kept_codes=boosted,
            reasoning=(
                f"Boosted {len(boosted)} candidates in redirect target chapters "
                f"{list(redirect_targets.keys())}"
            ),
        ))

    return candidates


def _apply_definition_matching(cache, product_info, candidates, steps):
    """D2: Match product against chapter note definitions.

    If chapter notes define terms (e.g., "in this chapter, 'plastics' means...")
    and the product matches the defined term, boost that chapter's candidates.
    """
    alive = [c for c in candidates if c["alive"]]
    if len(alive) <= 1:
        return candidates

    product_text = " ".join([
        product_info.get("description", ""),
        product_info.get("description_he", ""),
        product_info.get("material", ""),
    ])

    chapters_seen = set()
    for c in alive:
        chapter = c.get("chapter", "")
        if not chapter or chapter in chapters_seen:
            continue
        chapters_seen.add(chapter)

        notes = cache.get_chapter_notes(chapter)
        if not notes.get("found"):
            continue

        # Look for definitions in preamble and notes
        all_notes = notes.get("notes", [])
        preamble = notes.get("preamble", "")
        definitions = _extract_definitions(all_notes)
        if preamble:
            definitions.extend(_extract_definitions(preamble))

        for defn_text in definitions:
            overlap_count, overlap_ratio = _keyword_overlap(product_text, defn_text)
            if overlap_count >= 2:
                boost = min(8, 3 + overlap_count)
                for c2 in candidates:
                    if c2["alive"] and c2["chapter"] == chapter:
                        c2["confidence"] = min(100, c2.get("confidence", 0) + boost)

                steps.append(_make_step(
                    level="chapter",
                    action="boost",
                    rule_type="inclusion",
                    rule_ref=f"D2 chapter {chapter} definition match",
                    rule_text=defn_text[:300],
                    candidates_before=sum(1 for x in candidates if x["alive"]),
                    candidates_after=sum(1 for x in candidates if x["alive"]),
                    eliminated_codes=[],
                    kept_codes=[x["hs_code"] for x in candidates
                                if x["alive"] and x["chapter"] == chapter],
                    reasoning=(
                        f"Product matches defined term in chapter {chapter} "
                        f"notes (overlap={overlap_count})"
                    ),
                ))
                break  # One definition match per chapter is enough

    return candidates


def _apply_chapter_exclusions_inclusions(cache, product_info, candidates, steps):
    """Apply chapter-level exclusions and inclusions.

    For each alive candidate's chapter:
    - Load chapter_notes
    - Check exclusions: if product matches an exclusion -> ELIMINATE
      D2: handles conditional exclusions ("except for X") — if product
      matches exception clause, skip the elimination.
    - Check inclusions: if product matches an inclusion -> BOOST confidence
    """
    # Collect unique chapters from alive candidates
    chapters_checked = set()
    for c in candidates:
        if not c["alive"] or not c.get("chapter"):
            continue
        chapter = c["chapter"]
        if chapter in chapters_checked:
            continue
        chapters_checked.add(chapter)

        notes = cache.get_chapter_notes(chapter)
        if not notes.get("found"):
            continue

        # ── Check exclusions ──
        exclusions = notes.get("exclusions", [])
        for excl in exclusions:
            excl_text = str(excl) if not isinstance(excl, dict) else (
                excl.get("text", "") or excl.get("description", "") or str(excl)
            )
            if not excl_text:
                continue

            # D2: Handle conditional exclusions ("except for X")
            # If the exclusion has an exception clause AND the product matches
            # the exception, skip this exclusion (product is in the exception).
            if _has_exception_clause(excl_text):
                main_clause, exception_clause = _split_at_exception(excl_text)
                # Product must match the main exclusion clause
                matches_main, score_main = _check_exclusion_match(
                    product_info, main_clause
                )
                if not matches_main:
                    continue
                # If product also matches the exception, DON'T eliminate
                if exception_clause:
                    matches_exc, _ = _check_exclusion_match(
                        product_info, exception_clause
                    )
                    if matches_exc:
                        logger.info(
                            f"Chapter {chapter}: exclusion matches product but "
                            f"exception clause also matches — keeping alive"
                        )
                        continue
                matches, score = matches_main, score_main
            else:
                matches, score = _check_exclusion_match(product_info, excl_text)
                if not matches:
                    continue

            # Check if the exclusion points to another specific chapter
            other_chapters = _exclusion_points_elsewhere(excl_text, chapter)

            before_count = sum(1 for x in candidates if x["alive"])
            eliminated = []
            for c2 in candidates:
                if c2["alive"] and c2["chapter"] == chapter:
                    c2["alive"] = False
                    c2["elimination_reason"] = (
                        f"Chapter {chapter} exclusion matches product "
                        f"(score={score}): {excl_text[:200]}"
                    )
                    c2["eliminated_at_level"] = "chapter"
                    eliminated.append(c2["hs_code"])
            after_count = sum(1 for x in candidates if x["alive"])

            if eliminated:
                reasoning = f"Product matches chapter {chapter} exclusion (score={score})"
                if other_chapters:
                    reasoning += f", exclusion points to chapter(s) {other_chapters}"

                steps.append(_make_step(
                    level="chapter",
                    action="eliminate",
                    rule_type="exclusion",
                    rule_ref=f"Chapter {chapter} exclusion",
                    rule_text=excl_text[:500],
                    candidates_before=before_count,
                    candidates_after=after_count,
                    eliminated_codes=eliminated,
                    kept_codes=[],
                    reasoning=reasoning,
                ))
                # Once eliminated by one exclusion, skip remaining exclusions for this chapter
                break

        # ── Check inclusions (only for still-alive candidates in this chapter) ──
        inclusions = notes.get("inclusions", [])
        alive_in_chapter = [c for c in candidates if c["alive"] and c["chapter"] == chapter]
        if not alive_in_chapter or not inclusions:
            continue

        for incl in inclusions:
            incl_text = str(incl) if not isinstance(incl, dict) else (
                incl.get("text", "") or incl.get("description", "") or str(incl)
            )
            if not incl_text:
                continue

            matches, score = _check_inclusion_match(product_info, incl_text)
            if not matches:
                continue

            boosted = []
            for c2 in alive_in_chapter:
                # Boost confidence by 5-15 points based on match score
                boost = min(15, 5 + score * 3)
                c2["confidence"] = min(100, c2.get("confidence", 0) + boost)
                boosted.append(c2["hs_code"])

            if boosted:
                steps.append(_make_step(
                    level="chapter",
                    action="boost",
                    rule_type="inclusion",
                    rule_ref=f"Chapter {chapter} inclusion",
                    rule_text=incl_text[:500],
                    candidates_before=sum(1 for x in candidates if x["alive"]),
                    candidates_after=sum(1 for x in candidates if x["alive"]),
                    eliminated_codes=[],
                    kept_codes=boosted,
                    reasoning=f"Product matches chapter {chapter} inclusion (score={score}), boosted {len(boosted)} candidates",
                ))
                # Apply first matching inclusion only
                break

    return candidates


# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 3: HEADING MATCH — GIR 1 full semantics (D3)
# ═══════════════════════════════════════════════════════════════════════════════

def _score_heading_specificity(heading_text):
    """D3: Score how specific a heading description is (0.0 to 1.0).

    GIR 1 principle: "the heading which provides the most specific description
    shall be preferred to headings providing a more general description."

    A heading like "Boxes of iron or steel" is more specific than
    "Other articles of iron or steel".
    """
    if not heading_text:
        return 0.0

    text_lower = heading_text.lower()
    words = _WORD_SPLIT_RE.split(text_lower)
    words = [w for w in words if len(w) > 1]
    if not words:
        return 0.0

    score = 0.0

    # Penalty: vague/catch-all indicators reduce specificity
    if _VAGUE_HEADING_RE.search(heading_text):
        score -= 0.3

    # Bonus: material terms increase specificity
    material_matches = sum(1 for w in words if w in _MATERIAL_TERMS)
    score += min(0.3, material_matches * 0.15)

    # Bonus: form/shape terms increase specificity
    form_matches = sum(1 for w in words if w in _FORM_TERMS)
    score += min(0.2, form_matches * 0.1)

    # Bonus: longer, more descriptive headings are generally more specific
    # (but cap the bonus to avoid rewarding verbosity)
    meaningful_word_count = len([w for w in words if w not in _STOP_WORDS and len(w) > 2])
    score += min(0.2, meaningful_word_count * 0.03)

    # Normalize to 0.0-1.0 range
    return max(0.0, min(1.0, score + 0.5))


def _match_product_attributes(product_info, heading_text):
    """D3: Score how well product attributes match heading terms.

    Checks material, form, and use from product_info against the heading
    description. Returns a score from 0.0 to 1.0.
    """
    if not heading_text:
        return 0.0

    heading_lower = heading_text.lower()
    heading_words = set(_WORD_SPLIT_RE.split(heading_lower))
    score = 0.0
    checks = 0

    # Check material match
    material = product_info.get("material", "").lower()
    if material:
        checks += 1
        mat_words = set(_WORD_SPLIT_RE.split(material))
        mat_words = {w for w in mat_words if len(w) > 2 and w not in _STOP_WORDS}
        if mat_words & heading_words:
            score += 0.4

    # Check form match
    form = product_info.get("form", "").lower()
    if form:
        checks += 1
        form_words = set(_WORD_SPLIT_RE.split(form))
        form_words = {w for w in form_words if len(w) > 2 and w not in _STOP_WORDS}
        if form_words & heading_words:
            score += 0.3

    # Check use match
    use = product_info.get("use", "").lower()
    if use:
        checks += 1
        use_words = set(_WORD_SPLIT_RE.split(use))
        use_words = {w for w in use_words if len(w) > 2 and w not in _STOP_WORDS}
        if use_words & heading_words:
            score += 0.3

    # If no structured attributes available, return 0 (no signal, not a penalty)
    if checks == 0:
        return 0.0

    return min(1.0, score)


def _get_heading_text(cache, candidate):
    """Build combined heading description text for a candidate."""
    heading = candidate.get("heading", "")
    parts = [candidate.get("description", ""), candidate.get("description_en", "")]
    if heading and cache is not None:
        heading_docs = cache.get_heading_docs(heading)
        for hd in heading_docs:
            parts.append(hd.get("description_he", ""))
            parts.append(hd.get("description_en", ""))
    return " ".join(p for p in parts if p)


def _apply_heading_match(cache, product_info, candidates, steps):
    """D3: GIR 1 full heading match — composite scoring.

    Combines three signals:
    1. Keyword overlap (D1 basic) — how many product keywords appear in heading
    2. Specificity score (D3) — is heading specific or vague/catch-all?
    3. Attribute match (D3) — do product material/form/use match heading terms?

    Elimination rules (conservative):
    - Zero composite score with best > 0: eliminate
    - Score < 30% of best AND best is strong (>= 0.5): eliminate
    - Vague "others" headings scored lower than specific headings
    """
    alive = [c for c in candidates if c["alive"]]
    if len(alive) <= 1:
        return candidates

    product_text = " ".join([
        product_info.get("description", ""),
        product_info.get("description_he", ""),
        product_info.get("material", ""),
        product_info.get("use", ""),
    ])

    # Score each alive candidate with composite scoring
    candidate_scores = {}  # hs_code -> {keyword, specificity, attribute, composite}
    for c in alive:
        heading_text = _get_heading_text(cache, c)

        # Signal 1: Keyword overlap (D1)
        kw_count, kw_ratio = _keyword_overlap(product_text, heading_text)
        kw_score = min(1.0, kw_count * 0.2)  # Normalize: 5+ keywords = 1.0

        # Signal 2: Heading specificity (D3)
        spec_score = _score_heading_specificity(heading_text)

        # Signal 3: Product attribute match (D3)
        attr_score = _match_product_attributes(product_info, heading_text)

        # Composite: weighted combination
        # Keyword overlap is most important (0.5), specificity adds (0.25),
        # attribute match adds (0.25)
        composite = (kw_score * 0.5) + (spec_score * 0.25) + (attr_score * 0.25)

        candidate_scores[c["hs_code"]] = {
            "keyword": kw_count,
            "keyword_score": kw_score,
            "specificity": spec_score,
            "attribute": attr_score,
            "composite": composite,
        }

    if not candidate_scores:
        return candidates

    best_composite = max(s["composite"] for s in candidate_scores.values())
    if best_composite == 0:
        return candidates  # No signal — keep all alive

    # Determine elimination threshold
    # Conservative: only eliminate when there's a clear gap
    before_count = sum(1 for c in candidates if c["alive"])
    eliminated = []
    kept = []

    for c in alive:
        scores = candidate_scores.get(c["hs_code"], {})
        composite = scores.get("composite", 0)
        kw_count = scores.get("keyword", 0)

        should_eliminate = False

        # Rule 1: Zero keyword overlap when best has >= 2 keywords
        best_kw = max(s["keyword"] for s in candidate_scores.values())
        if kw_count == 0 and best_kw >= 2:
            should_eliminate = True

        # Rule 2: Composite < 30% of best, and best is strong
        if best_composite >= 0.5 and composite < best_composite * 0.3:
            should_eliminate = True

        # Safety: don't eliminate if there would be 0 survivors
        alive_after = sum(
            1 for c2 in candidates
            if c2["alive"] and c2["hs_code"] != c["hs_code"]
            and not (
                candidate_scores.get(c2["hs_code"], {}).get("keyword", 0) == 0
                and best_kw >= 2
            )
        )
        if should_eliminate and alive_after == 0:
            should_eliminate = False

        if should_eliminate:
            c["alive"] = False
            c["elimination_reason"] = (
                f"GIR 1: heading {c.get('heading', '')} score={composite:.2f} "
                f"(kw={kw_count}, spec={scores.get('specificity', 0):.2f}, "
                f"attr={scores.get('attribute', 0):.2f}) "
                f"vs best={best_composite:.2f}"
            )
            c["eliminated_at_level"] = "heading"
            eliminated.append(c["hs_code"])
        else:
            kept.append(c["hs_code"])

    after_count = sum(1 for c in candidates if c["alive"])

    if eliminated:
        steps.append(_make_step(
            level="heading",
            action="eliminate",
            rule_type="gir_1",
            rule_ref="GIR 1 — heading specificity + keyword + attribute match",
            rule_text="",
            candidates_before=before_count,
            candidates_after=after_count,
            eliminated_codes=eliminated,
            kept_codes=kept,
            reasoning=(
                f"Eliminated {len(eliminated)} candidates by GIR 1 composite scoring; "
                f"best={best_composite:.2f}, {len(kept)} survivors"
            ),
        ))

    return candidates


def _apply_subheading_notes(cache, product_info, candidates, steps):
    """D3: Apply subheading classification rules from chapter notes.

    Uses the subheading_rules field from chapter_notes to further
    disambiguate candidates within the same chapter.
    """
    alive = [c for c in candidates if c["alive"]]
    if len(alive) <= 1:
        return candidates

    product_text = " ".join([
        product_info.get("description", ""),
        product_info.get("description_he", ""),
        product_info.get("material", ""),
    ])

    chapters_seen = set()
    for c in alive:
        chapter = c.get("chapter", "")
        if not chapter or chapter in chapters_seen:
            continue
        chapters_seen.add(chapter)

        # Only worth checking if multiple candidates in same chapter
        chapter_candidates = [
            x for x in alive if x["chapter"] == chapter
        ]
        if len(chapter_candidates) <= 1:
            continue

        notes = cache.get_chapter_notes(chapter)
        if not notes.get("found"):
            continue

        subheading_rules = notes.get("subheading_rules", [])
        if not subheading_rules:
            continue

        # Check if any subheading rule specifically references one of our
        # candidate headings and matches the product
        for rule_text in subheading_rules:
            rule_str = str(rule_text)
            heading_refs = _extract_heading_refs(rule_str)

            # Find which of our candidates are referenced
            referenced = [
                cc for cc in chapter_candidates
                if cc.get("heading", "") in heading_refs
            ]
            if not referenced:
                continue

            # Check if the rule text matches our product
            overlap_count, _ = _keyword_overlap(product_text, rule_str)
            if overlap_count >= 2:
                # Boost referenced candidates
                for cc in referenced:
                    cc["confidence"] = min(100, cc.get("confidence", 0) + 5)

                steps.append(_make_step(
                    level="subheading",
                    action="boost",
                    rule_type="gir_1",
                    rule_ref=f"D3 subheading rule ch{chapter}",
                    rule_text=rule_str[:300],
                    candidates_before=sum(1 for x in candidates if x["alive"]),
                    candidates_after=sum(1 for x in candidates if x["alive"]),
                    eliminated_codes=[],
                    kept_codes=[cc["hs_code"] for cc in referenced],
                    reasoning=(
                        f"Subheading rule in ch{chapter} references headings "
                        f"{heading_refs} and matches product (overlap={overlap_count})"
                    ),
                ))
                break  # One matching rule per chapter

    return candidates


# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 4a: D4 — GIR Rule 3 tiebreak (3א/3ב/3ג)
# ═══════════════════════════════════════════════════════════════════════════════

# ── D4 constants ──

# Essential character indicators — materials/components that typically define
# what a product "is" rather than secondary features
_ESSENTIAL_CHARACTER_TERMS = {
    # Metals
    "steel", "iron", "aluminum", "aluminium", "copper", "brass", "bronze",
    "zinc", "tin", "lead", "nickel", "titanium", "stainless",
    "פלדה", "ברזל", "אלומיניום", "נחושת", "פליז", "ארד",
    "אבץ", "בדיל", "עופרת", "ניקל", "טיטניום", "אל-חלד",
    # Plastics / rubber
    "plastic", "rubber", "silicone", "polyethylene", "polypropylene",
    "pvc", "nylon", "polyester", "acrylic", "epoxy",
    "פלסטיק", "גומי", "סיליקון", "פוליאתילן", "פוליפרופילן",
    "ניילון", "פוליאסטר", "אקריל", "אפוקסי",
    # Textiles
    "cotton", "wool", "silk", "linen", "polyester", "nylon",
    "כותנה", "צמר", "משי", "פשתן",
    # Wood / paper
    "wood", "wooden", "plywood", "mdf", "paper", "cardboard",
    "עץ", "דיקט", "נייר", "קרטון",
    # Glass / ceramic
    "glass", "ceramic", "porcelain", "crystal",
    "זכוכית", "קרמיקה", "חרסינה", "קריסטל",
    # Leather
    "leather", "suede", "עור", "זמש",
}

# Percentage/proportion patterns for "principally" test
_PERCENTAGE_RE = re.compile(r'(\d{1,3})\s*%')

# "Principally" / "mainly" / "באופן עיקרי" patterns
_PRINCIPALLY_RE = re.compile(
    r'(?:באופן\s+עיקרי|בעיקר|ברובו|ברובם|ברובה|'
    r'principally|mainly|predominantly|chiefly|essentially|'
    r'for\s+the\s+greater\s+part|consisting\s+(?:mainly|primarily)\s+of)',
    re.IGNORECASE
)

# "Others" / catch-all heading patterns (extends _VAGUE_HEADING_RE for D5)
_OTHERS_RE = re.compile(
    r'^[\s\-–—]*(?:אחר[ים|ות]?|other[s]?)[\s\-–—:;,.]*$|'
    r'(?:^|\s)(?:אחר[ים|ות]?|other[s]?)(?:\s|$)|'
    r'(?:שלא\s+(?:פורט|נכלל|צוין))|'
    r'(?:not\s+(?:elsewhere|otherwise)\s+(?:specified|included|provided))|'
    r'(?:n\.?e\.?s\.?(?:oi)?)',
    re.IGNORECASE
)


def _gir_3a_most_specific(cache, product_info, candidates):
    """D4 GIR 3א: The heading providing the most specific description wins.

    When two or more headings each refer to only part of the items in a
    mixed/composite product, those headings are equally specific. The one
    that describes the product most completely is preferred.

    Returns: list of (candidate, specificity_score) tuples, sorted best-first.
    """
    product_text = " ".join([
        product_info.get("description", ""),
        product_info.get("description_he", ""),
        product_info.get("material", ""),
        product_info.get("form", ""),
        product_info.get("use", ""),
    ])
    product_kw = set(_extract_keywords(product_text))

    scored = []
    for c in candidates:
        if not c["alive"]:
            continue

        heading_text = _get_heading_text(cache, c)
        heading_kw = set(_extract_keywords(heading_text))

        # GIR 3a scoring components:
        # 1. Keyword overlap breadth — how many product keywords are covered
        overlap = product_kw & heading_kw
        breadth = len(overlap) / max(len(product_kw), 1)

        # 2. Specificity — is this a specific or vague heading? (reuse D3)
        specificity = _score_heading_specificity(heading_text)

        # 3. Attribute match (material + form + use from D3)
        attr = _match_product_attributes(product_info, heading_text)

        # Combined 3a score
        score_3a = (breadth * 0.4) + (specificity * 0.3) + (attr * 0.3)
        scored.append((c, score_3a))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def _gir_3b_essential_character(product_info, candidates):
    """D4 GIR 3ב: Essential character test for composite/mixed goods.

    For products made of different materials or components, the heading
    that covers the material giving the product its essential character
    should be preferred.

    Uses material field from product_info. If no material info available,
    returns None (can't apply this rule).

    Returns: list of (candidate, essential_score) tuples, or None if N/A.
    """
    material = product_info.get("material", "").lower()
    if not material:
        return None  # Can't apply without material info

    material_words = set(_WORD_SPLIT_RE.split(material))
    material_words = {w for w in material_words if len(w) > 2 and w not in _STOP_WORDS}
    if not material_words:
        return None

    # Identify the primary (essential) material
    # If multiple materials listed, the first one is typically primary
    essential_materials = []
    for mw in material_words:
        if mw in _ESSENTIAL_CHARACTER_TERMS:
            essential_materials.append(mw)

    if not essential_materials:
        # No recognized material terms — can't determine essential character
        return None

    # The first recognized material term is treated as the essential one
    primary_material = essential_materials[0]

    scored = []
    for c in candidates:
        if not c["alive"]:
            continue

        heading_text = _get_heading_text(None, c).lower()
        heading_words = set(_WORD_SPLIT_RE.split(heading_text))

        # Score: does the heading mention the essential material?
        if primary_material in heading_words:
            score = 1.0
        elif material_words & heading_words:
            # Heading mentions a secondary material
            score = 0.5
        else:
            score = 0.0

        scored.append((c, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def _gir_3c_last_numerical(candidates):
    """D4 GIR 3ג: When 3a and 3b fail, classify under the heading which
    occurs last in numerical order among those equally meriting consideration.

    This is a pure fallback — only applies when other rules can't decide.
    Returns candidates sorted by HS code descending (last numerical first).
    """
    alive = [c for c in candidates if c["alive"]]
    if not alive:
        return []
    alive.sort(key=lambda c: c.get("hs_code", ""), reverse=True)
    return alive


def _apply_rule_3(cache, product_info, candidates, steps):
    """D4: GIR Rule 3 tiebreak — applies when multiple headings survive.

    Sequence:
    1. GIR 3א (most specific): prefer the heading that describes the
       product most specifically.
    2. GIR 3ב (essential character): for composite goods, prefer the heading
       covering the material giving the product its essential character.
    3. GIR 3ג (last numerical): fallback — prefer the heading that occurs
       last in numerical order.

    Conservative: only eliminates when there's a clear winner with
    significantly higher score than others.
    """
    alive = [c for c in candidates if c["alive"]]
    if len(alive) <= 1:
        return candidates

    # ── GIR 3א: Most specific description ──
    scored_3a = _gir_3a_most_specific(cache, product_info, candidates)
    if len(scored_3a) >= 2:
        best_score = scored_3a[0][1]
        second_score = scored_3a[1][1]

        # Only eliminate if clear gap: best is >= 2x the second-best
        # AND best is meaningful (>= 0.3)
        if best_score >= 0.3 and second_score > 0 and best_score >= second_score * 2.0:
            before_count = sum(1 for c in candidates if c["alive"])
            eliminated = []
            kept = []
            threshold = best_score * 0.4  # Eliminate below 40% of best

            for c, score in scored_3a:
                if score < threshold and c["alive"]:
                    c["alive"] = False
                    c["elimination_reason"] = (
                        f"GIR 3a: specificity score={score:.2f} < "
                        f"threshold={threshold:.2f} (best={best_score:.2f})"
                    )
                    c["eliminated_at_level"] = "gir_3a"
                    eliminated.append(c["hs_code"])
                elif c["alive"]:
                    kept.append(c["hs_code"])

            # Safety: ensure at least 1 survivor
            if eliminated and not kept:
                # Undo — restore the best candidate
                best_c = scored_3a[0][0]
                best_c["alive"] = True
                best_c["elimination_reason"] = ""
                best_c["eliminated_at_level"] = ""
                eliminated.remove(best_c["hs_code"])
                kept.append(best_c["hs_code"])

            after_count = sum(1 for c in candidates if c["alive"])

            if eliminated:
                steps.append(_make_step(
                    level="heading",
                    action="eliminate",
                    rule_type="gir_3a",
                    rule_ref="GIR 3a — most specific description",
                    rule_text="",
                    candidates_before=before_count,
                    candidates_after=after_count,
                    eliminated_codes=eliminated,
                    kept_codes=kept,
                    reasoning=(
                        f"GIR 3a: best specificity={best_score:.2f}, "
                        f"eliminated {len(eliminated)} below threshold={threshold:.2f}"
                    ),
                ))

    # Check if tiebreak resolved
    alive = [c for c in candidates if c["alive"]]
    if len(alive) <= 1:
        return candidates

    # ── GIR 3ב: Essential character ──
    scored_3b = _gir_3b_essential_character(product_info, candidates)
    if scored_3b and len(scored_3b) >= 2:
        best_score = scored_3b[0][1]
        second_score = scored_3b[1][1]

        # Only apply if there's a clear essential character winner
        # (score 1.0 = heading names the primary material, 0.5 = secondary)
        if best_score >= 1.0 and second_score < 1.0:
            before_count = sum(1 for c in candidates if c["alive"])
            eliminated = []
            kept = []

            for c, score in scored_3b:
                if score == 0.0 and c["alive"]:
                    c["alive"] = False
                    c["elimination_reason"] = (
                        f"GIR 3b: heading doesn't reference essential material "
                        f"(best={best_score:.1f})"
                    )
                    c["eliminated_at_level"] = "gir_3b"
                    eliminated.append(c["hs_code"])
                elif c["alive"]:
                    kept.append(c["hs_code"])

            # Safety: ensure at least 1 survivor
            if eliminated and not kept:
                best_c = scored_3b[0][0]
                best_c["alive"] = True
                best_c["elimination_reason"] = ""
                best_c["eliminated_at_level"] = ""
                eliminated.remove(best_c["hs_code"])
                kept.append(best_c["hs_code"])

            after_count = sum(1 for c in candidates if c["alive"])

            if eliminated:
                steps.append(_make_step(
                    level="heading",
                    action="eliminate",
                    rule_type="gir_3b",
                    rule_ref="GIR 3b — essential character",
                    rule_text="",
                    candidates_before=before_count,
                    candidates_after=after_count,
                    eliminated_codes=eliminated,
                    kept_codes=kept,
                    reasoning=(
                        f"GIR 3b: essential material match — "
                        f"eliminated {len(eliminated)} headings not referencing "
                        f"primary material"
                    ),
                ))

    # Check if tiebreak resolved
    alive = [c for c in candidates if c["alive"]]
    if len(alive) <= 1:
        return candidates

    # ── GIR 3ג: Last in numerical order ──
    # This is a pure fallback. We DON'T eliminate here — we just boost
    # the last-numerical candidate slightly so it wins in case of a true tie.
    # Actual elimination would be too aggressive for a "fallback" rule.
    sorted_alive = _gir_3c_last_numerical(candidates)
    if len(sorted_alive) >= 2:
        # Boost the last-numerical candidate by 1 point (very minor)
        last_numerical = sorted_alive[0]
        last_numerical["confidence"] = min(
            100, last_numerical.get("confidence", 0) + 1
        )
        steps.append(_make_step(
            level="heading",
            action="boost",
            rule_type="gir_3c",
            rule_ref="GIR 3c — last in numerical order",
            rule_text="",
            candidates_before=sum(1 for c in candidates if c["alive"]),
            candidates_after=sum(1 for c in candidates if c["alive"]),
            eliminated_codes=[],
            kept_codes=[last_numerical["hs_code"]],
            reasoning=(
                f"GIR 3c fallback: boosted {last_numerical['hs_code']} "
                f"(last numerical among {len(sorted_alive)} tied candidates)"
            ),
        ))

    return candidates


# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 4b: D5 — "אחרים" (Others) gate + "באופן עיקרי" (principally) test
# ═══════════════════════════════════════════════════════════════════════════════

def _is_others_heading(text):
    """D5: Detect if a heading/subheading is a catch-all "Others" entry.

    Returns True if the heading text is primarily a catch-all like:
    - "אחרים" / "אחרות" / "אחר" (Others)
    - "Other" / "Others"
    - "שלא פורט" / "שלא נכלל" (not elsewhere specified)
    - "n.e.s." / "not elsewhere specified"
    """
    if not text:
        return False
    text_stripped = str(text).strip()
    # Short text that is just "Others" or "אחרים"
    if len(text_stripped) < 30 and _OTHERS_RE.search(text_stripped):
        return True
    return False


def _is_others_candidate(candidate):
    """D5: Check if a candidate is in an "Others" catch-all category.

    Checks the candidate's own description and description_en fields.
    """
    desc = candidate.get("description", "")
    desc_en = candidate.get("description_en", "")
    return _is_others_heading(desc) or _is_others_heading(desc_en)


def _has_principally_qualifier(text):
    """D5: Check if heading text contains a 'principally' / 'באופן עיקרי' qualifier.

    These headings require that the product is PRIMARILY made of or used for
    the stated purpose/material — not just partially.
    """
    return bool(_PRINCIPALLY_RE.search(str(text)))


def _passes_principally_test(product_info, heading_text):
    """D5: Test whether a product passes the 'principally' requirement.

    If a heading says 'articles principally of iron or steel', the product
    must be primarily (>50%) made of that material.

    Returns: (passes, confidence) tuple.
    - passes=True if product likely passes the principally test
    - passes=None if we can't determine (insufficient info)
    - confidence is how sure we are (0.0-1.0)
    """
    material = product_info.get("material", "").lower()
    if not material:
        return None, 0.0  # Can't determine without material info

    heading_lower = str(heading_text).lower()
    heading_kw = set(_extract_keywords(heading_lower))
    material_kw = set(_extract_keywords(material))

    if not heading_kw or not material_kw:
        return None, 0.0

    # Check if heading mentions materials that match the product's material
    material_overlap = heading_kw & material_kw
    if not material_overlap:
        # Heading requires a material the product doesn't have
        return False, 0.6

    # Check for percentage in product description (e.g., "80% steel, 20% plastic")
    desc = product_info.get("description", "") + " " + product_info.get("description_he", "")
    pct_matches = _PERCENTAGE_RE.findall(desc)
    if pct_matches:
        # If we have percentages, the highest one is the primary material
        percentages = [int(p) for p in pct_matches]
        if max(percentages) > 50:
            # Primary material is >50%, principally test likely passes
            return True, 0.8
        elif max(percentages) <= 50:
            # No single material is >50%
            return False, 0.7

    # Without percentages, if material field matches heading, assume it passes
    # (material field typically lists the primary material)
    if material_overlap:
        return True, 0.5

    return None, 0.0


def _check_others_gate(cache, product_info, candidates, steps):
    """D5: "Others" gate + "principally" test.

    Two mechanisms:
    1. Others gate: If both specific and catch-all "Others" headings survive,
       demote/eliminate the "Others" candidates. Specific headings always
       take priority over catch-alls.

    2. Principally test: If a heading has a "principally/באופן עיקרי" qualifier,
       verify the product meets the majority composition requirement.
       If it doesn't, eliminate that candidate.
    """
    alive = [c for c in candidates if c["alive"]]
    if len(alive) <= 1:
        return candidates

    # ── Part 1: Others gate ──
    others_candidates = []
    specific_candidates = []
    for c in alive:
        if _is_others_candidate(c):
            others_candidates.append(c)
        else:
            specific_candidates.append(c)

    # If we have both specific and others candidates, demote/eliminate others
    if others_candidates and specific_candidates:
        before_count = sum(1 for c in candidates if c["alive"])
        eliminated = []
        kept = []

        for c in others_candidates:
            c["alive"] = False
            c["elimination_reason"] = (
                f"D5 Others gate: catch-all heading deprioritized — "
                f"{len(specific_candidates)} specific heading(s) available"
            )
            c["eliminated_at_level"] = "others_gate"
            eliminated.append(c["hs_code"])

        for c in specific_candidates:
            kept.append(c["hs_code"])

        after_count = sum(1 for c in candidates if c["alive"])

        if eliminated:
            steps.append(_make_step(
                level="heading",
                action="eliminate",
                rule_type="others_gate",
                rule_ref="D5 Others gate",
                rule_text="",
                candidates_before=before_count,
                candidates_after=after_count,
                eliminated_codes=eliminated,
                kept_codes=kept,
                reasoning=(
                    f"Eliminated {len(eliminated)} catch-all 'Others' headings; "
                    f"{len(kept)} specific headings remain"
                ),
            ))

    # ── Part 2: Principally test ──
    alive = [c for c in candidates if c["alive"]]
    if len(alive) <= 1:
        return candidates

    before_count = sum(1 for c in candidates if c["alive"])
    eliminated = []
    kept = []

    for c in alive:
        heading_text = _get_heading_text(cache, c)
        if not _has_principally_qualifier(heading_text):
            kept.append(c["hs_code"])
            continue

        # This heading has a "principally" qualifier — test if product passes
        passes, confidence = _passes_principally_test(product_info, heading_text)

        if passes is False and confidence >= 0.6:
            c["alive"] = False
            c["elimination_reason"] = (
                f"D5 principally test: product does not meet 'principally' "
                f"requirement for heading {c.get('heading', '')} "
                f"(confidence={confidence:.1f})"
            )
            c["eliminated_at_level"] = "principally"
            eliminated.append(c["hs_code"])
        else:
            kept.append(c["hs_code"])

    # Safety: ensure at least 1 survivor
    if eliminated and not kept:
        # Restore the first eliminated (least bad option)
        first = next(c for c in candidates
                     if c["hs_code"] == eliminated[0])
        first["alive"] = True
        first["elimination_reason"] = ""
        first["eliminated_at_level"] = ""
        eliminated.pop(0)
        kept.append(first["hs_code"])

    after_count = sum(1 for c in candidates if c["alive"])

    if eliminated:
        steps.append(_make_step(
            level="heading",
            action="eliminate",
            rule_type="principally",
            rule_ref="D5 principally/באופן עיקרי test",
            rule_text="",
            candidates_before=before_count,
            candidates_after=after_count,
            eliminated_codes=eliminated,
            kept_codes=kept,
            reasoning=(
                f"Eliminated {len(eliminated)} candidates failing 'principally' "
                f"composition test"
            ),
        ))

    return candidates


# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 4c: D6 — AI consultation at decision points
# ═══════════════════════════════════════════════════════════════════════════════

_AI_CONSULTATION_SYSTEM = """You are a customs classification expert. You are given:
- A product description
- Surviving HS code candidates after deterministic elimination
- The elimination steps already taken

Your task: Pick the BEST candidate or explain why you can't decide.

Respond in JSON only:
{
  "best_hs_code": "XXXXXXXX" or null,
  "confidence": 0-100,
  "reasoning": "one sentence",
  "eliminate": ["codes to eliminate"] or [],
  "needs_human": true/false
}"""


def _build_ai_consultation_prompt(product_info, candidates, steps):
    """Build the user prompt for AI consultation."""
    alive = [c for c in candidates if c["alive"]]

    lines = [
        f"Product: {product_info.get('description', '')}",
        f"Product (Hebrew): {product_info.get('description_he', '')}",
        f"Material: {product_info.get('material', '')}",
        f"Form: {product_info.get('form', '')}",
        f"Use: {product_info.get('use', '')}",
        "",
        f"Surviving candidates ({len(alive)}):",
    ]
    for c in alive:
        lines.append(
            f"  - {c['hs_code']} (ch{c.get('chapter','')}) "
            f"conf={c.get('confidence',0)} "
            f"desc=\"{c.get('description', '')[:100]}\""
        )

    lines.append("")
    lines.append(f"Elimination steps taken ({len(steps)}):")
    for s in steps[-10:]:  # Last 10 steps max
        lines.append(
            f"  - {s['level']}/{s['action']} {s['rule_type']}: "
            f"{s['reasoning'][:120]}"
        )

    return "\n".join(lines)


def _parse_ai_consultation_response(raw_text):
    """Parse AI consultation JSON response. Tolerant of markdown fences."""
    if not raw_text:
        return None
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        logger.warning(f"D6: Failed to parse AI response: {text[:200]}")
        return None


def _ai_consultation_hook(db, product_info, candidates, steps,
                          api_key=None, gemini_key=None):
    """D6: AI consultation when elimination engine can't decide.

    Called when multiple candidates survive the deterministic levels.
    Uses Gemini Flash for speed, Claude as fallback.

    Only invoked if needs_ai=True (>1 survivor). If API keys aren't
    provided, this is a no-op (graceful degradation).
    """
    alive = [c for c in candidates if c["alive"]]
    if len(alive) <= 1:
        return candidates

    # If no keys provided, try lazy import from environment
    if not gemini_key and not api_key:
        return candidates  # No keys = no-op, deterministic-only mode

    prompt = _build_ai_consultation_prompt(product_info, candidates, steps)

    # Call AI: Gemini Flash first, Claude fallback
    raw_response = None
    ai_source = "none"
    try:
        from lib.classification_agents import call_ai as _call_ai
        raw_response = _call_ai(
            api_key, gemini_key,
            _AI_CONSULTATION_SYSTEM, prompt,
            max_tokens=500, tier="fast"
        )
        ai_source = "gemini_flash"
    except ImportError:
        logger.info("D6: classification_agents not available, skipping AI consultation")
        return candidates
    except Exception as e:
        logger.warning(f"D6: AI consultation failed: {e}")
        return candidates

    if not raw_response:
        return candidates

    parsed = _parse_ai_consultation_response(raw_response)
    if not parsed:
        return candidates

    ai_source = "ai_consultation"
    eliminate_codes = parsed.get("eliminate", [])
    best_code = parsed.get("best_hs_code")
    ai_confidence = parsed.get("confidence", 0)
    reasoning = parsed.get("reasoning", "")

    if not eliminate_codes and not best_code:
        # AI couldn't decide either — record but don't act
        steps.append(_make_step(
            level="ai",
            action="keep",
            rule_type="ai_consultation",
            rule_ref="D6 AI consultation (inconclusive)",
            rule_text=reasoning[:500],
            candidates_before=len(alive),
            candidates_after=len(alive),
            eliminated_codes=[],
            kept_codes=[c["hs_code"] for c in alive],
            reasoning=f"AI consulted but couldn't decide: {reasoning[:200]}",
        ))
        return candidates

    # Apply AI eliminations
    before_count = sum(1 for c in candidates if c["alive"])
    eliminated = []
    kept = []

    for c in alive:
        if c["hs_code"] in eliminate_codes:
            c["alive"] = False
            c["elimination_reason"] = (
                f"D6 AI consultation: {reasoning[:150]}"
            )
            c["eliminated_at_level"] = "ai_consultation"
            eliminated.append(c["hs_code"])
        else:
            # If AI picked a best code, boost it
            if best_code and c["hs_code"] == _clean_hs(best_code):
                boost = min(15, max(5, ai_confidence // 10))
                c["confidence"] = min(100, c.get("confidence", 0) + boost)
            kept.append(c["hs_code"])

    # Safety: ensure at least 1 survivor
    if eliminated and not kept:
        best_c = alive[0]
        best_c["alive"] = True
        best_c["elimination_reason"] = ""
        best_c["eliminated_at_level"] = ""
        eliminated.remove(best_c["hs_code"])
        kept.append(best_c["hs_code"])

    after_count = sum(1 for c in candidates if c["alive"])

    steps.append(_make_step(
        level="ai",
        action="eliminate" if eliminated else "boost",
        rule_type="ai_consultation",
        rule_ref=f"D6 AI consultation (conf={ai_confidence})",
        rule_text=reasoning[:500],
        candidates_before=before_count,
        candidates_after=after_count,
        eliminated_codes=eliminated,
        kept_codes=kept,
        reasoning=(
            f"AI selected {best_code or 'none'} (conf={ai_confidence}), "
            f"eliminated {len(eliminated)}: {reasoning[:150]}"
        ),
    ))

    return candidates


# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 5: D7 — Devil's advocate
# ═══════════════════════════════════════════════════════════════════════════════

_DEVILS_ADVOCATE_SYSTEM = """You are a customs classification devil's advocate.
For the given HS code classification, provide ONE concise counter-argument:
why this code might be WRONG for this product.

Consider: wrong chapter scope, excluded category, better-fitting heading,
material mismatch, form vs function classification error.

Respond in JSON:
{
  "counter_argument": "one sentence why this code might be wrong",
  "alternative_code": "XXXX.XX" or null,
  "severity": "low"|"medium"|"high"
}"""


def _build_devils_advocate_prompt(product_info, candidate, steps):
    """Build prompt for devil's advocate challenge of one candidate."""
    lines = [
        f"Product: {product_info.get('description', '')}",
        f"Material: {product_info.get('material', '')}",
        f"Form: {product_info.get('form', '')}",
        f"Use: {product_info.get('use', '')}",
        "",
        f"Proposed HS code: {candidate.get('hs_code', '')}",
        f"Chapter: {candidate.get('chapter', '')}",
        f"Description: {candidate.get('description', '')}",
        f"Confidence: {candidate.get('confidence', 0)}",
        "",
        "Why might this classification be WRONG?",
    ]
    return "\n".join(lines)


def _run_devils_advocate(product_info, survivors, steps,
                         api_key=None, gemini_key=None):
    """D7: Generate counter-arguments for each survivor.

    For each surviving candidate, asks AI: "Why might this NOT be the right code?"
    Returns a list of challenge dicts, one per survivor.

    If no API keys available, returns empty list (graceful degradation).
    """
    if not survivors or (not gemini_key and not api_key):
        return []

    challenges = []
    try:
        from lib.classification_agents import call_ai as _call_ai
    except ImportError:
        logger.info("D7: classification_agents not available, skipping devil's advocate")
        return []

    for candidate in survivors[:5]:  # Cap at 5 to control costs
        prompt = _build_devils_advocate_prompt(product_info, candidate, steps)

        try:
            raw = _call_ai(
                api_key, gemini_key,
                _DEVILS_ADVOCATE_SYSTEM, prompt,
                max_tokens=300, tier="fast"
            )
        except Exception as e:
            logger.warning(f"D7: devil's advocate call failed for {candidate.get('hs_code')}: {e}")
            continue

        if not raw:
            continue

        parsed = _parse_ai_consultation_response(raw)
        if not parsed:
            continue

        challenges.append({
            "hs_code": candidate.get("hs_code", ""),
            "counter_argument": parsed.get("counter_argument", ""),
            "alternative_code": parsed.get("alternative_code"),
            "severity": parsed.get("severity", "low"),
        })

    return challenges


# ═══════════════════════════════════════════════════════════════════════════════
# D8: Elimination logging to Firestore
# ═══════════════════════════════════════════════════════════════════════════════

def _log_elimination_run(db, product_info, result, challenges=None):
    """D8: Log a complete elimination run to Firestore elimination_log collection.

    Creates one document per run with full audit trail: input candidates,
    each elimination step, survivors, AI consultations, and devil's advocate
    challenges.

    Safe: if db is None or write fails, logs warning and continues.
    """
    if db is None:
        return

    timestamp = datetime.now(timezone.utc)
    doc_id = f"elim_{timestamp.strftime('%Y%m%d_%H%M%S')}_{id(result) % 10000:04d}"

    # Sanitize candidates for Firestore (strip large fields)
    def _sanitize_candidate(c):
        return {
            "hs_code": c.get("hs_code", ""),
            "chapter": c.get("chapter", ""),
            "heading": c.get("heading", ""),
            "section": c.get("section", ""),
            "confidence": c.get("confidence", 0),
            "source": c.get("source", ""),
            "description": str(c.get("description", ""))[:200],
            "alive": c.get("alive", False),
            "elimination_reason": str(c.get("elimination_reason", ""))[:300],
            "eliminated_at_level": c.get("eliminated_at_level", ""),
        }

    # Sanitize steps (keep concise)
    def _sanitize_step(s):
        return {
            "level": s.get("level", ""),
            "action": s.get("action", ""),
            "rule_type": s.get("rule_type", ""),
            "rule_ref": str(s.get("rule_ref", ""))[:200],
            "candidates_before": s.get("candidates_before", 0),
            "candidates_after": s.get("candidates_after", 0),
            "eliminated_codes": s.get("eliminated_codes", []),
            "kept_codes": s.get("kept_codes", []),
            "reasoning": str(s.get("reasoning", ""))[:300],
        }

    log_doc = {
        "timestamp": timestamp.isoformat(),
        "product_description": str(product_info.get("description", ""))[:500],
        "product_description_he": str(product_info.get("description_he", ""))[:500],
        "product_material": str(product_info.get("material", ""))[:200],
        "product_form": str(product_info.get("form", ""))[:200],
        "product_use": str(product_info.get("use", ""))[:200],
        "input_count": result.get("input_count", 0),
        "survivor_count": result.get("survivor_count", 0),
        "needs_ai": result.get("needs_ai", False),
        "needs_questions": result.get("needs_questions", False),
        "survivors": [
            _sanitize_candidate(c) for c in result.get("survivors", [])
        ],
        "eliminated": [
            _sanitize_candidate(c) for c in result.get("eliminated", [])
        ],
        "steps": [
            _sanitize_step(s) for s in result.get("steps", [])
        ],
        "sections_checked": result.get("sections_checked", []),
        "chapters_checked": result.get("chapters_checked", []),
        "step_count": len(result.get("steps", [])),
        "challenges": challenges or [],
    }

    try:
        db.collection("elimination_log").document(doc_id).set(log_doc)
        logger.info(f"D8: Logged elimination run to elimination_log/{doc_id}")
    except Exception as e:
        logger.warning(f"D8: Failed to log elimination run: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 5: BUILD RESULT
# ═══════════════════════════════════════════════════════════════════════════════

def _build_result(candidates, steps, sections_checked, chapters_checked,
                  input_count):
    """Build the final EliminationResult from surviving/eliminated candidates + steps."""
    survivors = [c for c in candidates if c["alive"]]
    eliminated = [c for c in candidates if not c["alive"]]

    return {
        "survivors": survivors,
        "eliminated": eliminated,
        "steps": steps,
        "sections_checked": list(sections_checked),
        "chapters_checked": list(chapters_checked),
        "input_count": input_count,
        "survivor_count": len(survivors),
        "needs_ai": len(survivors) > 1,
        "needs_questions": len(survivors) > 3,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def eliminate(db, product_info, candidates, api_key=None, gemini_key=None):
    """Walk the tariff tree and eliminate candidates deterministically.

    Args:
        db: Firestore client
        product_info: ProductInfo dict (from make_product_info)
        candidates: list of HSCandidate dicts (from candidates_from_pre_classify
                    or manually constructed)
        api_key: optional Anthropic API key for AI consultation (D6/D7)
        gemini_key: optional Gemini API key for AI consultation (D6/D7)

    Returns:
        EliminationResult dict with survivors, eliminated, steps, metadata,
        and challenges (D7 devil's advocate).
    """
    if not candidates:
        result = _build_result([], [], set(), set(), 0)
        result["challenges"] = []
        return result

    # Ensure all candidates have alive=True and required fields
    for c in candidates:
        c.setdefault("alive", True)
        c.setdefault("elimination_reason", "")
        c.setdefault("eliminated_at_level", "")
        c.setdefault("confidence", 0)
        if not c.get("chapter") and c.get("hs_code"):
            c["chapter"] = _chapter_from_hs(c["hs_code"])
        if not c.get("heading") and c.get("hs_code"):
            c["heading"] = _heading_from_hs(c["hs_code"])
        if not c.get("subheading") and c.get("hs_code"):
            c["subheading"] = _subheading_from_hs(c["hs_code"])
        c.setdefault("section", "")

    input_count = len(candidates)
    steps = []
    cache = TariffCache(db)

    logger.info(
        f"Elimination engine: starting with {input_count} candidates for "
        f"product '{product_info.get('description', '')[:80]}'"
    )

    # Level 0: ENRICH — resolve sections
    candidates = _enrich_candidates(cache, candidates)

    # Track which sections/chapters we checked
    sections_checked = {c.get("section") for c in candidates if c.get("section")}
    chapters_checked = {c.get("chapter") for c in candidates if c.get("chapter")}

    # Level 1: SECTION SCOPE
    candidates = _apply_section_scope(cache, product_info, candidates, steps)
    alive_count = sum(1 for c in candidates if c["alive"])
    logger.info(f"After section scope: {alive_count}/{input_count} alive")

    # Level 2a: D2 — PREAMBLE SCOPE (chapter preamble relevance)
    candidates = _apply_preamble_scope(cache, product_info, candidates, steps)

    # Level 2b: CHAPTER EXCLUSIONS/INCLUSIONS (with D2 conditional handling)
    candidates = _apply_chapter_exclusions_inclusions(
        cache, product_info, candidates, steps
    )
    alive_count = sum(1 for c in candidates if c["alive"])
    logger.info(f"After chapter exclusions/inclusions: {alive_count}/{input_count} alive")

    # Level 2c: D2 — CROSS-CHAPTER REDIRECT BOOST
    candidates = _apply_cross_chapter_boost(candidates, steps)

    # Level 2d: D2 — DEFINITION MATCHING
    candidates = _apply_definition_matching(
        cache, product_info, candidates, steps
    )

    # Level 3: HEADING MATCH — GIR 1 full semantics (D3)
    candidates = _apply_heading_match(cache, product_info, candidates, steps)
    alive_count = sum(1 for c in candidates if c["alive"])
    logger.info(f"After heading match: {alive_count}/{input_count} alive")

    # Level 3b: D3 — SUBHEADING NOTES
    candidates = _apply_subheading_notes(
        cache, product_info, candidates, steps
    )

    # Level 4a: D4 — GIR RULE 3 TIEBREAK (3א/3ב/3ג)
    candidates = _apply_rule_3(cache, product_info, candidates, steps)
    alive_count = sum(1 for c in candidates if c["alive"])
    logger.info(f"After GIR 3 tiebreak: {alive_count}/{input_count} alive")

    # Level 4b: D5 — OTHERS GATE + PRINCIPALLY TEST
    candidates = _check_others_gate(cache, product_info, candidates, steps)
    alive_count = sum(1 for c in candidates if c["alive"])
    logger.info(f"After others gate + principally: {alive_count}/{input_count} alive")

    # Level 4c: D6 — AI CONSULTATION (when >1 survivor and keys available)
    candidates = _ai_consultation_hook(
        db, product_info, candidates, steps,
        api_key=api_key, gemini_key=gemini_key
    )
    alive_count = sum(1 for c in candidates if c["alive"])
    logger.info(f"After AI consultation: {alive_count}/{input_count} alive")

    # Level 5: BUILD RESULT
    result = _build_result(
        candidates, steps, sections_checked, chapters_checked, input_count
    )

    # Level 6: D7 — DEVIL'S ADVOCATE
    challenges = _run_devils_advocate(
        product_info, result["survivors"], steps,
        api_key=api_key, gemini_key=gemini_key
    )
    result["challenges"] = challenges
    if challenges:
        logger.info(f"D7: {len(challenges)} devil's advocate challenges generated")

    # Level 7: D8 — LOG TO FIRESTORE
    _log_elimination_run(db, product_info, result, challenges)

    logger.info(
        f"Elimination engine: {result['survivor_count']}/{input_count} survivors, "
        f"{len(steps)} steps, needs_ai={result['needs_ai']}"
    )

    return result
