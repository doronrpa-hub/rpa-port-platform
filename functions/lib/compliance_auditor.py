"""Compliance Auditor -- enriches classification outputs with official document citations.

Intercepts classification results and adds Outlook-safe HTML snippets with
citations from the Customs Ordinance, Framework Order, FTA agreements,
procedures, discount codes, and chapter notes.

DESIGN:
  - Additive only: never blocks the pipeline
  - Fail-open: every public function wrapped in try/except returning defaults
  - HTML goes INTO emails, not saved as standalone files
  - All HTML is Outlook-safe: table-based layout, inline CSS, no flexbox/grid/border-radius

Usage:
    from lib.compliance_auditor import (
        audit_classification,
        build_compliance_context,
        render_tariff_snippet_html,
        render_fta_requirements_html,
        render_ordinance_article_html,
        render_procedure_snippet_html,
        render_framework_order_article_html,
        render_discount_code_html,
        render_citation_badges_html,
        render_compliance_section_html,
        render_fta_comparison_html,
        build_attachment_html,
        AuditResult,
        Citation,
        ComparisonResult,
    )
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import os
import re
import traceback


# ============================================================================
# STYLE CONSTANTS  (match RPA-PORT branding from tracker_email / classification_agents)
# ============================================================================

_RPA_BLUE = "#1a5fb4"
_COLOR_OK = "#28a745"
_COLOR_WARN = "#ffc107"
_COLOR_ERR = "#dc3545"
_CITE_BG = "#f0f4ff"
_CITE_BORDER = "#4a90d9"
_TABLE_HEADER = "#003366"
_TABLE_ALT = "#f8f9fa"
_FONT = "Arial, Tahoma, sans-serif"

# Inline style fragments reused across renderers
_S_FONT = f"font-family:{_FONT};"
_S_CITE_BLOCK = (
    f"border-left:4px solid {_CITE_BORDER};"
    f"background:{_CITE_BG};"
    "padding:10px 14px;"
    "margin:6px 0;"
)
_S_TD_BASE = f"{_S_FONT}font-size:13px;padding:6px 10px;"
_S_HEADER_TD = (
    f"background:{_TABLE_HEADER};color:#fff;{_S_FONT}"
    "font-size:12px;font-weight:bold;padding:8px 10px;"
    "text-align:right;"
)
_S_BADGE_BASE = (
    "display:inline-block;padding:2px 10px;"
    f"{_S_FONT}font-size:11px;font-weight:bold;color:#fff;"
)

_SNIPPET_MAX = 500
_INLINE_THRESHOLD = 5 * 1024  # 5 KB


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Citation:
    """A single document citation for embedding in an email."""
    doc_id: str = ""
    article: str = ""
    title: str = ""
    text_snippet: str = ""
    relevance: str = "informational"  # "supporting", "conflicting", "informational"


@dataclass
class AuditResult:
    """Result of a compliance audit on classification output."""
    citations: List[Citation] = field(default_factory=list)
    flags: List[dict] = field(default_factory=list)
    inline_html: str = ""
    attachments: List[Tuple[str, bytes]] = field(default_factory=list)


@dataclass
class ComparisonResult:
    """Result of comparing live document fields vs official template."""
    matches: List[str] = field(default_factory=list)
    mismatches: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    score: float = 0.0
    html: str = ""


# ============================================================================
# PRIVATE HELPERS
# ============================================================================

def _esc(text: str) -> str:
    """HTML-escape a string. Handles None gracefully."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _trim(text: str, max_len: int = _SNIPPET_MAX) -> str:
    """Trim text to max_len, add ellipsis if truncated."""
    if not text:
        return ""
    t = str(text).strip()
    if len(t) <= max_len:
        return t
    return t[:max_len - 3] + "..."


def _hs_format(hs_code: str) -> str:
    """Format HS code as XX.XX.XXXXXX/X using librarian helper if available."""
    try:
        from lib.librarian import get_israeli_hs_format
        return get_israeli_hs_format(hs_code)
    except Exception:
        # Fallback: raw code
        digits = "".join(c for c in (hs_code or "") if c.isdigit())
        if len(digits) >= 10:
            return f"{digits[:2]}.{digits[2:4]}.{digits[4:10]}"
        return hs_code or ""


def _get_ordinance_article(article_num: str) -> Optional[dict]:
    """Lazy-load ordinance article from customs_law."""
    try:
        from lib.customs_law import CUSTOMS_ORDINANCE_ARTICLES
        art = CUSTOMS_ORDINANCE_ARTICLES.get(str(article_num))
        return art
    except Exception:
        return None


def _get_framework_article(article_num: str) -> Optional[dict]:
    """Lazy-load framework order article."""
    try:
        from lib._framework_order_data import FRAMEWORK_ORDER_ARTICLES
        art = FRAMEWORK_ORDER_ARTICLES.get(str(article_num))
        return art
    except Exception:
        return None


def _get_discount(item_number: str) -> Optional[dict]:
    """Lazy-load discount code."""
    try:
        from lib._discount_codes_data import get_discount_code
        return get_discount_code(str(item_number))
    except Exception:
        return None


def _get_fta_doc(country_code: str) -> Optional[dict]:
    """Lazy-load FTA document from registry."""
    try:
        from lib._document_registry import get_fta_for_country
        return get_fta_for_country(country_code)
    except Exception:
        return None


def _get_relevant_docs(hs_code=None, origin=None, direction=None):
    """Lazy-load relevant documents from registry."""
    try:
        from lib._document_registry import get_relevant_documents
        return get_relevant_documents(hs_code=hs_code, origin=origin, direction=direction)
    except Exception:
        return []


def _format_citation_str(doc_id, article=None, section=None):
    """Lazy-load format_citation from registry."""
    try:
        from lib._document_registry import format_citation
        return format_citation(doc_id, article=article, section=section)
    except Exception:
        return doc_id or ""


def _relevance_color(relevance: str) -> str:
    """Return color for citation relevance badge."""
    if relevance == "supporting":
        return _COLOR_OK
    elif relevance == "conflicting":
        return _COLOR_ERR
    return _CITE_BORDER  # informational


def _relevance_label(relevance: str) -> str:
    """Hebrew label for relevance."""
    if relevance == "supporting":
        return "תומך"
    elif relevance == "conflicting":
        return "סותר"
    return "מידע"


def _outer_table(inner_html: str) -> str:
    """Wrap content in a single-cell table for Outlook compatibility."""
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"'
        f' style="border-collapse:collapse;{_S_FONT}">'
        "<tr><td>"
        f"{inner_html}"
        "</td></tr></table>"
    )


# ============================================================================
# RENDER FUNCTIONS  (all return Outlook-safe HTML strings)
# ============================================================================


def render_tariff_snippet_html(
    hs_code: str,
    description_he: str = "",
    description_en: str = "",
    duty_rate: str = "",
) -> str:
    """Render an official tariff heading as a compact citation block.

    Returns Outlook-safe HTML with HS code in XX.XX.XXXXXX/X format,
    Hebrew + English description, and duty rate. Blue left border, light bg.
    """
    try:
        formatted_hs = _hs_format(hs_code)
        rows = []

        # HS code row
        rows.append(
            f'<tr><td style="{_S_TD_BASE}font-weight:bold;color:{_RPA_BLUE};'
            f'font-family:Courier New,monospace;font-size:16px;padding:8px 10px;"'
            f' dir="ltr">{_esc(formatted_hs)}</td></tr>'
        )

        # Hebrew description
        if description_he:
            rows.append(
                f'<tr><td style="{_S_TD_BASE}text-align:right;" dir="rtl">'
                f'{_esc(_trim(description_he))}</td></tr>'
            )

        # English description
        if description_en:
            rows.append(
                f'<tr><td style="{_S_TD_BASE}color:#555;" dir="ltr">'
                f'{_esc(_trim(description_en))}</td></tr>'
            )

        # Duty rate
        if duty_rate:
            rows.append(
                f'<tr><td style="{_S_TD_BASE}font-weight:bold;">'
                f'שיעור מכס: {_esc(duty_rate)}</td></tr>'
            )

        inner = (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-collapse:collapse;{_S_CITE_BLOCK}">'
            + "\n".join(rows)
            + "</table>"
        )
        return inner
    except Exception:
        traceback.print_exc()
        return ""


def render_fta_requirements_html(
    country_code: str,
    origin_proof_type: str = "",
    preferential_rate: str = "",
) -> str:
    """Render FTA origin proof requirements as a 2-column table.

    Shows country name, proof type (EUR.1 / Certificate of Origin / Invoice
    Declaration), and preferential rate if known.
    """
    try:
        fta_doc = _get_fta_doc(country_code)
        title = ""
        if fta_doc:
            title = fta_doc.get("title_he", "")
            if not origin_proof_type:
                origin_proof_type = fta_doc.get("origin_proof_type", "")

        country_display = _esc(title or country_code or "")

        def _row(label: str, value: str) -> str:
            if not value:
                return ""
            return (
                f'<tr><td style="{_S_TD_BASE}font-weight:bold;text-align:right;'
                f'width:40%;background:{_TABLE_ALT};" dir="rtl">{_esc(label)}</td>'
                f'<td style="{_S_TD_BASE}text-align:right;" dir="rtl">'
                f'{_esc(value)}</td></tr>'
            )

        rows = [
            _row("הסכם סחר", country_display),
            _row("סוג הוכחת מקור", origin_proof_type),
        ]
        if preferential_rate:
            rows.append(_row("שיעור העדפה", preferential_rate))

        # Status badge
        status = fta_doc.get("status", "pending") if fta_doc else "pending"
        status_color = _COLOR_OK if status == "complete" else _COLOR_WARN
        status_label = "נתונים מלאים" if status == "complete" else "נתונים חלקיים"
        rows.append(
            f'<tr><td style="{_S_TD_BASE}text-align:right;" dir="rtl" colspan="2">'
            f'<span style="{_S_BADGE_BASE}background:{status_color};">'
            f'{status_label}</span></td></tr>'
        )

        inner = (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-collapse:collapse;{_S_CITE_BLOCK}">'
            + "\n".join(r for r in rows if r)
            + "</table>"
        )
        return inner
    except Exception:
        traceback.print_exc()
        return ""


def render_ordinance_article_html(
    article_num: str,
    title_he: str = "",
    summary: str = "",
    text_snippet: str = "",
) -> str:
    """Render a Customs Ordinance article as a formatted citation block.

    Uses data from customs_law.py ORDINANCE_ARTICLES if title_he/summary
    are not provided.
    """
    try:
        # Try to fill from in-memory data if not provided
        art_data = _get_ordinance_article(article_num)
        if art_data:
            if not title_he:
                title_he = art_data.get("t", "")
            if not summary:
                summary = art_data.get("s", "")
            if not text_snippet:
                text_snippet = _trim(art_data.get("f", ""), _SNIPPET_MAX)

        # Article number badge
        badge = (
            f'<span style="{_S_BADGE_BASE}background:{_RPA_BLUE};'
            f'font-size:13px;">&#167;{_esc(str(article_num))}</span>'
        )

        parts = [
            f'<tr><td style="{_S_TD_BASE}padding:8px 10px;">{badge}'
        ]
        if title_he:
            parts[0] += (
                f'&nbsp;&nbsp;<span style="font-weight:bold;font-size:14px;">'
                f'{_esc(title_he)}</span>'
            )
        parts[0] += "</td></tr>"

        if summary:
            parts.append(
                f'<tr><td style="{_S_TD_BASE}color:#555;" dir="ltr">'
                f'{_esc(_trim(summary))}</td></tr>'
            )

        if text_snippet:
            parts.append(
                f'<tr><td style="{_S_TD_BASE}text-align:right;" dir="rtl">'
                f'{_esc(_trim(text_snippet))}</td></tr>'
            )

        citation_ref = _format_citation_str("customs_ordinance", article=str(article_num))
        parts.append(
            f'<tr><td style="{_S_TD_BASE}color:#888;font-size:11px;" dir="rtl">'
            f'מקור: {_esc(citation_ref)}</td></tr>'
        )

        inner = (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-collapse:collapse;{_S_CITE_BLOCK}">'
            + "\n".join(parts)
            + "</table>"
        )
        return inner
    except Exception:
        traceback.print_exc()
        return ""


def render_procedure_snippet_html(
    procedure_num: str,
    section_title: str = "",
    text: str = "",
) -> str:
    """Render a customs procedure section reference as a citation block."""
    try:
        proc_data = None
        try:
            from lib._procedures_data import get_procedure
            proc_data = get_procedure(procedure_num)
        except Exception:
            pass

        proc_name = ""
        if proc_data:
            proc_name = proc_data.get("name_he", "")

        badge = (
            f'<span style="{_S_BADGE_BASE}background:{_TABLE_HEADER};">'
            f'נוהל {_esc(str(procedure_num))}</span>'
        )

        parts = [
            f'<tr><td style="{_S_TD_BASE}padding:8px 10px;">{badge}'
        ]
        if proc_name:
            parts[0] += (
                f'&nbsp;&nbsp;<span style="font-weight:bold;">'
                f'{_esc(proc_name)}</span>'
            )
        parts[0] += "</td></tr>"

        if section_title:
            parts.append(
                f'<tr><td style="{_S_TD_BASE}font-weight:bold;text-align:right;"'
                f' dir="rtl">{_esc(section_title)}</td></tr>'
            )

        if text:
            parts.append(
                f'<tr><td style="{_S_TD_BASE}text-align:right;" dir="rtl">'
                f'{_esc(_trim(text))}</td></tr>'
            )

        inner = (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-collapse:collapse;{_S_CITE_BLOCK}">'
            + "\n".join(parts)
            + "</table>"
        )
        return inner
    except Exception:
        traceback.print_exc()
        return ""


def render_framework_order_article_html(
    article_num: str,
    title_he: str = "",
    text: str = "",
) -> str:
    """Render a Framework Order article reference as a citation block."""
    try:
        art_data = _get_framework_article(article_num)
        if art_data:
            if not title_he:
                title_he = art_data.get("t", "")
            if not text:
                text = _trim(art_data.get("f", ""), _SNIPPET_MAX)

        badge = (
            f'<span style="{_S_BADGE_BASE}background:{_RPA_BLUE};">'
            f'צו מסגרת &#167;{_esc(str(article_num))}</span>'
        )

        parts = [
            f'<tr><td style="{_S_TD_BASE}padding:8px 10px;">{badge}'
        ]
        if title_he:
            parts[0] += (
                f'&nbsp;&nbsp;<span style="font-weight:bold;">'
                f'{_esc(title_he)}</span>'
            )
        parts[0] += "</td></tr>"

        if text:
            parts.append(
                f'<tr><td style="{_S_TD_BASE}text-align:right;" dir="rtl">'
                f'{_esc(_trim(text))}</td></tr>'
            )

        citation_ref = _format_citation_str("framework_order", article=str(article_num))
        parts.append(
            f'<tr><td style="{_S_TD_BASE}color:#888;font-size:11px;" dir="rtl">'
            f'מקור: {_esc(citation_ref)}</td></tr>'
        )

        inner = (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-collapse:collapse;{_S_CITE_BLOCK}">'
            + "\n".join(parts)
            + "</table>"
        )
        return inner
    except Exception:
        traceback.print_exc()
        return ""


def render_discount_code_html(
    item_number: str,
    description: str = "",
    sub_codes: Optional[Dict[str, dict]] = None,
) -> str:
    """Render a discount/exemption code as a table with rate info."""
    try:
        dc_data = _get_discount(item_number)
        if dc_data:
            if not description:
                description = dc_data.get("description_he", "")
            if sub_codes is None:
                sub_codes = dc_data.get("sub_codes", {})

        badge = (
            f'<span style="{_S_BADGE_BASE}background:{_COLOR_OK};">'
            f'קוד הנחה {_esc(str(item_number))}</span>'
        )

        parts = [
            f'<tr><td style="{_S_TD_BASE}padding:8px 10px;" colspan="3">{badge}'
        ]
        if description:
            parts[0] += (
                f'&nbsp;&nbsp;<span style="font-size:12px;">'
                f'{_esc(_trim(description, 200))}</span>'
            )
        parts[0] += "</td></tr>"

        # Sub-codes table
        if sub_codes:
            parts.append(
                f'<tr>'
                f'<td style="{_S_HEADER_TD}">קוד</td>'
                f'<td style="{_S_HEADER_TD}">מכס</td>'
                f'<td style="{_S_HEADER_TD}">מס קניה</td>'
                f'</tr>'
            )
            for i, (sc_key, sc_val) in enumerate(list(sub_codes.items())[:10]):
                bg = _TABLE_ALT if i % 2 == 1 else "#fff"
                customs_duty = sc_val.get("customs_duty", "") if isinstance(sc_val, dict) else ""
                purchase_tax = sc_val.get("purchase_tax", "") if isinstance(sc_val, dict) else ""
                sc_desc = sc_val.get("description_he", "") if isinstance(sc_val, dict) else ""
                display_key = _esc(sc_key)
                if sc_desc:
                    display_key += f'<br><span style="font-size:11px;color:#666;">{_esc(_trim(sc_desc, 80))}</span>'
                parts.append(
                    f'<tr style="background:{bg};">'
                    f'<td style="{_S_TD_BASE}text-align:right;" dir="rtl">{display_key}</td>'
                    f'<td style="{_S_TD_BASE}text-align:center;">{_esc(customs_duty or "-")}</td>'
                    f'<td style="{_S_TD_BASE}text-align:center;">{_esc(purchase_tax or "-")}</td>'
                    f'</tr>'
                )

        inner = (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-collapse:collapse;{_S_CITE_BLOCK}">'
            + "\n".join(parts)
            + "</table>"
        )
        return inner
    except Exception:
        traceback.print_exc()
        return ""


def render_citation_badges_html(citations: List[Citation]) -> str:
    """Render a row of citation source badges as colored pills.

    Each badge shows an icon + source reference (e.g., "פקודת המכס section 130").
    """
    try:
        if not citations:
            return ""

        badges = []
        for cit in citations:
            color = _relevance_color(cit.relevance)
            icon = "&#128214;"  # open book emoji code point
            if "fta" in (cit.doc_id or "").lower():
                icon = "&#127758;"  # globe emoji
            elif "procedure" in (cit.doc_id or "").lower():
                icon = "&#128221;"  # memo/clipboard
            elif "framework" in (cit.doc_id or "").lower():
                icon = "&#9878;"  # staff of aesculapius (legal)
            elif "discount" in (cit.doc_id or "").lower():
                icon = "&#128176;"  # money bag

            label = cit.title
            if not label:
                label = _format_citation_str(cit.doc_id, article=cit.article)
            if cit.article and cit.article not in label:
                label += f" &#167;{_esc(cit.article)}"

            badges.append(
                f'<span style="{_S_BADGE_BASE}background:{color};'
                f'margin:2px 4px;">'
                f'{icon} {_esc(_trim(label, 60))}</span>'
            )

        return (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-collapse:collapse;margin:6px 0;">'
            f'<tr><td style="{_S_TD_BASE}text-align:right;" dir="rtl">'
            + " ".join(badges)
            + "</td></tr></table>"
        )
    except Exception:
        traceback.print_exc()
        return ""


def render_compliance_section_html(audit_result: AuditResult) -> str:
    """Full compliance block for email embedding.

    Combines citation badges, individual citation blocks, and flags
    into a single Outlook-safe HTML section.
    """
    try:
        if not audit_result or (
            not audit_result.citations and not audit_result.flags
        ):
            return ""

        parts = []

        # Section title
        parts.append(
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-collapse:collapse;margin-top:12px;">'
            f'<tr><td style="{_S_FONT}font-size:15px;font-weight:bold;'
            f'color:{_RPA_BLUE};padding:8px 10px;text-align:right;'
            f'border-bottom:2px solid {_RPA_BLUE};" dir="rtl">'
            f'אסמכתאות חוקיות</td></tr></table>'
        )

        # Citation badges row
        if audit_result.citations:
            badges_html = render_citation_badges_html(audit_result.citations)
            if badges_html:
                parts.append(badges_html)

        # Individual citation blocks (max 8 to keep email reasonable)
        for cit in audit_result.citations[:8]:
            cit_html = ""
            doc_id = cit.doc_id or ""
            if doc_id == "customs_ordinance":
                cit_html = render_ordinance_article_html(
                    cit.article, title_he=cit.title, text_snippet=cit.text_snippet
                )
            elif doc_id == "framework_order":
                cit_html = render_framework_order_article_html(
                    cit.article, title_he=cit.title, text=cit.text_snippet
                )
            elif doc_id.startswith("procedure_"):
                proc_num = doc_id.replace("procedure_", "")
                cit_html = render_procedure_snippet_html(
                    proc_num, section_title=cit.title, text=cit.text_snippet
                )
            elif doc_id.startswith("fta_"):
                country = ""
                try:
                    from lib._document_registry import get_document
                    fta_entry = get_document(doc_id)
                    if fta_entry:
                        country = fta_entry.get("country_code", "")
                except Exception:
                    pass
                if country:
                    cit_html = render_fta_requirements_html(country)
            elif doc_id == "discount_codes" and cit.article:
                cit_html = render_discount_code_html(cit.article)
            else:
                # Generic citation block
                cit_html = _render_generic_citation(cit)

            if cit_html:
                parts.append(cit_html)

        # Flags section
        if audit_result.flags:
            parts.append(_render_flags_html(audit_result.flags))

        # Source attribution footer
        parts.append(
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-collapse:collapse;margin-top:6px;">'
            f'<tr><td style="{_S_FONT}font-size:10px;color:#999;'
            f'padding:4px 10px;text-align:right;" dir="rtl">'
            f'האסמכתאות נמשכו אוטומטית ממאגר המסמכים הפנימי של RCB'
            f'</td></tr></table>'
        )

        return "\n".join(parts)
    except Exception:
        traceback.print_exc()
        return ""


def _render_generic_citation(cit: Citation) -> str:
    """Render a generic citation when doc_id is not a known special type."""
    try:
        color = _relevance_color(cit.relevance)
        rel_label = _relevance_label(cit.relevance)

        parts = []
        # Title row with relevance badge
        title_text = cit.title or _format_citation_str(cit.doc_id, article=cit.article)
        parts.append(
            f'<tr><td style="{_S_TD_BASE}padding:8px 10px;">'
            f'<span style="{_S_BADGE_BASE}background:{color};">'
            f'{_esc(rel_label)}</span>'
            f'&nbsp;&nbsp;<span style="font-weight:bold;">'
            f'{_esc(title_text)}</span></td></tr>'
        )

        if cit.text_snippet:
            parts.append(
                f'<tr><td style="{_S_TD_BASE}text-align:right;" dir="rtl">'
                f'{_esc(_trim(cit.text_snippet))}</td></tr>'
            )

        return (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-collapse:collapse;{_S_CITE_BLOCK}">'
            + "\n".join(parts)
            + "</table>"
        )
    except Exception:
        return ""


def _render_flags_html(flags: List[dict]) -> str:
    """Render compliance flags as colored badges with descriptions."""
    try:
        if not flags:
            return ""

        severity_colors = {
            "critical": _COLOR_ERR,
            "warning": _COLOR_WARN,
            "info": _CITE_BORDER,
        }

        rows = []
        for fl in flags[:10]:
            severity = fl.get("severity", "info")
            color = severity_colors.get(severity, _CITE_BORDER)
            flag_type = fl.get("type", "")
            message = fl.get("message", "")

            rows.append(
                f'<tr>'
                f'<td style="{_S_TD_BASE}width:30%;text-align:right;" dir="rtl">'
                f'<span style="{_S_BADGE_BASE}background:{color};">'
                f'{_esc(flag_type)}</span></td>'
                f'<td style="{_S_TD_BASE}text-align:right;" dir="rtl">'
                f'{_esc(message)}</td>'
                f'</tr>'
            )

        return (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-collapse:collapse;margin-top:8px;">'
            f'<tr><td colspan="2" style="{_S_FONT}font-size:13px;font-weight:bold;'
            f'color:{_TABLE_HEADER};padding:6px 10px;text-align:right;" dir="rtl">'
            f'דגלים</td></tr>'
            + "\n".join(rows)
            + "</table>"
        )
    except Exception:
        return ""


def render_fta_comparison_html(
    live_fields: Dict[str, str],
    template_fields: Dict[str, str],
    country_code: str,
) -> str:
    """Side-by-side comparison table: Live Document vs Official Template.

    Green for matches, red for mismatches, yellow for missing.
    """
    try:
        if not live_fields and not template_fields:
            return ""

        fta_doc = _get_fta_doc(country_code)
        fta_title = fta_doc.get("title_he", country_code) if fta_doc else country_code

        # Collect all field names
        all_fields = set(list(live_fields.keys()) + list(template_fields.keys()))
        if not all_fields:
            return ""

        matches = []
        mismatches = []
        missing = []

        rows = []
        rows.append(
            f'<tr>'
            f'<td style="{_S_HEADER_TD}width:30%;">שדה</td>'
            f'<td style="{_S_HEADER_TD}width:35%;">מסמך חי</td>'
            f'<td style="{_S_HEADER_TD}width:35%;">תבנית רשמית</td>'
            f'</tr>'
        )

        for i, field_name in enumerate(sorted(all_fields)):
            live_val = live_fields.get(field_name, "")
            tmpl_val = template_fields.get(field_name, "")
            bg = _TABLE_ALT if i % 2 == 1 else "#fff"

            if not live_val and tmpl_val:
                status_color = _COLOR_WARN
                missing.append(field_name)
            elif live_val and tmpl_val and live_val.strip().lower() == tmpl_val.strip().lower():
                status_color = _COLOR_OK
                matches.append(field_name)
            elif live_val and tmpl_val:
                status_color = _COLOR_ERR
                mismatches.append(field_name)
            else:
                status_color = bg
                if live_val:
                    matches.append(field_name)

            rows.append(
                f'<tr style="background:{bg};">'
                f'<td style="{_S_TD_BASE}font-weight:bold;text-align:right;'
                f'border-left:3px solid {status_color};" dir="rtl">'
                f'{_esc(field_name)}</td>'
                f'<td style="{_S_TD_BASE}text-align:right;" dir="rtl">'
                f'{_esc(live_val or "-")}</td>'
                f'<td style="{_S_TD_BASE}text-align:right;" dir="rtl">'
                f'{_esc(tmpl_val or "-")}</td>'
                f'</tr>'
            )

        total = len(all_fields)
        score = len(matches) / total if total > 0 else 0.0
        score_color = _COLOR_OK if score >= 0.8 else (_COLOR_WARN if score >= 0.5 else _COLOR_ERR)

        # Score row
        rows.append(
            f'<tr>'
            f'<td colspan="3" style="{_S_TD_BASE}text-align:right;padding:8px 10px;"'
            f' dir="rtl">'
            f'<span style="font-weight:bold;">ציון התאמה: </span>'
            f'<span style="font-weight:bold;color:{score_color};">'
            f'{score:.0%}</span>'
            f' ({len(matches)} תואם, {len(mismatches)} לא תואם, {len(missing)} חסר)'
            f'</td></tr>'
        )

        header = (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-collapse:collapse;margin-bottom:4px;">'
            f'<tr><td style="{_S_FONT}font-size:14px;font-weight:bold;'
            f'color:{_RPA_BLUE};padding:8px 10px;text-align:right;" dir="rtl">'
            f'השוואת מסמך מול תבנית: {_esc(fta_title)}</td></tr></table>'
        )

        table = (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0"'
            f' style="border-collapse:collapse;border:1px solid #ddd;">'
            + "\n".join(rows)
            + "</table>"
        )

        return header + table
    except Exception:
        traceback.print_exc()
        return ""


# ============================================================================
# AUDIT FUNCTIONS
# ============================================================================

def audit_classification(
    results: Any = None,
    invoice_data: Optional[dict] = None,
    origin: Optional[str] = None,
    hs_codes: Optional[List[str]] = None,
) -> AuditResult:
    """Main entry point: audit classification results and produce citations.

    Searches ordinance articles, framework order, discount codes, FTA
    requirements, procedures, and chapter notes for relevant citations.

    Args:
        results: Classification results dict (from run_full_classification)
        invoice_data: Invoice extraction data (from extract_invoice)
        origin: Country of origin code (e.g., "DE", "CN")
        hs_codes: List of HS code strings from classification

    Returns:
        AuditResult with citations, flags, inline_html, and attachments.
        On any error, returns an empty AuditResult.
    """
    try:
        audit = AuditResult()

        # Normalize inputs
        if hs_codes is None:
            hs_codes = []
        if results and isinstance(results, dict):
            # Extract HS codes from results if not provided
            if not hs_codes:
                for item in results.get("classifications", results.get("items", [])):
                    hs = item.get("hs_code", "")
                    if hs:
                        hs_codes.append(hs)
        if invoice_data and isinstance(invoice_data, dict):
            if not origin:
                origin = invoice_data.get("origin", invoice_data.get("country", ""))

        # Determine direction
        direction = None
        if invoice_data:
            direction = invoice_data.get("direction", None)
        if not direction and results and isinstance(results, dict):
            direction = results.get("direction", None)

        # --- Gather citations ---

        # 1. Ordinance valuation articles (always relevant for import)
        if direction != "export":
            audit.citations.extend(_find_valuation_citations())

        # 2. Classification procedure
        audit.citations.extend(_find_classification_procedure_citations())

        # 3. Per-HS-code citations
        for hs in hs_codes:
            audit.citations.extend(_find_hs_citations(hs, origin))

        # 4. FTA citations
        if origin:
            audit.citations.extend(_find_fta_citations(origin))

        # 5. Framework order classification rules
        audit.citations.extend(_find_framework_order_citations())

        # --- Deduplicate ---
        seen = set()
        unique_citations = []
        for cit in audit.citations:
            key = (cit.doc_id, cit.article)
            if key not in seen:
                seen.add(key)
                unique_citations.append(cit)
        audit.citations = unique_citations

        # --- Generate flags ---
        audit.flags = _generate_flags(hs_codes, origin, invoice_data, results)

        # --- Build inline HTML ---
        audit.inline_html = render_compliance_section_html(audit)

        # --- Check for large attachments ---
        for cit in audit.citations:
            att = build_attachment_html(cit.doc_id, section=cit.article)
            if att is not None:
                audit.attachments.append(att)

        return audit
    except Exception:
        traceback.print_exc()
        return AuditResult()


def _find_valuation_citations() -> List[Citation]:
    """Find valuation-related ordinance articles."""
    citations = []
    try:
        # Article 130: Transaction value definition
        art130 = _get_ordinance_article("130")
        if art130:
            citations.append(Citation(
                doc_id="customs_ordinance",
                article="130",
                title=art130.get("t", ""),
                text_snippet=_trim(art130.get("f", ""), _SNIPPET_MAX),
                relevance="supporting",
            ))

        # Article 132: Transaction value determination
        art132 = _get_ordinance_article("132")
        if art132:
            citations.append(Citation(
                doc_id="customs_ordinance",
                article="132",
                title=art132.get("t", ""),
                text_snippet=_trim(art132.get("s", ""), 200),
                relevance="informational",
            ))

        # Article 133: Alternative valuation methods
        art133 = _get_ordinance_article("133")
        if art133:
            citations.append(Citation(
                doc_id="customs_ordinance",
                article="133",
                title=art133.get("t", ""),
                text_snippet=_trim(art133.get("s", ""), 200),
                relevance="informational",
            ))
    except Exception:
        pass
    return citations


def _find_classification_procedure_citations() -> List[Citation]:
    """Find classification procedure references."""
    citations = []
    try:
        # Procedure #3 (Classification)
        proc_data = None
        try:
            from lib._procedures_data import get_procedure
            proc_data = get_procedure("3")
        except Exception:
            pass

        if proc_data:
            citations.append(Citation(
                doc_id="procedure_3",
                article="",
                title=proc_data.get("name_he", "נוהל סיווג טובין"),
                text_snippet="",
                relevance="informational",
            ))
    except Exception:
        pass
    return citations


def _find_hs_citations(hs_code: str, origin: Optional[str]) -> List[Citation]:
    """Find citations relevant to a specific HS code."""
    citations = []
    try:
        digits = "".join(c for c in (hs_code or "") if c.isdigit())
        if len(digits) < 4:
            return citations

        chapter = int(digits[:2])

        # Framework order article 03 — GIR classification rules
        art03 = _get_framework_article("03")
        if art03:
            citations.append(Citation(
                doc_id="framework_order",
                article="03",
                title="כללי סיווג (GIR)",
                text_snippet=_trim(art03.get("s", ""), 200),
                relevance="supporting",
            ))

        # Discount codes: search for HS code match
        try:
            from lib._discount_codes_data import DISCOUNT_CODES
            for item_num, dc in DISCOUNT_CODES.items():
                for sc_key, sc_val in dc.get("sub_codes", {}).items():
                    if isinstance(sc_val, dict):
                        for ref_hs in sc_val.get("hs_codes", []):
                            ref_digits = "".join(c for c in ref_hs if c.isdigit())
                            if ref_digits and digits.startswith(ref_digits[:4]):
                                citations.append(Citation(
                                    doc_id="discount_codes",
                                    article=item_num,
                                    title=f"קוד הנחה {item_num}",
                                    text_snippet=dc.get("description_he", ""),
                                    relevance="informational",
                                ))
                                break
                    # Only need one match per discount item
                    if citations and citations[-1].doc_id == "discount_codes" and citations[-1].article == item_num:
                        break
        except Exception:
            pass

    except Exception:
        pass
    return citations


def _find_fta_citations(origin: str) -> List[Citation]:
    """Find FTA citations for a given country of origin."""
    citations = []
    try:
        fta_doc = _get_fta_doc(origin)
        if fta_doc:
            citations.append(Citation(
                doc_id=fta_doc.get("doc_id", ""),
                article="",
                title=fta_doc.get("title_he", ""),
                text_snippet=(
                    f"סוג הוכחת מקור: {fta_doc.get('origin_proof_type', 'לא ידוע')}"
                ),
                relevance="supporting",
            ))

            # Framework order FTA articles (16-23)
            for art_num in ["16", "17", "18", "19", "20", "21", "22", "23"]:
                art = _get_framework_article(art_num)
                if art and art.get("fta"):
                    fta_country = art.get("fta", "")
                    # Match if the framework article's FTA country matches origin
                    resolved = None
                    try:
                        from lib._document_registry import _resolve_country_code
                        resolved = _resolve_country_code(origin)
                    except Exception:
                        pass
                    if fta_country and resolved and fta_country.upper() == resolved.upper():
                        citations.append(Citation(
                            doc_id="framework_order",
                            article=art_num,
                            title=art.get("t", ""),
                            text_snippet=_trim(art.get("s", ""), 200),
                            relevance="supporting",
                        ))
                        break
    except Exception:
        pass
    return citations


def _find_framework_order_citations() -> List[Citation]:
    """Find framework order classification rules."""
    citations = []
    try:
        # Article 06: Conditional items
        art06 = _get_framework_article("06")
        if art06:
            citations.append(Citation(
                doc_id="framework_order",
                article="06",
                title=art06.get("t", ""),
                text_snippet=_trim(art06.get("s", ""), 200),
                relevance="informational",
            ))
    except Exception:
        pass
    return citations


def _generate_flags(
    hs_codes: List[str],
    origin: Optional[str],
    invoice_data: Optional[dict],
    results: Any,
) -> List[dict]:
    """Generate compliance flags from classification context."""
    flags = []
    try:
        # Flag: Dual-use chapters
        _DUAL_USE_CHAPTERS = {28, 29, 38, 84, 85, 87, 88, 90, 93}
        for hs in hs_codes:
            digits = "".join(c for c in (hs or "") if c.isdigit())
            if len(digits) >= 2:
                ch = int(digits[:2])
                if ch in _DUAL_USE_CHAPTERS:
                    flags.append({
                        "type": "DUAL_USE",
                        "severity": "warning",
                        "message": f"פרק {ch} -- שימוש כפול אפשרי. יש לבדוק אם נדרש אישור ייצוא.",
                    })
                    break

        # Flag: Missing origin for FTA-eligible
        if not origin and hs_codes:
            flags.append({
                "type": "MISSING_ORIGIN",
                "severity": "info",
                "message": "ארץ מקור לא צוינה -- לא ניתן לבדוק הסכמי סחר חופשי.",
            })

        # Flag: FTA available
        if origin:
            fta_doc = _get_fta_doc(origin)
            if fta_doc:
                flags.append({
                    "type": "FTA_AVAILABLE",
                    "severity": "info",
                    "message": (
                        f"קיים הסכם סחר עם {fta_doc.get('title_he', origin)}. "
                        f"הוכחת מקור: {fta_doc.get('origin_proof_type', 'לא ידוע')}."
                    ),
                })

        # Flag: Conditional item (chapter 98/99)
        for hs in hs_codes:
            digits = "".join(c for c in (hs or "") if c.isdigit())
            if len(digits) >= 2:
                ch = int(digits[:2])
                if ch >= 98:
                    flags.append({
                        "type": "CONDITIONAL_ITEM",
                        "severity": "warning",
                        "message": (
                            f"פרט מותנה (פרק {ch}) -- יש להגיש רשימון מיוחד "
                            f"לפי סעיף 06 לצו המסגרת."
                        ),
                    })
                    break

        # Flag: Invoice validation issues
        if invoice_data and isinstance(invoice_data, dict):
            missing_fields = []
            for required in ["seller", "buyer", "total", "currency", "date"]:
                if not invoice_data.get(required):
                    missing_fields.append(required)
            if missing_fields:
                flags.append({
                    "type": "INVOICE_INCOMPLETE",
                    "severity": "warning",
                    "message": f"שדות חסרים בחשבונית: {', '.join(missing_fields)}",
                })

        # Flag: High-risk origins
        _HIGH_RISK_ORIGINS = {"KP", "IR", "SY", "CU"}
        if origin and origin.upper() in _HIGH_RISK_ORIGINS:
            flags.append({
                "type": "SANCTIONS_RISK",
                "severity": "critical",
                "message": f"ארץ מקור {origin} -- סיכון סנקציות. יש לבדוק רישיון יבוא.",
            })

        # Flag: Antidumping chapters (steel, aluminium, ceramics)
        _ANTIDUMPING_CHAPTERS = {69, 72, 73, 76}
        for hs in hs_codes:
            digits = "".join(c for c in (hs or "") if c.isdigit())
            if len(digits) >= 2:
                ch = int(digits[:2])
                if ch in _ANTIDUMPING_CHAPTERS:
                    flags.append({
                        "type": "ANTIDUMPING",
                        "severity": "info",
                        "message": (
                            f"פרק {ch} -- חשיפה אפשרית להיטל היצף (antidumping). "
                            f"יש לבדוק צו היצף בתוקף."
                        ),
                    })
                    break

    except Exception:
        pass
    return flags


def build_compliance_context(
    hs_codes: List[str],
    origin: Optional[str] = None,
    product_descriptions: Optional[List[str]] = None,
) -> str:
    """Build text context string for AI prompts (not HTML).

    Used by tool_calling_engine to inject compliance knowledge into the
    system prompt before classification.
    """
    try:
        parts = []

        # Relevant documents list
        for hs in (hs_codes or [])[:3]:
            docs = _get_relevant_docs(hs_code=hs, origin=origin)
            if docs:
                doc_names = [d.get("title_he", d.get("doc_id", "")) for d in docs[:8]]
                parts.append(f"מסמכים רלוונטיים ל-{_hs_format(hs)}: {', '.join(doc_names)}")

        # FTA info
        if origin:
            fta_doc = _get_fta_doc(origin)
            if fta_doc:
                parts.append(
                    f"הסכם סחר: {fta_doc.get('title_he', '')} "
                    f"(הוכחת מקור: {fta_doc.get('origin_proof_type', 'N/A')})"
                )

        # Valuation method reference
        art130 = _get_ordinance_article("130")
        if art130:
            parts.append(f"הערכה: {art130.get('t', '')} (סעיף 130 לפקודת המכס)")

        # GIR rules reference
        art03 = _get_framework_article("03")
        if art03:
            parts.append(f"סיווג: {art03.get('s', '')}")

        return "\n".join(parts) if parts else ""
    except Exception:
        traceback.print_exc()
        return ""


def build_attachment_html(
    doc_id: str,
    section: Optional[str] = None,
) -> Optional[Tuple[str, bytes]]:
    """Build an HTML attachment for large document content.

    Looks for pre-rendered HTML in downloads/html/ directory.
    Returns (filename, html_bytes) or None if file not found or content is small.
    """
    try:
        # Check registry for html_file
        doc = None
        try:
            from lib._document_registry import get_document
            doc = get_document(doc_id)
        except Exception:
            pass

        if not doc or not doc.get("has_html") or not doc.get("html_file"):
            return None

        html_file = doc["html_file"]

        # Look in multiple possible locations
        base_dirs = [
            os.path.join(os.path.dirname(__file__), "..", "downloads", "html"),
            os.path.join(os.path.dirname(__file__), "..", "..", "downloads", "html"),
            os.path.join(os.path.dirname(__file__), "downloads", "html"),
        ]

        for base in base_dirs:
            path = os.path.join(base, html_file)
            if os.path.isfile(path):
                with open(path, "rb") as f:
                    content = f.read()
                if len(content) < _INLINE_THRESHOLD:
                    # Small enough to inline -- caller decides
                    return None
                filename = html_file
                if section:
                    name, ext = os.path.splitext(html_file)
                    filename = f"{name}_{section}{ext}"
                return (filename, content)

        return None
    except Exception:
        traceback.print_exc()
        return None
