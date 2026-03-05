"""Chapter 98/99 Israeli Special Tariff Codes — Personal Import Exemptions.

These chapters are Israeli-specific (not in the international HS nomenclature).
They cover personal imports by incoming persons (olim, returning residents,
tourists, diplomats) and special-purpose goods.

Key relationship chain:
  Regular HS code (94.01 furniture) -> Chapter 98 code (98.01.400000/8)
  -> Discount code (item 7, sub 403400) -> Final duty (exempt)

Source: shaarolami-query.customs.mof.gov.il, customsItemId=27202 (Ch.98),
        customsItemId=27137 (Ch.99).
"""

from typing import Optional, Dict, Any


# ---------------------------------------------------------------------------
#  CHAPTER 98: Personal use goods for entry-entitled persons
# ---------------------------------------------------------------------------

CHAPTER_98_HEADINGS: Dict[str, Dict[str, Any]] = {
    "9801": {
        "heading_he": "טובין לשימוש אישי של הנכנס לישראל - סעיף 129 לפקודת המכס",
        "heading_en": "Personal use goods imported by entry-entitled persons (s.129 Customs Ordinance)",
        "legal_basis": "section_129",
        "sub_items": {
            "9801100000": {
                "desc_he": "טקסטיל והלבשה שבגדר פרקים 60 עד 63",
                "desc_en": "Textiles and clothing (chapters 60-63)",
                "regular_chapters": [60, 61, 62, 63],
                "duty": "exempt",
                "purchase_tax": "exempt",
            },
            "9801200000": {
                "desc_he": "הנעלה שבגדר פרק 64",
                "desc_en": "Footwear (chapter 64)",
                "regular_chapters": [64],
                "duty": "exempt",
                "purchase_tax": "exempt",
            },
            "9801300000": {
                "desc_he": "מכשירי קוסמטיקה ותמרוקים",
                "desc_en": "Cosmetic devices and toiletries",
                "regular_chapters": [33, 96],
                "duty": "exempt",
                "purchase_tax": "exempt",
            },
            "9801400000": {
                "desc_he": "רהיטים שבגדר פרק 94",
                "desc_en": "Furniture (chapter 94)",
                "regular_chapters": [94],
                "duty": "exempt",
                "purchase_tax": "exempt",
            },
            "9801500000": {
                "desc_he": "כלי מטבח ואוכל",
                "desc_en": "Kitchen and dining utensils",
                "regular_chapters": [69, 70, 73, 82],
                "duty": "exempt",
                "purchase_tax": "exempt",
            },
            "9801600000": {
                "desc_he": "תכשיטים ומוצרי זהב",
                "desc_en": "Jewelry and gold items",
                "regular_chapters": [71],
                "duty": "exempt",
                "purchase_tax": "exempt",
            },
            "9801700000": {
                "desc_he": "כלי נגינה",
                "desc_en": "Musical instruments",
                "regular_chapters": [92],
                "duty": "exempt",
                "purchase_tax": "exempt",
            },
            "9801800000": {
                "desc_he": "מזון ממינים שונים עד 15 ק\"ג",
                "desc_en": "Mixed food items up to 15 kg",
                "regular_chapters": list(range(1, 25)),
                "duty": "exempt",
                "purchase_tax": "exempt",
            },
            "9801900000": {
                "desc_he": "טובין אחרים לשימוש אישי",
                "desc_en": "Other personal use goods",
                "regular_chapters": [],
                "duty": "exempt",
                "purchase_tax": "exempt",
            },
        },
    },
    "9802": {
        "heading_he": "חבילות מתנה ושימוש אישי עד 130 דולר",
        "heading_en": "Gift packages and personal use up to $130",
        "legal_basis": "section_129",
        "sub_items": {
            "9802100000": {
                "desc_he": "חבילות מתנה שערכן אינו עולה על 130 דולר",
                "desc_en": "Gift packages valued up to $130",
                "regular_chapters": [],
                "duty": "exempt",
                "purchase_tax": "exempt",
            },
        },
    },
    "9803": {
        "heading_he": "טובין לשימוש אישי עד 500 דולר",
        "heading_en": "Personal use goods up to $500",
        "legal_basis": "section_129",
        "sub_items": {
            "9803100000": {
                "desc_he": "טובין לשימוש אישי שערכם הכולל אינו עולה על 500 דולר",
                "desc_en": "Personal goods valued up to $500",
                "regular_chapters": [],
                "duty": "exempt",
                "purchase_tax": "exempt",
            },
            "9803200000": {
                "desc_he": "חלקי חילוף לרכב מנועי",
                "desc_en": "Vehicle spare parts",
                "regular_chapters": [87],
                "duty": "exempt",
                "purchase_tax": "exempt",
            },
        },
    },
}


# ---------------------------------------------------------------------------
#  CHAPTER 99: Special purpose goods
# ---------------------------------------------------------------------------

CHAPTER_99_HEADINGS: Dict[str, Dict[str, Any]] = {
    "9901": {
        "heading_he": "טובין לסיוע באסון",
        "heading_en": "Disaster relief goods",
        "legal_basis": "special_order",
        "sub_items": {
            "9901100000": {
                "desc_he": "טובין שיובאו לשם סיוע בשעת אסון",
                "desc_en": "Goods imported for disaster relief",
                "regular_chapters": [],
                "duty": "exempt",
                "purchase_tax": "exempt",
            },
        },
    },
    "9902": {
        "heading_he": "ארונות קבורה עם גופות",
        "heading_en": "Coffins containing remains",
        "legal_basis": "special_order",
        "sub_items": {
            "9902100000": {
                "desc_he": "ארונות קבורה המכילים גופות נפטרים",
                "desc_en": "Coffins containing remains of the deceased",
                "regular_chapters": [],
                "duty": "exempt",
                "purchase_tax": "exempt",
            },
        },
    },
}


# ---------------------------------------------------------------------------
#  MAPPING: regular chapter -> Chapter 98 code (for personal imports)
# ---------------------------------------------------------------------------

CHAPTER_TO_98_MAP: Dict[int, str] = {}

# Build from sub_items automatically
for _heading_code, _heading_data in CHAPTER_98_HEADINGS.items():
    for _sub_code, _sub_data in _heading_data.get("sub_items", {}).items():
        for _ch in _sub_data.get("regular_chapters", []):
            # First mapping wins (more specific heading)
            if _ch not in CHAPTER_TO_98_MAP:
                CHAPTER_TO_98_MAP[_ch] = _sub_code


# ---------------------------------------------------------------------------
#  ITEM CATEGORY -> CHAPTER 98 CODE (for case_reasoning)
# ---------------------------------------------------------------------------

_ITEM_CATEGORY_TO_98: Dict[str, str] = {
    "textiles": "9801100000",
    "clothing": "9801100000",
    "footwear": "9801200000",
    "cosmetics": "9801300000",
    "furniture": "9801400000",
    "kitchen": "9801500000",
    "jewelry": "9801600000",
    "music": "9801700000",
    "food": "9801800000",
    "personal": "9801900000",
}

# Vehicle is NOT in Chapter 98 — uses discount code item 7 directly (sub 310000+)
# Electronics use 9801900000 (other personal) or regular tariff depending on value


# ---------------------------------------------------------------------------
#  HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def get_chapter98_code(regular_hs_code: str) -> Optional[str]:
    """Map a regular HS code to its Chapter 98 equivalent for personal imports.

    Args:
        regular_hs_code: e.g. "9401600000" or "94.01.600000"

    Returns:
        Chapter 98 code string (e.g. "9801400000") or None if no mapping exists.
    """
    clean = str(regular_hs_code).replace(".", "").replace("/", "").replace(" ", "")
    if len(clean) < 2:
        return None
    try:
        chapter = int(clean[:2])
    except ValueError:
        return None
    return CHAPTER_TO_98_MAP.get(chapter)


def get_chapter98_entry(code: str) -> Optional[Dict[str, Any]]:
    """Get full entry for a Chapter 98/99 code.

    Args:
        code: e.g. "9801400000" or "98.01.400000"

    Returns:
        dict with desc_he, desc_en, duty, purchase_tax, regular_chapters, heading info
        or None if not found.
    """
    clean = str(code).replace(".", "").replace("/", "").replace(" ", "")[:10]

    # Check Chapter 98
    for heading_code, heading_data in CHAPTER_98_HEADINGS.items():
        for sub_code, sub_data in heading_data.get("sub_items", {}).items():
            if sub_code == clean:
                return {
                    **sub_data,
                    "heading_code": heading_code,
                    "heading_he": heading_data["heading_he"],
                    "heading_en": heading_data["heading_en"],
                    "legal_basis": heading_data["legal_basis"],
                }

    # Check Chapter 99
    for heading_code, heading_data in CHAPTER_99_HEADINGS.items():
        for sub_code, sub_data in heading_data.get("sub_items", {}).items():
            if sub_code == clean:
                return {
                    **sub_data,
                    "heading_code": heading_code,
                    "heading_he": heading_data["heading_he"],
                    "heading_en": heading_data["heading_en"],
                    "legal_basis": heading_data["legal_basis"],
                }

    return None


def get_chapter98_by_category(category: str) -> Optional[str]:
    """Map an item category to its Chapter 98 code.

    Args:
        category: e.g. "furniture", "clothing", "electronics"

    Returns:
        Chapter 98 code string or None.
    """
    return _ITEM_CATEGORY_TO_98.get(category.lower())


def search_chapter98(query: str) -> list:
    """Search Chapter 98/99 codes by keyword.

    Returns:
        list of (code, desc_he, desc_en) tuples matching the query.
    """
    query_lower = query.lower()
    results = []

    for heading_data in list(CHAPTER_98_HEADINGS.values()) + list(CHAPTER_99_HEADINGS.values()):
        for sub_code, sub_data in heading_data.get("sub_items", {}).items():
            if (query_lower in sub_data.get("desc_he", "").lower()
                    or query_lower in sub_data.get("desc_en", "").lower()):
                results.append((sub_code, sub_data["desc_he"], sub_data["desc_en"]))

    return results
