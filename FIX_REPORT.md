# RCB Bug Fix Report
## Assignment 2 — Critical & High Bug Fixes
**Date:** February 16, 2026
**Performed by:** Claude Code (CLI)
**Status:** All 10 fixes applied and verified

---

## Summary

| # | Severity | File | Bug | Status |
|---|----------|------|-----|--------|
| 1 | CRITICAL | tracker_email.py | kwargs mismatch with caller | FIXED |
| 2 | CRITICAL | pdf_creator.py + main.py | VAT hardcoded as 17% (should be 18%) | FIXED |
| 3 | CRITICAL | main.py | Orphan decorator exposes helper as Cloud Function | FIXED |
| 4 | CRITICAL | intelligence.py | Confidence boost order — dead code branch | FIXED |
| 5 | HIGH | smart_questions.py | Tuple keys unsorted — never match lookup | FIXED |
| 6 | HIGH | tracker.py | `was_enriched` undefined on exception | FIXED |
| 7 | HIGH | classification_agents.py | Agent 6 uses Flash instead of Pro | FIXED |
| 8 | HIGH | main.py | `requests` used before import | FIXED |
| 9 | HIGH | pupil.py | `except Exception as re:` shadows re module | FIXED |
| 10 | HIGH | verification_loop.py | Cache poisoning — FIO upgrade missed | FIXED |

---

## Backups Created

All files backed up with `.bak_20260216` extension before editing:
- `functions/lib/tracker_email.py.bak_20260216`
- `functions/lib/tracker.py.bak_20260216`
- `functions/lib/pdf_creator.py.bak_20260216`
- `functions/lib/intelligence.py.bak_20260216`
- `functions/lib/smart_questions.py.bak_20260216`
- `functions/lib/classification_agents.py.bak_20260216`
- `functions/lib/pupil.py.bak_20260216`
- `functions/lib/verification_loop.py.bak_20260216`
- `functions/main.py.bak_20260216`

---

## Detailed Fix Descriptions

### FIX 1 (CRITICAL): tracker_email.py — kwargs mismatch

**Bug:** `tracker.py:1410-1412` calls `build_tracker_status_email(deal, container_statuses, update_type, observation=observation, extractions=extractions)` but the function signature at `tracker_email.py:10` only accepts `(deal, container_statuses, update_type)`. Python raises `TypeError: unexpected keyword argument` at runtime.

**Before:**
```python
def build_tracker_status_email(deal, container_statuses, update_type="status_update"):
```

**After:**
```python
def build_tracker_status_email(deal, container_statuses, update_type="status_update",
                               observation=None, extractions=None):
```

**Impact:** Every tracker status email would crash. Tracker email sending was completely broken.

---

### FIX 2 (CRITICAL): pdf_creator.py + main.py — VAT 17% → 18%

**Bug:** Israeli VAT changed from 17% to 18% on January 1, 2025. Three locations still hardcoded the old rate.

**Locations fixed:**
1. `pdf_creator.py:151` — `item.get('vat_rate', '17%')` → `'18%'`
2. `main.py:1627` — sample data `'vat_rate': '17%'` → `'18%'`
3. `main.py:1642` — sample data `'vat_rate': '17%'` → `'18%'`

**Note:** `language_tools.py` already has a 17%→18% auto-fixer for AI output text, but the PDF creator and sample data bypassed it.

**Impact:** PDF reports showed wrong VAT rate. Clients could underpay VAT based on incorrect report.

---

### FIX 3 (CRITICAL): main.py — Orphan decorator

**Bug:** Line 934 had `@https_fn.on_request(cors=...)` decorator with no function below it. Due to Python decorator mechanics, it attached to the next `def` — `graph_forward_email` — turning an internal Graph API helper into a **public HTTP Cloud Function endpoint**. This is a security vulnerability: anyone could call this endpoint to forward emails from the RCB mailbox.

**Before:**
```python
# Need this for Cloud Functions

# ============================================================
# FUNCTION 5: RCB API ENDPOINTS
# ============================================================
@https_fn.on_request(cors=options.CorsOptions(cors_origins="*", cors_methods=["GET", "POST"]))

# ============================================================
# RCB HELPER FUNCTIONS
# ============================================================

def graph_forward_email(access_token, user_email, message_id, to_email, comment):
```

**After:**
```python
# ============================================================
# RCB HELPER FUNCTIONS
# ============================================================

def graph_forward_email(access_token, user_email, message_id, to_email, comment):
```

**Impact:** Security fix. Removed unintended public HTTP endpoint.

---

### FIX 4 (CRITICAL): intelligence.py — Confidence boost order

**Bug:** Lines 1425-1429 checked `if usage >= 5` before `elif usage >= 10`. Since any value >= 10 is also >= 5, the `>= 10` branch was dead code. Items with 10+ uses got only +5 boost instead of +10.

**Before:**
```python
if usage >= 5:
    confidence = min(95, confidence + 5)
elif usage >= 10:
    confidence = min(95, confidence + 10)
```

**After:**
```python
if usage >= 10:
    confidence = min(95, confidence + 10)
elif usage >= 5:
    confidence = min(95, confidence + 5)
```

**Impact:** Well-known products (10+ classifications) were under-boosted, potentially causing unnecessary re-research.

---

### FIX 5 (HIGH): smart_questions.py — Tuple key ordering

**Bug:** The lookup uses `tuple(sorted([ch1, ch2]))` which produces alphabetically sorted keys like `("84", "87")`. But two dict entries had unsorted keys: `("87", "84")` and `("90", "85")`. These keys never matched any lookup.

**Before:**
```python
("87", "84"): { ... }
("90", "85"): { ... }
```

**After:**
```python
("84", "87"): { ... }
("85", "90"): { ... }
```

**Impact:** Vehicle vs. parts (ch 84/87) and medical vs. electronic (ch 85/90) disambiguation questions were never generated, leading to generic questions instead of professional customs broker questions.

---

### FIX 6 (HIGH): tracker.py — `was_enriched` undefined on exception

**Bug:** `was_enriched` was only assigned inside a `try` block (line 212). If `_llm_enrich_extraction` threw an exception, `was_enriched` was never defined. The subsequent `if was_enriched:` at line 220 would crash with `NameError`.

**Before:**
```python
# ── STEP 4b: LLM enrichment if regex got thin results ──
try:
    extractions, was_enriched = _llm_enrich_extraction(...)
```

**After:**
```python
# ── STEP 4b: LLM enrichment if regex got thin results ──
was_enriched = False
try:
    extractions, was_enriched = _llm_enrich_extraction(...)
```

**Impact:** When LLM enrichment failed AND template learning was attempted, the entire observation processing would crash.

---

### FIX 7 (HIGH): classification_agents.py — Agent 6 wrong tier

**Bug:** `run_synthesis_agent` (line 595) used `tier="fast"` (Gemini Flash) despite 7 comments/docstrings explicitly documenting it should use Gemini Pro. Session 15 architecture: Agent 2 = Claude Sonnet (smart), Agent 6 = Gemini Pro (pro), Agents 1/3/4/5 = Gemini Flash (fast).

**Before:**
```python
return call_ai(api_key, gemini_key, system, ..., tier="fast")
```

**After:**
```python
return call_ai(api_key, gemini_key, system, ..., tier="pro")
```

**Impact:** Synthesis quality was lower than intended. Gemini Flash produces shorter, less nuanced Hebrew summaries compared to Gemini Pro.

---

### FIX 8 (HIGH): main.py — `requests` used before import

**Bug:** `graph_forward_email` (line 933) uses `requests.post()` but `import requests` was only inside other functions (lines 1064, 1399). No top-level import exists. The function would crash with `NameError: name 'requests' is not defined`.

**Before:**
```python
def graph_forward_email(access_token, user_email, message_id, to_email, comment):
    """Forward email"""
    try:
        url = ...
        requests.post(url, ...)
```

**After:**
```python
def graph_forward_email(access_token, user_email, message_id, to_email, comment):
    """Forward email"""
    import requests
    try:
        url = ...
        requests.post(url, ...)
```

**Impact:** Email forwarding was broken. Any call to `graph_forward_email` would crash.

---

### FIX 9 (HIGH): pupil.py — `except Exception as re:` shadows module

**Bug:** Line 163 uses `re` as the exception variable name, shadowing the `re` module imported at line 30. Any code after this except block that calls `re.search()`, `re.match()`, etc. would crash with `AttributeError`.

**Before:**
```python
except Exception as re:
    print(f"    PUPIL: Review reply error: {re}")
```

**After:**
```python
except Exception as re_err:
    print(f"    PUPIL: Review reply error: {re_err}")
```

**Impact:** After a review reply error, any subsequent regex operations in the same scope would fail.

---

### FIX 10 (HIGH): verification_loop.py — Cache poisoning

**Bug:** `verify_hs_code()` caches results with a 30-day TTL. If the first call had no `free_import_result`, the HS code was cached as "verified" (not "official"). Later calls with FIO data would hit the stale cache and return "verified" — never upgrading to "official" status.

**Before:**
```python
cached = _check_verification_cache(db, hs_clean)
if cached:
    result.update(cached)
    result["from_cache"] = True
    return result
```

**After:**
```python
cached = _check_verification_cache(db, hs_clean)
if cached:
    cached_sources = cached.get("verification_sources", [])
    # Skip cache if caller has FIO data but cached result was verified without it
    if free_import_result and free_import_result.get("found") and "free_import_order" not in cached_sources:
        pass  # Re-verify with FIO data
    else:
        result.update(cached)
        result["from_cache"] = True
        return result
```

**Impact:** HS codes verified before FIO data was available were stuck at "verified" for 30 days instead of being upgraded to "official" when FIO data became available. This affected verification status display and potentially regulatory compliance checks.

---

## Verification Checklist

- [x] All 9 modified files pass `python -m py_compile` — zero syntax errors
- [x] FIX 1: `build_tracker_status_email` signature now includes `observation=None, extractions=None`
- [x] FIX 2: Zero remaining `17%` in pdf_creator.py; main.py sample data updated
- [x] FIX 3: No orphan `@https_fn` decorator near `graph_forward_email`
- [x] FIX 4: `usage >= 10` now checked before `usage >= 5`
- [x] FIX 5: All `_DISTINCTION_HINTS` keys are sorted — `("84","87")` and `("85","90")`
- [x] FIX 6: `was_enriched = False` initialized before try block
- [x] FIX 7: `run_synthesis_agent` uses `tier="pro"`
- [x] FIX 8: `import requests` present inside `graph_forward_email`
- [x] FIX 9: Exception variable renamed to `re_err`, `re` module no longer shadowed
- [x] FIX 10: Cache bypassed when FIO data available but not in cached sources

---

## NOT DEPLOYED

These fixes are local only. No `firebase deploy` was executed. Review before deploying.

```bash
# When ready to deploy:
cd ~/rpa-port-platform && firebase deploy --only functions
```
