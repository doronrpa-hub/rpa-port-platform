"""Broker Engine — Deterministic customs classification engine.

AI is called ONCE (Phase 1 item identification). Everything after is
deterministic Python: GIR 1-6 elimination, Chapter 98 mapping, discount codes,
FIO/FEO regulatory, FTA preferences, customs valuation articles.

Usage:
    from lib.broker_engine import process_case, classify_single_item, verify_and_loop

Session 90 — broker_engine.py
"""

import os
import re
import requests
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
    from lib._external_tariff_search import external_tariff_search
    _EXTERNAL_SEARCH_AVAILABLE = True
except ImportError:
    try:
        from _external_tariff_search import external_tariff_search
        _EXTERNAL_SEARCH_AVAILABLE = True
    except ImportError:
        _EXTERNAL_SEARCH_AVAILABLE = False

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

try:
    from lib.librarian import get_israeli_hs_format
except ImportError:
    from librarian import get_israeli_hs_format


def _enforce_hs_format(raw_code):
    """Always returns XX.XX.XXXXXX/X — enforced at output boundary.

    Every HS code leaving classify_single_item() passes through here.
    This is the single enforcement point for the Israeli canonical format.
    """
    if not raw_code:
        return ""
    return get_israeli_hs_format(raw_code)


# Customs vocabulary — for extracting products from conversational text
_CUSTOMS_VOCABULARY = None

def _ensure_vocabulary():
    global _CUSTOMS_VOCABULARY
    if _CUSTOMS_VOCABULARY is not None:
        return
    try:
        from lib._customs_vocabulary import CUSTOMS_VOCABULARY
        _CUSTOMS_VOCABULARY = CUSTOMS_VOCABULARY
    except ImportError:
        try:
            from _customs_vocabulary import CUSTOMS_VOCABULARY
            _CUSTOMS_VOCABULARY = CUSTOMS_VOCABULARY
        except ImportError:
            _CUSTOMS_VOCABULARY = False  # mark as unavailable


# Hebrew prefixes to strip when matching vocabulary
_HE_PREFIXES = ("וה", "של", "מה", "לה", "בה", "כש", "מ", "ב", "ל", "ה", "ו", "כ", "ש")

# Stop words to skip during vocabulary extraction — common Hebrew verbs,
# adjectives, pronouns, and adverbs that are NOT product nouns
_VOCAB_STOP = frozenset({
    # Hebrew function words / pronouns
    "יש", "לי", "את", "של", "על", "עם", "או", "גם", "כי", "אם", "לא", "זה",
    "מה", "הם", "הוא", "היא", "כל", "אני", "אנחנו", "רוצה", "צריך", "שרוצה",
    "שצריך", "לייבא", "לייצא", "ליבא", "ליצא", "יבוא", "יצוא", "לסווג",
    "סיווג", "פרט", "המכס", "מכס", "טובין", "שברצונך", "ברצונך",
    # Hebrew verbs / tenses that slip through vocabulary as false positives
    "יהיו", "יהיה", "היה", "היתה", "היו", "הייתי", "נהיה", "להיות",
    "עושה", "עשיתי", "עושים", "לעשות", "צריכים", "רוצים", "יכול", "יכולה",
    "אפשר", "נראה", "חושב", "חושבת", "יודע", "יודעת", "מבקש", "מבקשת",
    "שולח", "שולחת", "מצורף", "מצורפת", "מצורפים", "נא", "בבקשה",
    # Hebrew adjectives / descriptors that are NOT product names
    "פרטי", "פרטית", "מיוחד", "מיוחדת", "חדש", "חדשה", "ישן", "ישנה",
    "גדול", "גדולה", "קטן", "קטנה", "טוב", "טובה", "רע", "רעה",
    "ראשון", "שני", "שלישי", "אחר", "אחרת", "אחרים", "שונה", "שונים",
    "ישראל", "ישראלי", "ישראלית", "בינלאומי", "בינלאומית",
    # Hebrew nouns that are NOT products
    "דבר", "דברים", "עניין", "נושא", "שאלה", "תשובה", "בקשה", "הזמנה",
    "חברה", "לקוח", "ספק", "משלוח", "עסקה", "מסמך", "מסמכים", "קובץ",
    "תודה", "שלום", "בוקר", "ערב", "יום", "חודש", "שנה",
    # English stop words
    "the", "a", "an", "of", "for", "and", "or", "with", "to", "from", "is",
    "in", "on", "by", "what", "how", "need", "want", "import", "export",
    "classify", "tariff", "customs", "code", "attached", "please", "hello",
    "thank", "thanks", "would", "like", "about", "this", "that", "which",
    "special", "private", "new", "old", "good", "bad", "first", "second",
})

_EXTRACT_PRODUCT_PROMPT = """Extract the product name from this email.
The user is asking about customs classification (HS code / tariff heading).
Return ONLY the product name — no explanation, no quotes, no punctuation.
If you cannot identify a product, return exactly: NONE

Examples:
- "יש לי לקוח שרוצה לייבא פילטרים. מה פרט המכס?" → פילטרים
- "מה הסיווג של ספות מרופדות?" → ספות מרופדות
- "classify steel pipes for construction" → steel pipes for construction
- "שלום, מה שלומך?" → NONE"""


def _extract_product_from_question(text, api_key=None):
    """Extract product name from conversational email using AI."""
    if not api_key or not text:
        return None
    body = re.sub(r'<[^>]+>', ' ', text).strip()
    if len(body) < 5:
        return None
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key.strip(),
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 100,
                "messages": [{"role": "user",
                              "content": f"{_EXTRACT_PRODUCT_PROMPT}\n\nEmail:\n{body[:500]}"}],
            },
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"    [broker] product extraction API {resp.status_code}")
            return None
        result = resp.json().get("content", [{}])[0].get("text", "").strip()
        if not result or result == "NONE" or len(result) < 2:
            return None
        print(f"    [broker] AI extracted product: '{result}'")
        return result
    except Exception as e:
        print(f"    [broker] product extraction error: {e}")
        return None


def _extract_products_from_vocab(text):
    """Extract product terms from text using customs vocabulary.

    Used as fallback when analyze_case() finds 0 items (conversational text).
    Returns list of dicts: [{name, keywords, chapters}]
    """
    _ensure_vocabulary()
    if not _CUSTOMS_VOCABULARY or _CUSTOMS_VOCABULARY is False:
        return []

    text_lower = text.lower().strip()
    words = re.split(r'[\s,.\n;:!?()]+', text_lower)
    words = [w for w in words if len(w) >= 2 and w not in _VOCAB_STOP]

    found = []
    seen_chapters = set()

    # Check multi-word phrases first (longer = more specific)
    for phrase_len in range(min(len(words), 4), 0, -1):
        for i in range(len(words) - phrase_len + 1):
            phrase = " ".join(words[i:i + phrase_len])
            if phrase in _CUSTOMS_VOCABULARY:
                entry = _CUSTOMS_VOCABULARY[phrase]
                chapters = tuple(sorted(entry.get("chapters", [])))
                if chapters and chapters not in seen_chapters:
                    seen_chapters.add(chapters)
                    official = entry.get("official", phrase)
                    found.append({
                        "name": official,
                        "keywords": [phrase] + ([entry["official_en"]] if entry.get("official_en") else []),
                        "chapters": list(chapters),
                        "confidence": entry.get("confidence", "MEDIUM"),
                    })

    # Also check individual words with Hebrew prefix stripping
    for word in words:
        variants = [word]
        if len(word) > 3:
            for pfx in _HE_PREFIXES:
                if word.startswith(pfx) and len(word) - len(pfx) >= 2:
                    stripped = word[len(pfx):]
                    if stripped not in variants:
                        variants.append(stripped)
        for variant in variants:
            if variant in _CUSTOMS_VOCABULARY:
                entry = _CUSTOMS_VOCABULARY[variant]
                chapters = tuple(sorted(entry.get("chapters", [])))
                if chapters and chapters not in seen_chapters:
                    seen_chapters.add(chapters)
                    official = entry.get("official", variant)
                    found.append({
                        "name": official,
                        "keywords": [variant] + ([entry["official_en"]] if entry.get("official_en") else []),
                        "chapters": list(chapters),
                        "confidence": entry.get("confidence", "MEDIUM"),
                    })
                break  # First variant match wins

    # Sort: HIGH confidence first, multi-word phrases first
    found.sort(key=lambda x: (0 if x["confidence"] == "HIGH" else 1, -len(x["name"])))
    return found[:5]  # Cap at 5 products


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


# Unified index (instant in-memory search — replaces slow Firestore scan)
_unified_search = None
_UNIFIED_AVAILABLE = False


def _ensure_unified():
    global _unified_search, _UNIFIED_AVAILABLE
    if _unified_search is not None:
        return
    try:
        try:
            from lib._unified_search import find_tariff_codes, get_heading_subcodes, index_loaded
        except ImportError:
            from _unified_search import find_tariff_codes, get_heading_subcodes, index_loaded
        if index_loaded():
            _unified_search = {"find": find_tariff_codes, "subcodes": get_heading_subcodes}
            _UNIFIED_AVAILABLE = True
            print("    Unified index: loaded")
        else:
            _unified_search = {}
            print("    Unified index: no data (run build_unified_index.py)")
    except Exception as e:
        _unified_search = {}
        print(f"    Unified index: not available ({e})")


# Stage 1-3 reasoning pipeline (Session 110) — parallel identification + screening
_STAGES_AVAILABLE = False
_identify_product = None
_screen_candidates = None
_process_conversation_turn = None


def _ensure_stages():
    global _STAGES_AVAILABLE, _identify_product, _screen_candidates, _process_conversation_turn
    if _identify_product is not None:
        return
    try:
        try:
            from lib.classification_identifier import identify_product
            from lib.classification_screener import screen_candidates
            from lib.classification_conversation import process_conversation_turn
        except ImportError:
            from classification_identifier import identify_product
            from classification_screener import screen_candidates
            from classification_conversation import process_conversation_turn
        _identify_product = identify_product
        _screen_candidates = screen_candidates
        _process_conversation_turn = process_conversation_turn
        _STAGES_AVAILABLE = True
        print("    Stages 1-3: loaded")
    except ImportError as e:
        _identify_product = False  # sentinel: attempted but failed
        _STAGES_AVAILABLE = False
        print(f"    Stages 1-3: not available ({e})")


# Attribute keys to extract from item dict for Stage 2 screening
_SCREEN_ATTR_KEYS = frozenset({
    "physical", "essence", "function", "material", "weight",
    "dimensions", "frequency", "power", "voltage", "capacity",
    "category", "processing_state", "transformation_stage",
})


# Chapter decision trees (Session 98) — deterministic chapter routing
_chapter_decision_trees = None


def _ensure_decision_trees():
    global _chapter_decision_trees
    if _chapter_decision_trees is not None:
        return
    try:
        try:
            from lib._chapter_decision_trees import decide_chapter
        except ImportError:
            from _chapter_decision_trees import decide_chapter
        _chapter_decision_trees = decide_chapter
    except Exception:
        _chapter_decision_trees = False  # Mark as attempted but unavailable


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
# Session 98 — deepened prompt extracts 6 classification attributes needed by
# chapter decision trees and elimination engine.
_ITEM_ID_SYSTEM = """\
You are an Israeli customs broker (עמיל מכס) performing Phase 1 examination per \
נוהל סיווג טובין #3. For each item, determine SIX classification attributes. \
These feed directly into the tariff tree — accuracy here prevents misclassification.

Return a JSON array. Each element MUST have these fields:
{
  "name": "original item name as given",
  "physical": "dominant material(s) with estimated % if composite. Include form: \
solid/liquid/powder/paste/fiber/sheet/whole/fillet/peeled/assembled etc.",
  "essence": "what IS this product fundamentally — not brand, not marketing. \
Example: 'pneumatic rubber tire for passenger vehicle' not 'Michelin Primacy'",
  "function": "primary end-use or destination function",
  "transformation_stage": ONE of: "raw", "semi_processed", "processed", "prepared", \
"finished", "specialized".
    raw = natural state (live animal, crude ore, raw cotton).
    semi_processed = cleaned/cut/basic treatment (sawn wood, tanned leather, flour).
    processed = significant transformation (steel sheet, woven fabric, refined oil).
    prepared = food cooked/seasoned/preserved beyond basic (canned fish, sauces).
    finished = ready-to-use end product (tire, garment, furniture).
    specialized = professional/industrial/medical/military equipment.
  "processing_state": ONE of: "live", "fresh", "chilled", "frozen", "dried", \
"smoked", "salted", "cooked", "preserved", "compound", "fermented", "not_applicable".
    live = living organism.
    fresh = recently harvested, no preservation.
    chilled = cooled 0-4°C.
    frozen = below freezing.
    dried = moisture removed.
    smoked = smoke-cured.
    salted = salt-preserved or brined.
    cooked = heat-treated only (boiled/steamed/fried) — NO added ingredients.
    preserved = canned, vacuum-packed, chemically preserved.
    compound = MIXED with other ingredients: breaded, sauced, marinated, coated, stuffed.
    fermented = fermentation-processed (cheese, wine, vinegar).
    not_applicable = non-food/non-biological items.
  "dominant_material_pct": integer 0-100 or null if single-material or not relevant.
}

CRITICAL:
- "compound" = combined with OTHER ingredients. Breaded fish = compound. Plain frozen fish = frozen.
- Fish FILLET vs WHOLE: state this in "physical" — it changes the heading.
- For composites, dominant_material_pct determines essential character (GIR 3ב).

Example: [{"name":"חסילון קפוא מקולף","physical":"crustacean meat 100%, peeled tail meat",\
"essence":"langoustine meat, shell removed","function":"human consumption",\
"transformation_stage":"semi_processed","processing_state":"frozen",\
"dominant_material_pct":100}]"""

_ITEM_ID_USER = """\
Items to analyze:
{items_list}

Return ONLY a JSON array with the fields: name, physical, essence, function, \
transformation_stage, processing_state, dominant_material_pct."""


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
        # Merge AI analysis back into items — both legacy + new Layer 0 fields
        for i, item in enumerate(items):
            if i < len(ai_result):
                ai_item = ai_result[i] if isinstance(ai_result[i], dict) else {}
                item["physical"] = ai_item.get("physical", "")
                item["essence"] = ai_item.get("essence", "")
                item["function"] = ai_item.get("function", "")
                # New Layer 0 fields (Session 98)
                item["transformation_stage"] = ai_item.get("transformation_stage", "")
                item["processing_state"] = ai_item.get("processing_state", "")
                item["dominant_material_pct"] = ai_item.get("dominant_material_pct")
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
            text = call_gemini(gk, _ITEM_ID_SYSTEM, prompt_user, max_tokens=2000)
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
            text = call_chatgpt(ok, _ITEM_ID_SYSTEM, prompt_user, max_tokens=2000)
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
    # Each entry: (physical, essence, function, transformation_stage, processing_state)
    _MATERIAL_MAP = {
        "furniture": ("wood, fabric, foam", "seating/storage furniture", "household use", "finished", "not_applicable"),
        "electronics": ("plastic, metal, circuits", "electronic device", "computing/entertainment", "finished", "not_applicable"),
        "vehicle": ("steel, rubber, glass", "motor vehicle", "transportation", "finished", "not_applicable"),
        "personal": ("mixed materials", "personal belongings", "personal use", "finished", "not_applicable"),
        "kitchen": ("ceramic, metal, glass", "kitchenware", "food preparation", "finished", "not_applicable"),
        "food": ("organic matter", "food product", "consumption", "prepared", "preserved"),
        "textiles": ("fabric, cotton, polyester", "textile product", "household/clothing", "finished", "not_applicable"),
        "music": ("wood, metal, strings", "musical instrument", "music", "finished", "not_applicable"),
        "tools": ("metal, plastic, electric motor", "hand tool / power tool", "construction/repair", "finished", "not_applicable"),
        "safety": ("rubber, plastic, textile", "personal protective equipment", "safety/protection", "finished", "not_applicable"),
        "workwear": ("textile, polyester, cotton", "work clothing", "occupational use", "finished", "not_applicable"),
        "industrial": ("steel, metal, electric motor", "industrial equipment", "manufacturing/construction", "specialized", "not_applicable"),
    }
    for item in items:
        cat = item.get("category", "personal")
        phys, ess, func, t_stage, p_state = _MATERIAL_MAP.get(
            cat, ("mixed", "general goods", "general use", "finished", "not_applicable"))
        item.setdefault("physical", phys)
        item.setdefault("essence", ess)
        item.setdefault("function", func)
        item.setdefault("transformation_stage", t_stage)
        item.setdefault("processing_state", p_state)
        item.setdefault("dominant_material_pct", None)
    return items


# ---------------------------------------------------------------------------
#  FIX 3: Visit manufacturer URL from email
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
_SKIP_URL_DOMAINS = {
    "linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com",
    "youtube.com", "google.com", "mailchimp.com", "unsubscribe", "mailto:",
    "rpa-port.co.il", "outlook.com", "microsoft.com", "office.com",
}
_SPEC_WEIGHT_RE = re.compile(
    r'(?:weight|mass|משקל|net\s*weight)[:\s]*(\d+(?:[.,]\d+)?)\s*(g|kg|gram|גרם|ק"ג|oz|lb)',
    re.IGNORECASE,
)
_SPEC_DIM_RE = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*[x×X]\s*(\d+(?:[.,]\d+)?)\s*[x×X]?\s*(\d+(?:[.,]\d+)?)?\s*(mm|cm|m|inch|")',
    re.IGNORECASE,
)
_SPEC_FREQ_RE = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*(MHz|GHz|הרץ)',
    re.IGNORECASE,
)
_SPEC_POWER_RE = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*(W|watt|kW|וואט)',
    re.IGNORECASE,
)


def _extract_and_fetch_urls(text):
    """Extract product URLs from email body, fetch page, extract specs.

    Returns list of spec dicts: [{url, weight, dimensions, frequency, power, keywords}]
    """
    urls = _URL_RE.findall(text)
    if not urls:
        return []

    # Filter to product URLs
    product_urls = []
    for url in urls:
        url = url.rstrip(".,;)>]")
        domain = url.split("/")[2].lower() if len(url.split("/")) > 2 else ""
        if any(skip in domain for skip in _SKIP_URL_DOMAINS):
            continue
        product_urls.append(url)

    if not product_urls:
        return []

    specs_list = []
    for url in product_urls[:3]:  # Max 3 URLs
        try:
            import requests as req_lib
            resp = req_lib.get(url, timeout=5, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if resp.status_code != 200:
                continue
            html = resp.text[:50000]  # Limit to 50K chars

            specs = {"url": url, "keywords": []}

            # Extract weight
            wm = _SPEC_WEIGHT_RE.search(html)
            if wm:
                specs["weight"] = f"{wm.group(1)} {wm.group(2)}"

            # Extract dimensions
            dm = _SPEC_DIM_RE.search(html)
            if dm:
                parts = [dm.group(1), dm.group(2)]
                if dm.group(3):
                    parts.append(dm.group(3))
                specs["dimensions"] = f"{'x'.join(parts)} {dm.group(4)}"

            # Extract frequency
            fm = _SPEC_FREQ_RE.search(html)
            if fm:
                specs["frequency"] = f"{fm.group(1)} {fm.group(2)}"

            # Extract power
            pm = _SPEC_POWER_RE.search(html)
            if pm:
                specs["power"] = f"{pm.group(1)} {pm.group(2)}"

            # Extract product keywords from title tag
            import re as re2
            title_m = re2.search(r'<title[^>]*>(.*?)</title>', html, re2.IGNORECASE | re2.DOTALL)
            if title_m:
                title_text = title_m.group(1).strip()[:200]
                # Clean HTML entities
                title_text = title_text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                specs["title"] = title_text
                specs["keywords"] = [w for w in title_text.split() if len(w) > 2][:10]

            # Keep if has physical specs OR a meaningful title
            has_specs = any(specs.get(k) for k in ("weight", "dimensions", "frequency", "power"))
            has_title = bool(specs.get("title", "").strip())
            if has_specs or has_title:
                specs_list.append(specs)
                found = [k for k in ('weight', 'dimensions', 'frequency', 'power', 'title') if specs.get(k)]
                print(f"    URL specs from {url[:60]}: {', '.join(found)}")

        except Exception as e:
            print(f"    URL fetch failed for {url[:60]}: {e}")
            continue

    return specs_list


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

def _filter_by_vocab_chapters(candidates, vocab_chapters, item_name=""):
    """Filter candidates to vocab-identified chapters when available.

    Only filters if at least one candidate survives inside the vocab chapters.
    This prevents empty results when vocab is right about the chapter but the
    search didn't find any codes there.
    """
    if not vocab_chapters or not candidates:
        return candidates
    inside = [c for c in candidates
              if str(c.get("hs_code", "")).replace(".", "").replace("/", "")[:2]
              in vocab_chapters]
    if inside:
        dropped = len(candidates) - len(inside)
        if dropped:
            print(f"    Vocab chapter filter: kept {len(inside)}, "
                  f"dropped {dropped} outside {','.join(sorted(vocab_chapters))} "
                  f"for '{(item_name or '')[:40]}'")
        return inside
    return candidates


def _smart_tariff_search(item, db, vocab_chapters=None):
    """FIX 5: Smart search — unified index first, pre_classify fallback.

    Priority:
      1. Unified index (instant in-memory, all 11,753 tariff entries + chapter notes)
      2. pre_classify (Firestore keyword_index + tariff scan — slow fallback)

    Runs BOTH Hebrew and English searches, merges results.
    When both agree on chapter → boost confidence.

    Args:
        vocab_chapters: optional set of 2-digit chapter codes from smart_classify
                        vocabulary lookup. When provided, candidates outside these
                        chapters are filtered out (if any inside remain).
    """
    _ensure_unified()

    name_he = item.get("name", "")
    essence = item.get("essence", "")
    function = item.get("function", "")
    physical = item.get("physical", "")
    keywords = item.get("keywords", [])

    # Build search descriptions
    desc_he = name_he
    if keywords:
        desc_he = f"{desc_he} {' '.join(keywords)}"
    if physical:
        desc_he = f"{desc_he} ({physical})"

    desc_en = " ".join(filter(None, [essence, function, physical]))

    # --- Try unified index first (instant) ---
    if _UNIFIED_AVAILABLE:
        unified_candidates = _search_via_unified(desc_he, desc_en, item)
        if unified_candidates:
            unified_candidates = _filter_by_vocab_chapters(
                unified_candidates, vocab_chapters, name_he)
            print(f"    Unified index: {len(unified_candidates)} candidates for '{name_he[:40]}'")
            return {"candidates": unified_candidates}

    # --- Fallback to pre_classify (Firestore) ---
    _ensure_pre_classify()

    result_he = _pre_classify(db, desc_he)

    result_en = None
    if desc_en and desc_en.lower() != desc_he.lower():
        result_en = _pre_classify(db, desc_en)

    # Merge: combine candidates, boost when both agree on chapter
    if not result_he or not result_he.get("candidates"):
        return result_en or {"candidates": []}
    if not result_en or not result_en.get("candidates"):
        return result_he

    he_chapters = {str(c.get("hs_code", "")).replace(".", "")[:2]
                   for c in result_he.get("candidates", [])}
    en_chapters = {str(c.get("hs_code", "")).replace(".", "")[:2]
                   for c in result_en.get("candidates", [])}
    agreed_chapters = he_chapters & en_chapters

    # Merge candidates, dedup by hs_code
    seen = set()
    merged = []
    for c in result_he.get("candidates", []) + result_en.get("candidates", []):
        hs = str(c.get("hs_code", "")).replace(".", "").replace("/", "")
        if hs in seen:
            continue
        seen.add(hs)
        ch = hs[:2]
        if agreed_chapters and ch in agreed_chapters:
            c["confidence"] = min(100, (c.get("confidence") or 50) + 15)
        merged.append(c)

    merged = _filter_by_vocab_chapters(merged, vocab_chapters, name_he)
    result_he["candidates"] = merged
    return result_he


def _search_via_unified(desc_he, desc_en, item):
    """Search via unified index, return candidates in pre_classify format."""
    find = _unified_search.get("find")
    if not find:
        return None

    # Search Hebrew
    results_he = find(desc_he, min_score=1) if desc_he else []

    # Search English
    results_en = []
    if desc_en and desc_en.lower() != desc_he.lower():
        results_en = find(desc_en, min_score=1)

    if not results_he and not results_en:
        return None

    # Merge and deduplicate
    seen = set()
    candidates = []
    he_chapters = set()
    en_chapters = set()

    for r in results_he:
        hs = str(r["hs_code"]).replace(".", "").replace("/", "")
        if hs in seen:
            continue
        seen.add(hs)
        he_chapters.add(hs[:2])
        candidates.append(_unified_to_candidate(r, "unified_he"))

    for r in results_en:
        hs = str(r["hs_code"]).replace(".", "").replace("/", "")
        if hs in seen:
            continue
        seen.add(hs)
        en_chapters.add(hs[:2])
        candidates.append(_unified_to_candidate(r, "unified_en"))

    # Boost candidates where Hebrew + English agree on chapter
    agreed = he_chapters & en_chapters
    if agreed:
        for c in candidates:
            ch = str(c["hs_code"]).replace(".", "").replace("/", "")[:2]
            if ch in agreed:
                c["confidence"] = min(95, c["confidence"] + 15)

    # Sort by confidence
    candidates.sort(key=lambda c: c["confidence"], reverse=True)
    return candidates[:10]


def _unified_to_candidate(result, source_label):
    """Convert unified search result to pre_classify candidate format."""
    score = result.get("score", 1)
    weight = result.get("weight", 1)
    # Convert to 0-95 confidence scale
    confidence = min(95, max(20, score * 20 + weight * 2))
    return {
        "hs_code": result["hs_code"],
        "confidence": confidence,
        "source": source_label,
        "description": result.get("description_he", result.get("description_en", "")),
        "duty_rate": result.get("duty_rate", ""),
        "reasoning": f"Unified index: score={score}, weight={weight}, sources={result.get('sources', [])}",
    }


def _convert_stage1_candidates(s1_candidates):
    """Convert Stage 1 HSCandidate dicts to pre_classify candidate format."""
    results = []
    for c in s1_candidates[:15]:
        hs = str(c.get("hs_code", "")).replace(".", "").replace("/", "")
        results.append({
            "hs_code": hs,
            "confidence": c.get("confidence", 50),
            "description": c.get("desc_he") or c.get("desc_en", ""),
            "source": "stage1_" + ",".join(c.get("sources", [])),
            "duty_rate": c.get("duty_rate", ""),
        })
    return results


def _build_candidates_for_item(item, db, vocab_chapters=None,
                               conversation_id=None, email_body=None,
                               api_key=None):
    """Search tariff DB for candidate HS codes matching item description.

    Pipeline: Stage 1 (identify) → Stage 2 (screen) → Stage 3 (conversation).
    Falls back to _smart_tariff_search if stages unavailable or return empty.

    Returns:
        pre_classify result dict with candidates list.
    """
    # --- NEW: Stage 1-3 pipeline ---
    _ensure_stages()
    if _STAGES_AVAILABLE:
        try:
            product_name = item.get("name", "")
            if product_name:
                # Stage 1: use cached result if verification loop re-entered
                s1_candidates = item.get("_s1_candidates")
                if s1_candidates is None:
                    s1_candidates = _identify_product(product_name, db)
                    if s1_candidates:
                        item["_s1_candidates"] = s1_candidates  # cache for re-entry
                else:
                    print(f"    Stage 1: using cached {len(s1_candidates)} candidates")
                if s1_candidates:
                    # Stage 2: screen candidates for readiness
                    known_attrs = {k: v for k, v in item.items()
                                   if k in _SCREEN_ATTR_KEYS and v}
                    s2_result = _screen_candidates(
                        product_name, s1_candidates, known_attrs, db, api_key)

                    if s2_result and s2_result.get("ready_for_traversal"):
                        # Ready — convert and proceed to elimination engine
                        converted = _convert_stage1_candidates(s1_candidates)
                        if converted:
                            print(f"    Stage 1-3: READY ({len(converted)} candidates)")
                            return {"candidates": converted,
                                    "source": "stage1_identifier"}

                    elif s2_result and not s2_result.get("ready_for_traversal"):
                        # Stage 3: conversation turn (if we have thread context)
                        if conversation_id:
                            s3_result = _process_conversation_turn(
                                conversation_id, product_name, s2_result,
                                email_body or "", db, api_key)
                            if s3_result and s3_result.get("ready_for_traversal"):
                                converted = _convert_stage1_candidates(s1_candidates)
                                if converted:
                                    print(f"    Stage 1-3: READY after conversation ({len(converted)} candidates)")
                                    return {"candidates": converted,
                                            "source": "stage1_after_conversation"}
                            # Not ready — store questions on item for caller
                            if s3_result and s3_result.get("questions_to_ask"):
                                item["_pending_questions"] = s3_result["questions_to_ask"]
                                item["_conversation_id"] = conversation_id

                    # Use Stage 1 candidates even if not fully screened
                    # (better than nothing — elimination engine will filter)
                    converted = _convert_stage1_candidates(s1_candidates)
                    if converted:
                        print(f"    Stage 1-3: unscreened ({len(converted)} candidates)")
                        return {"candidates": converted,
                                "source": "stage1_unscreened"}
        except Exception as e:
            print(f"    Stage 1-3 pipeline error: {e}")

    # --- Legacy fallback ---
    return _smart_tariff_search(item, db, vocab_chapters=vocab_chapters)


def classify_single_item(item, operation_context, db, spare_chapter=None,
                         vocab_chapters=None, conversation_id=None,
                         email_body=None, api_key=None):
    """Classify one item via decision_tree -> pre_classify -> eliminate (GIR 1-6).

    Decision tree path (Session 98): If a chapter decision tree exists for the
    product, it provides focused candidates and may REDIRECT to a different
    chapter. This runs BEFORE pre_classify and supplements (not replaces) it.

    Args:
        item: dict with name, keywords, category, physical, essence, function,
              transformation_stage, processing_state, dominant_material_pct
        operation_context: dict with direction, legal_category, origin_country
        db: Firestore client
        spare_chapter: optional parent chapter code for spare parts
        vocab_chapters: optional set of 2-digit chapter codes from smart_classify
        conversation_id: optional email thread ID for Stage 3 conversation
        email_body: optional current email text for Stage 3 answer extraction
        api_key: optional Anthropic API key for Stage 2/3 AI calls

    Returns:
        dict with hs_code, confidence, description, duty_rate, elimination_result,
        or None if no candidates found.
    """
    _ensure_elimination()

    # --- Layer 1: Chapter decision tree (Session 98) ---
    tree_result = None
    _ensure_decision_trees()
    if _chapter_decision_trees and _chapter_decision_trees is not False:
        try:
            tree_result = _chapter_decision_trees(item)
        except Exception as e:
            print(f"    Decision tree error: {e}")
            tree_result = None

    # If tree says REDIRECT, update vocab_chapters to the redirect target
    if tree_result and tree_result.get("redirect"):
        redirect_ch = tree_result["redirect"].get("chapter")
        if redirect_ch:
            redirect_ch_str = str(redirect_ch).zfill(2)
            # Focus search on redirect target chapter
            vocab_chapters = {redirect_ch_str}
            print(f"    Decision tree REDIRECT: ch.{tree_result.get('chapter', '?')} → ch.{redirect_ch} "
                  f"({tree_result['redirect'].get('reason', '')[:80]})")

    # Build candidates from tariff search (Stage 1-3 first, legacy fallback)
    pre_result = _build_candidates_for_item(
        item, db, vocab_chapters=vocab_chapters,
        conversation_id=conversation_id, email_body=email_body,
        api_key=api_key)
    print(f"    [broker] candidate source: {pre_result.get('source', 'legacy') if pre_result else 'none'}")

    # Merge decision tree candidates into pre_classify results
    if tree_result and tree_result.get("candidates") and not tree_result.get("redirect"):
        tree_candidates = _convert_tree_candidates(tree_result["candidates"])
        if tree_candidates:
            existing = pre_result.get("candidates", []) if pre_result else []
            # Tree candidates go FIRST (higher priority)
            merged = tree_candidates + [c for c in existing
                                         if c.get("hs_code") not in
                                         {tc.get("hs_code") for tc in tree_candidates}]
            pre_result = pre_result or {}
            pre_result["candidates"] = merged[:15]  # Cap to avoid explosion
    # Filter garbage candidates when decision tree provides a chapter anchor.
    # Unified index substring matches (e.g. "תלת" matching "תלת כלורי") produce
    # candidates 50+ chapters away from the correct chapter — remove them.
    if tree_result and tree_result.get("chapter") and pre_result and pre_result.get("candidates"):
        tree_ch = int(tree_result["chapter"])
        filtered = []
        for c in pre_result["candidates"]:
            hs = str(c.get("hs_code", "")).replace(".", "").replace("/", "")
            try:
                cand_ch = int(hs[:2])
            except (ValueError, IndexError):
                filtered.append(c)  # Keep unparseable
                continue
            # Keep if within 15 chapters of tree result, or if from decision tree
            if abs(cand_ch - tree_ch) <= 15 or c.get("source") == "decision_tree":
                filtered.append(c)
        dropped = len(pre_result["candidates"]) - len(filtered)
        if dropped:
            print(f"    Tree proximity filter: dropped {dropped} candidates "
                  f">15 chapters from tree ch.{tree_ch}")
        if filtered:  # Only apply if at least 1 survives
            pre_result["candidates"] = filtered

    if not pre_result or not pre_result.get("candidates"):
        # Rescue: try external tariff sources (UK API + Shaarolami)
        if _EXTERNAL_SEARCH_AVAILABLE:
            ext_results = external_tariff_search(
                query_en=item.get("name", ""),
                query_he=item.get("name_he", item.get("name", "")),
                db=db,
            )
            if ext_results:
                pre_result = {
                    "candidates": ext_results,
                    "rescue_source": "external_tariff_search",
                }
        if not pre_result or not pre_result.get("candidates"):
            return None

    # Normalize confidence to 0-100 scale (elimination engine's internal scale).
    # Decision tree uses 0.0-1.0 — scale up. Unified index and pre_classify already 0-100.
    for c in pre_result.get("candidates", []):
        conf = c.get("confidence", 0)
        if 0 < conf <= 1.0:
            c["confidence"] = conf * 100.0

    # If spare part, boost parent chapter candidates
    candidates = _candidates_from_pre_classify(pre_result)
    if spare_chapter:
        for c in candidates:
            hs = str(c.get("hs_code", "")).replace(".", "").replace("/", "")
            if hs[:2].zfill(2) == spare_chapter.zfill(2):
                c["confidence"] = min(100, c.get("confidence", 50) + 20)

    # Build product info for elimination engine
    product_info = _make_product_info({
        "description": item.get("name", ""),
        "material": item.get("physical", ""),
        "form": item.get("physical_form", ""),
        "use": item.get("function", ""),
        "origin_country": operation_context.get("origin_country", ""),
    })
    # Attach Layer 0 fields for downstream use (tree result, logging)
    product_info["transformation_stage"] = item.get("transformation_stage", "")
    product_info["processing_state"] = item.get("processing_state", "")
    product_info["dominant_material_pct"] = item.get("dominant_material_pct")
    if tree_result:
        product_info["_tree_result"] = tree_result

    # Run elimination engine (GIR 1-6, deterministic)
    elim_result = _eliminate(db, product_info, candidates)

    survivors = elim_result.get("survivors", [])
    if not survivors:
        # All eliminated — use top pre_classify candidate as fallback
        top = pre_result["candidates"][0]
        raw_conf = top.get("confidence", 30)
        return {
            "hs_code": _enforce_hs_format(top.get("hs_code", "")),
            "confidence": raw_conf / 100.0 if raw_conf > 1.0 else raw_conf,
            "description": top.get("description", ""),
            "duty_rate": top.get("duty_rate", ""),
            "elimination_result": elim_result,
            "source": "pre_classify_fallback",
        }

    # Pick top survivor by confidence (0-100 scale from elimination engine)
    best = max(survivors, key=lambda s: s.get("confidence", 0))
    raw_conf = best.get("confidence", 50)
    return {
        "hs_code": _enforce_hs_format(best.get("hs_code", "")),
        "confidence": raw_conf / 100.0 if raw_conf > 1.0 else raw_conf,
        "description": best.get("description", best.get("description_en", "")),
        "duty_rate": best.get("duty_rate", ""),
        "elimination_result": elim_result,
        "source": "elimination_engine",
    }


def _convert_tree_candidates(tree_candidates):
    """Convert chapter decision tree candidates to pre_classify candidate format.

    Tree candidates have: heading, subheading_hint, confidence, reasoning.
    pre_classify candidates have: hs_code, confidence, source, description, reasoning.
    """
    results = []
    for tc in tree_candidates:
        heading = tc.get("heading", "")
        sub_hint = tc.get("subheading_hint", "")
        # Use subheading_hint if available, else pad heading to 10 digits
        if sub_hint:
            hs = sub_hint.replace(".", "").ljust(10, "0")
        elif heading:
            hs = heading.replace(".", "").ljust(10, "0")
        else:
            continue
        results.append({
            "hs_code": hs,
            "confidence": tc.get("confidence", 0.7),
            "source": "decision_tree",
            "description": tc.get("reasoning", ""),
            "reasoning": tc.get("reasoning", ""),
            "rule_applied": tc.get("rule_applied", ""),
        })
    return results


# ---------------------------------------------------------------------------
#  FIX 2: Sub-heading drill-down (heading → 10-digit XX.XX.XXXXXX/X)
# ---------------------------------------------------------------------------

# Distinguishing criteria patterns in Hebrew tariff descriptions
_WEIGHT_RE = re.compile(r'(?:משקל|ק"ג|קילוגרם|גרם|kg|KG)\s*[:<]?\s*(\d+(?:[.,]\d+)?)', re.IGNORECASE)
_POWER_RE = re.compile(r'(?:הספק|וואט|W|kW|קילוואט)\s*[:<]?\s*(\d+(?:[.,]\d+)?)', re.IGNORECASE)
_CAPACITY_RE = re.compile(r'(?:נפח|ליטר|cm3|סמ"ק)\s*[:<]?\s*(\d+(?:[.,]\d+)?)', re.IGNORECASE)
_DIMENSION_RE = re.compile(r'(?:אורך|רוחב|גובה|mm|cm|מ"מ)\s*[:<]?\s*(\d+(?:[.,]\d+)?)', re.IGNORECASE)

# Weight thresholds commonly found in tariff descriptions (Hebrew)
_WEIGHT_THRESHOLD_RE = re.compile(
    r'(?:שמשקלו?\s*(?:אינו\s*עולה\s*על|עד|לא\s*יותר\s*מ)\s*(\d+(?:[.,]\d+)?)\s*(?:ק"ג|קילוגרם|גרם|kg|g))|'
    r'(?:(\d+(?:[.,]\d+)?)\s*(?:ק"ג|קילוגרם|גרם|kg|g)\s*(?:ומטה|או\s*פחות))',
    re.IGNORECASE,
)


def _drill_to_subheading(hs_code, item, db):
    """Drill from heading-level HS (4-6 digit) to full 10-digit sub-heading.

    Queries tariff DB for all sub-codes under the heading, parses description
    DIFFERENCES to find distinguishing criteria (weight, material, power, etc.),
    then matches item specs against criteria.

    Returns:
        dict with:
            hs_code: str — best 10-digit code (or original if can't determine)
            sub_codes: list — all sibling sub-codes found (with supplement_rate, statistical_unit)
            description: str — description of matched code
            duty_rate: str — duty rate of matched code
            method: str — "spec_match" | "only_child" | "kram"
            clarification_options: list — Hebrew multiple-choice if kram
    """
    hs_clean = str(hs_code).replace(".", "").replace("/", "").replace(" ", "")

    # Already a leaf → nothing to drill
    if len(hs_clean) >= 10:
        _ensure_unified()
        if _UNIFIED_AVAILABLE:
            try:
                from lib._unified_search import is_leaf
                if is_leaf(hs_clean):
                    return None
            except Exception:
                pass
        # Fallback heuristic: if it doesn't end in 0000, likely a leaf
        if not hs_clean.endswith("0000"):
            return None

    # Build heading prefix (first 4 digits minimum)
    heading = hs_clean[:4] if len(hs_clean) >= 4 else hs_clean
    if len(heading) < 4:
        return None

    # Query sub-codes: unified index first (instant), Firestore fallback
    _ensure_unified()
    sub_codes = []

    if _UNIFIED_AVAILABLE:
        subcodes_fn = _unified_search.get("subcodes")
        if subcodes_fn:
            raw = subcodes_fn(heading)
            for r in raw:
                sub_codes.append({
                    "hs_code": r["hs_code"],
                    "description": r.get("description_he", ""),
                    "description_en": r.get("description_en", ""),
                    "duty_rate": r.get("duty_rate", ""),
                    "purchase_tax": r.get("purchase_tax", ""),
                })

    if not sub_codes:
        # Firestore fallback
        prefix_lo = heading.ljust(10, "0")
        prefix_hi = heading.ljust(10, "9")
        try:
            docs = db.collection("tariff").where(
                "__name__", ">=", prefix_lo
            ).where(
                "__name__", "<=", prefix_hi
            ).stream()
            for doc in docs:
                data = doc.to_dict()
                if data.get("corrupt_code"):
                    continue
                sub_codes.append({
                    "hs_code": doc.id,
                    "description": data.get("description", data.get("description_he", "")),
                    "description_en": data.get("description_en", ""),
                    "duty_rate": data.get("duty_rate", ""),
                    "purchase_tax": data.get("purchase_tax", ""),
                })
        except Exception as e:
            print(f"    Drill-down query error for heading {heading}: {e}")
            return None

    if not sub_codes:
        return None

    # Enrich sub_codes with supplement rate + statistical unit from XML data
    _enrich_subcodes_with_supplements(sub_codes)

    # Only one sub-code → use it directly
    if len(sub_codes) == 1:
        sc = sub_codes[0]
        return {
            "hs_code": sc["hs_code"],
            "description": sc["description"],
            "duty_rate": sc["duty_rate"],
            "purchase_tax": sc.get("purchase_tax", ""),
            "sub_codes": sub_codes,
            "method": "only_child",
        }

    # Try to match by item specs
    matched = _match_subcode_by_specs(sub_codes, item)
    if matched:
        return {
            "hs_code": matched["hs_code"],
            "description": matched["description"],
            "duty_rate": matched["duty_rate"],
            "purchase_tax": matched.get("purchase_tax", ""),
            "sub_codes": sub_codes,
            "method": "spec_match",
        }

    # Can't determine — return all sub-codes + clarification options
    options = []
    for sc in sub_codes[:8]:  # Limit to 8 options
        desc = sc.get("description", "") or sc.get("description_en", "")
        if desc:
            options.append({
                "hs_code": sc["hs_code"],
                "description": desc[:120],
            })

    return {
        "hs_code": sub_codes[0]["hs_code"],  # Default to first
        "description": sub_codes[0].get("description", ""),
        "duty_rate": sub_codes[0].get("duty_rate", ""),
        "purchase_tax": sub_codes[0].get("purchase_tax", ""),
        "sub_codes": sub_codes,
        "method": "kram",
        "clarification_options": options,
    }


def _enrich_subcodes_with_supplements(sub_codes):
    """Enrich sub_codes with supplement_rate and statistical_unit from XML data.

    Adds 'supplement_rate' and 'statistical_unit' keys to each sub-code dict.
    Data comes from _tariff_supplements.py (parsed from XML tariff archives).
    """
    try:
        from lib._tariff_supplements import get_supplement_rate, get_unit_for_hs
    except ImportError:
        try:
            from _tariff_supplements import get_supplement_rate, get_unit_for_hs
        except ImportError:
            return  # Data file not available — columns stay "—"

    for sc in sub_codes:
        hs = str(sc.get("hs_code", "")).replace(".", "").replace("/", "")
        # Supplement rate (שיעור התוספות)
        supp = get_supplement_rate(hs)
        if supp:
            sc["supplement_rate"] = supp.get("customs_en", "") or supp.get("customs_rate", "")
        # Statistical unit (יחידה סטטיסטית)
        unit = get_unit_for_hs(hs)
        if unit:
            sc["statistical_unit"] = unit.get("he", "") or unit.get("en", "")


def _match_subcode_by_specs(sub_codes, item):
    """Try to match a sub-code based on item specs vs description criteria.

    Checks weight, power, capacity, material patterns in sub-code descriptions
    against item's physical specs from AI analysis.
    """
    item_text = " ".join(filter(None, [
        item.get("name", ""), item.get("physical", ""),
        item.get("essence", ""), item.get("function", ""),
    ])).lower()

    # Extract item weight if available
    item_weight = None
    wm = _WEIGHT_RE.search(item_text)
    if wm:
        try:
            item_weight = float(wm.group(1).replace(",", "."))
            # Normalize to grams if "kg" context
            if "kg" in item_text or "ק\"ג" in item_text or "קילו" in item_text:
                item_weight *= 1000
        except (ValueError, TypeError):
            pass

    best_score = -1
    best_sc = None

    for sc in sub_codes:
        desc = (sc.get("description", "") + " " + sc.get("description_en", "")).lower()
        score = 0

        # Weight matching
        if item_weight is not None:
            tm = _WEIGHT_THRESHOLD_RE.search(desc)
            if tm:
                threshold_str = tm.group(1) or tm.group(2)
                if threshold_str:
                    try:
                        threshold = float(threshold_str.replace(",", "."))
                        # Normalize threshold to grams
                        if "kg" in desc or "ק\"ג" in desc or "קילו" in desc:
                            threshold *= 1000
                        if item_weight <= threshold:
                            score += 5  # Strong match
                    except (ValueError, TypeError):
                        pass

        # Material matching
        item_material = (item.get("physical", "") or "").lower()
        for mat_he, mat_en in [("פלדה", "steel"), ("עץ", "wood"),
                               ("פלסטיק", "plastic"), ("גומי", "rubber"),
                               ("זכוכית", "glass"), ("אלומיניום", "alumin"),
                               ("נחושת", "copper"), ("טקסטיל", "textile")]:
            if (mat_he in item_material or mat_en in item_material) and \
               (mat_he in desc or mat_en in desc):
                score += 3

        # Keyword overlap between item name and sub-code description
        item_words = set(item.get("name", "").lower().split())
        desc_words = set(desc.split())
        overlap = item_words & desc_words - {"של", "או", "את", "עם", "לא", "כל", "the", "of", "and", "or", "for"}
        score += len(overlap)

        if score > best_score:
            best_score = score
            best_sc = sc

    # Only return if we have a meaningful match (not just random overlap)
    if best_score >= 3 and best_sc:
        return best_sc
    return None


# ---------------------------------------------------------------------------
#  PHASE 7: Chapter 98 mapping
# ---------------------------------------------------------------------------

def _apply_chapter98(item_result, item, legal_category, item_category=""):
    """Map classification result to Chapter 98 code if personal import.

    Modifies item_result in-place to add chapter98_* fields.
    """
    if not legal_category or not item_result:
        return

    # Temporary import uses discount code 207, not Chapter 98
    if legal_category == "temporary_import":
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

    # --- CHECK 1b: MOC frequency detection ---
    _check_moc_requirement(item_result, item)

    # --- CHECK 1c: EU reform ("מה שטוב לאירופה") ---
    _check_eu_reform(item_result, item, operation_context)

    # --- Always add VAT ---
    item_result["vat_rate"] = ISRAEL_VAT_RATE


_MOC_KEYWORDS = re.compile(
    r'radio|wifi|wi-fi|bluetooth|2\.4\s*GHz|5\s*GHz|5\.8\s*GHz|cellular|'
    r'antenna|transmitter|רדיו|אנטנה|משדר|תקשורת|אלחוטי',
    re.IGNORECASE,
)
_MOC_CHAPTERS = {"85", "88", "90", "95"}  # Electronics, aircraft/drones, instruments, toys


def _check_moc_requirement(item_result, item):
    """CHECK 1b: Detect if product requires MOC (Ministry of Communications) approval.

    Products with radio/wifi/bluetooth frequencies need אישור תקשורת 1301
    from משרד התקשורת per FIO תוספת 2.
    """
    hs_clean = str(item_result.get("hs_code", "")).replace(".", "").replace("/", "")
    chapter = hs_clean[:2].zfill(2) if len(hs_clean) >= 2 else ""

    # Only check relevant chapters
    if chapter not in _MOC_CHAPTERS:
        return

    # Check item text for radio/frequency keywords
    item_text = " ".join(filter(None, [
        item.get("name", ""), item.get("physical", ""),
        item.get("essence", ""), item.get("function", ""),
        item.get("frequency", ""),
    ]))

    if not _MOC_KEYWORDS.search(item_text):
        return

    # Also check FIO authorities for MOC
    fio = item_result.get("fio", {})
    fio_has_moc = False
    if fio and fio.get("found"):
        for auth in fio.get("authorities", []):
            if "תקשורת" in str(auth):
                fio_has_moc = True
                break

    item_result["moc_required"] = True
    item_result["moc_note"] = "נדרש אישור תקשורת 1301 ממשרד התקשורת"
    if fio_has_moc:
        item_result["moc_note"] += " (מופיע בצו יבוא חופשי תוספת 2)"


# Chapters where EU reform CE marking may apply
_EU_REFORM_CHAPTERS = {
    "84", "85", "90", "94", "95",  # Electrical, instruments, furniture, toys
    "33", "34", "39", "40", "44",  # Cosmetics, soaps, plastics, rubber, wood
    "61", "62", "63", "64", "65",  # Textiles, footwear, headgear
    "68", "69", "70", "73", "76",  # Stone, ceramic, glass, iron, aluminum
    "96",  # Miscellaneous manufactured articles
}


def _check_eu_reform(item_result, item, operation_context):
    """CHECK 1c: Flag EU reform applicability ("מה שטוב לאירופה").

    If the HS chapter falls in EU reform scope AND origin is EU/EFTA,
    add eu_reform_note with CE marking guidance.
    """
    if operation_context.get("direction") != "import":
        return

    hs_clean = str(item_result.get("hs_code", "")).replace(".", "").replace("/", "")
    chapter = hs_clean[:2].zfill(2) if len(hs_clean) >= 2 else ""
    if chapter not in _EU_REFORM_CHAPTERS:
        return

    origin = (operation_context.get("origin_country", "") or "").lower()
    eu_origins = {"eu", "germany", "france", "italy", "spain", "netherlands",
                  "belgium", "austria", "poland", "czech", "romania", "portugal",
                  "sweden", "denmark", "finland", "ireland", "greece", "hungary",
                  "bulgaria", "croatia", "slovakia", "slovenia", "estonia",
                  "latvia", "lithuania", "luxembourg", "malta", "cyprus",
                  "efta", "switzerland", "norway", "iceland", "liechtenstein"}

    # Show note even without origin — it's informational
    item_result["eu_reform_applicable"] = True
    if origin in eu_origins:
        item_result["eu_reform_note"] = (
            'רפורמת "מה שטוב לאירופה" — מוצרים עם סימון CE מהאיחוד האירופי '
            "עשויים להתקבל ללא בדיקה נוספת של מכון התקנים (מת\"י). "
            "בתנאי שהדירקטיבה הרלוונטית אומצה בישראל (החלטת ממשלה 2118)."
        )
    else:
        item_result["eu_reform_note"] = (
            'פרק זה עשוי להיות בתחולת רפורמת "מה שטוב לאירופה". '
            "אם המוצר מיוצר באירופה עם סימון CE, ייתכן פטור מבדיקת מת\"י."
        )


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

    # Temporary import — sections 162, 85, 232
    if legal_category == "temporary_import":
        for art_id, key in [("162", "temporary_admission_162"),
                            ("85", "exhibition_85"),
                            ("232", "regulation_232")]:
            art = get_ordinance_article(art_id)
            if art:
                articles[key] = {
                    "article": art_id,
                    "title_he": art.get("t", ""),
                    "summary": art.get("s", ""),
                    "applies": True,
                    "reason": "temporary_import",
                }

    # Section 129: Personal use exemption (entry-entitled persons)
    if legal_category and legal_category != "temporary_import":
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

def verify_and_loop(result, item, operation_context, db, max_loops=3,
                    api_key=None):
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
        result = _reclassify_with_constraints(
            item, operation_context, db, errors, result, api_key=api_key)
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

    # CHECK 1: HS code exists in tariff DB (or find most specific subheading)
    if hs_clean and len(hs_clean) >= 4:
        try:
            found = False
            # Try exact match first (10-digit, then as-is)
            for doc_id in [hs_clean.ljust(10, "0")[:10], hs_clean]:
                doc = db.collection("tariff").document(doc_id).get()
                if doc.exists:
                    found = True
                    # If result was short (heading-level), upgrade to the full code
                    if len(hs_clean) < 8 and len(doc_id) == 10:
                        data = doc.to_dict()
                        result["hs_code"] = doc_id
                        result["description"] = (data.get("description", "") or
                                                 data.get("description_he", "") or
                                                 result.get("description", ""))
                        result["duty_rate"] = data.get("duty_rate", "") or result.get("duty_rate", "")
                    break
            # If short code, try prefix search for most specific subheading
            if not found and len(hs_clean) <= 6:
                prefix = hs_clean.ljust(4, "0")[:4]
                siblings = db.collection("tariff").where(
                    "__name__", ">=", prefix + "000000"
                ).where(
                    "__name__", "<", prefix + "\uf8ff"
                ).limit(5).stream()
                for sib in siblings:
                    sib_data = sib.to_dict()
                    desc = (sib_data.get("description", "") or "").lower()
                    item_kw = (item.get("name", "") + " " + item.get("essence", "")).lower()
                    # Match any keyword from item description in tariff description
                    item_words = set(re.findall(r'\w{3,}', item_kw))
                    desc_words = set(re.findall(r'\w{3,}', desc))
                    if item_words & desc_words:
                        result["hs_code"] = sib.id
                        result["description"] = sib_data.get("description", "")
                        result["duty_rate"] = sib_data.get("duty_rate", "")
                        found = True
                        break
                if not found:
                    # Use first child as fallback
                    siblings2 = db.collection("tariff").where(
                        "__name__", ">=", prefix + "000000"
                    ).where(
                        "__name__", "<", prefix + "\uf8ff"
                    ).limit(1).stream()
                    for sib in siblings2:
                        result["hs_code"] = sib.id
                        result["description"] = sib.to_dict().get("description", "")
                        result["duty_rate"] = sib.to_dict().get("duty_rate", "")
                        found = True
            if not found:
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


def _reclassify_with_constraints(item, operation_context, db, errors, prev_result,
                                 api_key=None):
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
        {**item, "name": augmented_desc}, db, api_key=api_key,
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

def process_case(email_text, attachments_text, db, get_secret_func,
                  vocab_chapters=None):
    """Main entry point. Classify all items in an email deterministically.

    Phases:
        0: analyze_case() — operation type, legal category, items
        1: _identify_items_with_ai() — ONE AI call for physical/essence/function
        2: _check_spare_part() — parent machine chapter check
        3-6: eliminate() per item — GIR 1-6 deterministic
        7: Chapter 98 mapping — personal import codes
        8: _post_classification_cascade() — FIO + FTA + discount + valuation
        9: verify_and_loop() — 3-iteration self-check

    Args:
        vocab_chapters: optional set of 2-digit chapter codes from smart_classify.
                        Constrains tariff search to these chapters when provided.

    Returns:
        dict with: status, operation, items[], ordinance_articles,
        valuation, release_notes, verification_log
    """
    if not email_text and not attachments_text:
        return None

    text = f"{email_text or ''}\n{attachments_text or ''}"

    # Fetch Anthropic API key early — needed for conversational extraction + Stage 2/3
    _anthropic_key = None
    if get_secret_func:
        try:
            _anthropic_key = get_secret_func("ANTHROPIC_API_KEY")
        except Exception as e:
            print(f"    [broker] ANTHROPIC_API_KEY fetch failed: {e}")
    # Fallback: environment variable (local dev / testing)
    if not _anthropic_key:
        _anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if _anthropic_key:
        _anthropic_key = _anthropic_key.strip()
    print(f"    [broker] API key available: {bool(_anthropic_key)}")

    # PHASE 0: Analyze case
    case_plan = analyze_case("", text)

    # PHASE 0b: Extract and fetch product URLs from email (BEFORE item check —
    # email may contain only URLs with no inline product names)
    url_specs = _extract_and_fetch_urls(text)

    # If case_reasoning found 0 items but email has URLs, use page titles as items
    if not case_plan.items_to_classify and url_specs:
        url_items = []
        for spec in url_specs:
            title = spec.get("title", "").strip()
            if title:
                url_items.append(title)
                print(f"    URL item from page title: {title[:80]}")
        if url_items:
            case_plan.items_to_classify = url_items

    if not case_plan.items_to_classify:
        # Fallback: extract products from conversational text via customs vocabulary
        vocab_products = _extract_products_from_vocab(text)
        if vocab_products:
            print(f"    Vocab fallback: {len(vocab_products)} products extracted from text")
            for vp in vocab_products:
                print(f"      → {vp['name'][:60]} (chapters: {vp.get('chapters', [])})")
            case_plan.items_to_classify = [
                {"name": vp["name"], "keywords": vp["keywords"],
                 "description": text[:500], "category": "commercial"}
                for vp in vocab_products
            ]
        elif vocab_chapters:
            # Vocab extraction found nothing but smart_classify identified chapters.
            # Use the email body itself as the product description with a chapter hint.
            ch_hint = sorted(vocab_chapters)[0]
            body_clean = re.sub(r'<[^>]+>', ' ', text).strip()
            body_first_line = body_clean.split('\n')[0].strip()[:80] or body_clean[:80]
            print(f"    Chapter hint fallback: ch.{ch_hint} from smart_classify, body='{body_first_line[:50]}'")
            case_plan.items_to_classify = [{
                "name": body_first_line,
                "description": body_clean[:500],
                "category": "commercial",
                "chapter_hint": ch_hint,
            }]
        else:
            # Last resort: AI extraction from conversational question
            print(f"    [broker] AI product extraction on {len(text)} chars")
            conv_product = _extract_product_from_question(text, api_key=_anthropic_key)
            if conv_product:
                print(f"    Conversational fallback: '{conv_product}'")
                case_plan.items_to_classify = [{
                    "name": conv_product,
                    "description": text[:500],
                    "category": "commercial",
                }]
            else:
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

    # Attach URL-extracted specs to items
    if url_specs:
        for item in items:
            item_name_lower = item.get("name", "").lower()
            for spec in url_specs:
                # If any spec keyword matches item name, attach
                spec_keywords = spec.get("keywords", [])
                if any(kw.lower() in item_name_lower for kw in spec_keywords if kw):
                    for field in ("weight", "dimensions", "frequency", "power", "material"):
                        if spec.get(field) and not item.get(field):
                            item[field] = spec[field]
                    if spec.get("url"):
                        item["source_url"] = spec["url"]
                    break  # One URL per item

    # _anthropic_key already fetched at top of process_case

    # Process each item
    classified_items = []
    verification_log = []

    for item in items:
        # PHASE 2: Spare part check
        spare_chapter = _check_spare_part(item, text, db)

        # Merge item-level chapter_hint into vocab_chapters
        _vc = vocab_chapters
        if item.get("chapter_hint"):
            _vc = (vocab_chapters or set()) | {item["chapter_hint"]}

        # PHASES 3-6: Classify via elimination engine
        result = classify_single_item(item, operation_context, db,
                                      spare_chapter=spare_chapter,
                                      vocab_chapters=_vc,
                                      email_body=text,
                                      api_key=_anthropic_key)

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

        # PHASE 6b: Sub-heading drill-down (heading → 10-digit)
        hs_raw = str(result.get("hs_code", "")).replace(".", "").replace("/", "")
        if len(hs_raw) < 10 or hs_raw.endswith("0000"):
            drill = _drill_to_subheading(hs_raw, item, db)
            if drill:
                result["hs_code"] = drill["hs_code"]
                result["sub_codes"] = drill.get("sub_codes", [])
                result["drill_method"] = drill.get("method", "")
                if drill.get("description"):
                    result["description"] = drill["description"]
                if drill.get("duty_rate"):
                    result["duty_rate"] = drill["duty_rate"]
                if drill.get("purchase_tax"):
                    result["purchase_tax"] = drill["purchase_tax"]
                if drill.get("clarification_options"):
                    result["clarification_options"] = drill["clarification_options"]

        # PHASE 7: Chapter 98 mapping
        _apply_chapter98(result, item, case_plan.legal_category,
                         item_category=item.get("category", ""))

        # PHASE 8: Post-classification cascade
        _post_classification_cascade(result, item, operation_context, db)

        # PHASE 9: Verification loop
        verified = verify_and_loop(result, item, operation_context, db,
                                   api_key=_anthropic_key)
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
