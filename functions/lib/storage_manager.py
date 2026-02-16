"""
Storage manager for RCB.
Rule: Firestore for metadata + searchable fields.
      Cloud Storage for anything > 10 KB (full text, PDFs, raw files).

Bucket layout (inside default Firebase bucket or dedicated bucket):
    rcb-docs/
    ├── raw/                    # Original downloaded files (PDF, HTML, images)
    │   ├── directives/
    │   ├── pre_rulings/
    │   ├── attachments/
    │   └── emails/
    ├── texts/                  # Extracted text (when > 10 KB)
    │   ├── directives/
    │   ├── pre_rulings/
    │   ├── attachments/
    │   └── emails/
    └── exports/                # Backups, reports

Session 28C — Assignment 20.
NEW FILE — does not modify any existing code.
"""

import hashlib
import logging
import os
from datetime import datetime

logger = logging.getLogger("rcb.storage_manager")

# Default bucket — matches existing Firebase setup.
# Override via env var if a dedicated bucket is created later.
BUCKET_NAME = os.environ.get(
    "RCB_STORAGE_BUCKET", "rpa-port-customs.appspot.com"
)

# Prefix inside the bucket for new document storage
BUCKET_PREFIX = "rcb-docs"

# Anything larger than this goes to Cloud Storage instead of Firestore
TEXT_SIZE_THRESHOLD = 10_000  # 10 KB


# ──────────────────────────────────────────────
#  Smart text storage
# ──────────────────────────────────────────────

def store_text_smart(text, collection, doc_id):
    """
    Store text in the right place based on size.

    Returns:
        dict to merge into the Firestore document.
        If text <= 10 KB → ``full_text`` stored directly in Firestore.
        If text > 10 KB → Cloud Storage gets the text; Firestore gets a preview + path.
    """
    text_bytes = text.encode("utf-8")

    if len(text_bytes) <= TEXT_SIZE_THRESHOLD:
        return {
            "full_text": text,
            "full_text_storage": "firestore",
            "full_text_length": len(text),
        }

    path = f"{BUCKET_PREFIX}/texts/{collection}/{doc_id}.txt"
    upload_to_gcs(BUCKET_NAME, path, text_bytes)

    return {
        "full_text_preview": text[:500],
        "full_text_path": f"gs://{BUCKET_NAME}/{path}",
        "full_text_storage": "cloud_storage",
        "full_text_length": len(text),
    }


def retrieve_full_text(doc_dict):
    """
    Retrieve full text regardless of where it's stored.

    Args:
        doc_dict: dict — Firestore document data (already ``.to_dict()``).

    Returns:
        str — the full text content.
    """
    if doc_dict.get("full_text_storage") == "cloud_storage":
        gs_path = doc_dict.get("full_text_path", "")
        prefix = f"gs://{BUCKET_NAME}/"
        path = gs_path.replace(prefix, "") if gs_path.startswith(prefix) else gs_path
        content = download_from_gcs(BUCKET_NAME, path)
        return content.decode("utf-8")

    return doc_dict.get("full_text", "")


# ──────────────────────────────────────────────
#  Raw file storage
# ──────────────────────────────────────────────

def store_raw_file(file_bytes, source_type, filename):
    """
    Store original file (PDF, HTML, etc.) in Cloud Storage.

    Args:
        file_bytes: bytes
        source_type: str — e.g. "attachments", "directives"
        filename: str — original file name

    Returns:
        str — gs:// path to the stored file
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    file_hash = hashlib.md5(file_bytes).hexdigest()[:8]
    safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
    path = f"{BUCKET_PREFIX}/raw/{source_type}/{date_str}/{file_hash}_{safe_name}"
    upload_to_gcs(BUCKET_NAME, path, file_bytes)
    return f"gs://{BUCKET_NAME}/{path}"


# ──────────────────────────────────────────────
#  Low-level GCS helpers
# ──────────────────────────────────────────────

def upload_to_gcs(bucket_name, path, content):
    """Upload bytes to Cloud Storage."""
    try:
        from google.cloud import storage as gcs
        client = gcs.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(path)
        blob.upload_from_string(content)
        logger.debug(f"Uploaded {len(content)} bytes → gs://{bucket_name}/{path}")
    except Exception as e:
        logger.error(f"GCS upload failed ({path}): {e}")
        raise


def download_from_gcs(bucket_name, path):
    """Download bytes from Cloud Storage."""
    try:
        from google.cloud import storage as gcs
        client = gcs.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(path)
        return blob.download_as_bytes()
    except Exception as e:
        logger.error(f"GCS download failed ({path}): {e}")
        raise


def get_bucket_size_mb(bucket_name=None):
    """Get total bucket size in MB (for monitoring dashboards)."""
    bucket_name = bucket_name or BUCKET_NAME
    try:
        from google.cloud import storage as gcs
        client = gcs.Client()
        bucket = client.bucket(bucket_name)
        total = sum(blob.size for blob in bucket.list_blobs())
        return round(total / (1024 * 1024), 2)
    except Exception as e:
        logger.error(f"Bucket size check failed: {e}")
        return -1
