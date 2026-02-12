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
