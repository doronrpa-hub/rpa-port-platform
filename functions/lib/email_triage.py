"""
Three-Layer Email Triage System
===============================
Classifies incoming emails into categories before routing to handlers.

Layer 0: Auto-skip (noreply, OOO, auto-replies, self-loop, tiny body)
Layer 1a: Reply thread detection (Re:/Fwd: + conversationId)
Layer 1b: Regex pre-classify (shipment/consultation/casual patterns)
Layer 1c: Gemini Flash classification (when regex is inconclusive)
Fallback: CONSULTATION (safest default for a customs broker mailbox)

Categories: SKIP, REPLY_THREAD, CASUAL, LIVE_SHIPMENT, CONSULTATION
"""

import re
from dataclasses import dataclass
from typing import Optional

# ═══════════════════════════════════════════
#  TRIAGE RESULT
# ═══════════════════════════════════════════

@dataclass
class TriageResult:
    category: str           # SKIP, REPLY_THREAD, CASUAL, LIVE_SHIPMENT, CONSULTATION
    confidence: float       # 0.0 - 1.0
    source: str             # "layer0", "regex", "gemini", "fallback"
    skip_reason: Optional[str] = None
    sub_intent: Optional[str] = None
    conversation_id: Optional[str] = None


# ═══════════════════════════════════════════
#  LAYER 0: AUTO-SKIP
# ═══════════════════════════════════════════

_OOO_PATTERNS = re.compile(
    r'(?:automatic\s*reply|out\s*of\s*office|אני\s*לא\s*במשרד|השבה\s*אוטומטית|autoreply|auto[_-]reply)',
    re.IGNORECASE
)

_NOREPLY_SENDERS = ('noreply@', 'no-reply@', 'mailer-daemon', 'postmaster@')


def _layer0_auto_skip(msg, sender_email, rcb_email):
    """Layer 0: Auto-skip obvious non-actionable emails.
    Returns TriageResult(SKIP) or None if email should proceed.
    """
    sender_lower = (sender_email or "").lower()

    # Self-loop prevention
    if sender_lower == rcb_email.lower():
        return TriageResult("SKIP", 1.0, "layer0", skip_reason="self_email")

    # Noreply / mailer-daemon / postmaster
    if any(pat in sender_lower for pat in _NOREPLY_SENDERS):
        return TriageResult("SKIP", 1.0, "layer0", skip_reason="noreply_sender")

    # OOO / auto-reply subject
    subject = (msg.get("subject") or "").strip()
    if _OOO_PATTERNS.search(subject):
        return TriageResult("SKIP", 1.0, "layer0", skip_reason="auto_reply_subject")

    # Auto-response headers
    headers = msg.get("internetMessageHeaders") or []
    for h in headers:
        name_lower = (h.get("name") or "").lower()
        if name_lower == "x-auto-response-suppress":
            return TriageResult("SKIP", 1.0, "layer0", skip_reason="x_auto_response_header")
        if name_lower == "auto-submitted":
            val = (h.get("value") or "").lower().strip()
            if val != "no":
                return TriageResult("SKIP", 1.0, "layer0", skip_reason="auto_submitted_header")

    # Tiny body
    body_content = (msg.get("body", {}).get("content") or msg.get("bodyPreview") or "").strip()
    # Strip HTML tags for length check
    plain = re.sub(r'<[^>]+>', '', body_content).strip()
    if len(plain) < 15:
        return TriageResult("SKIP", 1.0, "layer0", skip_reason="body_too_short")

    return None


# ═══════════════════════════════════════════
#  LAYER 1a: REPLY THREAD DETECTION
# ═══════════════════════════════════════════

_REPLY_FWD_RE = re.compile(
    r'^(?:re|fwd?|השב|הע)\s*:', re.IGNORECASE
)


def _check_reply_thread(msg):
    """Layer 1a: Detect reply/forward threads.
    Returns TriageResult(REPLY_THREAD) or None.
    """
    subject = (msg.get("subject") or "").strip()
    conversation_id = msg.get("conversationId")

    if _REPLY_FWD_RE.search(subject) and conversation_id:
        return TriageResult(
            "REPLY_THREAD", 0.8, "regex",
            conversation_id=conversation_id
        )
    return None


# ═══════════════════════════════════════════
#  LAYER 1b: REGEX PRE-CLASSIFY
# ═══════════════════════════════════════════

_SHIPMENT_PATTERNS = [
    re.compile(r'[A-Z]{3}U\d{7}', re.IGNORECASE),                    # Container ISO 6346
    re.compile(r'\b(?:b/?l|bill\s*of\s*lading|שטר\s*מטען)\b', re.IGNORECASE),
    re.compile(r'\b(?:mawb|hawb|air\s*waybill)\b', re.IGNORECASE),
    re.compile(r'\b(?:track|status|מעקב|סטטוס)\b', re.IGNORECASE),
    re.compile(r'\b(?:vessel|אניי?ה)\b', re.IGNORECASE),
    re.compile(r'\b(?:container|מכולה)\b', re.IGNORECASE),
]

_CONSULTATION_PATTERNS = [
    re.compile(r'\d{4}\.\d{2}\.\d{2}'),                               # HS code format
    re.compile(r'\b(?:tariff|תעריף)\b', re.IGNORECASE),
    re.compile(r'\b(?:customs|מכס)\b', re.IGNORECASE),
    re.compile(r'\b(?:ordinance|פקודה|פקודת)\b', re.IGNORECASE),
    re.compile(r'\b(?:fta|הסכם\s*סחר)\b', re.IGNORECASE),
    re.compile(r'\b(?:classification|סיווג)\b', re.IGNORECASE),
    re.compile(r'\b(?:import\s*order|צו\s*יבוא)\b', re.IGNORECASE),
    re.compile(r'\b(?:duty|מס\s*מכס|אגרה)\b', re.IGNORECASE),
    re.compile(r'\b(?:regulation|תקנה|תקנות)\b', re.IGNORECASE),
]

_CASUAL_PATTERNS = [
    re.compile(r'\b(?:שלום|היי|הי)\b', re.IGNORECASE),
    re.compile(r'\b(?:בוקר\s*טוב|ערב\s*טוב)\b', re.IGNORECASE),
    re.compile(r'\b(?:מה\s*שלומך|מה\s*נשמע)\b', re.IGNORECASE),
    re.compile(r'\b(?:תודה|תודה\s*רבה)\b', re.IGNORECASE),
    re.compile(r'\b(?:hello|hi|hey)\b', re.IGNORECASE),
    re.compile(r'\b(?:good\s*morning|good\s*evening)\b', re.IGNORECASE),
    re.compile(r'\b(?:thanks|thank\s*you)\b', re.IGNORECASE),
    re.compile(r'\b(?:joke|בדיחה)\b', re.IGNORECASE),
    re.compile(r'\b(?:מזג\s*אוויר|weather)\b', re.IGNORECASE),
]


def _regex_pre_classify(subject, body):
    """Layer 1b: Score text against pattern sets.
    Returns TriageResult or None if inconclusive.
    """
    combined = f"{subject} {body}".strip()
    if not combined:
        return None

    scores = {}
    for category, patterns in [
        ("LIVE_SHIPMENT", _SHIPMENT_PATTERNS),
        ("CONSULTATION", _CONSULTATION_PATTERNS),
        ("CASUAL", _CASUAL_PATTERNS),
    ]:
        matches = sum(1 for p in patterns if p.search(combined))
        scores[category] = matches / len(patterns) if patterns else 0

    # Find highest and second highest
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_cat, best_score = ranked[0]
    _, second_score = ranked[1]

    # Require: score >= 0.3 AND dominant (1.5x the runner-up)
    if best_score >= 0.3 and (second_score == 0 or best_score > second_score * 1.5):
        return TriageResult(best_cat, best_score, "regex")

    return None


# ═══════════════════════════════════════════
#  LAYER 1c: GEMINI CLASSIFICATION
# ═══════════════════════════════════════════

_GEMINI_CLASSIFY_PROMPT = (
    "Classify this email into exactly one category. "
    "Reply ONLY with JSON {\"category\": \"...\", \"confidence\": 0.0-1.0}\n"
    "Categories:\n"
    "- CASUAL (greetings, chat, jokes, general knowledge, weather)\n"
    "- CONSULTATION (customs law, tariffs, HS codes, FTA, regulations, import/export questions)\n"
    "- LIVE_SHIPMENT (tracking, cargo status, container/BL inquiries)\n"
    "- SKIP (spam, newsletters, marketing)\n"
)


def _gemini_classify(subject, body, get_secret_func):
    """Layer 1c: Use Gemini Flash for classification when regex is inconclusive.
    Returns TriageResult or None on error.
    """
    if not get_secret_func:
        return None

    gemini_key = get_secret_func("GEMINI_API_KEY")
    if not gemini_key:
        return None

    try:
        from lib.classification_agents import call_gemini
    except ImportError:
        try:
            from classification_agents import call_gemini
        except ImportError:
            return None

    user_prompt = f"Subject: {subject}\nBody: {body[:500]}"

    try:
        raw = call_gemini(gemini_key, _GEMINI_CLASSIFY_PROMPT, user_prompt, max_tokens=200)
        if not raw:
            return None

        import json
        # Try to extract JSON from response
        text = raw.strip()
        # Handle markdown fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        parsed = json.loads(text)
        category = parsed.get("category", "").upper()
        confidence = float(parsed.get("confidence", 0))

        if category in ("CASUAL", "CONSULTATION", "LIVE_SHIPMENT", "SKIP"):
            return TriageResult(category, confidence, "gemini")

    except Exception as e:
        print(f"  ⚠️ Gemini triage classify error: {e}")

    return None


# ═══════════════════════════════════════════
#  MAIN TRIAGE FUNCTION
# ═══════════════════════════════════════════

def triage_email(msg, rcb_email, db=None, get_secret_func=None):
    """Three-layer email triage. Returns TriageResult with category and confidence.

    Flow:
        1. Layer 0: Auto-skip (noreply, OOO, tiny body, self-loop)
        2. Layer 1a: Reply thread detection
        3. Layer 1b: Regex pre-classify
        4. Layer 1c: Gemini classify
        5. Fallback: CONSULTATION (safest default for customs broker)
    """
    sender_email = (
        msg.get("from", {}).get("emailAddress", {}).get("address", "")
    )
    subject = (msg.get("subject") or "").strip()
    body = (msg.get("body", {}).get("content") or msg.get("bodyPreview") or "").strip()
    # Strip HTML for text analysis
    body_plain = re.sub(r'<[^>]+>', '', body).strip()

    # Layer 0: auto-skip
    result = _layer0_auto_skip(msg, sender_email, rcb_email)
    if result:
        return result

    # Layer 1a: reply thread
    result = _check_reply_thread(msg)
    if result:
        return result

    # Layer 1b: regex pre-classify
    result = _regex_pre_classify(subject, body_plain)
    if result:
        return result

    # Layer 1c: Gemini classify
    result = _gemini_classify(subject, body_plain, get_secret_func)
    if result and result.confidence >= 0.4:
        return result

    # Fallback: CONSULTATION (safest default for customs broker mailbox)
    return TriageResult("CONSULTATION", 0.4, "fallback")
