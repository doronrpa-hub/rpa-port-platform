"""
RCB Deal Identity Graph — Unified Identifier Linking
=====================================================
Session 46: Links every document identifier (B/L, AWB, container,
invoice, PO, booking, packing list, email thread) to a single deal_id.

Foundation for accurate self-learning and outcome tracking.

Firestore collection: deal_identity_graph
  One document per deal_id → all known identifiers for that shipment.

Integration points (READ ONLY — wiring is Session 47):
  - tracker.py: register identifiers when deals are created/updated
  - email_intent.py: link inbound emails to deals
  - pupil.py: use graph for learning associations
  - main.py: hook into email processing pipeline

═══════════════════════════════════════════════════════════
INDIRECT FEEDBACK LOOP — DESIGN NOTES (no code yet)
═══════════════════════════════════════════════════════════

When a customs declaration outcome arrives by email (approval,
correction, or rejection), the flow should be:

  1. Email arrives (airpaport@gmail.com or CC)
  2. extract_identifiers_from_email() pulls declaration number,
     B/L, container, HS codes from email body + attachments
  3. find_deal_by_identifier() matches to the original deal
  4. Outcome (approved HS code, corrected code, rejection reason)
     is recorded against the deal's classification in
     classification_memory
  5. If customs CORRECTED the code:
     - Original classification confidence is reduced
     - Corrected code is stored as ground truth (conf ~0.85)
     - Overnight brain flags for review
  6. If customs APPROVED:
     - Classification confidence is boosted
     - Stored as verified ground truth
  7. deal_identity_graph doc is updated with declaration number

This closes the learning loop: classification → declaration →
outcome → memory update → better future classifications.

The identity graph is the KEY enabler — without it, we cannot
reliably match a declaration outcome back to the original
classification request.
═══════════════════════════════════════════════════════════
"""

import re
import hashlib
from datetime import datetime, timezone

# ═══════════════════════════════════════════
#  COLLECTION NAME
# ═══════════════════════════════════════════

COLLECTION = "deal_identity_graph"

# ═══════════════════════════════════════════
#  IDENTIFIER FIELD NAMES (array fields in graph doc)
# ═══════════════════════════════════════════

IDENTIFIER_FIELDS = [
    "bl_numbers",
    "booking_refs",
    "awb_numbers",
    "container_numbers",
    "invoice_numbers",
    "po_numbers",
    "packing_list_refs",
    "email_thread_ids",
]

# Scalar identifier fields (one value per deal)
SCALAR_ID_FIELDS = [
    "client_ref",
    "internal_file_ref",
    "job_order_number",
    "file_number",
    "import_number",
    "export_number",
    "seped_number",
]

# All searchable fields (arrays + scalar)
ALL_SEARCHABLE_FIELDS = IDENTIFIER_FIELDS + SCALAR_ID_FIELDS

# ═══════════════════════════════════════════
#  LEARNED PATTERNS — overnight brain integration
# ═══════════════════════════════════════════
#
# Collection: learned_identifier_patterns
# The overnight brain watches cc@ email history and learns
# real-world identifier formats per client / shipping line.
# Initial regex patterns below are intentionally BROAD —
# the brain refines them over time from real data.
#
# Schema per doc:
#   pattern_id: str (auto)
#   field: str (e.g. "file_number", "job_order_number")
#   regex: str (learned regex pattern)
#   source: str ("cc_email" | "manual" | "brain_refined")
#   client_name: str (optional — client-specific pattern)
#   examples: [] (real values seen)
#   hit_count: int
#   last_seen: timestamp
#
LEARNED_PATTERNS_COLLECTION = "learned_identifier_patterns"

# ═══════════════════════════════════════════
#  EXTRACTION PATTERNS
# ═══════════════════════════════════════════
#
# Reuses proven patterns from tracker.py PATTERNS dict
# and document_parser.py, plus new patterns for invoice/PO.

# Container: ISO 6346 — 4 letters + 7 digits
_RE_CONTAINER = re.compile(r'\b([A-Z]{4}\d{7})\b', re.IGNORECASE)

# Bill of Lading — labeled
_RE_BL_LABELED = re.compile(
    r'(?:B/?L|BOL|BL|bill\s*of\s*lading|שטר\s*מטען)[:\s#]*([A-Z0-9][\w\-]{6,25})',
    re.IGNORECASE
)
# B/L — MSC format
_RE_BL_MSC = re.compile(r'\b(MEDURS\d{5,10})\b')
# B/L — carrier prefix patterns (common prefixes)
_RE_BL_PREFIX = re.compile(
    r'\b((?:ZIMU|MAEU|MSCU|HDMU|HLCU|COSU|CMDU|EISU|OOLU|YMLU)[A-Z0-9]{4,15})\b'
)

# AWB: airline prefix (3 digits) + serial (8 digits)
_RE_AWB_LABELED = re.compile(
    r'(?:AWB|MAWB|HAWB|air\s*waybill|שטר\s*מטען\s*אווירי)[:\s#]*(\d{3}[\s\-]?\d{7,8})',
    re.IGNORECASE
)
_RE_AWB_BARE = re.compile(r'\b(\d{3}[\s\-]\d{4}[\s\-]?\d{4})\b')

# Booking reference
_RE_BOOKING = re.compile(
    r'(?:booking|הזמנה|BKG|EBKG)[:\s#]*([A-Z0-9]{6,20})',
    re.IGNORECASE
)
_RE_BOOKING_EBKG = re.compile(r'\b(EBKG\d{6,12})\b')

# Invoice number
_RE_INVOICE = re.compile(
    r'(?:invoice|inv|חשבונית|חשבון)\s*(?:no|number|n[°o]|#|מס[\'.]?)?[.:\s]*([A-Za-z0-9][\w\-/]{2,25})',
    re.IGNORECASE
)

# Purchase Order
_RE_PO = re.compile(
    r'(?:P/?O|purchase\s*order|הזמנת\s*רכש)\s*(?:no|number|n[°o]|#|מס[\'.]?)?[.:\s]*([A-Za-z0-9][\w\-/]{2,25})',
    re.IGNORECASE
)

# Packing list reference
_RE_PACKING_LIST = re.compile(
    r'(?:packing\s*list|P/?L|רשימת\s*אריזה|מפרט\s*אריזות)\s*(?:no|number|n[°o]|#|מס[\'.]?)?[.:\s]*([A-Za-z0-9][\w\-/]{2,25})',
    re.IGNORECASE
)

# Client reference / file number
_RE_CLIENT_REF = re.compile(
    r'(?:your\s*ref|client\s*ref|מספר\s*תיק|תיק\s*לקוח)[.:\s#]*([A-Za-z0-9][\w\-/]{2,25})',
    re.IGNORECASE
)

# Internal file reference
_RE_INTERNAL_REF = re.compile(
    r'(?:our\s*ref|file\s*(?:no|number|#)|תיק\s*(?:מס|מספר))[.:\s#]*([A-Za-z0-9][\w\-/]{2,25})',
    re.IGNORECASE
)

# ── RPA PORT internal identifiers (broad patterns — brain refines) ──

# File number: starts with 4 (import) or 6 (transit/export), typically 5-8 digits
# Broad: any labeled file number reference
_RE_FILE_NUMBER = re.compile(
    r'(?:file\s*(?:no|number|#)|תיק\s*(?:מס[\'.]?|מספר|#)|מספר\s*תיק)[.:\s#]*([46]\d{4,7})',
    re.IGNORECASE
)
# Bare file number: 4xxxxx or 6xxxxx when preceded by context
_RE_FILE_NUMBER_BARE = re.compile(
    r'(?:^|[\s,;(])([46]\d{4,7})(?:[\s,;)]|$)'
)

# Job order number: internal work order
_RE_JOB_ORDER = re.compile(
    r'(?:job\s*(?:order|no|number|#)|הזמנת\s*עבודה|פקודת\s*עבודה)[.:\s#]*([A-Za-z0-9][\w\-/]{2,20})',
    re.IGNORECASE
)

# Import license/permit number (רישיון יבוא)
_RE_IMPORT_NUMBER = re.compile(
    r'(?:import\s*(?:license|licence|permit|no)|רישיון\s*יבוא|היתר\s*יבוא)[.:\s#]*([A-Za-z0-9][\w\-/]{2,20})',
    re.IGNORECASE
)

# Export permit number (רישיון יצוא)
_RE_EXPORT_NUMBER = re.compile(
    r'(?:export\s*(?:license|licence|permit|no)|רישיון\s*יצוא|היתר\s*יצוא)[.:\s#]*([A-Za-z0-9][\w\-/]{2,20})',
    re.IGNORECASE
)

# Seped number (ספד — customs entry/clearance number)
_RE_SEPED = re.compile(
    r'(?:ספד|seped|entry\s*(?:no|number))[.:\s#]*(\d{4,12})',
    re.IGNORECASE
)

# Re:/Fwd: stripping (reuse from rcb_helpers)
_RE_FWD_PATTERN = re.compile(r'^(?:\s*(?:Re|RE|re|Fwd|FWD|FW|Fw|fw)\s*:\s*)+')


# ═══════════════════════════════════════════
#  ISO 6346 CHECK DIGIT (from tracker.py)
# ═══════════════════════════════════════════

def _iso6346_check_digit(prefix_digits):
    """Validate ISO 6346 container check digit."""
    alphabet = "0123456789A BCDEFGHIJK LMNOPQRSTU VWXYZ"
    values = {}
    n = 0
    for c in alphabet:
        if c == ' ':
            n += 1
            continue
        values[c] = n
        n += 1
    total = 0
    for i, ch in enumerate(prefix_digits[:10]):
        total += values.get(ch, 0) * (2 ** i)
    check = total % 11
    if check == 10:
        check = 0
    return str(check) == prefix_digits[10]


def _validate_container(number):
    """Validate container number format and check digit."""
    num = number.upper().strip()
    if not re.match(r'^[A-Z]{4}\d{7}$', num):
        return False
    return _iso6346_check_digit(num)


# ═══════════════════════════════════════════
#  CORE FUNCTION 1: find_deal_by_identifier
# ═══════════════════════════════════════════

def find_deal_by_identifier(db, identifier):
    """Search across ALL identifier fields for a match.

    Args:
        db: Firestore client
        identifier: str — any identifier (BL, container, AWB, invoice, PO, etc.)

    Returns:
        str or None — deal_id if found, None otherwise
    """
    if not db or not identifier:
        return None

    identifier = identifier.strip()
    if not identifier:
        return None

    coll = db.collection(COLLECTION)

    # Search array fields with array_contains
    for field in IDENTIFIER_FIELDS:
        try:
            docs = list(
                coll.where(field, "array_contains", identifier)
                .limit(1)
                .stream()
            )
            if docs:
                data = docs[0].to_dict()
                # Skip merged records
                if data.get("merged_into"):
                    return data["merged_into"]
                return docs[0].id
        except Exception:
            continue

    # Search scalar fields
    for field in SCALAR_ID_FIELDS:
        try:
            docs = list(
                coll.where(field, "==", identifier)
                .limit(1)
                .stream()
            )
            if docs:
                data = docs[0].to_dict()
                if data.get("merged_into"):
                    return data["merged_into"]
                return docs[0].id
        except Exception:
            continue

    # Try case-insensitive: uppercase version for containers/BLs
    upper = identifier.upper()
    if upper != identifier:
        for field in IDENTIFIER_FIELDS:
            try:
                docs = list(
                    coll.where(field, "array_contains", upper)
                    .limit(1)
                    .stream()
                )
                if docs:
                    data = docs[0].to_dict()
                    if data.get("merged_into"):
                        return data["merged_into"]
                    return docs[0].id
            except Exception:
                continue

    # Search email_subjects (normalized) for thread matching
    normalized_subj = _normalize_subject(identifier)
    if normalized_subj and len(normalized_subj) > 10:
        try:
            docs = list(
                coll.where("email_subjects", "array_contains", normalized_subj)
                .limit(1)
                .stream()
            )
            if docs:
                data = docs[0].to_dict()
                if data.get("merged_into"):
                    return data["merged_into"]
                return docs[0].id
        except Exception:
            pass

    return None


# ═══════════════════════════════════════════
#  CORE FUNCTION 2: register_identifier
# ═══════════════════════════════════════════

def register_identifier(db, deal_id, field, value):
    """Add an identifier to a deal's graph entry, deduped.

    Args:
        db: Firestore client
        deal_id: str — the deal ID (primary key)
        field: str — one of IDENTIFIER_FIELDS or a scalar field
        value: str — the identifier value to register

    Returns:
        bool — True if added, False if already present or error
    """
    if not db or not deal_id or not field or not value:
        return False

    value = value.strip()
    if not value:
        return False

    doc_ref = db.collection(COLLECTION).document(deal_id)
    now = datetime.now(timezone.utc).isoformat()

    try:
        doc = doc_ref.get()

        if not doc.exists:
            # Create new graph entry
            graph_data = _empty_graph(deal_id)
            if field in IDENTIFIER_FIELDS:
                graph_data[field] = [value]
            else:
                graph_data[field] = value
            graph_data["last_updated"] = now
            doc_ref.set(graph_data)
            return True

        data = doc.to_dict()

        # Array field: append if not present
        if field in IDENTIFIER_FIELDS:
            existing = data.get(field, [])
            if value in existing:
                return False  # Already present
            existing.append(value)
            doc_ref.update({
                field: existing,
                "last_updated": now,
            })
            return True

        # Scalar field: set if different
        if data.get(field) != value:
            doc_ref.update({
                field: value,
                "last_updated": now,
            })
            return True

        return False  # Same value already

    except Exception as e:
        print(f"  identity_graph: register_identifier error: {e}")
        return False


# ═══════════════════════════════════════════
#  CORE FUNCTION 3: merge_deals
# ═══════════════════════════════════════════

def merge_deals(db, deal_id_a, deal_id_b):
    """Merge all identifiers from deal_id_b into deal_id_a.

    deal_id_a is the survivor (primary).
    deal_id_b is marked as merged_into deal_id_a.

    Args:
        db: Firestore client
        deal_id_a: str — primary deal (keeps this ID)
        deal_id_b: str — secondary deal (gets merged away)

    Returns:
        bool — True if merged successfully
    """
    if not db or not deal_id_a or not deal_id_b:
        return False
    if deal_id_a == deal_id_b:
        return False

    coll = db.collection(COLLECTION)
    now = datetime.now(timezone.utc).isoformat()

    try:
        doc_a = coll.document(deal_id_a).get()
        doc_b = coll.document(deal_id_b).get()

        data_a = doc_a.to_dict() if doc_a.exists else _empty_graph(deal_id_a)
        data_b = doc_b.to_dict() if doc_b.exists else None

        if not data_b:
            return False  # Nothing to merge from

        # Merge array fields: union of both
        for field in IDENTIFIER_FIELDS:
            vals_a = set(data_a.get(field, []))
            vals_b = set(data_b.get(field, []))
            merged = sorted(vals_a | vals_b)
            data_a[field] = merged

        # Merge email_subjects
        subjs_a = set(data_a.get("email_subjects", []))
        subjs_b = set(data_b.get("email_subjects", []))
        data_a["email_subjects"] = sorted(subjs_a | subjs_b)

        # Merge scalar fields: fill empty from B
        for scalar in ["client_name", "client_ref", "internal_file_ref",
                        "job_order_number", "file_number", "import_number",
                        "export_number", "seped_number"]:
            if not data_a.get(scalar) and data_b.get(scalar):
                data_a[scalar] = data_b[scalar]

        # Recalculate confidence: higher of the two
        conf_a = data_a.get("confidence", 0.5)
        conf_b = data_b.get("confidence", 0.5)
        data_a["confidence"] = max(conf_a, conf_b)

        data_a["last_updated"] = now
        data_a["deal_id"] = deal_id_a

        # Write merged data to A
        coll.document(deal_id_a).set(data_a)

        # Mark B as merged
        coll.document(deal_id_b).set({
            "deal_id": deal_id_b,
            "merged_into": deal_id_a,
            "merged_at": now,
            "last_updated": now,
        })

        return True

    except Exception as e:
        print(f"  identity_graph: merge_deals error: {e}")
        return False


# ═══════════════════════════════════════════
#  CORE FUNCTION 4: extract_identifiers_from_email
# ═══════════════════════════════════════════

def extract_identifiers_from_email(subject, body, attachments_text=""):
    """Extract all document identifiers from email content.

    Uses regex patterns from tracker.py + document_parser.py + new
    patterns for invoice/PO numbers.

    Args:
        subject: str — email subject line
        body: str — email body text (plain or stripped HTML)
        attachments_text: str — concatenated text from all attachments

    Returns:
        dict — {field_name: [values]} for each identifier type found
    """
    result = {
        "bl_numbers": [],
        "booking_refs": [],
        "awb_numbers": [],
        "container_numbers": [],
        "invoice_numbers": [],
        "po_numbers": [],
        "packing_list_refs": [],
        "client_ref": "",
        "internal_file_ref": "",
        "job_order_number": "",
        "file_number": "",
        "import_number": "",
        "export_number": "",
        "seped_number": "",
        "email_subject_normalized": "",
    }

    # Combine all text sources
    combined = "\n".join(filter(None, [subject or "", body or "", attachments_text or ""]))
    if not combined.strip():
        return result

    # Normalize subject
    if subject:
        result["email_subject_normalized"] = _normalize_subject(subject)

    # ── Container numbers (with ISO 6346 validation) ──
    containers = set()
    for m in _RE_CONTAINER.finditer(combined):
        num = m.group(1).upper()
        if _validate_container(num):
            containers.add(num)
    result["container_numbers"] = sorted(containers)

    # ── Bill of Lading ──
    bls = set()
    for m in _RE_BL_LABELED.finditer(combined):
        bls.add(m.group(1).strip())
    for m in _RE_BL_MSC.finditer(combined):
        bls.add(m.group(1))
    for m in _RE_BL_PREFIX.finditer(combined):
        val = m.group(1)
        # Avoid matching container numbers as BLs
        if val.upper() not in containers and not re.match(r'^[A-Z]{4}\d{7}$', val):
            bls.add(val)
    result["bl_numbers"] = sorted(bls)

    # ── AWB numbers ──
    awbs = set()
    for m in _RE_AWB_LABELED.finditer(combined):
        awb = m.group(1).replace(" ", "-")
        if "-" not in awb and len(awb) >= 11:
            awb = awb[:3] + "-" + awb[3:]
        awbs.add(awb)
    # Only try bare AWB if text signals air cargo
    if re.search(r'(?:AWB|air\s*waybill|MAWB|HAWB|air\s*cargo|שטר.*?אוויר)', combined, re.IGNORECASE):
        for m in _RE_AWB_BARE.finditer(combined):
            awb = m.group(1).replace(" ", "-")
            awbs.add(awb)
    result["awb_numbers"] = sorted(awbs)

    # ── Booking references ──
    bookings = set()
    for m in _RE_BOOKING.finditer(combined):
        bookings.add(m.group(1).strip())
    for m in _RE_BOOKING_EBKG.finditer(combined):
        bookings.add(m.group(1))
    result["booking_refs"] = sorted(bookings)

    # ── Invoice numbers ──
    invoices = set()
    for m in _RE_INVOICE.finditer(combined):
        val = m.group(1).strip().rstrip(".,;:")
        if len(val) >= 2:
            invoices.add(val)
    result["invoice_numbers"] = sorted(invoices)

    # ── PO numbers ──
    pos = set()
    for m in _RE_PO.finditer(combined):
        val = m.group(1).strip().rstrip(".,;:")
        if len(val) >= 2:
            pos.add(val)
    result["po_numbers"] = sorted(pos)

    # ── Packing list refs ──
    pls = set()
    for m in _RE_PACKING_LIST.finditer(combined):
        val = m.group(1).strip().rstrip(".,;:")
        if len(val) >= 2:
            pls.add(val)
    result["packing_list_refs"] = sorted(pls)

    # ── Client reference ──
    m = _RE_CLIENT_REF.search(combined)
    if m:
        result["client_ref"] = m.group(1).strip()

    # ── Internal file reference ──
    m = _RE_INTERNAL_REF.search(combined)
    if m:
        result["internal_file_ref"] = m.group(1).strip()

    # ── File number (4=import, 6=transit/export) ──
    m = _RE_FILE_NUMBER.search(combined)
    if m:
        result["file_number"] = m.group(1).strip()

    # ── Job order number ──
    m = _RE_JOB_ORDER.search(combined)
    if m:
        result["job_order_number"] = m.group(1).strip()

    # ── Import license/permit number ──
    m = _RE_IMPORT_NUMBER.search(combined)
    if m:
        result["import_number"] = m.group(1).strip()

    # ── Export permit number ──
    m = _RE_EXPORT_NUMBER.search(combined)
    if m:
        result["export_number"] = m.group(1).strip()

    # ── Seped number (ספד) ──
    m = _RE_SEPED.search(combined)
    if m:
        result["seped_number"] = m.group(1).strip()

    return result


# ═══════════════════════════════════════════
#  CORE FUNCTION 5: link_email_to_deal
# ═══════════════════════════════════════════

def link_email_to_deal(db, email_data):
    """Extract identifiers from email → search graph → link to deal.

    Args:
        db: Firestore client
        email_data: dict with keys:
            - subject: str
            - body: str
            - attachments_text: str (optional)
            - thread_id: str (optional, email conversation ID)
            - from_email: str (optional)

    Returns:
        dict — {
            "deal_id": str or None,
            "identifiers": dict (extracted identifiers),
            "new_identifiers_added": int,
            "matched_by": str (which field matched),
        }
    """
    result = {
        "deal_id": None,
        "identifiers": {},
        "new_identifiers_added": 0,
        "matched_by": "",
    }

    if not db or not email_data:
        return result

    subject = email_data.get("subject", "")
    body = email_data.get("body", "")
    attachments_text = email_data.get("attachments_text", "")
    thread_id = email_data.get("thread_id", "")

    # Step 1: Extract identifiers
    identifiers = extract_identifiers_from_email(subject, body, attachments_text)
    result["identifiers"] = identifiers

    # Step 2: Search graph for a match (priority order)
    deal_id = None
    matched_by = ""

    # Priority 0: Thread ID
    if thread_id:
        found = find_deal_by_identifier(db, thread_id)
        if found:
            deal_id = found
            matched_by = "email_thread_id"

    # Priority 1: B/L number (most specific for sea freight)
    if not deal_id:
        for bl in identifiers.get("bl_numbers", []):
            found = find_deal_by_identifier(db, bl)
            if found:
                deal_id = found
                matched_by = f"bl_number:{bl}"
                break

    # Priority 2: AWB number (most specific for air freight)
    if not deal_id:
        for awb in identifiers.get("awb_numbers", []):
            found = find_deal_by_identifier(db, awb)
            if found:
                deal_id = found
                matched_by = f"awb_number:{awb}"
                break

    # Priority 3: Container number
    if not deal_id:
        for cnt in identifiers.get("container_numbers", []):
            found = find_deal_by_identifier(db, cnt)
            if found:
                deal_id = found
                matched_by = f"container_number:{cnt}"
                break

    # Priority 4: Booking reference
    if not deal_id:
        for bkg in identifiers.get("booking_refs", []):
            found = find_deal_by_identifier(db, bkg)
            if found:
                deal_id = found
                matched_by = f"booking_ref:{bkg}"
                break

    # Priority 5: Invoice number
    if not deal_id:
        for inv in identifiers.get("invoice_numbers", []):
            found = find_deal_by_identifier(db, inv)
            if found:
                deal_id = found
                matched_by = f"invoice_number:{inv}"
                break

    # Priority 6: PO number
    if not deal_id:
        for po in identifiers.get("po_numbers", []):
            found = find_deal_by_identifier(db, po)
            if found:
                deal_id = found
                matched_by = f"po_number:{po}"
                break

    # Priority 7: File number (RPA PORT internal — very specific)
    if not deal_id and identifiers.get("file_number"):
        found = find_deal_by_identifier(db, identifiers["file_number"])
        if found:
            deal_id = found
            matched_by = f"file_number:{identifiers['file_number']}"

    # Priority 8: Seped number (customs entry)
    if not deal_id and identifiers.get("seped_number"):
        found = find_deal_by_identifier(db, identifiers["seped_number"])
        if found:
            deal_id = found
            matched_by = f"seped_number:{identifiers['seped_number']}"

    # Priority 9: Client reference
    if not deal_id and identifiers.get("client_ref"):
        found = find_deal_by_identifier(db, identifiers["client_ref"])
        if found:
            deal_id = found
            matched_by = f"client_ref:{identifiers['client_ref']}"

    # Priority 10: Job order number
    if not deal_id and identifiers.get("job_order_number"):
        found = find_deal_by_identifier(db, identifiers["job_order_number"])
        if found:
            deal_id = found
            matched_by = f"job_order_number:{identifiers['job_order_number']}"

    result["deal_id"] = deal_id
    result["matched_by"] = matched_by

    # Step 3: If found, register any new identifiers
    if deal_id:
        added = 0
        for field in IDENTIFIER_FIELDS:
            for val in identifiers.get(field, []):
                if register_identifier(db, deal_id, field, val):
                    added += 1

        # Register thread ID if present
        if thread_id:
            if register_identifier(db, deal_id, "email_thread_ids", thread_id):
                added += 1

        # Register normalized subject
        norm_subj = identifiers.get("email_subject_normalized", "")
        if norm_subj:
            _add_email_subject(db, deal_id, norm_subj)

        # Register scalar fields
        for scalar in SCALAR_ID_FIELDS:
            val = identifiers.get(scalar, "")
            if val:
                register_identifier(db, deal_id, scalar, val)

        result["new_identifiers_added"] = added

    return result


# ═══════════════════════════════════════════
#  HELPER: Build empty graph document
# ═══════════════════════════════════════════

def _empty_graph(deal_id):
    """Create an empty identity graph document."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "deal_id": deal_id,
        "bl_numbers": [],
        "booking_refs": [],
        "awb_numbers": [],
        "container_numbers": [],
        "invoice_numbers": [],
        "po_numbers": [],
        "packing_list_refs": [],
        "email_thread_ids": [],
        "client_name": "",
        "client_ref": "",
        "internal_file_ref": "",
        "job_order_number": "",
        "file_number": "",
        "import_number": "",
        "export_number": "",
        "seped_number": "",
        "email_subjects": [],
        "last_updated": now,
        "confidence": 0.5,
    }


# ═══════════════════════════════════════════
#  HELPER: Normalize email subject
# ═══════════════════════════════════════════

def _normalize_subject(subject):
    """Strip Re:/Fwd: prefixes and normalize whitespace."""
    if not subject:
        return ""
    cleaned = _RE_FWD_PATTERN.sub("", subject).strip()
    # Collapse whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned if cleaned else ""


# ═══════════════════════════════════════════
#  HELPER: Add email subject to graph
# ═══════════════════════════════════════════

def _add_email_subject(db, deal_id, normalized_subject):
    """Add a normalized email subject to the graph doc, deduped."""
    if not normalized_subject:
        return False
    try:
        doc_ref = db.collection(COLLECTION).document(deal_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False
        data = doc.to_dict()
        subjects = data.get("email_subjects", [])
        if normalized_subject not in subjects:
            subjects.append(normalized_subject)
            doc_ref.update({
                "email_subjects": subjects,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            })
            return True
        return False
    except Exception:
        return False


# ═══════════════════════════════════════════
#  UTILITY: Bulk-register from tracker deal
# ═══════════════════════════════════════════

def register_deal_from_tracker(db, deal_id, deal_data):
    """Populate graph from an existing tracker_deals document.

    Reads standard tracker_deals fields and registers them
    in the identity graph. Call this when syncing existing deals.

    Args:
        db: Firestore client
        deal_id: str
        deal_data: dict — tracker_deals document data

    Returns:
        int — number of identifiers registered
    """
    if not db or not deal_id or not deal_data:
        return 0

    added = 0

    # B/L
    bl = deal_data.get("bol_number", "")
    if bl:
        if register_identifier(db, deal_id, "bl_numbers", bl):
            added += 1

    # AWB
    awb = deal_data.get("awb_number", "")
    if awb:
        if register_identifier(db, deal_id, "awb_numbers", awb):
            added += 1

    # Booking
    bkg = deal_data.get("booking_number", "")
    if bkg:
        if register_identifier(db, deal_id, "booking_refs", bkg):
            added += 1

    # Containers
    for cnt in deal_data.get("containers", []):
        if cnt:
            if register_identifier(db, deal_id, "container_numbers", cnt):
                added += 1

    # Thread ID
    thread_id = deal_data.get("source_email_thread_id", "")
    if thread_id:
        if register_identifier(db, deal_id, "email_thread_ids", thread_id):
            added += 1

    # Client name (scalar)
    consignee = deal_data.get("consignee", "")
    if consignee:
        try:
            doc_ref = db.collection(COLLECTION).document(deal_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                if not data.get("client_name"):
                    doc_ref.update({
                        "client_name": consignee,
                        "last_updated": datetime.now(timezone.utc).isoformat(),
                    })
                    added += 1
        except Exception:
            pass

    # Set confidence based on identifier count
    try:
        doc_ref = db.collection(COLLECTION).document(deal_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            total_ids = sum(len(data.get(f, [])) for f in IDENTIFIER_FIELDS)
            confidence = min(0.5 + total_ids * 0.1, 1.0)
            doc_ref.update({
                "confidence": confidence,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            })
    except Exception:
        pass

    return added
