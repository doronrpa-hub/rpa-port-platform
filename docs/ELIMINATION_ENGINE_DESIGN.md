# Elimination Engine — Design Document

## Block D, Session 33 (2026-02-18)
## File: `functions/lib/elimination_engine.py` (2,282 lines)

---

## Purpose

The elimination engine is Phase 3 of the RCB target architecture — the methodological backbone that walks the Israeli customs tariff tree deterministically. Given a product description and a list of candidate HS codes (from `pre_classify`), it eliminates incorrect candidates level by level using section scope, chapter notes (exclusions/inclusions), GIR rules, and AI consultation.

**Core principle:** The method has final say. AI participates (challenges, confirms, suggests) but cannot override deterministic rule-based elimination. False negatives (missed eliminations) are acceptable — they leave extra survivors for downstream processing. False positives (wrong eliminations) are not acceptable — they remove correct codes.

---

## Public API

### `eliminate(db, product_info, candidates, api_key=None, gemini_key=None) -> dict`

Main entry point. Runs the full pipeline (levels 0-7).

**Parameters:**
- `db` — Firestore client (used for TariffCache reads and D8 logging)
- `product_info` — ProductInfo dict (from `make_product_info()`)
- `candidates` — list of HSCandidate dicts (from `candidates_from_pre_classify()`)
- `api_key` — optional Anthropic API key (enables D6/D7 AI features)
- `gemini_key` — optional Gemini API key (enables D6/D7 AI features)

**Returns:** EliminationResult dict (see Data Structures below).

### `candidates_from_pre_classify(pre_classify_result) -> list[dict]`

Converts `intelligence.py:pre_classify()` output into HSCandidate list. Handles the `candidates` array format from pre_classify results.

### `make_product_info(item_dict) -> dict`

Builds a ProductInfo dict from an invoice item dict. Auto-extracts keywords from all text fields.

---

## Data Structures

All plain Python dicts — no classes, no external dependencies.

### ProductInfo
```python
{
    "description": str,       # English product description
    "description_he": str,    # Hebrew product description
    "material": str,          # Primary material(s)
    "form": str,              # Physical form/shape
    "use": str,               # Intended use/function
    "origin_country": str,    # Country of origin
    "seller_name": str,       # Supplier/seller name
    "keywords": set[str],     # Auto-extracted bilingual keywords
}
```

### HSCandidate
```python
{
    "hs_code": str,                # Full HS code (e.g. "7326.9000")
    "section": str,                # Roman numeral (e.g. "XV") — set by Level 0
    "chapter": str,                # 2-digit (e.g. "73")
    "heading": str,                # 4-digit (e.g. "7326")
    "subheading": str,             # 6-digit (e.g. "732690")
    "confidence": int,             # 0-100, modified during pipeline
    "source": str,                 # Origin (e.g. "pre_classify", "memory")
    "description": str,            # Hebrew tariff description
    "description_en": str,         # English tariff description
    "duty_rate": str,              # Duty rate string
    "alive": bool,                 # True=still a survivor, False=eliminated
    "elimination_reason": str,     # Why eliminated (empty if alive)
    "eliminated_at_level": str,    # Which level eliminated it
}
```

### EliminationStep
```python
{
    "level": str,              # "section"|"chapter"|"heading"|"subheading"|"ai"|"gir3"
    "action": str,             # "eliminate"|"keep"|"boost"
    "rule_type": str,          # "exclusion"|"inclusion"|"gir_1"|"gir_3a"|etc.
    "rule_ref": str,           # Human reference (e.g. "Chapter 84 exclusion (a)")
    "rule_text": str,          # Hebrew/English text of the rule applied
    "candidates_before": int,  # Alive count before this step
    "candidates_after": int,   # Alive count after this step
    "eliminated_codes": list,  # HS codes eliminated in this step
    "kept_codes": list,        # HS codes kept/boosted in this step
    "reasoning": str,          # Explanation of what happened
}
```

### EliminationResult
```python
{
    "survivors": list[HSCandidate],    # Candidates still alive
    "eliminated": list[HSCandidate],   # Candidates eliminated
    "steps": list[EliminationStep],    # Full elimination audit trail
    "challenges": list[dict],          # D7 devil's advocate counter-arguments
    "sections_checked": list[str],     # Sections encountered
    "chapters_checked": list[str],     # Chapters encountered
    "input_count": int,                # Total candidates at start
    "survivor_count": int,             # Total survivors at end
    "needs_ai": bool,                  # True if >1 survivor (ambiguity)
    "needs_questions": bool,           # True if >3 survivors (user input needed)
    "timestamp": str,                  # ISO 8601 UTC timestamp
}
```

---

## Pipeline Levels

### Level 0: ENRICH (D1)

For each candidate, resolve `chapter` → `section` via TariffCache. Reads from `tariff_structure` collection (doc IDs: `chapter_01` through `chapter_98`). Candidates without a valid section are kept alive (conservative).

### Level 1: SECTION SCOPE (D1)

Groups candidates by section. Builds section keyword text from `tariff_structure` section data + chapter names from `chapter_notes`. Compares against product keywords.

**Safety guards:**
- Requires **>= 5 section keywords** to have enough signal
- Requires **zero overlap** between product and section to eliminate
- At least 1 candidate always survives per section
- Very conservative — only catches clearly wrong sections (e.g., textiles product vs. metals section)

### Level 2a: PREAMBLE SCOPE (D2)

Loads chapter preamble from `chapter_notes` collection. Checks if the product falls outside the scope statement. Uses keyword overlap between product and preamble text. Requires >= 3 preamble keywords and zero overlap with product to eliminate.

### Level 2b: CHAPTER EXCLUSIONS/INCLUSIONS (D1+D2)

The most impactful level. For each candidate's chapter, loads `exclusions[]` and `inclusions[]` from `chapter_notes`.

**Exclusions:** Match product keywords against exclusion text. If overlap >= 2, check if the exclusion is conditional:
- Parse exception clauses (`_EXCEPTION_RE`): "except for...", "למעט..."
- Split exclusion text at exception boundary
- Check if product matches the exception (if so, exclusion doesn't apply)
- Otherwise, eliminate the candidate

**Inclusions:** Match product keywords against inclusion text. If overlap >= 2, boost the candidate's confidence by +10.

### Level 2c: CROSS-CHAPTER REDIRECT (D2)

When a chapter exclusion says "see chapter X" (detected via `_CHAPTER_REF_RE`), boost candidates in chapter X. This is because the excluding chapter is explicitly pointing to chapter X as the correct classification.

Boost amount: +8 confidence per redirect reference.

### Level 2d: DEFINITION MATCHING (D2)

Parse "in this chapter, X means..." definitions from chapter notes (`_DEFINITION_RE`). When a product matches a defined term's keywords (overlap >= 2), boost the candidate's confidence by +10.

### Level 3: GIR 1 HEADING MATCH (D3)

Composite scoring for each surviving candidate's heading text:

```
composite_score = 0.50 × keyword_overlap
                + 0.25 × specificity_score
                + 0.25 × attribute_match_score
```

**Keyword overlap** (0.0-1.0): Jaccard-style overlap between product keywords and heading description keywords.

**Specificity score** (0.0-1.0): Penalizes vague/catch-all headings:
- "אחרים"/"others"/"n.e.s." → 0.1-0.3
- Short headings (< 5 words) → 0.3-0.5
- Headings with specific technical terms → 0.5-0.9

**Attribute match** (0.0-1.0): Matches product material/form/use against heading text using bilingual term sets (`_MATERIAL_TERMS`: ~60 terms, `_FORM_TERMS`: ~40 terms).

**Elimination:** Bottom 30% of survivors eliminated (only when >3 survivors). Safety: at least 1 survivor always preserved.

### Level 3b: SUBHEADING NOTES (D3)

Applies subheading-level rules from `chapter_notes.subheading_rules`. When a subheading rule references a candidate's heading and matches the product (overlap >= 2), boost that candidate by +5.

### Level 4a: GIR 3 TIEBREAK (D4)

Only fires when >1 survivor remains. Three sub-rules applied in order:

**GIR 3א — Most Specific:** Each surviving heading scored for specificity and product coverage. The heading providing the most specific and complete description of the product wins. Others eliminated if the winner's score exceeds second-best by >= 0.15 margin.

**GIR 3ב — Essential Character:** For composite/mixed goods. Identifies the material that gives the product its "essential character" using `_ESSENTIAL_CHARACTER_TERMS` (80+ bilingual material terms). Heading matching that material wins. Requires >= 60% material keyword dominance for confident elimination.

**GIR 3ג — Last Numerical:** Fallback when 3א and 3ב are inconclusive. Among equally eligible headings, the one last in numerical order applies (per GIR 3c).

Each sub-rule only fires if the previous sub-rule didn't resolve to a single winner.

### Level 4b: OTHERS GATE + PRINCIPALLY TEST (D5)

**Others Gate:** Detects catch-all headings ("אחרים"/"others"/"n.e.s."/"שלא פורט") using `_OTHERS_RE`. When specific alternatives exist alongside an "others" heading, the catch-all is suppressed (eliminated). This prevents vague headings from surviving when more specific options are available.

**Principally Test:** For headings containing "באופן עיקרי"/"principally" (`_PRINCIPALLY_RE`), verify the product meets the material composition requirement. Uses keyword matching against `_ESSENTIAL_CHARACTER_TERMS`. If the heading requires a specific material composition that the product doesn't match, eliminate it.

### Level 4c: AI CONSULTATION (D6)

**Trigger:** >3 survivors remaining after all deterministic levels.

**Implementation:**
- Builds structured prompt with product info, surviving candidates, and elimination history
- Calls `classification_agents.call_ai()` with `tier="fast"` (Gemini Flash primary)
- Claude fallback if Gemini fails
- Expects JSON response: `{best_hs_code, eliminate[], confidence, reasoning}`
- AI can eliminate candidates and/or recommend a best code
- AI confidence >= 70 required to apply elimination
- Maximum 2 candidates eliminated per AI consultation
- **No-op when API keys are missing** (graceful degradation)

**System prompt:** Customs classification expert context. Instructed to analyze GIR rules, chapter notes, and elimination history.

### Level 5: BUILD RESULT (D1)

Assembles EliminationResult dict from surviving/eliminated candidates and all steps. Sets `needs_ai = (survivor_count > 1)` and `needs_questions = (survivor_count > 3)`.

### Level 6: DEVIL'S ADVOCATE (D7)

Per-survivor counter-arguments. For each surviving candidate, generates a challenge explaining why this code might be wrong and what alternative might be better.

**Implementation:**
- Builds per-candidate prompt with product info, candidate details, and elimination context
- Calls `classification_agents.call_ai()` with `tier="fast"`
- Expects JSON: `{strongest_alternative, risk_areas[], counter_argument, confidence_impact}`
- Results stored as `challenges[]` in EliminationResult
- **No-op when API keys are missing**

### Level 7: ELIMINATION LOGGING (D8)

Writes full audit trail to Firestore `elimination_log` collection.

**Document structure:**
```python
{
    "timestamp": str,                 # ISO 8601 UTC
    "product_description": str,       # Truncated to 500 chars
    "product_description_he": str,    # Truncated to 500 chars
    "product_material": str,          # Truncated to 200 chars
    "product_form": str,
    "product_use": str,
    "input_count": int,
    "survivor_count": int,
    "needs_ai": bool,
    "needs_questions": bool,
    "survivors": list[dict],          # Sanitized candidate summaries
    "eliminated": list[dict],         # Sanitized candidate summaries
    "steps": list[dict],              # Sanitized step summaries
    "sections_checked": list[str],
    "chapters_checked": list[str],
    "step_count": int,
    "challenges": list[dict],         # D7 devil's advocate results
}
```

**Doc ID format:** `elim_YYYYMMDD_HHMMSS_XXXX` (timestamp + hash).

**Safety:** All Firestore writes wrapped in try/except. Logging failure never breaks classification.

---

## TariffCache

Per-request in-memory cache that avoids repeated Firestore reads during one elimination run. One `TariffCache` instance per `eliminate()` call. Not shared across requests.

**Cached data:**
| Cache | Key | Source Collection | Doc IDs |
|-------|-----|-------------------|---------|
| `_chapter_notes` | chapter "84" | `chapter_notes` | `chapter_84` |
| `_section_data` | section "XVI" | `tariff_structure` | `section_XVI` |
| `_chapter_to_section` | chapter "84" → "XVI" | `tariff_structure` | `chapter_84` |
| `_headings` | heading "8471" | `tariff` | query by heading field |

---

## Key Regex Patterns

| Pattern | Source | Purpose |
|---------|--------|---------|
| `_CHAPTER_REF_RE` | `justification_engine.py:522` | Match "chapter 84" / "פרק 84" / "בפרק 84" |
| `_DEFINITION_RE` | D2 | Match "in this chapter X means..." / "בפרק זה..." |
| `_EXCEPTION_RE` | D2 | Match "except for" / "למעט" / "unless" |
| `_HEADING_REF_RE` | D2 | Match "heading 73.26" / "פרט 73.26" |
| `_VAGUE_HEADING_RE` | D3 | Match vague headings ("others", "n.e.s.") |
| `_OTHERS_RE` | D5 | Extended catch-all detection including "שלא פורט" |
| `_PRINCIPALLY_RE` | D5 | Match "באופן עיקרי" / "principally" / "mainly" |
| `_PERCENTAGE_RE` | D4 | Match "XX%" in composition text |

---

## Bilingual Term Sets

| Set | Count | Purpose |
|-----|-------|---------|
| `_STOP_WORDS` | ~40 | Hebrew + English stop words for keyword extraction |
| `_MATERIAL_TERMS` | ~60 | Material words (steel/פלדה, plastic/פלסטיק, etc.) |
| `_FORM_TERMS` | ~40 | Form/shape words (box/קופסה, tube/צינור, etc.) |
| `_ESSENTIAL_CHARACTER_TERMS` | ~80 | Materials for GIR 3ב essential character test |

---

## Scoring Thresholds

| Parameter | Value | Where Used |
|-----------|-------|------------|
| Section scope: min keywords for signal | >= 5 | Level 1 |
| Exclusion/inclusion keyword overlap | >= 2 | Level 2b |
| Preamble scope: min keywords | >= 3 | Level 2a |
| Cross-chapter redirect boost | +8 confidence | Level 2c |
| Definition match boost | +10 confidence | Level 2d |
| GIR 1 composite weights | 0.50/0.25/0.25 | Level 3 |
| GIR 1 bottom elimination | 30% of survivors | Level 3 |
| GIR 1 min survivors | 3 to trigger elimination | Level 3 |
| Subheading note boost | +5 confidence | Level 3b |
| GIR 3א specificity margin | >= 0.15 | Level 4a |
| GIR 3ב material dominance | >= 60% | Level 4a |
| AI consultation trigger | >3 survivors | Level 4c |
| AI confidence threshold | >= 70 | Level 4c |
| AI max eliminations | 2 per consultation | Level 4c |

---

## Dependencies

### Reads From (does NOT modify)
| Collection | What | Used By |
|-----------|------|---------|
| `chapter_notes` | Exclusions, inclusions, preamble, definitions, subheading rules | Levels 2a-2d, 3b |
| `tariff_structure` | Section↔chapter mapping, section scope text, chapter names | Levels 0-1 |
| `tariff` | Heading descriptions for GIR 1 matching | Level 3, 4a |

### Writes To
| Collection | What | Used By |
|-----------|------|---------|
| `elimination_log` | One doc per elimination run (full audit trail) | Level 7 (D8) |

### Code Dependencies
| Module | Function | Used By |
|--------|----------|---------|
| `classification_agents` | `call_ai()` | D6 AI consultation, D7 devil's advocate |

`call_ai()` is lazy-imported inside `_ai_consultation_hook()` and `_run_devils_advocate()` — the engine works without it in deterministic-only mode.

---

## GIR Rules Mapping

The Israeli customs tariff follows WCO General Interpretive Rules (GIR / כללי פרשנות כלליים):

| GIR Rule | Hebrew | Engine Level | Implementation |
|----------|--------|-------------|----------------|
| GIR 1 | כלל 1 — פרט ראשי | Level 3 | Heading description vs product. Composite scoring. |
| GIR 2a | כלל 2א — מוצר לא גמור | — | Not implemented (deferred) |
| GIR 2b | כלל 2ב — תערובות | — | Not implemented (deferred) |
| GIR 3a | כלל 3א — תיאור ספציפי | Level 4a | Most specific heading wins |
| GIR 3b | כלל 3ב — מהות עיקרית | Level 4a | Essential character test |
| GIR 3c | כלל 3ג — אחרון לפי הסדר | Level 4a | Last numerical order fallback |
| GIR 4 | כלל 4 — מוצר דומה | — | Not implemented (deferred) |
| GIR 5 | כלל 5 — אריזה | — | Not implemented (deferred) |
| GIR 6 | כלל 6 — פרטי משנה | Partial | Subheading notes (Level 3b) |

---

## Conservative Elimination Philosophy

The engine errs on the side of keeping candidates alive:

1. **When in doubt, keep.** If keyword overlap is ambiguous, the candidate survives.
2. **Safety guards.** Every elimination level ensures at least 1 survivor remains.
3. **Conditional exclusions.** Exception clauses ("except for X") are parsed — if the product matches the exception, the exclusion doesn't apply.
4. **AI is advisory.** D6 AI consultation can eliminate at most 2 candidates per run, and only with confidence >= 70.
5. **Devil's advocate is non-destructive.** D7 only adds challenges to the result — never eliminates.
6. **Logging is safe.** D8 Firestore writes are try/except wrapped — failure never breaks classification.

---

## D9: Pipeline Wiring (NEXT SESSION)

What D9 needs to do:
1. Wire `eliminate()` into the classification pipeline (after `pre_classify`, before cross-check)
2. Register `run_elimination` as a new tool in `tool_definitions.py`
3. Add tool executor in `tool_executors.py`
4. Convert pre_classify output to candidates via `candidates_from_pre_classify()`
5. Convert invoice item to product info via `make_product_info()`
6. Pass API keys from Secret Manager to `eliminate()`
7. Include elimination results in classification output (survivors, steps, challenges)

---

## Git History

| Block | SHA | Date | Description | Lines |
|-------|-----|------|-------------|-------|
| D1 | `2841a07` | 2026-02-18 | Core tree walk, TariffCache, section/chapter/heading | +801 |
| D2+D3 | `8b9e370` | 2026-02-18 | Chapter notes deep + GIR 1 full semantics | +606 |
| D4+D5 | `e485b65` | 2026-02-18 | GIR 3 tiebreak + Others gate + principally test | +563 |
| D6+D7+D8 | `e3913eb` | 2026-02-18 | AI consultation + devil's advocate + logging | +378 |
| **Total** | | | | **2,282** |
