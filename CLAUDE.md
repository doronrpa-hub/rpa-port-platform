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

### Block D: Elimination Engine — FULLY COMPLETE (Session 33, D1-D9)
**Status: Engine built (2,282 lines) + wired into pipeline (D9). 13 tools total. All green.**

**File created:** `functions/lib/elimination_engine.py` (2,282 lines)

**Pipeline levels (in order):**
| Level | Name | Block | What It Does |
|-------|------|-------|-------------|
| 0 | ENRICH | D1 | Resolve chapter→section for each candidate |
| 1 | SECTION SCOPE | D1 | Eliminate candidates from clearly wrong sections |
| 2a | PREAMBLE SCOPE | D2 | Check chapter preamble scope statements |
| 2b | CHAPTER EXCLUSIONS/INCLUSIONS | D1+D2 | Parse chapter notes, match product against exclusion/inclusion text |
| 2c | CROSS-CHAPTER REDIRECT | D2 | Boost candidates referenced by other chapter exclusions |
| 2d | DEFINITION MATCHING | D2 | Match product against "in this chapter X means..." definitions |
| 3 | GIR 1 HEADING MATCH | D3 | Composite scoring: 0.5×keyword + 0.25×specificity + 0.25×attribute |
| 3b | SUBHEADING NOTES | D3 | Apply subheading-level rules from chapter notes |
| 4a | GIR 3 TIEBREAK | D4 | 3א most specific, 3ב essential character, 3ג last numerical |
| 4b | OTHERS GATE + PRINCIPALLY | D5 | Suppress "אחרים" catch-alls when specific headings exist; composition test |
| 4c | AI CONSULTATION | D6 | Gemini Flash primary, Claude fallback via call_ai() |
| 5 | BUILD RESULT | D1 | Assemble EliminationResult from survivors/eliminated/steps |
| 6 | DEVIL'S ADVOCATE | D7 | Counter-arguments per survivor; challenges[] in result |
| 7 | ELIMINATION LOGGING | D8 | Write to Firestore `elimination_log` collection |

**Public API:**
```python
eliminate(db, product_info, candidates, api_key=None, gemini_key=None) -> EliminationResult
candidates_from_pre_classify(pre_classify_result) -> list[HSCandidate]
make_product_info(item_dict) -> ProductInfo
```

**Key dependencies reused (not modified):**
- `justification_engine.py:522` — Hebrew chapter reference regex
- `intelligence.py:1369-1381` — Keyword extraction, stop words
- `tool_executors.py:205-343` — Chapter notes + tariff structure Firestore reads
- `classification_agents.py:466-494` — `call_ai()` router for D6/D7

**Firestore collections used:**
- `chapter_notes` (read) — chapter exclusions, inclusions, preamble, definitions
- `tariff_structure` (read) — section→chapter mapping, section scope
- `tariff` (read) — heading descriptions for GIR 1 matching
- `elimination_log` (write, NEW) — full elimination audit trail per run

**Git commits:**
| Block | SHA | Description | Lines |
|-------|-----|-------------|-------|
| D1 | `2841a07` | Core tree walk, TariffCache, section/chapter/heading | +801 |
| D2+D3 | `8b9e370` | Chapter notes + GIR 1 full semantics | +606 |
| D4+D5 | `e485b65` | GIR 3 tiebreak + Others gate + principally test | +563 |
| D6+D7+D8 | `e3913eb` | AI consultation + devil's advocate + elimination logging | +378 |
| D9 | `0bb0a2f` | Pipeline wiring: 13th tool, full pipeline + tool-calling integration | +235 |

**D9 (pipeline wiring) — DONE (Session 33):**
- `classification_agents.py`: `eliminate()` wired between pre_classify and Agent 2 in `run_full_classification()`
- `classification_agents.py`: `_build_elimination_context()` formats survivors/steps for Agent 2 context
- `classification_agents.py`: `ELIMINATION_ENABLED = True` feature flag, `ELIMINATION_AVAILABLE` import guard
- `classification_agents.py`: `elimination_results` included in final output dict
- `tool_definitions.py`: `run_elimination` added as 13th tool (Claude + Gemini formats), system prompt updated
- `tool_executors.py`: `_run_elimination()` handler — builds ProductInfo, runs eliminate(), returns concise summary
- `tests/test_tool_calling.py`: Count 12→13, `run_elimination` in expected set

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

### Block Status After Session 32 (afternoon)
- **C1**: Tariff descriptions ✓
- **C2**: Chapter notes ✓
- **C3**: Free Import Order ✓
- **C4-C8**: Not started
- **Block D**: Elimination Engine — READY (C1+C2+C3 provide data foundation)

## Session 32 Evening Summary (2026-02-17) — Blocks C4+C5+C6+C8 Done

### Overview
Completed 4 remaining C-blocks in one session. All 12 tools now wired and live. C7 (pre-rulings) blocked on data source.

### Block C5: Framework Order (צו מסגרת) — DONE (commit 545c146)
- `functions/seed_framework_order_c5.py` (NEW): Parses knowledge doc + AdditionRulesDetailsHistory.xml
- **85 docs** seeded to `framework_order` collection: 31 definitions, 13 FTA clauses, 2 classification rules, 38 additions
- `tool_executors.py`: Added `_lookup_framework_order()` — 6 query types (definitions, def:term, fta, country, classification_rules, addition by ID)
- `tool_executors.py`: Enhanced `_lookup_fta()` with `_lookup_fw_fta_clause()` — FTA clause enrichment from framework_order
- `tool_definitions.py`: Added `lookup_framework_order` tool definition
- `librarian_index.py`: Added `framework_order` to COLLECTION_FIELDS
- Tests updated: 9→10 tools

### Block C6: Classification Directives (הנחיות סיווג) — DONE (commit 3e66ad8)
- `functions/enrich_directives_c6.py` (NEW): Regex enrichment of 218 existing hollow directives
- **218/218 enriched** at zero AI cost — regex extraction from consistent shaarolami HTML template
- Fields extracted: directive_id, title, directive_type, primary_hs_code, related_hs_codes, dates, content, is_active
- `tool_executors.py`: Replaced `_stub_not_available` with real `_search_classification_directives()` — 4 search strategies (HS code, chapter, directive_id, keyword)
- `tool_definitions.py`: Added `search_classification_directives` tool definition
- Tests updated: 10→11 tools

### Block C4: Free Export Order (צו יצוא חופשי) — DONE (commit ad3a399)
- `functions/seed_free_export_order_c4.py` (NEW): Parses data.gov.il JSON (CustomsBookType: "יצוא")
- **979 HS code docs** seeded from 1,704 records, 35 chapters, 7 authorities
- Source: `agent/data_gov_structured/20260201_download_20260201_143141.json` in Cloud Storage
- `tool_executors.py`: Added `_lookup_local_feo()`, enhanced `_check_regulatory()` to return `free_export_order` alongside `free_import_order`
- `tool_definitions.py`: Updated `check_regulatory` description to mention C4 Free Export Order
- `librarian_index.py`: Added `free_export_order` to COLLECTION_FIELDS
- Tests updated: 11→12 tools

### Block C8: Legal Knowledge — DONE (commit b35d0a4)
- `functions/seed_legal_knowledge_c8.py` (NEW): Multi-source legal document parser
- **19 docs** seeded to `legal_knowledge` collection:
  - 15 Customs Ordinance chapters (פקודת המכס, parsed from 272K chars in `legal_documents/pkudat_mechess`)
  - 1 Customs Agents Law reference (extracted from Chapter 11, 130K chars, 9 law references)
  - 1 EU Reform reference (מה שטוב לאירופה, effective 2014, legal basis: החלטת ממשלה 2118)
  - 1 US Reform reference (מה שטוב לארצות הברית, effective 2019, legal basis: החלטת ממשלה 4440)
  - 1 Export Order legal text (from `legal_documents/tzo_yetzu_hofshi`, 20K chars)
- `tool_executors.py`: Added `_search_legal_knowledge()` — 5 search cases (chapter by number, customs agents, EU reform, US reform, keyword)
- `tool_definitions.py`: Added `search_legal_knowledge` tool definition
- `librarian_index.py`: Added `legal_knowledge` to COLLECTION_FIELDS

### Block C7: Pre-Rulings (פרה-רולינג) — BLOCKED
- All shaarolami URL patterns return 200 with 0 bytes (WAF blocking)
- No alternative data source found
- Stub remains in tool_executors.py dispatcher

### Tool-Calling Engine: 13 Active Tools
| # | Tool | Source | Wired |
|---|------|--------|-------|
| 1 | check_memory | classification_memory | Session A |
| 2 | search_tariff | tariff, keyword_index, product_index, supplier_index | Session A |
| 3 | check_regulatory | regulatory baseline + free_import_order (C3) + free_export_order (C4) | C3+C4 |
| 4 | lookup_fta | FTA rules + framework_order FTA clauses (C5) | C5 |
| 5 | verify_hs_code | tariff collection | Session A |
| 6 | extract_invoice | Gemini Flash | Session A |
| 7 | assess_risk | Rule-based (dual-use chapters, high-risk origins) | Session A |
| 8 | get_chapter_notes | chapter_notes (C2) | C2 |
| 9 | lookup_tariff_structure | tariff_structure (C2) | C2 |
| 10 | lookup_framework_order | framework_order (C5) | C5 |
| 11 | search_classification_directives | classification_directives (C6) | C6 |
| 12 | search_legal_knowledge | legal_knowledge (C8) | C8 |
| 13 | run_elimination | elimination_engine (D1-D8) — deterministic tariff tree walk | D9 |

### Firestore Collections Seeded This Session
| Collection | Docs | Block |
|-----------|------|-------|
| `framework_order` | 85 + metadata | C5 |
| `classification_directives` | 218 enriched | C6 |
| `free_export_order` | 979 + metadata | C4 |
| `legal_knowledge` | 19 + metadata | C8 |
| `librarian_index` | +1,301 entries | All |

### Git Commits This Session
- `545c146` — C5: Framework Order (85 docs, lookup_framework_order tool)
- `3e66ad8` — C6: Classification directives (218 enriched, search_classification_directives tool)
- `ad3a399` — C4: Free Export Order (979 HS codes, _lookup_local_feo in check_regulatory)
- `b35d0a4` — C8: Legal knowledge (19 docs, search_legal_knowledge tool)

### Files Modified This Session
| File | Changes |
|------|---------|
| `functions/lib/tool_executors.py` | +4 tool methods, +2 cache/lookup helpers, dispatcher 9→12 active handlers |
| `functions/lib/tool_definitions.py` | +3 tool definitions (C5/C6/C8), updated check_regulatory desc (C4), system prompt 9→12 steps |
| `functions/lib/librarian_index.py` | +3 COLLECTION_FIELDS entries (framework_order, free_export_order, legal_knowledge) |
| `functions/lib/overnight_brain.py` | +5 collections in collections_to_count audit list |
| `functions/tests/test_tool_calling.py` | Tool count 9→12, expected names updated |

### Test Results
- **452 passed**, 5 failed (pre-existing BS4 issues in test_data_pipeline/test_smart_extractor/test_table_extractor — not our changes), 2 skipped

### Block Status After Session 32 Evening
- **C1**: Tariff descriptions ✓
- **C2**: Chapter notes ✓
- **C3**: Free Import Order ✓ (6,121 HS codes)
- **C4**: Free Export Order ✓ (979 HS codes)
- **C5**: Framework Order ✓ (85 docs)
- **C6**: Classification Directives ✓ (218 enriched)
- **C7**: Pre-Rulings — BLOCKED (no data source)
- **C8**: Legal Knowledge ✓ (19 docs)
- **Block D**: Elimination Engine — ✓ DONE (D1-D8, 2,282 lines)

## Session 33a Summary (2026-02-18) — Audit, Bug Verification, Caching, Merge, Cleanup

### What Was Done

**1. Full Audit Review**
- Compared Feb 16 AUDIT_REPORT.md against current codebase state
- Verified other Claude's Session 31+32 work
- Identified remaining gaps and new observations

**2. Git Remote Fixed + Pushed Working Copy**
- Fixed remote URL on `Usersdoronrpa-port-platform` working copy
- Pushed all local commits to origin/main (rebased over D-block commits)

**3. Production Bug Verification (Feb 16 Audit)**
All 3 critical bugs from the audit were ALREADY FIXED:
- Bug 1 (tracker_email kwargs): `tracker_email.py:39` already accepts `observation=None, extractions=None`
- Bug 2 (VAT 17%): `pdf_creator.py:151` already reads `vat_rate` with 18% default
- Bug 3 (orphan decorator): All decorators in `main.py` properly attached
- `seed_reference_data`: Already executed (29 docs exist: 11 container + 6 ULD + 12 package types)

**4. Per-Request Caching in tool_executors.py (Firestore read optimization)**
Reduced potential 5,000+ Firestore reads per elimination run to ~320:
- Added lazy-load caches: `_directives_docs` (218), `_framework_order_docs` (85), `_legal_knowledge_docs` (19)
- Added `_get_directives()`, `_get_framework_order()`, `_get_legal_knowledge()` cache methods
- Moved `_FTA_COUNTRY_MAP` to module-level constant (89 country entries, not rebuilt per call)
- Rewrote `_lookup_framework_order()`, `_search_classification_directives()`, `_search_legal_knowledge()` to use cached collections
- Added word-boundary regex for legal_knowledge search (`_LEGAL_EU_KEYWORDS`, `_LEGAL_US_KEYWORDS`, `_LEGAL_AGENT_KEYWORDS`) — prevents "us" matching "status"
- Fixed tool_definitions.py header "10 tools" → "12 tools"

**5. Merged session31-enhancements Branch**
- 9 commits, +917 lines merged to main with zero conflicts
- Includes: FCL/LCL detection, lifecycle tracking, CC learning, reference data, cross-check, deal intelligence
- Tests: 457 passed (up from 452)

**6. Block D: Elimination Engine (by parallel Claude session)**
- D1: Core tree-walking engine (`elimination_engine.py`, 801 lines)
- D2+D3: Chapter notes integration + GIR Rule 1
- D4+D5: GIR Rule 3 tiebreak logic (1,374 lines total)

**7. Audit Cleanup Tasks**
- Fixed dedup in `_search_classification_directives()` — added `seen_ids` set + `_add()` helper across all 4 search strategies
- Investigated 188 corrupt tariff codes: 15 chapters, 137 in ch87 (vehicles), all have empty descriptions, already flagged `corrupt_code: true`
- Added `corrupt_code` filtering in `intelligence.py:_search_tariff()` — corrupt codes now excluded from search results
- Added Firestore composite indexes for FIO/FEO range queries to `firestore.indexes.json`

### Files Modified This Session
| File | Changes |
|------|---------|
| `functions/lib/tool_executors.py` | Per-request collection caching, dedup fix, word-boundary regex, FTA_COUNTRY_MAP module-level |
| `functions/lib/tool_definitions.py` | Header fix: "10 tools" → "12 tools" |
| `functions/lib/intelligence.py` | Added `corrupt_code` filtering in `_search_tariff()` |
| `firestore.indexes.json` | Added FIO + FEO `hs_10` range query indexes |

### Git Commits This Session
- Caching + country map + regex + header fix (tool_executors + tool_definitions)
- Session31-enhancements merge
- Dedup + corrupt code filter + indexes + CLAUDE.md update

### Test Results
- **457 passed**, 5 failed (pre-existing BS4 issues), 2 skipped

## Session 33b Summary (2026-02-18) — Block D: Elimination Engine (D1-D8)

### Overview
Built the complete elimination engine in one session — all 8 sub-blocks (D1-D8). Single file created: `functions/lib/elimination_engine.py` (2,282 lines). No existing files modified. D9 (pipeline wiring) deferred.

### What Was Built

**D1 — Core Framework:** TariffCache (per-request in-memory), ProductInfo/HSCandidate/EliminationStep/EliminationResult data structures, keyword extraction (bilingual), HS code utilities, section scope elimination, chapter exclusions/inclusions, basic heading match.

**D2 — Chapter Notes Deep:** Preamble scope analysis, conditional exclusions (exception clause parsing), cross-chapter redirect detection and boosting, definition matching ("in this chapter X means...").

**D3 — GIR 1 Full Semantics:** Heading specificity scoring (penalizes vague/others headings), product attribute matching (material/form/use terms), composite scoring (0.5×keyword + 0.25×specificity + 0.25×attribute), relative elimination (bottom 30% removed), subheading notes application.

**D4 — GIR Rule 3 Tiebreak:** 3א (most specific description wins), 3ב (essential character — material composition dominance), 3ג (last numerical — fallback when 3a/3b inconclusive). Each stage only fires when needed.

**D5 — Others Gate + Principally Test:** Detects "אחרים"/"others"/"n.e.s." catch-all headings, suppresses them when specific alternatives exist. "באופן עיקרי"/"principally" composition test for headings requiring material dominance.

**D6 — AI Consultation:** Fires when >3 survivors remain after rule-based elimination. Gemini Flash primary, Claude fallback via `call_ai()`. Structured JSON prompt with product info + candidates + elimination history. Graceful no-op when API keys missing.

**D7 — Devil's Advocate:** Generates counter-arguments for each surviving candidate. Identifies strongest alternative classification and risk areas. Results stored as `challenges[]` in EliminationResult. Graceful no-op when API keys missing.

**D8 — Elimination Logging:** Writes full audit trail to Firestore `elimination_log` collection. Includes all steps, survivors, eliminated codes, AI consultations, devil's advocate challenges. All writes wrapped in try/except (logging failure never breaks classification).

### Git Commits (Session 33b)
- `2841a07` — D1: Core tree walk, TariffCache, section/chapter/heading (+801 lines)
- `8b9e370` — D2+D3: Chapter notes deep + GIR 1 full semantics (+606 lines)
- `e485b65` — D4+D5: GIR 3 tiebreak + Others gate + principally test (+563 lines)
- `e3913eb` — D6+D7+D8: AI consultation + devil's advocate + elimination logging (+378 lines)

### Files
| Action | File | Lines |
|--------|------|-------|
| **CREATE** | `functions/lib/elimination_engine.py` | 2,282 |

### Block Status After Session 33
- **Block A**: ✓ (A1-A4)
- **Block B**: ✓ (B1-B2)
- **Block C**: ✓ (C1-C6, C8) — C7 blocked
- **Block D**: ✓ FULLY COMPLETE (D1-D9) — engine built + wired into pipeline + 13th tool
- **Block E-H**: Not started
- **188 corrupt tariff codes**: Flagged + excluded from search (not fixable from available sources)

## Session 34 Summary (2026-02-18) — Gap 2: Auto-trigger Classification from Tracker

### Problem
83% of CC emails are shipping correspondence (BL, arrival notice, packing list). Classification only triggered from Block A1 (keyword match for "invoice" in the *current* email's text). When a deal accumulated invoice + shipping docs across *separate* emails, classification never fired. This was the #1 pipeline gap.

### What Was Done

**Gap 2: Auto-trigger classification when deal has invoice + shipping doc**

When a tracker deal accumulates both an invoice and at least one shipping document (BL, packing list, arrival notice, delivery order) across separate CC emails, classification now auto-triggers using aggregated text from all deal observations.

### Files Modified

| File | Changes |
|------|---------|
| `functions/lib/tracker.py` | `doc_text_preview` on observations, `_is_deal_classification_ready()`, classification readiness check in `_update_deal_from_observation`, `classification_ready` flag propagation, `internet_message_id` on observations/deals |
| `functions/main.py` | Capture `tracker_result` in CC handler, `_aggregate_deal_text()` helper, Gap 2 auto-trigger block after Block A1 |
| `functions/lib/tracker_email.py` | RTL Hebrew support, improved subject lines with direction labels, status badges, responsive font sizes |

### Flow After Changes
```
CC email → main.py CC handler:
  1. Pupil (silent learning)
  2. tracker_process_email():
     → updates deal, adds new doc to documents_received
     → checks _is_deal_classification_ready()
     → returns classification_ready=True if invoice+shipping doc + no prior classification
  3. Schedule email detection
  4. Block A1: if "invoice" keyword in current email → classify (unchanged)
  5. NEW Gap 2: if Block A1 didn't fire AND classification_ready:
     → aggregate text from all deal observations (doc_text_preview)
     → call process_and_send_report() with aggregated text
     → link classification to deal via rcb_classification_id
```

### Guards Against Double-Triggering
1. `rcb_classification_id` — already-classified deals skipped
2. `classification_auto_triggered_at` — set BEFORE classification starts (race guard)
3. `_cc_classified` flag — Block A1 and auto-trigger mutually exclusive per email
4. Existing `_link_classification_to_tracker()` bridge sets `rcb_classification_id` on success

### Git Commit
- `bcef70a` — Gap 2: Auto-trigger classification when tracker deal accumulates invoice + shipping docs

### Test Results
- **457 passed**, 2 skipped — no regressions

## Session 34b Summary (2026-02-18) — Elimination Engine Live Testing + 3 Bug Fixes

### What Was Done

Ran the elimination engine against production Firestore with 3 test products. Found and fixed 3 bugs. All 3 tests pass after fixes.

### Bugs Found & Fixed in `elimination_engine.py`

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| `chapter_names` crash (TypeError) | `tariff_structure` stores chapter names as `{name_he, name_en}` dicts; code called `.values()` expecting strings | Unwrap dicts, extract both `name_he` and `name_en` fields |
| Section scope too aggressive (false eliminations) | `_extract_keywords` capped at 15 words — section text spanning 12 chapters got truncated. Also Hebrew prefixes (`מפלדה` vs `פלדה`) prevented matching | Added `limit` parameter (100 for sections, 30 for products); added Hebrew prefix stripping (מ,ב,ל,ה,ו,כ,ש); included material/form/use in product keywords |
| No last-survivor safety (0 survivors possible) | Section scope could eliminate ALL candidates if all sections had zero overlap | Added guard: skip section elimination when no alive candidates would remain outside that section |

### Live Test Results (3 products, production Firestore)

**Test 1: Steel storage boxes → ch.73 (7326.9000) — PASS, 1 survivor**
```
5 candidates → Section scope kills ch.94 (furniture, Section XX) and ch.44 (wood, Section IX)
            → GIR 1 kills ch.83 8310 (sign-plates, score 0.10 vs best 0.38)
            → GIR 3b kills 7310 (sealed containers — doesn't match open/foldable)
            → Survivor: 7326.9000 "Other articles of iron or steel" ✓
```

**Test 2: Rubber gloves (medical) → ch.40 (4015.1900) — PASS, 1 survivor**
```
5 candidates → Section scope kills ch.61 + ch.62 (textiles, Section XI — rubber ≠ textiles)
            → GIR 1 kills ch.39 3926 (plastic apparel, score 0.17 vs best 0.79)
            → GIR 3b kills ch.90 9018 (medical instruments — essential material is rubber, not instruments)
            → Survivor: 4015.1900 "Gloves of vulcanized rubber" ✓
```

**Test 3: Li-ion battery (EV) → ch.85 (8507.6000) — PASS, 3 survivors (needs_ai=True)**
```
5 candidates → GIR 1 kills 8541 (semiconductors, score 0.17) and 8708 (vehicle parts, score 0.17)
            → GIR 3c boosts 8703 (last numerical) but can't eliminate — 3 tied
            → Survivors: 8507.6000 (Li-ion accumulators, conf=70) ✓
                         8703.8000 (electric vehicles, conf=41)
                         8501.3200 (electric motors, conf=30)
            → needs_ai=True — D6 AI consultation would resolve in production
```

### Elimination Engine Levels Exercised

| Level | Exercised | Eliminations Made |
|-------|-----------|-------------------|
| Level 0: Enrich (section resolution) | All 3 tests | — (enrichment only) |
| Level 1: Section scope | Tests 1, 2 | ch.94, ch.44, ch.61, ch.62 eliminated |
| Level 2a-2d: Chapter notes | All 3 tests | No eliminations (notes didn't trigger) |
| Level 3: GIR 1 heading match | All 3 tests | ch.83 8310, ch.39 3926, ch.85 8541, ch.87 8708 |
| Level 3b: Subheading notes | All 3 tests | No eliminations |
| Level 4a: GIR 3 tiebreak | Tests 1, 2, 3 | 7310, 9018 eliminated via GIR 3b |
| Level 4b: Others gate | All 3 tests | No eliminations |
| Level 4c: AI consultation (D6) | Skipped | No API keys (deterministic-only run) |
| Level 6: Devil's advocate (D7) | Skipped | No API keys |
| Level 7: Elimination logging (D8) | All 3 tests | 3 docs written to `elimination_log` |

### Files Modified
| File | Changes |
|------|---------|
| `functions/lib/elimination_engine.py` | 3 bug fixes: chapter_names dict handling, keyword extraction limit+Hebrew prefixes, last-survivor safety guard |
| `functions/test_elimination_live.py` | NEW: 3-scenario live test script against production Firestore |

### Git Commit
- `b438e39` — Fix 3 elimination engine bugs found by live Firestore testing

### Test Results
- **457 passed**, 2 skipped — no regressions
- **3/3 live elimination tests pass** — correct chapters survive in all scenarios
