#!/usr/bin/env python3
"""
Parse framework_order_text.txt (צו מסגרת / Framework Order) and generate
_framework_order_data.py with full Hebrew text for each article.

The source file is a PDF text extraction with:
- 44 lines total, even-indexed lines are empty (PDF page overlap)
- Articles marked as "( title_he NUMBER" e.g., "( הגדרות 01"
- Sub-articles: "SUFFIX( title_he NUMBER" e.g., "א( מיחזור 06"
- Page footers: "הודפס בתאריך DD/MM/YYYY   עמוד N"
- Each article's text runs until the next article boundary

Usage:
    python parse_framework_order.py                  # generate Python data module
    python parse_framework_order.py --json           # output as JSON
    python parse_framework_order.py --article 14     # show specific article
    python parse_framework_order.py --stats          # show article statistics
"""

import os
import re
import json
import sys
from collections import OrderedDict


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_PATH = os.path.join(os.path.dirname(_SCRIPT_DIR), "data_c3", "framework_order_text.txt")

# Page footer pattern to strip
_RE_PAGE_FOOTER = re.compile(r'הודפס בתאריך \d{2}/\d{2}/\d{4}\s+עמוד \d+')

# Hebrew letter suffixes for sub-articles
_HEB_LETTERS = "אבגדהוזחטי"

# Article boundary pattern:
#   Optional Hebrew suffix + "(" + optional title + 2-digit number
# Examples: "( הגדרות 01", "א( מיחזור וסילוק מוצרי דלק בפטור מותנה 06"
# Note: title may contain parens (e.g., "הוראה נוספת )ישראלית(")
_RE_ARTICLE = re.compile(
    r'([' + _HEB_LETTERS + r'])?\(\s*(.{0,120}?)\s+(\d{2})\s'
)

# Known article titles (manual mapping for clean output)
_ARTICLE_TITLES = {
    "01":   "הגדרות",
    "02":   "מהות התוספות הראשונה והשניה",
    "03":   "סיווג טובין בתוספת הראשונה",
    "04":   "הוראה נוספת (ישראלית)",
    "05":   "חלוקת פרט בתוספת הראשונה",
    "06":   "פרט מותנה",
    "06א":  "מיחזור וסילוק מוצרי דלק בפטור מותנה",
    "07":   "המחיר הסיטוני בייצור מקומי",
    "08":   "המחיר הסיטוני לסיגריות",
    "09":   "טובין הממועטים מן התוספת לחוק",
    "10":   "קביעת פעולת ייצור",
    "11":   "שיעור המכס או שיעור המס",
    "12":   "תיאום סכומי מס",
    "13":   "תיאום סכומי הפחתות",
    "14":   "הסכמי סחר",
    "15":   "מכסות חקלאיות",
    "16":   "הפחתת מכס לענין הסכמי הסחר עם ארה\"ב",
    "17":   "הפחתת המכס לעניין הסכם הסחר עם האיחוד האירופי",
    "18":   "הפחתת מכס לענין ארצות אפט\"א",
    "19":   "הפחתת מכס לעניין הסכם הסחר עם קנדה",
    "20":   "הפחתת מכס לענין הסכם הסחר עם ירדן",
    "21":   "הפחתת מכס לענין הסכם הסחר עם טורקיה",
    "22":   "הפחתת מכס לענין סחר עם מקסיקו",
    "23":   "הפחתת מכס לעניין ארצות מרקוסור",
    "23א":  "הפחתת מכס לעניין הסכם הסחר עם פנמה",
    "23ב":  "הפחתת מכס לעניין הסכם הסחר עם קולומביה",
    "23ג":  "הפחתת מכס לעניין הסכם הסחר עם אוקראינה",
    "23ד":  "הפחתת מכס לענין הסכם הסחר עם הממלכה המאוחדת",
    "23ה":  "הפחתת מכס לעניין הסכם הסחר עם הרפובליקה של קוריאה",
    "23ו":  "הפחתת מכס לענין הסכם הסחר עם איחוד האמירויות הערביות",
    "23ז":  "הפחתת מכס — הסכם הסחר עם גואטמלה",
    "24":   "בטל",
    "25":   "ביטול",
}

# English summaries for each article
_ARTICLE_SUMMARIES = {
    "01":   "Definitions for the Framework Order — all terms used in customs tariff supplements.",
    "02":   "Nature of the First and Second Supplements — tariff structure, columns, purchase tax.",
    "03":   "Classification of goods in the First Supplement — GIR rules 1-6 (Hebrew version of WCO rules).",
    "04":   "Additional Israeli rule — goods classifiable in chapters 98-99 vs chapters 1-97.",
    "05":   "Subdivision of items in the First Supplement — subheadings and sub-items numbering system.",
    "06":   "Conditional items (פרט מותנה) — special declaration required, conditions, time limits, penalties.",
    "06א":  "Recycling and disposal of fuel products under conditional exemption.",
    "07":   "Wholesale price determination for locally manufactured goods.",
    "08":   "Wholesale price determination for cigarettes and tobacco products.",
    "09":   "Goods excluded from the Law's supplement — specific HS codes still subject to purchase tax.",
    "10":   "Definition of manufacturing operations — which processing constitutes 'manufacturing' for tax.",
    "11":   "Customs duty and tax rate rules — ad valorem vs specific, CPI adjustment, weight calculation.",
    "12":   "Tax amount adjustment — CPI-linked automatic adjustment for specific HS codes.",
    "13":   "Reduction amount adjustment — CPI-linked for chapter 87 vehicle reductions.",
    "14":   "Trade agreements — general rules for FTA preference eligibility and documentation requirements.",
    "15":   "Agricultural quotas — WTO quota system for agricultural products.",
    "16":   "Customs reduction for USA FTA — full exemption under Israel-USA FTA.",
    "17":   "Customs reduction for EU FTA — exemption with exceptions for chapters 1-24 and specific items.",
    "18":   "Customs reduction for EFTA — exemption with exceptions per the Fifth Supplement.",
    "19":   "Customs reduction for Canada FTA — exemption with exceptions per the Sixth Supplement.",
    "20":   "Customs reduction for Jordan FTA — graduated reduction per the Seventh Supplement.",
    "21":   "Customs reduction for Turkey FTA — exemption with exceptions per the Eighth Supplement.",
    "22":   "Customs reduction for Mexico FTA — exemption with exceptions per the Ninth Supplement.",
    "23":   "Customs reduction for Mercosur FTA — exemption with graduated phase-in per Tenth Supplement.",
    "23א":  "Customs reduction for Panama FTA — graduated reduction per the Fourteenth Supplement.",
    "23ב":  "Customs reduction for Colombia FTA — graduated reduction per the Fifteenth Supplement.",
    "23ג":  "Customs reduction for Ukraine FTA — graduated reduction per the Sixteenth Supplement.",
    "23ד":  "Customs reduction for UK FTA — exemption with exceptions per the Seventeenth Supplement.",
    "23ה":  "Customs reduction for Korea FTA — graduated reduction per the Eighteenth Supplement.",
    "23ו":  "Customs reduction for UAE FTA — graduated reduction per the Nineteenth Supplement.",
    "23ז":  "Customs reduction for Guatemala FTA — exemption with exceptions per the Twentieth Supplement.",
    "24":   "Repealed.",
    "25":   "Repeal of previous Framework Order and transitional provisions.",
}

# Map article IDs to FTA countries (for cross-referencing)
_FTA_ARTICLES = {
    "16": "USA",
    "17": "EU",
    "18": "EFTA",
    "19": "Canada",
    "20": "Jordan",
    "21": "Turkey",
    "22": "Mexico",
    "23": "Mercosur",
    "23א": "Panama",
    "23ב": "Colombia",
    "23ג": "Ukraine",
    "23ד": "UK",
    "23ה": "Korea",
    "23ו": "UAE",
    "23ז": "Guatemala",
}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _load_text(path=None):
    """Load and clean the framework order text file."""
    path = path or _DEFAULT_PATH
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Only non-empty lines
    content_lines = [l.strip() for l in lines if l.strip()]

    # Join into one text blob
    full_text = "  ".join(content_lines)

    # Remove page footers
    full_text = _RE_PAGE_FOOTER.sub("", full_text)

    # Collapse multiple spaces
    full_text = re.sub(r' {3,}', '  ', full_text)

    return full_text


def _find_article_boundaries(text):
    """Find all article start positions in the text.
    Returns list of (position, article_id, raw_title) sorted by position.

    Strategy: Title-anchored search — for each known article, search for its
    specific title string followed by its 2-digit number. This avoids false
    positives from footnote references like "( 10 )" at the end of the document.

    Text format:
      Main articles:  ( TITLE NUMBER     e.g., ( הגדרות 01
      Sub-articles:   SUFFIX( TITLE NUMBER  e.g., א( מיחזור ... 06
      Special case:   ז( 23  (article 23ז has no title in text)
    """
    # Title anchors — first significant Hebrew word(s) for each article
    # These are unique enough to avoid false positives in the definitions section
    _TITLE_ANCHORS = {
        "01":   "הגדרות",
        "02":   "מהות התוספות",
        "03":   "סיווג טובין",
        "04":   "הוראה נוספת",
        "05":   "חלוקת פרט",
        "06":   "פרט מותנה",
        "06א":  "מיחזור",
        "07":   "המחיר הסיטוני בייצור",
        "08":   "המחיר הסיטוני לסיגריות",
        "09":   "טובין הממועטים",
        "10":   "קביעת פעולת",
        "11":   "שיעור המכס",
        "12":   "תיאום סכומי מס",
        "13":   "תיאום סכומי הפחתות",
        "14":   "הסכמי סחר",
        "15":   "מכסות חקלאיות",
        "16":   "הפחתת מכס לענין הסכמי הסחר עם",
        "17":   "הפחתת המכס לעניין הסכם הסחר עם האיחוד",
        "18":   "הפחתת מכס לענין ארצות אפט",
        "19":   "הפחתת מכס לעניין הסכם הסחר עם קנדה",
        "20":   "הפחתת מכס לענין הסכם הסחר עם ירדן",
        "21":   "הפחתת מכס לענין הסכם הסחר עם טורקיה",
        "22":   "הפחתת מכס לענין סחר עם מקסיקו",
        "23":   "הפחתת מכס לעניין ארצות מרקוסור",
        "23א":  "הפחתת מכס לעניין הסכם הסחר עם פנמה",
        "23ב":  "הפחתת מכס לעניין הסכם הסחר עם קולומביה",
        "23ג":  "הפחתת מכס לעניין הסכם הסחר עם אוקראינה",
        "23ד":  "הפחתת מכס לענין הסכם הסחר עם הממלכה",
        "23ה":  "הפחתת מכס לעניין הסכם הסחר עם הרפובליקה",
        "23ו":  "הפחתת מכס לענין הסכם הסחר עם איחוד האמירויות",
        "23ז":  "",  # no title in text — appears as just "ז( 23"
        "24":   "בטל",
        "25":   "ביטול",
    }

    boundaries = []

    for article_id, anchor in _TITLE_ANCHORS.items():
        num = re.match(r'(\d+)', article_id).group(1).zfill(2)
        # Extract Hebrew letter suffix (e.g., "23א" -> "א", "06" -> "")
        suffix = re.sub(r'^\d+', '', article_id)

        if suffix:
            # Sub-article: search for SUFFIX( TITLE... NUMBER
            if anchor:
                first_word = anchor.split()[0]
                pattern = re.compile(
                    re.escape(suffix) + r'\(?\s*' + re.escape(first_word)
                    + r'.{0,100}?\s+' + num + r'\b'
                )
            else:
                # 23ז has no title — just "ז( 23"
                pattern = re.compile(
                    re.escape(suffix) + r'\(\s*' + num + r'\b'
                )
        else:
            # Main article: search for ( TITLE... NUMBER
            first_word = anchor.split()[0]
            pattern = re.compile(
                r'\(\s*' + re.escape(first_word)
                + r'.{0,100}?\s+' + num + r'\b'
            )

        found = list(pattern.finditer(text))

        # For articles > 01, skip matches in definitions section (< pos 6000)
        if found and article_id != "01":
            after_defs = [m for m in found if m.start() > 6000]
            if after_defs:
                found = after_defs

        if found:
            m = found[0]
            boundaries.append((m.start(), article_id, anchor))

    boundaries.sort(key=lambda x: x[0])
    return boundaries


def _extract_articles(text, boundaries):
    """Extract full text for each article based on boundaries."""
    articles = OrderedDict()

    for i, (pos, article_id, raw_title) in enumerate(boundaries):
        # Text runs from this boundary to the next
        if i + 1 < len(boundaries):
            next_pos = boundaries[i + 1][0]
        else:
            next_pos = len(text)

        article_text = text[pos:next_pos].strip()

        # Clean up: remove the article header pattern from the start
        # The header is "SUFFIX( TITLE NUMBER" — remove it
        # Allow parens in title (e.g., "הוראה נוספת )ישראלית(")
        header_match = re.match(
            r'[א-ת]?\(?\s*.{0,120}?\s+\d{2}\s*', article_text
        )
        if header_match:
            article_text = article_text[header_match.end():].strip()

        # Get canonical title
        title = _ARTICLE_TITLES.get(article_id, raw_title)
        summary = _ARTICLE_SUMMARIES.get(article_id, "")

        # Determine FTA country if applicable
        fta_country = _FTA_ARTICLES.get(article_id)

        entry = {
            "t": title,
            "s": summary,
            "f": article_text,
        }

        if fta_country:
            entry["fta"] = fta_country

        if article_id in ("24",):
            entry["repealed"] = True

        articles[article_id] = entry

    return articles


def parse_framework_order(path=None):
    """Main entry: parse the framework order text file and return articles dict."""
    text = _load_text(path)
    boundaries = _find_article_boundaries(text)
    articles = _extract_articles(text, boundaries)
    return articles


# ---------------------------------------------------------------------------
# Code generator
# ---------------------------------------------------------------------------

def _generate_python_module(articles):
    """Generate _framework_order_data.py content."""
    lines = []
    lines.append('"""')
    lines.append("Framework Order (צו מסגרת) articles data.")
    lines.append(f"Generated from framework_order_text.txt ({len(articles)} articles).")
    lines.append("")
    lines.append("Fields per article:")
    lines.append('  t   — Hebrew title')
    lines.append('  s   — English summary')
    lines.append('  f   — full Hebrew text from the Framework Order')
    lines.append('  fta — FTA country code (for articles 16-23ז)')
    lines.append('  repealed — True if article was repealed')
    lines.append('"""')
    lines.append("")
    lines.append("")

    # Article metadata
    lines.append("# All articles, keyed by article number (string).")
    lines.append("FRAMEWORK_ORDER_ARTICLES = {")

    for article_id, data in articles.items():
        title = data["t"]
        summary = data["s"]
        full_text = data["f"]
        fta = data.get("fta")
        repealed = data.get("repealed", False)

        lines.append(f'    {article_id!r}: {{')
        lines.append(f'        "t": {title!r},')
        lines.append(f'        "s": {summary!r},')
        lines.append(f'        "f": {full_text!r},')

        if fta:
            lines.append(f'        "fta": {fta!r},')
        if repealed:
            lines.append(f'        "repealed": True,')

        lines.append(f'    }},')

    lines.append("}")
    lines.append("")

    # Total stats
    total_chars = sum(len(d["f"]) for d in articles.values())
    lines.append(f"# Total: {len(articles)} articles, {total_chars:,} chars of Hebrew text")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]

    path = _DEFAULT_PATH
    if not os.path.exists(path):
        # Try relative to script
        alt_path = os.path.join(_SCRIPT_DIR, "..", "data_c3", "framework_order_text.txt")
        if os.path.exists(alt_path):
            path = alt_path
        else:
            print(f"ERROR: Source file not found at {path}")
            sys.exit(1)

    articles = parse_framework_order(path)

    if "--json" in args:
        print(json.dumps(articles, ensure_ascii=False, indent=2))
        return

    if "--stats" in args:
        print(f"Articles found: {len(articles)}")
        total_chars = 0
        for aid, data in articles.items():
            text_len = len(data["f"])
            total_chars += text_len
            fta = f" [FTA: {data['fta']}]" if data.get("fta") else ""
            rep = " [REPEALED]" if data.get("repealed") else ""
            print(f"  {aid:6s} | {text_len:6,} chars | {data['t']}{fta}{rep}")
        print(f"\nTotal: {total_chars:,} chars of Hebrew text")
        return

    if "--article" in args:
        idx = args.index("--article")
        if idx + 1 < len(args):
            target = args[idx + 1]
            if target in articles:
                data = articles[target]
                print(f"Article {target}: {data['t']}")
                print(f"Summary: {data['s']}")
                if data.get("fta"):
                    print(f"FTA: {data['fta']}")
                print(f"\n{data['f'][:3000]}")
            else:
                print(f"Article {target} not found. Available: {', '.join(articles.keys())}")
        return

    # Default: generate Python module
    output_path = os.path.join(_SCRIPT_DIR, "lib", "_framework_order_data.py")
    content = _generate_python_module(articles)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated {output_path}")
    print(f"  {len(articles)} articles")
    total = sum(len(d["f"]) for d in articles.values())
    print(f"  {total:,} chars of Hebrew text")


if __name__ == "__main__":
    main()
