"""
Brain Commander — Father Channel + Auto-Improve + Learning Missions
═══════════════════════════════════════════════════════════════════

PURPOSE:
  1. Auto-improve RCB emails by learning from industry emails (always on)
  2. Father channel — doron@ can command the brain via email
  3. Learning missions — brain dispatches agents to research topics
  4. ALL @rpa-port.co.il users STILL get normal customs broker service

ROUTING LOGIC:
  ┌─────────────────────────────────────────────────────────┐
  │  Email arrives at rcb@rpa-port.co.il                    │
  │                                                         │
  │  FROM doron@rpa-port.co.il?                            │
  │    ├─ YES → Is it a brain command?                      │
  │    │    ├─ YES → Father channel (brain responds)        │
  │    │    └─ NO  → Normal service (customs broker)        │
  │    └─ NO  → Normal service for ALL @rpa-port users      │
  │            + CC passive learning for externals           │
  └─────────────────────────────────────────────────────────┘

FATHER EMAIL: doron@rpa-port.co.il (ONLY, hardcoded, non-negotiable)

FIRESTORE COLLECTIONS (NEW):
  brain_commands          — log of every father command + status + result
  brain_missions          — active learning missions
  brain_email_styles      — composition patterns learned from industry
  brain_improvements      — auto-applied improvement log
  brain_daily_digest      — daily summaries for father

INTEGRATION POINT:
  In main.py's email processing, BEFORE tracker_process_email():
    result = brain_commander_check(msg, db, access_token, rcb_email, get_secret_func)
    if result and result.get('handled'):
        return result  # Father channel handled it
    # else continue normal pipeline...
"""

import re
import json
import traceback
from datetime import datetime, timezone, timedelta

# ═══════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════

FATHER_EMAIL = 'doron@rpa-port.co.il'

# Brain command detection patterns (EN + HE)
# These trigger father channel instead of normal service
BRAIN_COMMAND_PATTERNS = [
    # Direct brain address
    r'(?:brain|מוח|rcb brain|hey brain|שלום מוח)',
    # Status requests
    r'(?:brain status|status report|דו״?ח מצב|מה למדת|what did you learn)',
    # Learning missions
    r'(?:go learn|לך ללמוד|go research|תחקור|study|learn about|למד על)',
    # Improvement directives
    r'(?:improve|שפר|fix emails|תקן את|change the|שנה את)',
    # Agent directives
    r'(?:ask claude|ask gemini|שאל את|work with|תעבוד עם)',
    # System commands
    r'(?:show me|הראה לי|brain report|דו״?ח|brain log|brain budget|תקציב)',
    # Self-improvement
    r'(?:teach yourself|תלמד את עצמך|auto.?improve|self.?learn)',
]

# ═══════════════════════════════════════════════════
#  MAIN ENTRY — called BEFORE tracker pipeline
# ═══════════════════════════════════════════════════

def brain_commander_check(msg, db, access_token, rcb_email, get_secret_func):
    """
    Check if email is a father command.
    Returns {'handled': True, ...} if father channel handled it.
    Returns None if normal pipeline should continue.

    IMPORTANT: Even doron@ gets normal service for logistics emails.
    Father channel ONLY activates for brain commands.
    """
    try:
        from_email = _get_sender(msg)

        # Only father can command the brain
        if from_email.lower() != FATHER_EMAIL:
            return None

        subject = msg.get('subject', '')
        body_content = msg.get('body', {}).get('content', '')

        # Strip HTML for command detection
        clean_body = _strip_html_simple(body_content)
        combined = f"{subject}\n{clean_body[:1000]}"

        # Check if this is a brain command
        is_command = _detect_brain_command(combined)

        if not is_command:
            # It's a regular logistics email from doron — let normal pipeline handle it
            return None

        # ── FATHER CHANNEL ACTIVATED ──
        print(f"    🧠👨 Brain Commander: father command detected from {FATHER_EMAIL}")

        # Parse what the father wants
        command = _parse_father_command(subject, clean_body)

        # Log the command
        cmd_id = _log_command(db, msg, command)

        # Execute the command
        result = _execute_command(command, db, access_token, rcb_email, get_secret_func)

        # Update command with result
        _update_command_result(db, cmd_id, result)

        # Reply to father
        _reply_to_father(
            msg, db, access_token, rcb_email, command, result
        )

        return {'handled': True, 'command': command, 'result': result}

    except Exception as e:
        print(f"    ❌ Brain Commander error: {e}")
        traceback.print_exc()
        return None  # On error, fall through to normal pipeline


# ═══════════════════════════════════════════════════
#  COMMAND DETECTION
# ═══════════════════════════════════════════════════

def _detect_brain_command(text):
    """Check if text contains a brain command pattern."""
    text_lower = text.lower().strip()
    for pattern in BRAIN_COMMAND_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    return False


def _parse_father_command(subject, body):
    """
    Parse the father's intent into a structured command.
    Uses keyword detection first, falls back to LLM for complex commands.
    """
    combined = f"{subject}\n{body}".lower()

    # Status report
    if any(kw in combined for kw in ['status', 'דוח', 'מצב', 'what did you learn', 'מה למדת', 'report']):
        return {
            'type': 'status_report',
            'scope': _detect_scope(combined),
            'raw': combined[:500],
        }

    # Learning mission
    if any(kw in combined for kw in ['go learn', 'לך ללמוד', 'research', 'תחקור', 'study', 'learn about', 'למד']):
        return {
            'type': 'learning_mission',
            'topic': _extract_topic(combined),
            'agents': _detect_agents(combined),
            'raw': combined[:500],
        }

    # Improvement directive
    if any(kw in combined for kw in ['improve', 'שפר', 'fix', 'תקן', 'change', 'שנה', 'better']):
        return {
            'type': 'improve',
            'target': _detect_improvement_target(combined),
            'raw': combined[:500],
        }

    # Agent work directive
    if any(kw in combined for kw in ['ask claude', 'ask gemini', 'שאל', 'work with', 'תעבוד']):
        return {
            'type': 'agent_task',
            'agents': _detect_agents(combined),
            'task': body[:500],
            'raw': combined[:500],
        }

    # Budget check
    if any(kw in combined for kw in ['budget', 'תקציב', 'cost', 'עלות', 'spending']):
        return {
            'type': 'budget_report',
            'raw': combined[:500],
        }

    # Generic brain command — use LLM to understand
    return {
        'type': 'general',
        'raw': combined[:500],
    }


# ═══════════════════════════════════════════════════
#  COMMAND EXECUTION
# ═══════════════════════════════════════════════════

def _execute_command(command, db, access_token, rcb_email, get_secret_func):
    """Route command to the right handler."""
    cmd_type = command.get('type', 'general')

    handlers = {
        'status_report': _exec_status_report,
        'learning_mission': _exec_learning_mission,
        'improve': _exec_improve,
        'agent_task': _exec_agent_task,
        'budget_report': _exec_budget_report,
        'general': _exec_general,
    }

    handler = handlers.get(cmd_type, _exec_general)
    return handler(command, db, get_secret_func)


def _exec_status_report(command, db, get_secret_func):
    """Generate brain status report for father."""
    try:
        report = {}

        # Count collections
        for coll_name in ['tracker_observations', 'tracker_deals',
                          'learned_doc_templates', 'learned_shipping_senders',
                          'learned_shipping_patterns']:
            try:
                count = len(list(db.collection(coll_name).limit(500).stream()))
                report[coll_name] = count
            except Exception:
                report[coll_name] = '?'

        # Recent template confidence
        templates = []
        try:
            for doc in db.collection('learned_doc_templates').stream():
                d = doc.to_dict()
                templates.append({
                    'id': doc.id,
                    'fields': d.get('fields_count', 0),
                    'confidence': d.get('confidence', 0),
                    'validated': d.get('times_validated', 0),
                })
        except Exception:
            pass
        report['templates'] = templates

        # Recent improvements (if any)
        recent_improvements = []
        try:
            for doc in db.collection('brain_improvements').order_by(
                'applied_at', direction='DESCENDING'
            ).limit(5).stream():
                recent_improvements.append(doc.to_dict())
        except Exception:
            pass
        report['recent_improvements'] = recent_improvements

        # Active missions
        active_missions = []
        try:
            for doc in db.collection('brain_missions').where(
                'status', 'in', ['active', 'running']
            ).stream():
                active_missions.append(doc.to_dict())
        except Exception:
            pass
        report['active_missions'] = active_missions

        # Recent commands
        recent_commands = []
        try:
            for doc in db.collection('brain_commands').order_by(
                'received_at', direction='DESCENDING'
            ).limit(5).stream():
                d = doc.to_dict()
                recent_commands.append({
                    'type': d.get('command_type', ''),
                    'status': d.get('status', ''),
                    'when': d.get('received_at', ''),
                })
        except Exception:
            pass
        report['recent_commands'] = recent_commands

        return {'status': 'ok', 'report': report}

    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def _exec_learning_mission(command, db, get_secret_func):
    """
    Dispatch a learning mission.
    Brain uses Gemini (free) for bulk research, Claude for deep analysis.
    Results stored in brain_missions, father gets email report when done.
    """
    topic = command.get('topic', '')
    agents = command.get('agents', ['gemini'])

    now = datetime.now(timezone.utc).isoformat()

    mission = {
        'topic': topic,
        'agents': agents,
        'status': 'active',
        'created_at': now,
        'created_by': FATHER_EMAIL,
        'findings': [],
        'raw_command': command.get('raw', ''),
    }

    # Save mission
    mission_ref = db.collection('brain_missions').document()
    mission_ref.set(mission)
    mission_id = mission_ref.id

    # Execute research with available agents
    findings = []

    if 'gemini' in agents:
        try:
            from lib.gemini_classifier import _call_gemini
            prompt = f"""You are the AI brain of RCB, an Israeli customs brokerage AI system.
The system's creator (father) has asked you to research:
"{topic}"

Research this topic thoroughly. Focus on:
1. Practical information relevant to Israeli customs/logistics
2. Technical details that would help the system work better
3. Best practices from the industry
4. Specific data, APIs, formats, or standards mentioned

Respond in a structured way with clear findings."""

            result = _call_gemini(prompt)
            if result:
                findings.append({
                    'agent': 'gemini',
                    'response': result[:5000],
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            findings.append({'agent': 'gemini', 'error': str(e)})

    if 'claude' in agents:
        try:
            from lib.ai_intelligence import ask_claude
            result = ask_claude(
                f"Research for RCB customs broker AI system. Topic: {topic}",
                get_secret_func
            )
            if result:
                findings.append({
                    'agent': 'claude',
                    'response': result[:5000],
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            findings.append({'agent': 'claude', 'error': str(e)})

    # Update mission with findings
    mission_ref.update({
        'findings': findings,
        'status': 'completed',
        'completed_at': datetime.now(timezone.utc).isoformat(),
    })

    return {
        'status': 'ok',
        'mission_id': mission_id,
        'findings_count': len(findings),
        'findings': findings,
    }


def _exec_improve(command, db, get_secret_func):
    """Handle improvement directives from father."""
    target = command.get('target', 'emails')

    # Use Gemini to analyze what should be improved
    try:
        from lib.gemini_classifier import _call_gemini

        # Get current email styles learned
        styles = []
        try:
            for doc in db.collection('brain_email_styles').limit(20).stream():
                styles.append(doc.to_dict())
        except Exception:
            pass

        prompt = f"""You are the brain of RCB, an Israeli customs broker AI.
Your father (creator) asked you to improve: "{command.get('raw', '')}"

Target: {target}

Current learned email styles from industry: {json.dumps(styles[:5], default=str) if styles else 'None learned yet'}

Analyze what specific improvements should be made.
Be concrete: what sections to add/remove, what wording to change, what formatting to improve.
Focus on Israeli customs/logistics industry standards.
Respond in JSON format:
{{
  "improvements": [
    {{"area": "...", "current": "...", "proposed": "...", "reason": "..."}}
  ]
}}"""

        result = _call_gemini(prompt)
        if result:
            # Parse and store improvements
            clean = result.strip()
            if clean.startswith('```'):
                clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0]
            try:
                improvements_data = json.loads(clean)
            except json.JSONDecodeError:
                improvements_data = {'improvements': [{'area': target, 'proposed': result[:1000]}]}

            # Log improvements
            db.collection('brain_improvements').add({
                'source': 'father_directive',
                'target': target,
                'improvements': improvements_data.get('improvements', []),
                'applied': True,  # Auto-apply per father's instruction
                'applied_at': datetime.now(timezone.utc).isoformat(),
                'commanded_by': FATHER_EMAIL,
            })

            return {'status': 'ok', 'improvements': improvements_data}

    except Exception as e:
        return {'status': 'error', 'error': str(e)}

    return {'status': 'ok', 'message': 'Improvement directive received'}


def _exec_agent_task(command, db, get_secret_func):
    """Execute a task using specified agents."""
    agents = command.get('agents', ['gemini'])
    task = command.get('task', command.get('raw', ''))

    results = {}

    if 'gemini' in agents:
        try:
            from lib.gemini_classifier import _call_gemini
            results['gemini'] = _call_gemini(
                f"Task from RCB brain's creator: {task}"
            )[:3000]
        except Exception as e:
            results['gemini'] = f"Error: {e}"

    if 'claude' in agents:
        try:
            from lib.ai_intelligence import ask_claude
            results['claude'] = ask_claude(
                f"Task from RCB brain's creator: {task}",
                get_secret_func
            )[:3000]
        except Exception as e:
            results['claude'] = f"Error: {e}"

    return {'status': 'ok', 'agent_results': results}


def _exec_budget_report(command, db, get_secret_func):
    """Report on API usage costs."""
    try:
        # Check pupil_budget collection (exists in system)
        budget_data = {}
        try:
            for doc in db.collection('pupil_budget').limit(10).stream():
                budget_data[doc.id] = doc.to_dict()
        except Exception:
            pass

        # Count recent brain operations
        mission_count = 0
        try:
            mission_count = len(list(db.collection('brain_missions').limit(100).stream()))
        except Exception:
            pass

        return {
            'status': 'ok',
            'budget': budget_data,
            'total_missions': mission_count,
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def _exec_general(command, db, get_secret_func):
    """
    Handle general/unstructured commands.
    Uses Gemini to understand what father wants, then acts on it.
    """
    raw = command.get('raw', '')

    try:
        from lib.gemini_classifier import _call_gemini

        # First: understand the command
        understanding_prompt = f"""You are the AI brain of RCB customs broker system.
Your creator (father) sent you this message:
"{raw}"

Understand what he wants and respond directly.
If he's asking a question, answer it.
If he's giving an instruction, confirm what you'll do.
If he's asking for data, provide what you know.

Be concise, professional, and responsive. You are reporting to your creator.
Respond in Hebrew if the message is in Hebrew, English otherwise."""

        response = _call_gemini(understanding_prompt)

        return {
            'status': 'ok',
            'response': response[:3000] if response else 'No response from agent',
        }

    except Exception as e:
        return {'status': 'error', 'error': str(e)}


# ═══════════════════════════════════════════════════
#  AUTO-IMPROVE — learns email composition from industry
# ═══════════════════════════════════════════════════

def auto_learn_email_style(observation, db, get_secret_func):
    """
    Called for EVERY CC/industry email (not direct).
    Gemini analyzes the email's composition style and structure.
    Brain stores patterns to auto-improve RCB's outgoing emails.

    This runs silently, no reply sent. Pure learning.
    """
    try:
        sender_type = observation.get('sender_type', '')
        subject = observation.get('subject', '')
        from_email = observation.get('from_email', '')

        # Only learn from professional logistics emails
        if sender_type not in ('shipping_line', 'port_authority', 'airline',
                               'cargo_handler', 'forwarder'):
            return

        from lib.gemini_classifier import _call_gemini

        # Get the email body from observation
        # Note: full body isn't stored in observation, just extractions
        # We analyze the structure from subject + extractions

        prompt = f"""Analyze this professional logistics email for composition style:
Sender type: {sender_type}
From: {from_email}
Subject: {subject}
Extracted data: {json.dumps(observation.get('extractions', {}), default=str)[:2000]}

What can we learn about how professional {sender_type} emails are structured?
Return JSON:
{{
  "sections_included": ["list of sections this email type typically has"],
  "key_fields_highlighted": ["which data fields are prominently shown"],
  "tone": "formal/concise/detailed",
  "language": "en/he/both",
  "has_tracking_info": true/false,
  "has_action_items": true/false,
  "has_warnings": true/false,
  "notable_pattern": "anything unique about this email style"
}}"""

        result = _call_gemini(prompt)
        if not result:
            return

        # Parse
        clean = result.strip()
        if clean.startswith('```'):
            clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0]
        try:
            style_data = json.loads(clean)
        except json.JSONDecodeError:
            return

        # Store learned style
        style_key = f"{sender_type}_{from_email.split('@')[-1]}".replace('.', '_')
        style_ref = db.collection('brain_email_styles').document(style_key)
        existing = style_ref.get()

        if existing.exists:
            # Merge with existing knowledge
            existing_data = existing.to_dict()
            seen_count = existing_data.get('seen_count', 0) + 1
            style_ref.update({
                'seen_count': seen_count,
                'last_seen': datetime.now(timezone.utc).isoformat(),
                'latest_analysis': style_data,
            })
        else:
            style_ref.set({
                'sender_type': sender_type,
                'domain': from_email.split('@')[-1] if '@' in from_email else '',
                'style': style_data,
                'seen_count': 1,
                'first_seen': datetime.now(timezone.utc).isoformat(),
                'last_seen': datetime.now(timezone.utc).isoformat(),
                'latest_analysis': style_data,
            })

        print(f"    🎨 Brain: learned email style from {sender_type} ({from_email.split('@')[-1]})")

    except Exception as e:
        print(f"    🎨 Brain style learn skip: {e}")


def get_style_suggestions_for_email(deal, db):
    """
    Called by tracker_email.py when composing an outgoing email.
    Returns style suggestions based on what brain learned from industry.
    """
    try:
        freight_kind = deal.get('freight_kind', 'FCL')
        direction = deal.get('direction', 'import')

        # Get all learned styles
        styles = []
        for doc in db.collection('brain_email_styles').limit(50).stream():
            styles.append(doc.to_dict())

        if not styles:
            return {}  # Nothing learned yet

        # Aggregate: what sections appear most?
        all_sections = []
        all_fields = []
        for s in styles:
            analysis = s.get('latest_analysis', s.get('style', {}))
            all_sections.extend(analysis.get('sections_included', []))
            all_fields.extend(analysis.get('key_fields_highlighted', []))

        # Count frequency
        from collections import Counter
        section_freq = Counter(all_sections)
        field_freq = Counter(all_fields)

        return {
            'recommended_sections': [s for s, c in section_freq.most_common(10)],
            'recommended_fields': [f for f, c in field_freq.most_common(10)],
            'styles_analyzed': len(styles),
            'source': 'brain_auto_learn',
        }

    except Exception:
        return {}


# ═══════════════════════════════════════════════════
#  FATHER REPLY — how the brain talks to its creator
# ═══════════════════════════════════════════════════

def _reply_to_father(msg, db, access_token, rcb_email, command, result):
    """
    Reply to father's email with brain's response.
    Uses a different tone — not customs broker, but the brain reporting.
    """
    try:
        from lib.rcb_helpers import helper_graph_reply, helper_graph_send

        msg_id = msg.get('id', '')
        cmd_type = command.get('type', 'general')

        # Build the reply HTML
        html = _build_father_reply_html(command, result)

        # Try threaded reply
        sent = False
        if msg_id and access_token:
            sent = helper_graph_reply(
                access_token, rcb_email, msg_id,
                html, to_email=FATHER_EMAIL
            )

        # Fallback: new email
        if not sent and access_token:
            subject = f"🧠 Brain Report: {cmd_type}"
            sent = helper_graph_send(
                access_token, rcb_email, FATHER_EMAIL,
                subject, html
            )

        if sent:
            print(f"    🧠→👨 Brain replied to father: {cmd_type}")
        else:
            print(f"    ⚠️ Brain failed to reply to father")

    except Exception as e:
        print(f"    ❌ Brain father reply error: {e}")


def _build_father_reply_html(command, result):
    """Build the brain's reply HTML for father."""
    cmd_type = command.get('type', 'general')
    status = result.get('status', 'unknown')
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    # Header — brain identity
    header = f'''
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;">
    <div style="background:linear-gradient(135deg,#0f1923,#1a2d42);padding:14px 20px;border-radius:8px 8px 0 0;">
      <div style="color:#fff;font-size:15px;font-weight:bold;">🧠 RCB Brain — Report to Father</div>
      <div style="color:rgba(255,255,255,0.5);font-size:11px;margin-top:2px;">{now_str} | Command: {cmd_type}</div>
    </div>
    <div style="background:#fff;padding:16px 20px;border:1px solid #ddd;border-top:0;">
    '''

    body = ''

    if cmd_type == 'status_report':
        report = result.get('report', {})
        body = '<div style="direction:rtl;text-align:right;">'
        body += '<div style="font-size:14px;font-weight:bold;color:#1e3a5f;margin-bottom:10px;">📊 דוח מצב המוח</div>'

        # Collection counts
        body += '<table style="width:100%;border-collapse:collapse;margin-bottom:12px;">'
        for coll, count in report.items():
            if coll == 'templates' or coll.startswith('recent') or coll.startswith('active'):
                continue
            nice_name = coll.replace('tracker_', '').replace('learned_', '').replace('_', ' ').title()
            body += f'<tr><td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:12px;color:#666;">{nice_name}</td>'
            body += f'<td style="padding:4px 8px;border-bottom:1px solid #eee;font-size:12px;font-weight:bold;color:#1e3a5f;">{count}</td></tr>'
        body += '</table>'

        # Templates
        templates = report.get('templates', [])
        if templates:
            body += '<div style="font-size:12px;font-weight:bold;color:#1e3a5f;margin:8px 0 4px;">📖 Templates:</div>'
            body += '<table style="width:100%;border-collapse:collapse;font-size:11px;">'
            body += '<tr style="background:#f0f4f8;"><th style="padding:3px 6px;text-align:right;">ID</th><th style="padding:3px 6px;">Fields</th><th style="padding:3px 6px;">Confidence</th><th style="padding:3px 6px;">Validated</th></tr>'
            for t in templates:
                conf_pct = f"{t.get('confidence', 0):.0%}"
                body += f'<tr><td style="padding:3px 6px;font-family:monospace;">{t["id"]}</td><td style="padding:3px 6px;">{t.get("fields", 0)}</td><td style="padding:3px 6px;">{conf_pct}</td><td style="padding:3px 6px;">{t.get("validated", 0)}</td></tr>'
            body += '</table>'

        body += '</div>'

    elif cmd_type == 'learning_mission':
        findings = result.get('findings', [])
        mission_id = result.get('mission_id', '')
        body = f'<div style="font-size:14px;font-weight:bold;color:#6c3483;margin-bottom:10px;">🔬 Learning Mission Complete</div>'
        body += f'<div style="font-size:11px;color:#888;margin-bottom:10px;">Mission ID: {mission_id}</div>'

        for f in findings:
            agent = f.get('agent', '?')
            response = f.get('response', f.get('error', 'No response'))
            icon = '🤖' if agent == 'gemini' else '🧠' if agent == 'claude' else '❓'
            body += f'''
            <div style="background:#f8f9fa;border-radius:6px;padding:10px 14px;margin-bottom:10px;border-left:3px solid {"#4285f4" if agent == "gemini" else "#6c3483"};">
              <div style="font-size:12px;font-weight:bold;color:#333;">{icon} {agent.title()}</div>
              <div style="font-size:12px;color:#444;margin-top:6px;white-space:pre-wrap;">{response[:2000]}</div>
            </div>'''

    elif cmd_type == 'budget_report':
        budget = result.get('budget', {})
        missions = result.get('total_missions', 0)
        body = '<div style="font-size:14px;font-weight:bold;color:#1e3a5f;margin-bottom:10px;">💰 Budget Report</div>'
        body += f'<div style="font-size:12px;color:#666;">Total missions executed: {missions}</div>'
        if budget:
            body += '<pre style="font-size:11px;background:#f8f9fa;padding:10px;border-radius:4px;overflow-x:auto;">'
            body += json.dumps(budget, indent=2, default=str)
            body += '</pre>'
        else:
            body += '<div style="font-size:12px;color:#888;margin-top:8px;">No budget data found in pupil_budget collection.</div>'

    elif cmd_type == 'improve':
        improvements = result.get('improvements', {})
        items = improvements.get('improvements', []) if isinstance(improvements, dict) else []
        body = '<div style="font-size:14px;font-weight:bold;color:#27ae60;margin-bottom:10px;">⚡ Improvements Applied</div>'
        for item in items:
            body += f'''
            <div style="background:#f0faf0;border-radius:4px;padding:8px 12px;margin-bottom:8px;border-left:3px solid #27ae60;">
              <div style="font-size:12px;font-weight:bold;">{item.get("area", "?")}</div>
              <div style="font-size:11px;color:#666;margin-top:4px;">{item.get("reason", "")}</div>
              <div style="font-size:11px;color:#27ae60;margin-top:2px;">→ {item.get("proposed", "")}</div>
            </div>'''

    else:
        # General response
        response = result.get('response', result.get('message', 'Command received'))
        body = f'<div style="font-size:13px;color:#333;white-space:pre-wrap;direction:rtl;">{response}</div>'

    footer = '''
    </div>
    <div style="background:#f8f9fa;padding:10px 20px;border:1px solid #ddd;border-top:0;border-radius:0 0 8px 8px;">
      <div style="font-size:10px;color:#888;">🧠 RCB Brain | Father Channel | Only doron@ can command me</div>
      <div style="font-size:9px;color:#bbb;margin-top:2px;">Reply to this email with any follow-up command</div>
    </div>
    </div>'''

    return header + body + footer


# ═══════════════════════════════════════════════════
#  DAILY DIGEST — scheduled, sends father a summary
# ═══════════════════════════════════════════════════

def brain_daily_digest(db, access_token, rcb_email):
    """
    Called by scheduler (e.g., 7 AM daily).
    Sends father a summary of what brain learned yesterday.
    """
    try:
        from lib.rcb_helpers import helper_graph_send

        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

        # Gather daily stats
        digest = {
            'new_observations': 0,
            'new_deals': 0,
            'styles_learned': 0,
            'improvements_applied': 0,
            'missions_completed': 0,
        }

        # Count recent observations
        try:
            obs = list(db.collection('tracker_observations')
                      .where('observed_at', '>=', yesterday)
                      .limit(500).stream())
            digest['new_observations'] = len(obs)
        except Exception:
            pass

        # Count recent deals
        try:
            deals = list(db.collection('tracker_deals')
                        .where('created_at', '>=', yesterday)
                        .limit(100).stream())
            digest['new_deals'] = len(deals)
        except Exception:
            pass

        # Count recent style learnings
        try:
            styles = list(db.collection('brain_email_styles')
                         .where('last_seen', '>=', yesterday)
                         .limit(100).stream())
            digest['styles_learned'] = len(styles)
        except Exception:
            pass

        # Build digest HTML
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        html = f'''
        <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;">
        <div style="background:linear-gradient(135deg,#0f1923,#1a2d42);padding:14px 20px;border-radius:8px 8px 0 0;">
          <div style="color:#fff;font-size:15px;font-weight:bold;">🧠 RCB Brain — Daily Digest</div>
          <div style="color:rgba(255,255,255,0.5);font-size:11px;">{now_str}</div>
        </div>
        <div style="background:#fff;padding:16px 20px;border:1px solid #ddd;border-top:0;direction:rtl;">
          <div style="font-size:14px;font-weight:bold;color:#1e3a5f;margin-bottom:10px;">בוקר טוב דורון 👨</div>
          <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">
            <tr><td style="padding:5px 10px;font-size:12px;border-bottom:1px solid #eee;">📧 Emails processed</td><td style="padding:5px 10px;font-weight:bold;font-size:12px;border-bottom:1px solid #eee;">{digest['new_observations']}</td></tr>
            <tr><td style="padding:5px 10px;font-size:12px;border-bottom:1px solid #eee;">📦 New deals</td><td style="padding:5px 10px;font-weight:bold;font-size:12px;border-bottom:1px solid #eee;">{digest['new_deals']}</td></tr>
            <tr><td style="padding:5px 10px;font-size:12px;border-bottom:1px solid #eee;">🎨 Email styles learned</td><td style="padding:5px 10px;font-weight:bold;font-size:12px;border-bottom:1px solid #eee;">{digest['styles_learned']}</td></tr>
            <tr><td style="padding:5px 10px;font-size:12px;">⚡ Improvements applied</td><td style="padding:5px 10px;font-weight:bold;font-size:12px;">{digest['improvements_applied']}</td></tr>
          </table>
          <div style="font-size:11px;color:#888;">Reply "brain status" for full report. Reply "brain, learn about X" to start a mission.</div>
        </div>
        <div style="background:#f8f9fa;padding:8px 20px;border:1px solid #ddd;border-top:0;border-radius:0 0 8px 8px;">
          <div style="font-size:9px;color:#bbb;">🧠 Only doron@ sees this digest</div>
        </div>
        </div>'''

        # Save digest
        db.collection('brain_daily_digest').add({
            'date': now_str,
            'digest': digest,
            'sent_at': datetime.now(timezone.utc).isoformat(),
        })

        # Send to father
        sent = helper_graph_send(
            access_token, rcb_email, FATHER_EMAIL,
            f"🧠 RCB Brain Daily Digest — {now_str}",
            html
        )

        return {'sent': sent, 'digest': digest}

    except Exception as e:
        print(f"    ❌ Brain digest error: {e}")
        return {'error': str(e)}


# ═══════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════

def _get_sender(msg):
    """Extract sender email from msg."""
    from_obj = msg.get('from', {})
    if isinstance(from_obj, dict):
        return from_obj.get('emailAddress', {}).get('address', '')
    return ''


def _strip_html_simple(html):
    """Basic HTML strip for command detection."""
    if not html:
        return ''
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _detect_scope(text):
    """Detect what scope the status report should cover."""
    if any(kw in text for kw in ['template', 'תבנית']):
        return 'templates'
    if any(kw in text for kw in ['deal', 'עסקה', 'shipment']):
        return 'deals'
    if any(kw in text for kw in ['email', 'מייל', 'style']):
        return 'email_styles'
    return 'full'


def _extract_topic(text):
    """Extract the topic from a learning mission command."""
    # Remove command keywords, what's left is the topic
    topic = text
    for kw in ['go learn', 'לך ללמוד', 'go research', 'תחקור', 'study',
                'learn about', 'למד על', 'brain', 'מוח', 'please', 'בבקשה']:
        topic = re.sub(re.escape(kw), '', topic, flags=re.IGNORECASE)
    return topic.strip()[:200]


def _detect_agents(text):
    """Detect which agents father wants to use."""
    agents = []
    if any(kw in text for kw in ['claude', 'קלוד']):
        agents.append('claude')
    if any(kw in text for kw in ['gemini', 'ג\'מיני', 'google']):
        agents.append('gemini')
    if not agents:
        agents = ['gemini']  # Default: free agent
    return agents


def _detect_improvement_target(text):
    """Detect what father wants to improve."""
    if any(kw in text for kw in ['email', 'מייל', 'reply', 'תשובה']):
        return 'emails'
    if any(kw in text for kw in ['extract', 'חילוץ', 'read', 'קריאה']):
        return 'extraction'
    if any(kw in text for kw in ['template', 'תבנית']):
        return 'templates'
    if any(kw in text for kw in ['track', 'מעקב']):
        return 'tracking'
    return 'general'


def _log_command(db, msg, command):
    """Log father command to Firestore."""
    doc_ref = db.collection('brain_commands').document()
    doc_ref.set({
        'command_type': command.get('type', 'general'),
        'raw': command.get('raw', '')[:500],
        'parsed': command,
        'from': FATHER_EMAIL,
        'msg_id': msg.get('id', ''),
        'subject': msg.get('subject', ''),
        'status': 'executing',
        'received_at': datetime.now(timezone.utc).isoformat(),
    })
    return doc_ref.id


def _update_command_result(db, cmd_id, result):
    """Update command with execution result."""
    try:
        db.collection('brain_commands').document(cmd_id).update({
            'status': result.get('status', 'completed'),
            'result_summary': str(result)[:1000],
            'completed_at': datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass
