"""
Import baseline knowledge JSONs into Firestore.
Phase A of Master Plan — loads FTA agreements, regulatory requirements,
and classification rules as starting cache.

Usage:
    python import_knowledge.py [--dry-run]

These are APPROXIMATIONS from training data. The system will VERIFY and
CORRECT them against official sources over time.
"""

import json
import os
import sys
from datetime import datetime, timezone

# Set credentials
cred_path = os.path.join(
    os.environ.get("APPDATA", ""),
    "gcloud", "legacy_credentials", "doronrpa@gmail.com", "adc.json"
)
if os.path.exists(cred_path):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "rpa-port-customs")

import firebase_admin
from firebase_admin import firestore

# Initialize Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

DRY_RUN = "--dry-run" in sys.argv


def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def import_fta_agreements():
    """Import FTA agreements into fta_agreements collection."""
    data = load_json("fta_agreements.json")
    collection = "fta_agreements"
    count = 0

    for agreement in data:
        doc_id = agreement["id"]
        doc = {
            **agreement,
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "source": "baseline_knowledge",
            "verified": False
        }
        if DRY_RUN:
            print(f"  [DRY RUN] Would write {collection}/{doc_id}")
        else:
            db.collection(collection).document(doc_id).set(doc, merge=True)
        count += 1

    print(f"  {collection}: {count} agreements {'(dry run)' if DRY_RUN else 'imported'}")
    return count


def import_regulatory_requirements():
    """Import regulatory requirements into regulatory_requirements collection."""
    data = load_json("regulatory_requirements.json")
    collection = "regulatory_requirements"
    count = 0

    for entry in data:
        # Use first HS chapter as document ID
        chapters = entry.get("hs_chapters", [])
        doc_id = f"ch_{'-'.join(chapters)}"
        doc = {
            **entry,
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "source": "baseline_knowledge",
            "verified": False
        }
        if DRY_RUN:
            print(f"  [DRY RUN] Would write {collection}/{doc_id}")
        else:
            db.collection(collection).document(doc_id).set(doc, merge=True)
        count += 1

    # Also create a ministry_index for quick lookups by HS chapter
    ministry_count = 0
    for entry in data:
        for chapter in entry.get("hs_chapters", []):
            doc_id = f"chapter_{chapter}"
            doc = {
                "hs_chapter": chapter,
                "cargo": entry["cargo"],
                "cargo_he": entry.get("cargo_he", ""),
                "ministries": entry["ministries"],
                "free_import_order": entry.get("free_import_order", False),
                "imported_at": datetime.now(timezone.utc).isoformat(),
                "source": "baseline_knowledge"
            }
            if DRY_RUN:
                print(f"  [DRY RUN] Would write ministry_index/{doc_id}")
            else:
                db.collection("ministry_index").document(doc_id).set(doc, merge=True)
            ministry_count += 1

    print(f"  {collection}: {count} entries {'(dry run)' if DRY_RUN else 'imported'}")
    print(f"  ministry_index: {ministry_count} chapter mappings {'(dry run)' if DRY_RUN else 'imported'}")
    return count + ministry_count


def import_classification_rules():
    """Import classification rules into classification_rules collection."""
    data = load_json("classification_rules.json")
    collection = "classification_rules"
    count = 0

    # Import GIR principles
    for rule in data.get("gir_principles", []):
        doc_id = rule["rule"].lower().replace(" ", "_")
        doc = {
            **rule,
            "type": "gir_principle",
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "source": "baseline_knowledge"
        }
        if DRY_RUN:
            print(f"  [DRY RUN] Would write {collection}/{doc_id}")
        else:
            db.collection(collection).document(doc_id).set(doc, merge=True)
        count += 1

    # Import keyword patterns
    for i, pattern in enumerate(data.get("keyword_patterns", [])):
        doc_id = f"kw_{pattern['hs_heading']}_{i}"
        doc = {
            **pattern,
            "type": "keyword_pattern",
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "source": "baseline_knowledge"
        }
        if DRY_RUN:
            print(f"  [DRY RUN] Would write {collection}/{doc_id}")
        else:
            db.collection(collection).document(doc_id).set(doc, merge=True)
        count += 1

    print(f"  {collection}: {count} rules {'(dry run)' if DRY_RUN else 'imported'}")
    return count


def main():
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(f"\n=== Importing Baseline Knowledge ({mode}) ===\n")

    total = 0
    total += import_fta_agreements()
    total += import_regulatory_requirements()
    total += import_classification_rules()

    print(f"\n=== Done: {total} total documents {'would be written' if DRY_RUN else 'imported'} ===\n")


if __name__ == "__main__":
    main()
