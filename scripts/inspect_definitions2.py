#!/usr/bin/env python3
"""Show full block text for definition blocks in FrameOrder.pdf."""

import fitz
import sys
sys.path.insert(0, "scripts")
from pdf_to_xml import extract_page_blocks, classify_block

doc = fitz.open("downloads/FrameOrder.pdf")

for page_idx in range(min(3, doc.page_count)):
    print(f"\n{'='*60}")
    print(f"PAGE {page_idx + 1}")
    print(f"{'='*60}")

    blocks = extract_page_blocks(doc, page_idx)

    for bi, block in enumerate(blocks):
        text = block.text
        # Look for definition-related content
        if '""' in text or 'הגדרות' in text:
            btype, extra = classify_block(block)
            print(f"\n  Block {bi}: type={btype}, extra={extra}, bold={block.is_bold}, size={block.max_size:.1f}")
            print(f"    text (first 200 chars): {repr(text[:200])}")
            # Count double-quote pairs
            dq_count = text.count('""')
            print(f"    double-quote pairs: {dq_count}")

doc.close()
