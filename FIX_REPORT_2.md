# RCB Bug Fix Report 2
## Assignment 5 — HIGH Bug Fixes + Keyword Index Cleanup
**Date:** February 16, 2026
**Performed by:** Claude Code (CLI)
**Status:** All 6 fixes applied and verified + keyword_index cleaned

---

## Summary

| Fix | File | Severity | Issue | Status |
|-----|------|----------|-------|--------|
| 11 | brain_commander.py | HIGH | `from lib.ai_intelligence import ask_claude` — module doesn't exist | FIXED |
| 12 | pupil.py | HIGH | Missing `system_hs_code`/`ai_hs_code` in investigation task dict | FIXED |
| 13 | librarian.py | HIGH | `get_israeli_hs_format` duplicates last digit | FIXED |
| 14 | main.py | HIGH | `monitor_self_heal` defined twice (duplicate Cloud Function) | FIXED |
| 15 | __init__.py | HIGH | `pc_agent` import not guarded with try/except | FIXED |
| 16 | language_tools.py | HIGH | Hebrew regex typo `בכפוו ל` should be `בכפוף ל` | FIXED |
| — | keyword_index | DATA | 101 docs with AI-response garbage in codes array | CLEANED |

---

## FIX 11: brain_commander.py — Non-existent `ai_intelligence` module

**Severity:** HIGH — `ask_claude` always throws ImportError, Claude agent silently fails in brain missions and creator tasks.

**BEFORE (lines 351, 460):**
```python
from lib.ai_intelligence import ask_claude
result = ask_claude(
    f"Research for RCB customs broker AI system. Topic: {topic}",
    get_secret_func
)
```

**AFTER:**
```python
from lib.classification_agents import call_claude
api_key = get_secret_func("ANTHROPIC_API_KEY")
result = call_claude(
    api_key,
    "You are a customs broker research assistant.",
    f"Research for RCB customs broker AI system. Topic: {topic}",
    max_tokens=3000
)
```

**Why:** `lib/ai_intelligence.py` does not exist. The real Claude wrapper is `call_claude` in `classification_agents.py`, which takes `(api_key, system_prompt, user_prompt, max_tokens)`. Both occurrences (research missions at line 351 and creator tasks at line 460) now use the correct import and call signature.

---

## FIX 12: pupil.py — Missing fields in investigation task dict

**Severity:** HIGH — Investigation tasks created from disputed corrections have empty `system_code` and `ai_code` fields.

**BEFORE (line 2479):**
```python
_create_investigation_task(db, {
    "case_id": case_id,
    "conflict_details": f"Correction disputed: {case.get('original_hs_code')} vs {case.get('corrected_hs_code')}",
}, body_clean)
```

**AFTER:**
```python
_create_investigation_task(db, {
    "case_id": case_id,
    "conflict_details": f"Correction disputed: {case.get('original_hs_code')} vs {case.get('corrected_hs_code')}",
    "system_hs_code": case.get("original_hs_code", ""),
    "ai_hs_code": case.get("corrected_hs_code", ""),
}, body_clean)
```

**Why:** `_create_investigation_task` (line 1976) reads `case.get("system_hs_code", "")` and `case.get("ai_hs_code", "")`. The caller was passing a dict without these keys, so investigation tasks were always created with empty HS codes, making them useless for the Claude escalation pipeline.

---

## FIX 13: librarian.py — HS format duplicates last digit

**Severity:** HIGH — Every formatted HS code displayed to clients in emails and reports has a duplicated digit.

**BEFORE (line 322):**
```python
return f"{code[:2]}.{code[2:4]}.{code[4:10]}/{code[9] if len(code) > 9 else '0'}"
```
Example: `0101200000` → `01.01.200000/0` (digit 9 appears twice)

**AFTER:**
```python
return f"{code[:2]}.{code[2:4]}.{code[4:8]}/{code[8:10]}"
```
Example: `0101200000` → `01.01.2000/00` (correct Israeli XX.XX.XXXX/XX format)

**Why:** `code[4:10]` gives 6 chars (positions 4-9), then `code[9]` repeats position 9. The correct Israeli tariff format is `XX.XX.XXXX/XX` — 4 subheading digits, slash, 2 statistical suffix digits.

---

## FIX 14: main.py — Duplicate `monitor_self_heal` definition

**Severity:** HIGH — Two `@https_fn.on_request` decorated functions with the same name. Python silently overwrites v1 with v2, but Firebase may register both decorators, causing deployment confusion.

**BEFORE (lines 1568-1580):**
```python
@https_fn.on_request(...)
def monitor_self_heal(request):
    """DISABLED Session 13.1: Dead code (redefined below). Was self-healer v1."""
    ...

@https_fn.on_request(...)
def monitor_self_heal(request):
    """DISABLED Session 13.1: Consolidated into rcb_check_email. Was self-healer v2."""
    ...
```

**AFTER:** First definition (v1) removed. Single definition remains.

---

## FIX 15: __init__.py — `pc_agent` import not guarded

**Severity:** HIGH — Every other import in `__init__.py` is wrapped in `try/except ImportError: pass`. If `pc_agent.py` has any import error, the entire `lib` package fails to load, taking down ALL Cloud Functions.

**BEFORE (line 208):**
```python
# PC Agent - Browser-based file downloads
from .pc_agent import (
    create_download_task,
    ...
)
```

**AFTER:**
```python
# PC Agent - Browser-based file downloads
try:
    from .pc_agent import (
        create_download_task,
        ...
    )
except ImportError:
    pass
```

---

## FIX 16: language_tools.py — Hebrew regex typo

**Severity:** HIGH — Regex pattern for extracting formal legal phrases has a typo. Never matches the Hebrew word "subject to" (בכפוף ל).

**BEFORE (line 1272):**
```python
r'(?:בהתאם ל|על פי|מכוח|לפי|בכפוו ל)[^.]{5,60}', text
```

**AFTER:**
```python
r'(?:בהתאם ל|על פי|מכוח|לפי|בכפוף ל)[^.]{5,60}', text
```

**Why:** `בכפוו ל` is a typo (double vav instead of peh-vav). The correct word is `בכפוף ל` ("subject to"), a common legal phrase in Israeli customs regulations.

---

## PART 2: Keyword Index Cleanup

**Collection:** `keyword_index`
**Before:** 8,195 docs, 234 garbage code entries across 101 docs
**After:** 8,120 docs, 0 garbage entries

**What was garbage:** `codes[].description` fields containing AI response text instead of product descriptions. Examples:
- `"The HS code 0810.50 covers kiwifruit, fresh..."`
- `"To accurately classify 'TEST 1800 0402'..."`
- `"Librarian has low confidence for..."`

**Actions taken:**
- **75 docs deleted** — all code entries were garbage
- **26 docs cleaned** — removed garbage entries, kept valid ones, updated count
- **0 errors**

**Verification:** Post-cleanup scan confirms 0 remaining garbage entries.

---

## Syntax Verification

| File | Syntax |
|------|--------|
| lib/brain_commander.py | OK |
| lib/pupil.py | OK |
| lib/librarian.py | OK |
| main.py | OK |
| lib/__init__.py | OK |
| lib/language_tools.py | OK |

## Backup Files

All 6 files backed up with `.bak2_20260216` suffix before modification.

---

## NOT DEPLOYED — Fixes applied to local files only.
