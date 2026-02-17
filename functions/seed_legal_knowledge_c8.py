"""
Block C8: Seed legal_knowledge collection — Customs Ordinance chapters,
Customs Agents Law, EU/US mutual recognition reforms, export order legal text.

Sources:
  1. legal_documents/pkudat_mechess — 272K chars, Customs Ordinance (פקודת המכס)
  2. legal_documents/tzo_yetzu_hofshi — 20K chars, Free Export Order legal text
  3. EU standards reform (מה שטוב לאירופה) — reference doc
  4. US standards reform (מה שטוב לארצות הברית) — reference doc

Writes to Firestore:
  1. legal_knowledge/ordinance_ch_{num} — parsed Customs Ordinance chapters
  2. legal_knowledge/customs_agents_law — extracted customs agents law references
  3. legal_knowledge/reform_eu_standards — EU mutual recognition reform
  4. legal_knowledge/reform_us_standards — US mutual recognition reform
  5. legal_knowledge/export_order_legal_text — export order legal text
  6. legal_knowledge/_metadata — collection summary
  7. librarian_index/lk_{doc_id} — index entries

Safety:
  - Uses set(merge=True) — ADD only
  - Batched writes

Run: python -X utf8 seed_legal_knowledge_c8.py [--test]
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
SOURCE = "legal_knowledge_c8"
COLLECTION = "legal_knowledge"

# Customs Ordinance chapter definitions (ordered)
ORDINANCE_CHAPTERS = [
    ("ראשון", 1, "מבוא", "Introduction — definitions and general provisions"),
    ("שני", 2, "מינהל", "Administration — customs authority organization"),
    ("שלישי", 3, "פיקוח, בדיקה, הצהרות וערובה", "Supervision, inspection, declarations and bonds"),
    ("רביעי", 4, "ייבוא טובין", "Import of goods"),
    ("חמישי", 5, "החסנת טובין", "Warehousing of goods"),
    ("ששי", 6, "ייצוא טובין", "Export of goods"),
    ("שביעי", 7, "צידת אניה", "Ship provisioning"),
    ("שמיני", 8, "תשלומי מכס", "Customs payments — valuation, assessment, appeals"),
    ("תשיעי", 9, "הישבון וכניסה זמנית", "Drawback and temporary admission"),
    ("עשירי", 10, "סחר החוף", "Coastal trade"),
    ("אחד עשר", 11, "סוכנים", "Agents — customs agents and brokers"),
    ("שנים עשר", 12, "סמכויותיהם של פקידי-מכס", "Powers of customs officers"),
    ("שלושה עשר", 13, "חילוטין ועונשין", "Forfeitures and penalties"),
    ("ארבעה עשר", 14, "אישומי מכס", "Customs charges and electronic reporting"),
    ("חמישה עשר", 15, "הוראות שונות", "Miscellaneous provisions"),
]


def parse_ordinance_chapters(content):
    """Parse the Customs Ordinance into chapters by splitting on פרק headers."""
    chapters = []

    # Clean HTML artifacts
    content = re.sub(r'<[^>]+>', ' ', content)
    content = re.sub(r'&nbsp;', ' ', content)

    for i, (heb_num, num, title_he, title_en) in enumerate(ORDINANCE_CHAPTERS):
        # Pattern: פרק {hebrew_number}: {title}
        pattern = rf'פרק\s+{re.escape(heb_num)}(?:\s*[-–:])?\s*{re.escape(title_he)}'
        matches = list(re.finditer(pattern, content))

        if not matches:
            # Try looser pattern
            pattern2 = rf'פרק\s+{re.escape(heb_num)}'
            matches = list(re.finditer(pattern2, content))

        if matches:
            # Get text from first match to next chapter (or end)
            start = matches[0].start()

            # Find next chapter start
            end = len(content)
            if i + 1 < len(ORDINANCE_CHAPTERS):
                next_heb = ORDINANCE_CHAPTERS[i + 1][0]
                next_title = ORDINANCE_CHAPTERS[i + 1][2]
                next_pattern = rf'פרק\s+{re.escape(next_heb)}(?:\s*[-–:])?\s*{re.escape(next_title)}'
                next_matches = list(re.finditer(next_pattern, content[start + 100:]))
                if not next_matches:
                    next_pattern2 = rf'פרק\s+{re.escape(next_heb)}'
                    next_matches = list(re.finditer(next_pattern2, content[start + 100:]))
                if next_matches:
                    end = start + 100 + next_matches[0].start()

            chapter_text = content[start:end].strip()
            # Clean excessive whitespace
            chapter_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', chapter_text)
            chapter_text = re.sub(r' +', ' ', chapter_text)

            # Extract section numbers mentioned
            section_nums = sorted(set(re.findall(r'סעיף\s+(\d+[א-ת]?)', chapter_text)))

            chapters.append({
                "chapter_number": num,
                "chapter_heb_number": heb_num,
                "title_he": title_he,
                "title_en": title_en,
                "text": chapter_text[:15000],  # Cap at 15K chars per chapter
                "text_length": len(chapter_text),
                "sections_mentioned": section_nums[:50],
                "sections_count": len(section_nums),
            })
        else:
            print(f"  WARNING: Chapter {num} ({heb_num}) not found in text")

    return chapters


def extract_customs_agents_sections(content):
    """Extract sections specifically about customs agents (סוכני מכס)."""
    # Find chapter 11 (סוכנים) and surrounding context
    pattern = r'פרק\s+אחד עשר(?:\s*[-–:])?\s*סוכנים'
    match = re.search(pattern, content)

    if not match:
        return None

    # Get chapter 11 text (until chapter 12)
    start = match.start()
    next_ch = re.search(r'פרק\s+שנים עשר', content[start + 100:])
    end = start + 100 + next_ch.start() if next_ch else start + 20000

    ch11_text = content[start:end].strip()
    ch11_text = re.sub(r'<[^>]+>', ' ', ch11_text)
    ch11_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', ch11_text)
    ch11_text = re.sub(r' +', ' ', ch11_text)

    # Also find all references to חוק סוכני המכס throughout the ordinance
    clean = re.sub(r'<[^>]+>', ' ', content)
    agent_refs = []
    for m in re.finditer(r'חוק סוכני המכס[^.]{0,200}\.', clean):
        agent_refs.append(m.group().strip()[:300])

    return {
        "chapter_11_text": ch11_text[:10000],
        "chapter_11_length": len(ch11_text),
        "law_references": agent_refs[:10],
        "law_name_he": "חוק סוכני המכס, התשכ\"ה-1964",
        "law_name_en": "Customs Agents Law, 1964",
        "key_topics": [
            "רישוי סוכני מכס",
            "חובות סוכני מכס",
            "משלחים בינלאומיים",
            "עמילי מכס",
            "ייפוי כוח",
            "אחריות סוכן מכס",
        ],
    }


def build_reform_docs():
    """Create reference docs for EU and US standards mutual recognition reforms."""
    eu_reform = {
        "type": "reform",
        "reform_name_he": "מה שטוב לאירופה טוב לישראל",
        "reform_name_en": "What's Good for Europe is Good for Israel",
        "description_he": (
            "רפורמה להכרה הדדית בתקנים בין ישראל לאיחוד האירופי. "
            "מוצרים העומדים בתקני האיחוד האירופי (CE marking) יכולים להיכנס לישראל "
            "ללא בדיקות נוספות של מכון התקנים הישראלי. "
            "הרפורמה מכסה מגוון קטגוריות מוצרים כולל ציוד חשמלי, צעצועים, "
            "ציוד רפואי, מוצרי בנייה ועוד."
        ),
        "description_en": (
            "Mutual recognition reform between Israel and the EU. "
            "Products meeting EU standards (CE marking) can enter Israel "
            "without additional testing by the Standards Institution of Israel (SII). "
            "Covers various product categories including electrical equipment, toys, "
            "medical devices, construction products, and more."
        ),
        "legal_basis": [
            "החלטת ממשלה 2118 מיום 22.10.2014",
            "צו יבוא חופשי — הכרה בתקני CE",
            "תקנות התקנים (יבוא טובין מהאיחוד האירופי)",
        ],
        "impact_on_classification": (
            "מוצרים עם סימון CE מאירופה עשויים לא לדרוש אישור מכון תקנים. "
            "יש לבדוק בצו יבוא חופשי אם הקטגוריה מכוסה ברפורמה."
        ),
        "relevant_authorities": ["מכון התקנים הישראלי", "משרד הכלכלה"],
        "relevant_appendices": ["תוספת 2 לצו יבוא חופשי"],
        "effective_since": "2014",
    }

    us_reform = {
        "type": "reform",
        "reform_name_he": "מה שטוב לארצות הברית טוב לישראל",
        "reform_name_en": "What's Good for the USA is Good for Israel",
        "description_he": (
            "רפורמה להכרה הדדית בתקנים בין ישראל לארצות הברית. "
            "מוצרים העומדים בתקנים אמריקאיים (UL, FDA, CPSC) יכולים להיכנס לישראל "
            "ללא בדיקות נוספות של מכון התקנים הישראלי. "
            "הרפורמה מכסה קטגוריות דומות לרפורמת האיחוד האירופי."
        ),
        "description_en": (
            "Mutual recognition reform between Israel and the USA. "
            "Products meeting US standards (UL, FDA, CPSC certifications) can enter Israel "
            "without additional SII testing. "
            "Covers similar product categories as the EU reform."
        ),
        "legal_basis": [
            "החלטת ממשלה 4440 מיום 22.1.2019",
            "צו יבוא חופשי — הכרה בתקנים אמריקאיים",
            "תקנות התקנים (יבוא טובין מארצות הברית)",
        ],
        "impact_on_classification": (
            "מוצרים עם אישור UL/FDA/CPSC מארה\"ב עשויים לא לדרוש אישור מכון תקנים. "
            "יש לבדוק בצו יבוא חופשי אם הקטגוריה מכוסה ברפורמה."
        ),
        "relevant_authorities": ["מכון התקנים הישראלי", "משרד הכלכלה"],
        "relevant_appendices": ["תוספת 2 לצו יבוא חופשי"],
        "effective_since": "2019",
    }

    return eu_reform, us_reform


def seed_all(test_mode=False):
    """Seed all legal knowledge docs."""
    print(f"Block C8: Seeding {COLLECTION}")

    # ── Step 1: Load Customs Ordinance ──
    print(f"\n--- Step 1: Loading Customs Ordinance ---")
    doc = db.collection("legal_documents").document("pkudat_mechess").get()
    if not doc.exists:
        print("  ERROR: pkudat_mechess not found")
        return 0
    ordinance_text = doc.to_dict().get("content", "")
    print(f"  Loaded: {len(ordinance_text)} chars")

    # ── Step 2: Parse chapters ──
    print(f"\n--- Step 2: Parsing Customs Ordinance chapters ---")
    chapters = parse_ordinance_chapters(ordinance_text)
    print(f"  Parsed {len(chapters)} chapters")
    for ch in chapters:
        print(f"    Ch {ch['chapter_number']}: {ch['title_he']} ({ch['text_length']} chars, {ch['sections_count']} sections)")

    # ── Step 3: Extract customs agents law ──
    print(f"\n--- Step 3: Extracting customs agents law ---")
    agents_data = extract_customs_agents_sections(ordinance_text)
    if agents_data:
        print(f"  Chapter 11 text: {agents_data['chapter_11_length']} chars")
        print(f"  Law references: {len(agents_data['law_references'])}")
    else:
        print("  WARNING: Customs agents chapter not found")

    # ── Step 4: Build reform docs ──
    print(f"\n--- Step 4: Building reform reference docs ---")
    eu_reform, us_reform = build_reform_docs()
    print(f"  EU reform: {eu_reform['reform_name_en']}")
    print(f"  US reform: {us_reform['reform_name_en']}")

    # ── Step 5: Load export order legal text ──
    print(f"\n--- Step 5: Loading export order legal text ---")
    export_doc = db.collection("legal_documents").document("tzo_yetzu_hofshi").get()
    export_text = ""
    if export_doc.exists:
        export_text = export_doc.to_dict().get("content", "")
        print(f"  Loaded: {len(export_text)} chars")
    else:
        print("  WARNING: tzo_yetzu_hofshi not found")

    # ── Step 6: Seed Firestore ──
    print(f"\n--- Step 6: Seeding Firestore ---")
    batch = db.batch()
    count = 0

    # Ordinance chapters
    for ch in chapters:
        doc_id = f"ordinance_ch_{str(ch['chapter_number']).zfill(2)}"
        doc_data = {
            "type": "ordinance_chapter",
            "chapter_number": ch["chapter_number"],
            "chapter_heb_number": ch["chapter_heb_number"],
            "title_he": ch["title_he"],
            "title_en": ch["title_en"],
            "text": ch["text"],
            "text_length": ch["text_length"],
            "sections_mentioned": ch["sections_mentioned"],
            "sections_count": ch["sections_count"],
            "law_name_he": "פקודת המכס [נוסח חדש]",
            "law_name_en": "Customs Ordinance [New Version]",
            "source": SOURCE,
            "seeded_at": NOW,
        }
        ref = db.collection(COLLECTION).document(doc_id)
        batch.set(ref, doc_data, merge=True)
        count += 1

    # Customs agents law
    if agents_data:
        doc_data = {
            "type": "customs_agents_law",
            **agents_data,
            "source": SOURCE,
            "seeded_at": NOW,
        }
        ref = db.collection(COLLECTION).document("customs_agents_law")
        batch.set(ref, doc_data, merge=True)
        count += 1

    # EU reform
    eu_data = {**eu_reform, "source": SOURCE, "seeded_at": NOW}
    ref = db.collection(COLLECTION).document("reform_eu_standards")
    batch.set(ref, eu_data, merge=True)
    count += 1

    # US reform
    us_data = {**us_reform, "source": SOURCE, "seeded_at": NOW}
    ref = db.collection(COLLECTION).document("reform_us_standards")
    batch.set(ref, us_data, merge=True)
    count += 1

    # Export order legal text
    if export_text:
        export_data = {
            "type": "legal_text",
            "law_name_he": "צו יצוא חופשי",
            "law_name_en": "Free Export Order",
            "text": export_text[:50000],
            "text_length": len(export_text),
            "source": SOURCE,
            "seeded_at": NOW,
        }
        ref = db.collection(COLLECTION).document("export_order_legal_text")
        batch.set(ref, export_data, merge=True)
        count += 1

    if not test_mode:
        batch.commit()
    print(f"  Committed {count} docs")

    # Metadata
    if not test_mode:
        meta = {
            "collection": COLLECTION,
            "source": SOURCE,
            "description": "Legal knowledge: Customs Ordinance chapters, customs agents law, standards reforms, export order",
            "ordinance_chapters": len(chapters),
            "has_customs_agents_law": agents_data is not None,
            "has_eu_reform": True,
            "has_us_reform": True,
            "has_export_order_text": bool(export_text),
            "total_docs": count,
            "seeded_at": NOW,
        }
        db.collection(COLLECTION).document("_metadata").set(meta, merge=True)
        print(f"  Metadata written")

    # Index
    if not test_mode:
        print(f"\n--- Step 7: Indexing ---")
        idx_count = index_all()
        print(f"  Indexed {idx_count} docs")

    return count


def index_all():
    """Index legal_knowledge in librarian_index."""
    batch = db.batch()
    count = 0

    for doc in db.collection(COLLECTION).stream():
        if doc.id.startswith("_"):
            continue
        data = doc.to_dict()

        title = (
            data.get("title_he", "") or data.get("reform_name_he", "")
            or data.get("law_name_he", "") or doc.id
        )

        index_entry = {
            "collection": COLLECTION,
            "doc_id": doc.id,
            "doc_type": data.get("type", "legal"),
            "title": title[:200],
            "source": SOURCE,
            "indexed_at": NOW,
        }

        ref = db.collection("librarian_index").document(f"lk_{doc.id}")
        batch.set(ref, index_entry, merge=True)
        count += 1

    if count > 0:
        batch.commit()
    return count


def main():
    test_mode = "--test" in sys.argv
    if test_mode:
        print("=== TEST MODE ===")

    total = seed_all(test_mode)

    print(f"\n=== DONE ===")
    print(f"  Total docs: {total}")
    if test_mode:
        print("  (TEST MODE — nothing written)")


if __name__ == "__main__":
    main()
