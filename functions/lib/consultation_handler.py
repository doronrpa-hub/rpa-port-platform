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

# Composition layer (Session 87)
try:
    from lib.direction_router import detect_direction, get_direction_config
    from lib.evidence_types import build_evidence_bundle
    from lib.straitjacket_prompt import build_straitjacket_prompt, parse_ai_response, is_valid_response, needs_escalation
    from lib.reply_composer import compose_consultation, compose_live_shipment, verify_citations
    COMPOSITION_LAYER_AVAILABLE = True
except ImportError:
    try:
        from direction_router import detect_direction, get_direction_config
        from evidence_types import build_evidence_bundle
        from straitjacket_prompt import build_straitjacket_prompt, parse_ai_response, is_valid_response, needs_escalation
        from reply_composer import compose_consultation, compose_live_shipment, verify_citations
        COMPOSITION_LAYER_AVAILABLE = True
    except ImportError:
        COMPOSITION_LAYER_AVAILABLE = False

# Case reasoning (Session 88)
try:
    from lib.case_reasoning import analyze_case
    CASE_REASONING_AVAILABLE = True
except ImportError:
    try:
        from case_reasoning import analyze_case
        CASE_REASONING_AVAILABLE = True
    except ImportError:
        analyze_case = None
        CASE_REASONING_AVAILABLE = False

# Broker engine (Session 90) — deterministic classification
try:
    from lib.broker_engine import process_case as broker_process_case
    BROKER_ENGINE_AVAILABLE = True
except ImportError:
    try:
        from broker_engine import process_case as broker_process_case
        BROKER_ENGINE_AVAILABLE = True
    except ImportError:
        broker_process_case = None
        BROKER_ENGINE_AVAILABLE = False


# ═══════════════════════════════════════════
#  PER-ITEM TARIFF LOOKUP (Fix: real HS codes)
# ═══════════════════════════════════════════

# Category -> typical tariff search keywords (Hebrew+English)
_CATEGORY_SEARCH_TERMS = {
    "furniture": ["ריהוט", "רהיטים", "furniture"],
    "electronics": ["מוצרי חשמל", "electronics", "טלוויזיה", "television"],
    "vehicle": ["רכב מנועי", "motor vehicle", "automobile"],
    "personal": ["חפצים אישיים", "personal effects"],
    "kitchen": ["כלי מטבח", "kitchenware"],
    "textiles": ["מצעים", "bedding", "textiles"],
    "music": ["כלי נגינה", "musical instruments"],
    "food": ["מזון", "food"],
}

def _enrich_case_plan_items_with_tariff(case_plan, context_package, db):
    """Run tariff search for each item in case_plan, inject real HS codes.

    Modifies case_plan.items_to_classify in place — adds tariff_match dict
    with hs_code, description, duty, purchase_tax from Firestore tariff collection.
    Also adds results to context_package.tariff_results so evidence_bundle picks them up.
    """
    if not db:
        return

    for item in case_plan.items_to_classify:
        category = item.get("category", "")
        keywords = item.get("keywords", [])
        name = item.get("name", "")

        # Build search terms: item keywords + category defaults
        search_terms = list(keywords)
        search_terms.extend(_CATEGORY_SEARCH_TERMS.get(category, []))

        # Search tariff collection for matching HS codes
        best_match = None
        for term in search_terms:
            if not term:
                continue
            try:
                results = list(db.collection("tariff")
                               .where("description_he", ">=", term)
                               .where("description_he", "<=", term + "\uf8ff")
                               .limit(3).stream())
                for doc in results:
                    d = doc.to_dict()
                    if d.get("corrupt_code"):
                        continue
                    best_match = {
                        "hs_code": d.get("hs_code", doc.id),
                        "description_he": d.get("description", ""),
                        "description_en": d.get("description_en", ""),
                        "duty": d.get("customs_rate", d.get("duty", "")),
                        "purchase_tax": d.get("purchase_tax", d.get("pt", "")),
                    }
                    break
                if best_match:
                    break
            except Exception:
                continue

        # Fallback: search by chapter if no keyword match
        if not best_match and category:
            _CATEGORY_CHAPTERS = {
                "furniture": "94", "electronics": "85", "vehicle": "87",
                "personal": "96", "kitchen": "73", "textiles": "63",
                "music": "92", "food": "21",
            }
            ch = _CATEGORY_CHAPTERS.get(category)
            if ch:
                try:
                    results = list(db.collection("tariff")
                                   .where("hs_code", ">=", ch)
                                   .where("hs_code", "<", str(int(ch) + 1))
                                   .limit(1).stream())
                    for doc in results:
                        d = doc.to_dict()
                        if not d.get("corrupt_code"):
                            best_match = {
                                "hs_code": d.get("hs_code", doc.id),
                                "description_he": d.get("description", ""),
                                "description_en": d.get("description_en", ""),
                                "duty": d.get("customs_rate", d.get("duty", "")),
                                "purchase_tax": d.get("purchase_tax", d.get("pt", "")),
                            }
                except Exception:
                    pass

        if best_match:
            item["tariff_match"] = best_match
            # Inject into context_package so evidence_bundle picks it up
            if hasattr(context_package, 'tariff_results') and context_package.tariff_results is not None:
                # Avoid duplicates
                existing_codes = {r.get("hs_code") for r in context_package.tariff_results}
                if best_match["hs_code"] not in existing_codes:
                    context_package.tariff_results.append(best_match)


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
    "המערכת חיפשה ומצאה את המידע הבא. השתמש במידע זה לתשובתך.\n"
    "אל תמציא מידע. אם המידע לא מספיק — אמור מה חסר ומה צריך לבדוק.\n"
    "אנחנו עמיל המכס. לעולם אל תכתוב 'מומלץ לפנות לעמיל מכס'.\n\n"
    "כלל חשוב — לעולם אל תסרב לענות על שאלה:\n"
    "• אם השאלה כוללת ידע כללי (היסטוריה, מדע, כלכלה) — ענה בחום ובקצרה מהמידע שסופק, "
    "ואז הוסף: 'במה שקשור לתחום שלנו — מכס וייבוא...' וקשר לתחום המכס.\n"
    "• אם יש גם שאלת מכס וגם שאלה כללית — ענה על שתיהן.\n"
    "• לעולם אל תכתוב 'השאלה אינה קשורה למכס' או 'אינה בסמכותנו'.\n\n"
    "ענה בפורמט הבא בדיוק:\n"
    "## תשובה ישירה\n[תשובה קצרה וישירה בשורה אחת או שתיים]\n\n"
    "## ציטוט מהחוק\n[ציטוט מילה במילה מהמקור — סעיף, פקודה, צו — עם מספר סעיף מדויק. "
    "אם אין מקור חוקי רלוונטי — כתוב 'לא נמצא מקור ישיר']\n\n"
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
    "שני סוכנים כתבו תשובות שונות. המערכת סיפקה נתונים.\n\n"
    "המשימה שלך:\n"
    "1. קבע מי צודק — או שניהם, או אף אחד\n"
    "2. כתוב את התשובה הסופית והמדויקת ביותר\n"
    "3. חובה להשתמש בנתוני המערכת שסופקו\n"
    "4. אם שניהם טועים — אמור זאת בפירוש ותן את התשובה הנכונה\n"
    "5. פורמט: אותו פורמט 5 חלקים (תשובה ישירה / ציטוט / הסבר / מידע נוסף / English Summary)\n\n"
    "כלל חשוב: לעולם אל תסרב לענות. אם השאלה כוללת ידע כללי — ענה בחום מהנתונים "
    "שסופקו (ויקיפדיה וכו') ואז קשר בטבעיות למכס."
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
    # (skip this check if wikipedia data is present — general knowledge questions don't need ordinance refs)
    has_wikipedia = hasattr(context_package, 'wikipedia_results') and context_package.wikipedia_results
    if context_package.ordinance_articles and not has_wikipedia:
        article_ids = [a["article_id"] for a in context_package.ordinance_articles]
        if not any(aid in draft for aid in article_ids):
            # Check if ANY article number appears
            if not re.search(r'סעיף\s+\d', draft):
                return False

    # If we found tariff results, draft should mention at least one HS code
    if context_package.tariff_results and not has_wikipedia:
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
#  COMPOSITION LAYER (Session 87)
# ═══════════════════════════════════════════

def _run_composition_pipeline(context_package, get_secret_func, msg,
                              template_type="consultation", db=None):
    """Run the full evidence→straitjacket→AI→composer pipeline.

    Args:
        template_type: "consultation" or "live_shipment"

    Returns:
        dict with {html, subject, tracking_code} or None on failure.
    """
    if not COMPOSITION_LAYER_AVAILABLE:
        return None

    try:
        subject = (msg.get("subject") or "").strip()
        body_text = context_package.original_body or ""

        # 1. Direction detection
        direction_result = detect_direction(subject, body_text,
                                            entities=context_package.entities)
        print(f"    Direction: {direction_result['direction']} "
              f"(conf={direction_result['confidence']:.2f})")

        # 1b. Case reasoning (detect legal category, items, tier)
        case_plan = None
        if CASE_REASONING_AVAILABLE and analyze_case:
            case_plan = analyze_case(subject, body_text,
                                     entities=context_package.entities)
            if case_plan and case_plan.case_type != "GENERAL":
                print(f"    Case: {case_plan.case_type} | "
                      f"{case_plan.legal_category_he or '-'} | "
                      f"tier={case_plan.tier} | "
                      f"{len(case_plan.items_to_classify)} items")
                # Override direction if case reasoning detected import
                if case_plan.direction == "import" and direction_result["direction"] == "unknown":
                    direction_result["direction"] = "import"
                    direction_result["confidence"] = 0.75

        # 1c. Per-item tariff lookup (feed real HS codes into evidence)
        if case_plan and case_plan.items_to_classify and context_package:
            _enrich_case_plan_items_with_tariff(case_plan, context_package, db)

        # 2. Build evidence bundle (with case_plan for directed searches)
        bundle = build_evidence_bundle(context_package, direction_result,
                                       case_plan=case_plan)
        print(f"    Evidence: {len(bundle.sources_found)} sources found, "
              f"{len(bundle.sources_not_found)} not found")

        # 3. Build straitjacket prompt (with case_plan for per-item schema)
        prompt = build_straitjacket_prompt(bundle, case_plan=case_plan)

        # 4. Call AI with straitjacket (Gemini → ChatGPT → Claude)
        ai_text = None

        if call_gemini and get_secret_func:
            try:
                gk = get_secret_func("GEMINI_API_KEY")
                if gk:
                    ai_text = call_gemini(gk, prompt["system"], prompt["user"],
                                          max_tokens=2500)
            except Exception as e:
                logger.warning(f"Straitjacket Gemini error: {e}")

        parsed = parse_ai_response(ai_text) if ai_text else None
        reason = needs_escalation(parsed)

        if reason and call_chatgpt and get_secret_func:
            print(f"    ⬆️ Escalating to ChatGPT: {reason}")
            try:
                ok = get_secret_func("OPENAI_API_KEY")
                if ok:
                    ai_text = call_chatgpt(ok, prompt["system"], prompt["user"],
                                           max_tokens=2500)
                    parsed = parse_ai_response(ai_text) if ai_text else parsed
                    reason = needs_escalation(parsed)
            except Exception as e:
                logger.warning(f"Straitjacket ChatGPT error: {e}")

        if reason and call_claude and get_secret_func:
            print(f"    ⬆️ Escalating to Claude: {reason}")
            try:
                ak = get_secret_func("ANTHROPIC_API_KEY")
                if ak:
                    ai_text = call_claude(ak, prompt["system"], prompt["user"],
                                          max_tokens=2500)
                    parsed = parse_ai_response(ai_text) if ai_text else parsed
            except Exception as e:
                logger.warning(f"Straitjacket Claude error: {e}")

        if not parsed or not is_valid_response(parsed):
            print(f"    ⚠️ Composition pipeline: no valid AI response")
            return None

        # 5. Compliance verification
        verification = verify_citations(parsed, bundle)
        if not verification["passed"]:
            print(f"    ⚠️ Citation verification failed: {verification['errors']}")
            # Continue anyway — warnings are logged but don't block

        # 6. Compose HTML
        recipient_name = ""
        from_addr = (msg.get("from", {}).get("emailAddress", {}).get("name") or "")
        if from_addr:
            recipient_name = from_addr.split("@")[0].split(".")[0].strip()

        composer = compose_live_shipment if template_type == "live_shipment" else compose_consultation
        result = composer(parsed, bundle, recipient_name=recipient_name,
                          case_plan=case_plan)
        print(f"    ✅ Composition pipeline ({template_type}): HTML rendered ({len(result['html'])} chars)")
        return result

    except Exception as e:
        logger.warning(f"Composition pipeline error: {e}")
        import traceback
        traceback.print_exc()
        return None


# ═══════════════════════════════════════════
#  BROKER ENGINE HTML RENDERER
# ═══════════════════════════════════════════

_RPA_BLUE = "#1a5276"
_COLOR_OK = "#27ae60"
_COLOR_WARN = "#f39c12"
_LOGO_URL = "https://storage.googleapis.com/rpa-port-customs.appspot.com/logo/rpa_port_logo.png"


def _render_broker_result_html(broker_result):
    """Render broker_engine.process_case() output into branded RTL HTML email.

    Each section IS the process documentation — proves the system did its work.
    Block 1: Header + classification methodology citation
    Block 2: URL visit results (what website was visited, what was found)
    Block 3: Methodology — cites נוהל סיווג #3, explains process
    Block 4: Official 6-column tariff table
    Block 5: FIO/FEO requirements (specific per authority)
    Block 6: FTA / Chapter 98 / Valuation / Release
    """
    op = broker_result.get("operation", {})
    items = broker_result.get("items", [])
    legal_he = op.get("legal_category_he", "")
    direction = op.get("direction", "import")
    direction_he = "יבוא" if direction == "import" else "יצוא"

    parts = []
    # --- DOCTYPE + charset for proper Hebrew rendering ---
    parts.append('<!DOCTYPE html><html dir="rtl" lang="he"><head><meta charset="utf-8"></head>'
                 '<body style="margin:0;padding:0;">')
    # --- Block 1: Header ---
    parts.append(f"""<table width="100%" cellpadding="0" cellspacing="0" style="direction:rtl;font-family:Arial,sans-serif;">
    <tr><td style="background:{_RPA_BLUE};padding:16px 24px;color:#fff;">
        <table width="100%"><tr>
            <td><img src="{_LOGO_URL}" height="36" alt="RPA-PORT" style="vertical-align:middle;"/></td>
            <td style="text-align:left;color:#d5e8f0;font-size:13px;">{direction_he}</td>
        </tr></table>
        <div style="font-size:20px;font-weight:bold;margin-top:8px;">
            {"סיווג מכס" if not legal_he else f"סיווג מכס — {legal_he}"}
        </div>
    </td></tr>""")

    # --- Block 2: URL visit results (what website was visited, what was found) ---
    parts.append(f"""<tr><td style="padding:12px 24px;">
    <div style="font-size:14px;font-weight:bold;color:{_RPA_BLUE};border-bottom:2px solid {_RPA_BLUE};padding-bottom:4px;margin-bottom:8px;">
        מידע שנאסף מאתר היצרן
    </div>""")
    _has_url_visit = False
    for ci in items:
        item = ci.get("item", {})
        source_url = item.get("source_url", "")
        if source_url:
            _has_url_visit = True
            specs_found = []
            for field in ("weight", "dimensions", "frequency", "power"):
                val = item.get(field)
                if val:
                    label = {"weight": "משקל", "dimensions": "מידות", "frequency": "תדר", "power": "הספק"}[field]
                    specs_found.append(f"{label}: {val}")
            parts.append(f"""<div style="font-size:13px;margin-bottom:6px;padding:8px;background:#eaf2f8;border-right:3px solid {_RPA_BLUE};">
                ביקרתי באתר <a href="{source_url}" style="color:{_RPA_BLUE};">{source_url[:60]}</a>
                {f' ומצאתי: <b>{", ".join(specs_found)}</b>' if specs_found else ' — לא נמצאו מפרטים טכניים'}
            </div>""")
    if not _has_url_visit:
        parts.append("""<div style="font-size:13px;color:#666;">
            לא נמצאו קישורים לאתרי יצרן בגוף ההודעה. לשיפור הסיווג, ניתן לצרף קישור לדף המוצר.
        </div>""")
    parts.append("</td></tr>")

    # --- Block 3: Methodology — cite נוהל סיווג #3 ---
    parts.append(f"""<tr><td style="padding:8px 24px;">
        <div style="font-size:14px;font-weight:bold;color:{_RPA_BLUE};border-bottom:2px solid {_RPA_BLUE};padding-bottom:4px;margin-bottom:6px;">
            מתודולוגיית הסיווג
        </div>
        <div style="font-size:12px;color:#555;line-height:1.6;">
            בהתאם ל<b>נוהל סיווג טובין #3</b> (מנהלת המכס):<br/>
            1. זיהוי פיזי — חומר, מהות, שימוש (שלושת העמודים)<br/>
            2. חיפוש בתעריף המכס — כללי פרשנות (GIR 1-6)<br/>
            3. אלימינציה — סעיפים שאינם מתאימים הוסרו לפי הערות לפרקים ולחלקים<br/>
            4. תת-פרט — ירידה לרמת 10 ספרות (XX.XX.XXXXXX/X)<br/>
            5. בדיקת צו יבוא חופשי — תוספות, רשויות מאשרות, תקנים<br/>
            6. אימות — לולאת בדיקה עצמית (3 סיבובים)
        </div>
    </td></tr>""")

    # --- Block 4: Official 6-column tariff table per item ---
    for ci in items:
        item = ci.get("item", {})
        cls = ci.get("classification", {})
        status = ci.get("status", "")
        item_name = item.get("name", "?")

        parts.append(f"""<tr><td style="padding:12px 24px;">
        <div style="font-size:16px;font-weight:bold;color:{_RPA_BLUE};margin-bottom:8px;">
            {item_name}
        </div>""")

        if status == "kram":
            kram_qs = ci.get("kram_questions", cls.get("kram_questions", []))
            parts.append(f"""<div style="color:#c0392b;padding:8px;background:#fdf0f0;border-right:3px solid #c0392b;">
                <b>נדרש מידע נוסף לסיווג פריט זה:</b>
                <ul style="margin:4px 0;">""")
            for q in kram_qs:
                parts.append(f"<li>{q.get('question_he', '')}</li>")
            parts.append("</ul></div>")
        elif cls:
            hs_code = cls.get("hs_code", "")
            hs_fmt = _format_hs(hs_code)
            conf = cls.get("confidence", 0)
            conf_pct = int(conf * 100) if conf <= 1 else int(conf)
            duty = cls.get("duty_rate", "")
            pt = cls.get("purchase_tax", "")
            vat = cls.get("vat_rate", broker_result.get("vat_rate", "18%"))
            desc = cls.get("description", "")
            conf_color = _COLOR_OK if conf_pct >= 70 else _COLOR_WARN if conf_pct >= 40 else "#c0392b"

            # Recommended code highlight
            parts.append(f"""<div style="font-size:13px;margin-bottom:8px;">
                <span style="font-size:18px;font-family:monospace;font-weight:bold;">{hs_fmt}</span>
                <span style="background:{conf_color};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;margin-right:8px;">{conf_pct}%</span>
                <span style="color:#555;font-size:12px;">{desc[:80]}</span>
            </div>""")

            # Official 6-column tariff table
            sub_codes = cls.get("sub_codes", [])
            if sub_codes:
                parts.append("""<table width="100%" cellpadding="5" cellspacing="0" style="border:1px solid #ccc;border-collapse:collapse;font-size:12px;margin-bottom:10px;">
                <tr style="background:#2c3e50;color:#fff;font-weight:bold;">
                    <td style="border:1px solid #555;width:15%;">פרט</td>
                    <td style="border:1px solid #555;width:35%;">תיאור</td>
                    <td style="border:1px solid #555;width:10%;">מכס כללי</td>
                    <td style="border:1px solid #555;width:10%;">מס קנייה</td>
                    <td style="border:1px solid #555;width:15%;">שיעור התוספות</td>
                    <td style="border:1px solid #555;width:15%;">יחידה סטטיסטית</td>
                </tr>""")
                for sc in sub_codes:
                    sc_hs = _format_hs(sc.get("hs_code", ""))
                    sc_desc = sc.get("description", "") or sc.get("description_en", "")
                    sc_duty = sc.get("duty_rate", "")
                    sc_pt = sc.get("purchase_tax", "")
                    is_recommended = (str(sc.get("hs_code", "")).replace(".", "").replace("/", "") ==
                                      str(hs_code).replace(".", "").replace("/", ""))
                    row_style = f"background:#e8f8f5;border-right:4px solid {_COLOR_OK};" if is_recommended else ""
                    parts.append(f"""<tr style="{row_style}">
                        <td style="border:1px solid #ddd;font-family:monospace;">{sc_hs}</td>
                        <td style="border:1px solid #ddd;">{sc_desc[:100]}</td>
                        <td style="border:1px solid #ddd;text-align:center;">{sc_duty or '—'}</td>
                        <td style="border:1px solid #ddd;text-align:center;">{sc_pt or '—'}</td>
                        <td style="border:1px solid #ddd;text-align:center;">—</td>
                        <td style="border:1px solid #ddd;text-align:center;">—</td>
                    </tr>""")
                parts.append("</table>")
            else:
                # Single-row table when no sub-codes available
                parts.append(f"""<table width="100%" cellpadding="5" cellspacing="0" style="border:1px solid #ccc;border-collapse:collapse;font-size:12px;margin-bottom:10px;">
                <tr style="background:#2c3e50;color:#fff;font-weight:bold;">
                    <td style="border:1px solid #555;">פרט</td>
                    <td style="border:1px solid #555;">תיאור</td>
                    <td style="border:1px solid #555;">מכס כללי</td>
                    <td style="border:1px solid #555;">מס קנייה</td>
                    <td style="border:1px solid #555;">מע"מ</td>
                </tr>
                <tr style="background:#e8f8f5;border-right:4px solid {_COLOR_OK};">
                    <td style="border:1px solid #ddd;font-family:monospace;">{hs_fmt}</td>
                    <td style="border:1px solid #ddd;">{desc[:100]}</td>
                    <td style="border:1px solid #ddd;text-align:center;">{duty or '—'}</td>
                    <td style="border:1px solid #ddd;text-align:center;">{pt or '—'}</td>
                    <td style="border:1px solid #ddd;text-align:center;">{vat}</td>
                </tr></table>""")

            # Chapter 98 + discount (if personal import)
            ch98_code = cls.get("chapter98_code", "")
            if ch98_code:
                ch98_desc = cls.get("chapter98_desc_he", "")
                ch98_duty = cls.get("chapter98_duty", "")
                disc = cls.get("discount", {})
                disc_desc = disc.get("discount_desc_he", "")
                disc_duty = disc.get("discount_duty", "")
                parts.append(f"""<div style="background:#e8f8f5;padding:8px;border-right:3px solid {_COLOR_OK};font-size:13px;margin-bottom:8px;">
                    <b>פרק 98:</b> {_format_hs(ch98_code)} — {ch98_desc[:60] or disc_desc[:60]}
                    <br/>מכס הנחה: <b>{disc_duty or ch98_duty or 'פטור'}</b>
                </div>""")

            # Temporary import discount (item 207)
            disc = cls.get("discount", {})
            if disc and disc.get("discount_group") == "207":
                sub_codes_207 = disc.get("sub_codes", {})
                legal_basis = disc.get("legal_basis", "")
                parts.append(f"""<div style="background:#e8f8f5;padding:8px;border-right:3px solid {_COLOR_OK};font-size:13px;margin-bottom:8px;">
                    <b>יבוא זמני — פריט 207</b> ({legal_basis})
                </div>""")
                for sc_num, sc_info in sorted(sub_codes_207.items()):
                    parts.append(f"""<div style="font-size:12px;color:#2c3e50;padding:2px 8px;">
                        {sc_info.get('desc_he', '')[:50]} — מכס: {sc_info.get('customs_duty', '')} | מס קניה: {sc_info.get('purchase_tax', '')}
                    </div>""")
                if disc.get("ata_carnet"):
                    parts.append(f"""<div style="font-size:12px;background:#fef9e7;padding:6px 8px;margin-top:4px;">
                        <b>קרנה ATA</b> — פטור מלא ממכס ומס קניה (בכפוף להגשת פנקס ATA בלשכת המסחר)
                    </div>""")

            # MOC requirement callout (FIX 4)
            if cls.get("moc_required"):
                parts.append(f"""<div style="background:#fef3e0;padding:8px;border-right:3px solid #f39c12;font-size:13px;margin-bottom:8px;">
                    <b>משרד התקשורת:</b> {cls.get('moc_note', 'נדרש אישור תקשורת 1301')}
                </div>""")

        parts.append("</td></tr>")

    # --- Block 5: FIO/FEO requirements (always shown — proves the check was done) ---
    _fio_feo_label = f"צו {'יבוא' if direction == 'import' else 'יצוא'} חופשי"
    parts.append(f"""<tr><td style="padding:8px 24px;">
    <div style="font-size:14px;font-weight:bold;color:{_RPA_BLUE};border-bottom:2px solid {_RPA_BLUE};padding-bottom:4px;margin-bottom:6px;">
        דרישות רגולטוריות — {_fio_feo_label}
    </div>""")

    _has_fio_feo = False
    for ci in items:
        cls = ci.get("classification", {})
        if not cls:
            continue
        fio = cls.get("fio", {})
        feo = cls.get("feo", {})
        if (fio and fio.get("found")) or (feo and feo.get("found")):
            if not _has_fio_feo:
                parts.append("""<table width="100%" cellpadding="4" cellspacing="0" style="border:1px solid #ddd;border-collapse:collapse;font-size:12px;">
                <tr style="background:#f0f4f8;font-weight:bold;">
                    <td style="border:1px solid #ddd;">תוספת</td>
                    <td style="border:1px solid #ddd;">רשות מאשרת</td>
                    <td style="border:1px solid #ddd;">תקן / אישור</td>
                    <td style="border:1px solid #ddd;">תנאי</td>
                </tr>""")
                _has_fio_feo = True

            if fio and fio.get("found"):
                for req in fio.get("requirements", [])[:5]:
                    parts.append(f"""<tr>
                        <td style="border:1px solid #ddd;">תוספת {req.get('appendix', '')}</td>
                        <td style="border:1px solid #ddd;">{req.get('authority', '')}</td>
                        <td style="border:1px solid #ddd;">{req.get('standard_ref', '') or req.get('confirmation_type', '')}</td>
                        <td style="border:1px solid #ddd;font-size:11px;">{req.get('conditions', '')[:80]}</td>
                    </tr>""")

            if feo and feo.get("found"):
                for req in feo.get("requirements", [])[:5]:
                    parts.append(f"""<tr>
                        <td style="border:1px solid #ddd;">תוספת {req.get('appendix', '')}</td>
                        <td style="border:1px solid #ddd;">{req.get('authority', '')}</td>
                        <td style="border:1px solid #ddd;">{req.get('confirmation_type', '')}</td>
                        <td style="border:1px solid #ddd;">—</td>
                    </tr>""")

    if _has_fio_feo:
        parts.append("</table>")
    else:
        parts.append(f"""<div style="font-size:13px;color:{_COLOR_OK};padding:4px 0;">
            בוצעה בדיקה — לא נמצאו דרישות ב{_fio_feo_label} עבור קוד המכס שנקבע.
        </div>""")
    parts.append("</td></tr>")

    # --- Block 6a: FTA (always shown) ---
    parts.append(f"""<tr><td style="padding:8px 24px;">
    <div style="font-size:14px;font-weight:bold;color:{_RPA_BLUE};border-bottom:2px solid {_RPA_BLUE};padding-bottom:4px;margin-bottom:6px;">
        הסכמי סחר חופשי (FTA)
    </div>""")
    _has_fta = False
    for ci in items:
        cls = ci.get("classification", {})
        fta = cls.get("fta", {}) if cls else {}
        if fta and fta.get("eligible"):
            _has_fta = True
            fw = fta.get("framework_order", {})
            pref_doc = fw.get("preference_document", {})
            pref_primary = pref_doc.get("primary", "") if isinstance(pref_doc, dict) else ""
            parts.append(f"""<div style="font-size:13px;background:#fef9e7;padding:8px;border-right:3px solid {_COLOR_WARN};margin-bottom:4px;">
                <b>{fta.get('agreement_name', '')}</b>
                {f" — שיעור מועדף: {fta.get('preferential_rate', '')}" if fta.get('preferential_rate') else ''}
                {f" | מסמך מקור: {pref_primary}" if pref_primary else ''}
                {f" | תוספות: {', '.join(fw.get('supplements', []))}" if fw and fw.get('supplements') else ''}
            </div>""")
    if not _has_fta:
        origin = op.get("origin_country", "")
        if origin:
            parts.append(f"""<div style="font-size:13px;color:#666;">
                בוצעה בדיקה — לא נמצא הסכם סחר חופשי עבור ארץ המוצא ({origin}).
            </div>""")
        else:
            parts.append("""<div style="font-size:13px;color:#666;">
                בוצעה בדיקה — לא צוינה ארץ מוצא. לבדיקת FTA נא לציין מאיפה הטובין.
            </div>""")
    parts.append("</td></tr>")

    # --- Block 6b: Valuation ---
    val = broker_result.get("valuation", {})
    if val and val.get("primary_method"):
        parts.append(f"""<tr><td style="padding:8px 24px;">
            <div style="font-size:14px;font-weight:bold;color:{_RPA_BLUE};border-bottom:2px solid {_RPA_BLUE};padding-bottom:4px;margin-bottom:6px;">
                הערכת שווי מכס
            </div>
            <div style="font-size:13px;">
                שיטה ראשית: <b>ערך עסקה</b> (סעיף 132 לפקודת המכס) —
                המחיר ששולם או שישולם בפועל.
            </div>
        </td></tr>""")

    # --- Block 6c: Release notes ---
    rel = broker_result.get("release_notes", [])
    if rel:
        parts.append(f"""<tr><td style="padding:8px 24px;">
            <div style="font-size:14px;font-weight:bold;color:{_RPA_BLUE};border-bottom:2px solid {_RPA_BLUE};padding-bottom:4px;margin-bottom:6px;">
                שחרור מהמכס
            </div>""")
        for note in rel:
            art = note.get("article", "")
            title = note.get("title_he", "")
            reason = note.get("applies_because", "")
            parts.append(f"""<div style="font-size:13px;margin-bottom:4px;">
                סעיף {art}: {title}
                {f'<span style="color:{_COLOR_OK};"> — חל עליך כ{reason}</span>' if reason else ''}
            </div>""")
        parts.append("</td></tr>")

    # --- Block 6d: Temporary import ordinance articles ---
    ord_arts = broker_result.get("ordinance_articles", {})
    temp_keys = [k for k in ord_arts if k.startswith(("temporary_", "exhibition_", "regulation_"))]
    if temp_keys:
        parts.append(f"""<tr><td style="padding:8px 24px;">
            <div style="font-size:14px;font-weight:bold;color:{_RPA_BLUE};border-bottom:2px solid {_RPA_BLUE};padding-bottom:4px;margin-bottom:6px;">
                יבוא זמני — בסיס חוקי
            </div>""")
        for k in temp_keys:
            art_data = ord_arts[k]
            art = art_data.get("article", "")
            title = art_data.get("title_he", "")
            summary = art_data.get("summary", "")
            parts.append(f"""<div style="font-size:13px;margin-bottom:4px;">
                <b>סעיף {art}</b>: {title}
                <br/><span style="color:#555;font-size:12px;">{summary[:150]}</span>
            </div>""")
        parts.append(f"""<div style="font-size:13px;margin-top:8px;padding:8px;background:#fef9e7;border-right:3px solid {_COLOR_WARN};">
            <b>קרנה ATA (ATA Carnet)</b>: פנקס בין-לאומי המאפשר יבוא זמני ללא תשלום מכס ומס קניה.
            ניתן להנפיק בלשכת המסחר הישראלית. בתוקף עד שנה, חובת יצוא חוזר בתוך התקופה.
            <br/>חלופה: ערבות בנקאית/מזומן בגובה המכס (סעיף 162 לפקודת המכס).
        </div>""")
        parts.append("</td></tr>")

    # --- Footer ---
    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")
    parts.append(f"""<tr><td style="background:#f8f9fa;padding:12px 24px;font-size:11px;color:#999;text-align:center;">
        RCB | RPA-PORT | {now_str} UTC | Broker Engine (deterministic)
        <br/>סיווג זה הוא הערכה מקצועית ואינו מהווה אישור רשמי של רשות המכס.
        <br/>מתודולוגיה: נוהל סיווג טובין #3 | כללי פרשנות GIR 1-6 | אלימינציה דטרמיניסטית
    </td></tr></table></body></html>""")

    return "\n".join(parts)


def _format_hs(hs_code):
    """Format HS code to Israeli display format XX.XX.XXXXXX/X (with Luhn check digit)."""
    raw = str(hs_code)
    # If already has check digit after slash, preserve it
    check = ""
    if "/" in raw:
        raw, check = raw.split("/", 1)
    clean = raw.replace(".", "").replace(" ", "")
    clean = clean.ljust(10, "0")[:10]
    if not check and len(clean) == 10 and clean.isdigit():
        # Compute Luhn check digit
        total = 0
        for i, ch in enumerate(reversed(clean)):
            d = int(ch)
            if i % 2 == 0:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        check = str((10 - total % 10) % 10)
    if len(clean) >= 10:
        return f"{clean[:2]}.{clean[2:4]}.{clean[4:10]}/{check}"
    elif len(clean) >= 4:
        return f"{clean[:2]}.{clean[2:4]}.{clean[4:]}"
    return clean


# ═══════════════════════════════════════════
#  REPLY SENDING
# ═══════════════════════════════════════════

def _send_consultation_reply(msg, content, context_package, access_token, rcb_email, db,
                             composed_result=None):
    """Send the consultation reply with RCB branding.

    Args:
        composed_result: If provided (from composition pipeline), use its HTML
                         instead of wrapping content with _wrap_html_rtl.
    """
    if composed_result:
        tracking_code = composed_result["tracking_code"]
        subject = composed_result["subject"]
        body_html = composed_result["html"]
    else:
        tracking_code = _generate_query_tracking_code()
        domain_label = _DOMAIN_LABELS.get(context_package.domain, "מכס")

        # Build subject
        orig_subject = (msg.get("subject") or "").strip()
        orig_clean = re.sub(r'^(?:\s*(?:Re|RE|re|Fwd|FWD|FW|Fw|fw)\s*:\s*)+', '', orig_subject).strip()
        if orig_clean and len(orig_clean) >= 3:
            topic = orig_clean[:50]
        else:
            topic = context_package.original_body[:50].strip()
            if len(context_package.original_body) > 50:
                topic += "..."
        subject = f"RCB | {tracking_code} | {domain_label} | {topic}"

        # Legacy: Wrap content in HTML
        body_html = _wrap_html_rtl(content, subject)

    # Send via the safe reply mechanism
    sent = _send_reply_safe(body_html, msg, access_token, rcb_email,
                            subject_override=subject)

    # Log to questions_log for cache
    if sent and db and context_package:
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
                        get_secret_func, triage_result=None, template_type="consultation",
                        thread_context=None):
    """
    Main entry point for CONSULTATION and LIVE_SHIPMENT emails.

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

    # 1. Check sub-intent (skip for live_shipment — triage already classified)
    if detect_email_intent and template_type == "consultation":
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

    # 1b. Try broker engine (Session 90) — deterministic, no AI tool loop
    _broker_sent = False  # Guard: if broker sends, do NOT let legacy also send
    if BROKER_ENGINE_AVAILABLE and template_type != "live_shipment":
        try:
            # Merge thread context (FIX 6) — prepend original question for continuity
            _broker_text = subject + "\n" + body_text
            if thread_context and thread_context.get("original_question"):
                _broker_text = (
                    f"Original question: {thread_context['original_question']}\n"
                    f"Follow-up reply:\n{_broker_text}"
                )
            print(f"    Broker Engine: deterministic classification")
            broker_result = broker_process_case(
                _broker_text, "", db, get_secret_func,
            )
            if broker_result and broker_result.get("status") == "completed":
                items = broker_result.get("items", [])
                classified_count = sum(
                    1 for it in items
                    if it.get("classification", {}).get("verified")
                )
                print(f"    Broker Engine: {classified_count}/{len(items)} verified")
                if classified_count > 0:
                    # Render broker result to HTML and send
                    html = _render_broker_result_html(broker_result)
                    tracking_code = _generate_query_tracking_code()
                    legal_he = broker_result.get("operation", {}).get("legal_category_he", "")
                    broker_subject = f"RCB | {tracking_code} | {legal_he or 'סיווג'} | {(msg.get('subject') or '')[:40]}"
                    composed = {
                        "tracking_code": tracking_code,
                        "subject": broker_subject,
                        "html": html,
                    }
                    sent = _send_consultation_reply(
                        msg, "", None, access_token, rcb_email, db,
                        composed_result=composed,
                    )
                    _broker_sent = sent  # Mark BEFORE return so except block knows
                    elapsed = int((time.time() - t0) * 1000)
                    print(f"    Broker Engine: sent={sent}, elapsed={elapsed}ms")
                    return {
                        "status": "replied" if sent else "send_failed",
                        "handler": "consultation",
                        "level": -1,
                        "model": "broker_engine",
                        "elapsed_ms": elapsed,
                    }
            elif broker_result and broker_result.get("status") == "kram":
                print(f"    Broker Engine: kram — needs clarification")
                # Fall through to composition pipeline with kram data
        except Exception as e:
            print(f"    Broker Engine error: {e}")
            import traceback
            traceback.print_exc()
            # If broker already sent the email, do NOT fall through to legacy
            if _broker_sent:
                elapsed = int((time.time() - t0) * 1000)
                return {
                    "status": "replied",
                    "handler": "consultation",
                    "level": -1,
                    "model": "broker_engine",
                    "elapsed_ms": elapsed,
                }

    # 2. Run SIF
    if not prepare_context_package:
        return {"status": "error", "handler": "consultation", "error": "SIF unavailable"}

    context_package = prepare_context_package(subject, body_text, db, get_secret_func)
    print(f"    📦 SIF: domain={context_package.domain}, lang={context_package.detected_language}, "
          f"confidence={context_package.confidence:.2f}, "
          f"tariff={len(context_package.tariff_results)}, "
          f"ordinance={len(context_package.ordinance_articles)}, "
          f"xml={len(context_package.xml_results)}")

    # 2b. Try composition pipeline (Session 87) — structured JSON + branded HTML
    if COMPOSITION_LAYER_AVAILABLE:
        print(f"    🎯 Trying composition pipeline (evidence→straitjacket→composer)")
        composed = _run_composition_pipeline(context_package, get_secret_func, msg,
                                               template_type=template_type, db=db)
        if composed:
            sent = _send_consultation_reply(msg, "", context_package,
                                            access_token, rcb_email, db,
                                            composed_result=composed)
            _log_to_pupil(context_package,
                          [("composition_pipeline", composed.get("tracking_code", ""))],
                          "composition", db)
            elapsed = int((time.time() - t0) * 1000)
            return {"status": "replied" if sent else "send_failed",
                    "handler": "consultation", "level": 0, "model": "composition",
                    "elapsed_ms": elapsed, "confidence": context_package.confidence}
        print(f"    ⚠️ Composition pipeline failed — falling back to legacy ladder")

    # 3. LEVEL 1: Gemini Flash (legacy fallback)
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
