# Session 60 Handoff — 2026-02-24

## Commit
- `84c93b1` — Fix critical bug: AI ignores provided legal context, answers from training data

## What Was Done

### Problem
AI composition (ChatGPT/Gemini/Claude) ignored injected legal context and answered from training data. Nike test proved it: domain routing correctly found articles 200א-200יד and injected them into context, but AI wrote "המכס אינו עוסק בזכויות יוצרים או מותגים" — directly contradicting the provided articles.

### Fix — 3 layers across 2 files

**1. System prompts rewritten** (`email_intent.py` REPLY_SYSTEM_PROMPT + `knowledge_query.py` generate_reply system_prompt):
- Added "הוראה עליונה": answer ONLY from provided legal sources
- Added "אל תשתמש בידע האימון שלך" (don't use training knowledge)
- Added explicit IP articles notice: "סעיפים 200א–200יד עוסקים באכיפת קניין רוחני במכס"
- Added: "אל תכתוב שפקודת המכס אינה עוסקת בכך"

**2. User prompts strengthened** (all 3 AI paths: ChatGPT in `_call_chatgpt`, Gemini in `_call_gemini_flash`, Claude in `generate_reply`):
- Context wrapped in `=== מקורות משפטיים מוסמכים (ענה רק מתוכם) ===` delimiters
- Explicit instruction appended: "ענה רק על בסיס המקורות למעלה. אם יש סעיפים — צטט אותם."

**3. Post-reply validation** (`_validate_reply_uses_context()` added to both files):
- Detects when context contains articles 200א+ but reply doesn't mention "200"
- **Contradictory reply** (contains "אינו עוסק", "לא עוסקת", etc.): reply **replaced** with extracted article text
- **Non-contradictory but missing cite**: article references **prepended**
- Wired after `_compose_reply()` in `_handle_customs_question` and `_handle_knowledge_query` (email_intent.py)
- Wired after `call_claude()` in `generate_reply` (knowledge_query.py)

### Files Modified
| File | Changes |
|------|---------|
| `functions/lib/email_intent.py` | REPLY_SYSTEM_PROMPT rewritten (+IP context-only mandate), user prompts in _call_chatgpt and _call_gemini_flash strengthened with source delimiters, +`_validate_reply_uses_context()` function (~54 lines), wired in 2 handlers |
| `functions/lib/knowledge_query.py` | System prompt rewritten (+IP context-only mandate), user prompt strengthened with source delimiters, +`_validate_reply_uses_context()` function (~54 lines), wired after call_claude |

### Test Results
- **1268 passed**, 0 failed — zero regressions
- **80 email intent tests** all pass
- Manual validation tests of `_validate_reply_uses_context()` pass all 3 scenarios (contradiction replaced, missing cite prepended, non-IP unchanged)

### Live Nike Test Result
- Sent test email from doron@ to rcb@ with subject "בדיקה - זיוף Nike"
- **Domain routing**: Correctly detected `IP_ENFORCEMENT` + 4 other domains → 20 targeted articles
- **Intent**: Handled as `KNOWLEDGE_QUERY`
- **Tools executed**: search_tariff (5.1s), search_classification_directives (0.9s), lookup_framework_order (0.6s)
- **Reply received**: RCB correctly cited «סעיף 200א לפקודת המכס» with FULL verbatim Hebrew text
- **Validation**: Reply mentions "200" — PASS. No contradiction — PASS.
- **Reply quality**: Excellent — full legal procedure explained with proper citations

### What We Could NOT Confirm
Cloud Function logs (`gcloud functions logs read` / `gcloud logging read`) don't expose:
1. **Which AI model composed the reply** (ChatGPT vs Gemini vs template) — `_compose_reply` returns `(text, model)` but model name is not logged
2. **Whether `_validate_reply_uses_context()` triggered** — validation uses `logger.warning()` but these may be batched/suppressed in Cloud Run logs
3. **Whether the AI got it right on its own** or the validation function corrected it

### TODO for Next Session
1. **Add explicit logging** in `_compose_reply()` and both `_handle_*` functions:
   ```python
   print(f"  🤖 Reply composed by {model}, {len(reply_text)} chars")
   ```
2. **Add logging in `_validate_reply_uses_context()`**:
   ```python
   print(f"  🔍 Context validation: has_ip_articles={has_ip_articles}, reply_mentions_200={reply_mentions_200}")
   ```
   Use `print()` not `logger.warning()` — print goes to Cloud Run stdout which is always captured.
3. **Consider**: the validation function is duplicated across email_intent.py and knowledge_query.py. Could extract to a shared module (e.g., `reply_validation.py`) but low priority.

### Deployment
- Commit `84c93b1` pushed to `origin/main`
- All 28 Cloud Functions deployed successfully to `rpa-port-customs`
- `questions_log` cache cleared (1 stale Nike doc deleted before test)

### Cache Cleared
- Deleted 1 doc from `questions_log` containing "זיוף" (stale cache from previous failed test)
