"""
Unit Tests for justification_engine — Phase B enhancements
Tests the pipeline-aware search helpers and enhanced chain steps.
Run: pytest tests/test_justification_engine.py -v
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, patch, MagicMock

from lib.justification_engine import (
    build_justification_chain,
    _search_pipeline_collection,
    _search_supporting_sources,
    _search_foreign_tariffs,
    save_knowledge_gaps,
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
    return doc


def _mock_db_with_collections(collection_data):
    """
    Create a mock Firestore DB.
    collection_data: dict mapping "collection_name" -> list of doc dicts
    """
    db = Mock()

    def mock_collection(name):
        col = Mock()
        docs = collection_data.get(name, [])
        mock_docs = [_mock_doc(d, f"{name}_{i}") for i, d in enumerate(docs)]

        def mock_where(*args, **kwargs):
            query = Mock()
            query.where = mock_where

            def mock_limit(n):
                limited = Mock()

                def mock_stream():
                    return iter(mock_docs[:n])
                limited.stream = mock_stream
                limited.limit = mock_limit
                return limited

            query.limit = mock_limit
            return query

        col.where = mock_where

        # For document() calls
        def mock_document(doc_id):
            doc_ref = Mock()
            if docs:
                doc_ref.get.return_value = _mock_doc(docs[0], doc_id)
            else:
                empty = Mock()
                empty.exists = False
                doc_ref.get.return_value = empty
            doc_ref.set = Mock()
            doc_ref.update = Mock()
            return doc_ref
        col.document = mock_document
        col.add = Mock()
        col.limit = lambda n: Mock(stream=lambda: iter(mock_docs[:n]))

        return col

    db.collection = mock_collection
    return db


# ============================================================
# _search_pipeline_collection
# ============================================================

class TestSearchPipelineCollection:

    def test_finds_by_hs_code(self):
        db = _mock_db_with_collections({
            "classification_directives": [
                {"hs_code": "85.16.31", "title": "Hair dryers directive"}
            ]
        })
        result = _search_pipeline_collection(
            db, "classification_directives", "85.16.31", "85163100", "85", "8516"
        )
        assert len(result) == 1

    def test_empty_collection_returns_empty(self):
        db = _mock_db_with_collections({})
        result = _search_pipeline_collection(
            db, "classification_directives", "85.16.31", "85163100", "85", "8516"
        )
        assert result == []

    def test_cascades_through_queries(self):
        """When hs_code match fails, should try chapter."""
        db = Mock()
        call_count = {"n": 0}

        def mock_collection(name):
            col = Mock()

            def mock_where(field, op, val):
                query = Mock()
                call_count["n"] += 1

                def mock_limit(n):
                    limited = Mock()
                    # Return empty for first queries, docs for chapter match
                    if field == "chapter" and val == 85:
                        limited.stream = lambda: iter([_mock_doc({"title": "Ch85"})])
                    else:
                        limited.stream = lambda: iter([])
                    limited.limit = mock_limit
                    return limited

                query.limit = mock_limit
                return query

            col.where = mock_where
            return col

        db.collection = mock_collection

        result = _search_pipeline_collection(
            db, "classification_directives", "85.16.31", "85163100", "85", "8516"
        )
        assert len(result) == 1
        assert call_count["n"] >= 3  # Tried multiple query paths


# ============================================================
# _search_supporting_sources
# ============================================================

class TestSearchSupportingSources:

    def test_finds_customs_decision(self):
        db = _mock_db_with_collections({
            "customs_decisions": [
                {"decision_id": "CD-001", "reasoning_summary": "Product is classified..."}
            ],
            "court_precedents": [],
        })
        result = _search_supporting_sources(db, "85.16.31", "85163100", "85", "8516")
        assert len(result) >= 1
        assert "customs_decisions" in result[0]["source"]

    def test_finds_court_precedent(self):
        db = _mock_db_with_collections({
            "customs_decisions": [],
            "court_precedents": [
                {"case_id": "CASE-001", "ruling_summary": "Court ruled..."}
            ],
        })
        result = _search_supporting_sources(db, "85.16.31", "85163100", "85", "8516")
        assert len(result) >= 1
        assert "court_precedents" in result[0]["source"]

    def test_empty_when_nothing_found(self):
        db = _mock_db_with_collections({
            "customs_decisions": [],
            "court_precedents": [],
        })
        result = _search_supporting_sources(db, "85.16.31", "85163100", "85", "8516")
        assert result == []


# ============================================================
# _search_foreign_tariffs
# ============================================================

class TestSearchForeignTariffs:

    def test_finds_uk_tariff(self):
        db = _mock_db_with_collections({
            "tariff_uk": [{"uk_code": "8516310000", "description": "Hair dryers", "heading": "85.16"}],
            "tariff_usa": [],
            "tariff_eu": [],
            "cbp_rulings": [],
            "bti_decisions": [],
        })
        result = _search_foreign_tariffs(db, "85163100", "8516")
        assert len(result) >= 1
        assert "UK" in result[0]["source"]

    def test_empty_when_no_foreign_data(self):
        db = _mock_db_with_collections({
            "tariff_uk": [],
            "tariff_usa": [],
            "tariff_eu": [],
            "cbp_rulings": [],
            "bti_decisions": [],
        })
        result = _search_foreign_tariffs(db, "85163100", "8516")
        assert result == []

    def test_handles_missing_collections(self):
        """Should not crash if foreign tariff collections don't exist."""
        db = Mock()
        db.collection.side_effect = Exception("Collection not found")
        result = _search_foreign_tariffs(db, "85163100", "8516")
        assert result == []


# ============================================================
# build_justification_chain (integration)
# ============================================================

class TestBuildJustificationChain:

    def _make_db(self):
        """Create a DB with chapter notes and tariff for basic chain."""
        return _mock_db_with_collections({
            "chapter_notes": [
                {
                    "preamble": "This chapter covers electrical machines...",
                    "chapter_title_he": "מכונות חשמליות",
                    "notes": ["Note 1: items of heading 85.16", "Note 2: general"],
                    "exclusions": [],
                }
            ],
            "tariff": [
                {
                    "heading": "8516",
                    "hs_code": "85.16.31",
                    "description_he": "מייבשי שיער",
                    "description_en": "Hair dryers",
                }
            ],
            "classification_directives": [
                {"directive_id": "CD-2024-005", "title": "Hair dryers classification", "summary": "Covers 85.16.31"}
            ],
            "pre_rulings": [],
            "customs_decisions": [],
            "court_precedents": [],
            "tariff_uk": [],
            "tariff_usa": [],
            "tariff_eu": [],
            "cbp_rulings": [],
            "bti_decisions": [],
        })

    def test_chain_has_at_least_5_steps(self):
        db = self._make_db()
        result = build_justification_chain(db, "85.16.31", "Hair dryer")
        # Should have steps: chapter, heading, subheading, notes, directives
        assert len(result["chain"]) >= 4

    def test_directive_step_includes_source_text(self):
        db = self._make_db()
        result = build_justification_chain(db, "85.16.31", "Hair dryer")
        directive_steps = [s for s in result["chain"] if s["source_type"] == "classification_directive"]
        if directive_steps:
            assert directive_steps[0].get("source_text")
            assert directive_steps[0].get("source_ref")

    def test_result_has_required_fields(self):
        db = self._make_db()
        result = build_justification_chain(db, "85.16.31", "Hair dryer")
        assert "chain" in result
        assert "gaps" in result
        assert "legal_strength" in result
        assert "coverage_pct" in result
        assert "confidence_boost" in result

    def test_coverage_is_percentage(self):
        db = self._make_db()
        result = build_justification_chain(db, "85.16.31", "Hair dryer")
        assert 0 <= result["coverage_pct"] <= 100

    def test_empty_db_returns_weak(self):
        db = _mock_db_with_collections({})
        result = build_justification_chain(db, "99.99.99", "Unknown product")
        assert result["legal_strength"] in ("weak", "moderate")


# ============================================================
# save_knowledge_gaps
# ============================================================

class TestSaveKnowledgeGaps:

    def test_saves_gaps_to_firestore(self):
        db = Mock()
        doc_ref = Mock()
        doc_ref.get.return_value = Mock(exists=False)
        doc_ref.set = Mock()
        db.collection.return_value.document.return_value = doc_ref

        gaps = [
            {"type": "missing_directive", "chapter": "85", "description": "No directive", "priority": "medium"},
        ]
        save_knowledge_gaps(db, gaps, hs_code="85.16.31")
        doc_ref.set.assert_called_once()

    def test_empty_gaps_does_nothing(self):
        db = Mock()
        save_knowledge_gaps(db, [], hs_code="85.16.31")
        db.collection.assert_not_called()

    def test_increments_seen_count_for_existing(self):
        db = Mock()
        existing_doc = Mock(exists=True)
        existing_doc.to_dict.return_value = {"seen_count": 3}
        doc_ref = Mock()
        doc_ref.get.return_value = existing_doc
        doc_ref.update = Mock()
        db.collection.return_value.document.return_value = doc_ref

        gaps = [{"type": "missing_directive", "chapter": "85", "description": "No directive"}]
        save_knowledge_gaps(db, gaps)
        doc_ref.update.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
