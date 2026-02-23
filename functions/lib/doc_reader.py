"""
Document Reader — Brain's reading engine
Reads documents structurally, learns templates, extracts without LLM over time.

LAYERS:
  1. Smart parsing (HTML tables, PDF tables, Excel → structured text)
  2. Template-based extraction (brain reads known formats independently)
  3. Template learning (stores HOW to read from successful LLM extractions)
  4. Template validation (cross-checks, builds confidence)

HARD RULES:
  - NEVER invent data
  - NEVER guess — if not found, return empty
  - Only extract values that exist in raw text
  - Templates only match verified patterns
"""

import re
from datetime import datetime, timezone


# ═══════════════════════════════════════════
#  LAYER 1: SMART PARSING — preserve structure
# ═══════════════════════════════════════════

def parse_html_tables(html):
    """Extract tables from HTML body as structured text.
    Port notifications, manifests, delivery orders come as HTML tables.
    Returns: list of dicts with headers and rows."""
    if not html or '<table' not in html.lower():
        return []

    tables = []
    # Find all <table> blocks
    table_pattern = re.compile(r'<table[^>]*>(.*?)</table>', re.DOTALL | re.IGNORECASE)
    for table_match in table_pattern.finditer(html):
        table_html = table_match.group(1)
        rows = []
        # Extract rows
        for row_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.IGNORECASE):
            cells = []
            for cell_match in re.finditer(r'<t[dh][^>]*>(.*?)</t[dh]>', row_match.group(1), re.DOTALL | re.IGNORECASE):
                # Clean cell content
                cell_text = re.sub(r'<[^>]+>', ' ', cell_match.group(1))
                cell_text = re.sub(r'&nbsp;', ' ', cell_text)
                cell_text = re.sub(r'&amp;', '&', cell_text)
                cell_text = re.sub(r'\s+', ' ', cell_text).strip()
                cells.append(cell_text)
            if cells:
                rows.append(cells)

        if rows:
            tables.append({"rows": rows, "num_rows": len(rows), "num_cols": max(len(r) for r in rows)})

    return tables


def html_tables_to_text(html):
    """Convert HTML tables to structured text preserving row/column layout.
    Use this INSTEAD of _strip_html for the table portions."""
    tables = parse_html_tables(html)
    if not tables:
        return ""

    parts = []
    for i, table in enumerate(tables):
        lines = []
        for row in table["rows"]:
            lines.append(" | ".join(row))
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def smart_read_html_body(html):
    """Read HTML body preserving both free text and table structure.
    Returns combined structured text."""
    if not html:
        return ""

    # Extract tables as structured text
    table_text = html_tables_to_text(html)

    # Extract non-table text
    # Remove tables from HTML first
    no_tables = re.sub(r'<table[^>]*>.*?</table>', ' [TABLE] ', html, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining HTML
    plain = re.sub(r'<style[^>]*>.*?</style>', '', no_tables, flags=re.DOTALL | re.IGNORECASE)
    plain = re.sub(r'<script[^>]*>.*?</script>', '', plain, flags=re.DOTALL | re.IGNORECASE)
    plain = re.sub(r'<br\s*/?\s*>', '\n', plain, flags=re.IGNORECASE)
    plain = re.sub(r'<[^>]+>', ' ', plain)
    plain = re.sub(r'&nbsp;', ' ', plain)
    plain = re.sub(r'&amp;', '&', plain)
    plain = re.sub(r'&lt;', '<', plain)
    plain = re.sub(r'&gt;', '>', plain)
    plain = re.sub(r'&#39;', "'", plain)
    plain = re.sub(r'&quot;', '"', plain)
    plain = re.sub(r'[ \t]+', ' ', plain)
    plain = re.sub(r'\n\s*\n', '\n\n', plain)
    plain = plain.strip()

    # Combine: free text + structured tables
    if table_text:
        return f"{plain}\n\n=== TABLES ===\n{table_text}"
    return plain


def extract_pdf_tables(pdf_bytes):
    """Extract tables from PDF using pdfplumber's table detection.
    Returns structured text of all tables found."""
    try:
        import pdfplumber
        import io
        tables_text = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                page_tables = page.extract_tables()
                if page_tables:
                    for j, table in enumerate(page_tables):
                        lines = []
                        for row in table:
                            cells = [str(c).strip() if c else '' for c in row]
                            if any(cells):
                                lines.append(" | ".join(cells))
                        if lines:
                            tables_text.append(f"--- Page {i+1} Table {j+1} ---\n" + "\n".join(lines))
        return "\n\n".join(tables_text)
    except Exception as e:
        print(f"    📊 PDF table extraction error: {e}")
        return ""


# ═══════════════════════════════════════════
#  LAYER 2: DOCUMENT TYPE IDENTIFICATION
# ═══════════════════════════════════════════

DOC_TYPE_SIGNALS = {
    'bol_pdf': {
        'en': ['bill of lading', 'b/l', 'shipped on board', 'consignee', 'shipper',
               'notify party', 'port of loading', 'port of discharge'],
        'he': ['שטר מטען', 'שטר מטעין'],
        'min_score': 3
    },
    'notice_of_arrival': {
        'en': ['notice of arrival', 'vessel arrival', 'eta', 'estimated arrival',
               'arrival notice', 'discharge list'],
        'he': ['הודעת הגעה', 'הגעת טובין', 'הודעה על הגעת', 'רשימת פריקה'],
        'min_score': 2
    },
    'delivery_order': {
        'en': ['delivery order', 'release order', 'getpass', 'gate pass',
               'release note', 'delivery note'],
        'he': ['פקודת מסירה', 'אישור מסירה', 'הוצאה מנמל', 'גטפס'],
        'min_score': 2
    },
    'customs_declaration': {
        'en': ['customs declaration', 'entry number', 'declaration number',
               'customs entry', 'import declaration'],
        'he': ['רשימון', 'הצהרת מכס', 'רשימון יבוא', 'רשימון יצוא'],
        'min_score': 2
    },
    'commercial_invoice': {
        'en': ['commercial invoice', 'invoice no', 'invoice number', 'total amount',
               'terms of payment', 'unit price'],
        'he': ['חשבונית מסחרית', 'חשבונית ספק'],
        'min_score': 2
    },
    'packing_list': {
        'en': ['packing list', 'packing note', 'package list', 'carton no',
               'gross weight', 'net weight', 'number of packages'],
        'he': ['רשימת אריזה', 'רשימת אריזות'],
        'min_score': 2
    },
    'manifest': {
        'en': ['manifest', 'cargo manifest', 'freight manifest', 'inward manifest'],
        'he': ['מניפסט', 'מנויפסט'],
        'min_score': 2
    },
    'storage_cert': {
        'en': ['storage certificate', 'warehouse receipt', 'storage receipt'],
        'he': ['תעודת אחסנה', 'אישור אחסנה'],
        'min_score': 2
    },
    'release_cert': {
        'en': ['phytosanitary', 'veterinary', 'health certificate', 'fumigation',
               'certificate of origin', 'inspection certificate'],
        'he': ['תעודה פיטוסניטרית', 'תעודה וטרינרית', 'תעודת בריאות', 'חיטוי',
               'תעודת מקור', 'אישור בדיקה'],
        'min_score': 2
    },
    'shipping_instruction': {
        'en': ['shipping instruction', 'booking confirmation', 'booking request',
               'export instruction', 'si instruction'],
        'he': ['הוראות משלוח', 'אישור הזמנה', 'הוראות יצוא'],
        'min_score': 2
    },
    'port_report': {
        'en': ['daily report', 'port report', 'vessel schedule', 'berth allocation',
               'discharge progress', 'loading progress'],
        'he': ['דוח יומי', 'דוח נמל', 'לוח אוניות', 'הקצאת רציף'],
        'min_score': 2
    },
    # FIATA document types (added by shipping_knowledge.py research)
    'fiata_fbl': {
        'en': ['fiata multimodal', 'FBL', 'multimodal transport bill of lading',
               'negotiable transport bill of lading'],
        'he': ['שטר מטען רב אמצעי', 'פיאטה'],
        'min_score': 2
    },
    'fiata_fwr': {
        'en': ['fiata warehouse receipt', 'FWR', 'warehouse receipt'],
        'he': ['תעודת מחסן', 'קבלת מחסן'],
        'min_score': 2
    },
    'dangerous_goods_declaration': {
        'en': ['dangerous goods declaration', 'DGD', 'shipper declaration dangerous',
               'UN number', 'IMDG', 'packing group', 'proper shipping name'],
        'he': ['הצהרת חומרים מסוכנים', 'מטענים מסוכנים'],
        'min_score': 2
    },
    'air_waybill': {
        'en': ['air waybill', 'AWB', 'airway bill', 'master air waybill', 'MAWB',
               'house air waybill', 'HAWB', 'airport of departure', 'IATA'],
        'he': ['שטר מטען אווירי', 'שטר אוויר'],
        'min_score': 2
    },
    'vessel_schedule': {
        'en': ['vessel schedule', 'sailing schedule', 'transit time',
               'port of loading', 'port of discharge', 'voyage number',
               'vessel name', 'cut-off date', 'ETA', 'ETD'],
        'he': ['לוח הפלגות', 'הפלגה', 'זמן מעבר'],
        'min_score': 3
    },
    'arrival_notice': {
        'en': ['arrival notice', 'notice of arrival', 'cargo arrival',
               'container arrival', 'shipment arrival notification',
               'ready for pickup', 'demurrage'],
        'he': ['הודעת הגעה', 'הודעת הגעת מכולה', 'הודעת פריקה'],
        'min_score': 2
    },
}


def identify_doc_type(text, filename=""):
    """Identify document type from text content and filename.
    Returns (doc_type, confidence) — never guesses."""
    if not text:
        return "unknown", 0.0

    text_lower = text.lower()
    filename_lower = filename.lower() if filename else ""

    best_type = "unknown"
    best_score = 0

    for doc_type, signals in DOC_TYPE_SIGNALS.items():
        score = 0
        for term in signals.get('en', []):
            if term in text_lower:
                score += 1
        for term in signals.get('he', []):
            if term in text_lower:
                score += 1.5  # Hebrew terms are more specific

        # Filename bonus
        type_short = doc_type.replace('_', ' ')
        if type_short in filename_lower or doc_type.split('_')[0] in filename_lower:
            score += 2

        if score >= signals['min_score'] and score > best_score:
            best_score = score
            best_type = doc_type

    confidence = min(best_score / 6.0, 1.0) if best_score > 0 else 0.0
    return best_type, confidence


# ═══════════════════════════════════════════
#  LAYER 3: TEMPLATE-BASED EXTRACTION
# ═══════════════════════════════════════════

def try_template_extraction(full_text, shipping_line, doc_type, db):
    """Try to extract data using a learned brain template.
    Returns (extractions_dict, used_template) or (None, False).
    NEVER invents — only extracts values found in text."""
    if not db or not full_text:
        return None, False

    try:
        # Find matching template
        template_key = f"{shipping_line}_{doc_type}".lower().replace(' ', '_')
        doc = db.collection("learned_doc_templates").document(template_key).get()

        if not doc.exists:
            # Try just doc_type
            doc = db.collection("learned_doc_templates").document(doc_type).get()
            if not doc.exists:
                return None, False

        template = doc.to_dict()

        # Only use templates with enough confidence
        if template.get('confidence', 0) < 0.4 or template.get('times_seen', 0) < 2:
            return None, False

        field_templates = template.get('field_templates', {})
        if not field_templates:
            return None, False

        extractions = {}
        fields_found = 0

        for field_name, ft in field_templates.items():
            context_before = ft.get('context_before', '')
            context_after = ft.get('context_after', '')

            if not context_before:
                continue

            # Find context_before in text (fuzzy — allow whitespace differences)
            cb_pattern = re.escape(context_before).replace(r'\ ', r'\s+').replace(r'\\\n', r'\s+')
            cb_match = re.search(cb_pattern, full_text, re.IGNORECASE)
            if not cb_match:
                continue

            # Extract value after context_before
            start = cb_match.end()
            # Find context_after or take next 100 chars
            if context_after:
                ca_pattern = re.escape(context_after).replace(r'\ ', r'\s+').replace(r'\\\n', r'\s+')
                ca_match = re.search(ca_pattern, full_text[start:start + 200], re.IGNORECASE)
                if ca_match:
                    end = start + ca_match.start()
                else:
                    end = start + 100
            else:
                end = start + 100

            value = full_text[start:end].strip()
            # Clean value — remove trailing newlines, excess whitespace
            value = re.sub(r'\s+', ' ', value).strip()
            value = value.rstrip('|,;:')

            if value and len(value) > 2 and len(value) < 200:
                # VERIFY value exists in original text (hard rule: never invent)
                if value in full_text or value.lower() in full_text.lower():
                    extractions[field_name] = [value] if field_name in (
                        'shippers', 'consignees', 'vessels', 'containers',
                        'bols', 'bookings', 'manifests', 'declarations',
                        'weights', 'etas', 'etds', 'ports') else value
                    fields_found += 1

        if fields_found > 0:
            print(f"    📖 Template extracted {fields_found} fields using '{template_key}'")
            # Update template usage stats
            try:
                db.collection("learned_doc_templates").document(doc.id).update({
                    "times_used": template.get('times_used', 0) + 1,
                    "last_used": datetime.now(timezone.utc)
                })
            except Exception as e:
                print(f"doc_reader: template stats update failed: {e}")
            return extractions, True

        return None, False

    except Exception as e:
        print(f"    📖 Template extraction error: {e}")
        return None, False


# ═══════════════════════════════════════════
#  LAYER 4: TEMPLATE LEARNING
# ═══════════════════════════════════════════

def learn_template(full_text, extractions, shipping_line, doc_type, db):
    """Learn HOW to read a document by finding WHERE each extracted value lives.
    Called after successful LLM extraction.
    Stores context patterns for future template-based extraction."""
    if not db or not full_text or not extractions:
        return False

    try:
        # Don't create templates for unknown doc types — they're useless
        if doc_type in ('unknown', 'other', '', None):
            return False

        template_key = f"{shipping_line}_{doc_type}".lower().replace(' ', '_')
        if not template_key or template_key == '_':
            template_key = doc_type

        field_templates = {}
        fields_learned = 0

        # Fields we want to learn context for
        learnable_fields = {
            'shippers': 'list',
            'consignees': 'list',
            'vessels': 'list',
            'bookings': 'list',
            'weights': 'list',
            'etas': 'list',
            'etds': 'list',
        }

        for field_name, field_type in learnable_fields.items():
            values = extractions.get(field_name, [])
            if not values:
                continue
            if isinstance(values, str):
                values = [values]

            # Take first non-empty value
            value = None
            for v in values:
                if v and isinstance(v, str) and len(v) > 2:
                    value = v
                    break
            if not value:
                continue

            # Find value in full_text
            pos = full_text.find(value)
            if pos < 0:
                # Try case-insensitive
                pos = full_text.lower().find(value.lower())
            if pos < 0:
                continue

            # Extract context: 60 chars before and after
            ctx_start = max(0, pos - 60)
            ctx_end = min(len(full_text), pos + len(value) + 60)

            context_before = full_text[ctx_start:pos].strip()
            context_after = full_text[pos + len(value):ctx_end].strip()

            # Clean context (collapse whitespace, keep structure markers)
            context_before = re.sub(r'[ \t]+', ' ', context_before)
            context_after = re.sub(r'[ \t]+', ' ', context_after)

            # Only store if context is meaningful (not just whitespace)
            if len(context_before) > 3:
                field_templates[field_name] = {
                    "context_before": context_before[-50:],  # Last 50 chars before value
                    "context_after": context_after[:50],      # First 50 chars after value
                    "value_example": value,
                    "char_position_pct": round(pos / len(full_text) * 100, 1),
                }
                fields_learned += 1

        if fields_learned == 0:
            return False

        # Store or update template
        existing = db.collection("learned_doc_templates").document(template_key).get()
        if existing.exists:
            old = existing.to_dict()
            old_templates = old.get('field_templates', {})
            # Merge: add new fields, keep existing
            for k, v in field_templates.items():
                if k not in old_templates:
                    old_templates[k] = v
            db.collection("learned_doc_templates").document(template_key).update({
                "field_templates": old_templates,
                "times_seen": old.get('times_seen', 0) + 1,
                "last_seen": datetime.now(timezone.utc),
                "fields_count": len(old_templates),
            })
        else:
            db.collection("learned_doc_templates").document(template_key).set({
                "template_key": template_key,
                "shipping_line": shipping_line or "",
                "doc_type": doc_type or "",
                "field_templates": field_templates,
                "times_seen": 1,
                "times_used": 0,
                "times_validated": 0,
                "confidence": 0.5,
                "fields_count": fields_learned,
                "created_at": datetime.now(timezone.utc),
                "last_seen": datetime.now(timezone.utc),
                "last_used": None,
            })

        print(f"    📖 Template LEARNED: '{template_key}' — {fields_learned} field contexts stored")
        return True

    except Exception as e:
        print(f"    📖 Template learning error: {e}")
        return False


def validate_template(template_extraction, actual_extraction, template_key, db):
    """Compare template extraction vs actual (LLM/regex) extraction.
    If they match → boost confidence. If differ → flag for review."""
    if not db or not template_extraction or not actual_extraction:
        return

    try:
        matches = 0
        mismatches = 0

        for field in ['shippers', 'consignees', 'vessels', 'bookings', 'weights']:
            tmpl_val = template_extraction.get(field)
            actual_val = actual_extraction.get(field)

            if not tmpl_val and not actual_val:
                continue  # Both empty — not a data point

            if tmpl_val and actual_val:
                # Compare (normalize for comparison)
                t = str(tmpl_val[0] if isinstance(tmpl_val, list) else tmpl_val).lower().strip()
                a = str(actual_val[0] if isinstance(actual_val, list) else actual_val).lower().strip()
                if t == a or t in a or a in t:
                    matches += 1
                else:
                    mismatches += 1
            else:
                mismatches += 1

        doc = db.collection("learned_doc_templates").document(template_key).get()
        if not doc.exists:
            return

        template = doc.to_dict()

        if matches > 0 and mismatches == 0:
            # Perfect match — boost confidence
            new_conf = min(template.get('confidence', 0.5) + 0.1, 0.95)
            db.collection("learned_doc_templates").document(template_key).update({
                "times_validated": template.get('times_validated', 0) + 1,
                "confidence": new_conf,
                "last_validated": datetime.now(timezone.utc),
            })
            print(f"    ✅ Template '{template_key}' validated: {matches} matches, conf→{new_conf:.0%}")
        elif mismatches > matches:
            # More wrong than right — decrease confidence
            new_conf = max(template.get('confidence', 0.5) - 0.15, 0.1)
            db.collection("learned_doc_templates").document(template_key).update({
                "confidence": new_conf,
                "last_validated": datetime.now(timezone.utc),
                "last_mismatch": {
                    "template_got": {k: v for k, v in template_extraction.items() if v},
                    "actual_got": {k: v for k, v in actual_extraction.items() if v},
                    "at": datetime.now(timezone.utc),
                }
            })
            print(f"    ⚠️ Template '{template_key}' mismatch: {mismatches} wrong, conf→{new_conf:.0%}")

    except Exception as e:
        print(f"    📖 Template validation error: {e}")


# ═══════════════════════════════════════════
#  MASTER READ FUNCTION
# ═══════════════════════════════════════════

def smart_read(subject, html_body, attachment_texts, attachment_tables=None):
    """Master read function — produces the richest possible text from all sources.

    Args:
        subject: email subject line
        html_body: raw HTML body of email
        attachment_texts: already-extracted text from attachments (from rcb_helpers)
        attachment_tables: PDF table text (optional, from extract_pdf_tables)

    Returns: full_text combining all structured sources
    """
    parts = []

    # Subject
    if subject:
        parts.append(subject)

    # HTML body — preserve table structure
    if html_body:
        structured_body = smart_read_html_body(html_body)
        parts.append(structured_body)

    # Attachment text (already extracted by rcb_helpers)
    if attachment_texts:
        parts.append(attachment_texts)

    # PDF tables (structural extraction)
    if attachment_tables:
        parts.append(f"=== PDF TABLES ===\n{attachment_tables}")

    full_text = "\n\n".join(p for p in parts if p)
    return full_text
