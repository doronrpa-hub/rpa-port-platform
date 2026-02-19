"""
Dry-run cleanup script for DARBOX/RPA16666 duplicate deals.

Shows exactly what would be deleted. Does NOT delete anything.
Run with --execute to actually perform deletions.
"""

import sys
import json
from datetime import datetime
from google.cloud import firestore

db = firestore.Client.from_service_account_json(
    r"C:\Users\doron\sa-key.json",
    project="rpa-port-customs",
)

EXECUTE = "--execute" in sys.argv

# ─────────────────────────────────────────────────────────
#  Step 1: Find all 9 deals from timeline
# ─────────────────────────────────────────────────────────

print("=" * 70)
print("STEP 1: Finding all deals from the DARBOX/RPA16666 thread")
print("=" * 70)

# Known deal IDs from timeline investigation
KNOWN_DEAL_IDS = [
    "kioLntuDsIUiUsy97XZD",
    "Vmn9cjhprQOfT9tQr9eq",
    "uEUsQ4QhduwjzsznrFup",
    "4ENaLjfXdLL3VatFM6wt",
    "29DvH18xBmXNurOeReiD",
    "irNeFo8XUbTWxCDJcHDh",
    "sjlyIoRV8hOllBkqlW86",
    "S1GRH8WVgGVU3ClmPThE",
    "Z6uKIN6rWcjYbJjk5YCK",
]

deals = {}
for did in KNOWN_DEAL_IDS:
    doc = db.collection("tracker_deals").document(did).get()
    if doc.exists:
        deals[did] = doc.to_dict()

print(f"\nFound {len(deals)} deals out of {len(KNOWN_DEAL_IDS)} known IDs:\n")

# Rank deals by data richness to pick the best one to keep
def deal_score(d):
    """Higher = more data."""
    score = 0
    if d.get("bol_number"): score += 10
    if d.get("vessel_name"): score += 5
    if d.get("shipping_line"): score += 3
    if d.get("manifest_number"): score += 3
    if d.get("customs_declaration"): score += 5
    score += len(d.get("containers", [])) * 5
    score += len(d.get("source_emails", [])) * 1
    if d.get("rcb_classification_id"): score += 20
    return score

ranked = sorted(deals.items(), key=lambda x: (-deal_score(x[1]), x[1].get("created_at", "")))

keep_id = ranked[0][0] if ranked else None
delete_deal_ids = [did for did in deals if did != keep_id]

for i, (did, d) in enumerate(ranked):
    marker = ">>> KEEP <<<" if did == keep_id else "    DELETE"
    created = str(d.get("created_at", "?"))[:19]
    status = d.get("status", "?")
    bol = d.get("bol_number", "") or "(blank)"
    vessel = d.get("vessel_name", "") or "(blank)"
    containers = d.get("containers", [])
    score = deal_score(d)
    print(f"  {marker}  {did}")
    print(f"           created={created}  status={status}  score={score}")
    print(f"           bol={bol}  vessel={vessel}  containers={containers}")
    print()

# ─────────────────────────────────────────────────────────
#  Step 2: Find container_status docs for duplicate deals
# ─────────────────────────────────────────────────────────

print("=" * 70)
print("STEP 2: Container status docs for DUPLICATE deals")
print("=" * 70)

container_docs_to_delete = []
container_docs_to_keep = []

for did in KNOWN_DEAL_IDS:
    docs = list(db.collection("tracker_container_status").where("deal_id", "==", did).stream())
    for doc in docs:
        entry = {"id": doc.id, "deal_id": did, "container_id": doc.to_dict().get("container_id", "?")}
        if did in delete_deal_ids:
            container_docs_to_delete.append(entry)
        else:
            container_docs_to_keep.append(entry)

print(f"\n  KEEP:   {len(container_docs_to_keep)} container docs (deal {keep_id})")
for c in container_docs_to_keep:
    print(f"           {c['id']}  container={c['container_id']}")

print(f"\n  DELETE: {len(container_docs_to_delete)} container docs")
for c in container_docs_to_delete:
    print(f"           {c['id']}  deal={c['deal_id']}  container={c['container_id']}")

# ─────────────────────────────────────────────────────────
#  Step 3: Find timeline entries for duplicate deals
# ─────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("STEP 3: Timeline entries for DUPLICATE deals")
print("=" * 70)

timeline_to_delete = []
timeline_to_keep = []

for did in KNOWN_DEAL_IDS:
    docs = list(db.collection("tracker_timeline").where("deal_id", "==", did).stream())
    for doc in docs:
        d = doc.to_dict()
        entry = {"id": doc.id, "deal_id": did, "event": d.get("event_type", "?"), "ts": str(d.get("timestamp", ""))[:19]}
        if did in delete_deal_ids:
            timeline_to_delete.append(entry)
        else:
            timeline_to_keep.append(entry)

print(f"\n  KEEP:   {len(timeline_to_keep)} timeline entries (deal {keep_id})")
for t in timeline_to_keep:
    print(f"           {t['id']}  event={t['event']}  ts={t['ts']}")

print(f"\n  DELETE: {len(timeline_to_delete)} timeline entries")
for t in timeline_to_delete:
    print(f"           {t['id']}  deal={t['deal_id']}  event={t['event']}")

# ─────────────────────────────────────────────────────────
#  Step 4: Find self-observations (from rcb@rpa-port.co.il)
# ─────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("STEP 4: Self-observations from rcb@rpa-port.co.il")
print("=" * 70)

# Query observations from rcb@ (no order_by to avoid composite index)
all_obs = list(db.collection("tracker_observations")
               .where("from_email", "==", "rcb@rpa-port.co.il")
               .limit(500)
               .stream())

self_obs = []
for doc in all_obs:
    d = doc.to_dict()
    subj = d.get("subject", "")
    # Only target the DARBOX thread
    if "DARBOX" in subj.upper() or "RPA16666" in subj.upper() or "6015697" in subj:
        self_obs.append({
            "id": doc.id,
            "subject": subj[:80],
            "created_at": str(d.get("created_at", ""))[:19],
            "deal_id": d.get("deal_id", "(none)"),
        })

print(f"\n  DELETE: {len(self_obs)} self-observations from rcb@ about DARBOX/RPA16666")
for i, obs in enumerate(self_obs[:10]):
    print(f"           [{i+1}] {obs['id']}  deal={obs['deal_id']}  ts={obs['created_at']}")
if len(self_obs) > 10:
    print(f"           ... and {len(self_obs) - 10} more")

# ─────────────────────────────────────────────────────────
#  Step 5: Find rcb_processed entries for self-emails
# ─────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("STEP 5: rcb_processed entries from rcb@ (DARBOX thread)")
print("=" * 70)

processed_to_delete = []
all_processed = list(db.collection("rcb_processed")
                     .where("from", "==", "rcb@rpa-port.co.il")
                     .limit(200)
                     .stream())

for doc in all_processed:
    d = doc.to_dict()
    subj = d.get("subject", "")
    if "DARBOX" in subj.upper() or "RPA16666" in subj.upper() or "6015697" in subj:
        processed_to_delete.append({
            "id": doc.id,
            "subject": subj[:80],
        })

print(f"\n  DELETE: {len(processed_to_delete)} rcb_processed entries")
for p in processed_to_delete[:10]:
    print(f"           {p['id']}  subj={p['subject']}")
if len(processed_to_delete) > 10:
    print(f"           ... and {len(processed_to_delete) - 10} more")

# ─────────────────────────────────────────────────────────
#  SUMMARY
# ─────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("DELETION SUMMARY")
print("=" * 70)

total = (len(delete_deal_ids) + len(container_docs_to_delete) +
         len(timeline_to_delete) + len(self_obs) + len(processed_to_delete))

print(f"\n  KEEP:")
print(f"    1 deal:              {keep_id}")
print(f"    {len(container_docs_to_keep)} container docs")
print(f"    {len(timeline_to_keep)} timeline entries")
print(f"\n  DELETE:")
print(f"    {len(delete_deal_ids)} duplicate deals")
print(f"    {len(container_docs_to_delete)} container status docs")
print(f"    {len(timeline_to_delete)} timeline entries")
print(f"    {len(self_obs)} self-observations")
print(f"    {len(processed_to_delete)} rcb_processed entries")
print(f"    --------------------")
print(f"    {total} total documents to delete\n")

if not EXECUTE:
    print("  DRY RUN -- nothing was deleted.")
    print("  Run with --execute to perform deletions.")
else:
    print("  EXECUTING DELETIONS...")
    deleted = 0

    # Delete duplicate deals
    for did in delete_deal_ids:
        db.collection("tracker_deals").document(did).delete()
        deleted += 1
        print(f"    OK Deleted deal {did}")

    # Delete container status docs
    for c in container_docs_to_delete:
        db.collection("tracker_container_status").document(c["id"]).delete()
        deleted += 1
    print(f"    OK Deleted {len(container_docs_to_delete)} container docs")

    # Delete timeline entries
    for t in timeline_to_delete:
        db.collection("tracker_timeline").document(t["id"]).delete()
        deleted += 1
    print(f"    OK Deleted {len(timeline_to_delete)} timeline entries")

    # Delete self-observations
    for obs in self_obs:
        db.collection("tracker_observations").document(obs["id"]).delete()
        deleted += 1
    print(f"    OK Deleted {len(self_obs)} self-observations")

    # Delete rcb_processed entries
    for p in processed_to_delete:
        db.collection("rcb_processed").document(p["id"]).delete()
        deleted += 1
    print(f"    OK Deleted {len(processed_to_delete)} rcb_processed entries")

    print(f"\n  DONE Done. {deleted} documents deleted.")
