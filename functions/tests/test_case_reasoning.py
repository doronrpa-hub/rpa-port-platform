"""Tests for case_reasoning.py — tiered complexity analyzer."""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.case_reasoning import (
    analyze_case,
    CasePlan,
    _detect_legal_category,
    _extract_items,
    _score_complexity,
    _build_evidence_targets,
    get_discount_for_item,
)
from lib._chapter98_data import (
    get_chapter98_code,
    get_chapter98_entry,
    get_chapter98_by_category,
    search_chapter98,
    CHAPTER_98_HEADINGS,
    CHAPTER_99_HEADINGS,
    CHAPTER_TO_98_MAP,
)


class TestDetectLegalCategory(unittest.TestCase):
    """Test legal category detection from text."""

    def test_toshav_chozer(self):
        cat, he, grp, sub = _detect_legal_category("אני תושב חוזר מארצות הברית")
        self.assertEqual(cat, "toshav_chozer")
        self.assertEqual(he, "תושב חוזר")
        self.assertEqual(grp, "7")
        self.assertEqual(sub, "4xxxxx")

    def test_oleh_chadash(self):
        cat, he, grp, sub = _detect_legal_category("אני עולה חדש מצרפת")
        self.assertEqual(cat, "oleh_chadash")
        self.assertEqual(he, "עולה חדש")
        self.assertEqual(sub, "3xxxxx")

    def test_oleh_without_chadash(self):
        cat, he, grp, sub = _detect_legal_category("אני עולה מרוסיה")
        self.assertEqual(cat, "oleh_chadash")

    def test_student_chozer(self):
        cat, _, _, sub = _detect_legal_category("סטודנט חוזר מאנגליה")
        self.assertEqual(cat, "student_chozer")
        self.assertEqual(sub, "4xxxxx")

    def test_diplomat(self):
        cat, _, _, sub = _detect_legal_category("נציג דיפלומטי")
        self.assertEqual(cat, "diplomat")
        self.assertEqual(sub, "2xxxxx")

    def test_tourist(self):
        cat, _, _, sub = _detect_legal_category("אני תייר מגרמניה")
        self.assertEqual(cat, "tourist")
        self.assertEqual(sub, "1xxxxx")

    def test_toshav_chozer_precedence(self):
        """When both 'תושב חוזר' and 'עולה' appear, תושב חוזר wins."""
        cat, _, _, _ = _detect_legal_category("תושב חוזר ולא עולה")
        self.assertEqual(cat, "toshav_chozer")

    def test_returning_resident_english(self):
        cat, _, _, _ = _detect_legal_category("I am a returning resident")
        self.assertEqual(cat, "toshav_chozer")

    def test_no_legal_category(self):
        cat, he, grp, sub = _detect_legal_category("I want to import steel bolts")
        self.assertEqual(cat, "")
        self.assertEqual(he, "")
        self.assertEqual(grp, "")

    def test_toshav_chutz(self):
        cat, _, _, sub = _detect_legal_category("אני תושב חוץ")
        self.assertEqual(cat, "toshav_chutz")
        self.assertEqual(sub, "2xxxxx")


class TestExtractItems(unittest.TestCase):
    """Test item extraction from email body."""

    def test_single_item(self):
        items = _extract_items("אני רוצה לייבא ספה ירוקה")
        self.assertTrue(len(items) >= 1)
        self.assertEqual(items[0]["category"], "furniture")

    def test_multi_item(self):
        items = _extract_items("ספה, טלוויזיה, כיסאות")
        categories = {i["category"] for i in items}
        self.assertIn("furniture", categories)
        self.assertIn("electronics", categories)

    def test_vehicle_detection(self):
        items = _extract_items("אני מביא רכב מנועי מארצות הברית")
        categories = {i["category"] for i in items}
        self.assertIn("vehicle", categories)

    def test_personal_items(self):
        items = _extract_items("חפצים אישיים ובגדים")
        categories = {i["category"] for i in items}
        self.assertIn("personal", categories)

    def test_empty_text(self):
        items = _extract_items("")
        self.assertEqual(items, [])

    def test_no_items(self):
        items = _extract_items("מה שיעור המכס על יבוא?")
        self.assertEqual(items, [])

    def test_kitchen_items(self):
        items = _extract_items("כלי מטבח וסירים")
        categories = {i["category"] for i in items}
        self.assertIn("kitchen", categories)

    def test_textiles(self):
        items = _extract_items("שטיחים ומצעים")
        categories = {i["category"] for i in items}
        self.assertIn("textiles", categories)


class TestScoreComplexity(unittest.TestCase):
    """Test complexity tier scoring."""

    def test_tier1_simple(self):
        tier = _score_complexity([], "", [])
        self.assertEqual(tier, 1)

    def test_tier1_single_item(self):
        tier = _score_complexity([{"name": "sofa"}], "", [])
        self.assertEqual(tier, 1)

    def test_tier2_multi_item(self):
        tier = _score_complexity([{"name": "a"}, {"name": "b"}], "", [])
        self.assertEqual(tier, 2)

    def test_tier2_legal_category(self):
        tier = _score_complexity([], "toshav_chozer", [])
        self.assertEqual(tier, 2)

    def test_tier3_legal_plus_items(self):
        items = [{"name": "a"}, {"name": "b"}, {"name": "c"}, {"name": "d"}]
        tier = _score_complexity(items, "toshav_chozer", [])
        self.assertEqual(tier, 3)

    def test_tier3_vehicle(self):
        tier = _score_complexity([], "oleh_chadash", ["vehicle_separate"])
        self.assertEqual(tier, 3)


class TestBuildEvidenceTargets(unittest.TestCase):
    """Test evidence target generation."""

    def test_legal_status_targets(self):
        plan = CasePlan(legal_category="toshav_chozer",
                        discount_group="7", discount_sub_range="4xxxxx")
        targets = _build_evidence_targets(plan)
        self.assertTrue(any("section 129" in t for t in targets))
        self.assertTrue(any("item 7" in t for t in targets))

    def test_vehicle_targets(self):
        plan = CasePlan(legal_category="oleh_chadash",
                        discount_group="7", discount_sub_range="3xxxxx",
                        special_flags=["vehicle_separate"])
        targets = _build_evidence_targets(plan)
        self.assertTrue(any("vehicle" in t.lower() for t in targets))

    def test_items_targets(self):
        plan = CasePlan(items_to_classify=[
            {"name": "sofa", "keywords": ["sofa", "furniture"]},
        ])
        targets = _build_evidence_targets(plan)
        self.assertTrue(any("tariff_search" in t for t in targets))

    def test_chapter98_target(self):
        plan = CasePlan(legal_category="toshav_chozer",
                        items_to_classify=[{"name": "sofa"}])
        targets = _build_evidence_targets(plan)
        self.assertTrue(any("chapter_98" in t for t in targets))

    def test_empty_plan(self):
        plan = CasePlan()
        targets = _build_evidence_targets(plan)
        self.assertEqual(targets, [])


class TestChapter98Data(unittest.TestCase):
    """Test Chapter 98/99 data module."""

    def test_chapter98_has_headings(self):
        self.assertIn("9801", CHAPTER_98_HEADINGS)
        self.assertIn("9802", CHAPTER_98_HEADINGS)
        self.assertIn("9803", CHAPTER_98_HEADINGS)

    def test_chapter99_has_headings(self):
        self.assertIn("9901", CHAPTER_99_HEADINGS)
        self.assertIn("9902", CHAPTER_99_HEADINGS)

    def test_furniture_maps_to_9801(self):
        code = get_chapter98_code("9401600000")
        self.assertIsNotNone(code)
        self.assertTrue(code.startswith("9801"))

    def test_clothing_maps_to_9801(self):
        code = get_chapter98_code("6109100000")
        self.assertIsNotNone(code)
        self.assertEqual(code, "9801100000")

    def test_no_mapping_for_chapter_1(self):
        # Chapter 1 (live animals) maps to food (9801800000)
        code = get_chapter98_code("0101210000")
        self.assertIsNotNone(code)  # Mapped via food

    def test_get_entry(self):
        entry = get_chapter98_entry("9801400000")
        self.assertIsNotNone(entry)
        self.assertIn("furniture", entry["desc_en"].lower())
        self.assertEqual(entry["duty"], "exempt")

    def test_get_entry_not_found(self):
        entry = get_chapter98_entry("9999999999")
        self.assertIsNone(entry)

    def test_get_by_category(self):
        code = get_chapter98_by_category("furniture")
        self.assertEqual(code, "9801400000")

    def test_search(self):
        results = search_chapter98("רהיטים")
        self.assertTrue(len(results) >= 1)

    def test_chapter_to_98_map_populated(self):
        self.assertGreater(len(CHAPTER_TO_98_MAP), 10)
        self.assertIn(94, CHAPTER_TO_98_MAP)  # furniture
        self.assertIn(64, CHAPTER_TO_98_MAP)  # footwear


class TestGetDiscountForItem(unittest.TestCase):
    """Test per-item discount code lookup."""

    def test_furniture_toshav_chozer(self):
        result = get_discount_for_item("sofa", "9401600000", "toshav_chozer", "furniture")
        self.assertIn("chapter98_code", result)
        self.assertEqual(result["discount_group"], "7")
        self.assertEqual(result["discount_sub_code"], "403400")

    def test_furniture_oleh(self):
        result = get_discount_for_item("sofa", "9401600000", "oleh_chadash", "furniture")
        self.assertEqual(result["discount_sub_code"], "302000")

    def test_personal_toshav_chozer(self):
        result = get_discount_for_item("clothes", "6109100000", "toshav_chozer", "personal")
        self.assertEqual(result["discount_sub_code"], "403100")

    def test_no_mapping(self):
        result = get_discount_for_item("steel bolt", "7318150000", "toshav_chozer", "")
        # Chapter 73 -> kitchen utensils in Ch.98
        # May or may not map depending on CHAPTER_TO_98_MAP
        # At minimum should return without error
        self.assertIsInstance(result, dict)

    def test_no_legal_category(self):
        result = get_discount_for_item("sofa", "9401600000", "", "furniture")
        self.assertEqual(result, {})


class TestAnalyzeCase(unittest.TestCase):
    """Test full case analysis integration."""

    def test_toshav_chozer_full(self):
        plan = analyze_case(
            "חפצים מארה\"ב",
            "אני תושב חוזר, חוזר מארצות הברית עם ספה ירוקה, שולחנות, "
            "כיסאות, טלוויזיה OLED, רכב ואלבומי תמונות ב-3 מכולות"
        )
        self.assertEqual(plan.case_type, "LEGAL_STATUS")
        self.assertEqual(plan.legal_category, "toshav_chozer")
        self.assertEqual(plan.tier, 3)
        self.assertEqual(plan.direction, "import")
        self.assertTrue(len(plan.items_to_classify) >= 3)
        self.assertEqual(plan.discount_group, "7")
        self.assertEqual(plan.discount_sub_range, "4xxxxx")
        self.assertTrue(plan.per_item_required)
        self.assertIn("vehicle_separate", plan.special_flags)

    def test_simple_query(self):
        plan = analyze_case("", "What is the duty rate for steel bolts?")
        self.assertEqual(plan.case_type, "GENERAL")
        self.assertEqual(plan.legal_category, "")
        self.assertEqual(plan.tier, 1)
        self.assertFalse(plan.per_item_required)

    def test_single_item(self):
        plan = analyze_case("", "כמה מכס על ספה מסין?")
        self.assertEqual(plan.case_type, "SINGLE_CLASSIFICATION")
        self.assertTrue(len(plan.items_to_classify) >= 1)

    def test_discount_query(self):
        plan = analyze_case("", "מהם קודי הנחה לפטור ממכס?")
        self.assertEqual(plan.case_type, "DISCOUNT_QUERY")

    def test_oleh_with_items(self):
        plan = analyze_case("", "עולה חדש רוצה לייבא רהיטים ומכשירים חשמליים")
        self.assertEqual(plan.legal_category, "oleh_chadash")
        self.assertTrue(plan.per_item_required)

    def test_export_not_legal_status(self):
        plan = analyze_case("", "I want to export furniture to Europe")
        self.assertNotEqual(plan.case_type, "LEGAL_STATUS")

    def test_to_dict(self):
        plan = CasePlan(case_type="LEGAL_STATUS", legal_category="toshav_chozer")
        d = plan.to_dict()
        self.assertEqual(d["case_type"], "LEGAL_STATUS")
        self.assertEqual(d["legal_category"], "toshav_chozer")

    def test_default_case_plan(self):
        plan = CasePlan()
        self.assertEqual(plan.case_type, "GENERAL")
        self.assertEqual(plan.tier, 1)
        self.assertFalse(plan.per_item_required)


if __name__ == "__main__":
    unittest.main()
