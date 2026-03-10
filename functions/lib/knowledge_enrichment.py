"""
Knowledge Enrichment — Tier 2 overnight heading enrichment.
============================================================
Enriches 4-digit HS headings with Wikipedia, TARIC notes,
and official XML structure. Writes ONLY to Tier 2 collections.

Entry point: enrich_headings_batch(db) — called by Cloud Function.
Batch cursor: processes 50 headings per run, resumes from last cursor.
Full cycle: ~1,200 headings in ~12 hours at 50/run every 30 min.
"""

import time
import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

from lib.librarian import normalize_hs_code, get_israeli_hs_format

# ═══════════════════════════════════════════════════════════
#  TIER 1 PROTECTION — NEVER WRITE TO THESE COLLECTIONS
# ═══════════════════════════════════════════════════════════

PROTECTED_COLLECTIONS = frozenset({
    "tariff", "chapter_notes", "free_import_order",
    "framework_order", "FIO", "FEO", "ordinance",
    "learned_classifications", "classification_history",
    "discount_codes", "fta_rates", "procedures",
})

# The ONLY collections this module may write to:
_ALLOWED_WRITE_COLLECTIONS = frozenset({
    "heading_knowledge",
    "enrichment_log",
    "enrichment_state",
})


class ProtectedCollectionError(Exception):
    """Raised when code attempts to write to a Tier 1 protected collection."""
    pass


def _safe_write(db, collection, doc_id, data):
    """Write to Firestore with Tier 1 protection guard.
    This guard runs BEFORE any Firestore write — no exceptions."""
    # Guard 1: reject Tier 1 collections
    if collection in PROTECTED_COLLECTIONS:
        raise ProtectedCollectionError(
            f"ABORT: Attempted write to Tier 1 collection '{collection}' "
            f"(doc '{doc_id}'). Tier 2 enrichment module cannot touch Tier 1 data."
        )
    # Guard 2: only allow known Tier 2 collections
    if collection not in _ALLOWED_WRITE_COLLECTIONS:
        raise ProtectedCollectionError(
            f"ABORT: Attempted write to unknown collection '{collection}' "
            f"(doc '{doc_id}'). Only {_ALLOWED_WRITE_COLLECTIONS} are allowed."
        )
    db.collection(collection).document(doc_id).set(data, merge=True)


# ═══════════════════════════════════════════════════════════
#  TIER 2 METADATA — required on every document
# ═══════════════════════════════════════════════════════════

def _tier2_meta(source):
    """Return metadata fields required on every Tier 2 document."""
    return {
        "data_tier": "enrichment",
        "is_authoritative": False,
        "source": source,
        "fetched_at": datetime.now(timezone.utc),
    }


# ═══════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════

_BATCH_SIZE = 50
_MAX_RUNTIME_SEC = 480
_FETCH_DELAY_SEC = 1.0

_WIKI_EN_SEARCH = "https://en.wikipedia.org/w/api.php"
_WIKI_HE_SEARCH = "https://he.wikipedia.org/w/api.php"
_WIKI_EN_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{term}"
_WIKI_HE_SUMMARY = "https://he.wikipedia.org/api/rest_v1/page/summary/{term}"
_TARIC_URL = "https://ec.europa.eu/taxation_customs/dds2/taric/taric_consultation.jsp"

_USER_AGENT = "RCB-RPA-PORT/1.0 (rcb@rpa-port.co.il) python-requests"
_HEADERS = {"User-Agent": _USER_AGENT, "Accept": "application/json"}

# XML namespace from CustomsItem.xml / CustomsItemDetailsHistory.xml
_XML_NS = {"ns": "http://malam.com/customs/CustomsBook/CBC_NG_8362_MSG01_CustomsBookOut"}

# Stop words for synonym extraction
_STOP_WORDS = frozenset({
    "the", "and", "for", "are", "was", "were", "been", "have", "has",
    "this", "that", "with", "from", "they", "which", "their", "also",
    "other", "some", "most", "many", "more", "such", "than", "very",
    "first", "may", "can", "used", "its", "these", "those", "after",
    "between", "each", "new", "often", "well", "however", "while",
    "about", "into", "over", "under", "being", "both", "through",
})

# FIX 4: Skip words for Wikipedia search term extraction
_WIKI_SKIP_WORDS = frozenset({
    "live", "other", "of", "and", "for", "the", "in", "or", "not",
    "elsewhere", "specified", "included", "parts", "thereof", "articles",
    "preparations", "made", "worked", "containing", "whether", "similar",
    "kinds", "put", "up", "retail", "sale", "sets", "consisting",
    "products", "goods", "materials", "n.e.s", "nes", "nesoi",
    "heading", "subheading", "chapter", "note", "except", "including",
    "type", "types", "form", "forms", "suitable", "use", "used",
    "ready", "wholly", "partly", "new", "old", "fresh", "frozen",
    "dried", "preserved", "crude", "refined", "raw", "processed",
    "printed", "unprinted", "mounted", "unmounted", "having",
})


# ═══════════════════════════════════════════════════════════
#  XML PARSER — loaded ONCE at cold start, reused across batch
# ═══════════════════════════════════════════════════════════

_xml_items_cache = None       # {hs10: {id, parent_id, hierarchy_level, ...}}
_xml_descriptions_cache = None  # {item_id: {description_he, description_en}}


def _xml_text(element, tag):
    """Extract text from a namespace-prefixed child element."""
    child = element.find(f"ns:{tag}", _XML_NS)
    if child is not None and child.text:
        return child.text.strip()
    return None


def _ensure_str(val):
    """Ensure value is a proper Python str, not bytes. Fixes mojibake."""
    if val is None:
        return ""
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val)


def _get_data_dir():
    """Return path to the data/ directory next to this file."""
    import os
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def load_xml_items(path=None):
    """Parse CustomsItem.xml → {hs10: {id, parent_id, hierarchy_level, check_digit, book_type}}.
    Loaded ONCE, cached in module-level variable."""
    global _xml_items_cache
    if _xml_items_cache is not None:
        return _xml_items_cache

    if path is None:
        import os
        path = os.path.join(_get_data_dir(), "CustomsItem.xml")

    items = {}
    try:
        print(f"[ENRICHMENT] Loading CustomsItem.xml ...")
        t0 = time.time()
        # FIX 2: Explicit UTF-8 encoding — read as text, parse from string
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        root = ET.fromstring(content)

        for elem in root.iter(f"{{{_XML_NS['ns']}}}CustomsItem"):
            item_id = _xml_text(elem, "ID")
            fc = _xml_text(elem, "FullClassification")
            if not fc or not item_id:
                continue
            hs10 = fc.replace(".", "").replace(" ", "").ljust(10, "0")[:10]
            items[hs10] = {
                "id": _ensure_str(item_id),
                "parent_id": _ensure_str(_xml_text(elem, "Parent_CustomsItemID")),
                "hierarchy_level": _ensure_str(_xml_text(elem, "CustomsItemHierarchicLocationID")),
                "check_digit": _ensure_str(_xml_text(elem, "ComputedCheckDigit")),
                "book_type": _ensure_str(_xml_text(elem, "CustomsBookTypeID")),
            }
        print(f"[ENRICHMENT] Loaded {len(items)} items in {time.time() - t0:.1f}s")
    except Exception as e:
        print(f"[ENRICHMENT] ERROR loading CustomsItem.xml: {e}")
        items = {}

    _xml_items_cache = items
    return _xml_items_cache


def load_xml_descriptions(path=None):
    """Parse CustomsItemDetailsHistory.xml → {item_id: {description_he, description_en}}.
    Keeps latest active entry per CustomsItemID. Loaded ONCE."""
    global _xml_descriptions_cache
    if _xml_descriptions_cache is not None:
        return _xml_descriptions_cache

    if path is None:
        import os
        path = os.path.join(_get_data_dir(), "CustomsItemDetailsHistory.xml")

    descs = {}
    try:
        print(f"[ENRICHMENT] Loading CustomsItemDetailsHistory.xml ...")
        t0 = time.time()
        # FIX 2: Explicit UTF-8 encoding — read as text, parse from string
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        root = ET.fromstring(content)

        for elem in root.iter(f"{{{_XML_NS['ns']}}}CustomsItemDetailsHistory"):
            item_id = _xml_text(elem, "CustomsItemID")
            if not item_id:
                continue
            # EntityStatusID: 2=active, 4=cancelled
            if _xml_text(elem, "EntityStatusID") == "4":
                continue
            he = _ensure_str(_xml_text(elem, "GoodsDescription"))
            en = _ensure_str(_xml_text(elem, "EnglishGoodsDescription"))
            if not he and not en:
                continue
            if en == "---":
                en = ""
            # Keep highest ID per item (latest entry)
            entry_id = int(_xml_text(elem, "ID") or "0")
            existing = descs.get(item_id)
            if existing is None or entry_id > existing.get("_entry_id", 0):
                descs[item_id] = {
                    "description_he": he,
                    "description_en": en,
                    "_entry_id": entry_id,
                }
        print(f"[ENRICHMENT] Loaded {len(descs)} descriptions in {time.time() - t0:.1f}s")
    except Exception as e:
        print(f"[ENRICHMENT] ERROR loading descriptions XML: {e}")
        descs = {}

    _xml_descriptions_cache = descs
    return _xml_descriptions_cache


def _reset_xml_caches():
    """Reset XML caches — for testing only."""
    global _xml_items_cache, _xml_descriptions_cache
    _xml_items_cache = None
    _xml_descriptions_cache = None


def get_heading_structure(hs4):
    """Get all subheadings under a 4-digit heading from XML.
    Args:
        hs4: '8413' or '84.13'
    Returns:
        list of {hs10, description_he, description_en, hierarchy_level, formatted}
    """
    items = load_xml_items()
    descriptions = load_xml_descriptions()

    hs4_clean = hs4.replace(".", "").replace(" ", "")[:4]

    results = []
    for hs10, info in items.items():
        if hs10[:4] == hs4_clean:
            desc = descriptions.get(info["id"], {})
            results.append({
                "hs10": hs10,
                "description_he": _ensure_str(desc.get("description_he", "")),
                "description_en": _ensure_str(desc.get("description_en", "")),
                "hierarchy_level": info.get("hierarchy_level", ""),
                "formatted": get_israeli_hs_format(hs10),
            })

    results.sort(key=lambda x: x["hs10"])
    return results


# ═══════════════════════════════════════════════════════════
#  EXTERNAL FETCHERS
# ═══════════════════════════════════════════════════════════

def _extract_wiki_search_term(description):
    """FIX 4: Extract meaningful nouns from tariff description for Wikipedia search.
    E.g., 'Live horses, asses, mules and hinnies' → 'horses asses mules'
    E.g., 'Pumps for liquids' → 'pumps liquids'"""
    if not description or len(description.strip()) < 3:
        return ""
    # Extract English words (3+ chars)
    words = re.findall(r'[a-zA-Z]{3,}', description.lower())
    meaningful = [w for w in words if w not in _WIKI_SKIP_WORDS]
    if meaningful:
        return " ".join(meaningful[:3])
    # Fallback: first 50 chars of description
    return description.strip()[:50]


def _fetch_wikipedia(description, lang="en"):
    """Search Wikipedia for description, fetch top result summary.
    Returns summary text (max 2000 chars) or empty string."""
    if not description or len(description.strip()) < 3:
        return ""

    # FIX 4: Extract meaningful search terms instead of raw description
    if lang == "en":
        search_term = _extract_wiki_search_term(description)
    else:
        # Hebrew: use description as-is (no skip word filtering for Hebrew)
        search_term = description.strip().rstrip(".:;-")

    if not search_term or len(search_term) < 3:
        return ""

    search_url = _WIKI_EN_SEARCH if lang == "en" else _WIKI_HE_SEARCH
    summary_base = _WIKI_EN_SUMMARY if lang == "en" else _WIKI_HE_SUMMARY

    try:
        # Step 1: search
        resp = requests.get(search_url, params={
            "action": "query", "list": "search",
            "srsearch": search_term, "srlimit": "3", "format": "json",
        }, headers=_HEADERS, timeout=10)
        if resp.status_code != 200:
            return ""
        results = resp.json().get("query", {}).get("search", [])
        if not results:
            return ""

        title = results[0].get("title", "")
        if not title:
            return ""

        time.sleep(_FETCH_DELAY_SEC)

        # Step 2: summary
        url = summary_base.format(term=requests.utils.quote(title))
        resp2 = requests.get(url, headers=_HEADERS, timeout=10)
        if resp2.status_code != 200:
            return ""
        extract = resp2.json().get("extract", "")
        return extract[:2000] if extract else ""

    except Exception as e:
        print(f"[ENRICHMENT] Wikipedia {lang} error for '{search_term}': {e}")
        return ""


def _fetch_taric_notes(hs4, wiki_en_fallback=""):
    """FIX 3: Fetch TARIC consultation page for a 4-digit heading.
    The TARIC JSP page is JS-rendered — if response is garbage (mostly
    script/CSS), falls back to wiki_en content as notes.
    Returns cleaned text or empty string. NOT authoritative for Israeli customs."""
    hs4_clean = hs4.replace(".", "").replace(" ", "")[:4]
    try:
        resp = requests.get(_TARIC_URL, params={
            "area": "", "code": hs4_clean, "domain": "TARIC",
            "expand": "true", "lang": "EN", "nomen": "goods",
            "offset": "0", "order": "num", "pageSize": "20",
        }, headers={"User-Agent": _USER_AGENT, "Accept": "text/html"}, timeout=15)
        if resp.status_code != 200:
            return wiki_en_fallback
        text = resp.text
        if len(text) < 100:
            return wiki_en_fallback

        # Strip HTML tags
        clean = re.sub(r'<[^>]+>', ' ', text)
        clean = re.sub(r'\s+', ' ', clean).strip()

        # FIX 3: Detect garbage — if clean text is mostly JS/CSS noise
        # Real TARIC content has heading codes like "8413" in the text
        if len(clean) < 200 or hs4_clean not in clean:
            return wiki_en_fallback

        # Check text-to-original ratio — if < 10% is real text, it's garbage
        if len(clean) < len(text) * 0.10:
            return wiki_en_fallback

        return clean[:3000]
    except Exception as e:
        print(f"[ENRICHMENT] TARIC error for {hs4_clean}: {e}")
        return wiki_en_fallback


def _extract_synonyms(wiki_en, wiki_he):
    """Extract product noun candidates from Wikipedia for human review.
    Returns sorted list, max 50."""
    candidates = set()
    for text in [wiki_en, wiki_he]:
        if not text:
            continue
        # English: capitalized words (3+ chars)
        candidates.update(w.lower() for w in re.findall(r'\b[A-Z][a-z]{2,}\b', text))
        # Hebrew words (3+ chars)
        candidates.update(re.findall(r'[\u0590-\u05FF]{3,}', text))
    candidates -= _STOP_WORDS
    return sorted(candidates)[:50]


# ═══════════════════════════════════════════════════════════
#  CURSOR / STATE
# ═══════════════════════════════════════════════════════════

def _raw4_to_dotted_prefix(hs4):
    """FIX 1: Convert raw 4-digit HS code to dotted prefix for tariff query.
    '8411' → '84.11', '0101' → '01.01'"""
    hs4 = hs4.ljust(4, "0")[:4]
    return f"{hs4[:2]}.{hs4[2:4]}"


def _load_state(db):
    """Read enrichment_state/cursor doc."""
    doc = db.collection("enrichment_state").document("cursor").get()
    if doc.exists:
        return doc.to_dict()
    return {"last_hs4": "", "total_processed": 0, "total_errors": 0, "last_run": None}


def _save_state(db, state):
    """Write enrichment_state/cursor doc."""
    _safe_write(db, "enrichment_state", "cursor", {
        **state,
        **_tier2_meta("enrichment_batch"),
    })


def _get_unenriched_headings(db, after_hs4, limit):
    """Get next batch of 4-digit headings from tariff that haven't been enriched.
    FIX 1: Uses dotted prefix for cursor comparison — tariff hs_code field
    uses dotted format (e.g., '84.13.100000'), so cursor must match.
    Returns list of {hs4, description_he, description_en}."""
    query = db.collection("tariff").order_by("hs_code")
    if after_hs4:
        # FIX 1: Convert raw cursor to dotted format for correct string comparison
        dotted_prefix = _raw4_to_dotted_prefix(after_hs4)
        # Use next heading prefix to skip the current heading entirely
        # "84.11" → next is "84.12" (increment last 2 digits)
        ch = int(after_hs4[:2])
        sub = int(after_hs4[2:4])
        if sub < 99:
            next_prefix = f"{ch:02d}.{sub + 1:02d}"
        else:
            next_prefix = f"{ch + 1:02d}.00"
        query = query.where("hs_code", ">=", next_prefix)
    query = query.limit(500)  # read extra to find unique headings

    seen = set()
    headings = []

    for doc in query.stream():
        data = doc.to_dict()
        hs_code = data.get("hs_code", "")
        if not hs_code:
            continue
        raw = normalize_hs_code(hs_code)
        hs4 = raw[:4]
        if hs4 in seen or not hs4.isdigit():
            continue
        seen.add(hs4)

        # Idempotent: skip if already enriched
        if db.collection("heading_knowledge").document(hs4).get().exists:
            continue

        headings.append({
            "hs4": hs4,
            "description_he": _ensure_str(data.get("description_he", "") or data.get("description", "") or ""),
            "description_en": _ensure_str(data.get("description_en", "") or data.get("english_description", "") or ""),
        })
        if len(headings) >= limit:
            break

    return headings


# ═══════════════════════════════════════════════════════════
#  SINGLE HEADING ENRICHMENT
# ═══════════════════════════════════════════════════════════

def _enrich_one(db, heading_info):
    """Enrich one 4-digit heading. Returns (success: bool, error_msg: str|None)."""
    hs4 = heading_info["hs4"]
    desc_en = _ensure_str(heading_info.get("description_en", ""))
    desc_he = _ensure_str(heading_info.get("description_he", ""))

    try:
        # 1. Official structure from local XML (instant, no HTTP)
        structure = get_heading_structure(hs4)

        # Fill missing description from XML
        if not desc_en and structure:
            for s in structure:
                if s.get("description_en"):
                    desc_en = s["description_en"]
                    break
        if not desc_he and structure:
            for s in structure:
                if s.get("description_he"):
                    desc_he = s["description_he"]
                    break

        # 2. Wikipedia EN — use extracted search terms (FIX 4)
        wiki_en = _fetch_wikipedia(desc_en, lang="en")
        time.sleep(_FETCH_DELAY_SEC)

        # 3. Wikipedia HE
        wiki_he = _fetch_wikipedia(desc_he or desc_en, lang="he")
        time.sleep(_FETCH_DELAY_SEC)

        # 4. TARIC notes — falls back to wiki_en if garbage (FIX 3)
        taric = _fetch_taric_notes(hs4, wiki_en_fallback=wiki_en)
        time.sleep(_FETCH_DELAY_SEC)

        # 5. Synonym candidates
        synonyms = _extract_synonyms(wiki_en, wiki_he)

        # 6. Write to heading_knowledge — all strings ensured via _ensure_str
        formatted_hs4 = f"{hs4[:2]}.{hs4[2:4]}"
        doc = {
            "hs4": formatted_hs4,
            "hs4_raw": hs4,
            "description_he": desc_he,
            "description_en": desc_en,
            "wiki_en": wiki_en,
            "wiki_he": wiki_he,
            "taric_notes": taric,
            "official_structure": [
                {
                    "hs10": s["hs10"],
                    "description_he": _ensure_str(s["description_he"]),
                    "description_en": _ensure_str(s["description_en"]),
                    "formatted": s["formatted"],
                }
                for s in structure
            ],
            "subheading_count": len(structure),
            "synonym_candidates": synonyms,
            **_tier2_meta("wikipedia+taric+local_xml"),
        }
        _safe_write(db, "heading_knowledge", hs4, doc)
        return True, None

    except ProtectedCollectionError:
        raise  # must abort entire run
    except Exception as e:
        msg = f"{hs4}: {e}"
        print(f"[ENRICHMENT] FAIL {msg}")
        return False, msg


# ═══════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════

def _log_run(db, run_id, data):
    """Write run log to enrichment_log/{run_id}."""
    try:
        _safe_write(db, "enrichment_log", run_id, {
            **data,
            **_tier2_meta("enrichment_batch"),
        })
    except Exception as e:
        import traceback
        print(f"[ENRICHMENT] Failed to write log {run_id}: {e}")
        traceback.print_exc()
        raise


# ═══════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

def enrich_headings_batch(db):
    """Process a batch of up to 50 HS headings.
    Args:
        db: Firestore client
    Returns:
        dict with run summary
    """
    run_start = time.time()
    now = datetime.now(timezone.utc)
    run_id = f"run_{now.strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(now.timestamp()).encode()).hexdigest()[:6]}"

    print(f"[ENRICHMENT] === Batch {run_id} starting ===")

    # Pre-load XMLs (cold start cost — reused for all 50 headings)
    load_xml_items()
    load_xml_descriptions()

    # Read cursor
    state = _load_state(db)
    cursor_before = state.get("last_hs4", "")
    print(f"[ENRICHMENT] Cursor: {cursor_before or '(start)'}, total so far: {state.get('total_processed', 0)}")

    # Get next batch of unenriched headings
    headings = _get_unenriched_headings(db, cursor_before, _BATCH_SIZE)

    if not headings:
        if cursor_before:
            print(f"[ENRICHMENT] Cycle complete. Resetting cursor.")
            state["last_hs4"] = ""
            state["last_run"] = now
            _save_state(db, state)
        else:
            print("[ENRICHMENT] All headings enriched. Nothing to do.")
        _log_run(db, run_id, {
            "started_at": now, "completed_at": datetime.now(timezone.utc),
            "headings_processed": 0, "errors": [],
            "cursor_before": cursor_before, "cursor_after": "",
            "run_id": run_id, "status": "no_work",
        })
        return {"status": "no_work", "headings_processed": 0, "run_id": run_id}

    print(f"[ENRICHMENT] Batch: {len(headings)} headings ({headings[0]['hs4']}..{headings[-1]['hs4']})")

    processed = 0
    errors = []
    last_hs4 = cursor_before

    for h in headings:
        # Runtime budget check
        if time.time() - run_start >= _MAX_RUNTIME_SEC:
            print(f"[ENRICHMENT] Runtime budget ({_MAX_RUNTIME_SEC}s) exhausted. Saving cursor.")
            break

        ok, err = _enrich_one(db, h)
        last_hs4 = h["hs4"]
        processed += 1

        if ok:
            print(f"[ENRICHMENT] {processed}/{len(headings)}: {h['hs4']} OK")
        else:
            errors.append({"hs4": h["hs4"], "error": err})

    # Save cursor
    state["last_hs4"] = last_hs4
    state["total_processed"] = state.get("total_processed", 0) + processed
    state["total_errors"] = state.get("total_errors", 0) + len(errors)
    state["last_run"] = datetime.now(timezone.utc)
    _save_state(db, state)

    # Log run
    summary = {
        "started_at": now,
        "completed_at": datetime.now(timezone.utc),
        "duration_sec": round(time.time() - run_start, 1),
        "headings_processed": processed,
        "headings_succeeded": processed - len(errors),
        "headings_failed": len(errors),
        "errors": errors[:20],
        "cursor_before": cursor_before,
        "cursor_after": last_hs4,
        "run_id": run_id,
        "status": "completed",
    }
    _log_run(db, run_id, summary)

    print(f"[ENRICHMENT] === Done: {processed} processed, {len(errors)} errors, cursor->{last_hs4} ===")
    return {
        "status": "completed",
        "run_id": run_id,
        "headings_processed": processed,
        "headings_succeeded": processed - len(errors),
        "headings_failed": len(errors),
        "cursor_after": last_hs4,
    }
