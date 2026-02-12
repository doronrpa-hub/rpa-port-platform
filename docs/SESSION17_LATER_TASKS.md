# Session 17 — Later Tasks (Not Now)
## Saved: February 12, 2026

These issues were identified during Session 17 testing but are NOT priority.
Phase 0 (document extraction) comes first.

---

## TASK 1: Merge Emails into One Threaded Response
**Problem:** System sends 3 separate emails: acknowledgment, classification report, clarification request
**Should be:** One email, threaded with the original
**Where:** `process_and_send_report()` in classification_agents.py, `build_rcb_reply()` in rcb_helpers.py
**Fix:** Remove acknowledgment email, combine report + clarification into one, use reply_to_id consistently

## TASK 2: Fix HS Code Validation Format
**Problem:** HS code 76.12.909000/0 returned "לא אומת" even though aluminum profiles (chapter 76) exist in tariff DB with 11,753 entries
**Cause:** Exact string match fails when format differs (extra zero, slash notation)
**Where:** `validate_and_correct_classifications()` in librarian.py
**Fix:** Normalize HS codes before comparison — strip slashes, trailing zeros, try prefix matching (first 6-8 digits)

## TASK 3: Email Threading
**Problem:** Emails not grouped in conversation thread
**Cause:** `helper_graph_send()` has reply_to_id parameter but not used consistently
**Where:** rcb_helpers.py
**Fix:** Always pass original message_id as reply_to_id, set In-Reply-To and References headers

## TASK 4: Tracker Integration
**Problem:** Full delivery order was in attachments but system didn't extract shipping data (BL, vessel, port, dates)
**Cause:** tracker.py not in repo, not wired
**Needs:** Doron to provide tracker.py file, fix known None crash bug, wire into pipeline
**Where:** Phase 5 of wiring plan

## TASK 5: FTA Agreements Download
**URL:** https://www.gov.il/he/departments/dynamiccollectors/bilateral-agreements-search?skip=0
**Problem:** 21 FTA agreements available, fta_agreements collection has 0 docs
**Fix:** Scrape page, populate fta_agreements collection, link to agreement PDFs
**Where:** Phase 4 of wiring plan

## TASK 6: Gemini/Claude Connection Errors
**Problem:** Both Gemini and Claude may return connection errors or timeouts during processing
**Where:** `call_ai()` in classification_agents.py
**Fix:** Add retry logic with exponential backoff, improve error reporting
