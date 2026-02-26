"""
Tests for context_engine.py — System Intelligence First (SIF) layer.
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add parent dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.context_engine import (
    prepare_context_package,
    ContextPackage,
    _detect_language,
    _extract_entities,
    _detect_domain,
    _build_context_summary,
    _calculate_confidence,
)


class TestDetectLanguage(unittest.TestCase):
    def test_hebrew_text(self):
        self.assertEqual(_detect_language("", "שלום מה הסיווג של מכונת קפה"), "he")

    def test_english_text(self):
        self.assertEqual(_detect_language("Classification question", "What is the HS code for coffee machines"), "en")

    def test_mixed_text(self):
        result = _detect_language("", "Hello שלום world")
        self.assertIn(result, ("he", "mixed"))

    def test_empty_text(self):
        self.assertEqual(_detect_language("", ""), "he")


class TestExtractEntities(unittest.TestCase):
    def test_hs_code(self):
        entities = _extract_entities("", "מה הפרט של 8419.81.10?")
        self.assertTrue(len(entities["hs_codes"]) > 0)

    def test_hs_code_dotted(self):
        entities = _extract_entities("", "code 8507.60.0000")
        self.assertTrue(len(entities["hs_codes"]) > 0)

    def test_product_name(self):
        entities = _extract_entities("", "מה פרט המכס למכונת קפה")
        self.assertTrue(len(entities["product_names"]) > 0)
        self.assertIn("מכונת קפה", entities["product_names"][0])

    def test_container_number(self):
        entities = _extract_entities("", "Container MSCU1234567 arrived")
        self.assertEqual(entities["container_numbers"], ["MSCU1234567"])

    def test_no_entities(self):
        entities = _extract_entities("", "hello world")
        self.assertEqual(entities["hs_codes"], [])
        self.assertEqual(entities["product_names"], [])
        self.assertEqual(entities["container_numbers"], [])

    def test_article_number(self):
        entities = _extract_entities("", "מה כתוב בסעיף 200א לפקודת המכס?")
        self.assertIn("200א", entities["article_numbers"])

    def test_bl_number(self):
        entities = _extract_entities("", "BL MEDURS12345")
        self.assertTrue(len(entities["bl_numbers"]) > 0)

    def test_multiple_hs_codes(self):
        entities = _extract_entities("", "compare 8419.81.10 and 8516.71.00")
        self.assertTrue(len(entities["hs_codes"]) >= 2)


class TestDetectDomain(unittest.TestCase):
    def test_tariff_from_hs_code(self):
        entities = {"hs_codes": ["84198110"], "product_names": [], "article_numbers": [], "keywords": []}
        self.assertEqual(_detect_domain(entities, "", ""), "tariff")

    def test_ordinance_from_article(self):
        entities = {"hs_codes": [], "product_names": [], "article_numbers": ["200א"], "keywords": []}
        self.assertEqual(_detect_domain(entities, "", "סעיף 200א"), "ordinance")

    def test_fta_domain(self):
        entities = {"hs_codes": [], "product_names": [], "article_numbers": [], "keywords": []}
        self.assertEqual(_detect_domain(entities, "", "הסכם סחר חופשי"), "fta")

    def test_regulatory_domain(self):
        entities = {"hs_codes": [], "product_names": [], "article_numbers": [], "keywords": []}
        self.assertEqual(_detect_domain(entities, "", "צו יבוא חופשי"), "regulatory")

    def test_general_domain(self):
        entities = {"hs_codes": [], "product_names": [], "article_numbers": [], "keywords": []}
        self.assertEqual(_detect_domain(entities, "", "שאלה כללית"), "general")

    def test_classification_keywords(self):
        entities = {"hs_codes": [], "product_names": [], "article_numbers": [], "keywords": []}
        self.assertEqual(_detect_domain(entities, "סיווג מוצר", ""), "tariff")


class TestContextPackage(unittest.TestCase):
    def test_dataclass_defaults(self):
        pkg = ContextPackage(original_subject="test", original_body="body",
                             detected_language="he")
        self.assertEqual(pkg.domain, "general")
        self.assertEqual(pkg.confidence, 0.0)
        self.assertIsNone(pkg.cached_answer)
        self.assertEqual(pkg.tariff_results, [])

    def test_confidence_nothing_found(self):
        pkg = ContextPackage(original_subject="test", original_body="body",
                             detected_language="he")
        self.assertEqual(_calculate_confidence(pkg), 0.0)

    def test_confidence_tariff_found(self):
        pkg = ContextPackage(original_subject="test", original_body="body",
                             detected_language="he",
                             tariff_results=[{"hs_code": "8419"}])
        self.assertGreaterEqual(_calculate_confidence(pkg), 0.3)

    def test_confidence_tariff_plus_ordinance(self):
        pkg = ContextPackage(
            original_subject="test", original_body="body",
            detected_language="he",
            tariff_results=[{"hs_code": "8419"}],
            ordinance_articles=[{"article_id": "130"}]
        )
        self.assertGreaterEqual(_calculate_confidence(pkg), 0.6)

    def test_confidence_cached(self):
        pkg = ContextPackage(original_subject="test", original_body="body",
                             detected_language="he",
                             cached_answer={"answer_text": "cached"})
        self.assertGreaterEqual(_calculate_confidence(pkg), 0.3)

    def test_confidence_max_1(self):
        pkg = ContextPackage(
            original_subject="test", original_body="body",
            detected_language="he",
            tariff_results=[{"hs_code": "1"}],
            ordinance_articles=[{"id": "1"}],
            xml_results=[{"id": "1"}],
            regulatory_results=[{"id": "1"}],
            framework_articles=[{"id": "1"}],
            cached_answer={"answer_text": "yes"},
            entities={"keywords": ["test"]},
        )
        self.assertLessEqual(_calculate_confidence(pkg), 1.0)


class TestBuildContextSummary(unittest.TestCase):
    def test_empty_package(self):
        pkg = ContextPackage(original_subject="test", original_body="body",
                             detected_language="he", domain="general",
                             entities={"hs_codes": [], "product_names": [], "keywords": []})
        summary = _build_context_summary(pkg)
        self.assertIn("=== נתוני מערכת RCB ===", summary)
        self.assertIn("general", summary)

    def test_with_tariff(self):
        pkg = ContextPackage(
            original_subject="test", original_body="body",
            detected_language="he", domain="tariff",
            entities={"hs_codes": ["84198110"], "product_names": [], "keywords": []},
            tariff_results=[{"hs_code": "8419.81.10", "description_he": "מכונות"}]
        )
        summary = _build_context_summary(pkg)
        self.assertIn("8419.81.10", summary)
        self.assertIn("תוצאות חיפוש תעריף", summary)

    def test_with_ordinance(self):
        pkg = ContextPackage(
            original_subject="test", original_body="body",
            detected_language="he", domain="ordinance",
            entities={"hs_codes": [], "product_names": [], "article_numbers": ["130"], "keywords": []},
            ordinance_articles=[{
                "article_id": "130", "title_he": "ערך עסקה",
                "full_text_he": "נוסח הסעיף..."
            }]
        )
        summary = _build_context_summary(pkg)
        self.assertIn("סעיף 130", summary)
        self.assertIn("ערך עסקה", summary)


class TestPrepareContextPackage(unittest.TestCase):
    """Tests that prepare_context_package runs without crashing,
    even when db is None (all searches gracefully return empty)."""

    def test_no_db(self):
        pkg = prepare_context_package("שאלה על מכס", "מה הסיווג של קפה?", db=None)
        self.assertIsInstance(pkg, ContextPackage)
        self.assertEqual(pkg.domain, "tariff")  # "סיווג" → tariff
        self.assertIn("=== נתוני מערכת RCB ===", pkg.context_summary)

    def test_empty_inputs(self):
        pkg = prepare_context_package("", "", db=None)
        self.assertIsInstance(pkg, ContextPackage)
        self.assertEqual(pkg.domain, "general")

    def test_ordinance_question_no_db(self):
        pkg = prepare_context_package("", "מה כתוב בסעיף 130 לפקודת המכס", db=None)
        self.assertIsInstance(pkg, ContextPackage)
        self.assertEqual(pkg.domain, "ordinance")
        # Should find article 130 from in-memory data (no DB needed)
        self.assertTrue(len(pkg.ordinance_articles) > 0)

    def test_search_log_populated(self):
        pkg = prepare_context_package("test", "שאלה כללית", db=None)
        self.assertTrue(len(pkg.search_log) > 0)
        # Should have a "total" entry with elapsed_ms
        total_entries = [e for e in pkg.search_log if e.get("search") == "total"]
        self.assertTrue(len(total_entries) > 0)


if __name__ == '__main__':
    unittest.main()
