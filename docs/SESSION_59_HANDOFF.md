# Session 59 Handoff — 24 February 2026

## What Was Done

### Task 1: Complete Data Map (Research Only)
Full audit of all data sources in `data_c3/`, `functions/data/`, `_ordinance_data.py`, `_framework_order_data.py`, and all Firestore collections in `librarian_index.py`.

**Key finding:** Most data is already parsed and wired. The ONE critical gap was:
- `_framework_order_data.py` (33 articles, 86KB) existed but was NOT connected to domain routing — FTA questions couldn't find צו מסגרת articles.

### Task 2: Wire Framework Order to Domain Routing (commit `19a5356`)
**Problem:** `get_articles_by_domain()` in `intelligence_gate.py` only searched `ORDINANCE_ARTICLES` from `_ordinance_data.py`. When domain was FTA_ORIGIN, it returned 0 articles.

**Fix:**
1. Added `source_fw_articles` field to `CUSTOMS_DOMAINS`:
   - `FTA_ORIGIN`: All 33 framework order articles
   - `CLASSIFICATION`: Articles 03-05 (GIR rules from צו מסגרת)
2. Extended `get_articles_by_domain()` to fetch from both `ORDINANCE_ARTICLES` and `FRAMEWORK_ORDER_ARTICLES`
3. Added `source_fw_articles` to `detect_customs_domain()` output
4. Updated `get_articles_by_ids()` to handle `fw_` prefix for framework order articles

**Result:** FTA_ORIGIN domain now returns 33 framework order articles. CLASSIFICATION domain gets GIR rules.

### Task 3: Fix BUG 1 — AI Must Quote Law Verbatim (commit `ef52b96`)
**Problem:** AI-composed replies paraphrased law text instead of quoting verbatim.

**Fix:** Strengthened both AI system prompts:
- `email_intent.py:REPLY_SYSTEM_PROMPT` — Now mandates `«סעיף X לפקודת המכס: [ציטוט מלא]»` format, covers both פקודת המכס and צו מסגרת, includes anti-fabrication and anti-broker-referral rules
- `knowledge_query.py` system prompt — Added same verbatim quoting mandate (was completely missing before)

### Task 4: BUG 2 — Email Threading (Already Fixed)
**Finding:** `_send_reply_safe()` already correctly uses `helper_graph_reply()` (Graph `/reply` endpoint) first for proper threading, with `helper_graph_send()` as fallback only. No code change needed.

### Task 5: Fix BUG 3 — Tracking Code in Knowledge Query Subject (commit `d1f9c4b`)
**Problem:** `knowledge_query.py` reply subjects had no tracking code — just `Re: {subject}` or `RCB | {preview}`.

**Fix:** Added `RCB-Q-YYYYMMDD-XXXXX` tracking code to all knowledge_query.py reply subjects, matching the pattern already used in `email_intent.py`.

## Files Modified

| File | Changes |
|------|---------|
| `functions/lib/intelligence_gate.py` | +`source_fw_articles` field on FTA_ORIGIN and CLASSIFICATION domains, extended `get_articles_by_domain()` to fetch from both ordinance + framework order data, propagated `source_fw_articles` through `detect_customs_domain()` output |
| `functions/lib/email_intent.py` | Strengthened `REPLY_SYSTEM_PROMPT` with mandatory verbatim quoting, anti-fabrication rules, covers both פקודת המכס and צו מסגרת |
| `functions/lib/knowledge_query.py` | Added verbatim law quoting mandate to system prompt, added tracking code to reply subjects |

## Git Commits (3 total, all pushed to origin/main)

| SHA | Description |
|-----|-------------|
| `19a5356` | Wire framework order (33 articles) into domain routing |
| `ef52b96` | Fix BUG 1: Mandate verbatim law quoting in AI reply prompts |
| `d1f9c4b` | Fix BUG 3: Add tracking code to knowledge_query.py reply subjects |

## Test Results
- **1,268 passed**, 0 failed, 0 skipped — zero regressions after all changes

## Data Map Summary

### Fully Wired (LIVE in production)

| Data Source | Size | Location | Tool |
|---|---|---|---|
| פקודת המכס (311 articles) | 286KB | `_ordinance_data.py` | `search_legal_knowledge` + domain routing |
| צו מסגרת (33 articles) | 86KB | `_framework_order_data.py` | `lookup_framework_order` + **domain routing (NEW)** |
| תעריף (11,753 entries) | Firestore | `tariff` | `search_tariff` |
| פרקי מכס (99 chapters) | Firestore | `chapter_notes` | `get_chapter_notes` |
| צו יבוא חופשי (6,121 HS codes) | Firestore | `free_import_order` | `check_regulatory` |
| צו יצוא חופשי (979 HS codes) | Firestore | `free_export_order` | `check_regulatory` |
| הנחיות סיווג (218 directives) | Firestore | `classification_directives` | `search_classification_directives` |
| Framework Order (85 docs) | Firestore | `framework_order` | `lookup_framework_order` |
| FTA Agreements (21 entries) | Firestore | `fta_agreements` | `lookup_fta` |
| Legal Knowledge (19 docs) | Firestore | `legal_knowledge` | `search_legal_knowledge` |

### Not Yet Wired (lower priority)

| Data Source | Status | Blocker |
|---|---|---|
| קודי הנחה (discount codes) | PC agent task pending | Requires browser download from shaarolami |
| נוהל סיווג (classification procedure) | PC agent task pending | Requires browser download from gov.il |
| נוהל הערכה (valuation procedure) | Download failed (redirect) | Needs browser |
| customs_procedures (2 PDFs downloaded) | In Firestore but not searchable | Needs tool wiring |
| FTA agreements (13 pending) | PC agent tasks created | Requires browser downloads |

## Domain Routing Coverage After Session 59

| Domain | Ordinance Articles | FW Articles | Firestore Tools |
|--------|:---:|:---:|:---:|
| CLASSIFICATION | — | 3 (GIR rules) | search_tariff, get_chapter_notes, run_elimination |
| VALUATION | 18 (arts 130-136) | — | search_legal_knowledge |
| IP_ENFORCEMENT | 14 (arts 200א-200יד) | — | search_legal_knowledge |
| FTA_ORIGIN | — | **33 (all)** | lookup_fta, lookup_framework_order |
| IMPORT_EXPORT | — | — | check_regulatory |
| PROCEDURES | 26 (arts 40-65א) | — | search_legal_knowledge |
| FORFEITURE_PENALTIES | 50+ (arts 190-223יח) | — | search_legal_knowledge |
| TRACKING | — | — | (uses tracker, not legal tools) |

## What to Do Next (Priority Order)

1. **Deploy to Firebase** — 3 commits pushed but not yet deployed to Cloud Functions
2. **Live test** — Send the 5 test emails from the routing spec (Part 10) to verify:
   - Classification: "DINING CHAIR"
   - IP: "עיכבו מכולה בטענת זיוף של Nike"
   - Valuation: "ערך עסקה לפי סעיף 132"
   - Classification + Regulatory: "יבוא תרופות מסין"
   - FTA: "מה שיעור המכס על יבוא רכב מגרמניה"
3. **Add missing IP articles 200ח-200יד** to `_ordinance_data.py` (from Session 58 handoff)
4. **Run local PC agent** → process 18 browser tasks (FTA agreements + procedures)
5. **Wire customs_procedures collection** to PROCEDURES domain search
6. **Consider paid Gemini tier** for production stability
