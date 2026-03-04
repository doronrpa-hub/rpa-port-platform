"""Tests for the document registry module (_document_registry.py).

Covers structure validation, specific documents, FTA documents, helper functions,
format_citation, and search/relevance queries.
"""
import pytest

from lib._document_registry import (
    DOCUMENT_REGISTRY,
    VALID_CATEGORIES,
    NONEXISTENT_SUPPLEMENTS,
    get_document,
    get_documents_by_category,
    get_fta_for_country,
    get_relevant_documents,
    format_citation,
    get_all_document_ids,
    get_supplement_documents,
)


# ============================================================================
# TestRegistryStructure
# ============================================================================

class TestRegistryStructure:
    """Validate the overall shape and consistency of DOCUMENT_REGISTRY."""

    def test_registry_has_at_least_40_documents(self):
        assert len(DOCUMENT_REGISTRY) >= 40

    def test_every_doc_has_required_fields(self):
        required = {"title_he", "title_en", "category", "has_html"}
        for doc_id, doc in DOCUMENT_REGISTRY.items():
            missing = required - set(doc.keys())
            assert not missing, f"{doc_id} missing required fields: {missing}"

    def test_category_is_valid(self):
        for doc_id, doc in DOCUMENT_REGISTRY.items():
            assert doc["category"] in VALID_CATEGORIES, (
                f"{doc_id} has invalid category '{doc['category']}'"
            )

    def test_title_he_is_nonempty_string(self):
        for doc_id, doc in DOCUMENT_REGISTRY.items():
            assert isinstance(doc["title_he"], str) and len(doc["title_he"]) > 0, (
                f"{doc_id} has empty or non-string title_he"
            )

    def test_title_en_is_nonempty_string(self):
        for doc_id, doc in DOCUMENT_REGISTRY.items():
            assert isinstance(doc["title_en"], str) and len(doc["title_en"]) > 0, (
                f"{doc_id} has empty or non-string title_en"
            )

    def test_no_duplicate_doc_ids(self):
        ids = get_all_document_ids()
        assert len(ids) == len(set(ids)), "Duplicate doc_ids found in registry"

    def test_searchable_via_is_always_a_list(self):
        for doc_id, doc in DOCUMENT_REGISTRY.items():
            sv = doc.get("searchable_via")
            if sv is not None:
                assert isinstance(sv, list), (
                    f"{doc_id} searchable_via is {type(sv).__name__}, expected list"
                )

    def test_html_file_values_are_strings_or_none(self):
        for doc_id, doc in DOCUMENT_REGISTRY.items():
            hf = doc.get("html_file")
            assert hf is None or isinstance(hf, str), (
                f"{doc_id} html_file is {type(hf).__name__}, expected str or None"
            )


# ============================================================================
# TestSpecificDocuments
# ============================================================================

class TestSpecificDocuments:
    """Verify that key documents exist and have correct metadata."""

    def test_tariff_book_exists_with_correct_fields(self):
        doc = DOCUMENT_REGISTRY["tariff_book"]
        assert doc["category"] == "tariff"
        assert doc["has_html"] is True
        assert doc["html_file"] == "tariff_book.html"
        assert doc["firestore_collection"] == "tariff"

    def test_customs_ordinance_exists_with_python_data(self):
        doc = DOCUMENT_REGISTRY["customs_ordinance"]
        assert doc["category"] == "law"
        assert doc["python_module"] == "lib._ordinance_data"
        assert doc["python_const"] == "ORDINANCE_ARTICLES"
        assert doc["article_count"] == 311

    def test_framework_order_exists(self):
        doc = DOCUMENT_REGISTRY["framework_order"]
        assert doc["category"] == "regulation"
        assert doc["firestore_collection"] == "framework_order"
        assert doc["article_count"] == 33

    def test_discount_codes_exists(self):
        doc = DOCUMENT_REGISTRY["discount_codes"]
        assert doc["category"] == "tariff"
        assert doc["has_html"] is True
        assert doc["html_file"] == "discount_codes.html"

    def test_procedures_1_through_28_exist(self):
        expected = ["procedure_1", "procedure_2", "procedure_3",
                    "procedure_10", "procedure_25", "procedure_28"]
        for pid in expected:
            assert pid in DOCUMENT_REGISTRY, f"{pid} not found in registry"
            assert DOCUMENT_REGISTRY[pid]["category"] == "procedure"

    def test_free_import_order_has_firestore_collection(self):
        doc = DOCUMENT_REGISTRY["free_import_order"]
        assert doc["firestore_collection"] == "free_import_order"
        assert doc["category"] == "regulation"

    def test_free_export_order_has_firestore_collection(self):
        doc = DOCUMENT_REGISTRY["free_export_order"]
        assert doc["firestore_collection"] == "free_export_order"
        assert doc["category"] == "regulation"

    def test_reforms_exist(self):
        assert "eu_reform" in DOCUMENT_REGISTRY
        assert DOCUMENT_REGISTRY["eu_reform"]["category"] == "reform"
        assert "us_reform" in DOCUMENT_REGISTRY
        assert DOCUMENT_REGISTRY["us_reform"]["category"] == "reform"


# ============================================================================
# TestFTADocuments
# ============================================================================

class TestFTADocuments:
    """Validate FTA agreement entries and country lookups."""

    def test_at_least_16_fta_docs(self):
        fta_docs = get_documents_by_category("fta")
        assert len(fta_docs) >= 16

    def test_all_fta_docs_have_country_code(self):
        fta_docs = get_documents_by_category("fta")
        for doc in fta_docs:
            assert doc.get("country_code") is not None, (
                f"FTA doc {doc['doc_id']} missing country_code"
            )

    def test_all_fta_docs_have_origin_proof_type(self):
        fta_docs = get_documents_by_category("fta")
        for doc in fta_docs:
            assert doc.get("origin_proof_type") is not None, (
                f"FTA doc {doc['doc_id']} missing origin_proof_type"
            )

    def test_eu_fta_has_eur1_origin_proof(self):
        doc = DOCUMENT_REGISTRY["fta_eu"]
        assert "EUR.1" in doc["origin_proof_type"]

    def test_usa_fta_has_invoice_declaration(self):
        doc = DOCUMENT_REGISTRY["fta_usa"]
        assert "Invoice Declaration" in doc["origin_proof_type"]

    def test_get_fta_for_country_eu(self):
        result = get_fta_for_country("EU")
        assert result is not None
        assert result["doc_id"] == "fta_eu"

    def test_get_fta_for_country_alias_de(self):
        result = get_fta_for_country("DE")
        assert result is not None
        assert result["doc_id"] == "fta_eu"

    def test_get_fta_for_country_nonexistent(self):
        result = get_fta_for_country("nonexistent")
        assert result is None


# ============================================================================
# TestGetDocument
# ============================================================================

class TestGetDocument:
    """Test get_document() helper."""

    def test_returns_dict_for_existing_doc(self):
        result = get_document("tariff_book")
        assert isinstance(result, dict)
        assert result["doc_id"] == "tariff_book"

    def test_returns_none_for_nonexistent(self):
        result = get_document("this_doc_does_not_exist_xyz")
        assert result is None

    def test_has_correct_title_for_known_doc(self):
        result = get_document("customs_ordinance")
        assert result["title_he"] == "פקודת המכס"
        assert result["title_en"] == "Customs Ordinance"

    def test_returned_dict_has_doc_id_key(self):
        result = get_document("framework_order")
        assert "doc_id" in result
        assert result["doc_id"] == "framework_order"


# ============================================================================
# TestGetDocumentsByCategory
# ============================================================================

class TestGetDocumentsByCategory:
    """Test get_documents_by_category() helper."""

    def test_tariff_returns_at_least_1(self):
        results = get_documents_by_category("tariff")
        assert len(results) >= 1

    def test_procedure_returns_at_least_4(self):
        results = get_documents_by_category("procedure")
        assert len(results) >= 4

    def test_fta_returns_at_least_16(self):
        results = get_documents_by_category("fta")
        assert len(results) >= 16

    def test_nonexistent_category_returns_empty(self):
        results = get_documents_by_category("nonexistent_category")
        assert results == []


# ============================================================================
# TestFormatCitation
# ============================================================================

class TestFormatCitation:
    """Test format_citation() output."""

    def test_ordinance_with_article(self):
        citation = format_citation("customs_ordinance", article="130")
        assert "פקודת המכס" in citation
        assert "סעיף 130" in citation

    def test_fta_with_section(self):
        citation = format_citation("framework_order", article="16", section="EU")
        assert "צו מסגרת" in citation
        assert "סעיף 16" in citation
        assert "EU" in citation

    def test_procedure_no_article(self):
        citation = format_citation("procedure_3")
        assert "נוהל סיווג" in citation

    def test_tariff_with_section(self):
        citation = format_citation("tariff_book", section="84.71")
        assert "תעריף המכס" in citation
        assert "פרט 84.71" in citation

    def test_unknown_doc_returns_doc_id(self):
        citation = format_citation("totally_unknown_doc_xyz")
        assert citation == "totally_unknown_doc_xyz"


# ============================================================================
# TestGetRelevantDocuments
# ============================================================================

class TestGetRelevantDocuments:
    """Test get_relevant_documents() relevance engine."""

    def test_always_includes_core_documents(self):
        results = get_relevant_documents()
        doc_ids = [r["doc_id"] for r in results]
        assert "tariff_book" in doc_ids
        assert "customs_ordinance" in doc_ids
        assert "framework_order" in doc_ids

    def test_hs_code_adds_supplements(self):
        results = get_relevant_documents(hs_code="8507600000")
        doc_ids = [r["doc_id"] for r in results]
        assert "discount_codes" in doc_ids

    def test_origin_adds_fta(self):
        results = get_relevant_documents(origin="EU")
        doc_ids = [r["doc_id"] for r in results]
        assert "fta_eu" in doc_ids

    def test_nonexistent_origin_no_crash(self):
        results = get_relevant_documents(origin="ZZ")
        assert isinstance(results, list)


# ============================================================================
# TestSupplements
# ============================================================================

class TestSupplements:
    """Test supplement-related functionality."""

    def test_get_supplement_documents_returns_list(self):
        results = get_supplement_documents()
        assert isinstance(results, list)
        assert len(results) >= 10

    def test_nonexistent_supplements_not_in_registry(self):
        for n in NONEXISTENT_SUPPLEMENTS:
            key = f"supplement_{n}"
            assert key not in DOCUMENT_REGISTRY, (
                f"Supplement {n} should not exist but found in registry"
            )

    def test_supplements_sorted_numerically(self):
        results = get_supplement_documents()
        # Extract numeric IDs for supplement_N entries
        nums = []
        for r in results:
            did = r["doc_id"]
            if did.startswith("supplement_"):
                nums.append(int(did.split("_")[1]))
        # Verify sorted
        assert nums == sorted(nums), "Supplements not in numerical order"
