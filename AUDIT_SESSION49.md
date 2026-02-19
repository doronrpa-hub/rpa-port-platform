# RPA-PORT-PLATFORM — Full System Audit Report
## Session 49 — 2026-02-19 (Read-Only Audit from Home PC)

**Audit scope:** Every `.py` file in `functions/lib/`, `functions/main.py`, `functions/tests/`, config files.
**Method:** 7 parallel audit agents reading the full codebase (~45,000 lines of Python).
**Result:** No code was changed. This report is for the office session to prioritize fixes.

---

## TEST SUITE STATUS

```
975 collected, 968 passed, 5 failed, 2 skipped
```

**5 failures** — all pre-existing BS4 `html.parser` issues (not stripping `<script>` tags):
- `test_html_extraction` (test_data_pipeline.py)
- `test_html_table_extraction` (test_data_pipeline.py)
- `test_html_scripts_removed` (test_smart_extractor.py)
- `test_bs4_tables` (test_table_extractor.py)
- `test_bs4_multiple_tables` (test_table_extractor.py)

**Fix:** Add explicit `<script>`/`<style>` tag removal before `html.parser`, or switch to `lxml`.

---

## CRITICAL BUGS (Fix First — 5 issues)

### C1. Sanctions alert email function name wrong
**File:** `main.py:622`
```python
from lib.rcb_helpers import helper_graph_send_email  # DOES NOT EXIST
```
The actual function is `helper_graph_send`. The `ImportError` is caught by `try/except` at line 621, so **sanctions alert emails to doron@rpa-port.co.il are NEVER sent**. Sanctions hits are logged to `security_log` but the human is never notified.

**Impact:** HIGH — compliance gap. Sanctioned parties could be processed without alert.
**Fix:** Change `helper_graph_send_email` to `helper_graph_send` and match the call signature.

### C2. OpenSanctions duplicate `schema` param drops Company search
**File:** `tool_executors.py:2207`
```python
params={"schema": "Company", "schema": "Person"},  # Python dict: only "Person" survives
```
Sanctions screening only searches for **persons**, never companies. A sanctioned company name would be missed.

**Impact:** HIGH — compliance gap.
**Fix:** Use `params=[("schema", "Company"), ("schema", "Person")]` or make two separate API calls.

### C3. Email intent status reply shows wrong field names
**File:** `email_intent.py:834-842`
- Uses `container_number` but tracker stores `container_id` → container always shows "?"
- Uses snake_case step keys (`cargo_exit_date`) but TaskYam data is PascalCase (`CargoExitDate`) → status steps always empty, shows "ממתין"

**Impact:** MEDIUM — status replies to team are useless (all show "?" and "waiting").
**Fix:** Change `container_number` → `container_id`, step keys to PascalCase.

### C4. `deal_thread_id` stable threading is NOT implemented
**File:** `tracker.py:2300-2315`
Session 41 documented stable threading via `deal_thread_id` field, and `_create_deal()` at line 1206 creates the field. But `_send_tracker_email()` at lines 2300-2308 still looks up the latest observation's `msg_id` and uses `helper_graph_reply`. The `deal_thread_id` is **created but never read or used**.

**Impact:** MEDIUM — tracker emails still not properly threaded in Outlook.
**Fix:** Use `deal_thread_id` as In-Reply-To header, fall back to helper_graph_send with clean subject.

### C5. `overnight_audit.py` claims READ-ONLY but writes to Firestore
**File:** `overnight_audit.py` checks 1, 8, 9
Docstring says "READ-ONLY: Does NOT send emails, does NOT modify existing data." But:
- Check 1 calls `pupil_process_email()` and `tracker_process_email()` on real emails → writes observations + deal updates
- Check 8 calls `run_nightly_enrichment()` → writes to Firestore
- Check 9 calls `run_pending_tasks()` → executes tasks with side effects

**Impact:** HIGH — production data modified by what's documented as a read-only audit.
**Fix:** Either make truly read-only (dry-run flag), or update docstring and add safeguards.

---

## HIGH SEVERITY BUGS (Fix Soon — 12 issues)

### H1. Infinite retry loop for permanently-failing emails
**File:** `main.py:1441-1447`
`rcb_retry_failed` (every 6 hours) deletes `rcb_processed` entries for emails without classification results. If an email genuinely cannot be classified (corrupt PDF, no attachments), it loops forever: process → fail → retry deletes dedup → process again. No retry count or circuit breaker.

**Fix:** Add `retry_count` field to `rcb_processed`, stop retrying after 3 attempts.

### H2. Three DISABLED functions still deployed and billing
**File:** `main.py:1573-1597`
- `monitor_self_heal` — 1GB, HTTP, disabled stub
- `monitor_fix_all` — 1GB, HTTP, disabled stub
- `monitor_fix_scheduled` — **1GB, every 5 minutes**, disabled stub → 288 invocations/day doing nothing

**Fix:** Delete these functions entirely.

### H3. Missing composite Firestore indexes
**File:** `firestore.indexes.json`
At least 10 multi-field queries need composite indexes but only 8 are defined. Key missing:
- `tracker_deals`: `bol_number` + `status` (in)
- `tracker_deals`: `awb_number` + `status` (in)
- `tracker_deals`: `source_email_thread_id` + `status` (in)
- `tracker_deals`: `containers` (array_contains) + `status` (in)
- `questions_log`: `from_email` + `created_at` (>=)

These will throw `FailedPrecondition` errors the first time they run. Rate limiting in email_intent silently fails without the questions_log index.

**Fix:** Add all required composite indexes to `firestore.indexes.json`.

### H4. `api()` stats endpoint reads entire collections into memory
**File:** `main.py:357-364`
```python
"knowledge_count": len(list(get_db().collection("knowledge_base").stream())),
```
Streams every document in 7 collections just to count them. Could OOM on large collections.

**Fix:** Use Firestore aggregation `count()` queries.

### H5. Identity graph NOT wired into live pipeline
**File:** `identity_graph.py` (500 lines, built Session 46)
`link_email_to_deal()` is never called from `main.py`, `tracker.py`, or `classification_agents.py`. The unified identifier linking for accurate self-learning and outcome tracking is completely inactive.

**Fix:** Wire `link_email_to_deal()` into `tracker_process_email()` and `register_deal_from_tracker()`.

### H6. Image pattern cache NOT wired into extraction flow
**File:** `extraction_adapter.py` / `self_learning.py`
`check_image_pattern()` and `save_image_pattern()` exist in self_learning.py but extraction_adapter.py never calls them. Every image is re-analyzed by both AI models ($0.015-0.035) even if the same image was seen before.

**Fix:** Check cache before `analyze_image()`, save after.

### H7. Bare `except:` (catches SystemExit) in 3 locations
- `tracker.py:1674` — `TaskYamClient.logout()`
- `tracker.py:2161` — `_decode_header()`
- `identity_graph.py:880` — `_add_email_subject()`

**Fix:** Change to `except Exception:` with logging.

### H8. Stream 12 regression guard reads with limit(100) and no date filter
**File:** `overnight_brain.py:1741`
`rcb_classifications` is read with `limit(100)` but no date filter. It reads the 100 most recent by doc ID, not by date. May miss today's classifications entirely.

**Fix:** Add `.where("created_at", ">=", today_start)` before `.limit(100)`.

### H9. Missing `storage.rules` file breaks full deploy
**File:** `firebase.json` references `"rules": "storage.rules"` but the file doesn't exist.
`firebase deploy` (all targets) will fail. Functions-only deploy works fine.

**Fix:** Create a minimal `storage.rules` file, or remove storage target from `firebase.json`.

### H10. Rule 7 HS regex too broad in email quality gate
**File:** `rcb_helpers.py:951-952`
Rule 7 uses `\d{2}\.\d{2}` to detect HS codes, but this matches dates (02.18), prices (12.50), etc.

**Fix:** Use `\d{4}\.\d{2}` (4-digit heading + 2-digit subheading) for proper HS code detection.

### H11. Geocoding has no fallback — single point of failure
**File:** `route_eta.py`
Only Nominatim is used for geocoding. If Nominatim is down, all route ETA calculations fail (returns None). ORS and OSRM are routing engines only.

**Fix:** Add fallback geocoder (e.g., Photon, which is free and based on OSM data like Nominatim).

### H12. `_aggregate_deal_text` N+1 Firestore reads
**File:** `main.py:542-555`
Reads tracker_observations one-by-one per obs_id. 10 observations = 10 sequential reads.

**Fix:** Use batch `getAll()` or `where("__name__", "in", obs_ids)`.

---

## MEDIUM SEVERITY (18 issues)

| # | File:Line | Issue |
|---|-----------|-------|
| M1 | `main.py:730` | 2-min schedule + 9-min timeout → overlapping invocations, TOCTOU race on rcb_processed |
| M2 | `main.py:1525` | `'error_count' in dir()` should be `'error_count' in locals()` |
| M3 | `main.py:454` | `rcb_api` path parsing breaks backup-by-ID route (split("/")[-1] loses prefix) |
| M4 | `tracker.py:1468-1476` | TOCTOU race on `classification_auto_triggered_at` (non-atomic check+write) |
| M5 | `tracker.py:2319` | Fallback `helper_graph_send` missing quality gate params (deal_id, alert_type) |
| M6 | `tracker_email.py:24-30` | Color constants exported with underscore prefix (fragile cross-file import) |
| M7 | `email_intent.py:460-466` | Rate limit query needs composite index or silently fails (fail-open) |
| M8 | `email_intent.py:155` | ADMIN_EMAIL hardcoded as `doron@rpa-port.co.il` |
| M9 | `rcb_helpers.py:730` | `Re:` prefix added when `reply_to_id` set but no actual threading occurs |
| M10 | `tool_executors.py:2347-2354` | `fetch_seller_website` bypasses `_safe_get()` domain allowlist |
| M11 | `overnight_brain.py:1886` | Budget recovery dumps all prior spending into `ai_cost` (inaccurate breakdown) |
| M12 | `nightly_learn.py:183` | Overwrites pipeline metadata each run — no run history preserved |
| M13 | `ttl_cleanup.py:87` | Docs with unrecognized IDs and no timestamp deleted by default |
| M14 | `ttl_cleanup.py:99` | `cleanup_collection_by_field()` streams entire collection without pagination |
| M15 | `schedule_il_ports.py` | Stores vessel names in original case but dedup keys are uppercase — potential mismatch |
| M16 | `route_eta.py` | Missing coordinates for ILKRN (Haifa Bay) and ILASH (Ashdod South) ports |
| M17 | `extraction_adapter.py:311-331` | `fitz.Document` not closed in exception path (resource leak) |
| M18 | `verification_engine.py` | Module-level cache for directives/framework — stale during warm instances |

---

## LOW SEVERITY (22 issues)

| # | File:Line | Issue |
|---|-----------|-------|
| L1 | `main.py:760` | `datetime.utcnow()` deprecated in Python 3.12+ |
| L2 | `main.py:235,240,258` | `datetime.now()` without timezone (should be Israel time per rules) |
| L3 | `main.py:434,446,1539` | Three dead functions (graph_forward_email, get_anthropic_key, _send_alert_email) |
| L4 | `main.py:1282-1285` | `monitor_agent_manual` HTTP endpoint does nothing |
| L5 | `main.py:600-601` | Unnecessary `__import__("datetime")` when datetime already imported |
| L6 | `main.py:1197-1202` | Duplicate "MONITOR AGENT" comment block |
| L7 | `main.py:28` | `auto_learn_email_style` imported but never used |
| L8 | `main.py:44` | `link_deal_to_schedule` imported but never called |
| L9 | `classification_agents.py` | Dead `_call_claude_check()` in cross_checker.py:168-180 (never called) |
| L10 | `tool_executors.py:226,252-254` | 4 dead dispatcher stubs not in CLAUDE_TOOLS |
| L11 | `tool_executors.py:1539` | Comtrade TTL: CLAUDE.md says 7 days, code uses 30 |
| L12 | `tool_executors.py:2349` | `fetch_seller_website` User-Agent reveals system identity |
| L13 | `tool_calling_engine.py:542-544` | Stale docstring says "Max 8 rounds / 120s" but values are 15/180s |
| L14 | `overnight_brain.py:4,1870` | Docstrings say "9 streams" but 12 exist |
| L15 | `overnight_brain.py:47` | `STREAM_PRIORITY` list defined but never used by orchestrator |
| L16 | `email_intent.py:614` | Pending clarification key per-sender, not per-conversation |
| L17 | `image_analyzer.py:287-288` | Dead confidence branch — both elif and else set "MEDIUM" |
| L18 | `smart_extractor.py:505-542` | Dead `try_ai_document_reading()` stub — always returns None |
| L19 | `doc_reader.py:361` | Bare `except:` (should be `except Exception:`) |
| L20 | `extraction_validator.py:135` | Reversed Hebrew indicator `הביי` may be wrong (should be `אביי`) |
| L21 | `document_parser.py` | Duplicate doc type detection — 17 types in doc_reader + 11 in document_parser |
| L22 | `overnight_brain.py:1843` | Checkpoint key uses UTC date — if brain spans UTC midnight, key changes |

---

## COLLECTION_FIELDS AUDIT

### Actual count: 80 collections registered (CLAUDE.md says 70 — stale)

### 12 Critical collections used in live code but NOT registered:
| Collection | Used In |
|-----------|---------|
| `learned_classifications` | self_learning.py, overnight_brain.py |
| `learned_patterns` | self_learning.py, overnight_brain.py |
| `learned_corrections` | self_learning.py, overnight_brain.py |
| `learned_doc_templates` | doc_reader.py, brain_commander.py |
| `tracker_observations` | main.py, self_learning.py |
| `security_log` | main.py |
| `brain_index` | self_learning.py |
| `regulatory_requirements` | intelligence.py |
| `free_import_cache` | intelligence.py |
| `knowledge_gaps` | justification_engine.py, overnight_brain.py |
| `classification_reports` | classification_agents.py |
| `tracker_awb_status` | air_cargo_tracker.py |

### 13 Phantom collections (registered but never used in code):
`regulatory_approvals`, `regulatory_certificates`, `legal_references`, `licensing_knowledge`, `customs_decisions`, `court_precedents`, `customs_ordinance`, `customs_procedures`, `tariff_usa`, `tariff_eu`, `cbp_rulings`, `bti_decisions`, `pre_rulings`

---

## UNTESTED MODULES (Highest Risk)

39 source modules have zero dedicated test files. The highest-risk untested:

| Module | Lines | Risk |
|--------|------:|------|
| `main.py` | 2,352 | CRITICAL — 31 Cloud Functions, core orchestration |
| `pupil.py` | 2,740 | HIGH — learning engine |
| `tracker.py` | 2,609 | HIGH — shipping tracker |
| `tool_executors.py` | 2,411 | HIGH — 33 tool handlers |
| `elimination_engine.py` | 2,413 | HIGH — tariff tree walker |
| `self_learning.py` | 1,732 | HIGH — memory + image cache |
| `intelligence.py` | 1,910 | HIGH — tariff search + regulatory |
| `ocean_tracker.py` | 1,606 | HIGH — 7 carrier APIs |

---

## DEPLOYMENT & CONFIG ISSUES

| Issue | Severity |
|-------|----------|
| Missing `storage.rules` file (firebase.json references it) | HIGH — breaks full deploy |
| Missing `web-app/public/` directory (hosting target) | MEDIUM — breaks hosting deploy |
| No `.firebaserc` — project not persisted | LOW |
| `google-cloud-storage` not explicit in requirements.txt | MEDIUM — works via firebase-admin transitive |
| `pytest` in production requirements (should be dev-only) | LOW |
| Stale backup file: `classification_agents.py.backup_session22` | LOW — delete it |
| `.claude/` directory should be in `.gitignore` | LOW |

---

## CLOUD FUNCTIONS INVENTORY (31 total)

### Schedule Conflicts
Three functions all run at `every day 02:00` Asia/Jerusalem:
- `rcb_nightly_learn` (1GB, 540s)
- `rcb_overnight_audit` (2GB, 900s)
- `rcb_daily_backup` (1GB, 540s)
They run concurrently — not a bug but a resource concern.

### Wasted Resources
- `monitor_fix_scheduled`: every 5 min, 1GB, does NOTHING → 288 invocations/day
- `monitor_self_heal`: 1GB HTTP, disabled
- `monitor_fix_all`: 1GB HTTP, disabled

---

## WHAT'S WORKING WELL

1. **Classification pipeline** — 33 tools, Gemini-first with Claude fallback, forced final answer
2. **Elimination engine** — 8 levels, all with last-survivor guards, proper AI fallback
3. **Email quality gate** — 7 rejection rules, fail-open, Firestore dedup
4. **Cost optimization** — Gemini Flash primary ($0.15/MTok vs Claude $3/MTok), ~$350/month savings
5. **Budget cap** — $3.50 limit with $0.20 safety margin, enforced per-stream
6. **Tracker Phase 1 (TaskYam)** — authoritative port data, proper 2-phase poll
7. **Self-email skip** — feedback loop prevention working correctly
8. **Sender routing** — external senders never get replies, proper team routing
9. **N+1 query fixes** — batch queries properly implemented at 3 sites in tracker.py
10. **Hebrew exclusion regex** — properly matches פרק/בפרק/לפרק
11. **Read-before-write guard** — classification memory protected from regression
12. **Port intelligence** — I1-I4 complete, 4 alert types, morning/afternoon digest
13. **Verification engine** — Phase 4+5 bilingual, 7 flag types, proper confidence adjustment
14. **Overnight brain** — 12 streams with checkpointing, budget-capped, crash recovery

---

## PRIORITY FIX ORDER FOR OFFICE SESSION

### Round 1 — Compliance & Security (30 min)
- [ ] C1: Fix sanctions email function name (`helper_graph_send_email` → `helper_graph_send`)
- [ ] C2: Fix OpenSanctions duplicate schema param
- [ ] H7: Fix 3 bare `except:` clauses

### Round 2 — Broken Features (45 min)
- [ ] C3: Fix email_intent status reply field names
- [ ] C4: Implement deal_thread_id stable threading
- [ ] H10: Fix Rule 7 HS regex in quality gate

### Round 3 — Data Integrity (30 min)
- [ ] H3: Add missing Firestore composite indexes
- [ ] H8: Add date filter to regression guard stream 12
- [ ] H1: Add retry count to rcb_retry_failed

### Round 4 — Performance & Cleanup (30 min)
- [ ] H2: Delete 3 disabled monitor functions
- [ ] H4: Replace collection stream counts with aggregation queries
- [ ] H12: Batch read in _aggregate_deal_text

### Round 5 — Wiring Gaps (60 min)
- [ ] H5: Wire identity graph into tracker pipeline
- [ ] H6: Wire image pattern cache into extraction flow

### Round 6 — Infrastructure (20 min)
- [ ] H9: Create storage.rules or remove from firebase.json
- [ ] Add 12 critical missing collections to COLLECTION_FIELDS
- [ ] Delete backup_session22 file
- [ ] Add .claude/ to .gitignore

---

*Generated by Claude Code Session 49 — Full System Audit (Read-Only)*
*Date: 2026-02-19*
*Commit: pushed to main for office session reference*
