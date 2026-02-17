"""
Seed tariff_structure collection from israeli_customs_tariff_structure.xml.

Writes to Firestore:
  1. tariff_structure/ — metadata, sections, chapters, additions, special docs
  2. keyword_index/ — section + chapter names (HE+EN), weight 3, skip existing

Safety:
  - Uses update() for existing docs, set(merge=True) for new docs
  - Tags everything with source: "israeli_customs_tariff_structure.xml"
  - Never overwrites existing keyword_index entries from B2 seeding
  - Re-indexes tariff_structure in librarian_index after seeding

Run: python -X utf8 seed_tariff_structure.py [--test] [--skip-keywords]
"""
import sys
import os
import xml.etree.ElementTree as ET
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

NOW = datetime.now(timezone.utc).isoformat()
SOURCE = "israeli_customs_tariff_structure.xml"
XML_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "israeli_customs_tariff_structure.xml")

# Fallback paths
if not os.path.exists(XML_PATH):
    XML_PATH = r"C:\Users\doron\rpa-port-platform\docs\israeli_customs_tariff_structure.xml"
if not os.path.exists(XML_PATH):
    XML_PATH = r"C:\Users\doron\Downloads\israeli_customs_tariff_structure.xml"


def safe_doc_id(text):
    """Create Firestore-safe document ID."""
    return text.lower().strip().replace(" ", "_").replace("/", "_")[:100]


def parse_xml():
    """Parse the XML and return structured data."""
    tree = ET.parse(XML_PATH)
    root = tree.getroot()

    data = {
        "metadata": {},
        "full_tariff": {},
        "discount_codes": {},
        "framework_order": {},
        "sections": [],
        "additions": [],
    }

    # Metadata
    meta = root.find("metadata")
    if meta is not None:
        data["metadata"] = {
            "source": meta.findtext("source", ""),
            "source_url": meta.findtext("source_url", ""),
            "base_download_url": meta.findtext("base_download_url", ""),
            "date_captured": meta.findtext("date_captured", ""),
        }

    # Full tariff
    ft = root.find("FullTariff")
    if ft is not None:
        data["full_tariff"] = {
            "name_he": ft.findtext("name_he", ""),
            "name_en": ft.findtext("name_en", ""),
            "filename": ft.findtext("filename", ""),
            "url": ft.findtext("url", ""),
        }

    # Discount codes
    dc = root.find("DiscountCodes")
    if dc is not None:
        data["discount_codes"] = {
            "name_he": dc.findtext("name_he", ""),
            "name_en": dc.findtext("name_en", ""),
            "filename": dc.findtext("filename", ""),
            "url": dc.findtext("url", ""),
        }

    # Framework order
    fo = root.find("FrameworkOrder")
    if fo is not None:
        data["framework_order"] = {
            "name_he": fo.findtext("name_he", ""),
            "name_en": fo.findtext("name_en", ""),
            "filename": fo.findtext("filename", ""),
            "url": fo.findtext("url", ""),
        }

    # Sections
    sections_el = root.find("Sections")
    if sections_el is not None:
        for sec in sections_el.findall("Section"):
            section = {
                "number": sec.get("number", ""),
                "name_he": sec.findtext("name_he", ""),
                "name_en": sec.findtext("name_en", ""),
                "filename": sec.findtext("filename", ""),
                "url": sec.findtext("url", ""),
                "contains": sec.findtext("contains", ""),
                "chapters": [],
            }
            chapters_el = sec.find("chapters")
            if chapters_el is not None:
                for ch in chapters_el.findall("chapter"):
                    section["chapters"].append({
                        "number": ch.get("number", ""),
                        "name_he": ch.get("name_he", ""),
                        "name_en": ch.get("name_en", ""),
                    })
            data["sections"].append(section)

    # Additions
    additions_el = root.find("Additions")
    if additions_el is not None:
        for add in additions_el.findall("Addition"):
            data["additions"].append({
                "number": add.get("number", ""),
                "name_he": add.findtext("name_he", ""),
                "name_en": add.findtext("name_en", ""),
                "filename": add.findtext("filename", ""),
                "url": add.findtext("url", ""),
            })

    return data


def seed_tariff_structure(data, test_mode=False):
    """Write tariff structure to Firestore tariff_structure collection."""
    coll = db.collection("tariff_structure")
    written = 0

    # 1. Metadata doc
    print("  Writing metadata...")
    coll.document("metadata").set({
        **data["metadata"],
        "type": "metadata",
        "source": SOURCE,
        "seeded_at": NOW,
    }, merge=True)
    written += 1

    # 2. Full tariff PDF doc
    print("  Writing full_tariff...")
    coll.document("full_tariff").set({
        **data["full_tariff"],
        "type": "full_tariff",
        "source": SOURCE,
        "seeded_at": NOW,
    }, merge=True)
    written += 1

    # 3. Discount codes doc
    print("  Writing discount_codes...")
    coll.document("discount_codes").set({
        **data["discount_codes"],
        "type": "discount_codes",
        "source": SOURCE,
        "seeded_at": NOW,
    }, merge=True)
    written += 1

    # 4. Framework order doc
    print("  Writing framework_order...")
    coll.document("framework_order").set({
        **data["framework_order"],
        "type": "framework_order",
        "source": SOURCE,
        "seeded_at": NOW,
    }, merge=True)
    written += 1

    # 5. Section docs (22)
    sections_to_write = data["sections"][:3] if test_mode else data["sections"]
    print(f"  Writing {len(sections_to_write)} sections...")
    for sec in sections_to_write:
        doc_id = f"section_{sec['number']}"
        chapter_numbers = [ch["number"] for ch in sec["chapters"]]
        chapter_names = {}
        for ch in sec["chapters"]:
            chapter_names[ch["number"]] = {
                "name_he": ch["name_he"],
                "name_en": ch["name_en"],
            }

        coll.document(doc_id).set({
            "type": "section",
            "number": sec["number"],
            "name_he": sec["name_he"],
            "name_en": sec["name_en"],
            "filename": sec["filename"],
            "pdf_url": sec["url"],
            "contains": sec["contains"],
            "chapters": chapter_numbers,
            "chapter_names": chapter_names,
            "chapter_count": len(chapter_numbers),
            "source": SOURCE,
            "seeded_at": NOW,
        }, merge=True)
        written += 1

    # 6. Chapter docs (one per chapter, with section back-reference)
    all_chapters = []
    for sec in data["sections"]:
        for ch in sec["chapters"]:
            all_chapters.append({
                **ch,
                "section": sec["number"],
                "section_name_he": sec["name_he"],
                "section_name_en": sec["name_en"],
                "section_pdf_url": sec["url"],
            })

    chapters_to_write = all_chapters[:10] if test_mode else all_chapters
    print(f"  Writing {len(chapters_to_write)} chapters...")
    for ch in chapters_to_write:
        doc_id = f"chapter_{ch['number']}"
        coll.document(doc_id).set({
            "type": "chapter",
            "number": ch["number"],
            "name_he": ch["name_he"],
            "name_en": ch["name_en"],
            "section": ch["section"],
            "section_name_he": ch["section_name_he"],
            "section_name_en": ch["section_name_en"],
            "section_pdf_url": ch["section_pdf_url"],
            "source": SOURCE,
            "seeded_at": NOW,
        }, merge=True)
        written += 1

    # 7. Addition docs
    additions_to_write = data["additions"][:3] if test_mode else data["additions"]
    print(f"  Writing {len(additions_to_write)} additions...")
    for add in additions_to_write:
        doc_id = f"addition_{add['number']}"
        coll.document(doc_id).set({
            "type": "addition",
            "number": add["number"],
            "name_he": add["name_he"],
            "name_en": add["name_en"],
            "filename": add["filename"],
            "pdf_url": add["url"],
            "source": SOURCE,
            "seeded_at": NOW,
        }, merge=True)
        written += 1

    print(f"  tariff_structure: {written} docs written")
    return written


def seed_keywords(data, test_mode=False):
    """Add section + chapter names to keyword_index. Weight 3. Skip existing."""
    kw_coll = db.collection("keyword_index")
    added = 0
    skipped = 0

    keywords_to_seed = []

    # Section names → map to all chapters in that section
    for sec in data["sections"]:
        chapter_numbers = [ch["number"] for ch in sec["chapters"]]
        # Hebrew section name
        if sec["name_he"]:
            keywords_to_seed.append({
                "keyword": sec["name_he"],
                "keyword_he": sec["name_he"],
                "keyword_en": sec["name_en"],
                "chapters": chapter_numbers,
                "description": f"Section {sec['number']} — {sec['name_en']}",
            })
        # English section name
        if sec["name_en"]:
            keywords_to_seed.append({
                "keyword": sec["name_en"].lower(),
                "keyword_he": sec["name_he"],
                "keyword_en": sec["name_en"],
                "chapters": chapter_numbers,
                "description": f"Section {sec['number']} — {sec['name_en']}",
            })

    # Chapter names → map to that chapter's 2-digit heading
    for sec in data["sections"]:
        for ch in sec["chapters"]:
            # Hebrew chapter name
            if ch["name_he"]:
                keywords_to_seed.append({
                    "keyword": ch["name_he"],
                    "keyword_he": ch["name_he"],
                    "keyword_en": ch["name_en"],
                    "chapters": [ch["number"]],
                    "description": f"Chapter {ch['number']} — {ch['name_en']}",
                })
            # English chapter name
            if ch["name_en"]:
                keywords_to_seed.append({
                    "keyword": ch["name_en"].lower(),
                    "keyword_he": ch["name_he"],
                    "keyword_en": ch["name_en"],
                    "chapters": [ch["number"]],
                    "description": f"Chapter {ch['number']} — {ch['name_en']}",
                })

    if test_mode:
        keywords_to_seed = keywords_to_seed[:20]

    print(f"  Processing {len(keywords_to_seed)} keyword candidates...")

    batch = db.batch()
    batch_count = 0

    for kw_entry in keywords_to_seed:
        kw = kw_entry["keyword"]
        doc_id = safe_doc_id(kw)
        ref = kw_coll.document(doc_id)

        existing = ref.get()
        if existing.exists:
            ex_data = existing.to_dict()
            ex_codes = ex_data.get("codes", [])
            # Check if any of these chapters are already mapped
            existing_headings = {c.get("hs_code", "") for c in ex_codes}
            new_chapters = [ch for ch in kw_entry["chapters"] if ch not in existing_headings]

            if not new_chapters:
                skipped += 1
                continue

            # Append new chapter codes to existing entry
            for ch in new_chapters:
                ex_codes.append({
                    "hs_code": ch,
                    "weight": 3,
                    "source": SOURCE,
                    "description": kw_entry["description"],
                })
            batch.update(ref, {
                "codes": ex_codes,
                "count": len(ex_codes),
                "updated_at": NOW,
            })
        else:
            # New entry
            codes = []
            for ch in kw_entry["chapters"]:
                codes.append({
                    "hs_code": ch,
                    "weight": 3,
                    "source": SOURCE,
                    "description": kw_entry["description"],
                })
            batch.set(ref, {
                "keyword": kw,
                "keyword_he": kw_entry.get("keyword_he", ""),
                "keyword_en": kw_entry.get("keyword_en", ""),
                "codes": codes,
                "count": len(codes),
                "built_at": NOW,
                "updated_at": NOW,
                "enriched": False,
            })

        added += 1
        batch_count += 1

        if batch_count >= 400:
            batch.commit()
            batch = db.batch()
            batch_count = 0
            print(f"    Committed batch ({added} added so far)")

    if batch_count > 0:
        batch.commit()

    print(f"  keyword_index: {added} added, {skipped} skipped (already had heading)")
    return added, skipped


def reindex_tariff_structure():
    """Re-index tariff_structure collection in librarian_index."""
    try:
        from lib.librarian_index import index_collection
        indexed = index_collection(db, "tariff_structure")
        print(f"  librarian_index: {indexed} tariff_structure docs indexed")
        return indexed
    except Exception as e:
        print(f"  WARNING: Could not re-index librarian_index: {e}")
        print("  (Run rebuild_index manually or wait for next overnight brain)")
        return 0


if __name__ == "__main__":
    test_mode = "--test" in sys.argv
    skip_keywords = "--skip-keywords" in sys.argv

    print("=" * 60)
    print("  SEED TARIFF STRUCTURE")
    print(f"  Source: {XML_PATH}")
    print(f"  Mode: {'TEST (limited)' if test_mode else 'FULL'}")
    print(f"  Keywords: {'SKIP' if skip_keywords else 'SEED'}")
    print("=" * 60)

    # Parse XML
    print("\n1. Parsing XML...")
    data = parse_xml()
    print(f"   Sections: {len(data['sections'])}")
    total_chapters = sum(len(s['chapters']) for s in data['sections'])
    print(f"   Chapters: {total_chapters}")
    print(f"   Additions: {len(data['additions'])}")

    # Seed tariff_structure collection
    print("\n2. Seeding tariff_structure collection...")
    struct_count = seed_tariff_structure(data, test_mode)

    # Seed keyword_index
    if not skip_keywords:
        print("\n3. Seeding keyword_index...")
        kw_added, kw_skipped = seed_keywords(data, test_mode)
    else:
        print("\n3. Skipping keyword_index (--skip-keywords)")
        kw_added, kw_skipped = 0, 0

    # Re-index
    print("\n4. Re-indexing tariff_structure in librarian_index...")
    reindex_count = reindex_tariff_structure()

    # Summary
    print("\n" + "=" * 60)
    print("  DONE")
    print(f"  tariff_structure docs: {struct_count}")
    print(f"  keyword_index added: {kw_added}, skipped: {kw_skipped}")
    print(f"  librarian_index re-indexed: {reindex_count}")
    print("=" * 60)
