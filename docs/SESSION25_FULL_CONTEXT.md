# SESSION 25 — FULL AUDIT & BL INVESTIGATION
## Date: February 16, 2026 (Saturday evening, home)
## Claude: Opus 4.6
## Commits: NONE (research/audit only, no code changes)

---

## RULE: TRUST NOTHING. VERIFY EVERYTHING.

---

## 1. SYSTEM STATUS CHECK (18:47 UTC)

All functions deployed and running on `rpa-port-customs`:

| Function | Last Run | Status |
|----------|----------|--------|
| `rcb_check_email` | 16:47 UTC | OK — processed emails, completed |
| `rcb_tracker_poll` | 16:48 UTC | OK — 64 deals, 97 containers, 0 updated |
| Air cargo (inside tracker_poll) | 16:48 UTC | FAIL — Maman secrets not configured |

**28 functions deployed total.** 15 scheduled, 8 HTTP, 2 Firestore triggers, 5 disabled stubs.

### Maman Air Cargo — NOT WORKING
```
Secret maman_username error: 404 Secret not found or has no versions
Secret maman_password error: 404 Secret not found or has no versions
```
Need to call Maman at 03-9715388, register, then store credentials in Secret Manager.

---

## 2. FULL CODE AUDIT — 22 ISSUES FOUND

### CRITICAL (will cause runtime failures)

**Bug 1: Circular import silently disables tool-calling engine**
- File: `functions/lib/tool_executors.py:17`
- `from lib.classification_agents import run_document_agent` at module level
- Creates circular dependency: main → classification_agents → tool_calling_engine → tool_executors → classification_agents (partial)
- The `try/except ImportError` in classification_agents.py:114 catches this and sets `TOOL_CALLING_AVAILABLE = False`
- **The entire tool-calling engine (Session 22's major feature) is DEAD in production**
- System always falls back to old 6-agent pipeline
- NOTE: Session 24 fixed circular imports IN tool_calling_engine.py (lazy imports at line 86) but did NOT fix tool_executors.py line 17
- Fix: Move import inside `_extract_invoice()` method

**Bug 2: `build_tracker_status_email` signature mismatch — all tracker emails crash**
- File: `functions/lib/tracker.py:1451` calls with `observation=observation, extractions=extractions`
- File: `functions/lib/tracker_email.py:10` only accepts `(deal, container_statuses, update_type)`
- Every call raises `TypeError: got unexpected keyword argument 'observation'`
- Falls into except block silently. **No tracker emails are being sent.**

**Bug 3: `brain_commander.py` — `from lib.ai_intelligence import ask_claude` — module doesn't exist**
- File: `functions/lib/brain_commander.py:351,460`
- `ai_intelligence.py` does not exist anywhere in the project
- The Claude agent path in `_exec_learning_mission` and `_exec_agent_task` silently fails every time
- The brain's "father" can never use Claude for learning missions

**Bug 4: AWB extraction completely missing from `_extract_logistics_data`**
- File: `functions/lib/tracker.py`
- PATTERNS dict defines AWB regex at line 69: `'awb': r'\b(\d{3})[\s\-]?(\d{8})\b'`
- `result['awbs']` initialized as `[]` at line 330
- **But NO code anywhere in the function populates it**
- AWBs only enter deals via LLM enrichment (unreliable)
- `register_awb()` almost never called → Maman polling pipeline disconnected from email ingestion

**Bug 5: Orphan `@https_fn.on_request` decorator in main.py**
- File: `functions/main.py:934`
- Decorator separated from function by comment block
- Accidentally decorates `graph_forward_email` (helper with wrong signature)

---

### HIGH SEVERITY (incorrect behavior)

**Bug 6: Confidence format mismatch — tool-calling engine vs downstream**
- `tool_definitions.py:235` tells AI: `"confidence": 0.0-1.0` (numeric)
- `classification_agents.py:1129` expects Hebrew: `"גבוהה"`, `"בינונית"`, `"נמוכה"`
- All AI-classified items default to medium confidence (50) regardless of actual confidence

**Bug 7: `CLASSIFICATION_INTENT_KEYWORDS` too broad**
- `knowledge_query.py:138-150` includes "יבוא", "יצוא", "מכס", "שחרור"
- Nearly every customs question triggers classification routing
- Knowledge query handler effectively unreachable for most real queries

**Bug 8: `run_synthesis_agent` uses wrong model tier**
- `classification_agents.py:603` — uses `tier="fast"` (Gemini Flash)
- Docstring and comments say Gemini Pro. Should be `tier="pro"`

**Bug 9: Schedule conflict — two heavy jobs at 02:00**
- `rcb_nightly_learn` AND `rcb_overnight_audit` both at `every day 02:00` Jerusalem
- Fire simultaneously, competing for resources

**Bug 10: Overnight audit violates "READ-ONLY" promise**
- `overnight_audit.py` calls `pupil_process_email` and `tracker_process_email`
- These write to Firestore (observations, deals)
- No dry-run flag. Can create duplicate observations or mutate deal state.

---

### MEDIUM SEVERITY

**Bug 11: Hebrew status normalization shadowed**
- `air_cargo_tracker.py:342` — `_STATUS_MAP` substring matching
- `"שוחרר"` matches before `"שוחרר מהמכס"`, returning less specific status

**Bug 12: Double `fix_all()` on synthesis text**
- `classification_agents.py:1015` and `:1305` — language correction applied twice

**Bug 13: `text_parts` reset discards intermediate AI text**
- `tool_calling_engine.py:372` — resets every loop iteration

**Bug 14: Air cargo alerts detected but never delivered**
- `air_cargo_tracker.py` — alerts only `print()`-ed, no email/webhook

**Bug 15: `tracker_email.py` has zero air cargo awareness**
- Air freight deals produce sea-centric emails with empty progress bars

---

### LOW SEVERITY / CODE QUALITY

**Bug 16:** `overnight_audit.py:392` — No-op `replace("brain_", "brain_")`, `brain_index_size` always 0
**Bug 17:** `classification_agents.py:2052` — Clarification footer searches wrong HTML marker, always -1
**Bug 18:** `query_tariff()` reads only 100 docs with no ordering — misses most tariff DB (11,753 docs)
**Bug 19:** `classification_agents.py:603` — `extract_tracking_from_subject()` defined, never called
**Bug 20:** Phantom Firestore collections `learned_shipping_senders` and `learned_shipping_patterns` — queried but never written
**Bug 21:** `pc_agent.py:403` — Self-import with hardcoded credential path
**Bug 22:** `rcb_diagnostic.py` — Hardcoded Azure AD client/tenant IDs

---

### DEAD CODE INVENTORY

- ~840 lines dead IMAP code in main.py (lines 90-927)
- 5 disabled Cloud Functions still deployed
- 14 backup files (`.backup_session6`, `.backup_session14`, `.bak`, etc.)
- ~25 one-off fix/patch scripts in functions/ root
- Unused imports across 5+ files (credentials, imaplib, email, run_full_classification, auto_learn_email_style, to_hebrew_name, build_rcb_reply, search_all_knowledge, process_and_respond, logging/logger, etc.)
- Dead functions: `_decode_header()`, `MamanClient.get_storage_list()`, `get_calculated_fees()`, `graph_forward_email()`, `get_anthropic_key()`, `_send_alert_email()`, `monitor_agent_manual` (stub)

---

## 3. BL (BILL OF LADING) COMPLETE AUDIT

### 3.1 BL Code Map — 17 Files Touch BLs

**Extraction Layer:**
| File | What it does |
|------|-------------|
| `rcb_helpers.py:92-95` | Tags `[BL_NUMBER: xxx]` via regex during preprocessing |
| `document_parser.py:573-636` | Primary BL field extractor — bl_number, shipper, consignee, vessel, POL, POD, containers, voyage |
| `tracker.py:49-53` | 3 BOL patterns: generic, MSC (`MEDURS`), Maersk (numeric 9-10 digits) |
| `doc_reader.py:137-452` | Template-based extraction — learns per-shipping-line BL layouts |
| `classification_agents.py:451-468` | Agent 1 (Gemini Flash) extracts bl_number, vessel, ports |
| `pupil.py:322-325` | Attachment type guess from filename |

**Document Detection:**
| File | Method |
|------|--------|
| `main.py:762-764` | Filename keywords: `b/l`, `bl_`, `bill_of_lading` |
| `main.py:1211-1215` | Shipping-only routing keywords |
| `document_parser.py:69-92` | Weighted regex scoring (strong/medium/weak signals) |
| `doc_reader.py:137-141` | English + Hebrew keyword scoring |

**Business Logic:**
| File | Role |
|------|------|
| `document_tracker.py` | BL = phase gate for `SHIPMENT_LOADED`; blocks `can_declare` |
| `intelligence.py:466-468` | BL is 1 of 3 required doc types |
| `clarification_generator.py` | Generates Hebrew requests for missing BLs |
| `smart_questions.py:340-350` | Asks for missing transport doc |
| `tracker_email.py` | Displays BOL in subject + body |
| `self_learning.py` | Tracks shipping_lines per contact |

### 3.2 Shipping Line Recognition

**Carrier regex (tracker.py:59) — 13 carriers:**
```
ZIM, MAERSK, MSC, CMA CGM, HAPAG, EVERGREEN, COSCO, ONE, HMM, YANG MING, PIL, TURKON, OOCL
```

**Email domains (tracker.py:88-96) — 9 carriers:**
```
zim.com, maersk.com, msc.com, cma-cgm.com, hapag-lloyd.com,
evergreen-line.com, cosco.com, one-line.com, hmm21.com
```

**BL-specific patterns:**
| Pattern | Carrier | Status |
|---------|---------|--------|
| `MEDURS\d{5,10}` | MSC | ACTIVE — used in extraction loop |
| `\d{9,10}` | Maersk | **DEFINED BUT NOT USED** — excluded from loop at lines 347-352 |
| Generic `B/L...[A-Z0-9][\w-]{6,25}` | All others | ACTIVE |

**Firestore `shipping_lines` collection:** ~15 docs with `full_name`, `country`, `bol_prefixes`.
Used by `read_everything.py` brain indexer only. **NOT used by tracker extraction.**

### 3.3 Liner Coverage Gaps

| Shipping Line | Regex | Domain | BL Pattern | Issue |
|---|---|---|---|---|
| ZIM | Yes | Yes | Generic only | Missing ZIMU prefix |
| MSC | Yes | Yes | MEDURS | OK |
| Maersk | Yes | Yes | **DEFINED NOT USED** | `bol_maersk` excluded from loop |
| CMA CGM | Yes | Yes | Generic only | Missing CMDU prefix |
| Hapag-Lloyd | Partial | Yes | Generic only | Only "HAPAG" matches, not "Hapag-Lloyd" |
| ONE | Yes | Yes | Generic only | **`\bONE\b` matches English word "one"** |
| Evergreen | Yes | Yes | Generic only | Missing EGLV prefix |
| COSCO | Yes | Partial | Generic only | May use cosco-shipping.com |
| Yang Ming | Yes | **NO** | Generic only | Missing domain |
| HMM | Yes | Yes | Generic only | — |
| PIL | Yes | **NO** | Generic only | Missing domain |
| TURKON | Yes | **NO** | Generic only | Missing domain |
| OOCL | Yes | **NO** | Generic only | Missing domain |
| **WAN HAI** | **NO** | **NO** | **NO** | **Completely missing** |

### 3.4 BL PDF Extraction Flow (complete chain)

```
PDF arrives via email
  │
  ▼
[rcb_helpers.py] extract_text_from_attachments()
  ├─ pdfplumber (text + tables) — FREE
  ├─ pypdf (fallback) — FREE
  ├─ Combined merge — FREE
  └─ Google Vision OCR (only if all text methods fail) — PAID
  │
  Tags: [BL_NUMBER], [CONTAINER], [INVOICE_NUMBER], etc.
  │
  ▼ TWO PARALLEL PATHS
  │
  ├─── CLASSIFICATION PATH (if invoice present) ──────────┐
  │  Agent 1 (Gemini Flash) → extract bl_number, vessel    │
  │  parse_all_documents() → regex BL field extraction      │
  │  Agent 2 (Claude) → HS classification                   │
  │  Agents 3-6 (Gemini) → regulatory/FTA/risk/synthesis    │
  │  → Firestore: rcb_classifications                       │
  │                                                         │
  ├─── TRACKER PATH (always runs) ─────────────────────────┤
  │  regex extraction (BOL, containers, vessels, etc.)       │
  │  Brain memory check (SelfLearningEngine)                 │
  │  Template extraction (doc_reader.py)                     │
  │  LLM enrichment (Gemini Flash) — only if regex thin      │
  │  Template learning (for future)                          │
  │  Match/create deal                                       │
  │  → Firestore: tracker_observations, tracker_deals,       │
  │               tracker_container_status, tracker_timeline  │
  └─────────────────────────────────────────────────────────┘
```

---

## 4. COST EFFICIENCY AUDIT

### PATH A: BL-Only Email (shipping docs, no invoice)
```
Graph API fetch .................. FREE
pdfplumber/pypdf ................. FREE    ✓ correct priority
Regex extraction ................. FREE    ✓ correct priority
Brain memory check ............... FREE    ✓ correct priority
Template extraction .............. FREE    ✓ correct priority
[Gemini Flash IF thin results] ... ~$0.001 conditional
Template learning ................ FREE
Deal create/update ............... FREE
Pupil observation ................ FREE
─────────────────────────────────────────
TOTAL: $0.00 - $0.001 ← EXCELLENT
```

### PATH B: BL+Invoice Email (full classification)
```
Graph API fetch .................. FREE
pdfplumber/pypdf ................. FREE
Agent 1 Gemini Flash ............. $0.001  ← ALWAYS runs, even if regex has BL fields
parse_all_documents regex ........ FREE    ← runs AFTER Agent 1 (should run BEFORE)
pre_classify brain ............... FREE    ✓
query_tariff ..................... FREE    ← only 100 of 11,753 docs!
knowledge search ................. FREE    ✓
Agent 2 Claude Sonnet 4.5 ........ $0.01-0.03  ← NECESSARY (core HS classification)
tariff validation ................ FREE    ✓
Free Import Order API ............ FREE    ✓
ministry routing ................. FREE    ✓
verification ..................... FREE    ✓
smart questions .................. FREE    ✓
Agent 3 Gemini Flash (regulatory)  $0.001  ← could skip if intelligence has answers
Agent 4 Gemini Flash (FTA) ....... $0.001  ← could skip if intelligence has answers
Agent 5 Gemini Flash (risk) ...... $0.001  ← could skip if intelligence has answers
Agent 6 Gemini Flash (synthesis) . $0.001  ← BUG: should be Pro per docs
email build + send ............... FREE
[PARALLEL] tracker ............... $0-0.001 ← duplicate text extraction
[PARALLEL] pupil ................. FREE
─────────────────────────────────────────
TOTAL: ~$0.015-0.04
```

### Key Waste Identified

| Issue | Wasted per email | Fix |
|-------|-----------------|-----|
| Tool-calling engine disabled (circular import) | Entire engine dead | Move import to lazy |
| Agent 1 runs BEFORE regex parser | ~$0.001 | Reorder |
| Agents 3-5 always run even when Intelligence has answers | ~$0.003 | Conditional skip |
| Duplicate text extraction (classification + tracker) | CPU waste | Pass text to tracker |
| `query_tariff()` limited to 100/11,753 docs | Quality loss | Increase limit |
| Agent 6 uses Flash instead of Pro | Quality loss | Change tier |

### What's Working Well (cost-wise)

- **Tracker path is excellent** — regex → brain → template → [LLM only if thin]
- **Vision OCR correctly gated** — only fires if ALL text methods fail quality check
- **Claude/ChatGPT NOT called in tracker path** — only Gemini Flash
- **Template learning working** — system learns document layouts, reduces future AI calls
- **Self-learning memory check** — skips AI for known products (tool-calling engine, when it works)

---

## 5. DOCUMENTATION INVENTORY

All docs are markdown (.md), no .docx files exist.

### System Architecture Docs
| File | Size | Content |
|------|------|---------|
| `docs/SYSTEM.md` | 5KB | Architecture overview, tech stack, 6-agent pipeline |
| `docs/SYSTEM_INDEX.md` | 41KB | Comprehensive system index (auto-generated) |
| `docs/MASTER_PLAN.md` | 12KB | 8-step classification flow, ministry map, implementation phases |
| `docs/WIRING_PLAN.md` | 14KB | How to connect existing modules, phase-by-phase |
| `docs/DECISIONS.md` | 5KB | 10 architecture decisions with rationale |
| `docs/CODE_AUDIT.md` | 14KB | Earlier code audit |
| `docs/CHANGELOG.md` | 18KB | Full change history |
| `docs/ROADMAP.md` | 6KB | Future roadmap |
| `docs/FIRESTORE_INVENTORY.md` | 1.4KB | 40 collections, 16,927 docs (as of Feb 11) |
| `functions/RCB_SYSTEM.md` | 3KB | Quick reference: collections, HS format, flow |

### Session Docs
| File | Size | Date | Summary |
|------|------|------|---------|
| `docs/SESSION24_FULL_CONTEXT.md` | 12KB | Feb 15 | 10 changes: air cargo, CC learning, shipping routing, audit |
| `docs/SESSION21_FULL_AUDIT.md` | 18KB | Feb 15 | Full inventory: 32 modules, 67 collections, wiring status |
| `docs/SESSION20_BACKUP.md` | 7KB | Feb 14 | Nightly learning pipeline |
| `docs/SESSION19_BACKUP.md` | 20KB | Feb 13 | System index + historical snapshots |
| `docs/SESSION18_BACKUP.md` | 17KB | Feb 12 | 58 deploys, full inventory |
| `docs/SESSION17_BACKUP.md` | 12KB | Feb 12 | Knowledge engine code audit |
| `docs/SESSION15_BACKUP.md` | 9KB | Feb 12 | Multi-model optimization |
| **`docs/SESSION25_FULL_CONTEXT.md`** | **THIS FILE** | **Feb 16** | **Full audit, BL investigation, cost analysis** |

---

## 6. FIRESTORE QUERIES NEEDED (Phase 1 — not yet executed)

These queries were planned but NOT run yet (script was written but not executed):

A) `learned_doc_templates` — which shipping lines have templates? What confidence?
B) `shipping_lines` — all carrier data, bol_prefixes
C) `learned_shipping_senders` — any data? (may be phantom)
D) `learned_shipping_patterns` — any data? (may be phantom)
E) Search for "Elizabeth" email across tracker_deals, tracker_observations, rcb_classifications
F) `tariff` collection count — confirm 11,753 docs and that query_tariff(limit=100) misses data

**These must be run before any BL fixes can proceed.**

---

## 7. PLANNED FIX ORDER (approved, not yet started)

### Phase 2: BL Extraction Fixes
1. **Maersk BL pattern** — add `bol_maersk` to extraction loop (tracker.py:347-352)
2. **Wire bol_prefixes from Firestore** — load shipping_lines collection into tracker, cache it
3. **Fix "ONE" false positive** — more specific pattern to avoid matching English word
4. **Add missing email domains** — Yang Ming, PIL, TURKON, OOCL, COSCO alternate
5. **Add WAN HAI** — regex + domain + WHLC prefix

### Phase 3: Critical Bugs
6. **query_tariff() 100-doc limit** — increase based on actual collection size
7. **overnight_audit.py:392 brain_index_size** — fix no-op replace
8. **classification_agents.py:2052 footer** — fix HTML marker search

### DO NOT TOUCH (separate session)
- Dead IMAP code, backup files, patch scripts, disabled functions
- Unused imports, dead functions
- pc_agent.py credentials, rcb_diagnostic.py Azure IDs
- Phantom collections investigation

---

## 8. CRITICAL BUGS NOT IN FIX PLAN (need separate prioritization)

These were found in the audit but are bigger fixes requiring design decisions:

| Bug | Impact | Why not in current plan |
|-----|--------|------------------------|
| Circular import (tool_executors.py:17) | Tool-calling engine dead | Needs careful testing — affects core pipeline |
| Tracker email signature mismatch | No tracker emails sent | Needs decision on what params to pass |
| brain_commander ask_claude broken | Father can't use Claude | Needs ai_intelligence.py created or import fixed |
| AWB regex extraction missing | Air cargo pipeline disconnected | Needs code added to _extract_logistics_data |
| Confidence format mismatch | All items medium confidence | Needs decision: Hebrew strings or numeric |
| Classification intent keywords too broad | Knowledge queries unreachable | Needs careful keyword list redesign |

---

## 9. PRODUCTION VERIFICATION CHECKLIST

| Check | Command | Expected |
|-------|---------|----------|
| Tool calling active? | Search logs for `TOOL_CALLING_AVAILABLE` | Should be True (currently False!) |
| Tracker emails sending? | Search logs for `Tracker email sent` | Should appear (currently crashing) |
| Brain commander working? | Search logs for `ask_claude` errors | Should NOT have ImportError |
| AWBs being extracted? | Search logs for `Registered AWB` | Should appear on AWB emails |
| Overnight audit ran? | Check `overnight_audit_results` collection | Should have today's doc |
| Daily digest sent? | Search logs for `Brain daily digest` | Should fire at 07:00 |
| Learning growing? | Check `learned_classifications` count | Should increase daily |

---

## 10. NEXT SESSION PRIORITIES

1. **Run Phase 1 Firestore queries** — get actual data before any fixes
2. **Fix circular import in tool_executors.py** — unblocks the tool-calling engine
3. **Fix tracker email signature** — unblocks tracker notifications
4. **Fix AWB extraction** — unblocks air cargo pipeline
5. **BL extraction fixes** (Maersk pattern, bol_prefixes, ONE false positive, missing domains)
6. **query_tariff limit** — easy win, big quality improvement

---

## 11. SESSION STATS

- Duration: ~3 hours
- Agents spawned: 10 parallel research agents
- Files read: 30+
- Issues found: 22 bugs + 5 dead code categories + 6 BL gaps
- Code written: 0 (audit only, as requested)
- Commits: 0
