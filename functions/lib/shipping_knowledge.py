"""
Shipping Knowledge — Carrier registry, BIC/ISO 6346 container codes,
BL field mappings, FIATA document types, and IATA AWB reference.

Sources:
  - BIC (bic-code.org) — ISO 6346 container identification, size/type codes, check digit
  - Carrier websites — BL formats, terms and conditions, SCAC codes
  - FIATA (fiata.org) — Transport document standards
  - IATA — AWB format and airline designators

This module provides DATA ONLY — no business logic changes.
Used by: tracker.py (BOL prefix matching), doc_reader.py (document identification),
         librarian_index.py (knowledge indexing), self_learning.py (template context).
"""

from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════
#  CARRIER REGISTRY — All major ocean carriers
# ═══════════════════════════════════════════════════════════
#
# Each carrier entry is structured for Firestore seeding into
# the 'shipping_lines' collection, which tracker.py reads via
# _load_bol_prefixes(db).

CARRIERS = {
    "zim": {
        "name": "ZIM Integrated Shipping Services",
        "country": "Israel",
        "headquarters": "Haifa, Israel",
        "scac": "ZIMU",
        "bol_prefixes": ["ZIMU"],
        "bol_pattern": r"ZIMU[A-Z]{3}\d{4,8}",
        "container_prefixes": [
            "ZIMU", "ZCSU", "ZMOU", "JXLU", "JZPU",
            "GSLU", "GLSU", "GSTU", "ZBXU", "ZCLU", "ZWFU"
        ],
        "email_domains": ["zim.com"],
        "terms_url": "https://www.zim.com/help/bl-terms-and-conditions",
        "terms_document": "ZIC-01/12",
        "governing_law": "Hague-Visby Rules",
        "jurisdiction": "Haifa Maritime Court, Israel",
        "liability_regime": {
            "international": "Hague-Visby Rules",
            "us_trade": "US COGSA",
            "limit_per_package_sdr": 666.67,
            "limit_per_kg_sdr": 2.0,
        },
        "ebl_platform": "WaveBL",
        "general_average": "York-Antwerp Rules 1994",
        "time_bar_months": 12,
    },
    "maersk": {
        "name": "Maersk A/S",
        "country": "Denmark",
        "headquarters": "Copenhagen, Denmark",
        "scac": "MAEU",
        "bol_prefixes": ["MAEU", "MAEI", "MRKU", "SEAU", "SAFM", "SUDU", "MCPU"],
        "bol_pattern": r"MAEU\d{9}",
        "container_prefixes": [
            "MSKU", "MRKU", "MAEU", "MALU", "MCRU",
            "APMU", "CSSU", "GCDU", "MGBU", "MHHU",
            "MMAU", "MNBU", "MRSU", "MWCU", "PONU",
            "SEAU", "TCLU", "SUDU", "GESU", "SFMU"
        ],
        "email_domains": ["maersk.com"],
        "terms_url": "https://terms.maersk.com/carriage",
        "governing_law": "Hague-Visby Rules / Hague Rules",
        "jurisdiction": "Per trade lane",
        "liability_regime": {
            "international": "Hague-Visby Rules",
            "us_trade": "US COGSA",
            "outside_us": "Hague Rules (Articles 1-8)",
            "limit_per_package_sdr": 666.67,
            "limit_per_kg_sdr": 2.0,
            "limit_us_per_package_usd": 500,
        },
        "ebl_platform": "Maersk.com BL Transfer",
        "general_average": "York-Antwerp Rules",
        "time_bar_months": 12,
        "notice_of_loss_days": 3,
    },
    "msc": {
        "name": "Mediterranean Shipping Company",
        "country": "Switzerland",
        "headquarters": "Geneva, Switzerland",
        "scac": "MSCU",
        "bol_prefixes": ["MEDU", "MSCU"],
        "bol_pattern": r"MEDU(?:RS)?\d{5,10}",
        "container_prefixes": [
            "MSCU", "MEDU", "MSDU", "GESU", "IPXU",
            "SEGU", "TRHU", "GATU", "CAIU", "CMAU",
            "INBU", "SZLU", "TTNU", "CLHU", "FSCU",
            "MOAU", "HJCU"
        ],
        "email_domains": ["msc.com"],
        "terms_url": "https://www.msc.com/en/legal/bill-of-lading",
        "governing_law": "Hague-Visby Rules",
        "jurisdiction": "High Court of London, England",
        "liability_regime": {
            "international": "Hague-Visby Rules",
            "us_trade": "US COGSA",
            "limit_per_package_sdr": 666.67,
            "limit_per_kg_sdr": 2.0,
        },
        "ebl_platform": "WaveBL / MSC eBL",
        "general_average": "York-Antwerp Rules",
        "time_bar_months": 12,
    },
    "evergreen": {
        "name": "Evergreen Marine Corporation",
        "country": "Taiwan",
        "headquarters": "Taoyuan City, Taiwan",
        "scac": "EGLV",
        "bol_prefixes": ["EGLV"],
        "bol_pattern": r"EGLV[A-Z0-9]{8,12}",
        "container_prefixes": [
            "EGHU", "EISU", "EMCU", "EGSU", "EITU"
        ],
        "email_domains": ["evergreen-line.com", "evergreen-marine.com"],
        "terms_url": "https://www.evergreen-line.com/toc",
        "governing_law": "Hague-Visby Rules",
        "jurisdiction": "London, England",
        "liability_regime": {
            "international": "Hague-Visby Rules",
            "us_trade": "US COGSA",
            "limit_per_package_sdr": 666.67,
            "limit_per_kg_sdr": 2.0,
        },
        "ebl_platform": "ShipmentLink i-B/L",
        "general_average": "York-Antwerp Rules",
        "time_bar_months": 12,
    },
    "hapag_lloyd": {
        "name": "Hapag-Lloyd AG",
        "country": "Germany",
        "headquarters": "Hamburg, Germany",
        "scac": "HLCU",
        "bol_prefixes": ["HLCU", "HLXU"],
        "bol_pattern": r"HLCU[A-Z0-9]{8,12}",
        "container_prefixes": [
            "HLCU", "HLXU", "CPSU", "DAYU",
            "DHDU", "GESU", "HJCU", "ITAU",
            "KNLU", "OOLU", "PRGU", "SUDU",
            "TCKU", "TRIU", "UACU", "UASC",
            "DHLU", "DLCU"
        ],
        "email_domains": ["hapag-lloyd.com", "hlag.com"],
        "terms_url": "https://www.hapag-lloyd.com/en/legal/bill-of-lading.html",
        "terms_document": "LV 01/24",
        "governing_law": "Hague-Visby Rules",
        "jurisdiction": "Hamburg, Germany or London, England",
        "liability_regime": {
            "international": "Hague-Visby Rules",
            "us_trade": "US COGSA",
            "limit_per_package_sdr": 666.67,
            "limit_per_kg_sdr": 2.0,
        },
        "ebl_platform": "WAVE BL / essDOCS CargoDocs",
        "general_average": "York-Antwerp Rules",
        "time_bar_months": 12,
    },
    "one": {
        "name": "Ocean Network Express",
        "country": "Japan",
        "headquarters": "Singapore (operations), Tokyo (parent)",
        "scac": "ONEY",
        "bol_prefixes": ["ONEY"],
        "bol_pattern": r"ONEY[A-Z0-9]{10,12}",
        "container_prefixes": [
            "ONEU", "TCLU", "TCKU", "NYKU", "MOLU", "KKLU"
        ],
        "legacy_note": "Formed from NYK + MOL + K Line merger (2016). Legacy container prefixes still in use.",
        "email_domains": ["one-line.com"],
        "terms_url": "https://www.one-line.com/en/standard-page/b/l-terms",
        "governing_law": "Singapore law",
        "jurisdiction": "Singapore High Court",
        "liability_regime": {
            "international": "Hague-Visby Rules",
            "us_trade": "US COGSA",
            "limit_per_package_sdr": 666.67,
            "limit_per_kg_sdr": 2.0,
        },
        "ebl_platform": "essDOCS CargoDocs / WAVE BL",
        "general_average": "York-Antwerp Rules 1994",
        "time_bar_months": 12,
    },
    "cosco": {
        "name": "COSCO Shipping Lines Co., Ltd.",
        "country": "China",
        "headquarters": "Shanghai, China",
        "scac": "COSU",
        "bol_prefixes": ["COSU", "COAU"],
        "bol_pattern": r"(?:COSU|COAU)\d{8,12}",
        "container_prefixes": [
            "CCLU", "CSLU", "CSNU", "CBHU", "CSGU",
            "VECU", "TEMU", "COHU", "CXDU", "TCNU", "TGHU", "FSCU"
        ],
        "legacy_note": "Merged with China Shipping Container Lines (CSCL) in 2016.",
        "email_domains": ["cosco.com", "coscoshipping.com", "coscon.com"],
        "terms_url": "https://lines.coscoshipping.com/home/HelpCenter/business/BillConditions",
        "governing_law": "Hague-Visby Rules",
        "jurisdiction": "Per trade route / Chinese Maritime Law",
        "liability_regime": {
            "international": "Hague-Visby Rules",
            "limit_per_package_usd": 500,
            "limit_per_kg_usd": 2.0,
        },
        "ebl_platform": "GSBN blockchain",
        "general_average": "York-Antwerp Rules",
        "time_bar_months": 12,
    },
    "yang_ming": {
        "name": "Yang Ming Marine Transport Corp.",
        "country": "Taiwan",
        "headquarters": "Keelung, Taiwan",
        "scac": "YMJA",
        "scac_legacy": "YMLU",
        "scac_change_date": "2023-10-01",
        "bol_prefixes": ["YMJA", "YMLU", "YMPR"],
        "bol_pattern": r"(?:YMJA|YMLU|YMPR)[A-Z0-9]{8,12}",
        "container_prefixes": ["YMLU", "YMMU"],
        "email_domains": ["yangming.com"],
        "terms_url": "https://www.yangming.com/service/Useful_Info/BL_Clause.aspx",
        "governing_law": "English law",
        "jurisdiction": "English courts (fallback: port of loading/discharge)",
        "liability_regime": {
            "international": "Hague-Visby Rules",
            "us_trade": "US COGSA",
        },
        "ebl_platform": "DCSA standards-based",
        "general_average": "York-Antwerp Rules",
        "time_bar_months": 12,
    },
    "oocl": {
        "name": "Orient Overseas Container Line",
        "country": "Hong Kong",
        "headquarters": "Hong Kong",
        "scac": "OOLU",
        "bol_prefixes": ["OOLU"],
        "bol_pattern": r"OOLU\d{8,12}",
        "container_prefixes": ["OOLU", "OOCU"],
        "parent_note": "Owned by COSCO Shipping Holdings since 2018. Operates independently.",
        "email_domains": ["oocl.com"],
        "terms_url": "https://www.oocl.com/eng/resourcecenter/blterms",
        "governing_law": "Hong Kong law",
        "jurisdiction": "High Court of Hong Kong",
        "liability_regime": {
            "international": "Hague-Visby Rules",
            "us_trade": "US COGSA",
        },
        "ebl_platform": "IQAX (GSBN) / ICE CargoDocs",
        "general_average": "York-Antwerp Rules",
        "time_bar_months": 9,
        "delay_liability": False,
    },
}


# ═══════════════════════════════════════════════════════════
#  BIC / ISO 6346 — Container Identification System
# ═══════════════════════════════════════════════════════════
#
# Source: bic-code.org, ISO 6346:2022
#
# Container number: 11 characters = XXXU NNNNNN C
#   Characters 1-3: Owner code (registered with BIC)
#   Character 4: Equipment category (U=freight, J=detachable, Z=trailer)
#   Characters 5-10: Serial number (6 digits)
#   Character 11: Check digit (ISO 6346 algorithm)

BIC_EQUIPMENT_CATEGORIES = {
    "U": "Freight container",
    "J": "Detachable freight container-related equipment",
    "Z": "Trailer and chassis",
}

# ISO 6346 check digit letter values — multiples of 11 are skipped
BIC_CHECK_DIGIT_VALUES = {
    "A": 10, "B": 12, "C": 13, "D": 14, "E": 15,
    "F": 16, "G": 17, "H": 18, "I": 19, "J": 20,
    "K": 21, "L": 23, "M": 24, "N": 25, "O": 26,
    "P": 27, "Q": 28, "R": 29, "S": 30, "T": 31,
    "U": 32, "V": 34, "W": 35, "X": 36, "Y": 37, "Z": 38,
    "0": 0, "1": 1, "2": 2, "3": 3, "4": 4,
    "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
}

# Container size codes — ISO 6346 first character (length)
BIC_SIZE_LENGTH = {
    "2": "20 ft (6.058 m)",
    "4": "40 ft (12.192 m)",
    "5": "45 ft (13.716 m)",
    "L": "45 ft (13.716 m)",
    "M": "48 ft (14.630 m)",
    "N": "49 ft (14.935 m)",
    "P": "53 ft (16.154 m)",
}

# Container size codes — ISO 6346 second character (height + width)
BIC_SIZE_HEIGHT = {
    "0": {"height": "<=8 ft (<=2438 mm)", "width": "8 ft (2438 mm)"},
    "2": {"height": "8 ft 6 in (2591 mm)", "width": "8 ft (2438 mm)"},   # Standard
    "4": {"height": "<=9 ft (<=2743 mm)", "width": "8 ft (2438 mm)"},
    "5": {"height": "9 ft 6 in (2896 mm)", "width": "8 ft (2438 mm)"},   # High Cube
    "6": {"height": ">=9 ft 6 in (>=2896 mm)", "width": "8 ft (2438 mm)"},
    "8": {"height": "<=8 ft (<=2438 mm)", "width": ">8 ft (>2438 mm)"},  # Wide
    "9": {"height": "8 ft 6 in (2591 mm)", "width": ">8 ft (>2438 mm)"},
}

# Container type codes — ISO 6346 third character (type group)
BIC_TYPE_GROUP = {
    "G": "General purpose (dry)",
    "V": "Ventilated",
    "B": "Bulk (dry)",
    "S": "Named cargo / special (livestock, auto, fish)",
    "R": "Refrigerated (reefer)",
    "H": "Thermal (insulated, removable equipment)",
    "U": "Open top",
    "P": "Platform / flat rack",
    "T": "Tank (non-pressurized)",
    "K": "Tank (pressurized)",
    "N": "Tank (hopper)",
    "W": "Foldable / collapsible",
    "A": "Air/surface (multi-modal)",
}

# Common container size/type codes seen in practice
COMMON_CONTAINER_TYPES = {
    "20GP": "20' Standard Dry",
    "20DV": "20' Standard Dry (alternate code)",
    "20RF": "20' Reefer",
    "20OT": "20' Open Top",
    "20FR": "20' Flat Rack",
    "20TK": "20' Tank",
    "40GP": "40' Standard Dry",
    "40DV": "40' Standard Dry (alternate code)",
    "40HC": "40' High Cube",
    "40RF": "40' Reefer",
    "40RH": "40' Reefer High Cube",
    "40OT": "40' Open Top",
    "40FR": "40' Flat Rack",
    "40TK": "40' Tank",
    "45HC": "45' High Cube",
    "22G1": "20' Standard Dry (ISO code)",
    "42G1": "40' Standard Dry (ISO code)",
    "45G1": "40' High Cube Dry (ISO code)",
    "42R1": "40' Standard Reefer (ISO code)",
    "45R1": "40' High Cube Reefer (ISO code)",
    "42U1": "40' Open Top (ISO code)",
    "42P1": "40' Flat Rack fixed (ISO code)",
    "42P3": "40' Flat Rack collapsible (ISO code)",
    "22T1": "20' Tank (ISO code)",
}

# BIC Facility Code format: XX NNN YYYY
# XX = country (ISO 3166-1), NNN = location (UN/LOCODE), YYYY = facility
# 17,000+ facilities in 160 countries
# API: bic-code.org/api/
# BoxTech API: app.bic-boxtech.org/api/v2.0/container/{container_number}


def validate_container_number(number):
    """
    Validate a container number per ISO 6346 / BIC standard.
    Returns dict with: valid (bool), owner_code, category, serial, check_digit, error.

    Does NOT look up the owner code against BIC registry — only validates format + check digit.
    """
    if not number or not isinstance(number, str):
        return {"valid": False, "error": "empty or not a string"}

    clean = number.upper().replace(" ", "").replace("-", "")

    if len(clean) != 11:
        return {"valid": False, "error": f"length {len(clean)}, expected 11"}

    owner_code = clean[:3]
    category = clean[3]
    serial = clean[4:10]
    check_digit = clean[10]

    if not owner_code.isalpha():
        return {"valid": False, "error": "owner code must be 3 letters"}
    if category not in ("U", "J", "Z"):
        return {"valid": False, "error": f"equipment category '{category}' must be U, J, or Z"}
    if not serial.isdigit():
        return {"valid": False, "error": "serial must be 6 digits"}
    if not check_digit.isdigit():
        return {"valid": False, "error": "check digit must be a digit"}

    # Calculate check digit per ISO 6346
    total = 0
    for i, ch in enumerate(clean[:10]):
        val = BIC_CHECK_DIGIT_VALUES.get(ch)
        if val is None:
            return {"valid": False, "error": f"invalid character '{ch}' at position {i}"}
        total += val * (2 ** i)

    calculated = total % 11
    if calculated == 10:
        calculated = 0

    if str(calculated) != check_digit:
        return {
            "valid": False,
            "error": f"check digit mismatch: expected {calculated}, got {check_digit}",
            "owner_code": owner_code,
            "category": BIC_EQUIPMENT_CATEGORIES.get(category, category),
            "serial": serial,
        }

    return {
        "valid": True,
        "owner_code": owner_code,
        "category": BIC_EQUIPMENT_CATEGORIES.get(category, category),
        "serial": serial,
        "check_digit": check_digit,
        "full": clean,
    }


def identify_carrier_from_container(container_number):
    """Identify the carrier from a container owner prefix.
    Returns carrier_id or None."""
    if not container_number or len(container_number) < 4:
        return None
    prefix = container_number[:4].upper()
    for carrier_id, carrier in CARRIERS.items():
        if prefix in carrier.get("container_prefixes", []):
            return carrier_id
    return None


def identify_carrier_from_bol(bol_number):
    """Identify the carrier from a BOL prefix.
    Returns carrier_id or None."""
    if not bol_number or len(bol_number) < 4:
        return None
    bol_upper = bol_number.upper()
    for carrier_id, carrier in CARRIERS.items():
        for prefix in carrier.get("bol_prefixes", []):
            if bol_upper.startswith(prefix):
                return carrier_id
    return None


# ═══════════════════════════════════════════════════════════
#  UNIVERSAL BL FIELDS — Common across all ocean carriers
# ═══════════════════════════════════════════════════════════
#
# These fields appear on every ocean Bill of Lading regardless of carrier.
# Used for document extraction templates and OCR field mapping.

UNIVERSAL_BL_FIELDS = {
    # Header / Identification
    "bl_number": {"label": "B/L Number", "type": "string", "required": True},
    "booking_number": {"label": "Booking No.", "type": "string", "required": False},
    "export_references": {"label": "Export References", "type": "string", "required": False},

    # Parties
    "shipper": {"label": "Shipper/Exporter", "type": "text_block", "required": True},
    "consignee": {"label": "Consignee", "type": "text_block", "required": True,
                  "note": "May be 'TO ORDER' or 'TO ORDER OF [bank]' for negotiable BLs"},
    "notify_party": {"label": "Notify Party", "type": "text_block", "required": True},
    "also_notify": {"label": "Also Notify", "type": "text_block", "required": False},

    # Routing
    "place_of_receipt": {"label": "Place of Receipt", "type": "string", "required": False,
                         "note": "If filled, indicates combined/multimodal transport"},
    "port_of_loading": {"label": "Port of Loading", "type": "string", "required": True},
    "vessel_name": {"label": "Ocean Vessel", "type": "string", "required": True},
    "voyage_number": {"label": "Voyage No.", "type": "string", "required": True},
    "port_of_discharge": {"label": "Port of Discharge", "type": "string", "required": True},
    "place_of_delivery": {"label": "Place of Delivery", "type": "string", "required": False,
                          "note": "If filled, indicates combined/multimodal transport"},

    # Cargo (repeating per container line)
    "container_number": {"label": "Container No.", "type": "string", "required": True,
                         "format": "ISO 6346: 4 letters + 7 digits"},
    "seal_number": {"label": "Seal No.", "type": "string", "required": True},
    "marks_and_numbers": {"label": "Marks and Numbers", "type": "text_block", "required": False},
    "number_of_packages": {"label": "No. of Packages", "type": "integer", "required": True},
    "kind_of_packages": {"label": "Kind of Packages", "type": "string", "required": True},
    "description_of_goods": {"label": "Description of Goods", "type": "text_block", "required": True},
    "gross_weight_kg": {"label": "Gross Weight (KGS)", "type": "decimal", "required": True},
    "measurement_cbm": {"label": "Measurement (CBM)", "type": "decimal", "required": False},
    "hs_code": {"label": "HS Code", "type": "string", "required": False},

    # Freight
    "freight_prepaid_collect": {"label": "Freight Prepaid/Collect", "type": "enum",
                                "values": ["PREPAID", "COLLECT"], "required": True},
    "freight_payable_at": {"label": "Freight Payable at", "type": "string", "required": False},

    # Issuance
    "place_of_issue": {"label": "Place of Issue", "type": "string", "required": True},
    "date_of_issue": {"label": "Date of Issue", "type": "date", "required": True},
    "shipped_on_board_date": {"label": "Shipped on Board Date", "type": "date", "required": True},
    "number_of_originals": {"label": "No. of Original B/Ls", "type": "integer", "required": True,
                            "note": "Typically 3"},
}

# Standard BL clauses/notations for OCR detection
BL_STANDARD_NOTATIONS = {
    "shipped_on_board": ["SHIPPED ON BOARD", "LADEN ON BOARD", "LOADED ON BOARD"],
    "clean": ["CLEAN ON BOARD", "RECEIVED IN APPARENT GOOD ORDER"],
    "said_to_contain": ["SAID TO CONTAIN", "STC"],
    "shippers_load_count": ["SHIPPER'S LOAD, STOW AND COUNT", "SLSC", "SL&C",
                            "SHIPPER'S LOAD AND COUNT"],
    "shippers_weight": ["SHIPPER'S WEIGHT", "SHIPPERS WEIGHT"],
    "to_order": ["TO ORDER", "TO THE ORDER OF"],
    "freight_prepaid": ["FREIGHT PREPAID"],
    "freight_collect": ["FREIGHT COLLECT"],
    "negotiable": ["ORIGINAL", "NEGOTIABLE"],
    "non_negotiable": ["NON-NEGOTIABLE", "NON NEGOTIABLE", "COPY"],
}


# ═══════════════════════════════════════════════════════════
#  FIATA TRANSPORT DOCUMENTS
# ═══════════════════════════════════════════════════════════
#
# Source: fiata.org/resources
# FIATA (International Federation of Freight Forwarders Associations)

FIATA_DOCUMENTS = {
    "FBL": {
        "name": "FIATA Multimodal Transport Bill of Lading",
        "color": "Blue",
        "negotiable": True,
        "description": "Negotiable document of title for multimodal transport. "
                       "Equivalent to an ocean BL but covers door-to-door.",
        "key_fields": [
            "shipper", "consignee", "notify_party",
            "place_of_receipt", "port_of_loading", "port_of_discharge",
            "place_of_delivery", "description_of_goods", "gross_weight",
            "measurement", "freight_prepaid_collect",
        ],
        "signals_en": ["fiata multimodal", "FBL", "negotiable transport bill of lading",
                       "multimodal transport bill of lading"],
    },
    "FWB": {
        "name": "FIATA Multimodal Transport Waybill",
        "color": "White",
        "negotiable": False,
        "description": "Non-negotiable transport waybill for multimodal carriage. "
                       "Consignee receives goods on proof of identity.",
        "key_fields": [
            "shipper", "consignee", "notify_party",
            "place_of_receipt", "place_of_delivery",
            "description_of_goods", "gross_weight",
        ],
        "signals_en": ["fiata waybill", "FWB", "multimodal transport waybill"],
    },
    "FCR": {
        "name": "Forwarder's Certificate of Receipt",
        "color": "Green",
        "negotiable": False,
        "description": "Confirms forwarder received goods in apparent good order. "
                       "Not a document of title.",
        "key_fields": ["shipper", "consignee", "description_of_goods", "gross_weight"],
        "signals_en": ["forwarder's certificate of receipt", "FCR", "certificate of receipt"],
    },
    "FCT": {
        "name": "Forwarder's Certificate of Transport",
        "color": "Yellow",
        "negotiable": False,
        "description": "Confirms forwarder undertakes to transport goods. "
                       "Irrevocable — cannot be varied without consignee consent.",
        "key_fields": ["shipper", "consignee", "place_of_delivery", "description_of_goods"],
        "signals_en": ["forwarder's certificate of transport", "FCT", "certificate of transport"],
    },
    "FWR": {
        "name": "FIATA Warehouse Receipt",
        "color": "Orange",
        "negotiable": True,
        "description": "Negotiable receipt for goods stored in a warehouse. "
                       "Can serve as collateral for financing.",
        "key_fields": ["depositor", "place_of_storage", "description_of_goods", "gross_weight"],
        "signals_en": ["fiata warehouse receipt", "FWR", "warehouse receipt"],
    },
    "SDT": {
        "name": "Shippers Declaration for Dangerous Goods (FIATA/IATA)",
        "color": "Red",
        "negotiable": False,
        "description": "Mandatory declaration for shipping dangerous goods. "
                       "Includes UN number, class, packing group.",
        "key_fields": ["shipper", "un_number", "proper_shipping_name",
                       "class_division", "packing_group", "quantity"],
        "signals_en": ["shipper's declaration", "dangerous goods", "SDT",
                       "DGD", "dangerous goods declaration"],
    },
    "FFI": {
        "name": "FIATA Forwarding Instructions",
        "color": "White",
        "negotiable": False,
        "description": "Shipper's instructions to the freight forwarder. "
                       "Serves as basis for transport arrangement.",
        "key_fields": ["shipper", "consignee", "description_of_goods",
                       "place_of_receipt", "place_of_delivery", "special_instructions"],
        "signals_en": ["forwarding instructions", "FFI", "fiata forwarding"],
    },
    "SIC": {
        "name": "Shippers Intermodal Weight Certificate",
        "color": "White/Green",
        "negotiable": False,
        "description": "Certifies the weight of a container for VGM (SOLAS) compliance.",
        "key_fields": ["container_number", "verified_gross_mass", "weighing_method",
                       "authorized_signatory"],
        "signals_en": ["intermodal weight", "SIC", "weight certificate", "VGM certificate"],
    },
}


# ═══════════════════════════════════════════════════════════
#  IATA AWB REFERENCE — Supplementary to air_cargo_tracker.py
# ═══════════════════════════════════════════════════════════
#
# air_cargo_tracker.py already has AIRLINE_PREFIXES and parse_awb().
# This section adds field mapping and document structure reference.

AWB_FIELDS = {
    "awb_number": {"label": "AWB Number", "type": "string",
                   "format": "3-digit airline prefix + 8-digit serial (last digit = check digit mod 7)"},
    "origin_airport": {"label": "Airport of Departure", "type": "string", "format": "3-letter IATA code"},
    "destination_airport": {"label": "Airport of Destination", "type": "string", "format": "3-letter IATA code"},
    "shipper": {"label": "Shipper (Name and Address)", "type": "text_block"},
    "consignee": {"label": "Consignee (Name and Address)", "type": "text_block"},
    "issuing_carrier": {"label": "Issuing Carrier's Agent", "type": "string"},
    "flight_number": {"label": "Flight/Date", "type": "string"},
    "number_of_pieces": {"label": "No. of Pieces RCP", "type": "integer"},
    "gross_weight": {"label": "Gross Weight", "type": "decimal"},
    "weight_unit": {"label": "Weight Unit", "type": "enum", "values": ["K", "L"]},
    "commodity_item_no": {"label": "Commodity Item No.", "type": "string"},
    "chargeable_weight": {"label": "Chargeable Weight", "type": "decimal"},
    "rate_charge": {"label": "Rate/Charge", "type": "decimal"},
    "nature_of_goods": {"label": "Nature and Quantity of Goods", "type": "text_block"},
    "declared_value_carriage": {"label": "Declared Value for Carriage", "type": "string",
                                "note": "NVD = No Value Declared"},
    "declared_value_customs": {"label": "Declared Value for Customs", "type": "string",
                               "note": "NCV = No Customs Value"},
    "handling_info": {"label": "Handling Information", "type": "text_block"},
    "special_handling_codes": {"label": "SHC (Special Handling Codes)", "type": "list",
                               "note": "e.g. PER (perishable), DGR (dangerous), VAL (valuable)"},
    "prepaid_collect": {"label": "Prepaid/Collect", "type": "enum", "values": ["PP", "CC"]},
}

# MAWB vs HAWB distinction
AWB_TYPES = {
    "MAWB": "Master AWB — issued by the airline directly to the freight forwarder",
    "HAWB": "House AWB — issued by the freight forwarder to the shipper/consignee",
}

# Common special handling codes
AWB_SHC_CODES = {
    "PER": "Perishable",
    "DGR": "Dangerous goods (IATA DGR)",
    "VAL": "Valuable cargo",
    "HUM": "Human remains",
    "AVI": "Live animals",
    "PIL": "Pharmaceuticals",
    "EAT": "Foodstuffs",
    "ICE": "Dry ice (carbon dioxide, solid)",
    "HEA": "Heavy cargo (>150 kg per piece)",
    "VOL": "Volume (light and bulky)",
    "BIG": "Big / oversized shipment",
    "GOH": "Garments on hangers",
    "VUN": "Vulnerable cargo",
    "ELI": "Electronics / lithium batteries",
}


# ═══════════════════════════════════════════════════════════
#  FIRESTORE SEEDER — Populate shipping_lines collection
# ═══════════════════════════════════════════════════════════

def seed_shipping_lines(db):
    """
    Populate the Firestore 'shipping_lines' collection with carrier data.
    This feeds tracker.py's _load_bol_prefixes() function.

    Only ADDS documents — never overwrites existing data (uses merge=True).
    Returns count of carriers seeded.
    """
    count = 0
    for carrier_id, carrier in CARRIERS.items():
        try:
            doc_data = {
                "name": carrier["name"],
                "country": carrier.get("country", ""),
                "scac": carrier.get("scac", ""),
                "bol_prefixes": carrier.get("bol_prefixes", []),
                "bol_pattern": carrier.get("bol_pattern", ""),
                "container_prefixes": carrier.get("container_prefixes", []),
                "email_domains": carrier.get("email_domains", []),
                "terms_url": carrier.get("terms_url", ""),
                "governing_law": carrier.get("governing_law", ""),
                "jurisdiction": carrier.get("jurisdiction", ""),
                "ebl_platform": carrier.get("ebl_platform", ""),
                "general_average": carrier.get("general_average", ""),
                "time_bar_months": carrier.get("time_bar_months", 12),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "source": "shipping_knowledge.py",
            }
            if carrier.get("scac_legacy"):
                doc_data["scac_legacy"] = carrier["scac_legacy"]
                doc_data["scac_change_date"] = carrier["scac_change_date"]
            if carrier.get("legacy_note"):
                doc_data["legacy_note"] = carrier["legacy_note"]
            if carrier.get("liability_regime"):
                doc_data["liability_regime"] = carrier["liability_regime"]

            db.collection("shipping_lines").document(carrier_id).set(doc_data, merge=True)
            count += 1
        except Exception as e:
            print(f"    Error seeding {carrier_id}: {e}")

    print(f"    Seeded {count} carriers into shipping_lines collection")
    return count


def seed_fiata_documents(db):
    """
    Populate a 'fiata_documents' collection with FIATA document type data.
    Returns count of documents seeded.
    """
    count = 0
    for doc_code, doc_info in FIATA_DOCUMENTS.items():
        try:
            db.collection("fiata_documents").document(doc_code).set({
                "code": doc_code,
                "name": doc_info["name"],
                "color": doc_info["color"],
                "negotiable": doc_info["negotiable"],
                "description": doc_info["description"],
                "key_fields": doc_info["key_fields"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "source": "shipping_knowledge.py",
            }, merge=True)
            count += 1
        except Exception as e:
            print(f"    Error seeding FIATA {doc_code}: {e}")

    print(f"    Seeded {count} FIATA document types")
    return count


def seed_all(db):
    """Seed all shipping knowledge into Firestore."""
    print("  SHIPPING KNOWLEDGE: Seeding Firestore...")
    carriers = seed_shipping_lines(db)
    fiata = seed_fiata_documents(db)
    israel = seed_israel_carrier_codes(db)
    print(f"  Done: {carriers} carriers + {fiata} FIATA + {israel} Israel codes")
    return {"carriers": carriers, "fiata": fiata, "israel": israel}


# ═══════════════════════════════════════════════════════════
#  ISRAELI PORT SYSTEM — Israports Community Tables
# ═══════════════════════════════════════════════════════════
#
# Source: israports.co.il Community Tables (TaskYam)
# Israeli ports use local company/line codes in customs declarations,
# manifests, and port system messages. These differ from SCAC codes.

# Israeli 3-letter company code → CARRIERS key
# From S19_ShippingCompanies.csv
ISRAEL_COMPANY_TO_CARRIER = {
    "ZIM": "zim",
    "MSC": "msc",
    "MSK": "maersk",
    "MLL": "maersk",     # Maersk Line Limited (Haifa)
    "MLM": "maersk",     # Maersk Line Limited (Ashdod)
    "SGL": "maersk",     # Seago Line (Maersk subsidiary)
    "COS": "cosco",
    "CSC": "cosco",      # China Shipping Container Line (merged 2016)
    "CSW": "cosco",      # China Shipping (Haifa variant)
    "EGL": "evergreen",
    "EMC": "evergreen",  # Evergreen agency (Israel)
    "HLC": "hapag_lloyd",
    "ONE": "one",        # Crown Shipping Ltd (ONE agent in Israel)
    "YML": "yang_ming",
    "OOL": "oocl",
    "MOL": "one",        # MOL merged into ONE (2018)
    "NYK": "one",        # NYK merged into ONE (2018)
    "KKK": "one",        # K-Line merged into ONE (2018)
    "HSD": "maersk",     # Hamburg Sud (acquired by Maersk 2017)
    "APL": "cosco",      # APL (now CMA CGM subsidiary)
}

# Israeli Kav (line/route) code → CARRIERS key
# From S19_ShippingCompanies.csv
# Each carrier can have different Kav codes at different Israeli ports.
# "XX" is a generic code used by many companies — not included here.
ISRAEL_KAV_TO_CARRIER = {
    "Z1": "zim",          # ZIM at Haifa
    "ZZ": "zim",          # ZIM at Ashdod, Eilat
    "QR": "msc",          # MSC at Haifa
    "QS": "msc",          # MSC at Ashdod, Eilat
    "MS": "maersk",       # Maersk at Ashdod, Haifa, Eilat
    "SM": "maersk",       # Maersk at Ashdod (secondary)
    "CO": "cosco",        # COSCO at Haifa
    "SP": "cosco",        # COSCO at Ashdod, Eilat
    "EL": "evergreen",    # Evergreen at Haifa
    "HC": "hapag_lloyd",  # Hapag-Lloyd at all ports
    "YM": "yang_ming",    # Yang Ming at all ports
    "OC": "oocl",         # OOCL at all ports
    "HS": "maersk",       # Hamburg Sud at all ports (now Maersk)
    "SG": "maersk",       # Seago Line at Ashdod, Haifa
    "AP": "cosco",        # APL at all ports
    "ML": "one",          # MOL at Haifa
    "NK": "one",          # NYK at all ports
    "KL": "one",          # K-Line at all ports
}

# Reverse lookup: CARRIERS key → Israel company codes
CARRIER_TO_ISRAEL_CODES = {}
for _code, _carrier_id in ISRAEL_COMPANY_TO_CARRIER.items():
    CARRIER_TO_ISRAEL_CODES.setdefault(_carrier_id, []).append(_code)

# Main Israeli ports — extends tracker.py PORT_MAP with structured metadata
ISRAEL_PORTS = {
    "ILHFA": {"name_en": "Haifa", "name_he": "\u05d7\u05d9\u05e4\u05d4",
              "unlocode": "IL/HFA", "type": "seaport",
              "israports_name": "\u05e0\u05de\u05dc \u05d7\u05d9\u05e4\u05d4"},
    "ILASD": {"name_en": "Ashdod", "name_he": "\u05d0\u05e9\u05d3\u05d5\u05d3",
              "unlocode": "IL/ASH", "type": "seaport",
              "israports_name": "\u05e0\u05de\u05dc \u05d0\u05e9\u05d3\u05d5\u05d3"},
    "ILELT": {"name_en": "Eilat", "name_he": "\u05d0\u05d9\u05dc\u05ea",
              "unlocode": "IL/ETH", "type": "seaport",
              "israports_name": "\u05e0\u05de\u05dc \u05d0\u05d9\u05dc\u05ea"},
    "ILHDR": {"name_en": "Hadera", "name_he": "\u05d7\u05d3\u05e8\u05d4",
              "unlocode": "IL/HAD", "type": "seaport"},
    "ILBGA": {"name_en": "Ben Gurion Airport",
              "name_he": '\u05e0\u05ea\u05d1"\u05d2',
              "unlocode": "IL/BGA", "type": "airport"},
    "ILTLV": {"name_en": "Tel Aviv",
              "name_he": "\u05ea\u05dc \u05d0\u05d1\u05d9\u05d1",
              "unlocode": "IL/TLV", "type": "city"},
}


def identify_carrier_from_israel_code(code):
    """Identify carrier from Israeli port system company or Kav code.
    Returns carrier_id or None."""
    if not code:
        return None
    code_upper = code.upper().strip()
    carrier = ISRAEL_COMPANY_TO_CARRIER.get(code_upper)
    if carrier:
        return carrier
    return ISRAEL_KAV_TO_CARRIER.get(code_upper)


# ═══════════════════════════════════════════════════════════
#  CONTAINER TYPE MAPPING — Old <> New (ISO 6346)
# ═══════════════════════════════════════════════════════════
#
# Source: israports.co.il Community Table A45 (OldToNew)
# Maps old container type codes (WCO numeric + commercial alpha)
# to new ISO 6346 codes. Value is list (first = primary/preferred).
# Old codes appear in Israeli customs system; new codes per ISO standard.

CONTAINER_TYPE_OLD_TO_NEW = {
    # ── Commercial alphanumeric codes (most common in documents) ──
    # 20-foot
    "20FH": ["25P3"],                    # 20f high Gondola
    "20FL": ["20P0"],                    # Platform (Flat)
    "20HC": ["26G0"],                    # High Container
    "20HH": ["28T8", "2879"],            # Half height Tanker
    "20OH": ["25U1"],                    # Open high top
    "20OS": ["20U0"],                    # Open-Side
    "20OT": ["20U1", "25PM"],            # Open-Top
    "20RF": ["22H1"],                    # Reefer
    "20RG": ["22G1"],                    # General purpose
    "20RH": ["26H1"],                    # High Reefer
    "20SL": ["20S0"],                    # Livestock
    "20TF": ["22K5"],                    # Refrigerated Tank
    "20TH": ["26T0"],                    # High Tank
    "20TK": ["20T3", "22K1", "22K2"],    # Tank
    "20TL": ["20T4"],                    # Tank variant
    "20VT": ["22V0"],                    # Ventilated
    # 40-foot
    "40FH": ["45P8"],                    # 40f high Gondola
    "40FL": ["40P0"],                    # Platform (Flat)
    "40HC": ["L5G1", "45G1", "45SJ", "46G0"],  # High Cube
    "40HH": ["48T8"],                    # Half height Tanker
    "40HT": ["45U6"],                    # High Open top rigid cover
    "40HW": ["4EG1"],                    # High + Wide dry
    "40OH": ["46U1"],                    # Open high top
    "40OL": ["48U1"],                    # Open top half height
    "40OS": ["40U0"],                    # Open-Side
    "40OT": ["40U1"],                    # Open-Top
    "40RF": ["42H1"],                    # Reefer
    "40RG": ["42G1"],                    # General purpose
    "40RH": ["45R1", "46H1"],            # High Reefer
    "40SL": ["40S0"],                    # Livestock
    "40TK": ["40T3"],                    # Tank
    "40VT": ["40V0"],                    # Ventilated
    # 45-foot
    "45FL": ["L0P0"],                    # Platform (Flat)
    "45HC": ["LEG1", "L5G1", "5EGB"],    # High Cube
    "45OS": ["L0U0"],                    # Open-Side
    "45OT": ["L0U1"],                    # Open-Top
    "45RF": ["L2H1"],                    # Reefer
    "45RG": ["L2G1"],                    # General purpose
    "45RH": ["L5R1"],                    # High Reefer
    "45TK": ["L0T3"],                    # Tank
    "45VT": ["L0V0"],                    # Ventilated
    # Other
    "55RG": ["55G1"],                    # GP passive vents
    # ── WCO numeric codes (customs declarations) ──
    # 20-foot
    "2000": ["20G0"], "2020": ["20PL"], "2030": ["20R0"], "2032": ["20HR"],
    "2050": ["20U0"], "2052": ["20OT"], "2054": ["20G2"], "2060": ["20P0"],
    "2063": ["20P1"], "2070": ["20T0"], "2080": ["20B0"],
    "2150": ["20OT"], "2160": ["20PL"], "2163": ["20PL"],
    "2200": ["22G0"], "2210": ["22G1"], "2213": ["20VT"], "2215": ["22V1"],
    "2220": ["20VH"], "2230": ["22R0"], "2232": ["22R1"],
    "2250": ["22U0"], "2251": ["22U1"], "2252": ["20UT"], "2253": ["20UT"],
    "2254": ["22G2"], "2260": ["22P0"], "2261": ["22P1"], "2263": ["22P3"],
    "2270": ["22T0"], "2275": ["22T5"], "2280": ["22B0"],
    "2332": ["20HR"], "2432": ["25R1"],
    "2500": ["25G0"], "2510": ["25G1"], "2530": ["25R0"], "2550": ["25U0"],
    "2554": ["25G2"], "2560": ["25P0"], "2563": ["25P3"], "2570": ["25T0"],
    "2580": ["25B0"], "2600": ["26GP"],
    # 40-foot
    "4000": ["40G0"], "4020": ["40VH"], "4030": ["40R0"], "4050": ["40U0"],
    "4054": ["40G2"], "4060": ["40P0"], "4063": ["40P3"], "4070": ["40T0"],
    "4080": ["40B0"],
    "4132": ["40HR"], "4170": ["40TD"], "4200": ["40GP"],
    "4260": ["40FL"], "4263": ["40FL"],
    "4300": ["42G0"], "4301": ["40OS"], "4305": ["40HT"],
    "4310": ["42G1"], "4315": ["42V1"], "4320": ["40VH"],
    "4330": ["42R0"], "4332": ["42R1"], "4350": ["42U0"], "4351": ["42U1"],
    "4354": ["42G2"], "4360": ["42P0"], "4361": ["42P1"], "4363": ["42P3"],
    "4370": ["42T0"], "4380": ["42B0"],
    "4400": ["46GP"], "4420": ["46GP"], "4426": ["46GP"], "4432": ["46HR"],
    "4500": ["45G0"], "4510": ["45G1"], "4511": ["45G1"],
    "4530": ["46HR"], "4531": ["46HR"],
    "4550": ["45U0"], "4554": ["45G2"], "4560": ["45P0"], "4563": ["45P3"],
    "4570": ["45T0"], "4580": ["45B0"], "4599": ["46GP"],
    "4650": ["40UT"], "4699": ["46GP"],
    # 45-foot (9xxx WCO codes; L-prefix in ISO = 45ft)
    "9400": ["L0GP"], "9500": ["L5G0"], "9510": ["45VT"],
    "9530": ["L5R0"], "9532": ["L0HR"], "9550": ["L5U0"],
    "9554": ["L5G2"], "9560": ["L5P0"], "9563": ["L5P3"],
    "9570": ["L5T0"], "9580": ["L5B0"],
}

# Reverse lookup: new ISO code → old commercial code(s)
# Built from commercial codes only (skip WCO 4-digit numeric)
CONTAINER_TYPE_NEW_TO_OLD = {}
for _old, _new_list in CONTAINER_TYPE_OLD_TO_NEW.items():
    if _old.isdigit():
        continue  # Skip WCO numeric-only codes for reverse map
    for _new in _new_list:
        CONTAINER_TYPE_NEW_TO_OLD.setdefault(_new, []).append(_old)


def resolve_container_type(code):
    """Resolve a container type code to its ISO 6346 equivalent and description.
    Accepts old (commercial/WCO) or new (ISO) codes.
    Returns dict with: input, iso_codes, description — or None if unknown."""
    if not code:
        return None
    code_upper = code.upper().strip()

    # Check if it's an old code -> return new ISO code(s)
    new_codes = CONTAINER_TYPE_OLD_TO_NEW.get(code_upper)
    if new_codes:
        desc = COMMON_CONTAINER_TYPES.get(code_upper) or COMMON_CONTAINER_TYPES.get(new_codes[0])
        return {"input": code_upper, "iso_codes": new_codes, "description": desc}

    # Check if it's already a known ISO/commercial code
    desc = COMMON_CONTAINER_TYPES.get(code_upper)
    if desc:
        old_codes = CONTAINER_TYPE_NEW_TO_OLD.get(code_upper, [])
        return {"input": code_upper, "iso_codes": [code_upper],
                "old_codes": old_codes, "description": desc}

    # Check if it's a new ISO code in our reverse map (not in COMMON_CONTAINER_TYPES)
    old_codes = CONTAINER_TYPE_NEW_TO_OLD.get(code_upper)
    if old_codes:
        return {"input": code_upper, "iso_codes": [code_upper],
                "old_codes": old_codes, "description": None}

    return None


# ═══════════════════════════════════════════════════════════
#  ISRAEL DATA SEEDER — Update Firestore with Israeli codes
# ═══════════════════════════════════════════════════════════

# Map carrier_id → Israeli port system identifiers (for Firestore seeding)
_CARRIER_ISRAEL_DATA = {
    "zim": {
        "israel_company_codes": ["ZIM"],
        "israel_kav_codes": {"Z1": "Haifa", "ZZ": "Ashdod/Eilat"},
    },
    "msc": {
        "israel_company_codes": ["MSC"],
        "israel_kav_codes": {"QR": "Haifa", "QS": "Ashdod/Eilat"},
    },
    "maersk": {
        "israel_company_codes": ["MSK", "MLL", "MLM", "SGL"],
        "israel_kav_codes": {"MS": "Ashdod/Haifa/Eilat", "SM": "Ashdod", "SG": "Ashdod/Haifa"},
    },
    "cosco": {
        "israel_company_codes": ["COS", "CSC", "CSW"],
        "israel_kav_codes": {"CO": "Haifa", "SP": "Ashdod/Eilat"},
    },
    "evergreen": {
        "israel_company_codes": ["EGL", "EMC"],
        "israel_kav_codes": {"EL": "Haifa"},
    },
    "hapag_lloyd": {
        "israel_company_codes": ["HLC"],
        "israel_kav_codes": {"HC": "Haifa/Ashdod/Eilat"},
    },
    "one": {
        "israel_company_codes": ["ONE", "MOL", "NYK", "KKK"],
        "israel_kav_codes": {"ML": "Haifa", "NK": "all ports", "KL": "all ports"},
    },
    "yang_ming": {
        "israel_company_codes": ["YML"],
        "israel_kav_codes": {"YM": "Haifa/Ashdod/Eilat"},
    },
    "oocl": {
        "israel_company_codes": ["OOL"],
        "israel_kav_codes": {"OC": "Haifa/Ashdod/Eilat"},
    },
}


def seed_israel_carrier_codes(db):
    """
    Update existing shipping_lines documents with Israeli port system codes.
    Adds israel_company_codes and israel_kav_codes fields.
    Uses merge=True — never overwrites existing fields.
    Returns count of carriers updated.
    """
    count = 0
    for carrier_id, israel_data in _CARRIER_ISRAEL_DATA.items():
        try:
            db.collection("shipping_lines").document(carrier_id).set({
                "israel_company_codes": israel_data["israel_company_codes"],
                "israel_kav_codes": israel_data["israel_kav_codes"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, merge=True)
            count += 1
        except Exception as e:
            print(f"    Error updating Israel codes for {carrier_id}: {e}")

    print(f"    Updated {count} carriers with Israeli port system codes")
    return count


# ═══════════════════════════════════════════════════════════
#  VESSEL TYPES — Israeli Port System (V03)
# ═══════════════════════════════════════════════════════════
#
# Source: israports.co.il Community Table V03
# Used in manifests and port messages to classify vessel type.

VESSEL_TYPES = {
    "04": {"name_en": "COAL", "name_he": "אנית פחם"},
    "06": {"name_en": "GRAIN", "name_he": "אנית גרעינים"},
    "07": {"name_en": "DRY BULK", "name_he": "אנית צובר יבש"},
    "08": {"name_en": "OIL TANKER", "name_he": "מכליות דלק"},
    "09": {"name_en": "CHEMICAL TANKER", "name_he": "מכליות כימיקלים"},
    "11": {"name_en": "PALLET CARRIER", "name_he": "אניות משטחים"},
    "12": {"name_en": "GENERAL CARGO", "name_he": "אניות משא כללי"},
    "14": {"name_en": "MULTI-PURPOSE", "name_he": "אניות רב תכליתיות"},
    "15": {"name_en": "CONTAINER SHIP", "name_he": "אניות מכולה מתמחה"},
    "17": {"name_en": "RO-RO", "name_he": "אניות גלנוע"},
    "19": {"name_en": "SCAND. RO-RO", "name_he": "אניות גלנוע סקנדינבי"},
    "21": {"name_en": "PASSENGER VESSEL", "name_he": "אניות נוסעים קו"},
    "25": {"name_en": "CRUISE VESSEL", "name_he": "אניות סיור"},
    "31": {"name_en": "FISHING VESSEL", "name_he": "סירות דייג"},
    "32": {"name_en": "NAVAL VESSEL", "name_he": "חיל הים"},
    "33": {"name_en": "MARITIME SCHOOL", "name_he": "בית ספר ימי"},
    "34": {"name_en": "LARGE TUG", "name_he": "גוררת גדולה"},
    "35": {"name_en": "SMALL TUG", "name_he": "גוררת קטנה"},
    "36": {"name_en": "SMALL VESSEL", "name_he": "ספינות קטנות"},
    "37": {"name_en": "MILITARY VESSEL", "name_he": "אניות מלחמה"},
    "39": {"name_en": "MISCELLANEOUS", "name_he": "בלתי מוגדר"},
    "40": {"name_en": "BARGE", "name_he": "דוברה"},
}


# ═══════════════════════════════════════════════════════════
#  PACKAGE TYPE CODES — Israeli Port System (C01)
# ═══════════════════════════════════════════════════════════
#
# Source: israports.co.il Community Table C01
# Maps Israeli package codes to WCO codes.
# Used in customs declarations and manifests.

PACKAGE_CODES = {
    "33": {"name_he": "משטחים-שקים", "name_en": "PALLETS - BAGS", "wco": "BG"},
    "36": {"name_he": "משטחים-חביות", "name_en": "PALLETS-DRUMS", "wco": "DR"},
    "37": {"name_he": "מענבים/משטחים-גלילי נייר", "name_en": "PALLETS-PAPER REELS", "wco": "RL"},
    "43": {"name_he": "מענבים-שקים", "name_en": "SLINGS-BAGS", "wco": "BG"},
    "44": {"name_he": "חבקים/מענבים-כריכות", "name_en": "SLINGS/BALES", "wco": "NE"},
    "60": {"name_he": "יחידות בולי עץ", "name_en": "WOOD LOGS", "wco": "LG"},
    "80": {"name_he": "חפצים אישיים בליפט/ארגז", "name_en": "WOOD LIFT", "wco": "LE"},
    "90": {"name_he": "צובר-פוספטים", "name_en": "BULK - PHOSPHATES", "wco": "VY"},
    "93": {"name_he": "צובר-דשנים", "name_en": "BULK - FERTILIZERS", "wco": "VY"},
    "95": {"name_he": "צובר נוזלי", "name_en": "BULK - LIQUID", "wco": "VL"},
    "A0": {"name_he": "חפצים אישיים בודדים", "name_en": "IMMIGRANTS CASES", "wco": "NE"},
    "A8": {"name_he": "שקים גדולים", "name_en": "BIG BAGS", "wco": "JB"},
    "A9": {"name_he": "כריכות-בודדים", "name_en": "BALES", "wco": "BN"},
    "AA": {"name_he": "שקי דואר", "name_en": "MAIL BAGS", "wco": "BG"},
    "AN": {"name_he": "בעלי חיים", "name_en": "ANIMAL", "wco": "PF"},
    "B8": {"name_he": "גלילי נייר-בודדים", "name_en": "PAPER REELS", "wco": "RL"},
    "BP": {"name_he": "שקים בודדים", "name_en": "BAGS", "wco": "BG"},
    "C8": {"name_he": "נגרר שהוא המטען/קרוואן", "name_en": "TRAILER", "wco": "VN"},
    "D2": {"name_he": "משטחים-כללי", "name_en": "PALLETS UNSPECIFIED", "wco": "PX"},
    "D5": {"name_he": "מכולה מלאה", "name_en": "CONTAINER", "wco": "CN"},
    "D6": {"name_he": "צובר יבש", "name_en": "CARGO IN BULK", "wco": "VR"},
    "DP": {"name_he": "חביות בודדות", "name_en": "DRUMS", "wco": "NE"},
    "E5": {"name_he": "מכונית נוסעים", "name_en": "VEHICLE UP TO 20'", "wco": "VN"},
    "E6": {"name_he": "רכב מסחרי מעל 20'", "name_en": "VEHICLE ABOVE 20'", "wco": "VN"},
    "E7": {"name_he": "גרוטאות מתכת", "name_en": "STEEL SCRAP", "wco": "VS"},
    "F1": {"name_he": "קרטונים-בשר קפוא", "name_en": "FROZEN MEAT CARTONS", "wco": "CT"},
    "F6": {"name_he": "פרי הדר לא ממושטח", "name_en": "CITRUS UNPALLETIZED", "wco": "FC"},
    "F7": {"name_he": "פרי הדר ממושטח", "name_en": "CITRUS PALLETIZED", "wco": "FC"},
    "F8": {"name_he": "משטחים-תוצרת חקלאית", "name_en": "PALLETS-AGRICULTURAL", "wco": "LU"},
    "G3": {"name_he": "פטקוק-צובר", "name_en": "PETCOKE BULK", "wco": "VO"},
    "G4": {"name_he": "צובר-פחם", "name_en": "BULK - COAL", "wco": "VO"},
    "G5": {"name_he": "צובר-מלט", "name_en": "BULK - CEMENT", "wco": "VY"},
    "G6": {"name_he": "צובר-גרעינים ותבואות", "name_en": "BULK - GRAIN", "wco": "VR"},
    "G7": {"name_he": "צובר-דלק", "name_en": "BULK - FUEL", "wco": "VL"},
    "G8": {"name_he": "צובר-גופרית", "name_en": "BULK - SULFUR", "wco": "VY"},
    "G9": {"name_he": "צובר-סוכר", "name_en": "BULK - SUGAR", "wco": "VR"},
    "GC": {"name_he": "ארגזים/קרטונים/לשכים", "name_en": "CASES/CARTONS/CRATES", "wco": "PP"},
    "GP": {"name_he": "מוצרי גרעינים", "name_en": "BULK - GRAIN PRODUCTS", "wco": "VR"},
    "H2": {"name_he": "גלילי בד", "name_en": "FABRIC ROLLS", "wco": "SO"},
    "H6": {"name_he": "רכב מסחרי עד 20' ואופנוע", "name_en": "VEHICLE/MOTORCYCLE", "wco": "VN"},
    "K1": {"name_he": "מכונות/חלקי מכונות לא ארוזים", "name_en": "UNPACKED MACHINES", "wco": "NE"},
    "K2": {"name_he": "גושי אבן/שיש בודדים", "name_en": "ROCKS/STONES/MARBLE", "wco": "NE"},
    "PP": {"name_he": "כריכות תאית-בודדים", "name_en": "CELLULOSE BALES", "wco": "BL"},
    "PS": {"name_he": "תאית-חבקים/מענבים", "name_en": "CELLULOSE SLINGS", "wco": "BL"},
    "S1": {"name_he": "פסי רכבת/צינורות ברזל", "name_en": "RAILS/IRON PIPES", "wco": "PI"},
    "S2": {"name_he": "כל סוגי המתכות", "name_en": "METALS", "wco": "SM"},
    "S3": {"name_he": "גלילים", "name_en": "ROLLS", "wco": "SM"},
    "S4": {"name_he": "סלילים", "name_en": "COILS", "wco": "SM"},
    "S5": {"name_he": "ברזל בניין", "name_en": "CONSTRUCTION STEEL", "wco": "SM"},
    "T1": {"name_he": "רכב ונגרר טעון עד 20'", "name_en": "LOADED VEHICLE UP TO 20'", "wco": "VN"},
    "T2": {"name_he": "רכב ונגרר מעל 20'", "name_en": "LOADED VEHICLE ABOVE 20'", "wco": "VN"},
    "T3": {"name_he": "רכב ונגרר ריק", "name_en": "EMPTY VEHICLE", "wco": "VN"},
    "VC": {"name_he": "מטען נפח", "name_en": "VOLUME CARGO", "wco": "PP"},
    "W1": {"name_he": "יחידות עץ נסור", "name_en": "SAWN WOOD UNITS", "wco": "NE"},
    "W2": {"name_he": "יחידות עמודים/אדנים", "name_en": "POLES/SLEEPERS", "wco": "NE"},
    "W3": {"name_he": "חבילות עצים/אדנים/לבידים", "name_en": "WOOD BUNDLES", "wco": "8C"},
}


# ═══════════════════════════════════════════════════════════
#  DANGEROUS GOODS — IMDG Classes Reference
# ═══════════════════════════════════════════════════════════
#
# Source: israports.co.il Community Table A17 (2,375 UN numbers)
# Full data in C:/Users/doron/israports_tables/A17_DangerousGoods.csv
# Too large to embed — use IMDG_CLASSES for classification,
# full UN number lookup from CSV or Firestore if needed.

IMDG_CLASSES = {
    "1": "Explosives",
    "1.1": "Mass explosion hazard",
    "1.2": "Projection hazard",
    "1.3": "Fire/minor blast/projection hazard",
    "1.4": "Minor hazard",
    "1.5": "Very insensitive; mass explosion hazard",
    "1.6": "Extremely insensitive",
    "2": "Gases",
    "2.1": "Flammable gas",
    "2.2": "Non-flammable, non-toxic gas",
    "2.3": "Toxic gas",
    "3": "Flammable liquids",
    "4": "Flammable solids",
    "4.1": "Flammable solid",
    "4.2": "Spontaneously combustible",
    "4.3": "Dangerous when wet",
    "5": "Oxidizers & organic peroxides",
    "5.1": "Oxidizing substance",
    "5.2": "Organic peroxide",
    "6": "Toxic & infectious substances",
    "6.1": "Toxic substance",
    "6.2": "Infectious substance",
    "7": "Radioactive material",
    "8": "Corrosives",
    "9": "Miscellaneous dangerous goods",
}


# ═══════════════════════════════════════════════════════════
#  TASKYAM ERROR CODES — Reference for port system messages
# ═══════════════════════════════════════════════════════════
#
# Source: israports.co.il Community Table S30 (133 error codes)
# Full data in C:/Users/doron/israports_tables/S30_ErrorCodes.csv
# Key error codes that appear in TaskYam system responses:

TASKYAM_KEY_ERRORS = {
    "1006": "MANIFEST NUMBER NOT VALID",
    "1011": "VESSEL CODE DOES NOT EXIST IN TABLE",
    "1025": "SHIP AGENT CODE MISSING",
    "1026": "SHIP AGENT CODE DOES NOT EXIST IN TABLE",
    "1105": "MANIFEST DOES NOT EXIST-ACTION NOT VALID",
    "1300": "DELIVERY ORDER NUMBER MISSING",
    "2009": "DEAL ID NOT VALID",
    "2010": "DEAL ID MISSING",
    "2011": "DEAL DOES NOT BELONG TO SENDER",
    "2012": "DEAL DOES NOT EXIST",
    "3026": "INVALID PORT OF LOADING",
    "3050": "PACKING TYPE MISSING",
    "3055": "CONTAINER NUMBER MISSING",
    "3060": "CONTAINER TYPE MISSING",
    "3061": "CONTAINER TYPE NOT VALID (WCO mismatch)",
    "3065": "CONTAINER LENGTH MISSING",
    "3090": "DANGER CODE NOT VALID",
    "3092": "UN CODE NOT VALID",
    "3100": "DELIVERY TYPE NOT VALID",
    "3110": "CUSTOMS AGENT CODE WRONG",
    "3810": "CARGO DESCRIPTION MISSING",
    "4512": "CUSTOMER ID IN DOCUMENT DOESNT FIT",
}
