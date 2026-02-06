# SESSION 14 — VERIFIED AUDIT REPORT
## language_tools.py vs Actual Codebase
**Date:** 2026-02-06 | **Status:** 🔴 3 CRITICAL ERRORS + 7 INTEGRATION ISSUES

---

## 🔴 CRITICAL ERROR 1: Israeli HS Code Format is COMPLETELY WRONG

### What I Built:
```python
ISRAEL_HS_CODE_DIGITS = 8
ISRAEL_HS_CODE_FORMAT = "XXXX.XX.XX"   # e.g., 8708.99.80
```

### What the Actual Codebase Uses (librarian.py:316-323):
```python
def get_israeli_hs_format(hs_code):
    """Convert HS code to Israeli format XX.XX.XXXXXX/X"""
    code = str(hs_code).replace('.', '').replace(' ', '').replace('/', '')
    code = code.ljust(10, '0')[:10]
    if len(code) >= 8:
        return f"{code[:2]}.{code[2:4]}.{code[4:10]}/{code[9] if len(code) > 9 else '0'}"
    return hs_code

def normalize_hs_code(hs_code):
    """Normalize HS code to 10 digits for comparison"""
    code = str(hs_code).replace('.', '').replace(' ', '').replace('/', '')
    return code.ljust(10, '0')[:10]
```

### Actual Israeli HS Format:
- **10 digits** internally (padded with zeros)
- **Display format:** `XX.XX.XXXXXX/X` → e.g., `84.71.300000/0`
- **Structure:** chapter(2) . heading(2) . subheading+national(6) / check(1)
- The Israel Tax Authority confirms: "פרט מכס הינו מספר בין 10 ספרות"

### Impact:
- My `check_hs_code_format()` validator REJECTS valid Israeli codes
- My sample letter shows `8471.30.00` instead of `84.71.300000/0`
- My LLM prompt tells Claude the wrong format

### Fix Required:
- Change constant to 10 digits
- Match `get_israeli_hs_format()` from librarian.py exactly
- My validator should accept the `XX.XX.XXXXXX/X` format
- Or better: **import `get_israeli_hs_format` from librarian.py instead of reimplementing it**

---

## 🔴 CRITICAL ERROR 2: De Minimis is $150 USD, Not ILS

### What I Built:
```python
ISRAEL_DE_MINIMIS_ILS = 150  # WRONG UNIT
```

### Reality:
- Threshold is **$150 USD** (≈545 ILS)
- Changed from $75 USD in late 2025 (Smotrich signed Nov 2025)
- Currently under legislative review

### Fix:
```python
ISRAEL_DE_MINIMIS_USD = 150     # $150 USD
ISRAEL_DE_MINIMIS_NOTE = "Updated Dec 2025, under legislative review"
```

---

## 🔴 CRITICAL ERROR 3: build_rcb_subject() Return Type Mismatch

### What the Actual Code Returns (classification_agents.py:126):
```python
return subject, tracking   # TUPLE: (str, str)
```

### How It's Called (classification_agents.py:701):
```python
subject_line, tracking_code = build_rcb_subject(invoice_data, status, score)
```

### What I Need to Match:
My `SubjectLineGenerator.generate()` must return `(subject_str, tracking_code_str)` tuple — NOT just a string.

---

## 🟡 INTEGRATION ISSUES (7)

### Issue 1: build_classification_email() — Exact Signature

**Actual signature** (classification_agents.py:434):
```python
def build_classification_email(results, sender_name, invoice_validation=None, tracking_code=None, invoice_data=None)
```

**`results` structure:**
```python
{
    "success": True,
    "agents": {
        "classification": {"classifications": [...]},
        "regulatory": {"regulatory": [...]},
        "fta": {"fta": [...]},
        "risk": {"risk": {"level": "...", "items": [...]}},
    },
    "synthesis": "Hebrew text...",
    "invoice_data": {...}
}
```

My `LetterStructure` doesn't consume this structure. It's a generic builder.
**Decision needed:** Do we replace `build_classification_email()` entirely, or add a wrapper that converts the `results` dict into `LetterStructure` calls?

### Issue 2: get_israeli_hs_format() — Don't Reimplement, Import

My `HebrewLanguageChecker.check_hs_code_format()` reinvents what `librarian.py` already does.
**Better approach:** Import and use the existing function:
```python
from lib.librarian import get_israeli_hs_format, normalize_hs_code
```

### Issue 3: call_claude() — TextPolisher Must Extend, Not Replace

**Actual call_claude** (classification_agents.py:149):
```python
def call_claude(api_key, system_prompt, user_prompt, max_tokens=2000)
```

My `TextPolisher.build_polish_prompt()` generates a text block. This must be APPENDED to `system_prompt` in existing calls, not create a new call.

**Integration pattern:**
```python
# In run_synthesis_agent or wherever polish is needed:
system = original_system_prompt + "\n\n" + polisher.build_polish_prompt(text, "he")
result = call_claude(api_key, system, user_prompt)
```

### Issue 4: Clarification Generator — 6 Functions, Not 6 Letter Types

**Actual functions in clarification_generator.py:**
1. `generate_missing_docs_request()` (HE) — lines 294-366
2. `generate_missing_docs_request_en()` (EN) — lines 369-443
3. `generate_classification_request()` — lines 446-505
4. `generate_cif_completion_request()` — lines 508-574
5. `generate_origin_request()` — lines 577-675
6. `generate_generic_request()` — lines 678-716

Each has **specific parameters and return types** (`ClarificationRequest` dataclass).
My `LetterStructure` doesn't replace these — it could enhance their HTML output.

### Issue 5: librarian_tags.py Data Structures — VERIFIED

My bootstrap assumptions were MOSTLY correct, but with gaps:

| Structure | My Assumption | Actual |
|-----------|--------------|--------|
| DOCUMENT_TAGS | `{"key": "Hebrew name"}` | ✅ Correct |
| TAG_KEYWORDS | `{"tag": ["keyword1", ...]}` | ✅ Correct |
| CUSTOMS_HANDBOOK_CHAPTERS | `{num: {"name_he":..., "tag":...}}` | ⚠️ Missing: `scope`, `pdf_url`, `sub_chapters` |

**Extra fields I missed:** `scope` (import/export/both), `pdf_url`, nested `sub_chapters` dict.

### Issue 6: Email Flow — Where to Hook In

**Actual email flow** (from rcb_email_processor.py + classification_agents.py):
```
Email arrives → extract_text → run_full_classification → 
build_rcb_subject → build_classification_email → 
helper_graph_send → save to Firestore
```

My `process_outgoing_text()` pipeline should hook in **between** `run_synthesis_agent()` and `build_classification_email()` to:
1. Fix the synthesis text (typos, VAT, RTL spacing)
2. Learn from the email sender's style (StyleAnalyzer)
3. NOT duplicate any Claude API calls

### Issue 7: Enrichment Agent — Already Has Learning

**enrichment_agent.py** already imports:
```python
from .librarian_researcher import (
    learn_from_classification,
    learn_from_email,
    ...
)
```

My `LanguageLearner` overlaps with this. We either:
- **Merge:** Have LanguageLearner delegate document/email learning to enrichment_agent
- **Separate:** LanguageLearner handles LANGUAGE learning only (spelling, style), enrichment_agent handles CONTENT learning (new terms, knowledge)

Best approach: **Separate concerns.** LanguageLearner = spelling/style/register. Enrichment = content/knowledge.

---

## 🟡 SUSPICIOUS DATA TO VERIFY WITH USER

| Item | What I Wrote | Concern |
|------|-------------|---------|
| שע"מ | שער עולמי | Non-standard abbreviation — verify |
| מס"ב | מס ערך מוסף בשיעור אפס | Non-standard — verify |
| בל"ד | בית לחם דרום (מעבר) | Verify if relevant |

---

## 🟢 WHAT'S SOLID AND READY

| Component | Status | Integration Plan |
|-----------|--------|-----------------|
| VAT = 18% + auto-fix 17%→18% | ✅ Verified | Wire into synthesis output processing |
| KNOWN_TYPOS dict (24 entries) | ✅ Good | Use in fix_all() on all outgoing text |
| RTL/LTR spacing fix | ✅ Good | Use in fix_all() on all outgoing text |
| StyleAnalyzer (register detection) | ✅ Good | New capability — hook into email processing |
| Contact profiling | ✅ Good | New capability — learn per sender |
| SubjectLineGenerator | ⚠️ Fix return type | Must return (subject, tracking) tuple |
| LetterStructure | ⚠️ Complement, don't replace | Enhance clarification HTML, not replace it |
| TextPolisher prompts | ⚠️ Must extend existing calls | Append to system_prompt, not new call |
| JokeBank | ✅ Good | Standalone, no integration issues |
| Vocabulary bootstrap | ⚠️ Fix data mapping | Add scope, pdf_url handling |

---

## 📋 CORRECTED INTEGRATION PLAN

### Phase 1: Fix Critical Errors (immediate)
1. HS code: Change to 10 digits, `XX.XX.XXXXXX/X` format, import from librarian.py
2. De minimis: Change to $150 USD
3. SubjectLineGenerator: Return (subject, tracking) tuple

### Phase 2: Safe Hooks (low risk)
4. Wire `fix_all()` into synthesis output (between Agent 6 and HTML builder)
5. Wire `check_vat_rate()` into build_classification_email HTML output
6. Add StyleAnalyzer.learn_from_email() call in email processor

### Phase 3: Enhanced Output (medium risk)
7. Wrap clarification emails in LetterStructure HTML (better formatting)
8. Add TextPolisher instructions to synthesis agent system prompt
9. Bootstrap vocabulary from actual DOCUMENT_TAGS + CUSTOMS_HANDBOOK_CHAPTERS

### Phase 4: Learning Pipeline (needs Firestore design)
10. LanguageLearner persistence to Firestore
11. Separate from enrichment_agent learning (language vs content)
12. Contact profiles collection

---

## 📊 FINAL STATISTICS

| Metric | Value |
|--------|-------|
| Critical errors found | 3 |
| Integration issues | 7 |
| Components ready as-is | 5/8 |
| Components needing fixes | 3/8 |
| Lines of code | 1,994 |
| Actual codebase files reviewed | 8 files, 6,410 lines |
