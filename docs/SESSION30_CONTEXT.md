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

### Assignment 3: Add Air Delivery Order recognition — DONE `1076f77`
- **Files**: functions/lib/document_parser.py, functions/lib/tracker.py, functions/main.py
- **Changes**:
  - New `air_delivery_order` doc type in `_DOC_TYPE_SIGNALS` with EN + HE scoring keywords
  - Strong: "air delivery order", "air release order", "cargo release notice", "הודעת שחרור מטען אווירי", "שחרור מטען אווירי"
  - Medium: "air release", "storage notice", "terminal release", AWB+release combos
  - Weak: "maman", "swissport", "cargo terminal", "storage fee", "דמי אחסנה"
  - New `_extract_air_do_fields()` function — extracts 7 fields:
    - `awb_reference` (critical) — AWB number XXX-XXXXXXXX format
    - `consignee` (critical) — deliver-to party
    - `terminal` (important) — Maman/Swissport detection
    - `release_status` (important) — released/hold/pending/ready
    - `storage_fees` (optional) — amount extraction
    - `flight_number` (optional) — airline flight
    - `agent_name` (optional) — issuing agent
  - Wired into `extract_structured_fields()` extractors dict
  - Added to `_REQUIRED_FIELDS` for completeness scoring
  - tracker.py: `_guess_doc_type_from_attachments()` — air D/O filenames detected before sea D/O
  - tracker.py: `_infer_direction()` — added "air delivery order", "cargo release notice" to import signals
  - main.py: `_shipping_kw` — added "air delivery order", "ado_", "cargo release", "שחרור מטען אווירי"
- **Cost**: FREE (pure regex, Priority 1)
- **Tests**: 452 passed, baseline intact

### Assignment 4: Add Booking Confirmation recognition — DONE `e5e4d3e`
- **Files**: functions/lib/document_parser.py, functions/lib/tracker.py
- **Finding**: tracker.py already extracts bookings/vessels/ETAs/ETDs/cutoffs — but NO booking_confirmation doc type existed in document_parser.py, and deal creation required BOL (bookings alone skipped)
- **Changes**:
  - **document_parser.py**:
    - New `booking_confirmation` doc type in `_DOC_TYPE_SIGNALS`:
      - Strong: "booking confirm", "אישור הזמנ", "booking no/number", "EBKG\d+"
      - Medium: "booking ref", "הזמנת הובלה/שילוח", "container cutoff", "doc cutoff", "vessel", "voyage"
      - Weak: "shipping instruction", "etd", "eta", "cut-off"
    - New `_extract_booking_fields()` function — extracts 8 fields:
      - `booking_number` (critical) — booking ref with explicit separator
      - `vessel` (important) — vessel/ship/M/V
      - `voyage` (important) — voyage number
      - `etd` (important) — expected departure date
      - `eta` (optional) — expected arrival date
      - `container_type` (optional) — e.g. "40HC", "20GP"
      - `container_quantity` (optional) — e.g. 2 from "2x40HC"
      - `cutoff_date` (optional) — general cutoff date
    - Added to `_REQUIRED_FIELDS` and `extractors` dict
  - **tracker.py**:
    - New PATTERNS: `voyage` and `container_type_qty` (e.g. "2x40HC")
    - `_extract_logistics_data()`: new keys `voyages` and `container_type_qty`
    - `_create_deal()`: stores `voyage` in deal
    - `_update_deal_from_observation()`: `voyage` in field_map
    - `_match_or_create_deal()`: bookings with vessel/shipping_line NOW create deals (BL links later via booking match)
    - `_guess_doc_type_from_attachments()`: recognizes booking filenames
- **Cost**: FREE (pure regex, Priority 1)
- **Tests**: 452 passed, baseline intact

### Assignment 5: Create shipping_agents Firestore collection — DONE `f5f2b16`
- **File**: functions/lib/tracker.py
- **Changes**:
  - New `_shipping_agent_cache`: `{domain: {agent_name, carriers: [...]}}` — cached per cold start
  - New `_load_shipping_agents(db)`: loads from `shipping_agents` Firestore collection
  - New `_resolve_agent_carrier(from_email, db)`: resolves sender domain → `{agent_name, carrier_name}`
  - New `seed_shipping_agents(db)`: one-time idempotent seed function for initial data:
    - `konmart` → domains: [konmart.co.il], carriers: [YANG_MING]
    - `rosenfeld` → domains: [rosenfeld.net], carriers: [SALAMIS]
    - `carmel` → domains: [carmelship.co.il], carriers: [ADMIRAL, COSCO]
  - `LOGISTICS_SENDERS`: moved konmart.co.il + carmelship.co.il from `shipping_line` → `shipping_agent`
  - Added `rosenfeld.net` to `shipping_agent`
  - Added `coscoshipping.com`, `coscon.com` to `shipping_line` (COSCO direct)
  - `_is_logistics_email()`: recognizes `shipping_agent` sender type
  - New Step 4d in pipeline: auto-resolves agent→carrier from email domain, fills `shipping_lines` if empty
  - `_create_deal()`: stores `agent_name` + `carrier_name` in deal
  - `_update_deal_from_observation()`: fills `agent_name` + `carrier_name` on updates (never overwrites)
- **Firestore collection**: `shipping_agents` (needs `seed_shipping_agents(db)` call to populate)
  - Doc schema: `{name, domains: [str], carriers: [str], role, notes}`
- **Cost**: FREE (Firestore cache + regex, Priority 1)
- **Tests**: 452 passed, baseline intact

### Assignment 6: Verify UK Tariff Integration — DONE (verification only)
- **Status**: FULLY OPERATIONAL, no changes needed
- **File**: functions/lib/uk_tariff_integration.py (446 lines, 0 stubs)
- **Tests**: functions/tests/test_uk_tariff_integration.py — 42/42 passing
- **Integrations**:
  - justification_engine.py Step 9 — IL vs UK comparison post-classification
  - cross_checker.py 4th source — UK tariff vote alongside Claude/Gemini/ChatGPT
  - overnight_brain.py Stream 6 — nightly sweep, 200 codes/run, 2 req/sec
- **Firestore**: `tariff_uk` collection with 7-day TTL cache
- **API**: UK Gov Trade Tariff (free, no key, https://trade-tariff.service.gov.uk/api/v2)

---

## COMMIT LOG (feature branch)

```
f5f2b16 Add shipping_agents Firestore collection with cache and agent→carrier resolution
e5e4d3e Add booking_confirmation document type and enhance booking-to-deal pipeline
1076f77 Add air_delivery_order document type for air cargo release notices
7d26827 Update SESSION30_CONTEXT.md with assignment status and research findings
8aecf83 Add pickup_location, release_date, agent_name to delivery order extraction
21ac348 Wire table_extractor into tracker path for BL table data
```

---

## FILES MODIFIED ON THIS BRANCH

- `functions/lib/tracker.py` — Assignments 1, 4, 5
- `functions/lib/document_parser.py` — Assignments 2, 3, 4
- `functions/main.py` — Assignment 3
- `docs/SESSION30_CONTEXT.md` — this file

---

## NEW FUNCTIONS ADDED (Assignments 3-5)

### document_parser.py
| Function | Assignment | Purpose |
|----------|-----------|---------|
| `_extract_air_do_fields(text)` | 3 | Extract AWB ref, terminal, release_status, storage_fees, flight, agent from air D/O |
| `_extract_booking_fields(text)` | 4 | Extract booking_number, vessel, voyage, ETD, ETA, container_type/qty, cutoff from booking confirmation |

### tracker.py
| Function | Assignment | Purpose |
|----------|-----------|---------|
| `_load_shipping_agents(db)` | 5 | Load shipping_agents collection into cache (per cold start) |
| `_resolve_agent_carrier(from_email, db)` | 5 | Resolve email domain → {agent_name, carrier_name} |
| `seed_shipping_agents(db)` | 5 | One-time seed: KONMART, Rosenfeld, Carmel into Firestore |

---

## NEW DICT KEYS / PATTERNS (Assignments 3-5)

### _DOC_TYPE_SIGNALS (document_parser.py)
- `air_delivery_order` — Assignment 3
- `booking_confirmation` — Assignment 4

### _REQUIRED_FIELDS (document_parser.py)
- `air_delivery_order`: awb_reference, consignee, terminal, release_status, storage_fees, flight_number, agent_name
- `booking_confirmation`: booking_number, vessel, voyage, etd, eta, container_type, container_quantity, cutoff_date

### PATTERNS (tracker.py)
- `voyage`: `(?:voyage|voy)[.:\s]*([A-Za-z0-9\-]{3,15})` — Assignment 4
- `container_type_qty`: `(\d+)\s*[xX*×]\s*(\d{2}(?:GP|HC|OT|RF|FR|TK))` — Assignment 4

### _extract_logistics_data result dict (tracker.py)
- `voyages: []` — Assignment 4
- `container_type_qty: []` — Assignment 4 (`[{qty: int, type: str}]`)
- `agent_name: str` — Assignment 5 (set by _resolve_agent_carrier)

### Deal fields (tracker_deals collection)
- `voyage` — Assignment 4 (stored in _create_deal, updated in _update_deal_from_observation)
- `agent_name` — Assignment 5 (shipping agent name, e.g. "KONMART")
- `carrier_name` — Assignment 5 (carrier name, e.g. "YANG_MING")

### LOGISTICS_SENDERS (tracker.py)
- NEW: `shipping_agent: ['konmart.co.il', 'carmelship.co.il', 'rosenfeld.net']`
- MOVED: konmart.co.il, carmelship.co.il from `shipping_line` → `shipping_agent`
- ADDED: `coscoshipping.com`, `coscon.com` to `shipping_line`

---

## NEW / UPDATED FIRESTORE COLLECTIONS

### shipping_agents (NEW — Assignment 5)
- **Seeded by**: `seed_shipping_agents(db)` (needs one-time call)
- **Doc ID**: agent slug (e.g. "konmart", "rosenfeld", "carmel")
- **Schema**: `{name: str, domains: [str], carriers: [str], role: str, notes: str}`
- **Cached by**: `_shipping_agent_cache` in tracker.py (loaded on first use per cold start)
- **Initial data**:
  - konmart → YANG_MING
  - rosenfeld → SALAMIS
  - carmel → ADMIRAL + COSCO

### tracker_deals (UPDATED — Assignments 4-5)
- New fields: `voyage`, `agent_name`, `carrier_name`

---

## PENDING TASKS (for next session)

### Assignment 7: Historical Backfill from Firestore (LOW priority, HIGH value)
- Scan ALL historical tracker_observations and rcb_processed
- For each email: extract shipping agent → carrier mappings
- For each email: learn document templates
- For each email: extract bol_prefix patterns
- READ-ONLY mining — do not reprocess or resend
- Store learned patterns into brain collections

### FCL vs LCL Detection (MEDIUM priority)
- Add freight_load_type to deals: "FCL" (default) or "LCL"
- Detection: "LCL", "CFS", "consolidation", "מיכול", "מטען חלקי" keywords
- CFS warehouse names: Gadot, Atta, Tiran → tag as LCL
- Affects: deal tracking level, D/O routing, pickup location

### CC Silent Learning Pipeline Verification
- CHECK: Is CC email pipeline feeding shipping_agents, learned_doc_templates, bol_prefix patterns?
- If not: wire brain.learn_tracking_extraction() to update these collections
- Goal: every CC email makes the system smarter, no human intervention

### seed_shipping_agents Execution
- Need to run `seed_shipping_agents(db)` once against production Firestore
- Can be done via overnight brain or one-time script

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

## SHIPPING AGENT MAPPING (from Session 29, implemented in Assignment 5)

| Agent | Domain | Carrier | Role | Firestore Doc |
|-------|--------|---------|------|---------------|
| KONMART | konmart.co.il | YANG_MING | shipping_agent | `shipping_agents/konmart` |
| Rosenfeld Shipping | rosenfeld.net | SALAMIS | shipping_agent | `shipping_agents/rosenfeld` |
| Carmel International | carmelship.co.il | ADMIRAL, COSCO | shipping_agent | `shipping_agents/carmel` |

Note: Carmel also operates COSCO Israel (50% JV), but COSCO emails come from coscon.com/coscoshipping.com (classified as shipping_line directly).

---

## KEY RESEARCH FINDINGS

### Delivery Order (Sea) — existing system
- document_parser.py:195-213 — D/O keyword scoring
- document_parser.py:862-920 — _extract_do_fields() (now 7 fields)
- main.py:1211 — shipping path routing for D/O keywords
- tracker.py:1580 — attachment filename detection (updated)
- Deal matching works via BOL/container — D/Os link to existing deals automatically

### Air Cargo — existing system
- air_cargo_tracker.py — 555 lines, Maman API client, AWB polling, alert detection
- AIRLINE_PREFIXES: 27 airlines with terminal routing (maman/swissport)
- tracker.py AWB extraction: lines 512-518 (air context guard from Fix 5)
- tracker.py AWB registration: lines 905-912 (auto-registers for polling)
- Maman credentials NOT configured (need phone call to 03-9715388)

### Deal Tracking Lifecycle
- ShipmentPhase enum: INITIAL -> ORDER_RECEIVED -> PRE_SHIPMENT -> SHIPMENT_LOADED -> CIF_COMPLETION -> READY_FOR_DECLARATION -> DECLARED -> RELEASED
- Deal status: "active", "pending", "stopped" (at deal level)
- Container step tracking via tracker_container_status (derived from TaskYam API dates)
- _match_or_create_deal matches by: thread -> BOL -> AWB -> container -> booking
- _update_deal_from_observation: merges data, never overwrites existing fields
- NEW: Bookings with vessel/shipping_line now create deals (BL links later)

### Test Baseline
- 452 passed, 5 failed (pre-existing bs4/HTML), 2 skipped
- Same baseline maintained throughout all 6 assignments
