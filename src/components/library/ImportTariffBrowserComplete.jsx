import React, { useState } from 'react';
import { ChevronDown, ChevronLeft, Search, FileText, AlertTriangle, Info, ExternalLink, BookOpen, Scale, Percent, Package, X, Globe, ScrollText, Landmark, Flag } from 'lucide-react';

/**
 * תעריף מכס יבוא - Import Customs Tariff Browser
 * COMPLETE STRUCTURE based on צו תעריף המכס והפטורים ומס קניה על טובין
 * 
 * Structure:
 * 1. צו מסגרת (Framework Order)
 * 2. תוספת ראשונה (First Supplement - Chapters 1-99)
 * 3. תוספות ב׳-י״ז (Supplements 2-17 - Trade Agreements)
 */

// ============================================
// צו מסגרת - FRAMEWORK ORDER
// ============================================
const FRAMEWORK_ORDER = {
  id: "framework",
  titleHe: "צו מסגרת",
  titleEn: "Framework Order",
  icon: "scroll",
  description: "הגדרות, כללי פרשנות וכללים כלליים",
  sections: [
    { id: "definitions", titleHe: "הגדרות", titleEn: "Definitions", content: "הגדרות מונחים בצו תעריף המכס" },
    { id: "interpretation", titleHe: "כללי פרשנות", titleEn: "Interpretation Rules", content: "6 כללי הפרשנות הבינלאומיים + כללים ישראליים" },
    { id: "general-rules", titleHe: "הוראות כלליות", titleEn: "General Provisions", content: "הוראות כלליות לסיווג טובין" },
    { id: "trade-agreements", titleHe: "הסכמי סחר", titleEn: "Trade Agreements", content: "הוראות להסכמי סחר בינלאומיים" },
    { id: "discount-codes", titleHe: "קודי הנחה", titleEn: "Discount Codes", content: "קודי הנחה וסימולים" },
  ]
};

// ============================================
// תוספת ראשונה - FIRST SUPPLEMENT (Main Tariff)
// Chapters 1-99 organized in 21 Sections
// ============================================
const FIRST_SUPPLEMENT = {
  id: "supplement-1",
  titleHe: "תוספת ראשונה",
  titleEn: "First Supplement",
  subtitle: "תעריף המכס - פרקים 01-99",
  icon: "book",
  sections: [
    {
      id: 1,
      titleHe: "בעלי חיים; מוצרים מן החי",
      titleEn: "Live Animals; Animal Products",
      chapters: [
        { num: "01", titleHe: "בעלי חיים חיים", titleEn: "Live Animals" },
        { num: "02", titleHe: "בשר ושאר-חלקי בשר הראויים לאכילה", titleEn: "Meat and Edible Meat Offal" },
        { num: "03", titleHe: "דגים וסרטנים, רכיכות ובעלי חיים אחרים מימיים", titleEn: "Fish and Crustaceans" },
        { num: "04", titleHe: "מוצרי חלב; ביצי עופות; דבש טבעי; מוצרים אחרים ממקור חי", titleEn: "Dairy Products; Eggs; Honey" },
        { num: "05", titleHe: "מוצרים אחרים מן החי, שלא פורשו ולא נכללו במקום אחר", titleEn: "Products of Animal Origin, NES" },
      ]
    },
    {
      id: 2,
      titleHe: "מוצרים מן הצומח",
      titleEn: "Vegetable Products",
      chapters: [
        { num: "06", titleHe: "עצים חיים וצמחים אחרים; פקעות, שורשים וכדומה; פרחים קטופים ועלוות נוי", titleEn: "Live Trees and Other Plants" },
        { num: "07", titleHe: "ירקות ושורשים ופקעות מסוימים, הראויים למאכל", titleEn: "Edible Vegetables" },
        { num: "08", titleHe: "פירות ואגוזים ראויים למאכל; קליפות פרי הדר או אבטיחיים", titleEn: "Edible Fruit and Nuts" },
        { num: "09", titleHe: "קפה, תה, מטה ותבלינים", titleEn: "Coffee, Tea, Maté and Spices" },
        { num: "10", titleHe: "דגנים", titleEn: "Cereals" },
        { num: "11", titleHe: "מוצרי תעשיית הטחינה; לתת; עמילנים; אינולין; גלוטן חיטה", titleEn: "Milling Industry Products" },
        { num: "12", titleHe: "זרעי שמן ופירות שמניים; דגנים, זרעים ופירות שונים; צמחי תעשיה ורפואה; קש ומספוא", titleEn: "Oil Seeds and Oleaginous Fruits" },
        { num: "13", titleHe: "לכה; דבקים, שרפים וחילופי צמחיים אחרים ותמציות מהם", titleEn: "Lac; Gums, Resins" },
        { num: "14", titleHe: "חמרים צמחיים לקליעה; מוצרים אחרים מן הצומח, שלא פורשו ולא נכללו במקום אחר", titleEn: "Vegetable Plaiting Materials" },
      ]
    },
    {
      id: 3,
      titleHe: "שומנים ושמנים ממקור חי או צמחי ותוצרי פירוקם; שומנים מעובדים למאכל; שעוות ממקור חי או צמחי",
      titleEn: "Animal or Vegetable Fats and Oils",
      chapters: [
        { num: "15", titleHe: "שומנים ושמנים ממקור חי או צמחי ותוצרי פירוקם; שומנים מעובדים למאכל; שעוות ממקור חי או צמחי", titleEn: "Animal or Vegetable Fats and Oils" },
      ]
    },
    {
      id: 4,
      titleHe: "מוצרי תעשיות המזון; משקאות, אלכוהול וחומץ; טבק ותחליפי טבק מעובדים",
      titleEn: "Prepared Foodstuffs; Beverages, Spirits; Tobacco",
      chapters: [
        { num: "16", titleHe: "תכשירים מבשר, מדגים או מסרטנים, מרכיכות או מבעלי חיים מימיים אחרים", titleEn: "Preparations of Meat, Fish" },
        { num: "17", titleHe: "סוכר וממתקי סוכר", titleEn: "Sugars and Sugar Confectionery" },
        { num: "18", titleHe: "קקאו ותכשיריו", titleEn: "Cocoa and Cocoa Preparations" },
        { num: "19", titleHe: "תכשירים מדגנים, מקמח, מעמילן או מחלב; מוצרי מאפה", titleEn: "Preparations of Cereals, Flour, Starch or Milk" },
        { num: "20", titleHe: "תכשירים מירקות, מפירות, מאגוזים או מחלקים אחרים של צמחים", titleEn: "Preparations of Vegetables, Fruit, Nuts" },
        { num: "21", titleHe: "תכשירי מזון שונים", titleEn: "Miscellaneous Edible Preparations" },
        { num: "22", titleHe: "משקאות, אלכוהול וחומץ", titleEn: "Beverages, Spirits and Vinegar" },
        { num: "23", titleHe: "שאריות ופסולת מתעשיות המזון; מספוא מוכן לבעלי חיים", titleEn: "Residues from Food Industries; Animal Feed" },
        { num: "24", titleHe: "טבק ותחליפי טבק מעובדים", titleEn: "Tobacco and Manufactured Tobacco Substitutes" },
      ]
    },
    {
      id: 5,
      titleHe: "מוצרים מינרליים",
      titleEn: "Mineral Products",
      chapters: [
        { num: "25", titleHe: "מלח; גפרית; אדמות ואבנים; חומרי טיח, סיד ומלט", titleEn: "Salt; Sulphur; Earths and Stone; Lime and Cement" },
        { num: "26", titleHe: "עפרות, סיגים ואפר", titleEn: "Ores, Slag and Ash" },
        { num: "27", titleHe: "דלק מינרלי, שמני מינרלים ומוצרי זיקוקם; חמרים ביטומניים; שעוות מינרליות", titleEn: "Mineral Fuels, Mineral Oils; Bituminous Substances" },
      ]
    },
    {
      id: 6,
      titleHe: "מוצרים כימיים או מוצרים של תעשיות נלוות",
      titleEn: "Products of the Chemical or Allied Industries",
      chapters: [
        { num: "28", titleHe: "כימיקלים אנאורגניים; תרכובות אנאורגניות או אורגניות של מתכות יקרות, של מתכות עפרות נדירות, של יסודות רדיואקטיביים או של איזוטופים", titleEn: "Inorganic Chemicals" },
        { num: "29", titleHe: "כימיקלים אורגניים", titleEn: "Organic Chemicals" },
        { num: "30", titleHe: "מוצרים פרמצבטיים", titleEn: "Pharmaceutical Products" },
        { num: "31", titleHe: "דשנים", titleEn: "Fertilizers" },
        { num: "32", titleHe: "תמציות לעיבוד עורות או לצביעה; טאנינים ונגזרותיהם; צבענים, פיגמנטים וחומרי צביעה אחרים; צבעים ולכות; מרק וגיר; דיות", titleEn: "Tanning or Dyeing Extracts; Paints and Varnishes" },
        { num: "33", titleHe: "שמני אתרים ורזינואידים; בשמים, קוסמטיקה ומוצרי טיפוח", titleEn: "Essential Oils; Perfumery, Cosmetics" },
        { num: "34", titleHe: "סבון, חומרים פעילי-שטח אורגניים, תכשירי רחצה, תכשירי סיכה, שעוות מלאכותיות, שעוות מוכנות, תכשירים לצחצוח או לשיוף, נרות ומוצרים דומים, הדבקות לדיגום, 'שעוות לטיפול בשיניים' ותכשירים לטיפול בשיניים על בסיס טיח", titleEn: "Soap; Lubricating Preparations; Waxes; Candles" },
        { num: "35", titleHe: "חומרים חלבוניים; עמילנים משוכללים; דבקים; אנזימים", titleEn: "Albuminoidal Substances; Modified Starches; Glues" },
        { num: "36", titleHe: "חומרי נפץ; מוצרים פירוטכניים; גפרורים; סגסוגות פירופוריות; חומרים דליקים מסוימים", titleEn: "Explosives; Pyrotechnic Products; Matches" },
        { num: "37", titleHe: "מוצרים פוטוגרפיים או קינמטוגרפיים", titleEn: "Photographic or Cinematographic Goods" },
        { num: "38", titleHe: "מוצרים כימיים שונים", titleEn: "Miscellaneous Chemical Products" },
      ]
    },
    {
      id: 7,
      titleHe: "פלסטיק ומוצריו; גומי ומוצריו",
      titleEn: "Plastics and Articles Thereof; Rubber and Articles Thereof",
      chapters: [
        { num: "39", titleHe: "פלסטיק ומוצריו", titleEn: "Plastics and Articles Thereof" },
        { num: "40", titleHe: "גומי ומוצריו", titleEn: "Rubber and Articles Thereof" },
      ]
    },
    {
      id: 8,
      titleHe: "עורות גולמיים, עור, פרוות וחפצים מהם; אוכפים ורתמות; מוצרי נסיעה, ילקוטים ומכלי דומים; חפצים ממעי בעלי חיים (שאינם פיברואין מתולעת משי)",
      titleEn: "Raw Hides and Skins, Leather, Furskins and Articles Thereof",
      chapters: [
        { num: "41", titleHe: "עורות גולמיים (למעט פרוות) ועור", titleEn: "Raw Hides and Skins, Leather" },
        { num: "42", titleHe: "חפצי עור; אוכפים ורתמות; מוצרי נסיעה, ילקוטים וכיוצא בהם; חפצים ממעי בעלי חיים (שאינם פיברואין מתולעת משי)", titleEn: "Articles of Leather; Saddlery; Travel Goods" },
        { num: "43", titleHe: "פרוות ופרוות מלאכותיות; חפצים מהם", titleEn: "Furskins and Artificial Fur; Articles Thereof" },
      ]
    },
    {
      id: 9,
      titleHe: "עץ ומוצרי עץ; פחם עץ; שעם ומוצריו; מוצרי קש, אספרטו או חמרי קליעה אחרים; מוצרי סלסלאות ומוצרי נצרים",
      titleEn: "Wood and Articles of Wood; Cork and Articles of Cork; Basketware",
      chapters: [
        { num: "44", titleHe: "עץ ומוצרי עץ; פחם עץ", titleEn: "Wood and Articles of Wood; Wood Charcoal" },
        { num: "45", titleHe: "שעם ומוצריו", titleEn: "Cork and Articles of Cork" },
        { num: "46", titleHe: "מוצרי קש, אספרטו או חמרי קליעה אחרים; מוצרי סלסלאות ומוצרי נצרים", titleEn: "Manufactures of Straw; Basketware and Wickerwork" },
      ]
    },
    {
      id: 10,
      titleHe: "עיסת עץ או חומר סיבי תאיתי אחר; נייר או קרטון לעיבוד חוזר (פסולת ופגם); נייר וקרטון ומוצריהם",
      titleEn: "Pulp of Wood; Paper and Paperboard and Articles Thereof",
      chapters: [
        { num: "47", titleHe: "עיסת עץ או עיסה מחומר סיבי תאיתי אחר; נייר או קרטון לעיבוד חוזר (פסולת ופגם)", titleEn: "Pulp of Wood; Recovered Paper or Paperboard" },
        { num: "48", titleHe: "נייר וקרטון; מוצרים מעיסת נייר, מנייר או מקרטון", titleEn: "Paper and Paperboard; Articles of Paper Pulp" },
        { num: "49", titleHe: "ספרים מודפסים, עיתונים, תמונות ומוצרי דפוס אחרים; כתבי יד, טפסים מוקלדים ותכניות", titleEn: "Printed Books, Newspapers, Pictures; Manuscripts" },
      ]
    },
    {
      id: 11,
      titleHe: "חומרים טקסטיליים ומוצרי טקסטיל",
      titleEn: "Textiles and Textile Articles",
      chapters: [
        { num: "50", titleHe: "משי", titleEn: "Silk" },
        { num: "51", titleHe: "צמר, שיער חיות עדין או גס; חוטי שיער סוס ובדי ארוג מהם", titleEn: "Wool, Fine or Coarse Animal Hair; Horsehair Yarn" },
        { num: "52", titleHe: "כותנה", titleEn: "Cotton" },
        { num: "53", titleHe: "סיבים טקסטיליים אחרים ממקור צמחי; חוטי נייר ובדי ארוג מחוטי נייר", titleEn: "Other Vegetable Textile Fibers; Paper Yarn" },
        { num: "54", titleHe: "תילים מעושים (פילמנטים מעושים); רצועות וכדומה מחומר טקסטילי סינתטי או מלאכותי", titleEn: "Man-Made Filaments; Strip of Man-Made Textile" },
        { num: "55", titleHe: "סיבים מעושים מקוטעים", titleEn: "Man-Made Staple Fibers" },
        { num: "56", titleHe: "צמר גפן, לבד וארוגים בלתי סרוגים; חוטים מיוחדים; חבלים, פתילים, שזירים וכבלים ומוצריהם", titleEn: "Wadding, Felt; Special Yarns; Twine, Cordage, Ropes" },
        { num: "57", titleHe: "שטיחים ורפידות רצפה טקסטיליות אחרות", titleEn: "Carpets and Other Textile Floor Coverings" },
        { num: "58", titleHe: "אריגים מיוחדים; אריגי-ציצית טופטד; תחרה; קלעון; קישוטי רקמה", titleEn: "Special Woven Fabrics; Tufted; Lace; Tapestries" },
        { num: "59", titleHe: "אריגים טקסטיליים בהשריה, מצופים, מכוסים או משולבים; מוצרים טקסטיליים מהסוג המתאים לשימוש תעשייתי", titleEn: "Impregnated, Coated Textile Fabrics; Technical Textile" },
        { num: "60", titleHe: "אריגים סרוגים או סרוגי-מסרגה", titleEn: "Knitted or Crocheted Fabrics" },
        { num: "61", titleHe: "חפצי הלבשה ואבזרי לבוש, סרוגים או סרוגי-מסרגה", titleEn: "Apparel and Clothing Accessories, Knitted" },
        { num: "62", titleHe: "חפצי הלבשה ואבזרי לבוש, לא סרוגים ולא סרוגי-מסרגה", titleEn: "Apparel and Clothing Accessories, Not Knitted" },
        { num: "63", titleHe: "מוצרי טקסטיל מוגמרים אחרים; ערכות; בלאי בגדים ומוצרי טקסטיל בלויים; סמרטוטים", titleEn: "Other Made Up Textile Articles; Sets; Rags" },
      ]
    },
    {
      id: 12,
      titleHe: "הנעלה, כובעים, מטריות, שמשיות, מקלות-הליכה, מקלות-ישיבה, שוטים, מגלבים וחלקיהם; נוצות מעובדות וחפצים עשויים מהן; פרחים מלאכותיים; חפצים משיער אדם",
      titleEn: "Footwear, Headgear, Umbrellas, Walking-Sticks; Prepared Feathers",
      chapters: [
        { num: "64", titleHe: "הנעלה, גאטרים וכדומה; חלקים של חפצים אלה", titleEn: "Footwear, Gaiters and the Like; Parts Thereof" },
        { num: "65", titleHe: "כיסויי ראש וחלקיהם", titleEn: "Headgear and Parts Thereof" },
        { num: "66", titleHe: "מטריות, שמשיות, מקלות-הליכה, מקלות-ישיבה, שוטים, מגלבים וחלקיהם", titleEn: "Umbrellas, Sun Umbrellas, Walking-Sticks, Whips" },
        { num: "67", titleHe: "נוצות עופות מעובדות וחפצים עשויים נוצות; פרחים מלאכותיים; חפצים משיער אדם", titleEn: "Prepared Feathers; Artificial Flowers; Human Hair" },
      ]
    },
    {
      id: 13,
      titleHe: "חפצים מאבן, גבס, מלט, אסבסט, נציץ או חמרים דומים; מוצרי קרמיקה; זכוכית ומוצרי זכוכית",
      titleEn: "Articles of Stone, Plaster, Cement; Ceramic Products; Glass",
      chapters: [
        { num: "68", titleHe: "חפצים מאבן, גבס, מלט, אסבסט, נציץ או חמרים דומים", titleEn: "Articles of Stone, Plaster, Cement, Asbestos, Mica" },
        { num: "69", titleHe: "מוצרי קרמיקה", titleEn: "Ceramic Products" },
        { num: "70", titleHe: "זכוכית ומוצרי זכוכית", titleEn: "Glass and Glassware" },
      ]
    },
    {
      id: 14,
      titleHe: "פנינים טבעיות או מתורבתות, אבנים יקרות או חצי-יקרות, מתכות יקרות, מתכות מצופות במתכות יקרות וחפצים מהם; תכשיטי חיקוי; מטבעות",
      titleEn: "Pearls, Precious Stones, Precious Metals; Imitation Jewelry; Coins",
      chapters: [
        { num: "71", titleHe: "פנינים טבעיות או מתורבתות, אבנים יקרות או חצי-יקרות, מתכות יקרות, מתכות מצופות במתכות יקרות וחפצים מהם; תכשיטי חיקוי; מטבעות", titleEn: "Pearls, Precious Stones, Precious Metals, Jewelry" },
      ]
    },
    {
      id: 15,
      titleHe: "מתכות בסיסיות ומוצרים ממתכות בסיסיות",
      titleEn: "Base Metals and Articles of Base Metal",
      chapters: [
        { num: "72", titleHe: "ברזל ופלדה", titleEn: "Iron and Steel" },
        { num: "73", titleHe: "מוצרים מברזל או מפלדה", titleEn: "Articles of Iron or Steel" },
        { num: "74", titleHe: "נחושת ומוצריה", titleEn: "Copper and Articles Thereof" },
        { num: "75", titleHe: "ניקל ומוצריו", titleEn: "Nickel and Articles Thereof" },
        { num: "76", titleHe: "אלומיניום ומוצריו", titleEn: "Aluminium and Articles Thereof" },
        { num: "78", titleHe: "עופרת ומוצריה", titleEn: "Lead and Articles Thereof" },
        { num: "79", titleHe: "אבץ ומוצריו", titleEn: "Zinc and Articles Thereof" },
        { num: "80", titleHe: "בדיל ומוצריו", titleEn: "Tin and Articles Thereof" },
        { num: "81", titleHe: "מתכות בסיסיות אחרות; קרמטים; מוצריהם", titleEn: "Other Base Metals; Cermets; Articles Thereof" },
        { num: "82", titleHe: "כלים, מכשירים, סכו\"ם, מכפית ומזלג, ממתכת בסיסית; חלקיהם ממתכת בסיסית", titleEn: "Tools, Implements, Cutlery, Spoons and Forks" },
        { num: "83", titleHe: "חפצי מתכת שונים ממתכת בסיסית", titleEn: "Miscellaneous Articles of Base Metal" },
      ]
    },
    {
      id: 16,
      titleHe: "מכונות ומכשירים מכניים; ציוד חשמלי; חלקיהם; מקליטים ומשחזרי קול, מקליטים ומשחזרי תמונת טלוויזיה וקול, וחלקים ואבזרים של חפצים אלה",
      titleEn: "Machinery and Mechanical Appliances; Electrical Equipment",
      chapters: [
        { num: "84", titleHe: "גרעינים גרעיניים; דוודים, מכונות ומתקנים מכניים; חלקיהם", titleEn: "Nuclear Reactors, Boilers, Machinery" },
        { num: "85", titleHe: "מכונות וציוד חשמליים וחלקיהם; מקליטים ומשחזרי קול, מקליטים ומשחזרי תמונת טלוויזיה וקול, וחלקים ואבזרים של חפצים אלה", titleEn: "Electrical Machinery and Equipment; Sound Recorders" },
      ]
    },
    {
      id: 17,
      titleHe: "כלי רכב, כלי טיס, כלי שיט וציוד תחבורתי נלווה",
      titleEn: "Vehicles, Aircraft, Vessels and Associated Transport Equipment",
      chapters: [
        { num: "86", titleHe: "קטרי רכבת או חשמלית וציוד רכבת או חשמלית מתגלגל, וחלקיהם; מתקנים ואבזרים למסילות לתנועה; ציוד לאיתות תנועה מכני (לרבות אלקטרומכני) מכל הסוגים", titleEn: "Railway or Tramway Locomotives and Rolling-Stock" },
        { num: "87", titleHe: "כלי רכב שאינם ציוד רכבת או חשמלית מתגלגל, וחלקיהם ואבזריהם", titleEn: "Vehicles Other Than Railway or Tramway Rolling-Stock" },
        { num: "88", titleHe: "כלי טיס, חלליות, וחלקיהם", titleEn: "Aircraft, Spacecraft, and Parts Thereof" },
        { num: "89", titleHe: "אניות, סירות ומבנים צפים", titleEn: "Ships, Boats and Floating Structures" },
      ]
    },
    {
      id: 18,
      titleHe: "מכשירים ומתקנים אופטיים, פוטוגרפיים, קינמטוגרפיים, מדידה, בדיקה, דיוק, רפואיים או כירורגיים; שעונים ועת-מדים; כלי נגינה; חלקיהם ואבזריהם",
      titleEn: "Optical, Photographic, Measuring, Medical Instruments; Clocks; Musical",
      chapters: [
        { num: "90", titleHe: "מכשירים ומתקנים אופטיים, פוטוגרפיים, קינמטוגרפיים, מדידה, בדיקה, דיוק, רפואיים או כירורגיים; חלקיהם ואבזריהם", titleEn: "Optical, Photographic, Medical or Surgical Instruments" },
        { num: "91", titleHe: "שעונים ועת-מדים וחלקיהם", titleEn: "Clocks and Watches and Parts Thereof" },
        { num: "92", titleHe: "כלי נגינה; חלקים ואבזרים של חפצים אלה", titleEn: "Musical Instruments; Parts and Accessories" },
      ]
    },
    {
      id: 19,
      titleHe: "נשק ותחמושת; חלקיהם ואביזריהם",
      titleEn: "Arms and Ammunition; Parts and Accessories Thereof",
      chapters: [
        { num: "93", titleHe: "נשק ותחמושת; חלקיהם ואביזריהם", titleEn: "Arms and Ammunition; Parts and Accessories" },
      ]
    },
    {
      id: 20,
      titleHe: "מוצרים שונים",
      titleEn: "Miscellaneous Manufactured Articles",
      chapters: [
        { num: "94", titleHe: "רהיטים; מצעים, מזרנים, תומכי מזרנים, כריות ומוצרי ריפוד דומים; מנורות ואבזרי תאורה, שלא פורשו ולא נכללו במקום אחר; שלטים מוארים, לוחיות שם מוארות וכדומה; מבנים טרומיים", titleEn: "Furniture; Bedding, Mattresses; Lamps; Prefabricated Buildings" },
        { num: "95", titleHe: "צעצועים, משחקים ואביזרי ספורט; חלקיהם ואביזריהם", titleEn: "Toys, Games and Sports Requisites; Parts and Accessories" },
        { num: "96", titleHe: "מוצרים שונים", titleEn: "Miscellaneous Manufactured Articles" },
        { num: "97", titleHe: "יצירות אמנות, פריטי אספנות ועתיקות", titleEn: "Works of Art, Collectors' Pieces and Antiques" },
      ]
    },
    {
      id: 21,
      titleHe: "פרקים מיוחדים (ישראליים)",
      titleEn: "Special Israeli Chapters",
      chapters: [
        { num: "98", titleHe: "פטורים מיוחדים", titleEn: "Special Exemptions" },
        { num: "99", titleHe: "עולים ותושבים חוזרים", titleEn: "Immigrants and Returning Residents" },
      ]
    }
  ]
};

// ============================================
// תוספות ב׳-י״ז - SUPPLEMENTS 2-17 (Trade Agreements)
// ============================================
const TRADE_AGREEMENT_SUPPLEMENTS = [
  { id: "supplement-2", num: "ב׳", titleHe: "תוספת שניה", titleEn: "Second Supplement", description: "הסכמי סחר - הוראות כלליות", country: null },
  { id: "supplement-3", num: "ג׳", titleHe: "תוספת שלישית", titleEn: "Third Supplement", description: "ארגון הסחר העולמי (WTO)", country: "WTO", flag: "🌐" },
  { id: "supplement-4", num: "ד׳", titleHe: "תוספת רביעית", titleEn: "Fourth Supplement", description: "הקהילה האירופית (EU)", country: "EU", flag: "🇪🇺" },
  { id: "supplement-5", num: "ה׳", titleHe: "תוספת חמישית", titleEn: "Fifth Supplement", description: "ארצות הברית של אמריקה (USA)", country: "USA", flag: "🇺🇸" },
  { id: "supplement-6", num: "ו׳", titleHe: "תוספת שישית", titleEn: "Sixth Supplement", description: "איגוד הסחר החופשי האירופי (EFTA)", country: "EFTA", flag: "🇨🇭" },
  { id: "supplement-7", num: "ז׳", titleHe: "תוספת שביעית", titleEn: "Seventh Supplement", description: "קנדה", country: "Canada", flag: "🇨🇦" },
  { id: "supplement-8", num: "ח׳", titleHe: "תוספת שמינית", titleEn: "Eighth Supplement", description: "מקסיקו", country: "Mexico", flag: "🇲🇽" },
  { id: "supplement-9", num: "ט׳", titleHe: "תוספת תשיעית", titleEn: "Ninth Supplement", description: "טורקיה", country: "Turkey", flag: "🇹🇷" },
  { id: "supplement-10", num: "י׳", titleHe: "תוספת עשירית", titleEn: "Tenth Supplement", description: "ירדן", country: "Jordan", flag: "🇯🇴" },
  { id: "supplement-11", num: "י״א", titleHe: "תוספת אחת עשרה", titleEn: "Eleventh Supplement", description: "מרכז אמריקה (CAFTA)", country: "CAFTA", flag: "🌎" },
  { id: "supplement-12", num: "י״ב", titleHe: "תוספת שתים עשרה", titleEn: "Twelfth Supplement", description: "מרקוסור (MERCOSUR)", country: "MERCOSUR", flag: "🌎" },
  { id: "supplement-13", num: "י״ג", titleHe: "תוספת שלוש עשרה", titleEn: "Thirteenth Supplement", description: "הפחתת מכס כללית", country: null },
  { id: "supplement-14", num: "י״ד", titleHe: "תוספת ארבע עשרה", titleEn: "Fourteenth Supplement", description: "פנמה", country: "Panama", flag: "🇵🇦" },
  { id: "supplement-15", num: "ט״ו", titleHe: "תוספת חמש עשרה", titleEn: "Fifteenth Supplement", description: "קולומביה", country: "Colombia", flag: "🇨🇴" },
  { id: "supplement-16", num: "ט״ז", titleHe: "תוספת שש עשרה", titleEn: "Sixteenth Supplement", description: "אוקראינה", country: "Ukraine", flag: "🇺🇦" },
  { id: "supplement-17", num: "י״ז", titleHe: "תוספת שבע עשרה", titleEn: "Seventeenth Supplement", description: "הרפובליקה של קוריאה", country: "Korea", flag: "🇰🇷" },
];

// Sample Chapter 85 Data
const SAMPLE_CH85 = {
  notes: [
    "פרק זה אינו כולל: (א) שמיכות, כריות, משענות רגליים חשמליות וכדומה (פרק 94)",
    "הביטוי 'מוצרים חשמליים' בפרק זה כולל גם מוצרים אלקטרוניים",
    "לעניין פרטי משנה 8541.40 ו-8542.31 עד 8542.39, הביטוי 'מודולים' כולל גם לוחיות",
  ],
  headings: [
    { code: "8501", titleHe: "מנועים חשמליים וגנרטורים (למעט ערכות גנרטור)", titleEn: "Electric motors and generators", dutyRate: "פטור",
      subheadings: [
        { code: "850110", titleHe: "מנועים בהספק שאינו עולה על 37.5 וואט", dutyRate: "פטור" },
        { code: "850120", titleHe: "מנועי AC/DC אוניברסליים בהספק העולה על 37.5W", dutyRate: "פטור" },
        { code: "850131", titleHe: "מנועי DC אחרים - עד 750W", dutyRate: "פטור" },
        { code: "850132", titleHe: "מנועי DC אחרים - 750W עד 75kW", dutyRate: "פטור" },
      ]},
    { code: "8517", titleHe: "מכשירי טלפון, לרבות טלפונים לרשתות תאיות או לרשתות אחרות אלחוטיות", titleEn: "Telephone sets, including cellular network telephones", dutyRate: "פטור",
      subheadings: [
        { code: "851711", titleHe: "מכשירי טלפון קווי עם שפופרת אלחוטית", dutyRate: "פטור" },
        { code: "851712", titleHe: "טלפונים לרשתות תאיות או לרשתות אלחוטיות אחרות", dutyRate: "פטור", isPopular: true },
        { code: "851718", titleHe: "אחרים", dutyRate: "פטור", isOther: true },
        { code: "851762", titleHe: "מכונות לקליטה, המרה ושידור או שחזור של קול, תמונות או נתונים אחרים", dutyRate: "פטור" },
      ]},
    { code: "8536", titleHe: "מכשירים חשמליים למיתוג או להגנה על מעגלים חשמליים", titleEn: "Electrical apparatus for switching or protecting electrical circuits", dutyRate: "6%",
      subheadings: [
        { code: "853610", titleHe: "נתיכים", dutyRate: "6%" },
        { code: "853620", titleHe: "מפסיקים אוטומטיים", dutyRate: "6%" },
        { code: "853630", titleHe: "מכשירים אחרים להגנה על מעגלים חשמליים", dutyRate: "6%" },
        { code: "853641", titleHe: "ממסרים למתח שאינו עולה על 60V", dutyRate: "6%" },
        { code: "853650", titleHe: "מתגים אחרים", dutyRate: "6%" },
        { code: "853669", titleHe: "תקעים ושקעים", dutyRate: "6%" },
        { code: "853690", titleHe: "מכשירים אחרים", dutyRate: "6%", isOther: true },
      ]},
    { code: "8544", titleHe: "תיל מבודד, כבלים ומוליכים חשמליים מבודדים אחרים; כבלי סיב אופטי", titleEn: "Insulated wire, cable; fiber optic cables", dutyRate: "6%",
      subheadings: [
        { code: "854411", titleHe: "תיל לסלילים - מנחושת", dutyRate: "6%" },
        { code: "854419", titleHe: "תיל לסלילים - אחר", dutyRate: "6%" },
        { code: "854420", titleHe: "כבל קואקסיאלי ומוליכים קואקסיאליים אחרים", dutyRate: "6%" },
        { code: "854442", titleHe: "מוליכים חשמליים אחרים למתח עד 1,000V - מצוידים במחברים", dutyRate: "6%", isPopular: true },
        { code: "854449", titleHe: "מוליכים חשמליים אחרים למתח עד 1,000V - אחרים", dutyRate: "6%" },
        { code: "854470", titleHe: "כבלי סיב אופטי", dutyRate: "פטור" },
      ]},
  ]
};

// ============================================
// MAIN COMPONENT
// ============================================
export default function ImportTariffBrowser() {
  const [activeTab, setActiveTab] = useState('supplement-1'); // Start with תוספת ראשונה
  const [expandedSections, setExpandedSections] = useState(new Set([16]));
  const [selectedChapter, setSelectedChapter] = useState(null);
  const [expandedHeadings, setExpandedHeadings] = useState(new Set());
  const [search, setSearch] = useState('');

  const toggleSection = id => setExpandedSections(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const toggleHeading = c => setExpandedHeadings(p => { const n = new Set(p); n.has(c) ? n.delete(c) : n.add(c); return n; });

  const renderFrameworkOrder = () => (
    <div className="space-y-3">
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="p-2 bg-amber-500 rounded-lg"><ScrollText className="w-6 h-6 text-white" /></div>
          <div>
            <h2 className="text-xl font-bold text-amber-900">צו מסגרת</h2>
            <p className="text-sm text-amber-700">Framework Order - הגדרות וכללים</p>
          </div>
        </div>
        <p className="text-amber-800 text-sm mb-4">{FRAMEWORK_ORDER.description}</p>
      </div>
      
      <div className="grid gap-2">
        {FRAMEWORK_ORDER.sections.map(section => (
          <div key={section.id} className="bg-white rounded-lg border p-4 hover:shadow-md transition">
            <h3 className="font-semibold text-slate-800">{section.titleHe}</h3>
            <p className="text-xs text-slate-500">{section.titleEn}</p>
            <p className="text-sm text-slate-600 mt-2">{section.content}</p>
          </div>
        ))}
      </div>
    </div>
  );

  const renderFirstSupplement = () => (
    <>
      {selectedChapter ? (
        <div className="bg-white rounded-xl shadow-lg overflow-hidden border">
          <div className="bg-gradient-to-l from-blue-800 to-indigo-700 text-white p-4">
            <button onClick={() => setSelectedChapter(null)} className="flex items-center gap-1 px-2 py-1 bg-white/15 rounded text-xs mb-2 hover:bg-white/25">
              <ChevronLeft className="w-3 h-3" />חזרה לתוספת ראשונה
            </button>
            <span className="bg-white/20 px-2 py-0.5 rounded-full text-xs">פרק {selectedChapter.num}</span>
            <h2 className="text-lg font-bold mt-1">{selectedChapter.titleHe}</h2>
            <p className="text-xs opacity-70">{selectedChapter.titleEn}</p>
          </div>
          
          {selectedChapter.num === "85" ? (
            <>
              <div className="bg-amber-50 border-r-4 border-amber-400 p-3 text-sm">
                <div className="flex items-center gap-1 text-amber-700 font-semibold mb-1"><Info className="w-4 h-4" />הערות לפרק</div>
                <ul className="list-disc pr-4 text-slate-600 text-xs space-y-1">{SAMPLE_CH85.notes.map((n,i) => <li key={i}>{n}</li>)}</ul>
              </div>
              <div className="p-3 space-y-2">
                {SAMPLE_CH85.headings.map(h => (
                  <div key={h.code} className="border rounded-lg overflow-hidden">
                    <button onClick={() => toggleHeading(h.code)} className="w-full flex items-center gap-2 p-2.5 hover:bg-slate-50 text-right">
                      <span className="font-mono font-bold text-blue-700">{h.code}</span>
                      <div className="flex-1 text-sm">
                        <div className="font-medium">{h.titleHe}</div>
                        <div className="text-xs text-slate-400">{h.titleEn}</div>
                      </div>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${h.dutyRate === 'פטור' ? 'bg-emerald-100 text-emerald-700' : 'bg-blue-100 text-blue-700'}`}>{h.dutyRate}</span>
                      <ChevronDown className={`w-4 h-4 text-slate-300 transition ${expandedHeadings.has(h.code) ? 'rotate-180' : ''}`} />
                    </button>
                    {expandedHeadings.has(h.code) && h.subheadings && (
                      <div className="bg-slate-50 border-t divide-y">
                        {h.subheadings.map(s => (
                          <div key={s.code} className={`flex items-center gap-2 px-3 py-2 text-sm ${s.isOther ? 'bg-amber-50' : s.isPopular ? 'bg-emerald-50' : ''}`}>
                            <span className="font-mono text-blue-600 text-xs w-16">{s.code}</span>
                            <span className="flex-1 flex items-center gap-1 flex-wrap">
                              {s.titleHe}
                              {s.isOther && <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-amber-200 text-amber-800 rounded text-xs"><AlertTriangle className="w-3 h-3" />אחרי</span>}
                              {s.isPopular && <span className="px-1.5 py-0.5 bg-emerald-200 text-emerald-800 rounded text-xs">נפוץ</span>}
                            </span>
                            <span className="text-emerald-600 font-medium text-xs">{s.dutyRate}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="p-8 text-center text-slate-400">
              <Package className="w-10 h-10 mx-auto mb-2 opacity-50" />
              <p className="font-medium">נתונים יטענו מהספרייה</p>
              <p className="text-xs">בחר פרק 85 לדוגמה מלאה</p>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-4 mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-600 rounded-lg"><BookOpen className="w-6 h-6 text-white" /></div>
              <div>
                <h2 className="text-xl font-bold text-blue-900">תוספת ראשונה</h2>
                <p className="text-sm text-blue-700">First Supplement - תעריף המכס (פרקים 01-99)</p>
              </div>
            </div>
          </div>
          
          {FIRST_SUPPLEMENT.sections.map(section => (
            <div key={section.id} className="bg-white rounded-lg shadow-sm overflow-hidden border">
              <button onClick={() => toggleSection(section.id)} className="w-full flex items-center gap-2 p-3 hover:bg-slate-50 text-right">
                <div className="w-9 h-9 bg-gradient-to-br from-blue-700 to-indigo-800 text-white rounded-lg flex items-center justify-center font-bold text-sm">
                  {String(section.id).padStart(2,'0')}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm truncate">{section.titleHe}</div>
                  <div className="text-xs text-slate-400 truncate">{section.titleEn}</div>
                </div>
                <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">{section.chapters.length}</span>
                <ChevronDown className={`w-4 h-4 text-slate-300 transition ${expandedSections.has(section.id) ? 'rotate-180' : ''}`} />
              </button>
              {expandedSections.has(section.id) && (
                <div className="border-t bg-slate-50 divide-y divide-slate-100">
                  {section.chapters.map(ch => (
                    <button key={ch.num} onClick={() => setSelectedChapter(ch)} className="w-full flex items-center gap-2 px-4 py-2 hover:bg-white text-right">
                      <span className="font-semibold text-blue-700 text-sm w-14">פרק {ch.num}</span>
                      <span className="flex-1 text-sm truncate">{ch.titleHe}</span>
                      <ChevronLeft className="w-3 h-3 text-slate-300" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );

  const renderTradeAgreements = () => (
    <div className="space-y-3">
      <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl p-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="p-2 bg-green-600 rounded-lg"><Globe className="w-6 h-6 text-white" /></div>
          <div>
            <h2 className="text-xl font-bold text-green-900">תוספות ב׳-י״ז</h2>
            <p className="text-sm text-green-700">הסכמי סחר בינלאומיים - Trade Agreements</p>
          </div>
        </div>
        <p className="text-green-800 text-sm">הפחתות והעדפות מכס לפי הסכמים בינלאומיים</p>
      </div>
      
      <div className="grid gap-2">
        {TRADE_AGREEMENT_SUPPLEMENTS.map(supp => (
          <div key={supp.id} className="bg-white rounded-lg border p-4 hover:shadow-md transition flex items-center gap-3">
            <div className="text-3xl">{supp.flag || '📋'}</div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="bg-green-100 text-green-800 px-2 py-0.5 rounded text-xs font-semibold">תוספת {supp.num}</span>
                <h3 className="font-semibold text-slate-800">{supp.titleHe}</h3>
              </div>
              <p className="text-sm text-slate-600">{supp.description}</p>
              <p className="text-xs text-slate-400">{supp.titleEn}</p>
            </div>
            <ChevronLeft className="w-5 h-5 text-slate-300" />
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div dir="rtl" className="min-h-screen bg-gradient-to-b from-slate-100 to-slate-200 font-sans">
      {/* Header */}
      <header className="bg-gradient-to-l from-indigo-900 via-blue-800 to-blue-700 text-white p-4 shadow-xl sticky top-0 z-50">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-4 flex-wrap mb-3">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-white/10 rounded-lg"><Landmark className="w-8 h-8" /></div>
              <div>
                <h1 className="text-xl font-bold tracking-tight">צו תעריף המכס והפטורים ומס קנייה</h1>
                <p className="text-xs opacity-70">RPA-PORT | Import Customs Tariff Order</p>
              </div>
            </div>
            <div className="flex-1 max-w-sm relative">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input type="text" placeholder="חיפוש קוד או תיאור..." value={search} onChange={e => setSearch(e.target.value)}
                className="w-full py-2 pr-9 pl-8 rounded-lg text-slate-800 text-sm" />
            </div>
            <a href="https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb/he/CustomsBook/Import/CustomsTaarifEntry" target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1 px-3 py-1.5 bg-white/10 rounded-lg text-xs hover:bg-white/20 transition">
              <ExternalLink className="w-3 h-3" />אתר רשמי
            </a>
          </div>
          
          {/* Navigation Tabs */}
          <div className="flex gap-1 bg-white/10 rounded-lg p-1">
            <button onClick={() => { setActiveTab('framework'); setSelectedChapter(null); }}
              className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition ${activeTab === 'framework' ? 'bg-white text-blue-800' : 'hover:bg-white/10'}`}>
              <ScrollText className="w-4 h-4 inline ml-1" />צו מסגרת
            </button>
            <button onClick={() => { setActiveTab('supplement-1'); setSelectedChapter(null); }}
              className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition ${activeTab === 'supplement-1' ? 'bg-white text-blue-800' : 'hover:bg-white/10'}`}>
              <BookOpen className="w-4 h-4 inline ml-1" />תוספת ראשונה
            </button>
            <button onClick={() => { setActiveTab('trade'); setSelectedChapter(null); }}
              className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition ${activeTab === 'trade' ? 'bg-white text-blue-800' : 'hover:bg-white/10'}`}>
              <Globe className="w-4 h-4 inline ml-1" />תוספות ב׳-י״ז
            </button>
          </div>
        </div>
      </header>

      {/* Stats */}
      <div className="max-w-5xl mx-auto px-4 py-3">
        <div className="grid grid-cols-4 gap-2">
          {[[ScrollText,"1","צו מסגרת"],[BookOpen,"99","פרקים"],[Globe,"16","הסכמי סחר"],[Package,"~5,300","פרטים"]].map(([I,v,l],i) => (
            <div key={i} className="bg-white rounded-lg p-2.5 shadow-sm flex items-center gap-2 border">
              <I className="w-6 h-6 text-blue-600 opacity-70" />
              <div><div className="text-lg font-bold text-blue-900">{v}</div><div className="text-xs text-slate-400">{l}</div></div>
            </div>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-5xl mx-auto px-4 pb-8">
        {activeTab === 'framework' && renderFrameworkOrder()}
        {activeTab === 'supplement-1' && renderFirstSupplement()}
        {activeTab === 'trade' && renderTradeAgreements()}
      </main>

      {/* Footer */}
      <footer className="text-center p-3 text-slate-400 text-xs border-t bg-white/50">
        <p>נתונים: צו תעריף המכס והפטורים ומס קנייה על טובין | רשות המסים בישראל</p>
        <p className="font-semibold text-blue-700">RPA-PORT | Library & Research AI</p>
      </footer>
    </div>
  );
}
