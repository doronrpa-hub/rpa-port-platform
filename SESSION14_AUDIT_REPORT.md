# SESSION 14 — SELF-AUDIT REPORT
## language_tools.py Review Before Integration

**Date:** 2026-02-06  
**Status:** ⚠️ ERRORS FOUND — DO NOT INTEGRATE WITHOUT FIXES

---

## 🔴 FACTUAL ERRORS FOUND (3)

### Error 1: Israeli HS Code is 10 DIGITS, not 8

**What I wrote:**
```python
ISRAEL_HS_CODE_DIGITS = 8
ISRAEL_HS_CODE_FORMAT = "XXXX.XX.XX"
ISRAEL_HS_CODE_EXAMPLE = "8708.99.80"
```

**What it should be:**
The Israel Tax Authority's own definition:
> "פרט מכס הינו מספר בין 10 ספרות המכיל את מספר הפרק, הפרט ופרט משנה"
> "A customs item is a **10-digit number** containing chapter, item, and sub-item."

Structure: 6 (international WCO HS) + 4 (Israeli national digits) = **10 digits**

Multiple sources confirm:
- Orian.com (quoting Israel Tax Authority): "base code is 6 digits, each country adds 4 more"
- Traddal.com: "Israel uses an extended 10-digit import classification structure"
- FreightAmigo: "HS structure: 6-digit global, 10-digit Israel-specific"

The academic paper saying "digits 7-8" was referring to one LAYER of Israeli additions (called "paragraphs/articles"), not the total count.

**Impact:** HS code validator rejects valid 10-digit Israeli codes. Classification reports show truncated codes.

**Fix needed:** Change constant to 10, update validator to accept `XXXX.XX.XXXX` and flat `XXXXXXXXXX`, update all examples.

**⚠️ NOTE TO USER:** I still don't know the EXACT dotted display format your system uses (is it `8708.99.8000` or `8708.9980.00` or `87.08.99.80.00`?). You use שער עולמי daily — please confirm your display format.

---

### Error 2: De Minimis is $150 USD, not ILS

**What I wrote:**
```python
ISRAEL_DE_MINIMIS_ILS = 150
```

**What it should be:**
The threshold is **$150 USD** (approximately 545 ILS), not 150 ILS.
- Was $75 USD, doubled to $150 USD in late 2025
- Signed by Finance Minister Smotrich (November 2025)
- Under legislative review/challenge from business groups

**Impact:** If this value is used in any calculation or document, it's off by ~3.6x.

---

### Error 3: שע"מ abbreviation is suspicious

**What I wrote:**
```python
'שע"מ': "שער עולמי"
```

**Concern:** The system is called "שער עולמי" (Shaar Olami / Global Gate), but the standard acronym would be ש"ע or שע"ו, not שע"מ. I fabricated this abbreviation from training data without verification.

**⚠️ NOTE TO USER:** Please confirm whether שע"מ is actually used in your organization.

---

## 🟡 INTEGRATION RISKS (7)

### Risk 1: Unknown Existing Function Signatures

I created drop-in replacements for:
- `build_rcb_subject()` (line 53 of classification_agents.py)
- `build_html_report()` (line 435 of classification_agents.py)

**But I don't have the actual codebase.** I don't know:
- What arguments the existing callers pass
- What return type they expect
- What error handling wraps the calls
- Whether there are tests that assert specific output formats

**Risk:** My wrappers may not match the expected interface.

**Mitigation:** Before integrating, diff my function signatures against the actual code.

---

### Risk 2: librarian_tags.py Data Structure Assumptions

My `bootstrap_vocabulary()` assumes:
```python
# I assume DOCUMENT_TAGS is: {"tag_key": "Hebrew name"}
# I assume CUSTOMS_HANDBOOK_CHAPTERS is: {chapter_num: {"name_he": ..., "tag": ..., "sub_chapters": {...}}}
# I assume TAG_KEYWORDS is: {"tag": ["keyword1", "keyword2"]}
```

**But these might have different structures.** If they're nested differently, the bootstrap silently produces empty vocabulary instead of crashing (bad — silent failure).

**Mitigation:** Need to see actual librarian_tags.py to verify.

---

### Risk 3: Firestore Schema Conflicts

The mission doc proposes Firestore collections:
```
language_corrections/{correction_id}/...
vocabulary_additions/{term_id}/...
```

My code has `to_dict()` / `from_dict()` methods but:
- Doesn't import `google.cloud.firestore`
- Doesn't know the existing Firestore project ID or collection structure
- Doesn't handle transaction conflicts with other processes writing to Firestore

**Conflict risk:** If `enrichment_agent.py` or `librarian.py` is also writing documents concurrently, there could be write conflicts or inconsistent reads.

---

### Risk 4: Thread Safety / Serverless State

`CustomsVocabulary`, `StyleAnalyzer`, and `LanguageLearner` all hold mutable state in memory:
- `terms_he`, `contact_profiles`, `corrections`, `learned_spelling`

In a Cloud Functions environment:
- State doesn't persist between cold starts
- Concurrent requests may modify shared state
- No locking mechanism

**Impact:** Learned corrections and contact profiles could be lost or corrupted.

**Mitigation:** Every invocation should load from Firestore, process, save back. The `to_dict()`/`from_dict()` pattern supports this, but the calling code must implement it.

---

### Risk 5: Claude API Call Structure Unknown

The `TextPolisher.build_polish_prompt()` generates a text block to append to Claude calls. But I don't know:
- How `call_claude()` (line 149 of classification_agents.py) structures its messages
- Whether it uses system prompts, tool definitions, or a specific model version
- Whether there's a token budget that my added polish prompt would exceed

**Risk:** Appending ~200 tokens of polish instructions could push the request over token limits or conflict with the existing system prompt.

---

### Risk 6: clarification_generator.py Has 6 Letter Types (I didn't replicate them)

The mission doc says clarification_generator.py has 6 specific letter types (lines 290-670):
1. Missing docs
2. Clarification
3. CIF completion
4. Origin inquiry
5. Combined
6. Generic

My `LetterStructure` provides a generic template engine. **But I didn't create specific templates for each of the 6 types.** The existing code has specific Hebrew phrases, urgency levels, and document descriptions for each type.

**Risk:** Swapping to LetterStructure without replicating the 6 type-specific templates would produce generic letters where specific ones are needed.

**Mitigation:** The integration should map each existing type to a LetterStructure configuration, preserving the specific phrases and document descriptions.

---

### Risk 7: Gemini — Still Unresolved

The mission doc (line 11) says:
> "Gemini integration — was attempted but not working; need to review and fix or replace"

My code doesn't address Gemini at all. If there's dead Gemini code in the existing codebase, it could conflict with the new language tools, especially if both try to process the same text.

---

## 🟡 SUSPICIOUS ABBREVIATIONS & TERMS TO VERIFY

| Item | What I wrote | Concern |
|------|-------------|---------|
| שע"מ | שער עולמי | Abbreviation likely wrong — verify |
| מס"ב | מס ערך מוסף בשיעור אפס | Non-standard abbreviation — verify |
| מ.ב | מסמך ביטחון | Can't confirm this is standard |
| בל"ד | בית לחם דרום (מעבר) | Politically sensitive — verify if relevant to your operations |

---

## 🟢 WHAT'S CORRECT & TESTED

| Item | Status | Notes |
|------|--------|-------|
| VAT = 18% | ✅ Verified | Multiple authoritative sources confirm |
| VAT auto-fix (17%→18%) | ✅ Working | Tested 6 patterns, context-aware (ignores non-VAT 17%) |
| Known typos dict | ✅ Working | 20+ corrections, all fire correctly |
| Gender agreement check | ✅ Working | Feminine/masculine noun rules |
| RTL/LTR spacing fix | ✅ Working | Adds space between Hebrew↔English |
| Subject line generator | ✅ Working | Hebrew + English, emoji, 120-char |
| Letter HTML structure | ✅ Working | Clean RTL, professional CSS |
| Style analyzer | ✅ Working | Detects official/professional/casual/colloquial |
| Contact profiling | ✅ Working | Learns formality score per contact |
| Joke bank | ✅ Working | 22 jokes, no gender/race/political content |
| Serialization (to_dict/from_dict) | ✅ Working | StyleAnalyzer and LanguageLearner |

---

## 📋 BEFORE INTEGRATION CHECKLIST

1. ☐ **Get actual codebase files** — need classification_agents.py, clarification_generator.py, librarian_tags.py to verify interfaces
2. ☐ **Fix HS code to 10 digits** — confirm exact display format with user
3. ☐ **Fix de minimis to $150 USD** — not ILS
4. ☐ **Verify abbreviations** — especially שע"מ, מס"ב, מ.ב, בל"ד with actual customs broker
5. ☐ **Test bootstrap with real librarian_tags data** — verify data structure assumptions
6. ☐ **Map 6 letter types** — create LetterStructure configs for each clarification type
7. ☐ **Decide Gemini** — kill it or fix it
8. ☐ **Add Firestore persistence layer** — load/save on each Cloud Function invocation
9. ☐ **Token budget check** — verify TextPolisher prompt fits within Claude API limits

---

## 📊 MODULE STATS

- **Lines:** 1,994
- **Classes:** 8 (CustomsVocabulary, HebrewLanguageChecker, LetterStructure, SubjectLineGenerator, StyleAnalyzer, TextPolisher, LanguageLearner, JokeBank)
- **Data classes:** 5 (SpellingIssue, GrammarIssue, StyleObservation, LetterHead, SignatureBlock)
- **Enums:** 3 (LetterType, Tone, LanguageRegister)
- **Known typos:** 24 entries
- **Formal↔informal mappings:** 18 entries
- **Abbreviations:** 25 entries
- **Collocations:** 12 entries
- **Jokes:** 22 (12 HE + 10 EN)
