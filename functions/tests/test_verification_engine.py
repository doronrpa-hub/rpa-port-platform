"""
Tests for verification_engine.py — Block E: Phases 4-6 + Proactive Flagging

Unit tests with mocked Firestore (no live calls).
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add functions dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.verification_engine import (
    _extract_keywords,
    _score_bilingual,
    _run_phase4,
    _run_phase5,
    _generate_flags,
    run_verification_engine,
    build_verification_flags_html,
    _clean_hs,
    _chapter_from_hs,
    _reset_caches,
)


class TestExtractKeywords(unittest.TestCase):
    """Test bilingual keyword extraction with Hebrew prefix stripping."""

    def test_english_keywords(self):
        kw = _extract_keywords("Steel storage box for industrial use")
        assert "steel" in kw
        assert "storage" in kw
        assert "box" in kw
        assert "industrial" in kw
        # Stop words excluded
        assert "for" not in kw

    def test_hebrew_keywords(self):
        kw = _extract_keywords("קופסת אחסון מפלדה לשימוש תעשייתי")
        assert len(kw) > 0
        # Hebrew prefix stripping: מפלדה -> פלדה
        assert "פלדה" in kw or "מפלדה" in kw

    def test_hebrew_prefix_stripping(self):
        kw = _extract_keywords("מפלדה בגומי לעץ הברזל וכותנה שמשי כזכוכית")
        # Should contain both original and stripped variants
        assert "פלדה" in kw  # stripped from מפלדה
        assert "גומי" in kw  # stripped from בגומי

    def test_empty_input(self):
        assert _extract_keywords("") == []
        assert _extract_keywords(None) == []

    def test_short_words_excluded(self):
        kw = _extract_keywords("a b cd")
        assert "a" not in kw
        assert "b" not in kw

    def test_deduplication(self):
        kw = _extract_keywords("steel steel steel box box")
        assert kw.count("steel") == 1
        assert kw.count("box") == 1

    def test_limit(self):
        text = " ".join([f"word{i}" for i in range(50)])
        kw = _extract_keywords(text, limit=5)
        assert len(kw) <= 5


class TestScoreBilingual(unittest.TestCase):
    """Test bilingual keyword overlap scoring."""

    def test_perfect_overlap(self):
        score = _score_bilingual("steel storage box", "steel storage box container")
        assert score > 0.5

    def test_no_overlap(self):
        score = _score_bilingual("rubber gloves medical", "wooden furniture table")
        assert score < 0.1

    def test_partial_overlap(self):
        score = _score_bilingual("steel box industrial", "steel plate industrial sheet")
        assert 0.2 < score < 0.9

    def test_empty_returns_zero(self):
        assert _score_bilingual("", "something") == 0.0
        assert _score_bilingual("something", "") == 0.0
        assert _score_bilingual("", "") == 0.0

    def test_hebrew_matching(self):
        score = _score_bilingual("קופסת אחסון מפלדה", "פלדה קופסת אחסון ברזל")
        assert score > 0.3


class TestPhase4(unittest.TestCase):
    """Test Phase 4 bilingual verification."""

    def setUp(self):
        _reset_caches()

    def test_good_match_no_ai(self):
        """Both HE and EN scores above threshold -> no AI needed."""
        cls_item = {
            "hs_code": "7326.9000",
            "item": "steel storage box industrial",
            "official_description_he": "פריטים אחרים מפלדה ומברזל",
            "official_description_en": "Other articles of iron or steel storage",
        }
        result = _run_phase4(cls_item)
        assert result["bilingual_match"] is True
        assert result["ai_consulted"] is False

    def test_en_from_uk_api(self):
        """EN empty -> UK tariff import is attempted (inside try/except)."""
        cls_item = {
            "hs_code": "7326.9000",
            "item": "steel storage box",
            "official_description_he": "פריטים מפלדה steel box storage",
            "official_description_en": "",
        }
        # Without a real db or mock, the UK lookup import will be attempted
        # but we test that the function gracefully handles empty EN
        result = _run_phase4(cls_item, db=None)
        # Should still work with HE only
        assert result["en_source"] == "classification"

    def test_he_only_above_threshold(self):
        """Only HE available and above threshold -> match."""
        cls_item = {
            "hs_code": "7326.9000",
            "item": "steel storage box industrial",
            "official_description_he": "אחסון box storage steel industrial מפלדה",
            "official_description_en": "",
        }
        result = _run_phase4(cls_item)
        assert result["bilingual_match"] is True

    def test_no_product_desc(self):
        """No product description -> default match."""
        cls_item = {"hs_code": "7326.9000", "item": ""}
        result = _run_phase4(cls_item)
        assert result["bilingual_match"] is True

    def test_mismatch_without_ai(self):
        """Low scores without AI keys -> mismatch detected."""
        cls_item = {
            "hs_code": "7326.9000",
            "item": "organic coffee beans arabica",
            "official_description_he": "פריטים מפלדה ומברזל",
            "official_description_en": "Other articles of iron or steel",
        }
        result = _run_phase4(cls_item)
        # Should detect mismatch since product is coffee, not steel
        assert result["he_match_score"] < 0.25 or result["en_match_score"] < 0.25


class TestPhase5(unittest.TestCase):
    """Test Phase 5 post-classification knowledge verification."""

    def setUp(self):
        _reset_caches()

    def _mock_db(self, directives=None, framework=None, chapter_notes=None):
        """Create a mock Firestore db with proper collection routing."""
        db = MagicMock()

        # Build mock collections
        directives_mock = MagicMock()
        if directives:
            mock_docs = []
            for doc_id, data in directives:
                mock_doc = MagicMock()
                mock_doc.id = doc_id
                mock_doc.to_dict.return_value = data
                mock_docs.append(mock_doc)
            directives_mock.stream.return_value = mock_docs
        else:
            directives_mock.stream.return_value = []

        framework_mock = MagicMock()
        if framework:
            mock_docs = []
            for doc_id, data in framework:
                mock_doc = MagicMock()
                mock_doc.id = doc_id
                mock_doc.to_dict.return_value = data
                mock_docs.append(mock_doc)
            framework_mock.stream.return_value = mock_docs
        else:
            framework_mock.stream.return_value = []

        chapter_notes_mock = MagicMock()
        if chapter_notes:
            def _get_chapter_doc(chapter_id):
                doc_mock = MagicMock()
                if chapter_id in chapter_notes:
                    result_mock = MagicMock()
                    result_mock.exists = True
                    result_mock.to_dict.return_value = chapter_notes[chapter_id]
                    doc_mock.get.return_value = result_mock
                else:
                    result_mock = MagicMock()
                    result_mock.exists = False
                    doc_mock.get.return_value = result_mock
                return doc_mock
            chapter_notes_mock.document.side_effect = _get_chapter_doc
        else:
            empty_doc = MagicMock()
            empty_doc.exists = False
            chapter_notes_mock.document.return_value.get.return_value = empty_doc

        # Route db.collection() to the right mock
        def _collection_router(name):
            if name == "classification_directives":
                return directives_mock
            elif name == "framework_order":
                return framework_mock
            elif name == "chapter_notes":
                return chapter_notes_mock
            return MagicMock()

        db.collection.side_effect = _collection_router
        return db

    def test_elimination_conflict_detected(self):
        """Agent 2 chose a code that was eliminated -> CRITICAL."""
        db = self._mock_db()
        cls_item = {"hs_code": "7326.9000", "item": "steel box"}
        elim_results = {
            "steel box": {
                "eliminated": [{"hs_code": "7326.9000", "reason": "wrong chapter"}],
                "survivors": [{"hs_code": "7310.2900"}],
            }
        }
        result = _run_phase5(cls_item, db, elimination_results=elim_results)
        assert result["elimination_conflict"] is True
        assert result["verified"] is False
        assert result["confidence_adjustment"] <= -0.30

    def test_elimination_conflict_ok(self):
        """Agent 2 chose a survivor -> no conflict."""
        db = self._mock_db()
        cls_item = {"hs_code": "7326.9000", "item": "steel box"}
        elim_results = {
            "steel box": {
                "eliminated": [{"hs_code": "7310.2900"}],
                "survivors": [{"hs_code": "7326.9000"}],
            }
        }
        result = _run_phase5(cls_item, db, elimination_results=elim_results)
        assert result["elimination_conflict"] is False

    def test_directive_found(self):
        """Directive referencing this HS code found -> info."""
        directives = [
            ("dir_001", {
                "directive_id": "D-2024-001",
                "title": "Steel articles classification",
                "primary_hs_code": "7326",
                "hs_codes_mentioned": [],
                "related_hs_codes": [],
                "content": "steel storage box industrial classification",
                "is_active": True,
            })
        ]
        db = self._mock_db(directives=directives)
        cls_item = {"hs_code": "7326.9000", "item": "steel storage box"}
        result = _run_phase5(cls_item, db)
        assert len(result["directives_found"]) > 0

    def test_chapter_exclusion(self):
        """Chapter exclusion mentions product keywords -> flag."""
        chapter_notes = {
            "chapter_73": {
                "exclusions": [
                    {"text": "steel storage containers for food that are sealed and pressurized"},
                ]
            }
        }
        db = self._mock_db(chapter_notes=chapter_notes)
        cls_item = {"hs_code": "7326.9000", "item": "steel sealed pressurized container for food storage"}
        result = _run_phase5(cls_item, db)
        assert result["chapter_exclusion_hit"] is True
        assert result["confidence_adjustment"] < 0

    def test_graceful_on_empty_data(self):
        """No data at all -> verified=True, no adjustments."""
        db = self._mock_db()
        cls_item = {"hs_code": "7326.9000", "item": "steel box"}
        result = _run_phase5(cls_item, db)
        assert result["verified"] is True
        assert result["confidence_adjustment"] == 0

    def test_no_hs_code(self):
        """No HS code -> early return."""
        db = self._mock_db()
        result = _run_phase5({"item": "box"}, db)
        assert result["verified"] is True


class TestProactiveFlagging(unittest.TestCase):
    """Test proactive flag generation."""

    def test_permit_flag_from_fio(self):
        """FIO authority -> PERMIT flag."""
        cls_item = {"hs_code": "3004.9000", "origin_country": ""}
        fio = {"3004.9000": {"authorities_summary": ["משרד הבריאות"]}}
        flags = _generate_flags(cls_item, free_import_results=fio)
        permit_flags = [f for f in flags if f["type"] == "PERMIT"]
        assert len(permit_flags) == 1
        assert permit_flags[0]["severity"] == "warning"

    def test_standard_flag(self):
        """FIO has_standards -> STANDARD flag."""
        cls_item = {"hs_code": "4015.1900", "origin_country": ""}
        fio = {"4015.1900": {"has_standards": True, "authorities_summary": []}}
        flags = _generate_flags(cls_item, free_import_results=fio)
        std_flags = [f for f in flags if f["type"] == "STANDARD"]
        assert len(std_flags) == 1

    def test_antidumping_ch72_china(self):
        """Chapter 72 from China -> ANTIDUMPING warning."""
        cls_item = {"hs_code": "7210.1100", "origin_country": "China"}
        flags = _generate_flags(cls_item)
        ad_flags = [f for f in flags if f["type"] == "ANTIDUMPING"]
        assert len(ad_flags) == 1
        assert ad_flags[0]["severity"] == "warning"

    def test_antidumping_ch73_turkey(self):
        """Chapter 73 from Turkey -> ANTIDUMPING warning."""
        cls_item = {"hs_code": "7326.9000", "origin_country": "turkey"}
        flags = _generate_flags(cls_item)
        ad_flags = [f for f in flags if f["type"] == "ANTIDUMPING"]
        assert len(ad_flags) == 1

    def test_no_antidumping_other_origin(self):
        """Chapter 73 from Germany -> no ANTIDUMPING."""
        cls_item = {"hs_code": "7326.9000", "origin_country": "Germany"}
        flags = _generate_flags(cls_item)
        ad_flags = [f for f in flags if f["type"] == "ANTIDUMPING"]
        assert len(ad_flags) == 0

    def test_fta_flag(self):
        """FTA eligible -> FTA info flag."""
        cls_item = {
            "hs_code": "8471.3000",
            "origin_country": "EU",
            "fta": {"eligible": True, "agreement": "EU-Israel FTA"},
        }
        flags = _generate_flags(cls_item)
        fta_flags = [f for f in flags if f["type"] == "FTA"]
        assert len(fta_flags) == 1
        assert fta_flags[0]["severity"] == "info"

    def test_elimination_conflict_flag(self):
        """Elimination conflict -> CRITICAL flag."""
        cls_item = {"hs_code": "7326.9000", "origin_country": ""}
        phase5 = {"elimination_conflict": True, "directives_found": []}
        flags = _generate_flags(cls_item, phase5_result=phase5)
        ec_flags = [f for f in flags if f["type"] == "ELIMINATION_CONFLICT"]
        assert len(ec_flags) == 1
        assert ec_flags[0]["severity"] == "critical"

    def test_directive_flag(self):
        """Directive found -> DIRECTIVE info flag."""
        cls_item = {"hs_code": "7326.9000", "origin_country": ""}
        phase5 = {
            "elimination_conflict": False,
            "directives_found": [{"directive_id": "D-001", "title": "Steel classification"}],
        }
        flags = _generate_flags(cls_item, phase5_result=phase5)
        dir_flags = [f for f in flags if f["type"] == "DIRECTIVE"]
        assert len(dir_flags) == 1

    def test_bilingual_mismatch_flag(self):
        """Bilingual mismatch -> WARNING flag."""
        cls_item = {"hs_code": "7326.9000", "origin_country": ""}
        phase4 = {"bilingual_match": False, "mismatch_details": "Low overlap"}
        flags = _generate_flags(cls_item, phase4_result=phase4)
        bm_flags = [f for f in flags if f["type"] == "BILINGUAL_MISMATCH"]
        assert len(bm_flags) == 1
        assert bm_flags[0]["severity"] == "warning"

    def test_no_false_positives(self):
        """No data -> no flags."""
        cls_item = {"hs_code": "8471.3000", "origin_country": "USA"}
        flags = _generate_flags(cls_item)
        assert len(flags) == 0


class TestRunVerificationEngine(unittest.TestCase):
    """Test the main entry point."""

    def setUp(self):
        _reset_caches()

    def _mock_db(self):
        db = MagicMock()
        directives_mock = MagicMock()
        directives_mock.stream.return_value = []
        framework_mock = MagicMock()
        framework_mock.stream.return_value = []
        chapter_notes_mock = MagicMock()
        empty_doc = MagicMock()
        empty_doc.exists = False
        chapter_notes_mock.document.return_value.get.return_value = empty_doc

        def _collection_router(name):
            if name == "classification_directives":
                return directives_mock
            elif name == "framework_order":
                return framework_mock
            elif name == "chapter_notes":
                return chapter_notes_mock
            return MagicMock()

        db.collection.side_effect = _collection_router
        return db

    def test_empty_input(self):
        result = run_verification_engine(None, [])
        assert result["summary"]["total"] == 0

    def test_single_item_full_run(self):
        db = self._mock_db()
        classifications = [{
            "hs_code": "7326.9000",
            "item": "steel storage box",
            "official_description_he": "פריטים אחרים מפלדה",
            "official_description_en": "Other articles of steel",
            "confidence": 0.85,
        }]
        result = run_verification_engine(db, classifications)
        assert result["summary"]["total"] == 1
        assert "7326.9000" in result
        assert "phase4" in result["7326.9000"]
        assert "phase5" in result["7326.9000"]
        assert "flags" in result["7326.9000"]

    def test_summary_counts(self):
        db = self._mock_db()
        classifications = [
            {
                "hs_code": "7326.9000",
                "item": "steel box",
                "official_description_he": "פלדה",
                "official_description_en": "steel",
                "confidence": 0.8,
            },
            {
                "hs_code": "4015.1900",
                "item": "rubber gloves",
                "official_description_he": "גומי",
                "official_description_en": "rubber",
                "confidence": 0.9,
            },
        ]
        result = run_verification_engine(db, classifications)
        assert result["summary"]["total"] == 2

    def test_none_classifications_skipped(self):
        db = self._mock_db()
        classifications = [None, {"hs_code": "7326.9000", "item": "steel", "confidence": 0.8}]
        result = run_verification_engine(db, classifications)
        assert result["summary"]["total"] == 1


class TestBuildVerificationFlagsHtml(unittest.TestCase):
    """Test HTML rendering of verification badges and flags."""

    def test_empty_returns_empty(self):
        assert build_verification_flags_html({}) == ""
        assert build_verification_flags_html({"ve_flags": [], "ve_phase4": {}}) == ""

    def test_critical_flag_red(self):
        item = {
            "ve_flags": [{
                "type": "ELIMINATION_CONFLICT",
                "severity": "critical",
                "message_he": "קוד נפסל",
                "message_en": "Code eliminated",
                "source": "test",
            }],
            "ve_phase4": {},
        }
        html = build_verification_flags_html(item)
        assert "#991b1b" in html  # critical red color
        assert "קוד נפסל" in html

    def test_multiple_flags(self):
        item = {
            "ve_flags": [
                {
                    "type": "PERMIT",
                    "severity": "warning",
                    "message_he": "נדרש אישור",
                    "message_en": "Permit required",
                    "source": "test",
                },
                {
                    "type": "FTA",
                    "severity": "info",
                    "message_he": "FTA זכאי",
                    "message_en": "FTA eligible",
                    "source": "test",
                },
            ],
            "ve_phase4": {},
        }
        html = build_verification_flags_html(item)
        assert "נדרש אישור" in html
        assert "FTA זכאי" in html

    def test_phase4_badge(self):
        item = {
            "ve_flags": [],
            "ve_phase4": {
                "bilingual_match": True,
                "he_match_score": 0.45,
                "en_match_score": 0.55,
            },
        }
        html = build_verification_flags_html(item)
        assert "אימות דו-לשוני עבר" in html
        assert "#166534" in html  # green info color

    def test_phase4_mismatch_badge(self):
        item = {
            "ve_flags": [],
            "ve_phase4": {
                "bilingual_match": False,
                "he_match_score": 0.10,
                "en_match_score": 0.05,
            },
        }
        html = build_verification_flags_html(item)
        assert "אי-התאמה" in html
        assert "#92400e" in html  # warning amber color

    def test_valid_html(self):
        item = {
            "ve_flags": [{
                "type": "STANDARD",
                "severity": "warning",
                "message_he": "תקן",
                "message_en": "Standard",
                "source": "test",
            }],
            "ve_phase4": {"bilingual_match": True, "he_match_score": 0.5, "en_match_score": 0.5},
        }
        html = build_verification_flags_html(item)
        assert html.startswith('<div')
        assert html.endswith('</div>')


class TestHsUtilities(unittest.TestCase):
    """Test HS code utilities."""

    def test_clean_hs(self):
        assert _clean_hs("7326.9000") == "73269000"
        assert _clean_hs("73 26 / 90.00") == "73269000"

    def test_chapter_from_hs(self):
        assert _chapter_from_hs("7326.9000") == "73"
        assert _chapter_from_hs("0401.1000") == "04"
        assert _chapter_from_hs("") == ""


if __name__ == "__main__":
    unittest.main()
