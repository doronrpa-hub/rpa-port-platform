"""Read-only Firestore investigation: where did 767 enriched headings land?"""
import os
import json

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\User\rpa-port-platform\scripts\firebase-credentials.json"

from google.cloud import firestore

db = firestore.Client(project="rpa-port-customs")

print("=" * 70)
print("1. heading_knowledge collection — first 5 doc IDs")
print("=" * 70)
docs = list(db.collection("heading_knowledge").limit(5).stream())
if docs:
    for d in docs:
        print(f"  doc_id: {d.id}")
        data = d.to_dict()
        for k, v in data.items():
            val_str = str(v)
            if len(val_str) > 200:
                val_str = val_str[:200] + "..."
            print(f"    {k}: {val_str}")
        print()
else:
    print("  (no documents found)")

print()
print("=" * 70)
print("2. Try fetching heading_knowledge/84.13 and heading_knowledge/8413")
print("=" * 70)
for doc_id in ["84.13", "8413"]:
    ref = db.collection("heading_knowledge").document(doc_id)
    snap = ref.get()
    if snap.exists:
        print(f"  heading_knowledge/{doc_id} EXISTS:")
        data = snap.to_dict()
        for k, v in data.items():
            val_str = str(v)
            if len(val_str) > 300:
                val_str = val_str[:300] + "..."
            print(f"    {k}: {val_str}")
    else:
        print(f"  heading_knowledge/{doc_id} — NOT FOUND")
    print()

print()
print("=" * 70)
print("3. Check candidate collections for recent docs (limit 1 each)")
print("=" * 70)
candidates = [
    "heading_knowledge",
    "tariff_knowledge",
    "enrichment_results",
    "knowledge_enrichment",
    "tariff_enrichment",
    "heading_data",
    "brain_knowledge",
    "classification_knowledge",
    "tariff_headings",
    "heading_enrichment",
]
for coll_name in candidates:
    docs = list(db.collection(coll_name).limit(1).stream())
    if docs:
        d = docs[0]
        data = d.to_dict()
        print(f"  {coll_name} — HAS DATA (doc_id: {d.id})")
        for k, v in data.items():
            val_str = str(v)
            if len(val_str) > 200:
                val_str = val_str[:200] + "..."
            print(f"    {k}: {val_str}")
    else:
        print(f"  {coll_name} — EMPTY / NOT FOUND")
    print()

print()
print("=" * 70)
print("4. Check enrichment_state/cursor for output collection info")
print("=" * 70)
snap = db.collection("enrichment_state").document("cursor").get()
if snap.exists:
    data = snap.to_dict()
    print(f"  enrichment_state/cursor EXISTS:")
    for k, v in data.items():
        val_str = str(v)
        if len(val_str) > 300:
            val_str = val_str[:300] + "..."
        print(f"    {k}: {val_str}")
else:
    print("  enrichment_state/cursor — NOT FOUND")

# Also check other docs in enrichment_state
print()
print("  Other docs in enrichment_state:")
docs = list(db.collection("enrichment_state").limit(5).stream())
if docs:
    for d in docs:
        data = d.to_dict()
        print(f"    doc_id: {d.id}")
        for k, v in data.items():
            val_str = str(v)
            if len(val_str) > 200:
                val_str = val_str[:200] + "..."
            print(f"      {k}: {val_str}")
else:
    print("    (no documents)")

print()
print("=" * 70)
print("5. Count docs in heading_knowledge (if any)")
print("=" * 70)
# Stream all and count
count = 0
for _ in db.collection("heading_knowledge").stream():
    count += 1
    if count >= 1000:
        print(f"  heading_knowledge: {count}+ docs (stopped counting at 1000)")
        break
else:
    print(f"  heading_knowledge: {count} docs total")

print()
print("Done.")
