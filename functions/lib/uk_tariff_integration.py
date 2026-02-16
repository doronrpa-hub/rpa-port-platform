"""
UK Tariff API Integration for RCB
===================================
Verifies Israeli HS classifications against the UK Trade Tariff.
Uses the free UK Gov API (no key required).

Session 28D — Assignment 18
R.P.A.PORT LTD - February 2026

API docs: https://www.trade-tariff.service.gov.uk/api/v2/
"""

import logging
import re
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger("rcb.uk_tariff")

UK_API_BASE = "https://www.trade-tariff.service.gov.uk/api/v2"
UK_API_TIMEOUT = 10  # seconds
UK_CACHE_HOURS = 168  # 7 days


# ═══════════════════════════════════════════
#  CODE CONVERSION
# ═══════════════════════════════════════════

def convert_il_to_uk_code(il_code):
    """
    Convert Israeli HS code to UK 10-digit commodity code.
    Israeli codes are typically 8-10 digits.  UK uses 10 digits.
    The first 6 digits (HS) are internationally harmonized.
    """
    clean = str(il_code).replace(".", "").replace("/", "").replace(" ", "")
    # Remove non-digits
    clean = re.sub(r'\D', '', clean)
    if not clean:
        return None
    # Pad to 10 digits
    return clean.ljust(10, "0")[:10]


def convert_uk_to_il_code(uk_code):
    """
    Convert UK 10-digit code back to likely Israeli format.
    Returns the raw 10-digit code — caller formats as needed.
    """
    clean = str(uk_code).replace(".", "").replace("/", "").replace(" ", "")
    clean = re.sub(r'\D', '', clean)
    if not clean:
        return None
    return clean[:10] if len(clean) >= 10 else clean


# ═══════════════════════════════════════════
#  LIVE API FETCH (synchronous)
# ═══════════════════════════════════════════

def fetch_uk_tariff_live(uk_code):
    """
    Fetch commodity details from UK Trade Tariff API.
    Free, no key required.  Returns dict or None on failure.

    API: GET /api/v2/commodities/{10-digit-code}
    """
    clean = str(uk_code).replace(".", "").replace(" ", "")
    if len(clean) < 6:
        logger.warning(f"UK code too short for API lookup: {clean}")
        return None

    url = f"{UK_API_BASE}/commodities/{clean}"
    try:
        resp = requests.get(url, timeout=UK_API_TIMEOUT, headers={
            "Accept": "application/json",
        })
        if resp.status_code == 404:
            logger.info(f"UK tariff not found for {clean}")
            return {"uk_code": clean, "found": False, "error": "not_found"}
        if resp.status_code == 200:
            data = resp.json()
            return _parse_uk_api_response(data, clean)
        logger.warning(f"UK API returned {resp.status_code} for {clean}")
        return None
    except requests.exceptions.Timeout:
        logger.warning(f"UK API timeout for {clean}")
        return None
    except Exception as e:
        logger.warning(f"UK API error for {clean}: {e}")
        return None


def _parse_uk_api_response(data, uk_code):
    """Parse the UK Trade Tariff API JSON response into our standard format."""
    result = {
        "uk_code": uk_code,
        "found": True,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    # Extract from "data" envelope
    commodity = data.get("data", {})
    attrs = commodity.get("attributes", {})

    result["description"] = attrs.get("description", "")
    result["formatted_description"] = attrs.get("formatted_description", "")
    result["number_indents"] = attrs.get("number_indents", 0)
    result["goods_nomenclature_item_id"] = attrs.get("goods_nomenclature_item_id", uk_code)

    # Build heading from code
    heading_4 = uk_code[:4] if len(uk_code) >= 4 else uk_code
    result["heading"] = f"{heading_4[:2]}.{heading_4[2:4]}" if len(heading_4) >= 4 else heading_4

    # Extract ancestors (parent headings/chapters)
    ancestors = []
    included = data.get("included", [])
    for inc in included:
        if inc.get("type") in ("chapter", "heading", "subheading"):
            inc_attrs = inc.get("attributes", {})
            ancestors.append({
                "type": inc["type"],
                "description": inc_attrs.get("description", ""),
                "goods_nomenclature_item_id": inc_attrs.get("goods_nomenclature_item_id", ""),
            })
    result["ancestors"] = ancestors

    # Extract footnotes
    footnotes = []
    for inc in included:
        if inc.get("type") == "footnote":
            inc_attrs = inc.get("attributes", {})
            footnotes.append(inc_attrs.get("description", ""))
    result["footnotes"] = footnotes

    # Extract duty info if present
    for inc in included:
        if inc.get("type") == "duty_expression":
            inc_attrs = inc.get("attributes", {})
            result["duty_expression"] = inc_attrs.get("base", "")
            break

    return result


# ═══════════════════════════════════════════
#  FIRESTORE CACHE LOOKUP
# ═══════════════════════════════════════════

def lookup_uk_tariff(db, il_code):
    """
    Look up UK tariff data for an Israeli HS code.
    1. Check tariff_uk Firestore cache
    2. If miss or stale, fetch live from UK API
    3. Store result in cache

    Returns dict with UK tariff info or None.
    """
    uk_code = convert_il_to_uk_code(il_code)
    if not uk_code:
        return None

    # Step 1: Check Firestore cache
    cached = _check_uk_cache(db, uk_code)
    if cached:
        return cached

    # Step 2: Live fetch
    live = fetch_uk_tariff_live(uk_code)
    if not live:
        return None

    # Step 3: Store in cache
    if live.get("found"):
        _store_uk_cache(db, uk_code, il_code, live)

    return live


def _check_uk_cache(db, uk_code):
    """Check tariff_uk collection for cached data. Returns dict or None."""
    try:
        doc = db.collection("tariff_uk").document(uk_code).get()
        if doc.exists:
            data = doc.to_dict()
            # Check freshness
            fetched_at = data.get("fetched_at", "")
            if fetched_at and _is_cache_fresh(fetched_at):
                return data
            # Stale — will re-fetch
            return None
        return None
    except Exception as e:
        logger.warning(f"UK cache lookup error for {uk_code}: {e}")
        return None


def _is_cache_fresh(fetched_at_iso):
    """Check if a cached entry is still fresh (within UK_CACHE_HOURS)."""
    try:
        fetched = datetime.fromisoformat(fetched_at_iso.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - fetched).total_seconds() / 3600
        return age_hours < UK_CACHE_HOURS
    except (ValueError, TypeError):
        return False


def _store_uk_cache(db, uk_code, il_code, data):
    """Store UK tariff data in Firestore cache."""
    try:
        doc = {
            "uk_code": uk_code,
            "il_code": il_code,
            "description": data.get("description", ""),
            "formatted_description": data.get("formatted_description", ""),
            "heading": data.get("heading", ""),
            "ancestors": data.get("ancestors", []),
            "footnotes": data.get("footnotes", []),
            "duty_expression": data.get("duty_expression", ""),
            "found": data.get("found", True),
            "fetched_at": data.get("fetched_at", datetime.now(timezone.utc).isoformat()),
        }
        db.collection("tariff_uk").document(uk_code).set(doc)
    except Exception as e:
        logger.warning(f"Failed to cache UK tariff {uk_code}: {e}")


# ═══════════════════════════════════════════
#  DESCRIPTION MATCHING
# ═══════════════════════════════════════════

def simple_description_match(desc_il, desc_uk):
    """
    Compare Israeli and UK descriptions using word overlap.
    Returns a similarity score 0.0 - 1.0.
    """
    if not desc_il or not desc_uk:
        return 0.0

    # Normalize: lowercase, remove HTML tags, remove punctuation
    def normalize(text):
        text = re.sub(r'<[^>]+>', ' ', str(text))  # strip HTML
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = set(text.split())
        # Remove very short words (articles, etc)
        words = {w for w in words if len(w) > 2}
        return words

    words_il = normalize(desc_il)
    words_uk = normalize(desc_uk)

    if not words_il or not words_uk:
        return 0.0

    overlap = words_il & words_uk
    # Jaccard-like similarity (using smaller set as denominator for more lenient matching)
    smaller = min(len(words_il), len(words_uk))
    return len(overlap) / smaller if smaller > 0 else 0.0


# ═══════════════════════════════════════════
#  CLASSIFICATION COMPARISON
# ═══════════════════════════════════════════

def compare_il_uk_classification(db, il_code, il_description=""):
    """
    Full comparison of Israeli HS code against UK tariff.
    Used by justification_engine Step 9.

    Returns:
        dict with match_level, uk_data, similarity, verification_note
    """
    uk_data = lookup_uk_tariff(db, il_code)
    if not uk_data:
        return {
            "match_level": "no_data",
            "uk_data": None,
            "similarity": 0.0,
            "verification_note": "UK tariff data unavailable",
            "uk_code": convert_il_to_uk_code(il_code),
        }

    if not uk_data.get("found"):
        return {
            "match_level": "not_found",
            "uk_data": uk_data,
            "similarity": 0.0,
            "verification_note": f"UK commodity code {uk_data.get('uk_code', '')} not found in UK tariff",
            "uk_code": uk_data.get("uk_code", ""),
        }

    # Compare descriptions
    uk_desc = uk_data.get("description", "") or uk_data.get("formatted_description", "")
    similarity = simple_description_match(il_description, uk_desc) if il_description else 0.0

    # Check ancestor descriptions too for broader match
    ancestor_similarity = 0.0
    for anc in uk_data.get("ancestors", []):
        anc_sim = simple_description_match(il_description, anc.get("description", ""))
        ancestor_similarity = max(ancestor_similarity, anc_sim)

    best_similarity = max(similarity, ancestor_similarity)

    # Determine match level
    il_clean = str(il_code).replace(".", "").replace("/", "").replace(" ", "")
    uk_clean = str(uk_data.get("uk_code", "")).replace(".", "").replace("/", "").replace(" ", "")

    # Check code alignment at different levels
    il_heading = il_clean[:4] if len(il_clean) >= 4 else ""
    uk_heading = uk_clean[:4] if len(uk_clean) >= 4 else ""
    il_6 = il_clean[:6] if len(il_clean) >= 6 else ""
    uk_6 = uk_clean[:6] if len(uk_clean) >= 6 else ""

    if il_6 and uk_6 and il_6 == uk_6:
        match_level = "strong"
        note = f"UK tariff confirms: 6-digit match ({il_6}). Description similarity: {best_similarity:.0%}"
    elif il_heading and uk_heading and il_heading == uk_heading:
        match_level = "moderate"
        note = f"UK heading match ({il_heading}), subheading differs. Similarity: {best_similarity:.0%}"
    elif best_similarity >= 0.5:
        match_level = "description_match"
        note = f"Codes differ but descriptions overlap ({best_similarity:.0%})"
    else:
        match_level = "weak"
        note = f"UK code {uk_clean} — low alignment with IL code {il_clean}"

    return {
        "match_level": match_level,
        "uk_data": uk_data,
        "similarity": round(best_similarity, 3),
        "verification_note": note,
        "uk_code": uk_data.get("uk_code", ""),
        "uk_description": uk_desc,
    }


# ═══════════════════════════════════════════
#  CROSS-CHECKER HOOK
# ═══════════════════════════════════════════

def get_uk_verification_for_cross_check(db, primary_hs, item_description=""):
    """
    Simplified UK verification for the cross-checker.
    Returns a result dict compatible with cross_checker model format.
    """
    try:
        comparison = compare_il_uk_classification(db, primary_hs, item_description)

        uk_code_raw = comparison.get("uk_code", "")
        # Normalize to digits only
        uk_clean = re.sub(r'\D', '', uk_code_raw) if uk_code_raw else None

        match_level = comparison.get("match_level", "no_data")

        if match_level in ("strong", "moderate"):
            # UK agrees — provide the HS code as a vote
            confidence = 0.9 if match_level == "strong" else 0.6
            return {
                "hs_code": uk_clean,
                "confidence": confidence,
                "reason": comparison.get("verification_note", ""),
                "source": "uk_tariff",
                "match_level": match_level,
            }
        elif match_level == "description_match":
            return {
                "hs_code": uk_clean,
                "confidence": 0.4,
                "reason": comparison.get("verification_note", ""),
                "source": "uk_tariff",
                "match_level": match_level,
            }
        else:
            # No meaningful data — don't add as voter
            return {
                "hs_code": None,
                "confidence": 0,
                "reason": comparison.get("verification_note", "UK data unavailable"),
                "source": "uk_tariff",
                "match_level": match_level,
            }
    except Exception as e:
        logger.warning(f"UK cross-check failed: {e}")
        return {
            "hs_code": None,
            "confidence": 0,
            "reason": f"UK lookup error: {e}",
            "source": "uk_tariff",
            "match_level": "error",
        }


# ═══════════════════════════════════════════
#  POST-CLASSIFICATION ON-DEMAND FETCH
# ═══════════════════════════════════════════

def post_classification_uk_fetch(db, classification_result):
    """
    After classification, fetch UK tariff data for each classified item
    and store in tariff_uk collection for future lookups.

    Args:
        db: Firestore client
        classification_result: dict with 'classifications' list

    Returns:
        dict with fetched_count, cached_count, errors
    """
    stats = {"fetched": 0, "already_cached": 0, "errors": 0, "items_checked": 0}

    classifications = classification_result.get("classifications", [])
    if not classifications:
        return stats

    for cls in classifications[:5]:  # Limit to 5 items
        hs_code = cls.get("hs_code", "")
        if not hs_code:
            continue

        stats["items_checked"] += 1
        uk_code = convert_il_to_uk_code(hs_code)
        if not uk_code:
            continue

        try:
            # Check if already cached
            cached = _check_uk_cache(db, uk_code)
            if cached:
                stats["already_cached"] += 1
                continue

            # Fetch live
            live = fetch_uk_tariff_live(uk_code)
            if live and live.get("found"):
                _store_uk_cache(db, uk_code, hs_code, live)
                stats["fetched"] += 1
            elif live:
                stats["errors"] += 1
        except Exception as e:
            logger.warning(f"Post-classification UK fetch error for {hs_code}: {e}")
            stats["errors"] += 1

    return stats
