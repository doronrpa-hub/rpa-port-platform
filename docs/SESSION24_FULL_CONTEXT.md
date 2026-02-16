# SESSION 24 — FULL CONTEXT FOR FUTURE SESSIONS
## What was done, what SHOULD work, and what to VERIFY

**Date:** February 15, 2026
**Commits:** 23fbdac, 761fe4a, cf6a4b6, edda600
**Deploy:** Local firebase deploy successful at 22:32 UTC, all 26 functions updated
**Tests:** 129/129 passing locally
**Audit:** Triggered manually at 20:40 UTC, processing 30-day email backlog

---

## RULE: TRUST NOTHING. VERIFY EVERYTHING.

Past sessions have shown that code can pass tests locally but fail silently in production.
Before assuming anything works, CHECK THE CLOUD FUNCTION LOGS for actual evidence.

---

## CHANGE 1: Learning Step (Step 8) in tool_calling_engine.py

**What:** After tool_calling_classify() produces validated classifications, it now calls
SelfLearningEngine.learn_classification() to store product->HS code mappings.

**File:** `functions/lib/tool_calling_engine.py` ~line 295
**Grep:** `grep "Step 8" functions/lib/tool_calling_engine.py`
**Committed in:** 23fbdac (Session 23)

**HOW TO VERIFY IT WORKS:**
1. Search Cloud Function logs for `[TOOL ENGINE] Learned` — if present, learning is firing
2. Search for `[TOOL ENGINE] Learning error` — if present, learning is failing silently
3. Check Firestore `learned_classifications` collection — are NEW docs appearing after classification emails?
4. If the collection is STATIC (not growing), the learning loop is broken even if no errors show

**KNOWN RISKS:**
- The kwarg is `product_description=` (matches self_learning.py:314 signature)
- Only learns from classifications with verification_status "official" or "verified"
- If verification_loop changes status names, this silently stops learning
- The try/except means failures are NON-FATAL — check logs, don't assume

---

## CHANGE 2: Circular Import Fix

**What:** Moved 6 imports from top-level of tool_calling_engine.py into the function body
of tool_calling_classify() to break circular dependency with classification_agents.py.

**File:** `functions/lib/tool_calling_engine.py` ~line 85 (comment) and ~line 86 (lazy import)
**Grep:** `grep "Lazy imports" functions/lib/tool_calling_engine.py`
**Committed in:** 23fbdac (Session 23)

**HOW TO VERIFY IT WORKS:**
1. If tool calling works AT ALL in production, the import is fine
2. Search logs for `ImportError` or `NameError` related to these 6 functions
3. Search for `TOOL_CALLING_AVAILABLE` — should be True in logs
4. If tool calling silently falls back to old pipeline, check if these imports failed

**KNOWN RISKS:**
- classification_agents.py STILL imports from tool_calling_engine.py (wrapped in try/except)
- If someone adds a new top-level import in either file, the circular dependency could resurface
- The proper long-term fix is extracting shared functions into a third module

---

## CHANGE 3: CC Email Silent Learning

**What:** Previously, `if not is_direct: continue` skipped ALL CC emails entirely.
Now CC emails flow through Pupil (Phase A observation) and Tracker (is_direct=False)
for silent learning, without ever sending a reply.

**File:** `functions/main.py` ~lines 1095-1135
**Grep:** `grep "cc_observation" functions/main.py`
**Committed in:** 23fbdac (Session 23)

**HOW TO VERIFY IT WORKS:**
1. Doron CCs rcb@ on a client email -> check logs for `CC observation:`
2. Check Firestore `rcb_processed` — new docs with `type: "cc_observation"`?
3. Check `pupil_observations` — new entries from CC email senders?
4. Check `tracker_observations` — shipping data extracted from CC emails?
5. CRITICAL: Verify NO reply emails were sent for CC observations

**KNOWN RISKS:**
- If pupil_process_email() ever changes to send replies in Phase A, CC emails will get replies
- tracker_process_email(is_direct=False) relies on tracker checking is_direct before sending
  - Verified: tracker.py line 278-279 checks is_direct before email notifications
- Domain filter is NOT applied to CC emails (intentional) — any sender when CC'd
- Volume: Pupil Phase A is FREE (Firestore only), Tracker is_direct=False is mostly FREE

---

## CHANGE 4: Air Cargo Tracker (Maman API)

**What:** New module for tracking AWB status at Ben Gurion Airport cargo terminals.
Integrates with Maman API (REST, token auth) and stubs Swissport.

**File:** `functions/lib/air_cargo_tracker.py` (NEW — entire file, 22,542 bytes)
**Committed in:** 761fe4a (Session 24)

**Components:**
- `MamanClient` — REST API client for mamanonline.maman.co.il/api/v1
- `SwissportClient` — STUB only, no API yet
- `parse_awb()` — parse "114-12345678" into prefix, serial, airline, terminal
- `register_awb(db, awb_number, deal_id)` — create/update doc in tracker_awb_status
- `poll_air_cargo(db, get_secret_func)` — poll all active AWBs, update status, fire alerts
- `poll_air_cargo_for_tracker(db, firestore, get_secret)` — entry point for scheduler

**Alerts:** awb_arrived, customs_hold, storage_risk (>48h), customs_released

**WILL NOT WORK until Maman credentials configured:**
- Store in rcb_secrets as: maman_username, maman_password
- To register: Call Maman at 03-9715388
- Swagger: https://mamanonline.maman.co.il/swagger/index.html

---

## CHANGE 5: AWB Registration in Tracker

**What:** When tracker creates or updates a deal with an AWB number, it now calls
register_awb() to add the AWB to tracker_awb_status for polling.

**File:** `functions/lib/tracker.py` ~line 743 (_create_deal) and ~line 838 (_update_deal)
**Grep:** `grep "register_awb" functions/lib/tracker.py`
**Committed in:** 761fe4a (Session 24)

**Also fixed:** `awb_number` added to field_map in _update_deal_from_observation
(pre-existing gap — AWBs from follow-up emails weren't being saved to deals)

---

## CHANGE 6: Air Cargo Polling in rcb_tracker_poll

**What:** poll_air_cargo_for_tracker() called at end of rcb_tracker_poll, after sea freight.

**File:** `functions/main.py` ~line 1910
**Grep:** `grep "poll_air_cargo_for_tracker" functions/main.py`
**Committed in:** 761fe4a (Session 24)

---

## CHANGE 7: General Cargo Polling Branch

**What:** Added elif branch in tracker_poll_active_deals() for deals with no containers
and no AWB — queries TaskYam by storage_id or manifest number.

**File:** `functions/lib/tracker.py` ~line 1147
**Grep:** `grep "elif.*awb_number" functions/lib/tracker.py`
**Committed in:** cf6a4b6 (Session 24)

**Branch logic (mutually exclusive):**
```
if containers:              # FCL — UNCHANGED
elif manifest and txn_ids:  # Specific general cargo — UNCHANGED
elif not awb_number:        # NEW: broad general cargo (storage_id or manifest-only)
# else: AWB-only deals -> air cargo tracker handles separately
```

**Self-healing:** _enrich_deal_from_taskyam backfills manifest + transaction_ids,
promoting deal to the more specific branch on next poll.

---

## CHANGE 8: Shipping-Only Routing (BL -> Tracker)

**What:** Emails with only shipping documents (BL, AWB, booking, delivery order, packing list)
and NO invoice are now routed directly to Tracker, skipping Classification entirely.

**File:** `functions/main.py` ~lines 1209-1255
**Grep:** `grep "shipping_tracker" functions/main.py`
**Committed in:** edda600 (Session 24)

**Edge cases verified:**
| Scenario | Route |
|----------|-------|
| Invoice + BL | Classification (critical case preserved) |
| BL only | Tracker |
| AWB only | Tracker |
| Booking only | Tracker |
| Certificate only | Classification (safe default — NOT a shipping doc) |
| BL + "classify" in body | Classification (intent override) |
| Random PDF | Classification (default) |

**INTENTIONALLY EXCLUDED from _shipping_kw:** 'certificate', 'תעודת'
(trade compliance docs, not shipping docs — could be regulatory check requests)

---

## CHANGE 9: Brain Daily Digest (07:00 AM)

**What:** Wired existing brain_daily_digest() from brain_commander.py into
rcb_daily_digest Cloud Function at 07:00 Israel time.

**File:** `functions/main.py` ~line 2003
**Grep:** `grep "rcb_daily_digest" functions/main.py`
**Committed in:** cf6a4b6 (Session 24)

**Also fixed:** Greeting changed from "אבא" to "דורון" in brain_commander.py

**KNOWN RISK:** brain_daily_digest() was orphaned since it was written — may have bugs
that were never caught. Digest content is thin (only brain_commander observations).

---

## CHANGE 10: Overnight Audit (02:00 AM)

**What:** New diagnostic scan that runs nightly. READ-ONLY except writing results
to Firestore.

**File:** `functions/lib/overnight_audit.py` (NEW) + `functions/main.py` ~line 2036
**Committed in:** edda600 (Session 24)
**Schedule:** 02:00 Israel time, 2GB memory, 540s timeout
**First manual run:** Triggered at 20:40 UTC Feb 15

**What it checks:**
1. Re-processes last 30 days of emails through Pupil + Tracker (silent, is_direct=False)
2. Memory hit rate on learned_classifications
3. Ghost deal count (deals with no polling path)
4. AWB status count
5. Brain index size and recent growth
6. Sender/doc-type analysis from rcb_processed
7. Collection counts across 19 Firestore collections

**Results saved to:** `overnight_audit_results/{audit_YYYYMMDD_HHMMSS}`

---

## THINGS NOT DONE (DEFERRED)

### Stale Deal Cleanup
- Deals stuck as "active" with no updates for >30 days accumulate forever
- Fix: Add cleanup step to mark as "stale" (not "closed" so they can reactivate)

### Bug #4: Gemini MAX_TOKENS on Pupil
- Pupil learning hits MAX_TOKENS on some Gemini responses

### ETA/ETD Datetime Parsing
- tracker.py extracts ETA/ETD as raw strings, not parsed datetimes

### GitHub Actions Deploy Fix
- Broken since Session 23 — missing venv/ in Actions runner
- Workaround: local `firebase deploy --only functions --project rpa-port-customs`

---

## API CREDENTIALS NEEDED

### Maman Cargo Terminal API
- URL: mamanonline.maman.co.il
- Swagger: https://mamanonline.maman.co.il/swagger/index.html
- Test env: mamanonline.wsfreeze.co.il
- To register: Call 03-9715388
- Store as: maman_username, maman_password in rcb_secrets

### Swissport Cargo Terminal
- No public API — stub only
- Handles: FedEx (023), UPS (580)

---

## PRODUCTION VERIFICATION CHECKLIST

| Marker in logs | What it means | Expected? |
|----------------|---------------|-----------|
| `[TOOL ENGINE] Learned N classifications` | Step 8 learning fired | After any classification email |
| `CC observation:` | CC email observed | When Doron CCs rcb@ |
| `Air cargo: Maman credentials not configured` | Maman not ready | Until credentials added |
| `Registered AWB` | AWB registered for polling | When AWB email arrives |
| `Shipping docs only` | BL routed to tracker | When BL-only email arrives |
| `Brain daily digest starting` | Morning digest firing | At 07:00 Israel time |
| `Overnight audit starting` | Audit running | At 02:00 Israel time |
| `TOOL_CALLING_AVAILABLE: True` | Tool calling loaded | On every function start |

## COLLECTIONS TO MONITOR

| Collection | Should grow when... | If static = |
|------------|--------------------|----|
| learned_classifications | Classification emails processed | Step 8 broken |
| pupil_observations | Any email (TO or CC) | Pupil or CC learning broken |
| tracker_awb_status | AWB emails arrive | register_awb broken |
| rcb_processed (type=cc_observation) | CC emails arrive | CC learning broken |
| rcb_processed (type=shipping_tracker) | BL-only emails arrive | BL routing broken |
| brain_daily_digest | Every morning at 07:00 | Digest function broken |
| overnight_audit_results | Every night at 02:00 | Audit function broken |

## VERIFICATION SCRIPT
```bash
echo "1. Step 8:" && grep "Step 8" functions/lib/tool_calling_engine.py
echo "2. Lazy imports:" && grep "Lazy imports" functions/lib/tool_calling_engine.py
echo "3. CC observation:" && grep "CC observation" functions/main.py
echo "4. cc_observation type:" && grep "cc_observation" functions/main.py
echo "5. air_cargo_tracker:" && ls -la functions/lib/air_cargo_tracker.py
echo "6. poll_air_cargo:" && grep "poll_air_cargo_for_tracker" functions/main.py
echo "7. register_awb:" && grep "register_awb" functions/lib/tracker.py
echo "8. awb field_map:" && grep "awb_number.*awbs" functions/lib/tracker.py
echo "9. daily_digest:" && grep "rcb_daily_digest" functions/main.py
echo "10. general cargo:" && grep "storage_id" functions/lib/tracker.py | grep elif
echo "11. shipping_tracker:" && grep "shipping_tracker" functions/main.py
echo "12. learn_classification:" && grep "learn_classification" functions/lib/tool_calling_engine.py
```
All 12 should return results. Any missing = code was lost or not committed.
