"""Tests for Session 79 email rules: cc@ block, sole-recipient, Gap 2 silent classification.

Behavioral contracts:
- cc@rpa-port.co.il is NEVER a valid send target
- RCB replies ONLY when rcb@ is sole TO recipient
- _send_reply_safe() uses sole=True
- Gap 2 classifies silently (no email from CC path)
- Gap 2 report is sent from tracker poll to doron@ only
"""
import unittest
from unittest.mock import MagicMock, patch


# ── Helpers ──

def _make_msg(to_list=None, cc_list=None, from_email="doron@rpa-port.co.il",
              subject="Test", body="test body"):
    """Build a Graph API message dict for testing."""
    msg = {
        "id": "test-msg-id-123",
        "internetMessageId": "<test@rpa-port.co.il>",
        "subject": subject,
        "from": {"emailAddress": {"address": from_email, "name": "Test"}},
        "body": {"contentType": "text", "content": body},
        "bodyPreview": body[:200],
        "toRecipients": [],
        "ccRecipients": [],
    }
    for addr in (to_list or []):
        msg["toRecipients"].append({"emailAddress": {"address": addr}})
    for addr in (cc_list or []):
        msg["ccRecipients"].append({"emailAddress": {"address": addr}})
    return msg


class TestIsInternalRecipient(unittest.TestCase):
    """Step 2: cc@rpa-port.co.il is blocked."""

    def setUp(self):
        from lib.rcb_helpers import _is_internal_recipient
        self.check = _is_internal_recipient

    def test_individual_team_member_allowed(self):
        self.assertTrue(self.check("doron@rpa-port.co.il"))

    def test_rcb_address_allowed(self):
        self.assertTrue(self.check("rcb@rpa-port.co.il"))

    def test_cc_group_blocked(self):
        """cc@ is a distribution group — must never be a valid recipient."""
        self.assertFalse(self.check("cc@rpa-port.co.il"))

    def test_cc_group_case_insensitive(self):
        self.assertFalse(self.check("CC@RPA-PORT.CO.IL"))

    def test_cc_group_with_whitespace(self):
        self.assertFalse(self.check("  cc@rpa-port.co.il  "))

    def test_external_blocked(self):
        self.assertFalse(self.check("someone@gmail.com"))

    def test_empty_blocked(self):
        self.assertFalse(self.check(""))

    def test_none_blocked(self):
        self.assertFalse(self.check(None))


class TestIsDirectRecipientSole(unittest.TestCase):
    """Step 3: sole=True requires rcb@ to be the ONLY TO address."""

    def setUp(self):
        from lib.rcb_helpers import is_direct_recipient
        self.check = is_direct_recipient
        self.rcb = "rcb@rpa-port.co.il"

    def test_sole_true_single_to(self):
        """rcb@ alone in TO → sole=True returns True."""
        msg = _make_msg(to_list=["rcb@rpa-port.co.il"])
        self.assertTrue(self.check(msg, self.rcb, sole=True))

    def test_sole_true_multiple_to(self):
        """rcb@ + doron@ in TO → sole=True returns False."""
        msg = _make_msg(to_list=["rcb@rpa-port.co.il", "doron@rpa-port.co.il"])
        self.assertFalse(self.check(msg, self.rcb, sole=True))

    def test_sole_false_multiple_to(self):
        """rcb@ + doron@ in TO → sole=False returns True (old behavior)."""
        msg = _make_msg(to_list=["rcb@rpa-port.co.il", "doron@rpa-port.co.il"])
        self.assertTrue(self.check(msg, self.rcb, sole=False))

    def test_sole_true_not_in_to(self):
        """rcb@ only in CC → sole=True returns False."""
        msg = _make_msg(to_list=["doron@rpa-port.co.il"],
                        cc_list=["rcb@rpa-port.co.il"])
        self.assertFalse(self.check(msg, self.rcb, sole=True))

    def test_sole_default_is_false(self):
        """Default sole=False preserves backward compatibility."""
        msg = _make_msg(to_list=["rcb@rpa-port.co.il", "doron@rpa-port.co.il"])
        self.assertTrue(self.check(msg, self.rcb))

    def test_empty_to_failopen(self):
        """Empty toRecipients → fail-open True (both sole modes)."""
        msg = _make_msg(to_list=[])
        self.assertTrue(self.check(msg, self.rcb, sole=True))
        self.assertTrue(self.check(msg, self.rcb, sole=False))

    def test_sole_case_insensitive(self):
        msg = _make_msg(to_list=["RCB@RPA-PORT.CO.IL"])
        self.assertTrue(self.check(msg, self.rcb, sole=True))


class TestSendReplySafeSoleCheck(unittest.TestCase):
    """Step 5: _send_reply_safe() suppresses reply when rcb@ is not sole TO."""

    def test_reply_suppressed_when_multi_to(self):
        """When rcb@ + doron@ both in TO, reply must be suppressed (no send called)."""
        from lib.email_intent import _send_reply_safe

        msg = _make_msg(
            to_list=["rcb@rpa-port.co.il", "doron@rpa-port.co.il"],
            from_email="doron@rpa-port.co.il"
        )
        # Should return False before reaching any Graph API call
        result = _send_reply_safe("<p>test</p>", msg, "token", "rcb@rpa-port.co.il")
        self.assertFalse(result)

    @patch("lib.rcb_helpers.helper_graph_reply", return_value=True)
    def test_reply_allowed_when_sole_to(self, mock_reply):
        """When rcb@ is sole TO and sender is team, reply should proceed."""
        from lib.email_intent import _send_reply_safe

        msg = _make_msg(
            to_list=["rcb@rpa-port.co.il"],
            from_email="doron@rpa-port.co.il"
        )
        result = _send_reply_safe("<p>test reply</p>", msg, "token", "rcb@rpa-port.co.il")
        self.assertTrue(result)

    def test_reply_suppressed_for_external_sender(self):
        """External sender → reply suppressed even if rcb@ is sole TO."""
        from lib.email_intent import _send_reply_safe

        msg = _make_msg(
            to_list=["rcb@rpa-port.co.il"],
            from_email="client@external.com"
        )
        # External sender blocked by domain check — no Graph call reached
        result = _send_reply_safe("<p>test</p>", msg, "token", "rcb@rpa-port.co.il")
        self.assertFalse(result)


class TestGap2SilentClassification(unittest.TestCase):
    """Step 1: _run_gap2_silent_classification stores result without sending email."""

    @patch("main.run_full_classification")
    def test_silent_classify_stores_on_deal(self, mock_classify):
        """Gap 2 should call run_full_classification and update deal doc."""
        from main import _run_gap2_silent_classification

        mock_classify.return_value = {
            "success": True,
            "agents": {
                "classification": {
                    "classifications": [
                        {"hs_code": "7326.9000", "item": "Steel boxes", "confidence": "גבוהה"}
                    ]
                }
            },
            "synthesis": "Steel storage containers chapter 73",
        }

        mock_db = MagicMock()
        mock_fs = MagicMock()
        mock_fs.SERVER_TIMESTAMP = "TIMESTAMP"
        mock_get_secret = MagicMock(side_effect=lambda k: {
            "ANTHROPIC_API_KEY": "test-key",
            "GEMINI_API_KEY": "gem-key",
            "OPENAI_API_KEY": None,
        }.get(k))

        # Mock the rcb_classifications.add() return
        mock_ref = MagicMock()
        mock_ref.id = "cls-doc-123"
        mock_db.collection.return_value.add.return_value = (None, mock_ref)
        mock_db.collection.return_value.document.return_value.update.return_value = None

        result = _run_gap2_silent_classification(
            mock_db, mock_fs, "deal-abc", "Test invoice text for classification" * 5, mock_get_secret
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["classification_id"], "cls-doc-123")

        # Verify run_full_classification was called
        mock_classify.assert_called_once()

        # Verify deal was updated with classification_report_sent=False
        update_call = mock_db.collection.return_value.document.return_value.update
        update_call.assert_called()
        update_args = update_call.call_args[0][0]
        self.assertTrue(update_args["classification_auto_triggered"])
        self.assertFalse(update_args["classification_report_sent"])
        self.assertEqual(update_args["classification_auto_triggered_via"], "gap2_cc_silent")
        self.assertTrue(update_args["gap2_classification"]["success"])
        self.assertEqual(len(update_args["gap2_classification"]["hs_codes"]), 1)

    @patch("main.run_full_classification")
    def test_silent_classify_no_api_key(self, mock_classify):
        """Gap 2 should fail gracefully when no API key."""
        from main import _run_gap2_silent_classification

        mock_db = MagicMock()
        mock_fs = MagicMock()
        mock_get_secret = MagicMock(return_value=None)

        result = _run_gap2_silent_classification(
            mock_db, mock_fs, "deal-xyz", "Some text" * 20, mock_get_secret
        )

        self.assertFalse(result["success"])
        mock_classify.assert_not_called()

    @patch("main.run_full_classification")
    def test_silent_classify_stores_failure(self, mock_classify):
        """Gap 2 should store failure on deal when classification fails."""
        from main import _run_gap2_silent_classification

        mock_classify.return_value = {"success": False, "error": "agent_timeout"}

        mock_db = MagicMock()
        mock_fs = MagicMock()
        mock_fs.SERVER_TIMESTAMP = "TIMESTAMP"
        mock_get_secret = MagicMock(side_effect=lambda k: "key" if k == "ANTHROPIC_API_KEY" else None)
        mock_db.collection.return_value.document.return_value.update.return_value = None

        result = _run_gap2_silent_classification(
            mock_db, mock_fs, "deal-fail", "Some text" * 20, mock_get_secret
        )

        self.assertFalse(result["success"])
        update_call = mock_db.collection.return_value.document.return_value.update
        update_args = update_call.call_args[0][0]
        self.assertFalse(update_args["gap2_classification"]["success"])


class TestGap2ReportHtml(unittest.TestCase):
    """Step 6: _build_gap2_report_html produces valid HTML from deal data."""

    def test_builds_html_with_hs_codes(self):
        from main import _build_gap2_report_html

        deal_data = {
            "gap2_classification": {
                "success": True,
                "hs_codes": [
                    {"hs_code": "7326.9000", "description": "Steel articles", "confidence": "גבוהה"},
                    {"hs_code": "7310.1000", "description": "Steel containers", "confidence": "בינונית"},
                ],
                "synthesis": "Classified as steel articles",
            },
            "bol_number": "MEDURS12345",
            "direction": "import",
            "shipper": "ACME STEEL CO.",
        }

        html = _build_gap2_report_html("deal-123", deal_data)

        self.assertIn("7326.9000", html)
        self.assertIn("7310.1000", html)
        self.assertIn("MEDURS12345", html)
        self.assertIn("ACME STEEL CO.", html)
        self.assertIn("סיווג אוטומטי", html)
        self.assertIn("Gap 2", html)

    def test_builds_html_without_synthesis(self):
        from main import _build_gap2_report_html

        deal_data = {
            "gap2_classification": {"success": True, "hs_codes": [], "synthesis": ""},
            "bol_number": "",
            "direction": "export",
            "shipper": "",
        }

        html = _build_gap2_report_html("deal-empty", deal_data)
        self.assertIn("deal-empty", html)
        self.assertIn("export", html)
        self.assertNotIn("border-right:4px solid", html)  # No synthesis block


class TestEmailReplyMatrix(unittest.TestCase):
    """Full email rules matrix: who gets replies under what conditions.

    Matrix:
    | Scenario                         | Reply? | To whom?          |
    |----------------------------------|--------|-------------------|
    | TO: rcb@ alone, from team        | YES    | sender            |
    | TO: rcb@ alone, from external    | MAYBE  | team in CC chain  |
    | TO: rcb@ + doron@, from team     | NO     | -                 |
    | TO: doron@, CC: rcb@             | NO     | - (CC path)       |
    | TO: rcb@ alone, from cc@         | NO     | - (system addr)   |
    | Any send to cc@rpa-port.co.il    | BLOCK  | -                 |
    """

    def setUp(self):
        from lib.rcb_helpers import is_direct_recipient, _is_internal_recipient
        self.is_direct = is_direct_recipient
        self.is_internal = _is_internal_recipient

    def test_sole_to_from_team_reply_yes(self):
        msg = _make_msg(to_list=["rcb@rpa-port.co.il"], from_email="doron@rpa-port.co.il")
        self.assertTrue(self.is_direct(msg, "rcb@rpa-port.co.il", sole=True))
        self.assertTrue(self.is_internal("doron@rpa-port.co.il"))

    def test_sole_to_from_external_classify_only(self):
        msg = _make_msg(to_list=["rcb@rpa-port.co.il"], from_email="client@external.com")
        self.assertTrue(self.is_direct(msg, "rcb@rpa-port.co.il", sole=True))
        self.assertFalse(self.is_internal("client@external.com"))
        # External sender → reply goes to CC team member if found

    def test_multi_to_no_reply(self):
        msg = _make_msg(to_list=["rcb@rpa-port.co.il", "doron@rpa-port.co.il"])
        self.assertFalse(self.is_direct(msg, "rcb@rpa-port.co.il", sole=True))

    def test_cc_path_no_reply(self):
        msg = _make_msg(to_list=["doron@rpa-port.co.il"], cc_list=["rcb@rpa-port.co.il"])
        self.assertFalse(self.is_direct(msg, "rcb@rpa-port.co.il", sole=True))

    def test_from_cc_group_no_reply(self):
        """cc@ as sender is a group — never reply."""
        msg = _make_msg(to_list=["rcb@rpa-port.co.il"], from_email="cc@rpa-port.co.il")
        # Even though rcb@ is sole TO, cc@ group should not get a reply
        self.assertFalse(self.is_internal("cc@rpa-port.co.il"))

    def test_send_to_cc_group_blocked(self):
        """Attempting to send to cc@ must always be blocked."""
        self.assertFalse(self.is_internal("cc@rpa-port.co.il"))


if __name__ == "__main__":
    unittest.main()
