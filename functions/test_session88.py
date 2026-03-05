"""
Session 88 Live Test: Send toshav chozer email to rcb@rpa-port.co.il
and monitor Cloud Function logs for case_reasoning detection.

Run:  python test_session88.py
"""

import os
import sys
import subprocess
import requests


def get_secret(name):
    result = subprocess.run(
        ["gcloud", "secrets", "versions", "access", "latest",
         f"--secret={name}", "--project=rpa-port-customs"],
        capture_output=True, text=True, shell=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get secret {name}: {result.stderr}")
    return result.stdout.strip()


def get_token():
    tenant = get_secret("RCB_GRAPH_TENANT_ID")
    client_id = get_secret("RCB_GRAPH_CLIENT_ID")
    client_secret = get_secret("RCB_GRAPH_CLIENT_SECRET")
    resp = requests.post(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
    )
    return resp.json()["access_token"]


def send_test_email(token, from_email, to_email, subject, body):
    """Send email via Graph API."""
    url = f"https://graph.microsoft.com/v1.0/users/{from_email}/sendMail"
    msg = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to_email}}],
        },
        "saveToSentItems": True,
    }
    r = requests.post(url, headers={"Authorization": f"Bearer {token}",
                                     "Content-Type": "application/json"}, json=msg)
    print(f"  Send status: {r.status_code}")
    if r.status_code != 202:
        print(f"  Error: {r.text}")
    return r.status_code == 202


if __name__ == "__main__":
    print("=" * 60)
    print("Session 88 Live Test: Toshav Chozer Email")
    print("=" * 60)

    print("\n1. Getting Graph API token...")
    token = get_token()
    print("   OK")

    doron_email = "doron@rpa-port.co.il"
    rcb_email = "rcb@rpa-port.co.il"
    subject = "RCB-TEST-SESSION88 - toshav chozer"
    body = (
        "שלום, אני תושב חוזר מארצות הברית. "
        "אני חוזר עם ספה, שולחנות, כיסאות, טלוויזיה OLED, רכב ואלבומי תמונות ב-3 מכולות. "
        "מה המכס?"
    )

    print(f"\n2. Sending test email from {doron_email} to {rcb_email}...")
    print(f"   Subject: {subject}")
    print(f"   Body: {body}")
    ok = send_test_email(token, doron_email, rcb_email, subject, body)
    if ok:
        print("   Email sent successfully!")
        print("\n3. Next steps:")
        print("   - Watch Cloud Function logs: firebase functions:log --only rcb_check_email")
        print("   - Or: gcloud functions logs read rcb_check_email --project rpa-port-customs --limit 50")
        print("   - Check Doron's inbox for the reply")
        print("   - Verify: case_reasoning detects toshav_chozer, extracts 6 items, Tier 3")
    else:
        print("   FAILED to send email!")
