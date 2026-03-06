#!/usr/bin/env python3
"""Build unified tariff index — reads EVERY document in the system.

Three passes:
  Pass 0: Python data modules (instant, no I/O)
  Pass 1: Firestore collections (tariff, chapter_notes, directives, FIO)
  Pass 2: Cross-reference Hebrew<->English synonyms

Output: functions/lib/_unified_index.py
  - WORD_INDEX: dict[str, list[IndexEntry]]
  - HEADING_MAP: dict[str, list[str]]  (4-digit heading -> all 10-digit sub-codes)
  - HS_META: dict[str, dict]  (10-digit HS -> description, duty, purchase_tax)

Usage:
  # With Firestore (full build):
  python build_unified_index.py

  # Without Firestore (Pass 0 only, for testing):
  python build_unified_index.py --no-firestore

  # In Cloud Functions:
  from build_unified_index import build_index
  build_index(db)  # writes _unified_index.py
"""

import os
import re
import sys
import json
import time
import hashlib
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Any, Optional

# ---------------------------------------------------------------------------
#  Add functions/ to path so we can import lib.*
# ---------------------------------------------------------------------------
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)


# ---------------------------------------------------------------------------
#  Hebrew text processing
# ---------------------------------------------------------------------------
_HE_PREFIXES = ("ו", "ה", "ב", "ל", "כ", "מ", "ש")
_HE_COMPOUND_PREFIXES = ("וה", "של", "מה", "לה", "בה", "כש", "שב", "שה", "שמ", "של")
_STOP_WORDS_HE = frozenset({
    "את", "של", "על", "עם", "או", "גם", "כי", "אם", "לא", "יש", "זה",
    "אל", "הם", "הוא", "היא", "בין", "כל", "מן", "אשר", "עד", "רק",
    "זו", "אלה", "אלו", "כן", "הנ", "אין", "להם", "אך", "גם", "עוד",
    "לפי", "ידי", "תוך", "ללא", "כגון", "דהיינו", "לרבות", "למעט",
    "כולל", "פרט", "סעיף", "חלק", "פרק",
})
_STOP_WORDS_EN = frozenset({
    "the", "a", "an", "of", "for", "and", "or", "with", "to", "from",
    "in", "on", "by", "is", "are", "was", "were", "be", "been", "new",
    "used", "set", "pcs", "piece", "pieces", "item", "items", "type",
    "other", "others", "not", "including", "excluding", "whether",
    "than", "such", "but", "has", "have", "had", "its", "that", "this",
    "those", "these", "which", "who", "whom", "being", "into", "over",
    "under", "between", "through", "during", "before", "after",
})
_STOP_WORDS = _STOP_WORDS_HE | _STOP_WORDS_EN

# Hebrew synonyms: word -> list of synonyms (bidirectional)
_HE_EN_SYNONYMS = {
    # Common tariff terms
    "רחפן": ["drone", "uav", "quadcopter", "multicopter", "unmanned"],
    "drone": ["רחפן", "כטמב", "כלי טיס"],
    "uav": ["רחפן", "drone", "כטמב"],
    "מכונית": ["car", "automobile", "vehicle", "רכב"],
    "רכב": ["vehicle", "car", "מכונית"],
    "צמיג": ["tire", "tyre", "pneumatic"],
    "tire": ["צמיג", "tyre"],
    "tyre": ["צמיג", "tire"],
    "פלדה": ["steel", "iron"],
    "steel": ["פלדה", "ברזל"],
    "ברזל": ["iron", "steel", "פלדה"],
    "iron": ["ברזל", "פלדה"],
    "גומי": ["rubber", "caoutchouc"],
    "rubber": ["גומי"],
    "פלסטיק": ["plastic", "polymer"],
    "plastic": ["פלסטיק"],
    "עץ": ["wood", "timber"],
    "wood": ["עץ"],
    "נייר": ["paper", "cardboard"],
    "paper": ["נייר"],
    "בד": ["fabric", "textile", "cloth"],
    "textile": ["בד", "טקסטיל", "אריג"],
    "זכוכית": ["glass"],
    "glass": ["זכוכית"],
    "אלומיניום": ["aluminum", "aluminium"],
    "aluminum": ["אלומיניום"],
    "נחושת": ["copper"],
    "copper": ["נחושת"],
    "סוללה": ["battery", "accumulator", "cell"],
    "battery": ["סוללה", "מצבר"],
    "מנוע": ["motor", "engine"],
    "motor": ["מנוע"],
    "engine": ["מנוע"],
    "משאבה": ["pump"],
    "pump": ["משאבה"],
    "מחשב": ["computer"],
    "computer": ["מחשב"],
    "טלפון": ["phone", "telephone"],
    "phone": ["טלפון"],
    "מצלמה": ["camera"],
    "camera": ["מצלמה"],
    "תרופה": ["medicine", "drug", "pharmaceutical"],
    "medicine": ["תרופה", "רפואה"],
    "כימיקל": ["chemical"],
    "chemical": ["כימיקל", "חומר כימי"],
    "דשן": ["fertilizer"],
    "fertilizer": ["דשן"],
    "צבע": ["paint", "dye", "color"],
    "paint": ["צבע"],
    "סבון": ["soap", "detergent"],
    "soap": ["סבון"],
    "ריהוט": ["furniture"],
    "furniture": ["ריהוט", "רהיט"],
    "צעצוע": ["toy"],
    "toy": ["צעצוע"],
    "נעל": ["shoe", "footwear"],
    "shoe": ["נעל", "נעליים"],
    "בגד": ["garment", "clothing", "apparel"],
    "clothing": ["בגד", "לבוש", "ביגוד"],
}


def _tokenize(text: str) -> List[str]:
    """Split text into searchable tokens. Strips Hebrew prefixes."""
    if not text:
        return []
    words = re.split(r'[^\w\u0590-\u05FF]+', text.lower())
    tokens = []
    for w in words:
        if len(w) < 2 or w in _STOP_WORDS:
            continue
        tokens.append(w)
        # Also add prefix-stripped version for Hebrew
        if len(w) > 3:
            for pfx in _HE_COMPOUND_PREFIXES:
                if w.startswith(pfx) and len(w) - len(pfx) >= 2:
                    tokens.append(w[len(pfx):])
                    break
            else:
                for pfx in _HE_PREFIXES:
                    if w.startswith(pfx) and len(w) - len(pfx) >= 2:
                        tokens.append(w[len(pfx):])
                        break
    return tokens


def _dedup_tokens(tokens: List[str]) -> List[str]:
    seen = set()
    result = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


# ---------------------------------------------------------------------------
#  Index entry format
# ---------------------------------------------------------------------------
# Each entry in WORD_INDEX[word] is a tuple:
#   (hs_code: str, source: str, weight: int)
#
# source codes:
#   T  = tariff collection (hs_code + description)
#   CN = chapter_notes (exclusion/inclusion/preamble)
#   CD = classification_directives
#   FI = free_import_order
#   CH = chapter_expertise (section/chapter names)
#   DC = discount_codes
#   C98 = chapter 98/99
#   FTA = FTA agreement text
#   ORD = ordinance article
#   FW = framework order
#   PR = procedure
#   EU = EU reform
#   CAL = customs agents law

def _add_to_index(word_index: Dict[str, List], hs_code: str, source: str,
                  weight: int, tokens: List[str]):
    """Add tokens to the word index."""
    entry = (hs_code, source, weight)
    for token in _dedup_tokens(tokens):
        if len(token) >= 2:
            word_index[token].append(entry)


# ---------------------------------------------------------------------------
#  Pass 0: Python data modules (instant, no I/O)
# ---------------------------------------------------------------------------

def _pass0_python_modules(word_index, heading_map, hs_meta):
    """Read all Python-embedded data modules."""
    t0 = time.time()
    count = 0

    # --- Chapter expertise (section/chapter names) ---
    try:
        from lib.chapter_expertise import SEED_EXPERTISE
        for section_num, section_data in SEED_EXPERTISE.items():
            name_en = section_data.get("name_en", "")
            name_he = section_data.get("name_he", "")
            notes = section_data.get("notes", "")
            chapters = section_data.get("chapters", [])
            tokens = _tokenize(f"{name_en} {name_he} {notes}")
            for ch in chapters:
                ch_str = str(ch).zfill(2)
                _add_to_index(word_index, ch_str, "CH", 3, tokens)
                count += 1
    except Exception as e:
        print(f"  Pass 0 chapter_expertise error: {e}")

    # --- Discount codes ---
    try:
        from lib._discount_codes_data import DISCOUNT_CODES
        for item_num, item_data in DISCOUNT_CODES.items():
            desc = item_data.get("description_he", "")
            tokens = _tokenize(desc)
            for sc_code, sc_data in item_data.get("sub_codes", {}).items():
                sc_desc = sc_data.get("description_he", "")
                sc_tokens = _tokenize(sc_desc)
                for hs in sc_data.get("hs_codes", []):
                    _add_to_index(word_index, hs, "DC", 4, tokens + sc_tokens)
                    count += 1
                # Index the discount code itself
                dc_key = f"DC:{item_num}/{sc_code}"
                _add_to_index(word_index, dc_key, "DC", 2, sc_tokens)
                count += 1
    except Exception as e:
        print(f"  Pass 0 discount_codes error: {e}")

    # --- Chapter 98/99 ---
    try:
        from lib._chapter98_data import CHAPTER_98_HEADINGS, CHAPTER_99_HEADINGS
        for headings_dict in [CHAPTER_98_HEADINGS, CHAPTER_99_HEADINGS]:
            for code, data in headings_dict.items():
                desc_he = data.get("heading_he", "")
                desc_en = data.get("heading_en", "")
                tokens = _tokenize(f"{desc_he} {desc_en}")
                _add_to_index(word_index, str(code), "C98", 3, tokens)
                count += 1
                for sub_code, sub_data in data.get("sub_items", {}).items():
                    sub_he = sub_data.get("description_he", "")
                    sub_en = sub_data.get("description_en", "")
                    sub_tokens = _tokenize(f"{sub_he} {sub_en}")
                    full_code = str(sub_code)
                    _add_to_index(word_index, full_code, "C98", 4, tokens + sub_tokens)
                    count += 1
    except Exception as e:
        print(f"  Pass 0 chapter98 error: {e}")

    # --- Ordinance articles ---
    try:
        from lib._ordinance_data import ORDINANCE_ARTICLES
        for art_id, art_data in ORDINANCE_ARTICLES.items():
            title = art_data.get("t", "")
            summary = art_data.get("s", "")
            full_text = art_data.get("f", "")[:500]  # First 500 chars
            tokens = _tokenize(f"{title} {summary} {full_text}")
            _add_to_index(word_index, f"ORD:{art_id}", "ORD", 2, tokens)
            count += 1
    except Exception as e:
        print(f"  Pass 0 ordinance error: {e}")

    # --- Framework order ---
    try:
        from lib._framework_order_data import FRAMEWORK_ORDER_ARTICLES
        for art_id, art_data in FRAMEWORK_ORDER_ARTICLES.items():
            title = art_data.get("t", "")
            summary = art_data.get("s", "")
            full_text = art_data.get("f", "")[:500]
            tokens = _tokenize(f"{title} {summary} {full_text}")
            _add_to_index(word_index, f"FW:{art_id}", "FW", 2, tokens)
            count += 1
    except Exception as e:
        print(f"  Pass 0 framework_order error: {e}")

    # --- Customs agents law ---
    try:
        from lib._customs_agents_law import CUSTOMS_AGENTS_ARTICLES
        for art_id, art_data in CUSTOMS_AGENTS_ARTICLES.items():
            title = art_data.get("t", "")
            summary = art_data.get("s", "")
            full_text = art_data.get("f", "")[:500]
            tokens = _tokenize(f"{title} {summary} {full_text}")
            _add_to_index(word_index, f"CAL:{art_id}", "CAL", 2, tokens)
            count += 1
    except Exception as e:
        print(f"  Pass 0 customs_agents_law error: {e}")

    # --- Procedures ---
    try:
        from lib._procedures_data import PROCEDURES
        for proc_id, proc_data in PROCEDURES.items():
            title = proc_data.get("title_he", proc_data.get("title", ""))
            full_text = proc_data.get("full_text", "")[:1000]
            tokens = _tokenize(f"{title} {full_text}")
            _add_to_index(word_index, f"PR:{proc_id}", "PR", 2, tokens)
            count += 1
    except Exception as e:
        print(f"  Pass 0 procedures error: {e}")

    # --- EU Reform ---
    try:
        from lib._eu_reform_data import EU_REFORM_DOCS
        for doc_id, doc_data in EU_REFORM_DOCS.items():
            title = doc_data.get("title_he", "")
            full_text = doc_data.get("full_text", "")[:1000]
            tokens = _tokenize(f"{title} {full_text}")
            _add_to_index(word_index, f"EU:{doc_id}", "EU", 2, tokens)
            count += 1
    except Exception as e:
        print(f"  Pass 0 eu_reform error: {e}")

    # --- FTA (just key articles + country names, NOT full text) ---
    try:
        from lib._fta_all_countries import FTA_COUNTRIES
        for country_code, country_data in FTA_COUNTRIES.items():
            name_he = country_data.get("name_he", "")
            name_en = country_data.get("name_en", "")
            agreement = country_data.get("agreement_name_he", "")
            tokens = _tokenize(f"{name_he} {name_en} {agreement}")
            _add_to_index(word_index, f"FTA:{country_code}", "FTA", 2, tokens)
            count += 1
            # Key articles (dict of art_type -> {title, ...})
            key_arts = country_data.get("key_articles", {})
            if isinstance(key_arts, dict):
                for art_type, art_data in key_arts.items():
                    if isinstance(art_data, dict):
                        art_title = art_data.get("title", "")
                    elif isinstance(art_data, str):
                        art_title = art_data
                    else:
                        continue
                    art_tokens = _tokenize(f"{art_type} {art_title}")
                    _add_to_index(word_index, f"FTA:{country_code}", "FTA", 3, art_tokens)
    except Exception as e:
        print(f"  Pass 0 fta error: {e}")

    elapsed = time.time() - t0
    print(f"  Pass 0 complete: {count} entries from Python modules ({elapsed:.2f}s)")
    return count


# ---------------------------------------------------------------------------
#  Pass 1: Firestore collections
# ---------------------------------------------------------------------------

def _pass1_firestore(db, word_index, heading_map, hs_meta):
    """Read tariff, chapter_notes, directives, FIO from Firestore."""
    if db is None:
        print("  Pass 1 skipped: no Firestore client")
        return 0

    t0 = time.time()
    count = 0

    # --- Tariff collection (THE BIG ONE: ~11,753 docs) ---
    print("  Pass 1a: Reading tariff collection...")
    try:
        docs = db.collection("tariff").stream()
        for doc in docs:
            data = doc.to_dict()
            hs_code = doc.id
            if data.get("corrupt_code"):
                continue

            desc_he = data.get("description_he", data.get("description", ""))
            desc_en = data.get("description_en", "")
            duty_rate = data.get("duty_rate", "")
            purchase_tax = data.get("purchase_tax", "")

            # Store metadata
            hs_meta[hs_code] = {
                "he": desc_he,
                "en": desc_en,
                "duty": duty_rate,
                "pt": purchase_tax,
            }

            # Build heading map (4-digit -> all 10-digit codes)
            hs_clean = hs_code.replace(".", "").replace("/", "").replace(" ", "")
            if len(hs_clean) >= 4:
                heading = hs_clean[:4]
                if heading not in heading_map:
                    heading_map[heading] = []
                heading_map[heading].append(hs_code)

            # Index words
            tokens = _tokenize(f"{desc_he} {desc_en}")
            _add_to_index(word_index, hs_code, "T", 5, tokens)
            count += 1

            if count % 2000 == 0:
                print(f"    ...{count} tariff docs indexed")
    except Exception as e:
        print(f"  Pass 1a tariff error: {e}")
    print(f"  Pass 1a: {count} tariff entries indexed")

    # --- Chapter notes (~94 docs) ---
    cn_count = 0
    print("  Pass 1b: Reading chapter_notes...")
    try:
        docs = db.collection("chapter_notes").stream()
        for doc in docs:
            data = doc.to_dict()
            chapter = doc.id.replace("chapter_", "").zfill(2)
            preamble = data.get("preamble_he", data.get("preamble", ""))
            notes = data.get("notes_he", data.get("notes", ""))
            exclusions = data.get("exclusions", "")
            inclusions = data.get("inclusions", "")
            if isinstance(exclusions, list):
                exclusions = " ".join(exclusions)
            if isinstance(inclusions, list):
                inclusions = " ".join(inclusions)

            text = f"{preamble} {notes} {exclusions} {inclusions}"
            tokens = _tokenize(text)
            _add_to_index(word_index, chapter, "CN", 4, tokens)
            cn_count += 1
    except Exception as e:
        print(f"  Pass 1b chapter_notes error: {e}")
    print(f"  Pass 1b: {cn_count} chapter_notes indexed")
    count += cn_count

    # --- Classification directives (~218 docs) ---
    cd_count = 0
    print("  Pass 1c: Reading classification_directives...")
    try:
        docs = db.collection("classification_directives").stream()
        for doc in docs:
            data = doc.to_dict()
            title = data.get("title", "")
            content = data.get("content", "")[:500]
            hs_codes = data.get("primary_hs_code", "")
            related = data.get("related_hs_codes", [])
            if isinstance(related, list):
                related = " ".join(str(r) for r in related)

            tokens = _tokenize(f"{title} {content}")
            if hs_codes:
                _add_to_index(word_index, str(hs_codes), "CD", 5, tokens)
            for r_hs in (related.split() if isinstance(related, str) else []):
                _add_to_index(word_index, r_hs, "CD", 3, tokens)
            cd_count += 1
    except Exception as e:
        print(f"  Pass 1c directives error: {e}")
    print(f"  Pass 1c: {cd_count} directives indexed")
    count += cd_count

    # --- Free Import Order (~6,121 docs) ---
    fio_count = 0
    print("  Pass 1d: Reading free_import_order...")
    try:
        docs = db.collection("free_import_order").stream()
        for doc in docs:
            if doc.id == "_metadata":
                continue
            data = doc.to_dict()
            hs_code = data.get("hs_10", data.get("hs_code", doc.id))
            authorities = data.get("authorities_summary", "")
            if isinstance(authorities, list):
                authorities = " ".join(str(a) for a in authorities)
            conditions = data.get("conditions_type", "")
            appendices = data.get("appendices", "")
            if isinstance(appendices, list):
                appendices = " ".join(str(a) for a in appendices)

            tokens = _tokenize(f"{authorities} {conditions} {appendices}")
            _add_to_index(word_index, str(hs_code), "FI", 2, tokens)
            fio_count += 1

            if fio_count % 1000 == 0:
                print(f"    ...{fio_count} FIO docs indexed")
    except Exception as e:
        print(f"  Pass 1d FIO error: {e}")
    print(f"  Pass 1d: {fio_count} FIO entries indexed")
    count += fio_count

    elapsed = time.time() - t0
    print(f"  Pass 1 complete: {count} entries from Firestore ({elapsed:.2f}s)")
    return count


# ---------------------------------------------------------------------------
#  Pass 2: Cross-reference Hebrew<->English synonyms
# ---------------------------------------------------------------------------

def _pass2_synonyms(word_index):
    """Expand index with Hebrew<->English synonym mappings."""
    t0 = time.time()
    additions = 0

    for word, synonyms in _HE_EN_SYNONYMS.items():
        if word not in word_index:
            continue
        entries = word_index[word]
        for syn in synonyms:
            syn_lower = syn.lower()
            if syn_lower not in word_index:
                word_index[syn_lower] = []
            # Add cross-references (with lower weight)
            existing_codes = {(e[0], e[1]) for e in word_index[syn_lower]}
            for entry in entries:
                key = (entry[0], entry[1])
                if key not in existing_codes:
                    word_index[syn_lower].append((entry[0], entry[1], max(1, entry[2] - 1)))
                    additions += 1

    elapsed = time.time() - t0
    print(f"  Pass 2 complete: {additions} synonym cross-references ({elapsed:.2f}s)")
    return additions


# ---------------------------------------------------------------------------
#  Compact + write output file
# ---------------------------------------------------------------------------

def _compact_index(word_index):
    """Deduplicate and sort entries per word. Keep top 20 per word."""
    for word in list(word_index.keys()):
        entries = word_index[word]
        # Dedup by (hs_code, source), keep highest weight
        best = {}
        for hs, src, wt in entries:
            key = (hs, src)
            if key not in best or wt > best[key]:
                best[key] = wt
        # Sort by weight descending, keep top 20
        sorted_entries = sorted(best.items(), key=lambda x: -x[1])[:20]
        word_index[word] = [(k[0], k[1], v) for k, v in sorted_entries]
        # Drop words with only 1 low-weight entry
        if len(word_index[word]) == 1 and word_index[word][0][2] <= 1:
            if len(word) <= 3:
                del word_index[word]


def _write_output(word_index, heading_map, hs_meta, output_path):
    """Write the generated _unified_index.py file."""
    t0 = time.time()

    lines = []
    lines.append('"""Unified tariff index — auto-generated by build_unified_index.py.')
    lines.append('')
    lines.append('DO NOT EDIT MANUALLY. Re-run build_unified_index.py to regenerate.')
    lines.append('')
    lines.append(f'Generated: {datetime.now().isoformat()}')
    lines.append(f'Words indexed: {len(word_index)}')
    lines.append(f'HS codes: {len(hs_meta)}')
    lines.append(f'Headings: {len(heading_map)}')
    lines.append('"""')
    lines.append('')
    lines.append('from typing import Dict, List, Tuple, Optional')
    lines.append('')
    lines.append('')

    # --- WORD_INDEX ---
    lines.append('# word -> [(hs_code, source, weight), ...]')
    lines.append(f'WORD_INDEX: Dict[str, List[Tuple[str, str, int]]] = {{')
    for word in sorted(word_index.keys()):
        entries = word_index[word]
        entries_str = repr(entries)
        lines.append(f'  {word!r}: {entries_str},')
    lines.append('}')
    lines.append('')

    # --- HEADING_MAP ---
    lines.append('# 4-digit heading -> list of full HS codes under it')
    lines.append(f'HEADING_MAP: Dict[str, List[str]] = {{')
    for heading in sorted(heading_map.keys()):
        codes = sorted(heading_map[heading])
        lines.append(f'  {heading!r}: {codes!r},')
    lines.append('}')
    lines.append('')

    # --- HS_META ---
    lines.append('# full HS code -> {he, en, duty, pt}')
    lines.append(f'HS_META: Dict[str, dict] = {{')
    for hs in sorted(hs_meta.keys()):
        meta = hs_meta[hs]
        lines.append(f'  {hs!r}: {meta!r},')
    lines.append('}')
    lines.append('')

    # --- Search functions ---
    # Read the search functions from the template file
    search_path = os.path.join(os.path.dirname(output_path), "_unified_search.py")
    lines.append('')
    lines.append('# Search functions are in _unified_search.py (imported at bottom)')
    lines.append('# Import them into this module namespace for convenience')
    lines.append('try:')
    lines.append('    from lib._unified_search import search_word, search_phrase, find_tariff_codes, get_heading_subcodes')
    lines.append('except ImportError:')
    lines.append('    from _unified_search import search_word, search_phrase, find_tariff_codes, get_heading_subcodes')

    content = '\n'.join(lines)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    elapsed = time.time() - t0
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Output written: {output_path} ({size_mb:.1f} MB, {elapsed:.2f}s)")




# ---------------------------------------------------------------------------
#  Main build function
# ---------------------------------------------------------------------------

from datetime import datetime


def build_index(db=None, output_path=None):
    """Build the unified index.

    Args:
        db: Firestore client (None to skip Pass 1)
        output_path: where to write _unified_index.py (default: lib/_unified_index.py)
    """
    if output_path is None:
        output_path = os.path.join(_script_dir, "lib", "_unified_index.py")

    print("=" * 60)
    print("Building unified tariff index")
    print("=" * 60)

    word_index = defaultdict(list)  # word -> [(hs_code, source, weight)]
    heading_map = {}                # 4-digit heading -> [full hs codes]
    hs_meta = {}                    # full hs code -> {he, en, duty, pt}

    t_total = time.time()

    # Pass 0: Python modules
    print("\n--- Pass 0: Python data modules ---")
    p0 = _pass0_python_modules(word_index, heading_map, hs_meta)

    # Pass 1: Firestore
    print("\n--- Pass 1: Firestore collections ---")
    p1 = _pass1_firestore(db, word_index, heading_map, hs_meta)

    # Pass 2: Synonyms
    print("\n--- Pass 2: Hebrew<->English synonyms ---")
    p2 = _pass2_synonyms(word_index)

    # Compact
    print("\n--- Compacting index ---")
    _compact_index(word_index)

    # Write output
    print("\n--- Writing output ---")
    _write_output(word_index, heading_map, hs_meta, output_path)

    elapsed = time.time() - t_total
    print(f"\n{'=' * 60}")
    print(f"DONE in {elapsed:.1f}s")
    print(f"  Words: {len(word_index)}")
    print(f"  HS codes in meta: {len(hs_meta)}")
    print(f"  Headings: {len(heading_map)}")
    print(f"  Entries: Pass0={p0} + Pass1={p1} + Pass2={p2}")
    print(f"{'=' * 60}")

    return {
        "words": len(word_index),
        "hs_codes": len(hs_meta),
        "headings": len(heading_map),
        "pass0": p0, "pass1": p1, "pass2": p2,
        "elapsed": elapsed,
    }


# ---------------------------------------------------------------------------
#  CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    no_firestore = "--no-firestore" in sys.argv

    db = None
    if not no_firestore:
        try:
            import google.cloud.firestore as firestore
            # Try default creds first, then SA key
            sa_paths = [
                os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
                os.path.join(os.path.expanduser("~"), "sa-key.json"),
                os.path.join(_script_dir, "..", "sa-key.json"),
                os.path.join(_script_dir, "scripts", "firebase-credentials.json"),
            ]
            for sa_path in sa_paths:
                if sa_path and os.path.exists(sa_path):
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa_path
                    print(f"Using SA key: {sa_path}")
                    break
            db = firestore.Client(project="rpa-port-customs")
            # Quick connectivity check
            db.collection("tariff").limit(1).get()
            print("Firestore connected OK")
        except Exception as e:
            print(f"Firestore connection failed: {e}")
            print("Running Pass 0 only (--no-firestore mode)")
            db = None

    build_index(db=db)
