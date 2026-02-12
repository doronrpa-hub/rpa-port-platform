"""
Batch Reprocessor — Read, classify, verify, and LEARN from EVERYTHING
======================================================================
Pulls from ALL sources:
  1. Graph API mailbox — ALL emails (inbox + sentItems + all folders)
  2. Firestore inbox — stored emails with extracted text
  3. Firestore classifications — legacy classification records
  4. Firestore rcb_classifications — past RCB classification results
  5. Firestore knowledge_base — product/seller knowledge
  6. Firestore declarations — customs declarations with HS codes

NO EMAILS SENT. Just read, classify, verify, learn, store results.

Usage:
    python batch_reprocess.py                  # Full run (AI calls)
    python batch_reprocess.py --dry-run        # Extract + parse only (free)
    python batch_reprocess.py --limit 5        # Process first N items
    python batch_reprocess.py --trade-only     # Only classify items with commercial invoices
    python batch_reprocess.py --dry-run --limit 3
"""

import sys
import os
import io
import re
import argparse
import traceback
import hashlib
from datetime import datetime, timezone
from collections import Counter

# Fix Windows console encoding for Hebrew/emoji
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Firebase / GCP setup ──
os.environ.setdefault("GCLOUD_PROJECT", "rpa-port-customs")

_cred_path = os.path.join(
    os.environ.get("APPDATA", ""),
    "gcloud", "legacy_credentials", "doronrpa@gmail.com", "adc.json"
)
if os.path.exists(_cred_path):
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", _cred_path)

import firebase_admin
from firebase_admin import credentials, firestore

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

db = firestore.client()

# ── Add functions/ to path so lib.* imports work ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Import pipeline modules ──
from lib.rcb_helpers import (
    extract_text_from_attachments,
    helper_get_graph_token,
    helper_graph_messages,
    helper_graph_attachments,
    get_rcb_secrets_internal,
)
from lib.classification_agents import run_full_classification

try:
    from lib.document_parser import parse_all_documents
    PARSER_AVAILABLE = True
except ImportError:
    PARSER_AVAILABLE = False
    print("WARNING: document_parser not available")

try:
    from lib.intelligence import pre_classify, query_free_import_order, route_to_ministries
    INTELLIGENCE_AVAILABLE = True
except ImportError:
    INTELLIGENCE_AVAILABLE = False
    print("WARNING: intelligence module not available")

try:
    from lib.verification_loop import verify_all_classifications, learn_from_verification
    VERIFICATION_AVAILABLE = True
except ImportError:
    VERIFICATION_AVAILABLE = False
    print("WARNING: verification_loop not available")

try:
    from lib.smart_questions import should_ask_questions, generate_smart_questions
    SMART_QUESTIONS_AVAILABLE = True
except ImportError:
    SMART_QUESTIONS_AVAILABLE = False
    print("WARNING: smart_questions not available")


# ═══════════════════════════════════════════════════════════════
#  Secret Manager (local)
# ═══════════════════════════════════════════════════════════════

def get_secret(name):
    """Get secret from Google Cloud Secret Manager"""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        secret_path = f"projects/rpa-port-customs/secrets/{name}/versions/latest"
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"  Secret {name} error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
#  SOURCE 1: Fetch ALL emails from Graph API (all folders)
# ═══════════════════════════════════════════════════════════════

def fetch_graph_emails(access_token, rcb_email, max_pages=20):
    """Fetch ALL messages from inbox + sentItems (paginated)."""
    import requests

    all_messages = []
    seen_ids = set()

    for folder in ["inbox", "sentItems"]:
        url = f"https://graph.microsoft.com/v1.0/users/{rcb_email}/mailFolders/{folder}/messages"
        params = {
            "$top": 50,
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,receivedDateTime,body,bodyPreview,toRecipients,ccRecipients,hasAttachments",
        }

        for page in range(max_pages):
            resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, params=params)
            if resp.status_code != 200:
                print(f"    Graph API error ({folder} p{page}): {resp.status_code}")
                break

            data = resp.json()
            messages = data.get("value", [])
            for msg in messages:
                mid = msg.get("id", "")
                if mid and mid not in seen_ids:
                    seen_ids.add(mid)
                    msg["_folder"] = folder
                    all_messages.append(msg)

            next_link = data.get("@odata.nextLink")
            if not next_link:
                break
            url = next_link
            params = {}

    return all_messages


# ═══════════════════════════════════════════════════════════════
#  SOURCE 2-5: Firestore collections with stored text
# ═══════════════════════════════════════════════════════════════

def collect_firestore_items():
    """
    Read all Firestore collections that have text data we can learn from.
    Returns list of work items [{source, doc_id, text, metadata}].
    """
    items = []

    # ── Source 2: inbox collection (has extracted_text in attachments) ──
    print("  Reading Firestore: inbox...")
    try:
        for doc in db.collection("inbox").stream():
            data = doc.to_dict()
            text_parts = []
            body = data.get("body", "")
            if body:
                text_parts.append(body)
            for att in data.get("attachments", []):
                et = att.get("extracted_text", "")
                if et:
                    fn = att.get("filename", "file")
                    text_parts.append(f"=== {fn} ===\n{et}")
            combined = "\n\n".join(text_parts)
            if len(combined) >= 50:
                items.append({
                    "source": "firestore_inbox",
                    "doc_id": doc.id,
                    "text": combined,
                    "subject": data.get("subject", ""),
                    "from_email": data.get("from", ""),
                    "attachment_count": data.get("attachment_count", 0),
                })
    except Exception as e:
        print(f"    inbox read error: {e}")

    # ── Source 3: classifications collection (has extracted_text) ──
    print("  Reading Firestore: classifications...")
    try:
        for doc in db.collection("classifications").stream():
            data = doc.to_dict()
            text = data.get("extracted_text", "")
            product = data.get("product_description", "")
            if text and len(text) >= 50:
                items.append({
                    "source": "firestore_classifications",
                    "doc_id": doc.id,
                    "text": text,
                    "subject": f"Classification: {product[:60]}" if product else doc.id,
                    "from_email": data.get("source_email", ""),
                    "seller": data.get("seller", ""),
                    "origin": data.get("origin", ""),
                    "supplier_hs": data.get("supplier_hs", ""),
                })
            elif product and len(product) >= 20:
                # At least learn from the product description
                items.append({
                    "source": "firestore_classifications",
                    "doc_id": doc.id,
                    "text": product,
                    "subject": f"Classification: {product[:60]}",
                    "from_email": data.get("source_email", ""),
                    "seller": data.get("seller", ""),
                    "origin": data.get("origin", ""),
                    "supplier_hs": data.get("supplier_hs", ""),
                    "text_is_description_only": True,
                })
    except Exception as e:
        print(f"    classifications read error: {e}")

    # ── Source 4: knowledge_base (product/seller knowledge) ──
    print("  Reading Firestore: knowledge_base...")
    try:
        for doc in db.collection("knowledge_base").stream():
            data = doc.to_dict()
            content = data.get("content", {})
            if isinstance(content, dict):
                hs = content.get("hs", "")
                products = content.get("products", [])
                sellers = content.get("sellers", [])
                if hs and products:
                    for product in products:
                        if product and len(product) >= 10:
                            items.append({
                                "source": "firestore_knowledge_base",
                                "doc_id": doc.id,
                                "text": product,
                                "subject": f"KB: {product[:60]}",
                                "known_hs": hs,
                                "sellers": sellers,
                                "text_is_description_only": True,
                            })
    except Exception as e:
        print(f"    knowledge_base read error: {e}")

    # ── Source 5: declarations (customs declarations) ──
    print("  Reading Firestore: declarations...")
    try:
        for doc in db.collection("declarations").stream():
            data = doc.to_dict()
            text = data.get("extracted_text", "")
            hs_code = data.get("hs_code", "")
            filename = data.get("filename", "")
            if text and len(text) >= 50:
                items.append({
                    "source": "firestore_declarations",
                    "doc_id": doc.id,
                    "text": text,
                    "subject": f"Declaration: {filename or hs_code or doc.id}",
                    "known_hs": hs_code,
                })
            elif hs_code:
                # At least verify the HS code
                items.append({
                    "source": "firestore_declarations",
                    "doc_id": doc.id,
                    "text": f"Customs declaration HS code: {hs_code}",
                    "subject": f"Declaration: {filename or hs_code}",
                    "known_hs": hs_code,
                    "verify_only": True,
                })
    except Exception as e:
        print(f"    declarations read error: {e}")

    return items


# ═══════════════════════════════════════════════════════════════
#  Deduplication
# ═══════════════════════════════════════════════════════════════

def dedup_work_items(graph_items, firestore_items):
    """
    Merge graph API emails and Firestore items, deduplicate by content hash.
    Graph API items take priority (they have live attachments).
    """
    seen_hashes = set()
    final = []

    # Graph items first (highest quality — have raw attachments)
    for item in graph_items:
        subj = item.get("subject", "")
        from_addr = item.get("from_email", "")
        h = hashlib.md5(f"{subj}:{from_addr}".encode()).hexdigest()
        if h not in seen_hashes:
            seen_hashes.add(h)
            final.append(item)

    # Firestore items (only if not already covered by graph)
    for item in firestore_items:
        subj = item.get("subject", "")
        from_addr = item.get("from_email", "")
        h = hashlib.md5(f"{subj}:{from_addr}".encode()).hexdigest()
        if h not in seen_hashes:
            seen_hashes.add(h)
            final.append(item)

    return final


# ═══════════════════════════════════════════════════════════════
#  Process a single Graph API email (has live attachments)
# ═══════════════════════════════════════════════════════════════

def process_graph_email(msg, access_token, rcb_email, api_key, gemini_key, dry_run=False, trade_only=False):
    """Process one email from Graph API through the full pipeline."""
    msg_id = msg.get("id", "")
    subject = msg.get("subject", "No Subject")
    from_data = msg.get("from", {}).get("emailAddress", {})
    from_email = from_data.get("address", "")

    result = {
        "source": f"graph_{msg.get('_folder', 'inbox')}",
        "msg_id": msg_id,
        "subject": subject,
        "from_email": from_email,
        "received": msg.get("receivedDateTime", ""),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
    }

    # Get attachments from Graph API
    raw_attachments = helper_graph_attachments(access_token, rcb_email, msg_id)
    file_attachments = [
        a for a in raw_attachments
        if a.get("@odata.type") == "#microsoft.graph.fileAttachment"
    ]
    result["attachment_count"] = len(file_attachments)
    result["attachment_names"] = [a.get("name", "") for a in file_attachments]

    if not file_attachments:
        result["skipped"] = True
        result["skip_reason"] = "no_attachments"
        return result

    # Extract text
    email_body = msg.get("body", {}).get("content", "") or msg.get("bodyPreview", "")
    if msg.get("body", {}).get("contentType", "") == "html" and email_body:
        email_body = re.sub(r"<[^>]+>", " ", email_body)
        email_body = re.sub(r"\s+", " ", email_body).strip()

    doc_text = extract_text_from_attachments(raw_attachments, email_body=email_body)
    result["extracted_chars"] = len(doc_text) if doc_text else 0

    if not doc_text or len(doc_text) < 50:
        result["skipped"] = True
        result["skip_reason"] = "insufficient_text"
        return result

    return _run_pipeline(doc_text, result, api_key, gemini_key, dry_run, trade_only=trade_only)


# ═══════════════════════════════════════════════════════════════
#  Process a single Firestore item (has stored text)
# ═══════════════════════════════════════════════════════════════

def process_firestore_item(item, api_key, gemini_key, dry_run=False, trade_only=False):
    """Process one Firestore-sourced item through the pipeline."""
    result = {
        "source": item["source"],
        "doc_id": item.get("doc_id", ""),
        "subject": item.get("subject", ""),
        "from_email": item.get("from_email", ""),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
    }

    doc_text = item.get("text", "")
    result["extracted_chars"] = len(doc_text)

    if not doc_text or len(doc_text) < 20:
        result["skipped"] = True
        result["skip_reason"] = "insufficient_text"
        return result

    # For verify_only items (declarations with just an HS code), handle specially
    if item.get("verify_only") and VERIFICATION_AVAILABLE:
        hs = item.get("known_hs", "")
        if hs:
            result["known_hs"] = hs
            try:
                verified = verify_all_classifications(
                    db,
                    [{"hs_code": hs, "item": "declaration", "confidence": "N/A", "duty_rate": "", "reasoning": ""}],
                    free_import_results={},
                )
                result["verification"] = [
                    {"hs_code": c.get("hs_code", ""), "status": c.get("verification_status", "unverified")}
                    for c in verified
                ]
                for c in verified:
                    if c.get("verification_status") in ("official", "verified"):
                        try:
                            learn_from_verification(db, c)
                        except Exception:
                            pass
            except Exception as e:
                result["verification_error"] = str(e)
        result["skipped"] = False
        result["verify_only"] = True
        return result

    return _run_pipeline(doc_text, result, api_key, gemini_key, dry_run,
                         known_hs=item.get("known_hs"),
                         known_seller=item.get("seller"),
                         known_origin=item.get("origin"),
                         trade_only=trade_only)


# ═══════════════════════════════════════════════════════════════
#  Shared pipeline (steps 3-9)
# ═══════════════════════════════════════════════════════════════

def _run_pipeline(doc_text, result, api_key, gemini_key, dry_run,
                  known_hs=None, known_seller=None, known_origin=None,
                  trade_only=False):
    """
    Run steps 3-9 on extracted text. Shared between graph and firestore items.
    Mutates and returns result dict.
    """
    # ── Step 3: Document parser (free) ──
    parsed_documents = []
    if PARSER_AVAILABLE:
        try:
            parsed_documents = parse_all_documents(doc_text)
            result["parsed_documents"] = [
                {
                    "type": d.get("type_info", {}).get("name_en", "unknown"),
                    "type_he": d.get("type_info", {}).get("name_he", ""),
                    "confidence": d.get("type_info", {}).get("confidence", 0),
                    "completeness_score": d.get("completeness", {}).get("score", 0),
                    "missing_fields": d.get("completeness", {}).get("missing_fields", []),
                }
                for d in parsed_documents
            ]
        except Exception as e:
            result["parser_error"] = str(e)

    # ── Trade-only gate: skip if no commercial invoice found ──
    if trade_only:
        has_invoice = any(
            "commercial invoice" in (d.get("type_info", {}).get("name_en", "") or "").lower()
            for d in parsed_documents
        )
        if not has_invoice:
            result["skipped"] = True
            result["skip_reason"] = "no_trade_document"
            return result

    # ── Step 4: Pre-classify from intelligence (free) ──
    intelligence_results = {}
    if INTELLIGENCE_AVAILABLE:
        try:
            desc = _extract_description_from_text(doc_text)
            origin = known_origin or _extract_origin_from_text(doc_text)
            seller = known_seller or _extract_seller_from_text(doc_text)

            pc_result = pre_classify(db, desc, origin, seller_name=seller)
            intelligence_results["pre_classify"] = {
                "candidates_found": pc_result.get("stats", {}).get("candidates_found", 0),
                "top_confidence": pc_result.get("stats", {}).get("top_confidence", 0),
                "top_candidate": pc_result["candidates"][0] if pc_result.get("candidates") else None,
                "fta_eligible": pc_result.get("stats", {}).get("fta_eligible", False),
            }
            result["intelligence"] = intelligence_results
        except Exception as e:
            result["intelligence_error"] = str(e)

    # ── DRY RUN STOPS HERE ──
    if dry_run:
        result["skipped"] = False
        result["dry_run_complete"] = True
        return result

    # ── Step 5: Full AI classification ──
    try:
        classification_results = run_full_classification(api_key, doc_text, db, gemini_key=gemini_key)
        if not classification_results.get("success"):
            result["classification_error"] = classification_results.get("error", "unknown")
            return result
    except Exception as e:
        result["classification_error"] = str(e)
        return result

    classifications = (
        classification_results.get("agents", {})
        .get("classification", {})
        .get("classifications", [])
    )
    result["classifications"] = classifications
    result["hs_codes"] = [c.get("hs_code", "") for c in classifications]
    result["synthesis"] = classification_results.get("synthesis", "")[:500]

    # ── Step 6: Free Import Order API per HS code ──
    free_import_results = {}
    if INTELLIGENCE_AVAILABLE:
        for c in classifications[:3]:
            hs = c.get("hs_code", "")
            if hs:
                try:
                    fio = query_free_import_order(db, hs)
                    free_import_results[hs] = fio
                except Exception as e:
                    free_import_results[hs] = {"error": str(e)}
        result["free_import_order"] = {
            hs: {"found": v.get("found", False), "authorities_count": len(v.get("authorities", []))}
            for hs, v in free_import_results.items()
            if isinstance(v, dict) and "error" not in v
        }

    # ── Step 7: Ministry routing ──
    ministry_routing = {}
    if INTELLIGENCE_AVAILABLE:
        for c in classifications[:3]:
            hs = c.get("hs_code", "")
            if hs:
                try:
                    fio = free_import_results.get(hs, {})
                    mr = route_to_ministries(db, hs, free_import_result=fio)
                    ministry_routing[hs] = mr
                except Exception as e:
                    ministry_routing[hs] = {"error": str(e)}
        result["ministry_routing"] = {
            hs: {"risk_level": v.get("risk_level", ""), "ministries_count": len(v.get("ministries", []))}
            for hs, v in ministry_routing.items()
            if isinstance(v, dict) and "error" not in v
        }

    # ── Step 8: Verification loop ──
    if VERIFICATION_AVAILABLE:
        try:
            verified = verify_all_classifications(db, classifications, free_import_results=free_import_results)
            result["verification"] = [
                {
                    "hs_code": c.get("hs_code", ""),
                    "status": c.get("verification_status", "unverified"),
                    "purchase_tax": c.get("purchase_tax", ""),
                    "vat_rate": c.get("vat_rate", ""),
                    "duty_rate": c.get("duty_rate", ""),
                    "duty_source": c.get("duty_source", ""),
                }
                for c in verified
            ]
            for c in verified:
                if c.get("verification_status") in ("official", "verified"):
                    try:
                        learn_from_verification(db, c)
                    except Exception:
                        pass
        except Exception as e:
            result["verification_error"] = str(e)

    # ── Step 9: Smart questions ──
    if SMART_QUESTIONS_AVAILABLE:
        try:
            needs_questions, ambiguity = should_ask_questions(
                classifications,
                intelligence_results=intelligence_results,
                free_import_results=free_import_results,
                ministry_routing=ministry_routing,
            )
            result["ambiguity"] = ambiguity
            if needs_questions:
                questions = generate_smart_questions(
                    ambiguity, classifications,
                    invoice_data=classification_results.get("invoice_data", {}),
                    free_import_results=free_import_results,
                    ministry_routing=ministry_routing,
                    parsed_documents=parsed_documents,
                )
                result["smart_questions"] = [
                    {"question": q.get("question_he", ""), "category": q.get("category", "")}
                    for q in questions
                ]
        except Exception as e:
            result["smart_questions_error"] = str(e)

    result["skipped"] = False
    return result


# ═══════════════════════════════════════════════════════════════
#  Text extraction helpers
# ═══════════════════════════════════════════════════════════════

def _extract_description_from_text(text):
    """Best-effort: pull product description from extracted text."""
    for pattern in [
        r"(?:description|goods|product|item)[:\s]+(.{10,200})",
        r"(?:תיאור|פריט|טובין|סחורה)[:\s]+(.{10,200})",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    lines = text.split("\n")
    for line in lines[2:20]:
        line = line.strip()
        if len(line) > 20 and not any(kw in line.upper() for kw in ["INVOICE", "DATE", "FROM", "TO:", "SUBJECT"]):
            return line[:300]
    return text[:300]


def _extract_origin_from_text(text):
    """Best-effort: pull origin country from text."""
    m = re.search(
        r"(?:origin|country of origin|made in|ארץ המקור|מקור)[:\s]+([A-Za-z\u0590-\u05FF\s]{2,30})",
        text, re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def _extract_seller_from_text(text):
    """Best-effort: pull seller/shipper name from text."""
    for pattern in [
        r"(?:seller|exporter|shipper|supplier)[:\s]+(.{3,80})",
        r"(?:יצואן|ספק|שולח)[:\s]+(.{3,80})",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


# ═══════════════════════════════════════════════════════════════
#  Firestore save + clean
# ═══════════════════════════════════════════════════════════════

def save_result(result):
    """Save a single result to batch_reprocess_results collection."""
    try:
        clean = _clean_for_firestore(result)
        db.collection("batch_reprocess_results").add(clean)
        return True
    except Exception as e:
        print(f"  Firestore save error: {e}")
        return False


def _clean_for_firestore(data):
    """Recursively clean data for Firestore."""
    import math
    if isinstance(data, dict):
        return {k: _clean_for_firestore(v) for k, v in data.items() if v is not None}
    elif isinstance(data, list):
        return [_clean_for_firestore(v) for v in data if v is not None]
    elif isinstance(data, str):
        return data[:10000]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return 0
        return data
    return data


# ═══════════════════════════════════════════════════════════════
#  Summary
# ═══════════════════════════════════════════════════════════════

def build_summary(all_results):
    """Build summary of all batch results."""
    total = len(all_results)
    skipped = sum(1 for r in all_results if r.get("skipped"))
    failed = sum(1 for r in all_results if r.get("classification_error"))
    processed = total - skipped - failed
    dry_run_only = sum(1 for r in all_results if r.get("dry_run_complete"))
    verify_only = sum(1 for r in all_results if r.get("verify_only"))

    # Sources breakdown
    sources = Counter(r.get("source", "unknown") for r in all_results)

    # Document types
    doc_types = Counter()
    for r in all_results:
        for pd in r.get("parsed_documents", []):
            doc_types[pd.get("type", "unknown")] += 1

    # HS codes
    all_hs = []
    for r in all_results:
        all_hs.extend(r.get("hs_codes", []))
    hs_counter = Counter(all_hs)

    # Verification statuses
    verification_statuses = Counter()
    for r in all_results:
        for v in r.get("verification", []):
            verification_statuses[v.get("status", "unknown")] += 1

    # Smart questions
    total_questions = sum(len(r.get("smart_questions", [])) for r in all_results)
    items_with_questions = sum(1 for r in all_results if r.get("smart_questions"))

    # Skip reasons
    skip_reasons = Counter()
    for r in all_results:
        if r.get("skipped") and r.get("skip_reason"):
            skip_reasons[r["skip_reason"]] += 1

    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total_items": total,
        "processed_ai": processed,
        "dry_run_only": dry_run_only,
        "verify_only": verify_only,
        "skipped": skipped,
        "failed": failed,
        "sources": dict(sources),
        "skip_reasons": dict(skip_reasons),
        "document_types": dict(doc_types),
        "hs_codes_classified": len(all_hs),
        "unique_hs_codes": len(hs_counter),
        "top_hs_codes": dict(hs_counter.most_common(20)),
        "verification": dict(verification_statuses),
        "smart_questions_total": total_questions,
        "items_with_questions": items_with_questions,
        "failed_subjects": [
            r.get("subject", "?")[:60] for r in all_results if r.get("classification_error")
        ],
    }


def print_summary(summary):
    """Print formatted summary to console."""
    print("\n" + "=" * 60)
    print("  BATCH REPROCESS SUMMARY")
    print("=" * 60)
    print(f"  Total items:       {summary['total_items']}")
    print(f"  Processed (AI):    {summary['processed_ai']}")
    print(f"  Verify-only:       {summary['verify_only']}")
    print(f"  Dry-run only:      {summary['dry_run_only']}")
    print(f"  Skipped:           {summary['skipped']}")
    print(f"  Failed:            {summary['failed']}")

    if summary["sources"]:
        print(f"\n  Sources:")
        for src, count in sorted(summary["sources"].items(), key=lambda x: -x[1]):
            print(f"    {src}: {count}")

    if summary["skip_reasons"]:
        print(f"\n  Skip reasons:")
        for reason, count in summary["skip_reasons"].items():
            print(f"    {reason}: {count}")

    if summary["document_types"]:
        print(f"\n  Document types found:")
        for dtype, count in sorted(summary["document_types"].items(), key=lambda x: -x[1]):
            print(f"    {dtype}: {count}")

    print(f"\n  HS codes classified: {summary['hs_codes_classified']}")
    print(f"  Unique HS codes:     {summary['unique_hs_codes']}")
    if summary["top_hs_codes"]:
        print(f"  Top HS codes:")
        for hs, count in list(summary["top_hs_codes"].items())[:10]:
            print(f"    {hs}: {count}x")

    if summary["verification"]:
        print(f"\n  Verification results:")
        for status, count in summary["verification"].items():
            print(f"    {status}: {count}")

    print(f"\n  Smart questions: {summary['smart_questions_total']} "
          f"across {summary['items_with_questions']} items")

    if summary["failed_subjects"]:
        print(f"\n  Failed items:")
        for s in summary["failed_subjects"][:10]:
            print(f"    - {s}")

    print("=" * 60)


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Batch reprocess ALL data — read, classify, verify, learn")
    parser.add_argument("--dry-run", action="store_true", help="Extract and parse only, no AI calls (free)")
    parser.add_argument("--limit", type=int, default=0, help="Process only first N items")
    parser.add_argument("--source", choices=["graph", "firestore", "all"], default="all",
                        help="Source: graph (emails only), firestore (stored text only), or all")
    parser.add_argument("--trade-only", action="store_true",
                        help="Only run AI on items with a commercial invoice (skip BL-only, packing-list-only, etc.)")
    args = parser.parse_args()

    print("=" * 60)
    print("  BATCH REPROCESSOR — Read, classify, verify, LEARN from everything")
    print(f"  Mode: {'DRY RUN (no AI cost)' if args.dry_run else 'FULL (AI calls — costs money)'}")
    if args.limit:
        print(f"  Limit: {args.limit} items")
    print(f"  Source: {args.source}")
    if args.trade_only:
        print(f"  Filter: TRADE-ONLY (commercial invoice required)")
    print("  SENDS NOTHING. Only reads, learns, stores results.")
    print("=" * 60)

    # ── API keys ──
    api_key = None
    gemini_key = None
    if not args.dry_run:
        api_key = get_secret("ANTHROPIC_API_KEY")
        if not api_key:
            print("FATAL: No ANTHROPIC_API_KEY — use --dry-run or fix secrets")
            sys.exit(1)
        gemini_key = get_secret("GEMINI_API_KEY")
        if gemini_key:
            print("  Gemini key loaded (multi-model mode)")

    # ── Graph API token ──
    access_token = None
    rcb_email = None
    if args.source in ("graph", "all"):
        print("\n  Connecting to Graph API...")
        secrets = get_rcb_secrets_internal(get_secret)
        if not secrets:
            print("WARNING: Cannot get RCB secrets — skipping Graph API source")
        else:
            access_token = helper_get_graph_token(secrets)
            if not access_token:
                print("WARNING: Cannot get Graph API token — skipping Graph API source")
            else:
                rcb_email = secrets.get("RCB_EMAIL", "rcb@rpa-port.co.il")
                print(f"  Connected as: {rcb_email}")

    # ═══════════════════════════════════════════════
    #  COLLECT ALL WORK ITEMS
    # ═══════════════════════════════════════════════

    graph_items = []
    firestore_items = []

    # Source 1: Graph API emails
    if access_token and rcb_email and args.source in ("graph", "all"):
        print("\n  Fetching ALL emails from Graph API (inbox + sent)...")
        messages = fetch_graph_emails(access_token, rcb_email)
        print(f"  Found {len(messages)} total messages")

        for msg in messages:
            subj = msg.get("subject", "")
            # Skip system emails
            if any(kw in subj.lower() for kw in ["[rcb-selftest]", "undeliverable"]):
                continue
            # Skip no-attachment emails (but keep sent items — they might have reports)
            if not msg.get("hasAttachments", False) and msg.get("_folder") != "sentItems":
                continue

            from_addr = msg.get("from", {}).get("emailAddress", {}).get("address", "")
            graph_items.append({
                "type": "graph",
                "msg": msg,
                "subject": subj,
                "from_email": from_addr,
            })

        print(f"  After filtering: {len(graph_items)} emails to process")

    # Sources 2-5: Firestore collections
    if args.source in ("firestore", "all"):
        print("\n  Collecting Firestore items...")
        firestore_items = collect_firestore_items()
        print(f"  Found {len(firestore_items)} items from Firestore")

    # Deduplicate
    print(f"\n  Deduplicating: {len(graph_items)} graph + {len(firestore_items)} firestore...")
    all_work = dedup_work_items(graph_items, firestore_items)
    print(f"  After dedup: {len(all_work)} unique items")

    # Apply limit
    if args.limit and args.limit < len(all_work):
        all_work = all_work[:args.limit]
        print(f"  Limited to {args.limit} items")

    total = len(all_work)
    if total == 0:
        print("\n  No items to process. Done.")
        return

    print(f"\n  Starting batch processing of {total} items...\n")

    # ═══════════════════════════════════════════════
    #  PROCESS EACH ITEM
    # ═══════════════════════════════════════════════

    all_results = []
    for i, item in enumerate(all_work, 1):
        subject = item.get("subject", item.get("msg", {}).get("subject", "unknown"))

        print(f"\n{'─' * 55}")
        print(f"  [{i}/{total}] {subject[:55]}")
        src = item.get("type", item.get("source", "?"))
        print(f"  Source: {src}")
        print(f"{'─' * 55}")

        try:
            if item.get("type") == "graph":
                result = process_graph_email(
                    item["msg"], access_token, rcb_email,
                    api_key, gemini_key, dry_run=args.dry_run,
                    trade_only=args.trade_only,
                )
            else:
                result = process_firestore_item(
                    item, api_key, gemini_key, dry_run=args.dry_run,
                    trade_only=args.trade_only,
                )

            if result:
                save_result(result)
                all_results.append(result)

                if result.get("skipped"):
                    print(f"  -> SKIPPED: {result.get('skip_reason', '?')}")
                elif result.get("verify_only"):
                    verif = result.get("verification", [{}])
                    status = verif[0].get("status", "?") if verif else "?"
                    print(f"  -> VERIFY ONLY: {status}")
                elif result.get("classification_error"):
                    print(f"  -> FAILED: {result['classification_error'][:80]}")
                elif result.get("skip_reason") == "no_trade_document":
                    docs = [d.get("type", "?") for d in result.get("parsed_documents", [])]
                    print(f"  -> SKIPPED (trade-only): docs = {', '.join(docs) or 'none'}")
                elif result.get("dry_run_complete"):
                    chars = result.get("extracted_chars", 0)
                    docs = len(result.get("parsed_documents", []))
                    cands = result.get("intelligence", {}).get("pre_classify", {}).get("candidates_found", 0)
                    print(f"  -> DRY RUN OK: {chars} chars, {docs} docs, {cands} candidates")
                else:
                    hs_codes = result.get("hs_codes", [])
                    verif = [v.get("status", "?") for v in result.get("verification", [])]
                    print(f"  -> OK: HS {', '.join(hs_codes[:3])}")
                    if verif:
                        print(f"         Verification: {', '.join(verif)}")
            else:
                all_results.append({"subject": subject, "skipped": True, "skip_reason": "returned_none"})

        except Exception as e:
            print(f"  -> ERROR: {e}")
            traceback.print_exc()
            all_results.append({"subject": subject, "classification_error": str(e)})

    # ═══════════════════════════════════════════════
    #  SUMMARY
    # ═══════════════════════════════════════════════

    summary = build_summary(all_results)
    print_summary(summary)

    try:
        doc_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        db.collection("batch_reprocess_summary").document(doc_id).set(_clean_for_firestore(summary))
        print(f"\n  Summary saved to Firestore: batch_reprocess_summary/{doc_id}")
    except Exception as e:
        print(f"\n  Failed to save summary: {e}")

    print("\n  DONE.")


if __name__ == "__main__":
    main()
