# -*- coding: utf-8 -*-
"""Tests for _hs_reverse_index.py — discount code + FTA reverse lookups."""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib._hs_reverse_index import (
    get_discount_codes,
    get_fta_rates,
    get_discount_index_stats,
    _to_heading,
    _HS_DOTTED_RE,
    _extract_headings_from_text,
    _keyword_chapters_from_text,
)


class TestToHeading(unittest.TestCase):
    """Test _to_heading — normalizes any HS format to 4-digit heading."""

    def test_dotted_4digit(self):
        self.assertEqual(_to_heading("87.11"), "8711")

    def test_dotted_8digit(self):
        self.assertEqual(_to_heading("07.12.9010"), "0712")

    def test_dotted_6digit(self):
        self.assertEqual(_to_heading("60.04.1000"), "6004")

    def test_short_heading(self):
        self.assertEqual(_to_heading("49.03"), "4903")

    def test_raw_10digit(self):
        self.assertEqual(_to_heading("8711300000"), "8711")

    def test_israeli_format(self):
        self.assertEqual(_to_heading("87.11.300000/9"), "8711")


class TestHsDottedRegex(unittest.TestCase):
    """Test the regex pattern that extracts HS codes from Hebrew text."""

    def test_simple_heading(self):
        matches = _HS_DOTTED_RE.findall("שבפרט 87.11")
        self.assertIn("87.11", matches)

    def test_full_code(self):
        matches = _HS_DOTTED_RE.findall("שבפרט 07.12.9010")
        self.assertIn("07.12.9010", matches)

    def test_multiple_codes(self):
        text = "פרטים 60.04, 60.06 שיוצאו לצביעה, או תכשיטים 71.13"
        matches = _HS_DOTTED_RE.findall(text)
        self.assertIn("60.04", matches)
        self.assertIn("60.06", matches)
        self.assertIn("71.13", matches)


class TestExtractHeadings(unittest.TestCase):
    """Test multi-layer heading extraction from Hebrew descriptions."""

    def test_dotted_codes(self):
        headings = _extract_headings_from_text("שבפרט 87.11 ו-87.12")
        self.assertIn("8711", headings)
        self.assertIn("8712", headings)

    def test_chapter_ref(self):
        headings = _extract_headings_from_text("פרק 87")
        self.assertIn("ch87", headings)

    def test_chapter_list(self):
        headings = _extract_headings_from_text("פרקים 84, 85, 88, 90")
        for ch in ["ch84", "ch85", "ch88", "ch90"]:
            self.assertIn(ch, headings)

    def test_section_ref(self):
        headings = _extract_headings_from_text("חלק XVI")
        # Section XVI = chapters 84-85
        self.assertIn("ch84", headings)
        self.assertIn("ch85", headings)


class TestKeywordChapters(unittest.TestCase):
    """Test Hebrew keyword -> chapter matching."""

    def test_vehicle_keyword(self):
        chapters = _keyword_chapters_from_text("רכב נוסעים")
        self.assertIn("ch87", chapters)

    def test_pharmaceutical_keyword(self):
        chapters = _keyword_chapters_from_text("תרופות")
        self.assertIn("ch30", chapters)

    def test_textile_keyword(self):
        chapters = _keyword_chapters_from_text("טקסטיל")
        self.assertIn("ch50", chapters)
        self.assertIn("ch63", chapters)


class TestGetDiscountCodes(unittest.TestCase):
    """Test discount code lookups by HS heading."""

    def test_motorcycle_heading_8711(self):
        """Item 7 sub-codes 312000/321000 explicitly reference 87.11 headings."""
        results = get_discount_codes("8711")
        self.assertTrue(len(results) > 0, "Expected discount codes for heading 8711")
        # Sub-codes 312000 and 321000 under item 7 reference 87.11 motorcycles
        found = any(
            r["item"] == "7" and r.get("sub_code") in ("312000", "321000")
            for r in results
        )
        self.assertTrue(found, f"Expected item 7 sub-code 312000 or 321000 in results")

    def test_dotted_format(self):
        """Accept dotted format input."""
        results = get_discount_codes("87.11")
        self.assertTrue(len(results) > 0)

    def test_full_10digit(self):
        """Accept full 10-digit code, extract heading."""
        results = get_discount_codes("8711300000")
        self.assertTrue(len(results) > 0)

    def test_israeli_format(self):
        """Accept Israeli XX.XX.XXXXXX/X format."""
        results = get_discount_codes("87.11.300000/9")
        self.assertTrue(len(results) > 0)

    def test_no_results_heading(self):
        """Some headings have no discount codes — should return empty list."""
        results = get_discount_codes("0101")  # Live horses — unlikely discount
        # May or may not have results, just ensure no crash
        self.assertIsInstance(results, list)

    def test_group4_country_specific(self):
        """Group 4 items like 901 (dried garlic 07.12) should appear."""
        results = get_discount_codes("0712")
        items = {r["item"] for r in results}
        self.assertIn("901", items, "Item 901 (dried garlic) should map to heading 0712")

    def test_entry_fields(self):
        """Each result entry has required fields."""
        results = get_discount_codes("8711")
        if results:
            entry = results[0]
            for field in ("item", "group", "description", "customs_duty", "purchase_tax"):
                self.assertIn(field, entry, f"Missing field: {field}")

    def test_chapter_level_match(self):
        """Keyword-based chapter matches should appear for headings in that chapter."""
        # Chapter 87 keywords (רכב, אופנוע) should yield results for any ch87 heading
        results = get_discount_codes("8703")
        self.assertTrue(len(results) > 0, "Expected chapter-level discount codes for 8703")


class TestGetFtaRates(unittest.TestCase):
    """Test FTA country info lookup."""

    def test_returns_all_16_countries(self):
        rates = get_fta_rates("8711")
        self.assertEqual(len(rates), 16, f"Expected 16 FTA countries, got {len(rates)}")

    def test_country_fields(self):
        """Each country entry has required metadata."""
        rates = get_fta_rates("0101")
        for code, info in rates.items():
            self.assertIn("origin_proof", info, f"Missing origin_proof for {code}")
            self.assertIn("name_en", info, f"Missing name_en for {code}")
            self.assertIn("agreement_name", info, f"Missing agreement_name for {code}")

    def test_eu_has_eur1(self):
        rates = get_fta_rates("0101")
        self.assertEqual(rates["eu"]["origin_proof"], "EUR.1")

    def test_usa_has_invoice_declaration(self):
        rates = get_fta_rates("0101")
        self.assertEqual(rates["usa"]["origin_proof"], "Invoice Declaration")


class TestDiscountIndexStats(unittest.TestCase):
    """Test the index statistics function."""

    def test_stats_structure(self):
        stats = get_discount_index_stats()
        self.assertIn("total_headings", stats)
        self.assertIn("total_entries", stats)
        self.assertIn("sections_covered", stats)
        self.assertGreater(stats["total_headings"], 0, "Index should cover some headings")
        self.assertGreater(stats["total_entries"], 0, "Index should have entries")

    def test_known_headings_covered(self):
        """Headings explicitly referenced in discount codes should be indexed."""
        stats = get_discount_index_stats()
        headings = set(stats["headings"])
        # These are explicitly referenced in the data
        for h in ["8711", "8710", "4903", "3705"]:
            self.assertIn(h, headings, f"Heading {h} should be in index")

    def test_section_coverage(self):
        """Should cover many of the 22 tariff sections via keyword extraction."""
        stats = get_discount_index_stats()
        self.assertGreaterEqual(
            stats["sections_covered"], 10,
            f"Expected >= 10 sections covered, got {stats['sections_covered']}"
        )


if __name__ == "__main__":
    unittest.main()
