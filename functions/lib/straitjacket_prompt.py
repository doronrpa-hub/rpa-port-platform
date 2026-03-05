"""
Straitjacket Prompt — Force AI to Cite Only Fetched Evidence
=============================================================
Dynamically generates the AI system prompt from an EvidenceBundle.
The AI sees ONLY what the system found — no training data allowed.

The prompt:
  1. Lists every source found (with article/code/ref)
  2. Lists every source searched but NOT found
  3. Demands structured JSON output with source citations
  4. Forbids adding information not in the bundle

Usage:
    from lib.straitjacket_prompt import build_straitjacket_prompt, parse_ai_response
"""

import json
import re
from typing import Optional


# -----------------------------------------------------------------------
#  PROMPT BUILDER
# -----------------------------------------------------------------------

def build_straitjacket_prompt(bundle):
    """Build the AI system + user prompt from an EvidenceBundle.

    Args:
        bundle: EvidenceBundle from evidence_types.py

    Returns:
        dict with 'system' and 'user' prompt strings
    """
    system = _build_system_prompt(bundle)
    user = _build_user_prompt(bundle)
    return {"system": system, "user": user}


def _build_system_prompt(bundle):
    """Build the system prompt with strict rules."""
    direction_label = {
        "import": "יבוא",
        "export": "יצוא",
        "transit": "טרנזיט",
    }.get(bundle.direction, "לא ידוע")

    parts = [
        "אתה RCB — סוכן מכס מורשה של R.P.A. PORT LTD, חיפה.",
        f"כיוון הסחר: {direction_label}.",
        f"תחום: {bundle.domain}.",
        "",
        "═══ כללים בלתי ניתנים לשינוי ═══",
        "",
        "1. מותר לך לצטט אך ורק מידע שמופיע בבלוק EVIDENCE למטה.",
        "2. כל טענה חייבת לכלול source_ref (מספר סעיף, פרט מכס, שם נוהל).",
        "3. אם מידע על נושא מסוים לא נמצא — כתוב 'לא נמצא במקורות שלנו' ואל תמציא.",
        "4. לעולם אל תכתוב 'לא ניתן לסווג' — תמיד תן מועמדים עם רמת ביטחון, גם אם נמוכה.",
        "5. לעולם אל תכתוב 'מומלץ לפנות לעמיל מכס' — אנחנו עמיל המכס.",
        "6. ציטוטי חוק חייבים להיות מילה במילה מהטקסט המסופק.",
        "7. אם השאלה כוללת ידע כללי — ענה בחום מהמקורות שסופקו ואז קשר למכס.",
        "8. התשובה חייבת להיות JSON בפורמט המוגדר למטה — לא טקסט חופשי.",
        "",
    ]

    # Sources found / not found
    parts.append("═══ מקורות שנמצאו ═══")
    if bundle.sources_found:
        for src in bundle.sources_found:
            parts.append(f"  ✓ {src}")
    else:
        parts.append("  (לא נמצאו מקורות)")
    parts.append("")

    parts.append("═══ מקורות שלא נמצאו ═══")
    if bundle.sources_not_found:
        for src in bundle.sources_not_found:
            parts.append(f"  ✗ {src}")
    else:
        parts.append("  (הכל נמצא)")
    parts.append("")

    # JSON output schema
    parts.append("═══ פורמט פלט — JSON בלבד ═══")
    parts.append(_get_output_schema(bundle))
    parts.append("")

    return "\n".join(parts)


def _build_user_prompt(bundle):
    """Build the user prompt with all evidence data."""
    parts = []

    parts.append(f"נושא: {bundle.original_subject}")
    parts.append(f"גוף: {bundle.original_body}")
    parts.append("")
    parts.append("═══ EVIDENCE ═══")
    parts.append("")

    # Tariff entries
    if bundle.tariff_entries:
        parts.append("── תעריף המכס ──")
        for entry in bundle.tariff_entries:
            parts.append(
                f"  פרט {entry.get('hs_code', '')}: "
                f"{entry.get('description_he', '')} | "
                f"מכס: {entry.get('duty', '')} | "
                f"מס קניה: {entry.get('purchase_tax', '')} | "
                f"מע\"מ: {entry.get('vat', '18%')} | "
                f"[{entry.get('source_ref', '')}]"
            )
        parts.append("")

    # Ordinance articles
    if bundle.ordinance_articles:
        parts.append("── פקודת המכס ──")
        for art in bundle.ordinance_articles:
            text = art.get("full_text_he", "")
            if text and len(text) > 800:
                text = text[:800] + "..."
            parts.append(
                f"  סעיף {art.get('article_id', '')}: "
                f"{art.get('title_he', '')} "
                f"[{art.get('source_ref', '')}]"
            )
            if text:
                parts.append(f"    {text}")
        parts.append("")

    # Framework articles
    if bundle.framework_articles:
        parts.append("── צו מסגרת ──")
        for art in bundle.framework_articles:
            text = art.get("text", "")
            if text and len(text) > 500:
                text = text[:500] + "..."
            parts.append(
                f"  סעיף {art.get('article_id', '')}: "
                f"{art.get('title_he', '')} "
                f"[{art.get('source_ref', '')}]"
            )
            if text:
                parts.append(f"    {text}")
        parts.append("")

    # Regulatory requirements
    if bundle.regulatory_requirements:
        decree = bundle.direction_config.get("decree_name_he", "צו יבוא חופשי")
        parts.append(f"── {decree} ──")
        for req in bundle.regulatory_requirements:
            parts.append(
                f"  {req.get('supplement', '')}: "
                f"גורם: {req.get('authority', '')} | "
                f"דרישה: {req.get('requirement', '')} | "
                f"תקן: {req.get('standard', '')} | "
                f"[{req.get('source_ref', '')}]"
            )
        parts.append("")

    # FTA data
    if bundle.fta_data and bundle.fta_data.get("applicable"):
        parts.append("── הסכם סחר חופשי ──")
        fta = bundle.fta_data
        parts.append(f"  מדינה: {fta.get('country', '')}")
        parts.append(f"  כללי מקור: {fta.get('origin_rules', '')}")
        parts.append(f"  סוג הצהרה: {fta.get('declaration_type', '')}")
        parts.append(f"  שיעור העדפה: {fta.get('preferential_rate', '')}")
        parts.append(f"  [{fta.get('source_ref', '')}]")
        parts.append("")

    # Directives
    if bundle.directives:
        parts.append("── הנחיות סיווג ──")
        for d in bundle.directives:
            content = d.get("content", "")
            if content and len(content) > 500:
                content = content[:500] + "..."
            parts.append(
                f"  {d.get('directive_id', '')}: {d.get('title', '')} | "
                f"HS: {d.get('hs_code', '')} [{d.get('source_ref', '')}]"
            )
            if content:
                parts.append(f"    {content}")
        parts.append("")

    # Valuation articles (import only)
    if bundle.valuation_articles:
        parts.append("── סעיפי הערכה (פקודת המכס) ──")
        for piece in bundle.valuation_articles:
            fact = piece.fact if hasattr(piece, 'fact') else str(piece)
            if len(fact) > 800:
                fact = fact[:800] + "..."
            ref = piece.source_ref if hasattr(piece, 'source_ref') else ""
            parts.append(f"  [{ref}]")
            parts.append(f"    {fact}")
        parts.append("")

    # Release articles (import only)
    if bundle.release_articles:
        parts.append("── סעיפי שחרור ──")
        for piece in bundle.release_articles:
            fact = piece.fact if hasattr(piece, 'fact') else str(piece)
            if len(fact) > 800:
                fact = fact[:800] + "..."
            ref = piece.source_ref if hasattr(piece, 'source_ref') else ""
            parts.append(f"  [{ref}]")
            parts.append(f"    {fact}")
        parts.append("")

    # Procedure refs
    if bundle.procedure_refs:
        parts.append("── נהלי מכס ──")
        for proc in bundle.procedure_refs:
            text = proc.get("relevant_text", "")
            if text and len(text) > 500:
                text = text[:500] + "..."
            parts.append(
                f"  {proc.get('source_name', '')}: {proc.get('name_he', '')} "
                f"[{proc.get('source_ref', '')}]"
            )
            if text:
                parts.append(f"    {text}")
        parts.append("")

    # Web results
    if bundle.web_results:
        parts.append("── מקורות אינטרנט ──")
        for w in bundle.web_results:
            text = w.get("text", "")
            if text and len(text) > 500:
                text = text[:500] + "..."
            url = w.get("source_url", "")
            parts.append(f"  {w.get('source_name', '')}")
            if url:
                parts.append(f"  URL: {url}")
            if text:
                parts.append(f"    {text}")
        parts.append("")

    # Supplier results
    if bundle.supplier_results:
        parts.append("── אתר ספק ──")
        for s in bundle.supplier_results:
            content = s.get("content", "")
            if content and len(content) > 500:
                content = content[:500] + "..."
            parts.append(f"  {s.get('url', '')} [{s.get('source_ref', '')}]")
            if content:
                parts.append(f"    {content}")
        parts.append("")

    # XML results
    if bundle.xml_results:
        parts.append("── מסמכי עזר ──")
        for x in bundle.xml_results:
            content = x.get("content", "")
            if content and len(content) > 500:
                content = content[:500] + "..."
            parts.append(f"  {x.get('title', '')} [{x.get('source_ref', '')}]")
            if content:
                parts.append(f"    {content}")
        parts.append("")

    # Entities
    if bundle.entities:
        parts.append("── ישויות שזוהו ──")
        for k, v in bundle.entities.items():
            parts.append(f"  {k}: {v}")
        parts.append("")

    parts.append("═══ סוף EVIDENCE ═══")
    parts.append("")
    parts.append("כתוב את תשובתך כ-JSON בלבד. אל תוסיף טקסט לפני או אחרי ה-JSON.")

    return "\n".join(parts)


# -----------------------------------------------------------------------
#  OUTPUT SCHEMA
# -----------------------------------------------------------------------

def _get_output_schema(bundle):
    """Return the JSON output schema description for the AI."""
    schema = {
        "diagnosis": {
            "text": "תשובה ישירה בעברית — 2-4 משפטים",
            "certainty": "high / medium / low",
            "sources_cited": ["source_ref מדויק מתוך ה-EVIDENCE"],
            "law_quote": "ציטוט מילה במילה מטקסט החוק (אם רלוונטי) — או null",
            "law_ref": "source_ref של הציטוט — או null",
        },
        "clarification_questions": [
            {"question": "שאלת הבהרה (אם צריך)", "why_needed": "מדוע זה חשוב"}
        ],
    }

    # Add tariff section if tariff data exists
    if bundle.tariff_entries:
        schema["hs_candidates"] = [
            {
                "code": "XX.XX.XXXXXX",
                "description": "תיאור בעברית",
                "confidence": "high / medium / low",
                "duty": "שיעור מכס",
                "purchase_tax": "מס קניה",
                "vat": "מע\"מ",
                "source_ref": "פרט XX.XX",
            }
        ]

    # Add regulatory section if regulatory data exists
    if bundle.regulatory_requirements:
        schema["regulatory"] = [
            {
                "authority": "שם הגורם",
                "requirement": "תיאור הדרישה",
                "standard": "תקן (אם יש)",
                "source_ref": "source_ref",
            }
        ]

    # Add FTA section if FTA data exists
    if bundle.fta_data and bundle.fta_data.get("applicable"):
        schema["fta"] = {
            "applicable": True,
            "country": "שם המדינה",
            "preferential_rate": "שיעור העדפה",
            "origin_rule": "כלל מקור",
            "declaration_type": "סוג הצהרה (EUR.1 / הצהרת חשבון / תעודת מקור)",
            "source_ref": "source_ref",
        }

    # Valuation for import
    if bundle.valuation_articles:
        schema["valuation_notes"] = {
            "text": "הסבר קצר על הערכת ערך מכס",
            "article_ref": "סעיף XX לפקודת המכס",
        }

    # Release for import
    if bundle.release_articles:
        schema["release_notes"] = {
            "text": "הסבר על תהליך השחרור",
            "article_ref": "סעיף XX",
        }

    # Web results for general queries
    if bundle.web_results:
        schema["web_answer"] = {
            "text": "תשובה מבוססת על מקורות האינטרנט",
            "sources": [{"title": "כותרת", "url": "כתובת URL"}],
        }

    # English summary always
    schema["english_summary"] = "2-3 sentence summary in English"

    return json.dumps(schema, ensure_ascii=False, indent=2)


# -----------------------------------------------------------------------
#  RESPONSE PARSER
# -----------------------------------------------------------------------

def parse_ai_response(raw_text):
    """Parse the AI response, expecting JSON.

    Returns:
        dict with parsed response, or None if unparseable.
        On failure, returns {"_parse_error": True, "_raw": raw_text}
    """
    if not raw_text or not raw_text.strip():
        return {"_parse_error": True, "_raw": "", "_error": "empty_response"}

    text = raw_text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        # Remove first line (```json or ```)
        first_newline = text.find("\n")
        if first_newline > 0:
            text = text[first_newline + 1:]
        # Remove trailing ```
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    # Try direct JSON parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return {"_parse_error": True, "_raw": raw_text, "_error": "json_parse_failed"}


def is_valid_response(parsed):
    """Check if the parsed AI response has minimum required fields.

    A valid response must have diagnosis.text (non-empty).
    """
    if not parsed or not isinstance(parsed, dict):
        return False
    if parsed.get("_parse_error"):
        return False

    diagnosis = parsed.get("diagnosis")
    if not diagnosis or not isinstance(diagnosis, dict):
        return False

    text = diagnosis.get("text", "")
    if not text or len(text.strip()) < 10:
        return False

    return True


def needs_escalation(parsed):
    """Determine if the response needs AI escalation.

    Returns:
        str reason if escalation needed, None if response is acceptable.
    """
    if not parsed:
        return "empty_response"

    if parsed.get("_parse_error"):
        return parsed.get("_error", "parse_error")

    if not is_valid_response(parsed):
        return "invalid_response"

    # Check diagnosis has at least one source citation
    diagnosis = parsed.get("diagnosis", {})
    sources = diagnosis.get("sources_cited", [])
    if not sources:
        # Not an escalation trigger if it's a general knowledge query
        # but worth noting — the response may be from training data
        pass

    return None
