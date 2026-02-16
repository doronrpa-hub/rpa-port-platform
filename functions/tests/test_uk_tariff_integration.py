"""
Tests for UK Tariff API Integration
Assignment 18 — Session 28D
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone, timedelta

from lib.uk_tariff_integration import (
    convert_il_to_uk_code,
    convert_uk_to_il_code,
    fetch_uk_tariff_live,
    lookup_uk_tariff,
    simple_description_match,
    compare_il_uk_classification,
    get_uk_verification_for_cross_check,
    post_classification_uk_fetch,
    _parse_uk_api_response,
    _is_cache_fresh,
)


# ═══════════════════════════════════════════
#  CODE CONVERSION TESTS
# ═══════════════════════════════════════════

class TestConvertIlToUkCode:
    def test_8digit_padded_to_10(self):
        assert convert_il_to_uk_code("84713000") == "8471300000"

    def test_formatted_code_with_dots(self):
        assert convert_il_to_uk_code("8471.30.0000") == "8471300000"

    def test_6digit_padded(self):
        assert convert_il_to_uk_code("847130") == "8471300000"

    def test_10digit_unchanged(self):
        assert convert_il_to_uk_code("8471300090") == "8471300090"

    def test_empty_returns_none(self):
        assert convert_il_to_uk_code("") is None

    def test_with_slashes(self):
        assert convert_il_to_uk_code("8471/30/00") == "8471300000"

    def test_short_4digit(self):
        assert convert_il_to_uk_code("8471") == "8471000000"


class TestConvertUkToIlCode:
    def test_10digit(self):
        assert convert_uk_to_il_code("8471300000") == "8471300000"

    def test_formatted(self):
        assert convert_uk_to_il_code("8471.30.0000") == "8471300000"

    def test_empty_returns_none(self):
        assert convert_uk_to_il_code("") is None


# ═══════════════════════════════════════════
#  API RESPONSE PARSING TESTS
# ═══════════════════════════════════════════

class TestParseUkApiResponse:
    def test_parses_commodity_data(self):
        api_resp = {
            "data": {
                "id": "8471300000",
                "type": "commodity",
                "attributes": {
                    "description": "Portable automatic data-processing machines",
                    "formatted_description": "<strong>Portable</strong> automatic data-processing machines",
                    "number_indents": 2,
                    "goods_nomenclature_item_id": "8471300000",
                },
            },
            "included": [
                {
                    "type": "chapter",
                    "attributes": {
                        "description": "Nuclear reactors, boilers, machinery",
                        "goods_nomenclature_item_id": "8400000000",
                    },
                },
                {
                    "type": "heading",
                    "attributes": {
                        "description": "Automatic data-processing machines",
                        "goods_nomenclature_item_id": "8471000000",
                    },
                },
                {
                    "type": "footnote",
                    "attributes": {"description": "Some footnote text"},
                },
            ],
        }
        result = _parse_uk_api_response(api_resp, "8471300000")
        assert result["found"] is True
        assert result["description"] == "Portable automatic data-processing machines"
        assert result["heading"] == "84.71"
        assert len(result["ancestors"]) == 2
        assert result["ancestors"][0]["type"] == "chapter"
        assert len(result["footnotes"]) == 1

    def test_empty_response(self):
        result = _parse_uk_api_response({"data": {}, "included": []}, "0000000000")
        assert result["found"] is True
        assert result["description"] == ""


# ═══════════════════════════════════════════
#  LIVE FETCH TESTS (mocked)
# ═══════════════════════════════════════════

class TestFetchUkTariffLive:
    @patch("lib.uk_tariff_integration.requests.get")
    def test_successful_fetch(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "attributes": {
                    "description": "Laptops",
                    "formatted_description": "Laptops",
                    "number_indents": 2,
                    "goods_nomenclature_item_id": "8471300000",
                },
            },
            "included": [],
        }
        mock_get.return_value = mock_resp

        result = fetch_uk_tariff_live("8471300000")
        assert result is not None
        assert result["found"] is True
        assert result["description"] == "Laptops"
        mock_get.assert_called_once()

    @patch("lib.uk_tariff_integration.requests.get")
    def test_404_returns_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        result = fetch_uk_tariff_live("9999999999")
        assert result is not None
        assert result["found"] is False
        assert result["error"] == "not_found"

    @patch("lib.uk_tariff_integration.requests.get")
    def test_timeout_returns_none(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout("timed out")

        result = fetch_uk_tariff_live("8471300000")
        assert result is None

    @patch("lib.uk_tariff_integration.requests.get")
    def test_500_returns_none(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        result = fetch_uk_tariff_live("8471300000")
        assert result is None

    def test_short_code_rejected(self):
        result = fetch_uk_tariff_live("84")
        assert result is None


# ═══════════════════════════════════════════
#  CACHE FRESHNESS TESTS
# ═══════════════════════════════════════════

class TestCacheFreshness:
    def test_recent_is_fresh(self):
        recent = datetime.now(timezone.utc).isoformat()
        assert _is_cache_fresh(recent) is True

    def test_old_is_stale(self):
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        assert _is_cache_fresh(old) is False

    def test_invalid_date_is_stale(self):
        assert _is_cache_fresh("not-a-date") is False

    def test_empty_is_stale(self):
        assert _is_cache_fresh("") is False


# ═══════════════════════════════════════════
#  DESCRIPTION MATCHING TESTS
# ═══════════════════════════════════════════

class TestSimpleDescriptionMatch:
    def test_identical_descriptions(self):
        score = simple_description_match(
            "Portable automatic data-processing machines",
            "Portable automatic data-processing machines",
        )
        assert score > 0.8

    def test_similar_descriptions(self):
        score = simple_description_match(
            "Automatic data processing machine laptop",
            "Portable automatic data-processing machines and units",
        )
        assert score > 0.3

    def test_unrelated_descriptions(self):
        score = simple_description_match(
            "Fresh apples from New Zealand",
            "Portable automatic data-processing machines",
        )
        assert score < 0.2

    def test_empty_returns_zero(self):
        assert simple_description_match("", "something") == 0.0
        assert simple_description_match("something", "") == 0.0

    def test_html_stripped(self):
        score = simple_description_match(
            "data processing machines",
            "<strong>data</strong> processing <em>machines</em>",
        )
        assert score > 0.8


# ═══════════════════════════════════════════
#  LOOKUP WITH CACHE TESTS
# ═══════════════════════════════════════════

class TestLookupUkTariff:
    def test_returns_cached_data(self):
        db = MagicMock()
        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = {
            "uk_code": "8471300000",
            "description": "Laptops",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "found": True,
        }
        db.collection.return_value.document.return_value.get.return_value = doc_mock

        result = lookup_uk_tariff(db, "84713000")
        assert result is not None
        assert result["description"] == "Laptops"

    @patch("lib.uk_tariff_integration.fetch_uk_tariff_live")
    def test_fetches_live_on_cache_miss(self, mock_fetch):
        db = MagicMock()
        doc_mock = MagicMock()
        doc_mock.exists = False
        db.collection.return_value.document.return_value.get.return_value = doc_mock

        mock_fetch.return_value = {
            "uk_code": "8471300000",
            "description": "Laptops",
            "found": True,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        result = lookup_uk_tariff(db, "84713000")
        assert result is not None
        assert result["description"] == "Laptops"
        mock_fetch.assert_called_once_with("8471300000")
        # Verify it tried to store in cache
        db.collection.return_value.document.return_value.set.assert_called_once()

    def test_invalid_code_returns_none(self):
        db = MagicMock()
        result = lookup_uk_tariff(db, "")
        assert result is None


# ═══════════════════════════════════════════
#  CLASSIFICATION COMPARISON TESTS
# ═══════════════════════════════════════════

class TestCompareIlUkClassification:
    @patch("lib.uk_tariff_integration.lookup_uk_tariff")
    def test_strong_match_6digit(self, mock_lookup):
        mock_lookup.return_value = {
            "uk_code": "8471300000",
            "description": "Portable data-processing machines",
            "found": True,
            "ancestors": [],
        }
        db = MagicMock()
        result = compare_il_uk_classification(db, "8471300090", "Laptop computer")
        assert result["match_level"] == "strong"
        assert "6-digit match" in result["verification_note"]

    @patch("lib.uk_tariff_integration.lookup_uk_tariff")
    def test_moderate_match_heading(self, mock_lookup):
        mock_lookup.return_value = {
            "uk_code": "8471490000",
            "description": "Other data-processing machines",
            "found": True,
            "ancestors": [],
        }
        db = MagicMock()
        result = compare_il_uk_classification(db, "8471300090", "Desktop computer")
        assert result["match_level"] == "moderate"
        assert "heading match" in result["verification_note"]

    @patch("lib.uk_tariff_integration.lookup_uk_tariff")
    def test_not_found(self, mock_lookup):
        mock_lookup.return_value = {
            "uk_code": "9999999999",
            "found": False,
            "error": "not_found",
        }
        db = MagicMock()
        result = compare_il_uk_classification(db, "9999999999", "Unknown")
        assert result["match_level"] == "not_found"

    @patch("lib.uk_tariff_integration.lookup_uk_tariff")
    def test_no_data(self, mock_lookup):
        mock_lookup.return_value = None
        db = MagicMock()
        result = compare_il_uk_classification(db, "8471300090", "Laptop")
        assert result["match_level"] == "no_data"


# ═══════════════════════════════════════════
#  CROSS-CHECK HOOK TESTS
# ═══════════════════════════════════════════

class TestGetUkVerificationForCrossCheck:
    @patch("lib.uk_tariff_integration.compare_il_uk_classification")
    def test_strong_match_returns_vote(self, mock_compare):
        mock_compare.return_value = {
            "match_level": "strong",
            "uk_code": "8471300000",
            "verification_note": "6-digit match",
            "similarity": 0.85,
        }
        db = MagicMock()
        result = get_uk_verification_for_cross_check(db, "84713000", "Laptop")
        assert result["hs_code"] == "8471300000"
        assert result["confidence"] == 0.9
        assert result["source"] == "uk_tariff"

    @patch("lib.uk_tariff_integration.compare_il_uk_classification")
    def test_no_data_returns_null_hs(self, mock_compare):
        mock_compare.return_value = {
            "match_level": "no_data",
            "uk_code": "",
            "verification_note": "UK data unavailable",
            "similarity": 0.0,
        }
        db = MagicMock()
        result = get_uk_verification_for_cross_check(db, "84713000", "Laptop")
        assert result["hs_code"] is None
        assert result["confidence"] == 0

    @patch("lib.uk_tariff_integration.compare_il_uk_classification")
    def test_exception_handled(self, mock_compare):
        mock_compare.side_effect = Exception("Network error")
        db = MagicMock()
        result = get_uk_verification_for_cross_check(db, "84713000", "Laptop")
        assert result["hs_code"] is None
        assert result["match_level"] == "error"


# ═══════════════════════════════════════════
#  POST-CLASSIFICATION FETCH TESTS
# ═══════════════════════════════════════════

class TestPostClassificationUkFetch:
    @patch("lib.uk_tariff_integration.fetch_uk_tariff_live")
    def test_fetches_missing_items(self, mock_fetch):
        db = MagicMock()
        # Cache miss
        doc_mock = MagicMock()
        doc_mock.exists = False
        db.collection.return_value.document.return_value.get.return_value = doc_mock

        mock_fetch.return_value = {
            "uk_code": "8471300000",
            "description": "Laptops",
            "found": True,
            "fetched_at": "2026-02-16T00:00:00+00:00",
        }

        result = post_classification_uk_fetch(db, {
            "classifications": [
                {"hs_code": "84713000"},
                {"hs_code": "84714900"},
            ]
        })
        assert result["fetched"] == 2
        assert result["items_checked"] == 2

    def test_skips_already_cached(self):
        db = MagicMock()
        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = {
            "uk_code": "8471300000",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "found": True,
        }
        db.collection.return_value.document.return_value.get.return_value = doc_mock

        result = post_classification_uk_fetch(db, {
            "classifications": [{"hs_code": "84713000"}]
        })
        assert result["already_cached"] == 1
        assert result["fetched"] == 0

    def test_empty_classifications(self):
        db = MagicMock()
        result = post_classification_uk_fetch(db, {"classifications": []})
        assert result["items_checked"] == 0

    def test_limits_to_5_items(self):
        db = MagicMock()
        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = {
            "uk_code": "8471300000",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "found": True,
        }
        db.collection.return_value.document.return_value.get.return_value = doc_mock

        classifications = [{"hs_code": f"847130000{i}"} for i in range(10)]
        result = post_classification_uk_fetch(db, {"classifications": classifications})
        assert result["items_checked"] == 5


# ═══════════════════════════════════════════
#  JUSTIFICATION ENGINE HOOK TEST
# ═══════════════════════════════════════════

class TestJustificationEngineHook:
    @patch("lib.uk_tariff_integration.lookup_uk_tariff")
    def test_step9_appears_in_chain(self, mock_lookup):
        """Verify that build_justification_chain includes Step 9 (UK verification)."""
        mock_lookup.return_value = {
            "uk_code": "8471300000",
            "description": "Portable machines",
            "found": True,
            "ancestors": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        # Mock Firestore with chapter notes and tariff
        db = MagicMock()
        ch_doc = MagicMock()
        ch_doc.exists = True
        ch_doc.to_dict.return_value = {
            "preamble": "Chapter 84 covers machinery",
            "chapter_title_he": "מכונות",
            "notes": [],
        }

        tariff_doc = MagicMock()
        tariff_doc.to_dict.return_value = {
            "heading": "8471",
            "description_he": "מחשבים",
            "description_en": "Computers",
            "hs_code": "8471.30.0000",
        }

        empty_stream = iter([])
        tariff_stream = iter([tariff_doc])

        def mock_collection(name):
            coll = MagicMock()
            if name == "chapter_notes":
                coll.document.return_value.get.return_value = ch_doc
            elif name == "tariff":
                coll.where.return_value.limit.return_value.stream.return_value = tariff_stream
            elif name == "tariff_uk":
                uk_doc = MagicMock()
                uk_doc.exists = True
                uk_doc.to_dict.return_value = mock_lookup.return_value
                coll.document.return_value.get.return_value = uk_doc
            else:
                coll.where.return_value.limit.return_value.stream.return_value = empty_stream
                coll.document.return_value.get.return_value = MagicMock(exists=False)
            return coll

        db.collection.side_effect = mock_collection

        from lib.justification_engine import build_justification_chain
        result = build_justification_chain(db, "8471.30.0000", "Laptop computer")

        steps = [s["step"] for s in result["chain"]]
        assert 9 in steps, f"Step 9 should be in chain, got steps: {steps}"
        step9 = [s for s in result["chain"] if s["step"] == 9][0]
        assert step9["source_type"] == "uk_tariff_verification"


# ═══════════════════════════════════════════
#  CROSS-CHECKER HOOK TEST
# ═══════════════════════════════════════════

class TestCrossCheckerHook:
    @patch("lib.uk_tariff_integration.compare_il_uk_classification")
    @patch("lib.cross_checker._call_chatgpt_check")
    @patch("lib.cross_checker._call_gemini_check")
    @patch("lib.cross_checker._call_claude_check")
    def test_uk_added_as_4th_source(self, mock_claude, mock_gemini, mock_chatgpt, mock_uk):
        mock_claude.return_value = {"hs_code": "84713000", "confidence": 0.9, "reason": "test"}
        mock_gemini.return_value = {"hs_code": "84713000", "confidence": 0.8, "reason": "test"}
        mock_chatgpt.return_value = {"hs_code": "84713000", "confidence": 0.8, "reason": "test"}
        mock_uk.return_value = {
            "match_level": "strong",
            "uk_code": "8471300000",
            "verification_note": "6-digit match",
            "similarity": 0.9,
        }

        db = MagicMock()
        from lib.cross_checker import cross_check_classification
        result = cross_check_classification(
            primary_hs="84713000",
            item_description="Laptop computer",
            origin_country="CN",
            api_key="test",
            gemini_key="test",
            openai_key="test",
            db=db,
        )
        assert "uk_tariff" in result.get("models", {}), "UK tariff should be in models"
