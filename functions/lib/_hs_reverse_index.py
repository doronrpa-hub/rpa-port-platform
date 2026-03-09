# -*- coding: utf-8 -*-
"""HS reverse indexes — discount codes and FTA rates mapped to tariff headings.

Provides:
  get_discount_codes(hs_code) -> list of applicable discount code entries
  get_fta_rates(hs_code) -> dict of {country_code: {rate, origin_rule, ...}}

Uses librarian.normalize_hs_code() as the single normalizer — no duplicates.

Built at import time by scanning:
  1. _discount_codes_data.py — regex + keyword extraction from Hebrew descriptions
  2. _fta_all_countries.py — FTA agreement metadata per country

Author: Session 102 (2026-03-09)
"""

import re
from typing import Dict, List, Optional, Any

from lib.librarian import normalize_hs_code


# ---------------------------------------------------------------------------
#  Regex patterns for extracting HS codes from Hebrew discount descriptions
# ---------------------------------------------------------------------------

# Matches dotted HS codes: 87.11, 07.12.9010, 60.04.1000, 49.03, 51.06
_HS_DOTTED_RE = re.compile(r'(\d{2}\.\d{2}(?:\.\d{4,6})?)')

# Heading range: "55.12-55.16" or "55.12–55.16" or "55.12 עד 55.16"
_HS_RANGE_RE = re.compile(
    r'(\d{2}\.\d{2})(?:\.\d{4,6})?\s*[-\u2013\u05e2\u05d3]\s*(\d{2}\.\d{2})'
)

# Chapter references: "פרק 87", "לפרק 87", "פרקים 84, 85, 88, 90"
_CHAPTER_RE = re.compile(
    r'(?:\u05e4\u05e8\u05e7(?:\u05d9\u05dd)?|\u05dc\u05e4\u05e8\u05e7)'  # פרק/פרקים/לפרק
    r'\s+(\d{1,2}(?:\s*[,\u05d5]\s*\d{1,2})*)'
)

# Section references: "חלק XI", "חלק XVI"
_SECTION_RE = re.compile(
    r'\u05d7\u05dc\u05e7'  # חלק
    r'\s+(XXI{0,2}|XVI{0,3}|XI{0,3}V?|VI{0,3}|IV|I{1,3})\b'
)

# Roman numeral -> section number
_ROMAN_TO_INT = {
    'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7,
    'VIII': 8, 'IX': 9, 'X': 10, 'XI': 11, 'XII': 12, 'XIII': 13,
    'XIV': 14, 'XV': 15, 'XVI': 16, 'XVII': 17, 'XVIII': 18,
    'XIX': 19, 'XX': 20, 'XXI': 21, 'XXII': 22,
}

# Section number -> (first_chapter, last_chapter)
_SECTION_CHAPTERS = {
    1: (1, 5), 2: (6, 14), 3: (15, 15), 4: (16, 24), 5: (25, 27),
    6: (28, 38), 7: (39, 40), 8: (41, 43), 9: (44, 46), 10: (47, 49),
    11: (50, 63), 12: (64, 67), 13: (68, 70), 14: (71, 71), 15: (72, 83),
    16: (84, 85), 17: (86, 89), 18: (90, 92), 19: (93, 93), 20: (94, 96),
    21: (97, 97), 22: (98, 99),
}

# ---------------------------------------------------------------------------
#  Hebrew keyword -> chapter mappings (product types in discount descriptions)
# ---------------------------------------------------------------------------

_KEYWORD_CHAPTERS: Dict[str, List[int]] = {
    # --- Section I: Live animals (ch1-5) ---
    '\u05d1\u05e2\u05dc\u05d9 \u05d7\u05d9\u05d9\u05dd': [1, 2, 3, 4, 5],  # בעלי חיים
    # --- Section II-IV: Food/agriculture (ch1-24) ---
    '\u05de\u05d6\u05d5\u05df': list(range(1, 25)),  # מזון
    '\u05d7\u05e7\u05dc\u05d0': [6, 7, 8, 9, 10, 11, 12, 13, 14],  # חקלא*
    '\u05e9\u05d5\u05dd': [7],  # שום
    '\u05e7\u05d5\u05e7\u05d5\u05e1': [8],  # קוקוס
    '\u05de\u05e9\u05e7\u05d0\u05d5\u05ea': [22],  # משקאות
    '\u05d8\u05d1\u05e7': [24],  # טבק
    '\u05d0\u05dc\u05db\u05d5\u05d4\u05dc': [22],  # אלכוהול
    # --- Section V: Mineral (ch25-27) ---
    '\u05d3\u05dc\u05e7': [27],  # דלק
    '\u05e0\u05e4\u05d8': [27],  # נפט
    '\u05de\u05d9\u05e0\u05e8\u05dc': [25, 26],  # מינרל
    # --- Section VI: Chemical (ch28-38) ---
    '\u05db\u05d9\u05de': [28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38],  # כימ*
    '\u05ea\u05e8\u05d5\u05e4': [30],  # תרופ*
    '\u05e8\u05e4\u05d5\u05d0': [30],  # רפוא*
    '\u05d0\u05d5\u05e8\u05d8\u05d5\u05e4\u05d3': [90],  # אורטופד*
    '\u05e1\u05d1\u05d5\u05df': [34],  # סבון
    '\u05d1\u05d5\u05e9\u05dd': [33],  # בושם
    '\u05e6\u05d1\u05e2': [32],  # צבע
    '\u05d3\u05e9\u05e0\u05d9\u05dd': [31],  # דשנים
    '\u05e9\u05de\u05df': [15, 33],  # שמן
    '\u05e1\u05e8\u05d8': [37],  # סרט (film)
    '\u05e9\u05e7\u05d5\u05e4\u05d9\u05ea': [37],  # שקופית
    # --- Section VII: Plastics/rubber (ch39-40) ---
    '\u05e4\u05dc\u05e1\u05d8\u05d9\u05e7': [39],  # פלסטיק
    '\u05d2\u05d5\u05de\u05d9': [40],  # גומי
    '\u05e6\u05de\u05d9\u05d2': [40],  # צמיג
    # --- Section VIII: Leather (ch41-43) ---
    '\u05e2\u05d5\u05e8': [42],  # עור
    '\u05d7\u05e4\u05e6\u05d9 \u05e0\u05e1\u05d9\u05e2\u05d4': [42],  # חפצי נסיעה
    '\u05ea\u05d9\u05e7': [42],  # תיק*
    '\u05d0\u05e8\u05e0\u05e7': [42],  # ארנק
    '\u05d9\u05dc\u05e7\u05d5\u05d8': [42],  # ילקוט
    # --- Section IX: Wood (ch44-46) ---
    '\u05e2\u05e5': [44],  # עץ
    '\u05e9\u05e2\u05dd': [45],  # שעם
    # --- Section X: Paper (ch47-49) ---
    '\u05e0\u05d9\u05d9\u05e8': [48],  # נייר
    '\u05e1\u05e4\u05e8': [49],  # ספר
    '\u05d3\u05e4\u05d5\u05e1': [49],  # דפוס
    '\u05d1\u05e8\u05d9\u05d9\u05dc': [49],  # ברייל
    # --- Section XI: Textiles (ch50-63) ---
    '\u05d8\u05e7\u05e1\u05d8\u05d9\u05dc': list(range(50, 64)),  # טקסטיל
    '\u05e6\u05de\u05e8': [51],  # צמר
    '\u05db\u05d5\u05ea\u05e0\u05d4': [52],  # כותנה
    '\u05de\u05e9\u05d9': [50],  # משי
    '\u05d1\u05d3\u05d9\u05dd': list(range(50, 64)),  # בדים
    '\u05d0\u05e8\u05d9\u05d2': list(range(50, 64)),  # אריג
    '\u05d4\u05dc\u05d1\u05e9\u05d4': [61, 62],  # הלבשה
    '\u05dc\u05d1\u05d5\u05e9': [61, 62],  # לבוש
    '\u05dc\u05d1\u05d5\u05e9 \u05de\u05d2\u05df': [61, 62],  # לבוש מגן
    '\u05d7\u05d5\u05d8': list(range(50, 64)),  # חוט
    '\u05de\u05d5\u05dc\u05d1\u05e0\u05d9\u05dd': list(range(50, 64)),  # מולבנים
    '\u05e7\u05d5\u05d5\u05e8\u05e0': [56, 57, 58],  # קוורנ* (beehive fabric)
    # --- Section XII: Footwear/headgear (ch64-67) ---
    '\u05d4\u05e0\u05e2\u05dc\u05d4': [64],  # הנעלה
    '\u05e0\u05e2\u05dc': [64],  # נעל*
    '\u05db\u05d5\u05d1\u05e2': [65],  # כובע
    '\u05de\u05d8\u05e8\u05d9': [66],  # מטרי*
    # --- Section XIII: Stone/ceramic/glass (ch68-70) ---
    '\u05d6\u05db\u05d5\u05db\u05d9\u05ea': [70],  # זכוכית
    '\u05e7\u05e8\u05de\u05d9\u05e7': [69],  # קרמיק
    '\u05d0\u05d1\u05df': [68],  # אבן
    # --- Section XIV: Precious (ch71) ---
    '\u05ea\u05db\u05e9\u05d9\u05d8': [71],  # תכשיט*
    '\u05d9\u05d4\u05dc\u05d5': [71],  # יהלו*
    '\u05d6\u05d4\u05d1': [71],  # זהב
    '\u05db\u05e1\u05e3': [71],  # כסף
    # --- Section XV: Base metals (ch72-83) ---
    '\u05d1\u05e8\u05d6\u05dc': [72, 73],  # ברזל
    '\u05e4\u05dc\u05d3\u05d4': [72, 73],  # פלדה
    '\u05d0\u05dc\u05d5\u05de\u05d9\u05e0\u05d9\u05d5\u05dd': [76],  # אלומיניום
    '\u05e0\u05d7\u05d5\u05e9\u05ea': [74],  # נחושת
    '\u05de\u05ea\u05db': list(range(72, 84)),  # מתכ*
    '\u05de\u05e0\u05e2\u05d5\u05dc': [83],  # מנעול*
    # --- Section XVI: Machinery/electrical (ch84-85) ---
    '\u05de\u05db\u05d5\u05e0': [84],  # מכונ*
    '\u05de\u05db\u05e9\u05d9\u05e8': [84, 85, 90],  # מכשיר*
    '\u05d7\u05e9\u05de\u05dc': [85],  # חשמל*
    '\u05d0\u05dc\u05e7\u05d8\u05e8\u05d5\u05e0': [85],  # אלקטרונ*
    '\u05de\u05d7\u05e9\u05d1': [84, 85],  # מחשב
    '\u05d8\u05dc\u05d5\u05d5\u05d9\u05d6\u05d9\u05d4': [85],  # טלוויזיה
    '\u05ea\u05e7\u05e9\u05d5\u05e8\u05ea': [85],  # תקשורת
    # --- Section XVII: Transport (ch86-89) ---
    '\u05e8\u05db\u05d1': [87],  # רכב
    '\u05de\u05e0\u05d5\u05e2\u05d9': [87],  # מנועי
    '\u05d0\u05d5\u05e4\u05e0\u05d5\u05e2': [87],  # אופנוע
    '\u05de\u05e9\u05d0\u05d9\u05ea': [87],  # משאית
    '\u05e1\u05e4\u05d9\u05e0': [89],  # ספינ*
    '\u05de\u05d8\u05d5\u05e1': [88],  # מטוס
    '\u05d0\u05d5\u05d5\u05d9\u05e8': [88],  # אוויר*
    '\u05ea\u05d7\u05e8\u05d5\u05ea': [87],  # תחרות (competition vehicles)
    '\u05e0\u05d4\u05d2\u05d9\u05dd': [87],  # נהגים
    '\u05e8\u05d5\u05db\u05d1\u05d9\u05dd': [87],  # רוכבים
    '\u05d4\u05d9\u05d1\u05e8\u05d9\u05d3\u05d9': [87],  # היברידי
    '\u05e4\u05dc\u05d0\u05d2-\u05d0\u05d9\u05df': [87],  # פלאג-אין
    '\u05e6\u05d9\u05dc\u05d9\u05e0\u05d3\u05e8': [87],  # צילינדר
    '\u05de\u05d5\u05e0\u05d9\u05ea': [87],  # מונית
    '\u05d4\u05d5\u05d1\u05dc': [87],  # הובל*
    # --- Section XVIII: Optical/instruments (ch90-92) ---
    '\u05d0\u05d5\u05e4\u05d8\u05d9': [90],  # אופטי*
    '\u05e6\u05d9\u05dc\u05d5\u05dd': [90],  # צילום
    '\u05e9\u05e2\u05d5\u05df': [91],  # שעון
    '\u05db\u05dc\u05d9 \u05e0\u05d2\u05d9\u05e0\u05d4': [92],  # כלי נגינה
    # --- Section XIX: Arms (ch93) ---
    '\u05e0\u05e9\u05e7': [93],  # נשק
    '\u05ea\u05d7\u05de\u05d5\u05e9\u05ea': [93],  # תחמושת
    '\u05de\u05de\u05d5\u05d2\u05df': [87, 93],  # ממוגן (armored, also ch87)
    '\u05e9\u05e8\u05d9\u05d5\u05df': [93],  # שריון
    # --- Section XX: Miscellaneous (ch94-96) ---
    '\u05e8\u05d4\u05d9\u05d8': [94],  # רהיט*
    '\u05e6\u05e2\u05e6\u05d5\u05e2': [95],  # צעצוע
    '\u05e1\u05e4\u05d5\u05e8\u05d8': [95],  # ספורט
    '\u05de\u05d5\u05e9\u05d1': [94],  # מושב
    # --- Section XXI: Art (ch97) ---
    '\u05d0\u05de\u05e0\u05d5\u05ea': [97],  # אמנות
    '\u05e2\u05ea\u05d9\u05e7': [97],  # עתיק*
    # --- Broad categories ---
    '\u05d3\u05d5\u05d2\u05de': list(range(1, 98)),  # דוגמ* (samples — all chapters)
    '\u05ea\u05e8\u05d5\u05de\u05d4': list(range(1, 98)),  # תרומה (donation — all)
    '\u05d7\u05e0\u05d5\u05da': list(range(1, 98)),  # חנוך (education — all)
    '\u05d7\u05d9\u05e0\u05d5\u05da': list(range(1, 98)),  # חינוך (education — all)
    '\u05de\u05d7\u05e7\u05e8': list(range(1, 98)),  # מחקר (research — all)
}


def _to_heading(code_str: str) -> str:
    """Normalize any HS code format to a 4-digit heading using librarian."""
    return normalize_hs_code(code_str)[:4]


def _expand_heading_range(start: str, end: str) -> List[str]:
    """Expand 'XX.XX' to 'XX.XX' range into list of 4-digit headings.

    E.g., '55.12' to '55.16' -> ['5512', '5513', '5514', '5515', '5516']
    """
    s = int(start.replace(".", ""))
    e = int(end.replace(".", ""))
    return [f"{h:04d}" for h in range(s, e + 1)]


def _chapters_to_ch_keys(chapters: List[int]) -> List[str]:
    """Convert list of chapter ints to ch-keys like 'ch87'."""
    return [f"ch{c:02d}" for c in chapters]


# ---------------------------------------------------------------------------
#  Build discount code reverse index
# ---------------------------------------------------------------------------

def _extract_headings_from_text(text: str) -> set:
    """Extract all 4-digit headings from a Hebrew description.

    Uses 4 layers:
      1. Dotted HS codes: "87.11", "07.12.9010"
      2. Heading ranges: "55.12-55.16"
      3. Chapter references: "פרק 87", "פרקים 84, 85, 88, 90"
      4. Section references: "חלק XI"
    """
    headings = set()

    # Layer 1: Dotted HS codes
    for m in _HS_DOTTED_RE.finditer(text):
        headings.add(_to_heading(m.group(1)))

    # Layer 2: Heading ranges
    for m in _HS_RANGE_RE.finditer(text):
        for h in _expand_heading_range(m.group(1), m.group(2)):
            headings.add(h)

    # Layer 3: Chapter references (may contain comma-separated list)
    for m in _CHAPTER_RE.finditer(text):
        nums_str = m.group(1)
        # Split on comma or vav (ו)
        for part in re.split(r'[,\u05d5]', nums_str):
            part = part.strip()
            if part.isdigit():
                ch = int(part)
                if 1 <= ch <= 99:
                    headings.add(f"ch{ch:02d}")

    # Layer 4: Section references
    for m in _SECTION_RE.finditer(text):
        roman = m.group(1).strip()
        sec_num = _ROMAN_TO_INT.get(roman)
        if sec_num and sec_num in _SECTION_CHAPTERS:
            lo, hi = _SECTION_CHAPTERS[sec_num]
            for ch in range(lo, hi + 1):
                headings.add(f"ch{ch:02d}")

    return headings


def _keyword_chapters_from_text(text: str) -> set:
    """Match product keywords in text against chapter mapping."""
    chapters = set()
    for kw, chs in _KEYWORD_CHAPTERS.items():
        if kw in text:
            for ch in chs:
                chapters.add(f"ch{ch:02d}")
    return chapters


def _build_discount_index() -> Dict[str, List[Dict[str, Any]]]:
    """Build HS heading -> discount code entries map.

    Scans all discount codes for HS references via:
    1. Explicit hs_codes field (already populated on some entries)
    2. Dotted HS regex from descriptions
    3. Heading ranges from descriptions
    4. Chapter references from descriptions
    5. Section references from descriptions
    6. Product keyword matching against chapter map
    """
    from lib._discount_codes_data import DISCOUNT_CODES, DISCOUNT_GROUPS

    index: Dict[str, List[Dict[str, Any]]] = {}

    def _add(heading: str, entry: Dict[str, Any]):
        if heading not in index:
            index[heading] = []
        key = (entry["item"], entry.get("sub_code"))
        for existing in index[heading]:
            if (existing["item"], existing.get("sub_code")) == key:
                return
        index[heading].append(entry)

    for item_num, item_data in DISCOUNT_CODES.items():
        group = item_data.get("group", 0)
        group_name = DISCOUNT_GROUPS.get(group, "")
        item_desc = item_data.get("description_he", "")
        conditional = item_data.get("conditional", False)

        # Extract headings from item-level description (all 6 layers)
        item_headings = _extract_headings_from_text(item_desc)
        item_headings |= _keyword_chapters_from_text(item_desc)

        sub_codes = item_data.get("sub_codes", {})

        if not sub_codes:
            # Item with no sub-codes
            base_entry = {
                "item": item_num,
                "sub_code": None,
                "group": group,
                "group_name": group_name,
                "description": item_desc,
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": conditional,
            }
            for h in item_headings:
                _add(h, base_entry)
        else:
            for sc_num, sc_data in sub_codes.items():
                sc_desc = sc_data.get("description_he", "")
                full_desc = f"{item_desc} \u2014 {sc_desc}" if sc_desc else item_desc

                entry = {
                    "item": item_num,
                    "sub_code": sc_num,
                    "group": group,
                    "group_name": group_name,
                    "description": full_desc,
                    "customs_duty": sc_data.get("customs_duty", ""),
                    "purchase_tax": sc_data.get("purchase_tax", ""),
                    "conditional": sc_data.get("conditional", False),
                }

                # 1. Explicit hs_codes
                sc_headings = set()
                for hs in sc_data.get("hs_codes", []):
                    sc_headings.add(_to_heading(hs))

                # 2-5. Regex layers from sub-code description
                sc_headings |= _extract_headings_from_text(sc_desc)

                # 6. Keyword matching on sub-code description
                sc_headings |= _keyword_chapters_from_text(sc_desc)

                # Inherit item-level headings if sub-code found none of its own
                if not sc_headings and item_headings:
                    sc_headings = set(item_headings)

                for h in sc_headings:
                    _add(h, entry)

    return index


# ---------------------------------------------------------------------------
#  Build FTA country info (lightweight — metadata only)
# ---------------------------------------------------------------------------

def _build_fta_index() -> Dict[str, Dict[str, Any]]:
    """Build FTA country preference map.

    Returns per-country metadata. For actual preferential rates per heading,
    use search_fta_full_text() from _fta_all_countries.py.
    """
    from lib._fta_all_countries import FTA_COUNTRIES

    fta_info: Dict[str, Dict[str, Any]] = {}
    for code, data in FTA_COUNTRIES.items():
        fta_info[code] = {
            "name_he": data.get("name_he", ""),
            "name_en": data.get("name_en", ""),
            "agreement_name": data.get("agreement_name_en", ""),
            "agreement_name_he": data.get("agreement_name_he", ""),
            "year": data.get("agreement_year"),
            "origin_proof": data.get("origin_proof", ""),
            "has_invoice_declaration": data.get("has_invoice_declaration", False),
            "has_approved_exporter": data.get("has_approved_exporter", False),
            "cumulation": data.get("cumulation", ""),
        }
    return fta_info


# ---------------------------------------------------------------------------
#  Lazy-loaded indexes
# ---------------------------------------------------------------------------

_DISCOUNT_INDEX: Optional[Dict[str, List[Dict[str, Any]]]] = None
_FTA_INFO: Optional[Dict[str, Dict[str, Any]]] = None


def _ensure_discount_index():
    global _DISCOUNT_INDEX
    if _DISCOUNT_INDEX is None:
        _DISCOUNT_INDEX = _build_discount_index()
    return _DISCOUNT_INDEX


def _ensure_fta_info():
    global _FTA_INFO
    if _FTA_INFO is None:
        _FTA_INFO = _build_fta_index()
    return _FTA_INFO


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

def get_discount_codes(hs_code: str) -> List[Dict[str, Any]]:
    """Get all applicable discount codes for an HS code or heading.

    Args:
        hs_code: Any format — '8711', '87.11', '8711300000', '87.11.3000',
                 '87.11.300000/9' (Israeli format). Uses librarian.normalize_hs_code().

    Returns:
        List of dicts with: item, sub_code, group, group_name, description,
        customs_duty, purchase_tax, conditional
    """
    idx = _ensure_discount_index()

    # Normalize to 10 raw digits, take first 4 as heading
    heading = normalize_hs_code(hs_code)[:4]

    results = list(idx.get(heading, []))

    # Also check chapter-level codes
    try:
        chapter = int(heading[:2])
    except ValueError:
        chapter = 0
    ch_key = f"ch{chapter:02d}"
    for entry in idx.get(ch_key, []):
        key = (entry["item"], entry.get("sub_code"))
        if not any((e["item"], e.get("sub_code")) == key for e in results):
            results.append(entry)

    return results


def get_fta_rates(hs_code: str) -> Dict[str, Dict[str, Any]]:
    """Get FTA agreement info for all countries.

    Args:
        hs_code: Any format (uses librarian.normalize_hs_code()).

    Returns:
        Dict of {country_code: {name_he, name_en, agreement_name, year,
        origin_proof, has_invoice_declaration, has_approved_exporter, cumulation}}.
    """
    return dict(_ensure_fta_info())


def get_discount_index_stats() -> Dict[str, Any]:
    """Return stats about the discount code index."""
    idx = _ensure_discount_index()
    total_entries = sum(len(v) for v in idx.values())
    headings_covered = sorted(k for k in idx if not k.startswith("ch"))
    chapters_covered = sorted(k for k in idx if k.startswith("ch"))

    # Compute section coverage
    sections_hit = set()
    for ch_key in chapters_covered:
        ch_num = int(ch_key[2:])
        for sec, (lo, hi) in _SECTION_CHAPTERS.items():
            if lo <= ch_num <= hi:
                sections_hit.add(sec)
                break
    for h in headings_covered:
        try:
            ch_num = int(h[:2])
            for sec, (lo, hi) in _SECTION_CHAPTERS.items():
                if lo <= ch_num <= hi:
                    sections_hit.add(sec)
                    break
        except ValueError:
            pass

    return {
        "total_headings": len(headings_covered),
        "total_chapter_refs": len(chapters_covered),
        "total_entries": total_entries,
        "sections_covered": len(sections_hit),
        "sections_total": 22,
        "headings": headings_covered,
        "chapters": chapters_covered,
    }
