"""Patch main.py to add classification after acknowledgment"""

# Read current main.py
with open('main.py', 'r') as f:
    content = f.read()

# 1. Add import for classification at top (after other imports)
import_line = """from lib.classification_agents import run_full_classification, build_classification_email
from lib.rcb_helpers import extract_text_from_attachments"""

# Find where to add import (after "from lib.rcb_helpers" line)
if "from lib.classification_agents" not in content:
    # Find the last import from lib
    if "from lib.rcb_helpers" in content:
        content = content.replace(
            "from lib.rcb_helpers import",
            f"{import_line}\nfrom lib.rcb_helpers import"
        )
    else:
        # Add after firebase imports
        content = content.replace(
            "from firebase_admin import",
            f"from firebase_admin import"
        )
        # Find a good spot - after all imports
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('# ==') or line.startswith('db ='):
                lines.insert(i, import_line)
                break
        content = '\n'.join(lines)

# 2. Add classification function
classification_function = '''
# ============================================================
# CLASSIFICATION PROCESSING (called after acknowledgment)
# ============================================================

def process_classification_and_send_report(access_token, rcb_email, to_email, subject, sender_name, raw_attachments, msg_id, get_secret):
    """Extract text, run classification, send report email"""
    try:
        print(f"  🤖 Starting classification for: {subject[:50]}")
        
        # Get Anthropic API key
        anthropic_key = get_secret('ANTHROPIC_API_KEY')
        if not anthropic_key:
            print("  ❌ No Anthropic API key")
            return False
        
        # Extract text from PDFs
        print("  📄 Extracting text from attachments...")
        doc_text = extract_text_from_attachments(raw_attachments)
        
        if not doc_text or len(doc_text) < 50:
            print("  ⚠️ No readable text in attachments")
            # Send email saying couldn't read documents
            error_html = f"""<div dir="rtl" style="font-family:Arial;font-size:12pt;line-height:1.6">
            <p>שלום,</p>
            <p>לצערי לא הצלחתי לחלץ טקסט מהמסמכים שצירפת.</p>
            <p>אנא וודא שהקבצים הם PDF עם טקסט (לא סרוק כתמונה) ושלח שוב.</p>
            <p>לחלופין, ניתן להעביר את הבקשה לצוות בכתובת: airpaort@gmail.com</p>
            <hr style="margin:25px 0">
            <table dir="rtl"><tr>
                <td style="padding-left:15px"><img src="https://rpa-port.com/wp-content/uploads/2020/01/logo.png" style="width:80px"></td>
                <td style="border-right:3px solid #1e3a5f;padding-right:15px">
                    <strong style="color:#1e3a5f">🤖 RCB - AI Customs Broker</strong><br>
                    <strong>R.P.A. PORT LTD</strong>
                </td>
            </tr></table>
            </div>"""
            helper_graph_send(access_token, rcb_email, to_email, f"Re: {subject}", error_html, msg_id, None)
            return False
        
        print(f"  📝 Extracted {len(doc_text)} characters")
        
        # Run classification pipeline
        print("  🔍 Running classification agents...")
        results = run_full_classification(anthropic_key, doc_text)
        
        if not results.get('success'):
            print(f"  ❌ Classification failed: {results.get('error', 'Unknown error')}")
            return False
        
        # Build report email
        print("  📋 Building classification report...")
        report_html = build_classification_email(results, sender_name)
        
        # Send report email
        print("  📤 Sending classification report...")
        if helper_graph_send(access_token, rcb_email, to_email, f"📊 דו״ח סיווג: {subject}", report_html, msg_id, None):
            print(f"  ✅ Classification report sent to {to_email}")
            
            # Log to Firestore
            db.collection("rcb_classifications").add({
                "subject": subject,
                "to": to_email,
                "items_classified": len(results.get("agents", {}).get("hs_classification", {}).get("classifications", [])),
                "success": True,
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            return True
        else:
            print("  ❌ Failed to send report")
            return False
            
    except Exception as e:
        print(f"  ❌ Classification error: {e}")
        import traceback
        traceback.print_exc()
        return False

'''

# Add classification function if not present
if "def process_classification_and_send_report" not in content:
    # Find where rcb_check_email function starts and add before it
    if "def rcb_check_email" in content:
        content = content.replace(
            "def rcb_check_email",
            classification_function + "\ndef rcb_check_email"
        )

# 3. Add call to classification after acknowledgment is sent
# Find the line after "Replied to" log entry and add classification call
call_code = '''
            # Run classification in background and send report
            try:
                process_classification_and_send_report(
                    access_token, rcb_email, from_email, subject, 
                    from_name, raw_attachments, msg_id, get_secret
                )
            except Exception as ce:
                print(f"    ⚠️ Classification error (ack sent): {ce}")
'''

# Find the right place to insert - after the rcb_logs add for "sent" status
if "process_classification_and_send_report" not in content.split("def rcb_check_email")[1] if "def rcb_check_email" in content else "process_classification_and_send_report" not in content:
    # Look for the pattern after successful send
    marker = '"status": "sent",'
    marker2 = '"method": "graph_api",'
    
    if marker in content and marker2 in content:
        # Find the closing of the db.collection add
        parts = content.split(marker2)
        if len(parts) >= 2:
            # Find the next }) pattern
            after_marker = parts[1]
            # Find "timestamp": firestore.SERVER_TIMESTAMP followed by }) 
            insert_point = after_marker.find('firestore.SERVER_TIMESTAMP')
            if insert_point != -1:
                # Find the closing braces
                close_point = after_marker.find('})', insert_point)
                if close_point != -1:
                    # Insert after the })
                    new_after = after_marker[:close_point+2] + call_code + after_marker[close_point+2:]
                    content = parts[0] + marker2 + new_after
                    if len(parts) > 2:
                        content += marker2.join(parts[2:])

# Write updated main.py
with open('main.py', 'w') as f:
    f.write(content)

print("✅ main.py patched with classification integration")
