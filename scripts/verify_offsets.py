#!/usr/bin/env python3
"""Verify PDF page offset by checking a few known pages."""
import fitz
import re

PDF_PATH = "downloads/AllCustomsBookDataPDF.pdf"
doc = fitz.open(PDF_PATH)

# From TOC: "3069קודי הנחה" means internal page 3069 has discount codes
# From TOC: "3124תוספת שנייה" means internal page 3124 has Second Addition
# From TOC: "3135תוספת רביעית" means internal page 3135 has Fourth Addition

# Internal page number appears in footer: "NNNN  עמוד"
# Find the footer pattern to determine offset
footer_re = re.compile(r'הודפס בתאריך\s*(\d+)\s+עמוד')

# Check page 11 (should be internal page 1 = צו מסגרת start)
for pdf_page in [11, 15, 3079, 3080, 3134, 3135, 3145, 3146]:
    idx = pdf_page - 1
    if idx >= doc.page_count:
        print(f"PDF page {pdf_page}: OUT OF RANGE")
        continue
    page = doc[idx]
    text = page.get_text()
    m = footer_re.search(text)
    internal = m.group(1) if m else "NO FOOTER"
    preview = text[:150].replace('\n', ' | ')
    print(f"PDF page {pdf_page} = internal page {internal}")
    print(f"  Preview: {preview}")
    print()

doc.close()
