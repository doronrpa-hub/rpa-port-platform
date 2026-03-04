"""Tests for EU Reform data module (_eu_reform_data.py).

Verifies:
- EU Reform documents have full text from parsed gov.il XMLs
- Key facts are structured and complete
- Search function works for Hebrew and English queries
- Summary returns all required fields
"""
import pytest


class TestEUReformDocs:
    """Verify EU_REFORM_DOCS structure and content."""

    def test_docs_exist(self):
        from lib._eu_reform_data import EU_REFORM_DOCS
        assert len(EU_REFORM_DOCS) >= 2

    def test_information_doc_has_full_text(self):
        from lib._eu_reform_data import EU_REFORM_DOCS
        doc = EU_REFORM_DOCS["eu_reform_information"]
        assert len(doc["full_text"]) > 2000
        assert "מה שטוב לאירופה" in doc["full_text"]
        assert "קוד 65" in doc["full_text"]

    def test_news_doc_has_full_text(self):
        from lib._eu_reform_data import EU_REFORM_DOCS
        doc = EU_REFORM_DOCS["eu_reform_news_022026"]
        assert len(doc["full_text"]) > 1000
        assert "פברואר 2026" in doc["full_text"]

    def test_all_docs_have_required_fields(self):
        from lib._eu_reform_data import EU_REFORM_DOCS
        required = ["title_he", "title_en", "source_url", "effective_date", "pages", "full_text"]
        for doc_id, doc in EU_REFORM_DOCS.items():
            for field in required:
                assert field in doc, f"{doc_id} missing {field}"

    def test_source_urls_are_govil(self):
        from lib._eu_reform_data import EU_REFORM_DOCS
        for doc_id, doc in EU_REFORM_DOCS.items():
            assert "gov.il" in doc["source_url"], f"{doc_id} URL not gov.il"


class TestEUReformKeyFacts:
    """Verify EU_REFORM_KEY_FACTS structured data."""

    def test_key_facts_exist(self):
        from lib._eu_reform_data import EU_REFORM_KEY_FACTS
        assert EU_REFORM_KEY_FACTS is not None

    def test_customs_code_65(self):
        from lib._eu_reform_data import EU_REFORM_KEY_FACTS
        assert EU_REFORM_KEY_FACTS["customs_code"] == 65

    def test_43_directives(self):
        from lib._eu_reform_data import EU_REFORM_KEY_FACTS
        assert EU_REFORM_KEY_FACTS["directives_count"] == 43

    def test_phases_have_5_entries(self):
        from lib._eu_reform_data import EU_REFORM_KEY_FACTS
        assert len(EU_REFORM_KEY_FACTS["phases"]) == 5

    def test_phase_1_active(self):
        from lib._eu_reform_data import EU_REFORM_KEY_FACTS
        p1 = EU_REFORM_KEY_FACTS["phases"][0]
        assert p1["status"] == "active"
        assert p1["date"] == "2025-01"

    def test_adopted_directives_include_reach(self):
        from lib._eu_reform_data import EU_REFORM_KEY_FACTS
        texts = " ".join(EU_REFORM_KEY_FACTS["adopted_directives"])
        assert "REACH" in texts

    def test_included_products_not_empty(self):
        from lib._eu_reform_data import EU_REFORM_KEY_FACTS
        assert len(EU_REFORM_KEY_FACTS["included_products"]) >= 10

    def test_excluded_products_include_food(self):
        from lib._eu_reform_data import EU_REFORM_KEY_FACTS
        texts = " ".join(EU_REFORM_KEY_FACTS["excluded_products"])
        assert "מזון" in texts

    def test_risk_levels_three(self):
        from lib._eu_reform_data import EU_REFORM_KEY_FACTS
        assert set(EU_REFORM_KEY_FACTS["risk_levels"].keys()) == {"low", "medium", "high"}

    def test_required_documents_include_ce(self):
        from lib._eu_reform_data import EU_REFORM_KEY_FACTS
        texts = " ".join(EU_REFORM_KEY_FACTS["required_documents"])
        assert "CE" in texts

    def test_personal_import_threshold(self):
        from lib._eu_reform_data import EU_REFORM_KEY_FACTS
        t = EU_REFORM_KEY_FACTS["personal_import_vat_threshold"]
        assert t["current"] == 75
        assert t["was_raised_to"] == 150

    def test_references_not_empty(self):
        from lib._eu_reform_data import EU_REFORM_KEY_FACTS
        assert len(EU_REFORM_KEY_FACTS["references"]) >= 3


class TestSearchEUReform:
    """Verify search function works."""

    def test_search_finds_ce(self):
        from lib._eu_reform_data import search_eu_reform
        result = search_eu_reform("CE")
        assert result["found"] is True
        assert len(result["results"]) >= 1

    def test_search_finds_hebrew_keyword(self):
        from lib._eu_reform_data import search_eu_reform
        result = search_eu_reform("צעצועים")
        assert result["found"] is True

    def test_search_finds_code_65(self):
        from lib._eu_reform_data import search_eu_reform
        result = search_eu_reform("קוד 65")
        assert result["found"] is True

    def test_search_nonexistent_returns_empty(self):
        from lib._eu_reform_data import search_eu_reform
        result = search_eu_reform("xyznonexistent12345")
        assert result["found"] is False
        assert len(result["results"]) == 0

    def test_search_results_have_snippets(self):
        from lib._eu_reform_data import search_eu_reform
        result = search_eu_reform("DoC")
        if result["found"]:
            for r in result["results"]:
                assert "text_snippet" in r
                assert len(r["text_snippet"]) > 0


class TestGetEUReformSummary:
    """Verify summary function."""

    def test_summary_returns_found(self):
        from lib._eu_reform_data import get_eu_reform_summary
        s = get_eu_reform_summary()
        assert s["found"] is True
        assert s["type"] == "eu_reform"

    def test_summary_has_all_fields(self):
        from lib._eu_reform_data import get_eu_reform_summary
        s = get_eu_reform_summary()
        required = [
            "customs_code", "directives_count", "phases",
            "adopted_directives", "included_products", "excluded_products",
            "required_documents", "risk_levels", "documents_count",
        ]
        for field in required:
            assert field in s, f"Summary missing {field}"

    def test_summary_documents_count(self):
        from lib._eu_reform_data import get_eu_reform_summary
        s = get_eu_reform_summary()
        assert s["documents_count"] >= 2
        assert s["total_pages"] >= 5


class TestFTAFullTextCoverage:
    """Verify all 16 FTA countries have real parsed content."""

    def test_all_16_countries_exist(self):
        from lib._fta_all_countries import FTA_COUNTRIES
        assert len(FTA_COUNTRIES) == 16

    def test_all_countries_have_documents(self):
        from lib._fta_all_countries import FTA_COUNTRIES
        for country, data in FTA_COUNTRIES.items():
            assert len(data.get("documents", {})) >= 1, f"{country} has no documents"

    def test_all_countries_have_origin_proof(self):
        from lib._fta_all_countries import FTA_COUNTRIES
        for country, data in FTA_COUNTRIES.items():
            assert data.get("origin_proof"), f"{country} missing origin_proof"

    def test_all_countries_have_chars(self):
        from lib._fta_all_countries import FTA_COUNTRIES
        for country, data in FTA_COUNTRIES.items():
            assert data.get("total_chars", 0) > 0, f"{country} has 0 chars"

    def test_all_countries_have_agreement_name(self):
        from lib._fta_all_countries import FTA_COUNTRIES
        for country, data in FTA_COUNTRIES.items():
            assert data.get("agreement_name_he"), f"{country} missing agreement_name_he"
            assert data.get("agreement_name_en"), f"{country} missing agreement_name_en"

    def test_cumulation_field_present(self):
        from lib._fta_all_countries import FTA_COUNTRIES
        for country, data in FTA_COUNTRIES.items():
            assert "cumulation" in data, f"{country} missing cumulation"

    def test_eur1_countries_have_approved_exporter(self):
        """EUR.1 countries should have has_approved_exporter field."""
        from lib._fta_all_countries import FTA_COUNTRIES
        for country, data in FTA_COUNTRIES.items():
            assert "has_approved_exporter" in data, f"{country} missing has_approved_exporter"

    def test_total_chars_across_all_countries(self):
        """Total FTA text should be at least 10MB."""
        from lib._fta_all_countries import FTA_COUNTRIES
        total = sum(d.get("total_chars", 0) for d in FTA_COUNTRIES.values())
        assert total >= 10_000_000, f"Total FTA chars only {total:,}"


class TestDocumentRegistry:
    """Verify document registry has all expected entries."""

    def test_eu_reform_has_python_module(self):
        from lib._document_registry import DOCUMENT_REGISTRY
        doc = DOCUMENT_REGISTRY["eu_reform"]
        assert doc["python_module"] == "lib._eu_reform_data"

    def test_ports_ordinance_registered(self):
        from lib._document_registry import DOCUMENT_REGISTRY
        assert "ports_ordinance" in DOCUMENT_REGISTRY
        assert DOCUMENT_REGISTRY["ports_ordinance"]["status"] == "pending"

    def test_ata_carnet_registered(self):
        from lib._document_registry import DOCUMENT_REGISTRY
        assert "ata_carnet_procedure" in DOCUMENT_REGISTRY

    def test_direct_delivery_registered(self):
        from lib._document_registry import DOCUMENT_REGISTRY
        assert "direct_delivery_procedure" in DOCUMENT_REGISTRY

    def test_all_16_fta_countries_registered(self):
        from lib._document_registry import DOCUMENT_REGISTRY
        fta_entries = [k for k, v in DOCUMENT_REGISTRY.items() if v["category"] == "fta"]
        assert len(fta_entries) >= 16, f"Only {len(fta_entries)} FTA entries"

    def test_approved_exporter_is_export(self):
        from lib._document_registry import DOCUMENT_REGISTRY
        doc = DOCUMENT_REGISTRY.get("approved_exporter")
        if doc:
            assert doc.get("direction") == "export" or doc.get("category") == "procedure"
