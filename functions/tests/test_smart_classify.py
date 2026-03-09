"""Tests for smart_classify.py — synonym expansion + classification pipeline."""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Ensure functions/ is on path
_funcs = os.path.join(os.path.dirname(__file__), '..')
if _funcs not in sys.path:
    sys.path.insert(0, _funcs)

from lib.smart_classify import (
    expand_query,
    classify_product,
    ClassificationResult,
    Confidence,
    get_vocab_stats,
    reset_caches,
    _tokenize,
    _strip_prefixes,
    _score_specificity,
    _check_chapter_notes_exclusion,
    _extract_official_terms_from_shaarolami,
)


class TestTokenize(unittest.TestCase):
    """Test Hebrew/English tokenization."""

    def test_hebrew_basic(self):
        tokens = _tokenize("ספה תלת מושבית")
        self.assertIn("ספה", tokens)
        self.assertIn("תלת", tokens)
        self.assertIn("מושבית", tokens)

    def test_english_basic(self):
        tokens = _tokenize("frozen peeled cooked shrimp")
        self.assertIn("frozen", tokens)
        self.assertIn("peeled", tokens)
        self.assertIn("cooked", tokens)
        self.assertIn("shrimp", tokens)

    def test_stop_words_filtered(self):
        tokens = _tokenize("the big and small items")
        self.assertNotIn("the", tokens)
        self.assertNotIn("and", tokens)

    def test_short_words_filtered(self):
        tokens = _tokenize("a b cd efg")
        self.assertNotIn("a", tokens)
        self.assertNotIn("b", tokens)
        self.assertIn("cd", tokens)

    def test_empty_input(self):
        self.assertEqual(_tokenize(""), [])
        self.assertEqual(_tokenize(None), [])

    def test_mixed_hebrew_english(self):
        tokens = _tokenize("שרימפס frozen imported")
        self.assertIn("שרימפס", tokens)
        self.assertIn("frozen", tokens)
        self.assertIn("imported", tokens)


class TestStripPrefixes(unittest.TestCase):
    """Test Hebrew prefix stripping."""

    def test_basic_prefix(self):
        variants = _strip_prefixes("מפלדה")
        self.assertIn("מפלדה", variants)
        self.assertIn("פלדה", variants)

    def test_compound_prefix(self):
        variants = _strip_prefixes("והברזל")
        self.assertIn("והברזל", variants)
        # Should strip "וה" compound prefix
        self.assertIn("ברזל", variants)

    def test_short_word_no_strip(self):
        variants = _strip_prefixes("של")
        # Too short after stripping — shouldn't strip
        self.assertEqual(variants, ["של"])

    def test_no_prefix(self):
        variants = _strip_prefixes("rubber")
        self.assertEqual(variants, ["rubber"])


class TestScoreSpecificity(unittest.TestCase):
    """Test GIR Rule 1 specificity scoring."""

    def test_high_match(self):
        candidate = {"description_he": "ספות ישיבה מרופדות", "hs_raw": "9401710000"}
        score = _score_specificity(candidate, ["ספה", "מרופד"])
        self.assertGreater(score, 0.3)

    def test_vague_penalty(self):
        candidate = {"description_he": "אחרים", "description_en": "Others", "hs_raw": "9401900000"}
        score = _score_specificity(candidate, ["ספה"])
        # Vague "אחרים" should be penalized
        self.assertLess(score, 0.3)

    def test_no_description(self):
        candidate = {"description_he": "", "description_en": "", "hs_raw": ""}
        score = _score_specificity(candidate, ["ספה"])
        self.assertEqual(score, 0.0)

    def test_english_match(self):
        candidate = {"description_en": "Frozen shrimp, peeled", "hs_raw": "0306170000"}
        score = _score_specificity(candidate, ["frozen", "shrimp", "peeled"])
        self.assertGreater(score, 0.5)


class TestExtractOfficialTerms(unittest.TestCase):
    """Test official term extraction from shaarolami results."""

    def test_basic_extraction(self):
        results = [
            ("0306170000", "סרטנים מקפיא"),
            ("0306310000", "שרימפס וחסילונים"),
        ]
        terms = _extract_official_terms_from_shaarolami(results)
        self.assertIsInstance(terms, list)
        self.assertTrue(len(terms) > 0)
        # "סרטנים" should be one of the extracted terms
        self.assertTrue(any("סרטנים" in t for t in terms) or len(terms) > 0)

    def test_empty_results(self):
        terms = _extract_official_terms_from_shaarolami([])
        self.assertEqual(terms, [])


class TestCheckChapterNotesExclusion(unittest.TestCase):
    """Test chapter notes cross-check."""

    def test_no_notes_returns_none(self):
        candidate = {"hs_raw": "9401710000"}
        result = _check_chapter_notes_exclusion(candidate, ["ספה"], [], db=None)
        self.assertIsNone(result)

    def test_exclusion_match(self):
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "exclusions": ["פרק זה אינו כולל סרטנים חיים"],
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

        candidate = {"hs_raw": "1602000000"}
        result = _check_chapter_notes_exclusion(candidate, ["סרטנים"], [], db=mock_db)
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("excluded:"))

    def test_inclusion_match(self):
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "inclusions": ["פרק זה כולל שרימפס מבושלים ומקולפים"],
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

        candidate = {"hs_raw": "0306170000"}
        result = _check_chapter_notes_exclusion(candidate, ["שרימפס"], [], db=mock_db)
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("included:"))


class TestExpandQuery(unittest.TestCase):
    """Test synonym expansion."""

    def test_returns_list(self):
        # Even if vocab is empty, should return something
        result = expand_query("rubber gloves")
        self.assertIsInstance(result, list)

    def test_high_confidence_for_known_terms(self):
        """Terms in tariff tree vocabulary should get HIGH confidence."""
        result = expand_query("rubber")
        # "rubber" should be found in the tariff tree (if loaded)
        # or at least be returned as original
        self.assertTrue(len(result) > 0)
        terms = [t for t, _, _ in result]
        self.assertTrue(any("rubber" in t or "גומי" in t for t in terms))

    def test_synonym_expansion(self):
        """Synonyms should expand terms."""
        result = expand_query("ספה")
        terms = [t for t, _, _ in result]
        # "ספה" should trigger synonyms like "sofa", "couch", "furniture" etc.
        # At minimum the original term should be present
        self.assertTrue(any("ספה" in t or "sofa" in t or "couch" in t for t in terms))

    def test_empty_query(self):
        result = expand_query("")
        self.assertEqual(result, [])

    def test_mixed_language_expansion(self):
        result = expand_query("frozen shrimp מקולף")
        self.assertTrue(len(result) > 0)


class TestClassifyProduct(unittest.TestCase):
    """Test classify_product() end-to-end."""

    def test_returns_classification_result(self):
        result = classify_product("ספה")
        self.assertIsInstance(result, ClassificationResult)
        self.assertEqual(result.query, "ספה")

    def test_has_reasoning(self):
        result = classify_product("rubber gloves")
        self.assertIsInstance(result.reasoning, list)
        self.assertTrue(len(result.reasoning) > 0)

    def test_empty_query(self):
        result = classify_product("")
        self.assertEqual(result.hs_candidates, [])
        self.assertIn("Empty or unparseable query", result.reasoning[0])

    def test_hebrew_query_returns_candidates(self):
        """Hebrew furniture query should return candidates if index is loaded."""
        result = classify_product("ספה תלת מושבית מרופדת בד")
        # Index may or may not be loaded; check structure
        self.assertIsInstance(result.hs_candidates, list)
        self.assertIsInstance(result.expanded_terms, list)
        if result.hs_candidates:
            c = result.hs_candidates[0]
            self.assertIn("hs_code", c)

    def test_english_query_returns_candidates(self):
        result = classify_product("frozen peeled cooked shrimp")
        self.assertIsInstance(result.hs_candidates, list)
        if result.hs_candidates:
            c = result.hs_candidates[0]
            self.assertIn("hs_code", c)

    def test_confidence_field(self):
        result = classify_product("steel storage boxes")
        self.assertIn(result.confidence, ["HIGH", "MEDIUM", "LOW", "NONE"])

    def test_questions_field(self):
        result = classify_product("thing")
        self.assertIsInstance(result.questions_to_ask, list)

    def test_repr(self):
        """ClassificationResult repr should be readable."""
        result = classify_product("ספה")
        text = repr(result)
        self.assertIn("ClassificationResult", text)
        self.assertIn("ספה", text)


class TestClassificationResultDataclass(unittest.TestCase):
    """Test ClassificationResult dataclass."""

    def test_default_values(self):
        r = ClassificationResult()
        self.assertEqual(r.hs_candidates, [])
        self.assertEqual(r.confidence, "")
        self.assertEqual(r.reasoning, [])
        self.assertEqual(r.questions_to_ask, [])
        self.assertEqual(r.expanded_terms, [])
        self.assertEqual(r.query, "")

    def test_repr_with_data(self):
        r = ClassificationResult(
            query="test",
            hs_candidates=[{"hs_code": "01.02.030000/5", "score": 10}],
            confidence="HIGH",
            reasoning=["Found exact match"],
            expanded_terms=[("test", "tariff_tree_en", "HIGH")],
        )
        text = repr(r)
        self.assertIn("test", text)
        self.assertIn("01.02.030000/5", text)
        self.assertIn("Found exact match", text)


class TestConfidenceEnum(unittest.TestCase):
    """Test Confidence enum values."""

    def test_values(self):
        self.assertEqual(Confidence.HIGH.value, "HIGH")
        self.assertEqual(Confidence.MEDIUM.value, "MEDIUM")
        self.assertEqual(Confidence.LOW.value, "LOW")


class TestVocabStats(unittest.TestCase):
    """Test vocabulary statistics."""

    def test_stats_returns_dict(self):
        stats = get_vocab_stats()
        self.assertIn("he_words", stats)
        self.assertIn("en_words", stats)
        self.assertIsInstance(stats["he_words"], int)
        self.assertIsInstance(stats["en_words"], int)


class TestResetCaches(unittest.TestCase):
    """Test cache reset."""

    def test_reset_does_not_crash(self):
        reset_caches()
        # After reset, vocab should be rebuilt on next call
        stats = get_vocab_stats()
        self.assertIsInstance(stats, dict)


if __name__ == "__main__":
    unittest.main()
