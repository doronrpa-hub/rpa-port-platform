"""
customs_law.py — The broker's brain.

Pure Python constants encoding the complete Israeli customs classification
methodology, GIR rules, tariff structure, and known failures.

No DB. No network. No function calls to Firestore.
This knowledge exists without any external call.

Source documents:
  - RCB_CLASSIFICATION_METHODOLOGY_1602_1.docx (Phases 0-9)
  - RCB_SYSTEM_KNOWLEDGE_ADDENDUM_S23_1602.docx (Sections 23-28)
  - Israeli Customs Tariff (shaarolami.customs.mof.gov.il)
  - צו המסגרת (Framework Order)
  - GIR / כללים פרשניים כלליים
"""

from lib.chapter_expertise import SEED_EXPERTISE, get_section_for_chapter

# ============================================================================
# BLOCK 0 — TERMINOLOGY (CORRECT HEBREW CUSTOMS TERMS)
# ============================================================================
# Source: פקודת המכס (Customs Ordinance), פרק אחד עשר — סוכנים
# The Israeli customs profession uses ONLY these terms:
#   עמיל מכס = customs broker (the person who holds the license)
#   סוכן מכס = customs agent (synonym, used in the Customs Ordinance)
# NEVER use: מתווך מכס (wrong — מתווך means "mediator/middleman", not a legal term)

CORRECT_TERMS = {
    "customs_broker": "עמיל מכס",
    "customs_agent": "סוכן מכס",
}

WRONG_TERMS = {
    "מתווך מכס": "עמיל מכס",       # מתווך = mediator, NOT a customs term
    "מתווך מכס מוסמך": "עמיל מכס מוסמך",
    "מתווכי מכס": "עמילי מכס",      # plural
}

# ============================================================================
# BLOCK 1 — CLASSIFICATION_METHODOLOGY (Phases 0-9)
# ============================================================================

CLASSIFICATION_METHODOLOGY = {
    0: {
        "name": "Case Type Identification",
        "name_he": "זיהוי סוג התיק",
        "description": "Before ANY classification begins, determine the customs movement type.",
        "steps": [
            {
                "id": "0.1",
                "action": "Determine Import or Export",
                "detail": "Import and export use DIFFERENT tariff books with different code structures. The entire classification process differs.",
            },
            {
                "id": "0.2",
                "action": "Identify movement type",
                "detail": "Normal commercial, personal effects (העברת מגורים), temporary import/export (יבוא/יצוא זמני), Carnet ATA, transit, bonded warehouse, re-import/re-export, diplomatic, samples, other special regimes.",
            },
            {
                "id": "0.3",
                "action": "Identify applicable procedures (נהלים)",
                "detail": "נוהל סיווג טובין (classification), נוהל תש\"ר (tariff), נוהל הערכה (valuation), נוהל מצהרים (declaration), and any other applicable procedures.",
            },
            {
                "id": "0.4",
                "action": "Check פקודת המכס (Customs Ordinance)",
                "detail": "For special cases (temporary import, bonded warehouse, etc.), consult the Customs Ordinance for specific rules, exemptions, and requirements.",
            },
        ],
    },
    1: {
        "name": "Examine the Goods",
        "name_he": "בחינת הטובין",
        "description": "Three pillars of customs classification, examined IN THIS ORDER.",
        "steps": [
            {
                "id": "1.1",
                "action": "Physical Characteristics (מאפיינים פיזיים) — FIRST",
                "detail": "Material composition, dimensions, weight, form, structure. This is the PRIMARY determination. Start here, not with what the importer calls it.",
            },
            {
                "id": "1.2",
                "action": "Essence / Nature (מהות) — SECOND",
                "detail": "What IS this product fundamentally? Not its brand name or marketing description, but its essential nature.",
            },
            {
                "id": "1.3",
                "action": "Use / Function (אופן שימוש) — THIRD",
                "detail": "What is it used for? What is its intended function?",
            },
            {
                "id": "1.4",
                "action": "Apply צו המסגרת (Framework Order) definitions",
                "detail": "Legal definitions from the Framework Order OVERRIDE common language. Check if the product matches any legal definition.",
            },
            {
                "id": "1.5",
                "action": "Apply Rule 3 (כלל 3) if multiple headings",
                "detail": "3(א): The more SPECIFIC heading wins over the general one. "
                          "3(ב): Mixtures, composite goods, sets — classified by the component giving ESSENTIAL CHARACTER (אופי מהותי). "
                          "3(ג): If 3(א) and 3(ב) don't resolve it, take the LAST heading in numerical order.",
            },
            {
                "id": "1.6",
                "action": "Apply 'באופן עיקרי או בלעדי' test",
                "detail": "For parts and accessories: the 'principally or solely used for' test. See Section XVI Note 2 and similar notes in other sections.",
            },
        ],
    },
    2: {
        "name": "Gather Information (Legally Mandated Hierarchy)",
        "name_he": "איסוף מידע (היררכיה חוקית מחייבת)",
        "description": "Israeli Customs Authority directive — this hierarchy is a LEGAL OBLIGATION. Failure to follow it = סיווג רשלני.",
        "steps": [
            {
                "id": "2.א",
                "action": "Supplier Invoice Data (Primary Source)",
                "detail": "Classification is based FIRST on the data in the supplier invoice. This is always the starting point.",
            },
            {
                "id": "2.ב",
                "action": "Supplementary Research (MANDATORY if invoice insufficient)",
                "detail": "Supplier website (what it does, specs — NOT user manuals), catalogs, brochures, MSDS, ingredient lists, internet search for HS code, foreign tariffs (UK/USA/EU). For consultations: brochures, MSDS, explanations, ingredients as primary aids.",
            },
            {
                "id": "2.ג",
                "action": "Written Clarification from Importer",
                "detail": "ONLY after exhausting א+ב. ONLY on a specific unresolved point. ONLY in writing. Never verbal.",
            },
            {
                "id": "2.last",
                "action": "פרה-רולינג (Pre-Ruling)",
                "detail": "Last resort. If after all the above, open questions remain, apply for a pre-ruling from customs authority.",
            },
        ],
        "legal_warning": "Skipping ב and going directly to the importer = סיווג רשלני (negligent classification). "
                         "Broker PERSONALLY liable under הסדר בר-ענישה AND מערכת ליקויים. "
                         "This applies even if the importer gave wrong information, if the broker didn't exhaust ב first.",
    },
    3: {
        "name": "Elimination Process (Tariff Tree Navigation)",
        "name_he": "תהליך אלימינציה (ניווט בעץ התעריף)",
        "description": "Read הראישה FIRST. Stop ONLY at XX.XX.XXXXXX/X. אחרים valid ONLY after full elimination.",
        "steps": [
            {
                "id": "3.1",
                "action": "Read chapter preamble (הראישה לפרק) FIRST",
                "detail": "BEFORE examining any headings. The preamble legally defines what IS included, what is NOT included, and special definitions within the chapter. If notes say product is excluded — STOP and look elsewhere.",
            },
            {
                "id": "3.2",
                "action": "Identify candidate chapters from Phase 1 examination",
                "detail": "Based on physical characteristics, essence, and function.",
            },
            {
                "id": "3.3",
                "action": "Eliminate heading by heading within chapter",
                "detail": "Headings arranged specific to general. Examine from first (most specific) to last (most general). DOCUMENT why each heading is eliminated.",
            },
            {
                "id": "3.4",
                "action": "Eliminate sub-heading by sub-heading",
                "detail": "Within the correct heading, same process. Continue until reaching full code: XX.XX.XXXXXX/X (10 digits + check digit after slash).",
            },
            {
                "id": "3.5",
                "action": "Stopping rule",
                "detail": "If you have NOT reached XX.XX.XXXXXX/X — you are NOT done. The check digit after the slash is the signal that you have arrived at a classifiable code.",
            },
            {
                "id": "3.6",
                "action": "אחרים (Others) gate",
                "detail": "If product matches a SPECIFIC code listed before אחרים — use the specific code. NEVER jump to Others. "
                          "אחרים is valid ONLY as the last code standing after full elimination of every specific code above it.",
            },
        ],
    },
    4: {
        "name": "Bilingual Verification",
        "name_he": "אימות דו-לשוני",
        "description": "Run the ENTIRE elimination process again using the ENGLISH tariff. Cross-verify the Hebrew result.",
        "steps": [
            {
                "id": "4.1",
                "action": "Repeat elimination in English tariff",
                "detail": "The English tariff follows the same HS structure internationally. English wording often provides additional clarity where Hebrew may be ambiguous.",
            },
            {
                "id": "4.2",
                "action": "Cross-verify results",
                "detail": "If Hebrew and English eliminations reach different codes — investigate the discrepancy before proceeding.",
            },
        ],
    },
    5: {
        "name": "Post-Classification Verification",
        "name_he": "אימות לאחר סיווג",
        "description": "Code is NOT final until verified against 9 source categories.",
        "sources": [
            "הנחיות סיווג (Classification directives) from Israeli Customs",
            "פרה-רולינג (Pre-rulings) database",
            "Israeli customs decisions",
            "מנוע העזר (Assistance engine on customs authority website)",
            "Customs authority website publications",
            "UK tariff classifications and rulings",
            "USA tariff classifications and rulings (USITC/CBP)",
            "EU tariff classifications and rulings (TARIC/BTI)",
            "WCO council decisions and court precedents (VIVO, DENVER SANDALS, HALPERIN, etc.)",
        ],
    },
    6: {
        "name": "Regulatory and Commercial Checks",
        "name_he": "בדיקות רגולטוריות ומסחריות",
        "description": "Invoice validation, FTA, and import/export order checks.",
        "invoice_fields": [
            "ארץ המקור (Country of Origin)",
            "מקום ותאריך (Place & Date)",
            "מוכר וקונה (Seller & Buyer)",
            "פרטי אריזות (Package Details)",
            "תיאור הטובין (Goods Description)",
            "כמות (Quantity)",
            "משקלים (Weights)",
            "מחיר (Price)",
            "תנאי מכר / Incoterms (Sale Terms)",
        ],
        "invoice_conditions": [
            "Regulation 6 of Customs Regulations 1965",
            "Not a proforma invoice",
            "Signed by supplier",
        ],
        "fta_check": "EUR.1 needed? Certificate of Origin? Which agreement? (EU, Turkey, EFTA, USA, UK, Jordan, Egypt, Mercosur, etc.) What duty reduction?",
        "import_orders": "צו יבוא חופשי + ALL appendices (import). צו יצוא חופשי (export). Ministry requirements, permits, licenses per HS code.",
    },
    7: {
        "name": "Multi-AI Cross-Check",
        "name_he": "אימות צולב רב-מודלי",
        "description": "Three independent AI models verify the classification result.",
        "models": ["Claude (Anthropic)", "Gemini (Google)", "ChatGPT (OpenAI)"],
        "process": "Each AI receives the same product information and independently classifies. Disagreements flagged for human review with explanation of each model's reasoning.",
    },
    8: {
        "name": "Source Attribution",
        "name_he": "ייחוס מקורות",
        "description": "Every piece of information MUST state where it came from. No unsourced statements.",
        "required_sources": [
            "Tariff DB (Firestore) — code, description, duty rates",
            "Government API (צו יבוא חופשי) — import requirements",
            "Customs authority website — directives, publications",
            "Pre-ruling reference number — if applicable",
            "Court decision reference — if applicable",
            "FTA source — which agreement, which provision",
            "Foreign tariff source — UK/USA/EU classification reference",
            "WCO decision reference — if applicable",
        ],
    },
    9: {
        "name": "Final Output",
        "name_he": "פלט סופי",
        "description": "Never just say 'need more info'. Present candidates with specific questions.",
        "rules": [
            "Present remaining candidate codes (maximum 5)",
            "Explain what distinguishes each candidate from the others",
            "State exactly what information is needed to determine the correct code",
            "Formulate specific questions that need to be asked",
        ],
    },
}

# ============================================================================
# BLOCK 2 — TARIFF_STRUCTURE (Sections I-XXII with supplements)
# ============================================================================

TARIFF_SECTIONS = {
    "I": {"chapters": (1, 5), "name_en": "Live Animals; Animal Products"},
    "II": {"chapters": (6, 14), "name_en": "Vegetable Products"},
    "III": {"chapters": (15, 15), "name_en": "Animal or Vegetable Fats and Oils"},
    "IV": {"chapters": (16, 24), "name_en": "Prepared Foodstuffs; Beverages; Tobacco"},
    "V": {"chapters": (25, 27), "name_en": "Mineral Products"},
    "VI": {"chapters": (28, 38), "name_en": "Products of Chemical or Allied Industries"},
    "VII": {"chapters": (39, 40), "name_en": "Plastics; Rubber"},
    "VIII": {"chapters": (41, 43), "name_en": "Hides, Skins, Leather, Furskins"},
    "IX": {"chapters": (44, 46), "name_en": "Wood; Cork; Basketware"},
    "X": {"chapters": (47, 49), "name_en": "Paper and Paperboard"},
    "XI": {"chapters": (50, 63), "name_en": "Textiles and Textile Articles"},
    "XII": {"chapters": (64, 67), "name_en": "Footwear; Headgear; Umbrellas"},
    "XIII": {"chapters": (68, 70), "name_en": "Stone, Ceramic, Glass"},
    "XIV": {"chapters": (71, 71), "name_en": "Pearls, Precious Stones, Precious Metals; Jewellery"},
    "XV": {"chapters": (72, 83), "name_en": "Base Metals"},
    "XVI": {"chapters": (84, 85), "name_en": "Machinery; Electrical Equipment"},
    "XVII": {"chapters": (86, 89), "name_en": "Vehicles, Aircraft, Vessels"},
    "XVIII": {"chapters": (90, 92), "name_en": "Optical, Medical, Clocks, Musical Instruments"},
    "XIX": {"chapters": (93, 93), "name_en": "Arms and Ammunition"},
    "XX": {"chapters": (94, 96), "name_en": "Miscellaneous Manufactured Articles"},
    "XXI": {"chapters": (97, 97), "name_en": "Works of Art, Antiques"},
    "XXII": {"chapters": (98, 99), "name_en": "Israeli Special Provisions"},
}

# Supplements that ACTUALLY EXIST on shaarolami.customs.mof.gov.il
# Supplements 11, 12, 13 DO NOT EXIST — never invent them.
VALID_SUPPLEMENTS = {
    2: "תוספת שנייה — WTO concessions and preferential rates",
    3: "תוספת שלישית (WTO) — WTO bound rates",
    4: "תוספת רביעית — Special provisions",
    5: "תוספת חמישית — Additional provisions",
    6: "תוספת שישית — Framework order schedules",
    7: "תוספת שביעית — Trade agreement schedules",
    8: "תוספת שמינית — Additional trade provisions",
    9: "תוספת תשיעית — Specific product provisions",
    10: "תוספת עשירית — Additional specific provisions",
    14: "תוספת ארבע עשרה — Regulatory provisions",
    15: "תוספת חמש עשרה — Additional regulatory",
    16: "תוספת שש עשרה — Further provisions",
    17: "תוספת שבע עשרה — Supplementary provisions",
}

NONEXISTENT_SUPPLEMENTS = {11, 12, 13}

# ============================================================================
# BLOCK 3 — GIR_RULES (General Interpretive Rules / כללים פרשניים כלליים)
# ============================================================================

GIR_RULES = {
    "1": {
        "name": "Rule 1 — Legal text of headings and section/chapter notes",
        "name_he": "כלל 1 — הנוסח המשפטי של הפרטים והערות החלקים והפרקים",
        "text": "Classification is determined by the terms of the headings and any relative section or chapter notes. "
                "Classification by other rules applies only when the headings and notes do not otherwise require.",
        "application": "ALWAYS start here. Read the heading text and chapter notes literally. "
                       "Only proceed to Rules 2-6 if Rule 1 doesn't give a definitive answer.",
        "priority": 1,
    },
    "2a": {
        "name": "Rule 2(a) — Incomplete, unfinished, unassembled, disassembled",
        "name_he": "כלל 2(א) — פריטים לא שלמים, לא גמורים, לא מורכבים, מפורקים",
        "text": "Any reference to an article in a heading includes that article incomplete or unfinished, "
                "provided it has the essential character of the complete or finished article. "
                "Also includes complete or finished articles presented unassembled or disassembled.",
        "application": "A car engine shipped disassembled is still classified as an engine. "
                       "An incomplete widget that already has the essential character of a widget → classify as widget.",
        "priority": 2,
    },
    "2b": {
        "name": "Rule 2(b) — Mixtures and combinations of materials/substances",
        "name_he": "כלל 2(ב) — תערובות ושילובים של חומרים",
        "text": "Any reference to a material or substance includes mixtures or combinations with other materials. "
                "Any reference to goods of a given material includes goods partly of that material. "
                "Classification of goods of more than one material is by Rule 3.",
        "application": "A heading for 'articles of wood' includes articles partly of wood. "
                       "When multiple materials → apply Rule 3.",
        "priority": 2,
    },
    "3a": {
        "name": "Rule 3(א) — Most specific heading",
        "name_he": "כלל 3(א) — הפרט הספציפי ביותר",
        "text": "When goods are classifiable under two or more headings, "
                "the heading which provides the most specific description shall be preferred.",
        "application": "Specific description ALWAYS beats general. "
                       "'Electric shavers' (85.10) beats 'electro-mechanical appliances' (85.09). "
                       "A heading that names a product by name beats one that describes a category.",
        "priority": 3,
    },
    "3b": {
        "name": "Rule 3(ב) — Essential character",
        "name_he": "כלל 3(ב) — אופי מהותי",
        "text": "Mixtures, composite goods of different materials/components, and goods put up in sets for retail sale "
                "shall be classified as if they consisted of the material or component which gives them their essential character.",
        "application": "A leather wallet with metal clasp → leather gives essential character → ch.42. "
                       "A gift set of soap + candle + towel → determine which item gives the set its essential character. "
                       "Consider: bulk, weight, value, role of the component.",
        "priority": 3,
    },
    "3c": {
        "name": "Rule 3(ג) — Last in numerical order",
        "name_he": "כלל 3(ג) — האחרון בסדר המספרי",
        "text": "When 3(א) and 3(ב) cannot determine classification, "
                "the goods shall be classified under the heading which occurs LAST in numerical order.",
        "application": "This is the tiebreaker of last resort within Rule 3. "
                       "If a product equally fits 39.24 and 73.23, classify under 73.23 (last numerically).",
        "priority": 3,
    },
    "4": {
        "name": "Rule 4 — Most akin heading",
        "name_he": "כלל 4 — הפרט הדומה ביותר",
        "text": "Goods which cannot be classified by Rules 1-3 shall be classified under the heading "
                "appropriate to the goods to which they are most akin.",
        "application": "Rarely used. Only for truly novel products that don't fit any existing heading. "
                       "Classify under the heading for goods most similar in nature.",
        "priority": 4,
    },
    "5a": {
        "name": "Rule 5(a) — Cases, boxes, and similar containers",
        "name_he": "כלל 5(א) — נרתיקים, קופסאות ומכלים דומים",
        "text": "Camera cases, musical instrument cases, gun cases, and similar containers specially shaped to contain "
                "a specific article or set, suitable for long-term use, presented with the articles for which they are intended, "
                "shall be classified WITH the articles.",
        "application": "Guitar case shipped with guitar → classify together as guitar (ch.92). "
                       "But cases presented separately → classify by their own material.",
        "priority": 5,
    },
    "5b": {
        "name": "Rule 5(b) — Packing materials and containers",
        "name_he": "כלל 5(ב) — חומרי אריזה ומכלי אריזה",
        "text": "Packing materials and packing containers presented with the goods therein shall be classified "
                "with the goods if they are of a kind normally used for packing such goods. "
                "This does not apply when such containers are clearly suitable for repetitive use.",
        "application": "Cardboard box for shoes → classified with shoes. "
                       "Reusable metal container → classified separately.",
        "priority": 5,
    },
    "6": {
        "name": "Rule 6 — Sub-heading classification",
        "name_he": "כלל 6 — סיווג לפי פרטי משנה",
        "text": "Classification within a heading shall be determined by the terms of the sub-headings "
                "and related sub-heading notes. Rules 1-5 apply mutatis mutandis at the sub-heading level. "
                "Only sub-headings at the same level are comparable.",
        "application": "Once you've found the right 4-digit heading using Rules 1-5, "
                       "apply the same logic again to find the right 6/8/10-digit sub-heading. "
                       "CRITICAL: Only compare dashes at the same level.",
        "priority": 6,
    },
}

# ============================================================================
# BLOCK 4 — KNOWN_FAILURES
# ============================================================================

KNOWN_FAILURES = [
    {
        "id": "F001",
        "name": "Kiwi → Caviar confusion",
        "description": "System confused קווי (kiwi) with קוויאר (caviar).",
        "root_cause": "Phonetic similarity in Hebrew. No Phase 1 physical examination.",
        "correct_approach": "Phase 1: kiwi is a fruit → Section II → Chapter 8. Caviar is fish product → Section I → Chapter 3/16.",
        "lesson": "ALWAYS start with physical characteristics. Never rely on name similarity.",
    },
    {
        "id": "F002",
        "name": "Ouzo refusal (6x 'need more info')",
        "description": "System said 'need more info' 6 times when classifying ouzo.",
        "root_cause": "Failed to run elimination process. Kept asking instead of working.",
        "correct_approach": "Phase 3: Navigate 22.08 → eliminate named spirits one by one (whisky, rum, gin, vodka, etc.) → arrive at 22.08.90 'others'. This is the CORRECT and LEGITIMATE result after elimination.",
        "lesson": "אחרים (Others) is valid AFTER proper elimination. Never refuse to classify — run the elimination.",
    },
    {
        "id": "F003",
        "name": "Tires → Raw rubber",
        "description": "System picked 40.01 (natural rubber) instead of 40.11 (new pneumatic tires).",
        "root_cause": "Garbage data in parent_heading_desc field. System trusted bad data over product description.",
        "correct_approach": "Phase 1: tires are finished rubber articles → 40.11. Raw rubber (40.01) is the material, not the product.",
        "lesson": "Phase 3 requires clean data. Product description trumps inherited parent descriptions.",
    },
    {
        "id": "F004",
        "name": "No tariff rates shown",
        "description": "customs_duty and purchase_tax fields exist in DB but were never extracted.",
        "root_cause": "Phase 6 regulatory check incomplete — fields existed but pipeline didn't read them.",
        "correct_approach": "Phase 6: Always extract and display duty rates, purchase tax, and VAT.",
        "lesson": "Data exists ≠ data displayed. Verify the full output chain.",
    },
    {
        "id": "F005",
        "name": "No FIO check",
        "description": "Generic ministry references instead of specific Free Import Order requirements.",
        "root_cause": "Phase 6 import order check not implemented.",
        "correct_approach": "Phase 6: Check צו יבוא חופשי + ALL appendices for the specific HS code.",
        "lesson": "Ministry requirements must be CODE-SPECIFIC, not generic references.",
    },
]

# ============================================================================
# BLOCK 4B — CUSTOMS_ORDINANCE_ARTICLES (פקודת המכס [נוסח חדש])
# ============================================================================
# Source: https://www.nevo.co.il/law_html/law01/265_001.htm
# Structured summaries of key articles a licensed עמיל מכס uses daily.
# Full law = 272K chars (15 chapters, 241+ articles).
# Below: structured summaries of the articles most critical for classification,
# valuation, declarations, liability, and enforcement.
#
# The law has 15 chapters:
#   1. Introduction (הגדרות)           2. Administration
#   3. Supervision & declarations       4. Imports
#   5. Warehousing                      6. Exports
#   7. Ship's stores                    8. Customs payments (valuation)
#   9. Drawback & temporary admission  10. Coastal trade
#  11. Agents (סוכנים)                 12. Powers of customs officers
#  13. Forfeitures & penalties         13א. Administrative enforcement
#  14. Customs prosecutions + e-reporting  15. Miscellaneous

CUSTOMS_ORDINANCE_ARTICLES = {
    # ── ARTICLE 1: KEY DEFINITIONS ──────────────────────────────────────
    "1": {
        "name_he": "הגדרות",
        "name_en": "Definitions",
        "chapter": 1,
        "summary": "Foundational definitions used throughout the Customs Ordinance.",
        "definitions": {
            "טובין חבי מכס": "Goods subject to customs duty.",
            "בעל (טובין)": "Owner, importer, exporter, carrier, or agent of goods; "
                           "anyone holding, entitled to benefit from, or with control/authority over them.",
            "הברחה": "Importing/exporting/transporting goods along coast or borders intending to defraud "
                     "Treasury or evade prohibition/restriction — including attempts.",
            "הצהרת ייבוא": "Import declaration as defined in Section 62.",
            "הצהרת ייצוא": "Export declaration as defined in Section 103.",
            "מצהר": "Cargo manifest as defined in Section 53.",
            "סוכן מכס": "Customs agent as defined in Customs Agents Law (חוק סוכני המכס, תשכ\"ה-1964).",
            "פקיד מכס": "Person employed by customs authority (non-laborer) and any civil servant "
                        "serving customs functions.",
            "מסי יבוא": "Import taxes: customs duty + purchase tax (חוק מס קנייה) + VAT (חוק מע\"מ) "
                        "+ all other import taxes/levies.",
            "מסמכי העדפה": "Preference documents under trade agreements granting duty reduction/exemption — "
                          "including EUR.1, origin declarations, compliance statements.",
            "כלי הובלה": "Vessel, vehicle, aircraft, or animal used to transport goods.",
            "מחסן רשוי": "Licensed warehouse — authorized to deposit goods under customs supervision.",
            "מחסן המכס": "Customs warehouse — government-allocated place to deposit goods securing payment.",
            "הישבון": "Drawback — refund of customs duties under Part IX, or cancellation of "
                      "deferred customs debt under Section 160b(a).",
            "שטעון": "Transit — export of imported goods remaining under customs supervision.",
            "נמל": "Port, airport, transit terminal, or border crossing as confirmed by Director.",
            "גובה מכס": "Customs collector — the Director and any customs officer serving in that matter.",
            "רשות המכס": "Customs & Excise Authority (רשות המכס והמע\"מ).",
        },
        "broker_note": "Every classification report must use these definitions precisely. "
                       "When the law says בעל it means ANYONE with control — not just the registered importer.",
    },

    # ── ARTICLE 2: DUTY TO ANSWER & PROVIDE DOCUMENTS ───────────────────
    "2": {
        "name_he": "חובה להשיב תשובות ולמסור תעודות",
        "name_en": "Duty to Answer Questions and Provide Documents",
        "chapter": 1,
        "summary": "Any person required must answer truthfully; any person required to provide "
                   "documents must submit all relevant documentation.",
        "broker_note": "Applies to importers, exporters, agents, and customs brokers alike. "
                       "Refusal = obstruction under Section 212.",
    },

    # ── ARTICLE 24: DECLARATION OBLIGATIONS ─────────────────────────────
    "24": {
        "name_he": "הצהרות",
        "name_en": "Declarations",
        "chapter": 3,
        "summary": "Import goods and export-destined goods require import declaration (per Section 62) "
                   "or export declaration (per Section 103) as applicable.",
        "amendment": "Amended 2018 (Amendment 28) — restructured declaration requirements.",
        "broker_note": "This is the legal mandate for every import/export declaration. "
                       "No goods move without a declaration filed by the importer or their סוכן מכס.",
    },

    # ── ARTICLES 62-65G: IMPORT DECLARATION ─────────────────────────────
    "62-65g": {
        "name_he": "הצהרת ייבוא",
        "name_en": "Import Declaration Requirements",
        "chapter": 4,
        "sign": "ה (Sign E of Part IV)",
        "articles": {
            "62": {
                "name_he": "הצהרת ייבוא",
                "text": "(א) כל יבואן חייב להגיש הצהרת ייבוא לרשות המכס. "
                        "(ב) ההצהרה כוללת תיאור הטובין, כמות, ערך, מקור ופרטים נוספים שהמנהל קובע. "
                        "(ג) ההצהרה מוגשת באופן אלקטרוני לפי סעיף 64. "
                        "(ד) המנהל רשאי לדרוש צירוף מסמכים נוספים. "
                        "(ה) הגשת הצהרה יכול שתיעשה בידי סוכן מכס כאמור בסעיף 168.",
            },
            "63": {
                "name_he": "המועד להגשת הצהרת ייבוא",
                "text": "(א) הצהרה תוגש לאחר הגשת המצהר, לא יאוחר מ-3 חודשים ממועד הייבוא. "
                        "יבוא אווירי: לא יאוחר מ-45 ימים ממועד הייבוא. "
                        "(ב) לא הוגשה במועד — גובה המכס רשאי למכור או להשמיד את הטובין.",
            },
            "64": {
                "name_he": "הצהרת ייבוא אלקטרונית",
                "text": "המנהל רשאי להתיר הגשה אלקטרונית — תוקפה כתוקף הצהרה בכתב.",
            },
            "65": {
                "name_he": "בדיקת טובין שנכללו בהצהרת ייבוא",
                "text": "טובין בהצהרה ניתנים לבדיקה/אימות לפני שחרור.",
            },
            "65a": {
                "name_he": "שמירת מסמכים",
                "text": "יבואן חייב לשמור מסמכים הנוגעים לטובין ולמסרם לפי דרישה.",
            },
            "65b": {
                "name_he": "חובה להשיב על שאלות",
                "text": "מגיש הצהרה חייב להשיב על שאלות פקיד המכס.",
            },
            "65c": {
                "name_he": "מסמך חלופי",
                "text": "המנהל רשאי לקבל מסמך חלופי במקום הצהרת ייבוא.",
            },
        },
        "broker_note": "Section 62(ה) explicitly authorizes סוכן מכס to file. The 3-month deadline (sea) "
                       "and 45-day deadline (air) are strict — after that, goods can be sold/destroyed.",
    },

    # ── ARTICLES 123A-123B: CUSTOMS PAYMENT LIABILITY ───────────────────
    "123a-b": {
        "name_he": "חיוב בתשלומי מכס",
        "name_en": "Liability for Customs Payments",
        "chapter": 8,
        "articles": {
            "123a": {
                "name_he": "חיוב בתשלום מכס",
                "text": "Person liable: importer/owner when goods enter Israel; "
                        "exporter when goods exit.",
            },
            "123b": {
                "name_he": "תשלום המכס",
                "text": "Customs payable upon goods entry/exit. Director determines "
                        "payment timing and method by regulations.",
            },
        },
        "broker_note": "The customs broker is NOT the party liable for duty — the importer/owner is. "
                       "But broker liability exists under Section 168 and the Customs Agents Law.",
    },

    # ── ARTICLES 124-154: CUSTOMS VALUATION ─────────────────────────────
    # This is the most important block for daily broker work.
    "124-154": {
        "name_he": "הערכת טובין ותשלומי מכס",
        "name_en": "Customs Valuation and Duty Assessment",
        "chapter": 8,
        "key_articles": {
            "124": {
                "name_he": "שעת חיוב המכס",
                "text": "Rate applicable when goods physically enter/exit Israel — "
                        "NOT when declaration submitted.",
            },
            "129": {
                "name_he": "הגדרות להערכת טובין",
                "text": "Defines: טובין מוערכים (appraised goods), טובין זהים (identical goods), "
                        "טובין דומים (similar goods), יחסים מיוחדים (special relationships between parties).",
                "definitions": {
                    "טובין זהים": "Identical goods — same in all respects: physical characteristics, quality, reputation. "
                                  "Minor appearance differences do not prevent goods from being identical.",
                    "טובין דומים": "Similar goods — not identical but with similar characteristics and components, "
                                  "performing the same functions and commercially interchangeable.",
                    "יחסים מיוחדים": "Special relationships: officers/directors of each other's business, "
                                     "legally recognized partners, employer/employee, 5%+ ownership, "
                                     "control relationship, both controlled by third party, family members.",
                },
            },
            "130": {
                "name_he": "דרכי קביעת ערכם של טובין מוערכים",
                "name_en": "Valuation Methods for Appraised Goods",
                "text": "The 7 valuation methods IN MANDATORY ORDER (WTO/GATT Article VII):",
                "methods": [
                    {
                        "number": 1,
                        "name_he": "ערך עסקה",
                        "name_en": "Transaction Value",
                        "section": "132",
                        "description": "Price actually paid or payable for goods sold for export to Israel, "
                                       "adjusted per Section 133 additions. PRIMARY METHOD — try this first.",
                    },
                    {
                        "number": 2,
                        "name_he": "ערך עסקה של טובין זהים",
                        "name_en": "Transaction Value of Identical Goods",
                        "section": "133א+133ג",
                        "description": "Transaction value of identical goods exported to Israel at approximately "
                                       "the same time. Computed per Section 132 rules.",
                    },
                    {
                        "number": 3,
                        "name_he": "ערך עסקה של טובין דומים",
                        "name_en": "Transaction Value of Similar Goods",
                        "section": "133ב+133ג",
                        "description": "Transaction value of similar goods exported to Israel at approximately "
                                       "the same time. Computed per Section 132 rules.",
                    },
                    {
                        "number": 4,
                        "name_he": "מחיר מכירה בישראל (ערך ניכוי)",
                        "name_en": "Deductive Value (Domestic Resale Price)",
                        "section": "133ד",
                        "description": "Resale price in Israel MINUS: commissions/profit markup, "
                                       "domestic transport/insurance, import costs per 133(א)(5), "
                                       "customs duty and other import taxes.",
                    },
                    {
                        "number": 5,
                        "name_he": "ערך מחושב",
                        "name_en": "Computed Value",
                        "section": "133ה",
                        "description": "Cost of materials + fabrication + profit + general expenses "
                                       "in producing country + transport to Israeli port per 133(א)(5).",
                    },
                    {
                        "number": 6,
                        "name_he": "היפוך סדר (4↔5)",
                        "name_en": "Reversed Order (Methods 4 and 5 swapped)",
                        "section": "130(6)",
                        "description": "Importer may REQUEST to apply Method 5 before Method 4 "
                                       "(requires customs collector approval).",
                    },
                    {
                        "number": 7,
                        "name_he": "קביעת ערך במקרים אחרים (שיטת שארית)",
                        "name_en": "Fallback Method",
                        "section": "133ו",
                        "description": "Reasonable means consistent with GATT 1994 principles. "
                                       "PROHIBITED bases: domestic production price, higher-of-two values, "
                                       "export country market price, minimum customs value, "
                                       "arbitrary/fictitious values.",
                    },
                ],
                "critical_rule": "Methods MUST be applied IN ORDER. You cannot skip to Method 4 "
                                 "without proving Methods 1-3 are inapplicable.",
            },
            "131": {
                "name_he": "קביעת ערכם של טובין שחלפה שנה מעת ייבואם",
                "text": "Goods unredeemed for >1 year: valued per Methods 2-7 only "
                        "(Method 1 excluded). Director may allow Method 1 by request.",
            },
            "132": {
                "name_he": "ערך עסקה",
                "name_en": "Transaction Value (Method 1 Detail)",
                "text": "Transaction value = price paid or payable for export to Israel + Section 133 additions. "
                        "CONDITIONS: (a) no restrictions on sale/use except legal/geographic/non-material; "
                        "(b) sale not subject to unquantifiable conditions; "
                        "(c) no proceeds accrue to seller beyond Section 133 items; "
                        "(d) no special relationships, OR relationships don't affect price.",
                "special_relationships": "If special relationships exist, importer must prove price is close to: "
                                         "(1) transaction value of identical/similar goods to unrelated buyers, "
                                         "(2) deductive value per 133ד, or (3) computed value per 133ה.",
                "exclusions": "Financing interest excluded if: separate from price, in writing, "
                              "and rate not above market. Post-redemption discounts NOT included.",
            },
            "133": {
                "name_he": "התוספות למחיר העסקה",
                "name_en": "Additions to Transaction Value",
                "text": "Added to transaction value (if not already included), based on objective data:",
                "additions": [
                    "(1) Buyer's expenses: (א) commissions/brokerage (NOT buying commissions), "
                    "(ב) container costs deemed part of goods, (ג) packing costs including labor/materials.",
                    "(2) Proportional value of buyer-supplied inputs: (א) materials/components in goods, "
                    "(ב) tools/molds used in production, (ג) materials consumed in production, "
                    "(ד) engineering/design/artwork done OUTSIDE Israel.",
                    "(3) Royalties and license fees the buyer must pay as condition of sale.",
                    "(4) Seller's share in resale/use proceeds after export sale.",
                    "(5) Transport costs to port of import: (א) freight, (ב) loading/handling, "
                    "(ג) insurance — (CIF basis).",
                ],
                "critical_rule": "If objective data for any addition is unavailable, "
                                 "that transaction CANNOT be used for valuation under Section 130.",
            },
            "133א": {
                "name_he": "ערך עסקה של טובין זהים",
                "name_en": "Identical Goods Transaction Value",
                "text": "Method 2: identical goods exported to Israel at same/similar time. "
                        "Computed per Section 132. Must meet all conditions: same time, "
                        "same commercial level, same quantity (with adjustments).",
            },
            "133ב": {
                "name_he": "ערך עסקה של טובין דומים",
                "name_en": "Similar Goods Transaction Value",
                "text": "Method 3: similar goods exported to Israel at same/similar time. "
                        "Same rules as 133א.",
            },
            "133ג": {
                "name_he": "כללים לטובין זהים/דומים",
                "name_en": "Rules for Identical/Similar Goods",
                "text": "If multiple transaction values found for identical/similar goods, "
                        "use the LOWEST. Adjust for transport cost differences.",
            },
            "133ד": {
                "name_he": "קביעת ערך על פי מחיר מכירה בישראל",
                "name_en": "Deductive Value (Method 4)",
                "text": "Method 4: resale price in Israel of imported/identical/similar goods. "
                        "Deduct: (א) commissions/profit markup, (ב) domestic transport/insurance, "
                        "(ג) import transport per 133(א)(5), (ד) customs duty and taxes.",
            },
            "133ה": {
                "name_he": "קביעת ערך מחושב",
                "name_en": "Computed Value (Method 5)",
                "text": "Method 5: (א) materials + production cost including 133(א)(1)(ב)+(ג), "
                        "(ב) profit + general expenses for same class goods in country of production, "
                        "(ג) transport to Israeli port per 133(א)(5).",
            },
            "133ו": {
                "name_he": "קביעת ערך במקרים אחרים",
                "name_en": "Fallback Method (Method 7)",
                "text": "Method 7: reasonable means consistent with GATT/WTO principles. "
                        "PROHIBITED: domestic production price, higher-of-two, export country market price, "
                        "production cost (except computed value), export to third country price, "
                        "minimum customs value, arbitrary/fictitious values. "
                        "Director MAY use Methods 1-6 flexibly (without all conditions met).",
            },
            "133ז": {
                "name_he": "ערך טובין שניזוקו",
                "name_en": "Damaged Goods Valuation",
                "text": "Damaged goods before redemption: valued per Section 130 methods "
                        "with damage depreciation factored in.",
            },
            "133ח": {
                "name_he": "מסירת פירוט חשבון ליבואן",
                "name_en": "Valuation Notice to Importer",
                "text": "Director must notify importer in writing: (1) the determined value, "
                        "(2) the method used. On request, must provide detailed calculation.",
            },
            "133ט": {
                "name_he": "תחולה — טובין לשימוש מסחרי",
                "name_en": "Applicability — Commercial Goods Only",
                "text": "Sections 129-133ח apply ONLY to commercially imported goods. "
                        "Personal use goods: valued per Section 134א (Minister's regulations).",
            },
            "134": {
                "name_he": "סמכות המנהל להתקין תקנות",
                "text": "Director may issue regulations for Sections 129-133ט implementation. "
                        "May require any person connected to import to provide information, "
                        "accounting books, and purchase/import/sale documents.",
            },
            "148": {
                "name_he": "המרת מטבע חוץ",
                "text": "Foreign currency converted per exchange rate on goods entry date.",
            },
        },
        "broker_note": "The 7 valuation methods are the backbone of customs value calculation. "
                       "Method 1 (transaction value) applies in ~90% of cases. "
                       "CIF basis: price + freight + insurance to Israeli port. "
                       "The broker must verify: is there a special relationship? Are all additions declared? "
                       "Missing additions = undervaluation = penalty under Sections 207-223.",
    },

    # ── ARTICLES 168-169: CUSTOMS AGENTS ────────────────────────────────
    "168-169": {
        "name_he": "סוכנים",
        "name_en": "Customs Agents",
        "chapter": 11,
        "articles": {
            "168": {
                "name_he": "סוכן מכס",
                "text_current": "Customs agent defined per Customs Agents Law (חוק סוכני המכס, תשכ\"ה-1964). "
                                "Agent authorized to act for parties in all customs matters. "
                                "(א) כל בעל טובין רשאי לקיים הוראות הפקודה על ידי סוכן מכס. "
                                "(ב) סוכן מכס must verify and authenticate importer's power of attorney signature.",
                "text_previous": "OLD version (pre-Amendment 28): 'סוכן מורשה' could be employee or "
                                 "licensed עמיל מכס. Passenger baggage could be redeemed by anyone entrusted.",
            },
            "169": {
                "name_he": "יש להראות הרשאה",
                "text": "כל פקיד מכס רשאי לדרוש מסוכן שיראה הרשאה בכתב מן האדם שמטעמו הוא פועל. "
                        "If authorization not shown — customs officer may refuse to recognize the agency.",
            },
        },
        "broker_note": "These two articles + the Customs Agents Law (חוק סוכני המכס) define the entire "
                       "legal framework for customs brokers. Key obligations: (1) written power of attorney, "
                       "(2) signature verification, (3) show authorization on demand. "
                       "Section 223ב(ה) penalty for failing to verify POA: ₪400. "
                       "Section 223ב(ו) penalty for submitting invalid POA: ₪5,000.",
    },

    # ── ARTICLES 207-223: PENALTIES ─────────────────────────────────────
    "207-223": {
        "name_he": "עונשין",
        "name_en": "Penalties",
        "chapter": 13,
        "sign": "ב (Sign B of Part XIII)",
        "articles": {
            "207": {
                "name_he": "קשירת קשר להברחה",
                "text": "Conspiracy to smuggle: imprisonment up to 5 years or fine.",
            },
            "208": {
                "name_he": "הפעלת כוח, שוחד, השמדת טובין",
                "text": "Using force to resist capture, bribing customs officer, destroying goods, "
                        "preventing seizure: imprisonment up to 10 years or fine up to 3× goods value.",
            },
            "209": {
                "name_he": "ירי על כלי שיט של המכס",
                "text": "Firing at customs vessel/aircraft: imprisonment up to 10 years or fine.",
            },
            "210": {
                "name_he": "הרחקת טובין חבי מכס",
                "text": "Removing duty-liable goods or destroying them: imprisonment up to 7 years "
                        "or fine up to 3× goods value.",
            },
            "211": {
                "name_he": "הברחה",
                "name_en": "Smuggling",
                "text": "Smuggling goods with intent to defraud Treasury: imprisonment up to 5 years.",
            },
            "212": {
                "name_he": "עבירות מכס אחרות",
                "text": "Violating customs regulations not specified elsewhere: "
                        "imprisonment up to 2 years or fine.",
            },
            "214": {
                "name_he": "עונש כללי",
                "text": "Unspecified customs violations: imprisonment up to 6 months or fine.",
            },
            "217": {
                "name_he": "אחריות ביחד ולחוד",
                "text": "Multiple violators liable jointly and severally for penalties/fines.",
            },
            "218": {
                "name_he": "מסייעים ומשדלים",
                "text": "Aiders and abettors prosecuted as principals.",
            },
            "219": {
                "name_he": "ניסיון",
                "text": "Attempted violations prosecuted same as completed offenses.",
            },
            "220": {
                "name_he": "קנס פי שלושה מערך הטובין",
                "text": "Smuggling penalty: up to 3× goods value.",
            },
            "221": {
                "name_he": "עונש בנוסף לחילוט",
                "text": "Penalties imposed IN ADDITION to goods forfeiture.",
            },
            "222": {
                "name_he": "ערך הטובין לעניין הקנס",
                "text": "Value for penalty = current market price.",
            },
        },
        "broker_note": "Misclassification that reduces duty = defrauding Treasury under Section 211. "
                       "The broker can be prosecuted under Section 218 as aider/abettor. "
                       "Joint liability (217) means the broker AND the importer both face penalties. "
                       "Fine up to 3× goods value (220) applies to smuggling but also to "
                       "intentional undervaluation via wrong classification.",
    },

    # ── ARTICLES 223A-223R: ADMINISTRATIVE ENFORCEMENT ──────────────────
    "223a-r": {
        "name_he": "אמצעי אכיפה מינהליים",
        "name_en": "Administrative Enforcement",
        "chapter": "13א",
        "articles": {
            "223a": {
                "name_he": "הגדרות — פרק י\"ג א'",
                "text": "Definitions for the administrative enforcement chapter.",
            },
            "223b": {
                "name_he": "עיצום כספי",
                "name_en": "Financial Penalty",
                "text": "Director may impose financial penalties for violations. "
                        "Key amounts: (ה) ₪400 for failing to verify POA signature (סוכן מכס). "
                        "(ו) ₪5,000 for submitting invalid POA. "
                        "(ז) ₪25,000 for: late manifest, warehouse violations. "
                        "(ח) warehouse license violations per schedule.",
            },
            "223c": {
                "name_he": "הודעה על כוונת חיוב",
                "text": "Director provides written notice: violation details, penalty amount, appeal rights.",
            },
            "223d": {
                "name_he": "זכות טיעון",
                "text": "Violator may submit written arguments within 30 days.",
            },
            "223e": {
                "name_he": "החלטה וחיוב",
                "text": "Director issues written decision and payment demand. Penalty becomes a debt.",
            },
            "223f": {
                "name_he": "עבירה נמשכת וחוזרת",
                "text": "Continuous violation = single breach. Repeated violations within 3 years "
                        "may increase penalty.",
            },
            "223g": {
                "name_he": "הפחתת סכומים",
                "text": "Director may reduce penalty for: cooperation, small violations, other circumstances.",
            },
            "223h": {
                "name_he": "עדכון סכומי עיצום",
                "text": "Penalty amounts adjusted annually per Consumer Price Index.",
            },
            "223i": {
                "name_he": "מועד תשלום",
                "text": "Payment due within 30 days. Non-payment accrues interest + linkage adjustments.",
            },
            "223j": {
                "name_he": "פיגורים וריבית",
                "text": "Unpaid penalties accrue interest per Interest & Linkage Law.",
            },
            "223k": {
                "name_he": "גבייה",
                "text": "Collection via court enforcement, withholding, or asset seizure.",
            },
            "223l": {
                "name_he": "התראה מינהלית",
                "text": "Director may issue written warning for first violations. "
                        "Warning remains effective 3 years.",
            },
            "223m": {
                "name_he": "ביטול התראה",
                "text": "Warning canceled after 3 consecutive years of compliance.",
            },
            "223n": {
                "name_he": "חזרה על עבירה לאחר התראה",
                "text": "Repeat violation within 3 years of warning → financial penalty.",
            },
            "223p": {
                "name_he": "ערעור",
                "text": "Appeal to District Court within 30 days of penalty decision.",
            },
            "223q": {
                "name_he": "פרסום",
                "text": "Director may publish penalty details for serious violations.",
            },
            "223r": {
                "name_he": "שמירת אחריות פלילית",
                "text": "Administrative penalties do NOT prevent criminal prosecution for same violation.",
            },
        },
        "broker_note": "This is the הסדר בר-ענישה (administrative penalty regime) referenced in the "
                       "classification methodology. It allows customs to impose ₪400-₪25,000 penalties "
                       "WITHOUT criminal prosecution. 223r means BOTH administrative AND criminal "
                       "penalties can apply — they are not mutually exclusive. "
                       "The 3-year escalation window (223f, 223n) means second offenses are penalized harder.",
    },
}


# Helper function for law article access
def get_ordinance_article(article_id: str) -> dict:
    """Return a specific article or article group from the Customs Ordinance.

    Args:
        article_id: Article identifier (e.g., '1', '24', '62-65g', '124-154', '168-169',
                     '207-223', '223a-r').
    Returns:
        Dict with article data, or empty dict if not found.
    """
    return CUSTOMS_ORDINANCE_ARTICLES.get(article_id, {})


def get_valuation_methods() -> list:
    """Return the 7 customs valuation methods in mandatory order.

    These are the methods from Section 130 of the Customs Ordinance,
    implementing WTO/GATT Article VII.
    """
    valuation = CUSTOMS_ORDINANCE_ARTICLES.get("124-154", {})
    key_articles = valuation.get("key_articles", {})
    art_130 = key_articles.get("130", {})
    return art_130.get("methods", [])


# ============================================================================
# BLOCK 5 — SEED_EXPERTISE (imported from chapter_expertise.py)
# ============================================================================
# Already imported at top: from lib.chapter_expertise import SEED_EXPERTISE, get_section_for_chapter

# ============================================================================
# BLOCK 6 — Functions
# ============================================================================


def get_classification_methodology() -> dict:
    """Return the complete 10-phase classification methodology."""
    return CLASSIFICATION_METHODOLOGY


def get_gir_rule(rule_id: str) -> dict:
    """Return a specific GIR rule by ID ('1', '2a', '2b', '3a', '3b', '3c', '4', '5a', '5b', '6')."""
    return GIR_RULES.get(rule_id, {})


def get_chapter_section(chapter: int) -> str:
    """Return the section (Roman numeral) for a given chapter number.

    Uses the TARIFF_SECTIONS lookup (range-based) as the primary source,
    falls back to SEED_EXPERTISE for edge cases.
    """
    for section_id, info in TARIFF_SECTIONS.items():
        lo, hi = info["chapters"]
        if lo <= chapter <= hi:
            return section_id
    return get_section_for_chapter(chapter)


def get_applicable_supplements(chapter: int) -> list:
    """Return list of supplement numbers that apply to a given chapter.

    All valid supplements potentially apply to all chapters.
    Returns only supplements that ACTUALLY EXIST.
    """
    return sorted(VALID_SUPPLEMENTS.keys())


def format_legal_context_for_prompt(chapters: list = None, phase: int = None) -> str:
    """Build embeddable prompt text that gives the AI the broker's knowledge
    BEFORE any product description or search results.

    This is the key function — it returns the legal framework that must be
    injected at the TOP of the classification system prompt.

    Args:
        chapters: Optional list of chapter numbers to include section-specific expertise.
                  If None, includes general methodology only.
        phase: Optional phase number to focus on. If None, includes core phases.

    Returns:
        A formatted string ready to prepend to any classification prompt.
    """
    parts = []

    # --- Classification methodology core ---
    parts.append("=== ISRAELI CUSTOMS CLASSIFICATION LAW — EMBEDDED EXPERTISE ===")
    parts.append("")

    if phase is not None:
        # Single phase requested
        p = CLASSIFICATION_METHODOLOGY.get(phase)
        if p:
            parts.append(f"PHASE {phase}: {p['name']} ({p['name_he']})")
            parts.append(p["description"])
            if "steps" in p:
                for step in p["steps"]:
                    parts.append(f"  {step['id']}: {step['action']}")
                    parts.append(f"      {step['detail']}")
            if "legal_warning" in p:
                parts.append(f"  ⚠️ LEGAL WARNING: {p['legal_warning']}")
            if "sources" in p:
                for src in p["sources"]:
                    parts.append(f"  - {src}")
    else:
        # Include core phases that every classification needs
        for phase_num in [1, 2, 3]:
            p = CLASSIFICATION_METHODOLOGY[phase_num]
            parts.append(f"PHASE {phase_num}: {p['name']} ({p['name_he']})")
            parts.append(p["description"])
            if "steps" in p:
                for step in p["steps"]:
                    parts.append(f"  {step['id']}: {step['action']}")
            if "legal_warning" in p:
                parts.append(f"  ⚠️ {p['legal_warning']}")
            parts.append("")

    parts.append("")

    # --- GIR rules summary ---
    parts.append("=== GIR RULES (כללים פרשניים כלליים) ===")
    parts.append("Rule 1: Headings + section/chapter notes are primary. Only use Rules 2-6 when Rule 1 insufficient.")
    parts.append("Rule 2a: Incomplete/unassembled goods with essential character → classify as complete.")
    parts.append("Rule 2b: Mixtures/combinations of materials → classify by Rule 3.")
    parts.append("Rule 3א: Most SPECIFIC heading wins.")
    parts.append("Rule 3ב: Essential character determines classification for mixtures/composites/sets.")
    parts.append("Rule 3ג: Last numerical heading (tiebreaker of last resort).")
    parts.append("Rule 4: Most akin heading (novel products only).")
    parts.append("Rule 5a: Specially shaped containers classified WITH their contents.")
    parts.append("Rule 5b: Normal packing classified with goods; reusable containers separately.")
    parts.append("Rule 6: Sub-heading classification uses same Rules 1-5 at sub-heading level.")
    parts.append("")

    # --- Known failures as warnings ---
    parts.append("=== KNOWN CLASSIFICATION FAILURES — DO NOT REPEAT ===")
    for f in KNOWN_FAILURES:
        parts.append(f"- {f['name']}: {f['lesson']}")
    parts.append("")

    # --- Customs Ordinance key articles ---
    parts.append("=== CUSTOMS ORDINANCE — KEY ARTICLES (פקודת המכס [נוסח חדש]) ===")
    parts.append("")

    # Valuation methods (Section 130) — most critical for daily work
    parts.append("CUSTOMS VALUATION (Section 130 — 7 methods in MANDATORY order):")
    for method in get_valuation_methods():
        parts.append(f"  Method {method['number']}: {method['name_en']} ({method['name_he']}) "
                     f"[§{method['section']}] — {method['description']}")
    parts.append("  RULE: Methods MUST be applied in order. Cannot skip to Method 4 without proving 1-3 inapplicable.")
    parts.append("")

    # Transaction value additions (Section 133) — CIF basis
    art_133 = CUSTOMS_ORDINANCE_ARTICLES.get("124-154", {}).get("key_articles", {}).get("133", {})
    if art_133:
        parts.append("TRANSACTION VALUE ADDITIONS (Section 133 — what gets added to price):")
        for add in art_133.get("additions", []):
            parts.append(f"  {add}")
        parts.append("")

    # Key definitions (Section 1)
    parts.append("KEY DEFINITIONS (Section 1):")
    defs = CUSTOMS_ORDINANCE_ARTICLES.get("1", {}).get("definitions", {})
    for term, meaning in list(defs.items())[:8]:  # Top 8 most relevant
        parts.append(f"  {term}: {meaning}")
    parts.append("")

    # Agent obligations
    parts.append("AGENT OBLIGATIONS (Sections 168-169):")
    parts.append("  §168: סוכן מכס authorized to act per Customs Agents Law. Must verify POA signatures.")
    parts.append("  §169: Must show written authorization on demand. Refusal = agency not recognized.")
    parts.append("")

    # Penalties summary
    parts.append("PENALTIES (Sections 207-223):")
    parts.append("  §211 Smuggling (defrauding Treasury): up to 5 years imprisonment.")
    parts.append("  §220 Fine: up to 3× goods value.")
    parts.append("  §217 Joint liability: broker AND importer both face penalties.")
    parts.append("  §218 Aiders/abettors prosecuted as principals.")
    parts.append("  Wrong classification reducing duty = defrauding Treasury.")
    parts.append("")

    # Administrative enforcement summary
    parts.append("ADMINISTRATIVE ENFORCEMENT (Sections 223א-223ר):")
    parts.append("  §223ב Financial penalty: ₪400 (POA failure) to ₪25,000 (manifest/warehouse).")
    parts.append("  §223ד Right to argue within 30 days.")
    parts.append("  §223פ Appeal to District Court within 30 days.")
    parts.append("  §223ר Administrative AND criminal penalties can BOTH apply.")
    parts.append("")

    # --- Section/chapter expertise — ALL 22 sections always present ---
    # A broker knows the full tariff structure before reading any invoice.
    # When specific chapters are known, those sections are highlighted.
    relevant_sections = set()
    if chapters:
        for ch in chapters:
            sec = get_chapter_section(ch)
            if sec:
                relevant_sections.add(sec)

    parts.append("=== TARIFF SECTION & CHAPTER EXPERTISE (ALL 22 SECTIONS) ===")
    for sec_id in ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
                    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII",
                    "XIX", "XX", "XXI", "XXII"]:
        expertise = SEED_EXPERTISE.get(sec_id, {})
        if not expertise:
            continue
        marker = " >>> RELEVANT <<<" if sec_id in relevant_sections else ""
        parts.append(f"Section {sec_id}: {expertise.get('name_en', '')} ({expertise.get('name_he', '')}){marker}")
        parts.append(f"  Chapters: {expertise.get('chapters', [])}")
        for note in expertise.get("notes", []):
            parts.append(f"  {note}")
        for trap in expertise.get("traps", []):
            parts.append(f"  ⚠️ {trap}")
    parts.append("")

    # --- Legal hierarchy reminder ---
    parts.append("=== CRITICAL REMINDERS ===")
    parts.append("- Three pillars IN ORDER: Physical → Essence → Function. NEVER skip Physical.")
    parts.append("- Legal hierarchy: א Invoice → ב Research (MANDATORY) → ג Written clarification → פרה-רולינג")
    parts.append("- Skipping ב = סיווג רשלני. Broker personally liable.")
    parts.append("- Stop ONLY at XX.XX.XXXXXX/X format. No partial codes.")
    parts.append("- אחרים (Others) valid ONLY after eliminating every specific code above it.")
    parts.append("- Supplements 11, 12, 13 DO NOT EXIST — never reference them.")
    parts.append("- TERMINOLOGY: The correct Hebrew for customs broker is עמיל מכס or סוכן מכס. NEVER use מתווך מכס (wrong term — מתווך means mediator).")
    parts.append("=== END EMBEDDED EXPERTISE ===")
    parts.append("")

    return "\n".join(parts)
