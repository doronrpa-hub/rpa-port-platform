# RPA-PORT Changelog

## Session 17 — February 12, 2026

### Knowledge Engine Audit
- Full code audit of librarian.py, librarian_index.py, librarian_researcher.py, enrichment_agent.py
- Confirmed `enrich_knowledge` in main.py was a dummy (logged stats, called nothing)
- Confirmed librarian_index, librarian_researcher, enrichment_agent never wired into main.py
- Created 6-phase wiring plan (`docs/WIRING_PLAN.md`)

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

### Documentation
- Created `docs/SESSION17_BACKUP.md` — session notes
- Created `docs/WIRING_PLAN.md` — 6-phase wiring plan
- Created `docs/FIRESTORE_INVENTORY.md` — 16,927 docs across 40 collections
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
