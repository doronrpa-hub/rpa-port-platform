"""
RCB Document Parser — Per-Document Type Identification & Field Extraction
=========================================================================
Identifies individual document types from text + filename, then extracts
structured fields using regex patterns in Hebrew and English.

No AI calls — pure pattern matching.

Functions:
1. identify_document_type(text, filename)
2. extract_structured_fields(text, doc_type)
3. assess_document_completeness(extracted_fields, doc_type)
4. parse_document(text, filename)  — convenience: runs 1 + 2 + 3
"""

import re
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
#  DOCUMENT TYPE DEFINITIONS
# ═══════════════════════════════════════════════════════════════

# Each type has weighted keyword groups. A keyword in "strong" is worth 3 pts,
# "medium" 2 pts, "weak" 1 pt.  Highest total score wins.
_DOC_TYPE_SIGNALS = {
    "commercial_invoice": {
        "name_he": "חשבונית מסחרית",
        "name_en": "Commercial Invoice",
        "strong": [
            r"commercial\s*invoice", r"חשבונית\s*מסחרית", r"חשבון\s*מכר",
            r"tax\s*invoice", r"invoice\s*n[o°umber#.:]+\s*\S+",
        ],
        "medium": [
            r"invoice\s*date", r"invoice\s*amount", r"total\s*value",
            r"unit\s*price", r"חשבונית", r"חשבון",
            r"proforma", r"factura", r"rechnung",
        ],
        "weak": [
            r"quantity", r"description\s*of\s*goods", r"incoterms?",
            r"\b(fob|cif|cfr|exw|ddp|dap)\b", r"payment\s*terms",
            r"תיאור\s*(ה)?טובין", r"כמות", r"מחיר\s*יחידה",
        ],
        "filename": [
            r"inv", r"invoice", r"חשבונית", r"factura",
        ],
    },
    "packing_list": {
        "name_he": "רשימת אריזה",
        "name_en": "Packing List",
        "strong": [
            r"packing\s*list", r"רשימת\s*אריזה",
            r"packing\s*note", r"packing\s*slip",
        ],
        "medium": [
            r"gross\s*weight", r"net\s*weight", r"carton\s*n[o°#]",
            r"package\s*n[o°#]", r"dimensions", r"\bcbm\b",
            r"משקל\s*ברוטו", r"משקל\s*נטו",
        ],
        "weak": [
            r"pallet", r"carton", r"box\s*n[o°#]",
            r"length.*width.*height", r"volume",
            r"אריזה", r"משטח", r"קרטון",
        ],
        "filename": [
            r"pack", r"pl[_\-\s]", r"packing",
        ],
    },
    "bill_of_lading": {
        "name_he": "שטר מטען ימי",
        "name_en": "Bill of Lading",
        "strong": [
            r"bill\s*of\s*lading", r"שטר\s*מטען",
            r"b/?l\s*n[o°umber#.:]+\s*\S+",
            r"ocean\s*bill", r"sea\s*waybill",
        ],
        "medium": [
            r"shipper", r"consignee", r"notify\s*party",
            r"port\s*of\s*loading", r"port\s*of\s*discharge",
            r"vessel\s*name", r"voyage\s*n[o°#]",
            r"שולח", r"נמען", r"נמל\s*טעינה", r"נמל\s*פריקה",
        ],
        "weak": [
            r"container\s*n[o°#]", r"freight\s*prepaid",
            r"freight\s*collect", r"on\s*board\s*date",
            r"shipped\s*on\s*board", r"laden\s*on\s*board",
            r"מכולה", r"הובלה\s*ימית",
        ],
        "filename": [
            r"b[/]?l", r"bill.?of.?lading", r"bol", r"bl[_\-\s\d]",
        ],
    },
    "booking_confirmation": {
        "name_he": "אישור הזמנה",
        "name_en": "Booking Confirmation",
        "strong": [
            r"booking\s*confirm", r"אישור\s*הזמנ",
            r"booking\s*n[o°umber#.:]+\s*\S+",
            r"EBKG\d{6,12}",
        ],
        "medium": [
            r"booking\s*(?:ref|number|no)", r"הזמנת?\s*(?:הובלה|שילוח)",
            r"container\s*cutoff", r"doc(?:ument)?\s*cutoff",
            r"closing\s*date", r"סגירת?\s*מכולו?ת",
            r"vessel\s*(?:name|/|:)", r"voyage",
        ],
        "weak": [
            r"shipping\s*instruction", r"הוראות\s*שילוח",
            r"etd", r"eta", r"cut[\s\-]?off",
        ],
        "filename": [
            r"book", r"bkg", r"ebkg", r"confirm",
        ],
    },
    "air_waybill": {
        "name_he": "שטר מטען אווירי",
        "name_en": "Air Waybill",
        "strong": [
            r"air\s*waybill", r"airway\s*bill",
            r"\bawb\s*n[o°umber#.:]+\s*\S+", r"שטר\s*מטען\s*אווירי",
            r"master\s*air\s*waybill", r"house\s*air\s*waybill",
        ],
        "medium": [
            r"airport\s*of\s*departure", r"airport\s*of\s*destination",
            r"flight\s*n[o°#]", r"iata\s*code",
            r"\bawb\b", r"air\s*cargo",
        ],
        "weak": [
            r"airline", r"aircraft", r"cargo\s*terminal",
        ],
        "filename": [
            r"awb", r"air.?waybill", r"airway",
        ],
    },
    "certificate_of_origin": {
        "name_he": "תעודת מקור",
        "name_en": "Certificate of Origin",
        "strong": [
            r"certificate\s*of\s*origin", r"תעודת\s*מקור",
            r"origin\s*certificate",
        ],
        "medium": [
            r"country\s*of\s*origin", r"ארץ\s*המקור",
            r"originating\s*product", r"origin\s*criterion",
            r"chamber\s*of\s*commerce",
        ],
        "weak": [
            r"certified\s*that", r"the\s*goods\s*originate",
            r"manufactured\s*in", r"produced\s*in",
        ],
        "filename": [
            r"c[_\-\s]?o[_\-\s]?o", r"origin", r"coo",
            r"cert.?of.?origin",
        ],
    },
    "eur1": {
        "name_he": "תעודת תנועה EUR.1",
        "name_en": "EUR.1 Movement Certificate",
        "strong": [
            r"eur[\.\s]*1\b", r"movement\s*certificate",
            r"תעודת\s*תנועה",
        ],
        "medium": [
            r"euro[- ]?mediterranean", r"preferential\s*treatment",
            r"cumulation", r"approved\s*exporter",
            r"invoice\s*declaration",
        ],
        "weak": [
            r"protocol\s*\d", r"pan[- ]?euro",
            r"diagonal\s*cumulation",
        ],
        "filename": [
            r"eur[\.\s]*1", r"eur1",
        ],
    },
    "health_certificate": {
        "name_he": "תעודת בריאות",
        "name_en": "Health/Sanitary/Phytosanitary Certificate",
        "strong": [
            r"health\s*certificate", r"תעודת\s*בריאות",
            r"phytosanitary\s*certificate", r"תעודה\s*פיטוסניטרית",
            r"veterinary\s*certificate", r"תעודה\s*וטרינרית",
            r"sanitary\s*certificate",
        ],
        "medium": [
            r"free\s*from\s*pest", r"plant\s*protection",
            r"animal\s*health", r"food\s*safety",
            r"שירות\s*הווטרינרי", r"שירות\s*הגנת\s*הצומח",
        ],
        "weak": [
            r"fumigation", r"inspection\s*result",
            r"treatment\s*certificate", r"חיטוי",
        ],
        "filename": [
            r"health", r"sanit", r"phyto", r"veter",
        ],
    },
    "insurance": {
        "name_he": "תעודת ביטוח",
        "name_en": "Insurance Certificate/Policy",
        "strong": [
            r"insurance\s*certificate", r"insurance\s*policy",
            r"תעודת\s*ביטוח", r"פוליסת\s*ביטוח",
        ],
        "medium": [
            r"insured\s*value", r"premium\s*amount",
            r"coverage\s*type", r"all\s*risks",
            r"ערך\s*מבוטח", r"כיסוי\s*ביטוחי",
        ],
        "weak": [
            r"claim", r"deductible", r"underwriter",
        ],
        "filename": [
            r"insur", r"policy", r"ביטוח",
        ],
    },
    "delivery_order": {
        "name_he": "פקודת מסירה",
        "name_en": "Delivery Order",
        "strong": [
            r"delivery\s*order", r"פקודת\s*מסירה",
            r"release\s*order",
        ],
        "medium": [
            r"consignee\s*release", r"cargo\s*release",
            r"please\s*deliver", r"authorized\s*to\s*collect",
            r"שחרור\s*מטען",
        ],
        "weak": [
            r"warehouse", r"terminal", r"gate\s*pass",
        ],
        "filename": [
            r"d[_\-\s]?o\b", r"delivery.?order", r"release",
        ],
    },
    "air_delivery_order": {
        "name_he": "פקודת מסירה אווירית",
        "name_en": "Air Delivery Order",
        "strong": [
            r"air\s*delivery\s*order", r"פקודת\s*מסירה\s*אווירית",
            r"air\s*release\s*order",
            r"cargo\s*release\s*notice", r"הודעת\s*שחרור\s*מטען\s*אווירי",
            r"שחרור\s*מטען\s*אווירי",
        ],
        "medium": [
            r"air\s*release", r"air\s*cargo\s*release",
            r"storage\s*notice", r"terminal\s*release",
            r"(?:cargo\s*release|שחרור\s*מטען).*(?:awb|אווירי)",
            r"(?:awb|air\s*waybill).*(?:release|שחרור)",
        ],
        "weak": [
            r"maman", r"swissport", r"cargo\s*terminal",
            r"storage\s*fee", r"דמי\s*אחסנה",
        ],
        "filename": [
            r"ado", r"air.?release", r"air.?delivery", r"cargo.?release",
        ],
    },
}

# Required fields per document type (field_name, importance)
# importance: "critical" = must have, "important" = should have, "optional" = nice to have
_REQUIRED_FIELDS = {
    "commercial_invoice": [
        ("invoice_number", "critical"),
        ("date", "critical"),
        ("seller_name", "critical"),
        ("buyer_name", "critical"),
        ("currency", "critical"),
        ("total_value", "critical"),
        ("origin_country", "important"),
        ("incoterms", "important"),
        ("line_items", "important"),
        ("destination", "optional"),
    ],
    "packing_list": [
        ("total_packages", "critical"),
        ("gross_weight", "critical"),
        ("net_weight", "important"),
        ("dimensions", "optional"),
        ("marks_numbers", "optional"),
    ],
    "bill_of_lading": [
        ("bl_number", "critical"),
        ("shipper", "critical"),
        ("consignee", "critical"),
        ("vessel", "important"),
        ("port_of_loading", "important"),
        ("port_of_discharge", "important"),
        ("container_numbers", "optional"),
    ],
    "booking_confirmation": [
        ("booking_number", "critical"),
        ("vessel", "important"),
        ("voyage", "important"),
        ("etd", "important"),
        ("eta", "optional"),
        ("container_type", "optional"),
        ("container_quantity", "optional"),
        ("cutoff_date", "optional"),
    ],
    "air_waybill": [
        ("awb_number", "critical"),
        ("shipper", "critical"),
        ("consignee", "critical"),
        ("airport_departure", "important"),
        ("airport_destination", "important"),
        ("flight_number", "optional"),
    ],
    "certificate_of_origin": [
        ("certificate_number", "critical"),
        ("country_of_origin", "critical"),
        ("issuing_authority", "important"),
        ("goods_description", "important"),
        ("exporter", "optional"),
    ],
    "eur1": [
        ("certificate_number", "critical"),
        ("exporter", "critical"),
        ("consignee", "important"),
        ("country_of_origin", "important"),
        ("goods_description", "important"),
    ],
    "health_certificate": [
        ("certificate_number", "critical"),
        ("issuing_authority", "critical"),
        ("country_of_origin", "important"),
        ("goods_description", "important"),
        ("issue_date", "important"),
        ("expiry_date", "optional"),
    ],
    "insurance": [
        ("policy_number", "critical"),
        ("insured_value", "critical"),
        ("coverage_type", "important"),
        ("insurer_name", "optional"),
    ],
    "delivery_order": [
        ("do_number", "critical"),
        ("consignee", "critical"),
        ("bl_reference", "important"),
        ("vessel", "optional"),
        ("pickup_location", "optional"),
        ("release_date", "optional"),
        ("agent_name", "optional"),
    ],
    "air_delivery_order": [
        ("awb_reference", "critical"),
        ("consignee", "critical"),
        ("terminal", "important"),
        ("release_status", "important"),
        ("storage_fees", "optional"),
        ("flight_number", "optional"),
        ("agent_name", "optional"),
    ],
}


# ═══════════════════════════════════════════════════════════════
#  1. IDENTIFY DOCUMENT TYPE
# ═══════════════════════════════════════════════════════════════

def identify_document_type(text, filename=""):
    """
    Analyze extracted text and filename to determine document type.

    Args:
        text: str — extracted text content
        filename: str — original filename

    Returns:
        dict with:
          doc_type: str (e.g. "commercial_invoice")
          name_he: str
          name_en: str
          confidence: int (0-100)
          scores: dict — breakdown of all type scores (for debugging)
    """
    text_lower = (text or "").lower()
    fn_lower = (filename or "").lower()
    scores = {}

    for doc_type, signals in _DOC_TYPE_SIGNALS.items():
        score = 0

        # Text keyword matching
        for pattern in signals.get("strong", []):
            if re.search(pattern, text_lower):
                score += 3

        for pattern in signals.get("medium", []):
            if re.search(pattern, text_lower):
                score += 2

        for pattern in signals.get("weak", []):
            if re.search(pattern, text_lower):
                score += 1

        # Filename matching (bonus, not standalone)
        for pattern in signals.get("filename", []):
            if re.search(pattern, fn_lower):
                score += 2

        scores[doc_type] = score

    # Pick the winner
    if not scores or max(scores.values()) == 0:
        return {
            "doc_type": "unknown",
            "name_he": "לא מזוהה",
            "name_en": "Unknown",
            "confidence": 0,
            "scores": scores,
        }

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    # Calculate confidence:
    # 1-2 pts = low, 3-5 = medium, 6-9 = high, 10+ = very high
    if best_score >= 10:
        confidence = min(98, 75 + best_score)
    elif best_score >= 6:
        confidence = 60 + best_score * 2
    elif best_score >= 3:
        confidence = 40 + best_score * 5
    else:
        confidence = best_score * 15

    # Penalize if runner-up is close (ambiguous)
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) >= 2 and sorted_scores[1] > 0:
        gap = sorted_scores[0] - sorted_scores[1]
        if gap <= 1:
            confidence = max(20, confidence - 15)
        elif gap <= 2:
            confidence = max(25, confidence - 8)

    signals_info = _DOC_TYPE_SIGNALS[best_type]
    return {
        "doc_type": best_type,
        "name_he": signals_info["name_he"],
        "name_en": signals_info["name_en"],
        "confidence": min(98, confidence),
        "scores": scores,
    }


# ═══════════════════════════════════════════════════════════════
#  2. EXTRACT STRUCTURED FIELDS
# ═══════════════════════════════════════════════════════════════

def extract_structured_fields(text, doc_type):
    """
    Based on document type, extract key fields using regex patterns.

    Args:
        text: str — extracted text content
        doc_type: str — from identify_document_type()

    Returns:
        dict — field names to extracted values
    """
    if not text:
        return {}

    extractors = {
        "commercial_invoice": _extract_invoice_fields,
        "packing_list": _extract_packing_list_fields,
        "bill_of_lading": _extract_bl_fields,
        "booking_confirmation": _extract_booking_fields,
        "air_waybill": _extract_awb_fields,
        "certificate_of_origin": _extract_coo_fields,
        "eur1": _extract_eur1_fields,
        "health_certificate": _extract_health_cert_fields,
        "insurance": _extract_insurance_fields,
        "delivery_order": _extract_do_fields,
        "air_delivery_order": _extract_air_do_fields,
    }

    extractor = extractors.get(doc_type)
    if extractor:
        return extractor(text)
    return _extract_generic_fields(text)


# ── Invoice ──

def _extract_invoice_fields(text):
    fields = {}
    t = text
    tu = text.upper()

    # Invoice number
    for pat in [
        r'(?:invoice|inv|חשבונית|חשבון)\s*(?:no|number|n[°o]|#|מס[\'.]?)[.:\s]*([A-Za-z0-9\-/]+)',
        r'(?:invoice|inv)\s*[.:\s]+([A-Za-z0-9\-/]{3,20})',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["invoice_number"] = m.group(1).strip()
            break

    # Date
    fields["date"] = _find_date(t, prefix_patterns=[
        r'(?:invoice\s*date|date|תאריך)',
    ])

    # Seller
    for pat in [
        r'(?:seller|exporter|shipper|supplier|from|מוכר|יצואן|ספק)[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["seller_name"] = _clean_value(m.group(1), max_len=120)
            break

    # Buyer
    for pat in [
        r'(?:buyer|consignee|importer|customer|to|sold\s*to|ship\s*to|קונה|יבואן|לקוח)[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["buyer_name"] = _clean_value(m.group(1), max_len=120)
            break

    # Origin country
    for pat in [
        r'(?:country\s*of\s*origin|origin|made\s*in|ארץ\s*(?:ה)?מקור)[:\s]+([A-Za-z\u0590-\u05FF\s]+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["origin_country"] = _clean_value(m.group(1), max_len=50)
            break

    # Destination
    for pat in [
        r'(?:destination|port\s*of\s*destination|יעד|נמל\s*יעד)[:\s]+([A-Za-z\u0590-\u05FF\s,]+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["destination"] = _clean_value(m.group(1), max_len=80)
            break

    # Incoterms
    m = re.search(r'\b(EXW|FCA|FAS|FOB|CFR|CIF|CPT|CIP|DAP|DPU|DDP)\b', tu)
    if m:
        fields["incoterms"] = m.group(1)

    # Currency
    m = re.search(r'\b(USD|EUR|GBP|ILS|NIS|CNY|JPY|CHF|CAD|AUD|TRY)\b', tu)
    if m:
        fields["currency"] = m.group(1)
    elif re.search(r'[$]', t):
        fields["currency"] = "USD"
    elif re.search(r'[€]', t):
        fields["currency"] = "EUR"
    elif re.search(r'[₪]', t):
        fields["currency"] = "ILS"

    # Total value
    for pat in [
        r'(?:total|grand\s*total|total\s*amount|amount\s*due|סה"כ|סכום\s*כולל)[:\s]*'
        r'(?:[A-Z]{3}\s*)?([0-9][0-9,.\s]*[0-9])',
        r'(?:[A-Z]{3})\s*([0-9][0-9,.\s]*[0-9])\s*(?:total|grand)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["total_value"] = m.group(1).replace(" ", "").replace(",", "")
            break

    # HS codes mentioned in the invoice
    hs_codes = re.findall(r'\b(\d{4}\.\d{2}(?:\.\d{2,6})?)\b', t)
    if hs_codes:
        fields["hs_codes_mentioned"] = list(set(hs_codes))

    # Line items (simplified extraction)
    fields["line_items"] = _extract_line_items(t)

    return fields


# ── Packing List ──

def _extract_packing_list_fields(text):
    fields = {}
    t = text

    # Total packages
    for pat in [
        r'(?:total\s*(?:packages|cartons|boxes|ctns|pkgs)|סה"כ\s*(?:אריזות|קרטונים))[:\s]*(\d+)',
        r'(\d+)\s*(?:cartons|ctns|packages|boxes|pallets|pkgs)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["total_packages"] = m.group(1)
            break

    # Gross weight
    for pat in [
        r'(?:gross\s*weight|g\.?w\.?|gw|משקל\s*ברוטו)[:\s]*([0-9,.\s]+)\s*(kg|kgs|lbs|tons?)?',
        r'([0-9,.\s]+)\s*(kg|kgs)\s*(?:gross)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            val = m.group(1).strip().replace(",", "")
            unit = (m.group(2) or "kg").strip()
            fields["gross_weight"] = f"{val} {unit}"
            break

    # Net weight
    for pat in [
        r'(?:net\s*weight|n\.?w\.?|nw|משקל\s*נטו)[:\s]*([0-9,.\s]+)\s*(kg|kgs|lbs|tons?)?',
        r'([0-9,.\s]+)\s*(kg|kgs)\s*(?:net)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            val = m.group(1).strip().replace(",", "")
            unit = (m.group(2) or "kg").strip()
            fields["net_weight"] = f"{val} {unit}"
            break

    # Dimensions / CBM
    m = re.search(r'(?:cbm|cubic\s*met|volume)[:\s]*([0-9,.]+)', t, re.IGNORECASE)
    if m:
        fields["dimensions"] = f"{m.group(1)} CBM"

    # Marks & numbers
    m = re.search(r'(?:marks?\s*(?:and|&)\s*numbers?|shipping\s*marks?|סימון)[:\s]+(.+)',
                   t, re.IGNORECASE)
    if m:
        fields["marks_numbers"] = _clean_value(m.group(1), max_len=100)

    # Container numbers
    containers = re.findall(r'\b([A-Z]{4}\s*\d{7})\b', text)
    if containers:
        fields["container_numbers"] = list(set(containers))

    return fields


# ── FCL vs LCL helper ──

def _detect_lcl(text):
    """Detect LCL (Less than Container Load) from multiple signals.
    Signal A: Explicit keywords (LCL, CFS, consolidation, מיכול) → always LCL.
    Signal B: Cargo description co-occurrence (marking+dims+units+CBM) → house BL LCL.
    CFS warehouse names (Gadot, Atta, Tiran) → LCL.
    Returns True if LCL indicators found in text."""
    # Signal A: explicit keywords
    _lcl_en = r'\bLCL\b|\bCFS\b|consolidat(?:ion|ed)|less\s+than\s+container|groupage'
    _lcl_he = r'מיכול|מטען\s*חלקי|מכולה\s*משותפת'
    _cfs_names = r'\b(?:Gadot|Atta|Tiran)\b|גדות|עטא|טירן'
    if (re.search(_lcl_en, text, re.IGNORECASE) or
            re.search(_lcl_he, text) or
            re.search(_cfs_names, text, re.IGNORECASE)):
        return True

    # Signal B: house BL cargo description — marking+dims+units+CBM co-occurrence
    _desc_signals = [
        re.search(r'(?:marking|marks|סימון|סימנים)', text, re.IGNORECASE),
        re.search(r'(?:dimensions?|מידות|length.*width|ארוך.*רוחב)', text, re.IGNORECASE),
        re.search(r'(?:units?|packages?|pieces?|יחידות|חבילות|אריזות)\s*[:\s]*\d', text, re.IGNORECASE),
        re.search(r'(?:CBM|cubic\s*met|מ"ק|מטר\s*מעוקב)', text, re.IGNORECASE),
    ]
    if sum(1 for s in _desc_signals if s) >= 3:
        return True

    return False


# ── Bill of Lading ──

def _extract_bl_fields(text):
    fields = {}
    t = text

    # BL number
    for pat in [
        r'(?:b/?l\s*(?:no|number|n[°o]|#)|bill\s*of\s*lading\s*(?:no|#))[.:\s]*([A-Za-z0-9\-/]+)',
        r'(?:שטר\s*מטען\s*(?:מס[\'.]?|#))[:\s]*([A-Za-z0-9\-/]+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["bl_number"] = m.group(1).strip()
            break

    # Shipper
    m = re.search(r'(?:shipper|שולח)[:\s]+(.+?)(?:\n|consignee|notify)', t, re.IGNORECASE | re.DOTALL)
    if m:
        fields["shipper"] = _clean_multiline(m.group(1), max_len=150)

    # Consignee
    m = re.search(r'(?:consignee|נמען)[:\s]+(.+?)(?:\n\n|notify|port\s*of)', t, re.IGNORECASE | re.DOTALL)
    if m:
        fields["consignee"] = _clean_multiline(m.group(1), max_len=150)

    # Vessel
    for pat in [
        r'(?:vessel|ship|v\.?s\.?\s*name|שם\s*(?:ה)?אוניה|כלי\s*שיט)[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["vessel"] = _clean_value(m.group(1), max_len=60)
            break

    # Port of loading
    for pat in [
        r'(?:port\s*of\s*loading|pol|נמל\s*טעינה|נמל\s*מוצא)[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["port_of_loading"] = _clean_value(m.group(1), max_len=60)
            break

    # Port of discharge
    for pat in [
        r'(?:port\s*of\s*discharge|pod|port\s*of\s*destination|נמל\s*(?:ה)?פריקה|נמל\s*יעד)[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["port_of_discharge"] = _clean_value(m.group(1), max_len=60)
            break

    # Container numbers (standard format: 4 letters + 7 digits)
    containers = re.findall(r'\b([A-Z]{4}\s*\d{7})\b', text)
    if containers:
        fields["container_numbers"] = list(set(c.replace(" ", "") for c in containers))

    # Voyage number
    m = re.search(r'(?:voyage|voy)[.:\s]*([A-Za-z0-9\-]+)', t, re.IGNORECASE)
    if m:
        fields["voyage_number"] = m.group(1).strip()

    # FCL vs LCL detection
    if _detect_lcl(t):
        fields["freight_load_type"] = "LCL"

    return fields


# ── Booking Confirmation ──

def _extract_booking_fields(text):
    """Extract fields from booking confirmation / shipping instruction."""
    fields = {}
    t = text

    # Booking number — require explicit label+separator to avoid matching "Booking Confirmation"
    for pat in [
        r'(?:booking|bkg)\s*(?:no|number|n[°o]|#|ref)[.:\s]*([A-Z0-9]{6,20})',
        r'(?:booking|bkg)[.:\s#]+([A-Z0-9]{6,20})',
        r'(?:הזמנה)\s*(?:מס[\'.]?|#)?[:\s]*([A-Z0-9]{6,20})',
        r'\b(EBKG\d{6,12})\b',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["booking_number"] = m.group(1).strip()
            break

    # Vessel
    for pat in [
        r'(?:vessel|ship|m/?v|אוניה|ספינה)[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["vessel"] = _clean_value(m.group(1), max_len=60)
            break

    # Voyage
    m = re.search(r'(?:voyage|voy)[.:\s]*([A-Za-z0-9\-]+)', t, re.IGNORECASE)
    if m:
        fields["voyage"] = m.group(1).strip()

    # ETD
    for pat in [
        r'(?:ETD|expected\s*departure|departure\s*date|הפלגה)[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["etd"] = m.group(1).strip()
            break

    # ETA
    for pat in [
        r'(?:ETA|expected\s*arrival|arrival\s*date|הגעה)[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["eta"] = m.group(1).strip()
            break

    # Container type (e.g. "40HC", "20GP", "45HC")
    m = re.search(r'\b(\d{2}(?:GP|HC|OT|RF|FR|TK))\b', t)
    if m:
        fields["container_type"] = m.group(1)

    # Container quantity (e.g. "2x40HC", "1 X 20GP", "3 * 40HC")
    m = re.search(r'(\d+)\s*[xX*×]\s*(\d{2}(?:GP|HC|OT|RF|FR|TK))', t)
    if m:
        fields["container_quantity"] = int(m.group(1))
        fields["container_type"] = m.group(2)

    # Cutoff date (general cutoff if doc/container not specified)
    for pat in [
        r'(?:cut[\s\-]?off|closing|סגיר)[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["cutoff_date"] = m.group(1).strip()
            break

    # FCL vs LCL detection
    if _detect_lcl(t):
        fields["freight_load_type"] = "LCL"

    return fields


# ── Air Waybill ──

def _extract_awb_fields(text):
    fields = {}
    t = text

    # AWB number (format: XXX-XXXXXXXX)
    for pat in [
        r'(?:awb|air\s*waybill)\s*(?:no|number|n[°o]|#)?[.:\s]*(\d{3}[\s-]?\d{7,8})',
        r'\b(\d{3}[\s-]\d{4}[\s-]?\d{4})\b',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["awb_number"] = m.group(1).strip()
            break

    # Shipper
    m = re.search(r'(?:shipper|שולח)[:\s]+(.+?)(?:\n\n|consignee)', t, re.IGNORECASE | re.DOTALL)
    if m:
        fields["shipper"] = _clean_multiline(m.group(1), max_len=150)

    # Consignee
    m = re.search(r'(?:consignee|נמען)[:\s]+(.+?)(?:\n\n|notify|airport)', t, re.IGNORECASE | re.DOTALL)
    if m:
        fields["consignee"] = _clean_multiline(m.group(1), max_len=150)

    # Airport of departure
    for pat in [
        r'(?:airport\s*of\s*departure|departure\s*airport|origin\s*airport)[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["airport_departure"] = _clean_value(m.group(1), max_len=60)
            break

    # Airport of destination
    for pat in [
        r'(?:airport\s*of\s*destination|destination\s*airport|dest\.?\s*airport)[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["airport_destination"] = _clean_value(m.group(1), max_len=60)
            break

    # Flight number
    m = re.search(r'(?:flight|flt)\s*(?:no|#)?[.:\s]*([A-Z]{2}\s*\d{2,5})', t, re.IGNORECASE)
    if m:
        fields["flight_number"] = m.group(1).strip()

    return fields


# ── Certificate of Origin ──

def _extract_coo_fields(text):
    fields = {}
    t = text

    # Certificate number
    for pat in [
        r'(?:certificate|cert|תעודה)\s*(?:no|number|n[°o]|#|מס[\'.]?)[.:\s]*([A-Za-z0-9\-/]+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["certificate_number"] = m.group(1).strip()
            break

    # Country of origin
    for pat in [
        r'(?:country\s*of\s*origin|goods\s*originating\s*(?:in|from)|ארץ\s*(?:ה)?מקור)[:\s]+([A-Za-z\u0590-\u05FF\s]+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["country_of_origin"] = _clean_value(m.group(1), max_len=50)
            break

    # Issuing authority
    for pat in [
        r'(?:issued\s*by|issuing\s*authority|chamber\s*of\s*commerce|גורם\s*מנפיק|לשכת\s*המסחר)[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["issuing_authority"] = _clean_value(m.group(1), max_len=100)
            break

    # Exporter
    m = re.search(r'(?:exporter|shipper|יצואן|שולח)[:\s]+(.+)', t, re.IGNORECASE)
    if m:
        fields["exporter"] = _clean_value(m.group(1), max_len=120)

    # Goods description
    m = re.search(r'(?:description\s*of\s*goods|goods\s*description|תיאור\s*(?:ה)?טובין)[:\s]+(.+)',
                   t, re.IGNORECASE)
    if m:
        fields["goods_description"] = _clean_value(m.group(1), max_len=200)

    return fields


# ── EUR.1 ──

def _extract_eur1_fields(text):
    fields = _extract_coo_fields(text)  # Base fields same as COO

    t = text

    # Consignee (EUR.1 box 2)
    m = re.search(r'(?:consignee|נמען)[:\s]+(.+)', t, re.IGNORECASE)
    if m:
        fields["consignee"] = _clean_value(m.group(1), max_len=120)

    # Cumulation type
    m = re.search(r'(?:cumulation)[:\s]+(.+)', t, re.IGNORECASE)
    if m:
        fields["cumulation"] = _clean_value(m.group(1), max_len=80)

    return fields


# ── Health Certificate ──

def _extract_health_cert_fields(text):
    fields = {}
    t = text

    # Certificate number
    for pat in [
        r'(?:certificate|cert|תעודה)\s*(?:no|number|n[°o]|#|מס[\'.]?)[.:\s]*([A-Za-z0-9\-/]+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["certificate_number"] = m.group(1).strip()
            break

    # Issuing authority
    for pat in [
        r'(?:issued\s*by|issuing\s*authority|competent\s*authority|גורם\s*מנפיק|רשות\s*מוסמכת)[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["issuing_authority"] = _clean_value(m.group(1), max_len=100)
            break

    # Country of origin
    for pat in [
        r'(?:country\s*of\s*origin|exporting\s*country|ארץ\s*(?:ה)?מקור)[:\s]+([A-Za-z\u0590-\u05FF\s]+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["country_of_origin"] = _clean_value(m.group(1), max_len=50)
            break

    # Goods description
    m = re.search(r'(?:description\s*of\s*(?:goods|commodity|product)|תיאור\s*(?:ה)?(?:טובין|מוצר|סחורה))[:\s]+(.+)',
                   t, re.IGNORECASE)
    if m:
        fields["goods_description"] = _clean_value(m.group(1), max_len=200)

    # Issue date
    fields["issue_date"] = _find_date(t, prefix_patterns=[
        r'(?:date\s*of\s*issue|issue\s*date|date\s*issued|תאריך\s*הנפקה)',
    ])

    # Expiry date
    fields["expiry_date"] = _find_date(t, prefix_patterns=[
        r'(?:expir|valid\s*until|תוקף\s*עד)',
    ])

    return fields


# ── Insurance ──

def _extract_insurance_fields(text):
    fields = {}
    t = text

    # Policy number
    for pat in [
        r'(?:policy|certificate)\s*(?:no|number|n[°o]|#)[.:\s]*([A-Za-z0-9\-/]+)',
        r'(?:פוליסה|תעודה)\s*(?:מס[\'.]?|#)[:\s]*([A-Za-z0-9\-/]+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["policy_number"] = m.group(1).strip()
            break

    # Insured value
    for pat in [
        r'(?:insured\s*(?:value|amount)|sum\s*insured|ערך\s*מבוטח)[:\s]*'
        r'(?:[A-Z]{3}\s*)?([0-9][0-9,.\s]*[0-9])',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["insured_value"] = m.group(1).replace(" ", "").replace(",", "")
            break

    # Coverage type
    for pat in [
        r'(?:coverage|type\s*of\s*cover|כיסוי)[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["coverage_type"] = _clean_value(m.group(1), max_len=80)
            break

    # Insurer name
    for pat in [
        r'(?:insurer|underwriter|חברת\s*ביטוח|מבטח)[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["insurer_name"] = _clean_value(m.group(1), max_len=100)
            break

    return fields


# ── Delivery Order ──

def _extract_do_fields(text):
    fields = {}
    t = text

    # DO number
    for pat in [
        r'(?:d/?o|delivery\s*order)\s*(?:no|number|n[°o]|#)[.:\s]*([A-Za-z0-9\-/]+)',
        r'(?:פקודת\s*מסירה)\s*(?:מס[\'.]?|#)?[:\s]*([A-Za-z0-9\-/]+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["do_number"] = m.group(1).strip()
            break

    # Consignee
    m = re.search(r'(?:consignee|deliver\s*to|נמען|למסור\s*ל)[:\s]+(.+)', t, re.IGNORECASE)
    if m:
        fields["consignee"] = _clean_value(m.group(1), max_len=120)

    # BL reference
    m = re.search(r'(?:b/?l|bill\s*of\s*lading)\s*(?:ref|no|#)?[.:\s]*([A-Za-z0-9\-/]+)', t, re.IGNORECASE)
    if m:
        fields["bl_reference"] = m.group(1).strip()

    # Vessel
    m = re.search(r'(?:vessel|ship|אוניה)[:\s]+(.+)', t, re.IGNORECASE)
    if m:
        fields["vessel"] = _clean_value(m.group(1), max_len=60)

    # Pickup location / terminal
    for pat in [
        r'(?:pickup|collection|collect\s*from|terminal|warehouse|מחסן|נמל)[:\s]+(.+)',
        r'(?:איסוף\s*מ|מקום\s*איסוף)[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["pickup_location"] = _clean_value(m.group(1), max_len=120)
            break

    # Release date
    for pat in [
        r'(?:release\s*date|date\s*of\s*release|valid\s*from|תאריך\s*שחרור)[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["release_date"] = m.group(1).strip()
            break

    # Agent name (shipping agent issuing the D/O)
    for pat in [
        r'(?:shipping\s*agent|סוכן\s*אוניות)[:\s]+(.+)',
        r'(?:issued\s*by|מונפק\s*(?:ע"י|על\s*ידי))[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["agent_name"] = _clean_value(m.group(1), max_len=80)
            break

    # FCL vs LCL detection
    if _detect_lcl(t):
        fields["freight_load_type"] = "LCL"

    return fields


# ── Air Delivery Order ──

def _extract_air_do_fields(text):
    """Extract fields from air cargo delivery order / release notice."""
    fields = {}
    t = text

    # AWB reference (format: XXX-XXXXXXXX or XXX XXXXXXXX)
    for pat in [
        r'(?:awb|air\s*waybill)\s*(?:no|number|n[°o]|#|ref)?[.:\s]*(\d{3}[\s-]?\d{7,8})',
        r'(?:שטר\s*(?:מטען\s*)?אווירי)\s*(?:מס[\'.]?|#)?[:\s]*(\d{3}[\s-]?\d{7,8})',
        r'\b(\d{3}-\d{8})\b',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["awb_reference"] = m.group(1).strip()
            break

    # Consignee
    m = re.search(r'(?:consignee|deliver\s*to|נמען|למסור\s*ל)[:\s]+(.+)', t, re.IGNORECASE)
    if m:
        fields["consignee"] = _clean_value(m.group(1), max_len=120)

    # Terminal (Maman / Swissport / cargo terminal)
    for pat in [
        r'(?:terminal|cargo\s*terminal|מסוף)[:\s]+(.+)',
        r'\b(maman|swissport|ממן|סוויספורט)\b',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["terminal"] = _clean_value(m.group(1), max_len=60)
            break

    # Release status
    for pat in [
        r'(?:release\s*status|status|סטטוס\s*שחרור|מצב)[:\s]+(.+)',
        r'\b(released|שוחרר|hold|מעוכב|pending|ממתין|ready\s*for\s*collection|מוכן\s*למסירה)\b',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["release_status"] = _clean_value(m.group(1), max_len=40)
            break

    # Storage fees
    for pat in [
        r'(?:storage\s*fee|storage\s*charge|דמי\s*אחסנה|אחסנה)[:\s]*'
        r'(?:[A-Z]{3}\s*)?([0-9][0-9,.\s]*[0-9])',
        r'(?:storage|אחסנה)[:\s]+(?:USD|ILS|NIS|₪|\$)?\s*([0-9][0-9,.]*)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["storage_fees"] = m.group(1).replace(" ", "").strip()
            break

    # Flight number
    m = re.search(r'(?:flight|flt|טיסה)\s*(?:no|#)?[.:\s]*([A-Z]{2}\s*\d{2,5})', t, re.IGNORECASE)
    if m:
        fields["flight_number"] = m.group(1).strip()

    # Agent name
    for pat in [
        r'(?:agent|סוכן|issued\s*by|מונפק\s*(?:ע"י|על\s*ידי))[:\s]+(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            fields["agent_name"] = _clean_value(m.group(1), max_len=80)
            break

    return fields


# ── Generic (unknown type) ──

def _extract_generic_fields(text):
    """Extract whatever we can from an unknown document type."""
    fields = {}
    t = text

    # Dates
    dates = re.findall(r'\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}', t)
    if dates:
        fields["dates_found"] = dates[:5]

    # Currency amounts
    amounts = re.findall(
        r'(?:USD|EUR|ILS|GBP|NIS|\$|€|₪)\s*[0-9][0-9,.\s]*[0-9]', t, re.IGNORECASE
    )
    if not amounts:
        amounts = re.findall(
            r'[0-9][0-9,.\s]*[0-9]\s*(?:USD|EUR|ILS|GBP|NIS)', t, re.IGNORECASE
        )
    if amounts:
        fields["amounts_found"] = [a.strip() for a in amounts[:5]]

    # HS codes
    hs_codes = re.findall(r'\b(\d{4}\.\d{2}(?:\.\d{2,6})?)\b', t)
    if hs_codes:
        fields["hs_codes_found"] = list(set(hs_codes))

    # Company names (heuristic: lines with "Ltd", "Inc", "בע\"מ")
    companies = re.findall(r'(.{5,60}(?:Ltd\.?|Inc\.?|Corp\.?|Co\.?|בע"מ|בע״מ))', t)
    if companies:
        fields["companies_found"] = [c.strip() for c in companies[:5]]

    return fields


# ═══════════════════════════════════════════════════════════════
#  3. ASSESS DOCUMENT COMPLETENESS
# ═══════════════════════════════════════════════════════════════

def assess_document_completeness(extracted_fields, doc_type):
    """
    Assess whether the extracted fields meet completeness requirements
    for the given document type.

    Args:
        extracted_fields: dict — from extract_structured_fields()
        doc_type: str — document type

    Returns:
        dict with:
          score: int (0-100)
          present: [{field, importance, value_preview}]
          missing: [{field, importance, name_he}]
          is_complete: bool
          summary_he: str
    """
    requirements = _REQUIRED_FIELDS.get(doc_type, [])
    if not requirements:
        return {
            "score": 50,
            "present": [],
            "missing": [],
            "is_complete": False,
            "summary_he": "סוג מסמך לא מוכר — לא ניתן להעריך שלמות",
        }

    present = []
    missing = []
    weights = {"critical": 3, "important": 2, "optional": 1}
    total_weight = 0
    present_weight = 0

    for field_name, importance in requirements:
        w = weights.get(importance, 1)
        total_weight += w

        value = extracted_fields.get(field_name)
        # For line_items, check if non-empty list
        if field_name == "line_items" and isinstance(value, list):
            has_value = len(value) > 0
        elif field_name == "container_numbers" and isinstance(value, list):
            has_value = len(value) > 0
        else:
            has_value = bool(value)

        if has_value:
            present_weight += w
            preview = str(value)[:60] if not isinstance(value, list) else f"{len(value)} items"
            present.append({
                "field": field_name,
                "importance": importance,
                "value_preview": preview,
            })
        else:
            missing.append({
                "field": field_name,
                "importance": importance,
                "name_he": _field_name_he(field_name),
            })

    score = int((present_weight / max(total_weight, 1)) * 100)
    critical_missing = [m for m in missing if m["importance"] == "critical"]
    is_complete = score >= 70 and len(critical_missing) == 0

    # Build Hebrew summary
    doc_info = _DOC_TYPE_SIGNALS.get(doc_type, {})
    doc_name = doc_info.get("name_he", doc_type)
    parts = [f"{doc_name}: ציון שלמות {score}/100"]
    if critical_missing:
        names = ", ".join(m["name_he"] for m in critical_missing)
        parts.append(f"שדות קריטיים חסרים: {names}")
    elif missing:
        names = ", ".join(m["name_he"] for m in missing[:3])
        parts.append(f"שדות חסרים: {names}")
    else:
        parts.append("כל השדות הנדרשים נמצאו")

    return {
        "score": score,
        "present": present,
        "missing": missing,
        "is_complete": is_complete,
        "summary_he": ". ".join(parts),
    }


# ═══════════════════════════════════════════════════════════════
#  4. CONVENIENCE: PARSE DOCUMENT (all 3 steps)
# ═══════════════════════════════════════════════════════════════

def parse_document(text, filename=""):
    """
    Full pipeline: identify type, extract fields, assess completeness.

    Args:
        text: str — extracted text content
        filename: str — original filename

    Returns:
        dict with:
          doc_type: str
          type_info: dict (from identify_document_type)
          fields: dict (from extract_structured_fields)
          completeness: dict (from assess_document_completeness)
    """
    type_info = identify_document_type(text, filename)
    doc_type = type_info["doc_type"]
    fields = extract_structured_fields(text, doc_type)
    completeness = assess_document_completeness(fields, doc_type)

    return {
        "doc_type": doc_type,
        "type_info": type_info,
        "fields": fields,
        "completeness": completeness,
    }


def parse_all_documents(extracted_text):
    """
    Parse multi-document extracted text (split on === filename === markers).
    Returns list of parse results, one per document segment.
    """
    results = []

    # Split on the === filename === pattern used by rcb_helpers
    segments = re.split(r'===\s*(.+?)\s*===', extracted_text or "")

    # segments[0] = text before first ===, segments[1] = first filename,
    # segments[2] = first content, segments[3] = second filename, etc.
    i = 1
    while i < len(segments) - 1:
        filename = segments[i].strip()
        content = segments[i + 1].strip()

        if content and filename != "Email Body":
            result = parse_document(content, filename)
            result["filename"] = filename
            results.append(result)
        i += 2

    return results


# ═══════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════

def _clean_value(text, max_len=100):
    """Clean an extracted value: strip, collapse whitespace, truncate."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    # Cut at first newline or pipe (table separator)
    for sep in ['\n', '|', '\t']:
        if sep in text:
            text = text[:text.index(sep)].strip()
    return text[:max_len]


def _clean_multiline(text, max_len=150):
    """Clean a multiline value (addresses, etc.)."""
    if not text:
        return ""
    text = re.sub(r'\n+', ', ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.rstrip(',').strip()
    return text[:max_len]


def _find_date(text, prefix_patterns=None):
    """Find a date in text, optionally after a prefix pattern."""
    date_re = r'(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})'

    if prefix_patterns:
        for prefix in prefix_patterns:
            m = re.search(prefix + r'[:\s]*' + date_re, text, re.IGNORECASE)
            if m:
                return m.group(1)

    # Fallback: first date-looking thing
    m = re.search(date_re, text)
    if m:
        return m.group(1)
    return ""


def _extract_line_items(text):
    """Extract line items from invoice text (best-effort regex)."""
    items = []

    # Pattern 1: table rows with description | qty | price pattern
    # Look for lines with at least a number and some description
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line or len(line) < 15:
            continue

        # Skip header-like lines
        if re.search(r'(?:description|item|quantity|price|amount|total)', line, re.IGNORECASE) \
           and not re.search(r'\d{3,}', line):
            continue

        # Look for lines with a price-like number at the end
        m = re.search(
            r'(.{10,80}?)\s+(\d+(?:[.,]\d+)?)\s+(\d+(?:[.,]\d+)?)\s+(\d+(?:[.,]\d+)?)\s*$',
            line
        )
        if m:
            items.append({
                "description": m.group(1).strip(),
                "quantity": m.group(2),
                "unit_price": m.group(3),
                "total": m.group(4),
            })
            continue

        # Simpler: description followed by amount
        m = re.search(r'(.{10,80}?)\s+([0-9,]+\.?\d*)\s*$', line)
        if m and not items:  # Only if we haven't found structured items
            desc = m.group(1).strip()
            # Skip if desc is just numbers or too short
            if re.search(r'[a-zA-Z\u0590-\u05FF]{3,}', desc):
                items.append({
                    "description": desc,
                    "total": m.group(2),
                })

        # Check for HS code in the line
        if items:
            hs_m = re.search(r'\b(\d{4}\.\d{2}(?:\.\d{2,6})?)\b', line)
            if hs_m and items[-1].get("description", "") in line:
                items[-1]["hs_code"] = hs_m.group(1)

    return items[:50]  # Cap at 50 items


# Hebrew field name mapping for completeness report
_FIELD_NAMES_HE = {
    "invoice_number": "מספר חשבונית",
    "date": "תאריך",
    "seller_name": "שם המוכר",
    "buyer_name": "שם הקונה",
    "origin_country": "ארץ מקור",
    "destination": "יעד",
    "incoterms": "תנאי מכר",
    "currency": "מטבע",
    "total_value": "ערך כולל",
    "line_items": "פירוט פריטים",
    "total_packages": "סה\"כ אריזות",
    "gross_weight": "משקל ברוטו",
    "net_weight": "משקל נטו",
    "dimensions": "מידות/נפח",
    "marks_numbers": "סימנים ומספרים",
    "bl_number": "מספר שטר מטען",
    "shipper": "שולח",
    "consignee": "נמען",
    "vessel": "שם אוניה",
    "port_of_loading": "נמל טעינה",
    "port_of_discharge": "נמל פריקה",
    "container_numbers": "מספרי מכולות",
    "voyage_number": "מספר מסע",
    "awb_number": "מספר שטר מטען אווירי",
    "airport_departure": "שדה תעופה מוצא",
    "airport_destination": "שדה תעופה יעד",
    "flight_number": "מספר טיסה",
    "certificate_number": "מספר תעודה",
    "country_of_origin": "ארץ מקור",
    "issuing_authority": "גורם מנפיק",
    "goods_description": "תיאור הטובין",
    "exporter": "יצואן",
    "cumulation": "צבירה",
    "issue_date": "תאריך הנפקה",
    "expiry_date": "תאריך תוקף",
    "policy_number": "מספר פוליסה",
    "insured_value": "ערך מבוטח",
    "coverage_type": "סוג כיסוי",
    "insurer_name": "חברת ביטוח",
    "do_number": "מספר פקודת מסירה",
    "bl_reference": "אסמכתא שטר מטען",
    "hs_codes_mentioned": "קודי HS שנמצאו",
}


def _field_name_he(field_name):
    """Get Hebrew name for a field."""
    return _FIELD_NAMES_HE.get(field_name, field_name)
