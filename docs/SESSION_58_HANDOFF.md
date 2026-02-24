# Session 58 Handoff — 24 February 2026

## What Was Done

### Intelligence Gates Extended to email_intent.py (Phase 2 from Routing Spec)

Session 57 built intelligence gates (HS validation, loop breaker, banned phrases) but they only protected `classification_agents.py`. Legal questions going through `email_intent.py` handlers (`_handle_customs_question`, `_handle_knowledge_query`) had ZERO protection — no banned phrase filtering, no domain-aware routing, just flat keyword search across all 311 ordinance articles.

### 3 Changes Implemented

#### 1. Banned Phrase Filter on ALL Outgoing Emails (commit `3c70504`)

**Problem:** AI-composed replies from email_intent could contain "consult a customs broker", "unable to classify", etc.

**Fix:** Added `filter_banned_phrases()` call inside `_send_reply_safe()` — the single chokepoint for ALL email_intent.py replies. Every handler (customs question, knowledge query, status, admin, instruction, non-work, clarification, cache hits) now passes through the banned phrase filter before sending.

**Location:** `email_intent.py:630-636` — fail-open, try/except wrapped.

#### 2. Domain Detection — 8 Customs Domains (commit `3c70504`)

**New function:** `detect_customs_domain(text)` in `intelligence_gate.py`

Pure Python keyword matching (no AI call). Detects which area of customs law a question belongs to, returning sorted list by confidence score.

| Domain | Hebrew Keywords | Source Articles |
|--------|----------------|-----------------|
| CLASSIFICATION | סיווג, פרט מכס, תעריף | None (uses tariff DB) |
| VALUATION | הערכה, ערך עסקה, שווי, מחיר | 130-136 (17 articles) |
| IP_ENFORCEMENT | זיוף, סימן מסחר, עיכוב, קניין רוחני | 200א-200יד (14 articles) |
| FTA_ORIGIN | הסכם סחר, מקור, EUR.1, העדפה | None (uses framework_order tools) |
| IMPORT_EXPORT_REQUIREMENTS | רישיון, צו יבוא, צו יצוא | None (uses FIO/FEO) |
| PROCEDURES | נוהל, תש"ר, שחרור, רשימון | 40-65א (26 articles) |
| FORFEITURE_PENALTIES | חילוט, קנס, עבירה, הברחה | 190-223יח (50+ articles) |
| TRACKING | מעקב, אונייה, מכולה | None (uses tracker) |

Multi-domain detection supported: "Nike counterfeit detained" matches both IP_ENFORCEMENT and TRACKING.

#### 3. Source Routing — Domain-Aware Article Retrieval (commit `3c70504`)

**New functions:**
- `get_articles_by_domain(domain_result)` — fetches ordinance articles by ID from `_ordinance_data.py`
- `get_articles_by_ids(article_ids)` — convenience wrapper for direct article lookup

**Wired into both handlers:**
- `_handle_customs_question()` — now detects domain FIRST, fetches targeted articles, supplements with tool calls
- `_handle_knowledge_query()` — same domain-aware routing, only falls back to flat keyword search if domain detection found no articles

**Helper functions added to email_intent.py:**
- `_detect_domains_safe(text)` — fail-open wrapper around `detect_customs_domain()`
- `_fetch_domain_articles(detected_domains)` — fetches articles from all detected domains, dedupes, caps at 20

### What This Changes in Practice

**Before (flat keyword search):**
```
"עיכבו מכולה בטענת זיוף של Nike"
→ keyword search "זיוף" across 311 articles
→ finds article 204 (חילוט, word match on "זיוף")
→ AI writes answer based on penalty article, NOT the actual IP procedure
```

**After (domain-aware routing):**
```
"עיכבו מכולה בטענת זיוף של Nike"
→ detect_customs_domain() → IP_ENFORCEMENT (score=10)
→ fetch articles 200א-200ז directly (all IP enforcement articles)
→ AI writes answer with:
  - 200א: Detention authority + 3 business day timeline
  - 200ב: Guarantee requirements
  - 200ג: Infringing goods = prohibited
  - Full Hebrew law text injected as context
```

### Verified Test Results

| Test | Input | Expected | Result |
|------|-------|----------|--------|
| IP enforcement | "עיכבו מכולה בטענת זיוף של Nike" | IP_ENFORCEMENT → articles 200א+ | 7 articles fetched |
| Valuation | "ערך עסקה לפי סעיף 132" | VALUATION → articles 130-136 | 17 articles fetched |
| FTA | "תעודת מקור EUR.1 הסכם סחר" | FTA_ORIGIN → framework tools | Correct tools selected |
| Penalties | "עבירת מכס חמורה הברחת סחורה" | FORFEITURE_PENALTIES → 190+ | 10+ articles fetched |
| Banned phrases | "מומלץ לפנות לעמיל מכס" | Replaced with RCB contact | Correctly replaced |

## Files Created
| File | Lines | Purpose |
|------|-------|---------|
| `functions/tests/test_domain_routing.py` | 280 | 49 tests: domain detection, article retrieval, banned phrases, integration |

## Files Modified
| File | Changes |
|------|---------|
| `functions/lib/intelligence_gate.py` | +208 lines: CUSTOMS_DOMAINS dict, detect_customs_domain(), get_articles_by_domain(), get_articles_by_ids(), product indicators |
| `functions/lib/email_intent.py` | +338/-88 lines: banned phrase filter in _send_reply_safe(), _detect_domains_safe(), _fetch_domain_articles(), domain-aware _handle_customs_question and _handle_knowledge_query |

## Git Commits
| SHA | Description |
|-----|-------------|
| `3c70504` | Session 58: Intelligence gates for email_intent — domain detection, source routing, banned phrases |

## Test Results
- **1,268 passed**, 0 failed, 0 skipped (was 1,219, +49 new tests)

## Data Gaps Discovered

### Missing IP Articles in _ordinance_data.py
Articles 200ח through 200יד (7 of 14 IP articles) do NOT exist in `_ordinance_data.py`. Only 200א-200ז are present. This means IP domain routing returns 7 articles instead of 14.

**Root cause:** Session 53 parsed `pkudat_mechess.txt` which may not have contained the newer IP provisions (some were added in 2024 amendments).

**Fix needed:** Add articles 200ח-200יד to `_ordinance_data.py` with correct Hebrew text. These cover:
- 200ח: Simplified destruction procedure for small quantities
- 200ט: Costs and expenses
- 200י: Bond/guarantee requirements
- 200יא: Rights holder liability for wrongful detention
- 200יב: Customs immunity from liability
- 200יג: Application to patents and designs
- 200יד: Regulations authority

### Domain Detection Could Be Richer
The current detection is pure keyword matching. Future improvements:
- Article number detection (e.g., "סעיף 132" → VALUATION)
- Entity-based detection (e.g., "Nike" → product → CLASSIFICATION bonus)
- Negation handling (e.g., "לא זיוף" should NOT trigger IP)

## What to Do Next (Priority Order)

### Immediate
1. **Add missing IP articles 200ח-200יד** to `_ordinance_data.py` — check if source text exists in pkudat_mechess.txt or legal_documents collection
2. **Live test** — send the 5 test emails from the spec (Part 10) and verify domain routing in production logs
3. **Deploy** to Firebase

### Phase 3 from Intelligence Routing Spec
4. Classification with legal basis — cite GIR rules and chapter notes in output
5. Automatic regulatory check — after classification, auto-check צו יבוא/יצוא
6. FTA integration — after classification, check applicable FTAs
7. Cross-reference engine — combine multiple sources per query

### Other Pending
- Run local PC agent → process 18 browser tasks (FTA agreements + procedures)
- Consider adding article number detection to domain detection (e.g., "סעיף 200ב" → IP_ENFORCEMENT directly)
- Consider paid Gemini tier for production stability

## Architecture Summary After Session 58

### Intelligence Gates Coverage

| Component | HS Validation | Loop Breaker | Banned Phrases | Domain Routing |
|-----------|:---:|:---:|:---:|:---:|
| classification_agents.py | Yes (Session 57) | Yes (Session 57) | Yes (Session 57) | No (uses elimination engine) |
| email_intent.py — all handlers | N/A | N/A | **Yes (Session 58)** | **Yes (Session 58)** |
| knowledge_query.py (fallback) | N/A | N/A | No | No |
| tracker_email.py | N/A | N/A | No (not AI-composed) | N/A |

### Email Flow After Session 58

```
Email arrives
  → detect_email_intent() → CUSTOMS_QUESTION or KNOWLEDGE_QUERY
  → detect_customs_domain(text) → [IP_ENFORCEMENT, TRACKING, ...]
  → get_articles_by_domain() → [200א, 200ב, ...] (targeted retrieval)
  → Supplement: search_tariff, check_regulatory, lookup_fta (domain-aware)
  → Fallback: flat keyword search ONLY if domain detection found nothing
  → _compose_reply() → AI writes answer WITH targeted article context
  → filter_banned_phrases() → removes "consult a broker" etc.
  → _send_reply_safe() → sends to @rpa-port.co.il only
```
