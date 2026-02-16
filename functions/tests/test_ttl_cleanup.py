"""
Tests for ttl_cleanup — scanner_logs + collection TTL.
Assignment 16.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.ttl_cleanup import cleanup_scanner_logs, _is_doc_old, cleanup_collection_by_field


# ── _is_doc_old ──────────────────────────────────────────────

class TestIsDocOld:
    """Age-detection logic for scanner_logs documents."""

    def _cutoffs(self, dt):
        return dt.isoformat(), int(dt.timestamp() * 1000)

    def test_old_iso_timestamp(self):
        iso, epoch = self._cutoffs(datetime(2026, 1, 15, tzinfo=timezone.utc))
        assert _is_doc_old({"timestamp": "2025-12-01T00:00:00.000Z"}, "scan_1", iso, epoch) is True

    def test_recent_iso_timestamp(self):
        iso, epoch = self._cutoffs(datetime(2026, 1, 15, tzinfo=timezone.utc))
        assert _is_doc_old({"timestamp": "2026-02-01T00:00:00.000Z"}, "scan_1", iso, epoch) is False

    def test_fallback_to_doc_id_old(self):
        iso, epoch = self._cutoffs(datetime(2026, 1, 15, tzinfo=timezone.utc))
        old_epoch = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        assert _is_doc_old({}, f"scan_{old_epoch}", iso, epoch) is True

    def test_fallback_to_doc_id_recent(self):
        iso, epoch = self._cutoffs(datetime(2026, 1, 15, tzinfo=timezone.utc))
        recent_epoch = int(datetime(2026, 2, 1, tzinfo=timezone.utc).timestamp() * 1000)
        assert _is_doc_old({}, f"scan_{recent_epoch}", iso, epoch) is False

    def test_orphaned_doc_treated_as_old(self):
        iso, epoch = self._cutoffs(datetime(2026, 1, 15, tzinfo=timezone.utc))
        assert _is_doc_old({}, "random_doc_id", iso, epoch) is True

    def test_none_timestamp_uses_doc_id(self):
        iso, epoch = self._cutoffs(datetime(2026, 1, 15, tzinfo=timezone.utc))
        recent_epoch = int(datetime(2026, 2, 10, tzinfo=timezone.utc).timestamp() * 1000)
        assert _is_doc_old({"timestamp": None}, f"scan_{recent_epoch}", iso, epoch) is False


# ── cleanup_scanner_logs ─────────────────────────────────────

class TestCleanupScannerLogs:
    """Batch cleanup logic for scanner_logs."""

    def _make_doc(self, doc_id, timestamp_iso):
        doc = Mock()
        doc.id = doc_id
        doc.to_dict.return_value = {"timestamp": timestamp_iso}
        doc.reference = Mock()
        return doc

    @patch("lib.collection_streamer.stream_collection")
    def test_dry_run_no_delete(self, mock_stream):
        old_doc = self._make_doc("scan_1000000000000", "2020-01-01T00:00:00Z")
        mock_stream.return_value = [[old_doc]]

        db = Mock()
        result = cleanup_scanner_logs(db, max_age_days=30, dry_run=True)

        assert result["deleted"] == 1
        assert result["batches_committed"] == 0

    @patch("lib.collection_streamer.stream_collection")
    def test_old_docs_deleted(self, mock_stream):
        docs = [self._make_doc(f"scan_{1000 + i}", "2020-01-01T00:00:00Z") for i in range(5)]
        mock_stream.return_value = [docs]

        db = Mock()
        mock_batch = Mock()
        db.batch.return_value = mock_batch

        result = cleanup_scanner_logs(db, max_age_days=30)

        assert result["deleted"] == 5
        assert mock_batch.delete.call_count == 5
        assert mock_batch.commit.call_count == 1

    @patch("lib.collection_streamer.stream_collection")
    def test_recent_docs_skipped(self, mock_stream):
        recent = self._make_doc("scan_9999999999999", "2099-01-01T00:00:00Z")
        mock_stream.return_value = [[recent]]

        db = Mock()
        mock_batch = Mock()
        db.batch.return_value = mock_batch

        result = cleanup_scanner_logs(db, max_age_days=30)

        assert result["deleted"] == 0
        assert result["skipped"] == 1
        mock_batch.delete.assert_not_called()

    @patch("lib.collection_streamer.stream_collection")
    def test_batch_commits_at_450(self, mock_stream):
        docs = [self._make_doc(f"scan_{1000 + i}", "2020-01-01T00:00:00Z") for i in range(460)]
        mock_stream.return_value = [docs]

        db = Mock()
        mock_batch = Mock()
        db.batch.return_value = mock_batch

        result = cleanup_scanner_logs(db, max_age_days=30)

        assert result["deleted"] == 460
        assert result["batches_committed"] == 2

    @patch("lib.collection_streamer.stream_collection")
    def test_empty_collection(self, mock_stream):
        mock_stream.return_value = []

        db = Mock()
        mock_batch = Mock()
        db.batch.return_value = mock_batch

        result = cleanup_scanner_logs(db, max_age_days=30)

        assert result["deleted"] == 0
        assert result["skipped"] == 0
        assert result["batches_committed"] == 0


# ── cleanup_collection_by_field ──────────────────────────────

class TestCleanupCollectionByField:
    """Generic collection TTL cleanup."""

    def _make_doc(self, doc_id, ts):
        doc = Mock()
        doc.id = doc_id
        doc.to_dict.return_value = {"timestamp": ts}
        doc.reference = Mock()
        return doc

    def test_deletes_old_docs(self):
        old_ts = datetime.now(timezone.utc) - timedelta(days=100)
        doc = self._make_doc("doc1", old_ts)
        db = Mock()
        db.collection.return_value.stream.return_value = [doc]

        result = cleanup_collection_by_field(db, "rcb_logs", "timestamp", max_age_days=90)

        assert result["deleted"] == 1
        doc.reference.delete.assert_called_once()

    def test_skips_recent_docs(self):
        recent_ts = datetime.now(timezone.utc) - timedelta(days=10)
        doc = self._make_doc("doc1", recent_ts)
        db = Mock()
        db.collection.return_value.stream.return_value = [doc]

        result = cleanup_collection_by_field(db, "rcb_logs", "timestamp", max_age_days=90)

        assert result["deleted"] == 0
        assert result["skipped"] == 1
        doc.reference.delete.assert_not_called()

    def test_dry_run_no_delete(self):
        old_ts = datetime.now(timezone.utc) - timedelta(days=100)
        doc = self._make_doc("doc1", old_ts)
        db = Mock()
        db.collection.return_value.stream.return_value = [doc]

        result = cleanup_collection_by_field(db, "rcb_logs", "timestamp", max_age_days=90, dry_run=True)

        assert result["deleted"] == 1
        doc.reference.delete.assert_not_called()

    def test_empty_collection(self):
        db = Mock()
        db.collection.return_value.stream.return_value = []

        result = cleanup_collection_by_field(db, "rcb_logs", "timestamp", max_age_days=90)

        assert result["deleted"] == 0
        assert result["skipped"] == 0
        assert result["errors"] == 0
