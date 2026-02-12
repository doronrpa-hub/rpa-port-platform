# RPA-PORT Architecture Decisions

## AD-01: Multi-Model AI Routing (Session 15)

**Decision:** Use Gemini Flash for simple agents, Claude Sonnet for core classification.

**Context:** All 6 agents were using Claude Sonnet 4 at $0.21/email. At 15 emails/day, that's ~$95/month in API costs alone.

**Options considered:**
1. All Claude — best quality but expensive
2. All Gemini — cheapest but lower quality for complex classification
3. Hybrid — Claude for core task, Gemini for simple tasks

**Chosen:** Option 3. Agent 2 (HS Classification) stays on Claude because classification accuracy is the core business value. Agents 1, 3, 4, 5, 6 handle extraction and lookup tasks where Gemini Flash performs equally well.

**Result:** ~$0.05/email (~75% cost reduction). Automatic fallback to Claude if Gemini fails.

---

## AD-02: Lazy Initialization for Firestore/Storage (Session 15)

**Decision:** Use `get_db()` / `get_bucket()` lazy initialization instead of module-level `db = firestore.client()`.

**Context:** Firebase CLI analyzes function code at deploy time by importing `main.py`. The module-level `firestore.client()` call attempted a real connection during import, causing timeouts in CI/CD environments (GitHub Actions and local Windows PC).

**Options considered:**
1. try/except wrapper around initialization
2. Lazy initialization with getter functions
3. Environment variable flag to skip initialization

**Chosen:** Option 2. Clean, no special environment handling needed. Every `db.` reference replaced with `get_db().` (66+ replacements).

---

## AD-03: Microsoft Graph API over Gmail (Session ~8)

**Decision:** Replace Gmail IMAP/SMTP with Microsoft Graph API for all email operations.

**Context:** Gmail IMAP had reliability issues and app password management complexity. The company email is on Microsoft 365.

**Result:** OAuth2 token exchange, full email lifecycle (read, send, forward, delete), attachment handling. Gmail paths kept as disabled fallback code.

---

## AD-04: GitHub Actions CI/CD over Cloud Shell (Session 15)

**Decision:** Deploy via GitHub Actions with approval gate instead of manual Cloud Shell deployment.

**Context:** Manual deployment required opening Cloud Shell, pulling code, running `firebase deploy`. Error-prone and not auditable.

**Pipeline:** Push → pytest → approval gate → Firebase deploy.

**Auth:** `google-github-actions/auth@v2` with raw JSON service account key stored as GitHub secret (`GCP_SA_KEY`).

---

## AD-05: Google Cloud Secret Manager (Session ~5)

**Decision:** Store all API keys and credentials in Secret Manager, not environment variables or Firestore config.

**Context:** Early versions stored email credentials in Firestore `config/email` document. API keys were in environment variables.

**Result:** 8 secrets centrally managed. Single `get_secret(name)` function in `main.py`. Bulk retrieval via `get_rcb_secrets_internal()`.

---

## AD-06: 6-Agent Pipeline Architecture (Session ~7)

**Decision:** Split classification into 6 specialized agents instead of one monolithic prompt.

**Agents:**
1. Document extraction — parse invoice/packing list
2. HS Classification — determine tariff code
3. Regulatory — check ministry requirements
4. FTA — Free Trade Agreement eligibility
5. Risk — risk assessment
6. Synthesis — Hebrew report generation

**Why:** Each agent has a focused prompt and can use different AI models. Failures in one agent don't break the entire pipeline. Results are combined by the orchestrator.

---

## AD-07: Hebrew RTL PDF Generation (Session 9)

**Decision:** Use ReportLab with custom Hebrew RTL handling for classification reports.

**Context:** Standard PDF libraries don't handle Hebrew right-to-left text mixed with English/numbers properly.

**Result:** `pdf_creator.py` handles bidirectional text, proper alignment, and mixed-language content.

---

## AD-08: Sequential RCB IDs (Session 13.1)

**Decision:** Generate human-readable sequential IDs (not UUIDs) for every email entering the system.

**Context:** Firestore auto-generated IDs are not human-readable. Staff need to reference emails by simple numbers.

**Implementation:** `system_counters` collection in Firestore with atomic increment. Format: `RCB-XXXX`.

---

## AD-09: Consolidation of Email Processors (Session 13.1)

**Decision:** Consolidate 4 separate email processing functions into single `rcb_check_email`.

**Context:** Multiple overlapping scheduled functions were causing duplicate processing and email floods. Functions `check_email_scheduled`, `monitor_fix_scheduled`, `monitor_self_heal` (v1 & v2), and `monitor_fix_all` had redundant logic.

**Result:** Single entry point, clearer dedup logic, disabled functions kept as dead code reference.

---

## AD-10: Gemini Flash over Gemini Pro for Agent 6 (Session 15)

**Decision:** Switch Agent 6 (Hebrew synthesis) from Gemini Pro to Gemini Flash.

**Context:** Gemini Pro hit 429 quota errors on free tier. Hebrew text synthesis doesn't require Pro-level quality.

**Result:** No quality degradation observed. Eliminates quota errors without needing a paid Gemini plan.
