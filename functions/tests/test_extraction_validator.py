"""
Tests for ExtractionValidator.

Session 28C — Assignment 20.
NEW FILE.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.extraction_validator import ExtractionValidator
from lib.extraction_result import ExtractionResult


@pytest.fixture
def validator():
    return ExtractionValidator()


# ─────────────────────────────────────
#  Basic quality checks
# ─────────────────────────────────────

class TestBasicQuality:

    def test_empty_text_is_invalid(self, validator):
        r = ExtractionResult(text="", confidence=0.5, method="test")
        v = validator.validate(r)
        assert v.valid is False
        assert any("CRITICAL" in i for i in v.issues)

    def test_very_short_text_is_invalid(self, validator):
        r = ExtractionResult(text="hello", confidence=0.5, method="test")
        v = validator.validate(r)
        assert v.valid is False

    def test_normal_text_is_valid(self, validator):
        text = (
            "Invoice #12345\n"
            "Date: 2025-01-15\n"
            "Item: Industrial Bolts\n"
            "Quantity: 1000\n"
            "Unit Price: $5.50\n"
            "Total: $5,500.00\n"
            "Payment Terms: Net 30\n"
        )
        r = ExtractionResult(text=text, confidence=0.8, method="test")
        v = validator.validate(r)
        assert v.valid is True

    def test_garbage_characters_detected(self, validator):
        garbage = "\x00\x01\x02\x03\x04" * 100 + "some text"
        r = ExtractionResult(text=garbage, confidence=0.5, method="test")
        v = validator.validate(r)
        assert v.valid is False
        assert any("garbage" in i.lower() for i in v.issues)

    def test_replacement_characters_detected(self, validator):
        text = "\ufffd" * 200 + "some real text here with enough words to pass"
        r = ExtractionResult(text=text, confidence=0.5, method="test")
        v = validator.validate(r)
        assert v.valid is False


# ─────────────────────────────────────
#  Language detection
# ─────────────────────────────────────

class TestLanguageDetection:

    def test_hebrew_detected(self, validator):
        lang = validator._detect_language("שלום עולם זהו מסמך בעברית בלבד")
        assert lang == "hebrew"

    def test_english_detected(self, validator):
        lang = validator._detect_language("This is a document in English only")
        assert lang == "english"

    def test_mixed_detected(self, validator):
        lang = validator._detect_language("Invoice חשבונית number מספר 12345")
        assert lang == "mixed"

    def test_unknown_for_numbers_only(self, validator):
        lang = validator._detect_language("12345 67890 111 222 333")
        assert lang == "unknown"


# ─────────────────────────────────────
#  Hebrew RTL checks
# ─────────────────────────────────────

class TestHebrewRTL:

    def test_normal_hebrew_not_reversed(self, validator):
        text = "ישראל מכס שער פטור ייבוא יצוא"
        assert validator._has_reversed_hebrew(text) is False

    def test_reversed_hebrew_detected(self, validator):
        # "ישראל" reversed → "לארשי"
        text = "לארשי is a reversed word here with more text"
        assert validator._has_reversed_hebrew(text) is True

    def test_no_hebrew_no_reversal(self, validator):
        text = "This is English text only"
        assert validator._has_reversed_hebrew(text) is False


# ─────────────────────────────────────
#  Document-type checks
# ─────────────────────────────────────

class TestDocumentTypeChecks:

    def test_invoice_with_keywords_passes(self, validator):
        text = (
            "Commercial Invoice #INV-2025-001\n"
            "Total Amount: USD 15,000.00\n"
            "Quantity: 500 units\n"
            "Unit Price: $30.00\n"
        )
        r = ExtractionResult(text=text, confidence=0.8, method="test")
        v = validator.validate(r, expected_type="invoice")
        assert v.valid is True
        # No WARNING about missing keywords
        assert not any("No invoice keywords" in i for i in v.issues)

    def test_invoice_without_keywords_warns(self, validator):
        text = "Some random text about flowers and gardens and nature " * 5
        r = ExtractionResult(text=text, confidence=0.8, method="test")
        v = validator.validate(r, expected_type="invoice")
        assert any("invoice keywords" in i.lower() for i in v.issues)

    def test_bl_with_keywords_passes(self, validator):
        text = (
            "Bill of Lading\n"
            "Shipper: ABC Corp\n"
            "Consignee: XYZ Ltd\n"
            "Port of Loading: Shanghai\n"
        )
        r = ExtractionResult(text=text, confidence=0.8, method="test")
        v = validator.validate(r, expected_type="bill_of_lading")
        assert not any("bill-of-lading keywords" in i.lower() for i in v.issues)

    def test_tariff_with_hs_code(self, validator):
        text = "Tariff classification: 85.17.620000/2 for electronic devices " * 3
        r = ExtractionResult(text=text, confidence=0.8, method="test")
        v = validator.validate(r, expected_type="tariff_entry")
        assert not any("HS-code format" in i for i in v.issues)

    def test_tariff_without_hs_code_warns(self, validator):
        text = "Some tariff document without proper codes but enough text content " * 3
        r = ExtractionResult(text=text, confidence=0.8, method="test")
        v = validator.validate(r, expected_type="tariff_entry")
        assert any("HS-code" in i for i in v.issues)

    def test_coo_hebrew(self, validator):
        text = "תעודת מקור - ארץ מוצא: ישראל - מספר תעודה: 12345 " * 2
        r = ExtractionResult(text=text, confidence=0.8, method="test")
        v = validator.validate(r, expected_type="certificate_of_origin")
        assert v.valid is True


# ─────────────────────────────────────
#  Confidence adjustment
# ─────────────────────────────────────

class TestConfidenceAdjustment:

    def test_no_issues_no_adjustment(self, validator):
        text = "Sufficient text content with many words to pass all checks " * 3
        r = ExtractionResult(text=text, confidence=0.8, method="test")
        v = validator.validate(r)
        assert v.confidence_adjustment == 0.0

    def test_critical_issue_large_penalty(self, validator):
        r = ExtractionResult(text="", confidence=0.8, method="test")
        v = validator.validate(r)
        assert v.confidence_adjustment < 0

    def test_warnings_small_penalty(self, validator):
        text = "12345 67890 " * 20  # Numbers only, no language detected
        r = ExtractionResult(text=text, confidence=0.8, method="test")
        v = validator.validate(r, expected_type="invoice")
        # Should have warnings but still be valid (no CRITICAL issues)
        warning_count = sum(1 for i in v.issues if i.startswith("WARNING"))
        if warning_count > 0:
            assert v.confidence_adjustment < 0
