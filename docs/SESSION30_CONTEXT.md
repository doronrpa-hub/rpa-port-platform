# SESSION 30 — CONTEXT
## Date: February 16, 2026 (night)
## Branch: session30-tracker-upgrades (merge to main when all done)

---

## ASSIGNMENTS THIS SESSION

### Assignment 1: Wire smart_extractor + table_extractor into tracker path
- Status: IN PROGRESS

### Assignment 2: Add Delivery Order recognition (Sea)
- Status: PENDING

### Assignment 3: Add Delivery Order recognition (Air)
- Status: PENDING

### Assignment 4: Add Booking Confirmation recognition
- Status: PENDING

### Assignment 5: Create shipping_agents Firestore collection
- Status: PENDING

### Assignment 6: Verify UK Tariff Integration (report only)
- Status: PENDING

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
