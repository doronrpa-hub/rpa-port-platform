"""RCB Helper functions - Graph API, PDF extraction, Hebrew names"""
import requests
import base64
import io
from datetime import datetime

# ============================================================
# PDF TEXT EXTRACTION (with OCR fallback)
# ============================================================

def extract_text_from_pdf_bytes(pdf_bytes):
    """Extract text from PDF bytes - tries multiple methods"""
    
    # Method 1: pdfplumber (fast, for text-based PDFs)
    text = _extract_with_pdfplumber(pdf_bytes)
    if len(text.strip()) > 50:
        print(f"    ✅ pdfplumber extracted {len(text)} chars")
        return text
    
    # Method 2: pypdf (sometimes works better)
    text = _extract_with_pypdf(pdf_bytes)
    if len(text.strip()) > 50:
        print(f"    ✅ pypdf extracted {len(text)} chars")
        return text
    
    # Method 3: Google Cloud Vision OCR (for scanned PDFs)
    print(f"    🔍 Text extraction failed, trying OCR...")
    text = _extract_with_vision_ocr(pdf_bytes)
    if text:
        print(f"    ✅ OCR extracted {len(text)} chars")
        return text
    
    print(f"    ⚠️ All extraction methods failed")
    return ""


def _extract_with_pdfplumber(pdf_bytes):
    """Extract text using pdfplumber"""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                # Also try to extract tables
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            text_parts.append(" | ".join([str(cell) if cell else "" for cell in row]))
        return "\n".join(text_parts)
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
        return "\n".join(text_parts)
    except Exception as e:
        print(f"    pypdf error: {e}")
        return ""


def _extract_with_vision_ocr(pdf_bytes):
    """Extract text using Google Cloud Vision OCR"""
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
            image = vision.Image(content=img_bytes)
            response = client.text_detection(image=image)
            
            if response.text_annotations:
                page_text = response.text_annotations[0].description
                all_text.append(f"--- Page {i+1} ---\n{page_text}")
                print(f"    📄 Page {i+1}: {len(page_text)} chars")
            
            if response.error.message:
                print(f"    Vision API error: {response.error.message}")
        
        return "\n\n".join(all_text)
    except ImportError:
        print(f"    ⚠️ google-cloud-vision not installed")
        return ""
    except Exception as e:
        print(f"    Vision OCR error: {e}")
        return ""


def _pdf_to_images(pdf_bytes):
    """Convert PDF pages to images for OCR"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []
        
        for page_num in range(min(len(doc), 10)):  # Max 10 pages
            page = doc[page_num]
            # Render at 150 DPI for good OCR quality
            pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
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
        images = convert_from_bytes(pdf_bytes, dpi=150, first_page=1, last_page=10)
        result = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            result.append(buf.getvalue())
        return result
    except Exception as e:
        print(f"    pdf2image error: {e}")
        return []


def extract_text_from_attachments(attachments_data):
    """Extract text from all PDF attachments"""
    all_text = []
    for att in attachments_data:
        name = att.get('name', 'file')
        content_bytes = att.get('contentBytes', '')
        
        if not content_bytes:
            continue
            
        # Decode base64
        try:
            file_bytes = base64.b64decode(content_bytes)
        except:
            continue
        
        # Check if PDF
        if name.lower().endswith('.pdf'):
            print(f"    📄 Extracting text from: {name}")
            text = extract_text_from_pdf_bytes(file_bytes)
            if text:
                all_text.append(f"=== {name} ===\n{text}")
            else:
                all_text.append(f"=== {name} ===\n[No text could be extracted]")
        
        # Handle images directly with OCR
        elif name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
            print(f"    🖼️ OCR on image: {name}")
            text = _ocr_image(file_bytes)
            if text:
                all_text.append(f"=== {name} ===\n{text}")
    
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
    except:
        return []

def helper_graph_attachments(access_token, user_email, message_id):
    """Get message attachments"""
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{message_id}/attachments"
        response = requests.get(url, headers={'Authorization': f'Bearer {access_token}'})
        return response.json().get('value', []) if response.status_code == 200 else []
    except:
        return []

def helper_graph_mark_read(access_token, user_email, message_id):
    """Mark message as read"""
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{message_id}"
        requests.patch(url, headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}, json={'isRead': True})
    except:
        pass

def helper_graph_send(access_token, user_email, to_email, subject, body_html, reply_to_id=None, attachments_data=None):
    """Send email via Graph API"""
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
        <td style="padding-left:15px"><img src="https://rpa-port.com/wp-content/uploads/2020/01/logo.png" style="width:80px"></td>
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
    except:
        return None
