#!/usr/bin/env python3
"""Inspect span bbox data from a garbled-font PDF to understand word spacing."""

import fitz
import sys

pdf_path = sys.argv[1] if len(sys.argv) > 1 else "downloads/ThirdAddition.pdf"
doc = fitz.open(pdf_path)

for page_idx in range(min(2, doc.page_count)):
    page = doc[page_idx]
    raw = page.get_text("dict")
    print(f"\n{'='*60}")
    print(f"PAGE {page_idx + 1}")
    print(f"{'='*60}")

    for bi, blk in enumerate(raw["blocks"][:8]):
        if blk["type"] != 0:
            continue
        bbox = blk["bbox"]
        print(f"\n--- Block {bi} bbox=[{bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f}] ---")
        for li, line in enumerate(blk["lines"]):
            lbbox = line["bbox"]
            print(f"  Line {li}: bbox=[{lbbox[0]:.1f}, {lbbox[1]:.1f}, {lbbox[2]:.1f}, {lbbox[3]:.1f}]")
            prev_span_end = None
            for si, span in enumerate(line["spans"]):
                sbbox = span["bbox"]
                gap = ""
                if prev_span_end is not None:
                    # Gap between end of previous span and start of this span
                    # For RTL text, x0 of current < x2 of previous means overlap
                    gap_px = prev_span_end - sbbox[2]  # RTL: previous x0 - current x2
                    gap = f" GAP={gap_px:.1f}px"
                prev_span_end = sbbox[0]
                text = span["text"]
                print(f"    Span {si}: font={span['font']}, size={span['size']:.1f}, "
                      f"x=[{sbbox[0]:.1f}..{sbbox[2]:.1f}]{gap}")
                print(f"      raw:   {repr(text[:60])}")
                # Show fixed text
                from pdf_to_xml import fix_garbled_hebrew
                fixed = fix_garbled_hebrew(text)
                if fixed != text:
                    print(f"      fixed: {repr(fixed[:60])}")

doc.close()
