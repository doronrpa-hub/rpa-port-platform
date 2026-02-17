"""
Block C5: Seed framework_order collection from צו מסגרת (Framework Order).

Sources:
  1. Firestore knowledge/TrvmM8ttC94uR46LRmwo — 50K char full text (PDF extraction)
  2. tariff_xml_backup/AdditionRulesDetailsHistory.xml — 296 versioned additions (7.2 MB)

Writes to Firestore:
  1. framework_order/definitions — legal term definitions
  2. framework_order/fta_{country} — FTA rule per trade agreement
  3. framework_order/additions/{id} — active addition rules from XML
  4. framework_order/_metadata — collection summary
  5. framework_order/_full_text — raw full text for AI search
  6. librarian_index/ — indexes all framework_order docs

The Framework Order (צו מסגרת) defines:
  - Legal definitions that OVERRIDE common language for classification
  - FTA (Free Trade Agreement) preferential duty rules per country
  - Classification rules for the תוספת ראשונה (First Supplement)
  - Tax computation rules (מס קניה)
  - Addition rules for tariff schedule amendments

Safety:
  - Uses set(merge=True) — ADD only
  - Tags with source: "framework_order_c5"
  - Batched writes

Run: python -X utf8 seed_framework_order_c5.py [--test] [--skip-xml]
"""
import sys
import os
import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from collections import defaultdict

os.environ["GOOGLE_CLOUD_PROJECT"] = "rpa-port-customs"

import firebase_admin
from firebase_admin import credentials, firestore

# ── Firebase init ──
SA_PATHS = [
    r"C:\Users\User\Downloads\rpa-port-customs-firebase-adminsdk-fbsvc-da5df22d32.json",
    r"C:\Users\doron\sa-key.json",
]

try:
    app = firebase_admin.get_app()
except ValueError:
    sa_path = next((p for p in SA_PATHS if os.path.exists(p)), None)
    if not sa_path:
        print("ERROR: No service account key found")
        sys.exit(1)
    cred = credentials.Certificate(sa_path)
    app = firebase_admin.initialize_app(cred)

db = firestore.client()

NOW = datetime.now(timezone.utc).isoformat()
SOURCE = "framework_order_c5"
COLLECTION = "framework_order"
KNOWLEDGE_DOC_ID = "TrvmM8ttC94uR46LRmwo"

# XML namespace
NS = "{http://malam.com/customs/CustomsBook/CBC_NG_8362_MSG01_CustomsBookOut}"

# Path to downloaded XML
XML_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "data_c3", "AdditionRulesDetailsHistory.xml"),
    r"C:\Users\User\rpa-port-platform\data_c3\AdditionRulesDetailsHistory.xml",
]


# ══════════════════════════════════════════════
#  PART 1: Parse definitions from knowledge doc
# ══════════════════════════════════════════════

# Known legal definition terms in the Framework Order
KNOWN_DEFINITIONS = [
    "אזור", "אל\"י", "אל\"פ", "ארה\"ב", "ארצות מצטרפות", "ארצות אפט\"א",
    "האיחוד האירופי", "ארצות מרקוסור", "גאט\"ט", "דולר", "הסכם סחר",
    "השער היציג", "חבילות שי", "טובין המשמשים לייצור", "ייצור מקומי",
    "מדד", "מחיר עסקה", "מכס", "מס", "מע\"מ", "ערך", "ק\"ג", "שוחרר",
    "(מותנה)", "פרט", "מחיר", "תוצרת הארץ", "ערך עסקה",
]

# FTA countries and their Hebrew names
FTA_COUNTRIES = {
    "eu": {"he": "האיחוד האירופי", "en": "European Union", "supplements": ["ראשונה"]},
    "efta": {"he": "ארצות אפט\"א", "en": "EFTA", "supplements": ["שלישית"]},
    "usa": {"he": "ארה\"ב", "en": "United States", "supplements": ["רביעית"]},
    "canada": {"he": "קנדה", "en": "Canada", "supplements": ["חמישית"]},
    "mexico": {"he": "מקסיקו", "en": "Mexico", "supplements": ["שישית"]},
    "turkey": {"he": "טורקיה", "en": "Turkey", "supplements": ["שביעית"]},
    "jordan": {"he": "ירדן", "en": "Jordan", "supplements": ["שמינית"]},
    "mercosur": {"he": "ארצות מרקוסור", "en": "Mercosur", "supplements": ["תשיעית"]},
    "korea": {"he": "הרפובליקה של קוריאה", "en": "South Korea", "supplements": ["עשירית"]},
    "colombia": {"he": "קולומביה", "en": "Colombia", "supplements": ["שתים עשרה"]},
    "panama": {"he": "פנמה", "en": "Panama", "supplements": ["שלוש עשרה"]},
    "ukraine": {"he": "אוקראינה", "en": "Ukraine", "supplements": ["ארבע עשרה"]},
    "uk": {"he": "הממלכה המאוחדת", "en": "United Kingdom", "supplements": ["שבע עשרה"]},
    "uae": {"he": "איחוד האמירויות הערביות", "en": "UAE", "supplements": ["שמונה עשרה"]},
    "guatemala": {"he": "גואטמלה", "en": "Guatemala", "supplements": []},
}


def extract_definitions(text):
    """Extract legal definitions from the Framework Order text.
    Definitions appear as: "term"  definition text ; or "term"  definition text"""
    definitions = []

    # The definitions section starts after הגדרות and before סיווג טובין
    # Find definition block boundaries
    def_start = text.find("הגדרות")
    if def_start == -1:
        print("  WARNING: Could not find הגדרות section")
        return definitions

    # Definitions end roughly at סיווג טובין בתוספת הראשונה
    def_end = text.find("סיווג טובין בתוספת הראשונה", def_start)
    if def_end == -1:
        def_end = min(def_start + 15000, len(text))

    def_block = text[def_start:def_end]

    # Pattern: "term"  followed by definition until next "term" or semicolon boundary
    # Hebrew quotes are regular ASCII quotes in this text
    pattern = r'"([^"]{1,60})"\s{2,}([^"]+?)(?=\s{2,}"[^"]{1,60}"|\Z)'
    matches = re.finditer(pattern, def_block, re.DOTALL)

    seen_terms = set()
    for m in matches:
        term = m.group(1).strip()
        definition = m.group(2).strip()

        # Clean up definition
        definition = re.sub(r'\s+', ' ', definition)
        # Remove trailing semicolons and whitespace
        definition = definition.rstrip('; \t')

        # Skip if too short or duplicate
        if len(term) < 2 or len(definition) < 5:
            continue
        if term in seen_terms:
            continue
        seen_terms.add(term)

        # Skip terms that are clearly not definitions (date patterns, etc.)
        if re.match(r'^\d{4}', term):
            continue

        definitions.append({
            "term": term,
            "definition": definition[:2000],  # Cap at 2000 chars
            "source_section": "הגדרות",
        })

    # Also extract known definitions by direct search
    for known_term in KNOWN_DEFINITIONS:
        clean_term = known_term.replace('"', '')
        if clean_term in seen_terms:
            continue

        # Search for the term in quotes
        search_patterns = [
            f'"{clean_term}"',
            f'"{known_term}"',
        ]
        for sp in search_patterns:
            idx = def_block.find(sp)
            if idx != -1:
                # Get text after the term
                after = def_block[idx + len(sp):idx + len(sp) + 500]
                # Clean and extract definition
                after = after.strip()
                # Take until next quoted term or semicolon
                end = re.search(r'(?:;\s{2,}"|"\s{2,})', after)
                if end:
                    after = after[:end.start()]
                after = re.sub(r'\s+', ' ', after).strip().rstrip(';')
                if len(after) > 5:
                    definitions.append({
                        "term": clean_term,
                        "definition": after[:2000],
                        "source_section": "הגדרות",
                    })
                    seen_terms.add(clean_term)
                break

    return definitions


def extract_fta_clauses(text):
    """Extract FTA (Free Trade Agreement) clauses from the Framework Order.
    These describe duty exemptions/reductions per trade agreement country."""
    fta_clauses = []

    for code, info in FTA_COUNTRIES.items():
        he_name = info["he"].replace('"', '')
        en_name = info["en"]

        # Find all mentions of הסכם הסחר עם {country}
        pattern = rf'הסכם הסחר\s+(?:עם\s+|החופשי\s+בין\s+.*?לבין\s+.*?){re.escape(he_name)}'
        matches = list(re.finditer(pattern, text))

        if not matches:
            # Try simpler pattern
            pattern2 = rf'הסכם הסחר.*?{re.escape(he_name)}'
            matches = list(re.finditer(pattern2, text))

        if matches:
            # Get the longest context around the first substantive match
            best_match = None
            best_len = 0
            for m in matches:
                # Get surrounding context (the full clause)
                start = max(0, m.start() - 50)
                end = min(len(text), m.end() + 800)
                context = text[start:end]
                if len(context) > best_len:
                    best_match = context
                    best_len = len(context)

            clause_text = re.sub(r'\s+', ' ', best_match).strip() if best_match else ""

            # Determine if it's duty-free or reduced
            is_duty_free = "פטורים ממכס" in clause_text or "פטור ממכס" in clause_text
            has_reduction = "הפחתה" in clause_text or "הפחתת מכס" in clause_text

            fta_clauses.append({
                "country_code": code,
                "country_he": info["he"],
                "country_en": en_name,
                "supplements": info["supplements"],
                "clause_text": clause_text[:3000],
                "is_duty_free": is_duty_free,
                "has_reduction": has_reduction,
                "mentions_count": len(matches),
            })

    return fta_clauses


def extract_classification_rules(text):
    """Extract classification-specific rules from the Framework Order."""
    rules = []

    # Find classification section
    cls_start = text.find("סיווג טובין בתוספת הראשונה")
    if cls_start == -1:
        return rules

    # Get the classification rules block (roughly 5000 chars)
    cls_block = text[cls_start:cls_start + 5000]
    cls_text = re.sub(r'\s+', ' ', cls_block).strip()

    rules.append({
        "type": "classification_rules",
        "title": "סיווג טובין בתוספת הראשונה",
        "title_en": "Classification of goods in the First Supplement",
        "text": cls_text[:4000],
    })

    # Find conditional classification (מותנה) rules
    cond_start = text.find("(מותנה)")
    if cond_start != -1:
        cond_block = text[max(0, cond_start - 200):cond_start + 800]
        cond_text = re.sub(r'\s+', ' ', cond_block).strip()
        rules.append({
            "type": "conditional_classification",
            "title": "סיווג מותנה",
            "title_en": "Conditional classification rules",
            "text": cond_text[:2000],
        })

    # Find manufacturing (ייצור מקומי) rules
    mfg_start = text.find("ייצור מקומי")
    if mfg_start != -1:
        mfg_block = text[max(0, mfg_start - 100):mfg_start + 1000]
        mfg_text = re.sub(r'\s+', ' ', mfg_block).strip()
        rules.append({
            "type": "local_manufacturing",
            "title": "ייצור מקומי",
            "title_en": "Local manufacturing definitions",
            "text": mfg_text[:2000],
        })

    return rules


# ══════════════════════════════════════════════
#  PART 2: Parse additions from XML
# ══════════════════════════════════════════════

def parse_additions_xml(xml_path):
    """Parse AdditionRulesDetailsHistory.xml and extract the most current
    version of each addition (latest StartDate with EndDate >= 2026)."""
    print(f"  Parsing XML: {xml_path}")
    tree = ET.parse(xml_path)
    root = tree.getroot()
    tables = root.find(f"{NS}CustomsBookGeneralTables")
    entries = list(tables.findall(f"{NS}AdditionRulesDetailsHistory"))
    print(f"  Total XML entries: {len(entries)}")

    # Group by CustomsBookAdditionID, keep most recent active version
    by_addition = defaultdict(list)
    for e in entries:
        add_id = e.findtext(f"{NS}CustomsBookAdditionID", "")
        end_date = e.findtext(f"{NS}EndDate", "")
        start_date = e.findtext(f"{NS}StartDate", "")

        # Only active entries
        if end_date and end_date >= "2026":
            by_addition[add_id].append({
                "id": e.findtext(f"{NS}ID", ""),
                "title": (e.findtext(f"{NS}Title", "") or "")[:500],
                "start_date": start_date,
                "end_date": end_date,
                "rules": e.findtext(f"{NS}Rules", "") or "",
                "rules_rtf": (e.findtext(f"{NS}RulesRTF", "") or "")[:100],
                "addition_id": add_id,
                "type_id": e.findtext(f"{NS}TypeID", ""),
                "status_id": e.findtext(f"{NS}EntityStatusID", ""),
            })

    # Keep only the most recent version per addition
    additions = []
    for add_id, versions in by_addition.items():
        # Sort by StartDate descending
        versions.sort(key=lambda x: x["start_date"], reverse=True)
        best = versions[0]

        # Only include additions with actual content
        if len(best["rules"]) > 50:
            additions.append({
                "addition_id": add_id,
                "entry_id": best["id"],
                "title": best["title"],
                "start_date": best["start_date"],
                "end_date": best["end_date"],
                "rules_text": best["rules"][:10000],  # Cap at 10K chars
                "rules_length": len(best["rules"]),
                "type_id": best["type_id"],
                "versions_count": len(versions),
            })

    additions.sort(key=lambda x: int(x["addition_id"]) if x["addition_id"].isdigit() else 0)
    print(f"  Active additions with content: {len(additions)}")
    return additions


# ══════════════════════════════════════════════
#  PART 3: Seed Firestore
# ══════════════════════════════════════════════

def seed_firestore(definitions, fta_clauses, cls_rules, additions, full_text, test_mode=False):
    """Seed all parsed data into Firestore framework_order collection."""
    batch = db.batch()
    count = 0

    # 1. Definitions
    print(f"\n  --- Seeding {len(definitions)} definitions ---")
    for defn in definitions:
        doc_id = f"def_{defn['term'][:50]}".replace("/", "_").replace('"', '').replace(" ", "_")
        doc_data = {
            "type": "definition",
            "term": defn["term"],
            "definition": defn["definition"],
            "source_section": defn["source_section"],
            "source": SOURCE,
            "seeded_at": NOW,
        }
        ref = db.collection(COLLECTION).document(doc_id)
        batch.set(ref, doc_data, merge=True)
        count += 1

    # 2. FTA clauses
    print(f"  --- Seeding {len(fta_clauses)} FTA clauses ---")
    for fta in fta_clauses:
        doc_id = f"fta_{fta['country_code']}"
        doc_data = {
            "type": "fta_clause",
            "country_code": fta["country_code"],
            "country_he": fta["country_he"],
            "country_en": fta["country_en"],
            "supplements": fta["supplements"],
            "clause_text": fta["clause_text"],
            "is_duty_free": fta["is_duty_free"],
            "has_reduction": fta["has_reduction"],
            "mentions_count": fta["mentions_count"],
            "source": SOURCE,
            "seeded_at": NOW,
        }
        ref = db.collection(COLLECTION).document(doc_id)
        batch.set(ref, doc_data, merge=True)
        count += 1

    # 3. Classification rules
    print(f"  --- Seeding {len(cls_rules)} classification rules ---")
    for rule in cls_rules:
        doc_id = f"rule_{rule['type']}"
        doc_data = {
            "type": "classification_rule",
            "rule_type": rule["type"],
            "title": rule["title"],
            "title_en": rule["title_en"],
            "text": rule["text"],
            "source": SOURCE,
            "seeded_at": NOW,
        }
        ref = db.collection(COLLECTION).document(doc_id)
        batch.set(ref, doc_data, merge=True)
        count += 1

    # Commit definitions + FTA + rules batch
    if not test_mode:
        batch.commit()
    print(f"  Committed {count} docs (definitions + FTA + rules)")

    # 4. Addition rules (separate batches — can be large)
    print(f"  --- Seeding {len(additions)} addition rules ---")
    batch = db.batch()
    add_count = 0
    for add in additions:
        doc_id = f"addition_{add['addition_id']}"
        doc_data = {
            "type": "addition_rule",
            "addition_id": add["addition_id"],
            "entry_id": add["entry_id"],
            "title": add["title"],
            "start_date": add["start_date"],
            "end_date": add["end_date"],
            "rules_text": add["rules_text"],
            "rules_length": add["rules_length"],
            "type_id": add["type_id"],
            "versions_count": add["versions_count"],
            "source": SOURCE,
            "seeded_at": NOW,
        }
        ref = db.collection(COLLECTION).document(doc_id)
        batch.set(ref, doc_data, merge=True)
        add_count += 1
        count += 1

        if add_count % 200 == 0:
            if not test_mode:
                batch.commit()
            batch = db.batch()
            print(f"    Committed {add_count} additions...")

    if add_count % 200 != 0:
        if not test_mode:
            batch.commit()
    print(f"  Committed {add_count} additions")

    # 5. Full text doc (for AI search)
    print(f"  --- Seeding full text doc ---")
    full_text_doc = {
        "type": "full_text",
        "content": full_text,
        "content_length": len(full_text),
        "source_doc": f"knowledge/{KNOWLEDGE_DOC_ID}",
        "source": SOURCE,
        "seeded_at": NOW,
    }
    if not test_mode:
        db.collection(COLLECTION).document("_full_text").set(full_text_doc, merge=True)
    count += 1

    return count


def seed_metadata(defs_count, fta_count, rules_count, additions_count, total):
    """Seed metadata doc."""
    meta = {
        "collection": COLLECTION,
        "source": SOURCE,
        "description": "צו מסגרת — Framework Order: legal definitions, FTA rules, classification rules, tariff additions",
        "definitions_count": defs_count,
        "fta_clauses_count": fta_count,
        "classification_rules_count": rules_count,
        "additions_count": additions_count,
        "total_docs": total,
        "fta_countries": list(FTA_COUNTRIES.keys()),
        "seeded_at": NOW,
    }
    db.collection(COLLECTION).document("_metadata").set(meta, merge=True)
    print(f"  Metadata doc written")


def index_in_librarian(total):
    """Add framework_order entries to librarian_index."""
    batch = db.batch()
    count = 0

    for doc in db.collection(COLLECTION).stream():
        if doc.id.startswith("_"):
            continue
        data = doc.to_dict()

        index_entry = {
            "collection": COLLECTION,
            "doc_id": doc.id,
            "doc_type": data.get("type", ""),
            "title": (
                data.get("term", "") or data.get("title", "") or
                data.get("country_en", "") or doc.id
            )[:200],
            "source": SOURCE,
            "indexed_at": NOW,
        }

        ref = db.collection("librarian_index").document(f"fw_{doc.id}")
        batch.set(ref, index_entry, merge=True)
        count += 1

        if count % 500 == 0:
            batch.commit()
            batch = db.batch()
            print(f"  Indexed {count}...")

    if count % 500 != 0:
        batch.commit()

    print(f"  Indexed {count} docs in librarian_index (prefix: fw_)")
    return count


def main():
    test_mode = "--test" in sys.argv
    skip_xml = "--skip-xml" in sys.argv

    if test_mode:
        print("=== TEST MODE ===")

    print(f"Block C5: Seeding {COLLECTION} from Framework Order sources")

    # ── Step 1: Read knowledge doc ──
    print(f"\n--- Step 1: Reading knowledge doc ---")
    doc = db.collection("knowledge").document(KNOWLEDGE_DOC_ID).get()
    if not doc.exists:
        print(f"ERROR: knowledge/{KNOWLEDGE_DOC_ID} not found")
        sys.exit(1)
    full_text = doc.to_dict().get("content", "")
    print(f"  Full text: {len(full_text)} chars")

    # ── Step 2: Parse definitions ──
    print(f"\n--- Step 2: Extracting definitions ---")
    definitions = extract_definitions(full_text)
    print(f"  Extracted {len(definitions)} definitions")
    for d in definitions[:5]:
        print(f"    \"{d['term']}\": {d['definition'][:80]}...")

    # ── Step 3: Parse FTA clauses ──
    print(f"\n--- Step 3: Extracting FTA clauses ---")
    fta_clauses = extract_fta_clauses(full_text)
    print(f"  Extracted {len(fta_clauses)} FTA clauses")
    for f in fta_clauses:
        print(f"    {f['country_en']}: duty_free={f['is_duty_free']} reduction={f['has_reduction']} mentions={f['mentions_count']}")

    # ── Step 4: Parse classification rules ──
    print(f"\n--- Step 4: Extracting classification rules ---")
    cls_rules = extract_classification_rules(full_text)
    print(f"  Extracted {len(cls_rules)} classification rules")
    for r in cls_rules:
        print(f"    {r['type']}: {r['title']}")

    # ── Step 5: Parse XML additions ──
    additions = []
    if not skip_xml:
        xml_path = next((p for p in XML_PATHS if os.path.exists(p)), None)
        if xml_path:
            print(f"\n--- Step 5: Parsing XML additions ---")
            additions = parse_additions_xml(xml_path)
        else:
            print(f"\n--- Step 5: SKIPPED (XML not found) ---")
            print(f"  Tried: {XML_PATHS}")
    else:
        print(f"\n--- Step 5: SKIPPED (--skip-xml) ---")

    # ── Step 6: Seed Firestore ──
    print(f"\n--- Step 6: Seeding Firestore ---")
    total = seed_firestore(definitions, fta_clauses, cls_rules, additions, full_text, test_mode)

    if not test_mode:
        # Metadata
        seed_metadata(len(definitions), len(fta_clauses), len(cls_rules), len(additions), total)

        # Librarian index
        print(f"\n--- Step 7: Indexing ---")
        index_in_librarian(total)

    # Summary
    print(f"\n=== DONE ===")
    print(f"  Definitions: {len(definitions)}")
    print(f"  FTA clauses: {len(fta_clauses)}")
    print(f"  Classification rules: {len(cls_rules)}")
    print(f"  Addition rules: {len(additions)}")
    print(f"  Total docs: {total}")
    if test_mode:
        print("  (TEST MODE — nothing written)")


if __name__ == "__main__":
    main()
