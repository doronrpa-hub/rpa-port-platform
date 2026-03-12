"""Send a test email to rcb@rpa-port.co.il for pipeline testing.

Uses Microsoft Graph API via the same credentials as the RCB system.
Run from project root: python send_test_email.py
"""
import json
import sys
import requests
from datetime import datetime

# --- Config ---
SA_KEY_PATH = r"C:\Users\User\rpa-port-platform\scripts\firebase-credentials.json"
PROJECT_ID = "rpa-port-customs"
SENDER = "doron@rpa-port.co.il"  # must be @rpa-port.co.il
RECIPIENT = "rcb@rpa-port.co.il"

def get_secret(name):
    from google.cloud import secretmanager
    import os
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", SA_KEY_PATH)
    client = secretmanager.SecretManagerServiceClient()
    path = f"projects/{PROJECT_ID}/secrets/{name}/versions/latest"
    resp = client.access_secret_version(request={"name": path})
    return resp.payload.data.decode("UTF-8")

def get_graph_token():
    tenant = get_secret("RCB_GRAPH_TENANT_ID")
    client_id = get_secret("RCB_GRAPH_CLIENT_ID")
    client_secret = get_secret("RCB_GRAPH_CLIENT_SECRET")
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    resp = requests.post(url, data={
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    })
    resp.raise_for_status()
    return resp.json()["access_token"]

def send_email(token, subject, body):
    url = f"https://graph.microsoft.com/v1.0/users/{SENDER}/sendMail"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": RECIPIENT}}],
        }
    }
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code == 202:
        print(f"Email sent: {subject}")
    else:
        print(f"FAILED {resp.status_code}: {resp.text[:300]}")

if __name__ == "__main__":
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    subject = f"סיווג פילטרים TEST-{ts}"
    body = "יש לי לקוח שרוצה לייבא פילטרים. מה פרט המכס ומה צריך מבחינת חוקיות?"

    print(f"Getting Graph token...")
    token = get_graph_token()
    print(f"Sending: {subject}")
    send_email(token, subject, body)
