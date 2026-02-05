"""
RCB Multi-Agent Classification System
Queries Firestore for Israeli tariff data, ministry requirements, and rules
Outputs: HTML email + Excel

UPDATED: Session 10 - Integrated with Module 4, 5, 6
"""
import json
import requests
import base64
import io
from datetime import datetime
from lib.librarian import search_all_knowledge, search_extended_knowledge, full_knowledge_search, build_classification_context, get_israeli_hs_format

# Session 10: Import new modules
try:
    from lib.invoice_validator import validate_invoice, quick_validate, FIELD_DEFINITIONS
    from lib.clarification_generator import (
        generate_missing_docs_request,
        generate_origin_request,
        DocumentType,
        UrgencyLevel,
    )
    from lib.rcb_orchestrator import process_and_respond
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ New modules not available: {e}")
    MODULES_AVAILABLE = False


def clean_firestore_data(data):
    """Convert Firestore timestamps to strings for JSON serialization"""
    if isinstance(data, dict):
        return {k: clean_firestore_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_firestore_data(i) for i in data]
    elif hasattr(data, 'isoformat'):
        return data.isoformat()
    return data


def call_claude(api_key, system_prompt, user_prompt, max_tokens=2000):
    """Call Claude API"""
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}]
            },
            timeout=120
        )
        if response.status_code == 200:
            return response.json()['content'][0]['text']
        else:
            print(f"Claude API error: {response.status_code}")
            return None
    except Exception as e:
        print(f"Claude call error: {e}")
        return None

def query_tariff(db, search_terms):
    """Query tariff collection for Israeli HS codes"""
    results = []
    try:
        docs = db.collection('tariff').limit(100).stream()
        for doc in docs:
            data = doc.to_dict()
            desc = (data.get('description_he', '') + ' ' + data.get('description_en', '')).lower()
            for term in search_terms:
                if term.lower() in desc:
                    results.append(data)
                    break
    except Exception as e:
        print(f"Tariff query error: {e}")
    return clean_firestore_data(results[:20])

def query_ministry_index(db):
    """Get ministry requirements"""
    results = []
    try:
        docs = db.collection('ministry_index').stream()
        for doc in docs:
            results.append(doc.to_dict())
    except Exception as e:
        print(f"Ministry query error: {e}")
    return clean_firestore_data(results)

def query_classification_rules(db):
    """Get classification rules"""
    rules = []
    try:
        docs = db.collection('classification_rules').stream()
        for doc in docs:
            rules.append(doc.to_dict())
    except Exception as e:
        print(f"Rules query error: {e}")
    return rules

def run_document_agent(api_key, doc_text):
    """Agent 1: Extract invoice data"""
    system = """אתה סוכן חילוץ מידע. חלץ מהמסמך JSON:
{"seller":"","buyer":"","items":[{"description":"","quantity":"","unit_price":"","total":"","origin_country":""}],"invoice_number":"","invoice_date":"","total_value":"","currency":"","incoterms":""}
JSON בלבד."""
    result = call_claude(api_key, system, doc_text[:6000])
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1: return json.loads(result[start:end])
    except: pass
    return {"items": [{"description": doc_text[:500]}]}


def run_classification_agent(api_key, items, tariff_data, rules, knowledge_context=""):
    """Agent 2: Classify items using Israeli HS codes"""
    system = f"""אתה סוכן סיווג מכס ישראלי מומחה.

{knowledge_context}

כללים:
{json.dumps(rules[:10], ensure_ascii=False)}

תעריפון (דוגמאות):
{json.dumps(tariff_data[:15], ensure_ascii=False)}

סווג כל פריט עם קוד HS ישראלי (8-10 ספרות).
פלט JSON:
{{"classifications":[{{"item":"","hs_code":"","duty_rate":"","confidence":"גבוהה/בינונית/נמוכה","reasoning":""}}]}}"""
    
    result = call_claude(api_key, system, f"פריטים לסיווג:\n{json.dumps(items, ensure_ascii=False)}", 3000)
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1: return json.loads(result[start:end])
    except: pass
    return {"classifications": []}


def run_regulatory_agent(api_key, classifications, ministry_data):
    """Agent 3: Check regulatory requirements"""
    system = f"""אתה סוכן רגולציה. בדוק אילו אישורים נדרשים לפי הסיווגים.

משרדים ודרישות:
{json.dumps(ministry_data[:20], ensure_ascii=False)}

פלט JSON:
{{"regulatory":[{{"hs_code":"","ministries":[{{"name":"","required":true/false,"regulation":""}}]}}]}}"""
    
    result = call_claude(api_key, system, f"סיווגים:\n{json.dumps(classifications, ensure_ascii=False)}")
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1: return json.loads(result[start:end])
    except: pass
    return {"regulatory": []}


def run_fta_agent(api_key, classifications, origin_country):
    """Agent 4: Check FTA eligibility"""
    system = """אתה סוכן הסכמי סחר. בדוק זכאות להעדפות מכס.

הסכמים פעילים: EU, USA, UK, EFTA, Turkey, Jordan, Egypt, Mercosur, Mexico, Canada

פלט JSON:
{"fta":[{"hs_code":"","country":"","agreement":"","eligible":true/false,"preferential":"","documents_needed":""}]}"""
    
    result = call_claude(api_key, system, f"סיווגים: {json.dumps(classifications, ensure_ascii=False)}\nארץ מקור: {origin_country}")
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1: return json.loads(result[start:end])
    except: pass
    return {"fta": []}


def run_risk_agent(api_key, invoice_data, classifications):
    """Agent 5: Risk assessment"""
    system = """אתה סוכן הערכת סיכונים. בדוק:
1. ערך נמוך חשוד
2. סיווג שגוי אפשרי
3. מקור בעייתי
4. חוסר התאמה

פלט JSON:
{"risk":{"level":"נמוך/בינוני/גבוה","items":[{"item":"","issue":"","recommendation":""}]}}"""
    
    result = call_claude(api_key, system, f"חשבונית: {json.dumps(invoice_data, ensure_ascii=False)}\nסיווגים: {json.dumps(classifications, ensure_ascii=False)}")
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1: return json.loads(result[start:end])
    except: pass
    return {"risk": {"level": "נמוך", "items": []}}


def run_synthesis_agent(api_key, all_results):
    """Agent 6: Final synthesis"""
    system = """אתה סוכן סיכום. כתוב סיכום קצר בעברית (3-4 משפטים) של:
1. מה נמצא
2. המלצות עיקריות
3. אזהרות אם יש

טקסט בלבד, לא JSON."""
    
    return call_claude(api_key, system, json.dumps(all_results, ensure_ascii=False)[:4000]) or "לא ניתן לייצר סיכום."


def run_full_classification(api_key, doc_text, db):
    """Run complete multi-agent classification"""
    try:
        # Agent 1: Extract
        print("    🔍 Agent 1: Extracting...")
        invoice = run_document_agent(api_key, doc_text)
        items = invoice.get("items", [{"description": doc_text[:500]}])
        origin = items[0].get("origin_country", "") if items else ""
        
        # Get context
        search_terms = [i.get("description", "")[:50] for i in items[:5]]
        tariff = query_tariff(db, search_terms)
        ministry = query_ministry_index(db)
        rules = query_classification_rules(db)
        
        # Enhanced knowledge search
        knowledge_context = ""
        for item in items[:3]:
            desc = item.get("description", "")
            if desc:
                knowledge = full_knowledge_search(db, desc)
                knowledge_context += build_classification_context(knowledge) + "\n"
        
        # Agent 2: Classify
        print("    🏷️ Agent 2: Classifying...")
        classification = run_classification_agent(api_key, items, tariff, rules, knowledge_context)
        
        # Agent 3: Regulatory
        print("    ⚖️ Agent 3: Regulatory...")
        regulatory = run_regulatory_agent(api_key, classification.get("classifications", []), ministry)
        
        # Agent 4: FTA
        print("    🌍 Agent 4: FTA...")
        fta = run_fta_agent(api_key, classification.get("classifications", []), origin)
        
        # Agent 5: Risk
        print("    🚨 Agent 5: Risk...")
        risk = run_risk_agent(api_key, invoice, classification.get("classifications", []))
        
        # Agent 6: Synthesis
        print("    📝 Agent 6: Synthesis...")
        all_results = {"invoice": invoice, "classification": classification, "regulatory": regulatory, "fta": fta, "risk": risk}
        synthesis = run_synthesis_agent(api_key, all_results)
        
        return {
            "success": True,
            "agents": all_results,
            "synthesis": synthesis,
            "invoice_data": invoice  # Session 10: Pass invoice data for validation
        }
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return {"success": False, "error": str(e)}


def build_classification_email(results, sender_name, invoice_validation=None):
    """Build HTML email report - Updated with invoice validation"""
    classifications = results.get("agents", {}).get("classification", {}).get("classifications", [])
    regulatory = results.get("agents", {}).get("regulatory", {}).get("regulatory", [])
    fta = results.get("agents", {}).get("fta", {}).get("fta", [])
    risk = results.get("agents", {}).get("risk", {}).get("risk", {})
    synthesis = results.get("synthesis", "")
    
    html = f'''<div style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;direction:rtl">
    <div style="background:linear-gradient(135deg,#1e3a5f,#2d5a87);color:white;padding:20px;border-radius:10px 10px 0 0">
        <h1 style="margin:0">📊 דו״ח סיווג מכס</h1>
        <p style="margin:5px 0 0 0;opacity:0.9">נוצר אוטומטית ע״י RCB</p>
    </div>
    <div style="background:#f8f9fa;padding:20px;border:1px solid #ddd">'''
    
    # Session 10: Add invoice validation section
    if invoice_validation:
        score = invoice_validation.get('score', 0)
        is_valid = invoice_validation.get('is_valid', False)
        missing = invoice_validation.get('missing_fields', [])
        
        if is_valid:
            html += f'''<div style="background:#d4edda;border:1px solid #28a745;border-radius:5px;padding:15px;margin-bottom:20px">
                <h3 style="color:#155724;margin:0">✅ חשבון תקין (ציון: {score}/100)</h3>
                <p style="color:#155724;margin:5px 0 0 0">המסמכים מכילים את כל המידע הנדרש לפי תקנות המכס.</p>
            </div>'''
        else:
            html += f'''<div style="background:#fff3cd;border:1px solid #ffc107;border-radius:5px;padding:15px;margin-bottom:20px">
                <h3 style="color:#856404;margin:0">⚠️ חשבון חלקי (ציון: {score}/100)</h3>
                <p style="color:#856404;margin:5px 0 0 0">חסרים {len(missing)} שדות בהתאם לתקנות (מס' 2) תשל"ג-1972:</p>
                <ul style="color:#856404;margin:10px 0 0 0">'''
            for field in missing[:5]:
                html += f'<li>{field}</li>'
            html += '</ul></div>'
    
    html += f'<p style="background:white;padding:15px;border-radius:5px;border-right:4px solid #1e3a5f">{synthesis}</p>'
    
    html += '''<h2 style="color:#1e3a5f;margin-top:25px">🏷️ סיווגים</h2>
    <table style="width:100%;border-collapse:collapse;background:white">
    <tr style="background:#1e3a5f;color:white">
        <th style="padding:10px;border:1px solid #ddd">פריט</th>
        <th style="padding:10px;border:1px solid #ddd">קוד HS</th>
        <th style="padding:10px;border:1px solid #ddd">מכס</th>
        <th style="padding:10px;border:1px solid #ddd">ודאות</th>
    </tr>'''
    
    for c in classifications:
        conf = c.get("confidence", "בינונית")
        color = "#28a745" if conf == "גבוהה" else "#ffc107" if conf == "בינונית" else "#dc3545"
        html += f'''<tr>
            <td style="padding:10px;border:1px solid #ddd">{c.get("item", "")[:40]}</td>
            <td style="padding:10px;border:1px solid #ddd;font-family:monospace;font-weight:bold">{c.get("hs_code", "")}</td>
            <td style="padding:10px;border:1px solid #ddd">{c.get("duty_rate", "")}</td>
            <td style="padding:10px;border:1px solid #ddd;color:{color}">{conf}</td>
        </tr>'''
    html += '</table>'
    
    if regulatory:
        html += '<h2 style="color:#1e3a5f;margin-top:25px">⚖️ רגולציה</h2>'
        for r in regulatory:
            html += f'<p><strong>{r.get("hs_code", "")}</strong>: '
            for m in r.get("ministries", []):
                if m.get("required"):
                    html += f'{m.get("name")} ({m.get("regulation", "")}) | '
            html += '</p>'
    
    if [f for f in fta if f.get("eligible")]:
        html += '<h2 style="color:#28a745;margin-top:25px">🌍 הטבות FTA</h2>'
        for f in fta:
            if f.get("eligible"):
                html += f'<p>✓ {f.get("country", "")}: {f.get("agreement", "")} - מכס {f.get("preferential", "")}</p>'
    
    if risk.get("level") in ["גבוה", "בינוני"]:
        html += f'<h2 style="color:#dc3545;margin-top:25px">🚨 סיכון: {risk.get("level", "")}</h2>'
        for i in risk.get("items", []):
            html += f'<p>⚠️ {i.get("item", "")}: {i.get("issue", "")}</p>'
    
    html += '''<hr style="margin:25px 0">
    <table><tr>
        <td><img src="https://rpa-port.com/wp-content/uploads/2020/01/logo.png" style="width:70px"></td>
        <td style="border-right:3px solid #1e3a5f;padding-right:15px">
            <strong style="color:#1e3a5f">🤖 RCB - AI Customs Broker</strong><br>
            R.P.A. PORT LTD | rcb@rpa-port.co.il
        </td>
    </tr></table>
    <p style="font-size:9pt;color:#999;margin-top:15px">⚠️ המלצה ראשונית בלבד. יש לאמת עם עמיל מכס מוסמך.</p>
    </div></div>'''
    return html

def build_excel_report(results):
    """Build Excel report"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        
        wb = Workbook()
        ws = wb.active
        ws.title = "סיכום"
        ws['A1'] = "דו״ח סיווג RCB"
        ws['A1'].font = Font(size=16, bold=True)
        ws['A3'] = results.get("synthesis", "")
        
        ws2 = wb.create_sheet("סיווגים")
        headers = ["פריט", "קוד HS", "מכס", "ודאות", "נימוק"]
        for i, h in enumerate(headers, 1):
            ws2.cell(1, i, h).font = Font(bold=True)
        for row, c in enumerate(results.get("agents", {}).get("classification", {}).get("classifications", []), 2):
            ws2.cell(row, 1, c.get("item", ""))
            ws2.cell(row, 2, c.get("hs_code", ""))
            ws2.cell(row, 3, c.get("duty_rate", ""))
            ws2.cell(row, 4, c.get("confidence", ""))
            ws2.cell(row, 5, c.get("reasoning", ""))
        
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return base64.b64encode(output.read()).decode('utf-8')
    except Exception as e:
        print(f"Excel error: {e}")
        return None


def _parse_invoice_fields_from_data(invoice_data):
    """Session 10: Parse invoice data into validation format"""
    fields = {}
    
    if invoice_data.get('seller'):
        fields['seller'] = invoice_data['seller']
    if invoice_data.get('buyer'):
        fields['buyer'] = invoice_data['buyer']
    if invoice_data.get('invoice_date'):
        fields['date'] = invoice_data['invoice_date']
    if invoice_data.get('total_value'):
        fields['price'] = invoice_data['total_value']
    if invoice_data.get('incoterms'):
        fields['terms'] = invoice_data['incoterms']
    if invoice_data.get('currency'):
        fields['currency'] = invoice_data['currency']
    
    # Check items for origin and description
    items = invoice_data.get('items', [])
    if items:
        origins = [i.get('origin_country') for i in items if i.get('origin_country')]
        if origins:
            fields['origin'] = origins[0]
        
        descriptions = [i.get('description') for i in items if i.get('description')]
        if descriptions:
            fields['description'] = ', '.join(descriptions[:3])
        
        quantities = [i.get('quantity') for i in items if i.get('quantity')]
        if quantities:
            fields['quantity'] = ', '.join(str(q) for q in quantities[:3])
    
    return fields


def process_and_send_report(access_token, rcb_email, to_email, subject, sender_name, raw_attachments, msg_id, get_secret_func, db, firestore, helper_graph_send, extract_text_func):
    """Main: Extract, classify, validate, send report with Excel + original attachments
    
    UPDATED Session 10: Integrates Module 4, 5, 6
    - Validates invoice using Module 5
    - Adds validation results to report
    - Generates clarification requests if needed (Module 4)
    """
    try:
        print(f"  🤖 Starting: {subject[:50]}")
        
        api_key = get_secret_func('ANTHROPIC_API_KEY')
        if not api_key:
            print("  ❌ No API key")
            return False
        
        print("  📄 Extracting text...")
        doc_text = extract_text_func(raw_attachments)
        if not doc_text or len(doc_text) < 50:
            print("  ⚠️ No text")
            return False
        
        print(f"  📝 {len(doc_text)} chars")
        
        results = run_full_classification(api_key, doc_text, db)
        if not results.get('success'):
            print(f"  ❌ Failed")
            return False
        
        # Session 10: Validate invoice using Module 5
        invoice_validation = None
        if MODULES_AVAILABLE:
            print("  📋 Validating invoice (Module 5)...")
            invoice_data = results.get('invoice_data', {})
            validation_fields = _parse_invoice_fields_from_data(invoice_data)
            
            try:
                validation_result = validate_invoice(validation_fields)
                invoice_validation = {
                    'score': validation_result.score,
                    'is_valid': validation_result.is_valid,
                    'missing_fields': [FIELD_DEFINITIONS[f]['name_he'] for f in validation_result.missing_fields],
                    'fields_present': validation_result.fields_present,
                    'fields_required': validation_result.fields_required,
                }
                print(f"  📊 Invoice score: {validation_result.score}/100 ({'✅' if validation_result.is_valid else '⚠️'})")
            except Exception as ve:
                print(f"  ⚠️ Validation error: {ve}")
        
        print("  📋 Building reports...")
        html = build_classification_email(results, sender_name, invoice_validation)
        excel = build_excel_report(results)
        
        attachments = []
        if excel:
            attachments.append({
                '@odata.type': '#microsoft.graph.fileAttachment',
                'name': f'RCB_Report_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx',
                'contentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'contentBytes': excel
            })
        
        for att in raw_attachments:
            if att.get('contentBytes'):
                attachments.append({
                    '@odata.type': '#microsoft.graph.fileAttachment',
                    'name': att.get('name', 'file'),
                    'contentType': att.get('contentType', 'application/octet-stream'),
                    'contentBytes': att.get('contentBytes')
                })
        
        # Session 10: Add invoice score to subject
        subject_line = f"📊 דו״ח סיווג: {subject}"
        if invoice_validation:
            score = invoice_validation['score']
            if score >= 70:
                subject_line = f"✅ דו״ח סיווג ({score}/100): {subject}"
            else:
                subject_line = f"⚠️ דו״ח סיווג ({score}/100): {subject}"
        
        print("  📤 Sending...")
        if helper_graph_send(access_token, rcb_email, to_email, subject_line, html, msg_id, attachments):
            print(f"  ✅ Sent to {to_email}")
            
            # Save to Firestore with validation data
            save_data = {
                "subject": subject,
                "to": to_email,
                "items": len(results.get("agents", {}).get("classification", {}).get("classifications", [])),
                "timestamp": firestore.SERVER_TIMESTAMP
            }
            
            if invoice_validation:
                save_data["invoice_score"] = invoice_validation['score']
                save_data["invoice_valid"] = invoice_validation['is_valid']
                save_data["missing_fields"] = invoice_validation['missing_fields']
            
            db.collection("rcb_classifications").add(save_data)
            return True
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
