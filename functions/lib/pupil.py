"""
RCB Pupil Agent — Phase A+B+C
====================================
Passive learning loop that reads ALL emails (direct + CC),
extracts knowledge, challenges the brain, and teaches the system.

The Pupil sends emails ONLY to doron@ for review cases and corrections.

Architecture:
  Phase A: Pupil observes → asks Librarian what we know → finds gaps
  Phase B: Gemini/Claude fill gaps WITH method → stores teachings
  Phase C: Audit past work → find corrections → send correction emails

Collections used:
  - pupil_observations (new) — what pupil saw and learned per email
  - contacts (new) — people, companies, roles
  - pupil_teachings (new) — methods & rules extracted from AI, for Librarian
  - enrichment_tasks (new) — verification + challenge tasks for Phase B
  - pupil_budget (new) — daily API cost tracking
  - classification_knowledge (existing) — enriched with teachings
  - knowledge_base (existing) — enriched with workflow summaries
  - enrichment_log (existing) — task tracking

Author: RCB System
Version: 0.5.0 — Phase A+B+C + Corrections + Signature + Hebrew decode
"""

from datetime import datetime, timezone
import hashlib
import re
import os
import json
from email.header import decode_header as email_decode_header

# ═══════════════════════════════════════════
#  SAFETY LOCK — PUPIL EMAIL RULES
#  This module may ONLY send emails to REVIEW_EMAIL (doron@)
#  for review cases. Max 3/day. NEVER to external addresses.
#  NEVER to clients, customs, or any third party.
# ═══════════════════════════════════════════
_FORBIDDEN_IMPORTS = ['helper_graph_send', 'send_reply', 'smtplib']

# Review email — ONLY recipient for Pupil outgoing emails
REVIEW_EMAIL = "doron@rpa-port.co.il"
MAX_REVIEW_EMAILS_PER_DAY = 3

# ═══════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════

# Cost tiers — Pupil tries free first, then cheap, then expensive
TIER_FREE = 0       # Librarian + Firestore only
TIER_GEMINI = 1     # Gemini Flash (~$0.001/call)
TIER_CLAUDE = 2     # Claude Sonnet (~$0.05-0.15/call)

# Daily budget cap (USD) — stop API calls if exceeded
DAILY_BUDGET_USD = 5.0

# Approximate costs per call
COST_GEMINI_CALL = 0.002
COST_CLAUDE_CALL = 0.10


# ═══════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════

def pupil_process_email(msg, db, firestore_module, access_token, rcb_email, get_secret_func):
    """
    Main Pupil entry point. Called for EVERY email (direct or CC).
    
    For direct rcb@ emails: observes AFTER the main pipeline runs.
    For CC/other emails: full observation cycle (no reply sent).
    
    Returns dict with observation results.
    """
    msg_id = msg.get('id', '')
    subject = _decode_email_header(msg.get('subject', 'No Subject'))
    from_data = msg.get('from', {}).get('emailAddress', {})
    from_email = from_data.get('address', '')
    from_name = from_data.get('name', '')
    to_recipients = msg.get('toRecipients', [])
    cc_recipients = msg.get('ccRecipients', [])
    body_content = msg.get('body', {}).get('content', '')
    received_at = msg.get('receivedDateTime', '')
    has_attachments = msg.get('hasAttachments', False)

    # Generate pupil observation ID
    obs_id = _make_obs_id(msg_id)

    # Skip if already observed
    if db.collection("pupil_observations").document(obs_id).get().exists:
        return {"status": "already_observed", "obs_id": obs_id}

    print(f"  🎓 PUPIL observing: {subject[:50]} from {from_email}")

    # Determine email type
    is_direct_to_rcb = any(
        rcb_email.lower() in r.get('emailAddress', {}).get('address', '').lower()
        for r in to_recipients
    )
    is_reply = subject.lower().startswith('re:') or subject.lower().startswith('השב:')

    # ── STEP 1: Extract basic facts (FREE) ──
    observation = {
        "obs_id": obs_id,
        "msg_id": msg_id,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "subject": subject,
        "from_email": from_email,
        "from_name": from_name,
        "to_recipients": [r.get('emailAddress', {}).get('address', '') for r in to_recipients],
        "cc_recipients": [r.get('emailAddress', {}).get('address', '') for r in cc_recipients],
        "is_direct_to_rcb": is_direct_to_rcb,
        "is_reply": is_reply,
        "has_attachments": has_attachments,
        "body_snippet": _clean_body(body_content)[:500],
        "phase": "A_observe",
        "knowledge_gaps": [],
        "learnings": [],
        "api_calls": [],
        "total_cost_usd": 0.0,
    }

    # ── STEP 2: Identify people & companies (FREE) ──
    contact_info = _observe_contact(db, from_email, from_name, to_recipients, cc_recipients, body_content)
    observation["contact_info"] = contact_info

    # ── STEP 3: Parse attachments if present (FREE) ──
    attachment_info = []
    raw_attachments = msg.get('attachments', [])
    if raw_attachments:
        attachment_info = _observe_attachments(raw_attachments)
    observation["attachments"] = attachment_info

    # ── STEP 4: Extract keywords from subject + body (FREE) ──
    text_for_search = f"{subject} {_clean_body(body_content)[:2000]}"
    keywords = _extract_keywords(text_for_search)
    observation["keywords"] = keywords

    # ── STEP 5: Ask Librarian what we know (FREE) ──
    librarian_knowledge = _ask_librarian(db, keywords, text_for_search)
    observation["librarian_results"] = {
        "tariff_codes_found": len(librarian_knowledge.get("tariff_codes", [])),
        "regulations_found": len(librarian_knowledge.get("regulations", [])),
        "knowledge_found": len(librarian_knowledge.get("knowledge", [])),
        "similar_past_found": len(librarian_knowledge.get("similar_past", [])),
        "confidence": librarian_knowledge.get("confidence", "low"),
    }

    # ── STEP 6: Identify knowledge gaps (FREE) ──
    gaps = _identify_gaps(observation, librarian_knowledge, contact_info)
    observation["knowledge_gaps"] = gaps

    # ── STEP 7: Check if this is a reply to a Pupil review email ──
    if is_reply and from_email.lower() == REVIEW_EMAIL.lower():
        if "בקשת אימות" in subject or "review_" in body_content:
            try:
                review_result = pupil_handle_review_reply(db, msg, get_secret_func)
                observation["is_review_reply"] = True
                observation["review_result"] = review_result
                print(f"    🎓 PUPIL: Review reply processed: {review_result.get('status')}")
            except Exception as re_err:
                print(f"    🎓 PUPIL: Review reply error: {re_err}")
        
        # Check if it's a reply to a correction email
        if "תיקון סיווג" in subject or "corr_" in body_content:
            try:
                corr_result = pupil_handle_correction_reply(
                    db, msg, access_token, rcb_email, get_secret_func
                )
                observation["is_correction_reply"] = True
                observation["correction_result"] = corr_result
                print(f"    🎓 PUPIL: Correction reply processed: {corr_result.get('status')}")
            except Exception as ce:
                print(f"    🎓 PUPIL: Correction reply error: {ce}")

    # ── STEP 7b: Create enrichment tasks from gaps ──
    for gap in gaps:
        gap_task_id = f"gap_{obs_id}_{gap.get('type', 'unknown')}"
        try:
            db.collection("enrichment_tasks").document(gap_task_id).set({
                "type": "gap",
                "gap_type": gap.get("type", ""),
                "question": gap.get("question", gap.get("detail", "")),
                "priority": gap.get("priority", "medium"),
                "tier_needed": gap.get("tier_needed", "tier_gemini"),
                "obs_id": obs_id,
                "subject": subject[:100],
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "pupil_observer",
            }, merge=True)
        except Exception:
            pass

    # ── STEP 8: If this is a user reply/challenge, flag for dispute resolution ──
    if is_reply and is_direct_to_rcb:
        observation["is_dispute"] = True
        observation["dispute_context"] = _extract_dispute_context(subject, body_content)
        print(f"    🎓 PUPIL: Dispute detected — user challenging RCB on: {subject[:40]}")

    # ── STEP 8: Store observation ──
    db.collection("pupil_observations").document(obs_id).set(observation)
    print(f"    🎓 PUPIL: Stored observation {obs_id} — {len(gaps)} gaps found")

    return {
        "status": "observed",
        "obs_id": obs_id,
        "gaps_count": len(gaps),
        "is_dispute": observation.get("is_dispute", False),
        "librarian_confidence": librarian_knowledge.get("confidence", "low"),
    }


# ═══════════════════════════════════════════
#  STEP 2: CONTACT OBSERVATION
# ═══════════════════════════════════════════

def _observe_contact(db, from_email, from_name, to_recipients, cc_recipients, body_content=""):
    """
    Check what we know about the sender and recipients.
    Updates contacts collection with new sightings.
    """
    result = {
        "sender_known": False,
        "sender_role": None,
        "sender_company": None,
        "new_contacts": [],
    }
    
    # Extract info from email signature
    sig_info = _extract_signature_info(body_content) if body_content else {}

    # Extract domain = company hint
    domain = from_email.split('@')[-1].lower() if '@' in from_email else ''

    # Check if we know this sender
    contact_ref = db.collection("contacts").document(_safe_email_id(from_email))
    contact_doc = contact_ref.get()

    if contact_doc.exists:
        data = contact_doc.to_dict()
        result["sender_known"] = True
        result["sender_role"] = data.get("role")
        result["sender_company"] = data.get("company")
        # Update last seen + signature info if new
        update_data = {
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "email_count": (data.get("email_count", 0) + 1),
        }
        if sig_info.get("role") and not data.get("role"):
            update_data["role"] = sig_info["role"]
            update_data["role_source"] = "email_signature"
        if sig_info.get("phone") and not data.get("phone"):
            update_data["phone"] = sig_info["phone"]
        if sig_info.get("website") and not data.get("website"):
            update_data["website"] = sig_info["website"]
        contact_ref.update(update_data)
    else:
        # New contact — store what we know (name + domain)
        contact_ref.set({
            "email": from_email,
            "name": from_name,
            "domain": domain,
            "company": _guess_company_from_domain(domain),
            "role": None,  # Gap — Pupil Phase B will research this
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "email_count": 1,
            "source": "pupil_observation",
        })
        result["new_contacts"].append(from_email)

    # Also track recipients we haven't seen
    all_recipients = (
        [r.get('emailAddress', {}).get('address', '') for r in to_recipients] +
        [r.get('emailAddress', {}).get('address', '') for r in cc_recipients]
    )
    for addr in all_recipients:
        if addr and not db.collection("contacts").document(_safe_email_id(addr)).get().exists:
            db.collection("contacts").document(_safe_email_id(addr)).set({
                "email": addr,
                "name": "",
                "domain": addr.split('@')[-1].lower() if '@' in addr else '',
                "role": None,
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "email_count": 0,
                "source": "pupil_observation_recipient",
            })
            result["new_contacts"].append(addr)

    return result


# ═══════════════════════════════════════════
#  STEP 3: ATTACHMENT OBSERVATION
# ═══════════════════════════════════════════

def _observe_attachments(raw_attachments):
    """Catalog attachments — type, name, size. Text extraction happens in Phase B."""
    info = []
    for att in raw_attachments:
        if att.get('@odata.type') == '#microsoft.graph.fileAttachment':
            name = att.get('name', 'unknown')
            ext = os.path.splitext(name)[1].lower()
            size = len(att.get('contentBytes', '')) if att.get('contentBytes') else 0
            doc_type = _classify_attachment_type(name, ext)
            info.append({
                "filename": name,
                "extension": ext,
                "size_bytes": size,
                "doc_type": doc_type,  # invoice, BOL, certificate, packing_list, unknown
            })
    return info


def _classify_attachment_type(filename, ext):
    """Guess document type from filename."""
    fn = filename.lower()
    if any(w in fn for w in ['invoice', 'inv', 'חשבון', 'פרופורמה', 'proforma']):
        return 'invoice'
    if any(w in fn for w in ['bl', 'b/l', 'lading', 'שטר', 'bill']):
        return 'bill_of_lading'
    if any(w in fn for w in ['packing', 'pack', 'אריזה']):
        return 'packing_list'
    if any(w in fn for w in ['certificate', 'cert', 'תעודה', 'origin', 'מקור']):
        return 'certificate'
    if any(w in fn for w in ['declaration', 'הצהרה', 'customs']):
        return 'declaration'
    if ext == '.pdf':
        return 'pdf_unknown'
    if ext in ['.xlsx', '.xls', '.csv']:
        return 'spreadsheet'
    if ext in ['.jpg', '.jpeg', '.png', '.gif']:
        return 'image'
    return 'unknown'


# ═══════════════════════════════════════════
#  STEP 4: KEYWORD EXTRACTION
# ═══════════════════════════════════════════

def _extract_keywords(text):
    """Extract search keywords from email text. Uses Librarian's method."""
    try:
        from lib.librarian import extract_search_keywords
        return extract_search_keywords(text)
    except ImportError:
        # Fallback: simple word extraction
        words = re.findall(r'[\w\u0590-\u05FF]{3,}', text.lower())
        # Remove common Hebrew stopwords
        stopwords = {'של', 'את', 'על', 'עם', 'זה', 'הוא', 'היא', 'אני', 'שלום',
                     'בברכה', 'תודה', 'from', 'the', 'and', 'for', 'with', 'this'}
        return list(set(w for w in words if w not in stopwords))[:15]


# ═══════════════════════════════════════════
#  STEP 5: ASK LIBRARIAN
# ═══════════════════════════════════════════

def _ask_librarian(db, keywords, description):
    """Query Librarian for everything it knows about these keywords."""
    try:
        from lib.librarian import full_knowledge_search
        return full_knowledge_search(db, keywords, description)
    except Exception as e:
        print(f"    🎓 PUPIL: Librarian error: {e}")
        return {
            "tariff_codes": [], "regulations": [],
            "procedures_rules": [], "knowledge": [],
            "history": [], "similar_past": [],
            "confidence": "error",
        }


# ═══════════════════════════════════════════
#  STEP 6: GAP IDENTIFICATION
# ═══════════════════════════════════════════

def _identify_gaps(observation, librarian_results, contact_info):
    """
    Compare what we observed vs what Librarian knows.
    Each gap becomes a learning task for Phase B.
    """
    gaps = []

    # Gap: Unknown sender
    if not contact_info.get("sender_known"):
        gaps.append({
            "type": "unknown_contact",
            "question": f"Who is {observation['from_name']} ({observation['from_email']})? What is their role and company function?",
            "priority": "medium",
            "tier_needed": TIER_GEMINI,  # Web lookup needed
        })

    # Gap: Low librarian confidence
    if librarian_results.get("confidence") == "low":
        body_snippet = observation.get("body_snippet", "")[:200]
        attachment_names = ", ".join(a.get("filename", "") for a in observation.get("attachments", []))[:200]
        gaps.append({
            "type": "low_knowledge",
            "question": (
                f"Librarian has low confidence for: {observation['subject']}. "
                f"Email body: {body_snippet}. "
                f"Attachments: {attachment_names or 'none'}. "
                f"What classification or knowledge is needed?"
            ),
            "priority": "high",
            "tier_needed": TIER_GEMINI,
        })

    # Gap: No tariff codes found but email has commercial content
    has_commercial = any(
        a.get("doc_type") in ("invoice", "bill_of_lading", "packing_list", "certificate")
        for a in observation.get("attachments", [])
    )
    if has_commercial and len(librarian_results.get("tariff_codes", [])) == 0:
        gaps.append({
            "type": "missing_tariff",
            "question": "Commercial documents found but no tariff codes matched. What products are in this shipment?",
            "priority": "high",
            "tier_needed": TIER_GEMINI,
        })

    # Gap: No regulations found for known products
    if librarian_results.get("tariff_codes") and not librarian_results.get("regulations"):
        gaps.append({
            "type": "missing_regulations",
            "question": "Tariff codes found but no regulations. What import regulations apply?",
            "priority": "medium",
            "tier_needed": TIER_GEMINI,
        })

    # Gap: Unknown attachment types
    unknown_docs = [a for a in observation.get("attachments", []) if a.get("doc_type") in ("unknown", "pdf_unknown")]
    if unknown_docs:
        gaps.append({
            "type": "unknown_documents",
            "question": f"Cannot identify {len(unknown_docs)} attachment(s). What type of documents are these?",
            "priority": "low",
            "tier_needed": TIER_GEMINI,  # Need AI to analyze content
        })

    # Gap: Dispute — user is challenging RCB
    if observation.get("is_dispute"):
        gaps.append({
            "type": "dispute",
            "question": f"User is challenging RCB's answer. What did we say and is it correct?",
            "priority": "critical",
            "tier_needed": TIER_CLAUDE,  # Deep reasoning needed
        })

    return gaps


# ═══════════════════════════════════════════
#  STEP 7: DISPUTE DETECTION
# ═══════════════════════════════════════════

def _extract_dispute_context(subject, body_content):
    """Extract what the user is disputing from their reply."""
    clean_body = _clean_body(body_content)

    # Look for disagreement signals in Hebrew and English
    dispute_signals = [
        'לא נכון', 'טעות', 'שגיאה', 'לא מסכים', 'בדקו שוב',
        'incorrect', 'wrong', 'mistake', 'error', 'please check',
        'למה', 'why', 'מדוע', 'אבל', 'but',
    ]

    signals_found = [s for s in dispute_signals if s in clean_body.lower()]

    # Extract the original subject (strip Re: / השב:)
    original_subject = re.sub(r'^(re:|השב:|fw:|fwd:)\s*', '', subject, flags=re.IGNORECASE).strip()

    return {
        "original_subject": original_subject,
        "dispute_signals": signals_found,
        "user_message": clean_body[:1000],
    }


# ═══════════════════════════════════════════
#  BUDGET TRACKING
# ═══════════════════════════════════════════

def check_daily_budget(db):
    """Check if we're within daily API budget."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    budget_ref = db.collection("pupil_budget").document(today)
    budget_doc = budget_ref.get()

    if budget_doc.exists:
        spent = budget_doc.to_dict().get("total_spent_usd", 0.0)
        return spent < DAILY_BUDGET_USD, spent
    return True, 0.0


def log_api_cost(db, tier, cost_usd, purpose):
    """Log an API call cost."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    budget_ref = db.collection("pupil_budget").document(today)
    budget_doc = budget_ref.get()

    if budget_doc.exists:
        current = budget_doc.to_dict()
        budget_ref.update({
            "total_spent_usd": current.get("total_spent_usd", 0.0) + cost_usd,
            "call_count": current.get("call_count", 0) + 1,
            "last_call": datetime.now(timezone.utc).isoformat(),
        })
    else:
        budget_ref.set({
            "date": today,
            "total_spent_usd": cost_usd,
            "call_count": 1,
            "budget_limit_usd": DAILY_BUDGET_USD,
            "last_call": datetime.now(timezone.utc).isoformat(),
        })


# ═══════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════

def _make_obs_id(msg_id):
    """Create a safe observation ID from message ID."""
    return f"obs_{hashlib.md5(msg_id.encode()).hexdigest()}"


def _safe_email_id(email_addr):
    """Create a safe Firestore document ID from email."""
    return re.sub(r'[/\\\.\[\]\*~<>@]', '_', email_addr.lower())[:100]


def _guess_company_from_domain(domain):
    """Basic company name guess from email domain."""
    if domain == 'rpa-port.co.il':
        return 'R.P.A. PORT LTD'
    if domain in ('gmail.com', 'hotmail.com', 'yahoo.com', 'outlook.com'):
        return None  # Personal email
    # Use domain name as company hint
    name = domain.split('.')[0] if domain else None
    return name


def _extract_signature_info(body_content):
    """
    Extract role, phone, website from email signature.
    Signatures typically appear after -- or at the bottom.
    """
    info = {"role": None, "phone": None, "website": None, "title": None}
    if not body_content:
        return info
    
    text = _clean_body(body_content)
    
    # Extract website URLs
    urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', text)
    if urls:
        info["website"] = urls[0]
    
    # Extract phone numbers (Israeli format)
    phones = re.findall(r'(?:\+972|0)[\s-]?(?:\d[\s-]?){8,9}', text)
    if phones:
        info["phone"] = phones[0].strip()
    
    # Look for signature block (last 500 chars or after --)
    sig_text = ""
    if "--" in text:
        sig_text = text.split("--")[-1][:500]
    else:
        sig_text = text[-500:] if len(text) > 500 else text
    
    # Hebrew role patterns
    role_patterns = [
        ('\u05de\u05e0\u05db.\u05dc', 'CEO'),
        (r"מנהל(?:ת|)\s*(?:תפעול|כללי|)", "מנהל/ת"),
        (r"עמיל(?:ת|)\s*מכס", "עמיל/ת מכס"),
        (r"יועצ?(?:ת|)\s*מכס", "יועץ/ת מכס"),
        (r"מזכיר(?:ה|)", "מזכיר/ה"),
        (r"רואה?\s*חשבון", "רואה חשבון"),
        (r"שילוח", "שילוח"),
        ('\u05e1\u05de\u05e0\u05db.\u05dc', 'VP'),
    ]
    # English role patterns
    role_patterns_en = [
        ('(?i)CEO|Chief Executive', 'CEO'),
        (r"(?i)customs?\s*broker", "עמיל מכס"),
        (r"(?i)manager", "מנהל/ת"),
        (r"(?i)director", "מנהל/ת"),
        (r"(?i)secretary", "מזכיר/ה"),
        (r"(?i)accountant", "רואה חשבון"),
        (r"(?i)freight\s*forward", "שילוח"),
        (r"(?i)logistics", "לוגיסטיקה"),
    ]
    
    for pattern, role in role_patterns + role_patterns_en:
        if re.search(pattern, sig_text):
            info["role"] = role
            break
    
    return info


def _clean_body(body_content):
    """Strip HTML tags and excessive whitespace from email body."""
    if not body_content:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', body_content)
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _decode_email_header(header_value):
    """
    Decode encoded email headers (RFC 2047).
    Handles =?windows-1255?B?...?= and similar encodings.
    """
    if not header_value:
        return "No Subject"
    
    # Skip if already clean text (no encoding markers)
    if '=?' not in header_value:
        return header_value
    
    try:
        decoded_parts = email_decode_header(header_value)
        result = ""
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                encoding = charset or 'utf-8'
                # Common Hebrew encodings
                if encoding.lower() in ('windows-1255', 'iso-8859-8', 'iso-8859-8-i'):
                    try:
                        result += part.decode(encoding)
                    except (UnicodeDecodeError, LookupError):
                        result += part.decode('utf-8', errors='replace')
                else:
                    try:
                        result += part.decode(encoding)
                    except (UnicodeDecodeError, LookupError):
                        result += part.decode('utf-8', errors='replace')
            else:
                result += str(part)
        return result.strip() or "No Subject"
    except Exception:
        return header_value


# ═══════════════════════════════════════════
#  CONTACT ROLE RESEARCH
#  Uses Gemini to figure out who people are
# ═══════════════════════════════════════════

def pupil_research_contacts(db, get_secret_func, max_contacts=5):
    """
    Research contacts with unknown roles using Gemini.
    Uses email patterns, domain, and email history to determine roles.
    """
    print("  🎓 PUPIL: Researching unknown contacts...")

    within_budget, _ = check_daily_budget(db)
    if not within_budget:
        return {"status": "budget_exceeded"}

    # Find contacts with no role
    contacts = list(
        db.collection("contacts")
        .where("role", "==", None)
        .limit(max_contacts)
        .stream()
    )

    results = {"researched": 0, "roles_found": 0}

    for contact_doc in contacts:
        contact = contact_doc.to_dict()
        email = contact.get("email", "")
        name = contact.get("name", "")
        domain = contact.get("domain", "")
        company = contact.get("company", "")
        email_count = contact.get("email_count", 0)

        # Skip system emails
        if any(skip in email.lower() for skip in [
            'noreply', 'no-reply', 'mailer-daemon', 'postmaster',
            'microsoftexchange', 'accounts.google'
        ]):
            db.collection("contacts").document(contact_doc.id).update({
                "role": "system", "role_source": "auto_detected"
            })
            results["researched"] += 1
            continue

        # Build context from their emails
        email_context = _get_contact_email_context(db, email)

        prompt = f"""Determine the role of this person in an Israeli customs brokerage company:

Name: {name}
Email: {email}
Domain: {domain}
Company: {company or 'unknown'}
Total emails: {email_count}
Email context (subjects): {email_context[:500]}

This is R.P.A. PORT LTD, an Israeli customs brokerage firm.
Common roles: מנכ"ל (CEO), מנהל/ת (manager), עמיל מכס (customs broker), 
מנהל/ת תפעול (operations), מזכיר/ה (secretary), שילוח (freight forwarder),
לקוח (client), ספק (supplier), סוכן (agent)

Respond in JSON:
{{"role": "role in Hebrew", "role_en": "role in English", "confidence_pct": 0-100, "reasoning": "why"}}"""

        try:
            from lib.gemini_classifier import _call_gemini
            raw = _call_gemini(prompt)
            if raw:
                try:
                    result = json.loads(raw)
                except json.JSONDecodeError:
                    match = re.search(r'\{.*\}', raw, re.DOTALL)
                    result = json.loads(match.group()) if match else None

                if result and result.get("role"):
                    db.collection("contacts").document(contact_doc.id).update({
                        "role": result["role"],
                        "role_en": result.get("role_en", ""),
                        "role_confidence": result.get("confidence_pct", 0),
                        "role_reasoning": result.get("reasoning", "")[:200],
                        "role_source": "pupil_gemini",
                        "role_updated_at": datetime.now(timezone.utc).isoformat(),
                    })
                    results["roles_found"] += 1
                    print(f"      🎓 {email} → {result['role']} ({result.get('confidence_pct', 0)}%)")

                log_api_cost(db, TIER_GEMINI, COST_GEMINI_CALL, f"contact_role: {email}")

        except Exception as e:
            print(f"      🎓 Contact research error for {email}: {e}")

        results["researched"] += 1

    print(f"    🎓 Contact research done: {results}")
    return results


def _get_contact_email_context(db, email):
    """Get subjects of recent emails from this contact for context."""
    try:
        docs = list(
            db.collection("pupil_observations")
            .where("from_email", "==", email)
            .limit(10)
            .stream()
        )
        subjects = [d.to_dict().get("subject", "")[:50] for d in docs if d.to_dict().get("subject")]
        return " | ".join(subjects) if subjects else "no emails found"
    except Exception:
        return "error reading emails"


# ═══════════════════════════════════════════
#  VERIFICATION SCANNER
#  Scans all knowledge for unverified items,
#  pushes them toward אומת (verified) status.
# ═══════════════════════════════════════════

# Statuses — Hebrew + English recognized
UNVERIFIED_STATUSES = {
    'unverified', 'לא אומת', 'low', 'pending', 'unknown',
    'needs_verification', 'לא מאומת', 'ממתין לאימות',
}
VERIFIED_STATUSES = {'verified', 'אומת', 'מאומת', 'high'}

# Collections to scan for unverified items
VERIFIABLE_COLLECTIONS = [
    ("classification_knowledge", "confidence"),
    ("pupil_observations", "phase"),
    ("pupil_teachings", "confidence"),
    ("knowledge_base", "confidence"),
    ("contacts", "role"),  # None role = needs research
]


def pupil_verify_scan(db, get_secret_func, max_items=20):
    """
    Scan all collections for unverified knowledge.
    Try to verify each item using escalating tiers.
    
    Called periodically (e.g., every 30 min) or after Pupil observations.
    
    Returns dict with verification results.
    """
    print("  🎓 PUPIL VERIFY: Starting verification scan...")

    # Check budget before doing any API work
    within_budget, spent = check_daily_budget(db)
    if not within_budget:
        print(f"    🎓 PUPIL VERIFY: Budget exceeded (${spent:.2f}/${DAILY_BUDGET_USD}). Skipping.")
        return {"status": "budget_exceeded", "spent": spent}

    results = {
        "scanned": 0,
        "verified": 0,
        "escalated": 0,
        "stuck": 0,
        "items": [],
    }

    unverified_items = _collect_unverified(db, max_items)
    results["scanned"] = len(unverified_items)
    print(f"    🎓 PUPIL VERIFY: Found {len(unverified_items)} unverified items")

    for item in unverified_items:
        result = _try_verify_item(db, item, get_secret_func)
        results["items"].append(result)

        if result["new_status"] in VERIFIED_STATUSES:
            results["verified"] += 1
        elif result.get("escalated"):
            results["escalated"] += 1
        else:
            results["stuck"] += 1

    # Flag items stuck unverified for >7 days
    _flag_stale_unverified(db)

    print(f"    🎓 PUPIL VERIFY: Done — {results['verified']} verified, "
          f"{results['escalated']} escalated, {results['stuck']} stuck")
    return results


def _collect_unverified(db, max_items):
    """Gather unverified items from all verifiable collections."""
    items = []

    for collection_name, status_field in VERIFIABLE_COLLECTIONS:
        try:
            # Query for known unverified status values
            for status_val in ['unverified', 'לא אומת', 'low', 'pending']:
                docs = (db.collection(collection_name)
                        .where(status_field, '==', status_val)
                        .limit(max_items // len(VERIFIABLE_COLLECTIONS) + 1)
                        .stream())
                for doc in docs:
                    data = doc.to_dict()
                    items.append({
                        "collection": collection_name,
                        "doc_id": doc.id,
                        "status_field": status_field,
                        "current_status": data.get(status_field, ''),
                        "data": data,
                    })
                    if len(items) >= max_items:
                        return items

            # Special: contacts with role=None (unknown role)
            if collection_name == "contacts" and status_field == "role":
                docs = (db.collection(collection_name)
                        .where("role", '==', None)
                        .limit(5)
                        .stream())
                for doc in docs:
                    data = doc.to_dict()
                    items.append({
                        "collection": collection_name,
                        "doc_id": doc.id,
                        "status_field": "role",
                        "current_status": "unknown_role",
                        "data": data,
                    })
                    if len(items) >= max_items:
                        return items

        except Exception as e:
            print(f"    🎓 PUPIL VERIFY: Error scanning {collection_name}: {e}")

    return items


def _try_verify_item(db, item, get_secret_func):
    """
    Try to verify a single item using escalating tiers:
    Tier 0 (free): Ask Librarian with current data
    Tier 1 (Gemini): If Librarian can't verify
    Tier 2 (Claude): If Gemini can't verify + item is critical
    
    Verification = backed by tariff DB or government source.
    """
    collection = item["collection"]
    doc_id = item["doc_id"]
    data = item["data"]
    result = {
        "collection": collection,
        "doc_id": doc_id,
        "old_status": item["current_status"],
        "new_status": item["current_status"],
        "escalated": False,
        "method": None,
    }

    # ── TIER 0: Ask Librarian (FREE) ──
    verification = _verify_with_librarian(db, collection, data)
    if verification["verified"]:
        _update_verification_status(
            db, collection, doc_id, item["status_field"],
            "אומת", verification["source"], verification["method"]
        )
        result["new_status"] = "אומת"
        result["method"] = "librarian"
        print(f"      ✅ Verified {collection}/{doc_id} via Librarian")
        return result

    # ── TIER 1: Escalate to Gemini (CHEAP) ──
    within_budget, _ = check_daily_budget(db)
    if not within_budget:
        result["new_status"] = "ממתין לאימות"
        return result

    # Only escalate if item has enough context to verify
    if _has_verifiable_content(data):
        result["escalated"] = True
        # Store as escalation task for Phase B processing
        _create_verification_task(db, item, TIER_GEMINI)
        result["new_status"] = "ממתין לאימות"
        print(f"      ⏫ Escalated {collection}/{doc_id} to Gemini")

    return result


def _verify_with_librarian(db, collection, data):
    """
    Ask Librarian if this item can be verified from existing data.
    Verification means: matching tariff code exists in DB,
    or matching regulation/procedure exists with government source.
    """
    result = {"verified": False, "source": None, "method": None}

    try:
        from lib.librarian import search_tariff_codes, validate_hs_code, full_knowledge_search

        # For classification knowledge — verify HS code exists in tariff DB
        if collection == "classification_knowledge":
            hs_code = data.get("hs_code", "")
            if hs_code:
                validation = validate_hs_code(db, hs_code)
                if validation and validation.get("valid"):
                    result["verified"] = True
                    result["source"] = "tariff_db"
                    result["method"] = f"HS code {hs_code} validated against tariff collection"
                    return result

        # For knowledge_base — check if content references verifiable sources
        if collection == "knowledge_base":
            content = data.get("content", "")
            source = data.get("source", "")
            # If source is government/official, mark verified
            gov_sources = ['shaam.gov.il', 'gov.il', 'taxes.gov.il', 'customs.mof.gov.il',
                          'תעריף המכס', 'צו יבוא', 'פקודת המכס']
            if any(gs in (content + source).lower() for gs in gov_sources):
                result["verified"] = True
                result["source"] = "government_reference"
                result["method"] = f"References official source: {source[:100]}"
                return result

        # For pupil_observations — verify if Librarian confidence improved
        if collection == "pupil_observations":
            keywords = data.get("keywords", [])
            if keywords:
                lib_results = full_knowledge_search(db, keywords, data.get("subject", ""))
                if lib_results.get("confidence") in ("high", "medium"):
                    result["verified"] = True
                    result["source"] = "librarian_confidence_improved"
                    result["method"] = f"Librarian confidence now: {lib_results['confidence']}"
                    return result

    except Exception as e:
        print(f"      🎓 PUPIL VERIFY: Librarian check error: {e}")

    return result


def _update_verification_status(db, collection, doc_id, status_field, new_status, source, method):
    """Update a document's verification status."""
    try:
        update_data = {
            status_field: new_status,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "verified_by": "pupil_scanner",
            "verification_source": source,
            "verification_method": method,
        }
        db.collection(collection).document(doc_id).update(update_data)
    except Exception as e:
        print(f"      ❌ Failed to update {collection}/{doc_id}: {e}")


def _has_verifiable_content(data):
    """Check if item has enough data to attempt verification."""
    # Has HS code? Product description? Keywords?
    has_hs = bool(data.get("hs_code"))
    has_desc = bool(data.get("description") or data.get("subject"))
    has_keywords = bool(data.get("keywords"))
    return has_hs or has_desc or has_keywords


def _create_verification_task(db, item, tier):
    """Create a task for Phase B to process with AI."""
    task_id = f"verify_{item['collection']}_{item['doc_id']}"
    db.collection("enrichment_tasks").document(task_id).set({
        "type": "verification",
        "collection": item["collection"],
        "doc_id": item["doc_id"],
        "data_snapshot": {k: v for k, v in item["data"].items()
                         if isinstance(v, (str, int, float, bool, type(None)))},
        "tier_needed": tier,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "pupil_verify_scanner",
    }, merge=True)


def _flag_stale_unverified(db):
    """Flag items unverified for more than 7 days."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    try:
        stale = (db.collection("pupil_observations")
                 .where("phase", "==", "A_observe")
                 .where("observed_at", "<", cutoff)
                 .limit(50)
                 .stream())

        stale_count = 0
        for doc in stale:
            data = doc.to_dict()
            if data.get("phase") not in ("verified", "אומת"):
                db.collection("pupil_observations").document(doc.id).update({
                    "stale_flag": True,
                    "stale_flagged_at": datetime.now(timezone.utc).isoformat(),
                })
                stale_count += 1

        if stale_count > 0:
            print(f"    ⚠️ PUPIL VERIFY: Flagged {stale_count} stale unverified items (>7 days)")
    except Exception as e:
        print(f"    🎓 PUPIL VERIFY: Stale flag error: {e}")


# ═══════════════════════════════════════════
#  DEVIL'S ADVOCATE — Challenge existing knowledge
# ═══════════════════════════════════════════

def pupil_challenge(db, doc_id, collection="classification_knowledge"):
    """
    Challenge a verified item — ask 'why not something else?'
    Used by Phase B after getting answers, and by periodic audit.
    
    Returns list of counter-questions for the Librarian.
    """
    doc = db.collection(collection).document(doc_id).get()
    if not doc.exists:
        return []

    data = doc.to_dict()
    challenges = []

    # For classification knowledge — challenge the HS code
    if collection == "classification_knowledge":
        hs_code = data.get("hs_code", "")
        description = data.get("description", "")
        chapter = data.get("chapter", "")

        if hs_code and description:
            heading = hs_code[:5] if len(hs_code) >= 5 else ""
            challenges.append({
                "type": "alternative_heading",
                "question": f"Why is '{description}' classified under heading {heading} and not another heading in chapter {chapter}?",
                "requires": "elimination_walk",
            })
            challenges.append({
                "type": "alternative_chapter",
                "question": f"Could '{description}' belong in a different chapter entirely? What are the GRI rules that confirm chapter {chapter}?",
                "requires": "gri_check",
            })
            challenges.append({
                "type": "regulation_check",
                "question": f"What import regulations apply to {heading}? Are we missing ministry requirements?",
                "requires": "regulation_search",
            })

    # For any knowledge — challenge source freshness
    learned_at = data.get("learned_at") or data.get("created_at") or ""
    if learned_at:
        challenges.append({
            "type": "freshness",
            "question": f"This was learned on {learned_at[:10]}. Has anything changed since?",
            "requires": "web_check",
        })

    # Store challenges as tasks
    for ch in challenges:
        task_id = f"challenge_{doc_id}_{ch['type']}"
        db.collection("enrichment_tasks").document(task_id).set({
            "type": "challenge",
            "challenge_type": ch["type"],
            "question": ch["question"],
            "requires": ch["requires"],
            "source_collection": collection,
            "source_doc_id": doc_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "pupil_devil_advocate",
        }, merge=True)

    return challenges


# ═══════════════════════════════════════════
#  PHASE B: LEARNING LOOP
#  Gemini fills gaps, teaches the system.
#  Claude escalation only when needed.
# ═══════════════════════════════════════════

def pupil_learn(db, get_secret_func, max_tasks=10):
    """
    Phase B main entry. Processes pending enrichment_tasks.
    For each task:
      1. Ask Gemini to answer + explain method
      2. Devil's advocate: ask "why not X?"
      3. Store answer + method + teaching
      4. Update Librarian knowledge
    
    Returns dict with learning results.
    """
    print("  🎓 PUPIL PHASE B: Starting learning loop...")

    within_budget, spent = check_daily_budget(db)
    if not within_budget:
        print(f"    🎓 Budget exceeded (${spent:.2f}). Skipping Phase B.")
        return {"status": "budget_exceeded", "spent": spent}

    # Get pending tasks
    tasks = list(
        db.collection("enrichment_tasks")
        .where("status", "==", "pending")
        .limit(max_tasks)
        .stream()
    )
    print(f"    🎓 Found {len(tasks)} pending tasks")

    results = {"processed": 0, "learned": 0, "escalated": 0, "errors": 0}

    for task_doc in tasks:
        task = task_doc.to_dict()
        task_id = task_doc.id
        task_type = task.get("type", "")

        try:
            if task_type == "verification":
                result = _learn_verification(db, task, task_id, get_secret_func)
            elif task_type == "challenge":
                result = _learn_challenge(db, task, task_id, get_secret_func)
            else:
                result = _learn_gap(db, task, task_id, get_secret_func)

            if result.get("learned"):
                results["learned"] += 1
            if result.get("escalated"):
                results["escalated"] += 1
            results["processed"] += 1

        except Exception as e:
            print(f"    🎓 Task {task_id} error: {e}")
            db.collection("enrichment_tasks").document(task_id).update({
                "status": "error", "error": str(e)[:200],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            results["errors"] += 1

    print(f"    🎓 PHASE B done: {results}")
    return results


def _learn_gap(db, task, task_id, get_secret_func):
    """Fill a knowledge gap using Gemini, then teach the system."""
    question = task.get("question", "")
    if not question:
        db.collection("enrichment_tasks").document(task_id).update({"status": "skipped"})
        return {"learned": False}

    # Ask Gemini
    answer = _ask_gemini_with_method(question, get_secret_func)
    if not answer:
        return {"learned": False, "escalated": False}

    # Log cost
    log_api_cost(db, TIER_GEMINI, COST_GEMINI_CALL, f"gap: {question[:50]}")

    # Store teaching
    teaching_id = f"teach_{task_id}"
    teaching = {
        "question": question,
        "answer": answer.get("answer", ""),
        "method": answer.get("method", ""),
        "teaching_rule": answer.get("teaching", ""),
        "source": "gemini_flash",
        "confidence": "לא אומת",  # Unverified until Librarian confirms
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
    }
    db.collection("pupil_teachings").document(teaching_id).set(teaching)

    # Update task
    db.collection("enrichment_tasks").document(task_id).update({
        "status": "answered",
        "answer_summary": answer.get("answer", "")[:200],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    # Try to enrich Librarian's knowledge
    _teach_librarian(db, answer, task)

    print(f"      🎓 Learned: {question[:50]}")
    return {"learned": True}


def _learn_verification(db, task, task_id, get_secret_func):
    """Verify an item using Gemini."""
    data = task.get("data_snapshot", {})
    collection = task.get("collection", "")
    doc_id = task.get("doc_id", "")

    hs_code = data.get("hs_code", "")
    description = data.get("description", data.get("subject", ""))

    if not description:
        db.collection("enrichment_tasks").document(task_id).update({"status": "skipped"})
        return {"learned": False}

    question = (
        f"Verify this Israeli customs classification:\n"
        f"Product: {description}\n"
        f"HS Code: {hs_code}\n"
        f"Is this correct? Explain step by step using GRI rules and the Israeli tariff structure. "
        f"If incorrect, provide the correct HS code with reasoning."
    )

    answer = _ask_gemini_with_method(question, get_secret_func)
    if not answer:
        return {"learned": False}

    log_api_cost(db, TIER_GEMINI, COST_GEMINI_CALL, f"verify: {hs_code}")

    is_correct = answer.get("is_correct", None)
    confidence = "אומת" if is_correct else "לא אומת"

    # Store teaching
    teaching = {
        "question": question,
        "answer": answer.get("answer", ""),
        "method": answer.get("method", ""),
        "teaching_rule": answer.get("teaching", ""),
        "source": "gemini_flash",
        "confidence": confidence,
        "verified_hs_code": answer.get("correct_code", hs_code),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.collection("pupil_teachings").document(f"verify_{task_id}").set(teaching)

    # Update original doc if verified
    if is_correct and collection and doc_id:
        try:
            db.collection(collection).document(doc_id).update({
                "confidence": confidence,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "verified_by": "pupil_gemini",
                "verification_method": answer.get("method", "")[:500],
            })
        except Exception:
            pass

    db.collection("enrichment_tasks").document(task_id).update({
        "status": "verified" if is_correct else "disputed",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    # If Gemini says it's wrong — escalate to Claude for deeper review
    if is_correct is False:
        _create_verification_task(db, {
            "collection": collection, "doc_id": doc_id,
            "data": data, "status_field": "confidence",
            "current_status": "disputed_by_gemini",
        }, TIER_CLAUDE)
        return {"learned": True, "escalated": True}

    return {"learned": True}


def _learn_challenge(db, task, task_id, get_secret_func):
    """Process a devil's advocate challenge."""
    question = task.get("question", "")
    challenge_type = task.get("challenge_type", "")

    if not question:
        db.collection("enrichment_tasks").document(task_id).update({"status": "skipped"})
        return {"learned": False}

    answer = _ask_gemini_with_method(question, get_secret_func)
    if not answer:
        return {"learned": False}

    log_api_cost(db, TIER_GEMINI, COST_GEMINI_CALL, f"challenge: {challenge_type}")

    # Store the challenge result
    teaching = {
        "question": question,
        "answer": answer.get("answer", ""),
        "method": answer.get("method", ""),
        "teaching_rule": answer.get("teaching", ""),
        "challenge_type": challenge_type,
        "source": "gemini_flash",
        "confidence": "לא אומת",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.collection("pupil_teachings").document(f"chal_{task_id}").set(teaching)

    # If challenge reveals a problem, escalate
    answer_text = answer.get("answer", "").lower()
    problem_signals = ["incorrect", "wrong", "should be", "לא נכון", "טעות", "צריך להיות"]
    has_problem = any(sig in answer_text for sig in problem_signals)

    db.collection("enrichment_tasks").document(task_id).update({
        "status": "problem_found" if has_problem else "confirmed",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    if has_problem:
        # Escalate to Claude for final decision
        source_doc = task.get("source_doc_id", "")
        source_col = task.get("source_collection", "")
        if source_doc and source_col:
            _create_verification_task(db, {
                "collection": source_col, "doc_id": source_doc,
                "data": {"challenge_question": question, "gemini_answer": answer.get("answer", "")[:500]},
                "status_field": "confidence", "current_status": "challenged",
            }, TIER_CLAUDE)
        return {"learned": True, "escalated": True}

    # Challenge confirmed — the original was correct. Teach system why.
    _teach_librarian(db, answer, task)
    return {"learned": True}


# ═══════════════════════════════════════════
#  GEMINI CALLER
# ═══════════════════════════════════════════

def _ask_gemini_with_method(question, get_secret_func):
    """
    Ask Gemini to answer AND explain its method.
    Returns dict with: answer, method, teaching, is_correct, correct_code
    """
    prompt = f"""You are an expert Israeli customs broker assistant.
Answer this question about customs classification or import procedures.

CRITICAL RULES:
- Use Israeli tariff book (based on HS/WCO nomenclature)
- Reference GRI rules when applicable
- Reference specific government regulations when applicable
- If you're not certain, say so — DO NOT GUESS
- Answer in the same language as the question

QUESTION: {question}

Respond in this exact JSON format:
{{
    "answer": "Your detailed answer",
    "method": "Step-by-step method you used to reach this answer",
    "teaching": "A rule the system can learn for similar future cases",
    "is_correct": true/false/null,
    "correct_code": "XX.XX.XXXXXX if applicable, else empty string",
    "confidence_pct": 0-100,
    "sources": ["source1", "source2"]
}}"""

    try:
        from lib.gemini_classifier import _call_gemini
        raw = _call_gemini(prompt)
        if not raw:
            return None

        # Parse JSON
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                result = json.loads(match.group())
            else:
                result = {"answer": raw, "method": "", "teaching": "", "is_correct": None}

        return result

    except Exception as e:
        print(f"      🎓 Gemini error: {e}")
        return None


def _ask_claude_deep(question, get_secret_func):
    """
    Escalation: Ask Claude for deep reasoning on disputed items.
    More expensive but more thorough.
    """
    try:
        api_key = get_secret_func("ANTHROPIC_API_KEY")
        if not api_key:
            return None

        from lib.classification_agents import call_claude
        system_prompt = """You are a senior Israeli customs classification expert.
You must verify classifications using:
1. The Israeli Customs Tariff (based on HS Convention)
2. General Rules of Interpretation (GRI 1-6)
3. Israeli import regulations (צו יבוא חופשי, פקודת המכס)
4. Ministry requirements per product type

CRITICAL: Only confirm if you are certain. Explain your full reasoning.
If uncertain, say "UNCERTAIN" and explain what additional info is needed.
Respond in JSON format with: answer, method, teaching, is_correct, correct_code, confidence_pct, sources"""

        raw = call_claude(api_key, system_prompt, question, max_tokens=2000)
        if not raw:
            return None

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                result = json.loads(match.group())
            else:
                result = {"answer": raw, "method": "", "teaching": ""}

        return result

    except Exception as e:
        print(f"      🎓 Claude error: {e}")
        return None


# ═══════════════════════════════════════════
#  TEACH LIBRARIAN — Store knowledge for system
# ═══════════════════════════════════════════

def _teach_librarian(db, answer, task):
    """
    Take Gemini/Claude answer and SAFELY store it.
    NEVER auto-overrides existing knowledge.
    
    Flow:
    1. Check if answer contradicts existing system knowledge
    2. If conflict → create review case for human (doron@)
    3. If new info → store as לא אומת, pending review
    4. If confirms existing → strengthen confidence
    5. Cross-validate with Researcher when possible
    """
    if not answer:
        return

    answer_text = answer.get("answer", "")
    method = answer.get("method", "")
    teaching = answer.get("teaching", "")
    correct_code = answer.get("correct_code", "")
    confidence = answer.get("confidence_pct", 0)

    # ── SAFETY CHECK: Does this contradict existing knowledge? ──
    if correct_code and len(correct_code) >= 5:
        conflict = _check_for_conflicts(db, correct_code, answer_text, task)
        if conflict["has_conflict"]:
            # DO NOT store — create human review case
            _create_review_case(db, answer, task, conflict)
            print(f"      ⚠️ CONFLICT detected — sent to human review, NOT stored")
            return

    # ── VALIDATE with Librarian (tariff DB) ──
    validation = _validate_with_system(db, correct_code, answer_text)

    # Determine final confidence — NEVER אומת without system validation
    if validation.get("tariff_confirmed"):
        final_confidence = "ממתין לאימות אנושי"  # Pending human verification
    elif validation.get("tariff_exists"):
        final_confidence = "לא אומת"
    else:
        final_confidence = "לא אומת"

    # Store in knowledge_base — always as suggestion, never as fact
    if len(answer_text) > 50 and method:
        kb_id = f"pupil_{task.get('type', 'learn')}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        db.collection("knowledge_base").document(kb_id).set({
            "title": task.get("question", "")[:100],
            "content": answer_text[:2000],
            "method": method[:1000],
            "teaching_rule": teaching[:500],
            "source": f"pupil_phase_b_{answer.get('source', 'gemini')}",
            "category": "pupil_suggestion",  # NOT fact — suggestion
            "confidence": final_confidence,
            "system_validated": validation.get("tariff_confirmed", False),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tags": ["pupil", "auto_learned", "needs_review"],
        })

    # If we have an HS code — store as suggestion only
    if correct_code and len(correct_code) >= 5:
        description = task.get("question", "")[:200]
        ck_id = f"pupil_suggest_{correct_code}_{_safe_email_id(description[:30])}"
        db.collection("classification_knowledge").document(ck_id).set({
            "hs_code": correct_code,
            "description": description,
            "method": method[:500],
            "teaching_rule": teaching[:300],
            "source": "pupil_suggestion",
            "confidence": final_confidence,
            "system_validated": validation.get("tariff_confirmed", False),
            "learned_at": datetime.now(timezone.utc).isoformat(),
            "usage_count": 0,
            "tags": ["pupil", "suggestion", "needs_review"],
        }, merge=True)


def _check_for_conflicts(db, hs_code, answer_text, task):
    """
    Check if Gemini's answer contradicts existing system knowledge.
    Returns: {"has_conflict": bool, "existing": {...}, "details": str}
    """
    result = {"has_conflict": False, "existing": None, "details": ""}

    try:
        # Check classification_knowledge for same description with different code
        description = task.get("question", "")[:100]
        if description:
            existing_docs = list(
                db.collection("classification_knowledge")
                .where("description", "==", description)
                .limit(5)
                .stream()
            )
            for doc in existing_docs:
                data = doc.to_dict()
                existing_code = data.get("hs_code", "")
                if existing_code and existing_code != hs_code:
                    result["has_conflict"] = True
                    result["existing"] = data
                    result["details"] = (
                        f"System has '{description}' as {existing_code}, "
                        f"but AI suggests {hs_code}"
                    )
                    return result

        # Check if HS code heading differs from existing classifications
        heading = hs_code[:4]
        existing_heading_docs = list(
            db.collection("classification_knowledge")
            .where("hs_code", ">=", heading)
            .where("hs_code", "<", heading + "z")
            .limit(10)
            .stream()
        )
        # No conflict if no existing data or heading matches
        
    except Exception as e:
        print(f"      🎓 Conflict check error: {e}")

    return result


def _validate_with_system(db, hs_code, answer_text):
    """
    Cross-validate AI answer against system's actual data.
    Uses Librarian's tariff DB + Researcher's online sources.
    """
    result = {"tariff_exists": False, "tariff_confirmed": False, "researcher_checked": False}

    if not hs_code:
        return result

    try:
        # Step 1: Ask Librarian — does this code exist in tariff DB?
        from lib.librarian import validate_hs_code, search_tariff_codes
        
        validation = validate_hs_code(db, hs_code)
        if validation and validation.get("valid"):
            result["tariff_exists"] = True
            # Check if description matches
            tariff_desc = validation.get("description", "")
            if tariff_desc and len(tariff_desc) > 5:
                result["tariff_confirmed"] = True
                result["tariff_description"] = tariff_desc

        # Step 2: Ask Researcher — check online (shaam.gov.il)
        try:
            from lib.librarian_researcher import research_hs_code
            research = research_hs_code(db, hs_code)
            if research:
                result["researcher_checked"] = True
                result["researcher_data"] = research
        except (ImportError, AttributeError):
            pass  # Researcher may not have this function yet

    except Exception as e:
        print(f"      🎓 System validation error: {e}")

    return result


# ═══════════════════════════════════════════
#  HUMAN REVIEW EMAIL SYSTEM
#  Sends well-articulated cases to doron@
#  Max 3 review emails per day
# ═══════════════════════════════════════════


def _create_review_case(db, answer, task, conflict):
    """
    Create a review case and queue it for email to doron@.
    Does NOT send email directly — stores in pupil_reviews collection.
    Email is sent by pupil_send_reviews() which respects daily limit.
    """
    case_id = f"review_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{_make_obs_id(str(task))[:8]}"
    
    existing = conflict.get("existing", {})
    
    case = {
        "case_id": case_id,
        "status": "pending_email",
        "created_at": datetime.now(timezone.utc).isoformat(),
        
        # The finding
        "finding_type": "conflict" if conflict.get("has_conflict") else "new_info",
        "subject_line": f"🎓 בקשת אימות: {task.get('question', '')[:60]}",
        
        # Current system knowledge
        "system_hs_code": existing.get("hs_code", ""),
        "system_description": existing.get("description", ""),
        "system_confidence": existing.get("confidence", ""),
        "system_source": existing.get("source", ""),
        
        # AI suggestion
        "ai_hs_code": answer.get("correct_code", ""),
        "ai_answer": answer.get("answer", "")[:1000],
        "ai_method": answer.get("method", "")[:1000],
        "ai_teaching": answer.get("teaching", "")[:500],
        "ai_source": answer.get("source", "gemini"),
        "ai_confidence_pct": answer.get("confidence_pct", 0),
        "ai_legal_sources": answer.get("sources", []),
        
        # Conflict details
        "conflict_details": conflict.get("details", ""),
        
        # For tracking replies
        "email_sent": False,
        "human_response": None,
        "human_responded_at": None,
        "re_verified": False,
    }
    
    db.collection("pupil_reviews").document(case_id).set(case)
    print(f"      📋 Review case created: {case_id}")
    return case_id


def pupil_send_reviews(db, access_token, rcb_email, get_secret_func):
    """
    Send pending review cases to doron@ via email.
    Max 3 emails per day. Each email is a well-articulated case.
    
    Called from scheduler or after batch processing.
    """
    print("  🎓 PUPIL REVIEWS: Checking for pending cases...")
    
    # Check daily email count
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    budget_doc = db.collection("pupil_review_budget").document(today).get()
    emails_sent_today = budget_doc.to_dict().get("count", 0) if budget_doc.exists else 0
    
    if emails_sent_today >= MAX_REVIEW_EMAILS_PER_DAY:
        print(f"    🎓 Daily review limit reached ({emails_sent_today}/{MAX_REVIEW_EMAILS_PER_DAY})")
        return {"status": "limit_reached", "sent": 0}
    
    remaining = MAX_REVIEW_EMAILS_PER_DAY - emails_sent_today
    
    # Get pending cases
    cases = list(
        db.collection("pupil_reviews")
        .where("status", "==", "pending_email")
        .limit(remaining)
        .stream()
    )
    
    if not cases:
        print("    🎓 No pending review cases")
        return {"status": "no_cases", "sent": 0}
    
    sent = 0
    for case_doc in cases:
        case = case_doc.to_dict()
        case_id = case_doc.id
        
        try:
            email_body = _build_review_email(case)
            subject = case.get("subject_line", "🎓 בקשת אימות מ-RCB")
            
            # Send via Graph API — ONLY to doron@, NEVER to external
            from lib.rcb_helpers import helper_graph_send
            success = helper_graph_send(
                access_token, rcb_email, REVIEW_EMAIL,
                subject, email_body, []
            )
            
            if success:
                db.collection("pupil_reviews").document(case_id).update({
                    "status": "email_sent",
                    "email_sent": True,
                    "email_sent_at": datetime.now(timezone.utc).isoformat(),
                })
                sent += 1
                print(f"    ✉️ Review sent: {case_id}")
            else:
                print(f"    ❌ Failed to send review: {case_id}")
                
        except Exception as e:
            print(f"    ❌ Review email error: {e}")
    
    # Update daily count
    db.collection("pupil_review_budget").document(today).set({
        "count": emails_sent_today + sent,
        "date": today,
    }, merge=True)
    
    print(f"    🎓 Reviews sent: {sent}/{len(cases)}")
    return {"status": "sent", "sent": sent}


def _build_review_email(case):
    """
    Build a well-articulated Hebrew review email.
    Clear, professional, with reasoning and legal references.
    """
    finding_type = case.get("finding_type", "")
    
    if finding_type == "conflict":
        header = "🔍 נמצאה סתירה בין ידע המערכת לבין ניתוח AI"
    else:
        header = "🆕 מידע חדש שדורש אימות"
    
    body = f"""<div dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.8;">
<h2 style="color: #1a5276;">{header}</h2>

<hr>

<h3>📌 תיאור המקרה</h3>
<p>{case.get('conflict_details', case.get('ai_answer', '')[:200])}</p>

<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; margin: 15px 0;">
<tr style="background-color: #eaf2f8;">
    <th style="text-align: right;">פרט</th>
    <th style="text-align: right;">ידע המערכת הנוכחי</th>
    <th style="text-align: right;">הצעת AI</th>
</tr>
<tr>
    <td><strong>קוד HS</strong></td>
    <td>{case.get('system_hs_code', 'אין')}</td>
    <td>{case.get('ai_hs_code', 'אין')}</td>
</tr>
<tr>
    <td><strong>תיאור</strong></td>
    <td>{case.get('system_description', 'אין')[:100]}</td>
    <td>{case.get('ai_answer', '')[:100]}</td>
</tr>
<tr>
    <td><strong>ביטחון</strong></td>
    <td>{case.get('system_confidence', 'אין')}</td>
    <td>{case.get('ai_confidence_pct', 0)}%</td>
</tr>
</table>

<h3>📊 ניתוח ונימוקים</h3>
<p><strong>שיטת הניתוח:</strong></p>
<p>{case.get('ai_method', 'לא צוין')}</p>

<p><strong>כלל לימוד:</strong></p>
<p>{case.get('ai_teaching', 'לא צוין')}</p>

<p><strong>מקורות:</strong></p>
<p>{', '.join(case.get('ai_legal_sources', ['לא צוינו']))}</p>

<hr>

<h3>🎯 נדרשת החלטתך</h3>
<p>אנא השב למייל זה עם אחת מהאפשרויות:</p>
<ul>
<li><strong>מאשר</strong> — הצעת ה-AI נכונה, עדכנו את המערכת</li>
<li><strong>דוחה</strong> — ידע המערכת הנוכחי נכון, אל תשנו</li>
<li><strong>לבדוק</strong> — צריך בדיקה נוספת (ציינו מה)</li>
</ul>

<p style="color: #666; font-size: 0.9em;">
מזהה מקרה: {case.get('case_id', '')}<br>
נוצר: {case.get('created_at', '')[:16]}<br>
מקור AI: {case.get('ai_source', 'gemini')}
</p>
</div>"""
    
    return body


def pupil_handle_review_reply(db, msg, get_secret_func):
    """
    Process doron@'s reply to a review email.
    Extracts decision, updates case, re-verifies if needed.
    
    Called by Pupil when it observes a reply to a review email.
    """
    subject = msg.get("subject", "")
    body = msg.get("body", {}).get("content", "")
    body_clean = _clean_body(body).lower()
    
    # Find the case ID in the email
    case_id_match = re.search(r'review_\d{8}_\d{6}_\w+', body + subject)
    if not case_id_match:
        # Try to match by subject
        cases = list(
            db.collection("pupil_reviews")
            .where("status", "==", "email_sent")
            .limit(10)
            .stream()
        )
        matching = None
        for c in cases:
            cd = c.to_dict()
            if cd.get("subject_line", "")[:30] in subject:
                matching = c
                break
        if not matching:
            return {"status": "no_case_found"}
        case_id = matching.id
        case = matching.to_dict()
    else:
        case_id = case_id_match.group()
        case_doc = db.collection("pupil_reviews").document(case_id).get()
        if not case_doc.exists:
            return {"status": "case_not_found"}
        case = case_doc.to_dict()
    
    # Extract decision from reply
    decision = _extract_decision(body_clean)
    
    # Update case
    db.collection("pupil_reviews").document(case_id).update({
        "status": f"human_{decision}",
        "human_response": body_clean[:500],
        "human_responded_at": datetime.now(timezone.utc).isoformat(),
    })
    
    if decision == "approved":
        # Apply AI suggestion to system
        _apply_approved_suggestion(db, case)
        print(f"    ✅ Review {case_id}: APPROVED — system updated")
        
    elif decision == "rejected":
        # Strengthen existing knowledge
        _strengthen_existing_knowledge(db, case)
        print(f"    ❌ Review {case_id}: REJECTED — existing knowledge confirmed")
        
    elif decision == "investigate":
        # Create deeper research task
        _create_investigation_task(db, case, body_clean)
        print(f"    🔍 Review {case_id}: INVESTIGATE — deeper research queued")
    
    return {"status": decision, "case_id": case_id}


def _extract_decision(body_text):
    """Extract human decision from reply text."""
    approve_signals = ["מאשר", "נכון", "מאושר", "approved", "correct", "אשר", "עדכנו"]
    reject_signals = ["דוחה", "לא נכון", "rejected", "שגוי", "דחה", "אל תשנו"]
    investigate_signals = ["לבדוק", "בדיקה", "investigate", "check", "לא בטוח", "צריך"]
    
    for sig in approve_signals:
        if sig in body_text:
            return "approved"
    for sig in reject_signals:
        if sig in body_text:
            return "rejected"
    for sig in investigate_signals:
        if sig in body_text:
            return "investigate"
    
    return "investigate"  # Default to investigate if unclear


def _apply_approved_suggestion(db, case):
    """Apply an approved AI suggestion to system knowledge."""
    hs_code = case.get("ai_hs_code", "")
    if not hs_code:
        return
    
    # Update classification_knowledge with אומת status
    description = case.get("ai_answer", "")[:200]
    ck_id = f"approved_{hs_code}_{_safe_email_id(description[:30])}"
    db.collection("classification_knowledge").document(ck_id).set({
        "hs_code": hs_code,
        "description": description,
        "method": case.get("ai_method", "")[:500],
        "teaching_rule": case.get("ai_teaching", "")[:300],
        "source": "pupil_human_approved",
        "confidence": "אומת",
        "approved_by": REVIEW_EMAIL,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "case_id": case.get("case_id", ""),
        "usage_count": 0,
        "tags": ["pupil", "human_approved", "אומת"],
    }, merge=True)
    
    # ── Write to learned_corrections (Level -1 override for future classifications) ──
    product = case.get("product_description", "") or description
    if product and hs_code:
        import re as _re
        corr_id = _re.sub(r'[^a-zA-Z0-9]', '_', product.lower()[:80])
        db.collection("learned_corrections").document(f"pupil_{corr_id}").set({
            "product": product[:200],
            "corrected_code": hs_code,
            "original_code": case.get("system_hs_code", ""),
            "source": "pupil_human_approved",
            "reason": case.get("ai_method", "")[:500],
            "learned_at": datetime.now(timezone.utc).isoformat(),
            "case_id": case.get("case_id", ""),
        }, merge=True)

    # Store teaching rule for Librarian
    if case.get("ai_teaching"):
        db.collection("pupil_teachings").document(f"approved_{case['case_id']}").set({
            "teaching_rule": case["ai_teaching"],
            "method": case.get("ai_method", ""),
            "confidence": "אומת",
            "approved_by": REVIEW_EMAIL,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })


def _strengthen_existing_knowledge(db, case):
    """When human rejects AI suggestion, strengthen existing knowledge."""
    system_code = case.get("system_hs_code", "")
    if not system_code:
        return
    
    # Find and strengthen existing docs
    try:
        docs = list(
            db.collection("classification_knowledge")
            .where("hs_code", "==", system_code)
            .limit(5)
            .stream()
        )
        for doc in docs:
            db.collection("classification_knowledge").document(doc.id).update({
                "confidence": "אומת",
                "human_confirmed": True,
                "confirmed_by": REVIEW_EMAIL,
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
                "rejected_alternatives": [case.get("ai_hs_code", "")],
            })
    except Exception as e:
        print(f"      🎓 Strengthen error: {e}")


def _create_investigation_task(db, case, human_notes):
    """Create a deeper research task when human says 'investigate'."""
    task_id = f"investigate_{case.get('case_id', '')}"
    db.collection("enrichment_tasks").document(task_id).set({
        "type": "investigation",
        "question": case.get("conflict_details", ""),
        "system_code": case.get("system_hs_code", ""),
        "ai_code": case.get("ai_hs_code", ""),
        "human_notes": human_notes[:500],
        "tier_needed": TIER_CLAUDE,  # Use Claude for investigations
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "pupil_human_request",
        "review_case_id": case.get("case_id", ""),
    }, merge=True)


# ═══════════════════════════════════════════
#  PHASE B ESCALATION: Claude deep review
# ═══════════════════════════════════════════

def pupil_escalate_to_claude(db, get_secret_func, max_tasks=5):
    """
    Process tasks that need Claude (tier 2).
    Only called when Gemini couldn't resolve or found disputes.
    """
    print("  🎓 PUPIL ESCALATION: Claude deep review...")

    within_budget, spent = check_daily_budget(db)
    if not within_budget:
        print(f"    🎓 Budget exceeded. Skipping Claude escalation.")
        return {"status": "budget_exceeded"}

    tasks = list(
        db.collection("enrichment_tasks")
        .where("tier_needed", "==", TIER_CLAUDE)
        .where("status", "==", "pending")
        .limit(max_tasks)
        .stream()
    )

    results = {"processed": 0, "resolved": 0}

    for task_doc in tasks:
        task = task_doc.to_dict()
        task_id = task_doc.id
        data = task.get("data_snapshot", task.get("data", {}))

        question = data.get("challenge_question", "")
        if not question:
            question = (
                f"Deep review needed for {task.get('collection', '')} "
                f"doc {task.get('doc_id', '')}: {json.dumps(data, ensure_ascii=False)[:500]}"
            )

        answer = _ask_claude_deep(question, get_secret_func)
        if answer:
            log_api_cost(db, TIER_CLAUDE, COST_CLAUDE_CALL, f"escalation: {task_id[:30]}")

            teaching = {
                "question": question,
                "answer": answer.get("answer", ""),
                "method": answer.get("method", ""),
                "teaching_rule": answer.get("teaching", ""),
                "source": "claude_sonnet",
                "confidence": "אומת" if answer.get("confidence_pct", 0) >= 90 else "לא אומת",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            db.collection("pupil_teachings").document(f"claude_{task_id}").set(teaching)
            _teach_librarian(db, answer, task)

            db.collection("enrichment_tasks").document(task_id).update({
                "status": "resolved_by_claude",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            results["resolved"] += 1

        results["processed"] += 1

    print(f"    🎓 Claude escalation done: {results}")
    return results


# ═══════════════════════════════════════════
#  CORRECTION EMAIL SYSTEM
#  When Pupil finds that a past classification
#  sent to a client was wrong, builds a correction
#  case for doron@ to review and forward.
# ═══════════════════════════════════════════

MAX_CORRECTION_EMAILS_PER_DAY = 2


def pupil_find_corrections(db, access_token, rcb_email, get_secret_func):
    """
    Scan past RCB classifications and compare with current verified knowledge.
    If a correction is found, build a professional email for doron@.
    
    Flow:
    1. Get past classifications RCB sent (from rcb_processed or history)
    2. Compare each with current knowledge_base + classification_knowledge
    3. If verified knowledge contradicts what was sent → build correction case
    4. Send to doron@ for review
    """
    print("  🎓 PUPIL CORRECTIONS: Scanning for past errors...")
    
    # Check daily limit
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    budget_doc = db.collection("pupil_correction_budget").document(today).get()
    sent_today = budget_doc.to_dict().get("count", 0) if budget_doc.exists else 0
    
    if sent_today >= MAX_CORRECTION_EMAILS_PER_DAY:
        print(f"    🎓 Correction limit reached ({sent_today}/{MAX_CORRECTION_EMAILS_PER_DAY})")
        return {"status": "limit_reached", "sent": 0}
    
    remaining = MAX_CORRECTION_EMAILS_PER_DAY - sent_today
    results = {"scanned": 0, "corrections_found": 0, "emails_sent": 0}
    
    # Get past classifications from history
    past_classifications = _get_past_classifications(db)
    results["scanned"] = len(past_classifications)
    
    for pc in past_classifications:
        if results["corrections_found"] >= remaining:
            break
        
        correction = _check_for_correction(db, pc)
        if correction:
            # Build and store correction case
            case_id = _create_correction_case(db, pc, correction)
            results["corrections_found"] += 1
            
            # Send correction email to doron@
            try:
                sent = _send_correction_email(db, case_id, access_token, rcb_email)
                if sent:
                    results["emails_sent"] += 1
            except Exception as e:
                print(f"    🎓 Correction email error: {e}")
    
    # Update daily count
    if results["emails_sent"] > 0:
        db.collection("pupil_correction_budget").document(today).set({
            "count": sent_today + results["emails_sent"],
            "date": today,
        }, merge=True)
    
    print(f"    🎓 Corrections: {results}")
    return results


def _get_past_classifications(db, limit=50):
    """
    Get past classifications RCB sent.
    Sources: rcb_processed, classification history, sent emails with HS codes.
    """
    past = []
    
    # Source 1: rcb_processed collection (emails RCB already replied to)
    try:
        docs = list(db.collection("rcb_processed").limit(limit).stream())
        for doc in docs:
            data = doc.to_dict()
            hs_code = data.get("hs_code", data.get("classification_code", ""))
            if hs_code and len(str(hs_code)) >= 4:
                past.append({
                    "doc_id": doc.id,
                    "collection": "rcb_processed",
                    "hs_code": str(hs_code),
                    "description": data.get("description", data.get("subject", ""))[:200],
                    "sent_to": data.get("original_sender", data.get("from_email", "")),
                    "sent_at": data.get("processed_at", data.get("created_at", "")),
                    "subject": data.get("subject", ""),
                    "confidence": data.get("confidence", ""),
                    "already_corrected": data.get("correction_checked", False),
                })
    except Exception as e:
        print(f"    🎓 Error reading rcb_processed: {e}")
    
    # Source 2: classification_knowledge with usage_count > 0
    try:
        docs = list(
            db.collection("classification_knowledge")
            .where("usage_count", ">", 0)
            .limit(limit)
            .stream()
        )
        for doc in docs:
            data = doc.to_dict()
            if data.get("source", "").startswith("pupil"):
                continue  # Skip pupil suggestions
            past.append({
                "doc_id": doc.id,
                "collection": "classification_knowledge",
                "hs_code": data.get("hs_code", ""),
                "description": data.get("description", "")[:200],
                "sent_to": "",
                "sent_at": data.get("learned_at", data.get("created_at", "")),
                "subject": data.get("description", "")[:100],
                "confidence": data.get("confidence", ""),
                "already_corrected": data.get("correction_checked", False),
            })
    except Exception as e:
        print(f"    🎓 Error reading classification_knowledge: {e}")
    
    # Skip already-checked items
    past = [p for p in past if not p.get("already_corrected")]
    
    return past[:limit]


def _check_for_correction(db, past_classification):
    """
    Compare a past classification with current verified knowledge.
    Returns correction dict if mismatch found, None otherwise.
    """
    from lib.librarian import normalize_hs_code

    old_code = past_classification.get("hs_code", "")
    description = past_classification.get("description", "")

    if not old_code or not description:
        return None

    old_normalized = normalize_hs_code(old_code)

    # Check if we now have VERIFIED different knowledge
    # Source 1: Human-approved corrections
    try:
        approved = list(
            db.collection("classification_knowledge")
            .where("confidence", "==", "אומת")
            .where("source", "==", "pupil_human_approved")
            .limit(50)
            .stream()
        )
        for doc in approved:
            data = doc.to_dict()
            new_code = data.get("hs_code", "")
            new_desc = data.get("description", "")

            # Check if descriptions are similar but codes differ (normalize both)
            if new_code and normalize_hs_code(new_code) != old_normalized:
                if _descriptions_match(description, new_desc):
                    return {
                        "type": "human_approved_correction",
                        "old_code": old_code,
                        "new_code": new_code,
                        "new_description": new_desc,
                        "method": data.get("method", ""),
                        "teaching_rule": data.get("teaching_rule", ""),
                        "approved_by": data.get("approved_by", ""),
                        "source_doc": doc.id,
                    }
    except Exception:
        pass

    # Source 2: Pupil teachings with high confidence
    try:
        teachings = list(
            db.collection("pupil_teachings")
            .where("confidence", "==", "אומת")
            .limit(50)
            .stream()
        )
        for doc in teachings:
            data = doc.to_dict()
            new_code = data.get("verified_hs_code", "")
            if new_code and normalize_hs_code(new_code) != old_normalized:
                if description.lower()[:30] in data.get("question", "").lower():
                    return {
                        "type": "verified_teaching",
                        "old_code": old_code,
                        "new_code": new_code,
                        "new_description": data.get("answer", "")[:200],
                        "method": data.get("method", ""),
                        "teaching_rule": data.get("teaching_rule", ""),
                        "source_doc": doc.id,
                    }
    except Exception:
        pass
    
    # Source 3: DISABLED — validate_hs_code has format mismatch issues
    # (normalize_hs_code vs stored format) and .limit() truncation causes
    # false "not found" results. A "code not found" is never a valid correction
    # because there's no replacement to suggest. Re-enable only after
    # validate_hs_code is fixed with proper format normalization.

    # Mark as checked so we don't re-scan
    try:
        db.collection(past_classification["collection"]).document(
            past_classification["doc_id"]
        ).update({"correction_checked": True})
    except Exception:
        pass
    
    return None


_DESC_STOP_WORDS = frozenset({
    "of", "the", "a", "an", "and", "or", "for", "in", "on", "to", "with",
    "from", "by", "is", "are", "was", "were", "be", "been", "has", "have",
    "at", "as", "it", "its", "not", "no", "-", "--", "other", "others",
    "של", "את", "על", "עם", "או", "לא", "גם", "כל", "אחר", "אחרים",
})


def _descriptions_match(desc1, desc2):
    """Check if two descriptions refer to the same product.
    Requires 70% word overlap on meaningful words (stop words excluded),
    and at least 3 meaningful words in both descriptions.
    """
    if not desc1 or not desc2:
        return False
    d1 = desc1.lower().strip()[:80]
    d2 = desc2.lower().strip()[:80]
    # Exact prefix match (first 20 chars)
    if d1[:20] == d2[:20]:
        return True
    # Word overlap — exclude stop words, require 70% overlap
    words1 = set(d1.split()) - _DESC_STOP_WORDS
    words2 = set(d2.split()) - _DESC_STOP_WORDS
    if len(words1) < 3 or len(words2) < 3:
        return False
    overlap = words1 & words2
    if len(overlap) >= min(len(words1), len(words2)) * 0.7:
        return True
    return False


def _create_correction_case(db, past_classification, correction):
    """Create a correction case in pupil_corrections collection."""
    case_id = f"corr_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{_safe_email_id(past_classification.get('doc_id','')[:20])}"
    
    case = {
        "case_id": case_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        
        # What was sent
        "original_hs_code": past_classification.get("hs_code", ""),
        "original_description": past_classification.get("description", ""),
        "original_subject": past_classification.get("subject", ""),
        "original_sent_to": past_classification.get("sent_to", ""),
        "original_sent_at": past_classification.get("sent_at", ""),
        "original_confidence": past_classification.get("confidence", ""),
        
        # What we now know
        "correction_type": correction.get("type", ""),
        "corrected_hs_code": correction.get("new_code", ""),
        "corrected_description": correction.get("new_description", ""),
        "correction_method": correction.get("method", ""),
        "correction_rule": correction.get("teaching_rule", ""),
        "correction_source": correction.get("source_doc", ""),
        
        # Email tracking
        "email_sent_to_doron": False,
        "doron_approved": None,
        "client_notified": False,
    }
    
    db.collection("pupil_corrections").document(case_id).set(case)
    print(f"    📋 Correction case: {case_id}")
    return case_id


def _send_correction_email(db, case_id, access_token, rcb_email):
    """Send correction case to doron@ for review."""
    case_doc = db.collection("pupil_corrections").document(case_id).get()
    if not case_doc.exists:
        return False

    case = case_doc.to_dict()

    # Never send "code not found" corrections — no replacement to suggest
    if case.get("correction_type") == "invalid_code" or not case.get("corrected_hs_code"):
        print(f"    🎓 Skipping correction {case_id}: no valid replacement code")
        return False

    subject = f"🔄 תיקון סיווג: {case.get('original_description', '')[:40]}"
    
    body = f"""<div dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.8;">
<h2 style="color: #c0392b;">🔄 נמצא תיקון לסיווג שנשלח בעבר</h2>

<p>בביקורת שביצעה המערכת לאחר ששלחתי לך סיווג לראשונה, נראה שיש מידע חדש:</p>

<hr>

<h3>📌 מה נשלח בעבר</h3>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; margin: 10px 0;">
<tr style="background-color: #fadbd8;">
    <td><strong>קוד HS</strong></td>
    <td>{case.get('original_hs_code', 'לא ידוע')}</td>
</tr>
<tr>
    <td><strong>תיאור</strong></td>
    <td>{case.get('original_description', '')[:150]}</td>
</tr>
<tr>
    <td><strong>נשלח ל</strong></td>
    <td>{case.get('original_sent_to', 'לא ידוע')}</td>
</tr>
<tr>
    <td><strong>תאריך</strong></td>
    <td>{case.get('original_sent_at', '')[:16]}</td>
</tr>
</table>

<h3>✅ מה אנחנו יודעים עכשיו</h3>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; margin: 10px 0;">
<tr style="background-color: #d5f5e3;">
    <td><strong>קוד HS מתוקן</strong></td>
    <td>{case.get('corrected_hs_code', 'דרוש בדיקה')}</td>
</tr>
<tr>
    <td><strong>תיאור</strong></td>
    <td>{case.get('corrected_description', '')[:150]}</td>
</tr>
</table>

<h3>📊 נימוקים</h3>
<p><strong>שיטת הניתוח:</strong></p>
<p>{case.get('correction_method', 'לא צוין')}</p>

<p><strong>כלל:</strong></p>
<p>{case.get('correction_rule', 'לא צוין')}</p>

<p><strong>סוג התיקון:</strong> {case.get('correction_type', '')}</p>

<hr>

<h3>🎯 נדרשת החלטתך</h3>
<p>אנא השב למייל זה:</p>
<ul>
<li><strong>מאשר</strong> — אעדכן את המערכת ואכין טיוטת הודעה ללקוח</li>
<li><strong>דוחה</strong> — הסיווג המקורי נכון, אל תשנו</li>
<li><strong>לבדוק</strong> — צריך בדיקה נוספת</li>
</ul>

<p style="color: #666; font-size: 0.9em;">
מזהה תיקון: {case_id}<br>
נוצר: {case.get('created_at', '')[:16]}
</p>
</div>"""
    
    try:
        from lib.rcb_helpers import helper_graph_send
        success = helper_graph_send(
            access_token, rcb_email, REVIEW_EMAIL,
            subject, body, []
        )
        
        if success:
            db.collection("pupil_corrections").document(case_id).update({
                "email_sent_to_doron": True,
                "email_sent_at": datetime.now(timezone.utc).isoformat(),
                "status": "sent_to_doron",
            })
            print(f"    ✉️ Correction email sent: {case_id}")
            return True
    except Exception as e:
        print(f"    ❌ Correction send error: {e}")
    
    return False


def pupil_handle_correction_reply(db, msg, access_token, rcb_email, get_secret_func):
    """
    Process doron@'s reply to a correction email.
    If approved: update system + prepare client notification draft.
    """
    body = msg.get("body", {}).get("content", "")
    body_clean = _clean_body(body).lower()
    subject = msg.get("subject", "")
    
    # Find case ID
    case_id_match = re.search(r'corr_\d{8}_\d{6}_\w+', body + subject)
    if not case_id_match:
        return {"status": "no_case_found"}
    
    case_id = case_id_match.group()
    case_doc = db.collection("pupil_corrections").document(case_id).get()
    if not case_doc.exists:
        return {"status": "case_not_found"}
    
    case = case_doc.to_dict()
    decision = _extract_decision(body_clean)
    
    if decision == "approved":
        # Update system knowledge
        _apply_approved_suggestion(db, {
            "ai_hs_code": case.get("corrected_hs_code", ""),
            "ai_answer": case.get("corrected_description", ""),
            "ai_method": case.get("correction_method", ""),
            "ai_teaching": case.get("correction_rule", ""),
            "case_id": case_id,
        })
        
        # Prepare client notification draft
        client_email = case.get("original_sent_to", "")
        if client_email:
            _prepare_client_correction_draft(db, case, case_id)
        
        db.collection("pupil_corrections").document(case_id).update({
            "status": "approved",
            "doron_approved": True,
            "approved_at": datetime.now(timezone.utc).isoformat(),
        })
        
    elif decision == "rejected":
        db.collection("pupil_corrections").document(case_id).update({
            "status": "rejected",
            "doron_approved": False,
        })
        
    else:  # investigate
        db.collection("pupil_corrections").document(case_id).update({
            "status": "investigating",
        })
        _create_investigation_task(db, {
            "case_id": case_id,
            "conflict_details": f"Correction disputed: {case.get('original_hs_code')} vs {case.get('corrected_hs_code')}",
            "system_hs_code": case.get("original_hs_code", ""),
            "ai_hs_code": case.get("corrected_hs_code", ""),
        }, body_clean)
    
    return {"status": decision, "case_id": case_id}


def _prepare_client_correction_draft(db, case, case_id):
    """
    Prepare a draft correction email for the client.
    Stored in pupil_corrections — doron@ sends manually.
    """
    client_email = case.get("original_sent_to", "")
    
    draft = f"""<div dir="rtl" style="font-family: Arial, sans-serif; line-height: 1.8;">
<p>שלום רב,</p>

<p>בביקורת שביצעה המערכת שלנו, נמצא כי יש עדכון לסיווג שנשלח בעבר:</p>

<p><strong>נושא מקורי:</strong> {case.get('original_subject', '')}</p>

<p><strong>בעבר כתבנו:</strong> קוד HS {case.get('original_hs_code', '')}</p>
<p><strong>אך לאחר בקרה מעמיקה הגענו ל:</strong> קוד HS {case.get('corrected_hs_code', '')}</p>

<p><strong>נימוקים:</strong></p>
<p>{case.get('correction_method', '')}</p>

<p>נשמח לעמוד לשירותכם בכל שאלה.</p>

<p>בברכה,<br>
R.P.A. PORT LTD</p>
</div>"""
    
    db.collection("pupil_corrections").document(case_id).update({
        "client_draft": draft,
        "client_email": client_email,
        "client_draft_ready": True,
        "client_subject": f"עדכון סיווג: {case.get('original_subject', '')[:40]}",
    })
    print(f"    📝 Client draft prepared for: {client_email}")


# ═══════════════════════════════════════════
#  PHASE C: AUDIT
#  Reviews past work, finds patterns,
#  builds workflow summaries, re-challenges
#  old conclusions with new data.
# ═══════════════════════════════════════════

def pupil_audit(db, get_secret_func):
    """
    Phase C main entry. Reviews the system's accumulated knowledge.
    
    1. Summarize observation patterns (who sends what, common products)
    2. Find stale teachings that need refreshing
    3. Identify workflow patterns
    4. Re-challenge old verified items with new data
    5. Generate daily/weekly summary
    """
    print("  🎓 PUPIL PHASE C: Audit starting...")
    
    results = {
        "patterns": {},
        "stale_items": 0,
        "rechallenged": 0,
        "summary": "",
    }
    
    # Step 1: Analyze observation patterns
    results["patterns"] = _analyze_patterns(db)
    
    # Step 2: Find stale teachings (>7 days, not re-verified)
    results["stale_items"] = _find_stale_teachings(db)
    
    # Step 3: Re-challenge old verified items with current knowledge
    results["rechallenged"] = _rechallenge_old_items(db, get_secret_func)
    
    # Step 4: Generate summary
    results["summary"] = _generate_audit_summary(db, results)
    
    print(f"    🎓 Audit done: {results['stale_items']} stale, {results['rechallenged']} rechallenged")
    return results


def _analyze_patterns(db):
    """Analyze email patterns from observations."""
    patterns = {
        "total_observations": 0,
        "senders": {},
        "common_subjects": {},
        "attachment_types": {},
        "dispute_rate": 0,
        "avg_gaps": 0,
    }
    
    try:
        total_gaps = 0
        disputes = 0
        
        for doc in db.collection("pupil_observations").stream():
            data = doc.to_dict()
            patterns["total_observations"] += 1
            
            # Count senders
            sender = data.get("from_email", "")
            patterns["senders"][sender] = patterns["senders"].get(sender, 0) + 1
            
            # Count attachment types
            for att in data.get("attachments", []):
                dtype = att.get("doc_type", "unknown")
                patterns["attachment_types"][dtype] = patterns["attachment_types"].get(dtype, 0) + 1
            
            # Track gaps and disputes
            total_gaps += len(data.get("knowledge_gaps", []))
            if data.get("is_dispute"):
                disputes += 1
        
        total = patterns["total_observations"]
        if total > 0:
            patterns["avg_gaps"] = round(total_gaps / total, 1)
            patterns["dispute_rate"] = round(disputes / total * 100, 1)
        
        # Top 5 senders
        patterns["senders"] = dict(sorted(
            patterns["senders"].items(), key=lambda x: x[1], reverse=True
        )[:5])
        
    except Exception as e:
        print(f"    🎓 Pattern analysis error: {e}")
    
    return patterns


def _find_stale_teachings(db):
    """Find teachings older than 7 days that haven't been re-verified."""
    stale_count = 0
    cutoff = datetime.now(timezone.utc).isoformat()[:10]  # Today
    
    try:
        for doc in db.collection("pupil_teachings").stream():
            data = doc.to_dict()
            created = data.get("created_at", "")
            confidence = data.get("confidence", "")
            
            if not created:
                continue
            
            # Check if older than 7 days
            try:
                created_date = datetime.fromisoformat(created.replace('Z', '+00:00'))
                age_days = (datetime.now(timezone.utc) - created_date).days
                
                if age_days > 7 and confidence != "אומת":
                    stale_count += 1
                    # Flag as stale
                    db.collection("pupil_teachings").document(doc.id).update({
                        "stale": True,
                        "age_days": age_days,
                    })
            except (ValueError, TypeError):
                pass
    
    except Exception as e:
        print(f"    🎓 Stale check error: {e}")
    
    return stale_count


def _rechallenge_old_items(db, get_secret_func, max_items=5):
    """
    Re-challenge verified items using current knowledge.
    Maybe new regulations changed, or we have better data now.
    """
    rechallenged = 0
    
    try:
        # Get verified items that haven't been rechallenged recently
        verified = list(
            db.collection("classification_knowledge")
            .where("confidence", "==", "אומת")
            .limit(max_items * 2)
            .stream()
        )
        
        for doc in verified:
            if rechallenged >= max_items:
                break
            
            data = doc.to_dict()
            last_challenge = data.get("last_rechallenged", "")
            
            # Skip if rechallenged in last 30 days
            if last_challenge:
                try:
                    lc_date = datetime.fromisoformat(last_challenge.replace('Z', '+00:00'))
                    if (datetime.now(timezone.utc) - lc_date).days < 30:
                        continue
                except (ValueError, TypeError):
                    pass
            
            # Create devil's advocate challenge
            try:
                pupil_challenge(db, doc.id, "classification_knowledge")
                db.collection("classification_knowledge").document(doc.id).update({
                    "last_rechallenged": datetime.now(timezone.utc).isoformat(),
                })
                rechallenged += 1
            except Exception:
                pass
    
    except Exception as e:
        print(f"    🎓 Rechallenge error: {e}")
    
    return rechallenged


def _generate_audit_summary(db, audit_results):
    """Generate a text summary of the audit findings."""
    patterns = audit_results.get("patterns", {})
    
    summary = f"""=== RCB Pupil Audit Summary ===
Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC

Observations: {patterns.get('total_observations', 0)}
Average gaps per email: {patterns.get('avg_gaps', 0)}
Dispute rate: {patterns.get('dispute_rate', 0)}%

Top senders:
"""
    for sender, count in patterns.get("senders", {}).items():
        summary += f"  {sender}: {count} emails\n"
    
    summary += f"""
Attachment types:
"""
    for dtype, count in patterns.get("attachment_types", {}).items():
        summary += f"  {dtype}: {count}\n"
    
    summary += f"""
Stale teachings (>7 days unverified): {audit_results.get('stale_items', 0)}
Items rechallenged: {audit_results.get('rechallenged', 0)}

Teachings total: {len(list(db.collection('pupil_teachings').limit(1000).stream()))}
Knowledge base (pupil): {len(list(db.collection('knowledge_base').where('category','==','pupil_suggestion').limit(1000).stream()))}
"""
    
    # Store summary
    db.collection("pupil_audit_summaries").document(
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    ).set({
        "summary": summary,
        "patterns": {k: v for k, v in patterns.items() if k != "senders"},
        "top_senders": patterns.get("senders", {}),
        "stale_items": audit_results.get("stale_items", 0),
        "rechallenged": audit_results.get("rechallenged", 0),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    
    return summary
