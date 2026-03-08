"""
Tariff Tree — Full hierarchical Israeli customs tariff from XML archive.
Isolated module. Does NOT modify any existing code or Firestore collections.

Parses CustomsItem.xml (tree structure) and CustomsItemDetailsHistory.xml
(Hebrew + English descriptions) to build a complete in-memory tariff tree
with 18,032 import nodes across 9 levels.

Public API:
    get_subtree(code_or_id, db=None)  -> dict or None
    search_tree(query, db=None)       -> list of matches
"""

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_XML_DIR = os.path.join(os.path.dirname(__file__), 'data')
_CUSTOMS_ITEM_FILE = 'CustomsItem.xml'
_DESCRIPTIONS_FILE = 'CustomsItemDetailsHistory.xml'
_NS = 'http://malam.com/customs/CustomsBook/CBC_NG_8362_MSG01_CustomsBookOut'

# Hebrew prefixes to strip when searching
_HE_PREFIXES = ('של', 'וה', 'מ', 'ב', 'ל', 'ה', 'ו', 'כ', 'ש')

# Module-level cached tree
_TREE = None           # dict: {node_id: TariffNode}
_FC_INDEX = None       # dict: {fc_string: node_id}
_ROOT_IDS = None       # list of root node IDs (sections)

# Characters that can appear in XML and break parsing
_INVALID_XML_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


# ---------------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------------

@dataclass
class TariffNode:
    """Single node in the tariff tree."""
    id: int
    parent_id: Optional[int]
    fc: str                          # FullClassification (e.g., "8431490000")
    level: int                       # 0-9 (0 = negatives, 1 = section, ...)
    desc_he: str = ''
    desc_en: str = ''
    children: list = field(default_factory=list, repr=False)
    check_digit: str = ''

    @property
    def hs_formatted(self) -> str:
        """Human-readable HS code format."""
        return _format_hs(self.fc, self.level)


# ---------------------------------------------------------------------------
# HS formatting
# ---------------------------------------------------------------------------

def _format_hs(fc: str, level: int) -> str:
    """Convert FullClassification to readable format by level."""
    if not fc:
        return ''
    # Level 1 = Section (Roman numeral) — keep as-is
    if level == 1:
        return fc
    # Strip any leading zeros for chapter display, but keep FC as-is for deeper
    digits = fc.replace('-', '').replace('.', '')
    if len(digits) < 2:
        return fc
    # Level 2 = Chapter: first 2 digits
    if level == 2:
        return digits[:2]
    # Level 3 = Heading: XX.XX
    if level == 3 and len(digits) >= 4:
        return f'{digits[:2]}.{digits[2:4]}'
    # Level 4+ = XX.XX.XXXXXX (pad or trim to 10)
    if len(digits) >= 4:
        padded = digits.ljust(10, '0')[:10]
        return f'{padded[:2]}.{padded[2:4]}.{padded[4:10]}'
    return fc


# ---------------------------------------------------------------------------
# XML parsing: CustomsItem.xml
# ---------------------------------------------------------------------------

def _parse_customs_items() -> dict:
    """
    Parse CustomsItem.xml, filter BookType=1 (import), return dict of
    {id: TariffNode} with parent_id and fc populated but no descriptions.
    """
    filepath = os.path.join(_XML_DIR, _CUSTOMS_ITEM_FILE)
    if not os.path.isfile(filepath):
        print(f'[tariff_tree] WARNING: {filepath} not found')
        return {}

    nodes = {}
    tag_ci = f'{{{_NS}}}CustomsItem'

    for event, elem in ET.iterparse(filepath, events=['end']):
        if elem.tag != tag_ci:
            continue
        try:
            bt = (elem.findtext(f'{{{_NS}}}CustomsBookTypeID') or '').strip()
            if bt != '1':
                elem.clear()
                continue

            nid = int(elem.findtext(f'{{{_NS}}}ID') or '0')
            pid_text = (elem.findtext(f'{{{_NS}}}Parent_CustomsItemID') or '').strip()
            pid = int(pid_text) if pid_text else None
            fc = (elem.findtext(f'{{{_NS}}}FullClassification') or '').strip()
            hl_text = (elem.findtext(f'{{{_NS}}}CustomsItemHierarchicLocationID') or '').strip()
            hl = int(hl_text) if hl_text else 0
            cd = (elem.findtext(f'{{{_NS}}}ComputedCheckDigit') or '').strip()

            nodes[nid] = TariffNode(
                id=nid,
                parent_id=pid,
                fc=fc,
                level=hl,
                check_digit=cd,
            )
        except (ValueError, TypeError):
            pass
        elem.clear()

    return nodes


# ---------------------------------------------------------------------------
# XML parsing: CustomsItemDetailsHistory.xml
# ---------------------------------------------------------------------------

def _parse_descriptions() -> dict:
    """
    Parse CustomsItemDetailsHistory.xml, return dict of
    {customs_item_id: (desc_he, desc_en)}.

    Selects the record with EntityStatusID=2 (active) and the latest
    StartDate per CustomsItemID. Falls back to any status if no active
    record exists.
    """
    filepath = os.path.join(_XML_DIR, _DESCRIPTIONS_FILE)
    if not os.path.isfile(filepath):
        print(f'[tariff_tree] WARNING: {filepath} not found')
        return {}

    # best[item_id] = (start_date_str, desc_he, desc_en, status)
    best = {}
    tag_cidh = f'{{{_NS}}}CustomsItemDetailsHistory'

    for event, elem in ET.iterparse(filepath, events=['end']):
        if elem.tag != tag_cidh:
            continue
        try:
            cid_text = (elem.findtext(f'{{{_NS}}}CustomsItemID') or '').strip()
            if not cid_text:
                elem.clear()
                continue
            cid = int(cid_text)
            status = (elem.findtext(f'{{{_NS}}}EntityStatusID') or '').strip()
            start_date = (elem.findtext(f'{{{_NS}}}StartDate') or '').strip()

            # GoodsDescription = Hebrew, EnglishGoodsDescription = English
            desc_he = (elem.findtext(f'{{{_NS}}}GoodsDescription') or '').strip()
            desc_en = (elem.findtext(f'{{{_NS}}}EnglishGoodsDescription') or '').strip()

            # Skip cancelled/empty descriptions
            if desc_he in ('מבוטל', '') and desc_en in ('Canceled', 'Cancelled', '---', ''):
                elem.clear()
                continue

            # Prefer active (status=2) over others, then latest start_date
            is_active = (status == '2')
            prev = best.get(cid)
            if prev is None:
                best[cid] = (start_date, desc_he, desc_en, is_active)
            else:
                prev_active = prev[3]
                # Active beats non-active; among same status, later date wins
                if (is_active and not prev_active) or \
                   (is_active == prev_active and start_date > prev[0]):
                    best[cid] = (start_date, desc_he, desc_en, is_active)
        except (ValueError, TypeError):
            pass
        elem.clear()

    return {cid: (v[1], v[2]) for cid, v in best.items()}


# ---------------------------------------------------------------------------
# Firestore gap-fill (optional)
# ---------------------------------------------------------------------------

def _fill_from_firestore(nodes: dict, db) -> int:
    """
    For nodes missing descriptions, try to match by FullClassification
    against the existing `tariff` Firestore collection.
    Returns count of filled nodes. Only runs if db is provided.
    """
    if db is None:
        return 0

    # Gather FCs that need filling
    missing = {}
    for nid, node in nodes.items():
        if not node.desc_he and not node.desc_en and node.fc and not node.fc.startswith('-'):
            fc_key = node.fc.lstrip('0') or node.fc
            if fc_key not in missing:
                missing[fc_key] = []
            missing[fc_key].append(nid)

    if not missing:
        return 0

    filled = 0
    try:
        # Batch lookup from Firestore tariff collection
        # Documents are keyed by 10-digit HS code
        for fc, node_ids in missing.items():
            padded = fc.ljust(10, '0')[:10]
            doc = db.collection('tariff').document(padded).get()
            if doc.exists:
                data = doc.to_dict()
                he = data.get('description_he', '') or data.get('description', '')
                en = data.get('description_en', '')
                if he or en:
                    for nid in node_ids:
                        nodes[nid].desc_he = nodes[nid].desc_he or he
                        nodes[nid].desc_en = nodes[nid].desc_en or en
                        filled += 1
    except Exception as e:
        print(f'[tariff_tree] Firestore fill error: {e}')

    return filled


# ---------------------------------------------------------------------------
# Tree construction
# ---------------------------------------------------------------------------

def _build_tree(nodes: dict) -> list:
    """
    Link parent→children relationships.
    Returns list of root node IDs (nodes whose parent_id is None or
    whose parent is not in the import set).
    """
    root_ids = []
    for nid, node in nodes.items():
        if node.parent_id is not None and node.parent_id in nodes:
            parent = nodes[node.parent_id]
            parent.children.append(node)
        else:
            root_ids.append(nid)

    # Sort children at every level by FC for deterministic order
    for node in nodes.values():
        node.children.sort(key=lambda n: n.fc)

    return root_ids


# ---------------------------------------------------------------------------
# FC index builder
# ---------------------------------------------------------------------------

def _build_fc_index(nodes: dict) -> dict:
    """Build lookup dict: {normalized_fc: node_id}."""
    idx = {}
    for nid, node in nodes.items():
        fc = node.fc
        if fc:
            idx[fc] = nid
            # Also index without leading zeros (e.g., "0407110000" -> "407110000")
            stripped = fc.lstrip('0')
            if stripped and stripped != fc:
                idx[stripped] = nid
    return idx


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

def load_tariff_tree(db=None) -> tuple:
    """
    Load and cache the tariff tree.
    Returns (nodes_dict, fc_index, root_ids).
    """
    global _TREE, _FC_INDEX, _ROOT_IDS

    if _TREE is not None:
        return _TREE, _FC_INDEX, _ROOT_IDS

    print('[tariff_tree] Loading tariff tree from XML...')
    nodes = _parse_customs_items()
    if not nodes:
        print('[tariff_tree] No nodes parsed — check XML files.')
        _TREE, _FC_INDEX, _ROOT_IDS = {}, {}, []
        return _TREE, _FC_INDEX, _ROOT_IDS

    print(f'[tariff_tree] Parsed {len(nodes)} import nodes.')

    descs = _parse_descriptions()
    filled_xml = 0
    for nid, node in nodes.items():
        if nid in descs:
            node.desc_he, node.desc_en = descs[nid]
            filled_xml += 1
    print(f'[tariff_tree] {filled_xml} nodes got descriptions from XML.')

    missing_count = sum(1 for n in nodes.values() if not n.desc_he and not n.desc_en)
    print(f'[tariff_tree] {missing_count} nodes still missing descriptions.')

    if db is not None and missing_count > 0:
        fs_filled = _fill_from_firestore(nodes, db)
        print(f'[tariff_tree] {fs_filled} nodes filled from Firestore.')

    root_ids = _build_tree(nodes)
    print(f'[tariff_tree] Tree built: {len(root_ids)} root nodes.')

    fc_index = _build_fc_index(nodes)

    _TREE = nodes
    _FC_INDEX = fc_index
    _ROOT_IDS = root_ids

    return _TREE, _FC_INDEX, _ROOT_IDS


# ---------------------------------------------------------------------------
# Node serialization
# ---------------------------------------------------------------------------

def _node_to_dict(node: TariffNode, include_children: bool = True) -> dict:
    """Convert a TariffNode to a plain dict for the public API."""
    d = {
        'fc': node.fc,
        'hs': node.hs_formatted,
        'level': node.level,
        'desc_he': node.desc_he,
        'desc_en': node.desc_en,
    }
    if include_children:
        d['children'] = [_node_to_dict(c) for c in node.children]
    return d


def _node_to_path_entry(node: TariffNode) -> dict:
    """Minimal dict for path entries in search results."""
    return {
        'fc': node.fc,
        'level': node.level,
        'desc_he': node.desc_he,
        'desc_en': node.desc_en,
    }


# ---------------------------------------------------------------------------
# Code normalization for lookup
# ---------------------------------------------------------------------------

def _normalize_code(code_str: str) -> list:
    """
    Given a user-provided code string, return a list of candidate FC values
    to look up in the index.

    Examples:
        "8431"        -> ["8431000000"]
        "84.31"       -> ["8431000000"]
        "84.31.4900"  -> ["8431490000"]
        "8431490000"  -> ["8431490000"]
        "XVI"         -> ["XVI"]
        "84"          -> ["8400000000"]
    """
    s = code_str.strip()
    if not s:
        return []

    # Roman numeral section — keep as-is
    if re.match(r'^[IVXLCDM]+$', s):
        return [s]

    # Strip dots and spaces to get pure digits
    digits = s.replace('.', '').replace(' ', '').replace('/', '')

    if not digits.isdigit():
        return [s]

    candidates = []

    # For 2-digit codes (chapters), FC format is XX00000000
    # For 4-digit codes (headings), FC format is XXXX000000
    # For longer codes, pad to 10 digits
    padded = digits.ljust(10, '0')[:10]
    candidates.append(padded)

    # Also try original digits (in case of stripped-zero match)
    if digits != padded:
        candidates.append(digits)

    return candidates


# ---------------------------------------------------------------------------
# Path builder (for search results)
# ---------------------------------------------------------------------------

def _build_path(node: TariffNode, nodes: dict) -> list:
    """Build path from root (Section) down to this node."""
    path = []
    current = node
    visited = set()
    while current is not None:
        if current.id in visited:
            break
        visited.add(current.id)
        path.append(_node_to_path_entry(current))
        if current.parent_id is not None and current.parent_id in nodes:
            current = nodes[current.parent_id]
        else:
            break
    path.reverse()
    return path


# ---------------------------------------------------------------------------
# Hebrew prefix stripping for search
# ---------------------------------------------------------------------------

def _strip_he_prefixes(word: str) -> list:
    """Return the word plus variants with Hebrew prefixes stripped."""
    variants = [word]
    for prefix in _HE_PREFIXES:
        if word.startswith(prefix) and len(word) > len(prefix):
            stripped = word[len(prefix):]
            if stripped not in variants:
                variants.append(stripped)
    return variants


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_subtree(code_or_id, db=None) -> Optional[dict]:
    """
    Returns full subtree from that node downward.

    code_or_id can be:
      - HS code string: "8431", "84.31", "8431490000", "84.31.4900"
      - Roman numeral section: "XVI"
      - Node ID (int): 25900

    Returns dict with node info + children recursively, or None if not found.
    """
    nodes, fc_index, root_ids = load_tariff_tree(db)
    if not nodes:
        return None

    # Try as integer node ID first (only for Python int, not strings)
    if isinstance(code_or_id, int):
        node = nodes.get(code_or_id)
        if node:
            return _node_to_dict(node)
        return None

    code_str = str(code_or_id).strip()
    if not code_str:
        return None

    # Try FC index with normalization (do this BEFORE node ID to avoid
    # false matches — e.g., "84" is chapter 84, not node ID 84)
    candidates = _normalize_code(code_str)
    for c in candidates:
        if c in fc_index:
            node = nodes[fc_index[c]]
            return _node_to_dict(node)

    return None


def search_tree(query: str, db=None) -> list:
    """
    Search Hebrew or English descriptions in the tree.

    Returns list of matches, each with full path from Section down to the match.
    Supports Hebrew prefix stripping (מ,ב,ל,ה,ו,כ,ש).
    Returns up to 50 results.
    """
    nodes, fc_index, root_ids = load_tariff_tree(db)
    if not nodes:
        return []

    query = (query or '').strip()
    if not query:
        return []

    query_lower = query.lower()

    # Build search terms with Hebrew prefix variants
    words = query_lower.split()
    search_variants = []
    for w in words:
        search_variants.extend(_strip_he_prefixes(w))

    results = []
    for nid, node in nodes.items():
        he = (node.desc_he or '').lower()
        en = (node.desc_en or '').lower()
        match_field = None

        # Check if any variant matches
        for variant in search_variants:
            if variant in he:
                match_field = 'desc_he'
                break
            if variant in en:
                match_field = 'desc_en'
                break

        if match_field:
            results.append({
                'fc': node.fc,
                'hs': node.hs_formatted,
                'level': node.level,
                'desc_he': node.desc_he,
                'desc_en': node.desc_en,
                'path': _build_path(node, nodes),
                'match_field': match_field,
            })
            if len(results) >= 50:
                break

    return results


def reset_cache():
    """Reset the cached tree. Useful for testing."""
    global _TREE, _FC_INDEX, _ROOT_IDS
    _TREE = None
    _FC_INDEX = None
    _ROOT_IDS = None
