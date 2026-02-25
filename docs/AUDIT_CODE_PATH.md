# Code Path Audit: CUSTOMS_QUESTION Email Routing

**Date:** 2026-02-25
**Auditor:** Claude Code Session 73
**Test input:** "מה פרט המכס למכונת קפה ביתית?" from doron@rpa-port.co.il → rcb@rpa-port.co.il
**Status:** Read-only audit — no code modified

---

## 1. Entry Point — `main.py`

Email enters via `rcb_check_email()` (line 756) → `_rcb_check_email_inner()`.

**Sender filters (lines 820-825):**
- `rcb@rpa-port.co.il` → SKIP (self-loop prevention)
- `cc@rpa-port.co.il` → SKIP
- `doron@rpa-port.co.il` → PASSES all filters

**Direct email detection (line 814):** `is_direct = True` (rcb@ is in TO recipients)

**Reply-to resolution (lines 936-950):** `_reply_to = "doron@rpa-port.co.il"` (sender matches `@rpa-port.co.il`)

### Decision Tree for Direct Emails (lines 930-1010)

```
Line 971: Brain Commander check → No match → continue
Line 988: EMAIL_INTENT_AVAILABLE → True → call process_email_intent()
  Line 993: _intent_name = "CUSTOMS_QUESTION"
  Line 994: _intent_status = "replied" (happy path)
  Line 996: "CUSTOMS_QUESTION" not in ('NONE','') → True
  Line 997: not (INSTRUCTION + action=classify) → True
  Line 999: status in ('replied','cache_hit','clarification_sent') → True → log
  Line 1003: helper_graph_mark_read()
  Line 1004-1009: rcb_processed.set({type: "intent_CUSTOMS_QUESTION"})
  Line 1010: continue → EXIT — no knowledge_query, no classification
```

**What is NEVER reached for this email:**
- `detect_knowledge_query()` at line 1015
- Shipping-only routing at line 1047
- External rate limiting at line 1095
- Classification pipeline at line 1119

---

## 2. Intent Detection — `email_intent.py:234-350`

`detect_email_intent()` checks intents in priority order (cheapest first):

| Order | Intent | Match? | Line |
|-------|--------|--------|------|
| 1 | ADMIN_INSTRUCTION | No | 250-258 |
| 2 | NON_WORK | No | 260-267 |
| 3 | INSTRUCTION | No | 269-281 |
| 3b | CORRECTION | No | 283-293 |
| **4** | **CUSTOMS_QUESTION** | **YES** | **296-303** |
| 5 | STATUS_REQUEST | — skipped — | 305-329 |
| 6 | KNOWLEDGE_QUERY | — skipped — | 331+ |

### Regex Match Verification (ran live)

**CUSTOMS_Q_PATTERNS** defined at `email_intent.py:128-145` (13 patterns):

```python
CUSTOMS_Q_PATTERNS = [
    r'(?:what\s*(?:is\s*the\s*)?(?:hs|tariff|duty|customs)\s*(?:code|rate|classification))',
    r'(?:what\'?s?\s*the\s*(?:duty|tariff|customs)\s*(?:rate|code|classification))',
    r'(?:duty\s*rate|tariff\s*rate|customs\s*(?:duty|rate|code))',
    r'(?:מה\s*(?:ה?סיווג|ה?מכס|ה?תעריף|קוד\s*מכס|ה?מס))',
    r'(?:how\s*(?:much|to)\s*(?:duty|import|clear))',
    r'(?:כמה\s*מכס|איך\s*(?:ליבא|לשחרר|לסווג))',
    r'\b\d{4}\.\d{2}(?:\.\d{2,4})?\b',
    r'(?:פרט\s*(?:ה?מכס|מכסי)|שיעור\s*(?:ה?מכס|מכסי))',          # Pattern 7
    r'(?:מה\s*(?:פרט|שיעור)\s*(?:ה?מכס|מכסי))',                    # Pattern 8
    r'(?:מה\s*(?:צריך|נדרש)\s*(?:כדי\s*)?(?:ליבא|לייבא|ליצא|לייצא))',
    r'(?:(?:ליבא|לייבא|ליצא|לייצא)\s+.{3,}?\s*(?:ל?ישראל|\?))',
    r'(?:יבוא\s+.{3,}\s*(?:מ|מה|ל?ישראל))',
    r'(?:מכס\s+על\s+(?:יבוא|ייבוא|יצוא|ייצוא))',
]
```

**Live test result against "מה פרט המכס למכונת קפה ביתית?":**
```
Pattern 7: MATCH → "פרט המכס"     (first match, wins)
Pattern 8: MATCH → "מה פרט המכס"  (also matches, but pattern 7 comes first)
```

Pattern 7 matches first (line 138 in the list). Intent returned with confidence 0.85.

---

## 3. Entity Extraction — `email_intent.py:385-429`

`_extract_customs_entities()` runs 7 description patterns in priority order.

**Pattern 0 matches (line 396):**
```
Regex:   r'(?:פרט\s*(?:ה?מכס|מכסי)\s*(?:ל|של|על)\s*)(.{3,80}?)(?:\?|$|\.)'
Input:   "מה פרט המכס למכונת קפה ביתית?"
Group 1: "מכונת קפה ביתית"
```

**Live test confirmed:** `product_description = "מכונת קפה ביתית"`

Result: `{"intent": "CUSTOMS_QUESTION", "confidence": 0.85, "entities": {"product_description": "מכונת קפה ביתית"}}`

---

## 4. Handler — `_handle_customs_question()` at `email_intent.py:1530-1715`

**Signature:**
```python
def _handle_customs_question(db, entities, msg, access_token, rcb_email, get_secret_func):
```

**Execution flow for "מכונת קפה ביתית":**

| Step | Lines | Action | Expected Result |
|------|-------|--------|-----------------|
| Domain detection | 1550-1555 | `_detect_domains_safe(full_text)` | `domain_names = []` (coffee machine is not a customs domain like VALUATION/IP/FTA) |
| Targeted articles | 1557-1569 | `_fetch_domain_articles([])` | `domain_articles = []` (no domains detected) |
| **search_tariff** | **1577-1591** | `executor.execute("search_tariff", {"item_description": "מכונת קפה ביתית"})` | HS candidates from Firestore `tariff` collection |
| check_regulatory | 1593-1605 | SKIPPED — `hs_code` is None | No regulatory data |
| search_legal_knowledge | 1607-1617 | `executor.execute("search_legal_knowledge", ...)` | Runs because `not domain_articles` |
| lookup_fta | 1619-1644 | Runs — `product_desc` is truthy | FTA check |
| AI compose | 1671-1678 | `_compose_reply(context, "מכונת קפה ביתית", get_secret_func)` | Hebrew reply text |
| Build HTML | 1680-1690 | `_wrap_html_rtl()` + candidates table + FTA info | Complete reply_html |
| Send | 1700-1701 | `_send_reply_safe(reply_html, msg, ..., subject_override=reply_subject)` | True/False |

### search_tariff call (the exact line)

**Line 1581:**
```python
result = executor.execute("search_tariff", {
    "item_description": tariff_query,
})
```

Where `tariff_query = product_desc` = `"מכונת קפה ביתית"` (line 1578).

---

## 5. Candidates Table — `_build_candidates_table_html()`

**Exists:** Yes, at `email_intent.py:1370`
**Called:** Yes, at line 1683:
```python
candidates_html = _build_candidates_table_html(tariff_candidates, product_desc)
```
**Inserted into reply_html:** Yes, at lines 1684-1685:
```python
if candidates_html:
    reply_html = reply_html + candidates_html
```

For "מכונת קפה ביתית", the function also triggers **coffee-specific clarification questions** at line 1423:
```python
if any(w in pd for w in ["קפה", "coffee", "אספרסו", "espresso"]):
    questions = [
        "סוג המכונה — אספרסו/פילטר/קפסולות?",
        "ביתית או מסחרית/תעשייתית?",
        "עם מטחנה מובנית?",
        "מדינת מקור",
    ]
```

---

## 6. Send Path — `_send_reply_safe()` at `email_intent.py:789-845`

**5 gates that can return False:**

| # | Line | Gate | Condition |
|---|------|------|-----------|
| 1 | 799 | External sender block | `from_email` not `@rpa-port.co.il` |
| 2 | 807 | CC-only block | `is_direct_recipient(msg, rcb_email)` returns False |
| 3 | 814 | Banned phrase filter | Does NOT block — only cleans content |
| 4 | 840 | `helper_graph_reply` | Graph API error, or quality gate rejects |
| 5 | 843 | `helper_graph_send` (fallback) | Same — quality gate or Graph API failure |

For our email from doron@:
- Gate 1: doron@ ends with `@rpa-port.co.il` → PASSES
- Gate 2: rcb@ is in TO → PASSES
- Gate 3: AI reply goes through `filter_banned_phrases()` → cleaned, not blocked
- Gate 4: `helper_graph_reply` → threaded reply attempt
- Gate 5: `helper_graph_send` → fallback if reply fails

**Inside `helper_graph_reply` (rcb_helpers.py:777), additional sub-gates:**
- `to_email=from_email` → not None → passes (line 789)
- `_is_internal_recipient(doron@rpa-port.co.il)` → True → passes (line 803)
- `email_quality_gate(to_email, subject, body_html)` → Could reject (line 822-827)

---

## 7. Failure Handling — What Happens When Send Fails

At `email_intent.py:1702-1705`:
```python
sent = _send_reply_safe(...)
if not sent:
    logger.warning(f"CUSTOMS_QUESTION reply send failed...")
return {"status": "send_failed", "intent": "CUSTOMS_QUESTION", ...}
```

Back in `main.py:993-1010`:
```python
_intent_name = "CUSTOMS_QUESTION"   # not NONE → condition at line 996 is True
_intent_status = "send_failed"      # NOT in ('replied','cache_hit','clarification_sent')
```

Line 1001-1002 (else branch): prints warning
Line 1003: `helper_graph_mark_read()` — **marks email as read**
Line 1010: `continue` — **EXITS regardless of send success**

---

## 8. "לא הצלחנו לסווג" — Present in Codebase

| File | Line | Context |
|------|------|---------|
| `intelligence_gate.py` | 390 | In BANNED_PHRASES — will be stripped from any outgoing email |
| `classification_agents.py` | 3143 | Extraction failure template (file-read failure, not classification) |

The phrase is in BANNED_PHRASES and will be removed by `filter_banned_phrases()` before any reply is sent.

---

## 9. BANNED_PHRASES — Full List (28 entries)

Defined at `intelligence_gate.py:366-398`:

```python
BANNED_PHRASES = [
    # Hebrew — "consult a customs broker" variants (8)
    "מומלץ לפנות לעמיל מכס",
    "מומלץ להתייעץ עם עמיל מכס",
    "מומלץ להתייעץ עם סוכן מכס",
    "יש לפנות לעמיל מכס",
    "יש להתייעץ עם עמיל מכס",
    "פנה לעמיל מכס",
    "פנו לעמיל מכס",
    "התייעצו עם עמיל מכס",
    # English — broker referral variants (5)
    "consult a customs broker",
    "consult a licensed customs broker",
    "consult with a customs broker",
    "seek professional customs advice",
    "contact a customs agent",
    # Uncertainty phrases (9)
    "I'm not sure",
    "I am not sure",
    "I cannot determine",
    "unable to classify",
    "unclassifiable",
    "לא ניתן לסווג",
    "לא ניתן לקבוע",
    "לא הצלחנו לסווג",
    "לא הצלחנו לקבוע",
    "אין מספיק מידע",
    # Hebrew — customs advisor variants (2)
    "פנה ליועץ מכס",
    "פנו ליועץ מכס",
    # Duplicate English (1)
    "consult a customs agent",
    # Footer disclaimer (1)
    "יש לאמת עם עמיל מכס מוסמך",
]
```

Replacement text: `"לפרטים נוספים ניתן לפנות לצוות RCB בכתובת rcb@rpa-port.co.il"`

---

## 7 Failure Points

| # | Failure | Trigger | Impact | Severity |
|---|---------|---------|--------|----------|
| **F1** | `search_tariff` returns 0 candidates | Firestore down or no keyword match | Empty candidates table; AI reply sent but unhelpful | MEDIUM |
| **F2** | `_compose_reply` fails | All 3 AI models down (ChatGPT + Gemini + template) | Template: "לא נמצא מידע על X במערכת" — bare but accurate | LOW |
| **F3** | Quality gate rejects short reply (`body_under_200`) | AI reply < 200 chars (e.g., template fallback ~50 chars) | **`send_failed` → email consumed silently, user gets nothing** | **HIGH** |
| **F4** | Graph API failure (both reply + send) | Token expired, 429 throttle, MS outage | **`send_failed` → email consumed silently, user gets nothing** | **HIGH** |
| **F5** | Banned phrase stripping breaks reply coherence | AI says "לא ניתן לסווג" mid-sentence | Sentence fragment sent, still readable | LOW |
| **F6** | `ToolExecutor(api_key=None)` limits some tools | No AI keys for vision/extraction tools | Not relevant — `search_tariff` is Firestore-only | NONE |
| **F7** | Zero context from all sources | No tariff match + no legal match + no domain match | Template reply "לא נמצא מידע..." — no AI cost, useless answer | MEDIUM |

### F3 + F4: Silent Email Consumption (shared root cause)

**Root cause:** `main.py:996-1010` exits on intent **detection**, not intent **success**.

```python
# main.py:996
if _intent_name not in ('NONE', '') and not (
    _intent_name == 'INSTRUCTION' and intent_result.get('action') == 'classify'
):
    # Lines 999-1002: log success or failure (print only)
    helper_graph_mark_read(...)     # marks email as read
    rcb_processed.set({...})        # logs as processed
    continue                        # EXIT — no fallback to knowledge_query or classification
```

When `status="send_failed"`:
- Email marked as read in Outlook
- Logged to `rcb_processed` as `intent_CUSTOMS_QUESTION`
- **NOT retried** — won't be picked up by next poll cycle
- **NOT forwarded** to `detect_knowledge_query()` (line 1015) or classification (line 1119)
- **User gets no response**

---

## Files Audited

| File | Lines Read | Purpose |
|------|-----------|---------|
| `functions/main.py` | 756-1010 | Email loop, intent dispatch, exit logic |
| `functions/lib/email_intent.py` | 128-145, 234-303, 385-429, 789-845, 1370-1450, 1530-1715 | Patterns, detection, extraction, handler, send, candidates table |
| `functions/lib/rcb_helpers.py` | 777-830, 873-886 | `helper_graph_reply`, `is_direct_recipient`, quality gate |
| `functions/lib/intelligence_gate.py` | 366-402 | BANNED_PHRASES list and filter |
