#!/usr/bin/env python3
"""Trace what happens to \x03 spacing chars through fix_garbled_hebrew."""

import sys
sys.path.insert(0, "scripts")
from pdf_to_xml import fix_garbled_hebrew, _fix_rtl_visual_order, _GARBLED_TRANS

# Test with the actual garbled text from ExemptCustomsItems Block 0 Line 0 Span 0 (Segoe UI)
test1 = '\u0b6c\u0b69\u0b78\u0b6c\x03\u0b71\u0b6b\u0b6d\u0b7f'  # "הנחה קודי" garbled
print("=== Test 1: Segoe UI garbled (קודי הנחה) ===")
print(f"  Input: {repr(test1)}")
step1 = test1.translate(_GARBLED_TRANS)
print(f"  After translate: {repr(step1)}")
step2 = _fix_rtl_visual_order(step1)
print(f"  After RTL fix:   {repr(step2)}")
result = fix_garbled_hebrew(test1)
print(f"  Final result:    {repr(result)}")

# Test with Arial garbled text from Block 1 Line 0 Span 0
test2 = '\u02ba\u02a9\u02a8\u02b1\u02a9\u02a8\u02a8\u02b1\x03\u02a4\u02a3\u02a9\u02a7\u02a9'  # "יחידה סטטיסטית" garbled
print("\n=== Test 2: Arial garbled (יחידה סטטיסטית) ===")
print(f"  Input: {repr(test2)}")
step1 = test2.translate(_GARBLED_TRANS)
print(f"  After translate: {repr(step1)}")
step2 = _fix_rtl_visual_order(step1)
print(f"  After RTL fix:   {repr(step2)}")
result = fix_garbled_hebrew(test2)
print(f"  Final result:    {repr(result)}")

# Show what \x03 translates to
print(f"\n  \\x03 in _GARBLED_TRANS? {chr(0x03) in dict([(chr(k), v) for k, v in enumerate(range(256))])}")
print(f"  chr(3) translate result: {repr(chr(3).translate(_GARBLED_TRANS))}")

# Bigger test from Block 4 Line 2
test3 = '\x0b\u02a4\u02b0\u02ba\u02b5\u02ae\x0c\x03\u02a4\u02b0\u02a9\u02a3\u02ae\u02a4\x03\u02a0\u02a9\u02b9\u02b0\x03\u02b9\u02b5\u02ae\u02a9\u02b9\u02ac\x03\x0f\u02a9\u02b5\u02b9\u02b8\x03\u02b0\u02b1\u02a7\u02ae\u02a1\x03\u02b5\u02b9\u02ab\u02b8\u02b0\u02b9\x03\u02b5\u02a0\x03\u02b5\u02a0\u02a1\u02b5\u02a9\u02b9\x03\u02b0\u02a9\u02a1\u02b5\u02a8'
print("\n=== Test 3: Full garbled line ===")
print(f"  Input: {repr(test3[:40])}")
result = fix_garbled_hebrew(test3)
print(f"  Final result:    {repr(result)}")
print(f"  Readable:        {result}")
