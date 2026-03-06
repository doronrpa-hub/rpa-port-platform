"""Tests for unified index search functions."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestTokenizer:
    """Test the tokenizer used by search functions."""

    def test_basic_english(self):
        from lib._unified_search import _tok
        tokens = _tok("Steel storage boxes")
        assert "steel" in tokens
        assert "storage" in tokens
        assert "boxes" in tokens

    def test_basic_hebrew(self):
        from lib._unified_search import _tok
        tokens = _tok("קופסאות אחסון מפלדה")
        assert "קופסאות" in tokens
        assert "אחסון" in tokens
        assert "מפלדה" in tokens

    def test_hebrew_prefix_stripping(self):
        from lib._unified_search import _tok
        tokens = _tok("מפלדה")
        assert "מפלדה" in tokens
        assert "פלדה" in tokens  # prefix-stripped

    def test_compound_prefix_stripping(self):
        from lib._unified_search import _tok
        tokens = _tok("והמכולות")
        assert "והמכולות" in tokens
        assert "מכולות" in tokens  # "וה" prefix stripped

    def test_stop_words_removed(self):
        from lib._unified_search import _tok
        tokens = _tok("the steel of the box")
        assert "the" not in tokens
        assert "of" not in tokens
        assert "steel" in tokens
        assert "box" in tokens

    def test_hebrew_stop_words_removed(self):
        from lib._unified_search import _tok
        tokens = _tok("את הפלדה של הקופסה")
        assert "את" not in tokens
        assert "של" not in tokens

    def test_empty_input(self):
        from lib._unified_search import _tok
        assert _tok("") == []
        assert _tok(None) == []

    def test_dedup(self):
        from lib._unified_search import _tok
        tokens = _tok("steel steel steel")
        assert tokens.count("steel") == 1

    def test_min_length(self):
        from lib._unified_search import _tok
        tokens = _tok("a b cd ef gh")
        assert "a" not in tokens  # too short
        assert "b" not in tokens
        assert "cd" in tokens
        assert "ef" in tokens


class TestSearchWord:
    """Test search_word function."""

    def test_returns_list(self):
        from lib._unified_search import search_word
        result = search_word("nonexistent_word_xyz")
        assert isinstance(result, list)

    def test_entry_format(self):
        from lib._unified_search import search_word, _ensure_index
        _ensure_index()
        # Find any word that has entries
        from lib._unified_index import WORD_INDEX
        if WORD_INDEX:
            word = next(iter(WORD_INDEX))
            result = search_word(word)
            if result:
                entry = result[0]
                assert isinstance(entry, (tuple, list))
                assert len(entry) == 3  # (hs_code, source, weight)

    def test_prefix_strip_fallback(self):
        from lib._unified_search import search_word, _ensure_index
        _ensure_index()
        from lib._unified_index import WORD_INDEX
        # Find a word that's in the index
        for w in WORD_INDEX:
            if len(w) > 3:
                # Prepend Hebrew prefix
                prefixed = "\u05d4" + w  # ה + word
                result = search_word(prefixed)
                # Should find via prefix stripping
                assert isinstance(result, list)
                break


class TestSearchPhrase:
    """Test search_phrase function."""

    def test_returns_list_of_dicts(self):
        from lib._unified_search import search_phrase
        result = search_phrase("some query text")
        assert isinstance(result, list)

    def test_result_format(self):
        from lib._unified_search import search_phrase, _ensure_index
        _ensure_index()
        from lib._unified_index import WORD_INDEX
        if WORD_INDEX:
            # Use a word we know exists
            word = next(iter(WORD_INDEX))
            result = search_phrase(word, min_score=1)
            if result:
                r = result[0]
                assert "hs_code" in r
                assert "score" in r
                assert "weight" in r
                assert "sources" in r

    def test_min_score_filtering(self):
        from lib._unified_search import search_phrase
        # High min_score should return fewer results
        r_low = search_phrase("some words", min_score=1)
        r_high = search_phrase("some words", min_score=5)
        assert len(r_high) <= len(r_low)

    def test_max_20_results(self):
        from lib._unified_search import search_phrase
        result = search_phrase("a b c d e f g h i j k l m n o p", min_score=1)
        assert len(result) <= 20

    def test_empty_input(self):
        from lib._unified_search import search_phrase
        assert search_phrase("") == []
        assert search_phrase("the of and") == []  # all stop words


class TestFindTariffCodes:
    """Test find_tariff_codes function."""

    def test_returns_list(self):
        from lib._unified_search import find_tariff_codes
        result = find_tariff_codes("steel boxes")
        assert isinstance(result, list)

    def test_result_has_metadata(self):
        from lib._unified_search import find_tariff_codes, _ensure_index
        _ensure_index()
        from lib._unified_index import WORD_INDEX
        if WORD_INDEX:
            word = next(iter(WORD_INDEX))
            result = find_tariff_codes(word, min_score=1)
            if result:
                r = result[0]
                assert "hs_code" in r
                assert "description_he" in r
                assert "duty_rate" in r
                assert "purchase_tax" in r

    def test_filters_non_tariff_sources(self):
        from lib._unified_search import find_tariff_codes
        # ORD, FW, PR, EU, CAL sources should be excluded
        result = find_tariff_codes("customs ordinance article", min_score=1)
        for r in result:
            for src in r.get("sources", []):
                assert src in ("T", "CN", "CD", "FI", "CH", "DC", "C98"), \
                    f"Non-tariff source {src} leaked into find_tariff_codes"

    def test_empty_input(self):
        from lib._unified_search import find_tariff_codes
        assert find_tariff_codes("") == []


class TestGetHeadingSubcodes:
    """Test get_heading_subcodes function."""

    def test_returns_list(self):
        from lib._unified_search import get_heading_subcodes
        result = get_heading_subcodes("8471")
        assert isinstance(result, list)

    def test_result_format(self):
        from lib._unified_search import get_heading_subcodes, _ensure_index
        _ensure_index()
        from lib._unified_index import HEADING_MAP
        if HEADING_MAP:
            heading = next(iter(HEADING_MAP))
            result = get_heading_subcodes(heading)
            if result:
                r = result[0]
                assert "hs_code" in r
                assert "description_he" in r
                assert "duty_rate" in r

    def test_nonexistent_heading(self):
        from lib._unified_search import get_heading_subcodes
        result = get_heading_subcodes("0000")
        assert result == []

    def test_strips_dots(self):
        from lib._unified_search import get_heading_subcodes
        # Should handle "84.71" same as "8471"
        r1 = get_heading_subcodes("8471")
        r2 = get_heading_subcodes("84.71")
        assert r1 == r2


class TestIndexLoaded:
    """Test index_loaded function."""

    def test_returns_bool(self):
        from lib._unified_search import index_loaded
        result = index_loaded()
        assert isinstance(result, bool)


class TestBrokerEngineUnifiedWiring:
    """Test that broker_engine can use unified search."""

    def test_ensure_unified_no_crash(self):
        from lib.broker_engine import _ensure_unified
        _ensure_unified()  # Should not raise

    def test_unified_to_candidate_format(self):
        from lib.broker_engine import _unified_to_candidate
        result = _unified_to_candidate({
            "hs_code": "8525.8100",
            "score": 3,
            "weight": 15,
            "sources": ["T", "CN"],
            "description_he": "מצלמות טלוויזיה",
            "description_en": "Television cameras",
            "duty_rate": "free",
        }, "unified_he")
        assert result["hs_code"] == "8525.8100"
        assert 20 <= result["confidence"] <= 95
        assert result["source"] == "unified_he"
        assert result["description"] == "מצלמות טלוויזיה"
        assert result["duty_rate"] == "free"

    def test_search_via_unified_empty(self):
        from lib.broker_engine import _ensure_unified, _UNIFIED_AVAILABLE
        from lib.broker_engine import _search_via_unified
        _ensure_unified()
        # With empty descriptions
        result = _search_via_unified("", "", {})
        assert result is None

    def test_search_via_unified_returns_candidates(self):
        from lib.broker_engine import _ensure_unified, _UNIFIED_AVAILABLE
        from lib.broker_engine import _search_via_unified
        _ensure_unified()
        if _UNIFIED_AVAILABLE:
            # Search for something that should match chapter expertise
            result = _search_via_unified("כלי רכב ממונעים", "motor vehicles", {})
            if result:
                assert isinstance(result, list)
                assert len(result) <= 10
                for c in result:
                    assert "hs_code" in c
                    assert "confidence" in c
                    assert "source" in c


class TestBuilderTokenize:
    """Test the builder's tokenize function."""

    def test_matches_search_tokenize(self):
        """Builder and search must tokenize identically."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from build_unified_index import _tokenize as builder_tok
        from lib._unified_search import _tok as search_tok

        test_cases = [
            "Steel storage boxes",
            "קופסאות אחסון מפלדה",
            "drone UAV רחפן",
            "tire pneumatic צמיג",
        ]
        for text in test_cases:
            b_tokens = builder_tok(text)
            s_tokens = search_tok(text)
            # Search deduplicates, builder doesn't always — compare as sets
            assert set(b_tokens) == set(s_tokens), \
                f"Tokenizer mismatch for '{text}': builder={b_tokens}, search={s_tokens}"
