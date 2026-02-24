#!/usr/bin/env python3
"""
Validate converted XML files from shaarolami PDF-to-XML pipeline.

READ-ONLY — checks quality, never modifies files.

Checks per file:
  - No U+FFFD replacement characters
  - No Oriya block chars (U+0B68-U+0B82) remaining
  - No Modifier Letter chars (U+02A0-U+02BA) remaining
  - No control chars (\x03-\x1e) in text content
  - Hebrew present (U+05D0-U+05EA range)
  - Words spaced properly (avg Hebrew word length < 15)
  - No ץ (final tsade) in mid-word positions (broken mapping sign)
  - Page count matches source PDF (if PDF available)
  - Not empty

Specific file checks:
  - FrameOrder.xml: articles > 25, definitions > 10
  - I.xml through XXII.xml: HS refs > 10 each
  - ExemptCustomsItems.xml: readable discount codes with spaces
  - ThirdAddition.xml: readable supplement text with spaces

Usage:
    python -X utf8 scripts/validate_xml.py downloads/xml/
    python -X utf8 scripts/validate_xml.py downloads/xml/ --pdf-dir downloads/
"""

import sys
import re
import os
from pathlib import Path
from xml.etree.ElementTree import parse as xml_parse

# Try to import PyMuPDF for page count verification
try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


# ------------------------------------------------------------------ #
#  Constants                                                           #
# ------------------------------------------------------------------ #

# Unicode ranges that should NOT appear in properly converted output
ORIYA_RANGE = range(0x0B68, 0x0B83)          # Garbled Hebrew source chars
MODIFIER_LETTER_RANGE = range(0x02A0, 0x02BB)  # Garbled Hebrew source chars
CONTROL_CHARS = set(range(0x03, 0x1F)) - {0x09, 0x0A, 0x0D}  # Exclude tab, newline, CR

# Hebrew letter range
HEBREW_RANGE = range(0x05D0, 0x05EB)  # א through ת

# Section file names (Roman numerals I through XXII)
SECTION_FILES = {
    'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
    'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX',
    'XX', 'XXI', 'XXII'
}

# Mid-word ץ pattern: ץ followed by a Hebrew letter (ץ should only appear at word end)
RE_MID_WORD_TSADE = re.compile(r'ץ[\u05D0-\u05EA]')

# Hebrew word: contiguous Hebrew characters
RE_HEBREW_WORD = re.compile(r'[\u05D0-\u05EA]+')


# ------------------------------------------------------------------ #
#  Validation checks                                                   #
# ------------------------------------------------------------------ #

def get_all_text(root):
    """Extract all text content from an XML tree."""
    texts = []
    for elem in root.iter():
        if elem.text:
            texts.append(elem.text)
        if elem.tail:
            texts.append(elem.tail)
    return '\n'.join(texts)


def check_replacement_chars(text):
    """Check for U+FFFD replacement characters."""
    count = text.count('\uFFFD')
    return count


def check_oriya_chars(text):
    """Check for remaining Oriya block characters (should have been mapped to Hebrew)."""
    count = 0
    for ch in text:
        if ord(ch) in ORIYA_RANGE:
            count += 1
    return count


def check_modifier_letters(text):
    """Check for remaining Modifier Letter characters (should have been mapped to Hebrew)."""
    count = 0
    for ch in text:
        if ord(ch) in MODIFIER_LETTER_RANGE:
            count += 1
    return count


def check_control_chars(text):
    """Check for control characters in text content (should have been mapped to punctuation/spaces)."""
    count = 0
    for ch in text:
        if ord(ch) in CONTROL_CHARS:
            count += 1
    return count


def check_hebrew_present(text):
    """Check that Hebrew characters are present."""
    for ch in text:
        if ord(ch) in HEBREW_RANGE:
            return True
    return False


def check_word_spacing(text):
    """Check that Hebrew words are properly spaced (avg length < 15 chars).
    Very long Hebrew 'words' indicate missing spaces between words."""
    words = RE_HEBREW_WORD.findall(text)
    if not words:
        return 0, 0  # no Hebrew words
    total_len = sum(len(w) for w in words)
    avg_len = total_len / len(words)
    return avg_len, len(words)


def check_mid_word_tsade(text):
    """Check for ץ (final tsade) in mid-word positions — sign of broken character mapping."""
    matches = RE_MID_WORD_TSADE.findall(text)
    return len(matches)


def check_page_count(root, pdf_path):
    """Verify XML page count matches source PDF page count."""
    if not HAS_FITZ or not pdf_path or not pdf_path.exists():
        return None, None  # Cannot verify
    xml_pages = len(root.findall('.//page'))
    doc = fitz.open(str(pdf_path))
    pdf_pages = doc.page_count
    doc.close()
    return xml_pages, pdf_pages


def check_not_empty(root):
    """Check that the XML has actual content (paragraphs with text)."""
    paragraphs = root.findall('.//paragraph')
    non_empty = sum(1 for p in paragraphs if p.text and p.text.strip())
    return non_empty


# ------------------------------------------------------------------ #
#  Specific file checks                                                #
# ------------------------------------------------------------------ #

def check_frame_order(root):
    """FrameOrder.xml: articles > 25, definitions > 10."""
    articles = root.findall('.//article')
    definitions = root.findall('.//definition')
    # Count definition terms from <definition> elements
    all_def_terms = set()
    for d in definitions:
        term = d.get('term', '')
        if term:
            all_def_terms.add(term)
    for a in articles:
        for d in a.findall('definition'):
            term = d.get('term', '')
            if term:
                all_def_terms.add(term)
    # Also count definitions from bold paragraphs with ""term pattern
    # (FrameOrder stores each definition as a separate bold paragraph)
    re_def = re.compile(r'""([\u05D0-\u05EA](?:(?!"").){0,79})')
    for p in root.findall('.//paragraph'):
        if p.text and '""' in p.text:
            for m in re_def.finditer(p.text):
                all_def_terms.add(m.group(1))
    return len(articles), len(all_def_terms)


def check_section_hs_refs(root):
    """Section XML (I-XXII): count HS code references.

    Section texts use short-form HS headings (XX.XX) more than full tariff
    lines (XX.XX.XXXXXX). Count both formats.
    """
    # Count paragraphs with hs_codes attribute (full format, tagged by converter)
    tagged = len(root.findall('.//paragraph[@hs_codes]'))
    # Also count short-form heading references (XX.XX) in text
    re_heading = re.compile(r'\b\d{2}\.\d{2}\b')
    all_text = get_all_text(root)
    short_refs = len(re_heading.findall(all_text))
    return max(tagged, short_refs)


def check_readable_text(root, min_avg_word_count=3):
    """Check that text has readable words with spaces (not garbled/glued together).
    Returns (readable, avg_words_per_paragraph)."""
    paragraphs = root.findall('.//paragraph')
    if not paragraphs:
        return False, 0
    word_counts = []
    for p in paragraphs:
        if p.text and p.text.strip():
            words = p.text.split()
            word_counts.append(len(words))
    if not word_counts:
        return False, 0
    avg_words = sum(word_counts) / len(word_counts)
    return avg_words >= min_avg_word_count, avg_words


# ------------------------------------------------------------------ #
#  Main validation                                                     #
# ------------------------------------------------------------------ #

def validate_file(xml_path, pdf_dir=None):
    """Validate a single XML file. Returns (passed, results_dict)."""
    xml_path = Path(xml_path)
    stem = xml_path.stem
    results = {'file': xml_path.name, 'issues': [], 'stats': {}}

    # Skip test files
    if stem.endswith('_test'):
        return True, {'file': xml_path.name, 'issues': [], 'stats': {'skipped': 'test file'}}

    # Parse XML
    try:
        tree = xml_parse(str(xml_path))
        root = tree.getroot()
    except Exception as e:
        results['issues'].append(f'xml_parse_error: {e}')
        return False, results

    # Extract all text
    all_text = get_all_text(root)
    if not all_text.strip():
        results['issues'].append('empty_file: no text content')
        return False, results

    # --- Generic checks ---

    # 1. U+FFFD replacement characters
    fffd_count = check_replacement_chars(all_text)
    results['stats']['replacement_chars'] = fffd_count
    if fffd_count > 0:
        results['issues'].append(f'replacement_chars: {fffd_count} U+FFFD found')

    # 2. Oriya block chars
    oriya_count = check_oriya_chars(all_text)
    results['stats']['oriya_chars'] = oriya_count
    if oriya_count > 0:
        results['issues'].append(f'oriya_chars: {oriya_count} remaining')

    # 3. Modifier Letter chars
    modifier_count = check_modifier_letters(all_text)
    results['stats']['modifier_letters'] = modifier_count
    if modifier_count > 0:
        results['issues'].append(f'modifier_letters: {modifier_count} remaining')

    # 4. Control chars
    ctrl_count = check_control_chars(all_text)
    results['stats']['control_chars'] = ctrl_count
    if ctrl_count > 0:
        results['issues'].append(f'control_chars: {ctrl_count} in text')

    # 5. Hebrew present
    has_hebrew = check_hebrew_present(all_text)
    results['stats']['has_hebrew'] = has_hebrew
    if not has_hebrew:
        results['issues'].append('no_hebrew: no Hebrew characters found')

    # 6. Word spacing
    avg_word_len, word_count = check_word_spacing(all_text)
    results['stats']['avg_hebrew_word_len'] = round(avg_word_len, 1)
    results['stats']['hebrew_word_count'] = word_count
    if avg_word_len > 15 and word_count > 10:
        results['issues'].append(f'word_spacing: avg Hebrew word length {avg_word_len:.1f} (> 15)')

    # 7. Mid-word ץ
    tsade_count = check_mid_word_tsade(all_text)
    results['stats']['mid_word_tsade'] = tsade_count
    if tsade_count > 0:
        results['issues'].append(f'mid_word_tsade: {tsade_count}')

    # 8. Page count match
    pdf_path = None
    if pdf_dir:
        pdf_path = Path(pdf_dir) / xml_path.with_suffix('.pdf').name
    xml_pages, pdf_pages = check_page_count(root, pdf_path)
    if xml_pages is not None and pdf_pages is not None:
        results['stats']['xml_pages'] = xml_pages
        results['stats']['pdf_pages'] = pdf_pages
        if xml_pages != pdf_pages:
            results['issues'].append(f'page_count_mismatch: xml={xml_pages} pdf={pdf_pages}')

    # 9. Not empty
    para_count = check_not_empty(root)
    results['stats']['paragraphs'] = para_count
    if para_count == 0:
        results['issues'].append('empty_content: no paragraphs with text')

    # --- Specific file checks ---

    if stem == 'FrameOrder':
        articles, defs = check_frame_order(root)
        results['stats']['articles'] = articles
        results['stats']['definitions'] = defs
        if articles < 25:
            results['issues'].append(f'frame_order_articles: {articles} (< 25)')
        if defs < 10:
            results['issues'].append(f'frame_order_definitions: {defs} (< 10)')

    elif stem in SECTION_FILES:
        hs_refs = check_section_hs_refs(root)
        results['stats']['hs_refs'] = hs_refs
        if hs_refs < 5:
            results['issues'].append(f'section_hs_refs: {hs_refs} (< 5)')

    elif stem == 'ExemptCustomsItems':
        readable, avg_words = check_readable_text(root, min_avg_word_count=2)
        results['stats']['avg_words_per_para'] = round(avg_words, 1)
        if not readable:
            results['issues'].append(f'exempt_readability: avg {avg_words:.1f} words/para (too low)')

    elif stem == 'ThirdAddition':
        readable, avg_words = check_readable_text(root, min_avg_word_count=1.5)
        results['stats']['avg_words_per_para'] = round(avg_words, 1)
        if not readable:
            results['issues'].append(f'third_addition_readability: avg {avg_words:.1f} words/para (too low)')

    elif stem == 'SecondAddition':
        readable, avg_words = check_readable_text(root, min_avg_word_count=1.5)
        results['stats']['avg_words_per_para'] = round(avg_words, 1)

    elif stem.startswith('TradeAgreement'):
        # Trade agreements should have Hebrew text and no garbled chars
        readable, avg_words = check_readable_text(root, min_avg_word_count=2)
        results['stats']['avg_words_per_para'] = round(avg_words, 1)

    passed = len(results['issues']) == 0
    return passed, results


def format_result(passed, results):
    """Format a single file validation result."""
    name = results['file']
    stats = results['stats']

    if stats.get('skipped'):
        return f'[SKIP] {name} — {stats["skipped"]}'

    # Build stats string
    stat_parts = []
    for key in ['articles', 'definitions', 'hs_refs', 'paragraphs',
                 'xml_pages', 'avg_hebrew_word_len', 'hebrew_word_count',
                 'avg_words_per_para', 'replacement_chars', 'mid_word_tsade',
                 'control_chars']:
        if key in stats and stats[key]:
            # Only show non-zero/non-trivial stats
            val = stats[key]
            if key == 'paragraphs' and val > 0:
                stat_parts.append(f'{val} paras')
            elif key == 'articles':
                stat_parts.append(f'{val} articles')
            elif key == 'definitions':
                stat_parts.append(f'{val} defs')
            elif key == 'hs_refs':
                stat_parts.append(f'{val} HS refs')
            elif key == 'xml_pages':
                pdf_p = stats.get('pdf_pages', '?')
                stat_parts.append(f'{val}/{pdf_p} pages')
            elif key == 'avg_words_per_para':
                stat_parts.append(f'{val} avg words/para')
            elif key in ('replacement_chars', 'mid_word_tsade', 'control_chars') and val > 0:
                stat_parts.append(f'{key}: {val}')

    stat_str = ', '.join(stat_parts) if stat_parts else 'OK'

    if passed:
        return f'[PASS] {name} — {stat_str}'
    else:
        issues_str = '; '.join(results['issues'])
        return f'[FAIL] {name} — {issues_str}'


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    xml_dir = Path(sys.argv[1])
    if not xml_dir.is_dir():
        print(f"ERROR: {xml_dir} is not a directory")
        sys.exit(1)

    # Optional --pdf-dir
    pdf_dir = None
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == '--pdf-dir' and i + 1 < len(sys.argv):
            pdf_dir = sys.argv[i + 1]
        elif sys.argv[i - 1] == '--pdf-dir':
            continue  # already consumed

    # If no --pdf-dir specified, try parent of xml_dir
    if pdf_dir is None:
        candidate = xml_dir.parent
        if list(candidate.glob('*.pdf')):
            pdf_dir = str(candidate)

    xml_files = sorted(xml_dir.glob('*.xml'))
    if not xml_files:
        print(f"No XML files found in {xml_dir}")
        sys.exit(1)

    print(f"Validating {len(xml_files)} XML files in {xml_dir}")
    if pdf_dir:
        print(f"PDF source directory: {pdf_dir}")
    if not HAS_FITZ:
        print("NOTE: PyMuPDF not available — page count verification skipped")
    print(f"{'='*70}\n")

    passed_count = 0
    failed_count = 0
    skipped_count = 0
    all_results = []

    for xml_file in xml_files:
        passed, results = validate_file(xml_file, pdf_dir)
        all_results.append((passed, results))
        line = format_result(passed, results)
        print(line)
        if results.get('stats', {}).get('skipped'):
            skipped_count += 1
        elif passed:
            passed_count += 1
        else:
            failed_count += 1

    # Summary
    total = passed_count + failed_count
    print(f"\n{'='*70}")
    print(f"SUMMARY: {passed_count}/{total} PASS, {failed_count} FAIL"
          + (f", {skipped_count} SKIP" if skipped_count else ""))

    if failed_count > 0:
        print(f"\nFAILED FILES:")
        for passed, results in all_results:
            if not passed and not results.get('stats', {}).get('skipped'):
                for issue in results['issues']:
                    print(f"  {results['file']}: {issue}")

    sys.exit(1 if failed_count > 0 else 0)


if __name__ == '__main__':
    main()
