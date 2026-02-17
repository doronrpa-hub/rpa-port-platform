# RCB TARGET ARCHITECTURE — REVIEW ANSWERS
## Answered by Claude Code (Session 32) against live codebase + production Firestore
## Date: February 17, 2026

---

### Q1: Routing logic — Where does CC vs classification diverge?

**File:** `main.py:1083-1129`

The gate is `is_direct` (line 1084):
```python
is_direct = any(rcb_email.lower() in r.get('emailAddress', {}).get('address', '').lower()
                for r in to_recipients)
```

- `is_direct = False` (CC) → line 1096: `if not is_direct:` → pupil + tracker + save as `cc_observation` + `continue`
- `is_direct = True` (TO rcb@) → line 1132: gate to `@rpa-port.co.il` senders only → brain commander → knowledge query → shipping-only → classification pipeline

**CRITICAL FINDING:** 83% of emails (231/277) are CC observations. Zero go through classification because they all hit line 1129 `continue`.

---

### Q2: airpaport@gmail.com — Connected?

**NOT CONNECTED.** No reference to `airpaport@gmail.com` anywhere in the codebase.
System only monitors `rcb@rpa-port.co.il` via Microsoft Graph API.

To connect: Gmail API (OAuth2), or forward airpaport@ to rcb@ with a tag.

---

### Q3: smart_extractor.py — Ready to wire?

**YES. One-line change.**

- `smart_extractor.py`: 668 lines, complete SmartExtractor class
- `extraction_adapter.py`: 281 lines, drop-in replacement wrapper

Change `main.py:25` from:
```python
from lib.rcb_helpers import extract_text_from_attachments
```
to:
```python
from lib.extraction_adapter import extract_text_from_attachments
```

Backward compatible. Same function signature. Same return format.

---

### Q4: keyword_index — What's in it?

**8,195 documents**, 98% clean.

**Missing:** Packaging terms (empty boxes, metal containers, IBC, pallets, drums), brand names (Goodpack), material categories (stainless steel, aluminum), use-case terms (food grade, industrial, automotive), common English product terms.

---

### Q5: Tariff data state — 35.7% garbage?

**CORRECTED.** Actual numbers from live Firestore:
- 0.2% garbage in parent_heading_desc (23/11,753) — NOT 35.7%
- 19.5% empty description_he (2,292/11,753) — THIS is the real problem
- 41.4% missing purchase_tax_pct (4,865/11,753)
- 7.6% missing customs_duty_pct (891/11,753)
- Chapter 40 (rubber): CORRECT data
- Chapter 73 (iron/steel): CORRECT data

---

### Q6: Legal sources in Firestore?

| Source | Collection | Status |
|--------|-----------|--------|
| Chapter notes (structured) | `chapter_notes` | 5+ docs, minimal |
| Chapter notes Hebrew | `chapter_notes_he` | **DOES NOT EXIST** |
| Chapter notes English | `chapter_notes_en` | **DOES NOT EXIST** |
| Free Import Order | FIO API (live lookup) | WORKS per classification |
| Classification directives | `classification_directives` | 217 docs (Assignment 17) |
| Legal requirements | `legal_requirements` | 7,443 docs |
| Regulatory requirements | `regulatory_requirements` | 28 docs |
| FTA agreements | `fta_agreements` | 21 docs |
| Pre-rulings | — | **DOES NOT EXIST** |
| Court decisions | — | **DOES NOT EXIST** |

---

### Q7: Email templates — What generates them?

- **Classification:** `build_classification_email()` in `classification_agents.py:1313-1769`
- **Tracker:** `build_tracker_status_email()` in `tracker_email.py:10-319`
- **Clarification:** `generate_missing_docs_request()` in `clarification_generator.py`

Infrastructure is solid (HTML, RTL, tables, Graph API). Layout needs redesign to table-first.

---

### Q8: Reply processing — Any mechanism?

**PARTIAL.**
- Tracking code extraction exists: `extract_tracking_from_subject()` extracts `RCB-YYYYMMDD-XXXXX`
- Reply threading: In-Reply-To and References headers set via Graph API
- **NO reply detection logic** — system doesn't recognize replies to RCB emails

---

### Q9: tool_calling_engine.py — Multi-model hooks?

**DEAD CODE.** ~500 lines, never called. `TOOL_CALLING_AVAILABLE = True` flag exists but `tool_calling_classify()` is never invoked from the production pipeline.

---

### Q10: classification_memory structures — Usable?

| Collection | Docs | Usable? |
|-----------|------|---------|
| `product_index` | 68 | YES |
| `classification_knowledge` | 84 | YES |
| `learned_classifications` | ~100+ | YES |
| `sellers` | ~50+ | YES |
| `brain_index` | 11,262 | YES |

Structures exist, need more data and better pipeline integration.

---

### Q11: cross_checker.py — Wired? Working?

**YES.** `CROSS_CHECK_ENABLED = True` (line 133). Sends to Claude + Gemini + ChatGPT + UK Tariff API. 4-tier comparison. Results logged to `cross_check_log`.

---

### Q12: Overnight brain — 9 streams?

Runs at 20:00 ISR, hard cap $3.50/run. ~$2.05 actual, ~$60/month.

Streams: tariff mine, email mine, CC learning, attachment mine, AI gap fill, UK API sweep (free), cross-reference, self-teach, knowledge sync.

---

### Q13: Dead code modules — What can be wired?

| Module | Lines | Effort |
|--------|-------|--------|
| smart_extractor.py | 668 | One-line import |
| extraction_adapter.py | 281 | IS the one-line change |
| doc_reader.py | 551 | Low |
| table_extractor.py | 223 | Already in tracker |
| tool_calling_engine.py | ~500 | Medium |
| pre_classify_bypass | ~30 | Low |
| document_parser.py (in cls) | 1,462 | Low |
| **Total activatable** | **~3,715** | |

---

### Q14: CC + airpaport volume?

From live Firestore (277 emails, ~2 weeks):
- CC observations: 231 (83%) → ~15-20/day
- Classifications: 86 total, ~6-8/day
- airpaport: Not connected, volume unknown
- Last classification: Feb 13 (4-day gap)

Cost model correction: 6-8/day not 20/day → costs will be ~40% of architecture estimates.

---

### Q15: Can system parse customs declarations?

**NO dedicated parser.** No `customs_declaration` document type in `document_parser.py`. PDF extraction works, but no field extraction for declaration format. Needs new doc type.

---

### Q16: Email sending — Library/method/HTML/RTL/Tables?

- **Library:** Microsoft Graph API REST (`POST /v1.0/users/{email}/sendMail`)
- **Function:** `helper_graph_send()` in `rcb_helpers.py:702-736`
- **HTML:** Full — `contentType: 'HTML'`, inline CSS, nested tables
- **RTL:** Full — `direction:rtl`, `dir="rtl"` throughout
- **Tables:** Extensive — classification cards, tax grids, progress bars
- **Hebrew:** Full — time greetings, name conversion, language checker
- **Threading:** RFC 2822 In-Reply-To/References headers
- **Tracking:** `RCB-YYYYMMDD-XXXXX` in subject, regex extraction, Firestore storage
