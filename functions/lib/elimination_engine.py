"""
Elimination Engine — Core tree-walking logic for HS code classification.

Phase 3 of the RCB target architecture. Walks the tariff tree deterministically,
eliminating candidates using section scope, chapter exclusions/inclusions, and
heading-level keyword matching. AI participates but the method has final say.

D1: Core framework (data structures, cache, tree walk, chapter-level matching).
D2: Chapter elimination using full chapter notes (preamble scope, definitions,
    conditional exclusions, cross-chapter redirects).
D3: Heading elimination — GIR 1 full semantics (specificity scoring, product
    attribute matching, relative elimination, subheading notes).
D4-D9: GIR 3 rules, AI hooks, logging, and pipeline wiring.

Public API:
    eliminate(db, product_info, candidates) -> EliminationResult
    candidates_from_pre_classify(pre_classify_result) -> list[HSCandidate]
    make_product_info(item_dict) -> ProductInfo
"""

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
    if heading:
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
# LEVEL 4: STUBS — D4-D6 fill these in
# ═══════════════════════════════════════════════════════════════════════════════

def _apply_rule_3(candidates, steps):
    """GIR 3a/3b/3c tiebreak. Stub — D4 implements."""
    return candidates


def _check_others_gate(candidates, steps):
    """Check for 'Others' (אחרים) catch-all headings. Stub — D5 implements."""
    return candidates


def _ai_consultation_hook(db, product_info, candidates, steps):
    """AI consultation at decision points. Stub — D6 implements."""
    return candidates


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

def eliminate(db, product_info, candidates):
    """Walk the tariff tree and eliminate candidates deterministically.

    Args:
        db: Firestore client
        product_info: ProductInfo dict (from make_product_info)
        candidates: list of HSCandidate dicts (from candidates_from_pre_classify
                    or manually constructed)

    Returns:
        EliminationResult dict with survivors, eliminated, steps, and metadata.
    """
    if not candidates:
        return _build_result([], [], set(), set(), 0)

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

    # Level 4: STUBS (D4-D5)
    candidates = _apply_rule_3(candidates, steps)
    candidates = _check_others_gate(candidates, steps)
    candidates = _ai_consultation_hook(db, product_info, candidates, steps)

    # Level 5: BUILD RESULT
    result = _build_result(
        candidates, steps, sections_checked, chapters_checked, input_count
    )

    logger.info(
        f"Elimination engine: {result['survivor_count']}/{input_count} survivors, "
        f"{len(steps)} steps, needs_ai={result['needs_ai']}"
    )

    return result
