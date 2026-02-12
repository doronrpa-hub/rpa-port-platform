# RPA-PORT Code Audit — Generated February 11, 2026

## 1. Library Files (`functions/lib/`)

| File | Description |
|------|-------------|
| `clarification_generator.py` | Generates professional Hebrew requests for missing information in customs documents |
| `classification_agents.py` | Multi-agent classification system querying Firestore for Israeli tariff data and ministry requirements |
| `document_tracker.py` | Tracks shipment documents and identifies current phase plus missing documents |
| `enrichment_agent.py` | Continuous knowledge enrichment agent for import/export/customs procedures with PC Agent delegation |
| `incoterms_calculator.py` | Calculates CIF value components based on Incoterms and determines missing documents |
| `invoice_validator.py` | Validates commercial invoices according to Israeli customs regulations |
| `knowledge_query.py` | Handles knowledge queries from team members by consulting Librarian and Researcher |
| `language_tools.py` | Language engine: vocabulary, spelling, grammar, letter structure, and style learning for Hebrew customs text |
| `librarian.py` | Central knowledge manager for the RCB system: indexing, tagging, smart search, and researcher integration |
| `librarian_index.py` | Document indexing and inventory manager that scans and catalogs all Firestore collections |
| `librarian_researcher.py` | Continuously searches database and web for knowledge gaps, geo-tags Israeli vs foreign sources |
| `librarian_tags.py` | Complete Israeli customs and trade document tagging system (import, export, procedures, legal) |
| `pc_agent.py` | Browser-based file download and upload integration for sites requiring JavaScript or cookies |
| `pdf_creator.py` | Classification report generator with proper Hebrew RTL and mixed English/numbers support |
| `product_classifier.py` | Detects product category from text and determines required documents for customs clearance |
| `rcb_email_processor.py` | Smart email processor: checks today's emails, avoids duplicates, sends acknowledgments and reports |
| `rcb_helpers.py` | Helper functions for Graph API, PDF text extraction with OCR fallback, and Hebrew name handling |
| `rcb_id.py` | Generates human-readable sequential IDs for every email entering the RCB system |
| `rcb_inspector.py` | Autonomous system health and intelligence agent with database, process, flow, and monitor inspection |
| `rcb_orchestrator.py` | Integration layer connecting all RCB modules, orchestrates the complete shipment processing workflow |
| `rcb_self_test.py` | Self-test engine: sends test emails, processes them, verifies results, and logs test reports |

---

## 2. Cloud Functions (`main.py`)

### Scheduler Functions (9)

| Function | Schedule | Status | Description |
|----------|----------|--------|-------------|
| `check_email_scheduled` | every 5 min | **DISABLED** | Gmail IMAP fallback (consolidated into rcb_check_email) |
| `rcb_check_email` | every 2 min | ACTIVE | Main email handler — Graph API, processes rcb@rpa-port.co.il |
| `enrich_knowledge` | every 1 hour | ACTIVE | Fills knowledge gaps, checks stale enrichment sources |
| `monitor_agent` | every 5 min | ACTIVE | System monitor, auto-fixes known issues |
| `rcb_cleanup_old_processed` | every 24 hours | ACTIVE | Deletes rcb_processed docs older than 7 days |
| `rcb_retry_failed` | every 6 hours | ACTIVE | Retries failed classifications from last 24 hours |
| `rcb_health_check` | every 1 hour | ACTIVE | System health check + email alerts |
| `monitor_fix_scheduled` | every 5 min | **DISABLED** | Consolidated into rcb_check_email |
| `rcb_inspector_daily` | daily 15:00 IST | ACTIVE | Daily inspection + email report to doron@rpa-port.co.il |

### Firestore Triggers (2)

| Function | Trigger | Description |
|----------|---------|-------------|
| `on_new_classification` | `classifications/{classId}` created | Auto-classify using knowledge base |
| `on_classification_correction` | `classifications/{classId}` updated | Learns from user corrections |

### HTTP Endpoints (10)

| Function | Status | Description |
|----------|--------|-------------|
| `api` | ACTIVE | REST API for web app (stats, classifications, knowledge, inbox, sellers, learning) |
| `rcb_api` | ACTIVE | RCB API (health, logs, test, backup, backups) |
| `monitor_agent_manual` | ACTIVE | Manual monitor trigger |
| `monitor_self_heal` (v1) | **DISABLED** | Dead code (redefined below) |
| `monitor_self_heal` (v2) | **DISABLED** | Consolidated into rcb_check_email |
| `monitor_fix_all` | **DISABLED** | Consolidated into rcb_check_email |
| `test_pdf_ocr` | ACTIVE | Test PDF extraction with OCR |
| `test_pdf_report` | ACTIVE | Test PDF report generation |
| `rcb_self_test` | ACTIVE | Self-test engine — sends test emails, verifies, cleans up |
| `rcb_inspector` | ACTIVE | Full system inspection — manual trigger |

**Totals:** 21 functions (17 active, 4 disabled)

---

## 3. Firestore Collections

### Core Data
| Collection | Used In | Description |
|------------|---------|-------------|
| `classifications` | main.py, rcb_inspector.py | Active customs classifications (pending, confirmed, corrected) |
| `rcb_classifications` | classification_agents.py, librarian_researcher.py, main.py, patch_classification.py, rcb_inspector.py | Classification results from RCB pipeline |
| `classification_knowledge` | enrichment_agent.py, librarian_researcher.py, rcb_inspector.py | Classification knowledge store |
| `classification_rules` | classification_agents.py | HS classification rules |
| `knowledge_base` | enrichment_agent.py, librarian_researcher.py, main.py, rcb_inspector.py, rcb_self_test.py | Central knowledge base (HS codes, products, sellers) |
| `knowledge_queries` | knowledge_query.py, rcb_inspector.py | Team knowledge query log |
| `sellers` | main.py | Known sellers and their HS codes |
| `declarations` | main.py | Customs declarations |
| `regulatory_certificates` | main.py | Regulatory certs (EMC, RF, safety) |

### Email & Communication
| Collection | Used In | Description |
|------------|---------|-------------|
| `inbox` | main.py, patch_main.py, patch_smart_email.py | Email inbox records (Gmail path) |
| `rcb_processed` | main.py, rcb_inspector.py, rcb_self_test.py, clear_processed.py, fix_email_check.py, rcb_diagnostic.py, add_backup_api.py | Processed email dedup tracking |
| `rcb_logs` | main.py, add_followup_trigger.py | RCB activity logs |
| `rcb_first_emails` | (referenced) | First email tracking |
| `rcb_inbox` | (referenced) | RCB email inbox |
| `rcb_pdf_requests` | (referenced) | PDF generation requests |
| `rcb_stats` | (referenced) | RCB statistics |

### Librarian & Search
| Collection | Used In | Description |
|------------|---------|-------------|
| `librarian_index` | librarian.py, librarian_index.py, librarian_researcher.py, librarian_tags.py | Master librarian index |
| `librarian_search_log` | librarian.py, librarian_researcher.py | Librarian search history |
| `librarian_enrichment_log` | librarian_index.py, librarian_researcher.py, rcb_self_test.py | Librarian enrichment activity |
| `librarian_tags` | librarian_tags.py | Document tagging system |

### Reference Data
| Collection | Used In | Description |
|------------|---------|-------------|
| `tariff` | classification_agents.py, librarian.py | Israeli tariff database |
| `tariff_chapters` | librarian.py | Tariff chapter index |
| `hs_code_index` | librarian.py | HS code lookup index |
| `ministry_index` | classification_agents.py | Ministry requirements index |

### Task Queues
| Collection | Used In | Description |
|------------|---------|-------------|
| `agent_tasks` | main.py | AI classification and enrichment task queue |
| `enrichment_tasks` | rcb_inspector.py | Enrichment task queue |
| `pc_agent_tasks` | enrichment_agent.py, pc_agent.py | PC agent task queue |
| `pending_tasks` | main.py | General pending tasks |

### System & Meta
| Collection | Used In | Description |
|------------|---------|-------------|
| `system_status` | main.py, rcb_inspector.py | Health check status |
| `system_state` | rcb_email_processor.py | System state store |
| `system_counters` | rcb_id.py | Sequential ID counters |
| `monitor_errors` | main.py | Monitor error log |
| `enrichment_log` | main.py | Enrichment source check log |
| `learning_log` | main.py | Classification learning events |
| `config` | patch_main.py | System configuration |

### Backup & Reports
| Collection | Used In | Description |
|------------|---------|-------------|
| `session_backups` | main.py, add_backup_api.py | Session backup storage |
| `session_missions` | rcb_inspector.py | Session mission tracking |
| `sessions_backup` | rcb_inspector.py | Sessions backup (alt) |
| `rcb_inspector_reports` | rcb_inspector.py | Inspector report history |
| `rcb_test_reports` | rcb_self_test.py | Self-test report log |

**Total: 38 active collections** (excludes test/unused collections like books, hamburgers, etc.)

---

## 4. External APIs

### Anthropic (Claude) API
- **URL:** `https://api.anthropic.com/v1/messages`
- **Model:** `claude-sonnet-4-20250514`
- **Used in:** `classification_agents.py:172`, `add_multi_agent_system.py:33`, `add_multiagent_safe.py:17`, `test_real.py:14`, `test_classification.py:19`
- **Purpose:** Document classification (Agent 2), fallback for all agents when Gemini fails

### Google Gemini API
- **URL:** `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- **Models:** `gemini-2.5-flash` (Agents 1,3,4,5,6), `gemini-2.5-pro` (unused after quota fix)
- **Used in:** `classification_agents.py:213`
- **Purpose:** Cost-optimized AI for extraction, regulatory, FTA, risk, and synthesis tasks

### Microsoft Graph API
| Endpoint | Method | Used in | Purpose |
|----------|--------|---------|---------|
| `login.microsoftonline.com/{tenant}/oauth2/v2.0/token` | POST | `rcb_helpers.py:221` | OAuth2 token exchange |
| `graph.microsoft.com/v1.0/users/{email}/mailFolders/inbox/messages` | GET | `rcb_helpers.py:238`, `main.py:1064` | Get inbox messages |
| `graph.microsoft.com/v1.0/users/{email}/messages/{id}/attachments` | GET | `rcb_helpers.py:250` | Get email attachments |
| `graph.microsoft.com/v1.0/users/{email}/messages/{id}` | PATCH | `rcb_helpers.py:259` | Mark message as read |
| `graph.microsoft.com/v1.0/users/{email}/sendMail` | POST | `rcb_helpers.py:267` | Send emails |
| `graph.microsoft.com/v1.0/users/{email}/messages/{id}/forward` | POST | `main.py:944` | Forward emails |
| `graph.microsoft.com/v1.0/users/{email}/messages/{id}` | DELETE | `rcb_self_test.py:246` | Delete test emails |
| `graph.microsoft.com/v1.0/users/{email}/mailFolders/sentitems/messages` | GET | `rcb_self_test.py:267` | Get sent items for cleanup |

### Google Cloud Secret Manager
- **Client:** `secretmanager.SecretManagerServiceClient()`
- **Used in:** `main.py:31`, `move_get_secret.py:9`, `test_classification.py:1`, `test_graph.py:2`
- **Project:** `rpa-port-customs`

### Firebase / Google Cloud
- **Firestore:** `firestore.client()` — Database operations (lazy-initialized via `get_db()`)
- **Storage:** `storage.bucket()` — File storage (lazy-initialized via `get_bucket()`)
- **Used in:** `main.py:46-60`

### Gmail SMTP (Legacy — DISABLED)
- **URL:** `smtp.gmail.com:465`
- **Used in:** `main.py:110,149,320`, `patch_smart_email.py:168,207`
- **Status:** Superseded by Microsoft Graph API

### Gmail IMAP (Legacy — DISABLED)
- **URL:** `imap.gmail.com`
- **Used in:** `main.py:191,195`
- **Status:** Superseded by Microsoft Graph API

---

## 5. Secret Manager Keys

| Secret Name | Purpose | Critical | Files |
|-------------|---------|----------|-------|
| `ANTHROPIC_API_KEY` | Claude API authentication | YES | main.py, classification_agents.py, knowledge_query.py, rcb_inspector.py, rcb_helpers.py, + 6 more |
| `GEMINI_API_KEY` | Google Gemini API authentication | NO (optional) | classification_agents.py, test_real.py |
| `RCB_GRAPH_CLIENT_ID` | Microsoft Graph OAuth client ID | YES | main.py, rcb_helpers.py, fix_missing_functions.py, test_graph.py, + 4 more |
| `RCB_GRAPH_CLIENT_SECRET` | Microsoft Graph OAuth client secret | YES | main.py, rcb_helpers.py, fix_missing_functions.py, test_graph.py, + 4 more |
| `RCB_GRAPH_TENANT_ID` | Microsoft Azure tenant ID | YES | main.py, rcb_helpers.py, fix_missing_functions.py, test_graph.py, + 4 more |
| `RCB_EMAIL` | RCB inbox email address | YES | main.py, rcb_helpers.py, rcb_inspector.py, rcb_self_test.py, + 7 more |
| `RCB_PASSWORD` | Legacy email password | NO (unused) | rcb_helpers.py, fix_missing_functions.py |
| `RCB_FALLBACK_EMAIL` | Fallback email (default: airpaort@gmail.com) | NO | main.py, add_backup_api.py, rcb_helpers.py |

**Retrieval function:** `get_secret(name)` in `main.py:28-39`
**Bulk retrieval:** `get_rcb_secrets_internal(get_secret_func)` in `rcb_helpers.py:205-216`

---

## 6. Environment Variables & GitHub Actions Secrets

### GitHub Actions Secrets (`.github/workflows/deploy.yml`)

| Secret | Purpose |
|--------|---------|
| `GCP_SA_KEY` | Raw JSON service account key for `google-github-actions/auth@v2` |

### GitHub Actions Environment Variables (set in workflow)

| Variable | Value | Purpose |
|----------|-------|---------|
| `GOOGLE_APPLICATION_CREDENTIALS` | `${{ steps.auth.outputs.credentials_file_path }}` | GCP credentials file path (auto-set by auth action) |
| `GCLOUD_PROJECT` | `rpa-port-customs` | GCP project ID for gcloud CLI |
| `GOOGLE_CLOUD_PROJECT` | `rpa-port-customs` | GCP project ID for client libraries |
| `FIREBASE_CONFIG` | `{"projectId":"rpa-port-customs"}` | Firebase project config |

### Hardcoded Infrastructure Identifiers

| Identifier | Value | Where |
|------------|-------|-------|
| GCP Project ID | `rpa-port-customs` | main.py, deploy.yml, multiple test files |
| Firebase Storage Bucket | `rpa-port-customs.appspot.com` | pc_agent.py |
| RCB Email (default) | `rcb@rpa-port.co.il` | main.py, rcb_helpers.py |
| Fallback Email (default) | `airpaort@gmail.com` | main.py, add_backup_api.py |
| Master Alert Email | `doron@rpa-port.co.il` | main.py:1440 |
| Allowed Sender Domain | `@rpa-port.co.il` | main.py:1098 |
