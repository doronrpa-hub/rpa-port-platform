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

# Composition layer (Session 87)
try:
    from lib.direction_router import detect_direction
    from lib.evidence_types import build_evidence_bundle
    from lib.straitjacket_prompt import build_straitjacket_prompt, parse_ai_response, is_valid_response, needs_escalation
    from lib.reply_composer import compose_consultation, verify_citations
    _COMPOSITION_AVAILABLE = True
except ImportError:
    try:
        from direction_router import detect_direction
        from evidence_types import build_evidence_bundle
        from straitjacket_prompt import build_straitjacket_prompt, parse_ai_response, is_valid_response, needs_escalation
        from reply_composer import compose_consultation, verify_citations
        _COMPOSITION_AVAILABLE = True
    except ImportError:
        _COMPOSITION_AVAILABLE = False

# Tariff tree (Session 95)
try:
    from lib.tariff_tree import get_subtree as _tree_get_subtree
    _TARIFF_TREE_AVAILABLE = True
except ImportError:
    try:
        from tariff_tree import get_subtree as _tree_get_subtree
        _TARIFF_TREE_AVAILABLE = True
    except ImportError:
        _TARIFF_TREE_AVAILABLE = False

# ═══════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════

ADMIN_EMAIL = "doron@rpa-port.co.il"
TEAM_DOMAIN = "rpa-port.co.il"

REPLY_SYSTEM_PROMPT = (
    "אתה RCB — מערכת מידע מכס של ר.פ.א פורט בע\"מ, עמיל מכס מורשה.\n"
    "אנחנו עמיל המכס. לעולם אל תכתוב 'מומלץ לפנות לעמיל מכס'.\n\n"
    "*** מבנה התשובה — חובה לעקוב ***\n"
    "כל תשובה חייבת להיות בדיוק במבנה הזה:\n\n"
    "1. תשובה ישירה (2-3 משפטים בעברית — ענה על השאלה ישירות)\n"
    "2. ציטוט מהחוק (צטט מילה במילה את הסעיפים הרלוונטיים מהמקורות שסופקו):\n"
    "   «סעיף X לפקודת המכס: [ציטוט מלא בעברית]»\n"
    "   אם יש מספר סעיפים רלוונטיים — צטט את כולם (עד 5). אל תדלג.\n"
    "3. הסבר בעברית פשוטה (הסבר מה הסעיף אומר בפועל, כמו שמסבירים ללקוח)\n"
    "4. מידע נוסף (לוחות זמנים, שיעורי מכס, דרישות, צעדים מעשיים — אם רלוונטי)\n"
    "5. English Summary (תרגום קצר לאנגלית, 3-5 משפטים, מופרד בקו)\n\n"
    "*** כללים מחייבים ***\n"
    "- ענה בעברית RTL. אנגלית רק בסעיף 5 בתחתית.\n"
    "- השתמש אך ורק במקורות שסופקו. אל תמציא מידע, קודי HS או נוסח חוק.\n"
    "- אם סעיפים סופקו בהקשר — חובה לצטט אותם. לעולם אל תתעלם מהמקורות.\n"
    "- אם ההקשר מכיל סעיפי IP (200א-200ה) — אלה עוסקים באכיפת קניין רוחני.\n"
    "  אל תכתוב שפקודת המכס אינה עוסקת בכך.\n"
    "- אם אין מקור חוקי ספציפי — ציין: 'לא נמצא מקור חוקי ספציפי במערכת'\n"
    "- כתוב בשפה פשוטה ומקצועית. לא ז'רגון משפטי יבש.\n"
    "מונחים: עמיל מכס / סוכן מכס — לעולם לא מתווך מכס."
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

# TARIFF_SUBTREE: user asks for the full heading/chapter breakdown
# Matches: "תביאי לי את פרט מכס 84.36 במלואו", "הצגי פרט 03.06",
#          "show me heading 84.36", "כל פרט 84.36"
_TARIFF_SUBTREE_RE = re.compile(
    r'(?:תביא[י]?|הצג[י]?|הראה|תראי?|כל\s*ה?פרט|show|display|full|את\s*(?:כל\s*)?(?:ה?פרט|heading))'
    r'.*?'
    r'(?:פרט\s*(?:ה?מכס\s*)?|heading\s*|hs\s*)?'
    r'(\d{2}[.\s]?\d{2}(?:[.\s]?\d{2,6})?)',
    re.IGNORECASE
)


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
        # Product-specific customs patterns
        r'(?:פרט\s*(?:ה?מכס|מכסי)|שיעור\s*(?:ה?מכס|מכסי))',
        r'(?:מה\s*(?:פרט|שיעור)\s*(?:ה?מכס|מכסי))',
        r'(?:מה\s*(?:צריך|נדרש)\s*(?:כדי\s*)?(?:ליבא|לייבא|ליצא|לייצא))',
        r'(?:(?:ליבא|לייבא|ליצא|לייצא)\s+.{3,}?\s*(?:ל?ישראל|\?))',
        r'(?:יבוא\s+.{3,}\s*(?:מ|מה|ל?ישראל))',
        r'(?:מכס\s+על\s+(?:יבוא|ייבוא|יצוא|ייצוא))',
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
    # Product description — text after common prepositions/patterns (Hebrew + English)
    # Priority order: most specific patterns first
    desc_patterns = [
        # "פרט המכס ל..." / "מכס על..."
        r'(?:פרט\s*(?:ה?מכס|מכסי)\s*(?:ל|של|על)\s*)(.{3,80}?)(?:\?|$|\.)',
        # "שיעור המכס על יבוא..."
        r'(?:שיעור\s*(?:ה?מכס|מכסי)\s*(?:על|ל)\s*(?:יבוא|ייבוא)?\s*)(.{3,80}?)(?:\?|$|\.)',
        # "לייבא/ליצא X"
        r'(?:ליבא|לייבא|ליצא|לייצא)\s+(.{3,80}?)(?:\s*(?:ל?ישראל|מ\S+)?\s*(?:\?|$|\.))',
        # "יבוא X מ..."
        r'(?:יבוא|ייבוא|יצוא|ייצוא)\s+(.{3,60}?)(?:\s*(?:מ|ל)\S*\s*(?:\?|$|\.))',
        # "מכס על יבוא X"
        r'(?:מכס\s+על\s+(?:יבוא|ייבוא)?\s*)(.{3,60}?)(?:\s*(?:מ|ל)\S*\s*(?:\?|$|\.))',
        # "של X" / "עבור X" / "for X" / "on X"
        r'(?:for|של|עבור|on)\s+(.{5,80}?)(?:\?|$|\.)',
        # "סיווג X" / "לסווג X"
        r'(?:סיווג|לסווג|הסיווג\s+(?:של|ל))\s+(.{3,80}?)(?:\?|$|\.)',
    ]
    for pat in desc_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            desc = m.group(1).strip().rstrip('?.,! ')
            # Skip if it's just a country name (< 3 words, common country pattern)
            if desc and len(desc) > 2:
                entities['product_description'] = desc
                break

    # Fallback: extract product from "יבוא/מכס" context in the full text
    if not entities.get('product_description'):
        # Try extracting the core product noun from the question
        fb_match = re.search(
            r'(?:מה\s+(?:צריך|נדרש)\s+(?:כדי\s+)?(?:ליבא|לייבא)\s+)(.{3,60}?)(?:\s*(?:ל|מ)\S*\s*)?(?:\?|$|\.)',
            text, re.IGNORECASE
        )
        if fb_match:
            entities['product_description'] = fb_match.group(1).strip().rstrip('?.,! ')

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
                    {"role": "user", "content": (
                        f"שאלה: {question}\n\n"
                        "=== מקורות משפטיים מוסמכים (ענה רק מתוכם) ===\n"
                        f"{context}\n"
                        "=== סוף מקורות ===\n"
                        "עקוב אחרי מבנה התשובה: 1) תשובה ישירה 2) ציטוט מילה במילה מהסעיפים "
                        "3) הסבר בעברית פשוטה 4) מידע נוסף 5) English Summary.\n"
                        "צטט את כל הסעיפים הרלוונטיים מהמקורות, לא רק אחד.")},
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
    prompt = (
        f"{REPLY_SYSTEM_PROMPT}\n\n"
        f"שאלה: {question}\n\n"
        "=== מקורות משפטיים מוסמכים (ענה רק מתוכם) ===\n"
        f"{context}\n"
        "=== סוף מקורות ===\n"
        "עקוב אחרי מבנה התשובה: 1) תשובה ישירה 2) ציטוט מילה במילה מהסעיפים "
        "3) הסבר בעברית פשוטה 4) מידע נוסף 5) English Summary.\n"
        "צטט את כל הסעיפים הרלוונטיים מהמקורות, לא רק אחד."
    )
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
    """Template-based reply when no AI is available.

    Structures the raw context into a readable Hebrew reply following
    the 5-section format: answer, citation, explanation, additional info, English.
    """
    if not context:
        return "לא נמצא מידע רלוונטי במערכת לשאלה זו."
    # Extract article sections from context
    lines = context.split('\n')
    article_blocks = []
    other_lines = []
    current_block = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_block:
                article_blocks.append('\n'.join(current_block))
                current_block = []
            continue
        if re.search(r'^סעיף \d', stripped) or stripped.startswith('נוסח הסעיף'):
            current_block.append(stripped)
        elif current_block:
            current_block.append(stripped)
        else:
            other_lines.append(stripped)
    if current_block:
        article_blocks.append('\n'.join(current_block))

    parts = []
    if article_blocks:
        parts.append("להלן הסעיפים הרלוונטיים מפקודת המכס:\n")
        for block in article_blocks:
            # Cap each article at 1500 chars to fit multiple articles
            parts.append(block[:1500])
            parts.append("")  # blank line separator
    if other_lines:
        parts.append("מידע נוסף:")
        for line in other_lines[:10]:
            parts.append(f"• {line[:300]}")
    return '\n'.join(parts)


def _validate_reply_uses_context(reply_text, context):
    """Validate that the AI reply actually uses the provided legal context.

    If context contains articles 200א+ (IP enforcement) but the reply doesn't
    mention "200", the AI ignored the context and answered from training data.
    Returns the reply text, possibly with a warning prepended.
    """
    if not context or not reply_text:
        return reply_text
    # Check if context contains articles 200א-200יד (IP enforcement articles)
    has_ip_articles = bool(re.search(r'200[אבגדהוזחטייכלמנ]', context) or
                          re.search(r'סעיף 200', context))
    if has_ip_articles:
        reply_mentions_200 = '200' in reply_text
        if not reply_mentions_200:
            logger.warning("AI-IGNORED-CONTEXT: Context contains articles 200א+ "
                           "but reply does not mention them. Prepending correction.")
            # Check for contradictory statements
            contradiction_patterns = [
                'אינו עוסק',
                'אינה עוסקת',
                'לא עוסק',
                'לא עוסקת',
                'אין התייחסות',
                'אין סעיף',
            ]
            has_contradiction = any(p in reply_text for p in contradiction_patterns)
            if has_contradiction:
                logger.warning("AI-IGNORED-CONTEXT: Reply CONTRADICTS provided context "
                               "(claims law doesn't cover the topic)")
                # Replace the contradictory reply entirely with context-based answer
                article_lines = []
                for line in context.split('\n'):
                    if re.search(r'סעיף 200|200[אבגדהוזחטייכלמנ]', line):
                        article_lines.append(line.strip())
                if article_lines:
                    reply_text = (
                        "פקודת המכס כן עוסקת בנושא זה. "
                        "להלן הסעיפים הרלוונטיים:\n\n" +
                        "\n\n".join(article_lines[:5])
                    )
            else:
                # Reply doesn't contradict but also doesn't cite — prepend reminder
                article_refs = re.findall(r'סעיף (200[אבגדהוזחטייכלמנ]?)', context)
                if article_refs:
                    unique_refs = list(dict.fromkeys(article_refs))[:5]
                    refs_str = ", ".join(unique_refs)
                    reply_text = (
                        f"שים לב: סעיפים {refs_str} לפקודת המכס רלוונטיים לשאלה זו.\n\n"
                        + reply_text
                    )
    return reply_text


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
    if not is_direct_recipient(msg, rcb_email, sole=True):
        print(f"  📭 Reply suppressed — rcb@ not sole TO recipient (from={from_email})")
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

    # Try threaded reply first, fallback to send with conversationId for threading
    sent = helper_graph_reply(access_token, rcb_email, msg_id, body_html,
                              to_email=from_email, subject=subject)
    if not sent:
        conv_id = msg.get('conversationId')
        sent = helper_graph_send(access_token, rcb_email, from_email,
                                 subject, body_html, conversation_id=conv_id)
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


def _build_candidates_table_html(candidates, product_desc=""):
    """Build an HTML table of tariff candidates for CUSTOMS_QUESTION replies.

    Returns HTML string with table + clarification prompts, or empty string if no candidates.
    """
    if not candidates:
        return ""

    rows = []
    for i, c in enumerate(candidates[:5], 1):
        hs = c.get('hs_code', '?')
        desc = c.get('description_he', c.get('description_en', ''))
        duty = c.get('duty_rate', c.get('mfn_rate', '—'))
        rows.append(
            f'<tr><td style="padding:6px 8px;border:1px solid #dee2e6;text-align:center">{i}</td>'
            f'<td style="padding:6px 8px;border:1px solid #dee2e6;direction:ltr;font-family:monospace">{hs}</td>'
            f'<td style="padding:6px 8px;border:1px solid #dee2e6">{desc[:120]}</td>'
            f'<td style="padding:6px 8px;border:1px solid #dee2e6;text-align:center">{duty}</td></tr>'
        )

    product_note = f'<p style="margin:0 0 8px 0;color:#495057">עבור: <strong>{product_desc[:80]}</strong></p>' if product_desc else ''

    # Product-specific clarification questions
    clarification = _build_clarification_html(product_desc)

    return f'''<div style="background:#f8f9fa;border:1px solid #dee2e6;border-radius:4px;padding:12px;margin:10px 0;direction:rtl">
    <p style="margin:0 0 8px 0;font-weight:bold;color:#1B4F72">פרטי מכס אפשריים:</p>
    {product_note}
    <table dir="rtl" style="width:100%;border-collapse:collapse;font-size:13px">
        <tr style="background:#1B4F72;color:white">
            <th style="padding:8px;border:1px solid #ddd">#</th>
            <th style="padding:8px;border:1px solid #ddd">פרט מכס</th>
            <th style="padding:8px;border:1px solid #ddd">תיאור מתעריף</th>
            <th style="padding:8px;border:1px solid #ddd">שיעור מכס</th>
        </tr>
        {"".join(rows)}
    </table>
    {clarification}
</div>'''


def _build_clarification_html(product_desc=""):
    """Build product-specific clarification questions HTML."""
    pd = (product_desc or "").lower()

    # Default questions
    questions = [
        "חומר גלם (פלסטיק/מתכת/עץ/בד/אחר)",
        "שימוש מיועד",
        "מדינת מקור",
    ]

    # Product-specific questions
    if any(w in pd for w in ["קפה", "coffee", "אספרסו", "espresso"]):
        questions = [
            "סוג המכונה — אספרסו/פילטר/קפסולות?",
            "ביתית או מסחרית/תעשייתית?",
            "עם מטחנה מובנית?",
            "מדינת מקור",
        ]
    elif any(w in pd for w in ["צעצוע", "toy", "משחק", "בובה", "game"]):
        questions = [
            "סוג הצעצוע — בובה/משחק לוח/אלקטרוני/פלסטיק?",
            "חומר — פלסטיק/עץ/מתכת/בד?",
            "גיל יעד",
            "מדינת מקור",
        ]
    elif any(w in pd for w in ["גבינה", "cheese", "חלב", "milk", "dairy"]):
        questions = [
            "סוג הגבינה — קשה/רכה/מעובדת/טרייה?",
            "אחוז שומן",
            "מדינת מקור (לבדיקת הסכם סחר)",
            "האם יש תעודת מקור EUR.1 או חשבון הצהרה?",
        ]
    elif any(w in pd for w in ["רכב", "car", "vehicle", "מכונית"]):
        questions = [
            "סוג — נוסעים/מסחרי/חשמלי?",
            "נפח מנוע (סמ\"ק)",
            "חדש או משומש?",
            "מדינת ייצור",
        ]
    elif any(w in pd for w in ["בגד", "cloth", "textile", "בד", "shirt", "חולצה"]):
        questions = [
            "סוג הבגד",
            "חומר — כותנה/פוליאסטר/צמר/תערובת?",
            "לגברים/נשים/ילדים?",
            "סרוג או ארוג?",
        ]

    q_lines = "".join(f"<br>{i}. {q}" for i, q in enumerate(questions, 1))

    return f'''<div dir="rtl" style="background:#FFF3CD;padding:10px;border-radius:5px;margin:10px 0 0 0;font-size:13px">
    <strong>לסיווג מדויק, אנא פרט:</strong>{q_lines}
</div>'''


def _build_fta_info_html(fta_result, tariff_candidates=None, product_desc=""):
    """Build FTA info HTML section for questions about preferential rates.

    Shows: agreement name, origin proof, preferential rate, and origin requirement note.
    """
    if not fta_result or not isinstance(fta_result, dict) or not fta_result.get('eligible'):
        return ""

    rows = []
    agreement = fta_result.get('agreement_name_he', fta_result.get('agreement_name', ''))
    pref_rate = fta_result.get('preferential_rate', '—')
    origin_proof = fta_result.get('origin_proof', '')
    origin_proof_alt = fta_result.get('origin_proof_alt', '')

    # Build rate comparison row if we have tariff candidates with duty rates
    rate_rows = ""
    if tariff_candidates:
        for c in tariff_candidates[:3]:
            hs = c.get('hs_code', '?')
            desc = c.get('description_he', c.get('description_en', ''))[:80]
            mfn = c.get('duty_rate', c.get('mfn_rate', '—'))
            rate_rows += (
                f'<tr>'
                f'<td style="padding:6px 8px;border:1px solid #ddd;font-family:monospace;direction:ltr">{hs}</td>'
                f'<td style="padding:6px 8px;border:1px solid #ddd">{desc}</td>'
                f'<td style="padding:6px 8px;border:1px solid #ddd;text-align:center">{mfn}</td>'
                f'<td style="padding:6px 8px;border:1px solid #ddd;text-align:center;color:#155724;font-weight:bold">{pref_rate}</td>'
                f'</tr>'
            )

    rate_table = ""
    if rate_rows:
        rate_table = f'''<table dir="rtl" style="width:100%;border-collapse:collapse;font-size:13px;margin:8px 0">
        <tr style="background:#1B4F72;color:white">
            <th style="padding:8px;border:1px solid #ddd">פרט מכס</th>
            <th style="padding:8px;border:1px solid #ddd">תיאור</th>
            <th style="padding:8px;border:1px solid #ddd">מכס רגיל (MFN)</th>
            <th style="padding:8px;border:1px solid #ddd">מכס {agreement or "העדפה"}</th>
        </tr>
        {rate_rows}
    </table>'''

    # Origin proof requirement
    origin_note = ""
    if origin_proof:
        origin_note = f'<p style="margin:4px 0;font-size:13px">📄 <strong>תעודת מקור:</strong> {origin_proof}'
        if origin_proof_alt:
            origin_note += f' או {origin_proof_alt}'
        origin_note += '</p>'

    fw_clause = fta_result.get('framework_order_clause', {})
    fw_text = ""
    if fw_clause.get('clause_text'):
        fw_text = f'<p style="margin:4px 0;font-size:12px;color:#495057">צו מסגרת: {fw_clause["clause_text"][:300]}</p>'

    return f'''<div dir="rtl" style="background:#D4EDDA;border:1px solid #C3E6CB;border-radius:4px;padding:12px;margin:10px 0">
    <p style="margin:0 0 8px 0;font-weight:bold;color:#155724">🌐 הסכם סחר חופשי: {agreement}</p>
    {rate_table}
    {origin_note}
    <p style="margin:4px 0;font-size:13px">⚠️ <strong>תנאי:</strong> השיעור המופחת מותנה בהצגת תעודת מקור / חשבון הצהרה בעת השחרור</p>
    {fw_text}
</div>'''


def _try_composition_pipeline(db, msg, access_token, rcb_email, get_secret_func):
    """Try the Session 87 composition pipeline for structured replies.

    Returns result dict if successful, None to fall back to legacy.
    """
    if not _COMPOSITION_AVAILABLE:
        return None

    try:
        from lib.context_engine import prepare_context_package
    except ImportError:
        try:
            from context_engine import prepare_context_package
        except ImportError:
            return None

    try:
        from lib.classification_agents import call_gemini, call_chatgpt, call_claude
    except ImportError:
        try:
            from classification_agents import call_gemini, call_chatgpt, call_claude
        except ImportError:
            return None

    try:
        subject = (msg.get("subject") or "").strip()
        body_text = _get_body_text(msg)

        # 1. SIF — System Intelligence First
        context_package = prepare_context_package(subject, body_text, db, get_secret_func)

        # 2. Direction detection
        direction_result = detect_direction(subject, body_text,
                                            entities=context_package.entities)

        # 3. Build evidence bundle
        bundle = build_evidence_bundle(context_package, direction_result)

        # Skip composition if no evidence at all
        if not bundle.sources_found:
            return None

        # 4. Build straitjacket prompt
        prompt = build_straitjacket_prompt(bundle)

        # 5. AI with escalation ladder (Gemini → ChatGPT → Claude)
        ai_text = None
        model_used = None

        if call_gemini and get_secret_func:
            try:
                gk = (get_secret_func("GEMINI_API_KEY") or "").strip()
                if gk:
                    ai_text = call_gemini(gk, prompt["system"], prompt["user"],
                                          max_tokens=2500)
                    model_used = "gemini"
            except Exception:
                pass

        parsed = parse_ai_response(ai_text) if ai_text else None
        reason = needs_escalation(parsed)

        if reason and call_chatgpt and get_secret_func:
            try:
                ok = (get_secret_func("OPENAI_API_KEY") or "").strip()
                if ok:
                    ai_text = call_chatgpt(ok, prompt["system"], prompt["user"],
                                           max_tokens=2500)
                    parsed = parse_ai_response(ai_text) if ai_text else parsed
                    model_used = "chatgpt"
                    reason = needs_escalation(parsed)
            except Exception:
                pass

        if reason and call_claude and get_secret_func:
            try:
                ak = (get_secret_func("ANTHROPIC_API_KEY") or "").strip()
                if ak:
                    ai_text = call_claude(ak, prompt["system"], prompt["user"],
                                          max_tokens=2500)
                    parsed = parse_ai_response(ai_text) if ai_text else parsed
                    model_used = "claude"
            except Exception:
                pass

        if not parsed or not is_valid_response(parsed):
            return None

        # 6. Compose HTML
        recipient_name = (msg.get("from", {}).get("emailAddress", {}).get("name") or "")
        if recipient_name:
            recipient_name = recipient_name.split("@")[0].split(".")[0].strip()

        composed = compose_consultation(parsed, bundle, recipient_name=recipient_name)

        # 7. Send
        sent = _send_reply_safe(composed["html"], msg, access_token, rcb_email,
                                subject_override=composed["subject"])

        cost = {"gemini": 0.001, "chatgpt": 0.005, "claude": 0.01}.get(model_used, 0)
        return {
            "status": "replied" if sent else "send_failed",
            "intent": "CONSULTATION",
            "cost_usd": cost,
            "tracking_code": composed["tracking_code"],
            "answer_html": composed["html"][:10000],
            "compose_model": f"composition_{model_used}",
            "answer_sources": bundle.sources_found,
        }

    except Exception as e:
        logger.warning(f"Composition pipeline error in email_intent: {e}")
        return None


# ═══════════════════════════════════════════
#  TARIFF SUBTREE HANDLER (Session 95)
# ═══════════════════════════════════════════

def _handle_tariff_subtree(db, hs_code, msg, access_token, rcb_email):
    """Handle tariff subtree request — return full heading tree as 6-column HTML table.

    Called when user asks for 'פרט מכס XX.XX במלואו' or similar.
    Strategy: XML tree (hierarchical) > unified index flat list > Firestore fallback.
    """
    heading_4 = hs_code.replace('.', '').replace(' ', '')[:4]
    subtree = None
    sources = []

    # Try XML tree first (available locally, not in Cloud Functions)
    if _TARIFF_TREE_AVAILABLE:
        try:
            subtree = _tree_get_subtree(hs_code, db)
            if subtree and subtree.get('children'):
                sources.append("tariff_tree")
        except Exception as e:
            logger.warning(f"Tariff tree error: {e}")

    # Load duty rates + flat subcodes from unified index
    duty_map = {}
    flat_subcodes = []
    try:
        try:
            from lib._unified_search import get_heading_subcodes
        except ImportError:
            from _unified_search import get_heading_subcodes
        for sc in get_heading_subcodes(heading_4, leaves_only=False):
            raw = sc.get('hs_raw', '').split('_')[0]
            duty_map[raw] = {
                'duty': sc.get('duty_rate', ''),
                'pt': sc.get('purchase_tax', ''),
            }
            flat_subcodes.append(sc)
        if flat_subcodes:
            sources.append("unified_index")
    except Exception as e:
        logger.warning(f"Unified index lookup error: {e}")

    # Enrich duty_map from Firestore — adds unit, check_digit, hs_code_formatted, duty text
    if db:
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter
            try:
                from lib.librarian import _hs_check_digit
            except ImportError:
                from librarian import _hs_check_digit
            fs_docs = list(db.collection("tariff").where(
                filter=FieldFilter("heading", "==", f"{heading_4[:2]}.{heading_4[2:4]}")
            ).stream())
            for doc in fs_docs:
                d = doc.to_dict()
                if d.get("corrupt_code"):
                    continue
                raw_key = doc.id.split('_')[0]
                existing = duty_map.get(raw_key, {})
                # Compute check digit if missing
                chk = d.get('check_digit', '')
                hs_fmt = d.get('hs_code_formatted', '')
                if not chk and len(raw_key) == 10 and raw_key.isdigit():
                    chk = _hs_check_digit(raw_key)
                # Ensure hs_code_formatted includes check digit
                if hs_fmt and '/' not in hs_fmt and chk:
                    hs_fmt = f"{hs_fmt}/{chk}"
                duty_map[raw_key] = {
                    'duty': d.get('customs_duty', '') or existing.get('duty', ''),
                    'pt': d.get('purchase_tax', '') or existing.get('pt', ''),
                    'unit': d.get('unit', ''),
                    'check_digit': chk,
                    'hs_code_formatted': hs_fmt,
                }
            if fs_docs:
                sources.append("firestore_tariff")
        except Exception as e:
            logger.warning(f"Firestore tariff enrichment error: {e}")

    # Firestore fallback if both tree and unified index empty
    if not subtree and not flat_subcodes and db:
        try:
            prefix_lo = heading_4.ljust(10, '0')
            prefix_hi = heading_4.ljust(9, '9') + '9'
            docs = db.collection("tariff").where(
                "__name__", ">=", prefix_lo
            ).where(
                "__name__", "<=", prefix_hi
            ).stream()
            for doc in docs:
                data = doc.to_dict()
                if data.get("corrupt_code"):
                    continue
                flat_subcodes.append({
                    "hs_code": doc.id,
                    "hs_raw": doc.id,
                    "description_he": data.get("description_he", data.get("description", "")),
                    "description_en": data.get("description_en", ""),
                    "duty_rate": data.get("duty_rate", ""),
                    "purchase_tax": data.get("purchase_tax", ""),
                })
                duty_map[doc.id] = {
                    "duty": data.get("duty_rate", ""),
                    "pt": data.get("purchase_tax", ""),
                }
            if flat_subcodes:
                sources.append("firestore_tariff")
        except Exception as e:
            logger.warning(f"Firestore tariff fallback error: {e}")

    # Nothing found at all
    if not subtree and not flat_subcodes:
        return None

    # If no XML tree, build a synthetic subtree dict from flat subcodes
    if not subtree and flat_subcodes:
        subtree = _build_synthetic_subtree(hs_code, heading_4, flat_subcodes)

    # Load chapter notes
    chapter_num = heading_4[:2]
    chapter_notes_html = _fetch_chapter_notes_for_heading(db, chapter_num, hs_code)

    # Build HTML
    html = _build_subtree_html(subtree, duty_map, chapter_notes_html, hs_code)

    # Build subject
    tracking_code = _generate_query_tracking_code()
    reply_subject = f"RCB | {tracking_code} | פרט מכס {hs_code}"

    sent = _send_reply_safe(html, msg, access_token, rcb_email,
                            subject_override=reply_subject)

    return {
        "status": "replied" if sent else "send_failed",
        "intent": "CUSTOMS_QUESTION",
        "sub_intent": "tariff_subtree",
        "cost_usd": 0.0,
        "tracking_code": tracking_code,
        "answer_html": html[:10000],
        "compose_model": "tariff_tree",
        "answer_sources": sources + ["chapter_notes"],
    }


def _build_synthetic_subtree(hs_code, heading_4, flat_subcodes):
    """Build a subtree dict from flat subcodes (when XML tree not available)."""
    heading_desc_he = ""
    heading_desc_en = ""
    children = []
    for sc in sorted(flat_subcodes, key=lambda x: x.get('hs_raw', '') or x.get('hs_code', '')):
        raw = (sc.get('hs_raw', '') or sc.get('hs_code', '')).split('_')[0].replace('.', '').replace('/', '')
        hs_fmt = sc.get('hs_code', '')
        if not hs_fmt or hs_fmt == raw:
            # Format it
            if len(raw) >= 4:
                padded = raw.ljust(10, '0')[:10]
                hs_fmt = f"{padded[:2]}.{padded[2:4]}.{padded[4:10]}"
        desc_he = sc.get('description_he', '')
        desc_en = sc.get('description_en', '')

        # Check if this is the heading itself (4-digit level)
        trimmed = raw.rstrip('0')
        if len(trimmed) <= 4:
            heading_desc_he = desc_he
            heading_desc_en = desc_en
            continue

        # Determine depth by trailing zeros
        depth = 1
        if len(raw) >= 6 and raw[4:6] != '00':
            depth = 1
        if len(raw) >= 8 and raw[6:8] != '00':
            depth = 2
        if len(raw) >= 10 and raw[8:10] != '00':
            depth = 3

        children.append({
            'fc': raw,
            'hs': hs_fmt,
            'level': 4 + depth - 1,
            'desc_he': desc_he,
            'desc_en': desc_en,
            'children': [],
        })

    hs_dotted = f"{heading_4[:2]}.{heading_4[2:4]}"
    return {
        'fc': heading_4.ljust(10, '0'),
        'hs': hs_dotted,
        'level': 3,
        'desc_he': heading_desc_he,
        'desc_en': heading_desc_en,
        'children': children,
    }


def _fetch_chapter_notes_for_heading(db, chapter_num, hs_code):
    """Fetch chapter notes and subheading rules relevant to a heading."""
    if db is None:
        return ""
    try:
        if len(chapter_num) == 1:
            chapter_num = "0" + chapter_num
        doc = db.collection("chapter_notes").document(f"chapter_{chapter_num}").get()
        if not doc.exists:
            return ""
        data = doc.to_dict()
        parts = []

        # Chapter preamble
        preamble = data.get("preamble", "")
        if preamble:
            parts.append(f"<strong>הערות לפרק {chapter_num}:</strong><br>{preamble[:2000]}")

        # Subheading rules — filter to those mentioning this heading
        heading_digits = hs_code.replace('.', '').replace(' ', '')[:4]
        heading_dot = f"{heading_digits[:2]}.{heading_digits[2:4]}"
        sub_rules = data.get("subheading_rules", [])
        relevant_rules = []
        for rule in sub_rules:
            if heading_digits in str(rule) or heading_dot in str(rule):
                relevant_rules.append(str(rule))
        if relevant_rules:
            parts.append(f"<strong>כללים לפרטי משנה ({heading_dot}):</strong><br>" +
                         "<br>".join(relevant_rules[:5]))

        # Notes array
        notes = data.get("notes", [])
        if notes:
            notes_text = "<br>".join(str(n)[:500] for n in notes[:5])
            parts.append(f"<strong>הערות:</strong><br>{notes_text}")

        return "<br><br>".join(parts)
    except Exception as e:
        logger.warning(f"Chapter notes fetch error: {e}")
        return ""


def _build_subtree_html(subtree, duty_map, chapter_notes_html, hs_code):
    """Build 6-column HTML tariff table from subtree dict.

    Columns: פרט | תיאור | מכס כללי | מס קנייה | שיעור התוספות | יחידה
    """
    # Flatten the tree into rows with indent level
    rows_data = []

    def _flatten(node, depth=0, parent_unit=''):
        fc_raw = node.get('fc', '').replace('.', '').replace(' ', '').split('/')[0]
        dm = duty_map.get(fc_raw, {})
        # Use hs_code_formatted from Firestore (has check digit) or fall back to tree hs
        hs_display = dm.get('hs_code_formatted', '') or node.get('hs', '')
        # Unit: own value, or inherit from parent heading
        unit = dm.get('unit', '') or parent_unit
        rows_data.append({
            'hs': hs_display,
            'desc_he': (node.get('desc_he', '') or '').replace('\n', ' '),
            'desc_en': (node.get('desc_en', '') or '').replace('\n', ' '),
            'duty': dm.get('duty', ''),
            'pt': dm.get('pt', ''),
            'supplement': '',
            'unit': unit,
            'depth': depth,
            'level': node.get('level', 0),
        })
        for child in node.get('children', []):
            _flatten(child, depth + 1, unit)

    _flatten(subtree)

    # Build HTML rows
    table_rows = []
    has_patur = False
    for r in rows_data:
        indent = r['depth'] * 16
        is_heading = r['level'] <= 3
        weight = 'bold' if is_heading else 'normal'
        bg = '#f0f4f8' if is_heading else '#ffffff'
        desc = r['desc_he']
        if r['desc_en'] and not is_heading:
            desc += f'<br><span style="color:#888;font-size:11px;direction:ltr;unicode-bidi:embed">{r["desc_en"][:100]}</span>'

        duty_display = r['duty'].strip() if r['duty'] else '—'
        pt_display = r['pt'].strip() if r['pt'] else '—'
        unit_display = r['unit'].strip() if r['unit'] else '—'

        # Track if any duty/pt shows פטור for footnote
        if 'פטור' in duty_display or 'פטור' in pt_display:
            has_patur = True

        table_rows.append(f'''<tr style="background:{bg};">
  <td style="padding:6px 8px;border:1px solid #dee2e6;font-family:monospace;font-size:13px;direction:ltr;white-space:nowrap;text-align:center;font-weight:{weight}">{r['hs']}</td>
  <td style="padding:6px 8px;border:1px solid #dee2e6;padding-right:{indent + 8}px;font-weight:{weight}">{desc}</td>
  <td style="padding:6px 8px;border:1px solid #dee2e6;text-align:center;">{duty_display}</td>
  <td style="padding:6px 8px;border:1px solid #dee2e6;text-align:center;">{pt_display}</td>
  <td style="padding:6px 8px;border:1px solid #dee2e6;text-align:center;">{r['supplement']}</td>
  <td style="padding:6px 8px;border:1px solid #dee2e6;text-align:center;">{unit_display}</td>
</tr>''')

    # Chapter notes section
    notes_section = ""
    if chapter_notes_html:
        notes_section = f'''<div style="background:#fef9e7;border:1px solid #f9e79f;border-radius:4px;padding:12px;margin:0 0 16px 0;direction:rtl;font-size:13px;line-height:1.6;">
{chapter_notes_html}
</div>'''

    heading_desc = (subtree.get('desc_he', '') or '').replace('\n', ' ')

    return f'''<div dir="rtl" style="font-family: Arial, sans-serif; direction: rtl; text-align: right;">
<div style="background:linear-gradient(135deg, #1e3a5f, #2471a3);color:white;padding:16px 20px;border-radius:6px 6px 0 0;">
  <div style="font-size:11px;opacity:0.8;">ר.פ.א פורט | RCB</div>
  <div style="font-size:20px;font-weight:bold;margin-top:4px;">פרט מכס {hs_code}</div>
  <div style="font-size:13px;margin-top:4px;opacity:0.9;">{heading_desc}</div>
</div>

<div style="padding:16px 20px;background:#fff;border:1px solid #dee2e6;border-top:none;">

{notes_section}

<table dir="rtl" style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:16px;">
  <thead>
    <tr style="background:#1e3a5f;color:white;">
      <th style="padding:10px 8px;border:1px solid #1e3a5f;width:16%;">פרט</th>
      <th style="padding:10px 8px;border:1px solid #1e3a5f;">תיאור</th>
      <th style="padding:10px 8px;border:1px solid #1e3a5f;width:10%;text-align:center;">מכס כללי</th>
      <th style="padding:10px 8px;border:1px solid #1e3a5f;width:10%;text-align:center;">מס קנייה</th>
      <th style="padding:10px 8px;border:1px solid #1e3a5f;width:10%;text-align:center;">שיעור התוספות</th>
      <th style="padding:10px 8px;border:1px solid #1e3a5f;width:8%;text-align:center;">יחידה</th>
    </tr>
  </thead>
  <tbody>
    {"".join(table_rows)}
  </tbody>
</table>

{"" if not has_patur else '<div style="background:#fff8e1;border:1px solid #ffe082;border-radius:4px;padding:10px 12px;margin:0 0 12px 0;font-size:12px;color:#5d4037;direction:rtl;line-height:1.6;">* <strong>פטור</strong> — פטור ממכס ו/או ממס קנייה בהתאם לצו תעריף המכס. ייתכן ששיעורי מכס מופחתים חלים מכוח הסכמי סחר חופשי (FTA) — יש לבדוק זכאות לפי ארץ המקור ותעודת מקור מתאימה.</div>'}

<div style="color:#888;font-size:11px;border-top:1px solid #eee;padding-top:8px;">
מקור: עץ תעריף המכס הישראלי (XML) + Firestore | {len(rows_data)} פרטים
</div>

</div>

<div style="background:#f8f9fa;padding:12px 20px;border:1px solid #dee2e6;border-top:none;border-radius:0 0 6px 6px;">
<div style="color:#888;font-size:12px;">
RCB — מערכת אוטומטית לסיווג מכס וסחר בינלאומי<br>
ר.פ.א פורט בע"מ | עמיל מכס מורשה
</div>
</div>
</div>'''


def _handle_customs_question(db, entities, msg, access_token, rcb_email, get_secret_func):
    """Handle CUSTOMS_QUESTION — domain-aware routing + Firestore tools + AI composition.

    Phase 2 from Intelligence Routing Spec:
    1. Detect customs domain (VALUATION, IP, FTA, etc.)
    2. Fetch targeted articles by domain (not flat keyword search)
    3. Supplement with Firestore tools (tariff, regulatory, FTA)
    4. Compose reply with domain-specific context
    """
    # Session 95: Tariff subtree lookup — MUST be first (before composition pipeline)
    body_text_raw = _get_body_text(msg)
    subject_raw = msg.get('subject', '') or ''
    combined_text = f"{subject_raw} {body_text_raw}"
    subtree_match = _TARIFF_SUBTREE_RE.search(combined_text)
    logger.info(f"SUBTREE_CHECK: pattern match={bool(subtree_match)}, tree_available={_TARIFF_TREE_AVAILABLE}")
    if subtree_match:
        matched_code = subtree_match.group(1).replace(' ', '')
        # Normalize to XX.XX format
        digits = matched_code.replace('.', '')
        if len(digits) >= 4:
            hs_dotted = f"{digits[:2]}.{digits[2:4]}"
            if len(digits) > 4:
                hs_dotted = f"{digits[:2]}.{digits[2:4]}.{digits[4:]}"
        else:
            hs_dotted = matched_code
        print(f"  🌳 Tariff subtree request detected: {hs_dotted}")
        subtree_result = _handle_tariff_subtree(db, hs_dotted, msg, access_token, rcb_email)
        if subtree_result:
            return subtree_result

    # Try composition pipeline (Session 87)
    composed = _try_composition_pipeline(db, msg, access_token, rcb_email, get_secret_func)
    if composed:
        composed["intent"] = "CUSTOMS_QUESTION"
        return composed

    # Legacy path below
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
    tariff_candidates = []

    # ALWAYS search tariff — use product_desc, hs_code, or body text as fallback
    tariff_query = product_desc or hs_code or body_text[:200]
    if tariff_query:
        try:
            result = executor.execute("search_tariff", {
                "item_description": tariff_query,
            })
            if result.get('candidates'):
                tariff_candidates = result['candidates'][:5]
                for c in tariff_candidates[:3]:
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
    fta_result = None
    if hs_code or origin or product_desc or "FTA_ORIGIN" in domain_names:
        try:
            result = executor.execute("lookup_fta", {
                "hs_code": hs_code or "",
                "origin_country": origin or product_desc or body_text[:200],
            })
            if result and isinstance(result, dict) and result.get('eligible'):
                fta_result = result
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

    # ──── XML DOCUMENTS: FTA protocol text, tariff sections, amendments ────
    # Search xml_documents when FTA or import/export requirements detected
    if "FTA_ORIGIN" in domain_names or "IMPORT_EXPORT_REQUIREMENTS" in domain_names:
        xml_query = origin or product_desc or body_text[:200]
        xml_category = "fta" if "FTA_ORIGIN" in domain_names else None
        if xml_query:
            try:
                xml_inp = {"query": xml_query}
                if xml_category:
                    xml_inp["category"] = xml_category
                result = executor.execute("search_xml_documents", xml_inp)
                if result and isinstance(result, dict) and result.get("found"):
                    for doc in (result.get("documents") or [])[:3]:
                        parts = [f"מסמך: {doc.get('title', doc.get('doc_id', ''))}"]
                        if doc.get("text_excerpt"):
                            parts.append(doc["text_excerpt"][:1000])
                        context_parts.extend(parts)
                    sources.append("xml_documents")
            except Exception as e:
                logger.warning(f"search_xml_documents error: {e}")

    # Build question text
    question = entities.get('product_description', '') or f"HS code {hs_code}" if hs_code else "customs question"
    context = "\n".join(context_parts) if context_parts else ""

    if context:
        # Compose reply using AI (cost ladder)
        reply_text, model = _compose_reply(context, question, get_secret_func)
        reply_text = _validate_reply_uses_context(reply_text, context)
        cost = 0.005 if model == "chatgpt" else (0.001 if model == "gemini_flash" else 0.0)
    else:
        reply_text = f"לא נמצא מידע על {question} במערכת. אנא פנה לצוות סיווג המכס."
        model = "template"

    reply_html = _wrap_html_rtl(reply_text)

    # Append structured candidates table if tariff results found
    candidates_html = _build_candidates_table_html(tariff_candidates, product_desc)
    if candidates_html:
        reply_html = reply_html + candidates_html

    # Append FTA info section if FTA result found
    fta_html = _build_fta_info_html(fta_result, tariff_candidates, product_desc)
    if fta_html:
        reply_html = reply_html + fta_html

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
    if not sent:
        logger.warning(f"CUSTOMS_QUESTION reply send failed for {msg.get('from', {}).get('emailAddress', {}).get('address', '?')} — subject: {reply_subject}")

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
    # Try composition pipeline first (Session 87)
    composed = _try_composition_pipeline(db, msg, access_token, rcb_email, get_secret_func)
    if composed:
        composed["intent"] = "KNOWLEDGE_QUERY"
        return composed

    # Legacy path below
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
        # Budget: distribute text space across all articles
        n_articles = len(domain_articles)
        chars_per_article = max(500, 6000 // max(n_articles, 1))
        for art in domain_articles:
            parts = [f"סעיף {art['article_id']}: {art['title_he']}"]
            if art.get("summary_en"):
                parts.append(art["summary_en"][:200])
            if art.get("full_text_he"):
                parts.append(f"נוסח הסעיף:\n{art['full_text_he'][:chars_per_article]}")
            context_parts.extend(parts)
            context_parts.append("")  # blank line separator between articles
        sources.append("ordinance_targeted")
        print(f"  🎯 Domain routing: {domain_names} → {len(domain_articles)} targeted articles")

    # ──── DOMAIN-AWARE SUPPLEMENTAL SEARCHES ────
    # Only search tools relevant to detected domains
    should_search_tariff = "CLASSIFICATION" in domain_names or not detected_domains
    should_search_fta = "FTA_ORIGIN" in domain_names or not detected_domains
    should_search_directives = "CLASSIFICATION" in domain_names or not detected_domains
    should_search_framework = "FTA_ORIGIN" in domain_names or "PROCEDURES" in domain_names or not detected_domains
    should_search_regulatory = "IMPORT_EXPORT_REQUIREMENTS" in domain_names or "CLASSIFICATION" in domain_names

    # Search tariff (for CLASSIFICATION domain or fallback)
    # ALWAYS search tariff for IMPORT_EXPORT_REQUIREMENTS too (need HS codes for permit lookup)
    should_search_tariff = should_search_tariff or "IMPORT_EXPORT_REQUIREMENTS" in domain_names
    tariff_candidates = []
    if should_search_tariff:
        try:
            result = executor.execute("search_tariff", {"item_description": question[:200]})
            if result.get('candidates'):
                tariff_candidates = result['candidates'][:5]
                for c in tariff_candidates[:3]:
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
    fta_result = None
    if should_search_fta:
        try:
            result = executor.execute("lookup_fta", {
                "hs_code": "",
                "origin_country": question[:200],
            })
            if result and isinstance(result, dict) and result.get('eligible'):
                fta_result = result
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

    # Search regulatory (for IMPORT_EXPORT_REQUIREMENTS or CLASSIFICATION)
    if should_search_regulatory:
        try:
            # Try to extract an HS code from tariff results or question
            hs_match = re.search(r'\b(\d{4})[.\s]?(\d{2})', question)
            if hs_match:
                hs_code = hs_match.group(1) + hs_match.group(2)
                result = executor.execute("check_regulatory", {"hs_code": hs_code})
                if result and isinstance(result, dict):
                    reqs = result.get('requirements', [])
                    if reqs:
                        context_parts.append(f"דרישות יבוא עבור {hs_code}:")
                        for req in reqs[:5]:
                            context_parts.append(f"  • {req.get('authority', '')} — {req.get('requirement', '')}")
                        sources.append("free_import_order")
        except Exception:
            pass

    # ──── XML DOCUMENTS: search for all domains ────
    # Map domains to xml_documents categories where applicable
    _xml_category_map = {
        "FTA_ORIGIN": "fta",
        "CLASSIFICATION": "tariff",
        "VALUATION": "legal",
        "PROCEDURES": "legal",
        "IP_ENFORCEMENT": "legal",
        "IMPORT_EXPORT_REQUIREMENTS": "regulatory",
        "FORFEITURE_PENALTIES": "legal",
    }
    xml_categories = set()
    for dn in domain_names:
        cat = _xml_category_map.get(dn)
        if cat:
            xml_categories.add(cat)
    if not xml_categories and not domain_articles:
        xml_categories.add("legal")  # fallback
    for cat in xml_categories:
        try:
            xml_inp = {"query": question[:200], "category": cat}
            result = executor.execute("search_xml_documents", xml_inp)
            if result and isinstance(result, dict) and result.get("found"):
                for doc in (result.get("documents") or [])[:2]:
                    parts = [f"מסמך: {doc.get('title', doc.get('doc_id', ''))}"]
                    if doc.get("text_excerpt"):
                        parts.append(doc["text_excerpt"][:800])
                    context_parts.extend(parts)
                if "xml_documents" not in sources:
                    sources.append("xml_documents")
        except Exception:
            pass

    context = "\n".join(context_parts) if context_parts else ""
    cost = 0.0

    if context:
        reply_text, model = _compose_reply(context, question, get_secret_func)
        reply_text = _validate_reply_uses_context(reply_text, context)
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

    # Append structured candidates table if tariff results found
    # Extract product desc from question text for clarification context
    _kq_product_desc = ""
    _kq_pd_match = re.search(
        r'(?:ליבא|לייבא|ליצא|לייצא|יבוא|סיווג|מכס\s+(?:על|ל))\s+(.{3,60}?)(?:\s*(?:ל|מ)\S*\s*)?(?:\?|$|\.)',
        question, re.IGNORECASE
    )
    if _kq_pd_match:
        _kq_product_desc = _kq_pd_match.group(1).strip().rstrip('?.,! ')
    candidates_html = _build_candidates_table_html(tariff_candidates, _kq_product_desc)
    if candidates_html:
        reply_html = reply_html + candidates_html

    # Append FTA info section if FTA result found
    fta_html = _build_fta_info_html(fta_result, tariff_candidates, _kq_product_desc)
    if fta_html:
        reply_html = reply_html + fta_html

    # Session 82: Append compliance citations if available
    try:
        from lib.compliance_auditor import render_citation_badges_html, Citation
        _cite_list = []
        for s in sources:
            if s == "ordinance_targeted":
                _cite_list.append(Citation("customs_ordinance", "", "פקודת המכס", "", "supporting"))
            elif s == "framework_order":
                _cite_list.append(Citation("framework_order", "", "צו מסגרת", "", "supporting"))
            elif s == "fta_agreements":
                _cite_list.append(Citation("fta_eu", "", "הסכמי סחר", "", "informational"))
            elif s == "free_import_order":
                _cite_list.append(Citation("free_import_order", "", "צו יבוא חופשי", "", "informational"))
        if _cite_list:
            badges = render_citation_badges_html(_cite_list)
            if badges:
                reply_html = reply_html + badges
    except Exception:
        pass  # fail-open

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
    if not sent:
        logger.warning(f"KNOWLEDGE_QUERY reply send failed for {msg.get('from', {}).get('emailAddress', {}).get('address', '?')} — subject: {reply_subject}")

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

    # ── Tariff subtree early exit — fires regardless of intent classification ──
    if intent in ('CUSTOMS_QUESTION', 'KNOWLEDGE_QUERY'):
        body_text_raw = _get_body_text(msg)
        subject_raw = msg.get('subject', '') or ''
        combined_text = f"{subject_raw} {body_text_raw}"
        subtree_match = _TARIFF_SUBTREE_RE.search(combined_text)
        logger.info(f"SUBTREE_CHECK: intent={intent}, pattern_match={bool(subtree_match)}, tree_available={_TARIFF_TREE_AVAILABLE}")
        if subtree_match:
            matched_code = subtree_match.group(1).replace(' ', '')
            digits = matched_code.replace('.', '')
            if len(digits) >= 4:
                hs_dotted = f"{digits[:2]}.{digits[2:4]}"
                if len(digits) > 4:
                    hs_dotted = f"{digits[:2]}.{digits[2:4]}.{digits[4:]}"
            else:
                hs_dotted = matched_code
            print(f"  🌳 Tariff subtree request detected: {hs_dotted}")
            subtree_result = _handle_tariff_subtree(db, hs_dotted, msg, access_token, rcb_email)
            if subtree_result:
                return subtree_result

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
