"""Tests for classification_identifier.py — Stage 1 parallel product identification."""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Ensure lib/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from lib.classification_identifier import (
    identify_product,
    make_candidate,
    _tokenize,
    _heading_from_code,
    _is_hebrew,
    _converge,
    _search_tree_hebrew,
    _search_tree_english,
    _search_chapter_notes,
    _search_firestore_tariff,
    _search_uk_tariff,
    _search_israeli_english_tariff,
    _SOURCE_WEIGHTS,
    _CONFIDENCE_HIGH,
    _CONFIDENCE_MEDIUM,
    _CONFIDENCE_LOW,
)


# ═══════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════

def _mock_tree_search(results):
    """Create a mock tree search function that returns given results."""
    def search(query, db=None):
        return results
    return search


def _mock_chapter_notes_db(chapters_data):
    """Create a mock Firestore db with chapter_notes collection."""
    db = MagicMock()
    docs = []
    for ch_id, data in chapters_data.items():
        doc = MagicMock()
        doc.id = ch_id
        doc.to_dict.return_value = data
        docs.append(doc)
    db.collection.return_value.stream.return_value = docs
    return db


# ═══════════════════════════════════════════
#  Test: Text Utilities
# ═══════════════════════════════════════════

class TestTokenize(unittest.TestCase):
    def test_hebrew_basic(self):
        tokens = _tokenize('ספה מרופדת')
        self.assertIn('ספה', tokens)
        self.assertIn('מרופדת', tokens)

    def test_english_basic(self):
        tokens = _tokenize('cooked peeled shrimp')
        self.assertIn('cooked', tokens)
        self.assertIn('peeled', tokens)
        self.assertIn('shrimp', tokens)

    def test_stop_words_removed(self):
        tokens = _tokenize('the sofa of type')
        self.assertNotIn('the', tokens)
        self.assertNotIn('of', tokens)

    def test_hebrew_prefix_stripping(self):
        tokens = _tokenize('והספה')
        # Should include both the original and stripped version
        self.assertTrue(any('ספה' in t for t in tokens))

    def test_empty_input(self):
        self.assertEqual(_tokenize(''), [])
        self.assertEqual(_tokenize(None), [])

    def test_mixed_language(self):
        tokens = _tokenize('שרימפס shrimp מבושל')
        self.assertIn('שרימפס', tokens)
        self.assertIn('shrimp', tokens)
        self.assertIn('מבושל', tokens)


class TestHeadingFromCode(unittest.TestCase):
    def test_10digit(self):
        self.assertEqual(_heading_from_code('9401610000'), '9401')

    def test_formatted(self):
        self.assertEqual(_heading_from_code('94.01.610000/5'), '9401')

    def test_short(self):
        self.assertEqual(_heading_from_code('94'), '94')

    def test_empty(self):
        self.assertEqual(_heading_from_code(''), '')


class TestIsHebrew(unittest.TestCase):
    def test_hebrew(self):
        self.assertTrue(_is_hebrew('ספה'))

    def test_english(self):
        self.assertFalse(_is_hebrew('sofa'))

    def test_mixed(self):
        self.assertTrue(_is_hebrew('שרימפס shrimp'))

    def test_empty(self):
        self.assertFalse(_is_hebrew(''))
        self.assertFalse(_is_hebrew(None))


# ═══════════════════════════════════════════
#  Test: make_candidate
# ═══════════════════════════════════════════

class TestMakeCandidate(unittest.TestCase):
    def test_basic(self):
        c = make_candidate('9401610000', 80.0, ['tree_he', 'tariff_index'],
                           desc_he='ספות', desc_en='Sofas')
        self.assertEqual(c['hs_code'], '9401610000')
        self.assertEqual(c['heading'], '9401')
        self.assertEqual(c['chapter'], '94')
        self.assertEqual(c['confidence'], 80.0)
        self.assertTrue(c['alive'])
        self.assertEqual(c['sources'], ['tree_he', 'tariff_index'])

    def test_short_code(self):
        c = make_candidate('94', 30.0, ['chapter_notes'])
        self.assertEqual(c['heading'], '94')
        self.assertEqual(c['chapter'], '94')


# ═══════════════════════════════════════════
#  Test: Convergence Logic
# ═══════════════════════════════════════════

class TestConvergence(unittest.TestCase):
    def test_three_sources_high_confidence(self):
        results = [
            {'heading': '9401', 'fc': '9401610000', 'desc_he': 'ספות', 'desc_en': 'Seats', 'source': 'tree_he', 'level': 5},
            {'heading': '9401', 'fc': '9401610000', 'desc_he': 'ספות', 'desc_en': 'Seats', 'source': 'tariff_index', 'score': 3, 'weight': 6},
            {'heading': '9401', 'fc': '9401600000', 'desc_en': 'Seats with wooden frames', 'source': 'uk_tariff', 'level': 4},
        ]
        candidates = _converge(results)
        top = candidates[0]
        self.assertEqual(top['heading'], '9401')
        self.assertEqual(top['confidence_level'], _CONFIDENCE_HIGH)
        self.assertEqual(top['source_count'], 3)
        self.assertFalse(top['needs_web_search'])

    def test_two_sources_medium_confidence(self):
        results = [
            {'heading': '2515', 'fc': '2515110000', 'desc_he': 'שיש', 'source': 'tree_he', 'level': 5},
            {'heading': '2515', 'fc': '2515120000', 'desc_en': 'Marble', 'source': 'tariff_index', 'score': 2},
        ]
        candidates = _converge(results)
        top = candidates[0]
        self.assertEqual(top['heading'], '2515')
        self.assertEqual(top['confidence_level'], _CONFIDENCE_MEDIUM)
        self.assertEqual(top['source_count'], 2)

    def test_single_source_low_confidence(self):
        results = [
            {'heading': '8703', 'fc': '8703800000', 'desc_en': 'Motor cars', 'source': 'uk_tariff', 'level': 4},
        ]
        candidates = _converge(results)
        top = candidates[0]
        self.assertEqual(top['confidence_level'], _CONFIDENCE_LOW)
        self.assertTrue(top['needs_web_search'])

    def test_conflicting_single_sources_flagged(self):
        results = [
            {'heading': '8703', 'fc': '8703800000', 'desc_en': 'Cars', 'source': 'uk_tariff', 'level': 4},
            {'heading': '8704', 'fc': '8704210000', 'desc_en': 'Trucks', 'source': 'tree_en', 'level': 4},
        ]
        candidates = _converge(results)
        # Both should be flagged for GIR analysis
        flagged = [c for c in candidates if c['needs_gir_analysis']]
        self.assertEqual(len(flagged), 2)

    def test_empty_results(self):
        self.assertEqual(_converge([]), [])

    def test_multiple_headings_sorted(self):
        results = [
            {'heading': '9401', 'fc': '9401610000', 'source': 'tree_he', 'level': 5},
            {'heading': '9401', 'fc': '9401610000', 'source': 'tariff_index', 'score': 3},
            {'heading': '9401', 'fc': '9401610000', 'source': 'uk_tariff', 'level': 4},
            {'heading': '9403', 'fc': '9403500000', 'source': 'tree_he', 'level': 5},
        ]
        candidates = _converge(results)
        # 9401 should rank first (3 sources vs 1)
        self.assertEqual(candidates[0]['heading'], '9401')


# ═══════════════════════════════════════════
#  Test: Individual Sources
# ═══════════════════════════════════════════

class TestSearchTreeHebrew(unittest.TestCase):
    def test_returns_results(self):
        mock_fn = _mock_tree_search([
            {'fc': '9401610000', 'level': 5, 'desc_he': 'ספות מרופדות', 'desc_en': 'Upholstered seats'},
            {'fc': '9401690000', 'level': 5, 'desc_he': 'ספות אחרות', 'desc_en': 'Other seats'},
        ])
        results = _search_tree_hebrew('ספה', mock_fn)
        self.assertTrue(len(results) >= 2)
        self.assertEqual(results[0]['source'], 'tree_he')
        self.assertEqual(results[0]['heading'], '9401')

    def test_skips_low_levels(self):
        mock_fn = _mock_tree_search([
            {'fc': 'XVII', 'level': 1, 'desc_he': 'חלק XVII', 'desc_en': 'Section XVII'},
            {'fc': '87', 'level': 2, 'desc_he': 'פרק 87', 'desc_en': 'Chapter 87'},
            {'fc': '8703800000', 'level': 5, 'desc_he': 'רכב', 'desc_en': 'Cars'},
        ])
        results = _search_tree_hebrew('רכב', mock_fn)
        # Should skip level 1 and 2
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['heading'], '8703')


class TestSearchChapterNotes(unittest.TestCase):
    def test_finds_matching_chapter(self):
        db = _mock_chapter_notes_db({
            'chapter_94': {
                'preamble': '',
                'preamble_en': 'This chapter covers furniture and parts thereof',
                'notes': ['ספות, כורסאות ומושבים'],
                'notes_en': ['Seats, chairs and sofas'],
                'inclusions': [],
                'exclusions': [],
                'chapter_title_he': 'רהיטים',
            },
            'chapter_73': {
                'preamble': '',
                'preamble_en': 'Articles of iron or steel',
                'notes': [],
                'notes_en': [],
                'inclusions': [],
                'exclusions': [],
                'chapter_title_he': 'פלדה',
            },
        })
        results = _search_chapter_notes('sofa seats', db)
        self.assertTrue(len(results) >= 1)
        chapters = [r['chapter'] for r in results]
        self.assertIn('94', chapters)

    def test_no_db(self):
        self.assertEqual(_search_chapter_notes('sofa', None), [])


class TestSearchUkTariff(unittest.TestCase):
    @patch('lib.classification_identifier.requests.get')
    def test_exact_match(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'data': {
                'attributes': {
                    'type': 'exact_match',
                    'entry': {'endpoint': 'commodities', 'id': '4015120000'},
                }
            }
        }
        mock_get.return_value = mock_resp

        results = _search_uk_tariff('rubber gloves')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['heading'], '4015')
        self.assertEqual(results[0]['source'], 'uk_tariff')

    @patch('lib.classification_identifier.requests.get')
    def test_exact_match_skips_uk_special_codes(self, mock_get):
        """UK chapters 98/99 are end-use codes — not real HS headings."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'data': {
                'attributes': {
                    'type': 'exact_match',
                    'entry': {'endpoint': 'commodities', 'id': '9880940000'},
                }
            }
        }
        mock_get.return_value = mock_resp

        results = _search_uk_tariff('sofa')
        self.assertEqual(results, [])

    @patch('lib.classification_identifier.requests.get')
    def test_fuzzy_match(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'data': {
                'attributes': {
                    'type': 'fuzzy_match',
                    'goods_nomenclature_match': {
                        'headings': [
                            {'_source': {
                                'goods_nomenclature_item_id': '9401000000',
                                'description_indexed': 'Seats (other than those of heading 9402)',
                            }},
                        ],
                        'commodities': [
                            {'_source': {
                                'goods_nomenclature_item_id': '9401610000',
                                'description_indexed': 'Upholstered seats, with wooden frames',
                            }},
                        ],
                        'chapters': [],
                    },
                }
            }
        }
        mock_get.return_value = mock_resp

        results = _search_uk_tariff('upholstered seat')
        self.assertTrue(len(results) >= 2)
        headings = [r['heading'] for r in results]
        self.assertTrue(all(h == '9401' for h in headings))
        self.assertEqual(results[0]['source'], 'uk_tariff')

    @patch('lib.classification_identifier.requests.get')
    def test_legacy_format(self, mock_get):
        """Old goods_nomenclature_search_results format (fallback)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'data': {
                'attributes': {
                    'goods_nomenclature_search_results': [
                        {
                            'goods_nomenclature': {
                                'attributes': {
                                    'goods_nomenclature_item_id': '9401610000',
                                    'description': 'Upholstered seats, with wooden frames',
                                }
                            }
                        }
                    ]
                }
            }
        }
        mock_get.return_value = mock_resp

        results = _search_uk_tariff('upholstered sofa')
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]['heading'], '9401')
        self.assertEqual(results[0]['source'], 'uk_tariff')

    @patch('lib.classification_identifier.requests.get')
    def test_handles_api_error(self, mock_get):
        mock_get.side_effect = Exception('timeout')
        results = _search_uk_tariff('sofa')
        self.assertEqual(results, [])

    def test_pure_hebrew_skipped(self):
        results = _search_uk_tariff('ספה מרופדת')
        self.assertEqual(results, [])


# ═══════════════════════════════════════════
#  Test: Source 6 — Israeli English Tariff
# ═══════════════════════════════════════════

class TestSearchIsraeliEnglishTariff(unittest.TestCase):
    @patch('lib.classification_identifier.requests.get')
    def test_json_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {'Content-Type': 'application/json'}
        mock_resp.json.return_value = [
            {
                'CustomsTaarifCode': '9401.61.0000',
                'EnglishDescription': 'Upholstered seats, with wooden frames',
                'HebrewDescription': 'ספות מרופדות',
            }
        ]
        mock_resp.text = ''
        mock_get.return_value = mock_resp

        results = _search_israeli_english_tariff('upholstered sofa')
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]['source'], 'il_en_tariff')
        self.assertEqual(results[0]['heading'], '9401')
        self.assertTrue(results[0]['desc_he'])  # Hebrew from Israeli source

    @patch('lib.classification_identifier.requests.get')
    def test_html_table_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {'Content-Type': 'text/html'}
        mock_resp.text = '''
        <table>
        <tr><td>9401.61.0000/5</td><td>Upholstered seats with wooden frames</td></tr>
        <tr><td>9403.50.0000/7</td><td>Wooden furniture for bedrooms</td></tr>
        </table>
        '''
        mock_resp.json.side_effect = ValueError
        mock_get.return_value = mock_resp

        results = _search_israeli_english_tariff('sofa')
        headings = [r['heading'] for r in results]
        self.assertIn('9401', headings)

    @patch('lib.classification_identifier.requests.get')
    def test_handles_error(self, mock_get):
        mock_get.side_effect = Exception('connection refused')
        results = _search_israeli_english_tariff('sofa')
        self.assertEqual(results, [])

    def test_pure_hebrew_skipped(self):
        results = _search_israeli_english_tariff('ספה מרופדת')
        self.assertEqual(results, [])

    def test_source_weight_is_higher(self):
        self.assertEqual(_SOURCE_WEIGHTS['il_en_tariff'], 1.5)
        self.assertEqual(_SOURCE_WEIGHTS['uk_tariff'], 1.0)


class TestIlEnHebrewAgreement(unittest.TestCase):
    """Test: if Israeli EN + Hebrew agree → automatic HIGH confidence."""

    def test_il_en_plus_tree_he_equals_high(self):
        """il_en_tariff + tree_he on same heading → HIGH even with only 2 sources."""
        results = [
            {'heading': '9401', 'fc': '9401610000', 'desc_he': 'ספות', 'source': 'tree_he', 'level': 5},
            {'heading': '9401', 'fc': '9401610000', 'desc_en': 'Upholstered seats', 'source': 'il_en_tariff', 'level': 5},
        ]
        candidates = _converge(results)
        top = candidates[0]
        self.assertEqual(top['heading'], '9401')
        self.assertEqual(top['confidence_level'], _CONFIDENCE_HIGH)
        self.assertTrue(top['il_en_hebrew_agree'])
        self.assertEqual(top['source_count'], 2)

    def test_il_en_plus_tariff_index_equals_high(self):
        """il_en_tariff + tariff_index on same heading → HIGH."""
        results = [
            {'heading': '2515', 'fc': '2515110000', 'desc_he': 'שיש', 'source': 'tariff_index', 'score': 2},
            {'heading': '2515', 'fc': '2515110000', 'desc_en': 'Marble', 'source': 'il_en_tariff', 'level': 5},
        ]
        candidates = _converge(results)
        self.assertEqual(candidates[0]['confidence_level'], _CONFIDENCE_HIGH)
        self.assertTrue(candidates[0]['il_en_hebrew_agree'])

    def test_il_en_alone_not_high(self):
        """il_en_tariff alone (no Hebrew source) → not automatically HIGH."""
        results = [
            {'heading': '8703', 'fc': '8703230000', 'desc_en': 'Motor cars', 'source': 'il_en_tariff', 'level': 5},
        ]
        candidates = _converge(results)
        self.assertEqual(candidates[0]['confidence_level'], _CONFIDENCE_LOW)
        self.assertFalse(candidates[0]['il_en_hebrew_agree'])

    def test_il_en_plus_uk_not_automatic_high(self):
        """il_en_tariff + uk_tariff (both English) → MEDIUM, not automatic HIGH."""
        results = [
            {'heading': '8471', 'fc': '8471300000', 'desc_en': 'ADP machines', 'source': 'il_en_tariff', 'level': 5},
            {'heading': '8471', 'fc': '8471300000', 'desc_en': 'ADP machines', 'source': 'uk_tariff', 'level': 5},
        ]
        candidates = _converge(results)
        self.assertEqual(candidates[0]['confidence_level'], _CONFIDENCE_MEDIUM)
        self.assertFalse(candidates[0]['il_en_hebrew_agree'])

    def test_weighted_score_higher_with_il_en(self):
        """Candidate with il_en_tariff should have higher weighted_source_count."""
        results = [
            {'heading': '9401', 'fc': '9401610000', 'source': 'tree_he', 'level': 5},
            {'heading': '9401', 'fc': '9401610000', 'source': 'il_en_tariff', 'level': 5},
        ]
        candidates = _converge(results)
        top = candidates[0]
        # 1.0 (tree_he) + 1.5 (il_en_tariff) = 2.5
        self.assertEqual(top['weighted_source_count'], 2.5)


# ═══════════════════════════════════════════
#  Test: 5 Required Products (integration)
# ═══════════════════════════════════════════

class TestProductIdentification(unittest.TestCase):
    """Test the 5 required products using mocked sources."""

    def _run_with_mocked_sources(self, product, tree_he_results, tree_en_results,
                                  chapter_results, tariff_results, uk_results,
                                  il_en_results=None):
        """Helper to run identify_product with all 6 sources mocked."""
        il_en_results = il_en_results or []
        all_results = (tree_he_results + tree_en_results + chapter_results +
                       tariff_results + uk_results + il_en_results)
        return _converge(all_results)

    def test_sofa_9401(self):
        """ספה (sofa) → 94.01"""
        candidates = self._run_with_mocked_sources(
            'ספה',
            tree_he_results=[
                {'heading': '9401', 'fc': '9401610000', 'desc_he': 'ספות מרופדות', 'desc_en': 'Upholstered seats', 'source': 'tree_he', 'level': 5},
            ],
            tree_en_results=[
                {'heading': '9401', 'fc': '9401710000', 'desc_en': 'Upholstered seats with metal frame', 'source': 'tree_en', 'level': 5},
            ],
            chapter_results=[
                {'heading': '9400', 'chapter': '94', 'hits': 2, 'total_tokens': 3, 'desc_he': 'רהיטים', 'source': 'chapter_notes'},
            ],
            tariff_results=[
                {'heading': '9401', 'fc': '9401610000', 'desc_he': 'ספות', 'source': 'tariff_index', 'score': 3, 'weight': 6},
            ],
            uk_results=[
                {'heading': '9401', 'fc': '9401610000', 'desc_en': 'Seats', 'source': 'uk_tariff', 'level': 4},
            ],
            il_en_results=[
                {'heading': '9401', 'fc': '9401610000', 'desc_en': 'Upholstered seats, with wooden frames', 'desc_he': 'ספות מרופדות', 'source': 'il_en_tariff', 'level': 5},
            ],
        )
        top = candidates[0]
        self.assertEqual(top['heading'], '9401')
        self.assertGreaterEqual(top['source_count'], 4)
        self.assertEqual(top['confidence_level'], _CONFIDENCE_HIGH)
        self.assertTrue(top['il_en_hebrew_agree'])

    def test_shrimp_1605(self):
        """שרימפס מקולף מבושל (cooked peeled shrimp) → 16.05"""
        candidates = self._run_with_mocked_sources(
            'שרימפס מקולף מבושל',
            tree_he_results=[
                {'heading': '1605', 'fc': '1605210000', 'desc_he': 'שרימפס', 'desc_en': 'Shrimps prepared', 'source': 'tree_he', 'level': 5},
            ],
            tree_en_results=[],
            chapter_results=[
                {'heading': '1600', 'chapter': '16', 'hits': 1, 'total_tokens': 3, 'desc_he': 'הכנות מבשר', 'source': 'chapter_notes'},
            ],
            tariff_results=[
                {'heading': '1605', 'fc': '1605210000', 'desc_he': 'שרימפס', 'source': 'tariff_index', 'score': 2, 'weight': 4},
            ],
            uk_results=[],
        )
        headings = [c['heading'] for c in candidates]
        self.assertIn('1605', headings)
        shrimp_cand = next(c for c in candidates if c['heading'] == '1605')
        self.assertGreaterEqual(shrimp_cand['source_count'], 2)

    def test_computer_8471(self):
        """יחידה אוטומטית לעיבוד נתונים (computer) → 84.71"""
        candidates = self._run_with_mocked_sources(
            'יחידה אוטומטית לעיבוד נתונים',
            tree_he_results=[
                {'heading': '8471', 'fc': '8471300000', 'desc_he': 'מכונות אוטומטיות לעיבוד נתונים', 'desc_en': 'ADP machines', 'source': 'tree_he', 'level': 5},
            ],
            tree_en_results=[
                {'heading': '8471', 'fc': '8471300000', 'desc_en': 'ADP machines, portable', 'source': 'tree_en', 'level': 5},
            ],
            chapter_results=[
                {'heading': '8400', 'chapter': '84', 'hits': 2, 'total_tokens': 4, 'desc_he': 'מכונות', 'source': 'chapter_notes'},
            ],
            tariff_results=[
                {'heading': '8471', 'fc': '8471300000', 'desc_he': 'מכונות לעיבוד נתונים', 'source': 'tariff_index', 'score': 4, 'weight': 8},
            ],
            uk_results=[],
        )
        top = candidates[0]
        self.assertEqual(top['heading'], '8471')
        self.assertGreaterEqual(top['source_count'], 3)

    def test_marble_2515(self):
        """שיש גולמי (raw marble) → 25.15"""
        candidates = self._run_with_mocked_sources(
            'שיש גולמי',
            tree_he_results=[
                {'heading': '2515', 'fc': '2515110000', 'desc_he': 'שיש גולמי', 'desc_en': 'Marble, crude', 'source': 'tree_he', 'level': 5},
            ],
            tree_en_results=[],
            chapter_results=[],
            tariff_results=[
                {'heading': '2515', 'fc': '2515110000', 'desc_he': 'שיש', 'source': 'tariff_index', 'score': 2, 'weight': 5},
            ],
            uk_results=[
                {'heading': '2515', 'fc': '2515110000', 'desc_en': 'Marble and travertine, crude', 'source': 'uk_tariff', 'level': 5},
            ],
        )
        headings = [c['heading'] for c in candidates]
        self.assertIn('2515', headings)
        marble = next(c for c in candidates if c['heading'] == '2515')
        self.assertGreaterEqual(marble['source_count'], 2)

    def test_vehicle_8703(self):
        """רכב פרטי (private vehicle) → 87.03"""
        candidates = self._run_with_mocked_sources(
            'רכב פרטי',
            tree_he_results=[
                {'heading': '8703', 'fc': '8703230000', 'desc_he': 'רכב נוסעים', 'desc_en': 'Motor cars', 'source': 'tree_he', 'level': 5},
            ],
            tree_en_results=[
                {'heading': '8703', 'fc': '8703230000', 'desc_en': 'Motor cars for transport of persons', 'source': 'tree_en', 'level': 5},
            ],
            chapter_results=[
                {'heading': '8700', 'chapter': '87', 'hits': 1, 'total_tokens': 2, 'desc_he': 'כלי רכב', 'source': 'chapter_notes'},
            ],
            tariff_results=[
                {'heading': '8703', 'fc': '8703230000', 'desc_he': 'רכב', 'source': 'tariff_index', 'score': 2, 'weight': 4},
            ],
            uk_results=[
                {'heading': '8703', 'fc': '8703230000', 'desc_en': 'Motor cars', 'source': 'uk_tariff', 'level': 5},
            ],
            il_en_results=[
                {'heading': '8703', 'fc': '8703230000', 'desc_en': 'Motor cars for transport of persons', 'source': 'il_en_tariff', 'level': 5},
            ],
        )
        top = candidates[0]
        self.assertEqual(top['heading'], '8703')
        self.assertEqual(top['confidence_level'], _CONFIDENCE_HIGH)
        self.assertGreaterEqual(top['source_count'], 5)
        self.assertTrue(top['il_en_hebrew_agree'])


# ═══════════════════════════════════════════
#  Test: Edge Cases
# ═══════════════════════════════════════════

class TestEdgeCases(unittest.TestCase):
    def test_empty_product(self):
        result = identify_product('', skip_uk=True)
        self.assertEqual(result, [])

    def test_none_product(self):
        result = identify_product(None, skip_uk=True)
        self.assertEqual(result, [])

    def test_whitespace_product(self):
        result = identify_product('   ', skip_uk=True)
        self.assertEqual(result, [])

    def test_candidate_has_required_fields(self):
        """Verify HSCandidate structure is compatible with elimination_engine."""
        c = make_candidate('9401610000', 80.0, ['tree_he'], desc_he='ספות')
        required_fields = [
            'hs_code', 'heading', 'chapter', 'subheading', 'section',
            'confidence', 'source', 'description', 'description_en',
            'description_he', 'duty_rate', 'alive', 'elimination_reason',
            'eliminated_at_level',
        ]
        for field in required_fields:
            self.assertIn(field, c, f'Missing field: {field}')


# ═══════════════════════════════════════════
#  Test: Source count thresholds
# ═══════════════════════════════════════════

class TestConfidenceThresholds(unittest.TestCase):
    def test_six_sources_high(self):
        results = [
            {'heading': '9401', 'fc': '9401610000', 'source': 'tree_he', 'level': 5},
            {'heading': '9401', 'fc': '9401610000', 'source': 'tree_en', 'level': 5},
            {'heading': '9401', 'fc': '9401610000', 'source': 'chapter_notes'},
            {'heading': '9401', 'fc': '9401610000', 'source': 'tariff_index', 'score': 3},
            {'heading': '9401', 'fc': '9401610000', 'source': 'uk_tariff', 'level': 5},
            {'heading': '9401', 'fc': '9401610000', 'source': 'il_en_tariff', 'level': 5},
        ]
        candidates = _converge(results)
        self.assertEqual(candidates[0]['confidence_level'], _CONFIDENCE_HIGH)
        self.assertEqual(candidates[0]['source_count'], 6)
        self.assertTrue(candidates[0]['il_en_hebrew_agree'])

    def test_exactly_three_sources_high(self):
        results = [
            {'heading': '2515', 'fc': '2515110000', 'source': 'tree_he', 'level': 5},
            {'heading': '2515', 'fc': '2515110000', 'source': 'tariff_index', 'score': 2},
            {'heading': '2515', 'fc': '2515110000', 'source': 'uk_tariff', 'level': 5},
        ]
        candidates = _converge(results)
        self.assertEqual(candidates[0]['confidence_level'], _CONFIDENCE_HIGH)

    def test_exactly_two_sources_medium(self):
        results = [
            {'heading': '8471', 'fc': '8471300000', 'source': 'tree_he', 'level': 5},
            {'heading': '8471', 'fc': '8471300000', 'source': 'tariff_index', 'score': 3},
        ]
        candidates = _converge(results)
        self.assertEqual(candidates[0]['confidence_level'], _CONFIDENCE_MEDIUM)

    def test_one_source_low(self):
        results = [
            {'heading': '7326', 'fc': '7326900000', 'source': 'tree_he', 'level': 5},
        ]
        candidates = _converge(results)
        self.assertEqual(candidates[0]['confidence_level'], _CONFIDENCE_LOW)
        self.assertTrue(candidates[0]['needs_web_search'])

    def test_max_results_capped(self):
        results = []
        for i in range(20):
            h = str(i).zfill(4)
            results.append({'heading': h, 'fc': h + '000000', 'source': 'tree_he', 'level': 5})
        candidates = _converge(results)
        self.assertLessEqual(len(candidates), 15)


if __name__ == '__main__':
    unittest.main()
