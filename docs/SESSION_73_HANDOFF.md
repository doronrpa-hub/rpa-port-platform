# Session 73 Handoff — 2026-02-26

## Commits (5 total, all on main, all pushed)

| # | SHA | Description |
|---|-----|-------------|
| 1 | `4cb40aa` | BUG #1: Wire search_xml_documents into knowledge_query.py |
| 2 | `09fec68` | BUG #2: Fix silent email consumption on intent send failure |
| 3 | `47c6916` | BUG #3: Lower quality gate body threshold 200→50 chars |
| 4 | `233bf5e` | Add rcb_debug Firestore logging on every email processed |
| 5 | `76c73f6` | URGENT: Skip auto-reply/OOO emails to prevent reply loop |

## Bug Fixes

### BUG #1 — Wire xml_documents into knowledge_query.py
- `knowledge_query.py:gather_knowledge()` Step F2 now calls `search_xml_documents` via ToolExecutor
- 231 XML docs (FTA protocols, tariff sections, procedures) now reachable from knowledge_query path

### BUG #2 — Fix silent email consumption on send failure
- `main.py`: Only `replied`/`cache_hit`/`clarification_sent` mark email as read + continue
- `send_failed` → logs to `rcb_debug`, falls through to knowledge_query/classification

### BUG #3 — Quality gate body threshold 200→50 chars
- Short correct intent replies now pass the gate
- Reason code: `body_under_200` → `body_too_short`

### Auto-reply loop fix (`76c73f6`)
- Skip emails with subject containing: "אני לא נמצא", "Automatic reply", "Out of Office", "שליחה אוטומטית"
- Skip emails with `X-Auto-Response-Suppress` header
- Skip emails from doron@ with "אשוב" in body
- All skipped emails marked as read immediately

## Deploy Status
- `rcb_check_email` deployed: revision `rcb-check-email-00354-buc`, state ACTIVE
- `.gcloudignore` created (excludes venv/ — was causing olefile2.py build failure)
- 32 `questions_log` cache entries deleted (all doron@ entries)

## Test Emails — INVALID (need manual re-test)
3 test emails created via Graph API `POST /messages` endpoint had `is_direct=False` because API-created messages lack proper routing headers. They were processed as CC-path (not direct), so intent detection was never triggered. 1 rcb_debug entry captured for email #1 (fell through to knowledge_query, status=sent).

**Need manual test from Outlook when Doron is back** — real emails will have proper `is_direct=True`.

## Next Session TODO
1. **Manual test from Outlook** — send 3 test questions directly to rcb@ to verify full intent→reply flow
2. **Add Layer 2 casual/customs pre-filter** — Gemini Flash triage before intent detection
3. **Fix debug logging** — knowledge_query path needs its own rcb_debug entry (currently only intent path logs)
4. **Consider Gemini paid tier** — free tier 429s causing all traffic to fall back to Claude

## Files Modified This Session

| File | Change |
|------|--------|
| `functions/lib/knowledge_query.py` | +25 lines: Step F2 search_xml_documents |
| `functions/main.py` | +61/-10 lines: BUG #2 fix + rcb_debug logging + auto-reply skip |
| `functions/lib/rcb_helpers.py` | +4/-4 lines: threshold 200→50 |
| `functions/lib/librarian_index.py` | +6 lines: rcb_debug in COLLECTION_FIELDS |
| `functions/tests/test_email_quality_gate.py` | +9/-6 lines: updated tests |
| `functions/.gcloudignore` | NEW: exclude venv/ from deploy |

## Test Results
- **1269 passed**, 0 failed, 0 skipped
