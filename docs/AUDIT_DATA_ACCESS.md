# RCB DATA ACCESS AUDIT — 2026-02-25

## 1. FIRESTORE: What's Actually In There

**No service account key on this machine** — cannot query Firestore directly. All counts below come from commit messages, upload scripts, and seed scripts verified in the codebase.

### Collections with CONFIRMED data (seeded/uploaded with evidence)

| # | Collection | Docs | Evidence | Searchable via tool? |
|---|-----------|------|----------|---------------------|
| 1 | `tariff` | ~11,753 | C1 scraper, tariff_full_text.txt | YES — `search_tariff` |
| 2 | `chapter_notes` | ~99 | C2 parser (RuleDetailsHistory.xml) | YES — `get_chapter_notes` |
| 3 | `tariff_structure` | 137 | Seed script (22 sections, 98 chapters) | YES — `lookup_tariff_structure` |
| 4 | `free_import_order` | 6,121 | C3 seeder (data.gov.il JSON) | YES — `check_regulatory` |
| 5 | `free_export_order` | 979 | C4 seeder (data.gov.il JSON) | YES — `check_regulatory` |
| 6 | `framework_order` | 85 | C5 seeder | YES — `lookup_framework_order` |
| 7 | `classification_directives` | 218 | C6 enricher (shaarolami HTML) | YES — `search_classification_directives` |
| 8 | `legal_knowledge` | 19 | C8 seeder (ordinance + reforms) | YES — `search_legal_knowledge` |
| 9 | `keyword_index` | 5,001+ | B2 seed + overnight brain | YES — via `search_tariff` |
| 10 | `brain_index` | 5,001+ | Overnight brain output | Indirect (via intelligence.py) |
| 11 | `shipping_lines` | 29 | shipping_knowledge.py seed | Not via tool |
| 12 | `xml_documents` | **231** | **Commit `8c0b41b`: "221 direct + 10 chunked = 231 docs"** | **YES — `search_xml_documents` (tool #34)** |
| 13 | `librarian_index` | ~21,490 | Multiple seeders | Internal use only |

### Collections that PROBABLY have data (from runtime)

| Collection | Source | Docs (est.) |
|-----------|--------|-------------|
| `tracker_deals` | Live email processing | Unknown |
| `tracker_container_status` | Live email processing | Unknown |
| `rcb_processed` | Live email processing | Unknown |
| `learned_classifications` | Self-learning engine | Unknown |
| `questions_log` | Email intent system | Unknown |
| `elimination_log` | Elimination engine runs | Unknown |
| `email_quality_log` | Quality gate decisions | Unknown |
| `security_log` | Security events | Unknown |
| `port_schedules` | 12h scheduler | Unknown |

### Collections REGISTERED but likely EMPTY (no seed script, no runtime source)

| Collection | Status |
|-----------|--------|
| `pre_rulings` | C7 BLOCKED — no data source |
| `customs_decisions` | No seeder |
| `court_precedents` | No seeder |
| `customs_ordinance` | Replaced by in-memory `_ordinance_data.py` |
| `cbp_rulings` | No seeder |
| `bti_decisions` | No seeder |
| `tariff_uk` | Overnight brain fills, amount unknown |
| `tariff_usa` | No seeder |
| `tariff_eu` | No seeder |
| `fta_agreements` | No seeder (FTA data in xml_documents instead) |
| `licensing_knowledge` | No seeder |
| `section_notes` | No seeder |

### 18 Cache collections (filled on demand, may or may not have data)

`wikipedia_cache`, `wikidata_cache`, `country_cache`, `currency_rates`, `comtrade_cache`, `food_products_cache`, `fda_products_cache`, `boi_rates`, `pubchem_cache`, `eu_taric_cache`, `usitc_cache`, `cbs_trade_cache`, `barcode_cache`, `wco_notes_cache`, `unctad_country_cache`, `beauty_products_cache`, `crossref_cache`, `sanctions_cache`, `israel_tax_cache`, `image_patterns`

---

## 2. CODE-EMBEDDED DATA

| File | Lines | Contents |
|------|-------|----------|
| `_ordinance_data.py` | **1,828** | 311 articles, **ALL 311 have full Hebrew text** (`"f"` field). 17 chapters. Parsed from pkudat_mechess.txt |
| `_framework_order_data.py` | **199** | **33 articles** with title/summary/full Hebrew text. Framework order (צו מסגרת) |
| `customs_law.py` | **787** | Methodology (10 phases), GIR Rules 1-6, 5 Known Failures, tariff sections I-XXII, valid supplements list. Imports from the above two. |
| `chapter_expertise.py` | **380** | 22 tariff sections with `name_en`, `name_he`, `chapters`, `notes`, `traps` |

**Embedded total: ~3,194 lines of pure law/data as Python constants.**

---

## 3. xml_documents Collection — THE BIG ONE

### Confirmed: 231 docs uploaded (commit `8c0b41b`, Session 68)

### Source files on disk:

| Location | Files | Categories |
|----------|-------|-----------|
| `downloads/xml/` | **40 XML** (2 are test dupes) | 22 tariff sections (I-XXII), 11 trade agreements, framework order, supplements, exempt items, AllCustomsBookDataPDF |
| `downloads/govil/` | **193 XML + 200 PDF** | 146 FTA docs (16 countries), 46 FIO amendments, 1 FEO, 7 procedures |

### FTA country coverage (XML docs in govil/):

| Country | XML Docs | Country | XML Docs |
|---------|---------|---------|---------|
| Colombia | 34 | Panama | 20 |
| USA | 28 | UK | 16 |
| Jordan | 28 | Ukraine | 12 |
| EFTA | 28 | UAE | 10 |
| EU | 24 | Korea | 10 |
| Turkey | 22 | Guatemala | 10 |
| Mexico | 22 | Vietnam | 6 |
| Canada | 21 | | |

### Customs procedures downloaded (7 PDFs):

| File | Content |
|------|---------|
| `PROC_classification_nohalSivug3.pdf` | נוהל סיווג טובין (#3) |
| `PROC_tashar_Noal_1_Shichror_ACC.pdf` | נוהל תש"ר (#1) |
| `PROC_valuation_Noal_2_Aarcha_ACC.pdf` | נוהל הערכה (#2) |
| `PROC_declarants_Noal_25_Mzharim_ACC.pdf` | נוהל מצהרים (#25) |
| `PROC_25_Noal_25_Mzharim_ACC.pdf` | נוהל מצהרים (duplicate) |
| `PROC_28_LegalInformation_Noal_28_Matenim_ACC.pdf` | נוהל מתנים (#28) |
| `PROC_audit_Noal_10_Yavo_Eishi_ACC.pdf` | נוהל יבוא אישי (#10) |

---

## 4. Downloads Folder Summary

| Path | Count |
|------|-------|
| `downloads/xml/` | 40 files (38 useful XML + 2 test dupes) |
| `downloads/govil/` | 393 files (193 XML + 200 PDF) |
| `downloads/` (root) | 39 PDFs (22 tariff section PDFs, 12 trade agreement PDFs, frame order, additions) |
| **TOTAL LOCAL FILES** | **~472 files** |

---

## 5. TOOL -> COLLECTION MAP (What Each Tool Actually Queries)

### 34 active tools in dispatcher:

| # | Tool | Firestore Collection(s) | External API |
|---|------|------------------------|-------------|
| 1 | `check_memory` | `learned_classifications` (via SelfLearningEngine) | — |
| 2 | `search_tariff` | `tariff`, `keyword_index`, `product_index`, `supplier_index` (via intelligence.py) | — |
| 3 | `check_regulatory` | `free_import_order`, `free_export_order` | — |
| 4 | `lookup_fta` | `framework_order` (cached) | — |
| 5 | `verify_hs_code` | `tariff`, `chapter_notes`, `tariff_chapters` | — |
| 6 | `extract_invoice` | — | Gemini Flash |
| 7 | `assess_risk` | — | Rule-based |
| 8 | `get_chapter_notes` | `chapter_notes`, `tariff_structure` | — |
| 9 | `lookup_tariff_structure` | `tariff_structure` | — |
| 10 | `lookup_framework_order` | `framework_order` (cached) | — |
| 11 | `search_classification_directives` | `classification_directives` (cached) | — |
| 12 | `search_legal_knowledge` | `legal_knowledge` (cached) + **in-memory ordinance (311 arts)** | — |
| 13 | `run_elimination` | `tariff`, `chapter_notes`, `tariff_structure` (via engine) | Gemini/Claude (D6/D7) |
| 14 | `search_wikipedia` | `wikipedia_cache` | en.wikipedia.org |
| 15 | `search_wikidata` | `wikidata_cache` | wikidata.org |
| 16 | `lookup_country` | `country_cache` | restcountries.com |
| 17 | `convert_currency` | `currency_rates` | open.er-api.com |
| 18 | `search_comtrade` | `comtrade_cache` | comtradeapi.un.org |
| 19 | `lookup_food_product` | `food_products_cache` | openfoodfacts.org |
| 20 | `check_fda_product` | `fda_products_cache` | api.fda.gov |
| 21 | `bank_of_israel_rates` | `boi_rates` | boi.org.il |
| 22 | `search_pubchem` | `pubchem_cache` | pubchem.ncbi.nlm.nih.gov |
| 23 | `lookup_eu_taric` | `eu_taric_cache` | ec.europa.eu |
| 24 | `lookup_usitc` | `usitc_cache` | dataweb.usitc.gov |
| 25 | `israel_cbs_trade` | `cbs_trade_cache` | api.cbs.gov.il |
| 26 | `lookup_gs1_barcode` | `barcode_cache` | openfoodfacts.org (barcode) |
| 27 | `search_wco_notes` | `wco_notes_cache` | wcoomd.org |
| 28 | `lookup_unctad_gsp` | `unctad_country_cache` | unctadstat.unctad.org |
| 29 | `search_open_beauty` | `beauty_products_cache` | openbeautyfacts.org |
| 30 | `crossref_technical` | `crossref_cache` | api.crossref.org |
| 31 | `check_opensanctions` | `sanctions_cache` | api.opensanctions.org |
| 32 | `get_israel_vat_rates` | `israel_tax_cache` | gov.il |
| 33 | `fetch_seller_website` | — | Domain-whitelisted HTTP |
| **34** | **`search_xml_documents`** | **`xml_documents` (231 docs, cached)** | — |

---

## 6. CRITICAL: search_xml_documents STATUS

### Does it exist?
**YES.** Tool #34. Registered in `tool_definitions.py:744`. Handler `_search_xml_documents` at `tool_executors.py:1306`. Dispatcher entry at line 251.

### Is it in tool_definitions.py?
**YES.** Lines 742-785. System prompt step 34 at line 884.

### Is it called in email_intent.py?
**YES.** Two call sites:
- Line 1656: FTA_ORIGIN domain detection triggers `search_xml_documents`
- Line 1895: IMPORT_EXPORT_REQUIREMENTS domain triggers `search_xml_documents`

### Is it called in knowledge_query.py?
**NO.** Zero references. Knowledge queries that need FTA/tariff section text **cannot reach xml_documents** via this path.

### Is it in the AI tool-calling loop?
**YES.** It's tool #34 in the CLAUDE_TOOLS list, available to the AI during classification.

### Is it in the overnight brain?
**NO.** Zero references. Overnight enrichment never reads xml_documents.

---

## 7. HONEST SUMMARY

### What RCB ACTUALLY has:

| Category | Items | Searchable? |
|----------|-------|------------|
| Tariff codes with descriptions | ~11,753 | YES |
| Chapter notes (parsed XML) | ~99 | YES |
| Tariff structure (sections/chapters) | 137 | YES |
| Free Import Order records | 6,121 | YES |
| Free Export Order records | 979 | YES |
| Framework Order docs | 85 Firestore + 33 in-memory | YES |
| Classification directives | 218 | YES |
| Legal knowledge (Firestore) | 19 | YES |
| Ordinance articles (in-memory) | **311 with full Hebrew text** | YES (tool #12) |
| Framework Order articles (in-memory) | 33 with full Hebrew text | YES (tool #10) |
| Chapter expertise (in-memory) | 22 sections | YES (prompt injection) |
| **XML documents (FTA + tariff + procedures)** | **231 in Firestore** | **YES (tool #34)** |
| Keyword index | 5,001+ | YES (via search_tariff) |

### What's MISSING or BROKEN:

1. **`knowledge_query.py` has NO access to xml_documents** — direct email questions about FTA origin rules that go through the knowledge_query path can't reach the 231 XML docs
2. **Overnight brain ignores xml_documents** — never enriches from this collection
3. **~12 registered collections are likely EMPTY** (pre_rulings, customs_decisions, court_precedents, cbp_rulings, bti_decisions, tariff_usa, tariff_eu, fta_agreements, licensing_knowledge, section_notes, customs_ordinance)
4. **COLLECTION_FIELDS claims 70 but actually has 84** — header comment is stale
5. **No Firestore access from this machine** — sa-key.json not present, cannot verify actual live document counts
6. **200 PDFs in downloads/govil/ were NOT uploaded** — only XML conversions went to Firestore. The raw PDFs sit on disk unused
7. **AllCustomsBookDataPDF.xml** (6.9MB, full tariff book) is in downloads/xml/ and was uploaded, but its usefulness depends on how the XML was structured during conversion
