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
import re
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

# Intelligence module: system's own brain (Firestore-only, no AI)
try:
    from lib.intelligence import pre_classify, lookup_regulatory, lookup_fta, validate_documents, query_free_import_order, route_to_ministries
    INTELLIGENCE_AVAILABLE = True
except ImportError as e:
    print(f"Intelligence module not available: {e}")
    INTELLIGENCE_AVAILABLE = False

# Document parser: per-document type identification & field extraction
try:
    from lib.document_parser import parse_all_documents
    DOCUMENT_PARSER_AVAILABLE = True
except ImportError as e:
    print(f"Document parser not available: {e}")
    DOCUMENT_PARSER_AVAILABLE = False

# Smart question engine: elimination-based clarification
try:
    from lib.smart_questions import should_ask_questions, generate_smart_questions, format_questions_html
    SMART_QUESTIONS_AVAILABLE = True
except ImportError as e:
    print(f"Smart questions not available: {e}")
    SMART_QUESTIONS_AVAILABLE = False

# Verification loop: verify, enrich, cache every classification
try:
    from lib.verification_loop import verify_all_classifications, learn_from_verification
    VERIFICATION_AVAILABLE = True
except ImportError as e:
    print(f"Verification loop not available: {e}")
    VERIFICATION_AVAILABLE = False

# Document tracker: shipment phase detection + document completeness
try:
    from lib.document_tracker import create_tracker, Document, DocumentType as TrackerDocType, feed_parsed_documents
    TRACKER_AVAILABLE = True
except ImportError as e:
    print(f"Document tracker not available: {e}")
    TRACKER_AVAILABLE = False

# Tool-calling classification engine (Session 22)
try:
    from lib.tool_calling_engine import tool_calling_classify
    TOOL_CALLING_AVAILABLE = True
except ImportError as e:
    print(f"Tool-calling engine not available: {e}")
    TOOL_CALLING_AVAILABLE = False

# Three-way AI cross-check (Session 27)
try:
    from lib.cross_checker import cross_check_all_items, get_cross_check_summary
    CROSS_CHECK_AVAILABLE = True
except ImportError as e:
    print(f"Cross-checker not available: {e}")
    CROSS_CHECK_AVAILABLE = False

# =============================================================================
# FEATURE FLAGS (Session 26/27: cost optimization + cross-check)
# =============================================================================

PRE_CLASSIFY_BYPASS_ENABLED = True    # Skip AI pipeline when pre_classify confidence >= 90
PRE_CLASSIFY_BYPASS_THRESHOLD = 90    # Minimum confidence to bypass
COST_TRACKING_ENABLED = True          # Print per-call cost estimates
CROSS_CHECK_ENABLED = True            # Session 27: Run 3-way cross-check after classification

# =============================================================================
# SESSION 27: Per-Run Cost Accumulator
# =============================================================================

class _CostTracker:
    """Accumulates AI costs per classification run. Thread-safe reset per call."""
    def __init__(self):
        self.reset()

    def reset(self):
        self._costs = {}  # model_name -> total_cost
        self._calls = {}  # model_name -> call_count

    def add(self, model, cost):
        self._costs[model] = self._costs.get(model, 0) + cost
        self._calls[model] = self._calls.get(model, 0) + 1

    def total(self):
        return sum(self._costs.values())

    def summary(self):
        if not self._costs:
            return ""
        lines = ["💰 Cost Summary:"]
        for model in sorted(self._costs.keys()):
            lines.append(f"    {model}: {self._calls[model]} calls = ${self._costs[model]:.4f}")
        lines.append(f"    TOTAL: ${self.total():.4f}")
        return "\n".join(lines)

_cost_tracker = _CostTracker()

# =============================================================================
# HS CODE VALIDATION HELPERS
# =============================================================================

_HS_RE = re.compile(r'^\d{4,10}$')

def _is_valid_hs(code):
    """Check if a string looks like a real HS code (4-10 digits, chapter 01-97)."""
    if not code or not isinstance(code, str):
        return False
    clean = code.replace(".", "").replace("/", "").replace(" ", "").strip()
    if not _HS_RE.match(clean):
        return False
    try:
        chapter = int(clean[:2])
        return 1 <= chapter <= 97
    except (ValueError, IndexError):
        return False


def _is_product_description(text):
    """Check if text looks like a real product description, not raw email/HTML."""
    if not text or not isinstance(text, str):
        return False
    if text.startswith("=== "):
        return False
    if "&nbsp;" in text or "<br" in text.lower() or "<div" in text.lower():
        return False
    if len(text) > 400 and text.count("===") > 1:
        return False
    return True


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
    """Call Claude API - Sonnet 4.5 (Session 15: upgraded from Sonnet 4)
    Session 26: Added cost tracking"""
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
            data = response.json()
            # Cost tracking: Claude Sonnet 4.5 pricing ($3/$15 per MTok)
            if COST_TRACKING_ENABLED:
                usage = data.get("usage", {})
                inp_tok = usage.get("input_tokens", 0)
                out_tok = usage.get("output_tokens", 0)
                cost = (inp_tok * 3.0 + out_tok * 15.0) / 1_000_000
                print(f"    💰 Claude: {inp_tok}+{out_tok} tokens = ${cost:.4f}")
                _cost_tracker.add("Claude Sonnet", cost)
            return data['content'][0]['text']
        else:
            print(f"Claude API error: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"Claude call error: {e}")
        return None


# =============================================================================
# SESSION 15: Gemini API Integration (cost optimization)
# =============================================================================

# =============================================================================
# SESSION 27: ChatGPT / OpenAI Integration (cross-check)
# =============================================================================

def call_chatgpt(openai_key, system_prompt, user_prompt, max_tokens=2000, model="gpt-4o-mini"):
    """Call OpenAI ChatGPT API.

    Session 27: Added for three-way cross-check.
    Models:
      - gpt-4o-mini: Fast, cheap (~$0.15/$0.60 per MTok)
      - gpt-4o: Higher quality (~$2.50/$10 per MTok)
    """
    if not openai_key:
        return None
    try:
        import openai
        client = openai.OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        result = response.choices[0].message.content
        # Cost tracking
        if COST_TRACKING_ENABLED:
            usage = response.usage
            inp_tok = usage.prompt_tokens if usage else 0
            out_tok = usage.completion_tokens if usage else 0
            if "mini" in model:
                cost = (inp_tok * 0.15 + out_tok * 0.60) / 1_000_000
            else:  # gpt-4o
                cost = (inp_tok * 2.50 + out_tok * 10.0) / 1_000_000
            print(f"    💰 ChatGPT ({model}): {inp_tok}+{out_tok} tokens = ${cost:.4f}")
            _cost_tracker.add(f"ChatGPT {model}", cost)
        return result
    except ImportError:
        print("    ⚠️ openai package not installed, ChatGPT unavailable")
        return None
    except Exception as e:
        print(f"    ChatGPT call error ({model}): {e}")
        return None


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
            # Cost tracking: Gemini pricing
            if COST_TRACKING_ENABLED:
                usage = data.get("usageMetadata", {})
                inp_tok = usage.get("promptTokenCount", 0)
                out_tok = usage.get("candidatesTokenCount", 0)
                if "flash" in model:
                    cost = (inp_tok * 0.15 + out_tok * 0.60) / 1_000_000
                else:  # pro
                    cost = (inp_tok * 1.25 + out_tok * 10.0) / 1_000_000
                print(f"    💰 Gemini ({model}): {inp_tok}+{out_tok} tokens = ${cost:.4f}")
                _cost_tracker.add(f"Gemini {model}", cost)
            candidates = data.get("candidates", [])
            if candidates:
                finish_reason = candidates[0].get("finishReason", "UNKNOWN")
                if finish_reason not in ("STOP", "UNKNOWN"):
                    print(f"    ⚠️ Gemini finishReason: {finish_reason} (model={model})")
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    text = parts[0].get("text", "")
                    # Strip markdown code fences that Gemini often wraps around JSON
                    if text.startswith("```"):
                        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                    return text.strip()
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

def _try_parse_agent1(result, model_name):
    """Try to parse Agent 1 JSON response. Returns parsed dict or None."""
    try:
        if result:
            start, end = result.find('{'), result.rfind('}') + 1
            if start != -1 and end > start:
                parsed = json.loads(result[start:end])
                items = parsed.get("items", [])
                print(f"    📦 Agent 1 ({model_name}): {len(items)} items extracted, keys={list(parsed.keys())}")
                return parsed
            else:
                print(f"    ⚠️ Agent 1 ({model_name}): No complete JSON in response ({len(result)} chars): {result[:200]}")
        else:
            print(f"    ⚠️ Agent 1 ({model_name}): returned None/empty")
    except Exception as e:
        print(f"    ⚠️ Agent 1 ({model_name}) JSON parse error: {e}")
        print(f"    ⚠️ Agent 1 ({model_name}) raw ({len(result)} chars): {result[:300]}")
    return None


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
- CRITICAL: Extract EACH product as a SEPARATE item in the items array. Every line item on the invoice must be its own entry. If the invoice has 10 products, return 10 items. Include the product name, quantity, unit price, total, and origin country for each.
- Chinese product names (中文) must be translated to English in the description field.
- Do NOT combine multiple products into one item. Do NOT summarize.
- direction: "import" אם הסחורה מגיעה לישראל, "export" אם יוצאת מישראל
- freight_type: "sea" אם יש B/L או אונייה, "air" אם יש AWB או טיסה
- bl_number: מספר שטר מטען ימי (Bill of Lading)
- awb_number: מספר שטר מטען אווירי (Air Waybill)
- rpa_file_number: מספר תיק RPA אם מופיע

JSON בלבד."""
    result = call_ai(api_key, gemini_key, system, doc_text[:6000], max_tokens=4096, tier="fast")
    parsed = _try_parse_agent1(result, "Gemini")
    if parsed:
        return parsed

    # Gemini failed — retry with Claude (more reliable JSON output)
    print("    🔄 Agent 1: Gemini failed, retrying with Claude...")
    result = call_claude(api_key, system, doc_text[:6000], max_tokens=4096)
    parsed = _try_parse_agent1(result, "Claude")
    if parsed:
        return parsed

    print("    ⚠️ Agent 1: BOTH models failed — returning doc_text[:500] as single item")
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
    
    return call_ai(api_key, gemini_key, system, json.dumps(all_results, ensure_ascii=False)[:4000], tier="pro") or "לא ניתן לייצר סיכום."


def _link_invoice_to_classifications(items, classifications):
    """Link each classification back to its source invoice line item.

    Uses simple substring matching on descriptions. Adds line_number,
    invoice_description, quantity, unit_price, total, origin_country
    to each classification dict.
    """
    if not items or not classifications:
        return classifications

    for c in classifications:
        c_desc = (c.get("item") or "").lower().strip()
        if not c_desc:
            continue
        best_idx = -1
        best_score = 0
        for idx, inv_item in enumerate(items):
            if not isinstance(inv_item, dict):
                continue
            inv_desc = (inv_item.get("description") or "").lower().strip()
            if not inv_desc:
                continue
            # Simple overlap: check if key words match
            if inv_desc in c_desc or c_desc in inv_desc:
                score = len(inv_desc)
                if score > best_score:
                    best_score = score
                    best_idx = idx
            else:
                # Fallback: count shared words
                c_words = set(c_desc.split())
                inv_words = set(inv_desc.split())
                overlap = len(c_words & inv_words)
                if overlap > best_score:
                    best_score = overlap
                    best_idx = idx

        if best_idx >= 0:
            inv = items[best_idx]
            c["line_number"] = best_idx + 1
            c["invoice_description"] = inv.get("description", "")
            c["quantity"] = inv.get("quantity", "")
            c["unit_price"] = inv.get("unit_price", "")
            c["total_value"] = inv.get("total", "")
            c["origin_country"] = inv.get("origin_country", "")
        else:
            c["line_number"] = 0

    return classifications


def run_full_classification(api_key, doc_text, db, gemini_key=None):
    """Run complete multi-agent classification
    Session 15: Now accepts gemini_key for cost-optimized multi-model routing
    Session 18: Intelligence module runs BEFORE AI agents"""
    try:
        # Agent 1: Extract (Gemini Flash)
        print("    🔍 Agent 1: Extracting... [Gemini Flash]")
        invoice = run_document_agent(api_key, doc_text, gemini_key=gemini_key)
        if not isinstance(invoice, dict):
            print(f"    ⚠️ Agent 1 returned non-dict: {type(invoice)} — using fallback")
            invoice = {"items": [{"description": doc_text[:500]}]}
        items = invoice.get("items") or [{"description": doc_text[:500]}]
        if not isinstance(items, list):
            print(f"    ⚠️ Agent 1 items is not a list: {type(items)} — using fallback")
            items = [{"description": doc_text[:500]}]

        # DEBUG: Log exactly what Agent 1 extracted
        print(f"    📦 Agent 1 extracted {len(items)} items:")
        for idx, item in enumerate(items[:10]):
            if isinstance(item, dict):
                desc = item.get('description', '')[:80]
                qty = item.get('quantity', '')
                origin_c = item.get('origin_country', '')
                print(f"       [{idx+1}] {desc} | qty={qty} | origin={origin_c}")
            else:
                print(f"       [{idx+1}] NOT A DICT: {str(item)[:80]}")

        origin = items[0].get("origin_country", "") if items and isinstance(items[0], dict) else ""

        # ── DOCUMENT PARSER: Identify each document and extract structured fields ──
        parsed_documents = []
        if DOCUMENT_PARSER_AVAILABLE:
            try:
                parsed_documents = parse_all_documents(doc_text)
                if parsed_documents:
                    types_found = [d["type_info"]["name_en"] for d in parsed_documents]
                    print(f"    📑 Document Parser: {len(parsed_documents)} docs — {', '.join(types_found)}")
                    for pd in parsed_documents:
                        comp = pd.get("completeness", {})
                        if comp.get("missing"):
                            crit = [m["name_he"] for m in comp["missing"] if m["importance"] == "critical"]
                            if crit:
                                print(f"       ⚠️ {pd.get('filename','')}: missing critical — {', '.join(crit)}")
            except Exception as e:
                print(f"    ⚠️ Document parser error: {e}")

        # ── SHIPMENT TRACKER: Feed BL/DO/invoice fields to tracker ──
        tracker_info = None
        if TRACKER_AVAILABLE and parsed_documents:
            try:
                bl_num = invoice.get("bl_number", "") or ""
                shipment_id = bl_num or invoice.get("awb_number", "") or "PENDING"
                direction_val = invoice.get("direction", "import")
                transport = "sea_fcl" if invoice.get("freight_type") == "sea" else (
                    "air" if invoice.get("freight_type") == "air" else None)

                tracker = create_tracker(
                    shipment_id=shipment_id,
                    direction=direction_val,
                    transport_mode=transport,
                )
                feed_parsed_documents(tracker, parsed_documents, invoice_data=invoice)

                # Also add invoice doc if Agent 1 extracted it
                if invoice.get("invoice_number") or invoice.get("seller"):
                    tracker.add_document(Document(
                        doc_type=TrackerDocType.INVOICE,
                        doc_number=invoice.get("invoice_number", ""),
                    ))

                tracker_info = tracker.to_dict()
                print(f"    📦 Tracker: phase={tracker.phase_hebrew}, "
                      f"docs={len(tracker.documents)}, "
                      f"missing={len(tracker.missing_docs)}")
            except Exception as e:
                print(f"    ⚠️ Tracker error: {e}")

        # ── PRE-CLASSIFY: System's own brain BEFORE AI ──
        intelligence_context = ""
        intelligence_results = {}
        doc_validation = None
        seller_name = invoice.get("seller", "")
        if INTELLIGENCE_AVAILABLE:
            print("    🧠 Intelligence: Pre-classifying from own knowledge...")
            for item in items[:3]:
                if not isinstance(item, dict):
                    continue
                # Use extracted product description, not raw text blob
                desc = item.get("description", "")
                if not desc or desc.startswith("=== ") or "&nbsp;" in desc:
                    continue  # Skip raw email/HTML text — not a real product description
                item_origin = item.get("origin_country", origin)
                pc_result = pre_classify(db, desc, item_origin, seller_name=seller_name)
                if not isinstance(pc_result, dict):
                    continue
                intelligence_results[desc[:50]] = pc_result
                if pc_result.get("context_text"):
                    intelligence_context += pc_result["context_text"] + "\n\n"

            # Validate documents present in extracted text
            has_fta = any(
                r.get("fta", {}).get("eligible", False)
                for r in intelligence_results.values()
                if isinstance(r, dict)
            )
            doc_validation = validate_documents(doc_text, direction="import", has_fta=has_fta)
            if doc_validation.get("missing"):
                missing_names = ", ".join(m["name_he"] for m in doc_validation["missing"])
                print(f"    🧠 Intelligence: Missing documents — {missing_names}")

        # Get context (existing librarian search) — only real product descriptions
        search_terms = [
            i.get("description", "")[:50]
            for i in items[:5]
            if isinstance(i, dict) and _is_product_description(i.get("description", ""))
        ]
        tariff = query_tariff(db, search_terms)
        ministry = query_ministry_index(db)
        rules = query_classification_rules(db)

        # Enhanced knowledge search — skip raw text blobs
        knowledge_context = ""
        for item in items[:3]:
            if not isinstance(item, dict):
                continue
            desc = item.get("description", "")
            if desc and _is_product_description(desc):
                knowledge = full_knowledge_search(db, desc)
                knowledge_context += build_classification_context(knowledge) + "\n"

        # Merge intelligence context with librarian context
        combined_context = intelligence_context + knowledge_context

        # Agent 2: Classify (Claude Sonnet 4.5 — core task, best quality)
        items_payload = json.dumps(items, ensure_ascii=False)
        print(f"    🏷️ Agent 2: Classifying {len(items)} items ({len(items_payload)} chars payload)... [Claude Sonnet 4.5]")
        if len(items) == 1:
            desc_preview = items[0].get('description', '')[:150] if isinstance(items[0], dict) else str(items[0])[:150]
            print(f"    ⚠️ Agent 2 WARNING: Only 1 item! desc: {desc_preview}")
        classification = run_classification_agent(api_key, items, tariff, rules, combined_context, gemini_key=gemini_key)
        if not isinstance(classification, dict):
            classification = {"classifications": []}

        # Session 11: Validate HS codes against tariff database
        # First: reject non-HS-code text (e.g., Hebrew "לא ניתן לסווג")
        raw_classifications = classification.get("classifications") or []
        for c in raw_classifications:
            hs = c.get("hs_code", "")
            if hs and not _is_valid_hs(hs):
                print(f"    ⚠️ Agent 2 returned non-HS text: '{hs}' → marking unclassified")
                c["original_hs_code"] = hs
                c["hs_code"] = ""
                c["confidence"] = "נמוכה"
                c["hs_warning"] = f"⚠️ '{hs}' אינו קוד HS תקין"

        print("    ✅ Validating HS codes against tariff database...")
        validated_classifications = validate_and_correct_classifications(db, raw_classifications)
        classification["classifications"] = validated_classifications

        # Log validation results
        for c in validated_classifications:
            if c.get('hs_corrected'):
                print(f"    ⚠️ HS corrected: {c.get('original_hs_code')} → {c.get('hs_code')}")
            elif c.get('hs_warning'):
                print(f"    ⚠️ {c.get('hs_warning')}")

        # ── FREE IMPORT ORDER: Verify HS codes against official API ──
        # Only for valid HS codes — skip text like "לא ניתן לסווג"
        free_import_results = {}
        if INTELLIGENCE_AVAILABLE:
            for c in validated_classifications[:3]:
                hs = c.get("hs_code", "")
                if hs and _is_valid_hs(hs):
                    try:
                        fio = query_free_import_order(db, hs)
                        if fio.get("found"):
                            free_import_results[hs] = fio
                    except Exception as e:
                        print(f"    ⚠️ Free Import Order query error: {e}")

        # ── MINISTRY ROUTING: Combine all sources into actionable guidance ──
        # Only for valid HS codes
        ministry_routing = {}
        if INTELLIGENCE_AVAILABLE:
            for c in validated_classifications[:3]:
                hs = c.get("hs_code", "")
                if hs and _is_valid_hs(hs):
                    try:
                        fio_for_hs = free_import_results.get(hs)
                        routing = route_to_ministries(db, hs, fio_for_hs)
                        if routing.get("ministries"):
                            ministry_routing[hs] = routing
                    except Exception as e:
                        print(f"    ⚠️ Ministry routing error: {e}")

        # ── VERIFICATION LOOP: Verify, enrich, cache every classification ──
        if VERIFICATION_AVAILABLE:
            try:
                validated_classifications = verify_all_classifications(
                    db, validated_classifications, free_import_results=free_import_results
                )
                classification["classifications"] = validated_classifications
                # Learn from verified items
                for c in validated_classifications:
                    if c.get("verification_status") in ("official", "verified"):
                        learn_from_verification(db, c)
            except Exception as e:
                print(f"    ⚠️ Verification loop error: {e}")

        # ── LINK: Map invoice line items → classifications ──
        validated_classifications = _link_invoice_to_classifications(items, validated_classifications)
        classification["classifications"] = validated_classifications

        # ── SMART QUESTIONS: Detect ambiguity and generate elimination questions ──
        smart_questions = []
        ambiguity_info = {}
        if SMART_QUESTIONS_AVAILABLE:
            try:
                ask, ambiguity_info = should_ask_questions(
                    validated_classifications,
                    intelligence_results=intelligence_results,
                    free_import_results=free_import_results,
                    ministry_routing=ministry_routing,
                )
                if ask:
                    smart_questions = generate_smart_questions(
                        ambiguity_info,
                        validated_classifications,
                        invoice_data=invoice,
                        free_import_results=free_import_results,
                        ministry_routing=ministry_routing,
                        parsed_documents=parsed_documents,
                    )
                    print(f"    ❓ Smart questions: {len(smart_questions)} questions generated "
                          f"(reason: {ambiguity_info.get('reason', 'unknown')})")
                else:
                    print(f"    ✅ Classification clear — no questions needed")
            except Exception as e:
                print(f"    ⚠️ Smart questions error: {e}")

        # Agent 3: Regulatory (Gemini Flash)
        print("    ⚖️ Agent 3: Regulatory... [Gemini Flash]")
        regulatory = run_regulatory_agent(api_key, classification.get("classifications", []), ministry, gemini_key=gemini_key)
        if not isinstance(regulatory, dict):
            regulatory = {"regulatory": []}

        # Agent 4: FTA (Gemini Flash)
        print("    🌍 Agent 4: FTA... [Gemini Flash]")
        fta = run_fta_agent(api_key, classification.get("classifications", []), origin, gemini_key=gemini_key)
        if not isinstance(fta, dict):
            fta = {"fta": []}

        # Agent 5: Risk (Gemini Flash)
        print("    🚨 Agent 5: Risk... [Gemini Flash]")
        risk = run_risk_agent(api_key, invoice, classification.get("classifications", []), gemini_key=gemini_key)
        if not isinstance(risk, dict):
            risk = {"risk": {"level": "נמוך", "items": []}}

        # Agent 6: Synthesis (Gemini Pro)
        print("    📝 Agent 6: Synthesis... [Gemini Pro]")
        all_results = {"invoice": invoice, "classification": classification, "regulatory": regulatory, "fta": fta, "risk": risk}

        # Include intelligence results for synthesis context
        if intelligence_results:
            all_results["intelligence"] = {
                "pre_classify": {
                    k: {
                        "top_candidate": v["candidates"][0] if v.get("candidates") else None,
                        "candidates_found": v.get("stats", {}).get("candidates_found", 0),
                        "fta_eligible": v.get("stats", {}).get("fta_eligible", False),
                        "fta": v.get("fta") if isinstance(v.get("fta"), dict) else None,
                    }
                    for k, v in intelligence_results.items()
                    if isinstance(v, dict)
                }
            }
        if doc_validation:
            all_results["document_validation"] = {
                "score": doc_validation.get("score", 0),
                "present": [p["name_he"] for p in doc_validation.get("present", [])],
                "missing": [m["name_he"] for m in doc_validation.get("missing", [])],
            }

        # Include parsed document details for synthesis
        if parsed_documents:
            all_results["parsed_documents"] = [
                {
                    "filename": pd.get("filename", ""),
                    "doc_type": pd["doc_type"],
                    "type_name": pd["type_info"]["name_he"],
                    "confidence": pd["type_info"]["confidence"],
                    "completeness_score": pd["completeness"]["score"],
                    "fields_extracted": list(pd["fields"].keys()),
                    "critical_missing": [
                        m["name_he"] for m in pd["completeness"].get("missing", [])
                        if m["importance"] == "critical"
                    ],
                }
                for pd in parsed_documents
            ]

        # Include Free Import Order official results
        if free_import_results:
            all_results["free_import_order"] = {
                hs: {
                    "authorities": [a["name"] for a in fio.get("authorities", [])],
                    "requirements": [
                        req["name"]
                        for item in fio.get("items", [])
                        for req in item.get("legal_requirements", [])
                    ][:10],
                    "decree": fio.get("decree_version", ""),
                }
                for hs, fio in free_import_results.items()
            }

        # Include ministry routing with procedures and documents
        if ministry_routing:
            all_results["ministry_routing"] = {
                hs: {
                    "risk_level": r.get("risk_level", "low"),
                    "summary_he": r.get("summary_he", ""),
                    "ministries": [
                        {
                            "name_he": m["name_he"],
                            "url": m.get("url", ""),
                            "documents_he": m.get("documents_he", []),
                            "procedure": m.get("procedure", ""),
                            "official": m.get("official", False),
                        }
                        for m in r.get("ministries", [])
                    ],
                }
                for hs, r in ministry_routing.items()
            }

        # Include smart questions for synthesis awareness
        if smart_questions:
            all_results["smart_questions"] = {
                "reason": ambiguity_info.get("reason", ""),
                "questions_count": len(smart_questions),
                "first_question": smart_questions[0]["question_he"] if smart_questions else "",
            }

        # ── QUALITY GATE: Audit + retry before synthesis ──
        pre_send = {"agents": all_results, "invoice_data": invoice}
        audit = audit_before_send(
            pre_send, api_key=api_key, items=items,
            tariff=tariff, rules=rules, context=combined_context,
            gemini_key=gemini_key, db=db,
        )
        all_results["classification"]["classifications"] = audit["classifications"]

        synthesis = run_synthesis_agent(api_key, all_results, gemini_key=gemini_key)

        # Session 14: Clean synthesis text (fix typos, VAT rate, RTL spacing)
        if LANGUAGE_TOOLS_AVAILABLE:
            try:
                synthesis = _lang_checker.fix_all(synthesis)
            except Exception as e:
                print(f"    ⚠️ Language fix_all failed: {e}")

        result = {
            "success": True,
            "agents": all_results,
            "synthesis": synthesis,
            "invoice_data": invoice,  # Session 10: Pass invoice data for validation
            "intelligence": intelligence_results,  # Session 18: Pre-classify results
            "document_validation": doc_validation,  # Session 18: Document check
            "free_import_order": free_import_results,  # Session 18: Official API results
            "ministry_routing": ministry_routing,  # Session 18: Phase C ministry routing
            "parsed_documents": parsed_documents,  # Session 19: Per-document parsing
            "smart_questions": smart_questions,  # Phase E: Elimination-based questions
            "ambiguity": ambiguity_info,  # Phase E: Ambiguity analysis
            "tracker": tracker_info,  # Shipment phase tracker
            "audit": audit,  # Quality gate results
        }
        return result
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# QUALITY GATE: Audit output before sending to customer
# =============================================================================

_CONFIDENCE_SCORES = {"גבוהה": 80, "בינונית": 50, "נמוכה": 20}
_HEBREW_HS_PATTERNS = re.compile(r'[\u0590-\u05FF]')


def _retry_classification(api_key, items, tariff, rules, context, gemini_key=None):
    """Retry Agent 2 with explicit instruction to return numeric HS codes."""
    retry_instruction = """חשוב מאוד: אתה חייב להחזיר קוד HS מספרי בלבד (6-10 ספרות).
אם אינך בטוח, החזר את הקוד הקרוב ביותר עם confidence "נמוכה".
לעולם אל תחזיר טקסט כמו "לא ניתן לסווג" בשדה hs_code.
אם באמת אין מספיק מידע לסיווג, החזר hs_code ריק ""."""
    enhanced_context = retry_instruction + "\n\n" + (context or "")
    return run_classification_agent(api_key, items, tariff, rules, enhanced_context, gemini_key=gemini_key)


def audit_before_send(results, api_key=None, items=None, tariff=None, rules=None,
                      context=None, gemini_key=None, db=None):
    """Quality gate — validate classification output before sending email.

    Returns dict:
        action: "send" | "send_with_warning" | "send_unclassified"
        classifications: cleaned/retried classification list
        warning_banner: HTML string or None
        avg_confidence: numeric 0-100
    """
    classifications = results.get("agents", {}).get("classification", {}).get("classifications", [])
    items = items or results.get("invoice_data", {}).get("items", [])

    print("    🔍 Quality Gate: Auditing classifications before send...")

    # ── Step 1: Check every HS code, collect bad ones ──
    bad_indices = []
    for i, c in enumerate(classifications):
        hs = c.get("hs_code", "")
        if not hs:
            bad_indices.append(i)
            continue
        # Hebrew text in HS code field
        if _HEBREW_HS_PATTERNS.search(hs):
            print(f"    ⚠️ QG: Hebrew text in HS code: '{hs}' (item: {c.get('item', '')[:40]})")
            c["original_hs_code"] = hs
            c["hs_code"] = ""
            c["confidence"] = "נמוכה"
            c["hs_warning"] = f"⚠️ '{hs}' אינו קוד HS תקין"
            bad_indices.append(i)
            continue
        if not _is_valid_hs(hs):
            print(f"    ⚠️ QG: Invalid HS format: '{hs}' (item: {c.get('item', '')[:40]})")
            c["original_hs_code"] = hs
            c["hs_code"] = ""
            c["confidence"] = "נמוכה"
            c["hs_warning"] = f"⚠️ '{hs}' אינו קוד HS תקין"
            bad_indices.append(i)

    # ── Step 2: Retry once if we have bad classifications and API key ──
    retried = False
    if bad_indices and api_key and tariff is not None and rules is not None:
        print(f"    🔄 QG: Retrying Agent 2 for {len(bad_indices)} unclassified items...")
        retry_result = _retry_classification(api_key, items, tariff, rules, context, gemini_key)
        if isinstance(retry_result, dict):
            retry_cls = retry_result.get("classifications", [])
            fixed = 0
            for ri, rc in enumerate(retry_cls):
                hs = rc.get("hs_code", "")
                if hs and _is_valid_hs(hs) and not _HEBREW_HS_PATTERNS.search(hs):
                    # Find matching original by item name or index
                    if ri < len(classifications):
                        orig = classifications[ri]
                        if not orig.get("hs_code") or not _is_valid_hs(orig.get("hs_code", "")):
                            orig["hs_code"] = hs
                            orig["duty_rate"] = rc.get("duty_rate", orig.get("duty_rate", ""))
                            orig["reasoning"] = rc.get("reasoning", orig.get("reasoning", ""))
                            orig["confidence"] = rc.get("confidence", "בינונית")
                            orig.pop("hs_warning", None)
                            orig["hs_retried"] = True
                            fixed += 1
            if fixed:
                print(f"    ✅ QG: Retry fixed {fixed} classifications")
                retried = True
            # Rebuild bad_indices after retry
            bad_indices = [i for i, c in enumerate(classifications)
                           if not c.get("hs_code") or not _is_valid_hs(c.get("hs_code", ""))]

    # ── Step 3: Compute average confidence ──
    scores = []
    for c in classifications:
        conf = c.get("confidence", "בינונית")
        scores.append(_CONFIDENCE_SCORES.get(conf, 50))
    avg_confidence = sum(scores) / len(scores) if scores else 0

    # ── Step 4: Determine action ──
    total = len(classifications)
    classified = total - len(bad_indices)

    if total == 0 or classified == 0:
        # ALL items unclassified
        print(f"    ⚠️ QG: ALL {total} items unclassified — switching to info email")
        action = "send_unclassified"
        warning_banner = _build_unclassified_banner(items)
    elif avg_confidence < 50:
        print(f"    ⚠️ QG: Low average confidence ({avg_confidence:.0f}%) — adding warning")
        action = "send_with_warning"
        warning_banner = _build_low_confidence_banner(avg_confidence, classified, total)
    else:
        action = "send"
        warning_banner = None
        print(f"    ✅ QG: {classified}/{total} classified, avg confidence {avg_confidence:.0f}%")

    # Write back cleaned classifications
    results["agents"]["classification"]["classifications"] = classifications
    results["audit"] = {
        "action": action,
        "avg_confidence": round(avg_confidence),
        "classified": classified,
        "total": total,
        "retried": retried,
    }

    return {
        "action": action,
        "classifications": classifications,
        "warning_banner": warning_banner,
        "avg_confidence": avg_confidence,
    }


def _build_unclassified_banner(items):
    """HTML banner for when all items are unclassified."""
    item_list = ""
    for item in (items or [])[:5]:
        if isinstance(item, dict):
            desc = item.get("description", item.get("item", ""))
            if desc and _is_product_description(desc):
                item_list += f"<li>{desc[:100]}</li>"
    items_html = f"<ul>{item_list}</ul>" if item_list else ""

    return f'''<div style="background:#f8d7da;border:2px solid #dc3545;border-radius:5px;padding:20px;margin-bottom:20px">
        <h3 style="color:#721c24;margin:0">⚠️ לא הצלחנו לסווג את הפריטים</h3>
        <p style="color:#721c24;margin:10px 0 0 0">המערכת לא הצליחה לקבוע קודי HS עבור הפריטים שלהלן.
        יש לספק תיאור מפורט יותר של המוצרים, כולל: חומר גלם, שימוש מיועד, הרכב.</p>
        {items_html}
        <p style="color:#721c24;margin:10px 0 0 0"><strong>אנא השיבו עם מידע נוסף ונחזור עם סיווג.</strong></p>
    </div>'''


def _build_low_confidence_banner(avg_confidence, classified, total):
    """HTML warning banner for low average confidence."""
    return f'''<div style="background:#fff3cd;border:2px solid #ffc107;border-radius:5px;padding:15px;margin-bottom:20px">
        <h3 style="color:#856404;margin:0">⚠️ רמת ודאות נמוכה ({avg_confidence:.0f}%)</h3>
        <p style="color:#856404;margin:10px 0 0 0">סווגו {classified} מתוך {total} פריטים, אך רמת הוודאות הממוצעת נמוכה.
        מומלץ לבדוק את הסיווגים לפני שימוש. ייתכן שנדרש מידע נוסף על המוצרים.</p>
    </div>'''


def build_classification_email(results, sender_name, invoice_validation=None, tracking_code=None, invoice_data=None, enriched_items=None, original_email_body=None):
    """Build HTML email report - renders pre-computed data from agents + intelligence."""
    classifications = results.get("agents", {}).get("classification", {}).get("classifications", [])
    regulatory = results.get("agents", {}).get("regulatory", {}).get("regulatory", [])
    fta = results.get("agents", {}).get("fta", {}).get("fta", [])
    risk = results.get("agents", {}).get("risk", {}).get("risk", {})
    synthesis = results.get("synthesis", "")
    # Rich data from Firestore lookups (bypasses weak AI agent guesses)
    ministry_routing = results.get("ministry_routing", {})
    intelligence = results.get("intelligence", {})
    free_import_order = results.get("free_import_order", {})
    
    # Session 11: Generate tracking code if not provided
    if not tracking_code:
        tracking_code = generate_tracking_code()
    
    # --- Modern email template ---
    html = f'''<div style="font-family:'Segoe UI',Arial,Helvetica,sans-serif;max-width:680px;margin:0 auto;direction:rtl;background:#f0f2f5;padding:0">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#0f2439 0%,#1a3a5c 50%,#245a8a 100%);color:#fff;padding:32px 30px 28px;border-radius:12px 12px 0 0">
        <table style="width:100%" cellpadding="0" cellspacing="0"><tr>
            <td style="vertical-align:middle">
                <h1 style="margin:0;font-size:22px;font-weight:700;letter-spacing:0.3px">דו״ח סיווג מכס</h1>
                <p style="margin:6px 0 0 0;font-size:14px;opacity:0.85;font-weight:400">נוצר אוטומטית ע״י מערכת RCB</p>
            </td>
            <td style="text-align:left;vertical-align:middle">
                <div style="background:rgba(255,255,255,0.15);border-radius:8px;padding:8px 14px;display:inline-block">
                    <span style="font-size:10px;opacity:0.7;display:block;text-align:center;font-family:'Courier New',monospace">TRACKING</span>
                    <span style="font-size:13px;font-family:'Courier New',monospace;font-weight:600;letter-spacing:1px">{tracking_code}</span>
                </div>
            </td>
        </tr></table>
    </div>

    <!-- Body -->
    <div style="background:#ffffff;padding:28px 30px;border-left:1px solid #e0e0e0;border-right:1px solid #e0e0e0">'''

    # Session 11: Shipment info card
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

        html += f'''<div style="background:#f8faff;border:1px solid #d4e3f5;border-radius:10px;padding:18px 20px;margin-bottom:22px">
            <div style="font-size:13px;font-weight:700;color:#1a3a5c;margin-bottom:12px;text-transform:uppercase;letter-spacing:0.5px">פרטי משלוח</div>
            <table style="width:100%;font-size:14px;color:#333" cellpadding="0" cellspacing="0">
                <tr>
                    <td style="padding:5px 0;width:50%"><span style="color:#888;font-size:12px">כיוון</span><br><strong>{direction_text}</strong></td>
                    <td style="padding:5px 0;width:50%"><span style="color:#888;font-size:12px">הובלה</span><br><strong>{freight_text}</strong></td>
                </tr>
                <tr>
                    <td style="padding:5px 0"><span style="color:#888;font-size:12px">מוכר</span><br><strong>{seller}</strong></td>
                    <td style="padding:5px 0"><span style="color:#888;font-size:12px">קונה</span><br><strong>{buyer}</strong></td>
                </tr>
                <tr>
                    <td colspan="2" style="padding:5px 0"><span style="color:#888;font-size:12px">מס׳ משלוח</span><br><strong style="font-family:'Courier New',monospace">{ref}</strong></td>
                </tr>
            </table>
        </div>'''

    # Session 10: Invoice validation
    if invoice_validation:
        score = invoice_validation.get('score', 0)
        is_valid = invoice_validation.get('is_valid', False)
        missing = invoice_validation.get('missing_fields', [])
        bar_color = "#22c55e" if is_valid else "#f59e0b"
        bar_bg = "#dcfce7" if is_valid else "#fef3c7"
        text_color = "#166534" if is_valid else "#92400e"
        icon = "✅" if is_valid else "⚠️"
        label = "חשבון תקין" if is_valid else "חשבון חלקי"

        html += f'''<div style="background:{bar_bg};border-radius:10px;padding:18px 20px;margin-bottom:22px;border:1px solid {bar_color}33">
            <table style="width:100%" cellpadding="0" cellspacing="0"><tr>
                <td style="vertical-align:middle">
                    <span style="font-size:16px;font-weight:700;color:{text_color}">{icon} {label}</span>
                </td>
                <td style="text-align:left;vertical-align:middle;width:160px">
                    <div style="font-size:11px;color:{text_color};margin-bottom:4px;text-align:left">ציון: {score}/100</div>
                    <div style="background:#fff;border-radius:20px;height:8px;overflow:hidden">
                        <div style="background:{bar_color};height:100%;width:{score}%;border-radius:20px"></div>
                    </div>
                </td>
            </tr></table>'''
        if is_valid:
            html += f'<p style="color:{text_color};margin:10px 0 0 0;font-size:13px">המסמכים מכילים את כל המידע הנדרש לפי תקנות המכס.</p>'
        else:
            html += f'<p style="color:{text_color};margin:10px 0 0 0;font-size:13px">חסרים {len(missing)} שדות בהתאם לתקנות (מס\' 2) תשל"ג-1972:</p>'
            html += f'<div style="margin-top:8px">'
            for field in missing[:5]:
                html += f'<span style="display:inline-block;background:#fff;border:1px solid {bar_color}66;border-radius:20px;padding:3px 12px;margin:3px;font-size:12px;color:{text_color}">{field}</span>'
            html += '</div>'
        html += '</div>'

    # Quality Gate: Inject warning banner if present
    audit_banner = results.get("audit", {}).get("warning_banner", "")
    if audit_banner:
        html += audit_banner

    # Session 14: Synthesis
    if LANGUAGE_TOOLS_AVAILABLE:
        try:
            synthesis = _lang_checker.fix_all(synthesis)
        except Exception:
            pass
    html += f'''<div style="background:#f8faff;padding:18px 20px;border-radius:10px;border-right:4px solid #1a3a5c;margin-bottom:28px;font-size:14px;line-height:1.7;color:#333">{synthesis}</div>'''

    # Classifications header
    html += '''<div style="margin-bottom:14px">
        <span style="font-size:17px;font-weight:700;color:#0f2439">סיווגים</span>
        <div style="height:3px;width:50px;background:linear-gradient(90deg,#1a3a5c,#245a8a);border-radius:2px;margin-top:6px"></div>
    </div>'''

    # Classification cards — use enriched_items when available, fallback to classifications
    card_items = enriched_items if enriched_items else classifications
    _using_enriched = bool(enriched_items)

    for c in card_items:
        conf = c.get("confidence", "בינונית")
        if conf == "גבוהה":
            conf_color = "#22c55e"
            conf_bg = "#dcfce7"
            conf_width = "100"
        elif conf == "בינונית":
            conf_color = "#f59e0b"
            conf_bg = "#fef3c7"
            conf_width = "66"
        else:
            conf_color = "#ef4444"
            conf_bg = "#fee2e2"
            conf_width = "33"

        hs_display = get_israeli_hs_format(c.get("hs_code", ""))
        hs_note = ""
        v_status = c.get('verification_status', '')
        if c.get('hs_corrected'):
            hs_note = f'<span style="color:#92400e;font-size:11px;background:#fef3c7;padding:2px 8px;border-radius:10px;margin-right:6px">⚠️ תוקן מ-{get_israeli_hs_format(c.get("original_hs_code", ""))}</span>'
        elif v_status == 'official':
            hs_note = '<span style="color:#166534;font-size:11px;background:#dcfce7;padding:2px 8px;border-radius:10px;margin-right:6px">✅ אומת רשמית</span>'
        elif v_status == 'verified':
            hs_note = '<span style="color:#166534;font-size:11px;background:#dcfce7;padding:2px 8px;border-radius:10px;margin-right:6px">✅ אומת</span>'
        elif c.get('hs_warning'):
            hs_note = '<span style="color:#991b1b;font-size:11px;background:#fee2e2;padding:2px 8px;border-radius:10px;margin-right:6px">⚠️ לא אומת</span>'
        elif c.get('hs_validated') and c.get('hs_exact_match'):
            hs_note = '<span style="color:#166534;font-size:11px;background:#dcfce7;padding:2px 8px;border-radius:10px;margin-right:6px">✅ אומת</span>'

        pt = c.get("purchase_tax", {})
        if isinstance(pt, dict) and pt.get("applies"):
            pt_display = pt.get("rate_he", "חל")
            pt_note = pt.get("note_he", "")
            pt_html = f'{pt_display}'
            if pt_note:
                pt_html += f'<br><span style="color:#888;font-size:11px">{pt_note[:30]}</span>'
        else:
            pt_html = '<span style="color:#aaa">לא חל</span>'

        vat_display = c.get("vat_rate", "18%")

        # Invoice line data (from _link_invoice_to_classifications)
        line_num = c.get("line_number", 0)
        inv_desc = c.get("invoice_description", "")
        qty = c.get("quantity", "")
        unit_px = c.get("unit_price", "")
        item_origin = c.get("origin_country", "")
        tariff_text = c.get("tariff_text_he", "") or c.get("official_description_he", "")
        line_label = f'שורה {line_num}' if line_num else ''
        qty_price = f'{qty} \u00d7 ${unit_px}' if qty and unit_px else (str(qty) if qty else '')

        html += '<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;margin-bottom:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.04)">'
        html += '<div style="background:#f8faff;padding:14px 18px;border-bottom:1px solid #e5e7eb">'
        html += '<table style="width:100%" cellpadding="0" cellspacing="0"><tr><td style="vertical-align:middle">'
        if line_label:
            html += f'<span style="background:#1a3a5c;color:#fff;font-size:11px;font-weight:700;padding:2px 10px;border-radius:10px;margin-left:8px">{line_label}</span>'
        html += f'<span style="font-size:15px;font-weight:700;color:#0f2439">{c.get("item", "")[:50]}</span></td>'
        if qty_price:
            html += f'<td style="text-align:left;vertical-align:middle"><span style="font-size:13px;color:#555;font-family:\'Courier New\',monospace">{qty_price}</span></td>'
        html += '</tr></table>'
        if inv_desc and inv_desc.lower().strip() != (c.get("item", "") or "").lower().strip():
            html += f'<div style="font-size:12px;color:#888;margin-top:6px">חשבונית: {inv_desc[:80]}</div>'
        if item_origin:
            html += f'<div style="font-size:12px;color:#888;margin-top:3px">מקור: {item_origin}</div>'
        # Seller/Buyer row (enriched items)
        if _using_enriched:
            _seller = c.get("seller", "")
            _buyer = c.get("buyer", "")
            if _seller or _buyer:
                parts = []
                if _seller:
                    parts.append(f'<span style="color:#888">מוכר:</span> {_seller}')
                if _buyer:
                    parts.append(f'<span style="color:#888">קונה:</span> {_buyer}')
                html += f'<div style="font-size:12px;color:#555;margin-top:3px">{" &nbsp;|&nbsp; ".join(parts)}</div>'
        html += '</div><div style="padding:16px 18px">'
        html += '<div style="margin-bottom:14px">'
        html += f'<span style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px">קוד HS</span><br>'
        html += f'<span style="font-family:\'Courier New\',monospace;font-size:18px;font-weight:700;color:#1a3a5c;letter-spacing:0.5px">{hs_display}</span> {hs_note}'
        if tariff_text:
            html += f'<div style="font-size:12px;color:#555;margin-top:4px;line-height:1.4;font-style:italic">{tariff_text[:120]}</div>'
        html += '</div>'
        html += f'''<!-- Taxes grid -->
                <table style="width:100%;border-collapse:collapse" cellpadding="0" cellspacing="0">
                    <tr>
                        <td style="padding:8px 0;width:33%;border-top:1px solid #f0f0f0">
                            <span style="font-size:11px;color:#888">מכס</span><br>
                            <strong style="font-size:15px;color:#0f2439">{c.get("duty_rate", "")}</strong>
                        </td>
                        <td style="padding:8px 0;width:33%;border-top:1px solid #f0f0f0">
                            <span style="font-size:11px;color:#888">מס קנייה</span><br>
                            <span style="font-size:14px;color:#333">{pt_html}</span>
                        </td>
                        <td style="padding:8px 0;width:33%;border-top:1px solid #f0f0f0">
                            <span style="font-size:11px;color:#888">מע״מ</span><br>
                            <strong style="font-size:15px;color:#0f2439">{vat_display}</strong>
                        </td>
                    </tr>
                </table>
                <!-- Confidence bar -->
                <div style="margin-top:12px;padding-top:12px;border-top:1px solid #f0f0f0">
                    <table style="width:100%" cellpadding="0" cellspacing="0"><tr>
                        <td style="font-size:11px;color:#888;vertical-align:middle">ודאות</td>
                        <td style="width:60%;vertical-align:middle;padding:0 10px">
                            <div style="background:#f0f0f0;border-radius:20px;height:8px;overflow:hidden">
                                <div style="background:{conf_color};height:100%;width:{conf_width}%;border-radius:20px"></div>
                            </div>
                        </td>
                        <td style="font-size:12px;font-weight:700;color:{conf_color};vertical-align:middle;text-align:left">{conf}</td>
                    </tr></table>
                </div>'''

        # ── Per-item ministry approvals + FTA (enriched only) ──
        if _using_enriched:
            item_ministries = c.get("ministries", [])
            if item_ministries:
                html += '<div style="margin-top:12px;padding-top:12px;border-top:1px solid #f0f0f0">'
                html += '<span style="font-size:11px;color:#888">אישורי משרדים נדרשים</span><br>'
                for m in item_ministries:
                    m_name = m.get("name_he", m.get("name", ""))
                    m_docs = ", ".join((m.get("documents_he") or m.get("documents") or [])[:3])
                    html += f'<span style="display:inline-block;background:#eff6ff;border:1px solid #bfdbfe;border-radius:20px;padding:4px 12px;margin:3px;font-size:12px;color:#1e40af">{m_name}</span>'
                    if m_docs:
                        html += f'<div style="font-size:11px;color:#666;margin:2px 0 4px 14px">{m_docs[:80]}</div>'
                html += '</div>'

            item_fta = c.get("fta")
            if item_fta and item_fta.get("eligible"):
                agreement = item_fta.get("agreement", item_fta.get("agreement_name", ""))
                pref_rate = item_fta.get("preferential", item_fta.get("preferential_rate", ""))
                origin_proof = item_fta.get("origin_proof", item_fta.get("documents_needed", ""))
                html += f'<div style="margin-top:8px;padding:8px 12px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;font-size:12px">'
                html += f'<strong style="color:#166534">FTA:</strong> {agreement} '
                html += f'<span style="color:#166534;font-weight:700">מכס מופחת {pref_rate}</span>'
                if origin_proof:
                    html += f' <span style="color:#555">| תעודה: {origin_proof}</span>'
                html += '</div>'

        html += '''
            </div>
        </div>'''
    # end classification cards

    # Regulatory: prefer ministry_routing (Firestore data) over AI agent guesses
    has_routing = bool(ministry_routing)
    if has_routing:
        html += '''<div style="margin:28px 0 14px">
            <span style="font-size:17px;font-weight:700;color:#0f2439">רגולציה ואישורים</span>
            <div style="height:3px;width:50px;background:linear-gradient(90deg,#1a3a5c,#245a8a);border-radius:2px;margin-top:6px"></div>
        </div>'''
        for hs_code, routing in ministry_routing.items():
            if not routing.get("ministries"):
                continue
            summary = routing.get("summary_he", "")
            html += f'<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:16px 18px;margin-bottom:10px">'
            html += f'<div style="font-family:\'Courier New\',monospace;font-weight:700;color:#1a3a5c;margin-bottom:10px">{get_israeli_hs_format(hs_code)}</div>'
            if summary:
                html += f'<div style="font-size:13px;color:#555;margin-bottom:12px">{summary[:150]}</div>'
            for m in routing.get("ministries", []):
                official_badge = '<span style="color:#166534;font-size:10px;background:#dcfce7;padding:1px 6px;border-radius:8px;margin-right:4px">API</span>' if m.get("official") else ''
                html += f'<div style="background:#f8faff;border:1px solid #e5e7eb;border-radius:8px;padding:10px 14px;margin-bottom:8px">'
                html += f'<div style="font-weight:700;color:#1e40af;font-size:13px">{official_badge}{m.get("name_he", m.get("name", ""))}</div>'
                docs = m.get("documents_he", [])
                if docs:
                    html += '<div style="margin-top:6px">'
                    for d in docs[:4]:
                        html += f'<span style="display:inline-block;background:#eff6ff;border:1px solid #bfdbfe;border-radius:20px;padding:3px 10px;margin:2px;font-size:11px;color:#1e40af">{d}</span>'
                    html += '</div>'
                proc = m.get("procedure", "")
                if proc:
                    html += f'<div style="font-size:11px;color:#888;margin-top:4px">{proc[:100]}</div>'
                url = m.get("url", "")
                if url:
                    html += f'<div style="font-size:11px;margin-top:4px"><a href="{url}" style="color:#2563eb;text-decoration:none">אתר המשרד &larr;</a></div>'
                html += '</div>'
            html += '</div>'
    elif regulatory:
        # Fallback to AI agent output
        html += '''<div style="margin:28px 0 14px">
            <span style="font-size:17px;font-weight:700;color:#0f2439">רגולציה</span>
            <div style="height:3px;width:50px;background:linear-gradient(90deg,#1a3a5c,#245a8a);border-radius:2px;margin-top:6px"></div>
        </div>'''
        for r in regulatory:
            ministries_html = ""
            for m in r.get("ministries", []):
                if m.get("required"):
                    ministries_html += f'<span style="display:inline-block;background:#eff6ff;border:1px solid #bfdbfe;border-radius:20px;padding:4px 12px;margin:3px;font-size:12px;color:#1e40af">{m.get("name")} — {m.get("regulation", "")}</span>'
            if ministries_html:
                html += f'<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:14px 18px;margin-bottom:10px">'
                html += f'<div style="font-family:\'Courier New\',monospace;font-weight:700;color:#1a3a5c;margin-bottom:8px">{get_israeli_hs_format(r.get("hs_code", ""))}</div>'
                html += f'{ministries_html}</div>'

    # FTA: prefer intelligence FTA data (Firestore lookup) over AI agent guesses
    intel_fta_list = []
    if intelligence:
        for k, v in intelligence.items():
            if isinstance(v, dict):
                fta_data = v.get("fta")
                if isinstance(fta_data, dict) and fta_data.get("eligible"):
                    intel_fta_list.append(fta_data)

    if intel_fta_list:
        html += '''<div style="margin:28px 0 14px">
            <span style="font-size:17px;font-weight:700;color:#166534">הטבות סחר (FTA)</span>
            <div style="height:3px;width:50px;background:linear-gradient(90deg,#22c55e,#16a34a);border-radius:2px;margin-top:6px"></div>
        </div>'''
        for ft in intel_fta_list:
            agreement = ft.get("agreement_name_he") or ft.get("agreement_name", "")
            pref_rate = ft.get("preferential_rate", "")
            origin_proof = ft.get("origin_proof", "")
            origin_alt = ft.get("origin_proof_alt", "")
            cumulation = ft.get("cumulation", "")
            legal = ft.get("legal_basis", "")
            country = ft.get("origin_country", "")

            html += '<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:16px 18px;margin-bottom:10px">'
            html += f'<table style="width:100%" cellpadding="0" cellspacing="0"><tr>'
            html += f'<td style="vertical-align:middle"><strong style="color:#166534;font-size:14px">{country}</strong>'
            html += f'<span style="color:#555;font-size:13px"> — {agreement}</span></td>'
            if pref_rate:
                html += f'<td style="text-align:left;vertical-align:middle"><span style="background:#22c55e;color:#fff;font-weight:700;padding:4px 14px;border-radius:20px;font-size:13px">מכס {pref_rate}</span></td>'
            html += '</tr></table>'
            # Details row
            details = []
            if origin_proof:
                details.append(f'הוכחת מקור: <strong>{origin_proof}</strong>')
            if origin_alt:
                details.append(f'חלופה: {origin_alt}')
            if cumulation:
                details.append(f'צבירה: {cumulation}')
            if legal:
                details.append(f'בסיס משפטי: {legal}')
            if details:
                html += '<div style="margin-top:10px;padding-top:10px;border-top:1px solid #bbf7d0">'
                for d in details:
                    html += f'<div style="font-size:12px;color:#555;margin-bottom:3px">{d}</div>'
                html += '</div>'
            html += '</div>'
    elif [f for f in fta if f.get("eligible")]:
        # Fallback to AI agent output
        html += '''<div style="margin:28px 0 14px">
            <span style="font-size:17px;font-weight:700;color:#166534">הטבות FTA</span>
            <div style="height:3px;width:50px;background:linear-gradient(90deg,#22c55e,#16a34a);border-radius:2px;margin-top:6px"></div>
        </div>'''
        for f in fta:
            if f.get("eligible"):
                html += f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:14px 18px;margin-bottom:10px">'
                html += f'<table style="width:100%" cellpadding="0" cellspacing="0"><tr>'
                html += f'<td style="vertical-align:middle"><strong style="color:#166534">{f.get("country", "")}</strong><span style="color:#555;font-size:13px"> — {f.get("agreement", "")}</span></td>'
                html += f'<td style="text-align:left;vertical-align:middle"><span style="background:#22c55e;color:#fff;font-weight:700;padding:4px 14px;border-radius:20px;font-size:13px">מכס {f.get("preferential", "")}</span></td>'
                html += '</tr></table></div>'

    if risk.get("level") in ["גבוה", "בינוני"]:
        risk_color = "#ef4444" if risk.get("level") == "גבוה" else "#f59e0b"
        risk_bg = "#fef2f2" if risk.get("level") == "גבוה" else "#fffbeb"
        risk_border = "#fca5a5" if risk.get("level") == "גבוה" else "#fde68a"
        html += f'''<div style="margin:28px 0 14px">
            <span style="font-size:17px;font-weight:700;color:{risk_color}">סיכון: {risk.get("level", "")}</span>
            <div style="height:3px;width:50px;background:{risk_color};border-radius:2px;margin-top:6px"></div>
        </div>'''
        for i in risk.get("items", []):
            html += f'''<div style="background:{risk_bg};border:1px solid {risk_border};border-radius:10px;padding:14px 18px;margin-bottom:10px">
                <strong style="color:#333">{i.get("item", "")}</strong>
                <p style="margin:6px 0 0;color:#555;font-size:13px">{i.get("issue", "")}</p>
            </div>'''

    # Phase E: Smart questions section
    smart_q = results.get("smart_questions", [])
    if smart_q and SMART_QUESTIONS_AVAILABLE:
        try:
            item_desc = ""
            if classifications:
                item_desc = classifications[0].get("item", "")
            questions_html = format_questions_html(smart_q, item_description=item_desc)
            if questions_html:
                html += questions_html
        except Exception:
            pass

    # Original email quoting
    if original_email_body and len(original_email_body.strip()) > 10:
        import html as html_mod
        quoted = html_mod.escape(original_email_body.strip())
        if len(quoted) > 2000:
            quoted = quoted[:2000] + "..."
        html += f'''<div style="margin-top:28px;padding-top:20px;border-top:2px solid #e0e0e0">
            <div style="font-size:12px;color:#888;margin-bottom:8px">הודעה מקורית:</div>
            <blockquote style="margin:0;padding:12px 16px;border-right:3px solid #ccc;background:#f9f9f9;border-radius:4px;font-size:13px;color:#555;white-space:pre-wrap;direction:rtl">{quoted}</blockquote>
        </div>'''

    # Footer
    html += '''</div>
    <!-- Footer -->
    <div style="background:#f8faff;padding:24px 30px;border-top:1px solid #e0e0e0;border-radius:0 0 12px 12px;border-left:1px solid #e0e0e0;border-right:1px solid #e0e0e0">
        <table style="width:100%" cellpadding="0" cellspacing="0"><tr>
            <td style="vertical-align:middle;width:60px">
                <img src="https://rpa-port.com/wp-content/uploads/2016/09/logo.png" style="width:50px;border-radius:8px" alt="RPA PORT">
            </td>
            <td style="vertical-align:middle;border-right:3px solid #1a3a5c;padding-right:16px">
                <strong style="color:#0f2439;font-size:14px">RCB — AI Customs Broker</strong><br>
                <span style="color:#666;font-size:12px">R.P.A. PORT LTD</span>
                <span style="color:#ccc;margin:0 6px">|</span>
                <span style="color:#1a3a5c;font-size:12px">rcb@rpa-port.co.il</span>
            </td>
        </tr></table>
        <p style="font-size:10px;color:#aaa;margin:16px 0 0 0;line-height:1.5;border-top:1px solid #e8e8e8;padding-top:12px">⚠️ המלצה ראשונית בלבד. יש לאמת עם עמיל מכס מוסמך. דו״ח זה הופק באופן אוטומטי ואינו מהווה ייעוץ רשמי.</p>
    </div>
    </div>'''
    return html

def build_excel_report(results, enriched_items=None):
    """Build Excel report with enriched item data when available."""
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
        header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")

        if enriched_items:
            # Enhanced columns
            headers = ["שורה", "תיאור פריט", "מוכר", "קונה", "כמות", "מחיר ליחידה",
                        "ארץ מקור", "קוד HS", "תיאור תעריף", "מכס", "מס קנייה",
                        "מע\"מ", "ודאות", "סטטוס אימות", "משרדים נדרשים", "נימוק"]
            for i, h in enumerate(headers, 1):
                cell = ws2.cell(1, i, h)
                cell.font = header_font
                cell.fill = header_fill
            for row, c in enumerate(enriched_items, 2):
                ws2.cell(row, 1, c.get("line_number", ""))
                ws2.cell(row, 2, c.get("description", ""))
                ws2.cell(row, 3, c.get("seller", ""))
                ws2.cell(row, 4, c.get("buyer", ""))
                ws2.cell(row, 5, c.get("quantity", ""))
                ws2.cell(row, 6, c.get("unit_price", ""))
                ws2.cell(row, 7, c.get("origin_country", ""))
                ws2.cell(row, 8, get_israeli_hs_format(c.get("hs_code", "")))
                ws2.cell(row, 9, c.get("tariff_text_he", ""))
                ws2.cell(row, 10, c.get("duty_rate", ""))
                ws2.cell(row, 11, c.get("purchase_tax_display", "לא חל"))
                ws2.cell(row, 12, c.get("vat_rate", "18%"))
                ws2.cell(row, 13, c.get("confidence", ""))
                v_status = c.get('verification_status', '')
                if v_status == 'official':
                    validation_status = "אומת רשמית"
                elif v_status == 'verified':
                    validation_status = "אומת"
                elif c.get('hs_corrected'):
                    validation_status = f"תוקן מ-{get_israeli_hs_format(c.get('original_hs_code', ''))}"
                else:
                    validation_status = v_status
                ws2.cell(row, 14, validation_status)
                # Ministries
                ministries = c.get("ministries", [])
                ministry_names = ", ".join(m.get("name_he", m.get("name", "")) for m in ministries) if ministries else ""
                ws2.cell(row, 15, ministry_names)
                ws2.cell(row, 16, c.get("reasoning", ""))
        else:
            # Fallback: original 8-column format
            headers = ["פריט", "קוד HS", "מכס", "מס קנייה", "מע\"מ", "ודאות", "סטטוס אימות", "נימוק"]
            for i, h in enumerate(headers, 1):
                ws2.cell(1, i, h).font = Font(bold=True)
            for row, c in enumerate(results.get("agents", {}).get("classification", {}).get("classifications", []), 2):
                ws2.cell(row, 1, c.get("item", ""))
                ws2.cell(row, 2, get_israeli_hs_format(c.get("hs_code", "")))
                ws2.cell(row, 3, c.get("duty_rate", ""))
                pt = c.get("purchase_tax", {})
                pt_text = pt.get("rate_he", "לא חל") if isinstance(pt, dict) else "לא חל"
                ws2.cell(row, 4, pt_text)
                ws2.cell(row, 5, c.get("vat_rate", "18%"))
                ws2.cell(row, 6, c.get("confidence", ""))
                v_status = c.get('verification_status', '')
                if v_status == 'official':
                    validation_status = "אומת רשמית ✓"
                elif v_status == 'verified':
                    validation_status = "אומת ✓"
                elif c.get('hs_corrected'):
                    validation_status = f"תוקן מ-{get_israeli_hs_format(c.get('original_hs_code', ''))}"
                elif c.get('hs_warning'):
                    validation_status = "לא נמצא במאגר"
                elif c.get('hs_validated') and c.get('hs_exact_match'):
                    validation_status = "אומת ✓"
                elif c.get('hs_validated'):
                    validation_status = "התאמה חלקית"
                else:
                    validation_status = ""
                ws2.cell(row, 7, validation_status)
                ws2.cell(row, 8, c.get("reasoning", ""))

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


# ═══════════════════════════════════════════════════════════════
#  EMAIL ENRICHMENT: Merge invoice items + classifications + tariff
# ═══════════════════════════════════════════════════════════════

def _lookup_tariff_text(db, hs_code):
    """Fallback: look up tariff description from Firestore for a specific HS code."""
    if not db or not hs_code:
        return "", ""
    hs_clean = str(hs_code).replace(".", "").replace(" ", "").replace("/", "")
    for coll_name in ["tariff", "tariff_chapters"]:
        try:
            candidates = [hs_clean]
            if len(hs_clean) >= 6:
                candidates.append(f"{hs_clean[:4]}.{hs_clean[4:6]}.{hs_clean[6:]}")
            if len(hs_clean) >= 4:
                candidates.append(hs_clean[:4])
            for doc_id in candidates:
                doc = db.collection(coll_name).document(doc_id).get()
                if doc.exists:
                    data = doc.to_dict()
                    return (
                        data.get("description_he", data.get("title_he", "")),
                        data.get("description_en", data.get("title_en", ""))
                    )
        except Exception:
            continue
    return "", ""


def _enrich_results_for_email(results, invoice_data, db):
    """Merge invoice items (Agent 1) with classifications (Agent 2) by index.
    Add tariff text, ministry routing, and FTA data per item."""
    invoice_items = results.get("agents", {}).get("invoice", {}).get("items", [])
    if not invoice_items and isinstance(invoice_data, dict):
        invoice_items = invoice_data.get("items", [])
    classifications = results.get("agents", {}).get("classification", {}).get("classifications", [])
    ministry_routing = results.get("ministry_routing", {})
    fta_data = results.get("agents", {}).get("fta", {}).get("fta", [])
    free_import = results.get("free_import_order", {})

    seller = (invoice_data or {}).get("seller", "")
    buyer = (invoice_data or {}).get("buyer", "")

    enriched = []
    count = max(len(invoice_items), len(classifications))
    if count == 0:
        return enriched

    for idx in range(count):
        inv = invoice_items[idx] if idx < len(invoice_items) and isinstance(invoice_items[idx], dict) else {}
        cls = classifications[idx] if idx < len(classifications) and isinstance(classifications[idx], dict) else {}

        hs_code = cls.get("hs_code", "")

        # Tariff text: prefer verification loop data, fallback Firestore lookup
        tariff_he = cls.get("official_description_he", "")
        tariff_en = cls.get("official_description_en", "")
        if not tariff_he and hs_code and db:
            try:
                tariff_he, tariff_en = _lookup_tariff_text(db, hs_code)
            except Exception:
                pass

        # Ministry routing for this HS code
        ministries = []
        routing = ministry_routing.get(hs_code, {})
        if isinstance(routing, dict):
            ministries = routing.get("ministries", [])

        # FTA match by origin country
        origin = inv.get("origin_country", "")
        item_fta = None
        for f in fta_data:
            if not f.get("eligible"):
                continue
            f_country = (f.get("country", "") or "").lower()
            if origin and (f_country == origin.lower() or f_country in origin.lower()):
                item_fta = f
                break

        # Purchase tax display
        pt = cls.get("purchase_tax", {})
        if isinstance(pt, dict) and pt.get("applies"):
            pt_display = pt.get("rate_he", pt.get("rate", "חל"))
        elif isinstance(pt, str):
            pt_display = pt
        else:
            pt_display = "לא חל"

        enriched.append({
            "line_number": idx + 1,
            "description": inv.get("description", cls.get("item", "")),
            "quantity": inv.get("quantity", ""),
            "unit_price": inv.get("unit_price", ""),
            "total": inv.get("total", ""),
            "origin_country": origin,
            "seller": seller,
            "buyer": buyer,
            "hs_code": hs_code,
            "tariff_text_he": tariff_he,
            "tariff_text_en": tariff_en,
            "duty_rate": cls.get("duty_rate", ""),
            "purchase_tax": pt,
            "purchase_tax_display": pt_display,
            "vat_rate": cls.get("vat_rate", "18%"),
            "confidence": cls.get("confidence", ""),
            "reasoning": cls.get("reasoning", ""),
            "verification_status": cls.get("verification_status", ""),
            "hs_corrected": cls.get("hs_corrected", False),
            "original_hs_code": cls.get("original_hs_code", ""),
            "hs_warning": cls.get("hs_warning", ""),
            "hs_validated": cls.get("hs_validated", False),
            "hs_exact_match": cls.get("hs_exact_match", False),
            "ministries": ministries,
            "fta": item_fta,
        })

    return enriched


# =============================================================================
# PRE-CLASSIFY BYPASS: Skip AI pipeline for high-confidence known products
# =============================================================================

def _try_pre_classify_bypass(db, doc_text, gemini_key=None):
    """
    Attempt to classify using ONLY pre_classify (Firestore lookups, zero AI).
    Returns a full result dict (same format as run_full_classification) or None.

    Only succeeds when:
    - PRE_CLASSIFY_BYPASS_ENABLED is True
    - pre_classify returns a candidate with confidence >= PRE_CLASSIFY_BYPASS_THRESHOLD
    - The top candidate has a valid HS code
    """
    if not PRE_CLASSIFY_BYPASS_ENABLED or not INTELLIGENCE_AVAILABLE:
        return None

    # We need a minimal invoice extraction first (Gemini Flash — cheap)
    print("  [BYPASS] Checking pre-classify bypass...")
    invoice = run_document_agent(None, doc_text, gemini_key=gemini_key)
    if not isinstance(invoice, dict):
        invoice = {"items": [{"description": doc_text[:500]}]}
    items = invoice.get("items") or [{"description": doc_text[:500]}]
    if not isinstance(items, list):
        items = [{"description": doc_text[:500]}]

    origin = items[0].get("origin_country", "") if items and isinstance(items[0], dict) else ""
    seller_name = invoice.get("seller", "")

    # Run pre_classify on first item
    best_candidate = None
    best_pc_result = None
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        desc = item.get("description", "")
        if not desc or not _is_product_description(desc):
            continue
        item_origin = item.get("origin_country", origin)
        pc_result = pre_classify(db, desc, item_origin, seller_name=seller_name)
        if not isinstance(pc_result, dict):
            continue
        candidates = pc_result.get("candidates", [])
        if candidates and candidates[0].get("confidence", 0) >= PRE_CLASSIFY_BYPASS_THRESHOLD:
            top = candidates[0]
            hs = str(top.get("hs_code", "")).replace(".", "").replace("/", "").replace(" ", "")
            if _is_valid_hs(hs):
                if not best_candidate or top["confidence"] > best_candidate["confidence"]:
                    best_candidate = top
                    best_pc_result = pc_result

    if not best_candidate:
        print("  [BYPASS] No high-confidence match — proceeding to AI pipeline")
        return None

    hs_code = best_candidate["hs_code"]
    confidence = best_candidate["confidence"]
    source = best_candidate.get("source", "unknown")
    print(f"  [BYPASS] HIGH-CONFIDENCE MATCH: HS {hs_code} ({confidence}% from {source})")
    print(f"  [BYPASS] Skipping 6-agent AI pipeline — $0.00 AI cost")

    # Build classifications in the standard format
    classifications = []
    for item in items[:10]:
        if not isinstance(item, dict):
            continue
        desc = item.get("description", "")
        classifications.append({
            "item": desc[:100],
            "item_description": desc,
            "hs_code": hs_code,
            "confidence": "גבוהה",
            "reasoning": f"Pre-classify bypass ({source}, {confidence}% confidence)",
            "reasoning_he": f"סיווג מהיר ממאגר הידע ({source}, {confidence}% ביטחון)",
            "hs_description": best_candidate.get("description", ""),
            "duty_rate": best_candidate.get("duty_rate", ""),
        })

    # Validate HS codes
    validated = validate_and_correct_classifications(db, classifications)

    # Free Import Order
    free_import_results = {}
    if INTELLIGENCE_AVAILABLE:
        try:
            fio = query_free_import_order(db, hs_code)
            if fio.get("found"):
                free_import_results[hs_code] = fio
        except Exception:
            pass

    # Ministry routing
    ministry_routing = {}
    if INTELLIGENCE_AVAILABLE:
        try:
            routing = route_to_ministries(db, hs_code, free_import_results.get(hs_code))
            if routing.get("ministries"):
                ministry_routing[hs_code] = routing
        except Exception:
            pass

    # Verification
    if VERIFICATION_AVAILABLE:
        try:
            validated = verify_all_classifications(db, validated, free_import_results=free_import_results)
            for c in validated:
                if c.get("verification_status") in ("official", "verified"):
                    learn_from_verification(db, c)
        except Exception:
            pass

    # Build synthesis from pre-classify data
    synthesis = (
        f"סיווג מהיר: המערכת זיהתה את המוצר ממאגר הידע הפנימי "
        f"(מקור: {source}, רמת ביטחון: {confidence}%). "
        f"קוד HS: {hs_code}."
    )
    if best_candidate.get("duty_rate"):
        synthesis += f" שיעור מכס: {best_candidate['duty_rate']}."
    if free_import_results:
        synthesis += " נבדק מול צו יבוא חופשי."

    all_results = {
        "invoice": invoice,
        "classification": {"classifications": validated},
        "regulatory": {"regulatory": best_pc_result.get("regulatory", [])},
        "fta": {"fta": [best_pc_result.get("fta")] if best_pc_result.get("fta") else []},
        "risk": {"risk": {"level": "נמוך", "items": []}},
    }

    return {
        "success": True,
        "agents": all_results,
        "synthesis": synthesis,
        "invoice_data": invoice,
        "intelligence": {"bypass": best_pc_result},
        "document_validation": None,
        "free_import_order": free_import_results,
        "ministry_routing": ministry_routing,
        "parsed_documents": [],
        "smart_questions": [],
        "ambiguity": {},
        "tracker": None,
        "audit": {"action": "send", "classifications": validated, "warning_banner": None, "avg_confidence": confidence},
        "_engine": "pre_classify_bypass",
        "_bypass_confidence": confidence,
        "_bypass_source": source,
        "_cost": 0.001,  # Only Gemini Flash for invoice extraction
    }


def process_and_send_report(access_token, rcb_email, to_email, subject, sender_name, raw_attachments, msg_id, get_secret_func, db, firestore, helper_graph_send, extract_text_func, email_body=None, internet_message_id=None):
    """Main: Extract, classify, validate, send ONE consolidated email.

    Sends a single email containing: ack + classification report + clarification (if needed).
    Uses internet_message_id for proper Outlook/Gmail threading.
    """
    try:
        print(f"  🤖 Starting: {subject[:50]}")
        _cost_tracker.reset()  # Session 27: Reset per-run cost accumulator

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

        # ── PRE-CLASSIFY BYPASS: Skip AI if known product with high confidence ──
        results = None
        if PRE_CLASSIFY_BYPASS_ENABLED:
            try:
                results = _try_pre_classify_bypass(db, doc_text, gemini_key=gemini_key)
                if results:
                    print(f"  ✅ PRE-CLASSIFY BYPASS: saved ~$0.05 (engine={results.get('_engine')})")
            except Exception as bp_err:
                print(f"  ⚠️ Pre-classify bypass error: {bp_err}")
                results = None

        # ── TOOL-CALLING ENGINE: Single AI call with tools ──
        if not results and TOOL_CALLING_AVAILABLE:
            try:
                results = tool_calling_classify(api_key, doc_text, db, gemini_key=gemini_key)
                if not results or not results.get("success"):
                    print("  ⚠️ Tool-calling returned no result, falling back to pipeline")
                    results = None
            except Exception as tc_err:
                print(f"  ⚠️ Tool-calling error: {tc_err}, falling back to pipeline")
                results = None

        # ── FULL PIPELINE FALLBACK: 6-agent sequential classification ──
        if not results:
            results = run_full_classification(api_key, doc_text, db, gemini_key=gemini_key)
        if not results.get('success'):
            print(f"  ❌ Failed")
            return False

        # ── SESSION 27: THREE-WAY CROSS-CHECK ──
        if CROSS_CHECK_ENABLED and CROSS_CHECK_AVAILABLE:
            try:
                classifications = (
                    results.get("agents", {}).get("classification", {}).get("classifications", [])
                )
                invoice_data_cc = results.get("invoice_data", {})
                items_cc = invoice_data_cc.get("items", []) if isinstance(invoice_data_cc, dict) else []
                item_descs = [
                    it.get("description", "") for it in items_cc if isinstance(it, dict)
                ]
                origin_cc = ""
                if item_descs and items_cc:
                    origin_cc = items_cc[0].get("origin_country", "") if isinstance(items_cc[0], dict) else ""

                openai_key = None
                try:
                    openai_key = get_secret_func("OPENAI_API_KEY")
                except Exception:
                    pass

                if classifications:
                    cc_results = cross_check_all_items(
                        classifications,
                        item_descs,
                        origin_cc,
                        api_key,
                        gemini_key,
                        openai_key,
                        db=db,
                    )
                    if cc_results:
                        results["cross_check"] = cc_results
                        cc_summary = get_cross_check_summary(cc_results)
                        if cc_summary:
                            existing_synthesis = results.get("synthesis", "")
                            results["synthesis"] = existing_synthesis + "\n\n" + cc_summary
                            print(f"  🔍 Cross-check: {len(cc_results)} items verified")
                        # Apply confidence adjustments
                        for i, cc in enumerate(cc_results):
                            adj = cc.get("confidence_adjustment", 0)
                            if adj != 0 and i < len(classifications):
                                old_conf = classifications[i].get("confidence", "")
                                if isinstance(old_conf, (int, float)):
                                    classifications[i]["confidence"] = max(0, min(1, old_conf + adj))
                                classifications[i]["cross_check_tier"] = cc.get("tier", 0)
                                classifications[i]["cross_check_note"] = cc.get("learning_note", "")
            except Exception as cc_err:
                print(f"  ⚠️ Cross-check error: {cc_err}")

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
        has_smart_questions = bool(results.get("smart_questions"))
        if invoice_validation and invoice_validation['score'] < 70:
            status = "CLARIFICATION"
        elif has_smart_questions:
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
        enriched_items = _enrich_results_for_email(results, invoice_data, db)
        html = build_classification_email(results, sender_name, invoice_validation, tracking_code, invoice_data,
                                           enriched_items=enriched_items, original_email_body=email_body)
        excel = build_excel_report(results, enriched_items=enriched_items)

        # ── Build clarification section (merged into same email) ──
        clarification_sent = False
        clarification_html = ""
        if MODULES_AVAILABLE and invoice_validation and invoice_validation['score'] < 70:
            try:
                from lib.clarification_generator import (
                    generate_missing_docs_request,
                    DocumentType,
                    UrgencyLevel,
                )

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
                    urgency = UrgencyLevel.HIGH if invoice_validation['score'] < 50 else UrgencyLevel.MEDIUM
                    clarification = generate_missing_docs_request(
                        missing_docs=missing_docs,
                        invoice_number=invoice_data.get('invoice_number') or invoice_data.get('invoice_date'),
                        supplier_name=invoice_data.get('seller'),
                        recipient_name=sender_name,
                        urgency=urgency,
                        sender_name="מערכת RCB",
                    )
                    clarification_html = f'''<div style="background:#fff3cd;border:2px solid #ffc107;border-radius:10px;padding:20px;margin-top:25px">
                        <h2 style="color:#856404;margin:0 0 10px 0">📋 בקשה להשלמת מסמכים</h2>
                        <pre style="white-space:pre-wrap;font-family:Arial,sans-serif;direction:rtl;text-align:right;color:#856404;margin:0">{clarification.body}</pre>
                    </div>'''
                    clarification_sent = True
                    print(f"  📋 Clarification section added (score: {invoice_validation['score']}/100)")

            except Exception as ce:
                print(f"  ⚠️ Clarification generation error: {ce}")

        # ── Assemble ONE consolidated email: ack + classification + clarification ──
        # Insert ack banner before the classification report
        name = sender_name.split('<')[0].strip()
        first_name = name.split()[0] if name and '@' not in name else ""
        # Try Hebrew name
        try:
            from lib.rcb_helpers import to_hebrew_name
            display_name = to_hebrew_name(first_name) if first_name else "שלום"
        except Exception:
            display_name = first_name or "שלום"

        hour = datetime.now().hour
        greeting = "בוקר טוב" if 5 <= hour < 12 else "צהריים טובים" if 12 <= hour < 17 else "ערב טוב" if 17 <= hour < 21 else "לילה טוב"

        ack_banner = f'''<div dir="rtl" style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto 15px auto;background:#d4edda;border:1px solid #28a745;border-radius:10px;padding:15px">
            <p style="margin:0"><strong>{greeting} {display_name},</strong></p>
            <p style="margin:5px 0 0 0">✅ קיבלתי את המסמכים ועיבדתי אותם. להלן הדו"ח המלא:</p>
        </div>'''

        # Final HTML: ack banner + classification report + clarification section
        final_html = ack_banner + html
        if clarification_html:
            # Insert clarification before the footer (before the last </div></div>)
            footer_pos = final_html.rfind('<hr style="margin:25px 0">')
            if footer_pos > 0:
                final_html = final_html[:footer_pos] + clarification_html + final_html[footer_pos:]
            else:
                final_html += clarification_html

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

        print("  📤 Sending consolidated email...")
        if helper_graph_send(access_token, rcb_email, to_email, subject_line, final_html, msg_id, attachments, internet_message_id=internet_message_id):
            print(f"  ✅ Sent to {to_email}")

            # Save to Firestore
            save_data = {
                "tracking_code": tracking_code,
                "subject": subject_line,
                "original_subject": subject,
                "to": to_email,
                "items": len(results.get("agents", {}).get("classification", {}).get("classifications", [])),
                "timestamp": firestore.SERVER_TIMESTAMP,
                "direction": invoice_data.get('direction', 'unknown'),
                "freight_type": invoice_data.get('freight_type', 'unknown'),
                "bl_number": invoice_data.get('bl_number', ''),
                "awb_number": invoice_data.get('awb_number', ''),
                "seller": invoice_data.get('seller', ''),
                "buyer": invoice_data.get('buyer', ''),
                "clarification_sent": clarification_sent,
            }

            if invoice_validation:
                save_data["invoice_score"] = invoice_validation['score']
                save_data["invoice_valid"] = invoice_validation['is_valid']
                save_data["missing_fields"] = invoice_validation['missing_fields']

            if has_smart_questions:
                ambiguity = results.get("ambiguity", {})
                save_data["smart_questions_count"] = len(results["smart_questions"])
                save_data["ambiguity_reason"] = ambiguity.get("reason", "")
                save_data["classification_ambiguous"] = True

            # Session 27: Cost tracking
            if COST_TRACKING_ENABLED:
                save_data["total_cost"] = round(_cost_tracker.total(), 4)

            # Session 27: Cross-check results
            if results.get("cross_check"):
                cc_tiers = [cc.get("tier", 0) for cc in results["cross_check"]]
                save_data["cross_check_tiers"] = cc_tiers
                save_data["cross_check_avg_tier"] = round(sum(cc_tiers) / len(cc_tiers), 1) if cc_tiers else 0

            db.collection("rcb_classifications").add(save_data)

            # Learn from classification
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

            # Session 27: Print cost summary
            if COST_TRACKING_ENABLED:
                summary = _cost_tracker.summary()
                if summary:
                    print(f"  {summary}")

            return True
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
