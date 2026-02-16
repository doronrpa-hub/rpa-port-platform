"""
Tests for TableExtractor cross-verification.

Session 28C — Assignment 20.
NEW FILE.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.table_extractor import TableExtractor


@pytest.fixture
def extractor():
    return TableExtractor()


# ─────────────────────────────────────
#  Helper methods
# ─────────────────────────────────────

class TestHelpers:

    def test_to_dicts_basic(self, extractor):
        rows = [["Name", "Value"], ["A", "1"], ["B", "2"]]
        result = extractor._to_dicts(rows)
        assert len(result) == 2
        assert result[0] == {"Name": "A", "Value": "1"}
        assert result[1] == {"Name": "B", "Value": "2"}

    def test_to_dicts_empty(self, extractor):
        assert extractor._to_dicts([]) == []

    def test_to_dicts_header_only(self, extractor):
        assert extractor._to_dicts([["A", "B"]]) == []

    def test_to_dicts_none_cells(self, extractor):
        rows = [["Name", "Value"], [None, "1"], ["B", None]]
        result = extractor._to_dicts(rows)
        assert result[0]["Name"] == ""
        assert result[1]["Value"] == ""

    def test_to_dicts_skips_empty_rows(self, extractor):
        rows = [["Name", "Value"], ["A", "1"], [None, None], ["B", "2"]]
        result = extractor._to_dicts(rows)
        assert len(result) == 2  # Empty row skipped


# ─────────────────────────────────────
#  Cross-verification
# ─────────────────────────────────────

class TestCrossVerification:

    def test_structures_agree(self, extractor):
        t1 = [[{"A": "1", "B": "2"}, {"A": "3", "B": "4"}]]
        t2 = [[{"A": "1", "B": "2"}, {"A": "3", "B": "4"}]]
        assert extractor._structures_disagree(t1, t2) is False

    def test_different_table_count(self, extractor):
        t1 = [[{"A": "1"}]]
        t2 = [[{"A": "1"}], [{"B": "2"}]]
        assert extractor._structures_disagree(t1, t2) is True

    def test_different_row_count(self, extractor):
        t1 = [[{"A": "1"}, {"A": "2"}, {"A": "3"}, {"A": "4"}]]
        t2 = [[{"A": "1"}]]
        assert extractor._structures_disagree(t1, t2) is True

    def test_different_columns(self, extractor):
        t1 = [[{"A": "1", "B": "2"}]]
        t2 = [[{"X": "1", "Y": "2"}]]
        assert extractor._structures_disagree(t1, t2) is True

    def test_close_row_counts_agree(self, extractor):
        """Within 2 rows tolerance should agree."""
        t1 = [[{"A": "1"}, {"A": "2"}, {"A": "3"}]]
        t2 = [[{"A": "1"}, {"A": "2"}, {"A": "3"}, {"A": "4"}]]
        assert extractor._structures_disagree(t1, t2) is False


# ─────────────────────────────────────
#  HTML table extraction
# ─────────────────────────────────────

class TestHTMLTables:

    def test_bs4_tables(self, extractor):
        html = (
            b"<html><body>"
            b"<table>"
            b"<tr><th>Product</th><th>Price</th></tr>"
            b"<tr><td>Bolts</td><td>5.50</td></tr>"
            b"<tr><td>Nuts</td><td>3.25</td></tr>"
            b"</table>"
            b"</body></html>"
        )
        result = extractor._bs4_tables(html)
        assert result is not None
        assert len(result) == 1
        assert len(result[0]) == 2
        assert result[0][0]["Product"] == "Bolts"

    def test_bs4_multiple_tables(self, extractor):
        html = (
            b"<html><body>"
            b"<table><tr><th>A</th></tr><tr><td>1</td></tr></table>"
            b"<table><tr><th>B</th></tr><tr><td>2</td></tr></table>"
            b"</body></html>"
        )
        result = extractor._bs4_tables(html)
        assert result is not None
        assert len(result) == 2

    def test_no_tables_returns_none(self, extractor):
        html = b"<html><body><p>No tables here</p></body></html>"
        result = extractor._bs4_tables(html)
        assert result is None


# ─────────────────────────────────────
#  Full extraction pipeline
# ─────────────────────────────────────

class TestFullExtraction:

    def test_html_extraction_returns_structure(self, extractor):
        html = (
            b"<html><body>"
            b"<table><tr><th>X</th></tr><tr><td>Y</td></tr></table>"
            b"</body></html>"
        )
        result = extractor.extract_tables(html, "text/html")
        assert "tables" in result
        assert "confidence" in result
        assert "methods_tried" in result
        assert "warnings" in result

    def test_unknown_content_type(self, extractor):
        result = extractor.extract_tables(b"data", "application/octet-stream")
        assert result["tables"] == []
        assert "No tables found" in result["warnings"]

    def test_table_shape_description(self, extractor):
        tables = [
            [{"A": "1", "B": "2"}, {"A": "3", "B": "4"}],
            [{"X": "a"}],
        ]
        shape = extractor._table_shape(tables)
        assert "2 table(s)" in shape
        assert "2 rows" in shape
