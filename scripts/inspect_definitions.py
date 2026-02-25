#!/usr/bin/env python3
"""Find actual definition patterns in FrameOrder.pdf."""

import fitz
import sys
sys.path.insert(0, "scripts")
from pdf_to_xml import fix_garbled_hebrew

doc = fitz.open("downloads/FrameOrder.pdf")

# Search pages 1-4 for definition-like text
for page_idx in range(min(5, doc.page_count)):
    page = doc[page_idx]
    raw = page.get_text("dict")
    print(f"\n{'='*60}")
    print(f"PAGE {page_idx + 1}")
    print(f"{'='*60}")

    for bi, blk in enumerate(raw["blocks"]):
        if blk["type"] != 0:
            continue
        for li, line in enumerate(blk["lines"]):
            for si, span in enumerate(line["spans"]):
                text = span["text"]
                fixed = fix_garbled_hebrew(text)
                # Look for definition-related keywords
                if any(kw in fixed for kw in ['"', '״', '""', 'הגדרות', 'דולר', 'הסכם', 'שער', 'משמע']):
                    bold = "BOLD" if "Bold" in span["font"] or "bold" in span["font"].lower() else ""
                    print(f"\n  Block {bi} Line {li} Span {si}: {bold} font={span['font']} size={span['size']:.1f}")
                    print(f"    text: {repr(fixed[:120])}")
                    # Show raw hex for quote chars
                    for i, c in enumerate(text):
                        if c in '""\u201c\u201d\u201e\u201f\u05f4\u05f3\u2018\u2019\u00ab\u00bb':
                            print(f"    Quote char at pos {i}: U+{ord(c):04X} = {c}")

doc.close()
