# SESSION 30 — CONTEXT
## Date: February 16, 2026 (night)
## Branch: session30-tracker-upgrades (DO NOT merge to main yet)
## Resume: git checkout session30-tracker-upgrades && cat docs/SESSION30_CONTEXT.md

---

## ASSIGNMENTS STATUS

### Assignment 1: Wire table_extractor into tracker path — DONE `21ac348`
- **File**: functions/lib/tracker.py
- **Changes**:
  - Added Step 2a: after existing text extraction, calls TableExtractor on PDF attachments for structured table data (list-of-dicts)
  - Added `_merge_container_table_data()` function: scans table headers for container/seal/weight/package columns, extracts structured container details
  - Added 2 new keys to `_extract_logistics_data()` result dict: `seals`, `container_details`
  - All additive — existing extraction completely untouched
- **Cost**: FREE (pdfplumber tables, Priority 1)
- **Tests**: 452 passed, 5 failed (pre-existing), 2 skipped

### Assignment 2: Add Delivery Order recognition (Sea) — DONE `8aecf83`
- **File**: functions/lib/document_parser.py
- **Finding**: D/O recognition ALREADY EXISTED (scoring, routing, extraction, deal matching all built)
- **Changes**: Added 3 new optional fields to `_extract_do_fields()`:
  - `pickup_location` — terminal/warehouse/collection point (EN + HE patterns)
  - `release_date` — date of release (EN + HE patterns)
  - `agent_name` — shipping agent issuing the D/O (EN + HE patterns)
  - Added to REQUIRED_FIELDS as "optional" (won't affect existing completeness scoring)
- **Tests**: 452 passed, baseline intact

### Assignment 3: Add Delivery Order recognition (Air) — NOT STARTED
- **Research completed**, findings below:
- air_cargo_tracker.py (555 lines) already handles AWB polling via Maman API
- air_waybill doc type exists in document_parser.py (lines 93-112) with extraction
- delivery_order type is SEA-focused (references BL, vessel)
- **NEED**: Add air_delivery_order type to document_parser.py with keywords:
  - "air delivery order", "ADO", "cargo release notice", "הודעת שחרור מטען"
- **NEED**: Extract air-specific fields: awb_ref, terminal (Maman/Swissport), release_status, storage_fees
- **NEED**: Wire into tracker — match ADO to existing deal via AWB number
- Maman credentials NOT configured yet — focus on email-based extraction only

### Assignment 4: Add Booking Confirmation recognition — NOT STARTED
- **Pre-research**: tracker.py already has `booking` and `booking_bare` patterns
- Likely partially working — investigate before building

### Assignment 5: Create shipping_agents Firestore collection — NOT STARTED
- Agent→carrier mapping documented in SESSION29_CONTEXT.md
- Need: Firestore collection + cache in tracker.py + agent→carrier resolution

### Assignment 6: Verify UK Tariff Integration — NOT STARTED
- Report-only task, no code changes expected

---

## COMMIT LOG (feature branch)

```
8aecf83 Add pickup_location, release_date, agent_name to delivery order extraction
21ac348 Wire table_extractor into tracker path for BL table data
```

---

## FILES MODIFIED ON THIS BRANCH

- `functions/lib/tracker.py` — Assignment 1 (Step 2a table extraction + _merge_container_table_data + new result keys)
- `functions/lib/document_parser.py` — Assignment 2 (3 new fields in _extract_do_fields + REQUIRED_FIELDS)
- `docs/SESSION30_CONTEXT.md` — this file

---

## COST PRIORITY RULES (from user)

| Priority | Cost | Methods | When |
|----------|------|---------|------|
| 1 — FREE | $0.00 | pdfplumber, pypdf, regex, templates, bol_prefixes, brain memory, reference validation | ALWAYS FIRST |
| 2 — CHEAP | ~$0.001 | Gemini Flash gap filling, selective tool-calling | Only if Priority 1 got thin results |
| 3 — MODERATE | ~$0.01-0.03 | Claude Sonnet for HS classification | Only for classification |
| 4 — EXPENSIVE | $0.10+ | Three-way cross-check (Claude+Gemini+ChatGPT) | Only on disagreement |

NEVER call AI for data that regex/tables/templates already extracted.

---

## FUTURE ENRICHMENT — Reference Data Collections

### 1. CONTAINER TYPES (reference_container_types)
Standard ISO container codes for validation during extraction.

| Code | Description |
|------|-------------|
| 20GP | 20ft General Purpose |
| 20HC | 20ft High Cube |
| 40GP | 40ft General Purpose |
| 40HC | 40ft High Cube |
| 40OT | 40ft Open Top |
| 20RF | 20ft Reefer |
| 40RF | 40ft Reefer |
| 20FR | 20ft Flat Rack |
| 40FR | 40ft Flat Rack |
| 45HC | 45ft High Cube |
| 20TK | 20ft Tank |

Fields: code, description_en, description_he, teu_equivalent, max_weight_kg, internal_volume_cbm

### 2. ULD TYPES (reference_uld_types)
Unit Load Devices for air cargo validation.

| Code | Description |
|------|-------------|
| PMC | Pallet |
| AKE | Container (LD3) |
| PAG | Pallet |
| PLA | Pallet |

Fields: code, description, max_weight_kg, dimensions

### 3. PACKAGE TYPES (reference_package_types)
Customs packaging codes from Israeli port/customs catalog.

| Code | Description |
|------|-------------|
| CTN | Carton |
| PLT | Pallet |
| BAG | Bag |
| DRM | Drum |
| BDL | Bundle |
| PKG | Package |
| BLK | Bulk |
| ROL | Roll |

Fields: code, description_en, description_he

### 4. Community Tables (reference from shaarolami-query.customs.mof.gov.il)
Official Israeli customs reference tables used in customs declarations.
Check what's available and store relevant ones in Firestore for lookup during classification.

### Validation Rules (future):
- Container number: 4 letters + 7 digits (ISO 6346) — already implemented
- Container TYPE: validate against reference_container_types
- Package type: validate against reference_package_types
- ULD type: validate against reference_uld_types

---

## SHIPPING AGENT MAPPING (from Session 29)

| Agent | Domain | Carrier | Role |
|-------|--------|---------|------|
| KONMART | konmart.co.il | YANG_MING | shipping_agent |
| Rosenfeld Shipping | rosenfeld.net | SALAMIS | shipping_agent |
| Carmel International | carmelship.co.il | ADMIRAL | shipping_agent |

Note: Carmel also operates COSCO Israel (50% JV), but COSCO emails come from coscon.com/coscoshipping.com.

---

## KEY RESEARCH FINDINGS (for next session)

### Delivery Order (Sea) — existing system
- document_parser.py:195-213 — D/O keyword scoring
- document_parser.py:859-920 — _extract_do_fields() (now 7 fields)
- main.py:1211 — shipping path routing for D/O keywords
- tracker.py:1556 — attachment filename detection
- Deal matching works via BOL/container — D/Os link to existing deals automatically

### Air Cargo — existing system
- air_cargo_tracker.py — 555 lines, Maman API client, AWB polling, alert detection
- AIRLINE_PREFIXES: 27 airlines with terminal routing (maman/swissport)
- tracker.py AWB extraction: lines 505-514 (air context guard from Fix 5)
- tracker.py AWB registration: lines 887-894 (auto-registers for polling)
- Maman credentials NOT configured (need phone call to 03-9715388)

### Deal Tracking Lifecycle
- ShipmentPhase enum: INITIAL → ORDER_RECEIVED → PRE_SHIPMENT → SHIPMENT_LOADED → CIF_COMPLETION → READY_FOR_DECLARATION → DECLARED → RELEASED
- Deal status: "active", "pending", "stopped" (at deal level)
- Container step tracking via tracker_container_status (derived from TaskYam API dates)
- _match_or_create_deal matches by: thread → BOL → AWB → container → booking
- _update_deal_from_observation: merges data, never overwrites existing fields

### Test Baseline
- 452 passed, 5 failed (pre-existing bs4/HTML), 2 skipped
- Same baseline maintained throughout all changes
