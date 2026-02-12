# RCB MASTER PLAN — Session 17
## February 12, 2026
## THIS IS THE ONLY DOCUMENT. All previous session docs are superseded.

---

## WHAT WAS DONE TODAY

### Phase 0: Document Extraction ✅ DEPLOYED
- 300 DPI OCR (was 150)
- Image preprocessing (contrast, sharpen)
- Smart quality threshold (not just len > 50)
- Better table extraction with structure tags
- Hebrew text cleanup
- Structure tagging (invoice#, HS codes, BL, countries, amounts)
- Excel, Word, email, URL extraction added
- Files changed: rcb_helpers.py, requirements.txt

### Phase 1: Librarian Index ✅ DONE
- One-time rebuild: 0 → 12,595 documents indexed
- smart_search() now hits index first

### Phase 2: Learning Wired ✅ DEPLOYED
- After every classification: stores HS code + description in classification_knowledge
- After every email: stores supplier/product info in knowledge_base
- File changed: classification_agents.py

### Phase 3: Real Enrichment Scheduler ✅ DEPLOYED
- Replaced dummy code with real enrichment
- Tags completed downloads, runs 23 enrichment task types, logs stats
- File changed: main.py

### Phase 2+3 Test Result ✅ CONFIRMED
- Test email processed successfully
- Logs showed: "Learned: 1 items, 0 new suppliers" + "Enrichment: learned from classification"
- System is learning from every email now

---

## WHAT NEEDS TO BE DONE NEXT

### The Problem
The system reads documents (improved today) but doesn't THINK like a customs broker.
It sends everything to AI and trusts whatever comes back.
A 22-year professional cross-checks everything with all available sources before answering.
That's what we're building.

---

## THE CLASSIFICATION FLOW — TARGET STATE

```
EMAIL WITH ATTACHMENTS
    |
    v
STEP 1: READ EVERYTHING
    Read PDFs, Excel, Word, images, email body, URLs
    Extract: products, origin, values, quantities, shipping details, document types
    |
    v
STEP 2: OWN KNOWLEDGE FIRST (no AI, no cost)
    Search classification_knowledge for similar past items
    Apply classification_rules (keyword patterns)
    Check tariff DB for matching descriptions
    Check past corrections
    -> Output: candidate HS codes with confidence
    |
    v
STEP 3: AI CLASSIFICATION (with context)
    Send to Claude Sonnet WITH own knowledge candidates
    "Here's what I think, confirm or correct"
    If low confidence: also ask Gemini + ChatGPT
    Cross-check all results
    -> Output: HS code + confidence
    |
    v
STEP 4: VERIFY AGAINST OFFICIAL SOURCES (the real check)
    A. Query Free Import Order API (apps.economy.gov.il/Apps/FreeImport/)
       -> License needed? Which ministry? Which documents?
    B. Validate HS code in official customs tariff (shaarolami)
       -> Code exists? Duty rate? Purchase tax?
    C. Check FTA eligibility
       -> FTA with origin country? Preferential rate? Origin proof needed?
    -> Output: verified HS code + official requirements
    |
    v
STEP 5: RESEARCH MINISTRY-SPECIFIC REQUIREMENTS
    Based on HS chapter, go to the RIGHT ministry website:
    - Vehicles (87) -> Ministry of Transport
    - Food (02-22) -> Ministry of Health + Ministry of Agriculture
    - Electronics (85) -> Ministry of Communications + SII
    - Chemicals (28-29) -> Ministry of Environment
    - Medical (90) -> MOH Medical Devices
    - Pharmaceuticals (30) -> MOH Pharmaceutical Division
    - Toys (95) -> SII
    - Textiles (50-63) -> SII
    - Arms (93) -> Ministry of Defense
    - Diamonds (71) -> Diamond Controller
    - etc. (full mapping in this document below)
    Search, download, read, extract specific requirements
    -> Output: complete regulatory requirements
    |
    v
STEP 6: VALIDATE DOCUMENTS
    Compare what's in the email vs what's required:
    - Commercial invoice -- present
    - Packing list -- present
    - EUR.1 -- missing (needed for FTA)
    - Veterinary certificate -- missing (required for ch.02)
    -> Output: document gap analysis with legal basis
    |
    v
STEP 7: ANSWER OR ASK SMART QUESTIONS
    IF complete -> 100% answer with:
      - Classification with HS code
      - Duty rate (normal + preferential)
      - Purchase tax if applicable
      - All regulatory requirements with ministry names
      - Missing documents with legal basis
      - FTA recommendation
      - Risk assessment

    IF ambiguous -> Smart clarification that shows understanding:
      "This could be 7604.29 (aluminum profiles, 6% duty) or
       7610.10 (structural parts, 0% with EUR.1 from Turkey).
       Are these extruded profiles or assembled structural parts?"
    |
    v
STEP 8: LEARN & CACHE EVERYTHING
    Store: classification, official API results, ministry findings,
    duty rates, supplier patterns, document patterns
    Next time similar item -> skip research, use cache
    If corrected -> store correction with HIGH weight
```

---

## MINISTRY-SPECIFIC SOURCE MAP

### When cargo involves these chapters, research these specific sources:

| HS Chapters | Cargo | Go To | URL |
|---|---|---|---|
| 01 | Live animals | MOA + Veterinary Services | gov.il/he/departments/Units/veterinary_services |
| 02-05 | Meat, fish, dairy | MOH + MOA + Chief Rabbinate | gov.il/he/departments/ministry_of_health |
| 06-14 | Plants, vegetables, fruits | MOA + PPIS (Plant Protection) | gov.il/he/departments/Units/ppis |
| 15-22 | Food, beverages | MOH (food labeling, health cert) | gov.il/he/departments/ministry_of_health |
| 23 | Animal feed | MOA | gov.il/he/departments/ministry_of_agriculture |
| 24 | Tobacco | MOH (special license + health warnings) | gov.il/he/departments/ministry_of_health |
| 25-27 | Minerals, fuels | Ministry of Energy + Environment | gov.il/he/departments/ministry_of_energy |
| 28-29, 38 | Chemicals | Ministry of Environment + Economy | gov.il/he/departments/ministry_of_environmental_protection |
| 30 | Pharmaceuticals | MOH Pharmaceutical Division | gov.il/he/departments/Units/pharmacy_department |
| 31 | Fertilizers | MOA | gov.il/he/departments/ministry_of_agriculture |
| 33 | Cosmetics | MOH | gov.il/he/departments/ministry_of_health |
| 36 | Explosives | Ministry of Defense + Police | gov.il/he/departments/ministry_of_defense |
| 39-40 | Plastics, rubber | SII (consumer products) | sii.org.il |
| 44-46 | Wood | PPIS (ISPM 15) | gov.il/he/departments/Units/ppis |
| 50-63 | Textiles, clothing | SII (labeling, children's safety) | sii.org.il |
| 64-67 | Footwear | SII | sii.org.il |
| 68-70 | Stone, ceramics, glass | SII (safety glass, construction) | sii.org.il |
| 71 | Diamonds, precious | Diamond Controller | Israel Diamond Exchange |
| 72-76 | Metals | SII (construction steel/aluminum) | sii.org.il |
| 84 | Machinery | SII (consumer appliances) + Energy labels | sii.org.il |
| 85 | Electronics, telecom | MOC (type approval) + SII (electrical safety) | gov.il/he/departments/ministry_of_communications |
| 87 | Vehicles | MOT + Environment (emissions) + SII | gov.il/he/departments/ministry_of_transport_and_road_safety |
| 88 | Aircraft, drones | Civil Aviation Authority | gov.il/he/departments/civil_aviation_authority |
| 89 | Ships | Shipping Authority | gov.il/he/departments/Units/shipping_and_ports_authority |
| 90 | Medical devices | MOH Medical Devices (AMAR) | gov.il/he/departments/Units/medical_devices |
| 93 | Arms | Ministry of Defense SIBAT + Police | gov.il/he/departments/Units/sibat |
| 95 | Toys | SII (toy safety SI 562) | sii.org.il |
| 97 | Antiques | Israel Antiquities Authority | gov.il/he/departments/israel_antiquities_authority |
| Various | Endangered species | Nature and Parks Authority (CITES) | gov.il/he/departments/nature_and_parks_authority |

---

## CORE OFFICIAL SOURCES (every classification)

| Source | URL | Purpose |
|---|---|---|
| Free Import Order API | https://apps.economy.gov.il/Apps/FreeImport/ | Per HS code: license/approval requirements |
| Free Import Order legal text | https://www.gov.il/he/pages/free_import_order | Full legal text + all amendments |
| Free Export Order | https://www.gov.il/he/pages/free_export_order | Export requirements |
| Customs Tariff Files | https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb/he/CustomsBook/Home/LinkReports | Official tariff PDFs (sections I-XXII) |
| Customs Book portal | shaarolami customs book | Tariff + purchase tax, autonomous import, export classification |
| FTA Agreements | https://www.gov.il/he/departments/dynamiccollectors/bilateral-agreements-search | 21 FTA agreements |

---

## BASELINE KNOWLEDGE (load NOW as starting cache)

Three JSON files ready to import to Firestore:
1. **fta_agreements.json** — 21 agreements with country codes, origin proof requirements
2. **regulatory_requirements.json** — HS chapter -> ministry mapping (approximate, will be verified against Free Import API over time)
3. **classification_rules.json** — 15 keyword patterns + 11 GIR principles

Import script: **import_knowledge.py**

These are APPROXIMATIONS from training data. The system will VERIFY and CORRECT them against official sources over time. Every verification result gets cached, replacing the approximation with official data.

---

## IMPLEMENTATION ORDER

| Phase | What | Priority | Status |
|---|---|---|---|
| 0 | Document extraction improvements | Done | ✅ Deployed |
| 1 | Librarian index rebuild | Done | ✅ 12,595 docs |
| 2 | Learning wired into classification | Done | ✅ Deployed |
| 3 | Real enrichment scheduler | Done | ✅ Deployed |
| A | Load baseline knowledge JSONs | NOW | Import to Firestore |
| B | Free Import API integration | NEXT | Reverse-engineer API, build query function |
| C | Ministry routing logic | NEXT | HS chapter -> ministry URL -> research |
| D | Web research capability | NEXT | PC Agent + HTTP + Gemini analysis |
| E | Smart question engine | NEXT | Elimination-based questions with HS codes + duty rates |
| F | Verification loop | NEXT | Every classification verified, cached, learned |

---

## LATER TASKS (not priority now)

1. Merge 3 emails into 1 threaded response
2. Fix HS code validation format (exact match -> fuzzy match)
3. Email threading (In-Reply-To headers)
4. Tracker integration (need tracker.py from Doron)
5. Gemini/Claude connection error retry logic
6. Invoice score validation review
7. Pupil devil's advocate agent (need pupil_v05_final.py from Doron)

---

## AI MODEL USAGE

| Model | Use For | When |
|---|---|---|
| Gemini Flash | 90% of work: extraction, regulatory analysis, research, synthesis | Default |
| Claude Sonnet 4.5 | Core HS classification (Agent 2) | Agent 2 only |
| ChatGPT | Cross-check low-confidence classifications | When confidence < threshold |
| None (own logic) | Tariff lookup, FTA lookup, duty calculation, document validation, ministry routing | Always first |

---

## SUCCESS = WHEN THIS HAPPENS

- "לא אומת" never appears on straightforward classifications
- Every report includes verified duty rate from official tariff
- Every report checks Free Import Order for license requirements
- Ministry-specific requirements researched based on cargo type
- Missing documents identified with legal basis cited
- FTA eligibility checked with correct origin proof requirements
- Clarification questions reference specific HS codes and duty implications
- Knowledge base grows with every classification
- AI costs decrease over time as cache grows
- System works like a 22-year customs broker, not a chatbot
