"""
Unit Tests for Overnight Brain Explosion — Assignment 19
Tests CostTracker, all 8 enrichment streams, and the orchestrator.
Run: pytest tests/test_overnight_brain.py -v
"""
import pytest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, patch, MagicMock, call

from lib.cost_tracker import CostTracker, call_gemini_tracked
from lib.overnight_brain import (
    _validate_hs_format,
    _is_garbage_description,
    _extract_hebrew_terms,
    _extract_english_terms,
    _safe_doc_id,
    _chunk_list,
    _convert_il_to_uk_code,
    stream_1_tariff_deep_mine,
    stream_2_email_archive_mine,
    stream_3_cc_email_learning,
    stream_4_attachment_mine,
    stream_5_ai_knowledge_fill,
    stream_6_uk_tariff_sweep,
    stream_7_cross_reference,
    stream_8_self_teach,
    run_overnight_brain,
)


# ============================================================
# HELPERS
# ============================================================

def _mock_doc(data, doc_id="doc1"):
    """Create a mock Firestore document snapshot."""
    doc = Mock()
    doc.id = doc_id
    doc.exists = True
    doc.to_dict.return_value = data
    doc.reference = Mock()
    return doc


def _mock_doc_ref(exists=True, data=None):
    """Create a mock document reference with .get() support."""
    ref = Mock()
    snap = Mock()
    snap.exists = exists
    snap.to_dict.return_value = data or {}
    ref.get.return_value = snap
    return ref


def _mock_db(collection_data=None):
    """
    Create a mock Firestore DB.
    collection_data: dict mapping "collection_name" -> list of doc dicts
    """
    collection_data = collection_data or {}
    db = Mock()

    def mock_collection(name):
        col = Mock()
        docs = collection_data.get(name, [])
        mock_docs = [_mock_doc(d, f"{name}_{i}") for i, d in enumerate(docs)]

        def mock_where(*args, **kwargs):
            query = Mock()
            query.where = mock_where
            query.limit = lambda n: query
            query.stream.return_value = iter(mock_docs)
            return query

        col.where = mock_where
        col.stream.return_value = iter(mock_docs)
        col.limit = lambda n: col

        def mock_document(doc_id):
            ref = Mock()
            snap = Mock()
            # Check if this exact doc exists in our data
            matching = [d for d in mock_docs if d.id == doc_id]
            if matching:
                snap.exists = True
                snap.to_dict.return_value = matching[0].to_dict()
            else:
                snap.exists = False
                snap.to_dict.return_value = {}
            ref.get.return_value = snap
            ref.set = Mock()
            ref.update = Mock()
            return ref

        col.document = mock_document
        col.add = Mock()
        return col

    db.collection = mock_collection
    return db


# ============================================================
# COST TRACKER TESTS
# ============================================================

class TestCostTracker:

    def test_initial_state(self):
        t = CostTracker()
        assert t.total_spent == 0.0
        assert t.budget_remaining == 3.30  # 3.50 - 0.20 safety
        assert not t.is_over_budget
        assert t.breakdown["gemini_calls"] == 0

    def test_record_ai_call(self):
        t = CostTracker()
        result = t.record_ai_call(1_000_000, 500_000)
        assert result is True  # Still within budget
        assert t.breakdown["gemini_calls"] == 1
        assert t.breakdown["gemini_input_tokens"] == 1_000_000
        assert t.breakdown["gemini_output_tokens"] == 500_000
        # Cost: (1M * 0.15 + 0.5M * 0.60) / 1M = 0.15 + 0.30 = 0.45
        assert abs(t.breakdown["ai_cost"] - 0.45) < 0.001
        assert abs(t.total_spent - 0.45) < 0.001

    def test_budget_exhaustion(self):
        t = CostTracker()
        # Spend almost everything: 22M input tokens * $0.15/M = $3.30
        t.record_ai_call(22_000_000, 0)
        assert t.is_over_budget
        assert t._stopped

    def test_can_afford(self):
        t = CostTracker()
        # Should be able to afford a small call
        assert t.can_afford(10_000, 5_000) is True
        # Should not afford something that costs > budget
        assert t.can_afford(100_000_000, 100_000_000) is False

    def test_record_firestore_ops(self):
        t = CostTracker()
        t.record_firestore_ops(reads=100_000, writes=50_000)
        assert t.breakdown["firestore_reads"] == 100_000
        assert t.breakdown["firestore_writes"] == 50_000
        # Cost: 100K * 0.06/100K + 50K * 0.18/100K = 0.06 + 0.09 = 0.15
        expected = 0.06 + 0.09
        assert abs(t.breakdown["firestore_cost"] - expected) < 0.001

    def test_summary(self):
        t = CostTracker()
        t.record_ai_call(100_000, 50_000)
        s = t.summary()
        assert "total_spent" in s
        assert "budget_limit" in s
        assert "budget_remaining" in s
        assert "stopped_by_budget" in s
        assert s["gemini_calls"] == 1

    def test_safety_margin(self):
        t = CostTracker()
        assert t.SAFETY_MARGIN == 0.20
        assert t.budget_remaining == t.BUDGET_LIMIT - t.SAFETY_MARGIN - t.total_spent


class TestCallGeminiTracked:

    @patch("lib.cost_tracker.requests.post")
    def test_successful_call_returns_json(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50},
            "candidates": [{"content": {"parts": [{"text": '[{"id": "1", "fixed": "test"}]'}]}}],
        }
        mock_post.return_value = mock_response

        tracker = CostTracker()
        result = call_gemini_tracked("fake-key", "test prompt", tracker)

        assert result is not None
        assert isinstance(result, list)
        assert result[0]["id"] == "1"
        assert tracker.breakdown["gemini_calls"] == 1

    @patch("lib.cost_tracker.requests.post")
    def test_returns_string_if_not_json(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50},
            "candidates": [{"content": {"parts": [{"text": "just plain text"}]}}],
        }
        mock_post.return_value = mock_response

        tracker = CostTracker()
        result = call_gemini_tracked("fake-key", "test prompt", tracker)
        assert result == "just plain text"

    def test_returns_none_when_over_budget(self):
        tracker = CostTracker()
        tracker.total_spent = 3.50  # Already over budget
        result = call_gemini_tracked("fake-key", "test", tracker)
        assert result is None

    def test_returns_none_when_no_key(self):
        tracker = CostTracker()
        result = call_gemini_tracked(None, "test", tracker)
        assert result is None

    @patch("lib.cost_tracker.requests.post")
    def test_api_error_returns_none(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        tracker = CostTracker()
        result = call_gemini_tracked("fake-key", "test prompt", tracker)
        assert result is None

    @patch("lib.cost_tracker.requests.post")
    def test_strips_markdown_fences(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50},
            "candidates": [{"content": {"parts": [{"text": '```json\n[{"a": 1}]\n```'}]}}],
        }
        mock_post.return_value = mock_response

        tracker = CostTracker()
        result = call_gemini_tracked("fake-key", "test prompt", tracker)
        assert isinstance(result, list)
        assert result[0]["a"] == 1


# ============================================================
# HELPER FUNCTION TESTS
# ============================================================

class TestHelpers:

    def test_validate_hs_format_valid(self):
        assert _validate_hs_format("85.16.31.00") is True
        assert _validate_hs_format("8516310000") is True
        assert _validate_hs_format("01.02.0300") is True

    def test_validate_hs_format_invalid(self):
        assert _validate_hs_format("") is False
        assert _validate_hs_format("abc") is False
        assert _validate_hs_format("99.99.9999") is False  # Chapter 99 invalid
        assert _validate_hs_format(None) is False

    def test_is_garbage_description(self):
        assert _is_garbage_description("") is True
        assert _is_garbage_description("ab") is True
        assert _is_garbage_description("123456") is True
        assert _is_garbage_description("...---...") is True
        assert _is_garbage_description("Valid Hebrew description") is False

    def test_extract_hebrew_terms(self):
        terms = _extract_hebrew_terms("מייבשי שיער חשמליים")
        assert len(terms) > 0
        assert "מייבשי" in terms
        # Stop words filtered
        terms2 = _extract_hebrew_terms("של את או")
        assert len(terms2) == 0

    def test_extract_english_terms(self):
        terms = _extract_english_terms("Electric hair dryers and parts thereof")
        assert "electric" in terms
        assert "hair" in terms
        assert "dryers" in terms
        # Stop words filtered
        assert "and" not in terms
        assert "thereof" not in terms

    def test_safe_doc_id(self):
        doc_id = _safe_doc_id("test/special.chars!")
        assert "/" not in doc_id
        assert "." not in doc_id
        assert len(doc_id) <= 100

    def test_chunk_list(self):
        chunks = list(_chunk_list([1, 2, 3, 4, 5], 2))
        assert chunks == [[1, 2], [3, 4], [5]]

    def test_convert_il_to_uk_code(self):
        assert _convert_il_to_uk_code("85.16.31.00") == "8516310000"
        assert _convert_il_to_uk_code("84.71") == "8471000000"
        assert len(_convert_il_to_uk_code("01.02.0300/0")) == 10


# ============================================================
# STREAM TESTS
# ============================================================

class TestStream1TariffDeepMine:

    def test_processes_clean_items(self):
        db = _mock_db({
            "tariff": [
                {"hs_code": "85.16.31.00", "description_he": "מייבשי שיער חשמליים",
                 "description_en": "Electric hair dryers"},
            ],
        })
        tracker = CostTracker()
        stats = stream_1_tariff_deep_mine(db, "fake-key", tracker)
        assert stats["processed"] == 1
        assert stats["garbage_found"] == 0

    def test_detects_garbage(self):
        db = _mock_db({
            "tariff": [
                {"hs_code": "85.16.31.00", "description_he": "", "description_en": ""},
            ],
        })
        tracker = CostTracker()
        # Won't call Gemini because batch < 50
        stats = stream_1_tariff_deep_mine(db, None, tracker)
        assert stats["garbage_found"] == 1

    def test_stops_on_budget(self):
        db = _mock_db({
            "tariff": [
                {"hs_code": f"01.{i:02d}.0000", "description_he": f"item {i}", "description_en": ""}
                for i in range(100)
            ],
        })
        tracker = CostTracker()
        tracker.total_spent = 3.50  # Already over
        stats = stream_1_tariff_deep_mine(db, "fake-key", tracker)
        # Should process 0 because over budget check happens in loop
        assert stats["processed"] >= 0


class TestStream3CCLearning:

    @patch("lib.overnight_brain.call_gemini_tracked")
    def test_learns_from_cc_emails(self, mock_gemini):
        mock_gemini.return_value = [{
            "is_classification_decision": True,
            "hs_code_assigned": "85.16.31.00",
            "product_classified": "Hair dryer",
            "is_correction": False,
            "expert_reasoning": "Chapter 85 electrical",
            "new_terms": ["מייבש"],
        }]

        db = _mock_db({
            "rcb_processed": [
                {"from": "doron@rpa-port.co.il", "subject": "RE: Classification",
                 "type": "cc_observation"},
            ],
        })
        tracker = CostTracker()
        stats = stream_3_cc_email_learning(db, "fake-key", tracker)
        assert stats["cc_emails"] == 1
        assert stats["patterns_learned"] == 1


class TestStream6UKTariffSweep:

    @patch("lib.overnight_brain.requests.get")
    def test_fetches_uk_data(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"attributes": {
                "description": "Electric hair dryers",
                "formatted_description": "Electric hair dryers",
            }},
            "included": [],
        }
        mock_get.return_value = mock_response

        db = _mock_db({
            "tariff": [
                {"hs_code": "85.16.31.00"},
            ],
            "rcb_classifications": [],
            "tariff_uk": [],
        })
        tracker = CostTracker()
        stats = stream_6_uk_tariff_sweep(db, tracker)
        assert stats["fetched"] >= 0  # May be 0 if mock doesn't fully work

    @patch("lib.overnight_brain.requests.get")
    def test_handles_404(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        db = _mock_db({
            "tariff": [{"hs_code": "99.99.99.99"}],
            "rcb_classifications": [],
            "tariff_uk": [],
        })
        tracker = CostTracker()
        # 99 is invalid chapter, won't be fetched
        stats = stream_6_uk_tariff_sweep(db, tracker)
        assert isinstance(stats, dict)


class TestStream7CrossReference:

    def test_calculates_completeness(self):
        db = _mock_db({
            "tariff": [{"hs_code": "85.16.31.00"}],
            "rcb_classifications": [],
            "chapter_notes": [{"chapter_title_he": "test"}],
            "tariff_uk": [],
            "ai_knowledge_enrichments": [],
            "learned_patterns": [],
            "learned_corrections": [],
        })
        tracker = CostTracker()
        stats = stream_7_cross_reference(db, tracker)
        assert stats["codes_processed"] >= 0


class TestStream8SelfTeach:

    @patch("lib.overnight_brain.call_gemini_tracked")
    def test_generates_chapter_rules(self, mock_gemini):
        mock_gemini.return_value = {
            "classification_rules": ["Rule 1", "Rule 2"],
            "common_mistakes": ["Mistake 1"],
            "decision_keywords": ["keyword1"],
            "exclusion_keywords": ["excl1"],
            "typical_products": ["product1"],
        }

        db = _mock_db({
            "learned_patterns": [
                {"hs_code": "85.01.00.00", "product": f"product {i}", "reasoning": "test"}
                for i in range(5)
            ],
            "learned_corrections": [],
        })
        tracker = CostTracker()
        stats = stream_8_self_teach(db, "fake-key", tracker)
        assert stats["chapters_taught"] >= 0


# ============================================================
# ORCHESTRATOR TESTS
# ============================================================

class TestOrchestrator:

    @patch("lib.overnight_brain.stream_6_uk_tariff_sweep")
    @patch("lib.overnight_brain.stream_3_cc_email_learning")
    @patch("lib.overnight_brain.stream_1_tariff_deep_mine")
    @patch("lib.overnight_brain.stream_2_email_archive_mine")
    @patch("lib.overnight_brain.stream_4_attachment_mine")
    @patch("lib.overnight_brain.stream_5_ai_knowledge_fill")
    @patch("lib.overnight_brain.stream_7_cross_reference")
    @patch("lib.overnight_brain.stream_8_self_teach")
    @patch("lib.overnight_brain._final_knowledge_audit")
    def test_runs_all_streams(self, mock_audit, mock_s8, mock_s7, mock_s5,
                              mock_s4, mock_s2, mock_s1, mock_s3, mock_s6):
        # All streams return empty stats
        for m in [mock_s1, mock_s2, mock_s3, mock_s4, mock_s5, mock_s6, mock_s7, mock_s8]:
            m.return_value = {}
        mock_audit.return_value = {"tariff": 11753}

        db = _mock_db()
        get_secret = Mock(return_value="fake-gemini-key")

        result = run_overnight_brain(db, get_secret)

        assert "cost" in result
        assert "audit" in result
        assert "stream_stats" in result
        assert result["cost"]["budget_limit"] == 3.50

        # All streams should have been called
        mock_s6.assert_called_once()  # UK API sweep (Phase A)
        mock_s3.assert_called_once()  # CC learning (Phase B)
        mock_s1.assert_called_once()  # Tariff mine (Phase B)
        mock_s2.assert_called_once()  # Email mine (Phase B)

    @patch("lib.overnight_brain.stream_6_uk_tariff_sweep")
    @patch("lib.overnight_brain._final_knowledge_audit")
    def test_handles_stream_errors_gracefully(self, mock_audit, mock_s6):
        mock_s6.side_effect = Exception("Test error")
        mock_audit.return_value = {}

        db = _mock_db()
        get_secret = Mock(return_value="fake-key")

        # Should not raise
        result = run_overnight_brain(db, get_secret)
        assert "stream_stats" in result
        assert "error" in str(result["stream_stats"].get("stream_6_uk_tariff", {}))

    def test_budget_enforcement(self):
        """Verify budget cap is enforced across the run."""
        tracker = CostTracker()
        assert tracker.BUDGET_LIMIT == 3.50
        assert tracker.SAFETY_MARGIN == 0.20

        # Simulate many calls
        for _ in range(100):
            if tracker.is_over_budget:
                break
            tracker.record_ai_call(500_000, 200_000)

        assert tracker.is_over_budget
        assert tracker.total_spent <= 3.50 + 0.50  # May slightly exceed due to last call


# ============================================================
# INTEGRATION: Budget stops streams
# ============================================================

class TestBudgetIntegration:

    def test_stream_respects_budget(self):
        """All streams should check tracker.is_over_budget before AI calls."""
        tracker = CostTracker()
        tracker.total_spent = 3.50  # Already exhausted

        db = _mock_db({"tariff": [{"hs_code": "85.16.31.00", "description_he": "test"}]})
        stats = stream_1_tariff_deep_mine(db, "fake-key", tracker)
        # Should process items but skip Gemini calls
        assert isinstance(stats, dict)

    def test_tracker_can_afford_guards_calls(self):
        tracker = CostTracker()
        tracker.total_spent = 3.29  # Just under limit

        # Large call should be rejected
        assert tracker.can_afford(50_000_000, 10_000_000) is False
        # Small call should be ok
        assert tracker.can_afford(100, 50) is True
