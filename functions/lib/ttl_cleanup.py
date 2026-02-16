"""
TTL cleanup for Firestore collections.
Assignment 16 — Cleanup scanner_logs + Files TTL.

scanner_logs: ~76K docs, batch-deleted via collection_streamer.
Smaller collections: simple stream + delete.
"""

import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("rcb.ttl_cleanup")


def cleanup_scanner_logs(db, max_age_days=30, dry_run=False):
    """
    Delete scanner_logs documents older than max_age_days.

    Uses collection_streamer for memory-safe iteration.
    Batch deletes 450 docs per commit.

    scanner_logs docs have:
      - timestamp: ISO 8601 string (e.g. "2026-01-15T12:00:00.000Z")
      - doc ID: "scan_{epoch_ms}"
    """
    from lib.collection_streamer import stream_collection

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    cutoff_iso = cutoff.isoformat()
    cutoff_epoch_ms = int(cutoff.timestamp() * 1000)

    stats = {"deleted": 0, "skipped": 0, "errors": 0, "batches_committed": 0}

    batch = db.batch()
    batch_count = 0

    for doc_batch in stream_collection(db, "scanner_logs", batch_size=500):
        for doc in doc_batch:
            try:
                data = doc.to_dict()
                if _is_doc_old(data, doc.id, cutoff_iso, cutoff_epoch_ms):
                    if not dry_run:
                        batch.delete(doc.reference)
                        batch_count += 1
                    stats["deleted"] += 1

                    if batch_count >= 450:
                        batch.commit()
                        stats["batches_committed"] += 1
                        batch = db.batch()
                        batch_count = 0
                else:
                    stats["skipped"] += 1
            except Exception as e:
                logger.warning(f"Error processing {doc.id}: {e}")
                stats["errors"] += 1

    if batch_count > 0 and not dry_run:
        batch.commit()
        stats["batches_committed"] += 1

    return stats


def _is_doc_old(data, doc_id, cutoff_iso, cutoff_epoch_ms):
    """
    Check if a scanner_logs doc is older than the cutoff.

    1. Try timestamp field (ISO string comparison)
    2. Fallback: extract epoch from doc ID (scan_{epoch_ms})
    3. Neither works: treat as old (orphaned doc)
    """
    ts = data.get("timestamp")
    if ts and isinstance(ts, str):
        try:
            return ts < cutoff_iso
        except Exception:
            pass

    if doc_id and doc_id.startswith("scan_"):
        try:
            epoch_ms = int(doc_id.split("_", 1)[1])
            return epoch_ms < cutoff_epoch_ms
        except (ValueError, TypeError, IndexError):
            pass

    return True


def cleanup_collection_by_field(db, collection_name, timestamp_field,
                                max_age_days, dry_run=False):
    """
    Generic TTL cleanup for smaller collections with Firestore Timestamp fields.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    stats = {"deleted": 0, "skipped": 0, "errors": 0}

    try:
        docs = db.collection(collection_name).stream()
        for doc in docs:
            try:
                data = doc.to_dict()
                ts = data.get(timestamp_field)
                if ts and ts < cutoff:
                    if not dry_run:
                        doc.reference.delete()
                    stats["deleted"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                logger.warning(f"Error on {collection_name}/{doc.id}: {e}")
                stats["errors"] += 1
    except Exception as e:
        logger.error(f"Failed to stream {collection_name}: {e}")
        stats["errors"] += 1

    return stats
