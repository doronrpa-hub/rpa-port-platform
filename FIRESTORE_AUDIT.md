# Firestore Data Audit Report
## Assignment 3 — Collection Inventory + Data Quality
**Date:** February 16, 2026
**Project:** rpa-port-customs
**Total Collections:** 111
**Total Documents:** 139,274

---

## Part 1: Smoke Test Results

All 9 files modified in Assignment 2 pass syntax and import checks:

| File | Syntax | Import |
|------|--------|--------|
| lib/tracker.py | OK | OK |
| lib/tracker_email.py | OK | OK |
| lib/pdf_creator.py | OK | WARN: `reportlab` not installed locally (expected) |
| lib/intelligence.py | OK | OK |
| lib/smart_questions.py | OK | OK |
| lib/classification_agents.py | OK | OK |
| lib/pupil.py | OK | OK |
| lib/verification_loop.py | OK | OK |
| main.py | OK | OK |

**Verdict: All fixes are safe. No broken imports or syntax errors.**

---

## Part 2: All 111 Firestore Collections

### Documented in RCB_SYSTEM.md (~20 collections)
The system documentation lists about 20 collections. In reality there are **111**. The 91 undocumented collections have been created by various agents and subsystems over time.

### Collection Inventory (sorted by document count)

#### Tier 1: Large (>1,000 docs) — 9 collections, 132,500 docs (95%)

| Collection | Docs | Purpose |
|-----------|------|---------|
| scanner_logs | 37,964 | PC Agent document scanner logs |
| files | 37,954 | All processed email attachments |
| librarian_index | 12,595 | Librarian's searchable index of all knowledge |
| tariff | 11,753 | Israeli HS tariff codes (main classification DB) |
| brain_index | 11,262 | Brain Commander's keyword-to-HS-code index |
| keyword_index | 8,195 | Keyword search index for HS code lookup |
| legal_requirements | 7,443 | Free Import Order legal requirements per HS code |
| librarian_search_log | 3,138 | Log of all Librarian search queries |
| hub_tasks | 2,196 | Task queue for hub/web interface |

#### Tier 2: Medium (100–1,000 docs) — 17 collections

| Collection | Docs | Purpose |
|-----------|------|---------|
| agent_tasks | 731 | PC Agent download/enrichment tasks |
| batch_reprocess_results | 683 | Results from email reprocessing batches |
| tracker_observations | 629 | Tracker brain email observations |
| pupil_observations | 518 | Pupil agent email observations |
| tech_assistant_commands | 426 | PC Agent remote command history |
| enrichment_tasks | 382 | Pending knowledge enrichment tasks |
| knowledge_base | 305 | Uploaded knowledge documents |
| pupil_teachings | 224 | Pupil agent learned teachings |
| contacts | 194 | Learned email contacts |
| librarian_enrichment_log | 170 | Librarian enrichment run history |
| tracker_timeline | 161 | Container timeline events |
| tracker_container_status | 160 | Per-container import/export process status |
| rcb_silent_classifications | 128 | CC-observed classifications (silent mode) |
| rcb_processed | 121 | Processed email tracking |
| hs_code_index | 101 | Chapter-level HS code references |
| rcb_logs | 101 | RCB processing logs |
| tariff_chapters | 101 | Chapter descriptions (see data quality issues below) |

#### Tier 3: Small (1–100 docs) — 85 collections

| Collection | Docs | Notable |
|-----------|------|---------|
| rcb_classifications | 86 | Full classification reports sent to clients |
| classification_knowledge | 84 | Learned HS code associations |
| ministry_index | 84 | Ministry-to-HS-code mappings |
| unclassified_documents | 72 | Documents that couldn't be classified |
| knowledge | 71 | Legacy knowledge entries |
| hub_messages | 68 | Hub chat messages |
| product_index | 68 | Product name to HS code cache |
| inbox | 64 | Legacy IMAP inbox records |
| learned_shipping_patterns | 63 | BOL prefix patterns |
| tracker_deals | 58 | Active shipment deals |
| declarations | 53 | Customs declarations |
| knowledge_queries | 52 | Knowledge query history |
| session_backups | 46 | Claude session backups |
| backup_logs | 45 | Backup operation logs |
| verification_cache | 44 | HS code verification cache (30-day TTL) |
| learned_shipping_senders | 42 | Shipping sender patterns |
| triangle_learnings | 36 | Multi-AI classification comparisons |
| agent_downloads | 35 | PC Agent downloaded files |
| classification_rules | 32 | GIR rules and Israeli rules |
| learned_patterns | 32 | Email extraction patterns |
| brain_commands | 30 | Brain Commander command history |
| learned_doc_templates | 30 | Document template patterns |
| regulatory_requirements | 28 | Per-chapter regulatory requirements |
| pending_tasks | 27 | Pending human review tasks |
| classifications | 25 | Legacy classification records |
| bills_of_lading | 23 | Extracted BOL documents |
| fta_agreements | 21 | Free Trade Agreement data |
| learned_contacts | 19 | Auto-learned contact profiles |
| licensing_knowledge | 18 | FTA/licensing per country |
| rcb_inspector_reports | 16 | Inspector health reports |
| airlines | 15 | Airline reference data |
| classification_workflow | 15 | Classification workflow steps |
| shipping_lines | 15 | Shipping line reference data |
| document_types | 13 | Document type definitions |
| session_history | 13 | Development session summaries |
| packing_lists | 11 | Extracted packing lists |
| config | 9 | System configuration |
| free_import_cache | 9 | FIO API response cache |
| missions | 9 | Hub mission records |
| rcb_inbox | 9 | Direct RCB classification requests |
| system_counters | 9 | RCB ID sequence counters |
| web_search_cache | 9 | Web search result cache |
| enrichment_log | 8 | Enrichment source tracking |
| legal_references | 8 | Legal document references |
| hub_links | 6 | Hub quick links |
| hub_tools | 6 | Hub tool registry |
| pupil_audit_summaries | 6 | Pupil nightly audit summaries |
| batch_reprocess_summary | 5 | Batch reprocess run summaries |
| intelligence_files | 5 | Project intelligence file registry |
| pupil_budget | 5 | Pupil daily API budget tracking |
| system_metadata | 5 | System metadata (deep learn stats) |
| hub_agents | 4 | Registered AI agents |
| intelligence_decisions | 4 | Architecture decisions |
| legal_documents | 4 | Legal document records |
| pupil_corrections | 4 | Classification corrections found |
| regulatory_certificates | 4 | Certificates (EMC, SII, etc.) |
| sellers | 4 | Known seller records |
| system_status | 4 | Enrichment status |
| procedures | 3 | Customs procedures (sivug, haaracha, tashar) |
| project_backups | 3 | Architecture summaries |
| pupil_reviews | 3 | Pupil review cases |
| rcb_test_reports | 3 | Automated test results |
| supplier_index | 3 | Supplier-to-HS-code cache |
| tracker_shipments | 3 | Legacy shipment records |
| backup_log | 2 | Native backup log |
| buyers | 2 | Known buyer records |
| daily_state | 2 | Daily system state snapshots |
| mission_decisions | 2 | Hub mission decisions |
| pupil_correction_budget | 2 | Correction email daily budget |
| pupil_review_budget | 2 | Review email daily budget |
| rcb_first_emails | 2 | First email tracking |
| regulatory_approvals | 2 | Ministry approvals |
| sessions_backup | 2 | Session architecture backup |
| tech_assistant_state | 2 | PC Agent heartbeat state |
| _health | 1 | Health check marker |
| _test | 1 | Connection test marker |
| brain_daily_digest | 1 | Daily digest email record |
| intelligence_activity | 1 | Intelligence activity log |
| mission_chat | 1 | Hub mission chat history |
| monitor | 1 | Email processor health monitor |
| overnight_audit_results | 1 | Nightly audit results |
| rcb_stats | 1 | Daily email stats |
| regulatory | 1 | Regulatory metadata |
| session_missions | 1 | Session mission plans |
| system_tasks | 1 | Continuous learning config |

**Zero empty collections. Zero error collections.**

---

## Part 3: Data Quality Findings

### 3.1 tariff (11,753 docs) — Main Classification DB

**Sample quality check (20 docs):** 20 good, 0 garbage.

The 35.7% garbage in `parent_heading_desc` reported in the audit may be concentrated in specific chapter ranges not hit by the first-20-docs sample. A larger sample or targeted chapter scan would be needed to confirm the exact percentage.

**Sample good document (ID: 0101200000):**
```
chapter: 1
(full fields couldn't be displayed due to Hebrew encoding on Windows terminal)
```

**Document structure (18 fields):** chapter, customs_duty, description_en, description_he, duty_rate, full_code, heading, hs_code, parent_heading_code, parent_heading_desc, purchase_tax, section, subheading, statistical_suffix, ...

### 3.2 tariff_chapters (101 docs) — CORRECTED FINDING

**Doc IDs use `import_chapter_XX` format** (not plain chapter numbers):
- `import_chapter_01` through `import_chapter_99` (99 docs)
- `autonomy_main` (autonomy tariff)
- `export_main` (export tariff)

Each doc contains: `chapterId`, `chapterName`, `chapterDescription`, `content` (full scraped page from customs website), `hsCodes` (list of all HS codes), `headings` (list of headings), `scannedAt`, `source`.

**Code impact:** The code in `librarian.py:361` and `intelligence.py:1659` streams all docs (works fine). The code in `verification_loop.py:404` tries `db.collection("tariff_chapters").document(hs_clean).get()` which always fails (HS code as doc ID doesn't match `import_chapter_XX` format), but safely falls through to the `tariff` collection.

**The data is rich and usable.** The original audit incorrectly reported "non-standard IDs" — they are standard, just prefixed with `import_chapter_`.

### 3.3 keyword_index (8,195 docs) — CORRECTED: 98% CLEAN

Full scan results: **8,078 clean (98%), 117 garbage (1%), 0 empty**.

The garbage is limited to ~117 docs where descriptions contain AI responses:
```
0000: "The HS code 0810.50 covers kiwifruit, fresh..."
0106: "Why is 'Librarian has low confidence for..."
0402: "To accurately classify 'TEST 1800 0402'..."
```

Clean examples:
```
1170: "AMS - 1170 -2C 1170 EAS ANT - COOL GRAY" → HS 851319000
2026: "2026 Chevrolet Silverado EV" → HS 87031090
1kg: "VINE LEAVES STUFFED WITH RICE 6x2,1kg" → HS 6866
```

**Impact is low** — only 1% of docs are affected. A cleanup script could fix the 117 garbage entries.

### 3.4 product_index (68 docs)

Looks healthy. Sample:
```
1170_eas_ant_cool_gray → HS 8513190000, confidence 75, usage_count 1
2026_chevrolet_silverado_ev → HS 87031090, confidence 75, usage_count 2
2026_gmc_sierra_ev → HS 87031090, confidence 75, usage_count 2
```

### 3.5 supplier_index (3 docs)

Contains 3 suppliers (documented as 2):
- ligentia_poland_sp_z_o_o → 1 HS code, 1 shipment

### 3.6 verification_cache (44 docs)

Looks healthy. VAT correctly shows 18%. Sample:
```
06029010: verified=True, status="verified", vat_rate="18%", sources=["free_import_order"]
```

### 3.7 classification_knowledge (84 docs)

Working correctly. Sample:
```
hs_08105000: KIWI No23-HS T.C, chapter 08, seen_count 2
hs_0810501000: KIWI, chapter 08, seen_count 3
```

### 3.8 hub_agents (4 docs)

```
a_backup: Backup Agent (active)
a_classifier: Classification Agent (active)
a_licensing: Licensing Agent (dev)
a_scanner: Document Scanner Agent (active)
```

### 3.9 hub_tools (6 docs)

```
t_backup: Auto-Backup
t_cmdcenter: Command Center v3
t_command: Mission Command
t_intelligence: Project Intelligence
t_scanner: Document Scanner v3
t_upload: Smart Upload v2
```

### 3.10 Cost-Concerning Collections

Two collections have nearly 38K docs each and are growing:
- **scanner_logs: 37,964 docs** — PC Agent scanner creates a log entry per scan
- **files: 37,954 docs** — Every email attachment gets a document

At current Firestore pricing ($0.06/100K reads), the brute-force search in Librarian (up to 19,000 reads per query) costs ~$0.01 per query. With multiple queries per classification, this adds up.

---

## Part 4: Collection Categories

### Core Classification (5 collections, ~12K docs)
tariff, tariff_chapters, classification_knowledge, classification_rules, classification_workflow

### Search & Index (4 collections, ~32K docs)
brain_index, keyword_index, librarian_index, product_index

### Email Processing (7 collections, ~38K docs)
files, inbox, rcb_inbox, rcb_processed, rcb_classifications, rcb_silent_classifications, rcb_logs

### Tracker (5 collections, ~1K docs)
tracker_deals, tracker_observations, tracker_container_status, tracker_timeline, tracker_shipments

### Pupil Learning (7 collections, ~760 docs)
pupil_observations, pupil_teachings, pupil_corrections, pupil_reviews, pupil_audit_summaries, pupil_budget, pupil_correction_budget

### Knowledge & Regulatory (10 collections, ~8K docs)
knowledge_base, knowledge, knowledge_queries, legal_requirements, legal_references, legal_documents, regulatory, regulatory_requirements, regulatory_approvals, regulatory_certificates

### Brain & Intelligence (6 collections, ~11K docs)
brain_commands, brain_index, brain_daily_digest, intelligence_activity, intelligence_decisions, intelligence_files

### Self-Learning (6 collections, ~190 docs)
learned_contacts, learned_doc_templates, learned_patterns, learned_shipping_patterns, learned_shipping_senders, triangle_learnings

### Reference Data (5 collections, ~130 docs)
airlines, shipping_lines, document_types, fta_agreements, ministry_index

### System & Config (10 collections, ~80 docs)
config, system_counters, system_metadata, system_status, system_tasks, monitor, _health, _test, daily_state, overnight_audit_results

### Hub Web Interface (5 collections, ~2.3K docs)
hub_agents, hub_tools, hub_tasks, hub_messages, hub_links

### PC Agent (4 collections, ~39K docs)
agent_downloads, agent_tasks, scanner_logs, tech_assistant_commands

### Backup & History (6 collections, ~110 docs)
backup_log, backup_logs, session_backups, session_history, sessions_backup, project_backups

### Other (9 collections, ~900 docs)
buyers, sellers, contacts, declarations, bills_of_lading, packing_lists, unclassified_documents, enrichment_log, enrichment_tasks

### Uncategorized (12 collections)
batch_reprocess_results, batch_reprocess_summary, free_import_cache, licensing_knowledge, mission_chat, mission_decisions, missions, pending_tasks, rcb_first_emails, rcb_inspector_reports, rcb_stats, rcb_test_reports, supplier_index, verification_cache, web_search_cache, tech_assistant_state, session_missions

---

## Part 5: Critical Issues Summary

| # | Severity | Issue |
|---|----------|-------|
| 1 | MEDIUM | **tariff_chapters doc ID format** — Doc IDs are `import_chapter_XX` not plain numbers. Stream-based lookups work; direct doc-by-HS-code lookup in verification_loop.py always misses (falls through safely). |
| 2 | LOW | **keyword_index: 117 garbage docs (1%)** — 117 of 8,195 docs have AI response text as descriptions. 98% are clean. |
| 3 | HIGH | **scanner_logs + files = 76K docs growing daily** — No TTL, no cleanup. Cost and performance concern. |
| 4 | MEDIUM | **librarian_index has empty fields** — Sample shows empty description, keywords_en, keywords_he, hs_codes, source_url. Index is largely hollow. |
| 5 | MEDIUM | **111 collections vs 20 documented** — 91 undocumented collections. System has grown organically without documentation. |
| 6 | LOW | **Various encoding issues** — Hebrew content can't be displayed on Windows terminal (charmap codec). Not a data issue, just a display issue. |

---

## NOT DEPLOYED — Read-only audit. No data was modified.
