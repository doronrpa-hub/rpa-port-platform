#!/usr/bin/env python3
"""
Build tariff supplement rates + statistical units from XML data.

Data chain:
  Tariff_0.xml  ->  TariffDetailsHistory_0.xml  ->  ComputationMethodData_0.xml
       |                     |                              |
  ID, Title,           TariffID ->                    ID -> Rate,
  CustomsItemID        WithoutQuota_                  MeasurementUnitID,
                       ComputationMethodDataID        CalculationReference,
                       (active: EntityStatusID=2,     EnglishCalculationReference
                        EndDate >= 2026)

  CustomsItem.xml:  ID -> FullClassification (10-digit HS code)

Tariff titles in XML:
  - מכס כללי  (meches_klali)  = General Customs duty
  - מס קניה   (mas_kniya)     = Purchase Tax
  - הסכם סחר  (heskem_sachar) = Trade Agreement / FTA rates

The "שיעור התוספות" column on shaarolami corresponds to "מס קניה" entries.

Output: functions/lib/_tariff_supplements.py
"""

import os
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

# ─── paths ───────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data_c3", "extracted")
DATA_DIR = os.path.normpath(DATA_DIR)

ITEM_XML = os.path.join(DATA_DIR, "CustomsItem.xml")

# Partition files — sorted numerically
import glob as _glob

def _sorted_partitions(prefix):
    """Find all partition files like Tariff_0.xml, Tariff_1.xml, ... sorted numerically."""
    pattern = os.path.join(DATA_DIR, f"{prefix}_*.xml")
    files = _glob.glob(pattern)
    # Sort by numeric suffix
    def _num(f):
        base = os.path.basename(f)
        num_str = base.replace(prefix + "_", "").replace(".xml", "")
        try:
            return int(num_str)
        except ValueError:
            return 999999
    return sorted(files, key=_num)

TARIFF_FILES = _sorted_partitions("Tariff")
HISTORY_FILES = _sorted_partitions("TariffDetailsHistory")
COMP_FILES = _sorted_partitions("ComputationMethodData")

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "lib", "_tariff_supplements.py")

NS = {"c": "http://malam.com/customs/CustomsBook/CBC_NG_8362_MSG01_CustomsBookOut"}

# Hebrew title constants (by Unicode codepoints)
TITLE_MECHES_KLALI = "\u05de\u05db\u05e1 \u05db\u05dc\u05dc\u05d9"   # מכס כללי
TITLE_MAS_KNIYA    = "\u05de\u05e1 \u05e7\u05e0\u05d9\u05d4"          # מס קניה
TITLE_HESKEM_SACHAR = "\u05d4\u05e1\u05db\u05dd \u05e1\u05d7\u05e8"   # הסכם סחר

TITLE_MAP = {
    TITLE_MECHES_KLALI: "general_customs",
    TITLE_MAS_KNIYA: "purchase_tax",
    TITLE_HESKEM_SACHAR: "trade_agreement",
}

# Measurement unit mapping (from EnglishCalculationReference samples)
MEASUREMENT_UNITS = {
    1:  {"en": "Each",                            "he": "\u05d9\u05d7\u05d9\u05d3\u05d4"},                         # יחידה
    2:  {"en": "Pair",                            "he": "\u05d6\u05d5\u05d2"},                                     # זוג
    4:  {"en": "Gross",                           "he": "\u05d2\u05e8\u05d5\u05e1"},                               # גרוס
    5:  {"en": "1000 Units",                      "he": "1000 \u05d9\u05d7\u05d9\u05d3\u05d5\u05ea"},             # 1000 יחידות
    6:  {"en": "Kilogram",                        "he": "\u05e7\u05f4\u05d2"},                                     # ק״ג
    7:  {"en": "Gram",                            "he": "\u05d2\u05e8\u05dd"},                                     # גרם
    8:  {"en": "Tonne",                           "he": "\u05d8\u05d5\u05df"},                                     # טון
    11: {"en": "Cubic Metre",                     "he": "\u05de\u05f4\u05e7"},                                     # מ״ק
    12: {"en": "Litre",                           "he": "\u05dc\u05d9\u05d8\u05e8"},                               # ליטר
    19: {"en": "Metre",                           "he": "\u05de\u05d8\u05e8"},                                     # מטר
    22: {"en": "Millimetre",                      "he": "\u05de\u05f4\u05de"},                                     # מ״מ
    23: {"en": "Kilometre",                       "he": "\u05e7\u05f4\u05de"},                                     # ק״מ
    28: {"en": "Square Metre",                    "he": "\u05de\u05f4\u05e8"},                                     # מ״ר
    37: {"en": "BTU/h",                           "he": "BTU/\u05e9\u05e2\u05d4"},                                 # BTU/שעה
    47: {"en": "Litre Alcohol",                   "he": "\u05dc\u05d9\u05d8\u05e8 \u05d0\u05dc\u05db\u05d5\u05d4\u05d5\u05dc"},  # ליטר אלכוהול
    51: {"en": "1000 Cigarettes",                 "he": "1000 \u05e1\u05d9\u05d2\u05e8\u05d9\u05d5\u05ea"},       # 1000 סיגריות
    56: {"en": "Millilitre",                      "he": "\u05de\u05f4\u05dc"},                                     # מ״ל
    60: {"en": "Kilogram Tableware",              "he": "\u05e7\u05f4\u05d2 \u05db\u05dc\u05d9 \u05e9\u05d5\u05dc\u05d7\u05df"},  # ק״ג כלי שולחן
    99: {"en": "Unknown",                         "he": "\u05dc\u05d0 \u05d9\u05d3\u05d5\u05e2"},                  # לא ידוע
}


def _text(elem, tag):
    """Get text of a child element, or None."""
    child = elem.find(f"c:{tag}", NS)
    return child.text if child is not None else None


def parse_customs_items():
    """Parse CustomsItem.xml -> {CustomsItemID: FullClassification}.

    Filters out export items (CustomsBookTypeID=3) and negative HS codes.
    """
    print(f"  Parsing {ITEM_XML} ...")
    tree = ET.parse(ITEM_XML)
    root = tree.getroot()
    items = root.findall(".//c:CustomsItem", NS)
    mapping = {}
    skipped_export = 0
    skipped_negative = 0
    for item in items:
        item_id = _text(item, "ID")
        fc = _text(item, "FullClassification")
        book_type = _text(item, "CustomsBookTypeID")
        if not item_id or not fc:
            continue
        # Skip export tariff items
        if book_type == "3":
            skipped_export += 1
            continue
        # Skip negative/invalid HS codes
        if fc.startswith("-") or not fc[0].isdigit():
            skipped_negative += 1
            continue
        mapping[item_id] = fc
    print(f"    -> {len(mapping)} CustomsItem entries (skipped: {skipped_export} export, {skipped_negative} negative)")
    return mapping


def parse_tariffs():
    """Parse all Tariff_N.xml -> {TariffID: {title_key, customs_item_id, trade_agreement_id}}."""
    print(f"  Parsing {len(TARIFF_FILES)} Tariff partition files ...")
    mapping = {}
    title_counts = defaultdict(int)
    for fpath in TARIFF_FILES:
        tree = ET.parse(fpath)
        root = tree.getroot()
        tariffs = root.findall(".//c:Tariff", NS)
        for t in tariffs:
            tid = _text(t, "ID")
            title = _text(t, "Title")
            citem_id = _text(t, "CustomsItemID")
            ta_id = _text(t, "TradeAgreementID")
            if not tid or not title:
                continue
            title_key = TITLE_MAP.get(title, "unknown")
            title_counts[title_key] += 1
            mapping[tid] = {
                "title_key": title_key,
                "customs_item_id": citem_id,
                "trade_agreement_id": ta_id,
            }
    print(f"    -> {len(mapping)} Tariff entries")
    for k, v in sorted(title_counts.items()):
        print(f"       {k}: {v}")
    return mapping


def parse_tariff_history():
    """Parse all TariffDetailsHistory_N.xml -> {TariffID: ComputationMethodDataID} (active only)."""
    print(f"  Parsing {len(HISTORY_FILES)} TariffDetailsHistory partition files ...")
    # Keep only active: EntityStatusID=2, EndDate >= 2026-01-01
    # If multiple active for same TariffID, keep the one with latest StartDate
    active = {}
    skipped = 0
    total = 0
    for fpath in HISTORY_FILES:
        tree = ET.parse(fpath)
        root = tree.getroot()
        entries = root.findall(".//c:TariffDetailsHistory", NS)
        total += len(entries)
        for e in entries:
            status = _text(e, "EntityStatusID")
            end_date = _text(e, "EndDate")
            if status != "2":
                skipped += 1
                continue
            if not end_date or end_date < "2026-01-01":
                skipped += 1
                continue
            tariff_id = _text(e, "TariffID")
            comp_id = _text(e, "WithoutQuota_ComputationMethodDataID")
            start_date = _text(e, "StartDate") or ""
            if not tariff_id or not comp_id:
                skipped += 1
                continue
            # Keep latest StartDate per TariffID
            if tariff_id in active:
                if start_date > active[tariff_id]["start_date"]:
                    active[tariff_id] = {"comp_id": comp_id, "start_date": start_date}
            else:
                active[tariff_id] = {"comp_id": comp_id, "start_date": start_date}
    result = {k: v["comp_id"] for k, v in active.items()}
    print(f"    -> {len(result)} active TariffHistory entries from {total} total (skipped {skipped})")
    return result


def parse_computation_methods():
    """Parse all ComputationMethodData_N.xml -> {ID: {rate, calc_ref, calc_ref_en, mu_id, ...}}."""
    print(f"  Parsing {len(COMP_FILES)} ComputationMethodData partition files ...")
    mapping = {}
    for fpath in COMP_FILES:
        tree = ET.parse(fpath)
        root = tree.getroot()
        entries = root.findall(".//c:ComputationMethodData", NS)
        for e in entries:
            cid = _text(e, "ID")
            if not cid:
                continue
            rate = _text(e, "Rate")
            calc_ref = _text(e, "CalculationReference") or ""
            calc_ref_en = _text(e, "EnglishCalculationReference") or ""
            mu_id = _text(e, "MeasurementUnitID")
            comp_method_id = _text(e, "ComputationMethodID")
            defined_per_unit = _text(e, "DefinedPerUnitMethod")
            alt_rate = _text(e, "AlternateRate")
            alt_mu_id = _text(e, "Alternate_MeasurementUnitID")
            mapping[cid] = {
                "rate": rate,
                "calc_ref": calc_ref.strip(),
                "calc_ref_en": calc_ref_en.strip(),
                "mu_id": int(mu_id) if mu_id else None,
                "comp_method_id": comp_method_id,
                "defined_per_unit": defined_per_unit,
                "alt_rate": alt_rate,
                "alt_mu_id": int(alt_mu_id) if alt_mu_id else None,
            }
    print(f"    -> {len(mapping)} ComputationMethodData entries")
    return mapping


def _format_rate_str(comp):
    """Format a human-readable rate string from computation data."""
    en = comp.get("calc_ref_en", "")
    if en:
        return en.strip()
    rate = comp.get("rate")
    if rate:
        try:
            r = float(rate)
            if r == int(r):
                return f"{int(r)}%"
            return f"{r}%"
        except (ValueError, TypeError):
            return str(rate)
    return "Tax Free"


def build():
    """Main build: join all 4 XML files and produce output."""
    print("Building tariff supplements from XML data...")
    print()

    customs_items = parse_customs_items()
    tariffs = parse_tariffs()
    history = parse_tariff_history()
    comp_methods = parse_computation_methods()

    print()
    print("Joining data...")

    # For each tariff type, join: Tariff -> History -> CompMethod -> CustomsItem(HS code)
    # Result per HS code: {general_customs: {...}, purchase_tax: {...}, trade_agreements: [...]}
    hs_data = defaultdict(lambda: {
        "general_customs": None,
        "purchase_tax": None,
    })

    joined = 0
    no_history = 0
    no_comp = 0
    no_hs = 0

    for tariff_id, tariff_info in tariffs.items():
        title_key = tariff_info["title_key"]
        citem_id = tariff_info["customs_item_id"]

        # Skip trade agreements — they're FTA rates, not base tariff
        if title_key == "trade_agreement":
            continue

        # Get HS code
        if not citem_id or citem_id not in customs_items:
            no_hs += 1
            continue
        hs_code = customs_items[citem_id]

        # Get active history entry
        if tariff_id not in history:
            no_history += 1
            continue
        comp_id = history[tariff_id]

        # Get computation method
        if comp_id not in comp_methods:
            no_comp += 1
            continue
        comp = comp_methods[comp_id]

        rate_str = _format_rate_str(comp)
        entry = {
            "rate": rate_str,
            "rate_num": comp["rate"],
            "calc_ref_en": comp["calc_ref_en"],
            "mu_id": comp["mu_id"],
            "comp_method_id": comp["comp_method_id"],
        }
        # Add per-unit info if present
        if comp["defined_per_unit"]:
            entry["per_unit"] = comp["defined_per_unit"]
        if comp["alt_rate"]:
            entry["alt_rate"] = comp["alt_rate"]
            entry["alt_mu_id"] = comp["alt_mu_id"]

        hs_data[hs_code][title_key] = entry
        joined += 1

    print(f"  Joined {joined} entries across {len(hs_data)} HS codes")
    print(f"  Skipped: no_history={no_history}, no_comp={no_comp}, no_hs={no_hs}")

    # Build the output dicts
    SUPPLEMENT_RATES = {}  # hs_code -> {rate, calc_ref_en, mu_id}
    GENERAL_CUSTOMS = {}   # hs_code -> {rate, calc_ref_en, mu_id}
    PURCHASE_TAX = {}      # hs_code -> {rate, calc_ref_en, mu_id}

    for hs_code, data in sorted(hs_data.items()):
        gc = data["general_customs"]
        pt = data["purchase_tax"]

        if gc:
            GENERAL_CUSTOMS[hs_code] = {
                "rate": gc["rate"],
                "calc_ref_en": gc["calc_ref_en"],
            }
            if gc["mu_id"]:
                GENERAL_CUSTOMS[hs_code]["mu_id"] = gc["mu_id"]
            if gc.get("per_unit"):
                GENERAL_CUSTOMS[hs_code]["per_unit"] = gc["per_unit"]

        if pt:
            PURCHASE_TAX[hs_code] = {
                "rate": pt["rate"],
                "calc_ref_en": pt["calc_ref_en"],
            }
            if pt["mu_id"]:
                PURCHASE_TAX[hs_code]["mu_id"] = pt["mu_id"]
            if pt.get("per_unit"):
                PURCHASE_TAX[hs_code]["per_unit"] = pt["per_unit"]

        # SUPPLEMENT_RATES combines both for convenience
        entry = {}
        if gc:
            entry["customs_rate"] = gc["rate"]
            entry["customs_en"] = gc["calc_ref_en"]
        if pt:
            entry["purchase_tax"] = pt["rate"]
            entry["purchase_tax_en"] = pt["calc_ref_en"]
        if gc and gc["mu_id"]:
            entry["mu_id"] = gc["mu_id"]
        elif pt and pt["mu_id"]:
            entry["mu_id"] = pt["mu_id"]
        if entry:
            SUPPLEMENT_RATES[hs_code] = entry

    print(f"  GENERAL_CUSTOMS: {len(GENERAL_CUSTOMS)} HS codes")
    print(f"  PURCHASE_TAX: {len(PURCHASE_TAX)} HS codes")
    print(f"  SUPPLEMENT_RATES (combined): {len(SUPPLEMENT_RATES)} HS codes")

    # Collect unique MeasurementUnitIDs actually used
    used_mu_ids = set()
    for data in hs_data.values():
        for key in ("general_customs", "purchase_tax"):
            if data[key] and data[key]["mu_id"]:
                used_mu_ids.add(data[key]["mu_id"])
    print(f"  MeasurementUnitIDs used: {sorted(used_mu_ids)}")

    return SUPPLEMENT_RATES, GENERAL_CUSTOMS, PURCHASE_TAX


def write_output(supplement_rates, general_customs, purchase_tax):
    """Write the output Python module."""
    print()
    print(f"Writing {OUTPUT_FILE} ...")

    lines = []
    lines.append('"""')
    lines.append("Tariff supplement rates and statistical units.")
    lines.append("")
    lines.append(f"Auto-generated by build_tariff_supplements.py on {datetime.now().strftime('%Y-%m-%d %H:%M')}.")
    lines.append(f"Source: Tariff_0.xml + TariffDetailsHistory_0.xml + ComputationMethodData_0.xml + CustomsItem.xml")
    lines.append("")
    lines.append(f"SUPPLEMENT_RATES: {len(supplement_rates)} HS codes (combined customs + purchase tax)")
    lines.append(f"GENERAL_CUSTOMS: {len(general_customs)} HS codes")
    lines.append(f"PURCHASE_TAX: {len(purchase_tax)} HS codes")
    lines.append('"""')
    lines.append("")
    lines.append("")
    lines.append("# ── Measurement Unit mapping ─────────────────────────────────────────────────")
    lines.append("# From ComputationMethodData EnglishCalculationReference field patterns")
    lines.append("STATISTICAL_UNITS = {")
    for uid, info in sorted(MEASUREMENT_UNITS.items()):
        he_escaped = info["he"].encode("unicode_escape").decode("ascii")
        lines.append(f'    {uid}: {{"en": "{info["en"]}", "he": "{he_escaped}"}},')
    lines.append("}")
    lines.append("")
    lines.append("")

    def _safe_repr(d):
        """repr() that ensures ASCII-safe output for Hebrew strings."""
        parts = []
        for k, v in d.items():
            if isinstance(v, str):
                # Escape non-ASCII to Unicode escapes, then escape internal quotes
                v_safe = v.encode("unicode_escape").decode("ascii")
                v_safe = v_safe.replace('"', '\\"')
                parts.append(f'"{k}": "{v_safe}"')
            elif isinstance(v, int):
                parts.append(f'"{k}": {v}')
            elif v is None:
                parts.append(f'"{k}": None')
            else:
                parts.append(f'"{k}": {repr(v)}')
        return "{" + ", ".join(parts) + "}"

    # Write SUPPLEMENT_RATES
    lines.append("# ── Combined rates (customs duty + purchase tax) per 10-digit HS code ───────")
    lines.append(f"# {len(supplement_rates)} entries")
    lines.append("SUPPLEMENT_RATES = {")
    for hs_code in sorted(supplement_rates.keys()):
        entry = supplement_rates[hs_code]
        lines.append(f'    "{hs_code}": {_safe_repr(entry)},')
    lines.append("}")
    lines.append("")
    lines.append("")

    # Write GENERAL_CUSTOMS
    lines.append("# ── General Customs duty per 10-digit HS code ────────────────────────────────")
    lines.append(f"# {len(general_customs)} entries")
    lines.append("GENERAL_CUSTOMS = {")
    for hs_code in sorted(general_customs.keys()):
        entry = general_customs[hs_code]
        lines.append(f'    "{hs_code}": {_safe_repr(entry)},')
    lines.append("}")
    lines.append("")
    lines.append("")

    # Write PURCHASE_TAX
    lines.append("# ── Purchase Tax per 10-digit HS code ─────────────────────────────────────────")
    lines.append(f"# {len(purchase_tax)} entries")
    lines.append("PURCHASE_TAX = {")
    for hs_code in sorted(purchase_tax.keys()):
        entry = purchase_tax[hs_code]
        lines.append(f'    "{hs_code}": {_safe_repr(entry)},')
    lines.append("}")
    lines.append("")
    lines.append("")

    # Helper functions
    lines.append("# ── Helper functions ────────────────────────────────────────────────────────")
    lines.append("")
    lines.append("")
    lines.append("def get_supplement_rate(hs_code: str) -> dict | None:")
    lines.append('    """')
    lines.append("    Get combined customs duty + purchase tax for a 10-digit HS code.")
    lines.append("")
    lines.append("    Returns dict with keys:")
    lines.append("      customs_rate, customs_en, purchase_tax, purchase_tax_en, mu_id")
    lines.append("    or None if not found.")
    lines.append("")
    lines.append("    Tries exact 10-digit match first, then strips trailing zeros.")
    lines.append('    """')
    lines.append("    code = (hs_code or '').replace('.', '').replace('/', '').replace(' ', '').strip()")
    lines.append("    # Pad to 10 digits")
    lines.append("    if len(code) < 10:")
    lines.append("        code = code.ljust(10, '0')")
    lines.append("    # Exact match")
    lines.append("    if code in SUPPLEMENT_RATES:")
    lines.append("        return SUPPLEMENT_RATES[code]")
    lines.append("    # Try parent codes (strip trailing zeros)")
    lines.append("    for trim in (8, 6, 4):")
    lines.append("        parent = code[:trim].ljust(10, '0')")
    lines.append("        if parent in SUPPLEMENT_RATES:")
    lines.append("            return SUPPLEMENT_RATES[parent]")
    lines.append("    return None")
    lines.append("")
    lines.append("")
    lines.append("def get_general_customs(hs_code: str) -> dict | None:")
    lines.append('    """Get general customs duty rate for a 10-digit HS code."""')
    lines.append("    code = (hs_code or '').replace('.', '').replace('/', '').replace(' ', '').strip()")
    lines.append("    if len(code) < 10:")
    lines.append("        code = code.ljust(10, '0')")
    lines.append("    if code in GENERAL_CUSTOMS:")
    lines.append("        return GENERAL_CUSTOMS[code]")
    lines.append("    for trim in (8, 6, 4):")
    lines.append("        parent = code[:trim].ljust(10, '0')")
    lines.append("        if parent in GENERAL_CUSTOMS:")
    lines.append("            return GENERAL_CUSTOMS[parent]")
    lines.append("    return None")
    lines.append("")
    lines.append("")
    lines.append("def get_purchase_tax(hs_code: str) -> dict | None:")
    lines.append('    """Get purchase tax rate for a 10-digit HS code."""')
    lines.append("    code = (hs_code or '').replace('.', '').replace('/', '').replace(' ', '').strip()")
    lines.append("    if len(code) < 10:")
    lines.append("        code = code.ljust(10, '0')")
    lines.append("    if code in PURCHASE_TAX:")
    lines.append("        return PURCHASE_TAX[code]")
    lines.append("    for trim in (8, 6, 4):")
    lines.append("        parent = code[:trim].ljust(10, '0')")
    lines.append("        if parent in PURCHASE_TAX:")
    lines.append("            return PURCHASE_TAX[parent]")
    lines.append("    return None")
    lines.append("")
    lines.append("")
    lines.append("def get_statistical_unit(mu_id: int) -> dict | None:")
    lines.append('    """')
    lines.append("    Get statistical unit info for a MeasurementUnitID.")
    lines.append("")
    lines.append("    Returns {en: str, he: str} or None.")
    lines.append('    """')
    lines.append("    return STATISTICAL_UNITS.get(mu_id)")
    lines.append("")
    lines.append("")
    lines.append("def get_unit_for_hs(hs_code: str) -> dict | None:")
    lines.append('    """')
    lines.append("    Get the statistical/measurement unit for an HS code.")
    lines.append("")
    lines.append("    Returns {en: str, he: str} or None if percentage-based or not found.")
    lines.append('    """')
    lines.append("    data = get_supplement_rate(hs_code)")
    lines.append("    if data and data.get('mu_id'):")
    lines.append("        return STATISTICAL_UNITS.get(data['mu_id'])")
    lines.append("    return None")
    lines.append("")

    content = "\n".join(lines) + "\n"

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"  Written {size_kb:.0f} KB")


if __name__ == "__main__":
    supplement_rates, general_customs, purchase_tax = build()
    write_output(supplement_rates, general_customs, purchase_tax)

    print()
    print("Verification:")

    # Import and test
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
    from _tariff_supplements import (
        get_supplement_rate, get_general_customs, get_purchase_tax,
        get_statistical_unit, get_unit_for_hs,
        SUPPLEMENT_RATES, GENERAL_CUSTOMS, PURCHASE_TAX, STATISTICAL_UNITS,
    )

    print(f"  SUPPLEMENT_RATES: {len(SUPPLEMENT_RATES)} entries")
    print(f"  GENERAL_CUSTOMS: {len(GENERAL_CUSTOMS)} entries")
    print(f"  PURCHASE_TAX: {len(PURCHASE_TAX)} entries")
    print(f"  STATISTICAL_UNITS: {len(STATISTICAL_UNITS)} entries")

    # Test a few known codes
    test_codes = ["7304190000", "8703808000", "4011100000", "0207140000", "2204210000"]
    for code in test_codes:
        r = get_supplement_rate(code)
        if r:
            print(f"  {code}: customs={r.get('customs_rate','N/A')}, PT={r.get('purchase_tax','N/A')}, mu={r.get('mu_id','N/A')}")
        else:
            print(f"  {code}: not found")

    # Test parent code fallback
    r = get_supplement_rate("73.04.190000/9")
    print(f"  73.04.190000/9 (formatted): {r is not None}")

    print()
    print("Done.")
