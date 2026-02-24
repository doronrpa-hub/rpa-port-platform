#!/usr/bin/env python3
"""Verify supplement boundaries by checking actual content at TOC-listed pages."""
import fitz

PDF_PATH = "downloads/AllCustomsBookDataPDF.pdf"
doc = fitz.open(PDF_PATH)

# TOC from pages 9-10 (internal page numbers):
TOC_ENTRIES = {
    "צו מסגרת": 1,
    "חלק I": 23,
    "קודי הנחה": 3069,
    "תוספת שנייה": 3124,
    "תוספת שלישית": 3125,
    "תוספת רביעית": 3135,
    "תוספת חמישית": 3162,
    "תוספת שישית": 3170,
    "תוספת שביעית": 3188,
    "תוספת שמינית": 3242,
    "תוספת תשיעית": 3247,
    "תוספת עשירית": 3251,
    "תוספת ארבע עשר": 3272,
    "תוספת חמש עשר": 3355,
    "תוספת שש עשר": 3379,
    "תוספת שבע עשר": 4113,
    "תוספת שמונה עשרה": 4139,
    "תוספת תשע עשרה": 4791,
}

OFFSET = 10  # PDF page = internal page + 10

for name, internal_page in TOC_ENTRIES.items():
    pdf_page = internal_page + OFFSET
    idx = pdf_page - 1
    if idx >= doc.page_count:
        print(f"  {name}: internal={internal_page}, pdf={pdf_page} — OUT OF RANGE")
        continue
    page = doc[idx]
    text = page.get_text()
    # Show first 200 chars
    preview = text[:200].replace('\n', ' | ')
    print(f"  {name}: internal={internal_page}, pdf={pdf_page}")
    print(f"    Content: {preview}")
    print()

# Also check what's on the LAST page
last_name = "תוספת תשע עשרה"
last_internal = 4791
# Check a few pages after the last supplement to see where content ends
for i in [4791, 4800, 4900, 5000, 5100, 5200, 5300, 5400, 5500, 5530]:
    pdf_page = i + OFFSET
    idx = pdf_page - 1
    if idx >= doc.page_count:
        print(f"  Internal {i}, pdf {pdf_page}: OUT OF RANGE (max={doc.page_count})")
        continue
    page = doc[idx]
    text = page.get_text()
    preview = text[:80].replace('\n', ' | ')
    print(f"  Internal {i}, pdf {pdf_page}: {preview}")

doc.close()
