"""
RCB Tracker v2 — Deal-Centric Tracking Engine
==============================================
Tracks shipments by DEAL (BL/AWB), not by container.
All containers under one BL = one deal.
Extracts data from email body + PDF attachments.
Queries TaskYam for port operations.
Sends consolidated status emails with visual progress bar.

Collections:
  tracker_observations — per-email dedup (same as v1)
  tracker_deals — one per BL/AWB deal
  tracker_container_status — one per container per deal
  tracker_timeline — event log per deal

Data sources:
  Phase 1: Email + attachments, TaskYam API
  Phase 2: INTTRA, MarineTraffic, VesselFinder
  Phase 3: Maman/Swissport (air)
"""

import re
import json
import hashlib
import traceback
from datetime import datetime, timezone, timedelta

# ── Container validation (ISO 6346) ──
def _iso6346_check_digit(prefix_digits):
    """Validate ISO 6346 container check digit"""
    alphabet = "0123456789A BCDEFGHIJK LMNOPQRSTU VWXYZ"
    values = {}
    n = 0
    for c in alphabet:
        if c == ' ':
            n += 1
            continue
        values[c] = n
        n += 1
    total = 0
    for i, ch in enumerate(prefix_digits[:10]):
        total += values.get(ch, 0) * (2 ** i)
    check = total % 11
    if check == 10:
        check = 0
    return str(check) == prefix_digits[10]

# ── Extraction patterns ──
PATTERNS = {
    'container': r'\b([A-Z]{4}\d{7})\b',
    'bol': r'(?:B/?L|BOL|BL|bill\s*of\s*lading|שטר\s*מטען)[:\s#]*([A-Z0-9][\w\-]{6,25})',
    'bol_msc': r'\b(MEDURS\d{5,10})\b',
    'bol_maersk': r'\b(\d{9,10})\b',  # Maersk numeric BOLs
    'booking': r'(?:booking|הזמנה|BKG|EBKG)[:\s#]*([A-Z0-9]{6,20})',
    'booking_bare': r'\bEBKG(\d{6,12})\b',
    'manifest': r'(?:manifest|מניפסט|מצהר)[:\s#]*([0-9]{4,8})',
    'vessel_labeled': r'(?:M/?V|vessel|אוניה|ספינה)[:\s]+([A-Z][A-Z\s\-]{3,30})',
    'rnr_vessel': r'RNR\s*(?:CODE)?\s*[:\s]*(\d{3,5})\s+([A-Z][A-Z\s\-]{3,30})',
    'shipping_line': r'\b(ZIM|MAERSK|MSC|CMA[\s\-]?CGM|HAPAG|EVERGREEN|COSCO|ONE[\s\-]?LINE|OCEAN\s*NETWORK|HMM|YANG\s*MING|PIL|TURKON|OOCL|WAN[\s\-]?HAI|KONMART|CARMEL)\b',
    'port_hebrew': r'(חיפה|אשדוד|אילת|חדרה)',
    'port_english': r'\b(haifa|ashdod|eilat|hadera)\b',
    'eta': r'(?:ETA|הגעה\s*משוערת|expected\s*arrival)[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
    'etd': r'(?:ETD|expected\s*departure|הפלגה\s*משוערת)[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
    'declaration': r'(?:רשמ"י|רשימון|declaration)[:\s#]*(\d{6,12})',
    'getpass': r'(?:גטפס|getpass|שחרור|GP)[:\s#]*(\d{4,12})',
    'cutoff_doc': r'(?:doc(?:ument)?\s*cut[\s\-]?off|סגירת\s*מסמכים)[:\s]*(\d{1,2}[/\-\.]\d{1,2})',
    'cutoff_container': r'(?:container\s*cut[\s\-]?off|סגירת\s*מכולות)[:\s]*(\d{1,2}[/\-\.]\d{1,2})',
    'storage_id': r'(?:storage\s*(?:id|cert)|תעודת\s*אחסנה)[:\s#]*(\d{8,12})',
    'awb': r'\b(\d{3})[\s\-]?(\d{8})\b',  # Airline prefix + 8 digits
    'flight': r'\b(?:LY|EL|5C|TK|LH|AF|BA|KL|MS|ET|SU|W5)\s?\d{3,4}\b',
    'transaction_id': r'\b([IE]\d{2}\d{4,8}[A-Z]{2,5}\d{2,4})\b',
    'shipper': r'(?:shipper|שולח|מוצא)[:\s]+([^\n]{5,60})',
    'consignee': r'(?:consignee|נמען|יבואן)[:\s]+([^\n]{5,60})',
    'weight': r'(?:gross\s*weight|משקל\s*ברוטו)[:\s]*(\d[\d,\.]+)\s*(kg|ton)?',
    'notify_arrival': r'(?:notice\s*of\s*(?:goods\s*)?arrival|הודעת\s*הגעת\s*טובין)',
    'shaar_olami': r'(https?://shaarolami[^\s<"\']+)',
}

# Port code mapping
PORT_MAP = {
    'חיפה': 'ILHFA', 'haifa': 'ILHFA',
    'אשדוד': 'ILASD', 'ashdod': 'ILASD',
    'אילת': 'ILELT', 'eilat': 'ILELT',
    'חדרה': 'ILHDR', 'hadera': 'ILHDR',
}

# Sender classification
LOGISTICS_SENDERS = {
    'port_authority': ['haifaport.co.il', 'ashdodport.co.il', 'israports.co.il', 'gadot.co.il'],
    'shipping_line': ['zim.com', 'maersk.com', 'msc.com', 'cma-cgm.com', 'hapag-lloyd.com',
                      'evergreen-line.com', 'cosco.com', 'one-line.com', 'hmm21.com',
                      'yangming.com', 'pilship.com', 'oocl.com', 'wanhai.com',
                      'turkon.com.tr', 'konmart.co.il', 'carmelship.co.il'],
    'airline': ['elal.co.il', 'turkishairlines.com', 'lufthansa.com'],
    'cargo_handler': ['maman.co.il', 'swissport.com', 'jas.com'],
    'customs_agent': ['rpa-port.co.il'],
    'forwarder': ['dhl.com', 'kuehne-nagel.com', 'dbschenker.com', 'fedex.com', 'ups.com'],
}

# Follow/stop command patterns
FOLLOW_PATTERNS = [
    r'(?:follow|track|עקוב|צפי|מעקב)\s+([A-Z0-9][\w\-]{5,25})',
    r'(?:follow|track|עקוב|צפי)\s+(?:this|זה)',
]
STOP_PATTERNS = [
    r'(?:stop\s*follow|stop\s*track|תפסיק\s*לעקוב|הפסק\s*מעקב)',
]

# ── Cached BOL prefixes from Firestore shipping_lines collection ──
_bol_prefix_cache = None  # {prefix: carrier_name}, loaded on first use

def _load_bol_prefixes(db):
    """Load bol_prefixes from shipping_lines collection. Cached per cold start."""
    global _bol_prefix_cache
    if _bol_prefix_cache is not None:
        return _bol_prefix_cache
    _bol_prefix_cache = {}
    try:
        for doc in db.collection('shipping_lines').stream():
            data = doc.to_dict()
            carrier = doc.id
            for prefix in data.get('bol_prefixes', []):
                if prefix:
                    _bol_prefix_cache[prefix.upper()] = carrier
        print(f"    📋 Tracker: loaded {len(_bol_prefix_cache)} BOL prefixes from Firestore")
    except Exception as e:
        print(f"    📋 Tracker: BOL prefix load error: {e}")
    return _bol_prefix_cache

# ════════════════════════════════════════════════════════
#  MAIN ENTRY POINT — called from rcb_check_email hook
# ════════════════════════════════════════════════════════

def tracker_process_email(msg, db, firestore_module, access_token, rcb_email, get_secret_func, is_direct=True):
    """
    Process every email that flows through rcb_check_email.
    Extract logistics data, create/update deals, check for follow/stop commands.
    """
    try:
        msg_id = msg.get('id', '')
        from_email = msg.get('from', {}).get('emailAddress', {}).get('address', '') if isinstance(msg.get('from'), dict) else ''
        subject = msg.get('subject', '')
        body_content = msg.get('body', {}).get('content', '')
        received_at = msg.get('receivedDateTime', '')
        has_attachments = msg.get('hasAttachments', False)
        conversation_id = msg.get('conversationId', '')
        cc_list = [r.get('emailAddress', {}).get('address', '')
                   for r in msg.get('ccRecipients', []) if r.get('emailAddress')]

        # Generate observation ID
        obs_id = _make_obs_id(msg_id)

        # Skip if already observed
        if db.collection("tracker_observations").document(obs_id).get().exists:
            return {"status": "already_observed", "obs_id": obs_id}

        # ── STEP 1: Clean text (smart read — preserves table structure) ──
        try:
            from lib.doc_reader import smart_read_html_body
            clean_body = smart_read_html_body(body_content)
        except Exception:
            clean_body = _strip_html(body_content)
        full_text = f"{subject}\n{clean_body}"

        # ── STEP 2: Extract text from attachments (PDFs, images) ──
        attachment_text = ""
        attachment_names = []
        if has_attachments and access_token:
            try:
                from lib.rcb_helpers import helper_graph_attachments, extract_text_from_attachments
                raw_atts = helper_graph_attachments(access_token, rcb_email, msg_id)
                if raw_atts:
                    attachment_names = [a.get('name', '') for a in raw_atts if a.get('name')]
                    attachment_text = extract_text_from_attachments(raw_atts)
                    if attachment_text:
                        full_text = f"{full_text}\n{attachment_text}"
                        print(f"    📎 Tracker: extracted text from {len(raw_atts)} attachments ({len(attachment_text)} chars)")
            except Exception as ae:
                print(f"    📎 Tracker attachment error: {ae}")

        # ── STEP 3: Check for follow/stop commands ──
        command = _detect_command(subject, clean_body)
        if command:
            return _handle_command(command, msg, db, firestore_module, access_token, rcb_email, from_email)

        # ── STEP 4: Extract logistics data (brain-first) ──
        sender_type = _classify_sender(from_email)
        confidence = 0.0
        brain_level = "none"

        # Load BOL prefix cache (once per cold start)
        _load_bol_prefixes(db)

        # Ask brain first — does it know this sender/doc type?
        try:
            from lib.self_learning import SelfLearningEngine
            brain = SelfLearningEngine(db)
            brain_knowledge, brain_level = brain.check_tracking_memory(
                from_email, subject, attachment_names)

            if brain_level == "exact" and brain_knowledge:
                # Brain knows this sender — use its rules + validate with regex
                extractions = _extract_logistics_data(full_text)
                confidence = 0.85
                print(f"    🧠 Tracker: brain EXACT match for {from_email}")
            elif brain_level in ("similar", "partial") and brain_knowledge:
                extractions = _extract_logistics_data(full_text)
                confidence = 0.65
                print(f"    🧠 Tracker: brain {brain_level} match for {from_email}")
            else:
                extractions = _extract_logistics_data(full_text)
                confidence = 0.40
        except Exception as brain_err:
            print(f"    🧠 Tracker brain skip: {brain_err}")
            extractions = _extract_logistics_data(full_text)
            confidence = 0.40

        # ── STEP 4a: Try template extraction (brain reads independently) ──
        template_used = False
        template_extractions = None
        try:
            from lib.doc_reader import try_template_extraction, identify_doc_type
            _shipping_line = (extractions.get('shipping_lines') or [''])[0]
            _doc_type, _doc_conf = identify_doc_type(full_text, ','.join(attachment_names))
            template_extractions, template_used = try_template_extraction(
                full_text, _shipping_line, _doc_type, db)
            if template_used and template_extractions:
                for tk, tv in template_extractions.items():
                    if not extractions.get(tk) and tv:
                        extractions[tk] = tv
                confidence = max(confidence, 0.75)
                print(f"    📖 Tracker: template filled gaps for {_shipping_line} {_doc_type}")
        except Exception as tmpl_err:
            print(f"    📖 Tracker template skip: {tmpl_err}")

        # ── STEP 4b: LLM enrichment if regex got thin results ──
        was_enriched = False
        try:
            extractions, was_enriched = _llm_enrich_extraction(extractions, full_text, get_secret_func)
            if was_enriched:
                confidence = max(confidence, 0.70)
        except Exception as llm_err:
            print(f"    🤖 Tracker LLM skip: {llm_err}")

        # ── STEP 4c: Learn template if LLM was used (brain remembers HOW to read) ──
        try:
            if was_enriched:
                from lib.doc_reader import learn_template, identify_doc_type, validate_template
                _shipping_line = (extractions.get('shipping_lines') or [''])[0]
                if not _doc_type or _doc_type == 'unknown':
                    _doc_type, _doc_conf = identify_doc_type(full_text, ','.join(attachment_names))
                learn_template(full_text, extractions, _shipping_line, _doc_type, db)
                # Validate template if we tried it earlier
                if template_used and template_extractions:
                    tmpl_key = f"{_shipping_line}_{_doc_type}".lower().replace(' ', '_')
                    validate_template(template_extractions, extractions, tmpl_key, db)
        except Exception as tl_err:
            print(f"    📖 Tracker template learn skip: {tl_err}")

        is_logistics = _is_logistics_email(sender_type, extractions, subject)

        # ── STEP 5: Save observation ──
        observation = {
            "obs_id": obs_id,
            "msg_id": msg_id,
            "from_email": from_email,
            "subject": subject,
            "received_at": received_at,
            "conversation_id": conversation_id,
            "cc_list": cc_list,
            "sender_type": sender_type,
            "is_logistics": is_logistics,
            "has_attachments": has_attachments,
            "attachment_names": attachment_names,
            "extractions": extractions,
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        db.collection("tracker_observations").document(obs_id).set(observation)

        if not is_logistics:
            return {"status": "not_logistics", "obs_id": obs_id}

        print(f"    🚢 Tracker: logistics email from {from_email}: {len(extractions.get('containers', []))} containers, "
              f"{len(extractions.get('bols', []))} BOLs, {extractions.get('shipping_lines', [])}")

        # ── STEP 6: Match or create deal ──
        deal_result = _match_or_create_deal(db, firestore_module, observation)

        # ── STEP 7: Teach brain from this extraction ──
        try:
            if not brain_level or brain_level == "none":
                from lib.self_learning import SelfLearningEngine
                brain = SelfLearningEngine(db)
            doc_type = _guess_doc_type_from_attachments(attachment_names)
            brain.learn_tracking_extraction(
                sender_email=from_email,
                doc_type=doc_type,
                extractions=extractions,
                confidence=confidence,
                source=f"regex_brain_{brain_level}"
            )
        except Exception as learn_err:
            print(f"    🧠 Tracker learn skip: {learn_err}")

        # ── STEP 8: Send email for new and updated deals (if is_direct) ──
        if is_direct and deal_result.get("deal_id"):
            try:
                _deal_id = deal_result["deal_id"]
                _deal_doc = db.collection("tracker_deals").document(_deal_id).get()
                if _deal_doc.exists:
                    _update_type = "new_deal" if deal_result.get("action") == "created" else "status_update"
                    _send_tracker_email(
                        db, _deal_id, _deal_doc.to_dict(), access_token, rcb_email,
                        _update_type, observation=observation, extractions=extractions)
            except Exception as email_err:
                print(f"    Warning: Tracker email error: {email_err}")

        return {
            "status": "processed",
            "obs_id": obs_id,
            "is_logistics": True,
            "deal_result": deal_result,
            "brain_level": brain_level,
            "confidence": confidence,
        }

    except Exception as e:
        print(f"    ❌ Tracker error: {e}")
        traceback.print_exc()
        return {"status": "error", "error": str(e)}

# ════════════════════════════════════════════════════════
#  EXTRACTION ENGINE
# ════════════════════════════════════════════════════════

def _extract_logistics_data(text):
    """Extract all logistics identifiers from text (email body + attachments)"""
    result = {
        'containers': [],
        'bols': [],
        'bookings': [],
        'manifests': [],
        'vessels': [],
        'shipping_lines': [],
        'ports': [],
        'etas': [],
        'etds': [],
        'declarations': [],
        'getpasses': [],
        'storage_ids': [],
        'transaction_ids': [],
        'cutoff_doc': [],
        'cutoff_container': [],
        'shippers': [],
        'consignees': [],
        'weights': [],
        'awbs': [],
        'flights': [],
        'is_notice_of_arrival': False,
        'direction': '',  # import/export, inferred
    }

    if not text:
        return result

    text_upper = text.upper()

    # Containers (ISO 6346 with check digit validation)
    for m in re.finditer(PATTERNS['container'], text_upper):
        cn = m.group(1)
        if _iso6346_check_digit(cn) and cn not in result['containers']:
            result['containers'].append(cn)

    # BOLs — multiple patterns
    for pat_name in ['bol', 'bol_msc']:
        for m in re.finditer(PATTERNS[pat_name], text_upper if pat_name != 'bol' else text, re.IGNORECASE):
            bol = m.group(1).strip()
            if bol not in result['bols'] and len(bol) > 5:
                result['bols'].append(bol)

    # Maersk numeric BOLs — only when MAERSK detected in text (pattern too broad otherwise)
    if 'MAERSK' in text_upper and not result['bols']:
        for m in re.finditer(PATTERNS['bol_maersk'], text_upper):
            bol = m.group(1).strip()
            if bol not in result['bols']:
                result['bols'].append(bol)

    # BOLs — prefix matching from Firestore shipping_lines collection
    if _bol_prefix_cache:
        for prefix, carrier in _bol_prefix_cache.items():
            for m in re.finditer(r'\b(' + re.escape(prefix) + r'[\w\-]{3,20})\b', text_upper):
                bol = m.group(1).strip()
                if bol not in result['bols'] and len(bol) > 5:
                    result['bols'].append(bol)
                    if carrier not in result['shipping_lines']:
                        result['shipping_lines'].append(carrier)

    # Bookings
    for pat_name in ['booking', 'booking_bare']:
        for m in re.finditer(PATTERNS[pat_name], text, re.IGNORECASE):
            bkg = m.group(1).strip()
            if bkg not in result['bookings']:
                result['bookings'].append(bkg)

    # Manifests
    for m in re.finditer(PATTERNS['manifest'], text, re.IGNORECASE):
        result['manifests'].append(m.group(1))

    # Vessels
    for m in re.finditer(PATTERNS['vessel_labeled'], text_upper):
        v = m.group(1).strip()
        if len(v) > 3 and v not in result['vessels']:
            result['vessels'].append(v)
    for m in re.finditer(PATTERNS['rnr_vessel'], text_upper):
        v = m.group(2).strip()
        if v not in result['vessels']:
            result['vessels'].append(v)

    # Shipping lines
    for m in re.finditer(PATTERNS['shipping_line'], text_upper):
        sl = m.group(1)
        if sl not in result['shipping_lines']:
            result['shipping_lines'].append(sl)

    # Ports
    for pat_name in ['port_hebrew', 'port_english']:
        for m in re.finditer(PATTERNS[pat_name], text, re.IGNORECASE):
            port_name = m.group(1).lower() if pat_name == 'port_english' else m.group(1)
            code = PORT_MAP.get(port_name, PORT_MAP.get(port_name.lower(), ''))
            if code:
                port_entry = {'name': port_name, 'code': code}
                if port_entry not in result['ports']:
                    result['ports'].append(port_entry)

    # Dates
    for m in re.finditer(PATTERNS['eta'], text, re.IGNORECASE):
        result['etas'].append(m.group(1))
    for m in re.finditer(PATTERNS['etd'], text, re.IGNORECASE):
        result['etds'].append(m.group(1))
    for m in re.finditer(PATTERNS['cutoff_doc'], text, re.IGNORECASE):
        result['cutoff_doc'].append(m.group(1))
    for m in re.finditer(PATTERNS['cutoff_container'], text, re.IGNORECASE):
        result['cutoff_container'].append(m.group(1))

    # Declarations, getpasses, storage IDs
    for m in re.finditer(PATTERNS['declaration'], text, re.IGNORECASE):
        result['declarations'].append(m.group(1))
    for m in re.finditer(PATTERNS['getpass'], text, re.IGNORECASE):
        result['getpasses'].append(m.group(1))
    for m in re.finditer(PATTERNS['storage_id'], text, re.IGNORECASE):
        result['storage_ids'].append(m.group(1))
    for m in re.finditer(PATTERNS['transaction_id'], text_upper):
        result['transaction_ids'].append(m.group(1))

    # Shipper/Consignee (with noise filter)
    _noise = ['forwarding agent', 'gross cargo', 'load stow and count',
              'not checked by carrier', 'not responsible', 'non negotiable',
              'to order', 'measurement', 'continued on attached',
              'packages and goods', 'description of', 'seal number',
              'rider page', 'particulars furnished']
    for m in re.finditer(PATTERNS['shipper'], text, re.IGNORECASE):
        val = m.group(1).strip()
        if len(val) > 5 and not any(n in val.lower() for n in _noise):
            if val not in result['shippers']:
                result['shippers'].append(val)
    for m in re.finditer(PATTERNS['consignee'], text, re.IGNORECASE):
        val = m.group(1).strip()
        if len(val) > 5 and not any(n in val.lower() for n in _noise):
            if val not in result['consignees']:
                result['consignees'].append(val)

    # Weights
    for m in re.finditer(PATTERNS['weight'], text, re.IGNORECASE):
        result['weights'].append(m.group(1))

    # Air
    for m in re.finditer(PATTERNS['flight'], text_upper):
        result['flights'].append(m.group(0))

    # Notice of arrival detection
    if re.search(PATTERNS['notify_arrival'], text, re.IGNORECASE):
        result['is_notice_of_arrival'] = True

    # Infer direction
    result['direction'] = _infer_direction(text, result)

    return result




def _llm_enrich_extraction(extractions, full_text, get_secret_func):
    """Call Gemini Flash to enrich thin regex extractions. Brain learns from result."""
    try:
        # Count useful fields
        useful = sum(1 for k in ['containers','vessels','bookings','manifests']
                     if extractions.get(k))
        missing_parties = not extractions.get("shippers") or not extractions.get("consignees")
        if (useful >= 3 and not missing_parties) or len(full_text) < 500:
            return extractions, False  # Already rich enough or too little text

        from lib.gemini_classifier import _call_gemini
        import json

        prompt = """Extract ALL logistics data from this shipping document text.
Return ONLY valid JSON with these fields (empty string or empty list if not found):
{
  "containers": ["XXXX1234567"],
  "bols": ["BOL number"],
  "bookings": ["booking ref"],
  "manifests": ["manifest number"],
  "vessels": ["vessel name"],
  "shipping_lines": ["MSC/ZIM/etc"],
  "shippers": ["shipper name"],
  "consignees": ["consignee name"],
  "ports": [{"name":"port","code":"ILHFA"}],
  "weights": ["total weight"],
  "etas": ["date"],
  "etds": ["date"],
  "declarations": ["declaration number"],
  "direction": "import or export"
}

DOCUMENT TEXT:
""" + full_text[:30000]

        raw = _call_gemini(prompt)
        if not raw:
            return extractions, False

        # Parse JSON response
        clean = raw.strip()
        if clean.startswith('```'):
            clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0]
        llm_data = json.loads(clean)

        # Merge: LLM fills gaps, never overwrites existing regex results
        merged = 0
        for key in ['containers','bols','bookings','manifests','vessels','shipping_lines',
                     'shippers','consignees','ports','weights','etas','etds','declarations']:
            llm_val = llm_data.get(key, [])
            if isinstance(llm_val, str):
                llm_val = [llm_val] if llm_val else []
            existing = extractions.get(key, [])
            if not existing and llm_val:
                extractions[key] = llm_val
                merged += 1

        if not extractions.get('direction') and llm_data.get('direction'):
            extractions['direction'] = llm_data['direction']
            merged += 1

        print(f"    🤖 Tracker LLM enriched: {merged} fields added")
        return extractions, merged > 0

    except Exception as e:
        print(f"    🤖 Tracker LLM enrich skip: {e}")
        return extractions, False

def _infer_direction(text, extractions):
    """Infer import/export from context"""
    text_lower = text.lower()
    import_signals = ['import', 'יבוא', 'notice of arrival', 'הגעת טובין', 'eta', 'unloading',
                      'delivery order', 'פריקה', 'הורדה']
    export_signals = ['export', 'יצוא', 'etd', 'loading', 'stowage', 'storage cert',
                      'תעודת אחסנה', 'סגירה', 'cutoff', 'cut-off', 'העמסה']

    import_score = sum(1 for s in import_signals if s in text_lower)
    export_score = sum(1 for s in export_signals if s in text_lower)

    if extractions.get('storage_ids'):
        export_score += 2
    if extractions.get('is_notice_of_arrival'):
        import_score += 3

    if import_score > export_score:
        return 'import'
    elif export_score > import_score:
        return 'export'
    return ''


def _is_logistics_email(sender_type, extractions, subject):
    """Determine if email is logistics-relevant"""
    if sender_type in ('port_authority', 'shipping_line', 'airline', 'cargo_handler'):
        return True
    if extractions.get('containers'):
        return True
    if extractions.get('bols'):
        return True
    if extractions.get('bookings'):
        return True
    if extractions.get('manifests'):
        return True
    if extractions.get('vessels'):
        return True
    if extractions.get('awbs'):
        return True
    if extractions.get('is_notice_of_arrival'):
        return True
    if extractions.get('declarations'):
        return True
    if extractions.get('storage_ids'):
        return True
    return False

# ════════════════════════════════════════════════════════
#  DEAL MATCHING — find or create deal from observation
# ════════════════════════════════════════════════════════

def _match_or_create_deal(db, firestore_module, observation):
    """Match observation to existing deal or create new one"""
    ext = observation.get('extractions', {})
    bols = ext.get('bols', [])
    containers = ext.get('containers', [])
    bookings = ext.get('bookings', [])
    manifests = ext.get('manifests', [])

    matched_deal_id = None

    # Priority 0: Match by conversation thread (same email thread = same deal)
    conv_id = observation.get('conversation_id', '')
    if conv_id:
        try:
            conv_deals = list(db.collection("tracker_deals")
                             .where("source_email_thread_id", "==", conv_id)
                             .where("status", "in", ["active", "pending"])
                             .limit(1).stream())
            if conv_deals:
                matched_deal_id = conv_deals[0].id
                print(f"    🔗 Tracker: matched deal by conversation thread")
        except Exception:
            pass

    # Priority 1a: Match by BOL
    if not matched_deal_id:
        for bol in bols:
            deal = _find_deal_by_field(db, 'bol_number', bol)
            if deal:
                matched_deal_id = deal.id
                break

    # Priority 1b: Match by AWB (air freight)
    if not matched_deal_id:
        for awb in observation.get('extractions', {}).get('awbs', []):
            deal = _find_deal_by_field(db, 'awb_number', awb)
            if deal:
                matched_deal_id = deal.id
                print(f"    ✈️ Tracker: matched deal by AWB {awb}")
                break

    # Priority 2: Match by container (any container in this email matches a deal)
    if not matched_deal_id:
        for cn in containers:
            deal = _find_deal_by_container(db, cn)
            if deal:
                matched_deal_id = deal.id
                break

    # Priority 3: Match by booking
    if not matched_deal_id:
        for bkg in bookings:
            deal = _find_deal_by_field(db, 'booking_number', bkg)
            if deal:
                matched_deal_id = deal.id
                break

    if matched_deal_id:
        # Update existing deal with new info
        _update_deal_from_observation(db, firestore_module, matched_deal_id, observation)
        return {"action": "updated", "deal_id": matched_deal_id}
    else:
        # Create new deal if we have enough info
        if bols or (containers and (ext.get('shipping_lines') or ext.get('vessels'))):
            deal_id = _create_deal(db, firestore_module, observation)
            return {"action": "created", "deal_id": deal_id}
        else:
            return {"action": "skipped", "reason": "insufficient data for deal creation"}


def _find_deal_by_field(db, field, value):
    """Find active deal by a specific field"""
    if not value:
        return None
    try:
        results = list(db.collection("tracker_deals")
                       .where(field, "==", value)
                       .where("status", "in", ["active", "pending"])
                       .limit(1).stream())
        return results[0] if results else None
    except Exception:
        return None


def _find_deal_by_container(db, container_number):
    """Find active deal containing a specific container"""
    if not container_number:
        return None
    try:
        results = list(db.collection("tracker_deals")
                       .where("containers", "array_contains", container_number)
                       .where("status", "in", ["active", "pending"])
                       .limit(1).stream())
        return results[0] if results else None
    except Exception:
        return None


def _create_deal(db, firestore_module, observation):
    """Create a new deal from observation data"""
    ext = observation.get('extractions', {})
    now = datetime.now(timezone.utc).isoformat()

    deal_data = {
        "bol_number": ext.get('bols', [''])[0] if ext.get('bols') else '',
        "awb_number": ext.get('awbs', [''])[0] if ext.get('awbs') else '',
        "booking_number": ext.get('bookings', [''])[0] if ext.get('bookings') else '',
        "direction": ext.get('direction', ''),
        "containers": ext.get('containers', []),
        "manifest_number": ext.get('manifests', [''])[0] if ext.get('manifests') else '',
        "transaction_ids": ext.get('transaction_ids', []),
        "taskyam_transmitted": False,
        "vessel_name": ext.get('vessels', [''])[0] if ext.get('vessels') else '',
        "loyds_number": '',
        "journey_id": '',
        "shipping_line": ext.get('shipping_lines', [''])[0] if ext.get('shipping_lines') else '',
        "ship_agent_code": '',
        "shipper": ext.get('shippers', [''])[0] if ext.get('shippers') else '',
        "consignee": ext.get('consignees', [''])[0] if ext.get('consignees') else '',
        "customs_agent": "07294",
        "transport_company": '',
        "port": ext.get('ports', [{}])[0].get('code', '') if ext.get('ports') else '',
        "port_name": ext.get('ports', [{}])[0].get('name', '') if ext.get('ports') else '',
        "freight_kind": _infer_freight_kind(ext),
        "customs_declaration": ext.get('declarations', [''])[0] if ext.get('declarations') else '',
        "storage_id": ext.get('storage_ids', [''])[0] if ext.get('storage_ids') else '',
        "eta": ext.get('etas', [''])[0] if ext.get('etas') else '',
        "etd": ext.get('etds', [''])[0] if ext.get('etds') else '',
        "doc_cutoff": ext.get('cutoff_doc', [''])[0] if ext.get('cutoff_doc') else '',
        "container_cutoff": ext.get('cutoff_container', [''])[0] if ext.get('cutoff_container') else '',
        "sailing_date": '',
        "status": "active",
        "source_emails": [observation.get('obs_id', '')],
        "source_email_thread_id": observation.get('conversation_id', ''),
        "rcb_classification_id": '',
        "follower_email": observation.get('from_email', ''),
        "cc_list": observation.get('cc_list', []),
        "follow_mode": "auto",
        "created_at": now,
        "updated_at": now,
    }

    # Create deal document
    doc_ref = db.collection("tracker_deals").document()
    doc_ref.set(deal_data)
    deal_id = doc_ref.id

    # Create container status docs for each container
    for cn in ext.get('containers', []):
        cn_doc = db.collection("tracker_container_status").document(f"{deal_id}_{cn}")
        cn_doc.set({
            "deal_id": deal_id,
            "container_id": cn,
            "import_process": {},
            "export_process": {},
            "current_step": "",
            "last_taskyam_check": "",
            "container_type": '',
            "weight": '',
            "arrival_time": '',
            "exit_time": '',
            "taskyam_raw": {},
            "created_at": now,
            "updated_at": now,
        })

    # Log timeline
    _log_timeline(db, firestore_module, deal_id, {
        "event_type": "deal_created",
        "source": "email",
        "from_email": observation.get('from_email', ''),
        "subject": observation.get('subject', '')[:100],
        "containers_count": len(ext.get('containers', [])),
        "bol": deal_data['bol_number'],
    })

    # Register AWB for air cargo polling if present
    if deal_data.get("awb_number"):
        try:
            from lib.air_cargo_tracker import register_awb
            register_awb(db, deal_data["awb_number"], deal_id)
            print(f"    ✈️ Registered AWB {deal_data['awb_number']} for air cargo polling")
        except Exception as awb_err:
            print(f"    ⚠️ AWB registration error (non-fatal): {awb_err}")

    print(f"    📦 Tracker: created deal {deal_id}: BOL={deal_data['bol_number']}, "
          f"{len(ext.get('containers', []))} containers, {deal_data['shipping_line']}")

    return deal_id


def _update_deal_from_observation(db, firestore_module, deal_id, observation):
    """Update existing deal with new data from observation"""
    ext = observation.get('extractions', {})
    deal_ref = db.collection("tracker_deals").document(deal_id)
    deal_doc = deal_ref.get()
    if not deal_doc.exists:
        return

    deal = deal_doc.to_dict()
    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}

    # Add new containers (merge, don't replace)
    existing_containers = deal.get('containers', [])
    for cn in ext.get('containers', []):
        if cn not in existing_containers:
            existing_containers.append(cn)
            # Create container status doc
            cn_doc = db.collection("tracker_container_status").document(f"{deal_id}_{cn}")
            if not cn_doc.get().exists:
                cn_doc.set({
                    "deal_id": deal_id,
                    "container_id": cn,
                    "import_process": {},
                    "export_process": {},
                    "current_step": "",
                    "last_taskyam_check": "",
                    "container_type": '',
                    "weight": '',
                    "arrival_time": '',
                    "exit_time": '',
                    "taskyam_raw": {},
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
    if existing_containers != deal.get('containers', []):
        updates['containers'] = existing_containers

    # Fill empty fields with new data
    field_map = {
        'bol_number': ('bols', 0),
        'awb_number': ('awbs', 0),
        'booking_number': ('bookings', 0),
        'manifest_number': ('manifests', 0),
        'vessel_name': ('vessels', 0),
        'shipping_line': ('shipping_lines', 0),
        'customs_declaration': ('declarations', 0),
        'storage_id': ('storage_ids', 0),
        'eta': ('etas', 0),
        'etd': ('etds', 0),
        'doc_cutoff': ('cutoff_doc', 0),
        'container_cutoff': ('cutoff_container', 0),
    }
    for deal_field, (ext_field, idx) in field_map.items():
        if not deal.get(deal_field) and ext.get(ext_field):
            vals = ext[ext_field]
            if idx < len(vals):
                updates[deal_field] = vals[idx] if not isinstance(vals[idx], dict) else vals[idx].get('code', '')

    # Add source email
    source_emails = deal.get('source_emails', [])
    obs_id = observation.get('obs_id', '')
    if obs_id and obs_id not in source_emails:
        source_emails.append(obs_id)
        updates['source_emails'] = source_emails

    # Update direction if empty
    if not deal.get('direction') and ext.get('direction'):
        updates['direction'] = ext['direction']

    # Merge transaction_ids
    existing_txns = deal.get('transaction_ids', [])
    for txn in ext.get('transaction_ids', []):
        if txn not in existing_txns:
            existing_txns.append(txn)
            updates['transaction_ids'] = existing_txns

    if len(updates) > 1:  # more than just updated_at
        deal_ref.update(updates)
        print(f"    📦 Tracker: updated deal {deal_id} with {len(updates)-1} new fields")

        # Register AWB for air cargo polling if newly added
        if 'awb_number' in updates and updates['awb_number']:
            try:
                from lib.air_cargo_tracker import register_awb
                register_awb(db, updates['awb_number'], deal_id)
                print(f"    ✈️ Registered AWB {updates['awb_number']} for air cargo polling")
            except Exception as awb_err:
                print(f"    ⚠️ AWB registration error (non-fatal): {awb_err}")

    return deal_id


def _infer_freight_kind(extractions):
    """Infer freight kind from extractions"""
    if extractions.get('containers'):
        return 'FCL'
    if extractions.get('awbs') or extractions.get('flights'):
        return 'air'
    return 'general'

# ════════════════════════════════════════════════════════
#  FOLLOW / STOP COMMANDS
# ════════════════════════════════════════════════════════

def _detect_command(subject, body):
    """Detect follow/stop commands in email"""
    text = f"{subject} {body[:500]}"

    # Check stop first
    for pat in STOP_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return {"type": "stop"}

    # Check follow
    for pat in FOLLOW_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            identifier = m.group(1) if m.lastindex else ''
            return {"type": "follow", "identifier": identifier}

    return None


def _handle_command(command, msg, db, firestore_module, access_token, rcb_email, from_email):
    """Handle follow/stop commands"""
    cmd_type = command.get('type')
    identifier = command.get('identifier', '')
    msg_id = msg.get('id', '')

    if cmd_type == 'stop':
        # Find active deals where this user is follower
        deals = list(db.collection("tracker_deals")
                     .where("follower_email", "==", from_email)
                     .where("status", "==", "active")
                     .stream())
        stopped = 0
        for d in deals:
            db.collection("tracker_deals").document(d.id).update({
                "follow_mode": "stopped",
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
            stopped += 1
        print(f"    🛑 Tracker: stopped following {stopped} deals for {from_email}")
        # Send stop confirmation
        if access_token and rcb_email and msg_id:
            try:
                from lib.rcb_helpers import helper_graph_reply
                stop_html = '<div style="font-family:Arial;padding:20px;"><h3>Tracking Stopped</h3><p>You will no longer receive status updates for ' + str(stopped) + ' shipment(s).</p><p style="color:#888;font-size:12px;">Reply "follow [BL number]" to resume tracking.</p></div>'
                helper_graph_reply(access_token, rcb_email, msg_id, stop_html, to_email=from_email)
            except Exception as se:
                print(f"    Warning: Stop confirmation error: {se}")
        return {"status": "command_stop", "deals_stopped": stopped}

    elif cmd_type == 'follow':
        # Try to find deal by identifier (BOL, container, booking)
        deal = None
        if identifier:
            # Try BOL
            deal = _find_deal_by_field(db, 'bol_number', identifier)
            # Try container
            if not deal and re.match(r'^[A-Z]{4}\d{7}$', identifier):
                deal = _find_deal_by_container(db, identifier)
            # Try booking
            if not deal:
                deal = _find_deal_by_field(db, 'booking_number', identifier)

        if deal:
            db.collection("tracker_deals").document(deal.id).update({
                "follow_mode": "manual",
                "follower_email": from_email,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
            print(f"    👁️ Tracker: {from_email} now following deal {deal.id}")
            # Send current status email
            if access_token and rcb_email:
                try:
                    _send_tracker_email(db, deal.id, deal.to_dict(), access_token, rcb_email, "follow_started")
                except Exception as se:
                    print(f"    Warning: Follow status email error: {se}")
            return {"status": "command_follow", "deal_id": deal.id}
        else:
            # No existing deal — create a minimal one for tracking
            print(f"    👁️ Tracker: no deal found for '{identifier}', will create on next data")
            # Send "tracking started" notification
            if access_token and rcb_email and msg_id:
                try:
                    from lib.rcb_helpers import helper_graph_reply
                    pending_html = '<div style="font-family:Arial;padding:20px;"><h3>Tracking Started</h3><p>Now tracking: <b>' + str(identifier) + '</b></p><p>No data found yet. You will receive a status update as soon as port data becomes available.</p><p style="color:#888;font-size:12px;">Reply "stop following" to cancel.</p></div>'
                    helper_graph_reply(access_token, rcb_email, msg_id, pending_html, to_email=from_email)
                except Exception as se:
                    print(f"    Warning: Pending notification error: {se}")
            return {"status": "command_follow_pending", "identifier": identifier}

    return {"status": "command_unknown"}

# ════════════════════════════════════════════════════════
#  TASKYAM CLIENT
# ════════════════════════════════════════════════════════

class TaskYamClient:
    """Client for Israel Ports TaskYam API"""

    def __init__(self, get_secret_func, use_pilot=False):
        self.base_url = "https://pilot.israports.co.il/TaskYamWebAPI/" if use_pilot else "https://taskyam.israports.co.il/TaskYamWebAPI/"
        self.get_secret = get_secret_func
        self.token = None

    def login(self):
        """Login and get session token"""
        import requests
        try:
            username = self.get_secret("TASKYAM_USERNAME")
            password = self.get_secret("TASKYAM_PASSWORD")
            resp = requests.post(
                self.base_url + "api/Account/Login",
                json={"UserName": username, "Password": password},
                timeout=15
            )
            data = resp.json()
            if data.get("IsSuccess"):
                self.token = data.get("Token")
                return True
            return False
        except Exception as e:
            print(f"TaskYam login error: {e}")
            return False

    def logout(self):
        """Logout and release session"""
        import requests
        if self.token:
            try:
                requests.get(
                    self.base_url + "api/Account/Logout",
                    headers={"X-Session-Token": self.token},
                    timeout=10
                )
            except:
                pass
            self.token = None

    def _get(self, endpoint, params=None):
        """Make authenticated GET request"""
        import requests
        if not self.token:
            return None
        try:
            resp = requests.get(
                self.base_url + endpoint,
                headers={"X-Session-Token": self.token},
                params=params or {},
                timeout=20
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            print(f"TaskYam GET error ({endpoint}): {e}")
            return None

    def get_cargo_status(self, container=None, manifest=None, transaction_id=None, storage_id=None, port=None, notify=False):
        """Get cargo status — the core tracking endpoint"""
        params = {}
        if container:
            params['Container'] = container
        if manifest:
            params['ManifestNumber'] = manifest
        if transaction_id:
            params['TransactionID'] = transaction_id
        if storage_id:
            params['StorageID'] = storage_id
        if port:
            params['Port'] = port
        if notify:
            params['ReceiveNotification'] = 'true'
        return self._get("api/ContainerStatus/GetCargoStatus", params)

    def register_notifications(self, containers=None, transactions=None):
        """Register for PUSH cargo notifications"""
        import requests
        if not self.token:
            return None
        try:
            body = {}
            if containers:
                body['Containers'] = containers[:100]
            if transactions:
                body['Transactions'] = transactions[:100]
            resp = requests.post(
                self.base_url + "api/ContainerStatus/AddCargoNotification",
                headers={"X-Session-Token": self.token, "Content-Type": "application/json"},
                json=body,
                timeout=15
            )
            return resp.json() if resp.status_code == 200 else None
        except Exception as e:
            print(f"TaskYam notification error: {e}")
            return None

    def get_ship_details(self, lloyds_number=None, ship_id=None):
        """Get vessel details"""
        return self._get("api/CommunityTables/GetShipDetails", {
            'LloidsNumber': lloyds_number or '',
            'ShipId': ship_id or '',
            'StartDate': '',
            'EndDate': ''
        })

    def get_shipping_companies(self, agent_code=None, company_code=None, port_id=None):
        """Get shipping company details"""
        return self._get("api/CommunityTables/GetShippingCompanies", {
            'ShipAgentCode': agent_code or '',
            'CompanyCode': company_code or '',
            'PortID': port_id or ''
        })

# ════════════════════════════════════════════════════════
#  TASKYAM POLLER — poll active deals
# ════════════════════════════════════════════════════════

def tracker_poll_active_deals(db, firestore_module, get_secret_func, access_token=None, rcb_email=None):
    """
    Poll TaskYam for all active deals.
    Called by scheduler every 30 minutes.
    For each deal: query all containers, detect status changes, send updates.
    """
    try:
        # Get all active deals
        active_deals = list(db.collection("tracker_deals")
                           .where("status", "in", ["active", "pending"])
                           .stream())

        if not active_deals:
            print("🚢 Tracker poll: no active deals")
            return {"status": "ok", "deals": 0}

        # Login to TaskYam once
        client = TaskYamClient(get_secret_func)
        if not client.login():
            print("❌ Tracker poll: TaskYam login failed")
            return {"status": "error", "error": "taskyam_login_failed"}

        updated_deals = 0
        total_containers = 0

        for deal_doc in active_deals:
            deal = deal_doc.to_dict()
            deal_id = deal_doc.id

            # Skip stopped deals
            if deal.get('follow_mode') == 'stopped':
                continue

            containers = deal.get('containers', [])
            manifest = deal.get('manifest_number', '')
            transaction_ids = deal.get('transaction_ids', [])
            direction = deal.get('direction', '')

            deal_changed = False

            if containers:
                # FCL: query each container
                for cn in containers:
                    total_containers += 1
                    result = client.get_cargo_status(container=cn)

                    if result and result.get('CargoList'):
                        cargo = result['CargoList'][0]
                        changed = _update_container_status(
                            db, firestore_module, deal_id, cn, cargo, direction)
                        if changed:
                            deal_changed = True

                        # Enrich deal with TaskYam data
                        _enrich_deal_from_taskyam(db, deal_id, deal, cargo)

            elif manifest and transaction_ids:
                # General cargo: query by manifest + transaction
                for txn in transaction_ids:
                    result = client.get_cargo_status(
                        manifest=manifest, transaction_id=txn)
                    if result and result.get('CargoList'):
                        for cargo in result['CargoList']:
                            cn = cargo.get('ContainerID', txn)
                            changed = _update_container_status(
                                db, firestore_module, deal_id, cn, cargo, direction)
                            if changed:
                                deal_changed = True

            elif not deal.get('awb_number'):
                # General cargo without containers — try storage_id or manifest-only
                storage_id = deal.get('storage_id', '')
                result = None

                if storage_id:
                    result = client.get_cargo_status(storage_id=storage_id)
                elif manifest:
                    # manifest without transaction_ids — broad search
                    result = client.get_cargo_status(manifest=manifest)

                if result and result.get('CargoList'):
                    for cargo in result['CargoList']:
                        cn = cargo.get('ContainerID') or cargo.get('StorageID', '') or storage_id or 'general'
                        changed = _update_container_status(
                            db, firestore_module, deal_id, cn, cargo, direction)
                        if changed:
                            deal_changed = True
                        # Enrich deal — may backfill manifest + transaction_ids
                        # so next poll uses the more specific manifest+txn branch
                        _enrich_deal_from_taskyam(db, deal_id, deal, cargo)

            if deal_changed:
                updated_deals += 1
                # Send status update email
                if access_token and rcb_email:
                    try:
                        _send_tracker_email(db, deal_id, deal, access_token, rcb_email, "status_update")
                    except Exception as se:
                        print(f"    Warning: Tracker email send error: {se}")

        client.logout()

        print(f"🚢 Tracker poll: {len(active_deals)} deals, {total_containers} containers, {updated_deals} updated")
        return {"status": "ok", "deals": len(active_deals), "containers": total_containers, "updated": updated_deals}

    except Exception as e:
        print(f"❌ Tracker poll error: {e}")
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


def _update_container_status(db, firestore_module, deal_id, container_id, cargo, direction):
    """Update container status from TaskYam response, return True if changed"""
    doc_id = f"{deal_id}_{container_id}"
    doc_ref = db.collection("tracker_container_status").document(doc_id)
    doc = doc_ref.get()
    now = datetime.now(timezone.utc).isoformat()

    import_process = cargo.get('ImportProcess', {})
    export_process = cargo.get('ExportProcess', {})

    # Determine current step
    new_step = _derive_current_step(import_process if direction != 'export' else {}, 
                                      export_process if direction != 'import' else {})

    if doc.exists:
        old_data = doc.to_dict()
        old_step = old_data.get('current_step', '')

        # Detect change
        changed = (old_step != new_step)

        doc_ref.update({
            "import_process": import_process or {},
            "export_process": export_process or {},
            "current_step": new_step,
            "last_taskyam_check": now,
            "container_type": cargo.get('ContainerType', ''),
            "weight": cargo.get('Weight', ''),
            "arrival_time": cargo.get('ArrivalTime', ''),
            "exit_time": cargo.get('ExitTime', ''),
            "taskyam_raw": {
                "ShipName": cargo.get('ShipName', ''),
                "ShipAgentName": cargo.get('ShipAgentName', ''),
                "CustomsDeclaration": cargo.get('CustomsDeclaration', ''),
                "TransportCompanyName": cargo.get('TransportCompanyName', ''),
                "FreightKind": cargo.get('FreightKind', ''),
                "Port": cargo.get('Port', {}),
                "ManifestNumber": cargo.get('ManifestNumber', ''),
                "TransactionIDList": cargo.get('TransactionIDList', []),
            },
            "updated_at": now,
        })

        if changed:
            _log_timeline(db, firestore_module, deal_id, {
                "event_type": "status_change",
                "source": "taskyam_api",
                "container_id": container_id,
                "old_step": old_step,
                "new_step": new_step,
            })
            print(f"    📦 {container_id}: {old_step} → {new_step}")

        return changed
    else:
        # Create new
        doc_ref.set({
            "deal_id": deal_id,
            "container_id": container_id,
            "import_process": import_process or {},
            "export_process": export_process or {},
            "current_step": new_step,
            "last_taskyam_check": now,
            "container_type": cargo.get('ContainerType', ''),
            "weight": cargo.get('Weight', ''),
            "arrival_time": cargo.get('ArrivalTime', ''),
            "exit_time": cargo.get('ExitTime', ''),
            "taskyam_raw": {},
            "created_at": now,
            "updated_at": now,
        })
        return True


def _derive_current_step(import_proc, export_proc):
    """Derive the current step from process dates (latest step with a date)"""
    import_proc = import_proc or {}
    export_proc = export_proc or {}
    # Import steps in order
    import_steps = [
        ('cargo_exit', 'CargoExitDate'),
        ('cargo_exit_response', 'CargoExitResponseDate'),
        ('cargo_exit_request', 'CargoExitRequestDate'),
        ('escort_certificate', 'EscortCertificateDate'),
        ('port_release', 'PortReleaseDate'),
        ('hani_release', 'HaniReleaseDate'),
        ('customs_release', 'CustomsReleaseDate'),
        ('customs_check_response', 'CustomsCheckResponseDate'),
        ('customs_check', 'CustomsCheckDate'),
        ('delivery_order', 'DeliveryOrderDate'),
        ('port_unloading', 'PortUnloadingDate'),
        ('manifest', 'ManifestDate'),
    ]

    export_steps = [
        ('ship_sailing', 'ShipSailingDate'),
        ('cargo_loading', 'CargoLoadingDate'),
        ('cargo_entry', 'CargoEntryDate'),
        ('customs_release', 'CustomsReleaseDate'),
        ('logistical_permit', 'LogisticalPermitDate'),
        ('customs_check_response', 'CustomsCheckResponseDate'),
        ('customs_check', 'CustomsCheckDate'),
        ('port_transport_feedback', 'PortTransportationCompanyFeedbackDate'),
        ('driver_assignment', 'DriverAssignmentDate'),
        ('storage_to_customs', 'StorageIDToCustomsDate'),
        ('port_storage_feedback', 'PortStorageFeedbackDate'),
        ('storage_id', 'StorageIDDate'),
    ]

    # Check import process (reverse order — latest first)
    for step_name, date_field in import_steps:
        if import_proc.get(date_field):
            return step_name

    # Check export process
    for step_name, date_field in export_steps:
        if export_proc.get(date_field):
            return step_name

    return 'pending'


def _enrich_deal_from_taskyam(db, deal_id, deal, cargo):
    """Enrich deal record with data from TaskYam response"""
    updates = {}

    if not deal.get('vessel_name') and cargo.get('ShipName'):
        updates['vessel_name'] = cargo['ShipName']
    if not deal.get('manifest_number') and cargo.get('ManifestNumber'):
        updates['manifest_number'] = cargo['ManifestNumber']
    if not deal.get('ship_agent_code') and cargo.get('ShipAgentCode'):
        updates['ship_agent_code'] = cargo['ShipAgentCode']
    if not deal.get('customs_declaration') and cargo.get('CustomsDeclaration'):
        updates['customs_declaration'] = cargo['CustomsDeclaration']
    if not deal.get('port') and cargo.get('Port', {}).get('UNLocode'):
        updates['port'] = cargo['Port']['UNLocode']
        updates['port_name'] = cargo['Port'].get('NameEng', '')

    # Mark as transmitted to TaskYam
    if not deal.get('taskyam_transmitted') and cargo.get('ManifestNumber'):
        updates['taskyam_transmitted'] = True

    # Merge transaction IDs from TaskYam
    txn_list = cargo.get('TransactionIDList', [])
    existing_txns = deal.get('transaction_ids', [])
    for txn in txn_list:
        if txn and txn not in existing_txns:
            existing_txns.append(txn)
            updates['transaction_ids'] = existing_txns

    if updates:
        updates['updated_at'] = datetime.now(timezone.utc).isoformat()
        db.collection("tracker_deals").document(deal_id).update(updates)

# ════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ════════════════════════════════════════════════════════

def _log_timeline(db, firestore_module, deal_id, event_data):
    """Log event to deal timeline"""
    try:
        event_data["deal_id"] = deal_id
        event_data["timestamp"] = datetime.now(timezone.utc).isoformat()
        db.collection("tracker_timeline").add(event_data)
    except Exception as e:
        print(f"Timeline log error: {e}")


def _make_obs_id(msg_id):
    """Generate observation ID from message ID"""
    return "trk_" + hashlib.md5(str(msg_id).encode()).hexdigest()


def _decode_header(header_str):
    """Decode email header (handles encoded words)"""
    if not header_str:
        return ""
    try:
        import email.header
        decoded_parts = email.header.decode_header(header_str)
        result = ""
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result += part.decode(charset or 'utf-8', errors='replace')
            else:
                result += part
        return result
    except:
        return str(header_str)


def _strip_html(html):
    """Remove HTML tags and decode entities"""
    if not html:
        return ""
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&#39;', "'", text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()




def _guess_doc_type_from_attachments(attachment_names):
    """Guess primary document type from attachment filenames"""
    if not attachment_names:
        return ''
    for name in attachment_names:
        n = name.lower()
        if any(x in n for x in ['packing', 'pack_list', 'pl_']):
            return 'packing_list'
        if any(x in n for x in ['invoice', 'inv_', 'ci_', 'commercial']):
            return 'invoice'
        if any(x in n for x in ['bill_of_lading', 'b_l', 'bol', 'bl_', 'lading']):
            return 'bill_of_lading'
        if any(x in n for x in ['delivery', 'do_', 'release']):
            return 'delivery_order'
        if any(x in n for x in ['certif', 'cert_', 'coo', 'phyto', 'health']):
            return 'certificate'
        if any(x in n for x in ['arrival', 'notice', 'noa']):
            return 'arrival_notice'
    return ''

def _classify_sender(email_addr):
    """Classify sender by domain"""
    if not email_addr:
        return 'unknown'
    domain = email_addr.lower().split('@')[-1] if '@' in email_addr else ''
    for sender_type, domains in LOGISTICS_SENDERS.items():
        for d in domains:
            if domain.endswith(d):
                return sender_type
    return 'external'


# ══════════════════════════════════════════════════════════
#  EMAIL OUTPUT — send status updates via threaded reply
# ══════════════════════════════════════════════════════════

def _send_tracker_email(db, deal_id, deal, access_token, rcb_email, update_type="status_update",
                        observation=None, extractions=None):
    """Build and send tracker status email for a deal. v2: sea + air aware."""
    try:
        from lib.tracker_email import build_tracker_status_email
        from lib.rcb_helpers import helper_graph_reply, helper_graph_send

        # Get all container statuses for this deal (sea freight only)
        containers = deal.get('containers', [])
        container_statuses = []
        for cn in containers:
            doc = db.collection("tracker_container_status").document(f"{deal_id}_{cn}").get()
            if doc.exists:
                container_statuses.append(doc.to_dict())

        # Build email (v2: with observation context)
        email_data = build_tracker_status_email(
            deal, container_statuses, update_type,
            observation=observation, extractions=extractions)
        subject = email_data['subject']
        body_html = email_data['body_html']

        follower = deal.get('follower_email', '')
        cc_list = deal.get('cc_list', [])

        if not follower:
            print(f"    ⚠️ Tracker: no follower for deal {deal_id}, skipping email")
            return False

        sent = False

        # Try threaded reply first (needs original msg_id from observation)
        source_obs_ids = deal.get('source_emails', [])
        original_msg_id = None
        if source_obs_ids:
            latest_obs = db.collection("tracker_observations").document(source_obs_ids[-1]).get()
            if latest_obs.exists:
                original_msg_id = latest_obs.to_dict().get('msg_id', '')

        if original_msg_id and access_token:
            sent = helper_graph_reply(
                access_token, rcb_email, original_msg_id,
                body_html, to_email=follower, cc_emails=cc_list
            )

        # Fallback: send as new email
        if not sent and access_token:
            sent = helper_graph_send(
                access_token, rcb_email, follower,
                subject, body_html
            )

        if sent:
            _log_timeline(db, None, deal_id, {
                "event_type": "email_sent",
                "update_type": update_type,
                "to": follower,
                "subject": subject[:100],
            })
            print(f"    ✉️ Tracker email sent for deal {deal_id} to {follower}")
        else:
            print(f"    ⚠️ Tracker email FAILED for deal {deal_id}")

        return sent

    except Exception as e:
        print(f"    ❌ Tracker email error: {e}")
        import traceback
        traceback.print_exc()
        return False



# tracker_poll_active_shipments is the old v1 name
# Alias to new function for main.py compatibility
def tracker_poll_active_shipments(db, firestore_module, get_secret_func, access_token=None, rcb_email=None):
    """v1 compatibility alias"""
    return tracker_poll_active_deals(db, firestore_module, get_secret_func, access_token, rcb_email)
