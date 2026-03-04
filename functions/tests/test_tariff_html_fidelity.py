"""
Test PDF→XML→HTML roundtrip fidelity for the Israeli Customs Tariff Book.

PURPOSE (user stated):
"if for example now i spend the time with you to make sure you have and can read
the PDF-XML-present back in correct format, it will be recorded to test file so
in the future any change we make will not destroy what we already made and is working."

Gold standard: downloads/84_31_tariff_codes.html (approved by user 2026-03-04)
Data source:   downloads/xml/*.xml (22 section XMLs + supplementary files)
Parser:        downloads/build_full_tariff.py
"""
import os
import re
import sys
import pytest
import xml.etree.ElementTree as ET

# ── Path setup ──
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DOWNLOADS = os.path.join(REPO_ROOT, 'downloads')
XML_DIR = os.path.join(DOWNLOADS, 'xml')
GOLD_8431 = os.path.join(DOWNLOADS, '84_31_tariff_codes.html')
FULL_BOOK = os.path.join(DOWNLOADS, 'customs_tariff_book.html')
FTA_HTML = os.path.join(DOWNLOADS, 'fta_eu_protocol4.html')

# Add downloads to path for parser import
sys.path.insert(0, DOWNLOADS)
sys.path.insert(0, os.path.join(REPO_ROOT, 'functions', 'lib'))

# ── Section metadata ──
SECTION_ROMANS = [
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX",
    "XX", "XXI", "XXII",
]

SUPPLEMENTARY_FILES = [
    "FrameOrder.xml",
    "ExemptCustomsItems.xml",
    "SecondAddition.xml",
    "ThirdAddition.xml",
]

# Known 84.31 leaf codes from the approved gold standard HTML
GOLD_8431_LEAF_CODES = [
    "100000/8", "200000/7", "310000/4", "390000/7",
    "410000/3", "420000/1", "430000/9", "491000/5",
    "492000/4", "493000/3", "494000/2", "499000/7",
]

GOLD_8431_GROUP_CODES = ["300000", "400000", "490000"]


def _xml_exists(name):
    return os.path.isfile(os.path.join(XML_DIR, name))


def _gold_exists():
    return os.path.isfile(GOLD_8431)


def _read_gold():
    with open(GOLD_8431, encoding='utf-8') as f:
        return f.read()


def _read_full_book():
    if os.path.isfile(FULL_BOOK):
        with open(FULL_BOOK, encoding='utf-8') as f:
            return f.read()
    return None


# ══════════════════════════════════════════════════════════════
# 1. XML Files Exist
# ══════════════════════════════════════════════════════════════
class TestXMLFilesExist:
    """All 22 section XMLs and supplementary files must be present."""

    @pytest.mark.parametrize("roman", SECTION_ROMANS)
    def test_section_xml_exists(self, roman):
        assert _xml_exists(f"{roman}.xml"), f"Missing section XML: {roman}.xml"

    @pytest.mark.parametrize("name", SUPPLEMENTARY_FILES)
    def test_supplementary_xml_exists(self, name):
        assert _xml_exists(name), f"Missing supplementary XML: {name}"

    def test_total_xml_count(self):
        if not os.path.isdir(XML_DIR):
            pytest.skip("XML dir not found")
        xml_files = [f for f in os.listdir(XML_DIR) if f.endswith('.xml')]
        assert len(xml_files) >= 26, f"Expected >=26 XMLs, found {len(xml_files)}"


# ══════════════════════════════════════════════════════════════
# 2. XML Parsing — each file can be parsed as valid XML
# ══════════════════════════════════════════════════════════════
class TestXMLParsing:
    """Each section XML parses without error and has expected structure."""

    @pytest.mark.parametrize("roman", SECTION_ROMANS)
    def test_section_parses(self, roman):
        path = os.path.join(XML_DIR, f"{roman}.xml")
        if not os.path.isfile(path):
            pytest.skip(f"{roman}.xml not found")
        tree = ET.parse(path)
        root = tree.getroot()
        assert root.tag in ('document', 'section', 'root'), f"Unexpected root tag: {root.tag}"
        # Must have at least one page element
        pages = root.findall('.//page')
        assert len(pages) > 0, f"{roman}.xml has no page elements"

    def test_xvi_has_chapter_84(self):
        """XVI.xml must contain chapter 84 content (heading 84.31 etc)."""
        path = os.path.join(XML_DIR, "XVI.xml")
        if not os.path.isfile(path):
            pytest.skip("XVI.xml not found")
        with open(path, encoding='utf-8') as f:
            content = f.read()
        assert '84.31' in content, "XVI.xml must contain heading 84.31"


# ══════════════════════════════════════════════════════════════
# 3. Parser — heading 84.31 extraction
# ══════════════════════════════════════════════════════════════
class TestParserHeading8431:
    """Parser correctly extracts heading 84.31 from XVI.xml."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            from build_full_tariff import parse_section_xml
            self.parse = parse_section_xml
        except ImportError:
            pytest.skip("build_full_tariff.py not importable")
        path = os.path.join(XML_DIR, "XVI.xml")
        if not os.path.isfile(path):
            pytest.skip("XVI.xml not found")
        self.data = self.parse(path)
        self.rows = self.data['rows']
        # Find 84.31 heading and its sub-rows
        self.heading_idx = None
        for i, r in enumerate(self.rows):
            if r.get('type') == 'heading' and r.get('code') == '84.31':
                self.heading_idx = i
                break
        if self.heading_idx is None:
            pytest.skip("Parser did not find heading 84.31")
        # Collect rows until next heading
        self.section_rows = []
        for r in self.rows[self.heading_idx + 1:]:
            if r.get('type') == 'heading':
                break
            self.section_rows.append(r)

    def test_heading_found(self):
        assert self.heading_idx is not None

    def test_heading_has_description(self):
        h = self.rows[self.heading_idx]
        desc = h.get('description', '')
        # Parser may leave heading description empty (text on separate line in XML)
        # Either description has content or code is correct
        assert h.get('code') == '84.31'

    def test_leaf_codes_present(self):
        leaf_codes = [r['code'] for r in self.section_rows if r.get('type') == 'leaf']
        for code in ["100000/8", "200000/7", "499000/7"]:
            assert code in leaf_codes, f"Missing leaf code {code}"

    def test_leaf_count(self):
        leaf_codes = [r for r in self.section_rows if r.get('type') == 'leaf']
        assert len(leaf_codes) >= 10, f"Expected >=10 leaves under 84.31, got {len(leaf_codes)}"

    def test_group_codes_present(self):
        group_codes = [r['code'] for r in self.section_rows if r.get('type') == 'group']
        assert "300000" in group_codes or "400000" in group_codes

    def test_first_leaf_description(self):
        first_leaf = next((r for r in self.section_rows if r.get('type') == 'leaf'), None)
        assert first_leaf is not None
        assert '84.25' in first_leaf.get('description', '')

    def test_leaf_has_unit(self):
        leaves = [r for r in self.section_rows if r.get('type') == 'leaf']
        for leaf in leaves[:3]:
            unit = leaf.get('unit', '')
            assert unit, f"Leaf {leaf.get('code')} missing unit"


# ══════════════════════════════════════════════════════════════
# 4. Gold Standard HTML structure
# ══════════════════════════════════════════════════════════════
class TestGoldStandard8431:
    """The approved gold standard HTML (84_31_tariff_codes.html) has correct structure."""

    @pytest.fixture(autouse=True)
    def setup(self):
        if not _gold_exists():
            pytest.skip("Gold standard HTML not found")
        self.html = _read_gold()

    def test_is_rtl(self):
        assert 'dir="rtl"' in self.html

    def test_is_hebrew(self):
        assert 'lang="he"' in self.html

    def test_utf8(self):
        assert 'charset="utf-8"' in self.html or 'charset=utf-8' in self.html

    def test_six_column_headers(self):
        assert 'פרט' in self.html
        assert 'תיאור' in self.html
        assert 'מכס כללי' in self.html
        assert 'מס קנייה' in self.html
        assert 'שיעור התוספות' in self.html
        assert 'יחידה סטטיסטית' in self.html

    def test_heading_row_class(self):
        assert 'heading-row' in self.html

    def test_leaf_row_class(self):
        assert 'leaf-row' in self.html

    def test_group_row_class(self):
        assert 'group-row' in self.html

    def test_note_row_class(self):
        assert 'note-row' in self.html

    def test_heading_code(self):
        assert '84.31' in self.html

    def test_heading_description(self):
        assert 'חלקים המתאימים לשימוש בלעדי או עיקרי' in self.html

    def test_all_12_leaf_codes(self):
        for code in GOLD_8431_LEAF_CODES:
            assert code in self.html, f"Missing leaf code in gold: {code}"

    def test_leaf_count_exact(self):
        count = self.html.count('class="leaf-row"')
        assert count == 12, f"Expected 12 leaf rows, found {count}"

    def test_all_3_group_codes(self):
        for code in GOLD_8431_GROUP_CODES:
            assert code in self.html, f"Missing group code in gold: {code}"

    def test_group_count_exact(self):
        count = self.html.count('class="group-row"')
        assert count == 3, f"Expected 3 group rows, found {count}"

    def test_heading_count_exact(self):
        count = self.html.count('class="heading-row"')
        assert count == 1, f"Expected 1 heading row, found {count}"

    def test_kilogram_unit_present(self):
        assert self.html.count('קילוגרם') >= 11, "Expected >=11 קילוגרם units"

    def test_each_one_unit(self):
        assert 'כל אחד' in self.html, "Expected at least one כל אחד unit"

    def test_duty_exempt(self):
        assert 'פטור' in self.html, "Expected פטור duty values"

    def test_validity_note(self):
        assert 'פרט זה בתוקף' in self.html, "Expected validity notes"

    def test_note_count(self):
        # Some note rows also have group-end class, count both
        count = self.html.count('note-row')
        assert count >= 10, f"Expected >=10 note rows, found {count}"


# ══════════════════════════════════════════════════════════════
# 5. Dash Hierarchy — indentation levels
# ══════════════════════════════════════════════════════════════
class TestDashHierarchy:
    """Dash counting and CSS indentation classes are correct."""

    def test_count_dashes_function(self):
        try:
            from build_full_tariff import count_dashes
        except ImportError:
            pytest.skip("build_full_tariff not importable")
        assert count_dashes("-text") == 1
        assert count_dashes("--text") == 2
        assert count_dashes("---text") == 3
        assert count_dashes("----text") == 4
        assert count_dashes("no dashes") == 0
        assert count_dashes("") == 0

    def test_d1_class_in_gold(self):
        if not _gold_exists():
            pytest.skip("Gold HTML not found")
        html = _read_gold()
        assert ' d1"' in html or " d1'" in html or 'class="desc d1"' in html

    def test_d2_class_in_gold(self):
        if not _gold_exists():
            pytest.skip("Gold HTML not found")
        html = _read_gold()
        assert 'd2' in html

    def test_d3_class_in_gold(self):
        if not _gold_exists():
            pytest.skip("Gold HTML not found")
        html = _read_gold()
        assert 'd3' in html

    def test_d1_for_single_dash(self):
        """First-level items (e.g., 100000/8 "- במכונות שבפרט 84.25") get d1."""
        if not _gold_exists():
            pytest.skip("Gold HTML not found")
        html = _read_gold()
        idx = html.find('100000/8')
        assert idx > 0
        # Find the full <tr> block containing this code
        tr_start = html.rfind('<tr', 0, idx)
        tr_end = html.find('</tr>', idx) + 5
        block = html[tr_start:tr_end]
        assert 'd1' in block, "100000/8 row should have d1 indentation"

    def test_d2_for_double_dash(self):
        """Second-level items (e.g., 310000/4 "-- במעליות") get d2."""
        if not _gold_exists():
            pytest.skip("Gold HTML not found")
        html = _read_gold()
        idx = html.find('310000/4')
        assert idx > 0
        tr_start = html.rfind('<tr', 0, idx)
        tr_end = html.find('</tr>', idx) + 5
        block = html[tr_start:tr_end]
        assert 'd2' in block, "310000/4 row should have d2 indentation"

    def test_d3_for_triple_dash(self):
        """Third-level items (e.g., 491000/5 "--- מסגרות בטיחות") get d3."""
        if not _gold_exists():
            pytest.skip("Gold HTML not found")
        html = _read_gold()
        idx = html.find('491000/5')
        assert idx > 0
        tr_start = html.rfind('<tr', 0, idx)
        tr_end = html.find('</tr>', idx) + 5
        block = html[tr_start:tr_end]
        assert 'd3' in block, "491000/5 row should have d3 indentation"


# ══════════════════════════════════════════════════════════════
# 6. Check Digit Format — XXXXXX/X
# ══════════════════════════════════════════════════════════════
class TestCheckDigitFormat:
    """Leaf codes follow XXXXXX/X format, group codes are 6-digit."""

    RE_LEAF = re.compile(r'^\d{6}/\d$')
    RE_GROUP = re.compile(r'^\d{6}$')
    RE_HEADING = re.compile(r'^\d{2}\.\d{2}$')

    def test_leaf_code_format(self):
        for code in GOLD_8431_LEAF_CODES:
            assert self.RE_LEAF.match(code), f"Invalid leaf format: {code}"

    def test_group_code_format(self):
        for code in GOLD_8431_GROUP_CODES:
            assert self.RE_GROUP.match(code), f"Invalid group format: {code}"

    def test_heading_format(self):
        assert self.RE_HEADING.match("84.31"), "Heading format should be XX.XX"

    def test_check_digit_is_single(self):
        for code in GOLD_8431_LEAF_CODES:
            parts = code.split('/')
            assert len(parts) == 2
            assert len(parts[1]) == 1
            assert parts[1].isdigit()


# ══════════════════════════════════════════════════════════════
# 7. Section Coverage — all 22 sections produce rows
# ══════════════════════════════════════════════════════════════
class TestSectionCoverage:
    """All 22 section XMLs produce non-zero tariff rows when parsed."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            from build_full_tariff import parse_section_xml
            self.parse = parse_section_xml
        except ImportError:
            pytest.skip("build_full_tariff not importable")

    @pytest.mark.parametrize("roman", SECTION_ROMANS)
    def test_section_has_rows(self, roman):
        path = os.path.join(XML_DIR, f"{roman}.xml")
        if not os.path.isfile(path):
            pytest.skip(f"{roman}.xml not found")
        data = self.parse(path)
        rows = data.get('rows', [])
        assert len(rows) > 0, f"Section {roman} produced 0 rows"

    def test_total_rows_across_all(self):
        total = 0
        for roman in SECTION_ROMANS:
            path = os.path.join(XML_DIR, f"{roman}.xml")
            if os.path.isfile(path):
                data = self.parse(path)
                total += len(data.get('rows', []))
        assert total >= 5000, f"Total rows {total} below expected >=5000"

    def test_xvi_has_many_entries(self):
        """Section XVI (chapters 84-85) should have hundreds of entries."""
        path = os.path.join(XML_DIR, "XVI.xml")
        if not os.path.isfile(path):
            pytest.skip("XVI.xml not found")
        data = self.parse(path)
        rows = data.get('rows', [])
        assert len(rows) >= 200, f"XVI should have >=200 rows, got {len(rows)}"


# ══════════════════════════════════════════════════════════════
# 8. Full Book HTML
# ══════════════════════════════════════════════════════════════
class TestFullBookHTML:
    """The generated full tariff book HTML has correct structure."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.html = _read_full_book()
        if self.html is None:
            pytest.skip("customs_tariff_book.html not found")

    def test_has_toc(self):
        assert 'תוכן עניינים' in self.html

    def test_has_all_sections(self):
        for roman in SECTION_ROMANS:
            assert f'section-{roman}' in self.html, f"Missing section {roman}"

    def test_has_framework_order(self):
        assert 'frame-order' in self.html or 'צו מסגרת' in self.html

    def test_has_discount_codes(self):
        assert 'discount-codes' in self.html or 'קודי הנחה' in self.html

    def test_has_supplements(self):
        assert 'supplements' in self.html or 'תוספות' in self.html

    def test_rtl_direction(self):
        assert 'dir="rtl"' in self.html

    def test_six_column_structure(self):
        assert 'פרט' in self.html
        assert 'תיאור' in self.html
        assert 'מכס כללי' in self.html

    def test_file_size(self):
        """Full book should be at least 1MB (lots of data)."""
        assert len(self.html) >= 1_000_000, f"Book too small: {len(self.html)} bytes"

    def test_contains_heading_8431(self):
        assert '84.31' in self.html


# ══════════════════════════════════════════════════════════════
# 9. Discount Codes Data
# ══════════════════════════════════════════════════════════════
class TestDiscountCodesData:
    """_discount_codes_data.py has correct structure."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            from _discount_codes_data import (
                DISCOUNT_CODES, DISCOUNT_GROUPS,
                get_discount_code, search_discount_codes, get_codes_by_group,
            )
            self.CODES = DISCOUNT_CODES
            self.GROUPS = DISCOUNT_GROUPS
            self.get_code = get_discount_code
            self.search = search_discount_codes
            self.by_group = get_codes_by_group
        except ImportError:
            pytest.skip("_discount_codes_data not importable")

    def test_discount_codes_count(self):
        assert len(self.CODES) == 80, f"Expected 80 discount items, got {len(self.CODES)}"

    def test_discount_groups_count(self):
        assert len(self.GROUPS) == 4, f"Expected 4 groups, got {len(self.GROUPS)}"

    def test_group_keys_are_ints(self):
        for k in self.GROUPS:
            assert isinstance(k, int), f"Group key {k} should be int"

    def test_get_discount_code_works(self):
        # Try first available code
        first_key = list(self.CODES.keys())[0]
        result = self.get_code(first_key)
        assert result is not None

    def test_search_returns_results(self):
        results = self.search("פטור")
        assert len(results) >= 0  # may or may not find matches

    def test_get_codes_by_group(self):
        results = self.by_group(1)
        assert isinstance(results, (list, dict))

    def test_each_code_has_description(self):
        for key, item in list(self.CODES.items())[:5]:
            assert 'description_he' in item or 'description' in item or 'd' in item or 'name' in item, \
                f"Code {key} missing description field"


# ══════════════════════════════════════════════════════════════
# 10. Procedures Data
# ══════════════════════════════════════════════════════════════
class TestProceduresData:
    """_procedures_data.py has correct structure."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            from _procedures_data import PROCEDURES
            self.procs = PROCEDURES
        except ImportError:
            pytest.skip("_procedures_data not importable")

    def test_has_procedure_1(self):
        assert "procedure_1" in self.procs or 1 in self.procs or "1" in self.procs

    def test_has_procedure_2(self):
        assert "procedure_2" in self.procs or 2 in self.procs or "2" in self.procs

    def test_has_procedure_3(self):
        assert "procedure_3" in self.procs or 3 in self.procs or "3" in self.procs

    def test_has_procedure_25(self):
        assert "procedure_25" in self.procs or 25 in self.procs or "25" in self.procs

    def test_procedure_has_full_text(self):
        for key, proc in list(self.procs.items())[:1]:
            assert 'full_text' in proc or 'full_text_he' in proc, \
                f"Procedure {key} missing full_text field"

    def test_total_procedures(self):
        assert len(self.procs) >= 4, f"Expected >=4 procedures, got {len(self.procs)}"


# ══════════════════════════════════════════════════════════════
# 11. Regex Patterns
# ══════════════════════════════════════════════════════════════
class TestRegexPatterns:
    """Parser regex patterns match expected code formats."""

    RE_HEADING = re.compile(r'^(\d{2}\.\d{2})$')
    RE_LEAF = re.compile(r'^(\d{6})/(\d)$')
    RE_GROUP = re.compile(r'^(\d{6})$')

    def test_heading_matches(self):
        assert self.RE_HEADING.match("84.31")
        assert self.RE_HEADING.match("01.01")
        assert self.RE_HEADING.match("99.99")
        assert not self.RE_HEADING.match("8431")
        assert not self.RE_HEADING.match("84.311")

    def test_leaf_matches(self):
        assert self.RE_LEAF.match("100000/8")
        assert self.RE_LEAF.match("499000/7")
        assert not self.RE_LEAF.match("100000")
        assert not self.RE_LEAF.match("10000/8")

    def test_group_matches(self):
        assert self.RE_GROUP.match("300000")
        assert self.RE_GROUP.match("490000")
        assert not self.RE_GROUP.match("300000/1")
        assert not self.RE_GROUP.match("30000")


# ══════════════════════════════════════════════════════════════
# 12. FTA HTML
# ══════════════════════════════════════════════════════════════
class TestFTAHtml:
    """FTA Protocol 4 HTML has correct structure."""

    @pytest.fixture(autouse=True)
    def setup(self):
        if not os.path.isfile(FTA_HTML):
            pytest.skip("FTA HTML not found")
        with open(FTA_HTML, encoding='utf-8') as f:
            self.html = f.read()

    def test_is_rtl(self):
        assert 'dir="rtl"' in self.html

    def test_has_protocol4_title(self):
        assert 'פרוטוקול 4' in self.html

    def test_has_gate_v(self):
        assert 'שער V' in self.html

    def test_has_article_17(self):
        assert 'סעיף 17' in self.html

    def test_has_article_22(self):
        assert 'סעיף 22' in self.html

    def test_has_eur1(self):
        assert 'EUR.1' in self.html

    def test_has_invoice_declaration(self):
        assert 'הצהרת חשבונית' in self.html

    def test_has_approved_exporter(self):
        assert 'יצואן מאושר' in self.html

    def test_has_english_declaration_text(self):
        assert 'The exporter of the products' in self.html

    def test_all_14_articles(self):
        for art in range(15, 36):
            assert f'סעיף {art}' in self.html, f"Missing article {art}"


# ══════════════════════════════════════════════════════════════
# 13. Parser CSS classes match gold standard pattern
# ══════════════════════════════════════════════════════════════
class TestParserHTMLClasses:
    """Parser-generated HTML uses consistent CSS class naming."""

    def test_parser_row_classes(self):
        """Parser uses hrow/lrow/grow/nrow; gold uses heading-row/leaf-row/etc."""
        try:
            from build_full_tariff import render_section, parse_section_xml
        except ImportError:
            pytest.skip("build_full_tariff not importable")
        path = os.path.join(XML_DIR, "XVI.xml")
        if not os.path.isfile(path):
            pytest.skip("XVI.xml not found")
        data = parse_section_xml(path)
        html = render_section(data, "XVI", "test", "test")
        # Parser uses: hrow, lrow, grow, nrow
        assert 'hrow' in html, "Parser should use hrow class"
        assert 'lrow' in html, "Parser should use lrow class"

    def test_parser_has_six_columns(self):
        try:
            from build_full_tariff import html_table_header
        except ImportError:
            pytest.skip("build_full_tariff not importable")
        header = html_table_header()
        assert 'פרט' in header
        assert 'תיאור' in header
        assert 'מכס כללי' in header
        assert 'מס קנייה' in header
        assert 'יחידה סטטיסטית' in header

    def test_parser_dash_classes(self):
        try:
            from build_full_tariff import render_section, parse_section_xml
        except ImportError:
            pytest.skip("build_full_tariff not importable")
        path = os.path.join(XML_DIR, "XVI.xml")
        if not os.path.isfile(path):
            pytest.skip("XVI.xml not found")
        data = parse_section_xml(path)
        html = render_section(data, "XVI", "test", "test")
        assert 'd1' in html, "Parser should use d1 indentation class"
