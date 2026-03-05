"""Case Reasoning — Tiered Complexity Analyzer for Email Queries.

Sits between intent detection and evidence search. Analyzes the email
and produces a CasePlan that tells downstream pipeline what to search
for and how to structure results.

Usage:
    from lib.case_reasoning import analyze_case, CasePlan
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


# -----------------------------------------------------------------------
#  CASE PLAN DATA STRUCTURE
# -----------------------------------------------------------------------

@dataclass
class CasePlan:
    """What the downstream pipeline needs to know about this query."""

    case_type: str = "GENERAL"
    # SINGLE_CLASSIFICATION, MULTI_ITEM, LEGAL_STATUS, DISCOUNT_QUERY,
    # REGULATORY, VALUATION, GENERAL

    legal_category: str = ""
    # "", "toshav_chozer", "oleh_chadash", "diplomat", "tourist",
    # "student_chozer", "toshav_chutz", "crew"

    legal_category_he: str = ""
    # Hebrew display name

    tier: int = 1  # 1 = simple, 2 = moderate, 3 = complex

    direction: str = "import"  # import / export / unknown

    items_to_classify: list = field(default_factory=list)
    # Each: {name, keywords, category}

    origin_country: str = ""

    discount_group: str = ""  # "7" for incoming persons, "" for none

    discount_sub_range: str = ""
    # "1xxxxx" (tourist), "2xxxxx" (toshav chutz), "3xxxxx" (oleh),
    # "4xxxxx" (toshav chozer), "5xxxxx" (crew)

    special_flags: list = field(default_factory=list)
    # ["vehicle_separate", "food_contact", "hazmat"]

    per_item_required: bool = False
    # True = per-item table with regular + discount duty

    evidence_targets: list = field(default_factory=list)
    # Specific searches to run

    def to_dict(self) -> dict:
        return {
            "case_type": self.case_type,
            "legal_category": self.legal_category,
            "legal_category_he": self.legal_category_he,
            "tier": self.tier,
            "direction": self.direction,
            "items_to_classify": self.items_to_classify,
            "origin_country": self.origin_country,
            "discount_group": self.discount_group,
            "discount_sub_range": self.discount_sub_range,
            "special_flags": self.special_flags,
            "per_item_required": self.per_item_required,
            "evidence_targets": self.evidence_targets,
        }


# -----------------------------------------------------------------------
#  LEGAL CATEGORY DETECTION
# -----------------------------------------------------------------------

# Order matters — more specific patterns first
_LEGAL_PATTERNS = [
    # (compiled_regex, category_key, hebrew_label, discount_group, sub_range)
    (re.compile(r'תושב\s*חוזר', re.IGNORECASE), "toshav_chozer", "תושב חוזר", "7", "4xxxxx"),
    (re.compile(r'סטודנט\s*חוזר', re.IGNORECASE), "student_chozer", "סטודנט חוזר", "7", "4xxxxx"),
    (re.compile(r'עולה\s*חדש(?:ה)?', re.IGNORECASE), "oleh_chadash", "עולה חדש", "7", "3xxxxx"),
    # "עולה" without "חוזר" next to it — means oleh chadash
    (re.compile(r'(?<!\bתושב\s)(?<!\bסטודנט\s)עולה(?!\s*חוזר)', re.IGNORECASE),
     "oleh_chadash", "עולה חדש", "7", "3xxxxx"),
    (re.compile(r'דיפלומט|נציג\s*דיפלומטי|נציגות\s*מדינת\s*חוץ', re.IGNORECASE),
     "diplomat", "דיפלומט", "7", "2xxxxx"),
    (re.compile(r'תייר(?!ים\s*מהמערב)', re.IGNORECASE), "tourist", "תייר", "7", "1xxxxx"),
    (re.compile(r'תושב\s*חוץ', re.IGNORECASE), "toshav_chutz", "תושב חוץ", "7", "2xxxxx"),
    (re.compile(r'returning\s*resident', re.IGNORECASE), "toshav_chozer", "תושב חוזר", "7", "4xxxxx"),
    (re.compile(r'new\s*immigrant|oleh|olah', re.IGNORECASE),
     "oleh_chadash", "עולה חדש", "7", "3xxxxx"),
    # Temporary import — professional equipment, ATA Carnet, exhibitions
    (re.compile(r'יבוא\s*זמני|כניסה\s*זמנית|temporary\s*(?:import|admission)',
                re.IGNORECASE),
     "temporary_import", "יבוא זמני", "207", ""),
    (re.compile(r'קרנ[הת]\s*[אa]\.?[טt]\.?[אa]|ATA\s*Carnet|carnet',
                re.IGNORECASE),
     "temporary_import", "יבוא זמני — קרנה ATA", "207", ""),
]


def _detect_legal_category(text):
    """Detect legal category from text.

    Returns:
        (category_key, hebrew_label, discount_group, sub_range)
        or ("", "", "", "") if not detected.
    """
    for pattern, key, label_he, group, sub_range in _LEGAL_PATTERNS:
        if pattern.search(text):
            return key, label_he, group, sub_range
    return "", "", "", ""


# -----------------------------------------------------------------------
#  ITEM EXTRACTION
# -----------------------------------------------------------------------

# Item category patterns (Hebrew + English)
_ITEM_CATEGORIES = {
    "furniture": re.compile(
        r'ספה|ספות|כורסה|כורסאות|שולחן|שולחנות|כיסא|כיסאות|מיטה|מיטות|'
        r'ארון|ארונות|שידה|שידות|מדף|מדפים|ריהוט|רהיטים|'
        r'sofa|couch|table|chair|bed|wardrobe|closet|furniture|desk|shelf',
        re.IGNORECASE,
    ),
    "electronics": re.compile(
        r'טלוויזיה|טלויזיה|מסך|מסכי|מחשב|לפטופ|מקרר|מכונת\s*כביסה|מייבש|'
        r'מזגן|מדיח|תנור|מיקרוגל|שואב\s*אבק|'
        r'TV|television|monitor|computer|laptop|fridge|refrigerator|'
        r'washing\s*machine|dryer|air\s*condition|dishwasher|oven|microwave|vacuum',
        re.IGNORECASE,
    ),
    "vehicle": re.compile(
        r'רכב|מכונית|אוטו|אופנוע|קטנוע|'
        r'car|vehicle|motorcycle|scooter|automobile',
        re.IGNORECASE,
    ),
    "personal": re.compile(
        r'חפצים\s*אישיים|בגדים|הלבשה|נעליים|הנעלה|תכשיטים|אלבום|ספרים|'
        r'personal\s*(?:items|effects|belongings)|clothing|shoes|jewelry|books|albums',
        re.IGNORECASE,
    ),
    "kitchen": re.compile(
        r'כלי\s*מטבח|כלי\s*אוכל|סירים|מחבת|צלחות|כוסות|סכו\"ם|'
        r'kitchen\s*(?:utensils|ware)|pots|pans|plates|cups|cutlery',
        re.IGNORECASE,
    ),
    "food": re.compile(
        r'מזון|אוכל|food|groceries',
        re.IGNORECASE,
    ),
    "textiles": re.compile(
        r'מצעים|שמיכות|כריות|מגבות|וילונות|שטיח|שטיחים|'
        r'bedding|blankets|pillows|towels|curtains|carpet|rug',
        re.IGNORECASE,
    ),
    "music": re.compile(
        r'כלי\s*נגינה|פסנתר|גיטרה|כינור|'
        r'musical\s*instrument|piano|guitar|violin',
        re.IGNORECASE,
    ),
    "tools": re.compile(
        r'מקדח[הות]*|מברג[הות]*|מסור|מפתח\s*ברגים|ארגז[י]?\s*כלים|כלי\s*עבודה|'
        r'מכונ[הת]\s*(?:ל?הלחמה|ל?ריתוך|ל?ליטוש|ל?קידוח|ל?חיתוך|ל?השחזה)|מלחם|הלחמה|ריתוך|'
        r'drill|screwdriver|saw|wrench|toolbox|tool\s*(?:box|kit|set)|'
        r'welding\s*(?:machine|equipment)|grinder|sander|power\s*tool',
        re.IGNORECASE,
    ),
    "safety": re.compile(
        r'קסד[הות]*|כפפ[הות]*(?:\s*מגומי)?|משקפי\s*מגן|אוזניות\s*מגן|'
        r'נעלי\s*(?:בטיחות|מגן)|חגורת?\s*בטיחות|ביגוד\s*מגן|אפוד\s*מגן|'
        r'helmet|gloves|safety\s*(?:glasses|goggles|shoes|boots|vest|harness)|'
        r'(?:rubber|protective)\s*gloves|hard\s*hat|ear\s*(?:protection|muffs)',
        re.IGNORECASE,
    ),
    "workwear": re.compile(
        r'בגדי\s*עבודה|סרבל[ים]*|חולצת?\s*עבודה|מכנסי\s*עבודה|'
        r'work\s*(?:clothes|wear|uniform)|coverall|overalls|work\s*(?:shirt|pants)',
        re.IGNORECASE,
    ),
    "industrial": re.compile(
        r'מחולל|גנרטור|מדחס|קומפרסור|משאב[הת]|מנוף|עגורן|'
        r'מכונ[הת]\s*(?:תפירה|כביסה\s*תעשייתית|אריזה)|ציוד\s*(?:מקצועי|תעשייתי)|'
        r'generator|compressor|pump|crane|hoist|industrial\s*(?:equipment|machine)',
        re.IGNORECASE,
    ),
}


def _extract_items(text):
    """Extract product mentions from email body.

    Returns:
        list of dicts: [{name, keywords, category}]
    """
    items = []
    seen_categories = set()

    # Split by common separators (commas, "ו", newlines)
    # Look for item patterns with Hebrew connectors
    parts = re.split(r'[,\n]|\sו(?:גם|כן)?\s', text)

    for part in parts:
        part = part.strip()
        if not part or len(part) < 2:
            continue

        for category, pattern in _ITEM_CATEGORIES.items():
            match = pattern.search(part)
            if match:
                # Extract the matched item and surrounding context
                item_name = part.strip()
                if len(item_name) > 80:
                    # Try to get just the relevant phrase
                    start = max(0, match.start() - 20)
                    end = min(len(item_name), match.end() + 20)
                    item_name = item_name[start:end].strip()

                # Avoid duplicates of the same category from same sentence
                item_key = f"{category}:{match.group()[:20]}"
                if item_key not in seen_categories:
                    seen_categories.add(item_key)
                    items.append({
                        "name": item_name,
                        "keywords": [match.group()],
                        "category": category,
                    })
                break  # One category per part

    return items


# -----------------------------------------------------------------------
#  COMPLEXITY SCORING
# -----------------------------------------------------------------------

def _score_complexity(items, legal_category, special_flags):
    """Score case complexity to determine tier.

    Returns:
        int tier: 1 (simple), 2 (moderate), 3 (complex)
    """
    score = 0

    # Item count
    if len(items) > 3:
        score += 3
    elif len(items) > 1:
        score += 2
    elif len(items) == 1:
        score += 1

    # Legal category adds complexity
    if legal_category:
        score += 2

    # Special flags
    if "vehicle_separate" in special_flags:
        score += 3

    if score <= 1:
        return 1
    elif score <= 3:
        return 2
    else:
        return 3


# -----------------------------------------------------------------------
#  EVIDENCE TARGETS
# -----------------------------------------------------------------------

def _build_evidence_targets(plan):
    """Build list of specific evidence searches based on case plan."""
    targets = []

    # Legal status -> ordinance + discount codes
    if plan.legal_category == "temporary_import":
        targets.append("ordinance: section 162 (temporary admission)")
        targets.append("ordinance: section 85 (exhibition goods)")
        targets.append("ordinance: section 232 (regulation power — temporary admission)")
        targets.append("discount_code: item 207 (temporary import — goods to be re-exported)")
        targets.append("procedure: ATA Carnet (קרנה ATA) — temporary import of professional equipment")
        targets.append("procedure: 10 (personal import)")
    elif plan.legal_category:
        targets.append(f"ordinance: section 129 (entry-entitled persons)")
        targets.append(f"discount_code: item {plan.discount_group} sub {plan.discount_sub_range}")

    # Vehicle -> special procedure
    if "vehicle_separate" in plan.special_flags:
        if plan.legal_category in ("oleh_chadash",):
            targets.append("discount_code: item 7 sub 310000-313900 (oleh vehicle)")
        elif plan.legal_category in ("tourist",):
            targets.append("discount_code: item 7 sub 104000 (tourist vehicle)")
        targets.append("procedure: vehicle import")

    # Per-item tariff searches
    for item in plan.items_to_classify:
        targets.append(f"tariff_search: {' '.join(item.get('keywords', []))}")

    # Chapter 98 data (not for temporary import — uses discount 207 instead)
    if plan.legal_category and plan.legal_category != "temporary_import" and plan.items_to_classify:
        targets.append("chapter_98: personal import codes")

    return targets


# -----------------------------------------------------------------------
#  DISCOUNT CODE LOOKUP PER ITEM
# -----------------------------------------------------------------------

def get_discount_for_item(item_name, item_hs_code, legal_category, item_category=""):
    """For a single item, compute regular vs. Chapter 98 duty with discount codes.

    Args:
        item_name: e.g. "sofa"
        item_hs_code: e.g. "9401600000"
        legal_category: e.g. "toshav_chozer"
        item_category: e.g. "furniture"

    Returns:
        dict with regular_hs_code, chapter98_code, discount info, or empty dict
        if no chapter 98 mapping.
    """
    try:
        from lib._chapter98_data import get_chapter98_code, get_chapter98_entry
    except ImportError:
        try:
            from _chapter98_data import get_chapter98_code, get_chapter98_entry
        except ImportError:
            return {}

    if not legal_category:
        return {}

    # Temporary import uses discount code 207, not Chapter 98
    if legal_category == "temporary_import":
        try:
            from lib._discount_codes_data import get_discount_code
        except ImportError:
            try:
                from _discount_codes_data import get_discount_code
            except ImportError:
                get_discount_code = None

        if get_discount_code:
            item207 = get_discount_code("207")
            if item207:
                return {
                    "regular_hs_code": item_hs_code,
                    "discount_group": "207",
                    "discount_desc_he": item207.get("description_he", ""),
                    "sub_codes": {
                        sc_num: {
                            "desc_he": sc_data.get("description_he", ""),
                            "customs_duty": sc_data.get("customs_duty", ""),
                            "purchase_tax": sc_data.get("purchase_tax", ""),
                        }
                        for sc_num, sc_data in item207.get("sub_codes", {}).items()
                    },
                    "legal_basis": "סעיף 162 לפקודת המכס — כניסה זמנית",
                    "ata_carnet": True,
                }
        return {}

    ch98_code = get_chapter98_code(item_hs_code)
    if not ch98_code:
        return {}

    ch98_entry = get_chapter98_entry(ch98_code)
    if not ch98_entry:
        return {}

    # Map legal category to discount sub-code
    _CATEGORY_TO_SUB = {
        "toshav_chozer": {"personal": "403100", "tools": "403200", "household": "403400"},
        "student_chozer": {"personal": "403100", "tools": "403200", "household": "403400"},
        "oleh_chadash": {"personal": "300000", "tools": "301000", "household": "302000"},
        "tourist": {"personal": "100000", "tools": "101000"},
        "diplomat": {"personal": "190000"},
        "toshav_chutz": {"personal": "250000"},
    }

    sub_map = _CATEGORY_TO_SUB.get(legal_category, {})

    # Map item category to sub-code type
    _ITEM_TO_TYPE = {
        "furniture": "household",
        "electronics": "household",
        "kitchen": "household",
        "textiles": "household",
        "personal": "personal",
        "clothing": "personal",
        "footwear": "personal",
        "cosmetics": "personal",
        "music": "household",
        "food": "personal",
    }

    sub_type = _ITEM_TO_TYPE.get(item_category, "household")
    sub_code = sub_map.get(sub_type, sub_map.get("personal", ""))

    result = {
        "regular_hs_code": item_hs_code,
        "chapter98_code": ch98_code,
        "chapter98_desc_he": ch98_entry.get("desc_he", ""),
        "chapter98_desc_en": ch98_entry.get("desc_en", ""),
        "chapter98_duty": ch98_entry.get("duty", ""),
        "chapter98_pt": ch98_entry.get("purchase_tax", ""),
        "discount_group": "7",
        "discount_sub_code": sub_code,
    }

    # Enrich with actual discount description
    if sub_code:
        try:
            from lib._discount_codes_data import get_sub_code
        except ImportError:
            try:
                from _discount_codes_data import get_sub_code
            except ImportError:
                get_sub_code = None

        if get_sub_code:
            sc = get_sub_code("7", sub_code)
            if sc:
                result["discount_desc_he"] = sc.get("description_he", "")
                result["discount_duty"] = sc.get("customs_duty", "")
                result["discount_pt"] = sc.get("purchase_tax", "")

    return result


# -----------------------------------------------------------------------
#  MAIN ENTRY POINT
# -----------------------------------------------------------------------

def analyze_case(subject, body, entities=None, attachments=None):
    """Analyze email content and produce a CasePlan.

    Args:
        subject: Email subject line
        body: Email body text
        entities: Optional dict with extracted entities
        attachments: Optional list of attachment info

    Returns:
        CasePlan with case_type, legal_category, tier, items, etc.
    """
    text = f"{subject or ''} {body or ''}"
    entities = entities or {}

    plan = CasePlan()

    # 1. Detect legal category
    cat_key, cat_he, disc_group, disc_sub = _detect_legal_category(text)
    plan.legal_category = cat_key
    plan.legal_category_he = cat_he
    plan.discount_group = disc_group
    plan.discount_sub_range = disc_sub

    # 2. Extract items
    plan.items_to_classify = _extract_items(text)

    # 3. Detect special flags
    for item in plan.items_to_classify:
        if item.get("category") == "vehicle":
            if "vehicle_separate" not in plan.special_flags:
                plan.special_flags.append("vehicle_separate")

    # 4. Detect origin country from entities
    plan.origin_country = entities.get("origin_country", entities.get("country", ""))

    # 5. Determine case type
    if cat_key == "temporary_import":
        plan.case_type = "LEGAL_STATUS"
        plan.direction = "import"
        plan.per_item_required = True
        if "temporary_import" not in plan.special_flags:
            plan.special_flags.append("temporary_import")
    elif cat_key:
        plan.case_type = "LEGAL_STATUS"
        plan.direction = "import"  # Personal imports are always import
        plan.per_item_required = True
    elif len(plan.items_to_classify) > 1:
        plan.case_type = "MULTI_ITEM"
        plan.per_item_required = True
    elif len(plan.items_to_classify) == 1:
        plan.case_type = "SINGLE_CLASSIFICATION"
    else:
        # Check for discount/regulatory/valuation keywords
        if disc_group or any(kw in text.lower() for kw in ["קוד הנחה", "פטור", "discount", "exemption"]):
            plan.case_type = "DISCOUNT_QUERY"
        elif any(kw in text.lower() for kw in ["רגולציה", "תקן", "אישור", "regulatory", "standard"]):
            plan.case_type = "REGULATORY"
        elif any(kw in text.lower() for kw in ["ערך", "הערכה", "valuation", "customs value"]):
            plan.case_type = "VALUATION"

    # 6. Score complexity
    plan.tier = _score_complexity(plan.items_to_classify, cat_key, plan.special_flags)

    # 7. Build evidence targets
    plan.evidence_targets = _build_evidence_targets(plan)

    return plan
