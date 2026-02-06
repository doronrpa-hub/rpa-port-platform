"""
Knowledge Query Handler for RCB v4.1.0
=======================================
Handles knowledge queries from team members (@rpa-port.co.il).
When team emails arrive without commercial documents, RCB consults the
Librarian + Researcher, gathers knowledge, and replies with a concise
AI-generated explanation in Hebrew.

INTEGRATION:
    Called from the Cloud Function email check flow (main.py).
    Uses the SAME helper functions as the classification pipeline:
      - lib.librarian: find_by_tags, smart_search, full_knowledge_search
      - lib.librarian_researcher: find_similar_classifications, get_web_search_queries
      - lib.librarian_tags: auto_tag_document, CUSTOMS_HANDBOOK_CHAPTERS
      - lib.classification_agents: call_claude
      - lib.rcb_helpers: helper_graph_send, extract_text_from_pdf_bytes, to_hebrew_name

Author: RCB System
Session: 13
"""

import re
import time
import base64
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Imports from existing lib modules — same functions used by classification
# ---------------------------------------------------------------------------

try:
    from .librarian import (
        find_by_tags,
        smart_search,
        full_knowledge_search,
        get_all_locations_for,
        find_by_hs_code,
    )
    from .librarian_researcher import (
        find_similar_classifications,
        get_web_search_queries,
    )
    from .librarian_tags import (
        auto_tag_document,
        suggest_related_tags,
        CUSTOMS_HANDBOOK_CHAPTERS,
    )
    from .classification_agents import call_claude
    from .rcb_helpers import (
        helper_graph_send,
        extract_text_from_pdf_bytes,
        extract_text_from_attachments,
        to_hebrew_name,
    )
except ImportError:
    # For standalone testing
    from librarian import (
        find_by_tags, smart_search, full_knowledge_search,
        get_all_locations_for, find_by_hs_code,
    )
    from librarian_researcher import (
        find_similar_classifications, get_web_search_queries,
    )
    from librarian_tags import (
        auto_tag_document, suggest_related_tags, CUSTOMS_HANDBOOK_CHAPTERS,
    )
    from classification_agents import call_claude
    from rcb_helpers import (
        helper_graph_send, extract_text_from_pdf_bytes,
        extract_text_from_attachments, to_hebrew_name,
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEAM_DOMAIN = "rpa-port.co.il"
MAX_ATTACHMENTS = 5
KNOWLEDGE_COLLECTION = "knowledge_queries"
RCB_SIGNATURE = "RCB - מערכת מידע מכס"

# Hebrew question signals
HEBREW_QUESTION_PATTERNS = [
    r"\?",
    r"תוכל[י]?\s",
    r"מה\s",
    r"איך\s",
    r"האם\s",
    r"אני\sצריך[ה]?\sמידע",
    r"תגיד[י]?\sלי",
    r"מה\sאת[ה]?\sיודע[ת]?\sעל",
    r"יש\sמידע\sעל",
    r"מה\sהנוהל",
    r"מה\sהדין",
    r"תסביר[י]?\s",
    r"עדכונים?\s",
    r"שינויים?\s",
]

# English question signals
ENGLISH_QUESTION_PATTERNS = [
    r"what do you know about",
    r"can you find",
    r"i need info",
    r"what is the procedure",
    r"do you have information",
    r"tell me about",
    r"any updates on",
]

# HS code pattern in subject → shipment, not knowledge query
HS_CODE_PATTERN = re.compile(r"\b\d{4}\.\d{2}", re.ASCII)

# Commercial document indicators in attachment filenames
COMMERCIAL_DOC_KEYWORDS = [
    "invoice", "packing", "bill of lading", "certificate",
    "חשבונית", "רשימת אריזה", "שטר מטען", "תעודת",
    "proforma", "commercial invoice", "ci_", "pl_", "bol_",
]

# Scope detection
IMPORT_KEYWORDS = [
    "יבוא", "ייבוא", "import", "מכס", "customs", "שחרור",
    "יבוא אישי", "personal import", "מס קניה", "purchase tax",
]
EXPORT_KEYWORDS = [
    "יצוא", "ייצוא", "export", "קרנה אטא", "ata carnet",
    "תעודת תנועה", "eur.1", "movement certificate",
]

# Topic → tags mapping (uses the SAME tag names as librarian_tags.py DOCUMENT_TAGS)
TOPIC_TAG_MAP = {
    "רכב": ["vehicle", "personal_import"],
    "מכונית": ["vehicle", "personal_import"],
    "אספנות": ["vehicle", "collectors", "personal_import"],
    "קוסמטיקה": ["cosmetics", "ministry_health"],
    "תמרוקים": ["cosmetics", "ministry_health"],
    "מזון": ["food", "ministry_health"],
    "אוכל": ["food", "ministry_health"],
    "טקסטיל": ["textiles"],
    "בגדים": ["textiles", "garments"],
    "אלקטרוניקה": ["electronics"],
    "מחשב": ["electronics", "computers"],
    "קרנה": ["ata_carnet", "temporary_import"],
    "carnet": ["ata_carnet", "temporary_import"],
    "תערוכה": ["ata_exhibition", "ata_carnet"],
    "יבוא אישי": ["personal_import"],
    "עולה חדש": ["personal_import", "olim_import"],
    "ערך": ["customs_valuation"],
    "שווי": ["customs_valuation"],
    "הערכה": ["customs_valuation"],
    "מקור": ["rules_of_origin", "certificates"],
    "eur": ["rules_of_origin", "fta_eu"],
    "סיווג": ["customs_classification", "tariff"],
    "פרט מכס": ["customs_classification", "tariff"],
    "נוהל": ["customs_procedure"],
    "מצהר": ["manifest"],
    "רשימון": ["customs_declaration"],
    "שחרור": ["customs_release"],
    "פטור": ["conditional_exemption"],
    "הישבון": ["drawback"],
    "מחסן": ["bonded_warehouse"],
    "פיקוח": ["export_control"],
}

# Hebrew stop words to filter from keywords
STOP_WORDS_HE = {
    "של", "את", "על", "עם", "אני", "הוא", "היא", "אתה",
    "שלום", "תודה", "בבקשה", "לגבי", "לנו", "שלנו", "שלך",
    "אפשר", "צריך", "יודע", "יודעת", "תוכל", "תוכלי",
    "מידע", "בנושא", "בקשר", "עדכון", "בוקר", "ערב",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase + strip excess whitespace."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _extract_sender_name_graph(msg: dict) -> str:
    """Extract display name from Graph API message format."""
    try:
        sender = msg.get("from", {})
        name = sender.get("emailAddress", {}).get("name", "")
        if name:
            first = name.split()[0]
            return to_hebrew_name(first)
        addr = sender.get("emailAddress", {}).get("address", "")
        return to_hebrew_name(addr.split("@")[0]) if addr else "שלום"
    except Exception:
        return "שלום"


def _get_sender_address(msg: dict) -> str:
    """Get sender email address from Graph API message."""
    try:
        return msg.get("from", {}).get("emailAddress", {}).get("address", "")
    except Exception:
        return ""


def _generate_query_id(email_id: str) -> str:
    """Deterministic query ID from email ID."""
    h = hashlib.sha256(email_id.encode()).hexdigest()[:12]
    return f"kq_{h}"


def _strip_html(text: str) -> str:
    """Remove HTML tags and entities."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _get_body_text(msg: dict) -> str:
    """Extract plain text body from Graph API message."""
    body = msg.get("body", {})
    if isinstance(body, dict):
        content = body.get("content", "")
    else:
        content = str(body)
    return _strip_html(content)


def _find_handbook_chapters_by_tags(tags: list) -> list:
    """
    Match detected tags against CUSTOMS_HANDBOOK_CHAPTERS.
    Returns list of matching chapters with their metadata.
    """
    matched = []
    for ch_num, ch_data in CUSTOMS_HANDBOOK_CHAPTERS.items():
        ch_tag = ch_data.get("tag", "")
        if ch_tag in tags:
            matched.append({
                "chapter": ch_num,
                "tag": ch_tag,
                "name_he": ch_data.get("name_he", ""),
                "name_en": ch_data.get("name_en", ""),
                "scope": ch_data.get("scope", "both"),
                "pdf_url": ch_data.get("pdf_url", ""),
            })
        # Check sub-chapters
        for sub_num, sub_data in ch_data.get("sub_chapters", {}).items():
            sub_tag = sub_data.get("tag", "")
            if sub_tag in tags:
                matched.append({
                    "chapter": sub_num,
                    "tag": sub_tag,
                    "name_he": sub_data.get("name_he", ""),
                    "name_en": sub_data.get("name_en", ""),
                    "scope": ch_data.get("scope", "both"),
                    "pdf_url": ch_data.get("pdf_url", ""),
                })
    return matched


# ---------------------------------------------------------------------------
# Detection functions (stateless — match Graph API email format)
# ---------------------------------------------------------------------------

def is_team_sender(msg: dict) -> bool:
    """Check sender domain is @rpa-port.co.il (Graph API format)."""
    addr = _get_sender_address(msg)
    return addr.lower().endswith(f"@{TEAM_DOMAIN}")


def is_addressed_to_rcb(msg: dict) -> bool:
    """RCB must be in the TO field, not just CC/BCC (Graph API format)."""
    to_recipients = msg.get("toRecipients", [])
    for r in to_recipients:
        addr = r.get("emailAddress", {}).get("address", "")
        if "rcb" in addr.lower():
            return True
    return False


def has_commercial_documents(msg: dict) -> bool:
    """Check if email has commercial document attachments."""
    attachments = msg.get("attachments", [])
    for att in attachments:
        name = (att.get("name", "") or "").lower()
        for kw in COMMERCIAL_DOC_KEYWORDS:
            if kw in name:
                return True
    return False


def _is_question_like(text: str) -> bool:
    """Detect if text contains question/knowledge-request patterns."""
    normalized = _normalize(text)
    for pat in HEBREW_QUESTION_PATTERNS:
        if re.search(pat, text):
            return True
    for pat in ENGLISH_QUESTION_PATTERNS:
        if re.search(pat, normalized):
            return True
    return False


def detect_knowledge_query(msg: dict) -> bool:
    """
    Master detection: returns True if this email is a knowledge query.
    All conditions must be true:
      - Sender is @rpa-port.co.il
      - RCB is in TO (not just CC)
      - No commercial documents attached
      - Body/subject looks like a question
      - Subject doesn't contain HS code patterns (shipment indicator)
    """
    if not is_team_sender(msg):
        return False
    if not is_addressed_to_rcb(msg):
        return False
    if has_commercial_documents(msg):
        return False

    subject = msg.get("subject", "")
    if HS_CODE_PATTERN.search(subject):
        return False

    # Safety net: if NO attachments at all, always treat as KQ
    # (nothing to classify without documents)
    attachments = msg.get("attachments", [])
    if not attachments or len(attachments) == 0:
        return True

    body_text = _get_body_text(msg)
    combined = f"{subject} {body_text}"
    return _is_question_like(combined)


# ---------------------------------------------------------------------------
# Question parsing
# ---------------------------------------------------------------------------

def parse_question(msg: dict) -> dict:
    """
    Extract topic, scope, keywords, and tags from the question.
    """
    subject = msg.get("subject", "")
    body_text = _get_body_text(msg)
    question_text = f"{subject}\n{body_text}".strip()
    combined_lower = _normalize(question_text)

    # --- Scope ---
    has_import = any(kw in question_text or kw in combined_lower for kw in IMPORT_KEYWORDS)
    has_export = any(kw in question_text or kw in combined_lower for kw in EXPORT_KEYWORDS)
    if has_import and has_export:
        scope = "both"
    elif has_export:
        scope = "export"
    elif has_import:
        scope = "import"
    else:
        scope = "both"

    # --- Tags ---
    tags = set()
    for keyword, tag_list in TOPIC_TAG_MAP.items():
        if keyword in question_text:
            tags.update(tag_list)

    # Expand tags with related tags from librarian_tags
    if tags:
        try:
            related = suggest_related_tags(list(tags))
            if related:
                tags.update(related[:5])
        except Exception:
            pass

    # --- HS chapter references ---
    chapter_refs = re.findall(r"(?:פרק|chapter|ch\.?)\s*(\d{1,2})", combined_lower)
    for ch in chapter_refs:
        ch_int = int(ch)
        if ch_int in CUSTOMS_HANDBOOK_CHAPTERS:
            ch_tag = CUSTOMS_HANDBOOK_CHAPTERS[ch_int].get("tag", "")
            if ch_tag:
                tags.add(ch_tag)

    # --- Keywords ---
    hebrew_words = re.findall(r"[\u0590-\u05FF]{3,}", question_text)
    english_words = re.findall(r"[a-zA-Z]{4,}", question_text)
    keywords = [w for w in hebrew_words if w not in STOP_WORDS_HE]
    keywords += english_words

    # --- Reference attachments (PDFs attached for context, not commercial) ---
    attachments = msg.get("attachments", [])
    reference_attachments = [
        att for att in attachments
        if (att.get("name", "") or "").lower().endswith(".pdf")
        and att.get("contentBytes")
    ]

    return {
        "question_text": question_text,
        "scope": scope,
        "tags": list(tags),
        "keywords": keywords[:20],
        "reference_attachments": reference_attachments,
    }


# ---------------------------------------------------------------------------
# Knowledge gathering
# ---------------------------------------------------------------------------

def gather_knowledge(db, parsed: dict) -> dict:
    """
    Consult Librarian + Researcher. Uses the SAME functions
    that classification_agents uses — find_by_tags, smart_search, etc.
    """
    t0 = time.time()
    knowledge = {
        "librarian_results": [],
        "handbook_chapters": [],
        "past_classifications": [],
        "research_queries": [],
        "source_locations": [],
        "reference_doc_text": [],
    }

    tags = parsed.get("tags", [])
    keywords = parsed.get("keywords", [])
    question = parsed.get("question_text", "")

    # ── Step A: Librarian — find_by_tags (same as classification pipeline) ──
    if tags:
        try:
            tag_results = find_by_tags(db, tags)
            if tag_results:
                knowledge["librarian_results"].extend(tag_results)
                print(f"    📚 find_by_tags({tags[:3]}...): {len(tag_results)} results")
        except Exception as e:
            print(f"    ⚠️ find_by_tags error: {e}")

    # ── Step B: Librarian — smart_search (same as classification pipeline) ──
    try:
        search_results = smart_search(db, question, limit=15)
        if search_results:
            seen_ids = {r.get("id") for r in knowledge["librarian_results"]}
            for r in search_results:
                if r.get("id") not in seen_ids:
                    knowledge["librarian_results"].append(r)
                    seen_ids.add(r.get("id"))
            print(f"    📚 smart_search: {len(search_results)} results")
    except Exception as e:
        print(f"    ⚠️ smart_search error: {e}")

    # ── Step C: Handbook chapters (from CUSTOMS_HANDBOOK_CHAPTERS dict) ──
    if tags:
        knowledge["handbook_chapters"] = _find_handbook_chapters_by_tags(tags)
        print(f"    📖 Handbook chapters matched: {len(knowledge['handbook_chapters'])}")

    # ── Step D: Past classifications (Researcher — same function) ──
    if question:
        try:
            similar = find_similar_classifications(db, question, limit=5)
            if similar:
                knowledge["past_classifications"] = similar
                print(f"    🔍 Similar classifications: {len(similar)}")
        except Exception as e:
            print(f"    ⚠️ find_similar_classifications error: {e}")

    # ── Step E: Research query suggestions ──
    tag_to_topic = {
        "customs_classification": "classification_decisions",
        "customs_valuation": "customs_procedures",
        "rules_of_origin": "fta_updates",
        "ministry_health": "ministry_health_procedures",
        "cosmetics": "ministry_health_procedures",
        "food": "ministry_health_procedures",
    }
    for tag in tags:
        topic = tag_to_topic.get(tag)
        if topic:
            try:
                queries = get_web_search_queries(topic)
                if queries and queries.get("keywords_he"):
                    knowledge["research_queries"].append({
                        "topic": topic,
                        "queries": queries,
                    })
            except Exception:
                pass

    # ── Step F: Document locations ──
    if question:
        try:
            locations = get_all_locations_for(db, question)
            if locations:
                knowledge["source_locations"] = locations[:10]
        except Exception as e:
            print(f"    ⚠️ get_all_locations error: {e}")

    # ── Step G: Process reference attachments (using rcb_helpers) ──
    ref_attachments = parsed.get("reference_attachments", [])
    for att in ref_attachments:
        name = att.get("name", "unknown.pdf")
        content_b64 = att.get("contentBytes", "")
        if content_b64:
            try:
                file_bytes = base64.b64decode(content_b64)
                text = extract_text_from_pdf_bytes(file_bytes)
                doc_tags = []
                try:
                    doc_tags = auto_tag_document({"text": text, "name": name})
                except Exception:
                    pass
                knowledge["reference_doc_text"].append({
                    "name": name,
                    "text_preview": text[:2000] if text else "(לא ניתן לקרוא)",
                    "tags": doc_tags,
                })
            except Exception as e:
                print(f"    ⚠️ Error parsing reference PDF {name}: {e}")
                knowledge["reference_doc_text"].append({
                    "name": name,
                    "text_preview": "(שגיאה בקריאת המסמך)",
                    "tags": [],
                })

    knowledge["gathering_time_ms"] = int((time.time() - t0) * 1000)
    return knowledge


# ---------------------------------------------------------------------------
# Attachment selection
# ---------------------------------------------------------------------------

def select_attachments(knowledge: dict) -> Tuple[list, int]:
    """
    Pick relevant handbook chapter PDFs to mention in reply.
    Returns (selected, overflow_count).
    """
    candidates = []

    seen_urls = set()
    for ch in knowledge.get("handbook_chapters", []):
        url = ch.get("pdf_url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            candidates.append({
                "url": url,
                "name_he": ch.get("name_he", ""),
                "chapter": ch.get("chapter", ""),
                "priority": 1,
            })

    candidates.sort(key=lambda x: x.get("priority", 99))
    selected = candidates[:MAX_ATTACHMENTS]
    overflow = max(len(candidates) - MAX_ATTACHMENTS, 0)
    return selected, overflow


# ---------------------------------------------------------------------------
# Reply generation
# ---------------------------------------------------------------------------

def generate_reply(msg: dict, parsed: dict, knowledge: dict,
                   attachments: list, overflow_count: int,
                   api_key: str) -> dict:
    """
    Use call_claude (same function as classification_agents.py) to
    write a concise Hebrew reply.
    Returns: {subject, body_html, body_text}
    """
    sender_name = _extract_sender_name_graph(msg)
    original_subject = msg.get("subject", "")

    # ── Build knowledge context for the LLM ──
    ctx = []

    if knowledge.get("librarian_results"):
        ctx.append("=== מידע מהספרייה ===")
        for i, r in enumerate(knowledge["librarian_results"][:15], 1):
            title = r.get("title", r.get("id", f"מסמך {i}"))
            desc = r.get("description", "")[:300]
            tags_str = ", ".join(r.get("tags", [])[:5])
            ctx.append(f"{i}. {title} [{tags_str}]\n   {desc}")

    if knowledge.get("handbook_chapters"):
        ctx.append("\n=== פרקים רלוונטיים מספר היד למכס ===")
        for ch in knowledge["handbook_chapters"]:
            ctx.append(f"• פרק {ch['chapter']}: {ch['name_he']} ({ch['name_en']})")

    if knowledge.get("past_classifications"):
        ctx.append("\n=== סיווגים קודמים רלוונטיים ===")
        for cl in knowledge["past_classifications"][:5]:
            desc = cl.get("description", "")[:100]
            hs = cl.get("hs_code", "")
            conf = cl.get("confidence", "")
            corr = " [תיקון]" if cl.get("is_correction") else ""
            ctx.append(f"• {desc} → {hs} ({conf}){corr}")

    if knowledge.get("source_locations"):
        ctx.append("\n=== מיקום מסמכים במערכת ===")
        for loc in knowledge["source_locations"][:5]:
            ctx.append(f"• {loc}")

    if knowledge.get("reference_doc_text"):
        ctx.append("\n=== מסמכי ייחוס שצורפו למייל ===")
        for ds in knowledge["reference_doc_text"]:
            ctx.append(f"• {ds['name']}: {ds['text_preview'][:500]}")

    knowledge_context = "\n".join(ctx) if ctx else "(לא נמצא מידע רלוונטי במערכת)"

    # ── LLM prompt ──
    system_prompt = """אתה RCB - מערכת מידע מכס של ר.פ.א פורט בע"מ. אתה עונה לשאלות של צוות עמילות מכס בעברית.
כללים:
- כתוב בעברית מקצועית ותמציתית
- 2-4 פסקאות מקסימום
- ציין בסיס חוקי כשרלוונטי (פקודת המכס, צו יבוא חופשי, וכד')
- אם יש ניסיון קודם מהמערכת (סיווגים דומים), ציין אותו
- ציין דגשים חשובים ונקודות לתשומת לב
- אל תמציא מידע - אם אין לך מספיק מידע, ציין זאת
- טון מקצועי, ברור, פרקטי
- אל תכלול את רשימת המצורפים — זה יתווסף אוטומטית
- התחל ישר עם התשובה (בלי "שלום" - זה יתווסף אוטומטית)"""

    user_prompt = f"""השאלה מאת {sender_name}:
{parsed['question_text']}

תחום: {parsed['scope']}
תגיות שזוהו: {', '.join(parsed.get('tags', []))}

מידע שנאסף מהמערכת:
{knowledge_context}"""

    # call_claude: same function used by classification_agents.py
    reply_body = call_claude(api_key, system_prompt, user_prompt, max_tokens=2000)
    if not reply_body:
        reply_body = (
            "לצערי לא הצלחתי לייצר תשובה אוטומטית. "
            "מצורפים מסמכים רלוונטיים שמצאתי במערכת."
        )

    # ── Assemble full reply ──
    parts = [f"שלום {sender_name},", "", reply_body]

    if attachments:
        parts += ["", "📎 מסמכים רלוונטיים:"]
        for i, att in enumerate(attachments, 1):
            parts.append(f"  {i}. פרק {att.get('chapter', '?')}: {att.get('name_he', '')}")
            if att.get("url"):
                parts.append(f"     🔗 {att['url']}")

    if overflow_count > 0:
        parts.append(f"\n(יש עוד {overflow_count} מסמכים רלוונטיים — אשמח לשלוח בהמשך לפי בקשה)")

    if knowledge.get("research_queries"):
        parts += ["", "🔍 נושאים לבדיקה נוספת:"]
        for rq in knowledge["research_queries"][:3]:
            kw = rq.get("queries", {}).get("keywords_he", [])[:2]
            if kw:
                parts.append(f"  • {', '.join(kw)}")

    parts += ["", "בברכה,", RCB_SIGNATURE]

    body_text = "\n".join(parts)

    # HTML version (RTL, same signature style as rcb_helpers.build_rcb_reply)
    body_inner = body_text.replace("\n", "<br>")
    body_html = f'''<div dir="rtl" style="font-family:Arial,sans-serif;font-size:12pt;line-height:1.6">
{body_inner}
<hr style="margin:25px 0">
<table dir="rtl"><tr>
    <td style="padding-left:15px"><img src="https://rpa-port.com/wp-content/uploads/2020/01/logo.png" style="width:80px"></td>
    <td style="border-right:3px solid #1e3a5f;padding-right:15px">
        <strong style="color:#1e3a5f">🤖 RCB - AI Customs Broker</strong><br>
        <strong>R.P.A. PORT LTD</strong><br>
        <span style="font-size:10pt">📧 rcb@rpa-port.co.il</span>
    </td>
</tr></table>
</div>'''

    return {
        "subject": f"Re: {original_subject}",
        "body_html": body_html,
        "body_text": body_text,
    }


# ---------------------------------------------------------------------------
# Send reply — uses helper_graph_send (same as classification pipeline)
# ---------------------------------------------------------------------------

def send_reply(access_token: str, rcb_email: str, msg: dict,
               reply_content: dict, pdf_attachments: list = None) -> bool:
    """
    Send reply via helper_graph_send — the SAME function used by
    process_and_send_report() in classification_agents.py.
    Signature: helper_graph_send(access_token, user_email, to_email,
                                  subject, body_html, reply_to_id, attachments_data)
    """
    to_email = _get_sender_address(msg)
    if not to_email:
        print("    ❌ Cannot determine reply-to address")
        return False

    msg_id = msg.get("id")

    # Build attachment data in same format helper_graph_send expects:
    # list of dicts with 'name', 'contentType', 'contentBytes' (base64 str)
    attachments_data = None
    if pdf_attachments:
        attachments_data = []
        for att in pdf_attachments:
            if att.get("contentBytes"):
                attachments_data.append({
                    "name": att.get("name", "document.pdf"),
                    "contentType": "application/pdf",
                    "contentBytes": att["contentBytes"],
                })

    success = helper_graph_send(
        access_token,
        rcb_email,
        to_email,
        reply_content["subject"],
        reply_content["body_html"],
        msg_id,
        attachments_data,
    )

    if success:
        print(f"    ✅ Knowledge reply sent to {to_email}")
    else:
        print(f"    ❌ Failed to send knowledge reply to {to_email}")

    return success


# ---------------------------------------------------------------------------
# Firestore logging
# ---------------------------------------------------------------------------

def log_knowledge_query(db, firestore_module, msg: dict, parsed: dict,
                        knowledge: dict, attachments_sent: list,
                        reply_sent: bool, processing_time_ms: int):
    """Log knowledge query to Firestore for tracking."""
    try:
        email_id = msg.get("id", "unknown")
        query_id = _generate_query_id(email_id)

        doc_ref = db.collection(KNOWLEDGE_COLLECTION).document(query_id)
        doc_ref.set({
            "email_id": email_id,
            "sender": _get_sender_address(msg),
            "question_text": parsed.get("question_text", "")[:5000],
            "scope": parsed.get("scope", "both"),
            "tags_detected": parsed.get("tags", []),
            "keywords": parsed.get("keywords", [])[:20],
            "librarian_result_count": len(knowledge.get("librarian_results", [])),
            "handbook_chapters": [
                ch.get("name_he", "") for ch in knowledge.get("handbook_chapters", [])
            ],
            "past_classification_count": len(knowledge.get("past_classifications", [])),
            "attachments_sent": [a.get("name_he", "") for a in attachments_sent],
            "reply_sent": reply_sent,
            "created_at": firestore_module.SERVER_TIMESTAMP,
            "processing_time_ms": processing_time_ms,
        })
        print(f"    📝 Logged knowledge query: {query_id}")

    except Exception as e:
        print(f"    ⚠️ Failed to log knowledge query: {e}")


# ---------------------------------------------------------------------------
# Main handler — entry point called from Cloud Function
# ---------------------------------------------------------------------------

def handle_knowledge_query(
    msg: dict,
    db,
    firestore_module,
    access_token: str,
    rcb_email: str,
    get_secret_func,
) -> dict:
    """
    Main entry point — process a knowledge query end-to-end.

    Uses EXACTLY the same parameter style as the classification flow in main.py:
      msg            = Graph API message dict
      db             = Firestore client
      firestore_module = google.cloud.firestore (for SERVER_TIMESTAMP)
      access_token   = Graph API access token
      rcb_email      = RCB mailbox address
      get_secret_func = Secret Manager accessor
    """
    t0 = time.time()
    email_id = msg.get("id", "unknown")
    query_id = _generate_query_id(email_id)
    sender = _get_sender_address(msg)

    print(f"\n{'='*60}")
    print(f"📚 KNOWLEDGE QUERY {query_id}")
    print(f"   From: {sender}")
    print(f"   Subject: {msg.get('subject', '')[:60]}")
    print(f"{'='*60}")

    try:
        # Get API key — same way classification_agents does it
        api_key = get_secret_func('ANTHROPIC_API_KEY')
        if not api_key:
            print("    ❌ No ANTHROPIC_API_KEY")
            return {"status": "error", "query_id": query_id, "error": "no_api_key"}

        # Step 1: Parse question
        parsed = parse_question(msg)
        print(f"    📋 Parsed: scope={parsed['scope']}, tags={parsed['tags'][:5]}, "
              f"keywords={parsed['keywords'][:5]}")

        # Step 2+3: Gather knowledge (librarian + researcher)
        knowledge = gather_knowledge(db, parsed)
        print(f"    📚 Gathered: {len(knowledge.get('librarian_results', []))} lib results, "
              f"{len(knowledge.get('handbook_chapters', []))} chapters, "
              f"{len(knowledge.get('past_classifications', []))} past classifications "
              f"({knowledge.get('gathering_time_ms', 0)}ms)")

        # Step 4: Select attachments
        selected_attachments, overflow = select_attachments(knowledge)
        print(f"    📎 Attachments: {len(selected_attachments)} selected, {overflow} overflow")

        # Step 5: Generate reply
        reply_content = generate_reply(
            msg, parsed, knowledge,
            selected_attachments, overflow, api_key,
        )

        # Step 6: Send reply via helper_graph_send
        reply_sent = send_reply(
            access_token, rcb_email, msg,
            reply_content,
            pdf_attachments=None,  # PDF links in body; attach when cached via PC Agent
        )

        processing_time_ms = int((time.time() - t0) * 1000)

        # Step 7: Log to Firestore
        log_knowledge_query(
            db, firestore_module, msg, parsed, knowledge,
            selected_attachments, reply_sent, processing_time_ms,
        )

        # Step 8: Let researcher learn from this email
        try:
            from .librarian_researcher import learn_from_email
            learn_from_email(db, {
                "subject": msg.get("subject", ""),
                "body": _get_body_text(msg),
                "sender": sender,
                "type": "knowledge_query",
            })
        except Exception:
            pass

        status = "sent" if reply_sent else "generated_not_sent"
        print(f"\n    ✅ Knowledge query {query_id}: {status} ({processing_time_ms}ms)")

        return {
            "status": status,
            "query_id": query_id,
            "reply_sent": reply_sent,
            "processing_time_ms": processing_time_ms,
            "attachments_count": len(selected_attachments),
        }

    except Exception as e:
        processing_time_ms = int((time.time() - t0) * 1000)
        print(f"    ❌ Knowledge query {query_id} FAILED: {e}")

        try:
            log_knowledge_query(
                db, firestore_module, msg,
                parsed if 'parsed' in locals() else {"question_text": "", "scope": "both", "tags": [], "keywords": []},
                knowledge if 'knowledge' in locals() else {},
                [], False, processing_time_ms,
            )
        except Exception:
            pass

        return {
            "status": "error",
            "query_id": query_id,
            "error": str(e),
            "processing_time_ms": processing_time_ms,
        }
