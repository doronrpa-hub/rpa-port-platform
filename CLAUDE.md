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

## Git Commits (Session B)
- `0df6183` — shipping_knowledge.py + librarian_index + doc_reader signals
- `d85f686` — Phase 2: ocean_tracker.py + tracker.py wiring + email sections
- `25af8d1` — Consolidate Global Tracking email
- `6c0e9cf` — POL/POD timing table + BL/container summary
- `32e6cc7` — All timestamps in Israel time
