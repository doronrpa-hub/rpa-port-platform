"""Unified index search functions — used by _unified_index.py and broker_engine.py.

Provides:
  search_word(word) -> [(hs_code, source, weight), ...]
  search_phrase(phrase) -> [{hs_code, score, weight, sources}, ...]
  find_tariff_codes(description) -> [{hs_code, score, ..., description_he, duty_rate}, ...]
  get_heading_subcodes(heading_4digit) -> [{hs_code, description_he, ...}, ...]
"""

import re

# ---------------------------------------------------------------------------
#  Hebrew text processing (must match builder's _tokenize exactly)
# ---------------------------------------------------------------------------
_HE_PREFIXES = ("\u05d5", "\u05d4", "\u05d1", "\u05dc", "\u05db", "\u05de", "\u05e9")
_HE_COMPOUND = (
    "\u05d5\u05d4", "\u05e9\u05dc", "\u05de\u05d4", "\u05dc\u05d4",
    "\u05d1\u05d4", "\u05db\u05e9", "\u05e9\u05d1", "\u05e9\u05d4",
    "\u05e9\u05de", "\u05e9\u05dc",
)
_STOP = frozenset({
    "\u05d0\u05ea", "\u05e9\u05dc", "\u05e2\u05dc", "\u05e2\u05dd",
    "\u05d0\u05d5", "\u05d2\u05dd", "\u05db\u05d9", "\u05d0\u05dd",
    "\u05dc\u05d0", "\u05d9\u05e9", "\u05d6\u05d4", "\u05d0\u05dc",
    "\u05d4\u05dd", "\u05d4\u05d5\u05d0", "\u05d4\u05d9\u05d0",
    "\u05d1\u05d9\u05df", "\u05db\u05dc", "\u05de\u05df",
    "\u05d0\u05e9\u05e8", "\u05e2\u05d3", "\u05e8\u05e7",
    "the", "a", "an", "of", "for", "and", "or", "with",
    "to", "from", "in", "on", "by", "is", "are", "was", "were",
    "be", "been", "new", "used", "set", "pcs", "piece", "pieces",
    "item", "items", "type", "other", "others", "not",
})

_WORD_SPLIT_RE = re.compile(r'[^\w\u0590-\u05FF]+')


def _tok(text):
    """Tokenize for search — same logic as builder."""
    if not text:
        return []
    words = _WORD_SPLIT_RE.split(text.lower())
    tokens = []
    for w in words:
        if len(w) < 2 or w in _STOP:
            continue
        tokens.append(w)
        if len(w) > 3:
            for pfx in _HE_COMPOUND:
                if w.startswith(pfx) and len(w) - len(pfx) >= 2:
                    tokens.append(w[len(pfx):])
                    break
            else:
                for pfx in _HE_PREFIXES:
                    if w.startswith(pfx) and len(w) - len(pfx) >= 2:
                        tokens.append(w[len(pfx):])
                        break
    return list(dict.fromkeys(tokens))


# ---------------------------------------------------------------------------
#  Lazy import of index data
# ---------------------------------------------------------------------------
_INDEX = None


def _ensure_index():
    """Lazy-load the generated index data."""
    global _INDEX
    if _INDEX is not None:
        return _INDEX

    try:
        from lib._unified_index import WORD_INDEX, HEADING_MAP, HS_META
    except ImportError:
        try:
            from _unified_index import WORD_INDEX, HEADING_MAP, HS_META
        except ImportError:
            # Index not built yet — return empty
            _INDEX = {"words": {}, "headings": {}, "meta": {}}
            return _INDEX

    _INDEX = {"words": WORD_INDEX, "headings": HEADING_MAP, "meta": HS_META}
    return _INDEX


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

def search_word(word):
    """Search index for a single word. Returns [(hs_code, source, weight), ...]."""
    idx = _ensure_index()
    wi = idx["words"]

    w = word.lower().strip()
    results = wi.get(w, [])

    # Also try prefix-stripped
    if not results and len(w) > 3:
        for pfx in _HE_COMPOUND + _HE_PREFIXES:
            if w.startswith(pfx):
                stripped = w[len(pfx):]
                if stripped and len(stripped) >= 2:
                    results = wi.get(stripped, [])
                    if results:
                        break
    return results


def search_phrase(phrase, min_score=2):
    """Search index for a phrase (multiple words). Returns sorted candidates.

    Each candidate: {hs_code, score, sources, weight}
    Score = number of query words that matched this HS code.
    """
    tokens = _tok(phrase)
    if not tokens:
        return []

    # Aggregate: hs_code -> {score, weight, sources}
    agg = {}
    for token in tokens:
        hits = search_word(token)
        for hs, src, wt in hits:
            if hs not in agg:
                agg[hs] = {"score": 0, "weight": 0, "sources": set()}
            agg[hs]["score"] += 1
            agg[hs]["weight"] += wt
            agg[hs]["sources"].add(src)

    # Filter and sort
    results = []
    for hs, info in agg.items():
        if info["score"] >= min_score or (info["score"] >= 1 and info["weight"] >= 5):
            results.append({
                "hs_code": hs,
                "score": info["score"],
                "weight": info["weight"],
                "sources": sorted(info["sources"]),
            })

    results.sort(key=lambda r: (r["score"], r["weight"]), reverse=True)
    return results[:20]


def find_tariff_codes(description, min_score=1):
    """Find candidate HS codes for a product description.

    Like search_phrase but filters to tariff codes only (no ORD/FW/PR/etc).
    Returns candidates with metadata from HS_META.
    """
    idx = _ensure_index()
    tokens = _tok(description)
    if not tokens:
        return []

    agg = {}
    for token in tokens:
        hits = search_word(token)
        for hs, src, wt in hits:
            # Only tariff-relevant sources
            if src in ("T", "CN", "CD", "FI", "CH", "DC", "C98"):
                if hs not in agg:
                    agg[hs] = {"score": 0, "weight": 0, "sources": set()}
                agg[hs]["score"] += 1
                agg[hs]["weight"] += wt
                agg[hs]["sources"].add(src)

    results = []
    meta = idx["meta"]
    for hs, info in agg.items():
        if info["score"] < min_score:
            continue
        m = meta.get(hs, {})
        results.append({
            "hs_code": hs,
            "score": info["score"],
            "weight": info["weight"],
            "sources": sorted(info["sources"]),
            "description_he": m.get("he", ""),
            "description_en": m.get("en", ""),
            "duty_rate": m.get("duty", ""),
            "purchase_tax": m.get("pt", ""),
        })

    results.sort(key=lambda r: (r["score"], r["weight"]), reverse=True)
    return results[:20]


def get_heading_subcodes(heading_4digit):
    """Get all sub-codes under a 4-digit heading.

    Returns list of {hs_code, description_he, description_en, duty_rate, purchase_tax}.
    """
    idx = _ensure_index()
    heading = str(heading_4digit).replace(".", "").replace("/", "")[:4]
    codes = idx["headings"].get(heading, [])
    meta = idx["meta"]
    results = []
    for hs in codes:
        m = meta.get(hs, {})
        results.append({
            "hs_code": hs,
            "description_he": m.get("he", ""),
            "description_en": m.get("en", ""),
            "duty_rate": m.get("duty", ""),
            "purchase_tax": m.get("pt", ""),
        })
    return results


def index_loaded():
    """Check if the unified index is available and has data."""
    idx = _ensure_index()
    return bool(idx["words"])
