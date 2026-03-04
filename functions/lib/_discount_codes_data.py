"""Israeli customs discount codes (קודי הנחה) — exemptions and reduced duty rates.

Source: ExemptCustomsItems.xml (shaarolami-query.customs.mof.gov.il)
55-page PDF converted to XML, parsed 2026-03-04.

Contains 4 groups of duty exemptions/reductions from the Customs Tariff
and Exemptions Order (צו תעריף המכס והפטורים):
  Group 1: Goods for entities listed in the Customs Law supplement
  Group 2: Goods imported for a specific period
  Group 3: Miscellaneous goods
  Group 4: Goods imported from specific countries

Data structures:
  DISCOUNT_GROUPS: maps group number (int) to Hebrew group description
  DISCOUNT_CODES: maps item number (str, e.g. "1", "7", "201", "901") to dict:
    - group: int (1-4)
    - description_he: str (Hebrew description)
    - sub_codes: dict mapping 6-digit code (str) to sub-code info dict:
        - description_he: str
        - customs_duty: str ("exempt" / percentage like "72%" / "")
        - purchase_tax: str ("exempt" / percentage like "7%" / "")
        - conditional: bool
        - hs_codes: list[str] (referenced HS codes, if any)
    - conditional: bool (item-level conditional flag)

Helper functions:
  get_discount_code(item_number) -> dict or None
  get_sub_code(item_number, sub_code) -> dict or None
  search_discount_codes(keyword) -> list of matches
  get_codes_by_group(group_number) -> dict of item codes in that group
"""

from typing import Optional, List, Tuple, Dict, Any


# ---------------------------------------------------------------------------
# DISCOUNT_GROUPS: group number -> Hebrew description
# ---------------------------------------------------------------------------
DISCOUNT_GROUPS: Dict[int, str] = {
    1: "טובין המיועדים למפורטים בתוספת לחוק המכס, הבלו ומס הקניה (ביטול פטור מיוחד), התשי\"ז-1957",
    2: "טובין המיובאים לתקופה מסויימת",
    3: "טובין שונים",
    4: "טובין המיובאים מארצות מסויימות",
}


# ---------------------------------------------------------------------------
# DISCOUNT_CODES: item number (פרט) -> item data
# ---------------------------------------------------------------------------
DISCOUNT_CODES: Dict[str, Dict[str, Any]] = {
    # ===================================================================
    # GROUP 1: Goods for entities listed in the Customs Law supplement
    # ===================================================================
    "1": {
        "group": 1,
        "description_he": "טובין שיובאו או שנרכשו במחסן רשוי, לשימוש נשיא המדינה",
        "conditional": True,
        "sub_codes": {},
    },
    "3": {
        "group": 1,
        "description_he": "טובין לנציגויות מדינת חוץ ולנציגי מדינת חוץ",
        "conditional": True,
        "sub_codes": {
            "100000": {
                "description_he": "רכב ממוגן, המיועד לתנועה בכבישים הממוגן בפני ירי כדורים מסוג 7.62 מ\"מ חודרי שריון",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "110000": {
                "description_he": "רכב מנועי - אחר",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "190000": {
                "description_he": "אחר",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "900000": {
                "description_he": "אחר",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "4": {
        "group": 1,
        "description_he": "טובין המיובאים על ידי מוסד של ארגון האומות המאוחדות, אם הטובין מיועדים למטרותיו",
        "conditional": True,
        "sub_codes": {},
    },
    "5": {
        "group": 1,
        "description_he": "טובין - למעט טבק, רכב מנועי, חלקי חילוף לרכב מנועי וציוד משרדי - המיובאים על ידי מוסד של ארגון בין-לאומי לסיוע שהוכר על ידי הממשלה",
        "conditional": True,
        "sub_codes": {},
    },
    "6": {
        "group": 1,
        "description_he": "טובין המיובאים על ידי אדם הנהנה מפטור עליהם על פי התחייבות הנובעת מהסכמים",
        "conditional": True,
        "sub_codes": {
            "100000": {
                "description_he": "הסכם כללי לשיתוף פעולה טכני בין ישראל וארצות הברית של אמריקה",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "150000": {
                "description_he": "הסכם בענין יבוא חומר חינוכי, מדעי ותרבותי - נספח ד",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "151000": {
                "description_he": "הסכם בענין יבוא חומר חינוכי, מדעי ותרבותי - יתר הנספחים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "159000": {
                "description_he": "הסכם בענין יבוא חומר חינוכי, מדעי ותרבותי - אחר",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "200000": {
                "description_he": "אמנת ג'נבה מ-12.8.1949 בדבר הטיפול בשבויי מלחמה",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "250000": {
                "description_he": "אמנת ג'נבה מ-12.8.1949 בדבר הגנת אזרחים בימי מלחמה",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "300000": {
                "description_he": "הסכם בין ישראל ובין צרפת, בדבר פטור גומלין ממסים לגבי חומר תעמולה וכתבי תעמולה המיועדים לתיירים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "350000": {
                "description_he": "חילוף איגרות - הסכם בדבר עזרה כלכלית מיוחדת לישראל (ארצות הברית)",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "360000": {
                "description_he": "ההצעה הנספחת להסכם בין מצרים וישראל, מיום 1.9.1975",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "370000": {
                "description_he": "הפרוטוקול בין מדינת ישראל לבין מצרים, בדבר הקמתם וקיומם של הכוח והמשקיפים הרב-לאומיים, בסיני",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "380000": {
                "description_he": "הסכם בין מדינת ישראל ובין ארצות הברית על פי חוק ההסכם בדבר מעמדם של אנשי סגל ארצות הברית, התשנ\"ג-1993",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "400000": {
                "description_he": "הסכם בדבר קרן המטבע הבין-לאומית",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "410000": {
                "description_he": "אמנת הבנק הבין-אמריקני לפיתוח, התשל\"ו-1976",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "420000": {
                "description_he": "הסכם קרן גרמניה-ישראל למחקר ולפיתוח מדעי",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "430000": {
                "description_he": "הפרוטוקול בין ממשלת ישראל וממשלת אוקראינה בדבר הקמה הדדית של מרכזי תרבות ומידע ופעילויותיהם",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "450000": {
                "description_he": "הסכם בדבר הבנק הבין-לאומי לשיקום ולפיתוח",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "500000": {
                "description_he": "הסכם בין ממשלת ישראל ובין ממשלת ארצות הברית, למימון תכניות מסויימות לחילופים בשדה החינוך",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "510000": {
                "description_he": "הסכם בין ממשלת ישראל ובין ממשלת ארצות הברית, בדבר קרן מדע דו-לאומית של ארצות הברית וישראל",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "520000": {
                "description_he": "הסכם בין ממשלת ישראל ובין ממשלת ארצות הברית, בדבר קרן דו-לאומית למחקר ולפיתוח תעשייתיים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "530000": {
                "description_he": "הסכם בין ממשלת ישראל ובין ממשלת ארצות הברית, בדבר הקמת קרן למחקר ולפיתוח חקלאיים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "540000": {
                "description_he": "הסכם בין ממשלת ישראל ובין ממשלת הרפובליקה הפדרלית של גרמניה, בדבר מכון גתה, מרכז התרבות הגרמני",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "550000": {
                "description_he": "הסכם של התאגיד הבין-לאומי למימון",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "560000": {
                "description_he": "הסכם לשיתוף פעולה בשטח החקלאות בין ממשלת מדינת ישראל לבין ממשלת הרפובליקה של ונצואלה",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "570000": {
                "description_he": "הסכם לשיתוף פעולה מדעי וטכנולוגי בין ממשלת מדינת ישראל לבין ממשלת הרפובליקה של ונצואלה",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "580000": {
                "description_he": "הסכם לשיתוף פעולה טכני בין ממשלת מדינת ישראל לבין ממשלת הרפובליקה של ארגנטינה",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "590000": {
                "description_he": "הסכם בדבר שיתוף פעולה טכני בין ממשלת הרפובליקה של זאיר לבין ממשלת מדינת ישראל",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "600000": {
                "description_he": "אמנת המכס בדבר הקלות ביבואם של טובין להצגה או לשימוש בירידים, בכינוסים או באירועים דומים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "650000": {
                "description_he": "אמנת מכס בדבר יבוא זמני של ציוד מקצועי",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "700000": {
                "description_he": "אמנת מכס בדבר כלי קיבול",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "750000": {
                "description_he": "אמנת מכס בדבר הובלה בין-לאומית של טובין מכוח פנקסי TIR",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "760000": {
                "description_he": "פרוטוקול נוסף לאמנה על הקלות ממכס לתיירות בנוגע ליבואם של מסמכים וחומר לפרסומת התיירות",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "800000": {
                "description_he": "אמנת מכס בדבר יבוא זמני של ציוד מדעי",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "850000": {
                "description_he": "אמנת מכס בדבר יבוא זמני של כלי אריזה",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "900000": {
                "description_he": "אמנת מכס בדבר ציוד רווחה ליורדי ים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "950000": {
                "description_he": "אמנת מכס בדבר יבוא זמני של ציוד פדגוגי",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "960000": {
                "description_he": "אמנת התעופה האזרחית הבין-לאומית",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "970000": {
                "description_he": "הסכם יסודי בין ארגון הבריאות העולמי ובין ממשלת ישראל, בדבר אספקת סיוע של יעוץ טכני",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "980000": {
                "description_he": "הסכם בין ממשלת מדינת ישראל ובין ממשלת קנדה בדבר הובלה אווירית",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "990000": {
                "description_he": "הסכם בין ממשלת מדינת ישראל לבין ממשלת הפדרציה הרוסית בדבר ההקמה והתפקוד של מרכזי תרבות",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "7": {
        "group": 1,
        "description_he": "טובין המיובאים על ידי נכנסים לישראל (עולים, תיירים, תושבי חוץ, תושבים חוזרים)",
        "conditional": True,
        "sub_codes": {
            "100000": {
                "description_he": "תייר - חפצים אישיים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "101000": {
                "description_he": "תייר - כלי עבודה",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "102000": {
                "description_he": "תייר - מכונת כתיבה, מצלמה, מסרטה, מקלט רדיו, מקלט טלוויזיה ודומיהם משומשים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "103000": {
                "description_he": "תייר - גרור למגורים; סירה",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "104000": {
                "description_he": "תייר - רכב מנועי, ובלבד שיובא בתוך 3 חודשים מיום כניסת התייר ויוצא",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "105000": {
                "description_he": "תייר - רכב מנועי שרכש ממחסן רשוי בתוך 3 חודשים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "105100": {
                "description_he": "תייר עם אשרת א.2 (תלמיד) - רכב מנועי",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "105200": {
                "description_he": "תייר א.3 (איש דת) - רכב מנועי",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "105300": {
                "description_he": "תייר עיתונאי חוץ - רכב מנועי",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "105400": {
                "description_he": "תייר עיתונאי חוץ - רכב מנועי (סיום)",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "250000": {
                "description_he": "תושב חוץ כמוגדר בכלל 1(יג)(3) - טובין בכפוף לתנאים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "251000": {
                "description_he": "תושב חוץ כמוגדר בכלל 1(יג)(1) - טובין בפרטי משנה 3000 ו-3100",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "252000": {
                "description_he": "תושב חוץ המוגדר בכלל 1(יג)(2) - טובין ומשנה 1000 וחפצים ביתיים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "253000": {
                "description_he": "תושב חוץ - אחר",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "300000": {
                "description_he": "עולה - חפצים אישיים, לרבות צרכי מזון ממינים מעורבים עד 15 ק\"ג",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "301000": {
                "description_he": "עולה - כלי עבודה",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "302000": {
                "description_he": "עולה - חפצים ביתיים שיובאו במטענו הנילווה",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "303000": {
                "description_he": "עולה - חפצים ביתיים (משלוח נוסף)",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "310000": {
                "description_he": "עולה - רכב מנועי (כללי)",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "312000": {
                "description_he": "עולה - אופנוע שסיווגו בפרטים 87.11",
                "customs_duty": "exempt",
                "purchase_tax": "50%",
                "conditional": True,
                "hs_codes": ["87.11.3000", "87.11.4000", "87.11.5000", "87.11.9090"],
            },
            "313000": {
                "description_he": "עולה - רכב מנועי, ובלבד שהעולה לא ייבא אופנוע לפי סעיף 3120",
                "customs_duty": "exempt",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "313100": {
                "description_he": "עולה - רכב שיוצר מיום 1 בינואר 2007 ואילך",
                "customs_duty": "exempt",
                "purchase_tax": "50%",
                "conditional": True,
                "hs_codes": [],
            },
            "313900": {
                "description_he": "עולה - רכב מנועי אחר",
                "customs_duty": "exempt",
                "purchase_tax": "50%",
                "conditional": True,
                "hs_codes": [],
            },
            "320000": {
                "description_he": "עולה שייבא רכב מנועי בפרט משנה 3100, העבירו לאחר",
                "customs_duty": "100%",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "321000": {
                "description_he": "עולה העביר - אופנוע שסיווגו בפרטים 87.11",
                "customs_duty": "7%",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": ["87.11.3000", "87.11.4000", "87.11.5000", "87.11.9090"],
            },
            "322000": {
                "description_he": "עולה העביר - רכב שיוצר מיום 1 בינואר 2007 ואילך",
                "customs_duty": "7%",
                "purchase_tax": "83%",
                "conditional": False,
                "hs_codes": [],
            },
            "329000": {
                "description_he": "עולה העביר - רכב מנועי אחר",
                "customs_duty": "7%",
                "purchase_tax": "72%",
                "conditional": False,
                "hs_codes": [],
            },
            "400000": {
                "description_he": "תושב חוזר ששהה מחוץ לישראל עד שלושה ימים (כניסה יבשתית)",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "401000": {
                "description_he": "תושב חוזר (פחות משנתיים, יותר מ-3 ימים) - חפצים אישיים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "402000": {
                "description_he": "תושב חוזר ששהה למעלה משנתיים, או סטודנט חוזר",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "403000": {
                "description_he": "תושב חוזר/סטודנט חוזר - כותרת משנית",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "403100": {
                "description_he": "תושב חוזר/סטודנט חוזר - חפצים אישיים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "403200": {
                "description_he": "תושב חוזר/סטודנט חוזר - כלי עבודה",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "403400": {
                "description_he": "תושב חוזר/סטודנט חוזר - חפצים ביתיים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "501000": {
                "description_he": "אדם המשרת באניה או בכלי טיס (פחות מ-60 ימים) - הלבשה והנעלה משומשות",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "502000": {
                "description_he": "אדם המשרת באניה/כלי טיס - טבק 200 גרם, יין עד 3/4 ליטר",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "503000": {
                "description_he": "אדם המשרת באניה/כלי טיס - סיגריות/נוזל לסיגריה אלקטרונית",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "503100": {
                "description_he": "אדם המשרת באניה/כלי טיס - 80 סיגריות או 4 מ\"ל נוזל (פחות מ-5 ימים)",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "503200": {
                "description_he": "אדם המשרת באניה/כלי טיס - 200 סיגריות או 10 מ\"ל נוזל (5 ימים ויותר)",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "504000": {
                "description_he": "אדם המשרת באניה/כלי טיס - טובין אחרים",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "504100": {
                "description_he": "אדם המשרת - טובין שערכם הכולל אינו עולה על 20 דולר",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "504200": {
                "description_he": "אדם המשרת - טובין שערכם הכולל אינו עולה על 75 דולר (24 שעות ויותר)",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "505000": {
                "description_he": "אדם המשרת - טובין שסך כל מסי היבוא אינו עולה על 20 ש\"ח",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "8": {
        "group": 1,
        "description_he": "טובין המיובאים על ידי מוסד ציבורי כמשמעותו בפרט 12 בתוספת לחוק המכס",
        "conditional": True,
        "sub_codes": {
            "200000": {
                "description_he": "אבזרים ומכשירים רפואיים, למעט רכב מנועי שאינו עגלות נכים (עד 200 יחידות, 2 מיליון ש\"ח FOB בשנת מס)",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
        },
    },
    "9": {
        "group": 1,
        "description_he": "טובין הפטורים ממכס לפי חוק הנפט, התשי\"ב-1952",
        "conditional": True,
        "sub_codes": {},
    },
    "12": {
        "group": 1,
        "description_he": "טובין המיובאים במסגרת תכנית שאושרה על ידי ממשלת ישראל ושלטונות מדינות חוץ, כאמור בפרט 11 לתוספת לחוק המכס",
        "conditional": True,
        "sub_codes": {},
    },
    "13": {
        "group": 1,
        "description_he": "טובין הפטורים ממכס לפי חוק זכיון צינור הנפט, התשכ\"ח-1968",
        "conditional": True,
        "sub_codes": {},
    },
    "14": {
        "group": 1,
        "description_he": "מכונות, מכשירים וכלים לתעשיה, למלאכה, לחקלאות - למעט רכב מנועי - המיובאים ע\"י עולה או תושב חוזר (עד 36,000 דולר FOB)",
        "conditional": True,
        "sub_codes": {},
    },
    "16": {
        "group": 1,
        "description_he": "טובין הפטורים ממכס לפי סעיף 2(ד) לחוק מגן דוד אדום, התש\"י-1950",
        "conditional": True,
        "sub_codes": {},
    },
    "17": {
        "group": 1,
        "description_he": "טובין המיועדים לארגון בין לאומי לסיוע, שהוכר על ידי המנכ\"לים של משרדי האוצר, הבטחון, והעבודה והרווחה",
        "conditional": True,
        "sub_codes": {},
    },
    "18": {
        "group": 1,
        "description_he": "טובין המיובאים לתצוגה בבתי נכות (מוזיאון מוכר)",
        "conditional": True,
        "sub_codes": {},
    },

    # ===================================================================
    # GROUP 2: Goods imported for a specific period
    # ===================================================================
    "201": {
        "group": 2,
        "description_he": "דוגמאות שלא פורשו בפרט 612, המיועדות להדגמה בלבד, בכפוף לתנאים",
        "conditional": True,
        "sub_codes": {},
    },
    "207": {
        "group": 2,
        "description_he": "טובין שאושרו על ידי המנהל, שנשארו בבעלות הספק וייוצאו מישראל",
        "conditional": True,
        "sub_codes": {
            "100000": {
                "description_he": "אם אושרה תקופה עד חצי שנה",
                "customs_duty": "10%",
                "purchase_tax": "10%",
                "conditional": False,
                "hs_codes": [],
            },
            "150000": {
                "description_he": "אם אושרה תקופה עד שנה",
                "customs_duty": "20%",
                "purchase_tax": "20%",
                "conditional": False,
                "hs_codes": [],
            },
            "200000": {
                "description_he": "אם אושרה תקופה עד שנה וחצי",
                "customs_duty": "30%",
                "purchase_tax": "30%",
                "conditional": False,
                "hs_codes": [],
            },
            "250000": {
                "description_he": "אם אושרה תקופה עד שנתיים",
                "customs_duty": "40%",
                "purchase_tax": "40%",
                "conditional": False,
                "hs_codes": [],
            },
            "300000": {
                "description_he": "אם אושרה תקופה עד שנתיים וחצי",
                "customs_duty": "50%",
                "purchase_tax": "50%",
                "conditional": False,
                "hs_codes": [],
            },
            "350000": {
                "description_he": "אם אושרה תקופה עד שלוש שנים",
                "customs_duty": "60%",
                "purchase_tax": "60%",
                "conditional": False,
                "hs_codes": [],
            },
            "400000": {
                "description_he": "אם אושרה תקופה עד שלוש שנים וחצי",
                "customs_duty": "70%",
                "purchase_tax": "70%",
                "conditional": False,
                "hs_codes": [],
            },
            "450000": {
                "description_he": "אם אושרה תקופה עד ארבע שנים",
                "customs_duty": "80%",
                "purchase_tax": "80%",
                "conditional": False,
                "hs_codes": [],
            },
            "500000": {
                "description_he": "אם אושרה תקופה עד ארבע שנים וחצי",
                "customs_duty": "90%",
                "purchase_tax": "90%",
                "conditional": False,
                "hs_codes": [],
            },
            "550000": {
                "description_he": "אם אושרה תקופה עד חמש שנים",
                "customs_duty": "100%",
                "purchase_tax": "100%",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "209": {
        "group": 2,
        "description_he": "ציוד ללהקות אומנות ובידור שמקום עיסקן הקבוע הוא מחוץ לישראל",
        "conditional": True,
        "sub_codes": {},
    },
    "210": {
        "group": 2,
        "description_he": "דוגמאות שלא פורשו בפרט 201 או 612, המשמשות כדגם לייצור או לבדיקה מעבדתית",
        "conditional": True,
        "sub_codes": {},
    },
    "211": {
        "group": 2,
        "description_he": "אוטובוסים המשמשים לסיורים וטיולים של תיירים (חברה שמקום עיסקה מחוץ לישראל)",
        "conditional": True,
        "sub_codes": {},
    },
    "212": {
        "group": 2,
        "description_he": "טובין המיובאים על פי סעיף 162(ג) לפקודת המכס",
        "conditional": True,
        "sub_codes": {},
    },
    "213": {
        "group": 2,
        "description_he": "כלי רכב המשמש להובלה בין-לאומית של טובין בדרכים (הסכם: איטליה, בלגיה, גרמניה, הולנד, צרפת, ירדן)",
        "conditional": True,
        "sub_codes": {},
    },
    "214": {
        "group": 2,
        "description_he": "כלי רכב המשמש להובלה בין-לאומית של טובין בדרכים (הסכם ישראל-מצרים, 17.9.1981)",
        "conditional": True,
        "sub_codes": {},
    },

    # ===================================================================
    # GROUP 3: Miscellaneous goods
    # ===================================================================
    "402": {
        "group": 3,
        "description_he": "ציוד דיג שלגביו אישר מנכ\"ל משרד החקלאות כי הוא מיוחד לדיג מקצועי",
        "conditional": False,
        "sub_codes": {},
    },
    "408": {
        "group": 3,
        "description_he": "כלי יד המותאמים במיוחד לשימוש באמצעות גפיים מלאכותיים",
        "conditional": False,
        "sub_codes": {},
    },
    "410": {
        "group": 3,
        "description_he": "טובין המשמשים לצרכי נתיבי אויר (AIRLINES) ונמלי תעופה (AIRPORTS)",
        "conditional": True,
        "sub_codes": {
            "200000": {
                "description_he": "ציוד וחמרים לתיקון כלי טיס ולהחזקתם",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "400000": {
                "description_he": "ציוד להטענת והעברת מטענים בנמלי תעופה",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "500000": {
                "description_he": "ציוד להדרכת צוות אויר",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
        },
    },
    "411": {
        "group": 3,
        "description_he": "קרוסין דלק סילוני, שמני סיכה ותכשירי סיכה המשמשים לצורכי כלי טיס",
        "conditional": True,
        "sub_codes": {},
    },
    "412": {
        "group": 3,
        "description_he": "מכונות, מכשירים, חמרים וציוד המשמשים לבניית כלי שיט או לתיקונם",
        "conditional": True,
        "sub_codes": {},
    },
    "414": {
        "group": 3,
        "description_he": "חמרים, למעט בנזין, המשמשים לייצור צמיגים",
        "conditional": True,
        "sub_codes": {},
    },
    "415": {
        "group": 3,
        "description_he": "סולר כמפורט בסעיף 3(א)(1)א לצו הבלו על דלק (פטור והישבון), התשס\"ה-2005",
        "conditional": True,
        "sub_codes": {},
    },
    "416": {
        "group": 3,
        "description_he": "דלק כמפורט בסעיף 3(א)(1)ב לצו הבלו על דלק (פטור והישבון), התשס\"ה-2005",
        "conditional": True,
        "sub_codes": {},
    },
    "425": {
        "group": 3,
        "description_he": "חמרים וחלקים המשמשים לייצור או לתיקון של כלי טיס או ציוד קרקע הקשור לטיסה (פרקים 84, 85, 88, 90)",
        "conditional": True,
        "sub_codes": {
            "990000": {
                "description_he": "אחרים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
        },
    },
    "426": {
        "group": 3,
        "description_he": "מכונות, מכשירים וציוד המשמשים בתהליך ייצור או תיקון של כלי טיס, במפעל שעיקר עיסוקו בייצור כלי טיס",
        "conditional": True,
        "sub_codes": {
            "990000": {
                "description_he": "אחרים",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "991000": {
                "description_he": "אם שיעור המכס החל 4% או יותר",
                "customs_duty": "4%",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "999000": {
                "description_he": "אחרים",
                "customs_duty": "exempt",
                "purchase_tax": "100%",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "430": {
        "group": 3,
        "description_he": "ציוד או חמרים המיובאים למניעה או להדברה של זיהום על ידי שמנים, בימים, באגמים, בנחלים או בחופים",
        "conditional": False,
        "sub_codes": {},
    },
    "432": {
        "group": 3,
        "description_he": "מכונה או מכשיר חשמלי/אלקטרוני למדידה או דגימה של זיהום אוויר, ים, דרכי מים או קרקע; מכונה למניעת זיהום סביבתי",
        "conditional": False,
        "sub_codes": {},
    },
    "501": {
        "group": 3,
        "description_he": "תרופות שלגביהן אישר מנכ\"ל משרד הבריאות שישמשו לצורך ניסויים רפואיים בבני אדם",
        "conditional": True,
        "sub_codes": {},
    },
    "601": {
        "group": 3,
        "description_he": "מכשירים מהסוג המשמש לכוורנות (פרטים 44.21 ו-84.36) וחלקיהם",
        "conditional": False,
        "sub_codes": {},
    },
    "602": {
        "group": 3,
        "description_he": "ציוד מובהק לעיוורים",
        "conditional": False,
        "sub_codes": {
            "100000": {
                "description_he": "נייר בראיל (BRAILLE)",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "603": {
        "group": 3,
        "description_he": "עדשות או משקפיים המיוחדים לשיפור הראייה של אנשים אשר זווית הראייה אינה עולה על 20 מעלות או כושר ראייה 6/36",
        "conditional": False,
        "sub_codes": {},
    },
    "610": {
        "group": 3,
        "description_he": "הנחה להצהרות בתהליך בלדרות המכילים מסמכים (יש חובה לדווח פרט מהותי)",
        "conditional": False,
        "sub_codes": {},
    },
    "612": {
        "group": 3,
        "description_he": "דוגמאות בעלות ערך מבוטל, כמשמעותם באמנה הבין-לאומית בדבר הקלת יבואם של דוגמאות מסחריות",
        "conditional": True,
        "sub_codes": {},
    },
    "615": {
        "group": 3,
        "description_he": "סרטים סינמטוגרפיים, סרטונים, שקופיות, מיקרופילמים ושקפים בעלי אופי חינוכי",
        "conditional": False,
        "sub_codes": {
            "200000": {
                "description_he": "סרטים, שקפים ושקופיות המיוחדים לשימוש בחינוך לכל דרגותיו",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": ["37.05.9090", "37.05.9010"],
            },
            "400000": {
                "description_he": "סרטים, שקפים ושקופיות העוסקים במחקר מדעי או טכני",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "500000": {
                "description_he": "סרטים, שקפים ושקופיות העוסקים בבריאות, אימון גופני ועבודה סוציאלית",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "616": {
        "group": 3,
        "description_he": "מכשירים וציוד להגנתם ולבטחונם של עובדים בתעשיה ובחרושת, שאושרו על ידי מפקח העבודה הראשי",
        "conditional": False,
        "sub_codes": {},
    },
    "618": {
        "group": 3,
        "description_he": "גביעים, אותות הצטיינות, מדליות וסמלים המוענקים על ידי מוסד או ארגון כאות הוקרה למאורע ספורטיבי, תרבותי או דומה",
        "conditional": False,
        "sub_codes": {},
    },
    "619": {
        "group": 3,
        "description_he": "מיתקנים, מכונות, מכשירים או כלים מהסוג המיוחד למשקי חלב ועופות",
        "conditional": False,
        "sub_codes": {},
    },
    "621": {
        "group": 3,
        "description_he": "ציוד לחימה ייחודי אשר אושר על ידי מנכ\"ל משרד הבטחון",
        "conditional": True,
        "sub_codes": {},
    },
    "627": {
        "group": 3,
        "description_he": "חלקים למוני מוניות שרישום פעולותיהם מצטבר וסכומיהם אינם ניתנים למחיקה",
        "conditional": False,
        "sub_codes": {},
    },
    "628": {
        "group": 3,
        "description_he": "התקנים המיועדים לשימושם הבלעדי של בעלי סטומות דרכי העיכול ודרכי השתן; התקנים הנלבשים, נישאים או שתולים בגוף לשם הקלה על מום או נכות",
        "conditional": False,
        "sub_codes": {},
    },
    "629": {
        "group": 3,
        "description_he": "התקנים ומכשירים חשמליים המתוכננים במיוחד לשימושם של נכי גפיים",
        "conditional": False,
        "sub_codes": {},
    },
    "630": {
        "group": 3,
        "description_he": "טובין המותאמים במיוחד לשימושם של נכים למעט רכב מנועי",
        "conditional": False,
        "sub_codes": {},
    },
    "658": {
        "group": 3,
        "description_he": "טובין המשמשים לייצור התקנים אורטופדיים או חלקי גוף מלאכותיים (פרט 90.21)",
        "conditional": True,
        "sub_codes": {},
    },
    "660": {
        "group": 3,
        "description_he": "עיתונים, כתבי עת ודברי דפוס אחרים שמס ערך מוסף החל על יבואם שולם לפי סעיף 26(ב) לחוק מע\"מ",
        "conditional": False,
        "sub_codes": {
            "100000": {
                "description_he": "שבגדר פרט 49.03",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": ["49.03"],
            },
            "900000": {
                "description_he": "אחרים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "703": {
        "group": 3,
        "description_he": "חלקים ואבזרים של כלי רכב המשמשים להרכבה או לייצור של כלי רכב",
        "conditional": True,
        "sub_codes": {
            "100000": {
                "description_he": "חלקים ואבזרים המשמשים להרכבה או ייצור",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
            "210000": {
                "description_he": "רכב שדה העומד בתנאים (מרכב סגור, הנעה כפולה, נפח 2100+ סמ\"ק)",
                "customs_duty": "exempt",
                "purchase_tax": "72%",
                "conditional": False,
                "hs_codes": [],
            },
            "220000": {
                "description_he": "רכב משא (כלל 6(ה) לפרק 87)",
                "customs_duty": "exempt",
                "purchase_tax": "5%",
                "conditional": True,
                "hs_codes": [],
            },
            "230000": {
                "description_he": "רכב מנועי שנתקיימו בו תנאי פרט 621 או פרט 410",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
        },
    },
    "731": {
        "group": 3,
        "description_he": "חלק או אבזר משומשים לכלי רכב מנועי, למעט מחודשים/משופצים וצמיגים",
        "conditional": False,
        "sub_codes": {
            "100000": {
                "description_he": "שסיווגם בפרט 87.10",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": ["87.10"],
            },
            "200000": {
                "description_he": "מנועים",
                "customs_duty": "3 ש' לקילוגרם",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "900000": {
                "description_he": "אחרים",
                "customs_duty": "3 ש' לקילוגרם",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "801": {
        "group": 3,
        "description_he": "תשמישי קדושה",
        "conditional": False,
        "sub_codes": {
            "200000": {
                "description_he": "לפי הדת הנוצרית - צלבים, מדליות מקודשות, תמונות מקודשות, כלי עזר למיסה",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "201000": {
                "description_he": "לפי הדת הנוצרית - מזבח, משכן, חופה לטקסים, מצנפת לבישוף, כסא לבישוף",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "202000": {
                "description_he": "לפי הדת הנוצרית - פריטים נוספים באישור מנכ\"ל משרד הדתות",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "804": {
        "group": 3,
        "description_he": "ציוד ומכשירים רפואיים לבנק הדם, לייבוש דם או להחזקת פלסמה",
        "conditional": True,
        "sub_codes": {},
    },
    "807": {
        "group": 3,
        "description_he": "חלקי חילוף למכונות/מכשירים הנשלחים על ידי הספק ללא תמורה במסגרת אחריות (עד שנה, מכס עד 5%)",
        "conditional": False,
        "sub_codes": {},
    },
    "808": {
        "group": 3,
        "description_he": "בגדים משומשים (למעט פרוות) והנעלה משומשת במשלוחי דואר - הנשלחים במתנה",
        "conditional": False,
        "sub_codes": {},
    },
    "809": {
        "group": 3,
        "description_he": "מבנים טרומיים (PREFABRICATED HOUSES) למגורים, המיובאים לצרכי הדגמה",
        "conditional": False,
        "sub_codes": {},
    },
    "810": {
        "group": 3,
        "description_he": "טובין שיוצאו מישראל והוחזרו (עד 5 שנים)",
        "conditional": False,
        "sub_codes": {
            "100000": {
                "description_he": "אם לא ניתן הישבון מסים",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "101000": {
                "description_he": "לא עברו הטובין תהליך תיקון/חידוש/שיפור",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "102000": {
                "description_he": "עברו הטובין תהליך תיקון - חבות מכס ומס קניה על ההוצאות",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "102100": {
                "description_he": "חבי מכס לפי ערך, למעט טקסטיל ופרטים מסוימים",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "102200": {
                "description_he": "טקסטילים ומוצרי טקסטיל (חלק XI) החבים מכס קצוב",
                "customs_duty": "exempt",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "102300": {
                "description_he": "טובין אחרים החבים מכס קצוב, למעט פרקים 64, 65, 66",
                "customs_duty": "exempt",
                "purchase_tax": "8%",
                "conditional": False,
                "hs_codes": [],
            },
            "102400": {
                "description_he": "טקסטילים (חלק XI) החבים מכס קצוב, למעט פרט 1028",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "102500": {
                "description_he": "אוטובוסים שמשקלם הכולל המותר עולה על 4500 ק\"ג",
                "customs_duty": "exempt",
                "purchase_tax": "20%",
                "conditional": False,
                "hs_codes": [],
            },
            "102600": {
                "description_he": "טובין שיוצאו לארצות הקהילה או לקנדה והוחזרו ישירות",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "102700": {
                "description_he": "טובין שסיווגם בפרטים 60.04, 60.06 שיוצאו לצביעה, או תכשיטים 71.13",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": ["60.04.1000", "60.04.9000", "60.06.2100", "60.06.3100"],
            },
            "102800": {
                "description_he": "טקסטילים (חלק XI) שיוצאו לירדן והוחזרו ישירות",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "102900": {
                "description_he": "טובין אחרים חבי מכס לפי ערך נוסף למכס קצוב",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "200000": {
                "description_he": "אם ניתן לגבי הטובין הישבון מסים",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "300000": {
                "description_he": "אם ערכם הכולל של הטובין אינו עולה על 10 דולר",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "811": {
        "group": 3,
        "description_he": "כלי רכב ממוגן בפני ירי 7.62 מ\"מ חודרי שריון (תושב יש\"ע / שימוש ביש\"ע / אישור משרד הביטחון)",
        "conditional": True,
        "sub_codes": {
            "100000": {
                "description_he": "כלי הרכב ללא מיגון",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "200000": {
                "description_he": "המיגון",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "812": {
        "group": 3,
        "description_he": "כלי רכב מונמך רצפה עם מתקן מיוחד לנכים (כסא גלגלים), באישור משרד הביטחון או ביטוח לאומי",
        "conditional": False,
        "sub_codes": {
            "100000": {
                "description_he": "כלי הרכב ללא המתקן",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "200000": {
                "description_he": "המתקן",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "813": {
        "group": 3,
        "description_he": "רכב מנועי אשר מותקן בו באופן קבוע ציוד מקצועי יקר ערך, שאושר על ידי המנהל",
        "conditional": False,
        "sub_codes": {
            "100000": {
                "description_he": "הרכב המנועי ללא הציוד",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "200000": {
                "description_he": "ציוד מקצועי",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "814": {
        "group": 3,
        "description_he": "רכב אספנות שמשקלו הכולל המותר אינו עולה על 4,500 ק\"ג",
        "conditional": False,
        "sub_codes": {},
    },
    "815": {
        "group": 3,
        "description_he": "רכב המיובא ביבוא אישי או מקביל, בעל שם יצרן/קוד/מדינה זהים לרכב שקיבל העדפת מכס לפי הסכם סחר בין-לאומי",
        "conditional": True,
        "sub_codes": {
            "110000": {
                "description_he": "כלי רכב מונמך רצפה לנכים (כסא גלגלים) - ללא המתקן",
                "customs_duty": "exempt",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "190000": {
                "description_he": "כלי רכב מונמך רצפה לנכים - המתקן",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "210000": {
                "description_he": "כלי רכב ממוגן - ללא מיגון",
                "customs_duty": "exempt",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "290000": {
                "description_he": "כלי רכב ממוגן - המיגון",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "310000": {
                "description_he": "רכב מנועי עם ציוד מקצועי - ללא הציוד",
                "customs_duty": "exempt",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "390000": {
                "description_he": "רכב מנועי עם ציוד מקצועי - ציוד מקצועי",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": False,
                "hs_codes": [],
            },
            "900000": {
                "description_he": "אחרים",
                "customs_duty": "exempt",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "816": {
        "group": 3,
        "description_he": "רהיטים משומשים, שבגדר פרטים 94.01 ו-94.03",
        "conditional": False,
        "sub_codes": {},
    },
    "819": {
        "group": 3,
        "description_he": "כיסויי לחץ המיוחדים לנפגעי כוויות",
        "conditional": False,
        "sub_codes": {},
    },
    "820": {
        "group": 3,
        "description_he": "מכשירי טלוויזיה בלתי משולבים (85.28) המשמשים בבתי מלון (10%+ תיירי חוץ מסך לינות)",
        "conditional": True,
        "sub_codes": {},
    },
    "821": {
        "group": 3,
        "description_he": "טובין המיובאים על ידי מיזם מורשה על פי חוק אזורי נמל חופשיים, התשכ\"ט-1969",
        "conditional": True,
        "sub_codes": {
            "900000": {
                "description_he": "טובין אחרים שלא נעשתה בהם פעולת ייצור והמיועדים לייצוא",
                "customs_duty": "exempt",
                "purchase_tax": "exempt",
                "conditional": True,
                "hs_codes": [],
            },
        },
    },
    "822": {
        "group": 3,
        "description_he": "כלי רכב הייבריד (מנוע בוכנה בשריפה פנימית + מנוע חשמלי), כולל Plug-in",
        "conditional": True,
        "sub_codes": {},
    },
    "825": {
        "group": 3,
        "description_he": "בדים בלתי מולבנים שהם חומר גלם לתעשיית הטקסטיל וההלבשה (פרטים 51.12.1000, 54.07, 54.08, 55.12-55.16)",
        "conditional": False,
        "sub_codes": {},
    },
    "831": {
        "group": 3,
        "description_he": "כלים תחרותיים לנהיגה ספורטיבית (אופנוע, באגי, טרקטורון, משאית, קארט, מכונית)",
        "conditional": True,
        "sub_codes": {
            "100000": {
                "description_he": "כלי תחרותי בייבוא אישי/מסחרי לנהיגה ספורטיבית",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "110000": {
                "description_he": "מסוג משאית שמשקלה הכולל עד 4500 ק\"ג",
                "customs_duty": "60%",
                "purchase_tax": "12%",
                "conditional": True,
                "hs_codes": [],
            },
            "120000": {
                "description_he": "מסוג משאית שמשקלה הכולל עולה על 4500 ק\"ג",
                "customs_duty": "exempt",
                "purchase_tax": "100%",
                "conditional": True,
                "hs_codes": [],
            },
            "130000": {
                "description_he": "מסוג אופנוע",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "140000": {
                "description_he": "מסוג טרקטורון; מסוג רכב שטח",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "150000": {
                "description_he": "מסוג קארט",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "160000": {
                "description_he": "מסוג באגי",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "170000": {
                "description_he": "מסוג מכונית (עד 60 חודשים ממועד ייצור)",
                "customs_duty": "60%",
                "purchase_tax": "12%",
                "conditional": True,
                "hs_codes": [],
            },
            "190000": {
                "description_he": "אחרים",
                "customs_duty": "100%",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "210000": {
                "description_he": "כלי מנועי להסבה לכלי תחרותי - משאית עד 4500 ק\"ג",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "220000": {
                "description_he": "כלי מנועי להסבה - משאית מעל 4500 ק\"ג",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "230000": {
                "description_he": "כלי מנועי להסבה - אופנוע",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "240000": {
                "description_he": "כלי מנועי להסבה - טרקטורון; רכב שטח",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "250000": {
                "description_he": "כלי מנועי להסבה - קארט",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "270000": {
                "description_he": "כלי מנועי להסבה - מכונית",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "290000": {
                "description_he": "כלי מנועי להסבה - אחר",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "300000": {
                "description_he": "חלקי חילוף המיוחדים לכלי מנועי שסיווגו בפרט משנה 1000",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "310000": {
                "description_he": "חלקי חילוף - מכלי דלק",
                "customs_duty": "exempt",
                "purchase_tax": "100%",
                "conditional": True,
                "hs_codes": [],
            },
            "320000": {
                "description_he": "חלקי חילוף - מושבים",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "330000": {
                "description_he": "חלקי חילוף - רתמות (חגורות) בטיחות",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "340000": {
                "description_he": "חלקי חילוף - כלובי התהפכות (Roll Cages)",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
            "390000": {
                "description_he": "חלקי חילוף - אחרים",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "900000": {
                "description_he": "לבוש מגן וציוד מגן המיוחדים לנהגים/רוכבים בכלי תחרותי - אחרים",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": True,
                "hs_codes": [],
            },
        },
    },

    # ===================================================================
    # GROUP 4: Goods imported from specific countries
    # ===================================================================
    "901": {
        "group": 4,
        "description_he": "שום מיובש שבפרט 07.12.9010",
        "conditional": False,
        "sub_codes": {},
    },
    "902": {
        "group": 4,
        "description_he": "אגוזי קוקוס מיובשים שבפרט 08.01.1000",
        "conditional": False,
        "sub_codes": {},
    },
    "909": {
        "group": 4,
        "description_he": "חפצי נסיעה, שקי קניות, ילקוטים, תיקים, ארנקים - ששכבתם החיצונית מעור או מעור מורכב שבפרט 42.02",
        "conditional": False,
        "sub_codes": {},
    },
    "911": {
        "group": 4,
        "description_he": "חוט מצמר מנופץ המכיל אקריליים או מודאקריליים שבפרט 51.06",
        "conditional": False,
        "sub_codes": {},
    },
    "912": {
        "group": 4,
        "description_he": "חוט מצמר סרוק המכיל אקריליים או מודאקריליים שבפרט 51.07",
        "conditional": False,
        "sub_codes": {},
    },
    "913": {
        "group": 4,
        "description_he": "טובין שבפרט משנה 1000 לפרט 33.01",
        "conditional": False,
        "sub_codes": {},
    },
    "945": {
        "group": 4,
        "description_he": "טובין שבפרט משנה 1000 לפרט 44.07, למעט מחוברי אצבעות (FINGER JOINTED)",
        "conditional": False,
        "sub_codes": {},
    },
    "994": {
        "group": 4,
        "description_he": "רכב נוסעים לרש\"פ (הרשות הפלסטינית)",
        "conditional": True,
        "sub_codes": {
            "100000": {
                "description_he": "רכב נוסעים כולל מוניות ביבוא מסחרי",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "110000": {
                "description_he": "רכב משומש, לא כולל מוניות משומשות",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "111000": {
                "description_he": "כלי רכב המונעים ע\"י מנוע חשמלי בלבד (משומש)",
                "customs_duty": "10%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
            "112000": {
                "description_he": "רכב היברידי כולל פלאג-אין (משומש)",
                "customs_duty": "30%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
            "118000": {
                "description_he": "רכב משומש שנפח הצילינדרים עולה על 2000 סמ\"ק",
                "customs_duty": "75%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
            "119000": {
                "description_he": "רכב משומש - אחרים",
                "customs_duty": "50%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
            "120000": {
                "description_he": "רכב חדש כולל מוניות חדשות בלבד",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "121000": {
                "description_he": "כלי רכב חדש המונע ע\"י מנוע חשמלי בלבד",
                "customs_duty": "10%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
            "122000": {
                "description_he": "רכב חדש היברידי כולל פלאג-אין",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "123000": {
                "description_he": "מוניות חדשות",
                "customs_duty": "exempt",
                "purchase_tax": "7%",
                "conditional": True,
                "hs_codes": [],
            },
            "128000": {
                "description_he": "רכב חדש שנפח הצילינדרים עולה על 2000 סמ\"ק",
                "customs_duty": "75%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
            "129000": {
                "description_he": "רכב חדש - אחרים",
                "customs_duty": "50%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
            "200000": {
                "description_he": "רכב להובלת טובין ביבוא מסחרי",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "218000": {
                "description_he": "רכב הובלה שנפח הצילינדרים עולה על 2000 סמ\"ק",
                "customs_duty": "75%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
            "219000": {
                "description_he": "רכב הובלה - אחרים",
                "customs_duty": "50%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
            "400000": {
                "description_he": "רכב נוסעים ביבוא אישי, לא כולל מוניות",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "410000": {
                "description_he": "רכב משומש ביבוא אישי",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "411000": {
                "description_he": "רכב אישי משומש - מנוע חשמלי בלבד",
                "customs_duty": "10%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
            "412000": {
                "description_he": "רכב אישי משומש - היברידי כולל פלאג-אין",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "418000": {
                "description_he": "רכב אישי משומש שנפח הצילינדרים עולה על 2000 סמ\"ק",
                "customs_duty": "75%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
            "419000": {
                "description_he": "רכב אישי משומש - אחרים",
                "customs_duty": "50%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
            "420000": {
                "description_he": "רכב אישי חדש",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "421000": {
                "description_he": "רכב אישי חדש - מנוע חשמלי בלבד",
                "customs_duty": "10%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
            "422000": {
                "description_he": "רכב אישי חדש - היברידי כולל פלאג-אין",
                "customs_duty": "",
                "purchase_tax": "",
                "conditional": False,
                "hs_codes": [],
            },
            "428000": {
                "description_he": "רכב אישי חדש שנפח הצילינדרים עולה על 2000 סמ\"ק",
                "customs_duty": "75%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
            "429000": {
                "description_he": "רכב אישי חדש - אחרים",
                "customs_duty": "50%",
                "purchase_tax": "7%",
                "conditional": False,
                "hs_codes": [],
            },
        },
    },
    "998": {
        "group": 4,
        "description_he": "תרומה למוסדות האוטונומיה",
        "conditional": False,
        "sub_codes": {},
    },
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_discount_code(item_number: str) -> Optional[Dict[str, Any]]:
    """Get a discount code item by its number (e.g. '7', '201', '994').

    Returns the full item dict or None if not found.
    """
    return DISCOUNT_CODES.get(str(item_number))


def get_sub_code(item_number: str, sub_code: str) -> Optional[Dict[str, Any]]:
    """Get a specific 6-digit sub-code within an item.

    Returns the sub-code dict or None if not found.
    """
    item = DISCOUNT_CODES.get(str(item_number))
    if item is None:
        return None
    return item.get("sub_codes", {}).get(str(sub_code))


def search_discount_codes(keyword: str) -> List[Tuple[str, Optional[str], str]]:
    """Search discount codes by Hebrew keyword.

    Returns list of tuples: (item_number, sub_code_or_None, description_he).
    Limited to 30 results.
    """
    kw = keyword.strip().lower()
    if not kw:
        return []
    results: List[Tuple[str, Optional[str], str]] = []
    for item_num, item_data in DISCOUNT_CODES.items():
        desc = item_data.get("description_he", "")
        if kw in desc.lower():
            results.append((item_num, None, desc))
        for sc_num, sc_data in item_data.get("sub_codes", {}).items():
            sc_desc = sc_data.get("description_he", "")
            if kw in sc_desc.lower():
                results.append((item_num, sc_num, sc_desc))
    return results[:30]


def get_codes_by_group(group_number: int) -> Dict[str, Dict[str, Any]]:
    """Get all discount code items belonging to a specific group.

    Returns dict of item_number -> item_data for matching items.
    """
    return {
        item_num: item_data
        for item_num, item_data in DISCOUNT_CODES.items()
        if item_data.get("group") == group_number
    }
