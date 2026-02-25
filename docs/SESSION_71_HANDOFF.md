# Session 71 Handoff — Fix Intent Detection: Questions vs Shipments

**Date:** 2026-02-25
**Status:** Complete, tested, ready to deploy

## Problem
When `doron@rpa-port.co.il` sends a customs question to rcb@, the system correctly detects CUSTOMS_QUESTION intent and builds an answer, but if `_send_reply_safe()` fails (returns `status="send_failed"`), main.py only checked for `('replied', 'cache_hit', 'clarification_sent')` — so `send_failed` fell through to the classification pipeline, which extracted 0 items and sent a "לא הצלחנו לסווג" failure banner.

## 5 Fixes Implemented

### Fix 1: main.py:993 — Never fall through to classification when intent detected
- **Before:** Only `('replied', 'cache_hit', 'clarification_sent')` statuses triggered `continue`
- **After:** ANY detected intent (except INSTRUCTION+classify) blocks classification fallthrough
- Handles `send_failed`, `routed`, or any other status from intent handlers
- Still allows INSTRUCTION with action='classify' to fall through (correct behavior)

### Fix 2: intelligence_gate.py:388 — Add 6 missing banned phrases
Added to `BANNED_PHRASES`:
- `"לא הצלחנו לסווג"` — exact string from `_build_unclassified_banner`
- `"לא הצלחנו לקבוע"`
- `"אין מספיק מידע"`
- `"פנה ליועץ מכס"` / `"פנו ליועץ מכס"`
- `"consult a customs agent"`

### Fix 3: classification_agents.py:1713-1719 — Replace unclassified banner
- **Before:** Red background, "⚠️ לא הצלחנו לסווג את הפריטים" (failure admission)
- **After:** Amber background, "⚠️ נדרש מידע נוסף לסיווג מדויק" (clarification request)
- Requests specific info: חומר גלם, שימוש מיועד, הרכב, משקל/נפח

### Fix 4: email_intent.py — Candidates table in CUSTOMS_QUESTION replies
- New `_build_candidates_table_html(candidates, product_desc)` helper
- Builds structured HTML table with columns: #, פרט מכס, תיאור מתעריף, שיעור מכס
- Appended to AI-composed reply when tariff candidates found
- Makes reply useful even when AI composition produces minimal text

### Fix 5: email_intent.py — Send failure logging
- Both `_handle_customs_question` and `_handle_knowledge_query` now log warnings when `_send_reply_safe` returns False
- Includes sender address and subject for debugging

## Files Modified

| File | Changes |
|------|---------|
| `functions/main.py:993` | Intent fallthrough logic — catch all intents, not just replied |
| `functions/lib/intelligence_gate.py:388` | +6 banned phrases |
| `functions/lib/classification_agents.py:1713` | Rewrite unclassified banner — amber, clarification language |
| `functions/lib/email_intent.py` | +`_build_candidates_table_html()`, +tariff_candidates capture, +candidates table in reply, +send failure logging in both handlers |

## What Was NOT Changed
- Nike test flow (KNOWLEDGE_QUERY → IP_ENFORCEMENT) — untouched
- CC email path (silent observe) — untouched
- All 33+ tools — untouched
- Tracker emails — untouched
- Classification pipeline for documents/invoices — untouched

## Test Results
- **1268 passed**, 0 failed, 0 skipped — zero regressions

## Verification Checklist
- [x] No remaining "לא הצלחנו לסווג" in output HTML templates (only in banned phrases list + old .backup file)
- [x] CUSTOMS_QUESTION intent blocks classification fallthrough (Fix 1)
- [x] KNOWLEDGE_QUERY intent blocks classification fallthrough (Fix 1)
- [x] send_failed status blocks classification fallthrough (Fix 1)
- [x] INSTRUCTION+classify still falls through to classification (preserved)
- [x] 1268 tests pass
