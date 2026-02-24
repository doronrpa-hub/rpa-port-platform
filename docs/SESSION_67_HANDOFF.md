# Session 67 Handoff — 2026-02-24

## What Was Done

### Task 1: Full Audit of Existing Firestore Data
Before building anything, audited ALL existing collections to avoid duplication:

| Collection | Docs | Source | Do NOT duplicate |
|-----------|------|--------|-----------------|
| `tariff` | 11,753 | tariff_full_text.txt | HS codes with descriptions |
| `chapter_notes` | 99 | RuleDetailsHistory.xml | Chapter preamble/notes/exclusions |
| `framework_order` | 85 | Knowledge doc + XML | Definitions, FTA clauses, additions |
| `free_import_order` | 6,121 | data.gov.il JSON | HS code regulatory requirements |
| `free_export_order` | 979 | data.gov.il JSON | Export order requirements |
| `classification_directives` | 218 | Shaarolami HTML | Enriched directives |
| `legal_knowledge` | 19 | PDF text extraction | Ordinance chapters, reforms |
| `legal_documents` | 4+ | Raw PDF content | Has `sections` subcollection |
| `customs_procedures` | 2 | PC agent downloads | Downloaded procedure PDFs |
| `fta_agreements` | 21 | import_knowledge.py | FTA metadata entries |

### Task 2: Designed xml_documents Firestore Schema
New collection `xml_documents` — separate from `legal_documents` to avoid collision.

**Document schema:**
```
xml_documents/{doc_id}
├── file_name: str          — original filename without extension
├── source: str             — "shaarolami" | "govil"
├── category: str           — tariff_section | trade_agreement | framework_order |
│                              supplement | exempt_items | full_tariff_book | fta | fio | feo
├── subcategory: str|null   — country code (FTA), roman numeral (sections), agreement # (trade)
├── title_he: str|null      — Hebrew title from XML <title> element
├── page_count: int         — from <document pages="N">
├── has_hebrew: bool        — Hebrew character presence check
├── language: str            — "he" | "en" | "mixed"
├── md5: str                — from <document md5="...">
├── xml_content: str|null   — full XML string (if < 900KB)
├── is_chunked: bool        — true if split into page chunks
├── chunk_count: int         — number of chunk sub-documents
├── indexed_at: timestamp
├── size_bytes: int         — original file size

Subcollection (chunked docs only):
  xml_documents/{doc_id}/chunks/{chunk_number}
  ├── chunk_number, page_start, page_end, xml_content, parent_doc_id
```

**Categorization rules:**
| Pattern | category | subcategory |
|---------|----------|-------------|
| `I.xml` through `XXII.xml` | tariff_section | Roman numeral |
| `TradeAgreement{N}.xml` | trade_agreement | Agreement number |
| `FrameOrder.xml` | framework_order | null |
| `ExemptCustomsItems.xml` | exempt_items | null |
| `SecondAddition.xml/ThirdAddition.xml` | supplement | "2" / "3" |
| `AllCustomsBookDataPDF.xml` | full_tariff_book | null |
| `FTA_{country}_*.xml` | fta | country code |
| `FIO_*.xml` | fio | null |
| `FEO_*.xml` | feo | null |

### Task 3: Built Upload Script
Created `scripts/upload_xml_to_firestore.py`:
- Dry run verified: all 231 files categorized correctly
- 12 files flagged for page-based chunking (>900KB)
- Batch processing with 10-file batches and rate limiting
- Skip-if-exists logic (pass `--force` to re-upload)
- Writes to both `xml_documents` and `librarian_index` collections
- Registered `xml_documents` in `librarian_index.py` COLLECTION_FIELDS

**Dry run output:**
```
Found 231 XML files to process

Categorization summary:
  govil/feo: 1
  govil/fio: 46
  govil/fta: 146
  shaarolami/exempt_items: 1
  shaarolami/framework_order: 1
  shaarolami/full_tariff_book: 1
  shaarolami/supplement: 2
  shaarolami/tariff_section: 22
  shaarolami/trade_agreement: 11

12 files > 900KB (will be chunked):
  AllCustomsBookDataPDF.xml: 6.7MB
  TradeAgreement109.xml: 2.1MB
  + 10 gov.il FTA files (900KB-1.5MB)
```

## Data Inventory

### Total PDFs Downloaded: 231
- **38 shaarolami** (tariff sections, framework order, supplements, trade agreements)
- **193 gov.il** (146 FTA from 16 countries + 46 FIO amendments + 1 FEO)

### Total XMLs: 231 (all converted)
- Validation: **38/38 shaarolami PASS**, **108/193 gov.il PASS** (85 English-only = expected, not failures)

### Firestore Upload Status: NOT YET UPLOADED
Script built, dry-run verified, upload deferred to next session.

## Commits Today

| Hash | Description |
|------|-------------|
| (this session) | session 67: xml_documents schema + upload script |

## Scripts Created/Modified

| Script | Status | Purpose |
|--------|--------|---------|
| `scripts/upload_xml_to_firestore.py` | **NEW** | Upload 231 XMLs to Firestore with categorization + chunking |
| `scripts/pdf_to_xml.py` | Existing (Session 61-65) | PDF converter with garbled Hebrew fix |
| `scripts/validate_xml.py` | Existing (Session 65) | XML quality checker, 38/38 PASS |
| `scripts/map_tariff_book.py` | Existing (Session 61) | Supplement page range mapper |

### Files Modified
| File | Change |
|------|--------|
| `functions/lib/librarian_index.py` | +6 lines: `xml_documents` registered in COLLECTION_FIELDS |

## Known Issues

1. **85 English-only gov.il XMLs** — fail Hebrew check but this is expected (English FTA agreements)
2. **12 oversized XMLs** — need page-based chunking (handled by upload script)
3. **PROC procedure PDFs not yet converted to XML** — 7 PDFs in downloads/govil/ without XML counterparts
4. **AllCustomsBookDataPDF.xml is 6.98MB** — will split into ~8 chunks by page ranges

## How Existing Search Works (for next session's wiring)

### `_search_legal_knowledge()` in tool_executors.py — 7 cases:
1. **Case A**: Article lookup (`סעיף 130`) → in-memory CUSTOMS_ORDINANCE_ARTICLES
2. **Case B**: Chapter articles (`פרק 8`) → all articles in that chapter
3. **Case 1**: Bare digit 1-15 → Firestore cache (ordinance chapter summary)
4. **Case 2**: Customs agents keywords → Firestore cache
5. **Case 3**: EU reform keywords → Firestore cache
6. **Case 4**: US reform keywords → Firestore cache
7. **Case C**: General keyword search → scored against 311 ordinance articles
8. **Case D/E**: Framework Order articles → in-memory FRAMEWORK_ORDER_ARTICLES
9. **Case 5**: Firestore substring search → `legal_knowledge` collection

### What needs to change for xml_documents:
- Add new Case in `_search_legal_knowledge()` for FTA protocol/procedure queries
- Or better: create a dedicated `_search_xml_documents()` tool
- The xml_documents data is FULL TEXT of laws/agreements — search should extract relevant pages/articles
- FTA queries should route to `xml_documents` where `category="fta"` and `subcategory={country}`

## What's Left (Priority Order)

1. **Upload XMLs to Firestore** — run `python -X utf8 scripts/upload_xml_to_firestore.py --execute`
2. **Wire xml_documents into search tools** — either extend `_search_legal_knowledge` or create new tool
3. **Convert PROC PDFs to XML** — 7 procedure PDFs not yet converted
4. **Download remaining docs** — EU/US customs reforms, AEO, approved exporter
5. **Write SEARCH_WIRING_PLAN.md** — document how to integrate xml_documents into search
6. **End-to-end test** — Nike counterfeit test, valuation test, FTA test with real XML citations

## File Locations

| Path | Contents |
|------|----------|
| `downloads/xml/` | 38 shaarolami XMLs + 2 test files |
| `downloads/govil/` | 193 gov.il XMLs + 199 PDFs + 2 PNGs |
| `downloads/*.pdf` | 38 shaarolami source PDFs |
| `scripts/upload_xml_to_firestore.py` | Upload script (this session) |
| `scripts/pdf_to_xml.py` | PDF-to-XML converter |
| `scripts/validate_xml.py` | XML quality validator |
| `functions/lib/librarian_index.py` | xml_documents registered |

## Upload Command (for next session)

```bash
# Dry run first:
python -X utf8 scripts/upload_xml_to_firestore.py

# Actual upload:
python -X utf8 scripts/upload_xml_to_firestore.py --execute

# Re-upload (overwrite existing):
python -X utf8 scripts/upload_xml_to_firestore.py --execute --force
```
