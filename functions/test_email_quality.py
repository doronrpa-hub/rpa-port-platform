"""
Session 41 — Test email quality fixes.
Tests:
  1. clean_email_subject() strips Re:/Fwd: chains
  2. validate_email_before_send() rejects empty/garbage
  3. _deal_has_minimum_data() blocks empty deals
  4. Sends a real tracker email for a deal WITH data (end-to-end)
  5. Verifies empty deal is blocked (no email sent)

Usage: cd functions && python test_email_quality.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from google.cloud import secretmanager

# ── Get secrets from Secret Manager ──
PROJECT_ID = "rpa-port-customs"
sm_client = secretmanager.SecretManagerServiceClient()

def get_secret(name):
    resp = sm_client.access_secret_version(
        request={"name": f"projects/{PROJECT_ID}/secrets/{name}/versions/latest"})
    return resp.payload.data.decode("UTF-8")

secrets = {
    'RCB_EMAIL': get_secret('RCB_EMAIL'),
    'RCB_GRAPH_CLIENT_ID': get_secret('RCB_GRAPH_CLIENT_ID'),
    'RCB_GRAPH_TENANT_ID': get_secret('RCB_GRAPH_TENANT_ID'),
    'RCB_GRAPH_CLIENT_SECRET': get_secret('RCB_GRAPH_CLIENT_SECRET'),
}

from lib.rcb_helpers import (
    helper_get_graph_token, helper_graph_send,
    clean_email_subject, validate_email_before_send
)
from lib.tracker_email import build_tracker_status_email

print("=" * 60)
print("Session 41 — Email Quality Fix Verification")
print("=" * 60)

# ═══════════════════════════════════════════════════
# TEST 1: clean_email_subject
# ═══════════════════════════════════════════════════
print("\n--- TEST 1: clean_email_subject ---")
cases = [
    ("Re: Re: Fwd: RE: Some Subject", "Some Subject"),
    ("RE:RE:RE: Test", "Test"),
    ("Fwd: FW: Fw: Important", "Important"),
    ("  Re:  RE:  re:  Subject  ", "Subject"),
    ("Normal Subject", "Normal Subject"),
    ("RCB | BOL123 | 3/5 Released", "RCB | BOL123 | 3/5 Released"),
    ("", ""),
]
all_pass = True
for inp, expected in cases:
    result = clean_email_subject(inp)
    status = "PASS" if result == expected else "FAIL"
    if status == "FAIL":
        all_pass = False
    print(f"  {status}: '{inp}' -> '{result}' (expected: '{expected}')")
print(f"  Result: {'ALL PASS' if all_pass else 'SOME FAILED'}")

# ═══════════════════════════════════════════════════
# TEST 2: validate_email_before_send
# ═══════════════════════════════════════════════════
print("\n--- TEST 2: validate_email_before_send ---")
cases_v = [
    ("", "<p>body</p>", False, "empty_subject"),
    ("Re: Re:", "<p>body</p>", False, "garbage_subject"),
    ("Good Subject", "", False, "empty_body"),
    ("Good Subject", "<p></p>", False, "body_too_short"),
    ("Good Subject", "<p>--- --- --- --- --- --- --- --- ---</p>", False, "body_only_dashes"),
    ("Good Subject", "<p>This is meaningful content with actual data</p>", True, "ok"),
    ("RCB | BOL123 | Active", "<div>Shipment tracking data with real content here</div>", True, "ok"),
]
all_pass_v = True
for subj, body, exp_valid, exp_reason in cases_v:
    valid, reason = validate_email_before_send(subj, body)
    status = "PASS" if valid == exp_valid and reason == exp_reason else "FAIL"
    if status == "FAIL":
        all_pass_v = False
    print(f"  {status}: subj='{subj[:30]}' valid={valid} reason={reason} (expected: {exp_valid}/{exp_reason})")
print(f"  Result: {'ALL PASS' if all_pass_v else 'SOME FAILED'}")

# ═══════════════════════════════════════════════════
# TEST 3: _deal_has_minimum_data
# ═══════════════════════════════════════════════════
print("\n--- TEST 3: _deal_has_minimum_data ---")
# Import from tracker — need to handle the module path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from tracker import _deal_has_minimum_data

cases_d = [
    ({"containers": [], "bol_number": "", "vessel_name": ""}, False, "empty deal"),
    ({"containers": ["TEMU1234567"], "bol_number": "", "vessel_name": ""}, True, "has containers"),
    ({"containers": [], "bol_number": "MEDURS12345", "vessel_name": ""}, True, "has BOL"),
    ({"containers": [], "bol_number": "", "vessel_name": "MSC ANNA"}, True, "has vessel"),
    ({"containers": ["X"], "bol_number": "Y", "vessel_name": "Z"}, True, "has all"),
    ({}, False, "empty dict"),
]
all_pass_d = True
for deal, expected, desc in cases_d:
    result = _deal_has_minimum_data(deal)
    status = "PASS" if result == expected else "FAIL"
    if status == "FAIL":
        all_pass_d = False
    print(f"  {status}: {desc} -> {result} (expected: {expected})")
print(f"  Result: {'ALL PASS' if all_pass_d else 'SOME FAILED'}")

# ═══════════════════════════════════════════════════
# TEST 4: build_tracker_status_email — new subject format
# ═══════════════════════════════════════════════════
print("\n--- TEST 4: Subject format ---")
test_deal = {
    "bol_number": "MEDURS12345",
    "vessel_name": "MSC ANNA",
    "shipping_line": "MSC",
    "direction": "import",
    "containers": ["MSCU1234567", "MSCU7654321"],
    "eta": "2026-02-20T08:00:00Z",
}
email_data = build_tracker_status_email(test_deal, [], "new_deal")
print(f"  Subject: {email_data['subject']}")
assert "RCB |" in email_data['subject'], "Subject should start with RCB |"
assert "MEDURS12345" in email_data['subject'], "Subject should contain BOL"
assert "[RCB-TRK]" not in email_data['subject'], "Subject should NOT have old format"
print(f"  PASS: New format verified")

email_data2 = build_tracker_status_email(test_deal, [], "status_update")
print(f"  Subject (update): {email_data2['subject']}")
assert "MSC ANNA" in email_data2['subject'], "Subject should contain vessel"
print(f"  PASS: Vessel in subject verified")

# ═══════════════════════════════════════════════════
# TEST 5: Send REAL test email (end-to-end)
# ═══════════════════════════════════════════════════
print("\n--- TEST 5: Send real tracker email ---")
access_token = helper_get_graph_token(secrets)
rcb_email = secrets['RCB_EMAIL']

if not access_token:
    print("  SKIP: Could not get Graph token")
else:
    # Build a real tracker email with test data
    test_deal_full = {
        "deal_id": "TEST_SESSION41",
        "bol_number": "TEST-BL-SESSION41",
        "vessel_name": "MV TEST VESSEL",
        "shipping_line": "TEST LINE",
        "direction": "import",
        "containers": ["TESTU1234567", "TESTU7654321"],
        "eta": "2026-02-25T10:00:00Z",
        "etd": "2026-02-18T06:00:00Z",
        "port": "ILHFA",
        "port_name": "Haifa",
        "shipper": "TEST SHIPPER CO",
        "consignee": "TEST CONSIGNEE LTD",
        "manifest_number": "M12345",
        "status": "active",
    }

    # Build email
    email_data = build_tracker_status_email(
        test_deal_full, [], "new_deal")
    subject = clean_email_subject(email_data['subject'])
    body_html = email_data['body_html']

    # Validate
    is_valid, reason = validate_email_before_send(subject, body_html)
    print(f"  Validation: valid={is_valid}, reason={reason}")
    assert is_valid, f"Test email should be valid but got: {reason}"

    # Send to doron@rpa-port.co.il — plain send (no threading, just validates email delivery)
    to_email = "doron@rpa-port.co.il"
    print(f"  RCB email: {rcb_email}")

    sent = helper_graph_send(
        access_token, rcb_email, to_email,
        subject, body_html
    )
    print(f"  Subject: {subject}")
    print(f"  Send result: {sent}")
    if sent:
        print(f"  PASS: Test email sent to {to_email}")
    else:
        print(f"  FAIL: Email send failed")

# ═══════════════════════════════════════════════════
# TEST 6: Verify empty deal is BLOCKED
# ═══════════════════════════════════════════════════
print("\n--- TEST 6: Empty deal blocked ---")
empty_deal = {
    "bol_number": "",
    "vessel_name": "",
    "containers": [],
    "direction": "import",
}
blocked = not _deal_has_minimum_data(empty_deal)
print(f"  Empty deal blocked: {blocked}")
assert blocked, "Empty deal should be blocked!"
print(f"  PASS: Empty deal correctly blocked from sending")

# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
all_tests = all_pass and all_pass_v and all_pass_d
print(f"OVERALL: {'ALL TESTS PASSED' if all_tests else 'SOME TESTS FAILED'}")
print("=" * 60)
