#!/usr/bin/env python3
"""
PDF -> Structured XML Converter for Israeli Customs Documents.

Converts PDF documents to structured XML preserving:
- Full text content (Hebrew RTL)
- Document structure (articles, sections, definitions, tables)
- Font metadata (bold, italic, size) for semantic analysis
- Page numbers and source location metadata
- HS code cross-references tagged inline

Usage:
    python pdf_to_xml.py <input.pdf> [output.xml]
    python pdf_to_xml.py --batch <directory> [output_dir]
"""

import sys
import re
import hashlib
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring, indent

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install pymupdf")
    sys.exit(1)


# ------------------------------------------------------------------ #
#  Garbled Hebrew fix (broken ToUnicode CMap in embedded fonts)        #
#  Session 62 discovery: two character substitution mappings fix ALL   #
#  garbled Hebrew from shaarolami PDFs (supplements 3-19, etc.)       #
# ------------------------------------------------------------------ #

_GARBLED_TO_HEBREW = {}
for _i in range(27):  # Mapping 1: Modifier Letters U+02A0..U+02BA → Hebrew U+05D0..U+05EA
    _GARBLED_TO_HEBREW[chr(0x02A0 + _i)] = chr(0x05D0 + _i)
for _cp in range(0x0B68, 0x0B83):  # Mapping 2: Oriya block → Hebrew (offset -0x0598)
    _dst = _cp - 0x0598              # Verified: U+0B68→א(U+05D0), U+0B82→ת(U+05EA)
    if 0x05D0 <= _dst <= 0x05EA:
        _GARBLED_TO_HEBREW[chr(_cp)] = chr(_dst)
_GARBLED_TRANS = str.maketrans(_GARBLED_TO_HEBREW)

# Control characters used as punctuation/spacing in garbled PDF fonts.
# These are CID-mapped chars that don't go through ToUnicode properly.
# Verified by comparing known text against raw PDF output.
_CTRL_CHAR_MAP = {
    '\x03': ' ',    # ETX → space (word separator, 891 occurrences in ExemptCustomsItems)
    '\x05': '״',    # ENQ → gershayim (Hebrew double-quote for abbreviations like תשי"ז)
    '\x0b': '(',    # VT  → open parenthesis
    '\x0c': ')',    # FF  → close parenthesis
    '\x0f': ',',    # SI  → comma
    '\x10': '-',    # DLE → hyphen/dash
    '\x11': ')',    # DC1 → close parenthesis (alternate)
    '\x1d': ':',    # GS  → colon
    '\x1e': ';',    # RS  → semicolon
}
_CTRL_TRANS = str.maketrans(_CTRL_CHAR_MAP)


def fix_garbled_hebrew(text):
    """Fix garbled Hebrew caused by broken ToUnicode CMap in PDF fonts.

    Three-step process:
    1. Translate garbled Unicode chars (Modifier Letters / Oriya) to Hebrew
    2. Replace control characters with their intended punctuation/spaces
    3. Reverse Hebrew words from visual (LTR) to logical (RTL) order
    """
    fixed = text.translate(_GARBLED_TRANS)
    if fixed == text:
        return text  # No garbled chars found, return as-is
    # Replace control chars with punctuation/spaces
    fixed = fixed.translate(_CTRL_TRANS)
    # Text was garbled → it's in visual LTR order. Reverse Hebrew words.
    return _fix_rtl_visual_order(fixed)


def _fix_rtl_visual_order(text):
    """Reverse Hebrew character runs from visual to logical order.

    In visual-order PDFs, the Hebrew word "שלום" is stored as "םולש".
    This function reverses contiguous runs of Hebrew characters while
    preserving non-Hebrew characters (digits, punctuation, Latin) in place.
    """
    # Process each line independently
    result_lines = []
    for line in text.split('\n'):
        result_lines.append(_reverse_hebrew_runs(line))
    return '\n'.join(result_lines)


def _reverse_hebrew_runs(line):
    """Reverse Hebrew character runs within a single line."""
    # Split line into segments: Hebrew runs and non-Hebrew runs
    segments = []
    current = []
    current_is_hebrew = False

    for ch in line:
        is_heb = '\u05D0' <= ch <= '\u05EA'
        if current and is_heb != current_is_hebrew:
            segments.append((''.join(current), current_is_hebrew))
            current = []
        current.append(ch)
        current_is_hebrew = is_heb

    if current:
        segments.append((''.join(current), current_is_hebrew))

    # Reverse Hebrew segments and reverse the overall order of segments
    # that form a Hebrew-dominant line
    hebrew_count = sum(len(s) for s, h in segments if h)
    total_count = sum(len(s) for s, _ in segments)

    if hebrew_count > total_count * 0.3:
        # Hebrew-dominant line: reverse segment order and reverse Hebrew runs
        parts = []
        for seg_text, is_heb in reversed(segments):
            if is_heb:
                parts.append(seg_text[::-1])
            else:
                parts.append(seg_text)
        return ''.join(parts)
    else:
        # Non-Hebrew-dominant line: just reverse Hebrew runs in place
        parts = []
        for seg_text, is_heb in segments:
            if is_heb:
                parts.append(seg_text[::-1])
            else:
                parts.append(seg_text)
        return ''.join(parts)


# ------------------------------------------------------------------ #
#  Hebrew document structure patterns                                  #
# ------------------------------------------------------------------ #

# Framework Order article: "( title_textNN" where NN is 1-3 digits
# Hebrew numbering: the number comes BEFORE the closing paren
# Pattern matches: "( הגדרות01" or "א( מיחזור06" or "( קביעת פעולת ייצור10"
# But NOT HS codes like "24.04.111100"
RE_ARTICLE_HEB = re.compile(
    r'^\s*'                          # optional leading whitespace
    r'(?:[א-ת]+\s*)?'               # optional Hebrew suffix before paren
    r'\('                            # opening paren
    # The rest is the article body - we extract the trailing number
)
# Trailing article number at the end of the first line/block start
RE_ARTICLE_NUM_TRAIL = re.compile(r'(\d{1,3}[א-ת]?)\s*$')

# Standard article numbering: "(NN)" at start
RE_ARTICLE_PAREN = re.compile(r'^\s*\((\d{1,3}[א-ת]?)\)')

# Sub-article: ")א(" or ")ב(" etc
RE_SUB_ARTICLE = re.compile(r'^\s*\)([א-ת])\(')

# Section/supplement headers (bold, specific words)
RE_SECTION_HEADER = re.compile(r'^(חלק|פרק|סימן)\s+')
RE_SUPPLEMENT = re.compile(
    r'תוספת\s+(ראשונה|שנייה|שניה|שלישית|רביעית|חמישית|שישית|'
    r'שביעית|שמינית|תשיעית|עשירית|\d+)'
)

# Definition: ""TERM at end of text block — RTL format in the צו מסגרת
# In the PDF text (which is visual RTL), the pattern is:
#   ;definition body text ""TERM
# where "" is two ASCII double-quotes (U+0022) immediately followed by
# the Hebrew term text. The term may include spaces, quotes, and punctuation.
# Terms can contain single " for abbreviations (e.g., ארה"ב, מע"מ, אל"י)
# so we only stop at "" (next definition start) or end of text.
# Examples: '""דולר', '""הסכם סחר', '""ארה"ב', '""מערכת חלקים'
RE_DEFINITION_TERM = re.compile(r'""([א-ת](?:(?!""").){0,79})')

# HS code pattern: XX.XX.XXXXXX (6-10 digit with dots)
RE_HS_CODE = re.compile(r'\b\d{2}\.\d{2}\.\d{4,6}\b')

# Page footer: "11/07/2024  הודפס בתאריך1  עמוד"
RE_PAGE_FOOTER = re.compile(
    r'^\s*\d{2}/\d{2}/\d{4}\s+הודפס בתאריך\s*\d+\s+עמוד\s*$'
)

# Amendment marker
RE_AMENDMENT = re.compile(r'\(\s*תיקון\s+.*?\)')


# ------------------------------------------------------------------ #
#  PDF block extraction                                                #
# ------------------------------------------------------------------ #

class PDFBlock:
    """Text block from a PDF page with font/position metadata."""
    __slots__ = ('text', 'fonts', 'sizes', 'bbox', 'page_num',
                 'is_bold', 'max_size')

    def __init__(self, text, fonts, sizes, bbox, page_num, is_bold=False):
        self.text = text.strip()
        self.fonts = fonts
        self.sizes = sizes
        self.bbox = bbox
        self.page_num = page_num
        self.is_bold = is_bold
        self.max_size = max(sizes) if sizes else 0


def extract_page_blocks(doc, page_idx):
    """Extract text blocks from one PDF page."""
    page = doc[page_idx]
    # NOTE: Do NOT use fitz.TEXT_PRESERVE_WHITESPACE — it causes PyMuPDF to
    # return U+FFFD for garbled Hebrew fonts instead of the mappable Oriya chars
    raw = page.get_text('dict')
    out = []
    for blk in raw['blocks']:
        if blk['type'] != 0:
            continue
        lines_text = []
        fonts = set()
        sizes = set()
        bold = False
        for line in blk['lines']:
            lt = ''
            for span in line['spans']:
                lt += fix_garbled_hebrew(span['text'])
                fonts.add(span['font'])
                sizes.add(span['size'])
                if 'Bold' in span['font'] or 'bold' in span['font'].lower():
                    bold = True
            lines_text.append(lt)
        text = '\n'.join(lines_text)
        if not text.strip():
            continue
        bbox = tuple(blk['bbox'])
        out.append(PDFBlock(text, fonts, sizes, bbox, page_idx + 1, bold))
    return out


# ------------------------------------------------------------------ #
#  Semantic classification                                             #
# ------------------------------------------------------------------ #

def _is_article_start(text):
    """
    Detect Hebrew article numbering in the צו מסגרת format.

    The pattern is: "( TITLE_TEXT NN" where NN trails at end.
    Examples:
        "( הגדרות01"  -> article 1 (definitions)
        "א( מיחזור וסילוק מוצרי דלק בפטור מותנה06"  -> article 6א
        "( המחיר הסיטוני בייצור מקומי07"  -> article 7
        "( קביעת פעולת ייצור10"  -> article 10

    Must NOT match HS codes like "24.02.902000" or lines starting with
    HS-code numbers.
    """
    # Skip if starts with an HS code
    if RE_HS_CODE.match(text.strip()):
        return None

    # Pattern 1: Number at end of short text with Hebrew, containing paren
    # This is the צו מסגרת numbering style
    first_line = text.split('\n')[0].strip()
    if len(first_line) < 120 and '(' in first_line:
        m = RE_ARTICLE_NUM_TRAIL.search(first_line)
        if m:
            num = m.group(1)
            # Sanity: article numbers in צו מסגרת are 1-33, not 24, 85 etc
            # But we need to be flexible for other documents
            # Just exclude obvious HS-like patterns
            if '.' not in first_line[:10]:  # No dots near start = not HS code
                return num

    # Pattern 2: Standard "(NN)" at start
    m = RE_ARTICLE_PAREN.match(text)
    if m:
        return m.group(1)

    return None


def classify_block(block):
    """Classify a text block's semantic role."""
    text = block.text

    # Footer
    if RE_PAGE_FOOTER.match(text):
        return 'footer', None

    # Title (large bold)
    if block.is_bold and block.max_size > 16:
        return 'title', None

    # Section headers
    if block.is_bold and RE_SECTION_HEADER.match(text):
        return 'section_header', None

    # Supplement headers
    if RE_SUPPLEMENT.search(text) and (block.is_bold or block.max_size > 13):
        return 'supplement_header', None

    # Article start
    art_num = _is_article_start(text)
    if art_num is not None:
        return 'article_start', art_num

    # Definition line: bold text with ""term""
    if RE_DEFINITION_TERM.search(text):
        return 'definition', None

    # HS code reference
    if RE_HS_CODE.search(text):
        return 'hs_reference', None

    # Sub-article: )א( etc
    if RE_SUB_ARTICLE.match(text):
        return 'sub_article', None

    return 'paragraph', None


# ------------------------------------------------------------------ #
#  Main conversion                                                     #
# ------------------------------------------------------------------ #

def convert_pdf_to_xml(pdf_path, doc_name=None):
    """Convert a PDF file to structured XML."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))

    if doc_name is None:
        doc_name = pdf_path.stem

    with open(pdf_path, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()

    # --- XML root ---
    root = Element('document')
    root.set('name', doc_name)
    root.set('source_file', pdf_path.name)
    root.set('pages', str(doc.page_count))
    root.set('md5', file_hash)
    root.set('direction', 'rtl')
    root.set('language', 'he')

    meta_el = SubElement(root, 'metadata')
    pm = doc.metadata
    if pm.get('creationDate'):
        SubElement(meta_el, 'created').text = pm['creationDate']
    if pm.get('producer'):
        SubElement(meta_el, 'producer').text = pm['producer']
    SubElement(meta_el, 'source_url').text = 'shaarolami-query.customs.mof.gov.il'

    body = SubElement(root, 'body')

    # Track seen text per page to detect cross-page duplication
    seen_hashes = set()

    for page_idx in range(doc.page_count):
        page_el = SubElement(body, 'page')
        page_el.set('number', str(page_idx + 1))

        blocks = extract_page_blocks(doc, page_idx)

        for block in blocks:
            # Dedup: skip blocks whose text was already seen on a prior page
            text_hash = hashlib.md5(block.text.encode('utf-8')).hexdigest()
            if text_hash in seen_hashes:
                continue
            seen_hashes.add(text_hash)

            btype, extra = classify_block(block)

            if btype == 'footer':
                ft = SubElement(page_el, 'footer')
                ft.text = block.text
                continue

            if btype == 'title':
                t = SubElement(page_el, 'title')
                t.text = block.text
                t.set('font_size', f'{block.max_size:.1f}')
                continue

            if btype == 'section_header':
                s = SubElement(page_el, 'section')
                s.set('heading', block.text)
                s.set('page', str(block.page_num))
                continue

            if btype == 'supplement_header':
                sp = SubElement(page_el, 'supplement')
                m = RE_SUPPLEMENT.search(block.text)
                if m:
                    sp.set('number', m.group(1))
                sp.set('heading', block.text)
                sp.set('page', str(block.page_num))
                continue

            if btype == 'article_start':
                art = SubElement(page_el, 'article')
                art.set('number', extra)
                art.set('page', str(block.page_num))
                # Extract title (text minus trailing number)
                first_line = block.text.split('\n')[0].strip()
                title_text = RE_ARTICLE_NUM_TRAIL.sub('', first_line).strip()
                title_text = title_text.strip('() ')
                if title_text:
                    art.set('title', title_text)
                # Check for definitions
                defs = RE_DEFINITION_TERM.findall(block.text)
                if defs:
                    art.set('type', 'definitions')
                    for d in defs:
                        de = SubElement(art, 'definition')
                        de.set('term', d)
                # Full text
                txt = SubElement(art, 'text')
                txt.text = block.text
                continue

            if btype == 'definition':
                terms = RE_DEFINITION_TERM.findall(block.text)
                for term in terms:
                    de = SubElement(page_el, 'definition')
                    de.set('term', term)
                    de.set('page', str(block.page_num))
                    if block.is_bold:
                        de.set('bold', 'true')
                    de.text = block.text
                if not terms:
                    # Fallback: paragraph with bold
                    p = SubElement(page_el, 'paragraph')
                    p.text = block.text
                    p.set('page', str(block.page_num))
                    p.set('bold', 'true')
                continue

            # paragraph / hs_reference / sub_article — all stored as <paragraph>
            p = SubElement(page_el, 'paragraph')
            p.text = block.text
            p.set('page', str(block.page_num))
            if block.is_bold:
                p.set('bold', 'true')
            if btype == 'sub_article':
                m = RE_SUB_ARTICLE.match(block.text)
                if m:
                    p.set('sub_article', m.group(1))
            hs = RE_HS_CODE.findall(block.text)
            if hs:
                p.set('hs_codes', ','.join(hs))

    doc.close()
    return root


# ------------------------------------------------------------------ #
#  Output                                                              #
# ------------------------------------------------------------------ #

def xml_to_string(root):
    """Pretty-print XML to UTF-8 string."""
    indent(root, space='  ')
    body = tostring(root, encoding='unicode', xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body


def convert_file(input_path, output_path=None, doc_name=None):
    """Convert a single PDF to XML file."""
    inp = Path(input_path)
    outp = Path(output_path) if output_path else inp.with_suffix('.xml')

    print(f"Converting: {inp.name} -> {outp.name}")
    root = convert_pdf_to_xml(inp, doc_name)
    xml_str = xml_to_string(root)

    with open(outp, 'w', encoding='utf-8') as f:
        f.write(xml_str)

    arts = root.findall('.//article')
    defs = root.findall('.//definition')
    pages = root.findall('.//page')
    paras = root.findall('.//paragraph')
    hs_refs = [p for p in paras if p.get('hs_codes')]
    print(f"  Pages: {len(pages)}, Articles: {len(arts)}, "
          f"Definitions: {len(defs)}, Paragraphs: {len(paras)}, "
          f"HS refs: {len(hs_refs)}, Size: {len(xml_str):,} bytes")
    return outp


def batch_convert(directory, output_dir=None):
    """Convert all PDFs in a directory."""
    d = Path(directory)
    od = Path(output_dir) if output_dir else d / 'xml'
    od.mkdir(exist_ok=True)

    pdfs = sorted(d.glob('*.pdf'))
    if not pdfs:
        print(f"No PDFs found in {d}")
        return

    print(f"Found {len(pdfs)} PDFs to convert\n")
    results = []
    for pdf in pdfs:
        out = od / pdf.with_suffix('.xml').name
        try:
            convert_file(pdf, out)
            results.append((pdf.name, 'OK'))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((pdf.name, f'ERROR: {e}'))

    ok = sum(1 for _, s in results if s == 'OK')
    print(f"\n{'='*60}")
    print(f"Batch: {ok}/{len(results)} succeeded")
    for name, status in results:
        sym = '+' if status == 'OK' else '!'
        print(f"  [{sym}] {name}: {status}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == '--batch':
        if len(sys.argv) < 3:
            print("Usage: pdf_to_xml.py --batch <directory> [output_dir]")
            sys.exit(1)
        batch_convert(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        convert_file(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
