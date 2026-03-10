"""
Tests for inbox_relearner.py — cc@ mailbox relearning.
Guard test runs FIRST.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════
#  TEST 1: PROTECTED_COLLECTIONS GUARD
# ═══════════════════════════════════════════════════════════

class TestProtectedCollectionsGuard:

    def test_write_to_tariff_raises(self):
        from lib.inbox_relearner import _safe_write, ProtectedCollectionError
        db = MagicMock()
        with pytest.raises(ProtectedCollectionError, match="tariff"):
            _safe_write(db, "tariff", "doc", {"x": 1})
        db.collection.assert_not_called()

    def test_write_to_learned_classifications_raises(self):
        from lib.inbox_relearner import _safe_write, ProtectedCollectionError
        db = MagicMock()
        with pytest.raises(ProtectedCollectionError, match="learned_classifications"):
            _safe_write(db, "learned_classifications", "doc", {"x": 1})
        db.collection.assert_not_called()

    def test_all_protected_blocked(self):
        from lib.inbox_relearner import _safe_write, ProtectedCollectionError, PROTECTED_COLLECTIONS
        db = MagicMock()
        for coll in PROTECTED_COLLECTIONS:
            with pytest.raises(ProtectedCollectionError):
                _safe_write(db, coll, "test", {"x": 1})
            db.collection.assert_not_called()

    def test_unknown_collection_blocked(self):
        from lib.inbox_relearner import _safe_write, ProtectedCollectionError
        db = MagicMock()
        with pytest.raises(ProtectedCollectionError, match="random_coll"):
            _safe_write(db, "random_coll", "doc", {"x": 1})

    def test_inbox_learning_allowed(self):
        from lib.inbox_relearner import _safe_write
        db = MagicMock()
        _safe_write(db, "inbox_learning", "doc1", {"data": 1})
        db.collection.assert_called_with("inbox_learning")

    def test_inbox_learning_log_allowed(self):
        from lib.inbox_relearner import _safe_write
        db = MagicMock()
        _safe_write(db, "inbox_learning_log", "run1", {"data": 1})
        db.collection.assert_called_with("inbox_learning_log")

    def test_inbox_learning_state_allowed(self):
        from lib.inbox_relearner import _safe_write
        db = MagicMock()
        _safe_write(db, "inbox_learning_state", "cursor", {"skip": 0})
        db.collection.assert_called_with("inbox_learning_state")

    def test_protected_is_frozenset(self):
        from lib.inbox_relearner import PROTECTED_COLLECTIONS
        assert isinstance(PROTECTED_COLLECTIONS, frozenset)

    def test_guard_before_firestore(self):
        from lib.inbox_relearner import _safe_write, ProtectedCollectionError
        db = MagicMock()
        try:
            _safe_write(db, "chapter_notes", "x", {})
        except ProtectedCollectionError:
            pass
        db.collection.assert_not_called()


# ═══════════════════════════════════════════════════════════
#  TEST 2: EMAIL ANALYSIS (pure function, no I/O)
# ═══════════════════════════════════════════════════════════

class TestEmailAnalysis:

    def _make_msg(self, subject="Test", body="Hello", from_addr="user@example.com"):
        return {
            "id": "graph_id_123",
            "internetMessageId": "<msg@example.com>",
            "subject": subject,
            "from": {"emailAddress": {"address": from_addr, "name": "Test User"}},
            "toRecipients": [{"emailAddress": {"address": "cc@rpa-port.co.il"}}],
            "ccRecipients": [],
            "receivedDateTime": "2026-03-09T10:00:00Z",
            "body": {"content": f"<div>{body}</div>"},
            "hasAttachments": False,
            "conversationId": "conv_123",
        }

    def test_extracts_hs_codes(self):
        from lib.inbox_relearner import _analyze_email
        msg = self._make_msg(body="Classification 8413.91.0000 approved for pumps")
        result = _analyze_email(msg)
        assert any("8413" in c for c in result["hs_codes"])

    def test_extracts_containers(self):
        from lib.inbox_relearner import _analyze_email
        msg = self._make_msg(body="Container GAOU6394772 loaded on vessel")
        result = _analyze_email(msg)
        assert "GAOU6394772" in result["containers"]

    def test_extracts_bols(self):
        from lib.inbox_relearner import _analyze_email
        msg = self._make_msg(body="BL No. MEDURS12345678 shipped from Haifa")
        result = _analyze_email(msg)
        assert any("MEDURS12345678" in b for b in result["bols"])

    def test_detects_invoice_doc_type(self):
        from lib.inbox_relearner import _analyze_email
        msg = self._make_msg(subject="Commercial Invoice #12345", body="Total amount USD 5,000")
        result = _analyze_email(msg)
        assert "commercial_invoice" in result["document_types"]

    def test_detects_packing_list(self):
        from lib.inbox_relearner import _analyze_email
        msg = self._make_msg(body="Packing List - Gross weight 500 kg, Net weight 450 kg")
        result = _analyze_email(msg)
        assert "packing_list" in result["document_types"]

    def test_detects_bol_doc_type(self):
        from lib.inbox_relearner import _analyze_email
        msg = self._make_msg(body="Bill of Lading - Shipped on board, consignee: ACME Ltd")
        result = _analyze_email(msg)
        assert "bill_of_lading" in result["document_types"]

    def test_extracts_sender_info(self):
        from lib.inbox_relearner import _analyze_email
        msg = self._make_msg(from_addr="Shipper@maersk.com")
        result = _analyze_email(msg)
        assert result["from_email"] == "shipper@maersk.com"

    def test_body_snippet_capped(self):
        from lib.inbox_relearner import _analyze_email
        msg = self._make_msg(body="x" * 1000)
        result = _analyze_email(msg)
        assert len(result["body_snippet"]) <= 500

    def test_empty_body_handled(self):
        from lib.inbox_relearner import _analyze_email
        msg = self._make_msg(body="")
        result = _analyze_email(msg)
        assert result["body_snippet"] == ""
        assert result["hs_codes"] == []

    def test_product_description_extraction(self):
        from lib.inbox_relearner import _analyze_email
        msg = self._make_msg(body="Commodity: Steel bolts and nuts grade 8.8")
        result = _analyze_email(msg)
        assert len(result["product_descriptions"]) > 0


# ═══════════════════════════════════════════════════════════
#  TEST 3: CURSOR + IDEMPOTENCY
# ═══════════════════════════════════════════════════════════

class TestCursorAndIdempotency:

    def test_loads_state(self):
        from lib.inbox_relearner import _load_state
        db = MagicMock()
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {"skip": 100, "total_processed": 50, "completed": False}
        db.collection.return_value.document.return_value.get.return_value = doc
        state = _load_state(db)
        assert state["skip"] == 100
        assert state["total_processed"] == 50

    def test_default_state(self):
        from lib.inbox_relearner import _load_state
        db = MagicMock()
        doc = MagicMock()
        doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = doc
        state = _load_state(db)
        assert state["skip"] == 0
        assert state["completed"] is False

    def test_save_state_writes_learning_meta(self):
        from lib.inbox_relearner import _save_state
        db = MagicMock()
        _save_state(db, {"skip": 50, "total_processed": 25})
        call_args = db.collection.return_value.document.return_value.set.call_args
        written = call_args[0][0]
        assert written["data_tier"] == "learning"
        assert written["is_authoritative"] is False

    def test_completed_flag_stops_processing(self):
        from lib.inbox_relearner import relearn_inbox_batch
        db = MagicMock()
        doc = MagicMock()
        doc.exists = True
        doc.to_dict.return_value = {"skip": 500, "total_processed": 500, "completed": True}
        db.collection.return_value.document.return_value.get.return_value = doc
        result = relearn_inbox_batch(db, lambda x: "fake")
        assert result["status"] == "already_completed"


# ═══════════════════════════════════════════════════════════
#  TEST 4: GRACEFUL FAILURE
# ═══════════════════════════════════════════════════════════

class TestGracefulFailure:

    @patch("lib.inbox_relearner._get_graph_token_and_email", return_value=(None, None))
    def test_auth_failure_returns_error(self, mock_token):
        from lib.inbox_relearner import relearn_inbox_batch
        db = MagicMock()
        # State: not completed
        state_doc = MagicMock()
        state_doc.exists = True
        state_doc.to_dict.return_value = {"skip": 0, "total_processed": 0, "completed": False}
        db.collection.return_value.document.return_value.get.return_value = state_doc
        result = relearn_inbox_batch(db, lambda x: None)
        assert result["status"] == "auth_error"

    @patch("lib.inbox_relearner._fetch_messages", return_value=([], None))
    @patch("lib.inbox_relearner._get_graph_token_and_email", return_value=("fake_token", "rcb@rpa-port.co.il"))
    def test_empty_mailbox_marks_complete(self, mock_token, mock_fetch):
        from lib.inbox_relearner import relearn_inbox_batch
        db = MagicMock()
        state_doc = MagicMock()
        state_doc.exists = True
        state_doc.to_dict.return_value = {"skip": 0, "total_processed": 0, "completed": False}
        db.collection.return_value.document.return_value.get.return_value = state_doc
        result = relearn_inbox_batch(db, lambda x: "fake")
        assert result["status"] == "scan_complete"


# ═══════════════════════════════════════════════════════════
#  TEST 5: TIER 2 METADATA
# ═══════════════════════════════════════════════════════════

class TestTier2Metadata:

    def test_meta_fields(self):
        from lib.inbox_relearner import _tier2_meta
        meta = _tier2_meta()
        assert meta["data_tier"] == "learning"
        assert meta["is_authoritative"] is False
        assert meta["source"] == "cc_mailbox_relearn"
        assert "fetched_at" in meta

    def test_html_stripping(self):
        from lib.inbox_relearner import _strip_html
        assert _strip_html("<div><p>Hello &amp; World</p></div>") == "Hello & World"
        assert _strip_html("") == ""
        assert _strip_html(None) == ""
