# RCB INTELLIGENCE ROUTING SPECIFICATION
# R.P.A.PORT LTD — Robot Customs Broker
# Version 1.0 — 24 February 2026

---

## WHY THIS DOCUMENT EXISTS

For months, every Claude Code session reports "data is in the system ✅" and every
test email proves the system produces garbage. The data IS there. The tools ARE there.
The system is DUMB because it has no brain — no reasoning about WHAT to search,
WHERE to look, or HOW to validate before answering.

This document defines the intelligence layer that must be embedded IN THE CODE ITSELF.
Not in prompts. Not in comments. In actual Python logic that routes every question
to the right sources and validates every answer before it leaves the system.

**CRITICAL RULE: This specification is MANDATORY for any Claude Code session working
on the RCB system. Read it before touching any code. Follow it exactly.**

---

## PART 1: THE FUNDAMENTAL PROBLEM

### What Happens Now (broken)

```
Email arrives
  → Simple keyword search across all 311 ordinance articles
  → Whatever matches best (by word count) gets sent to AI
  → AI writes something based on what it received
  → System sends it
```

### What Should Happen (this spec)

```
Email arrives
  → DOMAIN DETECTION: What area of customs is this about?
  → SOURCE ROUTING: Which specific sources answer this type of question?
  → TARGETED SEARCH: Search those specific sources with domain-aware queries
  → VALIDATION: Does the answer make sense? Is the HS code real? Is the law cited correctly?
  → COMPOSITION: AI writes answer WITH citations from validated sources
  → QUALITY CHECK: Would a licensed customs broker send this? If not, flag for human review.
  → Send
```

---

## PART 2: DOMAIN DETECTION

Every incoming email must be classified into one or more of these domains BEFORE
any search happens. This is a Python function, not an AI call.

### Domain Definitions

```python
CUSTOMS_DOMAINS = {
    "CLASSIFICATION": {
        "description": "What HS code applies to these goods?",
        "keywords_he": ["סיווג", "פרט מכס", "תעריף", "פרק", "סעיף", "HS", "קוד"],
        "keywords_en": ["classify", "classification", "HS code", "tariff", "heading"],
        "product_indicators": True,  # If email describes a product, it's classification
        "sources": ["TARIFF", "GIR_RULES", "CHAPTER_NOTES", "CLASSIFICATION_DIRECTIVES",
                     "EXTERNAL_PRODUCT_INFO"],
    },
    "VALUATION": {
        "description": "How to determine the customs value of goods?",
        "keywords_he": ["הערכה", "ערך עסקה", "שווי", "מחיר", "תשלום", "132", "133",
                         "שיטות הערכה", "ערך"],
        "keywords_en": ["valuation", "transaction value", "customs value", "price"],
        "sources": ["ORDINANCE_130_136", "VALUATION_PROCEDURE", "WTO_VALUATION"],
    },
    "IP_ENFORCEMENT": {
        "description": "Intellectual property, counterfeiting, brand protection",
        "keywords_he": ["זיוף", "מזויף", "קניין רוחני", "סימן מסחר", "עיכוב", "חשד",
                         "מותג", "העתק", "פיראטיות", "זכויות יוצרים"],
        "keywords_en": ["counterfeit", "fake", "IP", "intellectual property", "trademark",
                         "brand", "piracy", "detained", "seized"],
        "sources": ["ORDINANCE_200A_200YD", "IP_PROCEDURES", "CUSTOMS_AGENTS_LAW"],
    },
    "FTA_ORIGIN": {
        "description": "Free trade agreements, origin rules, preferential rates",
        "keywords_he": ["הסכם סחר", "מקור", "תעודת מקור", "EUR.1", "העדפה", "הנחה",
                         "אזור סחר", "FTA", "כללי מקור", "צבירה"],
        "keywords_en": ["FTA", "free trade", "origin", "preferential", "EUR.1",
                         "certificate of origin", "cumulation"],
        "sources": ["FRAMEWORK_ORDER", "FTA_AGREEMENTS", "DISCOUNT_CODES", "FTA_PROTOCOLS"],
    },
    "IMPORT_EXPORT_REQUIREMENTS": {
        "description": "What permits, licenses, approvals are needed?",
        "keywords_he": ["רישיון", "היתר", "אישור", "צו יבוא", "צו יצוא", "תוספת",
                         "משרד", "רשות", "דרישה", "הגבלה"],
        "keywords_en": ["license", "permit", "approval", "import order", "export order",
                         "restricted", "prohibited", "requirement"],
        "sources": ["FREE_IMPORT_ORDER", "FREE_EXPORT_ORDER", "REGULATORY_AUTHORITIES"],
    },
    "PROCEDURES": {
        "description": "How to file, declare, process customs operations",
        "keywords_he": ["נוהל", "תש\"ר", "מצהר", "הצהרה", "שחרור", "עמיל", "רשימון",
                         "אוצר", "מכס", "הליך"],
        "keywords_en": ["procedure", "declaration", "clearance", "broker", "filing"],
        "sources": ["ORDINANCE_PROCEDURES", "CUSTOMS_PROCEDURES", "CUSTOMS_AGENTS_LAW"],
    },
    "FORFEITURE_PENALTIES": {
        "description": "Seizure, forfeiture, fines, penalties, offenses",
        "keywords_he": ["חילוט", "קנס", "עבירה", "עונש", "תפיסה", "הברחה", "עבירת מכס"],
        "keywords_en": ["forfeiture", "seizure", "penalty", "fine", "offense", "smuggling"],
        "sources": ["ORDINANCE_190_PLUS", "PENALTIES_CHAPTER"],
    },
    "TRACKING": {
        "description": "Shipment tracking, vessel arrivals, cargo status",
        "keywords_he": ["מעקב", "אונייה", "מכולה", "הגעה", "נמל", "מטען", "שילוח"],
        "keywords_en": ["tracking", "vessel", "container", "arrival", "port", "cargo",
                         "shipment", "ETA"],
        "sources": ["MAMAN_API", "SWISSPORT_API", "PORT_SCHEDULE", "VESSEL_TRACKING"],
    },
}
```

### Detection Logic

```python
def detect_domains(email_text: str, email_subject: str) -> list[dict]:
    """
    Returns list of matching domains, sorted by confidence score.

    RULE: If the email describes a PRODUCT (goods, items, merchandise),
    CLASSIFICATION is ALWAYS included as a domain, even if the question
    is about something else. Because every customs question about specific
    goods needs to start with "what is the HS code?"

    RULE: Multiple domains can match. A question about Nike counterfeits
    is both IP_ENFORCEMENT and CLASSIFICATION.
    """
    detected = []
    text = f"{email_subject} {email_text}".lower()

    for domain_id, domain in CUSTOMS_DOMAINS.items():
        score = 0
        # Count keyword matches
        for kw in domain["keywords_he"] + domain["keywords_en"]:
            if kw.lower() in text:
                score += 10

        # Product detection bonus for CLASSIFICATION
        if domain.get("product_indicators") and _contains_product_description(text):
            score += 20

        if score > 0:
            detected.append({"domain": domain_id, "score": score,
                             "sources": domain["sources"]})

    # Sort by score descending
    detected.sort(key=lambda x: x["score"], reverse=True)

    # FALLBACK: If nothing matched, use GENERAL_CUSTOMS_QUERY
    if not detected:
        detected = [{"domain": "GENERAL", "score": 0,
                     "sources": ["ORDINANCE", "TARIFF"]}]

    return detected
```

---

## PART 3: SOURCE ROUTING — What to Search for Each Domain

### The Source Map

Each domain maps to SPECIFIC articles, collections, and tools. This is NOT a keyword
search — it's a directed lookup.

```python
SOURCE_ROUTING = {
    # ══════════════════════════════════════════════════════════
    # CLASSIFICATION — "What HS code is this?"
    # ══════════════════════════════════════════════════════════
    "TARIFF": {
        "type": "firestore",
        "collection": "tariff",
        "description": "11,753 tariff entries — the actual Israeli customs tariff",
        "usage": "Search by product description, validate HS codes exist",
        "CRITICAL": "NEVER generate an HS code from AI. ALWAYS look it up in this DB.",
    },
    "GIR_RULES": {
        "type": "in_code",
        "location": "customs_law.py",
        "articles": "GIR rules 1-6 with full text",
        "usage": "Cite which GIR rule justifies the classification",
        "content_summary": {
            "GIR1": "Classification by terms of headings and section/chapter notes",
            "GIR2a": "Incomplete/unfinished articles classified as complete if essential character",
            "GIR2b": "Mixtures and combinations — by material/substance giving essential character",
            "GIR3a": "Most specific heading preferred over general",
            "GIR3b": "Mixtures/composites — essential character test",
            "GIR3c": "Last in numerical order when 3a and 3b fail",
            "GIR4": "Most akin/similar goods",
            "GIR5": "Cases, containers, packing materials",
            "GIR6": "Sub-headings within same heading — same rules apply",
        },
    },
    "CHAPTER_NOTES": {
        "type": "in_code",
        "location": "chapter_expertise.py",
        "description": "All 22 tariff sections with chapter notes and exclusions",
        "usage": "After determining candidate chapter, check notes for inclusions/exclusions",
    },
    "CLASSIFICATION_DIRECTIVES": {
        "type": "not_yet_available",
        "blocker": "Requires browser download from gov.il",
        "priority": "HIGH",
    },
    "EXTERNAL_PRODUCT_INFO": {
        "type": "tools",
        "tools": ["wikipedia_search", "pubchem_lookup", "web_search"],
        "usage": "When classifying unfamiliar goods, research what they ARE before classifying",
    },

    # ══════════════════════════════════════════════════════════
    # VALUATION — "How to value these goods?"
    # ══════════════════════════════════════════════════════════
    "ORDINANCE_130_136": {
        "type": "in_code",
        "location": "_ordinance_data.py",
        "articles": ["130", "131", "132", "132א", "133", "134", "135", "136"],
        "usage": "Quote the specific valuation method that applies",
        "content_summary": {
            "130": "The 7 valuation methods in order of preference",
            "131": "Definitions",
            "132": "Transaction value — primary method",
            "132א": "Transaction value conditions",
            "133": "Additions to transaction value",
            "134": "Identical goods method",
            "135": "Similar goods method",
            "136": "Deductive and computed methods",
        },
    },

    # ══════════════════════════════════════════════════════════
    # IP ENFORCEMENT — "Counterfeiting, brand protection"
    # ══════════════════════════════════════════════════════════
    "ORDINANCE_200A_200YD": {
        "type": "in_code",
        "location": "_ordinance_data.py",
        "articles": ["200א", "200ב", "200ג", "200ד", "200ה", "200ו", "200ז",
                      "200ח", "200ט", "200י", "200יא", "200יב", "200יג", "200יד"],
        "usage": "The COMPLETE IP enforcement chapter in the Customs Ordinance",
        "content_summary": {
            "200א": "Definitions — בעל זכות, טובין מפרים, סימן מסחר",
            "200ב": "Request by rights holder to customs to detain suspected goods",
            "200ג": "Customs authority to detain goods even without request",
            "200ד": "Notification to rights holder when goods detained",
            "200ה": "Examination of goods by rights holder",
            "200ו": "Release of goods if no legal action taken within deadline",
            "200ז": "Destruction of infringing goods",
            "200ח": "Simplified destruction procedure for small quantities",
            "200ט": "Costs and expenses",
            "200י": "Bond/guarantee requirements",
            "200יא": "Rights holder liability for wrongful detention",
            "200יב": "Customs immunity from liability",
            "200יג": "Application to patents and designs",
            "200יד": "Regulations authority",
        },
    },

    # ══════════════════════════════════════════════════════════
    # FTA / ORIGIN — "Trade agreements, preferential rates"
    # ══════════════════════════════════════════════════════════
    "FRAMEWORK_ORDER": {
        "type": "in_code",
        "location": "_framework_order_data.py",
        "description": "33 articles of צו מסגרת — full Hebrew text",
        "usage": "Quote FTA clause text, origin rules, tariff additions",
    },
    "FTA_AGREEMENTS": {
        "type": "firestore",
        "collection": "fta_agreements",
        "description": "21 FTA entries with metadata",
        "usage": "Look up which agreement applies for a given country",
    },
    "DISCOUNT_CODES": {
        "type": "not_yet_available",
        "blocker": "Requires browser download from shaarolami",
    },

    # ══════════════════════════════════════════════════════════
    # IMPORT/EXPORT REQUIREMENTS
    # ══════════════════════════════════════════════════════════
    "FREE_IMPORT_ORDER": {
        "type": "firestore",
        "collection": "free_import_order",
        "entries": 6121,
        "usage": "Given an HS code, look up what permits/approvals are needed for import",
    },
    "FREE_EXPORT_ORDER": {
        "type": "firestore",
        "collection": "free_export_order",
        "entries": 979,
        "usage": "Given an HS code, look up what permits/approvals are needed for export",
    },

    # ══════════════════════════════════════════════════════════
    # FORFEITURE / PENALTIES
    # ══════════════════════════════════════════════════════════
    "ORDINANCE_190_PLUS": {
        "type": "in_code",
        "location": "_ordinance_data.py",
        "articles": ["190", "191", "192", "193", "194", "195", "196", "197",
                      "198", "199", "200", "204", "205", "206", "207", "208",
                      "209", "210", "211", "212", "213", "214", "215", "216",
                      "217", "218", "219", "220", "221", "222", "223", "224",
                      "225", "226", "227", "228", "229", "230", "231"],
        "usage": "Offenses, penalties, forfeiture, appeals",
    },
}
```

---

## PART 4: THE CLASSIFICATION BRAIN — How to Classify Goods

This is the most critical function in the system. A dining chair should take
30 seconds to classify, not generate an invalid code and loop forever.

### The Classification Methodology (MUST be in code)

```python
def classify_goods(product_description: str, invoice_data: dict = None) -> dict:
    """
    The Israeli Customs Classification Methodology.

    This follows the EXACT process a licensed customs broker uses:

    Phase 0: UNDERSTAND THE PRODUCT
    Phase 1: DETERMINE THE SECTION (1-22)
    Phase 2: DETERMINE THE CHAPTER (01-97)
    Phase 3: DETERMINE THE HEADING (4-digit)
    Phase 4: DETERMINE THE SUBHEADING (6-digit)
    Phase 5: DETERMINE THE ISRAELI TARIFF LINE (8-10 digit)
    Phase 6: VALIDATE — code MUST exist in tariff DB
    Phase 7: REGULATORY CHECK — what permits needed?
    Phase 8: FTA CHECK — any preferential rates available?
    Phase 9: COMPOSE OUTPUT with full legal justification
    """
```

### Phase 0: Understand the Product

```python
# BEFORE classifying, understand what the product IS.
#
# "DINING CHAIR" →
#   Material: wood/metal/plastic? (affects classification)
#   Upholstered? (affects subheading)
#   Foldable? (affects subheading)
#   For indoor/outdoor? (can affect classification)
#   With armrests? (can affect code)
#
# If the description is insufficient, ASK. Don't guess.
# A broker would call the client. The system should email back
# with specific questions.
#
# BUT — if the general heading is obvious (chair = 94.01),
# present the CANDIDATES at that heading level with what
# additional info would narrow it down.
```

### Phase 1-5: Hierarchical Classification

```python
CLASSIFICATION_LOGIC = {
    # ═══════════════════════════════════════
    # SECTION XX: FURNITURE (Chapters 94-96)
    # ═══════════════════════════════════════
    94: {
        "title": "רהיטים; מיטות, מזרנים; מנורות; שלטים מוארים; בתים טרומיים",
        "chapter_note_exclusions": [
            "Parts of general use (section XV metals, section VII plastics)",
            "Metal furniture designed for standing on floor → still 94.01-94.03",
        ],
        "headings": {
            "9401": {
                "title": "מושבים (כיסאות)",
                "covers": "Seats and chairs of all kinds, except medical (94.02)",
                "GIR_rule": "GIR1 — classified by terms of heading 94.01",
                "subheadings": {
                    # THESE MUST COME FROM THE ACTUAL TARIFF DB
                    # The system must LOOK UP valid codes, never generate them
                },
                "common_products": [
                    "dining chair", "office chair", "armchair", "sofa", "bench",
                    "כיסא", "כורסה", "ספה", "שרפרף", "כיסא אוכל",
                ],
            },
        },
    },
}
```

### Phase 6: VALIDATE (THE MOST CRITICAL PHASE)

```python
def validate_hs_code(code: str) -> dict:
    """
    ABSOLUTE RULE: Never send an HS code that doesn't exist in the tariff DB.

    This is the #1 reason the system looks dumb. It generates codes from
    AI knowledge (which may be from other countries' tariffs) and sends
    them without checking if they exist in the ISRAELI tariff.

    Returns:
        {
            "valid": True/False,
            "code": "9401.61.0000" (corrected if needed),
            "description_he": "כיסאות מרופדים, בעלי שלד עץ",
            "duty_rate": "12%",
            "candidates": [...] if invalid — nearby valid codes
        }
    """
    # Step 1: Check exact code in tariff DB
    exact_match = search_tariff_db(code)
    if exact_match:
        return {"valid": True, "code": code, **exact_match}

    # Step 2: If not found, search for nearby codes (same 4-digit heading)
    heading = code[:4]
    candidates = search_tariff_db_by_heading(heading)

    # Step 3: If heading has no entries, the HEADING is wrong, not just the subheading
    if not candidates:
        return {"valid": False, "code": code, "error": "heading_not_found",
                "message": f"No entries under heading {heading}"}

    # Step 4: Return candidates for the AI to choose from (or ask the client)
    return {"valid": False, "code": code, "error": "subheading_not_found",
            "candidates": candidates,
            "message": f"Code {code} not found. {len(candidates)} valid codes under {heading}"}
```

### ANTI-LOOP RULE

```python
# The system currently sends "תיקון סיווג" emails in a loop when it can't
# find a valid code. This MUST stop.
#
# RULE: If classification fails validation:
#   1. First attempt: Try to find valid code under same heading
#   2. Second attempt: Present ALL valid codes under that heading to the client
#   3. NEVER attempt more than 2 classification cycles for the same product
#   4. After 2 attempts, escalate to human (Doron) with what was tried
#   5. NEVER send "code not found" or "invalid code" to the CLIENT
#
# The "תיקון סיווג" email should ONLY be sent once, with the CORRECT code,
# or with a structured list of candidates asking the client to clarify.
```

---

## PART 5: THE SEARCH BRAIN — How to Search Legal Knowledge

### Principle: Search by TOPIC, Not by Keywords

```python
def search_legal_knowledge_smart(domain: str, query: str) -> list[dict]:
    """
    Instead of keyword-matching across all 311 articles,
    go DIRECTLY to the relevant articles for the detected domain.

    Example:
      domain="IP_ENFORCEMENT", query="Nike counterfeit detained"
      → Go directly to articles 200א-200יד
      → Return ALL of them (they form a complete procedure)
      → Don't search for "Nike" in the ordinance (it won't be there)

    Example:
      domain="VALUATION", query="transaction value conditions"
      → Go directly to articles 130-136
      → Return the specific article about conditions (132א)
    """
    # Step 1: Get the source routing for this domain
    sources = SOURCE_ROUTING_FOR_DOMAIN[domain]

    # Step 2: For each source, do a TARGETED retrieval
    results = []
    for source in sources:
        if source["type"] == "in_code":
            # Direct article lookup — no search needed
            articles = get_articles_by_ids(source["articles"])
            results.extend(articles)
        elif source["type"] == "firestore":
            # Structured query against specific collection
            docs = query_collection(source["collection"], query)
            results.extend(docs)
        elif source["type"] == "tools":
            # External tool calls for product research
            for tool in source["tools"]:
                tool_result = call_tool(tool, query)
                results.append(tool_result)

    return results
```

### Example: Nike Counterfeit Question — Correct Flow

```
Input: "יש לי יבואן שהביא מכולה ובה בגדים של Nike, במכס עיכבו בטענה שמדובר בזיוף"

Step 1 — DOMAIN DETECTION:
  Keywords matched: "זיוף" → IP_ENFORCEMENT (score 10)
                    "עיכוב" → IP_ENFORCEMENT (score +10)
                    "בגדים" → CLASSIFICATION (product detected, score 20)
  Result: [IP_ENFORCEMENT (20), CLASSIFICATION (20)]

Step 2 — SOURCE ROUTING:
  IP_ENFORCEMENT → ORDINANCE_200A_200YD (articles 200א-200יד)
  CLASSIFICATION → TARIFF (search "בגדים", heading 61/62)

Step 3 — TARGETED SEARCH:
  → Fetch ALL articles 200א through 200יד (the complete IP chapter)
  → Fetch tariff entries for clothing (chapters 61-62)
  → Do NOT search all 311 articles for "זיוף"

Step 4 — COMPOSITION:
  AI receives:
  - Complete text of 14 IP enforcement articles
  - Relevant tariff entries for clothing

  AI composes answer:
  - Authority to detain: סעיף 200ג (customs can detain on their own)
  - Rights holder process: סעיף 200ב + 200ד
  - Timeline: סעיף 200ו (release if no action within X days)
  - Client's options: request examination (200ה), negotiate, legal action
  - Classification note: clothing generally chapters 61-62

Step 5 — VALIDATION:
  - Are all cited articles real? ✓ (they're from the embedded data)
  - Does the answer address the actual question? ✓
  - Is there any "consult a customs broker" nonsense? ✗ REMOVE IT
```

### Example: Dining Chair — Correct Flow

```
Input: "DINING CHAIR" (with invoice/shipping docs)

Step 1 — DOMAIN DETECTION:
  Product description detected → CLASSIFICATION (score 20)

Step 2 — SOURCE ROUTING:
  CLASSIFICATION → TARIFF + GIR_RULES + CHAPTER_NOTES

Step 3 — TARGETED SEARCH:
  a) Search tariff DB for "chair" / "כיסא" / "dining" / "seat"
  b) Results: heading 9401 entries
  c) Get ALL valid codes under 9401 from tariff DB:
     - 9401.10 — Aircraft seats
     - 9401.20 — Motor vehicle seats
     - 9401.30 — Swivel seats with height adjustment
     - 9401.40 — Seats convertible to beds
     - 9401.61 — Upholstered seats with wood frame
     - 9401.69 — Other seats with wood frame
     - 9401.71 — Upholstered seats with metal frame
     - 9401.79 — Other seats with metal frame
     - 9401.80 — Other seats
     - 9401.90 — Parts
  d) GIR Rule 1 applies: classified by terms of the heading

Step 4 — DECISION:
  "DINING CHAIR" — need to know material and upholstery to pick subheading.

  Option A (if description is clear): Pick the right code
  Option B (if unclear): Present candidates 9401.61/69/71/79/80 and ask:
    "Is it upholstered? What is the frame material (wood/metal/other)?"

  BOTH options include ONLY codes that EXIST in the tariff DB.

Step 5 — VALIDATION:
  validate_hs_code("9401.61.0000") → Check tariff DB → Valid? Send.
  If invalid → try nearby codes → present candidates → NEVER loop.
```

---

## PART 6: COMPOSITION RULES — What the Output Must Include

### For Classification Emails

```
REQUIRED OUTPUT STRUCTURE:
┌─────────────────────────────────────────────────┐
│ TABLE: Classification Result                     │
│ HS Code: 9401.61.0000                           │
│ Description (HE): כיסאות מרופדים, שלד עץ         │
│ Duty Rate: 12% or applicable rate               │
│ Purchase Tax: X% if applicable                   │
│                                                  │
│ LEGAL BASIS:                                     │
│ • GIR Rule: GIR 1 — terms of heading 94.01      │
│ • Chapter Note: Section XX Note 2 [if relevant]  │
│                                                  │
│ FTA OPTIONS (if origin country known):           │
│ • EU: 0% under Israel-EU FTA                    │
│ • Turkey: 0% under Israel-Turkey FTA             │
│                                                  │
│ IMPORT REQUIREMENTS (from צו יבוא):              │
│ • [Any permits/standards required for this code]  │
│                                                  │
│ CLARIFICATION NEEDED (if applicable):            │
│ • Is the chair upholstered?                      │
│ • Frame material: wood, metal, or other?         │
│ These details affect the exact subheading.        │
│ Candidates: 9401.61, 9401.69, 9401.71, 9401.79  │
└─────────────────────────────────────────────────┘
```

### For Legal/Knowledge Queries

```
REQUIRED OUTPUT STRUCTURE:
┌─────────────────────────────────────────────────┐
│ ANSWER (in Hebrew, RTL):                         │
│ Direct answer to the question.                   │
│                                                  │
│ LEGAL CITATION:                                  │
│ סעיף XXX לפקודת המכס:                            │
│ "actual quoted text from the law"                │
│                                                  │
│ EXPLANATION:                                     │
│ What this means in practice.                     │
│                                                  │
│ RELATED PROVISIONS (if relevant):                │
│ • סעיף YYY — related topic                      │
│ • נוהל ZZZ — relevant procedure                  │
│                                                  │
│ PRACTICAL GUIDANCE:                              │
│ What the client should actually DO.              │
│ (NEVER "consult a customs broker" — WE ARE ONE)  │
└─────────────────────────────────────────────────┘
```

### ABSOLUTE COMPOSITION RULES

```python
COMPOSITION_RULES = {
    "NEVER_SAY": [
        "מומלץ לפנות לעמיל מכס",         # WE ARE the customs broker
        "מומלץ להתייעץ עם סוכן מכס",      # Same thing
        "consult a customs broker",        # We ARE one
        "I'm not sure",                     # Don't send if not sure
        "unclassifiable",                   # ALWAYS present candidates
        "Code not found",                   # Find valid alternatives
        "לא ניתן לסווג",                    # Always present options
    ],
    "ALWAYS_DO": [
        "Quote actual law text when answering legal questions",
        "Validate HS codes exist in Israeli tariff before sending",
        "Present candidate codes when exact classification unclear",
        "Include duty rate from tariff DB",
        "Include FTA options if origin country is known",
        "Include import/export requirements for the classified code",
        "Write in Hebrew RTL for Hebrew-speaking clients",
        "Tables first, then explanation",
        "Keep it professional and concise",
    ],
    "ESCALATION": [
        "If confidence < 70%, present candidates with clarification questions",
        "If classification attempts > 2 for same product, escalate to Doron",
        "If legal question references law not in our system, say so honestly",
        "NEVER loop on the same classification — present what you have and ask",
    ],
}
```

---

## PART 7: VALIDATION LAYER — Before Anything Gets Sent

```python
def validate_before_send(email_draft: dict) -> dict:
    """
    EVERY outgoing email passes through this validation.

    Returns: {"approved": True/False, "issues": [...], "fixed_draft": {...}}
    """
    issues = []

    # 1. HS CODE VALIDATION
    hs_codes = extract_hs_codes(email_draft["body"])
    for code in hs_codes:
        if not tariff_db_has_code(code):
            issues.append(f"BLOCKING: HS code {code} does not exist in Israeli tariff")

    # 2. BANNED PHRASES
    for phrase in COMPOSITION_RULES["NEVER_SAY"]:
        if phrase in email_draft["body"]:
            issues.append(f"BLOCKING: Contains banned phrase: '{phrase}'")

    # 3. LOOP DETECTION
    if is_repeat_classification(email_draft):
        issues.append("BLOCKING: This is a repeat classification attempt. Escalate.")

    # 4. EMPTY/GENERIC SUBJECT
    if not email_draft["subject"] or email_draft["subject"].strip() == "Re:":
        issues.append("FIX: Empty subject — generate meaningful subject")

    # 5. LAW CITATION CHECK (for legal queries)
    if email_draft.get("domain") in ["VALUATION", "IP_ENFORCEMENT", "PROCEDURES"]:
        if "סעיף" not in email_draft["body"]:
            issues.append("WARNING: Legal query response has no law citation")

    # 6. NO BLOCKING ISSUES → approve
    blocking = [i for i in issues if i.startswith("BLOCKING")]
    if blocking:
        return {"approved": False, "issues": issues}

    return {"approved": True, "issues": issues, "fixed_draft": email_draft}
```

---

## PART 8: ANTI-PATTERNS — What the System Must STOP Doing

### Anti-Pattern 1: Generating HS Codes from AI Memory
```
WRONG: AI says "dining chair is 9401.60" (from US/EU tariff knowledge)
RIGHT: Search Israeli tariff DB for heading 9401 → get valid codes → pick/present
```

### Anti-Pattern 2: Flat Keyword Search for Legal Questions
```
WRONG: Search all 311 articles for "זיוף" → get article 204 (חילוט, word match)
RIGHT: Detect IP_ENFORCEMENT domain → go directly to articles 200א-200יד
```

### Anti-Pattern 3: "Consult a Customs Broker"
```
WRONG: "מומלץ לפנות לעמיל מכס מקצועי"
RIGHT: Give the actual legal answer with citations. We ARE the broker.
```

### Anti-Pattern 4: Classification Loops
```
WRONG: Classify → invalid code → send correction → classify again → invalid → loop
RIGHT: Classify → validate → if invalid, present valid candidates → ask client → DONE
```

### Anti-Pattern 5: Answering from AI Training Data
```
WRONG: AI writes about customs valuation from its training data
RIGHT: Fetch articles 130-136 → inject full Hebrew text → AI writes WITH citations
```

### Anti-Pattern 6: Sending Empty or Generic Emails
```
WRONG: "Re: " (empty subject, generic body)
RIGHT: "RCB | סיווג: DINING CHAIR — כיסא אוכל — 9401.XX" (descriptive, professional)
```

---

## PART 9: IMPLEMENTATION PRIORITY

### Phase 1 — Stop the Bleeding (implement FIRST)

1. **HS Code Validation Gate** — No email goes out with an invalid HS code. EVER.
   - Add `validate_hs_code()` call before every classification email send
   - If code not in tariff DB, search for candidates under same heading
   - If no candidates, search broader (same chapter)
   - Present candidates to client, don't loop

2. **Classification Loop Breaker** — Track classification attempts per product
   - Firestore: `classification_attempts/{email_thread_id}`
   - Max 2 attempts per product
   - After 2, escalate to Doron with summary of what was tried

3. **Banned Phrase Filter** — Remove "consult a broker" from all outputs
   - Simple string check in composition step
   - Replace with actual guidance

### Phase 2 — Add Intelligence

4. **Domain Detection** — Implement the domain detector
   - Pure Python, no AI call needed
   - Keyword matching + product detection
   - Returns sorted list of domains

5. **Source Routing** — For each domain, go directly to relevant articles
   - IP questions → articles 200א-200יד
   - Valuation → articles 130-136
   - FTA → framework order + FTA agreements
   - This replaces the flat keyword search for legal questions

6. **Targeted Article Retrieval** — Fetch article groups by ID, not by search
   - New function: `get_articles_by_ids(["200א", "200ב", ...])`
   - Returns full Hebrew text for each
   - Injects into AI prompt as structured context

### Phase 3 — Full Integration

7. **Classification with Legal Basis** — Cite GIR rules and chapter notes
8. **Automatic Regulatory Check** — After classification, check צו יבוא/יצוא
9. **FTA Integration** — After classification, check applicable FTAs
10. **Cross-Reference Engine** — Combine multiple sources per query

---

## PART 10: FOR CLAUDE CODE SESSIONS

### Rules for Every Session

1. **READ THIS DOCUMENT FIRST** — before touching any code
2. **READ CLAUDE.md** — for system architecture
3. **RUN TESTS FIRST** — `python -m pytest tests/ -x -q`
4. **DO NOT DESTROY** — only ADD and IMPROVE
5. **VALIDATE** — every classification must check tariff DB
6. **TEST END-TO-END** — don't just test functions in isolation

### The Test That Matters

Send these test emails after any change:

```
Test 1 (Classification): "DINING CHAIR"
Expected: Valid HS code under 9401 with candidates if unclear

Test 2 (Legal - IP): "עיכבו מכולה בטענת זיוף"
Expected: Citations from articles 200א-200יד, complete procedure

Test 3 (Legal - Valuation): "ערך עסקה לפי סעיף 132"
Expected: Full quote of סעיף 132(א) from the ordinance

Test 4 (Classification + Regulatory): "יבוא תרופות מסין"
Expected: HS code under chapter 30 + import requirements from צו יבוא

Test 5 (FTA): "מה שיעור המכס על יבוא רכב מגרמניה"
Expected: Tariff rate + EU FTA preferential rate
```

### What to Report in Handoff

Every session handoff MUST include:
- Which test emails were sent and what the system replied
- Whether the reply was correct, partially correct, or wrong
- What was changed and why
- What the next session should focus on

---

*RCB Intelligence Routing Specification v1.0*
*R.P.A.PORT LTD — 24 February 2026*
*This document must be committed to the repo and read by every Claude Code session.*
