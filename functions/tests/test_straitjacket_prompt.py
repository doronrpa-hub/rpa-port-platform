"""Tests for straitjacket_prompt.py — AI prompt builder + response parser."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import pytest
from lib.straitjacket_prompt import (
    build_straitjacket_prompt,
    parse_ai_response,
    is_valid_response,
    needs_escalation,
)
from lib.evidence_types import EvidenceBundle, EvidencePiece


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _bundle(**kwargs):
    """Create a minimal EvidenceBundle with overrides."""
    defaults = {
        "direction": "import",
        "direction_config": {"decree_name_he": "צו יבוא חופשי"},
        "domain": "customs",
        "original_subject": "מהו המכס על פלסטיק?",
        "original_body": "שלום, מה שיעור המכס על יבוא פוליאתילן?",
    }
    defaults.update(kwargs)
    return EvidenceBundle(**defaults)


# ---------------------------------------------------------------------------
#  System prompt
# ---------------------------------------------------------------------------

class TestSystemPrompt:
    def test_contains_direction(self):
        b = _bundle(direction="import")
        result = build_straitjacket_prompt(b)
        assert "יבוא" in result["system"]

    def test_contains_direction_export(self):
        b = _bundle(direction="export")
        result = build_straitjacket_prompt(b)
        assert "יצוא" in result["system"]

    def test_contains_rules(self):
        b = _bundle()
        result = build_straitjacket_prompt(b)
        sys_prompt = result["system"]
        assert "EVIDENCE" in sys_prompt
        assert "JSON" in sys_prompt
        assert "source_ref" in sys_prompt

    def test_contains_no_refuse_rule(self):
        b = _bundle()
        result = build_straitjacket_prompt(b)
        assert "לא ניתן לסווג" in result["system"]

    def test_contains_no_broker_referral(self):
        b = _bundle()
        result = build_straitjacket_prompt(b)
        assert "עמיל מכס" in result["system"]

    def test_sources_found_listed(self):
        b = _bundle(sources_found=["תעריף המכס", "פקודת המכס"])
        result = build_straitjacket_prompt(b)
        assert "תעריף המכס" in result["system"]
        assert "✓" in result["system"]

    def test_sources_not_found_listed(self):
        b = _bundle(sources_not_found=["הסכמי סחר", "הנחיות סיווג"])
        result = build_straitjacket_prompt(b)
        assert "הסכמי סחר" in result["system"]
        assert "✗" in result["system"]

    def test_output_schema_is_json(self):
        b = _bundle(tariff_entries=[{"hs_code": "3901"}])
        result = build_straitjacket_prompt(b)
        # Schema should be valid JSON embedded in system prompt
        assert "hs_candidates" in result["system"]
        assert "diagnosis" in result["system"]


# ---------------------------------------------------------------------------
#  User prompt — evidence sections
# ---------------------------------------------------------------------------

class TestUserPrompt:
    def test_contains_subject_and_body(self):
        b = _bundle()
        result = build_straitjacket_prompt(b)
        assert "מהו המכס על פלסטיק?" in result["user"]
        assert "פוליאתילן" in result["user"]

    def test_tariff_entries_shown(self):
        b = _bundle(tariff_entries=[
            {"hs_code": "3901100000", "description_he": "פוליאתילן",
             "duty": "5%", "purchase_tax": "0%", "vat": "18%",
             "source_ref": "פרט 3901100000"},
        ])
        result = build_straitjacket_prompt(b)
        assert "3901100000" in result["user"]
        assert "פוליאתילן" in result["user"]
        assert "5%" in result["user"]

    def test_ordinance_articles_shown(self):
        b = _bundle(ordinance_articles=[
            {"article_id": "132", "title_he": "ערך עסקה",
             "full_text_he": "ערך הטובין לצרכי מכס...",
             "source_ref": "סעיף 132 לפקודת המכס"},
        ])
        result = build_straitjacket_prompt(b)
        assert "סעיף 132" in result["user"]
        assert "ערך עסקה" in result["user"]
        assert "ערך הטובין לצרכי מכס" in result["user"]

    def test_regulatory_shown(self):
        b = _bundle(regulatory_requirements=[
            {"supplement": "תוספת 2", "authority": "משרד התחבורה",
             "requirement": "אישור MOT", "standard": "SI 1022",
             "source_ref": "צו יבוא חופשי, תוספת 2"},
        ])
        result = build_straitjacket_prompt(b)
        assert "משרד התחבורה" in result["user"]
        assert "SI 1022" in result["user"]

    def test_fta_shown(self):
        b = _bundle(fta_data={
            "applicable": True, "country": "EU",
            "origin_rules": "CTH", "declaration_type": "EUR.1",
            "preferential_rate": "0%", "source_ref": "EU-Israel FTA",
        })
        result = build_straitjacket_prompt(b)
        assert "EU" in result["user"]
        assert "EUR.1" in result["user"]
        assert "CTH" in result["user"]

    def test_fta_not_shown_when_not_applicable(self):
        b = _bundle(fta_data={"applicable": False})
        result = build_straitjacket_prompt(b)
        assert "הסכם סחר חופשי" not in result["user"]

    def test_web_results_shown_with_url(self):
        b = _bundle(web_results=[
            {"source_name": "Wikipedia: Polyethylene",
             "text": "PE is a common plastic...",
             "source_url": "https://en.wikipedia.org/wiki/Polyethylene"},
        ])
        result = build_straitjacket_prompt(b)
        assert "Wikipedia" in result["user"]
        assert "https://en.wikipedia.org" in result["user"]

    def test_supplier_results_shown(self):
        b = _bundle(supplier_results=[
            {"url": "https://example.com", "content": "Products",
             "source_ref": "https://example.com"},
        ])
        result = build_straitjacket_prompt(b)
        assert "example.com" in result["user"]

    def test_valuation_articles_shown(self):
        b = _bundle(valuation_articles=[
            EvidencePiece(fact="ערך העסקה הוא...", source_name="פקודת המכס",
                          source_ref="סעיף 132 לפקודת המכס", source_type="ordinance"),
        ])
        result = build_straitjacket_prompt(b)
        assert "סעיף 132" in result["user"]
        assert "ערך העסקה" in result["user"]

    def test_empty_evidence_still_valid(self):
        b = _bundle()
        result = build_straitjacket_prompt(b)
        assert "EVIDENCE" in result["user"]
        assert "סוף EVIDENCE" in result["user"]

    def test_entities_shown(self):
        b = _bundle(entities={"hs_codes": ["3901"], "countries": ["China"]})
        result = build_straitjacket_prompt(b)
        assert "3901" in result["user"]
        assert "China" in result["user"]

    def test_long_text_truncated(self):
        b = _bundle(ordinance_articles=[
            {"article_id": "130", "title_he": "ערך",
             "full_text_he": "X" * 2000,
             "source_ref": "סעיף 130"},
        ])
        result = build_straitjacket_prompt(b)
        # Should be truncated with ...
        assert "..." in result["user"]


# ---------------------------------------------------------------------------
#  Dynamic schema
# ---------------------------------------------------------------------------

class TestDynamicSchema:
    def test_hs_candidates_only_with_tariff(self):
        b = _bundle(tariff_entries=[{"hs_code": "3901"}])
        result = build_straitjacket_prompt(b)
        assert "hs_candidates" in result["system"]

    def test_no_hs_candidates_without_tariff(self):
        b = _bundle()
        result = build_straitjacket_prompt(b)
        assert "hs_candidates" not in result["system"]

    def test_regulatory_only_with_data(self):
        b = _bundle(regulatory_requirements=[{"authority": "MOH"}])
        result = build_straitjacket_prompt(b)
        assert '"regulatory"' in result["system"]

    def test_fta_only_when_applicable(self):
        b = _bundle(fta_data={"applicable": True, "country": "EU"})
        result = build_straitjacket_prompt(b)
        assert '"fta"' in result["system"]

    def test_valuation_only_for_import(self):
        b = _bundle(valuation_articles=[
            EvidencePiece(fact="x", source_name="y", source_ref="z", source_type="ordinance"),
        ])
        result = build_straitjacket_prompt(b)
        assert "valuation_notes" in result["system"]

    def test_web_answer_with_web_results(self):
        b = _bundle(web_results=[{"title": "X", "text": "Y"}])
        result = build_straitjacket_prompt(b)
        assert "web_answer" in result["system"]

    def test_always_has_diagnosis(self):
        b = _bundle()
        result = build_straitjacket_prompt(b)
        assert "diagnosis" in result["system"]

    def test_always_has_english_summary(self):
        b = _bundle()
        result = build_straitjacket_prompt(b)
        assert "english_summary" in result["system"]


# ---------------------------------------------------------------------------
#  Response parser
# ---------------------------------------------------------------------------

class TestParseAiResponse:
    def test_valid_json(self):
        raw = json.dumps({"diagnosis": {"text": "test", "certainty": "high"}})
        result = parse_ai_response(raw)
        assert result["diagnosis"]["text"] == "test"

    def test_json_with_code_fence(self):
        raw = '```json\n{"diagnosis": {"text": "hello"}}\n```'
        result = parse_ai_response(raw)
        assert result["diagnosis"]["text"] == "hello"

    def test_json_with_bare_fence(self):
        raw = '```\n{"diagnosis": {"text": "hello"}}\n```'
        result = parse_ai_response(raw)
        assert result["diagnosis"]["text"] == "hello"

    def test_json_embedded_in_text(self):
        raw = 'Here is the answer:\n{"diagnosis": {"text": "embedded"}}\nDone.'
        result = parse_ai_response(raw)
        assert result["diagnosis"]["text"] == "embedded"

    def test_empty_input(self):
        result = parse_ai_response("")
        assert result["_parse_error"] is True
        assert result["_error"] == "empty_response"

    def test_none_input(self):
        result = parse_ai_response(None)
        assert result["_parse_error"] is True

    def test_garbage_input(self):
        result = parse_ai_response("This is not JSON at all")
        assert result["_parse_error"] is True
        assert result["_error"] == "json_parse_failed"

    def test_array_not_accepted(self):
        result = parse_ai_response('[1, 2, 3]')
        assert result.get("_parse_error") is True

    def test_whitespace_handling(self):
        raw = '  \n  {"diagnosis": {"text": "spaced"}}  \n  '
        result = parse_ai_response(raw)
        assert result["diagnosis"]["text"] == "spaced"


# ---------------------------------------------------------------------------
#  Validation
# ---------------------------------------------------------------------------

class TestIsValidResponse:
    def test_valid(self):
        parsed = {"diagnosis": {"text": "This is a valid customs answer with details."}}
        assert is_valid_response(parsed) is True

    def test_empty_diagnosis(self):
        parsed = {"diagnosis": {"text": ""}}
        assert is_valid_response(parsed) is False

    def test_short_diagnosis(self):
        parsed = {"diagnosis": {"text": "ok"}}
        assert is_valid_response(parsed) is False

    def test_no_diagnosis(self):
        parsed = {"hs_candidates": []}
        assert is_valid_response(parsed) is False

    def test_parse_error(self):
        parsed = {"_parse_error": True}
        assert is_valid_response(parsed) is False

    def test_none(self):
        assert is_valid_response(None) is False

    def test_not_dict(self):
        assert is_valid_response("string") is False


# ---------------------------------------------------------------------------
#  Escalation
# ---------------------------------------------------------------------------

class TestNeedsEscalation:
    def test_valid_no_escalation(self):
        parsed = {"diagnosis": {"text": "This is a complete customs analysis."}}
        assert needs_escalation(parsed) is None

    def test_parse_error_escalates(self):
        parsed = {"_parse_error": True, "_error": "json_parse_failed"}
        assert needs_escalation(parsed) == "json_parse_failed"

    def test_empty_escalates(self):
        assert needs_escalation(None) == "empty_response"

    def test_invalid_response_escalates(self):
        parsed = {"diagnosis": {"text": ""}}
        assert needs_escalation(parsed) == "invalid_response"
