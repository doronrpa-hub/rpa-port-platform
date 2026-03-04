"""Parse ExemptCustomsItems.xml into _discount_codes_data.py.

One-time conversion script. Reads the XML and produces a Python module
with all discount codes (קודי הנחה) as embedded constants.
"""
import re
import xml.etree.ElementTree as ET
from collections import OrderedDict


def parse_discount_codes(xml_path):
    """Parse ExemptCustomsItems.xml → list of discount code groups."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Collect all text content per page
    pages = {}
    for page_el in root.iter('page'):
        page_num = int(page_el.get('number', '0'))
        texts = []
        for child in page_el:
            tag = child.tag
            text = (child.text or '').strip()
            if tag == 'footer' or not text:
                continue
            # Also get nested text from <article> elements
            if tag == 'article':
                inner = child.find('text')
                if inner is not None and inner.text:
                    text = inner.text.strip()
            texts.append(text)
        pages[page_num] = texts

    # Flatten all text blocks in order
    all_blocks = []
    for pn in sorted(pages.keys()):
        for t in pages[pn]:
            all_blocks.append(t)

    # Now parse the flat text stream into groups and codes
    groups = OrderedDict()
    current_group = None
    current_group_text = []
    current_code = None
    current_code_text = []

    # Patterns
    # Group header: "קבוצה" followed by number, or standalone small number (1-998)
    # that starts a new section
    group_pattern = re.compile(r'^(\d{1,3})$')
    # 6-digit discount code
    code_pattern = re.compile(r'^(\d{6})$')
    # 10-digit code (sometimes appears)
    code10_pattern = re.compile(r'(\d{10})')
    # Duty status
    duty_exempt = re.compile(r'פטור')
    duty_pct = re.compile(r'(\d+)%')
    conditional = re.compile(r'מותנה')

    i = 0
    while i < len(all_blocks):
        block = all_blocks[i].strip()

        # Skip page footers
        if re.match(r'^\d+עמוד\s*$', block) or 'הודפס בתאריך' in block:
            i += 1
            continue

        # Check for group number (standalone 1-3 digit number, typically 1-998)
        gm = group_pattern.match(block)
        if gm:
            num = int(gm.group(1))
            # Groups are typically small numbers; codes are 6-digit
            # Save previous group
            if current_group is not None:
                _save_group(groups, current_group, current_group_text,
                           current_code, current_code_text)
            current_group = num
            current_group_text = []
            current_code = None
            current_code_text = []
            i += 1
            continue

        # Check for 6-digit code
        cm = code_pattern.match(block)
        if cm:
            # Save previous code into current group
            if current_code is not None and current_group is not None:
                _save_code(groups, current_group, current_code, current_code_text)
            current_code = cm.group(1)
            current_code_text = []
            i += 1
            continue

        # Check for blocks that end with a 6-digit code (common pattern:
        # "description text\n100000")
        lines = block.split('\n')
        last_line = lines[-1].strip() if lines else ''
        cm2 = code_pattern.match(last_line)
        if cm2 and len(lines) > 1:
            # Text before the code goes to current context
            desc_text = '\n'.join(lines[:-1]).strip()
            if current_code is not None and current_group is not None:
                current_code_text.append(desc_text)
                _save_code(groups, current_group, current_code, current_code_text)
            elif current_group is not None:
                current_group_text.append(desc_text)
            current_code = cm2.group(1)
            current_code_text = []
            i += 1
            continue

        # Check for 10-digit code at start (like 0070000000)
        m10 = re.match(r'^[­\u00AD]?(\d{10})\b', block.replace('\u00AD', ''))
        if m10:
            # This is a top-level item code, treat as group identifier
            if current_group is not None:
                _save_group(groups, current_group, current_group_text,
                           current_code, current_code_text)
            current_group = m10.group(1)
            current_group_text = []
            current_code = None
            current_code_text = []
            rest = block[block.index(m10.group(1)) + len(m10.group(1)):].strip()
            if rest:
                current_group_text.append(rest)
            i += 1
            continue

        # Regular text — append to current code or group
        if current_code is not None:
            current_code_text.append(block)
        elif current_group is not None:
            current_group_text.append(block)
        i += 1

    # Save final
    if current_group is not None:
        _save_group(groups, current_group, current_group_text,
                   current_code, current_code_text)

    return groups


def _save_code(groups, group_id, code, text_parts):
    """Save a discount code into its group."""
    key = str(group_id)
    if key not in groups:
        groups[key] = {'codes': OrderedDict(), 'text': '', 'rules': []}
    full_text = '\n'.join(text_parts).strip()

    # Extract duty/tax status
    duty = 'פטור' if 'פטור' in full_text else ''
    pct_match = re.search(r'(\d+)%', full_text)
    if pct_match and not duty:
        duty = pct_match.group(0)
    conditional = 'מותנה' in full_text

    # Extract HS code references
    hs_refs = re.findall(r'\d{2}\.\d{2}\.\d{4}', full_text)

    groups[key]['codes'][code] = {
        'text': full_text,
        'duty': duty,
        'conditional': conditional,
        'hs_refs': hs_refs,
    }


def _save_group(groups, group_id, group_text, last_code, last_code_text):
    """Save group description and its last code."""
    key = str(group_id)
    if key not in groups:
        groups[key] = {'codes': OrderedDict(), 'text': '', 'rules': []}
    groups[key]['text'] = '\n'.join(group_text).strip()

    # Save last code if any
    if last_code is not None:
        _save_code(groups, group_id, last_code, last_code_text)


def _extract_rules(text):
    """Extract numbered rules from group text."""
    rules = []
    for m in re.finditer(r'\((\d+)\)\s*(.+?)(?=\(\d+\)|$)', text, re.DOTALL):
        rules.append({'num': int(m.group(1)), 'text': m.group(2).strip()})
    return rules


def build_data_module(groups, output_path):
    """Write _discount_codes_data.py from parsed groups."""
    lines = [
        '"""Discount codes (קודי הנחה) — Israeli customs duty exemptions and reductions.',
        '',
        'Source: ExemptCustomsItems.xml (shaarolami.customs.mof.gov.il)',
        'Extracted from 55-page PDF converted to XML.',
        '',
        'Structure:',
        '  DISCOUNT_GROUPS: dict keyed by group number (str)',
        '    Each group has:',
        '      "t": group description text (Hebrew)',
        '      "codes": dict of 6-digit codes, each with:',
        '        "t": description text',
        '        "d": duty status (פטור or percentage)',
        '        "c": True if conditional (מותנה)',
        '        "h": list of HS code references (if any)',
        '',
        'Helper functions:',
        '  get_discount_group(group_num) -> dict or None',
        '  get_discount_code(code) -> dict or None (searches all groups)',
        '  search_discount_codes(keyword) -> list of matches',
        '"""',
        '',
        '',
    ]

    # Build the dict
    lines.append('DISCOUNT_GROUPS = {')
    for gid, gdata in groups.items():
        g_text = gdata['text'].replace('\\', '\\\\').replace("'", "\\'")
        lines.append(f"    {repr(str(gid))}: {{")
        lines.append(f"        't': {repr(gdata['text'])},")
        if gdata['codes']:
            lines.append(f"        'codes': {{")
            for code, cdata in gdata['codes'].items():
                c_text = cdata['text']
                c_duty = cdata['duty']
                c_cond = cdata['conditional']
                c_hs = cdata['hs_refs']
                hs_part = f", 'h': {c_hs}" if c_hs else ""
                cond_part = ", 'c': True" if c_cond else ""
                lines.append(f"            {repr(code)}: {{'t': {repr(c_text)}, 'd': {repr(c_duty)}{cond_part}{hs_part}}},")
            lines.append(f"        }},")
        else:
            lines.append(f"        'codes': {{}},")
        lines.append(f"    }},")
    lines.append('}')
    lines.append('')
    lines.append('')

    # Add helper functions
    lines.extend([
        'def get_discount_group(group_num):',
        '    """Get a discount code group by number."""',
        '    return DISCOUNT_GROUPS.get(str(group_num))',
        '',
        '',
        'def get_discount_code(code):',
        '    """Find a discount code across all groups. Returns (group_id, code_data) or None."""',
        '    code = str(code)',
        '    for gid, gdata in DISCOUNT_GROUPS.items():',
        '        if code in gdata.get("codes", {}):',
        '            return (gid, gdata["codes"][code])',
        '    return None',
        '',
        '',
        'def search_discount_codes(keyword):',
        '    """Search discount codes by keyword. Returns list of (group_id, code, data) tuples."""',
        '    kw = keyword.lower()',
        '    results = []',
        '    for gid, gdata in DISCOUNT_GROUPS.items():',
        '        if kw in gdata.get("t", "").lower():',
        '            results.append((gid, None, gdata))',
        '        for code, cdata in gdata.get("codes", {}).items():',
        '            if kw in cdata.get("t", "").lower():',
        '                results.append((gid, code, cdata))',
        '    return results[:20]',
        '',
    ])

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return len(groups), sum(len(g.get('codes', {})) for g in groups.values())


if __name__ == '__main__':
    import os
    xml_path = os.path.join(os.path.dirname(__file__), '..', 'downloads', 'xml', 'ExemptCustomsItems.xml')
    out_path = os.path.join(os.path.dirname(__file__), 'lib', '_discount_codes_data.py')

    print(f"Parsing {xml_path}...")
    groups = parse_discount_codes(xml_path)

    print(f"Found {len(groups)} groups")
    for gid, gdata in list(groups.items())[:5]:
        print(f"  Group {gid}: {len(gdata.get('codes', {}))} codes, text={gdata['text'][:80]}...")

    n_groups, n_codes = build_data_module(groups, out_path)
    print(f"\nWrote {out_path}")
    print(f"  {n_groups} groups, {n_codes} total codes")
