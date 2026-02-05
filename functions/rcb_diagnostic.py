#!/usr/bin/env python3
"""RCB Diagnostic Tool - Run: python3 rcb_diagnostic.py"""
import subprocess, requests, argparse
from datetime import datetime, timedelta

CLIENT_ID = "a6d44279-39c8-4c8e-8fb6-04a25c69fdd3"
TENANT_ID = "d85f69a4-6269-4aae-bc3d-1cf43042772c"
RCB_EMAIL = "rcb@rpa-port.co.il"

def get_token():
    secret = subprocess.check_output(["gcloud", "secrets", "versions", "access", "latest", "--secret=RCB_GRAPH_CLIENT_SECRET"]).decode().strip()
    r = requests.post(f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data={"client_id": CLIENT_ID, "client_secret": secret, "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"})
    return r.json().get("access_token") if r.ok else None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", metavar="KEYWORD", help="Clear from rcb_processed")
    parser.add_argument("--debug", metavar="KEYWORD", help="Debug email filters")
    args = parser.parse_args()
    
    from google.cloud import firestore
    db = firestore.Client()
    
    print("📊 rcb_processed:")
    for doc in db.collection('rcb_processed').stream():
        print(f"  {doc.to_dict().get('subject','')[:50]}")
    
    token = get_token()
    if token:
        print("\n📬 Recent emails:")
        r = requests.get(f"https://graph.microsoft.com/v1.0/users/{RCB_EMAIL}/messages?$top=10&$select=subject,receivedDateTime",
            headers={"Authorization": f"Bearer {token}"})
        for m in r.json().get("value", []):
            print(f"  {m['receivedDateTime'][:16]} | {m['subject'][:40]}")
    
    if args.clear:
        for doc in db.collection('rcb_processed').stream():
            if args.clear.lower() in doc.to_dict().get('subject','').lower():
                doc.reference.delete()
                print(f"✅ Deleted: {doc.id[:30]}")

if __name__ == "__main__":
    main()
