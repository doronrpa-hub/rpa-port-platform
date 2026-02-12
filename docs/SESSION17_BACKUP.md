# Session 17 Backup — February 12, 2026
## AI: Claude Opus (claude.ai via Chrome browser)
## Task: Full code audit of knowledge engine — what exists, what's connected, what's dead

---

## WHAT WAS DONE THIS SESSION

Read the actual source code of all knowledge system files via GitHub raw URLs:
- `functions/main.py` — all cloud function entry points
- `functions/lib/librarian.py` — search engine (full file, ~600 lines)
- `functions/lib/librarian_index.py` — document indexing (full file, ~350 lines)
- `functions/lib/librarian_researcher.py` — research engine (full file, ~700 lines)
- `functions/lib/enrichment_agent.py` — orchestrator (full file, ~500 lines)

Also reviewed from Session 16 transcript:
- Firestore inventory: 16,927 docs across 40 collections
- All collection counts documented in docs/FIRESTORE_INVENTORY.md

---

## CONFIRMED FINDINGS (from reading actual code, not guessing)

### 1. `enrich_knowledge` in main.py is a DUMMY

**Location:** `main.py`, function `enrich_knowledge(event)`
**Runs:** Every 1 hour (scheduler)
**What it ACTUALLY does:**
- Counts documents in knowledge_base by category
- Checks inbox for unprocessed emails
- Checks enrichment_log for stale sources
- Prints logs
**What it does NOT do:**
- Does NOT import or call `EnrichmentAgent`
- Does NOT import or call `librarian_researcher`
- Does NOT import or call `librarian_index`
- Does NOT call `rebuild_index()`
- Does NOT call `run_scheduled_enrichments()`
- Does NOT call `learn_from_classification()`
- Does NOT trigger any web search or research

**Proof:** Searched main.py for these strings — ALL returned NOT FOUND:
- `pupil` — NOT FOUND
- `tracker` — NOT FOUND
- `EnrichmentAgent` — NOT FOUND
- `enrichment_agent` — NOT FOUND
- `librarian_researcher` — NOT FOUND
- `rebuild_index` — NOT FOUND
- `run_scheduled` — NOT FOUND

### 2. `librarian.py` — WORKS but limited

**What it does (confirmed by reading code):**
- `full_knowledge_search(db, query_terms, item_description)` — searches 7 collection groups
- `search_tariff_codes()` — searches tariff_chapters, tariff, hs_code_index
- `search_regulations()` — searches ministry_index, regulatory, regulatory_approvals, regulatory_certificates, licensing_knowledge
- `search_procedures_and_rules()` — searches procedures, classification_rules, classification_knowledge
- `search_knowledge_base()` — searches knowledge, knowledge_base, legal_references, legal_documents
- `search_history()` — searches classifications, declarations, rcb_classifications
- `validate_hs_code()` — checks if HS code exists in tariff DB
- `build_classification_context()` — formats search results for AI agent prompt

**How search works:** Brute-force keyword matching. Loads up to 500 docs per collection, checks if keywords appear in text fields, scores by keyword count. No embeddings, no vector search, no AI.

**Connected to pipeline:** YES — called from `classification_agents.py` during Agent 2 (HS classification). This is the ONLY part of the knowledge system that actually runs in production.

**Limitation:** Searches are ONLY as good as what's in the collections. If knowledge_base has 294 docs and most are supplier/product entries from emails, the librarian finds very little useful regulatory knowledge.

### 3. `librarian_index.py` — NEVER RUNS

**What it does (confirmed by reading code):**
- `rebuild_index(db)` — scans ALL 20 known collections, builds master index in `librarian_index` collection
- `index_collection(db, collection_name)` — indexes one collection
- `index_single_document(db, collection_name, doc_id, data)` — indexes one doc
- `scan_all_collections(db)` — counts docs in all collections
- `get_inventory_stats(db)` — comprehensive stats

**Index entry structure:** Each doc gets: title, description, tags (auto-generated), keywords_he, keywords_en, hs_codes, ministries, countries, source_url, file_path, confidence_score

**Why librarian_index has 0 docs:** `rebuild_index()` is never called from main.py. Nobody triggers it. The index was designed to be built but the trigger was never wired.

**Impact:** The `smart_search()` function in librarian.py checks librarian_index FIRST for fast results, then falls back to raw collection search. With 0 index docs, it always falls back.

### 4. `librarian_researcher.py` — NEVER RUNS

**What it does (confirmed by reading code):**
- Defines 23 ENRICHMENT_TASKS covering: tariff updates, classification decisions, free import order, customs procedures, ministry procedures (health, agriculture, transport, communications), standards, regulations, court rulings, FTAs, export procedures, export control, rules of origin, ATA carnet, declarants, customs release, valuation, bonded warehouse, temporary import/export, WCO updates, EU regulations, email learning, classification learning, correction learning, continuous DB scan
- Defines RESEARCH_KEYWORDS with Hebrew + English search terms for each topic
- Defines ISRAELI_WEB_SOURCES (9 sources: customs.mof.gov.il, taxes.gov.il, gov.il ministries, nevo.co.il, takdin.co.il, sii.org.il)
- Defines INTERNATIONAL_WEB_SOURCES (3: wcoomd.org, eur-lex.europa.eu, trade.gov)
- `scan_db_for_research_keywords(db)` — finds low-confidence classifications, docs needing update, HS codes missing regulatory info
- `learn_from_classification(db, result)` — stores learned HS code + description pairs
- `learn_from_correction(db, orig, corrected, desc)` — stores corrections (high value)
- `learn_from_email(db, email_data)` — extracts supplier + product knowledge
- `learn_from_web_result(db, web_result, topic)` — stores web research results
- `find_similar_classifications(db, description)` — word-overlap similarity matching
- `check_for_updates(db, source)` — checks if enrichment tasks are overdue
- `schedule_enrichment()` / `complete_enrichment()` — task lifecycle

**Key insight:** The researcher GENERATES search queries but does NOT execute them. It creates lists of Hebrew/English search terms and Israeli/international URLs. It was designed to hand these off to either:
1. An external web search service (not implemented)
2. The PC Agent for browser-based downloads (delegation exists but never triggered)

### 5. `enrichment_agent.py` — The Orchestrator — NEVER INSTANTIATED

**What it does (confirmed by reading code):**
- `EnrichmentAgent(db)` class that wraps everything:
  - `on_classification_complete(result)` — calls learn_from_classification + indexes the result
  - `on_email_processed(email_data)` — calls learn_from_email
  - `on_correction(orig, corrected, desc, reason)` — calls learn_from_correction
  - `on_web_result(web_result, topic)` — calls learn_from_web_result
  - `run_continuous_research()` — scans DB for gaps, generates research queries, delegates to PC Agent
  - `run_scheduled_enrichments()` — checks all 23 tasks, runs overdue ones
  - `request_gov_downloads()` — creates PC Agent tasks for all government sources
  - `request_customs_handbook_download()` — creates tasks for customs handbook chapters
  - `researcher_delegate_to_pc_agent(url, name, tags, scope)` — KEY integration between researcher and PC agent
  - `check_and_tag_completed_downloads()` — checks PC Agent completed downloads, auto-tags them via librarian

**The complete intended cycle:**
```
Email arrives
  → EnrichmentAgent.on_email_processed() → learns suppliers/products
  → EnrichmentAgent.on_classification_complete() → learns HS codes
  → EnrichmentAgent.run_continuous_research() → finds gaps
    → generates search queries
    → delegates browser downloads to PC Agent
  → EnrichmentAgent.check_and_tag_completed_downloads()
    → PC Agent downloads come back
    → librarian auto-tags them
    → librarian_index indexes them
  → EnrichmentAgent.run_scheduled_enrichments()
    → checks 23 enrichment task types
    → runs overdue ones
```

**None of this runs** because EnrichmentAgent is never imported or instantiated in main.py.

### 6. Files NOT in repo (confirmed NOT FOUND)

- `pupil_v05_final.py` — Doron has this locally, not committed
- `tracker.py` — Doron has this locally, not committed, has known None crash bug

---

## COLLECTION STATUS (from Session 16 Firestore count)

### Has useful data:
| Collection | Count | What's in it |
|---|---|---|
| tariff | 11,753 | Full Israeli tariff database — HS codes + descriptions |
| librarian_search_log | 2,896 | Search history (analytics only) |
| agent_tasks | 731 | Task queue records |
| enrichment_tasks | 304 | Enrichment task records |
| knowledge_base | 294 | Mix of supplier, product, and some knowledge entries |
| librarian_enrichment_log | 163 | Enrichment execution logs |
| tariff_chapters | 101 | Tariff chapter summaries |
| hs_code_index | 101 | HS code index entries |
| rcb_classifications | 83 | Completed classification results |
| declarations | 53 | Past customs declarations |
| classification_knowledge | 58 | Learned HS code patterns |

### Weak (needs more data):
| Collection | Count | What's needed |
|---|---|---|
| classification_rules | 6 | General interpretation rules (should have dozens) |
| regulatory_certificates | 4 | Certificate types (should cover all ministries) |
| sellers | 4 | Known sellers/suppliers |
| ministry_index | 9 | Ministry requirements (should be much more) |

### Empty (0 docs):
| Collection | Should contain |
|---|---|
| librarian_index | Master search index — rebuild_index() never ran |
| librarian_tags | Auto-generated tags — never ran |
| learning_log | Learning events — never wired |
| monitor_errors | Error tracking — never wired |
| pc_agent_tasks | PC Agent download tasks — never triggered |
| system_state | System state — never wired |
| rcb_pdf_requests | PDF generation requests — unused |

---

## WHAT NEEDS TO HAPPEN (wiring plan — to be detailed next)

### Phase 1: Build the index (no API cost)
- Run `rebuild_index()` once to populate librarian_index from existing 16,927 docs
- This makes all existing knowledge searchable through the smart index

### Phase 2: Wire learning into the pipeline (no API cost)
- After each classification: call `EnrichmentAgent.on_classification_complete()`
- After each email: call `EnrichmentAgent.on_email_processed()`
- On corrections: call `EnrichmentAgent.on_correction()`
- This makes the system learn from every interaction

### Phase 3: Wire enrichment scheduler (minimal API cost)
- Replace dummy `enrich_knowledge` in main.py with real `EnrichmentAgent.run_scheduled_enrichments()`
- Wire `check_and_tag_completed_downloads()`
- This activates the 23 research task types

### Phase 4: Enable actual web research (needs design decision)
- Researcher generates queries but can't execute them from Cloud Functions
- Options: Cloud Functions with requests library, dedicated research function, PC Agent delegation
- This is where Gemini Flash API calls would be used for analysis

### Phase 5: Wire Pupil + Tracker (needs files first)
- Get pupil_v05_final.py into repo
- Fix tracker.py None crash bug
- Wire both into main.py

---

## FILES READ THIS SESSION
1. `functions/lib/librarian.py` — full (~600 lines)
2. `functions/lib/librarian_index.py` — full (~350 lines)
3. `functions/lib/librarian_researcher.py` — full (~700 lines)
4. `functions/lib/enrichment_agent.py` — full (~500 lines)
5. `functions/main.py` — partial (searched for specific strings)
