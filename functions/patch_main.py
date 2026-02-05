#!/usr/bin/env python3
"""
RCB Final Fix - Automated Patcher
==================================
This script patches main.py with the production-ready email processor.

Run: python patch_main.py
"""

import os
import re
import shutil
from datetime import datetime

def main():
    print("=" * 60)
    print("🔧 RCB Final Fix - Patching main.py")
    print("=" * 60)
    
    # Check we're in the right directory
    if not os.path.exists("main.py"):
        print("❌ main.py not found! Run this from ~/rpa-port-platform/functions/")
        return False
    
    # Backup
    backup_name = f"main.py.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy("main.py", backup_name)
    print(f"✅ Backup created: {backup_name}")
    
    # Read current content
    with open("main.py", "r") as f:
        content = f.read()
    
    # =========================================================================
    # PATCH 1: Increase memory to 1GB
    # =========================================================================
    content = content.replace(
        "memory=options.MemoryOption.MB_512",
        "memory=options.MemoryOption.GB_1"
    )
    print("✅ Memory increased to 1GB")
    
    # =========================================================================
    # PATCH 2: Replace the entire check_email_scheduled function
    # =========================================================================
    
    # Find the function start and end
    func_start = content.find("@scheduler_fn.on_schedule(schedule=\"every 5 minutes\"")
    if func_start == -1:
        print("⚠️ Could not find check_email_scheduled function start")
        func_start = content.find("def check_email_scheduled")
    
    # Find the next function (FUNCTION 2)
    func_end = content.find("# ============================================================\n# FUNCTION 2:")
    if func_end == -1:
        func_end = content.find("@firestore_fn.on_document_created")
    
    if func_start == -1 or func_end == -1:
        print("❌ Could not locate function boundaries")
        return False
    
    # New function code
    new_function = '''@scheduler_fn.on_schedule(schedule="every 5 minutes", memory=options.MemoryOption.GB_1, timeout_sec=300)
def check_email_scheduled(event: scheduler_fn.ScheduledEvent) -> None:
    """Check emails using RCB Email Processor - Production Ready"""
    
    print("🚀 RCB Email Processor Starting...")
    
    # Get email config
    try:
        config = db.collection("config").document("email").get().to_dict()
        email_addr = config["email"]
        email_pass = config["app_password"]
    except Exception as e:
        print(f"❌ Email config error: {e}")
        return
    
    # Use RCB Email Processor
    try:
        from lib.rcb_email_processor import process_emails
        result = process_emails(db, bucket, email_addr, email_pass)
        print(f"✅ Processing complete: {result.get('stats', {})}")
    except ImportError as ie:
        print(f"⚠️ Module import error: {ie}")
        print("Falling back to simple processor...")
        _simple_email_check(email_addr, email_pass)
    except Exception as e:
        print(f"❌ Processing error: {e}")
        import traceback
        traceback.print_exc()
        _simple_email_check(email_addr, email_pass)


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
    for doc in db.collection("inbox").stream():
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
            safe_id = re.sub(r'[/\\\\\\.\[\\]\\*~<>]', '_', str(msg_id))[:100]
            
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
            db.collection("inbox").document(safe_id).set({
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
                    db.collection("inbox").document(safe_id).update({"ack_sent": True})
            
            # Process attachments
            for att in attachments:
                try:
                    classify_and_store(att, from_str, subject, date_str, body_text)
                except Exception as ce:
                    print(f"    ⚠️ Classification error: {ce}")
            
            # Update status
            db.collection("inbox").document(safe_id).update({
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
        att_list = "\\n".join([f"  • {a['filename']}" for a in attachments])
        
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


'''
    
    # Replace the function
    content = content[:func_start] + new_function + content[func_end:]
    print("✅ check_email_scheduled function replaced")
    
    # =========================================================================
    # PATCH 3: Ensure imports are present
    # =========================================================================
    if "import smtplib" not in content:
        # Add after other imports
        import_section = "from datetime import datetime, timedelta, timezone"
        content = content.replace(
            import_section,
            import_section + "\nimport smtplib\nfrom email.mime.text import MIMEText\nfrom email.mime.multipart import MIMEMultipart"
        )
        print("✅ Added email sending imports")
    
    # =========================================================================
    # Write patched file
    # =========================================================================
    with open("main.py", "w") as f:
        f.write(content)
    
    print("")
    print("=" * 60)
    print("✅ main.py patched successfully!")
    print("=" * 60)
    print("")
    print("Next steps:")
    print("1. Copy rcb_email_processor.py to lib/:")
    print("   cp rcb_email_processor.py lib/")
    print("")
    print("2. Deploy:")
    print("   firebase deploy --only functions:check_email_scheduled --project rpa-port-customs")
    print("")
    print("3. Watch logs:")
    print("   gcloud logging read 'resource.type=cloud_run_revision' --project rpa-port-customs --limit 20")
    
    return True


if __name__ == "__main__":
    main()
