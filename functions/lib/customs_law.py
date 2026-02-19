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

    # --- Section/chapter expertise for requested chapters ---
    if chapters:
        sections_seen = set()
        parts.append("=== RELEVANT SECTION/CHAPTER EXPERTISE ===")
        for ch in chapters:
            sec = get_chapter_section(ch)
            if sec and sec not in sections_seen:
                sections_seen.add(sec)
                expertise = SEED_EXPERTISE.get(sec, {})
                if expertise:
                    parts.append(f"Section {sec}: {expertise.get('name_en', '')} ({expertise.get('name_he', '')})")
                    parts.append(f"  Chapters: {expertise.get('chapters', [])}")
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
    parts.append("=== END EMBEDDED EXPERTISE ===")
    parts.append("")

    return "\n".join(parts)
