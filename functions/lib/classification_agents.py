"""
RCB Multi-Agent Classification System
Queries Firestore for Israeli tariff data, ministry requirements, and rules
Outputs: HTML email + Excel
"""
import json
import requests
import base64
import io
from datetime import datetime
from lib.librarian import search_all_knowledge, search_extended_knowledge, full_knowledge_search, build_classification_context, get_israeli_hs_format

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

def run_hs_agent(api_key, items, tariff_data, rules):
    """Agent 2: HS Classification - Israeli format"""
    system = """אתה מומחה סיווג מכס ישראלי.

פורמט HS ישראלי: XX.XX.XXXXXX/X (לדוגמה: 87.03.808000/5)

כללי סיווג:
- פקודת תעריף המכס 1937
- כללי פרשנות כלליים (GIR)
- סיווג לפי מהות, לא שימוש

החזר JSON:
{"classifications":[{"item":"תיאור","hs_code":"XX.XX.XXXXXX/X","tariff_desc":"","duty_rate":"X%","reasoning":"","confidence":"גבוהה/בינונית/נמוכה"}]}"""
    
    context = f"פריטים:\n{json.dumps(items, ensure_ascii=False)}\n\nתעריף:\n{json.dumps(tariff_data[:10], ensure_ascii=False)}\n\nכללים:\n{json.dumps(rules[:5], ensure_ascii=False)}"
    result = call_claude(api_key, system, context, 3000)
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1: return json.loads(result[start:end])
    except: pass
    return {"classifications": []}

def run_regulatory_agent(api_key, classifications, ministry_data):
    """Agent 3: Israeli regulatory requirements"""
    system = """אתה מומחה רגולציה ישראלית.

משרדים:
- MOT (תחבורה) - רכב, תקנה 271א
- MOH (בריאות) - מזון, תרופות
- MOA (חקלאות) - צמחים, בע״ח
- SII (מכון התקנים) - ת״י
- MOE (כלכלה) - צו יבוא חופשי

{"requirements":[{"hs_code":"","ministries":[{"name":"MOT/MOH/MOA/SII","required":true,"regulation":"תקנה X"}],"free_import":true,"standards":["ת״י X"]}]}"""
    
    result = call_claude(api_key, system, f"סיווגים:\n{json.dumps(classifications, ensure_ascii=False)}\n\nמשרדים:\n{json.dumps(ministry_data[:10], ensure_ascii=False)}")
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1: return json.loads(result[start:end])
    except: pass
    return {"requirements": []}

def run_fta_agent(api_key, items, origins):
    """Agent 4: Free Trade Agreements"""
    system = """אתה מומחה הסכמי סחר ישראל.

הסכמים: EU (EUR1), USA, EFTA, טורקיה, קנדה, ירדן, מצרים

{"fta":[{"country":"","agreement":"","normal_duty":"X%","preferential":"Y%","document":"EUR1/Form A","eligible":true}]}"""
    
    result = call_claude(api_key, system, f"פריטים:\n{json.dumps(items, ensure_ascii=False)}\n\nמקור: {origins}")
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1: return json.loads(result[start:end])
    except: pass
    return {"fta": []}

def run_risk_agent(api_key, data):
    """Agent 5: Risk assessment"""
    system = """אתה מומחה סיכוני סיווג.
{"risk":{"level":"גבוה/בינוני/נמוך","items":[{"item":"","issue":"","mitigation":""}],"pre_ruling":true}}"""
    
    result = call_claude(api_key, system, json.dumps(data, ensure_ascii=False))
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1: return json.loads(result[start:end])
    except: pass
    return {"risk": {"level": "בינוני"}}

def run_synthesis_agent(api_key, all_results):
    """Agent 6: Final summary"""
    system = """סכם בעברית: 1)סיכום מנהלים 2)המלצות סיווג 3)רגולציה 4)FTA 5)סיכונים 6)צעדים הבאים"""
    return call_claude(api_key, system, json.dumps(all_results, ensure_ascii=False), 2000) or "לא זמין"

def run_full_classification(api_key, doc_text, db=None):
    """Main classification pipeline"""
    results = {"timestamp": datetime.now().isoformat(), "agents": {}, "success": False}
    
    try:
        print("  🔍 Agent 1: Document...")
        doc_data = run_document_agent(api_key, doc_text)
        results["agents"]["document"] = doc_data
        items = doc_data.get("items", [{"description": doc_text[:500]}])
        
        # Use Librarian for comprehensive search
        librarian_results = {}
        knowledge_context = ""
        if db:
            search_terms = [i.get("description", "")[:50] for i in items]
            librarian_results = full_knowledge_search(db, search_terms, doc_text[:500])
            knowledge_context = build_classification_context(librarian_results)
            tariff_data = librarian_results.get("tariff_codes", [])
            ministry_data = librarian_results.get("ministry_requirements", [])
            rules = librarian_results.get("classification_rules", [])
        else:
            tariff_data, ministry_data, rules = [], [], []
        
        print("  📊 Agent 2: Classification...")
        hs_results = run_hs_agent(api_key, items, tariff_data, rules)
        results["agents"]["classification"] = hs_results
        
        print("  ⚖️ Agent 3: Regulatory...")
        reg_results = run_regulatory_agent(api_key, hs_results.get("classifications", []), ministry_data)
        results["agents"]["regulatory"] = reg_results
        
        print("  🌍 Agent 4: FTA...")
        origins = [i.get("origin_country", "") for i in items if i.get("origin_country")]
        fta_results = run_fta_agent(api_key, items, origins or ["Unknown"])
        results["agents"]["fta"] = fta_results
        
        print("  🚨 Agent 5: Risk...")
        risk_results = run_risk_agent(api_key, {"hs": hs_results, "reg": reg_results})
        results["agents"]["risk"] = risk_results
        
        print("  📋 Agent 6: Synthesis...")
        results["synthesis"] = run_synthesis_agent(api_key, results["agents"])
        results["success"] = True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results["error"] = str(e)
    
    return clean_firestore_data(results)

def build_classification_email(results, sender_name):
    """Build HTML report"""
    synthesis = results.get("synthesis", "לא זמין")
    classifications = results.get("agents", {}).get("classification", {}).get("classifications", [])
    regulatory = results.get("agents", {}).get("regulatory", {}).get("requirements", [])
    fta = results.get("agents", {}).get("fta", {}).get("fta", [])
    risk = results.get("agents", {}).get("risk", {}).get("risk", {})
    
    html = f'''<div dir="rtl" style="font-family:Arial;font-size:12pt;line-height:1.8">
    <div style="background:#1e3a5f;color:white;padding:20px;border-radius:10px 10px 0 0">
        <h1 style="margin:0">📋 דו״ח סיווג מכס - RCB</h1>
        <p style="margin:5px 0 0 0">{datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
    </div>
    <div style="border:1px solid #ddd;padding:20px;border-radius:0 0 10px 10px">
    
    <h2 style="color:#1e3a5f">📝 סיכום</h2>
    <div style="background:#f5f5f5;padding:15px;border-radius:8px;border-right:4px solid #1e3a5f;white-space:pre-wrap">{synthesis}</div>
    
    <h2 style="color:#1e3a5f;margin-top:25px">📊 סיווג</h2>
    <table style="width:100%;border-collapse:collapse">
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

def process_and_send_report(access_token, rcb_email, to_email, subject, sender_name, raw_attachments, msg_id, get_secret_func, db, firestore, helper_graph_send, extract_text_func):
    """Main: Extract, classify, send report with Excel + original attachments"""
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
        
        print("  📋 Building reports...")
        html = build_classification_email(results, sender_name)
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
        
        print("  📤 Sending...")
        if helper_graph_send(access_token, rcb_email, to_email, f"📊 דו״ח סיווג: {subject}", html, msg_id, attachments):
            print(f"  ✅ Sent to {to_email}")
            db.collection("rcb_classifications").add({
                "subject": subject, "to": to_email,
                "items": len(results.get("agents", {}).get("classification", {}).get("classifications", [])),
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            return True
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
