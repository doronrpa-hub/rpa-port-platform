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
    _decide_chapter_56,
    _decide_chapter_57,
    _decide_chapter_58,
    _decide_chapter_59,
    _decide_chapter_60,
    _decide_chapter_61,
    _decide_chapter_62,
    _decide_chapter_63,
    _decide_chapter_64,
    _decide_chapter_65,
    _decide_chapter_66,
    _decide_chapter_67,
    _decide_chapter_68,
    _decide_chapter_69,
    _decide_chapter_70,
    _decide_chapter_71,
    _decide_chapter_72,
    _is_chapter_56_candidate,
    _is_chapter_57_candidate,
    _is_chapter_58_candidate,
    _is_chapter_59_candidate,
    _is_chapter_60_candidate,
    _is_chapter_61_candidate,
    _is_chapter_62_candidate,
    _is_chapter_63_candidate,
    _is_chapter_64_candidate,
    _is_chapter_65_candidate,
    _is_chapter_66_candidate,
    _is_chapter_67_candidate,
    _is_chapter_68_candidate,
    _is_chapter_69_candidate,
    _is_chapter_70_candidate,
    _is_chapter_71_candidate,
    _is_chapter_72_candidate,
    _decide_chapter_73,
    _decide_chapter_74,
    _decide_chapter_75,
    _decide_chapter_76,
    _decide_chapter_78,
    _decide_chapter_79,
    _decide_chapter_80,
    _decide_chapter_81,
    _decide_chapter_82,
    _decide_chapter_83,
    _decide_chapter_84,
    _decide_chapter_85,
    _decide_chapter_86,
    _decide_chapter_87,
    _decide_chapter_88,
    _decide_chapter_89,
    _decide_chapter_90,
    _decide_chapter_91,
    _decide_chapter_92,
    _decide_chapter_93,
    _decide_chapter_94,
    _decide_chapter_95,
    _decide_chapter_96,
    _decide_chapter_97,
    _is_chapter_73_candidate,
    _is_chapter_74_candidate,
    _is_chapter_75_candidate,
    _is_chapter_76_candidate,
    _is_chapter_78_candidate,
    _is_chapter_79_candidate,
    _is_chapter_80_candidate,
    _is_chapter_81_candidate,
    _is_chapter_82_candidate,
    _is_chapter_83_candidate,
    _is_chapter_84_candidate,
    _is_chapter_85_candidate,
    _is_chapter_86_candidate,
    _is_chapter_87_candidate,
    _is_chapter_88_candidate,
    _is_chapter_89_candidate,
    _is_chapter_90_candidate,
    _is_chapter_91_candidate,
    _is_chapter_92_candidate,
    _is_chapter_93_candidate,
    _is_chapter_94_candidate,
    _is_chapter_95_candidate,
    _is_chapter_96_candidate,
    _is_chapter_97_candidate,
    _decide_chapter_98,
    _decide_chapter_99,
    _is_chapter_98_candidate,
    _is_chapter_99_candidate,
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

    def test_decide_chapter_returns_none_for_unknown(self):
        """decide_chapter() returns None for unrecognized product."""
        product = _make_product(name="zxyqtv abstract concept")
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
        self.assertEqual(len(chapters), 98)

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


# ========================================================================
# CHAPTER 56: Wadding, felt, nonwovens, yarns, twine, cordage, ropes
# ========================================================================

class TestChapter56WaddingFelt(unittest.TestCase):
    def test_nonwoven_spunbond(self):
        product = _make_product(name="spunbond nonwoven fabric 40gsm", essence="non-woven polypropylene")
        result = _decide_chapter_56(product)
        self.assertEqual(result["chapter"], 56)
        self.assertTrue(any("56.03" in c["heading"] for c in result["candidates"]))

    def test_felt_fabric(self):
        product = _make_product(name="pressed felt sheet industrial", essence="felt fabric pressed")
        result = _decide_chapter_56(product)
        self.assertTrue(any("56.02" in c["heading"] for c in result["candidates"]))

    def test_wadding(self):
        product = _make_product(name="polyester wadding batting", essence="wadding padding material")
        result = _decide_chapter_56(product)
        self.assertTrue(any("56.01" in c["heading"] for c in result["candidates"]))

    def test_rope(self):
        product = _make_product(name="polypropylene rope 12mm", essence="cordage rope cable")
        result = _decide_chapter_56(product)
        self.assertTrue(any("56.07" in c["heading"] for c in result["candidates"]))

    def test_fishing_net(self):
        product = _make_product(name="knotted nylon netting fishing net", essence="netting rope twine")
        result = _decide_chapter_56(product)
        self.assertTrue(any("56.08" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_56_candidate("spunbond nonwoven fabric"))
        self.assertTrue(_is_chapter_56_candidate("לבד"))
        self.assertFalse(_is_chapter_56_candidate("cotton shirt"))


# ========================================================================
# CHAPTER 57: Carpets and textile floor coverings
# ========================================================================

class TestChapter57Carpets(unittest.TestCase):
    def test_hand_knotted(self):
        product = _make_product(name="hand-knotted persian carpet silk wool", essence="oriental carpet hand knotted")
        result = _decide_chapter_57(product)
        self.assertEqual(result["chapter"], 57)
        self.assertTrue(any("57.01" in c["heading"] for c in result["candidates"]))

    def test_tufted_carpet(self):
        product = _make_product(name="tufted polypropylene carpet 4m wide", essence="tufted carpet floor covering")
        result = _decide_chapter_57(product)
        self.assertTrue(any("57.03" in c["heading"] for c in result["candidates"]))

    def test_woven_carpet(self):
        product = _make_product(name="Axminster woven carpet wool", essence="woven carpet Wilton")
        result = _decide_chapter_57(product)
        self.assertTrue(any("57.02" in c["heading"] for c in result["candidates"]))

    def test_generic_rug(self):
        product = _make_product(name="שטיח לסלון", essence="שטיח ריצוף טקסטיל")
        result = _decide_chapter_57(product)
        self.assertEqual(result["chapter"], 57)

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_57_candidate("tufted carpet"))
        self.assertTrue(_is_chapter_57_candidate("שטיח"))
        self.assertFalse(_is_chapter_57_candidate("steel pipe"))


# ========================================================================
# CHAPTER 58: Special woven fabrics — pile/lace/embroidery/ribbon
# ========================================================================

class TestChapter58SpecialFabrics(unittest.TestCase):
    def test_embroidery(self):
        product = _make_product(name="embroidered fabric lace trim", essence="embroidery broderie")
        result = _decide_chapter_58(product)
        self.assertEqual(result["chapter"], 58)
        self.assertTrue(any("58.10" in c["heading"] for c in result["candidates"]))

    def test_lace_tulle(self):
        product = _make_product(name="machine lace tulle fabric", essence="lace tulle net")
        result = _decide_chapter_58(product)
        self.assertTrue(any("58.04" in c["heading"] for c in result["candidates"]))

    def test_velvet_pile(self):
        product = _make_product(name="woven velvet pile fabric", essence="pile fabric velour")
        result = _decide_chapter_58(product)
        self.assertTrue(any("58.01" in c["heading"] for c in result["candidates"]))

    def test_ribbon_narrow(self):
        product = _make_product(name="woven ribbon label badge", essence="narrow woven fabric ribbon")
        result = _decide_chapter_58(product)
        self.assertTrue(any("58.06" in c["heading"] for c in result["candidates"]))

    def test_terry_towelling(self):
        product = _make_product(name="terry towelling fabric woven", essence="terry fabric towelling")
        result = _decide_chapter_58(product)
        self.assertTrue(any("58.02" in c["heading"] for c in result["candidates"]))


# ========================================================================
# CHAPTER 59: Impregnated/coated/laminated textile fabrics
# ========================================================================

class TestChapter59CoatedFabrics(unittest.TestCase):
    def test_tyre_cord(self):
        product = _make_product(name="nylon tyre cord fabric high-tenacity", essence="tyre cord fabric polyester")
        result = _decide_chapter_59(product)
        self.assertEqual(result["chapter"], 59)
        self.assertTrue(any("59.02" in c["heading"] for c in result["candidates"]))

    def test_conveyor_belt(self):
        product = _make_product(name="textile conveyor belt reinforced", essence="conveyor belt fabric transmission")
        result = _decide_chapter_59(product)
        self.assertTrue(any("59.10" in c["heading"] for c in result["candidates"]))

    def test_tarpaulin(self):
        product = _make_product(name="PVC tarpaulin waterproof", essence="tarpaulin awning tent fabric")
        result = _decide_chapter_59(product)
        self.assertTrue(any("59.07" in c["heading"] for c in result["candidates"]))

    def test_pvc_coated_fabric(self):
        product = _make_product(name="PVC coated polyester fabric", essence="coated textile fabric plastic")
        result = _decide_chapter_59(product)
        self.assertTrue(any("59.03" in c["heading"] for c in result["candidates"]))

    def test_textile_hose(self):
        product = _make_product(name="textile fire hose reinforced", essence="textile hose pipe")
        result = _decide_chapter_59(product)
        self.assertTrue(any("59.09" in c["heading"] for c in result["candidates"]))


# ========================================================================
# CHAPTER 60: Knitted or crocheted fabrics
# ========================================================================

class TestChapter60KnittedFabrics(unittest.TestCase):
    def test_pile_knit(self):
        product = _make_product(name="knitted velour pile fabric", essence="knit velvet pile")
        result = _decide_chapter_60(product)
        self.assertEqual(result["chapter"], 60)
        self.assertTrue(any("60.01" in c["heading"] for c in result["candidates"]))

    def test_warp_knit(self):
        product = _make_product(name="raschel warp-knit fabric", essence="warp knit tricot fabric")
        result = _decide_chapter_60(product)
        self.assertTrue(any("60.05" in c["heading"] for c in result["candidates"]))

    def test_jersey_fabric(self):
        product = _make_product(name="single jersey cotton knit fabric", essence="weft knit jersey interlock")
        result = _decide_chapter_60(product)
        self.assertTrue(any("60.06" in c["heading"] for c in result["candidates"]))

    def test_fleece_fabric(self):
        product = _make_product(name="polyester fleece fabric", essence="fleece knit fabric")
        result = _decide_chapter_60(product)
        self.assertTrue(any("60.0" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_60_candidate("jersey knit fabric"))
        self.assertTrue(_is_chapter_60_candidate("סריג"))
        self.assertFalse(_is_chapter_60_candidate("woven cotton"))


# ========================================================================
# CHAPTER 61: Knitted clothing
# ========================================================================

class TestChapter61KnittedClothing(unittest.TestCase):
    def test_tshirt(self):
        product = _make_product(name="cotton T-shirt men", essence="T-shirt singlet knitted")
        result = _decide_chapter_61(product)
        self.assertEqual(result["chapter"], 61)
        self.assertTrue(any("61.09" in c["heading"] for c in result["candidates"]))

    def test_sweater(self):
        product = _make_product(name="wool pullover sweater", essence="sweater pullover knit")
        result = _decide_chapter_61(product)
        self.assertTrue(any("61.10" in c["heading"] for c in result["candidates"]))

    def test_hosiery(self):
        product = _make_product(name="cotton socks men", essence="socks hosiery knitted")
        result = _decide_chapter_61(product)
        self.assertTrue(any("61.15" in c["heading"] for c in result["candidates"]))

    def test_baby_garment(self):
        product = _make_product(name="baby romper knitted cotton", essence="infant baby garment knit")
        result = _decide_chapter_61(product)
        self.assertTrue(any("61.11" in c["heading"] for c in result["candidates"]))

    def test_hoodie(self):
        product = _make_product(name="hoodie sweatshirt fleece", essence="hoodie pullover knit")
        result = _decide_chapter_61(product)
        self.assertTrue(any("61.10" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_61_candidate("T-shirt cotton"))
        self.assertTrue(_is_chapter_61_candidate("סוודר"))
        self.assertFalse(_is_chapter_61_candidate("woven shirt"))


# ========================================================================
# CHAPTER 62: Woven clothing
# ========================================================================

class TestChapter62WovenClothing(unittest.TestCase):
    def test_jeans(self):
        product = _make_product(name="men denim jeans trousers", essence="jeans denim trousers woven")
        result = _decide_chapter_62(product)
        self.assertEqual(result["chapter"], 62)
        self.assertTrue(any("62.03" in c["heading"] for c in result["candidates"]))

    def test_dress_shirt(self):
        product = _make_product(name="men's dress shirt cotton", essence="woven shirt button-down men")
        result = _decide_chapter_62(product)
        self.assertTrue(any("62.05" in c["heading"] for c in result["candidates"]))

    def test_womens_dress(self):
        product = _make_product(name="women silk dress woven", essence="woven dress skirt women")
        result = _decide_chapter_62(product)
        self.assertTrue(any("62.04" in c["heading"] for c in result["candidates"]))

    def test_workwear_overall(self):
        product = _make_product(name="industrial overall coverall", essence="workwear overall uniform")
        result = _decide_chapter_62(product)
        self.assertTrue(any("62.11" in c["heading"] for c in result["candidates"]))

    def test_tie(self):
        product = _make_product(name="silk necktie bow tie", essence="tie cravat bow tie")
        result = _decide_chapter_62(product)
        self.assertTrue(any("62.15" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_62_candidate("jeans trousers"))
        self.assertTrue(_is_chapter_62_candidate("shirt"))
        self.assertFalse(_is_chapter_62_candidate("knitted sweater"))


# ========================================================================
# CHAPTER 63: Other textile articles — blankets/bedlinen/curtains/bags/rags
# ========================================================================

class TestChapter63OtherTextiles(unittest.TestCase):
    def test_blanket(self):
        product = _make_product(name="polyester fleece blanket", essence="blanket quilt duvet")
        result = _decide_chapter_63(product)
        self.assertEqual(result["chapter"], 63)
        self.assertTrue(any("63.01" in c["heading"] for c in result["candidates"]))

    def test_bed_linen(self):
        product = _make_product(name="cotton bed sheet fitted", essence="bed linen sheet pillow case")
        result = _decide_chapter_63(product)
        self.assertTrue(any("63.02" in c["heading"] for c in result["candidates"]))

    def test_curtain(self):
        product = _make_product(name="polyester curtain drape", essence="curtain blind drape")
        result = _decide_chapter_63(product)
        self.assertTrue(any("63.03" in c["heading"] for c in result["candidates"]))

    def test_jute_bag(self):
        product = _make_product(name="jute sack FIBC big bag", essence="sack bag textile packing")
        result = _decide_chapter_63(product)
        self.assertTrue(any("63.05" in c["heading"] for c in result["candidates"]))

    def test_worn_clothing(self):
        product = _make_product(name="used clothing second-hand", essence="worn clothing used")
        result = _decide_chapter_63(product)
        self.assertTrue(any("63.09" in c["heading"] for c in result["candidates"]))

    def test_rags(self):
        product = _make_product(name="cotton rags wiping cloth industrial", essence="rag wiping cloth cleaning")
        result = _decide_chapter_63(product)
        self.assertTrue(any("63.10" in c["heading"] for c in result["candidates"]))


# ========================================================================
# CHAPTER 64: Footwear
# ========================================================================

class TestChapter64Footwear(unittest.TestCase):
    def test_leather_shoe(self):
        product = _make_product(name="leather men's oxford shoe", essence="leather footwear shoe upper leather")
        result = _decide_chapter_64(product)
        self.assertEqual(result["chapter"], 64)
        self.assertTrue(any("64.03" in c["heading"] for c in result["candidates"]))

    def test_waterproof_boot(self):
        product = _make_product(name="waterproof rubber wellington boot", essence="rubber boot waterproof gumboot")
        result = _decide_chapter_64(product)
        self.assertTrue(any("64.01" in c["heading"] for c in result["candidates"]))

    def test_textile_sneaker(self):
        product = _make_product(name="canvas textile sneaker shoe", essence="textile upper shoe canvas")
        result = _decide_chapter_64(product)
        self.assertTrue(any("64.04" in c["heading"] for c in result["candidates"]))

    def test_sports_shoe(self):
        product = _make_product(name="running shoe sports trainer", essence="sports shoe sneaker athletic")
        result = _decide_chapter_64(product)
        self.assertTrue(any("64.02" in c["heading"] for c in result["candidates"]))

    def test_footwear_parts(self):
        product = _make_product(name="rubber outsole shoe component", essence="insole outsole footwear parts")
        result = _decide_chapter_64(product)
        self.assertTrue(any("64.06" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_64_candidate("leather shoe"))
        self.assertTrue(_is_chapter_64_candidate("סנדל"))
        self.assertFalse(_is_chapter_64_candidate("cotton fabric"))


# ========================================================================
# CHAPTER 65: Headgear
# ========================================================================

class TestChapter65Headgear(unittest.TestCase):
    def test_safety_helmet(self):
        product = _make_product(name="safety helmet hard hat construction", essence="protective helmet headgear")
        result = _decide_chapter_65(product)
        self.assertEqual(result["chapter"], 65)
        self.assertTrue(any("65.06" in c["heading"] for c in result["candidates"]))

    def test_felt_hat(self):
        product = _make_product(name="felt hat fedora", essence="felt hat headgear")
        result = _decide_chapter_65(product)
        self.assertTrue(any("65.03" in c["heading"] for c in result["candidates"]))

    def test_straw_hat(self):
        product = _make_product(name="panama straw hat", essence="straw hat plaited")
        result = _decide_chapter_65(product)
        self.assertTrue(any("65.04" in c["heading"] for c in result["candidates"]))

    def test_knitted_beanie(self):
        product = _make_product(name="knitted wool beanie cap", essence="knit beanie textile")
        result = _decide_chapter_65(product)
        self.assertTrue(any("65.05" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_65_candidate("safety helmet"))
        self.assertTrue(_is_chapter_65_candidate("כובע"))
        self.assertFalse(_is_chapter_65_candidate("leather shoe"))


# ========================================================================
# CHAPTER 66: Umbrellas, walking sticks, whips
# ========================================================================

class TestChapter66Umbrellas(unittest.TestCase):
    def test_umbrella(self):
        product = _make_product(name="folding umbrella automatic", essence="umbrella parasol")
        result = _decide_chapter_66(product)
        self.assertEqual(result["chapter"], 66)
        self.assertTrue(any("66.01" in c["heading"] for c in result["candidates"]))

    def test_walking_stick(self):
        product = _make_product(name="wooden walking stick cane", essence="walking stick cane")
        result = _decide_chapter_66(product)
        self.assertTrue(any("66.02" in c["heading"] for c in result["candidates"]))

    def test_garden_umbrella(self):
        product = _make_product(name="garden umbrella beach parasol", essence="sun umbrella garden")
        result = _decide_chapter_66(product)
        self.assertTrue(any("66.01" in c["heading"] for c in result["candidates"]))

    def test_whip(self):
        product = _make_product(name="riding crop horse whip", essence="whip riding crop")
        result = _decide_chapter_66(product)
        self.assertTrue(any("66.02" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_66_candidate("umbrella"))
        self.assertTrue(_is_chapter_66_candidate("מטריה"))
        self.assertFalse(_is_chapter_66_candidate("leather bag"))


# ========================================================================
# CHAPTER 67: Feathers, artificial flowers, hair articles
# ========================================================================

class TestChapter67FeathersFlowers(unittest.TestCase):
    def test_artificial_flower(self):
        product = _make_product(name="artificial silk flower bouquet", essence="fake flower artificial plant")
        result = _decide_chapter_67(product)
        self.assertEqual(result["chapter"], 67)
        self.assertTrue(any("67.02" in c["heading"] for c in result["candidates"]))

    def test_wig(self):
        product = _make_product(name="human hair wig full lace", essence="wig hairpiece human hair")
        result = _decide_chapter_67(product)
        self.assertTrue(any("67.04" in c["heading"] for c in result["candidates"]))

    def test_feather_down(self):
        product = _make_product(name="goose down feather filling", essence="feather down filling")
        result = _decide_chapter_67(product)
        self.assertTrue(any("67.01" in c["heading"] for c in result["candidates"]))

    def test_human_hair_raw(self):
        product = _make_product(name="human hair dressed thinned bleached", essence="human hair dressed prepared")
        result = _decide_chapter_67(product)
        self.assertTrue(any("67.03" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_67_candidate("artificial flower"))
        self.assertTrue(_is_chapter_67_candidate("פאה"))
        self.assertFalse(_is_chapter_67_candidate("cotton fabric"))


# ========================================================================
# CHAPTER 68: Stone, plaster, cement, asbestos articles
# ========================================================================

class TestChapter68StoneArticles(unittest.TestCase):
    def test_grinding_wheel(self):
        product = _make_product(name="abrasive grinding wheel stone", essence="grindstone abrasive wheel")
        result = _decide_chapter_68(product)
        self.assertEqual(result["chapter"], 68)
        self.assertTrue(any("68.04" in c["heading"] for c in result["candidates"]))

    def test_brake_lining(self):
        product = _make_product(name="brake lining pad friction material", essence="friction material brake pad")
        result = _decide_chapter_68(product)
        self.assertTrue(any("68.13" in c["heading"] for c in result["candidates"]))

    def test_rock_wool_insulation(self):
        product = _make_product(name="mineral rock wool insulation board", essence="rock wool insulation mineral")
        result = _decide_chapter_68(product)
        self.assertTrue(any("68.06" in c["heading"] for c in result["candidates"]))

    def test_plasterboard(self):
        product = _make_product(name="gypsum plasterboard drywall", essence="plaster board gypsum panel")
        result = _decide_chapter_68(product)
        self.assertTrue(any("68.09" in c["heading"] for c in result["candidates"]))

    def test_marble_tile(self):
        product = _make_product(name="marble tile slab polished", essence="marble stone tile worked")
        result = _decide_chapter_68(product)
        self.assertTrue(any("68.02" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_68_candidate("grinding wheel"))
        self.assertTrue(_is_chapter_68_candidate("אבן שיש"))
        self.assertFalse(_is_chapter_68_candidate("glass bottle"))


# ========================================================================
# CHAPTER 69: Ceramic products
# ========================================================================

class TestChapter69Ceramics(unittest.TestCase):
    def test_sanitary_ware(self):
        product = _make_product(name="ceramic toilet sanitary ware", essence="sanitary ware toilet basin")
        result = _decide_chapter_69(product)
        self.assertEqual(result["chapter"], 69)
        self.assertTrue(any("69.10" in c["heading"] for c in result["candidates"]))

    def test_glazed_tile(self):
        product = _make_product(name="glazed porcelain floor tile", essence="glazed ceramic tile")
        result = _decide_chapter_69(product)
        self.assertTrue(any("69.08" in c["heading"] for c in result["candidates"]))

    def test_refractory_brick(self):
        product = _make_product(name="refractory fire brick alumina", essence="refractory brick fire-clay")
        result = _decide_chapter_69(product)
        self.assertTrue(any("69.02" in c["heading"] for c in result["candidates"]))

    def test_porcelain_tableware(self):
        product = _make_product(name="porcelain dinner plate cup china", essence="porcelain china tableware")
        result = _decide_chapter_69(product)
        self.assertTrue(any("69.11" in c["heading"] for c in result["candidates"]))

    def test_building_brick(self):
        product = _make_product(name="ceramic building brick", essence="brick ceramic building")
        result = _decide_chapter_69(product)
        self.assertTrue(any("69.04" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_69_candidate("ceramic tile"))
        self.assertTrue(_is_chapter_69_candidate("refractory"))
        self.assertFalse(_is_chapter_69_candidate("steel pipe"))


# ========================================================================
# CHAPTER 70: Glass and glassware
# ========================================================================

class TestChapter70Glass(unittest.TestCase):
    def test_fiberglass(self):
        product = _make_product(name="glass fibre mat fiberglass", essence="fiberglass glass wool glass fibre")
        result = _decide_chapter_70(product)
        self.assertEqual(result["chapter"], 70)
        self.assertTrue(any("70.19" in c["heading"] for c in result["candidates"]))

    def test_safety_glass(self):
        product = _make_product(name="laminated safety glass windshield", essence="tempered glass safety laminated")
        result = _decide_chapter_70(product)
        self.assertTrue(any("70.07" in c["heading"] for c in result["candidates"]))

    def test_mirror(self):
        product = _make_product(name="glass mirror framed bathroom", essence="mirror looking glass")
        result = _decide_chapter_70(product)
        self.assertTrue(any("70.09" in c["heading"] for c in result["candidates"]))

    def test_glass_bottle(self):
        product = _make_product(name="glass bottle 750ml wine", essence="glass bottle jar container")
        result = _decide_chapter_70(product)
        self.assertTrue(any("70.10" in c["heading"] for c in result["candidates"]))

    def test_drinking_glass(self):
        product = _make_product(name="crystal wine glass goblet", essence="glassware drinking glass tumbler")
        result = _decide_chapter_70(product)
        self.assertTrue(any("70.13" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_70_candidate("glass bottle"))
        self.assertTrue(_is_chapter_70_candidate("זכוכית"))
        self.assertFalse(_is_chapter_70_candidate("ceramic tile"))


# ========================================================================
# CHAPTER 71: Precious stones, metals, jewellery, coins
# ========================================================================

class TestChapter71PreciousMetals(unittest.TestCase):
    def test_diamond(self):
        product = _make_product(name="rough diamond uncut", essence="diamond brilliant")
        result = _decide_chapter_71(product)
        self.assertEqual(result["chapter"], 71)
        self.assertTrue(any("71.02" in c["heading"] for c in result["candidates"]))

    def test_gold_bar(self):
        product = _make_product(name="gold bar bullion 999", essence="gold unwrought ingot")
        result = _decide_chapter_71(product)
        self.assertTrue(any("71.08" in c["heading"] for c in result["candidates"]))

    def test_jewellery(self):
        product = _make_product(name="gold necklace pendant 18K", essence="jewellery necklace precious metal")
        result = _decide_chapter_71(product)
        self.assertTrue(any("71.13" in c["heading"] for c in result["candidates"]))

    def test_imitation_jewellery(self):
        product = _make_product(name="costume fashion jewellery imitation", essence="imitation jewellery costume")
        result = _decide_chapter_71(product)
        self.assertTrue(any("71.17" in c["heading"] for c in result["candidates"]))

    def test_coin(self):
        product = _make_product(name="gold commemorative coin numismatic", essence="coin gold silver")
        result = _decide_chapter_71(product)
        self.assertTrue(any("71.18" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_71_candidate("diamond"))
        self.assertTrue(_is_chapter_71_candidate("תכשיט"))
        self.assertFalse(_is_chapter_71_candidate("steel bar"))


# ========================================================================
# CHAPTER 72: Iron and steel
# ========================================================================

class TestChapter72IronSteel(unittest.TestCase):
    def test_pig_iron(self):
        product = _make_product(name="pig iron ingot", essence="pig iron spiegeleisen")
        result = _decide_chapter_72(product)
        self.assertEqual(result["chapter"], 72)
        self.assertTrue(any("72.01" in c["heading"] for c in result["candidates"]))

    def test_ferro_alloy(self):
        product = _make_product(name="ferro-silicon alloy", essence="ferro-alloy ferro-silicon")
        result = _decide_chapter_72(product)
        self.assertTrue(any("72.02" in c["heading"] for c in result["candidates"]))

    def test_hot_rolled_coil(self):
        product = _make_product(name="hot-rolled steel coil flat", essence="hot rolled steel sheet coil flat-rolled")
        result = _decide_chapter_72(product)
        self.assertTrue(any("72.08" in c["heading"] for c in result["candidates"]))

    def test_stainless_sheet(self):
        product = _make_product(name="stainless steel 304 cold-rolled sheet", essence="stainless steel sheet cold-rolled flat")
        result = _decide_chapter_72(product)
        self.assertTrue(any("72.20" in c["heading"] for c in result["candidates"]))

    def test_rebar(self):
        product = _make_product(name="steel rebar reinforcing bar deformed", essence="reinforcing bar rebar steel hot-rolled")
        result = _decide_chapter_72(product)
        self.assertTrue(any("72.13" in c["heading"] for c in result["candidates"]))

    def test_steel_wire(self):
        product = _make_product(name="galvanized steel wire", essence="iron steel wire galvanized")
        result = _decide_chapter_72(product)
        self.assertTrue(any("72.17" in c["heading"] for c in result["candidates"]))

    def test_h_beam(self):
        product = _make_product(name="structural H-beam steel section", essence="H-beam angle section structural steel")
        result = _decide_chapter_72(product)
        self.assertTrue(any("72.16" in c["heading"] for c in result["candidates"]))

    def test_scrap(self):
        product = _make_product(name="iron steel scrap waste remelting", essence="scrap iron steel waste")
        result = _decide_chapter_72(product)
        self.assertTrue(any("72.04" in c["heading"] for c in result["candidates"]))

    def test_candidate_detection(self):
        self.assertTrue(_is_chapter_72_candidate("stainless steel"))
        self.assertTrue(_is_chapter_72_candidate("פלדה"))
        self.assertFalse(_is_chapter_72_candidate("copper wire"))


# ========================================================================
# INTEGRATION: CHAPTERS 56-72 via decide_chapter()
# ========================================================================

class TestChapters56to72Integration(unittest.TestCase):
    def test_decide_chapter_detects_nonwoven(self):
        product = _make_product(name="spunbond nonwoven fabric", essence="non-woven polypropylene")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 56)

    def test_decide_chapter_detects_carpet(self):
        product = _make_product(name="tufted carpet 4m wide", essence="tufted carpet floor covering textile")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 57)

    def test_decide_chapter_detects_lace(self):
        product = _make_product(name="machine lace fabric", essence="lace tulle")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 58)

    def test_decide_chapter_detects_tyre_cord(self):
        product = _make_product(name="nylon tyre cord fabric high-tenacity", essence="tyre cord fabric")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 59)

    def test_decide_chapter_detects_jersey(self):
        product = _make_product(name="jersey knit fabric cotton", essence="knitted fabric jersey")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 60)

    def test_decide_chapter_detects_tshirt(self):
        product = _make_product(name="cotton T-shirt knitted", essence="T-shirt knit singlet")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 61)

    def test_decide_chapter_detects_jeans(self):
        product = _make_product(name="denim jeans trousers men", essence="jeans denim woven trousers")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 62)

    def test_decide_chapter_detects_blanket(self):
        product = _make_product(name="warm blanket bed throw", essence="blanket quilt duvet comforter")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 63)

    def test_decide_chapter_detects_shoe(self):
        product = _make_product(name="leather oxford shoe men", essence="leather shoe footwear")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 64)

    def test_decide_chapter_detects_helmet(self):
        product = _make_product(name="motorcycle helmet safety", essence="crash helmet protective headgear")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 65)

    def test_decide_chapter_detects_umbrella(self):
        product = _make_product(name="folding umbrella automatic", essence="umbrella parasol")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 66)

    def test_decide_chapter_detects_wig(self):
        product = _make_product(name="human hair wig full lace", essence="wig hairpiece human hair toupee")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 67)

    def test_decide_chapter_detects_grindstone(self):
        product = _make_product(name="abrasive grinding wheel stone", essence="grindstone millstone")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 68)

    def test_decide_chapter_detects_ceramic_tile(self):
        product = _make_product(name="glazed porcelain ceramic tile", essence="ceramic tile porcelain")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 69)

    def test_decide_chapter_detects_glass_fibre(self):
        product = _make_product(name="fiberglass glass fibre mat", essence="glass fibre fiberglass")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 70)

    def test_decide_chapter_detects_diamond(self):
        product = _make_product(name="rough diamond uncut gem", essence="diamond precious stone")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 71)

    def test_decide_chapter_detects_steel(self):
        product = _make_product(name="hot-rolled steel coil", essence="steel flat-rolled coil")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 72)


# ============================================================================
# CHAPTERS 73-83: Base metals and articles thereof
# ============================================================================

class TestChapter73IronSteelArticles(unittest.TestCase):
    def test_candidate_steel_pipe(self):
        self.assertTrue(_is_chapter_73_candidate("steel pipe seamless"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_73_candidate("צינור פלדה"))
    def test_negative(self):
        self.assertFalse(_is_chapter_73_candidate("cotton fabric"))
    def test_decide_tube(self):
        product = _make_product(name="seamless steel tube pipe", essence="steel tube")
        result = _decide_chapter_73(product)
        self.assertEqual(result["chapter"], 73)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_nails(self):
        product = _make_product(name="iron nails screws bolts", essence="nails bolts")
        result = _decide_chapter_73(product)
        self.assertEqual(result["chapter"], 73)
    def test_decide_stove(self):
        product = _make_product(name="cast iron stove radiator", essence="iron stove heating")
        result = _decide_chapter_73(product)
        self.assertEqual(result["chapter"], 73)
    def test_decide_wire(self):
        product = _make_product(name="steel wire barbed wire fencing", essence="wire steel barbed")
        result = _decide_chapter_73(product)
        self.assertEqual(result["chapter"], 73)
    def test_decide_structure(self):
        product = _make_product(name="steel structure bridge beam", essence="iron structure beam")
        result = _decide_chapter_73(product)
        self.assertEqual(result["chapter"], 73)


class TestChapter74Copper(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_74_candidate("copper wire refined"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_74_candidate("נחושת"))
    def test_negative(self):
        self.assertFalse(_is_chapter_74_candidate("plastic bottle"))
    def test_decide_wire(self):
        product = _make_product(name="copper wire cable", essence="copper wire")
        result = _decide_chapter_74(product)
        self.assertEqual(result["chapter"], 74)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_tube(self):
        product = _make_product(name="copper tube fitting plumbing", essence="copper tube")
        result = _decide_chapter_74(product)
        self.assertEqual(result["chapter"], 74)


class TestChapter75Nickel(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_75_candidate("nickel unwrought"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_75_candidate("ניקל"))
    def test_negative(self):
        self.assertFalse(_is_chapter_75_candidate("wooden chair"))
    def test_decide(self):
        product = _make_product(name="nickel bar rod profile", essence="nickel bar")
        result = _decide_chapter_75(product)
        self.assertEqual(result["chapter"], 75)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_tube(self):
        product = _make_product(name="nickel tube pipe", essence="nickel tube")
        result = _decide_chapter_75(product)
        self.assertEqual(result["chapter"], 75)


class TestChapter76Aluminium(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_76_candidate("aluminium foil sheet"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_76_candidate("אלומיניום"))
    def test_negative(self):
        self.assertFalse(_is_chapter_76_candidate("glass bottle"))
    def test_decide_foil(self):
        product = _make_product(name="aluminium foil kitchen wrap", essence="aluminium foil")
        result = _decide_chapter_76(product)
        self.assertEqual(result["chapter"], 76)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_structure(self):
        product = _make_product(name="aluminium window frame structure", essence="aluminium structure")
        result = _decide_chapter_76(product)
        self.assertEqual(result["chapter"], 76)


class TestChapter78Lead(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_78_candidate("lead unwrought ingot"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_78_candidate("עופרת"))
    def test_negative(self):
        self.assertFalse(_is_chapter_78_candidate("leather bag"))
    def test_decide(self):
        product = _make_product(name="lead plate sheet strip", essence="lead sheet")
        result = _decide_chapter_78(product)
        self.assertEqual(result["chapter"], 78)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_unwrought(self):
        product = _make_product(name="unwrought lead ingot", essence="lead unwrought")
        result = _decide_chapter_78(product)
        self.assertEqual(result["chapter"], 78)


class TestChapter79Zinc(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_79_candidate("zinc alloy ingot"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_79_candidate("אבץ"))
    def test_negative(self):
        self.assertFalse(_is_chapter_79_candidate("silk fabric"))
    def test_decide(self):
        product = _make_product(name="zinc dust powder flakes", essence="zinc dust")
        result = _decide_chapter_79(product)
        self.assertEqual(result["chapter"], 79)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_unwrought(self):
        product = _make_product(name="zinc unwrought ingot slab", essence="zinc unwrought")
        result = _decide_chapter_79(product)
        self.assertEqual(result["chapter"], 79)


class TestChapter80Tin(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_80_candidate("tin unwrought ingot"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_80_candidate("בדיל"))
    def test_negative(self):
        self.assertFalse(_is_chapter_80_candidate("rubber tyre"))
    def test_decide(self):
        product = _make_product(name="tin bar rod profile", essence="tin bar")
        result = _decide_chapter_80(product)
        self.assertEqual(result["chapter"], 80)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_unwrought(self):
        product = _make_product(name="tin unwrought alloy", essence="tin unwrought")
        result = _decide_chapter_80(product)
        self.assertEqual(result["chapter"], 80)


class TestChapter81OtherBaseMetals(unittest.TestCase):
    def test_candidate_tungsten(self):
        self.assertTrue(_is_chapter_81_candidate("tungsten carbide"))
    def test_candidate_titanium(self):
        self.assertTrue(_is_chapter_81_candidate("titanium alloy"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_81_candidate("טיטניום"))
    def test_negative(self):
        self.assertFalse(_is_chapter_81_candidate("cotton shirt"))
    def test_decide_tungsten(self):
        product = _make_product(name="tungsten bar rod", essence="tungsten")
        result = _decide_chapter_81(product)
        self.assertEqual(result["chapter"], 81)
        self.assertTrue(len(result["candidates"]) > 0)


class TestChapter82ToolsCutlery(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_82_candidate("kitchen knife blade"))
    def test_candidate_saw(self):
        self.assertTrue(_is_chapter_82_candidate("hand saw blade"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_82_candidate("סכין"))
    def test_negative(self):
        self.assertFalse(_is_chapter_82_candidate("ceramic tile"))
    def test_decide_knife(self):
        product = _make_product(name="kitchen knife chef blade stainless", essence="knife blade")
        result = _decide_chapter_82(product)
        self.assertEqual(result["chapter"], 82)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_spoon(self):
        product = _make_product(name="stainless steel spoon fork set", essence="cutlery spoon fork")
        result = _decide_chapter_82(product)
        self.assertEqual(result["chapter"], 82)
    def test_decide_saw(self):
        product = _make_product(name="hand saw wood cutting blade", essence="saw blade")
        result = _decide_chapter_82(product)
        self.assertEqual(result["chapter"], 82)


class TestChapter83MiscBaseMetal(unittest.TestCase):
    def test_candidate_lock(self):
        self.assertTrue(_is_chapter_83_candidate("padlock key lock"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_83_candidate("מנעול"))
    def test_negative(self):
        self.assertFalse(_is_chapter_83_candidate("paper notebook"))
    def test_decide_lock(self):
        product = _make_product(name="padlock brass key lock", essence="padlock key")
        result = _decide_chapter_83(product)
        self.assertEqual(result["chapter"], 83)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_hinge(self):
        product = _make_product(name="door hinge steel mounting hardware", essence="hinge mounting")
        result = _decide_chapter_83(product)
        self.assertEqual(result["chapter"], 83)


# ============================================================================
# CHAPTERS 84-85: Machinery and electrical
# ============================================================================

class TestChapter84Machinery(unittest.TestCase):
    def test_candidate_pump(self):
        self.assertTrue(_is_chapter_84_candidate("centrifugal pump industrial"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_84_candidate("משאבה תעשייתית"))
    def test_negative(self):
        self.assertFalse(_is_chapter_84_candidate("silk scarf"))
    def test_decide_boiler(self):
        product = _make_product(name="steam boiler industrial", essence="boiler steam")
        result = _decide_chapter_84(product)
        self.assertEqual(result["chapter"], 84)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_pump(self):
        product = _make_product(name="centrifugal pump water industrial", essence="pump centrifugal")
        result = _decide_chapter_84(product)
        self.assertEqual(result["chapter"], 84)
    def test_decide_compressor(self):
        product = _make_product(name="air compressor piston industrial", essence="compressor air")
        result = _decide_chapter_84(product)
        self.assertEqual(result["chapter"], 84)
    def test_decide_washing_machine(self):
        product = _make_product(name="washing machine automatic laundry", essence="washing machine")
        result = _decide_chapter_84(product)
        self.assertEqual(result["chapter"], 84)
    def test_decide_computer(self):
        product = _make_product(name="laptop computer portable data processing", essence="computer laptop")
        result = _decide_chapter_84(product)
        self.assertEqual(result["chapter"], 84)
    def test_decide_bearing(self):
        product = _make_product(name="ball bearing roller bearing", essence="bearing roller ball")
        result = _decide_chapter_84(product)
        self.assertEqual(result["chapter"], 84)
    def test_decide_air_conditioning(self):
        product = _make_product(name="air conditioning unit split system", essence="air conditioner")
        result = _decide_chapter_84(product)
        self.assertEqual(result["chapter"], 84)


class TestChapter85Electrical(unittest.TestCase):
    def test_candidate_motor(self):
        self.assertTrue(_is_chapter_85_candidate("electric motor generator"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_85_candidate("מנוע חשמלי"))
    def test_negative(self):
        self.assertFalse(_is_chapter_85_candidate("wooden table"))
    def test_decide_motor(self):
        product = _make_product(name="electric motor AC induction", essence="electric motor")
        result = _decide_chapter_85(product)
        self.assertEqual(result["chapter"], 85)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_transformer(self):
        product = _make_product(name="electrical transformer power supply", essence="transformer")
        result = _decide_chapter_85(product)
        self.assertEqual(result["chapter"], 85)
    def test_decide_battery(self):
        product = _make_product(name="lithium-ion battery rechargeable", essence="battery lithium-ion")
        result = _decide_chapter_85(product)
        self.assertEqual(result["chapter"], 85)
    def test_decide_phone(self):
        product = _make_product(name="smartphone mobile telephone", essence="telephone smartphone")
        result = _decide_chapter_85(product)
        self.assertEqual(result["chapter"], 85)
    def test_decide_semiconductor(self):
        product = _make_product(name="semiconductor integrated circuit chip", essence="IC chip semiconductor")
        result = _decide_chapter_85(product)
        self.assertEqual(result["chapter"], 85)
    def test_decide_cable(self):
        product = _make_product(name="electric cable wire insulated copper", essence="electric cable wire")
        result = _decide_chapter_85(product)
        self.assertEqual(result["chapter"], 85)
    def test_decide_solar_panel(self):
        product = _make_product(name="solar panel photovoltaic module", essence="solar panel photovoltaic")
        result = _decide_chapter_85(product)
        self.assertEqual(result["chapter"], 85)


# ============================================================================
# CHAPTERS 86-89: Transport
# ============================================================================

class TestChapter86Railway(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_86_candidate("railway locomotive diesel"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_86_candidate("קטר רכבת"))
    def test_negative(self):
        self.assertFalse(_is_chapter_86_candidate("leather shoes"))
    def test_decide_locomotive(self):
        product = _make_product(name="diesel locomotive railway engine", essence="locomotive diesel")
        result = _decide_chapter_86(product)
        self.assertEqual(result["chapter"], 86)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_wagon(self):
        product = _make_product(name="railway freight wagon car", essence="railway wagon freight")
        result = _decide_chapter_86(product)
        self.assertEqual(result["chapter"], 86)


class TestChapter87Vehicles(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_87_candidate("passenger automobile sedan"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_87_candidate("רכב נוסעים"))
    def test_negative(self):
        self.assertFalse(_is_chapter_87_candidate("ceramic plate"))
    def test_decide_car(self):
        product = _make_product(name="passenger car sedan petrol engine 1500cc", essence="automobile car petrol")
        result = _decide_chapter_87(product)
        self.assertEqual(result["chapter"], 87)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_truck(self):
        product = _make_product(name="cargo truck diesel 10 ton", essence="truck diesel cargo")
        result = _decide_chapter_87(product)
        self.assertEqual(result["chapter"], 87)
    def test_decide_bicycle(self):
        product = _make_product(name="bicycle mountain bike pedal", essence="bicycle pedal")
        result = _decide_chapter_87(product)
        self.assertEqual(result["chapter"], 87)
    def test_decide_motorcycle(self):
        product = _make_product(name="motorcycle 250cc engine", essence="motorcycle")
        result = _decide_chapter_87(product)
        self.assertEqual(result["chapter"], 87)
    def test_decide_electric_vehicle(self):
        product = _make_product(name="electric vehicle BEV passenger", essence="electric car vehicle")
        result = _decide_chapter_87(product)
        self.assertEqual(result["chapter"], 87)


class TestChapter88Aircraft(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_88_candidate("aeroplane aircraft passenger"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_88_candidate("מטוס"))
    def test_negative(self):
        self.assertFalse(_is_chapter_88_candidate("sugar candy"))
    def test_decide_helicopter(self):
        product = _make_product(name="helicopter rotorcraft", essence="helicopter")
        result = _decide_chapter_88(product)
        self.assertEqual(result["chapter"], 88)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_drone(self):
        product = _make_product(name="unmanned aerial vehicle drone UAV", essence="drone UAV")
        result = _decide_chapter_88(product)
        self.assertEqual(result["chapter"], 88)


class TestChapter89Ships(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_89_candidate("cargo ship vessel"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_89_candidate("ספינה"))
    def test_negative(self):
        self.assertFalse(_is_chapter_89_candidate("glass window"))
    def test_decide_yacht(self):
        product = _make_product(name="sailing yacht pleasure boat", essence="yacht sailing")
        result = _decide_chapter_89(product)
        self.assertEqual(result["chapter"], 89)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_cargo(self):
        product = _make_product(name="cargo vessel bulk carrier ship", essence="cargo ship vessel")
        result = _decide_chapter_89(product)
        self.assertEqual(result["chapter"], 89)


# ============================================================================
# CHAPTERS 90-92: Instruments and clocks
# ============================================================================

class TestChapter90Instruments(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_90_candidate("microscope optical"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_90_candidate("מיקרוסקופ"))
    def test_negative(self):
        self.assertFalse(_is_chapter_90_candidate("cotton fabric"))
    def test_decide_lens(self):
        product = _make_product(name="optical lens eyeglass spectacle", essence="lens optical")
        result = _decide_chapter_90(product)
        self.assertEqual(result["chapter"], 90)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_medical(self):
        product = _make_product(name="medical surgical instrument scalpel", essence="surgical instrument")
        result = _decide_chapter_90(product)
        self.assertEqual(result["chapter"], 90)
    def test_decide_xray(self):
        product = _make_product(name="X-ray apparatus medical imaging", essence="X-ray apparatus")
        result = _decide_chapter_90(product)
        self.assertEqual(result["chapter"], 90)
    def test_decide_thermometer(self):
        product = _make_product(name="thermometer temperature measuring instrument", essence="thermometer measuring")
        result = _decide_chapter_90(product)
        self.assertEqual(result["chapter"], 90)
    def test_decide_spectacles(self):
        product = _make_product(name="spectacles eyeglasses corrective prescription", essence="spectacles eyeglasses")
        result = _decide_chapter_90(product)
        self.assertEqual(result["chapter"], 90)


class TestChapter91Clocks(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_91_candidate("wrist watch mechanical"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_91_candidate("שעון יד"))
    def test_negative(self):
        self.assertFalse(_is_chapter_91_candidate("rubber tube"))
    def test_decide_wristwatch(self):
        product = _make_product(name="wrist watch mechanical automatic", essence="wrist watch")
        result = _decide_chapter_91(product)
        self.assertEqual(result["chapter"], 91)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_clock(self):
        product = _make_product(name="wall clock pendulum", essence="clock wall")
        result = _decide_chapter_91(product)
        self.assertEqual(result["chapter"], 91)


class TestChapter92Musical(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_92_candidate("piano grand acoustic"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_92_candidate("פסנתר"))
    def test_negative(self):
        self.assertFalse(_is_chapter_92_candidate("steel plate"))
    def test_decide_piano(self):
        product = _make_product(name="grand piano acoustic upright", essence="piano acoustic")
        result = _decide_chapter_92(product)
        self.assertEqual(result["chapter"], 92)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_guitar(self):
        product = _make_product(name="acoustic guitar string instrument", essence="guitar acoustic")
        result = _decide_chapter_92(product)
        self.assertEqual(result["chapter"], 92)
    def test_decide_drum(self):
        product = _make_product(name="drum kit percussion snare", essence="drum percussion")
        result = _decide_chapter_92(product)
        self.assertEqual(result["chapter"], 92)


# ============================================================================
# CHAPTERS 93-97: Arms, furniture, toys, misc, art
# ============================================================================

class TestChapter93Arms(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_93_candidate("rifle sporting hunting"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_93_candidate("רובה"))
    def test_negative(self):
        self.assertFalse(_is_chapter_93_candidate("coffee beans"))
    def test_decide_pistol(self):
        product = _make_product(name="revolver pistol handgun", essence="pistol revolver")
        result = _decide_chapter_93(product)
        self.assertEqual(result["chapter"], 93)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_ammunition(self):
        product = _make_product(name="ammunition cartridge bullet round", essence="ammunition cartridge")
        result = _decide_chapter_93(product)
        self.assertEqual(result["chapter"], 93)


class TestChapter94Furniture(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_94_candidate("wooden chair office"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_94_candidate("כיסא"))
    def test_negative(self):
        self.assertFalse(_is_chapter_94_candidate("aluminium foil"))
    def test_decide_chair(self):
        product = _make_product(name="office chair swivel ergonomic", essence="chair office")
        result = _decide_chapter_94(product)
        self.assertEqual(result["chapter"], 94)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_mattress(self):
        product = _make_product(name="spring mattress foam bed", essence="mattress")
        result = _decide_chapter_94(product)
        self.assertEqual(result["chapter"], 94)
    def test_decide_lamp(self):
        product = _make_product(name="table lamp desk lighting fixture", essence="lamp lighting")
        result = _decide_chapter_94(product)
        self.assertEqual(result["chapter"], 94)
    def test_decide_sofa(self):
        product = _make_product(name="leather sofa couch upholstered", essence="sofa couch")
        result = _decide_chapter_94(product)
        self.assertEqual(result["chapter"], 94)


class TestChapter95Toys(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_95_candidate("children toy doll"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_95_candidate("צעצוע"))
    def test_negative(self):
        self.assertFalse(_is_chapter_95_candidate("copper wire"))
    def test_decide_doll(self):
        product = _make_product(name="doll toy plastic children", essence="doll toy")
        result = _decide_chapter_95(product)
        self.assertEqual(result["chapter"], 95)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_board_game(self):
        product = _make_product(name="board game puzzle chess", essence="board game puzzle")
        result = _decide_chapter_95(product)
        self.assertEqual(result["chapter"], 95)
    def test_decide_sports(self):
        product = _make_product(name="tennis racket sports equipment", essence="racket tennis sports")
        result = _decide_chapter_95(product)
        self.assertEqual(result["chapter"], 95)


class TestChapter96MiscManufactured(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_96_candidate("ballpoint pen writing"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_96_candidate("עט כדורי"))
    def test_negative(self):
        self.assertFalse(_is_chapter_96_candidate("salmon fish"))
    def test_decide_pen(self):
        product = _make_product(name="ballpoint pen writing instrument", essence="pen ballpoint")
        result = _decide_chapter_96(product)
        self.assertEqual(result["chapter"], 96)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_button(self):
        product = _make_product(name="button snap fastener plastic", essence="button fastener")
        result = _decide_chapter_96(product)
        self.assertEqual(result["chapter"], 96)
    def test_decide_zipper(self):
        product = _make_product(name="slide fastener zipper metal", essence="zipper fastener")
        result = _decide_chapter_96(product)
        self.assertEqual(result["chapter"], 96)
    def test_decide_brush(self):
        product = _make_product(name="paint brush bristle artist", essence="brush painting")
        result = _decide_chapter_96(product)
        self.assertEqual(result["chapter"], 96)
    def test_decide_lighter(self):
        product = _make_product(name="cigarette lighter disposable gas", essence="lighter")
        result = _decide_chapter_96(product)
        self.assertEqual(result["chapter"], 96)


class TestChapter97Art(unittest.TestCase):
    def test_candidate(self):
        self.assertTrue(_is_chapter_97_candidate("oil painting canvas original"))
    def test_candidate_hebrew(self):
        self.assertTrue(_is_chapter_97_candidate("ציור שמן"))
    def test_negative(self):
        self.assertFalse(_is_chapter_97_candidate("steel pipe"))
    def test_decide_painting(self):
        product = _make_product(name="original oil painting canvas artwork", essence="painting oil canvas")
        result = _decide_chapter_97(product)
        self.assertEqual(result["chapter"], 97)
        self.assertTrue(len(result["candidates"]) > 0)
    def test_decide_sculpture(self):
        product = _make_product(name="bronze sculpture statue original", essence="sculpture statue")
        result = _decide_chapter_97(product)
        self.assertEqual(result["chapter"], 97)
    def test_decide_antique(self):
        product = _make_product(name="antique furniture 150 years old", essence="antique")
        result = _decide_chapter_97(product)
        self.assertEqual(result["chapter"], 97)


# ============================================================================
# Cross-chapter integration tests (73-97)
# ============================================================================

class TestChapters73to97Integration(unittest.TestCase):
    def test_available_chapters_includes_73_to_97(self):
        chapters = available_chapters()
        for ch in [73, 74, 75, 76, 78, 79, 80, 81, 82, 83, 84, 85,
                   86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97]:
            self.assertIn(ch, chapters)
        self.assertNotIn(77, chapters)  # reserved

    def test_decide_chapter_detects_steel_pipe(self):
        product = _make_product(name="seamless steel tube pipe", essence="steel pipe tube")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 73)

    def test_decide_chapter_detects_copper_wire(self):
        product = _make_product(name="refined copper wire cable", essence="copper wire")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 74)

    def test_decide_chapter_detects_aluminium_foil(self):
        product = _make_product(name="aluminium foil household kitchen", essence="aluminium foil")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 76)

    def test_decide_chapter_detects_knife(self):
        product = _make_product(name="kitchen knife stainless steel chef", essence="knife blade stainless")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 82)

    def test_decide_chapter_detects_padlock(self):
        product = _make_product(name="padlock brass combination", essence="padlock lock")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 83)

    def test_decide_chapter_detects_pump(self):
        product = _make_product(name="centrifugal water pump industrial", essence="pump centrifugal")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 84)

    def test_decide_chapter_detects_electric_motor(self):
        product = _make_product(name="AC electric motor induction", essence="electric motor AC")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 85)

    def test_decide_chapter_detects_car(self):
        product = _make_product(name="passenger car sedan petrol 2000cc", essence="automobile car")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 87)

    def test_decide_chapter_detects_aircraft(self):
        product = _make_product(name="aeroplane passenger aircraft", essence="aeroplane aircraft")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 88)

    def test_decide_chapter_detects_ship(self):
        product = _make_product(name="cargo ship bulk carrier vessel", essence="cargo ship vessel")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 89)

    def test_decide_chapter_detects_microscope(self):
        product = _make_product(name="optical microscope laboratory", essence="microscope optical")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 90)

    def test_decide_chapter_detects_wristwatch(self):
        product = _make_product(name="wrist watch automatic mechanical", essence="wrist watch")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 91)

    def test_decide_chapter_detects_piano(self):
        product = _make_product(name="grand piano acoustic upright", essence="piano acoustic")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 92)

    def test_decide_chapter_detects_rifle(self):
        product = _make_product(name="hunting rifle sporting firearm", essence="rifle sporting")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 93)

    def test_decide_chapter_detects_chair(self):
        product = _make_product(name="office chair ergonomic swivel", essence="chair office")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 94)

    def test_decide_chapter_detects_toy(self):
        product = _make_product(name="children plastic toy doll", essence="toy doll")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 95)

    def test_decide_chapter_detects_pen(self):
        product = _make_product(name="ballpoint pen writing instrument", essence="pen ballpoint")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 96)

    def test_decide_chapter_detects_painting(self):
        product = _make_product(name="original oil painting canvas fine art", essence="painting oil canvas")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 97)


# ============================================================================
# Chapter 98: Israeli personal import exemptions
# ============================================================================

class TestChapter98Detection(unittest.TestCase):
    def test_candidate_returning_resident(self):
        self.assertTrue(_is_chapter_98_candidate("תושב חוזר מביא רהיטים"))
    def test_candidate_new_immigrant(self):
        self.assertTrue(_is_chapter_98_candidate("עולה חדש importing furniture"))
    def test_candidate_english(self):
        self.assertTrue(_is_chapter_98_candidate("returning resident personal import"))
    def test_candidate_gift(self):
        self.assertTrue(_is_chapter_98_candidate("gift package from abroad"))
    def test_candidate_personal_import(self):
        self.assertTrue(_is_chapter_98_candidate("personal effects household goods"))
    def test_negative(self):
        self.assertFalse(_is_chapter_98_candidate("industrial steel pipe"))

class TestChapter98Decision(unittest.TestCase):
    def test_decide_furniture_returning_resident(self):
        product = _make_product(name="furniture sofa תושב חוזר", essence="furniture personal import")
        result = _decide_chapter_98(product)
        self.assertEqual(result["chapter"], 98)
        self.assertTrue(len(result["candidates"]) > 0)
        self.assertEqual(result["candidates"][0]["heading"], "98.01")
        self.assertEqual(result["candidates"][0]["subheading_hint"], "9801400000")
    def test_decide_gift_package(self):
        product = _make_product(name="gift package from family abroad", essence="gift present")
        result = _decide_chapter_98(product)
        self.assertEqual(result["chapter"], 98)
        self.assertEqual(result["candidates"][0]["heading"], "98.02")
    def test_decide_vehicle_relocation(self):
        product = _make_product(name="vehicle relocation personal car import", essence="car personal")
        result = _decide_chapter_98(product)
        self.assertEqual(result["chapter"], 98)
        self.assertEqual(result["candidates"][0]["heading"], "98.03")
        self.assertTrue(len(result["questions_needed"]) > 0)
    def test_decide_new_immigrant_clothing(self):
        product = _make_product(name="עולה חדש clothing textiles shirts", essence="clothing textiles")
        result = _decide_chapter_98(product)
        self.assertEqual(result["chapter"], 98)
        self.assertEqual(result["candidates"][0]["subheading_hint"], "9801100000")
    def test_decide_professional_equipment(self):
        product = _make_product(name="professional equipment tools of trade", essence="professional tools")
        result = _decide_chapter_98(product)
        self.assertEqual(result["chapter"], 98)
        self.assertEqual(result["candidates"][0]["heading"], "98.01")
    def test_decide_personal_import_general(self):
        product = _make_product(name="personal effects household import תכולת דירה", essence="household effects")
        result = _decide_chapter_98(product)
        self.assertEqual(result["chapter"], 98)
    def test_decide_footwear_oleh(self):
        product = _make_product(name="shoes boots oleh chadash import", essence="footwear shoes")
        result = _decide_chapter_98(product)
        self.assertEqual(result["chapter"], 98)
        self.assertEqual(result["candidates"][0]["subheading_hint"], "9801200000")


# ============================================================================
# Chapter 99: Israeli temporary provisions and special quotas
# ============================================================================

class TestChapter99Detection(unittest.TestCase):
    def test_candidate_disaster_relief(self):
        self.assertTrue(_is_chapter_99_candidate("disaster relief humanitarian aid"))
    def test_candidate_disaster_hebrew(self):
        self.assertTrue(_is_chapter_99_candidate("סיוע באסון"))
    def test_candidate_coffin(self):
        self.assertTrue(_is_chapter_99_candidate("coffin containing remains repatriation"))
    def test_candidate_chapter_99_ref(self):
        self.assertTrue(_is_chapter_99_candidate("chapter 99 temporary provision"))
    def test_negative(self):
        self.assertFalse(_is_chapter_99_candidate("steel wire industrial"))

class TestChapter99Decision(unittest.TestCase):
    def test_decide_disaster_relief(self):
        product = _make_product(name="disaster relief supplies humanitarian aid", essence="emergency supplies")
        result = _decide_chapter_99(product)
        self.assertEqual(result["chapter"], 99)
        self.assertTrue(len(result["candidates"]) > 0)
        self.assertEqual(result["candidates"][0]["heading"], "99.01")
    def test_decide_coffin_remains(self):
        product = _make_product(name="coffin containing remains of deceased repatriation", essence="coffin remains")
        result = _decide_chapter_99(product)
        self.assertEqual(result["chapter"], 99)
        self.assertEqual(result["candidates"][0]["heading"], "99.02")
    def test_decide_coffin_hebrew(self):
        product = _make_product(name="ארון קבורה עם גופה", essence="ארון קבורה")
        result = _decide_chapter_99(product)
        self.assertEqual(result["chapter"], 99)
        self.assertEqual(result["candidates"][0]["heading"], "99.02")
    def test_decide_general_ch99(self):
        product = _make_product(name="chapter 99 special provision", essence="special provision")
        result = _decide_chapter_99(product)
        self.assertEqual(result["chapter"], 99)
        self.assertTrue(len(result["questions_needed"]) > 0)
    def test_decide_humanitarian_hebrew(self):
        product = _make_product(name="סיוע הומניטרי חירום", essence="humanitarian aid")
        result = _decide_chapter_99(product)
        self.assertEqual(result["chapter"], 99)
        self.assertEqual(result["candidates"][0]["heading"], "99.01")


# ============================================================================
# Cross-chapter integration tests (98-99)
# ============================================================================

class TestChapters98to99Integration(unittest.TestCase):
    def test_available_chapters_includes_98_99(self):
        chapters = available_chapters()
        self.assertIn(98, chapters)
        self.assertIn(99, chapters)
        self.assertNotIn(77, chapters)  # reserved

    def test_decide_chapter_detects_returning_resident(self):
        product = _make_product(name="תושב חוזר רהיטים furniture", essence="furniture returning resident")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 98)

    def test_decide_chapter_detects_disaster_relief(self):
        product = _make_product(name="disaster relief humanitarian supplies", essence="disaster relief")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 99)

    def test_decide_chapter_detects_coffin(self):
        product = _make_product(name="coffin containing remains repatriation", essence="coffin remains")
        result = decide_chapter(product)
        self.assertIsNotNone(result)
        self.assertEqual(result["chapter"], 99)


if __name__ == "__main__":
    unittest.main()
