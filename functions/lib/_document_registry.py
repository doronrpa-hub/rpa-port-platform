"""
Central catalog of ALL official Israeli customs documents in the RPA-PORT system.

Every document gets a registry entry with metadata, source locations, and rendering
info. This is pure Python constants -- no Firestore calls, no network access.

Usage:
    from lib._document_registry import (
        get_document, get_documents_by_category, get_fta_for_country,
        get_relevant_documents, format_citation, search_registry,
        get_all_document_ids, get_supplement_documents,
    )

Categories: tariff, regulation, procedure, law, fta, supplement, reform
"""
from typing import Dict, List, Optional


# ============================================================================
# DOCUMENT REGISTRY
# ============================================================================

DOCUMENT_REGISTRY: Dict[str, dict] = {

    # ========================================================================
    # TARIFF
    # ========================================================================

    "tariff_book": {
        "title_he": "תעריף המכס",
        "title_en": "Customs Tariff Book",
        "category": "tariff",
        "source_xml": "tariff_extract/CustomsItem.xml",
        "source_pdf": "AllCustomsBookDataPDF.pdf",
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff",
        "has_html": True,
        "html_file": "tariff_book.html",
        "searchable_via": ["search_tariff", "verify_hs_code", "get_chapter_notes",
                           "lookup_tariff_structure"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": 11785,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "discount_codes": {
        "title_he": "קודי הנחה",
        "title_en": "Discount / Exemption Codes",
        "category": "tariff",
        "source_xml": "tariff_extract/ExemptCustomsItems.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "discount_codes",
        "has_html": True,
        "html_file": "discount_codes.html",
        "searchable_via": ["search_tariff"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": 80,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    # ========================================================================
    # REGULATIONS
    # ========================================================================

    "framework_order": {
        "title_he": "צו מסגרת",
        "title_en": "Framework Order",
        "category": "regulation",
        "source_xml": "tariff_extract/AdditionRulesDetailsHistory.xml",
        "source_pdf": "FrameOrder.pdf",
        "python_module": "lib._framework_order_data",
        "python_const": "FRAMEWORK_ORDER_ARTICLES",
        "firestore_collection": "framework_order",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_framework_order"],
        "inline_renderable": True,
        "article_count": 33,
        "entry_count": 85,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "free_import_order": {
        "title_he": "צו יבוא חופשי",
        "title_en": "Free Import Order",
        "category": "regulation",
        "source_xml": None,
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "free_import_order",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["check_regulatory"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": 6121,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "free_export_order": {
        "title_he": "צו יצוא חופשי",
        "title_en": "Free Export Order",
        "category": "regulation",
        "source_xml": None,
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "free_export_order",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["check_regulatory"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": 979,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    # ========================================================================
    # PROCEDURES
    # ========================================================================

    "procedure_1": {
        "title_he": 'נוהל תש"ר (שחרור)',
        "title_en": "Procedure #1 -- Release (Tashar)",
        "category": "procedure",
        "procedure_number": 1,
        "source_xml": None,
        "source_pdf": "customs_procedures/Noal_1_Shichror_ACC.pdf",
        "python_module": "lib._procedures_data",
        "python_const": "PROCEDURES",
        "firestore_collection": "customs_procedures",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "procedure_2": {
        "title_he": "נוהל הערכה",
        "title_en": "Procedure #2 -- Valuation",
        "category": "procedure",
        "procedure_number": 2,
        "source_xml": None,
        "source_pdf": "customs_procedures/nohalHaraha2.pdf",
        "python_module": "lib._procedures_data",
        "python_const": "PROCEDURES",
        "firestore_collection": "customs_procedures",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "procedure_3": {
        "title_he": "נוהל סיווג טובין",
        "title_en": "Procedure #3 -- Classification",
        "category": "procedure",
        "procedure_number": 3,
        "source_xml": None,
        "source_pdf": None,
        "python_module": "lib._procedures_data",
        "python_const": "PROCEDURES",
        "firestore_collection": "customs_procedures",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "procedure_10": {
        "title_he": "נוהל יבוא אישי",
        "title_en": "Procedure #10 -- Personal Import",
        "category": "procedure",
        "procedure_number": 10,
        "source_xml": None,
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": None,
        "has_html": False,
        "html_file": None,
        "searchable_via": ["search_legal_knowledge"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "pending",
    },

    "procedure_25": {
        "title_he": "נוהל מצהרים",
        "title_en": "Procedure #25 -- Declarants",
        "category": "procedure",
        "procedure_number": 25,
        "source_xml": None,
        "source_pdf": "customs_procedures/Noal_25_Mzharim_ACC.pdf",
        "python_module": "lib._procedures_data",
        "python_const": "PROCEDURES",
        "firestore_collection": "customs_procedures",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "procedure_28": {
        "title_he": "נוהל מידע משפטי",
        "title_en": "Procedure #28 -- Legal Information",
        "category": "procedure",
        "procedure_number": 28,
        "source_xml": None,
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": None,
        "has_html": False,
        "html_file": None,
        "searchable_via": ["search_legal_knowledge"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "pending",
    },

    "approved_exporter": {
        "title_he": "נוהל יצואן מאושר",
        "title_en": "Approved Exporter Procedure",
        "category": "procedure",
        "source_xml": "FTA_eu_sahar-hutz_agreements_nohal-misim-approved-exporter.xml",
        "source_pdf": None,
        "python_module": "_approved_exporter_GENERATED",
        "python_const": "APPROVED_EXPORTER_PROCEDURE",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": 1,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "aeo_procedure": {
        "title_he": "נוהל גורם כלכלי מאושר",
        "title_en": "Authorized Economic Operator (AEO) Procedure",
        "category": "procedure",
        "source_xml": None,
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": None,
        "has_html": False,
        "html_file": None,
        "searchable_via": ["search_legal_knowledge"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "pending",
    },

    # ========================================================================
    # LAWS
    # ========================================================================

    "customs_ordinance": {
        "title_he": "פקודת המכס",
        "title_en": "Customs Ordinance",
        "category": "law",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "lib._ordinance_data",
        "python_const": "ORDINANCE_ARTICLES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": 311,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "customs_agents_law": {
        "title_he": "חוק סוכני המכס",
        "title_en": "Customs Agents Law",
        "category": "law",
        "source_xml": None,
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "partial",
    },

    # ========================================================================
    # REFORMS
    # ========================================================================

    "eu_reform": {
        "title_he": "רפורמת מה שטוב לאירופה",
        "title_en": "EU Reform -- What's Good for Europe",
        "category": "reform",
        "source_xml": "tariff_extract/EU_Reform_Information.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "us_reform": {
        "title_he": 'רפורמת מה שטוב לארה"ב',
        "title_en": "US Reform -- What's Good for USA",
        "category": "reform",
        "source_xml": None,
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    # ========================================================================
    # FTA AGREEMENTS (16 countries/blocs)
    # ========================================================================

    "fta_eu": {
        "title_he": "הסכם סחר חופשי ישראל-האיחוד האירופי",
        "title_en": "Israel-EU Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": True,
        "html_file": "fta_protocol4_eu.html",
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "EU",
        "origin_proof_type": "EUR.1",
        "supplements": [2, 3, 6, 7],
        "status": "complete",
    },

    "fta_uk": {
        "title_he": "הסכם סחר חופשי ישראל-בריטניה",
        "title_en": "Israel-UK Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "GB",
        "origin_proof_type": "EUR.1",
        "supplements": [2, 3],
        "status": "complete",
    },

    "fta_efta": {
        "title_he": 'הסכם סחר חופשי ישראל-אפט"א',
        "title_en": "Israel-EFTA Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "EFTA",
        "origin_proof_type": "EUR.1",
        "supplements": [2, 3, 7],
        "status": "complete",
    },

    "fta_turkey": {
        "title_he": "הסכם סחר חופשי ישראל-טורקיה",
        "title_en": "Israel-Turkey Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "TR",
        "origin_proof_type": "EUR.1",
        "supplements": [2, 3],
        "status": "complete",
    },

    "fta_jordan": {
        "title_he": "הסכם סחר חופשי ישראל-ירדן",
        "title_en": "Israel-Jordan Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "JO",
        "origin_proof_type": "EUR.1",
        "supplements": [2, 3],
        "status": "complete",
    },

    "fta_ukraine": {
        "title_he": "הסכם סחר חופשי ישראל-אוקראינה",
        "title_en": "Israel-Ukraine Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "UA",
        "origin_proof_type": "EUR.1",
        "supplements": [2, 3],
        "status": "complete",
    },

    "fta_usa": {
        "title_he": 'הסכם סחר חופשי ישראל-ארה"ב',
        "title_en": "Israel-USA Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "US",
        "origin_proof_type": "Invoice Declaration",
        "supplements": [2],
        "status": "complete",
    },

    "fta_canada": {
        "title_he": "הסכם סחר חופשי ישראל-קנדה",
        "title_en": "Israel-Canada Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "CA",
        "origin_proof_type": "Certificate of Origin",
        "supplements": [2],
        "status": "complete",
    },

    "fta_mexico": {
        "title_he": "הסכם סחר חופשי ישראל-מקסיקו",
        "title_en": "Israel-Mexico Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "MX",
        "origin_proof_type": "Certificate of Origin",
        "supplements": [2],
        "status": "complete",
    },

    "fta_colombia": {
        "title_he": "הסכם סחר חופשי ישראל-קולומביה",
        "title_en": "Israel-Colombia Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "CO",
        "origin_proof_type": "Certificate of Origin",
        "supplements": [2],
        "status": "complete",
    },

    "fta_panama": {
        "title_he": "הסכם סחר חופשי ישראל-פנמה",
        "title_en": "Israel-Panama Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "PA",
        "origin_proof_type": "Certificate of Origin",
        "supplements": [2],
        "status": "complete",
    },

    "fta_guatemala": {
        "title_he": "הסכם סחר חופשי ישראל-גואטמלה",
        "title_en": "Israel-Guatemala Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "GT",
        "origin_proof_type": "Certificate of Origin",
        "supplements": [2],
        "status": "complete",
    },

    "fta_korea": {
        "title_he": "הסכם סחר חופשי ישראל-קוריאה",
        "title_en": "Israel-Korea Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "KR",
        "origin_proof_type": "Certificate of Origin",
        "supplements": [2],
        "status": "complete",
    },

    "fta_mercosur": {
        "title_he": "הסכם סחר חופשי ישראל-מרקוסור",
        "title_en": "Israel-Mercosur Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "MERCOSUR",
        "origin_proof_type": "Certificate of Origin",
        "supplements": [2],
        "status": "complete",
    },

    "fta_uae": {
        "title_he": "הסכם סחר חופשי ישראל-איחוד האמירויות",
        "title_en": "Israel-UAE Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "AE",
        "origin_proof_type": "Certificate of Origin",
        "supplements": [2],
        "status": "complete",
    },

    "fta_vietnam": {
        "title_he": "הסכם סחר חופשי ישראל-וייטנאם",
        "title_en": "Israel-Vietnam Free Trade Agreement",
        "category": "fta",
        "source_xml": None,
        "source_pdf": None,
        "python_module": "_fta_all_countries",
        "python_const": "FTA_COUNTRIES",
        "firestore_collection": "legal_knowledge",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_fta", "search_legal_knowledge"],
        "inline_renderable": True,
        "article_count": None,
        "entry_count": None,
        "country_code": "VN",
        "origin_proof_type": "Certificate of Origin",
        "supplements": [2],
        "status": "complete",
    },

    # ========================================================================
    # SUPPLEMENTS (תוספות)
    # Note: supplements 11, 12, 13 DO NOT EXIST in the Israeli tariff system.
    # ========================================================================

    "supplement_1": {
        "title_he": "תוספת ראשונה",
        "title_en": "First Supplement -- Tariff Schedule",
        "category": "supplement",
        "source_xml": "tariff_extract/TradeAgreement.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "supplement_2": {
        "title_he": "תוספת שנייה -- הנחות WTO ושיעורי העדפה",
        "title_en": "Second Supplement -- WTO Concessions and Preferential Rates",
        "category": "supplement",
        "source_xml": "tariff_extract/SecondAddition.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "supplement_3": {
        "title_he": "תוספת שלישית -- שיעורים כבולים WTO",
        "title_en": "Third Supplement -- WTO Bound Rates",
        "category": "supplement",
        "source_xml": "tariff_extract/ThirdAddition.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "supplement_4": {
        "title_he": "תוספת רביעית -- הוראות מיוחדות",
        "title_en": "Fourth Supplement -- Special Provisions",
        "category": "supplement",
        "source_xml": "tariff_extract/TradeAgreement.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "supplement_5": {
        "title_he": "תוספת חמישית -- הוראות נוספות",
        "title_en": "Fifth Supplement -- Additional Provisions",
        "category": "supplement",
        "source_xml": "tariff_extract/TradeAgreement.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "supplement_6": {
        "title_he": "תוספת שישית -- לוחות צו מסגרת",
        "title_en": "Sixth Supplement -- Framework Order Schedules",
        "category": "supplement",
        "source_xml": "tariff_extract/TradeAgreement.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "supplement_7": {
        "title_he": "תוספת שביעית -- לוחות הסכמי סחר",
        "title_en": "Seventh Supplement -- Trade Agreement Schedules",
        "category": "supplement",
        "source_xml": "tariff_extract/TradeAgreement.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "supplement_8": {
        "title_he": "תוספת שמינית -- הוראות סחר נוספות",
        "title_en": "Eighth Supplement -- Additional Trade Provisions",
        "category": "supplement",
        "source_xml": "tariff_extract/TradeAgreement.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "supplement_9": {
        "title_he": "תוספת תשיעית -- הוראות מוצר ספציפיות",
        "title_en": "Ninth Supplement -- Specific Product Provisions",
        "category": "supplement",
        "source_xml": "tariff_extract/TradeAgreement.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "supplement_10": {
        "title_he": "תוספת עשירית -- הוראות ספציפיות נוספות",
        "title_en": "Tenth Supplement -- Additional Specific Provisions",
        "category": "supplement",
        "source_xml": "tariff_extract/TradeAgreement.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    # NOTE: supplements 11, 12, 13 DO NOT EXIST in the Israeli tariff system.

    "supplement_14": {
        "title_he": "תוספת ארבע עשרה -- הוראות רגולטוריות",
        "title_en": "Fourteenth Supplement -- Regulatory Provisions",
        "category": "supplement",
        "source_xml": "tariff_extract/TradeAgreement.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "supplement_15": {
        "title_he": "תוספת חמש עשרה -- רגולציה נוספת",
        "title_en": "Fifteenth Supplement -- Additional Regulatory",
        "category": "supplement",
        "source_xml": "tariff_extract/TradeAgreement.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "supplement_16": {
        "title_he": "תוספת שש עשרה -- הוראות נוספות",
        "title_en": "Sixteenth Supplement -- Further Provisions",
        "category": "supplement",
        "source_xml": "tariff_extract/TradeAgreement.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "supplement_17": {
        "title_he": "תוספת שבע עשרה -- הוראות משלימות",
        "title_en": "Seventeenth Supplement -- Supplementary Provisions",
        "category": "supplement",
        "source_xml": "tariff_extract/TradeAgreement.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    # Named additions (also supplement-category)

    "second_addition": {
        "title_he": "תוספת שניה",
        "title_en": "Second Addition (SecondAddition.xml)",
        "category": "supplement",
        "source_xml": "tariff_extract/SecondAddition.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },

    "third_addition": {
        "title_he": "תוספת שלישית",
        "title_en": "Third Addition (ThirdAddition.xml)",
        "category": "supplement",
        "source_xml": "tariff_extract/ThirdAddition.xml",
        "source_pdf": None,
        "python_module": None,
        "python_const": None,
        "firestore_collection": "tariff_structure",
        "has_html": False,
        "html_file": None,
        "searchable_via": ["lookup_tariff_structure", "lookup_framework_order"],
        "inline_renderable": False,
        "article_count": None,
        "entry_count": None,
        "country_code": None,
        "origin_proof_type": None,
        "supplements": None,
        "status": "complete",
    },
}


# ============================================================================
# INDEXES — built once at import time
# ============================================================================

_CATEGORY_INDEX: Dict[str, List[str]] = {}
_COUNTRY_INDEX: Dict[str, str] = {}  # country_code -> doc_id

for _doc_id, _doc in DOCUMENT_REGISTRY.items():
    _cat = _doc["category"]
    _CATEGORY_INDEX.setdefault(_cat, []).append(_doc_id)
    if _doc.get("country_code"):
        _COUNTRY_INDEX[_doc["country_code"]] = _doc_id

# Country code aliases for lookup convenience (ISO 2-letter, common names)
_COUNTRY_ALIASES: Dict[str, str] = {
    # EU member states -> EU FTA
    "DE": "EU", "FR": "EU", "IT": "EU", "ES": "EU", "NL": "EU",
    "BE": "EU", "AT": "EU", "PL": "EU", "CZ": "EU", "RO": "EU",
    "PT": "EU", "GR": "EU", "SE": "EU", "DK": "EU", "FI": "EU",
    "IE": "EU", "HU": "EU", "SK": "EU", "HR": "EU", "BG": "EU",
    "LT": "EU", "SI": "EU", "LV": "EU", "EE": "EU", "CY": "EU",
    "LU": "EU", "MT": "EU",
    # EFTA members
    "CH": "EFTA", "NO": "EFTA", "IS": "EFTA", "LI": "EFTA",
    # Mercosur members
    "BR": "MERCOSUR", "AR": "MERCOSUR", "UY": "MERCOSUR", "PY": "MERCOSUR",
    # UK alias
    "UK": "GB",
}

# Section -> chapter ranges for HS code relevance lookups
_TARIFF_SECTIONS: Dict[str, List[range]] = {
    "I":     [range(1, 6)],
    "II":    [range(6, 15)],
    "III":   [range(15, 16)],
    "IV":    [range(16, 25)],
    "V":     [range(25, 28)],
    "VI":    [range(28, 39)],
    "VII":   [range(39, 41)],
    "VIII":  [range(41, 44)],
    "IX":    [range(44, 47)],
    "X":     [range(47, 50)],
    "XI":    [range(50, 64)],
    "XII":   [range(64, 68)],
    "XIII":  [range(68, 71)],
    "XIV":   [range(71, 72)],
    "XV":    [range(72, 84)],
    "XVI":   [range(84, 86)],
    "XVII":  [range(86, 90)],
    "XVIII": [range(90, 93)],
    "XIX":   [range(93, 94)],
    "XX":    [range(94, 97)],
    "XXI":   [range(97, 98)],
    "XXII":  [range(98, 100)],
}


def _chapter_for_hs(hs_code: str) -> Optional[int]:
    """Extract chapter number (1-99) from an HS code string."""
    digits = "".join(c for c in (hs_code or "") if c.isdigit())
    if len(digits) >= 2:
        ch = int(digits[:2])
        if 1 <= ch <= 99:
            return ch
    return None


def _section_for_chapter(chapter: int) -> Optional[str]:
    """Return the tariff section (Roman numeral) for a chapter number."""
    for section_id, ranges in _TARIFF_SECTIONS.items():
        for r in ranges:
            if chapter in r:
                return section_id
    return None


def _resolve_country_code(code: str) -> Optional[str]:
    """Resolve a country code (ISO or alias) to the FTA country code used in the index."""
    code_upper = (code or "").strip().upper()
    if code_upper in _COUNTRY_INDEX:
        return code_upper
    alias = _COUNTRY_ALIASES.get(code_upper)
    if alias and alias in _COUNTRY_INDEX:
        return alias
    return None


# ============================================================================
# PUBLIC API
# ============================================================================

def get_document(doc_id: str) -> Optional[dict]:
    """Return the registry entry for a document, or None if not found."""
    entry = DOCUMENT_REGISTRY.get(doc_id)
    if entry is None:
        return None
    result = dict(entry)
    result["doc_id"] = doc_id
    return result


def get_documents_by_category(category: str) -> List[dict]:
    """Return all documents in a given category.

    Valid categories: tariff, regulation, procedure, law, fta, supplement, reform
    """
    doc_ids = _CATEGORY_INDEX.get(category, [])
    results = []
    for doc_id in doc_ids:
        entry = dict(DOCUMENT_REGISTRY[doc_id])
        entry["doc_id"] = doc_id
        results.append(entry)
    return results


def get_fta_for_country(country_code: str) -> Optional[dict]:
    """Look up the FTA document for a country code (ISO 2-letter or alias).

    Handles EU member states (DE -> EU FTA), EFTA members (CH -> EFTA FTA),
    Mercosur members (BR -> MERCOSUR FTA), and UK alias (UK -> GB).

    Returns the full document entry with doc_id, or None.
    """
    resolved = _resolve_country_code(country_code)
    if resolved is None:
        return None
    doc_id = _COUNTRY_INDEX.get(resolved)
    if doc_id is None:
        return None
    return get_document(doc_id)


def get_relevant_documents(
    hs_code: Optional[str] = None,
    origin: Optional[str] = None,
    direction: Optional[str] = None,
) -> List[dict]:
    """Find documents relevant to a classification scenario.

    Args:
        hs_code: HS code string (e.g., "8507600000"). Used to determine
                 which tariff section, chapter notes, and supplements apply.
        origin: Country code or name for FTA lookup (e.g., "DE", "EU", "turkey").
        direction: "import" or "export" to filter regulatory documents.

    Returns:
        List of relevant document entries, each with a "doc_id" key.
    """
    results: List[dict] = []
    seen: set = set()

    def _add(doc_id: str) -> None:
        if doc_id not in seen and doc_id in DOCUMENT_REGISTRY:
            seen.add(doc_id)
            entry = dict(DOCUMENT_REGISTRY[doc_id])
            entry["doc_id"] = doc_id
            results.append(entry)

    # Always relevant: tariff book, customs ordinance, framework order
    _add("tariff_book")
    _add("customs_ordinance")
    _add("framework_order")

    # HS code -> section-specific supplements and chapter notes
    if hs_code:
        chapter = _chapter_for_hs(hs_code)
        if chapter is not None:
            _add("discount_codes")
            # All supplements are potentially relevant for any HS code
            for sup_id in _CATEGORY_INDEX.get("supplement", []):
                _add(sup_id)

    # Direction-specific regulatory documents
    if direction:
        direction_lower = direction.lower()
        if direction_lower == "import":
            _add("free_import_order")
            _add("procedure_1")
            _add("procedure_2")
            _add("procedure_3")
            _add("procedure_10")
        elif direction_lower == "export":
            _add("free_export_order")
            _add("approved_exporter")
            _add("aeo_procedure")
    else:
        # No direction specified -- include both
        _add("free_import_order")
        _add("free_export_order")

    # Origin country -> FTA
    if origin:
        fta = get_fta_for_country(origin)
        if fta:
            _add(fta["doc_id"])

    # Reforms always relevant for import classification
    _add("eu_reform")
    _add("us_reform")

    # Procedures relevant to any classification
    _add("procedure_3")
    _add("procedure_25")

    return results


def format_citation(
    doc_id: str,
    article: Optional[str] = None,
    section: Optional[str] = None,
) -> str:
    """Format a human-readable Hebrew citation string.

    Examples:
        format_citation("customs_ordinance", article="130")
        -> "פקודת המכס, סעיף 130"

        format_citation("framework_order", article="16", section="EU")
        -> "צו מסגרת, סעיף 16 (EU)"

        format_citation("fta_eu")
        -> "הסכם סחר חופשי ישראל-האיחוד האירופי"

        format_citation("procedure_3")
        -> "נוהל סיווג טובין"

        format_citation("tariff_book", section="84.71")
        -> "תעריף המכס, פרט 84.71"
    """
    doc = DOCUMENT_REGISTRY.get(doc_id)
    if doc is None:
        return doc_id

    title = doc["title_he"]
    parts = [title]

    if article:
        parts.append(f"סעיף {article}")
    elif section:
        if doc["category"] == "tariff":
            parts.append(f"פרט {section}")
        else:
            parts.append(f"חלק {section}")

    citation = ", ".join(parts)

    # Add parenthetical qualifier if section is provided alongside article
    if article and section:
        citation = f"{title}, סעיף {article} ({section})"

    return f"{citation}"


def get_all_document_ids() -> List[str]:
    """Return all registered document IDs in registry order."""
    return list(DOCUMENT_REGISTRY.keys())


def get_supplement_documents() -> List[dict]:
    """Return all supplement documents in numerical order.

    Note: supplements 11, 12, 13 do not exist and are not included.
    """
    sup_ids = _CATEGORY_INDEX.get("supplement", [])

    def _sort_key(doc_id: str) -> int:
        """Extract numeric part for sorting: supplement_2 -> 2, second_addition -> 200."""
        if doc_id.startswith("supplement_"):
            try:
                return int(doc_id.split("_")[1])
            except (IndexError, ValueError):
                return 999
        if doc_id == "second_addition":
            return 200
        if doc_id == "third_addition":
            return 201
        return 998

    sorted_ids = sorted(sup_ids, key=_sort_key)
    results = []
    for doc_id in sorted_ids:
        entry = dict(DOCUMENT_REGISTRY[doc_id])
        entry["doc_id"] = doc_id
        results.append(entry)
    return results


def search_registry(keyword: str) -> List[dict]:
    """Search all documents by keyword in Hebrew and English titles.

    Also matches against category, country_code, and origin_proof_type fields.
    Case-insensitive for English, exact substring for Hebrew.

    Args:
        keyword: search term.

    Returns:
        List of matching document entries, each with a "doc_id" key.
    """
    if not keyword or not keyword.strip():
        return []

    kw = keyword.strip().lower()
    results: List[dict] = []
    seen: set = set()

    for doc_id, doc in DOCUMENT_REGISTRY.items():
        if doc_id in seen:
            continue

        matched = False

        # Check Hebrew title (substring, case-sensitive for Hebrew)
        title_he = doc.get("title_he", "")
        if kw in title_he:
            matched = True

        # Check English title (case-insensitive)
        if not matched:
            title_en = doc.get("title_en", "")
            if kw in title_en.lower():
                matched = True

        # Check category
        if not matched:
            if kw == doc.get("category", ""):
                matched = True

        # Check country_code
        if not matched:
            cc = doc.get("country_code")
            if cc and kw == cc.lower():
                matched = True

        # Check origin_proof_type
        if not matched:
            proof = doc.get("origin_proof_type", "")
            if proof and kw in proof.lower():
                matched = True

        # Check doc_id itself
        if not matched:
            if kw in doc_id:
                matched = True

        if matched:
            seen.add(doc_id)
            entry = dict(doc)
            entry["doc_id"] = doc_id
            results.append(entry)

    return results


# ============================================================================
# VALIDATION (for tests)
# ============================================================================

VALID_CATEGORIES = {"tariff", "regulation", "procedure", "law", "fta", "supplement", "reform"}
VALID_STATUSES = {"complete", "partial", "pending", "placeholder"}
NONEXISTENT_SUPPLEMENTS = {11, 12, 13}
