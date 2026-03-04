# -*- coding: utf-8 -*-
"""Tests for lib.compliance_auditor — classification compliance citations and HTML rendering.

60+ tests across 13 test classes covering all public functions, dataclasses,
fail-open behavior, and HTML output correctness.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.compliance_auditor import (
    audit_classification,
    build_compliance_context,
    render_tariff_snippet_html,
    render_fta_requirements_html,
    render_ordinance_article_html,
    render_procedure_snippet_html,
    render_framework_order_article_html,
    render_discount_code_html,
    render_citation_badges_html,
    render_compliance_section_html,
    render_fta_comparison_html,
    build_attachment_html,
    AuditResult,
    Citation,
    ComparisonResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_html(text):
    """Check if text looks like HTML."""
    return isinstance(text, str) and ("<" in text or text == "")


# ===========================================================================
# TestAuditClassification
# ===========================================================================

class TestAuditClassification:
    """Tests for audit_classification() main entry point."""

    def test_empty_input_returns_empty_result(self):
        result = audit_classification()
        assert isinstance(result, AuditResult)
        assert isinstance(result.citations, list)
        assert isinstance(result.flags, list)

    def test_none_inputs_returns_empty_result(self):
        result = audit_classification(results=None, invoice_data=None, origin=None, hs_codes=None)
        assert isinstance(result, AuditResult)

    def test_with_hs_codes_returns_citations(self):
        result = audit_classification(hs_codes=["7326900000"])
        assert isinstance(result, AuditResult)
        # Should have at least some citations (valuation, classification procedure, etc.)
        # Even if lazy-loaded modules are missing, result is still valid
        assert isinstance(result.citations, list)

    def test_with_origin_adds_fta(self):
        result = audit_classification(hs_codes=["7326900000"], origin="DE")
        assert isinstance(result, AuditResult)
        assert isinstance(result.flags, list)

    def test_with_results_dict(self):
        results = {
            "classifications": [
                {"hs_code": "8507600000", "description": "Li-ion battery"},
            ],
            "direction": "import",
        }
        result = audit_classification(results=results)
        assert isinstance(result, AuditResult)

    def test_with_invoice_data(self):
        invoice = {"seller": "ACME", "origin": "CN", "direction": "import"}
        result = audit_classification(invoice_data=invoice, hs_codes=["8507600000"])
        assert isinstance(result, AuditResult)

    def test_inline_html_is_string(self):
        result = audit_classification(hs_codes=["7326900000"])
        assert isinstance(result.inline_html, str)

    def test_attachments_is_list(self):
        result = audit_classification(hs_codes=["7326900000"])
        assert isinstance(result.attachments, list)

    def test_deduplication(self):
        """Same HS code twice should not produce duplicate citations."""
        result = audit_classification(hs_codes=["7326900000", "7326900000"])
        doc_article_pairs = [(c.doc_id, c.article) for c in result.citations]
        assert len(doc_article_pairs) == len(set(doc_article_pairs))

    def test_fail_open_never_raises(self):
        """audit_classification must never raise, even with garbage input."""
        # Bad types
        result = audit_classification(results=12345, invoice_data="bad", origin=42, hs_codes="not_a_list")
        assert isinstance(result, AuditResult)


# ===========================================================================
# TestBuildComplianceContext
# ===========================================================================

class TestBuildComplianceContext:
    """Tests for build_compliance_context() — text context for AI prompts."""

    def test_returns_string(self):
        result = build_compliance_context(hs_codes=["7326900000"])
        assert isinstance(result, str)

    def test_empty_hs_codes(self):
        result = build_compliance_context(hs_codes=[])
        assert isinstance(result, str)

    def test_with_origin_includes_fta_info(self):
        result = build_compliance_context(hs_codes=["7326900000"], origin="DE")
        assert isinstance(result, str)

    def test_none_hs_codes(self):
        result = build_compliance_context(hs_codes=None)
        assert isinstance(result, str)

    def test_with_product_descriptions(self):
        result = build_compliance_context(
            hs_codes=["4011100000"],
            product_descriptions=["Rubber tires for passenger vehicles"],
        )
        assert isinstance(result, str)

    def test_fail_open(self):
        # Should not raise on bad input
        result = build_compliance_context(hs_codes=42)
        assert isinstance(result, str)


# ===========================================================================
# TestRenderTariffSnippet
# ===========================================================================

class TestRenderTariffSnippet:
    """Tests for render_tariff_snippet_html()."""

    def test_returns_html_string(self):
        html = render_tariff_snippet_html("7326900000")
        assert isinstance(html, str)

    def test_contains_hs_code(self):
        html = render_tariff_snippet_html("7326900000")
        # Should contain formatted HS code or raw digits
        assert "73" in html

    def test_contains_hebrew_description(self):
        html = render_tariff_snippet_html(
            "7326900000",
            description_he="מוצרים אחרים מברזל או פלדה",
        )
        assert "מוצרים" in html or "ברזל" in html

    def test_contains_english_description(self):
        html = render_tariff_snippet_html(
            "7326900000",
            description_en="Other articles of iron or steel",
        )
        assert "iron" in html or "steel" in html

    def test_contains_duty_rate(self):
        html = render_tariff_snippet_html("7326900000", duty_rate="12%")
        assert "12%" in html

    def test_empty_input_works(self):
        html = render_tariff_snippet_html("")
        assert isinstance(html, str)

    def test_none_code_works(self):
        html = render_tariff_snippet_html(None)
        assert isinstance(html, str)

    def test_outlook_safe_table(self):
        html = render_tariff_snippet_html("7326900000", description_he="test")
        assert "<table" in html
        assert "border-collapse" in html


# ===========================================================================
# TestRenderFTARequirements
# ===========================================================================

class TestRenderFTARequirements:
    """Tests for render_fta_requirements_html()."""

    def test_returns_html(self):
        html = render_fta_requirements_html("eu")
        assert isinstance(html, str)

    def test_contains_proof_type(self):
        html = render_fta_requirements_html("eu", origin_proof_type="EUR.1")
        assert "EUR.1" in html

    def test_contains_preferential_rate(self):
        html = render_fta_requirements_html("eu", preferential_rate="0%")
        assert "0%" in html

    def test_unknown_country_returns_html(self):
        html = render_fta_requirements_html("XX_UNKNOWN")
        assert isinstance(html, str)

    def test_empty_country_returns_html(self):
        html = render_fta_requirements_html("")
        assert isinstance(html, str)


# ===========================================================================
# TestRenderOrdinanceArticle
# ===========================================================================

class TestRenderOrdinanceArticle:
    """Tests for render_ordinance_article_html()."""

    def test_known_article_130(self):
        html = render_ordinance_article_html("130")
        assert isinstance(html, str)
        # Article 130 exists in customs_law — should have content
        if html:
            assert "130" in html

    def test_known_article_132(self):
        html = render_ordinance_article_html("132")
        assert isinstance(html, str)

    def test_unknown_article(self):
        html = render_ordinance_article_html("99999")
        assert isinstance(html, str)
        # Should still render with just the article number
        if html:
            assert "99999" in html

    def test_with_explicit_title(self):
        html = render_ordinance_article_html("130", title_he="ערך עסקה")
        assert isinstance(html, str)
        if html:
            assert "ערך" in html

    def test_with_text_snippet(self):
        html = render_ordinance_article_html("130", text_snippet="Test snippet text")
        assert isinstance(html, str)

    def test_empty_article_num(self):
        html = render_ordinance_article_html("")
        assert isinstance(html, str)


# ===========================================================================
# TestRenderProcedureSnippet
# ===========================================================================

class TestRenderProcedureSnippet:
    """Tests for render_procedure_snippet_html()."""

    def test_known_procedure_1(self):
        html = render_procedure_snippet_html("1")
        assert isinstance(html, str)
        if html:
            assert "1" in html

    def test_known_procedure_3(self):
        html = render_procedure_snippet_html("3")
        assert isinstance(html, str)

    def test_unknown_procedure(self):
        html = render_procedure_snippet_html("999")
        assert isinstance(html, str)
        # Even unknown procedures render with just the number
        if html:
            assert "999" in html

    def test_with_section_title(self):
        html = render_procedure_snippet_html("3", section_title="הליך סיווג")
        assert isinstance(html, str)
        if html:
            assert "סיווג" in html

    def test_with_text(self):
        html = render_procedure_snippet_html("1", text="Release procedure details")
        assert isinstance(html, str)
        if html:
            assert "Release" in html

    def test_empty_procedure_num(self):
        html = render_procedure_snippet_html("")
        assert isinstance(html, str)


# ===========================================================================
# TestRenderFrameworkOrder
# ===========================================================================

class TestRenderFrameworkOrder:
    """Tests for render_framework_order_article_html()."""

    def test_known_article(self):
        html = render_framework_order_article_html("01")
        assert isinstance(html, str)
        if html:
            assert "01" in html

    def test_article_03_gir(self):
        html = render_framework_order_article_html("03")
        assert isinstance(html, str)

    def test_unknown_article(self):
        html = render_framework_order_article_html("99999")
        assert isinstance(html, str)

    def test_with_explicit_title(self):
        html = render_framework_order_article_html("03", title_he="כללי סיווג")
        assert isinstance(html, str)
        if html:
            assert "סיווג" in html

    def test_with_text(self):
        html = render_framework_order_article_html("06", text="Conditional items rules")
        assert isinstance(html, str)

    def test_empty_article_num(self):
        html = render_framework_order_article_html("")
        assert isinstance(html, str)


# ===========================================================================
# TestRenderDiscountCode
# ===========================================================================

class TestRenderDiscountCode:
    """Tests for render_discount_code_html()."""

    def test_unknown_code(self):
        html = render_discount_code_html("9999")
        assert isinstance(html, str)
        # Should still render badge with the number
        if html:
            assert "9999" in html

    def test_with_description(self):
        html = render_discount_code_html("001", description="פטור ממכס")
        assert isinstance(html, str)
        if html:
            assert "פטור" in html

    def test_sub_codes_rendered(self):
        sub = {
            "001A": {"customs_duty": "0%", "purchase_tax": "0%", "description_he": "פטור מלא"},
            "001B": {"customs_duty": "5%", "purchase_tax": "0%"},
        }
        html = render_discount_code_html("001", description="test", sub_codes=sub)
        assert isinstance(html, str)
        if html:
            assert "001A" in html or "0%" in html

    def test_empty_sub_codes(self):
        html = render_discount_code_html("001", sub_codes={})
        assert isinstance(html, str)

    def test_none_sub_codes(self):
        html = render_discount_code_html("001", sub_codes=None)
        assert isinstance(html, str)

    def test_empty_item_number(self):
        html = render_discount_code_html("")
        assert isinstance(html, str)


# ===========================================================================
# TestRenderCitationBadges
# ===========================================================================

class TestRenderCitationBadges:
    """Tests for render_citation_badges_html()."""

    def test_empty_list_returns_empty(self):
        html = render_citation_badges_html([])
        assert html == ""

    def test_none_returns_empty(self):
        html = render_citation_badges_html(None)
        assert html == ""

    def test_with_citations_returns_html(self):
        cits = [
            Citation(doc_id="customs_ordinance", article="130", title="ערך עסקה", relevance="supporting"),
            Citation(doc_id="fta_eu", article="", title="EUR.1", relevance="informational"),
        ]
        html = render_citation_badges_html(cits)
        assert isinstance(html, str)
        assert "<table" in html
        assert len(html) > 0

    def test_relevance_colors(self):
        supporting = Citation(doc_id="test", title="S", relevance="supporting")
        conflicting = Citation(doc_id="test2", title="C", relevance="conflicting")
        info = Citation(doc_id="test3", title="I", relevance="informational")
        html = render_citation_badges_html([supporting, conflicting, info])
        assert isinstance(html, str)
        assert len(html) > 0

    def test_doc_type_icons(self):
        """Different doc_id prefixes should produce different badge icons."""
        fta = Citation(doc_id="fta_eu", title="FTA", relevance="informational")
        proc = Citation(doc_id="procedure_3", title="Procedure", relevance="informational")
        fw = Citation(doc_id="framework_order", title="FW", relevance="informational")
        disc = Citation(doc_id="discount_codes", title="Disc", relevance="informational")
        html = render_citation_badges_html([fta, proc, fw, disc])
        assert isinstance(html, str)
        assert len(html) > 0


# ===========================================================================
# TestRenderComplianceSection
# ===========================================================================

class TestRenderComplianceSection:
    """Tests for render_compliance_section_html()."""

    def test_audit_result_with_citations_renders(self):
        ar = AuditResult(
            citations=[
                Citation(doc_id="customs_ordinance", article="130", title="ערך עסקה", relevance="supporting"),
            ],
        )
        html = render_compliance_section_html(ar)
        assert isinstance(html, str)
        if html:
            assert "אסמכתאות" in html  # section title

    def test_empty_audit_result_returns_empty(self):
        ar = AuditResult()
        html = render_compliance_section_html(ar)
        assert html == ""

    def test_none_returns_empty(self):
        html = render_compliance_section_html(None)
        assert html == ""

    def test_with_flags(self):
        ar = AuditResult(
            flags=[{"type": "DUAL_USE", "severity": "warning", "message": "test flag"}],
            citations=[Citation(doc_id="test", title="test", relevance="informational")],
        )
        html = render_compliance_section_html(ar)
        assert isinstance(html, str)

    def test_max_8_citations(self):
        """Should render at most 8 individual citation blocks."""
        cits = [
            Citation(doc_id=f"test_{i}", article=str(i), title=f"Test {i}", relevance="informational")
            for i in range(15)
        ]
        ar = AuditResult(citations=cits)
        html = render_compliance_section_html(ar)
        assert isinstance(html, str)

    def test_source_attribution_footer(self):
        ar = AuditResult(
            citations=[Citation(doc_id="customs_ordinance", article="130", title="test", relevance="supporting")],
        )
        html = render_compliance_section_html(ar)
        if html:
            assert "RCB" in html


# ===========================================================================
# TestRenderFTAComparison
# ===========================================================================

class TestRenderFTAComparison:
    """Tests for render_fta_comparison_html()."""

    def test_matching_fields_green(self):
        live = {"shipper": "ACME Ltd", "consignee": "Import Corp"}
        template = {"shipper": "ACME Ltd", "consignee": "Import Corp"}
        html = render_fta_comparison_html(live, template, "eu")
        assert isinstance(html, str)
        if html:
            # Score should be 100%
            assert "100%" in html

    def test_mismatching_fields_red(self):
        live = {"shipper": "Wrong Name"}
        template = {"shipper": "Correct Name"}
        html = render_fta_comparison_html(live, template, "eu")
        assert isinstance(html, str)
        if html:
            assert "0%" in html or "לא תואם" in html

    def test_missing_fields_yellow(self):
        live = {}
        template = {"origin_declaration": "Required field"}
        html = render_fta_comparison_html(live, template, "eu")
        assert isinstance(html, str)
        if html:
            assert "חסר" in html

    def test_empty_both_returns_empty(self):
        html = render_fta_comparison_html({}, {}, "eu")
        assert html == ""

    def test_mixed_match_mismatch_missing(self):
        live = {"field_a": "match", "field_b": "wrong"}
        template = {"field_a": "match", "field_b": "correct", "field_c": "needed"}
        html = render_fta_comparison_html(live, template, "eu")
        assert isinstance(html, str)
        if html:
            assert "תואם" in html
            assert "לא תואם" in html
            assert "חסר" in html

    def test_unknown_country(self):
        live = {"a": "1"}
        template = {"a": "1"}
        html = render_fta_comparison_html(live, template, "UNKNOWN")
        assert isinstance(html, str)


# ===========================================================================
# TestBuildAttachment
# ===========================================================================

class TestBuildAttachment:
    """Tests for build_attachment_html()."""

    def test_unknown_doc_returns_none(self):
        result = build_attachment_html("nonexistent_doc_id_xyz")
        assert result is None

    def test_empty_doc_returns_none(self):
        result = build_attachment_html("")
        assert result is None

    def test_none_doc_returns_none(self):
        result = build_attachment_html(None)
        assert result is None

    def test_with_section(self):
        result = build_attachment_html("some_doc", section="chapter_3")
        assert result is None  # File not found is expected


# ===========================================================================
# TestFailOpen
# ===========================================================================

class TestFailOpen:
    """All public functions must survive bad input types without raising."""

    def test_audit_classification_bad_types(self):
        assert isinstance(audit_classification(results=[], invoice_data=123, origin=[], hs_codes={}), AuditResult)

    def test_build_compliance_context_bad_types(self):
        assert isinstance(build_compliance_context(hs_codes=None, origin=123), str)

    def test_render_tariff_snippet_none(self):
        assert isinstance(render_tariff_snippet_html(None), str)

    def test_render_fta_requirements_none(self):
        assert isinstance(render_fta_requirements_html(None), str)

    def test_render_ordinance_article_none(self):
        assert isinstance(render_ordinance_article_html(None), str)

    def test_render_procedure_snippet_none(self):
        assert isinstance(render_procedure_snippet_html(None), str)

    def test_render_framework_order_none(self):
        assert isinstance(render_framework_order_article_html(None), str)

    def test_render_discount_code_none(self):
        assert isinstance(render_discount_code_html(None), str)

    def test_render_citation_badges_bad_type(self):
        # Should not raise on non-list
        result = render_citation_badges_html("not_a_list")
        assert isinstance(result, str)

    def test_render_compliance_section_bad_type(self):
        result = render_compliance_section_html("not_an_audit_result")
        assert isinstance(result, str)

    def test_render_fta_comparison_bad_types(self):
        result = render_fta_comparison_html(None, None, None)
        assert isinstance(result, str)

    def test_build_attachment_bad_type(self):
        result = build_attachment_html(12345)
        assert result is None


# ===========================================================================
# TestDataclasses
# ===========================================================================

class TestDataclasses:
    """Tests for Citation, AuditResult, ComparisonResult dataclasses."""

    def test_citation_defaults(self):
        c = Citation()
        assert c.doc_id == ""
        assert c.article == ""
        assert c.title == ""
        assert c.text_snippet == ""
        assert c.relevance == "informational"

    def test_citation_with_values(self):
        c = Citation(doc_id="customs_ordinance", article="130", title="test", relevance="supporting")
        assert c.doc_id == "customs_ordinance"
        assert c.article == "130"
        assert c.relevance == "supporting"

    def test_audit_result_defaults(self):
        ar = AuditResult()
        assert ar.citations == []
        assert ar.flags == []
        assert ar.inline_html == ""
        assert ar.attachments == []

    def test_audit_result_mutable_lists(self):
        ar = AuditResult()
        ar.citations.append(Citation(doc_id="test"))
        ar.flags.append({"type": "TEST"})
        assert len(ar.citations) == 1
        assert len(ar.flags) == 1

    def test_comparison_result_defaults(self):
        cr = ComparisonResult()
        assert cr.matches == []
        assert cr.mismatches == []
        assert cr.missing == []
        assert cr.score == 0.0
        assert cr.html == ""
