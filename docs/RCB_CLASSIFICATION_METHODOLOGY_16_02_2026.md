# RCB — Robot Customs Broker
## Complete Classification Methodology
### Professional Customs Broker Workflow for AI Implementation

**R.P.A.PORT LTD**
**רפא פורט בע"מ**

- **Document Version:** 1.0
- **Date:** February 16, 2026
- **Compiled from:** Sessions 3–23 + Professional Methodology Review

---

## 1. Purpose of This Document

This document defines the complete, legally-mandated classification methodology that a licensed Israeli customs broker must follow when classifying goods for import or export. This methodology is the foundation upon which RCB's AI classification pipeline must be built.

The current 6-agent pipeline does not follow this methodology. This document serves as the authoritative reference for rebuilding the classification flow so that every step, every check, and every source is properly implemented in code.

This is a companion document to RCB_SYSTEM_KNOWLEDGE (Feb 15, 2026). That document covers the technical architecture. This document covers the professional methodology.

---

## 2. Phase 0 — Case Type Identification

Before any classification begins, determine what type of customs movement this is. The case type determines which tariff applies, which procedures govern, which forms are needed, and what exemptions might exist.

### 2.1 Import or Export?

This is the first determination. Import and export use different tariff books with different code structures. The entire classification process differs based on this.

### 2.2 Movement Type

Identify which type of movement applies:

- Normal commercial import/export
- Personal effects (העברת מגורים)
- Temporary import/export (יבוא/יצוא זמני)
- Carnet ATA (temporary admission under international convention)
- Transit
- Bonded warehouse
- Re-import / Re-export
- Diplomatic shipments
- Samples
- Other special regimes

### 2.3 Applicable Procedures (נהלים)

Based on the case type, identify which Israeli Customs procedures apply:

- נוהל סיווג טובין — Goods classification procedure
- נוהל תש"ר — Customs tariff procedure
- נוהל הערכה — Valuation procedure (how to determine customs value)
- נוהל מצהרים — Declaration procedure
- Other customs procedures as applicable

### 2.4 Check פקודת המכס (Customs Ordinance)

For special cases (temporary import, bonded warehouse, etc.), consult the Customs Ordinance for specific rules, exemptions, and requirements that may override or modify the standard classification process.

---

## 3. Phase 1 — Examine the Goods

The three pillars of customs classification, examined in this order:

### 3.1 Physical Characteristics (מאפיינים פיזיים)

What is it made of? What does it look like? Material composition, dimensions, weight, form, structure. This is the PRIMARY determination — start here, not with what the importer calls it.

### 3.2 Essence / Nature (מהות)

What IS this product fundamentally? Not its brand name or marketing description, but its essential nature.

### 3.3 Use / Function (אופן שימוש)

What is it used for? What is its intended function?

### 3.4 Legal Framework Application

After examining the goods, apply:

- **Definitions from צו המסגרת (Framework Order)** — these legal definitions override common language
- **Rule 3 (כלל 3)** if the product could fall under multiple headings:
  - **3(א)** — The more specific heading wins over the general one
  - **3(ב)** — Mixtures, composite goods, and sets: classified by the component giving essential character (אופי מהותי)
  - **3(ג)** — If 3(א) and 3(ב) don't resolve it, take the last heading in numerical order
- The **"באופן עיקרי או בלעדי"** (principally or solely used for) test for parts and accessories — Section XVI Note 2 and similar notes in other sections

---

## 4. Phase 2 — Gather Information (Legally Mandated Hierarchy)

This is not optional. Israeli Customs Authority has codified this hierarchy as a legal obligation. Failure to follow it constitutes negligent classification (סיווג רשלני).

### 4.1 The Legal Hierarchy

**א׳ — Supplier Invoice Data (Primary Source):** Classification is based first on the data in the supplier invoice. This is always the starting point.

**ב׳ — Supplementary Research (Mandatory if invoice insufficient):** If the invoice only has catalog numbers, or is missing essential details for classification, the broker MUST:

- Check the supplier website — not for user manuals, but for what the product does, how it works, its specifications
- Review catalogs, brochures, MSDS, ingredient lists, product explanations
- Search the internet — search for the HS code of the product
- Check foreign tariffs — UK, USA, EU tariff classifications for the same product
- For consultation (no live shipment): use brochures, MSDS, explanations, ingredients, samples as primary classification aids

**ג׳ — Written Clarification from Importer:** ONLY after exhausting א׳ and ב׳, and ONLY if a specific point remains unresolved, the broker may request a written clarification from the importer on that specific point only.

**Last Resort — פרה-רולינג (Pre-Ruling):** If after all the above, open questions remain, the broker must apply for a pre-ruling from customs.

### 4.2 Legal Consequences of Non-Compliance

Per the Israeli Customs Authority directive:

- Skipping ב׳ and going directly to the importer = **סיווג רשלני** (negligent classification)
- Accepting verbal clarification from the importer = **סיווג רשלני**
- If classification turns out wrong, the broker is personally liable under **הסדר בר-ענישה** AND **מערכת ליקויים**
- This applies even if the importer gave wrong information, if the broker didn't exhaust ב׳ first

---

## 5. Phase 3 — Elimination Process (Tariff Tree Navigation)

### 5.1 Tariff Book Structure

The Israeli tariff has 99 chapters + discount codes (קודי הנחה) for specific cases + appendices to the customs tariff.

The book is organized from simple to complex:

- Chapter 1: Live animals (simplest)
- Later chapters: Processed food preparations (more complex)
- This principle applies at EVERY level of the hierarchy

### 5.2 Chapter Notes (הראישה לפרק)

BEFORE examining any headings within a chapter, read the chapter preamble. This legally defines:

- What IS included in this chapter
- What is NOT included (and where it goes instead)
- Special definitions that apply within this chapter

The chapter notes are the first filter. If the notes say your product is excluded from this chapter, stop and look elsewhere.

### 5.3 The Elimination Process

Within each chapter, headings and sub-headings are arranged specific to general. The elimination process is:

1. Identify candidate chapters based on the product examination (Phase 1)
2. Read chapter notes — confirm the product belongs here
3. Within the chapter, examine headings from first (most specific) to last (most general)
4. Eliminate headings that clearly don't apply, documenting WHY each is eliminated
5. Within the correct heading, examine sub-headings the same way
6. Continue eliminating until reaching the full code: XX.XX.XXXXXX/X

### 5.4 HS Code Format (Israeli)

```
XX.XX.XXXXXX/X
```

- XX = Chapter (2 digits)
- XX = Heading (2 digits)
- XXXXXX = Sub-heading (6 digits)
- /X = Check digit (1 digit)

Total: 10 digits + check digit, formatted with two dots and a slash.

Example: `01.01.300000/3` (donkeys), `03.01.199000/3` (other ornamental fish)

### 5.5 The Stopping Rule

**CRITICAL:** If you have not reached the format XX.XX.XXXXXX/X — you are NOT done. Keep eliminating. The check digit after the slash is your signal that you have arrived at a classifiable code.

### 5.6 "אחרים" (Others) — When It Is Valid

Within a heading, sub-codes are listed specific-first, with "אחרים" (Others) at the end. This means:

- If your product matches a SPECIFIC code listed before "אחרים" — use the specific code. Never jump to Others.
- If your product does NOT match any specific code, and you have eliminated every option above — then "אחרים" is the CORRECT and LEGITIMATE classification.
- "אחרים" is valid ONLY as the last code standing after full elimination.

**The trap** (documented in known failures): jumping to "אחרים" WITHOUT checking if a specific code exists. That is wrong. But arriving at "אחרים" AFTER proper elimination is correct.

---

## 6. Phase 4 — Bilingual Verification

After reaching a code through the Hebrew tariff elimination process, run the ENTIRE process again using the English tariff. This cross-verification catches errors where Hebrew descriptions may be ambiguous or where the English wording provides additional clarity.

The English tariff follows the same HS structure internationally. Comparing both ensures the classification is consistent and defensible.

---

## 7. Phase 5 — Post-Classification Verification

Even after reaching XX.XX.XXXXXX/X through elimination in both languages, the code is NOT final until verified against:

### 7.1 Israeli Sources

- הנחיות סיווג (Classification directives) from Israeli Customs
- Pre-rulings (פרה-רולינג) database
- Israeli customs decisions
- מנוע העזר (Assistance engine on customs authority website)
- Information published on the customs authority website
- Legal records and publications

### 7.2 International Sources

- UK tariff classifications and rulings
- USA tariff classifications and rulings (USITC/CBP)
- EU tariff classifications and rulings (TARIC/BTI)
- WCO (World Customs Organization) council decisions

### 7.3 Court Precedents

Check relevant Israeli court decisions that may affect classification. Known precedents include: VIVO, DENVER SANDALS, HALPERIN, and others. These legal decisions can override or clarify tariff interpretations.

---

## 8. Phase 6 — Regulatory and Commercial Checks

### 8.1 Invoice Validation

Check the invoice has all 9 required fields per Israeli regulation (תקנות תשל"ג-1972):

1. ארץ המקור (Country of Origin)
2. מקום ותאריך (Place & Date)
3. מוכר וקונה (Seller & Buyer)
4. פרטי אריזות (Package Details)
5. תיאור הטובין (Goods Description)
6. כמות (Quantity)
7. משקלים (Weights)
8. מחיר (Price)
9. תנאי מכר / Incoterms (Sale Terms)

Invoice must also comply with 3 conditions: Regulation 6 of Customs Regulations 1965, not a proforma, and signed by supplier.

### 8.2 Free Trade Agreement (FTA) Check

- EUR.1 needed? Certificate of Origin?
- Which agreement applies? (EU, Turkey, EFTA, USA, UK, Jordan, Egypt, Mercosur, etc.)
- What duty reduction is available under the applicable FTA?

### 8.3 Import/Export Orders

- צו יבוא חופשי + ALL appendices (for import)
- צו יצוא חופשי (for export)
- Ministry requirements, permits, licenses based on the HS code

---

## 9. Phase 7 — Multi-AI Cross-Check

After the classification is complete, three independent AI models verify the result:

- **Claude (Anthropic)** — independent classification verification
- **Gemini (Google)** — independent classification verification
- **ChatGPT (OpenAI)** — independent classification verification

Each AI receives the same product information and independently classifies. Disagreements are flagged for human review with explanation of each model's reasoning.

Additionally, tool-calling capabilities should be used to verify against external databases and APIs during this phase.

---

## 10. Phase 8 — Source Attribution

Every piece of information in the final classification report MUST state where it came from:

- **Tariff DB (Firestore)** — code, description, duty rates
- **Government API (צו יבוא חופשי API)** — import requirements
- **Customs authority website** — directives, publications
- **Pre-ruling reference number** — if applicable
- **Court decision reference** — if applicable
- **FTA source** — which agreement, which provision
- **Foreign tariff source** — UK/USA/EU classification reference
- **WCO decision reference** — if applicable

The user must be able to trace every claim back to its source. No unsourced statements.

---

## 11. Phase 9 — Final Output

When classification cannot reach 100% certainty, the system MUST NOT simply say "need more info". Instead:

1. Present the user with the remaining candidate codes (maximum 5)
2. Explain what distinguishes each candidate from the others
3. State exactly what information is needed to determine which code is correct
4. Formulate the specific questions that need to be asked

With the full methodology above, there should be very few cases where the system cannot provide a definitive answer or at minimum a well-reasoned shortlist with clear guidance on how to resolve the remaining ambiguity.

---

## 12. Complete Classification Flow — Summary

| Phase | Name | Actions |
|-------|------|---------|
| 0 | Case Type | Import or export? Normal commercial or special regime (temporary, carnet, personal, transit, bonded, etc.)? Which נהלים apply? Check פקודת המכס for special cases. |
| 1 | Examine Goods | Physical characteristics → Essence/nature → Use/function. Apply צו המסגרת definitions. Rule 3 if heading conflict. "באופן עיקרי או בלעדי" test for parts. |
| 2 | Gather Info | א׳: Invoice data. ב׳: Supplier website, catalogs, MSDS, brochures, internet, foreign tariffs (UK/USA/EU). ג׳: Written clarification (specific point only). Last: פרה-רולינג. |
| 3 | Elimination | Read הראישה לפרק. Eliminate chapter → heading → sub-heading. Simple to complex, specific to general. Stop only at XX.XX.XXXXXX/X. "אחרים" valid only after full elimination. |
| 4 | Bilingual Check | Repeat entire elimination using the English tariff. Cross-verify Hebrew result. |
| 5 | Post-Classification | הנחיות סיווג, pre-rulings, IL/UK/USA/EU customs decisions, WCO decisions, מנוע העזר, court precedents, legal records. |
| 6 | Regulatory | Invoice validation (9 fields). FTA check. צו יבוא/יצוא חופשי + appendices. Ministry permits and licenses. |
| 7 | Multi-AI | Claude + Gemini + ChatGPT independently verify. Tool-calling for external DB checks. Flag disagreements. |
| 8 | Source Attribution | Every claim traceable to source: tariff DB, government API, ruling, court decision, FTA provision, foreign tariff. |
| 9 | Final Output | Definitive code OR shortlist (≤5 candidates) with specific differentiators and questions to resolve ambiguity. |

---

## 13. Known Classification Failures (from System Knowledge Document)

These failures demonstrate what happens when the methodology above is NOT followed:

**Kiwi → Caviar bug:** System confused קווי (kiwi) with קוויאר (caviar). A proper Phase 3 elimination starting at Chapter 08 (fruits) would have prevented this.

**Ouzo refusal:** System said "need more info" 6 times. A proper elimination through 22.08, eliminating named spirits one by one, arrives at 22.08.90 "others" — which is the CORRECT result after elimination.

**Tires → Raw rubber:** System picked 40.01 (natural rubber) instead of 40.11 (new pneumatic tires) because of garbage data in parent_heading_desc. Data quality issue — Phase 3 requires clean data.

**No tariff rates shown:** customs_duty and purchase_tax fields exist in DB but were never extracted. Phase 6 regulatory check incomplete.

**No FIO check:** Generic ministry references instead of specific Free Import Order requirements. Phase 6 incomplete.

---

## 14. What Must Change in RCB

The current 6-agent pipeline does NOT implement this methodology. Key gaps:

### 14.1 Data Foundation (Must Fix First)

- 35.7% of tariff DB has garbage in parent_heading_desc — **CLEAN THIS**
- tariff_chapters has wrong content (chapter 40 = chapter 64 shoe data) — **FIX THIS**
- Chapter notes (הראישה לפרק) not stored — **ADD THIS**
- הנחיות סיווג not in system — **ADD THIS**
- נהלים (סיווג, תש"ר, הערכה, מצהרים) not in system — **ADD THIS**
- Pre-rulings database not in system — **ADD THIS**
- Israeli customs decisions not in system — **ADD THIS**
- English tariff not in system — **ADD THIS**
- WCO/UK/USA/EU cross-references not in system — **ADD THIS**
- פקודת המכס not in system — **ADD THIS**
- Case type identification logic doesn't exist — **BUILD THIS**

### 14.2 Classification Flow (Rebuild After Data)

- Agent 2 prompt must follow the Phase 0–9 methodology exactly
- Elimination must be documented step by step
- Bilingual verification must be implemented
