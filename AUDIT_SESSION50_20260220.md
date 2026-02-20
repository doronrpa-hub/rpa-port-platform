# RCB SYSTEM — COMPREHENSIVE AUDIT REPORT
**Session 50 | Date: 2026-02-20 | READ ONLY AUDIT**
**Branch: main | Commit base: 1b62084**

---

## TABLE OF CONTENTS
1. [System Map](#1-system-map)
2. [AI/Model Usage Map](#2-aimodel-usage-map)
3. [Sessions Review](#3-sessions-review)
4. [Redundancies & Merge Candidates](#4-redundancies--merge-candidates)
5. [Gaps & Risks](#5-gaps--risks)
6. [Pending Items Assessment](#6-pending-items-assessment)
7. [Firestore Collection Inventory](#7-firestore-collection-inventory)
8. [Codebase Metrics](#8-codebase-metrics)

---

## 1. SYSTEM MAP

### 1.1 Codebase Overview

| Area | Files | Lines |
|------|-------|-------|
| `functions/lib/` (core library) | 71 | 62,455 |
| `functions/tests/` (test suite) | 23 | 11,150 |
| `functions/` (top-level scripts) | 53 | 15,729 |
| `functions/main.py` (entrypoint) | 1 | 2,352 |
| **Grand total** (app code) | ~148 | **89,556** |

### 1.2 Top 20 Largest Library Files

| # | File | Lines | Purpose |
|---|------|-------|---------|
| 1 | `classification_agents.py` | 3,494 | Multi-agent classification pipeline + email builder |
| 2 | `pupil.py` | 2,740 | Silent learning engine from CC emails |
| 3 | `port_intelligence.py` | 2,732 | Block I: vessel/port intelligence + digest |
| 4 | `tracker.py` | 2,609 | Shipment tracker (TaskYam + ocean) |
| 5 | `elimination_engine.py` | 2,413 | Block D: tariff elimination (GIR 1-6) |
| 6 | `tool_executors.py` | 2,411 | 33 tool handlers for tool-calling engine |
| 7 | `overnight_brain.py` | 2,200 | 12-stream nightly enrichment brain |
| 8 | `language_tools.py` | 2,068 | Hebrew/English bilingual NLP utilities |
| 9 | `intelligence.py` | 1,910 | Tariff search + regulatory intelligence |
| 10 | `rcb_inspector.py` | 1,749 | System inspection and diagnostics |
| 11 | `self_learning.py` | 1,732 | Classification memory + image patterns |
| 12 | `librarian_tags.py` | 1,714 | Tag-based document classification |
| 13 | `ocean_tracker.py` | 1,606 | 7-provider ocean tracking |
| 14 | `document_parser.py` | 1,504 | Multi-format document parser |
| 15 | `email_intent.py` | 1,261 | Email body intent classifier + handlers |
| 16 | `shipping_knowledge.py` | 1,230 | 9 carrier profiles, BIC/ISO 6346 |
| 17 | `librarian_researcher.py` | 1,181 | Research-oriented Firestore queries |
| 18 | `librarian.py` | 1,153 | Core librarian functions |
| 19 | `report_builder.py` | 1,123 | Classification report HTML builder |
| 20 | `rcb_helpers.py` | 1,096 | Graph API helpers, email quality gate |

### 1.3 Cloud Functions (27+ in main.py)

#### Firestore Triggers

| Function | Document Path | Purpose |
|----------|---------------|---------|
| `on_new_classification` | `classifications/{classId}` created | Auto-suggest HS code from knowledge base |
| `on_classification_correction` | `classifications/{classId}` updated | Learn when user corrects classification |

#### Scheduler Functions

| Function | Schedule | Memory | Timeout | Purpose |
|----------|----------|--------|---------|---------|
| `rcb_check_email` | every 2 min | 1GB | 540s | **MAIN**: Poll inbox, route emails (CC/direct/declarations) |
| `rcb_tracker_poll` | every 30 min | — | — | TaskYam poll + air cargo + gate cutoff + port alerts |
| `enrich_knowledge` | every 1 hour | 256MB | — | Enrich knowledge base, check downloads |
| `monitor_agent` | every 5 min | 256MB | 180s | System health monitoring |
| `rcb_cleanup_old_processed` | every 24 hours | — | — | Clean old rcb_processed documents |
| `rcb_ttl_cleanup` | daily 03:30 IL | 1GB | 540s | TTL cleanup with backup guard |
| `rcb_retry_failed` | every 6 hours | — | — | Retry failed classifications |
| `rcb_health_check` | every 1 hour | — | — | Periodic health check |
| `rcb_nightly_learn` | nightly | — | — | 4-step index builder |
| `rcb_port_schedule` | every 12 hours | 512MB | 300s | Build vessel schedules for 3 IL ports |
| `rcb_pupil_learn` | every 6 hours | 1GB | 540s | Silent learning verification cycle |
| `rcb_daily_digest` | daily 07:00 IL | 512MB | 300s | Morning port intelligence digest |
| `rcb_afternoon_digest` | daily 14:00 IL | 512MB | 300s | Afternoon digest |
| `rcb_overnight_audit` | daily 02:00 IL | 2GB | 900s | Diagnostic scan |
| `rcb_pc_agent_runner` | every 30 min | 512MB | 300s | Execute pending PC Agent tasks |
| `rcb_daily_backup` | daily 02:00 IL | 1GB | 540s | Export 4 collections to GCS NDJSON |
| `rcb_inspector_daily` | daily | — | — | System state inspection |
| `monitor_fix_scheduled` | — | — | — | **DISABLED** stub |

#### HTTP Endpoints

| Function | Auth | Purpose |
|----------|------|---------|
| `api` | Bearer token (RCB_API_SECRET) | REST API for web app (multiple routes) |
| `rcb_api` | Bearer (/health public) | RCB API endpoints |
| `rcb_self_test` | — | Self-test endpoint |
| `rcb_inspector` | — | Diagnostic HTTP endpoint |
| `monitor_agent_manual` | — | Manual monitor trigger |
| `monitor_self_heal` | — | **DISABLED** stub |
| `monitor_fix_all` | — | **DISABLED** stub |

### 1.4 Email Lifecycle

```
Email arrives at rcb@rpa-port.co.il (Graph API, polled every 2 min)
|
+-- Skip: rcb@ (self), cc@ (digest group), undeliverable, [RCB-SELFTEST]
|
+-- [DECL] in subject --> declarations_raw collection --> mark read --> DONE
|
+-- CC Email Path (is_direct=False):
|   +-- Pupil: silent learning (FREE, Firestore)
|   +-- Tracker: observe shipping updates --> tracker_deals
|   +-- Sanctions: screen shipper/consignee via OpenSanctions
|   +-- Schedule: detect vessel schedule emails --> port_schedules
|   +-- Email Intent: answer questions/status (6 intent types)
|   +-- Block A1: "invoice" keyword + attachments --> classify
|   +-- Gap 2: deal has invoice+shipping doc --> auto-classify
|
+-- Direct Email Path (is_direct=True):
    +-- Reply routing: team-->direct, external-->find team in CC
    +-- Brain Commander: admin commands from doron@
    +-- Email Intent: handle questions/instructions
    +-- Knowledge Query: answer team questions
    +-- Shipping-only: BL/AWB without invoice --> tracker only
    +-- Classification pipeline:
        +-- extract_text_from_attachments()
        +-- process_and_send_report() --> run_full_classification()
        |   +-- Agent 1: Invoice extraction (Gemini-->Claude-->ChatGPT)
        |   +-- Pre-classify bypass (memory confidence >= 90%)
        |   +-- Tool-calling engine (33 tools, 15 rounds max)
        |   +-- Elimination engine (D1-D9, deterministic)
        |   +-- Agent 2: Classification (ALWAYS Claude)
        |   +-- Agents 3-5: Regulatory, FTA, Risk (Gemini)
        |   +-- Agent 6: Synthesis (Gemini Pro)
        |   +-- Verification engine (bilingual + flags)
        |   +-- Cross-checker (3-way: Gemini Pro + Flash + ChatGPT)
        |   +-- build_classification_email() --> send
        +-- Feed to Tracker for deal observation
        +-- Feed to Pupil for passive learning
```

### 1.5 Tracker Lifecycle

```
BL/AWB received in email
  --> tracker_process_email() extracts logistics data
  --> _match_or_create_deal() --> tracker_deals doc created
  --> deal_thread_id assigned (stable threading)
  --> _is_deal_classification_ready() checks for invoice + shipping doc

Every 30 min (rcb_tracker_poll):
  --> Phase 1: TaskYam query (ALWAYS PRIMARY, 100% authoritative)
     Import: manifest-->port_unloading-->delivery_order-->customs-->port_release-->cargo_exit
     Export: storage_id-->cargo_entry-->customs-->vessel_loaded-->ship_sailing
  --> Phase 2: Ocean APIs (supplements only, never overrides TaskYam)
     query_ocean_status() from ocean_tracker.py (7 providers)
  --> _send_tracker_email() with data guards:
     _deal_has_minimum_data() required
     validate_email_before_send() quality gate
     clean_email_subject() strips Re:/Fwd: chains
     email_quality_gate() (6 rejection rules)
  --> check_gate_cutoff_alerts() -- warning/urgent/critical
  --> _run_port_intelligence_alerts() -- D/O, exam, storage, cutoff
```

### 1.6 Nightly Schedule (Jerusalem Time)

| Time | Function | Streams/Steps | Cost |
|------|----------|---------------|------|
| 20:00 | `rcb_overnight_brain` | 12 streams (Phases A-H) | $3.50 cap |
| 02:00 | `rcb_nightly_learn` | 4-step index builder | $0.00 |
| 02:00 | `rcb_overnight_audit` | Diagnostic scan | $0.00 |
| 02:00 | `rcb_daily_backup` | 4 collections --> GCS NDJSON | $0.00 |
| 03:30 | `rcb_ttl_cleanup` | TTL cleanup (backup-guarded) | $0.00 |
| 04:00 | `rcb_download_directives` | Shaarolami directives | $0.00 |
| 07:00 | `rcb_daily_digest` | Morning port digest (I4) | $0.00 |
| 14:00 | `rcb_afternoon_digest` | Afternoon digest (I4) | $0.00 |

### 1.7 Overnight Brain Streams (12 total)

| Stream | Phase | Name | Cost |
|--------|-------|------|------|
| 6 | A | UK Tariff API sweep | $0.00 |
| 3 | B | CC learning | ~$0.02 |
| 1 | B | Tariff mining | ~$0.02 |
| 2 | B | Email mining | ~$0.02 |
| 4 | C | Attachment mining | ~$0.03 |
| 5 | C | AI knowledge fill | ~$0.04 |
| 7 | D | Cross-reference engine | $0.00 |
| 8 | E | Self-teach | ~$0.02 |
| 9 | F | Knowledge sync | $0.00 |
| 10 | G | Deal enrichment | $0.00 |
| 11 | G2 | Port intelligence sync | $0.00 |
| 12 | H | Regression guard | $0.00 |

---

## 2. AI/MODEL USAGE MAP

### 2.1 Model Routing

| Component | Primary Model | Fallback(s) | Input/Output per MTok |
|-----------|--------------|-------------|----------------------|
| **Agent 1** (extraction) | Gemini 2.5 Flash | Claude Sonnet --> ChatGPT 4o-mini | $0.15/$0.60 |
| **Agent 2** (classification) | Claude Sonnet (ALWAYS) | None -- hard requirement | $3/$15 |
| **Agents 3,4,5** (reg/FTA/risk) | Gemini Flash | Claude | $0.15/$0.60 |
| **Agent 6** (synthesis) | Gemini 2.5 Pro | Claude | $1.25/$10 |
| **Tool-calling engine** | Gemini Flash | Claude | $0.15/$0.60 |
| **Cross-checker** | Gemini Pro + Flash + ChatGPT | -- | ~$1.55 combined |
| **Elimination D6** | Gemini Flash | Claude | $0.15/$0.60 |
| **Verification Phase 4** | Gemini Flash | Claude | $0.15/$0.60 |
| **Image analysis** | Gemini Flash + Claude Vision | -- | ~$3.15 combined |
| **Overnight brain** | Gemini Flash (budget-capped) | -- | $0.15/$0.60 |
| **Email intent** | Gemini Flash (ambiguous only) | -- | ~$0.001 |

### 2.2 AI Call Locations

| File | Function | Model | Purpose |
|------|----------|-------|---------|
| `classification_agents.py:344` | `call_claude()` | Claude Sonnet | API wrapper |
| `classification_agents.py:394` | `call_chatgpt()` | GPT-4o-mini | Third fallback |
| `classification_agents.py:508` | `call_gemini_fast()` | Gemini Flash | Fast tier |
| `classification_agents.py:513` | `call_gemini_pro()` | Gemini Pro | Pro tier |
| `classification_agents.py:530` | `call_ai(tier="smart")` | Claude (always) | Agent 2 |
| `tool_calling_engine.py:743` | `_call_gemini_with_tools()` | Gemini Flash | Tool loop |
| `tool_calling_engine.py:730` | `_call_claude_with_tools()` | Claude | Forced final answer |
| `cross_checker.py:88` | `_call_gemini_pro_check()` | Gemini Pro | Cross-check vote 1 |
| `cross_checker.py:96` | `_call_chatgpt_check()` | GPT-4o-mini | Cross-check vote 3 |
| `image_analyzer.py:103` | `_analyze_with_gemini()` | Gemini Flash | Image vision |
| `image_analyzer.py:146` | `_analyze_with_claude()` | Claude | Image vision |
| `elimination_engine.py:2003` | Level 4c Consultation | Gemini-->Claude | AI tiebreak |
| `verification_engine.py:245` | Phase 4 Bilingual | Gemini-->Claude | Confidence check |
| `overnight_brain.py:42` | `call_gemini_tracked()` | Gemini Flash | Enrichment |
| `brain_commander.py:326` | Father channel | Gemini Flash | Commands |
| `email_intent.py` | Ambiguous intent | Gemini Flash | ~$0.001 |

### 2.3 Key Flags and Constants

| Flag | File | Value | Effect |
|------|------|-------|--------|
| `_PREFER_GEMINI` | tool_calling_engine.py | `True` | Gemini first, Claude fallback |
| `_GEMINI_MODEL` | tool_calling_engine.py | `gemini-2.5-flash` | Primary model |
| `_gemini_quota_exhausted` | classification_agents.py | Reset per run | Skip all Gemini on 429 |
| `PRE_CLASSIFY_BYPASS_ENABLED` | classification_agents.py | `True` | Skip AI when memory >= 90% |
| `CROSS_CHECK_ENABLED` | classification_agents.py | `True` | 3-way verification |
| `ELIMINATION_ENABLED` | classification_agents.py | `True` | Deterministic tree walk |
| `VERIFICATION_ENGINE_ENABLED` | classification_agents.py | `True` | Phase 4+5 bilingual |
| `_MAX_ROUNDS` | tool_calling_engine.py | `15` | Max tool-calling iterations |
| `_TIME_BUDGET_SEC` | tool_calling_engine.py | `180` | Max time for tool loop |
| `BUDGET_LIMIT` | cost_tracker.py | `$3.50` | Hard cap per overnight run |
| `IMAGE_ANALYSIS_COST` | cost_tracker.py | `$0.002` | Per image analysis |

### 2.4 Monthly Cost Estimates (2,000 classifications)

| Component | Estimated Monthly Cost |
|-----------|----------------------|
| Tool-calling (Gemini primary) | $200-250 |
| Cross-check (3-way) | $40-50 |
| Overnight brain (30 nights) | $50-70 |
| Image analysis (~100/mo) | $20-30 |
| Elimination + Verification AI (rare) | $15-25 |
| **Total estimated** | **$325-425/month** |

### 2.5 Tool-Calling Engine: 33 Active Tools

| # | Tool | Source | Cost |
|---|------|--------|------|
| 1 | `check_memory` | classification_memory (Firestore) | FREE |
| 2 | `search_tariff` | tariff, keyword_index, product_index, supplier_index | FREE |
| 3 | `check_regulatory` | regulatory + free_import_order (C3) + free_export_order (C4) | FREE |
| 4 | `lookup_fta` | FTA rules + framework_order (C5) | FREE |
| 5 | `verify_hs_code` | tariff collection | FREE |
| 6 | `extract_invoice` | Gemini Flash | ~$0.001 |
| 7 | `assess_risk` | Rule-based (dual-use chapters, high-risk origins) | FREE |
| 8 | `get_chapter_notes` | chapter_notes (C2) | FREE |
| 9 | `lookup_tariff_structure` | tariff_structure (C2) | FREE |
| 10 | `lookup_framework_order` | framework_order (C5) | FREE |
| 11 | `search_classification_directives` | classification_directives (C6) | FREE |
| 12 | `search_legal_knowledge` | legal_knowledge (C8) | FREE |
| 13 | `run_elimination` | elimination_engine (D1-D8) deterministic | FREE |
| 14 | `search_wikipedia` | Wikipedia REST API | FREE |
| 15 | `search_wikidata` | Wikidata API | FREE |
| 16 | `lookup_country` | restcountries.com | FREE |
| 17 | `convert_currency` | open.er-api.com | FREE |
| 18 | `search_comtrade` | UN Comtrade (overnight only) | FREE |
| 19 | `lookup_food_product` | Open Food Facts | FREE |
| 20 | `check_fda_product` | FDA API (drugs + 510k) | FREE |
| 21 | `bank_of_israel_rates` | BOI SDMX + PublicApi | FREE |
| 22 | `search_pubchem` | NIH PubChem | FREE |
| 23 | `lookup_eu_taric` | EU TARIC | FREE |
| 24 | `lookup_usitc` | US HTS | FREE |
| 25 | `israel_cbs_trade` | CBS Israel (overnight only) | FREE |
| 26 | `lookup_gs1_barcode` | Open Food Facts barcode | FREE |
| 27 | `search_wco_notes` | WCO explanatory notes | FREE |
| 28 | `lookup_unctad_gsp` | UNCTAD GSP | FREE |
| 29 | `search_open_beauty` | Open Beauty Facts | FREE |
| 30 | `crossref_technical` | CrossRef (overnight only) | FREE |
| 31 | `check_opensanctions` | OpenSanctions (10k/mo free) | FREE |
| 32 | `get_israel_vat_rates` | gov.il API | FREE |
| 33 | `fetch_seller_website` | Domain inference + homepage | FREE |

### 2.6 Pre-Enrichment Triggers (Step 4b, before AI loop)

| Trigger | Condition | Tool Called |
|---------|-----------|------------|
| Country lookup | `origin` >= 2 chars | `lookup_country` |
| Currency lookup | Invoice currency not ILS/NIS | `convert_currency` / `bank_of_israel_rates` |
| Food product | Item words intersect 60 bilingual food keywords | `lookup_food_product` |
| Medical product | Item words intersect 33 bilingual medical keywords | `check_fda_product` |
| Chemical | 30 bilingual chemical terms | `search_pubchem` |
| Cosmetics | 30 bilingual cosmetics terms | `search_open_beauty` |

### 2.7 Cross-Reference Pipeline (Step 7d2, after classification)

For each validated HS code:
1. `lookup_eu_taric(hs6)` -- EU TARIC cross-reference
2. `lookup_usitc(hs6)` -- US HTS cross-reference
3. Confidence adjustment: both agree +0.12, one agrees +0.06, neither agrees -0.05

---

## 3. SESSIONS REVIEW

### 3.1 Session Timeline

| Session | Date | What Was Done | Status |
|---------|------|---------------|--------|
| 31 | Feb 16 | FCL/LCL detection, lifecycle tracking, CC learning, reference data | COMPLETE |
| C1 | Feb 16 | Shaarolami tariff descriptions (2,104 filled) | COMPLETE |
| B/Ocean | Feb 17 | ocean_tracker.py (1,606 lines, 7 providers) | COMPLETE |
| C2 | Feb 17 | Chapter notes parser (94/98 chapters) | COMPLETE (25 chapters missing XML) |
| C3 | Feb 17 | Free Import Order (6,121 HS codes) | COMPLETE |
| 32 eve | Feb 17 | Blocks C4+C5+C6+C8 (4 blocks, 12 tools) | COMPLETE (C7 blocked) |
| 33a | Feb 18 | Audit + caching + merge + cleanup | COMPLETE |
| 33b | Feb 18 | Block D: Elimination Engine D1-D8 (2,282 lines) | COMPLETE |
| D9 | Feb 18 | Pipeline wiring (13th tool) | COMPLETE |
| 34 | Feb 18 | Gap 2: Auto-trigger classification | COMPLETE |
| 34b | Feb 18 | Elimination live testing (3 bugs fixed) | COMPLETE |
| 34E | Feb 18 | Block E: Verification Engine (743 lines) | COMPLETE |
| 35 | Feb 18 | Email Body Intelligence (6 intents, 600 lines) | COMPLETE |
| 36 | Feb 18 | Content quality audit (4 HTML samples) | COMPLETE (justification English-only flagged) |
| 37 | Feb 18 | Tracker email visual redesign (7 section builders) | COMPLETE |
| 37b | Feb 18 | Tool #14: Wikipedia API | COMPLETE |
| 38 | Feb 18 | 5 audit fixes + automated backup system | COMPLETE (77/82 issues remain) |
| 38b | Feb 18 | Tools #15-20 (6 external APIs) | COMPLETE |
| 38c | Feb 18 | Fixes H3,H4,H5,H7,H8 | COMPLETE |
| 39 | Feb 18 | Tools #21-32 (12 APIs + cross-ref + sanctions) | COMPLETE |
| 40 | Feb 18 | Block H: Classification email redesign + HS format fix | COMPLETE |
| 40b | Feb 18 | Tracker feedback loop fix + data cleanup | COMPLETE |
| 40c | Feb 18 | Image pattern caching | COMPLETE |
| 41 | Feb 18 | Email quality: empty guards, clean subjects, threading | COMPLETE |
| 41b | Feb 18 | Land transport ETA alerts (route_eta.py) | COMPLETE (wiring to main.py deferred) |
| 44 | Feb 18 | Block I: I3+I4 alerts + digest | COMPLETE |
| 44-PAR | Feb 18 | Overnight brain streams 10-12 | COMPLETE |
| 45 | Feb 18 | Email quality gate (6 rejection rules) | COMPLETE |
| 46 | Feb 18 | Identity Graph (500 lines, 105 tests) | BUILT, **NOT WIRED** |
| 47 | Feb 18 | BALKI fixes (scanned PDF, price offers, MOT, tool #33) | COMPLETE |
| 48 | Feb 18 | AI fallback chain + max rounds fix | COMPLETE |
| 49 | Feb 19 | Full system audit report | COMPLETE |
| 50 | Feb 20 | This comprehensive audit | COMPLETE |

### 3.2 Block Status

| Block | Description | Status |
|-------|-------------|--------|
| A1-A4 | CC invoice classification, declaration routing, never-silent exits, clarification | COMPLETE |
| B1-B2 | Smart extractor wiring, keyword seeding | COMPLETE |
| C1 | Tariff descriptions (2,104 filled) | COMPLETE |
| C2 | Chapter notes (94/98 chapters) | COMPLETE |
| C3 | Free Import Order (6,121 HS codes) | COMPLETE |
| C4 | Free Export Order (979 HS codes) | COMPLETE |
| C5 | Framework Order (85 docs) | COMPLETE |
| C6 | Classification Directives (218 enriched) | COMPLETE |
| C7 | Pre-Rulings | **BLOCKED** (shaarolami WAF) |
| C8 | Legal Knowledge (19 docs) | COMPLETE |
| D1-D9 | Elimination Engine (2,282 lines + pipeline wiring) | COMPLETE |
| E | Verification Engine (Phase 4+5+Flagging, 743 lines) | COMPLETE |
| F | (Undefined) | NOT STARTED |
| G | (Undefined) | NOT STARTED |
| H | Classification email redesign (14 section builders) | COMPLETE |
| I1-I4 | Port Intelligence (deal-schedule link, views, alerts, digest) | COMPLETE |

### 3.3 Items Started But Not Finished

| Item | Session | Current State | Blocker |
|------|---------|---------------|---------|
| Identity Graph wiring | 46 | Built + 105 tests, NOT wired into tracker_process_email() | Needs careful integration |
| Justification Engine Hebrew | 36 | English-only chain text (scored 5.6/10) | Requires parallel `decision_he` fields |
| 25 chapters without XML notes | C2 | Missing from RuleDetailsHistory.xml | May need shaarolami scraping |
| Gemini paid tier upgrade | 48 | Free tier hits 429 daily | Needs billing account upgrade |
| Route ETA wiring to main.py | 41b | route_eta.py + check_gate_cutoff_alerts built | Needs main.py scheduler wiring |
| C7 Pre-Rulings | 32 | Shaarolami URL returns 0 bytes | WAF blocking, no alt source |

### 3.4 Items Never Started

| Item | Description |
|------|-------------|
| Block F | Undefined in CLAUDE.md |
| Block G | Undefined in CLAUDE.md |
| Forwarding Module | New `fwd_` prefix functions -- explicitly deferred 4-6 weeks |

---

## 4. REDUNDANCIES & MERGE CANDIDATES

### 4.1 Duplicate Functions (31 instances across codebase)

| Function | Count | Files | Priority |
|----------|-------|-------|----------|
| `_extract_keywords` | 4 | elimination_engine, intelligence, pupil, verification_engine | **CRITICAL** |
| `_safe_id` | 3 | enrichment_agent, librarian_researcher, pc_agent | HIGH |
| `_to_israel_time` | 2 | port_intelligence, tracker_email | HIGH |
| `scan_all_collections` | 2 | librarian, librarian_index | HIGH |
| `_chapter_from_hs` | 2 | cross-file | MEDIUM |
| `_clean_hs` | 2 | cross-file | MEDIUM |
| `_cleanup_hebrew_text` | 2 | cross-file | MEDIUM |
| `_derive_current_step` | 2 | cross-file | MEDIUM |
| `_extract_urls_from_text` | 2 | cross-file | LOW |
| `_get_body_text` | 2 | cross-file | LOW |
| `_get_sender_address` | 2 | cross-file | LOW |
| `_iso6346_check_digit` | 2 | cross-file | LOW |
| `_make_obs_id` | 2 | cross-file | LOW |
| `_section_header` | 2 | cross-file | LOW |
| `_strip_html` | 2 | cross-file | LOW |
| `_tag_document_structure` | 2 | cross-file | MEDIUM |
| ~15 more | 2x each | various | LOW-MEDIUM |

**Recommendation:** Create `functions/lib/shared_utils.py` with canonical implementations. Estimated ~800 lines saved.

### 4.2 Dead/Unused Modules

| Module | Lines | Evidence | Action |
|--------|-------|---------|--------|
| `self_enrichment.py` | ~200 | CLAUDE.md: "redundant (Stream 5 + Stream 10 cover its use case)" | DELETE |
| `product_classifier.py` | ~900 | Zero imports; superseded by elimination_engine | DELETE |
| `rcb_email_processor.py` | ~400 | Legacy IMAP; replaced by Graph API in rcb_helpers | DELETE (verify first) |
| 3 disabled monitor stubs in main.py | ~30 | Print "DISABLED" and return | DELETE |

### 4.3 Backup Files (10 files, ~568 KB)

| File | Status |
|------|--------|
| `functions/lib/classification_agents.py.backup_session22` | STALE |
| `functions/main.py.backup` | STALE |
| `functions/main.py.backup_20260205_150741` | STALE |
| `functions/main.py.backup_session10` | STALE |
| `functions/main.py.backup_session6` | STALE |
| `functions/main.py.bak` | STALE |
| `functions/main.py.bak_20260216` | STALE |
| `functions/main.py.bak2_20260216` | STALE |
| `functions/requirements.txt.backup` | STALE |
| `functions/requirements.txt.bak` | STALE |

Also: `functions/overnight_log.txt` (1.5 MB) -- should be in .gitignore.

All safe to delete -- git history preserves everything.

### 4.4 One-Time Scripts (~23 scripts, ~2,131 lines)

Files like `fix_decorator.py`, `fix_final.py`, `fix_main_imports.py`, `add_attachments.py`, `patch_classification.py` etc. All served their purpose in earlier sessions. Could move to `scripts/archive/` or delete.

### 4.5 Module Family Overlaps

#### Librarian Ecosystem (4 modules, 4,929 lines)

| Module | Lines | Overlap Issue |
|--------|-------|---------------|
| `librarian.py` | 1,153 | Core search -- has `scan_all_collections` |
| `librarian_index.py` | 881 | Indexing -- ALSO has `scan_all_collections` |
| `librarian_researcher.py` | 1,181 | Learning -- has `_safe_id` (also in 2 other files) |
| `librarian_tags.py` | 1,714 | Tagging -- duplicates operations from librarian.py |

#### Document Reading Ecosystem (3 modules, 2,211 lines)

| Module | Lines | Issue |
|--------|-------|-------|
| `document_parser.py` | 1,504 | Primary parser |
| `doc_reader.py` | 589 | Template extraction (overlapping table logic) |
| `read_document.py` | 118 | Single-function shim -- merge into extraction_adapter.py |

#### Verification Ecosystem (2 modules, 1,204 lines)

| Module | Lines | Issue |
|--------|-------|-------|
| `verification_engine.py` | 743 | Newer (Session 34E) |
| `verification_loop.py` | 461 | Older -- may be superseded. **AUDIT NEEDED** |

### 4.6 classification_agents.py -- God Object Risk

At 3,494 lines and 52 git changes, this file handles too many concerns:
- Multi-agent pipeline orchestration
- Email HTML building (14 section builders)
- Feature flags management
- Confidence adjustment helpers
- Verification engine wiring
- Cross-check wiring

**Recommendation:** Consider splitting into:
- `classification_core.py` -- Agent 1-6 AI calls, pipeline orchestration
- `classification_email.py` -- Email HTML building (already partially separated)
- `classification_config.py` -- Feature flags, constants

---

## 5. GAPS & RISKS

### 5.1 Critical Gaps

| # | Gap | Severity | Impact |
|---|-----|----------|--------|
| 1 | **Identity Graph not wired** (Session 46, 500 lines + 105 tests) | HIGH | Deal matching relies only on tracker.py regex |
| 2 | **82% of lib files have no unit tests** (49/60 untested) | HIGH | Regression risk on every change |
| 3 | **85 Firestore collections used but NOT registered** in librarian_index | MEDIUM | Overnight brain can't index/search them |
| 4 | **35 dead COLLECTION_FIELDS entries** registered but never used | LOW | Cognitive load, misleading inventory |
| 5 | **Gemini free tier** -- 429 quota exhausted daily | MEDIUM | Classification cost 20x higher when Gemini down |
| 6 | **Justification text English-only** (scored 5.6/10 in audit) | MEDIUM | Israeli users see English in Hebrew RTL email |

### 5.2 Error Handling Gaps (Bare except: clauses)

| # | File:Line | Context | Severity |
|---|-----------|---------|----------|
| 1 | `doc_reader.py:361` | `except: pass` in template extraction | MEDIUM |
| 2 | `rcb_email_processor.py:171` | `except: pass` in IMAP processing | MEDIUM |
| 3 | `rcb_email_processor.py:179` | `except: pass` in IMAP processing | MEDIUM |
| 4 | `tracker.py:1674` | `except: pass` in token cleanup | LOW |
| 5 | `tracker.py:2161` | Bare except in header decode | LOW |
| 6 | `pc_agent.py:502` | `except: pass` in script execution | LOW |
| 7 | `pdf_creator.py:76` | `except: pass` in font registration | LOW |

### 5.3 Test Coverage Analysis

**Test suite: 968 passed, 5 failed (pre-existing BS4), 2 skipped**

**23 test files covering 11 library modules:**

| Test File | Lines | Covers |
|-----------|-------|--------|
| `test_port_intelligence.py` | 1,633 | port_intelligence.py |
| `test_identity_graph.py` | 1,005 | identity_graph.py |
| `test_route_eta.py` | 860 | route_eta.py |
| `test_overnight_brain.py` | 651 | overnight_brain.py |
| `test_email_intent.py` | 647 | email_intent.py |
| `test_pc_agent_runner.py` | 614 | pc_agent.py |
| `test_report_builder.py` | 589 | report_builder.py |
| `test_verification_engine.py` | 579 | verification_engine.py |
| `test_uk_tariff_integration.py` | 534 | UK tariff API |
| `test_classification_agents.py` | 515 | classification_agents.py |
| `test_email_quality_gate.py` | 513 | rcb_helpers.py (partial) |
| `test_data_pipeline.py` | 382 | data_pipeline/ |
| `test_directive_downloader.py` | 365 | data_pipeline/ |
| `test_justification_engine.py` | 334 | justification_engine.py |
| `test_tool_calling.py` | 301 | tool_definitions.py |
| `test_librarian.py` | 259 | librarian.py |
| `test_rcb_helpers.py` | 256 | rcb_helpers.py |
| `test_smart_extractor.py` | 251 | smart_extractor.py |
| `test_knowledge_query.py` | 191 | knowledge_query.py |
| `test_extraction_validator.py` | 190 | extraction validation |
| `test_ttl_cleanup.py` | 188 | TTL cleanup |
| `test_table_extractor.py` | 155 | table extraction |
| `test_storage_manager.py` | 138 | storage management |

**HIGH-RISK UNTESTED modules (lines > 1,000):**

| Module | Lines | Risk | Why It Matters |
|--------|-------|------|----------------|
| `elimination_engine.py` | 2,413 | HIGH | Core tariff classification logic, only live test scripts exist |
| `tracker.py` | 2,609 | HIGH | Core shipment tracking, 36 git changes |
| `tool_executors.py` | 2,411 | HIGH | All 33 tool handlers, external API integrations |
| `ocean_tracker.py` | 1,606 | HIGH | 7 ocean carrier providers |
| `self_learning.py` | 1,732 | HIGH | Classification memory, confidence regression guard |
| `intelligence.py` | 1,910 | HIGH | Core tariff search, MOT routing |
| `cross_checker.py` | ~500 | HIGH | 3-way verification, confidence adjustment |
| `document_parser.py` | 1,504 | MEDIUM | Multi-format document parsing |
| `pupil.py` | 2,740 | MEDIUM | Silent learning (2,740 lines, no test) |

**Test-to-code ratio: 11,150 test lines / 62,455 lib lines = 17.9%**

### 5.4 Write-Only Collections (data never read back)

| Collection | Written By | Never Read By |
|-----------|-----------|---------------|
| `agent_tasks` | main.py | No reader found |
| `chapter_classification_rules` | overnight_brain | Never applied |
| `declarations_raw` | main.py | Never processed |
| `hs_code_crossref` | overnight_brain | Never read |
| `hs_code_references` | overnight_brain | Never read |
| `learned_answers` | knowledge_query | Never returned |
| `learned_document_types` | seed scripts | Never used |
| `learned_identifier_patterns` | seed scripts | Never consumed |

### 5.5 External Dependencies Without Fallback

| Dependency | Used By | Fallback | Risk |
|-----------|---------|----------|------|
| Microsoft Graph API | rcb_check_email (every 2 min) | **NONE** | **CRITICAL** |
| Google Secret Manager | All functions at startup | **NONE** | **CRITICAL** |
| Claude API | Agent 2 (classification) | **NONE** | HIGH |
| TaskYam (israports.co.il) | tracker_poll (every 30 min) | Ocean APIs (partial) | HIGH |
| Gemini API | Tool-calling, agents 1/3/4/5/6 | Claude --> ChatGPT | Good |
| OpenRouteService | route_eta.py | OSRM (free fallback) | Good |

### 5.6 5 Pre-Existing Test Failures

All from BeautifulSoup4 dependency version issues:

| Test | Failure |
|------|---------|
| `test_data_pipeline::test_html_extraction` | BS4 `bad()` not stripped |
| `test_data_pipeline::test_html_table_extraction` | BS4 returns 0 tables |
| `test_smart_extractor::test_html_scripts_removed` | BS4 not stripping `<script>` |
| `test_table_extractor::test_bs4_tables` | BS4 returns None |
| `test_table_extractor::test_bs4_multiple_tables` | BS4 returns None |

### 5.7 Hardcoded Secrets Scan

**CLEAN** -- No hardcoded API keys, tokens, passwords, or secrets found in the codebase. All secrets fetched via `get_secret()` from Google Cloud Secret Manager.

Only intentional hardcoded values:
- `doron@rpa-port.co.il` as admin email (documented, intentional)
- Port coordinates in `route_eta.py` (ports don't move)
- `sa-key.json` in `.gitignore` (never committed to git history)

### 5.8 TODO/FIXME Comments

Only 1 found: `air_cargo_tracker.py:260` -- `TODO: Check swissport.co.il for API access`

---

## 6. PENDING ITEMS ASSESSMENT

### 6.1 Justification Engine Language Issue

**Problem:** `justification_engine.py` generates English `decision` and `source_text` fields. Hebrew step labels wrap English content. Israeli customs professionals see English reasoning in a Hebrew RTL email. Content audit scored this 5.6/10.

**Fix:** Generate parallel `decision_he` fields or translate at render time.
**Files affected:** `justification_engine.py`, `classification_agents.py`
**Effort:** 1-2 sessions (moderate)

### 6.2 body_html in sent_emails

**Problem:** The `email_quality_log` and tracking may store full HTML bodies, creating large Firestore documents.

**Assessment:** Check `_log_email_quality()` in `rcb_helpers.py` and any `sent_emails` collection writes. Audit before fixing.
**Effort:** 1 hour audit, then decide on fix

### 6.3 Intent Reply Branding

**Problem:** `email_intent.py` sends replies to team questions but these replies may lack the RPA-PORT branded header/footer used in classification and tracker emails.

**Fix:** Wrap intent reply HTML in the same branded template.
**Effort:** ~2 hours

### 6.4 Recommended Priority Order

1. **Intent reply branding** -- lowest risk, highest visual impact, ~2 hours
2. **body_html audit** -- understand scope first, ~1 hour
3. **Justification Hebrew** -- largest effort, highest value, ~1-2 sessions

---

## 7. FIRESTORE COLLECTION INVENTORY

### 7.1 Summary

| Metric | Count |
|--------|-------|
| Registered in librarian_index COLLECTION_FIELDS | 82 |
| Used in active code | ~132 |
| Total unique collections found | ~167 |
| Registered AND used (properly aligned) | ~47 |
| Registered but NEVER used (dead weight) | ~35 |
| Used but NOT registered (gap) | ~85 |

### 7.2 Top 20 Most Heavily Used Collections

| Collection | Registered | Reads | Writes | Total | Purpose |
|-----------|:---:|---:|---:|---:|---------|
| classification_knowledge | Y | 11 | 4 | 15 | Classification pipeline |
| rcb_processed | Y | 9 | 5 | 14 | Pipeline marker |
| librarian_index | **N** | 6 | 8 | 14 | Self-index |
| knowledge_base | Y | 11 | 2 | 13 | Knowledge/learning |
| rcb_classifications | Y | 10 | 3 | 13 | Classification results |
| tracker_deals | Y | 8 | 5 | 13 | Logistics deals |
| tariff | Y | 11 | 1 | 12 | HS codes/descriptions |
| keyword_index | Y | 8 | 3 | 11 | Keyword search |
| chapter_notes | Y | 8 | 2 | 10 | Tariff chapter text |
| knowledge_gaps | **N** | 5 | 4 | 9 | Gap analysis |
| product_index | Y | 5 | 3 | 8 | Product cache |
| supplier_index | Y | 4 | 4 | 8 | Supplier cache |
| tariff_chapters | Y | 8 | 0 | 8 | HS chapter structure |
| pc_agent_tasks | **N** | 3 | 4 | 7 | Agent queue |
| classifications | Y | 5 | 1 | 6 | Old classification records |
| system_metadata | **N** | 1 | 5 | 6 | System state |
| tracker_container_status | Y | 5 | 1 | 6 | Container tracking |
| tracker_observations | **N** | 5 | 1 | 6 | Email observations |
| session_backups | **N** | 2 | 3 | 5 | Session persistence |
| inbox | **N** | 3 | 2 | 5 | Email inbox |

### 7.3 Core Data Collections (registered and active)

| Collection | Docs | Written By | Read By | Purpose |
|-----------|------|-----------|---------|---------|
| `tariff` | 11,753+ | seed scripts | intelligence, tool_executors, elimination_engine | HS codes + descriptions |
| `chapter_notes` | 99 | parse_chapter_notes_c2 | tool_executors, elimination_engine, verification_engine | Chapter preambles/exclusions |
| `tariff_structure` | 137 | seed_tariff_structure | tool_executors, elimination_engine | Section/chapter mapping |
| `classification_directives` | 218 | enrich_directives_c6 | tool_executors | Shaarolami directives |
| `framework_order` | 85 | seed_framework_order_c5 | tool_executors | FTA definitions + amendments |
| `free_import_order` | 6,121 | seed_free_import_order_c3 | tool_executors | Import regulatory requirements |
| `free_export_order` | 979 | seed_free_export_order_c4 | tool_executors | Export regulatory requirements |
| `legal_knowledge` | 19 | seed_legal_knowledge_c8 | tool_executors | Customs ordinance + reforms |
| `keyword_index` | 8,120+ | nightly_learn, seed_keywords_b2 | intelligence | Keyword search |
| `brain_index` | 5,001+ | overnight_brain | intelligence | Master knowledge index |
| `knowledge_base` | 305+ | overnight_brain, knowledge_query | intelligence, tool_executors | Knowledge articles |
| `classification_knowledge` | varies | classification_agents, overnight_brain | tool_executors, pupil | Classification results |

### 7.4 Tracker Collections

| Collection | Written By | Read By | Purpose |
|-----------|-----------|---------|---------|
| `tracker_deals` | tracker.py | tracker.py, main.py, port_intelligence | One per BL/AWB deal |
| `tracker_container_status` | tracker.py | tracker.py, tracker_email | Per-container per deal |
| `tracker_timeline` | tracker.py | tracker.py | Event log per deal |
| `tracker_observations` | tracker.py | tracker.py | Per-email dedup |
| `tracker_awb_status` | air_cargo_tracker | air_cargo_tracker | Air cargo tracking |

### 7.5 Cache Collections (18 external API caches)

| Collection | TTL | Source API |
|-----------|-----|-----------|
| `wikipedia_cache` | 30 days | Wikipedia REST API |
| `wikidata_cache` | 30 days | Wikidata API |
| `country_cache` | 30 days | restcountries.com |
| `currency_rates` | 24 hours | open.er-api.com |
| `comtrade_cache` | 7 days | UN Comtrade |
| `food_products_cache` | 30 days | Open Food Facts |
| `fda_products_cache` | 30 days | FDA API |
| `boi_rates` | 6 hours | Bank of Israel |
| `pubchem_cache` | 90 days | NIH PubChem |
| `eu_taric_cache` | 30 days | EU TARIC |
| `usitc_cache` | 30 days | US HTS |
| `cbs_trade_cache` | 30 days | CBS Israel |
| `barcode_cache` | 60 days | Open Food Facts barcode |
| `wco_notes_cache` | 180 days | WCO |
| `unctad_country_cache` | 90 days | UNCTAD |
| `beauty_products_cache` | 30 days | Open Beauty Facts |
| `crossref_cache` | 90 days | CrossRef |
| `sanctions_cache` | 24 hours | OpenSanctions |
| `israel_tax_cache` | 7 days | gov.il |
| `route_cache` | 24 hours | ORS/OSRM |
| `image_patterns` | 180 days | AI vision results |

### 7.6 Operational Collections

| Collection | Written By | Read By | Purpose |
|-----------|-----------|---------|---------|
| `rcb_processed` | main.py | main.py | Email processing marker |
| `rcb_logs` | various | rcb_inspector, overnight_audit | Operational logs |
| `rcb_classifications` | classification_agents | main.py, overnight_brain | Classification results |
| `email_quality_log` | rcb_helpers | — | Gate decisions + dedup |
| `security_log` | main.py, rcb_helpers | — | Security events |
| `elimination_log` | elimination_engine | — | Audit trail |
| `cross_check_log` | cross_checker | — | Cross-check results |
| `regression_alerts` | overnight_brain | — | Classification regressions |
| `questions_log` | email_intent | email_intent | Q&A cache + rate limit |
| `system_instructions` | email_intent | email_intent | Admin directives |
| `brain_run_progress` | overnight_brain | overnight_brain | Crash recovery checkpoints |

---

## 8. CODEBASE METRICS

### 8.1 Summary Dashboard

| Metric | Value |
|--------|-------|
| **Total app Python lines** | **89,556** |
| Library code lines | 62,455 |
| Test code lines | 11,150 |
| Script/tool lines | 15,729 |
| main.py lines | 2,352 |
| Library files | 71 |
| Test files | 23 |
| Script files | 53 |
| Files > 2,000 lines | 8 |
| Files > 1,000 lines | 20 |
| Cloud Functions | 27+ |
| Firestore collections (total unique) | ~167 |
| Firestore collections (registered) | 82 |
| Tools in engine | 33 |
| AI models used | 3 (Claude, Gemini, ChatGPT) |
| Git commits (Feb 16-19) | ~60 |
| Most-changed file | classification_agents.py (52 changes) |
| Test suite | 968 passed, 5 failed (BS4), 2 skipped |
| Test-to-code ratio | 17.9% |
| Backup/dead files | 10 (~568 KB) |
| Duplicate functions | 31 instances |
| Dead modules | 3-4 confirmed |
| Monthly AI cost (est.) | $325-425 |
| Overnight budget cap | $3.50/run |

### 8.2 Git File Change Hotspots (Top 20)

| Changes | File | Risk |
|---------|------|------|
| 52 | `classification_agents.py` | **CRITICAL** |
| 46 | `main.py` | HIGH |
| 36 | `tracker.py` | HIGH |
| 35 | `CLAUDE.md` | LOW |
| 21 | `librarian_index.py` | MEDIUM |
| 19 | `tool_executors.py` | MEDIUM |
| 15 | `.github/workflows/deploy.yml` | LOW |
| 14 | `tool_definitions.py` | MEDIUM |
| 12 | `rcb_helpers.py` | MEDIUM |
| 11 | `test_tool_calling.py` | LOW |
| 11 | `tracker_email.py` | MEDIUM |
| 10 | `tool_calling_engine.py` | MEDIUM |
| 8 | `self_learning.py` | MEDIUM |
| 8 | `overnight_brain.py` | MEDIUM |
| 8 | `intelligence.py` | MEDIUM |
| 8 | `document_parser.py` | MEDIUM |
| 7 | `librarian.py` | MEDIUM |
| 6 | `elimination_engine.py` | MEDIUM |

### 8.3 Top 5 Action Items (Priority Order)

1. **Wire Identity Graph** (Session 46 -- built but not connected to live pipeline)
2. **Add unit tests** for 8 high-risk untested modules (elimination_engine, tracker, tool_executors, ocean_tracker, self_learning, intelligence, cross_checker, document_parser)
3. **Register 85 missing Firestore collections** in librarian_index COLLECTION_FIELDS
4. **Clean up** -- delete 10 backup files, 3 disabled stubs, dead modules (~15,000 lines recoverable)
5. **Upgrade Gemini to paid tier** -- free tier causes daily 429s, forcing expensive Claude fallback

### 8.4 Cleanup Opportunities Summary

| Opportunity | Lines Saved | Effort | Priority |
|-------------|------------|--------|----------|
| Create shared_utils.py (31 duplicates) | ~800 | 1 day | HIGH |
| Remove dead modules (3-4 files) | ~1,500 | 2 hours | HIGH |
| Delete backup files (10 files) | ~568 KB | 15 min | LOW |
| Delete one-time scripts (~23) | ~2,131 | 30 min | LOW |
| Remove disabled monitor stubs | ~30 | 15 min | LOW |
| Consolidate librarian ecosystem | ~200 | 2 hours | MEDIUM |
| Merge read_document.py | ~118 | 1 hour | MEDIUM |
| **Total potential** | **~15,000+ lines** | **3-4 days** | — |

---

## END OF AUDIT REPORT
**Generated: 2026-02-20 | Session 50 | READ ONLY -- no files modified during audit**
**Next session should reference this file for context.**
