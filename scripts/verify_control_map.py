#!/usr/bin/env python3
"""Verify control char meanings by comparing with known text."""

import sys
sys.path.insert(0, "scripts")
from pdf_to_xml import fix_garbled_hebrew

# From ExemptCustomsItems page 1, Block 3 Line 0 Span 2:
# Raw: '\x10\x03ʦ\x05ʩʹʺ\x03\x0f\x0bʣʧʥʩʮ\x03ʸʥʨʴ\x03ʬʥʨʩʡ\x0c\x03ʤʩʰʷʤ'
# Expected: "הקניה, ביטול פטור מיוחד, (תשי"ז)"
# After RTL fix we'd see the Hebrew reversed

test = '\x10\x03\u02a6\x05\u02a9\u02b9\u02ba\x03\x0f\x0b\u02a3\u02a7\u02b5\u02a9\u02ae\x03\u02b8\u02b5\u02a8\u02b4\x03\u02ac\u02b5\u02a8\u02a9\u02a1\x0c\x03\u02a4\u02a9\u02b0\u02b7\u02a4'
result = fix_garbled_hebrew(test)
print(f"Result: {result}")
print(f"Repr:   {repr(result)}")

# From Block 2 Line 0 Span 0 (longer sentence):
# Expected: "± טובין המיועדים למפורטים בתוספת לחוק המכס(הבלו) ומס ."
# Control chars should map to punctuation
test2 = '\x03\u02b1\u02ae\u02b5\x03\u02b5\u02ac\u02a1\u02a4\x03\x0f\u02b1\u02ab\u02ae\u02a4\x03\u02b7\u02b5\u02a7\u02ac\x03\u02ba\u02b4\u02b1\u02b5\u02ba\u02a1\x03\u02ad\u02a9\u02a8\u02b8\u02b5\u02b4\u02ae\u02ac\x03\u02ad\u02a9\u02a3\u02b9\u02b5\u02a9\u02ae\u02a4\x03\u02b0\u02a9\u02a1\u02b5\u02a8\x03\u00b1\x03'
result2 = fix_garbled_hebrew(test2)
print(f"\nResult2: {result2}")
print(f"Repr2:   {repr(result2)}")

# Control char \x05 test - geresh?
# From "ʦ\x05ʩʹʺ" which should be "תשי"ז" (Hebrew year abbreviation)
# \x05 = gershayim (double quote ") used in Hebrew abbreviations
test3 = '\u02a6\x05\u02a9\u02b9\u02ba'
result3 = fix_garbled_hebrew(test3)
print(f"\nGeresh test: {repr(test3)} -> {repr(result3)}")
print(f"  Expected: תשי\"ז or תשי׳ז")

# Control char \x0b/\x0c test - parentheses?
# From "\x0bʠ\x0c" which should be "(א)"
test4 = '\x0b\u02a0\x0c'
result4 = fix_garbled_hebrew(test4)
print(f"\nParen test: {repr(test4)} -> {repr(result4)}")
print(f"  Expected: (א)")

# Control char \x0f test
# From "ʡʤ\x03\x0fʱʫʮ" context
test5 = '\u02a1\u02a4\x03\x0f\u02b1\u02ab\u02ae'
result5 = fix_garbled_hebrew(test5)
print(f"\n\\x0f test: {repr(test5)} -> {repr(result5)}")
