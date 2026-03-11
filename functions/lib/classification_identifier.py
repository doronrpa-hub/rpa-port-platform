"""
Classification Identifier — Stage 1 of the reasoning engine.

Parallel product identification: runs 6 search sources concurrently,
then converges results by 4-digit heading with confidence scoring.

INPUT:  raw product string (Hebrew or English)
OUTPUT: list of HSCandidate dicts ranked by confidence

Sources:
  1. tariff_tree  desc_he  (Hebrew description match)
  2. tariff_tree  desc_en  (English description match)
  3. chapter_notes          (product term in notes/inclusions)
  4. Firestore tariff       (description field text search)
  5. UK Trade Tariff API    (free text search)
  6. Israeli English tariff (shaarolami — ground truth, 1.5x weight)

Does NOT touch broker_engine.py.
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

logger = logging.getLogger('rcb.identifier')

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

_UK_SEARCH_URL = "https://www.trade-tariff.service.gov.uk/api/v2/search"
_IL_EN_TARIFF_URL = "https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb/en/CustomsBook/Import/CustomsTaarifEntry"
_UK_TIMEOUT = 8  # seconds
_IL_TIMEOUT = 10  # seconds — Israeli site can be slower
_MAX_RESULTS = 15

# Source weight multipliers for convergence scoring
# Israeli English tariff is ground truth — same legal codes, same chapter notes
_SOURCE_WEIGHTS = {
    'tree_he': 1.0,
    'tree_en': 1.0,
    'chapter_notes': 1.0,
    'tariff_index': 1.0,
    'uk_tariff': 1.0,
    'il_en_tariff': 1.5,  # Israeli EN = 1.5x weight (authoritative)
}

# Hebrew prefix stripping (same set used across the codebase)
_HE_PREFIXES = ('של', 'וה', 'מה', 'לה', 'בה', 'כש', 'שב', 'שה', 'שמ', 'של',
                 'מ', 'ב', 'ל', 'ה', 'ו', 'כ', 'ש')

# Stop words (bilingual)
_STOP = frozenset({
    'את', 'של', 'על', 'עם', 'או', 'גם', 'כי', 'אם',
    'לא', 'יש', 'זה', 'אל', 'הם', 'הוא', 'היא',
    'בין', 'כל', 'מן', 'אשר', 'עד', 'רק',
    'the', 'a', 'an', 'of', 'for', 'and', 'or', 'with',
    'to', 'from', 'in', 'on', 'by', 'is', 'are', 'not',
    'new', 'used', 'set', 'pcs', 'piece', 'pieces',
    'item', 'items', 'type', 'other', 'others',
})

_WORD_RE = re.compile(r'[^\w\u0590-\u05FF]+')


# ---------------------------------------------------------------------------
#  Data structures
# ---------------------------------------------------------------------------

def make_candidate(hs_code, confidence, sources, desc_he='', desc_en='',
                   chapter='', duty_rate=''):
    """Build an HSCandidate dict compatible with elimination_engine."""
    heading = hs_code[:4] if len(hs_code) >= 4 else hs_code
    ch = hs_code[:2] if len(hs_code) >= 2 else ''
    return {
        'hs_code': hs_code,
        'heading': heading,
        'chapter': ch,
        'subheading': '',
        'section': '',
        'confidence': confidence,
        'source': 'identifier',
        'sources': list(sources),
        'description': desc_en,
        'description_en': desc_en,
        'description_he': desc_he,
        'duty_rate': duty_rate,
        'alive': True,
        'elimination_reason': '',
        'eliminated_at_level': '',
    }


# ---------------------------------------------------------------------------
#  Text utilities
# ---------------------------------------------------------------------------

def _tokenize(text):
    """Split text into searchable tokens with Hebrew prefix stripping."""
    if not text:
        return []
    words = _WORD_RE.split(text.lower())
    tokens = []
    for w in words:
        if len(w) < 2 or w in _STOP:
            continue
        tokens.append(w)
        # Strip Hebrew prefixes for variant matching
        if len(w) > 3:
            for pfx in _HE_PREFIXES:
                if w.startswith(pfx) and len(w) - len(pfx) >= 2:
                    tokens.append(w[len(pfx):])
                    break
    return list(dict.fromkeys(tokens))  # dedup, preserve order


def _heading_from_code(code):
    """Extract 4-digit heading from any HS code format."""
    digits = re.sub(r'[^0-9]', '', str(code))
    if len(digits) >= 4:
        return digits[:4]
    return digits


def _is_hebrew(text):
    """Check if text contains Hebrew characters."""
    return bool(re.search(r'[\u0590-\u05FF]', text or ''))


# ---------------------------------------------------------------------------
#  Source 1: tariff_tree desc_he search
# ---------------------------------------------------------------------------

def _search_tree_hebrew(product, tree_search_func):
    """Search tariff_tree by Hebrew description."""
    results = []
    try:
        matches = tree_search_func(product)
        for m in matches[:30]:
            if m.get('level', 0) < 3:  # skip section/chapter level
                continue
            fc = m.get('fc', '')
            heading = _heading_from_code(fc)
            if heading:
                results.append({
                    'heading': heading,
                    'fc': fc,
                    'desc_he': m.get('desc_he', ''),
                    'desc_en': m.get('desc_en', ''),
                    'level': m.get('level', 0),
                    'source': 'tree_he',
                })
    except Exception as e:
        print(f'[identifier] tree_he error: {e}')
    return results


# ---------------------------------------------------------------------------
#  Source 2: tariff_tree desc_en search
# ---------------------------------------------------------------------------

def _search_tree_english(product, tree_search_func):
    """Search tariff_tree by English description."""
    results = []
    try:
        matches = tree_search_func(product)
        for m in matches[:30]:
            if m.get('level', 0) < 3:
                continue
            fc = m.get('fc', '')
            heading = _heading_from_code(fc)
            if heading:
                results.append({
                    'heading': heading,
                    'fc': fc,
                    'desc_he': m.get('desc_he', ''),
                    'desc_en': m.get('desc_en', ''),
                    'level': m.get('level', 0),
                    'source': 'tree_en',
                })
    except Exception as e:
        print(f'[identifier] tree_en error: {e}')
    return results


# ---------------------------------------------------------------------------
#  Source 3: chapter_notes (inclusions/notes text search)
# ---------------------------------------------------------------------------

def _search_chapter_notes(product, db):
    """Search Firestore chapter_notes for product terms in notes/inclusions."""
    results = []
    if db is None:
        return results

    tokens = _tokenize(product)
    if not tokens:
        return results

    try:
        docs = db.collection('chapter_notes').stream()
        for doc in docs:
            data = doc.to_dict()
            chapter = doc.id.replace('chapter_', '')
            if len(chapter) > 2:
                continue

            # Build searchable text from notes, inclusions, preamble
            search_text = ' '.join([
                data.get('preamble', ''),
                data.get('preamble_en', ''),
                ' '.join(data.get('notes', [])) if isinstance(data.get('notes'), list) else str(data.get('notes', '')),
                ' '.join(data.get('notes_en', [])) if isinstance(data.get('notes_en'), list) else str(data.get('notes_en', '')),
                ' '.join(data.get('inclusions', [])) if isinstance(data.get('inclusions'), list) else str(data.get('inclusions', '')),
                ' '.join(data.get('exclusions', [])) if isinstance(data.get('exclusions'), list) else str(data.get('exclusions', '')),
            ]).lower()

            if not search_text.strip():
                continue

            # Count how many product tokens appear in chapter notes
            hits = sum(1 for t in tokens if t in search_text)
            if hits >= 1:
                # Chapter matched — create heading-level reference
                ch_padded = chapter.zfill(2)
                results.append({
                    'heading': ch_padded + '00',  # chapter-level placeholder
                    'chapter': ch_padded,
                    'hits': hits,
                    'total_tokens': len(tokens),
                    'desc_he': data.get('chapter_title_he', ''),
                    'desc_en': data.get('chapter_description_he', ''),
                    'source': 'chapter_notes',
                })
    except Exception as e:
        print(f'[identifier] chapter_notes error: {e}')

    # Sort by hit count descending
    results.sort(key=lambda r: r['hits'], reverse=True)
    return results[:10]


# ---------------------------------------------------------------------------
#  Source 4: Firestore tariff collection (description text search)
# ---------------------------------------------------------------------------

def _search_firestore_tariff(product, db):
    """Search Firestore tariff collection by description text."""
    results = []
    if db is None:
        return results

    tokens = _tokenize(product)
    if not tokens:
        return results

    try:
        # Strategy: query tariff docs that contain key tokens
        # Firestore doesn't support full-text search, so we fetch
        # a subset by chapter hint from tokens, or scan a limited set
        #
        # Optimization: use the first meaningful token in an array_contains
        # query if the collection has keyword arrays.  Otherwise, fall back
        # to the unified search index (in-memory).
        try:
            from lib._unified_search import find_tariff_codes
        except ImportError:
            from _unified_search import find_tariff_codes

        hits = find_tariff_codes(product, min_score=1)
        for h in hits[:20]:
            hs_raw = h.get('hs_raw', '')
            heading = _heading_from_code(hs_raw)
            if heading:
                results.append({
                    'heading': heading,
                    'fc': hs_raw,
                    'desc_he': h.get('description_he', ''),
                    'desc_en': h.get('description_en', ''),
                    'duty_rate': h.get('duty_rate', ''),
                    'purchase_tax': h.get('purchase_tax', ''),
                    'score': h.get('score', 0),
                    'weight': h.get('weight', 0),
                    'source': 'tariff_index',
                })
    except Exception as e:
        print(f'[identifier] tariff_index error: {e}')

    return results


# ---------------------------------------------------------------------------
#  Source 5: UK Trade Tariff API (free text search)
# ---------------------------------------------------------------------------

def _search_uk_tariff(product):
    """Search UK Trade Tariff by free text query."""
    results = []

    # Only send English text to UK API (Hebrew won't match)
    query = product
    if _is_hebrew(product):
        # Extract any English words from mixed text
        en_words = [w for w in _WORD_RE.split(product) if w and not re.search(r'[\u0590-\u05FF]', w) and len(w) > 2]
        if not en_words:
            return results  # Pure Hebrew — UK API won't help
        query = ' '.join(en_words)

    try:
        resp = requests.get(
            _UK_SEARCH_URL,
            params={'q': query},
            headers={'Accept': 'application/json'},
            timeout=_UK_TIMEOUT,
        )
        if resp.status_code != 200:
            return results

        data = resp.json()
        if not isinstance(data, dict):
            return results

        attrs = data.get('data', {}).get('attributes', {})
        match_type = attrs.get('type', '')

        if match_type == 'exact_match':
            # Exact match: single entry redirect — extract code from entry.id
            entry = attrs.get('entry', {})
            code = str(entry.get('id', ''))
            heading = _heading_from_code(code)
            # Skip UK-specific chapters 98/99 (end-use codes, not real HS)
            if heading and len(heading) == 4 and heading[:2] not in ('98', '99'):
                results.append({
                    'heading': heading,
                    'fc': code.ljust(10, '0')[:10],
                    'desc_en': f'UK exact match ({entry.get("endpoint", "")})',
                    'desc_he': '',
                    'source': 'uk_tariff',
                })

        elif match_type == 'fuzzy_match':
            # Fuzzy match: goods_nomenclature_match has chapters/headings/commodities
            gn_match = attrs.get('goods_nomenclature_match', {})
            # Collect from all three levels
            items = (gn_match.get('headings', []) +
                     gn_match.get('commodities', []) +
                     gn_match.get('chapters', []))
            for item in items[:20]:
                # Items have _source with the actual data
                src = item.get('_source', item)
                code = str(src.get('goods_nomenclature_item_id', ''))
                desc = src.get('description_indexed',
                               src.get('description', ''))
                heading = _heading_from_code(code)
                if heading and len(heading) == 4:
                    results.append({
                        'heading': heading,
                        'fc': code.ljust(10, '0')[:10],
                        'desc_en': re.sub(r'<[^>]+>', '', str(desc))[:200],
                        'desc_he': '',
                        'source': 'uk_tariff',
                    })

        else:
            # Legacy/unknown format — try old paths
            goods_results = attrs.get('goods_nomenclature_search_results',
                                      attrs.get('results', []))
            for gr in goods_results[:15]:
                gn = gr.get('goods_nomenclature', gr)
                gn_attrs = gn.get('attributes', gn)
                code = str(gn_attrs.get('goods_nomenclature_item_id', ''))
                desc = gn_attrs.get('description', '')
                heading = _heading_from_code(code)
                if heading and len(heading) == 4:
                    results.append({
                        'heading': heading,
                        'fc': code,
                        'desc_en': re.sub(r'<[^>]+>', '', str(desc)),
                        'desc_he': '',
                        'source': 'uk_tariff',
                    })
    except Exception as e:
        print(f'[identifier] uk_tariff error: {e}')

    return results


# ---------------------------------------------------------------------------
#  Source 6: Israeli English tariff (shaarolami — ground truth)
# ---------------------------------------------------------------------------

def _search_israeli_english_tariff(product):
    """
    Search the Israeli customs tariff English interface (shaarolami).

    More authoritative than UK tariff because it IS the Israeli tariff
    in English — same legal text, same codes, same chapter notes.
    Weighted 1.5x in convergence scoring.
    """
    results = []

    # Only send English text (Hebrew has its own sources via tree_he)
    query = product
    if _is_hebrew(product):
        en_words = [w for w in _WORD_RE.split(product)
                    if w and not re.search(r'[\u0590-\u05FF]', w) and len(w) > 2]
        if not en_words:
            return results
        query = ' '.join(en_words)

    try:
        resp = requests.get(
            _IL_EN_TARIFF_URL,
            params={'search': query},
            headers={
                'Accept': 'text/html, application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
            timeout=_IL_TIMEOUT,
        )
        if resp.status_code != 200:
            return results

        content_type = resp.headers.get('Content-Type', '')
        body = resp.text

        if 'json' in content_type:
            # JSON response — parse structured data
            data = resp.json()
            items = data if isinstance(data, list) else data.get('results', data.get('items', []))
            for item in (items if isinstance(items, list) else []):
                code = str(item.get('CustomsTaarifCode', item.get('code', item.get('hs_code', ''))))
                desc = item.get('EnglishDescription', item.get('description', ''))
                heading = _heading_from_code(code)
                if heading and len(heading) == 4:
                    results.append({
                        'heading': heading,
                        'fc': re.sub(r'[^0-9]', '', code).ljust(10, '0')[:10],
                        'desc_en': str(desc).strip(),
                        'desc_he': str(item.get('HebrewDescription', '')).strip(),
                        'source': 'il_en_tariff',
                        'level': 5,
                    })
        else:
            # HTML response — extract tariff codes from table rows
            # Pattern: 10-digit codes with English descriptions
            code_pattern = re.compile(
                r'(\d{2})\.?(\d{2})\.?(\d{2,6})'  # HS code groups
            )
            # Look for table rows with HS codes and descriptions
            row_pattern = re.compile(
                r'<tr[^>]*>.*?'
                r'(\d{4}[\.\s]?\d{2}[\.\s]?\d{2,6}[\./]?\d?)'  # HS code
                r'.*?<td[^>]*>(.*?)</td>'  # description
                r'.*?</tr>',
                re.DOTALL | re.IGNORECASE,
            )
            for match in row_pattern.finditer(body):
                code_raw = match.group(1)
                desc_raw = match.group(2)
                code_digits = re.sub(r'[^0-9]', '', code_raw)
                heading = _heading_from_code(code_digits)
                if heading and len(heading) == 4:
                    desc_clean = re.sub(r'<[^>]+>', '', desc_raw).strip()
                    if desc_clean:
                        results.append({
                            'heading': heading,
                            'fc': code_digits.ljust(10, '0')[:10],
                            'desc_en': desc_clean,
                            'desc_he': '',
                            'source': 'il_en_tariff',
                            'level': 5,
                        })

    except Exception as e:
        print(f'[identifier] il_en_tariff error: {e}')

    return results[:15]


# ---------------------------------------------------------------------------
#  Convergence: merge results by 4-digit heading
# ---------------------------------------------------------------------------

_CONFIDENCE_HIGH = 'HIGH'
_CONFIDENCE_MEDIUM = 'MEDIUM'
_CONFIDENCE_LOW = 'LOW'


def _converge(all_results):
    """
    Merge results from all 6 sources by 4-digit heading.

    Scoring:
      3+ sources agree                   ->HIGH
      2 sources agree                    ->MEDIUM
      1 source                           ->LOW
      Israeli EN + Hebrew agree (any 2)  ->automatic HIGH (ground truth)

    Source weights (_SOURCE_WEIGHTS):
      il_en_tariff = 1.5x (Israeli English = same legal text, authoritative)
      All others   = 1.0x
    """
    # Aggregate by heading
    headings = {}  # heading -> {sources, best_fc, desc_he, desc_en, ...}

    for result in all_results:
        heading = result.get('heading', '')
        if not heading or len(heading) < 2:
            continue

        # Normalize: for chapter_notes results, heading is like '9400'
        # For tree/tariff results, heading is the real 4 digits
        h4 = heading[:4].ljust(4, '0')
        source = result.get('source', '')

        if h4 not in headings:
            headings[h4] = {
                'sources': set(),
                'best_fc': '',
                'best_level': 0,
                'desc_he': '',
                'desc_en': '',
                'duty_rate': '',
                'chapter': h4[:2],
                'score_sum': 0,
                'weight_sum': 0,
                'weighted_source_count': 0.0,
                'hit_count': 0,
            }

        entry = headings[h4]
        entry['sources'].add(source)
        entry['hit_count'] += 1
        entry['score_sum'] += result.get('score', 1)
        entry['weight_sum'] += result.get('weight', 1)
        entry['weighted_source_count'] += _SOURCE_WEIGHTS.get(source, 1.0)

        # Keep the most specific (deepest level) FC code
        level = result.get('level', 5)
        fc = result.get('fc', '')
        if level > entry['best_level'] and fc:
            entry['best_fc'] = fc
            entry['best_level'] = level

        # Fill descriptions
        if result.get('desc_he') and not entry['desc_he']:
            entry['desc_he'] = result['desc_he']
        if result.get('desc_en') and not entry['desc_en']:
            entry['desc_en'] = result['desc_en']
        if result.get('duty_rate') and not entry['duty_rate']:
            entry['duty_rate'] = result['duty_rate']

    # Build candidates with confidence levels
    candidates = []
    for h4, info in headings.items():
        sources = info['sources']
        n_sources = len(sources)
        weighted = info['weighted_source_count']

        # Special rule: Israeli EN + any Hebrew source agree ->automatic HIGH
        # This is ground truth — the Israeli tariff in English matches the Hebrew
        il_en_and_hebrew = ('il_en_tariff' in sources and
                            bool(sources & {'tree_he', 'tariff_index'}))

        if il_en_and_hebrew or n_sources >= 3:
            confidence = _CONFIDENCE_HIGH
            conf_score = 80.0 + min(n_sources - 2, 3) * 5
        elif n_sources == 2:
            confidence = _CONFIDENCE_MEDIUM
            conf_score = 55.0
        else:
            confidence = _CONFIDENCE_LOW
            conf_score = 30.0

        # Boost score by hit count, weight, and source weighting
        conf_score += min(info['hit_count'] * 2, 10)
        conf_score += min(info['weight_sum'] * 0.5, 5)
        # Extra boost for weighted sources (il_en_tariff = 1.5x)
        weighted_bonus = (weighted - n_sources) * 10  # 0.5 extra per il_en_tariff hit
        conf_score += max(weighted_bonus, 0)
        conf_score = min(conf_score, 99.0)

        hs_code = info['best_fc'] if info['best_fc'] else h4.ljust(10, '0')

        cand = make_candidate(
            hs_code=hs_code,
            confidence=round(conf_score, 1),
            sources=sorted(info['sources']),
            desc_he=info['desc_he'],
            desc_en=info['desc_en'],
            chapter=info['chapter'],
            duty_rate=info['duty_rate'],
        )
        cand['confidence_level'] = confidence
        cand['source_count'] = n_sources
        cand['weighted_source_count'] = round(weighted, 1)
        cand['hit_count'] = info['hit_count']
        cand['il_en_hebrew_agree'] = il_en_and_hebrew
        cand['needs_web_search'] = (n_sources == 1)
        cand['needs_gir_analysis'] = False
        candidates.append(cand)

    # Flag conflicting sources
    if len(candidates) > 1:
        # If top 2 candidates are from different single sources, flag GIR
        top2 = sorted(candidates, key=lambda c: c['confidence'], reverse=True)[:2]
        if top2[0]['source_count'] == 1 and top2[1]['source_count'] == 1:
            for c in top2:
                c['needs_gir_analysis'] = True

    # Sort by confidence descending
    candidates.sort(key=lambda c: c['confidence'], reverse=True)
    return candidates[:_MAX_RESULTS]


# ---------------------------------------------------------------------------
#  Main entry point
# ---------------------------------------------------------------------------

def identify_product(product, db=None, skip_uk=False, skip_il_en=False):
    """
    Parallel product identification from 6 sources.

    Args:
        product:    raw product string (Hebrew or English)
        db:         Firestore client (optional — Sources 3,4 need it)
        skip_uk:    if True, skip UK API call (for testing or rate limits)
        skip_il_en: if True, skip Israeli English tariff call

    Returns:
        list of HSCandidate dicts, sorted by confidence descending.
        Each candidate has extra fields:
          confidence_level:     'HIGH' / 'MEDIUM' / 'LOW'
          source_count:         how many of the 6 sources agreed
          weighted_source_count: source count with il_en_tariff at 1.5x
          sources:              list of source names that contributed
          il_en_hebrew_agree:   True if Israeli EN + Hebrew both found this heading
          needs_web_search:     True if only 1 source (LOW confidence)
          needs_gir_analysis:   True if conflicting sources
    """
    if not product or not product.strip():
        return []

    product = product.strip()
    t0 = time.monotonic()
    product_preview = product[:80] + ('...' if len(product) > 80 else '')
    logger.info('[identifier] START product=%r', product_preview)

    # Load tariff_tree search function (lazy)
    tree_search_func = None
    try:
        from lib.tariff_tree import search_tree
        tree_search_func = lambda q: search_tree(q, db=None)
    except ImportError:
        try:
            from tariff_tree import search_tree
            tree_search_func = lambda q: search_tree(q, db=None)
        except ImportError:
            logger.info('[identifier] tariff_tree not available — sources 1,2 skipped')

    # Prepare search tasks
    all_results = []
    futures = {}
    source_timings = {}  # name -> {ms, count, status}

    # Track which sources are skipped
    _all_source_names = ['tree_he', 'tree_en', 'chapter_notes',
                         'tariff_index', 'uk_tariff', 'il_en_tariff']

    with ThreadPoolExecutor(max_workers=6) as executor:
        # Source 1: tree Hebrew search
        if tree_search_func:
            futures['tree_he'] = (executor.submit(
                _search_tree_hebrew, product, tree_search_func), time.monotonic())
        else:
            source_timings['tree_he'] = {'ms': 0, 'count': 0, 'status': 'skipped'}

        # Source 2: tree English search
        if tree_search_func:
            futures['tree_en'] = (executor.submit(
                _search_tree_english, product, tree_search_func), time.monotonic())
        else:
            source_timings['tree_en'] = {'ms': 0, 'count': 0, 'status': 'skipped'}

        # Source 3: chapter_notes
        if db is not None:
            futures['chapter_notes'] = (executor.submit(
                _search_chapter_notes, product, db), time.monotonic())
        else:
            source_timings['chapter_notes'] = {'ms': 0, 'count': 0, 'status': 'skipped_no_db'}

        # Source 4: tariff index (unified search)
        futures['tariff_index'] = (executor.submit(
            _search_firestore_tariff, product, db), time.monotonic())

        # Source 5: UK tariff API
        if not skip_uk and not _is_hebrew(product):
            futures['uk_tariff'] = (executor.submit(
                _search_uk_tariff, product), time.monotonic())
        elif not skip_uk:
            en_words = [w for w in _WORD_RE.split(product)
                        if w and not re.search(r'[\u0590-\u05FF]', w) and len(w) > 2]
            if en_words:
                futures['uk_tariff'] = (executor.submit(
                    _search_uk_tariff, product), time.monotonic())
            else:
                source_timings['uk_tariff'] = {'ms': 0, 'count': 0, 'status': 'skipped_no_english'}
        else:
            source_timings['uk_tariff'] = {'ms': 0, 'count': 0, 'status': 'skipped'}

        # Source 6: Israeli English tariff (shaarolami — ground truth)
        if not skip_il_en and not _is_hebrew(product):
            futures['il_en_tariff'] = (executor.submit(
                _search_israeli_english_tariff, product), time.monotonic())
        elif not skip_il_en:
            en_words = [w for w in _WORD_RE.split(product)
                        if w and not re.search(r'[\u0590-\u05FF]', w) and len(w) > 2]
            if en_words:
                futures['il_en_tariff'] = (executor.submit(
                    _search_israeli_english_tariff, product), time.monotonic())
            else:
                source_timings['il_en_tariff'] = {'ms': 0, 'count': 0, 'status': 'skipped_no_english'}
        else:
            source_timings['il_en_tariff'] = {'ms': 0, 'count': 0, 'status': 'skipped'}

        # Collect results with per-source timing
        for name, (future, submit_time) in futures.items():
            try:
                result = future.result(timeout=15)
                elapsed_ms = int((time.monotonic() - submit_time) * 1000)
                count = len(result) if result else 0
                source_timings[name] = {'ms': elapsed_ms, 'count': count, 'status': 'ok'}
                if result:
                    all_results.extend(result)
                logger.info('[identifier]   %-16s -> %d results in %dms',
                            name, count, elapsed_ms)
            except TimeoutError:
                elapsed_ms = int((time.monotonic() - submit_time) * 1000)
                source_timings[name] = {'ms': elapsed_ms, 'count': 0, 'status': 'timeout'}
                logger.warning('[identifier]   %-16s ->TIMEOUT after %dms',
                               name, elapsed_ms)
            except Exception as e:
                elapsed_ms = int((time.monotonic() - submit_time) * 1000)
                source_timings[name] = {'ms': elapsed_ms, 'count': 0, 'status': f'error: {e}'}
                logger.warning('[identifier]   %-16s ->ERROR in %dms: %s',
                               name, elapsed_ms, e)

    # Log skipped sources
    for name in _all_source_names:
        if name in source_timings and source_timings[name]['status'].startswith('skipped'):
            logger.info('[identifier]   %-16s -> %s', name, source_timings[name]['status'])

    # Converge all results by 4-digit heading
    candidates = _converge(all_results)

    # Summary log
    total_ms = int((time.monotonic() - t0) * 1000)
    sources_ok = sum(1 for s in source_timings.values() if s['status'] == 'ok')
    sources_with_results = sum(1 for s in source_timings.values() if s['count'] > 0)
    total_raw = sum(s['count'] for s in source_timings.values())
    top_heading = candidates[0]['heading'] if candidates else 'none'
    top_conf = candidates[0]['confidence_level'] if candidates else 'none'
    top_n_src = candidates[0]['source_count'] if candidates else 0

    logger.info(
        '[identifier] DONE in %dms | %d/%d sources returned data | '
        '%d raw -> %d candidates | top=%s (%s, %d sources)',
        total_ms, sources_with_results, sources_ok, total_raw,
        len(candidates), top_heading, top_conf, top_n_src,
    )

    return candidates
