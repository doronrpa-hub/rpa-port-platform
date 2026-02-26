"""
Tests for Session 74: Three-Layer Email Triage + Casual Handler
===============================================================
"""

import pytest
import re
from unittest.mock import patch, MagicMock

# ═══════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════

RCB_EMAIL = "rcb@rpa-port.co.il"


def _make_msg(subject="", body="", from_email="doron@rpa-port.co.il",
              headers=None, conversation_id=None, has_attachments=False,
              msg_id="test-msg-123"):
    """Build a minimal Graph API message object for testing."""
    msg = {
        "id": msg_id,
        "subject": subject,
        "from": {"emailAddress": {"address": from_email}},
        "body": {"content": body},
        "bodyPreview": body[:200] if body else "",
        "hasAttachments": has_attachments,
        "toRecipients": [{"emailAddress": {"address": RCB_EMAIL}}],
    }
    if headers:
        msg["internetMessageHeaders"] = headers
    if conversation_id:
        msg["conversationId"] = conversation_id
    return msg


# ═══════════════════════════════════════════
#  TestLayer0AutoSkip
# ═══════════════════════════════════════════

class TestLayer0AutoSkip:
    """Layer 0: Auto-skip for non-actionable emails."""

    def test_auto_reply_subject(self):
        from lib.email_triage import triage_email
        msg = _make_msg(subject="Automatic Reply: Out of office")
        result = triage_email(msg, RCB_EMAIL)
        assert result.category == "SKIP"
        assert result.skip_reason == "auto_reply_subject"

    def test_hebrew_ooo_subject(self):
        from lib.email_triage import triage_email
        msg = _make_msg(subject="השבה אוטומטית: אני לא במשרד")
        result = triage_email(msg, RCB_EMAIL)
        assert result.category == "SKIP"
        assert result.skip_reason == "auto_reply_subject"

    def test_noreply_sender(self):
        from lib.email_triage import triage_email
        msg = _make_msg(subject="Your report", body="Here is your report data and full details.",
                        from_email="noreply@example.com")
        result = triage_email(msg, RCB_EMAIL)
        assert result.category == "SKIP"
        assert result.skip_reason == "noreply_sender"

    def test_mailer_daemon_sender(self):
        from lib.email_triage import triage_email
        msg = _make_msg(subject="Delivery failed", body="Message could not be delivered to destination.",
                        from_email="mailer-daemon@mail.example.com")
        result = triage_email(msg, RCB_EMAIL)
        assert result.category == "SKIP"
        assert result.skip_reason == "noreply_sender"

    def test_postmaster_sender(self):
        from lib.email_triage import triage_email
        msg = _make_msg(subject="Undeliverable mail", body="The following message could not be delivered.",
                        from_email="postmaster@mail.example.com")
        result = triage_email(msg, RCB_EMAIL)
        assert result.category == "SKIP"
        assert result.skip_reason == "noreply_sender"

    def test_empty_body(self):
        from lib.email_triage import triage_email
        msg = _make_msg(subject="Test", body="hi")
        result = triage_email(msg, RCB_EMAIL)
        assert result.category == "SKIP"
        assert result.skip_reason == "body_too_short"

    def test_x_auto_response_header(self):
        from lib.email_triage import triage_email
        msg = _make_msg(
            subject="Re: Meeting",
            body="This is an automatic response to your email message.",
            headers=[{"name": "X-Auto-Response-Suppress", "value": "All"}]
        )
        result = triage_email(msg, RCB_EMAIL)
        assert result.category == "SKIP"
        assert result.skip_reason == "x_auto_response_header"

    def test_auto_submitted_header(self):
        from lib.email_triage import triage_email
        msg = _make_msg(
            subject="Notification",
            body="Your account has been updated successfully with new settings.",
            headers=[{"name": "Auto-Submitted", "value": "auto-generated"}]
        )
        result = triage_email(msg, RCB_EMAIL)
        assert result.category == "SKIP"
        assert result.skip_reason == "auto_submitted_header"

    def test_auto_submitted_no_passes(self):
        """Auto-Submitted: no means it's a human email — should NOT skip."""
        from lib.email_triage import triage_email
        msg = _make_msg(
            subject="Hello there",
            body="I wanted to ask about something related to customs tariff rates.",
            headers=[{"name": "Auto-Submitted", "value": "no"}]
        )
        result = triage_email(msg, RCB_EMAIL)
        assert result.category != "SKIP"

    def test_own_email_self_loop(self):
        from lib.email_triage import triage_email
        msg = _make_msg(subject="Status update", body="This is an RCB generated status update report.",
                        from_email=RCB_EMAIL)
        result = triage_email(msg, RCB_EMAIL)
        assert result.category == "SKIP"
        assert result.skip_reason == "self_email"

    def test_normal_email_not_skipped(self):
        from lib.email_triage import triage_email
        msg = _make_msg(subject="Question about tariffs",
                        body="Hi, I need help with customs tariff classification for my shipment")
        result = triage_email(msg, RCB_EMAIL)
        assert result.category != "SKIP"

    def test_out_of_office_english(self):
        from lib.email_triage import triage_email
        msg = _make_msg(subject="Out of Office: John Smith")
        result = triage_email(msg, RCB_EMAIL)
        assert result.category == "SKIP"
        assert result.skip_reason == "auto_reply_subject"

    def test_autoreply_no_dash(self):
        from lib.email_triage import triage_email
        msg = _make_msg(subject="autoreply: Meeting")
        result = triage_email(msg, RCB_EMAIL)
        assert result.category == "SKIP"
        assert result.skip_reason == "auto_reply_subject"


# ═══════════════════════════════════════════
#  TestRegexPreClassify
# ═══════════════════════════════════════════

class TestRegexPreClassify:
    """Layer 1b: Regex pattern matching."""

    def test_container_number_shipment(self):
        from lib.email_triage import _regex_pre_classify
        result = _regex_pre_classify("Container tracking", "Please track MSCU1234567 container status")
        assert result is not None
        assert result.category == "LIVE_SHIPMENT"

    def test_hs_code_consultation(self):
        from lib.email_triage import _regex_pre_classify
        result = _regex_pre_classify("HS Code query", "What is the tariff rate for 8419.81.10 customs code?")
        assert result is not None
        assert result.category == "CONSULTATION"

    def test_hebrew_greeting_casual(self):
        from lib.email_triage import _regex_pre_classify
        result = _regex_pre_classify("", "שלום מה שלומך היי בוקר טוב")
        assert result is not None
        assert result.category == "CASUAL"

    def test_english_greeting_casual(self):
        from lib.email_triage import _regex_pre_classify
        result = _regex_pre_classify("Hello", "Hi there, hey how are you, good morning, thanks for everything")
        assert result is not None
        assert result.category == "CASUAL"

    def test_hebrew_customs_question(self):
        from lib.email_triage import _regex_pre_classify
        result = _regex_pre_classify("שאלה", "מה התעריף מכס על סיווג טובין לפי צו יבוא?")
        assert result is not None
        assert result.category == "CONSULTATION"

    def test_bl_tracking_shipment(self):
        from lib.email_triage import _regex_pre_classify
        result = _regex_pre_classify("BL tracking", "Please check the status of our bill of lading and container")
        assert result is not None
        assert result.category == "LIVE_SHIPMENT"

    def test_empty_text_no_match(self):
        from lib.email_triage import _regex_pre_classify
        result = _regex_pre_classify("", "")
        assert result is None

    def test_joke_casual(self):
        from lib.email_triage import _regex_pre_classify
        # Need 3+ pattern matches out of 9 (>= 0.3): שלום + בדיחה + תודה
        result = _regex_pre_classify("", "שלום תודה רבה, תספר לי בדיחה")
        assert result is not None
        assert result.category == "CASUAL"

    def test_weather_casual(self):
        from lib.email_triage import _regex_pre_classify
        # Need 3+ pattern matches: שלום + מזג אוויר + בוקר טוב
        result = _regex_pre_classify("", "שלום בוקר טוב מה מזג אוויר היום")
        assert result is not None
        assert result.category == "CASUAL"

    def test_mixed_signals_highest_wins(self):
        """When container + HS code both match, scoring determines winner."""
        from lib.email_triage import _regex_pre_classify
        # Only shipment signals — container + status + vessel + BL
        result = _regex_pre_classify("BL tracking",
                                     "Track container MSCU1234567 status on vessel for bill of lading")
        assert result is not None
        assert result.category == "LIVE_SHIPMENT"

    def test_tariff_hebrew(self):
        from lib.email_triage import _regex_pre_classify
        result = _regex_pre_classify("", "מה התעריף מכס על סיווג לפי צו יבוא ופקודת המכס ותקנות?")
        assert result is not None
        assert result.category == "CONSULTATION"


# ═══════════════════════════════════════════
#  TestReplyThread
# ═══════════════════════════════════════════

class TestReplyThread:
    """Layer 1a: Reply thread detection."""

    def test_re_with_conversation_id(self):
        from lib.email_triage import _check_reply_thread
        msg = _make_msg(subject="Re: Question about tariffs",
                        body="Thanks for the answer",
                        conversation_id="conv-abc-123")
        result = _check_reply_thread(msg)
        assert result is not None
        assert result.category == "REPLY_THREAD"
        assert result.conversation_id == "conv-abc-123"

    def test_fwd_with_conversation_id(self):
        from lib.email_triage import _check_reply_thread
        msg = _make_msg(subject="Fwd: Important notice",
                        body="See below",
                        conversation_id="conv-xyz-789")
        result = _check_reply_thread(msg)
        assert result is not None
        assert result.category == "REPLY_THREAD"

    def test_hebrew_reply(self):
        from lib.email_triage import _check_reply_thread
        msg = _make_msg(subject="השב: שאלה על מכס",
                        body="תודה על התשובה",
                        conversation_id="conv-hebrew-1")
        result = _check_reply_thread(msg)
        assert result is not None
        assert result.category == "REPLY_THREAD"

    def test_no_conversation_id(self):
        from lib.email_triage import _check_reply_thread
        msg = _make_msg(subject="Re: Question", body="Reply text")
        result = _check_reply_thread(msg)
        assert result is None  # No conversationId → not a thread

    def test_no_re_prefix(self):
        from lib.email_triage import _check_reply_thread
        msg = _make_msg(subject="New question", body="Some text", conversation_id="conv-1")
        result = _check_reply_thread(msg)
        assert result is None  # No Re:/Fwd: prefix


# ═══════════════════════════════════════════
#  TestTriageIntegration
# ═══════════════════════════════════════════

class TestTriageIntegration:
    """Full triage_email flow."""

    def test_layer0_skip_short_circuits(self):
        """Layer 0 skip should NOT call Gemini."""
        from lib.email_triage import triage_email
        msg = _make_msg(subject="Out of Office: John",
                        from_email="john@example.com")
        # Even without get_secret_func, layer0 should handle it
        result = triage_email(msg, RCB_EMAIL)
        assert result.category == "SKIP"
        assert result.source == "layer0"

    def test_regex_match_short_circuits(self):
        """Regex match should NOT call Gemini."""
        from lib.email_triage import triage_email
        msg = _make_msg(
            subject="Container tracking",
            body="Please track MSCU1234567 container status on vessel for bill of lading"
        )
        result = triage_email(msg, RCB_EMAIL)
        assert result.category == "LIVE_SHIPMENT"
        assert result.source == "regex"

    def test_fallback_to_consultation(self):
        """When nothing matches, default to CONSULTATION."""
        from lib.email_triage import triage_email
        msg = _make_msg(
            subject="Something",
            body="I need to discuss a matter related to importing goods into the country"
        )
        # No get_secret_func → Gemini can't run → fallback
        result = triage_email(msg, RCB_EMAIL, get_secret_func=None)
        assert result.category == "CONSULTATION"
        assert result.source == "fallback"

    @patch('lib.email_triage._gemini_classify')
    def test_gemini_called_when_regex_fails(self, mock_gemini):
        """When regex is inconclusive, Gemini should be called."""
        from lib.email_triage import triage_email, TriageResult
        mock_gemini.return_value = TriageResult("CASUAL", 0.85, "gemini")
        msg = _make_msg(
            subject="Hi",
            body="Just wanted to say thanks for everything you do, great work"
        )
        mock_secret = MagicMock(return_value="fake-key")
        result = triage_email(msg, RCB_EMAIL, get_secret_func=mock_secret)
        # Gemini should have been called since regex won't trigger
        assert mock_gemini.called
        assert result.category == "CASUAL"

    def test_reply_thread_detected(self):
        from lib.email_triage import triage_email
        msg = _make_msg(subject="Re: Question",
                        body="Thanks for the answer, let me check on that information",
                        conversation_id="conv-123")
        result = triage_email(msg, RCB_EMAIL)
        assert result.category == "REPLY_THREAD"


# ═══════════════════════════════════════════
#  TestCasualHandler
# ═══════════════════════════════════════════

class TestCasualHandler:
    """Casual email handler tests."""

    @patch('lib.email_intent._send_reply_safe')
    @patch('lib.classification_agents.call_gemini')
    def test_gemini_success_reply(self, mock_gemini, mock_send):
        """When Gemini succeeds, send AI-generated reply."""
        mock_gemini.return_value = "שלום! מה קורה? RCB"
        mock_send.return_value = True

        from lib.casual_handler import handle_casual
        msg = _make_msg(subject="היי", body="שלום מה שלומך")
        mock_secret = MagicMock(return_value="fake-key")
        result = handle_casual(msg, "token", RCB_EMAIL, mock_secret)

        assert result["status"] == "replied"
        assert result["handler"] == "casual"
        assert "tracking_code" in result
        assert result["tracking_code"].startswith("RCB-C-")

    @patch('lib.email_intent._send_reply_safe')
    @patch('lib.classification_agents.call_gemini')
    def test_gemini_failure_canned_reply(self, mock_gemini, mock_send):
        """When Gemini fails, send canned reply."""
        mock_gemini.return_value = None
        mock_send.return_value = True

        from lib.casual_handler import handle_casual
        msg = _make_msg(subject="Hello", body="Hey there how are you doing today friend")
        mock_secret = MagicMock(return_value="fake-key")
        result = handle_casual(msg, "token", RCB_EMAIL, mock_secret)

        assert result["status"] == "replied_canned"
        assert result["handler"] == "casual"

    @patch('lib.email_intent._send_reply_safe')
    @patch('lib.classification_agents.call_gemini')
    def test_subject_format(self, mock_gemini, mock_send):
        """Verify subject format: RCB | RCB-C-YYYYMMDD-XXXXX | שיחה"""
        mock_gemini.return_value = "Hello!"
        mock_send.return_value = True

        from lib.casual_handler import handle_casual
        msg = _make_msg(subject="Hi", body="Hello there how are you doing today?")
        mock_secret = MagicMock(return_value="fake-key")
        result = handle_casual(msg, "token", RCB_EMAIL, mock_secret)

        assert result["tracking_code"].startswith("RCB-C-")
        # Pattern: RCB-C-YYYYMMDD-DDDDD
        assert re.match(r'RCB-C-\d{8}-\d{5}', result["tracking_code"])

    @patch('lib.email_intent._send_reply_safe')
    @patch('lib.classification_agents.call_gemini')
    def test_rtl_wrapping_applied(self, mock_gemini, mock_send):
        """Verify RTL wrapping is applied to reply HTML."""
        mock_gemini.return_value = "Hello from RCB!"
        mock_send.return_value = True

        from lib.casual_handler import handle_casual
        msg = _make_msg(subject="Hi", body="Hello there, just checking in with you today")
        mock_secret = MagicMock(return_value="fake-key")
        handle_casual(msg, "token", RCB_EMAIL, mock_secret)

        # Check the HTML body passed to _send_reply_safe
        call_args = mock_send.call_args
        body_html = call_args[0][0]  # First positional arg
        assert 'dir="rtl"' in body_html

    @patch('lib.email_intent._send_reply_safe')
    @patch('lib.classification_agents.call_gemini')
    def test_send_failure(self, mock_gemini, mock_send):
        """When send fails, return send_failed status."""
        mock_gemini.return_value = "Hello!"
        mock_send.return_value = False

        from lib.casual_handler import handle_casual
        msg = _make_msg(subject="Hi", body="Hello there friend how are you")
        mock_secret = MagicMock(return_value="fake-key")
        result = handle_casual(msg, "token", RCB_EMAIL, mock_secret)

        assert result["status"] == "send_failed"


# ═══════════════════════════════════════════
#  TestGeminiClassify
# ═══════════════════════════════════════════

class TestGeminiClassify:
    """Layer 1c: Gemini classification."""

    @patch('lib.classification_agents.call_gemini')
    def test_gemini_returns_valid_category(self, mock_gemini):
        from lib.email_triage import _gemini_classify
        mock_gemini.return_value = '{"category": "CASUAL", "confidence": 0.9}'
        mock_secret = MagicMock(return_value="fake-key")

        result = _gemini_classify("Hi there", "Just saying hello to everyone", mock_secret)
        assert result is not None
        assert result.category == "CASUAL"
        assert result.confidence == 0.9
        assert result.source == "gemini"

    @patch('lib.classification_agents.call_gemini')
    def test_gemini_returns_none(self, mock_gemini):
        from lib.email_triage import _gemini_classify
        mock_gemini.return_value = None
        mock_secret = MagicMock(return_value="fake-key")

        result = _gemini_classify("Subject", "Body text here", mock_secret)
        assert result is None

    def test_gemini_no_secret_func(self):
        from lib.email_triage import _gemini_classify
        result = _gemini_classify("Subject", "Body", None)
        assert result is None

    @patch('lib.classification_agents.call_gemini')
    def test_gemini_invalid_json(self, mock_gemini):
        from lib.email_triage import _gemini_classify
        mock_gemini.return_value = "This is not JSON at all"
        mock_secret = MagicMock(return_value="fake-key")

        result = _gemini_classify("Subject", "Body text", mock_secret)
        assert result is None
