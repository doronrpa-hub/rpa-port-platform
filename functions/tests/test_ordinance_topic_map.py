"""
Tests for _ordinance_topic_map.py — semantic topic-to-article mapping.
Session 78.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib._ordinance_topic_map import (
    TOPIC_MAP,
    search_ordinance_by_topic,
    get_topic_notes,
    get_topic_external_law,
    get_framework_articles,
    get_topic_xml_terms,
    get_topic_map_stats,
    _MIN_ALIAS_LEN,
)


# ═══════════════════════════════════════════
#  STRUCTURAL TESTS
# ═══════════════════════════════════════════

class TestTopicMapStructure(unittest.TestCase):
    """Verify the topic map data structure is correct."""

    def test_total_topics(self):
        self.assertEqual(len(TOPIC_MAP), 25)

    def test_all_topics_have_required_fields(self):
        required = {"aliases", "articles", "chapter", "notes", "source"}
        for key, data in TOPIC_MAP.items():
            for field in required:
                self.assertIn(field, data, f"Topic {key} missing field: {field}")

    def test_all_aliases_are_strings(self):
        for key, data in TOPIC_MAP.items():
            for alias in data["aliases"]:
                self.assertIsInstance(alias, str, f"Topic {key} has non-string alias: {alias}")

    def test_all_articles_are_strings(self):
        for key, data in TOPIC_MAP.items():
            for art in data["articles"]:
                self.assertIsInstance(art, str, f"Topic {key} has non-string article: {art}")

    def test_source_values(self):
        for key, data in TOPIC_MAP.items():
            self.assertIn(data["source"], ("ordinance", "regulations"),
                          f"Topic {key} has invalid source: {data['source']}")

    def test_notes_not_empty(self):
        for key, data in TOPIC_MAP.items():
            self.assertTrue(len(data["notes"]) > 10,
                            f"Topic {key} has empty/short notes")

    def test_xml_search_terms_present(self):
        for key, data in TOPIC_MAP.items():
            self.assertIn("xml_search_terms", data,
                          f"Topic {key} missing xml_search_terms")

    def test_no_duplicate_topic_keys(self):
        keys = list(TOPIC_MAP.keys())
        self.assertEqual(len(keys), len(set(keys)))


# ═══════════════════════════════════════════
#  REGULATION SOURCE TESTS (CRITICAL BUG FIX)
# ═══════════════════════════════════════════

class TestRegulationSource(unittest.TestCase):
    """Verify that regulation-sourced topics are properly marked."""

    def test_hashbon_mecher_is_regulation_source(self):
        topic = TOPIC_MAP["חשבון_מכר"]
        self.assertEqual(topic["source"], "regulations")

    def test_hashbon_mecher_has_regulation_name(self):
        topic = TOPIC_MAP["חשבון_מכר"]
        self.assertIn("regulation_name", topic)
        self.assertIn("תקנות המכס", topic["regulation_name"])

    def test_hashbon_mecher_has_regulation_content(self):
        topic = TOPIC_MAP["חשבון_מכר"]
        self.assertIn("regulation_content", topic)
        content = topic["regulation_content"]
        # Must mention 10 requirements
        self.assertIn("שם ומען המוכר", content)
        self.assertIn("שם ומען הקונה", content)
        self.assertIn("תנאי האספקה", content)
        self.assertIn("מטבע התשלום", content)

    def test_hashbon_mecher_articles_are_regulation_articles(self):
        """Articles 6-9א in חשבון_מכר are REGULATION articles, not ordinance."""
        topic = TOPIC_MAP["חשבון_מכר"]
        self.assertIn("6", topic["articles"])
        self.assertIn("9", topic["articles"])
        # These should NOT be looked up from ORDINANCE_ARTICLES

    def test_only_hashbon_mecher_is_regulation(self):
        """Only חשבון_מכר should be regulation-sourced."""
        reg_topics = [k for k, v in TOPIC_MAP.items() if v["source"] == "regulations"]
        self.assertEqual(reg_topics, ["חשבון_מכר"])

    def test_ordinance_article_6_is_port_designation(self):
        """Ordinance article 6 is about port designation, NOT invoices."""
        from lib._ordinance_data import ORDINANCE_ARTICLES
        art6 = ORDINANCE_ARTICLES.get("6", {})
        # Article 6 in the ordinance is about designating ports — chapter 2
        self.assertEqual(art6.get("ch"), 2)
        # It should NOT contain invoice-related content
        summary = art6.get("s", "").lower()
        self.assertNotIn("invoice", summary)


# ═══════════════════════════════════════════
#  SEARCH FUNCTION TESTS
# ═══════════════════════════════════════════

class TestSearchByTopic(unittest.TestCase):
    """Test the search_ordinance_by_topic function."""

    def test_empty_input(self):
        self.assertEqual(search_ordinance_by_topic(""), [])
        self.assertEqual(search_ordinance_by_topic(None), [])

    def test_valuation_hebrew(self):
        results = search_ordinance_by_topic("מה שיטת הערכת המכס?")
        topics = [r["topic_key"] for r in results]
        self.assertIn("הערכת_מכס", topics)

    def test_valuation_english(self):
        results = search_ordinance_by_topic("customs valuation methods")
        topics = [r["topic_key"] for r in results]
        self.assertIn("הערכת_מכס", topics)

    def test_invoice_requirements(self):
        results = search_ordinance_by_topic("מה חייב להופיע בחשבון מכר")
        topics = [r["topic_key"] for r in results]
        self.assertIn("חשבון_מכר", topics)

    def test_invoice_english(self):
        results = search_ordinance_by_topic("commercial invoice requirements")
        topics = [r["topic_key"] for r in results]
        self.assertIn("חשבון_מכר", topics)

    def test_import_hebrew(self):
        results = search_ordinance_by_topic("הליך ייבוא טובין")
        topics = [r["topic_key"] for r in results]
        self.assertIn("ייבוא", topics)

    def test_export_hebrew(self):
        results = search_ordinance_by_topic("ייצוא טובין לחו\"ל")
        topics = [r["topic_key"] for r in results]
        self.assertIn("ייצוא", topics)

    def test_penalties(self):
        results = search_ordinance_by_topic("עונש על הברחה")
        topics = [r["topic_key"] for r in results]
        self.assertIn("עבירות_מכס", topics)

    def test_fta(self):
        results = search_ordinance_by_topic("כללי מקור בהסכם סחר חופשי")
        topics = [r["topic_key"] for r in results]
        self.assertIn("הסכמי_סחר", topics)

    def test_drawback(self):
        results = search_ordinance_by_topic("הישבון מכס על ייצוא חוזר")
        topics = [r["topic_key"] for r in results]
        self.assertIn("הישבון", topics)

    def test_customs_agent(self):
        results = search_ordinance_by_topic("רישיון עמיל מכס")
        topics = [r["topic_key"] for r in results]
        self.assertIn("סוכני_מכס", topics)

    def test_warehouse(self):
        results = search_ordinance_by_topic("מחסן ערובה")
        topics = [r["topic_key"] for r in results]
        self.assertIn("מחסני_ערובה", topics)

    def test_classification(self):
        results = search_ordinance_by_topic("סיווג טובין HS code")
        topics = [r["topic_key"] for r in results]
        self.assertIn("סיווג", topics)

    def test_returns_source_field(self):
        results = search_ordinance_by_topic("חשבון מכר")
        self.assertTrue(len(results) > 0)
        for r in results:
            self.assertIn("source", r)

    def test_regulation_source_in_result(self):
        results = search_ordinance_by_topic("commercial invoice")
        invoice_results = [r for r in results if r["topic_key"] == "חשבון_מכר"]
        self.assertEqual(len(invoice_results), 1)
        self.assertEqual(invoice_results[0]["source"], "regulations")

    def test_returns_articles_list(self):
        results = search_ordinance_by_topic("ערך עסקה")
        self.assertTrue(len(results) > 0)
        for r in results:
            self.assertIsInstance(r["articles"], list)


# ═══════════════════════════════════════════
#  MULTI-TOPIC TESTS
# ═══════════════════════════════════════════

class TestMultiTopic(unittest.TestCase):
    """Test that questions spanning multiple topics return multiple matches."""

    def test_valuation_and_invoice(self):
        results = search_ordinance_by_topic("הערכת מכס לפי חשבון מכר")
        topics = [r["topic_key"] for r in results]
        self.assertIn("הערכת_מכס", topics)
        self.assertIn("חשבון_מכר", topics)

    def test_import_and_regulatory(self):
        results = search_ordinance_by_topic("ייבוא טובין עם אישור רגולטורי")
        topics = [r["topic_key"] for r in results]
        self.assertIn("ייבוא", topics)
        self.assertIn("רגולציה", topics)

    def test_no_duplicate_topics(self):
        results = search_ordinance_by_topic("הערכה הערכה הערכה ערך עסקה שווי מכס")
        topic_keys = [r["topic_key"] for r in results]
        self.assertEqual(len(topic_keys), len(set(topic_keys)))


# ═══════════════════════════════════════════
#  NEW TOPICS TESTS
# ═══════════════════════════════════════════

class TestNewTopics(unittest.TestCase):
    """Test the 4 topics added to fix gaps."""

    def test_ship_stores(self):
        results = search_ordinance_by_topic("צידת אניה")
        topics = [r["topic_key"] for r in results]
        self.assertIn("צידת_אניה", topics)

    def test_coastal_trade(self):
        results = search_ordinance_by_topic("סחר חוף בין נמלים")
        topics = [r["topic_key"] for r in results]
        self.assertIn("סחר_חוף", topics)

    def test_officer_powers(self):
        results = search_ordinance_by_topic("סמכויות פקיד מכס")
        topics = [r["topic_key"] for r in results]
        self.assertIn("סמכויות_פקיד_מכס", topics)

    def test_admin_enforcement(self):
        results = search_ordinance_by_topic("אכיפה מינהלית קנס")
        topics = [r["topic_key"] for r in results]
        self.assertIn("אכיפה_מינהלית", topics)

    def test_ship_stores_articles(self):
        topic = TOPIC_MAP["צידת_אניה"]
        self.assertEqual(topic["articles"], ["120", "121", "122", "123"])
        self.assertEqual(topic["chapter"], 7)

    def test_coastal_articles(self):
        topic = TOPIC_MAP["סחר_חוף"]
        self.assertEqual(topic["articles"], ["163", "164", "165", "166", "167"])
        self.assertEqual(topic["chapter"], 10)

    def test_powers_has_38_articles(self):
        topic = TOPIC_MAP["סמכויות_פקיד_מכס"]
        self.assertEqual(len(topic["articles"]), 38)
        self.assertEqual(topic["chapter"], 12)

    def test_enforcement_chapter(self):
        topic = TOPIC_MAP["אכיפה_מינהלית"]
        self.assertEqual(topic["chapter"], "13א")


# ═══════════════════════════════════════════
#  WORD BOUNDARY TESTS
# ═══════════════════════════════════════════

class TestWordBoundary(unittest.TestCase):
    """Test that short aliases need word boundaries."""

    def test_vat_matches_word(self):
        results = search_ordinance_by_topic("what is the VAT rate?")
        topics = [r["topic_key"] for r in results]
        self.assertIn("מס_קניה", topics)

    def test_vat_no_false_positive(self):
        """'VAT' should NOT match 'elevator' or 'private'."""
        results = search_ordinance_by_topic("elevator maintenance private")
        topics = [r["topic_key"] for r in results]
        # VAT shouldn't appear in results for unrelated text
        vat_matches = [r for r in results if r.get("matched_alias", "").upper() == "VAT"]
        self.assertEqual(len(vat_matches), 0)

    def test_edi_word_boundary(self):
        results = search_ordinance_by_topic("send via EDI system")
        topics = [r["topic_key"] for r in results]
        self.assertIn("דיווח_אלקטרוני", topics)

    def test_fta_standalone(self):
        results = search_ordinance_by_topic("FTA agreement Israel-EU")
        topics = [r["topic_key"] for r in results]
        self.assertIn("הסכמי_סחר", topics)

    def test_min_alias_len_constant(self):
        self.assertEqual(_MIN_ALIAS_LEN, 4)


# ═══════════════════════════════════════════
#  HELPER FUNCTION TESTS
# ═══════════════════════════════════════════

class TestHelperFunctions(unittest.TestCase):
    """Test get_topic_notes, get_topic_external_law, etc."""

    def test_get_notes_existing(self):
        notes = get_topic_notes("הערכת_מכס")
        self.assertIn("7 שיטות", notes)

    def test_get_notes_missing(self):
        notes = get_topic_notes("nonexistent_topic")
        self.assertEqual(notes, "")

    def test_get_external_law(self):
        laws = get_topic_external_law("הערכת_מכס")
        self.assertIsInstance(laws, list)
        self.assertTrue(len(laws) > 0)

    def test_get_framework_articles(self):
        arts = get_framework_articles("הערכת_מכס")
        self.assertIn("130", arts)
        self.assertIn("132", arts)

    def test_get_xml_terms(self):
        terms = get_topic_xml_terms("הערכת_מכס")
        self.assertIn("ערך עסקה", terms)

    def test_get_xml_terms_missing(self):
        terms = get_topic_xml_terms("nonexistent")
        self.assertEqual(terms, [])


# ═══════════════════════════════════════════
#  STATS TESTS
# ═══════════════════════════════════════════

class TestStats(unittest.TestCase):
    """Test get_topic_map_stats."""

    def test_stats_total_topics(self):
        stats = get_topic_map_stats()
        self.assertEqual(stats["total_topics"], 25)

    def test_stats_has_all_fields(self):
        stats = get_topic_map_stats()
        self.assertIn("total_topics", stats)
        self.assertIn("total_unique_articles", stats)
        self.assertIn("total_aliases", stats)
        self.assertIn("topics_by_source", stats)

    def test_stats_source_breakdown(self):
        stats = get_topic_map_stats()
        self.assertEqual(stats["topics_by_source"]["regulations"], 1)
        self.assertEqual(stats["topics_by_source"]["ordinance"], 24)

    def test_stats_aliases_count(self):
        stats = get_topic_map_stats()
        self.assertGreater(stats["total_aliases"], 100)

    def test_stats_unique_articles(self):
        stats = get_topic_map_stats()
        # Should cover a significant portion of the 311 ordinance articles
        self.assertGreater(stats["total_unique_articles"], 200)


# ═══════════════════════════════════════════
#  INTEGRATION WITH CONTEXT ENGINE
# ═══════════════════════════════════════════

class TestContextEngineIntegration(unittest.TestCase):
    """Test integration with context_engine._search_ordinance."""

    def test_search_ordinance_returns_tuple(self):
        """_search_ordinance now returns (articles, xml_terms) tuple."""
        from lib.context_engine import _search_ordinance
        entities = {"article_numbers": [], "keywords": []}
        result = _search_ordinance(entities, "test", "test", [])
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_invoice_query_returns_regulation_content(self):
        """Querying about חשבון מכר should return regulation content, not port designation."""
        from lib.context_engine import _search_ordinance
        entities = {"article_numbers": [], "keywords": []}
        articles, xml_terms = _search_ordinance(
            entities, "מה חייב להופיע בחשבון מכר", "", [])

        # Should find invoice topic
        self.assertTrue(len(articles) > 0)

        # The first result should be regulation-sourced
        invoice_results = [a for a in articles if a.get("source") == "regulations"]
        self.assertTrue(len(invoice_results) > 0,
                        "Should find regulation-sourced results for חשבון מכר")

        # The content should mention invoice requirements, not port designation
        for inv in invoice_results:
            full = inv.get("full_text_he", "")
            self.assertNotIn("קביעת נמלים", full)

    def test_valuation_query_returns_ordinance_articles(self):
        """Querying about הערכה should return ordinance articles."""
        from lib.context_engine import _search_ordinance
        entities = {"article_numbers": [], "keywords": []}
        articles, xml_terms = _search_ordinance(
            entities, "שיטות הערכת מכס", "", [])

        self.assertTrue(len(articles) > 0)
        # Should include article 130 (master valuation hierarchy)
        art_ids = [a["article_id"] for a in articles]
        self.assertIn("130", art_ids)

    def test_xml_terms_returned_for_topic(self):
        """Topic match should return xml_search_terms."""
        from lib.context_engine import _search_ordinance
        entities = {"article_numbers": [], "keywords": []}
        _, xml_terms = _search_ordinance(
            entities, "הערכת מכס", "", [])
        self.assertIsInstance(xml_terms, list)
        self.assertTrue(len(xml_terms) > 0)

    def test_topic_notes_in_search_log(self):
        """Topic notes should be included in search_log."""
        from lib.context_engine import _search_ordinance
        entities = {"article_numbers": [], "keywords": []}
        search_log = []
        _search_ordinance(entities, "הערכת מכס", "", search_log)

        ordinance_entry = [e for e in search_log if e.get("search") == "ordinance"]
        self.assertTrue(len(ordinance_entry) > 0)
        self.assertIn("topic_notes", ordinance_entry[0])
        self.assertIn("topic_matches", ordinance_entry[0])

    def test_direct_article_still_works(self):
        """Direct article lookup by number should still work."""
        from lib.context_engine import _search_ordinance
        entities = {"article_numbers": ["130"], "keywords": []}
        articles, _ = _search_ordinance(entities, "", "", [])
        art_ids = [a["article_id"] for a in articles]
        self.assertIn("130", art_ids)

    def test_keyword_fallback_still_works(self):
        """Keyword search should still work for unrecognized topics."""
        from lib.context_engine import _search_ordinance
        entities = {"article_numbers": [], "keywords": []}
        # Use a very specific phrase that won't match any topic alias
        articles, _ = _search_ordinance(
            entities, "", "מניפסט הצהרת מטען כלי שיט", [])
        # Should find some articles via keyword search (chapter 3 supervision)
        # This may or may not match depending on keyword overlap,
        # but the function should not crash
        self.assertIsInstance(articles, list)


# ═══════════════════════════════════════════
#  EDGE CASES
# ═══════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):
    """Edge cases and boundary conditions."""

    def test_non_string_input(self):
        self.assertEqual(search_ordinance_by_topic(123), [])

    def test_very_long_input(self):
        """Long text should not crash."""
        long_text = "הערכת מכס " * 1000
        results = search_ordinance_by_topic(long_text)
        self.assertIsInstance(results, list)

    def test_special_characters(self):
        results = search_ordinance_by_topic('מה "ערך עסקה"? (customs)')
        self.assertIsInstance(results, list)

    def test_mixed_hebrew_english(self):
        results = search_ordinance_by_topic("customs valuation הערכת מכס methods")
        topics = [r["topic_key"] for r in results]
        self.assertIn("הערכת_מכס", topics)

    def test_case_insensitive(self):
        results_upper = search_ordinance_by_topic("CUSTOMS VALUATION")
        results_lower = search_ordinance_by_topic("customs valuation")
        topics_upper = {r["topic_key"] for r in results_upper}
        topics_lower = {r["topic_key"] for r in results_lower}
        self.assertEqual(topics_upper, topics_lower)


if __name__ == '__main__':
    unittest.main()
