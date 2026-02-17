# RPA-PORT-PLATFORM — Claude Code Session Notes

## CRITICAL RULES
- **TaskYam is ALWAYS primary and 100% authoritative** when it shows data
- **Do NOT change or destroy existing code** — only ADD and IMPROVE
- **No guessing, no blind coding, no fairy tales** — verify everything
- **ALL external APIs must be FREE** — no paid services
- **Protect the database** — never send internal data (deal IDs, customer names, emails) to external APIs
- **All timestamps in Israel time** (Asia/Jerusalem, UTC+2 winter / UTC+3 summer)

## Architecture Overview

### Data Flow
```
Email → tracker_process_email() → _extract_logistics_data() → _match_or_create_deal()
                                                                        ↓
Scheduler (30min) → tracker_poll_active_deals() → Phase 1: TaskYam (always first)
                                                  → Phase 2: Ocean APIs (supplements)
                                                  → _send_tracker_email() (Global + Local)
```

### Phase 1: TaskYam (Israeli Port Operations) — ALWAYS PRIMARY
- `tracker.py` — TaskYamClient queries taskyam.israports.co.il
- Import steps: manifest → port_unloading → delivery_order → customs_check → customs_release → port_release → cargo_exit
- Export steps: storage_id → cargo_entry → customs → vessel_loaded → ship_sailing
- Data is **100% authoritative** when present

### Phase 2: Ocean Tracker (Global Visibility) — SUPPLEMENTS TaskYam
- `ocean_tracker.py` — Multi-source ocean-leg tracking (1,600+ lines)
- **Never overrides TaskYam data** — only fills sea-leg gaps
- Phase 2 branch in tracker.py is wrapped in try/except — cannot break Phase 1

### Email Template: Two Sections
- `tracker_email.py` — builds HTML status emails
- **Global Tracking**: BL number, container count, POL/POD timing (ETA/ATA/ETD/ATD), consolidated ocean events
- **TaskYam Local Tracking**: per-container detail table from TaskYam

## Files Modified/Created (Session B — Ocean Tracker)

### NEW: `functions/lib/ocean_tracker.py` (1,606 lines)
7 provider classes, all FREE APIs first:

| Priority | Provider | Secret Keys Needed | Free? |
|----------|----------|-------------------|-------|
| 1 | MaerskProvider | MAERSK_CONSUMER_KEY | Yes (confirmed) |
| 2 | ZIMProvider | ZIM_API_TOKEN | Yes (currently) |
| 3 | HapagLloydProvider | HAPAG_CLIENT_ID, HAPAG_CLIENT_SECRET | Yes (EUR 0) |
| 4 | COSCOProvider | COSCO_API_KEY, COSCO_SECRET_KEY | Yes (trial) |
| 5 | Terminal49Provider | TERMINAL49_API_KEY | Yes (100 containers) |
| 6 | INTTRAProvider | INTTRA_CLIENT_ID, INTTRA_CLIENT_SECRET | Yes (shippers) |
| 7 | VesselFinderProvider | VESSELFINDER_API_KEY | PAID (optional) |

Key functions:
- `query_ocean_status()` — main entry, queries all providers, merges, sanitizes
- `query_vessel_schedule()` — schedule queries (Maersk, ZIM, Hapag-Lloyd, COSCO)
- `enrich_deal_from_ocean()` — fills deal fields from ocean data
- `update_container_ocean_events()` — stores events on container status
- `ensure_terminal49_tracking()` — creates Terminal49 tracking request once per deal
- `sanitize_ocean_result()` / `sanitize_ocean_event()` — data protection
- `validate_container_for_query()` / `validate_bol_for_query()` — input validation

Smart carrier routing: Maersk API only for Maersk shipments, ZIM for ZIM, etc.
10 normalized event codes: EE, GI, AE, VD, TS, TL, VA, UV, GO, RD

### MODIFIED: `functions/lib/tracker.py`
- Added Phase 2 ocean polling branch in `tracker_poll_active_deals()`
- Runs AFTER TaskYam polling (TaskYam always first)
- Calls `query_ocean_status()` for each active deal
- Wrapped in try/except — Phase 1 unaffected if ocean fails

### MODIFIED: `functions/lib/tracker_email.py`
- Added `_to_israel_time()` — converts UTC to Asia/Jerusalem
- Updated `_format_date()` — all timestamps in Israel time
- Added `_extract_ocean_times()` — extracts POL/POD timing from ocean events
- Added `_time_style()` — CSS helper for timing cells
- Global Tracking section: BL, containers, POL/POD table, event timeline
- TaskYam Local Tracking section: per-container detail (unchanged format)

### MODIFIED: `functions/lib/librarian_index.py`
- Added to COLLECTION_FIELDS: `tracker_deals`, `tracker_container_status`, `tracker_timeline`
- Previously added: `shipping_lines`, `fiata_documents`

### MODIFIED: `functions/lib/doc_reader.py`
- Added DOC_TYPE_SIGNALS: `vessel_schedule`, `arrival_notice`
- Previously added: `fiata_fbl`, `fiata_fwr`, `dangerous_goods_declaration`, `air_waybill`

### CREATED (Previous Session): `functions/lib/shipping_knowledge.py` (1,230 lines)
- 9 carrier profiles (ZIM, Maersk, MSC, Evergreen, Hapag-Lloyd, ONE, COSCO, Yang Ming, OOCL)
- BIC/ISO 6346 container validation
- BOL prefix identification
- Israeli port system integration (20 company codes, 18 kav codes)
- Container type old↔new mappings (145 entries)
- FIATA documents, IATA AWB format
- VESSEL_TYPES, PACKAGE_CODES, IMDG_CLASSES, TASKYAM_KEY_ERRORS
- `seed_all(db)` — seeds Firestore with carrier data

## Firestore Collections (Tracker)
- `tracker_deals` — one per BL/AWB deal
- `tracker_container_status` — one per container per deal (has both TaskYam + ocean data)
- `tracker_timeline` — event log per deal
- `tracker_observations` — per-email dedup
- `shipping_lines` — carrier profiles (seeded by shipping_knowledge.py)
- `fiata_documents` — FIATA document types

## Downloaded Data (israports.co.il)
Location: `C:/Users/doron/israports_tables/`
- S14_Ships.csv, U08_Ports.csv, S19_ShippingCompanies.csv, S03_Agents.csv
- M01_CustomsAgents.csv, A45_ContainerOldNew.csv, A46_ContainerNewOld.csv
- V03_ShipTypes.csv, A17_DangerousGoods.csv, S29_LinesShipAgent.csv
- C01_PackageCodes.csv, S30_ErrorCodes.csv

## Gov.il Tables (STILL INACCESSIBLE — Cloudflare)
Tables: 1091, 1259, 1326, 1347, 1390, 1307, 1308, 1378, 1369, 1373, 2010, 1557, 1907

## Carriers WITHOUT Free APIs
- MSC (gated, customer-only)
- OOCL (EDI only, no public API)
- Yang Ming (no API)
- ONE (portal exists, details behind login)
- Evergreen (requires sales rep)

## Additional Data Sources (User Noted)
- **Port2Port schedules** — can be parsed for ETD/ETA
- **Emails to cc@rpa-port.co.il** — schedule notifications from shipping lines
- **Port working plans** — published by Israeli ports
- **TaskYam = 100% authoritative** when shown

## Cost Optimization (Session C)

### Model Routing Strategy (MINIMIZE COSTS)
| Component | Model | Cost (per MTok) | Notes |
|-----------|-------|-----------------|-------|
| **Tool-calling engine** | Gemini 2.5 Flash (PRIMARY) | $0.15/$0.60 | Was Claude ($3/$15). ~95% savings. Falls back to Claude. |
| **Agent 2 (Classification)** | Claude Sonnet 4.5 | $3/$15 | Stays on Claude — core task, quality critical |
| **Agents 1,3,4,5** | Gemini 2.5 Flash | $0.15/$0.60 | Already optimized |
| **Agent 6 (Synthesis)** | Gemini 2.5 Pro | $1.25/$10 | Hebrew quality needs Pro |
| **Cross-check** | Gemini Pro + Flash + GPT-4o-mini | ~$0.0009/item | Was Claude+Gemini+GPT (~$0.0046/item). ~80% savings. |
| **Overnight Brain** | Gemini 2.5 Flash | $0.15/$0.60 | Budget-capped at $3.50/run |
| **Pupil** | Gemini 2.5 Flash | $0.15/$0.60 | Already optimized |

### Changes Made
- **`tool_calling_engine.py`**: Added `_call_gemini_with_tools()` + `_run_gemini_tool_loop()`. Gemini Flash is now PRIMARY for tool-calling, Claude is FALLBACK. `_PREFER_GEMINI = True` flag controls this.
- **`cross_checker.py`**: Replaced Claude Sonnet with Gemini Pro in 3-way cross-check. Still 3 independent models (Gemini Pro vs Flash vs GPT-4o-mini + UK Tariff).
- **`tool_definitions.py`**: Already had `GEMINI_TOOLS` format — now imported and used.

### Estimated Monthly Savings (2,000 classifications/month)
```
Tool-calling:  $200 → $10     (savings: $190)
Cross-check:   $200 → $40     (savings: $160)
Total savings: ~$350/month
```

### Key Constants
- `tool_calling_engine.py:_PREFER_GEMINI = True` — Gemini first, Claude fallback
- `classification_agents.py:PRE_CLASSIFY_BYPASS_ENABLED = True` — Skip AI when memory confidence >= 90%
- `classification_agents.py:CROSS_CHECK_ENABLED = True` — 3-way verification (now cheaper)
- `cost_tracker.py:BUDGET_LIMIT = 3.50` — Hard cap per overnight run

## Daily Port Schedule (Session C)

### NEW: `functions/lib/schedule_il_ports.py`
Daily vessel schedule aggregation for Israeli ports (Haifa, Ashdod, Eilat).

**6 FREE data sources:**
| # | Source | Type | Function |
|---|--------|------|----------|
| 1 | Carrier APIs | REST | `_query_carrier_schedules()` — via ocean_tracker.query_vessel_schedule() |
| 2 | aisstream.io | AIS/REST | `_query_ais_vessels()` — real-time vessel positions near ports |
| 3 | Haifa Port portal | Web | `_query_haifa_port_schedule()` — haifa-port.ynadev.com |
| 4 | ZIM Expected | Web | `_query_zim_expected_vessels()` — zim.com Israel page |
| 5 | TaskYam deals | Firestore | `_extract_from_active_deals()` — vessel data from active deals |
| 6 | Email parsing | Graph API | `parse_schedule_from_email()` — cc@rpa-port.co.il schedule emails |

**Key functions:**
- `build_all_port_schedules(db, get_secret_func)` — main entry, all 3 ports
- `build_daily_port_schedule(db, port_code, get_secret_func)` — single port
- `is_schedule_email(subject, body, from_email)` — detect schedule emails
- `process_schedule_email(db, subject, body, from_email, msg_id)` — extract & store
- `build_schedule_email_html(db, port_code)` — daily report HTML email
- `get_vessel_schedule(db, vessel_name)` — lookup by vessel
- `get_daily_report(db, port_code, date)` — get daily aggregate

**Dedup priority:** TaskYam > Carrier API > Haifa Port > ZIM Expected > Email > AIS

**Secret keys needed:** `AISSTREAM_API_KEY` (free registration at aisstream.io)

### MODIFIED: `functions/main.py`
- Added `rcb_port_schedule()` — scheduled every 12 hours
- Added schedule email detection in CC email handler (after tracker, before classification)
- Import: `schedule_il_ports.build_all_port_schedules, is_schedule_email, process_schedule_email`

### MODIFIED: `functions/lib/librarian_index.py`
- Added `port_schedules` and `daily_port_report` to COLLECTION_FIELDS

### Firestore Collections (Port Schedule)
- `port_schedules` — one doc per vessel visit per port (dedup key: port+vessel+eta_date)
- `daily_port_report` — aggregate per port per day (doc ID: `ILHFA_2026-02-17`)

### Israeli Port Data Sources (Discovered)
- Haifa Port digital portal: `haifa-port.ynadev.com` (ship schedules, work plan, real-time)
- Ashdod Port: `ashdodport.co.il` (ASP.NET, may need session)
- IsraPorts: `israports.co.il` (WAF-protected, has shipping schedule page)
- ZIM Israel: `zim.com/global-network/asia-oceania/israel/expected-vessels`
- ONE Port Schedule: `ecomm.one-line.com/one-ecom/schedule/port-schedule?portCdParam=ILHFA`
- aisstream.io: Free real-time AIS WebSocket/REST
- Port2Port portal: `port2port.co.il` (links to port work schedules)
- Note: Eilat Port closed July 2025 (Houthi attacks)

## RCB TARGET ARCHITECTURE — Block Status (Session D — Tariff Data)

### Blocks COMPLETED (deployed)
- **A1**: CC invoice classification → customs pipeline
- **A2**: [DECL] declaration routing
- **A3 Cat.1**: Never-silent exits (extraction_failed + pipeline_error notifications)
- **A3 Cat.2**: Clarification candidates instead of "unclassifiable"
- **A4**: Reserved (no action needed)
- **B1**: Wire smart_extractor via extraction_adapter
- **B2**: Keyword seeding (seed_keywords_b2.py) — brain_index populated

### Block C1: Tariff Descriptions — DONE (commit f1b7a44)
- `functions/scrape_shaarolami_c1.py` — scraper for shaarolami tariff descriptions
- **Phase 1**: 1,687 exact HS code matches written to `tariff` collection
- **Phase 2**: 417 parent-code inheritance written to `tariff` collection
- **Coverage**: 80.5% → 98.4% (descriptions filled)
- **188 corrupt codes** flagged with `corrupt_code: true` in tariff collection
- Staging collection: `shaarolami_scrape_staging` (12,308+ docs)

### Block C2: Chapter Notes — WIRED (commit 2cb4f61)
**Status: Parser built, chapter notes populated, tools wired.**
- `functions/parse_chapter_notes_c2.py` — parses RuleDetailsHistory.xml → Firestore `chapter_notes`
- **94/98 chapters** parsed with preamble, notes, exclusions, inclusions, supplementary_israeli, subheading_rules
- **Chapters 50, 53**: Confirmed no chapter-specific notes (Section XI notes apply) — verified against XI.pdf
- **Chapters 77, 98**: Reserved/Israeli-special — marked confirmed empty
- `tool_executors.py` `_get_chapter_notes()`: Now exposes all C2 fields (preamble_en, notes_en, supplementary_israeli, subheading_rules)
- `justification_engine.py` `challenge_classification()` METHOD 1: Hebrew exclusion regex fixed (was English-only, now matches פרק/בפרק/לפרק)
- `tariff_structure` collection: 137 docs seeded (22 sections, 98 chapters, 13 additions, metadata)
- `keyword_index`: Section + chapter names seeded (weight 3)

**Data source — RuleDetailsHistory.xml:**
- Covers **72 of 97 chapters** (missing 25: chapters 2, 13, 17, 23, 24, 36, 42, 45, 47, 50-53, 55, 66-67, 69, 75, 77-81, 88-89)
- 9,228 entries, 9,099 with Hebrew text, only 1,284 with English
- 18 section-level notes (Sections I, VI, VII, XI, XV, XVI, XVII)
- Location: `C:\Users\doron\tariff_extract\RuleDetailsHistory.xml` (39 MB)

**Remaining C2 gaps (25 chapters without XML data):**
- Some may have no chapter-specific notes (like ch50, ch53) — section notes apply
- Others may need scraping from shaarolami or manual entry
- XI.pdf chapter pages have garbled encoding (cid:XXX) — same as main tariff PDF

### Block C3: Free Import Order (צו יבוא חופשי) — DONE (Session 32)
**Status: 28,899 records parsed, 6,121 HS codes seeded, tool wired.**
- `functions/seed_free_import_order_c3.py` — parses data.gov.il JSON → Firestore `free_import_order`
- **Source**: `agent/free_import_order/20260201_download_20260201_141544.json` (39 MB, from Cloud Storage)
- **Also available**: `צו יבוא חופשי.zip` (13.6 MB, 46 amendment PDFs 2014-2025) in Cloud Storage root
- **6,121 unique HS codes** across 87 chapters, 28,899 regulatory requirement records
- **3 appendices**: תוספת 2 (27,026 records), תוספת 1 (1,620), תוספת 4 (253)
- **18 authorities** mapped: משרד הכלכלה, מכון התקנים, מעבדת בדיקה, משרד הבריאות, משרד החקלאות, משרד התחבורה + 12 more
- **25,892 active records** (EndDate >= 2026), 3,007 expired (kept with is_active=false)
- Per-HS doc: requirements list, authorities_summary, appendices, has_standards, has_lab_testing, conditions_type, inception_type
- `tool_executors.py` `_check_regulatory()`: Now checks local `free_import_order` collection first (instant), falls back to live API
- `tool_executors.py` `_lookup_local_fio()`: Exact match + parent code range query fallback
- `librarian_index.py`: `free_import_order` collection registered, 6,121 docs indexed (prefix: fio_)
- `free_import_order/_metadata`: Summary doc with collection stats

### Blocks C4-C8: NOT STARTED
- C4: Brain downloads: צו יצוא חופשי (Free Export Order)
- C5: Brain downloads: צו המסגרת (Framework Order) — content already in knowledge collection
- C6: Brain downloads: הנחיות סיווג (classification directives)
- C7: Brain downloads: פרה-רולינג database
- C8: Duty rates — `AdditionRulesDetailsHistory.xml` (7.4MB) has צו מסגרת legal text

### Block D: Elimination Engine — UNBLOCKED (C2 + C3 done)

## Tariff XML Archive (fullCustomsBookData.zip)

### Location
- **7z archive**: `C:\Users\doron\fullCustomsBookData.zip` (214 MB) — also in Cloud Storage as `documents/tariff/1769686305688_fullCustomsBookData (6).zip`
- **Extracted files**: `C:\Users\doron\tariff_extract\` (15 of 238 files extracted)
- **Cloud Storage backup**: `tariff_xml_backup/` folder (25 files, 103.4 MB)

### Extracted XML Files (analyzed)
| File | Size | Contents |
|------|------|----------|
| Rule.xml | 114 KB | 670 rules mapping RuleID → CustomsItemID. Title categories: כללים לפרק (236x), כללים לחלק (32x), כללים נוספים (28x) |
| RuleDetailsHistory.xml | 39 MB | **Chapter notes text** — 9,228 entries, 72/97 chapters covered. Fields: Rules (Hebrew), EnglishRules, RulesRTF |
| AdditionRulesDetailsHistory.xml | 7.4 MB | **צו מסגרת legal text** — 296 entries. Trade agreement clauses, תוספת ראשונה/שניה rules. For Block C8. |
| CustomsItem.xml | 12.4 MB | Master item tree — ID, FullClassification (HS code), Parent_CustomsItemID |
| CustomsItemDetailsHistory.xml | 42.9 MB | Item descriptions with history — NOT YET ANALYZED |
| CustomsBookAddition.xml | 25 KB | Metadata index of 95 additions — NO text content |
| CustomsBookAdditionsDetailsHistory.xml | 46 KB | 101 entries, metadata only |
| CustomsItemExclusion.xml | 48 KB | 322 regulatory exclusion mappings (NOT chapter note exclusions) |
| CustomsItemLinkage.xml | 1.6 MB | Item linkages |
| RegularityRequirement.xml | 3.5 MB | Regulatory requirements |
| TradeAgreement.xml | 20 KB | Trade agreement metadata |
| TradeAgreementVersion.xml | 267 KB | Trade agreement versions |
| TradeLevy.xml | 83 KB | Trade levies |
| CountriesExclusion.xml | 24 KB | Country-based exclusions |
| fullCustomsBookData.xml | 4.1 GB | Master file: CustomsItem + TariffDetailsHistory + TariffComputedData + ComputationMethodData + PropertiesDetailsHistory + RegularityRequirementComputedData |

### Unextracted Files (223 remaining in archive)
Key files still inside the 7z:
- `Tariff_0.xml` through `Tariff_6.xml` — tariff data partitions
- `TariffDetailsHistory_0.xml` through `TariffDetailsHistory_52.xml` — 53 tariff history files
- `ComputationMethodData_0.xml` through `ComputationMethodData_91.xml` — 92 computation files
- `RegularityRequirementComputedData_0-6.xml` — 7 regulatory files
- `PropertiesDetailsHistory_0-3.xml` — 4 properties files
- `Quota.xml`, `QuotaComputedData.xml`, `QuotaDetailsHistory.xml`, `QuotaRenewal.xml`
- `LevyCondition.xml`, `LevyExclusion.xml`
- `RegularityInception.xml`, `RegularityRequiredCertificate.xml`
- `Vendor.xml`, `AccessDBTamplate20240701.accdb`, `tempRegularityRequirementData.Json`

## Firestore Key Collections (120 total)
| Collection | Docs | Purpose |
|-----------|------|---------|
| tariff | 11,753+ | HS codes with descriptions, duty rates. Source: tariff_full_text.txt |
| tariff_chapters | 101 | Scraped shaarolami chapter page HTML |
| chapter_notes | 99 | **EMPTY** preamble/notes/exclusions/inclusions — needs C2 |
| shaarolami_scrape_staging | 12,308+ | C1 scrape staging data |
| classification_rules | 32 | GIR 1-6 interpretive rules only |
| brain_index | 5,001+ | 174K keywords extracted by overnight brain |
| librarian_index | 21,490 | Index metadata (tariff: 11,753, keyword_index: 8,120, knowledge_base: 305) |
| knowledge | 71 | 1 tariff doc (FrameOrder PDF content = full צו מסגרת text), rest are shipments |
| legal_documents | 4 | Has subcollection `sections` (8 docs about customs ordinance) |
| files | 5,001+ | File metadata from Cloud Storage uploads |
| pipeline_ingestion_log | 263 | All entries are classification_directives from shaarolami |

## Cloud Storage Key Files
| File | Size | Notes |
|------|------|-------|
| AllCustomsBookDataPDF.pdf | 35.9 MB | Full tariff book (3,134 pages) — text extraction BROKEN |
| fullCustomsBookData (6).zip | 214 MB | 7z archive with 238 XML files |
| FrameOrder (3) (1).pdf | 175 KB | צו מסגרת (content already in knowledge collection) |
| tariff_xml_backup/ | 103.4 MB | 25 files — extracted XMLs + scripts backup |

## Local Data Files
- `C:\Users\doron\tariff_extract\` — extracted XMLs from 7z archive
- `C:\Users\doron\fullCustomsBookData.zip` — the 7z archive (214 MB)
- `C:\Users\doron\Desktop\doronrpa\tariff_data\tariff_full_text.txt` — 7.3 MB, source for tariff collection
- `C:\Users\doron\Desktop\doronrpa\full_upload.py` — original upload script (regulatory data only)
- `C:\Users\doron\sa-key.json` — service account key for rpa-port-customs
- `C:\Users\doron\Downloads\AllCustomsBookDataPDF (4).pdf` — freshly downloaded tariff PDF

## Git Commits (Session B)
- `0df6183` — shipping_knowledge.py + librarian_index + doc_reader signals
- `d85f686` — Phase 2: ocean_tracker.py + tracker.py wiring + email sections
- `25af8d1` — Consolidate Global Tracking email
- `6c0e9cf` — POL/POD timing table + BL/container summary
- `32e6cc7` — All timestamps in Israel time

## Git Commits (Session D — Tariff)
- `f1b7a44` — Block C1: Shaarolami tariff description scraper + 2,104 descriptions filled
- `3ea16b5` — Backup: audit docs + seed keywords script from C1/C2 sessions

## Git Commits (Session E — Cost Optimization + Port Schedule Live Deploy)
- `c01c431` — Cost optimization + Daily IL port schedule module
- `7b265f9` — Fix Ashdod port schedule storage: sanitize vessel names and carrier keys

## Git Commits (Session F — C2 Wiring)
- `ce46f89` — Block C2: Chapter notes parser + tariff structure tooling
- `f810b20` — Fix test_tool_calling: update tool count for lookup_tariff_structure
- `2cb4f61` — C2 wiring: expose new chapter note fields + fix Hebrew exclusion regex

## Session E Summary (2026-02-17) — Cost Optimization + Port Schedule Deploy & Test

### What Was Done

**1. Cost Optimization — AI Model Routing**
Switched expensive Claude calls to cheaper Gemini where quality allows:

**`functions/lib/tool_calling_engine.py`** (MODIFIED):
- Added `_GEMINI_MODEL = "gemini-2.5-flash"` as PRIMARY for tool-calling
- Added `_PREFER_GEMINI = True` flag (toggle to switch back to Claude)
- Added `_call_gemini_with_tools()` — Gemini function calling format (functionCall/functionResponse)
- Added `_run_gemini_tool_loop()` — full tool loop with Gemini, auto-falls back to Claude on failure
- Imports `GEMINI_TOOLS` from tool_definitions.py (was already prepared but unused)
- **Savings: ~$190/month** (tool-calling: $200 → $10)

**`functions/lib/cross_checker.py`** (MODIFIED):
- Replaced Claude Sonnet with Gemini Pro in 3-way cross-check
- New lineup: Gemini Pro + Gemini Flash + GPT-4o-mini (3 independent models)
- Added `_call_gemini_pro_check()` function
- **Savings: ~$160/month** (cross-check: $200 → $40)

**2. Daily IL Port Schedule Module — Created, Deployed, Live-Tested**

**`functions/lib/schedule_il_ports.py`** (NEW ~750 lines):
- 6 FREE data sources for vessel schedules at Israeli ports
- Merge/dedup engine with priority: TaskYam > Carrier API > Haifa Port > ZIM > Email > AIS
- `_sanitize_vessel_name()` — strips \r\n\t, collapses whitespace (fix for Ashdod bug)
- `_store_port_schedule()` — stores to `port_schedules` (MD5 doc IDs from dedup key)
- `_store_daily_report()` — stores to `daily_port_report` (doc ID: `ILHFA_2026-02-17`)
- `build_schedule_email_html()` — Hebrew RTL HTML email with vessel tables per port
- `is_schedule_email()` / `process_schedule_email()` — detect and parse schedule emails from CC

**`functions/main.py`** (MODIFIED):
- Added `rcb_port_schedule()` — Cloud Function, runs every 12 hours, 512MB, 300s timeout
- Added schedule email detection in CC email handler (after tracker, before classification)

**`functions/lib/librarian_index.py`** (MODIFIED):
- Added `port_schedules` and `daily_port_report` to COLLECTION_FIELDS

### Live Test Results (Production Firestore)
| Port | Vessels | Collection | Status |
|------|---------|------------|--------|
| Haifa (ILHFA) | 36 | `daily_port_report/ILHFA_2026-02-17` | Stored OK |
| Ashdod (ILASD) | 9 | `daily_port_report/ILASD_2026-02-17` | Stored OK (after fix) |
| Eilat (ILELT) | 0 | N/A | Expected (port closed) |
| **Total** | **45** | `port_schedules` (45 docs) | All OK |

HTML email report: 27,974 chars generated successfully.

### Bugs Found & Fixed During Live Test
1. **Ashdod vessel name with newline**: `YM WITNESS\nVOY` → Fixed by `_sanitize_vessel_name()`
2. **Empty Firestore map key**: `shipping_line: ""` created empty key in carrier_breakdown dict → Fixed: `v.get("shipping_line", "") or "Unknown"`
3. **All string values sanitized** before Firestore storage (strip \r\n\t)

### Known Limitations (Expected)
- **Carrier APIs**: Return 0 locally (secrets only in Cloud Secret Manager) — will work in cloud
- **Haifa Port portal**: Connection timeout (geo-restricted or down) — handled gracefully
- **ZIM Expected Vessels**: 0 results (JS-rendered page, no embedded JSON) — handled gracefully
- **AIS (aisstream.io)**: Needs `AISSTREAM_API_KEY` in Secret Manager (free registration)

### Deployment Status
- All 30 functions deployed to Firebase (2026-02-17)
- `rcb_port_schedule` runs every 12 hours via Cloud Scheduler
- Schedule email detection active in CC email handler

### TODO for Future Sessions
- Register at aisstream.io (free) and add `AISSTREAM_API_KEY` to Secret Manager
- Configure carrier API secrets: `MAERSK_CONSUMER_KEY`, `ZIM_API_TOKEN`, `HAPAG_CLIENT_ID`, `HAPAG_CLIENT_SECRET`, `COSCO_API_KEY`, `COSCO_SECRET_KEY`
- Monitor `rcb_port_schedule` cloud function logs to verify scheduled execution
- Consider adding Ashdod Port scraper (ashdodport.co.il — ASP.NET, may need session handling)
- C2 remaining: 25 chapters without XML data — check if they have chapter notes via shaarolami scraping
- Block D (Elimination Engine) is now UNBLOCKED — can proceed with tree-walking logic

## Session F Summary (2026-02-17) — C2 Wiring + CI Fix

### What Was Done

**1. Fixed CI Build #151 (RED → GREEN)**
- `test_tool_calling.py`: Tests expected 8 tools but ce46f89 added `lookup_tariff_structure` as 9th tool
- Updated tool count assertions (8→9) and added `lookup_tariff_structure` to expected name set
- Build #162 GREEN in 40s

**2. Seeded `tariff_structure` Collection (137 docs)**
- Ran `seed_tariff_structure.py` against production Firestore
- 22 sections, 98 chapters, 13 additions, metadata, full_tariff, discount_codes, framework_order
- keyword_index: 1 new keyword added (239 already existed from B2 seeding)
- librarian_index: 137 tariff_structure docs re-indexed

**3. Wired `_get_chapter_notes()` with C2 Fields**
- `tool_executors.py`: Now returns `preamble_en`, `notes_en`, `supplementary_israeli`, `subheading_rules`
- These fields were populated by `parse_chapter_notes_c2.py` but tool didn't expose them

**4. Fixed Hebrew Exclusion Regex in `justification_engine.py`**
- `challenge_classification()` METHOD 1 used `r'(?:chapter)\s*(\d{1,2})'` — English only
- Fixed to `r'(?:chapter|פרק|בפרק|לפרק)\s*(\d{1,2})'` — matches Hebrew chapter references
- Exclusion text from RuleDetailsHistory.xml is in Hebrew, so the regex was completely dead

**5. Resolved Missing Chapter Notes (50, 53, 77, 98)**
- **Chapters 50 (Silk), 53 (Other veg textile)**: Verified against XI.pdf — no chapter-specific notes exist; Section XI notes apply
- **Chapter 77**: Reserved chapter in HS nomenclature
- **Chapter 98**: Israeli special chapter
- All 4 marked in Firestore with `no_chapter_notes_confirmed: true`

### Changes Made
| File | Change |
|------|--------|
| `functions/tests/test_tool_calling.py` | Tool count 8→9, added lookup_tariff_structure to expected set |
| `functions/lib/tool_executors.py` | 4 new fields in _get_chapter_notes() return dict |
| `functions/lib/justification_engine.py` | Hebrew patterns added to exclusion regex |

### Firestore Updates (not in code)
| Collection | Action |
|-----------|--------|
| `tariff_structure` | 137 docs seeded (sections, chapters, additions, metadata) |
| `chapter_notes/chapter_50` | Marked: no chapter notes, Section XI applies |
| `chapter_notes/chapter_53` | Marked: no chapter notes, Section XI applies |
| `chapter_notes/chapter_77` | Marked: reserved chapter |
| `chapter_notes/chapter_98` | Marked: Israeli special chapter |
| `keyword_index` | 1 new entry (239 skipped — already existed) |
| `librarian_index` | 137 tariff_structure entries indexed |

## Session 32 Summary (2026-02-17 evening) — Block C3: Free Import Order

### What Was Done

**1. Verified All 5 Session F Items — ALL COMPLETE**
- tariff_structure 137 docs ✓
- tool_executors C2 fields ✓
- justification_engine Hebrew regex ✓
- Chapters 50/53 resolved ✓
- CLAUDE.md updated ✓

**2. Block C3: צו יבוא חופשי — Free Import Order Seeded**
Discovered structured JSON from data.gov.il (39 MB, 28,899 records) in Cloud Storage — far superior to PDF parsing.

**Source data in Cloud Storage:**
- `צו יבוא חופשי.zip` (13.6 MB) — 46 amendment PDFs (2014-2025)
- `agent/free_import_order/20260201_download_20260201_141544.json` (39 MB) — structured data.gov.il API dump

**`functions/seed_free_import_order_c3.py`** (NEW):
- Parses data.gov.il JSON → groups by HS code → seeds Firestore
- 6,121 docs in `free_import_order/` collection + `_metadata` doc
- 6,121 entries in `librarian_index/` (prefix: fio_)
- Handles active/expired records, computes summaries per HS code

**`functions/lib/tool_executors.py`** (MODIFIED):
- `_check_regulatory()`: Now checks local `free_import_order` first → live API fallback
- `_lookup_local_fio()`: New method — exact doc match + parent code range query

**`functions/lib/librarian_index.py`** (MODIFIED):
- Added `free_import_order` to COLLECTION_FIELDS (doc_type: regulatory)

### Data Coverage
| Dimension | Count |
|-----------|-------|
| Total records | 28,899 |
| Unique HS codes | 6,121 |
| Chapters | 87 of 99 |
| Active records | 25,892 |
| Expired records | 3,007 |
| Authorities | 18 |
| Appendices | 3 (תוספת 1, 2, 4) |

### Firestore Updates
| Collection | Action |
|-----------|--------|
| `free_import_order` | 6,121 HS code docs + 1 metadata doc |
| `librarian_index` | 6,121 entries (prefix: fio_) |

### Block Status After Session 32
- **C1**: Tariff descriptions ✓
- **C2**: Chapter notes ✓
- **C3**: Free Import Order ✓ ← NEW
- **C4-C8**: Not started
- **Block D**: Elimination Engine — READY (C1+C2+C3 provide data foundation)
