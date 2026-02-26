"""
Context Engine — System Intelligence First (SIF)
=================================================
Searches tariff, ordinance, XML documents, regulatory info, framework order,
and cached answers BEFORE any AI model sees the question.

Session 77: Tool Router — routes questions to ALL available tools (34+) instead
of a hardcoded sequence of 5-7 searches. Uses keyword/domain/entity matching
to decide which tools are relevant, then executes them.

The AI models receive a pre-assembled context package and their ONLY job
is to synthesize a professional Hebrew answer from that context.

Usage:
    from lib.context_engine import prepare_context_package, ContextPackage
"""

import json
import re
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════
#  CONTEXT PACKAGE
# ═══════════════════════════════════════════

@dataclass
class ContextPackage:
    original_subject: str
    original_body: str
    detected_language: str          # "he" / "en" / "mixed"
    entities: dict = field(default_factory=dict)
    domain: str = "general"         # tariff / ordinance / fta / regulatory / logistics / general
    all_domains: list = field(default_factory=list)
    tariff_results: list = field(default_factory=list)
    ordinance_articles: list = field(default_factory=list)
    xml_results: list = field(default_factory=list)
    regulatory_results: list = field(default_factory=list)
    framework_articles: list = field(default_factory=list)
    wikipedia_results: list = field(default_factory=list)
    logistics_results: list = field(default_factory=list)
    shipment_results: list = field(default_factory=list)
    other_tool_results: list = field(default_factory=list)
    cached_answer: Optional[dict] = None
    context_summary: str = ""
    confidence: float = 0.0
    search_log: list = field(default_factory=list)


# ═══════════════════════════════════════════
#  ENTITY EXTRACTION PATTERNS
# ═══════════════════════════════════════════

_HS_CODE_RE = re.compile(r'\b(\d{4}[.\s]?\d{2}[.\s]?\d{2,4})\b')
_CONTAINER_RE = re.compile(r'\b([A-Z]{3}U\d{7})\b')
_BL_RE = re.compile(r'(?:B/?L|BOL|שטר)[:\s#]*([A-Z0-9][\w\-]{6,25})', re.IGNORECASE)
_BL_MSC_RE = re.compile(r'\b(MEDURS\d{5,10})\b')
_ARTICLE_RE = re.compile(r'(?:סעיף|article|§)\s*(\d{1,3}[אבגדהוזחטייכלמנסעפצקרשת]*)', re.IGNORECASE)

_PRODUCT_NAME_PATTERNS = [
    re.compile(r'(?:פרט\s*(?:ה?מכס|מכסי)\s*(?:ל|של|על)\s*)(.{3,80}?)(?:\?|$|\.)', re.IGNORECASE),
    re.compile(r'(?:סיווג\s+(?:של|ל)?\s*)(.{3,80}?)(?:\?|$|\.)', re.IGNORECASE),
    re.compile(r'(?:classification\s+(?:of|for)\s+)(.{3,80}?)(?:\?|$|\.)', re.IGNORECASE),
    re.compile(r'(?:hs\s*code\s*(?:for|of)\s+)(.{3,80}?)(?:\?|$|\.)', re.IGNORECASE),
    re.compile(r'(?:מה\s*(?:ה?סיווג|ה?מכס|ה?תעריף)\s*(?:של|ל|על)\s*)(.{3,80}?)(?:\?|$|\.)', re.IGNORECASE),
]

# Location extraction
_PORT_NAMES_MAP = {
    'אשדוד': 'ILASD', 'ashdod': 'ILASD',
    'חיפה': 'ILHFA', 'haifa': 'ILHFA',
    'אילת': 'ILELT', 'eilat': 'ILELT',
    'בן גוריון': 'LLBG', 'ben gurion': 'LLBG',
    'נתב"ג': 'LLBG', 'נתבג': 'LLBG',
}

_LOCATION_RE = re.compile(
    r'(?:נמל|port|מ|ל|ב)?\s*'
    r'(אשדוד|חיפה|אילת|בן\s*גוריון|נתב"ג|נתבג|'
    r'ashdod|haifa|eilat|ben\s*gurion)',
    re.IGNORECASE
)
_PLACE_RE = re.compile(
    r'(?:מ|ל|ב)?(?:קיבוץ|מושב|עיר|ישוב|יישוב)\s+([\u0590-\u05FF]{2,20})',
    re.IGNORECASE
)
_ADDRESS_RE = re.compile(
    r'(?:מ|ל|ב)?([\u0590-\u05FF]{2,20})\s+(?:ל|אל)\s+(?:נמל\s+)?([\u0590-\u05FF]{2,20})',
    re.IGNORECASE
)

# Deadline/time extraction
_DEADLINE_RE = re.compile(r'עד\s+(?:ה?שעה\s+)?(\d{1,2}[:.]\d{2})', re.IGNORECASE)
_DEADLINE_EN_RE = re.compile(r'(?:until|by|before)\s+(\d{1,2}[:.]\d{2})', re.IGNORECASE)

# Currency/amount extraction
_AMOUNT_RE = re.compile(
    r'(\d[\d,]*\.?\d*)\s*(?:₪|ש"ח|שקל|NIS|ILS|\$|USD|€|EUR|£|GBP|¥|JPY|CNY)',
    re.IGNORECASE
)
_AMOUNT_PREFIX_RE = re.compile(
    r'(?:₪|שקל|\$|€|£)\s*(\d[\d,]*\.?\d*)',
    re.IGNORECASE
)

# Customs-relevant keywords for extraction
_CUSTOMS_KEYWORDS_HE = {
    'מכס', 'תעריף', 'סיווג', 'יבוא', 'יצוא', 'פטור', 'הערכה', 'ערך',
    'שחרור', 'רשימון', 'מצהר', 'הסכם', 'מקור', 'קניין', 'עיכוב', 'חילוט',
    'קנס', 'הברחה', 'רישיון', 'תקן', 'נוהל', 'אישור', 'מכסה', 'החסנה',
    'פקודה', 'צו', 'תוספת', 'הנחה', 'מותנה', 'עמיל',
}

_CUSTOMS_KEYWORDS_EN = {
    'customs', 'tariff', 'classification', 'import', 'export', 'duty',
    'valuation', 'origin', 'fta', 'clearance', 'declaration', 'warehouse',
    'ordinance', 'penalty', 'forfeiture', 'license', 'permit',
}


# ═══════════════════════════════════════════
#  TOOL ROUTING MAP
# ═══════════════════════════════════════════

# Every tool in tool_executors.py MUST be mapped here.
# Keys: tool_name (as registered in ToolExecutor.execute dispatcher)
# Values: routing config dict
#   triggers: keywords/phrases in the question text that suggest this tool
#   domains: which detected domain(s) this tool serves
#   entity_types: which entity types feed into this tool
#   always_run: run whenever relevant entities are present (free/fast tools)
#   fallback: only run if primary tools found sparse data
#   needs_db: requires Firestore (skip when db=None)
#   param_builder: name of function to build params (default: auto)
#   skip_in_sif: True for tools that are classification-only, not consultation

TOOL_ROUTING_MAP = {
    # ── Tariff & Classification (core, always-run) ──
    "search_tariff": {
        "triggers": ["פרט מכס", "פריט", "hs code", "סיווג", "תעריף", "tariff",
                      "classification", "מכס על", "duty rate"],
        "domains": ["tariff", "general"],
        "entity_types": ["hs_codes", "product_names"],
        "always_run": True,
        "needs_db": True,
    },
    "check_regulatory": {
        "triggers": ["צו יבוא", "רישיון", "אישור", "היתר", "restricted", "import order",
                      "ISI", "תקן", "מת\"י", "רגולטורי", "רגולציה", "permit",
                      "standard", "approval", "license"],
        "domains": ["regulatory", "tariff"],
        "entity_types": ["hs_codes", "product_names"],
        "needs_db": True,
    },
    "verify_hs_code": {
        "triggers": ["אימות", "verify", "valid", "תקף"],
        "domains": ["tariff"],
        "entity_types": ["hs_codes"],
        "needs_db": True,
    },
    "get_chapter_notes": {
        "triggers": ["הערות לפרק", "chapter notes", "כלל פרשנות", "פרק"],
        "domains": ["tariff"],
        "entity_types": ["hs_codes"],
        "needs_db": True,
    },
    "lookup_tariff_structure": {
        "triggers": ["חלק", "section", "פרקים", "chapters", "מבנה התעריף",
                      "tariff structure"],
        "domains": ["tariff"],
        "entity_types": ["hs_codes"],
        "needs_db": True,
    },
    "search_xml_documents": {
        "triggers": ["רפורמ", "eu reform", "ce marking", "עץ מוצר", "הוראות",
                      "נוהל", "חוזר", "procedure", "guideline", "סימון ce",
                      "דירקטיבה", "תקנים אירופיים"],
        "domains": ["regulatory", "reform", "general"],
        "entity_types": ["keywords"],
        "always_run": True,
        "needs_db": True,
    },

    # ── Legal & Knowledge ──
    "search_legal_knowledge": {
        "triggers": ["פקודת המכס", "חוק", "סעיף", "ordinance", "law", "legal",
                      "חשבון מכר", "חשבונית", "invoice requirements",
                      "עונש", "קנס", "penalty", "הברחה", "smuggling",
                      "עמיל מכס", "customs agent", "broker"],
        "domains": ["ordinance", "general"],
        "entity_types": ["article_numbers", "keywords"],
        "needs_db": True,
    },
    "lookup_framework_order": {
        "triggers": ["צו מסגרת", "framework order", "הסכם סחר", "תוספת ראשונה",
                      "תוספת שנייה", "הגדרה"],
        "domains": ["fta", "tariff"],
        "entity_types": ["keywords"],
        "needs_db": True,
    },
    "lookup_fta": {
        "triggers": ["הסכם סחר", "fta", "כללי מקור", "תעודת מקור", "העדפה",
                      "preferential", "origin", "eur.1", "free trade"],
        "domains": ["fta"],
        "entity_types": ["hs_codes"],
        "needs_db": True,
    },
    "search_classification_directives": {
        "triggers": ["הנחיית סיווג", "classification directive", "הנחייה",
                      "directive"],
        "domains": ["tariff"],
        "entity_types": ["hs_codes", "keywords"],
        "needs_db": True,
    },

    # ── Distance & Logistics ──
    "calculate_route_eta": {
        "triggers": ["מרחק", "זמן נסיעה", "הובלה", "מכולה ריקה", "נמל",
                      "משאית", "truck", "container", "port", "distance",
                      "route", "pickup", "delivery", "איסוף", "העמסה",
                      "פריקה", "סגירת מכולות", "gate cutoff", "כמה זמן לוקח",
                      "כמה זמן", "driving time", "נסיעה מ", "נסיעה ל",
                      "אשדוד", "חיפה", "אילת", "בן גוריון",
                      "ashdod", "haifa", "eilat"],
        "domains": ["logistics"],
        "entity_types": ["locations"],
        "needs_db": True,
    },

    # ── Shipment & Tracking ──
    "check_shipment_status": {
        "triggers": ["מעקב", "tracking", "container status", "סטטוס משלוח",
                      "איפה המשלוח", "הגעה", "אנייה", "vessel", "eta", "etd",
                      "משלוח", "shipment status"],
        "domains": ["shipment", "logistics"],
        "entity_types": ["container_numbers", "bl_numbers"],
        "needs_db": True,
    },
    "get_port_schedule": {
        "triggers": ["לוח זמנים", "schedule", "אניות", "vessels", "כניסת אניות",
                      "port schedule", "לוח הפלגות", "vessel schedule"],
        "domains": ["logistics", "shipment"],
        "entity_types": ["locations"],
        "needs_db": True,
    },

    # ── Currency & Finance ──
    "bank_of_israel_rates": {
        "triggers": ["שער חליפין", "exchange rate", "שער דולר", "שער יורו",
                      "שער", "rate", "המרה", "convert", "בנק ישראל",
                      "boi rate"],
        "domains": ["tariff", "general"],
        "entity_types": ["amounts"],
        "needs_db": True,
    },
    "convert_currency": {
        "triggers": ["המרה", "convert", "exchange", "מטבע", "currency"],
        "domains": ["general"],
        "entity_types": ["amounts"],
        "needs_db": True,
    },
    "get_israel_vat_rates": {
        "triggers": ["מע\"מ", "מעמ", "vat", "מס קניה", "purchase tax",
                      "tax rate", "שיעור מס"],
        "domains": ["tariff", "regulatory", "general"],
        "entity_types": [],
        "needs_db": True,
    },

    # ── Country & Trade ──
    "lookup_country": {
        "triggers": ["מדינה", "country", "ארץ מקור", "origin country"],
        "domains": ["fta", "general"],
        "entity_types": [],
        "needs_db": True,
    },
    "lookup_unctad_gsp": {
        "triggers": ["gsp", "העדפה כללית", "generalized system", "developing",
                      "מדינה מתפתחת"],
        "domains": ["fta"],
        "entity_types": [],
        "needs_db": True,
    },

    # ── Product Knowledge (external APIs) ──
    "search_wikipedia": {
        "triggers": [],
        "domains": ["general"],
        "entity_types": ["keywords"],
        "fallback": True,
        "needs_db": True,
    },
    "search_wikidata": {
        "triggers": ["חומר", "material", "הרכב", "composition", "cas number",
                      "formula", "נוסחה כימית"],
        "domains": ["tariff", "general"],
        "entity_types": ["product_names"],
        "needs_db": True,
    },
    "search_pubchem": {
        "triggers": ["כימי", "chemical", "חומצה", "acid", "תרכובת", "compound",
                      "polymer", "פולימר", "resin", "שרף", "oxide", "chloride"],
        "domains": ["tariff"],
        "entity_types": ["product_names"],
        "needs_db": True,
    },
    "lookup_food_product": {
        "triggers": ["מזון", "food", "אוכל", "מאכל", "שוקולד", "chocolate",
                      "ממתק", "candy", "שתייה", "drink", "beverage",
                      "תבלין", "spice", "שמן", "oil", "חלב", "milk"],
        "domains": ["tariff"],
        "entity_types": ["product_names"],
        "needs_db": True,
    },
    "search_open_beauty": {
        "triggers": ["קוסמטיקה", "cosmetic", "קרם", "cream", "שמפו", "shampoo",
                      "בושם", "perfume", "סבון", "soap", "לושן", "lotion"],
        "domains": ["tariff"],
        "entity_types": ["product_names"],
        "needs_db": True,
    },
    "check_fda_product": {
        "triggers": ["fda", "רפואי", "medical", "תרופה", "drug", "device",
                      "510k", "מכשיר רפואי"],
        "domains": ["tariff", "regulatory"],
        "entity_types": ["product_names"],
        "needs_db": True,
    },
    "search_wco_notes": {
        "triggers": ["wco", "explanatory notes", "הערות פרשניות", "world customs"],
        "domains": ["tariff"],
        "entity_types": ["hs_codes", "keywords"],
        "needs_db": True,
    },
    "lookup_eu_taric": {
        "triggers": ["taric", "eu tariff", "תעריף אירופי", "european tariff"],
        "domains": ["tariff", "fta"],
        "entity_types": ["hs_codes"],
        "needs_db": True,
    },
    "lookup_usitc": {
        "triggers": ["usitc", "hts", "us tariff", "תעריף אמריקאי"],
        "domains": ["tariff", "fta"],
        "entity_types": ["hs_codes"],
        "needs_db": True,
    },

    # ── Sanctions & Compliance ──
    "check_opensanctions": {
        "triggers": ["סנקציות", "sanctions", "חרם", "embargo", "blacklist",
                      "רשימה שחורה"],
        "domains": ["regulatory", "general"],
        "entity_types": ["keywords"],
        "needs_db": True,
    },

    # ── Barcodes ──
    "lookup_gs1_barcode": {
        "triggers": ["barcode", "ברקוד", "gs1", "ean", "upc"],
        "domains": ["tariff"],
        "entity_types": ["product_names"],
        "needs_db": True,
    },

    # ── Classification-only tools (skip in SIF consultation) ──
    "check_memory": {
        "triggers": [],
        "domains": [],
        "entity_types": [],
        "skip_in_sif": True,
    },
    "extract_invoice": {
        "triggers": [],
        "domains": [],
        "entity_types": [],
        "skip_in_sif": True,
    },
    "assess_risk": {
        "triggers": [],
        "domains": [],
        "entity_types": [],
        "skip_in_sif": True,
    },
    "run_elimination": {
        "triggers": [],
        "domains": [],
        "entity_types": [],
        "skip_in_sif": True,
    },
    "fetch_seller_website": {
        "triggers": [],
        "domains": [],
        "entity_types": [],
        "skip_in_sif": True,
    },
    "search_comtrade": {
        "triggers": [],
        "domains": [],
        "entity_types": [],
        "skip_in_sif": True,  # overnight only
    },
    "israel_cbs_trade": {
        "triggers": [],
        "domains": [],
        "entity_types": [],
        "skip_in_sif": True,  # overnight only
    },
    "crossref_technical": {
        "triggers": [],
        "domains": [],
        "entity_types": [],
        "skip_in_sif": True,  # overnight only
    },
}


# ═══════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════

def _detect_language(subject, body):
    """Detect language by Hebrew character ratio."""
    text = f"{subject} {body}"
    if not text.strip():
        return "he"
    hebrew_chars = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
    total_alpha = sum(1 for c in text if c.isalpha()) or 1
    ratio = hebrew_chars / total_alpha
    if ratio > 0.3:
        return "he"
    if ratio < 0.1:
        return "en"
    return "mixed"


def _extract_entities(subject, body):
    """Extract HS codes, product names, containers, BL numbers, articles,
    keywords, locations, amounts, deadlines."""
    combined = f"{subject} {body}"
    entities = {
        "hs_codes": [],
        "product_names": [],
        "container_numbers": [],
        "bl_numbers": [],
        "article_numbers": [],
        "keywords": [],
        "locations": [],
        "amounts": [],
        "deadlines": [],
    }

    # HS codes
    for m in _HS_CODE_RE.finditer(combined):
        code = re.sub(r'[\s.]', '', m.group(1))
        if code not in entities["hs_codes"]:
            entities["hs_codes"].append(code)

    # Container numbers
    for m in _CONTAINER_RE.finditer(combined):
        entities["container_numbers"].append(m.group(1))

    # BL numbers
    for pat in [_BL_RE, _BL_MSC_RE]:
        for m in pat.finditer(combined):
            val = m.group(1) if pat.groups else m.group(0)
            if val not in entities["bl_numbers"]:
                entities["bl_numbers"].append(val)

    # Article numbers
    for m in _ARTICLE_RE.finditer(combined):
        art = m.group(1)
        if art not in entities["article_numbers"]:
            entities["article_numbers"].append(art)

    # Product names
    for pat in _PRODUCT_NAME_PATTERNS:
        m = pat.search(combined)
        if m:
            name = m.group(1).strip().rstrip('?.,! ')
            if name and len(name) > 2:
                entities["product_names"].append(name)
                break

    # Keywords
    for word in re.findall(r'[\u0590-\u05FF]{3,}', combined):
        if word in _CUSTOMS_KEYWORDS_HE and word not in entities["keywords"]:
            entities["keywords"].append(word)
    for word in re.findall(r'[a-zA-Z]{4,}', combined.lower()):
        if word in _CUSTOMS_KEYWORDS_EN and word not in entities["keywords"]:
            entities["keywords"].append(word)

    # Locations (ports, places, addresses)
    combined_lower = combined.lower()
    seen_locs = set()
    for m in _LOCATION_RE.finditer(combined):
        loc = m.group(1).strip()
        loc_lower = loc.lower()
        port_code = None
        for name, code in _PORT_NAMES_MAP.items():
            if name in loc_lower:
                port_code = code
                break
        entry = loc if not port_code else f"{loc} ({port_code})"
        if entry not in seen_locs:
            entities["locations"].append(entry)
            seen_locs.add(entry)
    for m in _PLACE_RE.finditer(combined):
        place = m.group(1).strip()
        if place not in seen_locs:
            entities["locations"].append(place)
            seen_locs.add(place)
    # Also extract place names from "from X to Y" patterns
    for m in _ADDRESS_RE.finditer(combined):
        for g in [m.group(1), m.group(2)]:
            g = g.strip()
            if g and g not in seen_locs and len(g) >= 2:
                entities["locations"].append(g)
                seen_locs.add(g)

    # Deadlines
    for pat in [_DEADLINE_RE, _DEADLINE_EN_RE]:
        for m in pat.finditer(combined):
            entities["deadlines"].append(m.group(1))

    # Amounts
    for pat in [_AMOUNT_RE, _AMOUNT_PREFIX_RE]:
        for m in pat.finditer(combined):
            entities["amounts"].append(m.group(1).replace(',', ''))

    return entities


def _detect_domain(entities, subject, body):
    """Detect primary domain from entities and text."""
    combined = f"{subject} {body}".lower()

    if entities.get("hs_codes"):
        return "tariff"

    # Product classification question patterns
    if any(p in combined for p in ['פרט מכס', 'סיווג', 'hs code', 'classification', 'תעריף']):
        return "tariff"

    if entities.get("article_numbers"):
        return "ordinance"
    if any(p in combined for p in ['פקודת המכס', 'פקודה', 'ordinance', 'סעיף']):
        return "ordinance"

    if any(p in combined for p in ['הסכם סחר', 'fta', 'כללי מקור', 'תעודת מקור',
                                    'העדפה', 'צו מסגרת', 'framework']):
        return "fta"

    if any(p in combined for p in ['צו יבוא', 'רישיון', 'import order', 'restricted',
                                    'היתר', 'אישור ליבוא']):
        return "regulatory"

    # Import reform / economic policy patterns — these ARE customs-related
    if any(p in combined for p in [
        'רפורמ',              # רפורמה, רפורמת, רפורמות
        'מה שטוב לאירופה',
        'מה שטוב לארצות הברית',
        'ce marking', 'סימון ce',
        'קוד 65',             # customs code 65 — reform clearance route
        'מסמכי מוכר',         # seller documents
        'פטור isi', 'פטור מת"י', 'פטור מכון התקנים',
        'דירקטיבה אירופית', 'דירקטיבות',
        'עץ מוצר',            # product tree (tariff classification tool)
        'תקנים אירופיים',
        'import reform',
        'eu reform',
    ]):
        return "regulatory"

    # Logistics / operational
    if any(p in combined for p in [
        'הובלה', 'מכולה ריקה', 'משאית', 'truck', 'container pickup',
        'נמל אשדוד', 'נמל חיפה', 'port',
        'סגירת מכולות', 'איסוף', 'העמסה', 'פריקה',
        'זמן נסיעה', 'מרחק', 'route', 'כמה זמן לוקח',
        'gate cutoff', 'driving time',
    ]):
        return "logistics"

    # Shipment tracking
    if entities.get("container_numbers") or entities.get("bl_numbers"):
        return "shipment"
    if any(p in combined for p in ['מעקב', 'tracking', 'shipment', 'vessel',
                                    'eta', 'etd', 'סטטוס משלוח']):
        return "shipment"

    return "general"


def _detect_all_domains(entities, subject, body):
    """Return ALL detected domains, ordered by priority."""
    combined = f"{subject} {body}".lower()
    domains = []

    # Tariff
    if (entities.get("hs_codes") or
        any(p in combined for p in ['פרט מכס', 'סיווג', 'hs code', 'classification', 'תעריף'])):
        domains.append("tariff")

    # Ordinance
    if (entities.get("article_numbers") or
        any(p in combined for p in ['פקודת המכס', 'פקודה', 'ordinance', 'סעיף',
                                     'חשבון מכר', 'חוק'])):
        domains.append("ordinance")

    # FTA
    if any(p in combined for p in ['הסכם סחר', 'fta', 'כללי מקור', 'תעודת מקור',
                                    'העדפה', 'צו מסגרת', 'framework']):
        domains.append("fta")

    # Regulatory
    if any(p in combined for p in ['צו יבוא', 'רישיון', 'import order', 'restricted',
                                    'היתר', 'אישור ליבוא', 'רפורמ', 'ce marking',
                                    'תקן', 'ISI']):
        domains.append("regulatory")

    # Logistics
    if (entities.get("locations") or entities.get("deadlines") or
        any(p in combined for p in ['הובלה', 'מכולה', 'משאית', 'truck',
                                     'container pickup', 'נמל אשדוד', 'נמל חיפה',
                                     'סגירת מכולות', 'איסוף', 'העמסה', 'פריקה',
                                     'זמן נסיעה', 'מרחק', 'route', 'כמה זמן לוקח',
                                     'gate cutoff'])):
        domains.append("logistics")

    # Shipment
    if (entities.get("container_numbers") or entities.get("bl_numbers") or
        any(p in combined for p in ['מעקב', 'tracking', 'vessel', 'eta', 'etd',
                                     'סטטוס משלוח'])):
        domains.append("shipment")

    if not domains:
        domains.append("general")

    return domains


# ═══════════════════════════════════════════
#  LOCAL (FREE) SEARCHES — always run
# ═══════════════════════════════════════════

def _search_ordinance(entities, subject, body, search_log):
    """Search ordinance articles by article number and keyword."""
    try:
        from lib._ordinance_data import ORDINANCE_ARTICLES
    except ImportError:
        try:
            from _ordinance_data import ORDINANCE_ARTICLES
        except ImportError:
            search_log.append({"search": "ordinance", "status": "import_error"})
            return []

    articles = []
    seen = set()

    # Direct article lookup
    for art_id in (entities.get("article_numbers") or []):
        art = ORDINANCE_ARTICLES.get(art_id)
        if art and art_id not in seen:
            articles.append({
                "article_id": art_id,
                "title_he": art.get("t", ""),
                "summary_en": art.get("s", ""),
                "full_text_he": (art.get("f") or "")[:3000],
                "chapter": art.get("ch", 0),
                "source": "ordinance",
            })
            seen.add(art_id)

    # Keyword search against titles and summaries
    if len(articles) < 5:
        combined = f"{subject} {body}".lower()
        # Strip Hebrew prefixes for matching
        words = set()
        for w in re.findall(r'[\u0590-\u05FF]{3,}', combined):
            words.add(w)
            # Strip common prefixes
            for prefix in ['ב', 'ל', 'ה', 'ו', 'מ', 'כ', 'ש']:
                if w.startswith(prefix) and len(w) > 3:
                    words.add(w[1:])
        for w in re.findall(r'[a-zA-Z]{4,}', combined):
            words.add(w)

        for art_id, art in ORDINANCE_ARTICLES.items():
            if art_id in seen:
                continue
            title = (art.get("t") or "").lower()
            summary = (art.get("s") or "").lower()
            full_text = (art.get("f") or "")[:500].lower()
            match_count = sum(1 for w in words if w in title or w in summary or w in full_text)
            if match_count >= 2:
                articles.append({
                    "article_id": art_id,
                    "title_he": art.get("t", ""),
                    "summary_en": art.get("s", ""),
                    "full_text_he": (art.get("f") or "")[:3000],
                    "chapter": art.get("ch", 0),
                    "source": "ordinance",
                    "_match_score": match_count,
                })
                seen.add(art_id)

        # Sort keyword matches by score, keep best
        scored = [a for a in articles if "_match_score" in a]
        scored.sort(key=lambda a: a["_match_score"], reverse=True)
        for a in scored:
            a.pop("_match_score", None)

    search_log.append({"search": "ordinance", "status": "ok", "count": len(articles)})
    return articles[:5]


def _search_framework_order(entities, body, search_log):
    """Search Framework Order articles by keyword."""
    try:
        from lib._framework_order_data import FRAMEWORK_ORDER_ARTICLES
    except ImportError:
        try:
            from _framework_order_data import FRAMEWORK_ORDER_ARTICLES
        except ImportError:
            search_log.append({"search": "framework", "status": "import_error"})
            return []

    articles = []
    combined = body.lower()
    words = set(re.findall(r'[\u0590-\u05FF]{3,}', combined))
    words.update(re.findall(r'[a-zA-Z]{4,}', combined))

    for art_id, art in FRAMEWORK_ORDER_ARTICLES.items():
        title = (art.get("t") or "").lower()
        summary = (art.get("s") or "").lower()
        full_text = (art.get("f") or "")[:300].lower()
        match_count = sum(1 for w in words if w in title or w in summary or w in full_text)
        if match_count >= 2:
            articles.append({
                "article_id": f"fw_{art_id}",
                "title_he": art.get("t", ""),
                "summary_en": art.get("s", ""),
                "full_text_he": (art.get("f") or "")[:2000],
                "source": "framework_order",
            })

    search_log.append({"search": "framework", "status": "ok", "count": len(articles)})
    return articles[:5]


def _check_cache(subject, body, db, search_log):
    """Check questions_log for cached answer."""
    if not db:
        return None
    try:
        normalized = re.sub(r'\s+', ' ', f"{subject} {body}".lower().strip())
        q_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]
        doc = db.collection("questions_log").document(q_hash).get()
        if doc.exists:
            data = doc.to_dict()
            if data.get('answer_html'):
                search_log.append({"search": "cache", "status": "hit", "hash": q_hash})
                return {
                    "answer_html": data["answer_html"],
                    "answer_text": data.get("answer_text", ""),
                    "intent": data.get("intent", ""),
                    "question_hash": q_hash,
                }
        search_log.append({"search": "cache", "status": "miss"})
    except Exception as e:
        search_log.append({"search": "cache", "status": f"error:{e}"})
    return None


# ═══════════════════════════════════════════
#  TOOL ROUTER
# ═══════════════════════════════════════════

def _get_executor(db):
    """Get ToolExecutor instance. Returns None if import fails."""
    if not db:
        return None
    try:
        from lib.tool_executors import ToolExecutor
    except ImportError:
        try:
            from tool_executors import ToolExecutor
        except ImportError:
            return None
    return ToolExecutor(db, api_key=None, gemini_key=None)


def _plan_tool_calls(pkg):
    """Determine which tools to call based on question content.
    Returns list of tool_name strings."""

    plan = []
    combined = f"{pkg.original_subject} {pkg.original_body}".lower()
    all_domains = pkg.all_domains or [pkg.domain]

    for tool_name, config in TOOL_ROUTING_MAP.items():
        # Skip classification-only tools
        if config.get("skip_in_sif"):
            continue

        # Skip fallback tools — they run later if needed
        if config.get("fallback"):
            continue

        should_call = False

        # Check 1: always_run tools run if any relevant entities present
        if config.get("always_run"):
            for et in config.get("entity_types", []):
                if pkg.entities.get(et):
                    should_call = True
                    break
            # Also run if keywords match
            if not should_call and config.get("entity_types") == ["keywords"]:
                if pkg.entities.get("keywords"):
                    should_call = True

        # Check 2: trigger keyword match
        if not should_call:
            for trigger in config.get("triggers", []):
                if trigger.lower() in combined:
                    should_call = True
                    break

        # Check 3: domain match — tool serves one of the detected domains
        if not should_call:
            for d in config.get("domains", []):
                if d in all_domains:
                    # Also need relevant entities or triggers
                    has_entities = any(pkg.entities.get(et) for et in config.get("entity_types", []))
                    has_triggers = any(t.lower() in combined for t in config.get("triggers", []))
                    if has_entities or has_triggers:
                        should_call = True
                        break

        if should_call:
            plan.append(tool_name)

    return plan


def _build_tool_params(tool_name, pkg):
    """Build parameter dict for a tool call based on extracted entities."""
    ents = pkg.entities
    combined_text = f"{pkg.original_subject} {pkg.original_body}"

    if tool_name == "search_tariff":
        terms = []
        for code in (ents.get("hs_codes") or [])[:2]:
            terms.append(code)
        for name in (ents.get("product_names") or [])[:2]:
            terms.append(name)
        if not terms:
            for kw in (ents.get("keywords") or [])[:3]:
                terms.append(kw)
        if not terms:
            return None
        return {"item_description": " ".join(terms)[:200]}

    if tool_name == "check_regulatory":
        for code in (ents.get("hs_codes") or [])[:1]:
            return {"hs_code": code}
        for name in (ents.get("product_names") or [])[:1]:
            return {"item_description": name}
        return None

    if tool_name == "verify_hs_code":
        for code in (ents.get("hs_codes") or [])[:1]:
            return {"hs_code": code}
        return None

    if tool_name == "get_chapter_notes":
        for code in (ents.get("hs_codes") or [])[:1]:
            chapter = code[:2].lstrip("0") if len(code) >= 2 else code
            return {"chapter": chapter}
        return None

    if tool_name == "lookup_tariff_structure":
        for code in (ents.get("hs_codes") or [])[:1]:
            chapter = code[:2].lstrip("0") if len(code) >= 2 else code
            return {"query": chapter}
        return None

    if tool_name == "search_xml_documents":
        terms = []
        for name in (ents.get("product_names") or [])[:1]:
            terms.append(name)
        for kw in (ents.get("keywords") or [])[:3]:
            terms.append(kw)
        if not terms:
            terms = [pkg.domain] if pkg.domain != "general" else []
        if not terms:
            return None
        return {"query": " ".join(terms)[:200]}

    if tool_name == "search_legal_knowledge":
        terms = []
        for art in (ents.get("article_numbers") or [])[:2]:
            terms.append(f"סעיף {art}")
        for kw in (ents.get("keywords") or [])[:3]:
            terms.append(kw)
        if not terms:
            # Extract meaningful words from the question
            words = re.findall(r'[\u0590-\u05FF]{3,}|[a-zA-Z]{4,}', combined_text)
            _STOP = {'מה', 'של', 'את', 'על', 'עם', 'לא', 'כל', 'או', 'גם', 'אם',
                      'אני', 'הוא', 'היא', 'זה', 'יש', 'אין', 'היה', 'היו', 'לפי',
                      'בנוסף', 'חייב', 'צריך', 'רוצה'}
            terms = [w for w in words if w.lower() not in _STOP][:4]
        if not terms:
            return None
        return {"query": " ".join(terms)[:200]}

    if tool_name == "lookup_framework_order":
        terms = (ents.get("keywords") or [])[:3]
        if not terms:
            return None
        return {"query": " ".join(terms)}

    if tool_name == "lookup_fta":
        hs = (ents.get("hs_codes") or [""])[0]
        if not hs:
            return None
        # Try to find origin country from text
        combined_lower = combined_text.lower()
        origin = ""
        for country_name in ['eu', 'turkey', 'usa', 'uk', 'china', 'korea', 'japan',
                              'טורקיה', 'סין', 'יפן', 'קוריאה']:
            if country_name in combined_lower:
                origin = country_name
                break
        if not origin:
            return None
        return {"hs_code": hs, "origin_country": origin}

    if tool_name == "search_classification_directives":
        terms = []
        for code in (ents.get("hs_codes") or [])[:1]:
            terms.append(code)
        for kw in (ents.get("keywords") or [])[:2]:
            terms.append(kw)
        if not terms:
            return None
        return {"query": " ".join(terms)[:100]}

    if tool_name == "calculate_route_eta":
        # Need origin and destination
        locations = ents.get("locations") or []
        if len(locations) < 1:
            return None
        # Find port from locations
        port_code = None
        origin = None
        for loc in locations:
            loc_lower = loc.lower()
            for name, code in _PORT_NAMES_MAP.items():
                if name in loc_lower:
                    port_code = code
                    break
            if not port_code:
                origin = loc
        # If we only found a port, use it as destination
        if port_code and not origin:
            # Look for non-port locations
            for loc in locations:
                loc_lower = loc.lower()
                is_port = any(name in loc_lower for name in _PORT_NAMES_MAP)
                if not is_port:
                    origin = loc
                    break
        if not port_code:
            port_code = "ILASD"  # default to Ashdod
        if not origin:
            return None
        # Clean location strings of port code suffixes
        origin = re.sub(r'\s*\([A-Z]+\)\s*$', '', origin).strip()
        return {"origin": origin, "port_code": port_code}

    if tool_name == "check_shipment_status":
        # Look up by container or BL
        containers = ents.get("container_numbers") or []
        bls = ents.get("bl_numbers") or []
        if containers:
            return {"container_number": containers[0]}
        if bls:
            return {"bl_number": bls[0]}
        return None

    if tool_name == "get_port_schedule":
        port_code = None
        for loc in (ents.get("locations") or []):
            loc_lower = loc.lower()
            for name, code in _PORT_NAMES_MAP.items():
                if name in loc_lower:
                    port_code = code
                    break
            if port_code:
                break
        return {"port_code": port_code or "ILHFA"}

    if tool_name == "bank_of_israel_rates":
        return {"currency": "USD"}  # default

    if tool_name == "convert_currency":
        amounts = ents.get("amounts") or []
        if amounts:
            return {"amount": amounts[0], "from_currency": "USD", "to_currency": "ILS"}
        return {"from_currency": "USD", "to_currency": "ILS"}

    if tool_name == "get_israel_vat_rates":
        return {}

    if tool_name == "lookup_country":
        combined_lower = combined_text.lower()
        for country in ['china', 'turkey', 'usa', 'india', 'germany', 'japan', 'korea',
                         'סין', 'טורקיה', 'הודו', 'גרמניה', 'יפן', 'קוריאה']:
            if country in combined_lower:
                return {"country": country}
        return None

    if tool_name == "lookup_unctad_gsp":
        combined_lower = combined_text.lower()
        for country in ['china', 'india', 'turkey', 'vietnam', 'bangladesh',
                         'סין', 'הודו', 'טורקיה', 'ויאטנם']:
            if country in combined_lower:
                return {"country": country}
        return None

    if tool_name == "search_wikipedia":
        words = re.findall(r'[\u0590-\u05FF]{3,}|[a-zA-Z]{4,}', combined_text)
        _STOP = {'מה', 'של', 'את', 'על', 'עם', 'לא', 'כל', 'או', 'גם', 'אם',
                  'אני', 'הוא', 'היא', 'זה', 'יש', 'אין', 'היה', 'היו',
                  'the', 'is', 'are', 'and', 'or', 'for', 'how', 'what'}
        terms = [w for w in words if w.lower() not in _STOP]
        if terms:
            return {"query": terms[0]}
        return None

    if tool_name == "search_wikidata":
        for name in (ents.get("product_names") or [])[:1]:
            return {"query": name}
        return None

    if tool_name == "search_pubchem":
        for name in (ents.get("product_names") or [])[:1]:
            return {"query": name}
        return None

    if tool_name == "lookup_food_product":
        for name in (ents.get("product_names") or [])[:1]:
            return {"query": name}
        return None

    if tool_name == "search_open_beauty":
        for name in (ents.get("product_names") or [])[:1]:
            return {"query": name}
        return None

    if tool_name == "check_fda_product":
        for name in (ents.get("product_names") or [])[:1]:
            return {"query": name}
        return None

    if tool_name == "search_wco_notes":
        for code in (ents.get("hs_codes") or [])[:1]:
            return {"query": code[:6]}  # HS6 for WCO
        for kw in (ents.get("keywords") or [])[:1]:
            return {"query": kw}
        return None

    if tool_name == "lookup_eu_taric":
        for code in (ents.get("hs_codes") or [])[:1]:
            return {"hs_code": code[:6]}
        return None

    if tool_name == "lookup_usitc":
        for code in (ents.get("hs_codes") or [])[:1]:
            return {"hs_code": code[:6]}
        return None

    if tool_name == "check_opensanctions":
        combined_lower = combined_text.lower()
        # Extract company/person names near sanctions keywords
        for kw in ['סנקציות', 'sanctions', 'חרם', 'embargo']:
            if kw in combined_lower:
                words = re.findall(r'[\u0590-\u05FF]{3,}|[a-zA-Z]{4,}', combined_text)
                terms = [w for w in words if w.lower() not in {kw, 'sanctions', 'סנקציות', 'חרם'}]
                if terms:
                    return {"query": " ".join(terms[:3])}
        return None

    if tool_name == "lookup_gs1_barcode":
        # Look for barcode patterns
        barcodes = re.findall(r'\b(\d{8,14})\b', combined_text)
        for bc in barcodes:
            if len(bc) in (8, 12, 13, 14):
                return {"barcode": bc}
        return None

    # Default: no params available
    return None


def _execute_tool_via_executor(executor, tool_name, params, search_log):
    """Execute a single tool via ToolExecutor and return result."""
    try:
        result = executor.execute(tool_name, params)
        search_log.append({
            "search": f"tool:{tool_name}",
            "status": "ok",
            "params": str(params)[:200],
        })
        return result
    except Exception as e:
        search_log.append({
            "search": f"tool:{tool_name}",
            "status": f"error:{e}",
            "params": str(params)[:200],
        })
        return None


def _execute_route_eta(origin, port_code, db, get_secret_func, search_log):
    """Execute calculate_route_eta directly (not a ToolExecutor tool)."""
    try:
        from lib.route_eta import calculate_route_eta
    except ImportError:
        try:
            from route_eta import calculate_route_eta
        except ImportError:
            search_log.append({"search": "tool:calculate_route_eta", "status": "import_error"})
            return None
    try:
        result = calculate_route_eta(db, origin, port_code, get_secret_func)
        search_log.append({
            "search": "tool:calculate_route_eta",
            "status": "ok",
            "params": f"origin={origin[:30]}, port={port_code}",
        })
        return result
    except Exception as e:
        search_log.append({
            "search": "tool:calculate_route_eta",
            "status": f"error:{e}",
        })
        return None


def _execute_shipment_lookup(params, db, search_log):
    """Look up shipment status from tracker_deals."""
    try:
        from lib.tracker import _find_deal_by_field, _find_deal_by_container
    except ImportError:
        try:
            from tracker import _find_deal_by_field, _find_deal_by_container
        except ImportError:
            search_log.append({"search": "tool:check_shipment_status", "status": "import_error"})
            return None
    try:
        deal_doc = None
        if params.get("container_number"):
            deal_doc = _find_deal_by_container(db, params["container_number"])
        elif params.get("bl_number"):
            deal_doc = _find_deal_by_field(db, "bl_number", params["bl_number"])

        if deal_doc:
            data = deal_doc.to_dict()
            result = {
                "found": True,
                "deal_id": deal_doc.id,
                "status": data.get("status", ""),
                "bl_number": data.get("bl_number", ""),
                "vessel": data.get("vessel_name", ""),
                "containers": data.get("containers", []),
                "direction": data.get("direction", ""),
                "eta": data.get("eta", ""),
                "etd": data.get("etd", ""),
                "shipper": data.get("shipper", ""),
                "consignee": data.get("consignee", ""),
            }
            search_log.append({"search": "tool:check_shipment_status", "status": "ok"})
            return result
        search_log.append({"search": "tool:check_shipment_status", "status": "not_found"})
        return {"found": False}
    except Exception as e:
        search_log.append({"search": "tool:check_shipment_status", "status": f"error:{e}"})
        return None


def _execute_port_schedule(params, db, search_log):
    """Look up port daily schedule."""
    try:
        from lib.schedule_il_ports import get_daily_report
    except ImportError:
        try:
            from schedule_il_ports import get_daily_report
        except ImportError:
            search_log.append({"search": "tool:get_port_schedule", "status": "import_error"})
            return None
    try:
        port_code = params.get("port_code", "ILHFA")
        result = get_daily_report(db, port_code)
        if result:
            search_log.append({"search": f"tool:get_port_schedule:{port_code}", "status": "ok"})
            return {
                "found": True,
                "port_code": port_code,
                "vessel_count": result.get("vessel_count", 0),
                "vessels": result.get("vessels", [])[:10],
                "date": result.get("date", ""),
            }
        search_log.append({"search": f"tool:get_port_schedule:{port_code}", "status": "empty"})
        return {"found": False, "port_code": port_code}
    except Exception as e:
        search_log.append({"search": "tool:get_port_schedule", "status": f"error:{e}"})
        return None


def _store_tool_result(tool_name, result, pkg):
    """Route tool results to the correct ContextPackage field."""
    if not result:
        return
    if isinstance(result, dict) and result.get("error"):
        return

    if tool_name == "search_tariff":
        candidates = result.get("candidates", []) if isinstance(result, dict) else []
        # Dedup by hs_code
        existing = {c.get("hs_code") for c in pkg.tariff_results}
        for c in candidates[:5]:
            if c.get("hs_code") not in existing:
                pkg.tariff_results.append(c)
                existing.add(c.get("hs_code"))

    elif tool_name == "check_regulatory":
        if isinstance(result, dict) and (result.get("authorities") or result.get("free_import_order")):
            pkg.regulatory_results.append({"data": result})

    elif tool_name == "search_xml_documents":
        docs = result.get("documents", []) if isinstance(result, dict) else []
        pkg.xml_results.extend(docs[:5])

    elif tool_name in ("search_wikipedia", "search_wikidata"):
        if isinstance(result, dict) and result.get("found"):
            pkg.wikipedia_results.append({
                "query": result.get("query", ""),
                "title": result.get("title", ""),
                "extract": (result.get("extract") or result.get("description") or "")[:1500],
            })

    elif tool_name in ("search_legal_knowledge", "search_classification_directives"):
        # These return knowledge that supplements ordinance context
        if isinstance(result, dict) and result.get("found"):
            items = result.get("results", result.get("documents", []))
            if isinstance(items, list):
                for item in items[:3]:
                    pkg.other_tool_results.append({"tool": tool_name, "result": item})
            else:
                pkg.other_tool_results.append({"tool": tool_name, "result": result})

    elif tool_name in ("calculate_route_eta",):
        if isinstance(result, dict) and result.get("duration_minutes"):
            pkg.logistics_results.append(result)

    elif tool_name in ("check_shipment_status",):
        if isinstance(result, dict) and result.get("found"):
            pkg.shipment_results.append(result)

    elif tool_name in ("get_port_schedule",):
        if isinstance(result, dict) and result.get("found"):
            pkg.logistics_results.append({"type": "port_schedule", **result})

    elif tool_name in ("bank_of_israel_rates", "convert_currency", "get_israel_vat_rates"):
        if isinstance(result, dict) and not result.get("error"):
            pkg.other_tool_results.append({"tool": tool_name, "result": result})

    elif tool_name in ("lookup_fta", "lookup_framework_order"):
        if isinstance(result, dict) and not result.get("error"):
            pkg.other_tool_results.append({"tool": tool_name, "result": result})

    elif tool_name in ("lookup_eu_taric", "lookup_usitc", "search_wco_notes",
                        "lookup_unctad_gsp", "check_opensanctions", "lookup_country"):
        if isinstance(result, dict) and not result.get("error"):
            pkg.other_tool_results.append({"tool": tool_name, "result": result})

    elif tool_name in ("search_pubchem", "lookup_food_product", "search_open_beauty",
                        "check_fda_product", "lookup_gs1_barcode"):
        if isinstance(result, dict) and result.get("found"):
            pkg.wikipedia_results.append({
                "query": result.get("query", tool_name),
                "title": result.get("name", result.get("product_name", tool_name)),
                "extract": json.dumps(result, ensure_ascii=False, default=str)[:1000],
            })

    elif tool_name == "verify_hs_code":
        if isinstance(result, dict) and result.get("verification_status"):
            pkg.other_tool_results.append({"tool": tool_name, "result": result})

    else:
        # Generic catch-all
        pkg.other_tool_results.append({"tool": tool_name, "result": result})


def _execute_tool_plan(plan, pkg, db, get_secret_func):
    """Execute planned tool calls and store results in pkg."""
    if not plan:
        return

    executor = _get_executor(db)

    # Separate tools by execution method
    executor_tools = set(TOOL_ROUTING_MAP.keys()) - {
        "calculate_route_eta", "check_shipment_status", "get_port_schedule"
    }

    for tool_name in plan:
        params = _build_tool_params(tool_name, pkg)
        if params is None:
            pkg.search_log.append({"search": f"tool:{tool_name}", "status": "no_params"})
            continue

        try:
            if tool_name == "calculate_route_eta":
                result = _execute_route_eta(
                    params.get("origin", ""),
                    params.get("port_code", "ILASD"),
                    db, get_secret_func, pkg.search_log
                )
            elif tool_name == "check_shipment_status":
                result = _execute_shipment_lookup(params, db, pkg.search_log)
            elif tool_name == "get_port_schedule":
                result = _execute_port_schedule(params, db, pkg.search_log)
            elif executor and tool_name in executor_tools:
                result = _execute_tool_via_executor(executor, tool_name, params, pkg.search_log)
            else:
                pkg.search_log.append({"search": f"tool:{tool_name}", "status": "no_executor"})
                continue

            _store_tool_result(tool_name, result, pkg)

        except Exception as e:
            pkg.search_log.append({
                "search": f"tool:{tool_name}",
                "status": f"crash:{e}",
            })

    # After all planned tools, check if we need fallbacks
    customs_data_count = (len(pkg.tariff_results) + len(pkg.ordinance_articles) +
                          len(pkg.regulatory_results) + len(pkg.framework_articles))

    if customs_data_count < 2 and executor:
        # Run fallback tools (wikipedia)
        for tool_name, config in TOOL_ROUTING_MAP.items():
            if not config.get("fallback"):
                continue
            if tool_name in plan:
                continue  # already ran
            try:
                params = _build_tool_params(tool_name, pkg)
                if params:
                    result = _execute_tool_via_executor(executor, tool_name, params, pkg.search_log)
                    _store_tool_result(tool_name, result, pkg)
            except Exception:
                pass


# ═══════════════════════════════════════════
#  SUMMARY & CONFIDENCE
# ═══════════════════════════════════════════

def _build_context_summary(pkg):
    """Build structured text summary for AI prompt injection."""
    parts = [
        "=== נתוני מערכת RCB ===",
        f"שפה שזוהתה: {pkg.detected_language}",
        f"תחום: {pkg.domain}",
    ]
    if pkg.all_domains and len(pkg.all_domains) > 1:
        parts.append(f"תחומים נוספים: {', '.join(pkg.all_domains[1:])}")

    # Entities
    ents = pkg.entities
    if ents.get("hs_codes"):
        parts.append(f"קודי HS שזוהו: {', '.join(ents['hs_codes'])}")
    if ents.get("product_names"):
        parts.append(f"מוצרים: {', '.join(ents['product_names'])}")
    if ents.get("article_numbers"):
        parts.append(f"סעיפים שהוזכרו: {', '.join(ents['article_numbers'])}")
    if ents.get("locations"):
        parts.append(f"מיקומים: {', '.join(ents['locations'])}")
    if ents.get("deadlines"):
        parts.append(f"מועדים: {', '.join(ents['deadlines'])}")
    if ents.get("amounts"):
        parts.append(f"סכומים: {', '.join(ents['amounts'])}")

    # Tariff results
    if pkg.tariff_results:
        parts.append("\n--- תוצאות חיפוש תעריף ---")
        for c in pkg.tariff_results[:5]:
            hs = c.get("hs_code", "")
            desc = c.get("description_he", c.get("description", ""))
            duty = c.get("duty_rate", "")
            parts.append(f"  {hs}: {desc}" + (f" (מכס: {duty})" if duty else ""))

    # Ordinance articles
    if pkg.ordinance_articles:
        parts.append("\n--- מאמרי פקודת המכס ---")
        for a in pkg.ordinance_articles:
            art_id = a.get("article_id", "")
            title = a.get("title_he", "")
            full = a.get("full_text_he", "")
            parts.append(f"\nסעיף {art_id}: {title}")
            if full:
                parts.append(f"נוסח הסעיף: {full}")

    # XML documents
    if pkg.xml_results:
        parts.append("\n--- מסמכי XML רלוונטיים ---")
        for d in pkg.xml_results:
            title = d.get("title", d.get("doc_id", ""))
            excerpt = (d.get("text_excerpt") or "")[:300]
            parts.append(f"  {title}: {excerpt}")

    # Regulatory
    if pkg.regulatory_results:
        parts.append("\n--- מידע רגולטורי ---")
        for r in pkg.regulatory_results:
            hs = r.get("hs_code", r.get("product", ""))
            data = r.get("data", {})
            auths = data.get("authorities", [])
            parts.append(f"  {hs}: {', '.join(str(a) for a in auths[:5])}" if auths else f"  {hs}: (נמצא)")

    # Framework order
    if pkg.framework_articles:
        parts.append("\n--- צווי מסגרת ---")
        for a in pkg.framework_articles:
            art_id = a.get("article_id", "")
            title = a.get("title_he", "")
            full = a.get("full_text_he", "")
            parts.append(f"\n{art_id}: {title}")
            if full:
                parts.append(f"נוסח: {full}")

    # Wikipedia / external knowledge results
    if pkg.wikipedia_results:
        parts.append("\n--- ידע כללי (ויקיפדיה) ---")
        for w in pkg.wikipedia_results:
            parts.append(f"\n{w.get('title', w.get('query', ''))}: {w.get('extract', '')[:800]}")

    # Logistics results
    if pkg.logistics_results:
        parts.append("\n--- מידע לוגיסטי ---")
        for lr in pkg.logistics_results:
            if lr.get("type") == "port_schedule":
                parts.append(f"  לוח אניות {lr.get('port_code', '')}: {lr.get('vessel_count', 0)} אניות")
                for v in (lr.get("vessels") or [])[:5]:
                    parts.append(f"    {v.get('vessel_name', '')} — ETA: {v.get('eta', 'N/A')}")
            elif lr.get("duration_minutes"):
                mins = lr["duration_minutes"]
                km = lr.get("distance_km", 0)
                parts.append(f"  זמן נסיעה: {mins:.0f} דקות ({km:.1f} ק\"מ)")
                if lr.get("route_summary"):
                    parts.append(f"  מסלול: {lr['route_summary']}")

    # Shipment results
    if pkg.shipment_results:
        parts.append("\n--- מעקב משלוחים ---")
        for sr in pkg.shipment_results:
            parts.append(f"  B/L: {sr.get('bl_number', 'N/A')} | "
                         f"סטטוס: {sr.get('status', 'N/A')} | "
                         f"אנייה: {sr.get('vessel', 'N/A')}")
            if sr.get("containers"):
                parts.append(f"  מכולות: {', '.join(sr['containers'][:5])}")
            if sr.get("eta"):
                parts.append(f"  ETA: {sr['eta']}")

    # Other tool results
    if pkg.other_tool_results:
        parts.append("\n--- מידע נוסף מכלים ---")
        for otr in pkg.other_tool_results:
            tool = otr.get("tool", "")
            res = otr.get("result", {})
            res_str = json.dumps(res, ensure_ascii=False, default=str)[:500] if isinstance(res, dict) else str(res)[:500]
            parts.append(f"  [{tool}]: {res_str}")

    # Cached answer
    if pkg.cached_answer:
        parts.append("\n--- תשובה קודמת דומה ---")
        parts.append(pkg.cached_answer.get("answer_text", "(cached)")[:500])

    parts.append("\n=== סוף נתוני מערכת ===")
    return "\n".join(parts)


def _calculate_confidence(pkg):
    """Calculate confidence based on what data was found."""
    score = 0.0
    if pkg.tariff_results:
        score += 0.3
    if pkg.ordinance_articles:
        score += 0.3
    if pkg.xml_results:
        score += 0.1
    if pkg.regulatory_results:
        score += 0.1
    if pkg.framework_articles:
        score += 0.1
    if pkg.wikipedia_results:
        score += 0.15
    if pkg.logistics_results:
        score += 0.2
    if pkg.shipment_results:
        score += 0.2
    if pkg.other_tool_results:
        score += 0.1
    if pkg.cached_answer:
        score += 0.3
    if pkg.entities.get("keywords"):
        score += 0.1
    return min(score, 1.0)


# ═══════════════════════════════════════════
#  MAIN PUBLIC FUNCTION
# ═══════════════════════════════════════════

def prepare_context_package(subject, body, db, get_secret_func=None):
    """
    System Intelligence First: search ALL relevant data sources BEFORE AI.

    Uses tool router to determine which of the 34+ tools are relevant to the
    question, then executes them. Local searches (ordinance, framework) always
    run for free. API tools are routed based on detected domains and entities.

    Returns a ContextPackage with pre-assembled results and a context_summary
    string ready for injection into AI prompts.
    """
    t0 = time.time()
    search_log = []

    # Strip HTML from body
    body_plain = re.sub(r'<[^>]+>', ' ', body or "").strip()
    body_plain = re.sub(r'&\w+;', ' ', body_plain)
    body_plain = re.sub(r'\s+', ' ', body_plain).strip()

    pkg = ContextPackage(
        original_subject=subject or "",
        original_body=body_plain,
        detected_language=_detect_language(subject or "", body_plain),
        search_log=search_log,
    )

    # 1. Extract entities (now includes locations, amounts, deadlines)
    pkg.entities = _extract_entities(subject or "", body_plain)

    # 2. Detect domain(s)
    pkg.domain = _detect_domain(pkg.entities, subject or "", body_plain)
    pkg.all_domains = _detect_all_domains(pkg.entities, subject or "", body_plain)

    # 3. Check cache first
    try:
        pkg.cached_answer = _check_cache(subject or "", body_plain, db, search_log)
    except Exception as e:
        search_log.append({"search": "cache", "status": f"crash:{e}"})

    # 4. Local searches — ALWAYS run (free, in-memory)
    try:
        pkg.ordinance_articles = _search_ordinance(
            pkg.entities, subject or "", body_plain, search_log)
    except Exception as e:
        search_log.append({"search": "ordinance", "status": f"crash:{e}"})

    try:
        pkg.framework_articles = _search_framework_order(
            pkg.entities, body_plain, search_log)
    except Exception as e:
        search_log.append({"search": "framework", "status": f"crash:{e}"})

    # 5. Tool Router — plan and execute relevant tools
    try:
        tool_plan = _plan_tool_calls(pkg)
        if tool_plan:
            print(f"    🔧 Tool router plan ({len(tool_plan)} tools): {', '.join(tool_plan)}")
        _execute_tool_plan(tool_plan, pkg, db, get_secret_func)
    except Exception as e:
        search_log.append({"search": "tool_router", "status": f"crash:{e}"})

    # 6. Build summary and confidence
    pkg.context_summary = _build_context_summary(pkg)
    pkg.confidence = _calculate_confidence(pkg)

    elapsed = int((time.time() - t0) * 1000)
    search_log.append({"search": "total", "elapsed_ms": elapsed})
    print(f"    📦 SIF context package: domain={pkg.domain}, "
          f"all_domains={pkg.all_domains}, confidence={pkg.confidence:.2f}, "
          f"tariff={len(pkg.tariff_results)}, ordinance={len(pkg.ordinance_articles)}, "
          f"xml={len(pkg.xml_results)}, regulatory={len(pkg.regulatory_results)}, "
          f"framework={len(pkg.framework_articles)}, "
          f"logistics={len(pkg.logistics_results)}, shipment={len(pkg.shipment_results)}, "
          f"other={len(pkg.other_tool_results)}, elapsed={elapsed}ms")

    return pkg
