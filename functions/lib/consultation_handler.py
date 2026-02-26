"""
Consultation Handler — 3-Level Escalation Ladder
=================================================
Handles CONSULTATION emails detected by the triage layer (Session 74).

Architecture:
  1. Sub-intent check: delegate ADMIN/CORRECTION/INSTRUCTION/STATUS/NON_WORK to legacy
  2. SIF (System Intelligence First): prepare_context_package searches ALL data BEFORE AI
  3. Level 1: Gemini Flash (cheapest) — if passes quality gate, send
  4. Level 2: ChatGPT reviews Gemini draft — if they agree, synthesize and send
  5. Level 3: Claude arbitrates seeing both drafts — final answer

Usage:
    from lib.consultation_handler import handle_consultation
"""

import re
import hashlib
import logging
import random
import string
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════
#  IMPORTS (with guards)
# ═══════════════════════════════════════════

try:
    from lib.context_engine import prepare_context_package
except ImportError:
    try:
        from context_engine import prepare_context_package
    except ImportError:
        prepare_context_package = None

try:
    from lib.classification_agents import call_gemini, call_chatgpt, call_claude
except ImportError:
    try:
        from classification_agents import call_gemini, call_chatgpt, call_claude
    except ImportError:
        call_gemini = call_chatgpt = call_claude = None

try:
    from lib.email_intent import (
        detect_email_intent, _get_body_text, _get_sender_address,
        _get_sender_privilege, _wrap_html_rtl, _send_reply_safe,
        _generate_query_tracking_code, REPLY_SYSTEM_PROMPT,
    )
except ImportError:
    try:
        from email_intent import (
            detect_email_intent, _get_body_text, _get_sender_address,
            _get_sender_privilege, _wrap_html_rtl, _send_reply_safe,
            _generate_query_tracking_code, REPLY_SYSTEM_PROMPT,
        )
    except ImportError:
        detect_email_intent = None

try:
    from lib.intelligence_gate import filter_banned_phrases
except ImportError:
    try:
        from intelligence_gate import filter_banned_phrases
    except ImportError:
        filter_banned_phrases = None


# ═══════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════

TEAM_DOMAIN = "rpa-port.co.il"

_DOMAIN_LABELS = {
    "tariff": "תעריף מכס",
    "ordinance": "פקודת המכס",
    "fta": "הסכמי סחר",
    "regulatory": "רגולציה",
    "general": "מכס כללי",
}

# Sub-intents that should delegate to legacy email_intent handlers.
# NON_WORK is NOT here — triage already filtered casual/non-work via CASUAL/SKIP.
# If triage said CONSULTATION, we trust triage over sub-intent re-classification.
_DELEGATE_INTENTS = {
    "ADMIN_INSTRUCTION", "CORRECTION", "INSTRUCTION",
    "STATUS_REQUEST",
}


# ═══════════════════════════════════════════
#  AI PROMPTS
# ═══════════════════════════════════════════

_LEVEL1_SYSTEM = (
    "אתה RCB — סוכן מכס מורשה של R.P.A. PORT LTD, חיפה.\n"
    "המערכת חיפשה ומצאה את המידע הבא. השתמש אך ורק במידע זה לתשובתך.\n"
    "אל תמציא מידע. אם המידע לא מספיק — אמור מה חסר ומה צריך לבדוק.\n"
    "אנחנו עמיל המכס. לעולם אל תכתוב 'מומלץ לפנות לעמיל מכס'.\n\n"
    "ענה בפורמט הבא בדיוק:\n"
    "## תשובה ישירה\n[תשובה קצרה וישירה בשורה אחת או שתיים]\n\n"
    "## ציטוט מהחוק\n[ציטוט מילה במילה מהמקור — סעיף, פקודה, צו — עם מספר סעיף מדויק. "
    "אם אין מקור — כתוב 'לא נמצא מקור ישיר']\n\n"
    "## הסבר\n[הסבר מקצועי קצר]\n\n"
    "## מידע נוסף\n[פרטים רלוונטיים נוספים]\n\n"
    "## English Summary\n[2-3 sentence summary in English]"
)

_LEVEL2_SYSTEM = (
    "אתה סוכן מכס בכיר הבודק טיוטת תשובה שהוכנה על ידי עמית.\n"
    "אנחנו עמיל המכס. לעולם אל תכתוב 'מומלץ לפנות לעמיל מכס'.\n\n"
    "המשימה שלך:\n"
    "1. בדוק האם הציטוטים מהחוק מדויקים ומתאימים למידע שסופק\n"
    "2. בדוק האם התשובה הישירה נכונה\n"
    "3. בדוק האם חסר מידע חשוב שקיים בנתוני המערכת אך לא הוזכר\n"
    "4. כתוב תשובה משופרת באותו פורמט — או אשר שהתשובה המקורית טובה\n\n"
    "אם אתה מסכים עם התשובה — התחל עם 'מאשר:' ואז כתוב את התשובה עם שיפורים קלים.\n"
    "אם אתה לא מסכים — התחל עם 'מתקן:' ואז כתוב תשובה חדשה."
)

_LEVEL3_SYSTEM = (
    "אתה הסוכן הבכיר ביותר — שופט ומסכם סופי.\n"
    "אנחנו עמיל המכס. לעולם אל תכתוב 'מומלץ לפנות לעמיל מכס'.\n"
    "שני סוכנים כתבו תשובות שונות לשאלת מכס. המערכת סיפקה נתונים.\n\n"
    "המשימה שלך:\n"
    "1. קבע מי צודק — או שניהם, או אף אחד\n"
    "2. כתוב את התשובה הסופית והמדויקת ביותר\n"
    "3. חובה להשתמש אך ורק בנתוני המערכת שסופקו\n"
    "4. אם שניהם טועים — אמור זאת בפירוש ותן את התשובה הנכונה\n"
    "5. פורמט: אותו פורמט 5 חלקים (תשובה ישירה / ציטוט / הסבר / מידע נוסף / English Summary)"
)


# ═══════════════════════════════════════════
#  ESCALATION LADDER
# ═══════════════════════════════════════════

def _call_level1_gemini(context_package, get_secret_func):
    """Level 1: Gemini Flash — cheapest, tries first."""
    if not call_gemini or not get_secret_func:
        return None
    try:
        gemini_key = get_secret_func("GEMINI_API_KEY")
        if not gemini_key:
            return None
        system = f"{_LEVEL1_SYSTEM}\n\n{context_package.context_summary}"
        user = f"נושא: {context_package.original_subject}\n\n{context_package.original_body}"
        result = call_gemini(gemini_key, system, user, max_tokens=2000)
        return result
    except Exception as e:
        logger.warning(f"Level 1 Gemini error: {e}")
        return None


def _call_level2_chatgpt(context_package, gemini_draft, get_secret_func):
    """Level 2: ChatGPT reviews Gemini's work."""
    if not call_chatgpt or not get_secret_func:
        return None
    try:
        openai_key = get_secret_func("OPENAI_API_KEY")
        if not openai_key:
            return None
        system = f"{_LEVEL2_SYSTEM}\n\nנתוני המערכת:\n{context_package.context_summary}"
        user = (
            f"שאלה מקורית:\nנושא: {context_package.original_subject}\n"
            f"{context_package.original_body}\n\n"
            f"טיוטת התשובה של העמית:\n---\n{gemini_draft}\n---"
        )
        result = call_chatgpt(openai_key, system, user, max_tokens=2000)
        return result
    except Exception as e:
        logger.warning(f"Level 2 ChatGPT error: {e}")
        return None


def _compare_drafts(gemini_draft, chatgpt_draft, context_package):
    """Compare two drafts. Returns float 0.0-1.0 agreement score."""
    if not chatgpt_draft:
        return 0.0

    text = chatgpt_draft.strip()
    # Check explicit signals
    if text.startswith("מאשר:") or text.startswith("מאשר :"):
        return 0.9
    if text.startswith("מתקן:") or text.startswith("מתקן :"):
        return 0.3

    # Keyword overlap — extract key terms from both
    def _extract_keys(text):
        keys = set()
        # HS codes
        keys.update(re.findall(r'\d{4}\.\d{2}', text or ""))
        # Article numbers
        keys.update(re.findall(r'סעיף\s+(\d{1,3}[אבגדהוזחטי]*)', text or ""))
        # Key legal terms
        for word in re.findall(r'[\u0590-\u05FF]{4,}', text or ""):
            keys.add(word)
        return keys

    keys1 = _extract_keys(gemini_draft)
    keys2 = _extract_keys(chatgpt_draft)
    if not keys1 or not keys2:
        return 0.5
    intersection = keys1 & keys2
    union = keys1 | keys2
    return len(intersection) / len(union) if union else 0.5


def _call_level3_claude(context_package, gemini_draft, chatgpt_draft, get_secret_func):
    """Level 3: Claude arbitrates seeing everything."""
    if not call_claude or not get_secret_func:
        return chatgpt_draft or gemini_draft  # fallback
    try:
        api_key = get_secret_func("ANTHROPIC_API_KEY")
        if not api_key:
            return chatgpt_draft or gemini_draft
        system = f"{_LEVEL3_SYSTEM}\n\nנתוני המערכת:\n{context_package.context_summary}"
        user = (
            f"שאלה מקורית:\nנושא: {context_package.original_subject}\n"
            f"{context_package.original_body}\n\n"
            f"תשובה 1 (ראשונית):\n---\n{gemini_draft or '(לא זמין)'}\n---\n\n"
            f"תשובה 2 (ביקורת):\n---\n{chatgpt_draft or '(לא זמין)'}\n---"
        )
        result = call_claude(api_key, system, user, max_tokens=2000)
        return result or chatgpt_draft or gemini_draft
    except Exception as e:
        logger.warning(f"Level 3 Claude error: {e}")
        return chatgpt_draft or gemini_draft


def _evaluate_draft(draft, context_package):
    """Quality gate on a draft. Returns True if draft passes."""
    if not draft:
        return False
    if len(draft.strip()) < 50:
        return False

    # Banned phrases check
    if filter_banned_phrases:
        try:
            bp_result = filter_banned_phrases(draft)
            if bp_result.get("phrases_found"):
                return False
        except Exception:
            pass

    # Context fidelity: if we found ordinance articles, draft should reference at least one
    if context_package.ordinance_articles:
        article_ids = [a["article_id"] for a in context_package.ordinance_articles]
        if not any(aid in draft for aid in article_ids):
            # Check if ANY article number appears
            if not re.search(r'סעיף\s+\d', draft):
                return False

    # If we found tariff results, draft should mention at least one HS code
    if context_package.tariff_results:
        hs_codes = [c.get("hs_code", "") for c in context_package.tariff_results if c.get("hs_code")]
        if hs_codes and not any(code[:4] in draft for code in hs_codes):
            if not re.search(r'\d{4}\.\d{2}', draft):
                return False

    return True


def _synthesize_two(gemini_draft, chatgpt_draft, context_package, get_secret_func):
    """When both models agree, merge with cheap Gemini call."""
    if not call_gemini or not get_secret_func:
        return chatgpt_draft or gemini_draft

    try:
        gemini_key = get_secret_func("GEMINI_API_KEY")
        if not gemini_key:
            return chatgpt_draft or gemini_draft
        system = "שלב את שתי התשובות הבאות לתשובה אחת מיטבית. שמור על פורמט 5 החלקים."
        user = f"תשובה 1:\n{gemini_draft}\n\nתשובה 2:\n{chatgpt_draft}"
        result = call_gemini(gemini_key, system, user, max_tokens=2000)
        return result or chatgpt_draft or gemini_draft
    except Exception:
        return chatgpt_draft or gemini_draft


# ═══════════════════════════════════════════
#  REPLY SENDING
# ═══════════════════════════════════════════

def _send_consultation_reply(msg, content, context_package, access_token, rcb_email, db):
    """Send the consultation reply with RCB branding."""
    tracking_code = _generate_query_tracking_code()
    domain_label = _DOMAIN_LABELS.get(context_package.domain, "מכס")

    # Build subject
    orig_subject = (msg.get("subject") or "").strip()
    # Strip Re:/Fwd: prefixes
    orig_clean = re.sub(r'^(?:\s*(?:Re|RE|re|Fwd|FWD|FW|Fw|fw)\s*:\s*)+', '', orig_subject).strip()
    if orig_clean and len(orig_clean) >= 3:
        topic = orig_clean[:50]
    else:
        topic = context_package.original_body[:50].strip()
        if len(context_package.original_body) > 50:
            topic += "..."
    subject = f"RCB | {tracking_code} | {domain_label} | {topic}"

    # Wrap content in HTML
    body_html = _wrap_html_rtl(content, subject)

    # Send via the safe reply mechanism
    sent = _send_reply_safe(body_html, msg, access_token, rcb_email,
                            subject_override=subject)

    # Log to questions_log for cache
    if sent and db:
        try:
            normalized = re.sub(r'\s+', ' ',
                                f"{context_package.original_subject} {context_package.original_body}"
                                .lower().strip())
            q_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]
            db.collection("questions_log").document(q_hash).set({
                "question_hash": q_hash,
                "question_text": f"{context_package.original_subject} {context_package.original_body}"[:2000],
                "answer_html": body_html[:10000],
                "answer_text": content[:5000],
                "intent": "CONSULTATION",
                "domain": context_package.domain,
                "from_email": (_get_sender_address(msg) or "").lower(),
                "tracking_code": tracking_code,
                "created_at": datetime.now(timezone.utc),
                "hit_count": 0,
            })
        except Exception as e:
            logger.warning(f"questions_log write error: {e}")

    return sent


def _log_to_pupil(context_package, drafts, winner, db):
    """Log consultation to pupil_consultation_log for learning."""
    if not db:
        return
    try:
        db.collection("pupil_consultation_log").add({
            "timestamp": datetime.now(timezone.utc),
            "question_subject": context_package.original_subject[:200],
            "question_body": context_package.original_body[:500],
            "language": context_package.detected_language,
            "domain": context_package.domain,
            "entities": context_package.entities,
            "context_confidence": context_package.confidence,
            "searches_performed": context_package.search_log[:20],
            "drafts": [
                {"model": model, "response": (draft or "")[:1000]}
                for model, draft in drafts
            ],
            "winner": winner,
            "escalation_level": len(drafts),
        })
    except Exception as e:
        logger.warning(f"Pupil log error (non-fatal): {e}")


# ═══════════════════════════════════════════
#  LEGACY DELEGATION
# ═══════════════════════════════════════════

def _delegate_to_legacy(msg, sub_intent, db, firestore_module, access_token,
                        rcb_email, get_secret_func):
    """Delegate to existing email_intent handlers."""
    try:
        try:
            from lib.email_intent import process_email_intent
        except ImportError:
            from email_intent import process_email_intent

        result = process_email_intent(msg, db, firestore_module, access_token,
                                      rcb_email, get_secret_func)
        return {
            "status": "delegated",
            "handler": "legacy",
            "sub_intent": sub_intent,
            "legacy_result": result,
        }
    except Exception as e:
        logger.warning(f"Legacy delegation error: {e}")
        return {"status": "delegation_error", "handler": "legacy",
                "sub_intent": sub_intent, "error": str(e)}


# ═══════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════

def handle_consultation(msg, db, firestore_module, access_token, rcb_email,
                        get_secret_func, triage_result=None):
    """
    Main entry point for CONSULTATION emails.

    Flow:
      1. Check sub-intent — delegate to legacy if ADMIN/CORRECTION/etc.
      2. Run SIF — System Intelligence First
      3. Level 1: Gemini Flash
      4. Level 2: ChatGPT reviews (if Gemini fails gate)
      5. Level 3: Claude arbitrates (if they disagree)
    """
    t0 = time.time()
    subject = (msg.get("subject") or "").strip()
    body_text = _get_body_text(msg) if _get_body_text else ""
    from_email = _get_sender_address(msg) if _get_sender_address else ""

    print(f"    🧠 Consultation handler: subject={subject[:60]}")

    # 1. Check sub-intent
    if detect_email_intent:
        try:
            privilege = _get_sender_privilege(from_email) if _get_sender_privilege else "TEAM"
            sub_result = detect_email_intent(subject, body_text, from_email,
                                             privilege=privilege,
                                             get_secret_func=get_secret_func)
            sub_intent = sub_result.get("intent", "NONE")
            sub_confidence = sub_result.get("confidence", 0)

            if sub_intent in _DELEGATE_INTENTS and sub_confidence >= 0.6:
                print(f"    ↪️  Sub-intent {sub_intent} (conf={sub_confidence:.2f}) → delegating to legacy")
                return _delegate_to_legacy(msg, sub_intent, db, firestore_module,
                                           access_token, rcb_email, get_secret_func)
            elif sub_intent in _DELEGATE_INTENTS:
                print(f"    ⚠️  Sub-intent {sub_intent} low confidence ({sub_confidence:.2f}) → treating as consultation")
        except Exception as e:
            logger.warning(f"Sub-intent detection error: {e}")

    # 2. Run SIF
    if not prepare_context_package:
        return {"status": "error", "handler": "consultation", "error": "SIF unavailable"}

    context_package = prepare_context_package(subject, body_text, db, get_secret_func)
    print(f"    📦 SIF: domain={context_package.domain}, lang={context_package.detected_language}, "
          f"confidence={context_package.confidence:.2f}, "
          f"tariff={len(context_package.tariff_results)}, "
          f"ordinance={len(context_package.ordinance_articles)}, "
          f"xml={len(context_package.xml_results)}")

    # 3. LEVEL 1: Gemini Flash
    print(f"    🟢 Level 1: Gemini Flash")
    gemini_draft = _call_level1_gemini(context_package, get_secret_func)

    if gemini_draft and _evaluate_draft(gemini_draft, context_package):
        print(f"    ✅ Level 1 passed quality gate — sending")
        sent = _send_consultation_reply(msg, gemini_draft, context_package,
                                        access_token, rcb_email, db)
        _log_to_pupil(context_package, [("gemini", gemini_draft)], "gemini", db)
        elapsed = int((time.time() - t0) * 1000)
        return {"status": "replied" if sent else "send_failed",
                "handler": "consultation", "level": 1, "model": "gemini",
                "elapsed_ms": elapsed, "confidence": context_package.confidence}

    # 4. LEVEL 2: ChatGPT reviews
    print(f"    🟡 Level 2: ChatGPT review" +
          (" (Gemini failed gate)" if gemini_draft else " (Gemini unavailable)"))
    chatgpt_draft = _call_level2_chatgpt(context_package, gemini_draft or "(לא זמין)", get_secret_func)

    if chatgpt_draft:
        agreement = _compare_drafts(gemini_draft, chatgpt_draft, context_package)
        print(f"    📊 Draft agreement: {agreement:.2f}")

        if agreement >= 0.7:
            final = _synthesize_two(gemini_draft or "", chatgpt_draft, context_package, get_secret_func)
            sent = _send_consultation_reply(msg, final, context_package,
                                            access_token, rcb_email, db)
            _log_to_pupil(context_package,
                          [("gemini", gemini_draft), ("chatgpt", chatgpt_draft)],
                          "synthesis_2", db)
            elapsed = int((time.time() - t0) * 1000)
            return {"status": "replied" if sent else "send_failed",
                    "handler": "consultation", "level": 2, "model": "chatgpt+gemini",
                    "elapsed_ms": elapsed, "confidence": context_package.confidence}

    # 5. LEVEL 3: Claude arbiter
    print(f"    🔴 Level 3: Claude arbiter")
    claude_draft = _call_level3_claude(context_package, gemini_draft, chatgpt_draft,
                                        get_secret_func)

    if claude_draft:
        sent = _send_consultation_reply(msg, claude_draft, context_package,
                                        access_token, rcb_email, db)
        _log_to_pupil(context_package,
                      [("gemini", gemini_draft), ("chatgpt", chatgpt_draft),
                       ("claude", claude_draft)],
                      "claude", db)
        elapsed = int((time.time() - t0) * 1000)
        return {"status": "replied" if sent else "send_failed",
                "handler": "consultation", "level": 3, "model": "claude",
                "elapsed_ms": elapsed, "confidence": context_package.confidence}

    # All levels failed
    elapsed = int((time.time() - t0) * 1000)
    print(f"    ❌ All escalation levels failed ({elapsed}ms)")
    return {"status": "all_levels_failed", "handler": "consultation",
            "elapsed_ms": elapsed, "confidence": context_package.confidence}
