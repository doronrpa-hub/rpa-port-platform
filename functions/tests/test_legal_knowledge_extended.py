"""Tests for extended search_legal_knowledge: discount codes + procedures.

Cases tested:
  F1: Direct discount code lookup (6-digit sub-code)
  F2: Discount item/group lookup (קוד הנחה NNN)
  F3: Discount code keyword search
  G1: Procedure lookup by number
  G1b: Procedure lookup by name alias (תש"ר, הערכה, סיווג)
  G2: Procedure keyword search
  Existing: Article, framework order, chapter still work
"""
import unittest
from unittest.mock import MagicMock


def _make_executor():
    """Build a ToolExecutor with mocked Firestore db."""
    from lib.tool_executors import ToolExecutor
    mock_db = MagicMock()
    # _get_legal_knowledge reads from legal_knowledge collection
    mock_db.collection.return_value.stream.return_value = iter([])
    return ToolExecutor(db=mock_db, api_key=None)


class TestDiscountCodeLookup(unittest.TestCase):
    """Case F1: Direct 6-digit sub-code lookup."""

    def setUp(self):
        self.te = _make_executor()

    def test_code_100000_found(self):
        """Sub-code 100000 exists under item 3."""
        r = self.te.execute("search_legal_knowledge", {"query": "100000"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["type"], "discount_code")
        self.assertIn("code", r)
        self.assertEqual(r["code"], "100000")
        self.assertIn("item_number", r)

    def test_code_has_duty_status(self):
        r = self.te.execute("search_legal_knowledge", {"query": "100000"})
        self.assertIn("duty", r)

    def test_nonexistent_code_falls_through(self):
        """A 6-digit number not in discount codes should not crash."""
        r = self.te.execute("search_legal_knowledge", {"query": "999999"})
        # Should fall through to other search cases (not crash)
        self.assertIsInstance(r, dict)


class TestDiscountGroupLookup(unittest.TestCase):
    """Case F2: Item/group lookup by number."""

    def setUp(self):
        self.te = _make_executor()

    def test_item_810_found(self):
        """Item 810 has 14 sub-codes."""
        r = self.te.execute("search_legal_knowledge", {"query": "קוד הנחה 810"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["type"], "discount_group")
        self.assertIn("codes_count", r)
        self.assertIn("codes", r)
        self.assertGreater(r["codes_count"], 0)

    def test_item_3_found(self):
        r = self.te.execute("search_legal_knowledge", {"query": "פרט מכס 3"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["type"], "discount_group")

    def test_nonexistent_item_falls_through(self):
        r = self.te.execute("search_legal_knowledge", {"query": "קוד הנחה 99999"})
        # Falls through to other cases or returns not found
        self.assertIsInstance(r, dict)


class TestDiscountCodeSearch(unittest.TestCase):
    """Case F3: Keyword search across discount codes."""

    def setUp(self):
        self.te = _make_executor()

    def test_search_vehicle(self):
        """'רכב' should match discount codes mentioning vehicles."""
        r = self.te.execute("search_legal_knowledge", {"query": "פטור רכב"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["type"], "discount_code_search")
        self.assertGreater(r["count"], 0)
        self.assertIn("results", r)

    def test_search_diplomatic(self):
        r = self.te.execute("search_legal_knowledge", {"query": "הנחה נציגויות"})
        self.assertTrue(r.get("found"))


class TestProcedureLookup(unittest.TestCase):
    """Case G1: Procedure lookup by number and name."""

    def setUp(self):
        self.te = _make_executor()

    def test_procedure_3_by_number(self):
        r = self.te.execute("search_legal_knowledge", {"query": "נוהל 3"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["type"], "customs_procedure")
        self.assertEqual(r["procedure_number"], "3")
        self.assertIn("סיווג", r["name_he"])
        self.assertIn("full_text", r)
        self.assertGreater(len(r["full_text"]), 100)

    def test_procedure_1_by_number(self):
        r = self.te.execute("search_legal_knowledge", {"query": "procedure 1"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["type"], "customs_procedure")
        self.assertEqual(r["procedure_number"], "1")
        self.assertIn("full_text", r)

    def test_procedure_by_name_tashar(self):
        r = self.te.execute("search_legal_knowledge", {"query": "תשר"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["type"], "customs_procedure")
        self.assertEqual(r["procedure_number"], "1")

    def test_procedure_by_name_valuation(self):
        r = self.te.execute("search_legal_knowledge", {"query": "הליך הערכה"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["type"], "customs_procedure")
        self.assertEqual(r["procedure_number"], "2")

    def test_procedure_by_name_classification(self):
        r = self.te.execute("search_legal_knowledge", {"query": "הליך סיווג"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["type"], "customs_procedure")
        self.assertEqual(r["procedure_number"], "3")

    def test_procedure_25_declarants(self):
        r = self.te.execute("search_legal_knowledge", {"query": "נוהל 25"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["procedure_number"], "25")
        self.assertIn("מצהרים", r["name_he"])

    def test_procedure_28_conditions(self):
        r = self.te.execute("search_legal_knowledge", {"query": "נוהל 28"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["procedure_number"], "28")

    def test_procedure_10_personal_import(self):
        r = self.te.execute("search_legal_knowledge", {"query": "נוהל 10"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["procedure_number"], "10")
        self.assertIn("יבוא אישי", r["name_he"])

    def test_nonexistent_procedure(self):
        r = self.te.execute("search_legal_knowledge", {"query": "נוהל 99"})
        # Falls through to other cases
        self.assertIsInstance(r, dict)


class TestProcedureSearch(unittest.TestCase):
    """Case G2: Procedure keyword search."""

    def setUp(self):
        self.te = _make_executor()

    def test_search_invoice(self):
        r = self.te.execute("search_legal_knowledge", {"query": "נוהל חשבון מכר"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["type"], "procedure_search")
        self.assertGreater(r["count"], 0)
        self.assertIn("results", r)
        # Should have snippets
        first = r["results"][0]
        self.assertIn("snippets", first)

    def test_search_declaration(self):
        r = self.te.execute("search_legal_knowledge", {"query": "procedure הצהרת יבוא"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["type"], "procedure_search")


class TestExistingCasesStillWork(unittest.TestCase):
    """Verify existing Cases A-E are not broken by new Cases F-G."""

    def setUp(self):
        self.te = _make_executor()

    def test_article_130_still_works(self):
        r = self.te.execute("search_legal_knowledge", {"query": "סעיף 130"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["type"], "ordinance_article")
        self.assertEqual(r["article_id"], "130")

    def test_chapter_8_still_works(self):
        r = self.te.execute("search_legal_knowledge", {"query": "פרק 8"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["type"], "ordinance_chapter_articles")

    def test_framework_order_still_works(self):
        r = self.te.execute("search_legal_knowledge", {"query": "צו מסגרת 14"})
        self.assertTrue(r.get("found"))
        self.assertEqual(r["type"], "framework_order_article")

    def test_keyword_search_still_works(self):
        r = self.te.execute("search_legal_knowledge", {"query": "ערך עסקה"})
        self.assertTrue(r.get("found"))


class TestDataIntegrity(unittest.TestCase):
    """Verify the embedded data files are loadable and have expected content."""

    def test_discount_codes_import(self):
        from lib._discount_codes_data import DISCOUNT_CODES
        self.assertGreater(len(DISCOUNT_CODES), 50)

    def test_discount_codes_helpers(self):
        from lib._discount_codes_data import get_discount_code, get_sub_code, search_discount_codes
        item = get_discount_code("810")
        self.assertIsNotNone(item)
        self.assertIn("sub_codes", item)

    def test_discount_sub_code(self):
        from lib._discount_codes_data import get_sub_code
        sub = get_sub_code("3", "100000")
        self.assertIsNotNone(sub)
        self.assertIn("customs_duty", sub)

    def test_procedures_import(self):
        from lib._procedures_data import PROCEDURES
        self.assertGreaterEqual(len(PROCEDURES), 6)  # 6 base + approved_exporter
        # All 6 base procedure numbers present
        for num in ["1", "2", "3", "10", "25", "28"]:
            self.assertIn(num, PROCEDURES, f"Procedure {num} missing")

    def test_procedures_helpers(self):
        from lib._procedures_data import get_procedure, search_procedures
        p = get_procedure(3)
        self.assertIsNotNone(p)
        self.assertIn("סיווג", p["name_he"])
        self.assertGreater(len(p["full_text"]), 1000)

    def test_procedures_search(self):
        from lib._procedures_data import search_procedures
        results = search_procedures("חשבון מכר")
        self.assertGreater(len(results), 0)
        self.assertIn("snippets", results[0])

    def test_framework_order_import(self):
        from lib._framework_order_data import FRAMEWORK_ORDER_ARTICLES
        self.assertGreater(len(FRAMEWORK_ORDER_ARTICLES), 25)
        # Check FTA fields exist
        art_17 = FRAMEWORK_ORDER_ARTICLES.get("17")
        self.assertIsNotNone(art_17)
        self.assertIn("fta", art_17)

    def test_ordinance_import(self):
        from lib._ordinance_data import ORDINANCE_ARTICLES
        self.assertEqual(len(ORDINANCE_ARTICLES), 311)


if __name__ == "__main__":
    unittest.main()
