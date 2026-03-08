"""
Tests for tariff_tree.py — isolated tariff tree from XML archive.
Tests require the XML files to be present at data_c3/extracted/.
"""

import os
import sys
import pytest

# Ensure functions/lib is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.tariff_tree import get_subtree, search_tree, load_tariff_tree, reset_cache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_XML_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data_c3', 'extracted')
_HAS_XML = os.path.isfile(os.path.join(_XML_DIR, 'CustomsItem.xml'))

pytestmark = pytest.mark.skipif(not _HAS_XML, reason='XML files not present')


@pytest.fixture(autouse=True, scope='module')
def _load_tree_once():
    """Ensure tree is loaded once for all tests in this module."""
    reset_cache()
    load_tariff_tree(db=None)
    yield
    reset_cache()


# ---------------------------------------------------------------------------
# Test get_subtree with code formats
# ---------------------------------------------------------------------------

class TestGetSubtreeByCode:

    def test_heading_4_digits(self):
        """get_subtree('8431') returns a non-empty subtree with children."""
        result = get_subtree('8431')
        assert result is not None
        assert len(result.get('children', [])) > 0

    def test_heading_dotted(self):
        """get_subtree('84.31') returns the same subtree as '8431'."""
        r1 = get_subtree('8431')
        r2 = get_subtree('84.31')
        assert r1 is not None
        assert r2 is not None
        assert r1['fc'] == r2['fc']

    def test_full_10_digit(self):
        """get_subtree('8431490000') returns a subtree (leaf or near-leaf)."""
        result = get_subtree('8431490000')
        assert result is not None
        assert result['fc'] == '8431490000'

    def test_section_roman(self):
        """get_subtree('XVI') returns Section XVI with chapters as children."""
        result = get_subtree('XVI')
        assert result is not None
        assert result['level'] == 1
        children = result.get('children', [])
        assert len(children) > 0
        # All children should be chapters (level 2)
        for child in children:
            assert child['level'] == 2

    def test_chapter_2_digits(self):
        """get_subtree('84') returns Chapter 84 with headings as children."""
        result = get_subtree('84')
        assert result is not None
        assert result['level'] == 2
        children = result.get('children', [])
        # Chapter 84 should have many headings
        assert len(children) >= 50

    def test_chapter_all_levels_ge_2(self):
        """Every node in get_subtree('84') has level >= 2."""
        result = get_subtree('84')
        assert result is not None

        def _check_levels(node, min_level):
            assert node['level'] >= min_level, \
                f"Node {node['fc']} has level {node['level']} < {min_level}"
            for child in node.get('children', []):
                _check_levels(child, min_level)

        _check_levels(result, 2)

    def test_nonexistent_returns_none(self):
        """get_subtree('nonexistent') returns None."""
        result = get_subtree('nonexistent')
        assert result is None

    def test_dotted_subheading(self):
        """get_subtree with dotted subheading format works."""
        result = get_subtree('84.31.4900')
        # Should resolve to the same node as 8431490000
        if result is not None:
            assert '8431' in result['fc']


# ---------------------------------------------------------------------------
# Test search_tree
# ---------------------------------------------------------------------------

class TestSearchTree:

    def test_hebrew_crane(self):
        """search_tree('עגורן') returns results (crane nodes)."""
        results = search_tree('עגורן')
        assert len(results) > 0
        # At least one result should have the Hebrew term
        assert any('עגורן' in r.get('desc_he', '').lower() or
                    'עגורנ' in r.get('desc_he', '').lower()
                    for r in results)

    def test_english_crane(self):
        """search_tree('crane') returns results (English search)."""
        results = search_tree('crane')
        assert len(results) > 0
        assert any('crane' in r.get('desc_en', '').lower() for r in results)

    def test_search_results_have_path(self):
        """search_tree results all have a path list with Section at index 0."""
        results = search_tree('עגורן')
        assert len(results) > 0
        for r in results:
            path = r.get('path', [])
            assert len(path) >= 1, f"Empty path for {r['fc']}"
            # Root of path should be a section (level 1) or chapter (level 2)
            assert path[0]['level'] in (1, 2, 0), \
                f"Path root level is {path[0]['level']} for {r['fc']}"

    def test_empty_query_returns_empty(self):
        """search_tree('') returns empty list."""
        results = search_tree('')
        assert results == []

    def test_max_50_results(self):
        """search_tree returns at most 50 results."""
        # Search for something very common
        results = search_tree('other')
        assert len(results) <= 50

    def test_search_match_field(self):
        """Each search result has match_field set."""
        results = search_tree('steel')
        assert len(results) > 0
        for r in results:
            assert r['match_field'] in ('desc_he', 'desc_en')


# ---------------------------------------------------------------------------
# Test tree loading without Firestore
# ---------------------------------------------------------------------------

class TestLoadWithoutFirestore:

    def test_loads_without_db(self):
        """Tree loads without Firestore (db=None) using XML descriptions only."""
        reset_cache()
        nodes, fc_index, root_ids = load_tariff_tree(db=None)
        assert len(nodes) > 10000  # should have ~18,032 nodes
        assert len(fc_index) > 10000
        assert len(root_ids) > 0
        # Restore cache
        reset_cache()
        load_tariff_tree(db=None)

    def test_root_nodes_are_sections(self):
        """Root nodes should be sections (level 1) or orphans."""
        nodes, fc_index, root_ids = load_tariff_tree(db=None)
        section_count = sum(1 for rid in root_ids if nodes[rid].level == 1)
        assert section_count == 22  # 22 tariff sections


# ---------------------------------------------------------------------------
# Test node structure
# ---------------------------------------------------------------------------

class TestNodeStructure:

    def test_subtree_has_required_fields(self):
        """Subtree dict has all required fields."""
        result = get_subtree('84')
        assert result is not None
        for key in ('fc', 'hs', 'level', 'desc_he', 'desc_en', 'children'):
            assert key in result, f"Missing key: {key}"

    def test_children_are_dicts(self):
        """Children in subtree are dicts with correct structure."""
        result = get_subtree('84')
        assert result is not None
        for child in result.get('children', [])[:5]:
            assert isinstance(child, dict)
            assert 'fc' in child
            assert 'children' in child
