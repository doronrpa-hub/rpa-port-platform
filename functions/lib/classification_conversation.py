"""
Classification Conversation — Stage 3 of the reasoning engine.

Multi-turn conversation state. Each email thread accumulates attributes.
System never asks the same question twice. When all determinative
attributes are known → ready for GIR traversal.

INPUT per email:
  - conversation_id (from Microsoft Graph conversationId)
  - product_name
  - screener_result (from Stage 2)
  - email_body (current email text — may contain answers to prior questions)

OUTPUT:
  {
    'conversation_id': str,
    'product_name': str,
    'known_attributes': dict,
    'still_missing': list,
    'ready_for_traversal': bool,
    'questions_to_ask': list,
    'turn_count': int
  }

Firestore collection: 'classification_conversations'
Doc ID = conversation_id
TTL: 7 days (expires_at field).

Does NOT touch broker_engine.py.
"""

import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger('rcb.conversation')

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 1024
_TIMEOUT = 25  # seconds
_TTL_DAYS = 7

_ISRAEL_TZ = timezone(timedelta(hours=2))  # Winter; summer would be +3


# ---------------------------------------------------------------------------
#  Answer extraction prompt
# ---------------------------------------------------------------------------

_EXTRACT_SYSTEM = """You extract attribute answers from email text.

Given a list of unanswered questions and the email body, find any answers.
Return ONLY valid JSON — no markdown, no explanation, no code fences.

JSON format:
{
  "extracted": {
    "attribute_key": "extracted value"
  }
}

Rules:
- Only extract values that clearly and directly answer a question
- Use the exact attribute_key from the question
- Values must be concise: a word, number, or short phrase
- If the email doesn't answer a question, do NOT include that key
- If no answers found, return {"extracted": {}}
- Never invent or guess values"""


def _build_extract_prompt(unanswered_questions, email_body):
    """Build user prompt for answer extraction."""
    parts = ["Unanswered questions:"]
    for q in unanswered_questions:
        parts.append(
            f"  - {q['question']} (attribute_key: {q['attribute_key']})"
        )
    parts.append(f"\nEmail body:\n{email_body[:3000]}")
    return '\n'.join(parts)


def _call_haiku(api_key, system_prompt, user_prompt):
    """Call Claude Haiku for answer extraction."""
    if not api_key:
        logger.warning('[conversation] no API key — skipping extraction')
        return None

    try:
        resp = requests.post(
            _API_URL,
            headers={
                'x-api-key': api_key.strip(),
                'content-type': 'application/json',
                'anthropic-version': '2023-06-01',
            },
            json={
                'model': _MODEL,
                'max_tokens': _MAX_TOKENS,
                'system': system_prompt,
                'messages': [{'role': 'user', 'content': user_prompt}],
            },
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get('content', [{}])[0].get('text', '')
        else:
            logger.warning('[conversation] Haiku API %d: %s',
                           resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.warning('[conversation] Haiku call error: %s', e)
        return None


def _parse_extracted(raw_text):
    """Parse AI extraction response into dict of attribute_key→value."""
    if not raw_text:
        return {}

    text = raw_text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                logger.warning('[conversation] could not parse extraction response')
                return {}
        else:
            return {}

    extracted = parsed.get('extracted', {})
    if not isinstance(extracted, dict):
        return {}

    # Validate: only string values, non-empty
    clean = {}
    for k, v in extracted.items():
        k_str = str(k).strip()
        v_str = str(v).strip()
        if k_str and v_str:
            clean[k_str] = v_str

    return clean


# ---------------------------------------------------------------------------
#  Firestore state management
# ---------------------------------------------------------------------------

def _load_state(db, conversation_id):
    """Load conversation state from Firestore. Returns dict or None."""
    if db is None:
        return None

    try:
        doc = db.collection('classification_conversations') \
                .document(conversation_id).get()
        if doc.exists:
            data = doc.to_dict()
            # Check TTL
            expires_at = data.get('expires_at')
            if expires_at:
                if hasattr(expires_at, 'timestamp'):
                    # Firestore Timestamp
                    exp_ts = expires_at.timestamp()
                elif isinstance(expires_at, str):
                    try:
                        exp_dt = datetime.fromisoformat(expires_at)
                        exp_ts = exp_dt.timestamp()
                    except (ValueError, TypeError):
                        exp_ts = float(expires_at)
                else:
                    exp_ts = float(expires_at)
                if time.time() > exp_ts:
                    logger.info('[conversation] %s expired, starting fresh',
                                conversation_id)
                    return None
            return data
        return None
    except Exception as e:
        logger.warning('[conversation] load error for %s: %s',
                       conversation_id, e)
        return None


def _save_state(db, conversation_id, state):
    """Save conversation state to Firestore."""
    if db is None:
        return

    try:
        db.collection('classification_conversations') \
          .document(conversation_id).set(state, merge=True)
        logger.info('[conversation] saved state for %s (turn %d)',
                    conversation_id, state.get('turn_count', 0))
    except Exception as e:
        logger.warning('[conversation] save error for %s: %s',
                       conversation_id, e)


def _now_israel():
    """Current time in Israel timezone."""
    return datetime.now(_ISRAEL_TZ)


def _make_expires_at():
    """Return expiry timestamp (7 days from now)."""
    return _now_israel() + timedelta(days=_TTL_DAYS)


# ---------------------------------------------------------------------------
#  Core: extract answers from email body
# ---------------------------------------------------------------------------

def extract_answers(email_body, unanswered_questions, api_key=None):
    """
    Extract answers from email body for unanswered questions.

    Args:
        email_body:           current email text
        unanswered_questions: list of question dicts with 'attribute_key'
        api_key:              Anthropic API key

    Returns:
        dict of {attribute_key: value} for answered questions
    """
    if not email_body or not unanswered_questions:
        return {}

    # Quick regex pre-check: if email body is very short or clearly
    # doesn't contain any relevant content, skip AI call
    body_stripped = email_body.strip()
    if len(body_stripped) < 5:
        return {}

    user_prompt = _build_extract_prompt(unanswered_questions, body_stripped)
    raw = _call_haiku(api_key, _EXTRACT_SYSTEM, user_prompt)
    return _parse_extracted(raw)


# ---------------------------------------------------------------------------
#  Core: deduplicate questions
# ---------------------------------------------------------------------------

def _dedup_questions(new_questions, asked_questions):
    """
    Remove questions that were already asked in previous turns.

    Args:
        new_questions:   list of question dicts from screener
        asked_questions: list of attribute_keys already asked

    Returns:
        list of truly new questions to ask
    """
    if not asked_questions:
        return list(new_questions)

    asked_set = set(asked_questions)
    return [q for q in new_questions if q['attribute_key'] not in asked_set]


# ---------------------------------------------------------------------------
#  Main entry point
# ---------------------------------------------------------------------------

def process_conversation_turn(conversation_id, product_name, screener_result,
                              email_body='', db=None, api_key=None):
    """
    Process one turn of a classification conversation.

    Args:
        conversation_id:  Graph API conversationId (doc ID)
        product_name:     product description
        screener_result:  dict from screen_candidates() (Stage 2)
        email_body:       current email text (may contain answers)
        db:               Firestore client
        api_key:          Anthropic API key

    Returns:
        dict with conversation state and next actions
    """
    t0 = time.monotonic()

    if not conversation_id:
        return _error_result('', product_name, 'missing conversation_id')

    # Step 1: Load existing state
    state = _load_state(db, conversation_id)

    if state is None:
        # New conversation
        state = {
            'conversation_id': conversation_id,
            'product_name': product_name or '',
            'known_attributes': {},
            'asked_questions': [],
            'candidates': screener_result.get('candidates', []),
            'turn_count': 0,
            'status': 'active',
            'created_at': _now_israel().isoformat(),
            'updated_at': _now_israel().isoformat(),
            'expires_at': _make_expires_at().isoformat(),
        }
    else:
        # Update product name if provided (may improve on first turn's guess)
        if product_name:
            state['product_name'] = product_name
        # Update candidates if screener gave new ones
        if screener_result.get('candidates'):
            state['candidates'] = screener_result['candidates']

    turn_count = state.get('turn_count', 0) + 1
    state['turn_count'] = turn_count
    state['updated_at'] = _now_israel().isoformat()

    known_attrs = state.get('known_attributes', {})
    asked_questions = state.get('asked_questions', [])

    # Step 2: Extract answers from current email body
    #   Build unanswered list from asked_questions that aren't in known_attrs
    unanswered = []
    # We need the full question dicts — reconstruct from state history
    question_history = state.get('question_history', [])
    for qh in question_history:
        if qh.get('attribute_key') not in known_attrs:
            unanswered.append(qh)

    new_answers = {}
    if email_body and unanswered and turn_count > 1:
        new_answers = extract_answers(email_body, unanswered, api_key=api_key)
        if new_answers:
            known_attrs.update(new_answers)
            state['known_attributes'] = known_attrs
            logger.info('[conversation] %s: extracted %d answers from email',
                        conversation_id, len(new_answers))

    # Step 3: Get missing questions from screener result
    screener_missing = screener_result.get('missing', [])
    screener_answered = screener_result.get('answered', {})

    # Merge screener's answered into known
    if screener_answered:
        for k, v in screener_answered.items():
            if k not in known_attrs:
                known_attrs[k] = v
        state['known_attributes'] = known_attrs

    # Step 4: Dedup — never ask the same question twice
    new_questions = _dedup_questions(screener_missing, asked_questions)

    # Record newly asked questions
    for q in new_questions:
        attr_key = q['attribute_key']
        if attr_key not in asked_questions:
            asked_questions.append(attr_key)
            question_history.append(q)

    state['asked_questions'] = asked_questions
    state['question_history'] = question_history

    # Step 5: Determine what's still missing
    #   A question is still missing if its attribute_key is not in known_attrs
    still_missing = [
        q for q in question_history
        if q['attribute_key'] not in known_attrs
    ]

    ready = len(still_missing) == 0 and (
        screener_result.get('ready_for_traversal', False)
        or len(known_attrs) > 0
    )

    if ready:
        state['status'] = 'ready'
    elif turn_count >= 5 and still_missing:
        # After 5 turns, proceed anyway with what we have
        state['status'] = 'ready_partial'
        ready = True
    else:
        state['status'] = 'active'

    # Step 6: Save state
    _save_state(db, conversation_id, state)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        '[conversation] %s turn %d | %dms | known=%d | missing=%d | '
        'new_answers=%d | new_questions=%d | ready=%s',
        conversation_id, turn_count, elapsed_ms,
        len(known_attrs), len(still_missing),
        len(new_answers), len(new_questions), ready,
    )

    return {
        'conversation_id': conversation_id,
        'product_name': state['product_name'],
        'known_attributes': known_attrs,
        'still_missing': still_missing,
        'ready_for_traversal': ready,
        'questions_to_ask': new_questions,
        'turn_count': turn_count,
    }


def _error_result(conversation_id, product_name, reason):
    """Return an error/empty result."""
    logger.warning('[conversation] error: %s', reason)
    return {
        'conversation_id': conversation_id or '',
        'product_name': product_name or '',
        'known_attributes': {},
        'still_missing': [],
        'ready_for_traversal': False,
        'questions_to_ask': [],
        'turn_count': 0,
    }
