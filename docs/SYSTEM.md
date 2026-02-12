# RPA-PORT System Architecture

## Overview

RPA-PORT is an AI-powered customs brokerage platform built for R.P.A. PORT LTD, an Israeli customs broker. The system automatically processes incoming emails with shipping documents, classifies goods using HS codes, checks regulatory requirements, and generates classification reports — all in Hebrew.

## Architecture

```
Email (rcb@rpa-port.co.il)
  → Microsoft Graph API (OAuth2)
    → Cloud Function: rcb_check_email (every 2 min)
      → PDF extraction (pdfplumber + OCR fallback)
        → 6-Agent Classification Pipeline
          → Firestore (results + knowledge)
            → PDF Report (Hebrew RTL)
              → Email reply to sender
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Google Cloud Functions (Python 3.12) |
| Database | Google Firestore (38 collections) |
| Storage | Google Cloud Storage |
| Email | Microsoft Graph API (OAuth2) |
| AI — Core | Claude Sonnet 4 (Anthropic) |
| AI — Cost-optimized | Gemini 2.5 Flash (Google) |
| Secrets | Google Cloud Secret Manager |
| CI/CD | GitHub Actions → Firebase Deploy |
| PDF Generation | ReportLab (Hebrew RTL support) |
| OCR | Google Cloud Vision API |

## 6-Agent Classification Pipeline

Each incoming email with shipping documents goes through 6 AI agents in sequence:

| Agent | Task | Model | Why |
|-------|------|-------|-----|
| 1 | Document extraction | Gemini Flash | Simple extraction, cheap |
| 2 | HS Classification | Claude Sonnet 4 | Core task, needs best quality |
| 3 | Regulatory check | Gemini Flash | Rule-based lookup, cheap |
| 4 | FTA (Free Trade Agreement) | Gemini Flash | Rule-based lookup, cheap |
| 5 | Risk assessment | Gemini Flash | Pattern matching, cheap |
| 6 | Hebrew synthesis | Gemini Flash | Text generation, cheap |

If any Gemini call fails, it automatically falls back to Claude.

**Cost per email: ~$0.05** (down from $0.21 with all-Claude)

## Cloud Functions (21 total)

### Scheduled (7 active)
- `rcb_check_email` — Main email processor (every 2 min)
- `enrich_knowledge` — Fill knowledge gaps (every 1 hour)
- `monitor_agent` — System monitor + auto-fix (every 5 min)
- `rcb_cleanup_old_processed` — Delete old dedup records (every 24 hours)
- `rcb_retry_failed` — Retry failed classifications (every 6 hours)
- `rcb_health_check` — Health check + email alerts (every 1 hour)
- `rcb_inspector_daily` — Daily inspection report (15:00 IST)

### Firestore Triggers (2)
- `on_new_classification` — Auto-classify on new document
- `on_classification_correction` — Learn from user corrections

### HTTP Endpoints (8 active)
- `api` — REST API for web app
- `rcb_api` — RCB system API
- `monitor_agent_manual` — Manual monitor trigger
- `test_pdf_ocr` — Test PDF extraction
- `test_pdf_report` — Test PDF report generation
- `rcb_self_test` — Self-test engine
- `rcb_inspector` — Full system inspection

## Library Modules (21 files in `functions/lib/`)

### Core Pipeline
- `classification_agents.py` — 6-agent classification with multi-model routing
- `rcb_email_processor.py` — Email intake, dedup, acknowledgment
- `rcb_orchestrator.py` — Orchestrates the full processing workflow
- `rcb_helpers.py` — Graph API, PDF extraction, Hebrew name handling

### Classification Support
- `product_classifier.py` — Product category detection
- `incoterms_calculator.py` — CIF value calculation
- `invoice_validator.py` — Israeli customs invoice validation
- `document_tracker.py` — Shipment document tracking
- `clarification_generator.py` — Hebrew requests for missing info

### Knowledge System
- `librarian.py` — Central knowledge manager (search, index, tags)
- `librarian_index.py` — Document indexing and catalog
- `librarian_researcher.py` — Knowledge gap research (DB + web)
- `librarian_tags.py` — Israeli customs tagging system
- `enrichment_agent.py` — Continuous knowledge enrichment
- `knowledge_query.py` — Team knowledge queries

### Output & Reporting
- `pdf_creator.py` — Hebrew RTL PDF report generation
- `language_tools.py` — Hebrew spelling, grammar, style engine

### System
- `rcb_id.py` — Sequential ID generator
- `rcb_inspector.py` — System health and intelligence
- `rcb_self_test.py` — Automated self-testing
- `pc_agent.py` — Browser-based file operations

## Infrastructure

| Resource | Value |
|----------|-------|
| GCP Project | `rpa-port-customs` |
| Firebase Bucket | `rpa-port-customs.appspot.com` |
| Email Address | `rcb@rpa-port.co.il` |
| Fallback Email | `airpaort@gmail.com` |
| Alert Email | `doron@rpa-port.co.il` |
| GitHub Repo | `doronrpa-hub/rpa-port-platform` |

## Deployment

```
Edit code (Claude Code on PC)
  → git push to GitHub
    → GitHub Actions runs pytest
      → Tests pass → waits for approval
        → Doron approves → deploys to Firebase
```

Fallback: Cloud Shell → `cd rpa-port-platform && git pull && firebase deploy --only functions`
