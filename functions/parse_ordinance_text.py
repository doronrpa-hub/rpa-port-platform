#!/usr/bin/env python3
"""
Parse pkudat_mechess.txt (Customs Ordinance) and extract the full Hebrew text
for each article.

The file has:
- Lines 1-~2510: Table of Contents (TOC) + HTML/CSS junk
- Lines ~2511+: Actual article content starting with "פרק ראשון: מבוא"

Articles appear as:
  Pattern A: "NUMBER.   " at start of line (e.g., "1.    ", "130. ", "241. ")
  Pattern B: "NUMBERsuffix." at start of line (e.g., "30א.", "133א.", "231א.")
  Pattern C: Split across two lines:
             "NUMBER"   (bare number on one line)
             "suffix."  (Hebrew suffix + dot on next line, e.g., "א. ...")
  Pattern D: Split number + dot:
             "NUMBER"   (bare number on one line)
             ".  ..."   (dot + text on next line)

Chapter headings: Lines starting with "פרק " (e.g., "פרק ראשון: מבוא")

Amendment blocks contain:
  - "(תיקון מס'" lines
  - "מיום" date lines
  - "ס\"ח" or "ס"ח" legislative references
  - "ה\"ח" or "ה"ח" bill references
  - "החלפת סעיף" replacement notices
  - "הנוסח הקודם:" (previous version marker)
  - "הוספת" addition notices
  - "ביטול" cancellation notices
  - "תיקון מס'" amendment notices (without parens)

Only the FIRST occurrence of each article number is the current version.
Later occurrences (after "הנוסח הקודם:") are old versions and must be skipped.

Usage:
    python parse_ordinance_text.py
    python parse_ordinance_text.py --json          # output as JSON
    python parse_ordinance_text.py --article 130   # show specific article
    python parse_ordinance_text.py --chapter 8     # show articles in chapter
"""

import os
import re
import json
import sys
from collections import OrderedDict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Path to the source file
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_PATH = os.path.join(os.path.dirname(_SCRIPT_DIR), "data_c3", "pkudat_mechess.txt")

# Content starts after this line number (skip TOC)
_CONTENT_START_LINE = 2510

# Hebrew number suffixes (ordered for greedy matching — longest first)
# In Hebrew numbering: 15=טו (NOT יה), 16=טז (NOT יו) to avoid divine names.
# Some articles have combined suffixes like א1, א2 (e.g., 231א1, 231א2).
_HEB_SUFFIXES = [
    "יח", "יז", "טז", "טו", "יד", "יג", "יב", "יא", "י",
    "ט", "ח", "ז", "ו", "ה", "ד", "ג", "ב",
    "א2", "א1", "א",  # א1/א2 before plain א for greedy match
]
_HEB_SUFFIX_PATTERN = "|".join(_HEB_SUFFIXES)

# Chapter heading to chapter number mapping
_CHAPTER_MAP = {
    "ראשון": 1,
    "שני": 2,
    "שלישי": 3,
    "רביעי": 4,
    "חמישי": 5,
    "ששי": 6,
    "שביעי": 7,
    "שמיני": 8,
    "תשיעי": 9,
    "עשירי": 10,
    "אחד עשר": 11,
    "שנים עשר": 12,
    "שלושה עשר א'": "13א",
    "שלושה עשר": 13,
    "ארבעה עשר א'": "14א",
    "ארבעה עשר": 14,
    "חמישה עשר": 15,
}

# Regex to detect article number at beginning of line
# Matches: "123." or "123א." or "123.   " etc.
_RE_ARTICLE_LINE = re.compile(
    r'^(\d+)(' + _HEB_SUFFIX_PATTERN + r')?\.\s'
)

# Regex to detect bare number on a line (for split article patterns)
_RE_BARE_NUMBER = re.compile(r'^(\d+)\s*$')

# Regex to detect Hebrew suffix start on next line (for split patterns)
_RE_SUFFIX_DOT_LINE = re.compile(
    r'^(' + _HEB_SUFFIX_PATTERN + r')\.\s'
)

# Regex to detect dot-start line (for split patterns like "65\n. (א)")
_RE_DOT_LINE = re.compile(r'^\.\s')

# Regex to detect chapter heading
_RE_CHAPTER = re.compile(r'^פרק\s+(.+?)(?:\s*:|\s*$)')

# Lines that signal amendment/legislative-history blocks
# These terminate article text collection.
_RE_AMENDMENT_START = re.compile(
    r'^(?:'
    r'מיום\s+\d'                            # "מיום 1.1.2025"
    r'|תיקון\s+מס[\'׳]'                     # "תיקון מס' 28"
    r'|ס"ח\s'                               # "ס"ח תשע"ח"
    r'|ס\"ח\s'                              # escaped variant
    r'|ה"ח\s'                               # "ה"ח 1150"
    r'|ה\"ח\s'                              # escaped variant
    r'|ה"ח$'                                # "ה"ח" alone on line
    r'|ה\"ח$'                               # escaped variant
    r'|החלפת\s'                             # "החלפת סעיף"
    r'|הנוסח\s+הקודם'                       # "הנוסח הקודם:"
    r'|הוספת\s'                             # "הוספת סעיף/הגדרת"
    r'|ביטול\s+סעיף'                        # "ביטול סעיף"
    r'|ק"ת\s'                              # "ק"ת תשפ"ד"
    r'|ק\"ת\s'                             # escaped variant
    r')'
)

# "Previous version" marker -- everything after this is OLD text
_RE_PREVIOUS_VERSION = re.compile(r'^הנוסח\s+הקודם')

# Title-like lines that precede article numbers
# These are short Hebrew lines that describe the article topic
_RE_TITLE_CANDIDATE = re.compile(
    r'^[\u0590-\u05FF]'  # starts with Hebrew
)

# Lines that are clearly NOT titles
_RE_NOT_TITLE = re.compile(
    r'^(?:'
    r'\(תיקון'              # amendment citation
    r'|\(בוטל\)'            # repealed marker
    r'|מיום\s'              # date
    r'|תיקון\s'             # amendment
    r'|ס"ח\s'               # legislative ref
    r'|ס\"ח\s'
    r'|ה"ח'                 # bill ref
    r'|ה\"ח'
    r'|ק"ת\s'
    r'|ק\"ת\s'
    r'|החלפת\s'             # replacement
    r'|הנוסח\s+הקודם'       # previous version
    r'|הוספת\s'             # addition
    r'|ביטול\s'             # cancellation
    r'|צו\s+תש'            # order citation
    r'|פרק\s'              # chapter heading
    r'|סימן\s'             # section heading
    r'|\*'                  # asterisk
    r'|\)'                  # closing paren
    r'|\d+$'                # bare number
    r')'
)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _parse_chapter_number(chapter_text):
    """Extract chapter number from Hebrew chapter heading text."""
    chapter_text = chapter_text.strip().rstrip(":")
    # Try longest matches first
    for heb, num in sorted(_CHAPTER_MAP.items(), key=lambda x: -len(x[0])):
        if heb in chapter_text:
            return num
    return None


def _is_amendment_line(line):
    """Check if a line signals the start of an amendment/history block."""
    stripped = line.strip()
    if not stripped:
        return False
    return bool(_RE_AMENDMENT_START.match(stripped))


def _is_previous_version(line):
    """Check if line marks previous version text."""
    return bool(_RE_PREVIOUS_VERSION.match(line.strip()))


def _looks_like_title(line, prev_line=""):
    """Check if a line looks like an article title."""
    stripped = line.strip()
    if not stripped:
        return False
    if len(stripped) > 120:
        return False
    if len(stripped) < 2:
        return False
    if _RE_NOT_TITLE.match(stripped):
        return False
    if not _RE_TITLE_CANDIDATE.match(stripped):
        return False
    # Title lines are typically short descriptive Hebrew text
    # They should not contain article sub-section markers like (א), (1) etc.
    if stripped.startswith("(") and stripped[1] != "ת":  # but allow (תיקון)
        return False
    return True


def parse_ordinance(filepath=None):
    """
    Parse the customs ordinance file and extract all articles.

    Returns:
        dict: Mapping of article_id -> {
            "title_he": str or "",
            "full_text_he": str,
            "chapter": int or str (e.g., 1, 2, ..., "13א", "14א"),
            "line_start": int,
            "line_end": int,
        }
    """
    if filepath is None:
        filepath = _DEFAULT_PATH

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Source file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        all_lines = f.readlines()

    # Only process lines after TOC
    lines = all_lines[_CONTENT_START_LINE:]  # 0-indexed, so this skips first 2510 lines

    articles = OrderedDict()
    current_chapter = None
    seen_articles = set()  # Track first occurrence only
    in_old_version = False  # After "הנוסח הקודם:", skip until next valid article

    # State for current article being collected
    cur_article_id = None
    cur_article_lines = []
    cur_article_title = ""
    cur_article_chapter = None
    cur_article_line_start = 0
    cur_in_amendment = False  # Are we in an amendment block?

    # Previous non-empty lines for title detection
    prev_nonempty_lines = []

    def _flush_article():
        """Save the current article if we have one."""
        nonlocal cur_article_id, cur_article_lines, cur_article_title
        nonlocal cur_article_chapter, cur_article_line_start, cur_in_amendment

        if cur_article_id and cur_article_id not in seen_articles:
            # Join and clean up the collected text
            text = "\n".join(cur_article_lines).strip()
            # Remove trailing empty lines
            while text.endswith("\n\n"):
                text = text[:-1]

            articles[cur_article_id] = {
                "title_he": cur_article_title.strip(),
                "full_text_he": text,
                "chapter": cur_article_chapter,
                "line_start": cur_article_line_start,
            }
            seen_articles.add(cur_article_id)

        cur_article_id = None
        cur_article_lines = []
        cur_article_title = ""
        cur_article_chapter = None
        cur_article_line_start = 0
        cur_in_amendment = False

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n").rstrip("\r")
        # Normalize non-breaking spaces to regular spaces for matching
        line_normalized = line.replace("\xa0", " ")
        stripped = line_normalized.strip()
        abs_line = _CONTENT_START_LINE + i + 1  # 1-based line number in original file

        # ------------------------------------------------------------------
        # Detect chapter headings
        # ------------------------------------------------------------------
        ch_match = _RE_CHAPTER.match(stripped)
        if ch_match:
            ch_num = _parse_chapter_number(ch_match.group(1))
            if ch_num is not None:
                # Always update chapter -- chapter headings are structural
                # boundaries that mark real transitions, even if they appear
                # inside old-version blocks (the chapter heading itself is
                # never "old version" text).
                current_chapter = ch_num
                # A chapter heading also ends any old-version block
                in_old_version = False
            i += 1
            continue

        # ------------------------------------------------------------------
        # Detect "הנוסח הקודם:" -- everything after this is old version
        # until next article that we haven't seen yet
        # ------------------------------------------------------------------
        if _is_previous_version(stripped):
            _flush_article()
            in_old_version = True
            i += 1
            continue

        # ------------------------------------------------------------------
        # Detect amendment lines -- terminate current article text
        # ------------------------------------------------------------------
        if _is_amendment_line(stripped):
            if cur_article_id and not cur_in_amendment:
                cur_in_amendment = True
            i += 1
            continue

        # ------------------------------------------------------------------
        # Try to detect article start
        # ------------------------------------------------------------------
        article_id = None
        article_first_text = ""
        consumed_extra = 0  # How many extra lines this pattern consumed

        # Pattern A/B: "NUMBER." or "NUMBERsuffix." on one line
        # Match against normalized line (not stripped) to preserve spaces after dot
        m = _RE_ARTICLE_LINE.match(line_normalized)
        if not m:
            # Also try left-stripped version (some lines have leading spaces)
            m = _RE_ARTICLE_LINE.match(line_normalized.lstrip())
        if m:
            num = m.group(1)
            suffix = m.group(2) or ""
            article_id = f"{num}{suffix}"
            # Get text after the article number pattern
            rest_text = line_normalized[m.end():] if _RE_ARTICLE_LINE.match(line_normalized) else line_normalized.lstrip()[m.end():]
            article_first_text = rest_text.strip()

        # Pattern C/D: Bare number on this line, suffix/dot on next line
        if article_id is None:
            bm = _RE_BARE_NUMBER.match(stripped)
            if bm:
                num = bm.group(1)
                num_int = int(num)
                # Only consider article-range numbers (1-250ish)
                # Skip numbers that are clearly amendment references (e.g., "2627", "3117")
                if 1 <= num_int <= 250 and (i + 1) < len(lines):
                    next_line = lines[i + 1].rstrip("\n").rstrip("\r").replace("\xa0", " ")
                    next_stripped = next_line.strip()

                    # But first, verify context: the previous line should NOT be
                    # "ה"ח" or similar (which would make this a bill number)
                    prev_context_ok = True
                    if i > 0:
                        prev = lines[i - 1].replace("\xa0", " ").strip()
                        if prev in ("ה\"ח", 'ה"ח', "ה״ח", "ס\"ח", 'ס"ח', "ק\"ת", 'ק"ת'):
                            prev_context_ok = False

                    if prev_context_ok:
                        # Check if next line starts with Hebrew suffix + dot
                        sm = _RE_SUFFIX_DOT_LINE.match(next_stripped)
                        if sm:
                            suffix = sm.group(1)
                            article_id = f"{num}{suffix}"
                            article_first_text = next_stripped[sm.end():].strip()
                            consumed_extra = 1
                        # Check if next line starts with just a dot
                        elif _RE_DOT_LINE.match(next_stripped):
                            article_id = num
                            article_first_text = next_stripped[1:].strip()
                            consumed_extra = 1

        # ------------------------------------------------------------------
        # If we found an article start, process it
        # ------------------------------------------------------------------
        if article_id is not None:
            # Check if this is a duplicate (old version)
            if article_id in seen_articles:
                # Skip this occurrence - it's an old version
                in_old_version = True
                i += 1 + consumed_extra
                continue

            # If we were in old_version mode and found a new unseen article,
            # we're back to current text
            in_old_version = False

            # Flush previous article
            _flush_article()

            # Determine title from previous non-empty lines
            title = ""
            # Look back at previous non-empty lines for title candidate
            for prev_txt, prev_ln in reversed(prev_nonempty_lines[-3:]):
                if _looks_like_title(prev_txt):
                    # Strip amendment citation suffix like "(תיקון מס' 28) תשע"ח-2018"
                    candidate = prev_txt.strip()
                    # Remove trailing amendment references
                    candidate = re.sub(
                        r'\s*\(תיקון\s+מס[\'׳]\s*\d+\)\s+תש.*$', '', candidate
                    )
                    if candidate and len(candidate) >= 2:
                        title = candidate
                        break

            cur_article_id = article_id
            cur_article_title = title
            cur_article_chapter = current_chapter
            cur_article_line_start = abs_line
            cur_in_amendment = False
            cur_article_lines = []

            if article_first_text:
                cur_article_lines.append(article_first_text)

            i += 1 + consumed_extra
            continue

        # ------------------------------------------------------------------
        # If we're collecting article text, add this line (if not amendment)
        # ------------------------------------------------------------------
        if cur_article_id and not cur_in_amendment and not in_old_version:
            if stripped:
                cur_article_lines.append(stripped)
            elif cur_article_lines:
                # Blank line within article text -- preserve paragraph break
                cur_article_lines.append("")

        # Track previous non-empty lines for title detection
        if stripped:
            prev_nonempty_lines.append((stripped, abs_line))
            if len(prev_nonempty_lines) > 5:
                prev_nonempty_lines.pop(0)

        i += 1

    # Flush last article
    _flush_article()

    return articles


def _clean_article_text(text):
    """Clean up article text: remove trailing blank lines, normalize whitespace."""
    # Remove multiple consecutive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip trailing whitespace on each line
    lines = [ln.rstrip() for ln in text.split('\n')]
    # Remove trailing empty lines
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines)


def _get_chapter_name(ch):
    """Get a display name for a chapter number."""
    names = {
        1: "פרק ראשון: מבוא",
        2: "פרק שני: מינהל",
        3: "פרק שלישי: פיקוח, בדיקה, הצהרות וערובה",
        4: "פרק רביעי: ייבוא טובין",
        5: "פרק חמישי: החסנת טובין",
        6: "פרק ששי: ייצוא טובין",
        7: "פרק שביעי: צידת אניה",
        8: "פרק שמיני: תשלומי מכס",
        9: "פרק תשיעי: הישבון וכניסה זמנית",
        10: "פרק עשירי: סחר החוף",
        11: "פרק אחד עשר: סוכנים",
        12: "פרק שנים עשר: סמכויות פקידי-מכס",
        13: "פרק שלושה עשר: חילוטין ועונשין",
        "13א": "פרק שלושה עשר א': אמצעי אכיפה מינהליים",
        14: "פרק ארבעה עשר: אישומי מכס",
        "14א": "פרק ארבעה עשר א': דיווח אלקטרוני",
        15: "פרק חמישה עשר: הוראות שונות",
    }
    return names.get(ch, f"פרק {ch}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Parse Customs Ordinance (פקודת המכס) and extract articles"
    )
    parser.add_argument(
        "--file", "-f",
        default=_DEFAULT_PATH,
        help="Path to pkudat_mechess.txt"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--article", "-a",
        help="Show specific article (e.g., 130, 133א)"
    )
    parser.add_argument(
        "--chapter", "-c",
        help="Show articles in specific chapter (e.g., 8, 13א)"
    )
    parser.add_argument(
        "--summary", "-s",
        action="store_true",
        help="Show summary stats only (default when no other flag)"
    )
    parser.add_argument(
        "--list-chapters",
        action="store_true",
        help="List all chapters with article counts"
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Show N sample articles"
    )
    args = parser.parse_args()

    print(f"Parsing: {args.file}")
    print()

    try:
        articles = parse_ordinance(args.file)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to parse: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Clean up article texts
    for art_id, data in articles.items():
        data["full_text_he"] = _clean_article_text(data["full_text_he"])

    # ------------------------------------------------------------------
    # Show specific article
    # ------------------------------------------------------------------
    if args.article:
        art = articles.get(args.article)
        if art:
            print(f"=== Article {args.article} ===")
            print(f"Chapter: {art['chapter']} ({_get_chapter_name(art['chapter'])})")
            print(f"Title: {art['title_he']}")
            print(f"Line: {art['line_start']}")
            print(f"Text length: {len(art['full_text_he'])} chars")
            print()
            print(art["full_text_he"])
        else:
            print(f"Article {args.article} not found.")
            # Show similar
            prefix = re.match(r'\d+', args.article)
            if prefix:
                similar = [k for k in articles if k.startswith(prefix.group())]
                if similar:
                    print(f"Similar articles: {', '.join(sorted(similar))}")
        return

    # ------------------------------------------------------------------
    # Show chapter
    # ------------------------------------------------------------------
    if args.chapter:
        ch = args.chapter
        # Try to convert to int if it's a plain number
        try:
            ch = int(ch)
        except ValueError:
            pass
        ch_articles = {k: v for k, v in articles.items() if v["chapter"] == ch}
        if ch_articles:
            print(f"=== {_get_chapter_name(ch)} ({len(ch_articles)} articles) ===")
            print()
            for art_id, data in ch_articles.items():
                title_part = f" [{data['title_he']}]" if data['title_he'] else ""
                text_preview = data["full_text_he"][:100].replace("\n", " ")
                print(f"  {art_id}{title_part}: {text_preview}...")
        else:
            print(f"No articles found for chapter {ch}")
        return

    # ------------------------------------------------------------------
    # JSON output
    # ------------------------------------------------------------------
    if args.json:
        # Convert to serializable format (remove line_start)
        output = {}
        for art_id, data in articles.items():
            output[art_id] = {
                "title_he": data["title_he"],
                "full_text_he": data["full_text_he"],
                "chapter": data["chapter"],
            }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    # ------------------------------------------------------------------
    # List chapters
    # ------------------------------------------------------------------
    if args.list_chapters:
        chapter_counts = {}
        chapter_chars = {}
        for data in articles.values():
            ch = data["chapter"]
            chapter_counts[ch] = chapter_counts.get(ch, 0) + 1
            chapter_chars[ch] = chapter_chars.get(ch, 0) + len(data["full_text_he"])

        print("Chapter                                           | Articles | Total Chars")
        print("-" * 80)
        for ch in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, "13א", 14, "14א", 15]:
            name = _get_chapter_name(ch)
            count = chapter_counts.get(ch, 0)
            chars = chapter_chars.get(ch, 0)
            if count > 0:
                print(f"  {name:<50s}| {count:>5d}    | {chars:>8,d}")
        # Check for articles with no chapter
        no_ch = sum(1 for d in articles.values() if d["chapter"] is None)
        if no_ch:
            print(f"  {'(no chapter)':50s}| {no_ch:>5d}    |")
        print("-" * 80)
        print(f"  {'TOTAL':50s}| {len(articles):>5d}    | {sum(chapter_chars.values()):>8,d}")
        return

    # ------------------------------------------------------------------
    # Show samples
    # ------------------------------------------------------------------
    if args.sample > 0:
        import itertools
        for art_id, data in itertools.islice(articles.items(), args.sample):
            print(f"=== Article {art_id} (Ch.{data['chapter']}) ===")
            if data["title_he"]:
                print(f"Title: {data['title_he']}")
            text = data["full_text_he"]
            if len(text) > 500:
                print(text[:500] + "\n[... truncated ...]")
            else:
                print(text)
            print()
        return

    # ------------------------------------------------------------------
    # Default: summary
    # ------------------------------------------------------------------
    print(f"Total articles extracted: {len(articles)}")
    print()

    # Per-chapter stats
    chapter_counts = {}
    chapter_chars = {}
    for data in articles.values():
        ch = data["chapter"]
        chapter_counts[ch] = chapter_counts.get(ch, 0) + 1
        chapter_chars[ch] = chapter_chars.get(ch, 0) + len(data["full_text_he"])

    print("Per-chapter breakdown:")
    print(f"  {'Chapter':<55s} {'Articles':>8s} {'Chars':>10s}")
    print("  " + "-" * 75)
    for ch in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, "13א", 14, "14א", 15]:
        name = _get_chapter_name(ch)
        count = chapter_counts.get(ch, 0)
        chars = chapter_chars.get(ch, 0)
        if count > 0:
            print(f"  {name:<55s} {count:>8d} {chars:>10,d}")
    no_ch = sum(1 for d in articles.values() if d["chapter"] is None)
    if no_ch:
        print(f"  {'(no chapter assigned)':<55s} {no_ch:>8d}")
    print("  " + "-" * 75)
    total_chars = sum(len(d["full_text_he"]) for d in articles.values())
    print(f"  {'TOTAL':<55s} {len(articles):>8d} {total_chars:>10,d}")

    # Articles with titles
    titled = sum(1 for d in articles.values() if d["title_he"])
    print(f"\nArticles with title: {titled}/{len(articles)} ({100*titled//len(articles)}%)")

    # Repealed articles
    repealed = sum(1 for d in articles.values()
                   if "(בוטל)" in d["full_text_he"][:20])
    print(f"Repealed articles (בוטל): {repealed}")

    # Average text length
    texts = [len(d["full_text_he"]) for d in articles.values()]
    if texts:
        avg = sum(texts) / len(texts)
        print(f"Text length: avg={avg:.0f}, min={min(texts)}, max={max(texts)} chars")

    # Articles with Hebrew suffixes
    suffixed = [k for k in articles if re.search(r'[א-ת]', k)]
    print(f"Articles with Hebrew suffix: {len(suffixed)}")
    if suffixed:
        print(f"  Examples: {', '.join(sorted(suffixed)[:15])}...")

    # Show first and last 5 article IDs
    art_ids = list(articles.keys())
    print(f"\nFirst 10 articles: {', '.join(art_ids[:10])}")
    print(f"Last 10 articles: {', '.join(art_ids[-10:])}")


if __name__ == "__main__":
    main()
