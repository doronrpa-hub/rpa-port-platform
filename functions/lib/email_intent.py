"""
Email Body Intelligence — Intent Classifier + Smart Router
===========================================================
Detects intent in email bodies (status requests, customs questions,
knowledge queries, instructions, admin instructions, non-work) and routes
to appropriate handlers. Cost-aware: regex/Firestore first (FREE),
AI only when truly needed.

HARD RULES:
- ONLY reply to @rpa-port.co.il addresses
- External senders → NEVER reply, silently skip
- Rate limit: max 1 reply per sender per hour
- Body < 15 chars → skip (auto-generated / notification)
"""

import re
import hashlib
import logging
import random
import string
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════

ADMIN_EMAIL = "doron@rpa-port.co.il"
TEAM_DOMAIN = "rpa-port.co.il"

REPLY_SYSTEM_PROMPT = (
    "אתה עוזר מקצועי בתחום סיווג מכס וסחר בינלאומי בישראל. "
    "ענה בעברית, בקצרה ובבהירות. השתמש במידע המערכת שסופק. "
    "אם אין מספיק מידע, ציין זאת בכנות. חתום כ-RCB. "
    "מונחים: עמיל מכס / סוכן מכס — לעולם לא מתווך מכס.\n\n"
    "כללים חשובים:\n"
    "1. כאשר יש לך נוסח סעיף מפקודת המכס — חובה לצטט אותו מילה במילה בגוף התשובה. "
    "השתמש בפורמט: «סעיף X: [ציטוט מלא]». אל תסכם — צטט את הנוסח המקורי.\n"
    "2. אם מספר סעיפים רלוונטיים, צטט את העיקריים (עד 3) ותמצת את השאר.\n"
    "3. לאחר הציטוט, הוסף הסבר קצר בשפה פשוטה."
)

RCB_SIGNATURE = "RCB - מערכת מידע מכס"

# Cache expiry: 24 hours
CACHE_TTL_SECONDS = 86400

# Rate limit: 1 reply per sender per hour
RATE_LIMIT_SECONDS = 3600


def _generate_query_tracking_code():
    """Generate unique query tracking code: RCB-Q-YYYYMMDD-XXXXX"""
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"RCB-Q-{date_part}-{random_part}"


# ═══════════════════════════════════════════
#  REGEX PATTERN SETS
# ═══════════════════════════════════════════

# ADMIN_INSTRUCTION patterns (ADMIN only)
ADMIN_INSTRUCTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'(?:from\s*now\s*on|מעכשיו|מהיום)',
        r'(?:change\s*(?:the|email|format)|שנה\s*את)',
        r'(?:in\s*future\s*emails|במיילים?\s*הבאים)',
        r'(?:always\s*(?:add|include|show)|תמיד\s*(?:הוסף|הצג|כלול))',
        r'(?:never\s*(?:add|include|show)|לעולם\s*(?:לא|אל)\s*(?:הוסף|הצג))',
        r'(?:update\s*(?:the\s*)?(?:\w+\s*)?template|עדכן\s*(?:את\s*)?ה?תבנית)',
    ]
]

# NON_WORK patterns
NON_WORK_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'(?:weather|מזג\s*אוויר|forecast)',
        r'(?:wikipedia|ויקיפדיה)',
        r'(?:joke|בדיחה|funny)',
        r'(?:recipe|מתכון)',
        r'(?:sports|ספורט|football|כדורגל)',
        r'(?:homework|שיעורי\s*בית)',
    ]
]

# STATUS_REQUEST patterns (bilingual)
STATUS_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'(?:מה\s*ה?מצב|status|where\s*is|check\s*(?:status|shipment)|עדכון\s*על|איפה\s*ה?משלוח)',
        r'(?:track|מעקב|עקוב\s*אחרי)',
    ]
]

STATUS_ENTITY_PATTERNS = {
    'bol': re.compile(r'(?:B/?L|BOL|BL|bill\s*of\s*lading|שטר)[:\s#]*([A-Z0-9][\w\-]{6,25})', re.IGNORECASE),
    'bol_msc': re.compile(r'\b(MEDURS\d{5,10})\b'),
    'container': re.compile(r'\b([A-Z]{4}\d{7})\b'),
}

# CORRECTION patterns (ADMIN only — must be checked BEFORE CUSTOMS_QUESTION
# to prevent "wrong, should be 8507.6000" from triggering on the HS code)
CORRECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'(?:wrong|incorrect|not\s*correct|fix\s*(?:the|this)|change\s*(?:to|hs|code))',
        r'(?:should\s*(?:be|have\s*been)\s*\d{4})',
        r'(?:טעות|לא\s*נכון|שגוי|תקן|תיקון|צריך\s*להיות)',
        r'(?:הסיווג\s*(?:שגוי|לא\s*נכון)|סיווג\s*(?:שגוי|לא\s*נכון))',
        r'(?:correct\s*(?:code|hs|classification)\s*(?:is|should))',
    ]
]

# CUSTOMS_QUESTION patterns
CUSTOMS_Q_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'(?:what\s*(?:is\s*the\s*)?(?:hs|tariff|duty|customs)\s*(?:code|rate|classification))',
        r'(?:what\'?s?\s*the\s*(?:duty|tariff|customs)\s*(?:rate|code|classification))',
        r'(?:duty\s*rate|tariff\s*rate|customs\s*(?:duty|rate|code))',
        r'(?:מה\s*(?:ה?סיווג|ה?מכס|ה?תעריף|קוד\s*מכס|ה?מס))',
        r'(?:how\s*(?:much|to)\s*(?:duty|import|clear))',
        r'(?:כמה\s*מכס|איך\s*(?:ליבא|לשחרר|לסווג))',
        r'\b\d{4}\.\d{2}(?:\.\d{2,4})?\b',
    ]
]

# INSTRUCTION patterns — must not match question forms like "מה הסיווג"
INSTRUCTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'(?:^|\s)(?:classify|לסווג)\s',
        r'(?:^|\s)(?:סווג|סיווג)\s+(?:את|the|this|these)',
        r'(?:add\s*container|הוסף\s*מכולה)',
        r'(?:stop\s*(?:follow|track|send)|הפסק\s*(?:מעקב|עדכונים)|תפסיק\s*לעקוב)',
        r'(?:start\s*track|התחל\s*מעקב)',
    ]
]

# KNOWLEDGE_QUERY patterns — reuse same signals as knowledge_query.py
KNOWLEDGE_Q_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        # Hebrew question patterns
        r'\?',
        r'תוכל[י]?\s',
        r'מה\s',
        r'איך\s',
        r'האם\s',
        r'אני\sצריך[ה]?\sמידע',
        r'תגיד[י]?\sלי',
        r'מה\sאת[ה]?\sיודע[ת]?\sעל',
        r'יש\sמידע\sעל',
        r'מה\sהנוהל',
        r'מה\sהדין',
        r'תסביר[י]?\s',
        # English question patterns
        r'what do you know about',
        r'can you find',
        r'i need info',
        r'what is the procedure',
        r'do you have information',
        r'tell me about',
        r'any updates on',
    ]
]

# Domain keywords for KNOWLEDGE_QUERY (customs/trade context)
DOMAIN_KEYWORDS = [
    'מכס', 'customs', 'tariff', 'תעריף', 'יבוא', 'import',
    'יצוא', 'export', 'שחרור', 'clearance', 'פטור', 'exemption',
    'הסכם', 'agreement', 'תקן', 'standard', 'רגולציה', 'regulation',
    'משרד', 'ministry', 'אישור', 'approval', 'מכסה', 'quota',
]


# ═══════════════════════════════════════════
#  SENDER PRIVILEGE
# ═══════════════════════════════════════════

def _get_sender_privilege(from_email):
    """ADMIN > TEAM > NONE. NONE = never reply."""
    email_lower = from_email.lower().strip()
    if email_lower == ADMIN_EMAIL:
        return "ADMIN"
    if email_lower.endswith(f"@{TEAM_DOMAIN}"):
        return "TEAM"
    return "NONE"


# ═══════════════════════════════════════════
#  HELPER: EXTRACT TEXT FROM MSG
# ═══════════════════════════════════════════

def _get_body_text(msg):
    """Extract plain text from email body (strip HTML if needed)."""
    body = msg.get('body', {})
    content = body.get('content', '') or ''
    if body.get('contentType', '') == 'html' and content:
        content = re.sub(r'<[^>]+>', ' ', content)
        content = re.sub(r'&\w+;', ' ', content)
        content = re.sub(r'\s+', ' ', content).strip()
    if not content:
        content = msg.get('bodyPreview', '') or ''
    return content


def _get_sender_address(msg):
    """Extract sender email address from Graph API message."""
    return msg.get('from', {}).get('emailAddress', {}).get('address', '') or ''


# ═══════════════════════════════════════════
#  INTENT DETECTION
# ═══════════════════════════════════════════

def detect_email_intent(subject, body_text, from_email, privilege=None, get_secret_func=None):
    """
    Detect intent in email body. Returns dict with intent, confidence, entities.

    Detection order (cheapest first):
    1. ADMIN_INSTRUCTION (regex, ADMIN only)
    2. NON_WORK (regex blacklist)
    3. INSTRUCTION (regex — before STATUS to avoid "add container" misroute)
    4. CUSTOMS_QUESTION (regex)
    5. STATUS_REQUEST (regex + entity extraction)
    6. KNOWLEDGE_QUERY (question patterns + domain keywords)
    7. AMBIGUOUS → Gemini Flash (if available)
    8. NONE (default)
    """
    combined = f"{subject} {body_text}"

    # 1. ADMIN_INSTRUCTION (ADMIN only)
    if privilege == "ADMIN":
        for pat in ADMIN_INSTRUCTION_PATTERNS:
            if pat.search(combined):
                return {
                    "intent": "ADMIN_INSTRUCTION",
                    "confidence": 0.95,
                    "entities": {"instruction_text": body_text.strip()},
                }

    # 2. NON_WORK
    for pat in NON_WORK_PATTERNS:
        if pat.search(combined):
            return {
                "intent": "NON_WORK",
                "confidence": 0.95,
                "entities": {},
            }

    # 3. INSTRUCTION (before STATUS to avoid "add container" misroute)
    for pat in INSTRUCTION_PATTERNS:
        m = pat.search(combined)
        if m:
            action = _classify_instruction(combined)
            entities = {"action": action, "text": body_text.strip()}
            if action == 'stop_tracking':
                entities.update(_extract_status_entities(combined))
            return {
                "intent": "INSTRUCTION",
                "confidence": 0.9,
                "entities": entities,
            }

    # 3b. CORRECTION (ADMIN only — before CUSTOMS_QUESTION to prevent HS code misroute)
    if privilege == "ADMIN":
        for pat in CORRECTION_PATTERNS:
            if pat.search(combined):
                corr_entities = _extract_correction_entities(combined)
                if corr_entities.get('corrected_hs'):
                    return {
                        "intent": "CORRECTION",
                        "confidence": 0.95,
                        "entities": corr_entities,
                    }

    # 4. CUSTOMS_QUESTION
    for pat in CUSTOMS_Q_PATTERNS:
        if pat.search(combined):
            hs_entities = _extract_customs_entities(combined)
            return {
                "intent": "CUSTOMS_QUESTION",
                "confidence": 0.85,
                "entities": hs_entities,
            }

    # 5. STATUS_REQUEST — status keyword match; entities extracted if present
    entities = _extract_status_entities(combined)
    has_status_keyword = any(pat.search(combined) for pat in STATUS_PATTERNS)

    if entities and has_status_keyword:
        return {
            "intent": "STATUS_REQUEST",
            "confidence": 0.9,
            "entities": entities,
        }
    if entities and '?' in combined:
        # Has BL/container entity but no explicit status keyword —
        # check if subject implies status (common pattern: "BL MEDURS12345?")
        return {
            "intent": "STATUS_REQUEST",
            "confidence": 0.8,
            "entities": entities,
        }
    if has_status_keyword and not entities:
        # Status keyword present but no entity — handler will send clarification
        return {
            "intent": "STATUS_REQUEST",
            "confidence": 0.7,
            "entities": {},
        }

    # 6. KNOWLEDGE_QUERY — question pattern + domain context
    is_question = False
    for pat in KNOWLEDGE_Q_PATTERNS:
        if pat.search(combined):
            is_question = True
            break

    if is_question:
        has_domain = any(kw in combined.lower() for kw in DOMAIN_KEYWORDS)
        if has_domain:
            return {
                "intent": "KNOWLEDGE_QUERY",
                "confidence": 0.8,
                "entities": {"question_text": body_text.strip()},
            }
        # Question but no domain context — still might be a knowledge query
        # if it's not too generic
        if len(body_text.strip()) > 30:
            return {
                "intent": "KNOWLEDGE_QUERY",
                "confidence": 0.7,
                "entities": {"question_text": body_text.strip()},
            }

    # 7. AMBIGUOUS — try Gemini Flash if available
    if get_secret_func:
        try:
            gemini_key = get_secret_func("GEMINI_API_KEY")
            if gemini_key:
                flash_result = _classify_with_gemini_flash(gemini_key, subject, body_text)
                if flash_result and flash_result.get('intent') != 'NONE':
                    flash_result['detection_method'] = 'gemini_flash'
                    return flash_result
        except Exception as e:
            logger.warning(f"Gemini Flash classification failed: {e}")

    # 8. DEFAULT
    return {
        "intent": "NONE",
        "confidence": 0.0,
        "entities": {},
    }


def _extract_status_entities(text):
    """Extract BL/container entities from text."""
    entities = {}
    for key, pat in STATUS_ENTITY_PATTERNS.items():
        m = pat.search(text)
        if m:
            entities[key] = m.group(1)
    return entities


def _extract_customs_entities(text):
    """Extract HS codes, product descriptions from customs question text."""
    entities = {}
    # HS code pattern
    hs_match = re.search(r'\b(\d{4}\.\d{2}(?:\.\d{2,4})?)\b', text)
    if hs_match:
        entities['hs_code'] = hs_match.group(1)
    # Product description — text after "for" or "של" or "עבור"
    desc_match = re.search(r'(?:for|של|עבור|on)\s+(.{5,80}?)(?:\?|$|\.)', text, re.IGNORECASE)
    if desc_match:
        entities['product_description'] = desc_match.group(1).strip()
    return entities


def _extract_correction_entities(text):
    """Extract corrected HS code and product from a correction email."""
    entities = {}
    # Look for the corrected HS code — the one Doron says it SHOULD be
    hs_match = re.search(r'(?:should\s*be|צריך\s*להיות|correct\s*(?:code|hs)\s*(?:is)?|תקן\s*ל?)\s*(\d{4}[\.\s]?\d{2,6})', text, re.IGNORECASE)
    if not hs_match:
        # Fallback: find any HS code in the text
        hs_match = re.search(r'\b(\d{4}\.\d{2}(?:\.\d{2,6})?)\b', text)
    if hs_match:
        entities['corrected_hs'] = re.sub(r'\s', '', hs_match.group(1))
    # Try to extract what the original wrong code was
    wrong_match = re.search(r'(?:wrong|incorrect|שגוי|טעות|not\s*correct)\s*[:\-]?\s*(\d{4}[\.\s]?\d{2,6})', text, re.IGNORECASE)
    if wrong_match:
        entities['original_hs'] = re.sub(r'\s', '', wrong_match.group(1))
    # Extract product description if mentioned
    product_match = re.search(r'(?:for|of|עבור|של|the)\s+(.{5,80}?)(?:\s*(?:should|צריך|is\s*not|לא\s*נכון))', text, re.IGNORECASE)
    if product_match:
        entities['product_description'] = product_match.group(1).strip()
    entities['correction_text'] = text.strip()[:500]
    return entities


def _classify_instruction(text):
    """Classify instruction sub-type."""
    text_lower = text.lower()
    if re.search(r'(?:classify|סווג|סיווג|לסווג)', text_lower):
        return 'classify'
    if re.search(r'(?:add\s*container|הוסף\s*מכולה)', text_lower):
        return 'tracker_update'
    if re.search(r'(?:stop\s*(?:follow|track|send)|הפסק\s*(?:מעקב|עדכונים)|תפסיק\s*לעקוב)', text_lower):
        return 'stop_tracking'
    if re.search(r'(?:start\s*track|התחל\s*מעקב)', text_lower):
        return 'start_tracking'
    return 'unknown'


def _classify_with_gemini_flash(gemini_key, subject, body_text):
    """Use Gemini Flash for ambiguous intent classification. ~$0.001."""
    import requests as _requests

    prompt = f"""Classify this email into ONE intent category. Return ONLY a JSON object.

Categories:
- CORRECTION: correcting a previous classification (wrong HS code, should be X)
- STATUS_REQUEST: asking about shipment status, BL tracking, container location
- CUSTOMS_QUESTION: asking about HS codes, tariff rates, duty, customs classification
- KNOWLEDGE_QUERY: asking about customs procedures, regulations, trade agreements
- INSTRUCTION: requesting an action (classify, track, add container)
- NON_WORK: off-topic (weather, sports, jokes, personal)
- NONE: cannot determine / not relevant

Subject: {subject}
Body: {body_text[:500]}

Return JSON: {{"intent": "CATEGORY", "confidence": 0.X, "entities": {{}}}}"""

    try:
        resp = _requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 200},
            },
            timeout=10,
        )
        if resp.status_code == 200:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            # Parse JSON from response
            import json
            # Strip markdown code fences if present
            text = re.sub(r'```(?:json)?\s*', '', text).strip()
            text = re.sub(r'```\s*$', '', text).strip()
            result = json.loads(text)
            if result.get('intent') in ('STATUS_REQUEST', 'CUSTOMS_QUESTION',
                                         'KNOWLEDGE_QUERY', 'INSTRUCTION',
                                         'NON_WORK', 'NONE'):
                return result
    except Exception as e:
        logger.warning(f"Gemini Flash intent error: {e}")
    return None


# ═══════════════════════════════════════════
#  CACHE & RATE LIMIT
# ═══════════════════════════════════════════

def _question_hash(subject, body_text):
    """Create dedup hash for a question."""
    normalized = re.sub(r'\s+', ' ', f"{subject} {body_text}".lower().strip())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]


def _check_cache(db, subject, body_text):
    """Check questions_log for cached answer. Returns dict or None."""
    q_hash = _question_hash(subject, body_text)
    try:
        doc = db.collection("questions_log").document(q_hash).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        # Check TTL
        created = data.get('created_at')
        if created:
            if hasattr(created, 'timestamp'):
                created_ts = created.timestamp()
            else:
                created_ts = created.replace(tzinfo=timezone.utc).timestamp() if isinstance(created, datetime) else 0
            if time.time() - created_ts > CACHE_TTL_SECONDS:
                return None
        if data.get('answer_html'):
            return {
                'answer_html': data['answer_html'],
                'intent': data.get('intent', ''),
                'question_hash': q_hash,
            }
    except Exception as e:
        logger.warning(f"Cache check error: {e}")
    return None


def _increment_hit_count(db, question_hash):
    """Increment cache hit counter."""
    try:
        db.collection("questions_log").document(question_hash).update({
            "hit_count": _firestore_increment(1),
        })
    except Exception:
        pass


def _firestore_increment(n):
    """Helper for Firestore field increment."""
    try:
        from google.cloud.firestore_v1 import transforms
        return transforms.Increment(n)
    except ImportError:
        return n


def _is_rate_limited(db, from_email):
    """Check if sender has been replied to in the last hour."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=RATE_LIMIT_SECONDS)
        results = list(
            db.collection("questions_log")
            .where("from_email", "==", from_email.lower())
            .where("created_at", ">=", cutoff)
            .limit(1)
            .stream()
        )
        return len(results) > 0
    except Exception as e:
        logger.warning(f"Rate limit check error: {e}")
        return False


# ═══════════════════════════════════════════
#  REPLY COMPOSITION (Cost ladder)
# ═══════════════════════════════════════════

def _compose_reply(context, question, get_secret_func):
    """Compose a Hebrew reply. ChatGPT for quality, Gemini Flash as fallback."""
    # Try ChatGPT first (better Hebrew prose)
    if get_secret_func:
        openai_key = get_secret_func("OPENAI_API_KEY")
        if openai_key:
            reply = _call_chatgpt(openai_key, context, question)
            if reply:
                return reply, "chatgpt"
        # Fallback to Gemini Flash
        gemini_key = get_secret_func("GEMINI_API_KEY")
        if gemini_key:
            reply = _call_gemini_flash(gemini_key, context, question)
            if reply:
                return reply, "gemini_flash"
    # Last resort: template-based (no AI)
    return _template_reply(context), "template"


def _call_chatgpt(api_key, context, question, max_tokens=1500):
    """Call OpenAI gpt-4o-mini for Hebrew reply composition. ~$0.005/call."""
    import requests as _requests
    try:
        resp = _requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": REPLY_SYSTEM_PROMPT},
                    {"role": "user", "content": f"שאלה: {question}\n\nמידע מהמערכת:\n{context}"},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"ChatGPT error: {e}")
    return None


def _call_gemini_flash(gemini_key, context, question):
    """Call Gemini Flash for reply composition. ~$0.001/call."""
    import requests as _requests
    prompt = f"{REPLY_SYSTEM_PROMPT}\n\nשאלה: {question}\n\nמידע מהמערכת:\n{context}"
    try:
        resp = _requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1500},
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.warning(f"Gemini Flash compose error: {e}")
    return None


def _template_reply(context):
    """Template-based reply when no AI is available."""
    if not context:
        return "לא נמצא מידע רלוונטי במערכת. אנא פנה לצוות המכס לסיוע נוסף."
    # Trim context to reasonable length
    ctx = context[:800] if len(context) > 800 else context
    return f"להלן המידע שנמצא במערכת:\n\n{ctx}\n\nלפרטים נוספים, אנא פנה לצוות."


def _wrap_html_rtl(text, subject=""):
    """Wrap text reply in Hebrew RTL HTML with RCB signature."""
    # Convert newlines to <br> if not already HTML
    if '<' not in text:
        text = text.replace('\n', '<br>')
    return f"""<div dir="rtl" style="font-family: Arial, sans-serif; font-size: 14px; direction: rtl; text-align: right;">
{text}
<br><br>
<hr style="border: none; border-top: 1px solid #ddd;">
<div style="color: #888; font-size: 12px;">
{RCB_SIGNATURE}<br>
מערכת אוטומטית לסיווג מכס וסחר בינלאומי
</div>
</div>"""


# ═══════════════════════════════════════════
#  REPLY SENDING — HARD RULE: only @rpa-port.co.il
# ═══════════════════════════════════════════

def _send_reply_safe(body_html, msg, access_token, rcb_email, subject_override=None):
    """Send reply ONLY to @rpa-port.co.il addresses. Strip external recipients.
    Also blocks replies when rcb@ is only CC'd (not a direct TO recipient).
    Applies banned phrase filter to ALL outgoing replies (intelligence gate).

    Args:
        subject_override: If provided, used as the reply subject instead of
                          deriving from original. Use for RCB-branded subjects.
    """
    from_email = _get_sender_address(msg)
    if not from_email.lower().endswith(f"@{TEAM_DOMAIN}"):
        return False  # NEVER reply to external

    # Gate: only reply if rcb@ was a direct TO recipient, not just CC'd
    try:
        from lib.rcb_helpers import is_direct_recipient
    except ImportError:
        from rcb_helpers import is_direct_recipient
    if not is_direct_recipient(msg, rcb_email):
        print(f"  📭 Reply suppressed — rcb@ was CC'd, not TO recipient (from={from_email})")
        return False

    # Intelligence Gate: filter banned phrases from ALL outgoing replies
    try:
        from lib.intelligence_gate import filter_banned_phrases
        bp_result = filter_banned_phrases(body_html)
        if bp_result["was_modified"]:
            body_html = bp_result["cleaned_html"]
            print(f"  🧹 Intent reply: removed {len(bp_result['phrases_found'])} banned phrases: "
                  f"{', '.join(bp_result['phrases_found'][:3])}")
    except Exception as e:
        print(f"  ⚠️ Banned phrase filter error (fail-open): {e}")

    msg_id = msg.get('id', '')
    try:
        from lib.rcb_helpers import helper_graph_reply, helper_graph_send, _RE_FWD_PATTERN
    except ImportError:
        from rcb_helpers import helper_graph_reply, helper_graph_send, _RE_FWD_PATTERN

    # Build subject: caller override > RCB-branded > Re: original > RCB minimum
    if subject_override:
        subject = subject_override
    else:
        orig_subject = (msg.get('subject', '') or '').strip()
        orig_subject = _RE_FWD_PATTERN.sub('', orig_subject).strip() if orig_subject else ''
        if not orig_subject:
            subject = 'RCB'
        else:
            subject = f"Re: {orig_subject}"

    # Try threaded reply first, fallback to send
    sent = helper_graph_reply(access_token, rcb_email, msg_id, body_html,
                              to_email=from_email, subject=subject)
    if not sent:
        sent = helper_graph_send(access_token, rcb_email, from_email,
                                 subject, body_html)
    return sent


# ═══════════════════════════════════════════
#  CLARIFICATION LOGIC
# ═══════════════════════════════════════════

CLARIFICATION_MESSAGES = {
    'missing_shipment_id': "של איזה משלוח? נא לציין מספר BL, מכולה או מספר תיק",
    'missing_stop_target': "איזה משלוח להפסיק לעקוב? נא לציין מספר BL או מכולה",
    'missing_attachment': "לא מצאתי מסמך מצורף. נא לשלוח חשבונית או מסמך לסיווג",
    'ambiguous_intent': "לא הצלחתי להבין את הבקשה. אפשר לנסח מחדש?",
}


def _send_clarification(clarification_type, original_intent, original_entities,
                        msg, db, firestore_module, access_token, rcb_email):
    """Send clarification reply and store pending doc for follow-up matching."""
    message_text = CLARIFICATION_MESSAGES.get(clarification_type, CLARIFICATION_MESSAGES['ambiguous_intent'])
    reply_html = _wrap_html_rtl(message_text)
    sent = _send_reply_safe(reply_html, msg, access_token, rcb_email)
    if not sent:
        return {"status": "send_failed", "intent": original_intent,
                "clarification_type": clarification_type, "cost_usd": 0.0}

    # Store pending clarification doc (upsert per sender)
    from_email = _get_sender_address(msg)
    key = f"pending_{hashlib.sha256(from_email.lower().encode()).hexdigest()[:12]}"
    try:
        db.collection("questions_log").document(key).set({
            "awaiting_clarification": True,
            "original_intent": original_intent,
            "original_entities": original_entities,
            "clarification_type": clarification_type,
            "from_email": from_email.lower(),
            "created_at": firestore_module.SERVER_TIMESTAMP,
            "msg_id": msg.get('id', ''),
        })
    except Exception as e:
        logger.warning(f"Failed to store pending clarification: {e}")

    return {
        "status": "clarification_sent",
        "intent": original_intent,
        "clarification_type": clarification_type,
        "cost_usd": 0.0,
    }


def _check_pending_clarification(db, from_email):
    """Check if sender has a pending clarification (< 4h old)."""
    key = f"pending_{hashlib.sha256(from_email.lower().encode()).hexdigest()[:12]}"
    try:
        doc = db.collection("questions_log").document(key).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if not data.get('awaiting_clarification'):
            return None
        # Expire after 4 hours
        created = data.get('created_at')
        if created:
            if hasattr(created, 'timestamp'):
                created_dt = datetime.fromtimestamp(created.timestamp(), tz=timezone.utc)
            elif isinstance(created, datetime):
                created_dt = created.replace(tzinfo=timezone.utc) if created.tzinfo is None else created
            else:
                return data  # can't check age, assume valid
            if (datetime.now(timezone.utc) - created_dt) > timedelta(hours=4):
                return None
        return data
    except Exception as e:
        logger.warning(f"Pending clarification check error: {e}")
        return None


def _resolve_clarification(pending, subject, body_text, msg, db, firestore_module,
                           access_token, rcb_email, get_secret_func):
    """Combine new email's entities with original intent, mark resolved, re-dispatch."""
    # Extract entities from new email body
    combined_text = f"{subject} {body_text}"
    new_entities = _extract_status_entities(combined_text)
    new_entities.update(_extract_customs_entities(combined_text))

    # Merge with original entities
    original_entities = pending.get('original_entities', {})
    merged = {**original_entities, **{k: v for k, v in new_entities.items() if v}}

    # If no new entities found, can't resolve
    if not new_entities:
        return None

    # Mark pending doc as resolved
    from_email = _get_sender_address(msg)
    key = f"pending_{hashlib.sha256(from_email.lower().encode()).hexdigest()[:12]}"
    try:
        db.collection("questions_log").document(key).update({
            "awaiting_clarification": False,
        })
    except Exception as e:
        logger.warning(f"Failed to mark clarification resolved: {e}")

    # Re-dispatch with original intent + merged entities
    original_intent = pending.get('original_intent', 'NONE')
    result = {"intent": original_intent, "entities": merged, "confidence": 0.9}

    try:
        handler_result = _dispatch(original_intent, result, msg, db, firestore_module,
                                   access_token, rcb_email, get_secret_func)
        if handler_result:
            handler_result['entities'] = merged
            handler_result['resolved_from_clarification'] = True
            return handler_result
    except Exception as e:
        logger.warning(f"Clarification dispatch error: {e}")

    return None


# ═══════════════════════════════════════════
#  INTENT HANDLERS
# ═══════════════════════════════════════════

def _handle_admin_instruction(db, firestore_module, msg, entities, access_token, rcb_email):
    """Handle ADMIN_INSTRUCTION — save directive to system_instructions."""
    instruction_text = entities.get('instruction_text', '')
    if not instruction_text:
        return {"status": "skipped", "reason": "empty_instruction"}

    scope = _detect_instruction_scope(instruction_text)
    msg_id = msg.get('id', '')

    try:
        doc_ref = db.collection("system_instructions").document()
        doc_ref.set({
            "instruction": instruction_text,
            "scope": scope,
            "source_email_id": msg_id,
            "created_by": ADMIN_EMAIL,
            "created_at": firestore_module.SERVER_TIMESTAMP,
            "is_active": True,
        })
    except Exception as e:
        logger.error(f"Failed to save system instruction: {e}")
        return {"status": "error", "reason": str(e)}

    # Confirm reply
    reply_html = _wrap_html_rtl(
        f"הוראה נשמרה: {instruction_text[:200]}<br><br>"
        f"תחום: {scope}<br>"
        f"תחול על כל המיילים העתידיים."
    )
    sent = _send_reply_safe(reply_html, msg, access_token, rcb_email)
    return {"status": "replied" if sent else "send_failed", "intent": "ADMIN_INSTRUCTION", "cost_usd": 0.0}


def _handle_correction(db, firestore_module, msg, entities, access_token, rcb_email):
    """Handle CORRECTION — apply Doron's HS code correction to learned_corrections."""
    corrected_hs = entities.get('corrected_hs', '')
    if not corrected_hs:
        return {"status": "skipped", "reason": "no_corrected_hs"}

    original_hs = entities.get('original_hs', '')
    product_desc = entities.get('product_description', '')
    correction_text = entities.get('correction_text', '')
    msg_id = msg.get('id', '')
    subject = msg.get('subject', '')

    # Try to find the classification being corrected from the email thread
    classification_id = ""
    try:
        conv_id = msg.get('conversationId', '')
        if conv_id:
            cls_docs = list(
                db.collection("rcb_classifications")
                .where("conversation_id", "==", conv_id)
                .limit(1).stream()
            )
            for doc in cls_docs:
                classification_id = doc.id
                cls_data = doc.to_dict()
                if not product_desc:
                    product_desc = cls_data.get("product_description", "") or cls_data.get("items", [{}])[0].get("description", "") if cls_data.get("items") else ""
                if not original_hs:
                    original_hs = cls_data.get("suggested_hs", "") or cls_data.get("hs_code", "")
    except Exception as e:
        logger.warning(f"Correction: could not find classification thread: {e}")

    # Write to learned_corrections (Level -1 override)
    corr_id = re.sub(r'[^a-zA-Z0-9]', '_', (product_desc or corrected_hs).lower()[:80])
    try:
        corr_doc = {
            "product": product_desc[:200] if product_desc else f"[correction from email] {subject[:100]}",
            "corrected_code": corrected_hs,
            "original_code": original_hs,
            "source": "email_correction_admin",
            "reason": correction_text[:500],
            "learned_at": datetime.now(timezone.utc).isoformat(),
            "classification_id": classification_id,
            "email_msg_id": msg_id,
        }
        db.collection("learned_corrections").document(f"email_{corr_id}").set(corr_doc, merge=True)
        print(f"  CORRECTION: saved to learned_corrections: {corrected_hs} (was {original_hs})")
    except Exception as e:
        logger.error(f"Failed to save correction: {e}")
        return {"status": "error", "reason": str(e)}

    # Also update the original classification if found
    if classification_id:
        try:
            db.collection("rcb_classifications").document(classification_id).update({
                "status": "corrected",
                "our_hs_code": corrected_hs,
                "corrected_at": firestore_module.SERVER_TIMESTAMP,
                "corrected_by": ADMIN_EMAIL,
            })
        except Exception as e:
            logger.warning(f"Correction: could not update classification {classification_id}: {e}")

    # Confirm reply to Doron
    reply_html = _wrap_html_rtl(
        f"<b>תיקון סיווג נקלט</b><br><br>"
        f"קוד מתוקן: <b>{corrected_hs}</b><br>"
        + (f"קוד קודם: {original_hs}<br>" if original_hs else "")
        + (f"מוצר: {product_desc[:100]}<br>" if product_desc else "")
        + f"<br>התיקון נשמר ויחול על סיווגים עתידיים של מוצר זהה."
    )
    sent = _send_reply_safe(reply_html, msg, access_token, rcb_email)
    return {"status": "replied" if sent else "send_failed", "intent": "CORRECTION", "cost_usd": 0.0}


def _detect_instruction_scope(text):
    """Detect scope of admin instruction."""
    text_lower = text.lower()
    if any(kw in text_lower for kw in ['subject', 'נושא', 'כותרת']):
        return 'tracker_email_subject'
    if any(kw in text_lower for kw in ['template', 'תבנית', 'פורמט', 'format']):
        return 'reply_format'
    if any(kw in text_lower for kw in ['classification', 'סיווג', 'classify']):
        return 'classification_email'
    if any(kw in text_lower for kw in ['email', 'מייל', 'mail']):
        return 'email_format'
    return 'general'


def _handle_status_request(db, entities, msg, access_token, rcb_email,
                           firestore_module=None):
    """Handle STATUS_REQUEST — look up deal in tracker and reply with status."""
    # Check if we have any shipment identifier
    bol = entities.get('bol') or entities.get('bol_msc')
    if not bol and not entities.get('container'):
        if firestore_module:
            return _send_clarification('missing_shipment_id', 'STATUS_REQUEST', entities,
                                       msg, db, firestore_module, access_token, rcb_email)

    try:
        from lib.tracker import _find_deal_by_field, _find_deal_by_container
    except ImportError:
        from tracker import _find_deal_by_field, _find_deal_by_container

    deal_doc = None
    lookup_key = ""

    # Try BL first
    if bol:
        deal_doc = _find_deal_by_field(db, 'bol_number', bol)
        lookup_key = f"BL {bol}"

    # Try container
    if not deal_doc and entities.get('container'):
        deal_doc = _find_deal_by_container(db, entities['container'])
        lookup_key = f"Container {entities['container']}"

    if not deal_doc:
        reply_html = _wrap_html_rtl(
            f"לא נמצאה משלוח תואם עבור {lookup_key or 'הנתונים שצוינו'}.<br>"
            f"אנא וודא את מספר שטר המטען או המכולה ונסה שנית."
        )
        sent = _send_reply_safe(reply_html, msg, access_token, rcb_email)
        return {"status": "replied" if sent else "send_failed", "intent": "STATUS_REQUEST", "cost_usd": 0.0,
                "answer_text": "deal_not_found"}

    deal = deal_doc.to_dict()
    status_text = _build_status_summary(db, deal, deal_doc.id)

    reply_html = _wrap_html_rtl(status_text)
    sent = _send_reply_safe(reply_html, msg, access_token, rcb_email)
    return {"status": "replied" if sent else "send_failed", "intent": "STATUS_REQUEST", "cost_usd": 0.0,
            "answer_text": status_text, "answer_html": reply_html}


def _build_status_summary(db, deal, deal_id):
    """Build Hebrew status summary from deal data."""
    lines = []
    bol = deal.get('bol_number', '')
    containers = deal.get('containers', [])
    status = deal.get('status', 'unknown')
    direction = deal.get('direction', 'import')
    shipping_line = deal.get('shipping_line', '')

    lines.append(f"<b>סטטוס משלוח</b>")
    if bol:
        lines.append(f"שטר מטען: {bol}")
    if shipping_line:
        lines.append(f"חברת ספנות: {shipping_line}")
    if containers:
        lines.append(f"מכולות: {', '.join(containers[:5])}")
    lines.append(f"כיוון: {'יבוא' if direction != 'export' else 'יצוא'}")
    lines.append(f"סטטוס: {status}")

    # Try to get container statuses
    try:
        container_statuses = list(
            db.collection("tracker_container_status")
            .where("deal_id", "==", deal_id)
            .stream()
        )
        if container_statuses:
            lines.append("")
            lines.append("<b>סטטוס מכולות:</b>")
            for cs_doc in container_statuses[:5]:
                cs = cs_doc.to_dict()
                cn = cs.get('container_id', '?')
                proc = cs.get('import_process' if direction != 'export' else 'export_process', {})
                last_step = ""
                for step_name, step_key in [
                    ('cargo exit', 'CargoExitDate'),
                    ('port release', 'PortReleaseDate'),
                    ('customs release', 'CustomsReleaseDate'),
                    ('customs check', 'CustomsCheckDate'),
                    ('delivery order', 'DeliveryOrderDate'),
                    ('port unloading', 'PortUnloadingDate'),
                    ('manifest', 'ManifestDate'),
                ]:
                    if proc.get(step_key):
                        last_step = step_name
                        break
                lines.append(f"  {cn}: {last_step or 'ממתין'}")
    except Exception:
        pass

    # ETA/ATA
    eta = deal.get('eta') or deal.get('eta_pod')
    if eta:
        lines.append(f"ETA: {eta}")

    return "<br>".join(lines)


def _extract_legal_context(result, context_parts):
    """Extract context from search_legal_knowledge result into context_parts.
    Handles all 7 return types from the tool executor."""
    rtype = result.get("type", "")

    # Case A: Single ordinance article (סעיף 130, article 62)
    if rtype == "ordinance_article":
        parts = []
        if result.get("title_he"):
            parts.append(f"סעיף {result.get('article_id', '?')}: {result['title_he']}")
        if result.get("summary_en"):
            parts.append(result["summary_en"][:500])
        # Full Hebrew text from the ordinance (primary source for AI to quote)
        if result.get("full_text_he"):
            parts.append(f"נוסח הסעיף:\n{result['full_text_he'][:2000]}")
        if result.get("definitions"):
            defs = result["definitions"]
            for k, v in (defs.items() if isinstance(defs, dict) else []):
                parts.append(f"  {k}: {str(v)[:200]}")
        if result.get("methods"):
            methods = result["methods"]
            if isinstance(methods, list):
                for m in methods:
                    if isinstance(m, dict):
                        parts.append(f"  שיטה {m.get('number', '?')}: {m.get('name_he', '')} — {m.get('name_en', '')}".strip())
                    else:
                        parts.append(f"  שיטה: {str(m)[:200]}")
            elif isinstance(methods, dict):
                for k, v in methods.items():
                    parts.append(f"  שיטה {k}: {str(v)[:200]}")
        if result.get("key"):
            parts.append(f"עיקרי: {str(result['key'])[:300]}")
        if result.get("critical_rule"):
            parts.append(f"כלל קריטי: {str(result['critical_rule'])[:300]}")
        if result.get("additions"):
            parts.append(f"תוספות: {str(result['additions'])[:500]}")
        if result.get("repealed"):
            parts.append("(סעיף זה בוטל)")
        context_parts.extend(parts)
        return

    # Case B: Chapter article listing (פרק 8)
    if rtype == "ordinance_chapter_articles":
        header = f"פרק {result.get('chapter', '?')}: {result.get('title_he', '')} ({result.get('title_en', '')})"
        context_parts.append(header)
        for art in (result.get("articles") or [])[:10]:
            context_parts.append(f"  סעיף {art.get('id', '?')}: {art.get('title_he', '')} — {art.get('summary_en', '')[:200]}")
        return

    # Case C: Keyword search across ordinance articles
    if rtype == "ordinance_article_search":
        for art in (result.get("articles") or [])[:8]:
            line = f"סעיף {art.get('article_id', '?')} (פרק {art.get('chapter', '?')}): {art.get('title_he', '')} — {art.get('summary_en', '')[:200]}"
            context_parts.append(line)
            # Include text snippet for top results (first 3 only to keep context manageable)
            snippet = art.get("text_snippet", "")
            if snippet and len(context_parts) <= 6:
                context_parts.append(f"  נוסח: {snippet[:300]}")
        return

    # Case D: Single Framework Order article (צו מסגרת סעיף 17)
    if rtype == "framework_order_article":
        parts = []
        if result.get("title_he"):
            parts.append(f"צו מסגרת סעיף {result.get('article_id', '?')}: {result['title_he']}")
        if result.get("summary_en"):
            parts.append(result["summary_en"][:500])
        if result.get("fta_country"):
            parts.append(f"הסכם סחר: {result['fta_country']}")
        if result.get("full_text_he"):
            parts.append(f"נוסח הסעיף:\n{result['full_text_he'][:2000]}")
        if result.get("repealed"):
            parts.append("(סעיף זה בוטל)")
        context_parts.extend(parts)
        return

    # Case E: Keyword search across Framework Order articles
    if rtype == "framework_order_search":
        for art in (result.get("articles") or [])[:8]:
            fta = f" [FTA: {art['fta_country']}]" if art.get("fta_country") else ""
            line = f"צו מסגרת סעיף {art.get('article_id', '?')}: {art.get('title_he', '')}{fta} — {art.get('summary_en', '')[:200]}"
            context_parts.append(line)
            snippet = art.get("text_snippet", "")
            if snippet and len(context_parts) <= 6:
                context_parts.append(f"  נוסח: {snippet[:300]}")
        return

    # Case 1: Firestore ordinance chapter (chapter summary with text field)
    if rtype == "ordinance_chapter":
        if result.get("title_he"):
            context_parts.append(f"פרק {result.get('chapter_number', '?')}: {result['title_he']}")
        if result.get("text"):
            context_parts.append(str(result["text"])[:500])
        return

    # Case 2: Customs agents law
    if rtype == "customs_agents_law":
        if result.get("law_name_he"):
            context_parts.append(result["law_name_he"])
        if result.get("key_topics"):
            context_parts.append("נושאים: " + ", ".join(str(t) for t in result["key_topics"][:10]))
        if result.get("chapter_11_text"):
            context_parts.append(str(result["chapter_11_text"])[:500])
        return

    # Cases 3-4: Reform docs (EU/US standards)
    if rtype == "reform":
        for key in ("reform_name_he", "reform_name_en", "effective_date", "legal_basis", "description"):
            if result.get(key):
                context_parts.append(f"{key}: {str(result[key])[:300]}")
        return

    # Case 5: General Firestore search results
    if isinstance(result.get("results"), list):
        for r in result["results"][:5]:
            title = r.get("title", "") or r.get("doc_id", "")
            context_parts.append(f"מסמך: {title}")
        return

    # Fallback: dump any text-like fields
    for key in ("text", "summary", "content", "title_he", "title_en"):
        if result.get(key):
            context_parts.append(str(result[key])[:500])
            break


# ═══════════════════════════════════════════
#  DOMAIN DETECTION HELPERS
# ═══════════════════════════════════════════

def _detect_domains_safe(text):
    """Detect customs domains from text. Fail-open: returns [] on error."""
    try:
        from lib.intelligence_gate import detect_customs_domain
    except ImportError:
        try:
            from intelligence_gate import detect_customs_domain
        except ImportError:
            return []
    try:
        return detect_customs_domain(text)
    except Exception as e:
        logger.warning(f"Domain detection error (fail-open): {e}")
        return []


def _fetch_domain_articles(detected_domains):
    """Fetch targeted ordinance articles for all detected domains.
    Returns combined list of articles, capped at 20 to avoid context bloat."""
    if not detected_domains:
        return []
    try:
        from lib.intelligence_gate import get_articles_by_domain
    except ImportError:
        try:
            from intelligence_gate import get_articles_by_domain
        except ImportError:
            return []
    articles = []
    seen_ids = set()
    for domain in detected_domains:
        if not domain.get("source_articles"):
            continue
        try:
            domain_arts = get_articles_by_domain(domain)
            for art in domain_arts:
                aid = art.get("article_id")
                if aid and aid not in seen_ids:
                    seen_ids.add(aid)
                    articles.append(art)
        except Exception as e:
            logger.warning(f"Article fetch error for {domain.get('domain')}: {e}")
    # Cap to 20 articles to prevent context overflow
    return articles[:20]


def _handle_customs_question(db, entities, msg, access_token, rcb_email, get_secret_func):
    """Handle CUSTOMS_QUESTION — domain-aware routing + Firestore tools + AI composition.

    Phase 2 from Intelligence Routing Spec:
    1. Detect customs domain (VALUATION, IP, FTA, etc.)
    2. Fetch targeted articles by domain (not flat keyword search)
    3. Supplement with Firestore tools (tariff, regulatory, FTA)
    4. Compose reply with domain-specific context
    """
    try:
        from lib.tool_executors import ToolExecutor
    except ImportError:
        from tool_executors import ToolExecutor

    # Use tool executor with no AI keys (Firestore-only tools)
    executor = ToolExecutor(db, api_key=None, gemini_key=None)
    context_parts = []
    sources = []
    cost = 0.0

    # ──── DOMAIN DETECTION ────
    body_text = _get_body_text(msg)
    subject = msg.get('subject', '') or ''
    full_text = f"{subject} {body_text}".strip()
    detected_domains = _detect_domains_safe(full_text)
    domain_names = [d["domain"] for d in detected_domains]

    # ──── TARGETED ARTICLE RETRIEVAL (by domain) ────
    # Instead of flat keyword search, go directly to the right articles
    domain_articles = _fetch_domain_articles(detected_domains)
    if domain_articles:
        for art in domain_articles:
            parts = [f"סעיף {art['article_id']}: {art['title_he']}"]
            if art.get("summary_en"):
                parts.append(art["summary_en"][:300])
            if art.get("full_text_he"):
                parts.append(f"נוסח הסעיף:\n{art['full_text_he'][:2000]}")
            context_parts.extend(parts)
        sources.append("ordinance_targeted")
        print(f"  🎯 Domain routing: {domain_names} → {len(domain_articles)} targeted articles")

    # ──── SUPPLEMENTAL SEARCHES ────
    # Search based on entities (tariff, regulatory)
    hs_code = entities.get('hs_code')
    product_desc = entities.get('product_description', '')

    if product_desc or hs_code:
        try:
            result = executor.execute("search_tariff", {
                "item_description": product_desc or hs_code or "",
            })
            if result.get('candidates'):
                for c in result['candidates'][:3]:
                    ctx = f"HS {c.get('hs_code', '?')}: {c.get('description_he', c.get('description_en', ''))}"
                    context_parts.append(ctx)
                sources.append("tariff")
        except Exception as e:
            logger.warning(f"search_tariff error: {e}")

    if hs_code:
        try:
            result = executor.execute("check_regulatory", {"hs_code": hs_code})
            if result.get('free_import_order'):
                fio = result['free_import_order']
                if isinstance(fio, list):
                    for item in fio[:3]:
                        context_parts.append(f"דרישת יבוא: {item.get('description', str(item))}")
                elif isinstance(fio, dict):
                    context_parts.append(f"דרישות יבוא: {fio.get('authorities_summary', str(fio))}")
                sources.append("free_import_order")
        except Exception as e:
            logger.warning(f"check_regulatory error: {e}")

    # Fallback: flat keyword search ONLY if domain detection found no articles
    if not domain_articles:
        legal_query = body_text[:200] if body_text else (product_desc or f"HS code {hs_code}" if hs_code else "")
        if legal_query:
            try:
                result = executor.execute("search_legal_knowledge", {"query": legal_query})
                if result and isinstance(result, dict) and result.get("found"):
                    _extract_legal_context(result, context_parts)
                    sources.append("legal_knowledge")
            except Exception as e:
                logger.warning(f"search_legal_knowledge error: {e}")

    # Lookup FTA if origin country detected or FTA_ORIGIN domain matched
    origin = entities.get('origin_country', '')
    if hs_code or origin or product_desc or "FTA_ORIGIN" in domain_names:
        try:
            result = executor.execute("lookup_fta", {
                "hs_code": hs_code or "",
                "origin_country": origin or product_desc or body_text[:200],
            })
            if result and isinstance(result, dict) and result.get('eligible'):
                parts = []
                if result.get('origin_proof'):
                    parts.append(f"תעודת מקור: {result['origin_proof']}")
                if result.get('origin_proof_alt'):
                    parts.append(f"חלופה: {result['origin_proof_alt']}")
                if result.get('preferential_rate'):
                    parts.append(f"שיעור: {result['preferential_rate']}")
                fw_clause = result.get('framework_order_clause', {})
                if fw_clause.get('clause_text'):
                    parts.append(f"צו מסגרת: {fw_clause['clause_text'][:300]}")
                if parts:
                    context_parts.append("FTA: " + " | ".join(parts))
                    sources.append("fta_agreements")
        except Exception:
            pass

    # Build question text
    question = entities.get('product_description', '') or f"HS code {hs_code}" if hs_code else "customs question"
    context = "\n".join(context_parts) if context_parts else ""

    if context:
        # Compose reply using AI (cost ladder)
        reply_text, model = _compose_reply(context, question, get_secret_func)
        cost = 0.005 if model == "chatgpt" else (0.001 if model == "gemini_flash" else 0.0)
    else:
        reply_text = f"לא נמצא מידע על {question} במערכת. אנא פנה לצוות סיווג המכס."
        model = "template"

    reply_html = _wrap_html_rtl(reply_text)

    # Build RCB-branded subject with tracking code
    tracking_code = _generate_query_tracking_code()
    topic_preview = (body_text or subject or question or "שאלה")[:40].strip()
    if domain_names:
        domain_label = domain_names[0].replace("_", " ").title()
        reply_subject = f"RCB | {tracking_code} | {domain_label} | {topic_preview}"
    else:
        reply_subject = f"RCB | {tracking_code} | {topic_preview}"
    sent = _send_reply_safe(reply_html, msg, access_token, rcb_email,
                            subject_override=reply_subject)

    return {
        "status": "replied" if sent else "send_failed",
        "intent": "CUSTOMS_QUESTION",
        "cost_usd": cost,
        "tracking_code": tracking_code,
        "answer_text": reply_text,
        "answer_html": reply_html,
        "answer_sources": sources,
        "compose_model": model,
        "detected_domains": domain_names,
    }


def _handle_knowledge_query(db, msg, access_token, rcb_email, get_secret_func, firestore_module):
    """Handle KNOWLEDGE_QUERY — domain-aware routing + Firestore tools + AI composition.

    Phase 2 from Intelligence Routing Spec:
    1. Detect customs domain first
    2. Fetch targeted articles for detected domain
    3. Supplement with Firestore tools relevant to the domain
    4. Only fall back to flat keyword search if domain detection found nothing
    """
    try:
        from lib.tool_executors import ToolExecutor
    except ImportError:
        from tool_executors import ToolExecutor

    body_text = _get_body_text(msg)
    subject = msg.get('subject', '') or ''
    question = f"{subject} {body_text}".strip()

    # Gather knowledge using Firestore tools (FREE)
    executor = ToolExecutor(db, api_key=None, gemini_key=None)
    context_parts = []
    sources = []

    # ──── DOMAIN DETECTION ────
    detected_domains = _detect_domains_safe(question)
    domain_names = [d["domain"] for d in detected_domains]

    # ──── TARGETED ARTICLE RETRIEVAL (by domain) ────
    domain_articles = _fetch_domain_articles(detected_domains)
    if domain_articles:
        for art in domain_articles:
            parts = [f"סעיף {art['article_id']}: {art['title_he']}"]
            if art.get("summary_en"):
                parts.append(art["summary_en"][:300])
            if art.get("full_text_he"):
                parts.append(f"נוסח הסעיף:\n{art['full_text_he'][:2000]}")
            context_parts.extend(parts)
        sources.append("ordinance_targeted")
        print(f"  🎯 Domain routing: {domain_names} → {len(domain_articles)} targeted articles")

    # ──── DOMAIN-AWARE SUPPLEMENTAL SEARCHES ────
    # Only search tools relevant to detected domains
    should_search_tariff = "CLASSIFICATION" in domain_names or not detected_domains
    should_search_fta = "FTA_ORIGIN" in domain_names or not detected_domains
    should_search_directives = "CLASSIFICATION" in domain_names or not detected_domains
    should_search_framework = "FTA_ORIGIN" in domain_names or "PROCEDURES" in domain_names or not detected_domains

    # Search tariff (for CLASSIFICATION domain or fallback)
    if should_search_tariff:
        try:
            result = executor.execute("search_tariff", {"item_description": question[:200]})
            if result.get('candidates'):
                for c in result['candidates'][:3]:
                    context_parts.append(f"HS {c.get('hs_code', '?')}: {c.get('description_he', '')}")
                sources.append("tariff")
        except Exception:
            pass

    # Fallback: flat keyword legal search ONLY if domain detection found no articles
    if not domain_articles:
        try:
            result = executor.execute("search_legal_knowledge", {"query": question[:200]})
            if result and isinstance(result, dict) and result.get("found"):
                _extract_legal_context(result, context_parts)
                sources.append("legal_knowledge")
        except Exception:
            pass

    # Search classification directives (for CLASSIFICATION or fallback)
    if should_search_directives:
        try:
            result = executor.execute("search_classification_directives", {"query": question[:200]})
            if result and isinstance(result, dict) and result.get('results'):
                for r in result['results'][:2]:
                    context_parts.append(f"הנחיית סיווג: {r.get('title', '')} — {r.get('content', '')[:200]}")
                sources.append("classification_directives")
        except Exception:
            pass

    # Lookup FTA agreements (for FTA_ORIGIN domain or fallback)
    if should_search_fta:
        try:
            result = executor.execute("lookup_fta", {
                "hs_code": "",
                "origin_country": question[:200],
            })
            if result and isinstance(result, dict) and result.get('eligible'):
                parts = []
                if result.get('agreement_name'):
                    parts.append(f"הסכם: {result.get('agreement_name_he', result['agreement_name'])}")
                if result.get('origin_proof'):
                    parts.append(f"תעודת מקור: {result['origin_proof']}")
                if result.get('origin_proof_alt'):
                    parts.append(f"חלופה: {result['origin_proof_alt']}")
                if result.get('preferential_rate'):
                    parts.append(f"שיעור העדפה: {result['preferential_rate']}")
                fw_clause = result.get('framework_order_clause', {})
                if fw_clause.get('clause_text'):
                    parts.append(f"צו מסגרת: {fw_clause['clause_text'][:400]}")
                if parts:
                    context_parts.append("FTA: " + " | ".join(parts))
                    sources.append("fta_agreements")
        except Exception:
            pass

    # Search framework order (for FTA_ORIGIN, PROCEDURES, or fallback)
    if should_search_framework:
        try:
            result = executor.execute("lookup_framework_order", {"query": question[:200]})
            if result and isinstance(result, dict):
                fw_results = result.get('results', [])
                if isinstance(fw_results, list):
                    for r in fw_results[:2]:
                        text = r.get('clause_text', r.get('definition', r.get('text', '')))
                        if text:
                            context_parts.append(f"צו מסגרת: {str(text)[:400]}")
                    if fw_results:
                        sources.append("framework_order")
                elif result.get('clause_text'):
                    context_parts.append(f"צו מסגרת: {result['clause_text'][:400]}")
                    sources.append("framework_order")
                elif result.get('definition'):
                    context_parts.append(f"הגדרה (צו מסגרת): {result['definition'][:400]}")
                    sources.append("framework_order")
        except Exception:
            pass

    context = "\n".join(context_parts) if context_parts else ""
    cost = 0.0

    if context:
        reply_text, model = _compose_reply(context, question, get_secret_func)
        cost = 0.005 if model == "chatgpt" else (0.001 if model == "gemini_flash" else 0.0)
    else:
        # No Firestore results — delegate to existing knowledge_query handler
        try:
            from lib.knowledge_query import handle_knowledge_query
            kq_result = handle_knowledge_query(
                msg=msg, db=db, firestore_module=firestore_module,
                access_token=access_token, rcb_email=rcb_email,
                get_secret_func=get_secret_func,
            )
            return {
                "status": kq_result.get("status", "replied"),
                "intent": "KNOWLEDGE_QUERY",
                "cost_usd": 0.01,  # Claude fallback
                "compose_model": "claude",
                "answer_sources": ["knowledge_query_handler"],
                "detected_domains": domain_names,
            }
        except Exception as e:
            logger.warning(f"knowledge_query fallback error: {e}")
            reply_text = "לא נמצא מידע רלוונטי. אנא נסח את השאלה מחדש או פנה לצוות."
            model = "template"

    reply_html = _wrap_html_rtl(reply_text)

    # Build RCB-branded subject with tracking code
    tracking_code = _generate_query_tracking_code()
    topic_preview = (body_text or subject or "שאלה")[:40].strip()
    if domain_names:
        domain_label = domain_names[0].replace("_", " ").title()
        reply_subject = f"RCB | {tracking_code} | {domain_label} | {topic_preview}"
    else:
        reply_subject = f"RCB | {tracking_code} | {topic_preview}"
    sent = _send_reply_safe(reply_html, msg, access_token, rcb_email,
                            subject_override=reply_subject)

    return {
        "status": "replied" if sent else "send_failed",
        "intent": "KNOWLEDGE_QUERY",
        "cost_usd": cost,
        "tracking_code": tracking_code,
        "answer_text": reply_text,
        "answer_html": reply_html,
        "answer_sources": sources,
        "compose_model": model,
        "detected_domains": domain_names,
    }


def _handle_instruction(db, entities, msg, access_token, rcb_email, get_secret_func,
                        firestore_module=None):
    """Handle INSTRUCTION — route to appropriate action."""
    action = entities.get('action', 'unknown')

    if action == 'classify':
        if not msg.get('hasAttachments', False):
            if firestore_module:
                return _send_clarification('missing_attachment', 'INSTRUCTION', entities,
                                           msg, db, firestore_module, access_token, rcb_email)
        return {"status": "routed", "intent": "INSTRUCTION", "action": "classify", "cost_usd": 0.0}

    if action in ('tracker_update', 'start_tracking'):
        return {"status": "routed", "intent": "INSTRUCTION", "action": "tracker_update", "cost_usd": 0.0}

    if action == 'stop_tracking':
        return _execute_stop_tracking(db, entities, msg, access_token, rcb_email,
                                      firestore_module=firestore_module)

    # Unknown instruction — acknowledge
    reply_html = _wrap_html_rtl(
        "קיבלתי את ההוראה. אנא ציין בצורה מפורשת יותר מה ברצונך לעשות:<br>"
        "- סווג (לסיווג מכס)<br>"
        "- הוסף מכולה (למעקב)<br>"
        "- הפסק מעקב"
    )
    sent = _send_reply_safe(reply_html, msg, access_token, rcb_email)
    return {"status": "replied" if sent else "send_failed", "intent": "INSTRUCTION", "action": action, "cost_usd": 0.0}


def _stop_deal(db, deal_doc):
    """Stop a single deal — set both status and follow_mode to stopped."""
    db.collection("tracker_deals").document(deal_doc.id).update({
        "status": "stopped",
        "follow_mode": "stopped",
        "stopped_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


def _execute_stop_tracking(db, entities, msg, access_token, rcb_email,
                           firestore_module=None):
    """Execute stop tracking — find deals and set status+follow_mode to stopped."""
    # If no specific BL/container, ask for clarification instead of stopping all
    bol = entities.get('bol') or entities.get('bol_msc')
    container = entities.get('container')
    if not bol and not container:
        if firestore_module:
            return _send_clarification('missing_stop_target', 'INSTRUCTION', entities,
                                       msg, db, firestore_module, access_token, rcb_email)

    from_email = _get_sender_address(msg)

    try:
        from lib.tracker import _find_deal_by_field, _find_deal_by_container
    except ImportError:
        from tracker import _find_deal_by_field, _find_deal_by_container

    stopped_deals = []

    if bol:
        deal_doc = _find_deal_by_field(db, 'bol_number', bol)
        if deal_doc:
            _stop_deal(db, deal_doc)
            stopped_deals.append(f"BL {bol}")

    if container and not stopped_deals:
        deal_doc = _find_deal_by_container(db, container)
        if deal_doc:
            _stop_deal(db, deal_doc)
            stopped_deals.append(f"Container {container}")

    if stopped_deals:
        deals_text = ", ".join(stopped_deals)
        reply_html = _wrap_html_rtl(
            f"<b>מעקב הופסק</b><br>"
            f"הפסקנו לעקוב אחרי: {deals_text}<br><br>"
            f"<span style='color:#888;font-size:12px;'>כדי לחדש מעקב, השב עם: follow [מספר BL]</span>"
        )
    else:
        reply_html = _wrap_html_rtl(
            "לא נמצאו משלוחים פעילים במעקב שלך.<br>"
            "אנא ציין מספר BL או מכולה ספציפי."
        )

    sent = _send_reply_safe(reply_html, msg, access_token, rcb_email)

    return {
        "status": "replied" if sent else "send_failed",
        "intent": "INSTRUCTION",
        "action": "stop_tracking",
        "cost_usd": 0.0,
        "deals_stopped": len(stopped_deals),
        "answer_text": f"Stopped {len(stopped_deals)} deals",
    }


def _handle_non_work(msg, access_token, rcb_email):
    """Handle NON_WORK — canned reply."""
    reply_html = _wrap_html_rtl(
        "RCB היא מערכת סיווג מכס וסחר בינלאומי. "
        "לשאלות מכס וסחר בינלאומי, אשמח לעזור. "
        "לשאלות כלליות, אנא פנה למקורות אחרים."
    )
    sent = _send_reply_safe(reply_html, msg, access_token, rcb_email)
    return {"status": "replied" if sent else "send_failed", "intent": "NON_WORK", "cost_usd": 0.0}


# ═══════════════════════════════════════════
#  DISPATCHER
# ═══════════════════════════════════════════

def _dispatch(intent, result, msg, db, firestore_module,
              access_token, rcb_email, get_secret_func):
    """Route intent to appropriate handler."""
    entities = result.get('entities', {})

    if intent == 'ADMIN_INSTRUCTION':
        return _handle_admin_instruction(db, firestore_module, msg, entities,
                                         access_token, rcb_email)
    if intent == 'CORRECTION':
        return _handle_correction(db, firestore_module, msg, entities,
                                  access_token, rcb_email)
    if intent == 'NON_WORK':
        return _handle_non_work(msg, access_token, rcb_email)

    if intent == 'STATUS_REQUEST':
        return _handle_status_request(db, entities, msg, access_token, rcb_email,
                                      firestore_module=firestore_module)

    if intent == 'INSTRUCTION':
        return _handle_instruction(db, entities, msg, access_token,
                                   rcb_email, get_secret_func,
                                   firestore_module=firestore_module)

    if intent == 'CUSTOMS_QUESTION':
        return _handle_customs_question(db, entities, msg, access_token,
                                        rcb_email, get_secret_func)

    if intent == 'KNOWLEDGE_QUERY':
        return _handle_knowledge_query(db, msg, access_token, rcb_email,
                                       get_secret_func, firestore_module)

    return {"status": "no_handler", "intent": intent}


# ═══════════════════════════════════════════
#  QUESTIONS LOG
# ═══════════════════════════════════════════

def _log_question(db, firestore_module, subject, body_text, from_email,
                  detection_result, handler_result, msg_id):
    """Log question and answer to questions_log collection."""
    q_hash = _question_hash(subject, body_text)
    privilege = _get_sender_privilege(from_email)

    try:
        doc_data = {
            "question_hash": q_hash,
            "question_text": f"{subject} {body_text}"[:2000],
            "intent": detection_result.get('intent', ''),
            "entities": detection_result.get('entities', {}),
            "from_email": from_email.lower(),
            "sender_privilege": privilege,
            "answer_text": handler_result.get('answer_text', '')[:5000] if handler_result else '',
            "answer_html": handler_result.get('answer_html', '')[:10000] if handler_result else '',
            "answer_sources": handler_result.get('answer_sources', []) if handler_result else [],
            "detection_method": detection_result.get('detection_method', 'regex'),
            "compose_model": handler_result.get('compose_model', '') if handler_result else '',
            "cost_usd": handler_result.get('cost_usd', 0.0) if handler_result else 0.0,
            "created_at": firestore_module.SERVER_TIMESTAMP,
            "hit_count": 0,
            "msg_id": msg_id,
        }
        db.collection("questions_log").document(q_hash).set(doc_data)
    except Exception as e:
        logger.warning(f"questions_log write error: {e}")


# ═══════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════

def process_email_intent(msg, db, firestore_module, access_token, rcb_email, get_secret_func):
    """Main entry — detect intent and handle. Returns dict with status."""
    subject = msg.get('subject', '')
    body_text = _get_body_text(msg)
    from_email = _get_sender_address(msg)

    # ── HARD RULE: sender privilege check ──
    privilege = _get_sender_privilege(from_email)
    if privilege == "NONE":
        return {"status": "skipped", "reason": "external_sender"}

    # Check if this is a reply to a previous clarification (before body length check —
    # a valid clarification reply may be just a BL number like "MEDURS12345")
    pending = _check_pending_clarification(db, from_email)
    if pending:
        resolved = _resolve_clarification(pending, subject, body_text, msg, db,
                                          firestore_module, access_token, rcb_email, get_secret_func)
        if resolved:
            _log_question(db, firestore_module, subject, body_text, from_email,
                          {"intent": pending['original_intent'], "entities": resolved.get('entities', {})},
                          resolved, msg.get('id', ''))
            return resolved

    # Skip if body is too short (auto-generated/notification)
    if len(body_text.strip()) < 15:
        return {"status": "skipped", "reason": "body_too_short"}

    # Rate limit: max 1 reply per sender per hour
    if _is_rate_limited(db, from_email):
        return {"status": "skipped", "reason": "rate_limited"}

    # Check questions_log cache first
    cached = _check_cache(db, subject, body_text)
    if cached:
        sent = _send_reply_safe(cached['answer_html'], msg, access_token, rcb_email)
        if sent:
            _increment_hit_count(db, cached['question_hash'])
        return {"status": "cache_hit" if sent else "send_failed", "intent": cached['intent']}

    # Detect intent (pass privilege for ADMIN_INSTRUCTION detection)
    result = detect_email_intent(subject, body_text, from_email,
                                 privilege=privilege, get_secret_func=get_secret_func)
    intent = result['intent']

    if intent == 'NONE':
        # For non-trivial body text, send ambiguous clarification
        if len(body_text.strip()) >= 30:
            return _send_clarification('ambiguous_intent', 'NONE', {},
                                       msg, db, firestore_module, access_token, rcb_email)
        return {"status": "no_intent"}

    # ADMIN-only intents
    if intent in ('ADMIN_INSTRUCTION', 'CORRECTION') and privilege != 'ADMIN':
        return {"status": "skipped", "reason": "not_admin"}

    # Handle
    handler_result = _dispatch(intent, result, msg, db, firestore_module,
                               access_token, rcb_email, get_secret_func)

    # Log to questions_log (all intents, not just questions)
    _log_question(db, firestore_module, subject, body_text, from_email,
                  result, handler_result, msg.get('id', ''))

    return handler_result
