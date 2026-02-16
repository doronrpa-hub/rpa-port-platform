"""
Parse Tariff Chapters into Structured Notes for AI Classification.
Assignment 9 — Session 27.

Reality check: tariff_chapters has NO chapter preamble/notes/exclusions.
The `content` field is just the scraped search page UI.

What we DO have:
- tariff_chapters: chapter name, description, headings list, HS codes
- tariff: 11,753 HS codes with heading descriptions, duty rates

Strategy: Build chapter_notes by grouping tariff entries into a heading tree
with Hebrew descriptions. This gives the AI a structured reference to classify against.
"""
import firebase_admin
from firebase_admin import credentials, firestore
import sys
import os
import re
from collections import defaultdict
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\Users\doron\Desktop\doronrpa\firebase-credentials.json'

if not firebase_admin._apps:
    cred = credentials.Certificate(r'C:\Users\doron\Desktop\doronrpa\firebase-credentials.json')
    firebase_admin.initialize_app(cred, {'projectId': 'rpa-port-customs'})

db = firestore.client()

WRITE_MODE = True

# ═══════════════════════════════════════════════════════════════
# STEP 1: Load all tariff data, group by chapter
# ═══════════════════════════════════════════════════════════════
print("Loading tariff collection (11,753 docs)...")
tariff_by_chapter = defaultdict(list)
tariff_count = 0

for doc in db.collection('tariff').stream():
    data = doc.to_dict()
    chapter = data.get('chapter')
    if chapter is None:
        continue
    chapter_str = str(int(chapter)).zfill(2) if isinstance(chapter, (int, float)) else str(chapter).zfill(2)
    tariff_by_chapter[chapter_str].append({
        'hs_code': data.get('hs_code', ''),
        'hs_formatted': data.get('hs_code_formatted', ''),
        'heading': data.get('heading', ''),
        'parent_heading_desc': data.get('parent_heading_desc', ''),
        'description_he': data.get('description_he', ''),
        'customs_duty': data.get('customs_duty', ''),
        'customs_duty_pct': data.get('customs_duty_pct', -1),
        'purchase_tax': data.get('purchase_tax', ''),
        'purchase_tax_pct': data.get('purchase_tax_pct', -1),
        'tags': data.get('tags', []),
        'unit': data.get('unit', ''),
    })
    tariff_count += 1

print(f"Loaded {tariff_count} tariff entries across {len(tariff_by_chapter)} chapters")

# ═══════════════════════════════════════════════════════════════
# STEP 2: Load tariff_chapters metadata
# ═══════════════════════════════════════════════════════════════
print("\nLoading tariff_chapters metadata...")
chapter_meta = {}
for doc in db.collection('tariff_chapters').stream():
    doc_id = doc.id
    if not doc_id.startswith('import_chapter_'):
        continue
    data = doc.to_dict()
    ch_num = doc_id.replace('import_chapter_', '').zfill(2)
    chapter_meta[ch_num] = {
        'chapterName': data.get('chapterName', ''),
        'chapterDescription': data.get('chapterDescription', ''),
        'headings': data.get('headings', []),
        'hsCodeCount': data.get('hsCodeCount', 0),
        'hsCodes': data.get('hsCodes', []),
    }

print(f"Loaded {len(chapter_meta)} chapter metadata docs")

# ═══════════════════════════════════════════════════════════════
# STEP 3: Build structured chapter notes
# ═══════════════════════════════════════════════════════════════
print("\nBuilding chapter notes...")
chapter_notes = {}

for ch_num in sorted(set(list(tariff_by_chapter.keys()) + list(chapter_meta.keys()))):
    meta = chapter_meta.get(ch_num, {})
    entries = tariff_by_chapter.get(ch_num, [])

    # Build heading tree: heading code -> {desc, subheadings}
    heading_tree = {}
    for entry in entries:
        h = entry['heading']
        if h not in heading_tree:
            heading_tree[h] = {
                'code': h,
                'description_he': entry['parent_heading_desc'],
                'subheadings': [],
            }
        desc_he = entry['description_he']
        if desc_he and desc_he != entry['parent_heading_desc']:
            heading_tree[h]['subheadings'].append({
                'hs_code': entry['hs_formatted'] or entry['hs_code'],
                'description_he': desc_he,
                'duty': entry['customs_duty'],
                'duty_pct': entry['customs_duty_pct'],
            })

    # Build duty rate summary
    duty_rates = defaultdict(int)
    for entry in entries:
        duty = entry['customs_duty']
        if duty:
            duty_rates[duty] += 1

    # Build heading summary for AI (concise, Hebrew)
    heading_lines = []
    for h_code in sorted(heading_tree.keys()):
        h = heading_tree[h_code]
        desc = h['description_he']
        sub_count = len(h['subheadings'])
        heading_lines.append(f"{h_code}: {desc} ({sub_count} פרטי משנה)")

    # Collect all unique tags (keywords)
    all_tags = set()
    for entry in entries:
        for tag in entry.get('tags', []):
            if tag and not tag.startswith('פרק'):
                all_tags.add(tag)

    chapter_notes[ch_num] = {
        'chapter_number': ch_num,
        'chapter_title_he': meta.get('chapterName', f'פרק {ch_num}'),
        'chapter_description_he': meta.get('chapterDescription', ''),
        'headings_count': len(heading_tree),
        'hs_codes_count': len(entries),
        'headings': [
            {
                'code': h['code'],
                'description_he': h['description_he'],
                'subheading_count': len(h['subheadings']),
                'subheadings': h['subheadings'][:20],  # Cap per heading
            }
            for h in [heading_tree[k] for k in sorted(heading_tree.keys())]
        ][:50],  # Cap total headings
        'heading_summary': '\n'.join(heading_lines),
        'duty_rates_summary': dict(duty_rates),
        'keywords': sorted(list(all_tags))[:100],
        'source': 'tariff + tariff_chapters',
    }

print(f"Built {len(chapter_notes)} chapter notes")

# ═══════════════════════════════════════════════════════════════
# STEP 4: DRY RUN REPORT
# ═══════════════════════════════════════════════════════════════
print('\n' + '=' * 60)
print('DRY RUN REPORT')
print('=' * 60)

has_headings = sum(1 for cn in chapter_notes.values() if cn['headings_count'] > 0)
has_keywords = sum(1 for cn in chapter_notes.values() if cn['keywords'])

print(f'Chapters: {len(chapter_notes)}')
print(f'  With headings: {has_headings}')
print(f'  With keywords: {has_keywords}')

# Show 3 samples
for ch in ['01', '39', '84']:
    cn = chapter_notes.get(ch)
    if cn:
        print(f'\n--- Chapter {ch}: {cn["chapter_title_he"]} ---')
        print(f'  Headings: {cn["headings_count"]}')
        print(f'  HS codes: {cn["hs_codes_count"]}')
        print(f'  Keywords: {len(cn["keywords"])} ({", ".join(cn["keywords"][:5])}...)')
        print(f'  Duty rates: {cn["duty_rates_summary"]}')
        print(f'  Heading summary (first 3):')
        for line in cn['heading_summary'].split('\n')[:3]:
            print(f'    {line}')

# ═══════════════════════════════════════════════════════════════
# STEP 5: WRITE TO chapter_notes COLLECTION
# ═══════════════════════════════════════════════════════════════
if WRITE_MODE:
    now_iso = datetime.now(timezone.utc).isoformat()
    written = 0
    errors = 0

    for ch_num, cn in chapter_notes.items():
        doc_id = f'chapter_{ch_num}'
        try:
            doc_data = {
                'chapter_number': cn['chapter_number'],
                'chapter_title_he': cn['chapter_title_he'],
                'chapter_description_he': cn['chapter_description_he'],
                'headings_count': cn['headings_count'],
                'hs_codes_count': cn['hs_codes_count'],
                'headings': cn['headings'],
                'heading_summary': cn['heading_summary'],
                'duty_rates_summary': cn['duty_rates_summary'],
                'keywords': cn['keywords'],
                'preamble': '',  # Not available in scraped data
                'notes': [],     # Not available in scraped data
                'exclusions': [],  # Not available in scraped data
                'inclusions': [],  # Not available in scraped data
                'has_legal_notes': False,
                'source': cn['source'],
                'parsed_at': now_iso,
            }
            db.collection('chapter_notes').document(doc_id).set(doc_data)
            written += 1
        except Exception as e:
            print(f'  Error writing {doc_id}: {e}')
            errors += 1

    print('\n' + '=' * 60)
    print('WRITE COMPLETE')
    print('=' * 60)
    print(f'Written: {written} docs to chapter_notes')
    print(f'Errors: {errors}')

    # Verify
    count = 0
    for _ in db.collection('chapter_notes').stream():
        count += 1
    print(f'Final chapter_notes count: {count}')
else:
    print('\n*** DRY RUN — no writes performed ***')
