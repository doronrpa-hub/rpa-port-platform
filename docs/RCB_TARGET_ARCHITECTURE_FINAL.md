# RCB TARGET ARCHITECTURE — FINAL
## The Method Leads. AI Participates. The User Gets Clarity.
## Date: February 17, 2026
## For: Claude Code — Review against codebase, then implement block by block

---

## CORE PRINCIPLE

The Israeli customs classification methodology (Phases 0-9) is the **backbone**.
AI is woven into every phase as an **active participant** — reads, researches,
challenges, enriches, plays devil's advocate. The method has the final say.

When the method + AI reach 100% certainty → deliver the answer.
When they don't → ask the user a **precise, structured question** that will
resolve it. Process the answer. Reach 100%. This is how professional accuracy
becomes achievable on every single classification.

**The final product delivers**: Accuracy, professionalism, comfort, visuality,
clear language, accumulated knowledge, saved searches and actions, helpful
reminders, and flagged crucial points.

---

## THE PRODUCT EXPERIENCE — WHAT THE USER SEES

### Principle: Tables First. Short and Precise. Elaboration Second.

The user is a busy customs broker or operations person. They want:
1. **The answer** — in a clear table, Hebrew, professional
2. **What they need to do** — flagged, highlighted
3. **Why** — only if they scroll down to read more

Every email from RCB follows this structure:

```
┌─────────────────────────────────────────────────────────┐
│  SECTION 1: THE ANSWER (always present)                 │
│                                                         │
│  Clean table(s) with:                                   │
│  - HS code(s)                                           │
│  - Hebrew tariff description (exact from תעריף)         │
│  - Duty rate, purchase tax                              │
│  - Import requirements (licenses, standards)            │
│  - Status indicators (✓ confirmed / ⚠ needs input)     │
│  - Crucial flags (⚠ requires permit! ⚠ antidumping!)   │
│                                                         │
│  If clarification needed: the question box (see below)  │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  SECTION 2: ELABORATION (for those who want detail)     │
│                                                         │
│  - Why this code (elimination reasoning, brief)         │
│  - Sources consulted                                    │
│  - Alternative codes considered and why eliminated       │
│  - Any AI disagreements and how resolved                │
│  - Confidence breakdown                                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### When 100% Certain — The Classification Report

```
╔══════════════════════════════════════════════════════════╗
║  RCB — דוח סיווג                                        ║
║  Invoice: [supplier] #[number] | Date: [date]           ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  ┌──────┬────────────┬──────────────────┬──────┬──────┐ ║
║  │ שורה │ פרט מכס     │ תיאור תעריף       │ מכס  │ מס   │ ║
║  │ Line │ HS Code     │ Tariff Desc (HE)  │ Duty │ Tax  │ ║
║  ├──────┼────────────┼──────────────────┼──────┼──────┤ ║
║  │  1   │73.26.9000/2│ מוצרים אחרים של    │ 6%  │ 17% │ ║
║  │      │            │ ברזל או פלדה       │      │      │ ║
║  ├──────┼────────────┼──────────────────┼──────┼──────┤ ║
║  │  2   │39.23.1000/8│ קופסאות, ארגזים    │ 12% │ 17% │ ║
║  │      │            │ וכלי קיבול דומים   │      │      │ ║
║  └──────┴────────────┴──────────────────┴──────┴──────┘ ║
║                                                          ║
║  ⚠ שורה 2: דרוש אישור מכון התקנים הישראלי (מת"י)         ║
║  ⚠ Line 2: Requires Standards Institute approval          ║
║                                                          ║
║  ✓ בדיקת צו יבוא חופשי — תקין                            ║
║  ✓ Free Import Order check — passed                      ║
║                                                          ║
╠══════════════════════════════════════════════════════════╣
║  ELABORATION (click to expand / scroll down)             ║
║  ...reasoning, sources, alternatives considered...       ║
╚══════════════════════════════════════════════════════════╝
```

### When Clarification Needed — The Smart Question

This is the KEY feature that achieves 100% accuracy. When the system has done
all its work (Phases 0-8) but can't reach certainty on an item:

```
╔══════════════════════════════════════════════════════════╗
║  RCB — דוח סיווג (דרוש הבהרה)                           ║
║  Invoice: Goodpack #GP-2026-0441 | Date: 2026-02-17     ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  ✓ שורה 1: 84.31.3100/4 — סיווג מאושר                   ║
║    (חלקים של מכונות הרמה — ✓ confirmed)                   ║
║                                                          ║
║  ⚠ שורה 3: דרושה הבהרה                                  ║
║                                                          ║
║  Invoice line 3: "Empty metal boxes"                     ║
║  Supplier: Goodpack | Item: GP-IBC-1220                  ║
║                                                          ║
║  המערכת בדקה וסיווגה — שני פרטי מכס אפשריים:              ║
║  (System checked — two possible classifications:)        ║
║                                                          ║
║  ┌─────┬────────────┬──────────────────────────┬──────┐ ║
║  │  #  │ פרט מכס     │ תיאור מתעריף המכס         │ מכס  │ ║
║  ├─────┼────────────┼──────────────────────────┼──────┤ ║
║  │  א  │73.26.9000/2│ מוצרים אחרים של ברזל      │  6% │ ║
║  │     │            │ או פלדה, לא נתפסים        │      │ ║
║  │     │            │ בפרט אחר בפרק זה          │      │ ║
║  ├─────┼────────────┼──────────────────────────┼──────┤ ║
║  │  ב  │73.10.1000/6│ מיכלים, חביות, פחים       │  8% │ ║
║  │     │            │ וכלי קיבול דומים של        │      │ ║
║  │     │            │ ברזל או פלדה              │      │ ║
║  └─────┴────────────┴──────────────────────────┴──────┘ ║
║                                                          ║
║  ╔════════════════════════════════════════════════════╗  ║
║  ║  לצורך סיווג מדויק, נא הבהירו:                    ║  ║
║  ║  (To classify precisely, please clarify:)          ║  ║
║  ║                                                    ║  ║
║  ║  1. האם הקופסאות נסגרות הרמטית?                    ║  ║
║  ║     (Do the boxes close hermetically?)             ║  ║
║  ║                                                    ║  ║
║  ║     [ ] כן, נסגרות הרמטית (Yes, hermetically)     ║  ║
║  ║     [ ] לא, פתוחות/מתקפלות (No, open/foldable)    ║  ║
║  ║                                                    ║  ║
║  ║  2. מה הנפח? (What is the volume?)                 ║  ║
║  ║                                                    ║  ║
║  ║     [ ] מעל 300 ליטר (Over 300L)                   ║  ║
║  ║     [ ] מתחת 300 ליטר (Under 300L)                 ║  ║
║  ║                                                    ║  ║
║  ║  הערות נוספות: ______________________________      ║  ║
║  ║  (Additional notes)                                ║  ║
║  ║                                                    ║  ║
║  ║              [ השב / Reply ]                       ║  ║
║  ╚════════════════════════════════════════════════════╝  ║
║                                                          ║
║  💡 אם הקופסאות פתוחות/מתקפלות ומתחת 300L:              ║
║     → 73.26.9000/2 (מוצרים אחרים) — מכס 6%             ║
║     אם הקופסאות נסגרות הרמטית ומעל 300L:                ║
║     → 73.10.1000/6 (מיכלים) — מכס 8%                    ║
║                                                          ║
╠══════════════════════════════════════════════════════════╣
║  ELABORATION                                             ║
║  ...why these two codes, what was eliminated, sources... ║
╚══════════════════════════════════════════════════════════╝
```

### The Reply Processing Loop

When the user replies (clicks options + optional notes):

```
User replies: "לא, פתוחות/מתקפלות" + "מתחת 300 ליטר"
    │
    ▼
System receives reply via email
    │
    ▼
Brain processes:
  - Match reply to original question context
  - Answer resolves the ambiguity: open/foldable + under 300L
  - Re-run ONLY the unresolved elimination step (not full pipeline)
  - 7310 eliminated (requires hermetic closure or >300L)
  - 7326.90 confirmed
    │
    ▼
Cost of processing reply: ~$0.005 (minimal AI, targeted re-evaluation)
    │
    ▼
Send FINAL classification:
  "שורה 3: 73.26.9000/2 — ✓ מאושר (בהתאם להבהרה שהתקבלה)"
  (Line 3: 73.26.9000/2 — ✓ confirmed per clarification received)
    │
    ▼
Save to classification_memory:
  - Product: "Goodpack GP-IBC-1220, foldable steel boxes, open, <300L"
  - HS: 7326.90.9000/2
  - Confidence: 1.00 (clarification-verified)
  - Key learning: "foldable metal boxes from Goodpack = 7326.90,
    distinguish from 7310 by: not hermetic, under 300L"
  - Next time Goodpack metal boxes arrive → instant classification
```

### Cost Impact of Clarification Flow

The clarification question itself costs almost nothing to generate (it comes from
the elimination log — the system already knows WHY it's uncertain). Processing the
reply is a tiny targeted re-evaluation, not a full pipeline run.

But the VALUE is enormous:
- Turns a "maybe 90% confident" into "100% confirmed"
- The confirmed answer goes into memory as high-confidence
- Next time → instant classification, zero cost
- Reduces the "long tail" of uncertain products much faster

---

## EMAIL COMMUNICATION — CURRENT PROBLEM AND FIX

### Current State: Brain Can't Communicate Well

The audit found that email output is broken or poor:
- Tracker emails crash (function signature mismatch — fixed locally, not deployed)
- Classification reports are generic and unhelpful
- No structured clarification mechanism
- No professional formatting
- No Hebrew RTL proper rendering
- No distinction between "answer" and "elaboration"

### Target: Professional, Clear, Bilingual Communication

Every email from RCB must be:

| Requirement | Description |
|-------------|------------|
| **Table-first** | Key information in clean tables at the top, always |
| **Short and precise** | Section 1 answers the question in minimal words |
| **Hebrew RTL** | Proper right-to-left rendering with correct fonts |
| **Bilingual where needed** | Hebrew primary, English in parentheses for product descriptions |
| **Visually clear** | Status indicators (✓ ⚠), color coding, clean borders |
| **Actionable** | If user needs to do something → highlighted, specific |
| **Flagged** | Crucial points (permits, deadlines, antidumping) → prominent warning |
| **Interactive** | Clarification questions with clickable options + notes field |
| **Elaboration separate** | Detail available but not forced on the user |

### Email Types and Their Format

| Email Type | Section 1 (Top) | Section 2 (Below) |
|------------|----------------|-------------------|
| **Classification — certain** | Table: line items, HS codes, duties, flags | Elimination reasoning, sources, alternatives considered |
| **Classification — needs clarification** | Table of candidates + structured question box | Why these candidates, what was eliminated |
| **Clarification reply processed** | Updated table with confirmed codes | What changed, what the answer resolved |
| **Tracker update** | Table: container/BL, status, vessel, ETA, location | Full timeline, document history |
| **Tracker alert** | ⚠ What happened, what user should do | Background details |
| **Daily digest** | Summary table: active deals, pending items, overdue | Per-deal detail |
| **Reminder/flag** | ⚠ What's due, deadline, required action | Context and background |

---

## ARCHITECTURE OVERVIEW

```
Email arrives (CC / direct / airpaport@gmail)
      │
      ├── CC email ──► Silent learning + detect classifiable content
      │                If invoice found → ALSO trigger classification
      ├── airpaport ──► Extract verified declaration → ground truth
      ├── Reply to clarification ──► Process answer → finalize → 100%
      └── Direct classification request ──► Full pipeline
      │
      ▼
╔═══════════════════════════════════════════════════════════╗
║  CHECK MEMORY FIRST                                       ║
║  1. Exact match (past classification or declaration)?     ║
║  2. Similar product from CC learning?                     ║
║  3. Pre-ruling in brain knowledge base?                   ║
║  4. Classification directive covers this?                 ║
║  → High confidence: verify + deliver ($0.00)              ║
║  → Partial match: abbreviated run from narrowed chapters  ║
║  → No match: full Phase 0-9                               ║
╚═══════════════════════════════════════════════════════════╝
      │
      ▼
╔═══════════════════════════════════════════════════════════╗
║  PHASE 0 — CASE TYPE                                     ║
║  Code: Import/Export? Movement type? Procedure?           ║
║  AI: Resolve ambiguity from email context if needed       ║
╚═══════════════════════════════════════════════════════════╝
      │
      ▼
╔═══════════════════════════════════════════════════════════╗
║  PHASE 1 — EXAMINE GOODS (THREE PILLARS)                 ║
║  AI: Read docs, extract material/form/weight/essence/use  ║
║  AI: Flag inconsistencies, enrich from brain knowledge    ║
║  Code: Validate three pillars populated                   ║
╚═══════════════════════════════════════════════════════════╝
      │
      ▼
╔═══════════════════════════════════════════════════════════╗
║  PHASE 2 — GATHER INFORMATION                            ║
║  AI: Research supplier, web search, foreign tariffs       ║
║  Brain: Provide indexed directives, rulings, UK tariff    ║
║  Code: Track legal obligation met (ב׳ mandatory)         ║
╚═══════════════════════════════════════════════════════════╝
      │
      ▼
╔═══════════════════════════════════════════════════════════╗
║  PHASE 3 — ELIMINATION ENGINE                            ║
║  Code: Walk tariff tree chapter by chapter                ║
║  Brain: Provide chapter notes, framework definitions      ║
║  AI: Confirm/challenge at each decision point             ║
║  AI: Devil's advocate before finalizing                   ║
║  Method: Decides, logs reasoning including AI input       ║
╚═══════════════════════════════════════════════════════════╝
      │
      ▼
╔═══════════════════════════════════════════════════════════╗
║  PHASE 4 — BILINGUAL VERIFICATION                        ║
║  Code: Query shaarolami HE + EN, compare                  ║
║  AI: Analyze mismatches if any                            ║
╚═══════════════════════════════════════════════════════════╝
      │
      ▼
╔═══════════════════════════════════════════════════════════╗
║  PHASE 5 — POST-CLASSIFICATION VERIFICATION              ║
║  Brain: Matching directives, pre-rulings, court decisions ║
║  AI: "Does this ruling apply to our product?"             ║
║  Method: Accept, flag, or re-run                          ║
╚═══════════════════════════════════════════════════════════╝
      │
      ▼
╔═══════════════════════════════════════════════════════════╗
║  PHASE 6 — REGULATORY & COMMERCIAL                       ║
║  Brain: Full FIO requirements per HS code                 ║
║  Code: Invoice validation, FTA, permits                   ║
║  AI: Flag gaps, suggest what's needed                     ║
╚═══════════════════════════════════════════════════════════╝
      │
      ▼
╔═══════════════════════════════════════════════════════════╗
║  PHASE 7 — MULTI-AI CROSS-CHECK                          ║
║  AI models classify independently (blind)                 ║
║  Compare to method's result                               ║
║  Disagreement: identify divergence, document both         ║
╚═══════════════════════════════════════════════════════════╝
      │
      ▼
╔═══════════════════════════════════════════════════════════╗
║  PHASE 8 — SOURCE ATTRIBUTION                            ║
║  Code: Every decision → source reference                  ║
║  AI: Review completeness                                  ║
╚═══════════════════════════════════════════════════════════╝
      │
      ▼
╔═══════════════════════════════════════════════════════════╗
║  DECISION POINT                                          ║
║                                                           ║
║  Certain (all items resolved)?                            ║
║  ├── YES → Phase 9: FINAL REPORT (table-first format)    ║
║  └── NO  → Phase 9: CLARIFICATION EMAIL                  ║
║            - Table of candidates per uncertain item       ║
║            - Structured question with clickable options   ║
║            - Notes field for free-text                    ║
║            - Shows: "if X then code A, if Y then code B"  ║
║            - User replies → brain processes → 100%        ║
╚═══════════════════════════════════════════════════════════╝
      │
      ▼
╔═══════════════════════════════════════════════════════════╗
║  ALWAYS — LEARN, RECORD, IMPROVE                         ║
║  Save classification + elimination log                    ║
║  Update indexes (keyword, product, supplier)              ║
║  AI reflects: "What was tricky? What to remember?"        ║
║  Clarification answers → high-confidence memory entries   ║
║  CC + airpaport learning in parallel                      ║
╚═══════════════════════════════════════════════════════════╝
```

---

## THE THREE LEARNING CHANNELS

### Channel 1: CC Emails (FREE)
- Team's actual classification work, expert-verified
- ~200-400 data points/month
- Silent: observe, extract, store. Never reply.

### Channel 2: Customs Declarations — airpaport@gmail.com (FREE)
- רשומוני מכס that customs ACCEPTED = ground truth
- ~100-200 data points/month
- HS codes, duties, requirements — all confirmed by customs authority

### Channel 3: Brain Knowledge Base (One-time + maintenance)

| Source | Impact |
|--------|--------|
| פקודת המכס | Full legal framework — the rules the method follows |
| צו יבוא חופשי — ALL appendices | Per HS code: licenses, standards, ministries |
| צו יצוא חופשי — ALL appendices | Per HS code: export requirements |
| צו המסגרת — complete | Legal definitions that override common language |
| הראישה לפרק — all 99 chapters | Gates for Phase 3 elimination |
| הנחיות סיווג — all directives | Customs authority interpretation per code |
| פרה-רולינג — all published | Official classifications for specific products |
| Court decisions | Legal precedents (VIVO, DENVER SANDALS, HALPERIN) |
| קודי הנחה ותוספות | FTA rates, preferential duties |
| Full shaarolami dump HE + EN | All codes with descriptions and duties |

Once indexed: thousands of classification paths pre-answered before any email arrives.

### Channel 4: Clarification Replies (VERY CHEAP)

Every clarification that gets answered becomes a HIGH-CONFIDENCE memory entry:
- The question identified exactly what was ambiguous
- The answer resolved it definitively
- The confirmed classification goes into memory with confidence ≈ 1.00
- Next time this product appears → instant, no question needed

**This is the fastest path from "uncertain" to "100% known"** — and it costs
almost nothing ($0.005 to process each reply).

---

## MODEL ROUTING

| Priority | Model | Roles | Cost/call |
|----------|-------|-------|-----------|
| 1 | **FREE** | Memory, brain knowledge, indexes, regex, templates, Firestore, shaarolami cache, elimination logic, CC/declaration extraction | $0.00 |
| 2 | **Gemini Flash** | Document extraction fallback | ~$0.001 |
| 3 | **GPT-4o** | Primary AI: read docs, research, elimination participation, devil's advocate, reports, clarification questions | ~$0.01-0.02 |
| 4 | **Claude Sonnet** | Specialist: complex legal Hebrew, disputed Rule 3, ambiguous cases | ~$0.02-0.03 |
| 5 | **Three-way** | Independent cross-check, disagreement resolution | ~$0.05-0.10 |

---

## THE KINGS ROAD — COST EVOLUTION

### Per-Email Cost Breakdown (After All Blocks Built)

| Scenario | What Happens | Cost |
|----------|-------------|------|
| **Memory hit — exact match** | Verify against current tariff, deliver | $0.002 |
| **Memory hit — similar product** | Abbreviated run from narrowed chapters | $0.015 |
| **Full run — straightforward** | Phases 0-9, method resolves cleanly | $0.04 |
| **Full run — needs clarification** | Phases 0-8, send question, wait for reply | $0.04 + $0.005 when reply comes |
| **Full run — complex** | Claude escalation, cross-check | $0.08-0.12 |

### 12-Month Projection (20 classification emails/day)

| Month | Block | Memory hit | Clarification rate | Avg $/email | Classification | Brain | **Total** | Accuracy |
|-------|-------|-----------|-------------------|-------------|---------------|-------|-----------|----------|
| 1 | A (runs) | 10-15%* | 30% (no method yet) | $0.05 | $30 | $105 | **$135** | 60-70% |
| 2 | B+C (data) | 25-35%* | 25% | $0.04 | $24 | $105 | **$129** | 75-80% |
| 3 | D (engine) | 45-55% | 15% | $0.025 | $15 | $105 | **$120** | 90%+ |
| 4 | E (verify) | 55-65% | 10% | $0.018 | $11 | $90 | **$101** | 93-95% |
| 5 | F (routing) | 65-70% | 8% | $0.014 | $8 | $80 | **$88** | 95%+ |
| 6 | G (memory) | 70-80% | 5% | $0.010 | $6 | $70 | **$76** | 97%+ |
| 9 | G mature | 85-90% | 3% | $0.006 | $4 | $45 | **$49** | 98-100% |
| 12 | Cruising | 90%+ | <2% | $0.004 | $2.50 | $30 | **$33** | 99-100% |

*Months 1-2: memory hits come from CC/airpaport + brain knowledge, not self-classification.

**Key insight**: Clarification rate DROPS as memory grows. By month 6, most products
have been seen (directly, via CC, via declarations, or via brain knowledge). The few
that need clarification get answered, stored, and never asked again.

### Year 1 Total

| Period | Months | Avg monthly | Subtotal |
|--------|--------|-------------|----------|
| Building (months 1-3) | 3 | $128 | $384 |
| Optimizing (months 4-6) | 3 | $88 | $264 |
| Cruising (months 7-12) | 6 | $41 | $246 |
| One-time brain download | — | — | $20 |
| **Year 1 total** | | | **~$914** |
| **Average monthly** | | | **~$76** |

### Year 2 Projection

| Item | Monthly |
|------|---------|
| Classification (90%+ memory, rare full runs) | $2-3 |
| Brain maintenance (monitoring for legal changes) | $15-25 |
| **Year 2 monthly** | **$17-28** |
| **Year 2 annual** | **$204-336** |

### Comparison

| Approach | Monthly avg | Annual | Accuracy |
|----------|-----------|--------|----------|
| Pure AI, no method | $200-250 | $2,400-3,000 | 60-70% (never improves) |
| **Kings Road Year 1** | **$76** | **$914** | **60% → 99-100%** |
| **Kings Road Year 2** | **$22** | **$270** | **99-100%** |

---

## HELPING, REMINDING, AND FLAGGING

Beyond classification, the system proactively helps the user:

### Proactive Flags (in every relevant email)

| Flag Type | Example | When |
|-----------|---------|------|
| ⚠ Permit required | "⚠ HS 7326.90 — requires מת"י approval for import >100 units" | Phase 6 check finds requirement |
| ⚠ Antidumping | "⚠ Product from China under antidumping order #XX" | Phase 6 match against orders |
| ⚠ FTA opportunity | "✓ EUR.1 available — duty 0% instead of 6% from EU origin" | Phase 6 FTA check |
| ⚠ Deadline | "⚠ D/O expires Feb 20 — 3 days remaining" | Tracker timeline check |
| ⚠ Missing document | "⚠ BL received but no invoice yet for deal #XX" | Document lifecycle tracking |
| ⚠ Rate change | "⚠ Duty rate for 7326.90 changed from 6% to 8% effective Mar 1" | Brain tariff monitoring |
| 💡 Suggestion | "💡 Similar product classified as 7326.20 in pre-ruling PR-2024-XX — verify" | Brain knowledge match |

### Daily Digest Email

Morning summary for the operations team:

```
╔══════════════════════════════════════════════════════════╗
║  RCB — סיכום יומי | February 18, 2026                   ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  📋 סיווגים ממתינים להבהרה: 2                             ║
║  ┌────────┬──────────────┬──────────────────┐            ║
║  │ Deal   │ Product      │ Waiting since    │            ║
║  ├────────┼──────────────┼──────────────────┤            ║
║  │ D-0441 │ Metal boxes  │ Feb 17 (1 day)   │            ║
║  │ D-0439 │ LED panels   │ Feb 15 (3 days!) │            ║
║  └────────┴──────────────┴──────────────────┘            ║
║                                                          ║
║  🚢 מעקב משלוחים:                                        ║
║  ┌────────┬────────┬──────────┬───────┬────────┐         ║
║  │ Deal   │ Type   │ Vessel   │ ETA   │ Status │         ║
║  ├────────┼────────┼──────────┼───────┼────────┤         ║
║  │ D-0440 │ FCL    │ MSC ANNA │ Feb 19│ ⚠ 1day │         ║
║  │ D-0438 │ LCL    │ —        │ Feb 22│ ✓ OK   │         ║
║  └────────┴────────┴──────────┴───────┴────────┘         ║
║                                                          ║
║  ⚠ D-0435: D/O expires tomorrow!                        ║
║  ⚠ D-0439: Clarification pending 3 days — follow up     ║
║                                                          ║
║  📊 Yesterday: 18 emails processed, 12 classified,       ║
║     4 learned from CC, 2 pending clarification           ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
```

### Knowledge Accumulation Tracking

The system tracks and reports its own growth:

```
📊 Brain Status (monthly):
  Knowledge base: 11,753 tariff codes indexed
  Chapter notes: 99/99 complete
  Classifications in memory: 3,847
  Verified by customs: 1,234
  Expert-verified (CC): 2,103
  Self-classified: 510
  Suppliers known: 89
  Products known: 2,456
  Average classification time: 12 seconds
  Memory hit rate: 78%
  Clarification rate: 4%
  Accuracy (verified): 99.2%
```

---

## IMPLEMENTATION ROADMAP — SEQUENTIAL

**Claude Code: review against codebase, answer review questions, THEN implement.**

### Block A: Make It Run (NOW)

| Step | What |
|------|------|
| A1 | CC emails with invoices → trigger classification alongside CC learning |
| A2 | airpaport@gmail.com → extract declarations to ground truth memory |
| A3 | Clarification reply processing — detect reply to RCB question, extract answers |
| A4 | Never "unclassifiable" — always present candidates with structured question |
| A5 | Unstick 9 pending emails |
| A6 | Fix email output format — table-first, short, professional |
| A7 | Deploy to Firebase |

### Block B: Make It Read (THIS WEEK)

| Step | What |
|------|------|
| B1 | Wire smart_extractor into classification path |
| B2 | Broaden keyword_index |
| B3 | Add fuzzy/semantic search fallback |

### Block C: Make It Know (THIS WEEK)

| Step | What |
|------|------|
| C1 | Clean tariff data (35.7% garbage, ch40/64 swap) |
| C2 | Brain downloads: הראישה לפרק (all 99 chapters) |
| C3 | Brain downloads: צו יבוא חופשי — ALL appendices |
| C4 | Brain downloads: צו יצוא חופשי — ALL appendices |
| C5 | Brain downloads: צו המסגרת — complete |
| C6 | Brain downloads: הנחיות סיווג (all directives) |
| C7 | Brain downloads: פרה-רולינג database |
| C8 | Fill blank tariff descriptions + duty rates from shaarolami |

### Block D: Elimination Engine (NEXT)

| Step | What |
|------|------|
| D1 | elimination_engine.py — core tree-walking logic |
| D2 | Chapter elimination using brain's chapter notes |
| D3 | Heading elimination — specific to general |
| D4 | Rule 3 (כלל 3) — 3א, 3ב, 3ג |
| D5 | "אחרים" gate + "באופן עיקרי" test |
| D6 | AI consultation hooks at decision points |
| D7 | Devil's advocate before finalization |
| D8 | Elimination logging for Phase 8 |
| D9 | Wire into pipeline — method-first, AI-assist |

### Block E: Verification (Phases 4-6)

| Step | What |
|------|------|
| E1 | Shaarolami scraper (HE + EN) |
| E2 | Phase 4 bilingual cross-check |
| E3 | Phase 5 post-verification using brain knowledge |
| E4 | Phase 6 regulatory using downloaded FIO data |
| E5 | Proactive flagging (permits, antidumping, FTA, deadlines) |

### Block F: Model Routing (Phase 7)

| Step | What |
|------|------|
| F1 | GPT-4o primary, Claude escalation |
| F2 | Phase 7 independent cross-check |
| F3 | Disagreement protocol with ground truth lookup |

### Block G: Memory & Intelligence

| Step | What |
|------|------|
| G1 | Classification memory write-back (all channels) |
| G2 | Memory search at pipeline start |
| G3 | Auto-populate indexes from every classification |
| G4 | Clarification reply → high-confidence memory entry |
| G5 | AI reflection ("what was tricky?") |
| G6 | Confidence decay for old entries |
| G7 | Monthly self-critique (review against new rulings) |
| G8 | Knowledge accumulation dashboard |

### Block H: Communication Excellence

| Step | What |
|------|------|
| H1 | Table-first email templates (classification, tracker, digest) |
| H2 | Structured clarification questions with clickable options |
| H3 | Reply processing pipeline |
| H4 | Daily digest email |
| H5 | Proactive reminders and flags |
| H6 | Monthly brain status report |
| H7 | Hebrew RTL professional formatting |
| H8 | Bilingual output (Hebrew primary, English support) |

---

## SAFETY RULES

1. **One step at a time.** Complete and test before next.
2. **Never remove working code** — add alongside, switch when tested.
3. **Method has final say** — AI enriches, challenges, but doesn't override.
4. **AI disagreements ALWAYS logged** — alternative documented even when overridden.
5. **Blocks B+C before D** — engine needs clean data.
6. **Memory never auto-trusts 100%** — verify against current tariff.
7. **Ground truth (declarations) = high confidence (0.85, not 0.99)** — method must still verify. Customs accepts wrong codes (e.g. Goodpack steel boxes classified as 8609.0090 instead of Ch.73).
8. **CC learning is silent** — never reply, never interfere.
9. **Clarification questions are SPECIFIC** — never "need more info," always structured.
10. **Tables first, elaboration second** — in every email.
11. **Flag crucial points prominently** — permits, deadlines, rate changes.
12. **Test with real emails** after every block.
13. **Deploy only from main** — feature branches merge when tested.

---

## REVIEW QUESTIONS FOR CLAUDE CODE

Before implementing, verify against actual codebase:

1. **Routing logic**: Where does CC vs classification diverge in main.py? (Block A)
2. **airpaport@gmail.com**: Connected via Graph API? Separate polling? How? (Block A)
3. **smart_extractor.py**: What does it do? Ready to wire? (Block B)
4. **keyword_index**: What's in it? What categories missing? (Block B)
5. **Tariff data state**: Verify 35.7% garbage, chapter swap (Block C)
6. **Legal sources in Firestore**: Any chapter notes, FIO, directives already? (Block C)
7. **Email templates**: What does the current report email look like? What generates it? (Block H)
8. **Reply processing**: Any mechanism to detect replies to RCB emails? (Block A)
9. **tool_calling_engine.py**: Multi-model hooks? Current routing? (Block F)
10. **classification_memory structures**: product_index, supplier_index — usable? (Block G)
11. **cross_checker.py**: Wired? Working? (Block F)
12. **overnight brain**: 9 streams — what are they, what do they cost? (Block C)
13. **Dead code modules**: What can be wired in before writing new? (all blocks)
14. **CC + airpaport volume**: Actual email counts for learning rate validation (cost model)
15. **רשומון מכס parsing**: Can system parse declaration format? (Block A/G)
16. **Email sending**: What library/method? HTML support? RTL? Tables? (Block H)

Provide assessment and suggest adjustments based on codebase reality.

---

## SUMMARY

**The product**: A customs classification system that is accurate, professional,
comfortable to use, visually clear, bilingual, knowledge-accumulating, proactively
helpful, and cost-efficient.

**The method**: Walks the tariff tree deterministically.
**AI**: Participates at every step — reads, researches, challenges, verifies, writes.
**When uncertain**: Sends a precise, structured question. Processes the answer. Reaches 100%.
**Three + one learning channels**: CC emails, customs declarations, brain knowledge base,
and clarification replies — all feed one growing brain.

**Result**: Accuracy rises from 0% (today) to 99-100% within 6 months.
Cost drops from $135/month to $33/month within 12 months.
Year 2: ~$22/month at 99-100% accuracy.

Build order: Run (A) → Read (B) → Know (C) → Engine (D) → Verify (E) → Route (F)
→ Learn (G) → Communicate (H)

Data first. Method second. AI throughout. Clarity always.
