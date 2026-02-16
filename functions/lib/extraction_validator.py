"""
Validates extracted content BEFORE it enters the system.
Catches: empty text, garbage, encoding errors, reversed Hebrew, wrong column mapping.

Session 28C — Assignment 20.
NEW FILE — does not modify any existing code.
"""

import re
import logging
from .extraction_result import ExtractionResult, ValidationResult

logger = logging.getLogger("rcb.extraction_validator")


class ExtractionValidator:
    """Validates extraction quality before the data enters the pipeline."""

    def validate(self, extraction, expected_type=None):
        """
        Validate extraction quality.

        Args:
            extraction: ExtractionResult
            expected_type: str or None — "invoice", "bill_of_lading",
                "packing_list", "tariff_entry", "certificate_of_origin"

        Returns:
            ValidationResult
        """
        issues = []
        text = extraction.text.strip()

        # --- Basic quality checks ---

        # 1. Not empty
        if not text or len(text) < 20:
            issues.append("CRITICAL: Empty or near-empty extraction")
            return ValidationResult(
                valid=False, issues=issues, confidence_adjustment=-0.3,
            )

        # 2. Not garbage
        garbage_ratio = self._garbage_ratio(text)
        if garbage_ratio > 0.3:
            issues.append(
                f"CRITICAL: {garbage_ratio:.0%} garbage characters "
                "— likely encoding error or binary data"
            )
            return ValidationResult(
                valid=False, issues=issues, confidence_adjustment=-0.5,
            )

        # 3. Has substance (not just headers/boilerplate)
        unique_words = len(set(text.split()))
        if unique_words < 10:
            issues.append(
                f"WARNING: Only {unique_words} unique words "
                "— may be just headers/boilerplate"
            )

        # 4. Language detection
        lang = self._detect_language(text)
        if lang == "unknown":
            issues.append(
                "WARNING: Could not detect language — content may be garbled"
            )

        # 5. Hebrew RTL check
        if self._has_reversed_hebrew(text):
            issues.append(
                "WARNING: Hebrew text appears reversed "
                "(extracted as LTR instead of RTL)"
            )

        # --- Document-type specific checks ---
        if expected_type:
            type_checks = {
                "invoice": self._check_invoice,
                "bill_of_lading": self._check_bl,
                "packing_list": self._check_packing_list,
                "tariff_entry": self._check_tariff,
                "certificate_of_origin": self._check_coo,
            }
            checker = type_checks.get(expected_type)
            if checker:
                checker(text, issues)

        # --- Score ---
        critical_count = sum(1 for i in issues if i.startswith("CRITICAL"))
        warning_count = sum(1 for i in issues if i.startswith("WARNING"))

        return ValidationResult(
            valid=critical_count == 0,
            issues=issues,
            confidence_adjustment=(-0.3 * critical_count) + (-0.1 * warning_count),
        )

    # ─────────────────────────────────────
    #  Quality helpers
    # ─────────────────────────────────────

    def _garbage_ratio(self, text):
        """Ratio of non-printable / replacement characters."""
        garbage = sum(
            1 for c in text
            if (ord(c) < 32 and c not in "\n\r\t") or c in "\ufffd"
        )
        return garbage / max(len(text), 1)

    def _detect_language(self, text):
        """Simple Hebrew / English / mixed / unknown detection."""
        hebrew = len(re.findall(r"[\u0590-\u05FF]", text))
        english = len(re.findall(r"[a-zA-Z]", text))
        total = hebrew + english
        if total == 0:
            return "unknown"
        if hebrew > english * 2:
            return "hebrew"
        if english > hebrew * 2:
            return "english"
        return "mixed"

    def _has_reversed_hebrew(self, text):
        """
        Common LTR extraction bug: Hebrew words appear reversed.
        Checks for reversed versions of common Hebrew customs words.
        """
        hebrew_words = re.findall(r"[\u0590-\u05FF]+", text)
        if not hebrew_words:
            return False

        # Reversed common words:
        #   ישראל→לארשי  מכס→סכמ  שער→רעש  פטור→רוטפ  ייבא→אביי  יצוא→אוצי
        reversed_indicators = {"לארשי", "סכמ", "רעש", "רוטפ", "הביי", "אוצי"}
        for word in hebrew_words[:100]:
            if word in reversed_indicators:
                return True
        return False

    # ─────────────────────────────────────
    #  Document-type specific checks
    # ─────────────────────────────────────

    def _check_invoice(self, text, issues):
        numbers = re.findall(r"\d+[.,]\d+", text)
        if len(numbers) < 2:
            issues.append(
                "WARNING: Invoice has very few numbers "
                "— extraction may be incomplete"
            )
        keywords = [
            "invoice", "חשבונית", "total", 'סה"כ',
            "qty", "כמות", "amount", "price", "unit",
        ]
        if not any(kw in text.lower() for kw in keywords):
            issues.append(
                "WARNING: No invoice keywords found "
                "— may not be invoice or extraction failed"
            )

    def _check_bl(self, text, issues):
        keywords = [
            "bill of lading", "שטר מטען", "b/l",
            "consignee", "shipper", "notify", "port of loading",
        ]
        if not any(kw in text.lower() for kw in keywords):
            issues.append("WARNING: No bill-of-lading keywords found")

    def _check_packing_list(self, text, issues):
        keywords = [
            "packing", "אריזה", "carton", "weight",
            "משקל", "dimension", "pieces", "gross", "net",
        ]
        if not any(kw in text.lower() for kw in keywords):
            issues.append("WARNING: No packing-list keywords found")

    def _check_tariff(self, text, issues):
        hs = re.findall(r"\d{2}\.\d{2}\.\d{6}/\d", text)
        if not hs:
            issues.append(
                "WARNING: No Israeli HS-code format (XX.XX.XXXXXX/X) found "
                "in tariff entry"
            )

    def _check_coo(self, text, issues):
        keywords = [
            "certificate of origin", "תעודת מקור",
            "country of origin", "ארץ מוצא",
        ]
        if not any(kw in text.lower() for kw in keywords):
            issues.append(
                "WARNING: No certificate-of-origin keywords found"
            )
