"""
RCB Smart Question Engine — Elimination-Based Clarification
=============================================================
When classification is ambiguous, generates professional customs broker
questions that reference specific HS codes, duty rates, and regulatory
implications — helping the user narrow down the correct classification.

No AI calls — pure logic from classification results.

A 22-year customs broker doesn't ask "what is this?" — they ask:
  "Is this an extruded aluminum profile (7604.29, 6% duty) or
   an assembled structural part (7610.10, 0% with EUR.1 from Turkey)?
   The distinction matters because structural parts require SII approval."

Functions:
1. analyze_ambiguity()       — detect when/why classification is ambiguous
2. generate_smart_questions() — build elimination-based questions
3. format_questions_he()     — format for Hebrew email
4. should_ask_questions()    — decide if questions are needed
"""

import re


# ═══════════════════════════════════════════════════════════════
#  AMBIGUITY DETECTION
# ═══════════════════════════════════════════════════════════════

# Confidence level mapping (Hebrew → numeric)
_CONF_MAP = {
    "גבוהה": 85,
    "high": 85,
    "בינונית": 60,
    "medium": 60,
    "נמוכה": 35,
    "low": 35,
}


def _get_numeric_confidence(classification):
    """Extract numeric confidence from a classification entry."""
    conf = classification.get("confidence", "")
    if isinstance(conf, (int, float)):
        return conf
    if isinstance(conf, str):
        return _CONF_MAP.get(conf.strip().lower(), _CONF_MAP.get(conf.strip(), 50))
    return 50


def _get_chapter(hs_code):
    """Extract 2-digit chapter from HS code."""
    clean = str(hs_code).replace(".", "").replace(" ", "").replace("/", "")
    return clean[:2].zfill(2) if len(clean) >= 2 else ""


def analyze_ambiguity(classifications, intelligence_results=None,
                      free_import_results=None, ministry_routing=None):
    """
    Analyze classification results for ambiguity.

    Returns dict with:
      is_ambiguous: bool
      reason: str
      competing_codes: list of {hs_code, confidence, description, ...}
      chapter_conflict: bool (different chapters = very different cargo types)
      duty_spread: float (max duty difference between candidates)
      regulatory_divergence: bool (different ministry requirements)
    """
    if not classifications:
        return {"is_ambiguous": False, "reason": "no_classifications"}

    # Single classification with high confidence → not ambiguous
    if len(classifications) == 1:
        conf = _get_numeric_confidence(classifications[0])
        if conf >= 70:
            return {"is_ambiguous": False, "reason": "single_high_confidence"}
        return {
            "is_ambiguous": True,
            "reason": "single_low_confidence",
            "competing_codes": classifications,
            "chapter_conflict": False,
            "duty_spread": 0,
            "regulatory_divergence": False,
        }

    # Multiple classifications — check confidence gap
    sorted_by_conf = sorted(classifications,
                            key=lambda c: _get_numeric_confidence(c), reverse=True)
    top = sorted_by_conf[0]
    runner_up = sorted_by_conf[1]
    top_conf = _get_numeric_confidence(top)
    runner_conf = _get_numeric_confidence(runner_up)
    gap = top_conf - runner_conf

    # If top candidate is clearly dominant, not ambiguous
    if top_conf >= 80 and gap >= 25:
        return {"is_ambiguous": False, "reason": "clear_winner"}

    # It's ambiguous — analyze the competing codes
    competing = sorted_by_conf[:4]  # Top 4 candidates

    # Check if different chapters (very different cargo types)
    chapters = set(_get_chapter(c.get("hs_code", "")) for c in competing)
    chapter_conflict = len(chapters) > 1

    # Check duty rate spread
    duty_rates = []
    for c in competing:
        rate_str = c.get("duty_rate", "")
        rate_match = re.search(r'(\d+(?:\.\d+)?)\s*%', str(rate_str))
        if rate_match:
            duty_rates.append(float(rate_match.group(1)))
    duty_spread = (max(duty_rates) - min(duty_rates)) if len(duty_rates) >= 2 else 0

    # Check regulatory divergence (different ministries for different codes)
    regulatory_divergence = False
    if ministry_routing and len(chapters) > 1:
        ministry_sets = []
        for c in competing:
            hs = c.get("hs_code", "")
            routing = ministry_routing.get(hs, {})
            ministries = set(m.get("name_he", "") for m in routing.get("ministries", []))
            if ministries:
                ministry_sets.append(ministries)
        if len(ministry_sets) >= 2 and ministry_sets[0] != ministry_sets[1]:
            regulatory_divergence = True

    reason = "multiple_candidates"
    if chapter_conflict:
        reason = "chapter_conflict"
    elif gap < 10:
        reason = "near_equal_confidence"
    elif top_conf < 60:
        reason = "all_low_confidence"

    return {
        "is_ambiguous": True,
        "reason": reason,
        "competing_codes": competing,
        "chapter_conflict": chapter_conflict,
        "duty_spread": duty_spread,
        "regulatory_divergence": regulatory_divergence,
        "top_confidence": top_conf,
        "confidence_gap": gap,
    }


# ═══════════════════════════════════════════════════════════════
#  QUESTION GENERATION
# ═══════════════════════════════════════════════════════════════

# Distinguishing features by HS chapter pairs
_DISTINCTION_HINTS = {
    # Machinery vs. electrical
    ("84", "85"): {
        "question_he": "האם המוצר מכני (מנוע, משאבה, מכונה) או אלקטרוני (מעגל, רכיב, מסך)?",
        "hint_he": "פרק 84 = מכונות ומכשירים מכניים. פרק 85 = מכשירים חשמליים ואלקטרוניים.",
    },
    # Plastics vs. articles thereof
    ("39", "40"): {
        "question_he": "האם זה פלסטיק גולמי/חצי מוגמר או מוצר מוגמר מפלסטיק/גומי?",
        "hint_he": "פרק 39 = פלסטיק ומוצריו. פרק 40 = גומי ומוצריו.",
    },
    # Iron/steel vs. aluminum
    ("72", "76"): {
        "question_he": "האם המוצר עשוי ברזל/פלדה או אלומיניום?",
        "hint_he": "חומר הגלם משנה את הסיווג ושיעור המכס.",
    },
    # Textiles
    ("61", "62"): {
        "question_he": "האם הבגד סרוג (knitted) או ארוג (woven)?",
        "hint_he": "פרק 61 = סרוגים. פרק 62 = ארוגים. הפרש מכס משמעותי.",
    },
    # Food preparations
    ("19", "21"): {
        "question_he": "האם מדובר במוצר דגנים/מאפה או בתכשיר מזון מעורב?",
        "hint_he": "פרק 19 = דגנים ומאפים. פרק 21 = תכשירי מזון שונים.",
    },
    # Vehicles vs. parts
    ("87", "84"): {
        "question_he": "האם מדובר ברכב שלם או בחלק/מכלול מכני?",
        "hint_he": "רכב שלם = פרק 87 (היטל רכישה). חלק בודד = ייתכן פרק 84.",
    },
    # Medical vs. optical
    ("90", "85"): {
        "question_he": "האם המכשיר רפואי (אושר AMAR) או ציוד אלקטרוני כללי?",
        "hint_he": "מכשיר רפואי = פרק 90 (דרוש אישור אגף מכשור רפואי). אלקטרוניקה = פרק 85.",
    },
}


def _build_code_comparison_he(c1, c2, free_import_results=None, ministry_routing=None):
    """Build a Hebrew comparison between two competing HS codes."""
    hs1 = c1.get("hs_code", "?")
    hs2 = c2.get("hs_code", "?")
    desc1 = c1.get("description", c1.get("item", ""))[:80]
    desc2 = c2.get("description", c2.get("item", ""))[:80]
    duty1 = c1.get("duty_rate", "לא ידוע")
    duty2 = c2.get("duty_rate", "לא ידוע")

    lines = []
    lines.append(f"אפשרות א': {hs1}")
    if desc1:
        lines.append(f"  תיאור: {desc1}")
    lines.append(f"  מכס: {duty1}")

    # Add regulatory info if available
    if ministry_routing:
        routing1 = ministry_routing.get(hs1, {})
        if routing1.get("ministries"):
            names = ", ".join(m.get("name_he", "") for m in routing1["ministries"][:2])
            lines.append(f"  דרוש אישור: {names}")

    if free_import_results:
        fio1 = free_import_results.get(hs1, {})
        if fio1.get("authorities"):
            auth_names = ", ".join(a.get("name", "") for a in fio1["authorities"][:2])
            lines.append(f"  רשות מאשרת: {auth_names}")

    lines.append("")
    lines.append(f"אפשרות ב': {hs2}")
    if desc2:
        lines.append(f"  תיאור: {desc2}")
    lines.append(f"  מכס: {duty2}")

    if ministry_routing:
        routing2 = ministry_routing.get(hs2, {})
        if routing2.get("ministries"):
            names = ", ".join(m.get("name_he", "") for m in routing2["ministries"][:2])
            lines.append(f"  דרוש אישור: {names}")

    if free_import_results:
        fio2 = free_import_results.get(hs2, {})
        if fio2.get("authorities"):
            auth_names = ", ".join(a.get("name", "") for a in fio2["authorities"][:2])
            lines.append(f"  רשות מאשרת: {auth_names}")

    return "\n".join(lines)


def generate_smart_questions(ambiguity, classifications,
                             invoice_data=None,
                             free_import_results=None,
                             ministry_routing=None,
                             parsed_documents=None):
    """
    Generate elimination-based questions from ambiguity analysis.

    Returns list of question dicts:
      [{
        question_he: str,
        context_he: str (why this matters),
        options: [{label_he, hs_code, duty_rate, implication_he}],
        priority: int (1=critical, 2=important, 3=nice-to-have),
        category: str (classification|regulatory|document|origin),
      }]
    """
    if not ambiguity.get("is_ambiguous"):
        return []

    questions = []
    competing = ambiguity.get("competing_codes", [])

    # ── Q1: HS code elimination (the core question) ──
    if len(competing) >= 2:
        c1 = competing[0]
        c2 = competing[1]
        ch1 = _get_chapter(c1.get("hs_code", ""))
        ch2 = _get_chapter(c2.get("hs_code", ""))

        # Check if we have a known distinction hint
        pair = tuple(sorted([ch1, ch2]))
        hint = _DISTINCTION_HINTS.get(pair)

        if hint:
            question_text = hint["question_he"]
            context_text = hint["hint_he"]
        elif ambiguity.get("chapter_conflict"):
            question_text = f"המוצר שייך לפרק {ch1} ({c1.get('description', '')[:40]}) או לפרק {ch2} ({c2.get('description', '')[:40]})?"
            context_text = "פרקים שונים = דרישות רגולטוריות שונות לחלוטין."
        else:
            # Same chapter, different subheadings
            question_text = f"מהו התיאור המדויק של המוצר? יש שני סיווגים אפשריים:"
            context_text = _build_code_comparison_he(c1, c2, free_import_results, ministry_routing)

        options = []
        for c in competing[:3]:
            duty = c.get("duty_rate", "לא ידוע")
            options.append({
                "label_he": f"{c.get('hs_code', '?')} — {c.get('description', '')[:60]}",
                "hs_code": c.get("hs_code", ""),
                "duty_rate": duty,
                "implication_he": _get_implication(c, free_import_results, ministry_routing),
            })

        questions.append({
            "question_he": question_text,
            "context_he": context_text,
            "options": options,
            "priority": 1,
            "category": "classification",
        })

    # ── Q2: Material/composition (if duty spread is significant) ──
    if ambiguity.get("duty_spread", 0) >= 4:
        low_duty = min(competing[:3], key=lambda c: _parse_duty(c.get("duty_rate", "")))
        high_duty = max(competing[:3], key=lambda c: _parse_duty(c.get("duty_rate", "")))
        low_rate = low_duty.get("duty_rate", "?")
        high_rate = high_duty.get("duty_rate", "?")

        questions.append({
            "question_he": f"הפרש המכס משמעותי: {low_rate} לעומת {high_rate}. מהו החומר העיקרי של המוצר?",
            "context_he": f"חומר הגלם העיקרי קובע את הסיווג במקרה זה.",
            "options": [],
            "priority": 2,
            "category": "classification",
        })

    # ── Q3: Missing origin (needed for FTA calculation) ──
    origin = ""
    if invoice_data:
        items = invoice_data.get("items", [])
        if items:
            origin = items[0].get("origin_country", "")
    if not origin:
        questions.append({
            "question_he": "מהי ארץ המקור של הסחורה?",
            "context_he": "ארץ המקור קובעת זכאות להסכם סחר חופשי (FTA) ושיעור מכס מופחת.",
            "options": [
                {"label_he": "האיחוד האירופי (EUR.1 → 0% על רוב התעשייתי)", "hs_code": "", "duty_rate": "", "implication_he": ""},
                {"label_he": "טורקיה (EUR.1 → 0% על רוב התעשייתי)", "hs_code": "", "duty_rate": "", "implication_he": ""},
                {"label_he": "סין (ללא הסכם — מכס מלא)", "hs_code": "", "duty_rate": "", "implication_he": ""},
            ],
            "priority": 2,
            "category": "origin",
        })

    # ── Q4: Missing critical documents ──
    if parsed_documents:
        has_invoice = any(pd.get("doc_type") == "commercial_invoice" for pd in parsed_documents)
        has_packing = any(pd.get("doc_type") == "packing_list" for pd in parsed_documents)
        has_transport = any(pd.get("doc_type") in ("bill_of_lading", "air_waybill") for pd in parsed_documents)

        missing = []
        if not has_invoice:
            missing.append("חשבונית מסחרית")
        if not has_packing:
            missing.append("רשימת אריזה")
        if not has_transport:
            missing.append("שטר מטען (B/L או AWB)")

        if missing:
            questions.append({
                "question_he": f"מסמכים חסרים: {', '.join(missing)}. האם ניתן לצרף?",
                "context_he": "מסמכים אלה נדרשים לשחרור המטען מהמכס.",
                "options": [],
                "priority": 1 if not has_invoice else 2,
                "category": "document",
            })

    # ── Q5: Regulatory divergence (different ministries) ──
    if ambiguity.get("regulatory_divergence") and ministry_routing:
        ministries_per_code = {}
        for c in competing[:2]:
            hs = c.get("hs_code", "")
            routing = ministry_routing.get(hs, {})
            mins = [m.get("name_he", "") for m in routing.get("ministries", [])]
            if mins:
                ministries_per_code[hs] = mins

        if len(ministries_per_code) >= 2:
            codes = list(ministries_per_code.keys())
            questions.append({
                "question_he": "הסיווג משפיע על הרשות המאשרת:",
                "context_he": (
                    f"{codes[0]}: נדרש אישור {', '.join(ministries_per_code[codes[0]][:2])}\n"
                    f"{codes[1]}: נדרש אישור {', '.join(ministries_per_code[codes[1]][:2])}\n"
                    "בחירת הסיווג הנכון קריטית — אישור מהרשות הלא נכונה לא ישחרר את המטען."
                ),
                "options": [],
                "priority": 1,
                "category": "regulatory",
            })

    # Sort by priority
    questions.sort(key=lambda q: q["priority"])
    return questions


def _get_implication(classification, free_import_results=None, ministry_routing=None):
    """Build a short Hebrew implication string for a classification option."""
    parts = []
    hs = classification.get("hs_code", "")

    if free_import_results:
        fio = free_import_results.get(hs, {})
        if fio.get("found"):
            reqs = []
            for item in fio.get("items", []):
                for req in item.get("legal_requirements", []):
                    name = req.get("name", "")
                    if name and name not in reqs:
                        reqs.append(name)
            if reqs:
                parts.append(f"דרישות: {', '.join(reqs[:2])}")

    if ministry_routing:
        routing = ministry_routing.get(hs, {})
        risk = routing.get("risk_level", "")
        if risk in ("high", "critical"):
            parts.append(f"סיכון: {'גבוה' if risk == 'high' else 'קריטי'}")

    return ". ".join(parts) if parts else ""


def _parse_duty(rate_str):
    """Parse duty rate string to float for comparison."""
    m = re.search(r'(\d+(?:\.\d+)?)', str(rate_str))
    return float(m.group(1)) if m else 0.0


# ═══════════════════════════════════════════════════════════════
#  DECISION: SHOULD WE ASK QUESTIONS?
# ═══════════════════════════════════════════════════════════════

def should_ask_questions(classifications, intelligence_results=None,
                         free_import_results=None, ministry_routing=None):
    """
    Decide whether smart questions should be generated and sent.

    Returns:
      (bool, ambiguity_dict)
    """
    ambiguity = analyze_ambiguity(
        classifications,
        intelligence_results=intelligence_results,
        free_import_results=free_import_results,
        ministry_routing=ministry_routing,
    )

    if not ambiguity.get("is_ambiguous"):
        return False, ambiguity

    # Always ask if chapter conflict or regulatory divergence
    if ambiguity.get("chapter_conflict") or ambiguity.get("regulatory_divergence"):
        return True, ambiguity

    # Ask if duty spread is significant (>= 4% difference)
    if ambiguity.get("duty_spread", 0) >= 4:
        return True, ambiguity

    # Ask if all candidates have low confidence
    if ambiguity.get("top_confidence", 100) < 60:
        return True, ambiguity

    # Ask if confidence gap is small (hard to pick a winner)
    if ambiguity.get("confidence_gap", 100) < 15:
        return True, ambiguity

    return False, ambiguity


# ═══════════════════════════════════════════════════════════════
#  FORMAT FOR EMAIL
# ═══════════════════════════════════════════════════════════════

def format_questions_he(questions, item_description=""):
    """
    Format questions as Hebrew text for email inclusion.

    Returns:
      str — formatted Hebrew text block
    """
    if not questions:
        return ""

    lines = []
    lines.append("❓ נדרש הבהרה לסיווג מדויק:")
    lines.append("")

    if item_description:
        lines.append(f"לגבי: {item_description[:100]}")
        lines.append("")

    for i, q in enumerate(questions, 1):
        lines.append(f"שאלה {i}: {q['question_he']}")

        if q.get("context_he"):
            lines.append(f"  {q['context_he']}")

        if q.get("options"):
            lines.append("")
            for j, opt in enumerate(q["options"], 1):
                label = opt.get("label_he", "")
                duty = opt.get("duty_rate", "")
                impl = opt.get("implication_he", "")
                line = f"  {j}. {label}"
                if duty:
                    line += f" (מכס: {duty})"
                lines.append(line)
                if impl:
                    lines.append(f"     → {impl}")

        lines.append("")

    lines.append("אנא השב/י כדי שנוכל להשלים את הסיווג המדויק.")
    return "\n".join(lines)


def format_questions_html(questions, item_description=""):
    """
    Format questions as styled HTML for email.

    Returns:
      str — HTML block (RTL, styled)
    """
    if not questions:
        return ""

    html_parts = []
    html_parts.append('<div dir="rtl" style="font-family:Arial,sans-serif;background:#fff8e1;border:2px solid #f9a825;border-radius:8px;padding:20px;margin:15px 0">')
    html_parts.append('<h3 style="color:#e65100;margin:0 0 10px">❓ נדרש הבהרה לסיווג מדויק</h3>')

    if item_description:
        html_parts.append(f'<p style="color:#555;margin:0 0 15px">לגבי: <strong>{_html_escape(item_description[:100])}</strong></p>')

    for i, q in enumerate(questions, 1):
        html_parts.append(f'<div style="margin:15px 0;padding:10px;background:#fff;border-radius:6px;border-right:4px solid #1e3a5f">')
        html_parts.append(f'<p style="margin:0 0 5px;font-weight:bold;color:#1e3a5f">שאלה {i}: {_html_escape(q["question_he"])}</p>')

        if q.get("context_he"):
            context_html = _html_escape(q["context_he"]).replace("\n", "<br>")
            html_parts.append(f'<p style="margin:5px 0;color:#666;font-size:13px">{context_html}</p>')

        if q.get("options"):
            html_parts.append('<table style="width:100%;margin-top:8px;border-collapse:collapse">')
            for j, opt in enumerate(q["options"], 1):
                bg = "#f5f5f5" if j % 2 == 0 else "#fff"
                label = _html_escape(opt.get("label_he", ""))
                duty = _html_escape(opt.get("duty_rate", ""))
                impl = _html_escape(opt.get("implication_he", ""))

                html_parts.append(f'<tr style="background:{bg}">')
                html_parts.append(f'<td style="padding:6px;font-weight:bold;width:30px">{j}.</td>')
                html_parts.append(f'<td style="padding:6px">{label}')
                if duty:
                    html_parts.append(f'<br><span style="color:#2e7d32;font-size:12px">מכס: {duty}</span>')
                if impl:
                    html_parts.append(f'<br><span style="color:#c62828;font-size:12px">→ {impl}</span>')
                html_parts.append('</td></tr>')
            html_parts.append('</table>')

        html_parts.append('</div>')

    html_parts.append('<p style="margin:15px 0 0;color:#1e3a5f;font-weight:bold">אנא השב/י כדי שנוכל להשלים את הסיווג המדויק.</p>')
    html_parts.append('</div>')

    return "\n".join(html_parts)


def _html_escape(text):
    """Basic HTML escaping."""
    if not text:
        return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
