#!/usr/bin/env python3
"""
Patch main.py with Smart Email Checker
Run: python patch_smart_email.py
"""

import re

# Read current main.py
with open("main.py", "r") as f:
    content = f.read()

# Backup
with open("main.py.backup_session10", "w") as f:
    f.write(content)
print("✅ Backup created: main.py.backup_session10")

# === PATCH 1: Fix memory ===
content = content.replace(
    "memory=options.MemoryOption.MB_512",
    "memory=options.MemoryOption.GB_1"
)
print("✅ Memory increased to 1GB")

# === PATCH 2: Replace email search from ALL to TODAY only ===
old_search = 'status, messages = mail.search(None, "ALL")'
new_search = '''# Search only TODAY's emails (not all!)
    from datetime import datetime
    today = datetime.now()
    date_str = today.strftime("%d-%b-%Y")  # Format: 05-Feb-2026
    status, messages = mail.search(None, f'(SINCE "{date_str}")')
    print(f"Checking emails from {date_str}")'''

content = content.replace(old_search, new_search)
print("✅ Email search changed to TODAY only")

# === PATCH 3: Add ACK email sending after storing ===
# Find where we store the email and add ACK
old_store = '''            # Store email
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
            })'''

new_store = '''            # Store email
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
                "status": "processing",
                "received_at": firestore.SERVER_TIMESTAMP
            })
            
            # Send ACK email immediately
            try:
                sender_email = extract_reply_email(from_str)
                if sender_email and attachments:
                    send_ack_email(email_addr, email_pass, sender_email, subject, attachments)
                    db.collection("inbox").document(safe_id).update({"ack_sent": True})
            except Exception as ack_err:
                print(f"ACK error: {ack_err}")'''

content = content.replace(old_store, new_store)
print("✅ ACK email sending added")

# === PATCH 4: Update status after classification ===
old_classify = '''            # Classify each attachment (triggers Firestore listener)
            for att in attachments:
                classify_and_store(att, from_str, subject, date_str, body_text)'''

new_classify = '''            # Classify each attachment
            classifications = []
            for att in attachments:
                try:
                    result = classify_and_store(att, from_str, subject, date_str, body_text)
                    if result:
                        classifications.append(result)
                except Exception as class_err:
                    print(f"Classification error: {class_err}")
            
            # Send classification report
            try:
                if sender_email and classifications:
                    send_classification_report(email_addr, email_pass, sender_email, subject, classifications, safe_id)
            except Exception as report_err:
                print(f"Report error: {report_err}")
            
            # Update status to completed
            db.collection("inbox").document(safe_id).update({
                "status": "completed",
                "processed_at": firestore.SERVER_TIMESTAMP
            })'''

content = content.replace(old_classify, new_classify)
print("✅ Classification report sending added")

# === PATCH 5: Add helper functions before the first function ===
helper_functions = '''
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
        att_list = "\\n".join([f"  • {a['filename']}" for a in attachments])
        
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
            lines.extend(["בברכה,", "מערכת RCB", "ר.פ.א - פורט בע\\"מ"])
            body = "\\n".join(lines)
        
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
        db.collection("inbox").document(doc_id).update({"report_sent": True})
        
    except Exception as e:
        print(f"Report email error: {e}")


'''

# Insert helper functions before the first @scheduler_fn
insert_point = "# ============================================================\n# FUNCTION 1: CHECK EMAIL"
content = content.replace(insert_point, helper_functions + insert_point)
print("✅ Helper functions added")

# Write patched file
with open("main.py", "w") as f:
    f.write(content)

print("")
print("=" * 50)
print("✅ main.py patched successfully!")
print("=" * 50)
print("")
print("Next steps:")
print("1. Review: head -250 main.py")
print("2. Deploy: firebase deploy --only functions:check_email_scheduled --project rpa-port-customs")
