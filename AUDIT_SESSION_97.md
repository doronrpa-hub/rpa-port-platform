# RCB System Audit — Session 97 (2026-03-09)

**Auditor**: Claude Opus 4.6 — Full codebase read, no code changes
**Test Suite**: 2,432 passed, 0 failed, 0 skipped
**Total Lines**: 151,374 across 110+ Python files in functions/lib/
**Firestore**: Not accessible from this machine (no sa-key.json)

---

## 1. Component Inventory

### A. Core Pipeline (WORKING — called from main.py)

| File | Lines | Status | Role |
|------|-------|--------|------|
| `main.py` | 2,768 | WORKING | Entry point: 28 Cloud Functions, email routing, schedulers |
| `email_triage.py` | 298 | WORKING | 3-layer email classification: SKIP/CASUAL/CONSULTATION/LIVE_SHIPMENT |
| `casual_handler.py` | 169 | WORKING | Non-customs casual reply handler |
| `email_intent.py` | 2,811 | WORKING | 6 intent types + 7 handlers + composition pipeline |
| `consultation_handler.py` | 1,332 | WORKING | Main orchestrator: smart_classify → broker_engine → composition pipeline |
| `broker_engine.py` | 2,107 | WORKING | Deterministic 9-phase classification (1 AI call, rest Python) |
| `classification_agents.py` | 3,770 | WORKING | 6-agent pipeline + email builder + feature flags |
| `tool_calling_engine.py` | 1,216 | WORKING | 15-round tool loop, pre-enrichment, cross-reference |
| `tool_executors.py` | 3,255 | WORKING | 35 tool handlers + domain allowlist + caching |
| `tool_definitions.py` | 967 | WORKING | Tool schemas (Claude + Gemini formats) + system prompt |
| `rcb_helpers.py` | 1,541 | WORKING | Graph API, email quality gate, security logging |
| `tracker.py` | 2,712 | WORKING | Deal tracking, TaskYam, email triggers |
| `tracker_email.py` | 876 | WORKING | Tracker status email HTML builder |
| `pupil.py` | 2,765 | WORKING | Passive CC learning, gap detection, review cases |
| `brain_commander.py` | 968 | WORKING | doron@ brain commands, auto-improve |
| `overnight_brain.py` | 2,202 | WORKING | 12-stream nightly enrichment, $3.50 cap |
| `self_learning.py` | 1,836 | WORKING | 5-level memory, learned_classifications |
| `intelligence.py` | 2,007 | WORKING | pre_classify Firestore search (7 strategies) |
| `rcb_id.py` | 68 | WORKING | Tracking code generator |

### B. Classification Engine Components (WORKING — called from broker/agents)

| File | Lines | Status | Role |
|------|-------|--------|------|
| `smart_classify.py` | 1,027 | WORKING | Vocab + synonym expansion + tariff tree search |
| `elimination_engine.py` | 2,413 | WORKING | 8-level GIR elimination (Section→GIR 3→AI→Devil's Advocate) |
| `verification_engine.py` | 743 | WORKING | Bilingual cross-check + proactive flagging |
| `cross_checker.py` | 480 | WORKING | 3-way AI cross-check (Gemini Pro + Flash + GPT-4o-mini) |
| `compliance_auditor.py` | 1,377 | WORKING | Official document citations in emails |
| `smart_questions.py` | 569 | WORKING | Post-classification clarification generator |

### C. Composition Layer (WORKING — called from consultation/email_intent)

| File | Lines | Status | Role |
|------|-------|--------|------|
| `direction_router.py` | 234 | WORKING | Import/export/transit detection |
| `case_reasoning.py` | 510 | WORKING | Legal category detection (תושב חוזר, עולה, etc.) |
| `evidence_types.py` | 595 | WORKING | EvidenceBundle from ContextPackage |
| `straitjacket_prompt.py` | 544 | WORKING | Forces AI to cite only fetched evidence |
| `reply_composer.py` | 1,196 | WORKING | 12 HTML blocks + 4 template orchestrators |
| `context_engine.py` | 1,722 | WORKING | SIF: 34+ tool routing, entity extraction |

### D. Data Modules (WORKING — in-memory Python constants)

| File | Lines | Status | Role |
|------|-------|--------|------|
| `_unified_index.py` | 38,584 | WORKING | 25,967 words, 11,565 HS codes (auto-generated) |
| `_unified_search.py` | 432 | WORKING | search_word, search_phrase, find_tariff_codes |
| `_customs_vocabulary.py` | 16,901 | WORKING | 16,887 term→chapter mappings |
| `_ordinance_data.py` | 1,828 | WORKING | 311 articles, full Hebrew text |
| `_ordinance_topic_map.py` | 783 | ORPHANED | 21 topics — only referenced in tests |
| `customs_law.py` | 787 | WORKING | GIR rules, methodology, format_legal_context_for_prompt |
| `chapter_expertise.py` | 380 | WORKING | 22 tariff sections with notes/traps |
| `_chapter98_data.py` | 293 | WORKING | Chapter 98/99 discount codes |
| `_fta_all_countries.py` | 2,324 | WORKING | 16 countries, 146 docs, 15.5M chars |
| `_fta_all_countries_GENERATED.py` | 2,324 | DEAD | Duplicate of _fta_all_countries.py |
| `_fta_all_countries_BACKUP.py` | 1,173 | DEAD | Old backup |
| `_customs_agents_law.py` | 550 | WORKING | 36 articles, 8 chapters from Nevo |
| `_document_registry.py` | 1,522 | WORKING | 52+ docs cataloged |
| `_discount_codes_data.py` | 2,003 | WORKING | Discount code mappings |
| `_eu_reform_data.py` | 285 | WORKING | EU reform structured data |
| `_framework_order_data.py` | 199 | WORKING | Framework order documents |
| `_procedures_data.py` | 111 | WORKING | 7 customs procedures (119K chars) |
| `_approved_exporter_GENERATED.py` | 19 | DEAD | Zero imports anywhere |

### E. Supporting Infrastructure (WORKING)

| File | Lines | Status | Role |
|------|-------|--------|------|
| `librarian_index.py` | 1,342 | WORKING | 154 collections registered |
| `librarian.py` | 1,177 | WORKING | Firestore search, HS format |
| `librarian_researcher.py` | 1,181 | WORKING | Deep research queries |
| `librarian_tags.py` | 1,714 | WORKING | Tag extraction and matching |
| `knowledge_query.py` | 1,056 | WORKING | Direct email Q&A handler |
| `nightly_learn.py` | 200 | WORKING | Overnight index builder |
| `cost_tracker.py` | 207 | WORKING | Budget tracking ($3.50 cap) |
| `ttl_cleanup.py` | 117 | WORKING | TTL-based Firestore cleanup |
| `overnight_audit.py` | 527 | WORKING | 02:00 diagnostic scan |
| `pc_agent.py` | 623 | WORKING | Task orchestration |
| `pc_agent_runner.py` | 546 | WORKING | Cloud-side task executor |
| `rcb_inspector.py` | 1,743 | WORKING | System inspection reports |
| `rcb_self_test.py` | 660 | WORKING | Loopback self-test |
| `schedule_il_ports.py` | 1,042 | WORKING | 6-source port schedule aggregation |
| `port_intelligence.py` | 2,732 | WORKING | I1-I4: deal-schedule links, alerts, digest |
| `air_cargo_tracker.py` | 554 | WORKING | Air cargo tracking |
| `ocean_tracker.py` | 1,606 | WORKING | 7-provider ocean tracking |
| `route_eta.py` | 286 | WORKING | Driving ETA calculator |
| `shipping_knowledge.py` | 1,230 | WORKING | 9 carrier profiles, BIC validation |
| `extraction_adapter.py` | 360 | WORKING | PDF/image extraction routing |
| `pdf_creator.py` | 202 | WORKING | PDF generation |
| `report_builder.py` | 1,133 | WORKING | HTML report rendering |
| `language_tools.py` | 2,071 | WORKING | Hebrew/English utilities |
| `intelligence_gate.py` | 808 | WORKING | Routing intelligence |
| `invoice_validator.py` | 381 | WORKING | Invoice validation |
| `uk_tariff_integration.py` | 445 | WORKING | UK tariff API |
| `gemini_classifier.py` | 67 | WORKING | AI call routing |
| `tariff_tree.py` | 552 | WORKING | XML tariff tree (backup search) |
| `storage_manager.py` | 163 | WORKING | Cloud Storage |

### F. ORPHANED Components (built but not wired into any live path)

| File | Lines | Status | Issue |
|------|-------|--------|-------|
| `identity_graph.py` | 973 | ORPHANED | Built Session 46, never wired into tracker/main |
| `_ordinance_topic_map.py` | 783 | ORPHANED | Only referenced from test file |
| `self_enrichment.py` | 205 | ORPHANED | Superseded by overnight_brain Stream 10 |
| `enrichment_agent.py` | 731 | ORPHANED | `enrich_knowledge()` scheduler exists but checks disabled |
| `verification_loop.py` | 461 | HALF-WIRED | Imported by classification_agents + tool_calling_engine but unclear if called |

### G. DEAD Code (zero imports, never called)

| File | Lines | Status |
|------|-------|--------|
| `_approved_exporter_GENERATED.py` | 19 | DEAD |
| `_fta_all_countries_GENERATED.py` | 2,324 | DEAD duplicate |
| `_fta_all_countries_BACKUP.py` | 1,173 | DEAD backup |
| `product_classifier.py` | 714 | DEAD |
| `rcb_email_processor.py` | 414 | DEAD |
| `rcb_orchestrator.py` | 408 | DEAD |
| `read_document.py` | 118 | DEAD |
| `memory_config.py` | 36 | DEAD |
| `extraction_quality_logger.py` | 84 | DEAD |

### H. Backup Files Still in Repo (10 files)

```
functions/lib/classification_agents.py.backup_session22
functions/main.py.backup
functions/main.py.backup_20260205_150741
functions/main.py.backup_session10
functions/main.py.backup_session6
functions/main.py.bak
functions/main.py.bak2_20260216
functions/main.py.bak_20260216
functions/requirements.txt.backup
functions/requirements.txt.bak
```

### I. Root-Level One-Off Scripts (65 files)

65 Python scripts in `functions/` root that are NOT deployed Cloud Functions. Mix of:
- **Seeders** (10): seed_*.py — one-time Firestore population scripts
- **Parsers** (6): parse_*.py — one-time data extraction
- **Fixers** (8): fix_*.py, patch_*.py — one-time bug fixes
- **Tests** (8): test_*.py — live integration tests (not in tests/)
- **Utilities** (33): build_*, cleanup_*, add_*, etc.

These are ALL dead weight in the deployed Cloud Functions package.

---

## 2. Call Graph — Consultation Email

```
main.py:rcb_check_email() [every 2 min]
  → _rcb_check_email_inner()
    → Graph API: fetch emails (2-day lookback)
    → FOR EACH email:
      → SKIP: self (rcb@), cc@, auto-replies, [RCB-SELFTEST]
      → Block A2: [DECL] declarations

      → IF CC path (not TO rcb@):
        → pupil.pupil_process_email()          [silent learn]
        → tracker.tracker_process_email()       [observe shipping]
        → _screen_deal_parties()                [sanctions]
        → schedule detection                    [vessel schedules]
        → Gap 2: _run_gap2_silent_classification() [if invoice+shipping]
        → DONE (no reply)

      → IF Direct path (TO rcb@):
        → Reply target detection (sole TO? team in CC?)
        → brain_commander check                 [doron@ only]
        → Thread context lookup                 [RCB tracking code]
        → email_triage.triage_email()

          → SKIP → mark read
          → CASUAL → casual_handler → reply

          → LIVE_SHIPMENT:
            → consultation_handler.handle_consultation(template_type="live_shipment")
              [SEE CONSULTATION FLOW BELOW]

          → CONSULTATION:
            → Tariff subtree intercept?
              → YES: _handle_tariff_subtree() → reply, DONE
              → NO: consultation_handler.handle_consultation()
                [SEE CONSULTATION FLOW BELOW]

          → Falls through to:
        → email_intent.process_email_intent()
          → STATUS_REQUEST → tracker lookup → reply
          → CUSTOMS_QUESTION → tool search → AI compose → reply
          → KNOWLEDGE_QUERY → tool search → AI compose → reply
          → INSTRUCTION → route to action

          → Falls through to:
        → knowledge_query.detect_knowledge_query()
          → If question → answer → reply

          → Falls through to:
        → Shipping-only routing (BL/AWB, no invoice)
          → tracker only, skip classification

          → Falls through to:
        → External rate limiting (5/hour)
        → Classification pipeline:
          → classification_agents.process_and_send_report()
            → run_full_classification() [6 agents]
            → build_classification_email()
            → send reply
```

### Consultation Handler Internal Flow

```
consultation_handler.handle_consultation()
  │
  ├─ Sub-intent check (ADMIN/CORRECTION/STATUS → delegate)
  │
  ├─ smart_classify.classify_product()              ← ALWAYS RUNS
  │   ├─ Step 0: _customs_vocabulary lookup          [16,887 terms → chapters]
  │   ├─ Step 1: expand_query()                      [synonym expansion]
  │   ├─ Step 2a: tariff_tree.search_tree()          [XML hierarchy]
  │   ├─ Step 2b: _unified_search.find_tariff_codes() [flat index]
  │   ├─ Step 3: chapter_notes cross-check           [exclusions]
  │   ├─ Step 4: GIR Rule 1 scoring                  [specificity]
  │   └─ Step 4b: vocab chapter filter               [restrict candidates]
  │   → Returns: hs_candidates, confidence, vocab_chapters
  │
  ├─ broker_engine.process_case()                    ← ALWAYS RUNS
  │   ├─ Phase 0: analyze_case()                     [case_reasoning.py]
  │   ├─ Phase 0b: _extract_and_fetch_urls()         [product specs from URLs]
  │   ├─ Phase 1: _identify_items_with_ai()          ← SINGLE AI CALL
  │   ├─ Phase 2: _check_spare_part()
  │   ├─ Phases 3-6: classify_single_item()
  │   │   ├─ _smart_tariff_search()                  [unified index FIRST]
  │   │   │   ├─ _unified_search.find_tariff_codes()
  │   │   │   ├─ _filter_by_vocab_chapters()
  │   │   │   └─ intelligence.pre_classify()          [Firestore FALLBACK]
  │   │   ├─ elimination_engine.eliminate()            ← CONNECTED: YES
  │   │   └─ _drill_to_subheading()                   [heading → 10-digit]
  │   ├─ Phase 7: _apply_chapter98()                  [_chapter98_data.py]
  │   ├─ Phase 8: FIO/FEO/Ordinance/FTA lookups
  │   │   ├─ _ordinance_data (311 articles)           ← CONNECTED: YES
  │   │   ├─ _fta_all_countries (16 countries)        ← CONNECTED: YES
  │   │   └─ free_import_order Firestore              ← CONNECTED: YES
  │   └─ Phase 9: verify_and_loop()
  │   → Returns: structured dict with HS codes, FIO, FTA, discount, etc.
  │
  ├─ _run_composition_pipeline()
  │   ├─ context_engine.prepare_context_package()     ← CONNECTED: YES
  │   │   ├─ Entity extraction
  │   │   ├─ _search_ordinance() [in-memory]          ← CONNECTED: YES
  │   │   ├─ _search_framework_order() [in-memory]    ← CONNECTED: YES
  │   │   └─ _plan_tool_calls() → _execute_tool_plan() [34+ tools]
  │   ├─ Level 1: Gemini Flash (cheapest)
  │   ├─ Level 2: ChatGPT (if Gemini fails)
  │   └─ Level 3: Claude (if they disagree)
  │
  └─ reply_composer.compose_*()                       ← HTML RENDERING
      └─ _send_consultation_reply() via Graph API
```

---

## 3. Connected vs Orphaned Components

### CONNECTED to Consultation Path
| Component | How |
|-----------|-----|
| smart_classify | Always runs first in handle_consultation |
| broker_engine | Always runs, gets vocab_chapters from smart_classify |
| _unified_search / _unified_index | Primary search in broker_engine._smart_tariff_search |
| _customs_vocabulary | Step 0 of smart_classify |
| elimination_engine | Called within classify_single_item |
| _ordinance_data | Phase 8 of broker_engine |
| _fta_all_countries | Phase 8 FTA lookup |
| _chapter98_data | Phase 7 discount codes |
| customs_law | Prepended to AI prompts in both tool_definitions and classification_agents |
| chapter_expertise | Imported by customs_law |
| context_engine | Runs in composition pipeline |
| direction_router | Runs early in composition pipeline |
| case_reasoning | Phase 0 of broker_engine |
| evidence_types | Composition pipeline |
| straitjacket_prompt | Composition pipeline |
| reply_composer | Final HTML rendering |

### NEVER CALLED in Consultation Path
| Component | Notes |
|-----------|-------|
| identity_graph.py | Built Session 46, designed for outcome tracking. NO live wiring. |
| _ordinance_topic_map.py | SIF Layer 0 — exists but never imported by context_engine |
| pupil.py | Called AFTER consultation (for learning), not DURING |
| knowledge_query.py | Separate handler for non-commercial questions |
| tracker.py | Separate pipeline for shipment tracking |
| overnight_brain.py | Nightly enrichment only |
| compliance_auditor.py | Only in classification_agents, not consultation |
| verification_engine.py | Only in classification_agents pipeline |
| cross_checker.py | Only in classification_agents pipeline |
| self_enrichment.py | Orphaned completely |

### Components in BOTH Paths (consultation AND classification)
| Component | Consultation Path | Classification Path |
|-----------|-------------------|---------------------|
| tool_executors | Via context_engine | Via tool_calling_engine |
| elimination_engine | Via broker_engine | Via classification_agents |
| intelligence.py | Fallback in broker_engine | Direct in pre_classify |

---

## 4. Critical Gaps

### Gap A: Identity Graph Never Wired (973 lines wasted)
- **Built**: Session 46 — `link_email_to_deal()`, `register_deal_from_tracker()`, `merge_deals()`
- **Designed for**: Matching customs declarations back to original classifications
- **Current state**: Zero imports from main.py, tracker.py, or any live module
- **Impact**: No indirect feedback loop. When a declaration comes back, the system can't match it to the original classification to learn from the outcome.

### Gap B: Ordinance Topic Map Orphaned (783 lines wasted)
- **Built**: Session 93c — `_ordinance_topic_map.py` with 21 topics for SIF Layer 0
- **Designed for**: Fast topic-based routing before full search
- **Current state**: Only imported by test file. context_engine.py does NOT import it.

### Gap C: Two Parallel Classification Paths with No Shared Result
- **Path 1**: consultation_handler → broker_engine → deterministic (1 AI call)
- **Path 2**: classification_agents → run_full_classification → 6 agents (expensive)
- **Problem**: broker_engine returns structured data but if composition pipeline takes over, it may re-classify via context_engine + AI ladder, potentially producing different results. No merge/reconciliation.

### Gap D: Compliance Auditor Not in Consultation Path
- `compliance_auditor.py` (1,377 lines) adds official document citations
- Only wired into `classification_agents.py:run_full_classification()`
- Consultation replies via reply_composer do NOT include compliance citations

### Gap E: 65 Root-Level Scripts Deployed to Cloud Functions
- All 65 scripts in `functions/` root get deployed in the Cloud Functions package
- Adds ~15,000+ lines of dead code to every deploy
- Should be moved to `scripts/` or excluded from deployment

### Gap F: 10 Backup Files Still in Repo
- 8 main.py backups, 1 classification_agents backup, 2 requirements backups
- Session 34-Audit deleted 23 backup files but these 10 remain

### Gap G: Feature Flag Confusion
Multiple feature flags control overlapping functionality:
- `ELIMINATION_ENABLED` — controls elimination in classification_agents
- `USE_SMART_CLASSIFY` — controls smart_classify in consultation_handler
- `USE_TARIFF_TREE` — controls tariff tree usage
- `VERIFICATION_ENGINE_ENABLED` — verification in classification_agents
- `COMPLIANCE_AUDITOR_ENABLED` — compliance in classification_agents
- `CROSS_CHECK_ENABLED` — cross-check in classification_agents
- `PRE_CLASSIFY_BYPASS_ENABLED` — skip AI when memory hit

All are `True`. There's no documentation of what happens when any is `False`.

### Gap H: Dead Code in lib/ (~5,300 lines)
| File | Lines | Status |
|------|-------|--------|
| `_fta_all_countries_GENERATED.py` | 2,324 | Exact duplicate |
| `_fta_all_countries_BACKUP.py` | 1,173 | Old version |
| `product_classifier.py` | 714 | Never imported |
| `rcb_email_processor.py` | 414 | Never imported |
| `rcb_orchestrator.py` | 408 | Never imported |
| `read_document.py` | 118 | Never imported |
| `extraction_quality_logger.py` | 84 | Never imported |
| `memory_config.py` | 36 | Never imported |
| `_approved_exporter_GENERATED.py` | 19 | Never imported |
| **Total** | **~5,300** | |

---

## 5. Data Layer Status

### Firestore Collections (cannot verify — no sa-key.json on this machine)
Based on code analysis, 154 collections registered in `librarian_index.py`.

**Critical collections (should contain data)**:
| Collection | Expected Docs | Populated By |
|-----------|---------------|-------------|
| `tariff` | 11,753 | tariff_full_text.txt upload |
| `chapter_notes` | 99 | parse_chapter_notes_c2.py |
| `classification_directives` | 218 | enrich_directives_c6.py |
| `free_import_order` | 6,121 | seed_free_import_order_c3.py |
| `free_export_order` | 979 | seed_free_export_order_c4.py |
| `framework_order` | 85 | seed_framework_order_c5.py |
| `legal_knowledge` | 19+ | seed_legal_knowledge_c8.py |
| `tariff_structure` | 137 | seed_tariff_structure.py |
| `learned_classifications` | Unknown | self_learning.py (runtime) |
| `brain_index` | 5,001+ | overnight_brain.py |
| `keyword_index` | 8,120+ | nightly_learn.py |
| `tracker_deals` | Unknown | tracker.py (runtime) |

**Potentially empty collections**:
| Collection | Risk |
|-----------|------|
| `deal_identity_graph` | EMPTY — identity_graph.py never wired |
| `regression_alerts` | Likely empty — Stream 12 only |
| `elimination_log` | Unknown — only written by live elimination runs |

### In-Memory Data (Python constants — always available)
| Module | Content | Size |
|--------|---------|------|
| `_unified_index.py` | 25,967 words → 11,565 HS codes | 38,584 lines |
| `_customs_vocabulary.py` | 16,887 term→chapter mappings | 16,901 lines |
| `_ordinance_data.py` | 311 articles, full Hebrew text | 1,828 lines |
| `_fta_all_countries.py` | 16 countries, 146 docs | 2,324 lines |
| `_customs_agents_law.py` | 36 articles, 8 chapters | 550 lines |
| `_chapter98_data.py` | Discount codes | 293 lines |
| `_discount_codes_data.py` | Discount mappings | 2,003 lines |
| `_procedures_data.py` | 7 procedures | 111 lines |
| `customs_law.py` | GIR 1-6, methodology | 787 lines |
| `chapter_expertise.py` | 22 sections | 380 lines |

### Pupil Agent Learning
- `pupil.py` is called from main.py for both CC and direct paths
- Learns AFTER email processing (not during)
- Stores in: `learned_classifications`, `learned_patterns`, `learned_contacts`
- Cannot verify actual stored data without Firestore access

### XML Documents
- 231 XML documents from `fullCustomsBookData.zip` (214 MB)
- 15 extracted to `C:\Users\doron\tariff_extract\`
- `search_xml_documents` (tool #34) provides access via `_document_registry.py`
- CustomsItemDetailsHistory.xml (42.9 MB) — NOT YET ANALYZED

---

## 6. Priority Fix List

### CRITICAL (fix first — direct impact on functionality)

1. **Wire identity_graph.py into tracker.py** (Gap A)
   - Call `register_deal_from_tracker()` when deals are created
   - Call `link_email_to_deal()` in tracker_process_email
   - Enables outcome-based learning (declaration → classification feedback loop)
   - Impact: 973 lines of built code becomes functional

2. **Reconcile broker_engine vs classification_agents paths** (Gap C)
   - When broker_engine completes with HIGH confidence, its result should be authoritative
   - composition pipeline should PRESENT broker results, not RE-CLASSIFY
   - Currently: broker result may be overwritten by AI ladder in composition

### HIGH (fix soon — quality/efficiency)

3. **Delete 5,300 lines of dead code in lib/** (Gap H)
   - Remove: _fta_all_countries_GENERATED.py, _fta_all_countries_BACKUP.py, product_classifier.py, rcb_email_processor.py, rcb_orchestrator.py, read_document.py, extraction_quality_logger.py, memory_config.py, _approved_exporter_GENERATED.py
   - Reduces confusion, deploy size, and accidental use

4. **Delete 10 backup files** (Gap F)
   - main.py.backup*, main.py.bak*, classification_agents.py.backup_session22, requirements.txt.backup/bak

5. **Move 65 root-level scripts out of functions/** (Gap E)
   - Move to `scripts/` or `tools/` directory
   - Exclude from Cloud Functions deployment
   - Currently deployed to every Cloud Function despite being one-time utilities

6. **Wire _ordinance_topic_map.py into context_engine.py** (Gap B)
   - 21 topics mapped but never used
   - Would speed up SIF by routing to correct ordinance topics before full search

### MEDIUM (fix when convenient — improvement)

7. **Add compliance_auditor to consultation path** (Gap D)
   - reply_composer should call compliance_auditor for official citations
   - Currently only in classification_agents pipeline

8. **Document feature flags** (Gap G)
   - Create a feature flags reference document
   - Test what happens when each flag is False
   - Remove flags that are always True and never toggled

9. **Clean up self_enrichment.py** (205 lines)
   - Superseded by overnight_brain Stream 10
   - `enrichment_agent.py` scheduler has checks disabled (dead scheduler)

10. **Firestore access audit** (requires sa-key.json)
    - Verify all critical collections have data
    - Check deal_identity_graph is truly empty
    - Count learned_classifications to assess learning effectiveness

---

## Appendix: Test Suite Summary

```
2,432 tests passed, 0 failed, 0 skipped (32.78s)
```

Test files in `functions/tests/`:
- test_broker_engine.py — broker phases
- test_case_reasoning.py — legal category detection
- test_classification_agents.py — 6-agent pipeline
- test_compliance_auditor.py — citations
- test_consultation_handler.py — consultation flow
- test_context_engine.py — SIF searches
- test_customs_agents_law.py — 36 articles
- test_customs_law.py — methodology + GIR
- test_direction_router.py — import/export
- test_email_intent.py — intent detection
- test_email_quality_gate.py — quality rules
- test_email_rules.py — reply rules
- test_email_triage.py — triage categories
- test_evidence_types.py — evidence bundle
- test_identity_graph.py — identity linking
- test_librarian_index.py — collection registry
- test_overnight_brain.py — nightly enrichment
- test_port_intelligence.py — port alerts
- test_reply_composer.py — HTML rendering
- test_route_eta.py — driving ETA
- test_smart_classify.py — vocabulary/synonym
- test_smart_questions.py — clarification
- test_straitjacket_prompt.py — prompt constraints
- test_tool_calling.py — 35 tools
- test_unified_search.py — flat index search
- test_verification_engine.py — bilingual check

---

## Appendix: Cloud Functions Schedule (28 functions)

| Time (IL) | Function | Purpose |
|-----------|----------|---------|
| every 2 min | rcb_check_email | Email processing |
| every 5 min | monitor_agent | Health check (disabled actions) |
| every 30 min | rcb_tracker_poll | Deal updates + Gap 2 reports + I3 alerts |
| every 30 min | rcb_pc_agent_runner | PC agent task executor |
| every 1 hour | enrich_knowledge | Knowledge enrichment (checks disabled) |
| every 1 hour | rcb_health_check | System health |
| every 6 hours | rcb_retry_failed | Retry failed classifications |
| every 6 hours | rcb_pupil_learn | Batch learning |
| every 12 hours | rcb_port_schedule | Port schedule aggregation |
| every 24 hours | rcb_cleanup_old_processed | Old processed cleanup |
| 02:00 | rcb_nightly_learn | Index building |
| 02:00 | rcb_overnight_audit | Diagnostic scan |
| 02:00 | rcb_daily_backup | 4 collections → GCS |
| 03:30 | rcb_ttl_cleanup | TTL-based cleanup (backup-guarded) |
| 04:00 | rcb_download_directives | Shaarolami directives |
| 07:00 | rcb_daily_digest | Morning port digest |
| 14:00 | rcb_afternoon_digest | Afternoon port digest |
| 15:00 | rcb_inspector_daily | Inspection report |
| 20:00 | rcb_overnight_brain | 12-stream enrichment ($3.50 cap) |

HTTP endpoints: api(), rcb_api(), test_pdf_ocr(), test_pdf_report(), rcb_self_test(), rcb_inspector(), monitor_agent_manual()

Firestore triggers: on_new_classification(), on_classification_correction()
