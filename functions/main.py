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
import re
import imaplib
import email as email_lib
from email.header import decode_header
from datetime import datetime, timedelta


# Initialize Firebase
firebase_admin.initialize_app()
db = firestore.client()
bucket = storage.bucket()


# ============================================================
# FUNCTION 1: CHECK EMAIL (runs every 5 minutes)
# ============================================================
@scheduler_fn.on_schedule(schedule="every 5 minutes", memory=options.MemoryOption.MB_512)
def check_email_scheduled(event: scheduler_fn.ScheduledEvent) -> None:
    """Check airpaport@gmail.com for new emails every 5 minutes"""
    
    # Get email config
    try:
        config = db.collection("config").document("email").get().to_dict()
        email_addr = config["email"]
        email_pass = config["app_password"]
    except Exception as e:
        print(f"Email config error: {e}")
        return

    # Get already processed IDs
    processed_ids = set()
    for doc in db.collection("inbox").stream():
        processed_ids.add(doc.id)

    # Connect to Gmail
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_addr, email_pass)
        mail.select("inbox")
    except Exception as e:
        print(f"Gmail connection failed: {e}")
        return

    status, messages = mail.search(None, "ALL")
    email_ids = messages[0].split() if messages[0] else []
    new_count = 0

    for eid in email_ids:
        try:
            status, msg_data = mail.fetch(eid, "(RFC822)")
            msg = email_lib.message_from_bytes(msg_data[0][1])
            msg_id = msg.get("Message-ID", str(eid))
            safe_id = re.sub(r'[/\\\.\[\]\*~]', '_', str(msg_id))[:100]

            if safe_id in processed_ids:
                continue

            new_count += 1

            # Decode headers
            subject = decode_email_header(msg.get("Subject", ""))
            from_str = decode_email_header(msg.get("From", ""))
            date_str = msg.get("Date", "")

            # Extract body
            body_text = extract_body(msg)

            # Extract and process attachments
            attachments = extract_attachments(msg, body_text, subject)

            # Store email
            db.collection("inbox").document(safe_id).set({
                "from": from_str,
                "subject": subject,
                "date": date_str,
                "body": body_text[:10000],
                "message_id": msg_id,
                "attachment_count": len(attachments),
                "attachments": [{
                    "filename": a["filename"],
                    "size": a["size"],
                    "type": a["type"],
                    "doc_type": a["doc_type"],
                    "storage_path": a.get("storage_path", "")
                } for a in attachments],
                "status": "processed",
                "processed_at": firestore.SERVER_TIMESTAMP
            })

            # Classify each attachment (triggers Firestore listener)
            for att in attachments:
                classify_and_store(att, from_str, subject, date_str, body_text)

        except Exception as e:
            print(f"Error processing email {eid}: {e}")
            continue

    mail.logout()
    print(f"Email check complete: {new_count} new emails")


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
        seller_doc = db.collection("sellers").document(seller_id).get()
        if seller_doc.exists:
            seller_data = seller_doc.to_dict()
            known_hs = seller_data.get("known_hs_codes", [])
            if len(known_hs) == 1:
                suggested_hs = known_hs[0]
                confidence = 70
                print(f"Seller match: {seller} -> {suggested_hs}")

    # Check knowledge base for product match
    if product:
        kb_docs = db.collection("knowledge_base").where("category", "==", "hs_classifications").stream()
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
        kb_match = db.collection("knowledge_base").where("category", "==", "hs_classifications").stream()
        for doc in kb_match:
            kb = doc.to_dict()
            if kb.get("content", {}).get("hs", "").replace(".", "") == supplier_hs.replace(".", ""):
                suggested_hs = supplier_hs
                confidence = 80
                print(f"Supplier HS confirmed: {supplier_hs}")
                break

    # Update classification with suggestion
    if suggested_hs and confidence >= 60:
        db.collection("classifications").document(class_id).update({
            "suggested_hs": suggested_hs,
            "suggestion_confidence": confidence,
            "suggestion_source": "auto_knowledge_base",
            "status": "pending_review"
        })
        print(f"Auto-suggested {suggested_hs} (confidence: {confidence}%) for {class_id}")
    else:
        # Need Claude AI for complex classification
        db.collection("agent_tasks").add({
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
        seller_ref = db.collection("sellers").document(seller_id)
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
    hs_ref = db.collection("knowledge_base").document(hs_id)
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
    db.collection("learning_log").add({
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
    """Periodically check and fill knowledge gaps"""
    
    # Count by category
    categories = {}
    for doc in db.collection("knowledge_base").stream():
        cat = doc.to_dict().get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    total = sum(categories.values())
    print(f"Knowledge base: {total} documents, {len(categories)} categories")

    # Check for unprocessed documents in storage
    unprocessed = db.collection("inbox").where("status", "==", "new").limit(10).stream()
    for doc in unprocessed:
        print(f"Found unprocessed email: {doc.id}")
        # Trigger reprocessing

    # Check for stale enrichment sources
    sources = ["customs_guidance", "free_import", "standards", "food_safety", "fta_updates"]
    for source in sources:
        log_doc = db.collection("enrichment_log").document(source).get()
        if log_doc.exists:
            data = log_doc.to_dict()
            last_check = data.get("last_checked", "")
            if last_check:
                try:
                    last_dt = datetime.fromisoformat(str(last_check))
                    hours_since = (datetime.now() - last_dt).total_seconds() / 3600
                    if hours_since > 24:
                        print(f"Source {source} stale ({hours_since:.0f}h) - creating refresh task")
                        db.collection("agent_tasks").add({
                            "type": "enrichment_check",
                            "source": source,
                            "status": "pending",
                            "created_at": firestore.SERVER_TIMESTAMP
                        })
                except Exception:
                    pass
        else:
            print(f"Source {source} never checked - creating task")
            db.collection("agent_tasks").add({
                "type": "enrichment_check",
                "source": source,
                "status": "pending",
                "created_at": firestore.SERVER_TIMESTAMP
            })

    print("Enrichment check complete")


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
            "knowledge_count": len(list(db.collection("knowledge_base").stream())),
            "inbox_count": len(list(db.collection("inbox").stream())),
            "classifications_pending": len(list(db.collection("classifications").where("status", "==", "pending_classification").stream())),
            "classifications_total": len(list(db.collection("classifications").stream())),
            "sellers_count": len(list(db.collection("sellers").stream())),
            "pending_tasks": len(list(db.collection("pending_tasks").where("status", "==", "pending").stream())),
            "learning_events": len(list(db.collection("learning_log").stream()))
        }
        return https_fn.Response(json.dumps(stats), content_type="application/json")

    # Get classifications
    elif path == "classifications" and method == "GET":
        result = []
        for doc in db.collection("classifications").order_by("created_at", direction=firestore.Query.DESCENDING).limit(50).stream():
            d = doc.to_dict()
            d["id"] = doc.id
            d.pop("extracted_text", None)  # Don't send large text
            result.append(d)
        return https_fn.Response(json.dumps(result, default=str), content_type="application/json")

    # Correct a classification (triggers learning)
    elif path.startswith("classifications/") and method == "POST":
        class_id = path.split("/")[1]
        data = req.get_json()
        db.collection("classifications").document(class_id).update({
            "our_hs_code": data.get("hs_code"),
            "status": "corrected" if data.get("is_correction") else "confirmed",
            "corrected_by": data.get("user", "admin"),
            "corrected_at": firestore.SERVER_TIMESTAMP
        })
        return https_fn.Response(json.dumps({"ok": True}), content_type="application/json")

    # Get knowledge base
    elif path == "knowledge" and method == "GET":
        result = []
        for doc in db.collection("knowledge_base").stream():
            d = doc.to_dict()
            d["id"] = doc.id
            result.append(d)
        return https_fn.Response(json.dumps(result, default=str), content_type="application/json")

    # Get inbox
    elif path == "inbox" and method == "GET":
        result = []
        for doc in db.collection("inbox").order_by("processed_at", direction=firestore.Query.DESCENDING).limit(50).stream():
            d = doc.to_dict()
            d["id"] = doc.id
            d.pop("body", None)
            result.append(d)
        return https_fn.Response(json.dumps(result, default=str), content_type="application/json")

    # Get sellers
    elif path == "sellers" and method == "GET":
        result = []
        for doc in db.collection("sellers").stream():
            d = doc.to_dict()
            d["id"] = doc.id
            result.append(d)
        return https_fn.Response(json.dumps(result, default=str), content_type="application/json")

    # Get learning log
    elif path == "learning" and method == "GET":
        result = []
        for doc in db.collection("learning_log").order_by("learned_at", direction=firestore.Query.DESCENDING).limit(50).stream():
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
            blob = bucket.blob(storage_path)
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
            db.collection("classifications").document(class_id).set({
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
        db.collection("declarations").add({
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

        db.collection("regulatory_certificates").add({
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
        db.collection(collection_map[doc_type]).add({
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
import os
