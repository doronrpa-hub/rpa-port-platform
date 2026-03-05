"""
Reply Composer — Render Branded HTML from Structured Data
==========================================================
12 block builders + 4 template orchestrators.
Pure Python HTML renderers — NO AI in the rendering step.
AI outputs structured JSON, Python renders branded HTML from data.

Usage:
    from lib.reply_composer import compose_consultation, compose_live_shipment
"""

import hashlib
import random
import string
from datetime import datetime, timezone, timedelta

# -----------------------------------------------------------------------
#  CONSTANTS (shared with tracker_email.py)
# -----------------------------------------------------------------------

_RPA_BLUE = "#1e3a5f"
_RPA_ACCENT = "#2471a3"
_COLOR_OK = "#27ae60"
_COLOR_WARN = "#f39c12"
_COLOR_ERR = "#e74c3c"
_COLOR_PENDING = "#999999"
_LOGO_URL = (
    "https://storage.googleapis.com/rpa-port-customs.appspot.com"
    "/public/rpa_logo_small.png"
)
_IL_TZ = timezone(timedelta(hours=2))

_DIRECTION_LABELS = {
    "import": "יבוא",
    "export": "יצוא",
    "transit": "טרנזיט",
    "unknown": "כללי",
}

_TEMPLATE_LABELS = {
    "consultation": "ייעוץ",
    "live_shipment": "סיווג משלוח",
    "tracking": "מעקב",
    "combined": "סיווג + מעקב",
}


def _esc(text):
    """HTML-escape text."""
    if not text:
        return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _now_il():
    """Current time in Israel timezone."""
    return datetime.now(_IL_TZ)


def _generate_tracking_code():
    """Generate a unique tracking code."""
    ts = _now_il().strftime("%Y%m%d")
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"RCB-Q-{ts}-{rand}"


# -----------------------------------------------------------------------
#  BLOCK 1: HEADER
# -----------------------------------------------------------------------

def _block_header(direction, template_type, tracking_code=""):
    """Branded header with RPA-PORT logo and direction badge."""
    dir_label = _DIRECTION_LABELS.get(direction, "כללי")
    tmpl_label = _TEMPLATE_LABELS.get(template_type, "ייעוץ")
    badge_text = f"{tmpl_label}"
    if direction and direction != "unknown":
        badge_text = f"{dir_label} | {tmpl_label}"

    return f"""
<table width="100%" cellpadding="0" cellspacing="0" style="background:{_RPA_BLUE};">
<tr>
  <td style="padding:18px 24px;" valign="middle">
    <span style="display:inline-block;vertical-align:middle;width:44px;height:44px;
      line-height:44px;text-align:center;background:#fff;color:{_RPA_BLUE};
      font-size:18px;font-weight:bold;border-radius:6px;
      font-family:Georgia,'Times New Roman',serif;">RCB</span>
    <span style="display:inline-block;vertical-align:middle;padding-right:12px;">
      <span style="color:#ffffff;font-size:16px;font-weight:bold;display:block;">
        R.P.A. PORT LTD</span>
      <span style="color:#aed6f1;font-size:12px;display:block;">
        RCB Customs Intelligence</span>
    </span>
  </td>
  <td align="left" style="padding:18px 24px;" valign="middle">
    <span style="display:inline-block;padding:5px 14px;border-radius:10px;
      font-size:13px;font-weight:bold;color:#fff;background:{_RPA_ACCENT};">
      {_esc(badge_text)}</span>
  </td>
</tr>
</table>
"""


# -----------------------------------------------------------------------
#  BLOCK 1b: TRACKING BAR
# -----------------------------------------------------------------------

def _block_tracking_bar(tracking_code):
    """Light tracking bar below header."""
    now = _now_il().strftime("%d/%m/%Y %H:%M")
    return f"""
<table width="100%" cellpadding="0" cellspacing="0"
  style="background:#eaf2f8;border-bottom:1px solid #d4e6f1;">
<tr>
  <td style="padding:8px 24px;font-size:12px;color:{_RPA_ACCENT};">
    <strong>מספר פניה:</strong> {_esc(tracking_code)} &nbsp;&bull;&nbsp;
    <strong>תאריך:</strong> {now} IL
  </td>
</tr>
</table>
"""


# -----------------------------------------------------------------------
#  BLOCK 2: GREETING
# -----------------------------------------------------------------------

def _block_greeting(recipient_name=""):
    """Personal Hebrew greeting."""
    name = recipient_name or ""
    greeting = f"שלום{' ' + _esc(name) if name else ''},"
    return f"""
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="padding:20px 24px 10px;font-size:14px;line-height:1.8;color:#333;">
<p style="margin:0 0 12px;">{greeting}</p>
</td></tr>
</table>
"""


# -----------------------------------------------------------------------
#  BLOCK 3: DIAGNOSIS
# -----------------------------------------------------------------------

def _block_diagnosis(diagnosis_data):
    """Main answer block with law citations.

    Args:
        diagnosis_data: dict with text, certainty, sources_cited, law_quote, law_ref
    """
    if not diagnosis_data:
        return ""

    text = _esc(diagnosis_data.get("text", ""))
    certainty = diagnosis_data.get("certainty", "")
    sources = diagnosis_data.get("sources_cited", [])
    law_quote = diagnosis_data.get("law_quote")
    law_ref = diagnosis_data.get("law_ref")

    # Certainty badge
    cert_color = {
        "high": _COLOR_OK, "medium": _COLOR_WARN, "low": _COLOR_ERR,
    }.get(certainty, _COLOR_PENDING)
    cert_label = {
        "high": "רמת ודאות גבוהה", "medium": "רמת ודאות בינונית", "low": "רמת ודאות נמוכה",
    }.get(certainty, "")

    parts = []
    parts.append(f'<div class="section-title">תשובה</div>')

    # Diagnosis text
    parts.append(f'<div class="quote-block">{text}</div>')

    # Certainty badge
    if cert_label:
        parts.append(
            f'<p style="margin:6px 0;"><span style="display:inline-block;padding:3px 10px;'
            f'border-radius:10px;font-size:11px;font-weight:bold;color:#fff;'
            f'background:{cert_color};">{_esc(cert_label)}</span></p>'
        )

    # Law citation
    if law_quote:
        ref_text = f' — {_esc(law_ref)}' if law_ref else ""
        parts.append(
            f'<div class="section-title">ציטוט מהחוק</div>'
            f'<div class="law-cite">{_esc(law_quote)}{ref_text}</div>'
        )

    # Sources cited
    if sources:
        parts.append('<p style="font-size:12px;color:#666;margin:8px 0 0 0;">'
                     f'מקורות: {", ".join(_esc(s) for s in sources)}</p>')

    return _wrap_section(parts)


# -----------------------------------------------------------------------
#  BLOCK 4: TARIFF TABLE
# -----------------------------------------------------------------------

def _block_tariff_table(hs_candidates):
    """HS code candidates table with duty/PT/VAT.

    Args:
        hs_candidates: list of dicts with code, description, confidence,
                       duty, purchase_tax, vat, source_ref
    """
    if not hs_candidates:
        return ""

    rows = []
    for c in hs_candidates:
        conf = c.get("confidence", "")
        conf_color = {
            "high": _COLOR_OK, "medium": _COLOR_WARN, "low": _COLOR_ERR,
        }.get(conf, _COLOR_PENDING)
        conf_label = {"high": "גבוה", "medium": "בינוני", "low": "נמוך"}.get(conf, "—")

        rows.append(f"""<tr>
  <td class="hs-code">{_esc(c.get('code', ''))}</td>
  <td>{_esc(c.get('description', ''))}</td>
  <td style="text-align:center;">{_esc(c.get('duty', '—'))}</td>
  <td style="text-align:center;">{_esc(c.get('purchase_tax', '—'))}</td>
  <td style="text-align:center;">{_esc(c.get('vat', '18%'))}</td>
  <td style="text-align:center;"><span style="display:inline-block;padding:2px 8px;
    border-radius:8px;font-size:10px;font-weight:bold;color:#fff;
    background:{conf_color};">{_esc(conf_label)}</span></td>
</tr>""")

    return f"""
<div class="section-title">סיווג מכס — מועמדים</div>
<table class="tariff-table">
<thead><tr>
  <th style="width:18%;">פרט מכס</th>
  <th>תיאור</th>
  <th style="width:10%;text-align:center;">מכס</th>
  <th style="width:10%;text-align:center;">מס קניה</th>
  <th style="width:8%;text-align:center;">מע"מ</th>
  <th style="width:10%;text-align:center;">ביטחון</th>
</tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
"""


# -----------------------------------------------------------------------
#  BLOCK 5: FIO / FEO (Regulatory)
# -----------------------------------------------------------------------

def _block_fio_feo(regulatory_data, direction="import"):
    """Free Import/Export Order requirements table.

    Args:
        regulatory_data: list of dicts with authority, requirement, standard, source_ref
        direction: import or export
    """
    if not regulatory_data:
        return ""

    title = "צו יבוא חופשי — דרישות רגולטוריות" if direction == "import" \
        else "צו יצוא חופשי — דרישות רגולטוריות"
    header_bg = _COLOR_OK

    rows = []
    for req in regulatory_data:
        rows.append(f"""<tr>
  <td>{_esc(req.get('authority', ''))}</td>
  <td>{_esc(req.get('requirement', ''))}</td>
  <td>{_esc(req.get('standard', '—'))}</td>
  <td style="font-size:11px;color:#666;">{_esc(req.get('source_ref', ''))}</td>
</tr>""")

    return f"""
<div class="section-title">{_esc(title)}</div>
<table class="fio-table">
<thead><tr style="background:{header_bg};">
  <th>גורם מאשר</th>
  <th>דרישה</th>
  <th>תקן</th>
  <th>מקור</th>
</tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
"""


# -----------------------------------------------------------------------
#  BLOCK 6: FTA
# -----------------------------------------------------------------------

def _block_fta(fta_data, direction="import"):
    """Free Trade Agreement details box.

    Args:
        fta_data: dict with applicable, country, preferential_rate,
                  origin_rule, declaration_type, source_ref
    """
    if not fta_data or not fta_data.get("applicable"):
        return ""

    country = _esc(fta_data.get("country", ""))
    pref_rate = _esc(fta_data.get("preferential_rate", ""))
    origin = _esc(fta_data.get("origin_rule", ""))
    decl = _esc(fta_data.get("declaration_type", ""))
    ref = _esc(fta_data.get("source_ref", ""))

    dir_note = "כללי מקור לייבוא" if direction == "import" else "הוכחת מקור ליצוא"

    return f"""
<div class="section-title">הסכם סחר חופשי — {_esc(country)}</div>
<div class="fta-box">
  <table width="100%" cellpadding="4" cellspacing="0" style="font-size:13px;">
  <tr>
    <td style="width:30%;font-weight:bold;color:{_RPA_BLUE};">מדינה:</td>
    <td>{country}</td>
  </tr>
  <tr>
    <td style="font-weight:bold;color:{_RPA_BLUE};">{dir_note}:</td>
    <td>{origin}</td>
  </tr>
  <tr>
    <td style="font-weight:bold;color:{_RPA_BLUE};">סוג הצהרה:</td>
    <td>{decl}</td>
  </tr>
  <tr>
    <td style="font-weight:bold;color:{_RPA_BLUE};">שיעור העדפה:</td>
    <td><strong style="color:{_COLOR_OK};">{pref_rate}</strong></td>
  </tr>
  <tr>
    <td colspan="2" style="font-size:11px;color:#666;padding-top:6px;">
      מקור: {ref}
    </td>
  </tr>
  </table>
</div>
"""


# -----------------------------------------------------------------------
#  BLOCK 7: VALUATION
# -----------------------------------------------------------------------

def _block_valuation(valuation_data):
    """Customs value explanation citing ordinance articles.

    Args:
        valuation_data: dict with text, article_ref
    """
    if not valuation_data:
        return ""

    text = _esc(valuation_data.get("text", ""))
    ref = _esc(valuation_data.get("article_ref", ""))

    return f"""
<div class="section-title">הערכת ערך מכס</div>
<div class="note-box">
  <p style="margin:0 0 6px;font-size:13px;">{text}</p>
  <p style="margin:0;font-size:11px;color:#888;">מקור: {ref}</p>
</div>
"""


# -----------------------------------------------------------------------
#  BLOCK 8: RELEASE NOTES
# -----------------------------------------------------------------------

def _block_release_notes(release_data):
    """Release procedure notes.

    Args:
        release_data: dict with text, article_ref
    """
    if not release_data:
        return ""

    text = _esc(release_data.get("text", ""))
    ref = _esc(release_data.get("article_ref", ""))

    return f"""
<div class="section-title">הערות שחרור</div>
<div class="note-box">
  <p style="margin:0 0 6px;font-size:13px;">{text}</p>
  <p style="margin:0;font-size:11px;color:#888;">מקור: {ref}</p>
</div>
"""


# -----------------------------------------------------------------------
#  BLOCK: WEB ANSWER (for general queries)
# -----------------------------------------------------------------------

def _block_web_answer(web_answer):
    """Web-sourced answer with cited URLs.

    Args:
        web_answer: dict with text, sources[{title, url}]
    """
    if not web_answer:
        return ""

    text = _esc(web_answer.get("text", ""))
    sources = web_answer.get("sources", [])

    source_links = ""
    if sources:
        items = []
        for s in sources:
            title = _esc(s.get("title", ""))
            url = _esc(s.get("url", ""))
            if url:
                items.append(f'<li><a href="{url}" style="color:{_RPA_ACCENT};'
                             f'text-decoration:none;">{title or url}</a></li>')
            elif title:
                items.append(f'<li>{title}</li>')
        if items:
            source_links = f'<ul style="margin:8px 0 0;padding:0 20px;font-size:12px;">{"".join(items)}</ul>'

    return f"""
<div class="section-title">תשובה ממקורות אינטרנט</div>
<div class="quote-block">{text}</div>
{source_links}
"""


# -----------------------------------------------------------------------
#  BLOCK: CLARIFICATION QUESTIONS
# -----------------------------------------------------------------------

def _block_clarifications(questions):
    """Clarification questions the system needs answered.

    Args:
        questions: list of dicts with question, why_needed
    """
    if not questions:
        return ""

    items = []
    for q in questions:
        question = _esc(q.get("question", ""))
        why = _esc(q.get("why_needed", ""))
        items.append(f'<li style="margin:4px 0;font-size:13px;color:#333;">'
                     f'{question}'
                     f'{"  — " + why if why else ""}'
                     f'</li>')

    return f"""
<div class="section-title">שאלות הבהרה</div>
<ul class="question-list">
{''.join(items)}
</ul>
"""


# -----------------------------------------------------------------------
#  BLOCK: ENGLISH SUMMARY
# -----------------------------------------------------------------------

def _block_english_summary(summary_text):
    """English summary block."""
    if not summary_text:
        return ""

    return f"""
<div class="section-title">English Summary</div>
<p style="font-size:13px;line-height:1.6;color:#555;margin:6px 0;direction:ltr;text-align:left;">
{_esc(summary_text)}
</p>
"""


# -----------------------------------------------------------------------
#  BLOCK 9: FOOTER
# -----------------------------------------------------------------------

def _block_footer():
    """Branded footer with timestamp and disclaimer."""
    now = _now_il().strftime("%d/%m/%Y %H:%M:%S")
    return f"""
<table width="100%" cellpadding="0" cellspacing="0"
  style="background:#f4f5f7;border-top:2px solid {_RPA_BLUE};margin-top:20px;">
<tr>
  <td style="padding:16px 24px;">
    <table width="100%"><tr>
      <td valign="middle" style="font-size:12px;color:#666;">
        <strong style="color:{_RPA_BLUE};">R.P.A. PORT LTD</strong><br>
        <span style="font-size:11px;">RCB Customs Intelligence</span><br>
        <span style="font-size:10px;color:#999;">{now} IL</span>
      </td>
      <td align="left" valign="middle" style="font-size:10px;color:#999;line-height:1.5;">
        הודעה זו נוצרה אוטומטית על ידי מערכת RCB.<br>
        המידע מבוסס על מקורות משפטיים ורגולטוריים בלבד.<br>
        אין לראות בתשובה זו חוות דעת משפטית.
      </td>
    </tr></table>
  </td>
</tr>
</table>
"""


# -----------------------------------------------------------------------
#  BLOCK 10-12: TRACKING (for templates 3, 4)
# -----------------------------------------------------------------------

def _block_progress(tracking_data):
    """Progress bar for shipment tracking.

    Args:
        tracking_data: dict with steps (list), current_step, percentage
    """
    if not tracking_data:
        return ""

    pct = tracking_data.get("percentage", 0)
    current = _esc(tracking_data.get("current_step", ""))

    bar_color = _COLOR_OK if pct >= 80 else (_COLOR_WARN if pct >= 40 else _RPA_ACCENT)

    return f"""
<div class="section-title">מעקב משלוח</div>
<table width="100%" cellpadding="0" cellspacing="0" style="margin:10px 0;">
<tr><td style="padding:4px 0;">
  <div style="background:#e8e8e8;border-radius:6px;height:18px;width:100%;position:relative;">
    <div style="background:{bar_color};border-radius:6px;height:18px;width:{pct}%;
      text-align:center;font-size:10px;color:#fff;line-height:18px;font-weight:bold;">
      {pct}%</div>
  </div>
</td></tr>
<tr><td style="font-size:12px;color:#666;padding:4px 0;">
  שלב נוכחי: <strong>{current}</strong>
</td></tr>
</table>
"""


def _block_container_table(container_data):
    """Container details table for tracking.

    Args:
        container_data: list of dicts with container_number, type, status, location
    """
    if not container_data:
        return ""

    rows = []
    for c in container_data:
        rows.append(f"""<tr>
  <td style="font-family:'Courier New',monospace;font-weight:bold;">{_esc(c.get('container_number', ''))}</td>
  <td>{_esc(c.get('type', ''))}</td>
  <td>{_esc(c.get('status', ''))}</td>
  <td>{_esc(c.get('location', ''))}</td>
</tr>""")

    return f"""
<div class="section-title">מכולות</div>
<table class="tariff-table">
<thead><tr>
  <th>מספר מכולה</th>
  <th>סוג</th>
  <th>סטטוס</th>
  <th>מיקום</th>
</tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
"""


# -----------------------------------------------------------------------
#  HELPERS
# -----------------------------------------------------------------------

def _wrap_section(parts):
    """Wrap list of HTML fragments in a padded section."""
    return f'<div style="padding:0 24px;">{"".join(parts)}</div>'


def _html_open():
    """Outlook-safe HTML wrapper opening."""
    return """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body { margin:0; padding:20px; background:#f4f5f7;
    font-family: Arial, Helvetica, sans-serif; direction:rtl; }
  .email-container { max-width:700px; margin:0 auto; background:#ffffff; }
  .section-title { font-size:15px; font-weight:bold; color:#1e3a5f;
    border-bottom:2px solid #2471a3; padding-bottom:6px; margin:18px 0 10px 0; }
  .quote-block { background:#f0f7ff; border-right:4px solid #2471a3;
    padding:12px 16px; margin:10px 0; font-size:13px; line-height:1.8; color:#333; }
  .law-cite { background:#fffbee; border-right:4px solid #f39c12;
    padding:10px 14px; margin:10px 0; font-size:13px; line-height:1.7; color:#555; }
  .tariff-table { width:100%; border-collapse:collapse; margin:10px 0; font-size:12px; }
  .tariff-table th { background:#1e3a5f; color:#fff; padding:8px 10px;
    text-align:right; font-weight:bold; }
  .tariff-table td { padding:7px 10px; border-bottom:1px solid #e8e8e8; }
  .tariff-table tr:nth-child(even) { background:#f9fafb; }
  .tariff-table .hs-code { font-family:'Courier New',monospace; font-size:14px;
    font-weight:bold; color:#1e3a5f; direction:ltr; text-align:left; }
  .fio-table { width:100%; border-collapse:collapse; margin:10px 0; font-size:12px; }
  .fio-table th { background:#27ae60; color:#fff; padding:7px 10px; text-align:right; }
  .fio-table td { padding:6px 10px; border-bottom:1px solid #e8e8e8; }
  .fta-box { background:#eaf7ee; border:1px solid #27ae60; border-radius:4px;
    padding:14px; margin:10px 0; }
  .note-box { background:#fff8e1; border:1px solid #f39c12; border-radius:4px;
    padding:12px 14px; margin:10px 0; font-size:13px; }
  .question-list { margin:8px 0; padding:0 20px; }
  .question-list li { margin:4px 0; font-size:13px; color:#333; }
</style>
</head>
<body>
<div class="email-container">
"""


def _html_close():
    """HTML wrapper closing."""
    return """
</div>
</body>
</html>"""


# -----------------------------------------------------------------------
#  COMPLIANCE VERIFICATION GATE
# -----------------------------------------------------------------------

def verify_citations(ai_response, bundle):
    """Verify that AI citations match actual evidence bundle data.

    Returns:
        dict with {passed: bool, warnings: list, errors: list}
    """
    result = {"passed": True, "warnings": [], "errors": []}

    if not ai_response or not isinstance(ai_response, dict):
        result["passed"] = False
        result["errors"].append("no_ai_response")
        return result

    # Check HS candidates match tariff data
    candidates = ai_response.get("hs_candidates", [])
    tariff_codes = {e.get("hs_code", "")[:4] for e in (bundle.tariff_entries or [])}
    for c in candidates:
        code = c.get("code", "").replace(".", "")[:4]
        if code and tariff_codes and code not in tariff_codes:
            result["warnings"].append(
                f"HS candidate {c.get('code', '')} not in tariff search results"
            )

    # Check regulatory citations match
    reg_data = ai_response.get("regulatory", [])
    bundle_authorities = {r.get("authority", "") for r in (bundle.regulatory_requirements or [])}
    for r in reg_data:
        auth = r.get("authority", "")
        if auth and bundle_authorities and auth not in bundle_authorities:
            result["warnings"].append(
                f"Regulatory authority '{auth}' not in evidence bundle"
            )

    # Check FTA citation matches
    fta = ai_response.get("fta")
    if fta and fta.get("applicable"):
        if not bundle.fta_data or not bundle.fta_data.get("applicable"):
            result["errors"].append("AI claims FTA applicable but no FTA data in evidence")
            result["passed"] = False

    return result


# -----------------------------------------------------------------------
#  ORCHESTRATORS
# -----------------------------------------------------------------------

def compose_consultation(ai_response, bundle, recipient_name="", tracking_code=None):
    """Compose Template 1: Consultation reply.

    Args:
        ai_response: parsed JSON from AI (after straitjacket)
        bundle: EvidenceBundle
        recipient_name: name for greeting
        tracking_code: optional tracking code (generated if None)

    Returns:
        dict with {html: str, subject: str, tracking_code: str}
    """
    if not tracking_code:
        tracking_code = _generate_tracking_code()

    html_parts = [_html_open()]

    # B1: Header
    html_parts.append(_block_header(bundle.direction, "consultation", tracking_code))

    # Tracking bar
    html_parts.append(_block_tracking_bar(tracking_code))

    # B2: Greeting
    html_parts.append(_block_greeting(recipient_name))

    # Content section
    html_parts.append('<div style="padding:0 24px;">')

    # B3: Diagnosis
    html_parts.append(_block_diagnosis(ai_response.get("diagnosis")))

    # B4: Tariff table
    html_parts.append(_block_tariff_table(ai_response.get("hs_candidates")))

    # B5: FIO/FEO
    html_parts.append(_block_fio_feo(ai_response.get("regulatory"), bundle.direction))

    # B6: FTA
    html_parts.append(_block_fta(ai_response.get("fta"), bundle.direction))

    # B7: Valuation (import only)
    html_parts.append(_block_valuation(ai_response.get("valuation_notes")))

    # B8: Release notes
    html_parts.append(_block_release_notes(ai_response.get("release_notes")))

    # Web answer (general queries)
    html_parts.append(_block_web_answer(ai_response.get("web_answer")))

    # Clarification questions
    html_parts.append(_block_clarifications(ai_response.get("clarification_questions")))

    # English summary
    html_parts.append(_block_english_summary(ai_response.get("english_summary")))

    html_parts.append('</div>')

    # B9: Footer
    html_parts.append(_block_footer())

    html_parts.append(_html_close())

    # Subject
    domain_label = {
        "customs": "מכס", "tariff": "תעריף", "regulatory": "רגולציה",
        "fta": "הסכם סחר", "general": "שאלה כללית",
    }.get(bundle.domain, "מכס")
    topic = (bundle.original_subject or bundle.original_body or "")[:50].strip()
    if len(bundle.original_subject or "") > 50:
        topic += "..."
    subject = f"RCB | {tracking_code} | {domain_label} | {topic}"

    return {
        "html": "".join(html_parts),
        "subject": subject,
        "tracking_code": tracking_code,
    }


def compose_live_shipment(ai_response, bundle, invoice_data=None,
                          recipient_name="", tracking_code=None):
    """Compose Template 2: Live shipment classification reply.

    Args:
        ai_response: parsed JSON from AI
        bundle: EvidenceBundle
        invoice_data: optional dict with invoice metadata
        recipient_name: name for greeting
        tracking_code: optional tracking code

    Returns:
        dict with {html: str, subject: str, tracking_code: str}
    """
    if not tracking_code:
        tracking_code = _generate_tracking_code()

    html_parts = [_html_open()]

    # Header
    html_parts.append(_block_header(bundle.direction, "live_shipment", tracking_code))
    html_parts.append(_block_tracking_bar(tracking_code))
    html_parts.append(_block_greeting(recipient_name))

    html_parts.append('<div style="padding:0 24px;">')

    # Diagnosis
    html_parts.append(_block_diagnosis(ai_response.get("diagnosis")))

    # Tariff table
    html_parts.append(_block_tariff_table(ai_response.get("hs_candidates")))

    # FIO/FEO
    html_parts.append(_block_fio_feo(ai_response.get("regulatory"), bundle.direction))

    # FTA
    html_parts.append(_block_fta(ai_response.get("fta"), bundle.direction))

    # Valuation
    html_parts.append(_block_valuation(ai_response.get("valuation_notes")))

    # Release
    html_parts.append(_block_release_notes(ai_response.get("release_notes")))

    # Clarifications
    html_parts.append(_block_clarifications(ai_response.get("clarification_questions")))

    # English summary
    html_parts.append(_block_english_summary(ai_response.get("english_summary")))

    html_parts.append('</div>')
    html_parts.append(_block_footer())
    html_parts.append(_html_close())

    topic = (bundle.original_subject or "משלוח")[:40]
    subject = f"RCB | {tracking_code} | סיווג משלוח | {topic}"

    return {
        "html": "".join(html_parts),
        "subject": subject,
        "tracking_code": tracking_code,
    }


def compose_tracking(tracking_data, container_data=None,
                     direction="import", tracking_code=None):
    """Compose Template 3: Tracking update.

    Args:
        tracking_data: dict with steps, current_step, percentage
        container_data: list of container dicts
        direction: import/export
        tracking_code: optional

    Returns:
        dict with {html: str, subject: str, tracking_code: str}
    """
    if not tracking_code:
        tracking_code = _generate_tracking_code()

    html_parts = [_html_open()]
    html_parts.append(_block_header(direction, "tracking", tracking_code))
    html_parts.append(_block_tracking_bar(tracking_code))

    html_parts.append('<div style="padding:0 24px;">')
    html_parts.append(_block_progress(tracking_data))
    html_parts.append(_block_container_table(container_data))
    html_parts.append('</div>')

    html_parts.append(_block_footer())
    html_parts.append(_html_close())

    current = (tracking_data or {}).get("current_step", "")
    subject = f"RCB | {tracking_code} | מעקב | {current}"

    return {
        "html": "".join(html_parts),
        "subject": subject,
        "tracking_code": tracking_code,
    }


def compose_combined(ai_response, bundle, tracking_data=None,
                     container_data=None, recipient_name="", tracking_code=None):
    """Compose Template 4: Combined classification + tracking.

    Args:
        ai_response: parsed JSON from AI
        bundle: EvidenceBundle
        tracking_data: dict with progress info
        container_data: list of container dicts
        recipient_name: name for greeting
        tracking_code: optional

    Returns:
        dict with {html: str, subject: str, tracking_code: str}
    """
    if not tracking_code:
        tracking_code = _generate_tracking_code()

    html_parts = [_html_open()]

    # Header
    html_parts.append(_block_header(bundle.direction, "combined", tracking_code))
    html_parts.append(_block_tracking_bar(tracking_code))
    html_parts.append(_block_greeting(recipient_name))

    html_parts.append('<div style="padding:0 24px;">')

    # Classification section
    html_parts.append(_block_diagnosis(ai_response.get("diagnosis")))
    html_parts.append(_block_tariff_table(ai_response.get("hs_candidates")))
    html_parts.append(_block_fio_feo(ai_response.get("regulatory"), bundle.direction))
    html_parts.append(_block_fta(ai_response.get("fta"), bundle.direction))
    html_parts.append(_block_valuation(ai_response.get("valuation_notes")))
    html_parts.append(_block_release_notes(ai_response.get("release_notes")))

    # Divider
    html_parts.append(f'<hr style="border:none;border-top:2px solid {_RPA_BLUE};margin:20px 0;">')

    # Tracking section
    html_parts.append(_block_progress(tracking_data))
    html_parts.append(_block_container_table(container_data))

    # Clarifications + English
    html_parts.append(_block_clarifications(ai_response.get("clarification_questions")))
    html_parts.append(_block_english_summary(ai_response.get("english_summary")))

    html_parts.append('</div>')
    html_parts.append(_block_footer())
    html_parts.append(_html_close())

    topic = (bundle.original_subject or "משלוח")[:40]
    subject = f"RCB | {tracking_code} | סיווג + מעקב | {topic}"

    return {
        "html": "".join(html_parts),
        "subject": subject,
        "tracking_code": tracking_code,
    }
