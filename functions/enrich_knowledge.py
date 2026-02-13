"""
Enrich Knowledge — Reclassify, extract, and link Firestore data.
================================================================
1. Reclassify 256 untyped knowledge_base docs by their category field.
   Extract HS codes, product names, supplier names from content.
2. Extract seller→HS links from rcb_classifications (classifications,
   invoice_data fields).
3. Parse declarations for real HS codes (the hs_code field is a filing number).

No AI calls — pure Firestore reads + text parsing + index writes.

Usage:
    python enrich_knowledge.py [--stats-only]
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

# ── HS code regex ──
_HS_PATTERN = re.compile(
    r'(?<!\d)'
    r'(\d{4}[\.\s]?\d{2}[\.\s]?\d{2,4}(?:/\d)?)'
    r'(?!\d)'
)

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
    # Reject dates that look like HS codes (20YYMMDD, 19YYMMDD)
    if len(clean) == 8 and clean[:2] in ("20", "19"):
        month = int(clean[4:6])
        day = int(clean[6:8])
        if 1 <= month <= 12 and 1 <= day <= 31:
            return ""
    return clean


def _extract_hs_codes(text):
    if not text:
        return []
    codes = set()
    for m in _HS_PATTERN.finditer(str(text)):
        clean = _clean_hs(m.group(1))
        if clean:
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


def _normalize_product(desc):
    if not desc:
        return ""
    text = desc.lower().strip()
    text = re.sub(r'[^\w\u0590-\u05FF\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:200] if text else ""


def _tokenize(text):
    if not text:
        return []
    words = re.split(r'[^\w\u0590-\u05FF]+', text.lower())
    return [w for w in words if len(w) > 2 and w not in _STOP_WORDS]


# ═══════════════════════════════════════════════════════════════
#  CATEGORY → TYPE MAPPING
# ═══════════════════════════════════════════════════════════════

_CATEGORY_TO_TYPE = {
    "pupil_suggestion":       "classification_rule",
    "hs_classifications":     "product",
    "invoice_patterns":       "reference_map",
    "document_formats":       "general",
    "customs_procedures":     "customs_procedure",
    "standards_compliance":   "general",
    "compliance_management":  "general",
}


# ═══════════════════════════════════════════════════════════════
#  TASK 1: Reclassify knowledge_base docs
# ═══════════════════════════════════════════════════════════════

def enrich_knowledge_base():
    print("\n═══ Task 1: Reclassify knowledge_base docs ═══")
    all_docs = list(db.collection("knowledge_base").stream())

    untyped = []
    for d in all_docs:
        data = d.to_dict()
        if "type" not in data:
            untyped.append((d.id, d.reference, data))

    print(f"  Total docs: {len(all_docs)}, untyped: {len(untyped)}")

    # Classify and extract
    reclassified = defaultdict(int)
    hs_extracted = []
    products_extracted = []
    suppliers_extracted = []
    updates = []  # (doc_ref, update_dict)

    for doc_id, doc_ref, data in untyped:
        category = data.get("category", data.get("source", ""))
        content = data.get("content", "")
        title = data.get("title", "")

        # Determine new type
        new_type = _CATEGORY_TO_TYPE.get(category, "general")

        # Port tariff docs
        if "port tariff" in str(data.get("source", "")).lower():
            new_type = "port_tariff"
        if "port tariff" in str(category).lower():
            new_type = "port_tariff"

        update = {"type": new_type}

        # ── Extract HS codes ──
        hs_codes = []

        # From content dict
        if isinstance(content, dict):
            hs_raw = content.get("hs", "")
            if hs_raw:
                if isinstance(hs_raw, list):
                    for h in hs_raw:
                        c = _clean_hs(h)
                        if c:
                            hs_codes.append(c)
                else:
                    c = _clean_hs(hs_raw)
                    if c:
                        hs_codes.append(c)

        # From content text (pupil_suggestion)
        if isinstance(content, str):
            hs_codes.extend(_extract_hs_codes(content))

        # From title
        hs_codes.extend(_extract_hs_codes(title))

        # From teaching_rule, method fields
        for field in ("teaching_rule", "method"):
            hs_codes.extend(_extract_hs_codes(str(data.get(field, ""))))

        hs_codes = list(set(hs_codes))
        if hs_codes:
            update["hs_codes_extracted"] = hs_codes
            for h in hs_codes:
                hs_extracted.append({"hs": h, "source": doc_id, "category": category})

        # ── Extract products ──
        products = []
        if isinstance(content, dict):
            prods = content.get("products", [])
            if isinstance(prods, list):
                for p in prods:
                    norm = _normalize_product(str(p))
                    if norm and len(norm) > 2:
                        products.append(norm)

        # From title (for pupil_suggestion, extract quoted product names)
        if category == "pupil_suggestion" and title:
            # Extract text between quotes
            quoted = re.findall(r"'([^']+)'|\"([^\"]+)\"", title)
            for q in quoted:
                prod = _normalize_product(q[0] or q[1])
                if prod and len(prod) > 2:
                    products.append(prod)

        products = list(set(products))
        if products:
            update["products_extracted"] = products
            for p in products:
                products_extracted.append({"product": p, "hs_codes": hs_codes, "source": doc_id})

        # ── Extract suppliers ──
        suppliers = []
        if isinstance(content, dict):
            seller = content.get("seller", "")
            buyer = content.get("buyer", "")
            if seller:
                norm = _normalize_supplier(seller)
                if norm and len(norm) > 2:
                    suppliers.append(norm)
            if buyer:
                norm = _normalize_supplier(buyer)
                if norm and len(norm) > 2:
                    suppliers.append(norm)

        suppliers = list(set(suppliers))
        if suppliers:
            update["suppliers_extracted"] = suppliers
            for s in suppliers:
                suppliers_extracted.append({"supplier": s, "hs_codes": hs_codes, "source": doc_id})

        update["enriched_at"] = datetime.now(timezone.utc).isoformat()
        reclassified[new_type] += 1
        updates.append((doc_ref, update))

    # Print stats
    print(f"\n  Reclassification:")
    for t, c in sorted(reclassified.items(), key=lambda x: -x[1]):
        print(f"    {t}: {c}")
    print(f"\n  Extracted:")
    print(f"    HS codes:  {len(hs_extracted)} (from {len(set(e['source'] for e in hs_extracted))} docs)")
    print(f"    Products:  {len(products_extracted)}")
    print(f"    Suppliers: {len(suppliers_extracted)}")

    # Show top HS codes
    hs_count = defaultdict(int)
    for e in hs_extracted:
        hs_count[e["hs"]] += 1
    if hs_count:
        print(f"\n  Top extracted HS codes:")
        for h, c in sorted(hs_count.items(), key=lambda x: -x[1])[:15]:
            print(f"    {h}: found in {c} docs")

    return updates, hs_extracted, products_extracted, suppliers_extracted


# ═══════════════════════════════════════════════════════════════
#  TASK 2: Extract seller→HS from rcb_classifications
# ═══════════════════════════════════════════════════════════════

def enrich_rcb_classifications():
    print("\n═══ Task 2: Extract seller→HS from rcb_classifications ═══")
    all_docs = list(db.collection("rcb_classifications").stream())
    print(f"  Total docs: {len(all_docs)}")

    seller_hs = defaultdict(lambda: defaultdict(lambda: {
        "count": 0, "last_seen": "", "products": [], "countries": set()
    }))
    product_links = {}  # product → {hs_code, confidence, source}
    total_links = 0
    sellers_no_hs = {}  # sellers found but without HS codes yet

    for d in all_docs:
        data = d.to_dict()
        timestamp = str(data.get("timestamp", ""))

        # Find seller name from multiple locations
        seller = ""
        seller_raw = data.get("seller", "")
        if seller_raw:
            seller = _normalize_supplier(seller_raw)

        # Check invoice_data.seller
        inv_data = data.get("invoice_data", {})
        if isinstance(inv_data, dict) and not seller:
            inv_seller = inv_data.get("seller", "")
            if inv_seller:
                seller = _normalize_supplier(inv_seller)

        # Try subject line: "seller → buyer" pattern
        if not seller:
            subject = data.get("subject", "")
            arrow_match = re.search(r'[\|]\s*(.+?)\s*→\s*(.+?)\s*[\|]', subject)
            if arrow_match:
                seller = _normalize_supplier(arrow_match.group(1))

        if not seller:
            continue

        found_hs_for_seller = False

        # Extract HS codes from classifications array
        classifications = data.get("classifications", [])
        if isinstance(classifications, list):
            for cls in classifications:
                if not isinstance(cls, dict):
                    continue
                hs_raw = cls.get("hs_code", "")
                hs = _clean_hs(hs_raw)
                item = cls.get("item", cls.get("description", ""))
                duty = cls.get("duty_rate", "")

                if hs and item:
                    seller_hs[seller][hs]["count"] += 1
                    seller_hs[seller][hs]["last_seen"] = timestamp
                    norm_prod = _normalize_product(item)
                    if norm_prod and norm_prod not in seller_hs[seller][hs]["products"]:
                        seller_hs[seller][hs]["products"].append(norm_prod)
                    total_links += 1
                    found_hs_for_seller = True

                    if norm_prod and norm_prod not in product_links:
                        product_links[norm_prod] = {
                            "hs_code": hs,
                            "confidence": 70,
                            "source": "rcb_classifications",
                            "description": item[:150],
                            "duty_rate": duty,
                        }

        # Extract from invoice_data.items
        if isinstance(inv_data, dict):
            items = inv_data.get("items", [])
            if isinstance(items, list):
                for item_entry in items:
                    if not isinstance(item_entry, dict):
                        continue
                    desc = item_entry.get("description", "")
                    country = item_entry.get("origin_country", "")

                    # Try to extract HS from description text
                    hs_from_desc = _extract_hs_codes(desc)
                    for hs in hs_from_desc:
                        seller_hs[seller][hs]["count"] += 1
                        seller_hs[seller][hs]["last_seen"] = timestamp
                        if country:
                            seller_hs[seller][hs]["countries"].add(country)
                        total_links += 1
                        found_hs_for_seller = True

                    # Link countries to HS codes from classifications
                    if country and isinstance(classifications, list):
                        for cls in classifications:
                            if not isinstance(cls, dict):
                                continue
                            hs = _clean_hs(cls.get("hs_code", ""))
                            if hs:
                                seller_hs[seller][hs]["countries"].add(country)

        # Also check synthesis field for HS codes
        synthesis = data.get("synthesis", "")
        if synthesis and not found_hs_for_seller:
            synth_hs = _extract_hs_codes(str(synthesis))
            for hs in synth_hs:
                seller_hs[seller][hs]["count"] += 1
                seller_hs[seller][hs]["last_seen"] = timestamp
                total_links += 1
                found_hs_for_seller = True

        # Track sellers even without HS (for supplier_index awareness)
        if not found_hs_for_seller:
            buyer = _normalize_supplier(data.get("buyer", ""))
            sellers_no_hs[seller] = {
                "last_seen": timestamp,
                "buyer": buyer,
                "direction": data.get("direction", ""),
            }

    print(f"  Sellers with HS links: {len(seller_hs)}")
    print(f"  Sellers without HS:    {len(sellers_no_hs)}")
    print(f"  Total seller→HS links: {total_links}")
    print(f"  Products extracted: {len(product_links)}")

    if seller_hs:
        print(f"\n  Seller→HS mappings:")
        for seller, codes in sorted(seller_hs.items()):
            hs_list = []
            for hs, info in sorted(codes.items()):
                prods = ", ".join(info["products"][:2]) if info["products"] else ""
                countries = ", ".join(info["countries"]) if info["countries"] else ""
                parts = [hs]
                if prods:
                    parts.append(f"({prods})")
                if countries:
                    parts.append(f"[{countries}]")
                hs_list.append(" ".join(parts))
            print(f"    {seller}: {'; '.join(hs_list)}")

    return seller_hs, product_links


# ═══════════════════════════════════════════════════════════════
#  TASK 3: Parse declarations for real HS codes
# ═══════════════════════════════════════════════════════════════

def enrich_declarations():
    print("\n═══ Task 3: Parse declarations for real HS codes ═══")
    all_docs = list(db.collection("declarations").stream())
    print(f"  Total docs: {len(all_docs)}")

    real_hs_found = []
    filing_numbers = []
    updates = []

    for d in all_docs:
        data = d.to_dict()
        filename = data.get("filename", "")
        stored_hs = data.get("hs_code", "")
        extracted_text = data.get("extracted_text", "")
        matched_cls = data.get("matched_classification", "")

        # The stored hs_code is a filing number, not a real HS code
        filing_numbers.append({"id": d.id, "filename": filename, "filing": stored_hs})

        found_hs = []

        # Try to extract HS from the filename itself
        # Patterns: IMP_DEC_YYMM... or WG_Declaration_YYMM...
        # The numbers after prefix are filing numbers, not HS codes

        # Extract from extracted_text (often garbled CID, but try)
        if extracted_text and "(cid:" not in str(extracted_text)[:50]:
            # Only try if text is not garbled CID references
            found_hs.extend(_extract_hs_codes(extracted_text))

        # Extract from matched_classification if present
        if matched_cls:
            if isinstance(matched_cls, dict):
                cls_hs = matched_cls.get("hs_code", "")
                c = _clean_hs(cls_hs)
                if c:
                    found_hs.append(c)
            elif isinstance(matched_cls, str):
                found_hs.extend(_extract_hs_codes(matched_cls))

        found_hs = list(set(found_hs))
        if found_hs:
            real_hs_found.append({
                "id": d.id,
                "filename": filename,
                "hs_codes": found_hs,
                "filing_number": stored_hs,
            })
            updates.append((d.reference, {
                "hs_codes_real": found_hs,
                "hs_code_is_filing": True,
                "enriched_at": datetime.now(timezone.utc).isoformat(),
            }))
        elif stored_hs:
            # Mark that the existing hs_code is a filing number
            updates.append((d.reference, {
                "hs_code_is_filing": True,
                "enriched_at": datetime.now(timezone.utc).isoformat(),
            }))

    print(f"  Filing numbers (not HS): {len(filing_numbers)}")
    print(f"  Docs with real HS found: {len(real_hs_found)}")
    print(f"  Docs to update: {len(updates)}")

    if real_hs_found:
        print(f"\n  Real HS codes found:")
        for entry in real_hs_found[:15]:
            print(f"    {entry['filename']}: {', '.join(entry['hs_codes'])} (filing={entry['filing_number']})")

    return updates, real_hs_found


# ═══════════════════════════════════════════════════════════════
#  WRITE RESULTS TO FIRESTORE
# ═══════════════════════════════════════════════════════════════

def write_kb_updates(updates):
    """Write knowledge_base reclassification updates."""
    print(f"\n  Writing {len(updates)} knowledge_base updates...")
    batch = db.batch()
    count = 0
    for doc_ref, update_dict in updates:
        batch.update(doc_ref, update_dict)
        count += 1
        if count % 450 == 0:
            batch.commit()
            batch = db.batch()
    if count % 450 != 0:
        batch.commit()
    print(f"  \u2705 {count} knowledge_base docs reclassified")


def write_supplier_index(seller_hs):
    """Merge seller→HS data into supplier_index."""
    print(f"\n  Merging {len(seller_hs)} sellers into supplier_index...")
    now = datetime.now(timezone.utc).isoformat()
    batch = db.batch()
    count = 0

    for seller, codes_dict in seller_hs.items():
        doc_id = _safe_doc_id(seller)
        doc_ref = db.collection("supplier_index").document(doc_id)

        # Read existing
        existing = doc_ref.get()
        existing_codes = {}
        total_shipments = 0
        if existing.exists:
            edata = existing.to_dict()
            for c in edata.get("codes", []):
                existing_codes[c["hs_code"]] = c
            total_shipments = edata.get("total_shipments", 0)

        # Merge new data
        for hs, info in codes_dict.items():
            if hs in existing_codes:
                existing_codes[hs]["count"] += info["count"]
                if info["last_seen"]:
                    existing_codes[hs]["last_seen"] = info["last_seen"]
            else:
                entry = {
                    "hs_code": hs,
                    "count": info["count"],
                    "last_seen": info["last_seen"],
                }
                if info["products"]:
                    entry["products"] = info["products"][:5]
                if info["countries"]:
                    entry["countries"] = list(info["countries"])
                existing_codes[hs] = entry
            total_shipments += info["count"]

        codes_list = sorted(existing_codes.values(), key=lambda x: -x["count"])[:30]

        batch.set(doc_ref, {
            "supplier_name": seller,
            "codes": codes_list,
            "total_hs_codes": len(codes_list),
            "total_shipments": total_shipments,
            "built_at": now,
            "enriched": True,
        })
        count += 1
        if count % 450 == 0:
            batch.commit()
            batch = db.batch()

    if count % 450 != 0:
        batch.commit()
    print(f"  \u2705 supplier_index: {count} entries merged")


def write_product_index(product_links):
    """Merge product→HS data into product_index."""
    print(f"\n  Merging {len(product_links)} products into product_index...")
    now = datetime.now(timezone.utc).isoformat()
    batch = db.batch()
    count = 0

    for prod, info in product_links.items():
        doc_id = _safe_doc_id(prod)
        doc_ref = db.collection("product_index").document(doc_id)

        existing = doc_ref.get()
        if existing.exists:
            edata = existing.to_dict()
            if edata.get("confidence", 0) >= info["confidence"]:
                # Existing entry has higher confidence, just bump usage
                batch.update(doc_ref, {
                    "usage_count": firestore.Increment(1),
                    "last_seen": now,
                })
                count += 1
                if count % 450 == 0:
                    batch.commit()
                    batch = db.batch()
                continue

        batch.set(doc_ref, {
            "product_key": prod,
            "hs_code": info["hs_code"],
            "confidence": info["confidence"],
            "usage_count": 1,
            "description": info["description"],
            "source": info["source"],
            "is_correction": False,
            "last_seen": now,
            "built_at": now,
            "enriched": True,
        })
        count += 1
        if count % 450 == 0:
            batch.commit()
            batch = db.batch()

    if count % 450 != 0:
        batch.commit()
    print(f"  \u2705 product_index: {count} entries merged")


def write_keyword_index(hs_extracted, products_extracted):
    """Add newly found HS codes and products to keyword_index."""
    # Build keyword → hs_code mappings from extracted data
    kw_map = defaultdict(lambda: defaultdict(lambda: {"weight": 0, "source": "", "description": ""}))

    for entry in products_extracted:
        product = entry["product"]
        for hs in entry["hs_codes"]:
            for token in _tokenize(product):
                kw_map[token][hs]["weight"] += 2
                kw_map[token][hs]["source"] = "knowledge_base_enriched"
                kw_map[token][hs]["description"] = product[:80]

    if not kw_map:
        print(f"\n  No new keywords to merge")
        return

    print(f"\n  Merging {len(kw_map)} keywords into keyword_index...")
    now = datetime.now(timezone.utc).isoformat()
    batch = db.batch()
    count = 0

    for keyword, codes_dict in kw_map.items():
        doc_id = _safe_doc_id(keyword)
        doc_ref = db.collection("keyword_index").document(doc_id)

        existing = doc_ref.get()
        existing_codes = {}
        if existing.exists:
            edata = existing.to_dict()
            for c in edata.get("codes", []):
                existing_codes[c["hs_code"]] = c

        for hs, info in codes_dict.items():
            if hs in existing_codes:
                existing_codes[hs]["weight"] = existing_codes[hs].get("weight", 0) + info["weight"]
            else:
                existing_codes[hs] = {
                    "hs_code": hs,
                    "weight": info["weight"],
                    "source": info["source"],
                    "description": info["description"],
                }

        codes_list = sorted(existing_codes.values(), key=lambda x: -x.get("weight", 0))[:20]

        batch.set(doc_ref, {
            "keyword": keyword,
            "codes": codes_list,
            "count": len(codes_list),
            "built_at": now,
            "enriched": True,
        })
        count += 1
        if count % 450 == 0:
            batch.commit()
            batch = db.batch()

    if count % 450 != 0:
        batch.commit()
    print(f"  \u2705 keyword_index: {count} entries merged")


def write_declaration_updates(updates):
    """Write declaration enrichment flags."""
    print(f"\n  Writing {len(updates)} declaration updates...")
    batch = db.batch()
    count = 0
    for doc_ref, update_dict in updates:
        batch.update(doc_ref, update_dict)
        count += 1
        if count % 450 == 0:
            batch.commit()
            batch = db.batch()
    if count % 450 != 0:
        batch.commit()
    print(f"  \u2705 {count} declarations updated")


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def run():
    mode = "STATS ONLY" if STATS_ONLY else "LIVE WRITE"
    print("=" * 60)
    print(f"  ENRICH KNOWLEDGE")
    print(f"  Mode: {mode}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    t0 = time.time()

    # Task 1
    kb_updates, hs_extracted, products_extracted, suppliers_extracted = enrich_knowledge_base()

    # Task 2
    seller_hs, product_links = enrich_rcb_classifications()

    # Task 3
    dec_updates, real_hs_found = enrich_declarations()

    # ── Summary ──
    elapsed = time.time() - t0
    print("\n" + "=" * 60)
    print("  ENRICHMENT SUMMARY")
    print("=" * 60)
    print(f"\n  Task 1 — Knowledge Base:")
    print(f"    Docs reclassified: {len(kb_updates)}")
    print(f"    HS codes found:    {len(hs_extracted)}")
    print(f"    Products found:    {len(products_extracted)}")
    print(f"    Suppliers found:   {len(suppliers_extracted)}")
    print(f"\n  Task 2 — RCB Classifications:")
    print(f"    Sellers with HS:   {len(seller_hs)}")
    print(f"    Products mapped:   {len(product_links)}")
    print(f"\n  Task 3 — Declarations:")
    print(f"    Real HS found:     {len(real_hs_found)}")
    print(f"    Docs to update:    {len(dec_updates)}")
    print(f"\n  Analysis took {elapsed:.1f}s")

    if STATS_ONLY:
        print(f"  [STATS ONLY \u2014 not writing to Firestore]")
        return

    # ── Write ──
    print("\n\u2550\u2550\u2550 Writing enrichments \u2550\u2550\u2550")
    t1 = time.time()

    write_kb_updates(kb_updates)
    write_supplier_index(seller_hs)
    write_product_index(product_links)
    write_keyword_index(hs_extracted, products_extracted)
    write_declaration_updates(dec_updates)

    write_time = time.time() - t1
    total_time = time.time() - t0

    # Save metadata
    db.collection("system_metadata").document("enrich_knowledge").set({
        "last_run": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "kb_reclassified": len(kb_updates),
        "hs_extracted": len(hs_extracted),
        "products_extracted": len(products_extracted),
        "suppliers_extracted": len(suppliers_extracted),
        "sellers_with_hs": len(seller_hs),
        "rcb_products": len(product_links),
        "declarations_real_hs": len(real_hs_found),
        "declarations_updated": len(dec_updates),
        "write_time_s": round(write_time, 1),
        "total_time_s": round(total_time, 1),
    })

    print(f"\n  Write time: {write_time:.1f}s")
    print(f"\n" + "=" * 60)
    print(f"  DONE — Total time: {total_time:.1f}s")
    print("=" * 60)
    print(f"\n  \u2705 Run metadata saved to system_metadata/enrich_knowledge")


if __name__ == "__main__":
    run()
