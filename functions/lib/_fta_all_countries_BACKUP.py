# -*- coding: utf-8 -*-
"""
FTA All Countries — Structured data for 16 Free Trade Agreement partners.

Parsed from 309 govil XML/PDF files in downloads/govil/.
Each country entry contains metadata, file inventory, document classification,
and key articles extracted from XML <article> elements.

Usage:
    from lib._fta_all_countries import (
        FTA_COUNTRIES, get_fta_country, get_all_country_codes,
        get_countries_with_eur1, search_fta_articles,
        get_country_files, classify_fta_document,
    )
"""

import os
import re

# ---------------------------------------------------------------------------
# GOVIL directory path (relative to functions/)
# ---------------------------------------------------------------------------
_GOVIL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "downloads", "govil",
)

# ---------------------------------------------------------------------------
# Document type classification patterns
# ---------------------------------------------------------------------------
_DOC_TYPE_PATTERNS = [
    # Origin rules & proof
    (re.compile(r"makor|origin|rules.of.origin|כללי.מקור|תעודת.מקור", re.I), "origin_rules"),
    (re.compile(r"eur1|EUR\.1|eur-1", re.I), "eur1_form"),
    (re.compile(r"teodat.makor|certificate.of.origin|milui.makor", re.I), "certificate_of_origin"),
    (re.compile(r"approved.exporter|יצואן.מאושר|nohal.misim", re.I), "approved_exporter"),
    (re.compile(r"invoice.declaration|חשבון.הצהרה|heshbon.hatzhar", re.I), "invoice_declaration"),
    # Benefits / concessions (before agreement_text — more specific)
    (re.compile(r"benefit|concession|הטבות|הטבה|tariff.schedule", re.I), "benefits_schedule"),
    (re.compile(r"agri|agriculture|חקלאות", re.I), "agriculture"),
    (re.compile(r"industry|תעשיי", re.I), "industry"),
    # Procedures / explanations (before agreement_text — more specific)
    (re.compile(r"procedure|ita.procedure|shitun|נוהל", re.I), "procedure"),
    (re.compile(r"exp\b|hesber|explanat|הסבר|brief", re.I), "explanation"),
    (re.compile(r"tech.guide|guide", re.I), "technical_guide"),
    # Updates / committees
    (re.compile(r"update|correction|תיקון", re.I), "update"),
    (re.compile(r"committee|joint|ועדה", re.I), "joint_committee"),
    (re.compile(r"mutual.recognition|mra", re.I), "mutual_recognition"),
    # Reviews / summaries
    (re.compile(r"review|economic.review|סקירה", re.I), "economic_review"),
    (re.compile(r"summ|summary|תקציר", re.I), "summary"),
    (re.compile(r"exit|preparation|הכנה", re.I), "preparation"),
    # Regional convention
    (re.compile(r"regional.convention|אמנה.אזורית", re.I), "regional_convention"),
    # Transfer / loading
    (re.compile(r"transfer|loading|העמסה|העברה", re.I), "transfer_rules"),
    # Intellectual property
    (re.compile(r"intellectual|property|קניין.רוחני", re.I), "intellectual_property"),
    # Memorandum
    (re.compile(r"memorandum|דברי.הסבר", re.I), "explanatory_memorandum"),
    # Agreement texts (generic — must be LAST to avoid catching specific docs)
    (re.compile(r"agreement|agree|הסכם|fta\b", re.I), "agreement_text"),
    (re.compile(r"protocol|פרוטוקול|annex|נספח|appendix", re.I), "protocol_annex"),
]


def classify_fta_document(filename):
    """Classify an FTA document filename into a document type.

    Returns a string like 'origin_rules', 'agreement_text', 'benefits_schedule', etc.
    Falls back to 'other' if no pattern matches.
    """
    for pattern, doc_type in _DOC_TYPE_PATTERNS:
        if pattern.search(filename):
            return doc_type
    return "other"


# ---------------------------------------------------------------------------
# File inventory per country (XML files only — each has a matching PDF)
# ---------------------------------------------------------------------------
_COUNTRY_XML_FILES = {
    "eu": [
        "Annex1-euro-fta",
        "benefits-euro-fta-export-from-israel",
        "benefits-euro-fta-import-to-israel",
        "euro-fta-Protocol42006_en",
        "euro-fta-agreement-en",
        "euro-fta-agreement-he",
        "euro-fta-agri-2010-en",
        "euro-fta-agri-2010-he",
        "exp-euro-fta-agri-2010",
        "fta-eur1-makor-example",
        "fta-teodat-makor-exp",
        "nohal-misim-approved-exporter",
    ],
    "uk": [
        "Annex1-euro-fta",
        "economic-review-uk-2019",
        "israel-uk-agreement-chapter5",
        "israel-uk-agreement-en",
        "israel-uk-agreement-he",
        "israel-uk-fta-appendix1",
        "israel-uk-fta-appendix2",
        "uk-exit-without-agreement-preparation",
    ],
    "efta": [
        "efta-Israel-Iceland-Agreement-2018",
        "efta-Israel-Norway-Agreement-2018",
        "efta-Israel-Switzerland-Agreement-2018",
        "efta-fta-annex-2",
        "efta-fta-en",
        "efta-fta-he",
        "efta-fta-hesber-Annex-I-Excluded-Products-2018",
        "efta-fta-hesber",
        "efta-fta-protocol-a-2018",
        "efta-fta-protocol-b",
        "efta-israel-tech-guide-export-benefits",
        "fta-eur1-makor-example",
        "fta-teodat-makor-exp",
        "nohal-misim-approved-exporter",
    ],
    "turkey": [
        "Turkey-fta-en",
        "Turkey-fta-he",
        "Turkey-joined-committee2006",
        "Turkey-joined-committee2007",
        "fta-eur1-makor-example",
        "fta-teodat-makor-exp",
        "nohal-misim-approved-exporter",
        "turkey-benefits-from-isr",
        "turkey-benefits-to-isr",
        "turkey-fta-annax1",
        "turkey-fta-exp-update2",
    ],
    "jordan": [
        "fta-eur1-makor-example",
        "fta-teodat-makor-exp",
        "jordan-fta-agreemrnt-he",
        "jordan-fta-agreemrnt-update-protocol-en-2004",
        "jordan-fta-agreemrnt-update-protocol-he-2004",
        "jordan-fta-exp",
        "jordan-fta-table1",
        "jordan-fta-table3-group1",
        "jordan-fta-table3-group2",
        "jordan-fta-tableA2",
        "jordan-fta-tableB2",
        "jordan-fta-tableB2-group1",
        "nohal-misim-approved-exporter",
    ],
    "ukraine": [
        "intro-ukraine-israel-fta",
        "israel-ukraine-fta-en",
        "israel-ukraine-fta-he",
        "israel-ukraine-fta-regional-convention",
        "ukraine-fta-export-Concessions-Final",
        "ukraine-fta-import-Concessions-Final",
    ],
    "usa": [
        "Mutual-Recognition-Agreement-usa-isr-en",
        "Mutual-Recognition-Agreement-usa-isr-he",
        "attachment-usa-isr-agri-2004",
        "fta-isr-usa-joint-committee-decision",
        "fta-usa-isr-en",
        "fta-usa-isr-exp",
        "fta-usa-isr-he",
        "usa-fta-Intellectual-Property-letters",
        "usa-fta-agri-annexa",
        "usa-fta-agri-annexb",
        "usa-fta-agri-annexc",
        "usa-fta-agri-annexd",
        "usa-fta-agriculture-letters",
        "usa-fta-rules-of-origin",
    ],
    "canada": [
        "canada-FTA-1997-Agreement-en",
        "canada-ag-1997-goods-transfer-usa",
        "canada-agr-summ-2019",
        "canada-mraEng",
        "canada-mraHeb",
        "canadaAgreeHEB",
        "canda-agr-benefits-from-isr-2019",
        "canda-agr-benefits-to-isr-2019",
        "israel_canada_agreement_update",
        "makor-canada1997",
    ],
    "mexico": [
        "Mexico-Israel-fta-en",
        "Mexico-Israel-fta-he",
        "mexico-benefits-from-isr-agriculture",
        "mexico-benefits-to-isr-agriculture",
        "mexico-fta-direct-transfer-update-en",
        "mexico-fta-direct-transfer-update-he",
        "mexico-fta-shitun-ita-procedure",
        "mexico-makor",
        "mexico-milui-makor",
        "mexico-third-party-loading-certificate",
        "mexico-third-party-loading-certificate-exp",
    ],
    "colombia": [
        "Explanatory-Memorandum-Columbia-Agreement",
        "colombia-agree-he-2020",
        "colombia-agriculture-benefits-1",
        "colombia-agriculture-benefits-2",
        "colombia-en-agreement2020",
        "colombia-to-israel-colombia-indusrty-benefits",
        "israel-to-colombia-icolombia-industry-benefits",
        "makor-colombia",
        "milui-makor-colombia",
    ],
    "panama": [
        "ita-procedure-panama-fta",
        "panama-benefits-from-isr-agriculture",
        "panama-benefits-from-isr-daga",
        "panama-benefits-from-isr-industry-goods",
        "panama-benefits-to-isr-agriculture",
        "panama-benefits-to-isr-daga",
        "panama-benefits-to-isr-industry-goods",
        "panama-fta-en-2018",
        "panama-makor",
        "panama-milui-makor",
    ],
    "mercosur": [
        "Decision-Israel-Mercosor-Joint-Committee-2012",
        "Mercosur-fta-EN-2010",
        "Mercosur-ftaHE-2010",
        "mercosur-CERTIFICATE-OF-ORIGIN-2018",
        "mercosur-benefits-from-isr",
        "mercosur-benefits-to-isr",
        "mercosur-filling-Instructions-Certificate-of-Origin",
        "mercosur-fta-exp-08-20",
        "mrcosor_irs_regulations_1_6_2010",
    ],
    "uae": [
        "customs-benefits-isr-to-uae",
        "customs-benefits-uae-to-isr",
        "uae-israel-agreement-en",
        "uae-israel-agreement-he-sum-070324",
        "uae-israel-agreement-he",
    ],
    "korea": [
        "Tariff-Schedule-Israel",
        "Tariff-Schedule-Korea",
        "fta-korea-il-breif-sep2022",
        "fta-korea-il-en",
        "fta-korea-il-he",
    ],
    "guatemala": [
        "guatemala-fta-export-concessions",
        "guatemala-fta-import-concessions",
        "intro-guatemala-israel-fta",
        "israel-guatemala-fta-en",
        "israel-guatemala-fta-he",
    ],
    "vietnam": [
        "vietnam_israel-vietnam-fta-en",
        "vietnam_israel-vietnam-fta-export-benefits",
        "vietnam_israel-vietnam-fta-import-benefits",
    ],
}

# Jordan has one extra file (FTA_jordan_sahar-hutz_jordan-fta-exp.xml) under a
# different path pattern (no "agreements_"). It duplicates jordan-fta-exp content.
# We track the standard path version only.

# ---------------------------------------------------------------------------
# FTA_COUNTRIES — main data structure
# ---------------------------------------------------------------------------
FTA_COUNTRIES = {
    # -----------------------------------------------------------------------
    # EUR.1 countries (EU Pan-Euro-Med cumulation zone)
    # -----------------------------------------------------------------------
    "eu": {
        "name_he": "האיחוד האירופי",
        "name_en": "European Union",
        "agreement_name_he": "הסכם שיתוף ישראל-קהילה האירופית",
        "agreement_name_en": "Euro-Mediterranean Association Agreement",
        "agreement_year": 1995,
        "effective_date": "2000-06-01",
        "origin_proof": "EUR.1",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Pan-Euro-Med diagonal cumulation",
        "cumulation_countries": [
            "EU", "EFTA", "Turkey", "Jordan", "Egypt", "Tunisia",
            "Morocco", "Algeria", "Lebanon", "Syria", "West Bank/Gaza",
            "Faeroe Islands",
        ],
        "govil_file_count": 24,
        "xml_file_count": 12,
        "supplements": [],
        "key_articles": {
            "protocol_4": {
                "title": "Protocol 4 — Definition of Originating Products",
                "title_he": "פרוטוקול 4 — הגדרת מוצרי מקור ושיטות שיתוף פעולה מנהלי",
                "summary": "Defines originating products, sufficient working, cumulation rules, "
                           "proof of origin (EUR.1 / invoice declaration), approved exporter status.",
                "xml_file": "euro-fta-Protocol42006_en",
            },
            "article_22": {
                "title": "EUR.1 Movement Certificate",
                "title_he": "תעודת תנועה EUR.1",
                "summary": "Proof of origin via EUR.1 certificate issued by customs authorities.",
            },
            "article_23": {
                "title": "Invoice Declaration",
                "title_he": "הצהרת חשבונית",
                "summary": "Invoice declaration by approved exporters or for consignments under EUR 6,000.",
            },
            "article_24": {
                "title": "Approved Exporter",
                "title_he": "יצואן מאושר",
                "summary": "Authorization to use invoice declaration without value limit. "
                           "Requires customs supervision and record-keeping.",
            },
            "article_3": {
                "title": "Diagonal Cumulation",
                "title_he": "צבירה אלכסונית",
                "summary": "Materials originating in Pan-Euro-Med countries can be used "
                           "without losing originating status.",
            },
        },
        "value_threshold_eur": 6000,
        "notes": "Protocol 4 (2006 revision) is the current origin protocol. "
                 "Pan-Euro-Med cumulation allows diagonal cumulation with all PEM countries.",
    },

    "uk": {
        "name_he": "הממלכה המאוחדת",
        "name_en": "United Kingdom",
        "agreement_name_he": "הסכם סחר ושותפות ישראל-בריטניה",
        "agreement_name_en": "Israel-UK Trade and Partnership Agreement",
        "agreement_year": 2019,
        "effective_date": "2021-01-01",
        "origin_proof": "EUR.1",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Bilateral + EU materials (transitional)",
        "cumulation_countries": ["UK", "EU (transitional)"],
        "govil_file_count": 16,
        "xml_file_count": 8,
        "supplements": [],
        "key_articles": {
            "chapter_5": {
                "title": "Chapter 5 — Rules of Origin",
                "title_he": "פרק 5 — כללי מקור",
                "summary": "Origin rules based on EU Protocol 4 with modifications for UK. "
                           "EUR.1 or invoice declaration. Approved exporter allowed.",
                "xml_file": "israel-uk-agreement-chapter5",
            },
            "annex_1": {
                "title": "Annex 1 — Product-Specific Rules",
                "title_he": "נספח 1 — כללים ספציפיים למוצר",
                "summary": "Product-specific origin rules by HS chapter, similar to EU Protocol 4 List.",
                "xml_file": "Annex1-euro-fta",
            },
        },
        "value_threshold_eur": 6000,
        "notes": "Post-Brexit agreement largely mirrors EU FTA. "
                 "Origin chapter based on PEM Convention principles.",
    },

    "efta": {
        "name_he": 'אפט"א',
        "name_en": "EFTA",
        "member_states": ["Iceland", "Liechtenstein", "Norway", "Switzerland"],
        "member_states_he": ["איסלנד", "ליכטנשטיין", "נורבגיה", "שוויץ"],
        "agreement_name_he": "הסכם סחר חופשי ישראל-אפט\"א",
        "agreement_name_en": "Israel-EFTA Free Trade Agreement",
        "agreement_year": 1992,
        "effective_date": "1993-01-01",
        "origin_proof": "EUR.1",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Pan-Euro-Med diagonal cumulation",
        "cumulation_countries": [
            "EFTA", "EU", "Turkey", "Jordan", "Egypt", "Tunisia",
            "Morocco", "Faeroe Islands",
        ],
        "govil_file_count": 28,
        "xml_file_count": 14,
        "supplements": [],
        "key_articles": {
            "protocol_a": {
                "title": "Protocol A — Rules of Origin (2018 revision)",
                "title_he": "פרוטוקול א — כללי מקור (עדכון 2018)",
                "summary": "Origin determination, sufficient working, cumulation (bilateral + PEM), "
                           "proof of origin (EUR.1 / invoice declaration).",
                "xml_file": "efta-fta-protocol-a-2018",
            },
            "protocol_b": {
                "title": "Protocol B — Administrative Cooperation",
                "title_he": "פרוטוקול ב — שיתוף פעולה מנהלי",
                "summary": "Verification procedures, mutual administrative assistance, "
                           "dispute resolution for origin matters.",
                "xml_file": "efta-fta-protocol-b",
            },
            "bilateral_agreements": {
                "title": "Bilateral Agricultural Agreements (2018)",
                "title_he": "הסכמים חקלאיים דו-צדדיים (2018)",
                "summary": "Separate bilateral agreements with Iceland, Norway, and Switzerland "
                           "for agricultural products not covered by the main FTA.",
            },
        },
        "value_threshold_eur": 6000,
        "notes": "EFTA is not EU. Four separate bilateral agriculture agreements. "
                 "Liechtenstein in customs union with Switzerland — same rules apply. "
                 "2018 revision aligned Protocol A with PEM Convention.",
    },

    "turkey": {
        "name_he": "טורקיה",
        "name_en": "Turkey",
        "agreement_name_he": "הסכם סחר חופשי ישראל-טורקיה",
        "agreement_name_en": "Israel-Turkey Free Trade Agreement",
        "agreement_year": 1996,
        "effective_date": "1997-05-01",
        "origin_proof": "EUR.1",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Pan-Euro-Med diagonal cumulation",
        "cumulation_countries": ["Turkey", "EU", "EFTA"],
        "govil_file_count": 22,
        "xml_file_count": 11,
        "supplements": [],
        "key_articles": {
            "origin_protocol": {
                "title": "Origin Protocol (EUR.1 based)",
                "title_he": "פרוטוקול מקור (מבוסס EUR.1)",
                "summary": "Standard PEM-zone EUR.1 origin rules. Cumulation with EU and EFTA. "
                           "Product-specific rules in annex.",
            },
            "annex_1": {
                "title": "Annex I — Product-Specific Rules",
                "title_he": "נספח I — כללים ספציפיים למוצר",
                "summary": "Sufficient working/processing list by HS heading.",
                "xml_file": "turkey-fta-annax1",
            },
            "joint_committee_2006": {
                "title": "Joint Committee Decision 2006",
                "title_he": "החלטת הוועדה המשותפת 2006",
                "summary": "Amendment to origin protocol aligning with PEM Convention.",
                "xml_file": "Turkey-joined-committee2006",
            },
        },
        "value_threshold_eur": 6000,
        "notes": "Part of Pan-Euro-Med cumulation zone. "
                 "Joint committee decisions updated origin rules in 2006 and 2007.",
    },

    "jordan": {
        "name_he": "ירדן",
        "name_en": "Jordan",
        "agreement_name_he": "הסכם סחר חופשי ישראל-ירדן",
        "agreement_name_en": "Israel-Jordan Free Trade Agreement",
        "agreement_year": 1995,
        "effective_date": "1995-10-29",
        "origin_proof": "EUR.1",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Pan-Euro-Med diagonal cumulation",
        "cumulation_countries": ["Jordan", "EU", "EFTA", "Turkey"],
        "govil_file_count": 28,
        "xml_file_count": 13,
        "supplements": [],
        "key_articles": {
            "origin_protocol": {
                "title": "Origin Protocol (EUR.1 based)",
                "title_he": "פרוטוקול מקור (מבוסס EUR.1)",
                "summary": "EUR.1 certificate or invoice declaration. Same PEM-zone rules. "
                           "2004 update aligned with diagonal cumulation.",
            },
            "update_2004": {
                "title": "Protocol Update 2004",
                "title_he": "עדכון פרוטוקול 2004",
                "summary": "Updated origin rules to enable Pan-Euro-Med diagonal cumulation.",
                "xml_file": "jordan-fta-agreemrnt-update-protocol-en-2004",
            },
        },
        "value_threshold_eur": 6000,
        "notes": "First FTA Israel signed with an Arab country. 14th XML file is duplicate "
                 "jordan-fta-exp under alternate path (FTA_jordan_sahar-hutz_ without agreements_). "
                 "Part of Pan-Euro-Med cumulation zone since 2004 update. "
                 "Multiple tariff tables (Table 1, Table 3, Table A2, Table B2).",
    },

    # -----------------------------------------------------------------------
    # Invoice Declaration countries (no EUR.1)
    # -----------------------------------------------------------------------
    "usa": {
        "name_he": "ארצות הברית",
        "name_en": "United States",
        "agreement_name_he": "הסכם סחר חופשי ישראל-ארה\"ב",
        "agreement_name_en": "Israel-US Free Trade Area Agreement",
        "agreement_year": 1985,
        "effective_date": "1985-09-01",
        "origin_proof": "Invoice Declaration",
        "has_invoice_declaration": True,
        "has_approved_exporter": False,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["USA"],
        "govil_file_count": 28,
        "xml_file_count": 14,
        "supplements": [],
        "key_articles": {
            "rules_of_origin": {
                "title": "Rules of Origin",
                "title_he": "כללי מקור",
                "summary": "35% value-added rule. Product must be substantially transformed "
                           "in Israel or USA. Invoice declaration (no EUR.1). "
                           "No approved exporter scheme.",
                "xml_file": "usa-fta-rules-of-origin",
            },
            "article_1": {
                "title": "Wholly Obtained Products",
                "title_he": "מוצר שהופק במלואו",
                "summary": "Product wholly grown or produced in a party's territory.",
            },
            "article_1_2": {
                "title": "Substantial Transformation",
                "title_he": "שינוי משמעותי",
                "summary": "Imported inputs must undergo substantial transformation. "
                           "35% domestic content + manufacturing cost requirement.",
            },
        },
        "value_threshold_usd": None,
        "notes": "Israel's first FTA (1985). Simple 35% value-added rule. "
                 "No EUR.1 — uses invoice declaration only. "
                 "Mutual Recognition Agreement for conformity assessment. "
                 "4 agriculture annexes (A-D).",
    },

    "ukraine": {
        "name_he": "אוקראינה",
        "name_en": "Ukraine",
        "agreement_name_he": "הסכם סחר חופשי ישראל-אוקראינה",
        "agreement_name_en": "Israel-Ukraine Free Trade Agreement",
        "agreement_year": 2019,
        "effective_date": "2021-01-01",
        "origin_proof": "EUR.1",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Bilateral + PEM Convention",
        "cumulation_countries": ["Ukraine"],
        "govil_file_count": 12,
        "xml_file_count": 6,
        "supplements": [],
        "key_articles": {
            "origin_chapter": {
                "title": "Origin Rules (Regional Convention based)",
                "title_he": "כללי מקור (מבוסס אמנה אזורית)",
                "summary": "Based on Regional Convention on Pan-Euro-Med Preferential Rules of Origin. "
                           "EUR.1 or invoice declaration. Approved exporter allowed.",
                "xml_file": "israel-ukraine-fta-regional-convention",
            },
        },
        "value_threshold_eur": 6000,
        "notes": "Modern FTA using Regional Convention on PEM Rules of Origin. "
                 "Import and export concession schedules included.",
    },

    # -----------------------------------------------------------------------
    # Certificate of Origin countries
    # -----------------------------------------------------------------------
    "canada": {
        "name_he": "קנדה",
        "name_en": "Canada",
        "agreement_name_he": "הסכם סחר חופשי ישראל-קנדה",
        "agreement_name_en": "Canada-Israel Free Trade Agreement (CIFTA)",
        "agreement_year": 1997,
        "effective_date": "1997-01-01",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": False,
        "has_approved_exporter": False,
        "cumulation": "Bilateral only + US materials (special provision)",
        "cumulation_countries": ["Canada", "USA (limited)"],
        "govil_file_count": 21,
        "xml_file_count": 10,
        "supplements": [],
        "key_articles": {
            "origin_rules": {
                "title": "Origin Rules (Chapter 3)",
                "title_he": "כללי מקור (פרק 3)",
                "summary": "Certificate of Origin required. Tariff shift + regional value content rules. "
                           "Special provision for goods transferred via USA.",
                "xml_file": "makor-canada1997",
            },
            "update_2019": {
                "title": "Agreement Modernization (2019)",
                "title_he": "מודרניזציה של ההסכם (2019)",
                "summary": "Updated benefits schedules and agricultural concessions.",
                "xml_file": "israel_canada_agreement_update",
            },
            "usa_transfer": {
                "title": "Goods Transfer via USA",
                "title_he": "העברת טובין דרך ארה\"ב",
                "summary": "Special rules for goods passing through US territory.",
                "xml_file": "canada-ag-1997-goods-transfer-usa",
            },
        },
        "notes": "Mutual Recognition Agreement (MRA) for conformity assessment. "
                 "2019 modernization updated concession schedules.",
    },

    "mexico": {
        "name_he": "מקסיקו",
        "name_en": "Mexico",
        "agreement_name_he": "הסכם סחר חופשי ישראל-מקסיקו",
        "agreement_name_en": "Israel-Mexico Free Trade Agreement",
        "agreement_year": 2000,
        "effective_date": "2000-07-01",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": False,
        "has_approved_exporter": False,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["Mexico"],
        "govil_file_count": 22,
        "xml_file_count": 11,
        "supplements": [],
        "key_articles": {
            "origin_rules": {
                "title": "Origin Rules",
                "title_he": "כללי מקור",
                "summary": "Certificate of Origin required. Tariff shift rules. "
                           "Third-party loading certificate provisions.",
                "xml_file": "mexico-makor",
            },
            "procedure": {
                "title": "ITA Procedure (Cooperation)",
                "title_he": "נוהל שיתוף פעולה",
                "summary": "Administrative cooperation procedures for origin verification.",
                "xml_file": "mexico-fta-shitun-ita-procedure",
            },
            "direct_transfer": {
                "title": "Direct Transfer Rules (Update)",
                "title_he": "כללי שיגור ישיר (עדכון)",
                "summary": "Updated rules for direct shipment and transshipment.",
                "xml_file": "mexico-fta-direct-transfer-update-en",
            },
        },
        "notes": "Third-party loading certificate available. "
                 "Certificate of Origin filling instructions included.",
    },

    "colombia": {
        "name_he": "קולומביה",
        "name_en": "Colombia",
        "agreement_name_he": "הסכם סחר חופשי ישראל-קולומביה",
        "agreement_name_en": "Israel-Colombia Free Trade Agreement",
        "agreement_year": 2020,
        "effective_date": "2020-08-11",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": True,
        "has_approved_exporter": False,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["Colombia"],
        "govil_file_count": 34,
        "xml_file_count": 9,
        "supplements": [],
        "key_articles": {
            "origin_rules": {
                "title": "Origin Rules",
                "title_he": "כללי מקור",
                "summary": "Certificate of Origin or certified invoice declaration. "
                           "Product-specific rules in annex.",
                "xml_file": "makor-colombia",
            },
            "agreement_text_en": {
                "title": "Full Agreement (English)",
                "title_he": "טקסט ההסכם המלא (אנגלית)",
                "summary": "133 articles covering goods, services, investment, IP, "
                           "dispute settlement, customs procedures.",
                "xml_file": "colombia-en-agreement2020",
            },
        },
        "notes": "Most recent comprehensive FTA (2020). "
                 "133 articles in English version. Includes services and investment chapters. "
                 "Agriculture benefits split into two annexes. "
                 "Explanatory memorandum available.",
    },

    "panama": {
        "name_he": "פנמה",
        "name_en": "Panama",
        "agreement_name_he": "הסכם סחר חופשי ישראל-פנמה",
        "agreement_name_en": "Israel-Panama Free Trade Agreement",
        "agreement_year": 2018,
        "effective_date": "2019-12-30",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": False,
        "has_approved_exporter": False,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["Panama"],
        "govil_file_count": 20,
        "xml_file_count": 10,
        "supplements": [],
        "key_articles": {
            "origin_rules": {
                "title": "Origin Rules",
                "title_he": "כללי מקור",
                "summary": "Certificate of Origin required. ITA verification procedure.",
                "xml_file": "panama-makor",
            },
            "procedure": {
                "title": "ITA Procedure",
                "title_he": "נוהל ITA",
                "summary": "53 articles covering administrative cooperation for origin verification.",
                "xml_file": "ita-procedure-panama-fta",
            },
        },
        "notes": "Benefits split by sector: agriculture, industry, daga (fish). "
                 "Certificate of Origin filling instructions included.",
    },

    "guatemala": {
        "name_he": "גואטמלה",
        "name_en": "Guatemala",
        "agreement_name_he": "הסכם סחר חופשי ישראל-גואטמלה",
        "agreement_name_en": "Israel-Guatemala Free Trade Agreement",
        "agreement_year": 2022,
        "effective_date": "2023-01-06",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": False,
        "has_approved_exporter": False,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["Guatemala"],
        "govil_file_count": 10,
        "xml_file_count": 5,
        "supplements": [],
        "key_articles": {
            "agreement_text": {
                "title": "Full Agreement",
                "title_he": "טקסט ההסכם",
                "summary": "Covers goods trade, origin rules, customs procedures. "
                           "Import and export concession schedules.",
                "xml_file": "israel-guatemala-fta-he",
            },
        },
        "notes": "One of Israel's newer FTAs. "
                 "Introduction document available with overview.",
    },

    "korea": {
        "name_he": "קוריאה",
        "name_en": "South Korea",
        "agreement_name_he": "הסכם סחר חופשי ישראל-קוריאה",
        "agreement_name_en": "Israel-Korea Free Trade Agreement",
        "agreement_year": 2021,
        "effective_date": "2022-12-01",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["South Korea"],
        "govil_file_count": 10,
        "xml_file_count": 5,
        "supplements": [],
        "key_articles": {
            "agreement_text_en": {
                "title": "Full Agreement (English)",
                "title_he": "טקסט ההסכם (אנגלית)",
                "summary": "Comprehensive modern FTA covering goods, services, SPS, TBT, "
                           "customs, e-commerce, government procurement.",
                "xml_file": "fta-korea-il-en",
            },
            "agreement_text_he": {
                "title": "Full Agreement (Hebrew, 308 articles)",
                "title_he": "טקסט ההסכם (עברית, 308 סעיפים)",
                "summary": "Hebrew version with 308 structured articles extracted from XML.",
                "xml_file": "fta-korea-il-he",
            },
            "tariff_schedule_israel": {
                "title": "Tariff Schedule — Israel",
                "title_he": "לוח תעריפים — ישראל",
                "summary": "Israeli tariff concession schedule for Korean imports.",
                "xml_file": "Tariff-Schedule-Israel",
            },
        },
        "notes": "Modern comprehensive FTA. Hebrew version has 308 articles. "
                 "Both Israeli and Korean tariff schedules available. "
                 "Brief summary document from September 2022.",
    },

    "mercosur": {
        "name_he": "מרקוסור",
        "name_en": "Mercosur",
        "member_states": ["Argentina", "Brazil", "Paraguay", "Uruguay"],
        "member_states_he": ["ארגנטינה", "ברזיל", "פרגוואי", "אורוגוואי"],
        "agreement_name_he": "הסכם סחר חופשי ישראל-מרקוסור",
        "agreement_name_en": "Israel-Mercosur Free Trade Agreement",
        "agreement_year": 2007,
        "effective_date": "2010-06-01",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": False,
        "has_approved_exporter": False,
        "cumulation": "Bilateral (Mercosur bloc treated as single territory)",
        "cumulation_countries": ["Argentina", "Brazil", "Paraguay", "Uruguay"],
        "govil_file_count": 18,
        "xml_file_count": 9,
        "supplements": [],
        "key_articles": {
            "origin_rules": {
                "title": "Rules of Origin (Regulations 2010)",
                "title_he": "כללי מקור (תקנות 2010)",
                "summary": "Certificate of Origin required. Specific form and filling instructions. "
                           "2018 updated certificate format.",
                "xml_file": "mrcosor_irs_regulations_1_6_2010",
            },
            "certificate_2018": {
                "title": "Certificate of Origin (2018 format)",
                "title_he": "תעודת מקור (פורמט 2018)",
                "summary": "Updated certificate of origin form adopted in 2018.",
                "xml_file": "mercosur-CERTIFICATE-OF-ORIGIN-2018",
            },
            "joint_committee_2012": {
                "title": "Joint Committee Decision 2012",
                "title_he": "החלטת הוועדה המשותפת 2012",
                "summary": "Amendments to the agreement following joint committee meeting.",
                "xml_file": "Decision-Israel-Mercosor-Joint-Committee-2012",
            },
        },
        "notes": "Mercosur bloc treated as single territory for cumulation. "
                 "Certificate of Origin filling instructions document available. "
                 "2018 updated certificate format.",
    },

    "uae": {
        "name_he": "איחוד האמירויות",
        "name_en": "United Arab Emirates",
        "agreement_name_he": "הסכם שותפות כלכלית מקיף ישראל-איחוד האמירויות",
        "agreement_name_en": "Israel-UAE Comprehensive Economic Partnership Agreement (CEPA)",
        "agreement_year": 2022,
        "effective_date": "2023-04-01",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["UAE"],
        "govil_file_count": 10,
        "xml_file_count": 5,
        "supplements": [],
        "key_articles": {
            "chapter_3": {
                "title": "Chapter 3 — Rules of Origin",
                "title_he": "פרק 3 — כללי מקור",
                "summary": "Modern origin rules with product-specific rules (PSRs) annex. "
                           "Certificate of Origin or approved origin declaration.",
            },
            "agreement_text_en": {
                "title": "Full Agreement (English, 32 articles)",
                "title_he": "טקסט ההסכם (אנגלית)",
                "summary": "Comprehensive agreement covering goods, services, government procurement, "
                           "e-commerce, customs procedures, SPS, TBT.",
                "xml_file": "uae-israel-agreement-en",
            },
            "agreement_text_he": {
                "title": "Full Agreement (Hebrew)",
                "title_he": "טקסט ההסכם (עברית)",
                "summary": "Hebrew version of the full CEPA agreement.",
                "xml_file": "uae-israel-agreement-he",
            },
        },
        "notes": "First FTA with a Gulf state. Signed under Abraham Accords framework. "
                 "Comprehensive modern agreement including services, investment, e-commerce. "
                 "Hebrew summary document available (March 2024).",
    },

    "vietnam": {
        "name_he": "וייטנאם",
        "name_en": "Vietnam",
        "agreement_name_he": "הסכם סחר חופשי ישראל-וייטנאם",
        "agreement_name_en": "Israel-Vietnam Free Trade Agreement (VIFTA)",
        "agreement_year": 2023,
        "effective_date": "2025-01-15",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["Vietnam"],
        "govil_file_count": 6,
        "xml_file_count": 3,
        "supplements": [],
        "key_articles": {
            "agreement_text_en": {
                "title": "Full Agreement (English)",
                "title_he": "טקסט ההסכם (אנגלית)",
                "summary": "Modern FTA covering goods, services, investment, "
                           "origin rules, customs procedures.",
                "xml_file": "vietnam_israel-vietnam-fta-en",
            },
        },
        "notes": "Israel's newest FTA. Entered into force January 2025. "
                 "Export and import benefit schedules available.",
    },
}


# ---------------------------------------------------------------------------
# Shared documents — appear under multiple countries
# ---------------------------------------------------------------------------
_SHARED_DOCUMENTS = {
    "fta-eur1-makor-example": {
        "title": "EUR.1 Certificate of Origin — Sample",
        "title_he": "תעודת מקור EUR.1 — דוגמה",
        "doc_type": "eur1_form",
        "countries": ["eu", "efta", "turkey", "jordan"],
    },
    "fta-teodat-makor-exp": {
        "title": "Certificate of Origin — Explanation",
        "title_he": "תעודת מקור — הסבר",
        "doc_type": "certificate_of_origin",
        "countries": ["eu", "efta", "turkey", "jordan"],
    },
    "nohal-misim-approved-exporter": {
        "title": "Approved Exporter Procedure",
        "title_he": "נוהל יצואן מאושר",
        "doc_type": "approved_exporter",
        "countries": ["eu", "efta", "turkey", "jordan"],
    },
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_fta_country(code):
    """Get FTA country data by country code.

    Args:
        code: Country code string (e.g. 'eu', 'usa', 'korea').

    Returns:
        dict with country data, or None if not found.
    """
    return FTA_COUNTRIES.get(code.lower() if code else None)


def get_all_country_codes():
    """Return sorted list of all 16 FTA country codes."""
    return sorted(FTA_COUNTRIES.keys())


def get_countries_with_eur1():
    """Return list of country codes that use EUR.1 as origin proof."""
    return [
        code for code, data in FTA_COUNTRIES.items()
        if data.get("origin_proof") == "EUR.1"
    ]


def get_countries_with_approved_exporter():
    """Return list of country codes that allow approved exporter status."""
    return [
        code for code, data in FTA_COUNTRIES.items()
        if data.get("has_approved_exporter")
    ]


def get_countries_with_invoice_declaration():
    """Return list of country codes that accept invoice declarations."""
    return [
        code for code, data in FTA_COUNTRIES.items()
        if data.get("has_invoice_declaration")
    ]


def get_country_files(code):
    """Get the list of XML file stems for a country.

    Args:
        code: Country code string.

    Returns:
        list of file stem strings (without extension or prefix), or empty list.
    """
    return list(_COUNTRY_XML_FILES.get(code.lower() if code else "", []))


def get_xml_filepath(code, file_stem):
    """Build full XML file path for a country document.

    Args:
        code: Country code (e.g. 'eu').
        file_stem: File stem from _COUNTRY_XML_FILES (e.g. 'euro-fta-Protocol42006_en').

    Returns:
        Absolute path string to the XML file, or None if not found.
    """
    code = (code or "").lower()
    if code not in _COUNTRY_XML_FILES:
        return None
    if file_stem not in _COUNTRY_XML_FILES[code]:
        return None

    # Standard pattern: FTA_{country}_sahar-hutz_agreements_{stem}.xml
    filename = f"FTA_{code}_sahar-hutz_agreements_{file_stem}.xml"
    path = os.path.join(_GOVIL_DIR, filename)
    if os.path.isfile(path):
        return path

    return None


def get_pdf_filepath(code, file_stem):
    """Build full PDF file path for a country document.

    Same as get_xml_filepath but returns .pdf path.
    """
    xml_path = get_xml_filepath(code, file_stem)
    if xml_path:
        return xml_path.replace(".xml", ".pdf")
    return None


def search_fta_articles(keyword):
    """Search across all countries' key articles for a keyword.

    Args:
        keyword: Search term (case-insensitive, searches title, title_he, summary).

    Returns:
        List of dicts with {country_code, country_name, article_key, article_data}.
    """
    if not keyword:
        return []
    kw = keyword.lower()
    results = []
    for code, country_data in FTA_COUNTRIES.items():
        for art_key, art_data in country_data.get("key_articles", {}).items():
            searchable = " ".join([
                art_data.get("title", ""),
                art_data.get("title_he", ""),
                art_data.get("summary", ""),
            ]).lower()
            if kw in searchable:
                results.append({
                    "country_code": code,
                    "country_name": country_data["name_en"],
                    "country_name_he": country_data["name_he"],
                    "article_key": art_key,
                    "article_data": art_data,
                })
    return results


def search_fta_countries(query):
    """Search countries by name, agreement name, or notes.

    Args:
        query: Search term (case-insensitive).

    Returns:
        List of (code, country_data) tuples matching the query.
    """
    if not query:
        return []
    q = query.lower()
    results = []
    for code, data in FTA_COUNTRIES.items():
        searchable = " ".join([
            code,
            data.get("name_he", ""),
            data.get("name_en", ""),
            data.get("agreement_name_he", ""),
            data.get("agreement_name_en", ""),
            data.get("notes", ""),
            data.get("origin_proof", ""),
        ]).lower()
        if q in searchable:
            results.append((code, data))
    return results


def get_origin_proof_type(country_of_origin):
    """Given a country name, find what origin proof is needed.

    Tries to match against name_en, name_he, member states.

    Args:
        country_of_origin: Country name string.

    Returns:
        dict with {country_code, origin_proof, has_invoice_declaration,
        has_approved_exporter} or None.
    """
    if not country_of_origin:
        return None
    q = country_of_origin.lower().strip()

    for code, data in FTA_COUNTRIES.items():
        names = [
            data.get("name_en", "").lower(),
            data.get("name_he", "").lower(),
            code,
        ]
        # Add member states for bloc agreements
        for ms in data.get("member_states", []):
            names.append(ms.lower())
        for ms in data.get("member_states_he", []):
            names.append(ms.lower())

        if q in names or any(q in n for n in names):
            return {
                "country_code": code,
                "origin_proof": data["origin_proof"],
                "has_invoice_declaration": data.get("has_invoice_declaration", False),
                "has_approved_exporter": data.get("has_approved_exporter", False),
                "agreement_name": data.get("agreement_name_en", ""),
            }
    return None


def get_document_inventory():
    """Return full document inventory across all countries.

    Returns:
        dict mapping country_code -> list of {file_stem, doc_type, has_xml, has_pdf}.
    """
    inventory = {}
    for code, files in _COUNTRY_XML_FILES.items():
        docs = []
        for stem in files:
            docs.append({
                "file_stem": stem,
                "doc_type": classify_fta_document(stem),
                "has_xml": True,
                "has_pdf": True,  # All XML files have matching PDFs
            })
        inventory[code] = docs
    return inventory


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def get_summary_stats():
    """Return summary statistics about the FTA collection.

    Returns:
        dict with counts and breakdowns.
    """
    total_xml = sum(len(files) for files in _COUNTRY_XML_FILES.values())
    total_govil = sum(d.get("govil_file_count", 0) for d in FTA_COUNTRIES.values())

    eur1_countries = get_countries_with_eur1()
    cert_countries = [
        c for c in FTA_COUNTRIES
        if FTA_COUNTRIES[c]["origin_proof"] == "Certificate of Origin"
    ]
    invoice_only = [
        c for c in FTA_COUNTRIES
        if FTA_COUNTRIES[c]["origin_proof"] == "Invoice Declaration"
    ]

    total_articles = sum(
        len(d.get("key_articles", {}))
        for d in FTA_COUNTRIES.values()
    )

    return {
        "total_countries": len(FTA_COUNTRIES),
        "total_govil_files": total_govil,
        "total_xml_files": total_xml,
        "total_key_articles": total_articles,
        "eur1_countries": eur1_countries,
        "certificate_of_origin_countries": cert_countries,
        "invoice_declaration_countries": invoice_only,
        "approved_exporter_countries": get_countries_with_approved_exporter(),
        "bloc_agreements": [c for c in FTA_COUNTRIES if "member_states" in FTA_COUNTRIES[c]],
    }
