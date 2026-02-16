"""
RCB Report Builder — Classification Report & Daily Digest HTML
================================================================
Renders justification chains, legal strength, devil's advocate results,
knowledge gaps, and full daily digest as email-safe HTML.

Session 27 — Assignments 12 & 13
R.P.A.PORT LTD - February 2026
"""

import logging

logger = logging.getLogger("rcb.report_builder")


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
#  DAILY DIGEST — FULL 5-SECTION BUILDER
#  (Assignment 13)
# ═══════════════════════════════════════════

# Keep old function as backward-compatible alias
def build_classification_digest_html(db, yesterday_iso):
    """Backward-compatible wrapper. Returns (html_rows, stats)."""
    stats = _gather_digest_stats(db, yesterday_iso)
    html = _build_section1_summary_rows(stats)
    return html, stats


def _digest_row(label, value):
    """Helper: single row for digest table."""
    return (
        f'<tr><td style="padding:5px 10px;font-size:12px;border-bottom:1px solid #eee">'
        f'{label}</td>'
        f'<td style="padding:5px 10px;font-size:12px;border-bottom:1px solid #eee">'
        f'{value}</td></tr>'
    )


def _section_header(title):
    """Render a section header for the digest."""
    return (
        f'<div style="font-size:14px;font-weight:700;color:#0f2439;margin:18px 0 8px 0;'
        f'padding-bottom:6px;border-bottom:2px solid #1a3a5c">{title}</div>'
    )


def _gather_digest_stats(db, yesterday_iso):
    """Query all collections and build a comprehensive stats dict."""
    stats = {
        "reports": 0,
        "items_classified": 0,
        "avg_confidence": 0,
        "strong": 0,
        "moderate": 0,
        "weak": 0,
        "gaps_open": 0,
        "gaps_filled": 0,
        "gaps_filled_self_enrichment": 0,
        "gaps_filled_ai": 0,
        "gaps_filled_other": 0,
        "pupil_questions": 0,
        "emails_processed": 0,
        "deals_tracked": 0,
        "cross_check_t1": 0,
        "cross_check_t2": 0,
        "cross_check_t3": 0,
        "cross_check_t4": 0,
        "cross_check_total": 0,
        "enrichment": {},
        "low_confidence_items": [],
        "pc_agent_pending": 0,
        "failed_extractions": 0,
    }

    # ── Classification reports ──
    confidence_values = []
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
            stats["items_classified"] += data.get("items_count", 0)

            # Cross-check tiers
            for t in data.get("cross_check_tiers", []):
                if t == 1:
                    stats["cross_check_t1"] += 1
                elif t == 2:
                    stats["cross_check_t2"] += 1
                elif t == 3:
                    stats["cross_check_t3"] += 1
                elif t == 4:
                    stats["cross_check_t4"] += 1
                stats["cross_check_total"] += 1

            # Low-confidence items + avg confidence tracking
            for item in data.get("items", []):
                strength = item.get("legal_strength", "")
                conf = item.get("confidence", 0)
                if isinstance(conf, (int, float)) and conf > 0:
                    confidence_values.append(conf)
                if strength == "weak" or not item.get("challenge_passed", True):
                    stats["low_confidence_items"].append({
                        "hs_code": item.get("hs_code", ""),
                        "item": item.get("item", "")[:60],
                        "strength": strength,
                        "confidence": conf,
                        "tracking": data.get("tracking_code", ""),
                    })

        if confidence_values:
            stats["avg_confidence"] = round(sum(confidence_values) / len(confidence_values))
    except Exception as e:
        logger.warning(f"Digest: classification_reports query failed: {e}")

    # ── Emails processed (rcb_processed) ──
    try:
        processed = list(
            db.collection("rcb_processed")
            .where("timestamp", ">=", yesterday_iso)
            .limit(500)
            .stream()
        )
        stats["emails_processed"] = len(processed)
    except Exception:
        # Fallback: try tracker_observations
        try:
            obs = list(
                db.collection("tracker_observations")
                .where("observed_at", ">=", yesterday_iso)
                .limit(500)
                .stream()
            )
            stats["emails_processed"] = len(obs)
        except Exception:
            pass

    # ── Deals tracked ──
    try:
        deals = list(
            db.collection("tracker_deals")
            .where("status", "==", "active")
            .limit(500)
            .stream()
        )
        stats["deals_tracked"] = len(deals)
    except Exception:
        pass

    # ── Knowledge gaps ──
    try:
        open_gaps = list(
            db.collection("knowledge_gaps")
            .where("status", "==", "open")
            .limit(500)
            .stream()
        )
        stats["gaps_open"] = len(open_gaps)
        stats["_open_gaps_data"] = [
            {"id": g.id, **g.to_dict()} for g in open_gaps[:20]
        ]
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
        # Also check filled_by_ai status
        filled_ai = list(
            db.collection("knowledge_gaps")
            .where("status", "==", "filled_by_ai")
            .where("filled_at", ">=", yesterday_iso)
            .limit(200)
            .stream()
        )
        all_filled = filled + filled_ai
        stats["gaps_filled"] = len(all_filled)
        for f in all_filled:
            fdata = f.to_dict()
            fill_status = fdata.get("status", "")
            if fill_status == "filled_by_ai":
                stats["gaps_filled_ai"] += 1
            elif fdata.get("filled_by") == "self_enrichment":
                stats["gaps_filled_self_enrichment"] += 1
            else:
                stats["gaps_filled_other"] += 1
    except Exception:
        pass

    # ── Pupil questions ──
    try:
        questions = list(
            db.collection("pupil_questions")
            .where("answered", "==", False)
            .limit(100)
            .stream()
        )
        stats["pupil_questions"] = len(questions)
        stats["_questions_data"] = [
            {"id": q.id, **q.to_dict()} for q in questions[:10]
        ]
    except Exception:
        pass

    # ── Enrichment (from overnight brain enrichment_reports) ──
    try:
        reports_list = list(
            db.collection("enrichment_reports")
            .limit(5)
            .stream()
        )
        if reports_list:
            # Pick the latest by date field
            latest = None
            for rpt in reports_list:
                rdata = rpt.to_dict()
                if not latest or rdata.get("date", "") > latest.get("date", ""):
                    latest = rdata
            if latest:
                stats["enrichment"] = latest
    except Exception:
        # Fallback to legacy overnight_audit_results
        try:
            audits = list(
                db.collection("overnight_audit_results")
                .limit(1)
                .stream()
            )
            if audits:
                audit = audits[0].to_dict()
                stats["enrichment"] = audit.get("self_enrichment", {})
        except Exception:
            pass

    # ── PC Agent pending tasks ──
    try:
        pending = list(
            db.collection("pc_agent_tasks")
            .where("status", "in", ["pending", "retry"])
            .limit(100)
            .stream()
        )
        stats["pc_agent_pending"] = len(pending)
    except Exception:
        pass

    # ── Failed extractions (last 24h) ──
    try:
        failed_ext = list(
            db.collection("rcb_processed")
            .where("status", "==", "extraction_failed")
            .where("timestamp", ">=", yesterday_iso)
            .limit(100)
            .stream()
        )
        stats["failed_extractions"] = len(failed_ext)
    except Exception:
        pass

    return stats


def _build_section1_summary_rows(stats):
    """Build Section 1 table rows (backward compatible format)."""
    total_items = stats["strong"] + stats["moderate"] + stats["weak"]
    if stats["reports"] == 0 and stats["gaps_open"] == 0:
        return ""

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

    return html


def build_full_daily_digest(db, yesterday_iso, date_str):
    """
    Build the complete 5-section daily digest HTML.

    Args:
        db: Firestore client
        yesterday_iso: ISO timestamp for 24h ago
        date_str: Display date string (DD/MM/YYYY)

    Returns:
        tuple: (full_html, stats_dict)
    """
    stats = _gather_digest_stats(db, yesterday_iso)

    html = f'''<div style="font-family:'Segoe UI',Arial,Helvetica,sans-serif;max-width:680px;margin:0 auto;direction:rtl;background:#f0f2f5;padding:0">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#0f2439 0%,#1a3a5c 50%,#245a8a 100%);color:#fff;padding:28px 30px 24px;border-radius:12px 12px 0 0">
        <table style="width:100%" cellpadding="0" cellspacing="0"><tr>
            <td style="vertical-align:middle">
                <h1 style="margin:0;font-size:20px;font-weight:700;letter-spacing:0.3px">סיכום יומי — RCB</h1>
                <p style="margin:6px 0 0 0;font-size:13px;opacity:0.8">בוקר טוב דורון, הנה מה שקרה ב-24 שעות האחרונות</p>
            </td>
            <td style="text-align:left;vertical-align:middle">
                <div style="background:rgba(255,255,255,0.15);border-radius:8px;padding:8px 14px;display:inline-block">
                    <span style="font-size:10px;opacity:0.7;display:block;text-align:center">DATE</span>
                    <span style="font-size:14px;font-weight:600;letter-spacing:0.5px">{date_str}</span>
                </div>
            </td>
        </tr></table>
    </div>

    <!-- Body -->
    <div style="background:#ffffff;padding:24px 30px;border-left:1px solid #e0e0e0;border-right:1px solid #e0e0e0">'''

    # ── SECTION 1: Daily Summary ──
    html += _build_section1_html(stats)

    # ── SECTION 2: Pupil Questions ──
    html += _build_section2_html(stats)

    # ── SECTION 3: Knowledge Gaps ──
    html += _build_section3_html(stats)

    # ── SECTION 4: Enrichment Report ──
    html += _build_section4_html(stats)

    # ── SECTION 5: Exceptions & Alerts ──
    html += _build_section5_html(stats)

    # Instructions
    html += '''<div style="margin-top:20px;padding:12px 16px;background:#f8faff;border:1px solid #d4e3f5;border-radius:8px;font-size:12px;color:#555">
        <strong style="color:#1a3a5c">How to respond:</strong><br>
        Reply to this email with answers to pupil questions. Format: "Q1: your answer"
    </div>'''

    # Footer
    html += '''</div>
    <div style="background:#f8faff;padding:20px 30px;border-top:1px solid #e0e0e0;border-radius:0 0 12px 12px;border-left:1px solid #e0e0e0;border-right:1px solid #e0e0e0">
        <table style="width:100%" cellpadding="0" cellspacing="0"><tr>
            <td style="vertical-align:middle;width:60px">
                <img src="https://rpa-port.com/wp-content/uploads/2016/09/logo.png" style="width:50px;border-radius:8px" alt="RPA PORT">
            </td>
            <td style="vertical-align:middle;border-right:3px solid #1a3a5c;padding-right:16px">
                <strong style="color:#0f2439;font-size:13px">RCB — AI Customs Broker</strong><br>
                <span style="color:#666;font-size:11px">R.P.A. PORT LTD</span>
                <span style="color:#ccc;margin:0 6px">|</span>
                <span style="color:#1a3a5c;font-size:11px">rcb@rpa-port.co.il</span>
            </td>
        </tr></table>
        <p style="font-size:9px;color:#bbb;margin:10px 0 0 0">Only doron@ receives this digest.</p>
    </div>
    </div>'''

    return html, stats


def _build_section1_html(stats):
    """Section 1: Daily Summary — key metrics cards."""
    reports = stats.get("reports", 0)
    items = stats.get("items_classified", 0)
    emails = stats.get("emails_processed", 0)
    deals = stats.get("deals_tracked", 0)
    avg_conf = stats.get("avg_confidence", 0)
    cc_total = stats.get("cross_check_total", 0)
    cc_t1 = stats.get("cross_check_t1", 0)
    agreement_pct = round(cc_t1 / max(cc_total, 1) * 100)

    html = _section_header("1. סיכום יומי")

    # Metrics grid (3x3)
    html += '<table style="width:100%;border-collapse:collapse" cellpadding="0" cellspacing="0">'

    html += '<tr>'
    html += _metric_cell("דו״חות סיווג", str(reports), "#1a3a5c")
    html += _metric_cell("פריטים סווגו", str(items), "#1a3a5c")
    html += _metric_cell("מיילים עובדו", str(emails), "#555")
    html += '</tr><tr>'
    html += _metric_cell("משלוחים פעילים", str(deals), "#555")

    # Avg confidence
    if avg_conf > 0:
        conf_color = "#166534" if avg_conf >= 80 else "#92400e" if avg_conf >= 60 else "#991b1b"
        html += _metric_cell("ביטחון ממוצע", f"{avg_conf}%", conf_color)
    else:
        html += _metric_cell("ביטחון ממוצע", "N/A", "#aaa")

    # Model agreement rate
    if cc_total > 0:
        agr_color = "#166534" if agreement_pct >= 70 else "#92400e" if agreement_pct >= 40 else "#991b1b"
        html += _metric_cell("הסכמת AI", f"{agreement_pct}%", agr_color)
    else:
        html += _metric_cell("הסכמת AI", "N/A", "#aaa")

    html += '</tr><tr>'

    # Legal strength summary
    strong = stats.get("strong", 0)
    moderate = stats.get("moderate", 0)
    weak = stats.get("weak", 0)
    total = strong + moderate + weak
    if total > 0:
        strong_pct = round(strong / total * 100)
        html += _metric_cell("חוזק משפטי", f"{strong_pct}% חזק", "#166534" if strong_pct >= 60 else "#92400e")
    else:
        html += _metric_cell("חוזק משפטי", "N/A", "#aaa")
    html += '<td></td><td></td>'

    html += '</tr></table>'
    return html


def _metric_cell(label, value, color):
    """Render a single metric cell."""
    return (
        f'<td style="width:33%;padding:10px 8px;text-align:center;border:1px solid #f0f0f0">'
        f'<div style="font-size:22px;font-weight:700;color:{color}">{value}</div>'
        f'<div style="font-size:11px;color:#888;margin-top:2px">{label}</div>'
        f'</td>'
    )


def _build_section2_html(stats):
    """Section 2: Pupil Questions — numbered list with confidence + action."""
    questions_data = stats.get("_questions_data", [])
    count = stats.get("pupil_questions", 0)
    if count == 0:
        return ""

    html = _section_header(f"2. שאלות תלמיד ({count})")

    for i, q in enumerate(questions_data[:8], 1):
        question_text = q.get("question_he", q.get("question_en", ""))
        context = q.get("context", "")[:80]
        product = q.get("product", q.get("item", ""))
        hs = q.get("primary_hs", "")
        confidence = q.get("confidence", 0)
        q_type = q.get("type", "")

        type_badge = (
            '<span style="background:#eff6ff;color:#1e40af;font-size:9px;padding:1px 6px;'
            'border-radius:8px;margin-right:4px">chapter dispute</span>'
            if q_type == "chapter_dispute"
            else '<span style="background:#fef3c7;color:#92400e;font-size:9px;padding:1px 6px;'
            'border-radius:8px;margin-right:4px">knowledge gap</span>'
        )

        # Determine action needed
        action = q.get("action_needed", "")
        if not action:
            if q_type == "chapter_dispute":
                action = "confirm correct chapter"
            elif confidence and int(confidence) < 50:
                action = "manual classification needed"
            else:
                action = "reply with answer"

        html += (
            f'<div style="padding:8px 12px;margin-bottom:6px;background:#f8faff;'
            f'border:1px solid #e5e7eb;border-radius:8px;font-size:12px">'
            f'<div style="font-weight:700;color:#0f2439">Q{i}. {_escape(question_text[:120])}</div>'
        )
        if product:
            html += f'<div style="font-size:11px;color:#555;margin-top:3px">מוצר: {_escape(str(product)[:80])}</div>'
        if context:
            html += f'<div style="font-size:11px;color:#666;margin-top:3px">{_escape(context)}</div>'

        # HS + confidence + type badge
        meta_parts = []
        if hs:
            meta_parts.append(f'HS: {_escape(hs)}')
        if confidence:
            conf_val = int(confidence) if isinstance(confidence, (int, float)) else 0
            conf_color = "#166534" if conf_val >= 80 else "#92400e" if conf_val >= 50 else "#991b1b"
            meta_parts.append(f'<span style="color:{conf_color}">confidence: {conf_val}%</span>')
        if meta_parts:
            html += f'<div style="font-size:11px;color:#888;margin-top:2px">{" | ".join(meta_parts)} {type_badge}</div>'

        # Action needed
        html += (
            f'<div style="font-size:10px;color:#1e40af;margin-top:3px;font-weight:600">'
            f'Action: {_escape(action)}</div>'
        )
        html += '</div>'

    if count > 8:
        html += f'<div style="font-size:11px;color:#888;text-align:center">... +{count - 8} more questions</div>'

    return html


def _build_section3_html(stats):
    """Section 3: Knowledge Gaps — open vs filled, with source split."""
    open_count = stats.get("gaps_open", 0)
    filled_count = stats.get("gaps_filled", 0)
    if open_count == 0 and filled_count == 0:
        return ""

    html = _section_header(f"3. פערי ידע")

    filled_se = stats.get("gaps_filled_self_enrichment", 0)
    filled_ai = stats.get("gaps_filled_ai", 0)
    filled_other = stats.get("gaps_filled_other", 0)

    # Summary bar
    html += (
        '<div style="padding:8px 12px;margin-bottom:8px;border-radius:8px;font-size:13px">'
        f'<span style="color:#991b1b;font-weight:700">{open_count} פתוחים</span>'
        f' &nbsp;|&nbsp; '
        f'<span style="color:#166534;font-weight:700">{filled_count} הושלמו אתמול</span>'
    )
    # Split by source
    if filled_count > 0:
        split_parts = []
        if filled_se > 0:
            split_parts.append(f'{filled_se} self-enrichment')
        if filled_ai > 0:
            split_parts.append(f'{filled_ai} AI')
        if filled_other > 0:
            split_parts.append(f'{filled_other} other')
        if split_parts:
            html += f'<div style="font-size:10px;color:#888;margin-top:2px">({", ".join(split_parts)})</div>'
    html += '</div>'

    # List top open gaps with classification context
    open_gaps = stats.get("_open_gaps_data", [])
    for g in open_gaps[:5]:
        desc = g.get("description", "")[:100]
        priority = g.get("priority", "low")
        hs_code = g.get("hs_code", "")
        source = g.get("source", g.get("triggered_by", ""))
        classification_id = g.get("classification_id", "")

        p_color = "#991b1b" if priority == "critical" else "#92400e" if priority == "high" else "#555"
        p_label = priority.upper()

        html += (
            f'<div style="font-size:11px;padding:4px 0;border-bottom:1px dotted #eee;color:#333">'
            f'<span style="color:{p_color};font-weight:700;font-size:10px">[{p_label}]</span> '
            f'{_escape(desc)}'
        )
        # Show which classification triggered the gap
        context_parts = []
        if hs_code:
            context_parts.append(f'HS: {_escape(hs_code)}')
        if source:
            context_parts.append(f'source: {_escape(str(source)[:40])}')
        if context_parts:
            html += f' <span style="color:#888;font-size:10px">({", ".join(context_parts)})</span>'
        html += '</div>'

    return html


def _build_section4_html(stats):
    """Section 4: Enrichment Report — overnight brain results from enrichment_reports."""
    enrichment = stats.get("enrichment", {})
    if not enrichment:
        return ""

    # Overnight brain report structure (from Assignment 19)
    stream_stats = enrichment.get("stream_stats", {})
    cost_data = enrichment.get("cost", {})
    duration = enrichment.get("duration_seconds", 0)

    # If legacy format (from overnight_audit_results), use old rendering
    if not stream_stats and not cost_data:
        processed = enrichment.get("processed", 0)
        filled = enrichment.get("filled", 0)
        failed = enrichment.get("failed", 0)
        if processed == 0:
            return ""
        html = _section_header("4. העשרה אוטומטית (לילית)")
        html += '<table style="width:100%;border-collapse:collapse" cellpadding="0" cellspacing="0"><tr>'
        html += _metric_cell("עובדו", str(processed), "#555")
        html += _metric_cell("הושלמו", str(filled), "#166534")
        html += _metric_cell("נכשלו", str(failed), "#991b1b" if failed > 0 else "#aaa")
        html += '</tr></table>'
        return html

    html = _section_header("4. העשרה אוטומטית (Overnight Brain)")

    # Cost + duration header
    total_cost = cost_data.get("total_spent", 0)
    ai_calls = cost_data.get("gemini_calls", 0)
    budget_limit = cost_data.get("budget_limit", 3.50)
    cost_color = "#166534" if total_cost < 2.0 else "#92400e" if total_cost < 3.0 else "#991b1b"

    html += (
        f'<div style="font-size:12px;margin-bottom:8px;padding:6px 10px;'
        f'background:#f8faff;border-radius:6px;border:1px solid #e0e0e0">'
        f'<span style="color:{cost_color};font-weight:700">${total_cost:.2f}</span>'
        f'<span style="color:#888"> / ${budget_limit}</span>'
        f' &nbsp;|&nbsp; {ai_calls} AI calls'
        f' &nbsp;|&nbsp; {round(duration)}s runtime'
        f'</div>'
    )

    # Stream results
    stream_items = []

    # Patterns learned (Stream 3 CC + Stream 8 self-teach)
    s3 = stream_stats.get("stream_3_cc_learning", {})
    s8 = stream_stats.get("stream_8_self_teach", {})
    patterns = s3.get("patterns_learned", 0) + s8.get("chapters_taught", 0)
    if patterns > 0:
        stream_items.append(("patterns learned", patterns, "#166534"))

    # Terms added (Stream 1 tariff mine)
    s1 = stream_stats.get("stream_1_tariff_mine", {})
    terms = s1.get("terms_indexed", 0)
    if terms > 0:
        stream_items.append(("terms indexed", terms, "#1a3a5c"))

    # Corrections (Stream 3)
    corrections = s3.get("corrections_learned", 0)
    if corrections > 0:
        stream_items.append(("corrections learned", corrections, "#92400e"))

    # Gaps filled (Stream 5)
    s5 = stream_stats.get("stream_5_ai_fill", {})
    gaps = s5.get("gaps_filled", 0)
    if gaps > 0:
        stream_items.append(("gaps filled", gaps, "#166534"))

    # UK tariff fetched (Stream 6)
    s6 = stream_stats.get("stream_6_uk_tariff", {})
    uk = s6.get("fetched", 0)
    if uk > 0:
        stream_items.append(("UK tariff codes", uk, "#555"))

    # Suppliers found (Stream 2)
    s2 = stream_stats.get("stream_2_email_mine", {})
    suppliers = s2.get("suppliers_found", 0)
    if suppliers > 0:
        stream_items.append(("suppliers indexed", suppliers, "#555"))

    # Knowledge synced (Stream 9)
    s9 = stream_stats.get("stream_9_knowledge_sync", {})
    synced = s9.get("patterns_synced", 0) + s9.get("enrichments_synced", 0)
    if synced > 0:
        stream_items.append(("synced to classifiers", synced, "#1e40af"))

    # Garbage fixed (Stream 1)
    garbage = s1.get("garbage_fixed", 0)
    if garbage > 0:
        stream_items.append(("garbage descriptions fixed", garbage, "#92400e"))

    # Rules generated (Stream 8)
    rules = s8.get("rules_generated", 0)
    if rules > 0:
        stream_items.append(("classification rules", rules, "#1a3a5c"))

    if stream_items:
        html += '<table style="width:100%;border-collapse:collapse;margin-top:4px" cellpadding="0" cellspacing="0">'
        for label, count, color in stream_items:
            html += (
                f'<tr>'
                f'<td style="padding:3px 8px;font-size:11px;color:#333;border-bottom:1px dotted #eee">'
                f'{_escape(label)}</td>'
                f'<td style="padding:3px 8px;font-size:12px;font-weight:700;color:{color};'
                f'text-align:left;width:60px;border-bottom:1px dotted #eee">{count}</td>'
                f'</tr>'
            )
        html += '</table>'

    # Budget warning if stopped by budget
    if cost_data.get("stopped_by_budget"):
        html += (
            '<div style="font-size:11px;color:#991b1b;margin-top:6px;font-weight:700">'
            'Budget exhausted — some streams were cut short</div>'
        )

    return html


def _build_section5_html(stats):
    """Section 5: Exceptions & Alerts."""
    # Low-confidence items
    low_conf = stats.get("low_confidence_items", [])

    # Model disagreements
    cc_t4 = stats.get("cross_check_t4", 0)
    cc_t3 = stats.get("cross_check_t3", 0)

    # PC Agent pending
    pc_pending = stats.get("pc_agent_pending", 0)

    # Failed extractions
    failed_ext = stats.get("failed_extractions", 0)

    if not low_conf and cc_t4 == 0 and cc_t3 == 0 and pc_pending == 0 and failed_ext == 0:
        return ""

    html = _section_header("5. חריגים והתראות")

    # Low confidence items (< 70%)
    if low_conf:
        html += '<div style="font-size:12px;font-weight:700;color:#991b1b;margin-bottom:4px">סיווגים בעייתיים:</div>'
        for item in low_conf[:5]:
            hs = item.get("hs_code", "?")
            name = item.get("item", "")[:50]
            strength = item.get("strength", "")
            confidence = item.get("confidence", "")
            tracking = item.get("tracking", "")

            conf_str = f'{confidence}%' if confidence else strength
            html += (
                f'<div style="font-size:11px;padding:3px 0;border-bottom:1px dotted #eee">'
                f'<span style="font-family:monospace;color:#991b1b;font-weight:700">{_escape(hs)}</span> '
                f'{_escape(name)} '
                f'<span style="color:#888">({_escape(str(conf_str))}, {_escape(tracking)})</span>'
                f'</div>'
            )

    # AI disagreements
    if cc_t3 > 0 or cc_t4 > 0:
        html += (
            f'<div style="font-size:12px;margin-top:8px">'
            f'<span style="font-weight:700;color:#92400e">חילוקי דעות AI:</span> '
        )
        if cc_t4 > 0:
            html += f'<span style="color:#991b1b">{cc_t4} disagreements (T4)</span> '
        if cc_t3 > 0:
            html += f'<span style="color:#92400e">{cc_t3} conflicts (T3)</span>'
        html += '</div>'

    # Failed extractions
    if failed_ext > 0:
        html += (
            f'<div style="font-size:12px;margin-top:8px">'
            f'<span style="font-weight:700;color:#991b1b">חילוצים שנכשלו:</span> '
            f'{failed_ext} extraction failures in last 24h'
            f'</div>'
        )

    # PC Agent pending
    if pc_pending > 0:
        html += (
            f'<div style="font-size:12px;margin-top:8px">'
            f'<span style="font-weight:700;color:#1e40af">PC Agent:</span> '
            f'{pc_pending} tasks pending execution'
            f'</div>'
        )

    return html


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
