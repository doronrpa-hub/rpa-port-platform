# RCB SYSTEM — SESSION 21 FULL AUDIT & INVENTORY
## Date: February 15, 2026
## Purpose: Complete system state for continuity between Claude sessions

---

## 1. SYSTEM OVERVIEW

**RCB (Robot Customs Broker)** — AI-powered customs classification system for R.P.A.PORT LTD.
- **GCP Project:** rpa-port-customs
- **Region:** us-central1
- **Email:** rcb@rpa-port.co.il (Microsoft Graph API)
- **Repo:** github.com / rpa-port-platform
- **CI/CD:** GitHub Actions → Firebase Cloud Functions

---

## 2. DEPLOYED CLOUD FUNCTIONS (main.py — 1,578 lines)

| # | Function | Schedule | Status | What it does |
|---|----------|----------|--------|-------------|
| 1 | `check_email_scheduled` | every 5 min | DISABLED | Old Gmail IMAP fallback, replaced by rcb_check_email |
| 2 | `on_new_classification` | Firestore trigger | ACTIVE | Auto-suggests HS code from knowledge when new doc arrives |
| 3 | `on_classification_correction` | Firestore trigger | ACTIVE | Learns when user corrects a classification |
| 4 | `enrich_knowledge` | every 1 hour | ACTIVE | Runs EnrichmentAgent — tags downloads, checks enrichment tasks |
| 5 | `api` | HTTP | ACTIVE | REST API: stats, classifications, knowledge, inbox, sellers, learning |
| 6 | `rcb_api` | HTTP | ACTIVE | RCB API: health, logs, test, backup CRUD |
| 7 | `rcb_check_email` | every 2 min | ACTIVE | **MAIN PIPELINE** — Graph API email check + classification |
| 8 | `monitor_agent` | every 5 min | ACTIVE | Auto-fixes stuck queue, retries failed |
| 9 | `rcb_cleanup_old_processed` | every 24h | ACTIVE | Deletes rcb_processed docs older than 7 days |
| 10 | `rcb_retry_failed` | every 6h | ACTIVE | Retries failed classifications from last 24h |
| 11 | `rcb_health_check` | every 1h | ACTIVE | System health check (alerts disabled) |
| 12 | `monitor_self_heal` (x2) | HTTP | DISABLED | Dead code, consolidated |
| 13 | `monitor_fix_all` | HTTP | DISABLED | Dead code, consolidated |
| 14 | `monitor_fix_scheduled` | every 5 min | DISABLED | Dead code, consolidated |
| 15 | `test_pdf_ocr` | HTTP | ACTIVE | Test endpoint for PDF extraction |
| 16 | `test_pdf_report` | HTTP | ACTIVE | Test endpoint for PDF report generation |
| 17 | `monitor_agent_manual` | HTTP | ACTIVE | Manual trigger for monitor |

**NOT wired into main.py:** pupil.py, tracker.py, brain_commander.py

---

## 3. LIB MODULES — COMPLETE INVENTORY (32 files)

### Core Pipeline (WORKING, DEPLOYED)
| File | Lines | Size | What it does |
|------|-------|------|-------------|
| classification_agents.py | ~1,633 | 75K | 6-agent classification pipeline (Claude + Gemini) |
| intelligence.py | ~1,363 | 80K | Pre-classification brain, FIO API, regulatory lookup |
| rcb_helpers.py | ~700 | 32K | Graph API, PDF extraction, Hebrew names |
| rcb_email_processor.py | ~300 | 14K | Smart email processing, dedup, ack |
| rcb_id.py | ~50 | 2.1K | Sequential RCB-{date}-{seq}-{type} IDs |

### Knowledge System (WORKING, DEPLOYED)
| File | Lines | Size | What it does |
|------|-------|------|-------------|
| librarian.py | ~600 | 36K | Central knowledge search during classification |
| librarian_index.py | ~350 | 16K | Document indexing and inventory |
| librarian_researcher.py | ~700 | 48K | Continuous knowledge enrichment |
| librarian_tags.py | ~1,800 | 90K | Full Israeli customs/trade document tagging |
| knowledge_query.py | ~700 | 34K | Handles team knowledge questions via email |
| enrichment_agent.py | ~500 | 31K | PC Agent integration for browser downloads |

### Document Processing (WORKING, DEPLOYED)
| File | Lines | Size | What it does |
|------|-------|------|-------------|
| document_parser.py | ~900 | 42K | Per-document type ID and field extraction (regex) |
| document_tracker.py | ~700 | 32K | Shipment phase tracking from documents |
| invoice_validator.py | ~350 | 15K | Invoice validation per Israeli customs regs |
| pdf_creator.py | ~200 | 8.1K | Hebrew RTL PDF classification reports |
| product_classifier.py | ~600 | 32K | Product type detection + required docs |
| incoterms_calculator.py | ~600 | 28K | CIF calculator + missing document detection |

### Communication & Language (WORKING, DEPLOYED)
| File | Lines | Size | What it does |
|------|-------|------|-------------|
| language_tools.py | ~1,800 | 88K | Hebrew/English vocab, spell-check, style learning |
| clarification_generator.py | ~600 | 29K | Professional Hebrew requests for missing info |
| smart_questions.py | ~500 | 24K | Smart clarification questions from classification |
| tracker_email.py | ~316 | 12K | Visual HTML emails with progress bars |

### Verification & Testing (WORKING, DEPLOYED)
| File | Lines | Size | What it does |
|------|-------|------|-------------|
| verification_loop.py | ~400 | 20K | Post-classification HS verification + caching |
| rcb_self_test.py | ~500 | 25K | Self-test engine: sends test emails, verifies |
| rcb_inspector.py | ~1,400 | 71K | System health + intelligence agent |

### Orchestration (WORKING, DEPLOYED)
| File | Lines | Size | What it does |
|------|-------|------|-------------|
| rcb_orchestrator.py | ~350 | 15K | Integration layer connecting all modules |
| pc_agent.py | ~500 | 23K | Browser-based file download/upload |
| nightly_learn.py | ~200 | 8.4K | Nightly pipeline: builds indexes from collections |

### NEW AGENTS — IN REPO BUT NOT WIRED (committed 2026-02-15)
| File | Lines | Size | What it does |
|------|-------|------|-------------|
| pupil.py | ~2,500 | 104K | Phase A+B+C learning: Observer, Student, Auditor |
| tracker.py | ~1,472 | 61K | Deal-centric tracking + TaskYam API client |
| brain_commander.py | ~900 | 40K | Father channel (doron@ commands) + auto-improve |

---

## 4. FIRESTORE COLLECTIONS — 67 TOTAL

### Critical (Core Pipeline)
- **inbox** — Incoming emails queue
- **rcb_processed** — Dedup tracking (prevents reprocessing)
- **rcb_classifications** — Classification results (the output)
- **classifications** — Auto-classify pending queue
- **knowledge_base** — Central learned knowledge (296 docs)
- **classification_knowledge** — HS codes + products (mined)

### Knowledge Indexes
- **keyword_index** — 8,013+ keyword→HS mappings
- **product_index** — 61+ product→HS mappings
- **supplier_index** — Supplier→HS mappings
- **brain_index** — 11,254 keywords from ALL collections
- **librarian_index** — 12,595 document index
- **hs_code_index** — HS code reference
- **tariff** — 11,753 tariff entries
- **tariff_chapters** — Chapter-level data
- **ministry_index** — Ministry classification data

### Reference Data
- **classification_rules** (26), **regulatory_requirements** (28), **fta_agreements** (21)
- **sellers**, **buyers**, **contacts**, **people**, **users**
- **shipping_lines**, **document_types**, **legal_requirements**, **licensing_knowledge**

### Tracker System (NOT YET ACTIVE)
- **tracker_deals** — One per BL/AWB deal
- **tracker_observations** — Per-email dedup for tracker
- **tracker_container_status** — Per container per deal
- **tracker_timeline** — Event log per deal

### Brain Commander (NOT YET ACTIVE)
- **brain_commands** — Father channel commands
- **brain_missions** — Learning missions
- **brain_improvements** — Auto-improvement log
- **brain_email_styles** — Email style learning
- **brain_daily_digest** — Daily digest entries

### Pupil System (NOT YET ACTIVE)
- **pupil_observations**, **pupil_corrections**, **pupil_reviews**
- **pupil_budget**, **pupil_audit_summaries**
- **enrichment_tasks** — Task queue for enrichment

### System
- **system_status**, **system_metadata**, **system_state**, **system_counters**
- **rcb_logs**, **rcb_inspector_reports**, **learning_log**, **monitor_errors**
- **session_backups**, **sessions_backup**, **session_missions**
- **pc_agent_tasks**, **agent_tasks**, **pending_tasks**
- **batch_reprocess_results**, **batch_reprocess_summary**
- **free_import_cache**, **verification_cache**

---

## 5. TASKYAM INTEGRATION (in tracker.py)

### API Details
- **Production URL:** `https://taskyam.israports.co.il/TaskYamWebAPI/`
- **Pilot URL:** `https://pilot.israports.co.il/TaskYamWebAPI/`
- **Auth:** Session token via `POST /api/Account/Login`
- **Credentials:** Stored in Secret Manager as `TASKYAM_USERNAME`, `TASKYAM_PASSWORD`
- **Header:** `X-Session-Token: {token}`

### Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `api/Account/Login` | POST | Get session token |
| `api/Account/Logout` | POST | Release session |
| `api/ContainerStatus/GetCargoStatus` | GET | Main container tracking |
| `api/ContainerStatus/AddCargoNotification` | POST | Register push notifications |
| `api/CommunityTables/GetShipDetails` | GET | Ship details lookup |
| `api/CommunityTables/GetShippingCompanies` | GET | Shipping company lookup |

### Port Codes
- חיפה (Haifa) → ILHFA
- אשדוד (Ashdod) → ILASD
- אילת (Eilat) → ILELT
- חדרה (Hadera) → ILHDR

### Process Steps Tracked
**Import (9 steps):** Manifest → Port Unloading → Delivery Order → Customs Check → Customs Release → Port Release → Escort Certificate → Cargo Exit Request → Cargo Exit

**Export (9 steps):** Storage ID → Port Storage Feedback → Storage to Customs → Driver Assignment → Customs Check → Customs Release → Cargo Entry → Cargo Loading → Ship Sailing

---

## 6. MULTI-MODEL AI STRATEGY

| Model | Use | Cost |
|-------|-----|------|
| Gemini Flash | Agents 1,3,4,5 (extraction, regulatory, FTA, risk) | ~$0.001/call |
| Claude Sonnet 4.5 | Agent 2 (HS classification — best reasoning) | ~$0.04/call |
| Gemini Pro | Agent 6 (synthesis in Hebrew) | ~$0.005/call |
| ChatGPT | Cross-check on low confidence (NOT YET IMPLEMENTED) | ~$0.002-0.01/call |

---

## 7. CI/CD PIPELINES (3 GitHub Actions)

| Workflow | Trigger | Steps |
|----------|---------|-------|
| deploy.yml | push to main | test → deploy to Firebase |
| test.yml | push to main | pytest functions/tests/ |
| overnight-learn.yml | 22:00 UTC daily | read_everything.py → deep_learn.py |

---

## 8. WHAT IS WORKING (DEPLOYED & ACTIVE)

1. **Email checking** — rcb_check_email runs every 2 min via Graph API
2. **6-agent classification pipeline** — Full chain: extract → classify → regulatory → FTA → risk → synthesize
3. **Knowledge queries** — Team members can ask questions, get AI answers
4. **Pre-classification brain check** — Searches keyword_index (8,013), product_index (61), supplier_index
5. **Free Import Order API** — gov.il integration with 7-day cache
6. **Learning from corrections** — on_classification_correction learns HS+seller+product
7. **Enrichment hourly** — enrich_knowledge calls EnrichmentAgent
8. **Document parsing** — 9 doc types with regex extraction
9. **PDF extraction** — pdfplumber → pypdf → Vision OCR at 300 DPI
10. **Nightly learning** — GitHub Actions runs read_everything + deep_learn at 22:00 UTC
11. **Monitor agent** — Queue cleanup, retry failed, health check
12. **REST API** — Stats, classifications, knowledge, inbox endpoints
13. **Hebrew classification emails** — HTML formatted with all 6 agent results
14. **RCB ID system** — Sequential IDs per type (classification, knowledge query)
15. **Self-test engine** — Can send test emails and verify results

---

## 9. WHAT IS NOT WORKING (CODE EXISTS, NOT WIRED)

### A. Pupil Agent (pupil.py — 104K, in repo but not called)
- Phase A: Observer — reads all emails, extracts knowledge
- Phase B: Student — challenges brain, finds gaps
- Phase C: Auditor — sends corrections to doron@ for review
- **What's needed:** Add scheduler function in main.py to call pupil periodically

### B. Tracker Agent (tracker.py — 61K, in repo but not called)
- Deal-centric tracking via BL/AWB
- TaskYam API client for port operations
- Visual progress bar emails via tracker_email.py
- **Has 6 patches applied but NOT COMMITTED** (from this session):
  - _derive_current_step None crash fix
  - Step 8 email on created AND updated deals
  - Conversation thread matching (Priority 0) + AWB matching (Priority 1b)
  - _send_tracker_email accepts observation + extractions params
  - Duplicate function removal
  - AWB number populated from extractions
- **What's needed:** Commit patches, add Cloud Function in main.py

### C. Brain Commander (brain_commander.py — 40K, in repo but not called)
- Father channel: doron@ emails commands to brain
- Auto-improve: learns from industry email styles
- Learning missions: dispatches research agents
- **What's needed:** Add Cloud Function in main.py

### D. CC Silent Classification
- fix_silent_classify.py exists in Downloads but not applied
- CC emails to rcb@ should be classified silently (no reply sent)
- Currently main.py skips CC emails entirely (is_direct check at line 1072)

### E. Self-Learning Agent
- Described in knowledge doc but FILE NEVER EXISTED
- Functionality partially covered by nightly_learn.py + pupil.py
- brain_commander.py covers auto-improve aspect

### F. doc_reader.py (Template Learning Engine)
- Exists in Downloads (22K), NOT in repo
- Reads documents structurally, learns templates, extracts without LLM
- Would reduce AI costs by learning known document formats

### G. rcb_unified_reply.py (Consolidated Email)
- Exists in Downloads (46K), NOT in repo
- One email thread per shipment combining classification + tracking + knowledge
- Supports both Sea (BOL) and Air (AWB) modes

---

## 10. FILES IN DOWNLOADS NOT IN REPO (potential additions)

| File | Size | Date | What it does | Priority |
|------|------|------|-------------|----------|
| rcb_unified_reply.py | 46K | Feb 10 | Unified email composer (sea+air) | HIGH |
| doc_reader.py | 22K | Feb 10 | Template learning doc reader | HIGH |
| classification_agents.py | 43K | Feb 11 | **NEWER** version with Session 15 optimizations | CHECK |
| main (2).py | 72K | Feb 9 | Newer main.py variant | CHECK |
| backfill_inbox.py | 8K | Feb 10 | Batch learn from historical inbox | MEDIUM |
| backfill_learning.py | 7.5K | Feb 10 | Train brain from all historical emails | MEDIUM |
| gov_data_sources.py | 44K | Feb 1 | Israeli gov data downloader | LOW |
| store_broker_knowledge.py | 27K | Feb 1 | Regulatory knowledge loader | LOW |
| rpa_master.py | 31K | Feb 1 | Master orchestrator (standalone) | LOW |
| FILE_03_...RULES.py | 31K | Jan 26 | 48 classification rules as code | REFERENCE |

### Fix/Patch Files (all Feb 10):
- fix_brain_patches.py, fix_brain_prompt.py, fix_brain_prompt2.py
- fix_classification_display.py, fix_duplicate_email.py
- fix_father_final.py, fix_hs_elimination.py
- fix_silent_classify.py, fix_subject_line.py, fix_tariff_desc.py
- patch_doc_reader_v2.py, patch_main_brain.py

---

## 11. UNCOMMITTED CHANGES (as of Feb 15)

**functions/lib/tracker.py** — 6 bug fix patches applied:
1. `_derive_current_step` None crash fix (import_proc/export_proc)
2. Step 8 emails on both created AND updated deals
3. Conversation thread matching (Priority 0) + AWB matching (Priority 1b)
4. `_send_tracker_email` accepts observation + extractions parameters
5. Removed duplicate `_send_tracker_email` function
6. AWB number populated from extractions

---

## 12. WIRING PLAN STATUS (from docs/WIRING_PLAN.md)

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 0 | Improve PDF extraction (OCR, tables, Hebrew) | NOT STARTED |
| Phase 1 | Build librarian_index (one-time rebuild) | DONE (12,595 docs) |
| Phase 2 | Wire learning into classification pipeline | PARTIALLY DONE (enrich_knowledge is real) |
| Phase 3 | Replace dummy enrich_knowledge | DONE (already real in main.py) |
| Phase 4 | Research execution (PC Agent + Gemini + Web) | NOT STARTED |
| Phase 5 | Wire Pupil + Tracker + Brain Commander | IN PROGRESS (files in repo, not wired) |

---

## 13. KNOWN ISSUES

1. **main.py has duplicate function decorator** at line 912 (orphaned @https_fn.on_request before rcb_api)
2. **monitor_self_heal defined TWICE** (lines 1438 and 1446) — second overrides first
3. **7 dead/disabled functions** in main.py consuming deploy quota
4. **2-hour email window** (line 1039) — temporary fix, should be reverted to 2 days
5. **CC emails skipped entirely** — should be silently classified
6. **No exponential backoff** on Gemini 429 rate limits
7. **HS code format** — displays raw 84314390 instead of Israeli format 84.31.4390.00/0
8. **brain_index vs keyword/product/supplier_index** — dual indexing architecture, some overlap

---

## 14. SECRETS IN GCP SECRET MANAGER

Required secrets (referenced in code):
- `ANTHROPIC_API_KEY` — Claude Sonnet for Agent 2
- `GEMINI_API_KEY` — Gemini Flash/Pro for Agents 1,3,4,5,6
- `RCB_GRAPH_CLIENT_ID` — Microsoft Graph API
- `RCB_GRAPH_CLIENT_SECRET` — Microsoft Graph API
- `RCB_GRAPH_TENANT_ID` — Microsoft Graph API
- `RCB_EMAIL` — rcb@rpa-port.co.il
- `RCB_FALLBACK_EMAIL` — airpaort@gmail.com
- `TASKYAM_USERNAME` — TaskYam API (not yet in use)
- `TASKYAM_PASSWORD` — TaskYam API (not yet in use)
- `OPENAI_API_KEY` — ChatGPT cross-check (NOT YET ADDED)

---

## 15. NEXT STEPS (Priority Order)

1. **Commit tracker.py patches** (6 bug fixes already applied)
2. **Compare Downloads classification_agents.py** (Feb 11) vs repo version — may be newer
3. **Wire pupil.py into main.py** — add scheduler function
4. **Wire tracker.py into main.py** — add scheduler function + observation from email pipeline
5. **Wire brain_commander.py into main.py** — add father channel check
6. **Add doc_reader.py to repo** — template learning engine
7. **Add rcb_unified_reply.py to repo** — unified email composer
8. **Enable CC silent classification** — modify is_direct check in rcb_check_email
9. **Clean up dead functions** from main.py
10. **Add OPENAI_API_KEY** + wire ChatGPT cross-check
