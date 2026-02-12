# Session 15: Multi-model optimization (Claude + Gemini)
"""
RCB Multi-Agent Classification System
Queries Firestore for Israeli tariff data, ministry requirements, and rules
Outputs: HTML email + Excel

UPDATED: Session 10 - Integrated with Module 4, 5, 6
UPDATED: Session 11 - HS code validation against tariff database
UPDATED: Session 11 - Standardized English subject line format
UPDATED: Session 15 - Multi-model optimization:
  - Agent 2 (classification): Claude Sonnet 4.5 (best reasoning)
  - Agent 6 (synthesis): Gemini 2.5 Pro (good Hebrew, lower cost)
  - Agents 1,3,4,5: Gemini 2.5 Flash (simple tasks, ~95% cheaper)
"""
import json
import requests
import base64
import io
import random
import string
from datetime import datetime
from lib.librarian import (
    search_all_knowledge, 
    search_extended_knowledge, 
    full_knowledge_search, 
    build_classification_context, 
    get_israeli_hs_format,
    validate_and_correct_classifications,  # Session 11: HS validation
)

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


# Session 14: Language tools integration
try:
    from lib.language_tools import (
        HebrewLanguageChecker,
        build_rcb_subject as build_rcb_subject_v2,
        process_outgoing_text,
        create_language_toolkit,
    )
    _lang_checker = HebrewLanguageChecker()
    LANGUAGE_TOOLS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Language tools not available: {e}")
    LANGUAGE_TOOLS_AVAILABLE = False

# Session 17 Phase 2: Enrichment agent integration
try:
    from lib.enrichment_agent import create_enrichment_agent
    ENRICHMENT_AVAILABLE = True
except ImportError as e:
    print(f"Enrichment agent not available: {e}")
    ENRICHMENT_AVAILABLE = False

# =============================================================================
# SESSION 11: Tracking Code & Subject Line Builder
# =============================================================================

def generate_tracking_code():
    """Generate unique RCB tracking code: RCB-YYYYMMDD-XXXXX"""
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"RCB-{date_part}-{random_part}"


def build_rcb_subject(invoice_data, status="ACK", invoice_score=None):
    """
    Build standardized RCB email subject line in English.
    
    Format: [TRACKING] Direction | RPA: XXX | Seller: XXX | Buyer: XXX | Freight | BL/AWB | STATUS
    
    Args:
        invoice_data: Dict from Agent 1 extraction
        status: "ACK" (acknowledged), "FINAL" (complete), "CLARIFICATION" (needs info)
        invoice_score: Optional invoice validation score
        
    Returns:
        Formatted subject line string
    """
    # Generate tracking code
    tracking = generate_tracking_code()
    
    # Direction
    direction = invoice_data.get('direction', 'unknown')
    if direction == 'import':
        direction_text = "Import to IL"
    elif direction == 'export':
        direction_text = "Export from IL"
    else:
        direction_text = "Direction TBD"
    
    # RPA file number
    rpa_file = invoice_data.get('rpa_file_number', '')
    rpa_text = f"RPA:{rpa_file}" if rpa_file else "RPA:TBD"
    
    # Seller (truncate to 20 chars)
    seller = invoice_data.get('seller', '')
    if seller:
        # Extract company name (first part before comma or address)
        seller = seller.split(',')[0].strip()[:20]
    seller_text = f"S:{seller}" if seller else "S:Unknown"
    
    # Buyer (truncate to 20 chars)
    buyer = invoice_data.get('buyer', '')
    if buyer:
        buyer = buyer.split(',')[0].strip()[:20]
    buyer_text = f"B:{buyer}" if buyer else "B:Unknown"
    
    # Freight type
    freight_type = invoice_data.get('freight_type', 'unknown')
    if freight_type == 'sea':
        freight_text = "SEA"
    elif freight_type == 'air':
        freight_text = "AIR"
    else:
        freight_text = "FRT:TBD"
    
    # BL or AWB number
    bl_number = invoice_data.get('bl_number', '')
    awb_number = invoice_data.get('awb_number', '')
    if bl_number:
        transport_text = f"BL:{bl_number[:15]}"
    elif awb_number:
        transport_text = f"AWB:{awb_number[:15]}"
    else:
        transport_text = "REF:TBD"
    
    # Status with score if available
    if status == "CLARIFICATION" or (invoice_score is not None and invoice_score < 70):
        status_text = "⚠️CLARIFICATION"
    elif status == "FINAL" or (invoice_score is not None and invoice_score >= 70):
        status_text = "✅FINAL"
    else:
        status_text = "📥ACK"
    
    # Build subject
    subject = f"[{tracking}] {direction_text} | {rpa_text} | {seller_text} | {buyer_text} | {freight_text} | {transport_text} | {status_text}"
    
    return subject, tracking


def extract_tracking_from_subject(subject):
    """Extract RCB tracking code from existing subject if present"""
    import re
    match = re.search(r'\[RCB-\d{8}-[A-Z0-9]{5}\]', subject)
    if match:
        return match.group(0)[1:-1]  # Remove brackets
    return None


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
    """Call Claude API - Sonnet 4.5 (Session 15: upgraded from Sonnet 4)"""
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
            print(f"Claude API error: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"Claude call error: {e}")
        return None


# =============================================================================
# SESSION 15: Gemini API Integration (cost optimization)
# =============================================================================

def call_gemini(gemini_key, system_prompt, user_prompt, max_tokens=2000, model="gemini-2.5-flash"):
    """Call Google Gemini API
    
    Session 15: Added for cost optimization.
    Models:
      - gemini-2.5-flash: Simple tasks (extraction, regulatory, FTA, risk) ~$0.15/$0.60 per MTok
      - gemini-2.5-pro: Medium tasks (synthesis) ~$1.25/$10 per MTok
    
    Falls back to Claude if Gemini fails or key is missing.
    """
    if not gemini_key:
        return None
    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}",
            headers={"content-type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": [{"text": user_prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": 0.3
                }
            },
            timeout=120
        )
        if response.status_code == 200:
            data = response.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text")
        else:
            print(f"Gemini API error ({model}): {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"Gemini call error ({model}): {e}")
        return None


def call_gemini_fast(gemini_key, system_prompt, user_prompt, max_tokens=2000):
    """Gemini 2.5 Flash - for simple structured tasks (Agents 1,3,4,5)"""
    return call_gemini(gemini_key, system_prompt, user_prompt, max_tokens, "gemini-2.5-flash")


def call_gemini_pro(gemini_key, system_prompt, user_prompt, max_tokens=2000):
    """Gemini 2.5 Pro - for medium complexity tasks (Agent 6 synthesis)"""
    return call_gemini(gemini_key, system_prompt, user_prompt, max_tokens, "gemini-2.5-pro")


def call_ai(api_key, gemini_key, system_prompt, user_prompt, max_tokens=2000, tier="fast"):
    """Smart router: picks the right model based on task tier.
    
    Session 15: Central routing function with automatic fallback.
    - tier="smart": Claude Sonnet 4.5 (Agent 2 - classification)
    - tier="pro": Gemini 2.5 Pro (Agent 6 - synthesis)  
    - tier="fast": Gemini 2.5 Flash (Agents 1,3,4,5 - simple tasks)
    
    If Gemini fails or key is missing, falls back to Claude automatically.
    """
    result = None
    
    if tier == "smart":
        # Always use Claude for the hard classification task
        result = call_claude(api_key, system_prompt, user_prompt, max_tokens)
    elif tier == "pro":
        # Try Gemini Pro first, fallback to Claude
        result = call_gemini_pro(gemini_key, system_prompt, user_prompt, max_tokens)
        if not result:
            print("    ↩️ Gemini Pro fallback → Claude")
            result = call_claude(api_key, system_prompt, user_prompt, max_tokens)
    else:  # "fast"
        # Try Gemini Flash first, fallback to Claude
        result = call_gemini_fast(gemini_key, system_prompt, user_prompt, max_tokens)
        if not result:
            print("    ↩️ Gemini Flash fallback → Claude")
            result = call_claude(api_key, system_prompt, user_prompt, max_tokens)
    
    return result

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

def run_document_agent(api_key, doc_text, gemini_key=None):
    """Agent 1: Extract invoice data - Updated Session 11 with shipping details
    Session 15: Uses Gemini Flash (simple extraction task)"""
    system = """אתה סוכן חילוץ מידע. חלץ מהמסמך JSON עם כל השדות הבאים:
{
    "seller": "",
    "buyer": "",
    "items": [{"description":"","quantity":"","unit_price":"","total":"","origin_country":""}],
    "invoice_number": "",
    "invoice_date": "",
    "total_value": "",
    "currency": "",
    "incoterms": "",
    "direction": "import/export/unknown",
    "freight_type": "sea/air/unknown",
    "bl_number": "",
    "awb_number": "",
    "rpa_file_number": "",
    "vessel_name": "",
    "port_of_loading": "",
    "port_of_discharge": ""
}

הנחיות:
- direction: "import" אם הסחורה מגיעה לישראל, "export" אם יוצאת מישראל
- freight_type: "sea" אם יש B/L או אונייה, "air" אם יש AWB או טיסה
- bl_number: מספר שטר מטען ימי (Bill of Lading)
- awb_number: מספר שטר מטען אווירי (Air Waybill)
- rpa_file_number: מספר תיק RPA אם מופיע

JSON בלבד."""
    result = call_ai(api_key, gemini_key, system, doc_text[:6000], tier="fast")
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1: return json.loads(result[start:end])
    except: pass
    return {"items": [{"description": doc_text[:500]}]}


def run_classification_agent(api_key, items, tariff_data, rules, knowledge_context="", gemini_key=None):
    """Agent 2: Classify items using Israeli HS codes
    Session 15: STAYS on Claude Sonnet 4.5 (highest quality for core task)"""
    system = f"""אתה סוכן סיווג מכס ישראלי מומחה.

{knowledge_context}

כללים:
{json.dumps(rules[:10], ensure_ascii=False)}

תעריפון (דוגמאות):
{json.dumps(tariff_data[:15], ensure_ascii=False)}

סווג כל פריט עם קוד HS ישראלי (8-10 ספרות).
פלט JSON:
{{"classifications":[{{"item":"","hs_code":"","duty_rate":"","confidence":"גבוהה/בינונית/נמוכה","reasoning":""}}]}}"""
    
    result = call_ai(api_key, gemini_key, system, f"פריטים לסיווג:\n{json.dumps(items, ensure_ascii=False)}", 3000, tier="smart")
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1: return json.loads(result[start:end])
    except: pass
    return {"classifications": []}


def run_regulatory_agent(api_key, classifications, ministry_data, gemini_key=None):
    """Agent 3: Check regulatory requirements
    Session 15: Uses Gemini Flash (structured matching task)"""
    system = f"""אתה סוכן רגולציה. בדוק אילו אישורים נדרשים לפי הסיווגים.

משרדים ודרישות:
{json.dumps(ministry_data[:20], ensure_ascii=False)}

פלט JSON:
{{"regulatory":[{{"hs_code":"","ministries":[{{"name":"","required":true/false,"regulation":""}}]}}]}}"""
    
    result = call_ai(api_key, gemini_key, system, f"סיווגים:\n{json.dumps(classifications, ensure_ascii=False)}", tier="fast")
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1: return json.loads(result[start:end])
    except: pass
    return {"regulatory": []}


def run_fta_agent(api_key, classifications, origin_country, gemini_key=None):
    """Agent 4: Check FTA eligibility
    Session 15: Uses Gemini Flash (country-agreement matching)"""
    system = """אתה סוכן הסכמי סחר. בדוק זכאות להעדפות מכס.

הסכמים פעילים: EU, USA, UK, EFTA, Turkey, Jordan, Egypt, Mercosur, Mexico, Canada

פלט JSON:
{"fta":[{"hs_code":"","country":"","agreement":"","eligible":true/false,"preferential":"","documents_needed":""}]}"""
    
    result = call_ai(api_key, gemini_key, system, f"סיווגים: {json.dumps(classifications, ensure_ascii=False)}\nארץ מקור: {origin_country}", tier="fast")
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1: return json.loads(result[start:end])
    except: pass
    return {"fta": []}


def run_risk_agent(api_key, invoice_data, classifications, gemini_key=None):
    """Agent 5: Risk assessment
    Session 15: Uses Gemini Flash (pattern detection task)"""
    system = """אתה סוכן הערכת סיכונים. בדוק:
1. ערך נמוך חשוד
2. סיווג שגוי אפשרי
3. מקור בעייתי
4. חוסר התאמה

פלט JSON:
{"risk":{"level":"נמוך/בינוני/גבוה","items":[{"item":"","issue":"","recommendation":""}]}}"""
    
    result = call_ai(api_key, gemini_key, system, f"חשבונית: {json.dumps(invoice_data, ensure_ascii=False)}\nסיווגים: {json.dumps(classifications, ensure_ascii=False)}", tier="fast")
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1: return json.loads(result[start:end])
    except: pass
    return {"risk": {"level": "נמוך", "items": []}}


def run_synthesis_agent(api_key, all_results, gemini_key=None):
    """Agent 6: Final synthesis with proper Hebrew formatting
    Session 15: Uses Gemini 2.5 Pro (good Hebrew, lower cost than Claude)"""
    system = """אתה סוכן סיכום מקצועי. כתוב סיכום מעוצב היטב בעברית.

חובה לעקוב אחר הפורמט הבא בדיוק:

📋 מה נמצא:
[כתוב 2-3 משפטים המתארים את תוכן החשבונית, המוצרים, ארץ המקור, והערך. כל משפט בשורה חדשה.]

📌 המלצות עיקריות:
• [המלצה ראשונה]
• [המלצה שנייה]
• [המלצה שלישית אם רלוונטי]

⚠️ אזהרות:
• [אזהרה ראשונה אם יש]
• [אזהרה שנייה אם יש]

כללי עיצוב חשובים:
- השתמש בשורה ריקה בין כל קטע
- השתמש בנקודות (•) לרשימות
- סיים כל משפט בנקודה
- אל תשתמש בכוכביות (**) או בסימני עיצוב אחרים
- כתוב בעברית תקנית וברורה
- אם אין אזהרות, השמט את הקטע הזה לחלוטין

טקסט מעוצב בלבד, לא JSON."""
    
    return call_ai(api_key, gemini_key, system, json.dumps(all_results, ensure_ascii=False)[:4000], tier="fast") or "לא ניתן לייצר סיכום."


def run_full_classification(api_key, doc_text, db, gemini_key=None):
    """Run complete multi-agent classification
    Session 15: Now accepts gemini_key for cost-optimized multi-model routing"""
    try:
        # Agent 1: Extract (Gemini Flash)
        print("    🔍 Agent 1: Extracting... [Gemini Flash]")
        invoice = run_document_agent(api_key, doc_text, gemini_key=gemini_key)
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
        
        # Agent 2: Classify (Claude Sonnet 4.5 — core task, best quality)
        print("    🏷️ Agent 2: Classifying... [Claude Sonnet 4.5]")
        classification = run_classification_agent(api_key, items, tariff, rules, knowledge_context, gemini_key=gemini_key)
        
        # Session 11: Validate HS codes against tariff database
        print("    ✅ Validating HS codes against tariff database...")
        raw_classifications = classification.get("classifications", [])
        validated_classifications = validate_and_correct_classifications(db, raw_classifications)
        classification["classifications"] = validated_classifications
        
        # Log validation results
        for c in validated_classifications:
            if c.get('hs_corrected'):
                print(f"    ⚠️ HS corrected: {c.get('original_hs_code')} → {c.get('hs_code')}")
            elif c.get('hs_warning'):
                print(f"    ⚠️ {c.get('hs_warning')}")
        
        # Agent 3: Regulatory (Gemini Flash)
        print("    ⚖️ Agent 3: Regulatory... [Gemini Flash]")
        regulatory = run_regulatory_agent(api_key, classification.get("classifications", []), ministry, gemini_key=gemini_key)
        
        # Agent 4: FTA (Gemini Flash)
        print("    🌍 Agent 4: FTA... [Gemini Flash]")
        fta = run_fta_agent(api_key, classification.get("classifications", []), origin, gemini_key=gemini_key)
        
        # Agent 5: Risk (Gemini Flash)
        print("    🚨 Agent 5: Risk... [Gemini Flash]")
        risk = run_risk_agent(api_key, invoice, classification.get("classifications", []), gemini_key=gemini_key)
        
        # Agent 6: Synthesis (Gemini Pro)
        print("    📝 Agent 6: Synthesis... [Gemini Pro]")
        all_results = {"invoice": invoice, "classification": classification, "regulatory": regulatory, "fta": fta, "risk": risk}
        synthesis = run_synthesis_agent(api_key, all_results, gemini_key=gemini_key)
        
        # Session 14: Clean synthesis text (fix typos, VAT rate, RTL spacing)
        if LANGUAGE_TOOLS_AVAILABLE:
            try:
                synthesis = _lang_checker.fix_all(synthesis)
            except Exception as e:
                print(f"    ⚠️ Language fix_all failed: {e}")
        
        return {
            "success": True,
            "agents": all_results,
            "synthesis": synthesis,
            "invoice_data": invoice  # Session 10: Pass invoice data for validation
        }
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return {"success": False, "error": str(e)}


def build_classification_email(results, sender_name, invoice_validation=None, tracking_code=None, invoice_data=None):
    """Build HTML email report - Updated with invoice validation and tracking code"""
    classifications = results.get("agents", {}).get("classification", {}).get("classifications", [])
    regulatory = results.get("agents", {}).get("regulatory", {}).get("regulatory", [])
    fta = results.get("agents", {}).get("fta", {}).get("fta", [])
    risk = results.get("agents", {}).get("risk", {}).get("risk", {})
    synthesis = results.get("synthesis", "")
    
    # Session 11: Generate tracking code if not provided
    if not tracking_code:
        tracking_code = generate_tracking_code()
    
    html = f'''<div style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;direction:rtl">
    <div style="background:linear-gradient(135deg,#1e3a5f,#2d5a87);color:white;padding:20px;border-radius:10px 10px 0 0">
        <h1 style="margin:0">📊 דו״ח סיווג מכס</h1>
        <p style="margin:5px 0 0 0;opacity:0.9">נוצר אוטומטית ע״י RCB</p>
        <p style="margin:5px 0 0 0;font-family:monospace;font-size:12px;opacity:0.8">Tracking: {tracking_code}</p>
    </div>
    <div style="background:#f8f9fa;padding:20px;border:1px solid #ddd">'''
    
    # Session 11: Add shipment info summary if available
    if invoice_data:
        direction = invoice_data.get('direction', 'unknown')
        direction_text = "יבוא לישראל" if direction == 'import' else "יצוא מישראל" if direction == 'export' else "לא ידוע"
        freight = invoice_data.get('freight_type', 'unknown')
        freight_text = "ים 🚢" if freight == 'sea' else "אוויר ✈️" if freight == 'air' else "לא ידוע"
        seller = invoice_data.get('seller', 'לא ידוע')[:30]
        buyer = invoice_data.get('buyer', 'לא ידוע')[:30]
        bl = invoice_data.get('bl_number', '')
        awb = invoice_data.get('awb_number', '')
        ref = f"B/L: {bl}" if bl else f"AWB: {awb}" if awb else "אין מספר משלוח"
        
        html += f'''<div style="background:#e3f2fd;border:1px solid #2196f3;border-radius:5px;padding:15px;margin-bottom:20px">
            <table style="width:100%;font-size:14px">
                <tr><td><strong>כיוון:</strong> {direction_text}</td><td><strong>הובלה:</strong> {freight_text}</td></tr>
                <tr><td><strong>מוכר:</strong> {seller}</td><td><strong>קונה:</strong> {buyer}</td></tr>
                <tr><td colspan="2"><strong>מס׳ משלוח:</strong> {ref}</td></tr>
            </table>
        </div>'''
    
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
    
    # Session 14: Clean synthesis text before rendering
    if LANGUAGE_TOOLS_AVAILABLE:
        try:
            synthesis = _lang_checker.fix_all(synthesis)
        except Exception:
            pass
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
        
        # Session 11: Show HS code with validation status
        hs_display = get_israeli_hs_format(c.get("hs_code", ""))
        hs_note = ""
        if c.get('hs_corrected'):
            hs_note = f'<br><small style="color:#856404">⚠️ תוקן מ-{get_israeli_hs_format(c.get("original_hs_code", ""))}</small>'
        elif c.get('hs_warning'):
            hs_note = f'<br><small style="color:#dc3545">⚠️ לא אומת</small>'
        elif c.get('hs_validated') and c.get('hs_exact_match'):
            hs_note = '<br><small style="color:#28a745">✅ אומת</small>'
        
        html += f'''<tr>
            <td style="padding:10px;border:1px solid #ddd">{c.get("item", "")[:40]}</td>
            <td style="padding:10px;border:1px solid #ddd;font-family:monospace;font-weight:bold">{hs_display}{hs_note}</td>
            <td style="padding:10px;border:1px solid #ddd">{c.get("duty_rate", "")}</td>
            <td style="padding:10px;border:1px solid #ddd;color:{color}">{conf}</td>
        </tr>'''
    html += '</table>'
    
    if regulatory:
        html += '<h2 style="color:#1e3a5f;margin-top:25px">⚖️ רגולציה</h2>'
        for r in regulatory:
            html += f'<p><strong>{get_israeli_hs_format(r.get("hs_code", ""))}</strong>: '
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
    """Build Excel report - Updated Session 11 with validation status"""
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
        headers = ["פריט", "קוד HS", "מכס", "ודאות", "סטטוס אימות", "נימוק"]
        for i, h in enumerate(headers, 1):
            ws2.cell(1, i, h).font = Font(bold=True)
        for row, c in enumerate(results.get("agents", {}).get("classification", {}).get("classifications", []), 2):
            ws2.cell(row, 1, c.get("item", ""))
            ws2.cell(row, 2, get_israeli_hs_format(c.get("hs_code", "")))
            ws2.cell(row, 3, c.get("duty_rate", ""))
            ws2.cell(row, 4, c.get("confidence", ""))
            
            # Session 11: Add validation status
            validation_status = ""
            if c.get('hs_corrected'):
                validation_status = f"תוקן מ-{get_israeli_hs_format(c.get('original_hs_code', ''))}"
            elif c.get('hs_warning'):
                validation_status = "לא נמצא במאגר"
            elif c.get('hs_validated') and c.get('hs_exact_match'):
                validation_status = "אומת ✓"
            elif c.get('hs_validated'):
                validation_status = "התאמה חלקית"
            ws2.cell(row, 5, validation_status)
            
            ws2.cell(row, 6, c.get("reasoning", ""))
        
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


def process_and_send_report(access_token, rcb_email, to_email, subject, sender_name, raw_attachments, msg_id, get_secret_func, db, firestore, helper_graph_send, extract_text_func, email_body=None):
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
        
        # Session 15: Get Gemini key for cost-optimized agents
        gemini_key = None
        try:
            gemini_key = get_secret_func('GEMINI_API_KEY')
            if gemini_key:
                print("  🔑 Gemini key loaded (multi-model mode)")
            else:
                print("  ℹ️ No Gemini key - all agents will use Claude")
        except Exception:
            print("  ℹ️ Gemini key not configured - all agents will use Claude")
        
        print("  📄 Extracting text...")
        doc_text = extract_text_func(raw_attachments, email_body=email_body)
        if not doc_text or len(doc_text) < 50:
            print("  ⚠️ No text")
            return False
        
        print(f"  📝 {len(doc_text)} chars")
        
        results = run_full_classification(api_key, doc_text, db, gemini_key=gemini_key)
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
        
        # Session 11: Build standardized English subject line FIRST (need tracking code for HTML)
        invoice_data = results.get('invoice_data', {})
        score = invoice_validation['score'] if invoice_validation else None
        
        # Determine status
        if invoice_validation and invoice_validation['score'] < 70:
            status = "CLARIFICATION"
        elif invoice_validation and invoice_validation['score'] >= 70:
            status = "FINAL"
        else:
            status = "ACK"
        
        # Session 14: Use improved subject line generator with fallback
        if LANGUAGE_TOOLS_AVAILABLE:
            try:
                subject_line, tracking_code = build_rcb_subject_v2(invoice_data, status, score)
            except Exception as e:
                print(f"    ⚠️ Language tools subject failed ({e}), using original")
                subject_line, tracking_code = build_rcb_subject(invoice_data, status, score)
        else:
            subject_line, tracking_code = build_rcb_subject(invoice_data, status, score)
        print(f"  🏷️ Tracking: {tracking_code}")
        
        print("  📋 Building reports...")
        html = build_classification_email(results, sender_name, invoice_validation, tracking_code, invoice_data)
        excel = build_excel_report(results)
        
        attachments = []
        if excel:
            attachments.append({
                '@odata.type': '#microsoft.graph.fileAttachment',
                'name': f'RCB_{tracking_code}_{datetime.now().strftime("%Y%m%d")}.xlsx',
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
        if helper_graph_send(access_token, rcb_email, to_email, subject_line, html, msg_id, attachments):
            print(f"  ✅ Sent to {to_email}")
            
            # Session 11: Auto-send clarification request if score < 70
            clarification_sent = False
            if MODULES_AVAILABLE and invoice_validation and invoice_validation['score'] < 70:
                try:
                    from lib.clarification_generator import (
                        generate_missing_docs_request,
                        DocumentType,
                        UrgencyLevel,
                    )
                    
                    # Map missing fields to document types
                    missing_docs = []
                    field_to_doc = {
                        'ארץ המקור': DocumentType.CERTIFICATE_OF_ORIGIN,
                        'פרטי אריזות': DocumentType.PACKING_LIST,
                        'משקלים': DocumentType.PACKING_LIST,
                        'תנאי מכר': DocumentType.INVOICE,
                        'מחיר': DocumentType.INVOICE,
                        'תיאור הטובין': DocumentType.INVOICE,
                    }
                    
                    for field_name in invoice_validation.get('missing_fields', []):
                        if field_name in field_to_doc:
                            doc = field_to_doc[field_name]
                            if doc not in missing_docs:
                                missing_docs.append(doc)
                    
                    if missing_docs:
                        # Determine urgency based on score
                        urgency = UrgencyLevel.HIGH if invoice_validation['score'] < 50 else UrgencyLevel.MEDIUM
                        
                        # Generate clarification request
                        clarification = generate_missing_docs_request(
                            missing_docs=missing_docs,
                            invoice_number=invoice_data.get('invoice_number') or invoice_data.get('invoice_date'),
                            supplier_name=invoice_data.get('seller'),
                            recipient_name=sender_name,
                            urgency=urgency,
                            sender_name="מערכת RCB",
                        )
                        
                        # Build clarification email HTML
                        clarification_html = f'''<div dir="rtl" style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto">
                        <div style="background:#1e3a5f;color:white;padding:20px;text-align:center">
                            <h1 style="margin:0">📋 בקשה להשלמת מסמכים</h1>
                        </div>
                        <div style="padding:25px;background:#fff">
                            <pre style="white-space:pre-wrap;font-family:Arial,sans-serif;direction:rtl;text-align:right">{clarification.body}</pre>
                        </div>
                        <hr style="margin:25px 0">
                        <table><tr>
                            <td><img src="https://rpa-port.com/wp-content/uploads/2020/01/logo.png" style="width:70px"></td>
                            <td style="border-right:3px solid #1e3a5f;padding-right:15px">
                                <strong style="color:#1e3a5f">🤖 RCB - AI Customs Broker</strong><br>
                                R.P.A. PORT LTD | rcb@rpa-port.co.il
                            </td>
                        </tr></table>
                        </div>'''
                        
                        # Send clarification email with same tracking code
                        clarification_subject = f"[{tracking_code}] ⚠️CLARIFICATION | {clarification.subject}"
                        if helper_graph_send(access_token, rcb_email, to_email, clarification_subject, clarification_html, None, []):
                            print(f"  📋 Clarification request sent (score: {invoice_validation['score']}/100)")
                            clarification_sent = True
                        
                except Exception as ce:
                    print(f"  ⚠️ Clarification generation error: {ce}")
            
            # Save to Firestore with validation data and tracking code
            save_data = {
                "tracking_code": tracking_code,
                "subject": subject_line,
                "original_subject": subject,
                "to": to_email,
                "items": len(results.get("agents", {}).get("classification", {}).get("classifications", [])),
                "timestamp": firestore.SERVER_TIMESTAMP,
                # Session 11: Store extracted shipping info
                "direction": invoice_data.get('direction', 'unknown'),
                "freight_type": invoice_data.get('freight_type', 'unknown'),
                "bl_number": invoice_data.get('bl_number', ''),
                "awb_number": invoice_data.get('awb_number', ''),
                "seller": invoice_data.get('seller', ''),
                "buyer": invoice_data.get('buyer', ''),
            }
            
            if invoice_validation:
                save_data["invoice_score"] = invoice_validation['score']
                save_data["invoice_valid"] = invoice_validation['is_valid']
                save_data["missing_fields"] = invoice_validation['missing_fields']
                save_data["clarification_sent"] = clarification_sent
            
            db.collection("rcb_classifications").add(save_data)

            # Phase 2: Learn from this classification
            if ENRICHMENT_AVAILABLE:
                try:
                    enrichment = create_enrichment_agent(db)
                    enrichment.on_classification_complete(results)
                    enrichment.on_email_processed({
                        "sender": to_email,
                        "subject": subject,
                        "extracted_items": invoice_data.get('items', [])
                    })
                    print("  Enrichment: learned from classification")
                except Exception as e:
                    print(f"  Enrichment learning error: {e}")

            return True
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
