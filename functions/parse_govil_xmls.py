# -*- coding: utf-8 -*-
"""
parse_govil_xmls.py — Parse ALL FTA XML files from downloads/govil/ and generate
two Python data files:

  1. functions/lib/_fta_all_countries_GENERATED.py  — FTA data with full text
  2. functions/lib/_approved_exporter_GENERATED.py  — Approved exporter procedure

Usage:
    cd functions && python parse_govil_xmls.py

Reads 146 XML files matching downloads/govil/FTA_*.xml.
"""

import glob
import os
import re
import sys
import textwrap
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GOVIL_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "downloads", "govil")
OUTPUT_FTA = os.path.join(SCRIPT_DIR, "lib", "_fta_all_countries_GENERATED.py")
OUTPUT_APPROVED = os.path.join(SCRIPT_DIR, "lib", "_approved_exporter_GENERATED.py")

# Max full_text size for inclusion in generated file (100 KB)
MAX_FULL_TEXT = 100_000
# For very large docs, store first N chars
LARGE_DOC_PREVIEW = 2000

# ---------------------------------------------------------------------------
# Document type classification patterns (matching existing _fta_all_countries.py)
# ---------------------------------------------------------------------------
_DOC_TYPE_PATTERNS = [
    # Origin rules & proof — most specific first
    (re.compile(r"eur1|EUR\.1|eur-1|makor-example", re.I), "eur1"),
    (re.compile(r"approved.exporter|יצואן.מאושר|nohal.misim", re.I), "approved_exporter"),
    (re.compile(r"teodat.makor|milui.makor", re.I), "certificate"),
    (re.compile(r"makor|origin|rules.of.origin|כללי.מקור|תעודת.מקור", re.I), "origin"),
    # Benefits / concessions
    (re.compile(r"benefits?.from.isr|export.from.israel|exp.+(?:benefit|concess)|export.benefit", re.I), "benefits_export"),
    (re.compile(r"benefits?.to.isr|import.to.israel|import.benefit|import.concess", re.I), "benefits_import"),
    (re.compile(r"benefit|concession|הטבות|Tariff.Schedule", re.I), "benefits_schedule"),
    # Protocols, annexes
    (re.compile(r"[Pp]rotocol|פרוטוקול", re.I), "protocol"),
    (re.compile(r"annex|Annex|נספח|appendix", re.I), "annex"),
    # Agriculture
    (re.compile(r"agri|agriculture|חקלאות", re.I), "agri"),
    # MRA
    (re.compile(r"[Mm]utual.?[Rr]ecognition|mra", re.I), "mra"),
    # Committee decisions
    (re.compile(r"committee|joint|ועדה|[Dd]ecision", re.I), "joint_committee"),
    # Agreement text — language-specific
    (re.compile(r"(?:agreement|agree|fta|הסכם).+(?:-en|_en|EN|[Ee]ng)", re.I), "agreement_en"),
    (re.compile(r"(?:-en|_en|EN|[Ee]ng).+(?:agreement|agree|fta)", re.I), "agreement_en"),
    (re.compile(r"(?:agreement|agree|fta|הסכם).+(?:-he|_he|HE|HEB)", re.I), "agreement_he"),
    (re.compile(r"(?:-he|_he|HE|HEB).+(?:agreement|agree|fta)", re.I), "agreement_he"),
    # Reviews, summaries, explanations
    (re.compile(r"review|economic.review|סקירה", re.I), "review"),
    (re.compile(r"summ|summary|תקציר|breif|brief", re.I), "summary"),
    (re.compile(r"exp\b|hesber|explanat|הסבר", re.I), "explanation"),
    (re.compile(r"intro|introduction|מבוא", re.I), "intro"),
    (re.compile(r"tech.guide|guide", re.I), "technical_guide"),
    (re.compile(r"update|correction|תיקון", re.I), "update"),
    (re.compile(r"procedure|shitun|נוהל", re.I), "procedure"),
    (re.compile(r"exit|preparation|הכנה", re.I), "preparation"),
    (re.compile(r"regional.convention|אמנה.אזורית", re.I), "regional_convention"),
    (re.compile(r"transfer|loading|העמסה|העברה", re.I), "transfer_rules"),
    (re.compile(r"intellectual|property|קניין.רוחני", re.I), "intellectual_property"),
    (re.compile(r"memorandum|דברי.הסבר", re.I), "explanatory_memorandum"),
    # Generic agreement (last resort before 'other')
    (re.compile(r"agreement|agree|הסכם|fta\b", re.I), "agreement_text"),
    (re.compile(r"table|טבלה|schedule", re.I), "tariff_table"),
]


def classify_doc(filename):
    """Classify a filename into a document type string."""
    for pattern, doc_type in _DOC_TYPE_PATTERNS:
        if pattern.search(filename):
            return doc_type
    return "other"


# ---------------------------------------------------------------------------
# XML Parsing
# ---------------------------------------------------------------------------

def parse_xml_file(filepath):
    """Parse a single govil XML file.

    Returns dict with:
        name, source_file, pages, language, direction,
        full_text, first_title, char_count
    or None on parse failure.
    """
    try:
        tree = ET.parse(filepath)
    except ET.ParseError as e:
        print(f"  WARNING: XML parse error in {os.path.basename(filepath)}: {e}")
        return None

    root = tree.getroot()

    # Document-level attributes
    name = root.get("name", "")
    source_file = root.get("source_file", os.path.basename(filepath))
    pages_str = root.get("pages", "0")
    try:
        pages = int(pages_str)
    except (ValueError, TypeError):
        pages = 0
    language = root.get("language", "he")
    direction = root.get("direction", "rtl")

    # Extract text from all <title> and <paragraph> elements
    text_parts = []
    first_title = ""
    current_page = None

    body = root.find("body")
    if body is None:
        # Try root-level pages
        body = root

    for page_elem in body.iter("page"):
        page_num = page_elem.get("number", "")
        if current_page is not None and page_num != current_page:
            text_parts.append("")  # Page break as blank line
        current_page = page_num

        for child in page_elem:
            text = child.text or ""
            text = text.strip()
            if not text:
                continue

            if child.tag == "title":
                if not first_title:
                    first_title = text
                text_parts.append(text)
            elif child.tag == "paragraph":
                text_parts.append(text)

    full_text = "\n".join(text_parts)

    # Clean up excessive whitespace but preserve structure
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)

    return {
        "name": name,
        "source_file": source_file,
        "pages": pages,
        "language": language,
        "direction": direction,
        "full_text": full_text,
        "first_title": first_title,
        "char_count": len(full_text),
    }


def extract_country_code(filename):
    """Extract country code from filename like FTA_{country}_sahar-hutz_..."""
    m = re.match(r"FTA_([a-z]+)_", filename, re.I)
    if m:
        return m.group(1).lower()
    return None


# ---------------------------------------------------------------------------
# Existing metadata from current _fta_all_countries.py
# (hardcoded here so we don't import it — keep script self-contained)
# ---------------------------------------------------------------------------
EXISTING_METADATA = {
    "eu": {
        "name_he": "האיחוד האירופי",
        "name_en": "European Union",
        "agreement_name_he": "הסכם שיתוף ישראל-קהילה האירופית",
        "agreement_name_en": "Euro-Mediterranean Association Agreement",
        "agreement_year": 1995,
        "effective_date": "2000-06-01",
        "origin_proof": "EUR.1",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Pan-Euro-Med diagonal cumulation",
        "cumulation_countries": [
            "EU", "EFTA", "Turkey", "Jordan", "Egypt", "Tunisia",
            "Morocco", "Algeria", "Lebanon", "Syria", "West Bank/Gaza",
            "Faeroe Islands",
        ],
        "value_threshold_eur": 6000,
    },
    "uk": {
        "name_he": "הממלכה המאוחדת",
        "name_en": "United Kingdom",
        "agreement_name_he": "הסכם סחר ושותפות ישראל-בריטניה",
        "agreement_name_en": "Israel-UK Trade and Partnership Agreement",
        "agreement_year": 2019,
        "effective_date": "2021-01-01",
        "origin_proof": "EUR.1",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Bilateral + EU materials (transitional)",
        "cumulation_countries": ["UK", "EU (transitional)"],
        "value_threshold_eur": 6000,
    },
    "efta": {
        "name_he": 'אפט"א',
        "name_en": "EFTA",
        "member_states": ["Iceland", "Liechtenstein", "Norway", "Switzerland"],
        "member_states_he": ["איסלנד", "ליכטנשטיין", "נורבגיה", "שוויץ"],
        "agreement_name_he": 'הסכם סחר חופשי ישראל-אפט"א',
        "agreement_name_en": "Israel-EFTA Free Trade Agreement",
        "agreement_year": 1992,
        "effective_date": "1993-01-01",
        "origin_proof": "EUR.1",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Pan-Euro-Med diagonal cumulation",
        "cumulation_countries": [
            "EFTA", "EU", "Turkey", "Jordan", "Egypt", "Tunisia",
            "Morocco", "Faeroe Islands",
        ],
        "value_threshold_eur": 6000,
    },
    "turkey": {
        "name_he": "טורקיה",
        "name_en": "Turkey",
        "agreement_name_he": "הסכם סחר חופשי ישראל-טורקיה",
        "agreement_name_en": "Israel-Turkey Free Trade Agreement",
        "agreement_year": 1996,
        "effective_date": "1997-05-01",
        "origin_proof": "EUR.1",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Pan-Euro-Med diagonal cumulation",
        "cumulation_countries": ["Turkey", "EU", "EFTA"],
        "value_threshold_eur": 6000,
    },
    "jordan": {
        "name_he": "ירדן",
        "name_en": "Jordan",
        "agreement_name_he": "הסכם סחר חופשי ישראל-ירדן",
        "agreement_name_en": "Israel-Jordan Free Trade Agreement",
        "agreement_year": 1995,
        "effective_date": "1995-10-29",
        "origin_proof": "EUR.1",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Pan-Euro-Med diagonal cumulation",
        "cumulation_countries": ["Jordan", "EU", "EFTA", "Turkey"],
        "value_threshold_eur": 6000,
    },
    "usa": {
        "name_he": "ארצות הברית",
        "name_en": "United States",
        "agreement_name_he": 'הסכם סחר חופשי ישראל-ארה"ב',
        "agreement_name_en": "Israel-US Free Trade Area Agreement",
        "agreement_year": 1985,
        "effective_date": "1985-09-01",
        "origin_proof": "Invoice Declaration",
        "has_invoice_declaration": True,
        "has_approved_exporter": False,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["USA"],
        "value_threshold_usd": None,
    },
    "ukraine": {
        "name_he": "אוקראינה",
        "name_en": "Ukraine",
        "agreement_name_he": "הסכם סחר חופשי ישראל-אוקראינה",
        "agreement_name_en": "Israel-Ukraine Free Trade Agreement",
        "agreement_year": 2019,
        "effective_date": "2021-01-01",
        "origin_proof": "EUR.1",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Bilateral + PEM Convention",
        "cumulation_countries": ["Ukraine"],
        "value_threshold_eur": 6000,
    },
    "canada": {
        "name_he": "קנדה",
        "name_en": "Canada",
        "agreement_name_he": "הסכם סחר חופשי ישראל-קנדה",
        "agreement_name_en": "Canada-Israel Free Trade Agreement (CIFTA)",
        "agreement_year": 1997,
        "effective_date": "1997-01-01",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": False,
        "has_approved_exporter": False,
        "cumulation": "Bilateral only + US materials (special provision)",
        "cumulation_countries": ["Canada", "USA (limited)"],
    },
    "mexico": {
        "name_he": "מקסיקו",
        "name_en": "Mexico",
        "agreement_name_he": "הסכם סחר חופשי ישראל-מקסיקו",
        "agreement_name_en": "Israel-Mexico Free Trade Agreement",
        "agreement_year": 2000,
        "effective_date": "2000-07-01",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": False,
        "has_approved_exporter": False,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["Mexico"],
    },
    "colombia": {
        "name_he": "קולומביה",
        "name_en": "Colombia",
        "agreement_name_he": "הסכם סחר חופשי ישראל-קולומביה",
        "agreement_name_en": "Israel-Colombia Free Trade Agreement",
        "agreement_year": 2020,
        "effective_date": "2020-08-11",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": True,
        "has_approved_exporter": False,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["Colombia"],
    },
    "panama": {
        "name_he": "פנמה",
        "name_en": "Panama",
        "agreement_name_he": "הסכם סחר חופשי ישראל-פנמה",
        "agreement_name_en": "Israel-Panama Free Trade Agreement",
        "agreement_year": 2018,
        "effective_date": "2019-12-30",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": False,
        "has_approved_exporter": False,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["Panama"],
    },
    "guatemala": {
        "name_he": "גואטמלה",
        "name_en": "Guatemala",
        "agreement_name_he": "הסכם סחר חופשי ישראל-גואטמלה",
        "agreement_name_en": "Israel-Guatemala Free Trade Agreement",
        "agreement_year": 2022,
        "effective_date": "2023-01-06",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": False,
        "has_approved_exporter": False,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["Guatemala"],
    },
    "korea": {
        "name_he": "קוריאה",
        "name_en": "South Korea",
        "agreement_name_he": "הסכם סחר חופשי ישראל-קוריאה",
        "agreement_name_en": "Israel-Korea Free Trade Agreement",
        "agreement_year": 2021,
        "effective_date": "2022-12-01",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["South Korea"],
    },
    "mercosur": {
        "name_he": "מרקוסור",
        "name_en": "Mercosur",
        "member_states": ["Argentina", "Brazil", "Paraguay", "Uruguay"],
        "member_states_he": ["ארגנטינה", "ברזיל", "פרגוואי", "אורוגוואי"],
        "agreement_name_he": "הסכם סחר חופשי ישראל-מרקוסור",
        "agreement_name_en": "Israel-Mercosur Free Trade Agreement",
        "agreement_year": 2007,
        "effective_date": "2010-06-01",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": False,
        "has_approved_exporter": False,
        "cumulation": "Bilateral (Mercosur bloc treated as single territory)",
        "cumulation_countries": ["Argentina", "Brazil", "Paraguay", "Uruguay"],
    },
    "uae": {
        "name_he": "איחוד האמירויות",
        "name_en": "United Arab Emirates",
        "agreement_name_he": "הסכם שותפות כלכלית מקיף ישראל-איחוד האמירויות",
        "agreement_name_en": "Israel-UAE Comprehensive Economic Partnership Agreement (CEPA)",
        "agreement_year": 2022,
        "effective_date": "2023-04-01",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["UAE"],
    },
    "vietnam": {
        "name_he": "וייטנאם",
        "name_en": "Vietnam",
        "agreement_name_he": "הסכם סחר חופשי ישראל-וייטנאם",
        "agreement_name_en": "Israel-Vietnam Free Trade Agreement (VIFTA)",
        "agreement_year": 2023,
        "effective_date": "2025-01-15",
        "origin_proof": "Certificate of Origin",
        "has_invoice_declaration": True,
        "has_approved_exporter": True,
        "cumulation": "Bilateral only",
        "cumulation_countries": ["Vietnam"],
    },
}

# Doc types that get full_text included (if under 100KB)
FULL_TEXT_DOC_TYPES = {
    "origin", "eur1", "approved_exporter", "protocol", "certificate",
    "agreement_en", "agreement_he", "agreement_text",
    "procedure", "regional_convention", "joint_committee",
    "explanation", "intro", "summary", "review",
    "mra", "transfer_rules", "update",
    "explanatory_memorandum", "intellectual_property",
    "technical_guide", "preparation",
}


# ---------------------------------------------------------------------------
# Main parse logic
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("parse_govil_xmls.py — Parse FTA XML files from downloads/govil/")
    print("=" * 70)

    # Find all FTA XML files
    xml_pattern = os.path.join(GOVIL_DIR, "FTA_*.xml")
    xml_files = sorted(glob.glob(xml_pattern))
    print(f"\nFound {len(xml_files)} FTA XML files in {GOVIL_DIR}")

    if not xml_files:
        print("ERROR: No XML files found. Check path.")
        sys.exit(1)

    # Parse all XMLs and group by country
    country_docs = defaultdict(list)
    approved_exporter_data = None
    parse_errors = 0

    for i, filepath in enumerate(xml_files):
        filename = os.path.basename(filepath)
        country = extract_country_code(filename)
        if not country:
            print(f"  SKIP: Cannot extract country from {filename}")
            continue

        # Parse XML
        parsed = parse_xml_file(filepath)
        if parsed is None:
            parse_errors += 1
            continue

        # Classify document type
        doc_type = classify_doc(filename)

        # Extract file stem (the part after FTA_{country}_sahar-hutz_agreements_)
        stem = filename.replace(".xml", "")
        # Remove the FTA_{country}_sahar-hutz_agreements_ prefix
        stem_short = re.sub(r"^FTA_[a-z]+_sahar-hutz_(?:agreements_)?", "", stem, flags=re.I)

        doc_entry = {
            "title": parsed["first_title"] or stem_short,
            "source_file": filename,
            "file_stem": stem_short,
            "pages": parsed["pages"],
            "language": parsed["language"],
            "char_count": parsed["char_count"],
            "doc_type": doc_type,
        }

        # Include full_text for qualifying doc types under 100KB
        if doc_type in FULL_TEXT_DOC_TYPES and parsed["char_count"] <= MAX_FULL_TEXT:
            doc_entry["full_text"] = parsed["full_text"]
        elif parsed["char_count"] > MAX_FULL_TEXT:
            # Large doc — store summary + first 2000 chars
            doc_entry["full_text_preview"] = parsed["full_text"][:LARGE_DOC_PREVIEW]
            doc_entry["full_text_truncated"] = True
        else:
            # Doc type not in full_text set (e.g. benefits_schedule, tariff_table)
            doc_entry["summary"] = parsed["full_text"][:500]

        # Always add a summary (first 500 chars)
        doc_entry["summary"] = parsed["full_text"][:500] if parsed["full_text"] else ""

        country_docs[country].append(doc_entry)

        # Capture approved exporter specifically from EU
        if country == "eu" and doc_type == "approved_exporter":
            approved_exporter_data = {
                "number": "approved_exporter",
                "name_he": "נוהל יצואן מאושר",
                "name_en": "Approved Exporter Procedure",
                "pages": parsed["pages"],
                "full_text": parsed["full_text"],
                "char_count": parsed["char_count"],
                "source_file": filename,
            }

        # Progress
        if (i + 1) % 20 == 0 or (i + 1) == len(xml_files):
            print(f"  Parsed {i + 1}/{len(xml_files)} files...")

    print(f"\nParsing complete: {len(xml_files)} files, {parse_errors} errors")
    print(f"Countries found: {sorted(country_docs.keys())}")

    # ---------------------------------------------------------------------------
    # Build country data dicts
    # ---------------------------------------------------------------------------
    fta_countries = {}

    for country, docs in sorted(country_docs.items()):
        meta = EXISTING_METADATA.get(country, {})

        # Build documents dict keyed by doc_type (or doc_type_N for duplicates)
        documents = {}
        type_counts = defaultdict(int)

        for doc in docs:
            dt = doc["doc_type"]
            type_counts[dt] += 1
            key = dt if type_counts[dt] == 1 else f"{dt}_{type_counts[dt]}"

            doc_dict = {
                "title": doc["title"],
                "source_file": doc["source_file"],
                "file_stem": doc["file_stem"],
                "pages": doc["pages"],
                "language": doc["language"],
                "char_count": doc["char_count"],
                "summary": doc.get("summary", ""),
            }
            if "full_text" in doc:
                doc_dict["full_text"] = doc["full_text"]
            if doc.get("full_text_truncated"):
                doc_dict["full_text_preview"] = doc.get("full_text_preview", "")
                doc_dict["full_text_truncated"] = True

            documents[key] = doc_dict

        total_chars = sum(d["char_count"] for d in docs)
        total_pages = sum(d["pages"] for d in docs)

        entry = {}

        # Preserve existing metadata fields
        for field in [
            "name_he", "name_en", "agreement_name_he", "agreement_name_en",
            "agreement_year", "effective_date", "origin_proof",
            "has_invoice_declaration", "has_approved_exporter",
            "cumulation", "cumulation_countries",
            "member_states", "member_states_he",
            "value_threshold_eur", "value_threshold_usd",
        ]:
            if field in meta:
                entry[field] = meta[field]

        # Fallback name if not in existing metadata
        if "name_en" not in entry:
            entry["name_en"] = country.capitalize()
        if "name_he" not in entry:
            entry["name_he"] = country

        entry["documents"] = documents
        entry["total_chars"] = total_chars
        entry["total_pages"] = total_pages
        entry["xml_count"] = len(docs)

        # Extract key_articles from origin docs
        key_articles = {}
        for doc in docs:
            if doc["doc_type"] == "origin" and doc.get("full_text"):
                # Try to extract article structure from origin rules text
                key_articles["origin_rules"] = {
                    "title": doc["title"],
                    "source_file": doc["source_file"],
                    "char_count": doc["char_count"],
                }
            elif doc["doc_type"] == "protocol" and doc.get("full_text"):
                key_articles["protocol"] = {
                    "title": doc["title"],
                    "source_file": doc["source_file"],
                    "char_count": doc["char_count"],
                }
        entry["key_articles"] = key_articles

        fta_countries[country] = entry

    # ---------------------------------------------------------------------------
    # Print summary table
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 90)
    print(f"{'Country':<12} {'XMLs':>5} {'Pages':>6} {'Chars':>10}  Doc Types")
    print("-" * 90)

    grand_total_xmls = 0
    grand_total_pages = 0
    grand_total_chars = 0

    for code in sorted(fta_countries.keys()):
        c = fta_countries[code]
        doc_types = sorted(set(d["doc_type"] for d in country_docs[code]))
        dt_str = ", ".join(doc_types)
        print(f"{code:<12} {c['xml_count']:>5} {c['total_pages']:>6} {c['total_chars']:>10,}  {dt_str}")
        grand_total_xmls += c["xml_count"]
        grand_total_pages += c["total_pages"]
        grand_total_chars += c["total_chars"]

    print("-" * 90)
    print(f"{'TOTAL':<12} {grand_total_xmls:>5} {grand_total_pages:>6} {grand_total_chars:>10,}")
    print("=" * 90)

    # Approved exporter summary
    if approved_exporter_data:
        print(f"\nApproved Exporter: {approved_exporter_data['pages']} pages, "
              f"{approved_exporter_data['char_count']:,} chars")
    else:
        print("\nWARNING: Approved exporter document not found!")

    # ---------------------------------------------------------------------------
    # Generate _fta_all_countries_GENERATED.py
    # ---------------------------------------------------------------------------
    print(f"\nWriting {OUTPUT_FTA}...")
    _write_fta_file(fta_countries, country_docs)

    # ---------------------------------------------------------------------------
    # Generate _approved_exporter_GENERATED.py
    # ---------------------------------------------------------------------------
    if approved_exporter_data:
        print(f"Writing {OUTPUT_APPROVED}...")
        _write_approved_exporter_file(approved_exporter_data)

    print("\nDone!")


def _escape_for_python(text):
    """Escape a string for inclusion in a Python triple-quoted string."""
    # Replace backslashes first, then quotes
    text = text.replace("\\", "\\\\")
    text = text.replace('"""', '\\"\\"\\"')
    return text


def _write_fta_file(fta_countries, country_docs):
    """Write the generated FTA data file."""
    lines = []
    lines.append('# -*- coding: utf-8 -*-')
    lines.append('"""')
    lines.append(f'FTA agreement data for {len(fta_countries)} countries '
                 f'-- parsed from govil XML files.')
    lines.append(f'Auto-generated by parse_govil_xmls.py on {datetime.now().strftime("%Y-%m-%d %H:%M")}.')
    lines.append('')
    lines.append('Usage:')
    lines.append('    from lib._fta_all_countries_GENERATED import (')
    lines.append('        FTA_COUNTRIES, get_fta_country, get_all_country_codes,')
    lines.append('        get_countries_with_eur1, search_fta_articles,')
    lines.append('        get_origin_proof_type, classify_fta_document,')
    lines.append('    )')
    lines.append('"""')
    lines.append('')
    lines.append('import os')
    lines.append('import re')
    lines.append('')
    lines.append('')
    lines.append('# ' + '-' * 75)
    lines.append('# GOVIL directory path (relative to functions/)')
    lines.append('# ' + '-' * 75)
    lines.append('_GOVIL_DIR = os.path.join(')
    lines.append('    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),')
    lines.append('    "downloads", "govil",')
    lines.append(')')
    lines.append('')
    lines.append('')
    lines.append('# ' + '-' * 75)
    lines.append('# Document type classification patterns')
    lines.append('# ' + '-' * 75)
    lines.append('_DOC_TYPE_PATTERNS = [')
    # Copy from existing file patterns
    pattern_lines = [
        '    (re.compile(r"makor|origin|rules.of.origin|\\u05db\\u05dc\\u05dc\\u05d9.\\u05de\\u05e7\\u05d5\\u05e8|\\u05ea\\u05e2\\u05d5\\u05d3\\u05ea.\\u05de\\u05e7\\u05d5\\u05e8", re.I), "origin_rules"),',
        '    (re.compile(r"eur1|EUR\\.1|eur-1", re.I), "eur1_form"),',
        '    (re.compile(r"teodat.makor|certificate.of.origin|milui.makor", re.I), "certificate_of_origin"),',
        '    (re.compile(r"approved.exporter|\\u05d9\\u05e6\\u05d5\\u05d0\\u05df.\\u05de\\u05d0\\u05d5\\u05e9\\u05e8|nohal.misim", re.I), "approved_exporter"),',
        '    (re.compile(r"invoice.declaration|\\u05d7\\u05e9\\u05d1\\u05d5\\u05df.\\u05d4\\u05e6\\u05d4\\u05e8\\u05d4|heshbon.hatzhar", re.I), "invoice_declaration"),',
        '    (re.compile(r"benefit|concession|\\u05d4\\u05d8\\u05d1\\u05d5\\u05ea|\\u05d4\\u05d8\\u05d1\\u05d4|tariff.schedule", re.I), "benefits_schedule"),',
        '    (re.compile(r"agri|agriculture|\\u05d7\\u05e7\\u05dc\\u05d0\\u05d5\\u05ea", re.I), "agriculture"),',
        '    (re.compile(r"industry|\\u05ea\\u05e2\\u05e9\\u05d9\\u05d9", re.I), "industry"),',
        '    (re.compile(r"procedure|ita.procedure|shitun|\\u05e0\\u05d5\\u05d4\\u05dc", re.I), "procedure"),',
        '    (re.compile(r"exp\\\\b|hesber|explanat|\\u05d4\\u05e1\\u05d1\\u05e8|brief", re.I), "explanation"),',
        '    (re.compile(r"tech.guide|guide", re.I), "technical_guide"),',
        '    (re.compile(r"update|correction|\\u05ea\\u05d9\\u05e7\\u05d5\\u05df", re.I), "update"),',
        '    (re.compile(r"committee|joint|\\u05d5\\u05e2\\u05d3\\u05d4", re.I), "joint_committee"),',
        '    (re.compile(r"mutual.recognition|mra", re.I), "mutual_recognition"),',
        '    (re.compile(r"review|economic.review|\\u05e1\\u05e7\\u05d9\\u05e8\\u05d4", re.I), "economic_review"),',
        '    (re.compile(r"summ|summary|\\u05ea\\u05e7\\u05e6\\u05d9\\u05e8", re.I), "summary"),',
        '    (re.compile(r"exit|preparation|\\u05d4\\u05db\\u05e0\\u05d4", re.I), "preparation"),',
        '    (re.compile(r"regional.convention|\\u05d0\\u05de\\u05e0\\u05d4.\\u05d0\\u05d6\\u05d5\\u05e8\\u05d9\\u05ea", re.I), "regional_convention"),',
        '    (re.compile(r"transfer|loading|\\u05d4\\u05e2\\u05de\\u05e1\\u05d4|\\u05d4\\u05e2\\u05d1\\u05e8\\u05d4", re.I), "transfer_rules"),',
        '    (re.compile(r"intellectual|property|\\u05e7\\u05e0\\u05d9\\u05d9\\u05df.\\u05e8\\u05d5\\u05d7\\u05e0\\u05d9", re.I), "intellectual_property"),',
        '    (re.compile(r"memorandum|\\u05d3\\u05d1\\u05e8\\u05d9.\\u05d4\\u05e1\\u05d1\\u05e8", re.I), "explanatory_memorandum"),',
        '    (re.compile(r"agreement|agree|\\u05d4\\u05e1\\u05db\\u05dd|fta\\\\b", re.I), "agreement_text"),',
        '    (re.compile(r"protocol|\\u05e4\\u05e8\\u05d5\\u05d8\\u05d5\\u05e7\\u05d5\\u05dc|annex|\\u05e0\\u05e1\\u05e4\\u05d7|appendix", re.I), "protocol_annex"),',
    ]
    # Actually, let's just reference the existing patterns from the original file
    # to avoid unicode escape mess. Instead, write the patterns directly.
    lines.append('    # Origin rules & proof')
    lines.append('    (re.compile(r"makor|origin|rules.of.origin|כללי.מקור|תעודת.מקור", re.I), "origin_rules"),')
    lines.append('    (re.compile(r"eur1|EUR\\.1|eur-1", re.I), "eur1_form"),')
    lines.append('    (re.compile(r"teodat.makor|certificate.of.origin|milui.makor", re.I), "certificate_of_origin"),')
    lines.append('    (re.compile(r"approved.exporter|יצואן.מאושר|nohal.misim", re.I), "approved_exporter"),')
    lines.append('    (re.compile(r"invoice.declaration|חשבון.הצהרה|heshbon.hatzhar", re.I), "invoice_declaration"),')
    lines.append('    # Benefits / concessions')
    lines.append('    (re.compile(r"benefit|concession|הטבות|הטבה|tariff.schedule", re.I), "benefits_schedule"),')
    lines.append('    (re.compile(r"agri|agriculture|חקלאות", re.I), "agriculture"),')
    lines.append('    (re.compile(r"industry|תעשיי", re.I), "industry"),')
    lines.append('    # Procedures / explanations')
    lines.append('    (re.compile(r"procedure|ita.procedure|shitun|נוהל", re.I), "procedure"),')
    lines.append(r'    (re.compile(r"exp\b|hesber|explanat|הסבר|brief", re.I), "explanation"),')
    lines.append('    (re.compile(r"tech.guide|guide", re.I), "technical_guide"),')
    lines.append('    # Updates / committees')
    lines.append('    (re.compile(r"update|correction|תיקון", re.I), "update"),')
    lines.append('    (re.compile(r"committee|joint|ועדה", re.I), "joint_committee"),')
    lines.append('    (re.compile(r"mutual.recognition|mra", re.I), "mutual_recognition"),')
    lines.append('    # Reviews / summaries')
    lines.append('    (re.compile(r"review|economic.review|סקירה", re.I), "economic_review"),')
    lines.append('    (re.compile(r"summ|summary|תקציר", re.I), "summary"),')
    lines.append('    (re.compile(r"exit|preparation|הכנה", re.I), "preparation"),')
    lines.append('    # Regional convention / transfer / IP')
    lines.append('    (re.compile(r"regional.convention|אמנה.אזורית", re.I), "regional_convention"),')
    lines.append('    (re.compile(r"transfer|loading|העמסה|העברה", re.I), "transfer_rules"),')
    lines.append('    (re.compile(r"intellectual|property|קניין.רוחני", re.I), "intellectual_property"),')
    lines.append('    (re.compile(r"memorandum|דברי.הסבר", re.I), "explanatory_memorandum"),')
    lines.append('    # Agreement texts (generic -- must be LAST)')
    lines.append(r'    (re.compile(r"agreement|agree|הסכם|fta\b", re.I), "agreement_text"),')
    lines.append('    (re.compile(r"protocol|פרוטוקול|annex|נספח|appendix", re.I), "protocol_annex"),')
    lines.append(']')
    lines.append('')
    lines.append('')

    # classify_fta_document function
    lines.append('def classify_fta_document(filename):')
    lines.append('    """Classify an FTA document filename into a document type."""')
    lines.append('    for pattern, doc_type in _DOC_TYPE_PATTERNS:')
    lines.append('        if pattern.search(filename):')
    lines.append('            return doc_type')
    lines.append('    return "other"')
    lines.append('')
    lines.append('')

    # _COUNTRY_XML_FILES
    lines.append('# ' + '-' * 75)
    lines.append('# File inventory per country')
    lines.append('# ' + '-' * 75)
    lines.append('_COUNTRY_XML_FILES = {')
    for code in sorted(country_docs.keys()):
        stems = [d["file_stem"] for d in country_docs[code]]
        lines.append(f'    "{code}": [')
        for stem in sorted(stems):
            lines.append(f'        "{stem}",')
        lines.append('    ],')
    lines.append('}')
    lines.append('')
    lines.append('')

    # FTA_COUNTRIES — the main data structure
    lines.append('# ' + '-' * 75)
    lines.append('# FTA_COUNTRIES -- main data structure')
    lines.append('# ' + '-' * 75)
    lines.append('FTA_COUNTRIES = {')

    for code in sorted(fta_countries.keys()):
        c = fta_countries[code]
        lines.append(f'    "{code}": {{')

        # Write metadata fields
        for field in [
            "name_he", "name_en", "agreement_name_he", "agreement_name_en",
        ]:
            if field in c:
                lines.append(f'        "{field}": {repr(c[field])},')

        for field in [
            "member_states", "member_states_he",
        ]:
            if field in c:
                lines.append(f'        "{field}": {repr(c[field])},')

        for field in ["agreement_year"]:
            if field in c:
                lines.append(f'        "{field}": {c[field]},')

        for field in ["effective_date"]:
            if field in c:
                lines.append(f'        "{field}": {repr(c[field])},')

        for field in ["origin_proof", "cumulation"]:
            if field in c:
                lines.append(f'        "{field}": {repr(c[field])},')

        for field in ["has_invoice_declaration", "has_approved_exporter"]:
            if field in c:
                lines.append(f'        "{field}": {c[field]},')

        for field in ["cumulation_countries"]:
            if field in c:
                lines.append(f'        "{field}": {repr(c[field])},')

        for field in ["value_threshold_eur", "value_threshold_usd"]:
            if field in c:
                lines.append(f'        "{field}": {repr(c[field])},')

        # Stats
        lines.append(f'        "xml_count": {c["xml_count"]},')
        lines.append(f'        "total_pages": {c["total_pages"]},')
        lines.append(f'        "total_chars": {c["total_chars"]},')

        # Documents dict
        lines.append('        "documents": {')
        for doc_key, doc_data in sorted(c["documents"].items()):
            lines.append(f'            "{doc_key}": {{')
            lines.append(f'                "title": {repr(doc_data["title"])},')
            lines.append(f'                "source_file": {repr(doc_data["source_file"])},')
            lines.append(f'                "file_stem": {repr(doc_data["file_stem"])},')
            lines.append(f'                "pages": {doc_data["pages"]},')
            lines.append(f'                "language": {repr(doc_data["language"])},')
            lines.append(f'                "char_count": {doc_data["char_count"]},')

            # Summary (always present)
            summary = doc_data.get("summary", "")
            if summary:
                lines.append(f'                "summary": {repr(summary)},')

            # Full text — write as triple-quoted string for readability
            if "full_text" in doc_data and doc_data["full_text"]:
                ft = doc_data["full_text"]
                # Use repr for safety with all the special chars
                lines.append(f'                "full_text": {repr(ft)},')
            elif doc_data.get("full_text_truncated"):
                preview = doc_data.get("full_text_preview", "")
                lines.append(f'                "full_text_preview": {repr(preview)},')
                lines.append('                "full_text_truncated": True,')

            lines.append('            },')
        lines.append('        },')

        # key_articles
        if c.get("key_articles"):
            lines.append('        "key_articles": {')
            for art_key, art_data in c["key_articles"].items():
                lines.append(f'            "{art_key}": {{')
                for k, v in art_data.items():
                    lines.append(f'                "{k}": {repr(v)},')
                lines.append('            },')
            lines.append('        },')
        else:
            lines.append('        "key_articles": {},')

        lines.append('    },')
        lines.append('')

    lines.append('}')
    lines.append('')
    lines.append('')

    # ---------------------------------------------------------------------------
    # Shared documents
    # ---------------------------------------------------------------------------
    lines.append('# ' + '-' * 75)
    lines.append('# Shared documents -- appear under multiple countries')
    lines.append('# ' + '-' * 75)
    lines.append('_SHARED_DOCUMENTS = {')
    lines.append('    "fta-eur1-makor-example": {')
    lines.append('        "title": "EUR.1 Certificate of Origin -- Sample",')
    lines.append('        "title_he": "\\u05ea\\u05e2\\u05d5\\u05d3\\u05ea \\u05de\\u05e7\\u05d5\\u05e8 EUR.1 -- \\u05d3\\u05d5\\u05d2\\u05de\\u05d4",')
    lines.append('        "doc_type": "eur1_form",')
    lines.append('        "countries": ["eu", "efta", "turkey", "jordan"],')
    lines.append('    },')
    lines.append('    "fta-teodat-makor-exp": {')
    lines.append('        "title": "Certificate of Origin -- Explanation",')
    lines.append('        "title_he": "\\u05ea\\u05e2\\u05d5\\u05d3\\u05ea \\u05de\\u05e7\\u05d5\\u05e8 -- \\u05d4\\u05e1\\u05d1\\u05e8",')
    lines.append('        "doc_type": "certificate_of_origin",')
    lines.append('        "countries": ["eu", "efta", "turkey", "jordan"],')
    lines.append('    },')
    lines.append('    "nohal-misim-approved-exporter": {')
    lines.append('        "title": "Approved Exporter Procedure",')
    lines.append('        "title_he": "\\u05e0\\u05d5\\u05d4\\u05dc \\u05d9\\u05e6\\u05d5\\u05d0\\u05df \\u05de\\u05d0\\u05d5\\u05e9\\u05e8",')
    lines.append('        "doc_type": "approved_exporter",')
    lines.append('        "countries": ["eu", "efta", "turkey", "jordan"],')
    lines.append('    },')
    lines.append('}')
    lines.append('')
    lines.append('')

    # ---------------------------------------------------------------------------
    # Helper functions — preserved from existing _fta_all_countries.py
    # ---------------------------------------------------------------------------
    lines.append('# ' + '-' * 75)
    lines.append('# Helper functions')
    lines.append('# ' + '-' * 75)
    lines.append('')
    lines.append('def get_fta_country(code):')
    lines.append('    """Get FTA country data by country code."""')
    lines.append('    return FTA_COUNTRIES.get(code.lower() if code else None)')
    lines.append('')
    lines.append('')
    lines.append('def get_all_country_codes():')
    lines.append(f'    """Return sorted list of all {len(fta_countries)} FTA country codes."""')
    lines.append('    return sorted(FTA_COUNTRIES.keys())')
    lines.append('')
    lines.append('')
    lines.append('def get_countries_with_eur1():')
    lines.append('    """Return list of country codes that use EUR.1 as origin proof."""')
    lines.append('    return [')
    lines.append('        code for code, data in FTA_COUNTRIES.items()')
    lines.append('        if data.get("origin_proof") == "EUR.1"')
    lines.append('    ]')
    lines.append('')
    lines.append('')
    lines.append('def get_countries_with_approved_exporter():')
    lines.append('    """Return list of country codes that allow approved exporter status."""')
    lines.append('    return [')
    lines.append('        code for code, data in FTA_COUNTRIES.items()')
    lines.append('        if data.get("has_approved_exporter")')
    lines.append('    ]')
    lines.append('')
    lines.append('')
    lines.append('def get_countries_with_invoice_declaration():')
    lines.append('    """Return list of country codes that accept invoice declarations."""')
    lines.append('    return [')
    lines.append('        code for code, data in FTA_COUNTRIES.items()')
    lines.append('        if data.get("has_invoice_declaration")')
    lines.append('    ]')
    lines.append('')
    lines.append('')
    lines.append('def get_country_files(code):')
    lines.append('    """Get the list of XML file stems for a country."""')
    lines.append('    return list(_COUNTRY_XML_FILES.get(code.lower() if code else "", []))')
    lines.append('')
    lines.append('')
    lines.append('def get_xml_filepath(code, file_stem):')
    lines.append('    """Build full XML file path for a country document."""')
    lines.append('    code = (code or "").lower()')
    lines.append('    if code not in _COUNTRY_XML_FILES:')
    lines.append('        return None')
    lines.append('    if file_stem not in _COUNTRY_XML_FILES[code]:')
    lines.append('        return None')
    lines.append('    filename = f"FTA_{code}_sahar-hutz_agreements_{file_stem}.xml"')
    lines.append('    path = os.path.join(_GOVIL_DIR, filename)')
    lines.append('    if os.path.isfile(path):')
    lines.append('        return path')
    lines.append('    return None')
    lines.append('')
    lines.append('')
    lines.append('def get_pdf_filepath(code, file_stem):')
    lines.append('    """Build full PDF file path for a country document."""')
    lines.append('    xml_path = get_xml_filepath(code, file_stem)')
    lines.append('    if xml_path:')
    lines.append('        return xml_path.replace(".xml", ".pdf")')
    lines.append('    return None')
    lines.append('')
    lines.append('')
    lines.append('def search_fta_articles(keyword):')
    lines.append('    """Search across all countries key articles for a keyword."""')
    lines.append('    if not keyword:')
    lines.append('        return []')
    lines.append('    kw = keyword.lower()')
    lines.append('    results = []')
    lines.append('    for code, country_data in FTA_COUNTRIES.items():')
    lines.append('        for art_key, art_data in country_data.get("key_articles", {}).items():')
    lines.append('            searchable = " ".join([')
    lines.append('                art_data.get("title", ""),')
    lines.append('                art_data.get("title_he", ""),')
    lines.append('                art_data.get("summary", ""),')
    lines.append('            ]).lower()')
    lines.append('            if kw in searchable:')
    lines.append('                results.append({')
    lines.append('                    "country_code": code,')
    lines.append('                    "country_name": country_data["name_en"],')
    lines.append('                    "country_name_he": country_data["name_he"],')
    lines.append('                    "article_key": art_key,')
    lines.append('                    "article_data": art_data,')
    lines.append('                })')
    lines.append('    return results')
    lines.append('')
    lines.append('')
    lines.append('def search_fta_countries(query):')
    lines.append('    """Search countries by name, agreement name, or notes."""')
    lines.append('    if not query:')
    lines.append('        return []')
    lines.append('    q = query.lower()')
    lines.append('    results = []')
    lines.append('    for code, data in FTA_COUNTRIES.items():')
    lines.append('        searchable = " ".join([')
    lines.append('            code,')
    lines.append('            data.get("name_he", ""),')
    lines.append('            data.get("name_en", ""),')
    lines.append('            data.get("agreement_name_he", ""),')
    lines.append('            data.get("agreement_name_en", ""),')
    lines.append('            data.get("origin_proof", ""),')
    lines.append('        ]).lower()')
    lines.append('        if q in searchable:')
    lines.append('            results.append((code, data))')
    lines.append('    return results')
    lines.append('')
    lines.append('')
    lines.append('def get_origin_proof_type(country_of_origin):')
    lines.append('    """Given a country name, find what origin proof is needed."""')
    lines.append('    if not country_of_origin:')
    lines.append('        return None')
    lines.append('    q = country_of_origin.lower().strip()')
    lines.append('    for code, data in FTA_COUNTRIES.items():')
    lines.append('        names = [')
    lines.append('            data.get("name_en", "").lower(),')
    lines.append('            data.get("name_he", "").lower(),')
    lines.append('            code,')
    lines.append('        ]')
    lines.append('        for ms in data.get("member_states", []):')
    lines.append('            names.append(ms.lower())')
    lines.append('        for ms in data.get("member_states_he", []):')
    lines.append('            names.append(ms.lower())')
    lines.append('        if q in names or any(q in n for n in names):')
    lines.append('            return {')
    lines.append('                "country_code": code,')
    lines.append('                "origin_proof": data["origin_proof"],')
    lines.append('                "has_invoice_declaration": data.get("has_invoice_declaration", False),')
    lines.append('                "has_approved_exporter": data.get("has_approved_exporter", False),')
    lines.append('                "agreement_name": data.get("agreement_name_en", ""),')
    lines.append('            }')
    lines.append('    return None')
    lines.append('')
    lines.append('')
    lines.append('def search_fta_full_text(keyword, max_results=10):')
    lines.append('    """Search across all document full_text fields for a keyword.')
    lines.append('')
    lines.append('    Returns list of {country_code, doc_key, title, snippet}.')
    lines.append('    """')
    lines.append('    if not keyword:')
    lines.append('        return []')
    lines.append('    kw = keyword.lower()')
    lines.append('    results = []')
    lines.append('    for code, country_data in FTA_COUNTRIES.items():')
    lines.append('        for doc_key, doc_data in country_data.get("documents", {}).items():')
    lines.append('            ft = doc_data.get("full_text", "")')
    lines.append('            if not ft:')
    lines.append('                ft = doc_data.get("summary", "")')
    lines.append('            if kw in ft.lower():')
    lines.append('                idx = ft.lower().index(kw)')
    lines.append('                start = max(0, idx - 100)')
    lines.append('                end = min(len(ft), idx + len(keyword) + 100)')
    lines.append('                snippet = ft[start:end]')
    lines.append('                results.append({')
    lines.append('                    "country_code": code,')
    lines.append('                    "country_name": country_data["name_en"],')
    lines.append('                    "doc_key": doc_key,')
    lines.append('                    "title": doc_data.get("title", ""),')
    lines.append('                    "snippet": snippet,')
    lines.append('                })')
    lines.append('                if len(results) >= max_results:')
    lines.append('                    return results')
    lines.append('    return results')
    lines.append('')
    lines.append('')
    lines.append('def get_document_inventory():')
    lines.append('    """Return full document inventory across all countries."""')
    lines.append('    inventory = {}')
    lines.append('    for code, files in _COUNTRY_XML_FILES.items():')
    lines.append('        docs = []')
    lines.append('        for stem in files:')
    lines.append('            docs.append({')
    lines.append('                "file_stem": stem,')
    lines.append('                "doc_type": classify_fta_document(stem),')
    lines.append('                "has_xml": True,')
    lines.append('                "has_pdf": True,')
    lines.append('            })')
    lines.append('        inventory[code] = docs')
    lines.append('    return inventory')
    lines.append('')
    lines.append('')
    lines.append('def get_summary_stats():')
    lines.append('    """Return summary statistics about the FTA collection."""')
    lines.append('    total_xml = sum(len(files) for files in _COUNTRY_XML_FILES.values())')
    lines.append('    eur1_countries = get_countries_with_eur1()')
    lines.append('    cert_countries = [')
    lines.append('        c for c in FTA_COUNTRIES')
    lines.append('        if FTA_COUNTRIES[c]["origin_proof"] == "Certificate of Origin"')
    lines.append('    ]')
    lines.append('    invoice_only = [')
    lines.append('        c for c in FTA_COUNTRIES')
    lines.append('        if FTA_COUNTRIES[c]["origin_proof"] == "Invoice Declaration"')
    lines.append('    ]')
    lines.append('    total_articles = sum(')
    lines.append('        len(d.get("key_articles", {})) for d in FTA_COUNTRIES.values()')
    lines.append('    )')
    lines.append('    total_chars = sum(d.get("total_chars", 0) for d in FTA_COUNTRIES.values())')
    lines.append('    total_pages = sum(d.get("total_pages", 0) for d in FTA_COUNTRIES.values())')
    lines.append('    return {')
    lines.append(f'        "total_countries": {len(fta_countries)},')
    lines.append('        "total_xml_files": total_xml,')
    lines.append('        "total_key_articles": total_articles,')
    lines.append('        "total_chars": total_chars,')
    lines.append('        "total_pages": total_pages,')
    lines.append('        "eur1_countries": eur1_countries,')
    lines.append('        "certificate_of_origin_countries": cert_countries,')
    lines.append('        "invoice_declaration_countries": invoice_only,')
    lines.append('        "approved_exporter_countries": get_countries_with_approved_exporter(),')
    lines.append('        "bloc_agreements": [c for c in FTA_COUNTRIES if "member_states" in FTA_COUNTRIES[c]],')
    lines.append('    }')
    lines.append('')

    content = "\n".join(lines) + "\n"
    with open(OUTPUT_FTA, "w", encoding="utf-8") as f:
        f.write(content)

    file_size = os.path.getsize(OUTPUT_FTA)
    print(f"  Written: {OUTPUT_FTA}")
    print(f"  Size: {file_size:,} bytes ({file_size / 1024 / 1024:.1f} MB)")


def _write_approved_exporter_file(data):
    """Write the approved exporter procedure file."""
    lines = []
    lines.append('# -*- coding: utf-8 -*-')
    lines.append('"""')
    lines.append('Approved Exporter Procedure (נוהל יצואן מאושר) -- parsed from govil XML.')
    lines.append(f'Auto-generated by parse_govil_xmls.py on {datetime.now().strftime("%Y-%m-%d %H:%M")}.')
    lines.append(f'Source: {data["source_file"]}')
    lines.append(f'Pages: {data["pages"]}, Characters: {data["char_count"]:,}')
    lines.append('"""')
    lines.append('')
    lines.append('')
    lines.append('APPROVED_EXPORTER_PROCEDURE = {')
    lines.append(f'    "number": {repr(data["number"])},')
    lines.append(f'    "name_he": {repr(data["name_he"])},')
    lines.append(f'    "name_en": {repr(data["name_en"])},')
    lines.append(f'    "pages": {data["pages"]},')
    lines.append(f'    "char_count": {data["char_count"]},')
    lines.append(f'    "source_file": {repr(data["source_file"])},')
    lines.append(f'    "full_text": {repr(data["full_text"])},')
    lines.append('}')
    lines.append('')

    content = "\n".join(lines) + "\n"
    with open(OUTPUT_APPROVED, "w", encoding="utf-8") as f:
        f.write(content)

    file_size = os.path.getsize(OUTPUT_APPROVED)
    print(f"  Written: {OUTPUT_APPROVED}")
    print(f"  Size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
