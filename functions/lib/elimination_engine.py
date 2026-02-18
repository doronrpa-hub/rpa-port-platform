"""
Elimination Engine — Core tree-walking logic for HS code classification.

Phase 3 of the RCB target architecture. Walks the tariff tree deterministically,
eliminating candidates using section scope, chapter exclusions/inclusions, and
heading-level keyword matching. AI participates but the method has final say.

Block D1: Core framework (data structures, cache, tree walk, chapter-level matching).
D2-D9 add GIR rules, AI hooks, logging, and pipeline wiring.

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


def _apply_chapter_exclusions_inclusions(cache, product_info, candidates, steps):
    """Apply chapter-level exclusions and inclusions.

    For each alive candidate's chapter:
    - Load chapter_notes
    - Check exclusions: if product matches an exclusion -> ELIMINATE
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
# LEVEL 3: HEADING MATCH — GIR 1 basic (keyword overlap)
# ═══════════════════════════════════════════════════════════════════════════════

def _apply_heading_match(cache, product_info, candidates, steps):
    """Check heading description vs product using keyword overlap.

    Specific headings survive over vague ones. Only eliminates headings
    with very low overlap when better matches exist.
    Stub for D3: full GIR 1 semantics.
    """
    alive = [c for c in candidates if c["alive"]]
    if len(alive) <= 1:
        return candidates

    # Score each alive candidate by heading description overlap
    product_text = " ".join([
        product_info.get("description", ""),
        product_info.get("description_he", ""),
        product_info.get("material", ""),
        product_info.get("use", ""),
    ])

    heading_scores = {}  # hs_code -> score
    for c in alive:
        heading = c.get("heading", "")
        if not heading:
            heading_scores[c["hs_code"]] = 0
            continue

        # Use cached heading docs for description
        heading_docs = cache.get_heading_docs(heading)
        heading_text_parts = [c.get("description", ""), c.get("description_en", "")]
        for hd in heading_docs:
            heading_text_parts.append(hd.get("description_he", ""))
            heading_text_parts.append(hd.get("description_en", ""))
        heading_text = " ".join(heading_text_parts)

        overlap_count, overlap_ratio = _keyword_overlap(product_text, heading_text)
        heading_scores[c["hs_code"]] = overlap_count

    # Find the best score
    if not heading_scores:
        return candidates
    best_score = max(heading_scores.values())
    if best_score == 0:
        return candidates  # No signal — keep all alive

    # Eliminate candidates with 0 overlap when best > 0 AND at least
    # 2 candidates have positive scores (so we're not randomly picking)
    positive_count = sum(1 for s in heading_scores.values() if s > 0)
    if positive_count < 2 and best_score < 3:
        # Not enough signal to eliminate — keep all
        return candidates

    before_count = sum(1 for c in candidates if c["alive"])
    eliminated = []
    kept = []
    for c in alive:
        score = heading_scores.get(c["hs_code"], 0)
        if score == 0 and best_score >= 2:
            c["alive"] = False
            c["elimination_reason"] = (
                f"Heading {c.get('heading', '')} has zero keyword overlap "
                f"with product (best heading score: {best_score})"
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
            rule_ref="GIR 1 basic — heading keyword match",
            rule_text="",
            candidates_before=before_count,
            candidates_after=after_count,
            eliminated_codes=eliminated,
            kept_codes=kept,
            reasoning=(
                f"Eliminated {len(eliminated)} candidates with zero heading overlap; "
                f"best heading score={best_score}, {len(kept)} survivors"
            ),
        ))

    return candidates


# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 4: STUBS — D2-D5 fill these in
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

    # Level 2: CHAPTER EXCLUSIONS/INCLUSIONS
    candidates = _apply_chapter_exclusions_inclusions(
        cache, product_info, candidates, steps
    )
    alive_count = sum(1 for c in candidates if c["alive"])
    logger.info(f"After chapter exclusions/inclusions: {alive_count}/{input_count} alive")

    # Level 3: HEADING MATCH (GIR 1 basic)
    candidates = _apply_heading_match(cache, product_info, candidates, steps)
    alive_count = sum(1 for c in candidates if c["alive"])
    logger.info(f"After heading match: {alive_count}/{input_count} alive")

    # Level 4: STUBS (D2-D5)
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
