"""
Deep Knowledge Learning — Mine ALL professional documents in Firestore.
======================================================================
Reads knowledge_base, declarations, classification_knowledge, sellers,
rcb_classifications — extracts HS codes, products, suppliers, rules,
cross-references everything, and enriches the inverted indexes.

No AI calls — pure Firestore reads + text parsing + index writes.

Usage:
    python deep_learn.py [--stats-only] [--dry-run]
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

DRY_RUN = "--dry-run" in sys.argv
STATS_ONLY = "--stats-only" in sys.argv

# ── HS code regex (Israeli format variations) ──
_HS_PATTERN = re.compile(
    r'(?<!\d)'
    r'(\d{4}[\.\s]?\d{2}[\.\s]?\d{2,4}(?:/\d)?)'
    r'(?!\d)'
)

# ── Stop words ──
_STOP_WORDS = {
    "the", "a", "an", "of", "for", "and", "or", "with", "to", "from",
    "in", "on", "by", "is", "are", "was", "were", "be", "been", "not",
    "this", "that", "these", "those", "has", "have", "had", "its",
    "other", "new", "used", "set", "pcs", "piece", "pieces", "item",
    "items", "type", "part", "parts", "made", "per", "each", "etc",
    "את", "של", "על", "עם", "או", "גם", "כי", "אם", "לא", "יש", "זה",
    "אל", "הם", "הוא", "היא", "בין", "כל", "מן", "אשר", "עד", "רק",
    "אין", "היו", "אחר", "לפי", "ללא", "ידי", "כגון", "וכו", "כמו",
}


def _tokenize(text):
    if not text:
        return []
    words = re.split(r'[^\w\u0590-\u05FF]+', text.lower())
    return [w for w in words if len(w) > 2 and w not in _STOP_WORDS]


def _clean_hs(code):
    if not code:
        return ""
    clean = str(code).replace(".", "").replace("/", "").replace(" ", "").strip()
    if not clean or not clean.isdigit():
        return ""
    # Valid HS codes are exactly 6, 8, or 10 digits (4+2, 4+2+2, 4+2+2+2)
    if len(clean) not in (6, 8, 10):
        return ""
    try:
        chapter = int(clean[:2])
        if chapter < 1 or chapter > 97:
            return ""
    except ValueError:
        return ""
    return clean


def _extract_hs_codes(text):
    """Extract all HS codes from text using regex."""
    if not text:
        return []
    codes = set()
    for m in _HS_PATTERN.finditer(text):
        clean = _clean_hs(m.group(1))
        if len(clean) < 6 or len(clean) > 10:
            continue
        # Reject codes starting with 00 or > 99 (valid HS chapters are 01-99)
        chapter = int(clean[:2])
        if chapter < 1 or chapter > 97:
            continue
        codes.add(clean)
    return list(codes)


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
#  MINING FUNCTIONS
# ═══════════════════════════════════════════════════════════════

# Accumulate all mined data here
mined = {
    "products": {},        # normalized_desc → {hs_code, confidence, supplier, usage_count, source}
    "suppliers": defaultdict(lambda: defaultdict(lambda: {"count": 0, "last_seen": "", "products": []})),
    "keywords": defaultdict(dict),  # keyword → {hs_code → {weight, source, description}}
    "hs_connections": defaultdict(lambda: {"suppliers": set(), "products": set(), "duty_rate": "", "origin_countries": set()}),
    "stats": defaultdict(int),
}


def mine_knowledge_base():
    """
    Read ALL knowledge_base docs. Extract HS codes, product names,
    supplier names from each document type.
    """
    print("\n═══ Mining knowledge_base ═══")
    count = 0
    type_counts = defaultdict(int)

    try:
        docs = db.collection("knowledge_base").stream()
        for doc in docs:
            data = doc.to_dict()
            doc_type = data.get("type", "unknown")
            type_counts[doc_type] += 1
            count += 1

            if doc_type == "supplier":
                _mine_kb_supplier(data)
            elif doc_type == "product":
                _mine_kb_product(data)
            elif doc_type == "web_research":
                _mine_kb_web_research(data)
            elif doc_type == "correction":
                _mine_kb_correction(data)
            else:
                # Legacy format: content dict with category
                _mine_kb_legacy(data)

    except Exception as e:
        print(f"  ⚠️ knowledge_base read error: {e}")

    mined["stats"]["knowledge_base_total"] = count
    print(f"  ✅ knowledge_base: {count} docs")
    for t, c in sorted(type_counts.items()):
        print(f"    {t}: {c}")


def _mine_kb_supplier(data):
    """Extract supplier info from knowledge_base supplier doc."""
    email = data.get("email", "")
    if not email:
        return
    # Use email domain as supplier hint
    domain = email.split("@")[-1] if "@" in email else ""
    name = _normalize_supplier(domain.split(".")[0]) if domain else ""
    if name and len(name) > 2:
        mined["stats"]["suppliers_from_kb"] += 1


def _mine_kb_product(data):
    """Extract product→HS mapping from knowledge_base product doc."""
    desc = data.get("description", "")
    hs = _clean_hs(data.get("hs_code", ""))
    supplier = data.get("supplier", "")

    if not desc:
        return

    key = re.sub(r'[^\w\u0590-\u05FF\s]', ' ', desc.lower())
    key = re.sub(r'\s+', ' ', key).strip()[:200]
    if not key:
        return

    if hs:
        if key not in mined["products"] or mined["products"][key].get("confidence", 0) < 70:
            mined["products"][key] = {
                "hs_code": hs,
                "confidence": 70,
                "usage_count": 1,
                "description": desc[:150],
                "source": "knowledge_base",
                "is_correction": False,
            }
        # Track HS connection
        mined["hs_connections"][hs]["products"].add(desc[:100])
        if supplier:
            sup_key = _normalize_supplier(supplier)
            if sup_key:
                mined["hs_connections"][hs]["suppliers"].add(sup_key)
                mined["suppliers"][sup_key][hs]["count"] += 1
                mined["suppliers"][sup_key][hs]["products"].append(desc[:80])

        # Keywords
        for kw in _tokenize(desc):
            if hs not in mined["keywords"][kw]:
                mined["keywords"][kw][hs] = {"weight": 0, "source": "knowledge_base", "description": desc[:80]}
            mined["keywords"][kw][hs]["weight"] += 2

    # Also extract any HS codes from the description text itself
    for found_hs in _extract_hs_codes(desc):
        if found_hs != hs:
            mined["hs_connections"][found_hs]["products"].add(desc[:100])

    mined["stats"]["products_from_kb"] += 1


def _mine_kb_web_research(data):
    """Extract HS codes and keywords from web research documents."""
    content = data.get("content", "")
    title = data.get("title", "")
    combined = f"{title} {content}"

    # Extract HS codes mentioned in research
    hs_codes = _extract_hs_codes(combined)
    for hs in hs_codes:
        for kw in _tokenize(combined)[:20]:
            if hs not in mined["keywords"][kw]:
                mined["keywords"][kw][hs] = {"weight": 0, "source": "web_research", "description": title[:80]}
            mined["keywords"][kw][hs]["weight"] += 1

    mined["stats"]["web_research_mined"] += 1


def _mine_kb_correction(data):
    """Extract correction data — high-confidence HS mappings."""
    original = _clean_hs(data.get("original_hs_code", ""))
    corrected = _clean_hs(data.get("corrected_hs_code", ""))
    desc = data.get("description", "")

    if corrected and desc:
        key = re.sub(r'[^\w\u0590-\u05FF\s]', ' ', desc.lower())
        key = re.sub(r'\s+', ' ', key).strip()[:200]
        if key:
            mined["products"][key] = {
                "hs_code": corrected,
                "confidence": 90,  # Corrections are very reliable
                "usage_count": data.get("usage_count", 1),
                "description": desc[:150],
                "source": "correction",
                "is_correction": True,
            }
            # Keywords with high weight
            for kw in _tokenize(desc):
                if corrected not in mined["keywords"][kw]:
                    mined["keywords"][kw][corrected] = {"weight": 0, "source": "correction", "description": desc[:80]}
                mined["keywords"][kw][corrected]["weight"] += 4  # Corrections get highest weight

    mined["stats"]["corrections_mined"] += 1


def _mine_kb_legacy(data):
    """Extract from legacy knowledge_base format (content dict with category)."""
    content = data.get("content", {})
    if isinstance(content, dict):
        hs = _clean_hs(content.get("hs", ""))
        products = content.get("products", [])
        sellers = content.get("sellers", [])

        if hs:
            for prod in products:
                if isinstance(prod, str) and prod.strip():
                    key = re.sub(r'[^\w\u0590-\u05FF\s]', ' ', prod.lower())
                    key = re.sub(r'\s+', ' ', key).strip()[:200]
                    if key and key not in mined["products"]:
                        mined["products"][key] = {
                            "hs_code": hs,
                            "confidence": 65,
                            "usage_count": 1,
                            "description": prod[:150],
                            "source": "knowledge_base_legacy",
                            "is_correction": False,
                        }
                    mined["hs_connections"][hs]["products"].add(prod[:100])

                    for kw in _tokenize(prod):
                        if hs not in mined["keywords"][kw]:
                            mined["keywords"][kw][hs] = {"weight": 0, "source": "knowledge_base_legacy", "description": prod[:80]}
                        mined["keywords"][kw][hs]["weight"] += 1

            for seller in sellers:
                if isinstance(seller, str) and seller.strip():
                    sup_key = _normalize_supplier(seller)
                    if sup_key:
                        mined["hs_connections"][hs]["suppliers"].add(sup_key)
                        mined["suppliers"][sup_key][hs]["count"] += 1

        mined["stats"]["legacy_kb_mined"] += 1
    elif isinstance(content, str) and content.strip():
        # Plain text content — extract HS codes
        for found_hs in _extract_hs_codes(content):
            for kw in _tokenize(content)[:15]:
                if found_hs not in mined["keywords"][kw]:
                    mined["keywords"][kw][found_hs] = {"weight": 0, "source": "knowledge_base_text", "description": content[:80]}
                mined["keywords"][kw][found_hs]["weight"] += 1
        mined["stats"]["text_kb_mined"] += 1


def mine_declarations():
    """
    Read ALL declarations — extract HS codes, shipper, consignee,
    origin country, quantities.
    """
    print("\n═══ Mining declarations ═══")
    count = 0
    hs_found = 0

    try:
        docs = db.collection("declarations").stream()
        for doc in docs:
            data = doc.to_dict()
            count += 1

            # Get HS code (direct field or extracted from text)
            hs = _clean_hs(data.get("hs_code", ""))
            text = data.get("extracted_text", "")
            filename = data.get("filename", "")
            from_email = data.get("from_email", "")

            # If no direct HS, try extracting from text
            if not hs and text:
                codes = _extract_hs_codes(text)
                if codes:
                    hs = codes[0]  # Take first found

            if hs:
                hs_found += 1
                mined["hs_connections"][hs]["products"].add(filename[:100] if filename else "declaration")

                # Extract supplier from email
                if from_email:
                    domain = from_email.split("@")[-1] if "@" in from_email else ""
                    sup_key = _normalize_supplier(domain.split(".")[0]) if domain else ""
                    if sup_key and len(sup_key) > 2:
                        mined["hs_connections"][hs]["suppliers"].add(sup_key)
                        mined["suppliers"][sup_key][hs]["count"] += 1

                # Extract keywords from text
                if text:
                    for kw in _tokenize(text)[:20]:
                        if hs not in mined["keywords"][kw]:
                            mined["keywords"][kw][hs] = {"weight": 0, "source": "declaration", "description": ""}
                        mined["keywords"][kw][hs]["weight"] += 1

                    # Extract origin countries
                    origin = _extract_origin_country(text)
                    if origin:
                        mined["hs_connections"][hs]["origin_countries"].add(origin)

                    # Try to find product description
                    desc = _extract_product_description(text)
                    if desc:
                        key = re.sub(r'[^\w\u0590-\u05FF\s]', ' ', desc.lower())
                        key = re.sub(r'\s+', ' ', key).strip()[:200]
                        if key and key not in mined["products"]:
                            mined["products"][key] = {
                                "hs_code": hs,
                                "confidence": 60,
                                "usage_count": 1,
                                "description": desc[:150],
                                "source": "declaration",
                                "is_correction": False,
                            }

            # Also mine ALL HS codes from text
            if text:
                for extra_hs in _extract_hs_codes(text):
                    if extra_hs != hs:
                        for kw in _tokenize(text)[:10]:
                            if extra_hs not in mined["keywords"][kw]:
                                mined["keywords"][kw][extra_hs] = {"weight": 0, "source": "declaration", "description": ""}
                            mined["keywords"][kw][extra_hs]["weight"] += 1

    except Exception as e:
        print(f"  ⚠️ declarations read error: {e}")

    mined["stats"]["declarations_total"] = count
    mined["stats"]["declarations_with_hs"] = hs_found
    print(f"  ✅ declarations: {count} docs, {hs_found} with HS codes")


def mine_classification_knowledge():
    """
    Read ALL classification_knowledge — extract patterns, boost
    existing product/keyword mappings.
    """
    print("\n═══ Mining classification_knowledge ═══")
    count = 0

    try:
        docs = db.collection("classification_knowledge").stream()
        for doc in docs:
            data = doc.to_dict()
            count += 1

            hs = _clean_hs(data.get("hs_code", ""))
            desc = data.get("description", data.get("content", ""))
            usage = data.get("usage_count", 0)
            is_corr = data.get("is_correction", False)
            duty_rate = data.get("duty_rate", "")
            supplier = data.get("source_sender", "")

            if not hs:
                continue

            # Track duty rate
            if duty_rate:
                mined["hs_connections"][hs]["duty_rate"] = duty_rate

            # Product mapping
            if desc:
                key = re.sub(r'[^\w\u0590-\u05FF\s]', ' ', desc.lower())
                key = re.sub(r'\s+', ' ', key).strip()[:200]
                if key:
                    conf = 85 if is_corr else 75
                    existing = mined["products"].get(key)
                    if not existing or existing["confidence"] < conf:
                        mined["products"][key] = {
                            "hs_code": hs,
                            "confidence": conf,
                            "usage_count": max(usage, existing["usage_count"] if existing else 0),
                            "description": desc[:150],
                            "source": "classification_knowledge",
                            "is_correction": is_corr,
                        }

                mined["hs_connections"][hs]["products"].add(desc[:100])

                # Keywords — classification_knowledge gets higher weight
                weight = 3 if is_corr else 2
                if usage >= 5:
                    weight += 1
                for kw in _tokenize(desc):
                    if hs not in mined["keywords"][kw]:
                        mined["keywords"][kw][hs] = {"weight": 0, "source": "classification_knowledge", "description": desc[:80]}
                    mined["keywords"][kw][hs]["weight"] += weight

            # Supplier tracking
            if supplier:
                sup_key = _normalize_supplier(supplier.split("@")[0] if "@" in supplier else supplier)
                if sup_key and len(sup_key) > 2:
                    mined["hs_connections"][hs]["suppliers"].add(sup_key)
                    mined["suppliers"][sup_key][hs]["count"] += max(usage, 1)

    except Exception as e:
        print(f"  ⚠️ classification_knowledge read error: {e}")

    mined["stats"]["ck_total"] = count
    print(f"  ✅ classification_knowledge: {count} docs")


def mine_rcb_classifications():
    """
    Read rcb_classifications — extract seller→HS mappings from
    actual processed emails.
    """
    print("\n═══ Mining rcb_classifications ═══")
    count = 0
    seller_hits = 0

    try:
        docs = db.collection("rcb_classifications").stream()
        for doc in docs:
            data = doc.to_dict()
            count += 1

            seller = data.get("seller", "")
            buyer = data.get("buyer", "")

            # Get classifications from nested structure
            agents = data.get("agents", {})
            cls_data = agents.get("classification", {})
            classifications = cls_data.get("classifications", [])

            # Also try top-level
            if not classifications:
                classifications = data.get("classifications", [])

            if not classifications:
                continue

            for cls in classifications:
                hs = _clean_hs(cls.get("hs_code", ""))
                item_desc = cls.get("item", cls.get("description", ""))
                duty_rate = cls.get("duty_rate", "")

                if not hs:
                    continue

                # Duty rate
                if duty_rate:
                    mined["hs_connections"][hs]["duty_rate"] = duty_rate

                # Seller → HS
                if seller:
                    sup_key = _normalize_supplier(seller)
                    if sup_key and len(sup_key) > 2:
                        mined["suppliers"][sup_key][hs]["count"] += 1
                        mined["hs_connections"][hs]["suppliers"].add(sup_key)
                        seller_hits += 1
                        if item_desc:
                            mined["suppliers"][sup_key][hs]["products"].append(item_desc[:80])

                # Product → HS
                if item_desc:
                    key = re.sub(r'[^\w\u0590-\u05FF\s]', ' ', item_desc.lower())
                    key = re.sub(r'\s+', ' ', key).strip()[:200]
                    if key and key not in mined["products"]:
                        mined["products"][key] = {
                            "hs_code": hs,
                            "confidence": 75,
                            "usage_count": 1,
                            "description": item_desc[:150],
                            "source": "rcb_classifications",
                            "is_correction": False,
                        }

                    mined["hs_connections"][hs]["products"].add(item_desc[:100])

                    # Keywords
                    for kw in _tokenize(item_desc):
                        if hs not in mined["keywords"][kw]:
                            mined["keywords"][kw][hs] = {"weight": 0, "source": "rcb_classifications", "description": item_desc[:80]}
                        mined["keywords"][kw][hs]["weight"] += 2

    except Exception as e:
        print(f"  ⚠️ rcb_classifications read error: {e}")

    mined["stats"]["rcb_total"] = count
    mined["stats"]["rcb_seller_hits"] = seller_hits
    print(f"  ✅ rcb_classifications: {count} docs, {seller_hits} seller→HS links")


# ═══════════════════════════════════════════════════════════════
#  TEXT EXTRACTION HELPERS
# ═══════════════════════════════════════════════════════════════

_ORIGIN_PATTERNS = [
    (r'(?:country\s*of\s*origin|origin\s*country|ארץ\s*המקור|ארץ\s*מקור)\s*[:\-]?\s*(\w[\w\s]{2,20})', 1),
    (r'(?:made\s*in|manufactured\s*in|produced\s*in)\s+(\w[\w\s]{2,20})', 1),
    (r'(?:מיוצר\s*ב|מקור\s*[:\-])\s*(\w[\w\s]{2,20})', 1),
]

def _extract_origin_country(text):
    """Try to extract origin country from text."""
    if not text:
        return ""
    text_lower = text.lower()[:3000]
    for pattern, group in _ORIGIN_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            country = m.group(group).strip()
            # Clean up
            country = re.sub(r'\s+', ' ', country).strip()
            if len(country) > 2 and len(country) < 30:
                return country
    return ""


def _extract_product_description(text):
    """Try to extract main product description from declaration text."""
    if not text:
        return ""
    text_lower = text[:2000]
    # Look for common patterns
    patterns = [
        r'(?:description\s*of\s*goods|goods\s*description|תיאור\s*הסחורה)\s*[:\-]?\s*(.{10,100})',
        r'(?:commodity|product)\s*[:\-]\s*(.{10,100})',
        r'(?:פריט|תיאור)\s*[:\-]\s*(.{10,100})',
    ]
    for p in patterns:
        m = re.search(p, text_lower, re.IGNORECASE)
        if m:
            desc = m.group(1).strip()
            desc = re.sub(r'\s+', ' ', desc)
            return desc[:150]
    return ""


# ═══════════════════════════════════════════════════════════════
#  WRITE ENRICHED INDEXES
# ═══════════════════════════════════════════════════════════════

def write_enriched_indexes():
    """Write all mined data back to Firestore indexes."""
    print("\n═══ Writing enriched indexes ═══")
    t0 = time.time()

    # ── 1. Merge into keyword_index ──
    print("  Merging into keyword_index...")
    kw_written = 0
    batch = db.batch()
    batch_count = 0

    for keyword, hs_entries in mined["keywords"].items():
        if not hs_entries:
            continue

        doc_id = _safe_doc_id(keyword)
        if not doc_id:
            continue

        # Read existing keyword_index doc to merge
        try:
            existing_doc = db.collection("keyword_index").document(doc_id).get()
            existing_codes = {}
            if existing_doc.exists:
                for entry in existing_doc.to_dict().get("codes", []):
                    existing_codes[entry["hs_code"]] = entry
        except Exception:
            existing_codes = {}

        # Merge new data
        for hs, info in hs_entries.items():
            if hs in existing_codes:
                existing_codes[hs]["weight"] += info["weight"]
                # Keep better description
                if info["description"] and not existing_codes[hs].get("description"):
                    existing_codes[hs]["description"] = info["description"]
            else:
                existing_codes[hs] = {
                    "hs_code": hs,
                    "weight": info["weight"],
                    "source": info["source"],
                    "description": info["description"],
                }

        # Sort by weight, keep top 20
        sorted_entries = sorted(existing_codes.values(), key=lambda x: x.get("weight", 0), reverse=True)[:20]

        ref = db.collection("keyword_index").document(doc_id)
        batch.set(ref, {
            "keyword": keyword,
            "codes": sorted_entries,
            "count": len(sorted_entries),
            "built_at": datetime.now(timezone.utc).isoformat(),
            "enriched": True,
        })

        batch_count += 1
        kw_written += 1
        if batch_count >= 450:
            batch.commit()
            batch = db.batch()
            batch_count = 0
            if kw_written % 2000 == 0:
                print(f"    ...{kw_written} keyword entries merged")

    if batch_count > 0:
        batch.commit()
    print(f"  ✅ keyword_index: {kw_written} entries merged")

    # ── 2. Merge into product_index ──
    print("  Merging into product_index...")
    prod_written = 0
    batch = db.batch()
    batch_count = 0

    for key, info in mined["products"].items():
        if not info.get("hs_code"):
            continue

        doc_id = _safe_doc_id(key)
        if not doc_id:
            continue

        # Check if existing entry has higher confidence
        try:
            existing = db.collection("product_index").document(doc_id).get()
            if existing.exists:
                ex_data = existing.to_dict()
                if ex_data.get("confidence", 0) > info["confidence"]:
                    # Existing is better — just bump usage_count
                    ref = db.collection("product_index").document(doc_id)
                    batch.set(ref, {
                        **ex_data,
                        "usage_count": max(ex_data.get("usage_count", 0), info["usage_count"]),
                        "enriched_at": datetime.now(timezone.utc).isoformat(),
                    })
                    batch_count += 1
                    prod_written += 1
                    if batch_count >= 450:
                        batch.commit()
                        batch = db.batch()
                        batch_count = 0
                    continue
        except Exception:
            pass

        ref = db.collection("product_index").document(doc_id)
        batch.set(ref, {
            "product_key": key,
            **info,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "enriched": True,
        })
        batch_count += 1
        prod_written += 1
        if batch_count >= 450:
            batch.commit()
            batch = db.batch()
            batch_count = 0

    if batch_count > 0:
        batch.commit()
    print(f"  ✅ product_index: {prod_written} entries merged")

    # ── 3. Merge into supplier_index ──
    print("  Merging into supplier_index...")
    supp_written = 0
    batch = db.batch()
    batch_count = 0

    for name, hs_entries in mined["suppliers"].items():
        if not hs_entries:
            continue

        doc_id = _safe_doc_id(name)
        if not doc_id:
            continue

        # Read existing
        try:
            existing = db.collection("supplier_index").document(doc_id).get()
            existing_codes = {}
            if existing.exists:
                for entry in existing.to_dict().get("codes", []):
                    existing_codes[entry["hs_code"]] = entry
        except Exception:
            existing_codes = {}

        # Merge
        for hs, info in hs_entries.items():
            if hs in existing_codes:
                existing_codes[hs]["count"] += info["count"]
            else:
                existing_codes[hs] = {
                    "hs_code": hs,
                    "count": info["count"],
                    "last_seen": info["last_seen"],
                }

        sorted_codes = sorted(existing_codes.values(), key=lambda x: x.get("count", 0), reverse=True)[:30]

        ref = db.collection("supplier_index").document(doc_id)
        batch.set(ref, {
            "supplier_name": name,
            "codes": sorted_codes,
            "total_hs_codes": len(sorted_codes),
            "total_shipments": sum(c["count"] for c in sorted_codes),
            "built_at": datetime.now(timezone.utc).isoformat(),
            "enriched": True,
        })
        batch_count += 1
        supp_written += 1
        if batch_count >= 450:
            batch.commit()
            batch = db.batch()
            batch_count = 0

    if batch_count > 0:
        batch.commit()
    print(f"  ✅ supplier_index: {supp_written} entries merged")

    elapsed = time.time() - t0
    print(f"  Total write time: {elapsed:.1f}s")

    return kw_written, prod_written, supp_written


# ═══════════════════════════════════════════════════════════════
#  PRINT STATS
# ═══════════════════════════════════════════════════════════════

def print_stats():
    """Print summary of all mined data."""
    print("\n" + "=" * 60)
    print("  DEEP LEARN — MINING SUMMARY")
    print("=" * 60)

    print(f"\n  Sources mined:")
    for k, v in sorted(mined["stats"].items()):
        print(f"    {k}: {v}")

    print(f"\n  Mined totals:")
    print(f"    Products:          {len(mined['products'])}")
    print(f"    Suppliers:         {len(mined['suppliers'])}")
    print(f"    Keywords:          {len(mined['keywords'])}")
    print(f"    HS connections:    {len(mined['hs_connections'])}")

    # Top products
    if mined["products"]:
        print(f"\n  Top 15 products (by confidence):")
        top = sorted(mined["products"].items(), key=lambda x: x[1]["confidence"], reverse=True)[:15]
        for key, info in top:
            print(f"    '{key[:50]}' → HS {info['hs_code']} "
                  f"(conf={info['confidence']}%, src={info['source']})")

    # Top suppliers
    if mined["suppliers"]:
        print(f"\n  Suppliers and their HS codes:")
        for name, codes in sorted(mined["suppliers"].items()):
            sorted_codes = sorted(codes.items(), key=lambda x: x[1]["count"], reverse=True)
            hs_list = ", ".join(f"HS {hs} (×{info['count']})" for hs, info in sorted_codes[:5])
            print(f"    '{name}' → {hs_list}")

    # HS connections
    if mined["hs_connections"]:
        print(f"\n  Top 15 HS codes (by connections):")
        top = sorted(mined["hs_connections"].items(),
                     key=lambda x: len(x[1]["products"]) + len(x[1]["suppliers"]), reverse=True)[:15]
        for hs, info in top:
            prods = len(info["products"])
            supps = len(info["suppliers"])
            duty = info["duty_rate"] or "unknown"
            origins = ", ".join(list(info["origin_countries"])[:3]) if info["origin_countries"] else "-"
            print(f"    HS {hs}: {prods} products, {supps} suppliers, duty={duty}, origins={origins}")


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def run():
    print("=" * 60)
    print("  DEEP KNOWLEDGE LEARNING")
    print(f"  Mode: {'DRY RUN' if DRY_RUN else 'STATS ONLY' if STATS_ONLY else 'LIVE WRITE'}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    t0 = time.time()

    # Mine all sources
    mine_knowledge_base()
    mine_declarations()
    mine_classification_knowledge()
    mine_rcb_classifications()

    # Print stats
    print_stats()

    # Write enriched indexes
    if not STATS_ONLY and not DRY_RUN:
        kw, prod, supp = write_enriched_indexes()

        elapsed = time.time() - t0
        print("\n" + "=" * 60)
        print("  FINAL SUMMARY")
        print(f"  keyword_index:  {kw} entries enriched")
        print(f"  product_index:  {prod} entries enriched")
        print(f"  supplier_index: {supp} entries enriched")
        print(f"  Total time:     {elapsed:.1f}s")
        print("=" * 60)

        # Save metadata
        try:
            db.collection("system_metadata").document("deep_learn").set({
                "last_run": datetime.now(timezone.utc).isoformat(),
                "keywords_enriched": kw,
                "products_enriched": prod,
                "suppliers_enriched": supp,
                "duration_seconds": round(elapsed, 1),
                "sources": dict(mined["stats"]),
            })
            print("\n  ✅ Run metadata saved to system_metadata/deep_learn")
        except Exception as e:
            print(f"\n  ⚠️ Failed to save metadata: {e}")
    else:
        elapsed = time.time() - t0
        print(f"\n  Mining took {elapsed:.1f}s")
        if DRY_RUN:
            print("  [DRY RUN — not writing to Firestore]")
        elif STATS_ONLY:
            print("  [STATS ONLY — not writing to Firestore]")


if __name__ == "__main__":
    run()
