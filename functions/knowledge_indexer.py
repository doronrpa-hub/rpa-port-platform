"""
Knowledge Indexer — Build inverted indexes for fast HS code lookup.
==================================================================
Reads tariff (11,753 docs), classification_knowledge, and sellers,
builds keyword→HS, product→HS, and supplier→HS inverted indexes,
stores them in Firestore for pre_classify() to use.

Usage:
    python knowledge_indexer.py [--dry-run] [--stats-only]

Collections written:
    keyword_index   — keyword → list of {hs_code, weight, source}
    product_index   — product description → {hs_code, confidence, usage_count}
    supplier_index  — supplier name → list of {hs_code, last_seen, count}
"""

import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

# ── Firebase setup (same as import_knowledge.py) ──
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

# ── Stop words (English + Hebrew) ──
_STOP_WORDS = {
    # English
    "the", "a", "an", "of", "for", "and", "or", "with", "to", "from",
    "in", "on", "by", "is", "are", "was", "were", "be", "been", "not",
    "this", "that", "these", "those", "has", "have", "had", "its",
    "other", "new", "used", "set", "pcs", "piece", "pieces", "item",
    "items", "type", "part", "parts", "made", "per", "each", "etc",
    "including", "also", "than", "more", "all", "any", "such", "into",
    "being", "between", "through", "only", "over", "but", "about",
    # Hebrew
    "את", "של", "על", "עם", "או", "גם", "כי", "אם", "לא", "יש", "זה",
    "אל", "הם", "הוא", "היא", "בין", "כל", "מן", "אשר", "עד", "רק",
    "אין", "היו", "אחר", "לפי", "ללא", "ידי", "כגון", "וכו", "כמו",
}


def _tokenize(text):
    """Split text into meaningful keywords, filtering stop words."""
    if not text:
        return []
    words = re.split(r'[^\w\u0590-\u05FF]+', text.lower())
    return [w for w in words if len(w) > 2 and w not in _STOP_WORDS]


def _clean_hs(code):
    """Normalize HS code: strip dots, slashes, spaces."""
    if not code:
        return ""
    return str(code).replace(".", "").replace("/", "").replace(" ", "").strip()


# ═══════════════════════════════════════════════════════════════
#  1. KEYWORD INDEX — keyword → [{hs_code, weight, source}]
# ═══════════════════════════════════════════════════════════════

def build_keyword_index():
    """
    Read ALL tariff + tariff_chapters + hs_code_index entries.
    For each document, extract keywords from Hebrew + English descriptions.
    Build: keyword → list of {hs_code, weight, source}.
    Weight = how strongly this keyword indicates this HS code.
    """
    print("\n═══ Building keyword_index ═══")
    # keyword → {hs_code → {weight, source, description}}
    kw_map = defaultdict(dict)
    doc_count = 0

    # ── tariff collection (11,753 docs) ──
    print("  Reading tariff collection...")
    t0 = time.time()
    try:
        docs = db.collection("tariff").stream()
        for doc in docs:
            data = doc.to_dict()
            hs = _clean_hs(data.get("hs_code", ""))
            if not hs or len(hs) < 4:
                continue

            desc_he = data.get("description_he", "")
            desc_en = data.get("description_en", "")
            combined = f"{desc_he} {desc_en}"
            keywords = _tokenize(combined)

            for kw in keywords:
                if hs not in kw_map[kw]:
                    kw_map[kw][hs] = {
                        "weight": 0,
                        "source": "tariff",
                        "description": (desc_he or desc_en)[:80],
                    }
                kw_map[kw][hs]["weight"] += 1

            doc_count += 1
            if doc_count % 2000 == 0:
                print(f"    ...{doc_count} tariff docs processed")
    except Exception as e:
        print(f"  ⚠️ tariff read error: {e}")

    tariff_count = doc_count
    print(f"  ✅ tariff: {tariff_count} docs in {time.time()-t0:.1f}s")

    # ── tariff_chapters (richer descriptions) ──
    print("  Reading tariff_chapters...")
    chapter_count = 0
    try:
        docs = db.collection("tariff_chapters").stream()
        for doc in docs:
            data = doc.to_dict()
            hs = _clean_hs(data.get("code", data.get("hs_code", "")))
            if not hs:
                continue

            parts = []
            for f in ["title_he", "title_en", "description_he", "description_en", "title"]:
                v = data.get(f, "")
                if isinstance(v, str) and v:
                    parts.append(v)
            combined = " ".join(parts)
            keywords = _tokenize(combined)

            for kw in keywords:
                if hs not in kw_map[kw]:
                    kw_map[kw][hs] = {
                        "weight": 0,
                        "source": "tariff_chapters",
                        "description": (data.get("title_he", "") or data.get("title_en", ""))[:80],
                    }
                # Chapter-level descriptions get extra weight (more authoritative)
                kw_map[kw][hs]["weight"] += 2

            chapter_count += 1
    except Exception as e:
        print(f"  ⚠️ tariff_chapters read error: {e}")
    print(f"  ✅ tariff_chapters: {chapter_count} docs")

    # ── hs_code_index ──
    print("  Reading hs_code_index...")
    hsi_count = 0
    try:
        docs = db.collection("hs_code_index").stream()
        for doc in docs:
            data = doc.to_dict()
            hs = _clean_hs(data.get("code", data.get("hs_code", "")))
            if not hs:
                continue

            parts = []
            for f in ["description", "description_he", "description_en"]:
                v = data.get(f, "")
                if isinstance(v, str) and v:
                    parts.append(v)
            keywords = _tokenize(" ".join(parts))

            for kw in keywords:
                if hs not in kw_map[kw]:
                    kw_map[kw][hs] = {
                        "weight": 0,
                        "source": "hs_code_index",
                        "description": (data.get("description_he", "") or data.get("description", ""))[:80],
                    }
                kw_map[kw][hs]["weight"] += 1

            hsi_count += 1
    except Exception as e:
        print(f"  ⚠️ hs_code_index read error: {e}")
    print(f"  ✅ hs_code_index: {hsi_count} docs")

    # ── Also index classification_knowledge keywords → HS ──
    print("  Reading classification_knowledge for keywords...")
    ck_count = 0
    try:
        docs = db.collection("classification_knowledge").stream()
        for doc in docs:
            data = doc.to_dict()
            hs = _clean_hs(data.get("hs_code", ""))
            if not hs:
                continue

            parts = []
            for f in ["description", "content", "title", "rule"]:
                v = data.get(f, "")
                if isinstance(v, str) and v:
                    parts.append(v)
            keywords = _tokenize(" ".join(parts))

            usage_count = data.get("usage_count", 0)
            is_correction = data.get("is_correction", False)

            for kw in keywords:
                if hs not in kw_map[kw]:
                    kw_map[kw][hs] = {
                        "weight": 0,
                        "source": "classification_knowledge",
                        "description": (data.get("description", "") or data.get("content", ""))[:80],
                    }
                # Past classifications get weight boost based on usage
                bonus = 2
                if usage_count >= 5:
                    bonus += 1
                if usage_count >= 10:
                    bonus += 2
                if is_correction:
                    bonus += 3  # Corrections are very reliable
                kw_map[kw][hs]["weight"] += bonus

            ck_count += 1
    except Exception as e:
        print(f"  ⚠️ classification_knowledge read error: {e}")
    print(f"  ✅ classification_knowledge: {ck_count} docs")

    # ── Write to Firestore ──
    total_keywords = len(kw_map)
    print(f"\n  Total unique keywords: {total_keywords}")
    print(f"  Total source docs: {tariff_count + chapter_count + hsi_count + ck_count}")

    if STATS_ONLY or DRY_RUN:
        # Show top keywords
        top = sorted(kw_map.items(), key=lambda x: len(x[1]), reverse=True)[:20]
        print("\n  Top 20 keywords by HS code count:")
        for kw, codes in top:
            print(f"    '{kw}' → {len(codes)} HS codes")
        if DRY_RUN:
            print("  [DRY RUN — not writing to Firestore]")
        return total_keywords

    print("  Writing keyword_index to Firestore...")
    batch = db.batch()
    batch_count = 0
    written = 0
    t0 = time.time()

    for keyword, hs_entries in kw_map.items():
        # Sort by weight descending, keep top 20 per keyword
        sorted_entries = sorted(hs_entries.items(), key=lambda x: x[1]["weight"], reverse=True)[:20]
        codes = []
        for hs, info in sorted_entries:
            codes.append({
                "hs_code": hs,
                "weight": info["weight"],
                "source": info["source"],
                "description": info["description"],
            })

        doc_id = _safe_doc_id(keyword)
        ref = db.collection("keyword_index").document(doc_id)
        batch.set(ref, {
            "keyword": keyword,
            "codes": codes,
            "count": len(codes),
            "built_at": datetime.now(timezone.utc).isoformat(),
        })

        batch_count += 1
        written += 1
        if batch_count >= 450:  # Firestore batch limit is 500
            batch.commit()
            batch = db.batch()
            batch_count = 0
            if written % 2000 == 0:
                print(f"    ...{written}/{total_keywords} keywords written")

    if batch_count > 0:
        batch.commit()

    print(f"  ✅ keyword_index: {written} entries written in {time.time()-t0:.1f}s")
    return written


# ═══════════════════════════════════════════════════════════════
#  2. PRODUCT INDEX — product description → {hs_code, confidence}
# ═══════════════════════════════════════════════════════════════

def build_product_index():
    """
    Read ALL classification_knowledge + rcb_classifications + classifications.
    Map: product description → HS code with confidence and usage count.
    """
    print("\n═══ Building product_index ═══")
    # normalized_desc → {hs_code, confidence, usage_count, source, last_seen}
    product_map = {}
    doc_count = 0

    # ── classification_knowledge (primary source) ──
    print("  Reading classification_knowledge...")
    try:
        docs = db.collection("classification_knowledge").stream()
        for doc in docs:
            data = doc.to_dict()
            hs = _clean_hs(data.get("hs_code", ""))
            desc = data.get("description", data.get("content", ""))
            if not hs or not desc:
                continue

            key = _normalize_product(desc)
            if not key:
                continue

            usage = data.get("usage_count", 1)
            is_corr = data.get("is_correction", False)
            conf = data.get("confidence", "")

            # Map Hebrew confidence strings
            conf_map = {"גבוהה": 90, "בינונית": 70, "נמוכה": 50, "high": 90, "medium": 70, "low": 50}
            conf_num = conf_map.get(conf, 75) if isinstance(conf, str) else 75

            if is_corr:
                conf_num = min(95, conf_num + 10)

            if key not in product_map or product_map[key]["confidence"] < conf_num:
                product_map[key] = {
                    "hs_code": hs,
                    "confidence": conf_num,
                    "usage_count": usage,
                    "description": desc[:150],
                    "source": "classification_knowledge",
                    "is_correction": is_corr,
                    "last_seen": data.get("learned_at", ""),
                }
            elif key in product_map and product_map[key]["hs_code"] == hs:
                product_map[key]["usage_count"] = max(product_map[key]["usage_count"], usage)

            doc_count += 1
    except Exception as e:
        print(f"  ⚠️ classification_knowledge read error: {e}")
    print(f"  ✅ classification_knowledge: {doc_count} docs → {len(product_map)} products")

    # ── rcb_classifications (completed classifications) ──
    rcb_count = 0
    print("  Reading rcb_classifications...")
    try:
        docs = db.collection("rcb_classifications").stream()
        for doc in docs:
            data = doc.to_dict()
            classifications = data.get("classifications", [])
            if not classifications:
                # Try agents.classification.classifications
                agents = data.get("agents", {})
                c_data = agents.get("classification", {})
                classifications = c_data.get("classifications", [])

            for cls in classifications:
                hs = _clean_hs(cls.get("hs_code", ""))
                desc = cls.get("item", cls.get("description", ""))
                if not hs or not desc:
                    continue

                key = _normalize_product(desc)
                if not key:
                    continue

                conf = cls.get("confidence", "")
                conf_map = {"גבוהה": 85, "בינונית": 65, "נמוכה": 45, "high": 85, "medium": 65, "low": 45}
                conf_num = conf_map.get(conf, 70) if isinstance(conf, str) else 70

                if key not in product_map or product_map[key]["confidence"] < conf_num:
                    product_map[key] = {
                        "hs_code": hs,
                        "confidence": conf_num,
                        "usage_count": 1,
                        "description": desc[:150],
                        "source": "rcb_classifications",
                        "is_correction": False,
                        "last_seen": data.get("processed_at", data.get("created_at", "")),
                    }

            rcb_count += 1
    except Exception as e:
        print(f"  ⚠️ rcb_classifications read error: {e}")
    print(f"  ✅ rcb_classifications: {rcb_count} docs → {len(product_map)} total products")

    # ── classifications collection ──
    cls_count = 0
    print("  Reading classifications...")
    try:
        docs = db.collection("classifications").stream()
        for doc in docs:
            data = doc.to_dict()
            hs = _clean_hs(data.get("hs_code", ""))
            desc = data.get("description", data.get("item_description", ""))
            if not hs or not desc:
                continue

            key = _normalize_product(desc)
            if not key:
                continue

            if key not in product_map:
                product_map[key] = {
                    "hs_code": hs,
                    "confidence": 70,
                    "usage_count": 1,
                    "description": desc[:150],
                    "source": "classifications",
                    "is_correction": False,
                    "last_seen": data.get("created_at", ""),
                }

            cls_count += 1
    except Exception as e:
        print(f"  ⚠️ classifications read error: {e}")
    print(f"  ✅ classifications: {cls_count} docs → {len(product_map)} total products")

    # ── Write to Firestore ──
    total_products = len(product_map)
    print(f"\n  Total unique products: {total_products}")

    if STATS_ONLY or DRY_RUN:
        top = sorted(product_map.items(), key=lambda x: x[1]["usage_count"], reverse=True)[:15]
        print("\n  Top 15 products by usage:")
        for key, info in top:
            print(f"    '{key[:50]}' → HS {info['hs_code']} "
                  f"(conf={info['confidence']}%, uses={info['usage_count']})")
        if DRY_RUN:
            print("  [DRY RUN — not writing to Firestore]")
        return total_products

    print("  Writing product_index to Firestore...")
    batch = db.batch()
    batch_count = 0
    written = 0
    t0 = time.time()

    for key, info in product_map.items():
        doc_id = _safe_doc_id(key)
        ref = db.collection("product_index").document(doc_id)
        batch.set(ref, {
            "product_key": key,
            **info,
            "built_at": datetime.now(timezone.utc).isoformat(),
        })

        batch_count += 1
        written += 1
        if batch_count >= 450:
            batch.commit()
            batch = db.batch()
            batch_count = 0

    if batch_count > 0:
        batch.commit()

    print(f"  ✅ product_index: {written} entries written in {time.time()-t0:.1f}s")
    return written


# ═══════════════════════════════════════════════════════════════
#  3. SUPPLIER INDEX — supplier → [{hs_code, count, last_seen}]
# ═══════════════════════════════════════════════════════════════

def build_supplier_index():
    """
    Read sellers + rcb_classifications + classifications.
    Map: supplier name → list of HS codes they typically ship.
    """
    print("\n═══ Building supplier_index ═══")
    # normalized_name → {hs_code → {count, last_seen}}
    supplier_map = defaultdict(lambda: defaultdict(lambda: {"count": 0, "last_seen": ""}))
    doc_count = 0

    # ── sellers collection (canonical source) ──
    print("  Reading sellers...")
    try:
        docs = db.collection("sellers").stream()
        for doc in docs:
            data = doc.to_dict()
            name = data.get("name", "")
            if not name:
                continue

            key = _normalize_supplier(name)
            if not key:
                continue

            hs_codes = data.get("known_hs_codes", [])
            last = data.get("last_classification", "")
            for hs in hs_codes:
                hs_clean = _clean_hs(hs)
                if hs_clean:
                    supplier_map[key][hs_clean]["count"] += data.get("classification_count", 1)
                    supplier_map[key][hs_clean]["last_seen"] = last

            doc_count += 1
    except Exception as e:
        print(f"  ⚠️ sellers read error: {e}")
    print(f"  ✅ sellers: {doc_count} docs")

    # ── rcb_classifications (extract seller → HS from actual classifications) ──
    rcb_count = 0
    print("  Reading rcb_classifications for supplier data...")
    try:
        docs = db.collection("rcb_classifications").stream()
        for doc in docs:
            data = doc.to_dict()
            seller = ""

            # Try invoice_data.seller first
            inv = data.get("invoice_data", {})
            if isinstance(inv, dict):
                seller = inv.get("seller", "")

            # Try agents.invoice.seller
            if not seller:
                agents = data.get("agents", {})
                inv2 = agents.get("invoice", {})
                if isinstance(inv2, dict):
                    seller = inv2.get("seller", "")

            if not seller:
                continue

            key = _normalize_supplier(seller)
            if not key:
                continue

            # Get HS codes from classifications
            classifications = data.get("classifications", [])
            if not classifications:
                agents = data.get("agents", {})
                c_data = agents.get("classification", {})
                classifications = c_data.get("classifications", [])

            proc_date = data.get("processed_at", data.get("created_at", ""))

            for cls in classifications:
                hs = _clean_hs(cls.get("hs_code", ""))
                if hs:
                    supplier_map[key][hs]["count"] += 1
                    if proc_date > supplier_map[key][hs]["last_seen"]:
                        supplier_map[key][hs]["last_seen"] = proc_date

            rcb_count += 1
    except Exception as e:
        print(f"  ⚠️ rcb_classifications read error: {e}")
    print(f"  ✅ rcb_classifications: {rcb_count} docs")

    # ── classifications collection ──
    cls_count = 0
    print("  Reading classifications for supplier data...")
    try:
        docs = db.collection("classifications").stream()
        for doc in docs:
            data = doc.to_dict()
            seller = data.get("seller", data.get("supplier", ""))
            hs = _clean_hs(data.get("hs_code", ""))
            if not seller or not hs:
                continue

            key = _normalize_supplier(seller)
            if not key:
                continue

            proc_date = data.get("created_at", "")
            supplier_map[key][hs]["count"] += 1
            if proc_date > supplier_map[key][hs]["last_seen"]:
                supplier_map[key][hs]["last_seen"] = proc_date

            cls_count += 1
    except Exception as e:
        print(f"  ⚠️ classifications read error: {e}")
    print(f"  ✅ classifications: {cls_count} docs")

    # ── Write to Firestore ──
    total_suppliers = len(supplier_map)
    print(f"\n  Total unique suppliers: {total_suppliers}")

    if STATS_ONLY or DRY_RUN:
        for name, codes in sorted(supplier_map.items()):
            sorted_codes = sorted(codes.items(), key=lambda x: x[1]["count"], reverse=True)
            hs_list = ", ".join(f"HS {hs} (×{info['count']})" for hs, info in sorted_codes[:5])
            print(f"    '{name}' → {hs_list}")
        if DRY_RUN:
            print("  [DRY RUN — not writing to Firestore]")
        return total_suppliers

    print("  Writing supplier_index to Firestore...")
    batch = db.batch()
    batch_count = 0
    written = 0
    t0 = time.time()

    for name, hs_entries in supplier_map.items():
        sorted_codes = sorted(hs_entries.items(), key=lambda x: x[1]["count"], reverse=True)
        codes = []
        for hs, info in sorted_codes[:30]:  # Top 30 HS codes per supplier
            codes.append({
                "hs_code": hs,
                "count": info["count"],
                "last_seen": info["last_seen"],
            })

        doc_id = _safe_doc_id(name)
        ref = db.collection("supplier_index").document(doc_id)
        batch.set(ref, {
            "supplier_name": name,
            "codes": codes,
            "total_hs_codes": len(codes),
            "total_shipments": sum(c["count"] for c in codes),
            "built_at": datetime.now(timezone.utc).isoformat(),
        })

        batch_count += 1
        written += 1
        if batch_count >= 450:
            batch.commit()
            batch = db.batch()
            batch_count = 0

    if batch_count > 0:
        batch.commit()

    print(f"  ✅ supplier_index: {written} entries written in {time.time()-t0:.1f}s")
    return written


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

def _normalize_product(desc):
    """Normalize product description for deduplication."""
    if not desc:
        return ""
    # Lowercase, strip excess whitespace, remove punctuation but keep Hebrew
    text = desc.lower().strip()
    text = re.sub(r'[^\w\u0590-\u05FF\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:200] if text else ""


def _normalize_supplier(name):
    """Normalize supplier name for deduplication."""
    if not name:
        return ""
    text = name.lower().strip()
    # Remove common suffixes
    for suffix in [" ltd", " ltd.", " inc", " inc.", " co.", " corp", " corp.",
                   " gmbh", " s.a.", " s.r.l.", " bv", " b.v.", " llc",
                   " בע\"מ", " בע״מ"]:
        if text.endswith(suffix):
            text = text[:-len(suffix)].strip()
    text = re.sub(r'[^\w\u0590-\u05FF\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text if text else ""


def _safe_doc_id(text):
    """Create a safe Firestore document ID from text."""
    # Replace non-alphanumeric (keeping Hebrew) with underscore
    safe = re.sub(r'[^\w\u0590-\u05FF]', '_', text.lower())
    safe = re.sub(r'_+', '_', safe).strip('_')
    # Firestore doc IDs max 1500 bytes; keep it safe
    return safe[:200] if safe else "unknown"


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def run_all():
    """Build all three indexes."""
    print("=" * 60)
    print("  KNOWLEDGE INDEXER — Building inverted indexes")
    print(f"  Mode: {'DRY RUN' if DRY_RUN else 'STATS ONLY' if STATS_ONLY else 'LIVE WRITE'}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    t0 = time.time()

    kw_count = build_keyword_index()
    prod_count = build_product_index()
    supp_count = build_supplier_index()

    elapsed = time.time() - t0

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print(f"  keyword_index:  {kw_count} entries")
    print(f"  product_index:  {prod_count} entries")
    print(f"  supplier_index: {supp_count} entries")
    print(f"  Total time:     {elapsed:.1f}s")
    print("=" * 60)

    # Store run metadata
    if not DRY_RUN and not STATS_ONLY:
        try:
            db.collection("system_metadata").document("knowledge_indexer").set({
                "last_run": datetime.now(timezone.utc).isoformat(),
                "keyword_count": kw_count,
                "product_count": prod_count,
                "supplier_count": supp_count,
                "duration_seconds": round(elapsed, 1),
            })
            print("\n  ✅ Run metadata saved to system_metadata/knowledge_indexer")
        except Exception as e:
            print(f"\n  ⚠️ Failed to save metadata: {e}")


if __name__ == "__main__":
    run_all()
