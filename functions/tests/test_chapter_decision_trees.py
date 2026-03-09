"""Tests for Chapter Decision Trees — Sessions 98-99.

Chapter 03 (Session 98): 5 mandatory test cases + edge cases.
Chapters 01-05 (Session 99a): species/product routing + gate tests.
Chapters 06-15 (Session 99b): plants, vegetables, fruit, spices, cereals, oils.
Chapters 16-24 (Session 99c): prepared foods, beverages, tobacco.
"""

import sys
import os
import unittest

# Ensure functions/lib is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from lib._chapter_decision_trees import (
    decide_chapter,
    _decide_chapter_01,
    _decide_chapter_02,
    _decide_chapter_03,
    _decide_chapter_04,
    _decide_chapter_05,
    _decide_chapter_06,
    _decide_chapter_07,
    _decide_chapter_08,
    _decide_chapter_09,
    _decide_chapter_10,
    _decide_chapter_11,
    _decide_chapter_12,
    _decide_chapter_13,
    _decide_chapter_14,
    _decide_chapter_15,
    _decide_chapter_16,
    _decide_chapter_17,
    _decide_chapter_18,
    _decide_chapter_19,
    _decide_chapter_20,
    _decide_chapter_21,
    _decide_chapter_22,
    _decide_chapter_23,
    _decide_chapter_24,
    _detect_creature_type,
    _detect_crustacean_species,
    _detect_ch01_species,
    _detect_ch02_species,
    _detect_ch04_product_type,
    _detect_ch05_product_type,
    _detect_ch16_product_type,
    _get_processing_state,
    _is_fillet,
    _is_peeled,
    _is_chapter_01_candidate,
    _is_chapter_02_candidate,
    _is_chapter_03_candidate,
    _is_chapter_04_candidate,
    _is_chapter_05_candidate,
    _is_chapter_06_candidate,
    _is_chapter_07_candidate,
    _is_chapter_08_candidate,
    _is_chapter_09_candidate,
    _is_chapter_10_candidate,
    _is_chapter_11_candidate,
    _is_chapter_12_candidate,
    _is_chapter_13_candidate,
    _is_chapter_14_candidate,
    _is_chapter_15_candidate,
    _is_chapter_16_candidate,
    _is_chapter_17_candidate,
    _is_chapter_18_candidate,
    _is_chapter_19_candidate,
    _is_chapter_20_candidate,
    _is_chapter_21_candidate,
    _is_chapter_22_candidate,
    _is_chapter_23_candidate,
    _is_chapter_24_candidate,
    _decide_chapter_25,
    _decide_chapter_26,
    _decide_chapter_27,
    _decide_chapter_28,
    _decide_chapter_29,
    _decide_chapter_30,
    _decide_chapter_31,
    _decide_chapter_32,
    _decide_chapter_33,
    _decide_chapter_34,
    _decide_chapter_35,
    _decide_chapter_36,
    _decide_chapter_37,
    _decide_chapter_38,
    _is_chapter_25_candidate,
    _is_chapter_26_candidate,
    _is_chapter_27_candidate,
    _is_chapter_28_candidate,
    _is_chapter_29_candidate,
    _is_chapter_30_candidate,
    _is_chapter_31_candidate,
    _is_chapter_32_candidate,
    _is_chapter_33_candidate,
    _is_chapter_34_candidate,
    _is_chapter_35_candidate,
    _is_chapter_36_candidate,
    _is_chapter_37_candidate,
    _is_chapter_38_candidate,
    _decide_chapter_39,
    _decide_chapter_40,
    _decide_chapter_41,
    _decide_chapter_42,
    _decide_chapter_43,
    _decide_chapter_44,
    _decide_chapter_45,
    _decide_chapter_46,
    _decide_chapter_47,
    _decide_chapter_48,
    _decide_chapter_49,
    _decide_chapter_50,
    _decide_chapter_51,
    _decide_chapter_52,
    _decide_chapter_53,
    _decide_chapter_54,
    _decide_chapter_55,
    _is_chapter_39_candidate,
    _is_chapter_40_candidate,
    _is_chapter_41_candidate,
    _is_chapter_42_candidate,
    _is_chapter_43_candidate,
    _is_chapter_44_candidate,
    _is_chapter_45_candidate,
    _is_chapter_46_candidate,
    _is_chapter_47_candidate,
    _is_chapter_48_candidate,
    _is_chapter_49_candidate,
    _is_chapter_50_candidate,
    _is_chapter_51_candidate,
    _is_chapter_52_candidate,
    _is_chapter_53_candidate,
    _is_chapter_54_candidate,
    _is_chapter_55_candidate,
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


# ========================================================================
# CHAPTER 01 — LIVE ANIMALS
# ========================================================================

class TestChapter01Species(unittest.TestCase):

    def test_bovine_hebrew(self):
        self.assertEqual(_detect_ch01_species("עגל חי"), "bovine")

    def test_poultry_english(self):
        self.assertEqual(_detect_ch01_species("live chicken"), "poultry")

    def test_horse(self):
        self.assertEqual(_detect_ch01_species("live horse"), "horse")

    def test_sheep(self):
        self.assertEqual(_detect_ch01_species("live lamb"), "ovine_caprine")

    def test_swine(self):
        self.assertEqual(_detect_ch01_species("live pig"), "swine")

    def test_unknown(self):
        self.assertEqual(_detect_ch01_species("live parrot"), "other")


class TestChapter01Tree(unittest.TestCase):

    def test_live_cattle_0102(self):
        """Live bovine → 01.02."""
        product = _make_product(name="בקר חי", essence="live cattle",
                                processing_state="live")
        result = _decide_chapter_01(product)
        self.assertEqual(result["chapter"], 1)
        self.assertIsNone(result["redirect"])
        self.assertEqual(result["candidates"][0]["heading"], "01.02")
        self.assertGreaterEqual(result["candidates"][0]["confidence"], 0.85)

    def test_live_chicken_0105(self):
        """Live poultry → 01.05."""
        product = _make_product(name="תרנגולות חיות", essence="live chickens",
                                processing_state="live")
        result = _decide_chapter_01(product)
        self.assertEqual(result["candidates"][0]["heading"], "01.05")

    def test_live_horse_0101(self):
        """Live horse → 01.01."""
        product = _make_product(name="סוס חי", essence="live horse",
                                processing_state="live")
        result = _decide_chapter_01(product)
        self.assertEqual(result["candidates"][0]["heading"], "01.01")

    def test_live_goat_0104(self):
        """Live goat → 01.04."""
        product = _make_product(name="עז חיה", essence="live goat",
                                physical="animal, live", processing_state="live")
        result = _decide_chapter_01(product)
        self.assertEqual(result["candidates"][0]["heading"], "01.04")

    def test_slaughtered_cattle_redirect_ch02(self):
        """Slaughtered cattle with meat → redirect Ch.02."""
        product = _make_product(name="בשר בקר טרי", essence="fresh beef meat",
                                processing_state="fresh")
        result = _decide_chapter_01(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 2)

    def test_live_pig_0103(self):
        """Live swine → 01.03."""
        product = _make_product(name="חזיר חי", essence="live pig",
                                processing_state="live")
        result = _decide_chapter_01(product)
        self.assertEqual(result["candidates"][0]["heading"], "01.03")

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_01_candidate("live cattle"))
        self.assertTrue(_is_chapter_01_candidate("עגל חי"))
        self.assertFalse(_is_chapter_01_candidate("steel pipes"))


# ========================================================================
# CHAPTER 02 — MEAT AND EDIBLE OFFAL
# ========================================================================

class TestChapter02Tree(unittest.TestCase):

    def test_fresh_beef_0201(self):
        """Fresh beef → 02.01."""
        product = _make_product(name="בשר בקר טרי", essence="fresh beef",
                                physical="meat, beef", processing_state="fresh")
        result = _decide_chapter_02(product)
        self.assertEqual(result["chapter"], 2)
        self.assertIsNone(result["redirect"])
        self.assertEqual(result["candidates"][0]["heading"], "02.01")

    def test_frozen_beef_0202(self):
        """Frozen beef → 02.02."""
        product = _make_product(name="frozen beef cuts",
                                physical="meat, beef, frozen",
                                processing_state="frozen")
        result = _decide_chapter_02(product)
        self.assertEqual(result["candidates"][0]["heading"], "02.02")

    def test_pork_0203(self):
        """Swine meat → 02.03."""
        product = _make_product(name="pork chops fresh",
                                physical="meat, pork",
                                processing_state="fresh")
        result = _decide_chapter_02(product)
        self.assertEqual(result["candidates"][0]["heading"], "02.03")

    def test_lamb_0204(self):
        """Lamb meat → 02.04."""
        product = _make_product(name="כבש טרי", essence="fresh lamb",
                                physical="meat", processing_state="fresh")
        result = _decide_chapter_02(product)
        self.assertEqual(result["candidates"][0]["heading"], "02.04")

    def test_chicken_0207(self):
        """Poultry meat → 02.07."""
        product = _make_product(name="חזה עוף קפוא", essence="frozen chicken breast",
                                physical="poultry meat", processing_state="frozen")
        result = _decide_chapter_02(product)
        self.assertEqual(result["candidates"][0]["heading"], "02.07")

    def test_offal_0206(self):
        """Beef liver → 02.06."""
        product = _make_product(name="כבד בקר", essence="beef liver",
                                physical="offal", processing_state="fresh")
        result = _decide_chapter_02(product)
        self.assertEqual(result["candidates"][0]["heading"], "02.06")

    def test_smoked_meat_0210(self):
        """Smoked meat → 02.10."""
        product = _make_product(name="בשר בקר מעושן", essence="smoked beef",
                                processing_state="smoked")
        result = _decide_chapter_02(product)
        self.assertEqual(result["candidates"][0]["heading"], "02.10")

    def test_sausage_redirect_ch16(self):
        """Sausage → redirect Ch.16."""
        product = _make_product(name="נקניק בקר", essence="beef sausage",
                                physical="processed meat", processing_state="")
        result = _decide_chapter_02(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 16)

    def test_live_animal_redirect_ch01(self):
        """Live animal → redirect Ch.01."""
        product = _make_product(name="בקר חי", essence="live cattle",
                                physical="bovine", processing_state="live")
        result = _decide_chapter_02(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 1)

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_02_candidate("fresh beef meat"))
        self.assertTrue(_is_chapter_02_candidate("חזה עוף"))
        self.assertFalse(_is_chapter_02_candidate("fresh milk"))


# ========================================================================
# CHAPTER 04 — DAIRY, EGGS, HONEY
# ========================================================================

class TestChapter04ProductType(unittest.TestCase):

    def test_milk(self):
        self.assertEqual(_detect_ch04_product_type("fresh whole milk"), "milk")

    def test_cheese_hebrew(self):
        self.assertEqual(_detect_ch04_product_type("גבינה צהובה"), "cheese")

    def test_yogurt(self):
        self.assertEqual(_detect_ch04_product_type("plain yogurt"), "yogurt")

    def test_honey(self):
        self.assertEqual(_detect_ch04_product_type("דבש טבעי"), "honey")

    def test_eggs(self):
        self.assertEqual(_detect_ch04_product_type("fresh eggs"), "eggs")


class TestChapter04Tree(unittest.TestCase):

    def test_fresh_milk_0401(self):
        """Fresh milk → 04.01."""
        product = _make_product(name="חלב טרי", essence="fresh whole milk",
                                processing_state="fresh")
        result = _decide_chapter_04(product)
        self.assertEqual(result["chapter"], 4)
        self.assertIsNone(result["redirect"])
        self.assertEqual(result["candidates"][0]["heading"], "04.01")

    def test_milk_powder_0402(self):
        """Milk powder → 04.02."""
        product = _make_product(name="אבקת חלב", essence="milk powder concentrated",
                                processing_state="dried")
        result = _decide_chapter_04(product)
        self.assertEqual(result["candidates"][0]["heading"], "04.02")

    def test_yogurt_0403(self):
        """Yogurt → 04.03."""
        product = _make_product(name="יוגורט טבעי", essence="plain yogurt",
                                processing_state="fresh")
        result = _decide_chapter_04(product)
        self.assertEqual(result["candidates"][0]["heading"], "04.03")

    def test_cheese_0406(self):
        """Cheese → 04.06."""
        product = _make_product(name="גבינה צהובה", essence="cheddar cheese",
                                processing_state="")
        result = _decide_chapter_04(product)
        self.assertEqual(result["candidates"][0]["heading"], "04.06")

    def test_butter_0405(self):
        """Butter → 04.05."""
        product = _make_product(name="חמאה", essence="butter",
                                processing_state="fresh")
        result = _decide_chapter_04(product)
        self.assertEqual(result["candidates"][0]["heading"], "04.05")

    def test_honey_0409(self):
        """Natural honey → 04.09."""
        product = _make_product(name="דבש טבעי", essence="natural honey",
                                processing_state="")
        result = _decide_chapter_04(product)
        self.assertEqual(result["candidates"][0]["heading"], "04.09")
        self.assertGreaterEqual(result["candidates"][0]["confidence"], 0.90)

    def test_eggs_in_shell_0407(self):
        """Fresh eggs in shell → 04.07."""
        product = _make_product(name="ביצים טריות", essence="fresh eggs in shell",
                                processing_state="fresh")
        result = _decide_chapter_04(product)
        self.assertEqual(result["candidates"][0]["heading"], "04.07")

    def test_egg_yolk_0408(self):
        """Egg yolk → 04.08."""
        product = _make_product(name="חלמון ביצה", essence="egg yolk separated",
                                processing_state="")
        result = _decide_chapter_04(product)
        self.assertEqual(result["candidates"][0]["heading"], "04.08")

    def test_ice_cream_redirect_ch21(self):
        """Ice cream → redirect Ch.21."""
        product = _make_product(name="גלידה שוקולד", essence="chocolate ice cream",
                                processing_state="frozen")
        result = _decide_chapter_04(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 21)

    def test_royal_jelly_0410(self):
        """Royal jelly → 04.10."""
        product = _make_product(name="royal jelly", essence="bee royal jelly",
                                processing_state="")
        result = _decide_chapter_04(product)
        self.assertEqual(result["candidates"][0]["heading"], "04.10")

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_04_candidate("fresh milk"))
        self.assertTrue(_is_chapter_04_candidate("גבינה"))
        self.assertTrue(_is_chapter_04_candidate("דבש"))
        self.assertFalse(_is_chapter_04_candidate("steel pipes"))


# ========================================================================
# CHAPTER 05 — OTHER ANIMAL PRODUCTS
# ========================================================================

class TestChapter05ProductType(unittest.TestCase):

    def test_bristle(self):
        self.assertEqual(_detect_ch05_product_type("pig bristle"), "hair_bristle")

    def test_feather(self):
        self.assertEqual(_detect_ch05_product_type("goose down feathers"), "feather_down")

    def test_bone(self):
        self.assertEqual(_detect_ch05_product_type("bone meal powder"), "bone_horn")

    def test_gut(self):
        self.assertEqual(_detect_ch05_product_type("natural sausage casings"), "guts")

    def test_blood(self):
        self.assertEqual(_detect_ch05_product_type("dried blood meal"), "blood")


class TestChapter05Tree(unittest.TestCase):

    def test_pig_bristle_0502(self):
        """Pig bristle → 05.02."""
        product = _make_product(name="pig bristle", essence="hog bristle for brushes",
                                processing_state="")
        result = _decide_chapter_05(product)
        self.assertEqual(result["chapter"], 5)
        self.assertIsNone(result["redirect"])
        self.assertEqual(result["candidates"][0]["heading"], "05.02")

    def test_feathers_0505(self):
        """Goose feathers → 05.05."""
        product = _make_product(name="נוצות אווז", essence="goose feathers and down",
                                processing_state="")
        result = _decide_chapter_05(product)
        self.assertEqual(result["candidates"][0]["heading"], "05.05")

    def test_bone_meal_0506(self):
        """Bone meal → 05.06."""
        product = _make_product(name="bone meal", essence="ground animal bones",
                                processing_state="")
        result = _decide_chapter_05(product)
        self.assertEqual(result["candidates"][0]["heading"], "05.06")

    def test_natural_casings_0504(self):
        """Natural sausage casings → 05.04."""
        product = _make_product(name="natural casings", essence="animal intestine casings",
                                processing_state="")
        result = _decide_chapter_05(product)
        self.assertEqual(result["candidates"][0]["heading"], "05.04")

    def test_animal_blood_0511(self):
        """Dried blood → 05.11."""
        product = _make_product(name="dried blood meal", essence="animal blood dried",
                                processing_state="dried")
        result = _decide_chapter_05(product)
        self.assertEqual(result["candidates"][0]["heading"], "05.11")

    def test_ambergris_0510(self):
        """Ambergris → 05.10."""
        product = _make_product(name="ambergris", essence="whale ambergris",
                                processing_state="")
        result = _decide_chapter_05(product)
        self.assertEqual(result["candidates"][0]["heading"], "05.10")

    def test_raw_hide_question(self):
        """Raw hide → 05.11 with question about Ch.41."""
        product = _make_product(name="raw hide untanned", essence="raw cattle skin",
                                processing_state="")
        result = _decide_chapter_05(product)
        self.assertEqual(result["candidates"][0]["heading"], "05.11")
        self.assertTrue(len(result["questions_needed"]) >= 1)
        self.assertIn("Ch.41", result["questions_needed"][0])

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_05_candidate("pig bristle"))
        self.assertTrue(_is_chapter_05_candidate("נוצות"))
        self.assertTrue(_is_chapter_05_candidate("bone meal"))
        self.assertFalse(_is_chapter_05_candidate("steel pipes"))


# ========================================================================
# PUBLIC API — Updated for all chapters
# ========================================================================

class TestPublicAPIAllChapters(unittest.TestCase):

    def test_available_chapters_includes_all(self):
        chapters = available_chapters()
        for ch in range(1, 16):
            self.assertIn(ch, chapters)
        self.assertEqual(len(chapters), 55)

    def test_decide_chapter_routes_to_ch01(self):
        product = _make_product(name="live cattle", essence="bovine animal",
                                physical="animal, live", processing_state="live")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 1)

    def test_decide_chapter_routes_to_ch02(self):
        product = _make_product(name="frozen beef meat cuts",
                                physical="beef, frozen", processing_state="frozen")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        # Should route to ch02 (meat detected)
        self.assertEqual(result["chapter"], 2)

    def test_decide_chapter_routes_to_ch04(self):
        product = _make_product(name="חלב טרי", processing_state="fresh")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 4)

    def test_decide_chapter_routes_to_ch05(self):
        product = _make_product(name="bone meal powder", processing_state="")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 5)


# ========================================================================
# CHAPTER 06 — LIVE PLANTS, CUT FLOWERS
# ========================================================================

class TestChapter06Tree(unittest.TestCase):

    def test_tulip_bulb_0601(self):
        product = _make_product(name="פקעת צבעוני", essence="tulip bulb",
                                processing_state="live")
        result = _decide_chapter_06(product)
        self.assertEqual(result["chapter"], 6)
        self.assertEqual(result["candidates"][0]["heading"], "06.01")

    def test_cut_roses_0603(self):
        product = _make_product(name="ורדים חתוכים", essence="cut roses bouquet",
                                processing_state="fresh")
        result = _decide_chapter_06(product)
        self.assertEqual(result["candidates"][0]["heading"], "06.03")

    def test_foliage_0604(self):
        product = _make_product(name="decorative fern foliage",
                                essence="ornamental foliage")
        result = _decide_chapter_06(product)
        self.assertEqual(result["candidates"][0]["heading"], "06.04")

    def test_tree_seedling_0602(self):
        product = _make_product(name="שתיל עץ זית", essence="olive tree seedling",
                                processing_state="live")
        result = _decide_chapter_06(product)
        self.assertEqual(result["candidates"][0]["heading"], "06.02")

    def test_artificial_flower_redirect_ch67(self):
        product = _make_product(name="artificial plastic flowers",
                                essence="artificial flower")
        result = _decide_chapter_06(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 67)

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_06_candidate("tulip bulb"))
        self.assertTrue(_is_chapter_06_candidate("ורדים"))
        self.assertFalse(_is_chapter_06_candidate("steel pipes"))


# ========================================================================
# CHAPTER 07 — VEGETABLES
# ========================================================================

class TestChapter07Tree(unittest.TestCase):

    def test_fresh_potatoes_0701(self):
        product = _make_product(name="תפוח אדמה טרי", essence="fresh potatoes",
                                processing_state="fresh")
        result = _decide_chapter_07(product)
        self.assertEqual(result["chapter"], 7)
        self.assertEqual(result["candidates"][0]["heading"], "07.01")

    def test_fresh_tomatoes_0702(self):
        product = _make_product(name="עגבניות טריות", essence="fresh tomatoes",
                                processing_state="fresh")
        result = _decide_chapter_07(product)
        self.assertEqual(result["candidates"][0]["heading"], "07.02")

    def test_frozen_vegetables_0710(self):
        product = _make_product(name="ירקות קפואים", essence="frozen mixed vegetables",
                                processing_state="frozen")
        result = _decide_chapter_07(product)
        self.assertEqual(result["candidates"][0]["heading"], "07.10")

    def test_dried_lentils_0713(self):
        product = _make_product(name="עדשים יבשות", essence="dried lentils",
                                processing_state="dried")
        result = _decide_chapter_07(product)
        self.assertEqual(result["candidates"][0]["heading"], "07.13")

    def test_pickled_cucumbers_redirect_ch20(self):
        product = _make_product(name="מלפפון חמוץ", essence="pickled cucumbers",
                                processing_state="")
        result = _decide_chapter_07(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 20)

    def test_garlic_0703(self):
        product = _make_product(name="fresh garlic", processing_state="fresh")
        result = _decide_chapter_07(product)
        self.assertEqual(result["candidates"][0]["heading"], "07.03")

    def test_broccoli_0704(self):
        product = _make_product(name="ברוקולי טרי", processing_state="fresh")
        result = _decide_chapter_07(product)
        self.assertEqual(result["candidates"][0]["heading"], "07.04")


# ========================================================================
# CHAPTER 08 — FRUIT AND NUTS
# ========================================================================

class TestChapter08Tree(unittest.TestCase):

    def test_fresh_oranges_0805(self):
        product = _make_product(name="תפוזים טריים", essence="fresh oranges",
                                processing_state="fresh")
        result = _decide_chapter_08(product)
        self.assertEqual(result["chapter"], 8)
        self.assertEqual(result["candidates"][0]["heading"], "08.05")

    def test_bananas_0803(self):
        product = _make_product(name="בננות", essence="bananas",
                                processing_state="fresh")
        result = _decide_chapter_08(product)
        self.assertEqual(result["candidates"][0]["heading"], "08.03")

    def test_almonds_0802(self):
        product = _make_product(name="שקדים", essence="almonds",
                                processing_state="")
        result = _decide_chapter_08(product)
        self.assertEqual(result["candidates"][0]["heading"], "08.02")

    def test_frozen_strawberries_0811(self):
        product = _make_product(name="תותים קפואים", essence="frozen strawberries",
                                processing_state="frozen")
        result = _decide_chapter_08(product)
        self.assertEqual(result["candidates"][0]["heading"], "08.11")

    def test_raisins_dried_grapes_0806(self):
        product = _make_product(name="צימוקים", essence="raisins dried grapes",
                                processing_state="dried")
        result = _decide_chapter_08(product)
        self.assertEqual(result["candidates"][0]["heading"], "08.06")

    def test_jam_redirect_ch20(self):
        product = _make_product(name="ריבת תות", essence="strawberry jam",
                                processing_state="")
        result = _decide_chapter_08(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 20)

    def test_apples_0808(self):
        product = _make_product(name="תפוחים טריים", essence="fresh apples",
                                processing_state="fresh")
        result = _decide_chapter_08(product)
        self.assertEqual(result["candidates"][0]["heading"], "08.08")


# ========================================================================
# CHAPTER 09 — COFFEE, TEA, SPICES
# ========================================================================

class TestChapter09Tree(unittest.TestCase):

    def test_coffee_beans_0901(self):
        product = _make_product(name="פולי קפה ירוקים", essence="green coffee beans",
                                processing_state="")
        result = _decide_chapter_09(product)
        self.assertEqual(result["chapter"], 9)
        self.assertEqual(result["candidates"][0]["heading"], "09.01")

    def test_green_tea_0902(self):
        product = _make_product(name="תה ירוק", essence="green tea leaves",
                                processing_state="dried")
        result = _decide_chapter_09(product)
        self.assertEqual(result["candidates"][0]["heading"], "09.02")

    def test_black_pepper_0904(self):
        product = _make_product(name="פלפל שחור", essence="black peppercorns",
                                processing_state="dried")
        result = _decide_chapter_09(product)
        self.assertEqual(result["candidates"][0]["heading"], "09.04")

    def test_cinnamon_0906(self):
        product = _make_product(name="קינמון טחון", essence="ground cinnamon",
                                processing_state="")
        result = _decide_chapter_09(product)
        self.assertEqual(result["candidates"][0]["heading"], "09.06")

    def test_turmeric_0910(self):
        product = _make_product(name="כורכום", essence="turmeric powder",
                                processing_state="")
        result = _decide_chapter_09(product)
        self.assertEqual(result["candidates"][0]["heading"], "09.10")

    def test_coffee_beverage_mix_redirect_ch21(self):
        product = _make_product(name="instant coffee beverage mix",
                                essence="coffee drink blend with milk")
        result = _decide_chapter_09(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 21)


# ========================================================================
# CHAPTER 10 — CEREALS
# ========================================================================

class TestChapter10Tree(unittest.TestCase):

    def test_wheat_1001(self):
        product = _make_product(name="חיטה", essence="wheat grain",
                                processing_state="")
        result = _decide_chapter_10(product)
        self.assertEqual(result["chapter"], 10)
        self.assertEqual(result["candidates"][0]["heading"], "10.01")

    def test_rice_1006(self):
        product = _make_product(name="אורז בסמטי", essence="basmati rice",
                                processing_state="")
        result = _decide_chapter_10(product)
        self.assertEqual(result["candidates"][0]["heading"], "10.06")

    def test_corn_1005(self):
        product = _make_product(name="תירס", essence="maize corn grain",
                                processing_state="")
        result = _decide_chapter_10(product)
        self.assertEqual(result["candidates"][0]["heading"], "10.05")

    def test_quinoa_1008(self):
        product = _make_product(name="קינואה", essence="quinoa seeds",
                                processing_state="")
        result = _decide_chapter_10(product)
        self.assertEqual(result["candidates"][0]["heading"], "10.08")

    def test_wheat_flour_redirect_ch11(self):
        product = _make_product(name="קמח חיטה", essence="wheat flour",
                                processing_state="")
        result = _decide_chapter_10(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 11)


# ========================================================================
# CHAPTER 11 — MILLING PRODUCTS
# ========================================================================

class TestChapter11Tree(unittest.TestCase):

    def test_wheat_flour_1101(self):
        product = _make_product(name="wheat flour", essence="wheat flour white",
                                processing_state="")
        result = _decide_chapter_11(product)
        self.assertEqual(result["chapter"], 11)
        self.assertEqual(result["candidates"][0]["heading"], "11.01")

    def test_rice_flour_1102(self):
        product = _make_product(name="rice flour", essence="rice flour",
                                processing_state="")
        result = _decide_chapter_11(product)
        self.assertEqual(result["candidates"][0]["heading"], "11.02")

    def test_corn_starch_1108(self):
        product = _make_product(name="עמילן תירס", essence="corn starch",
                                processing_state="")
        result = _decide_chapter_11(product)
        self.assertEqual(result["candidates"][0]["heading"], "11.08")

    def test_malt_1107(self):
        product = _make_product(name="לתת שעורה", essence="barley malt",
                                processing_state="")
        result = _decide_chapter_11(product)
        self.assertEqual(result["candidates"][0]["heading"], "11.07")

    def test_wheat_gluten_1109(self):
        product = _make_product(name="גלוטן חיטה", essence="wheat gluten",
                                processing_state="")
        result = _decide_chapter_11(product)
        self.assertEqual(result["candidates"][0]["heading"], "11.09")


# ========================================================================
# CHAPTER 12 — OIL SEEDS
# ========================================================================

class TestChapter12Tree(unittest.TestCase):

    def test_soybeans_1201(self):
        product = _make_product(name="סויה", essence="soya beans",
                                processing_state="")
        result = _decide_chapter_12(product)
        self.assertEqual(result["chapter"], 12)
        self.assertEqual(result["candidates"][0]["heading"], "12.01")

    def test_sunflower_seeds_1206(self):
        product = _make_product(name="גרעיני חמנייה", essence="sunflower seeds",
                                processing_state="")
        result = _decide_chapter_12(product)
        self.assertEqual(result["candidates"][0]["heading"], "12.06")

    def test_sesame_seeds_1207(self):
        product = _make_product(name="שומשום", essence="sesame seeds",
                                processing_state="")
        result = _decide_chapter_12(product)
        self.assertEqual(result["candidates"][0]["heading"], "12.07")

    def test_medicinal_herbs_1211(self):
        product = _make_product(name="צמח מרפא", essence="medicinal plant herb",
                                processing_state="dried")
        result = _decide_chapter_12(product)
        self.assertEqual(result["candidates"][0]["heading"], "12.11")

    def test_soybean_oil_redirect_ch15(self):
        product = _make_product(name="שמן סויה", essence="soybean oil crude",
                                processing_state="")
        result = _decide_chapter_12(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 15)

    def test_hay_fodder_1214(self):
        product = _make_product(name="חציר מספוא", essence="hay fodder",
                                processing_state="dried")
        result = _decide_chapter_12(product)
        self.assertEqual(result["candidates"][0]["heading"], "12.14")


# ========================================================================
# CHAPTER 13 — LAC, GUMS, RESINS
# ========================================================================

class TestChapter13Tree(unittest.TestCase):

    def test_gum_arabic_1301(self):
        product = _make_product(name="גומי ערבי", essence="gum arabic",
                                processing_state="")
        result = _decide_chapter_13(product)
        self.assertEqual(result["chapter"], 13)
        self.assertEqual(result["candidates"][0]["heading"], "13.01")

    def test_shellac_1301(self):
        product = _make_product(name="shellac", essence="lac resin",
                                processing_state="")
        result = _decide_chapter_13(product)
        self.assertEqual(result["candidates"][0]["heading"], "13.01")

    def test_pectin_1302(self):
        product = _make_product(name="פקטין", essence="pectin food grade",
                                processing_state="")
        result = _decide_chapter_13(product)
        self.assertEqual(result["candidates"][0]["heading"], "13.02")

    def test_agar_agar_1302(self):
        product = _make_product(name="agar agar", essence="agar seaweed extract",
                                processing_state="")
        result = _decide_chapter_13(product)
        self.assertEqual(result["candidates"][0]["heading"], "13.02")

    def test_plant_extract_1302(self):
        product = _make_product(name="aloe plant extract", essence="aloe vera extract",
                                processing_state="")
        result = _decide_chapter_13(product)
        self.assertEqual(result["candidates"][0]["heading"], "13.02")


# ========================================================================
# CHAPTER 14 — VEGETABLE PLAITING MATERIALS
# ========================================================================

class TestChapter14Tree(unittest.TestCase):

    def test_bamboo_1401(self):
        product = _make_product(name="במבוק גולמי", essence="raw bamboo",
                                processing_state="")
        result = _decide_chapter_14(product)
        self.assertEqual(result["chapter"], 14)
        self.assertEqual(result["candidates"][0]["heading"], "14.01")

    def test_rattan_1401(self):
        product = _make_product(name="rattan raw", essence="rattan cane",
                                processing_state="")
        result = _decide_chapter_14(product)
        self.assertEqual(result["candidates"][0]["heading"], "14.01")

    def test_kapok_1404(self):
        product = _make_product(name="kapok fiber", essence="kapok vegetable fiber",
                                processing_state="")
        result = _decide_chapter_14(product)
        self.assertEqual(result["candidates"][0]["heading"], "14.04")

    def test_coir_1404(self):
        product = _make_product(name="coir coconut fiber",
                                essence="coconut coir")
        result = _decide_chapter_14(product)
        self.assertEqual(result["candidates"][0]["heading"], "14.04")

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_14_candidate("bamboo"))
        self.assertTrue(_is_chapter_14_candidate("rattan"))
        self.assertTrue(_is_chapter_14_candidate("kapok"))
        self.assertFalse(_is_chapter_14_candidate("steel"))


# ========================================================================
# CHAPTER 15 — ANIMAL/VEGETABLE FATS AND OILS
# ========================================================================

class TestChapter15Tree(unittest.TestCase):

    def test_olive_oil_1509(self):
        product = _make_product(name="שמן זית כתית", essence="virgin olive oil",
                                processing_state="")
        result = _decide_chapter_15(product)
        self.assertEqual(result["chapter"], 15)
        self.assertEqual(result["candidates"][0]["heading"], "15.09")

    def test_palm_oil_1511(self):
        product = _make_product(name="שמן דקל", essence="crude palm oil",
                                processing_state="")
        result = _decide_chapter_15(product)
        self.assertEqual(result["candidates"][0]["heading"], "15.11")

    def test_sunflower_oil_1512(self):
        product = _make_product(name="שמן חמנייה", essence="refined sunflower oil",
                                processing_state="")
        result = _decide_chapter_15(product)
        self.assertEqual(result["candidates"][0]["heading"], "15.12")

    def test_margarine_1517(self):
        product = _make_product(name="מרגרינה", essence="margarine spread",
                                processing_state="")
        result = _decide_chapter_15(product)
        self.assertEqual(result["candidates"][0]["heading"], "15.17")

    def test_beeswax_1521(self):
        product = _make_product(name="שעוות דבורים", essence="natural beeswax",
                                processing_state="")
        result = _decide_chapter_15(product)
        self.assertEqual(result["candidates"][0]["heading"], "15.21")

    def test_hydrogenated_oil_1516(self):
        product = _make_product(name="hydrogenated vegetable oil",
                                essence="hydrogenated fat", processing_state="")
        result = _decide_chapter_15(product)
        self.assertEqual(result["candidates"][0]["heading"], "15.16")

    def test_lard_animal_fat_1501(self):
        product = _make_product(name="lard pig fat", essence="rendered lard",
                                processing_state="")
        result = _decide_chapter_15(product)
        self.assertEqual(result["candidates"][0]["heading"], "15.01")


# ========================================================================
# CHAPTER 16 — PREPARATIONS OF MEAT/FISH
# ========================================================================

class TestChapter16ProductType(unittest.TestCase):

    def test_sausage(self):
        self.assertEqual(_detect_ch16_product_type("beef sausage"), "sausage")

    def test_sausage_hebrew(self):
        self.assertEqual(_detect_ch16_product_type("נקניק בקר"), "sausage")

    def test_canned_tuna(self):
        self.assertEqual(_detect_ch16_product_type("canned tuna in oil"), "prepared_fish")

    def test_corned_beef(self):
        self.assertEqual(_detect_ch16_product_type("corned beef"), "prepared_meat")

    def test_caviar(self):
        self.assertEqual(_detect_ch16_product_type("Russian caviar"), "caviar")


class TestChapter16Tree(unittest.TestCase):

    def test_sausage_1601(self):
        product = _make_product(name="נקניק עוף", essence="chicken sausage")
        result = _decide_chapter_16(product)
        self.assertEqual(result["chapter"], 16)
        self.assertEqual(result["candidates"][0]["heading"], "16.01")

    def test_canned_fish_1604(self):
        product = _make_product(name="שימורי טונה בשמן", essence="canned tuna in oil")
        result = _decide_chapter_16(product)
        self.assertEqual(result["candidates"][0]["heading"], "16.04")

    def test_caviar_1604(self):
        product = _make_product(name="קוויאר", essence="caviar")
        result = _decide_chapter_16(product)
        self.assertEqual(result["candidates"][0]["heading"], "16.04")

    def test_prepared_shrimp_1605(self):
        product = _make_product(name="canned shrimp", essence="prepared shrimp")
        result = _decide_chapter_16(product)
        self.assertEqual(result["candidates"][0]["heading"], "16.05")

    def test_corned_beef_1602(self):
        product = _make_product(name="corned beef", essence="preserved beef")
        result = _decide_chapter_16(product)
        self.assertEqual(result["candidates"][0]["heading"], "16.02")

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_16_candidate("beef sausage"))
        self.assertTrue(_is_chapter_16_candidate("שימורי דג"))
        self.assertFalse(_is_chapter_16_candidate("fresh salmon"))


# ========================================================================
# CHAPTER 17 — SUGARS AND CONFECTIONERY
# ========================================================================

class TestChapter17Tree(unittest.TestCase):

    def test_cane_sugar_1701(self):
        product = _make_product(name="סוכר לבן", essence="refined white cane sugar")
        result = _decide_chapter_17(product)
        self.assertEqual(result["chapter"], 17)
        self.assertEqual(result["candidates"][0]["heading"], "17.01")

    def test_glucose_1702(self):
        product = _make_product(name="glucose syrup", essence="glucose")
        result = _decide_chapter_17(product)
        self.assertEqual(result["candidates"][0]["heading"], "17.02")

    def test_molasses_1703(self):
        product = _make_product(name="מולסה", essence="cane molasses")
        result = _decide_chapter_17(product)
        self.assertEqual(result["candidates"][0]["heading"], "17.03")

    def test_candy_1704(self):
        product = _make_product(name="סוכריות גומי", essence="gummy candy")
        result = _decide_chapter_17(product)
        self.assertEqual(result["candidates"][0]["heading"], "17.04")

    def test_chocolate_candy_redirect_ch18(self):
        """Chocolate confectionery → redirect to Ch.18."""
        product = _make_product(name="chocolate candy", essence="chocolate confectionery")
        result = _decide_chapter_17(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 18)

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_17_candidate("white sugar"))
        self.assertTrue(_is_chapter_17_candidate("סוכריות"))
        self.assertFalse(_is_chapter_17_candidate("steel pipes"))


# ========================================================================
# CHAPTER 18 — COCOA AND CHOCOLATE
# ========================================================================

class TestChapter18Tree(unittest.TestCase):

    def test_cocoa_beans_1801(self):
        product = _make_product(name="cocoa beans raw", essence="raw cocoa beans")
        result = _decide_chapter_18(product)
        self.assertEqual(result["chapter"], 18)
        self.assertEqual(result["candidates"][0]["heading"], "18.01")

    def test_cocoa_butter_1804(self):
        product = _make_product(name="חמאת קקאו", essence="cocoa butter")
        result = _decide_chapter_18(product)
        self.assertEqual(result["candidates"][0]["heading"], "18.04")

    def test_cocoa_powder_1805(self):
        product = _make_product(name="אבקת קקאו", essence="unsweetened cocoa powder")
        result = _decide_chapter_18(product)
        self.assertEqual(result["candidates"][0]["heading"], "18.05")

    def test_chocolate_bar_1806(self):
        product = _make_product(name="טבלת שוקולד חלב", essence="milk chocolate bar")
        result = _decide_chapter_18(product)
        self.assertEqual(result["candidates"][0]["heading"], "18.06")

    def test_cocoa_paste_1803(self):
        product = _make_product(name="cocoa paste", essence="cocoa liquor")
        result = _decide_chapter_18(product)
        self.assertEqual(result["candidates"][0]["heading"], "18.03")

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_18_candidate("chocolate bar"))
        self.assertTrue(_is_chapter_18_candidate("אבקת קקאו"))
        self.assertFalse(_is_chapter_18_candidate("sugar candy"))


# ========================================================================
# CHAPTER 19 — CEREAL/FLOUR PREPARATIONS
# ========================================================================

class TestChapter19Tree(unittest.TestCase):

    def test_pasta_1902(self):
        product = _make_product(name="ספגטי", essence="spaghetti pasta")
        result = _decide_chapter_19(product)
        self.assertEqual(result["chapter"], 19)
        self.assertEqual(result["candidates"][0]["heading"], "19.02")

    def test_bread_1905(self):
        product = _make_product(name="לחם חיטה", essence="wheat bread")
        result = _decide_chapter_19(product)
        self.assertEqual(result["candidates"][0]["heading"], "19.05")

    def test_cornflakes_1904(self):
        product = _make_product(name="קורנפלקס", essence="corn flakes breakfast cereal")
        result = _decide_chapter_19(product)
        self.assertEqual(result["candidates"][0]["heading"], "19.04")

    def test_croissant_1905(self):
        product = _make_product(name="croissant", essence="butter croissant pastry")
        result = _decide_chapter_19(product)
        self.assertEqual(result["candidates"][0]["heading"], "19.05")

    def test_pizza_1905(self):
        product = _make_product(name="פיצה קפואה", essence="frozen pizza")
        result = _decide_chapter_19(product)
        self.assertEqual(result["candidates"][0]["heading"], "19.05")

    def test_baby_food_1901(self):
        product = _make_product(name="דייסת תינוקות", essence="infant cereal")
        result = _decide_chapter_19(product)
        self.assertEqual(result["candidates"][0]["heading"], "19.01")

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_19_candidate("spaghetti pasta"))
        self.assertTrue(_is_chapter_19_candidate("לחם"))
        self.assertFalse(_is_chapter_19_candidate("fresh milk"))


# ========================================================================
# CHAPTER 20 — PREPARATIONS OF VEGETABLES/FRUIT
# ========================================================================

class TestChapter20Tree(unittest.TestCase):

    def test_tomato_paste_2002(self):
        product = _make_product(name="רסק עגבניות", essence="tomato paste")
        result = _decide_chapter_20(product)
        self.assertEqual(result["chapter"], 20)
        self.assertEqual(result["candidates"][0]["heading"], "20.02")

    def test_orange_juice_2009(self):
        product = _make_product(name="מיץ תפוזים", essence="orange juice")
        result = _decide_chapter_20(product)
        self.assertEqual(result["candidates"][0]["heading"], "20.09")

    def test_jam_2007(self):
        product = _make_product(name="ריבת תות", essence="strawberry jam")
        result = _decide_chapter_20(product)
        self.assertEqual(result["candidates"][0]["heading"], "20.07")

    def test_pickled_cucumber_2001(self):
        product = _make_product(name="מלפפון חמוץ", essence="pickled cucumber")
        result = _decide_chapter_20(product)
        self.assertEqual(result["candidates"][0]["heading"], "20.01")

    def test_peanut_butter_2008(self):
        product = _make_product(name="חמאת בוטנים", essence="peanut butter")
        result = _decide_chapter_20(product)
        self.assertEqual(result["candidates"][0]["heading"], "20.08")

    def test_frozen_vegetables_2004(self):
        product = _make_product(name="frozen vegetables mix", essence="frozen peas and corn")
        result = _decide_chapter_20(product)
        self.assertEqual(result["candidates"][0]["heading"], "20.04")

    def test_canned_corn_2005(self):
        product = _make_product(name="שימורי תירס", essence="canned corn")
        result = _decide_chapter_20(product)
        self.assertEqual(result["candidates"][0]["heading"], "20.05")

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_20_candidate("tomato paste"))
        self.assertTrue(_is_chapter_20_candidate("מיץ תפוזים"))
        self.assertFalse(_is_chapter_20_candidate("fresh tomato"))


# ========================================================================
# CHAPTER 21 — MISCELLANEOUS FOOD PREPARATIONS
# ========================================================================

class TestChapter21Tree(unittest.TestCase):

    def test_ice_cream_2105(self):
        product = _make_product(name="גלידה וניל", essence="vanilla ice cream")
        result = _decide_chapter_21(product)
        self.assertEqual(result["chapter"], 21)
        self.assertEqual(result["candidates"][0]["heading"], "21.05")

    def test_soy_sauce_2103(self):
        product = _make_product(name="רוטב סויה", essence="soy sauce")
        result = _decide_chapter_21(product)
        self.assertEqual(result["candidates"][0]["heading"], "21.03")

    def test_soup_2104(self):
        product = _make_product(name="מרק עוף מוכן", essence="chicken soup")
        result = _decide_chapter_21(product)
        self.assertEqual(result["candidates"][0]["heading"], "21.04")

    def test_yeast_2102(self):
        product = _make_product(name="שמרים יבשים", essence="dry yeast")
        result = _decide_chapter_21(product)
        self.assertEqual(result["candidates"][0]["heading"], "21.02")

    def test_instant_coffee_2101(self):
        product = _make_product(name="קפה נמס", essence="instant coffee")
        result = _decide_chapter_21(product)
        self.assertEqual(result["candidates"][0]["heading"], "21.01")

    def test_protein_powder_2106(self):
        product = _make_product(name="whey protein concentrate", essence="protein supplement")
        result = _decide_chapter_21(product)
        self.assertEqual(result["candidates"][0]["heading"], "21.06")

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_21_candidate("ice cream"))
        self.assertTrue(_is_chapter_21_candidate("רוטב סויה"))
        self.assertFalse(_is_chapter_21_candidate("fresh salmon"))


# ========================================================================
# CHAPTER 22 — BEVERAGES, SPIRITS, VINEGAR
# ========================================================================

class TestChapter22Tree(unittest.TestCase):

    def test_mineral_water_2201(self):
        product = _make_product(name="מים מינרליים", essence="mineral water")
        result = _decide_chapter_22(product)
        self.assertEqual(result["chapter"], 22)
        self.assertEqual(result["candidates"][0]["heading"], "22.01")

    def test_cola_2202(self):
        product = _make_product(name="cola soft drink", essence="carbonated cola beverage")
        result = _decide_chapter_22(product)
        self.assertEqual(result["candidates"][0]["heading"], "22.02")

    def test_beer_2203(self):
        product = _make_product(name="בירה לאגר", essence="lager beer")
        result = _decide_chapter_22(product)
        self.assertEqual(result["candidates"][0]["heading"], "22.03")

    def test_wine_2204(self):
        product = _make_product(name="יין אדום", essence="red wine")
        result = _decide_chapter_22(product)
        self.assertEqual(result["candidates"][0]["heading"], "22.04")

    def test_vermouth_2205(self):
        product = _make_product(name="vermouth wine", essence="vermouth")
        result = _decide_chapter_22(product)
        self.assertEqual(result["candidates"][0]["heading"], "22.05")

    def test_vodka_2208(self):
        product = _make_product(name="וודקה", essence="vodka spirit")
        result = _decide_chapter_22(product)
        self.assertEqual(result["candidates"][0]["heading"], "22.08")

    def test_vinegar_2209(self):
        product = _make_product(name="חומץ תפוחים", essence="apple cider vinegar")
        result = _decide_chapter_22(product)
        self.assertEqual(result["candidates"][0]["heading"], "22.09")

    def test_cider_2206(self):
        product = _make_product(name="apple cider", essence="fermented cider")
        result = _decide_chapter_22(product)
        self.assertEqual(result["candidates"][0]["heading"], "22.06")

    def test_juice_redirect_ch20(self):
        """Unfermented fruit juice → redirect Ch.20."""
        product = _make_product(name="apple juice", essence="fresh apple juice")
        result = _decide_chapter_22(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 20)

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_22_candidate("vodka"))
        self.assertTrue(_is_chapter_22_candidate("בירה"))
        self.assertFalse(_is_chapter_22_candidate("fresh milk"))


# ========================================================================
# CHAPTER 23 — FOOD RESIDUES / ANIMAL FEED
# ========================================================================

class TestChapter23Tree(unittest.TestCase):

    def test_dog_food_2309(self):
        product = _make_product(name="מזון כלבים", essence="dry dog food")
        result = _decide_chapter_23(product)
        self.assertEqual(result["chapter"], 23)
        self.assertEqual(result["candidates"][0]["heading"], "23.09")

    def test_soybean_meal_2304(self):
        product = _make_product(name="soybean meal", essence="soya oilcake residue")
        result = _decide_chapter_23(product)
        self.assertEqual(result["candidates"][0]["heading"], "23.04")

    def test_wheat_bran_2302(self):
        product = _make_product(name="סובין חיטה", essence="wheat bran")
        result = _decide_chapter_23(product)
        self.assertEqual(result["candidates"][0]["heading"], "23.02")

    def test_bone_meal_2301(self):
        product = _make_product(name="bone meal", essence="meat and bone meal MBM")
        result = _decide_chapter_23(product)
        self.assertEqual(result["candidates"][0]["heading"], "23.01")

    def test_beet_pulp_2303(self):
        product = _make_product(name="beet pulp", essence="sugar beet pulp residue")
        result = _decide_chapter_23(product)
        self.assertEqual(result["candidates"][0]["heading"], "23.03")

    def test_compound_feed_2309(self):
        product = _make_product(name="compound poultry feed", essence="poultry feed premix")
        result = _decide_chapter_23(product)
        self.assertEqual(result["candidates"][0]["heading"], "23.09")

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_23_candidate("dog food"))
        self.assertTrue(_is_chapter_23_candidate("סובין חיטה"))
        self.assertFalse(_is_chapter_23_candidate("fresh wheat"))


# ========================================================================
# CHAPTER 24 — TOBACCO
# ========================================================================

class TestChapter24Tree(unittest.TestCase):

    def test_cigarettes_2402(self):
        product = _make_product(name="סיגריות", essence="cigarettes")
        result = _decide_chapter_24(product)
        self.assertEqual(result["chapter"], 24)
        self.assertEqual(result["candidates"][0]["heading"], "24.02")

    def test_cigars_2402(self):
        product = _make_product(name="Cuban cigar", essence="hand-rolled cigar")
        result = _decide_chapter_24(product)
        self.assertEqual(result["candidates"][0]["heading"], "24.02")

    def test_tobacco_leaf_2401(self):
        product = _make_product(name="tobacco leaves raw", essence="unmanufactured tobacco leaf")
        result = _decide_chapter_24(product)
        self.assertEqual(result["candidates"][0]["heading"], "24.01")

    def test_pipe_tobacco_2403(self):
        product = _make_product(name="pipe tobacco", essence="smoking tobacco for pipe")
        result = _decide_chapter_24(product)
        self.assertEqual(result["candidates"][0]["heading"], "24.03")

    def test_heated_tobacco_2403(self):
        product = _make_product(name="heated tobacco sticks", essence="heat not burn tobacco product")
        result = _decide_chapter_24(product)
        self.assertEqual(result["candidates"][0]["heading"], "24.03")

    def test_vape_liquid_2404(self):
        product = _make_product(name="e-liquid vape juice", essence="nicotine vape liquid")
        result = _decide_chapter_24(product)
        self.assertEqual(result["candidates"][0]["heading"], "24.04")

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_24_candidate("cigarettes"))
        self.assertTrue(_is_chapter_24_candidate("טבק"))
        self.assertFalse(_is_chapter_24_candidate("fresh salmon"))


# ========================================================================
# CHAPTERS 16-24 — PUBLIC API INTEGRATION
# ========================================================================

class TestChapters16to24Integration(unittest.TestCase):

    def test_available_chapters_includes_16_to_24(self):
        chapters = available_chapters()
        for ch in range(16, 25):
            self.assertIn(ch, chapters)

    def test_decide_chapter_detects_sausage(self):
        product = _make_product(name="beef sausage salami", essence="salami")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 16)

    def test_decide_chapter_detects_chocolate(self):
        product = _make_product(name="dark chocolate bar", essence="chocolate praline")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 18)

    def test_decide_chapter_detects_beer(self):
        product = _make_product(name="imported beer bottles", essence="lager beer 330ml")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 22)

    def test_decide_chapter_detects_cigarettes(self):
        product = _make_product(name="סיגריות", essence="cigarettes")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 24)


# ========================================================================
# CHAPTER 25 — SALT, SULPHUR, EARTHS, STONE, CEMENT
# ========================================================================

class TestChapter25(unittest.TestCase):

    def test_salt_routes_to_2501(self):
        product = _make_product(name="sea salt", essence="sodium chloride")
        result = _decide_chapter_25(product)
        self.assertEqual(result["chapter"], 25)
        self.assertTrue(any("25.01" in c["heading"] for c in result["candidates"]))

    def test_sulphur_routes_to_2503(self):
        product = _make_product(name="crude sulphur", essence="elemental sulphur")
        result = _decide_chapter_25(product)
        self.assertEqual(result["chapter"], 25)
        self.assertTrue(any("25.03" in c["heading"] for c in result["candidates"]))

    def test_sand_routes_to_2505(self):
        product = _make_product(name="quartz sand", essence="natural sand silica")
        result = _decide_chapter_25(product)
        self.assertEqual(result["chapter"], 25)
        self.assertTrue(any("25.05" in c["heading"] for c in result["candidates"]))

    def test_cement_routes_to_2523(self):
        product = _make_product(name="portland cement", essence="cement clinker")
        result = _decide_chapter_25(product)
        self.assertEqual(result["chapter"], 25)
        self.assertTrue(any("25.23" in c["heading"] for c in result["candidates"]))

    def test_marble_routes_to_2515(self):
        product = _make_product(name="marble blocks", essence="marble stone")
        result = _decide_chapter_25(product)
        self.assertEqual(result["chapter"], 25)
        self.assertTrue(any("25.15" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_25_candidate("sea salt"))
        self.assertTrue(_is_chapter_25_candidate("מלט פורטלנד"))
        self.assertFalse(_is_chapter_25_candidate("cotton fabric"))


# ========================================================================
# CHAPTER 26 — ORES, SLAG, ASH
# ========================================================================

class TestChapter26(unittest.TestCase):

    def test_iron_ore_routes_to_2601(self):
        product = _make_product(name="iron ore concentrate", essence="iron ore")
        result = _decide_chapter_26(product)
        self.assertEqual(result["chapter"], 26)
        self.assertTrue(any("26.01" in c["heading"] for c in result["candidates"]))

    def test_copper_ore_routes_to_2603(self):
        product = _make_product(name="copper ore", essence="copper concentrate")
        result = _decide_chapter_26(product)
        self.assertEqual(result["chapter"], 26)
        self.assertTrue(any("26.03" in c["heading"] for c in result["candidates"]))

    def test_slag_routes_to_2618_2619_2620_2621(self):
        product = _make_product(name="granulated slag", essence="slag from smelting")
        result = _decide_chapter_26(product)
        self.assertEqual(result["chapter"], 26)
        self.assertTrue(len(result["candidates"]) >= 1)

    def test_ash_routes_correctly(self):
        product = _make_product(name="fly ash", essence="coal ash residue")
        result = _decide_chapter_26(product)
        self.assertEqual(result["chapter"], 26)

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_26_candidate("iron ore"))
        self.assertTrue(_is_chapter_26_candidate("עפרת נחושת"))
        self.assertFalse(_is_chapter_26_candidate("orange juice"))


# ========================================================================
# CHAPTER 27 — MINERAL FUELS, OILS, BITUMINOUS SUBSTANCES
# ========================================================================

class TestChapter27(unittest.TestCase):

    def test_crude_oil_routes_to_2709(self):
        product = _make_product(name="crude petroleum oil", essence="crude oil")
        result = _decide_chapter_27(product)
        self.assertEqual(result["chapter"], 27)
        self.assertTrue(any("27.09" in c["heading"] for c in result["candidates"]))

    def test_coal_routes_to_2701(self):
        product = _make_product(name="bituminous coal", essence="coal anthracite")
        result = _decide_chapter_27(product)
        self.assertEqual(result["chapter"], 27)
        self.assertTrue(any("27.01" in c["heading"] for c in result["candidates"]))

    def test_natural_gas_routes_to_2711(self):
        product = _make_product(name="liquefied natural gas LNG", essence="natural gas")
        result = _decide_chapter_27(product)
        self.assertEqual(result["chapter"], 27)
        self.assertTrue(any("27.11" in c["heading"] for c in result["candidates"]))

    def test_diesel_routes_to_2710(self):
        product = _make_product(name="diesel fuel", essence="petroleum diesel")
        result = _decide_chapter_27(product)
        self.assertEqual(result["chapter"], 27)
        self.assertTrue(any("27.10" in c["heading"] for c in result["candidates"]))

    def test_bitumen_routes_to_2713_2715(self):
        product = _make_product(name="petroleum bitumen asphalt", essence="bitumen")
        result = _decide_chapter_27(product)
        self.assertEqual(result["chapter"], 27)
        self.assertTrue(len(result["candidates"]) >= 1)

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_27_candidate("crude petroleum"))
        self.assertTrue(_is_chapter_27_candidate("פחם אבן"))
        self.assertFalse(_is_chapter_27_candidate("fresh apples"))


# ========================================================================
# CHAPTER 28 — INORGANIC CHEMICALS
# ========================================================================

class TestChapter28(unittest.TestCase):

    def test_hydrochloric_acid_routes(self):
        product = _make_product(name="hydrochloric acid", essence="hydrogen chloride")
        result = _decide_chapter_28(product)
        self.assertEqual(result["chapter"], 28)
        self.assertTrue(len(result["candidates"]) >= 1)

    def test_sodium_hydroxide_routes(self):
        product = _make_product(name="sodium hydroxide", essence="caustic soda NaOH")
        result = _decide_chapter_28(product)
        self.assertEqual(result["chapter"], 28)

    def test_hydrogen_peroxide_routes(self):
        product = _make_product(name="hydrogen peroxide", essence="H2O2")
        result = _decide_chapter_28(product)
        self.assertEqual(result["chapter"], 28)

    def test_titanium_dioxide_routes(self):
        product = _make_product(name="titanium dioxide", essence="TiO2 pigment")
        result = _decide_chapter_28(product)
        self.assertEqual(result["chapter"], 28)

    def test_rare_earth_routes(self):
        product = _make_product(name="cerium oxide rare earth", essence="rare earth compound")
        result = _decide_chapter_28(product)
        self.assertEqual(result["chapter"], 28)

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_28_candidate("hydrochloric acid"))
        self.assertTrue(_is_chapter_28_candidate("תחמוצת טיטניום"))
        self.assertFalse(_is_chapter_28_candidate("wooden table"))


# ========================================================================
# CHAPTER 29 — ORGANIC CHEMICALS
# ========================================================================

class TestChapter29(unittest.TestCase):

    def test_methanol_routes(self):
        product = _make_product(name="methanol", essence="methyl alcohol CH3OH")
        result = _decide_chapter_29(product)
        self.assertEqual(result["chapter"], 29)

    def test_acetic_acid_routes(self):
        product = _make_product(name="acetic acid", essence="ethanoic acid")
        result = _decide_chapter_29(product)
        self.assertEqual(result["chapter"], 29)

    def test_acetone_routes(self):
        product = _make_product(name="acetone", essence="propanone ketone")
        result = _decide_chapter_29(product)
        self.assertEqual(result["chapter"], 29)

    def test_citric_acid_routes(self):
        product = _make_product(name="citric acid", essence="citric acid anhydrous")
        result = _decide_chapter_29(product)
        self.assertEqual(result["chapter"], 29)

    def test_amino_acid_routes(self):
        product = _make_product(name="lysine amino acid", essence="amino acid")
        result = _decide_chapter_29(product)
        self.assertEqual(result["chapter"], 29)

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_29_candidate("methanol"))
        self.assertTrue(_is_chapter_29_candidate("citric acid"))
        self.assertFalse(_is_chapter_29_candidate("live horses"))


# ========================================================================
# CHAPTER 30 — PHARMACEUTICALS
# ========================================================================

class TestChapter30(unittest.TestCase):

    def test_medicine_tablet_routes_to_3004(self):
        product = _make_product(name="paracetamol tablets 500mg", essence="medicine dosage")
        result = _decide_chapter_30(product)
        self.assertEqual(result["chapter"], 30)
        self.assertTrue(any("30.04" in c["heading"] for c in result["candidates"]))

    def test_vaccine_routes_to_3002(self):
        product = _make_product(name="influenza vaccine", essence="vaccine immunological")
        result = _decide_chapter_30(product)
        self.assertEqual(result["chapter"], 30)
        self.assertTrue(any("30.02" in c["heading"] for c in result["candidates"]))

    def test_bandage_routes_to_3005(self):
        product = _make_product(name="sterile adhesive bandage", essence="medical dressing")
        result = _decide_chapter_30(product)
        self.assertEqual(result["chapter"], 30)
        self.assertTrue(any("30.05" in c["heading"] for c in result["candidates"]))

    def test_pharmaceutical_api_routes_to_3003(self):
        product = _make_product(name="amoxicillin bulk pharmaceutical",
                                essence="antibiotic active ingredient not dosed")
        result = _decide_chapter_30(product)
        self.assertEqual(result["chapter"], 30)

    def test_serum_routes_to_3002(self):
        product = _make_product(name="antiserum immunological", essence="serum antitoxin")
        result = _decide_chapter_30(product)
        self.assertEqual(result["chapter"], 30)
        self.assertTrue(any("30.02" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_30_candidate("paracetamol tablets"))
        self.assertTrue(_is_chapter_30_candidate("תרופה"))
        self.assertFalse(_is_chapter_30_candidate("steel pipe"))


# ========================================================================
# CHAPTER 31 — FERTILIZERS
# ========================================================================

class TestChapter31(unittest.TestCase):

    def test_urea_routes_to_3102(self):
        product = _make_product(name="urea fertilizer", essence="nitrogen fertilizer urea")
        result = _decide_chapter_31(product)
        self.assertEqual(result["chapter"], 31)
        self.assertTrue(any("31.02" in c["heading"] for c in result["candidates"]))

    def test_potash_routes_to_3104(self):
        product = _make_product(name="muriate of potash granular",
                                essence="KCl 60%")
        result = _decide_chapter_31(product)
        self.assertEqual(result["chapter"], 31)
        self.assertTrue(any("31.04" in c["heading"] for c in result["candidates"]))

    def test_npk_routes_to_3105(self):
        product = _make_product(name="NPK compound fertilizer 15-15-15",
                                essence="compound fertilizer")
        result = _decide_chapter_31(product)
        self.assertEqual(result["chapter"], 31)
        self.assertTrue(any("31.05" in c["heading"] for c in result["candidates"]))

    def test_phosphate_routes_to_3103(self):
        product = _make_product(name="superphosphate granular",
                                essence="Thomas slag")
        result = _decide_chapter_31(product)
        self.assertEqual(result["chapter"], 31)
        self.assertTrue(any("31.03" in c["heading"] for c in result["candidates"]))

    def test_animal_manure_routes_to_3101(self):
        product = _make_product(name="animal manure guano",
                                essence="organic fertilizer guano")
        result = _decide_chapter_31(product)
        self.assertEqual(result["chapter"], 31)
        self.assertTrue(any("31.01" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_31_candidate("urea fertilizer"))
        self.assertTrue(_is_chapter_31_candidate("דשן"))
        self.assertFalse(_is_chapter_31_candidate("cotton shirt"))


# ========================================================================
# CHAPTER 32 — TANNING, DYES, PAINTS, INKS
# ========================================================================

class TestChapter32(unittest.TestCase):

    def test_paint_routes_to_3208_3209(self):
        product = _make_product(name="acrylic paint coating",
                                essence="paint synthetic polymer")
        result = _decide_chapter_32(product)
        self.assertEqual(result["chapter"], 32)
        self.assertTrue(any("32.08" in c["heading"] or "32.09" in c["heading"]
                            for c in result["candidates"]))

    def test_ink_routes_to_3215(self):
        product = _make_product(name="printing ink", essence="ink pigment")
        result = _decide_chapter_32(product)
        self.assertEqual(result["chapter"], 32)
        self.assertTrue(any("32.15" in c["heading"] for c in result["candidates"]))

    def test_dye_routes_to_3204(self):
        product = _make_product(name="synthetic organic dye",
                                essence="reactive dye colorant")
        result = _decide_chapter_32(product)
        self.assertEqual(result["chapter"], 32)
        self.assertTrue(any("32.04" in c["heading"] for c in result["candidates"]))

    def test_tanning_extract_routes_to_3201(self):
        product = _make_product(name="tanning extract vegetable",
                                essence="tanning extract")
        result = _decide_chapter_32(product)
        self.assertEqual(result["chapter"], 32)
        self.assertTrue(any("32.01" in c["heading"] for c in result["candidates"]))

    def test_varnish_routes(self):
        product = _make_product(name="wood varnish lacquer",
                                essence="varnish coating")
        result = _decide_chapter_32(product)
        self.assertEqual(result["chapter"], 32)

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_32_candidate("acrylic paint"))
        self.assertTrue(_is_chapter_32_candidate("צבע קיר"))
        self.assertFalse(_is_chapter_32_candidate("frozen fish"))


# ========================================================================
# CHAPTER 33 — COSMETICS, ESSENTIAL OILS, PERFUMERY
# ========================================================================

class TestChapter33(unittest.TestCase):

    def test_perfume_routes_to_3303(self):
        product = _make_product(name="eau de parfum", essence="perfume fragrance")
        result = _decide_chapter_33(product)
        self.assertEqual(result["chapter"], 33)
        self.assertTrue(any("33.03" in c["heading"] for c in result["candidates"]))

    def test_shampoo_routes_to_3305(self):
        product = _make_product(name="hair shampoo", essence="shampoo")
        result = _decide_chapter_33(product)
        self.assertEqual(result["chapter"], 33)
        self.assertTrue(any("33.05" in c["heading"] for c in result["candidates"]))

    def test_essential_oil_routes_to_3301(self):
        product = _make_product(name="lavender essential oil", essence="essential oil")
        result = _decide_chapter_33(product)
        self.assertEqual(result["chapter"], 33)
        self.assertTrue(any("33.01" in c["heading"] for c in result["candidates"]))

    def test_toothpaste_routes_to_3306(self):
        product = _make_product(name="fluoride toothpaste", essence="toothpaste dentifrice")
        result = _decide_chapter_33(product)
        self.assertEqual(result["chapter"], 33)
        self.assertTrue(any("33.06" in c["heading"] for c in result["candidates"]))

    def test_skin_cream_routes_to_3304(self):
        product = _make_product(name="face cream moisturizer",
                                essence="skin care cream cosmetic")
        result = _decide_chapter_33(product)
        self.assertEqual(result["chapter"], 33)
        self.assertTrue(any("33.04" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_33_candidate("perfume"))
        self.assertTrue(_is_chapter_33_candidate("שמפו"))
        self.assertFalse(_is_chapter_33_candidate("iron ore"))


# ========================================================================
# CHAPTER 34 — SOAP, DETERGENT, WAX, CANDLES
# ========================================================================

class TestChapter34(unittest.TestCase):

    def test_soap_routes_to_3401(self):
        product = _make_product(name="toilet soap bar", essence="soap")
        result = _decide_chapter_34(product)
        self.assertEqual(result["chapter"], 34)
        self.assertTrue(any("34.01" in c["heading"] for c in result["candidates"]))

    def test_detergent_routes_to_3402(self):
        product = _make_product(name="laundry detergent surfactant",
                                essence="washing detergent")
        result = _decide_chapter_34(product)
        self.assertEqual(result["chapter"], 34)
        self.assertTrue(any("34.02" in c["heading"] for c in result["candidates"]))

    def test_candle_routes_to_3406(self):
        product = _make_product(name="paraffin wax candle", essence="candle")
        result = _decide_chapter_34(product)
        self.assertEqual(result["chapter"], 34)
        self.assertTrue(any("34.06" in c["heading"] for c in result["candidates"]))

    def test_polish_routes_to_3405(self):
        product = _make_product(name="shoe polish", essence="polish cream")
        result = _decide_chapter_34(product)
        self.assertEqual(result["chapter"], 34)
        self.assertTrue(any("34.05" in c["heading"] for c in result["candidates"]))

    def test_wax_routes_to_3404(self):
        product = _make_product(name="artificial wax blend",
                                essence="synthetic wax prepared")
        result = _decide_chapter_34(product)
        self.assertEqual(result["chapter"], 34)
        self.assertTrue(any("34.04" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_34_candidate("soap bar"))
        self.assertTrue(_is_chapter_34_candidate("סבון"))
        self.assertFalse(_is_chapter_34_candidate("crude petroleum"))


# ========================================================================
# CHAPTER 35 — ALBUMINOIDAL SUBSTANCES, GLUES, ENZYMES
# ========================================================================

class TestChapter35(unittest.TestCase):

    def test_casein_routes_to_3501(self):
        product = _make_product(name="casein powder", essence="casein milk protein")
        result = _decide_chapter_35(product)
        self.assertEqual(result["chapter"], 35)
        self.assertTrue(any("35.01" in c["heading"] for c in result["candidates"]))

    def test_gelatin_routes_to_3503(self):
        product = _make_product(name="gelatin powder food grade", essence="gelatin")
        result = _decide_chapter_35(product)
        self.assertEqual(result["chapter"], 35)
        self.assertTrue(any("35.03" in c["heading"] for c in result["candidates"]))

    def test_enzyme_routes_to_3507(self):
        product = _make_product(name="lipase enzyme industrial", essence="enzyme")
        result = _decide_chapter_35(product)
        self.assertEqual(result["chapter"], 35)
        self.assertTrue(any("35.07" in c["heading"] for c in result["candidates"]))

    def test_glue_routes_to_3506(self):
        product = _make_product(name="adhesive glue epoxy", essence="glue adhesive")
        result = _decide_chapter_35(product)
        self.assertEqual(result["chapter"], 35)
        self.assertTrue(any("35.06" in c["heading"] for c in result["candidates"]))

    def test_dextrin_routes_to_3505(self):
        product = _make_product(name="modified starch dextrin",
                                essence="dextrin modified starch")
        result = _decide_chapter_35(product)
        self.assertEqual(result["chapter"], 35)
        self.assertTrue(any("35.05" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_35_candidate("gelatin powder"))
        self.assertTrue(_is_chapter_35_candidate("דבק"))
        self.assertFalse(_is_chapter_35_candidate("diesel fuel"))


# ========================================================================
# CHAPTER 36 — EXPLOSIVES, FIREWORKS, MATCHES
# ========================================================================

class TestChapter36(unittest.TestCase):

    def test_fireworks_routes_to_3604(self):
        product = _make_product(name="fireworks display rockets",
                                essence="fireworks pyrotechnics")
        result = _decide_chapter_36(product)
        self.assertEqual(result["chapter"], 36)
        self.assertTrue(any("36.04" in c["heading"] for c in result["candidates"]))

    def test_matches_routes_to_3605(self):
        product = _make_product(name="safety matches box", essence="matches")
        result = _decide_chapter_36(product)
        self.assertEqual(result["chapter"], 36)
        self.assertTrue(any("36.05" in c["heading"] for c in result["candidates"]))

    def test_dynamite_routes_to_3602(self):
        product = _make_product(name="dynamite explosive",
                                essence="prepared explosives")
        result = _decide_chapter_36(product)
        self.assertEqual(result["chapter"], 36)
        self.assertTrue(any("36.02" in c["heading"] for c in result["candidates"]))

    def test_propellant_powder_routes_to_3601(self):
        product = _make_product(name="propellant powder smokeless",
                                essence="propellant powder")
        result = _decide_chapter_36(product)
        self.assertEqual(result["chapter"], 36)
        self.assertTrue(any("36.01" in c["heading"] for c in result["candidates"]))

    def test_fuse_routes_to_3603(self):
        product = _make_product(name="detonating fuse cord",
                                essence="safety fuse detonator")
        result = _decide_chapter_36(product)
        self.assertEqual(result["chapter"], 36)
        self.assertTrue(any("36.03" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_36_candidate("fireworks"))
        self.assertTrue(_is_chapter_36_candidate("חומר נפץ"))
        self.assertFalse(_is_chapter_36_candidate("cotton fabric"))


# ========================================================================
# CHAPTER 37 — PHOTOGRAPHIC GOODS
# ========================================================================

class TestChapter37(unittest.TestCase):

    def test_photographic_film_routes_to_3702(self):
        product = _make_product(name="photographic film roll 35mm",
                                essence="photographic film unexposed")
        result = _decide_chapter_37(product)
        self.assertEqual(result["chapter"], 37)
        self.assertTrue(any("37.02" in c["heading"] for c in result["candidates"]))

    def test_photographic_paper_routes_to_3703(self):
        product = _make_product(name="photographic paper rolls",
                                essence="photographic paper sensitized")
        result = _decide_chapter_37(product)
        self.assertEqual(result["chapter"], 37)
        self.assertTrue(any("37.03" in c["heading"] for c in result["candidates"]))

    def test_photographic_plates_routes_to_3701(self):
        product = _make_product(name="photographic plates sensitized",
                                essence="photographic plates")
        result = _decide_chapter_37(product)
        self.assertEqual(result["chapter"], 37)
        self.assertTrue(any("37.01" in c["heading"] for c in result["candidates"]))

    def test_instant_film_routes_to_3701(self):
        product = _make_product(name="instant print film packs",
                                essence="instant film photographic")
        result = _decide_chapter_37(product)
        self.assertEqual(result["chapter"], 37)

    def test_chemical_preparations_routes_to_3707(self):
        product = _make_product(name="photographic developer chemical",
                                essence="photographic chemical preparation")
        result = _decide_chapter_37(product)
        self.assertEqual(result["chapter"], 37)
        self.assertTrue(any("37.07" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_37_candidate("photographic film"))
        self.assertTrue(_is_chapter_37_candidate("סרט צילום"))
        self.assertFalse(_is_chapter_37_candidate("copper wire"))


# ========================================================================
# CHAPTER 38 — MISCELLANEOUS CHEMICAL PRODUCTS
# ========================================================================

class TestChapter38(unittest.TestCase):

    def test_insecticide_routes_to_3808(self):
        product = _make_product(name="insecticide spray", essence="pesticide insecticide")
        result = _decide_chapter_38(product)
        self.assertEqual(result["chapter"], 38)
        self.assertTrue(any("38.08" in c["heading"] for c in result["candidates"]))

    def test_activated_carbon_routes_to_3802(self):
        product = _make_product(name="activated carbon granules",
                                essence="activated charcoal")
        result = _decide_chapter_38(product)
        self.assertEqual(result["chapter"], 38)
        self.assertTrue(any("38.02" in c["heading"] for c in result["candidates"]))

    def test_antifreeze_routes_to_3820(self):
        product = _make_product(name="antifreeze coolant", essence="anti-freezing preparation")
        result = _decide_chapter_38(product)
        self.assertEqual(result["chapter"], 38)
        self.assertTrue(any("38.20" in c["heading"] for c in result["candidates"]))

    def test_biodiesel_routes_to_3826(self):
        product = _make_product(name="biodiesel B100 fatty acid methyl ester",
                                essence="biodiesel FAME")
        result = _decide_chapter_38(product)
        self.assertEqual(result["chapter"], 38)
        self.assertTrue(any("38.26" in c["heading"] for c in result["candidates"]))

    def test_soldering_flux_routes_to_3810(self):
        product = _make_product(name="soldering flux paste",
                                essence="welding flux preparation")
        result = _decide_chapter_38(product)
        self.assertEqual(result["chapter"], 38)
        self.assertTrue(any("38.10" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_38_candidate("insecticide spray"))
        self.assertTrue(_is_chapter_38_candidate("חומר הדברה"))
        self.assertFalse(_is_chapter_38_candidate("live poultry"))


# ========================================================================
# INTEGRATION: CHAPTERS 25-38 via decide_chapter()
# ========================================================================

class TestChapters25to38Integration(unittest.TestCase):
    """Test that decide_chapter() correctly dispatches to chapters 25-38."""

    def test_decide_chapter_detects_cement(self):
        product = _make_product(name="portland cement bags", essence="cement")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 25)

    def test_decide_chapter_detects_iron_ore(self):
        product = _make_product(name="iron ore lumps", essence="hematite ore")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 26)

    def test_decide_chapter_detects_petroleum(self):
        product = _make_product(name="crude petroleum cargo", essence="crude oil")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 27)

    def test_decide_chapter_detects_inorganic_chemical(self):
        product = _make_product(name="hydrochloric acid technical grade",
                                essence="HCl acid solution")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 28)

    def test_decide_chapter_detects_citric_acid(self):
        product = _make_product(name="citric acid anhydrous bulk",
                                essence="organic acid citric")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 29)

    def test_decide_chapter_detects_tablets(self):
        product = _make_product(name="ibuprofen tablets 200mg",
                                essence="medicine dosage form")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 30)

    def test_decide_chapter_detects_fertilizer(self):
        product = _make_product(name="urea granular fertilizer",
                                essence="nitrogen fertilizer")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 31)

    def test_decide_chapter_detects_paint(self):
        product = _make_product(name="acrylic wall paint",
                                essence="latex paint")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 32)

    def test_decide_chapter_detects_perfume(self):
        product = _make_product(name="eau de toilette spray",
                                essence="perfume fragrance")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 33)

    def test_decide_chapter_detects_soap(self):
        product = _make_product(name="toilet soap bars", essence="soap bar")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 34)

    def test_decide_chapter_detects_gelatin(self):
        product = _make_product(name="gelatin sheets food grade",
                                essence="gelatin powder")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 35)

    def test_decide_chapter_detects_fireworks(self):
        product = _make_product(name="display fireworks rockets",
                                essence="pyrotechnics fireworks")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 36)

    def test_decide_chapter_detects_photo_film(self):
        product = _make_product(name="photographic film 35mm",
                                essence="photographic plate unexposed")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 37)

    def test_decide_chapter_detects_herbicide(self):
        product = _make_product(name="herbicide glyphosate",
                                essence="weed killer fungicide")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 38)


# ========================================================================
# CHAPTERS 39-55
# ========================================================================

class TestChapter39Plastics(unittest.TestCase):
    def test_pe_granules_primary(self):
        product = _make_product(name="polyethylene HDPE granules", essence="PE resin pellets")
        result = _decide_chapter_39(product)
        self.assertEqual(result["chapter"], 39)
        self.assertTrue(any("39.01" in c["heading"] for c in result["candidates"]))

    def test_pvc_pipe(self):
        product = _make_product(name="PVC pipe 110mm", essence="polyvinyl chloride tube")
        result = _decide_chapter_39(product)
        self.assertTrue(any("39.17" in c["heading"] for c in result["candidates"]))

    def test_plastic_bottle(self):
        product = _make_product(name="plastic bottle 500ml PET", essence="plastic container")
        result = _decide_chapter_39(product)
        self.assertTrue(any("39.23" in c["heading"] for c in result["candidates"]))

    def test_polystyrene_sheet(self):
        product = _make_product(name="polystyrene foam sheet", essence="EPS cellular sheet")
        result = _decide_chapter_39(product)
        self.assertTrue(any("39.21" in c["heading"] for c in result["candidates"]))

    def test_plastic_sanitary(self):
        product = _make_product(name="plastic bath tub acrylic", essence="plastic sanitary ware")
        result = _decide_chapter_39(product)
        self.assertTrue(any("39.22" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_39_candidate("polyethylene resin"))
        self.assertTrue(_is_chapter_39_candidate("פלסטיק"))
        self.assertFalse(_is_chapter_39_candidate("live fish"))


class TestChapter40Rubber(unittest.TestCase):
    def test_new_tyre(self):
        product = _make_product(name="pneumatic radial tyre 205/55R16", essence="new car tyre")
        result = _decide_chapter_40(product)
        self.assertEqual(result["chapter"], 40)
        self.assertTrue(any("40.11" in c["heading"] for c in result["candidates"]))

    def test_latex_glove(self):
        product = _make_product(name="latex examination gloves", essence="rubber glove disposable")
        result = _decide_chapter_40(product)
        self.assertTrue(any("40.15" in c["heading"] for c in result["candidates"]))

    def test_conveyor_belt(self):
        product = _make_product(name="rubber conveyor belt", essence="transmission belt vulcanised")
        result = _decide_chapter_40(product)
        self.assertTrue(any("40.10" in c["heading"] for c in result["candidates"]))

    def test_natural_rubber(self):
        product = _make_product(name="natural rubber latex", essence="hevea rubber")
        result = _decide_chapter_40(product)
        self.assertTrue(any("40.01" in c["heading"] for c in result["candidates"]))

    def test_synthetic_rubber(self):
        product = _make_product(name="EPDM synthetic rubber", essence="synthetic rubber compound")
        result = _decide_chapter_40(product)
        self.assertTrue(any("40.02" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_40_candidate("rubber gasket"))
        self.assertTrue(_is_chapter_40_candidate("צמיג חדש"))
        self.assertFalse(_is_chapter_40_candidate("steel pipe"))


class TestChapter41Leather(unittest.TestCase):
    def test_raw_bovine_hide(self):
        product = _make_product(name="raw cowhide salted", essence="raw hide bovine")
        result = _decide_chapter_41(product)
        self.assertEqual(result["chapter"], 41)
        self.assertTrue(any("41.01" in c["heading"] for c in result["candidates"]))

    def test_wet_blue_sheep(self):
        product = _make_product(name="wet-blue sheepskin", essence="chrome tanned sheep skin")
        result = _decide_chapter_41(product)
        self.assertTrue(any("41.05" in c["heading"] for c in result["candidates"]))

    def test_finished_leather(self):
        product = _make_product(name="full grain finished leather", essence="finished leather bovine")
        result = _decide_chapter_41(product)
        self.assertTrue(any("41.07" in c["heading"] for c in result["candidates"]))

    def test_composition_leather(self):
        product = _make_product(name="reconstituted leather sheets", essence="composition leather")
        result = _decide_chapter_41(product)
        self.assertTrue(any("41.15" in c["heading"] for c in result["candidates"]))

    def test_reptile_leather(self):
        product = _make_product(name="crocodile leather finished", essence="reptile leather")
        result = _decide_chapter_41(product)
        self.assertTrue(any("41.13" in c["heading"] for c in result["candidates"]))


class TestChapter42LeatherArticles(unittest.TestCase):
    def test_handbag(self):
        product = _make_product(name="leather handbag shoulder bag", essence="handbag leather")
        result = _decide_chapter_42(product)
        self.assertEqual(result["chapter"], 42)
        self.assertTrue(any("42.02" in c["heading"] for c in result["candidates"]))

    def test_leather_belt(self):
        product = _make_product(name="leather belt men", essence="leather belt accessory")
        result = _decide_chapter_42(product)
        self.assertTrue(any("42.03" in c["heading"] for c in result["candidates"]))

    def test_saddlery(self):
        product = _make_product(name="horse saddle leather", essence="saddlery harness")
        result = _decide_chapter_42(product)
        self.assertTrue(any("42.01" in c["heading"] for c in result["candidates"]))

    def test_suitcase(self):
        product = _make_product(name="leather suitcase travel", essence="trunk suitcase")
        result = _decide_chapter_42(product)
        self.assertTrue(any("42.02" in c["heading"] for c in result["candidates"]))

    def test_wallet(self):
        product = _make_product(name="leather wallet billfold", essence="wallet card case")
        result = _decide_chapter_42(product)
        self.assertTrue(any("42.02" in c["heading"] for c in result["candidates"]))


class TestChapter43Furskins(unittest.TestCase):
    def test_raw_mink(self):
        product = _make_product(name="raw mink pelt", essence="raw furskin mink undressed")
        result = _decide_chapter_43(product)
        self.assertEqual(result["chapter"], 43)
        self.assertTrue(any("43.01" in c["heading"] for c in result["candidates"]))

    def test_dressed_fox_fur(self):
        product = _make_product(name="dressed fox furskin", essence="tanned fur dyed")
        result = _decide_chapter_43(product)
        self.assertTrue(any("43.02" in c["heading"] for c in result["candidates"]))

    def test_fur_coat(self):
        product = _make_product(name="fur coat mink", essence="fur garment")
        result = _decide_chapter_43(product)
        self.assertTrue(any("43.03" in c["heading"] for c in result["candidates"]))

    def test_faux_fur(self):
        product = _make_product(name="faux fur fabric", essence="artificial fur imitation")
        result = _decide_chapter_43(product)
        self.assertTrue(any("43.04" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_43_candidate("fur coat"))
        self.assertTrue(_is_chapter_43_candidate("פרווה"))
        self.assertFalse(_is_chapter_43_candidate("cotton shirt"))


class TestChapter44Wood(unittest.TestCase):
    def test_plywood(self):
        product = _make_product(name="birch plywood 18mm", essence="plywood laminated")
        result = _decide_chapter_44(product)
        self.assertEqual(result["chapter"], 44)
        self.assertTrue(any("44.12" in c["heading"] for c in result["candidates"]))

    def test_mdf(self):
        product = _make_product(name="MDF board 12mm", essence="medium density fibreboard")
        result = _decide_chapter_44(product)
        self.assertTrue(any("44.11" in c["heading"] for c in result["candidates"]))

    def test_particleboard(self):
        product = _make_product(name="OSB particleboard", essence="oriented strand board")
        result = _decide_chapter_44(product)
        self.assertTrue(any("44.10" in c["heading"] for c in result["candidates"]))

    def test_wooden_door(self):
        product = _make_product(name="wooden door interior", essence="door frame wood")
        result = _decide_chapter_44(product)
        self.assertTrue(any("44.18" in c["heading"] for c in result["candidates"]))

    def test_sawn_lumber(self):
        product = _make_product(name="sawn pine lumber boards", essence="sawn wood timber")
        result = _decide_chapter_44(product)
        self.assertTrue(any("44.07" in c["heading"] for c in result["candidates"]))

    def test_furniture_parts_redirect(self):
        product = _make_product(name="wooden furniture parts table top",
                                essence="wooden furniture part")
        result = _decide_chapter_44(product)
        self.assertIsNotNone(result["redirect"])
        self.assertEqual(result["redirect"]["chapter"], 94)


class TestChapter45Cork(unittest.TestCase):
    def test_wine_cork(self):
        product = _make_product(name="wine cork stoppers natural", essence="cork stopper bottle")
        result = _decide_chapter_45(product)
        self.assertEqual(result["chapter"], 45)
        self.assertTrue(any("45.03" in c["heading"] for c in result["candidates"]))

    def test_cork_tiles(self):
        product = _make_product(name="agglomerated cork floor tiles", essence="cork tile sheet")
        result = _decide_chapter_45(product)
        self.assertTrue(any("45.04" in c["heading"] for c in result["candidates"]))

    def test_raw_cork(self):
        product = _make_product(name="natural cork bark raw", essence="raw cork natural")
        result = _decide_chapter_45(product)
        self.assertTrue(any("45.01" in c["heading"] for c in result["candidates"]))

    def test_cork_granules(self):
        product = _make_product(name="crushed cork granules", essence="natural cork waste granule")
        result = _decide_chapter_45(product)
        self.assertTrue(any("45.01" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_45_candidate("cork stopper"))
        self.assertTrue(_is_chapter_45_candidate("שעם טבעי"))
        self.assertFalse(_is_chapter_45_candidate("rubber seal"))


class TestChapter46Plaiting(unittest.TestCase):
    def test_basket(self):
        product = _make_product(name="wicker basket hamper", essence="basketware wicker")
        result = _decide_chapter_46(product)
        self.assertEqual(result["chapter"], 46)
        self.assertTrue(any("46.02" in c["heading"] for c in result["candidates"]))

    def test_bamboo_mat(self):
        product = _make_product(name="bamboo plait mat", essence="bamboo plaiting")
        result = _decide_chapter_46(product)
        self.assertTrue(len(result["candidates"]) >= 1)

    def test_rattan_article(self):
        product = _make_product(name="rattan basket decorative", essence="rattan wickerwork")
        result = _decide_chapter_46(product)
        self.assertTrue(any("46.02" in c["heading"] for c in result["candidates"]))

    def test_straw_plait(self):
        product = _make_product(name="straw plait braid", essence="straw plaiting material")
        result = _decide_chapter_46(product)
        self.assertTrue(any("46.01" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_46_candidate("wicker basket"))
        self.assertTrue(_is_chapter_46_candidate("במבוק"))
        self.assertFalse(_is_chapter_46_candidate("steel wire"))


class TestChapter47Pulp(unittest.TestCase):
    def test_kraft_pulp(self):
        product = _make_product(name="bleached kraft pulp", essence="chemical wood pulp sulphate")
        result = _decide_chapter_47(product)
        self.assertEqual(result["chapter"], 47)
        self.assertTrue(any("47.03" in c["heading"] for c in result["candidates"]))

    def test_mechanical_pulp(self):
        product = _make_product(name="mechanical wood pulp groundwood", essence="TMP pulp")
        result = _decide_chapter_47(product)
        self.assertTrue(any("47.01" in c["heading"] for c in result["candidates"]))

    def test_dissolving_pulp(self):
        product = _make_product(name="dissolving grade pulp", essence="viscose pulp alpha cellulose")
        result = _decide_chapter_47(product)
        self.assertTrue(any("47.02" in c["heading"] for c in result["candidates"]))

    def test_waste_paper(self):
        product = _make_product(name="recovered waste paper", essence="recycled paper scrap")
        result = _decide_chapter_47(product)
        self.assertTrue(any("47.07" in c["heading"] for c in result["candidates"]))

    def test_sulphite_pulp(self):
        product = _make_product(name="chemical wood pulp sulphite", essence="sulphite pulp")
        result = _decide_chapter_47(product)
        self.assertTrue(any("47.04" in c["heading"] for c in result["candidates"]))


class TestChapter48Paper(unittest.TestCase):
    def test_newsprint(self):
        product = _make_product(name="newsprint paper rolls", essence="newsprint")
        result = _decide_chapter_48(product)
        self.assertEqual(result["chapter"], 48)
        self.assertTrue(any("48.01" in c["heading"] for c in result["candidates"]))

    def test_tissue_toilet(self):
        product = _make_product(name="toilet paper rolls", essence="tissue paper toilet")
        result = _decide_chapter_48(product)
        self.assertTrue(any("48.18" in c["heading"] for c in result["candidates"]))

    def test_kraft_paper(self):
        product = _make_product(name="kraft paper sack 80gsm", essence="kraft liner paper")
        result = _decide_chapter_48(product)
        self.assertTrue(any("48.04" in c["heading"] for c in result["candidates"]))

    def test_corrugated_board(self):
        product = _make_product(name="corrugated cardboard boxes", essence="corrugated paperboard")
        result = _decide_chapter_48(product)
        self.assertTrue(any("48.08" in c["heading"] for c in result["candidates"]))

    def test_coated_art_paper(self):
        product = _make_product(name="coated art paper glossy", essence="clay coated paper")
        result = _decide_chapter_48(product)
        self.assertTrue(any("48.10" in c["heading"] for c in result["candidates"]))

    def test_wallpaper(self):
        product = _make_product(name="wallpaper vinyl coated", essence="wallpaper wall covering")
        result = _decide_chapter_48(product)
        self.assertTrue(any("48.14" in c["heading"] for c in result["candidates"]))


class TestChapter49Printed(unittest.TestCase):
    def test_book(self):
        product = _make_product(name="printed textbook hardcover", essence="book printed")
        result = _decide_chapter_49(product)
        self.assertEqual(result["chapter"], 49)
        self.assertTrue(any("49.01" in c["heading"] for c in result["candidates"]))

    def test_newspaper(self):
        product = _make_product(name="daily newspaper edition", essence="newspaper journal")
        result = _decide_chapter_49(product)
        self.assertTrue(any("49.02" in c["heading"] for c in result["candidates"]))

    def test_map(self):
        product = _make_product(name="world map poster printed", essence="map chart printed")
        result = _decide_chapter_49(product)
        self.assertTrue(any("49.05" in c["heading"] for c in result["candidates"]))

    def test_calendar(self):
        product = _make_product(name="wall calendar 2026", essence="printed calendar")
        result = _decide_chapter_49(product)
        self.assertTrue(any("49.10" in c["heading"] for c in result["candidates"]))

    def test_postcard(self):
        product = _make_product(name="illustrated postcards set", essence="postcard greeting")
        result = _decide_chapter_49(product)
        self.assertTrue(any("49.09" in c["heading"] for c in result["candidates"]))


class TestChapter50Silk(unittest.TestCase):
    def test_silk_fabric(self):
        product = _make_product(name="woven silk satin fabric", essence="silk fabric woven")
        result = _decide_chapter_50(product)
        self.assertEqual(result["chapter"], 50)
        self.assertTrue(any("50.07" in c["heading"] for c in result["candidates"]))

    def test_silk_yarn(self):
        product = _make_product(name="silk yarn natural", essence="silk thread spun")
        result = _decide_chapter_50(product)
        self.assertTrue(any("50.04" in c["heading"] for c in result["candidates"]))

    def test_raw_silk(self):
        product = _make_product(name="raw silk not thrown", essence="raw silk hevea")
        result = _decide_chapter_50(product)
        self.assertTrue(any("50.02" in c["heading"] for c in result["candidates"]))

    def test_silk_waste(self):
        product = _make_product(name="silk waste noils", essence="silk waste raw")
        result = _decide_chapter_50(product)
        self.assertTrue(any("50.03" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_50_candidate("silk fabric"))
        self.assertTrue(_is_chapter_50_candidate("משי"))
        self.assertFalse(_is_chapter_50_candidate("cotton shirt"))


class TestChapter51Wool(unittest.TestCase):
    def test_raw_wool(self):
        product = _make_product(name="greasy raw wool shorn", essence="raw wool sheep")
        result = _decide_chapter_51(product)
        self.assertEqual(result["chapter"], 51)
        self.assertTrue(any("51.01" in c["heading"] for c in result["candidates"]))

    def test_cashmere(self):
        product = _make_product(name="cashmere fibre raw", essence="cashmere fine animal hair")
        result = _decide_chapter_51(product)
        self.assertTrue(any("51.02" in c["heading"] for c in result["candidates"]))

    def test_wool_yarn(self):
        product = _make_product(name="worsted wool yarn", essence="yarn of combed wool")
        result = _decide_chapter_51(product)
        self.assertTrue(any("51.07" in c["heading"] for c in result["candidates"]))

    def test_wool_fabric(self):
        product = _make_product(name="woven wool tweed fabric", essence="wool fabric woven")
        result = _decide_chapter_51(product)
        self.assertTrue(any("51.1" in c["heading"] for c in result["candidates"]))

    def test_wool_tops(self):
        product = _make_product(name="combed wool tops", essence="wool tops carded")
        result = _decide_chapter_51(product)
        self.assertTrue(any("51.05" in c["heading"] for c in result["candidates"]))


class TestChapter52Cotton(unittest.TestCase):
    def test_raw_cotton(self):
        product = _make_product(name="raw cotton ginned", essence="raw cotton not carded")
        result = _decide_chapter_52(product)
        self.assertEqual(result["chapter"], 52)
        self.assertTrue(any("52.01" in c["heading"] for c in result["candidates"]))

    def test_cotton_yarn(self):
        product = _make_product(name="cotton yarn 30Ne", essence="cotton yarn combed")
        result = _decide_chapter_52(product)
        self.assertTrue(any("52.05" in c["heading"] for c in result["candidates"]))

    def test_denim_fabric(self):
        product = _make_product(name="denim fabric 14oz", essence="denim woven cotton")
        result = _decide_chapter_52(product)
        self.assertTrue(any("52.09" in c["heading"] for c in result["candidates"]))

    def test_cotton_waste(self):
        product = _make_product(name="cotton waste linters", essence="cotton linter waste")
        result = _decide_chapter_52(product)
        self.assertTrue(any("52.02" in c["heading"] for c in result["candidates"]))

    def test_sewing_thread(self):
        product = _make_product(name="cotton sewing thread", essence="sewing thread cotton")
        result = _decide_chapter_52(product)
        self.assertTrue(any("52.04" in c["heading"] for c in result["candidates"]))


class TestChapter53VegFibres(unittest.TestCase):
    def test_raw_flax(self):
        product = _make_product(name="raw flax fibre", essence="flax fibre raw")
        result = _decide_chapter_53(product)
        self.assertEqual(result["chapter"], 53)
        self.assertTrue(any("53.01" in c["heading"] for c in result["candidates"]))

    def test_jute_yarn(self):
        product = _make_product(name="jute yarn spun", essence="jute bast fibre yarn")
        result = _decide_chapter_53(product)
        self.assertTrue(any("53.07" in c["heading"] for c in result["candidates"]))

    def test_linen_fabric(self):
        product = _make_product(name="woven linen fabric", essence="flax linen woven cloth")
        result = _decide_chapter_53(product)
        self.assertTrue(any("53.09" in c["heading"] for c in result["candidates"]))

    def test_sisal_fibre(self):
        product = _make_product(name="sisal fibre raw", essence="sisal agave fibre")
        result = _decide_chapter_53(product)
        self.assertTrue(any("53.05" in c["heading"] for c in result["candidates"]))

    def test_hemp_fabric(self):
        product = _make_product(name="hemp fabric woven", essence="hemp woven cloth")
        result = _decide_chapter_53(product)
        self.assertTrue(any("53.11" in c["heading"] for c in result["candidates"]))


class TestChapter54ManMadeFilaments(unittest.TestCase):
    def test_polyester_filament_yarn(self):
        product = _make_product(name="polyester filament yarn", essence="PET filament yarn")
        result = _decide_chapter_54(product)
        self.assertEqual(result["chapter"], 54)
        self.assertTrue(any("54.02" in c["heading"] for c in result["candidates"]))

    def test_nylon_fabric(self):
        product = _make_product(name="woven nylon fabric", essence="polyamide woven fabric synthetic")
        result = _decide_chapter_54(product)
        self.assertTrue(any("54.07" in c["heading"] for c in result["candidates"]))

    def test_viscose_filament_yarn(self):
        product = _make_product(name="viscose rayon filament yarn", essence="artificial filament viscose")
        result = _decide_chapter_54(product)
        self.assertTrue(any("54.03" in c["heading"] for c in result["candidates"]))

    def test_sewing_thread_filament(self):
        product = _make_product(name="sewing thread nylon filament", essence="synthetic filament sewing")
        result = _decide_chapter_54(product)
        self.assertTrue(any("54.01" in c["heading"] for c in result["candidates"]))

    def test_viscose_fabric(self):
        product = _make_product(name="woven fabric of viscose rayon filament", essence="viscose filament woven fabric synthetic")
        result = _decide_chapter_54(product)
        self.assertTrue(any("54.08" in c["heading"] for c in result["candidates"]))


class TestChapter55ManMadeStaple(unittest.TestCase):
    def test_polyester_staple(self):
        product = _make_product(name="polyester staple fibre 1.4D", essence="PSF polyester staple")
        result = _decide_chapter_55(product)
        self.assertEqual(result["chapter"], 55)
        self.assertTrue(any("55.03" in c["heading"] for c in result["candidates"]))

    def test_viscose_staple(self):
        product = _make_product(name="viscose staple fibre", essence="VSF viscose rayon staple")
        result = _decide_chapter_55(product)
        self.assertTrue(any("55.04" in c["heading"] for c in result["candidates"]))

    def test_synthetic_staple_yarn(self):
        product = _make_product(name="acrylic staple fibre yarn", essence="synthetic staple yarn")
        result = _decide_chapter_55(product)
        self.assertTrue(any("55.09" in c["heading"] for c in result["candidates"]))

    def test_synthetic_staple_fabric(self):
        product = _make_product(name="polyester staple woven fabric", essence="synthetic staple fibre fabric woven")
        result = _decide_chapter_55(product)
        self.assertTrue(any("55.12" in c["heading"] for c in result["candidates"]))

    def test_fibre_waste(self):
        product = _make_product(name="synthetic fibre waste scrap", essence="man-made fibre waste")
        result = _decide_chapter_55(product)
        self.assertTrue(any("55.05" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_55_candidate("polyester staple fibre"))
        self.assertTrue(_is_chapter_55_candidate("סיבי ויסקוזה"))
        self.assertFalse(_is_chapter_55_candidate("cotton yarn"))


# ========================================================================
# INTEGRATION: CHAPTERS 39-55 via decide_chapter()
# ========================================================================

class TestChapters39to55Integration(unittest.TestCase):
    def test_decide_chapter_detects_plastic(self):
        product = _make_product(name="PVC plastic granules", essence="plastic polymer")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 39)

    def test_decide_chapter_detects_tyre(self):
        product = _make_product(name="new pneumatic tyre radial", essence="rubber tyre")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 40)

    def test_decide_chapter_detects_leather(self):
        product = _make_product(name="finished leather sheets", essence="tanned leather hide")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 41)

    def test_decide_chapter_detects_handbag(self):
        product = _make_product(name="handbag shoulder bag tote", essence="handbag purse clutch")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 42)

    def test_decide_chapter_detects_fur(self):
        product = _make_product(name="artificial fur fabric", essence="faux fur imitation")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 43)

    def test_decide_chapter_detects_plywood(self):
        product = _make_product(name="birch plywood 18mm sheets", essence="plywood wood")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 44)

    def test_decide_chapter_detects_cork(self):
        product = _make_product(name="natural cork stopper bottle plug", essence="cork stopper")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 45)

    def test_decide_chapter_detects_basket(self):
        product = _make_product(name="basketware manufactured", essence="basketware article")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 46)

    def test_decide_chapter_detects_pulp(self):
        product = _make_product(name="paper pulp kraft", essence="paper pulp")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 47)

    def test_decide_chapter_detects_paper(self):
        product = _make_product(name="toilet paper tissue", essence="tissue paper napkin")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 48)

    def test_decide_chapter_detects_book(self):
        product = _make_product(name="printed textbook hardcover", essence="book brochure")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 49)

    def test_decide_chapter_detects_silk(self):
        product = _make_product(name="woven silk satin fabric", essence="silk fabric")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 50)

    def test_decide_chapter_detects_wool(self):
        product = _make_product(name="greasy raw wool", essence="wool fibre greasy")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 51)

    def test_decide_chapter_detects_cotton(self):
        product = _make_product(name="raw cotton fibre not carded", essence="raw cotton")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 52)

    def test_decide_chapter_detects_jute(self):
        product = _make_product(name="raw jute fibre processed", essence="jute bast fibre")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 53)

    def test_decide_chapter_detects_filament(self):
        product = _make_product(name="man-made filament yarn 70D", essence="synthetic filament textile")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 54)

    def test_decide_chapter_detects_staple_fibre(self):
        product = _make_product(name="man-made staple fibres synthetic", essence="staple fibre")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 55)


if __name__ == "__main__":
    unittest.main()
