#!/usr/bin/env python3
"""Build customs vocabulary: maps common product names → official tariff terms.

Runs OFFLINE only. Produces functions/lib/_customs_vocabulary.py.

Sources (in order):
  1. Tariff tree — extract every Hebrew/English term from all 18,032 nodes
  2. Hebrew Academy borrowed words (web fetch)
  3. Web search for heading synonyms (rate-limited)
  4. Wikipedia Hebrew — common import product categories

Usage:
    cd rpa-port-platform
    python scripts/build_customs_vocabulary.py [--resume] [--skip-web]

Output:
    functions/lib/_customs_vocabulary.py
"""

import os
import sys
import re
import json
import time
import hashlib
import textwrap
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

# Add functions/ to path so we can import tariff_tree
_ROOT = Path(__file__).resolve().parent.parent
_FUNCS = _ROOT / "functions"
sys.path.insert(0, str(_FUNCS))

# --- Progress file for incremental saves ---
_PROGRESS_FILE = _ROOT / "scripts" / "_vocab_progress.json"
_OUTPUT_FILE = _FUNCS / "lib" / "_customs_vocabulary.py"

# Rate limit between web requests (seconds)
_WEB_DELAY = 1.2


# ═══════════════════════════════════════════════════════════════════════
#  Utilities
# ═══════════════════════════════════════════════════════════════════════

_HE_PREFIXES = ("של", "וה", "מה", "לה", "בה", "כש", "מ", "ב", "ל", "ה", "ו", "כ", "ש")
_STOP_WORDS = frozenset({
    "את", "של", "על", "עם", "או", "גם", "כי", "אם", "לא", "יש", "זה",
    "אל", "הם", "הוא", "היא", "בין", "כל", "מן", "אשר", "עד", "רק",
    "חוץ", "לרבות", "מסוג", "מהסוג", "המשמש", "לפי", "כגון", "אחר",
    "אחרים", "אחרת", "שאינם", "שאינן",
    "the", "a", "an", "of", "for", "and", "or", "with", "to", "from",
    "in", "on", "by", "is", "are", "not", "other", "others", "whether",
    "including", "excluding", "n.e.s.", "n.e.s",
})
_WORD_RE = re.compile(r'[^\w\u0590-\u05FF]+')


def _is_hebrew(text: str) -> bool:
    return any('\u0590' <= c <= '\u05FF' for c in text)


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    words = _WORD_RE.split(text.lower())
    return [w for w in words if len(w) >= 2 and w not in _STOP_WORDS]


def _strip_he_prefix(word: str) -> str:
    if len(word) <= 3:
        return word
    for pfx in _HE_PREFIXES:
        if word.startswith(pfx) and len(word) - len(pfx) >= 2:
            return word[len(pfx):]
    return word


def _safe_get(url: str, params=None, headers=None, timeout=15) -> Optional[str]:
    """Rate-limited HTTP GET. Returns text or None."""
    import requests
    time.sleep(_WEB_DELAY)
    try:
        ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        hdrs = {**ua, **(headers or {})}
        resp = requests.get(url, params=params, headers=hdrs, timeout=timeout)
        if resp.status_code == 200 and len(resp.text) > 50:
            resp.encoding = "utf-8"
            return resp.text
    except Exception as e:
        print(f"    [GET FAIL] {url[:80]}: {e}")
    return None


def _load_progress() -> dict:
    if _PROGRESS_FILE.exists():
        try:
            return json.loads(_PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"vocab": {}, "completed_phases": [], "web_search_done": [],
            "wiki_done": [], "academy_done": False}


def _save_progress(progress: dict):
    _PROGRESS_FILE.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ═══════════════════════════════════════════════════════════════════════
#  PHASE 1: Tariff tree extraction
# ═══════════════════════════════════════════════════════════════════════

def phase1_tariff_tree(vocab: dict) -> int:
    """Extract official terms from tariff tree headings."""
    print("\n═══ Phase 1: Tariff tree extraction ═══")
    try:
        from lib.tariff_tree import load_tariff_tree
    except ImportError:
        print("  ERROR: tariff_tree not available")
        return 0

    nodes, fc_index, root_ids = load_tariff_tree()
    added = 0

    # Collect heading-level (L3) official terms
    headings = [(n.fc, n.desc_he, n.desc_en, n.level)
                for n in nodes.values() if n.level == 3 and n.desc_he]

    print(f"  Found {len(headings)} headings with Hebrew descriptions")

    # Build chapter → heading description map
    chapter_headings: Dict[str, List[str]] = defaultdict(list)
    for fc, desc_he, desc_en, level in headings:
        ch = fc[:2] if fc else ""
        if ch:
            chapter_headings[ch].append(desc_he)

    # Extract meaningful multi-word terms from descriptions
    # These are the OFFICIAL tariff terms
    for fc, desc_he, desc_en, level in headings:
        ch = fc[:2] if fc else ""
        if not ch:
            continue

        # Extract the primary term (first phrase before comma or semicolon)
        primary_he = re.split(r'[,;()\-–]', desc_he)[0].strip()
        primary_he_clean = re.sub(r'\s+', ' ', primary_he).strip()

        if len(primary_he_clean) >= 3 and primary_he_clean.lower() not in _STOP_WORDS:
            key = primary_he_clean.lower()
            if key not in vocab:
                vocab[key] = {
                    "official": primary_he_clean,
                    "chapters": [ch],
                    "confidence": "HIGH",
                    "source": "tariff_tree",
                }
                added += 1
            else:
                # Add chapter if not already there
                if ch not in vocab[key]["chapters"]:
                    vocab[key]["chapters"].append(ch)

        # Also map English primary term → Hebrew official
        if desc_en:
            primary_en = re.split(r'[,;()\-–]', desc_en)[0].strip()
            primary_en_clean = re.sub(r'\s+', ' ', primary_en).strip().lower()
            if len(primary_en_clean) >= 3 and primary_en_clean not in _STOP_WORDS:
                if primary_en_clean not in vocab:
                    vocab[primary_en_clean] = {
                        "official": primary_he_clean,
                        "chapters": [ch],
                        "confidence": "HIGH",
                        "source": "tariff_tree",
                        "english_term": primary_en_clean,
                    }
                    added += 1
                else:
                    if ch not in vocab[primary_en_clean]["chapters"]:
                        vocab[primary_en_clean]["chapters"].append(ch)

    # Also extract individual significant words and map to their chapters
    # This gives us word→chapter hints even when the full phrase doesn't match
    word_chapters: Dict[str, Set[str]] = defaultdict(set)
    for fc, desc_he, desc_en, level in headings:
        ch = fc[:2] if fc else ""
        if not ch:
            continue
        for w in _tokenize(desc_he):
            root = _strip_he_prefix(w)
            if len(root) >= 3:
                word_chapters[root].add(ch)
        if desc_en:
            for w in _tokenize(desc_en):
                if len(w) >= 3:
                    word_chapters[w].add(ch)

    # Add single words that map to 1-3 chapters (specific enough to be useful)
    for word, chs in word_chapters.items():
        if 1 <= len(chs) <= 3 and word not in vocab:
            ch_list = sorted(chs)
            vocab[word] = {
                "official": word,
                "chapters": ch_list,
                "confidence": "MEDIUM",
                "source": "tariff_tree_word",
            }
            added += 1

    # Now extract from ALL nodes (not just headings) — subheadings have
    # more specific product terms
    for nid, node in nodes.items():
        if node.level < 4 or not node.desc_he:
            continue
        ch = (node.fc or "")[:2]
        if not ch:
            continue

        # Extract key product words from sub-headings
        for w in _tokenize(node.desc_he):
            root = _strip_he_prefix(w)
            if len(root) >= 3 and root not in vocab:
                # Only add if it maps to a small set of chapters
                chs = word_chapters.get(root, set())
                chs.add(ch)
                if len(chs) <= 4:
                    vocab[root] = {
                        "official": root,
                        "chapters": sorted(chs),
                        "confidence": "MEDIUM",
                        "source": "tariff_tree_subheading",
                    }
                    added += 1

    print(f"  Added {added} entries from tariff tree")
    return added


# ═══════════════════════════════════════════════════════════════════════
#  PHASE 2: Curated product-name → tariff-term mappings
# ═══════════════════════════════════════════════════════════════════════

# These are the CORE mappings that fix the 10-product test failures.
# Each maps a common Hebrew/English product name to its official tariff term.
_CURATED_MAPPINGS = {
    # --- Electronics (ch 84, 85) ---
    "מחשב": {"official": "מכונות אוטומטיות לעיבוד נתונים", "chapters": ["84"], "en": "computer"},
    "מחשב נייד": {"official": "מכונות אוטומטיות לעיבוד נתונים ניידות", "chapters": ["84"], "en": "laptop"},
    "לפטופ": {"official": "מכונות אוטומטיות לעיבוד נתונים ניידות", "chapters": ["84"], "en": "laptop"},
    "laptop": {"official": "מכונות אוטומטיות לעיבוד נתונים ניידות", "chapters": ["84"]},
    "computer": {"official": "מכונות אוטומטיות לעיבוד נתונים", "chapters": ["84"]},
    "notebook": {"official": "מכונות אוטומטיות לעיבוד נתונים ניידות", "chapters": ["84"]},
    "טאבלט": {"official": "מכונות אוטומטיות לעיבוד נתונים", "chapters": ["84"], "en": "tablet"},
    "tablet": {"official": "מכונות אוטומטיות לעיבוד נתונים", "chapters": ["84"]},
    "טלפון סלולרי": {"official": "טלפונים לרשתות תאיות", "chapters": ["85"], "en": "cellular phone"},
    "טלפון נייד": {"official": "טלפונים לרשתות תאיות", "chapters": ["85"], "en": "mobile phone"},
    "סלולרי": {"official": "טלפונים לרשתות תאיות", "chapters": ["85"], "en": "cellular"},
    "סמארטפון": {"official": "טלפונים לרשתות תאיות", "chapters": ["85"], "en": "smartphone"},
    "smartphone": {"official": "טלפונים לרשתות תאיות", "chapters": ["85"]},
    "cellphone": {"official": "טלפונים לרשתות תאיות", "chapters": ["85"]},
    "mobile phone": {"official": "טלפונים לרשתות תאיות", "chapters": ["85"]},
    "טלוויזיה": {"official": "מקלטי טלוויזיה", "chapters": ["85"], "en": "television"},
    "television": {"official": "מקלטי טלוויזיה", "chapters": ["85"]},
    "tv": {"official": "מקלטי טלוויזיה", "chapters": ["85"]},
    "מסך": {"official": "צגים", "chapters": ["85"], "en": "monitor"},
    "monitor": {"official": "צגים", "chapters": ["85"]},
    "מדפסת": {"official": "מדפסות", "chapters": ["84"], "en": "printer"},
    "printer": {"official": "מדפסות", "chapters": ["84"]},
    "מקלדת": {"official": "מקלדות", "chapters": ["84"], "en": "keyboard"},
    "עכבר": {"official": "התקני קלט", "chapters": ["84"], "en": "mouse"},
    "אוזניות": {"official": "אוזניות ושפופרות אוזן", "chapters": ["85"], "en": "headphones"},
    "headphones": {"official": "אוזניות ושפופרות אוזן", "chapters": ["85"]},
    "רמקול": {"official": "רמקולים", "chapters": ["85"], "en": "speaker"},
    "speaker": {"official": "רמקולים", "chapters": ["85"]},
    "מצלמה": {"official": "מצלמות", "chapters": ["90"], "en": "camera"},
    "camera": {"official": "מצלמות", "chapters": ["90"]},
    "מייבש שיער": {"official": "מייבשי שיער", "chapters": ["85"], "en": "hair dryer"},
    "שואב אבק": {"official": "שואבי אבק", "chapters": ["85"], "en": "vacuum cleaner"},
    "מיקרוגל": {"official": "תנורי מיקרוגל", "chapters": ["85"], "en": "microwave"},
    "microwave": {"official": "תנורי מיקרוגל", "chapters": ["85"]},
    "מקרר": {"official": "מקררים", "chapters": ["84"], "en": "refrigerator"},
    "refrigerator": {"official": "מקררים", "chapters": ["84"]},
    "fridge": {"official": "מקררים", "chapters": ["84"]},
    "מכונת כביסה": {"official": "מכונות כביסה", "chapters": ["84"], "en": "washing machine"},
    "washing machine": {"official": "מכונות כביסה", "chapters": ["84"]},
    "מזגן": {"official": "מכונות ומכשירים לבקרת אקלים", "chapters": ["84"], "en": "air conditioner"},
    "air conditioner": {"official": "מכונות ומכשירים לבקרת אקלים", "chapters": ["84"]},
    "מדיח כלים": {"official": "מכונות להדחת כלים", "chapters": ["84"], "en": "dishwasher"},

    # --- Coffee machines ---
    "מכונת קפה": {"official": "מכונות לייצור קפה או תה", "chapters": ["84", "85"], "en": "coffee machine"},
    "coffee machine": {"official": "מכונות לייצור קפה או תה", "chapters": ["84", "85"]},
    "espresso machine": {"official": "מכונות לייצור קפה או תה", "chapters": ["84", "85"]},
    "מכונת אספרסו": {"official": "מכונות לייצור קפה או תה", "chapters": ["84", "85"], "en": "espresso machine"},
    "קומקום": {"official": "קומקומים חשמליים", "chapters": ["85"], "en": "electric kettle"},
    "kettle": {"official": "קומקומים חשמליים", "chapters": ["85"]},
    "טוסטר": {"official": "מצנמים", "chapters": ["85"], "en": "toaster"},
    "toaster": {"official": "מצנמים", "chapters": ["85"]},

    # --- Vehicles & parts (ch 87) ---
    "רכב": {"official": "רכב מנועי", "chapters": ["87"], "en": "vehicle"},
    "מכונית": {"official": "רכב מנועי להובלת אנשים", "chapters": ["87"], "en": "car"},
    "car": {"official": "רכב מנועי להובלת אנשים", "chapters": ["87"]},
    "automobile": {"official": "רכב מנועי להובלת אנשים", "chapters": ["87"]},
    "משאית": {"official": "רכב מנועי להובלת טובין", "chapters": ["87"], "en": "truck"},
    "truck": {"official": "רכב מנועי להובלת טובין", "chapters": ["87"]},
    "אופנוע": {"official": "אופנועים", "chapters": ["87"], "en": "motorcycle"},
    "motorcycle": {"official": "אופנועים", "chapters": ["87"]},
    "אופניים": {"official": "אופניים", "chapters": ["87"], "en": "bicycle"},
    "bicycle": {"official": "אופניים", "chapters": ["87"]},
    "חלקי חילוף": {"official": "חלקים ואבזרים", "chapters": ["84", "87"], "en": "spare parts"},
    "חלקי חילוף לרכב": {"official": "חלקים ואבזרים לרכב מנועי", "chapters": ["87"], "en": "vehicle spare parts"},
    "spare parts": {"official": "חלקים ואבזרים", "chapters": ["84", "87"]},
    "צמיג": {"official": "צמיגים פנאומטיים", "chapters": ["40"], "en": "tire"},
    "tire": {"official": "צמיגים פנאומטיים", "chapters": ["40"]},
    "tyre": {"official": "צמיגים פנאומטיים", "chapters": ["40"]},
    "מנוע רכב": {"official": "מנועים לרכב", "chapters": ["84", "87"], "en": "vehicle engine"},
    "גיר": {"official": "תיבות הילוכים", "chapters": ["87"], "en": "gearbox"},
    "בלמים": {"official": "מערכות בלימה", "chapters": ["87"], "en": "brakes"},
    "סוללת רכב": {"official": "מצברים חשמליים", "chapters": ["85"], "en": "car battery"},

    # --- Textiles & clothing (ch 61, 62, 63) ---
    "בגדים": {"official": "פריטי לבוש", "chapters": ["61", "62"], "en": "clothing"},
    "בגדי ילדים": {"official": "פריטי לבוש לילדים", "chapters": ["61", "62"], "en": "children's clothing"},
    "clothing": {"official": "פריטי לבוש", "chapters": ["61", "62"]},
    "חולצה": {"official": "חולצות", "chapters": ["61", "62"], "en": "shirt"},
    "shirt": {"official": "חולצות", "chapters": ["61", "62"]},
    "מכנסיים": {"official": "מכנסיים", "chapters": ["61", "62"], "en": "trousers"},
    "trousers": {"official": "מכנסיים", "chapters": ["61", "62"]},
    "pants": {"official": "מכנסיים", "chapters": ["61", "62"]},
    "שמלה": {"official": "שמלות", "chapters": ["61", "62"], "en": "dress"},
    "dress": {"official": "שמלות", "chapters": ["61", "62"]},
    "חצאית": {"official": "חצאיות", "chapters": ["61", "62"], "en": "skirt"},
    "ז'קט": {"official": "ז'קטים ובלייזרים", "chapters": ["61", "62"], "en": "jacket"},
    "jacket": {"official": "ז'קטים ובלייזרים", "chapters": ["61", "62"]},
    "מעיל": {"official": "מעילים", "chapters": ["61", "62"], "en": "coat"},
    "coat": {"official": "מעילים", "chapters": ["61", "62"]},
    "גרביים": {"official": "גרביים וכיסויי רגל", "chapters": ["61"], "en": "socks"},
    "socks": {"official": "גרביים וכיסויי רגל", "chapters": ["61"]},
    "נעליים": {"official": "הנעלה", "chapters": ["64"], "en": "shoes"},
    "shoes": {"official": "הנעלה", "chapters": ["64"]},
    "footwear": {"official": "הנעלה", "chapters": ["64"]},
    "כותנה": {"official": "כותנה", "chapters": ["52"], "en": "cotton"},
    "cotton": {"official": "כותנה", "chapters": ["52"]},
    "פוליאסטר": {"official": "סיבים סינתטיים", "chapters": ["54", "55"], "en": "polyester"},
    "polyester": {"official": "סיבים סינתטיים", "chapters": ["54", "55"]},
    "משי": {"official": "משי", "chapters": ["50"], "en": "silk"},
    "silk": {"official": "משי", "chapters": ["50"]},
    "צמר": {"official": "צמר", "chapters": ["51"], "en": "wool"},
    "wool": {"official": "צמר", "chapters": ["51"]},

    # --- Furniture (ch 94) ---
    "ספה": {"official": "מושבים מרופדים", "chapters": ["94"], "en": "sofa"},
    "sofa": {"official": "מושבים מרופדים", "chapters": ["94"]},
    "couch": {"official": "מושבים מרופדים", "chapters": ["94"]},
    "כורסה": {"official": "כורסאות מרופדות", "chapters": ["94"], "en": "armchair"},
    "armchair": {"official": "כורסאות מרופדות", "chapters": ["94"]},
    "כיסא": {"official": "מושבים", "chapters": ["94"], "en": "chair"},
    "chair": {"official": "מושבים", "chapters": ["94"]},
    "שולחן": {"official": "שולחנות", "chapters": ["94"], "en": "table"},
    "table": {"official": "שולחנות", "chapters": ["94"]},
    "desk": {"official": "שולחנות כתיבה", "chapters": ["94"]},
    "מיטה": {"official": "מיטות", "chapters": ["94"], "en": "bed"},
    "bed": {"official": "מיטות", "chapters": ["94"]},
    "mattress": {"official": "מזרנים", "chapters": ["94"]},
    "מזרן": {"official": "מזרנים", "chapters": ["94"], "en": "mattress"},
    "ארון": {"official": "ארונות", "chapters": ["94"], "en": "cabinet"},
    "cabinet": {"official": "ארונות", "chapters": ["94"]},
    "מדף": {"official": "מדפים", "chapters": ["94"], "en": "shelf"},
    "shelf": {"official": "מדפים", "chapters": ["94"]},

    # --- Food & beverages (ch 01-24) ---
    "שרימפס": {"official": "סרטנים", "chapters": ["03"], "en": "shrimp"},
    "shrimp": {"official": "סרטנים", "chapters": ["03"]},
    "prawn": {"official": "סרטנים", "chapters": ["03"]},
    "לובסטר": {"official": "סרטנים", "chapters": ["03"], "en": "lobster"},
    "lobster": {"official": "סרטנים", "chapters": ["03"]},
    "דג": {"official": "דגים", "chapters": ["03"], "en": "fish"},
    "דגים": {"official": "דגים", "chapters": ["03"], "en": "fish"},
    "fish": {"official": "דגים", "chapters": ["03"]},
    "בשר": {"official": "בשר", "chapters": ["02"], "en": "meat"},
    "meat": {"official": "בשר", "chapters": ["02"]},
    "בשר בקר": {"official": "בשר בקר", "chapters": ["02"], "en": "beef"},
    "beef": {"official": "בשר בקר", "chapters": ["02"]},
    "עוף": {"official": "בשר עופות", "chapters": ["02"], "en": "chicken"},
    "chicken": {"official": "בשר עופות", "chapters": ["02"]},
    "חלב": {"official": "חלב ומוצרי חלב", "chapters": ["04"], "en": "milk"},
    "milk": {"official": "חלב ומוצרי חלב", "chapters": ["04"]},
    "dairy": {"official": "חלב ומוצרי חלב", "chapters": ["04"]},
    "גבינה": {"official": "גבינות", "chapters": ["04"], "en": "cheese"},
    "cheese": {"official": "גבינות", "chapters": ["04"]},
    "ביצים": {"official": "ביצי עופות", "chapters": ["04"], "en": "eggs"},
    "eggs": {"official": "ביצי עופות", "chapters": ["04"]},
    "ירקות": {"official": "ירקות", "chapters": ["07"], "en": "vegetables"},
    "vegetables": {"official": "ירקות", "chapters": ["07"]},
    "פירות": {"official": "פירות", "chapters": ["08"], "en": "fruits"},
    "fruits": {"official": "פירות", "chapters": ["08"]},
    "fruit": {"official": "פירות", "chapters": ["08"]},
    "אורז": {"official": "אורז", "chapters": ["10"], "en": "rice"},
    "rice": {"official": "אורז", "chapters": ["10"]},
    "חיטה": {"official": "חיטה", "chapters": ["10"], "en": "wheat"},
    "wheat": {"official": "חיטה", "chapters": ["10"]},
    "סוכר": {"official": "סוכר", "chapters": ["17"], "en": "sugar"},
    "sugar": {"official": "סוכר", "chapters": ["17"]},
    "שוקולד": {"official": "שוקולד ותכשירי קקאו", "chapters": ["18"], "en": "chocolate"},
    "chocolate": {"official": "שוקולד ותכשירי קקאו", "chapters": ["18"]},
    "קפה": {"official": "קפה", "chapters": ["09"], "en": "coffee"},
    "coffee": {"official": "קפה", "chapters": ["09"]},
    "תה": {"official": "תה", "chapters": ["09"], "en": "tea"},
    "tea": {"official": "תה", "chapters": ["09"]},
    "יין": {"official": "יין", "chapters": ["22"], "en": "wine"},
    "wine": {"official": "יין", "chapters": ["22"]},
    "בירה": {"official": "בירה", "chapters": ["22"], "en": "beer"},
    "beer": {"official": "בירה", "chapters": ["22"]},
    "שמן זית": {"official": "שמן זית", "chapters": ["15"], "en": "olive oil"},
    "olive oil": {"official": "שמן זית", "chapters": ["15"]},
    "שמן דגים": {"official": "שומנים ושמנים של דגים", "chapters": ["15"], "en": "fish oil"},

    # --- Pharmaceuticals (ch 30) ---
    "תרופה": {"official": "תכשירים רוקחיים", "chapters": ["30"], "en": "medicine"},
    "תרופות": {"official": "תכשירים רוקחיים", "chapters": ["30"], "en": "medicines"},
    "medicine": {"official": "תכשירים רוקחיים", "chapters": ["30"]},
    "drug": {"official": "תכשירים רוקחיים", "chapters": ["30"]},
    "pharmaceutical": {"official": "תכשירים רוקחיים", "chapters": ["30"]},
    "תרופות לב": {"official": "תכשירים רוקחיים למערכת הלב", "chapters": ["30"], "en": "cardiac medicine"},
    "אנטיביוטיקה": {"official": "אנטיביוטיקה", "chapters": ["30"], "en": "antibiotics"},
    "antibiotics": {"official": "אנטיביוטיקה", "chapters": ["30"]},
    "ויטמינים": {"official": "ויטמינים", "chapters": ["29", "30"], "en": "vitamins"},
    "vitamins": {"official": "ויטמינים", "chapters": ["29", "30"]},
    "חיסון": {"official": "חיסונים", "chapters": ["30"], "en": "vaccine"},
    "vaccine": {"official": "חיסונים", "chapters": ["30"]},

    # --- Solar & energy (ch 85) ---
    "פאנל סולארי": {"official": "התקנים פוטו-וולטאיים מוליכים למחצה", "chapters": ["85"], "en": "solar panel"},
    "פאנלים סולאריים": {"official": "התקנים פוטו-וולטאיים מוליכים למחצה", "chapters": ["85"], "en": "solar panels"},
    "solar panel": {"official": "התקנים פוטו-וולטאיים מוליכים למחצה", "chapters": ["85"]},
    "solar panels": {"official": "התקנים פוטו-וולטאיים מוליכים למחצה", "chapters": ["85"]},
    "פוטו וולטאי": {"official": "התקנים פוטו-וולטאיים מוליכים למחצה", "chapters": ["85"], "en": "photovoltaic"},
    "photovoltaic": {"official": "התקנים פוטו-וולטאיים מוליכים למחצה", "chapters": ["85"]},
    "סוללה": {"official": "מצברים חשמליים", "chapters": ["85"], "en": "battery"},
    "battery": {"official": "מצברים חשמליים", "chapters": ["85"]},
    "מצבר": {"official": "מצברים חשמליים", "chapters": ["85"], "en": "accumulator"},

    # --- Baby products (ch 87, 94, 95) ---
    "עגלת תינוק": {"official": "עגלות לתינוקות", "chapters": ["87"], "en": "baby stroller"},
    "עגלת ילדים": {"official": "עגלות לתינוקות", "chapters": ["87"], "en": "baby carriage"},
    "baby stroller": {"official": "עגלות לתינוקות", "chapters": ["87"]},
    "stroller": {"official": "עגלות לתינוקות", "chapters": ["87"]},
    "pram": {"official": "עגלות לתינוקות", "chapters": ["87"]},
    "צעצוע": {"official": "צעצועים", "chapters": ["95"], "en": "toy"},
    "צעצועים": {"official": "צעצועים", "chapters": ["95"], "en": "toys"},
    "toy": {"official": "צעצועים", "chapters": ["95"]},
    "toys": {"official": "צעצועים", "chapters": ["95"]},
    "כיסא תינוק": {"official": "מושבי בטיחות לילדים", "chapters": ["94"], "en": "baby seat"},

    # --- Construction & ceramics (ch 68, 69) ---
    "אריחים": {"official": "אריחים", "chapters": ["69"], "en": "tiles"},
    "אריחי קרמיקה": {"official": "לוחות ריצוף וחיפוי מקרמיקה", "chapters": ["69"], "en": "ceramic tiles"},
    "ceramic tiles": {"official": "לוחות ריצוף וחיפוי מקרמיקה", "chapters": ["69"]},
    "tiles": {"official": "אריחים", "chapters": ["69"]},
    "קרמיקה": {"official": "מוצרי קרמיקה", "chapters": ["69"], "en": "ceramics"},
    "ceramics": {"official": "מוצרי קרמיקה", "chapters": ["69"]},
    "מלט": {"official": "מלט", "chapters": ["25"], "en": "cement"},
    "cement": {"official": "מלט", "chapters": ["25"]},
    "בטון": {"official": "בטון", "chapters": ["68"], "en": "concrete"},
    "concrete": {"official": "בטון", "chapters": ["68"]},
    "לבנים": {"official": "לבנים לבנייה", "chapters": ["69"], "en": "bricks"},
    "bricks": {"official": "לבנים לבנייה", "chapters": ["69"]},
    "גבס": {"official": "גבס", "chapters": ["25", "68"], "en": "plaster"},

    # --- Cables & electrical (ch 85) ---
    "כבל חשמל": {"official": "חוטים, כבלים מבודדים לחשמל", "chapters": ["85"], "en": "electric cable"},
    "כבלי חשמל": {"official": "חוטים, כבלים מבודדים לחשמל", "chapters": ["85"], "en": "electric cables"},
    "electric cable": {"official": "חוטים, כבלים מבודדים לחשמל", "chapters": ["85"]},
    "cable": {"official": "חוטים, כבלים מבודדים לחשמל", "chapters": ["85"]},
    "חוט חשמל": {"official": "חוטים, כבלים מבודדים לחשמל", "chapters": ["85"], "en": "electric wire"},
    "wire": {"official": "חוטים", "chapters": ["72", "73", "74", "85"]},

    # --- Metals (ch 72-76) ---
    "פלדה": {"official": "פלדה", "chapters": ["72", "73"], "en": "steel"},
    "steel": {"official": "פלדה", "chapters": ["72", "73"]},
    "ברזל": {"official": "ברזל", "chapters": ["72", "73"], "en": "iron"},
    "iron": {"official": "ברזל", "chapters": ["72", "73"]},
    "אלומיניום": {"official": "אלומיניום", "chapters": ["76"], "en": "aluminum"},
    "aluminum": {"official": "אלומיניום", "chapters": ["76"]},
    "aluminium": {"official": "אלומיניום", "chapters": ["76"]},
    "נחושת": {"official": "נחושת", "chapters": ["74"], "en": "copper"},
    "copper": {"official": "נחושת", "chapters": ["74"]},

    # --- Plastics & rubber (ch 39, 40) ---
    "פלסטיק": {"official": "פלסטיק ומוצרי פלסטיק", "chapters": ["39"], "en": "plastic"},
    "plastic": {"official": "פלסטיק ומוצרי פלסטיק", "chapters": ["39"]},
    "גומי": {"official": "גומי ומוצרי גומי", "chapters": ["40"], "en": "rubber"},
    "rubber": {"official": "גומי ומוצרי גומי", "chapters": ["40"]},

    # --- Paper (ch 48, 49) ---
    "נייר": {"official": "נייר וקרטון", "chapters": ["48"], "en": "paper"},
    "paper": {"official": "נייר וקרטון", "chapters": ["48"]},
    "קרטון": {"official": "קרטון", "chapters": ["48"], "en": "cardboard"},
    "cardboard": {"official": "קרטון", "chapters": ["48"]},

    # --- Glass (ch 70) ---
    "זכוכית": {"official": "זכוכית", "chapters": ["70"], "en": "glass"},
    "glass": {"official": "זכוכית", "chapters": ["70"]},

    # --- Chemicals (ch 28-38) ---
    "דשן": {"official": "דשנים", "chapters": ["31"], "en": "fertilizer"},
    "fertilizer": {"official": "דשנים", "chapters": ["31"]},
    "צבע": {"official": "צבעים ולכות", "chapters": ["32"], "en": "paint"},
    "paint": {"official": "צבעים ולכות", "chapters": ["32"]},
    "סבון": {"official": "סבון", "chapters": ["34"], "en": "soap"},
    "soap": {"official": "סבון", "chapters": ["34"]},
    "דטרגנט": {"official": "חומרי כביסה", "chapters": ["34"], "en": "detergent"},
    "detergent": {"official": "חומרי כביסה", "chapters": ["34"]},
    "בושם": {"official": "בשמים ומוצרי טואלט", "chapters": ["33"], "en": "perfume"},
    "perfume": {"official": "בשמים ומוצרי טואלט", "chapters": ["33"]},
    "קוסמטיקה": {"official": "תכשירי קוסמטיקה", "chapters": ["33"], "en": "cosmetics"},
    "cosmetics": {"official": "תכשירי קוסמטיקה", "chapters": ["33"]},

    # --- Machinery (ch 84) ---
    "מנוף": {"official": "מנופים", "chapters": ["84"], "en": "crane"},
    "crane": {"official": "מנופים", "chapters": ["84"]},
    "מלגזה": {"official": "מלגזות", "chapters": ["84", "87"], "en": "forklift"},
    "forklift": {"official": "מלגזות", "chapters": ["84", "87"]},
    "משאבה": {"official": "משאבות", "chapters": ["84"], "en": "pump"},
    "pump": {"official": "משאבות", "chapters": ["84"]},
    "מדחס": {"official": "מדחסים", "chapters": ["84"], "en": "compressor"},
    "compressor": {"official": "מדחסים", "chapters": ["84"]},
    "גנרטור": {"official": "מחוללי חשמל", "chapters": ["85"], "en": "generator"},
    "generator": {"official": "מחוללי חשמל", "chapters": ["85"]},
    "שנאי": {"official": "שנאים חשמליים", "chapters": ["85"], "en": "transformer"},
    "transformer": {"official": "שנאים חשמליים", "chapters": ["85"]},

    # --- Medical devices (ch 90) ---
    "ציוד רפואי": {"official": "מכשירים ומתקנים לרפואה", "chapters": ["90"], "en": "medical equipment"},
    "medical equipment": {"official": "מכשירים ומתקנים לרפואה", "chapters": ["90"]},
    "מכשיר שמיעה": {"official": "מכשירי שמיעה", "chapters": ["90"], "en": "hearing aid"},
    "משקפיים": {"official": "משקפיים", "chapters": ["90"], "en": "glasses"},
    "glasses": {"official": "משקפיים", "chapters": ["90"]},
    "עדשות מגע": {"official": "עדשות מגע", "chapters": ["90"], "en": "contact lenses"},

    # --- Cosmetics processing terms ---
    "קרם": {"official": "תכשירי טיפוח", "chapters": ["33"], "en": "cream"},
    "שמפו": {"official": "שמפו", "chapters": ["33"], "en": "shampoo"},
    "shampoo": {"official": "שמפו", "chapters": ["33"]},

    # --- Jewelry (ch 71) ---
    "תכשיטים": {"official": "תכשיטי זהב וכסף", "chapters": ["71"], "en": "jewelry"},
    "jewelry": {"official": "תכשיטי זהב וכסף", "chapters": ["71"]},
    "jewellery": {"official": "תכשיטי זהב וכסף", "chapters": ["71"]},
    "יהלום": {"official": "יהלומים", "chapters": ["71"], "en": "diamond"},
    "diamond": {"official": "יהלומים", "chapters": ["71"]},

    # --- Sporting goods (ch 95) ---
    "ציוד ספורט": {"official": "פריטי ספורט", "chapters": ["95"], "en": "sports equipment"},
    "כדור": {"official": "כדורים", "chapters": ["95"], "en": "ball"},
    "אופני כושר": {"official": "מתקני כושר", "chapters": ["95"], "en": "exercise bike"},

    # --- Musical instruments (ch 92) ---
    "פסנתר": {"official": "פסנתרים", "chapters": ["92"], "en": "piano"},
    "piano": {"official": "פסנתרים", "chapters": ["92"]},
    "גיטרה": {"official": "גיטרות", "chapters": ["92"], "en": "guitar"},
    "guitar": {"official": "גיטרות", "chapters": ["92"]},

    # --- Wood products (ch 44) ---
    "עץ": {"official": "עץ", "chapters": ["44"], "en": "wood"},
    "wood": {"official": "עץ", "chapters": ["44"]},
    "timber": {"official": "עץ בצורתו הגסה", "chapters": ["44"]},
    "דיקט": {"official": "עץ סיבים לבוד", "chapters": ["44"], "en": "plywood"},
    "plywood": {"official": "עץ סיבים לבוד", "chapters": ["44"]},

    # --- Misc common imports ---
    "שעון": {"official": "שעונים", "chapters": ["91"], "en": "watch"},
    "watch": {"official": "שעונים", "chapters": ["91"]},
    "clock": {"official": "שעוני קיר", "chapters": ["91"]},
    "תיק": {"official": "מזוודות, תיקים", "chapters": ["42"], "en": "bag"},
    "bag": {"official": "מזוודות, תיקים", "chapters": ["42"]},
    "מזוודה": {"official": "מזוודות", "chapters": ["42"], "en": "suitcase"},
    "suitcase": {"official": "מזוודות", "chapters": ["42"]},
    "מטריה": {"official": "מטריות", "chapters": ["66"], "en": "umbrella"},
    "umbrella": {"official": "מטריות", "chapters": ["66"]},
    "ספר": {"official": "ספרים מודפסים", "chapters": ["49"], "en": "book"},
    "book": {"official": "ספרים מודפסים", "chapters": ["49"]},
}


def phase2_curated_mappings(vocab: dict) -> int:
    """Add curated product-name → tariff-term mappings."""
    print("\n═══ Phase 2: Curated product mappings ═══")
    added = 0
    for term, data in _CURATED_MAPPINGS.items():
        key = term.lower()
        entry = {
            "official": data["official"],
            "chapters": data["chapters"],
            "confidence": "HIGH",
            "source": "curated",
        }
        if "en" in data:
            entry["english_term"] = data["en"]
        if key not in vocab:
            vocab[key] = entry
            added += 1
        else:
            # Curated overrides tree-extracted — more precise
            if vocab[key].get("source") != "curated":
                vocab[key] = entry
                added += 1
    print(f"  Added/updated {added} curated entries (total curated: {len(_CURATED_MAPPINGS)})")
    return added


# ═══════════════════════════════════════════════════════════════════════
#  PHASE 3: Hebrew Academy borrowed words
# ═══════════════════════════════════════════════════════════════════════

def phase3_hebrew_academy(vocab: dict, progress: dict, skip_web: bool = False) -> int:
    """Fetch Hebrew Academy borrowed word lists and map to tariff terms."""
    print("\n═══ Phase 3: Hebrew Academy borrowed words ═══")
    if skip_web:
        print("  Skipping (--skip-web)")
        return 0
    if progress.get("academy_done"):
        print("  Already done (resume)")
        return 0

    added = 0

    # Source 1: Borrowed words decision page
    url = "https://hebrew-academy.org.il/topic/hahlatot/grammardecisions/borrowed-words/"
    html = _safe_get(url)
    if html:
        # Look for word pairs in the page
        # Pattern: foreign word → Hebrew equivalent
        # The page has structured lists with borrowed words
        pairs = re.findall(
            r'<td[^>]*>([^<]{2,30})</td>\s*<td[^>]*>([^<]{2,30})</td>',
            html,
        )
        for foreign, hebrew in pairs:
            foreign = foreign.strip().lower()
            hebrew = hebrew.strip()
            if len(foreign) >= 2 and len(hebrew) >= 2 and _is_hebrew(hebrew):
                # Check if either term is in our vocab → create cross-reference
                if foreign in vocab:
                    if hebrew.lower() not in vocab:
                        vocab[hebrew.lower()] = {
                            "official": vocab[foreign].get("official", hebrew),
                            "chapters": vocab[foreign].get("chapters", []),
                            "confidence": "MEDIUM",
                            "source": "hebrew_academy",
                        }
                        added += 1
                elif hebrew.lower() in vocab:
                    if foreign not in vocab:
                        vocab[foreign] = {
                            "official": vocab[hebrew.lower()].get("official", foreign),
                            "chapters": vocab[hebrew.lower()].get("chapters", []),
                            "confidence": "MEDIUM",
                            "source": "hebrew_academy",
                        }
                        added += 1
        print(f"  Borrowed words page: found {len(pairs)} pairs, added {added}")
    else:
        print("  Could not fetch borrowed words page")

    # Source 2: 100 words PDF — try to fetch text
    pdf_url = "https://hebrew-academy.org.il/wp-content/uploads/100milim.pdf"
    print(f"  Attempting PDF: {pdf_url}")
    try:
        import requests
        time.sleep(_WEB_DELAY)
        resp = requests.get(pdf_url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })
        if resp.status_code == 200 and len(resp.content) > 1000:
            # Save temporarily and try to extract text
            tmp_path = _ROOT / "scripts" / "_temp_100milim.pdf"
            tmp_path.write_bytes(resp.content)
            print(f"  Downloaded PDF ({len(resp.content)} bytes)")

            # Try PyMuPDF
            try:
                import fitz
                doc = fitz.open(str(tmp_path))
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()

                # Parse word pairs from text
                lines = text.split("\n")
                pdf_added = 0
                for line in lines:
                    # Look for patterns like "computer מחשב" or "טלפון telephone"
                    words = line.strip().split()
                    if len(words) >= 2:
                        he_words = [w for w in words if _is_hebrew(w)]
                        en_words = [w for w in words if not _is_hebrew(w) and len(w) >= 3]
                        for hw in he_words:
                            for ew in en_words:
                                ew_lower = ew.lower()
                                hw_lower = hw.lower()
                                if ew_lower in vocab and hw_lower not in vocab:
                                    vocab[hw_lower] = {
                                        "official": vocab[ew_lower].get("official", hw),
                                        "chapters": vocab[ew_lower].get("chapters", []),
                                        "confidence": "MEDIUM",
                                        "source": "hebrew_academy_pdf",
                                    }
                                    pdf_added += 1
                print(f"  PDF extraction: added {pdf_added} cross-references")
                added += pdf_added
            except ImportError:
                print("  PyMuPDF not available — skipping PDF parsing")
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
        else:
            print(f"  PDF download failed: status={resp.status_code}")
    except Exception as e:
        print(f"  PDF download error: {e}")

    progress["academy_done"] = True
    _save_progress(progress)
    print(f"  Total added from Hebrew Academy: {added}")
    return added


# ═══════════════════════════════════════════════════════════════════════
#  PHASE 4: Wikipedia Hebrew — common product categories
# ═══════════════════════════════════════════════════════════════════════

# Top 200 most common import product categories for Israel
_WIKI_PRODUCT_QUERIES = [
    # Electronics
    "מחשב נייד", "טלפון חכם", "טלוויזיה", "מצלמה דיגיטלית", "מקרן",
    "רמקול בלוטות", "שעון חכם", "דיסק קשיח", "כונן הבזק", "נתב אינטרנט",
    "טאבלט", "קונסולת משחקים", "מסך מחשב", "מדפסת", "סורק",
    # Appliances
    "מקרר", "מכונת כביסה", "מדיח כלים", "מזגן", "מייבש כביסה",
    "שואב אבק", "תנור אפייה", "כיריים", "מיקרוגל", "מכונת קפה",
    "קומקום חשמלי", "מגהץ", "טוסטר", "בלנדר", "מסחטת מיצים",
    # Vehicles
    "רכב חשמלי", "אופנוע", "קטנוע", "אופניים חשמליים", "קורקינט חשמלי",
    # Furniture
    "ספה", "כורסה", "שולחן כתיבה", "מיטה", "מזרן", "ארון בגדים",
    "כיסא משרדי", "שידה", "כוננית", "מדף",
    # Food
    "שוקולד", "קפה", "תה", "אורז", "שמן זית",
    "גבינה", "יין", "בירה", "דבש", "תבלינים",
    "אגוזים", "שקדים", "תמרים",
    # Textiles
    "בד כותנה", "צמר", "משי", "פוליאסטר", "ניילון",
    "ג'ינס", "חולצת פולו", "שמלת ערב", "חליפה", "מעיל חורף",
    # Construction
    "מלט", "בטון", "אריחי קרמיקה", "גבס", "בלוק בנייה",
    "צינור פלסטיק", "ברז", "אסלה",
    # Chemicals
    "צבע אקרילי", "דבק", "חומר ניקוי", "חומר הדברה",
    # Medical
    "תרופה", "ציוד רפואי", "מסכה רפואית", "כפפות לטקס",
    "מכשיר שמיעה", "כיסא גלגלים", "משקפי ראייה",
    # Metals
    "פלדת אל-חלד", "אלומיניום", "נחושת", "פליז", "אבץ",
    # Energy
    "פאנל סולארי", "טורבינת רוח", "סוללת ליתיום",
    # Others
    "צעצוע", "משחק לוח", "פאזל", "בובה",
    "שעון יד", "תכשיט זהב", "יהלום",
    "כלי נגינה", "גיטרה", "פסנתר",
    "ספר", "עיתון", "מגזין",
    "מזוודה", "תיק גב", "ארנק",
    "נרות", "גפרורים", "סכין", "מזלג", "כף",
    "סיר", "מחבת", "קדרה",
    "מפתח ברגים", "מברג", "מקדחה", "מסור",
    "מנעול", "ציר", "בורג",
]


def phase4_wikipedia(vocab: dict, progress: dict, skip_web: bool = False) -> int:
    """Fetch Wikipedia Hebrew articles for common products and extract synonyms."""
    print("\n═══ Phase 4: Wikipedia Hebrew ═══")
    if skip_web:
        print("  Skipping (--skip-web)")
        return 0

    done_set = set(progress.get("wiki_done", []))
    added = 0
    total = len(_WIKI_PRODUCT_QUERIES)

    for i, query in enumerate(_WIKI_PRODUCT_QUERIES):
        if query in done_set:
            continue

        print(f"  [{i+1}/{total}] Wiki: {query}")

        # Wikipedia API search
        url = "https://he.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 3,
            "format": "json",
        }
        text = _safe_get(url, params=params)
        if not text:
            done_set.add(query)
            continue

        try:
            data = json.loads(text)
            search_results = data.get("query", {}).get("search", [])
        except Exception:
            done_set.add(query)
            continue

        for sr in search_results[:1]:  # Top result only
            title = sr.get("title", "")
            if not title:
                continue

            # Fetch extract
            params2 = {
                "action": "query",
                "titles": title,
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "format": "json",
            }
            text2 = _safe_get(url, params=params2)
            if not text2:
                continue

            try:
                data2 = json.loads(text2)
                pages = data2.get("query", {}).get("pages", {})
                for pid, page in pages.items():
                    extract = page.get("extract", "")
                    if not extract or len(extract) < 50:
                        continue

                    # Extract synonyms from first paragraph
                    first_para = extract.split("\n")[0]

                    # Pattern: "X (גם Y או Z)" or "X, הנקרא גם Y"
                    # Look for Hebrew alternative names
                    alt_names = re.findall(
                        r'(?:גם|נקרא|ידוע|מכונה|נקראת|ידועה|מכונה)\s+(?:כ|בשם\s+)?([^\s,.)]{2,30})',
                        first_para,
                    )
                    # Also look for parenthetical alternatives
                    paren_alts = re.findall(r'\(([^)]{2,50})\)', first_para)
                    for pa in paren_alts:
                        for word in re.split(r'[,;]', pa):
                            w = word.strip()
                            if _is_hebrew(w) and len(w) >= 2 and len(w) <= 30:
                                alt_names.append(w)

                    # Map: query term → synonyms found in Wikipedia
                    query_lower = query.lower()
                    for alt in alt_names:
                        alt_lower = alt.lower().strip()
                        if alt_lower == query_lower or len(alt_lower) < 2:
                            continue
                        if alt_lower in _STOP_WORDS:
                            continue

                        # If query is in vocab, add alt as cross-reference
                        if query_lower in vocab and alt_lower not in vocab:
                            vocab[alt_lower] = {
                                "official": vocab[query_lower].get("official", query),
                                "chapters": vocab[query_lower].get("chapters", []),
                                "confidence": "MEDIUM",
                                "source": "wikipedia",
                                "wiki_title": title,
                            }
                            added += 1

                    # Also: the Wikipedia title itself might be a useful term
                    title_lower = title.lower()
                    if title_lower != query_lower and title_lower not in vocab:
                        if query_lower in vocab:
                            vocab[title_lower] = {
                                "official": vocab[query_lower].get("official", query),
                                "chapters": vocab[query_lower].get("chapters", []),
                                "confidence": "MEDIUM",
                                "source": "wikipedia_title",
                            }
                            added += 1
            except Exception:
                pass

        done_set.add(query)

        # Save progress every 20 queries
        if len(done_set) % 20 == 0:
            progress["wiki_done"] = list(done_set)
            progress["vocab"] = vocab
            _save_progress(progress)
            print(f"    Progress saved ({len(done_set)}/{total} done, {added} added)")

    progress["wiki_done"] = list(done_set)
    _save_progress(progress)
    print(f"  Total added from Wikipedia: {added}")
    return added


# ═══════════════════════════════════════════════════════════════════════
#  PHASE 5: UK Trade Tariff — English heading descriptions
# ═══════════════════════════════════════════════════════════════════════

def phase5_uk_trade_tariff(vocab: dict, progress: dict, skip_web: bool = False) -> int:
    """Fetch English heading descriptions from UK Trade Tariff API.

    The UK Trade Tariff API is FREE and returns official English descriptions
    for all HS headings. These are the same descriptions used worldwide.
    """
    print("\n═══ Phase 5: UK Trade Tariff (English headings) ═══")
    if skip_web:
        print("  Skipping (--skip-web)")
        return 0

    done_chapters = set(progress.get("uk_tariff_done", []))
    added = 0

    # UK Trade Tariff API: fetch headings per chapter
    # API docs: https://api.trade-tariff.service.gov.uk
    base_url = "https://www.trade-tariff.service.gov.uk/api/v2"

    for ch_num in range(1, 100):
        ch = f"{ch_num:02d}"
        if ch in done_chapters:
            continue

        print(f"  Chapter {ch}...", end=" ", flush=True)
        url = f"{base_url}/chapters/{ch}"
        text = _safe_get(url, headers={"Accept": "application/json"})
        if not text:
            print("failed")
            done_chapters.add(ch)
            continue

        try:
            data = json.loads(text)
            chapter_data = data.get("data", {})
            ch_desc = chapter_data.get("attributes", {}).get("formatted_description", "")

            # Get headings from relationships
            headings_rel = data.get("included", [])
            heading_count = 0
            for item in headings_rel:
                if item.get("type") != "heading":
                    continue
                attrs = item.get("attributes", {})
                en_desc = attrs.get("formatted_description", "")
                goods_code = attrs.get("goods_nomenclature_item_id", "")

                if not en_desc or not goods_code:
                    continue

                # Clean HTML tags from description
                en_clean = re.sub(r'<[^>]+>', '', en_desc).strip()
                if not en_clean or len(en_clean) < 3:
                    continue

                # Extract primary English term (before comma/semicolon)
                primary_en = re.split(r'[,;()\-–]', en_clean)[0].strip().lower()

                if len(primary_en) >= 3 and primary_en not in _STOP_WORDS:
                    if primary_en not in vocab:
                        # Find Hebrew equivalent from tariff tree
                        he_official = ""
                        for key, v in vocab.items():
                            if _is_hebrew(key) and v.get("chapters") == [ch]:
                                if v.get("source") in ("tariff_tree", "curated"):
                                    he_official = v.get("official", key)
                                    break

                        vocab[primary_en] = {
                            "official": he_official or en_clean,
                            "chapters": [ch],
                            "confidence": "HIGH",
                            "source": "uk_trade_tariff",
                            "official_en": en_clean,
                        }
                        added += 1
                        heading_count += 1

                    # Also add the FULL description as a searchable entry
                    en_full_lower = en_clean.lower()
                    if len(en_full_lower) > len(primary_en) and en_full_lower not in vocab:
                        vocab[en_full_lower] = {
                            "official": he_official if 'he_official' in dir() else en_clean,
                            "chapters": [ch],
                            "confidence": "HIGH",
                            "source": "uk_trade_tariff_full",
                            "official_en": en_clean,
                        }
                        added += 1

                    # Extract individual significant English words
                    for word in _tokenize(en_clean):
                        if len(word) >= 4 and word not in vocab:
                            vocab[word] = {
                                "official": en_clean,
                                "chapters": [ch],
                                "confidence": "MEDIUM",
                                "source": "uk_trade_tariff_word",
                                "official_en": en_clean,
                            }
                            added += 1

            print(f"{heading_count} headings")
        except Exception as e:
            print(f"parse error: {e}")

        done_chapters.add(ch)

        # Save progress every 10 chapters
        if len(done_chapters) % 10 == 0:
            progress["uk_tariff_done"] = list(done_chapters)
            progress["vocab"] = vocab
            _save_progress(progress)

    progress["uk_tariff_done"] = list(done_chapters)
    _save_progress(progress)
    print(f"  Total added from UK Trade Tariff: {added}")
    return added


# ═══════════════════════════════════════════════════════════════════════
#  PHASE 6: English product term enrichment + cross-linking
# ═══════════════════════════════════════════════════════════════════════

# Common English product terms found on invoices — mapped to HS chapters
_ENGLISH_INVOICE_TERMS = {
    # Exactly the terms that appear on real commercial invoices
    # Electronics & IT
    "laptop computer": {"chapters": ["84"], "official_en": "Automatic data processing machines, portable"},
    "desktop computer": {"chapters": ["84"], "official_en": "Automatic data processing machines"},
    "server": {"chapters": ["84"], "official_en": "Automatic data processing machines"},
    "router": {"chapters": ["85"], "official_en": "Transmission apparatus for radio-telephony"},
    "switch": {"chapters": ["85"], "official_en": "Electrical apparatus for switching"},
    "modem": {"chapters": ["85"], "official_en": "Machines for the reception of voice, images"},
    "SSD": {"chapters": ["84"], "official_en": "Storage units"},
    "hard drive": {"chapters": ["84"], "official_en": "Storage units"},
    "USB flash drive": {"chapters": ["84"], "official_en": "Storage units"},
    "RAM": {"chapters": ["84"], "official_en": "Parts and accessories of automatic data processing machines"},
    "CPU": {"chapters": ["84"], "official_en": "Parts and accessories of automatic data processing machines"},
    "GPU": {"chapters": ["84"], "official_en": "Parts and accessories of automatic data processing machines"},
    "motherboard": {"chapters": ["84"], "official_en": "Parts and accessories of automatic data processing machines"},
    "power supply unit": {"chapters": ["85"], "official_en": "Static converters"},
    "UPS": {"chapters": ["85"], "official_en": "Static converters"},
    "LED display": {"chapters": ["85"], "official_en": "Monitors and projectors"},
    "LCD monitor": {"chapters": ["85"], "official_en": "Monitors and projectors"},
    "projector": {"chapters": ["85"], "official_en": "Monitors and projectors"},
    "scanner": {"chapters": ["84"], "official_en": "Input or output units"},
    "barcode reader": {"chapters": ["84"], "official_en": "Input or output units"},
    "webcam": {"chapters": ["85"], "official_en": "Television cameras"},
    "earbuds": {"chapters": ["85"], "official_en": "Headphones and earphones"},
    "bluetooth speaker": {"chapters": ["85"], "official_en": "Loudspeakers"},
    "charger": {"chapters": ["85"], "official_en": "Static converters"},
    "adapter": {"chapters": ["85"], "official_en": "Static converters"},
    "HDMI cable": {"chapters": ["85"], "official_en": "Insulated electric conductors"},
    "ethernet cable": {"chapters": ["85"], "official_en": "Insulated electric conductors"},
    "optical fiber cable": {"chapters": ["85"], "official_en": "Optical fibre cables"},
    "antenna": {"chapters": ["85"], "official_en": "Aerials and aerial reflectors"},
    # Phones
    "mobile phone": {"chapters": ["85"], "official_en": "Telephones for cellular networks"},
    "cell phone": {"chapters": ["85"], "official_en": "Telephones for cellular networks"},
    "phone case": {"chapters": ["39", "42"], "official_en": "Cases and covers"},
    "screen protector": {"chapters": ["39", "70"], "official_en": "Protection films"},
    # Appliances
    "washing machine": {"chapters": ["84"], "official_en": "Household laundry-type washing machines"},
    "dryer": {"chapters": ["84"], "official_en": "Drying machines"},
    "dishwasher": {"chapters": ["84"], "official_en": "Dish washing machines"},
    "oven": {"chapters": ["73", "85"], "official_en": "Ovens, cookers, cooking plates"},
    "stove": {"chapters": ["73", "85"], "official_en": "Cooking appliances"},
    "induction cooktop": {"chapters": ["85"], "official_en": "Cooking plates, boiling rings"},
    "air purifier": {"chapters": ["84"], "official_en": "Air conditioning machines"},
    "dehumidifier": {"chapters": ["84"], "official_en": "Air conditioning machines"},
    "water heater": {"chapters": ["84"], "official_en": "Instantaneous or storage water heaters"},
    "vacuum cleaner": {"chapters": ["85"], "official_en": "Vacuum cleaners"},
    "robot vacuum": {"chapters": ["85"], "official_en": "Vacuum cleaners"},
    "iron": {"chapters": ["85"], "official_en": "Electric smoothing irons"},
    "blender": {"chapters": ["85"], "official_en": "Electro-mechanical domestic appliances"},
    "food processor": {"chapters": ["85"], "official_en": "Electro-mechanical domestic appliances"},
    "mixer": {"chapters": ["85"], "official_en": "Electro-mechanical domestic appliances"},
    "juicer": {"chapters": ["85"], "official_en": "Electro-mechanical domestic appliances"},
    "hair dryer": {"chapters": ["85"], "official_en": "Electro-thermic hair-dressing apparatus"},
    "electric shaver": {"chapters": ["85"], "official_en": "Shavers with self-contained electric motor"},
    # Automotive
    "brake pad": {"chapters": ["68", "87"], "official_en": "Brake linings and pads"},
    "air filter": {"chapters": ["84"], "official_en": "Filtering or purifying machinery"},
    "oil filter": {"chapters": ["84"], "official_en": "Filtering or purifying machinery"},
    "spark plug": {"chapters": ["85"], "official_en": "Sparking plugs"},
    "windshield": {"chapters": ["70"], "official_en": "Safety glass, toughened or laminated"},
    "bumper": {"chapters": ["87"], "official_en": "Parts and accessories of motor vehicles"},
    "headlight": {"chapters": ["85"], "official_en": "Electrical lighting equipment for vehicles"},
    "wiper blade": {"chapters": ["85"], "official_en": "Windscreen wipers"},
    "clutch": {"chapters": ["87"], "official_en": "Parts and accessories of motor vehicles"},
    "radiator": {"chapters": ["87"], "official_en": "Parts and accessories of motor vehicles"},
    "shock absorber": {"chapters": ["87"], "official_en": "Parts and accessories of motor vehicles"},
    "wheel rim": {"chapters": ["87"], "official_en": "Wheels and parts thereof"},
    "bearing": {"chapters": ["84"], "official_en": "Ball or roller bearings"},
    "gasket": {"chapters": ["84"], "official_en": "Gaskets and similar joints"},
    "valve": {"chapters": ["84"], "official_en": "Taps, cocks, valves"},
    # Textiles
    "t-shirt": {"chapters": ["61"], "official_en": "T-shirts, singlets and other vests, knitted"},
    "polo shirt": {"chapters": ["61"], "official_en": "Men's shirts, knitted"},
    "jeans": {"chapters": ["62"], "official_en": "Men's trousers of cotton"},
    "hoodie": {"chapters": ["61"], "official_en": "Jerseys, pullovers, cardigans, knitted"},
    "sweater": {"chapters": ["61"], "official_en": "Jerseys, pullovers, cardigans, knitted"},
    "underwear": {"chapters": ["61"], "official_en": "Men's or women's undergarments, knitted"},
    "sportswear": {"chapters": ["61", "62"], "official_en": "Track suits, ski suits, swimwear"},
    "scarf": {"chapters": ["61", "62"], "official_en": "Shawls, scarves, mufflers"},
    "gloves": {"chapters": ["61", "62"], "official_en": "Gloves, mittens and mitts"},
    "hat": {"chapters": ["65"], "official_en": "Hats and other headgear"},
    "belt": {"chapters": ["42"], "official_en": "Belts and bandoliers"},
    "handbag": {"chapters": ["42"], "official_en": "Handbags"},
    "backpack": {"chapters": ["42"], "official_en": "Rucksacks, knapsacks"},
    "wallet": {"chapters": ["42"], "official_en": "Wallets, purses, key-pouches"},
    "sneakers": {"chapters": ["64"], "official_en": "Sports footwear"},
    "boots": {"chapters": ["64"], "official_en": "Footwear with outer soles of rubber or plastics"},
    "sandals": {"chapters": ["64"], "official_en": "Footwear with upper straps"},
    # Food & bev
    "frozen fish": {"chapters": ["03"], "official_en": "Fish, frozen"},
    "frozen shrimp": {"chapters": ["03"], "official_en": "Shrimps and prawns, frozen"},
    "canned tuna": {"chapters": ["16"], "official_en": "Prepared or preserved fish"},
    "olive oil": {"chapters": ["15"], "official_en": "Olive oil"},
    "sunflower oil": {"chapters": ["15"], "official_en": "Sunflower-seed oil"},
    "pasta": {"chapters": ["19"], "official_en": "Pasta"},
    "biscuits": {"chapters": ["19"], "official_en": "Sweet biscuits; waffles and wafers"},
    "infant formula": {"chapters": ["19"], "official_en": "Food preparations for infant use"},
    "spices": {"chapters": ["09"], "official_en": "Spices"},
    "cinnamon": {"chapters": ["09"], "official_en": "Cinnamon and cinnamon-tree flowers"},
    "pepper": {"chapters": ["09"], "official_en": "Pepper of the genus Piper"},
    "nuts": {"chapters": ["08"], "official_en": "Nuts"},
    "almonds": {"chapters": ["08"], "official_en": "Almonds"},
    "dates": {"chapters": ["08"], "official_en": "Dates"},
    "honey": {"chapters": ["04"], "official_en": "Natural honey"},
    "whey protein": {"chapters": ["04", "35"], "official_en": "Whey; products consisting of natural milk constituents"},
    "energy drink": {"chapters": ["22"], "official_en": "Non-alcoholic beverages"},
    "mineral water": {"chapters": ["22"], "official_en": "Mineral waters"},
    "whisky": {"chapters": ["22"], "official_en": "Whiskies"},
    "vodka": {"chapters": ["22"], "official_en": "Vodka"},
    # Construction & materials
    "ceramic tile": {"chapters": ["69"], "official_en": "Ceramic flags and paving, hearth or wall tiles"},
    "porcelain tile": {"chapters": ["69"], "official_en": "Ceramic flags and paving"},
    "granite slab": {"chapters": ["68"], "official_en": "Granite, cut or sawn"},
    "marble": {"chapters": ["68"], "official_en": "Marble, travertine"},
    "steel pipe": {"chapters": ["73"], "official_en": "Tubes, pipes and hollow profiles, of steel"},
    "steel beam": {"chapters": ["72"], "official_en": "Angles, shapes and sections of iron or steel"},
    "rebar": {"chapters": ["72"], "official_en": "Bars and rods, hot-rolled, of iron or steel"},
    "stainless steel sheet": {"chapters": ["72"], "official_en": "Flat-rolled products of stainless steel"},
    "aluminium profile": {"chapters": ["76"], "official_en": "Aluminium bars, rods and profiles"},
    "copper wire": {"chapters": ["74"], "official_en": "Copper wire"},
    "PVC pipe": {"chapters": ["39"], "official_en": "Tubes, pipes and hoses of plastics"},
    "plywood": {"chapters": ["44"], "official_en": "Plywood, veneered panels"},
    "MDF board": {"chapters": ["44"], "official_en": "Fibreboard of wood"},
    "particle board": {"chapters": ["44"], "official_en": "Particle board"},
    "insulation material": {"chapters": ["68", "39"], "official_en": "Insulating materials"},
    "roofing material": {"chapters": ["68"], "official_en": "Roofing tiles"},
    "paint": {"chapters": ["32"], "official_en": "Paints and varnishes"},
    "adhesive": {"chapters": ["35"], "official_en": "Prepared glues and adhesives"},
    "sealant": {"chapters": ["32"], "official_en": "Glaziers' putty; sealing compounds"},
    # Medical & pharma
    "surgical mask": {"chapters": ["63"], "official_en": "Face masks"},
    "latex gloves": {"chapters": ["40"], "official_en": "Gloves of vulcanized rubber"},
    "nitrile gloves": {"chapters": ["40"], "official_en": "Gloves of vulcanized rubber"},
    "syringe": {"chapters": ["90"], "official_en": "Syringes"},
    "wheelchair": {"chapters": ["87"], "official_en": "Carriages for disabled persons"},
    "prosthesis": {"chapters": ["90"], "official_en": "Artificial joints; orthopaedic appliances"},
    "blood pressure monitor": {"chapters": ["90"], "official_en": "Instruments for measuring blood pressure"},
    "thermometer": {"chapters": ["90"], "official_en": "Thermometers"},
    "stethoscope": {"chapters": ["90"], "official_en": "Stethoscopes"},
    "dental equipment": {"chapters": ["90"], "official_en": "Instruments and appliances used in dental sciences"},
    # Chemicals
    "fertilizer": {"chapters": ["31"], "official_en": "Fertilisers"},
    "pesticide": {"chapters": ["38"], "official_en": "Insecticides, fungicides, herbicides"},
    "herbicide": {"chapters": ["38"], "official_en": "Herbicides"},
    "detergent": {"chapters": ["34"], "official_en": "Organic surface-active agents"},
    "disinfectant": {"chapters": ["38"], "official_en": "Disinfectants"},
    "lubricant": {"chapters": ["27"], "official_en": "Lubricating preparations"},
    "epoxy resin": {"chapters": ["39"], "official_en": "Epoxide resins"},
    "polyethylene": {"chapters": ["39"], "official_en": "Polyethylene"},
    "polypropylene": {"chapters": ["39"], "official_en": "Polypropylene"},
    "silicone": {"chapters": ["39"], "official_en": "Silicones in primary forms"},
    # Machinery & industrial
    "CNC machine": {"chapters": ["84"], "official_en": "Machining centres, unit construction machines"},
    "lathe": {"chapters": ["84"], "official_en": "Lathes for removing metal"},
    "drill press": {"chapters": ["84"], "official_en": "Drilling machines"},
    "hydraulic press": {"chapters": ["84"], "official_en": "Presses"},
    "conveyor belt": {"chapters": ["84"], "official_en": "Conveyor machinery"},
    "forklift": {"chapters": ["84", "87"], "official_en": "Fork-lift trucks"},
    "excavator": {"chapters": ["84"], "official_en": "Self-propelled mechanical shovels, excavators"},
    "crane": {"chapters": ["84"], "official_en": "Cranes"},
    "compressor": {"chapters": ["84"], "official_en": "Air or vacuum pumps, compressors"},
    "generator": {"chapters": ["85"], "official_en": "Electric generating sets"},
    "transformer": {"chapters": ["85"], "official_en": "Electrical transformers"},
    "electric motor": {"chapters": ["85"], "official_en": "Electric motors"},
    "pump": {"chapters": ["84"], "official_en": "Pumps for liquids"},
    "heat exchanger": {"chapters": ["84"], "official_en": "Heat exchange units"},
    "boiler": {"chapters": ["84"], "official_en": "Steam or other vapour generating boilers"},
    "turbine": {"chapters": ["84"], "official_en": "Turbines"},
    # Packaging
    "cardboard box": {"chapters": ["48"], "official_en": "Cartons, boxes and cases of corrugated paper"},
    "plastic bag": {"chapters": ["39"], "official_en": "Sacks and bags of polymers of ethylene"},
    "glass bottle": {"chapters": ["70"], "official_en": "Bottles, flasks, jars of glass"},
    "metal can": {"chapters": ["73"], "official_en": "Cans of iron or steel"},
    "aluminium foil": {"chapters": ["76"], "official_en": "Aluminium foil"},
    "shrink wrap": {"chapters": ["39"], "official_en": "Self-adhesive plates, sheets, film of plastics"},
    "pallet": {"chapters": ["44"], "official_en": "Pallets, box pallets of wood"},
    # Solar & energy
    "solar panel": {"chapters": ["85"], "official_en": "Photosensitive semiconductor devices; photovoltaic cells"},
    "inverter": {"chapters": ["85"], "official_en": "Static converters"},
    "lithium battery": {"chapters": ["85"], "official_en": "Lithium-ion accumulators"},
    "lead acid battery": {"chapters": ["85"], "official_en": "Lead-acid accumulators"},
    "wind turbine": {"chapters": ["85"], "official_en": "Electric generating sets, wind-powered"},
    # Misc
    "watch": {"chapters": ["91"], "official_en": "Wrist-watches"},
    "clock": {"chapters": ["91"], "official_en": "Clocks"},
    "sunglasses": {"chapters": ["90"], "official_en": "Sunglasses"},
    "contact lens": {"chapters": ["90"], "official_en": "Contact lenses"},
    "hearing aid": {"chapters": ["90"], "official_en": "Hearing aids"},
    "musical instrument": {"chapters": ["92"], "official_en": "Musical instruments"},
    "bicycle": {"chapters": ["87"], "official_en": "Bicycles"},
    "electric bicycle": {"chapters": ["87"], "official_en": "Cycles with auxiliary motor"},
    "electric scooter": {"chapters": ["87"], "official_en": "Cycles with auxiliary motor"},
    "baby carriage": {"chapters": ["87"], "official_en": "Baby carriages"},
    "car seat": {"chapters": ["94"], "official_en": "Seats, of a kind used for motor vehicles"},
    "mattress": {"chapters": ["94"], "official_en": "Mattresses"},
    "pillow": {"chapters": ["94"], "official_en": "Pillows, cushions"},
    "carpet": {"chapters": ["57"], "official_en": "Carpets and other textile floor coverings"},
    "curtain": {"chapters": ["63"], "official_en": "Curtains, interior blinds"},
    "towel": {"chapters": ["63"], "official_en": "Toilet linen and kitchen linen"},
    "bedding": {"chapters": ["63"], "official_en": "Bed linen"},
    "candle": {"chapters": ["34"], "official_en": "Candles, tapers"},
    "toy": {"chapters": ["95"], "official_en": "Toys"},
    "board game": {"chapters": ["95"], "official_en": "Games"},
    "puzzle": {"chapters": ["95"], "official_en": "Puzzles"},
    "doll": {"chapters": ["95"], "official_en": "Dolls"},
    "book": {"chapters": ["49"], "official_en": "Printed books, brochures, leaflets"},
    "pen": {"chapters": ["96"], "official_en": "Ball point pens"},
    "pencil": {"chapters": ["96"], "official_en": "Pencils"},
    "toothbrush": {"chapters": ["96"], "official_en": "Tooth brushes"},
    "razor": {"chapters": ["82"], "official_en": "Razors and razor blades"},
    "knife": {"chapters": ["82"], "official_en": "Knives with cutting blades"},
    "scissors": {"chapters": ["82"], "official_en": "Scissors, tailors' shears"},
    "lock": {"chapters": ["83"], "official_en": "Padlocks and locks"},
    "screw": {"chapters": ["73"], "official_en": "Screws, bolts, nuts, washers of iron or steel"},
    "nail": {"chapters": ["73"], "official_en": "Nails, tacks, staples of iron or steel"},
    "hinge": {"chapters": ["83"], "official_en": "Hinges"},
    "faucet": {"chapters": ["84"], "official_en": "Taps, cocks, valves"},
    "tap": {"chapters": ["84"], "official_en": "Taps, cocks, valves"},
}


def phase6_english_enrichment(vocab: dict) -> int:
    """Add English invoice terms and build HE↔EN cross-links."""
    print("\n═══ Phase 6: English invoice terms + cross-linking ═══")
    added = 0

    # 6a: Add all English invoice terms
    for term, data in _ENGLISH_INVOICE_TERMS.items():
        key = term.lower()
        if key not in vocab:
            # Try to find Hebrew equivalent from existing vocab
            he_official = ""
            for ch in data["chapters"]:
                for vkey, vval in vocab.items():
                    if (_is_hebrew(vkey) and vval.get("source") == "curated"
                            and ch in vval.get("chapters", [])):
                        he_official = vval.get("official", "")
                        break
                if he_official:
                    break

            vocab[key] = {
                "official": he_official or data.get("official_en", term),
                "chapters": data["chapters"],
                "confidence": "HIGH",
                "source": "english_invoice",
                "official_en": data.get("official_en", term),
            }
            added += 1

    # 6b: Build cross-links: for every curated entry with "en" field,
    # ensure the English term exists in vocab pointing to same data
    for key, val in list(vocab.items()):
        en_term = val.get("english_term", "")
        if en_term:
            en_lower = en_term.lower()
            if en_lower not in vocab:
                vocab[en_lower] = {
                    "official": val.get("official", key),
                    "chapters": val.get("chapters", []),
                    "confidence": val.get("confidence", "HIGH"),
                    "source": "cross_link_en",
                    "official_en": en_term,
                }
                added += 1

    # 6c: For every English-sourced entry, ensure Hebrew equivalent exists
    for key, val in list(vocab.items()):
        if not _is_hebrew(key) and val.get("official") and _is_hebrew(val["official"]):
            he_key = val["official"].lower()
            if he_key not in vocab:
                vocab[he_key] = {
                    "official": val["official"],
                    "chapters": val.get("chapters", []),
                    "confidence": val.get("confidence", "MEDIUM"),
                    "source": "cross_link_he",
                }
                added += 1

    print(f"  Added {added} English entries + cross-links")
    return added


# ═══════════════════════════════════════════════════════════════════════
#  PHASE 7: Generate output file
# ═══════════════════════════════════════════════════════════════════════

def generate_output(vocab: dict):
    """Write functions/lib/_customs_vocabulary.py."""
    print(f"\n═══ Generating {_OUTPUT_FILE} ═══")

    # Sort entries by key
    sorted_keys = sorted(vocab.keys())

    lines = [
        '"""Auto-generated customs vocabulary.',
        '',
        'Maps common product names → official tariff terms + chapter hints.',
        'Both Hebrew and English terms included for bilingual classification.',
        'Generated by scripts/build_customs_vocabulary.py',
        '',
        'DO NOT EDIT MANUALLY — regenerate with:',
        '    python scripts/build_customs_vocabulary.py',
        '"""',
        '',
        '# Total entries: ' + str(len(sorted_keys)),
        '',
        'CUSTOMS_VOCABULARY = {',
    ]

    for key in sorted_keys:
        entry = vocab[key]
        # Clean entry for output — keep essential fields
        parts = [
            f'"official": {json.dumps(entry.get("official", key), ensure_ascii=False)}',
            f'"chapters": {json.dumps(entry.get("chapters", []), ensure_ascii=False)}',
            f'"confidence": {json.dumps(entry.get("confidence", "MEDIUM"))}',
        ]
        # Include official_en when present (English tariff description)
        if entry.get("official_en"):
            parts.append(f'"official_en": {json.dumps(entry["official_en"], ensure_ascii=False)}')
        lines.append(
            f'    {json.dumps(key, ensure_ascii=False)}: {{{", ".join(parts)}}},'
        )

    lines.append('}')
    lines.append('')

    content = "\n".join(lines)
    _OUTPUT_FILE.write_text(content, encoding="utf-8")
    print(f"  Written {len(sorted_keys)} entries to {_OUTPUT_FILE}")
    print(f"  File size: {len(content):,} bytes")


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Build customs vocabulary")
    parser.add_argument("--resume", action="store_true", help="Resume from progress file")
    parser.add_argument("--skip-web", action="store_true", help="Skip web requests (phases 3-4)")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════╗")
    print("║  Customs Vocabulary Builder                  ║")
    print("╚══════════════════════════════════════════════╝")

    if args.resume:
        progress = _load_progress()
        vocab = progress.get("vocab", {})
        print(f"Resuming: {len(vocab)} entries from progress file")
    else:
        progress = _load_progress()
        progress["vocab"] = {}
        progress["completed_phases"] = []
        vocab = {}

    t0 = time.time()

    # Phase 1: Tariff tree (always run — fast, local)
    p1 = phase1_tariff_tree(vocab)

    # Phase 2: Curated mappings (always run — no web)
    p2 = phase2_curated_mappings(vocab)

    # Phase 3: Hebrew Academy (web)
    p3 = phase3_hebrew_academy(vocab, progress, args.skip_web)

    # Phase 4: Wikipedia (web)
    p4 = phase4_wikipedia(vocab, progress, args.skip_web)

    # Phase 5: UK Trade Tariff English headings (web)
    p5 = phase5_uk_trade_tariff(vocab, progress, args.skip_web)

    # Phase 6: English invoice terms + cross-linking (always run — no web)
    p6 = phase6_english_enrichment(vocab)

    # Save final progress
    progress["vocab"] = vocab
    _save_progress(progress)

    # Generate output
    generate_output(vocab)

    elapsed = time.time() - t0
    he_count = sum(1 for k in vocab if _is_hebrew(k))
    en_count = len(vocab) - he_count
    print(f"\n{'='*50}")
    print(f"  Total entries: {len(vocab)}")
    print(f"    Hebrew:  {he_count}")
    print(f"    English: {en_count}")
    print(f"  Phase 1 (tariff tree): {p1}")
    print(f"  Phase 2 (curated):     {p2}")
    print(f"  Phase 3 (academy):     {p3}")
    print(f"  Phase 4 (wikipedia):   {p4}")
    print(f"  Phase 5 (UK tariff):   {p5}")
    print(f"  Phase 6 (EN enrich):   {p6}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
