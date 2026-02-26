"""
Tests for consultation_handler.py — 3-Level Escalation Ladder.
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call
from dataclasses import dataclass

# Add parent dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.consultation_handler import (
    _evaluate_draft,
    _compare_drafts,
    _DELEGATE_INTENTS,
    TEAM_DOMAIN,
    _DOMAIN_LABELS,
)


# ═══════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════

def _make_context_package(**overrides):
    """Create a mock ContextPackage for testing."""
    from lib.context_engine import ContextPackage
    defaults = {
        "original_subject": "שאלה על מכס",
        "original_body": "מה הסיווג של מכונת קפה?",
        "detected_language": "he",
        "domain": "tariff",
        "entities": {"hs_codes": [], "product_names": ["מכונת קפה"], "keywords": []},
        "tariff_results": [],
        "ordinance_articles": [],
        "xml_results": [],
        "regulatory_results": [],
        "framework_articles": [],
        "cached_answer": None,
        "context_summary": "=== נתוני מערכת RCB ===\nDomain: tariff\nLanguage: he",
        "confidence": 0.3,
        "search_log": [],
    }
    defaults.update(overrides)
    return ContextPackage(**defaults)


def _make_msg(**overrides):
    """Create a mock email message."""
    base = {
        "subject": "שאלה על סיווג מכס",
        "body": {"content": "מה הסיווג של מכונת קפה?"},
        "from": {"emailAddress": {"address": "doron@rpa-port.co.il"}},
        "conversationId": "test123",
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════
#  TEST DRAFT EVALUATION
# ═══════════════════════════════════════════

class TestDraftEvaluation(unittest.TestCase):
    def test_none_draft_fails(self):
        pkg = _make_context_package()
        self.assertFalse(_evaluate_draft(None, pkg))

    def test_empty_draft_fails(self):
        pkg = _make_context_package()
        self.assertFalse(_evaluate_draft("", pkg))

    def test_short_draft_fails(self):
        pkg = _make_context_package()
        self.assertFalse(_evaluate_draft("קצר מדי", pkg))

    def test_good_draft_passes(self):
        pkg = _make_context_package()
        draft = (
            "## תשובה ישירה\nסיווג מכונת קפה הוא 8419.81.10\n\n"
            "## ציטוט מהחוק\nלפי פרט 8419.81 - מכונות להכנת משקאות חמים\n\n"
            "## הסבר\nהסבר מפורט כאן\n\n"
            "## מידע נוסף\nמידע נוסף\n\n"
            "## English Summary\nCoffee machine classification."
        )
        self.assertTrue(_evaluate_draft(draft, pkg))

    def test_draft_with_ordinance_expects_reference(self):
        """When ordinance articles found, draft must reference at least one."""
        pkg = _make_context_package(
            ordinance_articles=[{"article_id": "130", "title_he": "ערך עסקה"}]
        )
        draft = (
            "## תשובה ישירה\nלפי סעיף 130 לפקודת המכס, ערך עסקה נקבע...\n\n"
            "## ציטוט מהחוק\nסעיף 130: ערך טובין מיובאים...\n\n"
            "## הסבר\nהסבר ארוך מספיק כדי לעבור את הבדיקה של 50 תווים\n\n"
            "## מידע נוסף\nללא\n\n"
            "## English Summary\nTransaction value per article 130."
        )
        self.assertTrue(_evaluate_draft(draft, pkg))

    def test_draft_missing_ordinance_reference(self):
        """Draft fails when ordinance articles found but not referenced."""
        pkg = _make_context_package(
            ordinance_articles=[{"article_id": "130", "title_he": "ערך עסקה"}]
        )
        draft = (
            "## תשובה ישירה\nערך עסקה נקבע לפי המחיר ששולם\n\n"
            "## ציטוט מהחוק\nאין ציטוט ספציפי כאן\n\n"
            "## הסבר\nהסבר ארוך מספיק כדי לעבור את הבדיקה של 50 תווים לפחות\n\n"
            "## מידע נוסף\nללא\n\n"
            "## English Summary\nTransaction value determined by actual price."
        )
        self.assertFalse(_evaluate_draft(draft, pkg))

    def test_draft_with_tariff_expects_hs_code(self):
        """When tariff results found, draft must reference at least one."""
        pkg = _make_context_package(
            tariff_results=[{"hs_code": "8419.81.10", "description_he": "מכונות"}]
        )
        draft = (
            "## תשובה ישירה\nהפרט הנכון הוא 8419.81.10\n\n"
            "## ציטוט מהחוק\nפרט 8419.81 — מכונות\n\n"
            "## הסבר\nהסבר ארוך מספיק כדי לעבור את הבדיקה של 50 תווים לפחות\n\n"
            "## מידע נוסף\nללא\n\n"
            "## English Summary\nHS code 8419.81.10 for coffee machines."
        )
        self.assertTrue(_evaluate_draft(draft, pkg))

    def test_draft_missing_tariff_reference(self):
        """Draft fails when tariff results found but no HS code mentioned."""
        pkg = _make_context_package(
            tariff_results=[{"hs_code": "8419.81.10", "description_he": "מכונות"}]
        )
        draft = (
            "## תשובה ישירה\nמכונת קפה מסווגת בפרק מכונות\n\n"
            "## ציטוט מהחוק\nלא נמצא ציטוט ספציפי\n\n"
            "## הסבר\nהסבר ארוך מספיק כדי לעבור את הבדיקה של חמישים תווים\n\n"
            "## מידע נוסף\nללא\n\n"
            "## English Summary\nCoffee machine classified under machinery chapter."
        )
        self.assertFalse(_evaluate_draft(draft, pkg))


# ═══════════════════════════════════════════
#  TEST DRAFT COMPARISON
# ═══════════════════════════════════════════

class TestDraftComparison(unittest.TestCase):
    def test_none_chatgpt_returns_0(self):
        self.assertEqual(_compare_drafts("draft", None, _make_context_package()), 0.0)

    def test_approves_prefix(self):
        score = _compare_drafts("gemini text", "מאשר: gemini text עם שיפורים", _make_context_package())
        self.assertEqual(score, 0.9)

    def test_corrects_prefix(self):
        score = _compare_drafts("gemini text", "מתקן: completely different", _make_context_package())
        self.assertEqual(score, 0.3)

    def test_keyword_overlap(self):
        draft1 = "סעיף 130 קובע ערך עסקה 8419.81"
        draft2 = "לפי סעיף 130 ערך עסקה נקבע 8419.81"
        score = _compare_drafts(draft1, draft2, _make_context_package())
        self.assertGreater(score, 0.5)

    def test_no_overlap(self):
        draft1 = "8419.81"
        draft2 = "9504.50"
        score = _compare_drafts(draft1, draft2, _make_context_package())
        # Low overlap
        self.assertLess(score, 0.5)

    def test_empty_keys_return_half(self):
        score = _compare_drafts("hello", "world", _make_context_package())
        self.assertEqual(score, 0.5)


# ═══════════════════════════════════════════
#  TEST ESCALATION LADDER
# ═══════════════════════════════════════════

class TestEscalationLadder(unittest.TestCase):
    """Test the escalation flow logic via handle_consultation."""

    @patch('lib.consultation_handler._send_consultation_reply', return_value=True)
    @patch('lib.consultation_handler._call_level1_gemini')
    @patch('lib.consultation_handler.detect_email_intent', return_value={"intent": "CUSTOMS_QUESTION"})
    @patch('lib.consultation_handler.prepare_context_package')
    def test_level1_pass(self, mock_sif, mock_detect, mock_l1, mock_send):
        """Gemini passes quality gate → Level 1 reply, no escalation."""
        from lib.consultation_handler import handle_consultation

        pkg = _make_context_package()
        mock_sif.return_value = pkg
        mock_l1.return_value = (
            "## תשובה ישירה\nתשובה מפורטת ונכונה\n\n"
            "## ציטוט מהחוק\nציטוט\n\n"
            "## הסבר\nהסבר ארוך מספיק כדי לעבור\n\n"
            "## מידע נוסף\nללא\n\n"
            "## English Summary\nSummary."
        )

        result = handle_consultation(
            _make_msg(), MagicMock(), MagicMock(), "token", "rcb@rpa-port.co.il",
            lambda x: "key")

        self.assertEqual(result["status"], "replied")
        self.assertEqual(result["level"], 1)
        self.assertEqual(result["model"], "gemini")

    @patch('lib.consultation_handler._send_consultation_reply', return_value=True)
    @patch('lib.consultation_handler._synthesize_two', return_value="Synthesized answer")
    @patch('lib.consultation_handler._compare_drafts', return_value=0.8)
    @patch('lib.consultation_handler._call_level2_chatgpt', return_value="מאשר: good")
    @patch('lib.consultation_handler._call_level1_gemini', return_value=None)
    @patch('lib.consultation_handler.detect_email_intent', return_value={"intent": "CUSTOMS_QUESTION"})
    @patch('lib.consultation_handler.prepare_context_package')
    def test_level1_fail_level2_agree(self, mock_sif, mock_detect, mock_l1,
                                      mock_l2, mock_compare, mock_synth, mock_send):
        """Gemini fails → ChatGPT agrees → Level 2 synthesis."""
        from lib.consultation_handler import handle_consultation

        mock_sif.return_value = _make_context_package()

        result = handle_consultation(
            _make_msg(), MagicMock(), MagicMock(), "token", "rcb@rpa-port.co.il",
            lambda x: "key")

        self.assertEqual(result["status"], "replied")
        self.assertEqual(result["level"], 2)
        self.assertIn("chatgpt", result["model"])

    @patch('lib.consultation_handler._send_consultation_reply', return_value=True)
    @patch('lib.consultation_handler._call_level3_claude', return_value="Claude final answer")
    @patch('lib.consultation_handler._compare_drafts', return_value=0.3)
    @patch('lib.consultation_handler._call_level2_chatgpt', return_value="מתקן: different")
    @patch('lib.consultation_handler._call_level1_gemini', return_value=None)
    @patch('lib.consultation_handler.detect_email_intent', return_value={"intent": "CUSTOMS_QUESTION"})
    @patch('lib.consultation_handler.prepare_context_package')
    def test_level3_claude_arbiter(self, mock_sif, mock_detect, mock_l1,
                                   mock_l2, mock_compare, mock_l3, mock_send):
        """Both disagree → Claude arbitrates → Level 3."""
        from lib.consultation_handler import handle_consultation

        mock_sif.return_value = _make_context_package()

        result = handle_consultation(
            _make_msg(), MagicMock(), MagicMock(), "token", "rcb@rpa-port.co.il",
            lambda x: "key")

        self.assertEqual(result["status"], "replied")
        self.assertEqual(result["level"], 3)
        self.assertEqual(result["model"], "claude")

    @patch('lib.consultation_handler._call_level3_claude', return_value=None)
    @patch('lib.consultation_handler._compare_drafts', return_value=0.2)
    @patch('lib.consultation_handler._call_level2_chatgpt', return_value=None)
    @patch('lib.consultation_handler._call_level1_gemini', return_value=None)
    @patch('lib.consultation_handler.detect_email_intent', return_value={"intent": "CUSTOMS_QUESTION"})
    @patch('lib.consultation_handler.prepare_context_package')
    def test_all_levels_fail(self, mock_sif, mock_detect, mock_l1, mock_l2,
                              mock_compare, mock_l3):
        """All levels fail → all_levels_failed status."""
        from lib.consultation_handler import handle_consultation

        mock_sif.return_value = _make_context_package()

        result = handle_consultation(
            _make_msg(), MagicMock(), MagicMock(), "token", "rcb@rpa-port.co.il",
            lambda x: "key")

        self.assertEqual(result["status"], "all_levels_failed")


# ═══════════════════════════════════════════
#  TEST SUB-INTENT DELEGATION
# ═══════════════════════════════════════════

class TestSubIntentDelegation(unittest.TestCase):
    def test_delegate_intents_set(self):
        """Correct intents are in the delegation set."""
        self.assertIn("ADMIN_INSTRUCTION", _DELEGATE_INTENTS)
        self.assertIn("CORRECTION", _DELEGATE_INTENTS)
        self.assertIn("INSTRUCTION", _DELEGATE_INTENTS)
        self.assertIn("STATUS_REQUEST", _DELEGATE_INTENTS)
        self.assertIn("NON_WORK", _DELEGATE_INTENTS)

    def test_customs_question_not_delegated(self):
        """CUSTOMS_QUESTION should NOT be delegated."""
        self.assertNotIn("CUSTOMS_QUESTION", _DELEGATE_INTENTS)
        self.assertNotIn("KNOWLEDGE_QUERY", _DELEGATE_INTENTS)

    @patch('lib.consultation_handler.detect_email_intent',
           return_value={"intent": "ADMIN_INSTRUCTION"})
    @patch('lib.consultation_handler._delegate_to_legacy',
           return_value={"status": "delegated", "sub_intent": "ADMIN_INSTRUCTION"})
    def test_admin_delegates(self, mock_delegate, mock_detect):
        """ADMIN_INSTRUCTION sub-intent delegates to legacy."""
        from lib.consultation_handler import handle_consultation

        result = handle_consultation(
            _make_msg(), MagicMock(), MagicMock(), "token", "rcb@rpa-port.co.il",
            lambda x: "key")

        self.assertEqual(result["status"], "delegated")
        self.assertEqual(result["sub_intent"], "ADMIN_INSTRUCTION")

    @patch('lib.consultation_handler.detect_email_intent',
           return_value={"intent": "STATUS_REQUEST"})
    @patch('lib.consultation_handler._delegate_to_legacy',
           return_value={"status": "delegated", "sub_intent": "STATUS_REQUEST"})
    def test_status_delegates(self, mock_delegate, mock_detect):
        """STATUS_REQUEST sub-intent delegates to legacy."""
        from lib.consultation_handler import handle_consultation

        result = handle_consultation(
            _make_msg(), MagicMock(), MagicMock(), "token", "rcb@rpa-port.co.il",
            lambda x: "key")

        self.assertEqual(result["status"], "delegated")


# ═══════════════════════════════════════════
#  TEST PUPIL LOGGING
# ═══════════════════════════════════════════

class TestPupilLogging(unittest.TestCase):
    def test_log_structure(self):
        """Pupil log writes expected fields."""
        from lib.consultation_handler import _log_to_pupil

        mock_db = MagicMock()
        pkg = _make_context_package()
        drafts = [("gemini", "draft1"), ("chatgpt", "draft2")]

        _log_to_pupil(pkg, drafts, "gemini", mock_db)

        mock_db.collection.assert_called_with("pupil_consultation_log")
        add_call = mock_db.collection("pupil_consultation_log").add
        self.assertTrue(add_call.called)
        doc = add_call.call_args[0][0]
        self.assertEqual(doc["domain"], "tariff")
        self.assertEqual(doc["winner"], "gemini")
        self.assertEqual(len(doc["drafts"]), 2)
        self.assertEqual(doc["escalation_level"], 2)

    def test_log_captures_drafts(self):
        """Drafts are captured in the log."""
        from lib.consultation_handler import _log_to_pupil

        mock_db = MagicMock()
        pkg = _make_context_package()
        drafts = [("gemini", "גמיני דרפט"), ("chatgpt", "צ'טגפט דרפט")]

        _log_to_pupil(pkg, drafts, "synthesis_2", mock_db)

        doc = mock_db.collection("pupil_consultation_log").add.call_args[0][0]
        self.assertEqual(doc["drafts"][0]["model"], "gemini")
        self.assertEqual(doc["drafts"][1]["model"], "chatgpt")
        self.assertEqual(doc["winner"], "synthesis_2")

    def test_log_no_db(self):
        """No crash when db is None."""
        from lib.consultation_handler import _log_to_pupil

        # Should not raise
        _log_to_pupil(_make_context_package(), [], "none", None)

    def test_log_db_error_silent(self):
        """DB error in pupil log does not crash."""
        from lib.consultation_handler import _log_to_pupil

        mock_db = MagicMock()
        mock_db.collection.side_effect = Exception("Firestore down")

        # Should not raise
        _log_to_pupil(_make_context_package(), [], "none", mock_db)


# ═══════════════════════════════════════════
#  TEST CONSTANTS
# ═══════════════════════════════════════════

class TestConstants(unittest.TestCase):
    def test_team_domain(self):
        self.assertEqual(TEAM_DOMAIN, "rpa-port.co.il")

    def test_domain_labels_hebrew(self):
        self.assertIn("tariff", _DOMAIN_LABELS)
        self.assertIn("ordinance", _DOMAIN_LABELS)
        self.assertIn("fta", _DOMAIN_LABELS)
        self.assertIn("regulatory", _DOMAIN_LABELS)
        self.assertIn("general", _DOMAIN_LABELS)

    def test_delegate_intents_count(self):
        self.assertEqual(len(_DELEGATE_INTENTS), 5)


# ═══════════════════════════════════════════
#  TEST LEVEL FUNCTIONS (unit)
# ═══════════════════════════════════════════

class TestLevelFunctions(unittest.TestCase):
    def test_level1_no_secret_func(self):
        from lib.consultation_handler import _call_level1_gemini
        result = _call_level1_gemini(_make_context_package(), None)
        self.assertIsNone(result)

    def test_level1_no_key(self):
        from lib.consultation_handler import _call_level1_gemini
        result = _call_level1_gemini(_make_context_package(), lambda x: None)
        self.assertIsNone(result)

    def test_level2_no_secret_func(self):
        from lib.consultation_handler import _call_level2_chatgpt
        result = _call_level2_chatgpt(_make_context_package(), "draft", None)
        self.assertIsNone(result)

    def test_level3_returns_fallback(self):
        """Level 3 returns chatgpt draft as fallback when Claude unavailable."""
        from lib.consultation_handler import _call_level3_claude
        result = _call_level3_claude(_make_context_package(), "gemini", "chatgpt", None)
        self.assertEqual(result, "chatgpt")

    def test_level3_gemini_fallback(self):
        """Level 3 returns gemini draft if no chatgpt and no Claude."""
        from lib.consultation_handler import _call_level3_claude
        result = _call_level3_claude(_make_context_package(), "gemini", None, None)
        self.assertEqual(result, "gemini")


# ═══════════════════════════════════════════
#  TEST SYNTHESIZE
# ═══════════════════════════════════════════

class TestSynthesizeTwo(unittest.TestCase):
    def test_no_secret_func_returns_chatgpt(self):
        from lib.consultation_handler import _synthesize_two
        result = _synthesize_two("gemini", "chatgpt", _make_context_package(), None)
        self.assertEqual(result, "chatgpt")

    def test_no_key_returns_chatgpt(self):
        from lib.consultation_handler import _synthesize_two
        result = _synthesize_two("gemini", "chatgpt", _make_context_package(), lambda x: None)
        self.assertEqual(result, "chatgpt")


if __name__ == '__main__':
    unittest.main()
