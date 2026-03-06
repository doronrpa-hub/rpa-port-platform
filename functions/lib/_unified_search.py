"""Unified index search functions — used by _unified_index.py and broker_engine.py.

Provides:
  search_word(word) -> [(hs_code, source, weight), ...]
  search_phrase(phrase) -> [{hs_code, score, weight, sources}, ...]
  find_tariff_codes(description) -> [{hs_code, score, ..., description_he, duty_rate}, ...]
  get_heading_subcodes(heading_4digit) -> [{hs_code, description_he, ...}, ...]
  format_hs(hs_code) -> str  (XX.XX.XXXXXX/X Israeli format)
"""

import re


# ---------------------------------------------------------------------------
#  Israeli HS format  XX.XX.XXXXXX/X
# ---------------------------------------------------------------------------

def _hs_check_digit(digits):
    """Compute Luhn check digit for a 10-digit Israeli HS code."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def format_hs(hs_code):
    """Convert HS code to Israeli format XX.XX.XXXXXX/X (Luhn check digit)."""
    raw = str(hs_code)
    # Skip non-tariff codes (ORD:, FW:, chapter-only like "94", etc.)
    if ":" in raw or len(raw.replace(".", "").replace("/", "").replace(" ", "")) < 4:
        return raw
    check = ""
    if "/" in raw:
        raw, check = raw.split("/", 1)
    code = raw.replace(".", "").replace(" ", "").replace("_", "").split("_")[0]
    # Strip suffix like _0, _1 etc from index keys
    if not code.isdigit():
        code = re.sub(r'[^0-9]', '', code)
    code = code.ljust(10, "0")[:10]
    if len(code) >= 10 and code.isdigit():
        if not check:
            check = _hs_check_digit(code)
        return f"{code[:2]}.{code[2:4]}.{code[4:10]}/{check}"
    return str(hs_code)

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
#  Tree hierarchy: branch vs leaf detection
# ---------------------------------------------------------------------------

def _raw_digits(hs_key):
    """Extract raw 10-digit code from an index key like '8806200000' or '8806210000_8'."""
    return hs_key.split("_")[0].replace(".", "").ljust(10, "0")[:10]


def _find_index_key(hs_input):
    """Find the actual index key for an HS code (handles _suffix lookup)."""
    idx = _ensure_index()
    meta = idx["meta"]
    if hs_input in meta:
        return hs_input
    # Try with common suffixes (_0 through _9, then _a-_f)
    raw = _raw_digits(hs_input)
    for suffix in "0123456789abcdef":
        candidate = f"{raw}_{suffix}"
        if candidate in meta:
            return candidate
    # Try in HEADING_MAP
    heading = raw[:4]
    for c in idx["headings"].get(heading, []):
        if _raw_digits(c) == raw:
            return c
    return hs_input  # Return original if not found


def is_leaf(hs_key):
    """Check if an HS code is a leaf (no children) in the tariff tree.

    Branch nodes have Hebrew descriptions ending with ':-' (colon-dash).
    A code is also a branch if other codes in its heading share its first
    6 or 8 digits but differ in the remaining positions.
    """
    idx = _ensure_index()
    meta = idx["meta"]

    # Resolve to actual index key
    key = _find_index_key(hs_key)

    # Check description ending — definitive signal for branches
    m = meta.get(key, {})
    desc = m.get("he", "").rstrip()
    if desc.endswith(":-"):
        return False

    # Check if children exist in HEADING_MAP
    raw = _raw_digits(key)
    heading = raw[:4]
    codes = idx["headings"].get(heading, [])
    for c in codes:
        if c == hs_key:
            continue
        c_raw = _raw_digits(c)
        # A child shares a longer prefix but differs after
        if len(raw) >= 6 and c_raw[:6] == raw[:6] and c_raw != raw:
            # c could be a child of hs_key if hs_key is the broader code
            # Branch pattern: hs_key ends in more trailing zeros
            if raw[6:] == "0000" and c_raw[6:] != "0000":
                return False
            if raw[8:] == "00" and c_raw[:8] == raw[:8] and c_raw[8:] != "00":
                return False
    return True


def get_children(hs_key):
    """Get direct children of a branch code. Returns list of index keys.

    Israeli tariff tree structure:
      8806.00.0000 = heading-level branch (4-digit, digits 5-10 are 000000)
      8806.20.0000 = subheading branch (5-digit significant, digit 6+ = 0)
        children: 8806.21.0000, 8806.22.0000, ... (share first 5 digits of group)
      8806.21.0000 = sub-subheading branch (6-digit, digits 7-10 = 0000)
        children: 8806.21.1000, 8806.21.2000, ...

    The branch indicator is trailing zeros after the significant prefix.
    """
    idx = _ensure_index()
    raw = _raw_digits(hs_key)
    heading = raw[:4]
    codes = idx["headings"].get(heading, [])

    # Determine the significant prefix length of this branch
    # Find where trailing zeros start
    sig_len = 10
    for i in range(9, 3, -1):
        if raw[i] == "0":
            sig_len = i
        else:
            break

    if sig_len >= 10:
        return []  # No trailing zeros — not a branch

    # For subheading groups like 8806.20 (sig_len=5, digit at pos 5 is '0'):
    # Children share first (sig_len-1) digits but have non-zero at position sig_len-1
    # e.g., 880620 -> children share '88062' (first 5) with different 6th digit
    # For heading groups like 8806.00 (sig_len=4):
    # Children share first 4 digits

    # Strategy: children share raw[:sig_len-1] but differ at position sig_len-1
    # UNLESS this is a "X0" group where the 0 is part of the group identifier
    # Better: just find all codes that share the longest non-zero prefix
    prefix = raw[:sig_len]

    # For groups like 8806.20 (prefix='88062'), children are 88062X where X!=0
    # They share raw[:5]='88062'
    group_prefix = prefix.rstrip("0") or prefix[:4]
    if len(group_prefix) < 4:
        group_prefix = raw[:4]

    children = []
    for c in codes:
        if c == hs_key:
            continue
        c_raw = _raw_digits(c)
        if c_raw == raw:
            continue
        # Child must share the group prefix and be "under" this branch
        if c_raw.startswith(group_prefix) and len(c_raw) >= len(raw):
            # Make sure it's actually under this branch, not a sibling
            # For 8806200000 (group '88062'): 8806210000 starts with '88062' ✓
            # For 8806000000 (group '8806'): 8806100000 starts with '8806' ✓
            # But we must not include siblings of the same level
            # A child has MORE significant digits than the parent
            c_sig = 10
            for i in range(9, 3, -1):
                if c_raw[i] == "0":
                    c_sig = i
                else:
                    break
            if c_sig > sig_len or c_sig >= 10:
                children.append(c)
    return children


def resolve_to_leaves(hs_key):
    """If hs_key is a branch, return its leaf children. If leaf, return [hs_key].

    Recursively resolves: if a child is also a branch, drill into its children.
    """
    if is_leaf(hs_key):
        return [hs_key]

    children = get_children(hs_key)
    if not children:
        # Fallback: if we think it's a branch but can't find children, return it
        return [hs_key]

    leaves = []
    for child in children:
        leaves.extend(resolve_to_leaves(child))
    return leaves


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

    # Collect raw results, then resolve branches to leaves
    raw_results = []
    meta = idx["meta"]
    for hs, info in agg.items():
        if info["score"] < min_score:
            continue
        raw_results.append((hs, info))

    # Resolve branches: if a code is a branch, expand to its leaf children
    results = []
    seen = set()
    for hs, info in raw_results:
        leaves = resolve_to_leaves(hs)
        for leaf in leaves:
            if leaf in seen:
                continue
            seen.add(leaf)
            m = meta.get(leaf, {})
            results.append({
                "hs_code": format_hs(leaf),
                "hs_raw": leaf,
                "score": info["score"],
                "weight": info["weight"],
                "sources": sorted(info["sources"]),
                "description_he": m.get("he", ""),
                "description_en": m.get("en", ""),
                "duty_rate": m.get("duty", ""),
                "purchase_tax": m.get("pt", ""),
                "resolved_from": format_hs(hs) if leaf != hs else None,
            })

    results.sort(key=lambda r: (r["score"], r["weight"]), reverse=True)
    return results[:20]


def get_heading_subcodes(heading_4digit, leaves_only=True):
    """Get all sub-codes under a 4-digit heading.

    Args:
        heading_4digit: 4-digit heading (e.g. "8806" or "88.06")
        leaves_only: if True (default), skip branch codes that have children

    Returns list of {hs_code, description_he, description_en, duty_rate, purchase_tax}.
    """
    idx = _ensure_index()
    heading = str(heading_4digit).replace(".", "").replace("/", "")[:4]
    codes = idx["headings"].get(heading, [])
    meta = idx["meta"]
    results = []
    for hs in codes:
        if leaves_only and not is_leaf(hs):
            continue
        m = meta.get(hs, {})
        results.append({
            "hs_code": format_hs(hs),
            "hs_raw": hs,
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
