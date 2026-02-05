import re

with open('main.py', 'r') as f:
    content = f.read()

# Find and replace the rcb_check_email function
old_pattern = r'@scheduler_fn\.on_schedule\(schedule="\*/2 \* \* \* \*"\)\ndef rcb_check_email\(event: scheduler_fn\.ScheduledEvent\) -> None:.*?print\("✅ RCB check complete"\)'

new_function = '''@scheduler_fn.on_schedule(schedule="*/2 * * * *")
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
    from datetime import datetime, timedelta
    two_days_ago = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z")
    
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
        subject = msg.get('subject', 'No Subject')
        from_data = msg.get('from', {}).get('emailAddress', {})
        from_email = from_data.get('address', '')
        from_name = from_data.get('name', '')
        to_recipients = msg.get('toRecipients', [])
        
        # Check if sent TO rcb@ (not CC)
        is_direct = any(rcb_email.lower() in r.get('emailAddress', {}).get('address', '').lower() 
                       for r in to_recipients)
        
        if not is_direct:
            continue
        
        # Check sender domain
        if not from_email.lower().endswith('@rpa-port.co.il'):
            continue
        
        # Skip system emails
        if 'undeliverable' in subject.lower() or 'backup' in subject.lower():
            continue
        
        # Check if already processed
        safe_id = msg_id.replace("/", "_")[:100]
        if db.collection("rcb_processed").document(safe_id).get().exists:
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
        
        # Build and send acknowledgment (Email 1)
        reply_body = build_rcb_reply(
            sender_name=from_name,
            attachments=attachments,
            subject=subject,
            is_first_email=True,
            include_joke=False
        )
        
        if helper_graph_send(access_token, rcb_email, from_email, f"Re: {subject}", reply_body, msg_id, raw_attachments):
            print(f"    ✅ Ack sent to {from_email}")
            
            # Mark as processed
            db.collection("rcb_processed").document(safe_id).set({
                "processed_at": firestore.SERVER_TIMESTAMP,
                "subject": subject,
                "from": from_email
            })
            
            # Run classification and send report (Email 2)
            try:
                process_classification_and_send_report(
                    access_token, rcb_email, from_email, subject,
                    from_name, raw_attachments, msg_id, get_secret
                )
            except Exception as ce:
                print(f"    ⚠️ Classification error: {ce}")
        else:
            print(f"    ❌ Failed to send ack")
    
    print("✅ RCB check complete")'''

# Use regex with DOTALL to match across lines
content_new = re.sub(old_pattern, new_function, content, flags=re.DOTALL)

if content_new == content:
    print("❌ Pattern not found - manual fix needed")
else:
    with open('main.py', 'w') as f:
        f.write(content_new)
    print("✅ rcb_check_email updated")
