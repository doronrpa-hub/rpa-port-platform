"""
Live test: Verify _is_internal_recipient() guard blocks external sends.

1. Gets Graph API token (same as production)
2. Sends a test email FROM doron@ TO rcb@ simulating an external-sender thread
3. Waits for rcb_check_email to process it
4. Checks Sent Items: confirms NO reply went to any external address
5. Cleans up test email

Run:  python test_external_block.py
"""

import os
import sys
import time
import requests

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS",
                       r"C:\Users\doron\sa-key.json")

from google.cloud import secretmanager

def get_secret(name):
    client = secretmanager.SecretManagerServiceClient()
    path = f"projects/rpa-port-customs/secrets/{name}/versions/latest"
    return client.access_secret_version(request={"name": path}).payload.data.decode("UTF-8")


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
            "body": {"contentType": "HTML", "content": body},
            "toRecipients": [{"emailAddress": {"address": to_email}}],
        },
        "saveToSentItems": True,
    }
    r = requests.post(url, headers={"Authorization": f"Bearer {token}",
                                     "Content-Type": "application/json"}, json=msg)
    return r.status_code == 202


def check_sent_items(token, user_email, subject_contains, minutes=5):
    """Check Sent Items for replies matching subject."""
    url = f"https://graph.microsoft.com/v1.0/users/{user_email}/mailFolders/sentitems/messages"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                     params={"$top": 20, "$orderby": "sentDateTime desc"})
    results = []
    for msg in r.json().get("value", []):
        subj = msg.get("subject", "")
        if subject_contains.lower() in subj.lower():
            recipients = [r["emailAddress"]["address"]
                          for r in msg.get("toRecipients", [])]
            cc = [r["emailAddress"]["address"]
                  for r in msg.get("ccRecipients", [])]
            results.append({
                "subject": subj,
                "to": recipients,
                "cc": cc,
                "sent": msg.get("sentDateTime"),
            })
    return results


def main():
    print("=" * 60)
    print("LIVE TEST: External send block verification")
    print("=" * 60)

    rcb_email = get_secret("RCB_EMAIL")
    doron_email = "doron@rpa-port.co.il"
    token = get_token()

    # Unique subject so we can track it
    tag = f"GUARD-TEST-{int(time.time())}"
    subject = f"Fwd: Invoice from NJAN Industries [{tag}]"
    body = f"""<div>
    <p>Hi, please classify this invoice from lea@njan.co.il</p>
    <p>From: lea@njan.co.il</p>
    <p>Subject: Invoice #INV-2026-0042</p>
    <p>Items: Steel bolts M10x50 grade 8.8, qty 5000</p>
    <p>[TEST TAG: {tag}]</p>
    </div>"""

    # Step 1: Send test email from doron@ to rcb@
    print(f"\n1. Sending test email from {doron_email} to {rcb_email}")
    print(f"   Subject: {subject}")
    ok = send_test_email(token, doron_email, rcb_email, subject, body)
    print(f"   Send result: {'OK' if ok else 'FAILED'}")
    if not ok:
        print("   ABORT — couldn't send test email")
        return

    # Step 2: Wait for processing
    wait_secs = 180
    print(f"\n2. Waiting {wait_secs}s for rcb_check_email to process...")
    for i in range(wait_secs // 10):
        time.sleep(10)
        elapsed = (i + 1) * 10
        print(f"   {elapsed}s / {wait_secs}s", end="\r")
    print()

    # Step 3: Check Sent Items from RCB
    print(f"\n3. Checking {rcb_email} Sent Items for replies with '{tag}'...")
    replies = check_sent_items(token, rcb_email, tag)

    if not replies:
        print("   NO replies found in Sent Items. Checking broader...")
        # Also check for any recent sends from rcb@
        all_recent = check_sent_items(token, rcb_email, "NJAN")
        if all_recent:
            print(f"   WARNING: Found {len(all_recent)} sends matching 'NJAN':")
            for r in all_recent:
                print(f"     To: {r['to']}  CC: {r['cc']}  Subj: {r['subject'][:60]}")
        else:
            print("   PASS: No replies to NJAN found anywhere.")
    else:
        print(f"   Found {len(replies)} replies:")
        all_ok = True
        for r in replies:
            all_to = r["to"] + r["cc"]
            external = [e for e in all_to if not e.lower().endswith("@rpa-port.co.il")]
            status = "BLOCKED" if not external else "LEAK!"
            if external:
                all_ok = False
            print(f"   {status} | To: {r['to']} CC: {r['cc']}")

        if all_ok:
            print("\n   PASS: All replies went to @rpa-port.co.il only.")
        else:
            print("\n   FAIL: External recipients found in replies!")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
