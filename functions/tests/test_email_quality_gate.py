"""
Tests for Email Quality Gate (Session 45)
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os
import hashlib
from datetime import datetime, timezone, timedelta

# Add lib directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lib'))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.rcb_helpers import (
    email_quality_gate,
    _log_email_quality,
    _GENERIC_SUBJECTS,
    _PLACEHOLDER_RE,
    _TD_RE,
)


# ── Helpers ──

def _good_body(extra=""):
    """Return a valid HTML body over 200 chars with real table data."""
    return (
        '<html><body>'
        '<table>'
        '<tr><td>BL Number</td><td>MEDURS12345</td></tr>'
        '<tr><td>Vessel</td><td>MSC ANNA</td></tr>'
        '<tr><td>Container</td><td>GAOU6394772</td></tr>'
        '<tr><td>Status</td><td>Active</td></tr>'
        '</table>'
        f'{extra}'
        '<p>This email contains real shipping tracking data for your deal.</p>'
        '</body></html>'
    )


def _placeholder_body():
    """Return a body where ALL td cells are placeholders."""
    return (
        '<html><body>'
        '<table>'
        '<tr><td>—</td><td>—</td></tr>'
        '<tr><td>טרם הגיע</td><td>—</td></tr>'
        '<tr><td> - </td><td>  </td></tr>'
        '</table>'
        '<p>Some filler text to get past the 200 char minimum threshold for the body.</p>'
        '</body></html>'
    )


def _mock_db(dedup_doc=None, subj_doc=None, digest_doc=None):
    """Build a mock Firestore db with configurable document returns."""
    db = MagicMock()
    collection_mock = MagicMock()
    db.collection.return_value = collection_mock

    # Default: no existing documents
    default_doc = MagicMock()
    default_doc.exists = False

    def _doc_side_effect(key):
        doc_mock = MagicMock()
        if key.startswith("dedup_") and dedup_doc is not None:
            doc_mock.get.return_value = dedup_doc
        elif key.startswith("subj_") and subj_doc is not None:
            doc_mock.get.return_value = subj_doc
        elif key.startswith("digest_") and digest_doc is not None:
            doc_mock.get.return_value = digest_doc
        else:
            empty = MagicMock()
            empty.exists = False
            doc_mock.get.return_value = empty
        return doc_mock

    collection_mock.document.side_effect = _doc_side_effect
    return db


def _make_firestore_doc(data, exists=True):
    """Create a mock Firestore document snapshot."""
    doc = MagicMock()
    doc.exists = exists
    doc.to_dict.return_value = data
    return doc


# ============================================================
# Rule 1: Body empty or under 200 characters
# ============================================================

class TestRule1BodyTooShort:
    def test_empty_body(self):
        ok, reason = email_quality_gate("user@test.com", "RCB | Deal", "")
        assert not ok
        assert reason == "body_under_200"

    def test_none_body(self):
        ok, reason = email_quality_gate("user@test.com", "RCB | Deal", None)
        assert not ok
        assert reason == "body_under_200"

    def test_short_body(self):
        ok, reason = email_quality_gate("user@test.com", "RCB | Deal", "<p>Hi</p>")
        assert not ok
        assert reason == "body_under_200"

    def test_exactly_200_chars(self):
        body = "x" * 200
        ok, reason = email_quality_gate("user@test.com", "RCB | Deal", body)
        assert ok
        assert reason == "approved"

    def test_199_chars_rejected(self):
        body = "x" * 199
        ok, reason = email_quality_gate("user@test.com", "RCB | Deal", body)
        assert not ok
        assert reason == "body_under_200"


# ============================================================
# Rule 2: Subject empty, generic, or unchanged
# ============================================================

class TestRule2Subject:
    def test_empty_subject(self):
        ok, reason = email_quality_gate("user@test.com", "", _good_body())
        assert not ok
        assert reason == "empty_subject"

    def test_none_subject(self):
        ok, reason = email_quality_gate("user@test.com", None, _good_body())
        assert not ok
        assert reason == "empty_subject"

    def test_whitespace_subject(self):
        ok, reason = email_quality_gate("user@test.com", "   ", _good_body())
        assert not ok
        assert reason == "empty_subject"

    def test_generic_test(self):
        ok, reason = email_quality_gate("user@test.com", "test", _good_body())
        assert not ok
        assert reason == "generic_subject"

    def test_generic_hello(self):
        ok, reason = email_quality_gate("user@test.com", "hello", _good_body())
        assert not ok
        assert reason == "generic_subject"

    def test_generic_hebrew(self):
        ok, reason = email_quality_gate("user@test.com", "בדיקה", _good_body())
        assert not ok
        assert reason == "generic_subject"

    def test_generic_update(self):
        ok, reason = email_quality_gate("user@test.com", "update", _good_body())
        assert not ok
        assert reason == "generic_subject"

    def test_only_re_prefix(self):
        ok, reason = email_quality_gate("user@test.com", "Re: Re: FW:", _good_body())
        assert not ok
        assert reason == "generic_subject"

    def test_real_subject_passes(self):
        ok, reason = email_quality_gate("user@test.com", "RCB | MEDURS12345 | 3/5 Released", _good_body())
        assert ok

    def test_unchanged_subject_with_db(self):
        subj = "RCB | DEAL123 | Status"
        subj_doc = _make_firestore_doc({"subject": subj, "timestamp": datetime.now(timezone.utc).isoformat()})
        db = _mock_db(subj_doc=subj_doc)
        ok, reason = email_quality_gate(
            "user@test.com", subj, _good_body(),
            deal_id="DEAL123", db=db)
        assert not ok
        assert reason == "unchanged_subject"

    def test_changed_subject_with_db(self):
        subj_doc = _make_firestore_doc({"subject": "RCB | DEAL123 | Old Status"})
        db = _mock_db(subj_doc=subj_doc)
        ok, reason = email_quality_gate(
            "user@test.com", "RCB | DEAL123 | New Status", _good_body(),
            deal_id="DEAL123", db=db)
        assert ok


# ============================================================
# Rule 3: All data cells are placeholder
# ============================================================

class TestRule3PlaceholderData:
    def test_all_placeholder_cells(self):
        ok, reason = email_quality_gate("user@test.com", "RCB | Deal", _placeholder_body())
        assert not ok
        assert reason == "all_placeholder_data"

    def test_mixed_cells_passes(self):
        ok, reason = email_quality_gate("user@test.com", "RCB | Deal", _good_body())
        assert ok

    def test_few_cells_skipped(self):
        """Tables with 3 or fewer td cells skip the check."""
        body = (
            '<html><body>'
            '<table><tr><td>—</td><td>—</td><td>—</td></tr></table>'
            '<p>' + 'x' * 200 + '</p>'
            '</body></html>'
        )
        ok, reason = email_quality_gate("user@test.com", "RCB | Deal", body)
        assert ok

    def test_placeholder_em_dash(self):
        assert _PLACEHOLDER_RE.match("—")

    def test_placeholder_hebrew(self):
        assert _PLACEHOLDER_RE.match("טרם הגיע")

    def test_placeholder_dash(self):
        assert _PLACEHOLDER_RE.match("-")

    def test_placeholder_na(self):
        assert _PLACEHOLDER_RE.match("N/A")

    def test_real_data_no_match(self):
        assert not _PLACEHOLDER_RE.match("MEDURS12345")

    def test_real_data_vessel(self):
        assert not _PLACEHOLDER_RE.match("MSC ANNA")


# ============================================================
# Rule 4: Same deal_id + alert_type within 4 hours
# ============================================================

class TestRule4Dedup:
    def test_dedup_recent_blocked(self):
        ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        dedup_doc = _make_firestore_doc({"timestamp": ts})
        db = _mock_db(dedup_doc=dedup_doc)
        ok, reason = email_quality_gate(
            "user@test.com", "RCB | Alert", _good_body(),
            deal_id="D001", alert_type="gate_cutoff", db=db)
        assert not ok
        assert reason == "dedup_4h"

    def test_dedup_old_passes(self):
        ts = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        dedup_doc = _make_firestore_doc({"timestamp": ts})
        db = _mock_db(dedup_doc=dedup_doc)
        ok, reason = email_quality_gate(
            "user@test.com", "RCB | Alert", _good_body(),
            deal_id="D001", alert_type="gate_cutoff", db=db)
        assert ok

    def test_dedup_no_deal_id_skipped(self):
        """Without deal_id, dedup check is skipped."""
        db = _mock_db()
        ok, reason = email_quality_gate(
            "user@test.com", "RCB | Alert", _good_body(),
            deal_id=None, alert_type="gate_cutoff", db=db)
        assert ok

    def test_dedup_no_alert_type_skipped(self):
        db = _mock_db()
        ok, reason = email_quality_gate(
            "user@test.com", "RCB | Alert", _good_body(),
            deal_id="D001", alert_type=None, db=db)
        assert ok


# ============================================================
# Rule 5: Never send to self
# ============================================================

class TestRule5SelfSend:
    def test_self_send_blocked(self):
        ok, reason = email_quality_gate("rcb@rpa-port.co.il", "RCB | Deal", _good_body())
        assert not ok
        assert reason == "self_send"

    def test_self_send_case_insensitive(self):
        ok, reason = email_quality_gate("RCB@RPA-PORT.CO.IL", "RCB | Deal", _good_body())
        assert not ok
        assert reason == "self_send"

    def test_self_send_with_whitespace(self):
        ok, reason = email_quality_gate(" rcb@rpa-port.co.il ", "RCB | Deal", _good_body())
        assert not ok
        assert reason == "self_send"

    def test_other_recipient_passes(self):
        ok, reason = email_quality_gate("doron@rpa-port.co.il", "RCB | Deal", _good_body())
        assert ok


# ============================================================
# Rule 6: Digest content identical to last digest
# ============================================================

class TestRule6DuplicateDigest:
    def test_duplicate_digest_blocked(self):
        body = _good_body()
        content_hash = hashlib.md5(body.encode('utf-8', errors='replace')).hexdigest()
        digest_doc = _make_firestore_doc({"content_hash": content_hash})
        db = _mock_db(digest_doc=digest_doc)
        ok, reason = email_quality_gate(
            "doron@rpa-port.co.il", "RCB | דוח בוקר | 18.02.2026", body,
            alert_type="morning_digest", db=db)
        assert not ok
        assert reason == "duplicate_digest"

    def test_different_digest_passes(self):
        digest_doc = _make_firestore_doc({"content_hash": "old_hash_abc123"})
        db = _mock_db(digest_doc=digest_doc)
        ok, reason = email_quality_gate(
            "doron@rpa-port.co.il", "RCB | דוח בוקר | 18.02.2026", _good_body(),
            alert_type="morning_digest", db=db)
        assert ok

    def test_non_digest_skips_check(self):
        """Non-digest emails don't trigger the digest dedup."""
        body = _good_body()
        content_hash = hashlib.md5(body.encode('utf-8', errors='replace')).hexdigest()
        digest_doc = _make_firestore_doc({"content_hash": content_hash})
        db = _mock_db(digest_doc=digest_doc)
        ok, reason = email_quality_gate(
            "doron@rpa-port.co.il", "RCB | MEDURS12345 | Status", body,
            alert_type="tracker_update", db=db)
        assert ok


# ============================================================
# Rule 7: Block empty classification (Session 47)
# ============================================================

class TestRule7EmptyClassification:
    def test_classification_no_hs_codes_blocked(self):
        """Classification email with no HS codes in body is blocked."""
        body = '<html><body>' + 'x' * 300 + '</body></html>'
        subject = "[RCB-20260218-BALKI] \u2705 \u05e1\u05d9\u05d5\u05d5\u05d2 \u05d9\u05d1\u05d5\u05d0 | JSC BELSHINA"
        ok, reason = email_quality_gate("doron@rpa-port.co.il", subject, body)
        assert not ok
        assert reason == "empty_classification"

    def test_classification_with_hs_codes_passes(self):
        """Classification email containing HS codes is allowed."""
        body = '<html><body>' + 'x' * 200 + '<td>40.11.100000/2</td><td>12%</td>' + 'x' * 100 + '</body></html>'
        subject = "[RCB-20260218-XYZAB] \u2705 \u05e1\u05d9\u05d5\u05d5\u05d2 \u05d9\u05d1\u05d5\u05d0 | Test Corp"
        ok, reason = email_quality_gate("doron@rpa-port.co.il", subject, body)
        assert ok

    def test_non_classification_email_not_affected(self):
        """Non-classification emails (tracker, digest) are not affected by Rule 7."""
        body = '<html><body>' + 'x' * 300 + '</body></html>'
        subject = "RCB | Tracker Update | MEDURS12345"
        ok, reason = email_quality_gate("doron@rpa-port.co.il", subject, body)
        assert ok


# ============================================================
# Fail-open behavior
# ============================================================

class TestFailOpen:
    def test_gate_error_returns_approved(self):
        """If the gate function itself crashes, fail open."""
        with patch('lib.rcb_helpers._TD_RE') as mock_re:
            mock_re.findall.side_effect = Exception("regex engine exploded")
            ok, reason = email_quality_gate("user@test.com", "RCB | Deal", _good_body())
            assert ok
            assert reason == "gate_error_failopen"

    def test_firestore_error_skips_rules(self):
        """Firestore errors are caught and remaining rules skipped."""
        db = MagicMock()
        db.collection.side_effect = Exception("Firestore unavailable")
        ok, reason = email_quality_gate(
            "user@test.com", "RCB | Deal", _good_body(),
            deal_id="D001", alert_type="alert", db=db)
        # Should still approve — Firestore error is non-fatal
        assert ok

    def test_no_db_still_works(self):
        """Without db, local rules still run, Firestore rules skipped."""
        ok, reason = email_quality_gate("user@test.com", "RCB | Deal", _good_body())
        assert ok
        assert reason == "approved"


# ============================================================
# Approval path
# ============================================================

class TestApproval:
    def test_good_email_approved(self):
        ok, reason = email_quality_gate(
            "doron@rpa-port.co.il", "RCB | MEDURS12345 | 3/5 Released", _good_body())
        assert ok
        assert reason == "approved"

    def test_approved_with_db(self):
        db = _mock_db()
        ok, reason = email_quality_gate(
            "doron@rpa-port.co.il", "RCB | MEDURS12345 | Status", _good_body(),
            deal_id="D001", alert_type="status_update", db=db)
        assert ok
        assert reason == "approved"


# ============================================================
# Logging
# ============================================================

class TestLogging:
    def test_log_on_approval(self):
        db = _mock_db()
        email_quality_gate(
            "doron@rpa-port.co.il", "RCB | Deal", _good_body(),
            deal_id="D001", alert_type="status_update", db=db)
        # Verify .add() was called (log record)
        db.collection.return_value.add.assert_called()
        record = db.collection.return_value.add.call_args[0][0]
        assert record["approved"] is True
        assert record["reason"] == "approved"

    def test_log_on_rejection(self):
        db = MagicMock()
        db.collection.return_value = MagicMock()
        email_quality_gate("rcb@rpa-port.co.il", "RCB | Deal", _good_body(), db=db)
        db.collection.return_value.add.assert_called()
        record = db.collection.return_value.add.call_args[0][0]
        assert record["approved"] is False
        assert record["reason"] == "self_send"

    def test_no_db_no_crash(self):
        """Logging with db=None should not crash."""
        _log_email_quality(None, True, "approved", "to@test.com", "subj",
                           None, None, "hash123")
        # Should complete without error


# ============================================================
# helper_graph_send integration
# ============================================================

class TestGraphSendIntegration:
    @patch('lib.rcb_helpers.requests')
    def test_send_blocked_by_gate(self, mock_requests):
        """helper_graph_send returns False when gate rejects."""
        from lib.rcb_helpers import helper_graph_send
        result = helper_graph_send(
            "token", "rcb@rpa-port.co.il", "rcb@rpa-port.co.il",
            "RCB | Deal", _good_body())
        assert result is False
        # Graph API should NOT be called
        mock_requests.post.assert_not_called()

    @patch('lib.rcb_helpers.requests')
    def test_send_allowed_by_gate(self, mock_requests):
        """helper_graph_send proceeds when gate approves."""
        mock_requests.post.return_value.status_code = 202
        from lib.rcb_helpers import helper_graph_send
        result = helper_graph_send(
            "token", "rcb@rpa-port.co.il", "doron@rpa-port.co.il",
            "RCB | MEDURS12345 | Status", _good_body())
        assert result is True
        mock_requests.post.assert_called_once()

    @patch('lib.rcb_helpers.requests')
    def test_send_gate_error_failopen(self, mock_requests):
        """If gate crashes, send still proceeds."""
        mock_requests.post.return_value.status_code = 202
        from lib.rcb_helpers import helper_graph_send
        with patch('lib.rcb_helpers.email_quality_gate', side_effect=Exception("boom")):
            result = helper_graph_send(
                "token", "rcb@rpa-port.co.il", "doron@rpa-port.co.il",
                "RCB | Deal Status", _good_body())
            assert result is True


# ============================================================
# Edge cases
# ============================================================

class TestEdgeCases:
    def test_body_with_only_html_tags(self):
        """Body with HTML structure but no text content."""
        body = '<html><body><div><table></table></div></body></html>' + 'x' * 200
        ok, reason = email_quality_gate("user@test.com", "RCB | Deal", body)
        assert ok  # No td cells, so placeholder check skipped

    def test_unicode_in_subject(self):
        ok, reason = email_quality_gate(
            "user@test.com", "RCB | מעקב משלוח | MEDURS12345", _good_body())
        assert ok

    def test_none_recipient(self):
        """None recipient should not crash (rule 5 checks for it)."""
        ok, reason = email_quality_gate(None, "RCB | Deal", _good_body())
        assert ok

    def test_generic_subjects_frozen(self):
        """Verify _GENERIC_SUBJECTS is a frozenset."""
        assert isinstance(_GENERIC_SUBJECTS, frozenset)
        assert "test" in _GENERIC_SUBJECTS
        assert "hello" in _GENERIC_SUBJECTS
        assert "בדיקה" in _GENERIC_SUBJECTS
