"""
RCB PDF Creator - Classification Report Generator
Proper Hebrew RTL with mixed English/numbers support
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import os


def is_hebrew_char(c):
    return '\u0590' <= c <= '\u05FF'


def heb(text):
    """Handle Hebrew text for RTL display - reverse Hebrew, keep English/numbers"""
    if not text:
        return text
    text = str(text)
    
    # No Hebrew? Return as-is
    if not any(is_hebrew_char(c) for c in text):
        return text
    
    # Pure Hebrew? Simple reverse
    if all(is_hebrew_char(c) or c in ' .,;:!?()-"' for c in text):
        return text[::-1]
    
    # Mixed: split into segments, reverse Hebrew parts, reverse segment order
    segments = []
    current = []
    in_hebrew = None
    
    for char in text:
        char_is_heb = is_hebrew_char(char)
        
        if in_hebrew is None:
            in_hebrew = char_is_heb
        
        if char in ' .,;:!?()-/':
            current.append(char)
        elif char_is_heb == in_hebrew:
            current.append(char)
        else:
            if current:
                seg = ''.join(current)
                segments.append(seg[::-1] if in_hebrew else seg)
            current = [char]
            in_hebrew = char_is_heb
    
    if current:
        seg = ''.join(current)
        segments.append(seg[::-1] if in_hebrew else seg)
    
    return ''.join(reversed(segments))


def setup_fonts():
    fonts = [
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'DejaVu'),
        ('/usr/share/fonts/truetype/freefont/FreeSans.ttf', 'FreeSans'),
    ]
    for path, name in fonts:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                print(f"Registered font: {name}")
                return name
            except Exception as e:
                print(f"pdf_creator: Font registration failed for {name}: {e}")
    return 'Helvetica'


RPA_BLUE = colors.HexColor('#1e3a5f')
RPA_LIGHT = colors.HexColor('#4a90c2')
GRAY = colors.HexColor('#cccccc')
BG = colors.HexColor('#f5f5f5')


def get_styles(font):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('DocTitle', fontName=font, fontSize=20, alignment=TA_CENTER, textColor=RPA_BLUE, spaceAfter=5))
    styles.add(ParagraphStyle('DocSub', fontName=font, fontSize=14, alignment=TA_CENTER, textColor=colors.gray, spaceAfter=15))
    styles.add(ParagraphStyle('HeadR', fontName=font, fontSize=13, alignment=TA_RIGHT, textColor=RPA_BLUE, spaceBefore=12, spaceAfter=8))
    styles.add(ParagraphStyle('NormR', fontName=font, fontSize=10, alignment=TA_RIGHT, spaceAfter=4))
    styles.add(ParagraphStyle('NormC', fontName=font, fontSize=10, alignment=TA_CENTER, spaceAfter=4))
    styles.add(ParagraphStyle('Small', fontName=font, fontSize=8, alignment=TA_CENTER, textColor=colors.gray))
    return styles


def create_classification_pdf(data, output_path=None, language="he"):
    font = setup_fonts()
    styles = get_styles(font)
    
    if not output_path:
        output_path = f'/tmp/classification_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    
    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    # Header
    story.append(Paragraph('RCB - AI Customs Broker', styles['DocTitle']))
    story.append(Paragraph(heb('דו"ח סיווג מכס'), styles['DocSub']))
    story.append(HRFlowable(width="100%", thickness=2, color=RPA_BLUE))
    story.append(Spacer(1, 12))
    
    # Meta
    sender = data.get('sender_name', '-')
    subject = data.get('email_subject', '-')
    date = data.get('classification_date', datetime.now().strftime('%d/%m/%Y %H:%M'))
    
    meta = [[date, heb('תאריך:')], [sender, heb('שולח:')], [subject, heb('נושא:')]]
    t = Table(meta, colWidths=[350, 80])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), font), ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (0,0), (0,-1), 'LEFT'), ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('TEXTCOLOR', (1,0), (1,-1), RPA_BLUE), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))
    
    # Items
    for i, item in enumerate(data.get('items', []), 1):
        desc = item.get('description', f'Item {i}')
        story.append(Paragraph(f"{heb('פריט')} {i}: {heb(desc)}", styles['HeadR']))
        
        hs = item.get('hs_code', '-')
        hs_he = item.get('hs_description_he', '')
        hs_en = item.get('hs_description_en', '')
        
        info = [[hs, heb('קוד מכס HS')], [heb(hs_he), heb('תיאור עברית')], [hs_en, heb('תיאור אנגלית')]]
        t = Table(info, colWidths=[330, 120])
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), font), ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BACKGROUND', (1,0), (1,-1), BG), ('ALIGN', (0,0), (0,-1), 'LEFT'),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, GRAY),
            ('PADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))
        
        # Duty
        duty = item.get('duty_rate', '-')
        vat = item.get('vat_rate', '') or '\u2014'
        purchase = item.get('purchase_tax', heb('לא חל'))
        
        d = [[heb('מס קנייה'), heb('מע"מ'), heb('מכס')], [heb(str(purchase)), vat, duty]]
        t = Table(d, colWidths=[150, 150, 150])
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), font), ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BACKGROUND', (0,0), (-1,0), RPA_BLUE), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('GRID', (0,0), (-1,-1), 0.5, GRAY),
            ('PADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))
        
        # Ministries
        ministries = item.get('ministry_requirements', [])
        if ministries:
            story.append(Paragraph(heb('דרישות משרדים:'), styles['HeadR']))
            md = [[heb('סטטוס'), heb('דרישה'), heb('משרד')]]
            for m in ministries:
                md.append([heb(m.get('status', 'נדרש')), heb(m.get('requirement', '')), heb(m.get('ministry', ''))])
            t = Table(md, colWidths=[70, 250, 130])
            t.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,-1), font), ('FONTSIZE', (0,0), (-1,-1), 9),
                ('BACKGROUND', (0,0), (-1,0), RPA_LIGHT), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('GRID', (0,0), (-1,-1), 0.5, GRAY),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(t)
        
        notes = item.get('notes', '')
        if notes:
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"{heb('הערות')}: {heb(notes)}", styles['NormR']))
        
        conf = item.get('confidence', '')
        if conf:
            story.append(Paragraph(f"{heb('רמת ביטחון')}: {heb(conf)}", styles['NormR']))
        
        story.append(Spacer(1, 12))
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
        story.append(Spacer(1, 8))
    
    # Footer
    story.append(Spacer(1, 15))
    story.append(Paragraph(heb('הבהרה: דו"ח זה מהווה המלצה בלבד. הסיווג הסופי נתון לאישור רשות המכס.'), styles['Small']))
    story.append(Spacer(1, 8))
    story.append(Paragraph('RCB - AI Customs Broker | R.P.A. PORT LTD | rcb@rpa-port.co.il', styles['Small']))
    
    doc.build(story)
    print(f"PDF created: {output_path}")
    return output_path
