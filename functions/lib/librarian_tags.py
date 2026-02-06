"""
RCB Librarian Tags - Complete Israeli Customs & Trade Document Tagging System
Session 12 v3: Full coverage of import, export, customs procedures, legal, courts

Covers the FULL domain of Israeli import/export/customs:
- אוגדן מכס (סחר חוץ) - all chapters
- Legal: חקיקה, פקודות, תקנות, צווים, פסיקה
- Customs Procedures: שחרור, הערכה, סיווג, מצהרים, קרנה אט"א, פטור מותנה
- Import: צו יבוא חופשי + all 17 appendices, יבוא אישי, יבוא זמני
- Export: יצוא, יצוא חופשי, יצוא זמני, יצוא מוחזר, סיווג ביצוא, כללי מקור
- Courts: פסקי דין, החלטות, ערר, ערעור
- Publications: פרסומים, חוזרים, הודעות
- PC Agent: download_pending, upload_pending, agent_downloaded
- Geo-tagging: Israeli vs international sources
"""

from datetime import datetime, timezone

# ═══════════════════════════════════════════
#  TAG DEFINITIONS — COMPLETE DOMAIN
# ═══════════════════════════════════════════

DOCUMENT_TAGS = {
    # ── Content Type Tags ──
    "tariff": "תעריפון",
    "regulation": "רגולציה",
    "procedure": "נוהל",
    "legal": "משפטי",
    "certificate": "תעודה",
    "fta": "הסכם סחר",
    "classification": "סיווג",
    "classification_decision": "החלטת סיווג",
    "invoice": "חשבון",
    "declaration": "הצהרה",
    "knowledge": "ידע",
    "publication": "פרסום",
    "circular": "חוזר",

    # ── Legal Document Types ──
    "law": "חוק",
    "ordinance": "פקודה",
    "regulations": "תקנות",
    "order": "צו",
    "court_ruling": "פסק דין",
    "court_decision": "החלטת בית משפט",
    "legal_opinion": "חוות דעת משפטית",
    "appeal": "ערעור",

    # ═══════════════════════════════════════
    # אוגדן מכס (סחר חוץ) - ALL CHAPTERS
    # ═══════════════════════════════════════

    # Chapter 1: Release Process
    "customs_release": "תהליך שחרור",
    "customs_release_regular": "שחרור רגיל",
    "customs_release_green": "מסלול ירוק",
    "customs_release_red": "מסלול אדום",
    "customs_inspection": "בדיקת מכס",

    # Chapter 2: Valuation
    "customs_valuation": "הערכת טובין",
    "customs_valuation_gatt": "הערכה לפי GATT",
    "customs_valuation_vehicle": "הערכת רכב",

    # Chapter 3: Classification
    "customs_classification": "סיווג טובין",
    "customs_classification_ruling": "החלטת סיווג מכס",
    "classification_export": "סיווג טובין ביצוא",

    # Chapter 4: Rules of Origin
    "rules_of_origin": "כללי מקור",
    "origin_certificate": "תעודת מקור",
    "eur1": "תעודת EUR.1",
    "origin_declaration": "הצהרת מקור",
    "authorized_exporter": "יצואן מאושר",

    # Chapter 5: Tax Charge Date
    "tax_charge_date": "מועד החיוב במס",

    # Chapter 6: Export (EXPANDED)
    "customs_export": "יצוא",
    "export_declaration": "רשימון יצוא",
    "export_classification": "סיווג ביצוא",
    "export_general": "יצוא - כללי",
    "export_regular": "יצוא רגיל",
    "export_sea": "יצוא ימי",
    "export_air": "יצוא אווירי",
    "export_land": "יצוא יבשתי",
    "export_direct_loading": "טעינה ישירה ביצוא",
    "export_rear_terminal": "יצוא ממסוף עורפי",
    "export_gas": "יצוא גז",
    "returned_export": "יצוא מוחזר (פריט 810)",
    "temporary_export": "יצוא זמני",
    "transit": "טובין במעבר (טרנזיט)",
    "export_security": "יצוא ביטחוני (אפ\"י)",

    # Chapter 6.7: ATA Carnet
    "ata_carnet": "קרנה אט״א",
    "ata_carnet_israeli": "קרנה ישראלי",
    "ata_carnet_foreign": "קרנה זר",
    "ata_samples": "דוגמאות מסחריות",
    "ata_exhibition": "תערוכות וירידים",

    # Chapter 7: Conditional Exemption (פטור מותנה)
    "conditional_exemption": "פטור מותנה",
    "conditional_import": "יבוא בפטור מותנה",
    "drawback": "הישבון",

    # Chapter 8: Bonded Warehouses
    "bonded_warehouse": "מחסן רישוי",
    "warehouse_procedure": "נוהל מחסני רישוי",
    "free_zone": "אזור סחר חופשי",

    # Chapter 9: Temporary Import/Admission
    "temporary_import": "יבוא זמני",
    "temporary_admission": "כניסה זמנית",

    # Chapter 10: Personal Import
    "personal_import": "יבוא אישי",
    "personal_import_eligible": "יבוא אישי לזכאים",
    "olim_import": "יבוא עולים",
    "returning_residents": "תושבים חוזרים",
    "diplomats_import": "יבוא דיפלומטים",

    # Chapter 11-12: Transfers, Samples
    "cargo_transfer": "העברת טובין",
    "samples": "דוגמאות",
    "destruction": "השמדה",

    # Chapter 15: Intellectual Property
    "intellectual_property": "קניין רוחני",
    
    # Chapter 26: Export sub-chapters
    "export_air": "יצוא אווירי",
    "export_sea": "יצוא ימי",

    # Chapter 60-61: AEO & Authorized Importer
    "authorized_economic_operator": "גורם כלכלי מאושר",
    "authorized_importer": "יבואן מאושר",

    # PA Trade
    "pa_import": "יבוא לרשות הפלסטינית",

    # Chapter 13-15: Agents, Forwarding
    "customs_agent": "סוכן מכס",
    "customs_agent_license": "רישיון סוכן מכס",
    "forwarding_agent": "מעביר",
    "customs_broker": "עמיל מכס",

    # Chapter 16: Fines & Interest
    "fines_waiver": "ויתור על קנסות",
    "interest_waiver": "ויתור הפרשי הצמדה",

    # Chapter 25: Declarants (מצהרים)
    "declarants": "מצהרים",
    "declarants_procedure": "נוהל מצהרים",
    "authorized_declarant": "מצהר מורשה",

    # Chapter 28: Cargo Tracking
    "cargo_tracking": "מעקב מטענים",
    "manifest": "מניפסט",
    "bill_of_lading": "שטר מטען",

    # ── Free Import Order (צו יבוא חופשי) ──
    "free_import_order": "צו יבוא חופשי",
    "free_import_appendix_1": "תוספת 1 - טובין הטעונים רישיון יבוא",
    "free_import_appendix_2": "תוספת 2 - טובין הטעונים אישור תקן",
    "free_import_appendix_3": "תוספת 3 - מזון הטעון אישור",
    "free_import_appendix_4": "תוספת 4 - תרופות וציוד רפואי",
    "free_import_appendix_5": "תוספת 5 - צמחים וחומרי הדברה",
    "free_import_appendix_6": "תוספת 6 - בעלי חיים ומוצריהם",
    "free_import_appendix_7": "תוספת 7 - טובין הטעונים אישור משרד התקשורת",
    "free_import_appendix_8": "תוספת 8 - טובין הטעונים אישור משרד התחבורה",
    "free_import_appendix_9": "תוספת 9 - טובין דו-שימושיים",
    "free_import_appendix_10": "תוספת 10 - יהלומים ואבני חן",
    "free_import_appendix_11": "תוספת 11 - דלק ואנרגיה",
    "free_import_appendix_12": "תוספת 12 - כלי ירייה ותחמושת",
    "free_import_appendix_13": "תוספת 13 - חומרים מסוכנים",
    "free_import_appendix_14": "תוספת 14 - טובין הטעונים אישור משרד הבריאות",
    "free_import_appendix_15": "תוספת 15 - טובין הטעונים אישור איכות הסביבה",
    "free_import_appendix_16": "תוספת 16 - חומרי גלם לתעשייה",
    "free_import_appendix_17": "תוספת 17 - טובין הטעונים אישור משרד החקלאות",

    # ── Free Export & Export Control ──
    "free_export": "יצוא חופשי",
    "free_export_procedure": "נוהל יצוא חופשי",
    "export_procedure": "נוהל יצוא",
    "export_license": "רישיון יצוא",
    "export_control": "פיקוח יצוא",
    "export_control_chemical": "פיקוח יצוא כימי",
    "export_control_biological": "פיקוח יצוא ביולוגי",
    "export_control_nuclear": "פיקוח יצוא גרעיני",
    "export_control_dual_use": "פיקוח יצוא דו-שימושי",

    # ── Procedure Types by Ministry/Authority ──
    "procedure_customs": "נוהל מכס",
    "procedure_health": "נוהל משרד הבריאות",
    "procedure_agriculture": "נוהל משרד החקלאות",
    "procedure_communications": "נוהל משרד התקשורת",
    "procedure_transport": "נוהל משרד התחבורה",
    "procedure_economy": "נוהל משרד הכלכלה",
    "procedure_defense": "נוהל משרד הביטחון",
    "procedure_environment": "נוהל המשרד להגנת הסביבה",
    "procedure_interior": "נוהל משרד הפנים",
    "procedure_finance": "נוהל משרד האוצר",

    # ── Source / Authority Tags ──
    "customs_authority": "רשות המכס",
    "tax_authority": "רשות המסים",
    "ministry_health": "משרד הבריאות",
    "ministry_economy": "משרד הכלכלה",
    "ministry_agriculture": "משרד החקלאות",
    "ministry_defense": "משרד הביטחון",
    "ministry_transport": "משרד התחבורה",
    "ministry_communications": "משרד התקשורת",
    "ministry_environment": "המשרד להגנת הסביבה",
    "ministry_interior": "משרד הפנים",
    "ministry_finance": "משרד האוצר",
    "standards_institute": "מכון התקנים",
    "diamond_exchange": "בורסת היהלומים",
    "food_service": "שירות המזון",
    "veterinary_service": "השירותים הווטרינריים",
    "plant_protection": "שירות הגנת הצומח",
    "chamber_of_commerce": "לשכת המסחר",
    "export_institute": "מכון היצוא",

    # ── Court Tags ──
    "supreme_court": "בית המשפט העליון",
    "district_court": "בית משפט מחוזי",
    "customs_tribunal": "ועדת ערר מכס",
    "tax_tribunal": "ועדת ערר מסים",
    "administrative_court": "בית משפט לעניינים מנהליים",

    # ── Geographic / Source Country Tags ──
    "israel": "ישראל",
    "eu": "האיחוד האירופי",
    "usa": "ארצות הברית",
    "uk": "בריטניה",
    "china": "סין",
    "turkey": "טורקיה",
    "jordan": "ירדן",
    "egypt": "מצרים",
    "canada": "קנדה",
    "mexico": "מקסיקו",
    "korea": "קוריאה",
    "japan": "יפן",
    "india": "הודו",
    "mercosur": "מרקוסור",
    "efta": "אפט\"א",
    "international": "בינלאומי",
    "wco": "ארגון המכס העולמי",
    "wto": "ארגון הסחר העולמי",

    # ── Status Tags ──
    "active": "פעיל",
    "archived": "ארכיון",
    "draft": "טיוטה",
    "verified": "מאומת",
    "needs_update": "לעדכון",
    "expired": "פג תוקף",
    "superseded": "בוטל/הוחלף",
    "pending": "ממתין",

    # ── Priority Tags ──
    "critical": "קריטי",
    "important": "חשוב",
    "reference": "לעיון",
    "template": "תבנית",

    # ── Data Origin Tags ──
    "source_israeli": "מקור ישראלי",
    "source_foreign": "מקור זר",
    "source_web": "מקור אינטרנט",
    "source_email": "מקור אימייל",
    "source_manual": "הזנה ידנית",
    "source_learned": "נלמד אוטומטית",
    "source_pc_agent": "הורד ע\"י סוכן PC",

    # ── PC Agent / Download Tags ──
    "download_pending": "ממתין להורדה",
    "download_in_progress": "בתהליך הורדה",
    "download_complete": "הורדה הושלמה",
    "upload_pending": "ממתין להעלאה",
    "upload_complete": "הועלה למערכת",
    "agent_downloaded": "הורד ע\"י סוכן",
    "requires_browser": "דורש דפדפן",
    "pdf_file": "קובץ PDF",
    "excel_file": "קובץ אקסל",

    # ── Session 13.1: Missing Tags (50 broken refs → 30 unique tags) ──

    # Chapter 5: FTA Country-Specific Agreements
    "fta_eu": "הסכם סחר חופשי EU",
    "fta_us": "הסכם סחר חופשי ארה\"ב",
    "fta_efta": "הסכם סחר חופשי EFTA",
    "fta_mercosur": "הסכם סחר חופשי מרקוסור",
    "fta_jordan": "הסכם סחר חופשי ירדן",
    "fta_egypt": "הסכם סחר חופשי מצרים",
    "fta_turkey": "הסכם סחר חופשי טורקיה",
    "fta_canada": "הסכם סחר חופשי קנדה",
    "fta_mexico": "הסכם סחר חופשי מקסיקו",
    "fta_uae": "הסכם סחר חופשי איחוד האמירויות",

    # Chapter 7: Deposits & Guarantees
    "deposits_guarantees": "ערבויות ופיקדונות",

    # Chapter 8: Payment Collection
    "payment_collection": "גביית תשלומים",

    # Chapter 20: Smuggling & Enforcement
    "smuggling_enforcement": "הברחה ואכיפה",

    # Chapter 21: Refund Claims
    "refund_claims": "תביעות החזר",

    # Chapter 22: Dispute Resolution
    "dispute_resolution": "יישוב מחלוקות",

    # Chapter 23: Drawback (sub-types)
    "drawback_import_components": "הישבון רכיבים מיובאים",
    "drawback_local_components": "הישבון רכיבים מקומיים",
    "drawback_conditional": "הישבון מותנה",

    # Chapter 24: Warehouses (sub-types)
    "warehouse_general": "מחסן רישוי כללי",
    "warehouse_private": "מחסן רישוי פרטי",
    "warehouse_public": "מחסן רישוי ציבורי",

    # Chapter 25: Declarants (sub-types)
    "declarants_import": "מצהרים ביבוא",
    "declarants_export": "מצהרים ביצוא",

    # Chapter 27: Shaar Olami System
    "shaar_olami_system": "מערכת שער עולמי",

    # Chapter 28: Cargo Tracking (sub-types)
    "cargo_tracking_sea": "מעקב מטענים ימי",
    "cargo_tracking_air": "מעקב מטענים אווירי",

    # Chapter 34: Forms
    "form_a": "טופס A (תעודת מקור)",

    # Chapter 40: Land Crossing
    "land_crossing": "מעבר יבשתי",

    # Chapter 41: Palestinian Authority
    "pa_autonomy": "סחר עם הרשות הפלסטינית",

    # Chapter 42: Eilat Port
    "eilat_port": "נמל אילת",
}

# ═══════════════════════════════════════════
#  TAG HIERARCHY
# ═══════════════════════════════════════════

TAG_HIERARCHY = {
    "content_type": [
        "tariff", "regulation", "procedure", "legal", "certificate",
        "fta", "classification", "classification_decision", "invoice",
        "declaration", "knowledge", "publication", "circular",
    ],
    "legal_type": [
        "law", "ordinance", "regulations", "order",
        "court_ruling", "court_decision", "legal_opinion", "appeal",
    ],
    "customs_handbook": [
        "customs_release", "customs_release_regular", "customs_release_green",
        "customs_release_red", "customs_inspection",
        "customs_valuation", "customs_valuation_gatt", "customs_valuation_vehicle",
        "customs_classification", "customs_classification_ruling", "classification_export",
        "rules_of_origin", "origin_certificate", "eur1", "origin_declaration", "authorized_exporter",
        "tax_charge_date",
        "customs_export", "export_declaration", "export_classification",
        "export_general", "export_regular", "export_sea", "export_air", "export_land",
        "export_direct_loading", "export_rear_terminal", "export_gas",
        "returned_export", "temporary_export", "transit", "export_security",
        "ata_carnet", "ata_carnet_israeli", "ata_carnet_foreign",
        "ata_samples", "ata_exhibition",
        "conditional_exemption", "conditional_import", "drawback",
        "drawback_import_components", "drawback_local_components", "drawback_conditional",
        "bonded_warehouse", "warehouse_procedure", "warehouse_general",
        "warehouse_private", "warehouse_public", "free_zone",
        "temporary_import", "temporary_admission",
        "personal_import", "personal_import_eligible", "olim_import",
        "returning_residents", "diplomats_import",
        "cargo_transfer", "samples", "destruction",
        "deposits_guarantees", "payment_collection", "refund_claims",
        "smuggling_enforcement", "dispute_resolution",
        "customs_agent", "customs_agent_license", "forwarding_agent", "customs_broker",
        "fines_waiver", "interest_waiver",
        "declarants", "declarants_procedure", "authorized_declarant",
        "declarants_import", "declarants_export",
        "cargo_tracking", "manifest", "bill_of_lading",
        "cargo_tracking_sea", "cargo_tracking_air",
        "shaar_olami_system", "land_crossing", "pa_autonomy", "eilat_port",
        "intellectual_property",
    ],
    "free_import": [
        "free_import_order",
        *[f"free_import_appendix_{i}" for i in range(1, 18)],
    ],
    "export": [
        "free_export", "free_export_procedure", "export_procedure",
        "export_license", "export_control",
        "export_control_chemical", "export_control_biological",
        "export_control_nuclear", "export_control_dual_use",
    ],
    "procedures_by_ministry": [
        "procedure_customs", "procedure_health", "procedure_agriculture",
        "procedure_communications", "procedure_transport", "procedure_economy",
        "procedure_defense", "procedure_environment", "procedure_interior",
        "procedure_finance",
    ],
    "authority_source": [
        "customs_authority", "tax_authority",
        "ministry_health", "ministry_economy", "ministry_agriculture",
        "ministry_defense", "ministry_transport", "ministry_communications",
        "ministry_environment", "ministry_interior", "ministry_finance",
        "standards_institute", "diamond_exchange",
        "food_service", "veterinary_service", "plant_protection",
        "chamber_of_commerce", "export_institute",
    ],
    "courts": [
        "supreme_court", "district_court", "customs_tribunal",
        "tax_tribunal", "administrative_court",
    ],
    "geography": [
        "israel", "eu", "usa", "uk", "china", "turkey",
        "jordan", "egypt", "canada", "mexico", "korea", "japan", "india",
        "mercosur", "efta", "international", "wco", "wto",
    ],
    "data_origin": [
        "source_israeli", "source_foreign", "source_web",
        "source_email", "source_manual", "source_learned", "source_pc_agent",
    ],
    "pc_agent": [
        "download_pending", "download_in_progress", "download_complete",
        "upload_pending", "upload_complete", "agent_downloaded",
        "requires_browser", "pdf_file", "excel_file",
    ],
    "status": [
        "active", "archived", "draft", "verified",
        "needs_update", "expired", "superseded", "pending",
    ],
    "priority": ["critical", "important", "reference", "template"],
}

# ═══════════════════════════════════════════
#  KEYWORD → TAG DETECTION RULES
# ═══════════════════════════════════════════

TAG_KEYWORDS = {
    # Content types
    "tariff": ["תעריף", "מכס", "duty", "tariff", "hs_code", "פרט מכס", "שער מכס", "תעריפון"],
    "regulation": ["רגולציה", "regulation", "הוראות"],
    "procedure": ["נוהל", "procedure", "תהליך", "הנחיות", "instructions"],
    "legal": ["חוק", "פקודה", "law", "legal", "משפט"],
    "certificate": ["תעודה", "אישור", "certificate", "permit", "רישיון"],
    "fta": ["הסכם סחר", "fta", "free trade", "eur.1", "eur1", "תעודת מקור", "origin"],
    "classification": ["סיווג", "classification", "classify", "פרט מכס"],
    "classification_decision": ["החלטת סיווג", "classification decision", "החלטה מקדמית"],
    "publication": ["פרסום", "publication", "חוזר", "הודעה", "bulletin"],
    "circular": ["חוזר", "circular", "הנחיה"],

    # Legal types
    "law": ["חוק", "law", "act", "statute"],
    "ordinance": ["פקודה", "ordinance", "פקודת המכס"],
    "regulations": ["תקנות", "regulations", "תקנה"],
    "order": ["צו", "order", "צו יבוא", "צו מכס", "צו תעריף"],
    "court_ruling": ["פסק דין", "judgment", "פס\"ד"],
    "court_decision": ["החלטת בית משפט", "court decision"],
    "appeal": ["ערעור", "appeal", "ערר"],

    # Customs Handbook procedures
    "customs_release": ["שחרור", "release", "תהליך שחרור", "clearance"],
    "customs_valuation": ["הערכה", "הערכת טובין", "valuation", "ערך"],
    "customs_classification": ["סיווג טובין", "goods classification"],
    "rules_of_origin": ["כללי מקור", "rules of origin", "תעודת מקור"],
    "eur1": ["eur.1", "eur1", "אי.יו.אר"],
    "authorized_exporter": ["יצואן מאושר", "authorized exporter"],
    "tax_charge_date": ["מועד החיוב במס", "tax charge date"],
    "customs_export": ["יצוא", "export", "רשימון יצוא", "הצהרת יצוא"],
    "returned_export": ["יצוא מוחזר", "returned export", "פריט 810", "יבוא חוזר"],
    "temporary_export": ["יצוא זמני", "temporary export"],
    "export_sea": ["יצוא ימי", "sea export", "maritime export"],
    "export_air": ["יצוא אווירי", "air export", "airfreight export"],
    "export_land": ["יצוא יבשתי", "land export", "מעבר גבול יבשתי"],
    "export_direct_loading": ["טעינה ישירה", "direct loading"],
    "transit": ["טרנזיט", "transit", "מעבר", "העברה"],
    "export_security": ["יצוא ביטחוני", "security export", "אפ\"י", "DECA"],
    "export_control_dual_use": ["דו-שימושי", "dual use", "dual-use"],
    "ata_carnet": ["קרנה", "carnet", "אט\"א", "ata", "a.t.a", "פנקס מעבר"],
    "ata_samples": ["דוגמאות מסחריות", "commercial samples"],
    "ata_exhibition": ["תערוכה", "ירידים", "exhibition", "fair"],
    "conditional_exemption": ["פטור מותנה", "conditional exemption", "פט\"מ"],
    "drawback": ["הישבון", "drawback"],
    "bonded_warehouse": ["מחסן רישוי", "bonded warehouse", "מחסני ערובה"],
    "free_zone": ["אזור סחר חופשי", "free trade zone", "free zone"],
    "temporary_import": ["יבוא זמני", "temporary import"],
    "temporary_admission": ["כניסה זמנית", "temporary admission"],
    "personal_import": ["יבוא אישי", "personal import"],
    "olim_import": ["עולים", "olim", "עלייה"],
    "returning_residents": ["תושבים חוזרים", "returning residents"],
    "diplomats_import": ["דיפלומטים", "diplomats", "פטור דיפלומטי"],
    "cargo_transfer": ["העברת טובין", "cargo transfer"],
    "samples": ["דוגמאות", "samples", "דגימה"],
    "destruction": ["השמדה", "destruction"],
    "customs_agent": ["סוכן מכס", "customs agent", "עמיל מכס", "customs broker"],
    "fines_waiver": ["ויתור על קנסות", "waiver of fines", "ויתור קנס"],
    "declarants": ["מצהרים", "declarants", "מצהר"],
    "declarants_procedure": ["נוהל מצהרים", "declarants procedure"],
    "cargo_tracking": ["מעקב מטענים", "cargo tracking"],
    "manifest": ["מניפסט", "manifest"],
    "bill_of_lading": ["שטר מטען", "bill of lading", "b/l", "bl"],
    "customs_inspection": ["בדיקת מכס", "customs inspection", "בדיקה פיזית"],
    "intellectual_property": ["קניין רוחני", "intellectual property", "סימן מסחרי", "זכויות יוצרים"],
    "export_air": ["יצוא אווירי", "air export"],
    "export_sea": ["יצוא ימי", "sea export"],
    "authorized_economic_operator": ["גורם כלכלי מאושר", "AEO", "authorized economic operator"],
    "authorized_importer": ["יבואן מאושר", "authorized importer"],
    "pa_import": ["יבוא לרשות הפלסטינית", "PA import", "רש\"פ"],

    # Free Import Order + Appendices
    "free_import_order": ["צו יבוא חופשי", "free import order", "יבוא חופשי"],
    "free_import_appendix_1": ["תוספת 1", "תוספת ראשונה", "רישיון יבוא"],
    "free_import_appendix_2": ["תוספת 2", "תוספת שנייה", "אישור תקן", "תו תקן"],
    "free_import_appendix_3": ["תוספת 3", "תוספת שלישית", "אישור מזון"],
    "free_import_appendix_4": ["תוספת 4", "תרופות", "ציוד רפואי", "medical device"],
    "free_import_appendix_5": ["תוספת 5", "צמחים", "חומרי הדברה", "pesticide"],
    "free_import_appendix_6": ["תוספת 6", "בעלי חיים", "וטרינרי", "veterinary"],
    "free_import_appendix_7": ["תוספת 7", "תקשורת", "רדיו", "אלחוטי"],
    "free_import_appendix_8": ["תוספת 8", "תחבורה", "רכב", "vehicle"],
    "free_import_appendix_9": ["תוספת 9", "דו-שימושי", "dual-use", "dual use"],
    "free_import_appendix_10": ["תוספת 10", "יהלומים", "אבני חן", "diamond"],
    "free_import_appendix_11": ["תוספת 11", "דלק", "אנרגיה", "fuel"],
    "free_import_appendix_12": ["תוספת 12", "כלי ירייה", "תחמושת", "firearms"],
    "free_import_appendix_13": ["תוספת 13", "חומרים מסוכנים", "hazardous"],
    "free_import_appendix_14": ["תוספת 14", "אישור בריאות"],
    "free_import_appendix_15": ["תוספת 15", "איכות הסביבה"],
    "free_import_appendix_16": ["תוספת 16", "חומרי גלם", "raw materials"],
    "free_import_appendix_17": ["תוספת 17", "אישור חקלאות"],

    # Export
    "free_export": ["יצוא חופשי", "free export"],
    "free_export_procedure": ["נוהל יצוא חופשי", "free export procedure"],
    "export_license": ["רישיון יצוא", "export license"],
    "export_control": ["פיקוח יצוא", "export control", "בקרת יצוא"],
    "export_control_dual_use": ["דו-שימושי יצוא", "dual-use export"],
    "export_control_chemical": ["פיקוח כימי", "chemical export"],
    "export_control_biological": ["פיקוח ביולוגי", "biological export"],
    "export_control_nuclear": ["פיקוח גרעיני", "nuclear export"],

    # Ministry procedures
    "procedure_customs": ["נוהל מכס", "customs procedure", "נוהל רשות המכס", "אוגדן מכס"],
    "procedure_health": ["נוהל משרד הבריאות", "health procedure"],
    "procedure_agriculture": ["נוהל משרד החקלאות", "agriculture procedure", "נוהל וטרינרי"],
    "procedure_communications": ["נוהל משרד התקשורת", "communications procedure"],
    "procedure_transport": ["נוהל משרד התחבורה", "transport procedure", "נוהל רכב"],
    "procedure_economy": ["נוהל משרד הכלכלה", "economy procedure"],
    "procedure_defense": ["נוהל משרד הביטחון", "defense procedure"],
    "procedure_environment": ["נוהל סביבה", "environment procedure"],

    # Authorities
    "customs_authority": ["רשות המכס", "customs authority", "מכס ישראל", "שער עולמי"],
    "tax_authority": ["רשות המסים", "tax authority", "מס הכנסה"],
    "ministry_health": ["משרד הבריאות", "ministry of health", "בריאות"],
    "ministry_economy": ["משרד הכלכלה", "ministry of economy", "כלכלה", "תעשייה"],
    "ministry_agriculture": ["משרד החקלאות", "agriculture", "חקלאות", "וטרינרי"],
    "ministry_defense": ["משרד הביטחון", "defense", "ביטחון"],
    "ministry_transport": ["משרד התחבורה", "transport", "תחבורה"],
    "ministry_communications": ["משרד התקשורת", "communications", "תקשורת", "טלקום"],
    "ministry_environment": ["המשרד להגנת הסביבה", "environment", "סביבה"],
    "standards_institute": ["מכון התקנים", "standards", "תקן", "SII", "תו תקן"],
    "food_service": ["שירות המזון", "food service", "מזון"],
    "veterinary_service": ["השירותים הווטרינריים", "veterinary"],
    "plant_protection": ["שירות הגנת הצומח", "plant protection", "phytosanitary"],
    "chamber_of_commerce": ["לשכת המסחר", "chamber of commerce"],
    "export_institute": ["מכון היצוא", "export institute"],

    # Courts
    "supreme_court": ["בית המשפט העליון", "supreme court", "בג\"ץ"],
    "district_court": ["בית משפט מחוזי", "district court"],
    "customs_tribunal": ["ועדת ערר מכס", "customs tribunal", "ערר מכס"],
    "tax_tribunal": ["ועדת ערר מסים", "tax tribunal"],
    "administrative_court": ["בית משפט מנהלי", "administrative court"],

    # Geography
    "israel": ["ישראל", "israel", "israeli"],
    "eu": ["אירופ", "europe", "eu", "האיחוד האירופי"],
    "usa": ["ארצות הברית", "usa", "united states", "us customs"],
    "uk": ["בריטניה", "uk", "united kingdom", "hmrc"],
    "china": ["סין", "china", "chinese"],
    "turkey": ["טורקיה", "turkey"],
    "jordan": ["ירדן", "jordan"],
    "egypt": ["מצרים", "egypt"],
    "korea": ["קוריאה", "korea"],
    "japan": ["יפן", "japan"],
    "india": ["הודו", "india"],
    "mercosur": ["מרקוסור", "mercosur"],
    "efta": ["אפט\"א", "efta"],
    "wco": ["ארגון המכס העולמי", "wco", "world customs"],
    "wto": ["ארגון הסחר העולמי", "wto", "world trade"],
}

# ═══════════════════════════════════════════
#  CUSTOMS HANDBOOK CHAPTER MAP
#  (אוגדן מכס - סחר חוץ)
# ═══════════════════════════════════════════

CUSTOMS_HANDBOOK_CHAPTERS = {
    # ═══════════════════════════════════════
    #  IMPORT PROCEDURES
    # ═══════════════════════════════════════
    1: {"tag": "customs_release", "name_he": "תהליך השחרור (תש\"ר)", "name_en": "Release Process",
        "scope": "import",
        "pdf_url": "https://www.gov.il/BlobFolder/policy/noaalmeches1/he/Noal_1_Shichror_ACC.pdf"},
    2: {"tag": "customs_valuation", "name_he": "הערכה", "name_en": "Valuation",
        "scope": "import",
        "pdf_url": "https://www.gov.il/BlobFolder/guide/guide-to-importing-personally-via-parcels-or-shipping-companies/he/Guides_customs_nohalHaraha2.pdf"},
    3: {"tag": "customs_classification", "name_he": "סיווג טובין", "name_en": "Classification",
        "scope": "both",
        "pdf_url": ""},
    4: {"tag": "tax_charge_date", "name_he": "מועד החיוב במס", "name_en": "Tax Charge Date",
        "scope": "import",
        "pdf_url": ""},
    5: {"tag": "rules_of_origin", "name_he": "הסכמי סחר וכללי מקור", "name_en": "Trade Agreements & Rules of Origin",
        "scope": "both",
        "pdf_url": ""},
    "5.1": {"tag": "fta_eu", "name_he": "הסכם סחר - EU", "name_en": "EU FTA",
            "scope": "both", "pdf_url": ""},
    "5.2": {"tag": "fta_us", "name_he": "הסכם סחר - ארה\"ב", "name_en": "US FTA",
            "scope": "both", "pdf_url": ""},
    "5.3": {"tag": "fta_efta", "name_he": "הסכם סחר - EFTA", "name_en": "EFTA FTA",
            "scope": "both", "pdf_url": ""},
    "5.4": {"tag": "fta_mercosur", "name_he": "הסכם סחר - מרקוסור", "name_en": "Mercosur FTA",
            "scope": "both", "pdf_url": ""},
    "5.5": {"tag": "fta_jordan", "name_he": "הסכם סחר - ירדן", "name_en": "Jordan FTA",
            "scope": "both", "pdf_url": ""},
    "5.6": {"tag": "fta_egypt", "name_he": "הסכם סחר - מצרים", "name_en": "Egypt FTA",
            "scope": "both", "pdf_url": ""},
    "5.7": {"tag": "fta_turkey", "name_he": "הסכם סחר - טורקיה", "name_en": "Turkey FTA",
            "scope": "both", "pdf_url": ""},
    "5.8": {"tag": "fta_canada", "name_he": "הסכם סחר - קנדה", "name_en": "Canada FTA",
            "scope": "both", "pdf_url": ""},
    "5.9": {"tag": "fta_mexico", "name_he": "הסכם סחר - מכסיקו", "name_en": "Mexico FTA",
            "scope": "both", "pdf_url": ""},
    "5.10": {"tag": "fta_uae", "name_he": "הסכם סחר - איחוד האמירויות", "name_en": "UAE FTA",
             "scope": "both", "pdf_url": ""},

    # ═══════════════════════════════════════
    #  ATA CARNET (IMPORT + EXPORT)
    # ═══════════════════════════════════════
    "6.7": {"tag": "ata_carnet", "name_he": "קרנה אט״א", "name_en": "ATA Carnet",
             "scope": "both",
             "sub_chapters": {
                 "6.7.1": {"tag": "ata_carnet_israeli", "name_he": "קרנה ישראלי - יצוא", "name_en": "Israeli Carnet - Export"},
                 "6.7.2": {"tag": "ata_carnet_foreign", "name_he": "קרנה זר - יבוא", "name_en": "Foreign Carnet - Import"},
                 "6.7.3": {"tag": "ata_samples", "name_he": "דוגמאות מסחריות", "name_en": "Commercial Samples"},
                 "6.7.4": {"tag": "ata_exhibition", "name_he": "תערוכות וירידים", "name_en": "Exhibitions"},
             },
             "pdf_url": "https://www.gov.il/BlobFolder/policy/customs-procedures-karne/he/Policy_Customs-procedures_6.7-A.T.A%20CARNET-acc.pdf"},

    # ═══════════════════════════════════════
    #  CONDITIONAL EXEMPTION & DRAWBACK
    # ═══════════════════════════════════════
    7: {"tag": "deposits_guarantees", "name_he": "פיקדונות וערבויות", "name_en": "Deposits & Guarantees",
        "scope": "both", "pdf_url": ""},
    8: {"tag": "payment_collection", "name_he": "גבייה ותשלום", "name_en": "Payment & Collection",
        "scope": "import", "pdf_url": ""},
    9: {"tag": "temporary_import", "name_he": "יבוא זמני / כניסה זמנית", "name_en": "Temporary Import/Admission",
        "scope": "import", "pdf_url": ""},
    10: {"tag": "personal_import", "name_he": "יבוא אישי", "name_en": "Personal Import",
         "scope": "import",
         "sub_chapters": {
             "10.1": {"tag": "personal_import_eligible", "name_he": "יבוא אישי - פטור", "name_en": "Personal Import - Eligible"},
             "10.2": {"tag": "olim_import", "name_he": "יבוא עולים", "name_en": "Olim Import"},
             "10.3": {"tag": "returning_residents", "name_he": "תושבים חוזרים", "name_en": "Returning Residents"},
             "10.4": {"tag": "diplomats_import", "name_he": "פטור דיפלומטי", "name_en": "Diplomatic Exemption"},
         },
         "pdf_url": ""},
    11: {"tag": "cargo_transfer", "name_he": "העברת טובין", "name_en": "Cargo Transfer/Transit",
         "scope": "both", "pdf_url": ""},
    12: {"tag": "samples", "name_he": "דוגמאות ודגימות", "name_en": "Samples & Testing",
         "scope": "both", "pdf_url": ""},
    13: {"tag": "conditional_exemption", "name_he": "פטור מותנה", "name_en": "Conditional Exemption",
         "scope": "import", "pdf_url": ""},
    14: {"tag": "destruction", "name_he": "השמדת טובין", "name_en": "Destruction of Goods",
         "scope": "import", "pdf_url": ""},
    15: {"tag": "intellectual_property", "name_he": "קניין רוחני", "name_en": "Intellectual Property",
         "scope": "import", "pdf_url": ""},
    16: {"tag": "fines_waiver", "name_he": "קנסות, ריבית וויתורים", "name_en": "Fines, Interest & Waivers",
         "scope": "both", "pdf_url": ""},
    17: {"tag": "customs_agent", "name_he": "סוכני מכס", "name_en": "Customs Agents",
         "scope": "both", "pdf_url": ""},
    18: {"tag": "forwarding_agent", "name_he": "עמילי מכס ושילוח", "name_en": "Customs Brokers & Forwarders",
         "scope": "both", "pdf_url": ""},
    19: {"tag": "customs_inspection", "name_he": "בדיקות מכס ופיקוח", "name_en": "Customs Inspections",
         "scope": "both", "pdf_url": ""},
    20: {"tag": "smuggling_enforcement", "name_he": "הברחות ואכיפה", "name_en": "Smuggling & Enforcement",
         "scope": "both", "pdf_url": ""},
    21: {"tag": "refund_claims", "name_he": "תביעות להחזר מסים", "name_en": "Tax Refund Claims",
         "scope": "import", "pdf_url": ""},
    22: {"tag": "dispute_resolution", "name_he": "ערעורים וויכוחים", "name_en": "Dispute Resolution",
         "scope": "both", "pdf_url": ""},
    23: {"tag": "drawback", "name_he": "הישבון", "name_en": "Drawback",
         "scope": "export",
         "sub_chapters": {
             "23.1": {"tag": "drawback_import_components", "name_he": "הישבון - מרכיבים מיובאים", "name_en": "Drawback - Imported Components"},
             "23.2": {"tag": "drawback_local_components", "name_he": "הישבון - ייצור מקומי", "name_en": "Drawback - Local Components"},
             "23.3": {"tag": "drawback_conditional", "name_he": "הישבון - דחיית תשלום", "name_en": "Drawback - Deferred Payment"},
         },
         "pdf_url": ""},
    24: {"tag": "bonded_warehouse", "name_he": "מחסנים רשויים", "name_en": "Bonded Warehouses",
         "scope": "both",
         "sub_chapters": {
             "24.1": {"tag": "warehouse_general", "name_he": "מחסנים - כללי", "name_en": "Warehouses - General"},
             "24.2": {"tag": "warehouse_private", "name_he": "מחסן רישוי פרטי", "name_en": "Private Bonded Warehouse"},
             "24.3": {"tag": "warehouse_public", "name_he": "מחסן רישוי ציבורי", "name_en": "Public Bonded Warehouse"},
             "24.4": {"tag": "free_zone", "name_he": "אזור סחר חופשי", "name_en": "Free Trade Zone"},
         },
         "pdf_url": ""},

    # ═══════════════════════════════════════
    #  DECLARANTS (מצהרים) - Chapter 25
    # ═══════════════════════════════════════
    25: {"tag": "declarants_procedure", "name_he": "נוהל מצהרים", "name_en": "Declarants Procedure",
         "scope": "both",
         "sub_chapters": {
             "25.1": {"tag": "declarants_import", "name_he": "מצהרים - יבוא", "name_en": "Declarants - Import"},
             "25.2": {"tag": "declarants_export", "name_he": "מצהרים - יצוא", "name_en": "Declarants - Export"},
             "25.3": {"tag": "authorized_declarant", "name_he": "מצהר מורשה", "name_en": "Authorized Declarant"},
         },
         "pdf_url": "https://claltax.com/wp-content/uploads/2021/09/Noal_25_Mzharim_ACC-07012020.pdf"},

    # ═══════════════════════════════════════
    #  EXPORT PROCEDURES - Chapter 26 (FULL)
    # ═══════════════════════════════════════
    26: {"tag": "customs_export", "name_he": "יצוא", "name_en": "Export",
         "scope": "export",
         "sub_chapters": {
             "26.1": {"tag": "export_general", "name_he": "יצוא - כללי", "name_en": "Export - General"},
             "26.2": {"tag": "export_sea", "name_he": "יצוא ימי", "name_en": "Sea Export"},
             "26.3": {"tag": "export_air", "name_he": "יצוא אווירי", "name_en": "Air Export"},
             "26.4": {"tag": "export_land", "name_he": "יצוא יבשתי", "name_en": "Land Export"},
             "26.5": {"tag": "export_direct_loading", "name_he": "טעינה ישירה ביצוא", "name_en": "Direct Loading Export"},
             "26.6": {"tag": "export_rear_terminal", "name_he": "יצוא ממסוף עורפי", "name_en": "Export from Rear Terminal"},
             "26.7": {"tag": "export_gas", "name_he": "יצוא גז", "name_en": "Gas Export"},
             "26.8": {"tag": "returned_export", "name_he": "יצוא מוחזר (פריט 810)", "name_en": "Returned Export (Item 810)"},
             "26.9": {"tag": "temporary_export", "name_he": "יצוא זמני", "name_en": "Temporary Export"},
             "26.10": {"tag": "transit", "name_he": "טובין במעבר (טרנזיט)", "name_en": "Transit Goods"},
         },
         "pdf_url": ""},

    # ═══════════════════════════════════════
    #  CARGO TRACKING & MANIFEST
    # ═══════════════════════════════════════
    27: {"tag": "shaar_olami_system", "name_he": "מערכת שער עולמי", "name_en": "Shaar Olami System",
         "scope": "both", "pdf_url": ""},
    28: {"tag": "cargo_tracking", "name_he": "מעקב מטענים ומצהרים", "name_en": "Cargo Tracking & Declarations",
         "scope": "both",
         "sub_chapters": {
             "28.1": {"tag": "manifest", "name_he": "מניפסט", "name_en": "Manifest"},
             "28.2": {"tag": "bill_of_lading", "name_he": "שטר מטען", "name_en": "Bill of Lading"},
             "28.3": {"tag": "cargo_tracking_sea", "name_he": "מעקב מטענים - ימי", "name_en": "Cargo Tracking - Sea"},
             "28.4": {"tag": "cargo_tracking_air", "name_he": "מעקב מטענים - אווירי", "name_en": "Cargo Tracking - Air"},
         },
         "pdf_url": ""},

    # ═══════════════════════════════════════
    #  EXPORT-SPECIFIC PROCEDURES
    # ═══════════════════════════════════════
    30: {"tag": "export_control", "name_he": "פיקוח על יצוא", "name_en": "Export Control",
         "scope": "export",
         "sub_chapters": {
             "30.1": {"tag": "export_control_dual_use", "name_he": "יצוא דו-שימושי", "name_en": "Dual-Use Export Control"},
             "30.2": {"tag": "export_control_chemical", "name_he": "פיקוח כימי/ביולוגי/גרעיני", "name_en": "Chemical/Bio/Nuclear Export"},
             "30.3": {"tag": "export_security", "name_he": "יצוא ביטחוני (אפ\"י)", "name_en": "Security Export (DECA)"},
         },
         "pdf_url": ""},
    31: {"tag": "free_export", "name_he": "צו יצוא חופשי", "name_en": "Free Export Order",
         "scope": "export", "pdf_url": ""},
    32: {"tag": "authorized_exporter", "name_he": "יצואן מאושר", "name_en": "Authorized Exporter",
         "scope": "export", "pdf_url": ""},
    33: {"tag": "export_classification", "name_he": "סיווג טובין ביצוא", "name_en": "Export Classification",
         "scope": "export", "pdf_url": ""},
    34: {"tag": "origin_certificate", "name_he": "תעודות מקור ביצוא", "name_en": "Export Origin Certificates",
         "scope": "export",
         "sub_chapters": {
             "34.1": {"tag": "eur1", "name_he": "תעודת EUR.1", "name_en": "EUR.1 Certificate"},
             "34.2": {"tag": "origin_declaration", "name_he": "הצהרת מקור", "name_en": "Origin Declaration"},
             "34.3": {"tag": "form_a", "name_he": "טופס A - מדינות מתפתחות", "name_en": "Form A - GSP"},
         },
         "pdf_url": ""},

    # ═══════════════════════════════════════
    #  BORDER CROSSINGS & SPECIAL
    # ═══════════════════════════════════════
    40: {"tag": "land_crossing", "name_he": "מעברי גבול יבשתיים", "name_en": "Land Border Crossings",
         "scope": "both", "pdf_url": ""},
    41: {"tag": "pa_autonomy", "name_he": "קשרי אוטונומיה", "name_en": "PA Relations & Trade",
         "scope": "both", "pdf_url": ""},
    42: {"tag": "eilat_port", "name_he": "נמל אילת", "name_en": "Eilat Port",
         "scope": "both", "pdf_url": ""},

    # ═══════════════════════════════════════
    #  AEO / AUTHORIZED OPERATORS
    # ═══════════════════════════════════════
    60: {"tag": "authorized_economic_operator", "name_he": "גורם כלכלי מאושר (AEO)", "name_en": "Authorized Economic Operator",
         "scope": "both", "pdf_url": ""},
    61: {"tag": "authorized_importer", "name_he": "יבואן מאושר", "name_en": "Authorized Importer",
         "scope": "import", "pdf_url": ""},
}

# ═══════════════════════════════════════════
#  COLLECTION-BASED TAG RULES
# ═══════════════════════════════════════════

COLLECTION_DEFAULT_TAGS = {
    "tariff_chapters": ["tariff", "source_israeli", "active"],
    "tariff": ["tariff", "source_israeli", "active"],
    "hs_code_index": ["tariff", "classification", "source_israeli", "active"],
    "ministry_index": ["regulation", "source_israeli", "active"],
    "regulatory": ["regulation", "source_israeli", "active"],
    "regulatory_approvals": ["regulation", "certificate", "source_israeli", "active"],
    "regulatory_certificates": ["certificate", "regulation", "source_israeli", "active"],
    "classification_rules": ["classification", "legal", "source_israeli", "active"],
    "classification_knowledge": ["classification", "source_learned", "active"],
    "procedures": ["procedure", "source_israeli", "active"],
    "knowledge": ["knowledge", "active"],
    "knowledge_base": ["knowledge", "active"],
    "legal_references": ["legal", "reference", "source_israeli", "active"],
    "legal_documents": ["legal", "source_israeli", "active"],
    "licensing_knowledge": ["regulation", "certificate", "source_israeli", "active"],
    "classifications": ["classification", "active"],
    "declarations": ["declaration", "active"],
    "rcb_classifications": ["classification", "source_email", "active"],
    "fta_agreements": ["fta", "international", "active"],
    "documents": ["active"],
    "court_rulings": ["court_ruling", "legal", "source_israeli", "active"],
    "free_import_orders": ["free_import_order", "order", "source_israeli", "active"],
    "export_procedures": ["export_procedure", "free_export", "customs_export", "source_israeli", "active"],
    "publications": ["publication", "source_israeli", "active"],
    "customs_handbook": ["procedure_customs", "source_israeli", "active"],
    "ata_carnet_docs": ["ata_carnet", "procedure_customs", "source_israeli", "active"],
    "declarants_docs": ["declarants", "procedure_customs", "source_israeli", "active"],
    "pc_agent_downloads": ["agent_downloaded", "source_pc_agent", "active"],
}

# ═══════════════════════════════════════════
#  FREE IMPORT ORDER APPENDIX MAPPING
# ═══════════════════════════════════════════

FREE_IMPORT_APPENDIX_MAP = {
    1: {"tag": "free_import_appendix_1", "ministry": "ministry_economy", "desc": "טובין הטעונים רישיון יבוא"},
    2: {"tag": "free_import_appendix_2", "ministry": "standards_institute", "desc": "טובין הטעונים אישור תקן"},
    3: {"tag": "free_import_appendix_3", "ministry": "food_service", "desc": "מזון הטעון אישור"},
    4: {"tag": "free_import_appendix_4", "ministry": "ministry_health", "desc": "תרופות וציוד רפואי"},
    5: {"tag": "free_import_appendix_5", "ministry": "plant_protection", "desc": "צמחים וחומרי הדברה"},
    6: {"tag": "free_import_appendix_6", "ministry": "veterinary_service", "desc": "בעלי חיים ומוצריהם"},
    7: {"tag": "free_import_appendix_7", "ministry": "ministry_communications", "desc": "טובין הטעונים אישור תקשורת"},
    8: {"tag": "free_import_appendix_8", "ministry": "ministry_transport", "desc": "טובין הטעונים אישור תחבורה"},
    9: {"tag": "free_import_appendix_9", "ministry": "ministry_defense", "desc": "טובין דו-שימושיים"},
    10: {"tag": "free_import_appendix_10", "ministry": "diamond_exchange", "desc": "יהלומים ואבני חן"},
    11: {"tag": "free_import_appendix_11", "ministry": "ministry_finance", "desc": "דלק ואנרגיה"},
    12: {"tag": "free_import_appendix_12", "ministry": "ministry_defense", "desc": "כלי ירייה ותחמושת"},
    13: {"tag": "free_import_appendix_13", "ministry": "ministry_environment", "desc": "חומרים מסוכנים"},
    14: {"tag": "free_import_appendix_14", "ministry": "ministry_health", "desc": "טובין הטעונים אישור בריאות"},
    15: {"tag": "free_import_appendix_15", "ministry": "ministry_environment", "desc": "טובין הטעונים אישור סביבה"},
    16: {"tag": "free_import_appendix_16", "ministry": "ministry_economy", "desc": "חומרי גלם לתעשייה"},
    17: {"tag": "free_import_appendix_17", "ministry": "ministry_agriculture", "desc": "טובין הטעונים אישור חקלאות"},
}

# ═══════════════════════════════════════════
#  PC AGENT DOWNLOAD REGISTRY
#  URLs that require browser/PC agent to download
# ═══════════════════════════════════════════

PC_AGENT_DOWNLOAD_SOURCES = {
    # ═══════════════════════════════════════
    #  GOV.IL CUSTOMS PROCEDURES (MAIN PAGE)
    # ═══════════════════════════════════════
    "customs_procedures_gov": {
        "url": "https://www.gov.il/he/collectors/policies?officeId=c0d8ba69-e309-4fe5-801f-855971774a90&Type=2efa9b53-5df9-4df9-8e9d-21134511f368",
        "name_he": "נהלי מכס - Gov.il - דף ראשי",
        "content_type": ["procedure_customs"],
        "file_types": ["pdf", "html"],
        "requires_browser": True,
        "scope": "both",
        "auto_tags": ["procedure_customs", "source_israeli", "source_pc_agent"],
        "instructions": "Navigate to this page, list ALL procedure PDFs, download each one. Look for links to individual procedure chapters.",
    },

    # ═══════════════════════════════════════
    #  SPECIFIC CUSTOMS PROCEDURE PDFS
    # ═══════════════════════════════════════
    "customs_release_procedure": {
        "url": "https://www.gov.il/BlobFolder/policy/noaalmeches1/he/Noal_1_Shichror_ACC.pdf",
        "name_he": "נוהל שחרור (תש\"ר) - פרק 1",
        "content_type": ["customs_release", "procedure_customs"],
        "file_types": ["pdf"],
        "requires_browser": False,
        "scope": "import",
        "auto_tags": ["customs_release", "procedure_customs", "source_israeli"],
    },
    "declarants_procedure_pdf": {
        "url": "https://claltax.com/wp-content/uploads/2021/09/Noal_25_Mzharim_ACC-07012020.pdf",
        "name_he": "נוהל מצהרים - פרק 25",
        "content_type": ["declarants_procedure", "procedure_customs"],
        "file_types": ["pdf"],
        "requires_browser": False,
        "scope": "both",
        "auto_tags": ["declarants_procedure", "declarants", "procedure_customs", "source_israeli"],
    },
    "carnet_procedure": {
        "url": "https://www.gov.il/BlobFolder/policy/customs-procedures-karne/he/Policy_Customs-procedures_6.7-A.T.A%20CARNET-acc.pdf",
        "name_he": "נוהל קרנה אט\"א - פרק 6.7",
        "content_type": ["ata_carnet", "procedure_customs"],
        "file_types": ["pdf"],
        "requires_browser": False,
        "scope": "both",
        "auto_tags": ["ata_carnet", "procedure_customs", "source_israeli"],
    },
    "carnet_form_online": {
        "url": "https://www.gov.il/BlobFolder/service/application-release-goods-ata/he/customs_nealim_נוהל מילוי טופס קרנה מקוון.pdf",
        "name_he": "נוהל מילוי טופס קרנה מקוון",
        "content_type": ["ata_carnet", "template"],
        "file_types": ["pdf"],
        "requires_browser": False,
        "scope": "both",
        "auto_tags": ["ata_carnet", "template", "source_israeli"],
    },
    "carnet_gov_page": {
        "url": "https://www.gov.il/he/departments/general/procedures-karne",
        "name_he": "קרנה אט\"א - דף Gov.il",
        "content_type": ["ata_carnet", "procedure_customs"],
        "file_types": ["html", "pdf"],
        "requires_browser": True,
        "scope": "both",
        "auto_tags": ["ata_carnet", "procedure_customs", "source_israeli", "source_pc_agent"],
        "instructions": "Navigate to page, download all linked PDFs and documents.",
    },
    "conditional_exemption_procedure": {
        "url": "https://www.ruthcargo.co.il/wp-content/uploads/2024/05/אוגדן-מכס-שער-עולמי-נוהל-פטור-מותנה.pdf",
        "name_he": "נוהל פטור מותנה - פרק 13",
        "content_type": ["conditional_exemption", "procedure_customs"],
        "file_types": ["pdf"],
        "requires_browser": False,
        "scope": "import",
        "auto_tags": ["conditional_exemption", "procedure_customs", "source_israeli"],
    },
    "bonded_warehouse_procedure": {
        "url": "https://claltax.com/wp-content/uploads/2022/02/customs_meches24.pdf",
        "name_he": "נוהל מחסנים רשויים - פרק 24",
        "content_type": ["bonded_warehouse", "procedure_customs"],
        "file_types": ["pdf"],
        "requires_browser": False,
        "scope": "both",
        "auto_tags": ["bonded_warehouse", "warehouse_procedure", "procedure_customs", "source_israeli"],
    },

    # ═══════════════════════════════════════
    #  EXPORT PROCEDURES (FULL COVERAGE)
    # ═══════════════════════════════════════
    "export_procedure_shaar_olami": {
        "url": "https://www.chamber.org.il/media/166783/הוראות-נוהל-יצוא-פיילוט-שער-עולמי-טיוטה-להערות-הציבור.pdf",
        "name_he": "הוראת נוהל זמנית - יצוא במערכת שער עולמי - פרק 26",
        "content_type": ["customs_export", "procedure_customs"],
        "file_types": ["pdf"],
        "requires_browser": False,
        "scope": "export",
        "auto_tags": ["customs_export", "export_general", "procedure_customs", "shaar_olami_system", "source_israeli"],
    },
    "export_procedures_gov": {
        "url": "https://www.gov.il/he/collectors/policies?officeId=c0d8ba69-e309-4fe5-801f-855971774a90&Type=2efa9b53-5df9-4df9-8e9d-21134511f368",
        "name_he": "נהלי מכס יצוא ויבוא - Gov.il",
        "content_type": ["customs_export", "procedure_customs"],
        "file_types": ["pdf", "html"],
        "requires_browser": True,
        "scope": "both",
        "auto_tags": ["customs_export", "procedure_customs", "source_israeli", "source_pc_agent"],
        "instructions": "Download ALL export-related procedure PDFs from this page.",
    },
    "export_forms_israel_trade": {
        "url": "https://israel-trade.net/exporterformsandprocedures/",
        "name_he": "טפסים ונהלים ליצוא מישראל - מינהל סחר חוץ",
        "content_type": ["customs_export", "free_export", "export_control"],
        "file_types": ["html", "pdf"],
        "requires_browser": True,
        "scope": "export",
        "auto_tags": ["customs_export", "free_export", "procedure_customs", "source_israeli", "source_pc_agent"],
        "instructions": "Navigate and download all export procedure documents and forms.",
    },
    "free_export_order": {
        "url": "https://www.gov.il/he/departments/general/free-export-order",
        "name_he": "צו יצוא חופשי",
        "content_type": ["free_export", "order"],
        "file_types": ["html", "pdf"],
        "requires_browser": True,
        "scope": "export",
        "auto_tags": ["free_export", "order", "source_israeli", "source_pc_agent"],
    },
    "export_control_dual_use": {
        "url": "https://www.gov.il/he/departments/general/dual-use-items-export-supervision",
        "name_he": "פיקוח על יצוא טובין דו-שימושיים",
        "content_type": ["export_control", "export_control_dual_use"],
        "file_types": ["html", "pdf"],
        "requires_browser": True,
        "scope": "export",
        "auto_tags": ["export_control", "export_control_dual_use", "ministry_defense", "source_israeli", "source_pc_agent"],
    },
    "security_export_law": {
        "url": "https://www.gov.il/he/departments/general/security-export-control-law",
        "name_he": "חוק הפיקוח על היצוא הביטחוני",
        "content_type": ["export_security", "law"],
        "file_types": ["html", "pdf"],
        "requires_browser": True,
        "scope": "export",
        "auto_tags": ["export_security", "law", "ministry_defense", "source_israeli", "source_pc_agent"],
    },
    "drawback_procedure": {
        "url": "https://www.gov.il/he/departments/general/drawback-procedure",
        "name_he": "נוהל הישבון - פרק 23",
        "content_type": ["drawback", "procedure_customs"],
        "file_types": ["html", "pdf"],
        "requires_browser": True,
        "scope": "export",
        "auto_tags": ["drawback", "procedure_customs", "source_israeli", "source_pc_agent"],
    },
    "authorized_exporter_procedure": {
        "url": "https://www.gov.il/he/departments/general/authorized-exporter",
        "name_he": "נוהל יצואן מאושר",
        "content_type": ["authorized_exporter", "procedure_customs"],
        "file_types": ["html", "pdf"],
        "requires_browser": True,
        "scope": "export",
        "auto_tags": ["authorized_exporter", "procedure_customs", "rules_of_origin", "source_israeli", "source_pc_agent"],
    },
    "export_classification_book": {
        "url": "https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb/he/CustomsBook/Export/ExportCustomsEntry",
        "name_he": "ספר סיווג טובין ביצוא",
        "content_type": ["classification_export", "customs_export"],
        "file_types": ["html", "excel"],
        "requires_browser": True,
        "scope": "export",
        "auto_tags": ["customs_export", "classification_export", "source_israeli", "source_pc_agent"],
    },

    # ═══════════════════════════════════════
    #  TARIFF & CLASSIFICATION SOURCES
    # ═══════════════════════════════════════
    "customs_tariff_shaarolami": {
        "url": "https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb/he/CustomsBook",
        "name_he": "ספר מכס - שער עולמי",
        "content_type": ["tariff"],
        "file_types": ["html", "excel"],
        "requires_browser": True,
        "scope": "import",
        "auto_tags": ["tariff", "source_israeli", "source_pc_agent"],
    },

    # ═══════════════════════════════════════
    #  LEGAL SOURCES
    # ═══════════════════════════════════════
    "free_import_order_nevo": {
        "url": "https://www.nevo.co.il/law_html/law01/999_431.htm",
        "name_he": "צו יבוא חופשי - נבו",
        "content_type": ["free_import_order", "order"],
        "file_types": ["html"],
        "requires_browser": True,
        "scope": "import",
        "auto_tags": ["free_import_order", "order", "source_israeli", "source_pc_agent"],
    },
    "customs_ordinance_nevo": {
        "url": "https://www.nevo.co.il/law_html/law01/265_001.htm",
        "name_he": "פקודת המכס - נבו",
        "content_type": ["ordinance", "legal"],
        "file_types": ["html"],
        "requires_browser": True,
        "scope": "both",
        "auto_tags": ["ordinance", "legal", "source_israeli", "source_pc_agent"],
    },
    "customs_regulations_nevo": {
        "url": "https://www.nevo.co.il/law_html/law01/265_002.htm",
        "name_he": "תקנות המכס - נבו",
        "content_type": ["regulations", "legal"],
        "file_types": ["html"],
        "requires_browser": True,
        "scope": "both",
        "auto_tags": ["regulations", "legal", "source_israeli", "source_pc_agent"],
    },
    "customs_handbook_nevo": {
        "url": "https://www.nevo.co.il/FilesFolderPermalink.aspx?b=files&r=מוסדות+ממשל\\רשות+המסים\\נוהל+מכס",
        "name_he": "אוגדן מכס - נבו",
        "content_type": ["procedure_customs", "legal"],
        "file_types": ["pdf"],
        "requires_browser": True,
        "scope": "both",
        "auto_tags": ["procedure_customs", "source_israeli", "source_pc_agent", "legal"],
    },

    # ═══════════════════════════════════════
    #  CLALTAX - PROCEDURES & GUIDES
    # ═══════════════════════════════════════
    "customs_procedures_claltax": {
        "url": "https://claltax.com/נהלים-והנחיות-מכס-ומס-קניה/",
        "name_he": "נהלים והנחיות מכס - Claltax",
        "content_type": ["procedure_customs", "publication"],
        "file_types": ["html", "pdf"],
        "requires_browser": True,
        "scope": "both",
        "auto_tags": ["procedure_customs", "publication", "source_israeli", "source_pc_agent"],
        "instructions": "Navigate and download ALL procedure PDFs available on this page.",
    },
    "customs_guides_claltax": {
        "url": "https://claltax.com/מדריכי-רשות-המסים-מכס-יבוא-יצוא/",
        "name_he": "מדריכי מכס יבוא/יצוא - Claltax",
        "content_type": ["procedure_customs", "publication"],
        "file_types": ["html", "pdf"],
        "requires_browser": True,
        "scope": "both",
        "auto_tags": ["procedure_customs", "publication", "source_israeli", "source_pc_agent"],
    },

    # ═══════════════════════════════════════
    #  CHAMBER OF COMMERCE SOURCES
    # ═══════════════════════════════════════
    "chamber_customs_updates": {
        "url": "https://www.chamber.org.il/foreigntrade/1109/1111/",
        "name_he": "חדשות ועדכוני מכס - לשכת המסחר",
        "content_type": ["publication", "customs_export"],
        "file_types": ["html"],
        "requires_browser": True,
        "scope": "both",
        "auto_tags": ["publication", "chamber_of_commerce", "source_israeli", "source_pc_agent"],
    },
    "chamber_carnet": {
        "url": "https://haifachamber.org.il/קרנה-אטא-a-t-a-carnet/",
        "name_he": "קרנה אט\"א - לשכת המסחר חיפה",
        "content_type": ["ata_carnet"],
        "file_types": ["html"],
        "requires_browser": True,
        "scope": "both",
        "auto_tags": ["ata_carnet", "chamber_of_commerce", "source_israeli", "source_pc_agent"],
    },

    # ═══════════════════════════════════════
    #  MINISTRY-SPECIFIC EXPORT/IMPORT
    # ═══════════════════════════════════════
    "agriculture_export": {
        "url": "https://www.gov.il/he/departments/topics/agriculture-export",
        "name_he": "יצוא חקלאי - משרד החקלאות",
        "content_type": ["customs_export", "procedure_agriculture"],
        "file_types": ["html", "pdf"],
        "requires_browser": True,
        "scope": "export",
        "auto_tags": ["customs_export", "procedure_agriculture", "ministry_agriculture", "source_israeli", "source_pc_agent"],
    },
    "defense_export_apy": {
        "url": "https://www.exportctrl.mod.gov.il/",
        "name_he": "אגף פיקוח על היצוא הביטחוני (אפ\"י)",
        "content_type": ["export_security", "export_control"],
        "file_types": ["html", "pdf"],
        "requires_browser": True,
        "scope": "export",
        "auto_tags": ["export_security", "export_control", "ministry_defense", "source_israeli", "source_pc_agent"],
    },
    "cosmetics_export": {
        "url": "https://www.gov.il/he/departments/general/cosmetics-export",
        "name_he": "יצוא תמרוקים",
        "content_type": ["customs_export", "procedure_health"],
        "file_types": ["html", "pdf"],
        "requires_browser": True,
        "scope": "export",
        "auto_tags": ["customs_export", "procedure_health", "ministry_health", "source_israeli", "source_pc_agent"],
    },
}


# ═══════════════════════════════════════════
#  AUTO-TAGGING FUNCTIONS
# ═══════════════════════════════════════════

def auto_tag_document(document, collection_name=None):
    """Automatically generate tags for a document based on its content."""
    tags = set()

    if collection_name and collection_name in COLLECTION_DEFAULT_TAGS:
        tags.update(COLLECTION_DEFAULT_TAGS[collection_name])

    searchable = _build_searchable_text(document)

    for tag_key, keywords in TAG_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in searchable:
                tags.add(tag_key)
                break

    ministry = document.get("ministry", "")
    if ministry:
        _detect_ministry_tag(ministry, tags)

    hs_code = document.get("hs_code") or document.get("code", "")
    if hs_code and len(str(hs_code).replace(".", "").replace("/", "")) >= 4:
        tags.add("tariff")
        tags.update(get_tags_for_hs_code(hs_code))

    for field in ["origin", "country_of_origin", "fta", "agreement"]:
        if document.get(field):
            tags.add("fta")
            break

    _detect_free_import_appendices(searchable, tags)
    _detect_court_tags(searchable, tags)
    _detect_customs_handbook_chapter(searchable, tags)
    _detect_export_tags(searchable, tags)
    _detect_geography(searchable, document, tags)
    _detect_data_origin(document, searchable, tags)
    _detect_file_type(document, tags)

    return sorted(list(tags))


def auto_tag_pc_agent_download(file_path, source_key, metadata=None):
    """
    Generate tags for a file downloaded by the PC agent.

    Args:
        file_path: str - Path to downloaded file
        source_key: str - Key from PC_AGENT_DOWNLOAD_SOURCES
        metadata: dict - Optional metadata from the download

    Returns:
        List[str] - Tags for the downloaded file
    """
    tags = set()

    # Base tags from source definition
    source_info = PC_AGENT_DOWNLOAD_SOURCES.get(source_key, {})
    if source_info.get("auto_tags"):
        tags.update(source_info["auto_tags"])

    # Always add PC agent tags
    tags.add("agent_downloaded")
    tags.add("download_complete")
    tags.add("upload_pending")

    # Detect file type
    if file_path:
        fp = file_path.lower()
        if fp.endswith(".pdf"):
            tags.add("pdf_file")
        elif fp.endswith((".xlsx", ".xls", ".csv")):
            tags.add("excel_file")

    # Add metadata-based tags
    if metadata:
        if metadata.get("content"):
            searchable = metadata["content"].lower()
            for tag_key, keywords in TAG_KEYWORDS.items():
                for kw in keywords:
                    if kw.lower() in searchable:
                        tags.add(tag_key)
                        break

    return sorted(list(tags))


def suggest_related_tags(current_tags):
    """Suggest additional tags that commonly appear with current tags."""
    suggestions = set()
    tag_associations = {
        "tariff": ["classification", "source_israeli"],
        "classification": ["tariff"],
        "classification_decision": ["classification", "legal", "customs_authority"],
        "regulation": ["certificate"],
        "fta": ["customs_authority", "certificate", "international", "rules_of_origin"],
        "rules_of_origin": ["fta", "eur1", "authorized_exporter"],
        "customs_export": ["export_declaration", "classification_export"],
        "returned_export": ["customs_export", "conditional_exemption"],
        "temporary_export": ["customs_export", "ata_carnet"],
        "ata_carnet": ["temporary_export", "temporary_import", "chamber_of_commerce", "ata_samples"],
        "declarants": ["declarants_procedure", "customs_authority"],
        "customs_release": ["customs_inspection", "customs_valuation"],
        "conditional_exemption": ["drawback", "customs_release"],
        "bonded_warehouse": ["customs_release", "cargo_tracking"],
        "personal_import": ["customs_release", "customs_valuation"],
        "customs_agent": ["customs_agent_license", "customs_broker"],
        "free_import_order": ["order", "source_israeli", "regulation"],
        "free_export": ["export_procedure", "source_israeli"],
        "export_control": ["ministry_defense", "export_control_dual_use"],
        "ministry_health": ["procedure_health", "free_import_appendix_4", "free_import_appendix_14"],
        "ministry_economy": ["procedure_economy", "free_import_appendix_1"],
        "ministry_agriculture": ["procedure_agriculture", "free_import_appendix_6", "free_import_appendix_17"],
        "ministry_communications": ["procedure_communications", "free_import_appendix_7"],
        "ministry_transport": ["procedure_transport", "free_import_appendix_8"],
        "ministry_defense": ["free_import_appendix_9", "free_import_appendix_12", "export_control"],
        "ministry_environment": ["free_import_appendix_13", "free_import_appendix_15"],
        "standards_institute": ["free_import_appendix_2", "certificate"],
    }

    for tag in current_tags:
        if tag in tag_associations:
            for s in tag_associations[tag]:
                if s not in current_tags:
                    suggestions.add(s)

    return sorted(list(suggestions))


def get_tags_for_hs_code(hs_code):
    """Generate tags for an HS code chapter."""
    tags = ["tariff", "classification", "active"]
    code = str(hs_code).replace(".", "").replace("/", "").replace(" ", "")
    if len(code) < 2:
        return tags

    chapter = int(code[:2]) if code[:2].isdigit() else 0

    CHAPTER_MAP = {
        range(1, 6): ["ministry_agriculture", "veterinary_service", "free_import_appendix_6"],
        range(6, 15): ["ministry_agriculture", "plant_protection", "free_import_appendix_5"],
        range(15, 16): ["food_service", "free_import_appendix_3"],
        range(16, 25): ["food_service", "ministry_health", "free_import_appendix_3"],
        range(25, 28): ["ministry_environment", "free_import_appendix_13"],
        range(28, 39): ["ministry_environment", "free_import_appendix_13"],
        range(30, 31): ["ministry_health", "free_import_appendix_4"],
        range(50, 64): ["standards_institute", "free_import_appendix_2"],
        range(71, 72): ["diamond_exchange", "free_import_appendix_10"],
        range(72, 84): ["standards_institute"],
        range(84, 86): ["standards_institute", "free_import_appendix_2"],
        range(87, 88): ["ministry_transport", "free_import_appendix_8"],
        range(90, 93): ["standards_institute", "free_import_appendix_2"],
        range(93, 94): ["ministry_defense", "free_import_appendix_12", "export_control"],
        range(95, 96): ["standards_institute", "free_import_appendix_2"],
    }

    if chapter in (84, 85, 90):
        tags.append("free_import_appendix_9")

    for ch_range, extra_tags in CHAPTER_MAP.items():
        if chapter in ch_range:
            tags.extend(extra_tags)

    return sorted(list(set(tags)))


def get_free_import_appendix_info(appendix_number):
    """Get details about a Free Import Order appendix (1-17)."""
    return FREE_IMPORT_APPENDIX_MAP.get(appendix_number, {
        "tag": None, "ministry": None, "desc": f"תוספת {appendix_number} - לא ידוע"
    })


def get_pc_agent_sources():
    """Get all sources that need PC agent to download."""
    return PC_AGENT_DOWNLOAD_SOURCES


def get_pending_downloads(db):
    """Get all documents tagged as needing PC agent download."""
    try:
        docs = db.collection("librarian_index") \
            .where("tags", "array_contains", "download_pending") \
            .limit(50).stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]
    except Exception as e:
        print(f"    ❌ Error getting pending downloads: {e}")
        return []


def mark_download_complete(db, doc_id, file_path, file_url=""):
    """Mark a document as downloaded by PC agent and ready for upload."""
    try:
        doc_ref = db.collection("librarian_index").document(doc_id)
        doc_ref.update({
            "tags": _replace_tag(
                doc_ref.get().to_dict().get("tags", []),
                "download_pending", "download_complete"
            ),
            "file_path": file_path,
            "file_url": file_url,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "downloaded_by": "pc_agent",
        })
        return True
    except Exception as e:
        print(f"    ❌ Error marking download complete: {e}")
        return False


def mark_upload_complete(db, doc_id, firestore_path=""):
    """Mark a document as uploaded to Firestore/Storage after PC agent download."""
    try:
        doc_ref = db.collection("librarian_index").document(doc_id)
        current_tags = doc_ref.get().to_dict().get("tags", [])
        updated_tags = _replace_tag(current_tags, "upload_pending", "upload_complete")
        updated_tags = _replace_tag(updated_tags, "download_complete", "agent_downloaded")
        doc_ref.update({
            "tags": updated_tags,
            "firestore_path": firestore_path,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        })
        return True
    except Exception as e:
        print(f"    ❌ Error marking upload complete: {e}")
        return False


# ═══════════════════════════════════════════
#  TAG MANAGEMENT (Firestore)
# ═══════════════════════════════════════════

def add_tags(db, doc_id, tags, collection="librarian_index"):
    """Add tags to a document in Firestore."""
    try:
        doc_ref = db.collection(collection).document(doc_id)
        doc = doc_ref.get()
        if doc.exists:
            existing = doc.to_dict().get("tags", [])
            merged = sorted(list(set(existing + tags)))
            doc_ref.update({"tags": merged, "updated_at": datetime.now(timezone.utc).isoformat()})
        else:
            doc_ref.set({"tags": sorted(tags), "updated_at": datetime.now(timezone.utc).isoformat()})
        return True
    except Exception as e:
        print(f"    ❌ Error adding tags to {doc_id}: {e}")
        return False


def remove_tags(db, doc_id, tags_to_remove, collection="librarian_index"):
    """Remove specific tags from a document."""
    try:
        doc_ref = db.collection(collection).document(doc_id)
        doc = doc_ref.get()
        if doc.exists:
            existing = doc.to_dict().get("tags", [])
            updated = [t for t in existing if t not in tags_to_remove]
            doc_ref.update({"tags": updated, "updated_at": datetime.now(timezone.utc).isoformat()})
            return True
        return False
    except Exception as e:
        print(f"    ❌ Error removing tags from {doc_id}: {e}")
        return False


def get_tag_stats(db):
    """Get statistics on tag usage."""
    tag_counts = {}
    total_docs = 0
    try:
        for doc in db.collection("librarian_index").stream():
            total_docs += 1
            for tag in doc.to_dict().get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return {
            "total_documents": total_docs,
            "tag_counts": dict(sorted(tag_counts.items(), key=lambda x: -x[1])),
            "unique_tags": len(tag_counts),
            "most_common": sorted(tag_counts.items(), key=lambda x: -x[1])[:15],
        }
    except Exception as e:
        return {"error": str(e)}


def init_tag_definitions(db):
    """Initialize tag definitions in Firestore."""
    try:
        batch = db.batch()
        count = 0
        for tag_key, tag_he in DOCUMENT_TAGS.items():
            parent = None
            for category, children in TAG_HIERARCHY.items():
                if tag_key in children:
                    parent = category
                    break
            doc_ref = db.collection("librarian_tags").document(tag_key)
            batch.set(doc_ref, {
                "key": tag_key, "name_he": tag_he,
                "name_en": tag_key.replace("_", " ").title(),
                "category": parent or "other",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }, merge=True)
            count += 1
            if count % 400 == 0:
                batch.commit()
                batch = db.batch()
        batch.commit()
        print(f"    ✅ Initialized {count} tag definitions")
        return count
    except Exception as e:
        print(f"    ❌ Error initializing tags: {e}")
        return 0


# ═══════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════

def _build_searchable_text(document):
    parts = []
    for key, val in document.items():
        if isinstance(val, str):
            parts.append(val.lower())
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    parts.append(item.lower())
    return " ".join(parts)


def _detect_ministry_tag(ministry, tags):
    m = ministry.lower()
    ministry_map = {
        "בריאות": "ministry_health", "health": "ministry_health",
        "כלכלה": "ministry_economy", "economy": "ministry_economy",
        "חקלאות": "ministry_agriculture", "agriculture": "ministry_agriculture",
        "ביטחון": "ministry_defense", "defense": "ministry_defense",
        "תחבורה": "ministry_transport", "transport": "ministry_transport",
        "תקשורת": "ministry_communications", "communications": "ministry_communications",
        "סביבה": "ministry_environment", "environment": "ministry_environment",
        "פנים": "ministry_interior", "interior": "ministry_interior",
        "אוצר": "ministry_finance", "finance": "ministry_finance",
    }
    for keyword, tag in ministry_map.items():
        if keyword in m:
            tags.add(tag)
            procedure_tag = tag.replace("ministry_", "procedure_")
            if procedure_tag in DOCUMENT_TAGS:
                tags.add(procedure_tag)
            return


def _detect_free_import_appendices(searchable, tags):
    import re
    for num_str in re.findall(r'תוספת\s*(\d{1,2})', searchable):
        num = int(num_str)
        if 1 <= num <= 17:
            tags.add(f"free_import_appendix_{num}")
            tags.add("free_import_order")
            info = FREE_IMPORT_APPENDIX_MAP.get(num, {})
            if info.get("ministry"):
                tags.add(info["ministry"])
    if "צו יבוא חופשי" in searchable or "free import order" in searchable:
        tags.add("free_import_order")
        tags.add("order")
        tags.add("source_israeli")


def _detect_court_tags(searchable, tags):
    indicators = {
        "פסק דין": "court_ruling", "פס\"ד": "court_ruling",
        "ערעור": "appeal", "ערר מכס": "customs_tribunal",
        "ועדת ערר": "customs_tribunal",
        "בית המשפט העליון": "supreme_court", "בג\"ץ": "supreme_court",
        "בית משפט מחוזי": "district_court",
        "בית משפט מנהלי": "administrative_court",
    }
    for indicator, tag in indicators.items():
        if indicator.lower() in searchable:
            tags.add(tag)
            tags.add("legal")
            tags.add("source_israeli")


def _detect_customs_handbook_chapter(searchable, tags):
    """Detect references to אוגדן מכס chapters."""
    if "אוגדן מכס" in searchable or "אוגדן סחר חוץ" in searchable:
        tags.add("procedure_customs")
        tags.add("source_israeli")

    chapter_indicators = {
        "תהליך שחרור": "customs_release",
        "הערכת טובין": "customs_valuation",
        "סיווג טובין": "customs_classification",
        "כללי מקור": "rules_of_origin",
        "תעודת מקור": "origin_certificate",
        "יצואן מאושר": "authorized_exporter",
        "מועד החיוב במס": "tax_charge_date",
        "קרנה": "ata_carnet",
        "carnet": "ata_carnet",
        "פטור מותנה": "conditional_exemption",
        "הישבון": "drawback",
        "מחסן רישוי": "bonded_warehouse",
        "יבוא זמני": "temporary_import",
        "כניסה זמנית": "temporary_admission",
        "יבוא אישי": "personal_import",
        "נוהל מצהרים": "declarants_procedure",
        "מצהרים": "declarants",
        "מעקב מטענים": "cargo_tracking",
        "יצוא מוחזר": "returned_export",
        "יצוא זמני": "temporary_export",
        "פריט 810": "returned_export",
        "סוכן מכס": "customs_agent",
        "עמיל מכס": "customs_broker",
        "מניפסט": "manifest",
        "שטר מטען": "bill_of_lading",
        "השמדה": "destruction",
        "קניין רוחני": "intellectual_property",
        "יצוא אווירי": "export_air",
        "יצוא ימי": "export_sea",
        "גורם כלכלי מאושר": "authorized_economic_operator",
        "aeo": "authorized_economic_operator",
        "יבואן מאושר": "authorized_importer",
        "יבוא לרשות הפלסטינית": "pa_import",
    }

    for indicator, tag in chapter_indicators.items():
        if indicator.lower() in searchable:
            tags.add(tag)


def _detect_export_tags(searchable, tags):
    """Detect export-related content."""
    export_indicators = {
        "יצוא": "customs_export",
        "export": "customs_export",
        "רשימון יצוא": "export_declaration",
        "יצוא חופשי": "free_export",
        "נוהל יצוא חופשי": "free_export_procedure",
        "רישיון יצוא": "export_license",
        "פיקוח יצוא": "export_control",
        "יצוא מוחזר": "returned_export",
        "יצוא זמני": "temporary_export",
        "סיווג ביצוא": "classification_export",
        "פיקוח כימי": "export_control_chemical",
        "פיקוח ביולוגי": "export_control_biological",
        "פיקוח גרעיני": "export_control_nuclear",
        "יצוא אווירי": "export_air",
        "יצוא ימי": "export_sea",
        "גורם כלכלי מאושר": "authorized_economic_operator",
        "יבואן מאושר": "authorized_importer",
    }
    for indicator, tag in export_indicators.items():
        if indicator.lower() in searchable:
            tags.add(tag)


def _detect_geography(searchable, document, tags):
    for field in ["country", "country_of_origin", "origin", "source_country"]:
        val = document.get(field, "")
        if isinstance(val, str) and val:
            _tag_country(val.lower(), tags)

    url = document.get("source_url", document.get("url", ""))
    if url:
        url_lower = url.lower()
        if any(d in url_lower for d in [".gov.il", ".co.il", ".org.il"]):
            tags.add("israel")
            tags.add("source_israeli")
        elif ".europa.eu" in url_lower or "eur-lex" in url_lower:
            tags.add("eu")
            tags.add("source_foreign")
        elif ".wcoomd.org" in url_lower:
            tags.add("wco")
            tags.add("international")
            tags.add("source_foreign")


def _detect_data_origin(document, searchable, tags):
    if "source_israeli" in tags or "source_foreign" in tags:
        return
    for indicator in ["ישראל", "israel", ".gov.il", "מכס", "משרד", "רשות המסים",
                       "תעריפון", "צו יבוא", "נוהל מכס", "פקודת המכס", "אוגדן"]:
        if indicator in searchable:
            tags.add("source_israeli")
            tags.add("israel")
            return
    for indicator in ["eu regulation", "us customs", "european", "world customs", "wco"]:
        if indicator in searchable:
            tags.add("source_foreign")
            return


def _detect_file_type(document, tags):
    """Detect file type from file_path or url."""
    for field in ["file_path", "url", "source_url"]:
        val = document.get(field, "")
        if isinstance(val, str):
            if val.lower().endswith(".pdf"):
                tags.add("pdf_file")
            elif val.lower().endswith((".xlsx", ".xls", ".csv")):
                tags.add("excel_file")


def _tag_country(text, tags):
    country_map = {
        "ישראל": ("israel", "source_israeli"), "israel": ("israel", "source_israeli"),
        "eu": ("eu", "source_foreign"), "אירופ": ("eu", "source_foreign"),
        "usa": ("usa", "source_foreign"), "ארצות הברית": ("usa", "source_foreign"),
        "china": ("china", "source_foreign"), "סין": ("china", "source_foreign"),
        "uk": ("uk", "source_foreign"), "בריטניה": ("uk", "source_foreign"),
        "turkey": ("turkey", "source_foreign"), "טורקיה": ("turkey", "source_foreign"),
        "jordan": ("jordan", "source_foreign"), "ירדן": ("jordan", "source_foreign"),
        "egypt": ("egypt", "source_foreign"), "מצרים": ("egypt", "source_foreign"),
        "korea": ("korea", "source_foreign"), "japan": ("japan", "source_foreign"),
        "india": ("india", "source_foreign"),
        "מרקוסור": ("mercosur", "source_foreign"), "mercosur": ("mercosur", "source_foreign"),
    }
    for keyword, (geo_tag, origin_tag) in country_map.items():
        if keyword in text:
            tags.add(geo_tag)
            tags.add(origin_tag)
            return
    if text and "ישראל" not in text and "israel" not in text:
        tags.add("source_foreign")


def _replace_tag(tags, old_tag, new_tag):
    """Replace a tag in a list."""
    result = [t for t in tags if t != old_tag]
    if new_tag not in result:
        result.append(new_tag)
    return sorted(result)
