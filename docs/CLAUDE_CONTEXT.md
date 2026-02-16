# RPA-PORT PLATFORM — FULL CONTEXT FOR CLAUDE AI
## Last Updated: February 16, 2026 (end of Session 25 / after pulling Sessions 26-28)
## Repo: github.com/doronrpa-hub/rpa-port-platform
## Firebase Project: rpa-port-customs
## Owner: Doron, R.P.A. PORT LTD — Israeli customs brokerage

---

## WHAT THIS SYSTEM IS

An AI-powered Israeli customs brokerage platform that:
1. **Monitors** the mailbox `rcb@rpa-port.co.il` every 2 minutes via Microsoft Graph API
2. **Classifies** imported goods into Israeli HS codes (format: XX.XX.XXXXXX/X)
3. **Tracks** shipments (sea containers via TaskYam API, air cargo via Maman API)
4. **Learns** from every interaction — builds memory to reduce AI costs over time
5. **Reports** classification results back to the team via formatted HTML emails

The system runs as **28 Firebase Cloud Functions** (Python 3.12) on GCP project `rpa-port-customs`.

---

## CRITICAL RULES FOR ANY CHANGES

1. **DO NOT** delete, rename, or restructure ANY existing functions or files
2. **DO NOT** change any function signatures
3. Before ANY change: grep the ENTIRE codebase for references
4. After ANY change: run `python -m pytest tests/ -v --tb=short` from functions/
5. One fix per commit, commit and push to main immediately
6. If unsure — STOP and report, don't guess
7. Dead code cleanup goes in a SEPARATE branch, never main

---

## TECH STACK

| Layer | Technology |
|-------|-----------|
| Runtime | Firebase Cloud Functions, Python 3.12 |
| Database | Firestore (~132 collections, ~139K docs) |
| Storage | Google Cloud Storage (large files >10KB) |
| Email | Microsoft Graph API (OAuth2) for rcb@rpa-port.co.il |
| AI - Classification | Claude Sonnet 4.5 (HS codes), Gemini Flash (extraction/synthesis) |
| AI - Cross-check | Claude + Gemini + ChatGPT three-way verification |
| AI - Extraction | Gemini Flash (cheap), Claude (fallback only) |
| PDF Extraction | pdfplumber -> pypdf -> PyMuPDF -> Google Vision OCR (waterfall) |
| Sea Tracking | TaskYam API (Israeli ports: Haifa, Ashdod, Eilat, Hadera) |
| Air Tracking | Maman API (Ben Gurion cargo terminal) — NOT YET CONFIGURED |
| UK Tariff | UK Trade Tariff API (free, for cross-verification) |
| CI/CD | GitHub Actions: test on every push, deploy on main |
| Secrets | Google Secret Manager (zero hardcoded keys) |

---

## ARCHITECTURE: EMAIL PROCESSING PIPELINE

When an email arrives at `rcb@rpa-port.co.il`:

```
rcb_check_email() [every 2 min]
  |
  ├── CC email (not direct TO) → Silent observation only
  |     ├── Pupil: learn sender patterns (FREE)
  |     └── Tracker: observe shipping data (FREE)
  |
  └── Direct TO email (from @rpa-port.co.il)
        |
        ├── Brain Command? (from doron@) → brain_commander handles
        ├── Knowledge Query? (question, no docs) → knowledge_query answers
        ├── Shipping-only? (BL/AWB, no invoice) → Tracker only (skip classification)
        └── Default → FULL CLASSIFICATION PIPELINE
              |
              ├── 1. Extract text (regex → brain memory → templates → Gemini Flash)
              ├── 2. Pre-classify (intelligence.py, $0.001, skip pipeline if 90%+ confidence)
              ├── 3. Tool-calling engine OR 6-agent pipeline ($0.02-$0.05)
              ├── 4. Cross-check (3-way AI if disagreement)
              ├── 5. Build justification chain (legal backing)
              ├── 6. Generate HTML report
              └── 7. Send reply email + learn from result
```

---

## ALL 28 CLOUD FUNCTIONS

### Scheduled (17)
| Function | Schedule | Purpose |
|----------|----------|---------|
| check_email_scheduled | 5 min | **DISABLED** — replaced by rcb_check_email |
| rcb_check_email | 2 min | Main email processor (540s timeout) |
| enrich_knowledge | 1 hour | Fill knowledge gaps |
| monitor_agent | 5 min | PC agent monitoring |
| rcb_cleanup_old_processed | 24 hours | Delete old processed records |
| rcb_ttl_cleanup | 03:30 ISR | TTL cleanup: scanner_logs (30d), temp data |
| rcb_retry_failed | 6 hours | Retry failed classifications |
| rcb_health_check | 1 hour | System health + alerts |
| rcb_inspector_daily | Nightly | System diagnostics |
| rcb_nightly_learn | Nightly | Consolidate learning |
| rcb_tracker_poll | Scheduled | Poll active shipment deals |
| rcb_pupil_learn | Scheduled | Domain expert learning |
| rcb_daily_digest | 07:00 ISR | Morning intelligence report |
| rcb_overnight_audit | 02:00 ISR | Read-only system audit (50 emails, 900s) |
| rcb_pc_agent_runner | Scheduled | Execute pending PC agent tasks |
| rcb_overnight_brain | 20:00 ISR | 9-stream enrichment ($3.50 cap) |
| rcb_download_directives | 04:00 ISR | Download customs directives from Shaarolami |

### Firestore Triggers (2)
| Function | Trigger | Purpose |
|----------|---------|---------|
| on_new_classification | doc created in classifications/ | Auto-suggest HS codes |
| on_classification_correction | doc updated in classifications/ | Learn from corrections |

### HTTP Endpoints (9)
| Function | Purpose |
|----------|---------|
| api | Legacy REST API |
| rcb_api | Modern RCB API |
| monitor_agent_manual | Manual agent trigger |
| monitor_self_heal | System self-healing |
| monitor_fix_all | Batch fix issues |
| test_pdf_ocr | Test PDF extraction |
| test_pdf_report | Test PDF reports |
| rcb_self_test | System self-tests |
| rcb_inspector | Manual inspection |

---

## ALL MODULES (functions/lib/)

### Core Pipeline
| Module | Purpose |
|--------|---------|
| classification_agents.py | 6-agent classification pipeline (Agents 1-6) |
| tool_calling_engine.py | Replacement agentic classification (Claude + tools) |
| tool_definitions.py | Tool schemas for tool-calling engine |
| tool_executors.py | Tool execution implementations |
| intelligence.py | Zero-AI knowledge lookup (Firestore only, $0.001) |
| cross_checker.py | Three-way AI cross-check (Claude + Gemini + ChatGPT) |
| justification_engine.py | Legal justification chain builder |
| report_builder.py | HTML classification report generator |
| cost_tracker.py | Hard-capped budget tracker ($3.50/run) |

### Email & Communication
| Module | Purpose |
|--------|---------|
| rcb_helpers.py | Graph API, PDF extraction, email utilities |
| rcb_email_processor.py | Email parsing, acknowledgment |
| tracker_email.py | Tracker notification emails |
| clarification_generator.py | Generate Hebrew clarification requests |

### Document Extraction (NEW - Session 28)
| Module | Purpose |
|--------|---------|
| smart_extractor.py | Multi-method extraction engine |
| read_document.py | Master reliable extraction function |
| extraction_result.py | Data classes for results |
| extraction_validator.py | Quality validation before entry |
| extraction_adapter.py | Backward-compatible wrapper |
| table_extractor.py | Cross-verified table extraction |
| extraction_quality_logger.py | Track method performance |
| storage_manager.py | Smart Firestore vs Cloud Storage routing |
| doc_reader.py | Template-based document reading |
| document_parser.py | Regex document parsing (BL fields, etc.) |

### Knowledge Management
| Module | Purpose |
|--------|---------|
| librarian.py | Central knowledge search |
| librarian_index.py | Document indexing & inventory |
| librarian_tags.py | Auto-tagging system |
| librarian_researcher.py | Enrichment & learning |
| self_learning.py | Brain memory (check before AI, learn after) |
| knowledge_query.py | Detect & handle knowledge questions |

### Domain Agents
| Module | Purpose |
|--------|---------|
| brain_commander.py | Father channel (doron@ commands, missions) |
| pupil.py | Domain expert learning from emails |
| tracker.py | Shipment tracking & deal management |
| air_cargo_tracker.py | Maman API for Ben Gurion air cargo |

### Overnight Operations
| Module | Purpose |
|--------|---------|
| overnight_brain.py | 9-stream enrichment (hard cap $3.50) |
| overnight_audit.py | Read-only system health audit |
| nightly_learn.py | Learning consolidation |
| self_enrichment.py | Knowledge gap filling |

### Data Pipeline (NEW - Session 28)
| Module | Purpose |
|--------|---------|
| data_pipeline/pipeline.py | Master ingestion function |
| data_pipeline/extractor.py | Format-specific extraction |
| data_pipeline/structurer.py | LLM-based field extraction |
| data_pipeline/indexer.py | Searchable index creation |
| data_pipeline/directive_downloader.py | Israeli customs directive downloader |

### Integrations
| Module | Purpose |
|--------|---------|
| uk_tariff_integration.py | UK Trade Tariff API (free cross-check) |
| gemini_classifier.py | Gemini Flash bridge |
| pc_agent.py | Browser automation tasks |
| pc_agent_runner.py | Execute pending PC tasks |

### Utilities
| Module | Purpose |
|--------|---------|
| rcb_id.py | Generate trackable IDs (RCB-XXXXXX-CLS) |
| language_tools.py | Hebrew/English utilities |
| pdf_creator.py | PDF report generation |
| ttl_cleanup.py | TTL-based collection cleanup |
| collection_streamer.py | Memory-safe batch streaming |
| memory_config.py | Cloud Function memory configs |
| smart_questions.py | Question generation for clarification |
| invoice_validator.py | Invoice field validation |
| incoterms_calculator.py | CIF calculations |
| product_classifier.py | Product-based classification |
| document_tracker.py | Shipment phase tracking |
| verification_loop.py | Classification verification |
| enrichment_agent.py | Background enrichment runner |

---

## KEY FIRESTORE COLLECTIONS

### Tier 1 — Large (>1,000 docs)
| Collection | Docs | Purpose |
|------------|------|---------|
| scanner_logs | ~38K | PC Agent logs (TTL: 30 days) |
| files | ~38K | Attachment storage |
| tariff | 11,753 | Israeli HS code database |
| brain_index | 11,262 | Brain knowledge index |
| keyword_index | 8,195 | Term-to-HS mapping (98% clean) |

### Tier 2 — Active (~100-1,000 docs)
| Collection | Purpose |
|------------|---------|
| rcb_processed | Email processing records |
| rcb_classifications | Classification results |
| classifications | Pending/confirmed HS codes |
| sellers | Vendor history + known HS codes |
| learned_classifications | High-confidence past decisions |
| learned_doc_templates | Per-shipping-line extraction templates |
| tracker_deals | Active shipment deals |
| tracker_awb_status | Air cargo AWB tracking |
| pupil_observations | Email pattern learning |
| brain_commands | Father channel commands |
| knowledge_base | Past classifications knowledge |
| classification_knowledge | Learned patterns |
| classification_directives | Israeli customs directives (~217) |
| librarian_index | Master searchable index |
| cross_check_log | AI model disagreements |
| extraction_quality_log | Extraction method performance |
| overnight_audit_results | Audit reports |

### Total: ~132 collections, ~139K documents

---

## COST OPTIMIZATION TIERS

The system follows cheapest-first priority:

| Tier | Method | Cost | When |
|------|--------|------|------|
| 0 | Regex extraction | $0.00 | Always runs first |
| 1 | Brain memory lookup | $0.00 | Checks learned_classifications |
| 2 | Firestore templates | $0.00 | Checks learned_doc_templates |
| 3 | Intelligence pre-classify | $0.001 | Firestore knowledge lookup |
| 4 | Tool-calling engine | $0.02-0.04 | Claude with tools |
| 5 | Full 6-agent pipeline | $0.05 | Gemini Flash x5 + Claude x1 |
| 6 | Three-way cross-check | $0.10+ | Only on disagreement |

**Overnight brain enrichment**: Hard cap $3.50/run via CostTracker

---

## CLASSIFICATION METHODOLOGY (LEGALLY MANDATED)

Israeli customs classification follows 9 phases:
1. **Phase 0**: Case type (import/export, normal/special regime)
2. **Phase 1**: Examine goods (physical properties, essence, use/function)
3. **Phase 2**: Gather info (invoice FIRST, then research, clarification LAST)
4. **Phase 3**: Elimination (chapter -> heading -> subheading -> code)
5. **Phase 4**: Bilingual check (Hebrew tariff + English tariff cross-check)
6. **Phase 5**: Post-classification (verify against rulings, directives, precedents)
7. **Phase 6**: Regulatory (FTA, Free Import Order, ministry requirements)
8. **Phase 7**: Multi-AI verification (Claude + Gemini + ChatGPT independently)
9. **Phase 8**: Source attribution (trace every claim to a source)

**Current gap**: The 6-agent pipeline does NOT fully follow this methodology yet. This is the major improvement needed.

---

## BUGS FIXED IN SESSIONS 26-28 (already in main)

16 bugs were fixed and deployed:
1. tracker_email.py — signature mismatch (tracker emails were crashing)
2. VAT rate 17% -> 18% (pdf_creator.py + main.py)
3. Orphan @https_fn decorator removed (security fix)
4. Confidence boost order fixed (intelligence.py)
5. Tuple keys sorted (smart_questions.py)
6. was_enriched init before try block (tracker.py)
7. Agent 6 tier changed to "pro" (classification_agents.py)
8. requests import moved inside function (main.py)
9. re module shadowing fixed (pupil.py)
10. Cache bypass for FIO data (verification_loop.py)
11. brain_commander ask_claude fixed (was importing non-existent module)
12. Pupil investigation task fields added
13. Librarian HS format fixed
14. Duplicate monitor_self_heal removed
15. pc_agent import guarded with try/except
16. Hebrew regex typo fixed (language_tools.py)
17. Circular import in tool_executors.py fixed (lazy import)
18. Keyword index cleaned (117 garbage entries removed)

---

## KNOWN ISSUES STILL OPEN

### Critical
- **Maman Air Cargo**: Credentials not configured (need to call 03-9715388 to register)
- **AWB regex extraction**: `result['awbs']` initialized but never populated in tracker.py
- **Tariff data quality**: 35.7% of parent_heading_desc has garbage data
- **Chapter notes**: Not properly stored in tariff_chapters

### High
- **BL extraction gaps**: Maersk pattern defined but not used in extraction loop
- **Missing shipping line domains**: Yang Ming, PIL, TURKON, OOCL, WAN HAI
- **"ONE" pattern**: Matches English word "one" (false positives)
- **bol_prefixes from Firestore**: Not wired into tracker regex
- **Librarian reads**: Can trigger up to 19,000 Firestore reads per query (no caching)
- **Schedule conflict**: Two heavy jobs fire at 02:00 simultaneously

### Medium
- **5 failing tests**: table_extractor and smart_extractor HTML tests (beautifulsoup4 related)
- **tariff_chapters doc IDs**: Wrong format (import_chapter_XX not plain numbers)
- **Classification methodology gap**: Current pipeline doesn't follow legally mandated Phase 0-9

### Low
- **43 utility scripts** cluttering functions/ root directory
- **17 .bak_20260216 backup files** committed to repo
- **overnight_log.txt**: 22K lines committed to repo

---

## FILE STRUCTURE

```
rpa-port-platform/
├── .github/workflows/          # CI/CD (deploy, test, overnight-learn)
├── docs/                       # Session docs, audit reports, methodology
├── functions/
│   ├── main.py                 # Entry point — all 28 Cloud Functions
│   ├── requirements.txt        # Python dependencies
│   ├── lib/                    # All library modules (~60 .py files)
│   │   ├── data_pipeline/      # Document ingestion pipeline (5 modules)
│   │   └── *.py                # Core modules (see table above)
│   └── tests/                  # 20 test files, 452+ tests
├── public/                     # Web hosting
├── firebase.json               # Firebase config
├── firestore.rules             # Security rules
└── *.md                        # Audit/fix reports
```

---

## DEPLOYMENT

### Local deploy (preferred):
```bash
firebase deploy --only functions --project rpa-port-customs
```

### GitHub Actions (automatic):
- Push to main -> tests run -> if pass -> deploy

### Firebase project:
```bash
firebase use rpa-port-customs
```

---

## CREDENTIALS & SECRETS (in Google Secret Manager)

| Secret | Purpose |
|--------|---------|
| graph_client_id | Microsoft Graph API (email) |
| graph_client_secret | Microsoft Graph API |
| graph_tenant_id | Microsoft Graph API |
| gemini_api_key | Gemini Flash/Pro AI |
| anthropic_api_key | Claude AI |
| openai_api_key | ChatGPT (cross-check) |
| taskyam_api_key | Israeli port container tracking |
| maman_username | Air cargo terminal — NOT YET SET |
| maman_password | Air cargo terminal — NOT YET SET |

---

## TESTING

```bash
cd functions
python -m pytest tests/ -v --tb=short
```

Current: **452 passed, 5 failed** (HTML extraction tests need beautifulsoup4 fix)

---

## OVERNIGHT BRAIN — 9 STREAMS

The overnight_brain runs at 20:00 ISR with hard cap $3.50:

1. **Deep tariff mine** — Extract knowledge from tariff descriptions
2. **Email mine** — Learn from past email classifications
3. **CC learning** — Process CC email observations
4. **Attachment mine** — Extract knowledge from stored attachments
5. **AI gap fill** — Use Gemini to fill knowledge_gaps
6. **UK API sweep** — Free UK tariff cross-reference
7. **Cross-reference** — Link related HS codes
8. **Self-teach** — Generate training examples
9. **Knowledge sync** — Synchronize across collections

---

## KEY DECISIONS MADE

- Hebrew is the primary language (emails, reports, tariff data)
- Israeli HS format: XX.XX.XXXXXX/X (not international)
- Gemini Flash for cheap/fast operations, Claude for accuracy-critical HS classification
- No direct IMAP — Microsoft Graph API only (800+ lines of dead IMAP code still in main.py)
- Templates learn per shipping line (e.g., MSC BL template different from CMA CGM)
- Brain Commander channel: doron@rpa-port.co.il sends commands, system executes missions
- PC Agent for browser automation (TaskYam scraping, etc.)

---

## WHAT NEEDS TO BE DONE NEXT (PRIORITY ORDER)

### Phase 1 — Data Verification (before any code changes)
- Query learned_doc_templates — which shipping lines have templates
- Query shipping_lines collection — carrier data and bol_prefixes
- Search for "Elizabeth" email across tracker/classification collections
- Count tariff collection documents
- Verify tariff data quality (35.7% garbage in parent_heading_desc)

### Phase 2 — BL Extraction Fixes
1. Wire Maersk BL pattern into extraction loop
2. Wire bol_prefixes from Firestore into tracker
3. Fix "ONE" false positive pattern
4. Add missing shipping line email domains
5. Add WAN HAI carrier support

### Phase 3 — Critical Infrastructure
1. Configure Maman air cargo credentials
2. Implement AWB regex extraction in tracker
3. Fix tariff_chapters document format
4. Clean tariff parent_heading_desc garbage data
5. Rebuild classification pipeline to follow Phase 0-9 methodology

### Phase 4 — Cleanup
1. Remove 43 utility scripts from functions/ root
2. Remove .bak_20260216 backup files
3. Remove overnight_log.txt from repo
4. Remove 840 lines dead IMAP code from main.py
5. Add caching to librarian queries

---

## SESSION HISTORY

| Session | Date | Key Changes |
|---------|------|-------------|
| 22 | Feb 2026 | Tool-calling engine (first version) |
| 23 | Feb 15 | Learning step, circular import fix, CC observation |
| 24 | Feb 15 | Air cargo tracker, general cargo polling, shipping routing, overnight audit |
| 25 | Feb 16 | Full code audit (22 bugs found), BL audit, cost analysis, documentation |
| 26 | Feb 16 | 10 critical bug fixes, tool integration, cost optimization |
| 27 | Feb 16 | Three-way cross-check, librarian rebuild, digest upgrade, justification engine |
| 28 | Feb 16 | Smart extraction, data pipeline, UK tariff, overnight brain, PC agent runner |

---

## COMMIT CONVENTION

```
Session XX: Brief description of what was done

# or for assignments:
Assignment XX: Brief description
```

Always end with:
```
Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```
