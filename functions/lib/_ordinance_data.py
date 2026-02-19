"""
Comprehensive Customs Ordinance articles data.
Generated from pkudat_mechess.txt (272K chars, 9,897 lines).
Covers ALL 17 chapters and ~275 articles.

This file is imported by customs_law.py to replace the partial BLOCK 4B.
"""

# Chapter metadata
ORDINANCE_CHAPTERS = {
    1:   {"title_he": "מבוא", "title_en": "Introduction", "articles_range": "1-2"},
    2:   {"title_he": "מינהל", "title_en": "Administration", "articles_range": "3-13"},
    3:   {"title_he": "פיקוח, בדיקה, הצהרות וערובה", "title_en": "Supervision, Inspection, Declarations and Security", "articles_range": "14-39א"},
    4:   {"title_he": "ייבוא טובין", "title_en": "Import of Goods", "articles_range": "40-67"},
    5:   {"title_he": "החסנת טובין", "title_en": "Warehousing of Goods", "articles_range": "68-99"},
    6:   {"title_he": "ייצוא טובין", "title_en": "Export of Goods", "articles_range": "100-119"},
    7:   {"title_he": "צידת אניה", "title_en": "Ship's Stores", "articles_range": "120-123"},
    8:   {"title_he": "תשלומי מכס", "title_en": "Customs Payments (Valuation)", "articles_range": "123א-155"},
    9:   {"title_he": "הישבון וכניסה זמנית", "title_en": "Drawback and Temporary Admission", "articles_range": "156-162ג"},
    10:  {"title_he": "סחר החוף", "title_en": "Coastal Trade", "articles_range": "163-167"},
    11:  {"title_he": "סוכנים", "title_en": "Agents", "articles_range": "168-171"},
    12:  {"title_he": "סמכויותיהם של פקידי-מכס", "title_en": "Powers of Customs Officers", "articles_range": "172-202"},
    13:  {"title_he": "חילוטין ועונשין", "title_en": "Forfeitures and Penalties", "articles_range": "203-223"},
    "13א": {"title_he": "אמצעי אכיפה מינהליים", "title_en": "Administrative Enforcement", "articles_range": "223א-223יח"},
    14:  {"title_he": "אישומי מכס", "title_en": "Customs Prosecutions", "articles_range": "224-230"},
    "14א": {"title_he": "דיווח אלקטרוני", "title_en": "Electronic Reporting", "articles_range": "230א-230ח"},
    15:  {"title_he": "הוראות שונות", "title_en": "Miscellaneous Provisions", "articles_range": "231-241"},
}


# ════════════════════════════════════════════════════════════════════
# All articles, keyed by article number (string).
# Structure per article:
#   "N": {"ch": chapter, "t": title_he, "s": summary_en, ...}
# Critical articles have additional fields (definitions, methods, etc.)
# Repealed articles: {"ch": N, "t": "...", "repealed": True}
# ════════════════════════════════════════════════════════════════════

ORDINANCE_ARTICLES = {

    # ══════════════════════════════════════════════
    # CHAPTER 1: INTRODUCTION (מבוא)
    # ══════════════════════════════════════════════

    "1": {
        "ch": 1, "t": "הגדרות", "s": "Foundational definitions for the entire Customs Ordinance and all customs laws.",
        "definitions": {
            "טובין חבי מכס": "Goods subject to customs duty.",
            "בעל (טובין)": "Owner: importer, exporter, consignee, agent, holder, or anyone with beneficial interest or control.",
            "הברחה": "Smuggling: import/export/transport with intent to defraud Treasury or evade prohibition — including attempts.",
            "הצהרת ייבוא": "Import declaration per Section 62.",
            "הצהרת ייצוא": "Export declaration per Section 103.",
            "מצהר": "Cargo manifest per Section 53.",
            "סוכן מכס": "Customs agent per Customs Agents Law (חוק סוכני המכס, תשכ\"ה-1964).",
            "פקיד מכס": "Customs officer: any non-laborer employed by customs authority.",
            "מסי יבוא": "Import taxes: customs duty + purchase tax + VAT + all other import levies.",
            "מסמכי העדפה": "Preference documents (EUR.1, origin declarations) under trade agreements.",
            "כלי הובלה": "Transport vehicle: vessel, vehicle, aircraft, or animal.",
            "מחסן רשוי": "Licensed warehouse for goods under customs supervision.",
            "מחסן המכס": "Customs warehouse: government place for depositing goods securing payment.",
            "הישבון": "Drawback: refund of customs duties (Ch. 9) or cancellation of deferred debt.",
            "שטעון": "Transit: export of imported goods remaining under customs supervision.",
            "נמל": "Port, airport, transit terminal, or border crossing as confirmed by Director.",
            "גובה מכס": "Customs collector: the Director and any customs officer serving in that matter.",
            "תעודות": "Documents: all types including books, printouts, and computer-stored information.",
            "אריזה": "Packaging: anything goods destined for transport are packed, covered, or bound in.",
            "המנהל": "The Director: head of customs administration.",
        },
    },
    "2": {
        "ch": 1, "t": "חובה להשיב תשובות ולמסור תעודות",
        "s": "Must answer truthfully (best of knowledge) and submit all relevant documents (best of ability).",
    },

    # ══════════════════════════════════════════════
    # CHAPTER 2: ADMINISTRATION (מינהל)
    # ══════════════════════════════════════════════

    "3": {"ch": 2, "t": "תפקידי המנהל", "s": "Director is chief administrative authority for customs."},
    "4": {"ch": 2, "t": "אצילת סמכויות", "s": "Director may delegate powers in writing; revocable; does not extinguish Director's own authority."},
    "5": {"ch": 2, "t": "דגל המכס", "s": "Customs service vessels carry prescribed identification flag."},
    "6": {"ch": 2, "t": "קביעת נמלים, שדות תעופה",
        "s": "Government may designate by order: boarding stations, places of entry, aviation stations, overland routes, wharves, examination places. May be limited or unlimited in scope.",
    },
    "7": {"ch": 2, "t": "סידורים ברציפים", "s": "Wharf owner must provide customs office space and sheltered storage if Director requests."},
    "8": {"ch": 2, "t": "הצהרה בפני מי", "s": "Declarations may be made before customs collector, authorized officer, or any legally authorized person."},
    "9": {"ch": 2, "t": "בוטל", "repealed": True, "s": "Formerly prohibited declarations from minors under 18. Repealed 1995."},
    "10": {"ch": 2, "t": "ימי עבודה ושעות עבודה", "s": "Cargo operations restricted to official work days/hours unless overtime authorized."},
    "11": {"ch": 2, "t": "בוטל", "repealed": True, "s": "Formerly: overtime fees. Repealed 2018."},
    "12": {"ch": 2, "t": "בוטל", "repealed": True, "s": "Formerly: porter regulations. Repealed 2018."},
    "13": {"ch": 2, "t": "אגרות השגחה", "s": "Government may prescribe fees for: guarding goods, remote supervision, special arrangements, explosives/flammables handling."},

    # ══════════════════════════════════════════════
    # CHAPTER 3: SUPERVISION, INSPECTION, DECLARATIONS (פיקוח, בדיקה, הצהרות)
    # ══════════════════════════════════════════════

    "14": {"ch": 3, "t": "הפיקוח על טובין",
        "s": "Import: supervised from import until delivery/export. Export: from export site or declaration filing, whichever earlier, until export.",
    },
    "15": {"ch": 3, "t": "טובין בכלי הובלה", "s": "Goods in transport vehicles from abroad supervised while vehicle in Israeli port or foreign trade."},
    "16": {"ch": 3, "t": "זכות בדיקה", "s": "Customs may examine any goods under its supervision."},
    "17": {"ch": 3, "t": "הובלת טובין", "s": "All handling, examination prep, and storage costs borne by goods owner."},
    "18": {"ch": 3, "t": "שטר מסירה", "s": "Holder of delivery order treated as owner or authorized agent. Includes international forwarders."},
    "19": {"ch": 3, "t": "פתיחת אריזות",
        "s": "Opening packages for examination requires owner/consignee presence. 15-day wait if absent. Exception: perishable, prohibited, dangerous goods.",
    },
    "20": {"ch": 3, "t": "סימון ומספר אריזות", "s": "Customs officer may require marking/numbering at owner's expense."},
    "21": {"ch": 3, "t": "טובין במצב רע", "s": "Damaged goods set aside for examination; damage certificate may be demanded from captain."},
    "22": {"ch": 3, "t": "אין לנגוע בטובין", "s": "Supervised goods shall not be moved/altered without authority. Fine: 100 liras."},
    "23": {"ch": 3, "t": "אין תביעת פיצויים", "s": "No State liability for loss/damage to supervised goods unless willful act by customs officer."},
    "24": {"ch": 3, "t": "הצהרות",
        "s": "Mandatory filing of import declaration (Ch.4 §E) or export declaration (Ch.6 §B). Amendment 28 replaced the old רשמון system.",
    },
    "25": {"ch": 3, "t": "בוטל", "repealed": True, "s": "Formerly: hand-delivery of רשמון. Repealed 1995."},
    "26": {"ch": 3, "t": "בוטל", "repealed": True, "s": "Formerly: special customs entries. Repealed 2018."},
    "27": {"ch": 3, "t": "בוטל", "repealed": True, "s": "Formerly: duty to answer about רשמון. Repealed 2018."},
    "28": {"ch": 3, "t": "בוטל", "repealed": True, "s": "Formerly: approval of רשמון as registration. Repealed 2018."},
    "29": {"ch": 3, "t": "בוטל", "repealed": True, "s": "Formerly: immediate handling per approved entry. Repealed 2018."},
    "30": {"ch": 3, "t": "מטען אישי של נוסעים", "s": "Accompanied passenger luggage may be imported/exported without declaration, subject to conditions."},
    "30א": {"ch": 3, "t": "חובת מתן הצהרה",
        "s": "Finance Minister may require declarations in writing, oral, by conduct, or other manner. May apply generally or by category.",
    },
    "31": {"ch": 3, "t": "זכות לדרוש ערובה",
        "s": "Customs may demand bonds/sureties. May refuse delivery until bond given. Joint and several liability.",
    },
    "32": {"ch": 3, "t": "בוטל", "repealed": True, "s": "Formerly: forms of security. Repealed 1995."},
    "33": {"ch": 3, "t": "ערובה כללית", "s": "Director may accept general/blanket bond covering all transactions for approved period and amount."},
    "34": {"ch": 3, "t": "חילוט ערבון", "s": "Cash deposit forfeited if conditions not met within deadline."},
    "35": {"ch": 3, "t": "ערובה חדשה", "s": "Collector may demand new bond at any time if existing one deemed insufficient."},
    "36": {"ch": 3, "t": "כוחה של ערובה", "s": "Bond document is prima facie proof in court; burden shifts to defendant."},
    "37": {"ch": 3, "t": "מתן היתר טובין", "s": "All customs permits conditional; collector may revoke, modify, or suspend."},
    "38": {"ch": 3, "t": "המיובאים בדואר", "s": "Mail imports get full customs supervision like all other imports."},
    "39": {"ch": 3, "t": "חבילות דואר",
        "s": "Director may accept postal form/label as import declaration. Non-matching goods subject to forfeiture.",
    },
    "39א": {"ch": 3, "t": "בוטל", "repealed": True, "s": "Formerly: third-party customs payment. Repealed 2018."},

    # ══════════════════════════════════════════════
    # CHAPTER 4: IMPORT OF GOODS (ייבוא טובין)
    # ══════════════════════════════════════════════

    "40": {"ch": 4, "t": "סמכות לאסור יבוא", "s": "Government may prohibit/restrict/regulate import by order, by land/sea/air, by country/route."},
    "41": {"ch": 4, "t": "יבוא אסור", "s": "No person shall import goods whose import is prohibited."},
    "42": {"ch": 4, "t": "טובין אסורים", "s": "Prohibited: goods banned by law, counterfeit coins, obscene materials."},
    "43": {"ch": 4, "t": "יבוא מוגבל", "s": "Restricted goods importable only per applicable restrictions/regulations."},
    "44": {"ch": 4, "t": "טובין אסורים בטרנזיט", "s": "Transit exception for prohibited goods in manifest, unless transshipment banned by law/treaty."},
    "45": {"ch": 4, "t": "ייבוא בדרך הים", "s": "Sea import requires: boarding permitted, manifest submitted, goods unloaded for inspection."},
    "46": {"ch": 4, "t": "חובת אניה להיכנס לנמל", "s": "Ships must enter designated ports only, unless force majeure."},
    "47": {"ch": 4, "t": "חובת אניה להיענות", "s": "Must stop for customs boarding in Israeli coastal waters."},
    "48": {"ch": 4, "t": "עצירה בתחנת מעלה", "s": "Stop at boarding station upon arrival from abroad."},
    "49": {"ch": 4, "t": "הקלות לעליה", "s": "Captain must facilitate customs officer boarding."},
    "50": {"ch": 4, "t": "למהר למקום הפריקה", "s": "Proceed directly to unloading point after customs boarding."},
    "51": {"ch": 4, "t": "אין להשיט בלי רשות", "s": "Ship cannot depart until cargo fully discharged, unless authorized."},
    "52": {"ch": 4, "t": "הגבלת העליה", "s": "Only port pilot, government doctor, or authorized persons may board before customs."},
    "53": {"ch": 4, "t": "הגשת מצהר",
        "s": "Manifest required for all imports. Deadlines: sea=24hrs before arrival, air=4hrs, land=1 day. Director prescribes format.",
        "key": "Sea import manifest 24 hours before arrival; air 4 hours; land 1 day.",
    },
    "54": {"ch": 4, "t": "תיקון מצהר", "s": "Director may permit corrected manifest; fee applies."},
    "54א": {"ch": 4, "t": "מצהר אלקטרוני", "s": "Manifest must be submitted electronically per Chapter 14A."},
    "55": {"ch": 4, "t": "קברניט אניה שנטרפה", "s": "Wreck/loss: captain must submit manifest at nearest customs house."},
    "55א": {"ch": 4, "t": "חובה לסייע לפקיד", "s": "Must facilitate customs access, answer questions, submit documents about vehicle and cargo."},
    "56": {"ch": 4, "t": "פירוק הצובר", "s": "No breaking bulk without customs permission or valid release."},
    "57": {"ch": 4, "t": "הסרת טובין מאניה", "s": "Unloading only at designated places with customs permission; captain liable for improper placement."},
    "58": {"ch": 4, "t": "חובה להפקיד", "s": "Unloaded goods must be immediately deposited in customs warehouse or approved place."},
    "59": {"ch": 4, "t": "אריזה חוזרת", "s": "Repacking on wharf allowed with permission under customs supervision."},
    "60": {"ch": 4, "t": "מניעת צפיפות", "s": "Director may halt loading/unloading to prevent congestion; customs immune from loss claims."},
    "61": {"ch": 4, "t": "חובה לפרט נימוקים", "s": "Written notice with reasons required upon request for loading/unloading halt."},
    "62": {"ch": 4, "t": "הצהרת ייבוא",
        "s": "Owner must file import declaration for: (1) domestic consumption or (2) warehousing. "
             "Required documents: invoices, insurance, B/L, packing lists, preference docs. Electronic filing via customs agent.",
        "key": "Two purposes: consumption or warehousing. Required docs: invoices, B/L, insurance, packing list, preference documents.",
    },
    "63": {"ch": 4, "t": "המועד להגשת הצהרת ייבוא",
        "s": "Deadline: 3 months from import (sea/land), 45 days (air). No declaration = goods may be sold/destroyed.",
        "key": "3 months sea/land, 45 days air.",
    },
    "64": {"ch": 4, "t": "הגשת הצהרה אלקטרונית", "s": "Import declaration + documents must be submitted electronically per Chapter 14A."},
    "65": {"ch": 4, "t": "התרה",
        "s": "Director may grant online release. Denied if: incorrect details, missing docs, unpaid taxes, no security. "
             "May suspend/revoke before delivery.",
        "key": "6 grounds for denial; Director may suspend/revoke release before delivery.",
    },
    "65א": {"ch": 4, "t": "שמירת מסמכים", "s": "Owner must retain declaration and all documents per Director's rules."},
    "65ב": {"ch": 4, "t": "חובה להשיב על שאלות", "s": "Must answer customs officer questions about declared goods."},
    "65ג": {"ch": 4, "t": "מסמך אחר", "s": "Director may allow alternative document instead of import declaration."},
    "66": {"ch": 4, "t": "ייבוא שלא בים", "s": "Non-sea imports via designated entry points and routes; certificate from border customs if forwarded."},
    "67": {"ch": 4, "t": "בוטל", "repealed": True, "s": "Formerly: border declaration for non-sea imports. Repealed 2018."},

    # ══════════════════════════════════════════════
    # CHAPTER 5: WAREHOUSING (החסנת טובין)
    # ══════════════════════════════════════════════

    "68": {"ch": 5, "t": "רישיון מחסן", "s": "License required from Director. Only goods with import declaration for warehousing + release may be stored."},
    "69": {"ch": 5, "t": "מחסנים לסוגיהם", "s": "Two types: general (public) and private warehouses."},
    "70": {"ch": 5, "t": "תקופת רשיון", "s": "Annual license, Jan 1 start. Fee due in advance; non-payment = expiry."},
    "71": {"ch": 5, "t": "ביטול רשיון", "s": "Government may revoke for cause; published in Reshumot + written notice."},
    "72": {"ch": 5, "t": "תוצאות ביטול", "s": "Revoked/expired: pay duty, export, or transfer within Director's deadline. Otherwise sold at auction."},
    "73": {"ch": 5, "t": "רשימת טובין", "s": "Customs officer prepares detailed inventory upon deposit."},
    "74": {"ch": 5, "t": "גמר האחסנה", "s": "Customs officer confirms warehousing completion."},
    "75": {"ch": 5, "t": "סילוק למחסן", "s": "Customs may move goods to warehouse; license holder pays expenses and gets lien."},
    "76": {"ch": 5, "t": "אריזה", "s": "Goods deposited in import packaging; repacked goods in packaging at declaration time."},
    "77": {"ch": 5, "t": "חובות בעל רשיון", "s": "Five duties: accessibility, scales/lighting, labor/materials, office space, inventory records."},
    "78": {"ch": 5, "t": "פתיחת מחסן", "s": "Access by permission only. Fine: 200 lira."},
    "79": {"ch": 5, "t": "גישה למחסן", "s": "Unrestricted customs access at reasonable times; forcible entry if denied."},
    "80": {"ch": 5, "t": "מדידה חוזרת", "s": "Re-measurement/weighing allowed; duty based on results."},
    "81": {"ch": 5, "t": "תשלום מכס תוך שנה", "s": "Duty on warehoused goods must be paid within 1 year. Otherwise sold. Perishables earlier."},
    "82": {"ch": 5, "t": "העברה למחסן כללי", "s": "Collector may require transfer from private to general warehouse or duty payment."},
    "83": {"ch": 5, "t": "חובת בעל רשיון", "s": "Unauthorized removal: full duty + 5 lira/package OR double duty."},
    "84": {"ch": 5, "t": "חסר בטובין", "s": "Unexplained shortage: double duty penalty on missing quantity."},
    "85": {"ch": 5, "t": "הצגה", "s": "Duty-free removal for public exhibition with Director approval and bond."},
    "86": {"ch": 5, "t": "דוגמאות", "s": "Modest samples from warehoused goods without declaration or duty."},
    "87": {"ch": 5, "t": "טיפול בטובין", "s": "Sorting, repacking, preparation for sale with permission. Worthless portions destroyed duty-free."},
    "88": {"ch": 5, "t": "הערכה שנית", "s": "Re-valuation of deteriorated ad valorem goods if accidental deterioration."},
    "89": {"ch": 5, "t": "טובין לא שווים", "s": "Director may destroy goods worth less than duty and waive duty."},
    "90": {"ch": 5, "t": "חומרים מתלקחים", "s": "Flammable/explosive goods need permission; 14-day sale if unredeemed."},
    "91": {"ch": 5, "t": "הצהרה על טובין מוחסנים", "s": "Three options for removal: consumption, export, or transfer to another warehouse."},
    "92": {"ch": 5, "t": "ויתור על מכס", "s": "Duty waiver/refund for goods lost/destroyed by force majeure."},
    "93": {"ch": 5, "t": "אבדן במסירה", "s": "Duty waiver for released goods lost during delivery/loading by force majeure."},
    "94": {"ch": 5, "t": "אחסנה להלכה", "s": "Constructive warehousing: goods treated as warehoused even if second declaration filed before deposit."},
    "95": {"ch": 5, "t": "מחסני המכס", "s": "Government designates customs warehouses; fees apply; waiver for force majeure."},
    "96": {"ch": 5, "t": "הפיכת מחסן", "s": "Director may convert licensed warehouse to customs warehouse."},
    "97": {"ch": 5, "t": "זמן תשלום", "s": "Fees payable before removal."},
    "98": {"ch": 5, "t": "סמכות למכור", "s": "Goods in customs warehouse not removed within 1 year may be sold."},
    "99": {"ch": 5, "t": "תשלום היטלים", "s": "Proof of freight/landing charges required before release."},

    # ══════════════════════════════════════════════
    # CHAPTER 6: EXPORT OF GOODS (ייצוא טובין)
    # ══════════════════════════════════════════════

    "100": {"ch": 6, "t": "סמכות לאסור יצוא", "s": "Government may prohibit/restrict/regulate export by order, any route, any destination."},
    "101": {"ch": 6, "t": "יצוא אסור", "s": "No export of prohibited goods."},
    "102": {"ch": 6, "t": "יצוא מוגבל", "s": "Restricted goods exportable only per applicable restrictions."},
    "103": {"ch": 6, "t": "הצהרת ייצוא",
        "s": "Export declaration required before export. Documents: invoices, B/L, packing list, permits, preference docs. "
             "5 business days grace for certain details. Release denied if goods not at customs site.",
        "key": "5 business days grace for post-export documents. Release denied if goods not at customs-supervised site.",
    },
    "104": {"ch": 6, "t": "טובין שלא יוצאו", "s": "Unexported goods: 3 months (sea/land) or 45 days (air) to apply for release. Otherwise sold/destroyed."},
    "105": {"ch": 6, "t": "מסמכים וערובות", "s": "Documents and security/bond may be demanded for dutiable export goods."},
    "106": {"ch": 6, "t": "קיבול כלי שיט", "s": "Min 60 registered tons for warehoused/drawback/transshipment export goods."},
    "107": {"ch": 6, "t": "טעינה מרציף", "s": "Export loading only from wharf/approved place or via licensed lighter."},
    "108": {"ch": 6, "t": "יצוא ביבשה/אוויר", "s": "Nearest customs house; prescribed route without deviation; sealed railcar for rail."},
    "109": {"ch": 6, "t": "תעודת מפדה", "s": "Captain cannot sail without clearance certificate from customs officer."},
    "110": {"ch": 6, "t": "קנס הפלגה", "s": "Penalty: 20 lira skipping inspection; 100 lira sailing with customs officer without consent."},
    "111": {"ch": 6, "t": "דרישות לפני מפדה", "s": "Exit report, Q&A, documents required; exit manifest for vessels under 300 tons."},
    "112": {"ch": 6, "t": "מסירת מצהר", "s": "Exit manifest within 24 hours of clearance; Director may extend."},
    "113": {"ch": 6, "t": "טעינת טובין שלא פורטו", "s": "No unlisted goods loaded unless Section 103 met; passenger baggage exempt."},
    "114": {"ch": 6, "t": "תיקון מצהר יציאה", "s": "Correction of obvious errors only; fee may apply."},
    "115": {"ch": 6, "t": "תנאים לפדיה", "s": "Full accounting of cargo/provisions and all legal requirements met before clearance."},
    "116": {"ch": 6, "t": "עצירה בתחנת מעלה", "s": "Stop at boarding station on departure; no sailing without customs officer consent."},
    "117": {"ch": 6, "t": "הסבר על טובין חסרים", "s": "Must produce clearance certificate and explain missing manifest goods."},
    "118": {"ch": 6, "t": "איסור פריקת טובי יצוא", "s": "No unloading of export goods without customs permission."},
    "119": {"ch": 6, "t": "תעודת הנחת", "s": "Landing certificate from destination may be required; failure may block future exports."},

    # ══════════════════════════════════════════════
    # CHAPTER 7: SHIP'S STORES (צידת אניה)
    # ══════════════════════════════════════════════

    "120": {"ch": 7, "t": "שימוש בצידת אניה", "s": "Stores for passengers/crew/ship use only; import declaration + release needed for other use."},
    "121": {"ch": 7, "t": "הנחת צידת-אניה", "s": "No unauthorized use, unloading, or landing of ship's stores."},
    "122": {"ch": 7, "t": "צידת-אניה חתומה", "s": "Customs seal on duty-free/drawback stores until final foreign departure."},
    "123": {"ch": 7, "t": "עודפי צידת-אניה", "s": "Surplus: import declaration or warehousing for future use, with permission."},

    # ══════════════════════════════════════════════
    # CHAPTER 8: CUSTOMS PAYMENTS / VALUATION (תשלומי מכס)
    # This is the MOST CRITICAL chapter for classification work.
    # ══════════════════════════════════════════════

    "123א": {
        "ch": 8, "t": "החייב במכס",
        "s": "Owner is liable for customs. Third party may assume obligation with Director's consent (full or partial).",
    },
    "123ב": {
        "ch": 8, "t": "תשלום המכס",
        "s": "Duty paid at time of import declaration. Mail: at post office if no declaration. Director determines method.",
    },
    "124": {
        "ch": 8, "t": "המועד הקובע לשיעור המכס",
        "s": "Rate at time of payment (default). Exceptions: mail goods (assessment time), "
             "no declaration (import time), conditional exemption (when condition ceases).",
        "key": "Default: rate at payment time. Conditional exemption: rate when condition ceases.",
    },
    "125": {"ch": 8, "t": "משקלות ומידות", "s": "Weights/measures per Customs Authority approved standards."},
    "126": {"ch": 8, "t": "חישוב יחסי", "s": "Pro rata calculation for any deviation from specified unit."},
    "127": {"ch": 8, "t": "כמות גדולה יותר", "s": "Goods sold as larger than actual: duty on declared/apparent quantity."},
    "128": {"ch": 8, "t": "בוטל", "repealed": True, "s": "Formerly: place of payment. Repealed 1995."},

    # ── VALUATION FRAMEWORK: Articles 129-133ט ──
    "129": {
        "ch": 8, "t": "הגדרות ופרשנות (הערכה)",
        "s": "Definitions for WTO valuation framework (§§129-134א). Defines: goods being valued, identical goods, "
             "similar goods, Israeli component, production, commercial level, special relationships "
             "(8 criteria incl. 5% ownership threshold, family members), personal vs commercial use.",
        "key": "Special relationships: 8 criteria; 5% ownership threshold; family members enumerated. "
               "Israeli component excluded from identical/similar goods.",
    },
    "130": {
        "ch": 8, "t": "דרכי קביעת ערכם של טובין מוערכים",
        "s": "THE MASTER HIERARCHY: 7 valuation methods in MANDATORY sequential order (WTO/GATT Article VII).",
        "methods": [
            {"number": 1, "name_en": "Transaction Value", "name_he": "ערך עסקה",
             "section": "132", "description": "Price paid/payable + Section 133 additions. 4 conditions must be met."},
            {"number": 2, "name_en": "Transaction Value of Identical Goods", "name_he": "ערך עסקה של טובין זהים",
             "section": "133א+133ג", "description": "Same country, same/proximate export time. Lowest value rule."},
            {"number": 3, "name_en": "Transaction Value of Similar Goods", "name_he": "ערך עסקה של טובין דומים",
             "section": "133ב+133ג", "description": "Similar characteristics/materials, same country. Lowest value rule."},
            {"number": 4, "name_en": "Deductive Value (Sale Price in Israel)", "name_he": "ערך ניכוי",
             "section": "133ד", "description": "Greatest aggregate quantity sold in Israel, minus deductions. 90-day rule."},
            {"number": 5, "name_en": "Computed Value", "name_he": "ערך מחושב",
             "section": "133ה", "description": "Cost build-up: materials + production + profit/expenses + CIF."},
            {"number": 6, "name_en": "Reversed Order (Methods 4↔5)", "name_he": "סדר הפוך",
             "section": "130(6)", "description": "Importer may REQUEST to apply Method 5 before Method 4 (with approval)."},
            {"number": 7, "name_en": "Fallback Method", "name_he": "שיטת שארית",
             "section": "133ו", "description": "Reasonable means per GATT principles. 7 prohibited bases (no minimums, no arbitrary)."},
        ],
        "critical_rule": "Methods MUST be applied IN ORDER. Cannot skip to Method 4 without proving 1-3 inapplicable.",
    },
    "131": {
        "ch": 8, "t": "טובין שחלפה שנה",
        "s": "Goods under customs >1 year: Method 1 excluded by default. Director may reinstate on request.",
    },
    "132": {
        "ch": 8, "t": "ערך עסקה",
        "s": "METHOD 1 DETAIL: Price paid/payable + §133 additions. 4 CONDITIONS: "
             "(1) no sale restrictions (except legal/geographic/immaterial); "
             "(2) no unquantifiable conditions; "
             "(3) no seller-attributed resale proceeds not in §133; "
             "(4) no special relationship influence (or importer can prove non-influence via 3 benchmarks). "
             "Interest excluded if separate, written, and at prevailing rate. Post-release discounts excluded.",
        "key": "4 mandatory conditions. Special relationship test: 3 benchmarks (identical/similar TV, deductive, computed). "
               "Interest: 3 exclusion conditions. Post-release discounts: always excluded.",
    },
    "133": {
        "ch": 8, "t": "התוספות למחיר העסקה",
        "s": "5 categories of MANDATORY additions to transaction price (CIF basis):",
        "additions": [
            "(1) Buyer's costs: (א) commissions/brokerage (EXCLUDING buying commissions), (ב) containers, (ג) packing",
            "(2) Assists: (א) materials/components, (ב) tools/dies/molds, (ג) consumed materials, (ד) engineering/design done OUTSIDE Israel",
            "(3) Royalties and license fees as condition of sale",
            "(4) Resale proceeds attributable to seller",
            "(5) CIF costs: (א) transport to port, (ב) loading/unloading/handling, (ג) insurance",
        ],
        "key": "CIF basis. Buying commissions EXCLUDED. Israeli engineering EXCLUDED from assists. "
               "No objective data = transaction disqualified.",
    },
    "133א": {
        "ch": 8, "t": "ערך עסקה — טובין זהים",
        "s": "METHOD 2: Identical goods TV. Same country, same/proximate export time. Same commercial level/quantity preferred; "
             "adjustments with proven evidence. Section 132 calculation applies.",
    },
    "133ב": {
        "ch": 8, "t": "ערך עסקה — טובין דומים",
        "s": "METHOD 3: Similar goods TV. Same conditions as Method 2 but for similar (not identical) goods.",
    },
    "133ג": {
        "ch": 8, "t": "כללים לטובין זהים/דומים",
        "s": "Supplementary rules for Methods 2-3: LOWEST value selection; transport cost differential adjustments.",
    },
    "133ד": {
        "ch": 8, "t": "מחיר מכירה בישראל",
        "s": "METHOD 4 (Deductive): Greatest aggregate quantity sold in Israel. Deductions: commissions, domestic transport, "
             "CIF costs, import taxes. 90-day rule for later sales. Further-processing option on request.",
        "key": "90-day window. Greatest aggregate quantity. 4 deductions. Assists-related sales excluded.",
    },
    "133ה": {
        "ch": 8, "t": "ערך מחושב",
        "s": "METHOD 5 (Computed): Materials + manufacturing cost + profit/expenses + CIF. Foreign producer not compellable; "
             "verification abroad with consent and foreign authority notice.",
    },
    "133ו": {
        "ch": 8, "t": "שיטת שארית",
        "s": "METHOD 7 (Fallback): Reasonable means per GATT 1994. PROHIBITED: domestic prices, higher-of-two, "
             "export-country prices, cost of production (except Method 5 for identical/similar), export to other countries, "
             "minimum values, arbitrary values. Director may apply earlier methods flexibly.",
        "key": "7 prohibited bases. No minimum customs values. No arbitrary values.",
    },
    "133ז": {"ch": 8, "t": "טובין שניזוקו", "s": "Damaged goods: valuation hierarchy applies with damage discount. No double recovery (§150 excluded)."},
    "133ח": {"ch": 8, "t": "מסירת פירוט", "s": "Director must give written notice of value + method used. Detailed calculation on request."},
    "133ט": {"ch": 8, "t": "תחולה מסחרית", "s": "WTO valuation (§§129-133ח) applies ONLY to commercial imports. Personal use: §134א."},
    "134": {"ch": 8, "t": "תקנות להערכה", "s": "Director may make regulations; compulsory disclosure of accounts/books/documents. Fine: 100 lira."},
    "134א": {"ch": 8, "t": "ערך לשימוש עצמי", "s": "Personal-use imports valued per Finance Minister regulations (Knesset approval required)."},
    "135": {"ch": 8, "t": "בוטל", "repealed": True, "s": "Formerly: classification at highest rate. Repealed 1965."},
    "136": {"ch": 8, "t": "חלק מן השלם", "s": "Parts of a whole: each part taxed at rate of complete item (ad valorem). Anti-avoidance."},
    "137": {"ch": 8, "t": "בוטל", "repealed": True, "s": "Formerly: composite materials classification. Repealed 1965."},
    "138": {"ch": 8, "t": "מדידה", "s": "Goods arranged for measurement at owner's expense. Bulk: full extent of stack/pile."},
    "139": {"ch": 8, "t": "ערך מכירה פומבית", "s": "Customs auction price = permissible value for ad valorem goods."},
    "140": {"ch": 8, "t": "טובין במצהר שלא הוצגו",
        "s": "Goods in manifest but not presented: vessel owner/master/agent pays duty at rate when manifest delivered.",
    },
    "141": {"ch": 8, "t": "טובין פטורים שהועברו",
        "s": "Duty-free goods transferred to non-exempt entity: ad valorem at transfer value; specific rate with deterioration adjustment. "
             "Pre-transfer notification + payment required. Diplomatic car reciprocal exemption.",
    },
    "142": {"ch": 8, "t": "דוגמאות", "s": "Small samples from supervised bulk: customs-free with conditions."},
    "143": {"ch": 8, "t": "שינוי בהסכם", "s": "Contract price adjusts for customs rate changes between contract and declaration. Contractual override permitted."},
    "144": {"ch": 8, "t": "מועד ייבוא",
        "s": "Time of import: sea = entry into port limits; land/air = border crossing.",
        "key": "Sea: entry into port limits. Land/air: border crossing. Used for applicable rates.",
    },
    "145": {"ch": 8, "t": "ניכוי המכס", "s": "State holds FIRST AND PREFERENTIAL LIEN on goods for customs/charges/fines regardless of ownership."},
    "146": {"ch": 8, "t": "בוטל", "repealed": True, "s": "Formerly: documents with רשמון. Repealed 2018."},
    "147": {"ch": 8, "t": "בוטל", "repealed": True, "s": "Formerly: invoice particulars. Repealed 2018."},
    "148": {"ch": 8, "t": "המרת מטבע",
        "s": "Foreign currency → Israeli currency per Finance Minister rules (Knesset approval).",
        "key": "Currency conversion rules set by Finance Minister.",
    },
    "149": {"ch": 8, "t": "ליטול טובין בערכם",
        "s": "Suspected undervaluation: Director may take customs in kind OR seize goods at declared value + 5%. Payment within 30 days.",
        "key": "Compulsory purchase at declared value + 5% premium. 30-day payment.",
    },
    "150": {"ch": 8, "t": "החזרת מכס",
        "s": "Refund for: (1) lost/destroyed/damaged before release; (2) non-conformity/defect within 6 months of release. "
             "Immediate claim + no-use condition.",
        "key": "6-month post-release defect window. Immediate claim required. No-use or discovery-use only.",
    },
    "151": {"ch": 8, "t": "בוטל", "repealed": True, "s": "Formerly: deficit collection. Repealed 1968."},
    "152": {"ch": 8, "t": "אין החזרה עקב שינוי",
        "s": "Classification practice changes are PROSPECTIVE only. No retroactive refunds.",
        "key": "Classification changes = no retroactive refund for past payments.",
    },
    "153": {"ch": 8, "t": "טובין שחזרו",
        "s": "Re-imported goods: exempt if no foreign processing. Repair/improvement abroad: duty on improvement value only. "
             "Rate difference payable if rates increased.",
        "key": "No processing abroad = exempt. Repair/improvement = duty on value of improvement only.",
    },
    "154": {"ch": 8, "t": "סכסוך בנוגע לתשלום",
        "s": "Payment under protest mechanism. 3-month limitation for lawsuit. Must write 'PAID UNDER PROTEST' on declaration before payment.",
        "key": "'שולם אגב מחאה' must be written + signed BEFORE payment. 3-month lawsuit deadline.",
    },
    "155": {"ch": 8, "t": "בוטל", "repealed": True, "s": "Formerly: overpayment refund within 2 years. Repealed 1968."},

    # ══════════════════════════════════════════════
    # CHAPTER 9: DRAWBACK & TEMPORARY ADMISSION (הישבון)
    # ══════════════════════════════════════════════

    "156": {"ch": 9, "t": "הישבון ללא ייצור", "s": "Full customs drawback for re-exported goods within 6 months (extendable to 3 years). No use in Israel."},
    "157": {"ch": 9, "t": "הישבון רכב תייר", "s": "Tourist car drawback: 100% within 1 year; graduated 90/60/40/20% for later re-export."},
    "158": {"ch": 9, "t": "תביעות הישבון", "s": "Drawback claims on prescribed form to Collector."},
    "159": {"ch": 9, "t": "הצהרת תובע", "s": "Claimant declares goods exported and entitlement. Signature = proof of payment."},
    "160": {"ch": 9, "t": "הישבון עם ייצור", "s": "Finance Minister may order drawback on imported materials used in manufacturing for export."},
    "160א": {"ch": 9, "t": "בוטל", "repealed": True, "s": "Formerly: investment incentive drawback. Repealed 1976."},
    "160ב": {"ch": 9, "t": "דין טובין מותרים",
        "s": "Director may defer duty payment for drawback goods. Interest at max legal rate if unpaid by deadline.",
    },
    "160ג": {"ch": 9, "t": "החלפת טובין", "s": "Drawback on imported goods substituted with equivalent Israeli goods for manufacturing."},
    "161": {"ch": 9, "t": "הגבלת תשלום", "s": "3-month deadline from loading for export; Director's consent required."},
    "162": {"ch": 9, "t": "כניסה זמנית",
        "s": "Temporary duty-free admission for: manufacturing for export, packaging, processing, repair, renovation, public display.",
    },
    "162א": {"ch": 9, "t": "סירוב התרה", "s": "Director may refuse clearance on other goods if deferred duty/interest unpaid."},
    "162ב": {"ch": 9, "t": "תקנות הישבון", "s": "Finance Minister regulation power for drawback; information/book production requirements."},
    "162ג": {"ch": 9, "t": "עונשים", "s": "Fine: 1,000 liras or 3× revenue lost, whichever higher, per offense."},

    # ══════════════════════════════════════════════
    # CHAPTER 10: COASTAL TRADE (סחר החוף)
    # ══════════════════════════════════════════════

    "163": {"ch": 10, "t": "אניות חוף", "s": "Vessel trading between Israeli ports without foreign ports = coasting vessel."},
    "164": {"ch": 10, "t": "לא תוטען בים", "s": "No at-sea loading/unloading without permission; no deviation unless force majeure."},
    "165": {"ch": 10, "t": "תסקיר בעל אניה", "s": "Owner may substitute for master in reporting; same obligations/penalties."},
    "166": {"ch": 10, "t": "פרטי מטען", "s": "Master/owner must provide Collector with cargo details."},
    "167": {"ch": 10, "t": "הסדר סחר החוף", "s": "Government may regulate coastal trade by order; record-keeping required."},

    # ══════════════════════════════════════════════
    # CHAPTER 11: AGENTS (סוכנים)
    # ══════════════════════════════════════════════

    "168": {
        "ch": 11, "t": "סוכן מכס",
        "s": "Owner may act through customs agent. Agent must submit written authorization (כתב הרשאה) signed by owner, "
             "authenticated as prescribed. Electronic submission via Ch.14A. Traveler may authorize any person for luggage.",
        "key": "Written authorization with authenticated signature. Electronic submission permitted. "
               "Governed by Customs Agents Law (חוק סוכני המכס, תשכ\"ה-1964).",
    },
    "169": {
        "ch": 11, "t": "יש להראות הרשאה",
        "s": "Customs officer may demand agent produce written authorization. Failure = agency not recognized.",
    },
    "170": {"ch": 11, "t": "בוטל", "repealed": True, "s": "Formerly: agent personal liability. Repealed 1995."},
    "171": {"ch": 11, "t": "בוטל", "repealed": True, "s": "Formerly: principal liability for agent acts. Repealed 1995."},

    # ══════════════════════════════════════════════
    # CHAPTER 12: POWERS OF CUSTOMS OFFICERS (סמכויות)
    # ══════════════════════════════════════════════

    "172": {"ch": 12, "t": "רדיפת אניה", "s": "Customs vessel may pursue and fire (after warning) at vessel refusing to stop in territorial waters."},
    "173": {"ch": 12, "t": "עליה לאניה", "s": "May board, search, bring to port; interrogate all aboard; demand documents."},
    "174": {"ch": 12, "t": "בדיקת טובין", "s": "Open packages, examine, weigh, mark, seal; all costs on owner."},
    "175": {"ch": 12, "t": "חיפוש באניה", "s": "General boarding and search powers; securing goods."},
    "176": {"ch": 12, "t": "עליה ושהייה", "s": "Right to remain on vessel; free accommodation and food for stationed officer."},
    "177": {"ch": 12, "t": "חיפוש", "s": "Comprehensive search of all compartments, packages, drawers."},
    "178": {"ch": 12, "t": "חסימת טובין", "s": "Closing hatches, locking, sealing, marking, removal to warehouse."},
    "179": {"ch": 12, "t": "שבירת חותמות", "s": "Forbidden to break customs seals/locks on supervised goods."},
    "180": {"ch": 12, "t": "חותמות טרנזיט", "s": "Seals on provisions for inter-port transit; master liable for broken seals."},
    "181": {"ch": 12, "t": "סיור", "s": "Free patrol/traverse rights over all terrain (shore, roads, rail, lands)."},
    "182": {"ch": 12, "t": "עגינת כלי שיט", "s": "Customs vessels may moor anywhere as needed."},
    "183": {"ch": 12, "t": "חקירת נוסע", "s": "May question any person about dutiable/prohibited goods in possession."},
    "184": {"ch": 12, "t": "עיכוב וחיפוש גוף",
        "s": "Detention and body search with reasonable suspicion (same-sex). Drug Unit: external bodily searches at borders with consent.",
    },
    "185": {"ch": 12, "t": "חיפוש רכב", "s": "Stop and search vehicle on reasonable suspicion; driver must comply."},
    "186": {"ch": 12, "t": "סמכויות שוטר", "s": "Full police powers for customs officers; body search only per §184."},
    "187": {"ch": 12, "t": "חיפוש חצרים", "s": "Warrantless search of non-residential premises; warrant for dwellings; force permitted."},
    "188": {"ch": 12, "t": "תפיסת אניה/טובין", "s": "Seizure of forfeited/believed-forfeited property; custody to customs warehouse."},
    "189": {"ch": 12, "t": "דרישת עזרה", "s": "Right to demand public assistance during seizure."},
    "190": {"ch": 12, "t": "הודעת תפיסה", "s": "Written notice required; 1-month claim period (7 days for specified goods). Perishables: immediate sale/destruction."},
    "191": {"ch": 12, "t": "החזרת תפוס", "s": "Seized items returned upon surety bond."},
    "192": {"ch": 12, "t": "הנוהל לאחר תפיסה", "s": "Claimant: 2-month suit deadline. Collector: 3-month action deadline. Otherwise returned."},
    "193": {"ch": 12, "t": "העשיה בחילוט", "s": "Confiscated items: sold, destroyed, or dealt with per Director's order."},
    "194": {"ch": 12, "t": "מסירת טובין שנתפסו", "s": "Non-customs-officer seizure: immediate transfer to nearest customs house."},
    "195": {"ch": 12, "t": "מאסר חשודי הברחה", "s": "Warrantless arrest for smuggling offenses."},
    "196": {"ch": 12, "t": "הגשת מסמכים בתפיסה", "s": "Document production on demand; 5-year lookback for all books/records."},
    "197": {"ch": 12, "t": "עיכוב מסמכים", "s": "Collector may retain documents; certified copies admissible in court."},
    "198": {"ch": 12, "t": "דרישת הוכחות", "s": "Collector may demand proof of ownership and declaration accuracy; refuse delivery until provided."},
    "199": {"ch": 12, "t": "דוגמאות", "s": "Sampling rights; no compensation."},
    "200": {"ch": 12, "t": "רשיונות למסחר", "s": "Three types of trading licenses for vessel-related commerce."},
    "200א": {"ch": 12, "t": "עיכוב טובין מפרים",
        "s": "IP enforcement: 3 business-day detention (extendable); bank guarantee required; suit within 10 business days. "
             "Copyright, trademarks, registered designs.",
    },
    "200ב": {"ch": 12, "t": "שחרור ערבויות", "s": "Guarantee return after 3 months in various scenarios or per court order."},
    "200ג": {"ch": 12, "t": "טובין מפרים = אסורים", "s": "Infringing goods treated as prohibited imports/exports."},
    "200ד": {"ch": 12, "t": "ייבוא אישי", "s": "Personal use exemption from IP enforcement provisions."},
    "200ה": {"ch": 12, "t": "שמירת דינים", "s": "IP powers supplementary to other legal authorities."},
    "200ו": {"ch": 12, "t": "עיכוב לבקרת תקינה", "s": "Detention for Standards Superintendent sample inspection. Added 2024."},
    "200ז": {"ch": 12, "t": "יבואן מפר אמון", "s": "Detention/conditional release for trust-violating importers. Added 2024."},
    "201": {"ch": 12, "t": "הגנה לפקיד", "s": "Officer immunity for seizures with reasonable cause."},
    "202": {"ch": 12, "t": "קנס התנהגות", "s": "Director may fine officer up to 3 days' wages for negligence/misconduct."},

    # ══════════════════════════════════════════════
    # CHAPTER 13: FORFEITURES AND PENALTIES (חילוטין ועונשין)
    # ══════════════════════════════════════════════

    "203": {"ch": 13, "t": "חילוט כלי שיט",
        "s": "Vessels ≤250 tons: forfeited for smuggling/6 grounds. >250 tons: fine up to 10× Penal Law or 3× duties. "
             "Non-vessel vehicles also forfeited.",
    },
    "203א": {"ch": 13, "t": "דרישת קנס",
        "s": "30-day payment; interest + late charges on arrears. 30-day appeal to Magistrate's Court. Further appeal by leave to District Court.",
    },
    "204": {"ch": 13, "t": "חילוט טובין",
        "s": "17 categories of forfeitable goods: smuggled, false declarations, concealment, unauthorized movement, "
             "prohibited goods, deceptive packaging, undeclared dutiable goods.",
    },
    "205": {"ch": 13, "t": "שומת רכוש", "s": "Sworn official valuation; final for confiscation proceedings."},
    "206": {"ch": 13, "t": "אריזות וטובין", "s": "Forfeiture includes packaging+contents together; vehicle forfeiture includes owner's goods."},
    "207": {"ch": 13, "t": "התכנסות להברחה",
        "s": "Conspiracy to smuggle, prevent seizure, or rescue seized goods: 3 years imprisonment.",
    },
    "208": {"ch": 13, "t": "קנוניה, שוחד, חילוץ",
        "s": "Customs officer collusion, bribery, rescuing seized goods, destroying evidence: 3 years or 500 liras.",
    },
    "209": {"ch": 13, "t": "ירי אל כלי שיט",
        "s": "Shooting at customs vessel/officer or wounding officer: 15 years imprisonment.",
    },
    "210": {"ch": 13, "t": "סילוק טובין",
        "s": "Unauthorized removal from warehouse, destroying bonded goods, assault on officers: 2 years or 500 liras.",
    },
    "211": {
        "ch": 13, "t": "הברחה",
        "s": "SMUGGLING: 3 years + 2× Penal Law fine + 3× import duties. AGGRAVATED: 5 years + 4× fine + 3× duties. "
             "Vessel/vehicle owners equally liable. Wartime enhancement.",
        "key": "3 years / 2× Penal Law fine + 3× import duties. Aggravated: 5 years / 4× fine + 3× duties.",
    },
    "212": {
        "ch": 13, "t": "עבירות מכס אחרות",
        "s": "13 offenses at 2 years/500 liras: duty evasion, false invoices, false declarations, forging documents, "
             "misleading officers, refusing to answer, unauthorized handling, transferring exempt goods.",
        "key": "13 specific offenses. Failure to report tax opinions/shelf planning: Penal Law fines.",
    },
    "213": {"ch": 13, "t": "גיבוי קנס", "s": "Fines enforceable as criminal fines; attachment/sale of property."},
    "214": {"ch": 13, "t": "עונש כללי", "s": "Default penalty for unspecified violations: 6 months or 100 liras."},
    "215": {"ch": 13, "t": "טובין אסורים מיוחדים", "s": "6 offenses for government-designated prohibited goods; wartime enhancement."},
    "216": {"ch": 13, "t": "פרסום אסור", "s": "Duty to surrender unsolicited banned publications to police."},
    "217": {
        "ch": 13, "t": "אחריות ביחד ולחוד",
        "s": "Joint and several liability: each person liable for the FULL penalty.",
    },
    "218": {
        "ch": 13, "t": "מסייעים ומעודדים",
        "s": "Aiders, abettors, counselors, procurers treated as PRINCIPALS. Same punishment.",
    },
    "219": {"ch": 13, "t": "נסיון", "s": "Attempt = completed offense for punishment purposes."},
    "220": {
        "ch": 13, "t": "עונש פי שלושה",
        "s": "Maximum fine: 3× goods value + 3× customs duty when prescribed penalty is lower.",
        "key": "3× value + 3× duty = maximum fine.",
    },
    "221": {"ch": 13, "t": "עונש בנוסף על חילוט", "s": "All penalties are IN ADDITION TO forfeiture, not instead of."},
    "222": {"ch": 13, "t": "ערך לעונש", "s": "Goods value = best goods of type, duty-paid, at Tel Aviv-Jaffa prices, at offense time."},
    "223": {"ch": 13, "t": "חיוב קודם",
        "s": "Prior customs conviction within 5 years: court may impose 2 years imprisonment (in addition to/instead of fine).",
    },

    # ══════════════════════════════════════════════
    # CHAPTER 13א: ADMINISTRATIVE ENFORCEMENT (אמצעי אכיפה מינהליים)
    # ══════════════════════════════════════════════

    "223א": {"ch": "13א", "t": "הגדרות",
        "s": "Defines importer, exporter, non-profit, financial institution, business, personal use for admin enforcement.",
    },
    "223ב": {
        "ch": "13א", "t": "עיצום כספי",
        "s": "Financial sanction schedule: false manifest ₪2,500; importer/exporter incorrect declaration 10% or ₪5,000 (higher); "
             "agent errors 1% (₪500-₪5,000); minor agent errors ₪150; POA authentication failure ₪400; "
             "unauthorized authorization ₪5,000; late manifest/warehouse violations ₪25,000.",
        "key": "₪150 minor agent errors; ₪400 POA; ₪2,500 manifest; ₪5,000 importer/agent; ₪25,000 serious violations.",
    },
    "223ג": {"ch": "13א", "t": "הודעת כוונה", "s": "Written notice of intent before imposing sanction; specifies violation, amount, rights."},
    "223ד": {"ch": "13א", "t": "זכות טיעון", "s": "30-day written argument period (extendable to 60 days total)."},
    "223ה": {"ch": "13א", "t": "החלטה ודרישת תשלום",
        "s": "Director decides after arguments; written reasoned decision. No arguments filed = intent notice becomes demand.",
    },
    "223ו": {"ch": "13א", "t": "הפרה נמשכת/חוזרת",
        "s": "Continuing: +1/50 of amount per day. Repeat within 2 years: DOUBLED.",
    },
    "223ז": {"ch": "13א", "t": "סכומים מופחתים", "s": "No reduction below minimums except per ministerial regulations."},
    "223ח": {"ch": "13א", "t": "עדכון סכומים", "s": "Annual CPI adjustment on January 1; rounded to ₪10; published in Reshumot."},
    "223ט": {"ch": "13א", "t": "מועד תשלום", "s": "30-day payment deadline after receiving demand."},
    "223י": {"ch": "13א", "t": "ריבית ופיגורים", "s": "Unpaid sanctions accrue shekel interest + late-payment charges."},
    "223יא": {"ch": "13א", "t": "גבייה", "s": "Collected for state treasury; Tax Collection Ordinance applies."},
    "223יב": {"ch": "13א", "t": "התראה מינהלית",
        "s": "Alternative to sanction: warning per Attorney General-approved guidelines. Warns of future sanctions.",
    },
    "223יג": {"ch": "13א", "t": "ביטול התראה", "s": "30-day cancellation request on 2 grounds; written reasoned decision."},
    "223יד": {"ch": "13א", "t": "הפרה אחרי התראה", "s": "Continuing after warning: payment demand. Repeat within 2 years: doubled."},
    "223טו": {"ch": "13א", "t": "כפל עיצום", "s": "Single act violating multiple laws: only ONE sanction imposed. No double jeopardy."},
    "223טז": {"ch": "13א", "t": "ערעור",
        "s": "Appeal to Magistrate's Court within 30 days. No automatic stay. Successful appeal: refund with interest.",
    },
    "223יז": {"ch": "13א", "t": "פרסום",
        "s": "Published on Tax Authority website: 4 years for corporations, 2 years for individuals. No personal identification.",
    },
    "223יח": {"ch": "13א", "t": "שמירת אחריות פלילית",
        "s": "Admin penalties do NOT prevent criminal prosecution. No indictment after admin enforcement absent new facts. "
             "Sanction refunded if later indicted on new facts.",
    },

    # ══════════════════════════════════════════════
    # CHAPTER 14: CUSTOMS PROSECUTIONS (אישומי מכס)
    # ══════════════════════════════════════════════

    "224": {"ch": 14, "t": "הגדרה", "s": "Customs prosecutions: offenses under Ordinance + recovery of duty/penalties/confiscation."},
    "225": {"ch": 14, "t": "הגשת אישום", "s": "Filed in name of AG or Director; criminal appeal rules; deposit requirement."},
    "226": {"ch": 14, "t": "בוטל", "repealed": True, "s": "Formerly: 5-year limitation. Repealed 2018."},
    "227": {"ch": 14, "t": "חסינות עדים", "s": "Informant privilege; confidential report privilege for customs officers."},
    "228": {"ch": 14, "t": "הוכחת תקנות", "s": "Official gazette or certified copy = prima facie evidence of regulation validity."},
    "229": {"ch": 14, "t": "חובת הראיה",
        "s": "BURDEN OF PROOF on defendant/claimant that duty was paid or goods lawfully imported/exported.",
        "key": "Burden of proof on defendant for lawful dealing.",
    },
    "230": {"ch": 14, "t": "הרשעה = החרמה", "s": "Conviction = automatic confiscation where offense triggers forfeiture."},

    # ══════════════════════════════════════════════
    # CHAPTER 14א: ELECTRONIC REPORTING (דיווח אלקטרוני)
    # ══════════════════════════════════════════════

    "230א": {"ch": "14א", "t": "הגדרות", "s": "Electronic reporting = submission via certified electronic signature, storable and outputtable."},
    "230ב": {"ch": "14א", "t": "חובת דיווח אלקטרוני",
        "s": "Mandatory electronic submission: import/export declarations, manifests, authorizations. Director may add more.",
    },
    "230ג": {"ch": "14א", "t": "שמירת מסמך", "s": "Retention obligation for electronically submitted documents per Director's rules."},
    "230ד": {"ch": "14א", "t": "המצאה אלקטרונית", "s": "Customs authority may send documents electronically per Director's rules."},
    "230ה": {"ch": "14א", "t": "חזקת מסירה",
        "s": "Electronic message presumed delivered after 3 business days. Login notification + software log required. Rebuttable.",
    },
    "230ו": {"ch": "14א", "t": "כללים", "s": "Director sets rules: connection conditions, procedures, hardware/software, form structure."},
    "230ז": {"ch": "14א", "t": "מרשם תוכנות", "s": "Software registry on Tax Authority website; mandatory registration."},
    "230ח": {"ch": "14א", "t": "תקלת מערכת", "s": "System outage: Director sets non-electronic fallback procedures; published on website."},

    # ══════════════════════════════════════════════
    # CHAPTER 15: MISCELLANEOUS PROVISIONS (הוראות שונות)
    # ══════════════════════════════════════════════

    "231": {"ch": 15, "t": "כפרה על עבירות",
        "s": "Director may compound offenses by accepting payment up to max fine. Forfeiture still possible. Precludes further proceedings.",
    },
    "231א": {"ch": 15, "t": "תחולת חוק מע\"מ", "s": "VAT Law sections 1a(a), 100, 102a, 103, 106, 106b, 108, 135, 141 apply to customs."},
    "231א1": {"ch": 15, "t": "דרכי גביה", "s": "Tax Collection Ordinance + civil suit for recovery; VAT Law ss.102(b), 102b applicable."},
    "231א2": {"ch": 15, "t": "חובת סודיות",
        "s": "Strict confidentiality. 5 exceptions (Minister permission, enforcement, standards, court, NII). "
             "Unauthorized disclosure: 1 year or ₪19,300.",
        "key": "1 year imprisonment or ₪19,300 fine for unauthorized disclosure.",
    },
    "231ב": {"ch": 15, "t": "בוטל", "repealed": True, "s": "Formerly: appeal procedures. Repealed 1985."},
    "231ג": {"ch": 15, "t": "קנס מינהלי דואר",
        "s": "Postal goods with false declarations: double duty up to ₪1,000 (alternative to forfeiture). Requires consent.",
    },
    "231ד": {"ch": 15, "t": "דיווח חוות דעת",
        "s": "Tax opinion reporting within 60 days. Shelf planning = same opinion to 3+ persons. "
             "Fee-contingent opinions reportable. Exemptions for small businesses (<₪3M turnover).",
    },
    "231ה": {"ch": 15, "t": "עמדה חייבת בדיווח",
        "s": "Reportable position: contradicts published Tax Authority position AND benefit >₪2M/year or >₪5M/4 years. "
             "Max 25 positions/year published. 60-day reporting.",
    },
    "232": {"ch": 15, "t": "תקנות",
        "s": "Finance Minister broad regulation power: transit, fees, storage, foreign agreements, temporary admission, rewards.",
    },
    "232א": {"ch": 15, "t": "תיקון תוספת", "s": "Schedule amendment by order (Justice Minister consent); max ₪50,000 per violation."},
    "233": {"ch": 15, "t": "אניות שליחות", "s": "Government vessel manifest obligation for non-provision cargo."},
    "234": {"ch": 15, "t": "חיפוש אניות שליחות", "s": "Government vessels: boarding, search, removal to customs warehouse."},
    "235": {"ch": 15, "t": "פרס עצירה", "s": "Reward up to 25 liras per arrested/convicted smuggler."},
    "236": {"ch": 15, "t": "בוטל", "repealed": True, "s": "Formerly: disposal of seized property. Repealed 2003."},
    "237": {"ch": 15, "t": "החזרת תפוס", "s": "Government may return seized items, waive proceedings, or mitigate penalties."},
    "238": {"ch": 15, "t": "מחסנים קיימים", "s": "Transitional: agreement-based warehouses deemed licensed."},
    "238א": {"ch": 15, "t": "הקלות לגורמים מאושרים",
        "s": "Authorized Economic Operator (AEO) facilitations in import procedures. Director's discretion. Added 2018.",
    },
    "239": {"ch": 15, "t": "טפסים", "s": "Director prescribes forms for bonds, certificates, documents."},
    "239א": {"ch": 15, "t": "חובת הראיה", "s": "Burden on claimant for payment/filing/clearance in non-§229 proceedings."},
    "239ב": {"ch": 15, "t": "פטור מחתימה", "s": "No manual signature required on customs-issued documents bearing issuer name."},
    "240": {"ch": 15, "t": "דרישות טפסים", "s": "Form instructions binding; extra copies may be required; old forms transitionally usable."},
    "241": {"ch": 15, "t": "מכירת טובין", "s": "Customs authority sale per prescribed conditions."},
}


# Verify article count
def _count_articles():
    return len([k for k in ORDINANCE_ARTICLES if not k.startswith("_")])
