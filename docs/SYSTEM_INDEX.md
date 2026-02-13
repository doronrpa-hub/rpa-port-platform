# RCB System Index
## Complete inventory of every file, function, collection, and integration
## Last updated: Session 19 (February 13, 2026)
## Built by: Claude Code (reading actual code + querying Firebase live)

---

## Table of Contents

1. [Library Modules (functions/lib/)](#1-library-modules-functionslib)
2. [Cloud Functions (functions/main.py)](#2-cloud-functions-functionsmainpy)
3. [Standalone Scripts (functions/)](#3-standalone-scripts-functions)
4. [Firestore Collections](#4-firestore-collections)
5. [External API Integrations](#5-external-api-integrations)
6. [Data Flow: Email Pipeline](#6-data-flow-email-pipeline)
7. [Files NOT in Repo](#7-files-not-in-repo)
8. [Dead Code / Patch Files](#8-dead-code--patch-files)
9. [Firebase Session History](#9-firebase-session-history)
10. [System Health](#10-system-health)

---

## 1. Library Modules (functions/lib/)

### __init__.py (229 lines)
- **Purpose:** Exports from all lib modules. Version 4.1.0.
- **Status:** WORKING. All imports wrapped in try/except (safe deploy).
- **Exports from:** clarification_generator, invoice_validator, rcb_orchestrator, rcb_email_processor, classification_agents, rcb_helpers, librarian, librarian_index, librarian_tags, librarian_researcher, enrichment_agent, document_tracker, incoterms_calculator, product_classifier, pdf_creator, pc_agent, knowledge_query

### classification_agents.py (1,633 lines) -- THE CORE
- **Purpose:** 6-agent AI classification pipeline + email building + report sending
- **Status:** WORKING AND WIRED (called from main.py rcb_check_email)
- **Key functions:**
  - `call_claude()` :250 -- Anthropic API call
  - `call_gemini()` :282 -- Google Gemini API call (strips markdown fences)
  - `call_gemini_fast()` :332 -- Gemini Flash shortcut
  - `call_gemini_pro()` :337 -- Gemini Pro shortcut
  - `call_ai()` :342 -- Tier-based routing (fast=Gemini Flash, pro=Gemini Pro, claude=Claude)
  - `_try_parse_agent1()` :410 -- JSON parser with incomplete-JSON detection
  - `run_document_agent()` :430 -- **Agent 1**: Extract products (Gemini Flash -> Claude fallback, 4096 tokens)
  - `run_classification_agent()` :480 -- **Agent 2**: Classify HS codes (Claude Sonnet)
  - `run_regulatory_agent()` :506 -- **Agent 3**: Regulatory check (Gemini Flash)
  - `run_fta_agent()` :526 -- **Agent 4**: FTA check (Gemini Flash)
  - `run_risk_agent()` :545 -- **Agent 5**: Risk assessment (Gemini Flash)
  - `run_synthesis_agent()` :566 -- **Agent 6**: Hebrew synthesis (Gemini Pro)
  - `run_full_classification()` :598 -- Full pipeline orchestration
  - `_retry_classification()` :984 -- Retry Agent 2 on failure
  - `audit_before_send()` :994 -- Quality gate (catches garbage HS codes)
  - `build_classification_email()` :1133 -- HTML email builder
  - `build_excel_report()` :1306 -- Excel attachment builder
  - `process_and_send_report()` :1399 -- End-to-end: extract -> classify -> email (consolidated)
- **Calls:** intelligence.py (pre_classify, lookup_regulatory, lookup_fta, validate_documents, route_to_ministries, query_free_import_order), verification_loop.py, smart_questions.py, document_parser.py, librarian.py, rcb_helpers.py
- **API keys used:** ANTHROPIC_API_KEY, GEMINI_API_KEY
- **Firestore writes:** rcb_classifications, classification_knowledge
- **Firestore reads:** tariff, ministry_index, classification_rules

### intelligence.py (1,891 lines)
- **Purpose:** Brain pre-classification + regulatory/FTA lookup + document validation + ministry routing + Free Import Order API
- **Status:** WORKING AND WIRED (called from classification_agents.py)
- **Key functions:**
  - `pre_classify()` :23 -- Pre-classify from brain (keyword_index, product_index, supplier_index, classification_knowledge, tariff). Returns candidates with confidence scores.
  - `lookup_regulatory()` :223 -- Regulatory requirements by HS code
  - `lookup_fta()` :309 -- FTA agreement lookup by HS+country
  - `validate_documents()` :476 -- Check document completeness for import/export
  - `route_to_ministries()` :930 -- Route to Israeli ministries by HS chapter
  - `query_free_import_order()` :1089 -- gov.il Free Import Order API
  - `_query_fio_api()` :1180 -- Direct API call to data.gov.il
  - `_query_fio_parents()` :1269 -- Parent HS code fallback
  - `_search_keyword_index()` :1488 -- Brain keyword search
  - `_search_product_index()` :1549 -- Brain product search
  - `_search_supplier_index()` :1605 -- Brain supplier search
  - `_search_tariff()` :1652 -- Tariff DB search
  - `_search_classification_knowledge()` :1384 -- Past classifications search
  - `_search_classification_rules()` :1446 -- Rules search
- **Firestore reads:** keyword_index, product_index, supplier_index, classification_knowledge, classification_rules, tariff, tariff_chapters, regulatory_requirements, fta_agreements, ministry_index, free_import_cache
- **Firestore writes:** free_import_cache
- **External API:** data.gov.il Free Import Order (resource_id=a36db570...)

### rcb_helpers.py (809 lines)
- **Purpose:** Text extraction (PDF, Excel, Word, EML, MSG, images, URLs), Graph API helpers, Hebrew utilities
- **Status:** WORKING AND WIRED
- **Key functions:**
  - `extract_text_from_attachments()` :465 -- Main extraction entry point (9 file types)
  - `extract_text_from_pdf_bytes()` :147 -- PDF extraction (pdfplumber -> pypdf -> Vision OCR fallback)
  - `helper_get_graph_token()` :656 -- Microsoft Graph API OAuth token
  - `helper_graph_messages()` :673 -- Fetch emails from Graph
  - `helper_graph_attachments()` :685 -- Fetch attachments
  - `helper_graph_mark_read()` :694 -- Mark email as read
  - `helper_graph_send()` :702 -- Send email via Graph (supports In-Reply-To/References threading)
  - `to_hebrew_name()` :753 -- Convert English name to Hebrew
  - `get_rcb_secrets_internal()` :643 -- Load all secrets
- **External API:** Microsoft Graph API (emails, attachments, send)
- **Secrets used:** GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, GRAPH_TENANT_ID, GRAPH_REFRESH_TOKEN

### document_parser.py (1,219 lines)
- **Purpose:** Identify and parse 9 document types with structured field extraction
- **Status:** WORKING AND WIRED (called from classification_agents.py process_and_send_report)
- **Document types:** invoice, packing_list, bill_of_lading, awb, certificate_of_origin, eur1, health_certificate, insurance_certificate, delivery_order
- **Key functions:**
  - `identify_document_type()` :296 -- Classify document by content patterns
  - `extract_structured_fields()` :386 -- Extract fields per doc type
  - `assess_document_completeness()` :931 -- Score 0-100 with missing fields
  - `parse_document()` :1022 -- Combined identify+extract+score
  - `parse_all_documents()` :1050 -- Parse all attachments

### librarian.py (962 lines)
- **Purpose:** Knowledge search engine across 7 collection groups
- **Status:** WORKING AND WIRED (called from classification_agents.py)
- **Key functions:**
  - `full_knowledge_search()` :240 -- Search all 7 groups (tariff, regulations, procedures, knowledge, history, ministry, FTA)
  - `build_classification_context()` :490 -- Build context string for AI agents
  - `validate_hs_code()` :332 -- Validate HS code against tariff DB
  - `validate_and_correct_classifications()` :454 -- Batch validate
  - `get_israeli_hs_format()` :316 -- Format HS code (basic, not full Israeli format)
  - `smart_search()` :717 -- Keyword-based search
  - `find_by_hs_code()` :552 -- Direct HS lookup across all collections
  - `_log_search()` :949 -- Log to librarian_search_log
- **Firestore reads:** tariff, regulatory_requirements, classification_rules, knowledge_base, rcb_classifications, classification_knowledge, ministry_index, fta_agreements
- **Firestore writes:** librarian_search_log

### verification_loop.py (456 lines)
- **Purpose:** Verify HS codes against tariff DB, calculate purchase tax
- **Status:** WORKING AND WIRED (called from classification_agents.py)
- **Key functions:**
  - `verify_hs_code()` :77 -- Verify single HS code
  - `verify_all_classifications()` :177 -- Verify all in batch
  - `learn_from_verification()` :248 -- Store verified result in classification_knowledge
  - `_get_purchase_tax()` :307 -- Lookup purchase tax rate
  - `_format_hs_dots()` :448 -- Format HS with dots
- **Firestore reads:** tariff, verification_cache
- **Firestore writes:** verification_cache, classification_knowledge

### smart_questions.py (569 lines)
- **Purpose:** Generate clarification questions when classification is ambiguous
- **Status:** WORKING AND WIRED (called from classification_agents.py)
- **Key functions:**
  - `analyze_ambiguity()` :56 -- Detect ambiguity in classifications
  - `generate_smart_questions()` :241 -- Build targeted questions
  - `should_ask_questions()` :426 -- Decision: ask or not
  - `format_questions_html()` :510 -- HTML formatting for email

### document_tracker.py (839 lines)
- **Purpose:** Track shipment progress through 9 import + 9 export steps
- **Status:** IN REPO, NOT ACTIVELY WIRED into email pipeline
- **Classes:** ShipmentPhase, ProductCategory, DocumentType, Incoterm, TransportMode, Document, ClarificationRequest, DocumentTracker
- **Key functions:**
  - `create_tracker()` :624 -- Create new tracker instance
  - `_derive_current_step()` :697 -- Derive step from docs (has None bug -- fix_tracker_crash.py patches this)
  - `feed_parsed_documents()` :715 -- Feed documents to tracker
- **Note:** Has a known None bug in `_derive_current_step()` when import_proc or export_proc is None

### tracker_email.py (316 lines)
- **Purpose:** Build TaskYam-style HTML progress bar emails per container
- **Status:** IN REPO (committed in Session 18), NOT WIRED into pipeline
- **Key functions:**
  - `build_tracker_status_email()` :10 -- Main email builder
  - `_get_steps()` :79 -- Get import/export step definitions
  - `_summarize_steps()` :83 -- Summarize container statuses
  - `_build_html()` :129 -- Build HTML progress bar

### enrichment_agent.py (731 lines)
- **Purpose:** Background enrichment orchestrator
- **Status:** IN REPO, WIRED in Session 18 but execution uncertain
- **Class:** EnrichmentAgent (manages enrichment pipeline)
- **Firestore reads:** enrichment_tasks, pending_tasks
- **Firestore writes:** enrichment_tasks, knowledge_base

### knowledge_query.py (899 lines)
- **Purpose:** Detect and answer team knowledge questions (auto-reply)
- **Status:** WORKING AND WIRED (called from main.py rcb_check_email, Session 13)
- **Key functions:**
  - `detect_knowledge_query()` :309 -- Is this a team question?
  - `handle_knowledge_query()` :783 -- Full flow: detect -> parse -> gather -> reply
  - `gather_knowledge()` :417 -- Search all knowledge sources
  - `generate_reply()` :569 -- Build reply email

### language_tools.py (2,068 lines) -- LARGEST LIB FILE
- **Purpose:** Hebrew language processing, letter generation, style checking
- **Status:** IN REPO, PARTIALLY WIRED (Session 14: wired to classification_agents.py and rcb_email_processor.py)
- **Classes:** LetterType, Tone, LanguageRegister, CustomsVocabulary, HebrewLanguageChecker, LetterStructure, SubjectLineGenerator, StyleAnalyzer, TextPolisher, LanguageLearner, JokeBank
- **Key functions:**
  - `create_language_toolkit()` :1872 -- Bootstrap full toolkit
  - `build_rcb_subject()` :1944 -- Smart subject line builder
  - `build_html_report()` :2002 -- Report builder
  - `process_outgoing_text()` :2046 -- Polish outgoing text

### clarification_generator.py (781 lines)
- **Purpose:** Generate Hebrew clarification request emails (missing docs, classification questions, CIF completion, origin verification)
- **Status:** IN REPO, PARTIALLY WIRED
- **Key functions:**
  - `generate_missing_docs_request()` :318 -- Hebrew missing docs letter
  - `generate_classification_request()` :470 -- Classification clarification
  - `generate_cif_completion_request()` :532 -- CIF data request
  - `generate_origin_request()` :601 -- Origin verification

### rcb_email_processor.py (414 lines)
- **Purpose:** Smart email processing with language tools
- **Status:** IN REPO, WIRED (Session 14)
- **Class:** RCBEmailProcessor
- **Key functions:**
  - `create_processor()` :288 -- Factory
  - `build_ack_email()` :297 -- Acknowledgment email
  - `build_report_email()` :330 -- Classification report email
- **Firestore reads/writes:** system_state (language_learner persistence)

### rcb_orchestrator.py (408 lines)
- **Purpose:** High-level flow orchestration (shipment tracking integration)
- **Status:** IN REPO, NOT ACTIVELY CALLED from main.py
- **Classes:** ShipmentStage, ProcessingAction, ShipmentStatus, RCBOrchestrator
- **Key functions:**
  - `create_orchestrator()` :287 -- Factory
  - `process_and_respond()` :292 -- Full orchestration flow

### rcb_inspector.py (1,749 lines)
- **Purpose:** Daily system inspection, auto-fixes, session planning, email report
- **Status:** WORKING AND WIRED (daily scheduler + HTTP trigger)
- **Key functions:**
  - `run_full_inspection()` :1581 -- Full inspection pipeline
  - `consult_librarian()` :144 -- Check librarian health
  - `inspect_database()` :192 -- Audit Firestore collections
  - `inspect_processes()` :440 -- Check for race conditions, scheduler clashes
  - `inspect_flows()` :591 -- Check classification/knowledge/monitor flows
  - `inspect_monitors()` :774 -- Check monitor health
  - `run_auto_fixes()` :832 -- Auto-fix stuck classifications, stale processed
  - `plan_next_session()` :1077 -- Generate mission for next Claude session
  - `generate_report()` :1347 -- Build inspection report
  - `generate_email_html()` :1465 -- HTML report email
- **Firestore reads:** All major collections
- **Firestore writes:** rcb_inspector_reports, session_missions

### rcb_self_test.py (645 lines)
- **Purpose:** Self-test engine (detection, parsing, end-to-end tests)
- **Status:** WORKING AND WIRED (HTTP trigger)
- **Key functions:**
  - `run_all_tests()` :556 -- Run full test suite
  - `_run_detection_test()` :368 -- Test email detection
  - `_run_parse_test()` :394 -- Test document parsing
  - `_run_e2e_test()` :429 -- End-to-end email test

### librarian_index.py (467 lines)
- **Purpose:** Build librarian_index from all collections
- **Status:** IN REPO, called from enrichment flows
- **Key functions:**
  - `rebuild_index()` :250 -- Full index rebuild
  - `index_collection()` :191 -- Index single collection
  - `get_inventory_stats()` :332 -- Collection statistics
- **Firestore writes:** librarian_index (12,595 docs)

### librarian_researcher.py (1,181 lines)
- **Purpose:** 23 enrichment task definitions, learning from classifications/corrections/emails
- **Status:** IN REPO, PARTIALLY WIRED
- **Key functions:**
  - `learn_from_classification()` :715 -- Learn from new classification
  - `learn_from_correction()` :781 -- Learn from user correction
  - `learn_from_email()` :817 -- Learn from email content
  - `find_similar_classifications()` :945 -- Find similar past results
  - `get_web_search_queries()` :613 -- Generate web search queries (generates queries, CANNOT execute)
  - `schedule_enrichment()` :1029 -- Schedule enrichment task
- **Note:** Generates research queries but has no web execution capability (needs PC Agent)

### librarian_tags.py (1,714 lines)
- **Purpose:** Auto-tagging system for documents
- **Status:** IN REPO, WIRED (Session 12)
- **1,183 lines of tag definitions** (CUSTOMS_HANDBOOK_CHAPTERS, DOCUMENT_TAGS, TAG_HIERARCHY)
- **Key functions:**
  - `auto_tag_document()` :1184 -- Auto-tag a document
  - `suggest_related_tags()` :1269 -- Tag suggestions

### invoice_validator.py (381 lines)
- **Purpose:** Validate invoice fields against customs requirements
- **Status:** IN REPO, WIRED (called from classification_agents.py)
- **Key functions:**
  - `validate_invoice()` :248 -- Full validation
  - `quick_validate()` :307 -- Quick pass/fail with score

### incoterms_calculator.py (663 lines)
- **Purpose:** CIF/FOB/EXW calculation for customs valuation
- **Status:** IN REPO, available but not actively triggered
- **Classes:** Incoterm, TransportType, CIFComponents, CIFCalculation, IncotermsCalculator

### product_classifier.py (714 lines)
- **Purpose:** Alternative classification approach (not the main pipeline)
- **Status:** IN REPO, NOT WIRED into main pipeline
- **Class:** ProductClassifier

### pc_agent.py (623 lines)
- **Purpose:** Browser-based file downloads from government sites
- **Status:** IN REPO, NEVER TRIGGERED (0 tasks in pc_agent_tasks)
- **Key functions:**
  - `create_download_task()` :59 -- Create download task
  - `run_agent()` :450 -- Run download agent
  - `get_agent_script()` :524 -- Generate browser script

### pdf_creator.py (202 lines)
- **Purpose:** Generate PDF classification reports (Hebrew support)
- **Status:** IN REPO, available but PDF generation has issues locally
- **Key functions:**
  - `create_classification_pdf()` :98 -- Build PDF report

### rcb_id.py (68 lines)
- **Purpose:** Sequential RCB ID system (RCB-YYYYMMDD-NNN)
- **Status:** WORKING AND WIRED
- **Key functions:**
  - `generate_rcb_id()` :33 -- Generate next ID
  - `parse_rcb_id()` :58 -- Parse existing ID
- **Firestore reads/writes:** system_counters

---

## 2. Cloud Functions (functions/main.py — 1,708 lines)

### Active Schedulers
| Function | Schedule | Memory | What it does |
|----------|----------|--------|--------------|
| `check_email_scheduled` :166 | every 5 min | 1 GB | Legacy IMAP email check (disabled code inside) |
| `rcb_check_email` :1020 | every 2 min | 1 GB | **MAIN PIPELINE**: Graph API email check -> extract -> classify -> send |
| `monitor_agent` :1188 | every 5 min | default | Monitor system health, retry failures |
| `rcb_health_check` :1341 | every 1 hour | default | Health check, send alert if issues |
| `rcb_cleanup_old_processed` :1269 | every 24 hours | default | Clean up old rcb_processed entries |
| `rcb_retry_failed` :1296 | every 6 hours | default | Retry failed classifications |
| `enrich_knowledge` :509 | every 1 hour | 256 MB | Run enrichment agent |
| `rcb_inspector_daily` :1697 | every day 15:00 IST | 1 GB | Daily inspection + report email |
| `monitor_fix_scheduled` :1468 | Mon 08:00 IST | 1 GB | Weekly monitor fix (disabled) |

### HTTP Triggers
| Function | Path | What it does |
|----------|------|--------------|
| `api` :541 | /api/* | General API (legacy) |
| `graph_forward_email` :912 | /graph_forward_email | Forward email via Graph API (helper, not main flow) |
| `rcb_api` :934 | /rcb_api/* | **RCB API**: /api/classify, /api/status, /api/backup, /api/backups, /api/backup/{id}, /api/search, /api/health |
| `rcb_self_test` :1633 | /rcb_self_test | Run self-test suite |
| `rcb_inspector` :1667 | /rcb_inspector | Run inspection manually |
| `monitor_agent_manual` :1260 | /monitor_agent_manual | Manual monitor trigger |
| `test_pdf_ocr` :1476 | /test_pdf_ocr | Test PDF OCR pipeline |
| `test_pdf_report` :1550 | /test_pdf_report | Test PDF report generation |
| `monitor_self_heal` :1447 | /monitor_self_heal | Self-heal (disabled) |
| `monitor_fix_all` :1455 | /monitor_fix_all | Fix all (disabled) |

### Firestore Triggers
| Function | Trigger | What it does |
|----------|---------|--------------|
| `on_new_classification` :334 | classifications/{classId} created | Learn from new classification -> librarian_researcher |
| `on_classification_correction` :415 | classifications/{classId} updated | Learn from correction -> librarian_researcher |

### rcb_api Routes (inside rcb_api function)
- `POST /api/classify` -- Classify document via API
- `GET /api/status` -- System status
- `POST /api/backup` -- Save session backup to Firestore
- `GET /api/backups` -- List session backups (last 20)
- `GET /api/backup/{id}` -- Get specific backup
- `GET /api/search` -- Search knowledge
- `GET /api/health` -- Health check

---

## 3. Standalone Scripts (functions/)

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `batch_reprocess.py` | 1,063 | Reprocess ALL emails: Graph API mailbox scan -> extract -> classify -> learn | Run manually, 345 processed |
| `read_everything.py` | 1,138 | Build brain_index from ALL 29 collections -> 11,254 keywords | Run manually, writes brain_index + system_metadata |
| `deep_learn.py` | 905 | Mine professional docs: knowledge_base, declarations, rcb_classifications -> extract products/suppliers/keywords | Run manually, writes keyword_index + product_index + supplier_index |
| `enrich_knowledge.py` | 800 | Reclassify untyped knowledge_base, extract HS codes/products/suppliers | Run manually, writes knowledge_base + product_index + supplier_index |
| `knowledge_indexer.py` | 724 | Build inverted indexes: keyword_index (8,185), product_index (65), supplier_index (3) | Run manually, writes indexes |
| `import_knowledge.py` | 172 | Import baseline JSONs (FTA, regulatory, rules) into Firestore | Run once (Phase A) |

### Learning Pipeline (run order):
1. `enrich_knowledge.py` -- Reclassify + extract from knowledge_base
2. `deep_learn.py` -- Mine professional docs for products/suppliers/keywords
3. `knowledge_indexer.py` -- Build inverted indexes (keyword_index, product_index, supplier_index)
4. `read_everything.py` -- Build master brain_index from ALL collections

### overnight_learn.bat (planned, never ran):
```
enrich_knowledge.py -> deep_learn.py -> knowledge_indexer.py
```

---

## 4. Firestore Collections

### Queried live from Firebase on February 13, 2026:

#### Knowledge & Brain (the intelligence layer)
| Collection | Docs | What | Written by | Read by |
|------------|------|------|------------|---------|
| `brain_index` | 11,245 | Master keyword->HS index (178,375 mappings, 251,946 source refs) | read_everything.py | (future: pre_classify) |
| `keyword_index` | 8,185 | Keyword->HS inverted index | knowledge_indexer.py, deep_learn.py | intelligence.py pre_classify |
| `product_index` | 65 | Product name->HS index | knowledge_indexer.py, deep_learn.py, enrich_knowledge.py | intelligence.py pre_classify |
| `supplier_index` | 3 | Supplier->products/HS index | knowledge_indexer.py, deep_learn.py, enrich_knowledge.py | intelligence.py pre_classify |
| `classification_knowledge` | 82 | Verified classification results (learned) | verification_loop.py, deep_learn.py | intelligence.py pre_classify |
| `classification_rules` | 32 | Classification rules | import_knowledge.py | intelligence.py, classification_agents.py |
| `tariff` | 11,753 | Full Israeli tariff DB (HS codes, descriptions, rates) | Session 8 tariff import | intelligence.py, librarian.py, verification_loop.py |
| `tariff_chapters` | 101 | Chapter summaries | Session 8 cleanup | intelligence.py |
| `knowledge_base` | 297 | Professional documents (typed by category) | enrich_knowledge.py | librarian.py, deep_learn.py |
| `knowledge` | 71 | General knowledge docs | Manual/import | librarian.py |
| `legal_requirements` | 7,443 | Import/export legal requirements from data.gov.il (33,975 records) | Session 8 night (ingest_and_wire_legal.py) | NOT YET WIRED into pipeline |
| `licensing_knowledge` | 18 | Licensing info | Import | librarian.py |
| `procedures` | 3 | Customs procedures | Import | librarian.py |
| `hs_code_index` | 101 | HS code chapter index | Import | librarian.py |
| `triangle_learnings` | 36 | Triangle trade learnings | Import | read_everything.py |
| `fta_agreements` | 21 | Free Trade Agreements | import_knowledge.py | intelligence.py |
| `regulatory_requirements` | 28 | Regulatory requirements | import_knowledge.py | intelligence.py |
| `ministry_index` | 84 | Ministry routing (25 chapters) | Import | intelligence.py, classification_agents.py |
| `librarian_index` | 12,595 | Document search index | librarian_index.py | librarian.py |
| `free_import_cache` | 8 | Cached Free Import Order API results | intelligence.py | intelligence.py |

#### Pupil & Silent Learning (data exists, code NOT in repo)
| Collection | Docs | What | Written by | Read by |
|------------|------|------|------------|---------|
| `pupil_teachings` | 202 | Pupil's learned teachings | pupil_v05_final.py (NOT in repo) | read_everything.py (mines into brain_index) |
| `rcb_silent_classifications` | 128 | Silently classified CC emails | fix_silent_classify.py (NOT in repo) | read_everything.py (mines into brain_index) |

#### Classification Results
| Collection | Docs | What | Written by | Read by |
|------------|------|------|------------|---------|
| `rcb_classifications` | 86 | Classification results from pipeline | classification_agents.py | intelligence.py, read_everything.py |
| `classifications` | 25 | Legacy classifications | Legacy code | on_new_classification trigger, librarian.py |
| `declarations` | 53 | Customs declarations | Import | deep_learn.py |
| `batch_reprocess_results` | 345 | Batch reprocess results (16 classified, 38 learned) | batch_reprocess.py | read_everything.py |
| `batch_reprocess_summary` | ? | Batch reprocess run summaries | batch_reprocess.py | -- |

#### Email Processing
| Collection | Docs | What | Written by | Read by |
|------------|------|------|------------|---------|
| `rcb_processed` | 41 | Processed email message IDs (dedup) | main.py rcb_check_email | main.py rcb_check_email |
| `rcb_logs` | 101 | Processing logs | main.py | rcb_inspector.py |
| `rcb_inbox` | 9 | Stored inbox items | main.py | -- |
| `inbox` | 64 | Legacy inbox | Legacy | -- |
| `rcb_first_emails` | 2 | First-time sender tracking | main.py | main.py |
| `knowledge_queries` | 50 | Knowledge query logs | knowledge_query.py | rcb_inspector.py |

#### Enrichment & Tasks
| Collection | Docs | What | Written by | Read by |
|------------|------|------|------------|---------|
| `enrichment_tasks` | 304 | Enrichment task definitions | librarian_researcher.py | enrichment_agent.py |
| `agent_tasks` | 731 | Agent task queue | Various | enrichment_agent.py |
| `pending_tasks` | 27 | Pending tasks | Various | enrichment_agent.py |
| `librarian_search_log` | 2,921 | Search analytics | librarian.py | rcb_inspector.py |
| `librarian_enrichment_log` | 168 | Enrichment logs | librarian_index.py | -- |
| `enrichment_log` | 8 | Enrichment execution logs | enrichment_agent.py | -- |
| `pc_agent_tasks` | 0 | PC Agent download tasks | pc_agent.py | pc_agent.py (never triggered) |

#### System & Monitoring
| Collection | Docs | What | Written by | Read by |
|------------|------|------|------------|---------|
| `system_counters` | 8 | RCB ID sequence counters (per day) | rcb_id.py | rcb_id.py |
| `system_metadata` | 4 | Script run metadata (read_everything, deep_learn, enrich, indexer) | Scripts | -- |
| `system_status` | 4 | System status (rcb, rcb_monitor, enrichment_summary, source_catalog) | monitor_agent, rcb_inspector | rcb_health_check |
| `system_state` | 0 | Persistent state (language_learner) | rcb_email_processor.py | rcb_email_processor.py (EMPTY) |
| `config` | 9 | System configuration | Manual | Various |
| `rcb_inspector_reports` | 14 | Daily inspection reports | rcb_inspector.py | -- |
| `rcb_test_reports` | 3 | Self-test reports | rcb_self_test.py | -- |
| `session_backups` | 11 | Session backup content | rcb_api POST /api/backup | rcb_api GET /api/backups |
| `session_missions` | 1 | Auto-generated session missions | rcb_inspector.py | -- |
| `sessions_backup` | 2 | Legacy session tracking | Legacy | rcb_inspector.py |
| `monitor_errors` | 0 | Monitor error tracking | monitor_agent (EMPTY) | -- |
| `learning_log` | 0 | Learning event log | (NEVER WIRED, EMPTY) | -- |
| `rcb_stats` | 1 | Statistics | main.py | -- |

#### Other
| Collection | Docs | What | Written by | Read by |
|------------|------|------|------------|---------|
| `sellers` | 4 | Known sellers/suppliers | deep_learn.py | intelligence.py |
| `buyers` | 2 | Known buyers | Import | -- |
| `regulatory_certificates` | 4 | Certificate info | Import | -- |
| `document_types` | 13 | Document type definitions | Import | read_everything.py |
| `shipping_lines` | 15 | Shipping line info | Import | read_everything.py |
| `verification_cache` | 43 | HS verification cache | verification_loop.py | verification_loop.py |

---

## 5. External API Integrations

### Microsoft Graph API (Email)
- **Used by:** rcb_helpers.py
- **Endpoints:** /messages (read), /messages/{id}/attachments, /messages/{id} (PATCH read), /sendMail
- **Auth:** OAuth2 refresh token flow (client_id, client_secret, tenant_id, refresh_token)
- **Secrets:** GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, GRAPH_TENANT_ID, GRAPH_REFRESH_TOKEN
- **Mailbox:** rcb@rpa-port.co.il

### Anthropic API (Claude)
- **Used by:** classification_agents.py `call_claude()`
- **Model:** claude-sonnet-4-20250514 (Agent 2: classification)
- **Secret:** ANTHROPIC_API_KEY
- **Balance:** ~$30 remaining

### Google Gemini API
- **Used by:** classification_agents.py `call_gemini()`
- **Models:** gemini-2.5-flash (Agents 1,3,4,5), gemini-2.5-pro (Agent 6: synthesis)
- **Secret:** GEMINI_API_KEY
- **Tier:** Free (hitting 429 rate limits)

### Free Import Order API (apps.economy.gov.il)
- **Used by:** intelligence.py `_query_fio_api()`
- **Endpoint:** `https://apps.economy.gov.il/Apps/FreeImportServices/FreeImportData`
- **Auth:** None (public API)
- **Note:** SESSION19_BACKUP.md also references data.gov.il resource IDs for legal_requirements ingestion (separate from this API)

---

## 6. Data Flow: Email Pipeline

```
Email arrives at rcb@rpa-port.co.il
    |
    v
[rcb_check_email] (every 2 min, main.py:1020)
    |-- Graph API: fetch unread emails
    |-- Check rcb_processed (dedup)
    |-- Check knowledge query (knowledge_query.py)
    |-- Extract attachments (rcb_helpers.py)
    |
    v
[process_and_send_report] (classification_agents.py:1399)
    |-- extract_text_from_attachments (rcb_helpers.py)
    |-- parse_all_documents (document_parser.py)
    |-- validate_invoice (invoice_validator.py)
    |
    v
[run_full_classification] (classification_agents.py:598)
    |-- pre_classify (intelligence.py) -- brain search
    |-- Agent 1: run_document_agent (Gemini Flash -> Claude fallback)
    |-- Agent 2: run_classification_agent (Claude Sonnet)
    |-- query_tariff, query_ministry_index, query_classification_rules
    |-- Agent 3: run_regulatory_agent (Gemini Flash)
    |-- Agent 4: run_fta_agent (Gemini Flash)
    |-- Agent 5: run_risk_agent (Gemini Flash)
    |-- query_free_import_order (data.gov.il API)
    |-- route_to_ministries
    |-- verify_all_classifications (verification_loop.py)
    |-- Agent 6: run_synthesis_agent (Gemini Pro)
    |-- analyze_ambiguity + generate_smart_questions
    |
    v
[audit_before_send] (classification_agents.py:994)
    |-- Quality gate: check HS validity, confidence
    |-- Retry if garbage detected
    |
    v
[build_classification_email + build_excel_report]
    |-- Consolidated email (ack + report + clarification)
    |-- In-Reply-To/References threading headers
    |
    v
[helper_graph_send] -> email sent to original sender
[save to rcb_classifications in Firestore]
```

### Pipeline Logic Deep Dive (from reading actual code)

**Email Fetch (main.py:1020-1171):**
- Fetches emails from last **2 hours** (comment says "2 days" but code says `timedelta(hours=2)`, marked "TEMPORARY")
- Filters: must be in TO field (CC silently skipped at line 1072), must be from @rpa-port.co.il domain
- Dedup: MD5 hash of Graph message ID checked against `rcb_processed` collection
- Marks processed BEFORE classification starts (prevents double-processing if slow)
- Knowledge queries (team questions) handled separately, skip classification entirely

**Agent 1 — Product Extraction (classification_agents.py:430-477):**
- Gemini Flash first, 4096 max_tokens
- Strips markdown fences from Gemini response (```json wrapper bug)
- If JSON parse fails or incomplete response, falls back to Claude
- If both fail, uses raw text as single item: `{"items": [{"description": doc_text[:500]}]}`
- Extracts per product: description, quantity, unit_price, origin_country, hs_code (if known)

**Brain Pre-Classification (intelligence.py:23-216):**
- Runs on first 3 items only (not all 49 on a Chinese invoice)
- 6-source cascade with confidence boosting:
  1. `keyword_index` (8,185 docs) — fast inverted index, O(keywords) lookup
  2. `product_index` (65 docs) — exact/prefix match, usage count weighted
  3. `supplier_index` (3 docs) — if seller name matches, boost HS confidence
  4. `classification_knowledge` (82 docs) — past verified classifications
  5. `classification_rules` (32 docs) — keyword pattern rules
  6. `tariff` (11,753 docs) — SLOW fallback, only if keyword_index had zero results
- **Confidence boosting**: if 2+ sources agree on same HS code, confidence += 5 per source (max 95)
- **Correction priority**: if a classification_knowledge item was a user correction, extra +5 boost
- Returns top 10 candidates sorted by confidence
- Also runs: regulatory lookup by chapter, FTA lookup by country

**Agent 2 — HS Classification (classification_agents.py:480-504):**
- Claude Sonnet (best quality for core task)
- Receives: items + tariff excerpts + classification rules + combined brain+librarian context
- Validates output: rejects non-numeric HS codes (Hebrew text like "לא ניתן לסווג")
- HS codes validated against tariff DB, corrected if close match found

**Quality Gate (classification_agents.py:994-1103):**
- Checks every classification before sending:
  - HS code must be numeric (6-10 digits)
  - HS code must not contain Hebrew characters
  - Confidence must be parseable
  - At least 1 item must have valid HS code
- If all items garbage: retries Agent 2 with explicit "return numeric HS only" instruction
- Calculates average confidence, flags low-confidence results with warning banner
- If still garbage after retry: sends email with "unclassified" banner instead of wrong HS codes

**Email Output (classification_agents.py:1133-1397):**
- Consolidated single email: ack banner + classification table + clarification section
- In-Reply-To and References headers from original internetMessageId (threading)
- Excel attachment with all classifications
- Smart questions appear as yellow box before footer (if ambiguity detected)
- RTL direction set in HTML for Hebrew content

**What Brain CANNOT Do Yet (verified in code):**
- Cannot skip Agent 2 even at 95% confidence (always sends to AI)
- Cannot learn from CC emails (line 1072 skips them)
- Cannot learn from user reply corrections
- Cannot execute web searches (librarian_researcher generates queries but no execution)
- legal_requirements (7,443 docs) not queried during classification pipeline
- brain_index (11,245 docs) not used by pre_classify (uses keyword_index instead)

**Tracker Integration (classification_agents.py:644-673):**
- Tracker IS created during classification (if TRACKER_AVAILABLE)
- Fed with parsed documents (BL, invoice, etc.)
- Tracker info IS included in final result dict
- BUT: tracker_email.py (TaskYam progress bar) is NOT called — no progress email sent
- Known bug: `_derive_current_step()` crashes when import_proc or export_proc is None

---

## 7. Files NOT in Repo

These files were uploaded to Claude browser sessions but never committed. Their functionality exists ONLY in chat uploads and Firebase data.

| File | Lines | What it does | Session | Firebase evidence |
|------|-------|-------------|---------|-------------------|
| `fix_silent_classify.py` | 67 | CC emails silently classified, stores in rcb_silent_classifications | Session 18 | 128 docs exist in rcb_silent_classifications |
| `fix_tracker_crash.py` | 16 | Patches None bug in _derive_current_step() | Session 18 | -- |
| `patch_tracker_v2.py` | 300 | Tracker v2 patch with improved phase detection | Session 18 | -- |
| `pupil_v05_final.py` | ??? | Original pupil: devil's advocate, CC email learning | Pre-Session 17 | 202 docs exist in pupil_teachings |

**Note:** `tracker_email.py` was listed as missing but IS in the repo (functions/lib/tracker_email.py, 316 lines).

---

## 8. Dead Code / Patch Files

These files in `functions/` appear to be one-time patches or fixes that were applied and are no longer needed:

| File | Lines | What | Status |
|------|-------|------|--------|
| `add_attachments.py` | ? | Add attachment support | Applied, dead |
| `add_backup_api.py` | ? | Add backup API endpoint | Applied, dead |
| `add_followup_trigger.py` | ? | Add followup trigger | Applied, dead |
| `add_import.py` | ? | Add import statement | Applied, dead |
| `add_multi_agent_system.py` | ? | Add multi-agent system | Applied, dead |
| `add_multiagent_safe.py` | ? | Safe multi-agent add | Applied, dead |
| `fix_decorator.py` | ? | Fix function decorator | Applied, dead |
| `fix_email_check.py` | ? | Fix email check | Applied, dead |
| `fix_final.py` | ? | Final fixes | Applied, dead |
| `fix_main_imports.py` | ? | Fix imports in main.py | Applied, dead |
| `fix_missing_functions.py` | ? | Add missing functions | Applied, dead |
| `fix_signature.py` | ? | Fix function signatures | Applied, dead |
| `fix_test.py` | ? | Fix tests | Applied, dead |
| `final_fix.py` | ? | Final fix | Applied, dead |
| `main_fix.py` | ? | Fix main.py | Applied, dead |
| `name_fix.py` | ? | Fix names | Applied, dead |
| `move_get_secret.py` | ? | Move get_secret function | Applied, dead |
| `patch_classification.py` | ? | Patch classification | Applied, dead |
| `patch_main.py` | ? | Patch main.py | Applied, dead |
| `patch_rcb.py` | ? | Patch RCB | Applied, dead |
| `patch_smart_email.py` | ? | Patch smart email | Applied, dead |
| `cleanup_old_results.py` | ? | Clean old results | Utility |
| `clear_processed.py` | ? | Clear processed emails | Utility |
| `remove_duplicates.py` | ? | Remove duplicates | Utility |
| `rcb_diagnostic.py` | ? | Diagnostic tool | Utility |
| `test_classification.py` | ? | Test classification | Test |
| `test_full.py` | ? | Full test | Test |
| `test_graph.py` | ? | Test Graph API | Test |
| `test_real.py` | ? | Real email test | Test |

**Also in main.py (disabled):**
- `monitor_self_heal` :1439 (duplicate function name, disabled)
- `monitor_fix_all` :1455 (disabled)
- `monitor_fix_scheduled` :1468 (disabled)
- Old IMAP/SMTP code inside `check_email_scheduled` (dead, Graph API replaced it)

---

## 9. Firebase Session History

### session_backups (11 docs, queried live)
| ID | Date | Size | Content |
|----|------|------|---------|
| 2026-02-03-session5 | Feb 3 | 223 | Graph API + AI foundation |
| 2026-02-03-session5-multiagent | Feb 3 | 129 | Multi-agent architecture designed |
| 2026-02-03-session5-SUCCESS | Feb 3 | 531 | 8 functions deployed, rcb@ active |
| 2026-02-03-session5-END | Feb 3 | 440 | Session 5 end state |
| 2026-02-08-evening | Feb 8 | 1,741 | Tariff parent_heading_desc investigation |
| 2026-02-08-evening-2 | Feb 8 | 1,230 | parent_heading_desc fix complete (12,334 docs) |
| 2026-02-08-evening-full | Feb 8 | 3,737 | Full evening session log |
| 2026-02-08-evening-final | Feb 8 | 409 | Evening final summary |
| 2026-02-08-night-final | Feb 8 | 5,463 | Night session: legal_requirements (7,443 docs), 4 patch files, 30K+ DB ops |
| 2026-02-09-early-morning | Feb 9 | 0 | Empty |
| latest | -- | 0 | Empty placeholder |

### sessions_backup (2 docs, legacy)
| ID | Date | Content |
|----|------|---------|
| session_13 | Feb 6 | Knowledge query handler + self-test engine, v4.0.0 -> v4.1.0 |
| session_14 | Feb 6 | Language tools overhaul, wired to classification_agents + email_processor |

### session_missions (1 doc)
| ID | Priority | Content |
|----|----------|---------|
| session_15 | MEDIUM | Fix race condition RC-001 + Enrich 82 blind-spot HS chapters + Consolidate schedulers |

### rcb_inspector_reports (14 docs, daily since Feb 6)
- Health score range: 71-88
- Latest (Feb 13): health=88, status=DEGRADED, 1 issue, 3 warnings
- Consistent daily runs at 13:00 UTC

---

## 10. System Health

### Current Status (Feb 13, 2026)
- **Health Score:** 88/100 (DEGRADED)
- **RCB Status:** healthy (system_status/rcb)
- **Monitor Status:** degraded (6 pending retries)
- **Inspector:** Running daily at 15:00 IST
- **Version:** 4.1.0

### System Counters (emails processed per day)
| Date | Emails |
|------|--------|
| Feb 6 | 101 |
| Feb 7 | 5 |
| Feb 8 | 51 |
| Feb 9 | 46 |
| Feb 10 | 77 |
| Feb 11 | 3 |
| Feb 12 | 2 |
| Feb 13 | 6 |

### Last Script Runs (from system_metadata)
| Script | Last Run | Key Stats |
|--------|----------|-----------|
| read_everything | Feb 13 12:08 | 29 collections, 11,254 keywords, 178,375 HS mappings |
| knowledge_indexer | Feb 13 11:31 | 8,063 keywords, 61 products, 2 suppliers |
| deep_learn | Feb 13 11:29 | 240 keywords, 52 products enriched |
| enrich_knowledge | Feb 13 11:41 | 256 KB reclassified, 44 products extracted |

### API Balance
- **Anthropic:** ~$30 remaining
- **Gemini:** Free tier (429 rate limits)
- **Graph API:** Working
- **data.gov.il:** Working (public)
