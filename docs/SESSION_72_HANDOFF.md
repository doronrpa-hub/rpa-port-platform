# Session 72 Handoff — Fix Candidates Table + Entity Extraction + FTA Info

**Date:** 2026-02-25
**Status:** Code changes complete, NOT deployed, NOT tested against Firestore

## What Happened With the 3 Test Emails (Pre-Session 72)

| # | Email | Intent Detected | Result | Problem |
|---|-------|----------------|--------|---------|
| 1 | מה פרט המכס למכונת קפה ביתית? | **Not detected** — fell to classification | Loop breaker triggered (3 prior attempts) | CUSTOMS_Q_PATTERNS didn't match "פרט המכס ל..." |
| 2 | מה צריך כדי לייבא צעצועים לישראל? | KNOWLEDGE_QUERY | Got answer with law citations but **NO HS candidates table** | "מה צריך" didn't match CUSTOMS_Q_PATTERNS; _handle_knowledge_query had no candidates table |
| 3 | מה שיעור המכס על יבוא גבינה מהאיחוד האירופי? | **Not detected** — fell to classification | Loop breaker triggered | "שיעור המכס" not in CUSTOMS_Q_PATTERNS |

## Root Causes Found

1. **CUSTOMS_Q_PATTERNS too narrow** — only matched `מה הסיווג|המכס|התעריף|קוד מכס|המס`. Missed `פרט מכס`, `שיעור מכס`, `מה צריך כדי לייבא`, `מכס על יבוא`
2. **_extract_customs_entities() too narrow** — only found product after `של|עבור|on|for`. Missed `למכונת קפה` (ל prefix), `לייבא צעצועים`, `יבוא גבינה`
3. **_handle_knowledge_query had NO candidates table** — only _handle_customs_question appended candidates HTML
4. **_handle_customs_question skipped tariff search** when product_desc was empty (line 1414: `if product_desc or hs_code:`)
5. **No FTA info HTML section** — FTA data was passed to AI context but never rendered as a structured table
6. **"גבינה" missing from product indicators** in intelligence_gate.py

## 9 Fixes Implemented (in code, NOT deployed)

### Fix 1: CUSTOMS_Q_PATTERNS expanded (email_intent.py)
Added 6 new patterns:
- `פרט\s*(?:ה?מכס|מכסי)` — "פרט המכס"
- `שיעור\s*(?:ה?מכס|מכסי)` — "שיעור המכס"
- `מה\s*(?:פרט|שיעור)\s*(?:ה?מכס)` — "מה פרט המכס"
- `מה\s*(?:צריך|נדרש)\s*(?:כדי\s*)?(?:ליבא|לייבא)` — "מה צריך כדי לייבא"
- `(?:ליבא|לייבא)\s+.{3,}?\s*(?:ל?ישראל|\?)` — "לייבא צעצועים לישראל?"
- `מכס\s+על\s+(?:יבוא|ייבוא)` — "מכס על יבוא"

### Fix 2: _extract_customs_entities() rewritten (email_intent.py)
Replaced single regex with 7 ordered patterns + 1 fallback:
1. `פרט המכס ל...` / `פרט מכסי של...`
2. `שיעור המכס על יבוא...`
3. `לייבא X` / `ליצא X`
4. `יבוא X מ...`
5. `מכס על יבוא X`
6. `של X` / `עבור X` / `for X`
7. `סיווג X` / `לסווג X`
8. Fallback: `מה צריך כדי לייבא X`

**Verified locally:** All 3 test emails now extract correct product descriptions:
- Coffee → `מכונת קפה ביתית`
- Toys → `צעצועים`
- Cheese → `גבינה מהאיחוד האירופי`

### Fix 3: ALWAYS search tariff (email_intent.py)
Changed `_handle_customs_question` line ~1577:
- **Before:** `if product_desc or hs_code:` (skipped when both empty)
- **After:** `tariff_query = product_desc or hs_code or body_text[:200]` (always searches)

### Fix 4: Candidates table enhanced (email_intent.py)
- Table header changed to dark blue (#1B4F72) with white text
- Added bold "פרטי מכס אפשריים:" title above table
- Added `_build_clarification_html()` — product-specific clarification questions

### Fix 5: Product-specific clarification questions (email_intent.py)
New `_build_clarification_html(product_desc)` function generates targeted questions:
- **Coffee:** סוג המכונה, ביתית/מסחרית, עם מטחנה, מדינת מקור
- **Toys:** סוג הצעצוע, חומר, גיל יעד, מדינת מקור
- **Cheese:** סוג הגבינה, אחוז שומן, מדינת מקור, תעודת EUR.1
- **Vehicles:** סוג, נפח מנוע, חדש/משומש, מדינת ייצור
- **Textiles:** סוג הבגד, חומר, מין, סרוג/ארוג
- **Default:** חומר גלם, שימוש מיועד, מדינת מקור

### Fix 6: Candidates table added to _handle_knowledge_query (email_intent.py)
- Added `tariff_candidates = []` capture in tariff search section
- Added `should_search_tariff = True` for IMPORT_EXPORT_REQUIREMENTS domain too
- Added product description extraction from question text via regex
- Appends `_build_candidates_table_html()` after AI reply text
- Appends `_build_fta_info_html()` after candidates table

### Fix 7: FTA info HTML builder (email_intent.py)
New `_build_fta_info_html(fta_result, tariff_candidates, product_desc)`:
- Green background (#D4EDDA) section with agreement name
- Table: פרט מכס | תיאור | מכס רגיל (MFN) | מכס [agreement]
- Origin proof requirement note (EUR.1 / חשבון הצהרה)
- Condition note: "השיעור המופחת מותנה בהצגת תעודת מקור"
- Framework order clause text if available
- Wired into BOTH `_handle_customs_question` AND `_handle_knowledge_query`

### Fix 8: "גבינה" added to product indicators (intelligence_gate.py)
Added to `_PRODUCT_INDICATORS_HE`: גבינה, חמאה, יוגורט, שוקולד, ממתק, עוגה, לחם

### Fix 9: Loop breaker entries cleared (Firestore)
Deleted 9 documents:
- 6 rcb_processed entries (3 test emails × 2 processing cycles)
- 1 questions_log entry
- 2 email_quality_log entries

## Local Test Results (intent detection only, no Firestore)

| Email | Intent | Confidence | Product Extracted | Domains Detected |
|-------|--------|-----------|-------------------|-----------------|
| מכונת קפה ביתית | CUSTOMS_QUESTION | 0.85 | מכונת קפה ביתית | CLASSIFICATION (15), PROCEDURES (10) |
| צעצועים לישראל | CUSTOMS_QUESTION | 0.85 | צעצועים | IMPORT_EXPORT_REQUIREMENTS (30), CLASSIFICATION (5) |
| גבינה מהאיחוד האירופי | CUSTOMS_QUESTION | 0.85 | גבינה מהאיחוד האירופי | FTA_ORIGIN (30), PROCEDURES (10), CLASSIFICATION (5) |

**Unit tests:** 80 passed, 0 failed (test_email_intent.py)

## Files Modified

| File | Changes |
|------|---------|
| `functions/lib/email_intent.py` | +6 CUSTOMS_Q_PATTERNS, rewritten _extract_customs_entities (7 patterns + fallback), ALWAYS search tariff, _build_clarification_html(), _build_fta_info_html(), candidates table in _handle_knowledge_query, FTA HTML in both handlers |
| `functions/lib/intelligence_gate.py` | +7 product indicators (גבינה, חמאה, יוגורט, שוקולד, ממתק, עוגה, לחם) |

## What Was NOT Done (next session MUST do)

### 1. Full test suite NOT run
Only ran `test_email_intent.py` (80 tests). Need full `python -m pytest tests/ -x -q`.

### 2. NOT deployed to Firebase
All changes are local only. Need `firebase deploy --only functions`.

### 3. NOT committed to git
Need `git add` + `git commit` for the 2 modified files.

### 4. Firestore tariff search NOT tested
Did not verify that `search_tariff("מכונת קפה")` returns real candidates from production Firestore. The handler will search — but results depend on Firestore data quality.

### 5. FTA lookup NOT tested against Firestore
Did not verify that `lookup_fta(origin_country="גבינה מהאיחוד האירופי")` returns eligible=True with EU agreement. The `_build_fta_info_html` will silently return "" if FTA lookup returns nothing.

### 6. No new test emails sent
Doron should send 3 NEW test emails (different subjects to avoid any residual dedup):
1. **"שאלה על סיווג - מכונת קפה"**
2. **"שאלה על ייבוא - צעצועים"**
3. **"שאלה על מכס - גבינה מאירופה"**

## Expected Reply Structure After Deployment

### Coffee Reply Should Contain:
1. AI-composed Hebrew text about coffee machine classification
2. **Candidates table** with HS codes from heading 8419 or 8516 (coffee machines)
3. **Clarification questions:** סוג המכונה, ביתית/מסחרית, עם מטחנה, מדינת מקור

### Toys Reply Should Contain:
1. AI-composed text about import requirements (law citations)
2. **Candidates table** with HS codes from heading 9503 (toys)
3. **Clarification questions:** סוג הצעצוע, חומר, גיל יעד, מדינת מקור

### Cheese Reply Should Contain:
1. AI-composed text about duty rates
2. **Candidates table** with HS codes from chapter 04 (dairy)
3. **FTA info section** (green) with EU agreement, preferential rate, EUR.1 requirement
4. **Clarification questions:** סוג הגבינה, אחוז שומן, מדינת מקור, תעודת EUR.1

## Verification Checklist for Next Session
- [ ] Run full test suite
- [ ] Commit changes
- [ ] Deploy to Firebase
- [ ] Send 3 test emails
- [ ] Verify each reply has candidates table
- [ ] Verify each reply has clarification questions
- [ ] Verify cheese reply has FTA info section
- [ ] Verify NO shipment table (כיוון, הובלה, מוכר, קונה)
- [ ] Verify NO "לא הצלחנו לסווג"
- [ ] Verify Nike test still works (KNOWLEDGE_QUERY → IP articles)

## Architecture Note — Intent Detection Priority

The detection order in `detect_email_intent()` is:
1. ADMIN_INSTRUCTION (regex, ADMIN only)
2. NON_WORK (regex)
3. INSTRUCTION (regex)
4. **CUSTOMS_QUESTION (regex)** ← now catches more patterns
5. STATUS_REQUEST (regex + entities)
6. KNOWLEDGE_QUERY (question + domain keywords)

The key fix: questions that previously fell through to step 6 (KNOWLEDGE_QUERY) now match at step 4 (CUSTOMS_QUESTION), which has proper product entity extraction and candidates table support. KNOWLEDGE_QUERY handler also now has candidates table as a safety net.
