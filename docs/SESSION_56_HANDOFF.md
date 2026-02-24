# Session 56 Handoff — 24 February 2026

## What Was Done

### Pre-flight
- **1,185 tests passing** — confirmed baseline, zero regressions throughout
- **Git clean on `main`**, latest commit `cdfc3da`
- Milestone doc (P0) NOT committed — Doron did not provide content

### P1: Parse צו מסגרת — Framework Order (IN PROGRESS)

#### Analysis Completed
- Read and analyzed `data_c3/framework_order_text.txt` (82KB, 44 lines, ~50K chars)
- File structure: PDF text extraction with even-indexed lines empty (page overlap artifacts)
- Article pattern identified: `( TITLE NUMBER` (e.g., `( הגדרות 01`)
- Sub-article pattern: `SUFFIX( TITLE NUMBER` (e.g., `א( מיחזור 06`)
- Page footers: `הודפס בתאריך DD/MM/YYYY   עמוד N`
- All 33 articles catalogued with titles, English summaries, and FTA country mappings

#### Existing Infrastructure Reviewed
- `_ordinance_data.py`: Pattern to follow — `ORDINANCE_ARTICLES` dict with `t/s/f` fields
- `tool_executors.py:_lookup_framework_order()`: 6 query cases, reads from Firestore `framework_order` (85 docs)
- `tool_executors.py:_search_legal_knowledge()`: Has in-memory ordinance search (Cases A/B/C) — framework order needs same treatment
- `seed_framework_order_c5.py`: Seeded 85 docs (definitions, FTA clauses, rules, additions) with truncated text (max 3K chars)

#### Parser Built (functions/parse_framework_order.py)
- ~270 lines, follows `parse_ordinance_text.py` pattern
- **Known article titles dict**: 33 articles (01-25 + sub-articles 06א, 23א-23ז)
- **English summaries**: All 33 articles have English summaries
- **FTA country mapping**: 15 articles mapped to FTA countries
- **Code generator**: Outputs `_framework_order_data.py` in same format as `_ordinance_data.py`

#### Parser Bug — NOT YET FIXED
The regex-based boundary detection has a core problem:
- **False positives**: Footnote references at end of document match pattern `( NUMBER )` — e.g., `( 10 )`, `( 11 )`, etc.
- **Title matching**: Article 04 has parentheses in title `הוראה נוספת )ישראלית(` — breaks `[^()]` regex
- **Empty titles**: Article 23ז appears as `ז( 23` with no title text

**Best run so far**: 31 articles found, 47K chars extracted. Missing:
- Article 23ו (UAE FTA)
- Article 23ז (Guatemala FTA)
- Article 02 matched to wrong position (1 char instead of ~1K)
- Some articles picked wrong position due to duplicate patterns in definitions section

**Recommended fix approach**: Abandon generic regex. Instead, search for each known article by its specific title string as anchor. Example:
```python
for article_id, title in _ARTICLE_TITLES.items():
    pattern = f"({re.escape(title[:15])}.*?{num})"  # title-anchored search
    match = re.search(pattern, text)
```
This was being implemented when work was stopped (the edit to `_find_article_boundaries` was in progress but didn't apply due to a string mismatch in the Edit tool).

### P2-P4: Not Started
- **P2 (Email Threading)**: Not started
- **P3 (Firestore Index)**: Not started
- **P4 (Legal in Classification)**: Not started

## Current State

### Files Created (NOT committed)
| File | Status | Notes |
|------|--------|-------|
| `functions/parse_framework_order.py` | New, untracked | Parser ~270 lines, needs boundary detection fix |

### Files NOT Modified
No existing files were modified. Zero regressions.

### Git Status
```
Branch: main
HEAD: cdfc3da (Session 55 CLAUDE.md backup)
Tests: 1,185 passed
Untracked: parse_framework_order.py (new), plus pre-existing untracked files
```

## Remaining Work for P1

### Step 1: Fix `_find_article_boundaries()` in parse_framework_order.py
Use title-anchored search instead of generic regex. For each known article:
1. Search for first significant Hebrew words from `_ARTICLE_TITLES[id]` followed by the 2-digit number
2. For sub-articles (06א, 23א-23ז), include the suffix letter before the opening paren
3. Prefer matches after position ~6000 (skip definitions section) for articles > 01
4. Target: 33 articles, ~47K chars of Hebrew text

### Step 2: Generate `functions/lib/_framework_order_data.py`
Run `python parse_framework_order.py` to generate the data module. Should contain:
- `FRAMEWORK_ORDER_ARTICLES` dict with `t` (title_he), `s` (summary_en), `f` (full_text_he), optional `fta` (country)
- ~33 entries, ~47K chars total

### Step 3: Wire into `tool_executors.py`
Add to `_lookup_framework_order()`:
- Import `FRAMEWORK_ORDER_ARTICLES` from `_framework_order_data`
- Add full text return: when looking up an article, include `"full_text_he"` field (capped at 3000 chars)
- Add to `_search_legal_knowledge()`: new cases for framework order article lookup and keyword search (mirror Cases A/B/C from ordinance)

### Step 4: Wire into `email_intent.py`
Ensure `_extract_legal_context()` passes framework order results to the AI prompt, similar to how ordinance results are passed.

### Step 5: Test
- Run `python -m pytest functions/tests/ -x -q` — must stay at 1,185+ passed
- Manual test: send email asking about FTA with EU to verify framework order article 17 is returned

## Key Reference Files
| File | Purpose |
|------|---------|
| `functions/parse_framework_order.py` | Parser (needs fix) |
| `functions/parse_ordinance_text.py` | Reference parser (working, ~450 lines) |
| `functions/lib/_ordinance_data.py` | Reference data module (311 articles, 117K chars) |
| `functions/lib/tool_executors.py` | Wire search here (lines ~763-889 for framework_order, ~2500+ for legal_knowledge) |
| `functions/lib/email_intent.py` | Wire legal context here |
| `data_c3/framework_order_text.txt` | Source file (82KB) |

## What NOT to Touch
- All existing code is stable — 1,185 tests passing
- Do NOT modify `_ordinance_data.py`, `customs_law.py`, or `chapter_expertise.py`
- Do NOT change the Firestore `framework_order` collection (85 docs) — it stays as-is, the new Python data is supplemental
