# RCB Knowledge Engine — Wiring Plan
## Session 17 — February 12, 2026
## Status: DRAFT — For Doron's approval before any code changes

---

## GOAL

Connect the existing knowledge engine components that are built but not wired.
No new features. No new code logic. Just connecting what already exists.

---

## WHAT I READ (confirmed by reading actual source code)

| File | Lines | Status |
|---|---|---|
| `librarian.py` | ~600 | Works — searches during classification |
| `librarian_index.py` | ~350 | Code works — never called from main.py |
| `librarian_researcher.py` | ~700 | Code works — never called from main.py |
| `enrichment_agent.py` | ~500 | Code works — never imported in main.py |
| `classification_agents.py` | ~800 | Works — has exact hook points identified |
| `pc_agent.py` | ~400 | Code works — never triggered |
| `librarian_tags.py` | ~??? | Couldn't read directly, but exports confirmed via importers |
| `main.py` | ~large | Confirmed: no imports of enrichment/researcher/index/pupil/tracker |

---

## PHASE 0: Improve Document Extraction (no API cost)

**Why this comes first:** Everything downstream depends on reading documents correctly. If extraction is garbage, AI classification can't save it.

**Current pipeline (confirmed in rcb_helpers.py):**
```
PDF attachment → pdfplumber (text) → if <50 chars → pypdf → if <50 chars → Vision OCR (150 DPI)
```

**Problems found:**
- Table extraction is basic — customs invoices have complex multi-column tables
- No image preprocessing before OCR — scanned gov PDFs are often low quality
- 50-char threshold is too simple — 51 chars of garbage = "success"
- No Hebrew RTL text cleanup after extraction
- No structure detection — everything is one text blob sent to Agent 1
- OCR at 150 DPI — should be 200-250 for scanned docs

**Improvements (all local, zero API cost):**

| # | Improvement | How | Cost |
|---|---|---|---|
| 0a | Raise OCR DPI | Change PyMuPDF matrix from 150/72 to 250/72 | FREE |
| 0b | Smarter threshold | Check for Hebrew chars, numbers, invoice patterns — not just char count | FREE |
| 0c | Image preprocessing | Add Pillow: contrast, grayscale, deskew, denoise before OCR | FREE (add `Pillow` to requirements.txt) |
| 0d | Better table extraction | Improve pdfplumber settings, extract tables separately with structure | FREE |
| 0e | Hebrew text cleanup | Fix RTL issues: reversed parens, mixed-direction numbers, broken words | FREE |
| 0f | Structure tagging | Regex-based: detect invoice#, dates, currency, HS codes, seller/buyer blocks | FREE |
| 0g | Multi-pass extraction | Try text + tables separately, combine with structure preserved | FREE |

**Files to change:** `rcb_helpers.py` only + `requirements.txt` (add Pillow)

**Risk:** Low. All changes are in extraction, before the AI pipeline. If new extraction fails, can fall back to current method.

---

## PHASE 1: Build the Index (one-time, no API cost)

**What:** Run `rebuild_index()` to populate `librarian_index` from existing 16,927 docs.

**Why:** The `smart_search()` function checks `librarian_index` first. With 0 docs there, every search falls back to slow per-collection scanning.

**How:** One-time Python script (not a code change):
```python
from lib.librarian_index import rebuild_index
rebuild_index(db)
```

**Risk:** None. Read-only scan + writes to librarian_index. No existing data modified.

---

## PHASE 2: Wire Learning into the Pipeline (no API cost)

**What:** After each successful classification, call the EnrichmentAgent to learn from it.

**Where exactly (confirmed by reading classification_agents.py):**

In `process_and_send_report()` function in `classification_agents.py`, there is a block that runs after the report is sent successfully:

```python
if helper_graph_send(access_token, rcb_email, to_email, subject_line, html, msg_id, attachments):
    print(f" Sent to {to_email}")
    # ... clarification logic ...
    # ... save to Firestore ...
    db.collection("rcb_classifications").add(save_data)
    return True
```

**The hook point is RIGHT AFTER `db.collection("rcb_classifications").add(save_data)`.**

**Changes needed (2 files):**

### File 1: `classification_agents.py`

Add import at top:
```python
try:
    from lib.enrichment_agent import create_enrichment_agent
    ENRICHMENT_AVAILABLE = True
except ImportError as e:
    print(f"Enrichment agent not available: {e}")
    ENRICHMENT_AVAILABLE = False
```

Add after `db.collection("rcb_classifications").add(save_data)`:
```python
# Phase 2: Learn from this classification
if ENRICHMENT_AVAILABLE:
    try:
        enrichment = create_enrichment_agent(db)
        enrichment.on_classification_complete(results)
        enrichment.on_email_processed({
            "sender": to_email,
            "subject": subject,
            "extracted_items": items
        })
        print(" Enrichment: learned from classification")
    except Exception as e:
        print(f" Enrichment learning error: {e}")
```

**Why try/except:** If enrichment fails, the classification still succeeds. Never break the main pipeline.

**What this does (confirmed by reading enrichment_agent.py):**
- `on_classification_complete()` → calls `learn_from_classification()` → stores HS code + description pairs in `classification_knowledge`
- `on_email_processed()` → calls `learn_from_email()` → stores supplier info in `knowledge_base`, product info in `knowledge_base`
- Also calls `index_single_document()` for each learned item → adds to `librarian_index`

**API cost:** ZERO. No AI calls. Just Firestore reads/writes.

**Risk:** Low. Wrapped in try/except. If it fails, main pipeline unaffected.

---

## PHASE 3: Replace Dummy `enrich_knowledge` in main.py (minimal API cost)

**What:** Replace the dummy `enrich_knowledge` scheduler function with real enrichment.

**Current code in main.py (confirmed by reading):**
```python
def enrich_knowledge(event):
    # Counts docs by category
    # Checks for unprocessed emails
    # Checks enrichment_log for stale sources
    # ... that's it, does nothing useful
```

**Replace with:**
```python
def enrich_knowledge(event):
    """Periodically enrich knowledge base — Phase 3"""
    try:
        from lib.enrichment_agent import create_enrichment_agent
        from lib.librarian_index import rebuild_index

        enrichment = create_enrichment_agent(get_db())

        # 1. Check and tag any completed PC Agent downloads
        tagged = enrichment.check_and_tag_completed_downloads()
        print(f" Tagged {len(tagged)} completed downloads")

        # 2. Run scheduled enrichment tasks (checks 23 task types)
        summary = enrichment.run_scheduled_enrichments()
        print(f" Enrichment: checked {summary['tasks_checked']}, ran {summary['tasks_run']}")

        # 3. Get status for logging
        stats = enrichment.get_learning_stats()
        print(f" Knowledge: {stats['total_learned']} learned, "
              f"{stats['corrections']} corrections, "
              f"{stats['pc_agent_downloads']} downloads")

    except Exception as e:
        print(f" Enrichment error: {e}")
        import traceback
        traceback.print_exc()
```

**What this actually does (confirmed by reading the code):**

1. `check_and_tag_completed_downloads()` — checks `pc_agent_tasks` collection for completed downloads, auto-tags them, indexes them. **No API cost.**

2. `run_scheduled_enrichments()` — iterates through 23 ENRICHMENT_TASKS, checks which are overdue based on their frequency (daily/weekly/monthly), for overdue ones:
   - Generates search queries (Hebrew + English keywords)
   - Creates PC Agent download tasks for government URLs
   - Logs what needs to be searched
   - **Does NOT actually execute web searches** (Cloud Functions can't browse)
   - **No AI API cost** — it's all Firestore reads/writes + task generation

3. `get_learning_stats()` — reads classification_knowledge + knowledge_base for stats. **No API cost.**

**API cost:** ZERO. The enrichment generates *tasks* and *queries* but doesn't call any AI APIs.

**Risk:** Low. Same try/except pattern. If it fails, the scheduler just logs an error.

---

## PHASE 4: Enable Research Execution (requires design decision)

**The problem:** `run_scheduled_enrichments()` and `run_continuous_research()` generate search queries but don't execute them. The researcher creates lists like:
```
"query": "HS code 8471 classification"
```

But nobody runs these searches.

**Options (Doron needs to decide):**

### Option A: Gemini Flash as researcher (cheapest)
- Add a function that takes the generated queries
- Sends them to Gemini Flash with prompt: "You are a customs research assistant. Search your knowledge for: {query}. Return structured findings."
- Cost: ~$0.001 per query (Gemini Flash input/output)
- Limitation: Gemini only knows what's in its training data, can't access live websites

### Option B: PC Agent downloads (free but manual)
- The system already creates PC Agent tasks for government URLs
- Need to set up the PC Agent runner script on Doron's office PC
- PC Agent downloads PDFs from government sites → uploads → auto-tags
- Cost: FREE (no API calls)
- Limitation: Requires PC to be running, can't handle all query types

### Option C: Web search API (most capable, costs money)
- Use Google Custom Search API or similar
- Actually searches the web, returns results
- Feed results into Gemini Flash for analysis
- Cost: Google Search API has free tier (100 queries/day), then $5/1000 queries

### Option D: Combined approach (recommended)
- Phase 4a: Set up PC Agent for government PDF downloads (FREE)
- Phase 4b: Use Gemini Flash for knowledge-based research (CHEAP)
- Phase 4c: Add web search API later if needed (OPTIONAL)

**Doron's decision (Feb 12): DO ALL OF THEM. Cascade approach:**
1. PC Agent tries first (FREE)
2. If PC fails → Gemini Flash analyzes from its knowledge (CHEAP)
3. If Gemini can't answer → Web Search API fetches real results (max $5/1000 queries)
4. Feed search results back into Gemini Flash for structured analysis
5. For critical/disputed classifications → cross-check with ChatGPT as third opinion

Budget approved: $5/1000 queries is acceptable.

### Multi-Model Strategy (updated)

The system should use 3 AI models strategically:

| Model | Use for | Cost | When |
|---|---|---|---|
| Gemini Flash | 90% of work: extraction, regulatory, FTA, risk, synthesis, research analysis | ~$0.001/call | Default for everything |
| Claude Sonnet | Core HS classification (Agent 2), complex reasoning | ~$0.04/call | Only Agent 2 |
| ChatGPT (GPT-4o-mini or GPT-4o) | Cross-check disputed classifications, second opinion on low-confidence results, alternative research perspective | ~$0.002-0.01/call | When confidence is low or models disagree |

**Cross-check logic (Phase 4):**
- If Agent 2 (Claude) returns confidence low → ask Gemini Flash + ChatGPT for their classification
- If all 3 agree → boost confidence to medium
- If 2 of 3 agree → use majority, flag the disagreement
- If all 3 disagree → flag for Doron's manual review
- Cost: only triggered on low-confidence items, estimated 10-20% of classifications

**Requires:** OpenAI API key added to Secret Manager as `OPENAI_API_KEY`

---

## PHASE 5: Wire Pupil + Tracker (needs files first)

**Pupil (pupil_v05_final.py):**
- Doron has this file locally, not in repo
- Need to: get the file, review it, add to repo, wire into pipeline
- Purpose: Devil's advocate, questions classifications, learns from patterns

**Tracker (tracker.py):**
- Doron has this file locally, not in repo
- Has known None crash bug that needs fixing
- Purpose: Track shipments, connect outcomes to classifications

**Action needed:** Doron to provide both files so we can review them.

---

## DEPLOYMENT PLAN

Each phase gets its own commit and deploy:

| Phase | Commit message | Risk | Deploy |
|---|---|---|---|
| 0 | "Improve PDF extraction: OCR, tables, Hebrew, structure" | Low | GitHub Actions |
| 1 | "Populate librarian_index (one-time rebuild)" | None | N/A (script only) |
| 2 | "Wire learning into classification pipeline" | Low | GitHub Actions |
| 3 | "Replace dummy enrich_knowledge with real enrichment" | Low | GitHub Actions |
| 4 | "Enable research execution (PC Agent + Gemini + Web)" | Medium | After testing |
| 5 | "Wire Pupil and Tracker agents" | Medium | After testing |

**Rule: Each phase is tested before starting the next one.**

---

## FILES THAT WILL BE CHANGED

| Phase | File | Change type |
|---|---|---|
| 0 | `rcb_helpers.py` | Improve extraction functions |
| 0 | `requirements.txt` | Add Pillow |
| 1 | No files changed | One-time script |
| 2 | `classification_agents.py` | Add import + 10 lines after save |
| 3 | `main.py` | Replace enrich_knowledge function body |
| 4 | `main.py` + `classification_agents.py` + possibly new file | Add research cascade, add `call_chatgpt()`, add cross-check logic, add OPENAI_API_KEY to Secret Manager |
| 5 | `main.py` + new files | Add imports + scheduler entries |

---

## WHAT I WILL NOT DO

- No blind coding — every change is based on confirmed code reading
- No guessing what functions do — I read every line
- No breaking the main pipeline — all new code is wrapped in try/except
