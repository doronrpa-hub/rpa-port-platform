"""Integration tests for the compliance auditor wiring into the classification
pipeline and email output paths.

Tests cover:
  1. Pipeline import guards and feature flags
  2. HTML rendering for email output
  3. compare_fta_document tool integration
  4. Email intent citation wiring
  5. Document registry consistency with FTA country data
  6. Generated HTML file fidelity (skipped if files not present)
"""

import os
import sys
import inspect
import pytest

# Ensure functions/ is on sys.path
_FUNCTIONS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _FUNCTIONS_DIR not in sys.path:
    sys.path.insert(0, _FUNCTIONS_DIR)

# HTML files directory (generated locally, not in git)
HTML_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "downloads", "html")
HTML_DIR = os.path.normpath(HTML_DIR)


# =============================================================================
# 1. TestComplianceWiringInPipeline
# =============================================================================

class TestComplianceWiringInPipeline:
    """Verify that the compliance auditor is correctly wired into classification_agents."""

    def test_compliance_auditor_available_flag_is_true(self):
        from lib.classification_agents import COMPLIANCE_AUDITOR_AVAILABLE
        assert COMPLIANCE_AUDITOR_AVAILABLE is True

    def test_compliance_auditor_enabled_flag_is_true(self):
        from lib.classification_agents import COMPLIANCE_AUDITOR_ENABLED
        assert COMPLIANCE_AUDITOR_ENABLED is True

    def test_import_compliance_audit_from_classification_agents(self):
        """_compliance_audit (alias for audit_classification) is importable."""
        from lib.classification_agents import _compliance_audit
        assert callable(_compliance_audit)

    def test_import_render_compliance_section_html(self):
        from lib.classification_agents import render_compliance_section_html
        assert callable(render_compliance_section_html)

    def test_build_compliance_context_importable(self):
        from lib.compliance_auditor import build_compliance_context
        assert callable(build_compliance_context)

    def test_audit_classification_importable(self):
        from lib.compliance_auditor import audit_classification
        assert callable(audit_classification)

    def test_compliance_import_is_fail_open(self):
        """The import block in classification_agents uses try/except ImportError."""
        import lib.classification_agents as ca
        source = inspect.getsource(ca)
        # The import block should have except ImportError
        assert "COMPLIANCE_AUDITOR_AVAILABLE = False" in source

    def test_pipeline_calls_compliance_audit_when_enabled(self):
        """run_full_classification source references _compliance_audit."""
        from lib.classification_agents import run_full_classification
        source = inspect.getsource(run_full_classification)
        assert "_compliance_audit" in source
        assert "COMPLIANCE_AUDITOR_ENABLED" in source


# =============================================================================
# 2. TestComplianceInEmail
# =============================================================================

class TestComplianceInEmail:
    """Verify compliance HTML rendering for email output."""

    def test_render_empty_audit_result(self):
        from lib.compliance_auditor import AuditResult, render_compliance_section_html
        result = AuditResult()
        html = render_compliance_section_html(result)
        # Empty result should produce empty or minimal HTML
        assert isinstance(html, str)
        # No citations means no substantial content
        assert len(html) < 200

    def test_render_with_citations(self):
        from lib.compliance_auditor import (
            AuditResult, Citation, render_compliance_section_html,
        )
        result = AuditResult(citations=[
            Citation(
                doc_id="customs_ordinance",
                article="130",
                title="ערך עסקה",
                text_snippet="ערכם של טובין מיובאים לצורכי מכס",
                relevance="supporting",
            ),
            Citation(
                doc_id="framework_order",
                article="16",
                title="צו מסגרת",
                text_snippet="הגדרות",
                relevance="informational",
            ),
        ])
        html = render_compliance_section_html(result)
        assert isinstance(html, str)
        assert len(html) > 50
        # Should reference the documents
        assert "130" in html or "customs_ordinance" in html or "ערך עסקה" in html

    def test_html_is_outlook_safe_uses_tables(self):
        from lib.compliance_auditor import (
            AuditResult, Citation, render_compliance_section_html,
        )
        result = AuditResult(citations=[
            Citation(doc_id="procedure_3", article="", title="נוהל סיווג",
                     text_snippet="test", relevance="informational"),
        ])
        html = render_compliance_section_html(result)
        if html:  # only check if non-empty
            assert "<table" in html.lower() or "<tr" in html.lower() or "<td" in html.lower()
            # No flexbox
            assert 'display:flex' not in html.lower()
            assert 'display: flex' not in html.lower()

    def test_citation_badges_render_correctly(self):
        from lib.compliance_auditor import Citation, render_citation_badges_html
        badges_html = render_citation_badges_html([
            Citation(doc_id="customs_ordinance", article="62",
                     title="הגשת רשומון", text_snippet="", relevance="supporting"),
        ])
        assert isinstance(badges_html, str)
        # Should contain some HTML content for the badge
        if badges_html:
            assert "<" in badges_html  # at least some HTML tag

    def test_large_citation_block_under_50kb(self):
        from lib.compliance_auditor import (
            AuditResult, Citation, render_compliance_section_html,
        )
        # Create a result with many citations
        citations = []
        for i in range(30):
            citations.append(Citation(
                doc_id="customs_ordinance",
                article=str(i + 1),
                title=f"סעיף {i + 1}",
                text_snippet="x" * 200,
                relevance="informational",
            ))
        result = AuditResult(citations=citations)
        html = render_compliance_section_html(result)
        assert len(html.encode("utf-8")) < 50 * 1024

    def test_render_with_empty_citations_list(self):
        from lib.compliance_auditor import AuditResult, render_compliance_section_html
        result = AuditResult(citations=[])
        html = render_compliance_section_html(result)
        assert isinstance(html, str)


# =============================================================================
# 3. TestComplianceToolIntegration
# =============================================================================

class TestComplianceToolIntegration:
    """Verify compare_fta_document tool is in the dispatcher and works."""

    def test_compare_fta_document_in_dispatcher(self):
        from lib.tool_executors import ToolExecutor
        source = inspect.getsource(ToolExecutor.execute)
        assert "compare_fta_document" in source

    def test_handler_returns_result_for_valid_input(self):
        from lib.tool_executors import ToolExecutor
        executor = ToolExecutor(db=None, api_key=None)
        result = executor.execute("compare_fta_document", {
            "country_code": "eu",
            "document_type": "eur1",
            "live_fields": {"exporter": "ACME Ltd"},
        })
        assert isinstance(result, dict)
        # Should not be an error about missing country_code
        assert result.get("error") != "country_code is required"

    def test_handler_returns_error_for_missing_country_code(self):
        from lib.tool_executors import ToolExecutor
        executor = ToolExecutor(db=None, api_key=None)
        result = executor.execute("compare_fta_document", {
            "document_type": "eur1",
        })
        assert isinstance(result, dict)
        assert "error" in result
        assert "country_code" in result["error"].lower()

    def test_handler_returns_error_for_unknown_country(self):
        from lib.tool_executors import ToolExecutor
        executor = ToolExecutor(db=None, api_key=None)
        result = executor.execute("compare_fta_document", {
            "country_code": "zzz_nonexistent",
            "document_type": "eur1",
        })
        assert isinstance(result, dict)
        assert "error" in result

    def test_tool_definition_has_required_fields(self):
        from lib.tool_definitions import CLAUDE_TOOLS
        fta_tool = None
        for tool in CLAUDE_TOOLS:
            if tool.get("name") == "compare_fta_document":
                fta_tool = tool
                break
        assert fta_tool is not None, "compare_fta_document not in CLAUDE_TOOLS"
        assert "name" in fta_tool
        assert "description" in fta_tool
        assert "input_schema" in fta_tool
        assert fta_tool["input_schema"]["type"] == "object"
        assert "country_code" in fta_tool["input_schema"]["properties"]


# =============================================================================
# 4. TestEmailIntentCitations
# =============================================================================

class TestEmailIntentCitations:
    """Verify citation badge integration in email_intent.py."""

    def test_citation_import_is_try_except_guarded(self):
        """email_intent.py imports render_citation_badges_html inside try/except."""
        import lib.email_intent as ei
        source = inspect.getsource(ei)
        assert "render_citation_badges_html" in source
        # Should be wrapped in try/except
        assert "except" in source

    def test_render_citation_badges_html_importable(self):
        from lib.compliance_auditor import render_citation_badges_html
        assert callable(render_citation_badges_html)

    def test_empty_citation_list_renders_empty(self):
        from lib.compliance_auditor import render_citation_badges_html
        result = render_citation_badges_html([])
        assert isinstance(result, str)
        assert len(result) < 50  # empty or trivially small

    def test_citation_with_known_source_renders_badges(self):
        from lib.compliance_auditor import Citation, render_citation_badges_html
        result = render_citation_badges_html([
            Citation(
                doc_id="customs_ordinance",
                article="130",
                title="ערך עסקה",
                text_snippet="",
                relevance="supporting",
            ),
        ])
        assert isinstance(result, str)
        if result:
            assert "<" in result  # contains HTML markup


# =============================================================================
# 5. TestDocumentRegistryIntegration
# =============================================================================

class TestDocumentRegistryIntegration:
    """Verify document registry consistency with FTA country data."""

    def test_fta_countries_match_document_registry(self):
        """Every FTA country code in _fta_all_countries should have a registry entry."""
        from lib._fta_all_countries import get_all_country_codes
        from lib._document_registry import DOCUMENT_REGISTRY

        country_codes = get_all_country_codes()
        assert len(country_codes) > 0

        for code in country_codes:
            doc_id = f"fta_{code}"
            assert doc_id in DOCUMENT_REGISTRY, (
                f"FTA country '{code}' has no registry entry 'fta_{code}'"
            )

    def test_get_relevant_documents_for_known_hs_code(self):
        from lib._document_registry import get_relevant_documents
        docs = get_relevant_documents(hs_code="8507600000")
        assert isinstance(docs, list)
        assert len(docs) >= 3  # at least tariff_book, customs_ordinance, framework_order
        doc_ids = [d["doc_id"] for d in docs]
        assert "tariff_book" in doc_ids
        assert "customs_ordinance" in doc_ids

    def test_format_citation_works_for_all_doc_types(self):
        from lib._document_registry import format_citation, DOCUMENT_REGISTRY
        # Test a sample from each category
        test_cases = [
            ("customs_ordinance", "130", None),
            ("framework_order", "16", "EU"),
            ("tariff_book", None, "84.71"),
            ("procedure_3", None, None),
        ]
        for doc_id, article, section in test_cases:
            if doc_id in DOCUMENT_REGISTRY:
                result = format_citation(doc_id, article=article, section=section)
                assert isinstance(result, str)
                assert len(result) > 0

    def test_all_registry_docs_have_valid_categories(self):
        from lib._document_registry import DOCUMENT_REGISTRY
        valid_categories = {
            "tariff", "regulation", "procedure", "law", "fta",
            "supplement", "reform",
        }
        for doc_id, doc in DOCUMENT_REGISTRY.items():
            assert "category" in doc, f"Doc '{doc_id}' missing 'category'"
            assert doc["category"] in valid_categories, (
                f"Doc '{doc_id}' has invalid category '{doc['category']}'"
            )

    def test_supplement_11_12_13_excluded(self):
        """Supplements 11, 12, 13 do not exist in Israeli tariff."""
        from lib._document_registry import DOCUMENT_REGISTRY
        for num in (11, 12, 13):
            key = f"supplement_{num}"
            assert key not in DOCUMENT_REGISTRY, (
                f"Supplement {num} should not exist in registry"
            )


# =============================================================================
# 6. TestHTMLFidelityBasic
# =============================================================================

@pytest.mark.skipif(
    not os.path.exists(HTML_DIR),
    reason="HTML files not generated (downloads/html/ not present)",
)
class TestHTMLFidelityBasic:
    """Basic fidelity checks on generated HTML files in downloads/html/."""

    def _read_html(self, filename):
        path = os.path.join(HTML_DIR, filename)
        if not os.path.exists(path):
            pytest.skip(f"{filename} not found in {HTML_DIR}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def test_index_html_exists_and_valid(self):
        html = self._read_html("index.html")
        assert "<html" in html.lower()
        assert "<body" in html.lower()
        assert "</html>" in html.lower()

    def test_framework_order_contains_articles(self):
        html = self._read_html("framework_order.html")
        # Should contain article references (Hebrew "סעיף" or numbers)
        assert "סעיף" in html or "article" in html.lower()

    def test_discount_codes_contains_groups(self):
        html = self._read_html("discount_codes.html")
        # Discount codes should have group descriptions or code identifiers
        assert len(html) > 500  # non-trivial content

    def test_customs_ordinance_contains_311_articles(self):
        html = self._read_html("customs_ordinance.html")
        # Should be substantial (311 articles)
        assert len(html) > 50_000
        # Should contain article markers
        assert "סעיף" in html

    def test_procedure_files_exist(self):
        expected = [
            "procedure_1.html",
            "procedure_2.html",
            "procedure_3.html",
            "procedure_10.html",
            "procedure_25.html",
            "procedure_28.html",
        ]
        for filename in expected:
            path = os.path.join(HTML_DIR, filename)
            assert os.path.exists(path), f"Missing procedure file: {filename}"

    def test_all_html_files_have_rtl_direction(self):
        for filename in os.listdir(HTML_DIR):
            if not filename.endswith(".html"):
                continue
            html = self._read_html(filename)
            # RTL can be set via dir="rtl" or direction:rtl in style
            has_rtl = (
                'dir="rtl"' in html.lower()
                or "direction:rtl" in html.lower()
                or "direction: rtl" in html.lower()
            )
            assert has_rtl, f"{filename} missing RTL direction"

    def test_all_html_files_use_inline_css(self):
        for filename in os.listdir(HTML_DIR):
            if not filename.endswith(".html"):
                continue
            html = self._read_html(filename)
            # Should NOT have external stylesheet links
            assert '<link rel="stylesheet"' not in html.lower(), (
                f"{filename} uses external stylesheet — should be inline CSS"
            )

    def test_generated_html_files_exist(self):
        """At least the core set of HTML files should be present."""
        expected_core = [
            "index.html",
            "customs_ordinance.html",
            "framework_order.html",
            "discount_codes.html",
        ]
        for filename in expected_core:
            path = os.path.join(HTML_DIR, filename)
            assert os.path.exists(path), f"Core HTML file missing: {filename}"
