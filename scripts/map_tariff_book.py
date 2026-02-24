#!/usr/bin/env python3
"""
Map AllCustomsBookDataPDF.pdf — find page ranges for supplements and discount codes.

Searches every page for target Hebrew terms and reports first/last occurrence pages.
"""
import sys
import fitz  # PyMuPDF

PDF_PATH = "downloads/AllCustomsBookDataPDF.pdf"

# Terms to search for — in order
SEARCH_TERMS = [
    "תוספת ראשונה",
    "תוספת שנייה",
    "תוספת שניה",
    "תוספת שלישית",
    "תוספת רביעית",
    "תוספת חמישית",
    "תוספת שישית",
    "תוספת שביעית",
    "תוספת שמינית",
    "תוספת תשיעית",
    "תוספת עשירית",
    "תוספת אחת עשרה",
    "תוספת שתים עשרה",
    "תוספת שלוש עשרה",
    "תוספת ארבע עשרה",
    "תוספת חמש עשרה",
    "תוספת שש עשרה",
    "תוספת שבע עשרה",
    "קודי הנחה",
    "קוד הנחה",
    "DiscountCode",
]

# Also search for section/chapter headers to get full TOC
SECTION_TERMS = [
    "חלק I",
    "חלק II",
    "חלק III",
    "חלק IV",
    "חלק V",
    "חלק VI",
    "חלק VII",
    "חלק VIII",
    "חלק IX",
    "חלק X",
    "חלק XI",
    "חלק XII",
    "חלק XIII",
    "חלק XIV",
    "חלק XV",
    "חלק XVI",
    "חלק XVII",
    "חלק XVIII",
    "חלק XIX",
    "חלק XX",
    "חלק XXI",
    "חלק XXII",
]


def main():
    print(f"Opening {PDF_PATH}...")
    doc = fitz.open(PDF_PATH)
    total = doc.page_count
    print(f"Total pages: {total}")
    print()

    # Collect results: term -> list of page numbers (1-indexed)
    results = {t: [] for t in SEARCH_TERMS}
    section_results = {t: [] for t in SECTION_TERMS}

    # Scan every page
    for i in range(total):
        if i % 200 == 0:
            print(f"  Scanning page {i+1}/{total}...", file=sys.stderr)
        page = doc[i]
        text = page.get_text()

        for term in SEARCH_TERMS:
            if term in text:
                results[term].append(i + 1)

        for term in SECTION_TERMS:
            if term in text:
                section_results[term].append(i + 1)

    doc.close()

    # Print results
    print("=" * 70)
    print("SUPPLEMENT SEARCH RESULTS")
    print("=" * 70)
    for term in SEARCH_TERMS:
        pages = results[term]
        if pages:
            first = pages[0]
            last = pages[-1]
            count = len(pages)
            if count == 1:
                print(f"  {term}: page {first}")
            else:
                print(f"  {term}: pages {first}-{last} ({count} pages)")
        else:
            print(f"  {term}: NOT FOUND")

    print()
    print("=" * 70)
    print("SECTION SEARCH RESULTS (for context)")
    print("=" * 70)
    for term in SECTION_TERMS:
        pages = section_results[term]
        if pages:
            print(f"  {term}: first at page {pages[0]}, {len(pages)} occurrences")
        else:
            print(f"  {term}: NOT FOUND")

    # Also dump raw page numbers for detailed analysis
    print()
    print("=" * 70)
    print("RAW PAGE LISTS")
    print("=" * 70)
    for term in SEARCH_TERMS:
        pages = results[term]
        if pages:
            # Show first 20 pages
            shown = pages[:20]
            extra = f" ... +{len(pages)-20} more" if len(pages) > 20 else ""
            print(f"  {term}: {shown}{extra}")


if __name__ == "__main__":
    main()
