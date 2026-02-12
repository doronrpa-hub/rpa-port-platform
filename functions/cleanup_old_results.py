"""Delete old dry-run and test results from batch_reprocess_results."""
import sys, io, os
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

os.environ.setdefault("GCLOUD_PROJECT", "rpa-port-customs")
cred = os.path.join(os.environ.get("APPDATA", ""), "gcloud", "legacy_credentials", "doronrpa@gmail.com", "adc.json")
if os.path.exists(cred):
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", cred)

import firebase_admin
from firebase_admin import firestore
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()
db = firestore.client()

print("Cleaning batch_reprocess_results...")
deleted = 0
batch = db.batch()
batch_count = 0

for doc in db.collection("batch_reprocess_results").stream():
    data = doc.to_dict()
    if data.get("dry_run_complete") or data.get("dry_run"):
        batch.delete(doc.reference)
        batch_count += 1
        deleted += 1
        if batch_count >= 450:
            batch.commit()
            batch = db.batch()
            batch_count = 0

if batch_count > 0:
    batch.commit()

print(f"Deleted {deleted} old dry-run results.")
