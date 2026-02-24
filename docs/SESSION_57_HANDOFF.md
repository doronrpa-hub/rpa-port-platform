# Session 57 Handoff — 24 February 2026

## What Was Done

### 1. Intelligence Routing Spec (commit `b5a95ae`)
- Created `docs/RCB_INTELLIGENCE_ROUTING_SPEC.md` — 10-part mandatory spec
- Added first-line reference in `CLAUDE.md` CRITICAL RULES section
- Covers: domain detection, source routing, classification brain, anti-loop, banned phrases, composition rules, validation gate, anti-patterns, implementation priority

### 2. Phase 1: Three Intelligence Gates (commit `06caea3`)

**New file: `functions/lib/intelligence_gate.py` (~400 lines)**

| Gate | What It Does | Fail Mode |
|------|-------------|-----------|
| HS Code Validation | Checks every code against tariff DB before email send. Auto-corrects to nearest valid code. Searches same heading then chapter for candidates. | Fail-open |
| Loop Breaker | Tracks attempts in Firestore `classification_attempts/{thread_key}`. Max 2 per thread. After 2 → escalation email to doron@rpa-port.co.il, blocks classification. | Fail-open |
| Banned Phrase Filter | Scans HTML for 20+ phrases ("consult a customs broker", "unclassifiable", etc.), replaces with RCB contact info. | Fail-open |

**Wiring in `classification_agents.py`:**
- Loop breaker runs at line ~3195 BEFORE classification starts
- All 3 gates run at line ~3603 BEFORE email is sent via `_send_threaded()`
- HS codes recorded to `classification_attempts` AFTER successful send
- Error template footers fixed: removed "יש לאמת עם עמיל מכס מוסמך" (was in 2 places)

**New collection:** `classification_attempts` — registered in `librarian_index.py`

**Tests:** 34 new in `test_intelligence_gate.py`, 1,219 total passing

### 3. Prior Work (commit `fbf62e2`, pushed earlier)
- **P1**: Framework order parser fix — all 33/33 articles extracted (was 31). Generated `_framework_order_data.py` (47K chars Hebrew). Wired into `search_legal_knowledge` (Cases D+E) and `email_intent` `_extract_legal_context`.
- **P2**: Classification emails now thread via Graph API `/reply` endpoint. Added `attachments_data` to `helper_graph_reply`. Falls back to `helper_graph_send` if reply fails.

## Files Created This Session
| File | Lines | Purpose |
|------|-------|---------|
| `docs/RCB_INTELLIGENCE_ROUTING_SPEC.md` | 853 | Mandatory intelligence routing spec |
| `functions/lib/intelligence_gate.py` | ~400 | Phase 1: 3 gates (HS validation, loop breaker, banned phrases) |
| `functions/tests/test_intelligence_gate.py` | ~230 | 34 tests for intelligence gate |
| `functions/lib/_framework_order_data.py` | ~1400 | 33 framework order articles (generated) |

## Files Modified This Session
| File | Changes |
|------|---------|
| `CLAUDE.md` | +1 line: mandatory spec reference |
| `functions/lib/classification_agents.py` | +intelligence gate imports+wiring, +threading imports, +_send_threaded, error footer fix |
| `functions/lib/tool_executors.py` | +framework order Cases 0/D/E in search_legal_knowledge |
| `functions/lib/tool_definitions.py` | +framework order in search_legal_knowledge description |
| `functions/lib/email_intent.py` | +Cases D/E in _extract_legal_context |
| `functions/lib/rcb_helpers.py` | +attachments_data param on helper_graph_reply |
| `functions/lib/librarian_index.py` | +classification_attempts collection |
| `functions/parse_framework_order.py` | Title-anchored parser rewrite |

## Git Commits (all pushed to origin/main)
| SHA | Description |
|-----|-------------|
| `fbf62e2` | Session 56: Framework order parser fix (33/33) + email threading |
| `b5a95ae` | docs: RCB Intelligence Routing Spec v1.0 |
| `06caea3` | Session 57: Intelligence Gate Phase 1 — HS validation, loop breaker, banned phrases |

## Test Results
- **1,219 passed**, 0 failed, 0 skipped

## What to Do Next (Priority Order)

### Immediate: Phase 2 from Intelligence Routing Spec
1. **Domain Detection** — implement `detect_domains()` as pure Python function in `intelligence_gate.py`. Keyword matching per the 8 domains in the spec. No AI call needed.
2. **Source Routing** — for each domain, go directly to relevant ordinance articles instead of flat keyword search:
   - IP questions → articles 200א-200יד (all 14 articles)
   - Valuation → articles 130-136
   - FTA → framework order articles
   - Penalties → articles 190-231
3. **Targeted Article Retrieval** — new function `get_articles_by_domain()` that fetches article groups by ID from `_ordinance_data.py` and `_framework_order_data.py`
4. Wire domain detection into `email_intent.py` `_handle_knowledge_query` and `_handle_customs_question`

### Later: Phase 3 from Intelligence Routing Spec
5. Classification with legal basis — cite GIR rules and chapter notes in output
6. Automatic regulatory check — after classification, auto-check צו יבוא/יצוא
7. FTA integration — after classification, check applicable FTAs
8. Cross-reference engine — combine multiple sources per query

### Other Pending
- Run local PC agent → process 18 browser tasks (FTA agreements + procedures)
- Deploy to Firebase after changes
- Live test with the 5 test emails from the spec (Part 10)

## Known Issues
- Gemini free tier quota exhaustion still causes fallback to Claude (consider paid tier)
- C7 (pre-rulings) still blocked — no data source
- `_check_tariff_db` in intelligence_gate.py uses single-doc Firestore lookups (fast but may miss some tariff entries stored under non-standard doc IDs)
