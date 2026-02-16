"""
RCB Report Builder — Classification Report HTML Helpers
========================================================
Renders justification chains, legal strength, devil's advocate results,
and knowledge gaps as email-safe HTML (inline CSS, table-based, RTL Hebrew).

Session 27 — Assignment 12: Client Classification Report Email Upgrade
R.P.A.PORT LTD - February 2026
"""


# ═══════════════════════════════════════════
#  LEGAL STRENGTH BADGE
# ═══════════════════════════════════════════

def build_legal_strength_badge(legal_strength, coverage_pct):
    """
    Render a visual badge showing legal strength + coverage %.

    Args:
        legal_strength: "strong", "moderate", or "weak"
        coverage_pct: 0-100

    Returns:
        HTML string
    """
    config = {
        "strong": {
            "color": "#166534", "bg": "#dcfce7", "border": "#bbf7d0",
            "label_he": "חזק", "icon": "&#9679;&#9679;&#9679;",
        },
        "moderate": {
            "color": "#92400e", "bg": "#fef3c7", "border": "#fde68a",
            "label_he": "בינוני", "icon": "&#9679;&#9679;&#9675;",
        },
        "weak": {
            "color": "#991b1b", "bg": "#fee2e2", "border": "#fca5a5",
            "label_he": "חלש", "icon": "&#9679;&#9675;&#9675;",
        },
    }
    c = config.get(legal_strength, config["weak"])

    return (
        f'<div style="display:inline-block;background:{c["bg"]};border:1px solid {c["border"]};'
        f'border-radius:8px;padding:4px 12px;margin-top:8px">'
        f'<span style="font-size:12px;color:{c["color"]};letter-spacing:2px">{c["icon"]}</span> '
        f'<span style="font-size:12px;font-weight:700;color:{c["color"]}">'
        f'{c["label_he"]} ({coverage_pct}%)</span>'
        f'</div>'
    )


# ═══════════════════════════════════════════
#  JUSTIFICATION CHAIN
# ═══════════════════════════════════════════

_STEP_LABELS_HE = {
    1: "פרק",
    2: "פריט",
    3: "תת-פריט",
    4: "הערות לפרק",
    5: "הנחיות סיווג",
    6: "החלטות מקדמיות",
}


def build_justification_html(justification):
    """
    Render the 6-step justification chain as a visual timeline.

    Args:
        justification: dict from build_justification_chain()

    Returns:
        HTML string (empty string if no chain data)
    """
    chain = justification.get("chain", [])
    if not chain:
        return ""

    legal_strength = justification.get("legal_strength", "weak")
    coverage_pct = justification.get("coverage_pct", 0)

    html = (
        '<div style="margin-top:12px;padding-top:12px;border-top:1px solid #f0f0f0">'
        '<table style="width:100%" cellpadding="0" cellspacing="0"><tr>'
        '<td style="vertical-align:middle">'
        '<span style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px">'
        'שרשרת נימוק משפטי</span></td>'
        '<td style="text-align:left;vertical-align:middle">'
        f'{build_legal_strength_badge(legal_strength, coverage_pct)}'
        '</td></tr></table>'
    )

    # Timeline steps
    for step in chain:
        step_num = step.get("step", 0)
        has_source = step.get("has_source", False)
        decision = step.get("decision", "")
        source_text = step.get("source_text", "")
        label_he = _STEP_LABELS_HE.get(step_num, f"שלב {step_num}")

        dot_color = "#22c55e" if has_source else "#ef4444"
        line_color = "#e5e7eb"

        html += (
            f'<div style="display:table;width:100%;margin-top:8px">'
            f'<div style="display:table-cell;width:24px;vertical-align:top;padding-top:4px">'
            f'<div style="width:10px;height:10px;border-radius:50%;background:{dot_color};'
            f'margin:0 auto"></div>'
            f'<div style="width:2px;height:100%;background:{line_color};margin:2px auto 0"></div>'
            f'</div>'
            f'<div style="display:table-cell;vertical-align:top;padding:0 0 6px 8px">'
            f'<span style="font-size:10px;color:#888;text-transform:uppercase">{label_he}</span><br>'
            f'<span style="font-size:12px;color:#333;font-weight:600">{_escape(decision)}</span>'
        )

        if source_text and has_source:
            short_source = source_text[:120]
            html += (
                f'<div style="font-size:11px;color:#666;margin-top:2px;'
                f'font-style:italic">{_escape(short_source)}</div>'
            )

        html += '</div></div>'

    html += '</div>'
    return html


# ═══════════════════════════════════════════
#  DEVIL'S ADVOCATE (CHALLENGE)
# ═══════════════════════════════════════════

def build_challenge_html(challenge):
    """
    Render devil's advocate results: alternatives considered and verdict.

    Args:
        challenge: dict from challenge_classification()

    Returns:
        HTML string (empty string if no alternatives)
    """
    alternatives = challenge.get("alternatives", [])
    if not alternatives:
        return ""

    challenge_passed = challenge.get("challenge_passed", False)
    unresolved = challenge.get("unresolved_count", 0)

    if challenge_passed:
        verdict_bg = "#dcfce7"
        verdict_border = "#bbf7d0"
        verdict_color = "#166534"
        verdict_text = "הסיווג עמד בבדיקה"
        verdict_icon = "&#10003;"
    else:
        verdict_bg = "#fef3c7"
        verdict_border = "#fde68a"
        verdict_color = "#92400e"
        verdict_text = f"{unresolved} חלופות פתוחות"
        verdict_icon = "&#9888;"

    html = (
        '<div style="margin-top:10px;padding-top:10px;border-top:1px solid #f0f0f0">'
        '<span style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px">'
        'בדיקת חלופות (Devil\'s Advocate)</span>'
        f'<div style="background:{verdict_bg};border:1px solid {verdict_border};'
        f'border-radius:6px;padding:6px 12px;margin-top:6px;font-size:12px;color:{verdict_color}">'
        f'<span style="font-weight:700">{verdict_icon} {verdict_text}</span>'
        f' &mdash; {len(alternatives)} פרקים נבדקו'
        '</div>'
    )

    # Show top 3 alternatives as compact rows
    for alt in alternatives[:3]:
        ch = alt.get("chapter", "?")
        reason_for = alt.get("reason_for", "")[:80]
        reason_against = alt.get("reason_against", "")
        has_against = bool(reason_against)
        row_icon = "&#10007;" if has_against else "&#63;"
        row_color = "#666" if has_against else "#b45309"

        html += (
            f'<div style="font-size:11px;color:{row_color};margin-top:4px;padding:3px 0;'
            f'border-bottom:1px dotted #eee">'
            f'<span style="font-weight:700">CH {ch}</span> '
            f'{row_icon} {_escape(reason_for)}'
            '</div>'
        )

    html += '</div>'
    return html


# ═══════════════════════════════════════════
#  KNOWLEDGE GAPS SUMMARY
# ═══════════════════════════════════════════

def build_gaps_summary_html(gaps):
    """
    Render a summary of knowledge gaps detected for this classification.

    Args:
        gaps: list of gap dicts from justification_engine

    Returns:
        HTML string (empty if no gaps)
    """
    if not gaps:
        return ""

    high_priority = [g for g in gaps if g.get("priority") in ("critical", "high")]
    if not high_priority:
        return ""

    html = (
        '<div style="margin-top:8px;font-size:11px;color:#b45309;'
        'background:#fffbeb;border:1px solid #fde68a;border-radius:6px;padding:6px 10px">'
        f'<span style="font-weight:700">&#9888; {len(high_priority)} פערי ידע זוהו</span>'
        '<span style="color:#888"> &mdash; בתהליך השלמה אוטומטית</span>'
        '</div>'
    )
    return html


# ═══════════════════════════════════════════
#  CROSS-CHECK SUMMARY (for email)
# ═══════════════════════════════════════════

def build_cross_check_badge(cls_item):
    """
    Render a cross-check tier badge if available.

    Args:
        cls_item: classification dict (may have cross_check_tier)

    Returns:
        HTML string (empty if no cross-check data)
    """
    tier = cls_item.get("cross_check_tier", 0)
    if not tier:
        return ""

    tier_config = {
        1: {"label": "T1 — AI Unanimous", "bg": "#dcfce7", "color": "#166534"},
        2: {"label": "T2 — Majority", "bg": "#dbeafe", "color": "#1e40af"},
        3: {"label": "T3 — AI Conflict", "bg": "#fef3c7", "color": "#92400e"},
        4: {"label": "T4 — Divergence", "bg": "#fee2e2", "color": "#991b1b"},
    }
    tc = tier_config.get(tier, tier_config[4])

    return (
        f'<span style="display:inline-block;background:{tc["bg"]};color:{tc["color"]};'
        f'font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px;margin-right:6px">'
        f'{tc["label"]}</span>'
    )


# ═══════════════════════════════════════════
#  CLASSIFICATION REPORT — FIRESTORE SAVE
# ═══════════════════════════════════════════

def build_report_document(results, tracking_code, to_email, invoice_data,
                          invoice_validation=None):
    """
    Build a structured document for the classification_reports collection.

    Args:
        results: full classification results dict
        tracking_code: RCB tracking code
        to_email: recipient email
        invoice_data: parsed invoice data
        invoice_validation: validation results

    Returns:
        dict ready for Firestore .add()
    """
    from datetime import datetime, timezone

    classifications = (
        results.get("agents", {}).get("classification", {}).get("classifications", [])
    )

    items_summary = []
    total_strength = {"strong": 0, "moderate": 0, "weak": 0}

    for cls in classifications:
        hs = cls.get("hs_code", "")
        item_name = cls.get("item", "")[:100]
        justification = cls.get("justification", {})
        challenge = cls.get("challenge", {})
        strength = justification.get("legal_strength", "unknown")

        if strength in total_strength:
            total_strength[strength] += 1

        items_summary.append({
            "hs_code": hs,
            "item": item_name,
            "legal_strength": strength,
            "coverage_pct": justification.get("coverage_pct", 0),
            "sources_found": justification.get("sources_found", 0),
            "sources_needed": justification.get("sources_needed", 0),
            "challenge_passed": challenge.get("challenge_passed", True),
            "alternatives_checked": challenge.get("chapters_checked", 0),
            "gaps_count": len(justification.get("gaps", [])),
            "confidence": cls.get("confidence", ""),
            "cross_check_tier": cls.get("cross_check_tier", 0),
        })

    doc = {
        "tracking_code": tracking_code,
        "to_email": to_email,
        "direction": invoice_data.get("direction", "unknown"),
        "seller": invoice_data.get("seller", ""),
        "buyer": invoice_data.get("buyer", ""),
        "bl_number": invoice_data.get("bl_number", ""),
        "awb_number": invoice_data.get("awb_number", ""),
        "items_count": len(classifications),
        "items": items_summary,
        "strength_summary": total_strength,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if invoice_validation:
        doc["invoice_score"] = invoice_validation.get("score", 0)
        doc["invoice_valid"] = invoice_validation.get("is_valid", False)

    cross_check = results.get("cross_check")
    if cross_check:
        tiers = [cc.get("tier", 0) for cc in cross_check]
        doc["cross_check_tiers"] = tiers
        doc["cross_check_avg"] = round(sum(tiers) / len(tiers), 1) if tiers else 0

    return doc


# ═══════════════════════════════════════════
#  DAILY DIGEST UPGRADE HELPERS
# ═══════════════════════════════════════════

def build_classification_digest_html(db, yesterday_iso):
    """
    Build classification stats section for the daily digest.

    Args:
        db: Firestore client
        yesterday_iso: ISO timestamp for yesterday

    Returns:
        tuple: (html_string, stats_dict)
    """
    stats = {
        "reports": 0,
        "strong": 0,
        "moderate": 0,
        "weak": 0,
        "gaps_open": 0,
        "gaps_filled": 0,
        "pupil_questions": 0,
    }

    # Count recent reports
    try:
        reports = list(
            db.collection("classification_reports")
            .where("created_at", ">=", yesterday_iso)
            .limit(200)
            .stream()
        )
        stats["reports"] = len(reports)
        for r in reports:
            data = r.to_dict()
            summary = data.get("strength_summary", {})
            stats["strong"] += summary.get("strong", 0)
            stats["moderate"] += summary.get("moderate", 0)
            stats["weak"] += summary.get("weak", 0)
    except Exception:
        pass

    # Count gaps
    try:
        open_gaps = list(
            db.collection("knowledge_gaps")
            .where("status", "==", "open")
            .limit(500)
            .stream()
        )
        stats["gaps_open"] = len(open_gaps)
    except Exception:
        pass

    try:
        filled = list(
            db.collection("knowledge_gaps")
            .where("status", "==", "filled")
            .where("filled_at", ">=", yesterday_iso)
            .limit(200)
            .stream()
        )
        stats["gaps_filled"] = len(filled)
    except Exception:
        pass

    # Count pupil questions
    try:
        questions = list(
            db.collection("pupil_questions")
            .where("answered", "==", False)
            .limit(100)
            .stream()
        )
        stats["pupil_questions"] = len(questions)
    except Exception:
        pass

    if stats["reports"] == 0 and stats["gaps_open"] == 0:
        return "", stats

    # Build HTML section
    total_items = stats["strong"] + stats["moderate"] + stats["weak"]
    html = (
        '<tr><td colspan="2" style="padding:8px 10px;font-size:13px;font-weight:bold;'
        'color:#1e3a5f;border-bottom:2px solid #1e3a5f;padding-top:12px">'
        'Classification Intelligence</td></tr>'
    )

    html += _digest_row("Reports sent", str(stats["reports"]))

    if total_items > 0:
        strength_text = (
            f'<span style="color:#166534">{stats["strong"]} strong</span> / '
            f'<span style="color:#92400e">{stats["moderate"]} moderate</span> / '
            f'<span style="color:#991b1b">{stats["weak"]} weak</span>'
        )
        html += _digest_row("Legal strength", strength_text)

    if stats["gaps_open"] > 0 or stats["gaps_filled"] > 0:
        html += _digest_row(
            "Knowledge gaps",
            f'{stats["gaps_open"]} open, {stats["gaps_filled"]} filled yesterday',
        )

    if stats["pupil_questions"] > 0:
        html += _digest_row(
            "Pupil questions",
            f'{stats["pupil_questions"]} awaiting your answer',
        )

    return html, stats


def _digest_row(label, value):
    """Helper: single row for digest table."""
    return (
        f'<tr><td style="padding:5px 10px;font-size:12px;border-bottom:1px solid #eee">'
        f'{label}</td>'
        f'<td style="padding:5px 10px;font-size:12px;border-bottom:1px solid #eee">'
        f'{value}</td></tr>'
    )


# ═══════════════════════════════════════════
#  UTILITY
# ═══════════════════════════════════════════

def _escape(text):
    """HTML-escape text for safe rendering."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
