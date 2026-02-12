# RPA-PORT Changelog

## Session 18 — February 12, 2026

### Intelligence Module
- Created `functions/lib/intelligence.py` — the system's own brain, pure Firestore lookups, zero AI cost
- `pre_classify(db, desc, origin)` — searches classification_knowledge, classification_rules, tariff DB for candidate HS codes before AI
- `lookup_regulatory(db, hs_code)` — ministry/permit requirements by HS chapter from Firestore
- `lookup_fta(db, hs_code, origin)` — FTA eligibility lookup with country name normalization (English + Hebrew)
- `validate_documents(text, direction, has_fta)` — detects 11 document types (invoice, packing list, BL, EUR.1, etc.) via regex patterns
- Wired into `classification_agents.py`: runs BEFORE AI agents, injects context into Agent 2 prompt
- Intelligence results included in synthesis context and final return value

### Phase B: Free Import Order API Integration
- Added `query_free_import_order(db, hs_code)` to intelligence.py
- Queries live Ministry of Economy API (`apps.economy.gov.il/Apps/FreeImportServices`)
- Searches main endpoint + parent HS codes (requirements inherit from chapter-level parents)
- Returns: authorities (name, department, phone, email, website), legal requirements, decree version
- Cached in Firestore (`free_import_cache` collection, 7-day TTL)
- Falls back to stale cache on API errors
- Wired into pipeline: after Agent 2 classifies, queries API for each HS code (up to 3)
- Official requirements included in Agent 6 synthesis context
- Files changed: `intelligence.py`, `classification_agents.py`

### Phase C: Ministry Routing Logic
- Added `_MINISTRY_ROUTES` — 25 HS chapter entries with ministries, required documents, procedures, risk levels
- Added `_CHAPTER_ALIASES` — maps related chapters to canonical routes (e.g., chapters 51–63 → textiles)
- Added `route_to_ministries(db, hs_code, free_import_result=None)` — merges 3 sources:
  1. Built-in routing table (hardcoded ministry URLs, documents, procedures)
  2. Firestore baseline (`ministry_index` collection)
  3. Official Free Import Order API result (live authorities)
- Returns: risk_level, ministries list (name, URL, documents, procedure, official flag), summary_he
- Wired into pipeline: runs after FIO query, results in Agent 6 synthesis context and return value
- Files changed: `intelligence.py`, `classification_agents.py`

### Phase D: Document Parser
- Created `functions/lib/document_parser.py` — per-document type identification, structured field extraction, completeness assessment
- `identify_document_type(text, filename)` — weighted keyword scoring (strong=3, medium=2, weak=1, filename=2 bonus) across 9 document types
- Document types: commercial_invoice, packing_list, bill_of_lading, air_waybill, certificate_of_origin, eur1, health_certificate, insurance, delivery_order
- `extract_structured_fields(text, doc_type)` — dedicated regex extractors per type (invoice fields, BL fields, AWB fields, etc.)
- `assess_document_completeness(extracted_fields, doc_type)` — weighted scoring (critical=3, important=2, optional=1), returns score, missing fields list, Hebrew field names
- `parse_document(text, filename)` — convenience wrapper combining all 3 steps
- `parse_all_documents(extracted_text)` — splits multi-document text on `=== filename ===` markers from rcb_helpers, parses each
- Bilingual patterns (Hebrew + English) for all field extraction
- Wired into `classification_agents.py`: runs after Agent 1 extraction, before intelligence pre-classify
- Parsed document types, extracted fields, and completeness warnings included in synthesis context and final return value
- Files changed: `document_parser.py`, `classification_agents.py`

### Phase E: Knowledge Indexer
- Created `functions/knowledge_indexer.py` — one-time job to build inverted indexes from all Firestore knowledge
- `build_keyword_index()` — reads ALL tariff (11,753), tariff_chapters, hs_code_index, classification_knowledge entries; builds keyword → HS code inverted index with weights
  - Hebrew + English keywords extracted and indexed
  - Weight scoring: chapter descriptions 2x, corrections 3x bonus, high-usage items +1–2x
  - Top 20 HS codes stored per keyword
- `build_product_index()` — reads classification_knowledge + rcb_classifications + classifications; maps product description → HS code with confidence and usage count
- `build_supplier_index()` — reads sellers + rcb_classifications + classifications; maps supplier name → list of HS codes they typically ship (with count and last_seen)
- Stores in Firestore: `keyword_index`, `product_index`, `supplier_index` collections
- Supports `--dry-run` and `--stats-only` modes; stores run metadata in `system_metadata`
- Wired into `intelligence.py` `pre_classify()`:
  - New Step 1: `_search_keyword_index()` — fast O(keywords) Firestore lookups instead of scanning 11,753 tariff docs
  - New Step 2: `_search_product_index()` — exact/prefix product match
  - New Step 3: `_search_supplier_index()` — supplier-based HS hints (lower confidence, boosts existing candidates)
  - Old tariff scan kept as fallback if keyword_index not yet built
  - `pre_classify()` now accepts optional `seller_name` parameter
- `classification_agents.py` updated: passes `seller_name` from invoice to `pre_classify()`
- Files changed: `knowledge_indexer.py`, `intelligence.py`, `classification_agents.py`

### Smart Question Engine
- Created `functions/lib/smart_questions.py` — elimination-based clarification, no AI cost
- `analyze_ambiguity()` — detects chapter conflicts, duty rate spread, regulatory divergence, confidence gaps
- `should_ask_questions()` — decides if clarification is needed (triggers on: chapter conflict, duty spread >= 4%, low confidence, near-equal candidates)
- `generate_smart_questions()` — builds questions referencing specific HS codes, duty rates, and ministry requirements
  - 12 chapter-pair distinction hints (84/85 machinery vs electronics, 61/62 knitted vs woven, etc.)
  - Includes: material questions, origin country with FTA implications, missing document requests, regulatory divergence warnings
- `format_questions_html()` — styled RTL HTML block for email inclusion
- `format_questions_he()` — plain text format
- Wired into `classification_agents.py`:
  - Runs after ministry routing, before synthesis agent
  - Questions included in synthesis context (Agent 6 aware of ambiguity)
  - Questions rendered in HTML email report
  - Auto-sets email status to CLARIFICATION when questions generated
  - Ambiguity info (reason, question count) saved to Firestore `rcb_classifications`
- Files changed: `smart_questions.py`, `classification_agents.py`

---

## Session 17 — February 12, 2026

### Knowledge Engine Audit
- Full code audit of librarian.py, librarian_index.py, librarian_researcher.py, enrichment_agent.py
- Confirmed `enrich_knowledge` in main.py was a dummy (logged stats, called nothing)
- Confirmed librarian_index, librarian_researcher, enrichment_agent never wired into main.py
- Created 6-phase wiring plan (`docs/WIRING_PLAN.md`)

### Phase 0: Document Extraction Overhaul
- OCR DPI raised from 150 to 300 for better accuracy
- Added image preprocessing before OCR (grayscale, contrast 1.5x, sharpen) via Pillow
- Replaced `len > 50` quality check with `_assess_extraction_quality()` (Hebrew, Latin, digit ratios)
- Improved pdfplumber table extraction with `[TABLE]` structure tags
- Added `_cleanup_hebrew_text()` for common OCR typos
- Added `_tag_document_structure()` — regex detection of invoice#, HS codes, BL/AWB, countries, amounts, incoterms
- Added multi-format support: Excel (.xlsx/.xls), Word (.docx), email (.eml), URL detection
- Files changed: `rcb_helpers.py`, `requirements.txt`

### Phase 1: Build the Index
- Ran `rebuild_index()` — populated `librarian_index` with 12,595 documents from 20 collections
- `smart_search()` now hits the index first instead of slow per-collection scanning

### Phase 2: Wire Learning into Pipeline
- Added `create_enrichment_agent` import to `classification_agents.py` (with try/except)
- After each classification save, calls `on_classification_complete()` and `on_email_processed()`
- System now learns HS codes, suppliers, and products from every processed email
- Zero API cost — Firestore reads/writes only

### Phase 3: Replace Dummy Enrichment Scheduler
- Replaced no-op `enrich_knowledge` in `main.py` with real `EnrichmentAgent`
- Now runs: `check_and_tag_completed_downloads()`, `run_scheduled_enrichments()`, `get_learning_stats()`
- Activates 23 enrichment task types (tariff updates, ministry procedures, FTAs, etc.)
- Zero API cost — generates tasks and queries, no AI calls

### Phase A: Baseline Knowledge Import
- Created `functions/data/fta_agreements.json` — 21 FTA agreements with country codes, origin proof, preferential rates
- Created `functions/data/regulatory_requirements.json` — 28 HS chapter groups mapped to ministries
- Created `functions/data/classification_rules.json` — 11 GIR principles + 15 keyword patterns
- Created `functions/import_knowledge.py` — imports all 3 JSONs into Firestore
- Imported 150 documents: 21 fta_agreements, 28 regulatory_requirements, 75 ministry_index, 26 classification_rules
- All entries marked `verified: false` — system will verify against official sources over time

### 6 Extraction Fixes
1. Fixed `_assess_extraction_quality` — no longer rejects text-only documents (certificates, EUR.1, letters) that lack numbers
2. Added `_extract_from_msg()` for Outlook .msg files via `extract-msg` library; split .eml/.msg handling
3. Added TIFF support (multi-page OCR via PIL), CSV/TSV (with Hebrew encoding fallback), HTML (strip script/style/tags)
4. Wired `email_body` from Graph API through `process_and_send_report` into `extract_text_from_attachments` — URLs in email body now detected
5. Added `_try_decode()` helper — tries utf-8, windows-1255, iso-8859-8, latin-1 for Israeli government files
6. Added extraction summary logging (file count, total chars, 100-char preview per file)
- Updated `test_non_pdf_skipped` to expect CSV content instead of empty string
- Files changed: `rcb_helpers.py`, `classification_agents.py`, `main.py`, `requirements.txt`, `test_rcb_helpers.py`

### Documentation
- Created `docs/SESSION17_BACKUP.md` — session notes
- Created `docs/WIRING_PLAN.md` — 6-phase wiring plan
- Created `docs/FIRESTORE_INVENTORY.md` — 16,927 docs across 40 collections
- Created `docs/MASTER_PLAN.md` — single source of truth, supersedes all previous session docs
- Created `docs/SYSTEM.md`, `docs/CHANGELOG.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`

---

## Session 15 — February 11, 2026

### Multi-Model Optimization (Claude + Gemini)
- Added Gemini 2.5 Flash for Agents 1, 3, 4, 5, 6 (95% cheaper per call)
- Kept Claude Sonnet 4 for Agent 2 (HS Classification — best quality)
- Added automatic fallback: Gemini fails → Claude takes over
- Added `GEMINI_API_KEY` to Secret Manager
- Switched Agent 6 from Gemini Pro to Gemini Flash (free tier quota issue)
- **Cost reduction: ~$0.21 → ~$0.05 per email (~75% savings)**

### CI/CD Pipeline
- Created `.github/workflows/deploy.yml` (GitHub Actions)
- Two-stage: test (pytest) → approval gate → Firebase deploy
- Uses `google-github-actions/auth@v2` with service account key
- Added `GCP_SA_KEY` to GitHub secrets

### Lazy Initialization Fix
- Changed `db = firestore.client()` to lazy `get_db()` pattern
- Changed `bucket = storage.bucket()` to lazy `get_bucket()` pattern
- Fixed Firebase CLI timeout during deploy (both local and CI)

### Claude Code on Office PC
- Installed Git, Claude Code, Google Cloud SDK, Firebase CLI
- Cloned repo to `C:\Users\doron\rpa-port-platform`

### Documentation
- Created `docs/CODE_AUDIT.md` — full system audit
- Created `docs/SESSION15_BACKUP.md` — session notes

---

## Session 14 — February 2026

### Language Tools v4.1.0
- Hebrew spell checker and grammar engine
- VAT calculation fix
- HS code 10-digit format support
- Letter structure analysis
- Style analyzer and language learner

---

## Session 13.1 — February 2026

### Email Processing Consolidation
- Disabled 4 redundant email processors
- Consolidated all email processing into `rcb_check_email` only

### Tag System Fix
- Added 30 missing tag definitions (fixed 50 broken references)

### RCB ID System
- Added sequential human-readable ID generator
- Narrowed all monitor time windows to 2 hours (stopped email flood)

### Self-Test Fix
- Fixed safe_id hash mismatch in self-test guard

---

## Session 11 — February 2026

### Email Subject Standardization
- Standardized English subject line with tracking code

### HS Validation
- HS code validation and formatting
- VAT set to 18% (Israeli standard)

---

## Session 10 — February 2026

### Israeli HS Format
- Implemented XX.XX.XXXXXX/X format (Israeli standard)
- Invoice validation working (score: 80/100)
- Module 4: Origin determination
- Module 5: Invoice validator
- Module 6: Orchestrator

---

## Session 9 — February 2026

### PDF & Testing
- PDF OCR fix for scanned documents
- 66 unit tests added
- PDF report generation (Hebrew RTL)
- GitHub Actions CI pipeline (initial version)

---

## Initial Commit

- RPA-PORT platform with 5 Cloud Functions
- Command Center HTML interface
- Basic email processing and classification
