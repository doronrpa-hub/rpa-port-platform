# Session 73 Handoff — 2026-02-26

## 3 Bugs Fixed (4 commits pushed to main)

### BUG #1 — `4cb40aa` — Wire xml_documents into knowledge_query.py
- `knowledge_query.py:gather_knowledge()` Step F2 now calls `search_xml_documents` via ToolExecutor
- 231 XML docs (FTA protocols, tariff sections, procedures) now reachable from knowledge_query path
- Verified: `search_xml_documents` referenced in BOTH `email_intent.py` AND `knowledge_query.py`

### BUG #2 — `09fec68` — Fix silent email consumption on send failure
- `main.py:996-1027`: Only `replied`/`cache_hit`/`clarification_sent` mark email as read + continue
- `send_failed` → logs to `rcb_debug` collection, falls through to knowledge_query/classification
- Email no longer silently consumed when send fails

### BUG #3 — `47c6916` — Quality gate body threshold 200→50 chars
- `rcb_helpers.py:email_quality_gate()` threshold lowered from 200 to 50
- Short correct intent replies now pass (was the root cause of send failures triggering BUG #2)
- Reason code changed: `body_under_200` → `body_too_short`
- Tests updated + 1 new test

### Debug logging — `233bf5e`
- `rcb_debug` collection: logs intent, product_description, tariff_results, html_composed, send_status, failure_reason
- Registered in `librarian_index.py` COLLECTION_FIELDS

## Deploy
- `rcb_check_email` deployed to Cloud Functions (revision rcb-check-email-00352-pox)
- `.gcloudignore` created to exclude `venv/` from deploy (was causing build failure)
- 32 `questions_log` cache entries deleted (all doron@ entries)

## Test Email Results (PARTIAL)

### What happened
3 test emails created via Graph API `POST /messages` + `move` to inbox:
1. "בדיקה - סיווג מכונת קפה" / "מה פרט המכס למכונת קפה ביתית?"
2. "בדיקה - מכס גבינה מאירופה" / "מה שיעור המכס על יבוא גבינה מהאיחוד האירופי?"
3. "בדיקה - ייבוא צעצועים" / "מה צריך כדי לייבא צעצועים לישראל?"

### Problem: `is_direct=False` for all 3
Messages created via Graph API `POST /messages` endpoint are placed in mailbox without full routing headers. The `toRecipients` field was set but `is_direct` check at `main.py:814` checks the actual `toRecipients` array which may not be populated the same way for API-created messages vs real emails.

Cloud Function logs show all 3 as `is_direct=False` → they take the CC path (not direct path) → no intent detection → fall through to tracker/pupil/classification.

### rcb_debug collection: 1 entry found
```
event=intent_send_failed
intent=KNOWLEDGE_QUERY
status=sent
from=doron@rpa-port.co.il
tariff_results=['knowledge_query_handler']
```
This was email #1 — it was detected as KNOWLEDGE_QUERY by the knowledge_query.py path (not email_intent.py), processed successfully (status=sent), BUT was logged under the wrong event name (`intent_send_failed` instead of `email_processed`).

**Root cause of wrong event name**: The debug entry was created through the BUG #2 fallthrough path (send_failed branch). The knowledge_query handler returned status "sent" but the intent system returned a different status earlier. Need to investigate the exact flow.

### Cloud Function Logs Summary
- Gemini 429 quota exhausted (free tier) → fell back to Claude
- Classification pipeline ran for at least one email (493 chars extracted)
- Multiple real production emails also processed in the same cycle

## NEXT SESSION TODO

1. **Re-test with REAL emails** — send from Outlook (not Graph API) to get proper `is_direct=True`
2. **Verify the 3 test emails were processed** — check `rcb_processed` collection for the 3 subjects
3. **Check if replies were sent** — search Sent Items in rcb@ mailbox
4. **Fix debug logging event name** — the `intent_send_failed` event fired even for `status=sent` because the knowledge_query path doesn't go through the intent system. Need to add separate debug logging for the knowledge_query path.
5. **Consider**: Gemini paid tier — free tier 429s are causing all traffic to fall back to Claude ($$$)

## Files Modified This Session

| File | Change |
|------|--------|
| `functions/lib/knowledge_query.py` | +25 lines: Step F2 search_xml_documents |
| `functions/main.py` | +44/-10 lines: BUG #2 fix + rcb_debug logging |
| `functions/lib/rcb_helpers.py` | +4/-4 lines: threshold 200→50, reason code |
| `functions/lib/librarian_index.py` | +6 lines: rcb_debug in COLLECTION_FIELDS |
| `functions/tests/test_email_quality_gate.py` | +9/-6 lines: updated tests |
| `functions/.gcloudignore` | NEW: exclude venv/ from deploy |

## Test Results
- **1269 passed**, 0 failed, 0 skipped
