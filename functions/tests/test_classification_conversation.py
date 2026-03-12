"""Tests for classification_conversation.py — Stage 3 multi-turn state."""

import json
import sys
import os
import time
import unittest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from lib.classification_conversation import (
    process_conversation_turn,
    extract_answers,
    _parse_extracted,
    _build_extract_prompt,
    _dedup_questions,
    _load_state,
    _save_state,
    _make_expires_at,
    _now_israel,
    _error_result,
    _TTL_DAYS,
)


# ═══════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════

def _make_question(attr_key, question='What?', question_he='מה?',
                   distinguishes=None, why=''):
    return {
        'question': question,
        'question_he': question_he,
        'attribute_key': attr_key,
        'distinguishes_between': distinguishes or ['7304', '7306'],
        'why': why or f'Determines {attr_key}',
    }


def _make_screener_result(candidates=None, answered=None, missing=None,
                          ready=False, confidence='NEEDS_INFO'):
    return {
        'product': 'steel tubes',
        'candidates': candidates or [
            {'heading': '7304', 'chapter': '73',
             'description_en': 'Seamless tubes', 'sources': ['tree_he']},
            {'heading': '7306', 'chapter': '73',
             'description_en': 'Welded tubes', 'sources': ['tree_he']},
        ],
        'chapter_notes_loaded': ['73'],
        'answered': answered or {},
        'missing': missing or [],
        'confidence': confidence,
        'ready_for_traversal': ready,
    }


def _mock_firestore_doc(data=None, exists=True):
    """Create a mock Firestore document."""
    doc = MagicMock()
    doc.exists = exists
    doc.to_dict.return_value = data or {}
    return doc


def _mock_db(doc_data=None, doc_exists=True):
    """Create a mock Firestore client."""
    db = MagicMock()
    doc = _mock_firestore_doc(doc_data, doc_exists)
    db.collection.return_value.document.return_value.get.return_value = doc
    return db


# ═══════════════════════════════════════════
#  Test _parse_extracted
# ═══════════════════════════════════════════

class TestParseExtracted(unittest.TestCase):

    def test_valid_json(self):
        raw = '{"extracted": {"material": "stainless steel", "wall_thickness": "2mm"}}'
        result = _parse_extracted(raw)
        self.assertEqual(result, {'material': 'stainless steel', 'wall_thickness': '2mm'})

    def test_empty_extracted(self):
        raw = '{"extracted": {}}'
        self.assertEqual(_parse_extracted(raw), {})

    def test_with_code_fences(self):
        raw = '```json\n{"extracted": {"fuel_type": "diesel"}}\n```'
        result = _parse_extracted(raw)
        self.assertEqual(result, {'fuel_type': 'diesel'})

    def test_none_input(self):
        self.assertEqual(_parse_extracted(None), {})

    def test_empty_string(self):
        self.assertEqual(_parse_extracted(''), {})

    def test_invalid_json(self):
        self.assertEqual(_parse_extracted('not json at all'), {})

    def test_strips_empty_values(self):
        raw = '{"extracted": {"material": "steel", "color": "", "size": "  "}}'
        result = _parse_extracted(raw)
        self.assertEqual(result, {'material': 'steel'})

    def test_non_dict_extracted(self):
        raw = '{"extracted": ["a", "b"]}'
        self.assertEqual(_parse_extracted(raw), {})

    def test_embedded_json(self):
        raw = 'Here is the result: {"extracted": {"weight": "5kg"}} done'
        result = _parse_extracted(raw)
        self.assertEqual(result, {'weight': '5kg'})

    def test_values_converted_to_string(self):
        raw = '{"extracted": {"count": 5, "active": true}}'
        result = _parse_extracted(raw)
        self.assertEqual(result['count'], '5')
        self.assertEqual(result['active'], 'True')


# ═══════════════════════════════════════════
#  Test _build_extract_prompt
# ═══════════════════════════════════════════

class TestBuildExtractPrompt(unittest.TestCase):

    def test_basic_prompt(self):
        qs = [_make_question('material', 'What material?')]
        prompt = _build_extract_prompt(qs, 'The tubes are stainless steel')
        self.assertIn('What material?', prompt)
        self.assertIn('attribute_key: material', prompt)
        self.assertIn('stainless steel', prompt)

    def test_multiple_questions(self):
        qs = [
            _make_question('material', 'What material?'),
            _make_question('wall_thickness', 'What wall thickness?'),
        ]
        prompt = _build_extract_prompt(qs, 'Some email body')
        self.assertIn('material', prompt)
        self.assertIn('wall_thickness', prompt)

    def test_long_body_truncated(self):
        long_body = 'x' * 5000
        prompt = _build_extract_prompt([_make_question('m')], long_body)
        # Body truncated to 3000
        self.assertTrue(len(prompt) < 5500)

    def test_empty_questions(self):
        prompt = _build_extract_prompt([], 'body')
        self.assertIn('Unanswered questions:', prompt)


# ═══════════════════════════════════════════
#  Test _dedup_questions
# ═══════════════════════════════════════════

class TestDedupQuestions(unittest.TestCase):

    def test_no_prior(self):
        qs = [_make_question('material'), _make_question('fuel_type')]
        result = _dedup_questions(qs, [])
        self.assertEqual(len(result), 2)

    def test_all_asked(self):
        qs = [_make_question('material'), _make_question('fuel_type')]
        result = _dedup_questions(qs, ['material', 'fuel_type'])
        self.assertEqual(len(result), 0)

    def test_partial_overlap(self):
        qs = [_make_question('material'), _make_question('fuel_type')]
        result = _dedup_questions(qs, ['material'])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['attribute_key'], 'fuel_type')

    def test_none_asked(self):
        qs = [_make_question('material')]
        result = _dedup_questions(qs, None)
        self.assertEqual(len(result), 1)

    def test_empty_new(self):
        result = _dedup_questions([], ['material'])
        self.assertEqual(len(result), 0)


# ═══════════════════════════════════════════
#  Test extract_answers
# ═══════════════════════════════════════════

class TestExtractAnswers(unittest.TestCase):

    @patch('lib.classification_conversation._call_haiku')
    def test_extracts_from_body(self, mock_haiku):
        mock_haiku.return_value = '{"extracted": {"material": "carbon steel"}}'
        qs = [_make_question('material', 'What material?')]
        result = extract_answers('The tubes are carbon steel', qs, api_key='k')
        self.assertEqual(result, {'material': 'carbon steel'})
        mock_haiku.assert_called_once()

    @patch('lib.classification_conversation._call_haiku')
    def test_no_answers_found(self, mock_haiku):
        mock_haiku.return_value = '{"extracted": {}}'
        qs = [_make_question('material')]
        result = extract_answers('Weather is nice today', qs, api_key='k')
        self.assertEqual(result, {})

    def test_empty_body(self):
        result = extract_answers('', [_make_question('m')], api_key='k')
        self.assertEqual(result, {})

    def test_no_questions(self):
        result = extract_answers('Some body', [], api_key='k')
        self.assertEqual(result, {})

    def test_no_api_key(self):
        result = extract_answers('body', [_make_question('m')])
        self.assertEqual(result, {})

    def test_very_short_body(self):
        result = extract_answers('hi', [_make_question('m')], api_key='k')
        self.assertEqual(result, {})

    @patch('lib.classification_conversation._call_haiku')
    def test_ai_failure(self, mock_haiku):
        mock_haiku.return_value = None
        qs = [_make_question('material')]
        result = extract_answers('body text', qs, api_key='k')
        self.assertEqual(result, {})


# ═══════════════════════════════════════════
#  Test Firestore state management
# ═══════════════════════════════════════════

class TestLoadState(unittest.TestCase):

    def test_load_existing(self):
        data = {
            'conversation_id': 'conv1',
            'product_name': 'steel',
            'known_attributes': {'material': 'steel'},
            'turn_count': 1,
        }
        db = _mock_db(data, True)
        result = _load_state(db, 'conv1')
        self.assertEqual(result['product_name'], 'steel')

    def test_load_nonexistent(self):
        db = _mock_db(None, False)
        result = _load_state(db, 'conv_missing')
        self.assertIsNone(result)

    def test_load_none_db(self):
        result = _load_state(None, 'conv1')
        self.assertIsNone(result)

    def test_load_expired(self):
        # Expired 1 hour ago
        expired_ts = time.time() - 3600
        data = {'conversation_id': 'conv1', 'expires_at': expired_ts}
        db = _mock_db(data, True)
        result = _load_state(db, 'conv1')
        self.assertIsNone(result)

    def test_load_not_expired(self):
        future_ts = time.time() + 86400
        data = {'conversation_id': 'conv1', 'expires_at': future_ts}
        db = _mock_db(data, True)
        result = _load_state(db, 'conv1')
        self.assertIsNotNone(result)

    def test_load_firestore_error(self):
        db = MagicMock()
        db.collection.return_value.document.return_value.get.side_effect = \
            Exception('Firestore down')
        result = _load_state(db, 'conv1')
        self.assertIsNone(result)

    def test_load_timestamp_object(self):
        """Handle Firestore Timestamp objects with .timestamp() method."""
        future = time.time() + 86400
        ts_obj = MagicMock()
        ts_obj.timestamp.return_value = future
        data = {'conversation_id': 'conv1', 'expires_at': ts_obj}
        db = _mock_db(data, True)
        result = _load_state(db, 'conv1')
        self.assertIsNotNone(result)


class TestSaveState(unittest.TestCase):

    def test_save_calls_set(self):
        db = MagicMock()
        state = {'conversation_id': 'conv1', 'turn_count': 1}
        _save_state(db, 'conv1', state)
        db.collection.assert_called_with('classification_conversations')
        db.collection.return_value.document.assert_called_with('conv1')
        db.collection.return_value.document.return_value.set \
            .assert_called_once_with(state, merge=True)

    def test_save_none_db(self):
        # Should not raise
        _save_state(None, 'conv1', {'turn_count': 1})

    def test_save_firestore_error(self):
        db = MagicMock()
        db.collection.return_value.document.return_value.set.side_effect = \
            Exception('write failed')
        # Should not raise
        _save_state(db, 'conv1', {'turn_count': 1})


# ═══════════════════════════════════════════
#  Test _make_expires_at and _now_israel
# ═══════════════════════════════════════════

class TestTimeHelpers(unittest.TestCase):

    def test_expires_in_future(self):
        exp = _make_expires_at()
        now = _now_israel()
        diff = exp - now
        self.assertAlmostEqual(diff.days, _TTL_DAYS, delta=1)

    def test_now_has_timezone(self):
        now = _now_israel()
        self.assertIsNotNone(now.tzinfo)


# ═══════════════════════════════════════════
#  Test process_conversation_turn — new conversation
# ═══════════════════════════════════════════

class TestNewConversation(unittest.TestCase):

    def test_first_turn_with_missing_questions(self):
        db = _mock_db(None, False)  # no existing state
        missing = [
            _make_question('material', 'What material?'),
            _make_question('wall_thickness', 'What wall thickness?'),
        ]
        screener = _make_screener_result(missing=missing)

        result = process_conversation_turn(
            'conv_new', 'steel tubes', screener, db=db
        )

        self.assertEqual(result['conversation_id'], 'conv_new')
        self.assertEqual(result['product_name'], 'steel tubes')
        self.assertEqual(result['turn_count'], 1)
        self.assertFalse(result['ready_for_traversal'])
        self.assertEqual(len(result['questions_to_ask']), 2)
        self.assertEqual(len(result['still_missing']), 2)
        # State saved
        db.collection.return_value.document.return_value.set \
            .assert_called_once()

    def test_first_turn_ready_immediately(self):
        db = _mock_db(None, False)
        screener = _make_screener_result(
            missing=[], ready=True,
            answered={'material': 'steel'},
            confidence='HIGH'
        )

        result = process_conversation_turn(
            'conv_ready', 'steel tubes', screener, db=db
        )

        self.assertTrue(result['ready_for_traversal'])
        self.assertEqual(result['turn_count'], 1)
        self.assertEqual(len(result['still_missing']), 0)
        self.assertEqual(result['known_attributes']['material'], 'steel')

    def test_missing_conversation_id(self):
        result = process_conversation_turn(
            '', 'product', _make_screener_result()
        )
        self.assertEqual(result['conversation_id'], '')
        self.assertFalse(result['ready_for_traversal'])
        self.assertEqual(result['turn_count'], 0)


# ═══════════════════════════════════════════
#  Test process_conversation_turn — returning conversation
# ═══════════════════════════════════════════

class TestReturningConversation(unittest.TestCase):

    @patch('lib.classification_conversation.extract_answers')
    def test_second_turn_extracts_answers(self, mock_extract):
        mock_extract.return_value = {'material': 'stainless steel'}

        existing_state = {
            'conversation_id': 'conv2',
            'product_name': 'steel tubes',
            'known_attributes': {},
            'asked_questions': ['material', 'wall_thickness'],
            'question_history': [
                _make_question('material', 'What material?'),
                _make_question('wall_thickness', 'What wall thickness?'),
            ],
            'candidates': [{'heading': '7304', 'chapter': '73'}],
            'turn_count': 1,
            'status': 'active',
            'created_at': '2026-03-11T10:00:00+02:00',
            'updated_at': '2026-03-11T10:00:00+02:00',
            'expires_at': (time.time() + 86400),
        }
        db = _mock_db(existing_state, True)

        screener = _make_screener_result(
            missing=[_make_question('wall_thickness', 'What wall thickness?')],
        )

        result = process_conversation_turn(
            'conv2', 'steel tubes', screener,
            email_body='The material is stainless steel.',
            db=db, api_key='test_key'
        )

        self.assertEqual(result['turn_count'], 2)
        self.assertIn('material', result['known_attributes'])
        self.assertEqual(result['known_attributes']['material'], 'stainless steel')
        # wall_thickness still missing
        missing_keys = [q['attribute_key'] for q in result['still_missing']]
        self.assertIn('wall_thickness', missing_keys)

    @patch('lib.classification_conversation.extract_answers')
    def test_all_answered_becomes_ready(self, mock_extract):
        mock_extract.return_value = {'wall_thickness': '3mm'}

        existing_state = {
            'conversation_id': 'conv3',
            'product_name': 'steel tubes',
            'known_attributes': {'material': 'carbon steel'},
            'asked_questions': ['material', 'wall_thickness'],
            'question_history': [
                _make_question('material'),
                _make_question('wall_thickness'),
            ],
            'candidates': [{'heading': '7304', 'chapter': '73'}],
            'turn_count': 1,
            'status': 'active',
            'created_at': '2026-03-11T10:00:00+02:00',
            'updated_at': '2026-03-11T10:00:00+02:00',
            'expires_at': (time.time() + 86400),
        }
        db = _mock_db(existing_state, True)

        screener = _make_screener_result(missing=[], ready=True)

        result = process_conversation_turn(
            'conv3', 'steel tubes', screener,
            email_body='Wall thickness is 3mm.',
            db=db, api_key='test_key'
        )

        self.assertTrue(result['ready_for_traversal'])
        self.assertEqual(len(result['still_missing']), 0)
        self.assertIn('wall_thickness', result['known_attributes'])

    def test_no_extraction_on_first_turn(self):
        """Turn 1 should NOT try to extract answers (no prior questions)."""
        db = _mock_db(None, False)
        screener = _make_screener_result(
            missing=[_make_question('material')]
        )

        with patch('lib.classification_conversation._call_haiku') as mock_ai:
            result = process_conversation_turn(
                'conv_new', 'tubes', screener,
                email_body='Some body text', db=db
            )
            # AI should not be called for extraction on turn 1
            mock_ai.assert_not_called()


# ═══════════════════════════════════════════
#  Test question dedup across turns
# ═══════════════════════════════════════════

class TestQuestionDedup(unittest.TestCase):

    def test_never_asks_same_question_twice(self):
        """Even if screener returns same question, dedup removes it."""
        existing_state = {
            'conversation_id': 'conv_dedup',
            'product_name': 'tubes',
            'known_attributes': {},
            'asked_questions': ['material'],
            'question_history': [_make_question('material')],
            'candidates': [],
            'turn_count': 1,
            'status': 'active',
            'created_at': '2026-03-11T10:00:00+02:00',
            'updated_at': '2026-03-11T10:00:00+02:00',
            'expires_at': (time.time() + 86400),
        }
        db = _mock_db(existing_state, True)

        # Screener returns material again + a new question
        screener = _make_screener_result(missing=[
            _make_question('material'),
            _make_question('fuel_type'),
        ])

        result = process_conversation_turn(
            'conv_dedup', 'tubes', screener, db=db
        )

        # Only fuel_type should be in questions_to_ask
        ask_keys = [q['attribute_key'] for q in result['questions_to_ask']]
        self.assertNotIn('material', ask_keys)
        self.assertIn('fuel_type', ask_keys)


# ═══════════════════════════════════════════
#  Test max turns → ready_partial
# ═══════════════════════════════════════════

class TestMaxTurns(unittest.TestCase):

    def test_ready_partial_after_5_turns(self):
        existing_state = {
            'conversation_id': 'conv_maxed',
            'product_name': 'complex item',
            'known_attributes': {'material': 'steel'},
            'asked_questions': ['material', 'fuel_type'],
            'question_history': [
                _make_question('material'),
                _make_question('fuel_type'),
            ],
            'candidates': [],
            'turn_count': 4,  # Will become 5
            'status': 'active',
            'created_at': '2026-03-11T10:00:00+02:00',
            'updated_at': '2026-03-11T10:00:00+02:00',
            'expires_at': (time.time() + 86400),
        }
        db = _mock_db(existing_state, True)

        screener = _make_screener_result(
            missing=[_make_question('fuel_type')]
        )

        result = process_conversation_turn(
            'conv_maxed', 'complex item', screener, db=db
        )

        self.assertEqual(result['turn_count'], 5)
        self.assertTrue(result['ready_for_traversal'])
        # Still has missing but forced ready
        self.assertTrue(len(result['still_missing']) > 0)


# ═══════════════════════════════════════════
#  Test screener_answered merging
# ═══════════════════════════════════════════

class TestScreenerAnsweredMerge(unittest.TestCase):

    def test_screener_answered_merged_into_known(self):
        db = _mock_db(None, False)
        screener = _make_screener_result(
            answered={'material': 'steel', 'origin': 'China'},
            missing=[_make_question('wall_thickness')],
        )

        result = process_conversation_turn(
            'conv_merge', 'steel tubes', screener, db=db
        )

        self.assertIn('material', result['known_attributes'])
        self.assertIn('origin', result['known_attributes'])

    def test_screener_answered_does_not_overwrite_existing(self):
        existing_state = {
            'conversation_id': 'conv_no_overwrite',
            'product_name': 'tubes',
            'known_attributes': {'material': 'stainless steel'},
            'asked_questions': [],
            'question_history': [],
            'candidates': [],
            'turn_count': 1,
            'status': 'active',
            'created_at': '2026-03-11T10:00:00+02:00',
            'updated_at': '2026-03-11T10:00:00+02:00',
            'expires_at': (time.time() + 86400),
        }
        db = _mock_db(existing_state, True)

        screener = _make_screener_result(
            answered={'material': 'carbon steel'},  # less specific
            missing=[],
        )

        result = process_conversation_turn(
            'conv_no_overwrite', 'tubes', screener, db=db
        )

        # Original value preserved
        self.assertEqual(result['known_attributes']['material'],
                         'stainless steel')


# ═══════════════════════════════════════════
#  Test _error_result
# ═══════════════════════════════════════════

class TestErrorResult(unittest.TestCase):

    def test_error_result_structure(self):
        r = _error_result('conv1', 'prod', 'some error')
        self.assertEqual(r['conversation_id'], 'conv1')
        self.assertEqual(r['product_name'], 'prod')
        self.assertFalse(r['ready_for_traversal'])
        self.assertEqual(r['turn_count'], 0)
        self.assertEqual(r['known_attributes'], {})
        self.assertEqual(r['questions_to_ask'], [])

    def test_error_with_none(self):
        r = _error_result(None, None, 'missing')
        self.assertEqual(r['conversation_id'], '')
        self.assertEqual(r['product_name'], '')


# ═══════════════════════════════════════════
#  Test no DB / no API key graceful degradation
# ═══════════════════════════════════════════

class TestGracefulDegradation(unittest.TestCase):

    def test_no_db_still_returns_result(self):
        screener = _make_screener_result(
            missing=[_make_question('material')]
        )
        result = process_conversation_turn(
            'conv_nodb', 'tubes', screener, db=None
        )
        self.assertEqual(result['conversation_id'], 'conv_nodb')
        self.assertEqual(result['turn_count'], 1)
        self.assertFalse(result['ready_for_traversal'])

    def test_no_api_key_still_works(self):
        db = _mock_db(None, False)
        screener = _make_screener_result(
            missing=[_make_question('material')]
        )
        result = process_conversation_turn(
            'conv_nokey', 'tubes', screener,
            email_body='body', db=db, api_key=None
        )
        self.assertEqual(result['turn_count'], 1)


# ═══════════════════════════════════════════
#  Test product_name and candidates update
# ═══════════════════════════════════════════

class TestStateUpdates(unittest.TestCase):

    def test_product_name_updated_on_return(self):
        existing_state = {
            'conversation_id': 'conv_upd',
            'product_name': 'tubes',
            'known_attributes': {},
            'asked_questions': [],
            'question_history': [],
            'candidates': [],
            'turn_count': 1,
            'status': 'active',
            'created_at': '2026-03-11T10:00:00+02:00',
            'updated_at': '2026-03-11T10:00:00+02:00',
            'expires_at': (time.time() + 86400),
        }
        db = _mock_db(existing_state, True)
        screener = _make_screener_result(missing=[])

        result = process_conversation_turn(
            'conv_upd', 'seamless steel tubes', screener, db=db
        )

        self.assertEqual(result['product_name'], 'seamless steel tubes')

    def test_candidates_updated_from_screener(self):
        existing_state = {
            'conversation_id': 'conv_cand',
            'product_name': 'tubes',
            'known_attributes': {},
            'asked_questions': [],
            'question_history': [],
            'candidates': [{'heading': '7304', 'chapter': '73'}],
            'turn_count': 1,
            'status': 'active',
            'created_at': '2026-03-11T10:00:00+02:00',
            'updated_at': '2026-03-11T10:00:00+02:00',
            'expires_at': (time.time() + 86400),
        }
        db = _mock_db(existing_state, True)

        new_candidates = [
            {'heading': '7306', 'chapter': '73', 'description_en': 'Welded'},
        ]
        screener = _make_screener_result(
            candidates=new_candidates, missing=[]
        )

        result = process_conversation_turn(
            'conv_cand', 'tubes', screener, db=db
        )

        # Verify saved state has new candidates
        saved = db.collection.return_value.document.return_value \
                   .set.call_args[0][0]
        self.assertEqual(len(saved['candidates']), 1)
        self.assertEqual(saved['candidates'][0]['heading'], '7306')


# ═══════════════════════════════════════════
#  Integration-style: multi-turn scenario
# ═══════════════════════════════════════════

class TestMultiTurnScenario(unittest.TestCase):

    @patch('lib.classification_conversation.extract_answers')
    def test_three_turn_flow(self, mock_extract):
        """Simulate 3 turns: ask → partial answer → full answer."""

        # --- Turn 1: new conversation, 2 questions ---
        db_turn1 = _mock_db(None, False)
        screener1 = _make_screener_result(missing=[
            _make_question('material', 'What material?'),
            _make_question('wall_thickness', 'What wall thickness?'),
        ])

        r1 = process_conversation_turn(
            'conv_multi', 'steel tubes', screener1, db=db_turn1
        )

        self.assertEqual(r1['turn_count'], 1)
        self.assertFalse(r1['ready_for_traversal'])
        self.assertEqual(len(r1['questions_to_ask']), 2)

        # Capture saved state for turn 2
        saved_state = db_turn1.collection.return_value.document \
                             .return_value.set.call_args[0][0]

        # --- Turn 2: user answers material only ---
        mock_extract.return_value = {'material': 'carbon steel'}
        db_turn2 = _mock_db(saved_state, True)

        screener2 = _make_screener_result(missing=[
            _make_question('wall_thickness', 'What wall thickness?'),
        ])

        r2 = process_conversation_turn(
            'conv_multi', 'steel tubes', screener2,
            email_body='The material is carbon steel.',
            db=db_turn2, api_key='test_key'
        )

        self.assertEqual(r2['turn_count'], 2)
        self.assertFalse(r2['ready_for_traversal'])
        self.assertIn('material', r2['known_attributes'])
        # wall_thickness still missing
        missing_keys = [q['attribute_key'] for q in r2['still_missing']]
        self.assertIn('wall_thickness', missing_keys)
        # material should NOT be re-asked
        ask_keys = [q['attribute_key'] for q in r2['questions_to_ask']]
        self.assertNotIn('material', ask_keys)

        # Capture state for turn 3
        saved_state2 = db_turn2.collection.return_value.document \
                              .return_value.set.call_args[0][0]

        # --- Turn 3: user answers wall_thickness ---
        mock_extract.return_value = {'wall_thickness': '2.5mm'}
        db_turn3 = _mock_db(saved_state2, True)

        screener3 = _make_screener_result(missing=[], ready=True)

        r3 = process_conversation_turn(
            'conv_multi', 'steel tubes', screener3,
            email_body='Wall thickness is 2.5mm.',
            db=db_turn3, api_key='test_key'
        )

        self.assertEqual(r3['turn_count'], 3)
        self.assertTrue(r3['ready_for_traversal'])
        self.assertEqual(len(r3['still_missing']), 0)
        self.assertEqual(r3['known_attributes']['material'], 'carbon steel')
        self.assertEqual(r3['known_attributes']['wall_thickness'], '2.5mm')


if __name__ == '__main__':
    unittest.main()
