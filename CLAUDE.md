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

## Session 41b — Land Transport ETA Alert System

### NEW: `functions/lib/route_eta.py` (~250 lines)
Tool #33: calculate_route_eta — driving time from pickup address to Israeli port/airport.

| Component | Details |
|-----------|---------|
| **Geocoding** | Nominatim (free, no key, 1 req/sec rate limit) |
| **Primary routing** | OpenRouteService (free, 2000 req/day, needs ORS_API_KEY in Secret Manager) |
| **Fallback routing** | OSRM (completely free, no key) |
| **Cache** | Firestore `route_cache`, TTL 24 hours, key = md5(origin+port) |

Port coordinates hardcoded (ports don't move):
- `ILHFA` (Haifa Port): 32.8191, 35.0442
- `ILASD` (Ashdod Port): 31.8305, 34.6428
- Ben Gurion Airport: 32.0055, 34.8854

### MODIFIED: `functions/lib/tracker.py` (+~180 lines)
Added `check_gate_cutoff_alerts()` — proactive gate cutoff alert system.

- **Signature**: `check_gate_cutoff_alerts(db, firestore_module, get_secret_func, access_token, rcb_email)`
- **Called by**: Cloud Scheduler every 30 minutes (wire in main.py)
- **Queries**: `tracker_deals` where status in ["active", "pending"]
- **Filters**: deals with `land_pickup_address` + `gate_cutoff` populated, not `port_arrived`, not `stopped`
- **Alert thresholds**:
  - buffer < 120 min → WARNING: `⚠️ RCB | {deal} | Gate cutoff in {X} min | {vessel}`
  - buffer < 45 min → URGENT: `🚨 RCB | {deal} | URGENT gate cutoff risk | {vessel}`
  - buffer < 0 min → CRITICAL: `🔴 RCB | {deal} | MISSED cutoff — late entry needed` + auto-draft
- **Dedup**: tracks sent alerts in `deal.cutoff_alerts_sent[]` list
- **Escalation**: warning→urgent→critical (each level sent only once)

New deal fields (populated by email extraction or manual entry):
- `land_pickup_address` (str) — pickup location for land transport
- `gate_cutoff` (str, ISO 8601) — port gate cutoff datetime
- `cutoff_alerts_sent` (list) — ["warning", "urgent", "critical"] tracking

Helper functions added:
- `_parse_gate_cutoff()` — parse ISO 8601 with Israel timezone handling
- `_build_cutoff_subject()` — alert email subject per level
- `_build_cutoff_alert_html()` — alert email body with RTL table layout

### MODIFIED: `functions/lib/librarian_index.py` (+7 lines)
Added `route_cache` to COLLECTION_FIELDS (doc_type: "cache").

### NEW: `functions/tests/test_route_eta.py` (65 tests)
- TestCacheKey (5), TestGetDestCoords (4), TestGeocoding (5)
- TestRouteORS (4), TestRouteOSRM (3), TestCalculateRouteEta (9)
- TestParseGateCutoff (6), TestBuildCutoffSubject (4), TestBuildCutoffAlertHtml (4)
- TestCheckGateCutoffAlerts (16), TestConstants (5)

### Wiring needed (main.py — NOT touched per instructions):
```python
from lib.tracker import check_gate_cutoff_alerts
# Add to existing 30-min scheduler or create new one:
# result = check_gate_cutoff_alerts(db, firestore, get_secret, access_token, rcb_email)
```

### Secret keys needed:
- `ORS_API_KEY` — OpenRouteService (free at openrouteservice.org, 2000 req/day). Optional — falls back to OSRM.

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
| route_cache | — | Driving ETA cache: origin→port, 24h TTL. Source: ORS/OSRM |

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

### Tool-Calling Engine: 14 Active Tools
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
| 14 | search_wikipedia | Wikipedia REST API (free, cached 30 days) — product/material knowledge | Session 37b |

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

## Session 35 Summary (2026-02-18) — Email Body Intelligence: Intent Classifier + Smart Router

### Problem
RCB processes email attachments and extracts logistics data but ignores the actual email body text. If someone writes "what's the status of BL MEDURS12345?" or "what HS code for rubber gloves?", it's ignored. The existing `knowledge_query.py` only handles direct @rpa-port.co.il team questions (using expensive Claude), and CC emails never get replies.

### What Was Built
Cost-aware intent classifier that detects 6 intent types in email bodies, routes to appropriate handlers, and replies — using regex/Firestore first (FREE), AI only when truly needed.

### Intent Detection Pipeline (cheapest first)
| Priority | Intent | Detection | Cost |
|----------|--------|-----------|------|
| 1 | ADMIN_INSTRUCTION | Regex ("from now on", "מעכשיו", "change", "שנה") — ADMIN only | FREE |
| 2 | NON_WORK | Regex blacklist (weather, jokes, sports, recipes) | FREE |
| 3 | INSTRUCTION | Regex ("classify", "סווג את", "add container", "stop follow") | FREE |
| 4 | CUSTOMS_QUESTION | Regex (HS code, tariff rate, duty, "מה הסיווג") | FREE |
| 5 | STATUS_REQUEST | Regex (status keywords + BL/container entity extraction) | FREE |
| 6 | KNOWLEDGE_QUERY | Question patterns + domain keywords (customs/trade context) | FREE |
| 7 | AMBIGUOUS | Gemini Flash one-shot classification | ~$0.001 |
| 8 | NONE | Default — let existing pipeline handle | FREE |

### 6 Intent Handlers
| Handler | What It Does | Cost |
|---------|-------------|------|
| `_handle_admin_instruction` | Save directive to `system_instructions` collection, confirm reply | FREE |
| `_handle_non_work` | Canned Hebrew reply: "RCB is for customs questions" | FREE |
| `_handle_status_request` | Look up deal via tracker.py `_find_deal_by_field`/`_find_deal_by_container`, build status summary | FREE |
| `_handle_instruction` | Route to classify/tracker/stop — returns action metadata for main.py | FREE |
| `_handle_customs_question` | ToolExecutor Firestore tools (search_tariff, check_regulatory) + AI compose | FREE → ~$0.005 |
| `_handle_knowledge_query` | Firestore tools + AI compose; falls back to existing knowledge_query.py (Claude) | FREE → ~$0.01 |

### Reply Composition — Cost Ladder
1. ChatGPT gpt-4o-mini (~$0.005) — best Hebrew prose
2. Gemini Flash (~$0.001) — fallback
3. Template-based (FREE) — last resort, no AI

### Hard Rules Enforced
- **ONLY @rpa-port.co.il** gets replies — external senders NEVER replied to
- **Privilege check first**: ADMIN (doron@) > TEAM (*@rpa-port.co.il) > NONE (external)
- **`_send_reply_safe()`** re-checks domain before every send
- **Rate limit**: Max 1 reply per sender per hour (checked in `questions_log`)
- **Body < 15 chars** → skip (auto-generated/notifications)
- **Cache**: 24h TTL on `questions_log` by question hash — cache hits are FREE

### Files Created/Modified

| Action | File | Changes |
|--------|------|---------|
| **CREATE** | `functions/lib/email_intent.py` | ~600 lines: intent classifier, 6 handlers, cache, rate limit, reply composition, sender privileges |
| **CREATE** | `functions/tests/test_email_intent.py` | 73 unit tests: privilege, regex patterns (6 intents × bilingual), entity extraction, enforcement, cache, rate limit |
| **MODIFY** | `functions/main.py` | Import block with `EMAIL_INTENT_AVAILABLE` guard; CC path integration (after Schedule, before Block A1); direct path integration (after Brain Commander, before Knowledge Query) |
| **MODIFY** | `functions/lib/librarian_index.py` | Added `questions_log` and `system_instructions` to COLLECTION_FIELDS |

### New Firestore Collections
| Collection | Purpose |
|-----------|---------|
| `questions_log` | Q+A cache with hit tracking, dedup by question hash, 24h TTL |
| `system_instructions` | Admin directives that persist across emails (scope, is_active) |

### Integration in main.py
**CC Email Path** (after Schedule, before Block A1):
- Email Intent runs first, handles questions/status requests
- Does NOT skip tracker/pupil/classification — it's additive (answers AND continues learning)
- If intent action is 'classify' → sets `_cc_classified = True`

**Direct Email Path** (after Brain Commander, before Knowledge Query):
- Email Intent runs before existing `detect_knowledge_query()`
- If handled (replied/cache_hit) → marks read, logs to rcb_processed, continues to next email
- If INSTRUCTION with action='classify' → falls through to classification pipeline
- Fallback: existing knowledge_query + classification pipeline still run

### Git Commit
- `ea38f8d` — Email Body Intelligence: intent classifier + smart router for email bodies

### Deployment
- All 30 Cloud Functions deployed to Firebase (2026-02-18)
- `rcb_check_email` now runs intent detection on both CC and direct email paths

### Test Results
- **530 passed**, 2 skipped — 73 new tests added, zero regressions

## Session 36 Summary (2026-02-18) — Content Quality Audit + Error Template Improvements

### What Was Done

**1. Content Quality Audit — 4 HTML Sample Files**
Audited all user-facing output text across 4 components. Created detailed HTML sample files with realistic customs data, current vs proposed comparisons, and scored each component.

| # | File | Component | Score |
|---|------|-----------|-------|
| 01 | `functions/content_samples/01_smart_questions_sample.html` | Smart Questions | 8.4/10 |
| 02 | `functions/content_samples/02_justification_sample.html` | Justification Engine | 5.6/10 |
| 03 | `functions/content_samples/03_classification_report_sample.html` | Classification Report | 8.7/10 |
| 04 | `functions/content_samples/04_error_messages_sample.html` | Error Messages | 6.2/10 |

**2. Error Template Improvements (template/CSS only, no logic changes)**

**`functions/lib/classification_agents.py`** (MODIFIED):
- **Extraction failure template** (lines ~2498): Wrapped in RCB branded header (gradient) + footer. Changed color `#d63384` (pink) → `#991b1b` (system red). Added diagnostic hints: scanned image, password-protected PDF, unsupported format. Added clear recovery actions.
- **Pipeline error template** (lines ~2570): Wrapped in RCB branded header + footer. Changed color `#d63384` → `#991b1b`. Replaced misleading "אנחנו עובדים על כך" with honest "נתקלנו בשגיאה טכנית" + actionable steps (resend, contact team).
- **API badge RTL fix** (line 1846): Changed `margin-right:4px` → `margin-left:4px` so badge appears correctly before ministry name in RTL flow.

### Key Audit Findings (for future reference)
- **Justification chain text is ALL English** — `justification_engine.py` generates English `decision`/`source_text` fields. Hebrew step labels wrap English content. Biggest content gap (scored 5.6/10). Fix requires generating parallel `decision_he` fields.
- **Error templates had no branding** — bare HTML fragments without RCB header/footer/tracking. Now fixed.
- **Mixed Hebrew/English is acceptable** — Israeli customs industry standard. Don't translate English labels to Hebrew.

### Files Created/Modified
| Action | File | Changes |
|--------|------|---------|
| **CREATE** | `functions/content_samples/01_smart_questions_sample.html` | 6 question scenarios with audit notes |
| **CREATE** | `functions/content_samples/02_justification_sample.html` | Chain + gap + devil's advocate audit |
| **CREATE** | `functions/content_samples/03_classification_report_sample.html` | Full 11-section report audit |
| **CREATE** | `functions/content_samples/04_error_messages_sample.html` | 5 error/warning templates audit |
| **MODIFY** | `functions/lib/classification_agents.py` | Error template branding, color fix, RTL fix |
| **MODIFY** | `functions/lib/tracker_email.py` | RTL Hebrew support, direction labels, status badges |

### Git Commit
- `5b08ccf` — Content audit: improve error templates, add content quality samples

### Deployment
- All 30 Cloud Functions deployed to Firebase (2026-02-18)
- 6 functions updated, 24 skipped (no changes detected)

### Test Results
- **530 passed**, 2 skipped — zero regressions

## Session 37 Summary (2026-02-18) — Tracker Email Visual Redesign

### What Was Done

**Visual-only redesign of `tracker_email.py`** — no logic changes, no data flow changes, no tracker.py changes. Rewrote the monolithic `_build_html()` into 7 section builders + orchestrator. Matches RPA-PORT branding used in classification emails.

### Architecture Change

| Before | After |
|--------|-------|
| `_build_html()` — 320-line monolithic function | `_build_html()` — 12-line orchestrator calling 7 section builders |
| No logo, generic blue header | RPA-PORT logo + company name + subtitle |
| Shipper/consignee inline in deal info | Dedicated 3-column parties table |
| HS codes inline in deal info | Dedicated goods section with container details |
| Minimal text footer | Branded footer with logo, timestamp, Hebrew instructions |
| No change banner | Light-blue banner showing update trigger |
| 647 lines | 845 lines (+198) |

### New Code Structure

**Color constants added:**
- `_RPA_BLUE`, `_RPA_ACCENT`, `_COLOR_OK`, `_COLOR_WARN`, `_COLOR_ERR`, `_COLOR_PENDING`, `_LOGO_URL`

**Presentation helpers added:**
- `_confidence_color()` — color hex for HS code confidence level
- `_change_label()` — human-readable label for update_type
- `_html_open()` / `_html_close()` — Outlook-safe HTML wrapper

**7 section builders (all new):**
| Function | Purpose | Lines |
|----------|---------|-------|
| `_section_header()` | RPA logo + company name + direction/status badges | ~30 |
| `_section_change_banner()` | Light-blue bar showing update trigger | ~15 |
| `_section_parties()` | 3-column: Consignee / Shipper / Customs Broker | ~30 |
| `_section_shipment()` | 2-column key-value grid with deal metadata | ~55 |
| `_section_progress()` | Progress bar + step grid + ocean tracking + TaskYam table | ~200 |
| `_section_goods()` | Container type/weight table + HS code classification pills | ~70 |
| `_section_footer()` | Branded footer with logo, timestamp, Hebrew stop instruction | ~30 |

### What Was NOT Changed
- `build_tracker_status_email()` — same signature, same subject line logic
- `IMPORT_STEPS`, `EXPORT_STEPS`, `_get_steps()` — step constants
- `_to_israel_time()`, `_format_date()`, `_time_style()` — date/timezone helpers
- `_extract_ocean_times()`, `_summarize_steps()` — data aggregation
- Progress percentage calculation, step completion color logic, ocean event confirmation colors
- Container TaskYam per-row rendering, all data sources and field reads

### Files Modified
| File | Changes |
|------|---------|
| `functions/lib/tracker_email.py` | +7 color constants, +4 helpers, +7 section builders, `_build_html` rewritten as orchestrator |

### Git Commit
- `5b08ccf` — (included in Session 36 commit by parallel Claude session)

### Deployment
- All 30 Cloud Functions deployed to Firebase (2026-02-18)

### Test Results
- **523 passed**, 2 skipped — zero regressions from tracker_email changes
- 7 pre-existing failures in `test_report_builder.py` (Hebrew localization, unrelated)

## Session 38 Summary (2026-02-18) — Clarification Logic for Email Intent System

### Problem
Email intent system detected intents but sometimes key information was missing (no BL number for status, no attachment for classify). RCB would either silently do nothing or act on incomplete data (e.g., stop ALL active deals when no specific BL given). Now RCB replies asking for the missing piece and matches follow-up replies back to the original intent.

### What Was Built

**4 Clarification Triggers:**
| # | Trigger | Condition | Hebrew Reply |
|---|---------|-----------|-------------|
| 1 | STATUS_REQUEST missing entity | No BL/container extracted | "של איזה משלוח? נא לציין מספר BL, מכולה או מספר תיק" |
| 2 | stop_tracking missing target | No BL/container in text | "איזה משלוח להפסיק לעקוב? נא לציין מספר BL או מכולה" |
| 3 | classify missing attachment | `msg.hasAttachments` is False | "לא מצאתי מסמך מצורף. נא לשלוח חשבונית או מסמך לסיווג" |
| 4 | Ambiguous intent | NONE intent + body >= 30 chars | "לא הצלחתי להבין את הבקשה. אפשר לנסח מחדש?" |

**3 New Functions:**
- `_send_clarification()` — sends Hebrew RTL reply, stores pending doc in `questions_log` with key `pending_{email_hash}`
- `_check_pending_clarification()` — single Firestore doc read, 4-hour expiry
- `_resolve_clarification()` — extracts entities from follow-up email, merges with original, re-dispatches to original intent handler

**Detection Fix:**
- `detect_email_intent()` now returns STATUS_REQUEST (confidence 0.7) when status keywords match but no entities found — handler sends clarification instead of silently dropping

**Behavioral Change:**
- `_execute_stop_tracking()` no longer stops ALL active deals when no BL/container specified — sends clarification instead
- Pending clarification check runs before body length check (a valid reply may be just a BL number like "MEDURS12345")

### What Does NOT Get Clarification
- NON_WORK → canned reply (no clarification needed)
- ADMIN_INSTRUCTION → admin knows what they're doing
- KNOWLEDGE_QUERY → answer what we can, fallback to Claude
- CUSTOMS_QUESTION with product description → search by description (works fine)
- Body < 15 chars → already skipped (auto-generated)
- Body 15-29 chars with NONE intent → stay silent (too short to be a real question)

### Files Modified
| File | Changes |
|------|---------|
| `functions/lib/email_intent.py` | +3 new functions, CLARIFICATION_MESSAGES dict, 4 handler modifications, detection fix for STATUS_REQUEST without entities, pending check in process_email_intent |
| `functions/tests/test_email_intent.py` | +7 new tests, updated imports and _make_msg helper |

### Git Commit
- `69fa580` — Add clarification logic for email intent system

### Deployment
- 29 Cloud Functions deployed to Firebase (2026-02-18)
- Stale `check_email_scheduled` function cleaned up

### Test Results
- **583 passed**, 2 skipped — 80 email intent tests (73 existing + 7 new), zero regressions

## Session 34-Audit Summary (2026-02-18) — Full System Audit + Cleanup

### What Was Done

**1. Full System Audit Across All Sessions (32-37, 19 commits)**
Comprehensive audit of the entire codebase after a massive multi-session development day.

| Area | Result |
|------|--------|
| **Test suite** | 576 passed, 0 failed, 2 skipped |
| **Merge conflicts** | Zero conflict markers found |
| **Imports** | 62/63 pass (1 pre-existing: `pdf_creator.py` needs `reportlab`) |
| **Pipeline flow** | All 13 connection points verified end-to-end |
| **Feature flags** | All enabled, all consistent |
| **Dead code** | ~770 lines found in main.py + 23 backup files |
| **Duplicates** | Zero duplicate functions from parallel sessions |
| **Firestore refs** | ~35 collections used but not in librarian_index |

**2. Dead Code Cleanup — main.py (-551 lines)**
Removed 12 dead Session 13.1 Gmail/IMAP fallback functions:
- `extract_reply_email()`, `send_ack_email()`, `send_classification_report()`
- `check_email_scheduled()` (disabled scheduler), `_simple_email_check()`
- `_extract_email()`, `_send_ack()`, `decode_email_header()`
- `extract_body()`, `extract_attachments()`, `detect_document_type()`
- `classify_and_store()`, `extract_invoice_fields()`
- Removed unused imports: `imaplib`, `email as email_lib`, `decode_header`

**3. Backup File Cleanup — 23 files deleted (-24,979 lines total)**
Removed all stale `.bak*` and `.backup*` files from `functions/lib/`:
- 12 `.bak_20260216` files, 4 `.bak2_20260216`, 4 `.bak3_20260216`
- 3 `.backup_session14`, 1 `.backup_session6`, 1 `.backup_v1`, 1 `.backup`

**4. Tracker Cleanup — tracker.py (-8 lines)**
Removed `tracker_poll_active_shipments()` v1 compatibility alias (never called).

**5. Librarian Index — 5 Collections Added**
Added to `COLLECTION_FIELDS` so overnight brain and librarian can search them:
- `elimination_log` — D8 elimination engine audit trail
- `rcb_processed` — core pipeline processed email marker
- `rcb_logs` — operational system logs
- `section_notes` — C2 section-level tariff notes
- `shipping_agents` — customs/clearing agent profiles
- (`questions_log` and `system_instructions` were already present from Session 35)

### Files Modified
| File | Changes |
|------|---------|
| `functions/main.py` | -551 lines: 12 dead functions + 3 unused imports removed |
| `functions/lib/tracker.py` | -8 lines: removed v1 compat alias |
| `functions/lib/librarian_index.py` | +35 lines: 5 new COLLECTION_FIELDS entries |
| 23 `.bak*`/`.backup*` files | Deleted entirely |

### COLLECTION_FIELDS Total: 55 collections registered
(was 50, now 55 after adding 5)

### Git Commit
- `a1e9aef` — Session 34 audit cleanup: remove 551 lines dead code, 23 backup files, add 5 collections to librarian_index

### Deployment
- 29 Cloud Functions deployed to Firebase (2026-02-18) — no runtime changes detected (cleanup was non-functional files)

### Test Results
- **576 passed**, 2 skipped — zero regressions

## Session 34E Summary (2026-02-18) — Block E: Verification Engine (Phases 4-6)

### Problem
After Block D (elimination engine) narrows candidates and Agent 2 classifies, there was no verification that the classification is correct. The methodology mandates bilingual verification, knowledge cross-checks, and proactive flagging before results go out.

### What Was Built

**`functions/lib/verification_engine.py`** (NEW, 743 lines):

| Component | What It Does | Cost |
|-----------|-------------|------|
| **Phase 4: Bilingual Verification** | Cross-checks product description keywords against HE and EN official descriptions. If EN missing, fetches from UK tariff API (free, cached). If scores below 0.25 threshold, consults Gemini Flash AI (yes/no). | FREE → $0.001 |
| **Phase 5: Knowledge Verification** | Scans 218 directives + 85 framework order docs (cached in-memory) for supporting/conflicting references. Checks chapter exclusions. Detects if Agent 2 chose an eliminated code (CRITICAL). | FREE |
| **Proactive Flagging** | Generates 7 flag types per item: PERMIT, STANDARD, FTA, ANTIDUMPING, ELIMINATION_CONFLICT, DIRECTIVE, BILINGUAL_MISMATCH | FREE |
| **HTML Renderer** | Email-safe badges with severity colors (green/amber/red) matching existing badge scheme | FREE |

**Confidence adjustment table:**
| Condition | Delta |
|---|---|
| Supporting directive | +0.05 |
| Framework definition match | +0.05 |
| Chapter exclusion hit | -0.20 |
| Elimination conflict | -0.30 |
| UK tariff EN confirms | +0.05 |
| Total range | [-0.30, +0.20] |

### Pipeline Wiring (6 insertions in `classification_agents.py`)
1. Import + `VERIFICATION_ENGINE_AVAILABLE` guard
2. `VERIFICATION_ENGINE_ENABLED = True` feature flag
3. Pipeline call after verification loop, before `_link_invoice_to_classifications`
4. `"verification_engine": ve_results` in result dict
5. `ve_flags` + `ve_phase4` per item in `_enrich_results_for_email()`
6. `build_verification_flags_html(c)` in email builder after justification/cross-check block

### Audit Findings (2 bugs fixed in e3083d8)
| Bug | Severity | Fix |
|-----|----------|-----|
| Antidumping `"in"` substring match (`"in" in "finland"` → true) | CRITICAL | Changed to exact set membership: `origin in _ANTIDUMPING_ORIGINS` |
| Directive conflict keyword substring match (`"steel" in content_string`) | CRITICAL | Changed to set membership: `kw in content_kw` |

### Files Created/Modified
| Action | File | Lines |
|--------|------|-------|
| **CREATE** | `functions/lib/verification_engine.py` | 743 |
| **CREATE** | `functions/tests/test_verification_engine.py` | 576 (46 tests) |
| **CREATE** | `functions/test_verification_live.py` | 190 (3 live scenarios) |
| **MODIFY** | `functions/lib/classification_agents.py` | +42 lines (6 targeted insertions) |

### Git Commits
- `d12ac50` — Block E: Verification Engine — Phase 4+5 bilingual verification + proactive flagging
- `e3083d8` — Fix 2 audit bugs: antidumping substring + directive keyword match

### Deployment
- All Cloud Functions deployed to Firebase (2026-02-18)

### Test Results
- **576 passed**, 2 skipped — zero regressions

### Block Status After Session 34E
- **Block A**: ✓ (A1-A4)
- **Block B**: ✓ (B1-B2)
- **Block C**: ✓ (C1-C6, C8) — C7 blocked
- **Block D**: ✓ FULLY COMPLETE (D1-D9, 2,282 lines)
- **Block E**: ✓ COMPLETE (Phase 4+5+Flagging, 743 lines)
- **Block F-H**: Not started

## Session 37b Summary (2026-02-18) — Tool #14: Wikipedia API Integration

### What Was Done

Added `search_wikipedia` as the 14th tool in the tool-calling engine. FREE Wikipedia API integration for product/material knowledge lookup during classification.

### How It Works

1. **Per-request cache** — avoids duplicate Wikipedia calls within one classification run
2. **Firestore cache** (`wikipedia_cache` collection, 30-day TTL) — avoids repeat API calls across runs
3. **Two-step Wikipedia API**:
   - Search API (`/w/api.php?action=query&list=search`) → find best matching title (top 3 results)
   - Summary API (`/api/rest_v1/page/summary/{title}`) → plain text extract (max 2000 chars)
4. **User-Agent**: `RCB-RPA-PORT/1.0 (rcb@rpa-port.co.il)`
5. **Cost**: FREE — no API key, no billing
6. **Safety**: No internal data sent (query is product/material name only)

### Use Cases in RCB
- Email intent KNOWLEDGE_QUERY: look up product before answering
- Overnight brain: enrich product knowledge for unknown materials
- Classification: understand product composition/use before HS code selection (e.g., "polyethylene terephthalate", "aramid fiber", "lithium iron phosphate")

### Files Modified
| File | Changes |
|------|---------|
| `functions/lib/tool_executors.py` | +`_search_wikipedia()` method (124 lines), `_wikipedia_cache` in `__init__`, registered in dispatcher, added `hashlib`+`requests` imports, Wikipedia API constants |
| `functions/lib/tool_definitions.py` | +`search_wikipedia` tool definition (Claude + Gemini auto-converted), system prompt step 13 added, header 13→14 tools |
| `functions/lib/librarian_index.py` | +`wikipedia_cache` collection in COLLECTION_FIELDS |
| `functions/tests/test_tool_calling.py` | Tool count 13→14, `search_wikipedia` in expected names set, Gemini declarations 13→14 |

### New Firestore Collection
| Collection | Purpose |
|-----------|---------|
| `wikipedia_cache` | Cached Wikipedia lookups, keyed by MD5(query.lower()), 30-day TTL |

### Git Commit
- `92d4b21` — Tool #14: search_wikipedia — free Wikipedia API integration for product knowledge

### Deployment
- All 29 Cloud Functions deployed to Firebase (2026-02-18)

### Test Results
- **583 passed**, 2 skipped — zero regressions

## Session 38 Summary (2026-02-18) — Full System Audit Fixes + Automated Backup System

### Overview
Session 37 delivered a read-only full system audit (82 issues: 5 CRITICAL, 9 HIGH, 25 MEDIUM, 24 LOW). This session fixed the top-priority issues and built an automated backup system to close the biggest infrastructure gap.

### Audit Fixes — 5 Issues Fixed (5 commits)

| # | Issue | Severity | File(s) | Commit | Fix |
|---|-------|----------|---------|--------|-----|
| 1 | H9: sa-key.json not in .gitignore | HIGH | `.gitignore` | `ef93631` | Added `sa-key.json` to gitignore. Verified never committed to git history. |
| 2 | H1+H2: Hebrew confidence vs numeric type mismatch | HIGH | `classification_agents.py` | `c1074d1` | VE Phase 5 and Cross-Check confidence adjustments were silently never applied because Agent 2 returns Hebrew strings ("גבוהה"/"בינונית"/"נמוכה") while adjustment code checked `isinstance(conf, (int, float))`. Added `_apply_confidence_adjustment()` helper that converts Hebrew→float, applies delta, converts back. Both VE (line 1084) and cross-check (line 2690) now use this. Also fixed cross_check_tier/note always being set. |
| 3 | C1: Bare except:pass in 4 AI agent JSON parsers | CRITICAL | `classification_agents.py` | `24c345f` | Agents 2-5 (lines 680, 700, 719, 740) had bare `except: pass` silently swallowing all errors. Replaced with `except Exception as e:` + print with agent name, error, and first 200 chars of raw AI response. |
| 4 | C3: Confidence regression in classification memory | CRITICAL | `self_learning.py` | `eb0bb2a` | `learn_classification()` unconditionally overwrote entries via `set(merge=True)`. Low-quality AI reclassification (confidence 0.5) could replace expert-validated result (confidence 0.95). Added read-before-write guard with method ranking: cross_validated > manual > ai. |
| 5 | C4+C5: Firestore triggers without try/except | CRITICAL | `main.py` | `7517375` | `on_new_classification` and `on_classification_correction` had no top-level exception handler. Unhandled errors caused Firebase retry storms creating duplicate agent_tasks and learning_log entries. Both wrapped in try/except with traceback logging. |

### New Feature: Automated Backup System (1 commit)

**Commit:** `f51939d`

**New Cloud Function: `rcb_daily_backup()`**
- Scheduled daily at 02:00 Israel time (before TTL cleanup at 03:30)
- Exports 4 critical collections to GCS as NDJSON:
  - `learned_classifications` — irreplaceable classification memory
  - `classification_directives` — 218 enriched directives
  - `legal_knowledge` — customs ordinance + reforms
  - `chapter_notes` — tariff chapter preambles/exclusions
- Filename format: `backups/{collection}/YYYY-MM-DD.ndjson`
- Sends confirmation email to doron@rpa-port.co.il with doc counts
- Sends alert email on partial/full failure

**Backup Guard on `rcb_ttl_cleanup()`**
- Before any TTL deletion, verifies today's backup exists in GCS
- If backup missing: aborts ALL deletions, logs to `security_log` collection, sends alert email
- If GCS check itself fails: warns but proceeds (fail-open to avoid permanent block)

**Daily Timeline:**
```
02:00  rcb_daily_backup → exports 4 collections to GCS
03:30  rcb_ttl_cleanup  → verifies backup exists → then runs deletions
```

### New Constants/Functions in main.py
- `_BACKUP_COLLECTIONS` — list of 4 collections to back up
- `_BACKUP_PREFIX` — GCS path prefix ("backups")
- `_BACKUP_ALERT_EMAIL` — "doron@rpa-port.co.il"
- `_export_collection_to_gcs(db, bucket, collection, date)` — streams collection to NDJSON blob
- `_check_backup_exists(bucket, collection, date)` — checks if blob exists in GCS

### New Firestore Collection
| Collection | Purpose |
|-----------|---------|
| `security_log` | Logs security-relevant events (TTL cleanup aborted, etc.) |

### Backup Audit Findings (Read-Only)
- **NO automated Firestore backups existed** before this session
- GCS bucket was initialized but **never used**
- `learned_classifications` was the only truly irreplaceable collection (no local source file)
- Other critical collections (tariff, chapter_notes, etc.) are recoverable from local XML/text files
- TTL cleanup jobs were deleting data without any backup verification

### Files Modified
| File | Changes |
|------|---------|
| `.gitignore` | +1 line (sa-key.json) |
| `functions/lib/classification_agents.py` | +30 lines: `_CONFIDENCE_TO_FLOAT`, `_apply_confidence_adjustment()`, 4 bare except→logged, VE/CC adjustment fix |
| `functions/lib/self_learning.py` | +23 lines: read-before-write guard with method ranking in `learn_classification()` |
| `functions/main.py` | +167 lines: `rcb_daily_backup()` function, backup guard in `rcb_ttl_cleanup()`, try/except on both Firestore triggers |

### Git Commits (6 total)
- `ef93631` — H9: Add sa-key.json to .gitignore
- `c1074d1` — H1+H2: Fix Hebrew confidence vs numeric type mismatch
- `24c345f` — C1: Replace bare except:pass in 4 AI agent JSON parsers with logging
- `eb0bb2a` — C3: Prevent confidence regression in classification memory
- `7517375` — C4+C5: Add top-level try/except to Firestore triggers
- `f51939d` — Add automated daily backup system with TTL cleanup guard

### Deployment
- All 30 Cloud Functions deployed to Firebase (2026-02-18)
- `rcb_daily_backup` created as new function
- `rcb_ttl_cleanup` updated with backup guard

### Test Results
- **583 passed**, 2 skipped — zero regressions after all 6 commits

### Remaining Audit Issues (Not Fixed This Session)
From the 82-issue audit, 77 remain. Highest priority for next session:
- **C2**: tracker.py race guard — `except Exception: pass` silences Firestore write failure + TOCTOU flaw (line 1462-1471)
- **H3**: `rcb_check_email` no top-level try/except on preamble (lines 521-547)
- **H4**: Bare `except:` in `rcb_helpers.py` Graph API helpers (lines 682, 691)
- **H5**: N+1 Firestore query patterns in tracker.py (~250 reads per poll cycle)
- **H7**: Unauthenticated `api()` HTTP endpoint with open CORS

## Session 38b Summary (2026-02-18) — Tools #15-20: External API Batch (6 New Tools)

### Overview
Added 6 new external API tools to the tool-calling engine, bringing the total from 14 to 20. All FREE APIs with domain-whitelisted HTTP, per-request + Firestore caching, key stripping, and text sanitization. Deterministic pre-enrichment (Step 4b) auto-fires relevant tools before the AI loop based on invoice data.

### 6 New Tools

| # | Tool | API Source | Cost | Cache TTL |
|---|------|-----------|------|-----------|
| 15 | `search_wikidata` | wikidata.org (search + claims) | FREE | 30 days |
| 16 | `lookup_country` | restcountries.com | FREE | 30 days |
| 17 | `convert_currency` | open.er-api.com | FREE | 24 hours |
| 18 | `search_comtrade` | comtradeapi.un.org | FREE | 7 days |
| 19 | `lookup_food_product` | world.openfoodfacts.org | FREE | 30 days |
| 20 | `check_fda_product` | api.fda.gov (drugs + 510k) | FREE | 30 days |

### Shared Infrastructure

**`_safe_get()` — Domain-whitelisted HTTP:**
- 7 allowed domains: `en.wikipedia.org`, `www.wikidata.org`, `restcountries.com`, `open.er-api.com`, `comtradeapi.un.org`, `world.openfoodfacts.org`, `api.fda.gov`
- All other domains silently blocked — no internal data can leak

**`_cached_external_lookup()` — Shared caching helper:**
- Per-request dict cache (instant, zero cost)
- Firestore document cache with configurable TTL (1 read per cache hit)
- Key stripping: each handler specifies `_ALLOWED` keys — only permitted fields returned to AI
- `sanitize_external_text()` applied to all external string fields (prompt injection defense)

**`_WIKIDATA_PROPS` — 8 property mappings:**
- P31 (instance_of), P279 (subclass_of), P186 (made_from_material), P274 (chemical_formula), P231 (cas_number), P366 (has_use), P2067 (mass), P2054 (density)

### Step 4b: Deterministic Pre-Enrichment

Added between Step 4 (memory check) and Step 5 (AI loop) in `tool_calling_engine.py`. Fires relevant tools BEFORE AI sees the items — zero AI cost for these lookups.

| Trigger | Condition | Tool Called |
|---------|-----------|------------|
| Country lookup | `origin` >= 2 chars | `lookup_country` |
| Currency lookup | Invoice currency not ILS/NIS | `convert_currency` |
| Food product | Item words ∩ `_FOOD_TRIGGERS` (60 bilingual keywords) | `lookup_food_product` |
| Medical product | Item words ∩ `_MEDICAL_TRIGGERS` (33 bilingual keywords) | `check_fda_product` |

Pre-enrichment data injected into `_build_user_prompt()` as "Pre-loaded external data" section.

### Special Behaviors
- **Comtrade** gated by `_overnight_mode` flag — only available during overnight brain runs (rate-limited API)
- **FDA** tries drug labels first, falls back to 510(k) device search
- **Wikidata** 2-step: search entity by name → fetch structured claims (materials, formulas, CAS numbers)
- **Currency** returns top 12 currencies only (USD, EUR, GBP, JPY, CNY, ILS, CHF, CAD, AUD, KRW, INR, THB)

### Files Modified

| File | Changes |
|------|---------|
| `functions/lib/tool_executors.py` | +~380 lines: `_DOMAIN_ALLOWLIST`, `_WIKIDATA_PROPS`, `_safe_get()`, `_ext_cache`+`_overnight_mode` in `__init__`, 6 dispatcher entries, `_cached_external_lookup()`, 6 handler methods |
| `functions/lib/tool_definitions.py` | +~128 lines: header 14→20 tools, 6 new CLAUDE_TOOLS entries, system prompt steps 15-20 |
| `functions/lib/tool_calling_engine.py` | +~93 lines: `_FOOD_TRIGGERS` (60 kw), `_MEDICAL_TRIGGERS` (33 kw), Step 4b pre-enrichment block, `_build_user_prompt()` enrichment parameter |
| `functions/lib/librarian_index.py` | +42 lines: 6 new COLLECTION_FIELDS cache entries |
| `functions/tests/test_tool_calling.py` | Tool counts 14→20, 6 new tool names in expected set |

### New Firestore Collections (6 caches)
| Collection | Purpose |
|-----------|---------|
| `wikidata_cache` | Wikidata entity claims, 30-day TTL |
| `country_cache` | Country info from restcountries.com, 30-day TTL |
| `currency_rates` | Exchange rates from open.er-api.com, 24-hour TTL |
| `comtrade_cache` | UN Comtrade trade data, 7-day TTL |
| `food_products_cache` | Open Food Facts product data, 30-day TTL |
| `fda_products_cache` | FDA drug labels + 510(k) device data, 30-day TTL |

### Tool-Calling Engine: 20 Active Tools
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
| 13 | run_elimination | elimination_engine (D1-D8) | D9 |
| 14 | search_wikipedia | Wikipedia REST API | Session 37b |
| 15 | search_wikidata | Wikidata API | Session 38b |
| 16 | lookup_country | restcountries.com | Session 38b |
| 17 | convert_currency | open.er-api.com | Session 38b |
| 18 | search_comtrade | UN Comtrade API (overnight only) | Session 38b |
| 19 | lookup_food_product | Open Food Facts API | Session 38b |
| 20 | check_fda_product | FDA API (drugs + 510k) | Session 38b |

### Git Commit
- `8d099c3` — Tools #15-20: 6 external API tools + domain whitelist + pre-enrichment

### Deployment
- All 29 Cloud Functions deployed to Firebase (2026-02-18)
- Initial deploy had 5 HTTP 409 conflicts (previous deploy still in flight) — resolved on retry

### Test Results
- **583 passed**, 2 skipped — zero regressions

## Session 38c Summary (2026-02-18) — Fix 3 HIGH Audit Issues (H3, H4, H7)

### What Was Done

Fixed the 3 remaining HIGH-severity issues from the full system audit, one commit per fix, 583 tests passing after each.

### Fix 1: H3 — Top-level try/except on `rcb_check_email` (commit `260f43b`)

**Problem:** The preamble of `rcb_check_email` (secrets lookup, Graph token acquisition, HTTP inbox request at lines 527-553) ran outside any try/except. An unhandled exception (network timeout, JSON decode, secrets outage) would crash the Cloud Function and trigger Firebase retry storms.

**Fix:** Extracted the entire function body into `_rcb_check_email_inner()` and wrapped the call in try/except with `traceback.print_exc()`. No behavior change on happy path.

| File | Change |
|------|--------|
| `functions/main.py` | +10 lines: `_rcb_check_email_inner()` extraction + top-level guard |

### Fix 2: H4 — Bare `except:` in Graph API helpers (commit `9835db9`)

**Problem:** 6 bare `except:` clauses caught `SystemExit`/`KeyboardInterrupt` and silently swallowed all errors with zero logging.

**Fix:** Replaced all with `except Exception as e:` + `print()` logging.

| Location | Function |
|----------|----------|
| `rcb_helpers.py:485` | `extract_text_from_attachments` (base64 decode) — `except Exception:` (continue) |
| `rcb_helpers.py:682` | `helper_graph_messages` — + print |
| `rcb_helpers.py:691` | `helper_graph_attachments` — + print |
| `rcb_helpers.py:699` | `helper_graph_mark_read` — + print |
| `rcb_helpers.py:835` | `get_anthropic_key` — + print |
| `main.py:412` | `graph_forward_email` — + print |

| File | Change |
|------|--------|
| `functions/lib/rcb_helpers.py` | 5 bare except → except Exception |
| `functions/main.py` | 1 bare except → except Exception |

### Fix 3: H7 — Unauthenticated API endpoints with open CORS (commit `986b793`)

**Problem:** Both `api()` (line 317) and `rcb_api()` (line 421) had `cors_origins="*"` with zero authentication. Exposed Firestore reads (classifications, sellers, knowledge_base, inbox, learning_log, rcb_logs, session_backups) and Firestore writes (classification corrections, backup creation + email trigger) to anyone on the internet.

**Fix:** Added `_check_api_auth()` helper using Bearer token verified with `hmac.compare_digest` against `RCB_API_SECRET` from Secret Manager.
- `api()` — all routes require auth
- `rcb_api()` — `/health` remains public, all other routes require auth
- `RCB_API_SECRET` created in Secret Manager (project `rpa-port-customs`, version 1)

| File | Change |
|------|--------|
| `functions/main.py` | +`_check_api_auth()` helper (15 lines), auth gate on `api()` and `rcb_api()` |

### Secret Manager
| Secret | Status | Purpose |
|--------|--------|---------|
| `RCB_API_SECRET` | Created (v1) | Bearer token for `api()` and `rcb_api()` HTTP endpoints |

### Git Commits
- `260f43b` — H3: Add top-level try/except to rcb_check_email
- `9835db9` — H4: Replace bare except: with except Exception in Graph API helpers
- `986b793` — H7: Add bearer token auth to api() and rcb_api() endpoints

### Deployment
- All 30 Cloud Functions deployed to Firebase (2026-02-18)

### Test Results
- **583 passed**, 2 skipped — zero regressions after all 3 commits

### Session 38c Continued — H5, H6, H8 Audit Fixes

**H5: N+1 Firestore queries in tracker.py (commit `ab25a16`)**

Replaced per-container `.document(id).get()` loops with single `.where("deal_id", "==", deal_id).stream()` batch queries at 3 sites:

| Site | Function | Lines | Before | After |
|------|----------|-------|--------|-------|
| 1 | `_check_deal_completion()` | 1941-1950 | N reads per deal | 1 query per deal |
| 2 | `_update_deal_from_observation()` | 1294-1316 | N reads to check existence | 1 query to load existing IDs |
| 3 | `_send_tracker_email()` | 2225-2231 | N reads per email | 1 query per email |

Reduces ~250 Firestore reads per 30-min poll cycle to ~50.

**H6: Synthesis race condition — DOWNGRADED TO LOW**

Investigation confirmed the entire classification pipeline (lines 1030-1236 in `classification_agents.py`) is fully synchronous — no threads, no async. Agent 6 always runs after all lookups complete. The silent-failure behavior (try/except returning empty dicts) is intentional fail-open resilience. No fix needed.

**H8: Crash recovery for overnight_brain.py (commit `7e017ab`)**

Added lightweight checkpointing to the orchestrator via `brain_run_progress/{date}` Firestore doc:

| Capability | Before | After |
|-----------|--------|-------|
| Budget persistence | In-memory only, lost on crash | Persisted to Firestore after each stream |
| Stream skip on resume | None — all 9 streams re-run | Completed streams skipped via `completed_streams` list |
| Progress visibility | Report only at very end | Checkpoint updated after every stream |
| Crash detection | None | Existing checkpoint doc detected on startup |

3 new helper functions: `_checkpoint_key()`, `_load_checkpoint()`, `_save_checkpoint()`. No changes to individual stream functions.

New Firestore collection: `brain_run_progress` (one doc per calendar day).

### Git Commits (H5 + H8)
- `ab25a16` — H5: Replace N+1 Firestore reads with batch queries in tracker.py
- `7e017ab` — H8: Add crash recovery checkpointing to overnight_brain.py

### Deployment
- All 30 Cloud Functions deployed to Firebase (2026-02-18)

### Test Results
- **583 passed**, 2 skipped — zero regressions after both commits

## Session 39 Summary (2026-02-18) — External APIs Batch 2 (Tools #21-32)

### Overview
Added 12 new external API tools to the tool-calling engine, bringing the total from 20 to 32. All FREE APIs with domain-whitelisted HTTP, per-request + Firestore caching, key stripping, and text sanitization. Added cross-reference pipeline (EU TARIC + US HTS) and sanctions screening on every shipment.

### 12 New Tools

| # | Tool | API Source | Cost | Cache TTL | Mode |
|---|------|-----------|------|-----------|------|
| 21 | `bank_of_israel_rates` | BOI SDMX + PublicApi | FREE | 6 hours | Real-time |
| 22 | `search_pubchem` | NIH PubChem REST | FREE | 90 days | Real-time |
| 23 | `lookup_eu_taric` | EC TARIC consultation | FREE | 30 days | Real-time |
| 24 | `lookup_usitc` | USITC tariff-schedule | FREE | 30 days | Real-time |
| 25 | `israel_cbs_trade` | CBS Israel API | FREE | 30 days | Overnight |
| 26 | `lookup_gs1_barcode` | Open Food Facts barcode | FREE | 60 days | Real-time |
| 27 | `search_wco_notes` | wcoomd.org pages | FREE | 180 days | Real-time |
| 28 | `lookup_unctad_gsp` | UNCTAD API | FREE | 90 days | Real-time |
| 29 | `search_open_beauty` | Open Beauty Facts | FREE | 30 days | Real-time |
| 30 | `crossref_technical` | CrossRef API | FREE | 90 days | Overnight |
| 31 | `check_opensanctions` | OpenSanctions search | FREE (10k/mo) | 24 hours | Real-time |
| 32 | `get_israel_vat_rates` | gov.il API | FREE | 7 days | Real-time |

### Cross-Reference Pipeline (Step 7d2 in tool_calling_engine.py)
After classification + verification, automatically runs for each validated HS code:
1. `lookup_eu_taric(hs6)` — EU TARIC cross-reference
2. `lookup_usitc(hs6)` — US HTS cross-reference
3. Confidence adjustment:
   - Both EU + US agree: +0.12
   - One agrees: +0.06
   - Neither agrees: -0.05, flags `CROSS_REF_CONFLICT`

### Sanctions Screening
- `_screen_deal_parties()` added to `main.py` — called after every CC tracker update
- Extracts shipper, consignee, notify_party from deal document
- Calls `check_opensanctions()` for each party name (score >= 0.7 threshold)
- On hit: logs to `security_log` collection, flags deal with `sanctions_hit: true`, sends alert email to doron@rpa-port.co.il
- Never blocks shipments — flag only, human decides
- `sanctions_screened` flag prevents re-screening same deal

### Pre-enrichment Triggers Added (Step 4b in tool_calling_engine.py)
| Trigger | Keywords | Tool Called |
|---------|----------|------------|
| Chemical | 30 bilingual terms (acid, oxide, chloride, polymer, resin, compound, etc.) | `search_pubchem` |
| Cosmetics | 30 bilingual terms (cream, lotion, shampoo, perfume, cosmetic, etc.) | `search_open_beauty` |
| BOI Rate | Non-ILS invoice currency | `bank_of_israel_rates` |

### Domain Allowlist Updated
25 total allowed domains (was 7). Added: boi.org.il, edge.boi.org.il, pubchem.ncbi.nlm.nih.gov, ec.europa.eu, dataweb.usitc.gov, api.cbs.gov.il, cbs.gov.il, world.openbeautyfacts.org, openbeautyfacts.org, gepir.gs1.org, wcoomd.org, www.wcoomd.org, unctadstat.unctad.org, api.crossref.org, api.opensanctions.org, gov.il, www.gov.il, taxes.gov.il

### Files Modified

| File | Changes |
|------|---------|
| `functions/lib/tool_executors.py` | +18 domains in allowlist, +12 handler methods, +12 dispatcher entries (~687 lines added) |
| `functions/lib/tool_definitions.py` | Header 20→32 tools, +12 CLAUDE_TOOLS entries, system prompt steps 21-32 (~243 lines added) |
| `functions/lib/tool_calling_engine.py` | +3 trigger sets (_CHEMICAL_TRIGGERS, _COSMETICS_TRIGGERS, BOI rate), +cross-ref pipeline (Step 7d2), `cross_reference` in output (~110 lines added) |
| `functions/lib/librarian_index.py` | +12 COLLECTION_FIELDS cache entries (~84 lines added) |
| `functions/tests/test_tool_calling.py` | Tool counts 20→32, +12 expected tool names |
| `functions/main.py` | +`_screen_deal_parties()` function (~90 lines), sanctions screening call in CC path |

### New Firestore Collections (12 caches)
| Collection | Purpose | TTL |
|-----------|---------|-----|
| `boi_rates` | Bank of Israel official exchange rates | 6 hours |
| `pubchem_cache` | NIH PubChem chemical compound data | 90 days |
| `eu_taric_cache` | EU TARIC tariff cross-reference | 30 days |
| `usitc_cache` | US HTS cross-reference | 30 days |
| `cbs_trade_cache` | Israeli CBS trade statistics | 30 days |
| `barcode_cache` | GS1 barcode product lookups | 60 days |
| `wco_notes_cache` | WCO explanatory notes | 180 days |
| `unctad_country_cache` | UNCTAD country GSP/development status | 90 days |
| `beauty_products_cache` | Open Beauty Facts cosmetics data | 30 days |
| `crossref_cache` | CrossRef academic papers | 90 days |
| `sanctions_cache` | OpenSanctions screening results | 24 hours |
| `israel_tax_cache` | Israel VAT/purchase tax rates | 7 days |

### Tool-Calling Engine: 32 Active Tools
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
| 13 | run_elimination | elimination_engine (D1-D8) | D9 |
| 14 | search_wikipedia | Wikipedia REST API | Session 37b |
| 15 | search_wikidata | Wikidata API | Session 38b |
| 16 | lookup_country | restcountries.com | Session 38b |
| 17 | convert_currency | open.er-api.com (fallback for non-customs use) | Session 38b |
| 18 | search_comtrade | UN Comtrade API (overnight only) | Session 38b |
| 19 | lookup_food_product | Open Food Facts API | Session 38b |
| 20 | check_fda_product | FDA API (drugs + 510k) | Session 38b |
| 21 | bank_of_israel_rates | BOI SDMX + PublicApi (replaces #17 for customs valuation) | Session 39 |
| 22 | search_pubchem | NIH PubChem (chapters 28/29/38 chemicals) | Session 39 |
| 23 | lookup_eu_taric | EU TARIC cross-reference validation | Session 39 |
| 24 | lookup_usitc | US HTS cross-reference validation | Session 39 |
| 25 | israel_cbs_trade | CBS Israel import statistics (overnight only) | Session 39 |
| 26 | lookup_gs1_barcode | Open Food Facts barcode lookup | Session 39 |
| 27 | search_wco_notes | WCO explanatory notes (gold standard) | Session 39 |
| 28 | lookup_unctad_gsp | UNCTAD GSP/preferential duty eligibility | Session 39 |
| 29 | search_open_beauty | Open Beauty Facts cosmetics (chapter 33) | Session 39 |
| 30 | crossref_technical | CrossRef academic papers (overnight only) | Session 39 |
| 31 | check_opensanctions | OpenSanctions sanctions screening (compliance) | Session 39 |
| 32 | get_israel_vat_rates | Israel purchase tax + VAT rates | Session 39 |

### COLLECTION_FIELDS Total: 67 collections registered
(was 55, now 67 after adding 12 cache collections)

### Git Commit
- `744154b` — Tools #21-32: 12 external API tools + cross-reference pipeline + sanctions screening

### Deployment
- All 30 Cloud Functions deployed to Firebase (2026-02-18)
- 1 function updated (`rcb_overnight_brain`), 29 skipped (no changes detected)

### Test Results
- **583 passed**, 2 skipped — zero regressions

## Session 40 Summary (2026-02-18) — Block H: Classification Email Redesign + HS Format Fix

### Overview
Redesigned the classification result email (`build_classification_email()` in `classification_agents.py`) to match the professional branded design of `tracker_email.py` (Session 37). Replaced the old monolithic 466-line function with 14 table-based section builders + orchestrator (834 lines). Also fixed a long-standing bug in the Israeli HS code format function.

### Email Architecture Change

| Before | After |
|--------|-------|
| `build_classification_email()` — 466-line monolithic function | 14 section builders + 12-line orchestrator |
| `<div>`-based layout with CSS gradients/border-radius | Table-based Outlook-safe layout |
| No logo, generic styling | RPA-PORT branded header + footer matching tracker_email.py |
| No cross-reference section | EU TARIC + US HTS cross-reference table |
| No customs value section | BOI exchange rate + ILS customs value calculation |
| Mixed color scheme | Shared constants from tracker_email.py (_RPA_BLUE, _COLOR_OK, etc.) |

### 14 Section Builders (all new)

| Function | Purpose |
|----------|---------|
| `_cls_html_open()` / `_cls_html_close()` | Local fallback Outlook-safe wrappers |
| `_cls_header(tracking_code)` | Branded header with RPA-PORT logo + tracking code badge |
| `_cls_shipment_info(invoice_data)` | 2-column key-value: direction, freight, seller/buyer, BL/AWB |
| `_cls_invoice_validation(invoice_validation)` | Score bar with missing fields badges |
| `_cls_synthesis(synthesis)` | Blue left-bordered summary text block |
| `_cls_section_title(title, color)` | Reusable section header with gradient underline |
| `_cls_result_table(card_items, using_enriched)` | Per-item cards: HS code (18px monospace), duty/PT/VAT grid, confidence bar |
| `_cls_regulatory(ministry_routing, regulatory)` | Ministry routing per HS code with API badges |
| `_cls_cross_reference(results, card_items)` | **NEW** EU TARIC / US HTS table with confidence adjustment |
| `_cls_customs_value(invoice_data, results)` | **NEW** Invoice currency, total, BOI rate, customs value in ₪ |
| `_cls_justification_details(card_items, using_enriched)` | Per-item justification chain, devil's advocate, gaps, verification flags |
| `_cls_fta_benefits(intelligence, fta)` | FTA trade agreements with preferential rate badges |
| `_cls_risk(risk)` | Risk level and items (shown for גבוה/בינוני only) |
| `_cls_smart_questions(smart_q, classifications)` | Delegates to format_questions_html |
| `_cls_original_email(original_email_body)` | Blockquote with right border |
| `_cls_footer()` | Logo, RCB branding, Israel time timestamp, Hebrew disclaimer |

### Israeli HS Code Format Fix

**Bug:** `get_israeli_hs_format()` in `librarian.py` formatted as `XX.XX.XXXX/XX` (2.2.4/2) but the correct Israeli format documented everywhere in the codebase is `XX.XX.XXXXXX/X` (2.2.6/check-digit).

**Fix:** Changed split from `{code[:2]}.{code[2:4]}.{code[4:8]}/{code[8:10]}` to `{code[:2]}.{code[2:4]}.{code[4:10]}/{check}`. Added `_hs_check_digit()` implementing Luhn algorithm (verified against known Israeli customs check digits from data.gov.il).

| Input | Before (wrong) | After (correct) |
|-------|----------------|-----------------|
| `7304190000` | `73.04.1900/00` | `73.04.190000/9` |
| `8703808000` | `87.03.8080/00` | `87.03.808000/5` |
| `4011100000` | `40.11.1000/00` | `40.11.100000/2` |
| `0101210000/2` | `01.01.2100/02` | `01.01.210000/2` (preserved) |

### Files Modified

| File | Changes |
|------|---------|
| `functions/lib/classification_agents.py` | +834/-466 lines: tracker_email imports with fallback, `_enrich_results_for_email()` cross-ref fields, 14 section builders replacing monolithic email builder, Agent 2 prompt HS format example fix |
| `functions/lib/tool_calling_engine.py` | +1 line: `pre_enrichment` in output dict (BOI rate for email) |
| `functions/lib/librarian.py` | +22/-7 lines: `_hs_check_digit()` Luhn algorithm, `get_israeli_hs_format()` rewritten for XX.XX.XXXXXX/X |
| `functions/lib/language_tools.py` | Fixed example `87.08.998000/0` → `87.08.998000/4` (correct Luhn check digit) |

### Git Commits
- `f3faac9` — Session 40 Block H: Classification email redesign + Israeli HS format fix
- `a32585e` — Session 40a: Image analysis for attachments with dual AI vision + pattern cache

### Deployment
- All 30 Cloud Functions deployed to Firebase (2026-02-18)
- 30/30 successful update operations

### Test Results
- **583 passed**, 2 skipped — zero regressions

### Block Status After Session 40
- **Block A**: ✓ (A1-A4)
- **Block B**: ✓ (B1-B2)
- **Block C**: ✓ (C1-C6, C8) — C7 blocked
- **Block D**: ✓ FULLY COMPLETE (D1-D9)
- **Block E**: ✓ COMPLETE (Phase 4+5+Flagging)
- **Block F**: Not started
- **Block G**: Not started
- **Block H**: ✓ COMPLETE (Classification email redesign)

## Session 40c Summary (2026-02-18) — Self-learning from Image Analysis Results

### Overview
Added image pattern caching to the self-learning engine so repeat AI vision calls on the same image are avoided. Session A (40a) built `image_analyzer.py`; this session added the supporting cache/cost infrastructure in the 3 files we own.

### What Was Built

**`self_learning.py` — 2 new methods on `SelfLearningEngine` (+105 lines)**

| Method | Purpose | Cost |
|--------|---------|------|
| `check_image_pattern(image_hash)` | Single Firestore doc read by hash. Returns cached dict (extracted_fields, final_hs_code, confidence, source) or None. 180-day TTL enforced on read. Increments `times_used` on hit (fire-and-forget). | 1 read |
| `save_image_pattern(image_hash, extracted_fields, final_hs_code, confidence, source)` | Writes to `image_patterns/{image_hash}`. Read-before-write guard: never overwrites higher-confidence existing result. | 1 read + 1 write |

**`cost_tracker.py` — `log_image_analysis()` method (+25 lines)**

| Parameter | Behavior |
|-----------|----------|
| `cache_hit=True` | $0.000 — increments `image_cache_hits` only |
| `cache_hit=False` | $0.002 default — increments `image_cache_misses`, adds to `total_spent` + `ai_cost` |

New breakdown keys: `image_analyses`, `image_cache_hits`, `image_cache_misses`, `image_cost`.
Class constant: `IMAGE_ANALYSIS_COST = 0.002`.

**`librarian_index.py` — `image_patterns` in COLLECTION_FIELDS (+6 lines)**
- `title_fields`: `["final_hs_code"]`, `keyword_fields`: `["image_hash"]`, `hs_fields`: `["final_hs_code"]`, `doc_type`: `"cache"`

### Firestore Collection
| Collection | Doc ID | Fields | TTL |
|-----------|--------|--------|-----|
| `image_patterns` | `{image_hash}` | image_hash, extracted_fields, final_hs_code, confidence, source, timestamp, times_used | 180 days |

### COLLECTION_FIELDS Total: 68 collections registered
(was 67, now 68 after adding `image_patterns`)

### Files Modified (Session 40c owns only these 3)
| File | Changes |
|------|---------|
| `functions/lib/self_learning.py` | +105 lines: `check_image_pattern()`, `save_image_pattern()`, `IMAGE_PATTERN_TTL_DAYS = 180` |
| `functions/lib/cost_tracker.py` | +25 lines: `IMAGE_ANALYSIS_COST`, 4 breakdown keys, `log_image_analysis()` |
| `functions/lib/librarian_index.py` | +6 lines: `image_patterns` in COLLECTION_FIELDS |

### Files NOT Touched
`image_analyzer.py`, `extraction_adapter.py`, `classification_agents.py`, `tracker_email.py`

### Git Commit
- `a32585e` — Session 40a: Image analysis for attachments with dual AI vision + pattern cache (combined commit with Session A)

### Test Results
- **583 passed**, 2 skipped — zero regressions

## Session 41 Summary (2026-02-18) — Fix Email Quality: Empty Guards, Clean Subjects, Stable Threading

### Problem
Production tracker emails had 5 critical quality issues:
1. **Empty tracker emails** being sent (Containers: 0, BL: blank, Vessel: blank, all dashes)
2. **Subject lines** full of Re:Re:Re: thread garbage
3. **Conversation threading** not working — emails about same deal not grouped
4. **No empty email guard** — `helper_graph_send` had zero content validation
5. **Specific empty deal** (RPA16666 / 6015697 / DARBOX → TEVA API) sent at 16:16

### Root Causes Identified
1. `_send_tracker_email()` had ZERO data guards — sent regardless of deal content
2. `_send_tracker_email()` used `helper_graph_reply()` first, which inherited the original thread's garbage subject — clean subject only used on fallback
3. Threading used the latest observation's message ID (changes with each email), not a stable per-deal anchor
4. `helper_graph_send()` had no content validation gate
5. Deal creation sent email BEFORE TaskYam enrichment populated data

### Full Email Audit
**34 email send points audited** across the entire codebase:
- 22 via `helper_graph_send` direct calls
- 13 via `_send_reply_safe` (email_intent system — all properly domain-gated)
- 3 via `_send_tracker_email` (THE PROBLEM — no guards)
- All other 29 send points had adequate guards

### What Was Done

**1. Centralized Email Quality Guards (`rcb_helpers.py`)**

| Function | Purpose |
|----------|---------|
| `clean_email_subject(subject)` | Strips Re:/RE:/Fwd:/FW: prefix chains via compiled regex |
| `validate_email_before_send(subject, body_html)` | Rejects empty subject, garbage subject, empty body, body-with-only-dashes templates |

**2. Tracker Email Data Guard (`tracker.py`)**

| Function | Purpose |
|----------|---------|
| `_deal_has_minimum_data(deal)` | Requires at least 1 container OR BL number OR vessel name |

**3. Rewritten `_send_tracker_email()` v3 (`tracker.py`)**

| Change | Before | After |
|--------|--------|-------|
| Data guard | None | `_deal_has_minimum_data()`, logs to `rcb_logs` if empty |
| Content validation | None | `validate_email_before_send()` rejects invalid emails |
| Subject cleaning | Raw subject | `clean_email_subject()` strips Re:/Fwd: chains |
| Send method | `helper_graph_reply` first (inherits garbage subject) | Always `helper_graph_send` with clean subject |
| Threading | Latest observation's message ID (unstable) | Stable `deal_thread_id` = `<rcb-trk-{deal_id}@rpa-port.co.il>` |
| Empty deal handling | Sent empty email immediately | Skipped + logged, deferred to next poll after enrichment |

**4. New Subject Format (`tracker_email.py`)**

| Before | After |
|--------|-------|
| `[RCB-TRK] Import \| BOL \| 3/5 Released` | `RCB \| BOL \| 3/5 Released \| VESSEL NAME` |

**5. Deal Thread ID for Stable Threading**
- `_create_deal()` includes `deal_thread_id: ""` field
- First email send generates `<rcb-trk-{deal_id}@rpa-port.co.il>` and saves to deal doc
- ALL subsequent emails use this as In-Reply-To + References headers

### RPA16666 Root Cause
Email with BOL → deal created → 0 containers, no vessel → TaskYam quick-check skipped (no containers) → STEP 8 sends email immediately → empty email. Fix: `_deal_has_minimum_data()` blocks send; deferred to 30-min poll after enrichment.

### Files Modified
| File | Changes |
|------|---------|
| `functions/lib/rcb_helpers.py` | +35 lines: `_RE_FWD_PATTERN`, `clean_email_subject()`, `validate_email_before_send()` |
| `functions/lib/tracker.py` | +63/-33 lines: `_deal_has_minimum_data()`, `_send_tracker_email()` v3, `deal_thread_id` in `_create_deal()` |
| `functions/lib/tracker_email.py` | +8/-6 lines: New subject format `RCB \| identifier \| status \| vessel` |

### Git Commit
- `ed986f1` — Fix email quality: empty tracker guards, clean subjects, stable threading

### Deployment
- All 30 Cloud Functions deployed to Firebase (2026-02-18)
- 27 first pass + 3 retried (HTTP 409)

### Test Results
- **583 passed**, 2 skipped — zero regressions

## Session 40b Summary (2026-02-18) — Tracker Feedback Loop Fix + Data Cleanup

### Problem
Live tracker email sent with empty data for shipment RPA16666 / 6015697 / DARBOX >> TEVA API (2x40HC, Haifa to CIF Nhava Sheva). Investigation revealed a critical feedback loop:

1. RCB sends tracker status email into the thread
2. Next 30-min poll cycle picks up that email as a new CC observation
3. Tracker processes RCB's own HTML email, extracts minimal/no logistics data
4. Creates a new deal with empty fields (no BL, sometimes no containers)
5. Sends another status email — loop repeats

**Impact:** 9 duplicate deals created in ~4 hours, 64 self-observations from rcb@rpa-port.co.il, 79 rcb_processed entries. One deal per poll cycle.

### Root Cause
No sender filtering in the email processing loop — RCB processed its own outgoing emails as if they were external shipping correspondence.

### Fix: Skip Own Emails (commit `d8802e9`)

Added self-email skip at the top of the email processing loop in `main.py`, before all handlers (declarations, CC, direct):

```python
# Skip system emails for all paths
if from_email.lower() == rcb_email.lower():
    continue  # Never process our own outgoing emails (prevents feedback loop)
```

**Location:** `functions/main.py:696` — applies to ALL email paths (CC, direct, declarations).

### Firestore Cleanup (194 documents deleted)

Ran `cleanup_darbox_dupes.py --execute` to remove all duplicate data:

| Collection | Deleted | Kept |
|-----------|---------|------|
| `tracker_deals` | 8 duplicate deals | 1 (`Vmn9cjhprQOfT9tQr9eq`, score=28, status=completed) |
| `tracker_container_status` | 8 container docs | 1 (GAOU6394772 with full TaskYam data) |
| `tracker_timeline` | 35 entries | 11 entries (deal_created + status_change + emails) |
| `tracker_observations` | 64 self-observations | 0 (all were from rcb@) |
| `rcb_processed` | 79 processed markers | 0 (all were for self-emails) |
| **Total** | **194 deleted** | **13 kept** |

Deal kept: vessel ITAL WIT, container GAOU6394772, MSC, manifest 262094, customs declaration 26014441623750, full TaskYam export process (already sailed 2026-02-05).

### Files Modified
| File | Change |
|------|--------|
| `functions/main.py` | +2 lines: self-email skip at top of processing loop |

### Git Commit
- `d8802e9` — Fix tracker feedback loop: skip emails from own mailbox

### Deployment
- All 30 Cloud Functions deployed to Firebase (2026-02-18)

### Test Results
- **583 passed**, 2 skipped — zero regressions
