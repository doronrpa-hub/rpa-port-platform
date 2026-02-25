# Session 70 Handoff — 2026-02-25

## Nike Test Results (TASK 1)

**Email sent:** 2026-02-25 11:45 UTC (13:45 Israel time)
**Subject:** בדיקה - עיכוב מכולת Nike
**Body:** יש לי יבואן שהביא מכולה ובה בגדים של Nike, במכס עיכבו בטענה שמדובר בזיוף. מה אומר החוק?

### What happened:
- Domain detection: **IP_ENFORCEMENT** (score 20) — CORRECT
- Intent: **KNOWLEDGE_QUERY** — CORRECT
- 5 articles fetched: 200א (2078 chars), 200ב (741), 200ג (73), 200ד (81), 200ה (67)
- Sources used: `ordinance_targeted`, `tariff`, `xml_documents`
- **compose_model: `template`** — Both ChatGPT AND Gemini Flash FAILED (API keys not available in cloud?), fell back to template

### Nike Test Scorecard:
| Check | Result | Notes |
|-------|--------|-------|
| Cites articles 200א-200ה | PARTIAL | Only cited 200א — template truncated at 800 chars |
| Quotes actual Hebrew law text | YES | Full text of 200א(1) about 3-day detention |
| Does NOT say "המכס אינו עוסק" | YES | No contradiction |
| Has RCB tracking code | NOT CHECKED | No `status` field in questions_log |
| Talks about clothes (בגדים) | NO | Template reply is raw data dump, not AI-composed |

### Root cause of partial failure:
1. **AI composition failed** — both ChatGPT and Gemini Flash returned None
2. Template fallback truncated to 800 chars, cutting off articles 200ב-200ה
3. Template output was raw "להלן המידע שנמצא במערכת:" instead of structured answer

## What Was Fixed (Session 70)

### 1. REPLY_SYSTEM_PROMPT rewritten (email_intent.py)
New 5-section structure enforced:
1. **תשובה ישירה** — Direct answer (2-3 sentences)
2. **ציטוט מהחוק** — Verbatim law quote with «סעיף X: [full text]»
3. **הסבר בעברית פשוטה** — Plain-language explanation
4. **מידע נוסף** — Practical steps, timelines, rates
5. **English Summary** — Brief translation at bottom

### 2. Template fallback fixed (email_intent.py)
- Was: truncate to 800 chars, raw dump
- Now: structured article blocks (1500 chars each), separator between articles
- All 5 IP articles now fit in template output

### 3. Article context budget fixed (email_intent.py)
- Was: `full_text_he[:2000]` — first article ate all the space
- Now: `6000 // n_articles` — distributed evenly (1200 chars each for 5 articles)

### 4. XML documents search wired for ALL domains (email_intent.py)
| Domain | XML Category | Before | After |
|--------|-------------|--------|-------|
| FTA_ORIGIN | fta | ✓ | ✓ |
| IMPORT_EXPORT_REQUIREMENTS | regulatory | ✓ | ✓ |
| CLASSIFICATION | tariff | ✗ | ✓ |
| VALUATION | legal | ✗ | ✓ |
| IP_ENFORCEMENT | legal | ✗ | ✓ |
| PROCEDURES | legal | ✗ | ✓ |
| FORFEITURE_PENALTIES | legal | ✗ | ✓ |

### 5. Domain detection keywords improved (intelligence_gate.py)
- **FTA_ORIGIN**: Added "אירופי", "שיעור המכס", "הסכם", "מכס מופחת", "פטור ממכס", "eu", "european union", "duty rate"
- **IMPORT_EXPORT_REQUIREMENTS**: Added "לייבא", "ייבוא", "לייצא", "ייצוא", "מה צריך", "מה נדרש"

### 6. knowledge_query.py prompt updated
Same 5-section structure applied to Claude-based knowledge query handler.

### 7. Regulatory search added for import domains (email_intent.py)
When IMPORT_EXPORT_REQUIREMENTS or CLASSIFICATION detected, HS code in question triggers `check_regulatory` tool.

## Domain Detection Test Results (after fixes)

| Test | Email Text | Top Domain | Score | Correct? |
|------|-----------|-----------|-------|----------|
| Nike IP | בגדים של Nike, עיכבו בטענת זיוף | IP_ENFORCEMENT | 20 | ✓ |
| FTA Cheese EU | שיעור המכס על גבינה מהאיחוד האירופי | FTA_ORIGIN | 30 | ✓ (was PROCEDURES) |
| Classification Coffee | מייבא מכונת קפה, מה פרט המכס | PROCEDURES+CLASS | 10+5 | ✓ (both triggered) |
| Import Req Toys | מה צריך כדי לייבא צעצועים | IMPORT_EXPORT_REQ | 20 | ✓ (was CLASS only) |
| Valuation | איך קובעים ערך טובין למכס | VALUATION | 10 | ✓ |

## Files Modified

| File | Changes |
|------|---------|
| `functions/lib/email_intent.py` | +145/-66: New prompt, template fix, article budget, XML routing, regulatory search, AI prompt reinforcement |
| `functions/lib/intelligence_gate.py` | +10/-3: FTA keywords, import/export keywords |
| `functions/lib/knowledge_query.py` | +53/-27: New 5-section prompt, user prompt reinforcement |

## Git Commit
- `53e12b7` — session 70: reply quality — 5-section format, all domains, template fix

## Test Results
- **1,268 passed**, 0 failed, 0 skipped — zero regressions

## Deployment
- Firebase deploy triggered (all 28+ functions)

## Known Issues

1. **AI composition failing in cloud** — `compose_model: template` for the Nike test means BOTH ChatGPT and Gemini Flash returned None. Likely cause: API keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`) not available in Secret Manager or expired. **This is the #1 issue** — even with perfect prompts, template output is inferior to AI-composed answers.

2. **Classification domain detection weak** — "מכונת קפה" (coffee machine) hits PROCEDURES first because "מייבא" matches. CLASSIFICATION only at 5. Not a real problem since both domains are searched, but product indicators could be stronger.

3. **Gemini free tier quota** — If Gemini hits 429 in cloud, both AI paths fail. Need paid tier or Claude fallback in _compose_reply.

## Test Emails for Doron

### Test 1 (re-test Nike — should now have ALL 5 articles):
```
Subject: בדיקה - עיכוב מכולת Nike
Body: יש לי יבואן שהביא מכולה ובה בגדים של Nike, במכס עיכבו בטענה שמדובר בזיוף. מה אומר החוק?
```

### Test 2 (FTA — cheese from EU):
```
Subject: שאלה - מכס על גבינה
Body: מה שיעור המכס על יבוא גבינה מהאיחוד האירופי?
```

### Expected Results:
- **Nike**: All 5 articles (200א-200ה) cited, detention process explained, guarantee requirements mentioned
- **FTA**: EU agreement referenced, dairy tariff rates, framework order clause cited

## Next Session Priorities

1. **Fix AI composition in cloud** — check OPENAI_API_KEY and GEMINI_API_KEY in Secret Manager. If missing/expired, add them. This is critical — template fallback is not acceptable for production.
2. **Add Claude as third AI fallback** in `_compose_reply()` — use existing `call_claude()` from knowledge_query.py when ChatGPT + Gemini both fail
3. **Test FTA and Classification domains** end-to-end with real emails
4. **Consider paid Gemini tier** — free tier quota exhaustion is causing all Gemini calls to fail
5. **Add CLASSIFICATION keywords** — "פרט מכס", "מה הפרט", "סיווג מכס" should boost CLASSIFICATION score
