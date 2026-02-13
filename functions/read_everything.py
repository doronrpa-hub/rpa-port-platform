"""
Read Everything — Build the master brain_index from ALL Firestore collections.
==============================================================================
Reads every knowledge-bearing collection and builds a unified inverted index:
  brain_index: keyword → {sources: [{collection, doc_id, hs_code, context, weight}]}

When pre_classify looks for "kiwi", it finds results from tariff + knowledge_base
+ classifications + rcb + legal + everything — one unified search.

No AI calls — pure Firestore reads + text parsing + index writes. $0 cost.

Usage:
    python read_everything.py [--stats-only]
"""

import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

# ── Firebase setup ──
cred_path = os.path.join(
    os.environ.get("APPDATA", ""),
    "gcloud", "legacy_credentials", "doronrpa@gmail.com", "adc.json"
)
if os.path.exists(cred_path):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "rpa-port-customs")

import firebase_admin
from firebase_admin import firestore

if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

STATS_ONLY = "--stats-only" in sys.argv

# ── HS code patterns ──
_HS_PATTERN = re.compile(
    r'(?<!\d)'
    r'(\d{4}[\.\s]?\d{2}[\.\s]?\d{2,4}(?:/\d)?)'
    r'(?!\d)'
)

_HS_DOT_PATTERN = re.compile(
    r'(\d{2}\.\d{2}(?:\.\d{2,4})?)'
)

_STOP_WORDS = {
    "the", "a", "an", "of", "for", "and", "or", "with", "to", "from",
    "in", "on", "by", "is", "are", "was", "were", "be", "been", "not",
    "this", "that", "these", "those", "has", "have", "had", "its",
    "other", "new", "used", "set", "pcs", "piece", "pieces", "item",
    "items", "type", "part", "parts", "made", "per", "each", "etc",
    "code", "codes", "chapter", "heading", "note", "notes", "shall",
    "may", "must", "including", "includes", "see", "also", "means",
    "את", "של", "על", "עם", "או", "גם", "כי", "אם", "לא", "יש", "זה",
    "אל", "הם", "הוא", "היא", "בין", "כל", "מן", "אשר", "עד", "רק",
    "אין", "היו", "אחר", "לפי", "ללא", "ידי", "כגון", "וכו", "כמו",
    "פרט", "סעיף", "תת", "לרבות",
}


def _clean_hs(code):
    if not code:
        return ""
    clean = str(code).replace(".", "").replace("/", "").replace(" ", "").strip()
    if not clean or not clean.isdigit():
        return ""
    if len(clean) not in (6, 8, 10):
        return ""
    try:
        chapter = int(clean[:2])
        if chapter < 1 or chapter > 97:
            return ""
    except ValueError:
        return ""
    if len(clean) == 8 and clean[:2] in ("20", "19"):
        month = int(clean[4:6])
        day = int(clean[6:8])
        if 1 <= month <= 12 and 1 <= day <= 31:
            return ""
    return clean


def _extract_hs_codes(text):
    if not text:
        return []
    text = str(text)
    codes = set()
    for m in _HS_PATTERN.finditer(text):
        c = _clean_hs(m.group(1))
        if c:
            codes.add(c)
    for m in _HS_DOT_PATTERN.finditer(text):
        c = _clean_hs(m.group(1))
        if c:
            codes.add(c)
    return list(codes)


def _tokenize(text):
    if not text:
        return []
    words = re.split(r'[^\w\u0590-\u05FF]+', text.lower())
    return [w for w in words if len(w) > 2 and w not in _STOP_WORDS]


def _safe_doc_id(text):
    safe = re.sub(r'[^\w\u0590-\u05FF]', '_', text.lower())
    safe = re.sub(r'_+', '_', safe).strip('_')
    return safe[:200] if safe else "unknown"


def _normalize_supplier(name):
    if not name:
        return ""
    text = name.lower().strip()
    for suffix in [" ltd", " ltd.", " inc", " inc.", " co.", " corp", " corp.",
                   " gmbh", " s.a.", " s.r.l.", " bv", " b.v.", " llc",
                   " בע\"מ", " בע״מ"]:
        if text.endswith(suffix):
            text = text[:-len(suffix)].strip()
    text = re.sub(r'[^\w\u0590-\u05FF\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text if text else ""


# ═══════════════════════════════════════════════════════════════
#  BRAIN INDEX ACCUMULATOR
# ═══════════════════════════════════════════════════════════════

# keyword → hs_code → {sources: [...], total_weight: int}
brain = defaultdict(lambda: defaultdict(lambda: {"sources": [], "total_weight": 0}))

stats = defaultdict(int)


def _add_to_brain(keyword, hs_code, collection, doc_id, context, weight):
    """Add a keyword → HS code mapping to the brain index."""
    entry = brain[keyword][hs_code]
    entry["total_weight"] += weight
    # Limit sources per keyword-hs pair to avoid bloat
    if len(entry["sources"]) < 5:
        entry["sources"].append({
            "collection": collection,
            "doc_id": doc_id,
            "context": context[:100] if context else "",
        })


def _index_text_with_hs(text, hs_code, collection, doc_id, context, weight):
    """Tokenize text and add each keyword → HS code mapping."""
    for token in _tokenize(text):
        _add_to_brain(token, hs_code, collection, doc_id, context, weight)


# ═══════════════════════════════════════════════════════════════
#  COLLECTION MINERS (ordered by authority)
# ═══════════════════════════════════════════════════════════════

def mine_tariff():
    """Official tariff database — highest authority. Weight: 5."""
    print("\n  Reading tariff...")
    count = 0
    for doc in db.collection("tariff").stream():
        data = doc.to_dict()
        hs = data.get("hs_code", "") or data.get("hs_code_raw", "")
        hs = _clean_hs(hs)
        if not hs:
            continue
        desc = data.get("description_he", "")
        chapter_desc = data.get("chapter_description", "")
        parent_desc = data.get("parent_heading_desc", "")
        context = desc[:100] if desc else chapter_desc[:100]

        for text in [desc, chapter_desc, parent_desc]:
            _index_text_with_hs(text, hs, "tariff", doc.id, context, 5)

        count += 1
        if count % 3000 == 0:
            print(f"    ...{count} tariff docs")

    stats["tariff"] = count
    print(f"  \u2705 tariff: {count} docs")


def mine_tariff_chapters():
    """Tariff chapter summaries. Weight: 4."""
    print("  Reading tariff_chapters...")
    count = 0
    for doc in db.collection("tariff_chapters").stream():
        data = doc.to_dict()
        chapter_name = data.get("chapterName", "")
        chapter_desc = data.get("chapterDescription", "")
        content = data.get("content", "")
        hs_codes = data.get("hsCodes", [])
        headings = data.get("headings", [])

        # Index chapter description with all its HS codes
        if isinstance(hs_codes, list):
            for hs_raw in hs_codes[:50]:
                hs = _clean_hs(hs_raw)
                if hs:
                    _index_text_with_hs(chapter_desc, hs, "tariff_chapters", doc.id, chapter_name, 4)

        # Index headings
        if isinstance(headings, list):
            for h in headings:
                if isinstance(h, dict):
                    h_code = _clean_hs(h.get("code", ""))
                    h_desc = h.get("description", "")
                    if h_code and h_desc:
                        _index_text_with_hs(h_desc, h_code, "tariff_chapters", doc.id, h_desc[:100], 4)

        # Extract HS from content text
        if isinstance(content, str):
            for hs in _extract_hs_codes(content):
                _index_text_with_hs(chapter_desc, hs, "tariff_chapters", doc.id, chapter_name, 3)

        count += 1

    stats["tariff_chapters"] = count
    print(f"  \u2705 tariff_chapters: {count} docs")


def _clean_legal_hs(raw):
    """Parse legal_requirements HS format: ' -0050000000/5' → '0500000000'.

    Format: 3-digit chapter (005=ch05) + 7-digit subheading, with /check_digit.
    Convert to standard 10-digit: 2-digit chapter + 8-digit subheading.
    """
    if not raw:
        return ""
    s = str(raw).strip().lstrip("-").strip()
    s = re.sub(r'/\d$', '', s)
    s = s.replace(".", "").replace(" ", "").strip()
    if not s or not s.isdigit():
        return ""
    if len(s) == 10 and s[:2] == "00":
        # 3-digit chapter format: 005XXXXXXX → chapter 05
        chapter = int(s[1:3])
        if 1 <= chapter <= 97:
            # Rebuild as standard 10-digit: chapter(2) + subheading(8)
            standard = s[1:3] + s[3:] + "0"  # 05 + 0000000 + 0 = 0500000000
            return _clean_hs(standard)
    return _clean_hs(s)


def mine_legal_requirements():
    """Legal/regulatory requirements per HS code. Weight: 5."""
    print("  Reading legal_requirements...")
    count = 0
    for doc in db.collection("legal_requirements").stream():
        data = doc.to_dict()
        hs = _clean_legal_hs(data.get("hs_code", "") or data.get("hs_code_raw", ""))
        if not hs:
            continue

        reqs = data.get("requirements", [])
        authorities = data.get("authorities", [])

        # Index authority names as keywords
        if isinstance(authorities, list):
            for auth in authorities:
                if isinstance(auth, str):
                    for token in _tokenize(auth):
                        _add_to_brain(token, hs, "legal_requirements", doc.id, auth, 4)

        # Index requirement descriptions
        if isinstance(reqs, list):
            for req in reqs:
                desc = ""
                if isinstance(req, dict):
                    desc = req.get("description", "") or req.get("name", "")
                elif isinstance(req, str):
                    desc = req
                if desc:
                    _index_text_with_hs(desc, hs, "legal_requirements", doc.id, desc[:100], 3)

        count += 1
        if count % 2000 == 0:
            print(f"    ...{count} legal_requirements docs")

    stats["legal_requirements"] = count
    print(f"  \u2705 legal_requirements: {count} docs")


def mine_knowledge_base():
    """Knowledge base — mixed authority. Weight: 2-3."""
    print("  Reading knowledge_base...")
    count = 0
    for doc in db.collection("knowledge_base").stream():
        data = doc.to_dict()
        doc_type = data.get("type", "")
        content = data.get("content", "")
        title = data.get("title", "")
        hs_codes = data.get("hs_codes_extracted", []) or data.get("hs_codes_referenced", [])

        weight = 3 if doc_type in ("product", "customs_procedure", "trade_agreement") else 2

        if isinstance(hs_codes, list):
            for hs_raw in hs_codes:
                hs = _clean_hs(hs_raw)
                if hs:
                    _index_text_with_hs(title, hs, "knowledge_base", doc.id, title[:100], weight)
                    if isinstance(content, str):
                        _index_text_with_hs(content[:500], hs, "knowledge_base", doc.id, title[:100], weight)

        # Legacy format: content dict with hs field
        if isinstance(content, dict):
            hs_raw = content.get("hs", "")
            if isinstance(hs_raw, list):
                for h in hs_raw:
                    hs = _clean_hs(h)
                    if hs:
                        products = content.get("products", [])
                        for p in (products if isinstance(products, list) else []):
                            _index_text_with_hs(str(p), hs, "knowledge_base", doc.id, str(p)[:100], 3)
            elif hs_raw:
                hs = _clean_hs(hs_raw)
                if hs:
                    products = content.get("products", [])
                    for p in (products if isinstance(products, list) else []):
                        _index_text_with_hs(str(p), hs, "knowledge_base", doc.id, str(p)[:100], 3)

        count += 1

    stats["knowledge_base"] = count
    print(f"  \u2705 knowledge_base: {count} docs")


def mine_classification_knowledge():
    """Learned classifications. Weight: 3."""
    print("  Reading classification_knowledge...")
    count = 0
    for doc in db.collection("classification_knowledge").stream():
        data = doc.to_dict()
        hs = _clean_hs(data.get("hs_code", ""))
        desc = data.get("description", "")
        sellers = data.get("sellers", [])

        if hs and desc:
            _index_text_with_hs(desc, hs, "classification_knowledge", doc.id, desc[:100], 3)

        if hs and isinstance(sellers, list):
            for s in sellers:
                if isinstance(s, str):
                    for token in _tokenize(s):
                        _add_to_brain(token, hs, "classification_knowledge", doc.id, f"seller: {s}", 2)

        count += 1

    stats["classification_knowledge"] = count
    print(f"  \u2705 classification_knowledge: {count} docs")


def mine_classifications():
    """Actual completed classifications. Weight: 3."""
    print("  Reading classifications...")
    count = 0
    for doc in db.collection("classifications").stream():
        data = doc.to_dict()
        hs = _clean_hs(data.get("our_hs_code", ""))
        desc = data.get("product_description", "")
        seller = data.get("seller", "")
        origin = data.get("origin", "")

        if hs and desc:
            _index_text_with_hs(desc, hs, "classifications", doc.id, desc[:100], 3)

        if hs and seller:
            for token in _tokenize(seller):
                _add_to_brain(token, hs, "classifications", doc.id, f"seller: {seller}", 2)

        if hs and origin:
            for token in _tokenize(origin):
                _add_to_brain(token, hs, "classifications", doc.id, f"origin: {origin}", 2)

        count += 1

    stats["classifications"] = count
    print(f"  \u2705 classifications: {count} docs")


def mine_rcb_classifications():
    """RCB broker classifications. Weight: 2."""
    print("  Reading rcb_classifications...")
    count = 0
    links = 0
    for doc in db.collection("rcb_classifications").stream():
        data = doc.to_dict()
        seller = data.get("seller", "")
        buyer = data.get("buyer", "")
        classifications = data.get("classifications", [])
        inv_data = data.get("invoice_data", {})
        synthesis = data.get("synthesis", "")

        if isinstance(classifications, list):
            for cls in classifications:
                if not isinstance(cls, dict):
                    continue
                hs = _clean_hs(cls.get("hs_code", ""))
                item = cls.get("item", cls.get("description", ""))
                if hs and item:
                    _index_text_with_hs(item, hs, "rcb_classifications", doc.id, item[:100], 2)
                    links += 1
                    if seller:
                        for token in _tokenize(seller):
                            _add_to_brain(token, hs, "rcb_classifications", doc.id, f"seller: {seller}", 2)

        # invoice_data items
        if isinstance(inv_data, dict):
            inv_seller = inv_data.get("seller", "")
            items = inv_data.get("items", [])
            if isinstance(items, list):
                for item_entry in items:
                    if not isinstance(item_entry, dict):
                        continue
                    desc = item_entry.get("description", "")
                    # Extract HS from nearby classifications
                    if isinstance(classifications, list):
                        for cls in classifications:
                            if isinstance(cls, dict):
                                hs = _clean_hs(cls.get("hs_code", ""))
                                if hs and desc:
                                    _index_text_with_hs(desc, hs, "rcb_classifications", doc.id, desc[:100], 2)

        # Synthesis text
        if synthesis:
            for hs in _extract_hs_codes(str(synthesis)):
                _index_text_with_hs(str(synthesis)[:300], hs, "rcb_classifications", doc.id, "synthesis", 1)

        count += 1

    stats["rcb_classifications"] = count
    stats["rcb_links"] = links
    print(f"  \u2705 rcb_classifications: {count} docs, {links} HS links")


def mine_rcb_silent():
    """Silent (auto) classifications. Weight: 2."""
    print("  Reading rcb_silent_classifications...")
    count = 0
    links = 0
    for doc in db.collection("rcb_silent_classifications").stream():
        data = doc.to_dict()
        classifications = data.get("classifications", [])
        inv_data = data.get("invoice_data", {})
        synthesis = data.get("synthesis", "")

        seller = ""
        if isinstance(inv_data, dict):
            seller = inv_data.get("seller", "")

        if isinstance(classifications, list):
            for cls in classifications:
                if not isinstance(cls, dict):
                    continue
                hs = _clean_hs(cls.get("hs_code", ""))
                item = cls.get("item", cls.get("description", ""))
                if hs and item:
                    _index_text_with_hs(item, hs, "rcb_silent", doc.id, item[:100], 2)
                    links += 1
                    if seller:
                        for token in _tokenize(seller):
                            _add_to_brain(token, hs, "rcb_silent", doc.id, f"seller: {seller}", 2)

        if synthesis:
            for hs in _extract_hs_codes(str(synthesis)):
                _index_text_with_hs(str(synthesis)[:300], hs, "rcb_silent", doc.id, "synthesis", 1)

        count += 1

    stats["rcb_silent_classifications"] = count
    stats["rcb_silent_links"] = links
    print(f"  \u2705 rcb_silent_classifications: {count} docs, {links} HS links")


def mine_regulatory_requirements():
    """Regulatory requirements by cargo type. Weight: 4."""
    print("  Reading regulatory_requirements...")
    count = 0
    for doc in db.collection("regulatory_requirements").stream():
        data = doc.to_dict()
        cargo = data.get("cargo", "") or data.get("cargo_he", "")
        hs_chapters = data.get("hs_chapters", [])
        ministries = data.get("ministries", [])
        requirements = data.get("requirements", [])

        # Index cargo keywords with HS chapters
        if isinstance(hs_chapters, list):
            for ch in hs_chapters:
                ch_str = str(ch).zfill(2)
                # Create a pseudo HS code from chapter (e.g., chapter 8 → 080000)
                pseudo_hs = ch_str + "0000"
                if _clean_hs(pseudo_hs):
                    _index_text_with_hs(cargo, pseudo_hs, "regulatory_requirements", doc.id, cargo[:100], 4)

        if isinstance(ministries, list):
            for m in ministries:
                if isinstance(m, str):
                    for token in _tokenize(m):
                        for ch in (hs_chapters if isinstance(hs_chapters, list) else []):
                            pseudo_hs = str(ch).zfill(2) + "0000"
                            if _clean_hs(pseudo_hs):
                                _add_to_brain(token, pseudo_hs, "regulatory_requirements", doc.id, m, 3)

        count += 1

    stats["regulatory_requirements"] = count
    print(f"  \u2705 regulatory_requirements: {count} docs")


def mine_fta_agreements():
    """Free trade agreements. Weight: 4."""
    print("  Reading fta_agreements...")
    count = 0
    for doc in db.collection("fta_agreements").stream():
        data = doc.to_dict()
        name = data.get("name", "") or data.get("name_he", "")
        countries = data.get("countries", [])
        pref_rate = data.get("preferential_rate", "")
        origin_proof = data.get("origin_proof", "")

        # FTAs don't have specific HS codes — index country keywords broadly
        context = f"FTA: {name}"
        if isinstance(countries, list):
            for country in countries:
                if isinstance(country, str):
                    for token in _tokenize(country):
                        _add_to_brain(token, "FTA", "fta_agreements", doc.id, context, 3)
        for token in _tokenize(name):
            _add_to_brain(token, "FTA", "fta_agreements", doc.id, context, 3)

        count += 1

    stats["fta_agreements"] = count
    print(f"  \u2705 fta_agreements: {count} docs")


def mine_classification_rules():
    """Classification rules and guidelines. Weight: 3."""
    print("  Reading classification_rules...")
    count = 0
    for doc in db.collection("classification_rules").stream():
        data = doc.to_dict()
        title = data.get("title", "") or data.get("title_he", "")
        desc = data.get("description", "")
        rule = data.get("rule", "")
        rule_type = data.get("type", "")

        # Extract HS codes from rule text
        all_text = f"{title} {desc} {rule}"
        for hs in _extract_hs_codes(all_text):
            _index_text_with_hs(title, hs, "classification_rules", doc.id, title[:100], 3)
            _index_text_with_hs(desc, hs, "classification_rules", doc.id, title[:100], 3)

        # Index rule type keywords
        for token in _tokenize(f"{title} {rule_type}"):
            _add_to_brain(token, "RULE", "classification_rules", doc.id, title[:100], 2)

        count += 1

    stats["classification_rules"] = count
    print(f"  \u2705 classification_rules: {count} docs")


def mine_ministry_index():
    """Ministry → HS chapter mappings. Weight: 4."""
    print("  Reading ministry_index...")
    count = 0
    for doc in db.collection("ministry_index").stream():
        data = doc.to_dict()
        ministry = data.get("ministry", "")
        cargo = data.get("cargo", "") or data.get("cargo_he", "")
        hs_chapter = data.get("hs_chapter", "")

        if hs_chapter:
            pseudo_hs = str(hs_chapter).zfill(2) + "0000"
            if _clean_hs(pseudo_hs):
                _index_text_with_hs(cargo, pseudo_hs, "ministry_index", doc.id, cargo[:100], 4)
                if ministry:
                    for token in _tokenize(ministry):
                        _add_to_brain(token, pseudo_hs, "ministry_index", doc.id, f"ministry: {ministry}", 3)

        count += 1

    stats["ministry_index"] = count
    print(f"  \u2705 ministry_index: {count} docs")


def mine_sellers():
    """Known sellers and their products. Weight: 3."""
    print("  Reading sellers...")
    count = 0
    for doc in db.collection("sellers").stream():
        data = doc.to_dict()
        name = data.get("name", "")
        country = data.get("country", "")
        products = data.get("products", [])

        if isinstance(products, list):
            for p in products:
                if isinstance(p, dict):
                    hs = _clean_hs(p.get("hs_code", ""))
                    desc = p.get("description", "") or p.get("name", "")
                    if hs:
                        _index_text_with_hs(desc, hs, "sellers", doc.id, f"{name}: {desc}"[:100], 3)
                        if name:
                            for token in _tokenize(name):
                                _add_to_brain(token, hs, "sellers", doc.id, f"seller: {name}", 3)

        count += 1

    stats["sellers"] = count
    print(f"  \u2705 sellers: {count} docs")


def mine_buyers():
    """Known buyers. Weight: 2."""
    print("  Reading buyers...")
    count = 0
    for doc in db.collection("buyers").stream():
        data = doc.to_dict()
        name = data.get("name", "") or data.get("name_he", "")
        products = data.get("products_imported", [])

        if isinstance(products, list):
            for p in products:
                if isinstance(p, dict):
                    hs = _clean_hs(p.get("hs_code", ""))
                    desc = p.get("description", "") or p.get("name", "")
                    if hs:
                        _index_text_with_hs(desc, hs, "buyers", doc.id, f"{name}: {desc}"[:100], 2)
                elif isinstance(p, str):
                    for hs in _extract_hs_codes(p):
                        _index_text_with_hs(p, hs, "buyers", doc.id, f"buyer: {name}", 2)

        count += 1

    stats["buyers"] = count
    print(f"  \u2705 buyers: {count} docs")


def mine_verification_cache():
    """Verified HS code lookups. Weight: 4."""
    print("  Reading verification_cache...")
    count = 0
    for doc in db.collection("verification_cache").stream():
        data = doc.to_dict()
        hs = _clean_hs(data.get("hs_code", "") or data.get("hs_clean", ""))
        desc_he = data.get("official_description_he", "")
        desc_en = data.get("official_description_en", "")

        if hs:
            if desc_he:
                _index_text_with_hs(desc_he, hs, "verification_cache", doc.id, desc_he[:100], 4)
            if desc_en:
                _index_text_with_hs(desc_en, hs, "verification_cache", doc.id, desc_en[:100], 4)

        count += 1

    stats["verification_cache"] = count
    print(f"  \u2705 verification_cache: {count} docs")


def mine_knowledge():
    """Knowledge collection (parsed shipping docs). Weight: 2."""
    print("  Reading knowledge...")
    count = 0
    for doc in db.collection("knowledge").stream():
        data = doc.to_dict()
        hs_codes = data.get("all_hs_codes", [])
        seller = data.get("seller", "")
        buyer = data.get("buyer", "")
        content = data.get("content", "")

        if isinstance(hs_codes, list):
            for hs_raw in hs_codes:
                hs = _clean_hs(hs_raw)
                if not hs:
                    continue
                if seller:
                    for token in _tokenize(seller):
                        _add_to_brain(token, hs, "knowledge", doc.id, f"seller: {seller}", 2)
                if buyer:
                    for token in _tokenize(buyer):
                        _add_to_brain(token, hs, "knowledge", doc.id, f"buyer: {buyer}", 2)
                if isinstance(content, str):
                    _index_text_with_hs(content[:300], hs, "knowledge", doc.id, f"{seller} → {buyer}"[:100], 2)

        count += 1

    stats["knowledge"] = count
    print(f"  \u2705 knowledge: {count} docs")


def mine_triangle_learnings():
    """AI comparison learnings. Weight: 3."""
    print("  Reading triangle_learnings...")
    count = 0
    for doc in db.collection("triangle_learnings").stream():
        data = doc.to_dict()
        winner_hs = _clean_hs(data.get("winner_code", ""))
        desc = data.get("product_description", "")

        if winner_hs and desc:
            _index_text_with_hs(desc, winner_hs, "triangle_learnings", doc.id, desc[:100], 3)

        count += 1

    stats["triangle_learnings"] = count
    print(f"  \u2705 triangle_learnings: {count} docs")


def mine_hs_code_index():
    """HS code cross-reference index. Weight: 3."""
    print("  Reading hs_code_index...")
    count = 0
    for doc in db.collection("hs_code_index").stream():
        data = doc.to_dict()
        chapter = data.get("chapter", "")
        refs = data.get("references", [])

        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, dict):
                    hs = _clean_hs(ref.get("hs_code", ""))
                    desc = ref.get("description", "")
                    if hs and desc:
                        _index_text_with_hs(desc, hs, "hs_code_index", doc.id, desc[:100], 3)

        count += 1

    stats["hs_code_index"] = count
    print(f"  \u2705 hs_code_index: {count} docs")


def mine_librarian_index():
    """Librarian document index. Weight: 2."""
    print("  Reading librarian_index...")
    count = 0
    for doc in db.collection("librarian_index").stream():
        data = doc.to_dict()
        hs_codes = data.get("hs_codes", [])
        keywords_en = data.get("keywords_en", [])
        keywords_he = data.get("keywords_he", [])
        desc = data.get("description", "")
        title = data.get("title", "")
        context = title[:100] if title else desc[:100]

        if isinstance(hs_codes, list):
            for hs_raw in hs_codes:
                hs = _clean_hs(hs_raw)
                if not hs:
                    continue

                # Index provided keywords directly
                for kw_list in [keywords_en, keywords_he]:
                    if isinstance(kw_list, list):
                        for kw in kw_list:
                            if isinstance(kw, str) and len(kw) > 2 and kw.lower() not in _STOP_WORDS:
                                _add_to_brain(kw.lower(), hs, "librarian_index", doc.id, context, 2)

                # Also tokenize description
                _index_text_with_hs(desc, hs, "librarian_index", doc.id, context, 2)

        count += 1
        if count % 3000 == 0:
            print(f"    ...{count} librarian_index docs")

    stats["librarian_index"] = count
    print(f"  \u2705 librarian_index: {count} docs")


def mine_free_import_cache():
    """Free import order cache. Weight: 4."""
    print("  Reading free_import_cache...")
    count = 0
    for doc in db.collection("free_import_cache").stream():
        data = doc.to_dict()
        hs = _clean_hs(data.get("hs_code", "") or data.get("hs_10", ""))
        items = data.get("items", [])
        authorities = data.get("authorities", [])

        if hs and isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    desc = item.get("description", "") or item.get("name", "")
                    if desc:
                        _index_text_with_hs(desc, hs, "free_import_cache", doc.id, desc[:100], 4)

        if hs and isinstance(authorities, list):
            for auth in authorities:
                if isinstance(auth, str):
                    for token in _tokenize(auth):
                        _add_to_brain(token, hs, "free_import_cache", doc.id, auth, 3)

        count += 1

    stats["free_import_cache"] = count
    print(f"  \u2705 free_import_cache: {count} docs")


def mine_licensing_knowledge():
    """Licensing/origin country knowledge. Weight: 3."""
    print("  Reading licensing_knowledge...")
    count = 0
    for doc in db.collection("licensing_knowledge").stream():
        data = doc.to_dict()
        hs_codes = data.get("hs_codes", [])
        country = data.get("origin_country", "")
        products = data.get("products_imported", [])

        if isinstance(hs_codes, list):
            for hs_raw in hs_codes:
                hs = _clean_hs(hs_raw)
                if not hs:
                    continue
                if country:
                    for token in _tokenize(country):
                        _add_to_brain(token, hs, "licensing_knowledge", doc.id, f"origin: {country}", 3)
                if isinstance(products, list):
                    for p in products:
                        if isinstance(p, str):
                            _index_text_with_hs(p, hs, "licensing_knowledge", doc.id, p[:100], 3)

        count += 1

    stats["licensing_knowledge"] = count
    print(f"  \u2705 licensing_knowledge: {count} docs")


def mine_procedures():
    """Customs procedures. Weight: 3."""
    print("  Reading procedures...")
    count = 0
    for doc in db.collection("procedures").stream():
        data = doc.to_dict()
        name = data.get("name_en", "") or data.get("name_he", "")
        content = data.get("content", "")
        legal_refs = data.get("legal_references", [])

        # Extract HS codes from content
        if isinstance(content, str):
            for hs in _extract_hs_codes(content):
                _index_text_with_hs(name, hs, "procedures", doc.id, name[:100], 3)

        count += 1

    stats["procedures"] = count
    print(f"  \u2705 procedures: {count} docs")


def mine_batch_reprocess():
    """Batch reprocess results — real classification data. Weight: 2."""
    print("  Reading batch_reprocess_results...")
    count = 0
    hs_found = 0
    for doc in db.collection("batch_reprocess_results").stream():
        data = doc.to_dict()
        hs_codes = data.get("hs_codes", [])
        classifications = data.get("classifications", [])
        subject = data.get("subject", "")
        intelligence = data.get("intelligence", "")

        if isinstance(hs_codes, list):
            for hs_raw in hs_codes:
                hs = _clean_hs(hs_raw)
                if hs:
                    context = subject[:100] if subject else ""
                    _index_text_with_hs(subject, hs, "batch_reprocess", doc.id, context, 2)
                    hs_found += 1

        if isinstance(classifications, list):
            for cls in classifications:
                if isinstance(cls, dict):
                    hs = _clean_hs(cls.get("hs_code", ""))
                    item = cls.get("item", cls.get("description", ""))
                    if hs and item:
                        _index_text_with_hs(item, hs, "batch_reprocess", doc.id, item[:100], 2)
                        hs_found += 1

        count += 1

    stats["batch_reprocess_results"] = count
    stats["batch_hs_found"] = hs_found
    print(f"  \u2705 batch_reprocess_results: {count} docs, {hs_found} HS links")


def mine_pupil_teachings():
    """Pupil AI learnings. Weight: 1."""
    print("  Reading pupil_teachings...")
    count = 0
    for doc in db.collection("pupil_teachings").stream():
        data = doc.to_dict()
        question = data.get("question", "")
        answer = data.get("answer", "")
        teaching = data.get("teaching_rule", "")

        all_text = f"{question} {answer} {teaching}"
        for hs in _extract_hs_codes(all_text):
            _index_text_with_hs(question, hs, "pupil_teachings", doc.id, question[:100], 1)

        count += 1

    stats["pupil_teachings"] = count
    print(f"  \u2705 pupil_teachings: {count} docs")


def mine_document_types():
    """Document type definitions with signal keywords. Weight: 2."""
    print("  Reading document_types...")
    count = 0
    for doc in db.collection("document_types").stream():
        data = doc.to_dict()
        code = data.get("code", "")
        desc = data.get("description", "")
        signals_en = data.get("signals_en", [])
        signals_he = data.get("signals_he", [])

        # These don't have HS codes — index as document type keywords
        context = f"doc_type: {code}"
        for kw_list in [signals_en, signals_he]:
            if isinstance(kw_list, list):
                for kw in kw_list:
                    if isinstance(kw, str) and len(kw) > 2:
                        _add_to_brain(kw.lower(), "DOCTYPE", "document_types", doc.id, context, 2)

        count += 1

    stats["document_types"] = count
    print(f"  \u2705 document_types: {count} docs")


def mine_shipping_lines():
    """Shipping line reference data. Weight: 2."""
    print("  Reading shipping_lines...")
    count = 0
    for doc in db.collection("shipping_lines").stream():
        data = doc.to_dict()
        name = data.get("full_name", "")
        country = data.get("country", "")
        prefixes = data.get("bol_prefixes", [])

        context = f"shipping: {name}"
        if name:
            for token in _tokenize(name):
                _add_to_brain(token, "SHIPPING", "shipping_lines", doc.id, context, 2)
        if isinstance(prefixes, list):
            for p in prefixes:
                if isinstance(p, str) and len(p) > 2:
                    _add_to_brain(p.lower(), "SHIPPING", "shipping_lines", doc.id, context, 2)

        count += 1

    stats["shipping_lines"] = count
    print(f"  \u2705 shipping_lines: {count} docs")


# ═══════════════════════════════════════════════════════════════
#  WRITE BRAIN INDEX
# ═══════════════════════════════════════════════════════════════

def write_brain_index():
    """Write the unified brain_index to Firestore."""
    total_keywords = len(brain)
    print(f"\n  Writing brain_index: {total_keywords} keywords...")
    now = datetime.now(timezone.utc).isoformat()

    batch = db.batch()
    count = 0

    for keyword, hs_entries in brain.items():
        doc_id = _safe_doc_id(keyword)
        if not doc_id or doc_id == "unknown":
            continue

        # Build the sources list sorted by weight
        codes = []
        for hs_code, info in hs_entries.items():
            codes.append({
                "hs_code": hs_code,
                "weight": info["total_weight"],
                "sources": info["sources"][:3],  # Top 3 source references
            })

        # Sort by weight, keep top 25 HS codes per keyword
        codes.sort(key=lambda x: -x["weight"])
        codes = codes[:25]

        ref = db.collection("brain_index").document(doc_id)
        batch.set(ref, {
            "keyword": keyword,
            "codes": codes,
            "count": len(codes),
            "total_weight": sum(c["weight"] for c in codes),
            "built_at": now,
        })

        count += 1
        if count % 450 == 0:
            batch.commit()
            batch = db.batch()
            if count % 5000 == 0:
                print(f"    ...{count} keywords written")

    if count % 450 != 0:
        batch.commit()

    print(f"  \u2705 brain_index: {count} keywords written")
    return count


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def run():
    mode = "STATS ONLY" if STATS_ONLY else "LIVE WRITE"
    print("=" * 60)
    print("  READ EVERYTHING \u2014 Build Master Brain Index")
    print(f"  Mode: {mode}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    t0 = time.time()

    # ── Mine everything ──
    print("\n\u2550\u2550\u2550 Mining all collections \u2550\u2550\u2550")

    mine_tariff()               # 11,753 docs, weight 5
    mine_tariff_chapters()      # 101 docs, weight 4
    mine_legal_requirements()   # 7,443 docs, weight 5
    mine_verification_cache()   # 43 docs, weight 4
    mine_regulatory_requirements()  # 28 docs, weight 4
    mine_ministry_index()       # 84 docs, weight 4
    mine_free_import_cache()    # 8 docs, weight 4
    mine_fta_agreements()       # 21 docs, weight 4
    mine_classification_knowledge()  # 81 docs, weight 3
    mine_classifications()      # 25 docs, weight 3
    mine_classification_rules() # 32 docs, weight 3
    mine_knowledge_base()       # 296 docs, weight 2-3
    mine_triangle_learnings()   # 36 docs, weight 3
    mine_hs_code_index()        # 101 docs, weight 3
    mine_sellers()              # 4 docs, weight 3
    mine_licensing_knowledge()  # 18 docs, weight 3
    mine_procedures()           # 3 docs, weight 3
    mine_knowledge()            # 71 docs, weight 2
    mine_rcb_classifications()  # 84 docs, weight 2
    mine_rcb_silent()           # 128 docs, weight 2
    mine_buyers()               # 2 docs, weight 2
    mine_librarian_index()      # 12,595 docs, weight 2
    mine_batch_reprocess()      # 345 docs, weight 2
    mine_document_types()       # 13 docs, weight 2
    mine_shipping_lines()       # 15 docs, weight 2
    mine_pupil_teachings()      # 202 docs, weight 1

    mine_time = time.time() - t0

    # ── Stats ──
    total_keywords = len(brain)
    total_hs_mappings = sum(len(entries) for entries in brain.values())
    total_sources = sum(
        sum(len(info["sources"]) for info in entries.values())
        for entries in brain.values()
    )

    # Count unique collections contributing
    all_collections = set()
    for entries in brain.values():
        for info in entries.values():
            for src in info["sources"]:
                all_collections.add(src["collection"])

    print("\n" + "=" * 60)
    print("  BRAIN INDEX SUMMARY")
    print("=" * 60)
    print(f"\n  Collections mined: {len(stats)} source collections")
    for name, count in sorted(stats.items()):
        print(f"    {name}: {count}")
    print(f"\n  Brain index:")
    print(f"    Unique keywords:    {total_keywords:,}")
    print(f"    HS code mappings:   {total_hs_mappings:,}")
    print(f"    Source references:   {total_sources:,}")
    print(f"    Collections used:    {len(all_collections)}")
    print(f"\n  Mining took {mine_time:.1f}s")

    # Top keywords by total weight
    top_kw = sorted(brain.items(), key=lambda x: sum(e["total_weight"] for e in x[1].values()), reverse=True)[:20]
    print(f"\n  Top 20 keywords by weight:")
    for kw, entries in top_kw:
        total_w = sum(e["total_weight"] for e in entries.values())
        n_hs = len(entries)
        print(f"    {kw}: weight={total_w}, hs_codes={n_hs}")

    if STATS_ONLY:
        print(f"\n  [STATS ONLY \u2014 not writing to Firestore]")
        return

    # ── Write ──
    print(f"\n\u2550\u2550\u2550 Writing brain_index \u2550\u2550\u2550")
    t1 = time.time()
    kw_written = write_brain_index()
    write_time = time.time() - t1
    total_time = time.time() - t0

    # Save metadata
    db.collection("system_metadata").document("read_everything").set({
        "last_run": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "collections_mined": len(stats),
        "unique_keywords": total_keywords,
        "hs_mappings": total_hs_mappings,
        "source_references": total_sources,
        "keywords_written": kw_written,
        "sources_detail": dict(stats),
        "mine_time_s": round(mine_time, 1),
        "write_time_s": round(write_time, 1),
        "total_time_s": round(total_time, 1),
    })

    print(f"\n  Write time: {write_time:.1f}s")
    print(f"\n" + "=" * 60)
    print(f"  DONE \u2014 Total time: {total_time:.1f}s")
    print(f"  brain_index: {kw_written:,} keywords from {len(all_collections)} collections")
    print("=" * 60)
    print(f"\n  \u2705 Run metadata saved to system_metadata/read_everything")


if __name__ == "__main__":
    run()
