"""
Block C1: Scrape shaarolami tariff descriptions into staging collection.
One-time script. Run with: python -X utf8 scrape_shaarolami_c1.py [--test]

--test: scrape only first 3 chapters (test batch)
(no flag): scrape all 98 chapters

Writes to: shaarolami_scrape_staging (NOT production tariff)
"""
import sys
import os
import re
import time
import requests
from datetime import datetime, timezone

os.environ["GOOGLE_CLOUD_PROJECT"] = "rpa-port-customs"

import firebase_admin
from firebase_admin import credentials, firestore

try:
    app = firebase_admin.get_app()
except ValueError:
    cred = credentials.Certificate(r"C:\Users\doron\sa-key.json")
    app = firebase_admin.initialize_app(cred)

db = firestore.client()

# ── Shaarolami config ──
BASE = "https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb"
TREE_URL = f"{BASE}/he/CustomsBook/Import/FirstAddition"
CHAPTER_URL_HE = f"{BASE}/he/CustomsBook/Import/ImportCustomsItemDetails?customsItemId={{cid}}"
CHAPTER_URL_EN = f"{BASE}/en/CustomsBook/Import/ImportCustomsItemDetails?customsItemId={{cid}}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (RPA-PORT customs research)",
    "Accept": "text/html,application/xhtml+xml",
}
DELAY = 0.5  # seconds between requests

# ── Regex patterns ──
# From chapter tree: extract chapter IDs + codes
RE_CHAPTER = re.compile(
    r'customsItemId=(\d+)[^>]*>(\d{10})</span>.*?hidden-sm-inline[^>]*>([^<]+)',
    re.DOTALL,
)

# From chapter detail page: extract item code + description
# Structure: <span class="...treeLink" data-url="...customsItemId=XXX...">HSCODE</span>
#            ... <div class="...hidden-sm-inline">description</div>
RE_ITEM_CODE_DESC = re.compile(
    r'treeLink[^>]*data-url="[^"]*customsItemId=(\d+)[^"]*"[^>]*>\s*(\d{10}(?:/\d)?)\s*</span>'
    r'.*?hidden-sm-inline[^>]*>([^<]+)</div>',
    re.DOTALL,
)
# Fallback: some items have treeLink before data-url, some after
RE_ITEM_FALLBACK = re.compile(
    r'treeLink[^>]*>\s*(\d{10}(?:/\d)?)\s*</span>'
    r'.*?hidden-sm-inline[^>]*>([^<]+)</div>',
    re.DOTALL,
)


def fetch(url):
    """Fetch URL with retry."""
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            if attempt == 2:
                print(f"  FAILED after 3 attempts: {url} — {e}")
                return None
            time.sleep(2)
    return None


def get_chapter_list():
    """Fetch FirstAddition tree → list of (customsItemId, chapterCode, description)."""
    print("Fetching chapter tree...")
    # Need session cookie first
    session = requests.Session()
    session.headers.update(HEADERS)
    session.get(f"{BASE}/he/CustomsBook/Import/CustomsTaarifEntry", timeout=30)
    time.sleep(DELAY)

    html = session.get(TREE_URL, timeout=30).text
    chapters = RE_CHAPTER.findall(html)
    print(f"  Found {len(chapters)} chapters")
    return [(cid, code, desc.strip()) for cid, code, desc in chapters]


def scrape_chapter(session, cid, lang="he"):
    """Scrape one chapter page → list of (customsItemId, hsCode, description)."""
    url_tpl = CHAPTER_URL_HE if lang == "he" else CHAPTER_URL_EN
    url = url_tpl.format(cid=cid)
    try:
        resp = session.get(url, timeout=30)
        resp.encoding = "utf-8"
        html = resp.text
    except Exception as e:
        print(f" [request error: {e}]", end="")
        return []
    if not html or len(html) < 1000:
        return []

    items = RE_ITEM_CODE_DESC.findall(html)
    if items:
        return [(item_id, code.strip(), desc.strip()) for item_id, code, desc in items]
    # Fallback regex (no customsItemId capture)
    items_fb = RE_ITEM_FALLBACK.findall(html)
    return [("", code.strip(), desc.strip()) for code, desc in items_fb]


def format_hs_code(raw_code):
    """Convert 10-digit code to XX.XX.XXXXXX format, preserve /check digit."""
    # raw: 0101210000/2 or 0101210000
    check = ""
    if "/" in raw_code:
        raw_code, check = raw_code.split("/", 1)
        check = "/" + check

    digits = raw_code.replace(".", "").replace(" ", "")
    if len(digits) == 10:
        return f"{digits[0:2]}.{digits[2:4]}.{digits[4:10]}{check}"
    return raw_code + check


def main():
    test_mode = "--test" in sys.argv
    chapters = get_chapter_list()

    if test_mode:
        chapters = chapters[:3]
        print(f"TEST MODE: scraping {len(chapters)} chapters only")
    else:
        print(f"FULL MODE: scraping {len(chapters)} chapters")

    session = requests.Session()
    session.headers.update(HEADERS)
    # Warm up session
    session.get(f"{BASE}/he/CustomsBook/Import/CustomsTaarifEntry", timeout=30)

    all_items = {}  # hs_code_raw → {data}
    errors = 0

    # Phase 1: Hebrew descriptions
    print("\n── Phase 1: Hebrew descriptions ──")
    for i, (cid, ch_code, ch_desc) in enumerate(chapters):
        ch_num = ch_code[:2]
        print(f"  [{i+1}/{len(chapters)}] Chapter {ch_num}: {ch_desc[:50]}...", end="")
        time.sleep(DELAY)

        items_he = scrape_chapter(session, cid, lang="he")
        if not items_he:
            print(" EMPTY/ERROR")
            errors += 1
            continue

        for item_id, raw_code, desc_he in items_he:
            hs_formatted = format_hs_code(raw_code)
            all_items[raw_code] = {
                "hs_code_raw": raw_code,
                "hs_code_formatted": hs_formatted,
                "chapter": ch_num,
                "chapter_description": ch_desc,
                "customs_item_id": item_id,
                "description_he": desc_he,
                "description_en": "",  # filled in phase 2
            }

        print(f" {len(items_he)} items")

    # Phase 2: English descriptions
    print("\n── Phase 2: English descriptions ──")
    for i, (cid, ch_code, ch_desc) in enumerate(chapters):
        ch_num = ch_code[:2]
        print(f"  [{i+1}/{len(chapters)}] Chapter {ch_num}...", end="")
        time.sleep(DELAY)

        items_en = scrape_chapter(session, cid, lang="en")
        if not items_en:
            print(" EMPTY/ERROR")
            errors += 1
            continue

        matched = 0
        for item_id, raw_code, desc_en in items_en:
            if raw_code in all_items:
                all_items[raw_code]["description_en"] = desc_en
                matched += 1

        print(f" {matched} matched")

    # Summary
    total = len(all_items)
    with_he = sum(1 for v in all_items.values() if v["description_he"])
    with_en = sum(1 for v in all_items.values() if v["description_en"])
    print(f"\n── Summary ──")
    print(f"  Total HS codes scraped: {total}")
    print(f"  With Hebrew desc: {with_he}")
    print(f"  With English desc: {with_en}")
    print(f"  Errors: {errors}")

    # Show sample
    print(f"\n── Sample (first 10) ──")
    for i, (code, data) in enumerate(list(all_items.items())[:10]):
        print(f"  {data['hs_code_formatted']} | HE: {data['description_he'][:50]} | EN: {data['description_en'][:50]}")

    # Write to staging
    print(f"\n── Writing to shaarolami_scrape_staging ──")
    staging = db.collection("shaarolami_scrape_staging")
    written = 0
    batch = db.batch()
    batch_count = 0

    for raw_code, data in all_items.items():
        doc_id = raw_code.replace("/", "_")  # safe doc ID
        data["scraped_at"] = datetime.now(timezone.utc).isoformat()
        data["source"] = "shaarolami"
        batch.set(staging.document(doc_id), data)
        batch_count += 1
        written += 1

        if batch_count >= 400:  # Firestore batch limit is 500
            batch.commit()
            batch = db.batch()
            batch_count = 0
            print(f"  ... committed {written} so far")

    if batch_count > 0:
        batch.commit()

    print(f"  Done: {written} documents written to shaarolami_scrape_staging")
    print(f"\n  ⚠ STAGING ONLY — review before writing to production tariff collection")


if __name__ == "__main__":
    main()
