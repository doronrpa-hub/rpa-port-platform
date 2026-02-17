"""
Block C4: Seed free_export_order collection from צו יצוא חופשי (Free Export Order).

Source: data.gov.il JSON dump (2.3 MB, 1,704 records, 979 HS codes)
  resource_id: dbf19712-e570-4264-805e-c891cf4c8d1d
  Cloud Storage: agent/data_gov_structured/20260201_download_20260201_143141.json
  Local: data_c3/free_export_order_raw.json

Writes to Firestore:
  1. free_export_order/{hs_code_doc_id} — one doc per unique HS code
  2. free_export_order/_metadata — collection summary
  3. librarian_index/feo_{doc_id} — index entries

Same pattern as C3 (seed_free_import_order_c3.py) adapted for export.

Safety:
  - Uses set(merge=True) — ADD only
  - Tags with source: "free_export_order_c4"
  - Batched writes

Run: python -X utf8 seed_free_export_order_c4.py [--test]
"""
import sys
import os
import json
import re
import hashlib
from datetime import datetime, timezone
from collections import defaultdict

os.environ["GOOGLE_CLOUD_PROJECT"] = "rpa-port-customs"

import firebase_admin
from firebase_admin import credentials, firestore

# ── Firebase init ──
SA_PATHS = [
    r"C:\Users\User\Downloads\rpa-port-customs-firebase-adminsdk-fbsvc-da5df22d32.json",
    r"C:\Users\doron\sa-key.json",
]

try:
    app = firebase_admin.get_app()
except ValueError:
    sa_path = next((p for p in SA_PATHS if os.path.exists(p)), None)
    if not sa_path:
        print("ERROR: No service account key found")
        sys.exit(1)
    cred = credentials.Certificate(sa_path)
    app = firebase_admin.initialize_app(cred)

db = firestore.client()

NOW = datetime.now(timezone.utc).isoformat()
SOURCE = "free_export_order_c4"
COLLECTION = "free_export_order"
JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "data_c3", "free_export_order_raw.json")


def format_hs(raw):
    """Format raw HS code (e.g., '0602109000/3') to dotted format."""
    clean = raw.split("/")[0].strip()
    if len(clean) >= 4:
        return f"{clean[:2]}.{clean[2:4]}.{clean[4:]}" if len(clean) > 4 else f"{clean[:2]}.{clean[2:4]}"
    return clean


def make_doc_id(hs_code):
    """Generate Firestore-safe doc ID from HS code."""
    return hs_code.replace(".", "_").replace("/", "_").replace(" ", "")


def parse_records(records):
    """Group records by HS code and build per-HS-code documents."""
    by_hs = defaultdict(list)

    for r in records:
        fc = r.get("CustomsItemFullClassification", "")
        if not fc:
            continue
        hs_raw = fc.split("/")[0].strip()
        by_hs[hs_raw].append(r)

    docs = []
    for hs_raw, recs in sorted(by_hs.items()):
        hs_dotted = format_hs(hs_raw)
        chapter = hs_raw[:2] if len(hs_raw) >= 2 else ""

        # Aggregate fields
        authorities = set()
        confirmation_types = set()
        appendices = set()
        inception_codes = set()
        active_count = 0
        expired_count = 0
        requirements = []

        for r in recs:
            auth = r.get("RegularityRequirement_Authority", "")
            if auth:
                authorities.add(auth)

            ct = r.get("ConfirmationType", "")
            if ct:
                confirmation_types.add(ct)

            src = r.get("RegularitySource", "")
            if src:
                appendices.add(src)

            ic = r.get("InceptionCode", "")
            if ic:
                inception_codes.add(ic)

            end_date = r.get("EndDate", "")
            is_active = end_date >= "2026" if end_date else True
            if is_active:
                active_count += 1
            else:
                expired_count += 1

            requirements.append({
                "confirmation_type": ct,
                "authority": auth,
                "appendix": src,
                "inception_code": ic,
                "end_date": end_date,
                "is_active": is_active,
                "measurement_unit": r.get("MeasurementUnitDescription", ""),
                "autonomy_region": r.get("AutonomyRegularityRegionType", ""),
                "inter_conditions": r.get("InterConditionsRelationship", ""),
            })

        # Goods description from first record
        goods_desc = recs[0].get("FullGoodsDescription", "")

        doc = {
            "hs_code": hs_dotted,
            "hs_10": hs_raw,
            "chapter": chapter,
            "goods_description": goods_desc[:1000],
            "authorities_summary": sorted(authorities),
            "confirmation_types": sorted(confirmation_types),
            "appendices": sorted(appendices),
            "inception_codes": sorted(inception_codes),
            "requirements_count": len(requirements),
            "active_count": active_count,
            "expired_count": expired_count,
            "requirements": requirements[:50],  # Cap at 50 per doc
            "has_absolute": "מוחלט" in inception_codes,
            "has_partial": "חלקי" in inception_codes,
            "source": SOURCE,
            "seeded_at": NOW,
        }
        docs.append((make_doc_id(hs_raw), doc))

    return docs


def seed_firestore(docs, test_mode=False):
    """Write docs to Firestore."""
    batch = db.batch()
    count = 0

    for doc_id, doc_data in docs:
        ref = db.collection(COLLECTION).document(doc_id)
        batch.set(ref, doc_data, merge=True)
        count += 1

        if count % 200 == 0:
            if not test_mode:
                batch.commit()
            batch = db.batch()
            print(f"    Committed {count}...")

    if count % 200 != 0:
        if not test_mode:
            batch.commit()

    return count


def seed_metadata(docs, records_count):
    """Write metadata doc."""
    chapters = set()
    authorities = set()
    for _, d in docs:
        chapters.add(d["chapter"])
        for a in d["authorities_summary"]:
            authorities.add(a)

    meta = {
        "collection": COLLECTION,
        "source": SOURCE,
        "description": "צו יצוא חופשי — Free Export Order: export regulatory requirements per HS code",
        "data_gov_resource_id": "dbf19712-e570-4264-805e-c891cf4c8d1d",
        "total_records": records_count,
        "unique_hs_codes": len(docs),
        "chapters_count": len(chapters),
        "chapters": sorted(chapters),
        "authorities": sorted(authorities),
        "seeded_at": NOW,
    }
    db.collection(COLLECTION).document("_metadata").set(meta, merge=True)
    print(f"  Metadata doc written")


def index_in_librarian(docs):
    """Index in librarian_index."""
    batch = db.batch()
    count = 0

    for doc_id, doc_data in docs:
        index_entry = {
            "collection": COLLECTION,
            "doc_id": doc_id,
            "doc_type": "regulatory",
            "title": doc_data.get("goods_description", "")[:200],
            "source": SOURCE,
            "indexed_at": NOW,
        }
        ref = db.collection("librarian_index").document(f"feo_{doc_id}")
        batch.set(ref, index_entry, merge=True)
        count += 1

        if count % 500 == 0:
            batch.commit()
            batch = db.batch()

    if count % 500 != 0:
        batch.commit()

    print(f"  Indexed {count} docs in librarian_index (prefix: feo_)")
    return count


def main():
    test_mode = "--test" in sys.argv

    if test_mode:
        print("=== TEST MODE ===")

    print(f"Block C4: Seeding {COLLECTION} from Free Export Order data.gov.il JSON")

    # Load JSON
    json_path = JSON_PATH
    if not os.path.exists(json_path):
        # Try alternate path
        json_path = os.path.join(os.path.dirname(__file__), "data_c3", "free_export_order_raw.json")
    if not os.path.exists(json_path):
        print(f"ERROR: JSON not found at {JSON_PATH}")
        sys.exit(1)

    print(f"  Loading {json_path}...")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("result", {}).get("records", [])
    print(f"  Total records: {len(records)}")

    # Parse
    print(f"\n--- Parsing records ---")
    docs = parse_records(records)
    print(f"  Unique HS code docs: {len(docs)}")

    # Seed
    print(f"\n--- Seeding Firestore ---")
    count = seed_firestore(docs, test_mode)
    print(f"  Seeded {count} docs")

    if not test_mode:
        seed_metadata(docs, len(records))

        print(f"\n--- Indexing ---")
        index_in_librarian(docs)

    print(f"\n=== DONE ===")
    print(f"  Records: {len(records)}")
    print(f"  HS code docs: {len(docs)}")
    if test_mode:
        print("  (TEST MODE — nothing written)")


if __name__ == "__main__":
    main()
