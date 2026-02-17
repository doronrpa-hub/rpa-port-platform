"""
Block C3: Seed free_import_order collection from data.gov.il JSON dump.

Source: צו יבוא חופשי (Free Import Order) — 28,899 regulatory requirement records
from data.gov.il API, downloaded to Cloud Storage as:
  agent/free_import_order/20260201_download_20260201_141544.json

Writes to Firestore:
  1. free_import_order/ — one doc per HS code, all requirements grouped
  2. librarian_index/ — indexes all free_import_order docs

Data structure per HS code doc:
  - hs_code: full classification (e.g., "0407110000/4")
  - hs_10: 10-digit padded code
  - chapter: 2-digit chapter
  - goods_description: full Hebrew description from tariff
  - requirements: list of requirement dicts
  - authorities_summary: unique authorities list
  - appendices: which appendices apply (תוספת 1/2/4)
  - has_standards: bool — does it need מכון התקנים
  - conditions_type: "all" / "alternative" / "mixed"
  - inception_type: "partial" / "absolute" / "mixed"
  - active_count: number of active requirements
  - total_count: total requirements (including expired)

Safety:
  - Uses set(merge=True) — ADD only, never overwrites existing fields
  - Tags with source: "data_gov_il_fio_20260201"
  - Batched writes (500 per batch)

Run: python -X utf8 seed_free_import_order_c3.py [--test] [--active-only]
"""
import sys
import os
import json
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
SOURCE = "data_gov_il_fio_20260201"
COLLECTION = "free_import_order"

# ── JSON file paths ──
JSON_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "data_c3", "fio_download.json"),
    r"C:\Users\User\rpa-port-platform\data_c3\fio_download.json",
]


def safe_doc_id(hs_code):
    """Create Firestore-safe document ID from HS code."""
    return hs_code.replace("/", "_").replace(".", "").replace(" ", "").strip()


def parse_records(json_path, active_only=False):
    """Parse the data.gov.il JSON and group records by HS code."""
    print(f"  Loading JSON from {json_path}...")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data["result"]["records"]
    total = data["result"]["total"]
    print(f"  Loaded {len(records)} records (total in dataset: {total})")

    # Group by HS code
    by_hs = defaultdict(list)
    skipped_expired = 0
    skipped_empty = 0

    for r in records:
        hs = r.get("CustomsItemFullClassification", "").strip()
        if not hs:
            skipped_empty += 1
            continue

        # Check active status
        end_date = r.get("EndDate", "")
        is_active = True
        if end_date:
            try:
                dt = datetime.strptime(end_date[:10], "%Y-%m-%d")
                is_active = dt >= datetime(2026, 1, 1)
            except (ValueError, TypeError):
                pass

        if active_only and not is_active:
            skipped_expired += 1
            continue

        by_hs[hs].append({
            "record": r,
            "is_active": is_active,
        })

    print(f"  Grouped into {len(by_hs)} unique HS codes")
    if skipped_expired:
        print(f"  Skipped {skipped_expired} expired records")
    if skipped_empty:
        print(f"  Skipped {skipped_empty} records with empty HS code")

    return by_hs


def build_requirement(record_data):
    """Build a clean requirement dict from a raw record."""
    r = record_data["record"]
    is_active = record_data["is_active"]

    return {
        "regularity_requirement_id": r.get("RegularityRequirementID"),
        "authority": r.get("RegularityRequirement_Authority", ""),
        "confirmation_type": r.get("ConfirmationType", ""),
        "confirmation_type_id": r.get("ConfirmationTypeID"),
        "appendix": r.get("RegularitySource", ""),
        "conditions": r.get("InterConditionsRelationship", ""),
        "inception": r.get("InceptionCode", ""),
        "goods_description": r.get("RegularityRequirement_GoodsDescription", ""),
        "measurement_unit": r.get("MeasurementUnitDescription", ""),
        "maslul_unit": r.get("MaslulMeasurementUnit"),
        "parent_hs": str(r.get("CustomsItemParent_FullClassification", "")),
        "requirement_hs": r.get(
            "RegularityRequirement_CustomsItemFullClassification", ""
        ),
        "region_type": r.get("AutonomyRegularityRegionType", ""),
        "is_carnet_included": r.get("IsCarnetIncluded", "") == "True",
        "end_date": r.get("EndDate", ""),
        "update_date": r.get("UpdateDate", ""),
        "is_active": is_active,
    }


def build_hs_doc(hs_code, record_list):
    """Build a Firestore document for one HS code with all its requirements."""
    requirements = [build_requirement(rd) for rd in record_list]

    # Get the first record for goods description
    first_r = record_list[0]["record"]
    goods_desc = first_r.get("FullGoodsDescription", "")

    # HS code parsing
    hs_clean = hs_code.replace("/", "").replace(".", "").replace(" ", "").replace("-", "")
    chapter = hs_clean[:2].lstrip("0").zfill(2) if len(hs_clean) >= 2 else ""
    hs_10 = hs_clean[:10].ljust(10, "0") if len(hs_clean) >= 4 else hs_clean

    # Compute summaries
    authorities = sorted(set(
        r["authority"] for r in requirements if r["authority"]
    ))
    appendices = sorted(set(
        r["appendix"] for r in requirements if r["appendix"]
    ))
    confirmation_types = sorted(set(
        r["confirmation_type"] for r in requirements if r["confirmation_type"]
    ))

    # Conditions analysis
    cond_vals = set(r["conditions"] for r in requirements if r["conditions"])
    if len(cond_vals) == 1:
        conditions_type = (
            "all" if "כל התנאים" in cond_vals else "alternative"
        )
    elif len(cond_vals) > 1:
        conditions_type = "mixed"
    else:
        conditions_type = "unknown"

    # Inception analysis
    inc_vals = set(r["inception"] for r in requirements if r["inception"])
    if len(inc_vals) == 1:
        inception_type = "absolute" if "מוחלט" in inc_vals else "partial"
    elif len(inc_vals) > 1:
        inception_type = "mixed"
    else:
        inception_type = "unknown"

    # Standards check
    has_standards = any(
        "מכון התקנים" in r["authority"] for r in requirements
    )
    has_lab = any(
        "מעבדת בדיקה" in r["authority"] or "מעבדה מוסמכת" in r["authority"]
        for r in requirements
    )

    active_reqs = [r for r in requirements if r["is_active"]]
    expired_reqs = [r for r in requirements if not r["is_active"]]

    return {
        "hs_code": hs_code,
        "hs_10": hs_10,
        "chapter": chapter,
        "goods_description": goods_desc,
        "requirements": active_reqs,
        "expired_requirements_count": len(expired_reqs),
        "authorities_summary": authorities,
        "appendices": appendices,
        "confirmation_types": confirmation_types,
        "has_standards": has_standards,
        "has_lab_testing": has_lab,
        "conditions_type": conditions_type,
        "inception_type": inception_type,
        "active_count": len(active_reqs),
        "total_count": len(requirements),
        "source": SOURCE,
        "seeded_at": NOW,
    }


def seed_firestore(by_hs, test_mode=False):
    """Seed all HS code docs into Firestore."""
    batch_size = 500
    batch = db.batch()
    count = 0
    total = len(by_hs)
    chapters_seen = set()

    for hs_code, record_list in sorted(by_hs.items()):
        doc_data = build_hs_doc(hs_code, record_list)
        doc_id = safe_doc_id(hs_code)
        chapters_seen.add(doc_data["chapter"])

        if test_mode and count >= 10:
            print(f"  [TEST] Stopping after 10 docs")
            break

        ref = db.collection(COLLECTION).document(doc_id)
        batch.set(ref, doc_data, merge=True)
        count += 1

        if count % batch_size == 0:
            if not test_mode:
                batch.commit()
            batch = db.batch()
            print(f"  Seeded {count}/{total} docs...")

    # Final batch
    if count % batch_size != 0:
        if not test_mode:
            batch.commit()

    print(f"  Seeded {count} docs into {COLLECTION}/")
    print(f"  Chapters covered: {len(chapters_seen)} ({', '.join(sorted(chapters_seen))})")

    return count, chapters_seen


def seed_metadata(total_docs, chapters):
    """Seed a metadata doc summarizing the FIO collection."""
    meta = {
        "collection": COLLECTION,
        "source": SOURCE,
        "source_url": "https://data.gov.il/api/3/action/datastore_search",
        "description": "צו יבוא חופשי — Free Import Order regulatory requirements",
        "total_hs_codes": total_docs,
        "chapters_covered": len(chapters),
        "chapters_list": sorted(chapters),
        "seeded_at": NOW,
        "data_fields": [
            "hs_code", "goods_description", "requirements",
            "authorities_summary", "appendices", "confirmation_types",
            "has_standards", "has_lab_testing", "conditions_type",
            "inception_type", "active_count",
        ],
        "appendix_names": {
            "1": "תוספת 1 — רשימת טובין שיבואם טעון רישיון",
            "2": "תוספת 2 — רשימת טובין שיבואם מותנה בהתאמה לדרישות",
            "4": "תוספת 4 — יבוא",
        },
    }
    db.collection(COLLECTION).document("_metadata").set(meta, merge=True)
    print(f"  Metadata doc written to {COLLECTION}/_metadata")


def index_in_librarian(total_docs):
    """Add free_import_order entries to librarian_index."""
    batch = db.batch()
    count = 0

    docs = db.collection(COLLECTION).stream()
    for doc in docs:
        if doc.id == "_metadata":
            continue
        data = doc.to_dict()

        index_entry = {
            "collection": COLLECTION,
            "doc_id": doc.id,
            "hs_code": data.get("hs_code", ""),
            "chapter": data.get("chapter", ""),
            "title": data.get("goods_description", "")[:200],
            "authorities": data.get("authorities_summary", []),
            "doc_type": "regulatory",
            "source": SOURCE,
            "indexed_at": NOW,
        }

        ref = db.collection("librarian_index").document(f"fio_{doc.id}")
        batch.set(ref, index_entry, merge=True)
        count += 1

        if count % 500 == 0:
            batch.commit()
            batch = db.batch()
            print(f"  Indexed {count} in librarian_index...")

    if count % 500 != 0:
        batch.commit()

    print(f"  Indexed {count} docs in librarian_index (prefix: fio_)")
    return count


def print_summary(by_hs):
    """Print analysis summary."""
    from collections import Counter
    auth_counter = Counter()
    appendix_counter = Counter()
    chapter_counter = Counter()

    for hs_code, record_list in by_hs.items():
        hs_clean = hs_code.replace("/", "").replace(".", "").replace(" ", "").replace("-", "")
        ch = hs_clean[:2].lstrip("0").zfill(2) if len(hs_clean) >= 2 else "??"
        chapter_counter[ch] += 1

        for rd in record_list:
            r = rd["record"]
            auth_counter[r.get("RegularityRequirement_Authority", "")] += 1
            appendix_counter[r.get("RegularitySource", "")] += 1

    print("\n=== FIO SUMMARY ===")
    print(f"Total unique HS codes: {len(by_hs)}")
    print(f"Total records: {sum(len(v) for v in by_hs.values())}")
    print(f"Chapters: {len(chapter_counter)}")
    print(f"\nTop authorities:")
    for auth, cnt in auth_counter.most_common(10):
        print(f"  {cnt:>6}  {auth}")
    print(f"\nAppendices:")
    for app, cnt in appendix_counter.most_common():
        print(f"  {cnt:>6}  {app}")
    print(f"\nTop chapters:")
    for ch, cnt in chapter_counter.most_common(10):
        print(f"  Ch {ch}: {cnt} HS codes")


def main():
    test_mode = "--test" in sys.argv
    active_only = "--active-only" in sys.argv

    if test_mode:
        print("=== TEST MODE — no writes ===")

    # Find JSON file
    json_path = next((p for p in JSON_PATHS if os.path.exists(p)), None)
    if not json_path:
        print("ERROR: fio_download.json not found")
        print(f"  Tried: {JSON_PATHS}")
        sys.exit(1)

    print(f"Block C3: Seeding {COLLECTION} from data.gov.il FIO JSON")
    print(f"  JSON: {json_path}")
    print(f"  Active only: {active_only}")

    # Parse
    by_hs = parse_records(json_path, active_only=active_only)
    print_summary(by_hs)

    # Seed
    print(f"\n--- Seeding Firestore ---")
    total_docs, chapters = seed_firestore(by_hs, test_mode=test_mode)

    if not test_mode:
        # Metadata
        seed_metadata(total_docs, chapters)

        # Librarian index
        print(f"\n--- Indexing in librarian_index ---")
        index_in_librarian(total_docs)

    print(f"\n=== DONE ===")
    print(f"  Collection: {COLLECTION}")
    print(f"  Documents: {total_docs}")
    print(f"  Chapters: {len(chapters)}")
    if test_mode:
        print("  (TEST MODE — nothing written)")


if __name__ == "__main__":
    main()
