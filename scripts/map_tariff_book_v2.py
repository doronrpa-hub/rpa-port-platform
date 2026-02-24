#!/usr/bin/env python3
"""
Map AllCustomsBookDataPDF.pdf — deeper analysis.

Phase 1: Dump text from key pages (TOC pages 1-15, and sample from middle/end)
Phase 2: Search with broader patterns
"""
import sys
import re
import fitz

PDF_PATH = "downloads/AllCustomsBookDataPDF.pdf"


def dump_pages(doc, page_nums, max_chars=2000):
    """Print text from specific pages."""
    for pn in page_nums:
        idx = pn - 1
        if idx < 0 or idx >= doc.page_count:
            continue
        page = doc[idx]
        text = page.get_text()
        print(f"\n{'='*70}")
        print(f"PAGE {pn} (of {doc.page_count})")
        print(f"{'='*70}")
        if len(text) > max_chars:
            print(text[:max_chars])
            print(f"\n... [truncated, {len(text)} chars total]")
        else:
            print(text)


def search_broad(doc):
    """Search with broader patterns across all pages."""
    patterns = {
        "תוספת": re.compile(r'תוספת'),
        "הנחה": re.compile(r'הנחה'),
        "SECTION": re.compile(r'SECTION|Section'),
        "CHAPTER": re.compile(r'CHAPTER|Chapter'),
        "חלק": re.compile(r'חלק\b'),
        "פרק": re.compile(r'פרק\b'),
        "supplement": re.compile(r'[Ss]upplement'),
        "addition": re.compile(r'[Aa]ddition'),
        "PART": re.compile(r'\bPART\b'),
    }

    results = {name: [] for name in patterns}

    for i in range(doc.page_count):
        if i % 500 == 0:
            print(f"  Broad scan: page {i+1}/{doc.page_count}...", file=sys.stderr)
        page = doc[i]
        text = page.get_text()
        for name, pat in patterns.items():
            if pat.search(text):
                results[name].append(i + 1)

    print("\n" + "=" * 70)
    print("BROAD SEARCH RESULTS")
    print("=" * 70)
    for name, pages in results.items():
        if pages:
            # Show ranges
            if len(pages) <= 10:
                print(f"  {name}: {pages}")
            else:
                print(f"  {name}: {len(pages)} pages, first={pages[0]}, last={pages[-1]}")
                # Show first 5 and last 5
                print(f"    first 5: {pages[:5]}")
                print(f"    last 5: {pages[-5:]}")
        else:
            print(f"  {name}: NOT FOUND")


def find_major_breaks(doc):
    """Find pages where the content style changes (likely section boundaries).
    Look for pages with very little text or large bold text."""
    breaks = []
    for i in range(doc.page_count):
        if i % 500 == 0:
            print(f"  Break scan: page {i+1}/{doc.page_count}...", file=sys.stderr)
        page = doc[i]
        text = page.get_text().strip()
        # Very short pages (< 200 chars) are likely section dividers
        if 5 < len(text) < 200:
            breaks.append((i + 1, len(text), text[:100].replace('\n', ' | ')))

    print("\n" + "=" * 70)
    print(f"SHORT PAGES (likely section boundaries): {len(breaks)} found")
    print("=" * 70)
    for pn, chars, preview in breaks[:80]:
        print(f"  Page {pn:5d} ({chars:3d} chars): {preview}")
    if len(breaks) > 80:
        print(f"  ... +{len(breaks)-80} more")


def main():
    print(f"Opening {PDF_PATH}...")
    doc = fitz.open(PDF_PATH)
    print(f"Total pages: {doc.page_count}")

    # Phase 1: Dump first 15 pages (TOC area)
    print("\n" + "#" * 70)
    print("PHASE 1: TABLE OF CONTENTS AREA (pages 1-15)")
    print("#" * 70)
    dump_pages(doc, range(1, 16), max_chars=3000)

    # Phase 2: Dump some pages from the end
    print("\n" + "#" * 70)
    print("PHASE 2: LAST 5 PAGES")
    print("#" * 70)
    dump_pages(doc, range(doc.page_count - 4, doc.page_count + 1), max_chars=2000)

    # Phase 3: Broad search
    print("\n" + "#" * 70)
    print("PHASE 3: BROAD SEARCH")
    print("#" * 70)
    search_broad(doc)

    # Phase 4: Find section breaks
    print("\n" + "#" * 70)
    print("PHASE 4: SECTION BOUNDARIES")
    print("#" * 70)
    find_major_breaks(doc)

    doc.close()


if __name__ == "__main__":
    main()
