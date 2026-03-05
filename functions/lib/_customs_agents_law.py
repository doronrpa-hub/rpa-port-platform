"""Customs Agents Law (חוק סוכני המכס, תשכ"ה-1964) — full structured text.

Source: Nevo Legal Database (nevo.co.il/law_html/law01/265_023.htm)
Parsed: Session 85 (2026-03-05)

35 articles across 7 chapters. Covers:
- Registration of customs agents (סוכני מכס)
- Qualification requirements
- Disciplinary measures
- Licensed clerks (פקידים רשויים)
- Agent duties and responsibilities
- International forwarders (משלחים בינלאומיים)
- Penalties
"""

# ── Chapters ──────────────────────────────────────────────────────
CUSTOMS_AGENTS_CHAPTERS = {
    "1": {
        "title_he": "פרשנות",
        "title_en": "Interpretation",
        "articles": ["1"],
    },
    "2": {
        "title_he": "רישום סוכני מכס",
        "title_en": "Registration of Customs Agents",
        "articles": ["2", "3", "3א", "3ב", "4", "5", "6", "7"],
    },
    "3": {
        "title_he": "מחיקת רישום ואמצעי משמעת",
        "title_en": "Deregistration and Disciplinary Measures",
        "articles": ["11", "12", "13", "14", "15"],
    },
    "4": {
        "title_he": "פקידים רשויים",
        "title_en": "Licensed Clerks",
        "articles": ["16", "17", "18", "19"],
    },
    "5": {
        "title_he": "חובותיו של סוכן מכס",
        "title_en": "Duties of a Customs Agent",
        "articles": ["20", "21", "22"],
    },
    "6": {
        "title_he": "ערר",
        "title_en": "Appeals",
        "articles": ["23"],
    },
    "6.1": {
        "title_he": "משלחים בינלאומיים",
        "title_en": "International Forwarders",
        "articles": ["24א", "24ב"],
    },
    "7": {
        "title_he": "שונות",
        "title_en": "Miscellaneous",
        "articles": ["25", "26", "27", "28", "29", "29א", "30", "31", "32", "33", "34", "35"],
    },
}


# ── Articles ──────────────────────────────────────────────────────
# Each article: ch=chapter, t=Hebrew title, s=English summary, f=full Hebrew text
CUSTOMS_AGENTS_ARTICLES = {
    "1": {
        "ch": "1",
        "t": "הגדרות",
        "s": "Definitions: customs agent, customs action, secondary education, advisory committee, licensed clerk, director",
        "f": (
            'בחוק זה –\n'
            '"סוכן מכס" – אדם העושה פעולת מכס בשביל זולתו דרך שירות לכל, '
            'והוא רשום בפנקס סוכני המכס לפי חוק זה;\n'
            '"פעולת מכס" – כל עשיה למען הזולת כלפי רשויות המכס בקשר ליבוא, '
            'ליצוא או למעבר טובין, ששר האוצר קבע אותה בצו;\n'
            '"בעל השכלה תיכונית" – מי שהוא בעל תעודה המזכה את בעליה להתקבל '
            'למוסד שהוכר כמוסד להשכלה גבוהה;\n'
            '"הועדה" – הועדה המייעצת שנתמנתה לפי סעיף 2;\n'
            '"פקיד רשוי" – מי שנתמנה לפי סעיף 16;\n'
            '"המנהל" – מנהל המכס ומס ערך מוסף.'
        ),
    },
    "2": {
        "ch": "2",
        "t": "ועדה מייעצת",
        "s": "Advisory committee: 7 members appointed by Director, includes customs agent reps, Ministry of Transport, Chamber of Commerce, Manufacturers Association",
        "f": (
            '(א) המנהל ימנה ועדה מייעצת בת שבעה חברים, לענין חוק זה, ויקבע את דרך פעולתה.\n'
            '(ב) הועדה תקבע את סדרי דיוניה ככל שלא קבעם המנהל.\n'
            '(ג) חברי הועדה יהיו –\n'
            '(1) המשנה למנהל או סגן המנהל שמינה המנהל, אשר יכהן כיושב ראש הועדה;\n'
            '(2) שלושה נציגים של סוכני המכס, שמינה המנהל בהתייעצות עם הגופים המייצגים סוכני מכס;\n'
            '(3) עובד משרד התחבורה שהציע המנהל הכללי של משרד התחבורה;\n'
            '(4) נציג איגוד לשכות המסחר בישראל;\n'
            '(5) נציג התאחדות התעשיינים בישראל.'
        ),
    },
    "3": {
        "ch": "2",
        "t": "איסור לפעול ללא רישום",
        "s": "Prohibition to act as customs agent without registration. Exceptions: lawyers (per Bar Association Law), bonded warehouse operators, ship agents",
        "f": (
            '(א) לא יפעל אדם כסוכן מכס, לא יפרסם ולא יציג עצמו ולא יתחזה כסוכן מכס, '
            'אלא אם הוא רשום בפנקס סוכני המכס לפי חוק זה, ולא יעסוק בסוכנות מכס '
            'אלא בהתאם לאמור ברישום.\n'
            '(ג) הוראות חוק זה אינן באות לפגוע בזכותו –\n'
            '(1) של עורך-דין לעסוק בכל פעולה מהפעולות המנויות בסעיף 20 לחוק לשכת עורכי-הדין;\n'
            '(2) של בעל רשיון למחסן רשוי כללי כמשמעותו בסעיף 69 לפקודת המכס – לטפל בהחסנת טובין;\n'
            '(3) של אדם שעיסוקו ניהול משא ומתן עם רשות המכס בקשר עם כניסתן והפלגתן של אניות.'
        ),
    },
    "3א": {
        "ch": "2",
        "t": "ייחוד פעולות מכס",
        "s": "Exclusive customs actions: only registered agents or licensed clerks may perform customs actions. Import/export declarations may be signed by goods owner under conditions",
        "f": (
            '(א) לא יעשה אדם פעולת מכס אלא אם כן הוא סוכן מכס או פקיד רשוי; '
            'סוכן מכס שהוא תאגיד לא יעשה פעולת מכס אלא באמצעות יחיד שהוא סוכן מכס או פקיד רשוי מטעמו.\n'
            '(ב) על אף האמור בסעיף קטן (א), חתימה על הצהרת ייבוא לפי סימן ה\' בפרק רביעי לפקודת המכס '
            'או הצהרת ייצוא לפי סימן ב\' בפרק שישי לפקודה האמורה רשאי לחתום גם בעל הטובין '
            'שאישר גובה המכס את חתימתו.'
        ),
    },
    "3ב": {
        "ch": "2",
        "t": "בקשה לרישום סוכן מכס",
        "s": "Application for registration: submit to Director, published in Reshumot, decision after 60 days",
        "f": (
            'המבקש להירשם כסוכן מכס יגיש למנהל בקשה לכך; '
            'הבקשה תפורסם ברשומות והמנהל לא יחליט בה לפני תום ששים ימים מיום הפרסום.'
        ),
    },
    "4": {
        "ch": "2",
        "t": "תנאים לרישום סוכן מכס",
        "s": "Registration conditions for individual: Israeli resident, age 23+, secondary education, passed exams, 3-year apprenticeship. Disqualification: former customs/police/IDF employee within 3 years, criminal conviction within 10 years",
        "f": (
            '(א) יחיד יהא כשיר לרישום כסוכן מכס אם נתקיימו בו כל אלה:\n'
            '(1) הוא תושב ישראל;\n'
            '(2) מלאו לו 23 שנה;\n'
            '(3) הוא בעל השכלה תיכונית, אלא שהמנהל רשאי, במקרים הנראים לו, '
            'לוותר על קיום תנאי זה, כולו או מקצתו;\n'
            '(4) עמד בבחינות שנקבעו על ידי המנהל בהתייעצות עם הועדה;\n'
            '(5) התמחה בפעולות מכס לפחות שלוש שנים בהתאם לכללים והתנאים שנקבעו.\n'
            '(ב) לא יירשם יחיד כסוכן מכס אם נתקיים בו אחד מאלה:\n'
            '(1) בשלוש השנים שקדמו להגשת הבקשה לרישום היה פקיד מכס, או עובד מדינה, או שוטר, '
            'או עובד רשות שדות הנמלים מהסוגים שקבע המנהל הכללי;\n'
            '(2) תוך עשר שנים שקדמו להגשת הבקשה לרישום הורשע או נשא עונש מאסר על עבירה שיש עמה קלון;\n'
            '(3) נפסל לשירות המדינה, גורש מן המשטרה, או גורש מצה"ל על פי פסק דין.'
        ),
    },
    "5": {
        "ch": "2",
        "t": "כשירות תאגיד להירשם בפנקס",
        "s": "Corporate registration: must be registered in Israel, authorized for customs actions, have at least one active director/employee who is a registered customs agent (cannot serve in another firm simultaneously)",
        "f": (
            'תאגיד יהא כשיר לרישום כסוכן מכס אם נתקיימו בו כל אלה:\n'
            '(1) הוא רשום בישראל;\n'
            '(2) הוא רשאי במסגרת הפעולות או המטרות שנקבעו לו, לבצע פעולות מכס;\n'
            '(3) יש בו לפחות מנהל פעיל אחד או פקיד אחד שהוא אחראי לפעולות מכס או שותף אחד, '
            'לפי המקרה, שהוא סוכן מכס ובלבד שסוכן מכס כאמור לא יבצע פעולת מכס '
            'בתאגיד נוסף או כסוכן מכס עצמאי.'
        ),
    },
    "6": {
        "ch": "2",
        "t": "פנקס סוכני המכס",
        "s": "Customs agents registry maintained by Director. Agent may practice from registration date until Dec 31 of each year, subject to annual fee payment",
        "f": (
            '(א) המנהל ינהל פנקס שבו ירשום כסוכן מכס את מי שהתקיימו בו הוראות סעיף 4, '
            'ויתן למי שרשום בו תעודה שהוא סוכן מכס.\n'
            '(ב) מי שרשום בפנקס, רשאי לשמש סוכן מכס מיום רישומו ועד יום 31 בדצמבר של כל שנה '
            'ובלבד ששילם את אגרת הרישום לאותה שנה לפי הוראות סעיף 31.'
        ),
    },
    "7": {
        "ch": "2",
        "t": "סמכות המנהל לרשום",
        "s": "Director may register as general agent or limited agent (specific transaction types or locations), after consulting advisory committee",
        "f": (
            'המנהל רשאי, לאחר התייעצות עם הועדה, לרשום בפנקס אדם כסוכן מכס כללי, '
            'או כסוכן מכס מוגבל לסוגי עסקאות פלונים או למקומות פלונים.'
        ),
    },
    "11": {
        "ch": "3",
        "t": "מחיקת רישום",
        "s": "Mandatory deregistration: ceased Israeli residency, corporate conditions unmet (60-day cure for Art 5(3)), criminal conviction. Discretionary: 2-year inactivity, unfit to serve, law violation. Can be permanent or temporary",
        "f": (
            '(א) רישומו של סוכן מכס יימחק אם נתקיים בו אחד מאלה:\n'
            '(1) חדל להיות תושב ישראל;\n'
            '(2) חדל לקיים אחד התנאים המנויים בסעיף 5, אלא שבגלל אי קיום תנאי שבסעיף 5(3) '
            'לא יימחק רישומו של תאגיד כסוכן מכס אם חזר וקיים את התנאי תוך 60 יום;\n'
            '(3) הורשע בעבירה שלדעת היועץ המשפטי לממשלה יש עמה קלון.\n'
            '(ב) המנהל רשאי, לאחר התייעצות עם הועדה, למחוק רישומו של סוכן מכס, '
            'אם היה לו יסוד סביר להניח שנתקיים בו אחד מאלה:\n'
            '(1) שנתיים רצופות לא עסק באופן פעיל כסוכן מכס;\n'
            '(2) אינו ראוי לשמש כסוכן מכס;\n'
            '(3) הפר הוראה מהוראות חוק זה.\n'
            '(ג) מחיקת רישום יכול שתהא לצמיתות, או לתקופה מסויימת שבסופה יהא האדם רשאי '
            'לבקש חידוש רישומו, או לתקופה מסויימת שבסופה יחודש רישומו מאליו.\n'
            '(ד) נמחק רישומו של סוכן מכס, יפורסם הדבר בדרך שנקבעה.'
        ),
    },
    "12": {
        "ch": "3",
        "t": "אזהרה ונזיפה",
        "s": "Warning and reprimand: Director may issue instead of deregistration. May be published (without name) after appeal period expires",
        "f": (
            '(א) היה למנהל יסוד סביר להניח שסוכן מכס הפר הוראה מהוראות חוק זה, '
            'רשאי הוא, במקום למחוק רישומו, להזהירו או לנזוף בו.\n'
            '(ב) רשאי המנהל לפרסם אזהרה או נזיפה כאמור, אך לא יעשה כן כל עוד לא חלפה '
            'תקופת הערר שנקבעה בחוק זה, ואם הוגש הערר – כל עוד לא נסתיים הדיון בו; '
            'הפרסום לא יכיל שמו של האדם שניתנה לו האזהרה או הנזיפה.'
        ),
    },
    "13": {
        "ch": "3",
        "t": "איסור פעולות לשעה",
        "s": "Temporary suspension: Director may prohibit acting as agent pending investigation, max 3 months (extended during police/tax investigation)",
        "f": (
            'היה למנהל יסוד סביר להניח כי נתקיימו נסיבות המחייבות או מרשות מחיקת רישומו '
            'של אדם מן הפנקס, רשאי הוא, לאחר התייעצות עם הועדה, לאסור עליו לפעול כסוכן מכס '
            'עד שיתברר קיומן של הנסיבות, ובלבד שאיסור כאמור לא יארך משלושה חדשים, '
            'ואם התחילה חקירת משטרה או חקירת רשויות המס בעניין זה – עד גמר החקירה '
            'וההליכים המשפטיים שבעקבותיה.'
        ),
    },
    "14": {
        "ch": "3",
        "t": "סייגים",
        "s": "Safeguards: Director must consult advisory committee and give agent opportunity to present their case before deregistration or disciplinary action",
        "f": (
            'לא ישתמש המנהל בסמכות מן הסמכויות שהוענקו לו בפרק זה אלא לאחר '
            'התייעצות עם הועדה ולאחר שנתן לסוכן המכס הזדמנות נאותה להשמיע טענותיו.'
        ),
    },
    "15": {
        "ch": "3",
        "t": "תאגיד שרישומו נמחק",
        "s": "Corporate deregistration: must remove 'customs agent' from name within 3 months of deregistration",
        "f": (
            'תאגיד שנמחק רישומו כסוכן מכס חייב, תוך שלושה חדשים מיום שנמחק רישומו, '
            'להפסיק להשתמש בשם הכולל את המלים "סוכן מכס" או מלים דומות.'
        ),
    },
    "16": {
        "ch": "4",
        "t": "פקיד רשוי",
        "s": "Licensed clerk: customs agent or goods owner may appoint a licensed clerk in writing, with customs collector approval, to perform customs actions",
        "f": (
            'סוכן מכס וכן בעל טובין רשאים, באישור גובה המכס, למנות בכתב אדם אחד או יותר '
            'כפקיד רשוי מטעמם לפעולות מכס.'
        ),
    },
    "17": {
        "ch": "4",
        "t": "כשירות של פקיד רשוי",
        "s": "Licensed clerk qualification: Israeli resident, age 21+, secondary education, passed exams, 2-year apprenticeship. Same disqualifications as Art 4(b). Director may revoke if conditions not met or unfit",
        "f": (
            '(א) אדם יהא כשיר להתמנות פקיד רשוי אם נתקיימו בו כל אלה:\n'
            '(1) הוא תושב ישראל;\n'
            '(2) מלאו לו 21 שנה;\n'
            '(3) הוא בעל השכלה תיכונית;\n'
            '(4) עמד בבחינות שנקבעו על ידי המנהל בהתייעצות עם הועדה;\n'
            '(5) התמחה בפעולות מכס לפחות שנתיים בהתאם לכללים ולתנאים שנקבעו.\n'
            '(ב) הוראות סעיף 4(ב) יחולו, בשינויים המחויבים, על בקשה לאישור פקיד רשוי.\n'
            '(ג) גובה המכס רשאי לבטל אישור של פקיד רשוי, אם חדל האדם למלא אחד '
            'מהתנאים בסעיף קטן (א), או אם יש לו יסוד סביר להניח שאינו ראוי לשמש כפקיד רשוי.'
        ),
    },
    "18": {
        "ch": "4",
        "t": "החלת הוראות על פקיד רישוי",
        "s": "Articles 11(a), 12, and 13 apply to licensed clerks (except deregistration provisions)",
        "f": (
            'הוראות סעיף 11(א), 12 ו-13 יחולו, בשינויים המחויבים, על ביטול אישורו של פקיד רשוי.'
        ),
    },
    "19": {
        "ch": "4",
        "t": "הודעה על הפסקת העסקה",
        "s": "Termination notice: customs agent must notify customs collector when a licensed clerk's employment ends. Clerk's license automatically revoked",
        "f": (
            '(א) סוכן מכס חייב להודיע לגובה המכס בכתב כאשר פקיד רשוי שהוא העסיקו חדל '
            'מלהיות מועסק על ידיו.\n'
            '(ב) אישורו של פקיד רישוי יבוטל אם –\n'
            '(1) חדל למלא אחד מהתנאים האמורים בסעיף 17(א);\n'
            '(2) סוכן המכס שמטעמו הוא מועסק הודיע על הפסקת העסקתו.'
        ),
    },
    "20": {
        "ch": "5",
        "t": "מהימנות ויושר",
        "s": "Duty of fidelity and integrity: agent must act with reliability, loyalty and integrity towards customs authorities and clients",
        "f": (
            'סוכן מכס יפעל בפעולות מכס במהימנות, בנאמנות וביושר הן כלפי רשויות המכס והן כלפי לקוחותיו.'
        ),
    },
    "21": {
        "ch": "5",
        "t": "ניהול רשומות",
        "s": "Record-keeping: agent must maintain records and ledgers as prescribed by regulations for all customs actions performed",
        "f": (
            'סוכן מכס ינהל רשומות ופנקסים, כפי שנקבע בתקנות, לענין פעולות מכס שביצע.'
        ),
    },
    "22": {
        "ch": "5",
        "t": "אחריות סוכן מכס",
        "s": "Corporate agent responsibility: corporate customs agent may only perform customs actions through an individual who is a registered agent or licensed clerk",
        "f": (
            'תאגיד-סוכן מכס לא יעשה פעולת מכס אלא על ידי יחיד שהוא סוכן מכס או פקיד רשוי.'
        ),
    },
    "23": {
        "ch": "6",
        "t": "ערר",
        "s": "Appeal: person aggrieved by Director's or customs collector's decision may appeal to District Court within prescribed period",
        "f": (
            'מי שנפגע מהחלטה של המנהל או של גובה המכס לפי חוק זה, רשאי לערור עליה '
            'לפני בית המשפט המחוזי, תוך התקופה שנקבעה בתקנות.'
        ),
    },
    "24א": {
        "ch": "6.1",
        "t": "הגדרות — משלחים בינלאומיים",
        "s": "International forwarder definitions: person who arranges international cargo transport on behalf of others as regular business, including consolidated shipments",
        "f": (
            'בפרק זה –\n'
            '"משלח בינלאומי" – מי שעיסוקו, דרך קבע, סידור הובלת טובין בינלאומית בשביל זולתו, '
            'ובכלל זה הובלה בדרך של מטענים מאוחדים;\n'
            '"הובלה בינלאומית" – הובלת טובין מישראל לחוץ לארץ או מחוץ לארץ לישראל;\n'
            '"מטענים מאוחדים" – טובין של שני בעלים או יותר המאוחדים למשלוח אחד.'
        ),
    },
    "24ב": {
        "ch": "6.1",
        "t": "החלת הוראות על משלח בינלאומי",
        "s": "Application to international forwarders: registration, qualification, deregistration, duties, appeal and penalty provisions apply to international forwarders with necessary modifications",
        "f": (
            'הוראות פרקים ב\', ג\', ה\', ו\' ו-ז\' יחולו, בשינויים המחויבים, '
            'על משלח בינלאומי ועל מי שמבקש להירשם כמשלח בינלאומי.'
        ),
    },
    "25": {
        "ch": "7",
        "t": "מסירת ידיעות ומסמכים",
        "s": "Director may demand information and documents from customs agent or licensed clerk relating to their customs activities",
        "f": (
            'המנהל או מי שהוסמך לכך על ידיו בכתב רשאי לדרוש מסוכן מכס או מפקיד רשוי '
            'ידיעות ומסמכים הנוגעים לפעולותיו כסוכן מכס או כפקיד רשוי.'
        ),
    },
    "26": {
        "ch": "7",
        "t": "סמכות חקירה",
        "s": "Investigation powers: Director has all powers that can be granted to a commission of inquiry under the Commissions of Inquiry Ordinance",
        "f": (
            'לענין חוק זה יהיו למנהל כל הסמכויות שניתן להעניק לועדת חקירה '
            'לפי פקודת ועדות חקירה.'
        ),
    },
    "27": {
        "ch": "7",
        "t": "עונשין",
        "s": "Penalties: fraudulent registration = 3 years imprisonment; acting without registration = 1 year + fine; using 'customs agent' title without registration = fine; obstructing Director's powers or withholding documents = 6 months",
        "f": (
            '(א) המשיג במרמה רישום בפנקס כסוכן מכס או אישור כפקיד רשוי, '
            'דינו – מאסר שלוש שנים.\n'
            '(ב) העושה פעולת מכס או מפרסם או מציג עצמו או מתחזה כסוכן מכס '
            'בניגוד להוראות סעיף 3, דינו – מאסר שנה או קנס.\n'
            '(ג) המפר הוראה מהוראות סעיף 15 (שימוש בשם סוכן מכס לאחר מחיקת רישום), '
            'דינו – קנס.\n'
            '(ד) המפריע למנהל או למי שהוסמך על ידיו בהפעלת סמכויותיו לפי חוק זה, '
            'או המסרב או הנמנע מלמסור ידיעות או מסמכים שנדרשו ממנו לפי סעיף 25, '
            'דינו – מאסר ששה חדשים.'
        ),
    },
    "28": {
        "ch": "7",
        "t": "אחריותם של מנהלים ופקידים",
        "s": "Corporate criminal liability: if offense committed by corporation, every director, active partner, or officer responsible for customs shall also be liable",
        "f": (
            'נעברה עבירה לפי חוק זה על ידי תאגיד, יאשם בה גם כל מנהל, שותף פעיל, '
            'או פקיד אחראי לפעולות מכס של התאגיד, אלא אם הוכיח שהעבירה נעברה שלא בידיעתו '
            'ושנקט אמצעים סבירים כדי למנוע ביצועה.'
        ),
    },
    "29": {
        "ch": "7",
        "t": "אחריותם של סוכני מכס למעשי פקידיהם",
        "s": "Agent vicarious liability: customs agent liable for offenses committed by their employees unless agent proves lack of knowledge and took reasonable prevention measures",
        "f": (
            'נעברה עבירה לפי חוק זה על ידי פקיד רשוי, יאשם בה גם סוכן המכס '
            'שמטעמו פעל פקיד הרשוי, אלא אם הוכיח שהעבירה נעברה שלא בידיעתו '
            'ושנקט אמצעים סבירים כדי למנוע ביצועה.'
        ),
    },
    "29א": {
        "ch": "7",
        "t": "אחריות של מרשה",
        "s": "Principal's liability: if customs agent or licensed clerk commits offense on behalf of principal, the principal is also liable unless they prove lack of knowledge",
        "f": (
            '(א) נעברה עבירה לפי פקודת המכס בידי סוכן מכס או פקיד רשוי בשמו של מרשה, '
            'יאשם בה גם המרשה אלא אם כן הוכיח שהעבירה נעברה שלא בידיעתו.\n'
            '(ב) לענין סעיף זה, "מרשה" – מי שהרשה סוכן מכס או פקיד רשוי לפעול בשמו '
            'בפעולת מכס שבקשר אליה נעברה העבירה.'
        ),
    },
    "30": {
        "ch": "7",
        "t": "הוראות שמורות",
        "s": "Savings clause: this law supplements other legislation without derogating from it",
        "f": 'הוראות חוק זה באות להוסיף על הוראות חיקוקים אחרים ולא לגרוע מהם.',
    },
    "31": {
        "ch": "7",
        "t": "אגרה שנתית",
        "s": "Annual fee required for customs agent and licensed clerk to continue practicing each year after initial registration",
        "f": (
            'הרוצה לפעול כסוכן מכס או כפקיד רשוי בכל שנה שלאחר השנה שבה נרשם בפנקס '
            'או אושר כפקיד רשוי, ישלם אגרה שנתית שנקבעה.'
        ),
    },
    "32": {
        "ch": "7",
        "t": "תקנות",
        "s": "Regulations: Minister of Finance authorized to promulgate regulations for implementation. Regulations on exams, apprenticeship, and registration require Knesset Finance Committee approval",
        "f": (
            '(א) שר האוצר ממונה על ביצוע חוק זה והוא רשאי להתקין תקנות בכל ענין '
            'הנוגע לביצועו.\n'
            '(ב) תקנות הנוגעות לבחינות, לתקופת ההתמחות ולרישום סוכני מכס ופקידים רשויים '
            'טעונות אישור ועדת הכספים של הכנסת.'
        ),
    },
    "33": {
        "ch": "7",
        "t": "הוראות מעבר",
        "s": "Transitional provisions: existing license holders deemed registered. Licensed clerks with 3+ years experience get 2-year exam grace period. Corporate agents must meet qualifications within 6 months",
        "f": (
            '(א) המחזיק ערב תחילתו של חוק זה ברשיון בר-תוקף שניתן לפי פקודת סוכני בתי המכס '
            'יראוהו כאילו נרשם בפנקס לפי חוק זה.\n'
            '(ב) פקיד רשוי שנתמנה לפי פקודת סוכני בתי המכס ועסק באופן פעיל בפעולות מכס '
            'שלוש שנים לפחות מתוך שש שנים שקדמו לתחילתו של חוק זה, יהא חייב לעמוד '
            'תוך שנתיים בבחינות לפקיד רשוי.\n'
            '(ג) תאגיד שנרשם כאמור בסעיף קטן (א), ימחוק המנהל את רישומו כתום ששה חדשים '
            'מיום פירסום חוק זה אם לא נתקיימו בו כל תנאי הכשירות הנדרשים.'
        ),
    },
    "34": {
        "ch": "7",
        "t": "ביטול",
        "s": "Repeal: the Customs House Agents Ordinance is hereby repealed",
        "f": 'פקודת סוכני בתי המכס – בטלה.',
    },
    "35": {
        "ch": "7",
        "t": "תחילה",
        "s": "Commencement: this law takes effect on January 1, 1965 (27 Tevet 5725)",
        "f": 'תחילתו של החוק היא ביום כ"ז בטבת תשכ"ה (1 בינואר 1965).',
    },
}


# ── Search helpers ────────────────────────────────────────────────

def search_customs_agents_law(query):
    """Search the Customs Agents Law by article number, chapter, or keyword.

    Returns dict with found, type, results.
    """
    import re as _re

    q = query.strip().lower()

    # Case 1: Article lookup — "סעיף 4", "article 27", "§3א"
    m = _re.search(r'(?:סעיף|article|§)\s*(\d{1,2}[א-ת]?)', q)
    if not m:
        m = _re.match(r'^(\d{1,2}[א-ת]?)$', q)
    if m:
        art_id = m.group(1)
        art = CUSTOMS_AGENTS_ARTICLES.get(art_id)
        if art:
            return {
                "found": True,
                "type": "customs_agents_article",
                "article_id": art_id,
                "chapter": art["ch"],
                "title_he": art["t"],
                "summary_en": art["s"],
                "full_text_he": art["f"],
            }

    # Case 2: Chapter lookup — "פרק 2", "chapter 3"
    m = _re.search(r'(?:פרק|chapter)\s*(\d)', q)
    if m:
        ch = m.group(1)
        ch_data = CUSTOMS_AGENTS_CHAPTERS.get(ch)
        if ch_data:
            articles = []
            for aid in ch_data["articles"]:
                a = CUSTOMS_AGENTS_ARTICLES.get(aid, {})
                articles.append({
                    "article_id": aid,
                    "title_he": a.get("t", ""),
                    "summary_en": a.get("s", ""),
                })
            return {
                "found": True,
                "type": "customs_agents_chapter",
                "chapter": ch,
                "title_he": ch_data["title_he"],
                "title_en": ch_data["title_en"],
                "articles": articles,
            }

    # Case 3: Keyword search across all articles
    results = []
    # Strip Hebrew prefixes
    prefixes = ("ל", "ב", "ה", "ש", "מ", "כ", "ו", "של", "וה")
    words = set()
    for w in q.split():
        words.add(w)
        for p in prefixes:
            if w.startswith(p) and len(w) > len(p) + 1:
                words.add(w[len(p):])

    for art_id, art in CUSTOMS_AGENTS_ARTICLES.items():
        searchable = f"{art['t']} {art['s']} {art['f']}".lower()
        score = sum(1 for w in words if w in searchable)
        if score > 0:
            results.append((score, art_id, art))

    results.sort(key=lambda x: -x[0])
    if results:
        return {
            "found": True,
            "type": "customs_agents_search",
            "results": [
                {
                    "article_id": aid,
                    "title_he": a["t"],
                    "summary_en": a["s"],
                    "text_snippet": a["f"][:300],
                    "relevance": sc,
                }
                for sc, aid, a in results[:10]
            ],
        }

    return {"found": False, "type": "customs_agents_search", "results": []}
