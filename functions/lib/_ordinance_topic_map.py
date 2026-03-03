"""
Ordinance Topic Map — semantic topic-to-article mapping.
=========================================================
Maps 25 customs domain topics to their relevant Customs Ordinance articles,
external laws, and practitioner notes. Used by context_engine._search_ordinance()
to find articles by topic BEFORE falling back to keyword search.

Session 78: Created with fixes for article number collisions (חשבון_מכר uses
regulation articles, not ordinance articles), 4 missing topics added.

CRITICAL: Articles 6-9א in חשבון_מכר are from תקנות המכס (regulations),
NOT from פקודת המכס (ordinance). Ordinance article 6 = "קביעת נמלים".
These regulation articles are marked with source="regulations".
"""

# ═══════════════════════════════════════════
#  TOPIC MAP — 25 topics
# ═══════════════════════════════════════════

TOPIC_MAP = {

    # ──────────────────────────────────────
    # 1. VALUATION (הערכה)
    # ──────────────────────────────────────
    "הערכת_מכס": {
        "aliases": [
            "הערכה", "הערכת", "שווי מכס", "ערך עסקה", "ערך מכסי",
            "customs valuation", "transaction value", "valuation",
            "שווי טובין", "ערך טובין", "שומת מכס",
        ],
        "articles": [
            "130", "131", "132", "133", "133א", "133ב",
            "133ג", "133ד", "133ה", "133ו", "133ז", "133ח", "133ט",
            "134", "134א", "135", "136",
        ],
        "chapter": 8,
        "notes": (
            "שיטת הערכה לפי 7 שיטות היררכיות (סעיף 130): "
            "(1) ערך עסקה, (2) ערך עסקה של טובין זהים, (3) ערך עסקה של טובין דומים, "
            "(4) שיטת הניכוי, (5) שיטת החישוב, (6) שיטת השארית, (7) שיטת השארית הגמישה. "
            "חובה לעבור בסדר — אין לדלג לשיטה מאוחרת אלא אם הקודמת לא חלה."
        ),
        "xml_search_terms": ["ערך עסקה", "הערכה", "valuation"],
        "external_laws": ["תקנות המכס (קביעת ערכם של טובין), תשס\"ז-2006"],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 2. COMMERCIAL INVOICE (חשבון מכר)
    # ──────────────────────────────────────
    "חשבון_מכר": {
        "aliases": [
            "חשבון מכר", "חשבונית מכר", "commercial invoice",
            "invoice requirements", "דרישות חשבונית", "פרטי חשבון",
            "חשבון עסקה", "חשבון ספק", "invoice",
        ],
        "articles": [
            # NOTE: These are REGULATION articles (תקנות המכס), NOT ordinance articles.
            # Ordinance article 6 = "קביעת נמלים" (port designation) — completely unrelated.
            "6", "7", "8", "9", "9א",
        ],
        "chapter": 8,  # Related to valuation chapter conceptually
        "source": "regulations",  # CRITICAL: these are regulation articles, not ordinance
        "regulation_name": "תקנות המכס (קביעת ערכם של טובין), תשס\"ז-2006",
        "regulation_content": (
            "10 פרטי חובה בחשבון מכר לפי תקנה 6:\n"
            "1. שם ומען המוכר\n"
            "2. שם ומען הקונה\n"
            "3. מספר החשבון ותאריכו\n"
            "4. תיאור הטובין — כולל שם מסחרי, דגם, מספר קטלוגי\n"
            "5. כמות הטובין — מספר יחידות, משקל, נפח\n"
            "6. מחיר ליחידה ומחיר כולל\n"
            "7. מטבע התשלום\n"
            "8. תנאי האספקה (אינקוטרמס) — FOB, CIF, CFR וכו'\n"
            "9. תנאי התשלום — מועד, אמצעי תשלום\n"
            "10. הצהרה על קשר בין הצדדים (אם קיים)\n\n"
            "תקנה 7: חשבון חייב להיות חתום על ידי המוכר\n"
            "תקנה 8: חשבון שלא עומד בדרישות — המכס רשאי לא לקבלו כבסיס להערכה\n"
            "תקנה 9: המכס רשאי לדרוש מסמכים נוספים לאימות ערך העסקה"
        ),
        "notes": (
            "חשבון מכר חייב להכיל 10 פרטים לפי תקנה 6 לתקנות המכס. "
            "חשבון חסר פרטים עלול להביא לאי-קבלתו כבסיס להערכה (תקנה 8). "
            "הפרטים הם: מוכר, קונה, מספר חשבון, תיאור, כמות, מחיר, מטבע, "
            "תנאי אספקה, תנאי תשלום, הצהרת קשר."
        ),
        "xml_search_terms": ["חשבון מכר", "commercial invoice", "תקנות הערכה"],
        "external_laws": ["תקנות המכס (קביעת ערכם של טובין), תשס\"ז-2006, תקנות 6-9א"],
    },

    # ──────────────────────────────────────
    # 3. IMPORT (ייבוא)
    # ──────────────────────────────────────
    "ייבוא": {
        "aliases": [
            "ייבוא", "ייבוא טובין", "import", "importing goods",
            "הצהרת ייבוא", "רשימון ייבוא", "import declaration",
            "יבוא", "ליבא",
        ],
        "articles": [
            "40", "41", "42", "43", "44", "45", "46", "47", "48",
            "49", "50", "51", "52", "53", "54", "54א", "55", "55א",
            "56", "57", "58", "59", "60", "61", "62", "63", "64",
            "65", "65א", "65ב", "65ג", "66", "67",
        ],
        "chapter": 4,
        "notes": (
            "פרק 4 — ייבוא טובין: הצהרות ייבוא (סעיפים 40-55), שחרור טובין (56-61), "
            "רשימון ייבוא (62-63), אחריות שילוחית (64), ועוד. "
            "סעיף 62 — רשימון ייבוא חייב להיות מוגש תוך 14 יום. "
            "סעיף 63 — פרטי הרשימון."
        ),
        "xml_search_terms": ["ייבוא", "import", "רשימון"],
        "external_laws": ["צו יבוא חופשי, תשע\"ד-2014", "תקנות המכס"],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 4. EXPORT (ייצוא)
    # ──────────────────────────────────────
    "ייצוא": {
        "aliases": [
            "ייצוא", "ייצוא טובין", "export", "exporting goods",
            "הצהרת ייצוא", "רשימון ייצוא", "export declaration",
            "יצוא", "ליצא",
        ],
        "articles": [
            "100", "101", "102", "103", "104", "105", "106", "107",
            "108", "109", "110", "111", "112", "113", "114", "115",
            "116", "117", "118", "119",
        ],
        "chapter": 6,
        "notes": (
            "פרק 6 — ייצוא טובין (סעיפים 100-119). "
            "סעיף 100 — הצהרת ייצוא חייבת להיות מוגשת לפני הטעינה. "
            "סעיפים 107-109 — טעינה, פיקוח, וקנסות. "
            "סעיף 116 — ביטול הצהרת ייצוא."
        ),
        "xml_search_terms": ["ייצוא", "export", "רשימון ייצוא"],
        "external_laws": ["צו יצוא חופשי"],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 5. WAREHOUSING (מחסני ערובה)
    # ──────────────────────────────────────
    "מחסני_ערובה": {
        "aliases": [
            "מחסן ערובה", "מחסני ערובה", "bonded warehouse", "warehouse",
            "החסנה", "אחסנה", "warehousing", "customs warehouse",
            "מחסן מכס", "מחסן רשוי",
        ],
        "articles": [
            "68", "69", "70", "71", "72", "73", "74", "75", "76",
            "77", "78", "79", "80", "81", "82", "83", "84", "85",
            "86", "87", "88", "89", "90", "91", "92", "93", "94",
            "95", "96", "97", "98", "99",
        ],
        "chapter": 5,
        "notes": (
            "פרק 5 — החסנת טובין (סעיפים 68-99). "
            "סעיף 68 — הגדרת מחסן ערובה ומחסן רשוי. "
            "סעיף 76 — תקופת החסנה מרבית. "
            "סעיפים 90-99 — מחסנים ציבוריים."
        ),
        "xml_search_terms": ["מחסן ערובה", "החסנה", "bonded warehouse"],
        "external_laws": ["תקנות המכס (מחסני ערובה)"],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 6. CLASSIFICATION (סיווג)
    # ──────────────────────────────────────
    "סיווג": {
        "aliases": [
            "סיווג", "סיווג טובין", "classification", "HS code",
            "פרט מכסי", "פרט מכס", "tariff heading", "tariff classification",
            "קוד מכס", "סיווג מכסי",
        ],
        "articles": ["2", "130"],
        "chapter": 1,
        "notes": (
            "סעיף 2 — תעריף המכס הוא חלק בלתי נפרד מפקודת המכס. "
            "הסיווג נקבע לפי כללי הפרשנות (GIR 1-6) שבראש התעריף. "
            "נוהל סיווג טובין (נוהל 3) מפרט את הליך הבקשה לפרה-רולינג."
        ),
        "xml_search_terms": ["סיווג", "classification", "GIR", "כללי פרשנות"],
        "external_laws": [
            "תעריף המכס (צו תעריף המכס והפטורים)",
            "אמנת מערכת התיאור והקידוד המתואמים (HS Convention)",
        ],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 7. FTA / ORIGIN (הסכמי סחר / מקור)
    # ──────────────────────────────────────
    "הסכמי_סחר": {
        "aliases": [
            "הסכם סחר", "הסכם סחר חופשי", "FTA", "free trade",
            "כללי מקור", "rules of origin", "תעודת מקור",
            "certificate of origin", "EUR.1", "ארץ מקור",
            "origin", "preferential", "העדפה מכסית",
        ],
        "articles": ["130", "133ד"],
        "chapter": 8,
        "notes": (
            "הסכמי סחר חופשי מזכים בשיעור מכס מופחת או פטור. "
            "נדרשת תעודת מקור (EUR.1 / הצהרת מקור / הצהרת יצואן מאושר). "
            "כללי מקור קובעים אחוז ערך מוסף מקומי מינימלי."
        ),
        "xml_search_terms": ["הסכם סחר", "FTA", "כללי מקור", "EUR.1"],
        "external_laws": [
            "צו תעריף המכס — תוספות 2-10 (שיעורי העדפה)",
            "חוק הסכמי סחר (הטבות מכס), תשכ\"ח-1968",
        ],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 8. DUTY PAYMENT (תשלומי מכס)
    # ──────────────────────────────────────
    "תשלומי_מכס": {
        "aliases": [
            "תשלום מכס", "תשלומי מכס", "duty payment", "customs duty",
            "מסי יבוא", "מסי מכס", "שיעור מכס", "duty rate",
            "גביית מכס", "חישוב מכס",
        ],
        "articles": [
            "123א", "123ב", "137", "138", "139", "140", "141",
            "142", "143", "144", "145", "146", "147", "148",
            "149", "150", "151", "152", "153", "154", "155",
        ],
        "chapter": 8,
        "notes": (
            "סעיפים 123א-123ב — הגדרות תשלומי מכס. "
            "סעיפים 137-155 — גביית מכס, ערובות, הנחות, תשלום ביתר/בחסר, "
            "ריבית, השגות, ועוד. סעיף 153 — ערעור על שומה."
        ),
        "xml_search_terms": ["תשלומי מכס", "duty", "גביית מכס"],
        "external_laws": ["חוק מסים עקיפים (מס קניה)", "חוק מע\"מ"],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 9. CUSTOMS AGENTS (סוכנים)
    # ──────────────────────────────────────
    "סוכני_מכס": {
        "aliases": [
            "סוכן מכס", "סוכני מכס", "customs agent", "customs broker",
            "עמיל מכס", "עמילי מכס", "מתווך מכס", "broker",
            "עמיל", "סוכן",
        ],
        "articles": ["168", "169", "170", "171"],
        "chapter": 11,
        "notes": (
            "פרק 11 (סעיפים 168-171) — רישוי סוכנים (עמילי מכס). "
            "סעיף 168 — רישיון סוכן. "
            "חוק סוכני המכס, תשכ\"ה-1964 מרחיב את ההסדר."
        ),
        "xml_search_terms": ["סוכן מכס", "עמיל מכס", "customs agent"],
        "external_laws": ["חוק סוכני המכס, תשכ\"ה-1964"],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 10. SUPERVISION & DECLARATIONS (פיקוח והצהרות)
    # ──────────────────────────────────────
    "פיקוח_והצהרות": {
        "aliases": [
            "פיקוח", "בדיקה", "הצהרה", "ערובה",
            "supervision", "inspection", "declarations", "security",
            "בדיקת מכס", "ביקורת מכס", "customs inspection",
        ],
        "articles": [
            "14", "15", "16", "17", "18", "19", "20", "21", "22",
            "23", "24", "25", "26", "27", "28", "29", "30", "30א",
            "31", "32", "33", "34", "35", "36", "37", "38", "39", "39א",
        ],
        "chapter": 3,
        "notes": (
            "פרק 3 — פיקוח, בדיקה, הצהרות וערובה (סעיפים 14-39א). "
            "סעיף 14 — כניסת כלי שיט לנמל. "
            "סעיפים 20-29 — הצהרות מטען, מניפסט, חוסרים. "
            "סעיפים 30-39 — ערובות ובטחונות."
        ),
        "xml_search_terms": ["פיקוח", "בדיקה", "הצהרה"],
        "external_laws": [],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 11. ADDITIONS TO VALUE (תוספות לערך)
    # ──────────────────────────────────────
    "תוספות_לערך": {
        "aliases": [
            "תוספות לערך", "additions to value", "additions",
            "עמלה", "commission", "royalty", "תמלוגים",
            "עלויות אריזה", "packing costs", "דמי תיווך",
            "assists", "סיוע",
        ],
        "articles": ["133", "133א", "133ב", "133ג", "133ד", "133ה"],
        "chapter": 8,
        "notes": (
            "סעיף 133 — 5 קטגוריות תוספות לערך עסקה: "
            "(1) עמלות ודמי תיווך (133א), "
            "(2) עלות אריזה ומכלים (133ב), "
            "(3) סיוע (assists) — חומרים, כלים, תכניות (133ג), "
            "(4) תמלוגים ודמי רישיון (133ד), "
            "(5) תמורה מהמכירה החוזרת (133ה)."
        ),
        "xml_search_terms": ["תוספות לערך", "additions", "133"],
        "external_laws": ["תקנות המכס (קביעת ערכם של טובין)"],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 12. RELATED PARTIES (צדדים קשורים)
    # ──────────────────────────────────────
    "צדדים_קשורים": {
        "aliases": [
            "צדדים קשורים", "related parties", "related persons",
            "קשרים בין צדדים", "עסקת קשורים", "transfer pricing",
            "בין חברות קשורות", "affiliated", "הצהרת קשר",
        ],
        "articles": ["131", "132", "133ד"],
        "chapter": 8,
        "notes": (
            "סעיף 131 — הגדרת אנשים קשורים (7 מקרים). "
            "סעיף 132 — 4 תנאים לקבלת ערך עסקה בצדדים קשורים. "
            "עסקה בין קשורים לא נפסלת אוטומטית — נדרש מבחן קרבה."
        ),
        "xml_search_terms": ["צדדים קשורים", "related parties", "קשר"],
        "external_laws": [],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 13. ASSESSMENT APPEAL (ערעור שומה)
    # ──────────────────────────────────────
    "ערעור_שומה": {
        "aliases": [
            "ערעור", "ערעור שומה", "השגה", "assessment appeal",
            "appeal", "objection", "ועדת ערר", "בית משפט",
            "חילוקי דעות",
        ],
        "articles": [
            "153", "154",  # Ch 8 — valuation disputes
            "224", "225", "226", "227", "228", "229", "230",  # Ch 14 — prosecutions
            "223טז",  # Ch 13א — admin appeal
        ],
        "chapter": 14,
        "notes": (
            "סעיף 153 — ערעור על שומת מכס: 30 יום להגשת השגה. "
            "סעיף 154 — ערעור לבית משפט מחוזי. "
            "פרק 14 (סעיפים 224-230) — סמכות שיפוט, ראיות, ועונשים. "
            "סעיף 223טז — ערעור מינהלי על קנס כספי (פרק 13א)."
        ),
        "xml_search_terms": ["ערעור", "השגה", "appeal", "שומה"],
        "external_laws": [],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 14. PENALTIES & OFFENSES (עבירות ועונשין)
    # ──────────────────────────────────────
    "עבירות_מכס": {
        "aliases": [
            "עבירה", "עבירות מכס", "עונש", "עונשין", "קנס",
            "offense", "penalty", "smuggling", "הברחה",
            "חילוט", "forfeiture", "customs offense",
        ],
        "articles": [
            # Chapter 13: Forfeitures and Penalties (203-223)
            "203", "203א", "204", "205", "206", "207", "208", "209",
            "210", "211", "212", "213", "214", "215", "216", "217",
            "218", "219", "220", "221", "222", "223",
            # Chapter 13א: Administrative Enforcement (223א-223יח)
            "223א", "223ב", "223ג", "223ד", "223ה", "223ו", "223ז",
            "223ח", "223ט", "223יא", "223יב", "223יג",
            "223יד", "223טו", "223טז", "223יז", "223יח",
            # Note: 223י = "223יא" 10th article — already included
        ],
        "chapter": 13,
        "notes": (
            "פרק 13 (סעיפים 203-223) — חילוטין ועונשין: הברחה, הצהרות כוזבות, "
            "מסמכים מזויפים, העלמת מכס. "
            "סעיף 203 — חילוט טובין מוברחים. "
            "סעיף 211 — הברחה — עונש מאסר עד 7 שנים. "
            "פרק 13א (223א-223יח) — אכיפה מינהלית: קנסות כספיים ללא הרשעה פלילית."
        ),
        "xml_search_terms": ["עבירה", "עונש", "חילוט", "הברחה", "penalty"],
        "external_laws": ["חוק העונשין, תשל\"ז-1977 (לעניין שותפות לעבירה)"],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 15. DRAWBACK & TEMPORARY ADMISSION (הישבון)
    # ──────────────────────────────────────
    "הישבון": {
        "aliases": [
            "הישבון", "drawback", "החזר מכס", "customs refund",
            "כניסה זמנית", "temporary admission", "יבוא זמני",
            "ATA carnet", "החזר",
        ],
        "articles": [
            "156", "157", "158", "159", "160", "160א", "160ב", "160ג",
            "161", "162", "162א", "162ב", "162ג",
        ],
        "chapter": 9,
        "notes": (
            "פרק 9 (סעיפים 156-162ג) — הישבון וכניסה זמנית. "
            "סעיף 156 — הישבון מלא על טובין שיוצאו מחדש תוך 6 חודשים. "
            "סעיף 159 — אישור הישבון בתנאים. "
            "סעיפים 160-160ג — כניסה זמנית (ATA Carnet)."
        ),
        "xml_search_terms": ["הישבון", "drawback", "כניסה זמנית"],
        "external_laws": ["תקנות המכס (הישבון)", "אמנת איסטנבול (ATA)"],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 16. REGULATORY REQUIREMENTS (רגולציה)
    # ──────────────────────────────────────
    "רגולציה": {
        "aliases": [
            "רגולציה", "אישור רגולטורי", "regulatory", "permit",
            "רישיון יבוא", "import license", "תקן", "standard",
            "אישור משרד", "ministry approval", "תקן ישראלי",
        ],
        "articles": ["41", "55", "231א"],
        "chapter": 4,
        "notes": (
            "סעיף 41 — הגבלות על ייבוא (רישיונות, תקנים, אישורים). "
            "צו יבוא חופשי מפרט את הגופים הרגולטוריים: "
            "משרד הכלכלה, מכון התקנים, משרד הבריאות, משרד החקלאות, "
            "משרד התחבורה, המשרד להגנת הסביבה, ועוד."
        ),
        "xml_search_terms": ["רגולציה", "רישיון", "אישור", "תקן"],
        "external_laws": [
            "צו יבוא חופשי, תשע\"ד-2014",
            "חוק התקנים, תשי\"ג-1953",
        ],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 17. DANGEROUS GOODS (מסוכנים)
    # ──────────────────────────────────────
    "טובין_מסוכנים": {
        "aliases": [
            "טובין מסוכנים", "חומרים מסוכנים", "dangerous goods",
            "hazardous", "IMDG", "חומ\"ס", "ADR",
            "סיווג סיכון", "hazard class",
        ],
        "articles": ["41", "55", "208"],
        "chapter": 4,
        "notes": (
            "ייבוא חומרים מסוכנים דורש אישור מיוחד (סעיף 41). "
            "סיווג לפי IMDG (ימי), ADR (יבשתי), IATA-DGR (אווירי). "
            "9 מחלקות סיכון (1-9). חובת MSDS."
        ),
        "xml_search_terms": ["מסוכנים", "IMDG", "dangerous goods"],
        "external_laws": ["חוק החומרים המסוכנים, תשנ\"ג-1993"],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 18. PURCHASE TAX / VAT (מס קניה / מע"מ)
    # ──────────────────────────────────────
    "מס_קניה": {
        "aliases": [
            "מס קניה", "purchase tax", "מע\"מ", "VAT",
            "מס ערך מוסף", "value added tax",
            "שיעור מס", "tax rate",
        ],
        "articles": ["137", "140"],
        "chapter": 8,
        "notes": (
            "מס קניה מוטל לפי חוק מסים עקיפים ומחושב על ערך CIF + מכס. "
            "מע\"מ מחושב על ערך CIF + מכס + מס קניה. "
            "שיעור מע\"מ נוכחי: 18%. "
            "חישוב: CIF → +מכס → +מס קניה → +מע\"מ."
        ),
        "xml_search_terms": ["מס קניה", "purchase tax", "מע\"מ", "VAT"],
        "external_laws": [
            "חוק מסים עקיפים (מס קניה ומס בולים), תשי\"ב-1952",
            "חוק מס ערך מוסף, תשל\"ו-1975",
        ],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 19. ELECTRONIC REPORTING (דיווח אלקטרוני)
    # ──────────────────────────────────────
    "דיווח_אלקטרוני": {
        "aliases": [
            "דיווח אלקטרוני", "electronic reporting", "שידור אלקטרוני",
            "מערכת שער עולמי", "shaar olami", "electronic declaration",
            "EDI", "ASYCUDA",
        ],
        "articles": [
            "230א", "230ב", "230ג", "230ד", "230ה", "230ו", "230ז", "230ח",
        ],
        "chapter": "14א",
        "notes": (
            "פרק 14א (סעיפים 230א-230ח) — דיווח אלקטרוני. "
            "סעיף 230א — הגדרות: מסמך אלקטרוני, חתימה אלקטרונית. "
            "סעיף 230ב — חובת דיווח אלקטרוני לגורמים שקבע שר האוצר. "
            "מערכת שער עולמי (ASYCUDA) היא מערכת הדיווח הראשית."
        ),
        "xml_search_terms": ["דיווח אלקטרוני", "שער עולמי", "ASYCUDA"],
        "external_laws": ["חוק חתימה אלקטרונית, תשס\"א-2001"],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 20. ADMINISTRATION (מינהל מכס)
    # ──────────────────────────────────────
    "מינהל_מכס": {
        "aliases": [
            "מינהל", "מנהל המכס", "administration",
            "director of customs", "גובה מכס", "customs collector",
            "תקנות מכס", "customs regulations",
        ],
        "articles": [
            "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13",
        ],
        "chapter": 2,
        "notes": (
            "פרק 2 (סעיפים 3-13) — מינהל: סמכויות מנהל המכס, "
            "קביעת נמלים ומקומות מכס, שעות עבודה, הצהרות. "
            "סעיף 3 — מינוי מנהל המכס. "
            "סעיף 6 — קביעת נמלים."
        ),
        "xml_search_terms": ["מינהל", "מנהל המכס"],
        "external_laws": [],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 21. MISCELLANEOUS / GENERAL (הוראות שונות)
    # ──────────────────────────────────────
    "הוראות_שונות": {
        "aliases": [
            "הוראות שונות", "miscellaneous", "כלליות",
            "הוראות כלליות", "general provisions",
        ],
        "articles": [
            "231", "231א", "232", "232א", "233", "234", "235",
            "236", "237", "238", "238א", "239", "239א", "239ב",
            "240", "241",
        ],
        "chapter": 15,
        "notes": (
            "פרק 15 (סעיפים 231-241) — הוראות שונות: "
            "סעיף 231 — שמירת מסמכים. "
            "סעיף 232 — שומות רטרואקטיביות. "
            "סעיף 238 — סמכות שר האוצר להתקין תקנות."
        ),
        "xml_search_terms": ["הוראות שונות"],
        "external_laws": [],
        "source": "ordinance",
    },

    # ══════════════════════════════════════
    # NEW TOPICS (4 missing from original)
    # ══════════════════════════════════════

    # ──────────────────────────────────────
    # 22. SHIP'S STORES (צידת אניה)
    # ──────────────────────────────────────
    "צידת_אניה": {
        "aliases": [
            "צידת אניה", "צידה", "ship stores", "ship's stores",
            "provisions", "צידת כלי שיט",
        ],
        "articles": ["120", "121", "122", "123"],
        "chapter": 7,
        "notes": (
            "פרק 7 (סעיפים 120-123) — צידת אניה. "
            "סעיף 120 — צידה לנוסעים/צוות/שימוש האניה בלבד. "
            "סעיפים 121-122 — הגבלות על צידה בתנועה חופית. "
            "סעיף 123 — הגבלות על צידה ביבשה."
        ),
        "xml_search_terms": ["צידת אניה", "ship stores"],
        "external_laws": [],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 23. COASTAL TRADE (סחר חוף)
    # ──────────────────────────────────────
    "סחר_חוף": {
        "aliases": [
            "סחר חוף", "סחר חופים", "coastal trade", "cabotage",
            "סחר בין נמלים", "תנועה חופית",
        ],
        "articles": ["163", "164", "165", "166", "167"],
        "chapter": 10,
        "notes": (
            "פרק 10 (סעיפים 163-167) — סחר החוף. "
            "סעיף 163 — הגדרת תנועה חופית (בין נמלים ישראליים ללא נמל זר). "
            "סעיפים 164-167 — פיקוח, מגבלות, רישיונות."
        ),
        "xml_search_terms": ["סחר חוף", "coastal trade"],
        "external_laws": [],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 24. CUSTOMS OFFICER POWERS (סמכויות פקיד מכס)
    # ──────────────────────────────────────
    "סמכויות_פקיד_מכס": {
        "aliases": [
            "סמכויות", "סמכויות פקיד מכס", "powers", "customs officer",
            "חיפוש", "search", "עיכוב", "seizure", "תפיסה",
            "סמכות חיפוש", "סמכות עיכוב", "סמכות תפיסה",
        ],
        "articles": [
            "172", "173", "174", "175", "176", "177", "178", "179",
            "180", "181", "182", "183", "184", "185", "186", "187",
            "188", "189", "190", "191", "192", "193", "194", "195",
            "196", "197", "198", "199", "200", "200א", "200ב",
            "200ג", "200ד", "200ה", "200ו", "200ז", "201", "202",
        ],
        "chapter": 12,
        "notes": (
            "פרק 12 (סעיפים 172-202) — סמכויות פקידי מכס. "
            "הפרק הגדול ביותר (38 סעיפים). "
            "סעיף 172 — סמכות מרדף וירי (אחרי אזהרה). "
            "סעיפים 180-190 — סמכויות חיפוש (כלי רכב, אנשים, מטענים). "
            "סעיפים 195-200 — תפיסת טובין ומסמכים. "
            "סעיפים 200א-200ז — סמכויות מיוחדות (חדירה למחשבים, צילום)."
        ),
        "xml_search_terms": ["סמכויות", "חיפוש", "תפיסה", "powers"],
        "external_laws": ["חוק סדר הדין הפלילי (סמכויות אכיפה – מעצרים)"],
        "source": "ordinance",
    },

    # ──────────────────────────────────────
    # 25. ADMINISTRATIVE ENFORCEMENT (אכיפה מינהלית)
    # ──────────────────────────────────────
    "אכיפה_מינהלית": {
        "aliases": [
            "אכיפה מינהלית", "administrative enforcement",
            "קנס מינהלי", "administrative fine", "עיצום כספי",
            "monetary sanction", "אכיפה ללא הרשעה",
        ],
        "articles": [
            "223א", "223ב", "223ג", "223ד", "223ה", "223ו", "223ז",
            "223ח", "223ט", "223יא", "223יב", "223יג",
            "223יד", "223טו", "223טז", "223יז", "223יח",
        ],
        "chapter": "13א",
        "notes": (
            "פרק 13א (סעיפים 223א-223יח) — אכיפה מינהלית. "
            "הליך חלופי להליך הפלילי — קנסות כספיים ללא הרשעה. "
            "סעיף 223ב — עבירות שניתן להטיל עליהן קנס מינהלי. "
            "סעיף 223טז — ערעור על קנס מינהלי."
        ),
        "xml_search_terms": ["אכיפה מינהלית", "עיצום כספי", "קנס מינהלי"],
        "external_laws": ["חוק העבירות המינהליות, תשמ\"ו-1985"],
        "source": "ordinance",
    },
}


# ═══════════════════════════════════════════
#  SEARCH FUNCTIONS
# ═══════════════════════════════════════════

# Minimum alias length for direct substring matching.
# Shorter aliases need word boundary checks to avoid false positives.
_MIN_ALIAS_LEN = 4


def search_ordinance_by_topic(text):
    """
    Search the topic map for topics matching the given text.

    Returns a list of dicts, each with:
      - topic_key: internal topic identifier
      - topic_data: the full topic dict from TOPIC_MAP
      - matched_alias: the alias that triggered the match
      - articles: list of article numbers
      - source: "ordinance" or "regulations"

    Short aliases (< 4 chars) require word boundary matching to avoid
    false positives (e.g., "VAT" matching "elevator").
    """
    if not text or not isinstance(text, str):
        return []

    text_lower = text.lower()
    results = []
    seen_topics = set()

    for topic_key, topic_data in TOPIC_MAP.items():
        if topic_key in seen_topics:
            continue

        matched_alias = None
        for alias in topic_data.get("aliases", []):
            alias_lower = alias.lower()

            if len(alias) < _MIN_ALIAS_LEN:
                # Short alias — require word boundary
                import re
                pattern = r'(?:^|[\s,;.!?\-(])' + re.escape(alias_lower) + r'(?:$|[\s,;.!?\-)])'
                if re.search(pattern, text_lower):
                    matched_alias = alias
                    break
            else:
                # Normal alias — substring match
                if alias_lower in text_lower:
                    matched_alias = alias
                    break

        if matched_alias:
            seen_topics.add(topic_key)
            results.append({
                "topic_key": topic_key,
                "topic_data": topic_data,
                "matched_alias": matched_alias,
                "articles": topic_data.get("articles", []),
                "source": topic_data.get("source", "ordinance"),
            })

    return results


def get_topic_notes(topic_key):
    """Get practitioner notes for a topic."""
    topic = TOPIC_MAP.get(topic_key)
    if not topic:
        return ""
    return topic.get("notes", "")


def get_topic_external_law(topic_key):
    """Get external law references for a topic."""
    topic = TOPIC_MAP.get(topic_key)
    if not topic:
        return []
    return topic.get("external_laws", [])


def get_framework_articles(topic_key):
    """Get framework order article numbers relevant to a topic."""
    topic = TOPIC_MAP.get(topic_key)
    if not topic:
        return []
    return topic.get("articles", [])


def get_topic_xml_terms(topic_key):
    """Get XML search terms for a topic."""
    topic = TOPIC_MAP.get(topic_key)
    if not topic:
        return []
    return topic.get("xml_search_terms", [])


def get_topic_map_stats():
    """Return statistics about the topic map."""
    total_topics = len(TOPIC_MAP)
    total_articles = set()
    total_aliases = 0
    topics_by_source = {"ordinance": 0, "regulations": 0}

    for topic_data in TOPIC_MAP.values():
        total_articles.update(topic_data.get("articles", []))
        total_aliases += len(topic_data.get("aliases", []))
        src = topic_data.get("source", "ordinance")
        topics_by_source[src] = topics_by_source.get(src, 0) + 1

    return {
        "total_topics": total_topics,
        "total_unique_articles": len(total_articles),
        "total_aliases": total_aliases,
        "topics_by_source": topics_by_source,
    }
