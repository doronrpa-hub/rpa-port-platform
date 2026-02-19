# WIRING_HANDOFF_50b.md — Session 50b Handoff for main.py Changes

## Files Modified by Session 50b
- `functions/lib/self_learning.py` — Level 0.5 keyword-overlap memory match
- `functions/lib/tracker.py` — TOCTOU race fix on classification_auto_triggered_at
- `functions/lib/tracker_email.py` — Color constants renamed to public API
- `functions/lib/identity_graph.py` — Bare except fix + wired into tracker.py
- `functions/tests/test_self_learning.py` — 24 new tests

---

## 1. tracker_email.py Color Constants (M6)

**What changed:** Renamed 7 underscore-prefixed constants to public names:
```
_RPA_BLUE    → RPA_BLUE
_RPA_ACCENT  → RPA_ACCENT
_COLOR_OK    → COLOR_OK
_COLOR_WARN  → COLOR_WARN
_COLOR_ERR   → COLOR_ERR
_COLOR_PENDING → COLOR_PENDING
_LOGO_URL    → LOGO_URL
```

**Action needed in classification_agents.py (line 158):**
```python
# BEFORE:
from lib.tracker_email import (
    _RPA_BLUE, _RPA_ACCENT, _COLOR_OK, _COLOR_WARN, _COLOR_ERR,
    _LOGO_URL, _html_open, _html_close, _to_israel_time,
)

# AFTER:
from lib.tracker_email import (
    RPA_BLUE, RPA_ACCENT, COLOR_OK, COLOR_WARN, COLOR_ERR,
    LOGO_URL, _html_open, _html_close, _to_israel_time,
)
```

And update all references in classification_agents.py (replace_all):
- `_RPA_BLUE` → `RPA_BLUE`
- `_RPA_ACCENT` → `RPA_ACCENT`
- `_COLOR_OK` → `COLOR_OK`
- `_COLOR_WARN` → `COLOR_WARN`
- `_COLOR_ERR` → `COLOR_ERR`
- `_LOGO_URL` → `LOGO_URL`

**Note:** The try/except fallback at lines 162-169 already has the hardcoded values, so the old names still work until updated. No breakage.

---

## 2. Pupil Unwired Functions (P3 Audit)

### 2a. Wire `pupil_escalate_to_claude()` into rcb_pupil_learn()

**File:** `functions/main.py` — inside `rcb_pupil_learn()` function

The function is already imported (line ~1976) but never called. Add after `pupil_find_corrections()`:

```python
# In rcb_pupil_learn(), after the pupil_find_corrections call:

# Phase B2: Escalate complex tasks to Claude (tier 2)
try:
    escalated = pupil_escalate_to_claude(db, get_secret)
    results["escalated"] = escalated
    print(f"  [PUPIL] Escalated to Claude: {escalated}")
except Exception as e:
    print(f"  [PUPIL] Escalation error: {e}")
```

### 2b. Wire `pupil_research_contacts()` into rcb_pupil_learn()

**File:** `functions/main.py` — inside `rcb_pupil_learn()` function

Add import and call:

```python
# Add to the dynamic import block at line ~1975:
from lib.pupil import (
    pupil_learn, pupil_verify_scan, pupil_challenge,
    pupil_send_reviews, pupil_find_corrections, pupil_audit,
    pupil_escalate_to_claude, pupil_research_contacts,  # ← ADD
)

# Add call in Phase B, after pupil_verify_scan:
try:
    contacts = pupil_research_contacts(db, get_secret)
    results["contacts_researched"] = contacts
    print(f"  [PUPIL] Contacts researched: {contacts}")
except Exception as e:
    print(f"  [PUPIL] Contact research error: {e}")
```

---

## 3. Memory Level 0.5 — Tool Engine Bypass Enhancement (Optional)

**What changed:** `check_classification_memory()` now returns `"exact"` level for keyword-overlap matches (Level 0.5). The pre-classify bypass in `tool_calling_engine.py` (line ~196) already works with this since it checks `level == "exact"`.

**Optional enhancement in tool_calling_engine.py:**
If you want to distinguish true exact from normalized matches in logging:
```python
# In Step 4 memory check, after the memory hit:
mem = executor.execute("check_memory", {"product_description": desc})
if mem.get("found") and mem.get("level") == "exact" and mem.get("confidence", 0) >= 0.9:
    memory_hits[desc[:50]] = mem
    # The print already distinguishes EXACT vs NORMALIZED in self_learning.py logs
```

No changes needed — this already works.

---

## 4. Identity Graph Wiring (Done in tracker.py)

Session 50b wired the identity graph directly in `tracker.py`:
- `link_email_to_deal()` called from `tracker_process_email()`
- `register_deal_from_tracker()` called from `_create_deal()`

**No main.py changes needed for identity graph.**
