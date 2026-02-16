# SESSION 31 — CONTEXT
## Date: February 16, 2026 (night)
## Branch: session31-enhancements (NOT merged — review tomorrow)
## Resume: git checkout session31-enhancements && cat docs/SESSION31_CONTEXT.md

---

## ASSIGNMENTS STATUS — ALL 7 DONE

### Assignment 1: FCL vs LCL Detection — DONE `8b12239` + `0f9097f`
- **Files**: functions/lib/tracker.py, functions/lib/document_parser.py
- **Changes**:
  - Multi-signal LCL detection:
    - Signal A: Explicit keywords (LCL, CFS, consolidation, groupage, מיכול, מטען חלקי)
    - Signal B: CFS warehouse names (Gadot, Atta, Tiran, גדות, עטא, טירן)
    - Signal C: House BL cargo description co-occurrence (marking+dims+units+CBM, 3 of 4)
  - Decision tree:
    1. Master BL (known carrier prefix) + container+seal → FCL (default)
    2. House BL + marking+dims+units+CBM co-occurring → LCL
    3. Keywords LCL/CFS/consolidation/מיכול → LCL (override)
    4. CFS warehouse name → LCL
  - `freight_load_type` field added to deals ('FCL' default, 'LCL' when detected)
  - `_infer_freight_kind()` returns 'LCL' when detected
  - `_update_deal_from_observation()` upgrades to LCL if later evidence found (never downgrades)
  - `_detect_lcl()` shared helper in document_parser.py for BL/D-O/booking extractors
- **Cost**: FREE (pure regex, Priority 1)
- **Tests**: 452 passed, baseline intact

### Assignment 2: Import/Export Lifecycle Enhancement — DONE `cbcaaad`
- **File**: functions/lib/tracker.py
- **Changes**:
  - `_infer_direction()`: POL/POD port detection — Israeli port as POD = import (+3), as POL = export (+3)
  - `_create_deal()`: new fields `documents_received[]`, `expected_next_document`, `lifecycle_stage`
  - `_update_deal_from_observation()`:
    - Direction self-correction: new evidence overrides old guess, logs to timeline
    - Lifecycle tracking: appends doc types, detects out-of-order docs, logs anomalies
    - Recomputes expected_next_document after each update
  - `_compute_expected_next_doc()`: lifecycle maps for import/export doc sequences:
    - IMPORT: booking_confirmation → bill_of_lading → arrival_notice → delivery_order → customs_declaration
    - EXPORT: booking_confirmation → bill_of_lading → customs_declaration
  - TaskYam poll: LCL deals query general cargo path FIRST (manifest+txn or storage_id), then ALSO check containers for vessel/arrival info. FCL path completely unchanged.
- **Cost**: FREE (pure regex + Firestore, Priority 1)
- **Tests**: 452 passed, baseline intact
- **⚠️ NEEDS VERIFICATION**: TaskYam LCL routing change needs testing with real LCL deal data

### Assignment 3: CC Learning Pipeline Verification — DONE `b1cb077`
- **Files**: functions/lib/self_learning.py, functions/lib/tracker.py
- **Findings & Changes**:
  - CC pipeline IS live (main.py:1095-1129) — routes CC emails to pupil + tracker
  - `learn_tracking_extraction()` previously only fed 2 collections:
    - ✅ `learned_contacts` (sender profiles)
    - ✅ `learned_patterns` (doc patterns)
  - NOW also feeds 3 more:
    - ✅ `shipping_lines.bol_prefixes` — auto-learns new BOL prefix→carrier mappings
    - ✅ `shipping_agents` — auto-discovers domain→agent→carrier from CC emails
    - ✅ Template learning expanded — fires on good regex extraction (≥0.5 confidence with substance), not just LLM enrichment
  - All new learning blocks are non-fatal (try/except)
- **Cost**: FREE (Firestore writes only, Priority 1)
- **Tests**: 452 passed, baseline intact

### Assignment 4: Historical Email Backfill (ONE-TIME) — DONE `a8363b3`
- **Files**: functions/lib/self_learning.py, functions/lib/overnight_brain.py
- **Changes**:
  - `backfill_from_history(max_docs=2000)` method on SelfLearningEngine:
    - Scans `tracker_observations` and `rcb_processed` collections
    - Feeds each through `learn_tracking_extraction()` (reuses all learning logic)
    - Extracts agent→carrier, BOL prefixes, doc templates
    - READ-ONLY mining — no emails reprocessed or resent
  - overnight_brain.py Phase 0: runs backfill once, marks `brain_config/backfill_done` flag
  - Safety: max_docs=2000 limit, brain_config flag prevents re-runs
- **Cost**: FREE (Firestore reads only, Priority 1)
- **Status**: Will run on NEXT overnight brain execution, then mark itself done
- **Tests**: 452 passed, baseline intact

### Assignment 5: Reference Data Collections — DONE `f405c2f`
- **File**: functions/lib/tracker.py
- **Changes**:
  - `seed_reference_data(db)`: idempotent seed for 3 Firestore collections:
    - `reference_container_types`: 11 ISO codes (20GP, 20HC, 40GP, 40HC, 40OT, 20RF, 40RF, 20FR, 40FR, 45HC, 20TK) with TEU, max_weight_kg, internal_volume_cbm, description_en, description_he
    - `reference_uld_types`: 6 air cargo ULD codes (PMC, AKE, PAG, PLA, AAA, AMP) with max_weight, dimensions
    - `reference_package_types`: 12 customs codes (CTN, PLT, BAG, DRM, BDL, PKG, BLK, ROL, CAS, BOX, ENV, TBE) with description_en, description_he
  - `_load_reference_data(db)`: cached per cold start for validation during extraction
  - `validate_container_type()` / `validate_package_type()`: validation helpers
  - Wired into tracker pipeline cache initialization
- **Pending**: `seed_reference_data(db)` needs one-time call against production Firestore
- **Pending**: Community Tables from shaarolami-query.customs.mof.gov.il — not checked yet
- **Cost**: FREE (Firestore only, Priority 1)
- **Tests**: 452 passed, baseline intact

### Assignment 6: TaskYam Cross-Check for New Doc Types — DONE `6fb0957`
- **File**: functions/lib/tracker.py
- **Changes**:
  - `_create_deal()`: after creating deal with containers, runs immediate TaskYam query (capped at 3 containers) for real-time port status enrichment
  - `_update_deal_from_observation()`: when new containers added to existing deal, runs immediate TaskYam cross-check for those containers
  - Both inline checks are non-blocking (try/except), skip gracefully if no credentials
  - `get_secret_func` attached to observation dict after Firestore write (not stored in DB)
  - Supplements existing 30-minute poll with instant enrichment at email time
- **⚠️ NEEDS VERIFICATION**: TaskYam inline check adds latency to email processing (~1-3 seconds per container). Monitor performance.
- **Cost**: FREE (TaskYam API calls, no AI)
- **Tests**: 452 passed, baseline intact

### Assignment 7: Deal Intelligence & Self-Correction — DONE `d561f3c`
- **File**: functions/lib/tracker.py
- **Changes**:
  - Carrier self-correction: when BL confirms different carrier than agent guess, updates deal + logs to timeline
  - Duplicate deal detection: cross-signal check in `_match_or_create_deal()` — if BOL match finds deal A but container/booking match finds deal B, merges B into A
  - `_merge_deals()`: merges containers, source_emails, documents_received, fills empty fields from secondary, marks secondary as stopped+merged_into
  - All self-corrections logged to `tracker_timeline` for audit trail
- **Cost**: FREE (Firestore only, Priority 1)
- **Tests**: 452 passed, baseline intact

---

## COMMIT LOG (session31-enhancements branch)

```
d561f3c Add deal intelligence: carrier self-correction, duplicate merge, cross-signal detection
6fb0957 Add inline TaskYam cross-check for new containers on deal create/update
f405c2f Add reference data collections: container types, ULD types, package types
a8363b3 Add historical email backfill — one-time read-only mining of observations
b1cb077 Wire CC learning pipeline: auto-learn BOL prefixes, agent→carrier, templates
cbcaaad Add import/export lifecycle tracking and LCL general cargo TaskYam routing
0f9097f Refine LCL detection: add house BL cargo description co-occurrence signal
8b12239 Add FCL vs LCL detection for deals — keyword scan + CFS warehouse names
```

---

## FILES MODIFIED ON THIS BRANCH

- `functions/lib/tracker.py` — Assignments 1, 2, 5, 6, 7 (major changes)
- `functions/lib/document_parser.py` — Assignment 1 (LCL detection)
- `functions/lib/self_learning.py` — Assignments 3, 4 (learning pipeline + backfill)
- `functions/lib/overnight_brain.py` — Assignment 4 (backfill Phase 0)
- `docs/SESSION31_CONTEXT.md` — this file

---

## NEW FUNCTIONS ADDED

### tracker.py
| Function | Assignment | Purpose |
|----------|-----------|---------|
| `seed_reference_data(db)` | 5 | One-time seed for container/ULD/package reference collections |
| `_load_reference_data(db)` | 5 | Load reference caches per cold start |
| `validate_container_type(code)` | 5 | Validate container type against reference |
| `validate_package_type(code)` | 5 | Validate package type against reference |
| `_compute_expected_next_doc(docs, dir)` | 2 | Compute expected next document from lifecycle |
| `_merge_deals(db, fs, primary, secondary)` | 7 | Merge duplicate deals into primary |

### document_parser.py
| Function | Assignment | Purpose |
|----------|-----------|---------|
| `_detect_lcl(text)` | 1 | Multi-signal LCL detection (keywords + CFS names + cargo description) |

### self_learning.py
| Method | Assignment | Purpose |
|--------|-----------|---------|
| `backfill_from_history(max_docs)` | 4 | One-time mining of historical observations |

---

## NEW DEAL FIELDS (tracker_deals collection)

| Field | Type | Assignment | Purpose |
|-------|------|-----------|---------|
| `freight_load_type` | string | 1 | 'FCL' (default) or 'LCL' |
| `documents_received` | array | 2 | List of doc types received for this deal |
| `expected_next_document` | string | 2 | Next expected doc type based on lifecycle |
| `lifecycle_stage` | string | 2 | Current lifecycle stage name |
| `merged_into` | string | 7 | If deal was merged, ID of primary deal |

---

## NEW FIRESTORE COLLECTIONS

| Collection | Assignment | Doc Count | Purpose |
|------------|-----------|-----------|---------|
| `reference_container_types` | 5 | 11 | ISO container codes with dimensions/weights |
| `reference_uld_types` | 5 | 6 | Air cargo ULD codes |
| `reference_package_types` | 5 | 12 | Customs package codes (EN+HE) |
| `brain_config` | 4 | 1 (backfill_done) | One-time flags for brain tasks |

---

## ITEMS NEEDING VERIFICATION BEFORE MERGE

1. **TaskYam LCL routing** (Assignment 2): LCL deals now query general cargo FIRST, then containers. Verify with a real LCL deal that both paths execute correctly.

2. **TaskYam inline check latency** (Assignment 6): Inline TaskYam queries at deal create/update add ~1-3 seconds. Monitor email processing time.

3. **CC learning pipeline** (Assignment 3): BOL prefix auto-learning and agent auto-discovery need production monitoring — ensure no false positives (e.g., customer domains being incorrectly classified as shipping agents).

4. **Historical backfill** (Assignment 4): Will run on next overnight brain execution. Verify the `brain_config/backfill_done` flag is set after completion.

5. **seed_reference_data()** and **seed_shipping_agents()** need one-time calls against production Firestore.

6. **Deal merge logic** (Assignment 7): `_merge_deals()` marks secondary as stopped. Verify merged deals don't appear in active deal queries.

---

## PENDING TASKS FOR NEXT SESSION

### Not yet done:
- Community Tables from shaarolami-query.customs.mof.gov.il — need to check what's available
- Time gap learning per carrier (normal transit times) — mentioned in Assignment 7 but deferred
- Maman API configuration for air cargo (needs phone call to 03-9715388)

### One-time production tasks:
- Run `seed_reference_data(db)` once against production Firestore
- Run `seed_shipping_agents(db)` once (from Session 30, may already be done)
- Historical backfill runs automatically on next overnight brain

### Branch status:
- **Branch**: session31-enhancements
- **NOT merged to main** — review and merge tomorrow
- **All tests passing**: 452 passed, 5 failed (pre-existing bs4/HTML), 2 skipped

---

## COST PRIORITY RULES (unchanged)

| Priority | Cost | Methods | When |
|----------|------|---------|------|
| 1 — FREE | $0.00 | pdfplumber, pypdf, regex, templates, bol_prefixes, brain memory, reference validation | ALWAYS FIRST |
| 2 — CHEAP | ~$0.001 | Gemini Flash gap filling, selective tool-calling | Only if Priority 1 got thin results |
| 3 — MODERATE | ~$0.01-0.03 | Claude Sonnet for HS classification | Only for classification |
| 4 — EXPENSIVE | $0.10+ | Three-way cross-check (Claude+Gemini+ChatGPT) | Only on disagreement |

ALL Session 31 changes are Priority 1 — $0.00 cost (pure regex + Firestore).

---

## RESUME INSTRUCTIONS (office PC tomorrow)

```bash
git pull origin main
git fetch origin
git checkout session31-enhancements
cat docs/SESSION31_CONTEXT.md
```

Then:
1. Review each commit: `git log --oneline session31-enhancements | head -10`
2. Verify with real data (especially LCL routing and TaskYam inline checks)
3. If all good: `git checkout main && git merge session31-enhancements && git push origin main`
