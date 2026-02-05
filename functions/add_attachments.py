# Read main.py
with open('main.py', 'r') as f:
    content = f.read()

# Update graph_send_email to support attachments
old_func = '''def graph_send_email(access_token, user_email, to_email, subject, body_html, reply_to_id=None):
    """Send email using Microsoft Graph API"""
    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/sendMail"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    message = {
        'subject': subject if not reply_to_id else f"Re: {subject}",
        'body': {
            'contentType': 'HTML',
            'content': body_html
        },
        'toRecipients': [
            {'emailAddress': {'address': to_email}}
        ]
    }
    
    data = {
        'message': message,
        'saveToSentItems': True
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Graph API send email failed: {e}")
        return False'''

new_func = '''def graph_send_email(access_token, user_email, to_email, subject, body_html, reply_to_id=None, attachments_data=None):
    """Send email using Microsoft Graph API with optional attachments"""
    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/sendMail"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    message = {
        'subject': f"Re: {subject}" if reply_to_id else subject,
        'body': {
            'contentType': 'HTML',
            'content': body_html
        },
        'toRecipients': [
            {'emailAddress': {'address': to_email}}
        ]
    }
    
    # Add attachments if provided
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
    
    data = {
        'message': message,
        'saveToSentItems': True
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Graph API send email failed: {e}")
        return False'''

content = content.replace(old_func, new_func)

# Update the call to graph_send_email to pass attachments
old_call = 'if graph_send_email(access_token, rcb_email, from_email, subject, reply_body, msg_id):'
new_call = 'if graph_send_email(access_token, rcb_email, from_email, subject, reply_body, msg_id, raw_attachments):'

content = content.replace(old_call, new_call)

with open('main.py', 'w') as f:
    f.write(content)

print("✅ Added attachment support!")
