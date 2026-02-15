"""
Upload session/transcript files from Downloads to Firestore session_backups.
Adds NEW documents only — never overwrites existing backups.
"""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

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

DOWNLOADS = Path(os.path.expanduser("~/Downloads"))

# Collect readable session/transcript files (skip zips/tars)
SKIP_EXT = {".zip", ".gz", ".tar", ".rar", ".7z"}

files = []
for f in DOWNLOADS.iterdir():
    if not f.is_file():
        continue
    if f.suffix.lower() in SKIP_EXT:
        continue
    name_lower = f.name.lower()
    if "session" in name_lower or "transcript" in name_lower:
        files.append(f)

# Sort by file modification time (chronological)
files.sort(key=lambda f: f.stat().st_mtime)

print(f"Found {len(files)} readable session/transcript files\n")

# Check existing backups to avoid duplicates
existing_ids = set()
try:
    for doc in db.collection("session_backups").stream():
        existing_ids.add(doc.id)
except Exception as e:
    print(f"Warning: could not read existing backups: {e}")

uploaded = 0
skipped = 0

for i, f in enumerate(files, 1):
    mtime = datetime.fromtimestamp(f.stat().st_mtime)
    # Create a unique session_id from filename
    safe_name = re.sub(r'[^\w\-]', '_', f.stem)
    session_id = f"downloads_{safe_name}"

    if session_id in existing_ids:
        print(f"  [{i}/{len(files)}] SKIP (exists): {f.name}")
        skipped += 1
        continue

    try:
        content = f.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"  [{i}/{len(files)}] ERROR reading {f.name}: {e}")
        continue

    # Upload to Firestore
    doc_data = {
        "session_id": session_id,
        "original_filename": f.name,
        "content": content,
        "file_date": mtime.strftime("%Y-%m-%d %H:%M:%S"),
        "file_size_bytes": f.stat().st_size,
        "source": "downloads_archive",
        "uploaded_at": firestore.SERVER_TIMESTAMP,
        "order": i,
    }

    db.collection("session_backups").document(session_id).set(doc_data)
    uploaded += 1
    print(f"  [{i}/{len(files)}] UPLOADED: {f.name} ({len(content):,} chars, {mtime.strftime('%Y-%m-%d %H:%M')})")

print(f"\nDone: {uploaded} uploaded, {skipped} skipped (already existed)")
print(f"Total in session_backups: {len(existing_ids) + uploaded}")
