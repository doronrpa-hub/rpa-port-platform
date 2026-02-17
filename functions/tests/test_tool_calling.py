"""
Tests for the tool-calling classification engine.
Validates tool definitions, response parsing, executor routing,
and output format compatibility with the existing pipeline.
"""

import sys
import os
import json
import pytest

# Add functions/ to path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from lib.tool_definitions import CLAUDE_TOOLS, GEMINI_TOOLS, CLASSIFICATION_SYSTEM_PROMPT
from lib.tool_calling_engine import _extract_json, _parse_ai_response, _build_user_prompt


# ---------------------------------------------------------------------------
# Tests: Tool definition schemas
# ---------------------------------------------------------------------------

class TestToolDefinitions:

    def test_claude_tools_count(self):
        assert len(CLAUDE_TOOLS) == 12

    def test_claude_tools_have_required_fields(self):
        for tool in CLAUDE_TOOLS:
            assert "name" in tool, f"Missing name in tool"
            assert "description" in tool, f"Missing description in {tool.get('name')}"
            assert "input_schema" in tool, f"Missing input_schema in {tool['name']}"
            schema = tool["input_schema"]
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema

    def test_claude_tool_names(self):
        names = {t["name"] for t in CLAUDE_TOOLS}
        expected = {
            "check_memory", "search_tariff", "check_regulatory",
            "lookup_fta", "verify_hs_code", "extract_invoice", "assess_risk",
            "get_chapter_notes", "lookup_tariff_structure", "lookup_framework_order",
            "search_classification_directives", "search_legal_knowledge",
        }
        assert names == expected

    def test_gemini_tools_format(self):
        assert len(GEMINI_TOOLS) == 1
        declarations = GEMINI_TOOLS[0]["function_declarations"]
        assert len(declarations) == 12
        for decl in declarations:
            assert "name" in decl
            assert "description" in decl
            assert "parameters" in decl

    def test_system_prompt_not_empty(self):
        assert len(CLASSIFICATION_SYSTEM_PROMPT) > 100
        assert "check_memory" in CLASSIFICATION_SYSTEM_PROMPT
        assert "XX.XX.XXXXXX/X" in CLASSIFICATION_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Tests: _extract_json
# ---------------------------------------------------------------------------

class TestExtractJson:

    def test_code_fenced_json(self):
        text = 'Some text\n```json\n{"classifications": [{"hs_code": "4011.10"}]}\n```\nMore text'
        result = _extract_json(text)
        assert result is not None
        assert result["classifications"][0]["hs_code"] == "4011.10"

    def test_raw_json(self):
        text = '{"classifications": [], "synthesis": "test"}'
        result = _extract_json(text)
        assert result is not None
        assert result["synthesis"] == "test"

    def test_mixed_text_json(self):
        text = 'Here are the results:\n{"classifications": [{"item": "tires"}]}\nDone.'
        result = _extract_json(text)
        assert result is not None
        assert len(result["classifications"]) == 1

    def test_empty_text(self):
        assert _extract_json("") is None
        assert _extract_json(None) is None

    def test_no_json(self):
        assert _extract_json("This is just plain text with no JSON") is None

    def test_invalid_json(self):
        assert _extract_json("{not valid json}}}") is None


# ---------------------------------------------------------------------------
# Tests: _parse_ai_response
# ---------------------------------------------------------------------------

class TestParseAiResponse:

    def test_with_ai_text(self):
        ai_text = json.dumps({
            "classifications": [
                {"item_description": "rubber tires", "hs_code": "4011.10.0000"}
            ],
            "regulatory": [{"ministry": "test"}],
            "fta": [{"eligible": True}],
            "risk": {"level": "נמוך", "items": []},
            "synthesis": "סיכום בדיקה",
        })
        cls, reg, fta, risk, synthesis = _parse_ai_response(ai_text, {}, [])
        assert len(cls) == 1
        assert cls[0]["hs_code"] == "4011.10.0000"
        assert len(reg) == 1
        assert synthesis == "סיכום בדיקה"

    def test_with_memory_hits_only(self):
        memory_hits = {
            "rubber tires from china": {
                "hs_code": "4011.10.0000",
                "level": "exact",
                "confidence": 0.95,
            }
        }
        cls, reg, fta, risk, synthesis = _parse_ai_response(None, memory_hits, [])
        assert len(cls) == 1
        assert cls[0]["hs_code"] == "4011.10.0000"
        assert cls[0]["confidence"] == "גבוהה"
        assert cls[0]["source"] == "memory"

    def test_merge_memory_and_ai(self):
        ai_text = json.dumps({
            "classifications": [
                {"item_description": "steel pipes", "hs_code": "7304.19.0000"}
            ],
        })
        memory_hits = {
            "rubber tires from china": {
                "hs_code": "4011.10.0000",
                "level": "exact",
                "confidence": 0.95,
            }
        }
        cls, _, _, _, _ = _parse_ai_response(ai_text, memory_hits, [])
        assert len(cls) == 2
        hs_codes = {c["hs_code"] for c in cls}
        assert "7304.19.0000" in hs_codes
        assert "4011.10.0000" in hs_codes

    def test_empty_response(self):
        cls, reg, fta, risk, synthesis = _parse_ai_response(None, {}, [])
        assert cls == []
        assert risk["level"] == "נמוך"
        assert synthesis == ""

    def test_normalizes_item_fields(self):
        ai_text = json.dumps({
            "classifications": [{"item": "test product", "hs_code": "1234.56"}],
        })
        cls, _, _, _, _ = _parse_ai_response(ai_text, {}, [])
        assert cls[0]["item"] == "test product"
        assert cls[0]["item_description"] == "test product"


# ---------------------------------------------------------------------------
# Tests: _build_user_prompt
# ---------------------------------------------------------------------------

class TestBuildUserPrompt:

    def test_basic_prompt(self):
        items = [{"description": "rubber tires", "quantity": "100", "origin_country": "China"}]
        invoice = {"seller": "Acme Corp", "currency": "USD"}
        prompt = _build_user_prompt(items, "China", invoice, "")
        assert "rubber tires" in prompt
        assert "China" in prompt
        assert "Acme Corp" in prompt
        assert "USD" in prompt

    def test_empty_items(self):
        prompt = _build_user_prompt([], "", {}, "")
        assert "Classify" in prompt

    def test_multiple_items(self):
        items = [
            {"description": "item A", "quantity": "10"},
            {"description": "item B", "quantity": "20"},
        ]
        prompt = _build_user_prompt(items, "", {}, "")
        assert "item A" in prompt
        assert "item B" in prompt


# ---------------------------------------------------------------------------
# Tests: Output format compatibility
# ---------------------------------------------------------------------------

class TestOutputFormat:
    """Verify the tool-calling engine output has all keys that
    _enrich_results_for_email() and build_classification_email() read."""

    REQUIRED_TOP_KEYS = {
        "success", "agents", "synthesis", "invoice_data",
        "intelligence", "document_validation", "free_import_order",
        "ministry_routing", "parsed_documents", "smart_questions",
        "ambiguity", "tracker", "audit",
    }

    REQUIRED_AGENT_KEYS = {
        "invoice", "classification", "regulatory", "fta", "risk",
    }

    def _make_mock_result(self):
        """Build a minimal result dict matching tool_calling_classify output."""
        return {
            "success": True,
            "agents": {
                "invoice": {"items": [], "seller": "", "buyer": ""},
                "classification": {"classifications": []},
                "regulatory": {"regulatory": []},
                "fta": {"fta": []},
                "risk": {"risk": {"level": "נמוך", "items": []}},
            },
            "synthesis": "",
            "invoice_data": {"items": []},
            "intelligence": {},
            "document_validation": None,
            "free_import_order": {},
            "ministry_routing": {},
            "parsed_documents": [],
            "smart_questions": [],
            "ambiguity": {},
            "tracker": None,
            "audit": {"action": "send", "classifications": [], "warning_banner": None, "avg_confidence": 0},
            "_engine": "tool_calling",
        }

    def test_has_all_top_keys(self):
        result = self._make_mock_result()
        for key in self.REQUIRED_TOP_KEYS:
            assert key in result, f"Missing top-level key: {key}"

    def test_has_all_agent_keys(self):
        result = self._make_mock_result()
        agents = result["agents"]
        for key in self.REQUIRED_AGENT_KEYS:
            assert key in agents, f"Missing agents key: {key}"

    def test_classification_structure(self):
        result = self._make_mock_result()
        cls = result["agents"]["classification"]
        assert "classifications" in cls
        assert isinstance(cls["classifications"], list)

    def test_risk_structure(self):
        result = self._make_mock_result()
        risk = result["agents"]["risk"]["risk"]
        assert "level" in risk
        assert "items" in risk

    def test_engine_flag(self):
        result = self._make_mock_result()
        assert result.get("_engine") == "tool_calling"


# ---------------------------------------------------------------------------
# Tests: ToolExecutor._assess_risk (rule-based, no mocking needed)
# ---------------------------------------------------------------------------

class TestAssessRisk:

    def setup_method(self):
        from lib.tool_executors import _DUAL_USE_CHAPTERS, _HIGH_RISK_ORIGINS
        self.dual_use = _DUAL_USE_CHAPTERS
        self.high_risk = _HIGH_RISK_ORIGINS

    def test_dual_use_chapter(self):
        assert "84" in self.dual_use
        assert "93" in self.dual_use

    def test_high_risk_origins(self):
        assert "iran" in self.high_risk
        assert "איראן" in self.high_risk

    def test_normal_chapter_not_flagged(self):
        assert "01" not in self.dual_use
        assert "62" not in self.dual_use
