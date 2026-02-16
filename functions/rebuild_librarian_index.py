"""
Rebuild Librarian Index — Assignment 10, Session 27.

Scans all known collections and rebuilds the librarian_index.
Run with DRY_RUN=True first to verify counts, then set to False to write.
"""
import firebase_admin
from firebase_admin import credentials, firestore
import sys
import os
import time

sys.stdout.reconfigure(encoding='utf-8')

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\Users\doron\Desktop\doronrpa\firebase-credentials.json'

if not firebase_admin._apps:
    cred = credentials.Certificate(r'C:\Users\doron\Desktop\doronrpa\firebase-credentials.json')
    firebase_admin.initialize_app(cred, {'projectId': 'rpa-port-customs'})

db = firestore.client()

DRY_RUN = '--write' not in sys.argv

# ═══════════════════════════════════════════
# STEP 1: Scan all collections
# ═══════════════════════════════════════════
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from lib.librarian_index import COLLECTION_FIELDS, _build_index_entry

print('=' * 60)
print('LIBRARIAN INDEX REBUILD')
print('=' * 60)
print(f'Mode: {"DRY RUN" if DRY_RUN else "WRITE"}')
print(f'Collections to index: {len(COLLECTION_FIELDS)}')
print()

total_docs = 0
total_indexed = 0
per_collection = {}

start = time.time()

for coll_name, field_config in COLLECTION_FIELDS.items():
    coll_start = time.time()
    count = 0
    try:
        for doc in db.collection(coll_name).stream():
            count += 1
    except Exception as e:
        print(f'  ERROR scanning {coll_name}: {e}')
        per_collection[coll_name] = -1
        continue

    per_collection[coll_name] = count
    total_docs += count
    coll_elapsed = time.time() - coll_start
    if count > 0:
        print(f'  {coll_name}: {count} docs ({coll_elapsed:.1f}s)')

print(f'\nTotal docs across {len(per_collection)} collections: {total_docs}')

# Check current index size
current_index = 0
for _ in db.collection('librarian_index').stream():
    current_index += 1
print(f'Current librarian_index size: {current_index}')

# ═══════════════════════════════════════════
# STEP 2: Rebuild (if not dry run)
# ═══════════════════════════════════════════
if not DRY_RUN:
    print('\n' + '=' * 60)
    print('WRITING INDEX...')
    print('=' * 60)

    batch = db.batch()
    batch_count = 0
    errors = 0
    written = 0

    for coll_name, field_config in COLLECTION_FIELDS.items():
        if per_collection.get(coll_name, 0) <= 0:
            continue

        coll_count = 0
        try:
            for doc in db.collection(coll_name).stream():
                data = doc.to_dict()
                index_entry = _build_index_entry(doc.id, coll_name, data, field_config)
                index_id = f"{coll_name}__{doc.id}"
                ref = db.collection('librarian_index').document(index_id)
                batch.set(ref, index_entry, merge=True)
                batch_count += 1
                coll_count += 1
                written += 1

                if batch_count >= 100:
                    batch.commit()
                    batch = db.batch()
                    batch_count = 0

        except Exception as e:
            print(f'  ERROR indexing {coll_name}: {e}')
            errors += 1

        if coll_count > 0:
            print(f'  Indexed {coll_count} from {coll_name}')

    if batch_count > 0:
        batch.commit()

    elapsed = time.time() - start

    print(f'\n{"=" * 60}')
    print('REBUILD COMPLETE')
    print(f'{"=" * 60}')
    print(f'Written: {written} index entries')
    print(f'Errors: {errors}')
    print(f'Duration: {elapsed:.1f}s')

    # Verify
    final_count = 0
    for _ in db.collection('librarian_index').stream():
        final_count += 1
    print(f'Final librarian_index count: {final_count}')

else:
    print(f'\n*** DRY RUN — no writes. Run with --write to rebuild. ***')
    print(f'Expected new index entries: ~{total_docs}')
