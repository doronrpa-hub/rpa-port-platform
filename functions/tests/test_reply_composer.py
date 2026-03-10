"""Tests for reply_composer.py — HTML block builders + template orchestrators."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from lib.reply_composer import (
    _block_header, _block_tracking_bar, _block_greeting,
    _block_diagnosis, _block_tariff_table, _block_fio_feo,
    _block_fta, _block_valuation, _block_release_notes,
    _block_web_answer, _block_clarifications, _block_english_summary,
    _block_footer, _block_progress, _block_container_table,
    compose_consultation, compose_live_shipment,
    compose_tracking, compose_combined,
    verify_citations, _esc,
)
from lib.evidence_types import EvidenceBundle


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _bundle(**kwargs):
    defaults = {
        "direction": "import",
        "direction_config": {"decree_name_he": "צו יבוא חופשי"},
        "domain": "customs",
        "original_subject": "שאלת סיווג",
        "original_body": "מה המכס על פלסטיק?",
    }
    defaults.update(kwargs)
    return EvidenceBundle(**defaults)


def _ai_response(**kwargs):
    defaults = {
        "diagnosis": {
            "text": "פוליאתילן מסווג בפרט 3901 לתעריף המכס.",
            "certainty": "high",
            "sources_cited": ["פרט 3901", "סעיף 132 לפקודת המכס"],
            "law_quote": "ערך הטובין לצרכי מכס הוא מחיר העסקה",
            "law_ref": "סעיף 132 לפקודת המכס",
        },
        "english_summary": "Polyethylene is classified under tariff heading 3901.",
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
#  HTML escaping
# ---------------------------------------------------------------------------

class TestEscape:
    def test_ampersand(self):
        assert _esc("A & B") == "A &amp; B"

    def test_angle_brackets(self):
        assert _esc("<script>") == "&lt;script&gt;"

    def test_none(self):
        assert _esc(None) == ""

    def test_empty(self):
        assert _esc("") == ""


# ---------------------------------------------------------------------------
#  Block 1: Header
# ---------------------------------------------------------------------------

class TestBlockHeader:
    def test_contains_rpa_port(self):
        html = _block_header("import", "consultation")
        assert "R.P.A. PORT" in html

    def test_import_direction(self):
        html = _block_header("import", "consultation")
        assert "יבוא" in html

    def test_export_direction(self):
        html = _block_header("export", "live_shipment")
        assert "יצוא" in html

    def test_unknown_direction(self):
        html = _block_header("unknown", "consultation")
        assert "ייעוץ" in html


# ---------------------------------------------------------------------------
#  Block 2: Greeting
# ---------------------------------------------------------------------------

class TestBlockGreeting:
    def test_with_name(self):
        html = _block_greeting("דורון")
        assert "דורון" in html

    def test_without_name(self):
        html = _block_greeting()
        assert "שלום" in html


# ---------------------------------------------------------------------------
#  Block 3: Diagnosis
# ---------------------------------------------------------------------------

class TestBlockDiagnosis:
    def test_with_data(self):
        html = _block_diagnosis({
            "text": "פוליאתילן מסווג בפרט 3901.",
            "certainty": "high",
            "sources_cited": ["פרט 3901"],
            "law_quote": "ערך הטובין",
            "law_ref": "סעיף 132",
        })
        assert "3901" in html
        assert "ערך הטובין" in html
        assert "סעיף 132" in html
        assert "גבוהה" in html

    def test_empty(self):
        html = _block_diagnosis(None)
        assert html == ""

    def test_low_certainty(self):
        html = _block_diagnosis({"text": "uncertain", "certainty": "low"})
        assert "נמוכה" in html


# ---------------------------------------------------------------------------
#  Block 4: Tariff table
# ---------------------------------------------------------------------------

class TestBlockTariffTable:
    def test_with_candidates(self):
        html = _block_tariff_table([
            {"code": "39.01.100000", "description": "פוליאתילן",
             "confidence": 0.85, "duty": "5%", "purchase_tax": "0%",
             "supplement_rate": "12%", "statistical_unit": "ק״ג"},
        ])
        assert "39.01.100000" in html
        assert "5%" in html
        assert "פוליאתילן" in html
        assert "85%" in html  # confidence badge
        assert "שיעור התוספות" in html  # column header
        assert "יחידה סטטיסטית" in html  # column header
        assert "12%" in html  # supplement rate value
        assert "ק״ג" in html  # statistical unit value

    def test_multiple_candidates(self):
        html = _block_tariff_table([
            {"code": "3901", "description": "A", "confidence": 0.9},
            {"code": "3902", "description": "B", "confidence": 0.3},
        ])
        assert "3901" in html
        assert "3902" in html

    def test_empty(self):
        html = _block_tariff_table(None)
        assert html == ""

    def test_six_column_headers(self):
        """Verify all 6 official columns are present."""
        html = _block_tariff_table([
            {"code": "8507.60", "description": "Li-ion", "confidence": 0.7},
        ])
        assert "פרט" in html
        assert "תיאור" in html
        assert "מכס כללי" in html
        assert "מס קנייה" in html
        assert "שיעור התוספות" in html
        assert "יחידה סטטיסטית" in html


# ---------------------------------------------------------------------------
#  Block 5: FIO/FEO
# ---------------------------------------------------------------------------

class TestBlockFioFeo:
    def test_import(self):
        html = _block_fio_feo([
            {"authority": "משרד התחבורה", "requirement": "MOT",
             "standard": "SI 1022", "source_ref": "צו יבוא חופשי"},
        ], "import")
        assert "משרד התחבורה" in html
        assert "צו יבוא חופשי" in html

    def test_export(self):
        html = _block_fio_feo([
            {"authority": "MOD", "requirement": "license"},
        ], "export")
        assert "צו יצוא חופשי" in html

    def test_empty(self):
        assert _block_fio_feo(None) == ""


# ---------------------------------------------------------------------------
#  Block 6: FTA
# ---------------------------------------------------------------------------

class TestBlockFta:
    def test_applicable(self):
        html = _block_fta({
            "applicable": True, "country": "EU",
            "preferential_rate": "0%", "origin_rule": "CTH",
            "declaration_type": "EUR.1", "source_ref": "EU-Israel FTA",
        })
        assert "EU" in html
        assert "EUR.1" in html
        assert "0%" in html

    def test_not_applicable(self):
        assert _block_fta({"applicable": False}) == ""

    def test_none(self):
        assert _block_fta(None) == ""


# ---------------------------------------------------------------------------
#  Block 7/8: Valuation + Release
# ---------------------------------------------------------------------------

class TestBlockValuation:
    def test_with_data(self):
        html = _block_valuation({"text": "ערך עסקה", "article_ref": "סעיף 132"})
        assert "ערך עסקה" in html
        assert "סעיף 132" in html

    def test_empty(self):
        assert _block_valuation(None) == ""


class TestBlockRelease:
    def test_with_data(self):
        html = _block_release_notes({"text": "שחרור", "article_ref": "סעיף 62"})
        assert "שחרור" in html
        assert "סעיף 62" in html

    def test_empty(self):
        assert _block_release_notes(None) == ""


# ---------------------------------------------------------------------------
#  Web answer
# ---------------------------------------------------------------------------

class TestBlockWebAnswer:
    def test_with_sources(self):
        html = _block_web_answer({
            "text": "PE is a plastic polymer.",
            "sources": [
                {"title": "Wikipedia: Polyethylene",
                 "url": "https://en.wikipedia.org/wiki/Polyethylene"},
            ],
        })
        assert "Wikipedia" in html
        assert "https://en.wikipedia.org" in html

    def test_empty(self):
        assert _block_web_answer(None) == ""


# ---------------------------------------------------------------------------
#  Clarifications
# ---------------------------------------------------------------------------

class TestBlockClarifications:
    def test_with_questions(self):
        html = _block_clarifications([
            {"question": "מה החומר?", "why_needed": "לסיווג מדויק"},
        ])
        assert "מה החומר?" in html
        assert "לסיווג מדויק" in html

    def test_empty(self):
        assert _block_clarifications(None) == ""
        assert _block_clarifications([]) == ""


# ---------------------------------------------------------------------------
#  English summary
# ---------------------------------------------------------------------------

class TestBlockEnglishSummary:
    def test_with_text(self):
        html = _block_english_summary("This is a test.")
        assert "This is a test." in html
        assert "ltr" in html

    def test_empty(self):
        assert _block_english_summary("") == ""
        assert _block_english_summary(None) == ""


# ---------------------------------------------------------------------------
#  Footer
# ---------------------------------------------------------------------------

class TestBlockFooter:
    def test_contains_branding(self):
        html = _block_footer()
        assert "R.P.A. PORT" in html
        assert "RCB" in html
        assert "IL" in html


# ---------------------------------------------------------------------------
#  Tracking blocks
# ---------------------------------------------------------------------------

class TestBlockProgress:
    def test_with_data(self):
        html = _block_progress({"percentage": 60, "current_step": "פריקה"})
        assert "60%" in html
        assert "פריקה" in html

    def test_empty(self):
        assert _block_progress(None) == ""


class TestBlockContainerTable:
    def test_with_containers(self):
        html = _block_container_table([
            {"container_number": "TEMU1234567", "type": "40HC",
             "status": "בנמל", "location": "חיפה"},
        ])
        assert "TEMU1234567" in html
        assert "40HC" in html

    def test_empty(self):
        assert _block_container_table(None) == ""


# ---------------------------------------------------------------------------
#  Orchestrator: consultation
# ---------------------------------------------------------------------------

class TestComposeConsultation:
    def test_returns_html_and_subject(self):
        result = compose_consultation(
            _ai_response(), _bundle(), recipient_name="דורון",
            tracking_code="RCB-Q-TEST-001",
        )
        assert "html" in result
        assert "subject" in result
        assert "tracking_code" in result
        assert result["tracking_code"] == "RCB-Q-TEST-001"

    def test_html_contains_all_sections(self):
        result = compose_consultation(
            _ai_response(
                hs_candidates=[{"code": "3901", "description": "PE",
                                "confidence": "high", "duty": "5%"}],
                regulatory=[{"authority": "SII", "requirement": "test"}],
                fta={"applicable": True, "country": "EU",
                     "preferential_rate": "0%", "origin_rule": "CTH",
                     "declaration_type": "EUR.1"},
                valuation_notes={"text": "ערך", "article_ref": "סעיף 132"},
                release_notes={"text": "שחרור", "article_ref": "סעיף 62"},
            ),
            _bundle(), recipient_name="דורון",
        )
        html = result["html"]
        assert "R.P.A. PORT" in html  # header
        assert "דורון" in html  # greeting
        assert "3901" in html  # tariff
        assert "EU" in html  # FTA
        assert "סעיף 132" in html  # valuation
        assert "סעיף 62" in html  # release
        assert "English" in html  # summary
        assert "</html>" in html  # properly closed

    def test_subject_format(self):
        result = compose_consultation(
            _ai_response(), _bundle(domain="customs"),
            tracking_code="RCB-Q-TEST-002",
        )
        assert "RCB" in result["subject"]
        assert "RCB-Q-TEST-002" in result["subject"]

    def test_empty_ai_response(self):
        result = compose_consultation({}, _bundle())
        assert "html" in result
        assert "</html>" in result["html"]

    def test_general_query_web_answer(self):
        result = compose_consultation(
            _ai_response(web_answer={
                "text": "מזג אוויר חם",
                "sources": [{"title": "Weather", "url": "https://example.com"}],
            }),
            _bundle(domain="general"),
        )
        assert "https://example.com" in result["html"]


# ---------------------------------------------------------------------------
#  Orchestrator: live shipment
# ---------------------------------------------------------------------------

class TestComposeLiveShipment:
    def test_returns_dict(self):
        result = compose_live_shipment(_ai_response(), _bundle())
        assert "html" in result
        assert "סיווג משלוח" in result["subject"]


# ---------------------------------------------------------------------------
#  Orchestrator: tracking
# ---------------------------------------------------------------------------

class TestComposeTracking:
    def test_returns_dict(self):
        result = compose_tracking(
            {"percentage": 70, "current_step": "שחרור"},
            [{"container_number": "TEST123", "type": "40HC",
              "status": "OK", "location": "Haifa"}],
        )
        assert "html" in result
        assert "מעקב" in result["subject"]
        assert "70%" in result["html"]


# ---------------------------------------------------------------------------
#  Orchestrator: combined
# ---------------------------------------------------------------------------

class TestComposeCombined:
    def test_returns_dict(self):
        result = compose_combined(
            _ai_response(),
            _bundle(),
            tracking_data={"percentage": 50, "current_step": "פריקה"},
            container_data=[{"container_number": "C1", "type": "20GP",
                             "status": "OK", "location": "Ashdod"}],
        )
        assert "html" in result
        assert "סיווג + מעקב" in result["subject"]
        assert "50%" in result["html"]
        assert "C1" in result["html"]


# ---------------------------------------------------------------------------
#  Compliance verification
# ---------------------------------------------------------------------------

class TestVerifyCitations:
    def test_clean_pass(self):
        bundle = _bundle(tariff_entries=[{"hs_code": "3901100000"}])
        ai = {"hs_candidates": [{"code": "39.01.100000"}]}
        result = verify_citations(ai, bundle)
        assert result["passed"] is True

    def test_fta_mismatch(self):
        bundle = _bundle()  # no FTA data
        ai = {"fta": {"applicable": True, "country": "EU"}}
        result = verify_citations(ai, bundle)
        assert result["passed"] is False
        assert any("FTA" in e for e in result["errors"])

    def test_empty_ai(self):
        result = verify_citations(None, _bundle())
        assert result["passed"] is False

    def test_no_warnings_when_all_match(self):
        bundle = _bundle(
            tariff_entries=[{"hs_code": "3901100000"}],
            regulatory_requirements=[{"authority": "SII"}],
        )
        ai = {
            "hs_candidates": [{"code": "3901"}],
            "regulatory": [{"authority": "SII"}],
        }
        result = verify_citations(ai, bundle)
        assert result["passed"] is True
        assert len(result["warnings"]) == 0
