"""
Tests for Email Body Intelligence — Intent Classifier + Smart Router
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os
import time
from datetime import datetime, timezone, timedelta

# Add lib directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lib'))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.email_intent import (
    _get_sender_privilege,
    _get_body_text,
    _get_sender_address,
    detect_email_intent,
    _extract_status_entities,
    _extract_customs_entities,
    _question_hash,
    _check_cache,
    _is_rate_limited,
    _send_reply_safe,
    _wrap_html_rtl,
    _classify_instruction,
    _detect_instruction_scope,
    _check_pending_clarification,
    _send_clarification,
    CLARIFICATION_MESSAGES,
    process_email_intent,
    ADMIN_EMAIL,
    TEAM_DOMAIN,
)


# ── Helpers ──

def _make_msg(from_addr="doron@rpa-port.co.il", subject="Test", body="Test body",
              body_type="text", msg_id="msg123", has_attachments=False):
    return {
        "id": msg_id,
        "subject": subject,
        "from": {"emailAddress": {"address": from_addr, "name": "Test User"}},
        "body": {"content": body, "contentType": body_type},
        "bodyPreview": body[:100],
        "hasAttachments": has_attachments,
    }


def _mock_db_no_cache():
    """Mock DB that returns no cache hits and no rate limit."""
    db = Mock()
    # questions_log cache miss
    mock_doc = Mock()
    mock_doc.exists = False
    db.collection.return_value.document.return_value.get.return_value = mock_doc
    # rate limit query returns empty
    db.collection.return_value.where.return_value.where.return_value.limit.return_value.stream.return_value = []
    return db


# ============================================================
# SENDER PRIVILEGE TESTS
# ============================================================

class TestSenderPrivilege:
    def test_admin_email(self):
        assert _get_sender_privilege("doron@rpa-port.co.il") == "ADMIN"

    def test_admin_email_case_insensitive(self):
        assert _get_sender_privilege("Doron@RPA-Port.co.il") == "ADMIN"

    def test_admin_email_with_spaces(self):
        assert _get_sender_privilege("  doron@rpa-port.co.il  ") == "ADMIN"

    def test_team_member(self):
        assert _get_sender_privilege("amit@rpa-port.co.il") == "TEAM"

    def test_team_member_case_insensitive(self):
        assert _get_sender_privilege("Amit@RPA-PORT.CO.IL") == "TEAM"

    def test_external_sender(self):
        assert _get_sender_privilege("someone@gmail.com") == "NONE"

    def test_external_similar_domain(self):
        assert _get_sender_privilege("doron@not-rpa-port.co.il") == "NONE"

    def test_empty_email(self):
        assert _get_sender_privilege("") == "NONE"


# ============================================================
# BODY TEXT EXTRACTION TESTS
# ============================================================

class TestBodyTextExtraction:
    def test_plain_text(self):
        msg = _make_msg(body="Hello world", body_type="text")
        assert _get_body_text(msg) == "Hello world"

    def test_html_stripped(self):
        msg = _make_msg(body="<div>Hello <b>world</b></div>", body_type="html")
        text = _get_body_text(msg)
        assert "Hello" in text
        assert "world" in text
        assert "<div>" not in text

    def test_fallback_to_preview(self):
        msg = _make_msg(body="", body_type="text")
        msg["bodyPreview"] = "preview text"
        assert _get_body_text(msg) == "preview text"

    def test_sender_address(self):
        msg = _make_msg(from_addr="test@example.com")
        assert _get_sender_address(msg) == "test@example.com"


# ============================================================
# INTENT DETECTION — REGEX PATTERNS
# ============================================================

class TestAdminInstructionDetection:
    def test_from_now_on_english(self):
        result = detect_email_intent("", "from now on add shipper name in subject", ADMIN_EMAIL, privilege="ADMIN")
        assert result["intent"] == "ADMIN_INSTRUCTION"
        assert result["confidence"] >= 0.9

    def test_from_now_on_hebrew(self):
        result = detect_email_intent("", "מעכשיו הוסף את שם היצואן בכותרת", ADMIN_EMAIL, privilege="ADMIN")
        assert result["intent"] == "ADMIN_INSTRUCTION"

    def test_change_template(self):
        result = detect_email_intent("", "update the email template to include BL number", ADMIN_EMAIL, privilege="ADMIN")
        assert result["intent"] == "ADMIN_INSTRUCTION"

    def test_always_include(self):
        result = detect_email_intent("", "always add container number in the subject", ADMIN_EMAIL, privilege="ADMIN")
        assert result["intent"] == "ADMIN_INSTRUCTION"

    def test_not_detected_for_team(self):
        """ADMIN_INSTRUCTION should NOT match when privilege is TEAM."""
        result = detect_email_intent("", "from now on add shipper name", "amit@rpa-port.co.il", privilege="TEAM")
        assert result["intent"] != "ADMIN_INSTRUCTION"


class TestNonWorkDetection:
    def test_weather_english(self):
        result = detect_email_intent("", "what's the weather forecast for today?", "amit@rpa-port.co.il")
        assert result["intent"] == "NON_WORK"

    def test_weather_hebrew(self):
        result = detect_email_intent("", "מה מזג אוויר מחר?", "amit@rpa-port.co.il")
        assert result["intent"] == "NON_WORK"

    def test_joke(self):
        result = detect_email_intent("", "tell me a joke", "amit@rpa-port.co.il")
        assert result["intent"] == "NON_WORK"

    def test_sports(self):
        result = detect_email_intent("", "what's the football score?", "amit@rpa-port.co.il")
        assert result["intent"] == "NON_WORK"

    def test_recipe_hebrew(self):
        result = detect_email_intent("", "יש לך מתכון טוב?", "amit@rpa-port.co.il")
        assert result["intent"] == "NON_WORK"


class TestStatusRequestDetection:
    def test_status_with_bl(self):
        result = detect_email_intent("", "what's the status of BL MEDURS12345?", "amit@rpa-port.co.il")
        assert result["intent"] == "STATUS_REQUEST"
        assert result["entities"].get("bol_msc") == "MEDURS12345"

    def test_status_hebrew(self):
        result = detect_email_intent("", "מה המצב של BL MEDURS99999?", "amit@rpa-port.co.il")
        assert result["intent"] == "STATUS_REQUEST"

    def test_container_tracking(self):
        result = detect_email_intent("", "track container MSCU1234567", "amit@rpa-port.co.il")
        assert result["intent"] == "STATUS_REQUEST"
        assert result["entities"].get("container") == "MSCU1234567"

    def test_where_is_shipment(self):
        result = detect_email_intent("", "where is shipment BL ZIMU12345678?", "amit@rpa-port.co.il")
        assert result["intent"] == "STATUS_REQUEST"

    def test_update_hebrew(self):
        result = detect_email_intent("", "עדכון על TEMU7654321 בבקשה", "amit@rpa-port.co.il")
        assert result["intent"] == "STATUS_REQUEST"
        assert result["entities"].get("container") == "TEMU7654321"


class TestCustomsQuestionDetection:
    def test_hs_code_english(self):
        result = detect_email_intent("", "what is the HS code for rubber gloves?", "amit@rpa-port.co.il")
        assert result["intent"] == "CUSTOMS_QUESTION"

    def test_tariff_rate(self):
        result = detect_email_intent("", "what's the duty rate for electronics?", "amit@rpa-port.co.il")
        assert result["intent"] == "CUSTOMS_QUESTION"

    def test_hebrew_classification(self):
        result = detect_email_intent("", "מה הסיווג של כפפות גומי?", "amit@rpa-port.co.il")
        assert result["intent"] == "CUSTOMS_QUESTION"

    def test_hs_code_in_text(self):
        result = detect_email_intent("", "tell me about 8516.31 and its requirements", "amit@rpa-port.co.il")
        assert result["intent"] == "CUSTOMS_QUESTION"
        assert result["entities"].get("hs_code") == "8516.31"

    def test_how_much_duty(self):
        result = detect_email_intent("", "כמה מכס על טלוויזיות?", "amit@rpa-port.co.il")
        assert result["intent"] == "CUSTOMS_QUESTION"


class TestInstructionDetection:
    def test_classify_hebrew(self):
        result = detect_email_intent("", "סווג את המסמכים המצורפים", "amit@rpa-port.co.il")
        assert result["intent"] == "INSTRUCTION"
        assert result["entities"].get("action") == "classify"

    def test_classify_hebrew_lesaveg(self):
        result = detect_email_intent("", "צריך לסווג את המסמכים האלה", "amit@rpa-port.co.il")
        assert result["intent"] == "INSTRUCTION"
        assert result["entities"].get("action") == "classify"

    def test_classify_english(self):
        result = detect_email_intent("", "classify the attached documents", "amit@rpa-port.co.il")
        assert result["intent"] == "INSTRUCTION"

    def test_add_container(self):
        result = detect_email_intent("", "add container MSCU1234567 to tracking", "amit@rpa-port.co.il")
        assert result["intent"] == "INSTRUCTION"
        assert result["entities"].get("action") == "tracker_update"

    def test_stop_following(self):
        result = detect_email_intent("", "הפסק מעקב על המשלוח", "amit@rpa-port.co.il")
        assert result["intent"] == "INSTRUCTION"
        assert result["entities"].get("action") == "stop_tracking"


class TestKnowledgeQueryDetection:
    def test_question_with_domain(self):
        result = detect_email_intent("", "מה הנוהל ליבוא אישי של רכב?", "amit@rpa-port.co.il")
        assert result["intent"] == "KNOWLEDGE_QUERY"

    def test_english_question(self):
        result = detect_email_intent("", "what is the procedure for customs clearance of electronics?", "amit@rpa-port.co.il")
        assert result["intent"] == "KNOWLEDGE_QUERY"

    def test_short_generic_question(self):
        """Short question without domain context → no intent (too ambiguous)."""
        result = detect_email_intent("", "?מה", "amit@rpa-port.co.il")
        assert result["intent"] == "NONE"


class TestNoIntentDetection:
    def test_generic_text(self):
        result = detect_email_intent("", "hello this is a regular email about nothing", "amit@rpa-port.co.il")
        assert result["intent"] == "NONE"

    def test_empty_body(self):
        result = detect_email_intent("", "", "amit@rpa-port.co.il")
        assert result["intent"] == "NONE"


# ============================================================
# ENTITY EXTRACTION TESTS
# ============================================================

class TestEntityExtraction:
    def test_bol_extraction(self):
        entities = _extract_status_entities("check BL ZIMU12345678 status")
        assert entities.get("bol") == "ZIMU12345678"

    def test_msc_bol(self):
        entities = _extract_status_entities("MEDURS12345 status please")
        assert entities.get("bol_msc") == "MEDURS12345"

    def test_container(self):
        entities = _extract_status_entities("container MSCU1234567")
        assert entities.get("container") == "MSCU1234567"

    def test_hs_code_extraction(self):
        entities = _extract_customs_entities("what about 8516.31?")
        assert entities.get("hs_code") == "8516.31"

    def test_product_desc_extraction(self):
        entities = _extract_customs_entities("what is the tariff for rubber gloves?")
        assert entities.get("product_description") is not None


# ============================================================
# INSTRUCTION CLASSIFICATION
# ============================================================

class TestInstructionClassification:
    def test_classify(self):
        assert _classify_instruction("please classify this") == "classify"

    def test_hebrew_classify(self):
        assert _classify_instruction("סווג את זה") == "classify"

    def test_add_container(self):
        assert _classify_instruction("add container ABCD1234567") == "tracker_update"

    def test_stop_tracking(self):
        assert _classify_instruction("stop following this shipment") == "stop_tracking"

    def test_start_tracking(self):
        assert _classify_instruction("start tracking BL 12345") == "start_tracking"


class TestInstructionScope:
    def test_subject_scope(self):
        assert _detect_instruction_scope("change the subject line") == "tracker_email_subject"

    def test_template_scope(self):
        assert _detect_instruction_scope("update the template format") == "reply_format"

    def test_classification_scope(self):
        assert _detect_instruction_scope("change classification email") == "classification_email"

    def test_general_scope(self):
        assert _detect_instruction_scope("change something") == "general"


# ============================================================
# PRIVILEGE ENFORCEMENT
# ============================================================

class TestPrivilegeEnforcement:
    def test_external_sender_skipped(self):
        db = _mock_db_no_cache()
        msg = _make_msg(from_addr="external@gmail.com", body="what is the status of BL MEDURS12345?")
        result = process_email_intent(msg, db, Mock(), "token", "rcb@rpa-port.co.il", lambda x: None)
        assert result["status"] == "skipped"
        assert result["reason"] == "external_sender"

    def test_admin_instruction_blocked_for_team(self):
        db = _mock_db_no_cache()
        msg = _make_msg(from_addr="amit@rpa-port.co.il", body="from now on always add shipper name in subject line please")
        result = process_email_intent(msg, db, Mock(), "token", "rcb@rpa-port.co.il", lambda x: None)
        # Should not be ADMIN_INSTRUCTION for team member
        assert result.get("intent") != "ADMIN_INSTRUCTION" or result.get("status") == "skipped"

    def test_body_too_short_skipped(self):
        db = _mock_db_no_cache()
        msg = _make_msg(body="hi")
        result = process_email_intent(msg, db, Mock(), "token", "rcb@rpa-port.co.il", lambda x: None)
        assert result["status"] == "skipped"
        assert result["reason"] == "body_too_short"


# ============================================================
# SEND REPLY SAFE
# ============================================================

class TestSendReplySafe:
    @patch("lib.rcb_helpers.helper_graph_reply", return_value=True)
    @patch("lib.rcb_helpers.helper_graph_send", return_value=True)
    def test_team_sender_allowed(self, mock_send, mock_reply):
        msg = _make_msg(from_addr="amit@rpa-port.co.il")
        result = _send_reply_safe("<p>test</p>", msg, "token", "rcb@rpa-port.co.il")
        assert result is True

    def test_external_sender_blocked(self):
        msg = _make_msg(from_addr="external@gmail.com")
        result = _send_reply_safe("<p>test</p>", msg, "token", "rcb@rpa-port.co.il")
        assert result is False


# ============================================================
# CACHE LOGIC
# ============================================================

class TestCacheLogic:
    def test_cache_miss(self):
        db = Mock()
        mock_doc = Mock()
        mock_doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = mock_doc
        assert _check_cache(db, "subject", "body") is None

    def test_cache_hit_fresh(self):
        db = Mock()
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "answer_html": "<p>cached answer</p>",
            "intent": "STATUS_REQUEST",
            "created_at": datetime.now(timezone.utc),  # fresh
        }
        db.collection.return_value.document.return_value.get.return_value = mock_doc
        result = _check_cache(db, "subject", "body")
        assert result is not None
        assert result["answer_html"] == "<p>cached answer</p>"

    def test_cache_hit_expired(self):
        db = Mock()
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "answer_html": "<p>old answer</p>",
            "intent": "STATUS_REQUEST",
            "created_at": datetime.now(timezone.utc) - timedelta(hours=25),  # expired
        }
        db.collection.return_value.document.return_value.get.return_value = mock_doc
        result = _check_cache(db, "subject", "body")
        assert result is None


# ============================================================
# RATE LIMITING
# ============================================================

class TestRateLimiting:
    def test_not_rate_limited(self):
        db = Mock()
        db.collection.return_value.where.return_value.where.return_value.limit.return_value.stream.return_value = []
        assert _is_rate_limited(db, "amit@rpa-port.co.il") is False

    def test_rate_limited(self):
        db = Mock()
        mock_doc = Mock()
        db.collection.return_value.where.return_value.where.return_value.limit.return_value.stream.return_value = [mock_doc]
        assert _is_rate_limited(db, "amit@rpa-port.co.il") is True


# ============================================================
# QUESTION HASH
# ============================================================

class TestQuestionHash:
    def test_deterministic(self):
        h1 = _question_hash("subject", "body text")
        h2 = _question_hash("subject", "body text")
        assert h1 == h2

    def test_case_insensitive(self):
        h1 = _question_hash("Subject", "Body Text")
        h2 = _question_hash("subject", "body text")
        assert h1 == h2

    def test_whitespace_normalized(self):
        h1 = _question_hash("subject", "body  text")
        h2 = _question_hash("subject", "body text")
        assert h1 == h2

    def test_different_questions(self):
        h1 = _question_hash("a", "b")
        h2 = _question_hash("c", "d")
        assert h1 != h2


# ============================================================
# HTML WRAPPING
# ============================================================

class TestHtmlWrapping:
    def test_rtl_direction(self):
        html = _wrap_html_rtl("test")
        assert 'dir="rtl"' in html

    def test_signature_present(self):
        html = _wrap_html_rtl("test")
        assert "RCB" in html

    def test_newlines_converted(self):
        html = _wrap_html_rtl("line1\nline2")
        assert "<br>" in html


# ============================================================
# CLARIFICATION LOGIC TESTS
# ============================================================

def _mock_db_for_clarification(has_pending=False, pending_data=None):
    """Mock DB for clarification tests — supports both cache miss and pending doc reads."""
    db = Mock()

    # Track document key to return different results for pending vs cache
    doc_mock_cache = Mock()
    doc_mock_cache.exists = False

    doc_mock_pending = Mock()
    if has_pending and pending_data:
        doc_mock_pending.exists = True
        doc_mock_pending.to_dict.return_value = pending_data
    else:
        doc_mock_pending.exists = False

    def _document_side_effect(key):
        doc_ref = Mock()
        if key.startswith("pending_"):
            doc_ref.get.return_value = doc_mock_pending
        else:
            doc_ref.get.return_value = doc_mock_cache
        doc_ref.set.return_value = None
        doc_ref.update.return_value = None
        return doc_ref

    db.collection.return_value.document.side_effect = _document_side_effect
    # Rate limit query returns empty
    db.collection.return_value.where.return_value.where.return_value.limit.return_value.stream.return_value = []
    return db


class TestClarificationStatusNoEntity:
    """STATUS_REQUEST with no BL/container → clarification_sent"""

    @patch("lib.email_intent._send_reply_safe", return_value=True)
    def test_status_request_no_entity_sends_clarification(self, mock_reply):
        db = _mock_db_for_clarification()
        firestore_module = Mock()
        firestore_module.SERVER_TIMESTAMP = "mock_ts"
        msg = _make_msg(from_addr="amit@rpa-port.co.il",
                        body="מה המצב של המשלוח שלנו? צריך לדעת בדחיפות")
        result = process_email_intent(msg, db, firestore_module, "token",
                                      "rcb@rpa-port.co.il", lambda x: None)
        assert result["status"] == "clarification_sent"
        assert result["clarification_type"] == "missing_shipment_id"


class TestClarificationStopNoTarget:
    """'stop tracking' with no BL/container → clarification_sent"""

    @patch("lib.email_intent._send_reply_safe", return_value=True)
    def test_stop_tracking_no_target_sends_clarification(self, mock_reply):
        db = _mock_db_for_clarification()
        firestore_module = Mock()
        firestore_module.SERVER_TIMESTAMP = "mock_ts"
        msg = _make_msg(from_addr="amit@rpa-port.co.il",
                        body="הפסק מעקב על המשלוח בבקשה")
        result = process_email_intent(msg, db, firestore_module, "token",
                                      "rcb@rpa-port.co.il", lambda x: None)
        assert result["status"] == "clarification_sent"
        assert result["clarification_type"] == "missing_stop_target"


class TestClarificationClassifyNoAttachment:
    """classify with hasAttachments=False → clarification_sent"""

    @patch("lib.email_intent._send_reply_safe", return_value=True)
    def test_classify_no_attachment_sends_clarification(self, mock_reply):
        db = _mock_db_for_clarification()
        firestore_module = Mock()
        firestore_module.SERVER_TIMESTAMP = "mock_ts"
        msg = _make_msg(from_addr="amit@rpa-port.co.il",
                        body="סווג את המסמכים המצורפים בבקשה",
                        has_attachments=False)
        result = process_email_intent(msg, db, firestore_module, "token",
                                      "rcb@rpa-port.co.il", lambda x: None)
        assert result["status"] == "clarification_sent"
        assert result["clarification_type"] == "missing_attachment"


class TestClarificationAmbiguous:
    """Gibberish body >= 30 chars → clarification_sent"""

    @patch("lib.email_intent._send_reply_safe", return_value=True)
    def test_ambiguous_long_body_sends_clarification(self, mock_reply):
        db = _mock_db_for_clarification()
        firestore_module = Mock()
        firestore_module.SERVER_TIMESTAMP = "mock_ts"
        msg = _make_msg(from_addr="amit@rpa-port.co.il",
                        body="שלום רב אני רוצה לבדוק משהו לגבי הנושא הזה שדיברנו עליו אתמול")
        result = process_email_intent(msg, db, firestore_module, "token",
                                      "rcb@rpa-port.co.il", lambda x: None)
        assert result["status"] == "clarification_sent"
        assert result["clarification_type"] == "ambiguous_intent"


class TestResolveClarification:
    """Pending exists + new email has BL → executes original intent"""

    @patch("lib.email_intent._send_reply_safe", return_value=True)
    @patch("lib.email_intent._handle_status_request")
    def test_resolve_pending_with_bl(self, mock_status_handler, mock_reply):
        pending_data = {
            "awaiting_clarification": True,
            "original_intent": "STATUS_REQUEST",
            "original_entities": {},
            "clarification_type": "missing_shipment_id",
            "from_email": "amit@rpa-port.co.il",
            "created_at": datetime.now(timezone.utc),
            "msg_id": "orig_msg",
        }
        db = _mock_db_for_clarification(has_pending=True, pending_data=pending_data)
        firestore_module = Mock()
        firestore_module.SERVER_TIMESTAMP = "mock_ts"
        # Mock the status handler to return a resolved result
        mock_status_handler.return_value = {
            "status": "replied",
            "intent": "STATUS_REQUEST",
            "cost_usd": 0.0,
            "answer_text": "status info",
        }
        msg = _make_msg(from_addr="amit@rpa-port.co.il",
                        body="MEDURS12345")
        result = process_email_intent(msg, db, firestore_module, "token",
                                      "rcb@rpa-port.co.il", lambda x: None)
        assert result["status"] == "replied"
        assert result.get("resolved_from_clarification") is True


class TestClarificationExpires:
    """Pending > 4h → treated as normal email (no resolution)"""

    @patch("lib.email_intent._send_reply_safe", return_value=True)
    def test_expired_pending_ignored(self, mock_reply):
        old_time = datetime.now(timezone.utc) - timedelta(hours=5)
        pending_data = {
            "awaiting_clarification": True,
            "original_intent": "STATUS_REQUEST",
            "original_entities": {},
            "clarification_type": "missing_shipment_id",
            "from_email": "amit@rpa-port.co.il",
            "created_at": old_time,
            "msg_id": "orig_msg",
        }
        db = _mock_db_for_clarification(has_pending=True, pending_data=pending_data)
        firestore_module = Mock()
        firestore_module.SERVER_TIMESTAMP = "mock_ts"
        # Short body with no intent → should be no_intent (expired pending is ignored)
        msg = _make_msg(from_addr="amit@rpa-port.co.il",
                        body="just checking in on things")
        result = process_email_intent(msg, db, firestore_module, "token",
                                      "rcb@rpa-port.co.il", lambda x: None)
        # Expired pending → not resolved, falls through to normal detection
        assert result["status"] != "clarification_sent" or result.get("clarification_type") != "missing_shipment_id"


class TestNoClarificationShortBody:
    """NONE intent with < 30 char body → no_intent (no clarification)"""

    def test_short_body_no_clarification(self):
        db = _mock_db_for_clarification()
        firestore_module = Mock()
        firestore_module.SERVER_TIMESTAMP = "mock_ts"
        msg = _make_msg(from_addr="amit@rpa-port.co.il",
                        body="hello this is short")
        result = process_email_intent(msg, db, firestore_module, "token",
                                      "rcb@rpa-port.co.il", lambda x: None)
        assert result["status"] == "no_intent"
