"""
Live test: Gate cutoff alert system (Tool #33)
==============================================
1. Find an active deal in Firestore
2. Set land_pickup_address + gate_cutoff (90 min from now = WARNING zone)
3. Run check_gate_cutoff_alerts()
4. Show results
5. Clean up test fields
"""
import json
import sys
import os
from datetime import datetime, timezone, timedelta
from google.cloud import firestore
from google.oauth2 import service_account

SA_KEY_PATH = r"C:\Users\doron\sa-key.json"
PROJECT_ID = "rpa-port-customs"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))


def get_db():
    creds = service_account.Credentials.from_service_account_file(SA_KEY_PATH)
    return firestore.Client(project=PROJECT_ID, credentials=creds)


def get_secret(name):
    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()
    resource = f"projects/{PROJECT_ID}/secrets/{name}/versions/latest"
    resp = client.access_secret_version(request={"name": resource})
    return resp.payload.data.decode("utf-8")


def main():
    db = get_db()

    # ── Step 1: Find an active deal ──
    print("=" * 60)
    print("  STEP 1: Finding an active deal...")
    print("=" * 60)
    active_deals = list(db.collection("tracker_deals")
                       .where("status", "in", ["active", "pending"])
                       .limit(10).stream())

    if not active_deals:
        print("  No active deals found! Creating a test deal...")
        # Create minimal test deal
        test_deal_ref = db.collection("tracker_deals").document("test_gate_cutoff_live")
        test_deal_ref.set({
            "bol_number": "TEST_GATE_CUTOFF",
            "vessel_name": "TEST VESSEL",
            "port": "ILHFA",
            "port_name": "Haifa",
            "status": "active",
            "follow_mode": "auto",
            "current_step": "customs_check",
            "direction": "import",
            "containers": ["TESTU1234567"],
            "follower_email": "doron@rpa-port.com",
            "cutoff_alerts_sent": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        deal_id = "test_gate_cutoff_live"
        deal_data = test_deal_ref.get().to_dict()
        print(f"  Created test deal: {deal_id}")
    else:
        # Pick first active deal
        deal_doc = active_deals[0]
        deal_id = deal_doc.id
        deal_data = deal_doc.to_dict()
        print(f"  Found deal: {deal_id}")
        print(f"  BOL: {deal_data.get('bol_number', '—')}")
        print(f"  Vessel: {deal_data.get('vessel_name', '—')}")
        print(f"  Port: {deal_data.get('port', '—')}")
        print(f"  Status: {deal_data.get('status', '—')}")
        print(f"  Follower: {deal_data.get('follower_email', '—')}")

    # ── Step 2: Set test land transport fields ──
    print()
    print("=" * 60)
    print("  STEP 2: Setting land transport fields (WARNING zone)...")
    print("=" * 60)

    # Gate cutoff = 90 min from now, which with ~30-60 min ETA gives ~30-60 min buffer → WARNING
    il_tz = timezone(timedelta(hours=2))
    gate_cutoff = (datetime.now(il_tz) + timedelta(minutes=90)).isoformat()
    pickup_address = "אזור תעשייה ציפורית, נשר, ישראל"  # Near Haifa

    port = deal_data.get("port", "ILHFA")
    print(f"  Pickup: {pickup_address}")
    print(f"  Gate cutoff: {gate_cutoff}")
    print(f"  Port: {port}")

    # Save original values to restore later
    orig_pickup = deal_data.get("land_pickup_address")
    orig_cutoff = deal_data.get("gate_cutoff")
    orig_alerts = deal_data.get("cutoff_alerts_sent")

    db.collection("tracker_deals").document(deal_id).update({
        "land_pickup_address": pickup_address,
        "gate_cutoff": gate_cutoff,
        "cutoff_alerts_sent": [],
        "port": port if port else "ILHFA",
    })
    print("  Fields set ✓")

    # ── Step 3: Test route_eta directly ──
    print()
    print("=" * 60)
    print("  STEP 3: Testing calculate_route_eta()...")
    print("=" * 60)
    from lib.route_eta import calculate_route_eta

    eta = calculate_route_eta(db, pickup_address, port, get_secret)
    if eta:
        print(f"  Duration: {eta['duration_minutes']} min")
        print(f"  Distance: {eta['distance_km']} km")
        print(f"  Provider: {eta['provider']}")
        print(f"  Cached: {eta['cached']}")
        print(f"  Summary: {eta['route_summary']}")
    else:
        print("  ❌ ETA calculation returned None!")

    # ── Step 4: Run check_gate_cutoff_alerts (dry — no email) ──
    print()
    print("=" * 60)
    print("  STEP 4: Running check_gate_cutoff_alerts() (no email - no token)...")
    print("=" * 60)
    from lib.tracker import check_gate_cutoff_alerts

    result = check_gate_cutoff_alerts(
        db, firestore, get_secret,
        access_token=None,  # No email sending
        rcb_email=None
    )
    print(f"  Result: {json.dumps(result, indent=2)}")

    # ── Step 5: Run WITH email sending ──
    print()
    print("=" * 60)
    print("  STEP 5: Running WITH email sending...")
    print("=" * 60)

    # Reset alerts_sent so it can fire again
    db.collection("tracker_deals").document(deal_id).update({
        "cutoff_alerts_sent": [],
    })

    try:
        from lib.rcb_helpers import get_rcb_secrets_internal, helper_get_graph_token
        secrets = get_rcb_secrets_internal(get_secret)
        access_token = helper_get_graph_token(secrets) if secrets else None
        rcb_email = secrets.get('RCB_EMAIL', 'rcb@rpa-port.co.il') if secrets else None

        if access_token:
            print(f"  Graph token: OK")
            print(f"  RCB email: {rcb_email}")

            result2 = check_gate_cutoff_alerts(
                db, firestore, get_secret,
                access_token=access_token,
                rcb_email=rcb_email
            )
            print(f"  Result: {json.dumps(result2, indent=2)}")
        else:
            print("  ❌ Could not get Graph token — skipping email test")
    except Exception as e:
        print(f"  ❌ Email test error: {e}")
        import traceback
        traceback.print_exc()

    # ── Step 6: Verify deal doc updated ──
    print()
    print("=" * 60)
    print("  STEP 6: Checking deal doc after alert...")
    print("=" * 60)
    updated_deal = db.collection("tracker_deals").document(deal_id).get().to_dict()
    print(f"  cutoff_alerts_sent: {updated_deal.get('cutoff_alerts_sent', [])}")
    print(f"  last_cutoff_alert: {updated_deal.get('last_cutoff_alert', '—')}")
    print(f"  last_cutoff_alert_at: {updated_deal.get('last_cutoff_alert_at', '—')}")

    # ── Step 7: Clean up ──
    print()
    print("=" * 60)
    print("  STEP 7: Cleaning up test fields...")
    print("=" * 60)
    cleanup = {}
    if orig_pickup is None:
        cleanup["land_pickup_address"] = firestore.DELETE_FIELD
    else:
        cleanup["land_pickup_address"] = orig_pickup
    if orig_cutoff is None:
        cleanup["gate_cutoff"] = firestore.DELETE_FIELD
    else:
        cleanup["gate_cutoff"] = orig_cutoff
    if orig_alerts is None:
        cleanup["cutoff_alerts_sent"] = firestore.DELETE_FIELD
    else:
        cleanup["cutoff_alerts_sent"] = orig_alerts
    cleanup["last_cutoff_alert"] = firestore.DELETE_FIELD
    cleanup["last_cutoff_alert_at"] = firestore.DELETE_FIELD

    db.collection("tracker_deals").document(deal_id).update(cleanup)

    # If we created a test deal, delete it
    if deal_id == "test_gate_cutoff_live":
        db.collection("tracker_deals").document(deal_id).delete()
        print("  Test deal deleted ✓")

    print("  Original fields restored ✓")
    print()
    print("=" * 60)
    print("  TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
