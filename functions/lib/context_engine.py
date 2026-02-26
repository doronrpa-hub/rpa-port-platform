"""
Context Engine — System Intelligence First (SIF)
=================================================
Searches tariff, ordinance, XML documents, regulatory info, framework order,
and cached answers BEFORE any AI model sees the question.

The AI models receive a pre-assembled context package and their ONLY job
is to synthesize a professional Hebrew answer from that context.

Usage:
    from lib.context_engine import prepare_context_package, ContextPackage
"""

import re
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════
#  CONTEXT PACKAGE
# ═══════════════════════════════════════════

@dataclass
class ContextPackage:
    original_subject: str
    original_body: str
    detected_language: str          # "he" / "en" / "mixed"
    entities: dict = field(default_factory=dict)
    domain: str = "general"         # tariff / ordinance / fta / regulatory / general
    tariff_results: list = field(default_factory=list)
    ordinance_articles: list = field(default_factory=list)
    xml_results: list = field(default_factory=list)
    regulatory_results: list = field(default_factory=list)
    framework_articles: list = field(default_factory=list)
    wikipedia_results: list = field(default_factory=list)
    cached_answer: Optional[dict] = None
    context_summary: str = ""
    confidence: float = 0.0
    search_log: list = field(default_factory=list)


# ═══════════════════════════════════════════
#  ENTITY EXTRACTION PATTERNS
# ═══════════════════════════════════════════

_HS_CODE_RE = re.compile(r'\b(\d{4}[.\s]?\d{2}[.\s]?\d{2,4})\b')
_CONTAINER_RE = re.compile(r'\b([A-Z]{3}U\d{7})\b')
_BL_RE = re.compile(r'(?:B/?L|BOL|שטר)[:\s#]*([A-Z0-9][\w\-]{6,25})', re.IGNORECASE)
_BL_MSC_RE = re.compile(r'\b(MEDURS\d{5,10})\b')
_ARTICLE_RE = re.compile(r'(?:סעיף|article|§)\s*(\d{1,3}[אבגדהוזחטייכלמנסעפצקרשת]*)', re.IGNORECASE)

_PRODUCT_NAME_PATTERNS = [
    re.compile(r'(?:פרט\s*(?:ה?מכס|מכסי)\s*(?:ל|של|על)\s*)(.{3,80}?)(?:\?|$|\.)', re.IGNORECASE),
    re.compile(r'(?:סיווג\s+(?:של|ל)?\s*)(.{3,80}?)(?:\?|$|\.)', re.IGNORECASE),
    re.compile(r'(?:classification\s+(?:of|for)\s+)(.{3,80}?)(?:\?|$|\.)', re.IGNORECASE),
    re.compile(r'(?:hs\s*code\s*(?:for|of)\s+)(.{3,80}?)(?:\?|$|\.)', re.IGNORECASE),
    re.compile(r'(?:מה\s*(?:ה?סיווג|ה?מכס|ה?תעריף)\s*(?:של|ל|על)\s*)(.{3,80}?)(?:\?|$|\.)', re.IGNORECASE),
]

# Customs-relevant keywords for extraction
_CUSTOMS_KEYWORDS_HE = {
    'מכס', 'תעריף', 'סיווג', 'יבוא', 'יצוא', 'פטור', 'הערכה', 'ערך',
    'שחרור', 'רשימון', 'מצהר', 'הסכם', 'מקור', 'קניין', 'עיכוב', 'חילוט',
    'קנס', 'הברחה', 'רישיון', 'תקן', 'נוהל', 'אישור', 'מכסה', 'החסנה',
    'פקודה', 'צו', 'תוספת', 'הנחה', 'מותנה', 'עמיל',
}

_CUSTOMS_KEYWORDS_EN = {
    'customs', 'tariff', 'classification', 'import', 'export', 'duty',
    'valuation', 'origin', 'fta', 'clearance', 'declaration', 'warehouse',
    'ordinance', 'penalty', 'forfeiture', 'license', 'permit',
}


# ═══════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════

def _detect_language(subject, body):
    """Detect language by Hebrew character ratio."""
    text = f"{subject} {body}"
    if not text.strip():
        return "he"
    hebrew_chars = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
    total_alpha = sum(1 for c in text if c.isalpha()) or 1
    ratio = hebrew_chars / total_alpha
    if ratio > 0.3:
        return "he"
    if ratio < 0.1:
        return "en"
    return "mixed"


def _extract_entities(subject, body):
    """Extract HS codes, product names, containers, BL numbers, articles, keywords."""
    combined = f"{subject} {body}"
    entities = {
        "hs_codes": [],
        "product_names": [],
        "container_numbers": [],
        "bl_numbers": [],
        "article_numbers": [],
        "keywords": [],
    }

    # HS codes
    for m in _HS_CODE_RE.finditer(combined):
        code = re.sub(r'[\s.]', '', m.group(1))
        if code not in entities["hs_codes"]:
            entities["hs_codes"].append(code)

    # Container numbers
    for m in _CONTAINER_RE.finditer(combined):
        entities["container_numbers"].append(m.group(1))

    # BL numbers
    for pat in [_BL_RE, _BL_MSC_RE]:
        for m in pat.finditer(combined):
            val = m.group(1) if pat.groups else m.group(0)
            if val not in entities["bl_numbers"]:
                entities["bl_numbers"].append(val)

    # Article numbers
    for m in _ARTICLE_RE.finditer(combined):
        art = m.group(1)
        if art not in entities["article_numbers"]:
            entities["article_numbers"].append(art)

    # Product names
    for pat in _PRODUCT_NAME_PATTERNS:
        m = pat.search(combined)
        if m:
            name = m.group(1).strip().rstrip('?.,! ')
            if name and len(name) > 2:
                entities["product_names"].append(name)
                break

    # Keywords
    for word in re.findall(r'[\u0590-\u05FF]{3,}', combined):
        if word in _CUSTOMS_KEYWORDS_HE and word not in entities["keywords"]:
            entities["keywords"].append(word)
    for word in re.findall(r'[a-zA-Z]{4,}', combined.lower()):
        if word in _CUSTOMS_KEYWORDS_EN and word not in entities["keywords"]:
            entities["keywords"].append(word)

    return entities


def _detect_domain(entities, subject, body):
    """Detect primary domain from entities and text."""
    combined = f"{subject} {body}".lower()

    if entities.get("hs_codes"):
        return "tariff"

    # Product classification question patterns
    if any(p in combined for p in ['פרט מכס', 'סיווג', 'hs code', 'classification', 'תעריף']):
        return "tariff"

    if entities.get("article_numbers"):
        return "ordinance"
    if any(p in combined for p in ['פקודת המכס', 'פקודה', 'ordinance', 'סעיף']):
        return "ordinance"

    if any(p in combined for p in ['הסכם סחר', 'fta', 'כללי מקור', 'תעודת מקור',
                                    'העדפה', 'צו מסגרת', 'framework']):
        return "fta"

    if any(p in combined for p in ['צו יבוא', 'רישיון', 'import order', 'restricted',
                                    'היתר', 'אישור ליבוא']):
        return "regulatory"

    # Import reform / economic policy patterns — these ARE customs-related
    if any(p in combined for p in [
        'רפורמ',              # רפורמה, רפורמת, רפורמות
        'מה שטוב לאירופה',
        'מה שטוב לארצות הברית',
        'ce marking', 'סימון ce',
        'קוד 65',             # customs code 65 — reform clearance route
        'מסמכי מוכר',         # seller documents
        'פטור isi', 'פטור מת"י', 'פטור מכון התקנים',
        'דירקטיבה אירופית', 'דירקטיבות',
        'עץ מוצר',            # product tree (tariff classification tool)
        'תקנים אירופיים',
        'import reform',
        'eu reform',
    ]):
        return "regulatory"

    return "general"


def _search_tariff_data(entities, db, search_log):
    """Search tariff DB for HS codes and product names."""
    results = []
    if not db:
        return results

    try:
        from lib.tool_executors import ToolExecutor
    except ImportError:
        try:
            from tool_executors import ToolExecutor
        except ImportError:
            search_log.append({"search": "tariff", "status": "import_error"})
            return results

    try:
        executor = ToolExecutor(db, api_key=None, gemini_key=None)

        # Search by HS codes
        for code in (entities.get("hs_codes") or [])[:3]:
            try:
                r = executor.execute("search_tariff", {"item_description": code})
                if r and r.get("candidates"):
                    results.extend(r["candidates"][:3])
                search_log.append({"search": f"tariff_hs:{code}", "status": "ok",
                                   "count": len(r.get("candidates", [])) if r else 0})
            except Exception as e:
                search_log.append({"search": f"tariff_hs:{code}", "status": f"error:{e}"})

        # Search by product names
        for name in (entities.get("product_names") or [])[:2]:
            try:
                r = executor.execute("search_tariff", {"item_description": name})
                if r and r.get("candidates"):
                    # Dedup by hs_code
                    existing = {c.get("hs_code") for c in results}
                    for c in r["candidates"][:3]:
                        if c.get("hs_code") not in existing:
                            results.append(c)
                            existing.add(c.get("hs_code"))
                search_log.append({"search": f"tariff_product:{name[:30]}", "status": "ok",
                                   "count": len(r.get("candidates", [])) if r else 0})
            except Exception as e:
                search_log.append({"search": f"tariff_product:{name[:30]}", "status": f"error:{e}"})

    except Exception as e:
        search_log.append({"search": "tariff_init", "status": f"error:{e}"})

    return results


def _search_ordinance(entities, subject, body, search_log):
    """Search ordinance articles by article number and keyword."""
    try:
        from lib._ordinance_data import ORDINANCE_ARTICLES
    except ImportError:
        try:
            from _ordinance_data import ORDINANCE_ARTICLES
        except ImportError:
            search_log.append({"search": "ordinance", "status": "import_error"})
            return []

    articles = []
    seen = set()

    # Direct article lookup
    for art_id in (entities.get("article_numbers") or []):
        art = ORDINANCE_ARTICLES.get(art_id)
        if art and art_id not in seen:
            articles.append({
                "article_id": art_id,
                "title_he": art.get("t", ""),
                "summary_en": art.get("s", ""),
                "full_text_he": (art.get("f") or "")[:3000],
                "chapter": art.get("ch", 0),
                "source": "ordinance",
            })
            seen.add(art_id)

    # Keyword search against titles and summaries
    if len(articles) < 5:
        combined = f"{subject} {body}".lower()
        # Strip Hebrew prefixes for matching
        words = set()
        for w in re.findall(r'[\u0590-\u05FF]{3,}', combined):
            words.add(w)
            # Strip common prefixes
            for prefix in ['ב', 'ל', 'ה', 'ו', 'מ', 'כ', 'ש']:
                if w.startswith(prefix) and len(w) > 3:
                    words.add(w[1:])
        for w in re.findall(r'[a-zA-Z]{4,}', combined):
            words.add(w)

        for art_id, art in ORDINANCE_ARTICLES.items():
            if art_id in seen:
                continue
            title = (art.get("t") or "").lower()
            summary = (art.get("s") or "").lower()
            full_text = (art.get("f") or "")[:500].lower()
            match_count = sum(1 for w in words if w in title or w in summary or w in full_text)
            if match_count >= 2:
                articles.append({
                    "article_id": art_id,
                    "title_he": art.get("t", ""),
                    "summary_en": art.get("s", ""),
                    "full_text_he": (art.get("f") or "")[:3000],
                    "chapter": art.get("ch", 0),
                    "source": "ordinance",
                    "_match_score": match_count,
                })
                seen.add(art_id)

        # Sort keyword matches by score, keep best
        scored = [a for a in articles if "_match_score" in a]
        scored.sort(key=lambda a: a["_match_score"], reverse=True)
        for a in scored:
            a.pop("_match_score", None)

    search_log.append({"search": "ordinance", "status": "ok", "count": len(articles)})
    return articles[:5]


def _search_xml_documents(entities, domain, db, search_log):
    """Search XML documents collection via ToolExecutor."""
    if not db:
        return []

    try:
        from lib.tool_executors import ToolExecutor
    except ImportError:
        try:
            from tool_executors import ToolExecutor
        except ImportError:
            search_log.append({"search": "xml", "status": "import_error"})
            return []

    results = []
    # Build search query from entities and domain
    terms = []
    for name in (entities.get("product_names") or [])[:1]:
        terms.append(name)
    for kw in (entities.get("keywords") or [])[:3]:
        terms.append(kw)
    if not terms:
        terms = [domain] if domain != "general" else []

    if not terms:
        return results

    query = " ".join(terms)[:200]
    try:
        executor = ToolExecutor(db, api_key=None, gemini_key=None)
        r = executor.execute("search_xml_documents", {"query": query})
        if r and isinstance(r, dict) and r.get("found"):
            results = r.get("documents", [])[:5]
        search_log.append({"search": f"xml:{query[:30]}", "status": "ok",
                           "count": len(results)})
    except Exception as e:
        search_log.append({"search": "xml", "status": f"error:{e}"})

    return results


def _check_regulatory_data(entities, domain, db, search_log):
    """Check regulatory requirements for products/HS codes."""
    if not db:
        return []
    if domain not in ("regulatory", "tariff") and not entities.get("product_names"):
        return []

    try:
        from lib.tool_executors import ToolExecutor
    except ImportError:
        try:
            from tool_executors import ToolExecutor
        except ImportError:
            search_log.append({"search": "regulatory", "status": "import_error"})
            return []

    results = []
    try:
        executor = ToolExecutor(db, api_key=None, gemini_key=None)
        # Check by HS codes
        for code in (entities.get("hs_codes") or [])[:2]:
            try:
                r = executor.execute("check_regulatory", {"hs_code": code})
                if r and (r.get("authorities") or r.get("free_import_order")):
                    results.append({"hs_code": code, "data": r})
            except Exception as e:
                search_log.append({"search": f"regulatory_hs:{code}", "status": f"error:{e}"})

        # Check by product name
        for name in (entities.get("product_names") or [])[:1]:
            try:
                r = executor.execute("check_regulatory", {"item_description": name})
                if r and (r.get("authorities") or r.get("free_import_order")):
                    results.append({"product": name, "data": r})
            except Exception as e:
                search_log.append({"search": f"regulatory_product:{name[:30]}", "status": f"error:{e}"})

        search_log.append({"search": "regulatory", "status": "ok", "count": len(results)})
    except Exception as e:
        search_log.append({"search": "regulatory_init", "status": f"error:{e}"})

    return results


def _search_framework_order(entities, body, search_log):
    """Search Framework Order articles by keyword."""
    try:
        from lib._framework_order_data import FRAMEWORK_ORDER_ARTICLES
    except ImportError:
        try:
            from _framework_order_data import FRAMEWORK_ORDER_ARTICLES
        except ImportError:
            search_log.append({"search": "framework", "status": "import_error"})
            return []

    articles = []
    combined = body.lower()
    words = set(re.findall(r'[\u0590-\u05FF]{3,}', combined))
    words.update(re.findall(r'[a-zA-Z]{4,}', combined))

    for art_id, art in FRAMEWORK_ORDER_ARTICLES.items():
        title = (art.get("t") or "").lower()
        summary = (art.get("s") or "").lower()
        full_text = (art.get("f") or "")[:300].lower()
        match_count = sum(1 for w in words if w in title or w in summary or w in full_text)
        if match_count >= 2:
            articles.append({
                "article_id": f"fw_{art_id}",
                "title_he": art.get("t", ""),
                "summary_en": art.get("s", ""),
                "full_text_he": (art.get("f") or "")[:2000],
                "source": "framework_order",
            })

    search_log.append({"search": "framework", "status": "ok", "count": len(articles)})
    return articles[:5]


def _search_wikipedia(pkg, db, search_log):
    """Search Wikipedia via tool executor for general knowledge context.
    Fires when we have few customs results — provides knowledge to answer warmly."""
    customs_data_count = (len(pkg.tariff_results) + len(pkg.ordinance_articles)
                          + len(pkg.regulatory_results) + len(pkg.framework_articles))
    # Only search Wikipedia when we don't have enough customs context
    if customs_data_count >= 3:
        return []
    if not db:
        return []

    # Build search terms from body — extract noun phrases / proper nouns
    combined = f"{pkg.original_subject} {pkg.original_body}"
    # Skip very short text
    if len(combined.strip()) < 10:
        return []

    try:
        from lib.tool_executors import ToolExecutor
    except ImportError:
        try:
            from tool_executors import ToolExecutor
        except ImportError:
            search_log.append({"search": "wikipedia", "status": "import_error"})
            return []

    results = []
    try:
        executor = ToolExecutor(db, api_key=None, gemini_key=None)

        # Extract meaningful search terms (skip stop words)
        _STOP = {'מה', 'של', 'את', 'על', 'עם', 'לא', 'כל', 'או', 'גם', 'אם',
                 'אני', 'הוא', 'היא', 'זה', 'יש', 'אין', 'היה', 'היו',
                 'שלך', 'שלי', 'שלום', 'היום', 'איזה', 'איזו', 'טובה',
                 'the', 'is', 'are', 'and', 'or', 'for', 'how', 'what',
                 'you', 'your', 'have', 'can', 'do', 'does'}
        words = re.findall(r'[\u0590-\u05FF]{3,}|[a-zA-Z]{4,}', combined)
        terms = [w for w in words if w.lower() not in _STOP]

        # Search for the most distinctive terms (up to 2 queries)
        searched = set()
        for term in terms[:5]:
            if term in searched:
                continue
            searched.add(term)
            try:
                r = executor.execute("search_wikipedia", {"query": term})
                if r and r.get("found"):
                    results.append({
                        "query": term,
                        "title": r.get("title", ""),
                        "extract": (r.get("extract") or "")[:1500],
                    })
                    if len(results) >= 2:
                        break
            except Exception:
                pass

        search_log.append({"search": "wikipedia", "status": "ok", "count": len(results)})
    except Exception as e:
        search_log.append({"search": "wikipedia_init", "status": f"error:{e}"})

    return results


def _check_cache(subject, body, db, search_log):
    """Check questions_log for cached answer."""
    if not db:
        return None
    try:
        normalized = re.sub(r'\s+', ' ', f"{subject} {body}".lower().strip())
        q_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]
        doc = db.collection("questions_log").document(q_hash).get()
        if doc.exists:
            data = doc.to_dict()
            if data.get('answer_html'):
                search_log.append({"search": "cache", "status": "hit", "hash": q_hash})
                return {
                    "answer_html": data["answer_html"],
                    "answer_text": data.get("answer_text", ""),
                    "intent": data.get("intent", ""),
                    "question_hash": q_hash,
                }
        search_log.append({"search": "cache", "status": "miss"})
    except Exception as e:
        search_log.append({"search": "cache", "status": f"error:{e}"})
    return None


def _build_context_summary(pkg):
    """Build structured text summary for AI prompt injection."""
    parts = [
        "=== נתוני מערכת RCB ===",
        f"שפה שזוהתה: {pkg.detected_language}",
        f"תחום: {pkg.domain}",
    ]

    # Entities
    ents = pkg.entities
    if ents.get("hs_codes"):
        parts.append(f"קודי HS שזוהו: {', '.join(ents['hs_codes'])}")
    if ents.get("product_names"):
        parts.append(f"מוצרים: {', '.join(ents['product_names'])}")
    if ents.get("article_numbers"):
        parts.append(f"סעיפים שהוזכרו: {', '.join(ents['article_numbers'])}")

    # Tariff results
    if pkg.tariff_results:
        parts.append("\n--- תוצאות חיפוש תעריף ---")
        for c in pkg.tariff_results[:5]:
            hs = c.get("hs_code", "")
            desc = c.get("description_he", c.get("description", ""))
            duty = c.get("duty_rate", "")
            parts.append(f"  {hs}: {desc}" + (f" (מכס: {duty})" if duty else ""))

    # Ordinance articles
    if pkg.ordinance_articles:
        parts.append("\n--- מאמרי פקודת המכס ---")
        for a in pkg.ordinance_articles:
            art_id = a.get("article_id", "")
            title = a.get("title_he", "")
            full = a.get("full_text_he", "")
            parts.append(f"\nסעיף {art_id}: {title}")
            if full:
                parts.append(f"נוסח הסעיף: {full}")

    # XML documents
    if pkg.xml_results:
        parts.append("\n--- מסמכי XML רלוונטיים ---")
        for d in pkg.xml_results:
            title = d.get("title", d.get("doc_id", ""))
            excerpt = (d.get("text_excerpt") or "")[:300]
            parts.append(f"  {title}: {excerpt}")

    # Regulatory
    if pkg.regulatory_results:
        parts.append("\n--- מידע רגולטורי ---")
        for r in pkg.regulatory_results:
            hs = r.get("hs_code", r.get("product", ""))
            data = r.get("data", {})
            auths = data.get("authorities", [])
            parts.append(f"  {hs}: {', '.join(str(a) for a in auths[:5])}" if auths else f"  {hs}: (נמצא)")

    # Framework order
    if pkg.framework_articles:
        parts.append("\n--- צווי מסגרת ---")
        for a in pkg.framework_articles:
            art_id = a.get("article_id", "")
            title = a.get("title_he", "")
            full = a.get("full_text_he", "")
            parts.append(f"\n{art_id}: {title}")
            if full:
                parts.append(f"נוסח: {full}")

    # Wikipedia results
    if pkg.wikipedia_results:
        parts.append("\n--- ידע כללי (ויקיפדיה) ---")
        for w in pkg.wikipedia_results:
            parts.append(f"\n{w.get('title', w.get('query', ''))}: {w.get('extract', '')[:800]}")

    # Cached answer
    if pkg.cached_answer:
        parts.append("\n--- תשובה קודמת דומה ---")
        parts.append(pkg.cached_answer.get("answer_text", "(cached)")[:500])

    parts.append("\n=== סוף נתוני מערכת ===")
    return "\n".join(parts)


def _calculate_confidence(pkg):
    """Calculate confidence based on what data was found."""
    score = 0.0
    if pkg.tariff_results:
        score += 0.3
    if pkg.ordinance_articles:
        score += 0.3
    if pkg.xml_results:
        score += 0.1
    if pkg.regulatory_results:
        score += 0.1
    if pkg.framework_articles:
        score += 0.1
    if pkg.wikipedia_results:
        score += 0.15
    if pkg.cached_answer:
        score += 0.3
    if pkg.entities.get("keywords"):
        score += 0.1
    return min(score, 1.0)


# ═══════════════════════════════════════════
#  MAIN PUBLIC FUNCTION
# ═══════════════════════════════════════════

def prepare_context_package(subject, body, db, get_secret_func=None):
    """
    System Intelligence First: search ALL relevant data sources BEFORE AI.

    Returns a ContextPackage with pre-assembled results and a context_summary
    string ready for injection into AI prompts.
    """
    t0 = time.time()
    search_log = []

    # Strip HTML from body
    body_plain = re.sub(r'<[^>]+>', ' ', body or "").strip()
    body_plain = re.sub(r'&\w+;', ' ', body_plain)
    body_plain = re.sub(r'\s+', ' ', body_plain).strip()

    pkg = ContextPackage(
        original_subject=subject or "",
        original_body=body_plain,
        detected_language=_detect_language(subject or "", body_plain),
        search_log=search_log,
    )

    # 1. Extract entities
    pkg.entities = _extract_entities(subject or "", body_plain)

    # 2. Detect domain
    pkg.domain = _detect_domain(pkg.entities, subject or "", body_plain)

    # 3. Check cache first
    try:
        pkg.cached_answer = _check_cache(subject or "", body_plain, db, search_log)
    except Exception as e:
        search_log.append({"search": "cache", "status": f"crash:{e}"})

    # 4. Search tariff
    try:
        pkg.tariff_results = _search_tariff_data(pkg.entities, db, search_log)
    except Exception as e:
        search_log.append({"search": "tariff", "status": f"crash:{e}"})

    # 5. Search ordinance
    try:
        pkg.ordinance_articles = _search_ordinance(
            pkg.entities, subject or "", body_plain, search_log)
    except Exception as e:
        search_log.append({"search": "ordinance", "status": f"crash:{e}"})

    # 6. Search XML documents
    try:
        pkg.xml_results = _search_xml_documents(
            pkg.entities, pkg.domain, db, search_log)
    except Exception as e:
        search_log.append({"search": "xml", "status": f"crash:{e}"})

    # 7. Check regulatory
    try:
        pkg.regulatory_results = _check_regulatory_data(
            pkg.entities, pkg.domain, db, search_log)
    except Exception as e:
        search_log.append({"search": "regulatory", "status": f"crash:{e}"})

    # 8. Search framework order
    try:
        pkg.framework_articles = _search_framework_order(
            pkg.entities, body_plain, search_log)
    except Exception as e:
        search_log.append({"search": "framework", "status": f"crash:{e}"})

    # 8b. Wikipedia search for general knowledge questions
    #     If we found no customs data and there are product names or keywords,
    #     search Wikipedia to provide useful context (never refuse a question)
    try:
        pkg.wikipedia_results = _search_wikipedia(pkg, db, search_log)
    except Exception as e:
        search_log.append({"search": "wikipedia", "status": f"crash:{e}"})

    # 9. Build summary and confidence
    pkg.context_summary = _build_context_summary(pkg)
    pkg.confidence = _calculate_confidence(pkg)

    elapsed = int((time.time() - t0) * 1000)
    search_log.append({"search": "total", "elapsed_ms": elapsed})
    print(f"    📦 SIF context package: domain={pkg.domain}, confidence={pkg.confidence:.2f}, "
          f"tariff={len(pkg.tariff_results)}, ordinance={len(pkg.ordinance_articles)}, "
          f"xml={len(pkg.xml_results)}, regulatory={len(pkg.regulatory_results)}, "
          f"framework={len(pkg.framework_articles)}, elapsed={elapsed}ms")

    return pkg
