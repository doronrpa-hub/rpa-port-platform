"""
Tool Executors for RCB Tool-Calling Classification Engine
==========================================================
ToolExecutor class wraps existing module functions as tool handlers.
Each tool_name maps to a method that calls the real code.

No new logic — just routing + caching + error handling.
"""

import hashlib
import json
import re
import time
import traceback

import requests

from lib.self_learning import SelfLearningEngine
from lib import intelligence
from lib import verification_loop
# NOTE: run_document_agent imported LAZILY inside _extract_invoice() to avoid circular import.
# classification_agents.py -> tool_calling_engine.py -> tool_executors.py -> classification_agents.py


# Dual-use HS chapters (require extra scrutiny)
_DUAL_USE_CHAPTERS = {"28", "29", "36", "84", "85", "87", "90", "93"}
# High-risk origins
_HIGH_RISK_ORIGINS = {"iran", "north korea", "syria", "cuba", "איראן", "צפון קוריאה", "סוריה", "קובה"}

# FTA country name/code → framework_order doc ID (module-level constant, not rebuilt per call)
_FTA_COUNTRY_MAP = {
    "eu": "eu", "european union": "eu", "האיחוד האירופי": "eu",
    "germany": "eu", "france": "eu", "italy": "eu", "spain": "eu",
    "netherlands": "eu", "belgium": "eu", "austria": "eu", "poland": "eu",
    "czech republic": "eu", "czechia": "eu", "romania": "eu",
    "portugal": "eu", "greece": "eu", "sweden": "eu", "denmark": "eu",
    "finland": "eu", "ireland": "eu", "hungary": "eu", "slovakia": "eu",
    "croatia": "eu", "bulgaria": "eu", "lithuania": "eu", "slovenia": "eu",
    "latvia": "eu", "estonia": "eu", "cyprus": "eu", "luxembourg": "eu",
    "malta": "eu",
    "efta": "efta", "switzerland": "efta", "norway": "efta",
    "iceland": "efta", "liechtenstein": "efta", "אפט\"א": "efta",
    "usa": "usa", "us": "usa", "united states": "usa", "america": "usa",
    "ארה\"ב": "usa", "ארצות הברית": "usa",
    "uk": "uk", "gb": "uk", "united kingdom": "uk", "britain": "uk",
    "england": "uk", "בריטניה": "uk", "הממלכה המאוחדת": "uk",
    "turkey": "turkey", "tr": "turkey", "turkiye": "turkey", "טורקיה": "turkey",
    "jordan": "jordan", "jo": "jordan", "ירדן": "jordan",
    "canada": "canada", "ca": "canada", "קנדה": "canada",
    "mexico": "mexico", "mx": "mexico", "מקסיקו": "mexico",
    "mercosur": "mercosur", "brazil": "mercosur", "argentina": "mercosur",
    "uruguay": "mercosur", "paraguay": "mercosur", "מרקוסור": "mercosur",
    "korea": "korea", "kr": "korea", "south korea": "korea", "קוריאה": "korea",
    "colombia": "colombia", "co": "colombia", "קולומביה": "colombia",
    "panama": "panama", "pa": "panama", "פנמה": "panama",
    "ukraine": "ukraine", "ua": "ukraine", "אוקראינה": "ukraine",
    "uae": "uae", "ae": "uae", "united arab emirates": "uae", "אמירויות": "uae",
    "guatemala": "guatemala", "gt": "guatemala", "גואטמלה": "guatemala",
}

# Word boundary keywords for legal_knowledge search — prevents "us" matching "status", "focus", etc.
_LEGAL_EU_KEYWORDS = re.compile(r'\b(?:europe|eu)\b|אירופ|ce mark', re.IGNORECASE)
_LEGAL_US_KEYWORDS = re.compile(r'\b(?:usa|united states)\b|america|\bfda\b|\bul\b|ארצות הברית|ארה', re.IGNORECASE)
_LEGAL_AGENT_KEYWORDS = re.compile(r'\bagent\b|\bbroker\b|סוכנ|עמיל', re.IGNORECASE)

# Wikipedia API constants
_WIKI_USER_AGENT = "RCB-RPA-PORT/1.0 (rcb@rpa-port.co.il)"
_WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
_WIKI_CACHE_TTL_DAYS = 30

# Domain allowlist for external API calls — only these hosts can be queried
_DOMAIN_ALLOWLIST = {
    "en.wikipedia.org",
    "www.wikidata.org",
    "restcountries.com",
    "open.er-api.com",
    "comtradeapi.un.org",
    "world.openfoodfacts.org",
    "api.fda.gov",
}

# Wikidata property IDs → human-readable keys
_WIKIDATA_PROPS = {
    "P31": "instance_of",
    "P279": "subclass_of",
    "P186": "made_from_material",
    "P274": "chemical_formula",
    "P231": "cas_number",
    "P366": "has_use",
    "P2067": "mass",
    "P2054": "density",
}

# Prompt injection sanitizer — applied to ALL external text before it enters AI context
_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "you are now",
    "act as",
    "forget everything",
    "new instructions",
]


def sanitize_external_text(text, max_length=500):
    """Sanitize text from external APIs (Wikipedia, etc.) before passing to AI.
    Hard-truncates at max_length and rejects text containing injection patterns."""
    if not text:
        return ""
    text = text[:max_length]  # hard truncate
    lower = text.lower()
    for pattern in _INJECTION_PATTERNS:
        if pattern in lower:
            return ""  # discard entire field, don't try to clean it
    return text.strip()


def _safe_get(url, params=None, headers=None, timeout=10):
    """HTTP GET with domain whitelist enforcement. Returns Response or None."""
    from urllib.parse import urlparse
    domain = urlparse(url).hostname or ""
    if domain not in _DOMAIN_ALLOWLIST:
        print(f"  [SAFE_GET] Blocked: {domain} not in allowlist")
        return None
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        return resp if resp.status_code == 200 else None
    except Exception as e:
        print(f"  [SAFE_GET] {domain} error: {e}")
        return None


class ToolExecutor:
    """Routes tool calls to existing module functions."""

    def __init__(self, db, api_key, gemini_key=None):
        self.db = db
        self.api_key = api_key
        self.gemini_key = gemini_key
        self._learning = SelfLearningEngine(db)
        # Caches to avoid duplicate API calls within one classification run
        self._fio_cache = {}       # hs_code -> free_import_order result
        self._feo_cache = {}       # hs_code -> free_export_order result
        self._ministry_cache = {}  # hs_code -> route_to_ministries result
        # Per-request collection caches — loaded lazily on first access, avoids repeated .stream() scans
        self._directives_docs = None      # list of (doc_id, dict) for classification_directives (218 docs)
        self._framework_order_docs = None  # list of (doc_id, dict) for framework_order (85 docs)
        self._legal_knowledge_docs = None  # list of (doc_id, dict) for legal_knowledge (19 docs)
        self._wikipedia_cache = {}         # query_key -> wikipedia result (per-request)
        self._ext_cache = {}               # shared cache for tools #15-20 (per-request)
        self._overnight_mode = False       # set True by overnight_brain for Comtrade access
        # Stats
        self._stats = {}

    # ------------------------------------------------------------------
    # Collection cache loaders — read once per ToolExecutor instance
    # ------------------------------------------------------------------

    def _get_directives(self):
        """Lazy-load all classification_directives docs. Cached for request lifetime."""
        if self._directives_docs is None:
            self._directives_docs = [
                (doc.id, doc.to_dict())
                for doc in self.db.collection("classification_directives").stream()
            ]
        return self._directives_docs

    def _get_framework_order(self):
        """Lazy-load all framework_order docs. Cached for request lifetime."""
        if self._framework_order_docs is None:
            self._framework_order_docs = [
                (doc.id, doc.to_dict())
                for doc in self.db.collection("framework_order").stream()
            ]
        return self._framework_order_docs

    def _get_legal_knowledge(self):
        """Lazy-load all legal_knowledge docs. Cached for request lifetime."""
        if self._legal_knowledge_docs is None:
            self._legal_knowledge_docs = [
                (doc.id, doc.to_dict())
                for doc in self.db.collection("legal_knowledge").stream()
            ]
        return self._legal_knowledge_docs

    # ------------------------------------------------------------------
    # Main dispatcher
    # ------------------------------------------------------------------

    def execute(self, tool_name, tool_input):
        """Execute a tool by name. Returns dict result."""
        start = time.time()
        self._stats[tool_name] = self._stats.get(tool_name, 0) + 1

        handler = {
            "check_memory": self._check_memory,
            "search_tariff": self._search_tariff,
            "check_regulatory": self._check_regulatory,
            "lookup_fta": self._lookup_fta,
            "verify_hs_code": self._verify_hs_code,
            "extract_invoice": self._extract_invoice,
            "assess_risk": self._assess_risk,
            "get_chapter_notes": self._get_chapter_notes,
            "lookup_tariff_structure": self._lookup_tariff_structure,
            "lookup_framework_order": self._lookup_framework_order,
            "search_pre_rulings": self._stub_not_available,
            "search_classification_directives": self._search_classification_directives,
            "search_legal_knowledge": self._search_legal_knowledge,
            "run_elimination": self._run_elimination,
            "search_wikipedia": self._search_wikipedia,
            "search_wikidata": self._search_wikidata,
            "lookup_country": self._lookup_country,
            "convert_currency": self._convert_currency,
            "search_comtrade": self._search_comtrade,
            "lookup_food_product": self._lookup_food_product,
            "check_fda_product": self._check_fda_product,
            "search_foreign_tariff": self._stub_not_available,
            "search_court_precedents": self._stub_not_available,
            "search_wco_decisions": self._stub_not_available,
        }.get(tool_name)

        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            result = handler(tool_input)
            elapsed = time.time() - start
            print(f"  [TOOL] {tool_name} completed in {elapsed:.1f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start
            print(f"  [TOOL] {tool_name} FAILED in {elapsed:.1f}s: {e}")
            traceback.print_exc()
            return {"error": str(e), "tool": tool_name}

    def get_stats(self):
        """Return tool call counts for logging."""
        return dict(self._stats)

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _check_memory(self, inp):
        """Wraps SelfLearningEngine.check_classification_memory()."""
        product = inp.get("product_description", "")
        answer, level = self._learning.check_classification_memory(product)
        if answer:
            return {
                "found": True,
                "level": level,
                "hs_code": answer.get("hs_code", ""),
                "confidence": answer.get("confidence", 0),
                "source": answer.get("source", ""),
                "data": answer,
            }
        return {"found": False, "level": level}

    def _search_tariff(self, inp):
        """Wraps intelligence.pre_classify()."""
        result = intelligence.pre_classify(
            self.db,
            inp.get("item_description", ""),
            origin_country=inp.get("origin_country", ""),
            seller_name=inp.get("seller_name", ""),
        )
        return result or {"candidates": [], "regulatory": [], "fta": None, "context_text": ""}

    def _check_regulatory(self, inp):
        """Wraps intelligence.route_to_ministries() + query_free_import_order().
        C3: Checks local free_import_order collection first (instant), then
        falls back to live API if not found locally.
        C4: Also checks local free_export_order collection.
        Caches both to avoid repeat lookups for same HS code."""
        hs_code = inp.get("hs_code", "")

        # Free Import Order (cached per HS)
        if hs_code not in self._fio_cache:
            # C3: Try local Firestore collection first (seeded from data.gov.il)
            local_fio = self._lookup_local_fio(hs_code)
            if local_fio and local_fio.get("found"):
                self._fio_cache[hs_code] = local_fio
            else:
                # Fallback to live API
                self._fio_cache[hs_code] = intelligence.query_free_import_order(self.db, hs_code)
        fio = self._fio_cache[hs_code]

        # Free Export Order (cached per HS) — C4
        if hs_code not in self._feo_cache:
            self._feo_cache[hs_code] = self._lookup_local_feo(hs_code)
        feo = self._feo_cache[hs_code]

        # Ministry routing (cached per HS)
        if hs_code not in self._ministry_cache:
            self._ministry_cache[hs_code] = intelligence.route_to_ministries(self.db, hs_code, fio)
        ministry = self._ministry_cache[hs_code]

        result = {
            "free_import_order": fio,
            "ministry_routing": ministry,
        }
        if feo and feo.get("found"):
            result["free_export_order"] = feo
        return result

    def _lookup_local_fio(self, hs_code):
        """C3: Look up Free Import Order requirements from local Firestore collection.
        Checks exact match first, then parent code match."""
        hs_clean = str(hs_code).replace(".", "").replace(" ", "").replace("/", "").replace("-", "")
        hs_10 = hs_clean.ljust(10, "0")[:10]

        # Build possible doc IDs (exact and with check digit variations)
        candidates = [hs_clean]
        # Also try with common check digit formats
        if "/" in str(hs_code):
            candidates.append(str(hs_code).replace("/", "_").replace(".", "").replace(" ", ""))

        for doc_id in candidates:
            try:
                doc = self.db.collection("free_import_order").document(doc_id).get()
                if doc.exists:
                    data = doc.to_dict()
                    reqs = data.get("requirements", [])
                    return {
                        "hs_code": hs_code,
                        "hs_10": hs_10,
                        "found": True,
                        "source": "local_free_import_order",
                        "items": [{
                            "hs_code": data.get("hs_code", ""),
                            "description": data.get("goods_description", ""),
                            "legal_requirements": [
                                {
                                    "name": r.get("confirmation_type", ""),
                                    "authority": r.get("authority", ""),
                                    "supplement": r.get("appendix", ""),
                                    "conditions": r.get("conditions", ""),
                                    "inception": r.get("inception", ""),
                                }
                                for r in reqs
                            ],
                        }],
                        "authorities": [
                            {"name": a} for a in data.get("authorities_summary", [])
                        ],
                        "has_standards": data.get("has_standards", False),
                        "has_lab_testing": data.get("has_lab_testing", False),
                        "appendices": data.get("appendices", []),
                        "conditions_type": data.get("conditions_type", ""),
                        "inception_type": data.get("inception_type", ""),
                        "active_count": data.get("active_count", 0),
                        "cached": False,
                    }
            except Exception:
                continue

        # Try parent code lookup (strip last 2 digits at a time)
        for trim_len in [2, 4]:
            if len(hs_clean) > trim_len:
                parent = hs_clean[:-trim_len]
                try:
                    parent_10 = parent.ljust(10, "0")[:10]
                    # Query by hs_10 prefix
                    query = (
                        self.db.collection("free_import_order")
                        .where("hs_10", ">=", parent_10)
                        .where("hs_10", "<", parent_10[:-1] + chr(ord(parent_10[-1]) + 1))
                        .limit(5)
                    )
                    parent_docs = list(query.stream())
                    if parent_docs:
                        # Merge results from parent matches
                        all_auths = set()
                        all_items = []
                        for pd in parent_docs:
                            pd_data = pd.to_dict()
                            all_auths.update(pd_data.get("authorities_summary", []))
                            for r in pd_data.get("requirements", []):
                                all_items.append({
                                    "name": r.get("confirmation_type", ""),
                                    "authority": r.get("authority", ""),
                                    "supplement": r.get("appendix", ""),
                                    "inherited_from_parent": True,
                                })
                        if all_items:
                            return {
                                "hs_code": hs_code,
                                "hs_10": hs_10,
                                "found": True,
                                "source": "local_free_import_order_parent",
                                "items": [{
                                    "hs_code": parent_10,
                                    "description": f"Parent code match ({len(parent_docs)} codes)",
                                    "legal_requirements": all_items[:20],
                                }],
                                "authorities": [{"name": a} for a in sorted(all_auths)],
                                "cached": False,
                            }
                except Exception:
                    continue

        return None

    def _lookup_local_feo(self, hs_code):
        """C4: Look up Free Export Order requirements from local Firestore collection.
        Same pattern as _lookup_local_fio but for export (979 HS codes)."""
        hs_clean = str(hs_code).replace(".", "").replace(" ", "").replace("/", "").replace("-", "")

        candidates = [hs_clean]
        if "/" in str(hs_code):
            candidates.append(str(hs_code).replace("/", "_").replace(".", "").replace(" ", ""))

        for doc_id in candidates:
            try:
                doc = self.db.collection("free_export_order").document(doc_id).get()
                if doc.exists:
                    data = doc.to_dict()
                    return {
                        "hs_code": hs_code,
                        "found": True,
                        "source": "local_free_export_order",
                        "goods_description": data.get("goods_description", ""),
                        "authorities": data.get("authorities_summary", []),
                        "confirmation_types": data.get("confirmation_types", []),
                        "appendices": data.get("appendices", []),
                        "has_absolute": data.get("has_absolute", False),
                        "has_partial": data.get("has_partial", False),
                        "active_count": data.get("active_count", 0),
                        "requirements": [
                            {
                                "confirmation_type": r.get("confirmation_type", ""),
                                "authority": r.get("authority", ""),
                                "appendix": r.get("appendix", ""),
                                "inception_code": r.get("inception_code", ""),
                            }
                            for r in data.get("requirements", [])[:20]
                        ],
                    }
            except Exception:
                continue

        # Parent code fallback (4-digit chapter match)
        if len(hs_clean) >= 4:
            prefix = hs_clean[:4]
            try:
                query = (
                    self.db.collection("free_export_order")
                    .where("hs_10", ">=", prefix)
                    .where("hs_10", "<", prefix[:-1] + chr(ord(prefix[-1]) + 1))
                    .limit(3)
                )
                parent_docs = list(query.stream())
                if parent_docs:
                    all_auths = set()
                    all_types = set()
                    for pd in parent_docs:
                        pd_data = pd.to_dict()
                        all_auths.update(pd_data.get("authorities_summary", []))
                        all_types.update(pd_data.get("confirmation_types", []))
                    return {
                        "hs_code": hs_code,
                        "found": True,
                        "source": "local_free_export_order_parent",
                        "authorities": sorted(all_auths),
                        "confirmation_types": sorted(all_types),
                        "parent_matches": len(parent_docs),
                    }
            except Exception:
                pass

        return None

    def _lookup_fta(self, inp):
        """Wraps intelligence.lookup_fta() + enriches with C5 framework_order FTA clauses."""
        result = intelligence.lookup_fta(
            self.db,
            inp.get("hs_code", ""),
            inp.get("origin_country", ""),
        )
        # C5: Enrich with framework_order FTA clause if available
        origin = (inp.get("origin_country", "") or "").strip().lower()
        if origin:
            fw_fta = self._lookup_fw_fta_clause(origin)
            if fw_fta:
                result["framework_order_clause"] = fw_fta
        return result

    def _lookup_fw_fta_clause(self, origin_country):
        """Look up FTA clause from framework_order collection by country.
        Uses module-level _FTA_COUNTRY_MAP and cached collection data."""
        code = _FTA_COUNTRY_MAP.get(origin_country.lower())
        if not code:
            return None
        doc_id = f"fta_{code}"
        # Search cached collection (avoids per-call Firestore read)
        for did, data in self._get_framework_order():
            if did == doc_id:
                return {
                    "country_code": data.get("country_code", ""),
                    "country_en": data.get("country_en", ""),
                    "country_he": data.get("country_he", ""),
                    "supplements": data.get("supplements", []),
                    "is_duty_free": data.get("is_duty_free", False),
                    "has_reduction": data.get("has_reduction", False),
                    "clause_text": data.get("clause_text", "")[:2000],
                    "source": "framework_order_c5",
                }
        return None

    def _verify_hs_code(self, inp):
        """Wraps verification_loop.verify_hs_code()."""
        hs_code = inp.get("hs_code", "")
        # Use cached FIO result if available
        fio = self._fio_cache.get(hs_code)
        return verification_loop.verify_hs_code(self.db, hs_code, free_import_result=fio)

    def _extract_invoice(self, inp):
        """Wraps classification_agents.run_document_agent()."""
        from lib.classification_agents import run_document_agent  # Lazy import to avoid circular
        doc_text = inp.get("document_text", "")
        result = run_document_agent(self.api_key, doc_text, gemini_key=self.gemini_key)
        if isinstance(result, dict):
            return result
        return {"error": "Invoice extraction returned non-dict"}

    def _assess_risk(self, inp):
        """Rule-based risk assessment. No AI calls."""
        hs_code = inp.get("hs_code", "")
        declared_value = inp.get("declared_value", 0)
        origin = (inp.get("origin_country", "") or "").lower()
        description = inp.get("item_description", "")

        hs_clean = str(hs_code).replace(".", "").replace(" ", "")
        chapter = hs_clean[:2].zfill(2) if len(hs_clean) >= 2 else ""

        items = []
        level = "low"

        # Check 1: Dual-use chapters
        if chapter in _DUAL_USE_CHAPTERS:
            items.append({
                "item": description[:60],
                "issue": f"פרק {chapter} — טובין דו-שימושיים, עשוי לדרוש רישיון יבוא",
                "recommendation": "לוודא שהמוצר אינו ברשימת הפיקוח הביטחוני",
            })
            level = "medium"

        # Check 2: High-risk origin
        if origin in _HIGH_RISK_ORIGINS:
            items.append({
                "item": origin,
                "issue": "מדינת מקור בסיכון גבוה — סנקציות / מגבלות יבוא",
                "recommendation": "לוודא שאין צו איסור יבוא ממדינה זו",
            })
            level = "high"

        # Check 3: Suspiciously low value (heuristic)
        if declared_value and declared_value > 0:
            if declared_value < 50 and chapter in {"84", "85", "87", "90"}:
                items.append({
                    "item": f"${declared_value}",
                    "issue": "ערך מוצהר נמוך באופן חשוד עבור פרק זה",
                    "recommendation": "לבדוק שומת ערך מול מחירי שוק",
                })
                if level == "low":
                    level = "medium"

        # Hebrew level mapping
        level_he = {"low": "נמוך", "medium": "בינוני", "high": "גבוה"}.get(level, "נמוך")

        return {"risk": {"level": level_he, "items": items}}

    def _get_chapter_notes(self, inp):
        """Fetch structured chapter notes from chapter_notes collection.
        Session 27: Now reads from chapter_notes (parsed heading tree with
        Hebrew descriptions, duty rates, keywords) instead of raw tariff_chapters."""
        chapter = str(inp.get("chapter", "")).replace(".", "").strip()
        if len(chapter) == 1:
            chapter = "0" + chapter
        doc_id = f"chapter_{chapter}"
        try:
            doc = self.db.collection("chapter_notes").document(doc_id).get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    "found": True,
                    "chapter": chapter,
                    "chapter_name": data.get("chapter_title_he", ""),
                    "chapter_description": data.get("chapter_description_he", ""),
                    "preamble": data.get("preamble", ""),
                    "preamble_en": data.get("preamble_en", ""),
                    "notes": data.get("notes", []),
                    "notes_en": data.get("notes_en", []),
                    "exclusions": data.get("exclusions", []),
                    "inclusions": data.get("inclusions", []),
                    "supplementary_israeli": data.get("supplementary_israeli", []),
                    "subheading_rules": data.get("subheading_rules", []),
                    "heading_summary": data.get("heading_summary", ""),
                    "headings_count": data.get("headings_count", 0),
                    "hs_codes_count": data.get("hs_codes_count", 0),
                    "keywords": data.get("keywords", [])[:50],
                    "duty_rates": data.get("duty_rates_summary", {}),
                }
            # Fallback to old tariff_chapters
            old_doc_id = f"import_chapter_{chapter}"
            old_doc = self.db.collection("tariff_chapters").document(old_doc_id).get()
            if old_doc.exists:
                old_data = old_doc.to_dict()
                return {
                    "found": True,
                    "chapter": chapter,
                    "chapter_name": old_data.get("chapterName", ""),
                    "chapter_description": old_data.get("chapterDescription", ""),
                    "headings": old_data.get("headings", [])[:20],
                    "hs_codes_count": len(old_data.get("hsCodes", [])),
                }
            return {"found": False, "chapter": chapter, "message": f"Chapter {chapter} not found"}
        except Exception as e:
            return {"found": False, "error": str(e)}

    def _lookup_tariff_structure(self, inp):
        """Look up tariff structure: sections, chapters, additions, PDF URLs.
        Reads from tariff_structure collection (seeded from israeli_customs_tariff_structure.xml)."""
        query = str(inp.get("query", "")).strip()
        if not query:
            return {"found": False, "error": "No query provided"}

        try:
            # Case 1: Query by chapter number (e.g., "73", "03")
            chapter_num = query.lstrip("0") if query.isdigit() else None
            if chapter_num and 1 <= int(chapter_num) <= 98:
                chapter_padded = query.zfill(2)
                doc = self.db.collection("tariff_structure").document(f"chapter_{chapter_padded}").get()
                if doc.exists:
                    data = doc.to_dict()
                    # Also fetch the parent section
                    section_num = data.get("section", "")
                    section_data = {}
                    if section_num:
                        sec_doc = self.db.collection("tariff_structure").document(f"section_{section_num}").get()
                        if sec_doc.exists:
                            section_data = sec_doc.to_dict()
                    return {
                        "found": True,
                        "type": "chapter",
                        "chapter": chapter_padded,
                        "name_he": data.get("name_he", ""),
                        "name_en": data.get("name_en", ""),
                        "section": section_num,
                        "section_name_he": data.get("section_name_he", "") or section_data.get("name_he", ""),
                        "section_name_en": data.get("section_name_en", "") or section_data.get("name_en", ""),
                        "section_pdf_url": section_data.get("pdf_url", ""),
                        "section_chapters": section_data.get("chapters", []),
                    }

            # Case 2: Query by section (Roman numeral, e.g., "XV", "I", "XVI")
            roman_upper = query.upper()
            valid_roman = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
                           "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII",
                           "XIX", "XX", "XXI", "XXII"}
            if roman_upper in valid_roman:
                doc = self.db.collection("tariff_structure").document(f"section_{roman_upper}").get()
                if doc.exists:
                    data = doc.to_dict()
                    return {
                        "found": True,
                        "type": "section",
                        "section": roman_upper,
                        "name_he": data.get("name_he", ""),
                        "name_en": data.get("name_en", ""),
                        "chapters": data.get("chapters", []),
                        "chapter_names": data.get("chapter_names", {}),
                        "pdf_url": data.get("pdf_url", ""),
                    }

            # Case 3: "all_sections" — overview
            if query.lower() in ("all_sections", "all", "overview"):
                sections = []
                for doc in self.db.collection("tariff_structure").where("type", "==", "section").stream():
                    data = doc.to_dict()
                    sections.append({
                        "section": data.get("number", ""),
                        "name_he": data.get("name_he", ""),
                        "name_en": data.get("name_en", ""),
                        "chapters": data.get("chapters", []),
                    })
                return {"found": True, "type": "overview", "sections": sections, "count": len(sections)}

            # Case 4: Keyword search — search section/chapter names
            query_lower = query.lower()
            matches = []
            for doc in self.db.collection("tariff_structure").stream():
                data = doc.to_dict()
                name_he = (data.get("name_he", "") or "").lower()
                name_en = (data.get("name_en", "") or "").lower()
                if query_lower in name_he or query_lower in name_en or query in (data.get("name_he", "") or ""):
                    matches.append({
                        "doc_id": doc.id,
                        "type": data.get("type", ""),
                        "name_he": data.get("name_he", ""),
                        "name_en": data.get("name_en", ""),
                        "section": data.get("section", "") or data.get("number", ""),
                        "chapters": data.get("chapters", []),
                    })
            if matches:
                return {"found": True, "type": "search", "query": query, "results": matches[:10]}

            return {"found": False, "query": query, "message": "No matching section, chapter, or keyword found"}

        except Exception as e:
            return {"found": False, "error": str(e)}

    def _lookup_framework_order(self, inp):
        """Look up Framework Order (צו מסגרת) data: legal definitions, FTA clauses,
        classification rules, and addition rules.
        C5: Reads from cached framework_order collection (85 docs, loaded once per request)."""
        query = str(inp.get("query", "")).strip()
        if not query:
            return {"found": False, "error": "No query provided"}

        query_lower = query.lower()
        all_docs = self._get_framework_order()

        try:
            # Case 1: "definitions" — return all legal definitions
            if query_lower in ("definitions", "הגדרות", "all_definitions"):
                defs = []
                for doc_id, data in all_docs:
                    if data.get("type") == "definition":
                        defs.append({
                            "term": data.get("term", ""),
                            "definition": data.get("definition", "")[:500],
                        })
                return {"found": bool(defs), "type": "definitions", "definitions": defs, "count": len(defs)}

            # Case 2: Specific definition term lookup
            if query_lower.startswith("def:") or query_lower.startswith("define:"):
                term = query.split(":", 1)[1].strip()
                matches = []
                for doc_id, data in all_docs:
                    if data.get("type") == "definition":
                        doc_term = data.get("term", "")
                        if term in doc_term or term.lower() in doc_term.lower():
                            matches.append({
                                "term": doc_term,
                                "definition": data.get("definition", ""),
                            })
                return {"found": bool(matches), "type": "definition_search", "term": term,
                        "results": matches, "count": len(matches)}

            # Case 3: "fta" or country name — FTA clause lookup
            if query_lower.startswith("fta") or query_lower in (
                "eu", "efta", "usa", "uk", "turkey", "jordan", "canada", "mexico",
                "mercosur", "korea", "colombia", "panama", "ukraine", "uae", "guatemala",
            ):
                country = query_lower.replace("fta:", "").replace("fta ", "").strip()
                if country == "fta":
                    clauses = []
                    for doc_id, data in all_docs:
                        if data.get("type") == "fta_clause":
                            clauses.append({
                                "country_code": data.get("country_code", ""),
                                "country_en": data.get("country_en", ""),
                                "country_he": data.get("country_he", ""),
                                "is_duty_free": data.get("is_duty_free", False),
                                "has_reduction": data.get("has_reduction", False),
                                "supplements": data.get("supplements", []),
                            })
                    return {"found": bool(clauses), "type": "fta_overview", "clauses": clauses, "count": len(clauses)}
                else:
                    fw_fta = self._lookup_fw_fta_clause(country)
                    if fw_fta:
                        return {"found": True, "type": "fta_clause", **fw_fta}
                    return {"found": False, "type": "fta_clause", "query": country,
                            "message": f"No FTA clause found for '{country}'"}

            # Case 4: "classification_rules" or "rules"
            if query_lower in ("classification_rules", "rules", "סיווג"):
                rules = []
                for doc_id, data in all_docs:
                    if data.get("type") == "classification_rule":
                        rules.append({
                            "rule_type": data.get("rule_type", ""),
                            "title": data.get("title", ""),
                            "title_en": data.get("title_en", ""),
                            "text": data.get("text", "")[:2000],
                        })
                return {"found": bool(rules), "type": "classification_rules", "rules": rules, "count": len(rules)}

            # Case 5: Addition by ID (e.g., "addition_3", "3")
            add_match = None
            if query_lower.startswith("addition_") or query_lower.startswith("addition "):
                add_match = query.split("_", 1)[-1].split(" ", 1)[-1].strip()
            elif query.isdigit():
                add_match = query
            if add_match:
                target_id = f"addition_{add_match}"
                for doc_id, data in all_docs:
                    if doc_id == target_id:
                        return {
                            "found": True,
                            "type": "addition_rule",
                            "addition_id": data.get("addition_id", ""),
                            "title": data.get("title", ""),
                            "start_date": data.get("start_date", ""),
                            "end_date": data.get("end_date", ""),
                            "rules_text": data.get("rules_text", "")[:3000],
                            "versions_count": data.get("versions_count", 0),
                        }

            # Case 6: General text search across all cached docs
            matches = []
            for doc_id, data in all_docs:
                if doc_id.startswith("_"):
                    continue
                searchable = " ".join([
                    str(data.get("term", "")),
                    str(data.get("title", "")),
                    str(data.get("definition", "")),
                    str(data.get("country_en", "")),
                    str(data.get("country_he", "")),
                ]).lower()
                if query_lower in searchable:
                    matches.append({
                        "doc_id": doc_id,
                        "type": data.get("type", ""),
                        "term": data.get("term", ""),
                        "title": data.get("title", ""),
                        "country_en": data.get("country_en", ""),
                        "snippet": (data.get("definition", "") or data.get("text", "")
                                    or data.get("clause_text", ""))[:300],
                    })
            if matches:
                return {"found": True, "type": "search", "query": query, "results": matches[:10], "count": len(matches)}

            return {"found": False, "query": query, "message": "No matching framework order data found"}

        except Exception as e:
            return {"found": False, "error": str(e)}

    def _search_classification_directives(self, inp):
        """Search classification directives (הנחיות סיווג) from shaarolami.
        C6: 218 directives enriched with directive_id, title, content, dates.
        Search by HS code, chapter, directive_id, or keyword.
        Uses cached collection (loaded once per request, not per tool call)."""
        query = str(inp.get("query", "")).strip()
        hs_code = str(inp.get("hs_code", "")).strip()
        chapter = str(inp.get("chapter", "")).strip()

        if not query and not hs_code and not chapter:
            return {"found": False, "error": "Provide query, hs_code, or chapter"}

        all_docs = self._get_directives()

        try:
            results = []
            seen_ids = set()  # dedup across strategies

            def _add(doc_id, data, limit):
                if doc_id not in seen_ids and len(results) < limit:
                    seen_ids.add(doc_id)
                    results.append(self._format_directive(doc_id, data))

            # Strategy 1: Search by HS code (exact or prefix match)
            if hs_code:
                hs_clean = hs_code.replace(".", "").replace(" ", "").replace("/", "")
                for doc_id, data in all_docs:
                    phs = (data.get("primary_hs_code", "") or "").replace(".", "")
                    hs_mentioned = data.get("hs_codes_mentioned", [])
                    related = data.get("related_hs_codes", [])

                    match = False
                    if hs_clean and phs and (hs_clean.startswith(phs[:4]) or phs.startswith(hs_clean[:4])):
                        match = True
                    if not match:
                        for h in hs_mentioned + related:
                            h_clean = str(h).replace(".", "").replace(" ", "")
                            if hs_clean[:4] == h_clean[:4]:
                                match = True
                                break

                    if match:
                        _add(doc_id, data, 5)
                        if len(results) >= 5:
                            break

            # Strategy 2: Search by chapter
            if not results and chapter:
                ch = chapter.zfill(2)
                for doc_id, data in all_docs:
                    chapters_covered = [str(c).zfill(2) for c in data.get("chapters_covered", [])]
                    title = data.get("title", "")
                    if ch in chapters_covered or title.startswith(f"{ch}."):
                        _add(doc_id, data, 10)
                        if len(results) >= 10:
                            break

            # Strategy 3: Search by directive_id
            if not results and query:
                if re.match(r'\d{1,3}/\d{2,4}', query):
                    for doc_id, data in all_docs:
                        if data.get("directive_id") == query:
                            _add(doc_id, data, 5)
                            break

            # Strategy 4: Keyword search in title + content
            if not results and query:
                q_lower = query.lower()
                for doc_id, data in all_docs:
                    searchable = " ".join([
                        str(data.get("title", "")),
                        str(data.get("content", "")),
                        str(data.get("summary", "")),
                        " ".join(data.get("key_terms", [])),
                    ]).lower()
                    if q_lower in searchable:
                        _add(doc_id, data, 5)
                        if len(results) >= 5:
                            break

            if results:
                return {"found": True, "count": len(results), "directives": results}
            return {"found": False, "query": query or hs_code or chapter,
                    "message": "No matching classification directive found"}

        except Exception as e:
            return {"found": False, "error": str(e)}

    @staticmethod
    def _format_directive(doc_id, data):
        """Format a directive doc for tool output."""
        return {
            "doc_id": doc_id,
            "directive_id": data.get("directive_id", ""),
            "title": data.get("title", ""),
            "directive_type": data.get("directive_type", ""),
            "primary_hs_code": data.get("primary_hs_code", ""),
            "related_hs_codes": data.get("related_hs_codes", []),
            "date_opened": data.get("date_opened", ""),
            "date_expires": data.get("date_expires", ""),
            "is_active": data.get("is_active", True),
            "content": (data.get("content", "") or data.get("summary", ""))[:2000],
        }

    def _search_legal_knowledge(self, inp):
        """Search legal knowledge: Customs Ordinance chapters, customs agents law,
        EU/US standards reforms. C8: 19 docs from cached legal_knowledge collection.
        Uses word-boundary regex for English keywords to prevent false positives."""
        query = str(inp.get("query", "")).strip()
        if not query:
            return {"found": False, "error": "No query provided"}

        all_docs = self._get_legal_knowledge()

        try:
            # Case 1: Ordinance chapter by number — direct lookup from cache
            if query.isdigit() and 1 <= int(query) <= 15:
                target_id = f"ordinance_ch_{query.zfill(2)}"
                for doc_id, data in all_docs:
                    if doc_id == target_id:
                        return {
                            "found": True, "type": "ordinance_chapter",
                            "chapter_number": data.get("chapter_number", 0),
                            "title_he": data.get("title_he", ""),
                            "title_en": data.get("title_en", ""),
                            "text": data.get("text", "")[:3000],
                            "sections_count": data.get("sections_count", 0),
                        }

            # Case 2: Customs agents — word-boundary regex prevents "reagent" matching "agent"
            if _LEGAL_AGENT_KEYWORDS.search(query):
                for doc_id, data in all_docs:
                    if doc_id == "customs_agents_law":
                        return {
                            "found": True, "type": "customs_agents_law",
                            "law_name_he": data.get("law_name_he", ""),
                            "law_name_en": data.get("law_name_en", ""),
                            "key_topics": data.get("key_topics", []),
                            "law_references": data.get("law_references", [])[:5],
                            "chapter_11_text": data.get("chapter_11_text", "")[:3000],
                        }

            # Case 3: EU reform — word-boundary regex prevents "queue" matching "eu"
            if _LEGAL_EU_KEYWORDS.search(query):
                for doc_id, data in all_docs:
                    if doc_id == "reform_eu_standards":
                        return {"found": True, "type": "reform", **{
                            k: v for k, v in data.items()
                            if k not in ("source", "seeded_at")
                        }}

            # Case 4: US reform — word-boundary regex prevents "status"/"focus" matching "us"
            if _LEGAL_US_KEYWORDS.search(query):
                for doc_id, data in all_docs:
                    if doc_id == "reform_us_standards":
                        return {"found": True, "type": "reform", **{
                            k: v for k, v in data.items()
                            if k not in ("source", "seeded_at")
                        }}

            # Case 5: General keyword search across cached docs
            query_lower = query.lower()
            matches = []
            for doc_id, data in all_docs:
                if doc_id.startswith("_"):
                    continue
                searchable = " ".join([
                    str(data.get("title_he", "")),
                    str(data.get("title_en", "")),
                    str(data.get("reform_name_he", "")),
                    str(data.get("law_name_he", "")),
                    str(data.get("text", ""))[:2000],
                ]).lower()
                if query_lower in searchable:
                    matches.append({
                        "doc_id": doc_id,
                        "type": data.get("type", ""),
                        "title": data.get("title_he", "") or data.get("reform_name_he", "") or data.get("law_name_he", ""),
                    })
            if matches:
                return {"found": True, "type": "search", "results": matches[:10], "count": len(matches)}

            return {"found": False, "query": query, "message": "No matching legal knowledge found"}
        except Exception as e:
            return {"found": False, "error": str(e)}

    def _run_elimination(self, inp):
        """Run the elimination engine on candidate HS codes.

        Wraps elimination_engine.eliminate() — walks the tariff tree
        deterministically and returns surviving candidates.
        """
        try:
            from lib.elimination_engine import eliminate, make_product_info
        except ImportError:
            return {"available": False, "message": "Elimination engine not available"}

        raw_candidates = inp.get("candidates", [])
        if not raw_candidates or len(raw_candidates) < 2:
            return {"error": "Need at least 2 candidates to run elimination"}

        # Build product info from input fields
        product_info = make_product_info({
            "description": inp.get("product_description", ""),
            "material": inp.get("product_material", ""),
            "form": inp.get("product_form", ""),
            "use": inp.get("product_use", ""),
            "origin_country": inp.get("origin_country", ""),
        })

        # Build HSCandidate-compatible dicts from raw input
        candidates = []
        for c in raw_candidates:
            hs = str(c.get("hs_code", "")).replace(".", "").replace("/", "").replace(" ", "").strip()
            if not hs or len(hs) < 4:
                continue
            chapter = hs[:2].zfill(2)
            candidates.append({
                "hs_code": hs,
                "section": "",
                "chapter": chapter,
                "heading": hs[:4] if len(hs) >= 4 else "",
                "subheading": hs[:6] if len(hs) >= 6 else "",
                "confidence": c.get("confidence", 0),
                "source": "tool_calling",
                "description": c.get("description", ""),
                "description_en": c.get("description_en", ""),
                "duty_rate": c.get("duty_rate", ""),
                "alive": True,
                "elimination_reason": "",
                "eliminated_at_level": "",
            })

        if len(candidates) < 2:
            return {"error": "Need at least 2 valid candidates after cleanup"}

        result = eliminate(
            self.db, product_info, candidates,
            api_key=self.api_key, gemini_key=self.gemini_key,
        )

        # Return a concise summary suitable for the AI tool loop
        survivors = result.get("survivors", [])
        return {
            "input_count": result.get("input_count", 0),
            "survivor_count": result.get("survivor_count", 0),
            "survivors": [
                {
                    "hs_code": s["hs_code"],
                    "confidence": s.get("confidence", 0),
                    "description": s.get("description", "")[:120],
                }
                for s in survivors
            ],
            "eliminated": [
                {
                    "hs_code": e["hs_code"],
                    "reason": e.get("elimination_reason", "")[:120],
                }
                for e in result.get("eliminated", [])
            ],
            "steps_summary": [
                {
                    "level": st.get("level", ""),
                    "eliminated_codes": st.get("eliminated_codes", []),
                    "reasoning": st.get("reasoning", "")[:120],
                }
                for st in result.get("steps", [])
                if st.get("eliminated_codes")
            ][:8],
            "needs_questions": result.get("needs_questions", False),
        }

    def _search_wikipedia(self, inp):
        """Search Wikipedia for product/material knowledge.
        FREE — no API key needed. Caches in Firestore (30-day TTL).
        Two-step: search API to find best title, then summary API for extract."""
        query = str(inp.get("query", "")).strip()
        if not query or len(query) < 2:
            return {"found": False, "error": "Query too short"}

        # Per-request cache
        cache_key = query.lower()
        if cache_key in self._wikipedia_cache:
            return self._wikipedia_cache[cache_key]

        # Firestore cache (30-day TTL)
        doc_id = hashlib.md5(cache_key.encode()).hexdigest()
        try:
            cached_doc = self.db.collection("wikipedia_cache").document(doc_id).get()
            if cached_doc.exists:
                data = cached_doc.to_dict()
                cached_at = data.get("cached_at", "")
                # Check TTL (30 days)
                if cached_at:
                    from datetime import datetime, timezone, timedelta
                    try:
                        cached_dt = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
                        if datetime.now(timezone.utc) - cached_dt < timedelta(days=_WIKI_CACHE_TTL_DAYS):
                            result = data.get("result", {})
                            # Re-sanitize cached content (may predate sanitizer)
                            for field in ("title", "extract", "description"):
                                if field in result:
                                    result[field] = sanitize_external_text(
                                        result[field], max_length=2000 if field == "extract" else 300
                                    )
                            result["source"] = "wikipedia_cache"
                            self._wikipedia_cache[cache_key] = result
                            return result
                    except (ValueError, TypeError):
                        pass
        except Exception:
            pass

        # Step 1: Search Wikipedia for best matching title
        headers = {"User-Agent": _WIKI_USER_AGENT}
        title = None
        search_results = []
        try:
            resp = requests.get(
                _WIKI_SEARCH_URL,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": 3,
                },
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("query", {}).get("search", [])
                if hits:
                    title = hits[0].get("title", "")
                    search_results = [
                        {
                            "title": sanitize_external_text(h.get("title", ""), max_length=200),
                            "snippet": sanitize_external_text(
                                re.sub(r"<[^>]+>", "", h.get("snippet", "")), max_length=500
                            ),
                        }
                        for h in hits[:3]
                    ]
        except Exception as e:
            return {"found": False, "error": f"Wikipedia search failed: {e}"}

        if not title:
            result = {"found": False, "query": query, "message": "No Wikipedia article found"}
            self._wikipedia_cache[cache_key] = result
            return result

        # Step 2: Get page summary via REST API
        try:
            summary_url = _WIKI_SUMMARY_URL.format(title=requests.utils.quote(title))
            resp = requests.get(summary_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                result = {
                    "found": True,
                    "title": sanitize_external_text(data.get("title", title), max_length=200),
                    "extract": sanitize_external_text(data.get("extract", ""), max_length=2000),
                    "description": sanitize_external_text(data.get("description", ""), max_length=300),
                    "categories": data.get("categories", []),
                    "lang_links": data.get("lang_links", []),
                    "page_url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                    "source": "wikipedia_api",
                    "other_results": search_results[1:] if len(search_results) > 1 else [],
                }
            else:
                # Fallback: return search results without summary
                result = {
                    "found": True,
                    "title": sanitize_external_text(title, max_length=200),
                    "extract": sanitize_external_text(
                        search_results[0].get("snippet", "") if search_results else "", max_length=500
                    ),
                    "source": "wikipedia_search",
                    "other_results": search_results[1:] if len(search_results) > 1 else [],
                }
        except Exception as e:
            result = {"found": False, "error": f"Wikipedia summary failed: {e}"}
            self._wikipedia_cache[cache_key] = result
            return result

        # Cache in per-request memory
        self._wikipedia_cache[cache_key] = result

        # Cache in Firestore (30-day TTL) — non-blocking, fire-and-forget
        if result.get("found"):
            try:
                from datetime import datetime, timezone
                self.db.collection("wikipedia_cache").document(doc_id).set({
                    "query": query,
                    "cache_key": cache_key,
                    "result": result,
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass  # Cache write failure is non-fatal

        return result

    # ------------------------------------------------------------------
    # Shared external API helper (Tools #15-20)
    # ------------------------------------------------------------------

    def _cached_external_lookup(self, cache_key, collection_name, ttl_days, fetcher_fn, allowed_keys=None):
        """Shared external API lookup with per-request + Firestore caching.
        fetcher_fn() should return a dict (the raw result)."""
        ext_key = f"{collection_name}:{cache_key}"
        if ext_key in self._ext_cache:
            return self._ext_cache[ext_key]

        doc_id = hashlib.md5(cache_key.encode()).hexdigest()
        try:
            cached_doc = self.db.collection(collection_name).document(doc_id).get()
            if cached_doc.exists:
                data = cached_doc.to_dict()
                cached_at = data.get("cached_at", "")
                if cached_at:
                    from datetime import datetime, timezone, timedelta
                    try:
                        cached_dt = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
                        if datetime.now(timezone.utc) - cached_dt < timedelta(days=ttl_days):
                            result = data.get("result", {})
                            result["source"] = f"{collection_name}"
                            self._ext_cache[ext_key] = result
                            return result
                    except (ValueError, TypeError):
                        pass
        except Exception:
            pass

        result = fetcher_fn()

        if allowed_keys and isinstance(result, dict):
            result = {k: v for k, v in result.items()
                      if k in allowed_keys or k in ("found", "error", "source", "query", "message")}

        if isinstance(result, dict):
            for k, v in list(result.items()):
                if isinstance(v, str) and k not in ("source", "query", "error", "message"):
                    result[k] = sanitize_external_text(
                        v, max_length=1000 if k in ("extract", "indications_and_usage") else 500
                    )

        self._ext_cache[ext_key] = result
        if isinstance(result, dict) and result.get("found"):
            try:
                from datetime import datetime, timezone
                self.db.collection(collection_name).document(doc_id).set({
                    "cache_key": cache_key,
                    "result": result,
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass

        return result

    # ------------------------------------------------------------------
    # Tool #15: search_wikidata
    # ------------------------------------------------------------------

    def _search_wikidata(self, inp):
        """Search Wikidata for structured product facts (material, formula, CAS).
        FREE — no API key. Cached 60 days."""
        query = str(inp.get("query", "")).strip()
        if not query or len(query) < 2:
            return {"found": False, "error": "Query too short"}

        _ALLOWED = {"found", "source", "query", "qid", "label", "description",
                     "instance_of", "subclass_of", "made_from_material",
                     "chemical_formula", "cas_number", "has_use", "mass", "density"}

        def _fetch():
            headers = {"User-Agent": _WIKI_USER_AGENT}
            # Step 1: Search for entity
            resp = _safe_get(
                "https://www.wikidata.org/w/api.php",
                params={"action": "wbsearchentities", "search": query,
                        "language": "en", "format": "json", "limit": "1"},
                headers=headers,
            )
            if not resp:
                return {"found": False, "query": query, "error": "Wikidata search failed"}
            data = resp.json()
            results = data.get("search", [])
            if not results:
                return {"found": False, "query": query, "message": "No Wikidata entity found"}

            qid = results[0].get("id", "")
            label = results[0].get("label", "")
            desc = results[0].get("description", "")

            # Step 2: Get entity claims
            resp2 = _safe_get(
                "https://www.wikidata.org/w/api.php",
                params={"action": "wbgetentities", "ids": qid,
                        "languages": "en", "format": "json", "props": "claims"},
                headers=headers,
            )
            result = {"found": True, "qid": qid, "label": label,
                      "description": desc, "source": "wikidata_api", "query": query}
            if resp2:
                entities = resp2.json().get("entities", {})
                claims = entities.get(qid, {}).get("claims", {})
                for prop_id, prop_name in _WIKIDATA_PROPS.items():
                    if prop_id in claims:
                        claim_list = claims[prop_id]
                        values = []
                        for c in claim_list[:3]:
                            mv = c.get("mainsnak", {}).get("datavalue", {}).get("value", "")
                            if isinstance(mv, dict):
                                mv = mv.get("id", str(mv))
                            values.append(str(mv))
                        result[prop_name] = ", ".join(values) if len(values) > 1 else (values[0] if values else "")
            return result

        return self._cached_external_lookup(query.lower(), "wikidata_cache", 60, _fetch, _ALLOWED)

    # ------------------------------------------------------------------
    # Tool #16: lookup_country
    # ------------------------------------------------------------------

    def _lookup_country(self, inp):
        """Look up country data from restcountries.com. FREE, cached 90 days."""
        country = str(inp.get("country", "")).strip()
        if not country or len(country) < 2:
            return {"found": False, "error": "Country name too short"}

        _ALLOWED = {"found", "source", "query", "name", "official_name",
                     "cca2", "cca3", "region", "subregion", "currencies",
                     "languages", "borders"}

        def _fetch():
            resp = _safe_get(
                f"https://restcountries.com/v3.1/name/{requests.utils.quote(country)}",
                params={"fullText": "false",
                        "fields": "name,cca2,cca3,region,subregion,currencies,languages,borders"},
            )
            if not resp:
                return {"found": False, "query": country, "message": "Country not found"}
            data = resp.json()
            if not isinstance(data, list) or not data:
                return {"found": False, "query": country, "message": "Country not found"}
            c = data[0]
            name_data = c.get("name", {})
            currencies = c.get("currencies", {})
            currency_list = [f"{code} ({v.get('name', '')})" for code, v in currencies.items()] if isinstance(currencies, dict) else []
            languages = c.get("languages", {})
            lang_list = list(languages.values()) if isinstance(languages, dict) else []
            return {
                "found": True,
                "name": name_data.get("common", country),
                "official_name": name_data.get("official", ""),
                "cca2": c.get("cca2", ""),
                "cca3": c.get("cca3", ""),
                "region": c.get("region", ""),
                "subregion": c.get("subregion", ""),
                "currencies": ", ".join(currency_list),
                "languages": ", ".join(lang_list[:5]),
                "borders": c.get("borders", []),
                "source": "restcountries_api",
                "query": country,
            }

        return self._cached_external_lookup(country.lower(), "country_cache", 90, _fetch, _ALLOWED)

    # ------------------------------------------------------------------
    # Tool #17: convert_currency
    # ------------------------------------------------------------------

    def _convert_currency(self, inp):
        """Get exchange rates from open.er-api.com. FREE, cached 6 hours."""
        base = str(inp.get("from_currency", "USD")).strip().upper()
        target = str(inp.get("to_currency", "ILS")).strip().upper()
        _TOP_CURRENCIES = {"ILS", "EUR", "GBP", "JPY", "CNY", "CHF", "CAD", "AUD", "INR", "KRW", "TRY", "USD"}

        def _fetch():
            resp = _safe_get(f"https://open.er-api.com/v6/latest/{base}")
            if not resp:
                return {"found": False, "error": f"Exchange rate API failed for {base}"}
            data = resp.json()
            if data.get("result") != "success":
                return {"found": False, "error": "Exchange rate API returned error"}
            all_rates = data.get("rates", {})
            rates = {k: v for k, v in all_rates.items() if k in _TOP_CURRENCIES}
            return {
                "found": True,
                "base": base,
                "rates": rates,
                "target_rate": all_rates.get(target),
                "target": target,
                "last_update": data.get("time_last_update_utc", ""),
                "source": "open_er_api",
            }

        # TTL 0.25 days = 6 hours
        return self._cached_external_lookup(f"{base}_{target}", "currency_rates", 0.25, _fetch)

    # ------------------------------------------------------------------
    # Tool #18: search_comtrade
    # ------------------------------------------------------------------

    def _search_comtrade(self, inp):
        """Search UN Comtrade for global trade data. FREE, cached 30 days.
        Only available in overnight mode (too slow for real-time)."""
        if not self._overnight_mode:
            return {"available": False, "message": "Comtrade search available in overnight mode only"}

        hs_code = str(inp.get("hs_code", "")).replace(".", "").replace("/", "").replace(" ", "").strip()
        reporter = str(inp.get("reporter", "376")).strip()  # 376 = Israel
        period = str(inp.get("period", "2024")).strip()
        if not hs_code or len(hs_code) < 4:
            return {"found": False, "error": "HS code too short (need at least 4 digits)"}
        cmd_code = hs_code[:6]  # Comtrade uses 6-digit HS

        def _fetch():
            resp = _safe_get(
                "https://comtradeapi.un.org/data/v1/get/C/A/HS",
                params={"reporterCode": reporter, "period": period,
                        "cmdCode": cmd_code, "flowCode": "M"},
                timeout=30,
            )
            if not resp:
                return {"found": False, "query": cmd_code, "error": "Comtrade API failed"}
            data = resp.json()
            records = data.get("data", [])
            if not records:
                return {"found": False, "query": cmd_code, "message": "No Comtrade data found"}
            items = []
            for r in records[:5]:
                items.append({
                    "period": r.get("period", ""),
                    "cmdCode": r.get("cmdCode", ""),
                    "flowCode": r.get("flowCode", ""),
                    "partner": r.get("partnerDesc", ""),
                    "cifvalue": r.get("primaryValue", 0),
                    "quantity": r.get("qty", 0),
                    "netWgt": r.get("netWgt", 0),
                })
            return {
                "found": True,
                "cmd_code": cmd_code,
                "reporter": reporter,
                "period": period,
                "records_count": len(records),
                "items": items,
                "source": "comtrade_api",
                "query": cmd_code,
            }

        return self._cached_external_lookup(f"{reporter}_{period}_{cmd_code}", "comtrade_cache", 30, _fetch)

    # ------------------------------------------------------------------
    # Tool #19: lookup_food_product
    # ------------------------------------------------------------------

    def _lookup_food_product(self, inp):
        """Search Open Food Facts for product data. FREE, cached 30 days."""
        query = str(inp.get("query", "")).strip()
        if not query or len(query) < 2:
            return {"found": False, "error": "Query too short"}

        _ALLOWED = {"found", "source", "query", "product_name", "brands",
                     "categories", "ingredients_text", "nutrition_grades",
                     "labels", "origins", "countries", "quantity"}

        def _fetch():
            resp = _safe_get(
                "https://world.openfoodfacts.org/cgi/search.pl",
                params={"search_terms": query, "search_simple": "1",
                        "action": "process", "json": "1", "page_size": "3"},
            )
            if not resp:
                return {"found": False, "query": query, "error": "Open Food Facts API failed"}
            data = resp.json()
            products = data.get("products", [])
            if not products:
                return {"found": False, "query": query, "message": "No food product found"}
            p = products[0]
            return {
                "found": True,
                "product_name": p.get("product_name", ""),
                "brands": p.get("brands", ""),
                "categories": p.get("categories", ""),
                "ingredients_text": p.get("ingredients_text", ""),
                "nutrition_grades": p.get("nutrition_grades", ""),
                "labels": p.get("labels", ""),
                "origins": p.get("origins", ""),
                "countries": p.get("countries", ""),
                "quantity": p.get("quantity", ""),
                "source": "openfoodfacts_api",
                "query": query,
            }

        return self._cached_external_lookup(query.lower(), "food_products_cache", 30, _fetch, _ALLOWED)

    # ------------------------------------------------------------------
    # Tool #20: check_fda_product
    # ------------------------------------------------------------------

    def _check_fda_product(self, inp):
        """Search FDA drug/device database. FREE, cached 30 days."""
        query = str(inp.get("query", "")).strip()
        if not query or len(query) < 2:
            return {"found": False, "error": "Query too short"}

        _ALLOWED = {"found", "source", "query", "brand_name", "generic_name",
                     "product_type", "route", "dosage_form", "active_ingredients",
                     "indications_and_usage", "manufacturer_name", "product_code"}

        def _fetch():
            # Try drug labels first
            resp = _safe_get(
                "https://api.fda.gov/drug/label.json",
                params={"search": query, "limit": "3"},
            )
            if resp:
                data = resp.json()
                results = data.get("results", [])
                if results:
                    r = results[0]
                    openfda = r.get("openfda", {})
                    # Parse active ingredients
                    active = r.get("active_ingredient", [])
                    if isinstance(active, list):
                        ingredients_str = ", ".join(
                            i.get("name", "") if isinstance(i, dict) else str(i)
                            for i in active[:5]
                        )
                    else:
                        ingredients_str = ", ".join(openfda.get("substance_name", [])[:5])
                    # Parse indications
                    indications = r.get("indications_and_usage", [""])
                    indications_str = indications[0] if isinstance(indications, list) and indications else str(indications)
                    return {
                        "found": True,
                        "product_type": "drug",
                        "brand_name": ", ".join(openfda.get("brand_name", [])[:3]),
                        "generic_name": ", ".join(openfda.get("generic_name", [])[:3]),
                        "route": ", ".join(openfda.get("route", [])[:3]),
                        "dosage_form": ", ".join(openfda.get("dosage_form", [])[:3]),
                        "manufacturer_name": ", ".join(openfda.get("manufacturer_name", [])[:3]),
                        "active_ingredients": ingredients_str,
                        "indications_and_usage": indications_str,
                        "source": "fda_api",
                        "query": query,
                    }

            # Fallback: try device endpoint
            resp2 = _safe_get(
                "https://api.fda.gov/device/510k.json",
                params={"search": query, "limit": "3"},
            )
            if resp2:
                data = resp2.json()
                results = data.get("results", [])
                if results:
                    r = results[0]
                    return {
                        "found": True,
                        "product_type": "device",
                        "brand_name": r.get("device_name", ""),
                        "generic_name": r.get("generic_name", ""),
                        "manufacturer_name": r.get("applicant", ""),
                        "product_code": r.get("product_code", ""),
                        "source": "fda_api",
                        "query": query,
                    }

            return {"found": False, "query": query, "message": "No FDA product found"}

        return self._cached_external_lookup(query.lower(), "fda_products_cache", 30, _fetch, _ALLOWED)

    def _stub_not_available(self, inp):
        """Stub for tools whose data sources are not yet loaded."""
        return {"available": False, "message": "Data source not yet loaded"}
