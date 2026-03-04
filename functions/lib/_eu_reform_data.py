"""EU Reform "מה שטוב לאירופה" — full structured data parsed from gov.il XMLs.

Source files:
  - downloads/govil/EU_Reform_Information.xml (3 pages, effective 2025-01-01)
  - downloads/govil/EU_Reform_News_040226.xml (2 pages, update 2026-02-04)

This module provides in-memory search over all EU Reform content at zero Firestore cost.
"""

# ============================================================================
# EU REFORM DOCUMENTS
# ============================================================================

EU_REFORM_DOCS = {
    "eu_reform_information": {
        "title_he": 'רפורמת "מה שטוב לאירופה טוב לישראל"',
        "title_en": "EU Reform: What's Good for Europe is Good for Israel",
        "source_url": "https://www.gov.il/he/pages/eu-reform-information",
        "effective_date": "2025-01-01",
        "legal_basis": "החלטת ממשלה 2118",
        "pages": 3,
        "full_text": (
            'רפורמת "מה שטוב לאירופה טוב לישראל"\n\n'
            'רפורמת הייבוא "מה שטוב לאירופה טוב לישראל" נכנסה לתוקף ב-1 בינואר 2025. '
            'הרפורמה מאפשרת ליבואנים ישראלים לייבא מוצרים על בסיס תקנים אירופיים (CE) '
            'ללא צורך בבדיקה נוספת של מכון התקנים הישראלי (מת"י/ISI), בתנאי שהדירקטיבה '
            'הרלוונטית אומצה ונכנסה לתוקף בישראל.\n'
            'הרפורמה מכירה ב-43 רגולציות של האיחוד האירופי ומשפיעה על כ-444 תקנים '
            'ישראליים מתוך 573 תקנים חובה.\n\n'
            'מטרות הרפורמה\n'
            '1. הסרת חסמי ייבוא והפחתת עלויות — חיסכון של כ-8 מיליארד שקלים בשנה למשק\n'
            '2. ביטול בדיקות כפולות — אין צורך באישור נוסף ממכון התקנים הישראלי למוצרים עם CE\n'
            '3. שחרור מואץ במכס — שחרור תוך יום עסקים אחד למוצרים העומדים בתנאי הרפורמה\n'
            '4. הגברת התחרות והרחבת מגוון המוצרים בשוק הישראלי\n'
            '5. הוזלת יוקר המחיה לצרכן\n\n'
            'דירקטיבות אירופיות שאומצו\n'
            'הרפורמה מאמצת דירקטיבות אירופיות בתחומים הבאים:\n'
            '• REACH — בטיחות כימיקלים\n'
            '• LVD (Low Voltage Directive) — ציוד חשמלי במתח נמוך\n'
            '• EMC (Electromagnetic Compatibility) — תאימות אלקטרומגנטית\n'
            '• PPE (Personal Protective Equipment) — ציוד מגן אישי\n'
            '• בטיחות צעצועים (החל מפברואר 2025)\n'
            '• חומרים הבאים במגע עם מזון (החל ממרץ 2025)\n'
            '• אופניים חשמליים וציוד רפואי (צפויים בהמשך)\n\n'
            'קטגוריות מוצרים\n'
            'הרפורמה חלה על מגוון רחב של מוצרים:\n'
            '• מכשירי חשמל ביתיים\n'
            '• מוצרי ניקוי וטיפוח\n'
            '• מחשבים ומוצרי אלקטרוניקה\n'
            '• מכשירי תקשורת\n'
            '• ציוד בטיחות (קסדות, ביגוד מגן)\n'
            '• מוצרי ילדים\n'
            '• חומרים מבוססי עץ\n'
            '• אירוסולים לא מסוכנים\n'
            '• משקפי שמש\n'
            '• קוסמטיקה\n'
            '• צעצועים\n'
            '• פריטי בית ומכשירים חשמליים קטנים\n\n'
            'מוצרים שאינם כלולים ברפורמה\n'
            '• מזון ומשקאות\n'
            '• רכבים מנועיים\n'
            '• פריטי בטיחות אש כללית (למעט ציוד כיבוי נייד)\n'
            '• מוצרי קבוצה 1 הדורשים בדיקת מעבדה מוסמכת\n\n'
            'רמות סיכון ודרישות תיעוד\n'
            'סיכון נמוך: הצהרה עצמית של היבואן מספיקה\n'
            'סיכון בינוני: יש לאשר שהמוצר נמכר בשוק האירופי או להמציא הצהרת תאימות מהיצרן\n'
            'סיכון גבוה: דרישות מחמירות כולל מוצרי תינוקות, פלסטיק במגע עם מזון, וחומרי ניקוי מסוימים\n\n'
            'נוהל מכס — קוד 65\n'
            'לשחרור מכס נכון, יש לסמן את הרשימון בקוד 65 (מסלול רפורמה). '
            'הקוד מציין שהמוצר מיובא במסלול הרפורמה על בסיס תאימות לדירקטיבות אירופיות.\n'
            'יבואנים אינם נדרשים עוד להוכיח תאימות לתקנים ישראלים, אך רשאים לעשות כן מרצון.\n\n'
            'שחרור מכס עם מסמכי מוכר (Seller Documents)\n'
            'אחד החידושים המשמעותיים של הרפורמה הוא האפשרות לשחרר סחורה עם מסמכי המוכר בלבד, '
            'ללא צורך באישורים נוספים ממכון התקנים:\n'
            '• הצהרת תאימות מהיצרן (Declaration of Conformity - DoC)\n'
            '• תעודת CE מהיצרן או מגוף נוטיפייד (Notified Body)\n'
            '• תיעוד טכני מלא בעברית\n'
            '• הצהרת יבואן\n\n'
            'לוח זמנים — פעימות יישום\n'
            'פעימה 1: ינואר 2025 — כניסה לתוקף ראשונית, 23 דירקטיבות\n'
            'פעימה 2: פברואר 2025 — דירקטיבת בטיחות צעצועים\n'
            'פעימה 3: מרץ 2025 — חומרים במגע עם מזון\n'
            'פעימות נוספות: עד ינואר 2028 — הרחבה ל-43 דירקטיבות\n'
            'תקופות מעבר: חלק מהדירקטיבות כוללות תקופת מעבר של עד 3 שנים\n\n'
            'אכיפה\n'
            'פיקוח שוטף באמצעות ביקורות מסחר אקראיות. הפרות גוררות עיצומים מנהליים, '
            'קנסות או העמדה לדין פלילי בהתאם לחומרה.\n\n'
            'סטטיסטיקה\n'
            'סקר משרד הכלכלה: 90% מ-400 יבואנים שנסקרו מעדיפים את המסלול האירופי '
            'על פני עמידה בתקן ישראלי מסורתי.'
        ),
    },

    "eu_reform_news_022026": {
        "title_he": "עדכון רפורמת הייבוא — פברואר 2026",
        "title_en": "EU Import Reform Update — February 2026",
        "source_url": "https://www.gov.il/he/pages/news-040226",
        "effective_date": "2026-02-04",
        "legal_basis": None,
        "pages": 2,
        "full_text": (
            'עדכון רפורמת הייבוא "מה שטוב לאירופה טוב לישראל" — פברואר 2026\n\n'
            'משרד הכלכלה והתעשייה מפרסם עדכון בנוגע להתקדמות רפורמת '
            '"מה שטוב לאירופה טוב לישראל" ופעימות יישום חדשות.\n\n'
            'פטור מבדיקות מכון התקנים (ISI)\n'
            'הרפורמה מבטלת את חובת הבדיקה במכון התקנים הישראלי עבור מוצרים העומדים '
            'בדירקטיבות אירופיות שאומצו. יבואנים רשאים לשחרר סחורה מהמכס על בסיס '
            'תעודת CE אירופית ומסמכי המוכר, ללא צורך באישור מכון התקנים.\n'
            'מוצרים שנכללו בפטור ISI כוללים: מכשירי חשמל ביתיים, אלקטרוניקה, '
            'ציוד מגן אישי, קוסמטיקה, צעצועים, ומוצרים מגעם מזון.\n\n'
            'שחרור מכס עם מסמכי מוכר (Seller Documents)\n'
            'חידוש מרכזי ברפורמה — אפשרות שחרור מכס על בסיס מסמכי המוכר בלבד:\n'
            '1. הצהרת תאימות (Declaration of Conformity) מהיצרן\n'
            '2. תעודת CE מהיצרן או מגוף נוטיפייד\n'
            '3. תיעוד טכני\n'
            '4. הצהרת יבואן\n'
            'הסימון ברשימון: קוד 65 — מציין ייבוא במסלול הרפורמה\n\n'
            'סטטוס פעימות יישום (נכון לפברואר 2026)\n'
            'פעימה 1 (ינואר 2025): 23 דירקטיבות — פעילה ✓\n'
            'פעימה 2 (פברואר 2025): בטיחות צעצועים — פעילה ✓\n'
            'פעימה 3 (מרץ 2025): חומרים במגע עם מזון — פעילה ✓\n'
            'פעימה 4 (יולי 2026): הרחבה נוספת — צפויה\n'
            'פעימה 5 (ינואר 2028): השלמה ל-43 דירקטיבות — צפויה\n\n'
            'רפורמת הייבוא האישי — עדכון פברואר 2026\n'
            'סף הפטור ממע"מ על ייבוא אישי: הועלה ל-150 דולר (מ-75 דולר) בדצמבר 2024, '
            'אך הצו נדרש לאישור הכנסת עד 23 בפברואר 2026.\n'
            'לאחר שהצו לא אושר בכנסת, סף הפטור חזר ל-75 דולר עד 1 ביוני 2026 '
            'בהתאם להחלטת ועדת הכספים.\n'
            'חבילות שהוזמנו בתקופת הפטור (150 דולר) אך הגיעו לאחר ביטולו — '
            'נבדקות על ידי רשות המכס לפי מועד ההזמנה.\n\n'
            'השלכות על עמילי מכס\n'
            'על עמילי מכס לשים לב ל:\n'
            '1. סימון רשימון בקוד 65 עבור מוצרים במסלול הרפורמה\n'
            '2. בדיקת סטטוס הדירקטיבה — לא כל דירקטיבות CE פעילות בישראל\n'
            '3. מוצרי קבוצה 1 אינם כלולים ברפורמה ודורשים בדיקת מעבדה\n'
            '4. חומרים מבוססי EU שנרכשו לפני הפעימה הרלוונטית — לא זכאים למסלול 65\n'
            '5. שמירת תיעוד טכני ומסמכי תאימות במקרה של ביקורת\n'
            '6. מעקב אחר עדכוני הפעימות במערכת החיפוש של משרד הכלכלה: '
            'apps.economy.gov.il/Apps/FreeImport/'
        ),
    },
}


# ============================================================================
# EU REFORM KEY FACTS (structured, for quick tool access)
# ============================================================================

EU_REFORM_KEY_FACTS = {
    "name_he": 'רפורמת "מה שטוב לאירופה טוב לישראל"',
    "name_en": "EU Reform: What's Good for Europe is Good for Israel",
    "legal_basis": "החלטת ממשלה 2118",
    "effective_date": "2025-01-01",
    "customs_code": 65,
    "directives_count": 43,
    "standards_affected": 444,
    "total_mandatory_standards": 573,
    "annual_savings_nis": 8_000_000_000,
    "phases": [
        {"phase": 1, "date": "2025-01", "directives": 23, "status": "active",
         "scope": "כניסה לתוקף ראשונית"},
        {"phase": 2, "date": "2025-02", "directives": 1, "status": "active",
         "scope": "בטיחות צעצועים"},
        {"phase": 3, "date": "2025-03", "directives": 1, "status": "active",
         "scope": "חומרים במגע עם מזון"},
        {"phase": 4, "date": "2026-07", "directives": None, "status": "planned",
         "scope": "הרחבה נוספת"},
        {"phase": 5, "date": "2028-01", "directives": None, "status": "planned",
         "scope": "השלמה ל-43 דירקטיבות"},
    ],
    "adopted_directives": [
        "REACH — בטיחות כימיקלים",
        "LVD (Low Voltage Directive) — ציוד חשמלי במתח נמוך",
        "EMC (Electromagnetic Compatibility) — תאימות אלקטרומגנטית",
        "PPE (Personal Protective Equipment) — ציוד מגן אישי",
        "בטיחות צעצועים",
        "חומרים במגע עם מזון",
        "אופניים חשמליים וציוד רפואי (צפויים)",
    ],
    "included_products": [
        "מכשירי חשמל ביתיים", "מוצרי ניקוי וטיפוח", "מחשבים ומוצרי אלקטרוניקה",
        "מכשירי תקשורת", "ציוד בטיחות", "מוצרי ילדים", "חומרים מבוססי עץ",
        "אירוסולים לא מסוכנים", "משקפי שמש", "קוסמטיקה", "צעצועים",
        "פריטי בית ומכשירים חשמליים קטנים",
    ],
    "excluded_products": [
        "מזון ומשקאות", "רכבים מנועיים",
        "פריטי בטיחות אש כללית (למעט ציוד כיבוי נייד)",
        "מוצרי קבוצה 1 הדורשים בדיקת מעבדה מוסמכת",
    ],
    "required_documents": [
        "הצהרת תאימות מהיצרן (Declaration of Conformity - DoC)",
        "תעודת CE מהיצרן או מגוף נוטיפייד (Notified Body)",
        "תיעוד טכני מלא בעברית",
        "הצהרת יבואן",
    ],
    "risk_levels": {
        "low": "הצהרה עצמית של היבואן מספיקה",
        "medium": "יש לאשר שהמוצר נמכר בשוק האירופי או להמציא הצהרת תאימות מהיצרן",
        "high": "דרישות מחמירות כולל מוצרי תינוקות, פלסטיק במגע עם מזון, וחומרי ניקוי מסוימים",
    },
    "personal_import_vat_threshold": {
        "current": 75,
        "was_raised_to": 150,
        "raised_date": "2024-12",
        "reverted_date": "2026-02-23",
        "next_review": "2026-06-01",
    },
    "references": [
        "gov.il/he/pages/eu-reform-information",
        "gov.il/he/pages/qna-europe-reform",
        "gov.il/he/Departments/DynamicCollectors/eu-directives-seach",
        "apps.economy.gov.il/Apps/FreeImport/",
    ],
}


# ============================================================================
# SEARCH HELPERS
# ============================================================================

def search_eu_reform(query: str) -> dict:
    """Search EU reform documents by keyword. Returns matching documents."""
    q_lower = query.lower()
    results = []
    for doc_id, doc in EU_REFORM_DOCS.items():
        text = doc["full_text"].lower()
        title = (doc.get("title_he", "") + " " + doc.get("title_en", "")).lower()
        if q_lower in text or q_lower in title:
            results.append({
                "doc_id": doc_id,
                "title_he": doc["title_he"],
                "title_en": doc["title_en"],
                "source_url": doc["source_url"],
                "effective_date": doc["effective_date"],
                "text_snippet": _extract_snippet(doc["full_text"], query, 500),
            })
    return {
        "found": len(results) > 0,
        "type": "eu_reform",
        "results": results,
        "key_facts": EU_REFORM_KEY_FACTS if results else None,
    }


def get_eu_reform_summary() -> dict:
    """Return structured EU reform summary for tool responses."""
    return {
        "found": True,
        "type": "eu_reform",
        "title_he": EU_REFORM_KEY_FACTS["name_he"],
        "title_en": EU_REFORM_KEY_FACTS["name_en"],
        "legal_basis": EU_REFORM_KEY_FACTS["legal_basis"],
        "effective_date": EU_REFORM_KEY_FACTS["effective_date"],
        "customs_code": EU_REFORM_KEY_FACTS["customs_code"],
        "directives_count": EU_REFORM_KEY_FACTS["directives_count"],
        "standards_affected": EU_REFORM_KEY_FACTS["standards_affected"],
        "phases": EU_REFORM_KEY_FACTS["phases"],
        "adopted_directives": EU_REFORM_KEY_FACTS["adopted_directives"],
        "included_products": EU_REFORM_KEY_FACTS["included_products"],
        "excluded_products": EU_REFORM_KEY_FACTS["excluded_products"],
        "required_documents": EU_REFORM_KEY_FACTS["required_documents"],
        "risk_levels": EU_REFORM_KEY_FACTS["risk_levels"],
        "personal_import_vat_threshold": EU_REFORM_KEY_FACTS["personal_import_vat_threshold"],
        "references": EU_REFORM_KEY_FACTS["references"],
        "documents_count": len(EU_REFORM_DOCS),
        "total_pages": sum(d["pages"] for d in EU_REFORM_DOCS.values()),
    }


def _extract_snippet(text: str, query: str, max_len: int = 500) -> str:
    """Extract a text snippet around the first occurrence of query."""
    q_lower = query.lower()
    t_lower = text.lower()
    idx = t_lower.find(q_lower)
    if idx == -1:
        return text[:max_len]
    start = max(0, idx - max_len // 4)
    end = min(len(text), idx + max_len * 3 // 4)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet
