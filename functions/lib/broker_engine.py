"""Broker Engine — Deterministic customs classification engine.

AI is called ONCE (Phase 1 item identification). Everything after is
deterministic Python: GIR 1-6 elimination, Chapter 98 mapping, discount codes,
FIO/FEO regulatory, FTA preferences, customs valuation articles.

Usage:
    from lib.broker_engine import process_case, classify_single_item, verify_and_loop

Session 90 — broker_engine.py
"""

import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

# ---------------------------------------------------------------------------
#  IMPORTS — existing modules (lazy where needed to avoid circular)
# ---------------------------------------------------------------------------

try:
    from lib.case_reasoning import analyze_case, get_discount_for_item, CasePlan
except ImportError:
    from case_reasoning import analyze_case, get_discount_for_item, CasePlan

try:
    from lib._chapter98_data import (
        get_chapter98_code, get_chapter98_entry, CHAPTER_TO_98_MAP,
    )
except ImportError:
    from _chapter98_data import (
        get_chapter98_code, get_chapter98_entry, CHAPTER_TO_98_MAP,
    )

try:
    from lib.customs_law import (
        get_ordinance_article, get_valuation_methods,
        CUSTOMS_ORDINANCE_ARTICLES,
    )
except ImportError:
    from customs_law import (
        get_ordinance_article, get_valuation_methods,
        CUSTOMS_ORDINANCE_ARTICLES,
    )

try:
    from lib._discount_codes_data import get_sub_code, get_discount_code
except ImportError:
    from _discount_codes_data import get_sub_code, get_discount_code

# Elimination engine — heavy, lazy import in functions that need it
_eliminate = None
_make_product_info = None
_candidates_from_pre_classify = None


def _ensure_elimination():
    global _eliminate, _make_product_info, _candidates_from_pre_classify
    if _eliminate is not None:
        return
    try:
        from lib.elimination_engine import (
            eliminate, make_product_info, candidates_from_pre_classify,
        )
    except ImportError:
        from elimination_engine import (
            eliminate, make_product_info, candidates_from_pre_classify,
        )
    _eliminate = eliminate
    _make_product_info = make_product_info
    _candidates_from_pre_classify = candidates_from_pre_classify


# Pre-classify for candidate generation
_pre_classify = None


def _ensure_pre_classify():
    global _pre_classify
    if _pre_classify is not None:
        return
    try:
        from lib.intelligence import pre_classify
    except ImportError:
        from intelligence import pre_classify
    _pre_classify = pre_classify


# FTA country map (same as tool_executors — avoids importing the class)
_FTA_COUNTRY_MAP = {
    "eu": "eu", "european union": "eu",
    "germany": "eu", "france": "eu", "italy": "eu", "spain": "eu",
    "netherlands": "eu", "belgium": "eu", "austria": "eu", "poland": "eu",
    "czech republic": "eu", "czechia": "eu", "romania": "eu",
    "portugal": "eu", "greece": "eu", "sweden": "eu", "denmark": "eu",
    "finland": "eu", "ireland": "eu", "hungary": "eu", "bulgaria": "eu",
    "croatia": "eu", "slovakia": "eu", "slovenia": "eu", "lithuania": "eu",
    "latvia": "eu", "estonia": "eu", "cyprus": "eu", "luxembourg": "eu",
    "malta": "eu",
    "uk": "uk", "united kingdom": "uk", "great britain": "uk", "england": "uk",
    "usa": "usa", "united states": "usa", "us": "usa",
    "turkey": "turkey", "turkiye": "turkey",
    "canada": "canada",
    "korea": "korea", "south korea": "korea",
    "ukraine": "ukraine",
    "jordan": "jordan",
    "egypt": "egypt",
    "efta": "efta", "switzerland": "efta", "norway": "efta",
    "iceland": "efta", "liechtenstein": "efta",
    "mexico": "mexico",
    "colombia": "colombia",
    "panama": "panama",
    "mercosur": "mercosur", "brazil": "mercosur", "argentina": "mercosur",
    "uruguay": "mercosur", "paraguay": "mercosur",
    "vietnam": "vietnam",
    "uae": "uae", "united arab emirates": "uae",
    "guatemala": "guatemala",
    "costa rica": "costa_rica",
    "china": "china",
    "india": "india",
    "japan": "japan",
    "taiwan": "taiwan",
    "thailand": "thailand",
    "belarus": "belarus",
}


# ---------------------------------------------------------------------------
#  CONSTANTS
# ---------------------------------------------------------------------------

ISRAEL_VAT_RATE = "18%"

# Ordinance articles relevant to classification pipeline
_VALUATION_ARTICLES = ["129", "130", "131", "132", "133", "133א"]
_RELEASE_ARTICLES = ["62", "63", "64"]
_IP_ARTICLES = [f"200{s}" for s in ["א", "ב", "ג", "ד", "ה", "ו", "ז",
                                     "ח", "ט", "י", "יא", "יב", "יג", "יד"]]

# Spare-part detection keywords
_SPARE_PART_RE = re.compile(
    r'חלק[יי]?\s*חילוף|חלפ|spare\s*part|replacement\s*part|'
    r'accessory|accessories|אביזר|אביזרים',
    re.IGNORECASE,
)

# Phase 1: item identification prompt (single AI call)
_ITEM_ID_SYSTEM = """You are a customs classification expert. For each item below,
identify: (1) physical composition/material, (2) essential character/nature,
(3) primary function/use. Return JSON array. Be concise — 1-2 words each field.
Example: [{"name":"sofa","physical":"wood frame, polyester fabric","essence":"seating furniture","function":"sitting"}]"""

_ITEM_ID_USER = """Items to analyze:
{items_list}
Return ONLY a JSON array with fields: name, physical, essence, function."""


# ---------------------------------------------------------------------------
#  PHASE 1: Item identification (ONE AI call)
# ---------------------------------------------------------------------------

def _identify_items_with_ai(items, get_secret_func):
    """Call AI once to get physical/essence/function for all items.

    Args:
        items: list of dicts from CasePlan.items_to_classify
        get_secret_func: function to get API keys

    Returns:
        list of dicts with added physical, essence, function fields.
        Falls back to regex-based extraction on AI failure.
    """
    if not items:
        return []

    items_text = "\n".join(
        f"- {it.get('name', '')} ({it.get('category', '')})"
        for it in items
    )

    ai_result = None
    if get_secret_func:
        ai_result = _call_ai_for_items(items_text, get_secret_func)

    if ai_result and isinstance(ai_result, list):
        # Merge AI analysis back into items
        for i, item in enumerate(items):
            if i < len(ai_result):
                ai_item = ai_result[i] if isinstance(ai_result[i], dict) else {}
                item["physical"] = ai_item.get("physical", "")
                item["essence"] = ai_item.get("essence", "")
                item["function"] = ai_item.get("function", "")
        return items

    # Fallback: regex-based extraction
    return _fallback_item_identification(items)


def _call_ai_for_items(items_text, get_secret_func):
    """Try Gemini -> ChatGPT -> Claude for item identification."""
    import json

    prompt_user = _ITEM_ID_USER.format(items_list=items_text)

    # Try Gemini first (cheapest)
    try:
        gk = get_secret_func("GEMINI_API_KEY")
        if gk:
            try:
                from lib.classification_agents import call_gemini
            except ImportError:
                from classification_agents import call_gemini
            text = call_gemini(gk, _ITEM_ID_SYSTEM, prompt_user, max_tokens=1000)
            if text:
                return _parse_json_array(text)
    except Exception:
        pass

    # Try ChatGPT (second cheapest)
    try:
        ok = get_secret_func("OPENAI_API_KEY")
        if ok:
            try:
                from lib.classification_agents import call_chatgpt
            except ImportError:
                from classification_agents import call_chatgpt
            text = call_chatgpt(ok, _ITEM_ID_SYSTEM, prompt_user, max_tokens=1000)
            if text:
                return _parse_json_array(text)
    except Exception:
        pass

    return None


def _parse_json_array(text):
    """Extract JSON array from AI response text."""
    import json
    # Find JSON array in response
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def _fallback_item_identification(items):
    """Regex-based item identification when AI is unavailable."""
    _MATERIAL_MAP = {
        "furniture": ("wood, fabric, foam", "seating/storage furniture", "household use"),
        "electronics": ("plastic, metal, circuits", "electronic device", "computing/entertainment"),
        "vehicle": ("steel, rubber, glass", "motor vehicle", "transportation"),
        "personal": ("mixed materials", "personal belongings", "personal use"),
        "kitchen": ("ceramic, metal, glass", "kitchenware", "food preparation"),
        "food": ("organic matter", "food product", "consumption"),
        "textiles": ("fabric, cotton, polyester", "textile product", "household/clothing"),
        "music": ("wood, metal, strings", "musical instrument", "music"),
    }
    for item in items:
        cat = item.get("category", "personal")
        phys, ess, func = _MATERIAL_MAP.get(cat, ("mixed", "general goods", "general use"))
        item.setdefault("physical", phys)
        item.setdefault("essence", ess)
        item.setdefault("function", func)
    return items


# ---------------------------------------------------------------------------
#  PHASE 2: Spare parts check
# ---------------------------------------------------------------------------

def _check_spare_part(item, text, db):
    """Check if item is a spare part that should follow parent machine chapter.

    GIR Rule 2b + Note 2 to Sections XV-XVII: Parts and accessories are
    classified with their parent machine unless specifically provided for.

    Returns:
        str or None: parent chapter heading code if spare part, else None.
    """
    if not _SPARE_PART_RE.search(text):
        return None

    # Item must have a parent machine reference
    name = item.get("name", "").lower()
    essence = item.get("essence", "").lower()

    # Common parent machine chapters for spare parts
    _PARENT_CHAPTERS = {
        "vehicle": "87", "car": "87", "רכב": "87", "אוטו": "87",
        "machine": "84", "מכונה": "84", "machinery": "84",
        "computer": "84", "מחשב": "84",
        "electrical": "85", "חשמלי": "85",
        "refrigerator": "84", "מקרר": "84",
        "washing": "84", "כביסה": "84",
    }

    for keyword, chapter in _PARENT_CHAPTERS.items():
        if keyword in name or keyword in essence or keyword in text.lower():
            return chapter

    return None


# ---------------------------------------------------------------------------
#  PHASE 3-6: Build candidates + eliminate
# ---------------------------------------------------------------------------

def _build_candidates_for_item(item, db):
    """Search tariff DB for candidate HS codes matching item description.

    Returns:
        pre_classify result dict with candidates list.
    """
    _ensure_pre_classify()

    description = item.get("name", "")
    keywords = item.get("keywords", [])
    if keywords:
        description = f"{description} {' '.join(keywords)}"

    # Add physical/essence/function context if available
    physical = item.get("physical", "")
    essence = item.get("essence", "")
    function = item.get("function", "")
    if physical:
        description = f"{description} ({physical})"
    if essence and essence not in description.lower():
        description = f"{description} {essence}"

    return _pre_classify(db, description)


def classify_single_item(item, operation_context, db, spare_chapter=None):
    """Classify one item via pre_classify -> eliminate (GIR 1-6).

    Args:
        item: dict with name, keywords, category, physical, essence, function
        operation_context: dict with direction, legal_category, origin_country
        db: Firestore client
        spare_chapter: optional parent chapter code for spare parts

    Returns:
        dict with hs_code, confidence, description, duty_rate, elimination_result,
        or None if no candidates found.
    """
    _ensure_elimination()

    # Build candidates from tariff search
    pre_result = _build_candidates_for_item(item, db)
    if not pre_result or not pre_result.get("candidates"):
        return None

    # If spare part, boost parent chapter candidates
    candidates = _candidates_from_pre_classify(pre_result)
    if spare_chapter:
        for c in candidates:
            hs = str(c.get("hs_code", "")).replace(".", "").replace("/", "")
            if hs[:2].zfill(2) == spare_chapter.zfill(2):
                c["confidence"] = min(1.0, c.get("confidence", 0.5) + 0.2)

    # Build product info for elimination engine
    product_info = _make_product_info({
        "description": item.get("name", ""),
        "material": item.get("physical", ""),
        "use": item.get("function", ""),
        "origin_country": operation_context.get("origin_country", ""),
    })

    # Run elimination engine (GIR 1-6, deterministic)
    elim_result = _eliminate(db, product_info, candidates)

    survivors = elim_result.get("survivors", [])
    if not survivors:
        # All eliminated — use top pre_classify candidate as fallback
        top = pre_result["candidates"][0]
        return {
            "hs_code": top.get("hs_code", ""),
            "confidence": top.get("confidence", 0.3),
            "description": top.get("description", ""),
            "duty_rate": top.get("duty_rate", ""),
            "elimination_result": elim_result,
            "source": "pre_classify_fallback",
        }

    # Pick top survivor by confidence
    best = max(survivors, key=lambda s: s.get("confidence", 0))
    return {
        "hs_code": best.get("hs_code", ""),
        "confidence": best.get("confidence", 0.5),
        "description": best.get("description", best.get("description_en", "")),
        "duty_rate": best.get("duty_rate", ""),
        "elimination_result": elim_result,
        "source": "elimination_engine",
    }


# ---------------------------------------------------------------------------
#  PHASE 7: Chapter 98 mapping
# ---------------------------------------------------------------------------

def _apply_chapter98(item_result, item, legal_category, item_category=""):
    """Map classification result to Chapter 98 code if personal import.

    Modifies item_result in-place to add chapter98_* fields.
    """
    if not legal_category or not item_result:
        return

    hs_code = item_result.get("hs_code", "")
    ch98_code = get_chapter98_code(hs_code)
    if not ch98_code:
        return

    ch98_entry = get_chapter98_entry(ch98_code)
    if not ch98_entry:
        return

    item_result["chapter98_code"] = ch98_code
    item_result["chapter98_desc_he"] = ch98_entry.get("desc_he", "")
    item_result["chapter98_desc_en"] = ch98_entry.get("desc_en", "")
    item_result["chapter98_duty"] = ch98_entry.get("duty", "")
    item_result["chapter98_pt"] = ch98_entry.get("purchase_tax", "")
    item_result["chapter98_legal_basis"] = ch98_entry.get("legal_basis", "")

    # Get discount code info
    discount_info = get_discount_for_item(
        item.get("name", ""), hs_code, legal_category,
        item_category=item_category or item.get("category", ""),
    )
    if discount_info:
        item_result["discount"] = discount_info


# ---------------------------------------------------------------------------
#  PHASE 8: Post-classification cascade
# ---------------------------------------------------------------------------

def _post_classification_cascade(item_result, item, operation_context, db):
    """Systematic post-classification checks per HS code.

    Checks (in order):
    1. צו יבוא חופשי — which תוספת, which רשות מאשרת, which תקן
    2. צו יצוא חופשי — export license requirements (export only)
    3. פקודת המכס articles — 129 personal, 130-133 valuation, 62 release, 200א-200יד IP
    4. צו מסגרת FTA — which supplement, which rules of origin, which preference document

    Modifies item_result in-place.
    """
    if not item_result:
        return

    hs_code = item_result.get("hs_code", "")
    direction = operation_context.get("direction", "import")

    # --- CHECK 1: Free Import Order (צו יבוא חופשי) ---
    if direction == "import":
        fio = _lookup_fio(db, hs_code)
        if fio and fio.get("found"):
            item_result["fio"] = _format_fio_result(fio)

    # --- CHECK 2: Free Export Order (צו יצוא חופשי) ---
    if direction == "export":
        feo = _lookup_feo(db, hs_code)
        if feo and feo.get("found"):
            item_result["feo"] = _format_feo_result(feo)

    # --- CHECK 3: Customs Ordinance articles ---
    item_result["ordinance_articles"] = _collect_ordinance_articles(
        operation_context, item_result,
    )

    # --- CHECK 4: FTA / צו מסגרת ---
    origin = operation_context.get("origin_country", "")
    if origin:
        fta = _lookup_fta_for_item(db, hs_code, origin)
        if fta:
            item_result["fta"] = fta

    # --- Always add VAT ---
    item_result["vat_rate"] = ISRAEL_VAT_RATE


def _lookup_fio(db, hs_code):
    """Look up Free Import Order requirements directly from Firestore.

    Returns structured dict with תוספת (appendix), רשות מאשרת (authority),
    תקן (standard) per requirement.
    """
    hs_clean = str(hs_code).replace(".", "").replace(" ", "").replace("/", "").replace("-", "")
    hs_10 = hs_clean.ljust(10, "0")[:10]

    candidates = [hs_clean, hs_10]
    # Try Luhn check digit variant
    if len(hs_10) == 10 and hs_10.isdigit():
        try:
            try:
                from lib.librarian import _hs_check_digit
            except ImportError:
                from librarian import _hs_check_digit
            check = _hs_check_digit(hs_10)
            candidates.append(f"{hs_10}_{check}")
        except Exception:
            pass

    for doc_id in candidates:
        try:
            doc = db.collection("free_import_order").document(doc_id).get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    "hs_code": hs_code,
                    "found": True,
                    "goods_description": data.get("goods_description", ""),
                    "requirements": data.get("requirements", []),
                    "authorities_summary": data.get("authorities_summary", []),
                    "has_standards": data.get("has_standards", False),
                    "has_lab_testing": data.get("has_lab_testing", False),
                    "appendices": data.get("appendices", []),
                    "active_count": data.get("active_count", 0),
                }
        except Exception:
            continue

    # Parent code fallback (strip last 2-4 digits)
    for trim in [2, 4]:
        if len(hs_clean) > trim + 2:
            prefix = hs_clean[:len(hs_clean) - trim]
            try:
                docs = db.collection("free_import_order").where(
                    "hs_10", ">=", prefix.ljust(10, "0")
                ).where(
                    "hs_10", "<", prefix.ljust(10, "0")[:len(prefix)] + chr(ord(prefix[-1]) + 1) + "0" * (9 - len(prefix))
                ).limit(1).stream()
                for d in docs:
                    data = d.to_dict()
                    return {
                        "hs_code": hs_code,
                        "found": True,
                        "source": "parent_code",
                        "goods_description": data.get("goods_description", ""),
                        "requirements": data.get("requirements", []),
                        "authorities_summary": data.get("authorities_summary", []),
                        "has_standards": data.get("has_standards", False),
                        "has_lab_testing": data.get("has_lab_testing", False),
                        "appendices": data.get("appendices", []),
                        "active_count": data.get("active_count", 0),
                    }
            except Exception:
                continue

    return {"hs_code": hs_code, "found": False}


def _format_fio_result(fio):
    """Format FIO result into structured per-requirement detail.

    Each requirement specifies:
    - תוספת (appendix/supplement) — which schedule of the order
    - רשות מאשרת (approving authority) — which government ministry
    - תקן (standard) — which Israeli standard (SI) applies
    - conditions — import conditions text
    """
    formatted = {
        "found": True,
        "goods_description": fio.get("goods_description", ""),
        "has_standards": fio.get("has_standards", False),
        "has_lab_testing": fio.get("has_lab_testing", False),
        "appendices": fio.get("appendices", []),
        "authorities": fio.get("authorities_summary", []),
        "active_requirements": fio.get("active_count", 0),
        "requirements": [],
    }

    for req in fio.get("requirements", []):
        formatted["requirements"].append({
            "appendix": req.get("appendix", req.get("supplement", "")),
            "authority": req.get("authority", ""),
            "confirmation_type": req.get("confirmation_type", ""),
            "conditions": req.get("conditions", ""),
            "inception": req.get("inception_code", req.get("inception", "")),
            "standard_ref": _extract_standard_ref(req),
        })

    return formatted


def _extract_standard_ref(req):
    """Extract Israeli Standard (SI/ת\"י) reference from requirement text."""
    text = f"{req.get('confirmation_type', '')} {req.get('conditions', '')}"
    # Match patterns like "ת"י 900", "SI 1022", "תקן ישראלי 60335"
    m = re.search(r'(?:ת"י|ת״י|תי|SI|ת\.י\.?)\s*(\d{2,5})', text)
    if m:
        return f"SI {m.group(1)}"
    m = re.search(r'תקן\s*(?:ישראלי\s*)?(\d{2,5})', text)
    if m:
        return f"SI {m.group(1)}"
    return ""


def _lookup_feo(db, hs_code):
    """Look up Free Export Order requirements from Firestore."""
    hs_clean = str(hs_code).replace(".", "").replace(" ", "").replace("/", "").replace("-", "")

    for doc_id in [hs_clean]:
        try:
            doc = db.collection("free_export_order").document(doc_id).get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    "hs_code": hs_code,
                    "found": True,
                    "goods_description": data.get("goods_description", ""),
                    "authorities": data.get("authorities_summary", []),
                    "confirmation_types": data.get("confirmation_types", []),
                    "appendices": data.get("appendices", []),
                    "has_absolute": data.get("has_absolute", False),
                    "active_count": data.get("active_count", 0),
                    "requirements": [
                        {
                            "confirmation_type": r.get("confirmation_type", ""),
                            "authority": r.get("authority", ""),
                            "appendix": r.get("appendix", ""),
                        }
                        for r in data.get("requirements", [])[:20]
                    ],
                }
        except Exception:
            continue

    return {"hs_code": hs_code, "found": False}


def _format_feo_result(feo):
    """Format FEO result with export license requirements."""
    return {
        "found": True,
        "goods_description": feo.get("goods_description", ""),
        "authorities": feo.get("authorities", []),
        "requires_export_license": feo.get("has_absolute", False),
        "appendices": feo.get("appendices", []),
        "active_requirements": feo.get("active_count", 0),
        "requirements": feo.get("requirements", []),
    }


def _collect_ordinance_articles(operation_context, item_result):
    """Collect relevant Customs Ordinance articles for the classification.

    Returns dict keyed by article category with article data.
    """
    articles = {}
    legal_category = operation_context.get("legal_category", "")

    # Section 129: Personal use exemption (entry-entitled persons)
    if legal_category:
        art129 = get_ordinance_article("129")
        if art129:
            articles["personal_use_129"] = {
                "article": "129",
                "title_he": art129.get("t", ""),
                "summary": art129.get("s", ""),
                "applies": True,
                "reason": f"Legal category: {legal_category}",
            }

    # Sections 130-133: Valuation methods (always relevant for imports)
    if operation_context.get("direction") == "import":
        valuation_methods = get_valuation_methods()
        val_articles = {}
        for art_id in ["130", "131", "132", "133", "133א"]:
            art = get_ordinance_article(art_id)
            if art:
                val_articles[art_id] = {
                    "article": art_id,
                    "title_he": art.get("t", ""),
                    "summary": art.get("s", ""),
                }
        articles["valuation_130_133"] = {
            "methods": valuation_methods,
            "articles": val_articles,
            "primary_method": "transaction_value",
            "article_132_applies": True,
        }

    # Section 62: Release from customs (always relevant)
    art62 = get_ordinance_article("62")
    if art62:
        articles["release_62"] = {
            "article": "62",
            "title_he": art62.get("t", ""),
            "summary": art62.get("s", ""),
        }

    # Sections 200א-200יד: Intellectual property (check if relevant)
    if _is_ip_relevant(item_result):
        ip_articles = {}
        for art_id in _IP_ARTICLES:
            art = get_ordinance_article(art_id)
            if art:
                ip_articles[art_id] = {
                    "article": art_id,
                    "title_he": art.get("t", ""),
                    "summary": art.get("s", ""),
                }
        if ip_articles:
            articles["ip_200"] = ip_articles

    return articles


def _is_ip_relevant(item_result):
    """Check if IP provisions (200א-200יד) are relevant for this item.

    IP articles apply to branded goods, electronics, fashion, pharmaceuticals.
    """
    hs_code = str(item_result.get("hs_code", "")).replace(".", "").replace("/", "")
    chapter = hs_code[:2].zfill(2) if len(hs_code) >= 2 else ""
    desc = (item_result.get("description", "") or "").lower()

    # Chapters with high IP risk
    ip_chapters = {"30", "33", "42", "61", "62", "64", "71", "84", "85", "90", "91"}
    if chapter in ip_chapters:
        return True

    # Keywords suggesting branded goods
    ip_keywords = {"brand", "trademark", "patent", "מותג", "סימן מסחרי", "פטנט"}
    return any(kw in desc for kw in ip_keywords)


def _lookup_fta_for_item(db, hs_code, origin_country):
    """Look up FTA eligibility for HS code + origin country.

    Returns structured FTA result with:
    - Which צו מסגרת supplement applies
    - Rules of origin requirements
    - Which preference document needed (EUR.1, invoice declaration, etc.)
    """
    origin_lower = origin_country.lower().strip()
    fta_code = _FTA_COUNTRY_MAP.get(origin_lower)
    if not fta_code:
        return None

    # Query intelligence.lookup_fta for base eligibility
    try:
        try:
            from lib.intelligence import lookup_fta
        except ImportError:
            from intelligence import lookup_fta
        base_fta = lookup_fta(db, hs_code, origin_country)
    except Exception:
        base_fta = {"eligible": False}

    # Enrich with framework order supplement data
    fw_clause = _lookup_framework_order_fta(db, fta_code)

    result = {
        "eligible": base_fta.get("eligible", False),
        "agreement_name": base_fta.get("agreement_name", ""),
        "agreement_name_he": base_fta.get("agreement_name_he", ""),
        "preferential_rate": base_fta.get("preferential_rate", ""),
        "origin_proof": base_fta.get("origin_proof", ""),
        "origin_proof_alt": base_fta.get("origin_proof_alt", ""),
        "cumulation": base_fta.get("cumulation", ""),
        "legal_basis": base_fta.get("legal_basis", ""),
    }

    if fw_clause:
        result["framework_order"] = {
            "supplements": fw_clause.get("supplements", []),
            "country_he": fw_clause.get("country_he", ""),
            "is_duty_free": fw_clause.get("is_duty_free", False),
            "has_reduction": fw_clause.get("has_reduction", False),
            "rules_of_origin": _determine_origin_rules(fta_code),
            "preference_document": _determine_preference_doc(fta_code),
        }

    return result


def _lookup_framework_order_fta(db, fta_code):
    """Look up FTA clause from framework_order collection."""
    doc_id = f"fta_{fta_code}"
    try:
        doc = db.collection("framework_order").document(doc_id).get()
        if doc.exists:
            return doc.to_dict()
    except Exception:
        pass
    return None


def _determine_origin_rules(fta_code):
    """Determine rules of origin type for the FTA agreement."""
    # Each FTA has specific origin protocol
    _ORIGIN_RULES = {
        "eu": {"protocol": "Protocol 4", "type": "cumulation_diagonal",
               "min_local_content": "varies by product"},
        "uk": {"protocol": "Annex on Rules of Origin", "type": "cumulation_bilateral",
               "min_local_content": "varies by product"},
        "usa": {"protocol": "Rules of Origin Annex", "type": "substantial_transformation",
                "min_local_content": "35%"},
        "efta": {"protocol": "Protocol B", "type": "cumulation_diagonal",
                 "min_local_content": "varies by product"},
        "turkey": {"protocol": "Protocol 3", "type": "cumulation_diagonal",
                   "min_local_content": "varies by product"},
        "canada": {"protocol": "Rules of Origin Chapter", "type": "tariff_shift",
                   "min_local_content": "varies by product"},
        "korea": {"protocol": "Origin Protocol", "type": "tariff_shift_or_value_added",
                  "min_local_content": "varies by product"},
        "jordan": {"protocol": "Protocol on Rules of Origin", "type": "cumulation_bilateral",
                   "min_local_content": "varies by product"},
        "mercosur": {"protocol": "Origin Annex", "type": "cumulation",
                     "min_local_content": "varies by product"},
        "vietnam": {"protocol": "Rules of Origin Chapter", "type": "tariff_shift",
                    "min_local_content": "varies by product"},
        "uae": {"protocol": "Rules of Origin Chapter", "type": "value_added",
                "min_local_content": "40%"},
        "ukraine": {"protocol": "Protocol on Rules of Origin", "type": "cumulation_diagonal",
                    "min_local_content": "varies by product"},
    }
    return _ORIGIN_RULES.get(fta_code, {
        "protocol": "See agreement text",
        "type": "unknown",
        "min_local_content": "check agreement",
    })


def _determine_preference_doc(fta_code):
    """Determine which preference document is required for FTA."""
    _PREF_DOCS = {
        "eu": {"primary": "EUR.1", "alternative": "Invoice declaration (approved exporter)",
               "threshold": "$6,000 (invoice declaration without approval)"},
        "uk": {"primary": "EUR.1", "alternative": "Invoice declaration",
               "threshold": "$6,000"},
        "usa": {"primary": "Certificate of Origin (form A)", "alternative": None,
                "threshold": None},
        "efta": {"primary": "EUR.1", "alternative": "Invoice declaration",
                 "threshold": "$6,000"},
        "turkey": {"primary": "EUR.1 / A.TR", "alternative": "Invoice declaration",
                   "threshold": "$6,000"},
        "canada": {"primary": "Certificate of Origin", "alternative": None,
                   "threshold": None},
        "korea": {"primary": "Certificate of Origin", "alternative": "Self-certification",
                  "threshold": None},
        "jordan": {"primary": "EUR.1", "alternative": "Invoice declaration",
                   "threshold": "$6,000"},
        "mercosur": {"primary": "Certificate of Origin", "alternative": None,
                     "threshold": None},
        "vietnam": {"primary": "Certificate of Origin (form VC)", "alternative": None,
                    "threshold": None},
        "uae": {"primary": "Certificate of Origin", "alternative": "Invoice declaration",
                "threshold": "$10,000"},
        "ukraine": {"primary": "EUR.1", "alternative": "Invoice declaration",
                    "threshold": "$6,000"},
    }
    return _PREF_DOCS.get(fta_code, {
        "primary": "Certificate of Origin",
        "alternative": None,
        "threshold": None,
    })


# ---------------------------------------------------------------------------
#  PHASE 9: Verification loop
# ---------------------------------------------------------------------------

def verify_and_loop(result, item, operation_context, db, max_loops=3):
    """Self-verification loop. Re-runs classification if errors found.

    6 checks per iteration:
    1. HS code exists in tariff DB
    2. Chapter notes don't exclude this item
    3. No more specific heading was missed
    4. Chapter 98 eligibility matches person type
    5. Discount code exists (if applicable)
    6. Cross-ref with classification directives

    After max_loops failures -> kram with specific questions.
    """
    if not result:
        return _generate_kram_result(None, ["No classification result"], item)

    for iteration in range(max_loops):
        errors = _run_verification_checks(result, item, operation_context, db)

        if not errors:
            result["verified"] = True
            result["verification_iterations"] = iteration + 1
            return result

        print(f"    Verification loop {iteration + 1}/{max_loops}: "
              f"{len(errors)} errors — {[e['check'] for e in errors]}")

        # Try to fix by reclassifying with constraints
        result = _reclassify_with_constraints(item, operation_context, db, errors, result)
        if not result:
            return _generate_kram_result(None, errors, item)

    # max_loops exhausted -> kram
    return _generate_kram_result(result, errors, item)


def _run_verification_checks(result, item, operation_context, db):
    """Run all 6 verification checks. Returns list of error dicts."""
    errors = []
    hs_code = result.get("hs_code", "")
    hs_clean = hs_code.replace(".", "").replace("/", "").replace(" ", "")
    chapter = hs_clean[:2].zfill(2) if len(hs_clean) >= 2 else ""

    # CHECK 1: HS code exists in tariff DB
    if hs_clean and len(hs_clean) >= 4:
        try:
            doc = db.collection("tariff").document(hs_clean[:10]).get()
            if not doc.exists:
                # Try without padding
                doc = db.collection("tariff").document(hs_clean).get()
            if not doc.exists:
                errors.append({
                    "check": "hs_exists",
                    "message": f"HS code {hs_code} not found in tariff database",
                    "severity": "critical",
                })
        except Exception:
            pass  # Firestore error — skip check, don't block

    # CHECK 2: Chapter notes don't exclude this item
    if chapter:
        try:
            notes_doc = db.collection("chapter_notes").document(f"chapter_{chapter}").get()
            if notes_doc.exists:
                notes_data = notes_doc.to_dict()
                exclusions = notes_data.get("exclusions", [])
                item_desc = (item.get("name", "") + " " +
                             item.get("physical", "") + " " +
                             item.get("essence", "")).lower()
                for excl in exclusions:
                    excl_lower = excl.lower()
                    # Check if exclusion text matches item description
                    excl_words = set(re.findall(r'\w{3,}', excl_lower))
                    item_words = set(re.findall(r'\w{3,}', item_desc))
                    overlap = excl_words & item_words
                    if len(overlap) >= 2:
                        errors.append({
                            "check": "chapter_exclusion",
                            "message": f"Chapter {chapter} exclusion may apply: {excl[:100]}",
                            "severity": "warning",
                            "exclusion_text": excl,
                        })
                        break
        except Exception:
            pass

    # CHECK 3: No more specific heading missed
    if hs_clean and len(hs_clean) >= 4:
        heading = hs_clean[:4]
        try:
            # Look for more specific subheadings in same heading
            siblings = db.collection("tariff").where(
                "__name__", ">=", heading
            ).where(
                "__name__", "<", heading + "\uf8ff"
            ).limit(10).stream()

            item_desc_lower = item.get("name", "").lower()
            for sib in siblings:
                sib_data = sib.to_dict()
                sib_desc = (sib_data.get("description_he", "") + " " +
                            sib_data.get("description_en", "")).lower()
                sib_id = sib.id
                if sib_id != hs_clean and sib_id != hs_clean[:10]:
                    # Check if sibling description is more specific match
                    item_words = set(re.findall(r'\w{3,}', item_desc_lower))
                    sib_words = set(re.findall(r'\w{3,}', sib_desc))
                    current_desc = (result.get("description", "") or "").lower()
                    current_words = set(re.findall(r'\w{3,}', current_desc))

                    sib_overlap = len(item_words & sib_words)
                    current_overlap = len(item_words & current_words)

                    if sib_overlap > current_overlap + 1:
                        errors.append({
                            "check": "more_specific",
                            "message": f"More specific heading {sib_id} may apply",
                            "severity": "warning",
                            "alternative_code": sib_id,
                        })
                        break
        except Exception:
            pass

    # CHECK 4: Chapter 98 eligibility
    legal_category = operation_context.get("legal_category", "")
    if legal_category and result.get("chapter98_code"):
        ch98 = result["chapter98_code"]
        ch98_entry = get_chapter98_entry(ch98)
        if ch98_entry:
            # Verify the item's regular chapter is in the Ch98 mapping
            regular_chapters = ch98_entry.get("regular_chapters", [])
            if regular_chapters:
                item_chapter = int(chapter) if chapter.isdigit() else 0
                if item_chapter and item_chapter not in regular_chapters:
                    errors.append({
                        "check": "chapter98_mismatch",
                        "message": (f"Chapter 98 code {ch98} covers chapters "
                                    f"{regular_chapters}, but item is chapter {chapter}"),
                        "severity": "warning",
                    })

    # CHECK 5: Discount code exists (if applicable)
    if legal_category and result.get("discount"):
        disc = result["discount"]
        sub_code = disc.get("discount_sub_code", "")
        if sub_code:
            sc = get_sub_code("7", sub_code)
            if not sc:
                errors.append({
                    "check": "discount_code_missing",
                    "message": f"Discount sub-code 7/{sub_code} not found",
                    "severity": "warning",
                })

    # CHECK 6: Classification directives cross-reference
    if chapter:
        try:
            directives = db.collection("classification_directives").where(
                "primary_hs_code_prefix", "==", chapter
            ).limit(5).stream()
            for d in directives:
                d_data = d.to_dict()
                d_title = d_data.get("title", "").lower()
                item_desc_lower = item.get("name", "").lower()
                if any(w in d_title for w in item_desc_lower.split() if len(w) >= 3):
                    # Directive may be relevant — check if it contradicts
                    d_hs = d_data.get("primary_hs_code", "")
                    if d_hs and d_hs != hs_clean[:len(d_hs)]:
                        errors.append({
                            "check": "directive_conflict",
                            "message": (f"Classification directive suggests {d_hs}: "
                                        f"{d_data.get('title', '')[:80]}"),
                            "severity": "info",
                            "directive_id": d_data.get("directive_id", d.id),
                        })
                        break
        except Exception:
            pass

    return errors


def _reclassify_with_constraints(item, operation_context, db, errors, prev_result):
    """Re-run classification with knowledge from verification errors.

    Modifies the item description to include constraints from errors,
    then re-runs the classification pipeline.
    """
    _ensure_elimination()

    # Build constraint text from errors
    constraints = []
    excluded_codes = set()

    for err in errors:
        check = err.get("check", "")
        if check == "hs_exists":
            # Current code doesn't exist — exclude it
            excluded_codes.add(prev_result.get("hs_code", "").replace(".", "").replace("/", ""))
        elif check == "chapter_exclusion":
            constraints.append(f"NOT chapter {prev_result.get('hs_code', '')[:2]}")
        elif check == "more_specific":
            alt = err.get("alternative_code", "")
            if alt:
                constraints.append(f"Consider {alt}")
        elif check == "directive_conflict":
            alt = err.get("directive_id", "")
            if alt:
                constraints.append(f"Check directive {alt}")

    # Re-run pre_classify with augmented description
    augmented_desc = item.get("name", "")
    if constraints:
        augmented_desc = f"{augmented_desc} [{'; '.join(constraints)}]"

    pre_result = _build_candidates_for_item(
        {**item, "name": augmented_desc}, db,
    )
    if not pre_result or not pre_result.get("candidates"):
        return None

    candidates = _candidates_from_pre_classify(pre_result)

    # Remove excluded codes
    if excluded_codes:
        candidates = [
            c for c in candidates
            if c.get("hs_code", "").replace(".", "").replace("/", "") not in excluded_codes
        ]
        if not candidates:
            return None

    product_info = _make_product_info({
        "description": item.get("name", ""),
        "material": item.get("physical", ""),
        "use": item.get("function", ""),
        "origin_country": operation_context.get("origin_country", ""),
    })

    elim_result = _eliminate(db, product_info, candidates)
    survivors = elim_result.get("survivors", [])
    if not survivors:
        return None

    best = max(survivors, key=lambda s: s.get("confidence", 0))
    return {
        "hs_code": best.get("hs_code", ""),
        "confidence": best.get("confidence", 0.5),
        "description": best.get("description", best.get("description_en", "")),
        "duty_rate": best.get("duty_rate", ""),
        "elimination_result": elim_result,
        "source": "reclassification",
        "reclassification_reason": [e.get("check", "") for e in errors],
    }


def _generate_kram_result(result, errors, item):
    """Generate clarification questions when verification fails 3x.

    Returns a kram (קר"מ = קריאה למידע מפורט) result with specific
    questions derived from the failed checks.
    """
    questions = _generate_clarification_questions(errors, item, result)

    return {
        "status": "kram",
        "hs_code": result.get("hs_code", "") if result else "",
        "confidence": 0.0,
        "verified": False,
        "kram_questions": questions,
        "failed_checks": errors if isinstance(errors, list) else [str(errors)],
        "source": "verification_exhausted",
    }


def _generate_clarification_questions(errors, item, result):
    """Generate specific clarification questions from verification errors.

    Not generic "need more info" — each question targets a specific ambiguity.
    """
    questions = []
    seen_types = set()

    if not isinstance(errors, list):
        errors = []

    for err in errors:
        check = err.get("check", "")
        if check in seen_types:
            continue
        seen_types.add(check)

        if check == "hs_exists":
            questions.append({
                "question_he": "מהו התיאור המדויק של הטובין? (חומר, צורה, שימוש)",
                "question_en": "What is the exact product description? (material, form, use)",
                "reason": "HS code not found in tariff database",
            })
        elif check == "chapter_exclusion":
            excl = err.get("exclusion_text", "")
            questions.append({
                "question_he": f"האם הפריט עומד בהגדרת ההחרגה: {excl[:80]}?",
                "question_en": f"Does the item fall under exclusion: {excl[:80]}?",
                "reason": "Chapter note exclusion may apply",
            })
        elif check == "more_specific":
            alt = err.get("alternative_code", "")
            questions.append({
                "question_he": f"האם הפריט שייך לפרט {alt} (יותר ספציפי)?",
                "question_en": f"Does the item belong to subheading {alt} (more specific)?",
                "reason": "More specific heading may apply",
            })
        elif check == "chapter98_mismatch":
            questions.append({
                "question_he": "מהו סוג הפריט לצורך פרק 98 (שימוש אישי)?",
                "question_en": "What type of item is this for Chapter 98 (personal use)?",
                "reason": "Chapter 98 code mismatch with regular chapter",
            })
        elif check == "directive_conflict":
            questions.append({
                "question_he": "האם קיימת הנחיית סיווג רלוונטית? נא לפרט.",
                "question_en": "Is there a relevant classification directive? Please specify.",
                "reason": "Classification directive suggests different code",
            })

    # Always add a catch-all if no specific questions generated
    if not questions:
        questions.append({
            "question_he": "נא לתאר את הפריט: חומר, צורה פיזית, שימוש עיקרי",
            "question_en": "Please describe the item: material, physical form, primary use",
            "reason": "Insufficient information for definitive classification",
        })

    return questions


# ---------------------------------------------------------------------------
#  MASTER ORCHESTRATOR
# ---------------------------------------------------------------------------

def process_case(email_text, attachments_text, db, get_secret_func):
    """Main entry point. Classify all items in an email deterministically.

    Phases:
        0: analyze_case() — operation type, legal category, items
        1: _identify_items_with_ai() — ONE AI call for physical/essence/function
        2: _check_spare_part() — parent machine chapter check
        3-6: eliminate() per item — GIR 1-6 deterministic
        7: Chapter 98 mapping — personal import codes
        8: _post_classification_cascade() — FIO + FTA + discount + valuation
        9: verify_and_loop() — 3-iteration self-check

    Returns:
        dict with: status, operation, items[], ordinance_articles,
        valuation, release_notes, verification_log
    """
    if not email_text and not attachments_text:
        return None

    text = f"{email_text or ''}\n{attachments_text or ''}"

    # PHASE 0: Analyze case
    case_plan = analyze_case("", text)
    if not case_plan.items_to_classify:
        return {
            "status": "no_items",
            "operation": case_plan.to_dict(),
            "items": [],
            "kram_questions": [{
                "question_he": "לא זיהיתי פריטים לסיווג. מה הטובין שברצונך לסווג?",
                "question_en": "No items detected. What goods would you like to classify?",
            }],
        }

    operation_context = {
        "direction": case_plan.direction,
        "legal_category": case_plan.legal_category,
        "legal_category_he": case_plan.legal_category_he,
        "origin_country": case_plan.origin_country,
        "discount_group": case_plan.discount_group,
        "discount_sub_range": case_plan.discount_sub_range,
        "case_type": case_plan.case_type,
        "special_flags": case_plan.special_flags,
    }

    # PHASE 1: Identify items with AI (ONE call)
    items = _identify_items_with_ai(case_plan.items_to_classify, get_secret_func)

    # Process each item
    classified_items = []
    verification_log = []

    for item in items:
        # PHASE 2: Spare part check
        spare_chapter = _check_spare_part(item, text, db)

        # PHASES 3-6: Classify via elimination engine
        result = classify_single_item(item, operation_context, db,
                                      spare_chapter=spare_chapter)

        if not result:
            classified_items.append({
                "item": item,
                "status": "kram",
                "kram_questions": [{
                    "question_he": f"לא מצאתי סיווג עבור: {item.get('name', '')}. נא לתאר בפירוט.",
                    "question_en": f"No classification found for: {item.get('name', '')}. Please describe in detail.",
                }],
            })
            continue

        # PHASE 7: Chapter 98 mapping
        _apply_chapter98(result, item, case_plan.legal_category,
                         item_category=item.get("category", ""))

        # PHASE 8: Post-classification cascade
        _post_classification_cascade(result, item, operation_context, db)

        # PHASE 9: Verification loop
        verified = verify_and_loop(result, item, operation_context, db)
        verification_log.append({
            "item": item.get("name", ""),
            "hs_code": verified.get("hs_code", ""),
            "verified": verified.get("verified", False),
            "iterations": verified.get("verification_iterations", 0),
            "status": verified.get("status", "classified"),
        })

        classified_items.append({
            "item": item,
            "classification": verified,
            "status": verified.get("status", "classified"),
        })

    # Collect global ordinance articles
    global_articles = _collect_ordinance_articles(operation_context, {})

    return {
        "status": "completed" if any(
            ci.get("status") == "classified" or ci.get("classification", {}).get("verified")
            for ci in classified_items
        ) else "kram",
        "operation": operation_context,
        "case_plan": case_plan.to_dict(),
        "items": classified_items,
        "ordinance_articles": global_articles,
        "valuation": _build_valuation_summary(operation_context),
        "release_notes": _build_release_notes(operation_context),
        "verification_log": verification_log,
        "vat_rate": ISRAEL_VAT_RATE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _build_valuation_summary(operation_context):
    """Build customs valuation summary from ordinance articles."""
    if operation_context.get("direction") != "import":
        return {}

    methods = get_valuation_methods()
    art132 = get_ordinance_article("132")

    return {
        "primary_method": "transaction_value",
        "primary_article": "132",
        "primary_desc_he": art132.get("t", "") if art132 else "ערך עסקה",
        "methods_count": len(methods) if methods else 7,
        "legal_hierarchy": [
            {"method": "transaction_value", "article": "132",
             "desc_he": "ערך עסקה - המחיר ששולם או שישולם בפועל"},
            {"method": "identical_goods", "article": "133",
             "desc_he": "ערך עסקה של טובין זהים"},
            {"method": "similar_goods", "article": "133",
             "desc_he": "ערך עסקה של טובין דומים"},
            {"method": "deductive", "article": "133א",
             "desc_he": "שיטה ניכויית"},
            {"method": "computed", "article": "133א",
             "desc_he": "שיטה מחושבת"},
            {"method": "fallback", "article": "133א",
             "desc_he": "שיטת שווי חלופי"},
        ],
    }


def _build_release_notes(operation_context):
    """Build release procedure notes."""
    notes = []
    art62 = get_ordinance_article("62")
    if art62:
        notes.append({
            "article": "62",
            "title_he": art62.get("t", ""),
            "summary": art62.get("s", ""),
        })

    if operation_context.get("legal_category"):
        art129 = get_ordinance_article("129")
        if art129:
            notes.append({
                "article": "129",
                "title_he": art129.get("t", ""),
                "summary": art129.get("s", ""),
                "applies_because": operation_context.get("legal_category_he", ""),
            })

    return notes
