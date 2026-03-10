"""
Tests for knowledge_enrichment.py — Tier 2 heading enrichment.
Guard test runs FIRST — if it fails, nothing else matters.
"""

import pytest
import time
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════
#  TEST 1: PROTECTED_COLLECTIONS GUARD (must pass first)
# ═══════════════════════════════════════════════════════════

class TestProtectedCollectionsGuard:
    """If these fail, the module is unsafe. Stop immediately."""

    def test_write_to_tariff_raises(self):
        """Attempt to write to 'tariff' must raise ProtectedCollectionError."""
        from lib.knowledge_enrichment import _safe_write, ProtectedCollectionError
        db = MagicMock()
        with pytest.raises(ProtectedCollectionError, match="tariff"):
            _safe_write(db, "tariff", "test_doc", {"foo": "bar"})
        # Firestore must NOT have been called
        db.collection.assert_not_called()

    def test_write_to_chapter_notes_raises(self):
        from lib.knowledge_enrichment import _safe_write, ProtectedCollectionError
        db = MagicMock()
        with pytest.raises(ProtectedCollectionError, match="chapter_notes"):
            _safe_write(db, "chapter_notes", "ch01", {"data": 1})
        db.collection.assert_not_called()

    def test_write_to_free_import_order_raises(self):
        from lib.knowledge_enrichment import _safe_write, ProtectedCollectionError
        db = MagicMock()
        with pytest.raises(ProtectedCollectionError, match="free_import_order"):
            _safe_write(db, "free_import_order", "8413", {})
        db.collection.assert_not_called()

    def test_write_to_learned_classifications_raises(self):
        from lib.knowledge_enrichment import _safe_write, ProtectedCollectionError
        db = MagicMock()
        with pytest.raises(ProtectedCollectionError, match="learned_classifications"):
            _safe_write(db, "learned_classifications", "x", {})
        db.collection.assert_not_called()

    def test_write_to_framework_order_raises(self):
        from lib.knowledge_enrichment import _safe_write, ProtectedCollectionError
        db = MagicMock()
        with pytest.raises(ProtectedCollectionError, match="framework_order"):
            _safe_write(db, "framework_order", "x", {})
        db.collection.assert_not_called()

    def test_write_to_discount_codes_raises(self):
        from lib.knowledge_enrichment import _safe_write, ProtectedCollectionError
        db = MagicMock()
        with pytest.raises(ProtectedCollectionError, match="discount_codes"):
            _safe_write(db, "discount_codes", "x", {})
        db.collection.assert_not_called()

    def test_all_protected_collections_guarded(self):
        """Every member of PROTECTED_COLLECTIONS must be blocked."""
        from lib.knowledge_enrichment import _safe_write, ProtectedCollectionError, PROTECTED_COLLECTIONS
        db = MagicMock()
        for coll in PROTECTED_COLLECTIONS:
            with pytest.raises(ProtectedCollectionError):
                _safe_write(db, coll, "test", {"x": 1})
            db.collection.assert_not_called()

    def test_write_to_unknown_collection_raises(self):
        """Writing to a collection NOT in the allowed set must also raise."""
        from lib.knowledge_enrichment import _safe_write, ProtectedCollectionError
        db = MagicMock()
        with pytest.raises(ProtectedCollectionError, match="random_collection"):
            _safe_write(db, "random_collection", "doc1", {"x": 1})
        db.collection.assert_not_called()

    def test_write_to_heading_knowledge_allowed(self):
        """Writing to heading_knowledge must succeed."""
        from lib.knowledge_enrichment import _safe_write
        db = MagicMock()
        _safe_write(db, "heading_knowledge", "8413", {"data": 1})
        db.collection.assert_called_once_with("heading_knowledge")

    def test_write_to_enrichment_log_allowed(self):
        from lib.knowledge_enrichment import _safe_write
        db = MagicMock()
        _safe_write(db, "enrichment_log", "run_001", {"data": 1})
        db.collection.assert_called_once_with("enrichment_log")

    def test_write_to_enrichment_state_allowed(self):
        from lib.knowledge_enrichment import _safe_write
        db = MagicMock()
        _safe_write(db, "enrichment_state", "cursor", {"last_hs4": "0101"})
        db.collection.assert_called_once_with("enrichment_state")

    def test_protected_set_is_frozenset(self):
        """PROTECTED_COLLECTIONS must be immutable."""
        from lib.knowledge_enrichment import PROTECTED_COLLECTIONS
        assert isinstance(PROTECTED_COLLECTIONS, frozenset)

    def test_guard_runs_before_firestore_call(self):
        """If guard blocks, Firestore .collection() must never be invoked."""
        from lib.knowledge_enrichment import _safe_write, ProtectedCollectionError
        db = MagicMock()
        try:
            _safe_write(db, "tariff", "doc", {"evil": True})
        except ProtectedCollectionError:
            pass
        db.collection.assert_not_called()
        db.collection.return_value.document.assert_not_called()


# ═══════════════════════════════════════════════════════════
#  TEST 2: CURSOR MECHANISM
# ═══════════════════════════════════════════════════════════

class TestCursorMechanism:

    def _mock_db_with_state(self, last_hs4="", total_processed=0):
        """Create a mock DB with enrichment_state cursor."""
        db = MagicMock()
        # enrichment_state/cursor doc
        state_doc = MagicMock()
        state_doc.exists = True
        state_doc.to_dict.return_value = {
            "last_hs4": last_hs4,
            "total_processed": total_processed,
            "total_errors": 0,
            "last_run": None,
        }
        db.collection.return_value.document.return_value.get.return_value = state_doc
        return db

    def test_loads_state_on_start(self):
        from lib.knowledge_enrichment import _load_state
        db = self._mock_db_with_state(last_hs4="4011", total_processed=100)
        state = _load_state(db)
        assert state["last_hs4"] == "4011"
        assert state["total_processed"] == 100

    def test_default_state_when_no_doc(self):
        from lib.knowledge_enrichment import _load_state
        db = MagicMock()
        no_doc = MagicMock()
        no_doc.exists = False
        db.collection.return_value.document.return_value.get.return_value = no_doc
        state = _load_state(db)
        assert state["last_hs4"] == ""
        assert state["total_processed"] == 0

    def test_save_state_writes_tier2_meta(self):
        from lib.knowledge_enrichment import _save_state
        db = MagicMock()
        _save_state(db, {"last_hs4": "8413", "total_processed": 50, "total_errors": 2, "last_run": None})
        # Verify the write went to enrichment_state
        db.collection.assert_called_with("enrichment_state")
        call_args = db.collection.return_value.document.return_value.set.call_args
        written_data = call_args[0][0]
        assert written_data["data_tier"] == "enrichment"
        assert written_data["is_authoritative"] is False
        assert written_data["last_hs4"] == "8413"


# ═══════════════════════════════════════════════════════════
#  TEST 3: IDEMPOTENCY
# ═══════════════════════════════════════════════════════════

class TestIdempotency:

    def test_skips_already_enriched_heading(self):
        """If heading_knowledge/{hs4} exists, heading must be skipped."""
        from lib.knowledge_enrichment import _get_unenriched_headings

        db = MagicMock()

        # Tariff returns 3 docs: 0401, 0402, 0403
        tariff_docs = []
        for code in ["0401000000", "0402000000", "0403000000"]:
            d = MagicMock()
            d.to_dict.return_value = {"hs_code": code, "description": "test"}
            tariff_docs.append(d)

        # Wire up the query chain
        query = MagicMock()
        query.stream.return_value = iter(tariff_docs)
        db.collection.return_value.order_by.return_value = query
        query.where.return_value = query
        query.limit.return_value = query

        # heading_knowledge: 0401 exists, 0402 doesn't, 0403 doesn't
        def mock_hk_get(hs4):
            mock_doc = MagicMock()
            if hs4 == "0401":
                mock_doc = MagicMock()
                mock_doc.exists = True
            else:
                mock_doc = MagicMock()
                mock_doc.exists = False
            return mock_doc

        # We need to handle both collection("tariff") and collection("heading_knowledge")
        original_collection = db.collection

        def route_collection(name):
            if name == "heading_knowledge":
                coll = MagicMock()
                coll.document.side_effect = lambda doc_id: MagicMock(
                    get=MagicMock(return_value=mock_hk_get(doc_id))
                )
                return coll
            return original_collection(name)

        db.collection = MagicMock(side_effect=route_collection)

        # Re-wire tariff query since we replaced db.collection
        tariff_coll = MagicMock()
        tariff_query = MagicMock()
        tariff_query.stream.return_value = iter(tariff_docs)
        tariff_query.where.return_value = tariff_query
        tariff_query.limit.return_value = tariff_query
        tariff_coll.order_by.return_value = tariff_query

        def route_v2(name):
            if name == "heading_knowledge":
                coll = MagicMock()
                coll.document.side_effect = lambda doc_id: MagicMock(
                    get=MagicMock(return_value=mock_hk_get(doc_id))
                )
                return coll
            if name == "tariff":
                return tariff_coll
            return MagicMock()

        db.collection = MagicMock(side_effect=route_v2)

        result = _get_unenriched_headings(db, "", 10)
        # 0401 should be skipped (already exists), 0402 and 0403 should be returned
        hs4s = [h["hs4"] for h in result]
        assert "0401" not in hs4s
        assert "0402" in hs4s
        assert "0403" in hs4s


# ═══════════════════════════════════════════════════════════
#  TEST 4: XML PARSER
# ═══════════════════════════════════════════════════════════

class TestXmlParser:

    def test_parse_heading_8413_from_real_xml(self):
        """Parse heading 84.13 from the actual CustomsItem.xml on disk."""
        import os
        from lib.knowledge_enrichment import get_heading_structure, _reset_xml_caches

        xml_path = os.path.join(os.path.dirname(__file__), "..", "lib", "data", "CustomsItem.xml")
        if not os.path.exists(xml_path):
            pytest.skip("CustomsItem.xml not on disk")

        _reset_xml_caches()  # force fresh load
        structure = get_heading_structure("8413")

        assert len(structure) > 0, "Heading 8413 must have subheadings"
        # All entries must start with 8413
        for s in structure:
            assert s["hs10"].startswith("8413"), f"Unexpected hs10: {s['hs10']}"
        # Must have formatted field
        assert all("formatted" in s for s in structure)
        # At least one should have a description
        has_desc = any(s.get("description_he") or s.get("description_en") for s in structure)
        assert has_desc, "At least one subheading should have a description"

        _reset_xml_caches()

    def test_heading_structure_returns_sorted(self):
        """Results must be sorted by hs10."""
        import os
        from lib.knowledge_enrichment import get_heading_structure, _reset_xml_caches

        xml_path = os.path.join(os.path.dirname(__file__), "..", "lib", "data", "CustomsItem.xml")
        if not os.path.exists(xml_path):
            pytest.skip("CustomsItem.xml not on disk")

        _reset_xml_caches()
        structure = get_heading_structure("0101")
        codes = [s["hs10"] for s in structure]
        assert codes == sorted(codes)
        _reset_xml_caches()

    def test_nonexistent_heading_returns_empty(self):
        """A heading with no items in XML returns empty list."""
        import os
        from lib.knowledge_enrichment import get_heading_structure, _reset_xml_caches

        xml_path = os.path.join(os.path.dirname(__file__), "..", "lib", "data", "CustomsItem.xml")
        if not os.path.exists(xml_path):
            pytest.skip("CustomsItem.xml not on disk")

        _reset_xml_caches()
        structure = get_heading_structure("0000")
        assert structure == []
        _reset_xml_caches()


# ═══════════════════════════════════════════════════════════
#  TEST 5: GRACEFUL FAILURE
# ═══════════════════════════════════════════════════════════

class TestGracefulFailure:

    @patch("lib.knowledge_enrichment._fetch_wikipedia", side_effect=Exception("Network down"))
    @patch("lib.knowledge_enrichment.get_heading_structure", return_value=[])
    @patch("lib.knowledge_enrichment.time.sleep")  # skip delays in tests
    def test_wikipedia_failure_does_not_crash_run(self, mock_sleep, mock_struct, mock_wiki):
        """If Wikipedia raises, the heading should fail but not crash the batch."""
        from lib.knowledge_enrichment import _enrich_one

        db = MagicMock()
        heading = {"hs4": "8413", "description_en": "Pumps", "description_he": "משאבות"}

        ok, err = _enrich_one(db, heading)
        assert ok is False
        assert err is not None
        assert "8413" in err

    @patch("lib.knowledge_enrichment._fetch_wikipedia", return_value="")
    @patch("lib.knowledge_enrichment._fetch_taric_notes", return_value="")
    @patch("lib.knowledge_enrichment.get_heading_structure", return_value=[])
    @patch("lib.knowledge_enrichment.time.sleep")
    def test_empty_results_still_writes_doc(self, mock_sleep, mock_struct, mock_taric, mock_wiki):
        """Even with empty external data, a doc should be written."""
        from lib.knowledge_enrichment import _enrich_one

        db = MagicMock()
        heading = {"hs4": "9999", "description_en": "", "description_he": ""}

        ok, err = _enrich_one(db, heading)
        assert ok is True
        assert err is None
        # Verify write happened to heading_knowledge
        db.collection.assert_called_with("heading_knowledge")
        call_args = db.collection.return_value.document.return_value.set.call_args
        written = call_args[0][0]
        assert written["data_tier"] == "enrichment"
        assert written["is_authoritative"] is False

    @patch("lib.knowledge_enrichment._fetch_wikipedia", return_value="Pumps are devices that move fluids.")
    @patch("lib.knowledge_enrichment._fetch_taric_notes", return_value="TARIC notes for pumps")
    @patch("lib.knowledge_enrichment.get_heading_structure", return_value=[
        {"hs10": "8413110000", "description_he": "משאבות דלק", "description_en": "Fuel pumps", "formatted": "84.13.110000/X"}
    ])
    @patch("lib.knowledge_enrichment.time.sleep")
    def test_successful_enrichment_writes_complete_doc(self, mock_sleep, mock_struct, mock_taric, mock_wiki):
        """A successful enrichment writes all expected fields."""
        from lib.knowledge_enrichment import _enrich_one

        db = MagicMock()
        heading = {"hs4": "8413", "description_en": "Pumps", "description_he": "משאבות"}

        ok, err = _enrich_one(db, heading)
        assert ok is True

        call_args = db.collection.return_value.document.return_value.set.call_args
        written = call_args[0][0]
        assert written["hs4"] == "84.13"
        assert written["hs4_raw"] == "8413"
        assert written["wiki_en"] == "Pumps are devices that move fluids."
        assert written["taric_notes"] == "TARIC notes for pumps"
        assert len(written["official_structure"]) == 1
        assert written["data_tier"] == "enrichment"
        assert written["is_authoritative"] is False
        assert "fetched_at" in written
        assert "source" in written


# ═══════════════════════════════════════════════════════════
#  TEST 6: TIER 2 METADATA
# ═══════════════════════════════════════════════════════════

class TestTier2Metadata:

    def test_tier2_meta_fields(self):
        from lib.knowledge_enrichment import _tier2_meta
        meta = _tier2_meta("test_source")
        assert meta["data_tier"] == "enrichment"
        assert meta["is_authoritative"] is False
        assert meta["source"] == "test_source"
        assert "fetched_at" in meta

    def test_no_normalize_hs_code_defined_locally(self):
        """Module must import normalize_hs_code from librarian, not define its own."""
        import inspect
        import lib.knowledge_enrichment as ke
        # The function should be imported, not defined in this module
        source_file = inspect.getfile(ke.normalize_hs_code)
        assert "librarian" in source_file, f"normalize_hs_code comes from {source_file}, expected librarian"

    def test_no_get_israeli_hs_format_defined_locally(self):
        import inspect
        import lib.knowledge_enrichment as ke
        source_file = inspect.getfile(ke.get_israeli_hs_format)
        assert "librarian" in source_file


# ═══════════════════════════════════════════════════════════
#  TEST 7: SYNONYM EXTRACTION
# ═══════════════════════════════════════════════════════════

class TestSynonymExtraction:

    def test_extracts_english_nouns(self):
        from lib.knowledge_enrichment import _extract_synonyms
        result = _extract_synonyms("Pumps are devices that move Fluids through pipes.", "")
        assert "pumps" in result
        assert "fluids" in result

    def test_extracts_hebrew_words(self):
        from lib.knowledge_enrichment import _extract_synonyms
        result = _extract_synonyms("", "משאבות הן מכשירים להעברת נוזלים")
        assert "משאבות" in result
        assert "נוזלים" in result

    def test_filters_stop_words(self):
        from lib.knowledge_enrichment import _extract_synonyms
        result = _extract_synonyms("The First and Most Common devices are Used between Many systems.", "")
        # These should be filtered out
        assert "the" not in result
        assert "and" not in result
        assert "most" not in result

    def test_caps_at_50(self):
        from lib.knowledge_enrichment import _extract_synonyms
        long_text = " ".join([f"Word{i}" for i in range(200)])
        result = _extract_synonyms(long_text, "")
        assert len(result) <= 50
