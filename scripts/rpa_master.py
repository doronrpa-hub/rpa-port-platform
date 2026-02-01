#!/usr/bin/env python3
"""
RPA-PORT Master Agent
=====================
Single script that runs everything:
1. Checks airpaport@gmail.com for new emails
2. Classifies documents (invoices, declarations, certificates, etc.)
3. Enriches the knowledge base when idle
4. Processes pending tasks

Run: nohup python3 rpa_master.py >> logs/master.log 2>&1 &
"""

import firebase_admin
from firebase_admin import credentials, firestore, storage
import imaplib
import email as email_lib
from email.header import decode_header
import os
import re
import json
import time
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict

# ============================================================
# FIREBASE INIT
# ============================================================
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-credentials.json")
    firebase_admin.initialize_app(cred, {
        'storageBucket': 'rpa-port-customs.firebasestorage.app'
    })

db = firestore.client()
bucket = storage.bucket()

# Get Gmail credentials from Firebase config
try:
    config = db.collection("config").document("email").get().to_dict()
    EMAIL_ADDR = config["email"]
    EMAIL_PASS = config["app_password"]
    print(f"✅ Email config loaded: {EMAIL_ADDR}")
except Exception as e:
    print(f"⚠️ Could not load email config from Firebase: {e}")
    print("   Make sure config/email document exists with 'email' and 'app_password' fields")
    EMAIL_ADDR = None
    EMAIL_PASS = None


# ============================================================
# PART 1: EMAIL CHECKER + CLASSIFIER
# ============================================================

def check_emails():
    """Check airpaport@gmail.com for new emails, classify attachments"""
    if not EMAIL_ADDR or not EMAIL_PASS:
        print("⚠️ Email not configured - skipping inbox check")
        return 0

    print(f"\n📧 Checking inbox: {EMAIL_ADDR}...")
    
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_ADDR, EMAIL_PASS)
        mail.select("inbox")
    except Exception as e:
        print(f"❌ Gmail connection failed: {e}")
        return 0

    # Get already-processed message IDs from Firebase
    processed_ids = set()
    try:
        docs = db.collection("inbox").stream()
        for doc in docs:
            processed_ids.add(doc.id)
    except:
        pass

    # Search for all emails
    status, messages = mail.search(None, "ALL")
    email_ids = messages[0].split() if messages[0] else []
    print(f"  📬 Found {len(email_ids)} emails in inbox, {len(processed_ids)} already processed")

    new_count = 0

    for eid in email_ids:
        try:
            status, msg_data = mail.fetch(eid, "(RFC822)")
            msg = email_lib.message_from_bytes(msg_data[0][1])

            # Get message ID
            msg_id = msg.get("Message-ID", str(eid))
            safe_id = re.sub(r'[/\\\.\[\]\*~]', '_', str(msg_id))[:100]

            # Skip if already processed
            if safe_id in processed_ids:
                continue

            new_count += 1

            # Decode subject
            subject = ""
            raw_subject = msg.get("Subject", "")
            if raw_subject:
                decoded = decode_header(raw_subject)
                subject = " ".join([
                    part.decode(enc or 'utf-8') if isinstance(part, bytes) else str(part)
                    for part, enc in decoded
                ])

            # Decode from
            from_raw = msg.get("From", "")
            decoded_from = decode_header(from_raw)
            from_str = " ".join([
                part.decode(enc or 'utf-8') if isinstance(part, bytes) else str(part)
                for part, enc in decoded_from
            ])

            date_str = msg.get("Date", "")

            print(f"\n  {'='*50}")
            print(f"  📧 NEW: From: {from_str[:60]}")
            print(f"  📧 Subject: {subject[:80]}")
            print(f"  📧 Date: {date_str}")

            # Extract body
            body_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            try:
                                body_text += payload.decode(charset, errors='replace')
                            except:
                                body_text += payload.decode('utf-8', errors='replace')
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body_text = payload.decode('utf-8', errors='replace')

            # Extract attachments
            attachments = []
            if msg.is_multipart():
                for part in msg.walk():
                    content_disp = str(part.get("Content-Disposition", ""))
                    if "attachment" in content_disp or part.get_filename():
                        filename = part.get_filename()
                        if filename:
                            decoded_fn = decode_header(filename)
                            filename = " ".join([
                                p.decode(e or 'utf-8') if isinstance(p, bytes) else str(p)
                                for p, e in decoded_fn
                            ])

                            file_data = part.get_payload(decode=True)
                            if file_data:
                                safe_name = re.sub(r'[^\w\-_\. ]', '_', filename)
                                local_path = f"/tmp/{safe_name}"
                                with open(local_path, 'wb') as f:
                                    f.write(file_data)

                                file_size = len(file_data)
                                file_ext = os.path.splitext(filename)[1].lower()

                                print(f"    📎 Attachment: {filename} ({file_size:,} bytes)")

                                # Detect document type
                                doc_type = detect_document_type(filename, body_text, subject)
                                print(f"       🔍 Detected type: {doc_type}")

                                # Upload to Firebase Storage
                                storage_path = f"inbox/{datetime.now().strftime('%Y%m%d')}_{safe_name}"
                                try:
                                    blob = bucket.blob(storage_path)
                                    blob.upload_from_filename(local_path)
                                    blob.make_public()
                                    download_url = blob.public_url
                                    print(f"       ☁️ Uploaded to Firebase Storage")
                                except Exception as e:
                                    print(f"       ⚠️ Upload failed: {e}")
                                    download_url = ""

                                # Extract text from PDF
                                extracted_text = ""
                                if file_ext == '.pdf':
                                    extracted_text = extract_pdf_text(local_path)
                                    if extracted_text:
                                        print(f"       📄 Extracted {len(extracted_text):,} chars from PDF")

                                attachments.append({
                                    "filename": filename,
                                    "size": file_size,
                                    "type": file_ext,
                                    "doc_type": doc_type,
                                    "storage_path": storage_path,
                                    "download_url": download_url,
                                    "local_path": local_path,
                                    "extracted_text": extracted_text[:50000] if extracted_text else ""
                                })

            # Store email in Firebase
            email_doc = {
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
                    "storage_path": a["storage_path"],
                    "download_url": a.get("download_url", "")
                } for a in attachments],
                "status": "processed",
                "processed_at": firestore.SERVER_TIMESTAMP,
                "received_at": date_str
            }

            db.collection("inbox").document(safe_id).set(email_doc)
            print(f"  ✅ Stored in Firebase inbox/{safe_id}")

            # Classify each attachment
            for att in attachments:
                classify_document(att, from_str, subject, date_str, body_text)

        except Exception as e:
            print(f"  ❌ Error processing email {eid}: {e}")
            continue

    mail.logout()
    print(f"\n📧 Email check complete: {new_count} new emails processed")
    return new_count


def detect_document_type(filename, body="", subject=""):
    """Detect what type of document this is"""
    fn = filename.lower()
    body_lower = (body + " " + subject).lower()

    # Commercial Invoice
    if any(kw in fn for kw in ['invoice', 'inv_', 'inv-', 'חשבון', 'facture', 'rechnung', 'faktura']):
        return "commercial_invoice"
    if any(kw in fn for kw in ['commercial', 'commerciale']):
        return "commercial_invoice"

    # Packing List
    if any(kw in fn for kw in ['packing', 'pl ', 'pl_', 'pl-', 'רשימת אריזה', 'packing list', 'packing_list']):
        return "packing_list"

    # Customs Declaration (World Gate / רשימון)
    if any(kw in fn for kw in ['wg_', 'imp_dec', 'exp_dec', 'רשימון', 'declaration', 'customs_dec', 'rishimon']):
        return "customs_declaration"

    # EMC / Safety / RF Certificates (SII, MoC, etc.)
    if any(kw in fn for kw in ['cert_emc', 'cert_rf', 'cert_safety', '_emc_', '_rf_', '_safety_',
                                'emc_safety', 'emc_cert', 'rf_cert', 'safety_cert']):
        return "regulatory_certificate"
    if any(kw in fn for kw in ['sii', 'moc_', '_moc', 'תקן', 'תו_תקן', 'si_', 'iso_']):
        return "regulatory_certificate"
    if any(kw in fn for kw in ['polygon', 'intertek', 'sgs', 'tuv', 'ul_', 'ce_mark', 'fcc_']):
        return "regulatory_certificate"

    # Certificate of Origin (EUR.1, Form A, etc.)
    if any(kw in fn for kw in ['eur.1', 'eur1', 'origin', 'תעודת מקור', 'co_', 'coo_',
                                'form_a', 'forma', 'preferential']):
        return "certificate_of_origin"
    if 'certificate' in fn and 'origin' in fn:
        return "certificate_of_origin"

    # Bill of Lading / Airway Bill
    if any(kw in fn for kw in ['b/l', 'bl_', 'bl-', 'bill_of_lading', 'שטר מטען', 'awb',
                                'airway', 'air_waybill', 'house_bl', 'master_bl', 'mbl', 'hbl']):
        return "bill_of_lading"

    # Insurance
    if any(kw in fn for kw in ['insurance', 'ביטוח', 'policy', 'poliza']):
        return "insurance"

    # Import License / Permit
    if any(kw in fn for kw in ['license', 'licence', 'permit', 'רישיון', 'היתר', 'אישור יבוא',
                                'import_permit', 'import_license']):
        return "import_permit"

    # Lab Test / Analysis Report
    if any(kw in fn for kw in ['lab_', 'test_', 'analysis', 'report_', 'בדיקה', 'מעבדה',
                                'test_report', 'lab_report', 'coa_', 'certificate_of_analysis']):
        return "lab_report"

    # Proforma Invoice
    if any(kw in fn for kw in ['proforma', 'pro_forma', 'pro-forma', 'פרופורמה']):
        return "proforma_invoice"

    # Scanned documents (doc + numbers pattern = likely scanned declaration or customs doc)
    if re.match(r'^doc\d{10,}', fn):
        return "scanned_document"

    # Body text clues
    if 'invoice' in body_lower or 'חשבונית' in body_lower:
        if any(fn.endswith(ext) for ext in ['.pdf', '.xlsx', '.xls']):
            return "possible_invoice"
    if 'רשימון' in body_lower or 'declaration' in body_lower:
        return "possible_declaration"
    if any(kw in body_lower for kw in ['cert', 'תעודה', 'אישור', 'תקן']):
        if any(fn.endswith(ext) for ext in ['.pdf']):
            return "possible_certificate"

    return "unknown"


def extract_pdf_text(filepath):
    """Extract text from PDF"""
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages[:30]:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception:
        pass

    try:
        import PyPDF2
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages[:30]:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception:
        pass

    return text


def classify_document(att, from_str, subject, date_str, body_text):
    """Classify the document and take appropriate action"""
    doc_type = att["doc_type"]
    filename = att["filename"]
    text = att.get("extracted_text", "")

    print(f"\n    🧠 Classifying: {filename} (type: {doc_type})")

    if doc_type in ("commercial_invoice", "possible_invoice"):
        classify_invoice(att, from_str, subject, date_str, text)
    elif doc_type == "proforma_invoice":
        classify_invoice(att, from_str, subject, date_str, text)
    elif doc_type == "customs_declaration":
        process_declaration(att, from_str, subject, date_str, text)
    elif doc_type == "certificate_of_origin":
        process_origin_cert(att, from_str, subject, date_str, text)
    elif doc_type == "packing_list":
        process_packing_list(att, from_str, subject, date_str, text)
    elif doc_type == "bill_of_lading":
        process_bol(att, from_str, subject, date_str, text)
    elif doc_type == "regulatory_certificate":
        process_regulatory_cert(att, from_str, subject, date_str, text)
    elif doc_type == "import_permit":
        process_import_permit(att, from_str, subject, date_str, text)
    elif doc_type == "lab_report":
        process_lab_report(att, from_str, subject, date_str, text)
    elif doc_type == "scanned_document":
        process_scanned_doc(att, from_str, subject, date_str, text)
    elif doc_type == "possible_certificate":
        process_regulatory_cert(att, from_str, subject, date_str, text)
    elif doc_type == "unknown":
        process_unknown(att, from_str, subject, date_str, text)
    else:
        print(f"       ℹ️ Stored as-is (type: {doc_type})")


def extract_invoice_fields(text):
    """Extract structured data from invoice text"""
    if not text or len(text) < 50:
        return None

    data = {}
    text_upper = text.upper()

    for pattern in [r'(?:SELLER|EXPORTER|SHIPPER|FROM)[:\s]*(.+)', r'(?:מוכר|יצואן|שולח)[:\s]*(.+)']:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            data["seller"] = m.group(1).strip()[:100]
            break

    for pattern in [r'(?:BUYER|CONSIGNEE|TO|IMPORTER)[:\s]*(.+)', r'(?:קונה|יבואן|נמען)[:\s]*(.+)']:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            data["buyer"] = m.group(1).strip()[:100]
            break

    for pattern in [r'(?:HS|H\.S\.|TARIFF|HTS|CN)[:\s#]*(\d{4}[\.\s]?\d{2}[\.\s]?\d{0,4})', r'(\d{4}\.\d{2}\.\d{2,4})']:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            data["supplier_hs"] = m.group(1).strip()
            break

    for pattern in [r'(?:TOTAL|GRAND TOTAL|NET TOTAL|AMOUNT)[:\s]*([A-Z]{3})\s*([\d,\.]+)', r'([A-Z]{3})\s*([\d,\.]+)\s*(?:TOTAL|CIF|FOB)']:
        m = re.search(pattern, text_upper)
        if m:
            data["currency"] = m.group(1)
            data["total_value"] = m.group(2).replace(",", "")
            break

    for term in ['EXW', 'FCA', 'FAS', 'FOB', 'CFR', 'CIF', 'CPT', 'CIP', 'DAP', 'DPU', 'DDP']:
        if term in text_upper:
            data["incoterms"] = term
            break

    for pattern in [r'(?:ORIGIN|COUNTRY OF ORIGIN|MADE IN)[:\s]*([A-Z][a-zA-Z\s]+)', r'(?:מקור|ארץ מקור)[:\s]*(.+)']:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            data["origin"] = m.group(1).strip()[:50]
            break

    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if len(line) > 20 and not any(kw in line.upper() for kw in ['INVOICE', 'DATE', 'SELLER', 'BUYER', 'TOTAL', 'ADDRESS']):
            if re.search(r'[A-Za-z]{3,}', line):
                data["product"] = line[:200]
                break

    for pattern in [r'(\d+)\s*(?:EA|PCS|PCS\.|PIECES|UNITS|KG|KGS|SETS?)', r'(?:QTY|QUANTITY)[:\s]*(\d+)']:
        m = re.search(pattern, text_upper)
        if m:
            data["quantity"] = m.group(1)
            break

    return data if data else None


def classify_invoice(att, from_str, subject, date_str, text):
    """Full invoice classification"""
    print(f"       📄 Processing invoice...")
    invoice_data = extract_invoice_fields(text)

    if invoice_data:
        print(f"       ✅ Extracted: {invoice_data.get('seller', 'Unknown')} → {invoice_data.get('buyer', 'Unknown')}")
        print(f"       📦 Product: {invoice_data.get('product', 'Unknown')[:60]}")
        print(f"       🏷️ Supplier HS: {invoice_data.get('supplier_hs', 'Not found')}")

        class_id = f"class_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        classification = {
            "date": date_str,
            "seller": invoice_data.get("seller", ""),
            "buyer": invoice_data.get("buyer", ""),
            "product_description": invoice_data.get("product", ""),
            "quantity": invoice_data.get("quantity", ""),
            "total_value": invoice_data.get("total_value", ""),
            "currency": invoice_data.get("currency", ""),
            "incoterms": invoice_data.get("incoterms", ""),
            "origin": invoice_data.get("origin", ""),
            "supplier_hs": invoice_data.get("supplier_hs", ""),
            "our_hs_code": "PENDING_CLASSIFICATION",
            "status": "pending_classification",
            "source_email": from_str,
            "source_subject": subject,
            "attachment_path": att.get("storage_path", ""),
            "extracted_text": text[:10000],
            "created_at": firestore.SERVER_TIMESTAMP
        }
        db.collection("classifications").document(class_id).set(classification)
        print(f"       ✅ Saved as {class_id} - PENDING CLASSIFICATION")

        # Create task for AI classification
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_classify"
        db.collection("pending_tasks").document(task_id).set({
            "type": "ai_classification",
            "description": f"סווג חשבונית מ-{invoice_data.get('seller', 'Unknown')}",
            "classification_id": class_id,
            "status": "pending",
            "priority": "high",
            "assigned_to": "ai",
            "created": datetime.now().isoformat(),
            "trigger": "email_received"
        })

        # Update seller database
        seller_name = invoice_data.get("seller", "").strip()
        if seller_name:
            seller_id = re.sub(r'[^a-zA-Z0-9]', '_', seller_name.lower())[:50]
            seller_ref = db.collection("sellers").document(seller_id)
            try:
                seller_doc = seller_ref.get()
                if seller_doc.exists:
                    existing = seller_doc.to_dict()
                    invoices = existing.get("invoices", [])
                    invoices.append(class_id)
                    seller_ref.update({"invoices": invoices, "last_invoice": date_str})
                else:
                    seller_ref.set({
                        "name": seller_name,
                        "country": invoice_data.get("origin", ""),
                        "products": [invoice_data.get("product", "")],
                        "invoices": [class_id],
                        "first_seen": date_str,
                        "last_invoice": date_str
                    })
                print(f"       🏭 Updated seller: {seller_name}")
            except Exception as e:
                print(f"       ⚠️ Seller update failed: {e}")
    else:
        print(f"       ⚠️ Could not extract invoice fields - storing for manual review")
        db.collection("pending_tasks").document(f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_manual").set({
            "type": "manual_review",
            "description": f"חשבונית לא זוהתה - {att['filename']}",
            "reason": "Could not extract invoice fields automatically",
            "source_email": from_str,
            "attachment_path": att.get("storage_path", ""),
            "status": "pending",
            "priority": "medium",
            "assigned_to": "user",
            "created": datetime.now().isoformat()
        })


def process_declaration(att, from_str, subject, date_str, text):
    """Process customs declaration - match with existing classification"""
    print(f"       📋 Processing customs declaration...")
    hs_match = re.search(r'(\d{4}[\.\s]?\d{2}[\.\s]?\d{2,4})', text or "")
    hs_from_dec = hs_match.group(1) if hs_match else None

    if hs_from_dec:
        print(f"       🏷️ Declaration HS: {hs_from_dec}")

    dec_id = f"dec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    db.collection("declarations").document(dec_id).set({
        "filename": att["filename"],
        "from_email": from_str,
        "date": date_str,
        "hs_code": hs_from_dec,
        "extracted_text": text[:10000] if text else "",
        "attachment_path": att.get("storage_path", ""),
        "matched_classification": None,
        "created_at": firestore.SERVER_TIMESTAMP
    })

    # Auto-match with pending classifications
    try:
        pending = db.collection("classifications").where("status", "==", "pending_wg_comparison").get()
        for doc in pending:
            cls = doc.to_dict()
            if hs_from_dec and cls.get("our_hs_code"):
                if hs_from_dec.replace(".", "") == cls["our_hs_code"].replace(".", ""):
                    print(f"       ✅ MATCH! Declaration HS matches our classification")
                    db.collection("classifications").document(doc.id).update({
                        "status": "confirmed_by_declaration",
                        "wg_hs_code": hs_from_dec,
                        "wg_declaration_id": dec_id,
                        "confirmed_at": firestore.SERVER_TIMESTAMP
                    })
                else:
                    print(f"       ⚠️ DIFFERENT! Our: {cls['our_hs_code']} vs WG: {hs_from_dec}")
                    db.collection("classifications").document(doc.id).update({
                        "status": "classification_difference",
                        "wg_hs_code": hs_from_dec,
                        "wg_declaration_id": dec_id,
                        "difference_reason": f"Our HS: {cls['our_hs_code']} vs Declaration HS: {hs_from_dec}"
                    })
                    # Create learning task
                    db.collection("pending_tasks").document(f"learn_{dec_id}").set({
                        "type": "ai_learning",
                        "description": f"למד מהבדל סיווג: {cls['our_hs_code']} vs {hs_from_dec}",
                        "classification_id": doc.id,
                        "declaration_id": dec_id,
                        "status": "pending",
                        "assigned_to": "ai",
                        "created": datetime.now().isoformat()
                    })
    except Exception as e:
        print(f"       ⚠️ Auto-match failed: {e}")

    print(f"       ✅ Declaration stored: {dec_id}")


def process_origin_cert(att, from_str, subject, date_str, text):
    """Process certificate of origin"""
    print(f"       🌍 Processing certificate of origin...")
    db.collection("origin_certificates").add({
        "filename": att["filename"],
        "from_email": from_str,
        "date": date_str,
        "extracted_text": text[:10000] if text else "",
        "attachment_path": att.get("storage_path", ""),
        "created_at": firestore.SERVER_TIMESTAMP
    })
    print(f"       ✅ Origin certificate stored")


def process_packing_list(att, from_str, subject, date_str, text):
    """Process packing list"""
    print(f"       📦 Processing packing list...")
    db.collection("packing_lists").add({
        "filename": att["filename"],
        "from_email": from_str,
        "date": date_str,
        "extracted_text": text[:10000] if text else "",
        "attachment_path": att.get("storage_path", ""),
        "created_at": firestore.SERVER_TIMESTAMP
    })
    print(f"       ✅ Packing list stored")


def process_bol(att, from_str, subject, date_str, text):
    """Process bill of lading"""
    print(f"       🚢 Processing bill of lading...")
    db.collection("bills_of_lading").add({
        "filename": att["filename"],
        "from_email": from_str,
        "date": date_str,
        "extracted_text": text[:10000] if text else "",
        "attachment_path": att.get("storage_path", ""),
        "created_at": firestore.SERVER_TIMESTAMP
    })
    print(f"       ✅ Bill of lading stored")


def process_unknown(att, from_str, subject, date_str, text):
    """Process unknown document"""
    print(f"       ❓ Unknown document: {att['filename']}")
    clues = []
    if text:
        text_lower = text.lower()
        if any(kw in text_lower for kw in ['invoice', 'total', 'qty', 'price', 'amount']):
            clues.append("possible_invoice")
        if any(kw in text_lower for kw in ['packing', 'weight', 'carton', 'dimension']):
            clues.append("possible_packing_list")
        if any(kw in text_lower for kw in ['origin', 'certificate', 'eur.1', 'preferential']):
            clues.append("possible_origin_cert")
        if any(kw in text_lower for kw in ['customs', 'declaration', 'duty', 'tariff', 'hs code']):
            clues.append("possible_declaration")
        if any(kw in text_lower for kw in ['bill of lading', 'consignee', 'vessel', 'port of loading']):
            clues.append("possible_bol")
        if any(kw in text_lower for kw in ['רשימון', 'מכס', 'סיווג', 'מע"מ']):
            clues.append("possible_hebrew_customs")

    print(f"       🔍 Clues found: {clues if clues else 'none'}")

    db.collection("unclassified_documents").add({
        "filename": att["filename"],
        "from_email": from_str,
        "subject": subject,
        "date": date_str,
        "extracted_text": text[:10000] if text else "",
        "attachment_path": att.get("storage_path", ""),
        "content_clues": clues,
        "needs_review": True,
        "created_at": firestore.SERVER_TIMESTAMP
    })

    db.collection("pending_tasks").document(f"review_{datetime.now().strftime('%Y%m%d_%H%M%S')}").set({
        "type": "manual_review",
        "description": f"מסמך לא מזוהה: {att['filename']}",
        "reason": f"Content clues: {clues}" if clues else "No recognizable content",
        "from_email": from_str,
        "attachment_path": att.get("storage_path", ""),
        "status": "pending",
        "priority": "medium",
        "assigned_to": "user",
        "created": datetime.now().isoformat()
    })
    print(f"       📌 Created review task for manual classification")


def process_regulatory_cert(att, from_str, subject, date_str, text):
    """Process regulatory certificates (EMC, RF, Safety, SII, MoC)"""
    filename = att["filename"]
    fn_lower = filename.lower()
    print(f"       📜 Processing regulatory certificate...")

    # Detect certificate sub-type
    cert_type = "general"
    if any(kw in fn_lower for kw in ['emc', 'electromagnetic']):
        cert_type = "emc"
    elif any(kw in fn_lower for kw in ['rf_', '_rf', 'radio', 'moc', 'תקשורת']):
        cert_type = "rf_radio"
    elif any(kw in fn_lower for kw in ['safety', 'בטיחות']):
        cert_type = "safety"
    elif any(kw in fn_lower for kw in ['sii', 'מכון_התקנים', 'si_']):
        cert_type = "sii_standard"

    # Detect issuing body
    issuer = "unknown"
    if 'sii' in fn_lower or 'מכון התקנים' in (text or '').lower():
        issuer = "SII - Standards Institution of Israel"
    elif 'moc' in fn_lower or 'ministry of communication' in (text or '').lower():
        issuer = "MoC - Ministry of Communications"
    elif 'polygon' in fn_lower:
        issuer = "Polygon Trading Corp (agent)"
    elif 'intertek' in fn_lower:
        issuer = "Intertek"
    elif 'sgs' in fn_lower:
        issuer = "SGS"
    elif 'tuv' in fn_lower:
        issuer = "TÜV"

    # Try to extract model/product from filename
    model = ""
    model_match = re.search(r'([A-Z]{2,5}[-_]\d{3,}[-_]?\w*)', filename, re.IGNORECASE)
    if model_match:
        model = model_match.group(1)

    # Try to extract expiry date
    expiry = ""
    expiry_match = re.search(r'[Ee]xpires?[_\s-]*(\d{1,2}[-_][A-Za-z]{3}[-_]\d{2,4})', filename)
    if expiry_match:
        expiry = expiry_match.group(1)
    if not expiry and text:
        expiry_match = re.search(r'(?:valid until|expires?|תוקף עד)[:\s]*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})', text, re.IGNORECASE)
        if expiry_match:
            expiry = expiry_match.group(1)

    print(f"       📜 Type: {cert_type} | Issuer: {issuer} | Model: {model or 'N/A'} | Expires: {expiry or 'N/A'}")

    cert_id = f"cert_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    db.collection("regulatory_certificates").document(cert_id).set({
        "filename": filename,
        "cert_type": cert_type,
        "issuer": issuer,
        "model_number": model,
        "expiry_date": expiry,
        "from_email": from_str,
        "date": date_str,
        "extracted_text": text[:10000] if text else "",
        "attachment_path": att.get("storage_path", ""),
        "status": "active",
        "created_at": firestore.SERVER_TIMESTAMP
    })

    # If we have a model number, link to product database
    if model:
        product_id = re.sub(r'[^a-zA-Z0-9]', '_', model.lower())
        product_ref = db.collection("products").document(product_id)
        try:
            product_doc = product_ref.get()
            if product_doc.exists:
                existing = product_doc.to_dict()
                certs = existing.get("certificates", [])
                certs.append({"cert_id": cert_id, "type": cert_type, "issuer": issuer, "expiry": expiry})
                product_ref.update({"certificates": certs, "last_updated": datetime.now().isoformat()})
            else:
                product_ref.set({
                    "model": model,
                    "certificates": [{"cert_id": cert_id, "type": cert_type, "issuer": issuer, "expiry": expiry}],
                    "first_seen": date_str,
                    "last_updated": datetime.now().isoformat()
                })
            print(f"       🔗 Linked to product: {model}")
        except Exception as e:
            print(f"       ⚠️ Product link failed: {e}")

    # Alert if certificate is expiring soon
    if expiry:
        try:
            for fmt in ['%d-%b-%y', '%d-%b-%Y', '%d/%m/%Y', '%d.%m.%Y', '%d-%m-%Y']:
                try:
                    exp_date = datetime.strptime(expiry, fmt)
                    days_left = (exp_date - datetime.now()).days
                    if 0 < days_left < 60:
                        print(f"       ⚠️ EXPIRING SOON: {days_left} days left!")
                        db.collection("pending_tasks").document(f"expiry_{cert_id}").set({
                            "type": "certificate_expiry",
                            "description": f"תעודת {cert_type} עבור {model} פגה בעוד {days_left} ימים",
                            "cert_id": cert_id,
                            "model": model,
                            "expiry_date": expiry,
                            "days_left": days_left,
                            "status": "pending",
                            "priority": "high",
                            "assigned_to": "user",
                            "created": datetime.now().isoformat()
                        })
                    break
                except ValueError:
                    continue
        except Exception:
            pass

    print(f"       ✅ Certificate stored: {cert_id}")


def process_import_permit(att, from_str, subject, date_str, text):
    """Process import permit / license"""
    print(f"       📋 Processing import permit...")

    # Try to detect issuing ministry
    ministry = "unknown"
    text_lower = (text or "").lower() + att["filename"].lower()
    if any(kw in text_lower for kw in ['health', 'בריאות']):
        ministry = "Ministry of Health"
    elif any(kw in text_lower for kw in ['economy', 'כלכלה', 'תמ"ת']):
        ministry = "Ministry of Economy"
    elif any(kw in text_lower for kw in ['agriculture', 'חקלאות']):
        ministry = "Ministry of Agriculture"
    elif any(kw in text_lower for kw in ['communication', 'תקשורת']):
        ministry = "Ministry of Communications"
    elif any(kw in text_lower for kw in ['defense', 'ביטחון']):
        ministry = "Ministry of Defense"

    permit_id = f"permit_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    db.collection("import_permits").document(permit_id).set({
        "filename": att["filename"],
        "ministry": ministry,
        "from_email": from_str,
        "date": date_str,
        "extracted_text": text[:10000] if text else "",
        "attachment_path": att.get("storage_path", ""),
        "status": "active",
        "created_at": firestore.SERVER_TIMESTAMP
    })
    print(f"       ✅ Import permit stored: {permit_id} (Ministry: {ministry})")


def process_lab_report(att, from_str, subject, date_str, text):
    """Process lab test / analysis report"""
    print(f"       🔬 Processing lab report...")

    report_id = f"lab_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    db.collection("lab_reports").document(report_id).set({
        "filename": att["filename"],
        "from_email": from_str,
        "date": date_str,
        "extracted_text": text[:10000] if text else "",
        "attachment_path": att.get("storage_path", ""),
        "status": "received",
        "created_at": firestore.SERVER_TIMESTAMP
    })
    print(f"       ✅ Lab report stored: {report_id}")


def process_scanned_doc(att, from_str, subject, date_str, text):
    """Process scanned document (likely customs declaration or official doc)"""
    filename = att["filename"]
    print(f"       📃 Processing scanned document: {filename}")

    # Analyze text content to guess type
    actual_type = "unknown_scanned"
    if text:
        text_lower = text.lower()
        if any(kw in text_lower for kw in ['רשימון', 'customs', 'declaration', 'מכס', 'import entry']):
            actual_type = "scanned_declaration"
        elif any(kw in text_lower for kw in ['invoice', 'חשבונית', 'total', 'amount']):
            actual_type = "scanned_invoice"
        elif any(kw in text_lower for kw in ['certificate', 'תעודה', 'אישור', 'תקן']):
            actual_type = "scanned_certificate"
        elif any(kw in text_lower for kw in ['רישיון', 'permit', 'license', 'היתר']):
            actual_type = "scanned_permit"

    print(f"       📃 Detected as: {actual_type}")

    doc_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    db.collection("scanned_documents").document(doc_id).set({
        "filename": filename,
        "detected_type": actual_type,
        "from_email": from_str,
        "date": date_str,
        "extracted_text": text[:10000] if text else "",
        "attachment_path": att.get("storage_path", ""),
        "needs_review": True,
        "created_at": firestore.SERVER_TIMESTAMP
    })

    # If we identified it, route to the right handler
    if actual_type == "scanned_declaration":
        process_declaration(att, from_str, subject, date_str, text)
    elif actual_type == "scanned_invoice":
        classify_invoice(att, from_str, subject, date_str, text)
    elif actual_type == "scanned_certificate":
        process_regulatory_cert(att, from_str, subject, date_str, text)
    else:
        # Create review task
        db.collection("pending_tasks").document(f"review_scan_{doc_id}").set({
            "type": "manual_review",
            "description": f"מסמך סרוק לא מזוהה: {filename}",
            "scan_id": doc_id,
            "status": "pending",
            "priority": "medium",
            "assigned_to": "user",
            "created": datetime.now().isoformat()
        })

    print(f"       ✅ Scanned document stored: {doc_id}")


# ============================================================
# PART 2: ENRICHMENT ENGINE
# ============================================================

ENRICHMENT_SOURCES = {
    "customs_guidance": {
        "name": "Israeli Customs Guidance Center",
        "check_interval_hours": 24,
        "description": "Check for new customs classification guidance"
    },
    "free_import_app": {
        "name": "Free Import Order Digital App",
        "check_interval_hours": 48,
        "description": "Check for updates to free import order requirements"
    },
    "standards_institute": {
        "name": "Israel Standards Institute",
        "check_interval_hours": 72,
        "description": "Check for new mandatory standards"
    },
    "food_service": {
        "name": "Food Service Import Requirements",
        "check_interval_hours": 72,
        "description": "Check for updated food import requirements"
    },
    "fta_updates": {
        "name": "Free Trade Agreement Updates",
        "check_interval_hours": 168,
        "description": "Check for FTA schedule changes"
    }
}


def is_system_idle():
    """Check if there are pending tasks"""
    try:
        pending = db.collection('agent_tasks').where('status', '==', 'pending').limit(1).stream()
        for _ in pending:
            return False
    except:
        pass
    return True


def run_enrichment_cycle(cycle_num):
    """Run one enrichment cycle when system is idle"""
    print(f"\n🧠 Enrichment Cycle #{cycle_num}")

    if not is_system_idle():
        print("  ⏸️ System busy - skipping enrichment")
        return

    print("  💤 System idle - enriching knowledge...")

    # Check which sources need updating
    for source_key, source in ENRICHMENT_SOURCES.items():
        try:
            doc = db.collection('enrichment_log').document(source_key).get()
            if doc.exists:
                last_check = doc.to_dict().get('last_checked')
                if last_check:
                    if hasattr(last_check, 'timestamp'):
                        last_dt = datetime.fromtimestamp(last_check.timestamp())
                    else:
                        last_dt = datetime.fromisoformat(str(last_check))
                    hours_since = (datetime.now() - last_dt).total_seconds() / 3600
                    if hours_since < source['check_interval_hours']:
                        continue

            # Create task for this source
            task_id = f"enrich_{source_key}_{datetime.now().strftime('%Y%m%d_%H%M')}"
            db.collection('agent_tasks').document(task_id).set({
                'type': 'enrichment_check',
                'source': source_key,
                'source_name': source['name'],
                'description': source['description'],
                'status': 'pending',
                'created_at': firestore.SERVER_TIMESTAMP
            })
            print(f"  📡 Created enrichment task: {source['name']}")

            # Log the check
            db.collection('enrichment_log').document(source_key).set({
                'last_checked': datetime.now().isoformat(),
                'source_name': source['name'],
                'check_count': firestore.Increment(1)
            }, merge=True)

        except Exception as e:
            print(f"  ⚠️ Error checking {source_key}: {e}")

    # Check knowledge gaps
    check_knowledge_gaps()

    print(f"  ✅ Enrichment cycle #{cycle_num} complete")


def check_knowledge_gaps():
    """Check for gaps in knowledge base"""
    try:
        kb_docs = list(db.collection('knowledge_base').stream())
        total = len(kb_docs)

        categories = defaultdict(int)
        for doc in kb_docs:
            d = doc.to_dict()
            cat = d.get('category', 'unknown')
            categories[cat] += 1

        print(f"  📊 Knowledge base: {total} documents across {len(categories)} categories")

        # Check for gaps
        expected_categories = [
            'customs_tariff', 'import_requirements', 'standards',
            'food_safety', 'fta_benefits', 'regulatory_updates'
        ]
        for cat in expected_categories:
            if categories.get(cat, 0) == 0:
                print(f"  ⚠️ Gap: No documents for '{cat}'")

    except Exception as e:
        print(f"  ⚠️ Knowledge gap check failed: {e}")


# ============================================================
# PART 3: MASTER LOOP
# ============================================================

def main():
    """Main loop - checks email, processes, enriches"""
    print("=" * 70)
    print("🤖 RPA-PORT MASTER AGENT")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Email: {EMAIL_ADDR or 'NOT CONFIGURED'}")
    print(f"   Cycle: Check emails → Classify → Enrich → Sleep 5 min")
    print("   Press Ctrl+C to stop")
    print("=" * 70)

    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"\n{'='*60}")
            print(f"🔄 CYCLE #{cycle} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}")

            # Step 1: Check emails
            try:
                new_emails = check_emails()
            except Exception as e:
                print(f"❌ Email check error: {e}")
                new_emails = 0

            # Step 2: Run enrichment if idle
            try:
                run_enrichment_cycle(cycle)
            except Exception as e:
                print(f"❌ Enrichment error: {e}")

            # Step 3: Show status
            try:
                pending = list(db.collection('pending_tasks').where('status', '==', 'pending').stream())
                classifications = list(db.collection('classifications').where('status', '==', 'pending_classification').stream())
                print(f"\n📊 Status: {len(pending)} pending tasks, {len(classifications)} awaiting classification")
            except:
                pass

            # Sleep
            print(f"\n⏳ Next cycle in 5 minutes...")
            time.sleep(300)  # 5 minutes

    except KeyboardInterrupt:
        print(f"\n\n🛑 Master agent stopped at {datetime.now().strftime('%H:%M:%S')}")
        print(f"   Completed {cycle} cycles")


if __name__ == "__main__":
    main()
