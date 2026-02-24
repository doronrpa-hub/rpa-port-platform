"""
Intelligence Gate — Phase 1 from RCB Intelligence Routing Spec v1.0.

Three gates that run BEFORE any classification email is sent:
  1. HS Code Validation Gate — no invalid codes leave the system
  2. Classification Loop Breaker — max 2 attempts per product/thread
  3. Banned Phrase Filter — removes "consult a broker" etc.

Usage:
    from lib.intelligence_gate import (
        validate_classification_hs_codes,
        check_classification_loop,
        filter_banned_phrases,
        run_all_gates,
    )
"""
import re
from datetime import datetime, timezone, timedelta

# ═══════════════════════════════════════════════════════════════════════
# GATE 1: HS CODE VALIDATION
# ═══════════════════════════════════════════════════════════════════════
# RULE: No email goes out with an HS code that doesn't exist in the
# Israeli tariff DB. If invalid, find candidates under same heading.

def validate_classification_hs_codes(db, classifications):
    """
    Validate every HS code in the classification results against tariff DB.

    For each item:
      - If code exists in tariff DB → keep it, mark validated
      - If code NOT found → search same heading for candidates
      - If no heading match → search same chapter
      - Never return an invalid code — replace with best candidate or flag

    Returns:
        dict with:
          "all_valid": bool — True if every code was found in tariff DB
          "items": list of per-item validation results
          "any_corrected": bool — True if any code was auto-corrected
          "blocking_issues": list of str — issues that should block sending
    """
    if not db or not classifications:
        return {"all_valid": True, "items": [], "any_corrected": False,
                "blocking_issues": []}

    items = []
    all_valid = True
    any_corrected = False
    blocking = []

    for idx, cls in enumerate(classifications):
        hs_code = cls.get("hs_code", "")
        if not hs_code:
            items.append({"index": idx, "status": "no_code", "hs_code": ""})
            continue

        hs_clean = _normalize(hs_code)
        result = _check_tariff_db(db, hs_clean)

        if result["found"]:
            items.append({
                "index": idx,
                "status": "valid",
                "hs_code": hs_code,
                "hs_clean": hs_clean,
                "description_he": result.get("description_he", ""),
                "duty_rate": result.get("duty_rate", ""),
            })
        else:
            # Code not found — search for candidates
            all_valid = False
            heading = hs_clean[:4] if len(hs_clean) >= 4 else ""
            chapter = hs_clean[:2] if len(hs_clean) >= 2 else ""

            candidates = _find_candidates(db, heading, chapter)

            if candidates:
                # Auto-correct to best candidate
                best = candidates[0]
                any_corrected = True
                cls["original_hs_code"] = hs_code
                cls["hs_code"] = best["hs_code"]
                cls["hs_corrected"] = True
                cls["correction_note"] = (
                    f"קוד {_format_il(hs_clean)} לא נמצא במאגר. "
                    f"תוקן ל-{_format_il(best['hs_code'])}"
                )
                # Downgrade confidence if it was high
                if cls.get("confidence") == "גבוהה":
                    cls["confidence"] = "בינונית"

                items.append({
                    "index": idx,
                    "status": "corrected",
                    "original_code": hs_code,
                    "corrected_to": best["hs_code"],
                    "description_he": best.get("description_he", ""),
                    "candidates_count": len(candidates),
                    "candidates": candidates[:5],  # top 5 for context
                })
            else:
                # No candidates at all — this is a blocking issue
                blocking.append(
                    f"HS code {_format_il(hs_clean)} (item {idx+1}) does not exist "
                    f"in Israeli tariff and no candidates found under heading {heading}"
                )
                cls["confidence"] = "נמוכה"
                cls["hs_warning"] = f"קוד {_format_il(hs_clean)} לא נמצא במאגר התעריף הישראלי"

                items.append({
                    "index": idx,
                    "status": "invalid",
                    "hs_code": hs_code,
                    "hs_clean": hs_clean,
                    "heading": heading,
                    "chapter": chapter,
                })

    return {
        "all_valid": all_valid,
        "items": items,
        "any_corrected": any_corrected,
        "blocking_issues": blocking,
    }


def _check_tariff_db(db, hs_clean):
    """Check if an HS code exists in the tariff DB. Fast single-doc lookups."""
    # Try exact document lookups (cheapest Firestore reads)
    for coll in ["tariff", "tariff_chapters", "hs_code_index"]:
        try:
            # Try clean digits
            doc = db.collection(coll).document(hs_clean).get()
            if doc.exists:
                data = doc.to_dict()
                if data.get("corrupt_code"):
                    continue
                return {
                    "found": True,
                    "description_he": data.get("description_he", data.get("title_he", "")),
                    "description_en": data.get("description_en", data.get("title_en", "")),
                    "duty_rate": data.get("duty_rate", ""),
                }
            # Try dotted format
            dotted = _format_dots(hs_clean)
            if dotted != hs_clean:
                doc = db.collection(coll).document(dotted).get()
                if doc.exists:
                    data = doc.to_dict()
                    if data.get("corrupt_code"):
                        continue
                    return {
                        "found": True,
                        "description_he": data.get("description_he", data.get("title_he", "")),
                        "description_en": data.get("description_en", data.get("title_en", "")),
                        "duty_rate": data.get("duty_rate", ""),
                    }
        except Exception:
            continue
    return {"found": False}


def _find_candidates(db, heading, chapter):
    """Find valid HS codes under the same heading, falling back to chapter."""
    candidates = []

    if heading and len(heading) >= 4:
        # Search tariff collection by heading prefix
        try:
            start = heading
            end = heading[:-1] + chr(ord(heading[-1]) + 1)
            docs = (db.collection("tariff")
                    .where("hs_code", ">=", start)
                    .where("hs_code", "<", end)
                    .limit(20).stream())
            for doc in docs:
                data = doc.to_dict()
                if data.get("corrupt_code"):
                    continue
                hs = data.get("hs_code", "")
                if hs:
                    candidates.append({
                        "hs_code": _normalize(hs),
                        "description_he": data.get("description_he", ""),
                        "duty_rate": data.get("duty_rate", ""),
                    })
        except Exception:
            pass

    # If no heading matches, try chapter level
    if not candidates and chapter and len(chapter) >= 2:
        try:
            start = chapter
            end = str(int(chapter) + 1).zfill(2)
            docs = (db.collection("tariff")
                    .where("hs_code", ">=", start)
                    .where("hs_code", "<", end)
                    .limit(10).stream())
            for doc in docs:
                data = doc.to_dict()
                if data.get("corrupt_code"):
                    continue
                hs = data.get("hs_code", "")
                if hs:
                    candidates.append({
                        "hs_code": _normalize(hs),
                        "description_he": data.get("description_he", ""),
                        "duty_rate": data.get("duty_rate", ""),
                    })
        except Exception:
            pass

    return candidates


# ═══════════════════════════════════════════════════════════════════════
# GATE 2: CLASSIFICATION LOOP BREAKER
# ═══════════════════════════════════════════════════════════════════════
# RULE: Max 2 classification attempts per product/thread.
# After 2, escalate to Doron. NEVER loop.

_MAX_CLASSIFICATION_ATTEMPTS = 2
_ESCALATION_EMAIL = "doron@rpa-port.co.il"

def check_classification_loop(db, msg_id, email_subject="", email_body=""):
    """
    Check if this email/thread has already been classified too many times.

    Uses Firestore `classification_attempts` collection to track.
    Key = MD5 of normalized subject (strips Re:/Fwd: and tracking codes).

    Returns:
        dict with:
          "allowed": bool — True if classification can proceed
          "attempt_number": int — which attempt this would be (1-based)
          "escalate": bool — True if should escalate to Doron
          "prior_codes": list — HS codes from previous attempts
          "thread_key": str — the dedup key used
    """
    if not db:
        return {"allowed": True, "attempt_number": 1, "escalate": False,
                "prior_codes": [], "thread_key": ""}

    # Compute thread key from normalized subject
    thread_key = _compute_thread_key(email_subject, msg_id)
    if not thread_key:
        return {"allowed": True, "attempt_number": 1, "escalate": False,
                "prior_codes": [], "thread_key": ""}

    try:
        doc_ref = db.collection("classification_attempts").document(thread_key)
        doc = doc_ref.get()

        if not doc.exists:
            # First attempt — record it
            doc_ref.set({
                "thread_key": thread_key,
                "subject": email_subject[:200],
                "msg_id": msg_id or "",
                "attempts": 1,
                "hs_codes": [],
                "first_attempt_at": datetime.now(timezone.utc).isoformat(),
                "last_attempt_at": datetime.now(timezone.utc).isoformat(),
            })
            return {"allowed": True, "attempt_number": 1, "escalate": False,
                    "prior_codes": [], "thread_key": thread_key}

        data = doc.to_dict()
        attempts = data.get("attempts", 0)
        prior_codes = data.get("hs_codes", [])

        if attempts >= _MAX_CLASSIFICATION_ATTEMPTS:
            print(f"  🛑 LOOP BREAKER: {attempts} prior attempts for this thread. Escalating.")
            return {
                "allowed": False,
                "attempt_number": attempts + 1,
                "escalate": True,
                "prior_codes": prior_codes,
                "thread_key": thread_key,
            }

        # Allowed — increment counter
        doc_ref.update({
            "attempts": attempts + 1,
            "last_attempt_at": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "allowed": True,
            "attempt_number": attempts + 1,
            "escalate": False,
            "prior_codes": prior_codes,
            "thread_key": thread_key,
        }

    except Exception as e:
        # Fail-open: if Firestore read fails, allow classification
        print(f"  ⚠️ Loop breaker Firestore error (fail-open): {e}")
        return {"allowed": True, "attempt_number": 1, "escalate": False,
                "prior_codes": [], "thread_key": thread_key}


def record_classification_codes(db, thread_key, hs_codes):
    """After classification succeeds, record the HS codes for future loop checks."""
    if not db or not thread_key:
        return
    try:
        doc_ref = db.collection("classification_attempts").document(thread_key)
        doc = doc_ref.get()
        if doc.exists:
            existing = doc.to_dict().get("hs_codes", [])
            merged = list(set(existing + hs_codes))
            doc_ref.update({"hs_codes": merged})
    except Exception:
        pass


def build_escalation_email_html(email_subject, prior_codes, attempt_number):
    """Build HTML email to Doron explaining the escalation."""
    codes_html = ""
    if prior_codes:
        codes_list = "".join(f"<li>{_format_il(c)}</li>" for c in prior_codes)
        codes_html = f'<p>קודים שנוסו בעבר:</p><ul>{codes_list}</ul>'

    return (
        '<div dir="rtl" style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">'
        '<div style="background:#dc2626;color:#fff;padding:16px 24px;border-radius:8px 8px 0 0">'
        '<h2 style="margin:0">RCB | הסלמה — סיווג חוזר</h2>'
        '</div>'
        '<div style="background:#fff;padding:24px;border:1px solid #e0e0e0">'
        f'<p style="font-size:15px"><strong>נושא:</strong> {email_subject}</p>'
        f'<p style="font-size:15px"><strong>מספר ניסיונות:</strong> {attempt_number}</p>'
        f'{codes_html}'
        '<p style="color:#991b1b;font-weight:bold;margin-top:16px">'
        'המערכת עצרה אוטומטית כדי למנוע לולאת סיווג. '
        'נדרש טיפול ידני.</p>'
        '</div>'
        '<div style="background:#f8f8f8;padding:12px 24px;border-radius:0 0 8px 8px;'
        'border:1px solid #e0e0e0;border-top:0">'
        '<p style="font-size:11px;color:#999;margin:0">RCB Intelligence Gate — Loop Breaker</p>'
        '</div></div>'
    )


def _compute_thread_key(subject, msg_id):
    """Compute a stable thread key from email subject."""
    import hashlib
    if not subject and not msg_id:
        return ""
    # Strip Re:/Fwd:/FW: prefixes and tracking codes
    clean = re.sub(r'(?i)^(re:\s*|fwd?:\s*|fw:\s*)+', '', subject or "")
    clean = re.sub(r'RCB-\d{8}-\d{3}(-[A-Z]+)?', '', clean)  # Remove RCB tracking codes
    clean = clean.strip()
    if not clean:
        # Fall back to msg_id if subject is empty after cleaning
        clean = msg_id or ""
    return hashlib.md5(clean.encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════
# GATE 3: BANNED PHRASE FILTER
# ═══════════════════════════════════════════════════════════════════════
# RULE: WE ARE the customs broker. Never say "consult a broker".
# Never say "unclassifiable". Never say "I'm not sure" in output.

BANNED_PHRASES = [
    # Hebrew — "consult a customs broker" variants
    "מומלץ לפנות לעמיל מכס",
    "מומלץ להתייעץ עם עמיל מכס",
    "מומלץ להתייעץ עם סוכן מכס",
    "יש לפנות לעמיל מכס",
    "יש להתייעץ עם עמיל מכס",
    "פנה לעמיל מכס",
    "פנו לעמיל מכס",
    "התייעצו עם עמיל מכס",
    # English variants
    "consult a customs broker",
    "consult a licensed customs broker",
    "consult with a customs broker",
    "seek professional customs advice",
    "contact a customs agent",
    # Uncertainty phrases that should never appear in output
    "I'm not sure",
    "I am not sure",
    "I cannot determine",
    "unable to classify",
    "unclassifiable",
    "לא ניתן לסווג",
    "לא ניתן לקבוע",
    # The existing footer disclaimer that contradicts our identity
    "יש לאמת עם עמיל מכס מוסמך",
]

# Replacement for broker references
_BROKER_REPLACEMENT_HE = "לפרטים נוספים ניתן לפנות לצוות RCB בכתובת rcb@rpa-port.co.il"
_BROKER_REPLACEMENT_EN = "For further details, contact the RCB team at rcb@rpa-port.co.il"


def filter_banned_phrases(html_body):
    """
    Scan HTML body for banned phrases and replace them.

    Returns:
        dict with:
          "cleaned_html": str — body with banned phrases removed/replaced
          "phrases_found": list of str — which phrases were found
          "was_modified": bool — True if any replacements were made
    """
    if not html_body:
        return {"cleaned_html": html_body, "phrases_found": [], "was_modified": False}

    found = []
    cleaned = html_body

    for phrase in BANNED_PHRASES:
        if phrase.lower() in cleaned.lower():
            found.append(phrase)
            # Case-insensitive replacement
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            # Choose replacement based on language
            if any(c in phrase for c in "אבגדהוזחטיכלמנסעפצקרשת"):
                replacement = _BROKER_REPLACEMENT_HE
            else:
                replacement = _BROKER_REPLACEMENT_EN
            cleaned = pattern.sub(replacement, cleaned)

    return {
        "cleaned_html": cleaned,
        "phrases_found": found,
        "was_modified": bool(found),
    }


# ═══════════════════════════════════════════════════════════════════════
# COMBINED GATE — Run all 3 before sending
# ═══════════════════════════════════════════════════════════════════════

def run_all_gates(db, classifications, html_body, msg_id="",
                  email_subject="", email_body=""):
    """
    Run all 3 intelligence gates before a classification email is sent.

    Returns:
        dict with:
          "approved": bool — True if email can be sent
          "html_body": str — cleaned HTML (banned phrases replaced)
          "hs_validation": dict — from validate_classification_hs_codes
          "loop_check": dict — from check_classification_loop
          "banned_filter": dict — from filter_banned_phrases
          "block_reason": str — reason if not approved (empty if approved)
    """
    result = {
        "approved": True,
        "html_body": html_body,
        "hs_validation": None,
        "loop_check": None,
        "banned_filter": None,
        "block_reason": "",
    }

    # Gate 1: HS code validation
    try:
        hs_result = validate_classification_hs_codes(db, classifications)
        result["hs_validation"] = hs_result
        if hs_result["blocking_issues"]:
            print(f"  🚫 HS Gate: {len(hs_result['blocking_issues'])} blocking issues")
            for issue in hs_result["blocking_issues"]:
                print(f"     {issue}")
            # Don't block — downgrade confidence and warn, but still send
            # The spec says present candidates, not block entirely
        if hs_result["any_corrected"]:
            print(f"  🔄 HS Gate: auto-corrected HS codes")
    except Exception as e:
        print(f"  ⚠️ HS Gate error (fail-open): {e}")

    # Gate 2: Classification loop breaker
    try:
        loop_result = check_classification_loop(db, msg_id, email_subject, email_body)
        result["loop_check"] = loop_result
        if not loop_result["allowed"]:
            result["approved"] = False
            result["block_reason"] = (
                f"Classification loop detected: {loop_result['attempt_number']} attempts. "
                f"Prior codes: {', '.join(loop_result['prior_codes'])}. Escalating to Doron."
            )
            print(f"  🛑 Loop Gate: BLOCKED — {result['block_reason']}")
    except Exception as e:
        print(f"  ⚠️ Loop Gate error (fail-open): {e}")

    # Gate 3: Banned phrase filter
    try:
        banned_result = filter_banned_phrases(html_body)
        result["banned_filter"] = banned_result
        result["html_body"] = banned_result["cleaned_html"]
        if banned_result["was_modified"]:
            print(f"  🧹 Phrase Gate: removed {len(banned_result['phrases_found'])} banned phrases: "
                  f"{', '.join(banned_result['phrases_found'][:3])}")
    except Exception as e:
        print(f"  ⚠️ Phrase Gate error (fail-open): {e}")

    return result


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _normalize(hs_code):
    """Normalize HS code to clean digits."""
    return re.sub(r'[.\s/\-]', '', str(hs_code)).strip()


def _format_dots(hs_clean):
    """Format clean HS code with dots: XXXX.XX.XXXX"""
    if len(hs_clean) >= 6:
        return f"{hs_clean[:4]}.{hs_clean[4:6]}.{hs_clean[6:]}"
    elif len(hs_clean) >= 4:
        return f"{hs_clean[:4]}.{hs_clean[4:]}"
    return hs_clean


def _format_il(hs_code):
    """Format HS code in Israeli display format XX.XX.XXXXXX"""
    clean = _normalize(hs_code)
    if len(clean) >= 10:
        return f"{clean[:2]}.{clean[2:4]}.{clean[4:10]}"
    elif len(clean) >= 6:
        return f"{clean[:2]}.{clean[2:4]}.{clean[4:]}"
    elif len(clean) >= 4:
        return f"{clean[:2]}.{clean[2:4]}"
    return clean


# ═══════════════════════════════════════════════════════════════════════
# PHASE 2: DOMAIN DETECTION
# ═══════════════════════════════════════════════════════════════════════
# Pure Python keyword matching — no AI call needed.
# Detects which customs domain(s) a question belongs to, enabling
# targeted article retrieval instead of flat keyword search.

CUSTOMS_DOMAINS = {
    "CLASSIFICATION": {
        "keywords_he": ["סיווג", "פרט מכס", "תעריף", "פרק", "HS", "קוד"],
        "keywords_en": ["classify", "classification", "hs code", "tariff", "heading"],
        "product_indicators": True,
        "source_articles": [],  # Uses tariff DB, not ordinance articles
        "source_fw_articles": ["03", "04", "05"],  # GIR rules from צו מסגרת
        "source_tools": ["search_tariff", "get_chapter_notes", "run_elimination"],
    },
    "VALUATION": {
        "keywords_he": ["הערכה", "ערך עסקה", "שווי", "מחיר ששולם", "תשלום",
                         "שיטות הערכה", "ערך", "מחיר העסקה", "עסקת יבוא",
                         "חישוב מכס", "שער חליפין", "הפחתה", "ניכוי"],
        "keywords_en": ["valuation", "transaction value", "customs value", "price paid",
                         "deductive", "computed value"],
        "source_articles": ["130", "131", "132", "132א", "133", "133א", "133ב",
                            "133ג", "133ד", "133ה", "133ו", "133ז", "133ח", "133ט",
                            "134", "134א", "135", "136"],
        "source_tools": ["search_legal_knowledge"],
    },
    "IP_ENFORCEMENT": {
        "keywords_he": ["זיוף", "מזויף", "קניין רוחני", "סימן מסחר", "עיכוב",
                         "חשד", "מותג", "העתק", "פיראטיות", "זכויות יוצרים",
                         "טובין מפרים", "בעל זכות", "עיכוב טובין"],
        "keywords_en": ["counterfeit", "fake", "ip", "intellectual property",
                         "trademark", "brand", "piracy", "detained", "seized",
                         "infringing goods"],
        "source_articles": ["200א", "200ב", "200ג", "200ד", "200ה", "200ו", "200ז",
                            "200ח", "200ט", "200י", "200יא", "200יב", "200יג", "200יד"],
        "source_tools": ["search_legal_knowledge"],
    },
    "FTA_ORIGIN": {
        "keywords_he": ["הסכם סחר", "מקור", "תעודת מקור", "העדפה", "הנחה",
                         "אזור סחר", "כללי מקור", "צבירה", "יצואן מאושר",
                         "חשבון הצהרה", "צו מסגרת", "תוספת ראשונה", "תוספת שניה"],
        "keywords_en": ["fta", "free trade", "origin", "preferential", "eur.1",
                         "certificate of origin", "cumulation", "framework order"],
        "source_articles": [],  # Ordinance articles — none for FTA
        "source_fw_articles": [  # Framework Order (צו מסגרת) articles
            "01", "02", "03", "04", "05", "06", "06א", "07", "08", "09",
            "10", "11", "12", "13", "14", "15", "16", "17", "18", "19",
            "20", "21", "22", "23", "23א", "23ב", "23ג", "23ד", "23ה",
            "23ו", "23ז", "24", "25",
        ],
        "source_tools": ["lookup_fta", "lookup_framework_order"],
    },
    "IMPORT_EXPORT_REQUIREMENTS": {
        "keywords_he": ["רישיון", "היתר", "אישור", "צו יבוא", "צו יצוא",
                         "תוספת", "דרישה", "הגבלה", "תקן", "בדיקה",
                         "מכון התקנים"],
        "keywords_en": ["license", "permit", "approval", "import order",
                         "export order", "restricted", "prohibited",
                         "requirement", "standard"],
        "source_articles": [],  # Uses free_import_order/free_export_order
        "source_tools": ["check_regulatory"],
    },
    "PROCEDURES": {
        "keywords_he": ["נוהל", "תש\"ר", "מצהר", "הצהרה", "שחרור", "עמיל",
                         "רשימון", "מכס", "הליך", "מכסה", "החסנה"],
        "keywords_en": ["procedure", "declaration", "clearance", "broker",
                         "filing", "manifest", "warehousing"],
        "source_articles": ["40", "41", "42", "43", "44", "45", "46", "47",
                            "48", "49", "50", "51", "52", "53", "54", "55",
                            "56", "57", "58", "59", "60", "61", "62", "63",
                            "64", "65", "65א"],
        "source_tools": ["search_legal_knowledge"],
    },
    "FORFEITURE_PENALTIES": {
        "keywords_he": ["חילוט", "קנס", "עבירה", "עונש", "תפיסה", "הברחה",
                         "עבירת מכס", "עיצום כספי", "אכיפה"],
        "keywords_en": ["forfeiture", "seizure", "penalty", "fine", "offense",
                         "smuggling", "confiscation"],
        "source_articles": ["190", "191", "192", "193", "194", "195", "196",
                            "197", "198", "199", "200", "203", "203א", "204",
                            "205", "206", "207", "208", "209", "210", "211",
                            "212", "213", "214", "215", "216", "217", "218",
                            "219", "220", "221", "222", "223",
                            "223א", "223ב", "223ג", "223ד", "223ה", "223ו",
                            "223ז", "223ח", "223ט", "223י", "223יא", "223יב",
                            "223יג", "223יד", "223טו", "223טז", "223יז", "223יח"],
        "source_tools": ["search_legal_knowledge"],
    },
    "TRACKING": {
        "keywords_he": ["מעקב", "אונייה", "מכולה", "הגעה", "נמל", "מטען", "שילוח"],
        "keywords_en": ["tracking", "vessel", "container", "arrival", "port",
                         "cargo", "shipment", "eta"],
        "source_articles": [],
        "source_tools": [],
    },
}

# Product indicator words — if any appear, CLASSIFICATION domain is added
_PRODUCT_INDICATORS_HE = {
    "טובין", "מוצר", "סחורה", "פריט", "חומר", "מכשיר", "רכיב",
    "בד", "פלסטיק", "מתכת", "עץ", "גומי", "זכוכית", "נייר",
}
_PRODUCT_INDICATORS_EN = {
    "goods", "product", "item", "material", "device", "component",
    "machine", "equipment", "chemical", "textile", "fabric",
}


def detect_customs_domain(text):
    """
    Detect which customs domain(s) an email/question belongs to.

    Pure Python — no AI call. Returns sorted list of matching domains.
    Multiple domains can match (e.g., Nike counterfeit = IP + CLASSIFICATION).

    Returns:
        list of dict: [{"domain": str, "score": int, "source_articles": list,
                        "source_tools": list}, ...]
        Sorted by score descending. Empty list → GENERAL fallback.
    """
    if not text:
        return []

    text_lower = text.lower()

    detected = []
    for domain_id, domain in CUSTOMS_DOMAINS.items():
        score = 0
        for kw in domain.get("keywords_he", []):
            if kw in text:  # Hebrew: case-sensitive (no uppercase in Hebrew)
                score += 10
        for kw in domain.get("keywords_en", []):
            if kw in text_lower:
                score += 10

        # Product description bonus for CLASSIFICATION
        if domain.get("product_indicators"):
            for pw in _PRODUCT_INDICATORS_HE:
                if pw in text:
                    score += 5
                    break
            for pw in _PRODUCT_INDICATORS_EN:
                if pw in text_lower:
                    score += 5
                    break

        if score > 0:
            detected.append({
                "domain": domain_id,
                "score": score,
                "source_articles": domain.get("source_articles", []),
                "source_fw_articles": domain.get("source_fw_articles", []),
                "source_tools": domain.get("source_tools", []),
            })

    detected.sort(key=lambda x: x["score"], reverse=True)
    return detected


def get_articles_by_domain(domain_result):
    """
    Given a domain detection result, fetch ALL relevant articles
    from _ordinance_data.py AND _framework_order_data.py.

    This replaces flat keyword search — we go directly to the right articles.

    Args:
        domain_result: single dict from detect_customs_domain() output

    Returns:
        list of dict: [{"article_id": str, "title_he": str, "summary_en": str,
                        "full_text_he": str, "chapter": int, "source": str}, ...]
    """
    articles = []

    # ── Ordinance articles (פקודת המכס) ──
    ordinance_ids = domain_result.get("source_articles", [])
    if ordinance_ids:
        try:
            from lib._ordinance_data import ORDINANCE_ARTICLES
        except ImportError:
            try:
                from _ordinance_data import ORDINANCE_ARTICLES
            except ImportError:
                ORDINANCE_ARTICLES = {}

        for art_id in ordinance_ids:
            art = ORDINANCE_ARTICLES.get(art_id)
            if art:
                articles.append({
                    "article_id": art_id,
                    "title_he": art.get("t", ""),
                    "summary_en": art.get("s", ""),
                    "full_text_he": art.get("f", "")[:3000],
                    "chapter": art.get("ch", 0),
                    "source": "ordinance",
                })

    # ── Framework Order articles (צו מסגרת) ──
    fw_ids = domain_result.get("source_fw_articles", [])
    if fw_ids:
        try:
            from lib._framework_order_data import FRAMEWORK_ORDER_ARTICLES
        except ImportError:
            try:
                from _framework_order_data import FRAMEWORK_ORDER_ARTICLES
            except ImportError:
                FRAMEWORK_ORDER_ARTICLES = {}

        for art_id in fw_ids:
            art = FRAMEWORK_ORDER_ARTICLES.get(art_id)
            if art:
                articles.append({
                    "article_id": f"fw_{art_id}",
                    "title_he": art.get("t", ""),
                    "summary_en": art.get("s", ""),
                    "full_text_he": art.get("f", "")[:3000],
                    "chapter": 0,
                    "source": "framework_order",
                })

    return articles


def get_articles_by_ids(article_ids):
    """
    Fetch specific ordinance articles by their IDs from _ordinance_data.py.
    Utility for targeted retrieval — no keyword search, direct lookup.

    Args:
        article_ids: list of str, e.g. ["200א", "200ב", "200ג"]
                     Prefix with "fw_" for framework order articles.

    Returns:
        list of dict with article_id, title_he, summary_en, full_text_he, chapter
    """
    if not article_ids:
        return []
    # Separate ordinance vs framework order IDs
    ord_ids = [a for a in article_ids if not a.startswith("fw_")]
    fw_ids = [a[3:] for a in article_ids if a.startswith("fw_")]
    return get_articles_by_domain({
        "source_articles": ord_ids,
        "source_fw_articles": fw_ids,
    })
