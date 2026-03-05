"""
Direction Router -- Import/Export/Transit Detection
====================================================
Determines shipment direction BEFORE any data gathering or AI processing.
Routes to correct data sources: import tariff vs export tariff,
FIO vs FEO, valuation articles (import only), approved exporter (export only).

Usage:
    from lib.direction_router import detect_direction, get_direction_config
"""

import re

# -----------------------------------------------------------------------
#  DETECTION PATTERNS
# -----------------------------------------------------------------------

_IMPORT_KEYWORDS_HE = re.compile(
    r'(?:יבוא|ייבוא|מייבא|מייבאים|ליבא|יובא|מיובא|מיובאים|נכנס|'
    r'שחרור\s*מ?המכס|רשימון\s*יבוא|הצהרת\s*יבוא)',
    re.IGNORECASE,
)
_IMPORT_KEYWORDS_EN = re.compile(
    r'(?:import(?:ing|ed|s)?|inbound|clearance|release\s*from\s*customs|'
    r'import\s*declaration)',
    re.IGNORECASE,
)
_EXPORT_KEYWORDS_HE = re.compile(
    r'(?:יצוא|ייצוא|מייצא|מייצאים|לייצא|יוצא|מיוצא|מיוצאים|יוצאים|'
    r'יצואן\s*מאושר|רשימון\s*יצוא|הצהרת\s*יצוא|שטעון)',
    re.IGNORECASE,
)
_EXPORT_KEYWORDS_EN = re.compile(
    r'(?:export(?:ing|ed|s)?|outbound|export\s*declaration|approved\s*exporter)',
    re.IGNORECASE,
)
_TRANSIT_KEYWORDS = re.compile(
    r'(?:טרנזיט|מעבר|transit|transshipment|in\s*bond)',
    re.IGNORECASE,
)

# Incoterms that imply direction when paired with Israel location
_IMPORT_INCOTERMS = re.compile(
    r'(?:CIF|CFR|CIP|CPT|DAP|DDP|DDU|DPU)\s+(?:Israel|Haifa|Ashdod|'
    r'חיפה|אשדוד|ישראל|נתב"ג|ILHFA|ILASD|TLV)',
    re.IGNORECASE,
)
_EXPORT_INCOTERMS = re.compile(
    r'(?:FOB|FCA|FAS|EXW)\s+(?:Israel|Haifa|Ashdod|'
    r'חיפה|אשדוד|ישראל|נתב"ג|ILHFA|ILASD|TLV)',
    re.IGNORECASE,
)

# Israeli ports as POD (import) vs POL (export)
_POD_ISRAEL = re.compile(
    r'(?:POD|port\s*of\s*(?:discharge|destination)|נמל\s*(?:יעד|פריקה))\s*'
    r'[:=]?\s*(?:Haifa|Ashdod|חיפה|אשדוד|ILHFA|ILASD|Israel)',
    re.IGNORECASE,
)
_POL_ISRAEL = re.compile(
    r'(?:POL|port\s*of\s*(?:loading|origin)|נמל\s*(?:מוצא|טעינה|העמסה))\s*'
    r'[:=]?\s*(?:Haifa|Ashdod|חיפה|אשדוד|ILHFA|ILASD|Israel)',
    re.IGNORECASE,
)

# Regulatory decree mentions
_FIO_MENTION = re.compile(r'צו\s*יבוא\s*חופשי|free\s*import\s*order|FIO', re.IGNORECASE)
_FEO_MENTION = re.compile(r'צו\s*יצוא\s*חופשי|free\s*export\s*order|FEO', re.IGNORECASE)
_APPROVED_EXPORTER = re.compile(r'יצואן\s*מאושר|approved\s*exporter', re.IGNORECASE)


# -----------------------------------------------------------------------
#  DIRECTION DETECTION
# -----------------------------------------------------------------------

def detect_direction(subject, body, entities=None, deal_data=None):
    """Detect import/export/transit direction from email content.

    Args:
        subject: Email subject line
        body: Email body text
        entities: Optional dict with extracted entities (hs_codes, countries, etc.)
        deal_data: Optional dict from tracker_deals Firestore document

    Returns:
        dict with keys: direction, confidence, signals
        direction is one of: 'import', 'export', 'transit', 'unknown'
    """
    signals = []
    text = f"{subject or ''} {body or ''}"

    # 1. Deal data is authoritative (set by tracker or manual entry)
    if deal_data:
        deal_dir = (deal_data.get("direction") or "").lower().strip()
        if deal_dir in ("import", "export", "transit"):
            signals.append(("deal_data", deal_dir, 1.0))
            return _build_result(signals)

    # 2. Explicit keyword matching
    if _IMPORT_KEYWORDS_HE.search(text):
        signals.append(("keyword_he", "import", 0.85))
    if _IMPORT_KEYWORDS_EN.search(text):
        signals.append(("keyword_en", "import", 0.85))
    if _EXPORT_KEYWORDS_HE.search(text):
        signals.append(("keyword_he", "export", 0.85))
    if _EXPORT_KEYWORDS_EN.search(text):
        signals.append(("keyword_en", "export", 0.85))
    if _TRANSIT_KEYWORDS.search(text):
        signals.append(("keyword", "transit", 0.80))

    # 3. Incoterms with Israel location
    if _IMPORT_INCOTERMS.search(text):
        signals.append(("incoterm", "import", 0.80))
    if _EXPORT_INCOTERMS.search(text):
        signals.append(("incoterm", "export", 0.80))

    # 4. Port of loading/discharge
    if _POD_ISRAEL.search(text):
        signals.append(("pod_israel", "import", 0.80))
    if _POL_ISRAEL.search(text):
        signals.append(("pol_israel", "export", 0.80))

    # 5. Regulatory decree mentions
    if _FIO_MENTION.search(text):
        signals.append(("fio_mention", "import", 0.75))
    if _FEO_MENTION.search(text):
        signals.append(("feo_mention", "export", 0.75))
    if _APPROVED_EXPORTER.search(text):
        signals.append(("approved_exporter", "export", 0.80))

    return _build_result(signals)


def _build_result(signals):
    """Score signals and determine winning direction."""
    if not signals:
        return {"direction": "unknown", "confidence": 0.0, "signals": []}

    scores = {"import": 0.0, "export": 0.0, "transit": 0.0}
    for _name, direction, weight in signals:
        scores[direction] += weight

    best = max(scores, key=scores.get)
    best_score = scores[best]
    total = sum(scores.values())

    # Normalize confidence: proportion of total signal weight
    confidence = best_score / total if total > 0 else 0.0

    # If both import and export have similar scores, it's ambiguous
    runner_up = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0
    if best_score > 0 and runner_up > 0 and (runner_up / best_score) > 0.8:
        confidence *= 0.5  # Reduce confidence for ambiguous cases

    return {
        "direction": best if best_score > 0 else "unknown",
        "confidence": min(confidence, 1.0),
        "signals": [(n, d, w) for n, d, w in signals],
    }


# -----------------------------------------------------------------------
#  DIRECTION CONFIG
# -----------------------------------------------------------------------

# Data source routing per direction
_DIRECTION_CONFIGS = {
    "import": {
        "tariff_type": "import",
        "decree_collection": "free_import_order",
        "decree_name_he": "צו יבוא חופשי",
        "valuation_articles": [130, 131, 132, 133],
        "release_articles": [62, 63],
        "procedures": ["1", "2", "3"],
        "procedure_names": {
            "1": "תהליך השחרור (תש\"ר)",
            "2": "נוהל הערכה",
            "3": "נוהל סיווג טובין",
        },
        "check_approved_exporter": False,
        "fta_direction": "import",
    },
    "export": {
        "tariff_type": "export",
        "decree_collection": "free_export_order",
        "decree_name_he": "צו יצוא חופשי",
        "valuation_articles": [],  # No valuation for exports
        "release_articles": [],
        "procedures": ["approved_exporter"],
        "procedure_names": {
            "approved_exporter": "נוהל יצואן מאושר",
        },
        "check_approved_exporter": True,
        "fta_direction": "export",
    },
    "transit": {
        "tariff_type": "import",  # Transit still uses import tariff for classification
        "decree_collection": "free_import_order",
        "decree_name_he": "צו יבוא חופשי",
        "valuation_articles": [],
        "release_articles": [],
        "procedures": [],
        "procedure_names": {},
        "check_approved_exporter": False,
        "fta_direction": "transit",
    },
    "unknown": {
        "tariff_type": "import",  # Default to import (most common)
        "decree_collection": "free_import_order",
        "decree_name_he": "צו יבוא חופשי",
        "valuation_articles": [130, 131, 132, 133],
        "release_articles": [62, 63],
        "procedures": ["1", "2", "3"],
        "procedure_names": {
            "1": "תהליך השחרור (תש\"ר)",
            "2": "נוהל הערכה",
            "3": "נוהל סיווג טובין",
        },
        "check_approved_exporter": False,
        "fta_direction": "import",
    },
}


def get_direction_config(direction):
    """Get data source routing config for a direction.

    Args:
        direction: 'import', 'export', 'transit', or 'unknown'

    Returns:
        dict with tariff_type, decree_collection, valuation_articles, etc.
    """
    return _DIRECTION_CONFIGS.get(direction, _DIRECTION_CONFIGS["unknown"]).copy()
