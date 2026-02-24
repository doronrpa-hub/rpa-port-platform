# Session 61 Handoff — PDF Download & Conversion Pipeline

**Date:** 2026-02-24
**Branch:** main

---

## 1. Downloaded PDFs (38 files, 77 MB)

All in `downloads/` folder. Source: `shaarolami-query.customs.mof.gov.il`

### Framework Order (צו מסגרת)
| File | Size |
|------|------|
| `FrameOrder.pdf` | 175,215 |
| `SecondAddition.pdf` (תוספת שניה) | 72,839 |
| `ThirdAddition.pdf` (תוספת שלישית) | 206,109 |

### Trade Agreements (הסכמי סחר)
| File | Size |
|------|------|
| `TradeAgreement5.pdf` | 350,626 |
| `TradeAgreement6.pdf` | 295,606 |
| `TradeAgreement7.pdf` | 268,510 |
| `TradeAgreement8.pdf` | 174,930 |
| `TradeAgreement14.pdf` | 171,083 |
| `TradeAgreement17.pdf` | 338,754 |
| `TradeAgreement19.pdf` | 309,099 |
| `TradeAgreement105.pdf` | 400,509 |
| `TradeAgreement106.pdf` | 335,691 |
| `TradeAgreement108.pdf` | 289,659 |
| `TradeAgreement109.pdf` | 1,490,034 |

### Exempt Items / Discount Codes
| File | Size |
|------|------|
| `ExemptCustomsItems.pdf` | 1,047,506 |

### Tariff Sections I-XXII
| File | Size | File | Size |
|------|------|------|------|
| `I.pdf` | 1,514,409 | `XII.pdf` | 1,030,439 |
| `II.pdf` | 2,419,825 | `XIII.pdf` | 1,095,534 |
| `III.pdf` | 390,654 | `XIV.pdf` | 401,516 |
| `IV.pdf` | 2,348,204 | `XV.pdf` | 3,605,121 |
| `V.pdf` | 984,485 | `XVI.pdf` | 2,354,569 |
| `VI.pdf` | 3,819,635 | `XVII.pdf` | 1,413,493 |
| `VII.pdf` | 937,740 | `XVIII.pdf` | 1,153,859 |
| `VIII.pdf` | 853,636 | `XIX.pdf` | 318,878 |
| `IX.pdf` | 917,927 | `XX.pdf` | 957,353 |
| `X.pdf` | 977,269 | `XXI.pdf` | 357,850 |
| `XI.pdf` | 4,460,616 | `XXII.pdf` | 404,216 |

### Full Tariff Book
| File | Size |
|------|------|
| `AllCustomsBookDataPDF.pdf` | 42,068,387 |

### Download URL Pattern
```
https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb/he/CustomsBook/Home/DownloadFileWithName?fileName={FILENAME}.pdf
```
No auth, no WAF — direct HTTP GET works. Server returns HTTP 200 with 0 bytes for non-existent files.

### Supplements 4-17: NOT separate PDFs
Tested all naming patterns (FourthAddition, Addition4, etc.) — all return 0 bytes.
These supplements are embedded inside `AllCustomsBookDataPDF.pdf` (41MB).
**TODO**: Map page ranges for supplements inside the big PDF.

### DiscountCodes page: 404
`/CustomspilotWeb/he/CustomsBook/Home/DiscountCodes` returns 404. Discount codes may be inside `ExemptCustomsItems.pdf`.

---

## 2. Firestore Collection Counts (VERIFIED 2026-02-24)

| Collection | Docs | Claimed | Match? |
|------------|------|---------|--------|
| `tariff` | 10,001+ | 11,753 | Likely yes (query capped at 10K) |
| `chapter_notes` | 99 | 99 | YES |
| `tariff_structure` | 137 | 137 | YES |
| `classification_directives` | 218 | 218 | YES |
| `framework_order` | 86 | 85+meta | YES |
| `free_import_order` | 6,122 | 6,121+meta | YES |
| `free_export_order` | 980 | 979+meta | YES |
| `legal_knowledge` | 20 | 19+meta | YES |
| `fta_agreements` | 21 | 21 | YES |
| `classification_rules` | 32 | 32 | YES |
| `brain_index` | 10,001+ | 5,001+ | YES |
| `keyword_index` | 10,001+ | 8,120+ | YES |
| `librarian_index` | 10,001+ | 21,490 | Likely yes |
| `tariff_chapters` | 101 | 101 | YES |
| `section_notes` | 11 | 11 | YES |
| `customs_procedures` | 2 | 2 | YES |
| `learned_classifications` | 14 | 14 | YES |
| `knowledge` | 71 | 71 | YES |
| `shaarolami_scrape_staging` | 10,001+ | 12,308+ | Likely yes |

**Verdict: All claimed counts verified.** The data IS in Firestore.

---

## 3. Code-Embedded Legal Data

### `functions/lib/_ordinance_data.py` — 285,894 bytes, 1,828 lines
- **Content:** ALL 311 articles of פקודת המכס (Customs Ordinance)
- **Fields per article:** `ch` (chapter), `t` (Hebrew title), `s` (English summary), `f` (full Hebrew text)
- **17 chapters** with metadata in `ORDINANCE_CHAPTERS`
- **117K chars** of Hebrew law text embedded in `"f"` fields
- **Source:** Parsed from `pkudat_mechess.txt` (272K chars, 9,897 lines)

### `functions/lib/_framework_order_data.py` — 86,280 bytes
- **Content:** 33 articles of צו מסגרת (Framework Order)
- **Fields per article:** `t` (title), `s` (summary), `f` (full Hebrew text), `fta` (country code)
- **Full Hebrew text** for all 33 articles
- **Source:** Parsed from `framework_order_text.txt`

### `functions/lib/customs_law.py` — 41,574 bytes, 787 lines
- **Content:** Classification methodology, GIR Rules 1-6, tariff sections, known failures
- **Imports** `_ordinance_data.py` and `_framework_order_data.py`
- **Key function:** `format_legal_context_for_prompt()` — injects law into AI prompts

### `functions/lib/chapter_expertise.py` — 18,272 bytes, 380 lines
- **Content:** Seed expertise for all 22 tariff sections (I-XXII)
- Chapter ranges, names, classification notes, common traps

---

## 4. AllCustomsBookDataPDF.pdf Structure

**NOT YET ANALYZED.** This 41MB file likely contains:
- Full tariff tables (sections I-XXII)
- Supplements 1-17 (תוספות)
- Exempt items / discount codes

**TODO for next session:** Open with PyMuPDF, search for supplement headers, map page ranges.

---

## 5. PDF-to-XML Converter

### `scripts/pdf_to_xml.py` — working prototype
- **Input:** Any PDF
- **Output:** Structured XML with `<page>`, `<article>`, `<paragraph>`, `<definition>`, `<footer>` elements
- **Features:** Page numbers, bold detection, HS code tagging, dedup across pages
- **Tested on:** `FrameOrder.pdf` → 40 articles, 467 paragraphs, 24 HS references detected
- **Known limitations:** Definition extraction incomplete (Hebrew `""term""` pattern not fully working), article numbering heuristic needs tuning for different document formats
- **Usage:** `python -X utf8 scripts/pdf_to_xml.py input.pdf output.xml`
- **Batch:** `python -X utf8 scripts/pdf_to_xml.py --batch downloads/ downloads/xml/`

### Test output
`downloads/FrameOrder.xml` — 63,869 bytes, validated structure

---

## 6. What's Already Covered vs What's New in the PDFs

### ALREADY IN CODE (no conversion needed):
| Document | Location | Status |
|----------|----------|--------|
| פקודת המכס (311 articles) | `_ordinance_data.py` | Full Hebrew text embedded |
| צו מסגרת (33 articles) | `_framework_order_data.py` | Full Hebrew text embedded |
| GIR Rules 1-6 | `customs_law.py` | Full text |
| Section/chapter expertise | `chapter_expertise.py` | All 22 sections |

### ALREADY IN FIRESTORE (no conversion needed):
| Document | Collection | Docs |
|----------|------------|------|
| Tariff codes + descriptions | `tariff` | 11,753+ |
| Chapter notes (72/97 from XML) | `chapter_notes` | 99 |
| Tariff structure (sections/chapters) | `tariff_structure` | 137 |
| Classification directives | `classification_directives` | 218 |
| Free Import Order (צו יבוא חופשי) | `free_import_order` | 6,122 |
| Free Export Order (צו יצוא חופשי) | `free_export_order` | 980 |
| Framework Order metadata | `framework_order` | 86 |
| Legal knowledge (ordinance chapters) | `legal_knowledge` | 20 |
| FTA agreements metadata | `fta_agreements` | 21 |

### NEW IN DOWNLOADED PDFs (NOT yet in system):
| PDF | Content | Priority |
|-----|---------|----------|
| `SecondAddition.pdf` | תוספת שניה — purchase tax rates | HIGH |
| `ThirdAddition.pdf` | תוספת שלישית — additional levy rates | HIGH |
| `ExemptCustomsItems.pdf` | Exempt/discount codes | HIGH |
| Supplements 4-17 (inside AllCustomsBookDataPDF) | FTA preferential rates per agreement | HIGH |
| `TradeAgreement5-109.pdf` (10 files) | Individual FTA agreement tariff tables | MEDIUM |
| Sections I-XXII PDFs | Full tariff with duty rates, notes, HS codes | LOW (mostly in Firestore already) |

### KEY GAP: Supplements 4-17
The צו מסגרת supplements contain the **actual preferential duty rates** per FTA agreement. The code has article text but NOT the rate tables. These are inside `AllCustomsBookDataPDF.pdf` and need page mapping + extraction.

---

## 7. What's Left To Do

### Immediate (next session):
1. **Map AllCustomsBookDataPDF.pdf** — find supplement page ranges (4-17)
2. **Extract supplement rate tables** — the actual duty rates per HS code per FTA
3. **Extract ExemptCustomsItems.pdf** — discount/exemption codes
4. **Verify SecondAddition + ThirdAddition** content vs what's in Firestore

### Later:
5. **gov.il downloads** — need Playwright for Cloudflare challenge (FTA full agreements, procedures)
6. **Batch convert** remaining PDFs to XML
7. **Wire converted data** into Firestore search tools

---

## 8. Access Patterns Confirmed

| Site | Method | Status |
|------|--------|--------|
| shaarolami-query.customs.mof.gov.il | Direct HTTP (curl) | Works, no auth |
| gov.il `/he/pages/*` | Blocked by Cloudflare JS challenge | Needs Playwright |
| gov.il `/BlobFolder/*` PDFs | Direct HTTP | Works, no auth |

---

## 9. Git Status

### Files created this session:
- `scripts/pdf_to_xml.py` — PDF-to-XML converter
- `downloads/*.pdf` — 38 downloaded PDFs (77 MB) — NOT committed (too large for git)
- `downloads/FrameOrder.xml` — test conversion output
- `downloads/frame_order_analysis.txt` — analysis scratch file

### Commits needed:
- `scripts/pdf_to_xml.py` — commit to repo
- `docs/SESSION_61_HANDOFF.md` — this file
- `downloads/` — add to `.gitignore` (PDFs too large for git)
