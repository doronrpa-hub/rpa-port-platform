"""
RCB Intelligence Module — The System's Own Brain
=================================================
Searches the system's OWN Firestore knowledge BEFORE calling any AI.
Pure database lookups, zero AI calls.

Functions:
1. pre_classify()       — candidate HS codes from past knowledge
2. lookup_regulatory()  — ministry/permit requirements for an HS code
3. lookup_fta()         — FTA eligibility for HS + origin country
4. validate_documents() — what doc types are present vs missing
"""

import re
import requests
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════
#  1. PRE-CLASSIFY — search own knowledge before AI
# ═══════════════════════════════════════════════════════════════

def pre_classify(db, item_description, origin_country=""):
    """
    Search the system's own Firestore knowledge for candidate HS codes
    BEFORE calling any AI model.

    Searches:
      - classification_knowledge (past classifications, corrections)
      - classification_rules (keyword patterns)
      - tariff / tariff_chapters (HS description matching)
      - regulatory_requirements (by HS chapter)
      - fta_agreements (by origin country)

    Returns:
        dict with:
          candidates: [{hs_code, confidence, source, description, duty_rate, reasoning}]
          regulatory: [{ministry, requirements, hs_chapter}]
          fta: {agreement, preferential_rate, origin_proof, eligible}
          context_text: str — ready to inject into AI prompt
    """
    print(f"  🧠 INTELLIGENCE: Pre-classifying '{item_description[:60]}' from '{origin_country}'")

    candidates = []
    regulatory_hits = []
    fta_info = None
    desc_lower = item_description.lower()
    keywords = _extract_keywords(item_description)

    # ── Step 1: classification_knowledge (past items) ──
    ck_results = _search_classification_knowledge(db, keywords, desc_lower)
    for r in ck_results:
        candidates.append({
            "hs_code": r["hs_code"],
            "confidence": r["score"],
            "source": "past_classification",
            "description": r.get("description", ""),
            "duty_rate": r.get("duty_rate", ""),
            "reasoning": f"Similar past item (score {r['score']}): {r.get('description', '')[:80]}",
            "is_correction": r.get("is_correction", False),
            "usage_count": r.get("usage_count", 0),
        })

    # ── Step 2: classification_rules (keyword patterns) ──
    rule_results = _search_classification_rules(db, desc_lower)
    for r in rule_results:
        # Don't duplicate if same heading already found with higher confidence
        heading = r["hs_heading"]
        already = any(c["hs_code"].startswith(heading) for c in candidates if c["confidence"] > r["confidence"])
        if not already:
            candidates.append({
                "hs_code": heading,
                "confidence": r["confidence"],
                "source": "keyword_rule",
                "description": r.get("description", ""),
                "duty_rate": "",
                "reasoning": f"Keyword pattern match: {r.get('pattern', '')[:60]}",
                "notes": r.get("notes", ""),
            })

    # ── Step 3: tariff + tariff_chapters (HS description matching) ──
    tariff_results = _search_tariff(db, keywords)
    for r in tariff_results:
        # Don't duplicate if same code already found
        already = any(c["hs_code"] == r["hs_code"] for c in candidates)
        if not already:
            candidates.append({
                "hs_code": r["hs_code"],
                "confidence": r["score"],
                "source": "tariff_db",
                "description": r.get("description_he", r.get("description_en", "")),
                "duty_rate": r.get("duty_rate", ""),
                "reasoning": f"Tariff description match (score {r['score']})",
            })

    # Sort by confidence descending
    candidates.sort(key=lambda c: c["confidence"], reverse=True)
    candidates = candidates[:10]  # Top 10

    # ── Step 4: regulatory_requirements (by HS chapter from top candidates) ──
    chapters_checked = set()
    for c in candidates[:5]:
        hs = str(c["hs_code"]).replace(".", "").replace(" ", "")
        chapter = hs[:2] if len(hs) >= 2 else ""
        if chapter and chapter not in chapters_checked:
            chapters_checked.add(chapter)
            reg = _lookup_regulatory_by_chapter(db, chapter)
            if reg:
                regulatory_hits.append(reg)

    # ── Step 5: fta_agreements (by origin country) ──
    if origin_country:
        fta_info = _search_fta_by_country(db, origin_country)

    # Build context text for AI
    context_text = _build_pre_classify_context(candidates, regulatory_hits, fta_info)

    result = {
        "candidates": candidates,
        "regulatory": regulatory_hits,
        "fta": fta_info,
        "context_text": context_text,
        "stats": {
            "candidates_found": len(candidates),
            "top_confidence": candidates[0]["confidence"] if candidates else 0,
            "regulatory_hits": len(regulatory_hits),
            "fta_eligible": bool(fta_info and fta_info.get("eligible")),
        },
    }

    top = candidates[0] if candidates else None
    if top:
        print(f"  🧠 INTELLIGENCE: Top candidate HS {top['hs_code']} "
              f"({top['confidence']}% confidence, source: {top['source']})")
    else:
        print(f"  🧠 INTELLIGENCE: No candidates found in own knowledge")

    return result


# ═══════════════════════════════════════════════════════════════
#  2. LOOKUP REGULATORY — ministries, permits, documents needed
# ═══════════════════════════════════════════════════════════════

def lookup_regulatory(db, hs_code):
    """
    Given an HS code, look up what ministries, documents, and approvals are needed.

    Searches:
      - regulatory_requirements (by HS chapter)
      - ministry_index (by chapter)

    Returns:
        dict with:
          hs_code, chapter, cargo, cargo_he,
          ministries: [{name, requirements, urls}],
          free_import_order: bool,
          notes: str
    """
    hs_clean = str(hs_code).replace(".", "").replace(" ", "").replace("/", "")
    chapter = hs_clean[:2].lstrip("0") or hs_clean[:2]
    chapter_padded = chapter.zfill(2)

    print(f"  🧠 INTELLIGENCE: Regulatory lookup for HS {hs_code} (chapter {chapter_padded})")

    result = {
        "hs_code": hs_code,
        "chapter": chapter_padded,
        "cargo": "",
        "cargo_he": "",
        "ministries": [],
        "free_import_order": False,
        "notes": "",
    }

    # Search regulatory_requirements — documents keyed by chapter ranges
    try:
        docs = db.collection("regulatory_requirements").stream()
        for doc in docs:
            data = doc.to_dict()
            chapters = data.get("hs_chapters", [])
            if chapter_padded in chapters or chapter in chapters:
                result["cargo"] = data.get("cargo", "")
                result["cargo_he"] = data.get("cargo_he", "")
                result["free_import_order"] = data.get("free_import_order", False)
                result["notes"] = data.get("notes", "")

                for ministry_name in data.get("ministries", []):
                    result["ministries"].append({
                        "name": ministry_name,
                        "requirements": data.get("requirements", []),
                        "urls": data.get("urls", []),
                    })
                break  # First match is the specific one
    except Exception as e:
        print(f"    ⚠️ regulatory_requirements query error: {e}")

    # Also check ministry_index for this chapter
    try:
        mi_doc = db.collection("ministry_index").document(f"chapter_{chapter_padded}").get()
        if mi_doc.exists:
            mi_data = mi_doc.to_dict()
            # Merge any ministries not already found
            existing_names = {m["name"] for m in result["ministries"]}
            for m_name in mi_data.get("ministries", []):
                if m_name not in existing_names:
                    result["ministries"].append({
                        "name": m_name,
                        "requirements": [],
                        "urls": [],
                    })
            if not result["cargo"]:
                result["cargo"] = mi_data.get("cargo", "")
                result["cargo_he"] = mi_data.get("cargo_he", "")
    except Exception as e:
        print(f"    ⚠️ ministry_index query error: {e}")

    if result["ministries"]:
        names = ", ".join(m["name"] for m in result["ministries"])
        print(f"  🧠 INTELLIGENCE: Regulatory — {names}")
    else:
        print(f"  🧠 INTELLIGENCE: No specific regulatory requirements for chapter {chapter_padded}")

    return result


# ═══════════════════════════════════════════════════════════════
#  3. LOOKUP FTA — preferential rates, origin proof needed
# ═══════════════════════════════════════════════════════════════

def lookup_fta(db, hs_code, origin_country):
    """
    Given HS code and origin country, look up FTA eligibility.

    Searches:
      - fta_agreements (by country code or country name)

    Returns:
        dict with:
          eligible: bool,
          agreement_name, agreement_name_he,
          preferential_rate, origin_proof, origin_proof_alt,
          cumulation, legal_basis, notes
    """
    print(f"  🧠 INTELLIGENCE: FTA lookup for HS {hs_code} from '{origin_country}'")

    result = {
        "hs_code": hs_code,
        "origin_country": origin_country,
        "eligible": False,
        "agreement_name": "",
        "agreement_name_he": "",
        "preferential_rate": "",
        "origin_proof": "",
        "origin_proof_alt": "",
        "cumulation": "",
        "legal_basis": "",
        "notes": "",
    }

    if not origin_country:
        return result

    fta = _search_fta_by_country(db, origin_country)
    if fta:
        result.update(fta)

    if result["eligible"]:
        print(f"  🧠 INTELLIGENCE: FTA eligible — {result['agreement_name']} "
              f"({result['preferential_rate']})")
    else:
        print(f"  🧠 INTELLIGENCE: No FTA found for '{origin_country}'")

    return result


# ═══════════════════════════════════════════════════════════════
#  4. VALIDATE DOCUMENTS — check what's present vs missing
# ═══════════════════════════════════════════════════════════════

# Document type detection patterns (Hebrew + English)
_DOC_PATTERNS = {
    "commercial_invoice": {
        "name_he": "חשבונית מסחרית",
        "name_en": "Commercial Invoice",
        "patterns": [
            r"commercial\s*invoice", r"proforma\s*invoice", r"invoice\s*n[o°#]",
            r"חשבונית", r"חשבון\s*מסחרי",
            r"invoice\s*date", r"invoice\s*amount", r"total\s*value",
            r"unit\s*price", r"quantity",
        ],
    },
    "packing_list": {
        "name_he": "רשימת אריזה",
        "name_en": "Packing List",
        "patterns": [
            r"packing\s*list", r"רשימת\s*אריזה",
            r"gross\s*weight", r"net\s*weight", r"carton",
            r"package\s*n[o°#]", r"dimensions", r"cbm",
        ],
    },
    "bill_of_lading": {
        "name_he": "שטר מטען",
        "name_en": "Bill of Lading",
        "patterns": [
            r"bill\s*of\s*lading", r"b/?l\s*n[o°#]", r"shipper",
            r"consignee", r"notify\s*party", r"port\s*of\s*loading",
            r"port\s*of\s*discharge", r"שטר\s*מטען",
            r"ocean\s*bill", r"house\s*b/?l", r"master\s*b/?l",
        ],
    },
    "air_waybill": {
        "name_he": "שטר מטען אווירי",
        "name_en": "Air Waybill",
        "patterns": [
            r"air\s*waybill", r"awb", r"airway\s*bill",
            r"שטר\s*מטען\s*אווירי", r"flight\s*n[o°#]",
            r"airport\s*of\s*departure", r"airport\s*of\s*destination",
        ],
    },
    "certificate_of_origin": {
        "name_he": "תעודת מקור",
        "name_en": "Certificate of Origin",
        "patterns": [
            r"certificate\s*of\s*origin", r"תעודת\s*מקור",
            r"country\s*of\s*origin", r"ארץ\s*המקור",
            r"origin\s*criterion", r"originating\s*product",
        ],
    },
    "eur1": {
        "name_he": "EUR.1",
        "name_en": "EUR.1 Movement Certificate",
        "patterns": [
            r"eur\.?\s*1", r"movement\s*certificate",
            r"euro[- ]?mediterranean", r"cumulation",
            r"approved\s*exporter", r"invoice\s*declaration",
        ],
    },
    "health_certificate": {
        "name_he": "תעודת בריאות",
        "name_en": "Health Certificate",
        "patterns": [
            r"health\s*certificate", r"תעודת\s*בריאות",
            r"sanitary", r"phytosanitary", r"veterinary\s*certificate",
            r"תעודה\s*וטרינרית", r"תעודה\s*צמחית",
        ],
    },
    "insurance_certificate": {
        "name_he": "תעודת ביטוח",
        "name_en": "Insurance Certificate",
        "patterns": [
            r"insurance\s*certificate", r"insurance\s*policy",
            r"תעודת\s*ביטוח", r"פוליסת\s*ביטוח",
            r"insured\s*value", r"premium",
        ],
    },
    "lab_report": {
        "name_he": "דוח מעבדה",
        "name_en": "Lab/Test Report",
        "patterns": [
            r"test\s*report", r"lab\s*report", r"analysis\s*report",
            r"דוח\s*מעבדה", r"דוח\s*בדיקה",
            r"certificate\s*of\s*analysis", r"coa\b",
            r"intertek", r"sgs\b", r"tuv\b", r"bureau\s*veritas",
        ],
    },
    "import_license": {
        "name_he": "רישיון יבוא",
        "name_en": "Import License/Permit",
        "patterns": [
            r"import\s*license", r"import\s*permit",
            r"רישיון\s*יבוא", r"היתר\s*יבוא",
            r"free\s*import\s*order", r"צו\s*יבוא\s*חופשי",
        ],
    },
    "customs_declaration": {
        "name_he": "רשימון מכס",
        "name_en": "Customs Declaration",
        "patterns": [
            r"customs\s*declaration", r"רשימון",
            r"import\s*declaration", r"entry\s*summary",
        ],
    },
}

# Minimum documents typically required for import clearance
_REQUIRED_FOR_IMPORT = [
    "commercial_invoice",
    "packing_list",
    "bill_of_lading",  # or air_waybill
]

_REQUIRED_FOR_FTA = [
    "certificate_of_origin",  # or eur1
]


def validate_documents(extracted_text, direction="import", has_fta=False):
    """
    Check what document types are present in the extracted text.

    Args:
        extracted_text: str — all extracted text from attachments
        direction: "import" or "export"
        has_fta: bool — if True, also check for origin proof documents

    Returns:
        dict with:
          present: [{doc_type, name_he, name_en, confidence}]
          missing: [{doc_type, name_he, name_en, importance}]
          score: int (0-100)
          summary_he: str
    """
    print(f"  🧠 INTELLIGENCE: Validating documents (direction={direction}, fta={has_fta})")

    text_lower = extracted_text.lower() if extracted_text else ""
    present = []
    detected_types = set()

    # Check each document type
    for doc_type, info in _DOC_PATTERNS.items():
        match_count = 0
        for pattern in info["patterns"]:
            if re.search(pattern, text_lower):
                match_count += 1

        if match_count >= 2:
            confidence = min(95, 50 + match_count * 15)
            present.append({
                "doc_type": doc_type,
                "name_he": info["name_he"],
                "name_en": info["name_en"],
                "confidence": confidence,
            })
            detected_types.add(doc_type)
        elif match_count == 1:
            present.append({
                "doc_type": doc_type,
                "name_he": info["name_he"],
                "name_en": info["name_en"],
                "confidence": 40,
            })
            detected_types.add(doc_type)

    # Determine what's missing
    missing = []

    if direction == "import":
        for req_type in _REQUIRED_FOR_IMPORT:
            if req_type not in detected_types:
                # BL or AWB — either is fine
                if req_type == "bill_of_lading" and "air_waybill" in detected_types:
                    continue
                info = _DOC_PATTERNS[req_type]
                missing.append({
                    "doc_type": req_type,
                    "name_he": info["name_he"],
                    "name_en": info["name_en"],
                    "importance": "critical",
                })

        if has_fta:
            has_origin_proof = ("certificate_of_origin" in detected_types
                                or "eur1" in detected_types)
            if not has_origin_proof:
                missing.append({
                    "doc_type": "origin_proof",
                    "name_he": "תעודת מקור / EUR.1",
                    "name_en": "Certificate of Origin / EUR.1",
                    "importance": "important_for_fta",
                })

    # Calculate score
    total_required = len(_REQUIRED_FOR_IMPORT)
    if has_fta:
        total_required += 1
    found_required = total_required - len(missing)
    score = int((found_required / max(total_required, 1)) * 100)

    # Bonus for extra documents
    extras = len(detected_types) - found_required
    if extras > 0:
        score = min(100, score + extras * 5)

    summary_parts = []
    if present:
        names = ", ".join(p["name_he"] for p in present)
        summary_parts.append(f"מסמכים שנמצאו: {names}")
    if missing:
        names = ", ".join(m["name_he"] for m in missing)
        summary_parts.append(f"מסמכים חסרים: {names}")

    result = {
        "present": present,
        "missing": missing,
        "score": score,
        "summary_he": ". ".join(summary_parts),
    }

    print(f"  🧠 INTELLIGENCE: Documents — {len(present)} found, "
          f"{len(missing)} missing, score {score}/100")

    return result


# ═══════════════════════════════════════════════════════════════
#  5. MINISTRY ROUTING — HS chapter → specific ministry guidance
# ═══════════════════════════════════════════════════════════════

# Detailed ministry routing table with procedures, docs, URLs per chapter range
_MINISTRY_ROUTES = {
    "01": {
        "cargo_he": "בעלי חיים חיים",
        "risk": "high",
        "ministries": [
            {"name": "Veterinary Services", "name_he": "שירותים וטרינריים",
             "url": "https://www.gov.il/he/departments/Units/veterinary_services",
             "documents": ["Import permit", "Health certificate from origin", "Quarantine clearance"],
             "documents_he": ["היתר יבוא", "תעודת בריאות מארץ המקור", "אישור הסגר"],
             "procedure": "Apply for import permit BEFORE shipping. Pre-arrival notification 48h."},
        ],
    },
    "02": {
        "cargo_he": "בשר",
        "risk": "high",
        "ministries": [
            {"name": "MOH", "name_he": "משרד הבריאות",
             "url": "https://www.gov.il/he/departments/ministry_of_health",
             "documents": ["MOH food import license", "Health certificate"],
             "documents_he": ["רישיון יבוא מזון", "תעודת בריאות"],
             "procedure": "Food import license from MOH Food Service."},
            {"name": "Veterinary Services", "name_he": "שירותים וטרינריים",
             "url": "https://www.gov.il/he/departments/Units/veterinary_services",
             "documents": ["Veterinary certificate"],
             "documents_he": ["תעודה וטרינרית"],
             "procedure": "Veterinary certificate per shipment."},
            {"name": "Chief Rabbinate", "name_he": "הרבנות הראשית",
             "url": "https://www.gov.il/he/departments/chief_rabbinate",
             "documents": ["Kosher certification"],
             "documents_he": ["תעודת כשרות"],
             "procedure": "Required for retail sale. Not required for industrial use."},
        ],
    },
    "04": {
        "cargo_he": "חלב ומוצריו",
        "risk": "high",
        "ministries": [
            {"name": "MOH", "name_he": "משרד הבריאות",
             "url": "https://www.gov.il/he/departments/ministry_of_health",
             "documents": ["MOH food import license", "Health certificate", "Lab test results"],
             "documents_he": ["רישיון יבוא מזון", "תעודת בריאות", "תוצאות מעבדה"],
             "procedure": "Lab tests may be required on arrival."},
        ],
    },
    "06": {
        "cargo_he": "צמחים, ירקות, פירות",
        "risk": "high",
        "ministries": [
            {"name": "PPIS", "name_he": "שה\"צ - שירות ההגנה על הצומח",
             "url": "https://www.gov.il/he/departments/Units/ppis",
             "documents": ["Phytosanitary certificate", "PPIS import permit", "Fumigation certificate"],
             "documents_he": ["תעודה פיטוסניטרית", "היתר יבוא שה\"צ", "תעודת חיטוי"],
             "procedure": "Phytosanitary certificate mandatory. Fumigation if from listed countries."},
        ],
    },
    "15": {
        "cargo_he": "מזון, משקאות, שמנים",
        "risk": "medium",
        "ministries": [
            {"name": "MOH", "name_he": "משרד הבריאות",
             "url": "https://www.gov.il/he/departments/ministry_of_health",
             "documents": ["MOH food import license", "Hebrew labeling", "Health certificate", "Lab results"],
             "documents_he": ["רישיון יבוא מזון", "תיוג בעברית", "תעודת בריאות", "תוצאות מעבדה"],
             "procedure": "Hebrew labeling required on all consumer food products."},
        ],
    },
    "24": {
        "cargo_he": "טבק ומוצרי טבק",
        "risk": "high",
        "ministries": [
            {"name": "MOH", "name_he": "משרד הבריאות",
             "url": "https://www.gov.il/he/departments/ministry_of_health",
             "documents": ["Special import license", "Health warnings in Hebrew"],
             "documents_he": ["רישיון יבוא מיוחד", "אזהרות בריאות בעברית"],
             "procedure": "Special purchase tax. Health warning labels mandatory."},
            {"name": "Tax Authority", "name_he": "רשות המסים",
             "url": "https://www.gov.il/he/departments/israel_tax_authority",
             "documents": ["Purchase tax declaration"],
             "documents_he": ["הצהרת מס קנייה"],
             "procedure": "Purchase tax applies."},
        ],
    },
    "28": {
        "cargo_he": "כימיקלים",
        "risk": "high",
        "ministries": [
            {"name": "Ministry of Environment", "name_he": "המשרד להגנת הסביבה",
             "url": "https://www.gov.il/he/departments/ministry_of_environmental_protection",
             "documents": ["MSDS", "Chemical registration", "Hazmat permit", "GHS labeling"],
             "documents_he": ["גיליון בטיחות", "רישום כימיקל", "היתר חומ\"ס", "תיוג GHS"],
             "procedure": "MSDS mandatory. Rotterdam/Stockholm convention compliance."},
        ],
    },
    "30": {
        "cargo_he": "תרופות",
        "risk": "critical",
        "ministries": [
            {"name": "MOH Pharmaceutical Division", "name_he": "אגף הרוקחות - משרד הבריאות",
             "url": "https://www.gov.il/he/departments/Units/pharmacy_department",
             "documents": ["Drug registration", "Import permit per shipment", "GMP certificate", "CPP"],
             "documents_he": ["רישום תרופה", "היתר יבוא לכל משלוח", "תעודת GMP", "CPP"],
             "procedure": "Must be registered in Israeli drug registry BEFORE import."},
        ],
    },
    "33": {
        "cargo_he": "קוסמטיקה",
        "risk": "medium",
        "ministries": [
            {"name": "MOH", "name_he": "משרד הבריאות",
             "url": "https://www.gov.il/he/departments/ministry_of_health",
             "documents": ["Cosmetics notification", "INCI ingredient list", "Hebrew labeling"],
             "documents_he": ["הודעה על קוסמטיקה", "רשימת רכיבים INCI", "תיוג בעברית"],
             "procedure": "Based on EU cosmetics regulation. INCI labeling mandatory."},
        ],
    },
    "36": {
        "cargo_he": "חומרי נפץ, זיקוקין",
        "risk": "critical",
        "ministries": [
            {"name": "Ministry of Defense", "name_he": "משרד הביטחון",
             "url": "https://www.gov.il/he/departments/ministry_of_defense",
             "documents": ["Defense Ministry license", "End-user certificate", "Storage approval"],
             "documents_he": ["רישיון משרד הביטחון", "תעודת משתמש סופי", "אישור אחסון"],
             "procedure": "Security clearance required. Long processing times."},
            {"name": "Israel Police", "name_he": "משטרת ישראל",
             "url": "https://www.gov.il/he/departments/israel_police",
             "documents": ["Police approval"],
             "documents_he": ["אישור משטרה"],
             "procedure": "Police approval for civilian pyrotechnics."},
        ],
    },
    "39": {
        "cargo_he": "פלסטיק, גומי",
        "risk": "low",
        "ministries": [
            {"name": "SII", "name_he": "מכון התקנים",
             "url": "https://www.sii.org.il",
             "documents": ["SII standard compliance", "Food-contact certificate"],
             "documents_he": ["עמידה בתקן ישראלי", "אישור מגע מזון"],
             "procedure": "Consumer products require SII mark. Food-contact materials need separate cert."},
        ],
    },
    "44": {
        "cargo_he": "עץ, שעם",
        "risk": "medium",
        "ministries": [
            {"name": "PPIS", "name_he": "שה\"צ - שירות ההגנה על הצומח",
             "url": "https://www.gov.il/he/departments/Units/ppis",
             "documents": ["ISPM 15 compliance", "Phytosanitary certificate", "Heat treatment certificate"],
             "documents_he": ["עמידה ב-ISPM 15", "תעודה פיטוסניטרית", "תעודת טיפול חום"],
             "procedure": "ISPM 15 for ALL wood packaging. Solid wood products need phytosanitary cert."},
        ],
    },
    "50": {
        "cargo_he": "טקסטיל, הלבשה",
        "risk": "low",
        "ministries": [
            {"name": "SII", "name_he": "מכון התקנים",
             "url": "https://www.sii.org.il",
             "documents": ["Fiber composition label", "Safety standards (children)", "Care instructions"],
             "documents_he": ["תווית הרכב סיבים", "תקני בטיחות (ילדים)", "הוראות טיפול"],
             "procedure": "Hebrew labeling required. Children's items have strict safety standards."},
        ],
    },
    "64": {
        "cargo_he": "הנעלה",
        "risk": "low",
        "ministries": [
            {"name": "SII", "name_he": "מכון התקנים",
             "url": "https://www.sii.org.il",
             "documents": ["Material composition label", "Size marking"],
             "documents_he": ["תווית הרכב חומרים", "סימון מידה"],
             "procedure": "Labeling requirements for footwear materials."},
        ],
    },
    "68": {
        "cargo_he": "אבן, קרמיקה, זכוכית",
        "risk": "low",
        "ministries": [
            {"name": "SII", "name_he": "מכון התקנים",
             "url": "https://www.sii.org.il",
             "documents": ["Safety glass SI 1099", "Construction materials approval"],
             "documents_he": ["זכוכית בטיחות ת\"י 1099", "אישור חומרי בנייה"],
             "procedure": "Construction materials subject to Israeli Standards."},
        ],
    },
    "71": {
        "cargo_he": "יהלומים, אבנים יקרות, תכשיטים",
        "risk": "medium",
        "ministries": [
            {"name": "Diamond Controller", "name_he": "מפקח על היהלומים",
             "url": "https://www.gov.il/he/departments/Units/diamond_supervisor",
             "documents": ["Kimberley Process cert (rough diamonds)", "Diamond Controller registration", "Hallmarking"],
             "documents_he": ["תעודת קימברלי (יהלומי גלם)", "רישום מפקח היהלומים", "חותמת מתכת יקרה"],
             "procedure": "Trade through Israel Diamond Exchange in Ramat Gan."},
        ],
    },
    "72": {
        "cargo_he": "מתכות (ברזל, פלדה, אלומיניום)",
        "risk": "medium",
        "ministries": [
            {"name": "SII", "name_he": "מכון התקנים",
             "url": "https://www.sii.org.il",
             "documents": ["Construction steel SI 4466", "Aluminum profiles standards"],
             "documents_he": ["פלדת בנייה ת\"י 4466", "תקני פרופילי אלומיניום"],
             "procedure": "Construction metals have mandatory SII standards. Check anti-dumping duties."},
        ],
    },
    "84": {
        "cargo_he": "מכונות, מכשירים מכניים",
        "risk": "low",
        "ministries": [
            {"name": "SII", "name_he": "מכון התקנים",
             "url": "https://www.sii.org.il",
             "documents": ["Electrical safety cert", "Energy efficiency label", "CE/UL marking"],
             "documents_he": ["אישור בטיחות חשמלית", "תווית יעילות אנרגטית", "סימון CE/UL"],
             "procedure": "Consumer appliances need energy labels. Industrial machinery generally exempt."},
        ],
    },
    "85": {
        "cargo_he": "אלקטרוניקה, ציוד תקשורת",
        "risk": "medium",
        "ministries": [
            {"name": "MOC", "name_he": "משרד התקשורת",
             "url": "https://www.gov.il/he/departments/ministry_of_communications",
             "documents": ["MOC type approval (wireless/telecom)", "EMC compliance"],
             "documents_he": ["אישור סוג משרד התקשורת", "עמידה ב-EMC"],
             "procedure": "WiFi/Bluetooth/cellular devices need MOC type approval BEFORE import."},
            {"name": "SII", "name_he": "מכון התקנים",
             "url": "https://www.sii.org.il",
             "documents": ["Electrical safety cert", "Energy efficiency label"],
             "documents_he": ["אישור בטיחות חשמלית", "תווית יעילות אנרגטית"],
             "procedure": "All electrical products need SII safety certification."},
        ],
    },
    "87": {
        "cargo_he": "כלי רכב",
        "risk": "high",
        "ministries": [
            {"name": "MOT", "name_he": "משרד התחבורה",
             "url": "https://www.gov.il/he/departments/ministry_of_transport_and_road_safety",
             "documents": ["Vehicle type approval", "Emissions compliance (Euro 6)"],
             "documents_he": ["אישור סוג רכב", "עמידה בתקן פליטות (Euro 6)"],
             "procedure": "Type approval mandatory. Green tax based on pollution level."},
            {"name": "Ministry of Environment", "name_he": "המשרד להגנת הסביבה",
             "url": "https://www.gov.il/he/departments/ministry_of_environmental_protection",
             "documents": ["Green tax calculation"],
             "documents_he": ["חישוב מס ירוק"],
             "procedure": "Green tax based on CO2 emissions and pollutant level."},
        ],
    },
    "88": {
        "cargo_he": "כלי טיס, רחפנים",
        "risk": "high",
        "ministries": [
            {"name": "CAAI", "name_he": "רשות התעופה האזרחית",
             "url": "https://www.gov.il/he/departments/civil_aviation_authority",
             "documents": ["CAAI type certificate", "Drone registration (>250g)"],
             "documents_he": ["תעודת סוג רת\"א", "רישום רחפן (מעל 250 גרם)"],
             "procedure": "Drones heavily regulated. Registration + flight permits required."},
        ],
    },
    "89": {
        "cargo_he": "כלי שיט",
        "risk": "medium",
        "ministries": [
            {"name": "Shipping Authority", "name_he": "רשות הספנות",
             "url": "https://www.gov.il/he/departments/Units/shipping_and_ports_authority",
             "documents": ["Vessel registration", "Safety equipment compliance"],
             "documents_he": ["רישום כלי שיט", "עמידה בציוד בטיחות"],
             "procedure": "Different requirements for pleasure craft vs commercial."},
        ],
    },
    "90": {
        "cargo_he": "מכשירים רפואיים",
        "risk": "high",
        "ministries": [
            {"name": "AMAR", "name_he": "אגף מכשירים רפואיים (אמ\"ר)",
             "url": "https://www.gov.il/he/departments/Units/medical_devices",
             "documents": ["AMAR registration", "CE marking or FDA clearance", "Hebrew user manual", "Authorized representative"],
             "documents_he": ["רישום אמ\"ר", "סימון CE או אישור FDA", "הוראות שימוש בעברית", "נציג מורשה בישראל"],
             "procedure": "Risk class I-IV. AMAR registration mandatory BEFORE import."},
        ],
    },
    "93": {
        "cargo_he": "נשק, תחמושת",
        "risk": "critical",
        "ministries": [
            {"name": "SIBAT", "name_he": "סיבא\"ט - משרד הביטחון",
             "url": "https://www.gov.il/he/departments/Units/sibat",
             "documents": ["Defense import license", "End-user certificate", "Police approval"],
             "documents_he": ["רישיון יבוא ביטחוני", "תעודת משתמש סופי", "אישור משטרה"],
             "procedure": "Highly restricted. Multiple approvals. Long processing times."},
        ],
    },
    "95": {
        "cargo_he": "צעצועים, משחקים, ציוד ספורט",
        "risk": "medium",
        "ministries": [
            {"name": "SII", "name_he": "מכון התקנים",
             "url": "https://www.sii.org.il",
             "documents": ["SI 562 toy safety", "Age marking", "Hebrew warning labels", "Small parts test (under 3)"],
             "documents_he": ["ת\"י 562 בטיחות צעצועים", "סימון גיל", "אזהרות בעברית", "בדיקת חלקים קטנים (מתחת ל-3)"],
             "procedure": "Based on EN 71 / ASTM F963. Chemical content limits apply."},
        ],
    },
    "97": {
        "cargo_he": "עתיקות, אמנות",
        "risk": "medium",
        "ministries": [
            {"name": "Israel Antiquities Authority", "name_he": "רשות העתיקות",
             "url": "https://www.gov.il/he/departments/israel_antiquities_authority",
             "documents": ["Provenance documentation", "Cultural heritage compliance"],
             "documents_he": ["תיעוד מקור", "עמידה בחוקי מורשת תרבותית"],
             "procedure": "Items over 200 years old classified as antiquities. Export restrictions."},
        ],
    },
}

# Chapters that share the same route (map to canonical chapter)
_CHAPTER_ALIASES = {
    "03": "02", "05": "02",  # meat, fish, dairy, animal products
    "07": "06", "08": "06", "09": "06", "10": "06",
    "11": "06", "12": "06", "13": "06", "14": "06",  # plants, veg, fruits
    "16": "15", "17": "15", "18": "15", "19": "15",
    "20": "15", "21": "15", "22": "15",  # food, beverages
    "23": "06",  # animal feed -> MOA (same as plants)
    "25": "28", "26": "28", "27": "28",  # minerals, fuels -> environment
    "29": "28", "38": "28",  # chemicals
    "31": "06",  # fertilizers -> MOA
    "40": "39",  # rubber -> plastics/SII
    "45": "44", "46": "44",  # cork, straw -> wood
    "51": "50", "52": "50", "53": "50", "54": "50", "55": "50",
    "56": "50", "57": "50", "58": "50", "59": "50", "60": "50",
    "61": "50", "62": "50", "63": "50",  # textiles
    "65": "64", "66": "64", "67": "64",  # headgear -> footwear
    "69": "68", "70": "68",  # ceramics, glass -> stone
    "73": "72", "74": "72", "75": "72", "76": "72",  # metals
}


def route_to_ministries(db, hs_code, free_import_result=None):
    """
    Phase C: Given an HS code (and optionally Free Import Order API result),
    return complete ministry routing with procedures, documents, and URLs.

    Merges three sources:
      1. Built-in routing table (_MINISTRY_ROUTES)
      2. Firestore baseline knowledge (regulatory_requirements, ministry_index)
      3. Official Free Import Order API result (from Phase B)

    Returns:
        dict with:
          hs_code, chapter,
          risk_level: "low"|"medium"|"high"|"critical",
          ministries: [{name, name_he, url, documents, documents_he, procedure,
                        official: bool, source}],
          summary_he: str
    """
    hs_clean = str(hs_code).replace(".", "").replace(" ", "").replace("/", "")
    chapter = hs_clean[:2].zfill(2)

    print(f"  🏛️ MINISTRY ROUTING: HS {hs_code} (chapter {chapter})")

    # Resolve chapter alias
    canonical = _CHAPTER_ALIASES.get(chapter, chapter)
    route = _MINISTRY_ROUTES.get(canonical)

    result = {
        "hs_code": hs_code,
        "chapter": chapter,
        "risk_level": "low",
        "ministries": [],
        "summary_he": "",
    }

    seen_ministries = set()

    # ── Source 1: Built-in routing table ──
    if route:
        result["risk_level"] = route.get("risk", "low")
        for m in route["ministries"]:
            seen_ministries.add(m["name"])
            result["ministries"].append({
                "name": m["name"],
                "name_he": m["name_he"],
                "url": m["url"],
                "documents": m.get("documents", []),
                "documents_he": m.get("documents_he", []),
                "procedure": m.get("procedure", ""),
                "official": False,
                "source": "routing_table",
            })

    # ── Source 2: Firestore baseline ──
    try:
        mi_doc = db.collection("ministry_index").document(f"chapter_{chapter}").get()
        if mi_doc.exists:
            mi_data = mi_doc.to_dict()
            for m_name in mi_data.get("ministries", []):
                if m_name not in seen_ministries:
                    seen_ministries.add(m_name)
                    result["ministries"].append({
                        "name": m_name,
                        "name_he": m_name,
                        "url": "",
                        "documents": [],
                        "documents_he": [],
                        "procedure": "",
                        "official": False,
                        "source": "firestore_baseline",
                    })
    except Exception as e:
        print(f"    ⚠️ Ministry index query error: {e}")

    # ── Source 3: Official Free Import Order API result ──
    if free_import_result and free_import_result.get("found"):
        for auth in free_import_result.get("authorities", []):
            auth_name = auth.get("name", "")
            if not auth_name:
                continue

            # Check if we already have this ministry
            existing = None
            for m in result["ministries"]:
                if auth_name in m["name"] or auth_name in m.get("name_he", ""):
                    existing = m
                    break

            if existing:
                # Enrich existing entry with official data
                existing["official"] = True
                existing["source"] = "official_api"
                if auth.get("phone"):
                    existing["phone"] = auth["phone"]
                if auth.get("email"):
                    existing["email"] = auth["email"]
                if auth.get("website") and not existing["url"]:
                    existing["url"] = auth["website"]
                if auth.get("department"):
                    existing["department"] = auth["department"]
            else:
                # Add new ministry from API
                seen_ministries.add(auth_name)
                result["ministries"].append({
                    "name": auth_name,
                    "name_he": auth_name,
                    "url": auth.get("website", ""),
                    "phone": auth.get("phone", ""),
                    "email": auth.get("email", ""),
                    "department": auth.get("department", ""),
                    "documents": [],
                    "documents_he": [],
                    "procedure": "",
                    "official": True,
                    "source": "official_api",
                })

        # Add specific legal requirements from API items
        for item in free_import_result.get("items", []):
            for req in item.get("legal_requirements", []):
                req_name = req.get("name", "")
                req_auth = req.get("authority", "")
                if req_name:
                    # Find the matching ministry and add the requirement
                    for m in result["ministries"]:
                        if req_auth and (req_auth in m["name"] or req_auth in m.get("name_he", "")):
                            if req_name not in m["documents"] and req_name not in m["documents_he"]:
                                m["documents_he"].append(req_name)
                            break

    # Build Hebrew summary
    if result["ministries"]:
        ministry_names = ", ".join(m["name_he"] for m in result["ministries"])
        risk_he = {"low": "נמוך", "medium": "בינוני", "high": "גבוה", "critical": "קריטי"}
        result["summary_he"] = (
            f"פרק {chapter} — רמת רגולציה: {risk_he.get(result['risk_level'], result['risk_level'])}. "
            f"גורמים מאשרים: {ministry_names}."
        )
        official_count = sum(1 for m in result["ministries"] if m.get("official"))
        if official_count:
            result["summary_he"] += f" ({official_count} מאומתים מול צו יבוא חופשי)"

        print(f"  🏛️ MINISTRY ROUTING: {len(result['ministries'])} ministries, "
              f"risk={result['risk_level']}, official={official_count}")
    else:
        result["summary_he"] = f"פרק {chapter} — אין דרישות רגולטוריות מיוחדות."
        print(f"  🏛️ MINISTRY ROUTING: No specific ministry requirements for chapter {chapter}")

    return result


# ═══════════════════════════════════════════════════════════════
#  6. FREE IMPORT ORDER API — official license/permit requirements
# ═══════════════════════════════════════════════════════════════

_FIO_API = "https://apps.economy.gov.il/Apps/FreeImportServices/FreeImportData"
_FIO_CACHE_HOURS = 168  # 7 days


def query_free_import_order(db, hs_code):
    """
    Query the official Free Import Order API for license/permit requirements.

    1. Checks Firestore cache (free_import_cache) first
    2. If miss or stale, queries the live Ministry of Economy API
    3. Also queries parent HS codes (requirements can be inherited)
    4. Caches result in Firestore

    Returns:
        dict with:
          hs_code, found: bool,
          items: [{description, legal_requirements: [{name, authority, url, supplement}]}],
          authorities: [{name, department, phone, email, website}],
          decree_version: str,
          cached: bool, cache_age_hours: float
    """
    hs_clean = str(hs_code).replace(".", "").replace(" ", "").replace("/", "")
    # Pad to 10 digits (Israeli format)
    hs_10 = hs_clean.ljust(10, "0")[:10]

    print(f"  🏛️ FREE IMPORT ORDER: Querying for HS {hs_10}")

    result = {
        "hs_code": hs_code,
        "hs_10": hs_10,
        "found": False,
        "items": [],
        "authorities": [],
        "decree_version": "",
        "cached": False,
        "cache_age_hours": 0,
    }

    # ── Step 1: Check Firestore cache ──
    cached = _check_fio_cache(db, hs_10)
    if cached:
        age_hours = cached.get("cache_age_hours", 0)
        if age_hours < _FIO_CACHE_HOURS:
            print(f"  🏛️ FREE IMPORT ORDER: Cache hit ({age_hours:.0f}h old)")
            cached["cached"] = True
            return cached

    # ── Step 2: Query live API ──
    try:
        # Main search
        api_result = _query_fio_api(hs_10)
        if api_result:
            result.update(api_result)
            result["found"] = True

        # Also get parent code requirements (they can apply too)
        parent_result = _query_fio_parents(hs_10)
        if parent_result:
            # Merge parent items that aren't already in result
            existing_ids = {item.get("id") for item in result["items"]}
            for item in parent_result.get("items", []):
                if item.get("id") not in existing_ids:
                    item["inherited_from_parent"] = True
                    result["items"].append(item)
            # Merge parent authorities
            existing_auths = {a.get("name") for a in result["authorities"]}
            for auth in parent_result.get("authorities", []):
                if auth.get("name") not in existing_auths:
                    result["authorities"].append(auth)
            if not result["found"] and parent_result.get("items"):
                result["found"] = True

    except Exception as e:
        print(f"  🏛️ FREE IMPORT ORDER: API error — {e}")
        # Fall back to cache even if stale
        if cached:
            print(f"  🏛️ FREE IMPORT ORDER: Using stale cache")
            cached["cached"] = True
            return cached
        return result

    # ── Step 3: Cache result ──
    if result["found"]:
        _save_fio_cache(db, hs_10, result)
        count = len(result["items"])
        auths = ", ".join(a.get("name", "") for a in result["authorities"][:3])
        print(f"  🏛️ FREE IMPORT ORDER: Found {count} items, authorities: {auths}")
    else:
        print(f"  🏛️ FREE IMPORT ORDER: No requirements found for HS {hs_10}")
        # Cache the "no results" too so we don't re-query
        _save_fio_cache(db, hs_10, result)

    return result


def _query_fio_api(hs_10):
    """Query the main Free Import Order search endpoint."""
    url = f"{_FIO_API}/GetImportWaresBySearchParamsAndCA/"
    payload = {
        "customNum": hs_10,
        "freeText": "",
        "customsAuthoritys": []
    }

    resp = requests.post(url, json=payload, timeout=15,
                         headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    data = resp.json()

    search_list = data.get("Data", {}).get("FISearchList", [])
    if not search_list:
        return None

    items = []
    authorities_seen = {}

    for entry in search_list:
        # Only include active entries
        if not entry.get("fiimw_is_active", True):
            continue

        # Filter: only include items whose HS code matches our query
        entry_code = entry.get("fiimw_iware_code", "")
        if entry_code and not hs_10.startswith(entry_code.rstrip("0")) and not entry_code.startswith(hs_10.rstrip("0")):
            continue

        item = {
            "id": entry.get("fiimw_id"),
            "hs_code": entry_code,
            "description": entry.get("fiimw_description", ""),
            "legal_requirements": [],
        }

        for lr in entry.get("LegalRequirements", []):
            req = {
                "name": lr.get("filrq_legal_requirement_name", ""),
                "supplement": lr.get("filrq_supplement_num", 0),
                "type": lr.get("filrq_type", 0),
                "url": lr.get("filrq_url", ""),
                "description": lr.get("fiwlr_description", ""),
                "includes_standards": lr.get("filrq_is_including_standards", False),
            }

            # Extract authority info
            auth = lr.get("CompetentAuthority", {})
            if auth:
                auth_name = auth.get("gvmen_heb_name", "")
                req["authority"] = auth_name
                req["authority_department"] = auth.get("cpau_department", "")

                if auth_name and auth_name not in authorities_seen:
                    authorities_seen[auth_name] = {
                        "name": auth_name,
                        "department": auth.get("cpau_department", ""),
                        "phone": auth.get("cpau_phone", ""),
                        "email": auth.get("cpau_email", ""),
                        "website": auth.get("cpau_website", ""),
                        "address": auth.get("cpau_address", ""),
                    }

            # Standard info
            std = lr.get("Standard")
            if std:
                req["standard"] = std

            item["legal_requirements"].append(req)

        if item["legal_requirements"]:
            items.append(item)

    # Decree version
    decree = ""
    if search_list:
        dv = search_list[0].get("ImportWareDecreeVersion", {})
        if dv:
            decree = dv.get("fidcv_name", "")

    return {
        "items": items,
        "authorities": list(authorities_seen.values()),
        "decree_version": decree,
    }


def _query_fio_parents(hs_10):
    """Query parent HS codes for inherited requirements."""
    url = f"{_FIO_API}/GetImportWaresParents/{hs_10}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict):
            parents = data.get("Data", {}).get("FISearchList", data.get("Data", []))
        else:
            parents = data
        if not parents:
            return None

        items = []
        authorities_seen = {}

        for entry in parents:
            if not entry.get("fiimw_is_active", True):
                continue

            item = {
                "id": entry.get("fiimw_id"),
                "hs_code": entry.get("fiimw_iware_code", ""),
                "description": entry.get("fiimw_description", ""),
                "legal_requirements": [],
            }

            for lr in entry.get("LegalRequirements", []):
                req = {
                    "name": lr.get("filrq_legal_requirement_name", ""),
                    "supplement": lr.get("filrq_supplement_num", 0),
                    "type": lr.get("filrq_type", 0),
                    "url": lr.get("filrq_url", ""),
                }
                auth = lr.get("CompetentAuthority", {})
                if auth:
                    auth_name = auth.get("gvmen_heb_name", "")
                    req["authority"] = auth_name
                    if auth_name and auth_name not in authorities_seen:
                        authorities_seen[auth_name] = {
                            "name": auth_name,
                            "department": auth.get("cpau_department", ""),
                            "phone": auth.get("cpau_phone", ""),
                            "email": auth.get("cpau_email", ""),
                            "website": auth.get("cpau_website", ""),
                        }
                item["legal_requirements"].append(req)

            if item["legal_requirements"]:
                items.append(item)

        return {
            "items": items,
            "authorities": list(authorities_seen.values()),
        }
    except Exception as e:
        print(f"    ⚠️ FIO parents query error: {e}")
        return None


def _check_fio_cache(db, hs_10):
    """Check Firestore cache for Free Import Order results."""
    try:
        doc = db.collection("free_import_cache").document(hs_10).get()
        if doc.exists:
            data = doc.to_dict()
            cached_at = data.get("cached_at", "")
            if cached_at:
                if isinstance(cached_at, str):
                    cached_time = datetime.fromisoformat(cached_at)
                else:
                    cached_time = cached_at
                if cached_time.tzinfo is None:
                    cached_time = cached_time.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - cached_time).total_seconds() / 3600
                data["cache_age_hours"] = age
            return data
    except Exception as e:
        print(f"    ⚠️ FIO cache read error: {e}")
    return None


def _save_fio_cache(db, hs_10, result):
    """Save Free Import Order results to Firestore cache."""
    try:
        cache_doc = {
            **result,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        db.collection("free_import_cache").document(hs_10).set(cache_doc)
    except Exception as e:
        print(f"    ⚠️ FIO cache write error: {e}")


# ═══════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════

def _extract_keywords(text):
    """Extract meaningful keywords from item description."""
    stop_words = {
        "the", "a", "an", "of", "for", "and", "or", "with", "to", "from",
        "in", "on", "by", "is", "are", "was", "were", "be", "been", "new",
        "used", "set", "pcs", "piece", "pieces", "item", "items", "type",
        "את", "של", "על", "עם", "או", "גם", "כי", "אם", "לא", "יש", "זה",
        "אל", "הם", "הוא", "היא", "בין", "כל", "מן", "אשר", "עד", "רק",
    }
    # Split on non-word characters, keep Hebrew
    words = re.split(r'[^\w\u0590-\u05FF]+', text.lower())
    keywords = [w for w in words if len(w) > 2 and w not in stop_words]
    return keywords[:15]


def _search_classification_knowledge(db, keywords, desc_lower):
    """Search classification_knowledge for similar past items."""
    results = []
    keywords_set = set(keywords)

    try:
        docs = db.collection("classification_knowledge").limit(500).stream()
        for doc in docs:
            data = doc.to_dict()
            hs_code = data.get("hs_code", "")
            if not hs_code:
                continue

            # Build searchable text from document
            search_parts = []
            for field in ["description", "description_lower", "content",
                          "title", "rule", "item"]:
                val = data.get(field, "")
                if isinstance(val, str):
                    search_parts.append(val.lower())
            search_text = " ".join(search_parts)

            # Score by keyword overlap
            score = 0
            for kw in keywords_set:
                if kw in search_text:
                    score += 1

            # Bonus for exact phrase fragments (3+ word matches)
            if len(desc_lower) > 10 and desc_lower[:30] in search_text:
                score += 3

            if score > 0:
                # Convert to percentage-like confidence
                confidence = min(95, int((score / max(len(keywords_set), 1)) * 100))

                # Boost corrections (they're more reliable)
                if data.get("is_correction"):
                    confidence = min(95, confidence + 10)

                # Boost items with high usage count
                usage = data.get("usage_count", 0)
                if usage >= 5:
                    confidence = min(95, confidence + 5)
                elif usage >= 10:
                    confidence = min(95, confidence + 10)

                results.append({
                    "hs_code": hs_code,
                    "score": confidence,
                    "description": data.get("description", data.get("content", ""))[:100],
                    "duty_rate": data.get("duty_rate", ""),
                    "is_correction": data.get("is_correction", False),
                    "usage_count": usage,
                })
    except Exception as e:
        print(f"    ⚠️ classification_knowledge search error: {e}")

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:5]


def _search_classification_rules(db, desc_lower):
    """Search classification_rules keyword_patterns against description."""
    results = []

    try:
        docs = db.collection("classification_rules").stream()
        for doc in docs:
            data = doc.to_dict()
            if data.get("type") != "keyword_pattern":
                continue

            pattern_str = data.get("pattern", "")
            if not pattern_str:
                continue

            # Split pattern alternatives (pipe-separated)
            alternatives = [p.strip().lower() for p in pattern_str.split("|") if p.strip()]
            matched = False
            for alt in alternatives:
                if alt in desc_lower:
                    matched = True
                    break

            if matched:
                conf_str = data.get("confidence", "medium")
                confidence_map = {"high": 80, "medium": 60, "low": 40}
                confidence = confidence_map.get(conf_str, 50)

                results.append({
                    "hs_heading": data.get("hs_heading", ""),
                    "confidence": confidence,
                    "description": data.get("description", ""),
                    "pattern": pattern_str[:80],
                    "notes": data.get("notes", ""),
                })
    except Exception as e:
        print(f"    ⚠️ classification_rules search error: {e}")

    results.sort(key=lambda r: r["confidence"], reverse=True)
    return results[:5]


def _search_tariff(db, keywords):
    """Search tariff and tariff_chapters for matching HS descriptions."""
    results = []
    keywords_lower = [k.lower() for k in keywords if k]

    # Search tariff_chapters (has richer data)
    try:
        docs = db.collection("tariff_chapters").limit(1000).stream()
        for doc in docs:
            data = doc.to_dict()
            search_text = ""
            for field in ["description_he", "description_en", "title",
                          "title_he", "title_en"]:
                val = data.get(field, "")
                if isinstance(val, str):
                    search_text += " " + val.lower()

            score = sum(1 for kw in keywords_lower if kw in search_text)
            if score >= 2:  # Need at least 2 keyword matches for tariff
                hs = data.get("code", data.get("hs_code", ""))
                if hs:
                    results.append({
                        "hs_code": hs,
                        "score": min(85, score * 15),
                        "description_he": data.get("description_he",
                                                     data.get("title_he", "")),
                        "description_en": data.get("description_en",
                                                     data.get("title_en", "")),
                        "duty_rate": data.get("duty_rate", ""),
                        "source": "tariff_chapters",
                    })
    except Exception as e:
        print(f"    ⚠️ tariff_chapters search error: {e}")

    # Search tariff collection
    try:
        docs = db.collection("tariff").limit(500).stream()
        for doc in docs:
            data = doc.to_dict()
            search_text = ""
            for field in ["description_he", "description_en", "hs_code"]:
                val = data.get(field, "")
                if isinstance(val, str):
                    search_text += " " + val.lower()

            score = sum(1 for kw in keywords_lower if kw in search_text)
            if score >= 2:
                hs = data.get("hs_code", "")
                if hs:
                    # Don't duplicate
                    already = any(r["hs_code"] == hs for r in results)
                    if not already:
                        results.append({
                            "hs_code": hs,
                            "score": min(80, score * 15),
                            "description_he": data.get("description_he", ""),
                            "duty_rate": data.get("duty_rate", ""),
                            "source": "tariff",
                        })
    except Exception as e:
        print(f"    ⚠️ tariff search error: {e}")

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:10]


def _lookup_regulatory_by_chapter(db, chapter):
    """Look up regulatory requirements for an HS chapter."""
    chapter_padded = chapter.zfill(2)

    try:
        # Check regulatory_requirements
        docs = db.collection("regulatory_requirements").stream()
        for doc in docs:
            data = doc.to_dict()
            chapters = data.get("hs_chapters", [])
            if chapter_padded in chapters or chapter in chapters:
                return {
                    "hs_chapter": chapter_padded,
                    "cargo": data.get("cargo", ""),
                    "cargo_he": data.get("cargo_he", ""),
                    "ministries": data.get("ministries", []),
                    "requirements": data.get("requirements", []),
                    "free_import_order": data.get("free_import_order", False),
                    "notes": data.get("notes", ""),
                }
    except Exception as e:
        print(f"    ⚠️ regulatory lookup error: {e}")

    return None


def _search_fta_by_country(db, origin_country):
    """Search fta_agreements by origin country name or code."""
    if not origin_country:
        return None

    country_upper = origin_country.strip().upper()
    country_lower = origin_country.strip().lower()

    # Common country name normalization
    country_aliases = {
        "china": "CN", "prc": "CN",
        "usa": "US", "united states": "US", "america": "US",
        "uk": "GB", "united kingdom": "GB", "britain": "GB", "england": "GB",
        "germany": "DE", "france": "FR", "italy": "IT", "spain": "ES",
        "netherlands": "NL", "holland": "NL",
        "turkey": "TR", "turkiye": "TR",
        "jordan": "JO",
        "egypt": "EG",
        "canada": "CA",
        "mexico": "MX",
        "japan": "JP",
        "korea": "KR", "south korea": "KR",
        "india": "IN",
        "switzerland": "CH",
        "norway": "NO",
        "sweden": "SE",
        "poland": "PL",
        "czech republic": "CZ", "czechia": "CZ",
        "romania": "RO",
        "portugal": "PT",
        "greece": "GR",
        "austria": "AT",
        "belgium": "BE",
        "denmark": "DK",
        "finland": "FI",
        "ireland": "IE",
        "colombia": "CO",
        "panama": "PA",
        "ukraine": "UA",
        # Hebrew names
        "סין": "CN", "ארה\"ב": "US", "ארצות הברית": "US",
        "בריטניה": "GB", "גרמניה": "DE", "צרפת": "FR",
        "איטליה": "IT", "ספרד": "ES", "הולנד": "NL",
        "טורקיה": "TR", "ירדן": "JO", "מצרים": "EG",
        "יפן": "JP", "הודו": "IN", "קנדה": "CA",
    }

    # Resolve country code
    country_code = country_upper if len(country_upper) == 2 else None
    if not country_code:
        country_code = country_aliases.get(country_lower)

    try:
        docs = db.collection("fta_agreements").stream()
        for doc in docs:
            data = doc.to_dict()
            countries = data.get("countries", [])
            name_lower = data.get("name", "").lower()

            # Match by country code in list
            match = False
            if country_code and country_code in countries:
                match = True
            # Match by agreement name
            elif country_lower in name_lower:
                match = True
            # Match by country name in list (for multi-country agreements)
            elif country_upper in countries:
                match = True

            if match:
                return {
                    "eligible": True,
                    "agreement_name": data.get("name", ""),
                    "agreement_name_he": data.get("name_he", ""),
                    "preferential_rate": data.get("preferential_rate", ""),
                    "origin_proof": data.get("origin_proof", ""),
                    "origin_proof_alt": data.get("origin_proof_alt", ""),
                    "cumulation": data.get("cumulation", ""),
                    "legal_basis": data.get("legal_basis", ""),
                    "notes": data.get("notes", ""),
                }
    except Exception as e:
        print(f"    ⚠️ fta_agreements search error: {e}")

    return {"eligible": False, "origin_country": origin_country}


def _build_pre_classify_context(candidates, regulatory_hits, fta_info):
    """Build context text string to inject into AI classification prompt."""
    lines = []

    if candidates:
        lines.append("=== ידע קיים במערכת (PRE-CLASSIFY) ===")
        lines.append("המערכת מצאה התאמות במאגרי הידע שלה. אמת או תקן:")
        lines.append("")

        for i, c in enumerate(candidates[:5], 1):
            hs = c["hs_code"]
            conf = c["confidence"]
            source_labels = {
                "past_classification": "סיווג קודם",
                "keyword_rule": "כלל מילות מפתח",
                "tariff_db": "תעריפון",
            }
            source = source_labels.get(c["source"], c["source"])
            lines.append(f"  {i}. HS {hs} — ודאות {conf}% (מקור: {source})")
            if c.get("description"):
                lines.append(f"     תיאור: {c['description'][:80]}")
            if c.get("duty_rate"):
                lines.append(f"     מכס: {c['duty_rate']}")
            if c.get("reasoning"):
                lines.append(f"     נימוק: {c['reasoning'][:80]}")
            if c.get("is_correction"):
                lines.append(f"     ⚠️ מבוסס על תיקון קודם — קוד מתוקן!")
            if c.get("notes"):
                lines.append(f"     הערה: {c['notes'][:80]}")
            lines.append("")

    if regulatory_hits:
        lines.append("=== דרישות רגולטוריות שנמצאו ===")
        for reg in regulatory_hits:
            ch = reg.get("hs_chapter", "")
            cargo = reg.get("cargo_he", reg.get("cargo", ""))
            ministries = ", ".join(reg.get("ministries", []))
            lines.append(f"  פרק {ch} ({cargo}): {ministries}")
            reqs = reg.get("requirements", [])
            for r in reqs[:3]:
                lines.append(f"    - {r}")
        lines.append("")

    if fta_info and fta_info.get("eligible"):
        lines.append("=== הסכם סחר חופשי (FTA) ===")
        lines.append(f"  הסכם: {fta_info.get('agreement_name', '')} "
                      f"({fta_info.get('agreement_name_he', '')})")
        lines.append(f"  שיעור מועדף: {fta_info.get('preferential_rate', '')}")
        lines.append(f"  הוכחת מקור: {fta_info.get('origin_proof', '')}")
        if fta_info.get("origin_proof_alt"):
            lines.append(f"  חלופה: {fta_info.get('origin_proof_alt', '')}")
        if fta_info.get("cumulation"):
            lines.append(f"  צבירה: {fta_info.get('cumulation', '')}")
        lines.append("")

    if not lines:
        return ""

    lines.append("=== הנחיה: אמת את הממצאים לעיל או תקן אם אינם מדויקים ===")
    return "\n".join(lines)
