#!/usr/bin/env python
"""
Block C2: Parse chapter notes (הערות לפרק) from XML and write to Firestore.

Source: RuleDetailsHistory.xml from fullCustomsBookData.zip
Chain:  RuleDetailsHistory.RuleID -> Rule.CustomsItemID -> CustomsItem.FullClassification -> chapter

Covers 94 of 98 chapters. Missing: 50 (Silk), 53 (Other veg textile), 77 (Reserved), 98 (Special).
Also extracts 12 section-level notes.

Usage:
    python parse_chapter_notes_c2.py --dry-run    # Parse and print, no Firestore writes
    python parse_chapter_notes_c2.py --write       # Parse and write to Firestore
"""

import re
import sys
import json
from datetime import datetime
from collections import defaultdict
from xml.etree.ElementTree import iterparse

# ── Config ──────────────────────────────────────────────────────────────────

RULE_XML = "C:/Users/doron/tariff_extract/Rule.xml"
CUSTOMS_ITEM_XML = "C:/Users/doron/tariff_extract/CustomsItem.xml"
RULE_DETAILS_XML = "C:/Users/doron/tariff_extract/RuleDetailsHistory_clean.xml"
SA_KEY = "C:/Users/doron/sa-key.json"

NS = "http://malam.com/customs/CustomsBook/CBC_NG_8362_MSG01_CustomsBookOut"
TODAY = "2026-02-17"

# Rule Title patterns that indicate note types
PATTERN_CHAPTER_RULES = re.compile(r"כללים\s*לפרק")
PATTERN_CHAPTER_NUMBERED = re.compile(r"כללים?\s*לפרק\s*\d+")
PATTERN_SUBHEADING_RULES = re.compile(r"כללים?\s*לפרטי\s*משנה")
PATTERN_SUPPLEMENTARY = re.compile(r"כללים\s*נוספים.*ישראלי")
PATTERN_SECTION_RULES = re.compile(r"כללים\s*לחלק")

# Patterns to identify exclusions/inclusions in note text
EXCLUSION_PATTERNS = [
    r"פרק\s+זה\s+אינו\s+(?:מכסה|כולל|חל)",
    r"אינ[וה]\s+כולל",
    r"לא\s+כולל",
    r"למעט",
    r"אינ[וה]\s+חל",
    r"לא\s+נכלל",
    r"does\s+not\s+(?:cover|include|apply)",
    r"exclud(?:es|ing|ed)",
    r"except\s+(?:for|that)",
]

INCLUSION_PATTERNS = [
    r"פרק\s+זה\s+(?:כולל|מכסה|חל)",
    r"כולל\s+(?:גם|את)",
    r"חל\s+(?:גם\s+)?על",
    r"(?:includes?|covers?|applies?\s+to)",
    r"נכלל",
]


def _tag(name):
    return f"{{{NS}}}{name}"


# ── Step 1: Parse Rule.xml ──────────────────────────────────────────────────

def parse_rules():
    """Parse Rule.xml -> dict of RuleID -> (CustomsItemID, Title)."""
    rule_map = {}
    item_ids = set()
    for event, elem in iterparse(RULE_XML, events=["end"]):
        if elem.tag == _tag("Rule"):
            rid = int(elem.find(_tag("ID")).text)
            cid = int(elem.find(_tag("CustomsItemID")).text)
            title_el = elem.find(_tag("Title"))
            title = title_el.text if title_el is not None and title_el.text else ""
            rule_map[rid] = (cid, title)
            item_ids.add(cid)
            elem.clear()
    print(f"[Rule.xml] {len(rule_map)} rules, {len(item_ids)} unique CustomsItemIDs")
    return rule_map, item_ids


# ── Step 2: Parse CustomsItem.xml ──────────────────────────────────────────

def parse_customs_items(item_ids):
    """Parse CustomsItem.xml -> dict of ID -> (FullClassification, HierarchicLocationID)."""
    item_map = {}
    for event, elem in iterparse(CUSTOMS_ITEM_XML, events=["end"]):
        if elem.tag == _tag("CustomsItem"):
            iid_el = elem.find(_tag("ID"))
            if iid_el is not None:
                iid = int(iid_el.text)
                if iid in item_ids:
                    fc_el = elem.find(_tag("FullClassification"))
                    hl_el = elem.find(_tag("CustomsItemHierarchicLocationID"))
                    fc = fc_el.text if fc_el is not None and fc_el.text else ""
                    hl = hl_el.text if hl_el is not None and hl_el.text else ""
                    item_map[iid] = (fc, hl)
            elem.clear()
    print(f"[CustomsItem.xml] Found {len(item_map)} matching items")
    return item_map


# ── Step 3: Build RuleID -> chapter/section mapping ────────────────────────

def build_rule_chapter_map(rule_map, item_map):
    """Map each RuleID to a chapter number or section identifier."""
    rule_to_chapter = {}  # RuleID -> (chapter_str, title, note_type)
    rule_to_section = {}  # RuleID -> (section_roman, title, note_type)

    for rid, (cid, title) in rule_map.items():
        if cid not in item_map:
            continue
        fc, hl = item_map[cid]

        # Determine note type from title
        note_type = "chapter_rules"  # default
        if PATTERN_SUBHEADING_RULES.search(title):
            note_type = "subheading_rules"
        elif PATTERN_SUPPLEMENTARY.search(title):
            note_type = "supplementary_israeli"
        elif PATTERN_CHAPTER_NUMBERED.search(title):
            note_type = "chapter_rules_numbered"
        elif PATTERN_SECTION_RULES.search(title):
            note_type = "section_rules"
        elif PATTERN_CHAPTER_RULES.search(title):
            note_type = "chapter_rules"
        elif title == "new":
            note_type = "new"

        if hl == "2" and len(fc) >= 2:
            ch = fc[:2]
            rule_to_chapter[rid] = (ch, title, note_type)
        elif hl == "1":
            rule_to_section[rid] = (fc, title, note_type)

    chapters = set(ch for ch, _, _ in rule_to_chapter.values())
    sections = set(s for s, _, _ in rule_to_section.values())
    print(f"[Mapping] {len(rule_to_chapter)} rules -> {len(chapters)} chapters")
    print(f"[Mapping] {len(rule_to_section)} rules -> {len(sections)} sections")

    return rule_to_chapter, rule_to_section


# ── Step 4: Parse RuleDetailsHistory.xml ────────────────────────────────────

def parse_rule_details(rule_to_chapter, rule_to_section):
    """Parse RuleDetailsHistory.xml and extract current notes per chapter/section."""
    target_rids = set(rule_to_chapter.keys()) | set(rule_to_section.keys())

    # Collect all entries for target RuleIDs
    entries_by_rid = defaultdict(list)
    total = 0

    for event, elem in iterparse(RULE_DETAILS_XML, events=["end"]):
        if elem.tag == _tag("RuleDetailsHistory"):
            rid_el = elem.find(_tag("RuleID"))
            if rid_el is not None:
                rid = int(rid_el.text)
                if rid in target_rids:
                    entry = {
                        "id": int(elem.find(_tag("ID")).text),
                        "rule_id": rid,
                        "start": _text(elem, "StartDate"),
                        "end": _text(elem, "EndDate"),
                        "rules_he": _text(elem, "Rules"),
                        "rules_en": _text(elem, "EnglishRules"),
                        "order": _text(elem, "OrderinalPostion"),
                        "parent_id": _text(elem, "Parent_RuleDetailsHistoryID"),
                    }
                    entries_by_rid[rid].append(entry)
            total += 1
            elem.clear()

    print(f"[RuleDetailsHistory.xml] Scanned {total} entries, "
          f"found {sum(len(v) for v in entries_by_rid.values())} for target rules")

    # For each RuleID, keep only the CURRENT version(s)
    # Current = entries where EndDate >= TODAY, or if none, the latest EndDate
    current_by_rid = {}
    for rid, entries in entries_by_rid.items():
        # Group by (order, parent_id) to handle sub-entries
        future = [e for e in entries if e["end"] >= TODAY]
        if future:
            current_by_rid[rid] = future
        else:
            # Take entries with the latest EndDate
            max_end = max(e["end"] for e in entries)
            current_by_rid[rid] = [e for e in entries if e["end"] == max_end]

    return current_by_rid


def _text(elem, tag_name):
    """Extract text from a child element, return empty string if missing."""
    child = elem.find(_tag(tag_name))
    if child is None:
        return ""
    if child.text is None:
        return ""
    return child.text.strip()


# ── Step 5: Build chapter notes structure ───────────────────────────────────

def build_chapter_notes(rule_to_chapter, rule_to_section, current_by_rid):
    """Build structured chapter notes from parsed data."""
    chapter_data = defaultdict(lambda: {
        "preamble": "",
        "notes": [],
        "exclusions": [],
        "inclusions": [],
        "notes_en": [],
        "preamble_en": "",
        "supplementary_israeli": [],
        "subheading_rules": [],
        "source_rule_ids": [],
    })

    section_data = defaultdict(lambda: {
        "notes_he": "",
        "notes_en": "",
        "source_rule_ids": [],
    })

    # Process chapter rules
    for rid, (ch, title, note_type) in rule_to_chapter.items():
        if rid not in current_by_rid:
            continue

        entries = current_by_rid[rid]
        ch_data = chapter_data[ch]
        ch_data["source_rule_ids"].append(rid)

        # Separate root entries (order=0, no parent) from sub-entries
        root_entries = [e for e in entries if not e["parent_id"] and e["order"] == "0"]
        sub_entries = [e for e in entries if e["parent_id"] or e["order"] != "0"]

        for entry in root_entries:
            he_text = _clean_note_text(entry["rules_he"])
            en_text = _clean_note_text(entry["rules_en"])

            if note_type in ("chapter_rules", "chapter_rules_numbered"):
                if not ch_data["preamble"] or len(he_text) > len(ch_data["preamble"]):
                    ch_data["preamble"] = he_text
                if en_text and en_text != "---":
                    if not ch_data["preamble_en"] or len(en_text) > len(ch_data["preamble_en"]):
                        ch_data["preamble_en"] = en_text
            elif note_type == "supplementary_israeli":
                if he_text:
                    ch_data["supplementary_israeli"].append(he_text)
            elif note_type == "subheading_rules":
                if he_text:
                    ch_data["subheading_rules"].append(he_text)
            elif note_type == "new":
                # "new" entries — add as supplementary
                if he_text:
                    ch_data["supplementary_israeli"].append(he_text)

        # Sub-entries are individual notes
        for entry in sorted(sub_entries, key=lambda e: int(e["order"]) if e["order"].isdigit() else 999):
            he_text = _clean_note_text(entry["rules_he"])
            en_text = _clean_note_text(entry["rules_en"])

            if he_text:
                if note_type == "subheading_rules":
                    ch_data["subheading_rules"].append(he_text)
                elif note_type == "supplementary_israeli":
                    ch_data["supplementary_israeli"].append(he_text)
                else:
                    ch_data["notes"].append(he_text)
                    if en_text and en_text != "---":
                        ch_data["notes_en"].append(en_text)

    # Process section rules
    for rid, (section, title, note_type) in rule_to_section.items():
        if rid not in current_by_rid:
            continue
        entries = current_by_rid[rid]
        sd = section_data[section]
        sd["source_rule_ids"].append(rid)

        for entry in entries:
            he_text = _clean_note_text(entry["rules_he"])
            en_text = _clean_note_text(entry["rules_en"])
            if he_text:
                if sd["notes_he"]:
                    sd["notes_he"] += "\n\n" + he_text
                else:
                    sd["notes_he"] = he_text
            if en_text and en_text != "---":
                if sd["notes_en"]:
                    sd["notes_en"] += "\n\n" + en_text
                else:
                    sd["notes_en"] = en_text

    # Post-process: deduplicate, split, extract exclusions/inclusions
    for ch, data in chapter_data.items():
        # Deduplicate all list fields (multiple CustomsItemIDs = same chapter, different time periods)
        data["notes"] = _deduplicate(data["notes"])
        data["notes_en"] = _deduplicate(data["notes_en"])
        data["supplementary_israeli"] = _deduplicate(data["supplementary_israeli"])
        data["subheading_rules"] = _deduplicate(data["subheading_rules"])

        # Split preamble into individual notes if it contains numbered items
        if data["preamble"]:
            individual_notes = _split_numbered_notes(data["preamble"])
            if len(individual_notes) > 1:
                for note in individual_notes:
                    if note not in data["notes"]:
                        data["notes"].append(note)

        # Deduplicate notes again after splitting
        data["notes"] = _deduplicate(data["notes"])

        # Extract exclusions
        for note in data["notes"] + [data["preamble"]]:
            if _is_exclusion(note):
                if note not in data["exclusions"]:
                    data["exclusions"].append(note)

        # Extract inclusions
        for note in data["notes"] + [data["preamble"]]:
            if _is_inclusion(note):
                if note not in data["inclusions"]:
                    data["inclusions"].append(note)

    # Deduplicate section notes too
    for section, sd in section_data.items():
        # Remove duplicate paragraphs in section notes
        if sd["notes_he"]:
            paras = sd["notes_he"].split("\n\n")
            sd["notes_he"] = "\n\n".join(_deduplicate(paras))
        if sd["notes_en"]:
            paras = sd["notes_en"].split("\n\n")
            sd["notes_en"] = "\n\n".join(_deduplicate(paras))

    return dict(chapter_data), dict(section_data)


def _deduplicate(items):
    """Remove duplicate strings while preserving order."""
    seen = set()
    result = []
    for item in items:
        # Normalize for comparison (strip, collapse whitespace)
        key = re.sub(r"\s+", " ", item.strip())
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _clean_note_text(text):
    """Clean note text: strip RTF, normalize whitespace."""
    if not text:
        return ""
    # Remove RTF if present
    if text.startswith("{\\rtf"):
        return ""
    # Remove leading dots and colons
    text = re.sub(r"^[.:]+\s*", "", text)
    # Remove redundant title prefixes (various formats)
    text = re.sub(r"^\.?כללים\s*ל(?:פרק|חלק)\s*(?:[IVX]+|\d+)\s*:?\s*\.?\s*", "", text)
    text = re.sub(r"^\.?כלל\s*ל(?:פרק|חלק)\s*(?:[IVX]+|\d+)\s*:?\s*\.?\s*", "", text)
    text = re.sub(r"^\.?כללים\s*נוספים\s*\(ישראליים\)\s*:?\s*\.?\s*", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_numbered_notes(text):
    """Split a block of text into individual numbered notes."""
    # Try splitting on Hebrew numbered patterns: .1. .2. or 1. 2.
    parts = re.split(r"(?:^|\.)(\d+)\.\s+", text)
    if len(parts) <= 1:
        return [text]

    notes = []
    i = 1
    while i < len(parts) - 1:
        num = parts[i]
        content = parts[i + 1].strip()
        if content:
            notes.append(f"{num}. {content}")
        i += 2
    return notes if notes else [text]


def _is_exclusion(text):
    """Check if a note text describes an exclusion."""
    if not text:
        return False
    for pattern in EXCLUSION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _is_inclusion(text):
    """Check if a note text describes an inclusion."""
    if not text:
        return False
    for pattern in INCLUSION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


# ── Step 6: Write to Firestore ──────────────────────────────────────────────

def write_to_firestore(chapter_data, section_data):
    """Write chapter notes to Firestore chapter_notes collection."""
    import firebase_admin
    from firebase_admin import credentials, firestore

    cred = credentials.Certificate(SA_KEY)
    app = firebase_admin.initialize_app(cred)
    db = firestore.client()

    now_iso = datetime.utcnow().isoformat() + "Z"
    written = 0
    batch = db.batch()
    batch_count = 0

    for ch in sorted(chapter_data.keys()):
        data = chapter_data[ch]
        doc_id = f"chapter_{ch}"
        doc_ref = db.collection("chapter_notes").document(doc_id)

        update = {
            "preamble": data["preamble"],
            "preamble_en": data["preamble_en"],
            "notes": data["notes"],
            "notes_en": data["notes_en"],
            "exclusions": data["exclusions"],
            "inclusions": data["inclusions"],
            "supplementary_israeli": data["supplementary_israeli"],
            "subheading_rules": data["subheading_rules"],
            "has_legal_notes": bool(data["preamble"] or data["notes"]),
            "source": "RuleDetailsHistory.xml",
            "source_rule_ids": data["source_rule_ids"],
            "c2_parsed_at": now_iso,
        }

        batch.update(doc_ref, update)
        batch_count += 1
        written += 1

        if batch_count >= 450:
            batch.commit()
            batch = db.batch()
            batch_count = 0

    # Write section notes to a new collection
    for section in sorted(section_data.keys()):
        sd = section_data[section]
        doc_id = f"section_{section}"
        doc_ref = db.collection("section_notes").document(doc_id)

        section_doc = {
            "section": section,
            "notes_he": sd["notes_he"],
            "notes_en": sd["notes_en"],
            "source": "RuleDetailsHistory.xml",
            "source_rule_ids": sd["source_rule_ids"],
            "c2_parsed_at": now_iso,
        }

        batch.set(doc_ref, section_doc)
        batch_count += 1

    if batch_count > 0:
        batch.commit()

    print(f"\n[Firestore] Written {written} chapter_notes updates")
    print(f"[Firestore] Written {len(section_data)} section_notes documents")

    firebase_admin.delete_app(app)


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv or "--write" not in sys.argv

    print("=" * 70)
    print("Block C2: Chapter Notes Parser")
    print(f"Mode: {'DRY RUN' if dry_run else 'WRITE TO FIRESTORE'}")
    print("=" * 70)

    # Step 1: Parse Rule.xml
    rule_map, item_ids = parse_rules()

    # Step 2: Parse CustomsItem.xml
    item_map = parse_customs_items(item_ids)

    # Step 3: Build mapping
    rule_to_chapter, rule_to_section = build_rule_chapter_map(rule_map, item_map)

    # Step 4: Parse RuleDetailsHistory.xml
    current_by_rid = parse_rule_details(rule_to_chapter, rule_to_section)

    # Step 5: Build structured notes
    chapter_data, section_data = build_chapter_notes(
        rule_to_chapter, rule_to_section, current_by_rid
    )

    # Report
    print("\n" + "=" * 70)
    print("CHAPTER NOTES SUMMARY")
    print("=" * 70)

    chapters_with_preamble = 0
    chapters_with_notes = 0
    chapters_with_exclusions = 0
    chapters_with_inclusions = 0

    for ch in sorted(chapter_data.keys()):
        data = chapter_data[ch]
        has_pre = bool(data["preamble"])
        has_notes = bool(data["notes"])
        has_excl = bool(data["exclusions"])
        has_incl = bool(data["inclusions"])
        has_supp = bool(data["supplementary_israeli"])
        has_sub = bool(data["subheading_rules"])

        if has_pre:
            chapters_with_preamble += 1
        if has_notes:
            chapters_with_notes += 1
        if has_excl:
            chapters_with_exclusions += 1
        if has_incl:
            chapters_with_inclusions += 1

        flags = []
        if has_pre:
            flags.append(f"preamble({len(data['preamble'])} chars)")
        if has_notes:
            flags.append(f"notes({len(data['notes'])})")
        if has_excl:
            flags.append(f"excl({len(data['exclusions'])})")
        if has_incl:
            flags.append(f"incl({len(data['inclusions'])})")
        if has_supp:
            flags.append(f"supp({len(data['supplementary_israeli'])})")
        if has_sub:
            flags.append(f"subh({len(data['subheading_rules'])})")

        print(f"  Ch {ch}: {', '.join(flags) if flags else 'EMPTY'}")

    print(f"\nTotals:")
    print(f"  Chapters covered: {len(chapter_data)}/98")
    print(f"  With preamble: {chapters_with_preamble}")
    print(f"  With notes: {chapters_with_notes}")
    print(f"  With exclusions: {chapters_with_exclusions}")
    print(f"  With inclusions: {chapters_with_inclusions}")

    missing = sorted(set(f"{i:02d}" for i in range(1, 99)) - set(chapter_data.keys()))
    print(f"  Missing chapters: {missing}")

    print(f"\nSection notes: {len(section_data)}")
    for s in sorted(section_data.keys()):
        sd = section_data[s]
        print(f"  Section {s}: {len(sd['notes_he'])} chars HE, {len(sd['notes_en'])} chars EN")

    # Sample output for verification
    print("\n" + "=" * 70)
    print("SAMPLE: Chapter 73 (Iron/Steel articles)")
    print("=" * 70)
    if "73" in chapter_data:
        d = chapter_data["73"]
        print(f"Preamble ({len(d['preamble'])} chars):")
        print(f"  {d['preamble'][:500]}")
        print(f"\nNotes ({len(d['notes'])}):")
        for i, n in enumerate(d["notes"][:5]):
            print(f"  [{i}] {n[:200]}")
        print(f"\nExclusions ({len(d['exclusions'])}):")
        for e in d["exclusions"][:3]:
            print(f"  - {e[:200]}")
        print(f"\nSupplementary Israeli ({len(d['supplementary_israeli'])}):")
        for s in d["supplementary_israeli"][:3]:
            print(f"  - {s[:200]}")

    if not dry_run:
        write_to_firestore(chapter_data, section_data)
    else:
        print("\n[DRY RUN] No Firestore writes. Use --write to write to Firestore.")


if __name__ == "__main__":
    main()
