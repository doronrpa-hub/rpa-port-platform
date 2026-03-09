"""Tests for Chapter Decision Trees — Sessions 98-99.

Chapter 03 (Session 98): 5 mandatory test cases + edge cases.
Chapters 01, 02, 04, 05 (Session 99): species/product routing + gate tests.
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
    _detect_creature_type,
    _detect_crustacean_species,
    _detect_ch01_species,
    _detect_ch02_species,
    _detect_ch04_product_type,
    _detect_ch05_product_type,
    _get_processing_state,
    _is_fillet,
    _is_peeled,
    _is_chapter_01_candidate,
    _is_chapter_02_candidate,
    _is_chapter_03_candidate,
    _is_chapter_04_candidate,
    _is_chapter_05_candidate,
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
        self.assertIn(1, chapters)
        self.assertIn(2, chapters)
        self.assertIn(3, chapters)
        self.assertIn(4, chapters)
        self.assertIn(5, chapters)
        self.assertEqual(len(chapters), 5)

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


if __name__ == "__main__":
    unittest.main()
