#!/usr/bin/env python3
"""Check ExemptCustomsItems.pdf for control char spacing."""

import fitz

pdf_path = "downloads/ExemptCustomsItems.pdf"
doc = fitz.open(pdf_path)

page = doc[0]
raw = page.get_text("dict")

print("EXAMINING CONTROL CHARS IN EXEMPTCUSTOMSITEMS PAGE 1")
print("=" * 60)

for bi, blk in enumerate(raw["blocks"][:6]):
    if blk["type"] != 0:
        continue
    for li, line in enumerate(blk["lines"]):
        for si, span in enumerate(line["spans"]):
            text = span["text"]
            # Show all non-printable chars
            has_control = any(ord(c) < 0x20 and c not in '\n\r\t' for c in text)
            has_garbled = any(0x0B68 <= ord(c) <= 0x0B82 or 0x02A0 <= ord(c) <= 0x02BA for c in text)

            if not has_garbled and not has_control:
                continue

            print(f"\nBlock {bi} Line {li} Span {si}:")
            print(f"  font: {span['font']}, size: {span['size']}")
            print(f"  raw text repr: {repr(text[:80])}")

            # Show char by char with hex
            chars = []
            for c in text[:60]:
                if ord(c) < 0x20:
                    chars.append(f"[{ord(c):02X}]")
                elif 0x0B68 <= ord(c) <= 0x0B82:
                    chars.append(f"G({chr(ord(c)-0x0598)})")
                elif 0x02A0 <= ord(c) <= 0x02BA:
                    chars.append(f"G({chr(ord(c)-0x02A0+0x05D0)})")
                else:
                    chars.append(c)
            print(f"  decoded: {''.join(chars)}")

doc.close()
