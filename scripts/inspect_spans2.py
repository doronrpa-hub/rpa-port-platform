#!/usr/bin/env python3
"""Inspect individual spans within lines to see if word spacing is between spans or within spans."""

import fitz
import sys

pdf_path = sys.argv[1] if len(sys.argv) > 1 else "downloads/ExemptCustomsItems.pdf"
doc = fitz.open(pdf_path)

# Look at page 1 for lines with multiple spans where words might run together
for page_idx in range(min(3, doc.page_count)):
    page = doc[page_idx]
    raw = page.get_text("dict")
    print(f"\n{'='*60}")
    print(f"PAGE {page_idx + 1}")
    print(f"{'='*60}")

    for bi, blk in enumerate(raw["blocks"][:15]):
        if blk["type"] != 0:
            continue
        for li, line in enumerate(blk["lines"]):
            spans = line["spans"]
            if len(spans) < 2:
                continue  # Only look at multi-span lines

            lbbox = line["bbox"]
            print(f"\n  Block {bi} Line {li}: [{lbbox[0]:.1f}..{lbbox[2]:.1f}]")

            for si, span in enumerate(spans):
                sbbox = span["bbox"]
                text = span["text"]
                # Show gap from previous span
                gap_info = ""
                if si > 0:
                    prev_bbox = spans[si-1]["bbox"]
                    # In a page, x0 is left edge, x2 is right edge
                    # For RTL, spans go right-to-left
                    # Gap = prev_span.x0 - current_span.x2
                    gap_rtl = prev_bbox[0] - sbbox[2]
                    gap_ltr = sbbox[0] - prev_bbox[2]
                    gap_info = f" gap_rtl={gap_rtl:.1f} gap_ltr={gap_ltr:.1f}"

                # Check for garbled chars
                has_garbled = any(0x0B68 <= ord(c) <= 0x0B82 or 0x02A0 <= ord(c) <= 0x02BA for c in text)

                from pdf_to_xml import fix_garbled_hebrew
                fixed = fix_garbled_hebrew(text) if has_garbled else text

                print(f"    Span {si}: x=[{sbbox[0]:.1f}..{sbbox[2]:.1f}] size={span['size']:.1f}{gap_info}")
                print(f"      text: {repr(fixed[:60])}")

doc.close()
