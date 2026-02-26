"""
Casual Email Handler
====================
Handles casual/social emails (greetings, jokes, general chat) with
Gemini Flash AI. Falls back to a canned Hebrew reply on failure.

Does NOT handle customs, tariffs, or legal matters — those go to
CONSULTATION category handled by the legacy pipeline.
"""

import random
import string
from datetime import datetime


# ═══════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════

_CASUAL_SYSTEM_PROMPT = (
    "You are RCB, a friendly AI assistant at R.P.A. PORT customs brokerage "
    "in Haifa, Israel. Someone emailed you casually. Reply warmly, briefly "
    "(max 10 lines). Match their language (Hebrew/English/both). You can "
    "discuss ANY topic — weather, philosophy, jokes, general knowledge. "
    "Do NOT discuss customs, tariffs, or legal matters (those go to a "
    "different department). Sign off as RCB."
)

_CANNED_REPLY = (
    "שלום! קיבלתי את ההודעה שלך. "
    "אני כאן אם תצטרך עזרה בנושאי מכס ויבוא. "
    "RCB 🤖"
)


def _generate_casual_tracking_code():
    """Generate tracking code: RCB-C-YYYYMMDD-XXXXX"""
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = ''.join(random.choices(string.digits, k=5))
    return f"RCB-C-{date_part}-{random_part}"


def _strip_html(text):
    """Strip HTML tags from text."""
    import re
    return re.sub(r'<[^>]+>', '', text).strip()


# ═══════════════════════════════════════════
#  MAIN HANDLER
# ═══════════════════════════════════════════

def handle_casual(msg, access_token, rcb_email, get_secret_func, db=None):
    """Handle a CASUAL email with Gemini Flash. Returns result dict.

    Args:
        msg: Graph API message object
        access_token: Graph API access token
        rcb_email: RCB mailbox address
        get_secret_func: Secret Manager accessor
        db: Firestore client (optional, for logging)

    Returns:
        dict with keys: status, handler, tracking_code (if replied)
    """
    sender_email = msg.get("from", {}).get("emailAddress", {}).get("address", "")
    body_raw = msg.get("body", {}).get("content") or msg.get("bodyPreview") or ""
    body_plain = _strip_html(body_raw)

    tracking_code = _generate_casual_tracking_code()
    subject = f"RCB | {tracking_code} | שיחה"

    # Try Gemini Flash
    reply_text = None
    if get_secret_func:
        gemini_key = get_secret_func("GEMINI_API_KEY")
        if gemini_key:
            try:
                from lib.classification_agents import call_gemini
            except ImportError:
                try:
                    from classification_agents import call_gemini
                except ImportError:
                    call_gemini = None

            if call_gemini:
                try:
                    reply_text = call_gemini(
                        gemini_key,
                        _CASUAL_SYSTEM_PROMPT,
                        body_plain[:500],
                        max_tokens=500
                    )
                except Exception as e:
                    print(f"  ⚠️ Casual Gemini error: {e}")

    # Determine status
    if reply_text:
        status = "replied"
    else:
        reply_text = _CANNED_REPLY
        status = "replied_canned"

    # Wrap in RTL HTML
    try:
        from lib.email_intent import _wrap_html_rtl
    except ImportError:
        try:
            from email_intent import _wrap_html_rtl
        except ImportError:
            _wrap_html_rtl = None

    if _wrap_html_rtl:
        body_html = _wrap_html_rtl(reply_text, subject)
    else:
        body_html = f'<div dir="rtl" style="font-family:Arial;font-size:14px;">{reply_text}</div>'

    # Send reply using _send_reply_safe (respects team-only + quality gate)
    try:
        from lib.email_intent import _send_reply_safe
    except ImportError:
        try:
            from email_intent import _send_reply_safe
        except ImportError:
            _send_reply_safe = None

    sent = False
    if _send_reply_safe:
        sent = _send_reply_safe(body_html, msg, access_token, rcb_email, subject_override=subject)
    else:
        # Fallback: use helper_graph_reply directly
        try:
            from lib.rcb_helpers import helper_graph_reply, helper_graph_send
        except ImportError:
            from rcb_helpers import helper_graph_reply, helper_graph_send

        msg_id = msg.get('id', '')
        sent = helper_graph_reply(
            access_token, rcb_email, msg_id, body_html,
            to_email=sender_email, subject=subject
        )
        if not sent:
            sent = helper_graph_send(
                access_token, rcb_email, sender_email,
                subject, body_html
            )

    if not sent:
        return {"status": "send_failed", "handler": "casual"}

    # Log to Firestore (fire-and-forget)
    if db:
        try:
            db.collection("rcb_debug").add({
                "type": "casual_handled",
                "tracking_code": tracking_code,
                "sender": sender_email,
                "subject": msg.get("subject", ""),
                "ai_status": status,
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception:
            pass

    return {
        "status": status,
        "handler": "casual",
        "tracking_code": tracking_code,
    }
