"""Tests for Chapter Decision Trees — Session 98.

5 mandatory test cases from the design spec:
  1. חסילון חי → 03.06.11
  2. חסילון קפוא מקולף → 03.06.17
  3. חסילון מצופה פירורי לחם → REDIRECT Ch.16
  4. דג סלמון טרי → 03.02
  5. דג מעושן → 03.05

Plus additional edge cases for creature detection, state detection, and routing.
"""

import sys
import os
import unittest

# Ensure functions/lib is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from lib._chapter_decision_trees import (
    decide_chapter,
    _decide_chapter_03,
    _detect_creature_type,
    _detect_crustacean_species,
    _get_processing_state,
    _is_fillet,
    _is_peeled,
    _is_chapter_03_candidate,
    available_chapters,
)


def _make_product(name, essence="", physical="", function="human consumption",
                  transformation_stage="", processing_state="",
                  dominant_material_pct=None):
    """Helper to build a product dict matching Layer 0 output."""
    return {
        "name": name,
        "essence": essence,
        "physical": physical,
        "function": function,
        "transformation_stage": transformation_stage,
        "processing_state": processing_state,
        "dominant_material_pct": dominant_material_pct,
    }


# ========================================================================
# 5 MANDATORY TEST CASES (from design spec)
# ========================================================================

class TestMandatoryCases(unittest.TestCase):
    """The 5 test cases specified in the plan."""

    def test_01_live_langoustine(self):
        """חסילון חי → 03.06.11"""
        product = _make_product(
            name="חסילון חי",
            essence="langoustine, live",
            physical="crustacean, whole, live",
            processing_state="live",
            transformation_stage="raw",
        )
        result = _decide_chapter_03(product)

        self.assertEqual(result["chapter"], 3)
        self.assertIsNone(result["redirect"])
        self.assertTrue(len(result["candidates"]) >= 1)

        best = result["candidates"][0]
        self.assertEqual(best["heading"], "03.06")
        self.assertEqual(best["subheading_hint"], "0306.11")
        self.assertGreaterEqual(best["confidence"], 0.85)

    def test_02_frozen_peeled_langoustine(self):
        """חסילון קפוא מקולף → 03.06.17"""
        product = _make_product(
            name="חסילון קפוא מקולף",
            essence="langoustine meat, shell removed",
            physical="crustacean meat 100%, peeled tail meat",
            processing_state="frozen",
            transformation_stage="semi_processed",
            dominant_material_pct=100,
        )
        result = _decide_chapter_03(product)

        self.assertEqual(result["chapter"], 3)
        self.assertIsNone(result["redirect"])
        self.assertTrue(len(result["candidates"]) >= 1)

        best = result["candidates"][0]
        self.assertEqual(best["heading"], "03.06")
        self.assertEqual(best["subheading_hint"], "0306.17")
        self.assertGreaterEqual(best["confidence"], 0.80)

    def test_03_breaded_langoustine_redirect(self):
        """חסילון מצופה פירורי לחם → REDIRECT Ch.16"""
        product = _make_product(
            name="חסילון מצופה פירורי לחם",
            essence="breaded langoustine",
            physical="crustacean meat coated in breadcrumbs",
            processing_state="compound",
            transformation_stage="prepared",
        )
        result = _decide_chapter_03(product)

        self.assertEqual(result["chapter"], 3)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 16)
        self.assertIn("compound", result["redirect"]["reason"])
        self.assertEqual(len(result["candidates"]), 0)

    def test_04_fresh_salmon(self):
        """דג סלמון טרי → 03.02"""
        product = _make_product(
            name="דג סלמון טרי",
            essence="salmon, fresh whole fish",
            physical="fish, whole, fresh",
            processing_state="fresh",
            transformation_stage="raw",
        )
        result = _decide_chapter_03(product)

        self.assertEqual(result["chapter"], 3)
        self.assertIsNone(result["redirect"])
        self.assertTrue(len(result["candidates"]) >= 1)

        best = result["candidates"][0]
        self.assertEqual(best["heading"], "03.02")
        self.assertGreaterEqual(best["confidence"], 0.85)

    def test_05_smoked_fish(self):
        """דג מעושן → 03.05"""
        product = _make_product(
            name="דג מעושן",
            essence="smoked fish",
            physical="fish, smoked",
            processing_state="smoked",
            transformation_stage="semi_processed",
        )
        result = _decide_chapter_03(product)

        self.assertEqual(result["chapter"], 3)
        self.assertIsNone(result["redirect"])
        self.assertTrue(len(result["candidates"]) >= 1)

        best = result["candidates"][0]
        self.assertEqual(best["heading"], "03.05")
        self.assertGreaterEqual(best["confidence"], 0.85)


# ========================================================================
# CREATURE TYPE DETECTION
# ========================================================================

class TestCreatureDetection(unittest.TestCase):

    def test_fish_hebrew(self):
        self.assertEqual(_detect_creature_type("דג סלמון"), "fish")

    def test_fish_english(self):
        self.assertEqual(_detect_creature_type("fresh salmon fillet"), "fish")

    def test_crustacean_hebrew(self):
        self.assertEqual(_detect_creature_type("חסילון קפוא"), "crustacean")

    def test_crustacean_english(self):
        self.assertEqual(_detect_creature_type("frozen shrimp"), "crustacean")

    def test_mollusc_hebrew(self):
        self.assertEqual(_detect_creature_type("קלמרי טבעות"), "mollusc")

    def test_mollusc_english(self):
        self.assertEqual(_detect_creature_type("fresh squid"), "mollusc")

    def test_other_invertebrate(self):
        self.assertEqual(_detect_creature_type("sea cucumber dried"), "other_invertebrate")

    def test_flour_meal(self):
        self.assertEqual(_detect_creature_type("fish meal pellets"), "flour_meal")

    def test_unknown(self):
        self.assertEqual(_detect_creature_type("some random product"), "unknown")


# ========================================================================
# CRUSTACEAN SPECIES DETECTION
# ========================================================================

class TestCrustaceanSpecies(unittest.TestCase):

    def test_langoustine_hebrew(self):
        self.assertEqual(_detect_crustacean_species("חסילון"), "lobster_langoustine")

    def test_lobster_english(self):
        self.assertEqual(_detect_crustacean_species("rock lobster"), "lobster_langoustine")

    def test_shrimp_english(self):
        self.assertEqual(_detect_crustacean_species("frozen shrimp"), "shrimp_prawn")

    def test_crab_hebrew(self):
        self.assertEqual(_detect_crustacean_species("סרטן"), "crab")

    def test_other_crustacean(self):
        self.assertEqual(_detect_crustacean_species("krill"), "other")


# ========================================================================
# PROCESSING STATE DETECTION
# ========================================================================

class TestProcessingState(unittest.TestCase):

    def test_compound_override_from_text(self):
        """Even if processing_state=frozen, breaded text → compound."""
        product = _make_product(
            name="חסילון מצופה פירורי לחם",
            processing_state="frozen",
        )
        self.assertEqual(_get_processing_state(product), "compound")

    def test_frozen_stays_frozen(self):
        product = _make_product(name="שרימפס קפוא", processing_state="frozen")
        self.assertEqual(_get_processing_state(product), "frozen")

    def test_empty_state(self):
        product = _make_product(name="some fish", processing_state="")
        self.assertEqual(_get_processing_state(product), "")


# ========================================================================
# CHAPTER GATE — REDIRECT LOGIC
# ========================================================================

class TestChapterGate(unittest.TestCase):

    def test_preserved_fish_redirect(self):
        """Canned tuna → redirect Ch.16."""
        product = _make_product(
            name="טונה בשימורים",
            essence="canned tuna",
            processing_state="preserved",
        )
        result = _decide_chapter_03(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 16)

    def test_cooked_fish_redirect(self):
        """Cooked fish (not crustacean) → redirect Ch.16."""
        product = _make_product(
            name="דג מבושל",
            essence="cooked fish",
            processing_state="cooked",
        )
        result = _decide_chapter_03(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 16)

    def test_cooked_crustacean_in_shell_stays(self):
        """Cooked crustacean in shell → stays Ch.03."""
        product = _make_product(
            name="לובסטר מבושל בקליפה",
            essence="cooked lobster in shell",
            processing_state="cooked",
        )
        result = _decide_chapter_03(product)
        # Should NOT redirect because "בקליפה" is present
        self.assertIsNone(result["redirect"])
        self.assertTrue(len(result["candidates"]) >= 1)
        self.assertEqual(result["candidates"][0]["heading"], "03.06")

    def test_cooked_crustacean_no_shell_question(self):
        """Cooked crustacean without shell mention → needs clarification."""
        product = _make_product(
            name="לובסטר מבושל",
            essence="cooked lobster",
            processing_state="cooked",
        )
        result = _decide_chapter_03(product)
        # Should have a question, and tentative candidate
        self.assertTrue(len(result["questions_needed"]) >= 1)
        self.assertIn("בקליפה", result["questions_needed"][0])


# ========================================================================
# FISH ROUTING
# ========================================================================

class TestFishRouting(unittest.TestCase):

    def test_live_fish(self):
        product = _make_product(name="דג חי", processing_state="live")
        result = _decide_chapter_03(product)
        self.assertEqual(result["candidates"][0]["heading"], "03.01")

    def test_frozen_whole_fish(self):
        product = _make_product(name="דג קפוא", processing_state="frozen")
        result = _decide_chapter_03(product)
        self.assertEqual(result["candidates"][0]["heading"], "03.03")

    def test_fish_fillet_fresh(self):
        product = _make_product(
            name="פילה דג טרי",
            physical="fish fillet",
            processing_state="fresh",
        )
        result = _decide_chapter_03(product)
        self.assertEqual(result["candidates"][0]["heading"], "03.04")

    def test_fish_fillet_frozen(self):
        product = _make_product(
            name="frozen salmon fillet",
            physical="fish fillet, frozen",
            processing_state="frozen",
        )
        result = _decide_chapter_03(product)
        self.assertEqual(result["candidates"][0]["heading"], "03.04")

    def test_salted_fish(self):
        product = _make_product(name="דג מלוח", processing_state="salted")
        result = _decide_chapter_03(product)
        self.assertEqual(result["candidates"][0]["heading"], "03.05")

    def test_dried_fish(self):
        product = _make_product(name="דג מיובש", processing_state="dried")
        result = _decide_chapter_03(product)
        self.assertEqual(result["candidates"][0]["heading"], "03.05")

    def test_unknown_state_fish(self):
        """Fish with unknown state → multiple candidates + question."""
        product = _make_product(name="דג", processing_state="")
        result = _decide_chapter_03(product)
        self.assertTrue(len(result["candidates"]) >= 2)
        self.assertTrue(len(result["questions_needed"]) >= 1)


# ========================================================================
# CRUSTACEAN ROUTING
# ========================================================================

class TestCrustaceanRouting(unittest.TestCase):

    def test_live_shrimp(self):
        product = _make_product(
            name="שרימפס חי",
            processing_state="live",
        )
        result = _decide_chapter_03(product)
        best = result["candidates"][0]
        self.assertEqual(best["heading"], "03.06")
        # Live shrimp goes to 0306.19 (other live crustaceans)
        self.assertIn("0306", best["subheading_hint"])

    def test_frozen_crab(self):
        product = _make_product(
            name="frozen crab",
            processing_state="frozen",
        )
        result = _decide_chapter_03(product)
        best = result["candidates"][0]
        self.assertEqual(best["heading"], "03.06")
        self.assertEqual(best["subheading_hint"], "0306.14")

    def test_fresh_shrimp(self):
        product = _make_product(
            name="שרימפס טרי",
            processing_state="fresh",
        )
        result = _decide_chapter_03(product)
        best = result["candidates"][0]
        self.assertEqual(best["heading"], "03.06")
        self.assertEqual(best["subheading_hint"], "0306.36")


# ========================================================================
# PUBLIC API
# ========================================================================

class TestPublicAPI(unittest.TestCase):

    def test_decide_chapter_detects_fish(self):
        """decide_chapter() dispatches to ch.03 for fish products."""
        product = _make_product(name="דג סלמון טרי", processing_state="fresh")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 3)

    def test_decide_chapter_returns_none_for_non_fish(self):
        """decide_chapter() returns None for non-seafood."""
        product = _make_product(name="steel pipes")
        result = decide_chapter(product)
        self.assertIsNone(result)

    def test_available_chapters(self):
        chapters = available_chapters()
        self.assertIn(3, chapters)

    def test_is_chapter_03_candidate(self):
        self.assertTrue(_is_chapter_03_candidate("frozen salmon"))
        self.assertTrue(_is_chapter_03_candidate("חסילון"))
        self.assertFalse(_is_chapter_03_candidate("steel pipes"))


# ========================================================================
# BREADED OVERRIDE — compound detection from text even when state wrong
# ========================================================================

class TestCompoundOverride(unittest.TestCase):

    def test_breaded_detected_from_name_only(self):
        """Even with no processing_state, breaded in name → redirect."""
        product = _make_product(
            name="שרימפס מצופה פירורי לחם",
            processing_state="frozen",  # AI might say frozen
        )
        result = _decide_chapter_03(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 16)

    def test_tempura_shrimp_redirect(self):
        product = _make_product(
            name="tempura shrimp",
            essence="battered shrimp",
            processing_state="frozen",
        )
        result = _decide_chapter_03(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 16)

    def test_marinated_fish_redirect(self):
        product = _make_product(
            name="דג במרינדה",
            processing_state="fresh",
        )
        result = _decide_chapter_03(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 16)


if __name__ == "__main__":
    unittest.main()
