"""
Inbox Relearner — one-time relearning from cc@rpa-port.co.il mailbox.
=====================================================================
Scans the full cc@ Outlook mailbox via Graph API and extracts knowledge
from every email. READ ONLY — no sending, no replies, no actions.

Entry point: relearn_inbox_batch(db, get_secret_func) — called by Cloud Function.
Batch cursor: processes 50 emails per run, cursor-based, idempotent.
"""

import re
import time
import hashlib
import traceback
from datetime import datetime, timezone
from html import unescape

import requests

# ═══════════════════════════════════════════════════════════
#  TIER 1 PROTECTION — NEVER WRITE TO THESE COLLECTIONS
# ═══════════════════════════════════════════════════════════

PROTECTED_COLLECTIONS = frozenset({
    "tariff", "chapter_notes", "free_import_order",
    "framework_order", "FIO", "FEO", "ordinance",
    "learned_classifications", "classification_history",
})

_ALLOWED_WRITE_COLLECTIONS = frozenset({
    "inbox_learning",
    "inbox_learning_log",
    "inbox_learning_state",
})


class ProtectedCollectionError(Exception):
    """Raised when code attempts to write to a Tier 1 protected collection."""
    pass


def _safe_write(db, collection, doc_id, data):
    """Write to Firestore with Tier 1 protection guard.
    Guard runs BEFORE any Firestore write — no exceptions."""
    if collection in PROTECTED_COLLECTIONS:
        raise ProtectedCollectionError(
            f"ABORT: Attempted write to Tier 1 collection '{collection}' "
            f"(doc '{doc_id}'). Inbox relearner cannot touch Tier 1 data."
        )
    if collection not in _ALLOWED_WRITE_COLLECTIONS:
        raise ProtectedCollectionError(
            f"ABORT: Attempted write to unknown collection '{collection}' "
            f"(doc '{doc_id}'). Only {_ALLOWED_WRITE_COLLECTIONS} are allowed."
        )
    db.collection(collection).document(doc_id).set(data, merge=True)


def _tier2_meta():
    """Return metadata fields required on every document."""
    return {
        "data_tier": "learning",
        "is_authoritative": False,
        "source": "cc_mailbox_relearn",
        "fetched_at": datetime.now(timezone.utc),
    }


# ═══════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════

_BATCH_SIZE = 50
_MAX_RUNTIME_SEC = 480
# cc@ is a distribution group (no own mailbox). All CC traffic lands in rcb@ inbox.
# We scan rcb@ and learn from ALL emails (both direct and CC'd).

# Graph API
_GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# HS code patterns (reuse existing patterns)
_HS_CODE_RE = re.compile(
    r'\b(\d{4}[\.\s]?\d{2}[\.\s]?\d{2,6})\b'
    r'|'
    r'\b(\d{2}\.\d{2}\.\d{4,6}(?:/\d)?)\b'
)

# Document type keywords (lightweight version — no external imports needed)
_DOC_TYPE_SIGNALS = {
    "commercial_invoice": {
        "keywords": ["invoice", "חשבונית", "commercial invoice", "proforma", "price list", "הצעת מחיר"],
        "min_score": 1,
    },
    "packing_list": {
        "keywords": ["packing list", "רשימת אריזה", "packing note", "gross weight", "net weight"],
        "min_score": 1,
    },
    "bill_of_lading": {
        "keywords": ["bill of lading", "b/l", "bl number", "שטר מטען", "shipped on board", "consignee"],
        "min_score": 1,
    },
    "air_waybill": {
        "keywords": ["air waybill", "awb", "שטר מטען אווירי", "mawb", "hawb"],
        "min_score": 1,
    },
    "arrival_notice": {
        "keywords": ["arrival notice", "notice of arrival", "הודעת הגעה", "eta"],
        "min_score": 1,
    },
    "delivery_order": {
        "keywords": ["delivery order", "פקודת מסירה", "release order", "getpass", "gate pass"],
        "min_score": 1,
    },
    "customs_declaration": {
        "keywords": ["customs declaration", "רשימון", "הצהרת מכס", "entry number"],
        "min_score": 1,
    },
    "booking_confirmation": {
        "keywords": ["booking confirmation", "booking ref", "booking number"],
        "min_score": 1,
    },
    "certificate_of_origin": {
        "keywords": ["certificate of origin", "תעודת מקור", "eur.1", "form a"],
        "min_score": 1,
    },
}

# Container regex (ISO 6346)
_CONTAINER_RE = re.compile(r'\b([A-Z]{4}\d{7})\b')

# BOL patterns
_BOL_RE = re.compile(r'\b(?:B/?L|BOL|BL)\s*(?:No\.?|#|:)?\s*([A-Z0-9]{6,25})\b', re.IGNORECASE)

# AWB pattern
_AWB_RE = re.compile(r'\b(\d{3}[-\s]?\d{8})\b')

# Product description extraction (simple heuristic)
_PRODUCT_RE = re.compile(
    r'(?:goods|commodity|description|product|item|פריט|תיאור|סחורה|טובין)\s*[:：]\s*(.{5,120})',
    re.IGNORECASE
)


# ═══════════════════════════════════════════════════════════
#  GRAPH API ACCESS (reuses existing auth pattern)
# ═══════════════════════════════════════════════════════════

def _get_graph_token_and_email(get_secret_func):
    """Get Graph API token + rcb email using the same secrets as the main system.
    Returns (access_token, rcb_email) or (None, None)."""
    try:
        tenant = get_secret_func('RCB_GRAPH_TENANT_ID')
        client_id = get_secret_func('RCB_GRAPH_CLIENT_ID')
        client_secret = get_secret_func('RCB_GRAPH_CLIENT_SECRET')
        rcb_email = get_secret_func('RCB_EMAIL')
        if not all([tenant, client_id, client_secret, rcb_email]):
            print("[RELEARN] Missing Graph API secrets")
            return None, None
        resp = requests.post(
            f"https://login.microsoftonline.com/{tenant.strip()}/oauth2/v2.0/token",
            data={
                'client_id': client_id.strip(),
                'client_secret': client_secret.strip(),
                'scope': 'https://graph.microsoft.com/.default',
                'grant_type': 'client_credentials',
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get('access_token'), rcb_email.strip()
        print(f"[RELEARN] Token error: {resp.status_code} {resp.text[:200]}")
        return None, None
    except Exception as e:
        print(f"[RELEARN] Token exception: {e}")
        return None, None


def _fetch_messages(access_token, mailbox, skip=0, top=50):
    """Fetch a page of messages from mailbox. Oldest first for cursor stability."""
    url = f"{_GRAPH_BASE}/users/{mailbox}/mailFolders/inbox/messages"
    params = {
        '$top': top,
        '$skip': skip,
        '$orderby': 'receivedDateTime asc',
        '$select': 'id,internetMessageId,subject,from,toRecipients,ccRecipients,'
                   'receivedDateTime,bodyPreview,body,hasAttachments,conversationId',
    }
    try:
        resp = requests.get(url, headers={'Authorization': f'Bearer {access_token}'}, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data.get('value', []), data.get('@odata.nextLink')
        print(f"[RELEARN] Graph messages error: {resp.status_code}")
        return [], None
    except Exception as e:
        print(f"[RELEARN] Graph messages exception: {e}")
        return [], None


# ═══════════════════════════════════════════════════════════
#  EMAIL EXTRACTION (read-only analysis)
# ═══════════════════════════════════════════════════════════

def _strip_html(html):
    """Remove HTML tags, decode entities, collapse whitespace."""
    if not html:
        return ""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _detect_doc_types(text):
    """Detect document types from text using keyword signals."""
    if not text:
        return []
    text_lower = text.lower()
    detected = []
    for doc_type, info in _DOC_TYPE_SIGNALS.items():
        score = sum(1 for kw in info["keywords"] if kw.lower() in text_lower)
        if score >= info["min_score"]:
            detected.append(doc_type)
    return detected


def _extract_hs_codes(text):
    """Extract HS code candidates from text."""
    if not text:
        return []
    codes = set()
    for m in _HS_CODE_RE.finditer(text):
        code = m.group(1) or m.group(2)
        if code:
            clean = code.replace(".", "").replace(" ", "").replace("/", "")
            if len(clean) >= 4 and clean[:4].isdigit():
                codes.add(code.strip())
    return sorted(codes)[:10]


def _extract_containers(text):
    """Extract container numbers from text."""
    if not text:
        return []
    return list(set(_CONTAINER_RE.findall(text.upper())))[:20]


def _extract_bols(text):
    """Extract BOL numbers from text."""
    if not text:
        return []
    return list(set(m.group(1) for m in _BOL_RE.finditer(text)))[:10]


def _extract_awbs(text):
    """Extract AWB numbers from text."""
    if not text:
        return []
    return list(set(_AWB_RE.findall(text)))[:10]


def _extract_products(text):
    """Extract product descriptions from text."""
    if not text:
        return []
    return list(set(m.group(1).strip() for m in _PRODUCT_RE.finditer(text)))[:5]


def _analyze_email(msg):
    """Extract all learnable data from one email message. Pure function, no I/O."""
    subject = msg.get('subject', '') or ''
    from_addr = msg.get('from', {}).get('emailAddress', {}).get('address', '') or ''
    from_name = msg.get('from', {}).get('emailAddress', {}).get('name', '') or ''
    body_html = msg.get('body', {}).get('content', '') or ''
    body_text = _strip_html(body_html)
    received = msg.get('receivedDateTime', '')

    # Combine subject + body for analysis
    full_text = f"{subject} {body_text}"

    to_addrs = [r.get('emailAddress', {}).get('address', '')
                for r in msg.get('toRecipients', []) if r.get('emailAddress')]
    cc_addrs = [r.get('emailAddress', {}).get('address', '')
                for r in msg.get('ccRecipients', []) if r.get('emailAddress')]

    return {
        "subject": subject,
        "from_email": from_addr.lower(),
        "from_name": from_name,
        "to_recipients": to_addrs,
        "cc_recipients": cc_addrs,
        "received_at": received,
        "has_attachments": msg.get('hasAttachments', False),
        "conversation_id": msg.get('conversationId', ''),
        "body_snippet": body_text[:500],
        # Extracted knowledge
        "hs_codes": _extract_hs_codes(full_text),
        "containers": _extract_containers(full_text),
        "bols": _extract_bols(full_text),
        "awbs": _extract_awbs(full_text),
        "product_descriptions": _extract_products(full_text),
        "document_types": _detect_doc_types(full_text),
        "body_length": len(body_text),
    }


# ═══════════════════════════════════════════════════════════
#  CURSOR / STATE
# ═══════════════════════════════════════════════════════════

def _load_state(db):
    """Read cursor from inbox_learning_state/cursor."""
    doc = db.collection("inbox_learning_state").document("cursor").get()
    if doc.exists:
        return doc.to_dict()
    return {"skip": 0, "total_processed": 0, "total_errors": 0, "last_run": None, "completed": False}


def _save_state(db, state):
    """Write cursor to inbox_learning_state/cursor."""
    _safe_write(db, "inbox_learning_state", "cursor", {
        **state,
        **_tier2_meta(),
    })


# ═══════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

def relearn_inbox_batch(db, get_secret_func):
    """Process a batch of 50 emails from cc@ mailbox.
    Args:
        db: Firestore client
        get_secret_func: function to fetch secrets from Secret Manager
    Returns:
        dict with run summary
    """
    run_start = time.time()
    now = datetime.now(timezone.utc)
    run_id = f"relearn_{now.strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(now.timestamp()).encode()).hexdigest()[:6]}"

    print(f"[RELEARN] === Batch {run_id} starting ===")

    # Load state
    state = _load_state(db)
    if state.get("completed"):
        print("[RELEARN] Full scan already completed. Nothing to do.")
        return {"status": "already_completed", "run_id": run_id}

    skip = state.get("skip", 0)
    print(f"[RELEARN] Cursor: skip={skip}, total processed: {state.get('total_processed', 0)}")

    # Get Graph token + mailbox
    access_token, rcb_email = _get_graph_token_and_email(get_secret_func)
    if not access_token:
        print("[RELEARN] Failed to get Graph token. Aborting.")
        return {"status": "auth_error", "run_id": run_id}

    print(f"[RELEARN] Scanning mailbox: {rcb_email}")

    # Fetch batch of messages from rcb@ inbox (all CC traffic lands here)
    messages, next_link = _fetch_messages(access_token, rcb_email, skip=skip, top=_BATCH_SIZE)
    if not messages:
        print(f"[RELEARN] No more messages. Marking scan as complete.")
        state["completed"] = True
        state["last_run"] = now
        _save_state(db, state)
        _log_run(db, run_id, {
            "started_at": now, "completed_at": datetime.now(timezone.utc),
            "emails_processed": 0, "errors": [],
            "skip_before": skip, "skip_after": skip,
            "status": "scan_complete",
        })
        return {"status": "scan_complete", "emails_processed": 0, "run_id": run_id}

    print(f"[RELEARN] Fetched {len(messages)} messages from cc@ mailbox")

    processed = 0
    skipped = 0
    errors = []

    for msg in messages:
        # Runtime budget
        if time.time() - run_start >= _MAX_RUNTIME_SEC:
            print(f"[RELEARN] Runtime budget ({_MAX_RUNTIME_SEC}s) exhausted.")
            break

        msg_id = msg.get('id', '')
        internet_msg_id = msg.get('internetMessageId', '')

        # Generate stable doc ID from internet message ID (or Graph ID as fallback)
        stable_id = internet_msg_id or msg_id
        doc_id = hashlib.md5(stable_id.encode()).hexdigest()

        # Idempotent: skip if already learned
        existing = db.collection("inbox_learning").document(doc_id).get()
        if existing.exists:
            skipped += 1
            continue

        try:
            # Analyze email (pure function, read-only)
            extracted = _analyze_email(msg)

            # Write to inbox_learning
            doc = {
                "email_id": doc_id,
                "graph_id": msg_id,
                "internet_message_id": internet_msg_id,
                **extracted,
                **_tier2_meta(),
            }
            _safe_write(db, "inbox_learning", doc_id, doc)
            processed += 1

            if processed % 10 == 0:
                print(f"[RELEARN] {processed}/{len(messages)} processed...")

        except ProtectedCollectionError:
            raise  # abort entire run
        except Exception as e:
            error_msg = f"{doc_id}: {e}"
            print(f"[RELEARN] FAIL {error_msg}")
            errors.append(error_msg)

    # Update cursor
    new_skip = skip + len(messages)  # advance past this page regardless of individual failures
    state["skip"] = new_skip
    state["total_processed"] = state.get("total_processed", 0) + processed
    state["total_errors"] = state.get("total_errors", 0) + len(errors)
    state["last_run"] = datetime.now(timezone.utc)
    _save_state(db, state)

    # Log run
    _log_run(db, run_id, {
        "started_at": now,
        "completed_at": datetime.now(timezone.utc),
        "duration_sec": round(time.time() - run_start, 1),
        "emails_processed": processed,
        "emails_skipped": skipped,
        "emails_failed": len(errors),
        "errors": errors[:20],
        "skip_before": skip,
        "skip_after": new_skip,
        "status": "completed",
    })

    print(f"[RELEARN] === Done: {processed} learned, {skipped} skipped, {len(errors)} errors ===")
    return {
        "status": "completed",
        "run_id": run_id,
        "emails_processed": processed,
        "emails_skipped": skipped,
        "emails_failed": len(errors),
        "skip_after": new_skip,
    }


def _log_run(db, run_id, data):
    """Write run log to inbox_learning_log/{run_id}."""
    try:
        _safe_write(db, "inbox_learning_log", run_id, {
            **data,
            **_tier2_meta(),
        })
    except Exception as e:
        import traceback
        print(f"[RELEARN] Failed to write log {run_id}: {e}")
        traceback.print_exc()
        raise
