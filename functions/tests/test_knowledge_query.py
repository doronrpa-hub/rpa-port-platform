"""
Tests for knowledge query detection logic.
Verifies that classification-intent emails are routed to the classification
pipeline, NOT intercepted as knowledge queries.
"""

import sys
import os
import pytest

# Add functions/ to path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))


from lib.knowledge_query import (
    detect_knowledge_query,
    _has_classification_intent,
    _is_question_like,
    is_team_sender,
)


# ---------------------------------------------------------------------------
# Helpers to build fake Graph API message dicts
# ---------------------------------------------------------------------------

def _make_msg(from_email, subject, body="", attachments=None, to_email="rcb@rpa-port.co.il"):
    """Build a minimal Graph API message dict."""
    return {
        "from": {"emailAddress": {"address": from_email}},
        "toRecipients": [{"emailAddress": {"address": to_email}}],
        "subject": subject,
        "body": {"contentType": "text", "content": body},
        "bodyPreview": body[:200] if body else "",
        "attachments": attachments or [],
    }


def _make_attachment(name):
    return {"name": name, "contentType": "application/octet-stream"}


# ---------------------------------------------------------------------------
# Tests: _has_classification_intent
# ---------------------------------------------------------------------------

class TestClassificationIntent:

    def test_hebrew_classify(self):
        assert _has_classification_intent("אנא סווגו צמיגי גומי") is True

    def test_hebrew_sivug(self):
        assert _has_classification_intent("סיווג מוצרים מסין") is True

    def test_hebrew_customs_code(self):
        assert _has_classification_intent("מה קוד מכס של צמיגים?") is True

    def test_hebrew_import(self):
        assert _has_classification_intent("יבוא ציוד רפואי") is True

    def test_hebrew_export(self):
        assert _has_classification_intent("יצוא תוצרת חקלאית") is True

    def test_english_classify(self):
        assert _has_classification_intent("Please classify rubber tires") is True

    def test_english_tariff(self):
        assert _has_classification_intent("What tariff applies to steel?") is True

    def test_english_customs(self):
        assert _has_classification_intent("customs duty for electronics") is True

    def test_english_hs(self):
        assert _has_classification_intent("need HS code for this product") is True

    def test_no_intent_general_question(self):
        assert _has_classification_intent("מה שעות הפעילות של המשרד?") is False

    def test_no_intent_meeting(self):
        assert _has_classification_intent("Can we schedule a meeting tomorrow?") is False

    def test_no_intent_empty(self):
        assert _has_classification_intent("") is False


# ---------------------------------------------------------------------------
# Tests: detect_knowledge_query — classification intent overrides KQ
# ---------------------------------------------------------------------------

class TestDetectKnowledgeQuery:

    def test_classification_email_no_attachment_not_kq(self):
        """Core fix: 'סיווג' email without attachments → classify, NOT KQ."""
        msg = _make_msg(
            "doron@rpa-port.co.il",
            "סיווג - צמיגי גומי מסין",
            "שלום, אנא סווגו: צמיגי גומי פנאומטיים חדשים",
        )
        assert detect_knowledge_query(msg) is False

    def test_import_consultation_no_attachment_not_kq(self):
        """Customer asking about import — should classify."""
        msg = _make_msg(
            "doron@rpa-port.co.il",
            "יבוא ציוד רפואי מגרמניה",
            "אנחנו מתכננים לייבא ציוד רפואי, מה המכס?",
        )
        assert detect_knowledge_query(msg) is False

    def test_hs_code_in_subject_not_kq(self):
        """HS code in subject → always classify."""
        msg = _make_msg(
            "doron@rpa-port.co.il",
            "שאלה על פרט 4011.10",
            "מה שיעור המכס?",
        )
        assert detect_knowledge_query(msg) is False

    def test_commercial_attachment_not_kq(self):
        """Invoice attachment → classify."""
        msg = _make_msg(
            "doron@rpa-port.co.il",
            "שלום, מצורפת חשבונית",
            "בדקו בבקשה",
            attachments=[_make_attachment("invoice_12345.pdf")],
        )
        assert detect_knowledge_query(msg) is False

    def test_external_sender_never_kq(self):
        """External senders never get KQ treatment."""
        msg = _make_msg(
            "customer@example.com",
            "שאלה כללית על המשרד",
            "מה שעות הפעילות?",
        )
        assert detect_knowledge_query(msg) is False

    def test_genuine_knowledge_query_is_kq(self):
        """Team member asking a general question with no classification intent → KQ."""
        msg = _make_msg(
            "doron@rpa-port.co.il",
            "שאלה",
            "מה הנוהל לגבי שינויים ברגולציה?",
        )
        assert detect_knowledge_query(msg) is True

    def test_question_with_classify_keyword_not_kq(self):
        """Even if phrased as question, classification keywords override."""
        msg = _make_msg(
            "doron@rpa-port.co.il",
            "שאלה",
            "תוכל לסווג לי מוצר מסוים?",
        )
        assert detect_knowledge_query(msg) is False

    def test_english_classify_no_attachment_not_kq(self):
        """English classification request without attachment → classify."""
        msg = _make_msg(
            "doron@rpa-port.co.il",
            "Classification request",
            "Please classify rubber tires 205/55R16 from China",
        )
        assert detect_knowledge_query(msg) is False

    def test_customs_question_is_classification(self):
        """'מכס' keyword → classification intent."""
        msg = _make_msg(
            "doron@rpa-port.co.il",
            "שאלה על מכס",
            "כמה מכס על טלוויזיות?",
        )
        assert detect_knowledge_query(msg) is False

    def test_no_attachments_no_intent_question_is_kq(self):
        """No attachments, no classification intent, question-like → KQ."""
        msg = _make_msg(
            "doron@rpa-port.co.il",
            "עדכונים",
            "יש עדכונים על הנהלים החדשים?",
        )
        assert detect_knowledge_query(msg) is True

    def test_no_attachments_no_intent_no_question_not_kq(self):
        """No attachments, no classification intent, NOT a question → not KQ (goes to classify)."""
        msg = _make_msg(
            "doron@rpa-port.co.il",
            "פגישה מחר",
            "נפגש מחר בשעה 10",
        )
        assert detect_knowledge_query(msg) is False
