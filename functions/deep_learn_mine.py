"""Deep Learn: Mine existing Firestore data for knowledge collections.
Assignment 8 — Session 27.
"""
import firebase_admin
from firebase_admin import credentials, firestore
import sys
import os
import re

sys.stdout.reconfigure(encoding='utf-8')

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\Users\doron\Desktop\doronrpa\firebase-credentials.json'

if not firebase_admin._apps:
    cred = credentials.Certificate(r'C:\Users\doron\Desktop\doronrpa\firebase-credentials.json')
    firebase_admin.initialize_app(cred, {'projectId': 'rpa-port-customs'})

db = firestore.client()

HS_RE = re.compile(r'^\d{4,10}$')


def is_valid_hs(code):
    if not code or not isinstance(code, str):
        return False
    clean = code.replace('.', '').replace('/', '').replace(' ', '').strip()
    if not HS_RE.match(clean):
        return False
    try:
        return 1 <= int(clean[:2]) <= 97
    except Exception:
        return False


def clean_hs(code):
    return str(code).replace('.', '').replace('/', '').replace(' ', '').strip()


def make_key(text, max_len=100):
    """Create a safe Firestore doc ID from text."""
    key = re.sub(r'[^a-z0-9_]', '', text.lower().strip()[:max_len].replace(' ', '_'))
    return key[:100] if key else None


all_products = []
all_suppliers = []
all_knowledge = []

# ═══════════════════════════════════════════════════════════════
# SOURCE 1: rcb_classifications (GOLD — reports sent to clients)
# ═══════════════════════════════════════════════════════════════
print('=== SOURCE 1: rcb_classifications ===')
s1p = 0
s1s = 0
for doc in db.collection('rcb_classifications').stream():
    d = doc.to_dict()
    seller = d.get('seller', '')
    buyer = d.get('buyer', '')
    direction = d.get('direction', '')

    # Extract from classifications list
    cls_list = d.get('classifications', [])
    if isinstance(cls_list, list):
        for c in cls_list:
            if not isinstance(c, dict):
                continue
            hs = c.get('hs_code', '')
            desc = c.get('item_description', c.get('item', c.get('description', '')))
            if not is_valid_hs(hs):
                continue
            hs_clean = clean_hs(hs)
            if desc and len(desc) > 5:
                pkey = make_key(desc, 80)
                if pkey:
                    all_products.append({
                        'doc_id': pkey,
                        'product_description': desc[:200],
                        'hs_code': hs,
                        'confidence': 85,
                        'source': 'rcb_classifications',
                    })
                    all_knowledge.append({
                        'doc_id': f'hs_{hs_clean}',
                        'hs_code': hs,
                        'product_description': desc[:200],
                        'confidence': 85,
                        'source': 'rcb_classifications',
                    })
                    s1p += 1

    # Supplier info
    if seller and len(seller) > 3:
        skey = make_key(seller, 60)
        if skey:
            all_suppliers.append({
                'doc_id': skey,
                'name': seller[:100],
                'direction': direction,
                'source': 'rcb_classifications',
            })
            s1s += 1

print(f'  Products: {s1p}, Suppliers: {s1s}')

# ═══════════════════════════════════════════════════════════════
# SOURCE 2: rcb_silent_classifications (CC-observed)
# ═══════════════════════════════════════════════════════════════
print('\n=== SOURCE 2: rcb_silent_classifications ===')
s2p = 0
s2s = 0
for doc in db.collection('rcb_silent_classifications').stream():
    d = doc.to_dict()
    sender = d.get('from', '')

    cls_list = d.get('classifications', [])
    if isinstance(cls_list, list):
        for c in cls_list:
            if not isinstance(c, dict):
                continue
            hs = c.get('hs_code', '')
            desc = c.get('item', c.get('item_description', ''))
            if not is_valid_hs(hs):
                continue
            hs_clean = clean_hs(hs)
            if desc and len(desc) > 5:
                pkey = make_key(desc, 80)
                if pkey:
                    all_products.append({
                        'doc_id': pkey,
                        'product_description': desc[:200],
                        'hs_code': hs,
                        'confidence': 70,
                        'source': 'rcb_silent',
                    })
                    all_knowledge.append({
                        'doc_id': f'hs_{hs_clean}',
                        'hs_code': hs,
                        'product_description': desc[:200],
                        'confidence': 70,
                        'source': 'rcb_silent',
                    })
                    s2p += 1

    if sender and '@' in sender:
        skey = sender.lower().split('@')[0].replace('.', '_')[:60]
        all_suppliers.append({
            'doc_id': skey,
            'name': sender,
            'email': sender,
            'source': 'rcb_silent',
        })
        s2s += 1

print(f'  Products: {s2p}, Senders: {s2s}')

# ═══════════════════════════════════════════════════════════════
# SOURCE 3: batch_reprocess_results (683 docs, mixed quality)
# ═══════════════════════════════════════════════════════════════
print('\n=== SOURCE 3: batch_reprocess_results ===')
s3p = 0
s3s = 0
for doc in db.collection('batch_reprocess_results').stream():
    d = doc.to_dict()
    if d.get('skipped'):
        continue

    cls_list = d.get('classifications', [])
    hs_codes = d.get('hs_codes', [])
    sender = d.get('from_email', '')

    if isinstance(cls_list, list):
        for c in cls_list:
            if not isinstance(c, dict):
                continue
            hs = c.get('hs_code', '')
            desc = c.get('item', c.get('item_description', ''))
            if not is_valid_hs(hs):
                continue
            hs_clean = clean_hs(hs)
            conf_raw = c.get('confidence', '')
            conf = 60
            if conf_raw in ('high', '\u05d2\u05d1\u05d5\u05d4\u05d4'):
                conf = 85
            elif conf_raw in ('medium', '\u05d1\u05d9\u05e0\u05d5\u05e0\u05d9\u05ea'):
                conf = 70

            if desc and len(desc) > 5:
                pkey = make_key(desc, 80)
                if pkey:
                    all_products.append({
                        'doc_id': pkey,
                        'product_description': desc[:200],
                        'hs_code': hs,
                        'confidence': conf,
                        'source': 'batch_reprocess',
                    })
                    all_knowledge.append({
                        'doc_id': f'hs_{hs_clean}',
                        'hs_code': hs,
                        'product_description': desc[:200],
                        'confidence': conf,
                        'source': 'batch_reprocess',
                    })
                    s3p += 1

    valid_hs = [h for h in (hs_codes if isinstance(hs_codes, list) else []) if is_valid_hs(h)]
    if sender and '@' in sender:
        skey = sender.lower().split('@')[0].replace('.', '_')[:60]
        all_suppliers.append({
            'doc_id': skey,
            'name': sender,
            'email': sender,
            'hs_codes': valid_hs,
            'source': 'batch_reprocess',
        })
        s3s += 1

print(f'  Products: {s3p}, Senders: {s3s}')

# ═══════════════════════════════════════════════════════════════
# SOURCE 4: tracker_observations (shipping senders)
# ═══════════════════════════════════════════════════════════════
print('\n=== SOURCE 4: tracker_observations ===')
s4count = 0
s4_senders = 0
for doc in db.collection('tracker_observations').stream():
    d = doc.to_dict()
    s4count += 1
    sender = d.get('sender_email', d.get('sender', d.get('from', '')))
    if sender and '@' in str(sender):
        skey = str(sender).lower().split('@')[0].replace('.', '_')[:60]
        all_suppliers.append({
            'doc_id': skey,
            'name': str(sender),
            'email': str(sender),
            'source': 'tracker_observations',
        })
        s4_senders += 1
print(f'  Docs: {s4count}, Senders: {s4_senders}')

# ═══════════════════════════════════════════════════════════════
# SOURCE 5: contacts (email contacts)
# ═══════════════════════════════════════════════════════════════
print('\n=== SOURCE 5: contacts ===')
s5count = 0
for doc in db.collection('contacts').stream():
    d = doc.to_dict()
    s5count += 1
    email = d.get('email', d.get('email_address', ''))
    name = d.get('name', d.get('display_name', d.get('company', '')))
    if email and '@' in str(email):
        skey = str(email).lower().split('@')[0].replace('.', '_')[:60]
        all_suppliers.append({
            'doc_id': skey,
            'name': str(name)[:100] if name else str(email),
            'email': str(email),
            'source': 'contacts',
        })
print(f'  Docs: {s5count}')

# ═══════════════════════════════════════════════════════════════
# CONSOLIDATION + DEDUPLICATION
# ═══════════════════════════════════════════════════════════════
print('\n' + '=' * 60)
print('RAW EXTRACTION TOTALS')
print('=' * 60)
print(f'Products: {len(all_products)}')
print(f'Suppliers: {len(all_suppliers)}')
print(f'Knowledge: {len(all_knowledge)}')

# Deduplicate products (prefer higher confidence)
merged_products = {}
for p in all_products:
    key = p['doc_id']
    if key in merged_products:
        merged_products[key]['seen_count'] = merged_products[key].get('seen_count', 1) + 1
        if p['confidence'] > merged_products[key]['confidence']:
            merged_products[key]['confidence'] = p['confidence']
            merged_products[key]['hs_code'] = p['hs_code']
            merged_products[key]['product_description'] = p['product_description']
    else:
        p['seen_count'] = 1
        merged_products[key] = dict(p)

# Deduplicate suppliers
merged_suppliers = {}
for s in all_suppliers:
    key = s['doc_id']
    if key in merged_suppliers:
        merged_suppliers[key]['seen_count'] = merged_suppliers[key].get('seen_count', 1) + 1
        existing_hs = set(merged_suppliers[key].get('hs_codes', []))
        existing_hs.update(s.get('hs_codes', []))
        merged_suppliers[key]['hs_codes'] = list(existing_hs)
    else:
        s['seen_count'] = 1
        merged_suppliers[key] = dict(s)

# Deduplicate knowledge
merged_knowledge = {}
for k in all_knowledge:
    key = k['doc_id']
    if key in merged_knowledge:
        merged_knowledge[key]['seen_count'] = merged_knowledge[key].get('seen_count', 1) + 1
        if k['confidence'] > merged_knowledge[key]['confidence']:
            merged_knowledge[key]['confidence'] = k['confidence']
            merged_knowledge[key]['product_description'] = k.get('product_description', '')
    else:
        k['seen_count'] = 1
        merged_knowledge[key] = dict(k)

# Current collection sizes
print('\nCurrent collection sizes:')
for col in ['product_index', 'supplier_index', 'classification_knowledge']:
    count = 0
    for _ in db.collection(col).stream():
        count += 1
    print(f'  {col}: {count} docs')

print('\n' + '=' * 60)
print('CONSOLIDATED (DEDUPLICATED)')
print('=' * 60)
print(f'Unique products: {len(merged_products)}')
print(f'Unique suppliers/contacts: {len(merged_suppliers)}')
print(f'Unique knowledge entries: {len(merged_knowledge)}')

print('\n--- Top 15 products (by confidence) ---')
sorted_prods = sorted(merged_products.values(), key=lambda x: (-x['confidence'], -x.get('seen_count', 1)))
for p in sorted_prods[:15]:
    print(f'  {p["doc_id"][:45]:45s} HS={p["hs_code"]:15s} conf={p["confidence"]} seen={p["seen_count"]} src={p["source"]}')

print('\n--- Top 15 suppliers (by seen_count) ---')
sorted_supps = sorted(merged_suppliers.values(), key=lambda x: -x.get('seen_count', 1))
for s in sorted_supps[:15]:
    hs = s.get('hs_codes', [])
    print(f'  {s["doc_id"][:35]:35s} seen={s["seen_count"]:3d} hs_codes={len(hs)} name={s["name"][:35]}')

print('\n--- Top 10 knowledge entries ---')
sorted_know = sorted(merged_knowledge.values(), key=lambda x: (-x['confidence'], -x.get('seen_count', 1)))
for k in sorted_know[:10]:
    print(f'  {k["doc_id"][:25]:25s} conf={k["confidence"]} seen={k["seen_count"]} desc={k.get("product_description","")[:50]}')

# Check what already exists (to calculate net new)
existing_products = set()
for doc in db.collection('product_index').stream():
    existing_products.add(doc.id)
existing_knowledge = set()
for doc in db.collection('classification_knowledge').stream():
    existing_knowledge.add(doc.id)
existing_suppliers = set()
for doc in db.collection('supplier_index').stream():
    existing_suppliers.add(doc.id)

new_products = {k: v for k, v in merged_products.items() if k not in existing_products}
new_knowledge = {k: v for k, v in merged_knowledge.items() if k not in existing_knowledge}
new_suppliers = {k: v for k, v in merged_suppliers.items() if k not in existing_suppliers}

update_products = {k: v for k, v in merged_products.items() if k in existing_products}
update_knowledge = {k: v for k, v in merged_knowledge.items() if k in existing_knowledge}

print('\n' + '=' * 60)
print('DRY RUN - WHAT WOULD BE WRITTEN')
print('=' * 60)
print(f'product_index:')
print(f'  New docs to add: {len(new_products)}')
print(f'  Existing docs to update: {len(update_products)}')
print(f'supplier_index:')
print(f'  New docs to add: {len(new_suppliers)}')
print(f'classification_knowledge:')
print(f'  New docs to add: {len(new_knowledge)}')
print(f'  Existing docs to update: {len(update_knowledge)}')

print('\n--- New products that would be added ---')
for key, p in list(new_products.items())[:20]:
    print(f'  + {key[:45]:45s} HS={p["hs_code"]:15s} conf={p["confidence"]}')

print('\n--- New suppliers that would be added ---')
for key, s in list(new_suppliers.items())[:20]:
    print(f'  + {key[:45]:45s} name={s["name"][:40]}')

print('\n--- New knowledge that would be added ---')
for key, k in list(new_knowledge.items())[:20]:
    print(f'  + {key[:25]:25s} conf={k["confidence"]} desc={k.get("product_description","")[:50]}')

WRITE_MODE = True
FILTER_INTERNAL = True
INTERNAL_DOMAINS = {'rpa-port.co.il', 'rpa-port.com', 'h-caspi.co.il'}

if FILTER_INTERNAL:
    before = len(new_suppliers)
    filtered_suppliers = {}
    for key, s in new_suppliers.items():
        email = s.get('email', s.get('name', ''))
        domain = email.lower().split('@')[-1] if '@' in email else ''
        if domain in INTERNAL_DOMAINS:
            continue
        filtered_suppliers[key] = s
    new_suppliers = filtered_suppliers
    print(f'\nFiltered internal emails: {before} -> {len(new_suppliers)} suppliers')

if WRITE_MODE:
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    written = {'products_new': 0, 'products_updated': 0, 'suppliers': 0, 'knowledge': 0}

    # Write NEW products
    for key, p in new_products.items():
        if FILTER_INTERNAL:
            pass  # products don't need filtering
        db.collection('product_index').document(key).set({
            'product_description': p['product_description'],
            'hs_code': p['hs_code'],
            'confidence': p['confidence'],
            'seen_count': p.get('seen_count', 1),
            'source': p['source'],
            'created': now_iso,
            'mined_by': 'deep_learn_session27',
        })
        written['products_new'] += 1

    # Update EXISTING products (bump seen_count, update confidence if higher)
    for key, p in update_products.items():
        try:
            doc_ref = db.collection('product_index').document(key)
            existing = doc_ref.get()
            if existing.exists:
                ed = existing.to_dict()
                updates = {
                    'seen_count': ed.get('seen_count', 1) + p.get('seen_count', 1),
                    'last_updated': now_iso,
                }
                if p['confidence'] > ed.get('confidence', 0):
                    updates['confidence'] = p['confidence']
                doc_ref.update(updates)
                written['products_updated'] += 1
        except Exception as e:
            print(f'  Error updating product {key}: {e}')

    # Write NEW suppliers (filtered)
    for key, s in new_suppliers.items():
        db.collection('supplier_index').document(key).set({
            'name': s.get('name', ''),
            'email': s.get('email', ''),
            'hs_codes': s.get('hs_codes', []),
            'products': s.get('products', []),
            'direction': s.get('direction', ''),
            'seen_count': s.get('seen_count', 1),
            'source': s.get('source', ''),
            'created': now_iso,
            'mined_by': 'deep_learn_session27',
        })
        written['suppliers'] += 1

    # Write NEW knowledge
    for key, k in new_knowledge.items():
        db.collection('classification_knowledge').document(key).set({
            'hs_code': k['hs_code'],
            'product_description': k.get('product_description', ''),
            'confidence': k['confidence'],
            'seen_count': k.get('seen_count', 1),
            'source': k.get('source', ''),
            'created': now_iso,
            'mined_by': 'deep_learn_session27',
        })
        written['knowledge'] += 1

    print('\n' + '=' * 60)
    print('WRITE COMPLETE')
    print('=' * 60)
    print(f'product_index: {written["products_new"]} new + {written["products_updated"]} updated')
    print(f'supplier_index: {written["suppliers"]} new')
    print(f'classification_knowledge: {written["knowledge"]} new')

    # Verify final counts
    print('\nFinal collection sizes:')
    for col in ['product_index', 'supplier_index', 'classification_knowledge']:
        count = 0
        for _ in db.collection(col).stream():
            count += 1
        print(f'  {col}: {count} docs')
else:
    print('\n\n*** DRY RUN COMPLETE — NO WRITES PERFORMED ***')
