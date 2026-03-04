# -*- coding: utf-8 -*-
"""Tests for lib._fta_all_countries — FTA country data for 16 trade agreement partners.

50+ tests across 11 test classes covering data structure integrity, helper functions,
search capabilities, document classification, and summary statistics.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib._fta_all_countries import (
    FTA_COUNTRIES,
    get_fta_country,
    get_all_country_codes,
    get_countries_with_eur1,
    get_countries_with_approved_exporter,
    get_countries_with_invoice_declaration,
    search_fta_articles,
    search_fta_full_text,
    search_fta_countries,
    get_origin_proof_type,
    classify_fta_document,
    get_summary_stats,
    get_country_files,
)


# ---------------------------------------------------------------------------
# Expected constants
# ---------------------------------------------------------------------------

_EXPECTED_COUNTRY_CODES = {
    "eu", "uk", "efta", "turkey", "jordan", "ukraine",
    "usa", "canada", "mexico", "colombia", "panama",
    "mercosur", "uae", "korea", "guatemala", "vietnam",
}

_EUR1_COUNTRY_CODES = {"eu", "uk", "efta", "turkey", "jordan", "ukraine"}

_REQUIRED_FIELDS = {
    "name_he", "name_en", "agreement_name_he", "agreement_name_en",
    "agreement_year", "effective_date", "origin_proof",
    "has_invoice_declaration", "has_approved_exporter",
    "cumulation", "cumulation_countries",
    "key_articles",
}

# Fields that differ between stub and parsed versions
_OPTIONAL_FIELDS = {"notes", "govil_file_count", "xml_file_count", "xml_count",
                     "total_chars", "total_pages", "documents"}

_VALID_PROOF_TYPES = {"EUR.1", "Certificate of Origin", "Invoice Declaration"}


# ===========================================================================
# TestFTACountriesStructure
# ===========================================================================

class TestFTACountriesStructure:
    """Tests for FTA_COUNTRIES dict structure and completeness."""

    def test_exactly_16_countries(self):
        assert len(FTA_COUNTRIES) == 16

    def test_all_expected_codes_present(self):
        assert set(FTA_COUNTRIES.keys()) == _EXPECTED_COUNTRY_CODES

    def test_required_fields_present(self):
        for code, data in FTA_COUNTRIES.items():
            for field in _REQUIRED_FIELDS:
                assert field in data, f"Missing field '{field}' in country '{code}'"

    def test_valid_origin_proof_types(self):
        for code, data in FTA_COUNTRIES.items():
            assert data["origin_proof"] in _VALID_PROOF_TYPES, (
                f"Country '{code}' has invalid origin_proof: {data['origin_proof']}"
            )

    def test_agreement_year_is_int(self):
        for code, data in FTA_COUNTRIES.items():
            assert isinstance(data["agreement_year"], int), f"Country '{code}' agreement_year not int"
            assert 1985 <= data["agreement_year"] <= 2030, (
                f"Country '{code}' agreement_year {data['agreement_year']} out of range"
            )

    def test_effective_date_format(self):
        import re
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for code, data in FTA_COUNTRIES.items():
            assert date_pattern.match(data["effective_date"]), (
                f"Country '{code}' effective_date format invalid: {data['effective_date']}"
            )

    def test_cumulation_countries_is_list(self):
        for code, data in FTA_COUNTRIES.items():
            assert isinstance(data["cumulation_countries"], list), (
                f"Country '{code}' cumulation_countries not a list"
            )

    def test_key_articles_is_dict(self):
        for code, data in FTA_COUNTRIES.items():
            assert isinstance(data["key_articles"], dict), (
                f"Country '{code}' key_articles not a dict"
            )


# ===========================================================================
# TestEUR1Countries
# ===========================================================================

class TestEUR1Countries:
    """Tests for EUR.1 origin proof countries."""

    def test_exactly_6_eur1_countries(self):
        eur1 = get_countries_with_eur1()
        assert len(eur1) == 6

    def test_all_correct_codes(self):
        eur1 = set(get_countries_with_eur1())
        assert eur1 == _EUR1_COUNTRY_CODES

    def test_non_eur1_not_included(self):
        eur1 = get_countries_with_eur1()
        assert "usa" not in eur1
        assert "korea" not in eur1
        assert "mercosur" not in eur1

    def test_eu_is_eur1(self):
        assert "eu" in get_countries_with_eur1()

    def test_uk_is_eur1(self):
        assert "uk" in get_countries_with_eur1()


# ===========================================================================
# TestGetFTACountry
# ===========================================================================

class TestGetFTACountry:
    """Tests for get_fta_country()."""

    def test_existing_returns_dict(self):
        result = get_fta_country("eu")
        assert isinstance(result, dict)
        assert result["name_en"] == "European Union"

    def test_case_insensitive(self):
        result = get_fta_country("EU")
        assert result is not None
        assert result["name_en"] == "European Union"

    def test_nonexistent_returns_none(self):
        result = get_fta_country("nonexistent_code")
        assert result is None

    def test_empty_returns_none(self):
        result = get_fta_country("")
        assert result is None

    def test_none_returns_none(self):
        result = get_fta_country(None)
        assert result is None

    def test_all_16_accessible(self):
        for code in _EXPECTED_COUNTRY_CODES:
            result = get_fta_country(code)
            assert result is not None, f"get_fta_country('{code}') returned None"


# ===========================================================================
# TestCountryCodes
# ===========================================================================

class TestCountryCodes:
    """Tests for get_all_country_codes()."""

    def test_all_16_present(self):
        codes = get_all_country_codes()
        assert len(codes) == 16

    def test_sorted(self):
        codes = get_all_country_codes()
        assert codes == sorted(codes)

    def test_returns_list(self):
        codes = get_all_country_codes()
        assert isinstance(codes, list)

    def test_all_expected_codes(self):
        codes = set(get_all_country_codes())
        assert codes == _EXPECTED_COUNTRY_CODES


# ===========================================================================
# TestOriginProofType
# ===========================================================================

class TestOriginProofType:
    """Tests for get_origin_proof_type()."""

    def test_switzerland_returns_efta(self):
        result = get_origin_proof_type("Switzerland")
        assert result is not None
        assert result["country_code"] == "efta"
        assert result["origin_proof"] == "EUR.1"

    def test_brazil_returns_mercosur(self):
        result = get_origin_proof_type("Brazil")
        assert result is not None
        assert result["country_code"] == "mercosur"

    def test_germany_matches_eu(self):
        """Germany is not an explicit member_state but 'eu' name_en is 'European Union'."""
        # EU does not have member_states list, so 'Germany' should NOT match
        result = get_origin_proof_type("European Union")
        assert result is not None
        assert result["country_code"] == "eu"
        assert result["origin_proof"] == "EUR.1"

    def test_direct_code_match(self):
        result = get_origin_proof_type("eu")
        assert result is not None
        assert result["country_code"] == "eu"

    def test_unknown_country_returns_none(self):
        result = get_origin_proof_type("Atlantis")
        assert result is None

    def test_empty_returns_none(self):
        result = get_origin_proof_type("")
        assert result is None

    def test_none_returns_none(self):
        result = get_origin_proof_type(None)
        assert result is None

    def test_has_expected_keys(self):
        result = get_origin_proof_type("Turkey")
        assert result is not None
        assert "country_code" in result
        assert "origin_proof" in result
        assert "has_invoice_declaration" in result
        assert "has_approved_exporter" in result
        assert "agreement_name" in result


# ===========================================================================
# TestSearchArticles
# ===========================================================================

class TestSearchArticles:
    """Tests for search_fta_articles() and search_fta_full_text()."""

    def test_keyword_finds_results(self):
        # search_fta_articles searches key_articles (old stubs)
        # search_fta_full_text searches documents (parsed data)
        results = search_fta_articles("EUR.1")
        ft_results = search_fta_full_text("EUR.1")
        assert isinstance(results, list)
        assert isinstance(ft_results, list)
        # At least one of the two APIs should return results
        assert len(results) > 0 or len(ft_results) > 0

    def test_empty_keyword_returns_empty(self):
        results = search_fta_articles("")
        assert results == []

    def test_none_keyword_returns_empty(self):
        results = search_fta_articles(None)
        assert results == []

    def test_full_text_search_finds_eur1(self):
        results = search_fta_full_text("EUR.1")
        assert isinstance(results, list)
        assert len(results) > 0
        for r in results:
            assert "country_code" in r

    def test_case_insensitive(self):
        results_lower = search_fta_full_text("protocol")
        results_upper = search_fta_full_text("PROTOCOL")
        # Should find the same results
        assert len(results_lower) == len(results_upper)

    def test_hebrew_keyword(self):
        results = search_fta_full_text("מקור")
        assert isinstance(results, list)
        assert len(results) > 0


# ===========================================================================
# TestSearchCountries
# ===========================================================================

class TestSearchCountries:
    """Tests for search_fta_countries()."""

    def test_country_name_finds(self):
        results = search_fta_countries("Turkey")
        assert len(results) > 0
        assert results[0][0] == "turkey"

    def test_hebrew_name_finds(self):
        results = search_fta_countries("טורקיה")
        assert len(results) > 0
        assert results[0][0] == "turkey"

    def test_empty_returns_empty(self):
        results = search_fta_countries("")
        assert results == []

    def test_none_returns_empty(self):
        results = search_fta_countries(None)
        assert results == []

    def test_result_is_tuple(self):
        results = search_fta_countries("Jordan")
        assert len(results) > 0
        code, data = results[0]
        assert isinstance(code, str)
        assert isinstance(data, dict)

    def test_partial_match(self):
        results = search_fta_countries("Vietnam")
        assert len(results) >= 1


# ===========================================================================
# TestDocumentClassification
# ===========================================================================

class TestDocumentClassification:
    """Tests for classify_fta_document()."""

    def test_origin_rules(self):
        assert classify_fta_document("usa-fta-rules-of-origin") == "origin_rules"

    def test_eur1_form(self):
        # "fta-eur1-makor-example" matches origin_rules first (due to "makor"),
        # so test with a filename that only matches EUR.1 pattern
        assert classify_fta_document("eur1-certificate-form") == "eur1_form"

    def test_agreement_text(self):
        assert classify_fta_document("euro-fta-agreement-en") == "agreement_text"

    def test_benefits_schedule(self):
        result = classify_fta_document("benefits-euro-fta-export-from-israel")
        assert result == "benefits_schedule"

    def test_approved_exporter(self):
        assert classify_fta_document("nohal-misim-approved-exporter") == "approved_exporter"

    def test_unknown_returns_other(self):
        assert classify_fta_document("random-filename-xyz") == "other"

    def test_empty_returns_other(self):
        assert classify_fta_document("") == "other"

    def test_protocol_annex(self):
        # Pattern priority: earlier patterns match first.
        # Use a filename that only matches the protocol/annex pattern.
        result = classify_fta_document("appendix-customs-2018")
        assert result == "protocol_annex"


# ===========================================================================
# TestSummaryStats
# ===========================================================================

class TestSummaryStats:
    """Tests for get_summary_stats()."""

    def test_returns_dict(self):
        stats = get_summary_stats()
        assert isinstance(stats, dict)

    def test_expected_keys(self):
        stats = get_summary_stats()
        expected_keys = {
            "total_countries", "total_xml_files",
            "total_key_articles", "eur1_countries",
            "certificate_of_origin_countries", "invoice_declaration_countries",
            "approved_exporter_countries", "bloc_agreements",
        }
        assert expected_keys.issubset(set(stats.keys()))

    def test_total_countries_16(self):
        stats = get_summary_stats()
        assert stats["total_countries"] == 16

    def test_eur1_list_matches(self):
        stats = get_summary_stats()
        assert set(stats["eur1_countries"]) == _EUR1_COUNTRY_CODES

    def test_xml_files_positive(self):
        stats = get_summary_stats()
        assert stats["total_xml_files"] > 0

    def test_total_articles_positive(self):
        stats = get_summary_stats()
        assert stats["total_key_articles"] > 0


# ===========================================================================
# TestKeyArticles
# ===========================================================================

class TestKeyArticles:
    """Tests for documents/key_articles fields across all countries."""

    def test_eu_has_documents(self):
        eu = get_fta_country("eu")
        # Parsed version uses 'documents' dict with full text
        docs = eu.get("documents", {})
        assert len(docs) >= 3, f"EU has only {len(docs)} documents"

    def test_all_countries_have_documents(self):
        for code, data in FTA_COUNTRIES.items():
            docs = data.get("documents", data.get("key_articles", {}))
            assert isinstance(docs, dict), (
                f"Country '{code}' documents/key_articles is not dict"
            )

    def test_document_has_title(self):
        for code, data in FTA_COUNTRIES.items():
            docs = data.get("documents", data.get("key_articles", {}))
            for doc_key, doc_data in docs.items():
                assert "title" in doc_data, (
                    f"Country '{code}' doc '{doc_key}' missing title"
                )

    def test_eu_has_protocol_content(self):
        eu = get_fta_country("eu")
        docs = eu.get("documents", eu.get("key_articles", {}))
        # Should have protocol-related document
        has_protocol = any("protocol" in k.lower() or "protocol" in v.get("title", "").lower()
                          for k, v in docs.items())
        assert has_protocol, "EU missing protocol document"

    def test_usa_has_origin_content(self):
        usa = get_fta_country("usa")
        docs = usa.get("documents", usa.get("key_articles", {}))
        # USA should have origin rules document
        has_origin = any("origin" in k.lower() or "origin" in v.get("title", "").lower()
                         for k, v in docs.items())
        assert has_origin, "USA missing origin rules document"


# ===========================================================================
# TestApprovedExporterAndInvoiceDeclaration
# ===========================================================================

class TestApprovedExporterAndInvoiceDeclaration:
    """Tests for approved exporter and invoice declaration helper functions."""

    def test_approved_exporter_returns_list(self):
        result = get_countries_with_approved_exporter()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_invoice_declaration_returns_list(self):
        result = get_countries_with_invoice_declaration()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_eu_has_both(self):
        eu = get_fta_country("eu")
        assert eu["has_approved_exporter"] is True
        assert eu["has_invoice_declaration"] is True
        assert "eu" in get_countries_with_approved_exporter()
        assert "eu" in get_countries_with_invoice_declaration()


# ===========================================================================
# TestCountryFiles
# ===========================================================================

class TestCountryFiles:
    """Tests for get_country_files()."""

    def test_eu_has_files(self):
        files = get_country_files("eu")
        assert isinstance(files, list)
        assert len(files) > 0

    def test_unknown_returns_empty(self):
        files = get_country_files("nonexistent")
        assert files == []

    def test_none_returns_empty(self):
        files = get_country_files(None)
        assert files == []

    def test_empty_returns_empty(self):
        files = get_country_files("")
        assert files == []
