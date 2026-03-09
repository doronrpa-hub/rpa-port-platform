# -*- coding: utf-8 -*-
"""HS reverse indexes — discount codes and FTA rates mapped to tariff headings.

Provides:
  get_discount_codes(hs_code) -> list of applicable discount code entries
  get_fta_rates(hs_code) -> dict of {country_code: {rate, origin_rule, ...}}

Built at import time by scanning:
  1. _discount_codes_data.py — regex extraction of HS references from descriptions
  2. _fta_all_countries.py — FTA agreement metadata per country (origin proof, agreement)

Author: Session 102 (2026-03-09)
"""

import re
from typing import Dict, List, Optional, Any


# ---------------------------------------------------------------------------
#  Regex patterns for extracting HS codes from Hebrew discount descriptions
# ---------------------------------------------------------------------------

# Matches patterns like: 87.11, 07.12.9010, 60.04.1000, 49.03, 51.06
_HS_DOTTED_RE = re.compile(r'\b(\d{2}\.\d{2}(?:\.\d{4,6})?)\b')

# Matches "בפרט XX.XX" / "בפרטים XX.XX" / "שבפרט XX.XX" / "שסיווגו בפרטים XX.XX"
# Also matches "בפרט משנה XXXX" (sub-heading reference within context of a heading)
_HS_CONTEXT_RE = re.compile(
    r'(?:שב|ב)פרט(?:ים|י)?\s+(?:משנה\s+)?(\d{2}\.\d{2}(?:\.\d{4,6})?)'
)

# Matches "פרק NN" for chapter-level references
_CHAPTER_RE = re.compile(r'לפרק\s+(\d{1,2})\b|פרק\s+(\d{1,2})\b')


def _normalize_heading(code_str: str) -> str:
    """Normalize a dotted HS code to a 4-digit heading.

    '87.11' -> '8711'
    '07.12.9010' -> '0712'
    '60.04.1000' -> '6004'
    '49.03' -> '4903'
    """
    digits = code_str.replace(".", "")
    return digits[:4].ljust(4, "0")


def _normalize_to_headings(code_str: str) -> List[str]:
    """Extract all 4-digit headings from a dotted HS code string.

    '87.11' -> ['8711']
    '51.12.1000, 54.07, 54.08, 55.12-55.16' would need separate regex matches.
    """
    return [_normalize_heading(code_str)]


# ---------------------------------------------------------------------------
#  Build discount code reverse index: heading -> discount entries
# ---------------------------------------------------------------------------

def _build_discount_index() -> Dict[str, List[Dict[str, Any]]]:
    """Build HS heading -> discount code entries map.

    Scans all discount codes for HS references in two places:
    1. Explicit hs_codes field (already populated on some entries)
    2. Hebrew descriptions mentioning HS headings via regex
    """
    from lib._discount_codes_data import DISCOUNT_CODES, DISCOUNT_GROUPS

    # heading_4digit -> list of {item, sub_code, description, customs_duty, purchase_tax, ...}
    index: Dict[str, List[Dict[str, Any]]] = {}

    def _add_entry(heading: str, entry: Dict[str, Any]):
        if heading not in index:
            index[heading] = []
        # Deduplicate by item+sub_code
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

        # Check item-level description for HS refs
        item_headings = set()
        for m in _HS_DOTTED_RE.finditer(item_desc):
            item_headings.add(_normalize_heading(m.group(1)))
        # Chapter-level refs -> expand to all headings in chapter
        for m in _CHAPTER_RE.finditer(item_desc):
            ch = m.group(1) or m.group(2)
            if ch:
                ch_num = int(ch)
                # Chapters map to heading ranges (e.g., ch87 = headings 8701-8716)
                # We store the chapter number for chapter-level discount codes
                item_headings.add(f"ch{ch_num:02d}")

        sub_codes = item_data.get("sub_codes", {})

        if not sub_codes:
            # Item with no sub-codes: use item-level data
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
                _add_entry(h, base_entry)
        else:
            # Process each sub-code
            for sc_num, sc_data in sub_codes.items():
                sc_desc = sc_data.get("description_he", "")
                full_desc = f"{item_desc} — {sc_desc}" if sc_desc else item_desc

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

                # 1. Explicit hs_codes on sub-code
                explicit_hs = sc_data.get("hs_codes", [])
                sc_headings = set()

                for hs in explicit_hs:
                    sc_headings.add(_normalize_heading(hs))

                # 2. Regex from sub-code description
                for m in _HS_DOTTED_RE.finditer(sc_desc):
                    sc_headings.add(_normalize_heading(m.group(1)))

                # 3. Inherit item-level headings if sub-code has none
                if not sc_headings and item_headings:
                    sc_headings = item_headings

                for h in sc_headings:
                    _add_entry(h, entry)

    return index


# ---------------------------------------------------------------------------
#  Build FTA country info per heading (lightweight — no full-text parsing)
# ---------------------------------------------------------------------------

def _build_fta_index() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Build FTA country preference map.

    Returns: {country_code: {origin_proof, agreement, year, ...}}

    Note: Extracting per-heading preferential rates from FTA full_text is not
    feasible — the tariff schedules are in inconsistent formats across 16
    countries (146 documents, 15.5M chars). Instead we provide:
    - Per-country FTA metadata (origin proof type, agreement details)
    - The lookup function accepts hs_code and returns which FTA countries
      have agreements that COULD apply (all 16), with origin proof requirements.

    For actual preferential rates, the broker must check the specific FTA
    document for the country in question — accessible via search_fta_full_text().
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
                 '87.11.300000/9' (Israeli format). Extracts 4-digit heading.

    Returns:
        List of dicts, each with:
          item, sub_code, group, group_name, description,
          customs_duty, purchase_tax, conditional
    """
    idx = _ensure_discount_index()

    # Normalize input to 4-digit heading
    raw = str(hs_code).replace(".", "").replace("/", "").replace(" ", "")
    # Strip check digit suffix (after /)
    if "/" in str(hs_code):
        raw = str(hs_code).split("/")[0].replace(".", "").replace(" ", "")
    heading = raw[:4].ljust(4, "0")

    results = list(idx.get(heading, []))

    # Also check chapter-level codes
    chapter = int(heading[:2])
    ch_key = f"ch{chapter:02d}"
    ch_results = idx.get(ch_key, [])
    for entry in ch_results:
        key = (entry["item"], entry.get("sub_code"))
        if not any((e["item"], e.get("sub_code")) == key for e in results):
            results.append(entry)

    return results


def get_fta_rates(hs_code: str) -> Dict[str, Dict[str, Any]]:
    """Get FTA agreement info for all countries that could apply to this HS code.

    Args:
        hs_code: Any format (see get_discount_codes).

    Returns:
        Dict of {country_code: {name_he, name_en, agreement_name, year,
        origin_proof, has_invoice_declaration, has_approved_exporter, cumulation}}.

    Note: For actual preferential duty rates, use search_fta_full_text() from
    _fta_all_countries.py with the specific HS code and country.
    """
    return dict(_ensure_fta_info())


def get_discount_index_stats() -> Dict[str, Any]:
    """Return stats about the discount code index."""
    idx = _ensure_discount_index()
    total_entries = sum(len(v) for v in idx.values())
    headings_covered = [k for k in idx if not k.startswith("ch")]
    chapters_covered = [k for k in idx if k.startswith("ch")]
    return {
        "total_headings": len(headings_covered),
        "total_chapter_refs": len(chapters_covered),
        "total_entries": total_entries,
        "headings": sorted(headings_covered),
        "chapters": sorted(chapters_covered),
    }
