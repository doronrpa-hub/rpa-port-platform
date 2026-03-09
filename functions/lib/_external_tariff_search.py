"""External Tariff Search — rescue path for unknown products.

When local index returns zero candidates, query 3 external sources
simultaneously: UK Trade Tariff API + Shaarolami EN + Shaarolami HE.
All FREE, no API keys required.

Session 97 — external tariff rescue.
"""

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

import requests

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

_UK_SEARCH_URL = "https://www.trade-tariff.service.gov.uk/api/v2/search"
_SHAAROLAMI_BASE = "https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb"
_TIMEOUT = 8
_CACHE_TTL_DAYS = 30

_HEADERS_UK = {"Accept": "application/json"}
_HEADERS_SHAAROLAMI = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                  " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

_RE_SHAAROLAMI_ITEM = re.compile(
    r'>\s*(\d{10}(?:/\d)?)\s*</span>'
    r'.*?hidden-sm-inline[^>]*>([^<]+)</div>',
    re.DOTALL,
)


# ---------------------------------------------------------------------------
#  UK Trade Tariff search
# ---------------------------------------------------------------------------

def _search_uk_tariff(query: str) -> List[Dict[str, Any]]:
    """Search UK Trade Tariff free API. Returns list of candidate dicts."""
    try:
        resp = requests.get(
            _UK_SEARCH_URL,
            params={"q": query},
            headers=_HEADERS_UK,
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        data = resp.json().get("data", {})
        attrs = data.get("attributes", {})

        results = []

        # Exact match
        entry = attrs.get("entry") or {}
        entry_id = str(entry.get("id", ""))
        if entry_id and len(entry_id) >= 6:
            hs = entry_id[:10].ljust(10, "0")
            results.append({
                "hs_code": hs,
                "description": f"UK exact match: {entry_id}",
                "source": "uk_trade_tariff",
            })

        # Fuzzy match — headings + commodities
        gnm = attrs.get("goods_nomenclature_match") or {}
        for section in ("commodities", "headings"):
            for item in (gnm.get(section) or [])[:5]:
                gni = str(item.get("goods_nomenclature_item_id", ""))
                desc = item.get("description", "") or ""
                if gni and len(gni) >= 4:
                    hs = gni[:10].ljust(10, "0")
                    if not any(r["hs_code"] == hs for r in results):
                        results.append({
                            "hs_code": hs,
                            "description": desc[:200],
                            "source": "uk_trade_tariff",
                        })

        return results[:8]
    except Exception:
        return []


# ---------------------------------------------------------------------------
#  Shaarolami search (standalone — no class dependency)
# ---------------------------------------------------------------------------

def _search_shaarolami(query: str, lang: str = "en") -> List[Dict[str, Any]]:
    """Query shaarolami customs site. Returns list of candidate dicts."""
    try:
        url = f"{_SHAAROLAMI_BASE}/{lang}/CustomsBook/Import/CustomsTaarifEntry"
        resp = requests.get(
            url,
            params={"freeText": query},
            headers=_HEADERS_SHAAROLAMI,
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200 or len(resp.text) < 100:
            return []

        resp.encoding = "utf-8"
        matches = _RE_SHAAROLAMI_ITEM.findall(resp.text)
        results = []
        for code, desc in matches[:10]:
            hs = code.replace("/", "").ljust(10, "0")[:10]
            results.append({
                "hs_code": hs,
                "description": desc.strip()[:200],
                "source": f"shaarolami_{lang}",
            })
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
#  Merge + confidence scoring
# ---------------------------------------------------------------------------

def _merge_results(all_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate by 4-digit heading, boost confidence when sources agree."""
    heading_map: Dict[str, Dict[str, Any]] = {}  # heading -> best candidate
    heading_sources: Dict[str, set] = {}  # heading -> set of source names

    for r in all_results:
        hs = str(r.get("hs_code", ""))
        if len(hs) < 4:
            continue
        heading = hs[:4]
        source = r.get("source", "")

        if heading not in heading_sources:
            heading_sources[heading] = set()
        heading_sources[heading].add(source)

        # Keep the most specific (longest) code per heading
        if heading not in heading_map or len(hs) > len(str(heading_map[heading].get("hs_code", ""))):
            heading_map[heading] = dict(r)

    merged = []
    for heading, candidate in heading_map.items():
        n_sources = len(heading_sources.get(heading, set()))
        if n_sources >= 2:
            candidate["confidence"] = 0.45
        elif "uk_trade_tariff" in heading_sources.get(heading, set()):
            candidate["confidence"] = 0.30
        else:
            candidate["confidence"] = 0.35
        candidate["source_count"] = n_sources
        merged.append(candidate)

    # Sort by confidence desc, then by specificity (longer hs_code first)
    merged.sort(key=lambda x: (-x.get("confidence", 0), -len(str(x.get("hs_code", "")))))
    return merged[:6]


# ---------------------------------------------------------------------------
#  Firestore cache helpers
# ---------------------------------------------------------------------------

def _cache_key(query: str) -> str:
    return hashlib.md5(query.lower().strip().encode()).hexdigest()


def _check_cache(db, query_en: str) -> Optional[List[Dict[str, Any]]]:
    if not db:
        return None
    try:
        doc = db.collection("external_tariff_cache").document(_cache_key(query_en)).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        ts = data.get("timestamp")
        if ts and isinstance(ts, datetime):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - ts > timedelta(days=_CACHE_TTL_DAYS):
                return None
        return data.get("candidates", [])
    except Exception:
        return None


def _write_cache(db, query_en: str, candidates: List[Dict[str, Any]]):
    if not db or not candidates:
        return
    try:
        db.collection("external_tariff_cache").document(_cache_key(query_en)).set({
            "query": query_en.lower().strip(),
            "candidates": candidates,
            "timestamp": datetime.now(timezone.utc),
        })
    except Exception:
        pass


# ---------------------------------------------------------------------------
#  Main entry point
# ---------------------------------------------------------------------------

def external_tariff_search(
    query_en: str,
    query_he: str = "",
    db=None,
) -> List[Dict[str, Any]]:
    """Search external tariff sources for unknown products.

    Fires 3 queries simultaneously (UK API + Shaarolami EN + Shaarolami HE).
    Returns merged, deduplicated candidates with LOW confidence (0.30-0.45).

    Args:
        query_en: English product description
        query_he: Hebrew product description (optional)
        db: Firestore client (optional, for caching)

    Returns:
        List of candidate dicts: [{hs_code, confidence, description, source}]
        Empty list on failure.
    """
    if not query_en or len(query_en.strip()) < 3:
        return []

    try:
        # Check cache first
        cached = _check_cache(db, query_en)
        if cached is not None:
            return cached

        # Fire queries simultaneously: UK + Shaarolami EN/HE
        # Also try UK with last 2 words (e.g. "stuffed grape leaves" → "grape leaves")
        q_en = query_en.strip()
        q_he = (query_he or query_en).strip()
        words = q_en.split()
        q_en_short = " ".join(words[-2:]) if len(words) > 2 else ""

        all_results = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(_search_uk_tariff, q_en): "uk_full",
                pool.submit(_search_shaarolami, q_en, "en"): "shaarolami_en",
                pool.submit(_search_shaarolami, q_he, "he"): "shaarolami_he",
            }
            if q_en_short:
                futures[pool.submit(_search_uk_tariff, q_en_short)] = "uk_short"
            for future in as_completed(futures, timeout=12):
                try:
                    results = future.result(timeout=1)
                    if results:
                        all_results.extend(results)
                except Exception:
                    pass

        if not all_results:
            return []

        # Merge, deduplicate, score
        merged = _merge_results(all_results)

        # Resolve to Israeli leaf codes via unified index (if available)
        try:
            from lib._unified_search import get_heading_subcodes
            resolved = []
            seen_hs = set()
            for cand in merged:
                heading = str(cand.get("hs_code", ""))[:4]
                subcodes = get_heading_subcodes(heading, leaves_only=True)
                if subcodes:
                    for sc in subcodes[:3]:
                        sc_hs = sc.get("hs_code", "")
                        if sc_hs and sc_hs not in seen_hs:
                            seen_hs.add(sc_hs)
                            resolved.append({
                                "hs_code": sc_hs,
                                "confidence": cand.get("confidence", 0.30),
                                "description": sc.get("description_he") or sc.get("description_en") or cand.get("description", ""),
                                "source": cand.get("source", "external"),
                                "rescue_source": "external_tariff_search",
                            })
                else:
                    # No local leaf found — keep external code as-is
                    hs = cand.get("hs_code", "")
                    if hs and hs not in seen_hs:
                        seen_hs.add(hs)
                        cand["rescue_source"] = "external_tariff_search"
                        resolved.append(cand)
            if resolved:
                merged = resolved[:8]
        except ImportError:
            pass

        # Cache results (fire-and-forget)
        _write_cache(db, query_en, merged)

        return merged

    except Exception:
        return []
