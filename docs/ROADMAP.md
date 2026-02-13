# RCB System Roadmap
## Living document -- updated every session
## Last updated: Session 19 (February 13, 2026)

---

## CLASSIFICATION PIPELINE (THE BRAIN)

- [x] Pre-classify from own knowledge (keyword_index 8,063, product_index 61, supplier_index 2, brain_index 11,254 keywords)
- [x] Agent 1 (Gemini Flash) extracts individual products (49 items from Chinese invoice!)
- [x] Agent 2 (Claude Sonnet 4.5) classifies with HS codes
- [x] Agents 3-5 (Gemini Flash) regulatory, FTA, risk
- [x] Agent 6 (Gemini Pro) synthesis in Hebrew
- [x] Quality gate catches garbage before sending (audit_before_send)
- [x] Brain learns from verified classifications
- [x] Gemini markdown fence stripping (```json fix)
- [x] Agent 1 Claude fallback when Gemini fails
- [ ] Brain should SKIP AI when 90%+ confident (not implemented)
- [ ] GPT as third opinion model
- [ ] Pupil devil's advocate (old code exists in pupil_v05_final.py, not wired)
- [ ] Inner loop: retry until 100% confident, not just once
- [ ] Cross-check between Claude vs Gemini vs GPT -- use consensus

---

## KNOWLEDGE & RULES

- [x] Tariff DB (11,753 entries)
- [x] Librarian index (12,595 docs)
- [x] Knowledge base (296 docs, all typed)
- [x] FTA agreements (21), regulatory requirements (28), classification rules (26)
- [x] Free Import Order API (gov.il)
- [x] deep_learn.py mines all professional docs ($0)
- [x] knowledge_indexer.py builds keyword index from tariff
- [x] enrich_knowledge.py reclassifies unknown docs
- [x] read_everything.py builds brain_index from ALL 26 collections
- [ ] Framework order rules (צו מסגרת) -- not parsed or checked
- [ ] Chapter heading validation rules
- [ ] Download and parse official tariff PDFs from shaarolami
- [ ] Download and parse Free Import Order PDFs from gov.il
- [ ] UK tariff cross-reference
- [ ] USA HTS cross-reference
- [ ] EU TARIC cross-reference

---

## DOCUMENT HANDLING

- [x] PDF OCR 300 DPI, Excel, Word, EML, MSG, TIFF, CSV, HTML, images, URLs
- [x] Document parser: 9 types (invoice, BL, packing list, AWB, cert of origin, EUR.1, health cert, insurance, DO)
- [x] Completeness scoring (0-100, missing critical fields)
- [x] Hebrew encoding fallback (Windows-1255)
- [ ] Image OCR (works in Cloud Functions via Vision API, fails locally)

---

## SHIPMENT TRACKING

- [x] document_tracker.py -- derives phase from documents
- [x] 9 import steps + 9 export steps
- [x] feed_parsed_documents maps 8 doc types
- [x] tracker_email.py -- TaskYam HTML progress emails
- [x] Wired into classification pipeline
- [ ] Automatic status updates when new docs arrive
- [ ] Container tracking via shipping line APIs
- [ ] Integration with port systems

---

## EMAIL (THE PRODUCT)

- [x] Sends classification response
- [x] Sends ack (now consolidated into single email)
- [x] Quality gate warning banner
- [ ] Threading (In-Reply-To headers added in #66, untested)
- [ ] Consolidation (3->1 email attempted in #66, untested)
- [ ] Professional Hebrew RTL layout
- [ ] Verification badges (built but not in email template)
- [ ] Confidence scores in email
- [ ] Tracker status in email
- [ ] Smart questions formatted in email
- [ ] "Reply 1, 2, or 3 to confirm" interactive classification
- [ ] Disable RCB System alert emails

---

## BATCH & LEARNING

- [x] batch_reprocess.py (dry-run, trade-only, source filter)
- [x] 345 docs processed, 16 classified, 38 learned
- [x] overnight_learn.bat (3-step, $0)
- [ ] Overnight batch never ran (office PC went to sleep)
- [ ] Gemini exponential backoff (429 rate limits)
- [ ] --gemini-only flag for batch (avoid Claude fallback cost)

---

## SILENT LEARNING

- [ ] CC emails silently classified (fix_silent_classify.py exists, not deployed)
- [ ] Learn from corrections when user replies with different HS code
- [ ] Watch sent folder for broker declarations (actual HS codes filed)

---

## WEB RESEARCH (PHASE D)

- [ ] PC Agent + Gemini web research
- [ ] Search supplier websites for product specs
- [ ] Search regulatory databases
- [ ] ChatGPT cross-check

---

## HS CODE FORMAT

- [ ] Display as Israeli format: xx.xx.xxxx.xx/x (e.g., 84.31.4390.00/0)
- [ ] Currently shows raw 8-digit: 84314390
- [ ] Check digit calculation

---

## API & COST

- Anthropic: ~$30 remaining
- Gemini: Free tier (hitting 429 rate limits)
- Gemini max_tokens was too low for Agent 1 (fixed: 2000 -> 4096)
- No retry/backoff logic on API failures
- [ ] Exponential backoff on 429s
- [ ] Cost tracking per email processed
- [ ] Monthly cost dashboard

---

## SYSTEM HEALTH (existing, working)

- [x] Monitor agent (every 5 min)
- [x] Health check (every 1 hour)
- [x] Inspector (daily report)
- [x] Self-test engine
- [x] Failed classification retry (every 6 hours)
- [x] Processed email cleanup (every 24 hours)
- [x] Sequential RCB ID system
- [x] GitHub Actions CI/CD with approval gate
- [x] Google Cloud Secret Manager

---

## DEAD CODE CLEANUP

- [ ] Remove disabled Gmail IMAP/SMTP code from main.py
- [ ] Remove disabled monitor_self_heal, monitor_fix_all, monitor_fix_scheduled
- [ ] Remove .backup_session* files from functions/lib/
- [ ] Remove patch files (patch_main.py, patch_smart_email.py, etc.)

---

## IDEAS (FUTURE)

### Multi-Tenant Support
- [ ] Separate Firestore collections per client
- [ ] Per-client API key management
- [ ] Client-specific classification rules
- [ ] Usage billing per client

### Advanced Classification
- [ ] Image-based product recognition (photos of goods)
- [ ] Multi-document correlation (match invoice to packing list to B/L)
- [ ] Historical pricing validation
- [ ] Automatic tariff rate lookup

### Compliance
- [ ] Automatic sanctions screening
- [ ] Dual-use goods detection
- [ ] AEO (Authorized Economic Operator) compliance checks
- [ ] Audit trail for all classification decisions

### Integration
- [ ] Direct submission to Israeli Customs (Shaar Olami)
- [ ] Shipping line API integration (container tracking)
- [ ] Bank document integration (letters of credit)
- [ ] Accounting system export
