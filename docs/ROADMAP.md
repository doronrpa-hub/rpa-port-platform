# RPA-PORT Roadmap

## Status Legend
- **DONE** — Completed and deployed
- **READY** — Code exists, not yet wired into main pipeline
- **PLANNED** — Designed, not yet coded
- **IDEA** — Under consideration

---

## Completed

### Core Pipeline (DONE)
- [x] Email intake via Microsoft Graph API
- [x] PDF text extraction with OCR fallback
- [x] 6-agent classification pipeline
- [x] Multi-model routing (Claude + Gemini)
- [x] Hebrew RTL PDF report generation
- [x] Email reply with classification report
- [x] Automatic fallback (Gemini → Claude)

### Knowledge System (DONE)
- [x] Librarian — central knowledge manager
- [x] Librarian index — document catalog
- [x] Librarian researcher — knowledge gap research
- [x] Librarian tags — Israeli customs tagging
- [x] Enrichment agent — continuous learning
- [x] Knowledge queries — team Q&A

### System Health (DONE)
- [x] Monitor agent (every 5 min)
- [x] Health check (every 1 hour)
- [x] Inspector (daily report)
- [x] Self-test engine
- [x] Failed classification retry (every 6 hours)
- [x] Processed email cleanup (every 24 hours)

### Infrastructure (DONE)
- [x] GitHub Actions CI/CD with approval gate
- [x] Google Cloud Secret Manager
- [x] Lazy initialization for CI/CD compatibility
- [x] Sequential RCB ID system
- [x] Cost optimization (75% API cost reduction)

---

## Next Up

### Pupil Agent (READY — needs wiring)
- [ ] Wire `pupil_v05_final.py` into `main.py`
- [ ] Phase A: Observe all processed emails, extract knowledge patterns
- [ ] Phase B: Identify knowledge gaps and inconsistencies
- [ ] Phase C: Challenge the system — test classification accuracy against learned data
- **File:** `functions/lib/pupil_v05_final.py` (exists but not imported)

### Tracker Agent (READY — needs wiring)
- [ ] Wire `tracker.py` into `main.py`
- [ ] Apply crash fix from `fix_tracker_crash.py` (None check for import_proc/export_proc)
- [ ] Track shipment lifecycle: document received → classified → declared → cleared
- [ ] Status dashboard per shipment
- **Files:** `functions/lib/tracker.py`, `functions/lib/fix_tracker_crash.py`

---

## Planned

### Multi-Model Monitoring
- [ ] Track per-agent success rates (Claude vs Gemini)
- [ ] Track per-agent latency and cost
- [ ] Dashboard showing model performance comparison
- [ ] Auto-switch agents if one model degrades

### Classification Accuracy
- [ ] Track correction rate per HS chapter
- [ ] Identify weak classification areas
- [ ] Targeted knowledge enrichment for low-accuracy categories
- [ ] Confidence score in reports

### Web Dashboard
- [ ] Classification inbox with status filters
- [ ] Knowledge base browser
- [ ] System health dashboard
- [ ] Cost tracking and API usage graphs

### Dead Code Cleanup
- [ ] Remove disabled Gmail IMAP/SMTP code from `main.py`
- [ ] Remove disabled `monitor_self_heal`, `monitor_fix_all`, `monitor_fix_scheduled`
- [ ] Remove `.backup_session*` files from `functions/lib/`
- [ ] Remove patch files (`patch_main.py`, `patch_smart_email.py`, etc.)

---

## Ideas

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
