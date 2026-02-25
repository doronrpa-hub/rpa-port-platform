#!/usr/bin/env python3
"""Inspect TradeAgreement109 to see why Hebrew is garbled."""

import fitz

doc = fitz.open("downloads/TradeAgreement109.pdf")
page = doc[0]
raw = page.get_text("dict")

for bi, blk in enumerate(raw["blocks"][:5]):
    if blk["type"] != 0:
        continue
    for li, line in enumerate(blk["lines"]):
        for si, span in enumerate(line["spans"]):
            text = span["text"]
            if not text.strip():
                continue
            # Show first 40 chars as hex codes
            hex_codes = ' '.join(f'{ord(c):04X}' for c in text[:30])
            has_hebrew = any('\u05D0' <= c <= '\u05EA' for c in text)
            has_garbled = any(0x0B68 <= ord(c) <= 0x0B82 or 0x02A0 <= ord(c) <= 0x02BA for c in text)
            has_fffd = '\ufffd' in text
            print(f"Block {bi} Line {li} Span {si}: font={span['font']} size={span['size']:.1f}")
            print(f"  text: {repr(text[:60])}")
            print(f"  hex:  {hex_codes}")
            print(f"  hebrew={has_hebrew} garbled={has_garbled} fffd={has_fffd}")
            print()

doc.close()
