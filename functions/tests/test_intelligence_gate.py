"""Tests for intelligence_gate.py — Phase 1 of RCB Intelligence Routing Spec."""
import re
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from lib.intelligence_gate import (
    validate_classification_hs_codes,
    check_classification_loop,
    record_classification_codes,
    build_escalation_email_html,
    filter_banned_phrases,
    run_all_gates,
    BANNED_PHRASES,
    _normalize,
    _format_il,
    _compute_thread_key,
    _MAX_CLASSIFICATION_ATTEMPTS,
)


# ═══════════════════════════════════════════════════════════════════════
# GATE 1: HS Code Validation
# ═══════════════════════════════════════════════════════════════════════

class TestHSValidation:
    """Test HS code validation gate."""

    def test_empty_classifications(self):
        result = validate_classification_hs_codes(None, [])
        assert result["all_valid"] is True
        assert result["items"] == []
        assert result["blocking_issues"] == []

    def test_no_db(self):
        result = validate_classification_hs_codes(None, [{"hs_code": "9401610000"}])
        assert result["all_valid"] is True

    def test_classification_with_no_code(self):
        # db=None → early return with empty items (no Firestore to check against)
        result = validate_classification_hs_codes(None, [{"item": "chair"}])
        assert result["all_valid"] is True
        assert result["items"] == []

    def test_normalize(self):
        assert _normalize("94.01.61.0000") == "9401610000"
        assert _normalize("9401 61 0000") == "9401610000"
        assert _normalize("9401/61/0000") == "9401610000"

    def test_format_il_10digit(self):
        assert _format_il("9401610000") == "94.01.610000"

    def test_format_il_short(self):
        assert _format_il("9401") == "94.01"
        assert _format_il("940161") == "94.01.61"


# ═══════════════════════════════════════════════════════════════════════
# GATE 2: Classification Loop Breaker
# ═══════════════════════════════════════════════════════════════════════

class TestLoopBreaker:
    """Test classification loop detection."""

    def test_no_db_allows(self):
        result = check_classification_loop(None, "msg123", "Test subject")
        assert result["allowed"] is True
        assert result["attempt_number"] == 1

    def test_empty_subject_and_msg(self):
        result = check_classification_loop(None, "", "")
        assert result["allowed"] is True

    def test_max_attempts_constant(self):
        assert _MAX_CLASSIFICATION_ATTEMPTS == 2

    def test_compute_thread_key_strips_re(self):
        key1 = _compute_thread_key("Re: Re: FW: Invoice BALKI", "")
        key2 = _compute_thread_key("Invoice BALKI", "")
        assert key1 == key2

    def test_compute_thread_key_strips_tracking(self):
        key1 = _compute_thread_key("RCB-20260218-003-CLS Invoice", "")
        key2 = _compute_thread_key("Invoice", "")
        assert key1 == key2

    def test_compute_thread_key_fallback_msgid(self):
        key = _compute_thread_key("", "msg_abc123")
        assert key  # Not empty
        assert len(key) == 16

    def test_compute_thread_key_empty(self):
        assert _compute_thread_key("", "") == ""

    def test_escalation_html(self):
        html = build_escalation_email_html("Test invoice", ["9401610000"], 3)
        assert "הסלמה" in html
        assert "Test invoice" in html
        assert "3" in html
        assert "94.01.610000" in html
        assert "dir=\"rtl\"" in html


# ═══════════════════════════════════════════════════════════════════════
# GATE 3: Banned Phrase Filter
# ═══════════════════════════════════════════════════════════════════════

class TestBannedPhraseFilter:
    """Test banned phrase filtering."""

    def test_clean_html_unchanged(self):
        html = "<p>Classification result: 9401.61.0000</p>"
        result = filter_banned_phrases(html)
        assert result["was_modified"] is False
        assert result["cleaned_html"] == html
        assert result["phrases_found"] == []

    def test_removes_consult_broker_hebrew(self):
        html = '<p>מומלץ לפנות לעמיל מכס לאישור.</p>'
        result = filter_banned_phrases(html)
        assert result["was_modified"] is True
        assert "מומלץ לפנות לעמיל מכס" not in result["cleaned_html"]
        assert "rcb@rpa-port.co.il" in result["cleaned_html"]

    def test_removes_consult_broker_english(self):
        html = '<p>We recommend that you consult a customs broker.</p>'
        result = filter_banned_phrases(html)
        assert result["was_modified"] is True
        assert "consult a customs broker" not in result["cleaned_html"]

    def test_removes_unclassifiable(self):
        html = '<p>The item is unclassifiable without more info.</p>'
        result = filter_banned_phrases(html)
        assert result["was_modified"] is True
        assert "unclassifiable" not in result["cleaned_html"]

    def test_removes_cannot_classify_hebrew(self):
        html = '<p>לא ניתן לסווג את המוצר.</p>'
        result = filter_banned_phrases(html)
        assert result["was_modified"] is True
        assert "לא ניתן לסווג" not in result["cleaned_html"]

    def test_removes_validate_with_broker(self):
        html = '<p>יש לאמת עם עמיל מכס מוסמך</p>'
        result = filter_banned_phrases(html)
        assert result["was_modified"] is True
        assert "יש לאמת עם עמיל מכס מוסמך" not in result["cleaned_html"]

    def test_case_insensitive(self):
        html = '<p>CONSULT A CUSTOMS BROKER for help.</p>'
        result = filter_banned_phrases(html)
        assert result["was_modified"] is True
        assert "CONSULT A CUSTOMS BROKER" not in result["cleaned_html"]

    def test_multiple_phrases(self):
        html = '<p>מומלץ להתייעץ עם עמיל מכס. I\'m not sure about this.</p>'
        result = filter_banned_phrases(html)
        assert result["was_modified"] is True
        assert len(result["phrases_found"]) >= 2

    def test_empty_html(self):
        result = filter_banned_phrases("")
        assert result["was_modified"] is False
        assert result["cleaned_html"] == ""

    def test_none_html(self):
        result = filter_banned_phrases(None)
        assert result["was_modified"] is False

    def test_banned_phrases_list(self):
        assert len(BANNED_PHRASES) >= 15
        # Hebrew broker references
        assert any("עמיל מכס" in p for p in BANNED_PHRASES)
        # English broker references
        assert any("customs broker" in p for p in BANNED_PHRASES)
        # Uncertainty phrases
        assert any("not sure" in p.lower() for p in BANNED_PHRASES)
        # Unclassifiable
        assert "unclassifiable" in BANNED_PHRASES


# ═══════════════════════════════════════════════════════════════════════
# Combined Gate
# ═══════════════════════════════════════════════════════════════════════

class TestRunAllGates:
    """Test the combined gate runner."""

    def test_passes_with_clean_html(self):
        result = run_all_gates(None, [], "<p>Clean email</p>")
        assert result["approved"] is True
        assert result["html_body"] == "<p>Clean email</p>"

    def test_cleans_banned_phrases(self):
        html = '<p>consult a customs broker</p>'
        result = run_all_gates(None, [], html)
        assert result["approved"] is True
        assert "consult a customs broker" not in result["html_body"]
        assert result["banned_filter"]["was_modified"] is True

    def test_no_db_still_works(self):
        result = run_all_gates(None, [{"hs_code": "9401610000"}], "<p>Test</p>",
                               msg_id="msg1", email_subject="Invoice")
        assert result["approved"] is True

    def test_empty_inputs(self):
        result = run_all_gates(None, [], "")
        assert result["approved"] is True


# ═══════════════════════════════════════════════════════════════════════
# Regression — ensure the spec's 3 gates are all present
# ═══════════════════════════════════════════════════════════════════════

class TestSpecCompliance:
    """Ensure all 3 Phase 1 gates from the Intelligence Routing Spec exist."""

    def test_gate1_exists(self):
        """Gate 1: HS Code Validation."""
        assert callable(validate_classification_hs_codes)

    def test_gate2_exists(self):
        """Gate 2: Classification Loop Breaker."""
        assert callable(check_classification_loop)
        assert callable(record_classification_codes)

    def test_gate3_exists(self):
        """Gate 3: Banned Phrase Filter."""
        assert callable(filter_banned_phrases)

    def test_combined_gate_exists(self):
        """Combined gate runner."""
        assert callable(run_all_gates)

    def test_escalation_email_builder(self):
        """Escalation email for loop breaker."""
        assert callable(build_escalation_email_html)
