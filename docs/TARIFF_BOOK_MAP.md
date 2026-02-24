# AllCustomsBookDataPDF.pdf — Complete Page Map

**Source file:** `downloads/AllCustomsBookDataPDF.pdf` (41 MB, 5,540 PDF pages)
**Downloaded from:** `https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb/he/CustomsBook/Home/DownloadFileWithName?fileName=AllCustomsBookDataPDF.pdf`
**Print date (per footers):** 11/07/2024
**Verified:** 2026-02-24 by mapping script (scripts/verify_supplements.py)

## Page Offset

The first 10 PDF pages are the Table of Contents.
Content begins at PDF page 11 = internal page 1.

**Formula:** `pdf_page = internal_page + 10`

---

## Table of Contents (PDF pages 1-10)

| PDF Pages | Content |
|-----------|---------|
| 1-10 | תוכן ענינים (Table of Contents) |

---

## צו מסגרת — Framework Order (PDF pages 11-32)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 1-22 | 11-32 | צו מסגרת (33 articles, definitions, FTA clauses) |

**Text quality:** Readable Hebrew. Already converted: `downloads/FrameOrder.xml`
**Also available separately:** `downloads/FrameOrder.pdf` (172 KB)
**Already in code:** `functions/lib/_framework_order_data.py` (33 articles with full Hebrew text)

---

## תעריף המכס — Tariff Schedule (PDF pages 33-3068)

| Internal Pages | PDF Pages | Section | Chapters | Content |
|---------------|-----------|---------|----------|---------|
| 23-92 | 33-102 | I — בעלי חיים; מוצרים מבעלי חיים | 1-5 | Live animals, meat, fish, dairy |
| 93-158 | 103-168 | II — מוצרי צמחים | 6-14 | Vegetables, fruits, cereals |
| 159-182 | 169-192 | III — שומנים ושמנים | 15 | Fats and oils |
| 183-255 | 193-265 | IV — מזון, משקאות, טבק | 16-24 | Food preparations, beverages, tobacco |
| 256-330 | 266-340 | V — מוצרים מינרליים | 25-27 | Mineral products |
| 331-748 | 341-758 | VI — מוצרים כימיים | 28-38 | Chemical products |
| 749-876 | 759-886 | VII — פלסטיק וגומי | 39-40 | Plastics and rubber |
| 877-909 | 887-919 | VIII — עורות ופרוות | 41-43 | Hides, leather, furskins |
| 910-967 | 920-977 | IX — עץ, שעם, קליעה | 44-46 | Wood, cork, basketware |
| 968-1039 | 978-1049 | X — נייר וקרטון | 47-49 | Paper, paperboard |
| 1041-1487 | 1051-1497 | XI — טקסטיל | 50-63 | Textiles |
| 1488-1513 | 1498-1523 | XII — מנעלים, כיסויי ראש | 64-67 | Footwear, headgear |
| 1514-1619 | 1524-1629 | XIII — אבן, קרמיקה, זכוכית | 68-70 | Stone, ceramics, glass |
| 1620-1652 | 1630-1662 | XIV — אבנים יקרות, מתכות יקרות | 71 | Precious stones/metals |
| 1653-1996 | 1663-2006 | XV — מתכות פשוטות | 72-83 | Base metals |
| 2053-2685 | 2063-2695 | XVI — מכונות וציוד חשמלי | 84-85 | Machinery, electrical equipment |
| 2686-2812 | 2696-2822 | XVII — כלי רכב, טייס, שייט | 86-89 | Vehicles, aircraft, vessels |
| 2813-2946 | 2823-2956 | XVIII — מכשירים אופטיים, שעונים | 90-92 | Optical instruments, clocks |
| 2947-2956 | 2957-2966 | XIX — נשק ותחמושת | 93 | Arms and ammunition |
| 2957-3029 | 2967-3039 | XX — פריטים מיוצרים שונים | 94-96 | Furniture, toys, misc. |
| 3030-3053 | 3040-3063 | XXI — יצירות אמנות | 97 | Works of art, antiques |
| 3054-3068 | 3064-3078 | XXII — נספח (פרק 98-99) | 98-99 | Israeli special chapter |

**Text quality:** Sections I-XXII have readable Hebrew text. Available separately as I.pdf through XXII.pdf.
**Already in system:** `tariff` Firestore collection (11,753 entries with descriptions and duty rates)

---

## קודי הנחה — Discount Codes (PDF pages 3079-3133)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 3069-3123 | 3079-3133 | קודי הנחה (Discount/exemption codes) — 55 pages |

**Text quality:** GARBLED. Uses encoded font — Hebrew appears as squares/Oriya/Tamil characters. HS codes (XX.XX.XXXXXX) ARE readable.
**Also available separately:** `downloads/ExemptCustomsItems.pdf` (1 MB)
**NOT yet in system.** ExemptCustomsItems.pdf may have better text extraction.

---

## תוספת שנייה — Second Addition (PDF page 3134)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 3124 | 3134 | תוספת שנייה — Purchase tax table structure rules (1 page) |

**Text quality:** Readable Hebrew.
**Also available separately:** `downloads/SecondAddition.pdf` (72 KB)

---

## תוספת שלישית — Third Addition: WTO Quotas (PDF pages 3135-3144)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 3125-3134 | 3135-3144 | תוספת שלישית — WTO tariff quotas (10 pages) |

**Text quality:** GARBLED font encoding. HS codes readable.
**Also available separately:** `downloads/ThirdAddition.pdf` (202 KB)

---

## תוספת רביעית — Fourth Addition: FTA Rate Tables (PDF pages 3145-3171)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 3135-3161 | 3145-3171 | תוספת רביעית — HS codes by FTA agreement column (27 pages) |

**Text quality:** GARBLED. HS codes readable. Contains multi-column FTA rate tables.
**NOT available as separate PDF.** Must extract from this file.

---

## תוספת חמישית — Fifth Addition (PDF pages 3172-3179)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 3162-3169 | 3172-3179 | תוספת חמישית (8 pages) |

**Text quality:** GARBLED. HS codes readable.

---

## תוספת שישית — Sixth Addition (PDF pages 3180-3197)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 3170-3187 | 3180-3197 | תוספת שישית — 100% duty codes (18 pages) |

**Text quality:** GARBLED. HS codes readable.

---

## תוספת שביעית — Seventh Addition (PDF pages 3198-3251)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 3188-3241 | 3198-3251 | תוספת שביעית — 100% duty reduction codes (54 pages) |

**Text quality:** GARBLED. HS codes readable.

---

## תוספת שמינית — Eighth Addition (PDF pages 3252-3256)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 3242-3246 | 3252-3256 | תוספת שמינית — Turkey FTA rates (5 pages) |

**Text quality:** GARBLED. HS codes readable.

---

## תוספת תשיעית — Ninth Addition (PDF pages 3257-3260)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 3247-3250 | 3257-3260 | תוספת תשיעית — Mexico FTA (4 pages) |

**Text quality:** GARBLED. HS codes readable.

---

## תוספת עשירית — Tenth Addition (PDF pages 3261-3271)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 3251-3271 | 3261-3281 | תוספת עשירית — HS code cross-reference table (11-21 pages) |

**Text quality:** GARBLED. HS codes readable.

---

## Supplements 11, 12, 13 — DO NOT EXIST

Confirmed by TOC: jumps from תוספת עשירית (10) to תוספת ארבע עשר (14).
These supplement numbers were never assigned in the Israeli tariff system.

---

## תוספת ארבע עשרה — Fourteenth Addition (PDF pages 3282-3364)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 3272-3354 | 3282-3364 | תוספת ארבע עשרה — HS codes with duty column (83 pages) |

**Text quality:** GARBLED. HS codes readable.

---

## תוספת חמש עשרה — Fifteenth Addition (PDF pages 3365-3388)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 3355-3378 | 3365-3388 | תוספת חמש עשרה — Colombia FTA codes (24 pages) |

**Text quality:** GARBLED. HS codes readable.

---

## תוספת שש עשרה — Sixteenth Addition (PDF pages 3389-4122)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 3379-4112 | 3389-4122 | תוספת שש עשרה — Georgia FTA codes (734 pages!) |

**Text quality:** GARBLED. HS codes readable.
**Note:** This is by far the largest supplement (734 pages). Contains extensive HS code tables.

---

## תוספת שבע עשרה — Seventeenth Addition (PDF pages 4123-4148)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 4113-4138 | 4123-4148 | תוספת שבע עשרה — UK FTA codes (26 pages) |

**Text quality:** GARBLED. HS codes readable.

---

## תוספת שמונה עשרה — Eighteenth Addition (PDF pages 4149-4800)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 4139-4790 | 4149-4800 | תוספת שמונה עשרה — Korea FTA (652 pages) |

**Text quality:** GARBLED. HS codes readable.
**Note:** Second largest supplement (652 pages).

---

## תוספת תשע עשרה — Nineteenth Addition (PDF pages 4801-5540)

| Internal Pages | PDF Pages | Content |
|---------------|-----------|---------|
| 4791-5530 | 4801-5540 | תוספת תשע עשרה — UAE FTA (740 pages) |

**Text quality:** GARBLED. HS codes readable.
**Note:** Largest supplement (740 pages). Ends at PDF page 5540 (last page).

---

## Summary

| Section | PDF Pages | Page Count | Text Quality |
|---------|-----------|------------|--------------|
| Table of Contents | 1-10 | 10 | Readable |
| צו מסגרת | 11-32 | 22 | Readable |
| Tariff (Sections I-XXII, Ch 1-99) | 33-3078 | 3,046 | Readable |
| קודי הנחה (Discount Codes) | 3079-3133 | 55 | **GARBLED** |
| תוספת שנייה (2nd) | 3134 | 1 | Readable |
| תוספת שלישית (3rd, WTO) | 3135-3144 | 10 | **GARBLED** |
| תוספת רביעית (4th) | 3145-3171 | 27 | **GARBLED** |
| תוספת חמישית (5th) | 3172-3179 | 8 | **GARBLED** |
| תוספת שישית (6th) | 3180-3197 | 18 | **GARBLED** |
| תוספת שביעית (7th) | 3198-3251 | 54 | **GARBLED** |
| תוספת שמינית (8th, Turkey) | 3252-3256 | 5 | **GARBLED** |
| תוספת תשיעית (9th, Mexico) | 3257-3260 | 4 | **GARBLED** |
| תוספת עשירית (10th) | 3261-3281 | 21 | **GARBLED** |
| ~~11th, 12th, 13th~~ | — | — | DO NOT EXIST |
| תוספת ארבע עשרה (14th) | 3282-3364 | 83 | **GARBLED** |
| תוספת חמש עשרה (15th, Colombia) | 3365-3388 | 24 | **GARBLED** |
| תוספת שש עשרה (16th, Georgia) | 3389-4122 | 734 | **GARBLED** |
| תוספת שבע עשרה (17th, UK) | 4123-4148 | 26 | **GARBLED** |
| תוספת שמונה עשרה (18th, Korea) | 4149-4800 | 652 | **GARBLED** |
| תוספת תשע עשרה (19th, UAE) | 4801-5540 | 740 | **GARBLED** |
| **TOTAL** | | **5,540** | |

### Text Extraction Notes

**Readable sections (PDF pages 1-3134):** ~3,134 pages of Hebrew text extractable as Unicode. Includes TOC, Framework Order, and full tariff schedule (Sections I-XXII with all 97 chapters).

**Garbled sections (PDF pages 3079-5540):** ~2,406 pages use a non-standard font encoding. Hebrew text appears as Oriya/Tamil/block characters. **HS codes (XX.XX.XXXXXX format) ARE extractable** as they use standard numeric encoding. Column headers and Hebrew labels are NOT readable.

**Implication for supplements:** The supplement data (FTA preferential rates, discount codes) cannot be extracted as readable text from this PDF. The **separate section PDFs** (I.pdf through XXII.pdf) and **separate addition PDFs** (SecondAddition.pdf, ThirdAddition.pdf) should be tried first. For supplements 4-19, the data may need to come from the XML archive (`fullCustomsBookData.zip`) which has structured data in `AdditionRulesDetailsHistory.xml` and `TariffDetailsHistory_*.xml`.

### FTA Agreement ↔ Supplement Mapping (from צו מסגרת article 18-25)

| Supplement | FTA Agreement | TOC Abbreviation |
|-----------|---------------|-------------------|
| 3 | WTO | WTO |
| 4 | Multiple (cross-ref table) | — |
| 5 | Multiple | — |
| 6 | 100% duty | — |
| 7 | 100% duty reduction | — |
| 8 | Turkey | TUR |
| 9 | Mexico | MEX |
| 10 | Cross-reference | — |
| 14 | — | — |
| 15 | Colombia | COL |
| 16 | Georgia | GEO |
| 17 | UK | GBR |
| 18 | Korea | KOR |
| 19 | UAE | UAE |
