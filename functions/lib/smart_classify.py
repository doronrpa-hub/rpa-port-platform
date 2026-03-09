"""Smart Classify — synonym expansion layer BEFORE unified index search.

Pipeline:
  query → synonym_expand() → search unified index → verify via shaarolami
        → cross-check chapter notes → return candidates

Does NOT replace anything. Sits in front of the existing search.

Public API:
    expand_query(query_text) -> list of (expanded_term, source, confidence)
    classify_product(query, db=None) -> ClassificationResult
"""

import re
import time
import hashlib
import requests
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Set
from enum import Enum


# ---------------------------------------------------------------------------
#  Confidence levels
# ---------------------------------------------------------------------------

class Confidence(Enum):
    HIGH = "HIGH"        # Word exists in tariff vocabulary
    MEDIUM = "MEDIUM"    # Found via shaarolami lookup
    LOW = "LOW"          # Found via web search fallback


# ---------------------------------------------------------------------------
#  Classification result
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    """Result of classify_product()."""
    hs_candidates: list = field(default_factory=list)
    confidence: str = ""
    reasoning: list = field(default_factory=list)
    questions_to_ask: list = field(default_factory=list)
    expanded_terms: list = field(default_factory=list)
    query: str = ""

    def __repr__(self):
        lines = [f"ClassificationResult(query={self.query!r})"]
        if self.expanded_terms:
            lines.append(f"  Expanded terms:")
            for term, src, conf in self.expanded_terms:
                lines.append(f"    {term!r} ({src}, {conf})")
        if self.hs_candidates:
            lines.append(f"  Candidates ({len(self.hs_candidates)}):")
            for c in self.hs_candidates[:10]:
                hs = c.get("hs_code", c.get("hs", "?"))
                desc = c.get("description_he", "") or c.get("desc_he", "")
                score = c.get("score", "")
                conf = c.get("confidence", "")
                line = f"    {hs}"
                if desc:
                    line += f"  {desc[:60]}"
                if score:
                    line += f"  (score={score})"
                if conf:
                    line += f"  [conf={conf}]"
                lines.append(line)
        if self.reasoning:
            lines.append(f"  Reasoning:")
            for r in self.reasoning:
                lines.append(f"    - {r}")
        if self.questions_to_ask:
            lines.append(f"  Questions:")
            for q in self.questions_to_ask:
                lines.append(f"    ? {q}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
#  Hebrew text processing
# ---------------------------------------------------------------------------

_HE_PREFIXES = ("של", "וה", "מה", "לה", "בה", "כש", "מ", "ב", "ל", "ה", "ו", "כ", "ש")
_WORD_SPLIT_RE = re.compile(r'[^\w\u0590-\u05FF]+')
_STOP_WORDS = frozenset({
    "את", "של", "על", "עם", "או", "גם", "כי", "אם", "לא", "יש", "זה",
    "אל", "הם", "הוא", "היא", "בין", "כל", "מן", "אשר", "עד", "רק",
    "the", "a", "an", "of", "for", "and", "or", "with", "to", "from",
    "in", "on", "by", "is", "are", "not", "other", "others",
})


def _tokenize(text: str) -> List[str]:
    """Split text into words, lowercase, filter stop words."""
    if not text:
        return []
    words = _WORD_SPLIT_RE.split(text.lower())
    return [w for w in words if len(w) >= 2 and w not in _STOP_WORDS]


def _strip_prefixes(word: str) -> List[str]:
    """Return word + prefix-stripped variants."""
    variants = [word]
    if len(word) > 3:
        for pfx in _HE_PREFIXES:
            if word.startswith(pfx) and len(word) - len(pfx) >= 2:
                stripped = word[len(pfx):]
                if stripped not in variants:
                    variants.append(stripped)
    return variants


# ---------------------------------------------------------------------------
#  Step 1: Build vocabulary from tariff tree
# ---------------------------------------------------------------------------

_HE_VOCAB: Optional[Dict[str, List[str]]] = None
_EN_VOCAB: Optional[Dict[str, List[str]]] = None
_VOCAB_BUILT = False


def _build_vocab_from_tree():
    """Parse the full tariff tree and extract every unique word → HS node mapping."""
    global _HE_VOCAB, _EN_VOCAB, _VOCAB_BUILT

    if _VOCAB_BUILT:
        return

    _HE_VOCAB = {}
    _EN_VOCAB = {}

    try:
        from lib.tariff_tree import load_tariff_tree
    except ImportError:
        try:
            from tariff_tree import load_tariff_tree
        except ImportError:
            print("[smart_classify] WARNING: tariff_tree not available")
            _VOCAB_BUILT = True
            return

    try:
        nodes, fc_index, root_ids = load_tariff_tree()
    except Exception as e:
        print(f"[smart_classify] WARNING: Could not load tariff tree: {e}")
        _VOCAB_BUILT = True
        return

    if not nodes:
        print("[smart_classify] WARNING: Tariff tree is empty")
        _VOCAB_BUILT = True
        return

    for nid, node in nodes.items():
        node_key = node.fc or str(nid)

        # Hebrew description words
        if node.desc_he:
            for w in _tokenize(node.desc_he):
                for variant in _strip_prefixes(w):
                    if variant not in _HE_VOCAB:
                        _HE_VOCAB[variant] = []
                    _HE_VOCAB[variant].append(node_key)

        # English description words
        if node.desc_en:
            for w in _tokenize(node.desc_en):
                if w not in _EN_VOCAB:
                    _EN_VOCAB[w] = []
                _EN_VOCAB[w].append(node_key)

    _VOCAB_BUILT = True
    print(f"[smart_classify] Vocab built: {len(_HE_VOCAB)} Hebrew words, {len(_EN_VOCAB)} English words")


def _ensure_vocab():
    """Lazy-load the vocabulary."""
    if not _VOCAB_BUILT:
        _build_vocab_from_tree()


def get_vocab_stats() -> dict:
    """Return vocabulary statistics (for testing/debugging)."""
    _ensure_vocab()
    return {
        "he_words": len(_HE_VOCAB) if _HE_VOCAB else 0,
        "en_words": len(_EN_VOCAB) if _EN_VOCAB else 0,
    }


# ---------------------------------------------------------------------------
#  Shaarolami query (Step 2 — MEDIUM confidence fallback)
# ---------------------------------------------------------------------------

_SHAAROLAMI_BASE = "https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb"
_SHAAROLAMI_SEARCH_HE = f"{_SHAAROLAMI_BASE}/he/CustomsBook/Import/CustomsTaarifEntry"
_SHAAROLAMI_SEARCH_EN = f"{_SHAAROLAMI_BASE}/en/CustomsBook/Import/CustomsTaarifEntry"
_SHAAROLAMI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}
_SHAAROLAMI_CACHE: Dict[str, Optional[List[Tuple[str, str]]]] = {}

# Regex to extract HS codes + descriptions from shaarolami HTML
_RE_SHAAROLAMI_ITEM = re.compile(
    r'>\s*(\d{10}(?:/\d)?)\s*</span>'
    r'.*?hidden-sm-inline[^>]*>([^<]+)</div>',
    re.DOTALL,
)


def _query_shaarolami(term: str, lang: str = "he") -> Optional[List[Tuple[str, str]]]:
    """Query shaarolami for a term. Returns list of (hs_code, description) or None.

    Caches results to avoid hammering the server.
    """
    cache_key = f"{lang}:{term.lower()}"
    if cache_key in _SHAAROLAMI_CACHE:
        return _SHAAROLAMI_CACHE[cache_key]

    url = _SHAAROLAMI_SEARCH_HE if lang == "he" else _SHAAROLAMI_SEARCH_EN
    try:
        resp = requests.get(
            url,
            params={"freeText": term},
            headers=_SHAAROLAMI_HEADERS,
            timeout=15,
        )
        if resp.status_code != 200 or len(resp.text) < 100:
            _SHAAROLAMI_CACHE[cache_key] = None
            return None

        resp.encoding = "utf-8"
        matches = _RE_SHAAROLAMI_ITEM.findall(resp.text)
        if matches:
            results = [(code.replace("/", "").ljust(10, "0")[:10], desc.strip())
                       for code, desc in matches[:20]]
            _SHAAROLAMI_CACHE[cache_key] = results
            return results
    except Exception:
        pass

    _SHAAROLAMI_CACHE[cache_key] = None
    return None


def _extract_official_terms_from_shaarolami(results: List[Tuple[str, str]]) -> List[str]:
    """Extract official tariff terms from shaarolami results."""
    terms = []
    for _code, desc in results:
        for w in _tokenize(desc):
            if w not in _STOP_WORDS and len(w) >= 3 and w not in terms:
                terms.append(w)
    return terms[:10]


# ---------------------------------------------------------------------------
#  Web search fallback (Step 2 — LOW confidence)
# ---------------------------------------------------------------------------

def _web_search_tariff_term(term: str) -> Optional[str]:
    """Search web for 'פרט מכס {term}' or 'HS code {term} Israel'.

    Returns a single official tariff term if found, or None.
    This is the last resort — confidence is LOW.
    """
    # Try WebSearch tool if available, otherwise skip
    try:
        # Quick attempt: query shaarolami in English if Hebrew term failed
        en_results = _query_shaarolami(term, lang="en")
        if en_results:
            official_terms = _extract_official_terms_from_shaarolami(en_results)
            if official_terms:
                return official_terms[0]
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
#  Step 2: Synonym expansion
# ---------------------------------------------------------------------------

# Import synonym map from the builder if available
_BUILDER_SYNONYMS: Optional[dict] = None


def _get_builder_synonyms() -> dict:
    """Return synonym map for query expansion.

    This is a superset of the builder's _HE_EN_SYNONYMS, with additional
    domain-specific synonyms (food, materials, products) needed for
    classification queries. The builder's synonyms are for INDEX BUILDING;
    these are for QUERY EXPANSION.
    """
    global _BUILDER_SYNONYMS
    if _BUILDER_SYNONYMS is not None:
        return _BUILDER_SYNONYMS

    _BUILDER_SYNONYMS = {
        "שרימפס": ["shrimp", "prawn", "חסילון", "סרטנים", "crustacean"],
        "shrimp": ["שרימפס", "prawn", "חסילון", "סרטנים", "crustacean", "crustaceans"],
        "prawn": ["שרימפס", "shrimp", "סרטנים", "crustacean"],
        "סרטנים": ["crustacean", "crustaceans", "שרימפס", "shrimp", "prawn", "חסילון"],
        "crustacean": ["סרטנים", "שרימפס", "shrimp", "crustaceans"],
        "crustaceans": ["סרטנים", "שרימפס", "shrimp", "crustacean"],
        "חסילון": ["shrimp", "prawn", "שרימפס", "סרטנים"],
        "lobster": ["לובסטר", "סרטנים", "crustacean"],
        "לובסטר": ["lobster", "סרטנים", "crustacean"],
        "crab": ["סרטן", "סרטנים", "crustacean"],
        "סרטן": ["crab", "סרטנים", "crustacean"],
        "ספה": ["sofa", "couch", "ספות", "מושבים", "כורסה", "ריהוט"],
        "sofa": ["ספה", "ספות", "couch", "מושבים"],
        "couch": ["ספה", "sofa", "ספות"],
        "כורסה": ["armchair", "ספה", "מושב"],
        "כיסא": ["chair", "seat", "מושב"],
        "ריהוט": ["furniture", "רהיט", "רהיטים"],
        "furniture": ["ריהוט", "רהיט", "רהיטים"],
        "פלדה": ["steel", "iron"],
        "steel": ["פלדה", "ברזל"],
        "ברזל": ["iron", "steel", "פלדה"],
        "גומי": ["rubber", "caoutchouc"],
        "rubber": ["גומי"],
        "פלסטיק": ["plastic", "polymer"],
        "plastic": ["פלסטיק"],
        "בד": ["fabric", "textile", "cloth"],
        "textile": ["בד", "טקסטיל", "אריג"],
        "צמיג": ["tire", "tyre", "pneumatic"],
        "tire": ["צמיג", "tyre"],
        "עץ": ["wood", "timber"],
        "wood": ["עץ"],
        "נייר": ["paper", "cardboard"],
        "paper": ["נייר"],
        "זכוכית": ["glass"],
        "glass": ["זכוכית"],
        "אלומיניום": ["aluminum", "aluminium"],
        "aluminum": ["אלומיניום"],
        "סוללה": ["battery", "accumulator", "cell"],
        "battery": ["סוללה", "מצבר"],
        "מנוע": ["motor", "engine"],
        "motor": ["מנוע"],
        "engine": ["מנוע"],
        "מחשב": ["computer"],
        "computer": ["מחשב"],
        "מקרר": ["refrigerator", "fridge"],
        "refrigerator": ["מקרר"],
        "תרופה": ["medicine", "drug", "pharmaceutical"],
        "medicine": ["תרופה", "רפואה"],
        "דג": ["fish"],
        "fish": ["דג", "דגים"],
        "דגים": ["fish", "דג"],
        "בשר": ["meat"],
        "meat": ["בשר"],
        "חלב": ["milk", "dairy"],
        "milk": ["חלב"],
        "ירק": ["vegetable"],
        "vegetable": ["ירק", "ירקות"],
        "פרי": ["fruit"],
        "fruit": ["פרי", "פירות"],
        "frozen": ["קפוא", "קפואים", "קפואה"],
        "קפוא": ["frozen"],
        "קפואים": ["frozen"],
        "מבושל": ["cooked", "prepared"],
        "cooked": ["מבושל"],
        "מקולף": ["peeled", "shelled"],
        "peeled": ["מקולף"],
        "מנוקה": ["cleaned", "deveined"],
        "cleaned": ["מנוקה"],
        "מרופד": ["upholstered", "padded"],
        "upholstered": ["מרופד", "ריפוד"],
        "תלת": ["three", "triple"],
        "מושבית": ["seat", "seater"],
    }
    return _BUILDER_SYNONYMS


def expand_query(query_text: str) -> List[Tuple[str, str, str]]:
    """Expand a query using tariff vocabulary, synonyms, and shaarolami.

    Returns list of (expanded_term, source, confidence) tuples.

    For each word in the query:
    1. If word exists in he_vocab or en_vocab → HIGH confidence
    2. If not → query shaarolami → MEDIUM confidence
    3. If shaarolami returns nothing → web fallback → LOW confidence
    """
    _ensure_vocab()

    results: List[Tuple[str, str, str]] = []
    seen_terms: Set[str] = set()
    words = _tokenize(query_text)

    if not words:
        return results

    synonyms = _get_builder_synonyms()

    for word in words:
        variants = _strip_prefixes(word)
        found_in_vocab = False

        # Check each variant against vocabulary
        for variant in variants:
            if _HE_VOCAB and variant in _HE_VOCAB:
                if variant not in seen_terms:
                    results.append((variant, "tariff_tree_he", Confidence.HIGH.value))
                    seen_terms.add(variant)
                found_in_vocab = True
                break
            if _EN_VOCAB and variant in _EN_VOCAB:
                if variant not in seen_terms:
                    results.append((variant, "tariff_tree_en", Confidence.HIGH.value))
                    seen_terms.add(variant)
                found_in_vocab = True
                break

        if found_in_vocab:
            # Also add known synonyms for cross-language coverage
            for variant in variants:
                if variant in synonyms:
                    for syn in synonyms[variant]:
                        syn_lower = syn.lower()
                        if syn_lower not in seen_terms:
                            results.append((syn_lower, "synonym", Confidence.HIGH.value))
                            seen_terms.add(syn_lower)
            continue

        # Check synonyms — if synonym is in vocab, use that
        synonym_found = False
        for variant in variants:
            if variant in synonyms:
                for syn in synonyms[variant]:
                    syn_lower = syn.lower()
                    if _HE_VOCAB and syn_lower in _HE_VOCAB:
                        if syn_lower not in seen_terms:
                            results.append((syn_lower, "synonym_he", Confidence.HIGH.value))
                            seen_terms.add(syn_lower)
                        synonym_found = True
                    elif _EN_VOCAB and syn_lower in _EN_VOCAB:
                        if syn_lower not in seen_terms:
                            results.append((syn_lower, "synonym_en", Confidence.HIGH.value))
                            seen_terms.add(syn_lower)
                        synonym_found = True
                if synonym_found:
                    break

        if synonym_found:
            # Also keep the original word as-is
            if word not in seen_terms:
                results.append((word, "original", Confidence.HIGH.value))
                seen_terms.add(word)
            continue

        # Not in vocab or synonyms — try shaarolami
        shaarolami_results = _query_shaarolami(word)
        if shaarolami_results:
            official_terms = _extract_official_terms_from_shaarolami(shaarolami_results)
            for ot in official_terms[:3]:
                if ot not in seen_terms:
                    results.append((ot, "shaarolami", Confidence.MEDIUM.value))
                    seen_terms.add(ot)
            # Keep original too
            if word not in seen_terms:
                results.append((word, "original", Confidence.MEDIUM.value))
                seen_terms.add(word)
            continue

        # Last resort — try English shaarolami
        web_term = _web_search_tariff_term(word)
        if web_term and web_term not in seen_terms:
            results.append((web_term, "web_search", Confidence.LOW.value))
            seen_terms.add(web_term)

        # Always keep the original word
        if word not in seen_terms:
            results.append((word, "original", Confidence.LOW.value))
            seen_terms.add(word)

    return results


# ---------------------------------------------------------------------------
#  Chapter notes cross-check (כולל / אינו כולל)
# ---------------------------------------------------------------------------

def _get_chapter_notes_for_code(hs_code: str, db=None) -> Optional[dict]:
    """Get chapter notes for the chapter of an HS code.

    Uses tariff_tree for hierarchy, falls back to Firestore chapter_notes.
    """
    digits = str(hs_code).replace(".", "").replace("/", "").replace(" ", "")
    if len(digits) < 2:
        return None
    chapter = digits[:2]

    # Try tariff tree first — get section > chapter node and check notes
    try:
        from lib.tariff_tree import search_tree
    except ImportError:
        try:
            from tariff_tree import search_tree
        except ImportError:
            search_tree = None

    # Try Firestore chapter_notes
    if db:
        try:
            doc = db.collection("chapter_notes").document(f"chapter_{chapter}").get()
            if doc.exists:
                return doc.to_dict()
        except Exception:
            pass

    return None


def _check_chapter_notes_exclusion(candidate: dict, query_words: List[str],
                                    all_candidates: list, db=None) -> Optional[str]:
    """Check if chapter notes exclude or include this candidate for the product.

    Returns:
      - "excluded: {reason}" if chapter notes say this product doesn't belong
      - "included: {reason}" if chapter notes confirm this product belongs
      - None if no relevant chapter note found
    """
    hs_code = candidate.get("hs_raw", candidate.get("hs_code", ""))
    notes = _get_chapter_notes_for_code(hs_code, db)
    if not notes:
        return None

    query_text = " ".join(query_words).lower()

    # Check exclusions (אינו כולל / does not include / excluding)
    exclusions = notes.get("exclusions", [])
    if isinstance(exclusions, str):
        exclusions = [exclusions]
    for excl in exclusions:
        excl_lower = (excl or "").lower()
        # Check if any query word appears in an exclusion clause
        for word in query_words:
            if len(word) >= 3 and word in excl_lower:
                return f"excluded: chapter note says '{excl[:80]}'"

    # Check inclusions (כולל / includes)
    inclusions = notes.get("inclusions", [])
    if isinstance(inclusions, str):
        inclusions = [inclusions]
    for incl in inclusions:
        incl_lower = (incl or "").lower()
        for word in query_words:
            if len(word) >= 3 and word in incl_lower:
                return f"included: chapter note confirms '{incl[:80]}'"

    # Check preamble for scope
    preamble = (notes.get("preamble", "") or "").lower()
    if preamble:
        for word in query_words:
            if len(word) >= 3 and word in preamble:
                return f"included: preamble mentions '{word}'"

    return None


# ---------------------------------------------------------------------------
#  GIR Rule 1: Most specific description wins
# ---------------------------------------------------------------------------

def _score_specificity(candidate: dict, query_words: List[str]) -> float:
    """Score how specifically a candidate's description matches the query.

    GIR Rule 1: The heading which provides the most specific description
    shall be preferred to headings providing a more general description.
    """
    desc_he = (candidate.get("description_he", "") or candidate.get("desc_he", "")).lower()
    desc_en = (candidate.get("description_en", "") or candidate.get("desc_en", "")).lower()
    combined = f"{desc_he} {desc_en}"

    if not combined.strip():
        return 0.0

    # Count matching query words
    matches = 0
    for word in query_words:
        for variant in _strip_prefixes(word):
            if variant in combined:
                matches += 1
                break

    # Word coverage ratio
    coverage = matches / max(len(query_words), 1)

    # Penalize vague/catch-all descriptions
    vague_indicators = ["אחרים", "אחר", "n.e.s.", "other", "others", "not elsewhere"]
    vague_penalty = 0.0
    for vi in vague_indicators:
        if vi in combined:
            vague_penalty = 0.15
            break

    # Bonus for leaf codes (more specific than branch codes)
    level_bonus = 0.0
    hs_raw = candidate.get("hs_raw", "")
    if hs_raw:
        digits = hs_raw.replace(".", "")
        trailing_zeros = len(digits) - len(digits.rstrip("0"))
        if trailing_zeros <= 2:
            level_bonus = 0.1  # Leaf-level code

    return coverage + level_bonus - vague_penalty


# ---------------------------------------------------------------------------
#  Step 3: classify_product
# ---------------------------------------------------------------------------

def classify_product(query: str, db=None) -> ClassificationResult:
    """Classify a product description into HS code candidates.

    Pipeline:
    1. expand_query() — synonym expansion
    2. Search unified index with expanded terms
    3. Cross-check chapter notes (כולל / אינו כולל)
    4. Apply GIR Rule 1 — most specific description wins
    5. Return: hs_candidates[], confidence, reasoning, questions_to_ask[]
    """
    result = ClassificationResult(query=query)
    query_words = _tokenize(query)

    if not query_words:
        result.reasoning.append("Empty or unparseable query")
        return result

    # --- Step 1: Expand query ---
    expanded = expand_query(query)
    result.expanded_terms = expanded

    # Collect all search terms
    search_terms_he = set()
    search_terms_en = set()
    for term, source, confidence in expanded:
        # Detect language by character range
        if any('\u0590' <= c <= '\u05FF' for c in term):
            search_terms_he.add(term)
        else:
            search_terms_en.add(term)

    result.reasoning.append(
        f"Expanded {len(query_words)} query words → "
        f"{len(search_terms_he)} Hebrew + {len(search_terms_en)} English terms"
    )

    # --- Step 2a: Search TARIFF TREE for product nouns (synonym-expanded) ---
    # Product nouns (terms from synonym expansion) are the most important —
    # "סרטנים" matters more than "מקולף" for classification.
    #
    # Heuristic: the FIRST query word is typically the product noun.
    # Synonyms of the first word get a higher tree search weight (product_noun_boost).
    # Material/attribute words (בד, מרופד, קפוא, etc.) get normal weight.
    tree_candidates = []
    synonym_terms = {}  # term -> is_primary_noun (bool)

    # Identify primary noun: first query word and its synonyms
    primary_noun_synonyms = set()
    if query_words:
        first_word = query_words[0]
        primary_noun_synonyms.add(first_word)
        for variant in _strip_prefixes(first_word):
            if variant in _get_builder_synonyms():
                for syn in _get_builder_synonyms()[variant]:
                    primary_noun_synonyms.add(syn.lower())

    for term, source, confidence in expanded:
        if source in ("synonym_he", "synonym_en", "synonym"):
            is_primary = term in primary_noun_synonyms
            synonym_terms[term] = is_primary
    # Also include original words that resolved to vocab via synonyms
    for term, source, confidence in expanded:
        if source == "original" and confidence == Confidence.HIGH.value:
            is_primary = term in primary_noun_synonyms
            synonym_terms[term] = is_primary

    try:
        from lib.tariff_tree import search_tree as _search_tree
    except ImportError:
        try:
            from tariff_tree import search_tree as _search_tree
        except ImportError:
            _search_tree = None

    if _search_tree and synonym_terms:
        for term, is_primary in synonym_terms.items():
            hits = _search_tree(term)
            # Primary noun (product identity) gets 8 points; modifier gets 3
            base_score = 8 if is_primary else 3
            for hit in hits:
                if hit.get("level", 0) >= 3:  # Heading level or deeper
                    tree_candidates.append({
                        "hs_code": hit.get("hs", ""),
                        "hs_raw": hit.get("fc", ""),
                        "description_he": hit.get("desc_he", ""),
                        "description_en": hit.get("desc_en", ""),
                        "score": base_score,
                        "weight": 10,
                        "sources": ["TREE"],
                        "tree_match_term": term,
                        "tree_path": [p.get("desc_he", "")[:40] for p in hit.get("path", [])],
                        "is_primary_noun_match": is_primary,
                    })
        if tree_candidates:
            result.reasoning.append(
                f"Tariff tree search for product nouns → {len(tree_candidates)} candidates"
            )

    # --- Step 2b: Search unified index ---
    try:
        from lib._unified_search import find_tariff_codes, search_phrase, index_loaded
    except ImportError:
        try:
            from _unified_search import find_tariff_codes, search_phrase, index_loaded
        except ImportError:
            result.reasoning.append("Unified index not available")
            # Still have tree candidates
            if tree_candidates:
                result.hs_candidates = tree_candidates[:15]
                result.confidence = "MEDIUM"
            return result

    if not index_loaded() and not tree_candidates:
        result.reasoning.append("Unified index not loaded (empty)")
        return result

    # Search with Hebrew terms
    he_candidates = []
    if search_terms_he:
        he_query = " ".join(search_terms_he)
        he_candidates = find_tariff_codes(he_query)
        result.reasoning.append(f"Hebrew search '{he_query[:50]}' → {len(he_candidates)} candidates")

    # Search with English terms
    en_candidates = []
    if search_terms_en:
        en_query = " ".join(search_terms_en)
        en_candidates = find_tariff_codes(en_query)
        result.reasoning.append(f"English search '{en_query[:50]}' → {len(en_candidates)} candidates")

    # Also search with original query directly
    orig_candidates = find_tariff_codes(query)
    result.reasoning.append(f"Original query search → {len(orig_candidates)} candidates")

    # --- Merge candidates ---
    merged = {}

    # Tree candidates get priority — they matched product nouns in the hierarchy
    for c in tree_candidates:
        key = c.get("hs_raw", c.get("hs_code", ""))
        if not key:
            continue
        if key not in merged:
            merged[key] = dict(c)
            merged[key]["match_sources"] = set()
            merged[key]["combined_score"] = 0
        merged[key]["match_sources"].add("tree")
        merged[key]["combined_score"] += c.get("score", 5)  # Tree match = 5 points
        if c.get("weight", 0) > merged[key].get("weight", 0):
            merged[key]["weight"] = c["weight"]

    for clist, source_label in [
        (he_candidates, "he_expanded"),
        (en_candidates, "en_expanded"),
        (orig_candidates, "original"),
    ]:
        for c in clist:
            key = c.get("hs_raw", c.get("hs_code", ""))
            if not key:
                continue
            if key not in merged:
                merged[key] = dict(c)
                merged[key]["match_sources"] = set()
                merged[key]["combined_score"] = 0
            merged[key]["match_sources"].add(source_label)
            merged[key]["combined_score"] += c.get("score", 1)
            # Keep best weight
            if c.get("weight", 0) > merged[key].get("weight", 0):
                merged[key]["weight"] = c["weight"]

    # --- Chapter agreement boost ---
    # If Hebrew and English agree on a chapter, boost those candidates
    he_chapters = set()
    en_chapters = set()
    for c in he_candidates[:5]:
        hs = c.get("hs_raw", "")
        if hs:
            he_chapters.add(hs[:2])
    for c in en_candidates[:5]:
        hs = c.get("hs_raw", "")
        if hs:
            en_chapters.add(hs[:2])
    agreed_chapters = he_chapters & en_chapters
    if agreed_chapters:
        result.reasoning.append(f"Chapter agreement (HE+EN): {', '.join(sorted(agreed_chapters))}")
        for key, c in merged.items():
            if key[:2] in agreed_chapters:
                c["combined_score"] += 3
                c["chapter_agreement"] = True

    # --- Step 3: Cross-check chapter notes ---
    all_candidates = list(merged.values())
    for c in all_candidates:
        note_result = _check_chapter_notes_exclusion(c, query_words, all_candidates, db)
        if note_result:
            c["chapter_note"] = note_result
            if note_result.startswith("excluded:"):
                c["combined_score"] -= 5
                result.reasoning.append(
                    f"Chapter note exclusion for {c.get('hs_code', '?')}: {note_result}"
                )
            elif note_result.startswith("included:"):
                c["combined_score"] += 2
                result.reasoning.append(
                    f"Chapter note inclusion for {c.get('hs_code', '?')}: {note_result}"
                )

    # --- Step 4: Apply GIR Rule 1 scoring ---
    for c in all_candidates:
        specificity = _score_specificity(c, query_words)
        c["specificity"] = specificity
        c["combined_score"] += specificity * 3

    # --- Sort by combined score ---
    all_candidates.sort(key=lambda c: c.get("combined_score", 0), reverse=True)

    # --- Finalize ---
    # Convert match_sources from set to list for serialization
    for c in all_candidates:
        if "match_sources" in c:
            c["match_sources"] = sorted(c["match_sources"])

    result.hs_candidates = all_candidates[:15]

    # Determine overall confidence
    if result.hs_candidates:
        top = result.hs_candidates[0]
        top_score = top.get("combined_score", 0)
        has_chapter_agreement = top.get("chapter_agreement", False)
        has_high_conf_terms = any(conf == Confidence.HIGH.value
                                  for _, _, conf in expanded)

        if top_score >= 10 and has_chapter_agreement and has_high_conf_terms:
            result.confidence = "HIGH"
        elif top_score >= 5 and (has_chapter_agreement or has_high_conf_terms):
            result.confidence = "MEDIUM"
        else:
            result.confidence = "LOW"

        # Check score gap between #1 and #2
        if len(result.hs_candidates) >= 2:
            second_score = result.hs_candidates[1].get("combined_score", 0)
            gap = top_score - second_score
            if gap < 2:
                result.questions_to_ask.append(
                    "Multiple headings have similar scores — "
                    "what is the primary material or function of the product?"
                )
                result.reasoning.append(
                    f"Close competition: #{1} score={top_score:.1f} vs #{2} score={second_score:.1f}"
                )
    else:
        result.confidence = "NONE"
        result.questions_to_ask.append("No matching tariff codes found — please provide more detail")

    # Add heading-level question if top candidates span multiple chapters
    if len(result.hs_candidates) >= 2:
        chapters = set()
        for c in result.hs_candidates[:5]:
            hs = c.get("hs_raw", "")
            if hs:
                chapters.add(hs[:2])
        if len(chapters) >= 3:
            result.questions_to_ask.append(
                f"Candidates span {len(chapters)} chapters ({', '.join(sorted(chapters))}) — "
                "what is the product's essential character?"
            )

    return result


# ---------------------------------------------------------------------------
#  Utility: reset caches (for testing)
# ---------------------------------------------------------------------------

def reset_caches():
    """Reset all module-level caches. For testing only."""
    global _HE_VOCAB, _EN_VOCAB, _VOCAB_BUILT, _SHAAROLAMI_CACHE, _BUILDER_SYNONYMS
    _HE_VOCAB = None
    _EN_VOCAB = None
    _VOCAB_BUILT = False
    _SHAAROLAMI_CACHE = {}
    _BUILDER_SYNONYMS = None
