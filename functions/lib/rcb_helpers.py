"""RCB Helper functions - Graph API, PDF extraction, Hebrew names
UPDATED Session 17 Phase 0: Improved document extraction
"""
import requests
import base64
import io
import re
from datetime import datetime

# ============================================================
# PDF TEXT EXTRACTION (with OCR fallback)
# Phase 0: Improved extraction quality, table handling, OCR
# ============================================================

def _assess_extraction_quality(text):
    """Check if extracted text is actually useful, not garbage"""
    if not text or len(text.strip()) < 50:
        return False, "too_short"

    stripped = text.strip()

    # Check for Hebrew content (customs docs should have Hebrew)
    hebrew_chars = sum(1 for c in stripped if '\u0590' <= c <= '\u05FF')
    latin_chars = sum(1 for c in stripped if c.isascii() and c.isalpha())
    digit_chars = sum(1 for c in stripped if c.isdigit())
    total_meaningful = hebrew_chars + latin_chars + digit_chars

    # If less than 30% of text is meaningful characters, it's garbage
    if len(stripped) > 0 and total_meaningful / len(stripped) < 0.3:
        return False, "garbage_chars"

    # Check for invoice-like patterns (numbers, currency, dates)
    has_numbers = bool(re.search(r'\d{3,}', stripped))  # 3+ digit numbers
    has_currency = bool(re.search(r'(USD|EUR|ILS|NIS|\$|€|₪)', stripped, re.IGNORECASE))
    has_date = bool(re.search(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}', stripped))

    # If we have meaningful length but no numbers AND no meaningful text, probably wrong extraction
    # Don't reject certificates, EUR.1, letters that have text but no numbers
    if len(stripped) > 200 and not has_numbers and hebrew_chars < 20 and latin_chars < 20:
        return False, "no_numbers"

    return True, "ok"


def _cleanup_hebrew_text(text):
    """Fix common Hebrew/RTL extraction issues"""
    if not text:
        return text

    # Normalize whitespace
    text = re.sub(r' {3,}', '  ', text)  # Multiple spaces to double
    text = re.sub(r'\n{4,}', '\n\n\n', text)  # Multiple newlines to max 3

    # Fix common OCR mistakes in Hebrew customs context
    replacements = {
        'חשבוו': 'חשבון',
        'מע"ט': 'מע"מ',
        'עמיל מכם': 'עמיל מכס',
    }
    for wrong, right in replacements.items():
        text = text.replace(wrong, right)

    return text


def _tag_document_structure(text):
    """Tag document sections to help AI classification agent"""
    tags = []

    # Detect invoice number
    inv_match = re.search(r'(?:invoice|inv|חשבונית|חשבון)[\s#:]*(\S+)', text, re.IGNORECASE)
    if inv_match:
        tags.append(f"[INVOICE_NUMBER: {inv_match.group(1)}]")

    # Detect dates
    dates = re.findall(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}', text)
    if dates:
        tags.append(f"[DATES_FOUND: {', '.join(dates[:5])}]")

    # Detect currency and amounts
    amounts = re.findall(r'(?:USD|EUR|ILS|NIS|\$|€|₪)\s*[\d,.]+', text, re.IGNORECASE)
    if not amounts:
        amounts = re.findall(r'[\d,.]+\s*(?:USD|EUR|ILS|NIS|\$|€|₪)', text, re.IGNORECASE)
    if amounts:
        tags.append(f"[AMOUNTS: {', '.join(amounts[:10])}]")

    # Detect HS code patterns (XX.XX or XXXX.XX.XXXX)
    hs_codes = re.findall(r'\b\d{4}[.\s]\d{2}(?:[.\s]\d{2,6})?\b', text)
    if hs_codes:
        tags.append(f"[HS_CODE_CANDIDATES: {', '.join(set(hs_codes[:10]))}]")

    # Detect BL/AWB numbers
    bl_match = re.search(r'(?:B/?L|bill\s*of\s*lading|שטר\s*מטען)[\s#:]*(\S+)', text, re.IGNORECASE)
    if bl_match:
        tags.append(f"[BL_NUMBER: {bl_match.group(1)}]")

    awb_match = re.search(r'(?:AWB|air\s*waybill)[\s#:]*(\S+)', text, re.IGNORECASE)
    if awb_match:
        tags.append(f"[AWB_NUMBER: {awb_match.group(1)}]")

    # Detect country names
    countries = re.findall(r'(?:China|India|Turkey|Germany|USA|Italy|Japan|Korea|Vietnam|Thailand|'
                           r'סין|הודו|טורקיה|גרמניה|ארה"ב|איטליה|יפן|קוריאה|וייטנאם|תאילנד)',
                           text, re.IGNORECASE)
    if countries:
        tags.append(f"[COUNTRIES: {', '.join(set(countries[:5]))}]")

    # Detect shipping terms
    incoterms = re.findall(r'\b(?:FOB|CIF|CFR|EXW|DDP|DAP|FCA|CPT|CIP|DAT)\b', text, re.IGNORECASE)
    if incoterms:
        tags.append(f"[INCOTERMS: {', '.join(set(incoterms))}]")

    if tags:
        header = "\n".join(tags)
        return f"[DOCUMENT_ANALYSIS]\n{header}\n[/DOCUMENT_ANALYSIS]\n\n{text}"

    return text


def _preprocess_image_for_ocr(img_bytes):
    """Preprocess image for better OCR accuracy"""
    try:
        from PIL import Image, ImageEnhance, ImageFilter

        img = Image.open(io.BytesIO(img_bytes))

        # Convert to grayscale
        if img.mode != 'L':
            img = img.convert('L')

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)

        # Sharpen
        img = img.filter(ImageFilter.SHARPEN)

        # Convert back to bytes
        output = io.BytesIO()
        img.save(output, format='PNG')
        return output.getvalue()
    except Exception as e:
        print(f"  Image preprocessing error: {e}")
        return img_bytes  # Return original if preprocessing fails


def extract_text_from_pdf_bytes(pdf_bytes):
    """Extract text from PDF bytes - tries multiple methods
    Phase 0: Improved quality assessment, combined extraction, better OCR"""

    # Method 1: pdfplumber (fast, for text-based PDFs)
    text = _extract_with_pdfplumber(pdf_bytes)
    is_good, reason = _assess_extraction_quality(text)
    if is_good:
        print(f"    ✅ pdfplumber extracted {len(text)} chars (quality: {reason})")
        return text
    elif text:
        print(f"    ⚠️ pdfplumber: {len(text)} chars but quality: {reason}")

    # Method 2: pypdf (sometimes works better)
    text = _extract_with_pypdf(pdf_bytes)
    is_good, reason = _assess_extraction_quality(text)
    if is_good:
        print(f"    ✅ pypdf extracted {len(text)} chars (quality: {reason})")
        return text

    # Method 3: COMBINED - try pdfplumber + pypdf merged
    combined = _extract_with_pdfplumber(pdf_bytes) + "\n" + _extract_with_pypdf(pdf_bytes)
    is_good, reason = _assess_extraction_quality(combined)
    if is_good:
        print(f"    ✅ Combined extraction: {len(combined)} chars")
        return combined

    # Method 4: Vision OCR (preprocessed, 300 DPI)
    print(f"    🔍 All text methods failed, trying OCR...")
    text = _extract_with_vision_ocr(pdf_bytes)
    if text:
        print(f"    ✅ OCR extracted {len(text)} chars")
    else:
        print(f"    ⚠️ All extraction methods failed")
    return text or ""


def _extract_with_pdfplumber(pdf_bytes):
    """Extract text using pdfplumber with improved table handling"""
    try:
        import pdfplumber
        text_parts = []

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Extract regular text
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

                # Extract tables with better settings
                tables = page.extract_tables({
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 5,
                    "join_tolerance": 5,
                    "edge_min_length": 10,
                    "min_words_vertical": 1,
                    "min_words_horizontal": 1,
                })

                for table_idx, table in enumerate(tables):
                    if not table:
                        continue

                    # Format table with structure preserved
                    table_text = f"\n[TABLE {table_idx + 1} on page {page_num + 1}]\n"
                    for row in table:
                        if row:
                            cells = [str(cell).strip() if cell else "" for cell in row]
                            # Skip completely empty rows
                            if any(cells):
                                table_text += " | ".join(cells) + "\n"
                    table_text += f"[/TABLE]\n"
                    text_parts.append(table_text)

        return _cleanup_hebrew_text("\n".join(text_parts))
    except Exception as e:
        print(f"    pdfplumber error: {e}")
        return ""


def _extract_with_pypdf(pdf_bytes):
    """Extract text using pypdf"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return _cleanup_hebrew_text("\n".join(text_parts))
    except Exception as e:
        print(f"    pypdf error: {e}")
        return ""


def _extract_with_vision_ocr(pdf_bytes):
    """Extract text using Google Cloud Vision OCR
    Phase 0: Added image preprocessing before OCR"""
    try:
        from google.cloud import vision

        # Convert PDF pages to images first
        images = _pdf_to_images(pdf_bytes)
        if not images:
            print(f"    ⚠️ Could not convert PDF to images")
            return ""

        client = vision.ImageAnnotatorClient()
        all_text = []

        for i, img_bytes in enumerate(images):
            # Phase 0: Preprocess image before OCR
            img_bytes = _preprocess_image_for_ocr(img_bytes)
            image = vision.Image(content=img_bytes)
            response = client.text_detection(image=image)

            if response.text_annotations:
                page_text = response.text_annotations[0].description
                all_text.append(f"--- Page {i+1} ---\n{page_text}")
                print(f"    📄 Page {i+1}: {len(page_text)} chars")

            if response.error.message:
                print(f"    Vision API error: {response.error.message}")

        return _cleanup_hebrew_text("\n\n".join(all_text))
    except ImportError:
        print(f"    ⚠️ google-cloud-vision not installed")
        return ""
    except Exception as e:
        print(f"    Vision OCR error: {e}")
        return ""


def _pdf_to_images(pdf_bytes):
    """Convert PDF pages to images for OCR
    Phase 0: Raised DPI from 150 to 300"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []

        for page_num in range(min(len(doc), 10)):  # Max 10 pages
            page = doc[page_num]
            # Phase 0: Render at 300 DPI (was 150) for better OCR accuracy
            pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
            img_bytes = pix.tobytes("png")
            images.append(img_bytes)

        doc.close()
        return images
    except ImportError:
        print(f"    ⚠️ PyMuPDF not installed, trying pdf2image...")
        return _pdf_to_images_fallback(pdf_bytes)
    except Exception as e:
        print(f"    PDF to image error: {e}")
        return []


def _pdf_to_images_fallback(pdf_bytes):
    """Fallback: Convert PDF to images using pdf2image"""
    try:
        from pdf2image import convert_from_bytes
        images = convert_from_bytes(pdf_bytes, dpi=300, first_page=1, last_page=10)
        result = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            result.append(buf.getvalue())
        return result
    except Exception as e:
        print(f"    pdf2image error: {e}")
        return []


def _try_decode(raw_bytes):
    """Decode bytes trying Hebrew-friendly encodings.
    Israeli government files often use Windows-1255, not UTF-8."""
    for encoding in ('utf-8', 'windows-1255', 'iso-8859-8', 'latin-1'):
        try:
            return raw_bytes.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw_bytes.decode('utf-8', errors='replace')


def _extract_from_excel(file_bytes):
    """Extract text from Excel files (.xlsx, .xls)"""
    try:
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        text_parts = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            text_parts.append(f"[SHEET: {sheet_name}]")
            for row in ws.iter_rows(values_only=True):
                cells = [str(cell).strip() if cell is not None else "" for cell in row]
                if any(cells):
                    text_parts.append(" | ".join(cells))
            text_parts.append(f"[/SHEET]")

        wb.close()
        return "\n".join(text_parts)
    except Exception as e:
        print(f"    Excel extraction error: {e}")
        return ""


def _extract_from_docx(file_bytes):
    """Extract text from Word documents (.docx)"""
    try:
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        text_parts = []

        # Extract paragraphs
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)

        # Extract tables
        for table_idx, table in enumerate(doc.tables):
            text_parts.append(f"\n[TABLE {table_idx + 1}]")
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    text_parts.append(" | ".join(cells))
            text_parts.append(f"[/TABLE]")

        return "\n".join(text_parts)
    except Exception as e:
        print(f"    Word extraction error: {e}")
        return ""


def _extract_from_eml(file_bytes):
    """Extract text from email files (.eml, .msg)"""
    try:
        import email
        from email import policy
        msg = email.message_from_bytes(file_bytes, policy=policy.default)
        text_parts = []

        # Extract headers
        subject = msg.get('Subject', '')
        from_addr = msg.get('From', '')
        date = msg.get('Date', '')
        if subject:
            text_parts.append(f"Subject: {subject}")
        if from_addr:
            text_parts.append(f"From: {from_addr}")
        if date:
            text_parts.append(f"Date: {date}")
        text_parts.append("")

        # Extract body
        body = msg.get_body(preferencelist=('plain', 'html'))
        if body:
            content = body.get_content()
            if body.get_content_type() == 'text/html':
                # Strip HTML tags
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'\s+', ' ', content).strip()
            text_parts.append(content)

        return "\n".join(text_parts)
    except Exception as e:
        print(f"    Email extraction error: {e}")
        return ""


def _extract_from_msg(file_bytes):
    """Extract text from Outlook .msg files"""
    try:
        import extract_msg
        msg = extract_msg.Message(io.BytesIO(file_bytes))
        text_parts = []

        if msg.subject:
            text_parts.append(f"Subject: {msg.subject}")
        if msg.sender:
            text_parts.append(f"From: {msg.sender}")
        if msg.date:
            text_parts.append(f"Date: {msg.date}")
        text_parts.append("")

        if msg.body:
            text_parts.append(msg.body)
        elif msg.htmlBody:
            content = re.sub(r'<[^>]+>', ' ', msg.htmlBody if isinstance(msg.htmlBody, str) else _try_decode(msg.htmlBody))
            content = re.sub(r'\s+', ' ', content).strip()
            text_parts.append(content)

        msg.close()
        return "\n".join(text_parts)
    except ImportError:
        print("    extract-msg not installed, cannot read .msg files")
        return ""
    except Exception as e:
        print(f"    MSG extraction error: {e}")
        return ""


def _extract_urls_from_text(text):
    """Detect URLs in text and append them as tagged section"""
    if not text:
        return text
    urls = re.findall(r'https?://[^\s<>"\')\]]+', text)
    if urls:
        unique_urls = list(dict.fromkeys(urls))  # Preserve order, remove dupes
        url_section = "\n[URLS_FOUND]\n" + "\n".join(unique_urls[:20]) + "\n[/URLS_FOUND]"
        return text + url_section
    return text


def extract_text_from_attachments(attachments_data, email_body=None):
    """Extract text from all attachments (PDF, Excel, Word, images, emails)
    Phase 0: Added Hebrew cleanup, structure tagging, multi-format support"""
    all_text = []

    # Extract URLs from email body if provided
    if email_body:
        email_body = _extract_urls_from_text(email_body)
        all_text.append(f"=== Email Body ===\n{email_body}")

    for att in attachments_data:
        name = att.get('name', 'file')
        content_bytes = att.get('contentBytes', '')

        if not content_bytes:
            continue

        # Decode base64
        try:
            file_bytes = base64.b64decode(content_bytes)
        except Exception:
            continue

        name_lower = name.lower()

        # PDF
        if name_lower.endswith('.pdf'):
            print(f"    📄 Extracting text from: {name}")
            text = extract_text_from_pdf_bytes(file_bytes)
            if text:
                text = _cleanup_hebrew_text(text)
                text = _tag_document_structure(text)
                all_text.append(f"=== {name} ===\n{text}")
            else:
                all_text.append(f"=== {name} ===\n[No text could be extracted]")

        # Excel
        elif name_lower.endswith(('.xlsx', '.xls')):
            print(f"    📊 Extracting text from: {name}")
            text = _extract_from_excel(file_bytes)
            if text:
                text = _cleanup_hebrew_text(text)
                text = _tag_document_structure(text)
                all_text.append(f"=== {name} ===\n{text}")

        # Word
        elif name_lower.endswith('.docx'):
            print(f"    📝 Extracting text from: {name}")
            text = _extract_from_docx(file_bytes)
            if text:
                text = _cleanup_hebrew_text(text)
                text = _tag_document_structure(text)
                all_text.append(f"=== {name} ===\n{text}")

        # Email files — .eml
        elif name_lower.endswith('.eml'):
            print(f"    📧 Extracting text from: {name}")
            text = _extract_from_eml(file_bytes)
            if text:
                text = _cleanup_hebrew_text(text)
                text = _extract_urls_from_text(text)
                all_text.append(f"=== {name} ===\n{text}")

        # Email files — Outlook .msg
        elif name_lower.endswith('.msg'):
            print(f"    📧 Extracting text from: {name}")
            text = _extract_from_msg(file_bytes)
            if text:
                text = _cleanup_hebrew_text(text)
                text = _extract_urls_from_text(text)
                all_text.append(f"=== {name} ===\n{text}")

        # Images — OCR
        elif name_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
            print(f"    🖼️ OCR on image: {name}")
            img_bytes = _preprocess_image_for_ocr(file_bytes)
            text = _ocr_image(img_bytes)
            if text:
                text = _cleanup_hebrew_text(text)
                text = _tag_document_structure(text)
                all_text.append(f"=== {name} ===\n{text}")

        # TIFF — multi-page image, convert each page then OCR
        elif name_lower.endswith(('.tiff', '.tif')):
            print(f"    🖼️ OCR on TIFF: {name}")
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(file_bytes))
                tiff_parts = []
                page = 0
                while True:
                    try:
                        img.seek(page)
                    except EOFError:
                        break
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    page_bytes = _preprocess_image_for_ocr(buf.getvalue())
                    page_text = _ocr_image(page_bytes)
                    if page_text:
                        tiff_parts.append(f"--- Page {page + 1} ---\n{page_text}")
                    page += 1
                if tiff_parts:
                    text = _cleanup_hebrew_text("\n\n".join(tiff_parts))
                    text = _tag_document_structure(text)
                    all_text.append(f"=== {name} ===\n{text}")
            except Exception as e:
                print(f"    TIFF extraction error: {e}")

        # CSV / TSV
        elif name_lower.endswith(('.csv', '.tsv')):
            print(f"    📊 Extracting text from: {name}")
            try:
                text = _try_decode(file_bytes)
                sep = '\t' if name_lower.endswith('.tsv') else ','
                lines = text.strip().split('\n')
                table_parts = [f"[TABLE CSV]"]
                for line in lines[:500]:  # Cap at 500 rows
                    cells = line.strip().split(sep)
                    if any(c.strip() for c in cells):
                        table_parts.append(" | ".join(c.strip() for c in cells))
                table_parts.append("[/TABLE]")
                result_text = "\n".join(table_parts)
                result_text = _cleanup_hebrew_text(result_text)
                result_text = _tag_document_structure(result_text)
                all_text.append(f"=== {name} ===\n{result_text}")
            except Exception as e:
                print(f"    CSV extraction error: {e}")

        # HTML
        elif name_lower.endswith(('.html', '.htm')):
            print(f"    🌐 Extracting text from: {name}")
            try:
                text = _try_decode(file_bytes)
                text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                if text:
                    text = _cleanup_hebrew_text(text)
                    text = _tag_document_structure(text)
                    all_text.append(f"=== {name} ===\n{text}")
            except Exception as e:
                print(f"    HTML extraction error: {e}")

    # Fix 6: Extraction summary logging
    print(f"  📊 Extraction summary: {len(all_text)} files, {sum(len(t) for t in all_text)} total chars")
    for entry in all_text:
        # Extract filename from "=== filename ===" header
        header_end = entry.find('\n')
        header = entry[:header_end] if header_end > 0 else entry[:50]
        content = entry[header_end+1:] if header_end > 0 else ""
        preview = content[:100].replace('\n', ' ').strip()
        print(f"    {header} ({len(content)} chars) -> {preview}...")

    return "\n\n".join(all_text)


def _ocr_image(image_bytes):
    """OCR a single image using Google Cloud Vision"""
    try:
        from google.cloud import vision
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_bytes)
        response = client.text_detection(image=image)
        
        if response.text_annotations:
            return response.text_annotations[0].description
        return ""
    except Exception as e:
        print(f"    Image OCR error: {e}")
        return ""


# ============================================================
# MICROSOFT GRAPH API HELPERS
# ============================================================

def get_rcb_secrets_internal(get_secret_func):
    """Get RCB email secrets from Secret Manager"""
    try:
        secrets = {}
        for name in ['RCB_EMAIL', 'RCB_PASSWORD', 'RCB_FALLBACK_EMAIL', 
                     'RCB_GRAPH_CLIENT_ID', 'RCB_GRAPH_TENANT_ID', 'RCB_GRAPH_CLIENT_SECRET',
                     'ANTHROPIC_API_KEY']:
            secrets[name] = get_secret_func(name)
        return secrets if secrets.get('RCB_EMAIL') else None
    except Exception as e:
        print(f"Secret error: {e}")
        return None

def helper_get_graph_token(secrets):
    """Get Microsoft Graph API access token"""
    try:
        response = requests.post(
            f"https://login.microsoftonline.com/{secrets.get('RCB_GRAPH_TENANT_ID')}/oauth2/v2.0/token",
            data={
                'client_id': secrets.get('RCB_GRAPH_CLIENT_ID'),
                'client_secret': secrets.get('RCB_GRAPH_CLIENT_SECRET'),
                'scope': 'https://graph.microsoft.com/.default',
                'grant_type': 'client_credentials'
            }
        )
        return response.json().get('access_token') if response.status_code == 200 else None
    except Exception as e:
        print(f"Token error: {e}")
        return None

def helper_graph_messages(access_token, user_email, unread_only=True, max_results=10):
    """Get messages from inbox"""
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/mailFolders/inbox/messages"
        params = {'$top': max_results, '$orderby': 'receivedDateTime desc'}
        if unread_only:
            params['$filter'] = 'isRead eq false'
        response = requests.get(url, headers={'Authorization': f'Bearer {access_token}'}, params=params)
        return response.json().get('value', []) if response.status_code == 200 else []
    except Exception as e:
        print(f"Graph messages error: {e}")
        return []

def helper_graph_attachments(access_token, user_email, message_id):
    """Get message attachments"""
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{message_id}/attachments"
        response = requests.get(url, headers={'Authorization': f'Bearer {access_token}'})
        return response.json().get('value', []) if response.status_code == 200 else []
    except Exception as e:
        print(f"Graph attachments error: {e}")
        return []

def helper_graph_mark_read(access_token, user_email, message_id):
    """Mark message as read"""
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{message_id}"
        requests.patch(url, headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}, json={'isRead': True})
    except Exception as e:
        print(f"Graph mark-read error: {e}")

def helper_graph_send(access_token, user_email, to_email, subject, body_html, reply_to_id=None, attachments_data=None, internet_message_id=None):
    """Send email via Graph API.

    Note: internet_message_id is accepted for backward compatibility but
    Graph API rejects standard In-Reply-To/References headers (must start with x-).
    For proper threading, use helper_graph_reply() with the Graph message ID instead.
    """
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/sendMail"
        message = {
            'subject': f"Re: {subject}" if reply_to_id else subject,
            'body': {'contentType': 'HTML', 'content': body_html},
            'toRecipients': [{'emailAddress': {'address': to_email}}]
        }
        if attachments_data:
            message['attachments'] = [
                {
                    '@odata.type': '#microsoft.graph.fileAttachment',
                    'name': a.get('name', 'file'),
                    'contentType': a.get('contentType', 'application/octet-stream'),
                    'contentBytes': a.get('contentBytes')
                } for a in attachments_data if a.get('contentBytes')
            ]
        response = requests.post(url, headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}, json={'message': message, 'saveToSentItems': True})
        return response.status_code == 202
    except Exception as e:
        print(f"Send error: {e}")
        return False


def helper_graph_reply(access_token, user_email, message_id, body_html, to_email=None, cc_emails=None, subject=None):
    """Reply to an existing email via Graph API (threads correctly in Outlook).

    Args:
        subject: Optional override for reply subject line. If provided,
                 replaces the default "Re: ..." subject inherited from the thread.
    """
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{message_id}/reply"
        payload = {
            'message': {
                'body': {'contentType': 'HTML', 'content': body_html}
            }
        }
        if subject:
            payload['message']['subject'] = subject
        if to_email:
            payload['message']['toRecipients'] = [{'emailAddress': {'address': to_email}}]
        if cc_emails:
            payload['message']['ccRecipients'] = [
                {'emailAddress': {'address': e}} for e in cc_emails if e
            ]
        response = requests.post(
            url,
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
            json=payload
        )
        return response.status_code == 202
    except Exception as e:
        print(f"Reply error: {e}")
        return False


# ============================================================
# EMAIL QUALITY GUARDS
# ============================================================

_RE_FWD_PATTERN = re.compile(r'^(?:\s*(?:Re|RE|re|Fwd|FWD|FW|Fw|fw)\s*:\s*)+')


def clean_email_subject(subject):
    """Strip accumulated Re:/RE:/Fwd:/FW: prefix chains from a subject line."""
    if not subject:
        return ""
    cleaned = _RE_FWD_PATTERN.sub('', subject).strip()
    return cleaned if cleaned else subject


def validate_email_before_send(subject, body_html):
    """Check email has meaningful subject and body content.

    Returns (is_valid, reason) tuple.
    Rejects: empty subject, garbage subject, empty body, body with only template dashes.
    """
    # Check subject
    if not subject or not subject.strip():
        return False, "empty_subject"
    # Strip Re:/Fwd: directly (clean_email_subject returns original if all-prefix)
    stripped_subj = _RE_FWD_PATTERN.sub('', subject).strip()
    if not stripped_subj or len(stripped_subj) < 3:
        return False, "garbage_subject"
    # Check body
    if not body_html or not body_html.strip():
        return False, "empty_body"
    # Strip HTML tags and entities, check remaining text
    text_only = re.sub(r'<[^>]+>', '', body_html)
    text_only = re.sub(r'&[a-zA-Z]+;|&#\d+;', ' ', text_only)
    text_only = text_only.strip()
    if len(text_only) < 20:
        return False, "body_too_short"
    # Reject templates that are all dashes / em-dashes / whitespace
    meaningful = re.sub(r'[\s\-\u2014\u2013]+', '', text_only)
    if len(meaningful) < 10:
        return False, "body_only_dashes"
    return True, "ok"


# ============================================================
# HEBREW NAMES
# ============================================================

HEBREW_NAMES = {
    'doron': 'דורון', 'amit': 'עמית', 'yossi': 'יוסי', 'moshe': 'משה', 
    'david': 'דוד', 'avi': 'אבי', 'eli': 'אלי', 'dan': 'דן', 
    'oren': 'אורן', 'guy': 'גיא', 'tal': 'טל', 'nir': 'ניר', 
    'roy': 'רועי', 'gal': 'גל', 'yuval': 'יובל', 'itay': 'איתי', 
    'idan': 'עידן', 'eyal': 'אייל', 'ran': 'רן', 'uri': 'אורי', 
    'yair': 'יאיר', 'alon': 'אלון', 'chen': 'חן', 'lior': 'ליאור', 
    'omer': 'עומר', 'noam': 'נועם', 'ron': 'רון', 'yoni': 'יוני',
    'asaf': 'אסף', 'matan': 'מתן', 'nadav': 'נדב', 'raz': 'רז'
}

def to_hebrew_name(name):
    """Convert English name to Hebrew if possible"""
    if not name:
        return "שלום"
    if any('\u0590' <= c <= '\u05FF' for c in name):
        return name
    return HEBREW_NAMES.get(name.lower().strip(), name)

# ============================================================
# EMAIL BUILDERS
# ============================================================

def build_rcb_reply(sender_name, attachments, subject="", is_first_email=False, include_joke=False):
    """Build acknowledgment reply (Email 1)"""
    name = sender_name.split('<')[0].strip()
    name = to_hebrew_name(name.split()[0]) if name and '@' not in name else "שלום"
    
    hour = datetime.now().hour
    greeting = "בוקר טוב" if 5 <= hour < 12 else "צהריים טובים" if 12 <= hour < 17 else "ערב טוב" if 17 <= hour < 21 else "לילה טוב"
    
    html = f'<div dir="rtl" style="font-family:Arial;font-size:12pt;line-height:1.6">'
    html += f'<p><strong>{greeting} {name},</strong></p>'
    html += '<p>תודה על פנייתך! קיבלתי את המסמכים שלך ואני מתחילה לעבור עליהם.</p>'
    
    if subject:
        html += f'<p>📋 <strong>נושא:</strong> {subject}</p>'
    
    if attachments:
        html += f'<p>🔍 <strong>זיהיתי {len(attachments)} קבצים:</strong></p><ul>'
        for a in attachments:
            ext = a.get('type', '')
            icon = "📑" if ext == '.pdf' else "📊" if ext in ['.xlsx', '.xls'] else "🖼️" if ext in ['.jpg', '.png'] else "📄"
            html += f"<li>{icon} {a.get('filename', 'קובץ')}</li>"
        html += "</ul>"
    
    html += '<p>⏳ אעבור על המסמכים ואשלח לך דו"ח סיווג מכס מפורט תוך מספר דקות.</p>'
    
    # Signature
    html += '''<hr style="margin:25px 0">
    <table dir="rtl"><tr>
        <td style="padding-left:15px"><img src="https://rpa-port.com/wp-content/uploads/2016/09/logo.png" style="width:80px"></td>
        <td style="border-right:3px solid #1e3a5f;padding-right:15px">
            <strong style="color:#1e3a5f">🤖 RCB - AI Customs Broker</strong><br>
            <strong>R.P.A. PORT LTD</strong><br>
            <span style="font-size:10pt">📧 rcb@rpa-port.co.il</span>
        </td>
    </tr></table>
    </div>'''
    
    return html

def get_anthropic_key(get_secret_func):
    """Get Anthropic API key"""
    try:
        return get_secret_func('ANTHROPIC_API_KEY')
    except Exception as e:
        print(f"Anthropic key error: {e}")
        return None
