#!/usr/bin/env python3
"""Check where words run together in ThirdAddition.pdf."""

import fitz
import sys
sys.path.insert(0, "scripts")
from pdf_to_xml import fix_garbled_hebrew

pdf_path = "downloads/ThirdAddition.pdf"
doc = fitz.open(pdf_path)

# Look at multiple pages for garbled text
for page_idx in range(min(3, doc.page_count)):
    page = doc[page_idx]
    raw = page.get_text("dict")
    print(f"\n{'='*60}")
    print(f"PAGE {page_idx + 1}")
    print(f"{'='*60}")

    for bi, blk in enumerate(raw["blocks"]):
        if blk["type"] != 0:
            continue
        for li, line in enumerate(blk["lines"]):
            spans = line["spans"]
            # Show each span's raw bytes to find spacing chars
            for si, span in enumerate(spans):
                text = span["text"]
                # Only show spans with garbled chars
                has_garbled = any(0x0B68 <= ord(c) <= 0x0B82 or 0x02A0 <= ord(c) <= 0x02BA for c in text)
                if not has_garbled:
                    continue
                # Show raw char codes
                fixed = fix_garbled_hebrew(text)
                hexcodes = ' '.join(f'{ord(c):04X}' for c in text[:40])
                print(f"\n  Block {bi} Line {li} Span {si}:")
                print(f"    fixed: {repr(fixed[:60])}")
                print(f"    raw hex: {hexcodes}")
                # Check for any space-like chars
                space_chars = [(i, f'U+{ord(c):04X}') for i, c in enumerate(text) if c in ' \t\x03\x00\xa0\u200b\u200c\u200d\u2009\u200a']
                if space_chars:
                    print(f"    space-like chars at: {space_chars}")
                else:
                    print(f"    NO space-like chars found in {len(text)} chars")

doc.close()
