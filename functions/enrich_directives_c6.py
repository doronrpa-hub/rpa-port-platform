"""
Block C6: Enrich 218 classification directives in Firestore.

The pipeline downloaded all directives from shaarolami but the Gemini structurer
failed to extract key fields. The full_text follows a consistent template, so we
can extract everything via regex — no AI cost.

Extracts per doc:
  - directive_id (e.g., "025/97")
  - title (e.g., "04.06 גבינה מוצרלה")
  - directive_type (e.g., "הנחיה לפרט מכס")
  - primary_hs_code (the main HS code)
  - date_opened, date_published, date_expires
  - related_hs_codes (additional HS codes the directive covers)
  - content (the actual ruling text, after תוכן הנחיה)
  - summary (first 300 chars of content — a real summary, not full_text copy)

Safety:
  - Uses set(merge=True) — ADD only, never destroys existing fields
  - Tags with enriched_by: "c6_enrich"
  - Batched writes (200 per batch)

Run: python -X utf8 enrich_directives_c6.py [--test]
"""
import sys
import os
import re
from datetime import datetime, timezone

os.environ["GOOGLE_CLOUD_PROJECT"] = "rpa-port-customs"

import firebase_admin
from firebase_admin import credentials, firestore

# ── Firebase init ──
SA_PATHS = [
    r"C:\Users\User\Downloads\rpa-port-customs-firebase-adminsdk-fbsvc-da5df22d32.json",
    r"C:\Users\doron\sa-key.json",
]

try:
    app = firebase_admin.get_app()
except ValueError:
    sa_path = next((p for p in SA_PATHS if os.path.exists(p)), None)
    if not sa_path:
        print("ERROR: No service account key found")
        sys.exit(1)
    cred = credentials.Certificate(sa_path)
    app = firebase_admin.initialize_app(cred)

db = firestore.client()

NOW = datetime.now(timezone.utc).isoformat()
SOURCE = "c6_enrich"
COLLECTION = "classification_directives"


def parse_directive(full_text):
    """Extract structured fields from directive full_text using regex."""
    result = {}

    # directive_id: after "הנחיית סיווג\n"
    m = re.search(r'הנחיית סיווג\s*\n\s*(\d{1,3}/\d{2,4})', full_text)
    if m:
        result["directive_id"] = m.group(1).strip()

    # title: after "שם הנחיה:\n"
    m = re.search(r'שם הנחיה:\s*\n\s*(.+?)(?:\n|$)', full_text)
    if m:
        result["title"] = m.group(1).strip()

    # directive_type: after "סוג הנחיה:\n"
    m = re.search(r'סוג הנחיה:\s*\n\s*(.+?)(?:\n|$)', full_text)
    if m:
        result["directive_type"] = m.group(1).strip()

    # primary_hs_code: after "חלק/פרק/פרט מכס:\n"
    m = re.search(r'חלק/פרק/פרט מכס:\s*\n[\s\u200e]*(\d{4,10})', full_text)
    if m:
        raw_hs = m.group(1).strip()
        # Format as XX.XX.XXXXXX
        if len(raw_hs) >= 4:
            result["primary_hs_code"] = f"{raw_hs[:2]}.{raw_hs[2:4]}.{raw_hs[4:]}" if len(raw_hs) > 4 else f"{raw_hs[:2]}.{raw_hs[2:4]}"

    # date_opened: after "תאריך פתיחה:\n"
    m = re.search(r'תאריך פתיחה:\s*\n\s*(\d{1,2}/\d{1,2}/\d{2,4})', full_text)
    if m:
        result["date_opened"] = _parse_date(m.group(1))

    # date_published: after "תאריך פרסום:\n"
    m = re.search(r'תאריך פרסום:\s*\n\s*(\d{1,2}/\d{1,2}/\d{2,4})', full_text)
    if m:
        result["date_published"] = _parse_date(m.group(1))

    # date_expires: after "תאריך סיום תוקף:\n"
    m = re.search(r'תאריך סיום תוקף:\s*\n\s*(\d{1,2}/\d{1,2}/\d{2,4})', full_text)
    if m:
        result["date_expires"] = _parse_date(m.group(1))

    # related_hs_codes: after "הנחיה זו מתייחסת גם לפרטים הבאים\n"
    m = re.search(r'הנחיה זו מתייחסת גם לפרטים הבאים\s*\n(.+?)(?:\nתוכן הנחיה)', full_text, re.DOTALL)
    if m:
        raw = m.group(1)
        related = re.findall(r'(\d{4,10})', raw)
        if related:
            result["related_hs_codes"] = [
                f"{h[:2]}.{h[2:4]}.{h[4:]}" if len(h) > 4 else f"{h[:2]}.{h[2:4]}"
                for h in related
            ]

    # content: after "תוכן הנחיה\n"
    m = re.search(r'תוכן הנחיה\s*\n(.+)', full_text, re.DOTALL)
    if m:
        content = m.group(1).strip()
        # Remove footer junk
        content = re.sub(r'\n\s*רשות המסים בישראל.*$', '', content, flags=re.DOTALL)
        content = re.sub(r'\n\s*\d+\s*$', '', content)  # trailing numbers
        content = content.strip()
        result["content"] = content
        # Real summary: first 300 chars of content, cleaned
        summary_text = re.sub(r'\s+', ' ', content)[:300].strip()
        if summary_text:
            result["summary_clean"] = summary_text

    # is_active: based on expiry date
    if result.get("date_expires"):
        try:
            exp = datetime.strptime(result["date_expires"], "%Y-%m-%d")
            result["is_active"] = exp.year >= 2026
        except ValueError:
            result["is_active"] = True
    else:
        result["is_active"] = True

    return result


def _parse_date(date_str):
    """Parse DD/MM/YYYY to YYYY-MM-DD."""
    try:
        parts = date_str.split("/")
        if len(parts) == 3:
            d, m, y = parts
            if len(y) == 2:
                y = "19" + y if int(y) > 50 else "20" + y
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    except Exception:
        pass
    return date_str


def enrich_all(test_mode=False):
    """Read all 218 docs, parse, and enrich with missing fields."""
    print(f"Block C6: Enriching {COLLECTION} — extracting structured fields from full_text")

    docs = list(db.collection(COLLECTION).stream())
    print(f"  Total docs: {len(docs)}")

    batch = db.batch()
    enriched = 0
    skipped = 0
    failed = 0
    stats = {
        "has_directive_id": 0,
        "has_title": 0,
        "has_content": 0,
        "has_dates": 0,
        "has_related_hs": 0,
    }

    for doc in docs:
        data = doc.to_dict()
        full_text = data.get("full_text", "")
        if not full_text:
            skipped += 1
            continue

        parsed = parse_directive(full_text)
        if not parsed.get("directive_id") and not parsed.get("title"):
            failed += 1
            continue

        # Build update payload — only add fields, never remove
        update = {}
        if parsed.get("directive_id") and not data.get("directive_id"):
            update["directive_id"] = parsed["directive_id"]
            stats["has_directive_id"] += 1
        if parsed.get("title") and not data.get("title"):
            update["title"] = parsed["title"]
            stats["has_title"] += 1
        if parsed.get("directive_type"):
            update["directive_type"] = parsed["directive_type"]
        if parsed.get("primary_hs_code"):
            update["primary_hs_code"] = parsed["primary_hs_code"]
        if parsed.get("date_opened"):
            update["date_opened"] = parsed["date_opened"]
            stats["has_dates"] += 1
        if parsed.get("date_published"):
            update["date_published"] = parsed["date_published"]
        if parsed.get("date_expires"):
            update["date_expires"] = parsed["date_expires"]
        if parsed.get("related_hs_codes"):
            update["related_hs_codes"] = parsed["related_hs_codes"]
            stats["has_related_hs"] += 1
        if parsed.get("content"):
            update["content"] = parsed["content"]
            stats["has_content"] += 1
        if parsed.get("summary_clean"):
            update["summary"] = parsed["summary_clean"]
        if "is_active" in parsed:
            update["is_active"] = parsed["is_active"]

        update["enriched_by"] = SOURCE
        update["enriched_at"] = NOW

        if update:
            ref = db.collection(COLLECTION).document(doc.id)
            batch.set(ref, update, merge=True)
            enriched += 1

            if enriched % 200 == 0:
                if not test_mode:
                    batch.commit()
                batch = db.batch()
                print(f"    Committed {enriched}...")

    # Final batch
    if enriched % 200 != 0:
        if not test_mode:
            batch.commit()

    print(f"\n  --- Results ---")
    print(f"  Enriched: {enriched}")
    print(f"  Skipped (no full_text): {skipped}")
    print(f"  Failed (no directive_id/title): {failed}")
    print(f"  Stats: {stats}")

    # Update librarian_index for enriched docs
    if not test_mode and enriched > 0:
        print(f"\n  --- Re-indexing enriched docs ---")
        reindex_count = reindex_enriched()
        print(f"  Re-indexed: {reindex_count}")

    return enriched


def reindex_enriched():
    """Re-index enriched classification_directives in librarian_index."""
    batch = db.batch()
    count = 0

    for doc in db.collection(COLLECTION).stream():
        data = doc.to_dict()
        if data.get("enriched_by") != SOURCE:
            continue

        title = data.get("title", "")
        directive_id = data.get("directive_id", "")
        summary = data.get("summary", "")

        index_entry = {
            "collection": COLLECTION,
            "doc_id": doc.id,
            "doc_type": "document",
            "title": (title or summary or doc.id)[:200],
            "directive_id": directive_id,
            "source": SOURCE,
            "indexed_at": NOW,
        }

        ref = db.collection("librarian_index").document(f"cd_{doc.id}")
        batch.set(ref, index_entry, merge=True)
        count += 1

        if count % 500 == 0:
            batch.commit()
            batch = db.batch()

    if count % 500 != 0:
        batch.commit()

    return count


def main():
    test_mode = "--test" in sys.argv
    if test_mode:
        print("=== TEST MODE ===")

    enriched = enrich_all(test_mode)

    print(f"\n=== DONE ===")
    print(f"  Total enriched: {enriched}")
    if test_mode:
        print("  (TEST MODE — nothing written)")


if __name__ == "__main__":
    main()
