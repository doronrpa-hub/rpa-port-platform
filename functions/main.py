"""
RPA-PORT Cloud Functions
========================
Serverless functions that run automatically - no server needed.

Functions:
1. check_email_scheduled - Runs every 5 min, checks Gmail inbox
2. classify_document - Triggered when new document arrives in Firestore
3. enrich_knowledge - Runs every hour, fills knowledge gaps
4. on_classification_correction - Learns when user corrects a classification
5. api - HTTP API for web app
"""

import firebase_admin
from firebase_admin import credentials, firestore, storage
from firebase_functions import scheduler_fn, firestore_fn, https_fn, options
import json
import os
import re
import imaplib
import email as email_lib
from lib.classification_agents import run_full_classification, build_classification_email, process_and_send_report
from lib.knowledge_query import detect_knowledge_query, handle_knowledge_query
from lib.rcb_id import generate_rcb_id, RCBType
from lib.rcb_helpers import extract_text_from_attachments
from lib.rcb_helpers import helper_get_graph_token, helper_graph_messages, helper_graph_attachments, helper_graph_mark_read, helper_graph_send, to_hebrew_name, build_rcb_reply, get_rcb_secrets_internal, extract_text_from_attachments

# ── Optional agent imports (fail gracefully if modules have issues) ──
try:
    from lib.brain_commander import brain_commander_check, auto_learn_email_style
    BRAIN_COMMANDER_AVAILABLE = True
except ImportError as e:
    print(f"Brain Commander not available: {e}")
    BRAIN_COMMANDER_AVAILABLE = False

try:
    from lib.tracker import tracker_process_email, tracker_poll_active_deals
    TRACKER_AVAILABLE = True
except ImportError as e:
    print(f"Tracker not available: {e}")
    TRACKER_AVAILABLE = False

try:
    from lib.pupil import pupil_process_email
    PUPIL_AVAILABLE = True
except ImportError as e:
    print(f"Pupil not available: {e}")
    PUPIL_AVAILABLE = False

def get_secret(name):
    """Get secret from Google Cloud Secret Manager"""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        project_id = "rpa-port-customs"
        secret_path = f"projects/{project_id}/secrets/{name}/versions/latest"
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Secret {name} error: {e}")
        return None

from email.header import decode_header
from datetime import datetime, timedelta, timezone


# Initialize Firebase
firebase_admin.initialize_app()
db = None
bucket = None

def get_db():
    global db
    if db is None:
        db = firestore.client()
    return db

def get_bucket():
    global bucket
    if bucket is None:
        bucket = storage.bucket()
    return bucket



# ============================================================
# HELPER FUNCTIONS FOR EMAIL PROCESSING
# ============================================================

def extract_reply_email(from_str):
    """Extract email address from 'Name <email>' format"""
    import re
    match = re.search(r'<([^>]+)>', from_str)
    if match:
        return match.group(1)
    if '@' in from_str:
        return from_str.strip()
    return None


def send_ack_email(email_addr, email_pass, to_email, original_subject, attachments):
    """Send acknowledgment email immediately"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        att_list = "\n".join([f"  • {a['filename']}" for a in attachments])
        
        body = f"""שלום,

קיבלנו את המסמכים שלך ומתחילים בעיבוד.

📎 מסמכים שהתקבלו:
{att_list}

⏱️ זמן עיבוד משוער: 2-5 דקות

נשלח דוח מפורט בסיום העיבוד.

בברכה,
מערכת RCB
ר.פ.א - פורט בע"מ
"""
        
        msg = MIMEMultipart()
        msg["From"] = email_addr
        msg["To"] = to_email
        msg["Subject"] = f"✅ התקבל: {original_subject}"
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_addr, email_pass)
            server.send_message(msg)
        
        print(f"✅ ACK sent to {to_email}")
        
    except Exception as e:
        print(f"ACK email error: {e}")


def send_classification_report(email_addr, email_pass, to_email, original_subject, classifications, doc_id):
    """Send classification report email"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        # Try to use existing report builder
        try:
            from lib.classification_agents import build_classification_email
            body = build_classification_email(classifications)
        except:
            # Fallback: simple report
            lines = ["שלום,", "", "להלן תוצאות הסיווג:", ""]
            for i, c in enumerate(classifications, 1):
                if isinstance(c, dict):
                    lines.append(f"📦 פריט {i}:")
                    lines.append(f"   תיאור: {c.get('product_description', 'N/A')[:50]}")
                    lines.append(f"   פרט מכס: {c.get('suggested_hs', c.get('hs_code', 'ממתין'))}")
                    lines.append("")
            lines.extend(["בברכה,", "מערכת RCB", "ר.פ.א - פורט בע\"מ"])
            body = "\n".join(lines)
        
        msg = MIMEMultipart()
        msg["From"] = email_addr
        msg["To"] = to_email
        msg["Subject"] = f"📋 דוח סיווג: {original_subject}"
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_addr, email_pass)
            server.send_message(msg)
        
        print(f"✅ Report sent to {to_email}")
        
        # Update Firestore
        get_db().collection("inbox").document(doc_id).update({"report_sent": True})
        
    except Exception as e:
        print(f"Report email error: {e}")


# ============================================================
# FUNCTION 1: CHECK EMAIL (runs every 5 minutes)
# ============================================================
@scheduler_fn.on_schedule(schedule="every 5 minutes", memory=options.MemoryOption.GB_1, timeout_sec=300)
def check_email_scheduled(event: scheduler_fn.ScheduledEvent) -> None:
    """DISABLED Session 13.1: Consolidated into rcb_check_email. Was Gmail IMAP fallback."""
    print("⏸️ check_email_scheduled DISABLED — consolidated into rcb_check_email")
    return



def _simple_email_check(email_addr: str, email_pass: str):
    """Fallback simple email check (no dependencies)"""
    import imaplib
    import email as email_lib
    from datetime import datetime
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    print("📧 Running simple email check...")
    
    # Get processed IDs
    processed_ids = set()
    for doc in get_db().collection("inbox").stream():
        processed_ids.add(doc.id)
    
    # Connect
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_addr, email_pass)
        mail.select("inbox")
    except Exception as e:
        print(f"❌ Gmail connection error: {e}")
        return
    
    # Search only today's emails
    today = datetime.now().strftime("%d-%b-%Y")
    status, messages = mail.search(None, f'(SINCE "{today}")')
    email_ids = messages[0].split() if messages[0] else []
    
    print(f"📬 Found {len(email_ids)} emails from {today}")
    
    new_count = 0
    for eid in email_ids[:10]:  # Max 10 per run
        try:
            # Fetch headers first
            status, header_data = mail.fetch(eid, "(BODY.PEEK[HEADER])")
            msg = email_lib.message_from_bytes(header_data[0][1])
            
            msg_id = msg.get("Message-ID", str(eid))
            safe_id = re.sub(r'[/\\\.\[\]\*~<>]', '_', str(msg_id))[:100]
            
            if safe_id in processed_ids:
                continue
            
            new_count += 1
            subject = decode_email_header(msg.get("Subject", ""))
            from_str = decode_email_header(msg.get("From", ""))
            date_str = msg.get("Date", "")
            
            print(f"  📨 New: {subject[:40]}...")
            
            # Fetch full content
            status, msg_data = mail.fetch(eid, "(RFC822)")
            full_msg = email_lib.message_from_bytes(msg_data[0][1])
            
            # Extract body
            body_text = extract_body(full_msg)
            
            # Extract attachments
            attachments = extract_attachments(full_msg, body_text, subject)
            
            # Store email
            get_db().collection("inbox").document(safe_id).set({
                "from": from_str,
                "subject": subject,
                "date": date_str,
                "body": body_text[:10000] if body_text else "",
                "message_id": msg_id,
                "attachment_count": len(attachments),
                "attachments": [{
                    "filename": a["filename"],
                    "size": a["size"],
                    "type": a["type"],
                    "doc_type": a.get("doc_type", ""),
                    "storage_path": a.get("storage_path", "")
                } for a in attachments],
                "status": "received",
                "received_at": firestore.SERVER_TIMESTAMP,
                "ack_sent": False,
            })
            
            # Send ACK if has attachments
            if attachments:
                from_email = _extract_email(from_str)
                if from_email:
                    _send_ack(email_addr, email_pass, from_email, subject, attachments)
                    get_db().collection("inbox").document(safe_id).update({"ack_sent": True})
            
            # Process attachments
            for att in attachments:
                try:
                    classify_and_store(att, from_str, subject, date_str, body_text)
                except Exception as ce:
                    print(f"    ⚠️ Classification error: {ce}")
            
            # Update status
            get_db().collection("inbox").document(safe_id).update({
                "status": "completed",
                "processed_at": firestore.SERVER_TIMESTAMP,
            })
            
        except Exception as e:
            print(f"  ❌ Error processing {eid}: {e}")
    
    mail.logout()
    print(f"✅ Processed {new_count} new emails")


def _extract_email(from_str: str) -> str:
    """Extract email address from From header"""
    match = re.search(r'<([^>]+)>', from_str)
    if match:
        return match.group(1)
    if '@' in from_str:
        return from_str.strip()
    return ""


def _send_ack(email_addr: str, email_pass: str, to_email: str, subject: str, attachments: list):
    """Send acknowledgment email"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        att_list = "\n".join([f"  • {a['filename']}" for a in attachments])
        
        body = f"""שלום,

✅ קיבלנו את המסמכים שלך ומתחילים בעיבוד.

📎 מסמכים שהתקבלו ({len(attachments)}):
{att_list}

⏱️ זמן עיבוד משוער: 2-5 דקות

בברכה,
מערכת RCB - ר.פ.א פורט בע"מ
"""
        
        msg = MIMEMultipart()
        msg["From"] = email_addr
        msg["To"] = to_email
        msg["Subject"] = f"✅ התקבל: {subject}"
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_addr, email_pass)
            server.send_message(msg)
        
        print(f"    📤 ACK sent to {to_email}")
        
    except Exception as e:
        print(f"    ⚠️ ACK error: {e}")


# ============================================================
# FUNCTION 2: AUTO-CLASSIFY ON NEW DOCUMENT
# ============================================================
@firestore_fn.on_document_created(document="classifications/{classId}")
def on_new_classification(event: firestore_fn.Event) -> None:
    """When a new classification is created, try to auto-classify using knowledge base"""
    
    data = event.data.to_dict()
    if data.get("status") != "pending_classification":
        return

    class_id = event.params["classId"]
    product = data.get("product_description", "")
    seller = data.get("seller", "")
    supplier_hs = data.get("supplier_hs", "")

    # Step 1: Check if we've seen this seller + product before
    suggested_hs = None
    confidence = 0

    # Check seller history
    if seller:
        seller_id = re.sub(r'[^a-zA-Z0-9]', '_', seller.lower())[:50]
        seller_doc = get_db().collection("sellers").document(seller_id).get()
        if seller_doc.exists:
            seller_data = seller_doc.to_dict()
            known_hs = seller_data.get("known_hs_codes", [])
            if len(known_hs) == 1:
                suggested_hs = known_hs[0]
                confidence = 70
                print(f"Seller match: {seller} -> {suggested_hs}")

    # Check knowledge base for product match
    if product:
        kb_docs = get_db().collection("knowledge_base").where("category", "==", "hs_classifications").stream()
        for doc in kb_docs:
            kb = doc.to_dict()
            content = kb.get("content", {})
            products_seen = content.get("products", [])
            for p in products_seen:
                if any(word.lower() in product.lower() for word in p.split() if len(word) > 3):
                    suggested_hs = content.get("hs", "")
                    confidence = max(confidence, 60)
                    print(f"Product match: {product} -> {suggested_hs}")
                    break

    # If supplier provided an HS code, validate it
    if supplier_hs:
        # Check if supplier HS matches our knowledge
        kb_match = get_db().collection("knowledge_base").where("category", "==", "hs_classifications").stream()
        for doc in kb_match:
            kb = doc.to_dict()
            if kb.get("content", {}).get("hs", "").replace(".", "") == supplier_hs.replace(".", ""):
                suggested_hs = supplier_hs
                confidence = 80
                print(f"Supplier HS confirmed: {supplier_hs}")
                break

    # Update classification with suggestion
    if suggested_hs and confidence >= 60:
        get_db().collection("classifications").document(class_id).update({
            "suggested_hs": suggested_hs,
            "suggestion_confidence": confidence,
            "suggestion_source": "auto_knowledge_base",
            "status": "pending_review"
        })
        print(f"Auto-suggested {suggested_hs} (confidence: {confidence}%) for {class_id}")
    else:
        # Need Claude AI for complex classification
        get_db().collection("agent_tasks").add({
            "type": "ai_classification",
            "classification_id": class_id,
            "product_description": product,
            "seller": seller,
            "supplier_hs": supplier_hs,
            "status": "pending",
            "created_at": firestore.SERVER_TIMESTAMP
        })
        print(f"Created AI classification task for {class_id}")


# ============================================================
# FUNCTION 3: LEARN FROM CORRECTIONS
# ============================================================
@firestore_fn.on_document_updated(document="classifications/{classId}")
def on_classification_correction(event: firestore_fn.Event) -> None:
    """When user corrects a classification, learn from it"""
    
    before = event.data.before.to_dict()
    after = event.data.after.to_dict()

    # Check if this is a correction (status changed to confirmed/corrected)
    if after.get("status") not in ("confirmed", "corrected"):
        return
    if before.get("status") == after.get("status"):
        return

    class_id = event.params["classId"]
    final_hs = after.get("our_hs_code", "")
    product = after.get("product_description", "")
    seller = after.get("seller", "")
    suggested_hs = before.get("suggested_hs", "")

    if not final_hs:
        return

    print(f"Learning from correction: {class_id}")
    print(f"  Product: {product}")
    print(f"  Final HS: {final_hs}")
    if suggested_hs and suggested_hs != final_hs:
        print(f"  Was suggested: {suggested_hs} (WRONG)")

    # Update seller knowledge
    if seller:
        seller_id = re.sub(r'[^a-zA-Z0-9]', '_', seller.lower())[:50]
        seller_ref = get_db().collection("sellers").document(seller_id)
        seller_doc = seller_ref.get()
        if seller_doc.exists:
            existing = seller_doc.to_dict()
            known_hs = existing.get("known_hs_codes", [])
            if final_hs not in known_hs:
                known_hs.append(final_hs)
            seller_ref.update({"known_hs_codes": known_hs, "last_classification": datetime.now().isoformat()})
        else:
            seller_ref.set({
                "name": seller,
                "known_hs_codes": [final_hs],
                "last_classification": datetime.now().isoformat()
            })

    # Update HS knowledge base
    hs_id = f"hs_{final_hs.replace('.', '_')}"
    hs_ref = get_db().collection("knowledge_base").document(hs_id)
    hs_doc = hs_ref.get()
    if hs_doc.exists:
        existing = hs_doc.to_dict()
        content = existing.get("content", {})
        products = content.get("products", [])
        sellers_list = content.get("sellers", [])
        if product and product not in products:
            products.append(product[:200])
        if seller and seller not in sellers_list:
            sellers_list.append(seller)
        content["products"] = products
        content["sellers"] = sellers_list
        hs_ref.update({"content": content, "last_updated": datetime.now().isoformat()})
    else:
        hs_ref.set({
            "title": f"HS {final_hs} - Learned from classification",
            "category": "hs_classifications",
            "content": {
                "hs": final_hs,
                "products": [product[:200]] if product else [],
                "sellers": [seller] if seller else [],
                "learned_from": [class_id]
            },
            "source": "classification_learning",
            "created_at": firestore.SERVER_TIMESTAMP
        })

    # Log the learning event
    get_db().collection("learning_log").add({
        "type": "classification_correction",
        "classification_id": class_id,
        "final_hs": final_hs,
        "suggested_hs": suggested_hs,
        "was_correct": suggested_hs == final_hs,
        "product": product,
        "seller": seller,
        "learned_at": firestore.SERVER_TIMESTAMP
    })

    print(f"  Learned: {product[:50]} -> {final_hs}")


# ============================================================
# FUNCTION 4: ENRICHMENT (runs every hour)
# ============================================================
@scheduler_fn.on_schedule(schedule="every 1 hours", memory=options.MemoryOption.MB_256)
def enrich_knowledge(event: scheduler_fn.ScheduledEvent) -> None:
    """Periodically enrich knowledge base — Phase 3"""
    try:
        from lib.enrichment_agent import create_enrichment_agent
        from lib.librarian_index import rebuild_index

        enrichment = create_enrichment_agent(get_db())

        # 1. Check and tag any completed PC Agent downloads
        tagged = enrichment.check_and_tag_completed_downloads()
        print(f" Tagged {len(tagged)} completed downloads")

        # 2. Run scheduled enrichment tasks (checks 23 task types)
        summary = enrichment.run_scheduled_enrichments()
        print(f" Enrichment: checked {summary['tasks_checked']}, ran {summary['tasks_run']}")

        # 3. Get status for logging
        stats = enrichment.get_learning_stats()
        print(f" Knowledge: {stats['total_learned']} learned, "
              f"{stats['corrections']} corrections, "
              f"{stats['pc_agent_downloads']} downloads")

    except Exception as e:
        print(f" Enrichment error: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# FUNCTION 5: HTTP API FOR WEB APP
# ============================================================
@https_fn.on_request(cors=options.CorsOptions(cors_origins="*", cors_methods=["GET", "POST"]))
def api(req: https_fn.Request) -> https_fn.Response:
    """REST API for the web application"""
    
    path = req.path.strip("/").replace("api/", "")

    method = req.method

    # Dashboard stats
    if path in ("stats", "") and method == "GET":
        stats = {
            "knowledge_count": len(list(get_db().collection("knowledge_base").stream())),
            "inbox_count": len(list(get_db().collection("inbox").stream())),
            "classifications_pending": len(list(get_db().collection("classifications").where("status", "==", "pending_classification").stream())),
            "classifications_total": len(list(get_db().collection("classifications").stream())),
            "sellers_count": len(list(get_db().collection("sellers").stream())),
            "pending_tasks": len(list(get_db().collection("pending_tasks").where("status", "==", "pending").stream())),
            "learning_events": len(list(get_db().collection("learning_log").stream()))
        }
        return https_fn.Response(json.dumps(stats), content_type="application/json")

    # Get classifications
    elif path == "classifications" and method == "GET":
        result = []
        for doc in get_db().collection("classifications").order_by("created_at", direction=firestore.Query.DESCENDING).limit(50).stream():
            d = doc.to_dict()
            d["id"] = doc.id
            d.pop("extracted_text", None)  # Don't send large text
            result.append(d)
        return https_fn.Response(json.dumps(result, default=str), content_type="application/json")

    # Correct a classification (triggers learning)
    elif path.startswith("classifications/") and method == "POST":
        class_id = path.split("/")[1]
        data = req.get_json()
        get_db().collection("classifications").document(class_id).update({
            "our_hs_code": data.get("hs_code"),
            "status": "corrected" if data.get("is_correction") else "confirmed",
            "corrected_by": data.get("user", "admin"),
            "corrected_at": firestore.SERVER_TIMESTAMP
        })
        return https_fn.Response(json.dumps({"ok": True}), content_type="application/json")

    # Get knowledge base
    elif path == "knowledge" and method == "GET":
        result = []
        for doc in get_db().collection("knowledge_base").stream():
            d = doc.to_dict()
            d["id"] = doc.id
            result.append(d)
        return https_fn.Response(json.dumps(result, default=str), content_type="application/json")

    # Get inbox
    elif path == "inbox" and method == "GET":
        result = []
        for doc in get_db().collection("inbox").order_by("processed_at", direction=firestore.Query.DESCENDING).limit(50).stream():
            d = doc.to_dict()
            d["id"] = doc.id
            d.pop("body", None)
            result.append(d)
        return https_fn.Response(json.dumps(result, default=str), content_type="application/json")

    # Get sellers
    elif path == "sellers" and method == "GET":
        result = []
        for doc in get_db().collection("sellers").stream():
            d = doc.to_dict()
            d["id"] = doc.id
            result.append(d)
        return https_fn.Response(json.dumps(result, default=str), content_type="application/json")

    # Get learning log
    elif path == "learning" and method == "GET":
        result = []
        for doc in get_db().collection("learning_log").order_by("learned_at", direction=firestore.Query.DESCENDING).limit(50).stream():
            d = doc.to_dict()
            d["id"] = doc.id
            result.append(d)
        return https_fn.Response(json.dumps(result, default=str), content_type="application/json")

    return https_fn.Response(json.dumps({"error": "Not found"}), status=404, content_type="application/json")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def decode_email_header(raw):
    """Decode email header (subject, from, etc.)"""
    if not raw:
        return ""
    decoded = decode_header(raw)
    return " ".join([
        part.decode(enc or 'utf-8') if isinstance(part, bytes) else str(part)
        for part, enc in decoded
    ])


def extract_body(msg):
    """Extract plain text body from email"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        body += payload.decode(charset, errors='replace')
                    except:
                        body += payload.decode('utf-8', errors='replace')
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode('utf-8', errors='replace')
    return body


def extract_attachments(msg, body_text, subject):
    """Extract attachments from email, detect type, upload to storage"""
    attachments = []
    if not msg.is_multipart():
        return attachments

    for part in msg.walk():
        content_disp = str(part.get("Content-Disposition", ""))
        if "attachment" not in content_disp and not part.get_filename():
            continue

        filename = part.get_filename()
        if not filename:
            continue

        filename = decode_email_header(filename)
        file_data = part.get_payload(decode=True)
        if not file_data:
            continue

        safe_name = re.sub(r'[^\w\-_\. ]', '_', filename)
        file_ext = os.path.splitext(filename)[1].lower()
        doc_type = detect_document_type(filename, body_text, subject)

        # Upload to Firebase Storage
        storage_path = f"inbox/{datetime.now().strftime('%Y%m%d')}_{safe_name}"
        try:
            blob = get_bucket().blob(storage_path)
            blob.upload_from_string(file_data)
        except Exception as e:
            print(f"Upload failed: {e}")
            storage_path = ""

        # Extract text from PDF
        extracted_text = ""
        if file_ext == '.pdf':
            try:
                import pdfplumber
                import io
                with pdfplumber.open(io.BytesIO(file_data)) as pdf:
                    for page in pdf.pages[:30]:
                        t = page.extract_text()
                        if t:
                            extracted_text += t + "\n"
            except Exception:
                pass

        attachments.append({
            "filename": filename,
            "size": len(file_data),
            "type": file_ext,
            "doc_type": doc_type,
            "storage_path": storage_path,
            "extracted_text": extracted_text[:50000]
        })

    return attachments


def detect_document_type(filename, body="", subject=""):
    """Detect document type from filename and content"""
    fn = filename.lower()
    body_lower = (body + " " + subject).lower()

    # Commercial Invoice
    if any(kw in fn for kw in ['invoice', 'inv_', 'inv-', 'facture', 'rechnung', 'faktura', 'commerciale']):
        return "commercial_invoice"
    # Packing List
    if any(kw in fn for kw in ['packing', 'pl_', 'pl-', 'packing_list']):
        return "packing_list"
    # Customs Declaration
    if any(kw in fn for kw in ['wg_', 'imp_dec', 'exp_dec', 'declaration', 'customs_dec']):
        return "customs_declaration"
    # Regulatory Certificate
    if any(kw in fn for kw in ['cert_emc', 'cert_rf', 'cert_safety', '_emc_', '_rf_', '_safety_',
                                'sii', 'moc_', '_moc', 'polygon', 'intertek', 'sgs', 'tuv']):
        return "regulatory_certificate"
    # Certificate of Origin
    if any(kw in fn for kw in ['eur.1', 'eur1', 'origin', 'co_', 'coo_', 'form_a']):
        return "certificate_of_origin"
    if 'certificate' in fn and 'origin' in fn:
        return "certificate_of_origin"
    # Bill of Lading
    if any(kw in fn for kw in ['b/l', 'bl_', 'bl-', 'bill_of_lading', 'awb', 'airway']):
        return "bill_of_lading"
    # Insurance
    if any(kw in fn for kw in ['insurance', 'policy']):
        return "insurance"
    # Import Permit
    if any(kw in fn for kw in ['license', 'licence', 'permit']):
        return "import_permit"
    # Lab Report
    if any(kw in fn for kw in ['lab_', 'test_', 'analysis', 'report_', 'coa_']):
        return "lab_report"
    # Proforma
    if any(kw in fn for kw in ['proforma', 'pro_forma', 'pro-forma']):
        return "proforma_invoice"
    # Scanned document
    if re.match(r'^doc\d{10,}', fn):
        return "scanned_document"

    # Body clues
    if 'invoice' in body_lower:
        if any(fn.endswith(ext) for ext in ['.pdf', '.xlsx']):
            return "possible_invoice"

    return "unknown"


def classify_and_store(att, from_str, subject, date_str, body_text):
    """Classify attachment and store in appropriate collection"""
    doc_type = att["doc_type"]
    text = att.get("extracted_text", "")

    if doc_type in ("commercial_invoice", "possible_invoice", "proforma_invoice"):
        # Extract invoice fields and create classification
        invoice_data = extract_invoice_fields(text)
        if invoice_data:
            class_id = f"class_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            get_db().collection("classifications").document(class_id).set({
                "seller": invoice_data.get("seller", ""),
                "buyer": invoice_data.get("buyer", ""),
                "product_description": invoice_data.get("product", ""),
                "supplier_hs": invoice_data.get("supplier_hs", ""),
                "total_value": invoice_data.get("total_value", ""),
                "currency": invoice_data.get("currency", ""),
                "incoterms": invoice_data.get("incoterms", ""),
                "origin": invoice_data.get("origin", ""),
                "our_hs_code": "PENDING",
                "status": "pending_classification",
                "source_email": from_str,
                "attachment_path": att.get("storage_path", ""),
                "extracted_text": text[:10000],
                "created_at": firestore.SERVER_TIMESTAMP
            })

    elif doc_type == "customs_declaration":
        hs_match = re.search(r'(\d{4}[\.\s]?\d{2}[\.\s]?\d{2,4})', text or "")
        get_db().collection("declarations").add({
            "filename": att["filename"],
            "hs_code": hs_match.group(1) if hs_match else None,
            "from_email": from_str,
            "attachment_path": att.get("storage_path", ""),
            "created_at": firestore.SERVER_TIMESTAMP
        })

    elif doc_type == "regulatory_certificate":
        cert_type = "general"
        fn = att["filename"].lower()
        if 'emc' in fn: cert_type = "emc"
        elif 'rf' in fn: cert_type = "rf_radio"
        elif 'safety' in fn: cert_type = "safety"

        model_match = re.search(r'([A-Z]{2,5}[-_]\d{3,}[-_]?\w*)', att["filename"], re.IGNORECASE)
        expiry_match = re.search(r'[Ee]xpires?[_\s-]*(\d{1,2}[-_][A-Za-z]{3}[-_]\d{2,4})', att["filename"])

        get_db().collection("regulatory_certificates").add({
            "filename": att["filename"],
            "cert_type": cert_type,
            "model_number": model_match.group(1) if model_match else "",
            "expiry_date": expiry_match.group(1) if expiry_match else "",
            "from_email": from_str,
            "attachment_path": att.get("storage_path", ""),
            "created_at": firestore.SERVER_TIMESTAMP
        })

    elif doc_type in ("certificate_of_origin", "packing_list", "bill_of_lading"):
        collection_map = {
            "certificate_of_origin": "origin_certificates",
            "packing_list": "packing_lists",
            "bill_of_lading": "bills_of_lading"
        }
        get_db().collection(collection_map[doc_type]).add({
            "filename": att["filename"],
            "from_email": from_str,
            "attachment_path": att.get("storage_path", ""),
            "created_at": firestore.SERVER_TIMESTAMP
        })


def extract_invoice_fields(text):
    """Extract structured data from invoice text"""
    if not text or len(text) < 50:
        return None

    data = {}
    text_upper = text.upper()

    # Seller
    for pat in [r'(?:SELLER|EXPORTER|SHIPPER|FROM)[:\s]*(.+)', r'(?:Seller|Exporter)[:\s]*(.+)']:
        m = re.search(pat, text)
        if m:
            data["seller"] = m.group(1).strip()[:100]
            break

    # Buyer
    for pat in [r'(?:BUYER|CONSIGNEE|TO|IMPORTER)[:\s]*(.+)', r'(?:Buyer|Consignee)[:\s]*(.+)']:
        m = re.search(pat, text)
        if m:
            data["buyer"] = m.group(1).strip()[:100]
            break

    # HS Code - use all known field names
    hs_fields = ['H\\.S\\.NUMBER', 'H\\.S\\.CODE', 'HTS CODE', 'STAT\\.Code',
                  'HS CODE', 'TARIFF CODE', 'CN CODE', 'Commodity Code', 'HSCODE']
    for field in hs_fields:
        m = re.search(f'{field}[:\\s]*([\\d\\.]+)', text, re.IGNORECASE)
        if m:
            data["supplier_hs"] = m.group(1).strip()
            break
    if "supplier_hs" not in data:
        m = re.search(r'(\d{4}\.\d{2}\.\d{2,4})', text)
        if m:
            data["supplier_hs"] = m.group(1)

    # Currency + total
    for pat in [r'(?:TOTAL|GRAND TOTAL|AMOUNT)[:\s]*([A-Z]{3})\s*([\d,\.]+)',
                r'([A-Z]{3})\s*([\d,\.]+)\s*(?:TOTAL|CIF|FOB)']:
        m = re.search(pat, text_upper)
        if m:
            data["currency"] = m.group(1)
            data["total_value"] = m.group(2).replace(",", "")
            break

    # Incoterms
    for term in ['EXW', 'FCA', 'FAS', 'FOB', 'CFR', 'CIF', 'CPT', 'CIP', 'DAP', 'DPU', 'DDP']:
        if term in text_upper:
            data["incoterms"] = term
            break

    # Origin
    for pat in [r'(?:ORIGIN|COUNTRY OF ORIGIN|MADE IN)[:\s]*([A-Z][a-zA-Z\s]+)']:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            data["origin"] = m.group(1).strip()[:50]
            break

    # Product
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if len(line) > 20 and not any(kw in line.upper() for kw in ['INVOICE', 'DATE', 'SELLER', 'BUYER', 'TOTAL', 'ADDRESS']):
            if re.search(r'[A-Za-z]{3,}', line):
                data["product"] = line[:200]
                break

    return data if data else None


# Need this for Cloud Functions

# ============================================================
# FUNCTION 5: RCB API ENDPOINTS
# ============================================================
@https_fn.on_request(cors=options.CorsOptions(cors_origins="*", cors_methods=["GET", "POST"]))

# ============================================================
# RCB HELPER FUNCTIONS
# ============================================================

def graph_forward_email(access_token, user_email, message_id, to_email, comment):
    """Forward email"""
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{message_id}/forward"
        requests.post(url, headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
                     json={'comment': comment, 'toRecipients': [{'emailAddress': {'address': to_email}}]})
        return True
    except:
        return False

def get_anthropic_key():
    """Get Anthropic API key"""
    return get_secret('ANTHROPIC_API_KEY')

# Hebrew name translations
@https_fn.on_request(cors=options.CorsOptions(cors_origins="*", cors_methods=["GET", "POST"]))
def rcb_api(req: https_fn.Request) -> https_fn.Response:
    """RCB API endpoints"""
    path = req.path.strip("/").split("/")[-1] if req.path else ""
    method = req.method
    
    # Health check
    if path == "" or path == "health":
        return https_fn.Response(json.dumps({"status": "ok", "service": "RCB API"}), content_type="application/json")
    
    # Get logs
    if path == "logs":
        logs = []
        for doc in get_db().collection("rcb_logs").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(50).stream():
            d = doc.to_dict()
            d["id"] = doc.id
            logs.append(d)
        return https_fn.Response(json.dumps(logs, default=str), content_type="application/json")
    
    # Test connection
    if path == "test":
        try:
            secrets = get_rcb_secrets_internal(get_secret)
        except Exception as e1:
            return https_fn.Response(json.dumps({"ok": False, "error": f"secrets error: {e1}"}), content_type="application/json")
        if not secrets:
            return https_fn.Response(json.dumps({"ok": False, "error": "No secrets returned"}), content_type="application/json")
        try:
            access_token = helper_get_graph_token(secrets)
        except Exception as e2:
            return https_fn.Response(json.dumps({"ok": False, "error": f"token error: {e2}"}), content_type="application/json")
        if access_token:
            return https_fn.Response(json.dumps({"ok": True, "email": secrets.get('RCB_EMAIL'), "method": "Graph API"}), content_type="application/json")
        return https_fn.Response(json.dumps({"ok": False, "error": "No token"}), content_type="application/json")
    
    # Save backup
    if path == "backup" and method == "POST":
        try:
            data = req.get_json()
            session_id = data.get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
            backup_content = data.get("content", "")
            get_db().collection("session_backups").document(session_id).set({
                "content": backup_content,
                "created_at": firestore.SERVER_TIMESTAMP,
                "session_id": session_id
            })
            # Email backup
            secrets = get_rcb_secrets_internal(get_secret)
            if secrets:
                access_token = helper_get_graph_token(secrets)
                if access_token:
                    helper_graph_send(access_token, secrets['RCB_EMAIL'], 
                        secrets.get('RCB_FALLBACK_EMAIL', 'airpaort@gmail.com'),
                        f"[RCB Backup] Session {session_id}",
                        f"<pre>{backup_content}</pre>")
            return https_fn.Response(json.dumps({"ok": True, "session_id": session_id, "message": "Backup saved to Firestore and emailed"}), content_type="application/json")
        except Exception as e:
            return https_fn.Response(json.dumps({"ok": False, "error": str(e)}), status=500, content_type="application/json")
    
    # List backups
    if path == "backups":
        backups = []
        for doc in get_db().collection("session_backups").order_by("created_at", direction=firestore.Query.DESCENDING).limit(20).stream():
            d = doc.to_dict()
            backups.append({"id": doc.id, "session_id": d.get("session_id"), "created_at": str(d.get("created_at"))})
        return https_fn.Response(json.dumps(backups, default=str), content_type="application/json")
    
    # Get backup by ID
    if path.startswith("backup/"):
        bid = path.split("/")[1] if "/" in path else path.replace("backup", "")
        doc = get_db().collection("session_backups").document(bid).get()
        if doc.exists:
            return https_fn.Response(json.dumps(doc.to_dict(), default=str), content_type="application/json")
        return https_fn.Response(json.dumps({"error": "Not found"}), status=404, content_type="application/json")
    
    return https_fn.Response(json.dumps({"error": "Unknown endpoint"}), status=404, content_type="application/json")


# ============================================================
# FUNCTION 6: RCB EMAIL HANDLER - GRAPH API
# ============================================================

# ============================================================
# CLASSIFICATION PROCESSING (called after acknowledgment)
# ============================================================

@scheduler_fn.on_schedule(schedule="every 2 minutes", memory=options.MemoryOption.GB_1, timeout_sec=540)
def rcb_check_email(event: scheduler_fn.ScheduledEvent) -> None:
    """Check rcb@rpa-port.co.il inbox - process emails from last 2 days"""
    print("🤖 RCB checking email via Graph API...")
    
    secrets = get_rcb_secrets_internal(get_secret)
    if not secrets:
        print("❌ No secrets configured")
        return
    
    rcb_email = secrets.get('RCB_EMAIL', 'rcb@rpa-port.co.il')
    
    access_token = helper_get_graph_token(secrets)
    if not access_token:
        print("❌ Failed to get access token")
        return
    
    # Get ALL messages from last 2 days (ignore read/unread)
    from datetime import datetime, timedelta, timezone
    # TEMPORARY: 2-hour window to prevent reprocessing old emails after hash fix
    two_days_ago = (datetime.utcnow() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    url = f"https://graph.microsoft.com/v1.0/users/{rcb_email}/mailFolders/inbox/messages"
    params = {
        '$top': 50,
        '$orderby': 'receivedDateTime desc',
        '$filter': f"receivedDateTime ge {two_days_ago}"
    }
    
    import requests
    response = requests.get(url, headers={'Authorization': f'Bearer {access_token}'}, params=params)
    messages = response.json().get('value', []) if response.status_code == 200 else []
    
    if not messages:
        print("📭 No messages in last 2 days")
        return
    
    print(f"📬 Found {len(messages)} messages in last 2 days")
    
    for msg in messages:
        msg_id = msg.get('id')
        internet_msg_id = msg.get('internetMessageId', '')  # RFC 2822 Message-ID for threading
        subject = msg.get('subject', 'No Subject')
        from_data = msg.get('from', {}).get('emailAddress', {})
        from_email = from_data.get('address', '')
        from_name = from_data.get('name', '')
        to_recipients = msg.get('toRecipients', [])
        
        # Check if sent TO rcb@ (not CC)
        is_direct = any(rcb_email.lower() in r.get('emailAddress', {}).get('address', '').lower() 
                       for r in to_recipients)
        
        print(f"    DEBUG: {subject[:30]} from={from_email} is_direct={is_direct}")

        # Skip system emails for all paths
        if 'undeliverable' in subject.lower() or 'backup' in subject.lower():
            continue
        if '[RCB-SELFTEST]' in subject:
            continue

        # ── CC emails: silent learning from ALL senders, no reply ──
        if not is_direct:
            import hashlib as _hl
            safe_id_cc = _hl.md5(msg_id.encode()).hexdigest()
            if get_db().collection("rcb_processed").document(safe_id_cc).get().exists:
                continue

            print(f"  👁️ CC observation: {subject[:50]} from {from_email}")

            # Pupil: silent observation (FREE — Firestore only, no replies)
            if PUPIL_AVAILABLE:
                try:
                    pupil_process_email(
                        msg, get_db(), firestore, access_token, rcb_email, get_secret
                    )
                except Exception as pe:
                    print(f"    ⚠️ Pupil CC error (non-fatal): {pe}")

            # Tracker: observe shipping updates (FREE — no notifications when is_direct=False)
            if TRACKER_AVAILABLE:
                try:
                    tracker_process_email(
                        msg, get_db(), firestore, access_token, rcb_email, get_secret,
                        is_direct=False
                    )
                except Exception as te:
                    print(f"    ⚠️ Tracker CC error (non-fatal): {te}")

            get_db().collection("rcb_processed").document(safe_id_cc).set({
                "processed_at": firestore.SERVER_TIMESTAMP,
                "subject": subject,
                "from": from_email,
                "type": "cc_observation",
            })
            continue

        # ── Direct TO emails: full pipeline, only from @rpa-port.co.il ──
        if not from_email.lower().endswith('@rpa-port.co.il'):
            continue

        # Check if already processed
        import hashlib; safe_id = hashlib.md5(msg_id.encode()).hexdigest()
        if get_db().collection("rcb_processed").document(safe_id).get().exists:
            continue
        
        print(f"  📧 Processing: {subject[:50]} from {from_email}")
        
        # Get attachments
        raw_attachments = helper_graph_attachments(access_token, rcb_email, msg_id)
        attachments = []
        for att in raw_attachments:
            if att.get('@odata.type') == '#microsoft.graph.fileAttachment':
                name = att.get('name', 'file')
                ext = os.path.splitext(name)[1].lower()
                attachments.append({'filename': name, 'type': ext})
        
        print(f"    📎 {len(attachments)} attachments")

        # ── Brain Commander: Father channel check ──
        # If doron@ sends a brain command, handle it and skip classification
        if BRAIN_COMMANDER_AVAILABLE:
            try:
                brain_result = brain_commander_check(msg, get_db(), access_token, rcb_email, get_secret)
                if brain_result and brain_result.get('handled'):
                    print(f"    🧠 Brain Commander handled: {brain_result.get('command', {}).get('type', 'unknown')}")
                    helper_graph_mark_read(access_token, rcb_email, msg_id)
                    get_db().collection("rcb_processed").document(safe_id).set({
                        "processed_at": firestore.SERVER_TIMESTAMP,
                        "subject": subject,
                        "from": from_email,
                        "type": "brain_command",
                    })
                    continue
            except Exception as bc_err:
                print(f"    ⚠️ Brain Commander error (continuing normally): {bc_err}")

        # ── Session 13 v4.1.0: Knowledge Query Detection ──
        # If team member asks a question (no commercial docs), answer it
        # and skip the classification pipeline entirely.
        try:
            msg["attachments"] = raw_attachments
            if detect_knowledge_query(msg):
                try:
                    rcb_id = generate_rcb_id(get_db(), firestore, RCBType.KNOWLEDGE_QUERY)
                except Exception:
                    rcb_id = "RCB-UNKNOWN-KQ"
                print(f"  📚 [{rcb_id}] Knowledge query detected from {from_email}")
                kq_result = handle_knowledge_query(
                    msg=msg,
                    db=get_db(),
                    firestore_module=firestore,
                    access_token=access_token,
                    rcb_email=rcb_email,
                    get_secret_func=get_secret,
                )
                print(f"  📚 [{rcb_id}] Knowledge query result: {kq_result.get('status')}")
                helper_graph_mark_read(access_token, rcb_email, msg_id)
                get_db().collection("rcb_processed").document(safe_id).set({
                    "processed_at": firestore.SERVER_TIMESTAMP,
                    "subject": subject,
                    "from": from_email,
                    "type": "knowledge_query",
                    "rcb_id": rcb_id,
                })
                continue
        except Exception as kq_err:
            print(f"  ⚠️ Knowledge query detection error: {kq_err}")


        # Consolidated: ONE email with ack + classification + clarification
        try:
            rcb_id = generate_rcb_id(get_db(), firestore, RCBType.CLASSIFICATION)
        except Exception:
            rcb_id = "RCB-UNKNOWN-CLS"
        print(f"  🏷️ [{rcb_id}] Processing classification")

        # Mark as processed immediately to prevent double-processing
        get_db().collection("rcb_processed").document(safe_id).set({
            "processed_at": firestore.SERVER_TIMESTAMP,
            "subject": subject,
            "from": from_email,
            "rcb_id": rcb_id,
        })

        try:
            # Extract email body for URL detection and context
            email_body = msg.get('body', {}).get('content', '') or msg.get('bodyPreview', '')
            if msg.get('body', {}).get('contentType', '') == 'html' and email_body:
                import re as _re
                email_body = _re.sub(r'<[^>]+>', ' ', email_body)
                email_body = _re.sub(r'\s+', ' ', email_body).strip()

            process_and_send_report(
                access_token, rcb_email, from_email, subject,
                from_name, raw_attachments, msg_id, get_secret,
                get_db(), firestore, helper_graph_send, extract_text_from_attachments,
                email_body=email_body,
                internet_message_id=internet_msg_id,
            )
        except Exception as ce:
            print(f"    ⚠️ Classification error: {ce}")

        # ── Tracker: Feed email as observation for deal tracking ──
        if TRACKER_AVAILABLE:
            try:
                tracker_process_email(
                    msg, get_db(), firestore, access_token, rcb_email, get_secret,
                    is_direct=is_direct
                )
            except Exception as te:
                print(f"    ⚠️ Tracker error (non-fatal): {te}")

        # ── Pupil: Passive learning from every email ──
        if PUPIL_AVAILABLE:
            try:
                pupil_process_email(
                    msg, get_db(), firestore, access_token, rcb_email, get_secret
                )
            except Exception as pe:
                print(f"    ⚠️ Pupil error (non-fatal): {pe}")

    print("✅ RCB check complete")



# ============================================================================
# MONITOR AGENT

# ============================================================================
# MONITOR AGENT
# ============================================================================

@scheduler_fn.on_schedule(
    schedule="every 5 minutes",
    region="us-central1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=180
)
def monitor_agent(event: scheduler_fn.ScheduledEvent) -> None:
    """RCB System Monitor - runs every 5 minutes, auto-fixes known issues"""
    print("🤖 Monitor Agent starting...")
    
    errors_fixed = 0
    errors_escalated = 0
    
    try:
        # Check 1: rcb_processed queue stuck (more than 20 docs)
        processed_count = len(list(get_db().collection("rcb_processed").limit(25).stream()))
        if processed_count > 20:
            print(f"⚠️ Queue large: {processed_count} docs - cleaning old entries")
            # Auto-fix: delete docs older than 3 days
            from datetime import datetime, timedelta, timezone
            cutoff = datetime.now(timezone.utc) - timedelta(days=3)
            for doc in get_db().collection("rcb_processed").stream():
                data = doc.to_dict()
                if data.get("processed_at") and data.get("processed_at") < cutoff:
                    doc.reference.delete()
                    errors_fixed += 1
            print(f"  🔧 Auto-fixed: deleted {errors_fixed} old records")
        
        # Check 2: Failed classifications (processed but no classification in last 24h)
        from datetime import datetime, timedelta, timezone
        yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
        
        processed_recently = {}
        for doc in get_db().collection("rcb_processed").stream():
            data = doc.to_dict()
            ts = data.get("processed_at")
            if ts and ts > yesterday:
                processed_recently[data.get("subject", "")] = doc.id
        
        classified_recently = set()
        for doc in get_db().collection("rcb_classifications").stream():
            data = doc.to_dict()
            ts = data.get("timestamp")
            if ts and ts > yesterday:
                classified_recently.add(data.get("subject", ""))
        
        failed = set(processed_recently.keys()) - classified_recently
        if len(failed) > 3:
            print(f"⚠️ {len(failed)} failed classifications - queuing retry")
            for subj in list(failed)[:5]:  # Retry max 5
                doc_id = processed_recently[subj]
                get_db().collection("rcb_processed").document(doc_id).delete()
                errors_fixed += 1
                print(f"  🔄 Retry queued: {subj[:30]}")
        
        # Check 3: System status update
        status = "healthy" if errors_fixed == 0 and len(failed) < 3 else "degraded"
        get_db().collection("system_status").document("rcb_monitor").set({
            "last_check": datetime.now(timezone.utc),
            "status": status,
            "queue_size": processed_count,
            "errors_fixed": errors_fixed,
            "pending_retries": len(failed)
        })
        
        # Alert master if too many issues (disabled — Doron requested no system alert emails)
        if len(failed) > 5 or errors_fixed > 10:
            print(f"⚠️ Would alert: {len(failed)} failed, {errors_fixed} fixes (email alerts disabled)")
            errors_escalated += 1
        
        print(f"✅ Monitor complete: {errors_fixed} fixed, {errors_escalated} escalated")
        
    except Exception as e:
        print(f"❌ Monitor error: {e}")
        import traceback
        traceback.print_exc()

@https_fn.on_request(region="us-central1")
def monitor_agent_manual(req: https_fn.Request) -> https_fn.Response:
    """Manual trigger for testing"""
    print("🤖 Manual monitor trigger...")
    return https_fn.Response("Monitor OK", status=200)

# ============================================================
# AUTO-CLEANUP: Remove old rcb_processed docs (older than 7 days)
# ============================================================
@scheduler_fn.on_schedule(schedule="every 24 hours")
def rcb_cleanup_old_processed(event: scheduler_fn.ScheduledEvent) -> None:
    """Delete rcb_processed documents older than 7 days"""
    print("🧹 Starting cleanup of old processed records...")
    
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    
    deleted = 0
    try:
        docs = get_db().collection("rcb_processed").stream()
        for doc in docs:
            data = doc.to_dict()
            processed_at = data.get("processed_at")
            if processed_at and processed_at < cutoff:
                doc.reference.delete()
                deleted += 1
                print(f"  🗑️ Deleted: {data.get('subject', 'unknown')[:30]}")
    except Exception as e:
        print(f"❌ Cleanup error: {e}")
    
    print(f"✅ Cleanup complete: {deleted} old records deleted")


# ============================================================
# FAILED CLASSIFICATIONS RETRY
# ============================================================
@scheduler_fn.on_schedule(schedule="every 6 hours")
def rcb_retry_failed(event: scheduler_fn.ScheduledEvent) -> None:
    """Retry failed classifications from last 24 hours"""
    print("🔄 Checking for failed classifications to retry...")
    
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    
    retried = 0
    try:
        # Find processed emails without classification
        processed_docs = get_db().collection("rcb_processed").stream()
        processed_subjects = {}
        for doc in processed_docs:
            data = doc.to_dict()
            if data.get("processed_at") and data.get("processed_at") > cutoff:
                processed_subjects[data.get("subject", "")] = doc.id
        
        # Find classifications
        classified_subjects = set()
        class_docs = get_db().collection("rcb_classifications").stream()
        for doc in class_docs:
            data = doc.to_dict()
            if data.get("timestamp") and data.get("timestamp") > cutoff:
                classified_subjects.add(data.get("subject", ""))
        
        # Find failed (processed but not classified)
        failed = set(processed_subjects.keys()) - classified_subjects
        
        for subject in failed:
            doc_id = processed_subjects[subject]
            # Delete from processed so it will be retried
            get_db().collection("rcb_processed").document(doc_id).delete()
            retried += 1
            print(f"  🔄 Queued for retry: {subject[:40]}")
        
    except Exception as e:
        print(f"❌ Retry check error: {e}")
    
    print(f"✅ Retry check complete: {retried} emails queued for retry")


# ============================================================
# HEALTH CHECK & EMAIL ALERTS
# ============================================================
@scheduler_fn.on_schedule(schedule="every 1 hours")
def rcb_health_check(event: scheduler_fn.ScheduledEvent) -> None:
    """Check system health and alert if stuck"""
    print("🏥 Running health check...")
    
    from datetime import datetime, timedelta, timezone
    import requests
    
    now = datetime.now(timezone.utc)
    issues = []
    
    try:
        # Check 1: Any classifications in last 6 hours?
        six_hours_ago = now - timedelta(hours=6)
        recent_classifications = list(get_db().collection("rcb_classifications")
            .order_by("timestamp", direction="DESCENDING")
            .limit(1).stream())
        
        if recent_classifications:
            last_class = recent_classifications[0].to_dict()
            last_time = last_class.get("timestamp")
            if last_time and last_time < six_hours_ago:
                issues.append("No classifications in last 6 hours")
        
        # Check 2: Any errors in monitor_errors?
        recent_errors = list(get_db().collection("monitor_errors")
            .order_by("timestamp", direction="DESCENDING")
            .limit(5).stream())
        
        error_count = len([e for e in recent_errors if e.to_dict().get("timestamp", now) > six_hours_ago])
        if error_count >= 3:
            issues.append(f"{error_count} errors in last 6 hours")
        
        # Check 3: Queue stuck? (processed but pending > 5)
        pending = 0
        processed_docs = get_db().collection("rcb_processed").stream()
        for doc in processed_docs:
            data = doc.to_dict()
            if data.get("processed_at") and data.get("processed_at") > six_hours_ago:
                pending += 1
        
        if pending > 10:
            issues.append(f"Queue may be stuck: {pending} processed in 6 hours")
        
        # Update system status
        status = "healthy" if not issues else "degraded"
        get_db().collection("system_status").document("rcb").set({
            "last_check": now,
            "status": status,
            "issues": issues,
            "pending_count": pending,
            "error_count": error_count if 'error_count' in dir() else 0
        })
        
        # Send alert email if issues (disabled — Doron requested no system alert emails)
        if issues:
            print(f"⚠️ Issues detected (email alerts disabled): {issues}")
        else:
            print("✅ System healthy")
            
    except Exception as e:
        print(f"❌ Health check error: {e}")


def _send_alert_email(issues):
    """Send alert email to master"""
    try:
        secrets = get_rcb_secrets_internal(get_secret)
        access_token = helper_get_graph_token(secrets)
        if not access_token:
            return
        
        rcb_email = secrets.get('RCB_EMAIL', 'rcb@rpa-port.co.il')
        master_email = "doron@rpa-port.co.il"
        
        issues_html = "<br>".join([f"⚠️ {issue}" for issue in issues])
        body = f'''<div dir="rtl" style="font-family:Arial">
            <h2>🚨 RCB System Alert</h2>
            <p>זוהו בעיות במערכת:</p>
            <div style="background:#fff3cd;padding:15px;border-radius:8px">
                {issues_html}
            </div>
            <p>אנא בדוק את הלוגים:</p>
            <a href="https://console.cloud.google.com/logs?project=rpa-port-customs">Cloud Console Logs</a>
            <hr>
            <small>RCB Health Monitor</small>
        </div>'''
        
        helper_graph_send(access_token, rcb_email, master_email, 
                         "🚨 RCB Alert: System Issues Detected", body, None, None)
        print(f"📧 Alert sent to {master_email}")
        
    except Exception as e:
        print(f"❌ Failed to send alert: {e}")


# ============================================================
@https_fn.on_request(region="us-central1", memory=options.MemoryOption.GB_1, timeout_sec=540)
def monitor_self_heal(request):
    """DISABLED Session 13.1: Dead code (redefined below). Was self-healer v1."""
    print("⏸️ monitor_self_heal v1 DISABLED — dead code, redefined below")
    return https_fn.Response(json.dumps({"status": "disabled", "reason": "consolidated"}), content_type="application/json")



@https_fn.on_request(region="us-central1", memory=options.MemoryOption.GB_1, timeout_sec=540)
def monitor_self_heal(request):
    """DISABLED Session 13.1: Consolidated into rcb_check_email. Was self-healer v2."""
    print("⏸️ monitor_self_heal v2 DISABLED — consolidated into rcb_check_email")
    return https_fn.Response(json.dumps({"status": "disabled", "reason": "consolidated"}), content_type="application/json")



@https_fn.on_request(region="us-central1", memory=options.MemoryOption.GB_1, timeout_sec=540)
def monitor_fix_all(request):
    """DISABLED Session 13.1: Consolidated into rcb_check_email. Was fix-all monitor."""
    print("⏸️ monitor_fix_all DISABLED — consolidated into rcb_check_email")
    return https_fn.Response(json.dumps({"status": "disabled", "reason": "consolidated"}), content_type="application/json")



@scheduler_fn.on_schedule(
    schedule="every 5 minutes",
    region="us-central1",
    memory=options.MemoryOption.GB_1,
    timeout_sec=540
)
def monitor_fix_scheduled(event: scheduler_fn.ScheduledEvent) -> None:
    """DISABLED Session 13.1: Consolidated into rcb_check_email. Was scheduled fix monitor."""
    print("⏸️ monitor_fix_scheduled DISABLED — consolidated into rcb_check_email")
    return



@https_fn.on_request(memory=options.MemoryOption.GB_1, timeout_sec=120)
def test_pdf_ocr(req: https_fn.Request) -> https_fn.Response:
    """Test PDF extraction with OCR - call via browser or curl"""
    from lib.rcb_helpers import extract_text_from_pdf_bytes, helper_get_graph_token, helper_graph_messages, helper_graph_attachments
    import base64
    
    results = {"status": "starting", "steps": []}
    
    try:
        # Step 1: Get Graph token
        secrets = {
            'RCB_GRAPH_CLIENT_ID': get_secret('RCB_GRAPH_CLIENT_ID'),
            'RCB_GRAPH_CLIENT_SECRET': get_secret('RCB_GRAPH_CLIENT_SECRET'),
            'RCB_GRAPH_TENANT_ID': get_secret('RCB_GRAPH_TENANT_ID')
        }
        token = helper_get_graph_token(secrets)
        if not token:
            return https_fn.Response(json.dumps({"error": "Failed to get Graph token"}), status=500)
        results["steps"].append("✅ Got Graph token")
        
        # Step 2: Get recent emails
        user_email = "rcb@rpa-port.co.il"
        messages = helper_graph_messages(token, user_email, unread_only=False, max_results=5)
        results["steps"].append(f"✅ Found {len(messages)} recent emails")
        
        # Step 3: Find first email with PDF attachment
        pdf_found = False
        for msg in messages:
            msg_id = msg.get('id')
            subject = msg.get('subject', 'No subject')
            
            attachments = helper_graph_attachments(token, user_email, msg_id)
            pdf_attachments = [a for a in attachments if a.get('name', '').lower().endswith('.pdf')]
            
            if pdf_attachments:
                results["steps"].append(f"✅ Found email with PDF: {subject}")
                
                # Step 4: Extract text from first PDF
                att = pdf_attachments[0]
                pdf_name = att.get('name', 'unknown.pdf')
                content_bytes = att.get('contentBytes', '')
                
                if content_bytes:
                    pdf_bytes = base64.b64decode(content_bytes)
                    results["steps"].append(f"✅ Loaded PDF: {pdf_name} ({len(pdf_bytes)} bytes)")
                    
                    # Step 5: Run extraction with OCR
                    text = extract_text_from_pdf_bytes(pdf_bytes)
                    
                    results["pdf_name"] = pdf_name
                    results["pdf_size"] = len(pdf_bytes)
                    results["extracted_chars"] = len(text)
                    results["extracted_preview"] = text[:500] if text else "[No text extracted]"
                    results["status"] = "success" if len(text) > 50 else "extraction_failed"
                    pdf_found = True
                    break
        
        if not pdf_found:
            results["status"] = "no_pdf_found"
            results["steps"].append("⚠️ No PDF attachments found in recent emails")
        
    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)
    
    return https_fn.Response(
        json.dumps(results, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8"
    )
# Add this to main.py to test PDF generation

# ============================================================
# TEST: PDF REPORT GENERATION
# ============================================================
@https_fn.on_request(memory=options.MemoryOption.GB_1, timeout_sec=60)
def test_pdf_report(req: https_fn.Request) -> https_fn.Response:
    """Test PDF report generation - creates a sample classification PDF"""
    from lib.pdf_creator import create_classification_pdf
    import base64
    from datetime import datetime
    
    try:
        # Sample classification data
        test_data = {
            'sender_name': 'דורון טסט',
            'email_subject': 'בקשת סיווג - מייבש שיער',
            'classification_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'items': [
                {
                    'description': 'מייבש שיער חשמלי 2000W',
                    'hs_code': '8516.31.00.00',
                    'hs_description_he': 'מייבשי שיער',
                    'hs_description_en': 'Hair dryers',
                    'duty_rate': '12%',
                    'vat_rate': '17%',
                    'purchase_tax': 'לא חל',
                    'ministry_requirements': [
                        {'ministry': 'משרד הכלכלה', 'requirement': 'תקן ישראלי', 'status': 'נדרש'},
                        {'ministry': 'מכון התקנים', 'requirement': 'בדיקת בטיחות חשמל', 'status': 'נדרש'}
                    ],
                    'notes': 'יש לוודא תאימות מתח 220V',
                    'confidence': 'גבוהה (95%)'
                },
                {
                    'description': 'כבל USB-C לטעינה',
                    'hs_code': '8544.42.00.00',
                    'hs_description_he': 'מוליכים חשמליים מצוידים במחברים',
                    'hs_description_en': 'Electric conductors with connectors',
                    'duty_rate': '0%',
                    'vat_rate': '17%',
                    'purchase_tax': 'לא חל',
                    'ministry_requirements': [],
                    'confidence': 'גבוהה (92%)'
                }
            ]
        }
        
        # Create PDF
        pdf_path = create_classification_pdf(test_data, '/tmp/test_report.pdf')
        
        # Read PDF and return as base64 (for download)
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
        
        # Check if browser request (return PDF) or API request (return JSON)
        accept = req.headers.get('Accept', '')
        if 'text/html' in accept:
            # Return PDF directly for browser viewing
            return https_fn.Response(
                pdf_bytes,
                headers={
                    'Content-Type': 'application/pdf',
                    'Content-Disposition': 'inline; filename="classification_report.pdf"'
                }
            )
        else:
            # Return JSON with base64 PDF
            return https_fn.Response(
                json.dumps({
                    'status': 'success',
                    'message': 'PDF created successfully',
                    'pdf_size': len(pdf_bytes),
                    'pdf_base64': base64.b64encode(pdf_bytes).decode()
                }),
                content_type='application/json'
            )
            
    except Exception as e:
        return https_fn.Response(
            json.dumps({'status': 'error', 'error': str(e)}),
            status=500,
            content_type='application/json'
        )

# ============================================================
# SELF-TEST: RCB tests itself (Session 13)
# ============================================================
@https_fn.on_request(region="us-central1", memory=options.MemoryOption.GB_1, timeout_sec=300)
def rcb_self_test(req: https_fn.Request) -> https_fn.Response:
    """RCB Self-Test — sends test emails to itself, verifies, cleans up."""
    from lib.rcb_self_test import run_all_tests
    try:
        secrets = get_rcb_secrets_internal(get_secret)
        if not secrets:
            return https_fn.Response(json.dumps({"error": "No secrets"}), status=500)
        report = run_all_tests(
            db=get_db(), firestore_module=firestore,
            secrets=secrets, get_secret_func=get_secret,
        )
        status_code = 200 if report.get("all_passed") else 500
        return https_fn.Response(
            json.dumps(report, ensure_ascii=False, indent=2),
            status=status_code,
            headers={"Content-Type": "application/json"}
        )
    except Exception as e:
        return https_fn.Response(json.dumps({"error": str(e)}), status=500)
"""
═══════════════════════════════════════════════════════════════
  INSPECTOR AGENT — Add these to the END of main.py
  Session 14.01
═══════════════════════════════════════════════════════════════
"""

# --- Add this import near the top of main.py ---
# from lib.rcb_inspector import handle_inspector_http, handle_inspector_daily


# ============================================================
# INSPECTOR AGENT — Manual HTTP Trigger
# ============================================================
@https_fn.on_request(region="us-central1", memory=options.MemoryOption.GB_1, timeout_sec=300)
def rcb_inspector(req: https_fn.Request) -> https_fn.Response:
    """
    Full system inspection — manual trigger.
    
    Usage:
        curl https://us-central1-rpa-port-customs.cloudfunctions.net/rcb_inspector | python3 -m json.tool
    """
    print("🔍 RCB Inspector — Manual trigger")
    
    from lib.rcb_inspector import handle_inspector_http
    
    result = handle_inspector_http(req, get_db(), get_secret)
    
    return https_fn.Response(
        json.dumps(result, ensure_ascii=False, default=str, indent=2),
        status=200,
        headers={"Content-Type": "application/json"}
    )


# ============================================================
# INSPECTOR AGENT — Daily 15:00 Jerusalem Scheduler
# ============================================================
@scheduler_fn.on_schedule(
    schedule="every day 15:00",
    timezone=scheduler_fn.Timezone("Asia/Jerusalem"),
    region="us-central1",
    memory=options.MemoryOption.GB_1,
    timeout_sec=300,
)
def rcb_inspector_daily(event: scheduler_fn.ScheduledEvent) -> None:
    """
    Daily inspection + email report to doron@rpa-port.co.il
    Runs at 15:00 Jerusalem time every day.
    """
    print("🔍 RCB Inspector — Daily 15:00 scheduled run")
    
    from lib.rcb_inspector import handle_inspector_daily
    
    handle_inspector_daily(get_db(), get_secret)
    
    print("✅ RCB Inspector daily run complete")


# ============================================================
# NIGHTLY LEARNING — Build knowledge indexes automatically
# ============================================================
@scheduler_fn.on_schedule(
    schedule="every day 02:00",
    timezone=scheduler_fn.Timezone("Asia/Jerusalem"),
    region="us-central1",
    memory=options.MemoryOption.GB_1,
    timeout_sec=540,
)
def rcb_nightly_learn(event: scheduler_fn.ScheduledEvent) -> None:
    """
    Nightly learning pipeline — reads source data, builds indexes.
    Runs at 02:00 Jerusalem time every night.

    READS: tariff, knowledge_base, declarations, classification_knowledge,
           rcb_classifications, sellers, and 20+ other collections
    BUILDS: keyword_index, product_index, supplier_index, brain_index

    Source data is NEVER modified. Only derived indexes are written.
    No AI calls — pure text parsing. $0 cost.
    """
    print("NIGHTLY LEARN — Starting automated learning pipeline")

    from lib.nightly_learn import run_pipeline

    results = run_pipeline()

    success = all(r.get("status") == "success" for r in results.values())
    print(f"NIGHTLY LEARN — {'All steps succeeded' if success else 'Some steps failed'}")


# ============================================================
# TRACKER: Poll active deals via TaskYam (every 30 minutes)
# ============================================================
@scheduler_fn.on_schedule(
    schedule="every 30 minutes",
    region="us-central1",
    memory=options.MemoryOption.MB_512,
    timeout_sec=300,
)
def rcb_tracker_poll(event: scheduler_fn.ScheduledEvent) -> None:
    """Poll TaskYam for active deal updates. Sends status emails when steps change."""
    if not TRACKER_AVAILABLE:
        print("⏸️ Tracker not available — skipping poll")
        return

    print("📦 Tracker polling active deals...")
    try:
        secrets = get_rcb_secrets_internal(get_secret)
        access_token = helper_get_graph_token(secrets) if secrets else None
        rcb_email = secrets.get('RCB_EMAIL', 'rcb@rpa-port.co.il') if secrets else 'rcb@rpa-port.co.il'

        result = tracker_poll_active_deals(
            get_db(), firestore, get_secret,
            access_token=access_token, rcb_email=rcb_email
        )
        print(f"📦 Tracker poll complete: {result}")
    except Exception as e:
        print(f"❌ Tracker poll error: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# PUPIL: Batch learning cycle (every 6 hours)
# ============================================================
@scheduler_fn.on_schedule(
    schedule="every 6 hours",
    region="us-central1",
    memory=options.MemoryOption.GB_1,
    timeout_sec=540,
)
def rcb_pupil_learn(event: scheduler_fn.ScheduledEvent) -> None:
    """
    Pupil batch learning: verify observations, challenge brain, learn gaps.
    Phase B+C run here (not in email loop) to avoid slowing down email processing.
    """
    if not PUPIL_AVAILABLE:
        print("⏸️ Pupil not available — skipping learning cycle")
        return

    print("🎓 Pupil learning cycle starting...")
    try:
        from lib.pupil import (
            pupil_learn, pupil_verify_scan, pupil_challenge,
            pupil_send_reviews, pupil_find_corrections, pupil_audit
        )

        secrets = get_rcb_secrets_internal(get_secret)
        access_token = helper_get_graph_token(secrets) if secrets else None
        rcb_email = secrets.get('RCB_EMAIL', 'rcb@rpa-port.co.il') if secrets else 'rcb@rpa-port.co.il'

        # Phase B: Verify unverified observations
        try:
            pupil_verify_scan(get_db(), get_secret)
            print("  ✅ Pupil verify scan done")
        except Exception as e:
            print(f"  ⚠️ Pupil verify error: {e}")

        # Phase B: Learn from gaps (uses Gemini/Claude when needed)
        try:
            pupil_learn(get_db(), get_secret)
            print("  ✅ Pupil learning done")
        except Exception as e:
            print(f"  ⚠️ Pupil learn error: {e}")

        # Phase C: Find corrections in past classifications
        try:
            pupil_find_corrections(get_db(), access_token, rcb_email, get_secret)
            print("  ✅ Pupil corrections scan done")
        except Exception as e:
            print(f"  ⚠️ Pupil corrections error: {e}")

        # Phase C: Send review cases to doron@
        try:
            pupil_send_reviews(get_db(), access_token, rcb_email, get_secret)
            print("  ✅ Pupil reviews sent")
        except Exception as e:
            print(f"  ⚠️ Pupil reviews error: {e}")

        # Audit: Analyze patterns and summarize
        try:
            pupil_audit(get_db(), get_secret)
            print("  ✅ Pupil audit done")
        except Exception as e:
            print(f"  ⚠️ Pupil audit error: {e}")

        print("🎓 Pupil learning cycle complete")

    except Exception as e:
        print(f"❌ Pupil learning error: {e}")
        import traceback
        traceback.print_exc()
