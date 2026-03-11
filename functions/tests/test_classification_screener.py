"""Tests for classification_screener.py — Stage 2 screening questions."""

import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from lib.classification_screener import (
    screen_candidates,
    _load_chapter_notes,
    _format_chapter_notes_for_prompt,
    _build_user_prompt,
    _parse_ai_response,
    _cross_check,
    _normalize_key,
    _SYSTEM_PROMPT,
    _KNOWN_ATTRIBUTE_ALIASES,
    _ATTR_KEY_RE,
    _MAX_CANDIDATES,
)


# ═══════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════

def _make_candidate(heading, confidence_level='MEDIUM', sources=None,
                    desc_en='', desc_he='', chapter=None):
    """Build a minimal candidate dict matching identify_product() output."""
    ch = chapter or heading[:2]
    return {
        'hs_code': heading.ljust(10, '0'),
        'heading': heading[:4],
        'chapter': ch,
        'confidence': 60.0,
        'confidence_level': confidence_level,
        'sources': sources or ['tree_he', 'tariff_index'],
        'description': desc_en,
        'description_en': desc_en,
        'description_he': desc_he,
        'source_count': len(sources) if sources else 2,
    }


def _make_ai_response(questions):
    """Build a valid AI JSON response string."""
    return json.dumps({'questions': questions})


def _mock_chapter_notes_db(chapters_data):
    """Create a mock Firestore db returning chapter_notes docs."""
    db = MagicMock()

    def get_doc(doc_id):
        mock_doc = MagicMock()
        # doc_id like 'chapter_94'
        if doc_id in chapters_data:
            mock_doc.exists = True
            mock_doc.to_dict.return_value = chapters_data[doc_id]
        else:
            mock_doc.exists = False
        return mock_doc

    db.collection.return_value.document.return_value.get.side_effect = (
        lambda: get_doc(db.collection.return_value.document.call_args[0][0])
    )

    # Simpler approach: make document().get() return based on call args
    def doc_getter(doc_id):
        mock_ref = MagicMock()
        mock_doc = MagicMock()
        if doc_id in chapters_data:
            mock_doc.exists = True
            mock_doc.to_dict.return_value = chapters_data[doc_id]
        else:
            mock_doc.exists = False
        mock_ref.get.return_value = mock_doc
        return mock_ref

    db.collection.return_value.document.side_effect = doc_getter
    return db


SAMPLE_CHAPTER_94 = {
    'preamble': '',
    'preamble_en': 'This chapter covers furniture and parts thereof',
    'notes': ['ספות, כורסאות ומושבים'],
    'notes_en': ['Seats and parts thereof', 'Heading 94.01 covers seats'],
    'inclusions': ['upholstered seats', 'office chairs', 'car seats'],
    'exclusions': ['mattresses (94.04)', 'lighting (94.05)'],
    'definitions': [],
}

SAMPLE_CHAPTER_73 = {
    'preamble': '',
    'preamble_en': 'Articles of iron or steel',
    'notes': [],
    'notes_en': ['This chapter does not cover articles of cast iron'],
    'inclusions': ['storage boxes', 'wire products'],
    'exclusions': ['hand tools (chapter 82)'],
    'definitions': [],
}


# ═══════════════════════════════════════════
#  Test: _normalize_key
# ═══════════════════════════════════════════

class TestNormalizeKey(unittest.TestCase):
    def test_english_aliases(self):
        self.assertEqual(_normalize_key('material'), 'material')
        self.assertEqual(_normalize_key('made_of'), 'material')
        self.assertEqual(_normalize_key('composition'), 'material')

    def test_hebrew_aliases(self):
        self.assertEqual(_normalize_key('חומר'), 'material')
        self.assertEqual(_normalize_key('שימוש'), 'primary_function')
        self.assertEqual(_normalize_key('משקל'), 'gross_weight_kg')

    def test_function_aliases(self):
        self.assertEqual(_normalize_key('use'), 'primary_function')
        self.assertEqual(_normalize_key('purpose'), 'primary_function')
        self.assertEqual(_normalize_key('ייעוד'), 'primary_function')

    def test_specific_canonical_forms(self):
        """New canonical forms are more specific than old generic ones."""
        self.assertEqual(_normalize_key('weight'), 'gross_weight_kg')
        self.assertEqual(_normalize_key('power'), 'power_watts')
        self.assertEqual(_normalize_key('origin'), 'country_of_origin')
        self.assertEqual(_normalize_key('motor'), 'engine_type')
        self.assertEqual(_normalize_key('cc'), 'engine_cc')
        self.assertEqual(_normalize_key('frequency'), 'operating_frequency')
        self.assertEqual(_normalize_key('capacity'), 'capacity_liters')
        self.assertEqual(_normalize_key('form'), 'physical_form')

    def test_unknown_passthrough(self):
        """Unknown keys pass through unchanged — open set."""
        self.assertEqual(_normalize_key('color'), 'color')
        self.assertEqual(_normalize_key('CUSTOM'), 'custom')
        self.assertEqual(_normalize_key('fiber_content'), 'fiber_content')
        self.assertEqual(_normalize_key('seating_capacity'), 'seating_capacity')

    def test_case_insensitive(self):
        self.assertEqual(_normalize_key('Material'), 'material')
        self.assertEqual(_normalize_key('WEIGHT'), 'gross_weight_kg')

    def test_whitespace_stripped(self):
        self.assertEqual(_normalize_key('  material  '), 'material')

    def test_domain_specific_keys_exist(self):
        """Domain-specific aliases for vehicles, food, textiles."""
        self.assertEqual(_normalize_key('fuel_type'), 'fuel_type')
        self.assertEqual(_normalize_key('seating_capacity'), 'seating_capacity')
        self.assertEqual(_normalize_key('species'), 'species')
        self.assertEqual(_normalize_key('fiber_content'), 'fiber_content')


# ═══════════════════════════════════════════
#  Test: _load_chapter_notes
# ═══════════════════════════════════════════

class TestLoadChapterNotes(unittest.TestCase):
    def test_loads_existing_chapters(self):
        db = _mock_chapter_notes_db({
            'chapter_94': SAMPLE_CHAPTER_94,
            'chapter_73': SAMPLE_CHAPTER_73,
        })
        result = _load_chapter_notes(db, ['94', '73'])
        self.assertIn('94', result)
        self.assertIn('73', result)

    def test_skips_missing_chapters(self):
        db = _mock_chapter_notes_db({
            'chapter_94': SAMPLE_CHAPTER_94,
        })
        result = _load_chapter_notes(db, ['94', '99'])
        self.assertIn('94', result)
        self.assertNotIn('99', result)

    def test_no_db_returns_empty(self):
        result = _load_chapter_notes(None, ['94'])
        self.assertEqual(result, {})

    def test_pads_single_digit_chapters(self):
        db = _mock_chapter_notes_db({
            'chapter_02': {'preamble': 'Meat', 'notes': []},
        })
        result = _load_chapter_notes(db, ['2'])
        self.assertIn('02', result)

    def test_caps_at_max_chapters(self):
        """Should not load more than _MAX_CHAPTERS."""
        db = _mock_chapter_notes_db({
            f'chapter_{str(i).zfill(2)}': {'preamble': f'Ch {i}'}
            for i in range(1, 10)
        })
        result = _load_chapter_notes(db, [str(i) for i in range(1, 10)])
        self.assertLessEqual(len(result), 5)


# ═══════════════════════════════════════════
#  Test: _format_chapter_notes_for_prompt
# ═══════════════════════════════════════════

class TestFormatChapterNotes(unittest.TestCase):
    def test_includes_preamble(self):
        text = _format_chapter_notes_for_prompt({'94': SAMPLE_CHAPTER_94})
        self.assertIn('furniture', text)

    def test_includes_inclusions(self):
        text = _format_chapter_notes_for_prompt({'94': SAMPLE_CHAPTER_94})
        self.assertIn('upholstered seats', text)

    def test_includes_exclusions(self):
        text = _format_chapter_notes_for_prompt({'94': SAMPLE_CHAPTER_94})
        self.assertIn('mattresses', text)

    def test_multiple_chapters(self):
        notes = {'94': SAMPLE_CHAPTER_94, '73': SAMPLE_CHAPTER_73}
        text = _format_chapter_notes_for_prompt(notes)
        self.assertIn('Chapter 73', text)
        self.assertIn('Chapter 94', text)

    def test_empty_notes(self):
        text = _format_chapter_notes_for_prompt({})
        self.assertEqual(text, '')

    def test_skips_empty_fields(self):
        sparse = {'99': {'preamble': '', 'notes': [], 'inclusions': []}}
        text = _format_chapter_notes_for_prompt(sparse)
        # Only header, no content → should be empty
        self.assertEqual(text, '')


# ═══════════════════════════════════════════
#  Test: _build_user_prompt
# ═══════════════════════════════════════════

class TestBuildUserPrompt(unittest.TestCase):
    def test_includes_product(self):
        prompt = _build_user_prompt('sofa', [_make_candidate('9401')], '', {})
        self.assertIn('sofa', prompt)

    def test_includes_candidate_headings(self):
        cands = [_make_candidate('9401', desc_en='Seats'),
                 _make_candidate('9403', desc_en='Furniture')]
        prompt = _build_user_prompt('sofa', cands, '', {})
        self.assertIn('9401', prompt)
        self.assertIn('9403', prompt)

    def test_includes_chapter_notes(self):
        prompt = _build_user_prompt('sofa', [_make_candidate('9401')],
                                    'Chapter 94 covers furniture', {})
        self.assertIn('Chapter 94 covers furniture', prompt)

    def test_includes_known_attributes(self):
        prompt = _build_user_prompt('sofa', [_make_candidate('9401')], '',
                                    {'material': 'wood', 'weight': '15kg'})
        self.assertIn('material: wood', prompt)
        self.assertIn('weight: 15kg', prompt)
        self.assertIn('Do NOT ask', prompt)

    def test_empty_known_attributes(self):
        prompt = _build_user_prompt('sofa', [_make_candidate('9401')], '', {})
        self.assertNotIn('Already known', prompt)


# ═══════════════════════════════════════════
#  Test: _parse_ai_response
# ═══════════════════════════════════════════

class TestParseAiResponse(unittest.TestCase):
    def test_valid_json(self):
        raw = _make_ai_response([{
            'question': 'What material is the frame?',
            'question_he': 'מאיזה חומר המסגרת?',
            'attribute_key': 'material',
            'distinguishes_between': ['9401', '9403'],
            'why': 'Wood frame → 9401, metal → 9403',
        }])
        result = _parse_ai_response(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['attribute_key'], 'material')
        self.assertEqual(result[0]['distinguishes_between'], ['9401', '9403'])

    def test_strips_code_fences(self):
        raw = '```json\n' + _make_ai_response([{
            'question': 'What is it made of?',
            'attribute_key': 'material',
            'distinguishes_between': ['9401', '7326'],
        }]) + '\n```'
        result = _parse_ai_response(raw)
        self.assertEqual(len(result), 1)

    def test_empty_questions(self):
        raw = _make_ai_response([])
        result = _parse_ai_response(raw)
        self.assertEqual(result, [])

    def test_none_input(self):
        self.assertEqual(_parse_ai_response(None), [])

    def test_invalid_json(self):
        self.assertEqual(_parse_ai_response('not json at all'), [])

    def test_caps_at_five(self):
        questions = [
            {'question': f'Q{i}?', 'attribute_key': 'material',
             'distinguishes_between': ['9401', '9403']}
            for i in range(8)
        ]
        result = _parse_ai_response(_make_ai_response(questions))
        self.assertLessEqual(len(result), 5)

    def test_skips_invalid_questions(self):
        raw = _make_ai_response([
            {'question': '', 'attribute_key': 'material',
             'distinguishes_between': ['9401']},  # empty question
            {'question': 'Valid?', 'attribute_key': '',
             'distinguishes_between': ['9401']},  # empty key
            {'question': 'Good one?', 'attribute_key': 'gross_weight_kg',
             'distinguishes_between': ['9401', '7326']},  # valid
        ])
        result = _parse_ai_response(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['attribute_key'], 'gross_weight_kg')

    def test_accepts_domain_specific_keys(self):
        """Open set: any valid snake_case key is accepted."""
        raw = _make_ai_response([
            {'question': 'Fuel?', 'attribute_key': 'fuel_type',
             'distinguishes_between': ['8703', '8704']},
            {'question': 'Seats?', 'attribute_key': 'seating_capacity',
             'distinguishes_between': ['8703', '8704']},
            {'question': 'Fiber?', 'attribute_key': 'fiber_content',
             'distinguishes_between': ['5208', '5209']},
        ])
        result = _parse_ai_response(raw)
        self.assertEqual(len(result), 3)
        keys = [q['attribute_key'] for q in result]
        self.assertEqual(keys, ['fuel_type', 'seating_capacity', 'fiber_content'])

    def test_rejects_non_snake_case_keys(self):
        """Keys with spaces, special chars, or uppercase are rejected."""
        raw = _make_ai_response([
            {'question': 'Q?', 'attribute_key': 'Fuel Type',
             'distinguishes_between': ['8703', '8704']},  # has space+uppercase → auto-fixed
        ])
        result = _parse_ai_response(raw)
        # 'Fuel Type' → 'fuel_type' after auto-fix (space→underscore, lowercase)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['attribute_key'], 'fuel_type')

    def test_autofixes_spaces_to_underscores(self):
        raw = _make_ai_response([
            {'question': 'Q?', 'attribute_key': 'engine displacement',
             'distinguishes_between': ['8703', '8704']},
        ])
        result = _parse_ai_response(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['attribute_key'], 'engine_displacement')

    def test_rejects_key_over_30_chars(self):
        raw = _make_ai_response([
            {'question': 'Q?', 'attribute_key': 'a' * 31,
             'distinguishes_between': ['9401', '9403']},
        ])
        result = _parse_ai_response(raw)
        self.assertEqual(len(result), 0)

    def test_rejects_key_starting_with_digit(self):
        raw = _make_ai_response([
            {'question': 'Q?', 'attribute_key': '3phase_motor',
             'distinguishes_between': ['8501', '8502']},
        ])
        result = _parse_ai_response(raw)
        self.assertEqual(len(result), 0)

    def test_normalizes_heading_codes(self):
        raw = _make_ai_response([{
            'question': 'Q?',
            'attribute_key': 'material',
            'distinguishes_between': ['94010000', '73260000'],
        }])
        result = _parse_ai_response(raw)
        self.assertEqual(result[0]['distinguishes_between'], ['9401', '7326'])

    def test_extracts_json_from_text(self):
        raw = 'Here is my analysis:\n{"questions": [{"question": "Q?", "attribute_key": "physical_form", "distinguishes_between": ["9401", "9403"]}]}\nEnd.'
        result = _parse_ai_response(raw)
        self.assertEqual(len(result), 1)


# ═══════════════════════════════════════════
#  Test: _cross_check
# ═══════════════════════════════════════════

class TestCrossCheck(unittest.TestCase):
    def _q(self, attr_key, question='Q?'):
        return {
            'question': question,
            'question_he': '',
            'attribute_key': attr_key,
            'distinguishes_between': ['9401', '9403'],
            'why': '',
        }

    def test_all_answered(self):
        questions = [self._q('material'), self._q('primary_function')]
        known = {'material': 'wood', 'primary_function': 'seating'}
        answered, missing = _cross_check(questions, known)
        self.assertEqual(len(answered), 2)
        self.assertEqual(len(missing), 0)

    def test_none_answered(self):
        questions = [self._q('material'), self._q('primary_function')]
        answered, missing = _cross_check(questions, {})
        self.assertEqual(len(answered), 0)
        self.assertEqual(len(missing), 2)

    def test_partial_answered(self):
        questions = [self._q('material'), self._q('primary_function'),
                     self._q('gross_weight_kg')]
        known = {'material': 'steel'}
        answered, missing = _cross_check(questions, known)
        self.assertEqual(len(answered), 1)
        self.assertEqual(answered['material'], 'steel')
        self.assertEqual(len(missing), 2)

    def test_alias_matching(self):
        """'made_of' in known should match 'material' attribute_key."""
        questions = [self._q('material')]
        known = {'made_of': 'plastic'}
        answered, missing = _cross_check(questions, known)
        self.assertEqual(len(answered), 1)
        self.assertIn('material', answered)

    def test_hebrew_alias_matching(self):
        """Hebrew key 'חומר' should match 'material'."""
        questions = [self._q('material')]
        known = {'חומר': 'פלסטיק'}
        answered, missing = _cross_check(questions, known)
        self.assertEqual(len(answered), 1)

    def test_empty_value_not_counted(self):
        """Empty string values should not count as answered."""
        questions = [self._q('material')]
        known = {'material': ''}
        answered, missing = _cross_check(questions, known)
        self.assertEqual(len(answered), 0)
        self.assertEqual(len(missing), 1)

    def test_no_known_attrs(self):
        questions = [self._q('material')]
        answered, missing = _cross_check(questions, None)
        self.assertEqual(len(answered), 0)
        self.assertEqual(len(missing), 1)


# ═══════════════════════════════════════════
#  Test: screen_candidates (integration)
# ═══════════════════════════════════════════

class TestScreenCandidates(unittest.TestCase):
    def test_empty_product(self):
        result = screen_candidates('', [])
        self.assertEqual(result['confidence'], 'NEEDS_INFO')
        self.assertFalse(result['ready_for_traversal'])
        self.assertEqual(result['missing'], [])

    def test_empty_candidates(self):
        result = screen_candidates('sofa', [])
        self.assertFalse(result['ready_for_traversal'])

    def test_no_api_key_single_candidate_high(self):
        """Single candidate + no AI → no questions → HIGH."""
        cands = [_make_candidate('9401', desc_en='Seats')]
        result = screen_candidates('sofa', cands, db=None, api_key=None)
        self.assertEqual(result['confidence'], 'HIGH')
        self.assertTrue(result['ready_for_traversal'])
        self.assertEqual(result['missing'], [])

    def test_no_api_key_multi_candidate_medium(self):
        """Multiple candidates + no AI → no questions → MEDIUM."""
        cands = [_make_candidate('9401'), _make_candidate('7326')]
        result = screen_candidates('box', cands, db=None, api_key=None)
        self.assertEqual(result['confidence'], 'MEDIUM')
        self.assertTrue(result['ready_for_traversal'])
        self.assertEqual(result['missing'], [])

    @patch('lib.classification_screener._call_haiku')
    def test_all_questions_answered(self, mock_haiku):
        mock_haiku.return_value = _make_ai_response([
            {'question': 'Material?', 'attribute_key': 'material',
             'distinguishes_between': ['9401', '7326']},
        ])
        cands = [_make_candidate('9401'), _make_candidate('7326')]
        known = {'material': 'wood'}
        result = screen_candidates('storage box', cands, known, api_key='test-key')
        self.assertTrue(result['ready_for_traversal'])
        self.assertEqual(result['confidence'], 'HIGH')
        self.assertIn('material', result['answered'])
        self.assertEqual(len(result['missing']), 0)

    @patch('lib.classification_screener._call_haiku')
    def test_missing_questions_returned(self, mock_haiku):
        mock_haiku.return_value = _make_ai_response([
            {'question': 'Material?', 'attribute_key': 'material',
             'distinguishes_between': ['9401', '7326']},
            {'question': 'Weight?', 'attribute_key': 'weight',
             'distinguishes_between': ['9401', '7326']},
        ])
        cands = [_make_candidate('9401'), _make_candidate('7326')]
        result = screen_candidates('box', cands, {}, api_key='test-key')
        self.assertFalse(result['ready_for_traversal'])
        self.assertEqual(len(result['missing']), 2)

    @patch('lib.classification_screener._call_haiku')
    def test_single_candidate_high(self, mock_haiku):
        mock_haiku.return_value = _make_ai_response([])
        cands = [_make_candidate('9401', confidence_level='HIGH')]
        result = screen_candidates('sofa', cands, api_key='test-key')
        self.assertEqual(result['confidence'], 'HIGH')
        self.assertTrue(result['ready_for_traversal'])

    @patch('lib.classification_screener._call_haiku')
    def test_few_missing_is_medium(self, mock_haiku):
        mock_haiku.return_value = _make_ai_response([
            {'question': 'Q?', 'attribute_key': 'physical_form',
             'distinguishes_between': ['9401', '7326']},
        ])
        cands = [_make_candidate('9401'), _make_candidate('7326')]
        result = screen_candidates('item', cands, {}, api_key='test-key')
        self.assertEqual(result['confidence'], 'MEDIUM')  # 1 missing ≤ 2

    @patch('lib.classification_screener._call_haiku')
    def test_many_missing_is_needs_info(self, mock_haiku):
        mock_haiku.return_value = _make_ai_response([
            {'question': 'Q1?', 'attribute_key': 'material',
             'distinguishes_between': ['9401', '7326']},
            {'question': 'Q2?', 'attribute_key': 'primary_function',
             'distinguishes_between': ['9401', '7326']},
            {'question': 'Q3?', 'attribute_key': 'gross_weight_kg',
             'distinguishes_between': ['9401', '7326']},
        ])
        cands = [_make_candidate('9401'), _make_candidate('7326')]
        result = screen_candidates('unknown item', cands, {}, api_key='test-key')
        self.assertEqual(result['confidence'], 'NEEDS_INFO')

    @patch('lib.classification_screener._call_haiku')
    def test_chapter_notes_loaded(self, mock_haiku):
        mock_haiku.return_value = _make_ai_response([])
        db = _mock_chapter_notes_db({
            'chapter_94': SAMPLE_CHAPTER_94,
            'chapter_73': SAMPLE_CHAPTER_73,
        })
        cands = [_make_candidate('9401'), _make_candidate('7326')]
        result = screen_candidates('box', cands, db=db, api_key='test-key')
        self.assertIn('94', result['chapter_notes_loaded'])
        self.assertIn('73', result['chapter_notes_loaded'])

    @patch('lib.classification_screener._call_haiku')
    def test_caps_at_max_candidates(self, mock_haiku):
        mock_haiku.return_value = _make_ai_response([])
        cands = [_make_candidate(f'{20+i:02}01') for i in range(10)]
        result = screen_candidates('product', cands, api_key='test-key')
        self.assertLessEqual(len(result['candidates']), _MAX_CANDIDATES)

    @patch('lib.classification_screener._call_haiku')
    def test_ai_prompt_includes_chapter_notes(self, mock_haiku):
        """Verify the chapter notes text is passed to AI."""
        mock_haiku.return_value = _make_ai_response([])
        db = _mock_chapter_notes_db({
            'chapter_94': SAMPLE_CHAPTER_94,
        })
        cands = [_make_candidate('9401', desc_en='Seats')]
        screen_candidates('sofa', cands, db=db, api_key='test-key')

        # Check the user_prompt passed to _call_haiku
        call_args = mock_haiku.call_args
        user_prompt = call_args[0][2]  # positional arg 2
        self.assertIn('furniture', user_prompt)  # from preamble_en

    @patch('lib.classification_screener._call_haiku')
    def test_result_structure(self, mock_haiku):
        """Verify all required keys are present in result."""
        mock_haiku.return_value = _make_ai_response([])
        cands = [_make_candidate('9401')]
        result = screen_candidates('sofa', cands, api_key='test-key')
        required_keys = [
            'product', 'candidates', 'chapter_notes_loaded',
            'answered', 'missing', 'confidence', 'ready_for_traversal',
        ]
        for key in required_keys:
            self.assertIn(key, result, f'Missing key: {key}')


# ═══════════════════════════════════════════
#  Test: System prompt quality
# ═══════════════════════════════════════════

class TestSystemPrompt(unittest.TestCase):
    def test_mentions_json(self):
        self.assertIn('JSON', _SYSTEM_PROMPT)

    def test_mentions_snake_case(self):
        self.assertIn('snake_case', _SYSTEM_PROMPT)

    def test_shows_good_examples(self):
        self.assertIn('fuel_type', _SYSTEM_PROMPT)
        self.assertIn('engine_cc', _SYSTEM_PROMPT)
        self.assertIn('seating_capacity', _SYSTEM_PROMPT)
        self.assertIn('fiber_content', _SYSTEM_PROMPT)

    def test_shows_bad_examples(self):
        """Prompt discourages generic keys."""
        self.assertIn('Bad:', _SYSTEM_PROMPT)
        self.assertIn('gross_weight_kg', _SYSTEM_PROMPT)  # instead of "weight"
        self.assertIn('power_watts', _SYSTEM_PROMPT)  # instead of "power"

    def test_caps_at_five_questions(self):
        self.assertIn('Maximum 5', _SYSTEM_PROMPT)

    def test_requires_distinguishes_between(self):
        self.assertIn('distinguishes_between', _SYSTEM_PROMPT)

    def test_no_fixed_list_constraint(self):
        """Prompt should NOT say 'must be from the allowed list'."""
        self.assertNotIn('must be from the allowed list', _SYSTEM_PROMPT)


# ═══════════════════════════════════════════
#  Test: Attribute alias coverage
# ═══════════════════════════════════════════

class TestAttributeAliases(unittest.TestCase):
    def test_core_canonical_keys_covered(self):
        """Core canonical forms that must exist in the alias map."""
        canonical = {
            'material', 'primary_function', 'gross_weight_kg', 'dimensions',
            'power_watts', 'country_of_origin', 'physical_form', 'quantity',
            'operating_frequency', 'capacity_liters', 'engine_type',
        }
        mapped_values = set(_KNOWN_ATTRIBUTE_ALIASES.values())
        for c in canonical:
            self.assertIn(c, mapped_values, f'Canonical key {c} not in alias map')

    def test_domain_specific_keys_in_aliases(self):
        """Domain-specific keys exist for vehicles, food, textiles."""
        mapped_values = set(_KNOWN_ATTRIBUTE_ALIASES.values())
        for key in ['fuel_type', 'seating_capacity', 'engine_cc',
                     'fiber_content', 'species', 'fat_content',
                     'frame_material', 'processing_state']:
            self.assertIn(key, mapped_values, f'Domain key {key} not in alias map')

    def test_hebrew_keys_exist(self):
        hebrew_keys = [k for k in _KNOWN_ATTRIBUTE_ALIASES if any(
            '\u0590' <= ch <= '\u05FF' for ch in k)]
        self.assertGreaterEqual(len(hebrew_keys), 10,
                                'Should have at least 10 Hebrew aliases')


class TestAttrKeyRegex(unittest.TestCase):
    """Test the snake_case validation regex."""

    def test_valid_keys(self):
        for key in ['material', 'fuel_type', 'engine_cc', 'gross_weight_kg',
                     'a', 'x1', 'fiber_content_pct']:
            self.assertTrue(_ATTR_KEY_RE.match(key), f'{key} should be valid')

    def test_invalid_keys(self):
        for key in ['', 'Fuel_Type', 'has space', '3phase', '_leading',
                     'a' * 31, 'special!char', 'UPPER']:
            self.assertIsNone(_ATTR_KEY_RE.match(key), f'{key} should be invalid')


if __name__ == '__main__':
    unittest.main()
