# FLOW_AUDIT_SESSION_A — Deep Code Audit Report

**Date:** 2026-02-19
**Auditor:** Claude Opus 4.6
**Codebase State:** Post-Session 50d (commits through `1cfda99`)
**Mode:** READ ONLY — no code changes made

---

## Table of Contents

1. [Scenario Traces (5 end-to-end flows)](#scenario-traces)
2. [Nightly Pipeline Audit](#nightly-pipeline-audit)
3. [Memory System Audit](#memory-system-audit)
4. [Identity Graph Audit](#identity-graph-audit)
5. [Findings Summary (by severity)](#findings-summary)
6. [Dead Code](#dead-code)
7. [Test Coverage Gaps](#test-coverage-gaps)

---

## Scenario Traces

### Scenario 1: CC Email — External Shipper Sends Invoice + BL

**Setup:** Turkish shipper `exports@turksteel.com.tr` sends invoice + BL to
`doron@rpa-port.co.il` and CC's `rcb@rpa-port.co.il`. Subject: "Invoice CI-2026-4412 / BL MEDURS87654".

#### Exact Code Path

1. **Entry:** `main.py:740` → `rcb_check_email()` → `main.py:750` `_rcb_check_email_inner()`
2. **Graph API:** `main.py:771-780` fetches inbox messages from last 2 days
3. **Parse:** `main.py:788-799` extracts `from_email="exports@turksteel.com.tr"`, checks `is_direct`
   - `to_recipients` = `[{doron@rpa-port.co.il}]` — rcb@ NOT in toRecipients
   - `is_direct = False` (line 798-799)
4. **Self-skip:** `main.py:804` — from_email != rcb_email → passes
5. **[DECL] check:** `main.py:814` — "[DECL]" not in subject → skip
6. **CC path entered:** `main.py:854` — `not is_direct` → true

**CC Processing Chain:**

7. **Dedup:** `main.py:855-858` — MD5 of msg_id checked in `rcb_processed`
8. **Pupil:** `main.py:863-869` → `pupil_process_email()` — silent observation, extracts contacts, keywords, gaps. Safety lock: only sends review emails to `REVIEW_EMAIL` (doron@), max 3/day
9. **Tracker:** `main.py:872-880` → `tracker_process_email()` at `tracker.py:324`
   - Step 1: Dedup via `tracker_observations` (line 340)
   - Step 2: Extract body text (line 380)
   - Step 3: Brain memory check via `SelfLearningEngine.check_tracking_memory()` (line 420)
   - Step 4: Regex extraction via `_extract_logistics_data()` (line 450) — finds BOL `MEDURS87654`, containers
   - Step 5: Attachment text extraction (line 480)
   - Step 6: `_match_or_create_deal()` (line 520) — priority: thread → BOL → AWB → container → booking
   - Step 6b: Identity graph link via `link_email_to_deal()` (line 522-536)
   - Step 7: Brain learning via `learn_tracking_extraction()` (line 538)
   - Step 8: `_send_tracker_email()` — data guard at `_deal_has_minimum_data()` checks for containers/BOL/vessel before sending
   - Returns `tracker_result` with `deal_result`
10. **Sanctions:** `main.py:883-888` — `_screen_deal_parties()` checks shipper/consignee against OpenSanctions API
11. **Schedule:** `main.py:891-900` — `is_schedule_email()` checks if this is a vessel schedule notification
12. **Email Intent:** `main.py:904-915` — `process_email_intent()` at `email_intent.py:1214`
    - Extracts body text, detects privilege (NONE — external sender)
    - `detect_email_intent()` at `email_intent.py:188`
    - Regex scans: ADMIN (skip, not ADMIN), NON_WORK (no match), INSTRUCTION (no match), CUSTOMS_QUESTION (no match)
    - STATUS: no status keyword → no match
    - KNOWLEDGE_QUERY: no question mark, no domain keywords
    - Returns `{"intent": "NONE"}` → email intent does not handle, does not set `_cc_classified`
13. **Block A1:** `main.py:917-950` — keyword scan
    - `_cc_combined = "Invoice CI-2026-4412 / BL MEDURS87654 ..."` (lowered)
    - `"invoice"` is in `_cc_invoice_kw` → **MATCH**
    - Fetches attachments → has attachments
    - Generates `cc_rcb_id`
    - Strips HTML from body

14. **⚠️ CRITICAL BUG (S1-F1):** `main.py:935-941`
    ```python
    _cc_result = process_and_send_report(
        access_token, rcb_email, from_email, subject, ...
    ```
    `from_email` = `exports@turksteel.com.tr` — **external sender passed as `to_email`**
    - At `classification_agents.py:2969`: `_suppress_reply = not to_email` → `False` (to_email is truthy)
    - Classification runs, builds report
    - Report email **sent to `exports@turksteel.com.tr`** — an external party

15. **Mark processed:** `main.py:984-990` → `rcb_processed` doc written, `continue`

#### Findings

| ID | Severity | Description | Location |
|----|----------|-------------|----------|
| S1-F1 | **CRITICAL** | CC classification sends report to external sender `from_email` | `main.py:936` |
| S1-F2 | **CRITICAL** | Same bug in Gap 2 auto-trigger — `from_email` as fallback for `_to` | `main.py:963` |
| S1-F3 | MEDIUM | No admin fallback — if no @rpa-port.co.il in chain AND no follower_email, classification result stored but no human notified | `main.py:935-941` |
| S1-F4 | LOW | `helper_graph_send()` at `rcb_helpers.py:705` has `email_quality_gate` but it does NOT check recipient domain | `rcb_helpers.py:705` |

---

### Scenario 2: Direct Email — Team Member Asks "מה הסטטוס של BL MEDURS12345?"

**Setup:** `doron@rpa-port.co.il` sends to `rcb@rpa-port.co.il`: "מה הסטטוס של BL MEDURS12345?"

#### Exact Code Path

1. **Entry:** `main.py:788-799` — `is_direct = True` (rcb@ in toRecipients)
2. **Self-skip:** passes (doron ≠ rcb)
3. **[DECL] check:** no `[DECL]` → skip
4. **Direct path entered:** `main.py:992-999`
   - `from_email = "doron@rpa-port.co.il"` → ends with `@rpa-port.co.il` → `_reply_to = from_email`
5. **Dedup:** `main.py:1014-1016` — MD5 check in `rcb_processed`
6. **Brain Commander:** `main.py:1033-1047` — checks if this is a brain command → not a brain command
7. **Email Intent:** `main.py:1050-1067` → `process_email_intent()` at `email_intent.py:1214`
   - Body: "מה הסטטוס של BL MEDURS12345?"
   - Privilege: ADMIN (doron@ hardcoded)
   - `detect_email_intent()` at `email_intent.py:188`:
     - Step 1 ADMIN_INSTRUCTION: scans for "from now on" / "מעכשיו" etc. → no match
     - Step 2 NON_WORK: no match
     - Step 3 INSTRUCTION: no match
     - Step 4 CUSTOMS_QUESTION: no match (no HS code pattern, no "מה הסיווג")
     - Step 5 STATUS_REQUEST:
       - `_extract_status_entities()` scans for BL pattern: `MEDURS\d{5,10}` → matches `MEDURS12345`
       - `has_status_keyword`: STATUS_PATTERNS checks `מה\s*ה?מצב` → "מה הסטטוס" — **does it match?**

8. **⚠️ FINDING (S2-F1):** `email_intent.py:76-80`
   ```python
   STATUS_PATTERNS = [
       re.compile(r'(?:מה\s*ה?מצב|status|where\s*is|...)'),
       re.compile(r'(?:track|מעקב|עקוב\s*אחרי)'),
   ]
   ```
   The word "סטטוס" (Hebrew for "status") is NOT in `STATUS_PATTERNS`. The regex `מה\s*ה?מצב` matches "מה המצב" but NOT "מה הסטטוס".

   **However:** `entities` is truthy (has `bol_msc: MEDURS12345`) and `?` is present → falls through to `email_intent.py:257-264`:
   ```python
   if entities and '?' in combined:
       return {"intent": "STATUS_REQUEST", "confidence": 0.8, ...}
   ```
   So it works via the entity+question-mark fallback, NOT the status keyword regex.

9. **Status Handler:** `_handle_status_request()` at `email_intent.py:767`
   - `bol = "MEDURS12345"`, `container = None`
   - Calls `_find_deal_by_field(db, 'bol_number', 'MEDURS12345')` at `tracker.py:1078`

10. **⚠️ FINDING (S2-F2):** `tracker.py:1083-1086`
    ```python
    results = list(db.collection("tracker_deals")
                   .where(field, "==", value)
                   .where("status", "in", ["active", "pending"])
                   .limit(1).stream())
    ```
    Only searches `status IN ["active", "pending"]`. If the deal was completed (e.g., cargo released and status → "completed"), the status lookup returns `None` → "deal not found" reply. User gets "לא נמצאה משלוח תואם" for a deal that exists but is completed.

11. **If deal found:** `_build_status_summary()` at `email_intent.py:813` builds Hebrew text
12. **Reply:** `_send_reply_safe()` at `email_intent.py:571`
    - Domain check: doron@ ends with @rpa-port.co.il → passes
    - `is_direct_recipient()` check: rcb@ was in TO → passes (Session 50 fix)
    - Reply sent via `helper_graph_reply()` → threaded reply

13. **Intent handled:** Returns `{"status": "replied"}` → main.py marks read, writes rcb_processed, `continue`

#### Findings

| ID | Severity | Description | Location |
|----|----------|-------------|----------|
| S2-F1 | MEDIUM | Hebrew "סטטוס" not in STATUS_PATTERNS — only works via `?` fallback | `email_intent.py:76-80` |
| S2-F2 | MEDIUM | Status lookup only searches active/pending deals — completed deals invisible | `tracker.py:1083-1086` |

---

### Scenario 3: CC Email — Shipper CC's rcb@ on Packing List (No Invoice)

**Setup:** `shipping@msc.com` sends packing list to `logistics@rpa-port.co.il` CC `rcb@rpa-port.co.il`. Subject: "PL for BL MEDURS99999 / 2x40HC".

#### Exact Code Path

1. **Entry:** `main.py:788-799` — `is_direct = False`
2. **CC path:** `main.py:854`
3. **Pupil:** silent observation
4. **Tracker:** `tracker_process_email()` processes → extracts BOL, containers → creates/updates deal
5. **Schedule:** no schedule keywords
6. **Email Intent:** body has no question, no status keyword → `NONE`
7. **Block A1:** `main.py:920-922`
   - `_cc_combined` = "pl for bl medurs99999 / 2x40hc ..."
   - Invoice keywords: `['invoice', 'חשבונית', 'proforma', 'commercial invoice', 'חשבון מסחרי', 'פרופורמה']`
   - "packing list" does NOT match any invoice keyword → **Block A1 skipped**
8. **Gap 2:** `main.py:952-982`
   - `tracker_result.get('deal_result', {}).get('classification_ready')` → checks if deal has both invoice + shipping doc
   - If this is the first shipping doc and no invoice exists yet → `classification_ready = False` → Gap 2 skipped
   - If deal already had an invoice from prior email → `classification_ready = True` → auto-trigger fires

9. **If Gap 2 fires:** `main.py:963`
   ```python
   _to = _deal_data.get('follower_email', from_email) or from_email
   ```
   **S3-F3:** `follower_email` is a deal field that may or may not be set. Default is `from_email` = `shipping@msc.com` (external). Same domain leak risk as S1-F1, but gated by `follower_email` being set first.

10. **Mark processed:** `main.py:984-990` → `continue`

#### Findings

| ID | Severity | Description | Location |
|----|----------|-------------|----------|
| S3-F1 | **CRITICAL** | Block A1 CC classification passes `from_email` (external) as `to_email` to `process_and_send_report()` | `main.py:936` |
| S3-F2 | **CRITICAL** | `process_and_send_report()` has NO domain checking on `to_email` — `_suppress_reply = not to_email` only checks for None/empty | `classification_agents.py:2969` |
| S3-F3 | HIGH | Gap 2 auto-trigger falls back to external `from_email` when `follower_email` not set | `main.py:963` |

---

### Scenario 4: Direct Email — External Sender with Invoice, No Team in Chain

**Setup:** `factory@chinawidgets.cn` sends invoice directly TO `rcb@rpa-port.co.il` with no other @rpa-port.co.il addresses in CC. Subject: "Commercial Invoice for Order PO-2026-789".

#### Exact Code Path

1. **Entry:** `main.py:788-799` — `is_direct = True` (rcb@ in toRecipients)
2. **Self-skip:** passes
3. **Direct path:** `main.py:992-1011`
   - `from_email = "factory@chinawidgets.cn"` → does NOT end with @rpa-port.co.il
   - Else branch at `main.py:1001-1011`:
     ```python
     _all_recipients = to_recipients + msg.get('ccRecipients', [])
     for _r in _all_recipients:
         _addr = _r.get('emailAddress', {}).get('address', '').lower()
         if _addr.endswith('@rpa-port.co.il') and _addr != rcb_email.lower() and _addr != 'cc@rpa-port.co.il':
             _reply_to = _r.get('emailAddress', {}).get('address', '')
             break
     ```
   - toRecipients = `[{rcb@rpa-port.co.il}]` — excluded by `_addr != rcb_email.lower()`
   - ccRecipients = `[]` (no CC)
   - **`_reply_to = None`** → correct behavior
   - Log: "External sender factory@chinawidgets.cn → no team address in chain, will classify but NOT reply"

4. **Dedup:** MD5 check passes
5. **Brain Commander:** not a brain command
6. **Email Intent:** `process_email_intent()` at `email_intent.py:1214`
   - Privilege: NONE (external)
   - Body may be short ("Please find attached commercial invoice...")
   - Scans for intent → likely NONE or KNOWLEDGE_QUERY
   - Even if intent detected, `_send_reply_safe()` blocks reply: `from_email` doesn't end with @rpa-port.co.il → returns False
   - Intent handler returns without `status: "replied"` → falls through

7. **Knowledge Query:** `main.py:1072-1097` — `detect_knowledge_query()` checks if it's a question
   - Has attachments → NOT a knowledge query (knowledge queries are text-only)

8. **Shipping-only routing:** `main.py:1101-1147`
   - Has "invoice" in attachment filename → `_has_inv = True`
   - Since `_has_inv` is true, this block does NOT route to tracker-only

9. **Classification:** `main.py:1149-1179`
   - `process_and_send_report(access_token, rcb_email, _reply_to, ...)`
   - `_reply_to = None` → at `classification_agents.py:2969`: `_suppress_reply = not None` → `True`
   - Classification runs fully (extraction → 6 agents → tools → verification → synthesis)
   - Report email NOT sent (suppressed)
   - Result stored in `rcb_classifications` collection

10. **Tracker + Pupil:** `main.py:1183-1200` — both process the email for learning

#### Findings

| ID | Severity | Description | Location |
|----|----------|-------------|----------|
| S4-F1 | LOW | Classification runs but nobody is notified — result only in Firestore. Consider a daily digest of suppressed classifications | `classification_agents.py:2969-2971` |
| S4-F2 | INFO | Direct path domain-check logic is correct (Session 47 fix). This is the pattern that should be replicated in the CC path (S1-F1 fix) | `main.py:997-1011` |

---

### Scenario 5: Direct Email — Team Member Sends 15-Product Invoice

**Setup:** `doron@rpa-port.co.il` sends to `rcb@rpa-port.co.il` an invoice with 15 different chemical products from Germany. Subject: "CI from BASF / 15 items for classification".

#### Exact Code Path

1. **Direct path:** `_reply_to = "doron@rpa-port.co.il"` (team sender)
2. **Brain Commander:** not a command → skip
3. **Email Intent:** scans body → "classification" keyword may match INSTRUCTION pattern at `email_intent.py:104`:
   ```python
   r'(?:^|\s)(?:classify|לסווג)\s'
   ```
   "classify" not standalone in subject. If no match → falls through.
4. **Knowledge Query:** has attachments → NOT a knowledge query
5. **Shipping-only:** has invoice → NOT shipping-only
6. **Classification:** `main.py:1149-1179` → `process_and_send_report()`

**Inside Classification Pipeline** (`classification_agents.py:2959`):

7. **Text extraction:** `extract_text_func()` → extracts ~2000+ chars from invoice PDF
8. **Agent 1 (Extraction):** Gemini Flash extracts 15 items (product, qty, price, origin)
   - If Gemini 429 (quota) → Claude fallback
   - If Claude fails → ChatGPT gpt-4o-mini fallback (Session 48 triple fallback)

9. **Pre-classify bypass:** Checks each item against `SelfLearningEngine.check_classification_memory()`
   - If memory confidence ≥ 90% → bypass AI classification for that item
   - `PRE_CLASSIFY_BYPASS_ENABLED = True` (feature flag)

10. **Elimination Engine:** `eliminate()` runs for each item (Session 33, D1-D8)
    - TariffCache loads tariff data once per run
    - 8 levels: section scope → chapter notes → GIR 1 → GIR 3 → Others gate → AI consultation

11. **Tool-Calling Engine:** `tool_calling_engine.py`
    - **`_MAX_ROUNDS = 15`**, **`_TIME_BUDGET_SEC = 180`** (Session 48 fix)
    - Step 4b: Pre-enrichment fires:
      - `lookup_country` (origin: Germany)
      - `search_pubchem` (chemical products trigger `_CHEMICAL_TRIGGERS`)
      - `convert_currency` or `bank_of_israel_rates` (EUR → ILS)
    - Step 5: AI tool loop — Gemini primary, Claude fallback
    - 15 items × (search_tariff + verify_hs_code + chapter_notes) ≈ 45+ tool calls

12. **⚠️ FINDING (S5-F1):** With 15 items, the tool-calling engine needs at minimum:
    - 1 extract_invoice + 15 search_tariff + 15 verify_hs_code + 15 get_chapter_notes = **46 tool calls**
    - `_MAX_ROUNDS = 15` (each round can have multiple tool calls, but Gemini/Claude may batch differently)
    - `_TIME_BUDGET_SEC = 180` (3 minutes)
    - If AI calls tools one-at-a-time (common with Gemini): 46 calls × ~4s each = ~184s → **exceeds time budget**
    - Session 48 added "forced final answer" when max rounds hit — but partial results lose items

13. **Verification Engine:** `verification_engine.py` runs Phase 4 (bilingual) + Phase 5 (knowledge) for each item
14. **Cross-Reference Pipeline:** `tool_calling_engine.py` Step 7d2 — EU TARIC + US HTS for each validated HS code
15. **Synthesis Agent 6:** Gemini Pro generates Hebrew summary
16. **Email:** `build_classification_email()` sends branded report to doron@rpa-port.co.il

#### Findings

| ID | Severity | Description | Location |
|----|----------|-------------|----------|
| S5-F1 | HIGH | 15-product invoices likely exceed tool-calling round/time limits, producing partial results | `tool_calling_engine.py:542-544` |
| S5-F2 | MEDIUM | No item-level chunking — if engine hits max rounds, ALL items get truncated rather than batching in groups of 5 | `tool_calling_engine.py` |
| S5-F3 | LOW | Pre-enrichment fires `search_pubchem` for ALL 15 items even if only 3 are chemicals — trigger is per-invoice, not per-item | `tool_calling_engine.py` Step 4b |

---

## Nightly Pipeline Audit

### Architecture

Three nightly systems run sequentially:

| Time (IL) | Function | File | Purpose |
|-----------|----------|------|---------|
| 20:00 | `rcb_overnight_brain` | `overnight_brain.py` | 12-stream AI enrichment, $3.50 cap |
| 02:00 | `rcb_nightly_learn` | `nightly_learn.py` | 4-step index builder (zero AI cost) |
| 02:00 | `rcb_overnight_audit` | `overnight_audit.py` | Diagnostic scan |
| 02:00 | `rcb_daily_backup` | `main.py` | GCS NDJSON backup |
| 03:30 | `rcb_ttl_cleanup` | `main.py` | TTL deletion (backup-guarded) |

### Overnight Brain (`overnight_brain.py`)

**Entry:** `run_overnight_brain(db, get_secret_func)` at line 1869

**Orchestrator flow:**
1. Creates `CostTracker()` with `BUDGET_LIMIT = $3.50`
2. Loads checkpoint from `brain_run_progress/{date}` (crash recovery, line 1848-1853)
3. Restores prior spend + completed_streams if resuming (line 1882-1888)
4. Gets `GEMINI_API_KEY` — if missing, all AI streams skipped (line 1903-1912)
5. Phase 0: One-time historical backfill (line 1916-1935)
6. Phases A-H: 12 streams in priority order, checkpoint after each

**Stream execution order:**

| Phase | Stream | Cost | Depends on AI? |
|-------|--------|------|----------------|
| A | 6: UK Tariff API | $0.00 | No |
| B | 3: CC email learning | ~$0.01 | Yes |
| B | 1: Tariff deep mine | ~$0.04 | Yes |
| B | 2: Email archive mine | ~$0.01 | Yes |
| C | 4: Attachment mine | ~$0.05 | Yes |
| C | 5: AI knowledge fill | ~$0.02 | Yes |
| D | 7: Cross-reference | ~$0.00 | No |
| E | 8: Self-teach | ~$0.02 | Yes |
| F | 9: Knowledge sync | ~$0.00 | No |
| G | 10: Deal enrichment | ~$0.00 | No |
| G2 | 11: Port intelligence sync | ~$0.00 | No |
| H | 12: Regression guard | ~$0.00 | No |

**Crash recovery:** Checkpoint written after every stream (line 1946, 1961, etc.). On retry, completed streams are skipped. Budget restored from checkpoint.

#### Findings

| ID | Severity | Description | Location |
|----|----------|-------------|----------|
| N1-F1 | MEDIUM | Docstring says "9 enrichment streams" but there are 12 | `overnight_brain.py:4` |
| N1-F2 | MEDIUM | `STREAM_PRIORITY` list (line 47-57) only has 9 entries — streams 10, 11, 12 are NOT listed. If the priority list is used for ordering, these streams only run because they're hardcoded in the orchestrator at lines 2068-2103 | `overnight_brain.py:47-57` |
| N1-F3 | LOW | Stream 1 (`stream_1_tariff_deep_mine`) reads ALL 11,753 tariff docs into memory (line 154) — potential memory pressure in 512MB Cloud Function | `overnight_brain.py:154` |
| N1-F4 | LOW | Stream 5 reads ALL `ai_knowledge_enrichments` into memory (line 777) with no `.limit()` — unbounded growth | `overnight_brain.py:777` |
| N1-F5 | LOW | `_final_knowledge_audit` (line 2157) reads up to 10,000 docs per collection × 22 collections = potentially 220K reads — expensive | `overnight_brain.py:2173-2179` |
| N1-F6 | MEDIUM | Stream 12 regression guard reads ALL `learned_classifications` (line 1753-1757) with `.limit(5000)`. If collection grows beyond 5K, older entries silently dropped from regression checking | `overnight_brain.py:1753-1757` |
| N1-F7 | LOW | Stream 12 key lookup: `learned_by_product` uses `product_description` or `description` as key (line 1761), but `learn_classification()` stores the field as `product` and `product_lower` (self_learning.py:477-478). Field name mismatch may cause zero matches | `overnight_brain.py:1761` vs `self_learning.py:477` |

### Nightly Learn (`nightly_learn.py`)

**Entry:** `run_pipeline()` at line 58

**4-step pipeline (all Firestore-only, $0 AI cost):**
1. `enrich_knowledge` — import `enrich_knowledge` script, add extracted fields
2. `knowledge_indexer` — rebuild keyword/product/supplier indexes
3. `deep_learn` — mine all docs, enrich indexes
4. `read_everything` — build master `brain_index` from 27 collections

#### Findings

| ID | Severity | Description | Location |
|----|----------|-------------|----------|
| N2-F1 | HIGH | Steps 1-4 use `import enrich_knowledge as ek_script` style imports. These scripts (`enrich_knowledge.py`, `knowledge_indexer.py`, `deep_learn.py`, `read_everything.py`) must exist in the Python path. If deployed as Cloud Function, the import path may differ from local. Each script also does its own Firebase init which may conflict | `nightly_learn.py:83, 102, 122, 150` |
| N2-F2 | MEDIUM | Step 3 manually resets module-level `mined` dict (line 126-132) — fragile, depends on exact internal structure of `deep_learn.py` module state | `nightly_learn.py:126-132` |
| N2-F3 | LOW | No checkpoint/resume — if Step 2 fails, Steps 3-4 still run (each step is independent), but Step 2's indexes are stale | `nightly_learn.py:58` |
| N2-F4 | INFO | Pipeline results saved to `system_metadata/nightly_learn` — good observability | `nightly_learn.py:183` |

### Overnight Audit (`overnight_audit.py`)

**Entry:** `run_overnight_audit()` at line 30

**9 checks:**
1. Email reprocessing (last 30 days through Pupil + Tracker)
2. Memory hit rate
3. Ghost deals (no containers, no AWB, no storage_id)
4. AWB status
5. Brain index size + 7-day growth
6. Sender analysis
7. Collection counts
8. Self-enrichment (fills knowledge gaps — WRITES if not dry_run)
9. PC Agent Runner (executes pending tasks — WRITES if not dry_run)

#### Findings

| ID | Severity | Description | Location |
|----|----------|-------------|----------|
| N3-F1 | HIGH | Check 1 (`_audit_email_reprocessing`) re-runs Pupil + Tracker on last 30 days of emails (line 170-200). This writes to production Firestore (`learned_*`, `tracker_*` collections). If an email was already processed correctly, re-processing may create duplicate observations or overwrite learned data | `overnight_audit.py:52-60, 170` |
| N3-F2 | MEDIUM | Check 8 (`self_enrichment`) imports from `lib.self_enrichment` (line 123) — this module is listed as dead code in CLAUDE.md ("redundant, Stream 5 + Stream 10 cover its use case"). Its nightly invocation may conflict with overnight_brain's Stream 5 | `overnight_audit.py:123` |
| N3-F3 | LOW | `dry_run=False` is the default (line 30) — operator must explicitly pass `dry_run=True` for safe diagnostic-only mode. Cloud Function invocation in main.py should be checked for what it passes | `overnight_audit.py:30` |

---

## Memory System Audit

### Architecture

The memory system is implemented in `self_learning.py` (`SelfLearningEngine` class, 1,765 lines).

**5-Level Memory Hierarchy:**

| Level | Name | Cost | Source Collections |
|-------|------|------|--------------------|
| 0 | Exact Match | $0.00 | `learned_contacts`, `learned_classifications` (exact product_lower match) |
| 0.5 | Normalized Match | $0.00 | `learned_classifications` (keyword overlap ≥ 60%) |
| 1 | Similar Match | $0.00 | `keyword_index`, `product_index` |
| 2 | Pattern Match | $0.00 | `classification_knowledge` |
| 3 | Partial Knowledge | ~$0.003 | Quick Gemini call |
| 4 | No Knowledge | ~$0.05 | Full AI pipeline (caller handles) |

### `check_classification_memory()` flow (`self_learning.py:317`)

1. Level 0: exact `product_lower` match in `learned_classifications`
2. Level 0.5: keyword overlap ≥ 60% — picks longest keyword, queries `array_contains`, computes Jaccard-like overlap
3. Level 1: keyword match in `keyword_index` — returns first hit with `hs_code`
4. Level 2: keyword match in `classification_knowledge` — returns chapter-level match
5. Returns `(None, "none")` → caller runs full pipeline

### `learn_classification()` flow (`self_learning.py:424`)

1. Read-before-write guard (Session 38 fix):
   - Method ranking: `cross_validated: 3, manual: 2, ai: 1`
   - Skips overwrite if existing has higher confidence from same-or-better method
   - Skips if existing method strictly outranks new method at same-or-higher confidence
2. Normalizes HS code to Israeli format via `get_israeli_hs_format()`
3. `set(merge=True)` — updates existing doc or creates new

### Image Pattern Cache (`self_learning.py:499-597`)

- `check_image_pattern(image_hash)` — single doc read, 180-day TTL
- `save_image_pattern(image_hash, ...)` — read-before-write, never overwrites higher confidence

### Active Enrichment (`self_learning.py:603`)

- `enrich_knowledge()` — 3 strategies: gap filling, cross-validation, corrections research
- Multi-AI: Gemini Flash → Claude → ChatGPT for cross-validation
- Budget-capped per run

#### Findings

| ID | Severity | Description | Location |
|----|----------|-------------|----------|
| M-F1 | HIGH | Level 0.5 keyword overlap uses `array_contains` on a SINGLE keyword (the longest), then computes overlap. If the longest keyword is common (e.g., "steel"), many unrelated products match, and the 60% threshold may produce false positives. The `limit(5)` cap helps but doesn't prevent wrong matches | `self_learning.py:350-377` |
| M-F2 | MEDIUM | Level 1 returns the FIRST `keyword_index` hit with an `hs_code` (line 388-396). Multiple keywords are checked, but the first match wins regardless of relevance. A common keyword like "plastic" could match chapter 39 when the actual product is chapter 85 (plastic components of machines) | `self_learning.py:380-398` |
| M-F3 | MEDIUM | `learn_classification()` doc_id is `_make_id(f"cls_{product_lower}_{hs_code}")`. The same product with a DIFFERENT hs_code creates a SEPARATE doc. Over time, the same product may have multiple learned entries with conflicting codes, all returned by different query paths | `self_learning.py:443` |
| M-F4 | LOW | `_extract_keywords()` is called in multiple places but its implementation is not visible in the read range. If it strips Hebrew prefixes inconsistently, keyword matching fails | `self_learning.py:87-89` |
| M-F5 | INFO | Read-before-write guard in `learn_classification()` (Session 38 fix) is correct and prevents confidence regression — verified | `self_learning.py:445-463` |
| M-F6 | INFO | Image pattern cache with 180-day TTL and confidence guard is well-implemented | `self_learning.py:499-597` |

---

## Identity Graph Audit

### Architecture

Implemented in `identity_graph.py` (973 lines, Session 46). One Firestore doc per deal in `deal_identity_graph` collection.

**15 identifier fields:**
- Array: `bl_numbers`, `booking_refs`, `awb_numbers`, `container_numbers`, `invoice_numbers`, `po_numbers`, `packing_list_refs`, `email_thread_ids`
- Scalar: `client_ref`, `internal_file_ref`, `job_order_number`, `file_number`, `import_number`, `export_number`, `seped_number`

**5 core functions:**
1. `find_deal_by_identifier(db, identifier)` — searches all 15 fields in priority order
2. `register_identifier(db, deal_id, field, value)` — adds identifier with dedup
3. `merge_deals(db, deal_id_a, deal_id_b)` — merges all identifiers
4. `extract_identifiers_from_email(subject, body, attachments_text)` — 17 regex patterns
5. `link_email_to_deal(db, email_data, known_deal_id=None)` — orchestrate: extract → search → register

### Wiring Status

The identity graph IS wired into live code:

| Call Site | File:Line | Status |
|-----------|-----------|--------|
| `link_email_to_deal()` after deal match | `tracker.py:525-536` | **WIRED** (Session 50b) |
| `register_deal_from_tracker()` on deal creation | `tracker.py:1283-1288` | **WIRED** (Session 50b) |
| Email intent → deal lookup | `email_intent.py` | **NOT WIRED** — uses `_find_deal_by_field` directly |
| Classification → outcome tracking | `classification_agents.py` | **NOT WIRED** — no feedback from declarations |
| Overnight brain → pattern learning | `overnight_brain.py` | **NOT WIRED** — `learned_identifier_patterns` collection exists but no stream populates it |

### Indirect Feedback Loop (Design Notes in identity_graph.py:19-47)

The design notes describe a feedback loop:
```
classification → declaration → outcome → memory update → better future classifications
```
This is **NOT YET IMPLEMENTED**. The identity graph can link identifiers to deals, but:
- No code reads `[DECL]` email outcomes and matches them back to classifications
- `on_classification_correction()` in main.py handles manual corrections but not declaration-based corrections
- The `learned_identifier_patterns` collection is empty

#### Findings

| ID | Severity | Description | Location |
|----|----------|-------------|----------|
| IG-F1 | HIGH | Identity graph is wired for REGISTRATION (tracker creates/links identifiers) but NOT for RETRIEVAL in email_intent.py — status lookups still use `_find_deal_by_field` which only searches `tracker_deals`, not the identity graph's broader identifier set | `email_intent.py:778-793` vs `identity_graph.py:254` |
| IG-F2 | HIGH | Indirect feedback loop (declaration outcomes → classification memory) is designed but completely unimplemented. `[DECL]` emails are stored in `declarations_raw` (main.py:840) but never parsed or matched back to deals/classifications | `main.py:813-851`, `identity_graph.py:19-47` |
| IG-F3 | MEDIUM | `find_deal_by_identifier()` queries each of 15 fields sequentially (line 254+). For each field, it does a separate Firestore query. A single lookup can cost up to 15 Firestore reads. No short-circuit optimization beyond priority ordering | `identity_graph.py:254+` |
| IG-F4 | MEDIUM | `learned_identifier_patterns` collection registered in librarian_index but NEVER populated — overnight brain Stream 10-12 don't touch it, no other code writes to it | `identity_graph.py:92-100` |
| IG-F5 | LOW | `merge_deals()` marks secondary deal as `merged_into` but does NOT update `tracker_container_status` docs — container status records for the secondary deal remain orphaned | `identity_graph.py:490` |

---

## Findings Summary

### CRITICAL (3)

| ID | Description | Location | Impact |
|----|-------------|----------|--------|
| **S1-F1 / S3-F1** | CC path Block A1 sends classification report to external sender — `from_email` passed as `to_email` to `process_and_send_report()` | `main.py:936` | Classification reports with internal HS code analysis sent to external shippers/factories |
| **S3-F2** | `process_and_send_report()` has zero domain checking on `to_email` — only checks for None/empty | `classification_agents.py:2969` | No safety net — any truthy email address gets the report |
| **S3-F3 / S1-F2** | Gap 2 auto-trigger falls back to external `from_email` when `follower_email` is not set on deal | `main.py:963` | Same external-send risk via different code path |

### HIGH (5)

| ID | Description | Location |
|----|-------------|----------|
| **S5-F1** | 15-product invoices likely exceed tool-calling round/time limits (15 rounds × 180s budget), producing partial or zero results | `tool_calling_engine.py` |
| **N2-F1** | Nightly learn imports standalone scripts that do their own Firebase init — may fail in Cloud Function deployment context | `nightly_learn.py:83, 102, 122, 150` |
| **N3-F1** | Overnight audit re-processes 30 days of emails through Pupil + Tracker in WRITE mode — may create duplicate observations | `overnight_audit.py:52-60` |
| **M-F1** | Memory Level 0.5 keyword overlap uses single-keyword query + 60% threshold — false positive risk for common terms | `self_learning.py:350-377` |
| **IG-F1** | Identity graph wired for writes but NOT reads — email_intent status lookups bypass the graph entirely | `email_intent.py:778` |
| **IG-F2** | Declaration feedback loop designed but unimplemented — `[DECL]` emails stored but never matched to classifications | `main.py:813-851` |

### MEDIUM (9)

| ID | Description | Location |
|----|-------------|----------|
| S1-F3 | No admin notification for suppressed CC classifications (no team address in chain) | `main.py:935-941` |
| S2-F1 | Hebrew "סטטוס" not in STATUS_PATTERNS — works only via `?` fallback | `email_intent.py:76-80` |
| S2-F2 | Status lookup only searches active/pending deals — completed deals invisible | `tracker.py:1083-1086` |
| S5-F2 | No item-level chunking — all items truncated on max rounds, not batched | `tool_calling_engine.py` |
| N1-F1 | Docstring says "9 streams" but there are 12 | `overnight_brain.py:4` |
| N1-F2 | STREAM_PRIORITY list missing streams 10-12 | `overnight_brain.py:47-57` |
| N1-F6 | Regression guard caps at 5K learned_classifications — silent miss beyond that | `overnight_brain.py:1753` |
| N1-F7 | Stream 12 uses field name `product_description`/`description` but learn_classification stores as `product`/`product_lower` — potential zero matches | `overnight_brain.py:1761` |
| M-F2 | Memory Level 1 returns first keyword_index hit regardless of relevance | `self_learning.py:380-398` |
| M-F3 | Same product with different HS codes creates separate learned_classifications docs — conflicting memory entries | `self_learning.py:443` |
| N2-F2 | Nightly learn manually resets deep_learn module state — fragile coupling | `nightly_learn.py:126-132` |
| N3-F2 | Overnight audit invokes potentially-dead `self_enrichment` module | `overnight_audit.py:123` |
| IG-F3 | Identity graph lookup does up to 15 sequential Firestore queries per call | `identity_graph.py:254+` |
| IG-F4 | `learned_identifier_patterns` collection exists but is never populated | `identity_graph.py:92-100` |

### LOW (6)

| ID | Description | Location |
|----|-------------|----------|
| S1-F4 | `email_quality_gate` does not check recipient domain | `rcb_helpers.py:705` |
| S4-F1 | Suppressed classifications silently stored with no notification | `classification_agents.py:2969` |
| S5-F3 | Pre-enrichment triggers fire per-invoice not per-item | `tool_calling_engine.py` |
| N1-F3 | Stream 1 loads all 11,753 tariff docs into memory | `overnight_brain.py:154` |
| N1-F4 | Stream 5 reads all ai_knowledge_enrichments with no limit | `overnight_brain.py:777` |
| N1-F5 | Final audit reads up to 220K docs for collection counts | `overnight_brain.py:2173` |
| IG-F5 | Deal merge doesn't update container status records | `identity_graph.py:490` |

### INFO (3)

| ID | Description | Location |
|----|-------------|----------|
| S4-F2 | Direct path domain check is correct — should be replicated in CC path | `main.py:997-1011` |
| M-F5 | Learn_classification read-before-write guard is correct | `self_learning.py:445-463` |
| M-F6 | Image pattern cache well-implemented | `self_learning.py:499-597` |

---

## Dead Code

| File | Lines | Status |
|------|-------|--------|
| `functions/lib/rcb_email_processor.py` | 415 | Legacy IMAP/Gmail processor from Session 13 — never imported by main.py |
| `functions/lib/rcb_orchestrator.py` | 409 | Legacy Module 6 orchestrator — never imported by main.py |
| `lib.self_enrichment` (referenced in overnight_audit.py:123) | Unknown | Listed as "redundant" in CLAUDE.md Session 44-PARALLEL |

**Total dead code:** ~824+ lines across 2 confirmed files + 1 potentially-dead module

---

## Test Coverage Gaps

Based on the 965+ tests (as of Session 50d):

| Area | Tests | Coverage Gap |
|------|-------|-------------|
| CC classification path (Block A1) | **0 tests** | No test verifies what `to_email` is passed to `process_and_send_report()` from CC path |
| Gap 2 auto-trigger | **0 tests** | No test verifies `_to` address in auto-trigger path |
| Email quality gate recipient domain | **0 tests** | Tests cover body/subject/dedup but not recipient validation |
| Nightly pipeline import chain | **0 tests** | No integration test verifies that `nightly_learn.py` imports work in Cloud Function context |
| Regression guard field matching | **0 tests** | Stream 12's product field name assumption untested |
| Identity graph retrieval in email_intent | **0 tests** | No test exercises identity graph lookup during status requests |
| 15+ item classification | **0 tests** | No test verifies behavior when items exceed tool round limits |
| Declaration feedback loop | **0 tests** | No test for declaration parsing or outcome matching |

---

## Priority Fix Order

1. **S1-F1 / S3-F1 / S3-F2** (CRITICAL) — CC path external sender bug. 5-line fix in `main.py:935` replicating the direct path's domain-check pattern from `main.py:1001-1007`. Plus add domain check in Gap 2 at `main.py:963`.
2. **S3-F3 / S1-F2** (CRITICAL) — Gap 2 `_to` fallback. Replace `from_email` fallback with `None` after checking deal's `follower_email` is @rpa-port.co.il.
3. **S5-F1** (HIGH) — Item chunking for large invoices. Split 15-item invoices into batches of 5 before entering tool-calling loop.
4. **IG-F1** (HIGH) — Wire `find_deal_by_identifier()` into `_handle_status_request()` as fallback after `_find_deal_by_field()`.
5. **N1-F7** (MEDIUM) — Fix field name mismatch in regression guard (`product_description` → `product` or `product_lower`).
6. **S2-F1** (MEDIUM) — Add "סטטוס" to STATUS_PATTERNS regex.
7. **S2-F2** (MEDIUM) — Add "completed" to status filter in `_find_deal_by_field()` for status lookups.

---

*End of FLOW_AUDIT_SESSION_A report.*
