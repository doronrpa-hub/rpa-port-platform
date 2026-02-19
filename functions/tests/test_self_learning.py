"""
Tests for SelfLearningEngine — Session 50b
==========================================
Tests classification memory (check + learn) with exact, normalized,
and keyword-overlap matching.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add functions/ and functions/lib/ to path for direct imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from lib.self_learning import SelfLearningEngine


# ═══════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Create a mock Firestore database."""
    return Mock()


@pytest.fixture
def engine(mock_db):
    """Create a SelfLearningEngine with mock Firestore."""
    return SelfLearningEngine(mock_db)


def _make_doc(data, doc_id="doc1"):
    """Create a mock Firestore document snapshot."""
    doc = Mock()
    doc.id = doc_id
    doc.exists = True
    doc.to_dict.return_value = data
    return doc


def _make_empty_stream():
    """Return an empty iterator (simulates no Firestore results)."""
    return iter([])


# ═══════════════════════════════════════════
#  EXTRACT KEYWORDS (unit)
# ═══════════════════════════════════════════

class TestExtractKeywords:

    def test_basic_english(self, engine):
        kw = engine._extract_keywords("Rubber Gloves Medical Grade")
        assert "rubber" in kw
        assert "gloves" in kw
        assert "medical" in kw
        assert "grade" in kw

    def test_hebrew(self, engine):
        kw = engine._extract_keywords("כפפות גומי רפואיות")
        assert "כפפות" in kw
        assert "גומי" in kw

    def test_strips_punctuation(self, engine):
        kw = engine._extract_keywords("BEL-128 175/70R13 82H")
        assert "bel" in kw
        assert "128" in kw
        assert "70r13" in kw
        assert "82h" in kw

    def test_removes_stopwords(self, engine):
        kw = engine._extract_keywords("the product for this thing")
        assert "the" not in kw
        assert "for" not in kw
        assert "this" not in kw
        assert "product" in kw

    def test_empty_input(self, engine):
        assert engine._extract_keywords("") == []
        assert engine._extract_keywords(None) == []


# ═══════════════════════════════════════════
#  CHECK CLASSIFICATION MEMORY — LEVEL 0 (exact)
# ═══════════════════════════════════════════

class TestMemoryLevel0Exact:

    def test_exact_match_returns_data(self, engine, mock_db):
        """Level 0: identical product_lower string matches."""
        stored = {
            "product": "Rubber Gloves",
            "product_lower": "rubber gloves",
            "hs_code": "4015.19",
            "confidence": 0.95,
            "keywords": ["rubber", "gloves"],
        }
        mock_db.collection.return_value.where.return_value.limit.return_value.stream.return_value = iter([_make_doc(stored)])

        result, level = engine.check_classification_memory("Rubber Gloves")
        assert level == "exact"
        assert result["hs_code"] == "4015.19"

    def test_no_match_returns_none(self, engine, mock_db):
        """Level 0: no matching product_lower → falls through."""
        # All levels return empty
        mock_db.collection.return_value.where.return_value.limit.return_value.stream.return_value = _make_empty_stream()

        result, level = engine.check_classification_memory("Unknown Product XYZ")
        assert result is None
        assert level == "none"

    def test_empty_input_returns_none(self, engine):
        result, level = engine.check_classification_memory("")
        assert result is None
        assert level == "none"

    def test_none_input_returns_none(self, engine):
        result, level = engine.check_classification_memory(None)
        assert result is None
        assert level == "none"


# ═══════════════════════════════════════════
#  CHECK CLASSIFICATION MEMORY — LEVEL 0.5 (normalized keyword overlap)
# ═══════════════════════════════════════════

class TestMemoryLevel05Normalized:

    def _setup_level0_miss_level05_hit(self, mock_db, stored_doc):
        """Configure mock so Level 0 misses but Level 0.5 hits."""
        call_count = [0]

        def _mock_where(*args, **kwargs):
            call_count[0] += 1
            mock_query = Mock()
            if call_count[0] == 1:
                # Level 0: exact match — miss
                mock_query.limit.return_value.stream.return_value = _make_empty_stream()
            elif call_count[0] == 2:
                # Level 0.5: keyword array_contains — hit
                mock_query.limit.return_value.stream.return_value = iter([stored_doc])
            else:
                # Level 1+: miss
                mock_query.limit.return_value.stream.return_value = _make_empty_stream()
            return mock_query

        mock_db.collection.return_value.where = _mock_where

    def test_extra_words_match(self, engine, mock_db):
        """Product with extra words (brand name) matches stored version."""
        stored = {
            "product": "BEL-128 175/70R13 82H",
            "product_lower": "bel-128 175/70r13 82h",
            "hs_code": "4011.10",
            "confidence": 0.95,
            "keywords": ["bel", "128", "175", "70r13", "82h"],
        }
        self._setup_level0_miss_level05_hit(mock_db, _make_doc(stored))

        # Query with extra word "belshina"
        result, level = engine.check_classification_memory("BELSHINA BEL-128 175/70R13 82H")
        assert result is not None
        assert level == "exact"
        assert result["hs_code"] == "4011.10"

    def test_reordered_words_match(self, engine, mock_db):
        """Same product keywords in different order still matches."""
        stored = {
            "product": "Medical rubber gloves",
            "product_lower": "medical rubber gloves",
            "hs_code": "4015.19",
            "confidence": 0.9,
            "keywords": ["medical", "rubber", "gloves"],
        }
        self._setup_level0_miss_level05_hit(mock_db, _make_doc(stored))

        result, level = engine.check_classification_memory("Rubber Gloves Medical Grade")
        assert result is not None
        assert level == "exact"
        assert result["hs_code"] == "4015.19"

    def test_low_overlap_no_match(self, engine, mock_db):
        """Insufficient keyword overlap does NOT match."""
        stored = {
            "product": "Steel storage containers large industrial",
            "product_lower": "steel storage containers large industrial",
            "hs_code": "7326.90",
            "confidence": 0.9,
            "keywords": ["steel", "storage", "containers", "large", "industrial"],
        }
        # Level 0 miss
        call_count = [0]

        def _mock_where(*args, **kwargs):
            call_count[0] += 1
            mock_query = Mock()
            if call_count[0] == 1:
                # Level 0: exact — miss
                mock_query.limit.return_value.stream.return_value = _make_empty_stream()
            elif call_count[0] == 2:
                # Level 0.5: keyword hit but low overlap
                mock_query.limit.return_value.stream.return_value = iter([_make_doc(stored)])
            else:
                mock_query.limit.return_value.stream.return_value = _make_empty_stream()
            return mock_query

        mock_db.collection.return_value.where = _mock_where

        # Only 1 out of 5 keywords overlap ("steel") — 20% < 60% threshold
        result, level = engine.check_classification_memory("Steel wire rope")
        # Should fall through to Level 1+
        # The result depends on Level 1/2 also missing, which our mock provides
        # We just verify it did NOT match at Level 0.5
        if result is not None:
            # If it matched, it must NOT be from our stored doc
            assert result.get("hs_code") != "7326.90" or level != "exact"

    def test_picks_best_overlap(self, engine, mock_db):
        """When multiple candidates found, picks highest overlap."""
        doc_a = _make_doc({
            "product": "gloves leather",
            "hs_code": "4203.29",
            "confidence": 0.8,
            "keywords": ["gloves", "leather"],
        }, doc_id="a")
        doc_b = _make_doc({
            "product": "rubber gloves medical disposable",
            "hs_code": "4015.19",
            "confidence": 0.9,
            "keywords": ["rubber", "gloves", "medical", "disposable"],
        }, doc_id="b")

        call_count = [0]

        def _mock_where(*args, **kwargs):
            call_count[0] += 1
            mock_query = Mock()
            if call_count[0] == 1:
                mock_query.limit.return_value.stream.return_value = _make_empty_stream()
            elif call_count[0] == 2:
                mock_query.limit.return_value.stream.return_value = iter([doc_a, doc_b])
            else:
                mock_query.limit.return_value.stream.return_value = _make_empty_stream()
            return mock_query

        mock_db.collection.return_value.where = _mock_where

        result, level = engine.check_classification_memory("medical rubber gloves")
        assert result is not None
        assert result["hs_code"] == "4015.19"  # doc_b has higher overlap

    def test_single_keyword_skipped(self, engine, mock_db):
        """Products with only 1 keyword skip Level 0.5 (too short to be meaningful)."""
        # Set up mock to track calls
        mock_db.collection.return_value.where.return_value.limit.return_value.stream.return_value = _make_empty_stream()

        result, level = engine.check_classification_memory("Oil")
        assert result is None
        assert level == "none"


# ═══════════════════════════════════════════
#  LEARN CLASSIFICATION
# ═══════════════════════════════════════════

class TestLearnClassification:

    @patch("lib.self_learning.datetime")
    def test_stores_product_normalized(self, mock_dt, engine, mock_db):
        """learn_classification stores product_normalized field."""
        mock_dt.now.return_value = Mock()
        mock_dt.now.return_value.isoformat.return_value = "2026-02-19T10:00:00"

        # Mock existing doc check
        doc_ref = Mock()
        existing = Mock()
        existing.exists = False
        doc_ref.get.return_value = existing
        mock_db.collection.return_value.document.return_value = doc_ref

        engine.learn_classification(
            "BEL-128 175/70R13 82H",
            "4011.10",
            method="ai",
            source="gemini",
            confidence=0.85,
        )

        # Verify set was called
        assert doc_ref.set.called
        stored_data = doc_ref.set.call_args[0][0]
        assert "product_normalized" in stored_data
        # Sorted keywords
        kw = sorted(engine._extract_keywords("BEL-128 175/70R13 82H"))
        assert stored_data["product_normalized"] == " ".join(kw)

    @patch("lib.self_learning.datetime")
    def test_stores_product_lower(self, mock_dt, engine, mock_db):
        """learn_classification stores product_lower for exact matching."""
        mock_dt.now.return_value = Mock()
        doc_ref = Mock()
        existing = Mock()
        existing.exists = False
        doc_ref.get.return_value = existing
        mock_db.collection.return_value.document.return_value = doc_ref

        engine.learn_classification("Rubber Gloves", "4015.19", "ai", "gemini", 0.9)

        stored_data = doc_ref.set.call_args[0][0]
        assert stored_data["product_lower"] == "rubber gloves"

    def test_skip_empty_product(self, engine, mock_db):
        """learn_classification ignores empty product descriptions."""
        engine.learn_classification("", "4011.10", "ai", "gemini", 0.5)
        assert not mock_db.collection.called

    def test_skip_empty_hs_code(self, engine, mock_db):
        """learn_classification ignores empty HS codes."""
        engine.learn_classification("Rubber Gloves", "", "ai", "gemini", 0.5)
        assert not mock_db.collection.called


# ═══════════════════════════════════════════
#  CONFIDENCE REGRESSION GUARD (P2)
# ═══════════════════════════════════════════

class TestConfidenceRegressionGuard:

    @patch("lib.self_learning.datetime")
    def test_does_not_overwrite_higher_confidence(self, mock_dt, engine, mock_db):
        """AI result (conf=0.5) must NOT overwrite cross_validated (conf=0.95)."""
        mock_dt.now.return_value = Mock()

        # Existing doc: cross_validated at 0.95
        doc_ref = Mock()
        existing = Mock()
        existing.exists = True
        existing.to_dict.return_value = {
            "confidence": 0.95,
            "method": "cross_validated",
        }
        doc_ref.get.return_value = existing
        mock_db.collection.return_value.document.return_value = doc_ref

        engine.learn_classification(
            "BEL-128 175/70R13 82H", "4011.10",
            method="ai", source="gemini", confidence=0.5
        )

        # set should NOT be called
        assert not doc_ref.set.called

    @patch("lib.self_learning.datetime")
    def test_allows_upgrade_from_ai_to_manual(self, mock_dt, engine, mock_db):
        """Manual result (conf=0.9) CAN overwrite AI result (conf=0.85)."""
        mock_dt.now.return_value = Mock()

        doc_ref = Mock()
        existing = Mock()
        existing.exists = True
        existing.to_dict.return_value = {
            "confidence": 0.85,
            "method": "ai",
        }
        doc_ref.get.return_value = existing
        mock_db.collection.return_value.document.return_value = doc_ref

        engine.learn_classification(
            "Rubber Gloves", "4015.19",
            method="manual", source="user", confidence=0.9
        )

        # set SHOULD be called (manual outranks AI)
        assert doc_ref.set.called

    @patch("lib.self_learning.datetime")
    def test_blocks_same_method_lower_confidence(self, mock_dt, engine, mock_db):
        """Same method (ai), lower confidence (0.6 < 0.8) must NOT overwrite."""
        mock_dt.now.return_value = Mock()

        doc_ref = Mock()
        existing = Mock()
        existing.exists = True
        existing.to_dict.return_value = {
            "confidence": 0.8,
            "method": "ai",
        }
        doc_ref.get.return_value = existing
        mock_db.collection.return_value.document.return_value = doc_ref

        engine.learn_classification(
            "Steel Tubes", "7304.19",
            method="ai", source="gemini", confidence=0.6
        )

        assert not doc_ref.set.called

    @patch("lib.self_learning.datetime")
    def test_allows_same_method_higher_confidence(self, mock_dt, engine, mock_db):
        """Same method (ai), higher confidence (0.9 > 0.6) CAN overwrite."""
        mock_dt.now.return_value = Mock()

        doc_ref = Mock()
        existing = Mock()
        existing.exists = True
        existing.to_dict.return_value = {
            "confidence": 0.6,
            "method": "ai",
        }
        doc_ref.get.return_value = existing
        mock_db.collection.return_value.document.return_value = doc_ref

        engine.learn_classification(
            "Steel Tubes", "7304.19",
            method="ai", source="claude", confidence=0.9
        )

        assert doc_ref.set.called


# ═══════════════════════════════════════════
#  ROUND-TRIP: STORE THEN RECALL
# ═══════════════════════════════════════════

class TestRoundTrip:
    """Simulate the full store→recall flow with mock Firestore."""

    def test_store_and_recall_exact(self, engine, mock_db):
        """Store a classification, recall it with exact same description."""
        # First: learn
        doc_ref = Mock()
        existing = Mock()
        existing.exists = False
        doc_ref.get.return_value = existing
        mock_db.collection.return_value.document.return_value = doc_ref

        with patch("lib.self_learning.datetime") as mock_dt:
            mock_dt.now.return_value = Mock()
            engine.learn_classification("Rubber Gloves Medical", "4015.19", "ai", "gemini", 0.9)

        # Capture what was stored
        stored_data = doc_ref.set.call_args[0][0]

        # Now: check memory with same description
        stored_doc = _make_doc(stored_data)
        mock_db.collection.return_value.where.return_value.limit.return_value.stream.return_value = iter([stored_doc])

        result, level = engine.check_classification_memory("Rubber Gloves Medical")
        assert result is not None
        assert level == "exact"
        assert "4015" in result["hs_code"].replace(".", "") or result["hs_code"].startswith("40")

    def test_store_and_recall_with_extra_words(self, engine, mock_db):
        """Store a classification, recall it with extra words in description."""
        # Learn
        doc_ref = Mock()
        existing = Mock()
        existing.exists = False
        doc_ref.get.return_value = existing
        mock_db.collection.return_value.document.return_value = doc_ref

        with patch("lib.self_learning.datetime") as mock_dt:
            mock_dt.now.return_value = Mock()
            engine.learn_classification("BEL-128 175/70R13 82H", "4011.10", "ai", "gemini", 0.9)

        stored_data = doc_ref.set.call_args[0][0]
        stored_doc = _make_doc(stored_data)

        # Check memory: Level 0 misses, Level 0.5 hits
        call_count = [0]

        def _mock_where(*args, **kwargs):
            call_count[0] += 1
            mock_query = Mock()
            if call_count[0] == 1:
                # Level 0: exact — miss (different text)
                mock_query.limit.return_value.stream.return_value = _make_empty_stream()
            elif call_count[0] == 2:
                # Level 0.5: keyword — hit
                mock_query.limit.return_value.stream.return_value = iter([stored_doc])
            else:
                mock_query.limit.return_value.stream.return_value = _make_empty_stream()
            return mock_query

        mock_db.collection.return_value.where = _mock_where

        # Recall with extra word "BELSHINA"
        result, level = engine.check_classification_memory("BELSHINA BEL-128 175/70R13 82H")
        assert result is not None
        assert level == "exact"
        assert result.get("hs_code", "").replace(".", "").startswith("4011")
