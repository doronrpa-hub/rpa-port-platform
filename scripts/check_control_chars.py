#!/usr/bin/env python3
"""Find all control chars used in garbled PDF spans."""

import fitz
from collections import Counter

pdf_path = "downloads/ExemptCustomsItems.pdf"
doc = fitz.open(pdf_path)

ctrl_counter = Counter()
ctrl_contexts = {}

for page_idx in range(min(5, doc.page_count)):
    page = doc[page_idx]
    raw = page.get_text("dict")
    for blk in raw["blocks"]:
        if blk["type"] != 0:
            continue
        for line in blk["lines"]:
            for span in line["spans"]:
                text = span["text"]
                # Check for garbled fonts
                has_garbled = any(
                    0x0B68 <= ord(c) <= 0x0B82 or 0x02A0 <= ord(c) <= 0x02BA
                    for c in text
                )
                if not has_garbled:
                    continue
                for i, c in enumerate(text):
                    if ord(c) < 0x20 and c not in '\n\r\t':
                        ctrl_counter[f"U+{ord(c):04X}"] += 1
                        # Get context around it
                        start = max(0, i-3)
                        end = min(len(text), i+4)
                        ctx = repr(text[start:end])
                        if f"U+{ord(c):04X}" not in ctrl_contexts:
                            ctrl_contexts[f"U+{ord(c):04X}"] = []
                        if len(ctrl_contexts[f"U+{ord(c):04X}"]) < 3:
                            ctrl_contexts[f"U+{ord(c):04X}"].append(ctx)

doc.close()

print("Control chars in garbled spans (ExemptCustomsItems pages 1-5):")
for code, count in ctrl_counter.most_common():
    desc = {
        "U+0003": "ETX (End of Text) = WORD SEPARATOR",
        "U+000F": "SI (Shift In) = ??",
        "U+000B": "VT (Vertical Tab) = bracket open?",
        "U+000C": "FF (Form Feed) = bracket close?",
        "U+0010": "DLE = paren open?",
        "U+0011": "DC1 = paren close?",
        "U+001D": "GS = ??",
        "U+0005": "ENQ = geresh?",
        "U+001E": "RS = ??",
    }.get(code, "unknown")
    print(f"  {code}: {count:4d} occurrences — {desc}")
    for ctx in ctrl_contexts.get(code, []):
        print(f"         example: {ctx}")
