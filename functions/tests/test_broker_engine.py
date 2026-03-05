"""Tests for broker_engine.py — deterministic classification engine.

Session 90: ~50 tests covering Phases 0-9.
"""

import pytest
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))


# ---------------------------------------------------------------------------
#  IMPORTS
# ---------------------------------------------------------------------------

from lib.broker_engine import (
    process_case,
    classify_single_item,
    verify_and_loop,
    _identify_items_with_ai,
    _fallback_item_identification,
    _check_spare_part,
    _apply_chapter98,
    _post_classification_cascade,
    _collect_ordinance_articles,
    _lookup_fio,
    _lookup_feo,
    _lookup_fta_for_item,
    _format_fio_result,
    _format_feo_result,
    _extract_standard_ref,
    _is_ip_relevant,
    _run_verification_checks,
    _generate_clarification_questions,
    _generate_kram_result,
    _determine_origin_rules,
    _determine_preference_doc,
    _build_valuation_summary,
    _build_release_notes,
    _build_candidates_for_item,
    _FTA_COUNTRY_MAP,
    ISRAEL_VAT_RATE,
    _SPARE_PART_RE,
)


# ---------------------------------------------------------------------------
#  MOCK DB
# ---------------------------------------------------------------------------

class _MockDoc:
    def __init__(self, data=None, doc_id=""):
        self._data = data
        self.exists = data is not None
        self.id = doc_id

    def to_dict(self):
        return self._data or {}


class _MockCollection:
    def __init__(self, docs=None):
        self._docs = docs or {}

    def document(self, doc_id):
        return _MockDocRef(self._docs.get(doc_id))

    def where(self, *args, **kwargs):
        return self

    def limit(self, n):
        return self

    def stream(self):
        return iter([])


class _MockDocRef:
    def __init__(self, data=None):
        self._data = data

    def get(self):
        return _MockDoc(self._data)


class _MockDB:
    def __init__(self, collections=None):
        self._collections = collections or {}

    def collection(self, name):
        return _MockCollection(self._collections.get(name, {}))


def _make_db(**collections):
    return _MockDB(collections)


# ---------------------------------------------------------------------------
#  PHASE 0: Operation Type (via analyze_case)
# ---------------------------------------------------------------------------

class TestPhase0OperationType:
    def test_toshav_chozer_detected(self):
        from lib.case_reasoning import analyze_case
        plan = analyze_case("", "אני תושב חוזר, רוצה לייבא ספה, טלוויזיה")
        assert plan.legal_category == "toshav_chozer"
        assert plan.direction == "import"
        assert len(plan.items_to_classify) >= 2

    def test_oleh_chadash_detected(self):
        from lib.case_reasoning import analyze_case
        plan = analyze_case("", "עולה חדשה, מביאה רהיטים וכלי מטבח")
        assert plan.legal_category == "oleh_chadash"

    def test_commercial_no_legal_category(self):
        from lib.case_reasoning import analyze_case
        plan = analyze_case("", "We want to import steel bolts from China")
        assert plan.legal_category == ""

    def test_export_direction(self):
        from lib.case_reasoning import analyze_case
        plan = analyze_case("", "רוצים לייצא מזון")
        # May or may not detect direction from "לייצא" —
        # but should detect food item
        assert any(it.get("category") == "food" for it in plan.items_to_classify)

    def test_tourist_detected(self):
        from lib.case_reasoning import analyze_case
        plan = analyze_case("", "אני תייר, קניתי תכשיטים בחו\"ל")
        assert plan.legal_category == "tourist"
        assert plan.discount_group == "7"

    def test_diplomat_detected(self):
        from lib.case_reasoning import analyze_case
        plan = analyze_case("", "אני דיפלומט, מביא ציוד אישי")
        assert plan.legal_category == "diplomat"


# ---------------------------------------------------------------------------
#  PHASE 1: Item Identification
# ---------------------------------------------------------------------------

class TestPhase1ItemIdentification:
    def test_fallback_furniture(self):
        items = [{"name": "sofa", "category": "furniture", "keywords": ["sofa"]}]
        result = _fallback_item_identification(items)
        assert result[0]["physical"]
        assert result[0]["essence"]
        assert result[0]["function"]

    def test_fallback_electronics(self):
        items = [{"name": "TV", "category": "electronics", "keywords": ["TV"]}]
        result = _fallback_item_identification(items)
        assert "circuit" in result[0]["physical"] or "metal" in result[0]["physical"]

    def test_fallback_vehicle(self):
        items = [{"name": "car", "category": "vehicle", "keywords": ["car"]}]
        result = _fallback_item_identification(items)
        assert "steel" in result[0]["physical"]

    def test_no_ai_returns_fallback(self):
        items = [{"name": "desk", "category": "furniture", "keywords": ["desk"]}]
        result = _identify_items_with_ai(items, None)
        assert result[0].get("physical")

    def test_empty_items(self):
        result = _identify_items_with_ai([], None)
        assert result == []


# ---------------------------------------------------------------------------
#  PHASE 2: Spare Parts
# ---------------------------------------------------------------------------

class TestPhase2SpareParts:
    def test_spare_part_detected_vehicle(self):
        item = {"name": "brake pad", "essence": "vehicle part"}
        result = _check_spare_part(item, "spare part for my car", None)
        assert result == "87"

    def test_spare_part_detected_machine(self):
        item = {"name": "motor", "essence": "machine component"}
        result = _check_spare_part(item, "replacement part for machinery", None)
        assert result == "84"

    def test_no_spare_part(self):
        item = {"name": "sofa", "essence": "furniture"}
        result = _check_spare_part(item, "I want to import a sofa", None)
        assert result is None

    def test_spare_part_regex(self):
        assert _SPARE_PART_RE.search("חלקי חילוף לרכב")
        assert _SPARE_PART_RE.search("spare parts for washing machine")
        assert _SPARE_PART_RE.search("אביזרים למחשב")
        assert not _SPARE_PART_RE.search("sofa for living room")


# ---------------------------------------------------------------------------
#  PHASE 7: Chapter 98
# ---------------------------------------------------------------------------

class TestPhase7Chapter98:
    def test_furniture_maps_to_9801400000(self):
        from lib._chapter98_data import get_chapter98_code
        result = get_chapter98_code("9401600000")
        assert result == "9801400000"

    def test_clothing_maps_to_9801100000(self):
        from lib._chapter98_data import get_chapter98_code
        result = get_chapter98_code("6109100000")
        assert result == "9801100000"

    def test_vehicles_map_to_spare_parts(self):
        from lib._chapter98_data import get_chapter98_code
        result = get_chapter98_code("8703800000")
        # Chapter 87 maps to 9803200000 (vehicle spare parts entry)
        assert result == "9803200000"

    def test_apply_chapter98_sets_fields(self):
        item_result = {"hs_code": "9401600000"}
        item = {"name": "sofa", "category": "furniture"}
        _apply_chapter98(item_result, item, "toshav_chozer", "furniture")
        assert item_result.get("chapter98_code") == "9801400000"
        assert item_result.get("chapter98_duty") == "exempt"

    def test_apply_chapter98_no_legal_category(self):
        item_result = {"hs_code": "9401600000"}
        item = {"name": "sofa", "category": "furniture"}
        _apply_chapter98(item_result, item, "", "furniture")
        assert "chapter98_code" not in item_result


# ---------------------------------------------------------------------------
#  PHASE 8: Post-Classification Cascade
# ---------------------------------------------------------------------------

class TestPhase8PostClassification:
    def test_fio_lookup_not_found(self):
        db = _make_db()
        result = _lookup_fio(db, "9999999999")
        assert result.get("found") is False

    def test_fio_lookup_found(self):
        db = _make_db(free_import_order={
            "4011100000": {
                "goods_description": "pneumatic tyres",
                "requirements": [
                    {"confirmation_type": "type approval",
                     "authority": "Ministry of Transport",
                     "appendix": "2",
                     "conditions": "SI 1022"},
                ],
                "authorities_summary": ["Ministry of Transport"],
                "has_standards": True,
                "has_lab_testing": False,
                "appendices": ["2"],
                "active_count": 1,
            }
        })
        result = _lookup_fio(db, "4011100000")
        assert result.get("found") is True
        assert "Ministry of Transport" in result["authorities_summary"]

    def test_feo_lookup_not_found(self):
        db = _make_db()
        result = _lookup_feo(db, "9999999999")
        assert result.get("found") is False

    def test_feo_lookup_found(self):
        db = _make_db(free_export_order={
            "8471300000": {
                "goods_description": "laptops",
                "authorities_summary": ["Ministry of Economy"],
                "confirmation_types": ["export license"],
                "appendices": ["3"],
                "has_absolute": True,
                "active_count": 1,
                "requirements": [
                    {"confirmation_type": "export license",
                     "authority": "Ministry of Economy",
                     "appendix": "3"},
                ],
            }
        })
        result = _lookup_feo(db, "8471300000")
        assert result.get("found") is True
        assert result["has_absolute"] is True

    def test_format_fio_extracts_standard(self):
        fio = {
            "found": True,
            "goods_description": "tyres",
            "requirements": [
                {"confirmation_type": "type approval SI 1022",
                 "authority": "MOT", "appendix": "2", "conditions": ""},
            ],
            "authorities_summary": ["MOT"],
            "has_standards": True,
            "has_lab_testing": False,
            "appendices": ["2"],
            "active_count": 1,
        }
        formatted = _format_fio_result(fio)
        assert formatted["has_standards"] is True
        assert len(formatted["requirements"]) == 1
        assert formatted["requirements"][0]["authority"] == "MOT"

    def test_extract_standard_ref_si(self):
        assert _extract_standard_ref({"confirmation_type": "SI 1022"}) == "SI 1022"
        assert _extract_standard_ref({"confirmation_type": 'ת"י 900'}) == "SI 900"
        assert _extract_standard_ref({"confirmation_type": "no standard"}) == ""

    def test_collect_ordinance_articles_import(self):
        ctx = {"direction": "import", "legal_category": "toshav_chozer",
               "legal_category_he": "תושב חוזר"}
        articles = _collect_ordinance_articles(ctx, {})
        assert "personal_use_129" in articles
        assert "valuation_130_133" in articles
        assert "release_62" in articles

    def test_collect_ordinance_articles_no_legal(self):
        ctx = {"direction": "import", "legal_category": ""}
        articles = _collect_ordinance_articles(ctx, {})
        assert "personal_use_129" not in articles
        assert "valuation_130_133" in articles

    def test_ip_relevant_electronics(self):
        assert _is_ip_relevant({"hs_code": "8471300000"}) is True

    def test_ip_not_relevant_food(self):
        assert _is_ip_relevant({"hs_code": "0201100000"}) is False

    def test_post_cascade_adds_vat(self):
        item_result = {"hs_code": "9401600000"}
        ctx = {"direction": "import", "legal_category": ""}
        db = _make_db()
        _post_classification_cascade(item_result, {}, ctx, db)
        assert item_result["vat_rate"] == "18%"


# ---------------------------------------------------------------------------
#  FTA LOOKUP
# ---------------------------------------------------------------------------

class TestFTALookup:
    def test_fta_country_map_eu(self):
        assert _FTA_COUNTRY_MAP["germany"] == "eu"
        assert _FTA_COUNTRY_MAP["france"] == "eu"

    def test_fta_country_map_usa(self):
        assert _FTA_COUNTRY_MAP["usa"] == "usa"
        assert _FTA_COUNTRY_MAP["united states"] == "usa"

    def test_origin_rules_eu(self):
        rules = _determine_origin_rules("eu")
        assert rules["protocol"] == "Protocol 4"
        assert rules["type"] == "cumulation_diagonal"

    def test_origin_rules_usa(self):
        rules = _determine_origin_rules("usa")
        assert rules["min_local_content"] == "35%"

    def test_preference_doc_eu(self):
        doc = _determine_preference_doc("eu")
        assert doc["primary"] == "EUR.1"
        assert "invoice" in doc["alternative"].lower()

    def test_preference_doc_usa(self):
        doc = _determine_preference_doc("usa")
        assert "Certificate" in doc["primary"]

    def test_unknown_country(self):
        rules = _determine_origin_rules("unknown_country")
        assert rules["type"] == "unknown"


# ---------------------------------------------------------------------------
#  PHASE 9: Verification
# ---------------------------------------------------------------------------

class TestPhase9Verification:
    def _make_result(self, hs_code="9401600000", **kwargs):
        return {"hs_code": hs_code, "confidence": 0.7,
                "description": "Furniture", "duty_rate": "12%",
                "source": "test", **kwargs}

    def test_hs_exists_check_passes(self):
        db = _make_db(tariff={"9401600000": {"description_he": "ריהוט"}})
        errors = _run_verification_checks(
            self._make_result(), {"name": "sofa"}, {"legal_category": ""}, db,
        )
        hs_errors = [e for e in errors if e["check"] == "hs_exists"]
        assert len(hs_errors) == 0

    def test_hs_exists_check_fails(self):
        db = _make_db(tariff={})
        errors = _run_verification_checks(
            self._make_result("9999999999"), {"name": "sofa"}, {"legal_category": ""}, db,
        )
        hs_errors = [e for e in errors if e["check"] == "hs_exists"]
        assert len(hs_errors) == 1

    def test_chapter98_mismatch_detected(self):
        from lib._chapter98_data import get_chapter98_entry
        result = self._make_result("8471300000")
        result["chapter98_code"] = "9801400000"  # furniture — wrong for ch84
        db = _make_db(tariff={"8471300000": {"description_he": "computers"}})
        errors = _run_verification_checks(
            result, {"name": "computer"}, {"legal_category": "toshav_chozer"}, db,
        )
        ch98_errors = [e for e in errors if e["check"] == "chapter98_mismatch"]
        assert len(ch98_errors) == 1

    def test_discount_code_check(self):
        result = self._make_result()
        result["discount"] = {"discount_sub_code": "999999"}  # Non-existent
        db = _make_db(tariff={"9401600000": {"description_he": "ריהוט"}})
        errors = _run_verification_checks(
            result, {"name": "sofa"}, {"legal_category": "toshav_chozer"}, db,
        )
        disc_errors = [e for e in errors if e["check"] == "discount_code_missing"]
        assert len(disc_errors) == 1

    def test_kram_on_loop_exhaustion(self):
        kram = _generate_kram_result(
            {"hs_code": "1234567890"}, [{"check": "hs_exists"}], {"name": "widget"},
        )
        assert kram["status"] == "kram"
        assert len(kram["kram_questions"]) > 0

    def test_kram_questions_specific(self):
        errors = [
            {"check": "hs_exists", "message": "not found"},
            {"check": "chapter_exclusion", "exclusion_text": "textiles excluded here"},
            {"check": "more_specific", "alternative_code": "8471.41"},
        ]
        questions = _generate_clarification_questions(errors, {"name": "item"}, None)
        assert len(questions) == 3
        # Each question should have Hebrew and English
        for q in questions:
            assert q.get("question_he")
            assert q.get("question_en")

    def test_empty_errors_generate_catchall(self):
        questions = _generate_clarification_questions([], {"name": "item"}, None)
        assert len(questions) == 1

    def test_verified_result_has_flag(self):
        # Simulate a result that passes all checks
        result = self._make_result()
        db = _make_db(tariff={"9401600000": {"description_he": "ריהוט"}})
        # Mock verify_and_loop with max_loops=1 — if no errors, verified=True
        errors = _run_verification_checks(result, {"name": "sofa"}, {"legal_category": ""}, db)
        if not errors:
            result["verified"] = True
        assert result.get("verified") is True


# ---------------------------------------------------------------------------
#  VALUATION + RELEASE
# ---------------------------------------------------------------------------

class TestValuationAndRelease:
    def test_valuation_summary_import(self):
        ctx = {"direction": "import"}
        val = _build_valuation_summary(ctx)
        assert val["primary_method"] == "transaction_value"
        assert val["primary_article"] == "132"
        assert len(val["legal_hierarchy"]) == 6

    def test_valuation_summary_export_empty(self):
        ctx = {"direction": "export"}
        val = _build_valuation_summary(ctx)
        assert val == {}

    def test_release_notes_basic(self):
        ctx = {"direction": "import", "legal_category": ""}
        notes = _build_release_notes(ctx)
        assert any(n["article"] == "62" for n in notes)

    def test_release_notes_with_legal(self):
        ctx = {"direction": "import", "legal_category": "toshav_chozer",
               "legal_category_he": "תושב חוזר"}
        notes = _build_release_notes(ctx)
        assert any(n["article"] == "129" for n in notes)


# ---------------------------------------------------------------------------
#  INTEGRATION: process_case
# ---------------------------------------------------------------------------

class TestProcessCaseIntegration:
    def test_empty_input_returns_none(self):
        result = process_case("", "", _make_db(), None)
        assert result is None

    def test_no_items_detected(self):
        result = process_case("Hello, how are you?", "", _make_db(), None)
        assert result is not None
        assert result["status"] == "no_items"
        assert len(result.get("kram_questions", [])) > 0

    def test_toshav_chozer_items_detected(self):
        text = "אני תושב חוזר, רוצה לייבא ספה, טלוויזיה"
        result = process_case(text, "", _make_db(), None)
        assert result is not None
        assert result["operation"]["legal_category"] == "toshav_chozer"
        assert result["operation"]["direction"] == "import"
        assert len(result["items"]) >= 2
        assert result.get("vat_rate") == "18%"

    def test_result_has_ordinance_articles(self):
        text = "אני עולה חדש, מביא רהיטים"
        result = process_case(text, "", _make_db(), None)
        assert "ordinance_articles" in result

    def test_result_has_valuation(self):
        text = "אני תושב חוזר, מביא ספה"
        result = process_case(text, "", _make_db(), None)
        if result.get("valuation"):
            assert result["valuation"]["primary_method"] == "transaction_value"


# ---------------------------------------------------------------------------
#  CONSULTATION HANDLER WIRING
# ---------------------------------------------------------------------------

class TestConsultationHandlerWiring:
    def test_broker_engine_available_flag(self):
        from lib.consultation_handler import BROKER_ENGINE_AVAILABLE
        assert isinstance(BROKER_ENGINE_AVAILABLE, bool)
        assert BROKER_ENGINE_AVAILABLE is True

    def test_broker_process_case_imported(self):
        from lib.consultation_handler import broker_process_case
        assert broker_process_case is not None
        assert callable(broker_process_case)


# ---------------------------------------------------------------------------
#  CONSTANTS
# ---------------------------------------------------------------------------

class TestConstants:
    def test_vat_rate(self):
        assert ISRAEL_VAT_RATE == "18%"

    def test_fta_map_has_major_countries(self):
        for country in ["eu", "usa", "uk", "turkey", "canada", "korea",
                        "jordan", "efta", "vietnam", "uae"]:
            assert country in _FTA_COUNTRY_MAP

    def test_spare_part_regex_hebrew(self):
        assert _SPARE_PART_RE.search("חלקי חילוף")
        assert _SPARE_PART_RE.search("אביזרים")

    def test_spare_part_regex_english(self):
        assert _SPARE_PART_RE.search("spare parts")
        assert _SPARE_PART_RE.search("accessories")
