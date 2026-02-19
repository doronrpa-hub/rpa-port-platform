"""
Chapter-level seed expertise for Israeli customs classification.

This module contains the broker's embedded knowledge about each tariff section
and its chapters — what belongs where, common traps, and key distinctions.

Imported by customs_law.py as BLOCK 5. Do NOT duplicate this data elsewhere.
"""

# Section I-XXII with chapter ranges and expertise patterns
SEED_EXPERTISE = {
    "I": {
        "name_en": "Live Animals; Animal Products",
        "name_he": "בעלי חיים חיים; מוצרים מן החי",
        "chapters": list(range(1, 6)),
        "notes": [
            "Chapter 1: Live animals only — dead animals go to ch.2 (meat) or ch.5 (inedible)",
            "Chapter 2: Meat and edible offal — raw/chilled/frozen. Cooked preparations → ch.16",
            "Chapter 3: Fish and crustaceans — live, fresh, chilled, frozen, dried, smoked. Prepared → ch.16",
            "Chapter 4: Dairy, eggs, honey, edible animal products n.e.s.",
            "Chapter 5: Products of animal origin n.e.s. (bones, horns, hair, feathers)",
        ],
        "traps": [
            "Cooked/prepared meat → ch.16, not ch.2",
            "Fish fillets vs whole fish → different sub-headings",
            "Honey substitutes → ch.17 (sugars), not ch.4",
        ],
    },
    "II": {
        "name_en": "Vegetable Products",
        "name_he": "מוצרים מן הצומח",
        "chapters": list(range(6, 15)),
        "notes": [
            "Chapter 6: Live trees and plants",
            "Chapter 7: Edible vegetables — fresh/chilled/frozen/dried. Prepared → ch.20",
            "Chapter 8: Edible fruit and nuts — fresh/dried. Prepared → ch.20",
            "Chapter 9: Coffee, tea, spices",
            "Chapter 10: Cereals",
            "Chapter 11: Products of milling industry (flour, starch)",
            "Chapter 12: Oil seeds, oleaginous fruits, misc grains",
            "Chapter 13: Lac, gums, resins, other vegetable saps",
            "Chapter 14: Vegetable plaiting materials",
        ],
        "traps": [
            "Kiwi = ch.8 (fruit), not ch.3 (fish/caviar) — documented failure",
            "Frozen vegetables: blanched = ch.7; cooked = ch.20",
            "Roasted nuts with salt = ch.20 (prepared), not ch.8",
        ],
    },
    "III": {
        "name_en": "Animal or Vegetable Fats and Oils",
        "name_he": "שומנים ושמנים מן החי או מן הצומח",
        "chapters": [15],
        "notes": [
            "Chapter 15: Animal/vegetable fats and oils, prepared edible fats, waxes",
        ],
        "traps": [
            "Margarine → 15.17, not dairy (ch.4)",
            "Essential oils → ch.33, not ch.15",
        ],
    },
    "IV": {
        "name_en": "Prepared Foodstuffs; Beverages, Spirits and Vinegar; Tobacco",
        "name_he": "מוצרי מזון מעובדים; משקאות, אלכוהול וחומץ; טבק",
        "chapters": list(range(16, 25)),
        "notes": [
            "Chapter 16: Preparations of meat, fish, crustaceans",
            "Chapter 17: Sugars and sugar confectionery",
            "Chapter 18: Cocoa and cocoa preparations",
            "Chapter 19: Preparations of cereals, flour, starch, milk (bakery, pasta)",
            "Chapter 20: Preparations of vegetables, fruit, nuts",
            "Chapter 21: Miscellaneous edible preparations",
            "Chapter 22: Beverages, spirits, vinegar",
            "Chapter 23: Residues from food industries; animal feed",
            "Chapter 24: Tobacco and manufactured tobacco substitutes",
        ],
        "traps": [
            "Ouzo → 22.08.90 'others' AFTER eliminating named spirits — documented failure",
            "Energy drinks with vitamins → ch.22, not ch.21 or ch.30",
            "Pet food → ch.23, not ch.16",
            "Food supplements: if dosage form → ch.21.06; if medicinal claims → ch.30",
        ],
    },
    "V": {
        "name_en": "Mineral Products",
        "name_he": "מוצרים מינרליים",
        "chapters": list(range(25, 28)),
        "notes": [
            "Chapter 25: Salt, sulphur, earths, stone, plaster, lime, cement",
            "Chapter 26: Ores, slag, ash",
            "Chapter 27: Mineral fuels, oils, waxes, bituminous substances",
        ],
        "traps": [
            "Petroleum products: crude → 27.09; refined → 27.10",
            "Natural gas → 27.11",
        ],
    },
    "VI": {
        "name_en": "Products of the Chemical or Allied Industries",
        "name_he": "מוצרי תעשיות כימיות או תעשיות נלוות",
        "chapters": list(range(28, 39)),
        "notes": [
            "Chapter 28: Inorganic chemicals",
            "Chapter 29: Organic chemicals",
            "Chapter 30: Pharmaceutical products",
            "Chapter 31: Fertilizers",
            "Chapter 32: Tanning/dyeing extracts, paints, inks",
            "Chapter 33: Essential oils, perfumery, cosmetics",
            "Chapter 34: Soap, washing preparations, waxes, candles",
            "Chapter 35: Albuminoidal substances, glues, enzymes",
            "Chapter 36: Explosives, matches, pyrotechnics",
            "Chapter 37: Photographic or cinematographic goods",
            "Chapter 38: Miscellaneous chemical products",
        ],
        "traps": [
            "Cosmetics with medicinal active ingredient: if PRIMARY purpose is cosmetic → ch.33; medicinal → ch.30",
            "Hand sanitizer: if >60% alcohol → ch.22 or ch.38; if cosmetic form → ch.33",
            "Dietary supplements in dosage form → ch.21.06 or ch.30 depending on claims",
            "Chemical compounds: defined vs mixtures — ch.28/29 vs ch.38",
        ],
    },
    "VII": {
        "name_en": "Plastics and Articles Thereof; Rubber and Articles Thereof",
        "name_he": "פלסטיק ומוצריו; גומי ומוצריו",
        "chapters": list(range(39, 41)),
        "notes": [
            "Chapter 39: Plastics and articles thereof",
            "Chapter 40: Rubber and articles thereof",
        ],
        "traps": [
            "Tires → 40.11 (new pneumatic), NOT 40.01 (natural rubber) — documented failure",
            "Plastic bags: for retail → ch.39; for packaging goods → may stay with goods",
            "Silicone: rubber form → ch.40; in liquid/paste → ch.39 or ch.34",
        ],
    },
    "VIII": {
        "name_en": "Raw Hides and Skins, Leather, Furskins and Articles Thereof",
        "name_he": "עורות גולמיים, עור, פרוות ומוצריהם",
        "chapters": list(range(41, 44)),
        "notes": [
            "Chapter 41: Raw hides and skins (other than furskins) and leather",
            "Chapter 42: Articles of leather, travel goods, handbags",
            "Chapter 43: Furskins and artificial fur",
        ],
        "traps": [
            "Handbags: material determines chapter — leather → ch.42; textile → ch.62/63; plastic → ch.42",
        ],
    },
    "IX": {
        "name_en": "Wood and Articles of Wood; Cork; Basketware",
        "name_he": "עץ ומוצריו; שעם; מוצרי קליעה",
        "chapters": list(range(44, 47)),
        "notes": [
            "Chapter 44: Wood and articles of wood; wood charcoal",
            "Chapter 45: Cork and articles of cork",
            "Chapter 46: Manufactures of straw, basketware",
        ],
        "traps": [
            "Wooden furniture → ch.94, not ch.44",
            "Plywood/MDF → ch.44",
        ],
    },
    "X": {
        "name_en": "Pulp of Wood; Paper and Paperboard",
        "name_he": "עיסת עץ; נייר וקרטון",
        "chapters": list(range(47, 50)),
        "notes": [
            "Chapter 47: Pulp of wood or other fibrous cellulosic material",
            "Chapter 48: Paper and paperboard; articles of paper pulp",
            "Chapter 49: Printed books, newspapers, pictures",
        ],
        "traps": [
            "Paper packaging → ch.48; printed packaging → may be ch.49",
            "Stickers/labels: printed → ch.49; self-adhesive blank → ch.48",
        ],
    },
    "XI": {
        "name_en": "Textiles and Textile Articles",
        "name_he": "טקסטיל ומוצרי טקסטיל",
        "chapters": list(range(50, 64)),
        "notes": [
            "Chapter 50: Silk",
            "Chapter 51: Wool, fine/coarse animal hair",
            "Chapter 52: Cotton",
            "Chapter 53: Other vegetable textile fibres; paper yarn",
            "Chapter 54: Man-made filaments; strip of man-made textile materials",
            "Chapter 55: Man-made staple fibres",
            "Chapter 56: Wadding, felt, nonwovens; special yarns; twine, cordage",
            "Chapter 57: Carpets and other textile floor coverings",
            "Chapter 58: Special woven fabrics; tufted textile fabrics; lace; tapestries",
            "Chapter 59: Impregnated, coated, covered or laminated textile fabrics",
            "Chapter 60: Knitted or crocheted fabrics",
            "Chapter 61: Articles of apparel, knitted or crocheted",
            "Chapter 62: Articles of apparel, not knitted or crocheted",
            "Chapter 63: Other made up textile articles; sets; worn clothing; rags",
        ],
        "traps": [
            "Garments: knitted → ch.61; woven → ch.62. This is the FIRST determination",
            "Composition determines material chapter (50-55) for fabrics",
            "Section XI Note 2: goods classifiable in ch.50-55 AND ch.56-63 → classify in ch.56-63",
        ],
    },
    "XII": {
        "name_en": "Footwear, Headgear, Umbrellas, Walking-Sticks, Whips, Riding-Crops; Prepared Feathers; Artificial Flowers",
        "name_he": "נעליים, כיסויי ראש, מטריות, מקלות הליכה; נוצות מעובדות; פרחים מלאכותיים",
        "chapters": list(range(64, 68)),
        "notes": [
            "Chapter 64: Footwear, gaiters",
            "Chapter 65: Headgear",
            "Chapter 66: Umbrellas, walking-sticks, whips, riding-crops",
            "Chapter 67: Prepared feathers; artificial flowers; articles of human hair",
        ],
        "traps": [
            "Footwear material of outer sole determines classification in ch.64",
            "Sports shoes with cleats → specific sub-headings in 64.02",
        ],
    },
    "XIII": {
        "name_en": "Articles of Stone, Plaster, Cement, Asbestos, Mica; Ceramic Products; Glass and Glassware",
        "name_he": "מוצרי אבן, גבס, מלט, אסבסט, נציץ; מוצרי קרמיקה; זכוכית ומוצריה",
        "chapters": list(range(68, 71)),
        "notes": [
            "Chapter 68: Articles of stone, plaster, cement, asbestos, mica",
            "Chapter 69: Ceramic products",
            "Chapter 70: Glass and glassware",
        ],
        "traps": [
            "Ceramic tiles → ch.69; stone tiles → ch.68",
            "Glass bottles for beverages → ch.70; with beverages → classify by contents",
        ],
    },
    "XIV": {
        "name_en": "Natural or Cultured Pearls, Precious Stones, Precious Metals; Imitation Jewellery; Coin",
        "name_he": "פנינים, אבנים יקרות, מתכות יקרות; תכשיטי חיקוי; מטבעות",
        "chapters": [71],
        "notes": [
            "Chapter 71: Natural/cultured pearls, precious/semi-precious stones, precious metals, jewellery, coin",
        ],
        "traps": [
            "Costume/imitation jewellery → 71.17, not base metal chapters",
            "Gold bars → 71.08; gold coins → 71.18",
        ],
    },
    "XV": {
        "name_en": "Base Metals and Articles of Base Metal",
        "name_he": "מתכות פשוטות ומוצריהן",
        "chapters": list(range(72, 84)),
        "notes": [
            "Chapter 72: Iron and steel",
            "Chapter 73: Articles of iron or steel",
            "Chapter 74: Copper",
            "Chapter 75: Nickel",
            "Chapter 76: Aluminium",
            "Chapter 77: Reserved for future use in HS",
            "Chapter 78: Lead",
            "Chapter 79: Zinc",
            "Chapter 80: Tin",
            "Chapter 81: Other base metals; cermets",
            "Chapter 82: Tools, cutlery of base metal",
            "Chapter 83: Miscellaneous articles of base metal",
        ],
        "traps": [
            "Screws/bolts → ch.73 (iron/steel); material determines which metal chapter",
            "Section XV Note 1: excludes goods of Section XVI (machinery/electrical)",
            "Parts of general use (screws, springs, etc.) → Section XV, not with the machine",
        ],
    },
    "XVI": {
        "name_en": "Machinery and Mechanical Appliances; Electrical Equipment",
        "name_he": "מכונות ומתקנים מכניים; ציוד חשמלי",
        "chapters": [84, 85],
        "notes": [
            "Chapter 84: Nuclear reactors, boilers, machinery, mechanical appliances",
            "Chapter 85: Electrical machinery, equipment; sound/image recorders, TV",
        ],
        "traps": [
            "Section XVI Note 2: parts 'באופן עיקרי או בלעדי' (principally/solely) used with specific machine → classify with that machine",
            "Computer monitors → 85.28; computer → 84.71",
            "Printer → 84.43; scanner → 84.71",
            "Multi-function machines: classify by principal function (Rule 3ב)",
            "Cables/connectors: generic → ch.85; specific to machine → with machine",
        ],
    },
    "XVII": {
        "name_en": "Vehicles, Aircraft, Vessels and Associated Transport Equipment",
        "name_he": "כלי רכב, כלי טיס, כלי שיט וציוד תחבורה נלווה",
        "chapters": list(range(86, 90)),
        "notes": [
            "Chapter 86: Railway/tramway locomotives, rolling-stock, track fixtures",
            "Chapter 87: Vehicles other than railway/tramway rolling-stock",
            "Chapter 88: Aircraft, spacecraft",
            "Chapter 89: Ships, boats, floating structures",
        ],
        "traps": [
            "Car parts: specific → with ch.87; general use (screws) → Section XV",
            "Electric vehicles → 87.03 (still vehicles, not electrical equipment)",
            "Drones: if aircraft → ch.88; if toy → ch.95",
        ],
    },
    "XVIII": {
        "name_en": "Optical, Photographic, Cinematographic, Measuring, Checking, Precision, Medical or Surgical Instruments; Clocks and Watches; Musical Instruments",
        "name_he": "מכשירים אופטיים, צילום, מדידה, בדיקה, דיוק, רפואיים; שעונים; כלי נגינה",
        "chapters": list(range(90, 93)),
        "notes": [
            "Chapter 90: Optical, photographic, measuring, medical instruments",
            "Chapter 91: Clocks and watches",
            "Chapter 92: Musical instruments",
        ],
        "traps": [
            "Medical devices: if instrument → ch.90; if furniture (hospital bed) → ch.94",
            "Camera lens → ch.90; camera body → ch.90; phone camera module → ch.85 (part of phone)",
            "Smartwatch: if primarily watch → ch.91; if primarily computer → ch.84/85",
        ],
    },
    "XIX": {
        "name_en": "Arms and Ammunition",
        "name_he": "נשק ותחמושת",
        "chapters": [93],
        "notes": [
            "Chapter 93: Arms and ammunition; parts and accessories thereof",
        ],
        "traps": [
            "Toy guns → ch.95, not ch.93",
            "Hunting knives → ch.82 (cutlery), not ch.93",
        ],
    },
    "XX": {
        "name_en": "Miscellaneous Manufactured Articles",
        "name_he": "מוצרים מעורבים שונים",
        "chapters": list(range(94, 97)),
        "notes": [
            "Chapter 94: Furniture, bedding, lamps, prefabricated buildings",
            "Chapter 95: Toys, games, sports requisites",
            "Chapter 96: Miscellaneous manufactured articles (pens, buttons, brooms, etc.)",
        ],
        "traps": [
            "LED light fixture → ch.94 (lighting); LED component → ch.85",
            "Office furniture → ch.94; office machines → ch.84",
            "Baby stroller → ch.87 (vehicle), not ch.94 (furniture)",
        ],
    },
    "XXI": {
        "name_en": "Works of Art, Collectors' Pieces and Antiques",
        "name_he": "יצירות אמנות, פריטי אספנות ועתיקות",
        "chapters": [97],
        "notes": [
            "Chapter 97: Works of art, collectors' pieces, antiques",
        ],
        "traps": [
            "Reproductions/copies → classify by material, not as art",
            "Antiques must be >100 years old for 97.06",
        ],
    },
    "XXII": {
        "name_en": "Israeli Special Provisions",
        "name_he": "הוראות מיוחדות ישראליות",
        "chapters": [98, 99],
        "notes": [
            "Chapter 98: Israeli special tariff provisions",
            "Chapter 99: Discount codes (קודי הנחה) — not a classification chapter",
        ],
        "traps": [
            "Ch.99 codes are discount/exemption codes applied AFTER classification, not classification codes",
            "Ch.98 is unique to Israel — no international equivalent",
        ],
    },
}


def get_section_for_chapter(chapter: int) -> str:
    """Return the section number (Roman numeral) for a given chapter number."""
    for section_id, section_data in SEED_EXPERTISE.items():
        if chapter in section_data["chapters"]:
            return section_id
    return ""


def get_section_data(section_id: str) -> dict:
    """Return full section data for a given section ID (Roman numeral)."""
    return SEED_EXPERTISE.get(section_id, {})
