with open('main.py', 'r') as f:
    content = f.read()

missing_functions = '''
# ============================================================
# RCB HELPER FUNCTIONS
# ============================================================

def get_rcb_secrets():
    """Get RCB email secrets from Secret Manager"""
    try:
        secrets = {}
        for name in ['RCB_EMAIL', 'RCB_PASSWORD', 'RCB_FALLBACK_EMAIL', 
                     'RCB_GRAPH_CLIENT_ID', 'RCB_GRAPH_TENANT_ID', 'RCB_GRAPH_CLIENT_SECRET']:
            secrets[name] = get_secret(name)
        return secrets if secrets.get('RCB_EMAIL') else None
    except Exception as e:
        print(f"Secret error: {e}")
        return None

def get_graph_access_token(secrets):
    """Get Microsoft Graph API access token"""
    try:
        tenant_id = secrets.get('RCB_GRAPH_TENANT_ID')
        client_id = secrets.get('RCB_GRAPH_CLIENT_ID')
        client_secret = secrets.get('RCB_GRAPH_CLIENT_SECRET')
        
        response = requests.post(
            f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token',
            data={
                'client_id': client_id,
                'client_secret': client_secret,
                'scope': 'https://graph.microsoft.com/.default',
                'grant_type': 'client_credentials'
            }
        )
        if response.status_code == 200:
            return response.json().get('access_token')
        return None
    except Exception as e:
        print(f"Token error: {e}")
        return None

def graph_get_messages(access_token, user_email, unread_only=True, max_results=10):
    """Get messages from inbox"""
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/mailFolders/inbox/messages"
        params = {'$top': max_results, '$orderby': 'receivedDateTime desc'}
        if unread_only:
            params['$filter'] = 'isRead eq false'
        response = requests.get(url, headers={'Authorization': f'Bearer {access_token}'}, params=params)
        if response.status_code == 200:
            return response.json().get('value', [])
        return []
    except Exception as e:
        print(f"Get messages error: {e}")
        return []

def graph_get_attachments(access_token, user_email, message_id):
    """Get message attachments"""
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{message_id}/attachments"
        response = requests.get(url, headers={'Authorization': f'Bearer {access_token}'})
        if response.status_code == 200:
            return response.json().get('value', [])
        return []
    except Exception as e:
        print(f"Get attachments error: {e}")
        return []

def graph_mark_as_read(access_token, user_email, message_id):
    """Mark message as read"""
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{message_id}"
        requests.patch(url, headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}, json={'isRead': True})
    except:
        pass

def graph_send_email(access_token, user_email, to_email, subject, body_html, reply_to_id=None, attachments_data=None):
    """Send email with optional attachments"""
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/sendMail"
        message = {
            'subject': f"Re: {subject}" if reply_to_id else subject,
            'body': {'contentType': 'HTML', 'content': body_html},
            'toRecipients': [{'emailAddress': {'address': to_email}}]
        }
        if attachments_data:
            message['attachments'] = []
            for att in attachments_data:
                if att.get('contentBytes'):
                    message['attachments'].append({
                        '@odata.type': '#microsoft.graph.fileAttachment',
                        'name': att.get('name', 'attachment'),
                        'contentType': att.get('contentType', 'application/octet-stream'),
                        'contentBytes': att.get('contentBytes')
                    })
        response = requests.post(url, headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}, json={'message': message, 'saveToSentItems': True})
        return response.status_code == 202
    except Exception as e:
        print(f"Send email error: {e}")
        return False

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
HEBREW_NAMES = {
    'doron': 'דורון', 'amit': 'עמית', 'yossi': 'יוסי', 'moshe': 'משה',
    'david': 'דוד', 'avi': 'אבי', 'eli': 'אלי', 'dan': 'דן', 'oren': 'אורן',
    'guy': 'גיא', 'tal': 'טל', 'nir': 'ניר', 'roy': 'רועי', 'gal': 'גל',
    'yuval': 'יובל', 'itay': 'איתי', 'idan': 'עידן', 'eyal': 'אייל',
    'ran': 'רן', 'uri': 'אורי', 'yair': 'יאיר', 'alon': 'אלון', 'chen': 'חן',
    'lior': 'ליאור', 'omer': 'עומר', 'noam': 'נועם', 'ron': 'רון'
}

def to_hebrew_name(name):
    """Convert English name to Hebrew"""
    if not name:
        return "שלום"
    if any('\\u0590' <= c <= '\\u05FF' for c in name):
        return name
    return HEBREW_NAMES.get(name.lower().strip(), name)

def build_rcb_reply(sender_name, attachments, subject="", is_first_email=False, include_joke=False):
    """Build RCB auto-reply message"""
    name = sender_name.split('<')[0].strip()
    if not name or '@' in name:
        name = "שלום"
    else:
        name = to_hebrew_name(name.split()[0])
    
    hour = datetime.now().hour
    if 5 <= hour < 12:
        greeting = "בוקר טוב"
    elif 12 <= hour < 17:
        greeting = "צהריים טובים"
    elif 17 <= hour < 21:
        greeting = "ערב טוב"
    else:
        greeting = "לילה טוב"
    
    html = f"""
    <div dir="rtl" style="font-family: Arial, sans-serif; font-size: 12pt; line-height: 1.6;">
        <p><strong>{greeting} {name},</strong></p>
        <p>תודה על פנייתך! קיבלתי את המסמכים שלך ואני מתחילה לעבור עליהם.</p>
    """
    
    if subject:
        html += f'<p>📋 <strong>נושא:</strong> {subject}</p>'
    
    if attachments:
        html += f'<p>🔍 <strong>זיהיתי {len(attachments)} קבצים מצורפים:</strong></p><ul>'
        for att in attachments:
            icon = "📄"
            t = att.get('type', '')
            if t == '.pdf': icon = "📕"
            elif t in ['.xlsx', '.xls']: icon = "📊"
            elif t in ['.jpg', '.png', '.jpeg']: icon = "🖼️"
            html += f"<li>{icon} {att.get('filename', 'קובץ')}</li>"
        html += "</ul>"
    
    html += "<p>אעבור על המסמכים ואחזור אליך עם סיווג מכס מומלץ בהקדם.</p>"
    
    if include_joke:
        import random
        jokes = ["💡 טיפ: מסמך מסחרי טוב שווה אלף מילים!", "💡 קוד HS נכון יכול לחסוך עד 20% ממיסי היבוא!"]
        html += f"<p style='color:#666;font-style:italic;'>{random.choice(jokes)}</p>"
    
    html += """
        <hr style="border:none;border-top:1px solid #ddd;margin:25px 0;">
        <table dir="rtl"><tr>
            <td style="padding-left:15px;"><img src="https://rpa-port.com/wp-content/uploads/2020/01/logo.png" style="width:80px;"></td>
            <td style="border-right:3px solid #1e3a5f;padding-right:15px;">
                <strong style="color:#1e3a5f;">🤖 RCB - AI Customs Broker</strong><br>
                <strong style="color:#1e3a5f;">R.P.A. PORT LTD</strong><br>
                <span style="color:#666;font-size:10pt;">Freight Forwarders & Customs Brokers</span><br>
                <span style="color:#888;font-size:10pt;">📧 rcb@rpa-port.co.il</span>
            </td>
        </tr></table>
        <p style="color:#aaa;font-size:9pt;margin-top:15px;">הודעה זו נשלחה אוטומטית ע"י מערכת AI.</p>
    </div>
    """
    return html

'''

# Insert before rcb_api function
marker = '@https_fn.on_request(cors=options.CorsOptions(cors_origins="*", cors_methods=["GET", "POST"]))\ndef rcb_api'
if 'def get_rcb_secrets' not in content:
    if 'def rcb_api' in content:
        content = content.replace('def rcb_api', missing_functions + '\ndef rcb_api')
        print("✅ Missing functions added!")
    else:
        print("❌ Could not find rcb_api")
else:
    print("⚠️ Functions already exist")

with open('main.py', 'w') as f:
    f.write(content)

print(f"File size: {len(content)} chars")
