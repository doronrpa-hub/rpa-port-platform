"""
Session 67: Upload converted XML documents to Firestore xml_documents collection.

Reads all XMLs from downloads/xml/ (shaarolami) and downloads/govil/ (gov.il),
categorizes each file, uploads to Firestore with chunking for files > 900KB.

Usage:
  python -X utf8 scripts/upload_xml_to_firestore.py           # dry run
  python -X utf8 scripts/upload_xml_to_firestore.py --execute  # actually upload
  python -X utf8 scripts/upload_xml_to_firestore.py --execute --force  # re-upload even if exists

Collections written:
  - xml_documents/{doc_id} — main document metadata + xml_content (if < 900KB)
  - xml_documents/{doc_id}/chunks/{N} — page chunks for oversized files
  - librarian_index/xdoc_{doc_id} — search index entries
"""

import sys
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──
REPO_ROOT = Path(__file__).resolve().parent.parent
XML_DIR = REPO_ROOT / "downloads" / "xml"
GOVIL_DIR = REPO_ROOT / "downloads" / "govil"

CHUNK_THRESHOLD = 900_000  # 900KB — Firestore 1MB doc limit with safety margin
BATCH_SIZE = 10

# ── Firebase init ──
os.environ["GOOGLE_CLOUD_PROJECT"] = "rpa-port-customs"

import firebase_admin
from firebase_admin import credentials, firestore

SA_PATHS = [
    r"C:\Users\User\Downloads\rpa-port-customs-firebase-adminsdk-fbsvc-da5df22d32.json",
    r"C:\Users\doron\sa-key.json",
]

def init_firebase():
    try:
        app = firebase_admin.get_app()
    except ValueError:
        sa_path = next((p for p in SA_PATHS if os.path.exists(p)), None)
        if not sa_path:
            print("ERROR: No service account key found at:")
            for p in SA_PATHS:
                print(f"  {p}")
            sys.exit(1)
        cred = credentials.Certificate(sa_path)
        app = firebase_admin.initialize_app(cred)
    return firestore.client()


# ═══════════════════════════════════════════
#  CATEGORIZATION
# ═══════════════════════════════════════════

ROMAN_NUMERALS = {
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX",
    "XX", "XXI", "XXII",
}

# Skip test/duplicate files
SKIP_FILES = {"FrameOrder_test.xml", "ThirdAddition_test.xml"}


def categorize_file(filepath: Path) -> dict | None:
    """Categorize an XML file based on its path and filename pattern.

    Returns dict with: source, category, subcategory, doc_id
    Or None if file should be skipped.
    """
    name = filepath.stem  # filename without .xml
    parent = filepath.parent.name  # "xml" or "govil"

    if filepath.name in SKIP_FILES:
        return None

    source = "shaarolami" if parent == "xml" else "govil"

    # ── Shaarolami files ──
    if source == "shaarolami":
        if name in ROMAN_NUMERALS:
            return {
                "source": source, "category": "tariff_section",
                "subcategory": name,
                "doc_id": f"shaarolami__section_{name}",
            }
        m = re.match(r"^TradeAgreement(\d+)$", name)
        if m:
            return {
                "source": source, "category": "trade_agreement",
                "subcategory": m.group(1),
                "doc_id": f"shaarolami__trade_agreement_{m.group(1)}",
            }
        if name == "FrameOrder":
            return {
                "source": source, "category": "framework_order",
                "subcategory": None,
                "doc_id": "shaarolami__framework_order",
            }
        if name == "ExemptCustomsItems":
            return {
                "source": source, "category": "exempt_items",
                "subcategory": None,
                "doc_id": "shaarolami__exempt_items",
            }
        if name == "SecondAddition":
            return {
                "source": source, "category": "supplement",
                "subcategory": "2",
                "doc_id": "shaarolami__supplement_2",
            }
        if name == "ThirdAddition":
            return {
                "source": source, "category": "supplement",
                "subcategory": "3",
                "doc_id": "shaarolami__supplement_3",
            }
        if name == "AllCustomsBookDataPDF":
            return {
                "source": source, "category": "full_tariff_book",
                "subcategory": None,
                "doc_id": "shaarolami__full_tariff_book",
            }
        # Unknown shaarolami file
        return {
            "source": source, "category": "other",
            "subcategory": None,
            "doc_id": f"shaarolami__{name}",
        }

    # ── Gov.il files ──
    if name.startswith("FTA_"):
        # Extract country: FTA_{country}_sahar-hutz_...
        parts = name.split("_")
        country = parts[1] if len(parts) > 1 else "unknown"
        # Create a short doc_id from the filename
        short_name = name.replace("sahar-hutz_agreements_", "")
        # Sanitize for Firestore doc ID (no slashes, dots safe)
        doc_id = f"govil__{short_name}"
        # Truncate if too long (Firestore doc ID max 1500 bytes)
        if len(doc_id) > 200:
            doc_id = doc_id[:200]
        return {
            "source": source, "category": "fta",
            "subcategory": country,
            "doc_id": doc_id,
        }
    if name.startswith("FIO_"):
        short_name = name.replace("Hofshi_", "").replace("laws_", "")
        doc_id = f"govil__{short_name}"
        if len(doc_id) > 200:
            doc_id = doc_id[:200]
        return {
            "source": source, "category": "fio",
            "subcategory": None,
            "doc_id": doc_id,
        }
    if name.startswith("FEO_"):
        doc_id = f"govil__{name}"
        return {
            "source": source, "category": "feo",
            "subcategory": None,
            "doc_id": doc_id,
        }
    # Unknown govil file
    return {
        "source": source, "category": "other",
        "subcategory": None,
        "doc_id": f"govil__{name[:200]}",
    }


# ═══════════════════════════════════════════
#  XML PARSING
# ═══════════════════════════════════════════

def parse_xml_metadata(filepath: Path) -> dict:
    """Extract metadata from XML file without loading full content into memory."""
    info = {
        "page_count": 0,
        "title_he": None,
        "md5": None,
        "language": "he",
        "has_hebrew": False,
    }
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        info["page_count"] = int(root.get("pages", "0"))
        info["md5"] = root.get("md5", "")
        lang = root.get("language", "he")
        info["language"] = lang

        # Extract first title element
        for title_el in root.iter("title"):
            if title_el.text and title_el.text.strip():
                info["title_he"] = title_el.text.strip()
                break

        # Check for Hebrew content
        xml_text = filepath.read_text(encoding="utf-8")
        hebrew_pattern = re.compile(r"[\u0590-\u05FF]")
        info["has_hebrew"] = bool(hebrew_pattern.search(xml_text))

        if not info["has_hebrew"]:
            info["language"] = "en"
        elif info["language"] == "he" and re.search(r"[a-zA-Z]{20,}", xml_text):
            info["language"] = "mixed"

    except Exception as e:
        print(f"  WARNING: Could not parse {filepath.name}: {e}")

    return info


def split_xml_by_pages(filepath: Path, chunk_size_target: int = CHUNK_THRESHOLD) -> list[dict]:
    """Split a large XML into page-based chunks that fit under Firestore limit.

    Returns list of {chunk_number, page_start, page_end, xml_content}.
    """
    tree = ET.parse(filepath)
    root = tree.getroot()

    pages = list(root.iter("page"))
    if not pages:
        # No page elements — return entire content as one chunk
        content = filepath.read_text(encoding="utf-8")
        return [{"chunk_number": 0, "page_start": 1, "page_end": 1, "xml_content": content}]

    chunks = []
    current_pages = []
    current_size = 0
    chunk_num = 0

    for page in pages:
        page_xml = ET.tostring(page, encoding="unicode")
        page_size = len(page_xml.encode("utf-8"))
        page_num = int(page.get("number", "0"))

        # If adding this page would exceed threshold, flush current chunk
        if current_pages and (current_size + page_size) > chunk_size_target:
            chunk_xml = _build_chunk_xml(root, current_pages, chunk_num)
            first_page = int(current_pages[0].get("number", "0"))
            last_page = int(current_pages[-1].get("number", "0"))
            chunks.append({
                "chunk_number": chunk_num,
                "page_start": first_page,
                "page_end": last_page,
                "xml_content": chunk_xml,
            })
            chunk_num += 1
            current_pages = []
            current_size = 0

        current_pages.append(page)
        current_size += page_size

    # Flush remaining pages
    if current_pages:
        chunk_xml = _build_chunk_xml(root, current_pages, chunk_num)
        first_page = int(current_pages[0].get("number", "0"))
        last_page = int(current_pages[-1].get("number", "0"))
        chunks.append({
            "chunk_number": chunk_num,
            "page_start": first_page,
            "page_end": last_page,
            "xml_content": chunk_xml,
        })

    return chunks


def _build_chunk_xml(root, pages, chunk_num):
    """Build a minimal XML wrapper around a set of page elements."""
    header = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<document_chunk chunk="{chunk_num}" '
        f'source="{root.get("name", "")}" '
        f'pages="{root.get("pages", "")}">\n'
        f'  <body>\n'
    )
    body = ""
    for page in pages:
        body += "    " + ET.tostring(page, encoding="unicode") + "\n"
    footer = "  </body>\n</document_chunk>"
    return header + body + footer


# ═══════════════════════════════════════════
#  UPLOAD
# ═══════════════════════════════════════════

def upload_document(db, filepath: Path, cat: dict, force: bool = False) -> dict:
    """Upload a single XML document to Firestore.

    Returns: {"status": "uploaded"|"skipped"|"chunked", "chunks": N}
    """
    doc_id = cat["doc_id"]
    doc_ref = db.collection("xml_documents").document(doc_id)

    # Check if already exists
    if not force:
        existing = doc_ref.get()
        if existing.exists:
            return {"status": "skipped", "chunks": 0}

    # Parse metadata
    meta = parse_xml_metadata(filepath)
    file_size = filepath.stat().st_size
    xml_content = filepath.read_text(encoding="utf-8")

    now = datetime.now(timezone.utc)

    doc_data = {
        "file_name": filepath.stem,
        "source": cat["source"],
        "category": cat["category"],
        "subcategory": cat["subcategory"],
        "title_he": meta["title_he"],
        "page_count": meta["page_count"],
        "has_hebrew": meta["has_hebrew"],
        "language": meta["language"],
        "md5": meta["md5"],
        "size_bytes": file_size,
        "indexed_at": now,
        "is_chunked": False,
        "chunk_count": 0,
    }

    # Check if content fits in one document
    content_bytes = len(xml_content.encode("utf-8"))
    if content_bytes <= CHUNK_THRESHOLD:
        doc_data["xml_content"] = xml_content
        doc_data["is_chunked"] = False
        doc_data["chunk_count"] = 0
        doc_ref.set(doc_data)

        # Index in librarian_index
        _write_index_entry(db, doc_id, doc_data)
        return {"status": "uploaded", "chunks": 0}
    else:
        # Need to chunk
        doc_data["xml_content"] = None  # Too large for main doc
        doc_data["is_chunked"] = True
        chunks = split_xml_by_pages(filepath)
        doc_data["chunk_count"] = len(chunks)
        doc_ref.set(doc_data)

        # Write chunks as subcollection
        for chunk in chunks:
            chunk_ref = doc_ref.collection("chunks").document(str(chunk["chunk_number"]))
            chunk_ref.set({
                "chunk_number": chunk["chunk_number"],
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
                "xml_content": chunk["xml_content"],
                "parent_doc_id": doc_id,
            })

        # Index in librarian_index
        _write_index_entry(db, doc_id, doc_data)
        return {"status": "chunked", "chunks": len(chunks)}


def _write_index_entry(db, doc_id: str, doc_data: dict):
    """Write a librarian_index entry for searchability."""
    index_id = f"xdoc_{doc_id}"
    # Truncate if needed (Firestore doc ID limit)
    if len(index_id) > 500:
        index_id = index_id[:500]

    title = doc_data.get("title_he") or doc_data.get("file_name") or doc_id
    category = doc_data.get("category", "")
    subcategory = doc_data.get("subcategory") or ""

    # Build searchable text
    search_text = f"{title} {category} {subcategory} {doc_data.get('file_name', '')}"

    db.collection("librarian_index").document(index_id).set({
        "collection": "xml_documents",
        "doc_id": doc_id,
        "title": title[:500],
        "search_text": search_text[:1000],
        "doc_type": "document",
        "category": category,
        "subcategory": subcategory,
        "source": doc_data.get("source", ""),
        "indexed_at": doc_data.get("indexed_at"),
        "has_hebrew": doc_data.get("has_hebrew", False),
    })


# ═══════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════

def collect_xml_files() -> list[tuple[Path, dict]]:
    """Collect and categorize all XML files."""
    files = []

    # Shaarolami XMLs
    if XML_DIR.exists():
        for f in sorted(XML_DIR.glob("*.xml")):
            cat = categorize_file(f)
            if cat:
                files.append((f, cat))

    # Gov.il XMLs
    if GOVIL_DIR.exists():
        for f in sorted(GOVIL_DIR.glob("*.xml")):
            cat = categorize_file(f)
            if cat:
                files.append((f, cat))

    return files


def main():
    execute = "--execute" in sys.argv
    force = "--force" in sys.argv

    print("=" * 60)
    print("Session 67: Upload XML Documents to Firestore")
    print("=" * 60)

    # Collect files
    files = collect_xml_files()
    print(f"\nFound {len(files)} XML files to process")

    # Show categorization summary
    categories = {}
    for _, cat in files:
        key = f"{cat['source']}/{cat['category']}"
        categories[key] = categories.get(key, 0) + 1
    print("\nCategorization summary:")
    for key, count in sorted(categories.items()):
        print(f"  {key}: {count}")

    # Size analysis
    large_files = [(f, c) for f, c in files if f.stat().st_size > CHUNK_THRESHOLD]
    if large_files:
        print(f"\n{len(large_files)} files > 900KB (will be chunked):")
        for f, c in large_files:
            size_mb = f.stat().st_size / 1_048_576
            print(f"  {f.name}: {size_mb:.1f}MB → {c['doc_id']}")

    if not execute:
        print("\n" + "=" * 60)
        print("DRY RUN — pass --execute to actually upload")
        print("=" * 60)

        # Show all files that would be uploaded
        print(f"\nFiles to upload ({len(files)}):")
        for f, cat in files:
            size_kb = f.stat().st_size / 1024
            chunked = "CHUNK" if f.stat().st_size > CHUNK_THRESHOLD else "OK"
            subcat = cat.get('subcategory') or ''
            print(f"  [{chunked:5}] {size_kb:7.0f}KB  {cat['category']:20} {subcat:10} {f.name}")
        return

    # Initialize Firebase
    print("\nInitializing Firebase...")
    db = init_firebase()

    # Upload in batches
    stats = {"uploaded": 0, "chunked": 0, "skipped": 0, "errors": 0, "total_chunks": 0}

    for i, (filepath, cat) in enumerate(files):
        progress = f"[{i + 1}/{len(files)}]"
        try:
            result = upload_document(db, filepath, cat, force=force)
            status = result["status"]
            stats[status] = stats.get(status, 0) + 1
            if result.get("chunks", 0) > 0:
                stats["total_chunks"] += result["chunks"]

            symbol = {"uploaded": "+", "chunked": "~", "skipped": "="}
            print(f"  {progress} {symbol.get(status, '?')} {status:8} {cat['doc_id']}"
                  + (f" ({result['chunks']} chunks)" if result.get("chunks") else ""))

        except Exception as e:
            stats["errors"] += 1
            print(f"  {progress} ! ERROR   {cat['doc_id']}: {e}")

        # Batch pause every 10 uploads for Firestore rate limiting
        if (i + 1) % BATCH_SIZE == 0 and i < len(files) - 1:
            import time
            time.sleep(0.5)

    # Summary
    print("\n" + "=" * 60)
    print("Upload Summary")
    print("=" * 60)
    print(f"  Uploaded:      {stats['uploaded']}")
    print(f"  Chunked:       {stats['chunked']} ({stats['total_chunks']} total chunks)")
    print(f"  Skipped:       {stats['skipped']} (already existed)")
    print(f"  Errors:        {stats['errors']}")
    print(f"  Total files:   {len(files)}")


if __name__ == "__main__":
    main()
