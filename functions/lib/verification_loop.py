"""
RCB Verification Loop — Verify, Enrich, Cache Every Classification
====================================================================
After AI classification, verifies each HS code against multiple sources,
adds purchase tax + VAT, tracks verification confidence, and caches
results so repeat items skip research entirely.

No AI calls — pure Firestore lookups + Free Import Order API.

Pipeline:
  1. Check verification_cache (instant if recently verified)
  2. Verify HS code exists in tariff DB (3 collections)
  3. Cross-reference with Free Import Order API result
  4. Calculate purchase tax by HS chapter
  5. Add VAT rate (18%)
  6. Assign verification_status: "official" | "verified" | "partial" | "unverified"
  7. Cache result in verification_cache (30-day TTL)
  8. Store in classification_knowledge for future learning
"""

import re
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════
#  PURCHASE TAX TABLE (מס קנייה) by HS chapter
# ═══════════════════════════════════════════════════════════════
# Source: Israeli customs authority purchase tax schedule
# These are APPROXIMATE rates — the exact rate depends on subheading.

_PURCHASE_TAX = {
    # Tobacco (chapter 24)
    "24": {"rate": "varies", "rate_he": "משתנה (עד 770%)", "category": "tobacco",
           "note_he": "מס קנייה על טבק נקבע לפי סוג המוצר ומשקלו"},
    # Fuels (chapter 27)
    "27": {"rate": "varies", "rate_he": "משתנה", "category": "fuel",
           "note_he": "בלו דלק בנפרד ממס קנייה"},
    # Cosmetics (chapter 33)
    "33": {"rate": "0%", "rate_he": "לא חל", "category": "cosmetics",
           "note_he": ""},
    # Vehicles (chapter 87)
    "87": {"rate": "83%", "rate_he": "83%", "category": "vehicles",
           "note_he": "83% על רכב פרטי. משאיות ואוטובוסים — שיעורים מופחתים."},
    # Aircraft (chapter 88)
    "88": {"rate": "0%", "rate_he": "לא חל", "category": "aircraft",
           "note_he": ""},
    # Ships (chapter 89)
    "89": {"rate": "0%", "rate_he": "לא חל", "category": "ships",
           "note_he": ""},
    # Arms (chapter 93)
    "93": {"rate": "varies", "rate_he": "משתנה", "category": "arms",
           "note_he": ""},
}

# Alcoholic beverages (specific subheadings within chapters 22)
_PURCHASE_TAX_SUBHEADINGS = {
    "2203": {"rate_he": "כ-100%", "note_he": "בירה"},
    "2204": {"rate_he": "כ-100-150%", "note_he": "יין"},
    "2205": {"rate_he": "כ-100%", "note_he": "ורמוט"},
    "2206": {"rate_he": "כ-100%", "note_he": "משקאות מותססים אחרים"},
    "2207": {"rate_he": "כ-170%", "note_he": "אתנול"},
    "2208": {"rate_he": "כ-170%", "note_he": "משקאות חריפים"},
}

# VAT rate
ISRAEL_VAT_RATE = "18%"
ISRAEL_VAT_RATE_HE = "18%"

# Verification cache TTL
CACHE_TTL_DAYS = 30


# ═══════════════════════════════════════════════════════════════
#  1. VERIFY SINGLE HS CODE
# ═══════════════════════════════════════════════════════════════

def verify_hs_code(db, hs_code, free_import_result=None):
    """
    Verify a single HS code against all available sources.

    Args:
        db: Firestore client
        hs_code: str (e.g., "8471.30.0000")
        free_import_result: dict (from query_free_import_order, optional)

    Returns:
        dict with:
          hs_code, verified, verification_status, verification_sources,
          duty_rate, duty_source, purchase_tax, vat_rate,
          official_description_he, cached_at
    """
    hs_clean = str(hs_code).replace(".", "").replace(" ", "").replace("/", "")
    chapter = hs_clean[:2].zfill(2) if len(hs_clean) >= 2 else ""
    heading = hs_clean[:4] if len(hs_clean) >= 4 else ""

    result = {
        "hs_code": hs_code,
        "hs_clean": hs_clean,
        "chapter": chapter,
        "verified": False,
        "verification_status": "unverified",
        "verification_sources": [],
        "duty_rate": "",
        "duty_source": "",
        "purchase_tax": _get_purchase_tax(chapter, heading),
        "vat_rate": ISRAEL_VAT_RATE,
        "official_description_he": "",
        "official_description_en": "",
        "cached_at": "",
    }

    # ── Step 1: Check verification cache ──
    cached = _check_verification_cache(db, hs_clean)
    if cached:
        result.update(cached)
        result["from_cache"] = True
        return result

    # ── Step 2: Verify in tariff DB (3 collections) ──
    tariff_match = _verify_in_tariff_db(db, hs_clean)
    if tariff_match:
        result["verification_sources"].append("tariff_db")
        result["official_description_he"] = tariff_match.get("description_he", "")
        result["official_description_en"] = tariff_match.get("description_en", "")
        if tariff_match.get("duty_rate"):
            result["duty_rate"] = tariff_match["duty_rate"]
            result["duty_source"] = "tariff_db"
        if tariff_match.get("exact_match"):
            result["verified"] = True
            result["verification_status"] = "verified"

    # ── Step 3: Cross-reference with Free Import Order API ──
    if free_import_result and free_import_result.get("found"):
        result["verification_sources"].append("free_import_order")
        # FIO confirms the HS code exists in official decree
        result["verified"] = True

        fio_items = free_import_result.get("items", [])
        for item in fio_items:
            item_hs = str(item.get("hs_code", "")).replace(".", "")
            if item_hs == hs_clean or hs_clean.startswith(item_hs.rstrip("0")):
                result["fio_description"] = item.get("description", "")
                result["fio_requirements"] = [
                    req.get("name", "") for req in item.get("legal_requirements", [])
                ]
                break

        if result.get("fio_requirements"):
            result["verification_status"] = "official"
        elif result["verified"]:
            result["verification_status"] = "verified"

    # ── Step 4: Determine final status ──
    sources = result["verification_sources"]
    if "free_import_order" in sources and "tariff_db" in sources:
        result["verification_status"] = "official"
        result["verified"] = True
    elif "tariff_db" in sources:
        result["verification_status"] = "verified"
        result["verified"] = True
    elif "free_import_order" in sources:
        result["verification_status"] = "verified"
        result["verified"] = True
    else:
        result["verification_status"] = "unverified"

    # ── Step 5: Cache the result ──
    _save_verification_cache(db, hs_clean, result)

    return result


# ═══════════════════════════════════════════════════════════════
#  2. VERIFY ALL CLASSIFICATIONS
# ═══════════════════════════════════════════════════════════════

def verify_all_classifications(db, classifications, free_import_results=None):
    """
    Verify all classifications from Agent 2 output.

    Args:
        db: Firestore client
        classifications: list of classification dicts (from Agent 2)
        free_import_results: dict hs_code → FIO result (optional)

    Returns:
        list of enriched classification dicts with verification fields
    """
    if not classifications:
        return []

    verified_count = 0
    official_count = 0

    for c in classifications:
        hs = c.get("hs_code", "")
        if not hs:
            continue

        fio = None
        if free_import_results:
            fio = free_import_results.get(hs)

        try:
            verification = verify_hs_code(db, hs, free_import_result=fio)

            # Enrich the classification with verification data
            c["verification_status"] = verification["verification_status"]
            c["verification_sources"] = verification["verification_sources"]
            c["purchase_tax"] = verification["purchase_tax"]
            c["vat_rate"] = verification["vat_rate"]

            # Override duty_rate with official source if available
            if verification.get("duty_rate") and verification.get("duty_source"):
                if not c.get("duty_rate") or verification["duty_source"] == "tariff_db":
                    c["duty_rate"] = verification["duty_rate"]
                    c["duty_source"] = verification["duty_source"]

            # Add official descriptions
            if verification.get("official_description_he"):
                c["official_description_he"] = verification["official_description_he"]
            if verification.get("official_description_en"):
                c["official_description_en"] = verification["official_description_en"]

            # FIO-specific fields
            if verification.get("fio_requirements"):
                c["fio_requirements"] = verification["fio_requirements"]

            if verification["verification_status"] == "official":
                official_count += 1
            if verification.get("verified"):
                verified_count += 1

        except Exception as e:
            print(f"    ⚠️ Verification error for {hs}: {e}")
            c["verification_status"] = "error"

    print(f"  🔍 VERIFICATION: {verified_count}/{len(classifications)} verified, "
          f"{official_count} official")

    return classifications


# ═══════════════════════════════════════════════════════════════
#  3. LEARN FROM VERIFICATION (cache + knowledge)
# ═══════════════════════════════════════════════════════════════

def learn_from_verification(db, classification):
    """
    Store verified classification in classification_knowledge for future lookups.
    Only stores verified items (not unverified guesses).
    """
    hs = classification.get("hs_code", "")
    status = classification.get("verification_status", "")
    if not hs or status in ("unverified", "error"):
        return

    desc = classification.get("item", classification.get("description", ""))
    if not desc:
        return

    # Safe document ID
    safe_desc = re.sub(r'[^\w\u0590-\u05FF]', '_', desc.lower())[:50]
    doc_id = f"verified_{hs.replace('.', '')}_{safe_desc}"

    try:
        doc_ref = db.collection("classification_knowledge").document(doc_id)
        doc = doc_ref.get()

        if doc.exists:
            # Update existing — bump usage count
            existing = doc.to_dict()
            usage = existing.get("usage_count", 0) + 1
            doc_ref.update({
                "usage_count": usage,
                "last_verified": datetime.now(timezone.utc).isoformat(),
                "verification_status": status,
                "verification_sources": classification.get("verification_sources", []),
            })
        else:
            # Create new verified entry
            doc_ref.set({
                "hs_code": hs,
                "description": desc[:200],
                "description_lower": desc.lower()[:200],
                "duty_rate": classification.get("duty_rate", ""),
                "purchase_tax": classification.get("purchase_tax", {}),
                "vat_rate": classification.get("vat_rate", ""),
                "verification_status": status,
                "verification_sources": classification.get("verification_sources", []),
                "official_description_he": classification.get("official_description_he", ""),
                "confidence_score": 80 if status == "official" else 65,
                "usage_count": 1,
                "source": "verification_loop",
                "type": "classification",
                "learned_at": datetime.now(timezone.utc).isoformat(),
                "last_verified": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        print(f"    ⚠️ Learn from verification error: {e}")


# ═══════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════

def _get_purchase_tax(chapter, heading):
    """Look up purchase tax by chapter and heading."""
    # Check specific subheadings first (alcohol)
    if heading in _PURCHASE_TAX_SUBHEADINGS:
        info = _PURCHASE_TAX_SUBHEADINGS[heading]
        return {
            "applies": True,
            "rate_he": info["rate_he"],
            "note_he": info["note_he"],
            "category": "alcohol",
        }

    # Check chapter-level
    if chapter in _PURCHASE_TAX:
        info = _PURCHASE_TAX[chapter]
        return {
            "applies": info["rate"] != "0%",
            "rate_he": info["rate_he"],
            "note_he": info.get("note_he", ""),
            "category": info["category"],
        }

    # Default: no purchase tax
    return {
        "applies": False,
        "rate_he": "לא חל",
        "note_he": "",
        "category": "general",
    }


def _check_verification_cache(db, hs_clean):
    """Check verification_cache for a recently verified HS code."""
    try:
        doc = db.collection("verification_cache").document(hs_clean).get()
        if not doc.exists:
            return None

        data = doc.to_dict()
        cached_at = data.get("cached_at", "")
        if not cached_at:
            return None

        # Check age
        try:
            cached_time = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - cached_time).days
            if age_days > CACHE_TTL_DAYS:
                return None  # Stale cache
            data["cache_age_days"] = age_days
        except (ValueError, TypeError):
            return None

        return data
    except Exception:
        return None


def _save_verification_cache(db, hs_clean, result):
    """Save verification result to cache."""
    try:
        cache_data = {
            "hs_code": result.get("hs_code", ""),
            "hs_clean": hs_clean,
            "chapter": result.get("chapter", ""),
            "verified": result.get("verified", False),
            "verification_status": result.get("verification_status", ""),
            "verification_sources": result.get("verification_sources", []),
            "duty_rate": result.get("duty_rate", ""),
            "duty_source": result.get("duty_source", ""),
            "purchase_tax": result.get("purchase_tax", {}),
            "vat_rate": result.get("vat_rate", ""),
            "official_description_he": result.get("official_description_he", ""),
            "official_description_en": result.get("official_description_en", ""),
            "fio_description": result.get("fio_description", ""),
            "fio_requirements": result.get("fio_requirements", []),
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        db.collection("verification_cache").document(hs_clean).set(cache_data)
    except Exception as e:
        print(f"    ⚠️ Cache save error: {e}")


def _verify_in_tariff_db(db, hs_clean):
    """Verify HS code exists in tariff database. Returns match or None."""
    # Subheading (6 digits) and heading (4 digits) for partial match
    subheading = hs_clean[:6] if len(hs_clean) >= 6 else hs_clean
    heading = hs_clean[:4] if len(hs_clean) >= 4 else hs_clean

    # Search order: hs_code_index (fastest), tariff_chapters, tariff
    collections = [
        ("hs_code_index", ["code", "hs_code"]),
        ("tariff_chapters", ["code", "hs_code"]),
        ("tariff", ["hs_code"]),
    ]

    for coll_name, code_fields in collections:
        try:
            # Try exact document lookup by ID first
            doc = db.collection(coll_name).document(hs_clean).get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    "exact_match": True,
                    "source": coll_name,
                    "description_he": data.get("description_he", data.get("title_he", "")),
                    "description_en": data.get("description_en", data.get("title_en", "")),
                    "duty_rate": data.get("duty_rate", ""),
                }

            # Try with dots format (e.g., "8471.30.0000")
            hs_dotted = _format_hs_dots(hs_clean)
            if hs_dotted != hs_clean:
                doc = db.collection(coll_name).document(hs_dotted).get()
                if doc.exists:
                    data = doc.to_dict()
                    return {
                        "exact_match": True,
                        "source": coll_name,
                        "description_he": data.get("description_he", data.get("title_he", "")),
                        "description_en": data.get("description_en", data.get("title_en", "")),
                        "duty_rate": data.get("duty_rate", ""),
                    }

            # Try heading-level lookup (4 digits)
            doc = db.collection(coll_name).document(heading).get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    "exact_match": False,
                    "source": coll_name,
                    "description_he": data.get("description_he", data.get("title_he", "")),
                    "description_en": data.get("description_en", data.get("title_en", "")),
                    "duty_rate": data.get("duty_rate", ""),
                }
        except Exception:
            continue

    return None


def _format_hs_dots(hs_clean):
    """Format clean HS code with dots: XXXX.XX.XXXXXX"""
    if len(hs_clean) >= 10:
        return f"{hs_clean[:4]}.{hs_clean[4:6]}.{hs_clean[6:10]}"
    elif len(hs_clean) >= 6:
        return f"{hs_clean[:4]}.{hs_clean[4:6]}"
    elif len(hs_clean) >= 4:
        return hs_clean[:4]
    return hs_clean
