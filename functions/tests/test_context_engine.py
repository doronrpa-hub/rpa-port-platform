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
    _detect_all_domains,
    _build_context_summary,
    _calculate_confidence,
    _plan_tool_calls,
    _build_tool_params,
    _store_tool_result,
    TOOL_ROUTING_MAP,
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

    # --- NEW: Location extraction ---
    def test_location_port_name(self):
        entities = _extract_entities("", "כמה זמן מנמל אשדוד")
        self.assertTrue(len(entities["locations"]) > 0)
        found = any("אשדוד" in loc for loc in entities["locations"])
        self.assertTrue(found, f"Expected אשדוד in {entities['locations']}")

    def test_location_haifa(self):
        entities = _extract_entities("", "vessel arrived at חיפה port")
        self.assertTrue(len(entities["locations"]) > 0)
        found = any("חיפה" in loc for loc in entities["locations"])
        self.assertTrue(found, f"Expected חיפה in {entities['locations']}")

    def test_location_place(self):
        entities = _extract_entities("", "נסיעה מקיבוץ ניר עוז לנמל אשדוד")
        # Should find ניר עוז and אשדוד
        self.assertTrue(len(entities["locations"]) >= 1)

    # --- NEW: Deadline extraction ---
    def test_deadline_hebrew(self):
        entities = _extract_entities("", "צריך להגיע עד השעה 22:00 היום")
        self.assertIn("22:00", entities["deadlines"])

    def test_deadline_english(self):
        entities = _extract_entities("", "must arrive by 18:30")
        self.assertIn("18:30", entities["deadlines"])

    # --- NEW: Amount extraction ---
    def test_amount_shekel(self):
        entities = _extract_entities("", "שווי 15000 ₪")
        self.assertTrue(len(entities["amounts"]) > 0)

    def test_amount_dollar(self):
        entities = _extract_entities("", "value $5,000 USD")
        self.assertTrue(len(entities["amounts"]) > 0)

    # --- NEW: All entity types present ---
    def test_entities_have_all_keys(self):
        entities = _extract_entities("", "test")
        for key in ["hs_codes", "product_names", "container_numbers", "bl_numbers",
                     "article_numbers", "keywords", "locations", "amounts", "deadlines"]:
            self.assertIn(key, entities)


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

    # --- NEW: Logistics domain ---
    def test_logistics_domain(self):
        entities = {"hs_codes": [], "product_names": [], "article_numbers": [],
                     "keywords": [], "locations": [], "deadlines": []}
        self.assertEqual(_detect_domain(entities, "", "כמה זמן לוקח הובלה מאשדוד"), "logistics")

    def test_logistics_domain_port(self):
        entities = {"hs_codes": [], "product_names": [], "article_numbers": [],
                     "keywords": [], "locations": [], "deadlines": []}
        self.assertEqual(_detect_domain(entities, "", "סגירת מכולות בנמל אשדוד"), "logistics")

    # --- NEW: Shipment domain ---
    def test_shipment_domain_container(self):
        entities = {"hs_codes": [], "product_names": [], "article_numbers": [],
                     "keywords": [], "container_numbers": ["MSCU1234567"], "bl_numbers": []}
        self.assertEqual(_detect_domain(entities, "", ""), "shipment")


class TestDetectAllDomains(unittest.TestCase):
    def test_single_domain(self):
        entities = {"hs_codes": ["84198110"], "product_names": [], "article_numbers": [],
                     "keywords": [], "locations": [], "deadlines": []}
        domains = _detect_all_domains(entities, "", "מה הסיווג של")
        self.assertIn("tariff", domains)

    def test_multi_domain_logistics_plus_ordinance(self):
        """The real test case: logistics + ordinance in one email."""
        entities = {"hs_codes": [], "product_names": [], "article_numbers": [],
                     "keywords": ["מכס"], "locations": ["אשדוד"], "deadlines": ["22:00"]}
        domains = _detect_all_domains(entities, "",
            "כמה זמן לוקח מאשדוד לנמל? בנוסף מה חייב לפי פקודת המכס להופיע בחשבון מכר")
        self.assertIn("logistics", domains)
        self.assertIn("ordinance", domains)

    def test_empty_falls_to_general(self):
        entities = {"hs_codes": [], "product_names": [], "article_numbers": [],
                     "keywords": [], "locations": [], "deadlines": []}
        domains = _detect_all_domains(entities, "", "hello")
        self.assertEqual(domains, ["general"])

    def test_tariff_and_regulatory(self):
        entities = {"hs_codes": ["84198110"], "product_names": [], "article_numbers": [],
                     "keywords": [], "locations": [], "deadlines": []}
        domains = _detect_all_domains(entities, "", "מה הסיווג ומה צו יבוא חופשי")
        self.assertIn("tariff", domains)
        self.assertIn("regulatory", domains)


class TestContextPackage(unittest.TestCase):
    def test_dataclass_defaults(self):
        pkg = ContextPackage(original_subject="test", original_body="body",
                             detected_language="he")
        self.assertEqual(pkg.domain, "general")
        self.assertEqual(pkg.confidence, 0.0)
        self.assertIsNone(pkg.cached_answer)
        self.assertEqual(pkg.tariff_results, [])

    def test_new_fields_defaults(self):
        pkg = ContextPackage(original_subject="test", original_body="body",
                             detected_language="he")
        self.assertEqual(pkg.logistics_results, [])
        self.assertEqual(pkg.shipment_results, [])
        self.assertEqual(pkg.other_tool_results, [])
        self.assertEqual(pkg.all_domains, [])

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

    # --- NEW: Confidence for logistics/shipment ---
    def test_confidence_logistics(self):
        pkg = ContextPackage(original_subject="test", original_body="body",
                             detected_language="he",
                             logistics_results=[{"duration_minutes": 60}])
        self.assertGreaterEqual(_calculate_confidence(pkg), 0.2)

    def test_confidence_shipment(self):
        pkg = ContextPackage(original_subject="test", original_body="body",
                             detected_language="he",
                             shipment_results=[{"bl_number": "TEST123"}])
        self.assertGreaterEqual(_calculate_confidence(pkg), 0.2)


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

    # --- NEW: Logistics in summary ---
    def test_with_logistics_route(self):
        pkg = ContextPackage(
            original_subject="test", original_body="body",
            detected_language="he", domain="logistics",
            entities={"hs_codes": [], "product_names": [], "keywords": [], "locations": ["אשדוד"]},
            logistics_results=[{"duration_minutes": 45, "distance_km": 32.5, "route_summary": "Route 4"}]
        )
        summary = _build_context_summary(pkg)
        self.assertIn("מידע לוגיסטי", summary)
        self.assertIn("45", summary)
        self.assertIn("32.5", summary)

    def test_with_shipment(self):
        pkg = ContextPackage(
            original_subject="test", original_body="body",
            detected_language="he", domain="shipment",
            entities={"hs_codes": [], "product_names": [], "keywords": []},
            shipment_results=[{"bl_number": "MEDURS12345", "status": "active",
                               "vessel": "ITAL WIT", "containers": ["MSCU1234567"]}]
        )
        summary = _build_context_summary(pkg)
        self.assertIn("מעקב משלוחים", summary)
        self.assertIn("MEDURS12345", summary)
        self.assertIn("ITAL WIT", summary)

    def test_with_other_tools(self):
        pkg = ContextPackage(
            original_subject="test", original_body="body",
            detected_language="he", domain="general",
            entities={"hs_codes": [], "product_names": [], "keywords": []},
            other_tool_results=[{"tool": "bank_of_israel_rates", "result": {"USD": 3.65}}]
        )
        summary = _build_context_summary(pkg)
        self.assertIn("מידע נוסף מכלים", summary)
        self.assertIn("bank_of_israel_rates", summary)

    def test_all_domains_shown(self):
        pkg = ContextPackage(
            original_subject="test", original_body="body",
            detected_language="he", domain="logistics",
            all_domains=["logistics", "ordinance"],
            entities={"hs_codes": [], "product_names": [], "keywords": []},
        )
        summary = _build_context_summary(pkg)
        self.assertIn("ordinance", summary)

    def test_locations_in_summary(self):
        pkg = ContextPackage(
            original_subject="test", original_body="body",
            detected_language="he", domain="logistics",
            entities={"hs_codes": [], "product_names": [], "keywords": [],
                      "locations": ["אשדוד (ILASD)"], "deadlines": ["22:00"]},
        )
        summary = _build_context_summary(pkg)
        self.assertIn("מיקומים", summary)
        self.assertIn("מועדים", summary)
        self.assertIn("22:00", summary)


class TestToolRoutingMap(unittest.TestCase):
    def test_all_tools_mapped(self):
        """Every tool in the dispatcher should be in TOOL_ROUTING_MAP."""
        # Known dispatcher tools from tool_executors.py
        dispatcher_tools = {
            "check_memory", "search_tariff", "check_regulatory", "lookup_fta",
            "verify_hs_code", "extract_invoice", "assess_risk",
            "get_chapter_notes", "lookup_tariff_structure", "lookup_framework_order",
            "search_classification_directives", "search_legal_knowledge",
            "run_elimination", "search_wikipedia", "search_wikidata",
            "lookup_country", "convert_currency", "search_comtrade",
            "lookup_food_product", "check_fda_product",
            "bank_of_israel_rates", "search_pubchem", "lookup_eu_taric",
            "lookup_usitc", "israel_cbs_trade", "lookup_gs1_barcode",
            "search_wco_notes", "lookup_unctad_gsp", "search_open_beauty",
            "crossref_technical", "check_opensanctions", "get_israel_vat_rates",
            "fetch_seller_website", "search_xml_documents",
        }
        mapped_tools = set(TOOL_ROUTING_MAP.keys())

        # Also include non-dispatcher tools that are routed directly
        mapped_plus_direct = mapped_tools | {"calculate_route_eta", "check_shipment_status", "get_port_schedule"}

        for tool in dispatcher_tools:
            self.assertIn(tool, mapped_plus_direct,
                          f"Tool {tool} in dispatcher but not in TOOL_ROUTING_MAP")

    def test_classification_tools_skipped(self):
        """Classification-only tools should have skip_in_sif=True."""
        classification_only = {"check_memory", "extract_invoice", "assess_risk",
                               "run_elimination", "fetch_seller_website",
                               "search_comtrade", "israel_cbs_trade", "crossref_technical"}
        for tool in classification_only:
            config = TOOL_ROUTING_MAP.get(tool, {})
            self.assertTrue(config.get("skip_in_sif"),
                            f"Tool {tool} should be skip_in_sif=True")


class TestPlanToolCalls(unittest.TestCase):
    def _make_pkg(self, body, **kwargs):
        entities = kwargs.pop("entities", {})
        full_entities = {
            "hs_codes": [], "product_names": [], "container_numbers": [],
            "bl_numbers": [], "article_numbers": [], "keywords": [],
            "locations": [], "amounts": [], "deadlines": [],
        }
        full_entities.update(entities)
        domain = kwargs.pop("domain", "general")
        all_domains = kwargs.pop("all_domains", [domain])
        return ContextPackage(
            original_subject="", original_body=body,
            detected_language="he", domain=domain, all_domains=all_domains,
            entities=full_entities, **kwargs,
        )

    def test_logistics_question_includes_route(self):
        pkg = self._make_pkg(
            "כמה זמן לוקח מאשדוד לניר עוז",
            domain="logistics", all_domains=["logistics"],
            entities={"locations": ["אשדוד (ILASD)"]},
        )
        plan = _plan_tool_calls(pkg)
        self.assertIn("calculate_route_eta", plan)

    def test_tariff_question_includes_search(self):
        pkg = self._make_pkg(
            "מה הסיווג של מכונת קפה",
            domain="tariff", all_domains=["tariff"],
            entities={"product_names": ["מכונת קפה"]},
        )
        plan = _plan_tool_calls(pkg)
        self.assertIn("search_tariff", plan)

    def test_mixed_logistics_and_ordinance(self):
        pkg = self._make_pkg(
            "כמה זמן מאשדוד לניר עוז? מה חייב לפי פקודת המכס בחשבון מכר?",
            domain="logistics", all_domains=["logistics", "ordinance"],
            entities={"locations": ["אשדוד (ILASD)"], "keywords": ["מכס"]},
        )
        plan = _plan_tool_calls(pkg)
        self.assertIn("calculate_route_eta", plan)
        self.assertIn("search_legal_knowledge", plan)

    def test_shipment_tracking_includes_status(self):
        pkg = self._make_pkg(
            "מה הסטטוס של MSCU1234567",
            domain="shipment", all_domains=["shipment"],
            entities={"container_numbers": ["MSCU1234567"]},
        )
        plan = _plan_tool_calls(pkg)
        self.assertIn("check_shipment_status", plan)

    def test_reform_question_includes_xml(self):
        pkg = self._make_pkg(
            "מה הרפורמה של מה שטוב לאירופה",
            domain="regulatory", all_domains=["regulatory"],
            entities={"keywords": ["מכס"]},
        )
        plan = _plan_tool_calls(pkg)
        self.assertIn("search_xml_documents", plan)

    def test_classification_tools_never_in_plan(self):
        pkg = self._make_pkg(
            "classify this product please",
            domain="tariff", all_domains=["tariff"],
            entities={"product_names": ["coffee machine"]},
        )
        plan = _plan_tool_calls(pkg)
        # Classification-only tools should NEVER appear
        for skip_tool in ["check_memory", "extract_invoice", "assess_risk",
                          "run_elimination", "fetch_seller_website"]:
            self.assertNotIn(skip_tool, plan)

    def test_empty_question_minimal_plan(self):
        pkg = self._make_pkg("hello", domain="general", all_domains=["general"])
        plan = _plan_tool_calls(pkg)
        # Should have very few or no tools with empty entities
        self.assertTrue(len(plan) < 5)

    def test_vat_question_triggers_vat_tool(self):
        pkg = self._make_pkg(
            "כמה מע\"מ יש על יבוא",
            domain="general", all_domains=["general"],
            entities={"keywords": ["יבוא"]},
        )
        plan = _plan_tool_calls(pkg)
        self.assertIn("get_israel_vat_rates", plan)

    def test_exchange_rate_question(self):
        pkg = self._make_pkg(
            "מה שער החליפין של הדולר",
            domain="general", all_domains=["general"],
        )
        plan = _plan_tool_calls(pkg)
        self.assertIn("bank_of_israel_rates", plan)

    def test_port_schedule_question(self):
        pkg = self._make_pkg(
            "מה לוח הזמנים של אניות בחיפה",
            domain="logistics", all_domains=["logistics"],
            entities={"locations": ["חיפה (ILHFA)"]},
        )
        plan = _plan_tool_calls(pkg)
        self.assertIn("get_port_schedule", plan)


class TestBuildToolParams(unittest.TestCase):
    def _make_pkg(self, body="", **ent_overrides):
        entities = {
            "hs_codes": [], "product_names": [], "container_numbers": [],
            "bl_numbers": [], "article_numbers": [], "keywords": [],
            "locations": [], "amounts": [], "deadlines": [],
        }
        entities.update(ent_overrides)
        return ContextPackage(
            original_subject="", original_body=body,
            detected_language="he", entities=entities,
        )

    def test_search_tariff_params(self):
        pkg = self._make_pkg(hs_codes=["84198110"])
        params = _build_tool_params("search_tariff", pkg)
        self.assertIn("item_description", params)
        self.assertIn("84198110", params["item_description"])

    def test_search_tariff_no_entities(self):
        pkg = self._make_pkg()
        params = _build_tool_params("search_tariff", pkg)
        self.assertIsNone(params)

    def test_route_eta_params(self):
        pkg = self._make_pkg("מאשדוד לניר עוז",
                             locations=["ניר עוז", "אשדוד (ILASD)"])
        params = _build_tool_params("calculate_route_eta", pkg)
        self.assertIsNotNone(params)
        self.assertIn("origin", params)
        self.assertIn("port_code", params)

    def test_shipment_params_container(self):
        pkg = self._make_pkg(container_numbers=["MSCU1234567"])
        params = _build_tool_params("check_shipment_status", pkg)
        self.assertIsNotNone(params)
        self.assertEqual(params["container_number"], "MSCU1234567")

    def test_legal_knowledge_params(self):
        pkg = self._make_pkg("חשבון מכר לפי פקודת המכס",
                             keywords=["מכס"])
        params = _build_tool_params("search_legal_knowledge", pkg)
        self.assertIsNotNone(params)
        self.assertIn("query", params)


class TestStoreToolResult(unittest.TestCase):
    def _make_pkg(self):
        return ContextPackage(
            original_subject="test", original_body="test",
            detected_language="he",
        )

    def test_store_tariff_results(self):
        pkg = self._make_pkg()
        _store_tool_result("search_tariff", {"candidates": [{"hs_code": "8419"}]}, pkg)
        self.assertEqual(len(pkg.tariff_results), 1)
        self.assertEqual(pkg.tariff_results[0]["hs_code"], "8419")

    def test_store_tariff_dedup(self):
        pkg = self._make_pkg()
        pkg.tariff_results = [{"hs_code": "8419"}]
        _store_tool_result("search_tariff", {"candidates": [{"hs_code": "8419"}]}, pkg)
        self.assertEqual(len(pkg.tariff_results), 1)  # no duplicate

    def test_store_route_eta(self):
        pkg = self._make_pkg()
        _store_tool_result("calculate_route_eta",
                           {"duration_minutes": 45, "distance_km": 32.5}, pkg)
        self.assertEqual(len(pkg.logistics_results), 1)

    def test_store_shipment(self):
        pkg = self._make_pkg()
        _store_tool_result("check_shipment_status",
                           {"found": True, "bl_number": "TEST"}, pkg)
        self.assertEqual(len(pkg.shipment_results), 1)

    def test_store_error_ignored(self):
        pkg = self._make_pkg()
        _store_tool_result("search_tariff", {"error": "test error"}, pkg)
        self.assertEqual(len(pkg.tariff_results), 0)

    def test_store_none_ignored(self):
        pkg = self._make_pkg()
        _store_tool_result("search_tariff", None, pkg)
        self.assertEqual(len(pkg.tariff_results), 0)

    def test_store_wikipedia(self):
        pkg = self._make_pkg()
        _store_tool_result("search_wikipedia",
                           {"found": True, "title": "Test", "extract": "info..."}, pkg)
        self.assertEqual(len(pkg.wikipedia_results), 1)

    def test_store_boi_rates(self):
        pkg = self._make_pkg()
        _store_tool_result("bank_of_israel_rates", {"USD": 3.65}, pkg)
        self.assertEqual(len(pkg.other_tool_results), 1)
        self.assertEqual(pkg.other_tool_results[0]["tool"], "bank_of_israel_rates")


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

    def test_all_domains_populated(self):
        pkg = prepare_context_package("", "מה הסיווג", db=None)
        self.assertIsInstance(pkg.all_domains, list)
        self.assertTrue(len(pkg.all_domains) > 0)

    def test_logistics_question_no_db(self):
        pkg = prepare_context_package("", "כמה זמן לוקח הובלה מאשדוד", db=None)
        self.assertEqual(pkg.domain, "logistics")
        self.assertIn("logistics", pkg.all_domains)


if __name__ == '__main__':
    unittest.main()
