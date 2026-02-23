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
    # Batch 2 (Tools #21-32)
    "boi.org.il",
    "edge.boi.org.il",
    "pubchem.ncbi.nlm.nih.gov",
    "ec.europa.eu",
    "dataweb.usitc.gov",
    "api.cbs.gov.il",
    "cbs.gov.il",
    "world.openbeautyfacts.org",
    "openbeautyfacts.org",
    "gepir.gs1.org",
    "wcoomd.org",
    "www.wcoomd.org",
    "unctadstat.unctad.org",
    "api.crossref.org",
    "api.opensanctions.org",
    "gov.il",
    "www.gov.il",
    "taxes.gov.il",
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
            # Batch 2 (Tools #21-32)
            "bank_of_israel_rates": self._bank_of_israel_rates,
            "search_pubchem": self._search_pubchem,
            "lookup_eu_taric": self._lookup_eu_taric,
            "lookup_usitc": self._lookup_usitc,
            "israel_cbs_trade": self._israel_cbs_trade,
            "lookup_gs1_barcode": self._lookup_gs1_barcode,
            "search_wco_notes": self._search_wco_notes,
            "lookup_unctad_gsp": self._lookup_unctad_gsp,
            "search_open_beauty": self._search_open_beauty,
            "crossref_technical": self._crossref_technical,
            "check_opensanctions": self._check_opensanctions,
            "get_israel_vat_rates": self._get_israel_vat_rates,
            "fetch_seller_website": self._fetch_seller_website,
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
        if not result or not result.get("candidates"):
            return {
                "candidates": [], "regulatory": [], "fta": None, "context_text": "",
                "found": False,
                "suggestion": "No tariff matches found. Try broader search terms, use get_chapter_notes for chapter-level search, or search_wco_notes for WCO explanatory notes.",
            }
        return result

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
        # Session 47: Also try with Luhn check digit appended (doc IDs are hs10_checkdigit)
        if len(hs_10) == 10 and hs_10.isdigit():
            try:
                from lib.librarian import _hs_check_digit
                check = _hs_check_digit(hs_10)
                candidates.append(f"{hs_10}_{check}")
            except Exception:
                pass

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
        if not result.get("eligible"):
            result["suggestion"] = "No FTA found. Try lookup_framework_order with the country name for legal clause details, or lookup_unctad_gsp to check GSP preferential status."
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
            return {
                "found": False, "chapter": chapter,
                "message": f"Chapter {chapter} not found",
                "suggestion": "Try lookup_tariff_structure to find the correct section/chapter, or search_wco_notes for WCO explanatory notes on this chapter.",
            }
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
                    "message": "No matching classification directive found",
                    "suggestion": "Try searching by chapter number instead of HS code, or use search_legal_knowledge for broader legal context."}

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
        """Search legal knowledge: 311 Customs Ordinance articles (in-memory),
        Firestore chapter summaries, customs agents law, EU/US standards reforms.
        Uses word-boundary regex for English keywords to prevent false positives."""
        query = str(inp.get("query", "")).strip()
        if not query:
            return {"found": False, "error": "No query provided"}

        # Lazy import — in-memory, no Firestore cost
        try:
            from lib.customs_law import CUSTOMS_ORDINANCE_ARTICLES, CUSTOMS_ORDINANCE_CHAPTERS
            _ord_available = True
        except ImportError:
            _ord_available = False

        all_docs = self._get_legal_knowledge()

        try:
            # ── Case A: Article number lookup (סעיף 130, article 133א, §62, bare "130") ──
            if _ord_available:
                art_match = re.search(
                    r'(?:article|section|סעיף|§)\s*(\d{1,3}[א-ת]*)'
                    r'|^(\d{1,3}[א-ת]*)$',
                    query, re.IGNORECASE,
                )
                if art_match:
                    art_id = (art_match.group(1) or art_match.group(2) or "").strip()
                    # Bare digit 1-15 without prefix → fall through to chapter lookup (Case 1)
                    if not (art_id.isdigit() and 1 <= int(art_id) <= 15
                            and not re.search(r'(?:article|section|סעיף|§)', query, re.IGNORECASE)):
                        art = CUSTOMS_ORDINANCE_ARTICLES.get(art_id, {})
                        if art:
                            result = {
                                "found": True, "type": "ordinance_article",
                                "article_id": art_id,
                                "chapter": art.get("ch", ""),
                                "title_he": art.get("t", ""),
                                "summary_en": art.get("s", ""),
                            }
                            if art.get("definitions"):
                                result["definitions"] = dict(list(art["definitions"].items())[:15])
                            if art.get("methods"):
                                result["methods"] = art["methods"]
                            if art.get("additions"):
                                result["additions"] = art["additions"]
                            if art.get("key"):
                                result["key"] = art["key"]
                            if art.get("critical_rule"):
                                result["critical_rule"] = art["critical_rule"]
                            if art.get("repealed"):
                                result["repealed"] = True
                            return result

            # ── Case B: Chapter-scoped article list (פרק 8, "articles in chapter 4") ──
            if _ord_available:
                ch_match = re.search(
                    r'(?:articles?\s+(?:in|of|from)\s+chapter|פרק)\s*(\d{1,2})',
                    query, re.IGNORECASE,
                )
                if ch_match:
                    ch_num = int(ch_match.group(1))
                    ch_key = ch_num if ch_num in CUSTOMS_ORDINANCE_CHAPTERS else str(ch_num)
                    ch_meta = CUSTOMS_ORDINANCE_CHAPTERS.get(ch_key, {})
                    articles = [
                        {"id": k, "title_he": v.get("t", ""), "summary_en": v.get("s", "")}
                        for k, v in CUSTOMS_ORDINANCE_ARTICLES.items()
                        if v.get("ch") == ch_num
                    ]
                    if articles:
                        return {
                            "found": True, "type": "ordinance_chapter_articles",
                            "chapter": ch_num,
                            "title_he": ch_meta.get("title_he", ""),
                            "title_en": ch_meta.get("title_en", ""),
                            "articles_range": ch_meta.get("articles_range", ""),
                            "count": len(articles),
                            "articles": articles[:30],
                        }

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

            # ── Case C: Keyword search across all 311 ordinance articles ──
            if _ord_available:
                query_words = [w for w in re.split(r'[\s,;:?.!]+', query.lower()) if len(w) >= 3]
                if query_words:
                    scored = []
                    for art_id, art in CUSTOMS_ORDINANCE_ARTICLES.items():
                        searchable = f"{art.get('t', '')} {art.get('s', '')}".lower()
                        hits = sum(1 for w in query_words if w in searchable)
                        if hits >= 2:
                            scored.append((hits, art_id, art))
                    scored.sort(key=lambda x: -x[0])
                    ord_matches = [
                        {"article_id": aid, "chapter": a.get("ch", ""),
                         "title_he": a.get("t", ""), "summary_en": a.get("s", "")}
                        for _, aid, a in scored[:15]
                    ]
                if ord_matches:
                    return {
                        "found": True, "type": "ordinance_article_search",
                        "query": query,
                        "count": len(ord_matches),
                        "articles": ord_matches[:15],
                    }

            # Case 5: General keyword search across cached Firestore docs
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

        return self._cached_external_lookup(f"{reporter}_{period}_{cmd_code}", "comtrade_cache", 7, _fetch)

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

    # ------------------------------------------------------------------
    # Tool #21: bank_of_israel_rates
    # ------------------------------------------------------------------

    def _bank_of_israel_rates(self, inp):
        """Get official Bank of Israel exchange rates. FREE, cached 6 hours.
        Israeli customs law requires BOI official rates for valuation."""
        currency = str(inp.get("currency", "USD")).strip().upper()

        _ALLOWED = {"found", "source", "query", "currency", "rate",
                     "change", "lastUpdate"}

        def _fetch():
            # Try SDMX endpoint first (structured data)
            series_map = {
                "USD": "RER_USD_ILS", "EUR": "RER_EUR_ILS",
                "GBP": "RER_GBP_ILS", "CNY": "RER_CNY_ILS",
                "JPY": "RER_JPY_ILS",
            }
            series = series_map.get(currency)
            if series:
                resp = _safe_get(
                    f"https://edge.boi.org.il/FusionEdgeServer/sdmx/v2/data/dataflow/"
                    f"BOI.STATISTICS/EXR/1.0/{series}",
                    headers={"Accept": "application/json"},
                    timeout=15,
                )
                if resp:
                    try:
                        data = resp.json()
                        ds = data.get("dataSets", [{}])[0]
                        series_data = ds.get("series", {})
                        for key, val in series_data.items():
                            obs = val.get("observations", {})
                            if obs:
                                last_key = max(obs.keys())
                                rate_val = obs[last_key][0] if obs[last_key] else None
                                if rate_val:
                                    return {
                                        "found": True,
                                        "currency": currency,
                                        "rate": rate_val,
                                        "lastUpdate": data.get("meta", {}).get("prepared", ""),
                                        "source": "boi_sdmx",
                                    }
                    except (KeyError, IndexError, ValueError):
                        pass

            # Fallback: PublicApi endpoint
            resp2 = _safe_get(
                "https://boi.org.il/PublicApi/GetExchangeRates",
                timeout=15,
            )
            if resp2:
                try:
                    rates = resp2.json()
                    if isinstance(rates, list):
                        for r in rates:
                            if r.get("key", "").upper() == currency:
                                return {
                                    "found": True,
                                    "currency": currency,
                                    "rate": r.get("currentExchangeRate", 0),
                                    "change": r.get("currentChange", 0),
                                    "lastUpdate": r.get("lastUpdate", ""),
                                    "source": "boi_public_api",
                                }
                except (ValueError, KeyError):
                    pass

            return {"found": False, "currency": currency, "message": "BOI rate unavailable"}

        return self._cached_external_lookup(
            f"boi_{currency}", "boi_rates", 0.25, _fetch, _ALLOWED
        )

    # ------------------------------------------------------------------
    # Tool #22: search_pubchem
    # ------------------------------------------------------------------

    def _search_pubchem(self, inp):
        """Search PubChem for chemical compound data. FREE, cached 90 days.
        Returns IUPAC name, formula, weight, CAS number, hazard class."""
        query = str(inp.get("query", "")).strip()
        if not query or len(query) < 2:
            return {"found": False, "error": "Query too short"}

        _ALLOWED = {"found", "source", "query", "IUPACName", "MolecularFormula",
                     "MolecularWeight", "CID", "CASNumber", "HazardClass"}

        def _fetch():
            resp = _safe_get(
                f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
                f"{requests.utils.quote(query)}/JSON",
                timeout=15,
            )
            if not resp:
                return {"found": False, "query": query, "message": "PubChem lookup failed"}
            try:
                data = resp.json()
                compounds = data.get("PC_Compounds", [])
                if not compounds:
                    return {"found": False, "query": query, "message": "No compound found"}
                c = compounds[0]
                cid = c.get("id", {}).get("id", {}).get("cid", "")
                props = c.get("props", [])
                result = {"found": True, "CID": cid, "source": "pubchem_api", "query": query}
                for p in props:
                    urn = p.get("urn", {})
                    label = urn.get("label", "")
                    val = p.get("value", {})
                    sval = val.get("sval", "") or str(val.get("fval", ""))
                    if label == "IUPAC Name" and urn.get("name") == "Preferred":
                        result["IUPACName"] = sval
                    elif label == "Molecular Formula":
                        result["MolecularFormula"] = sval
                    elif label == "Molecular Weight":
                        result["MolecularWeight"] = sval
                return result
            except (ValueError, KeyError):
                return {"found": False, "query": query, "message": "PubChem parse error"}

        return self._cached_external_lookup(query.lower(), "pubchem_cache", 90, _fetch, _ALLOWED)

    # ------------------------------------------------------------------
    # Tool #23: lookup_eu_taric
    # ------------------------------------------------------------------

    def _lookup_eu_taric(self, inp):
        """Look up EU TARIC data for cross-reference validation. FREE, cached 30 days.
        Input: 6-digit HS code. Returns commodity description + duty rate."""
        hs_code = str(inp.get("hs_code", "")).replace(".", "").replace("/", "").replace(" ", "").strip()
        if not hs_code or len(hs_code) < 6:
            return {"found": False, "error": "Need at least 6-digit HS code"}
        hs6 = hs_code[:6]

        _ALLOWED = {"found", "source", "query", "commodityCode", "description",
                     "dutyRate", "measures"}

        def _fetch():
            resp = _safe_get(
                "https://ec.europa.eu/taxation_customs/dds2/taric/taric_consultation.jsp",
                params={"Lang": "en", "Taric": hs6, "LangDescr": "en"},
                timeout=20,
            )
            if not resp:
                return {"found": False, "query": hs6, "message": "EU TARIC unavailable"}
            text = resp.text[:5000]
            # Parse basic info from HTML response
            desc = ""
            duty = ""
            import re as _re
            desc_match = _re.search(r'class="td_desc[^"]*"[^>]*>([^<]+)', text)
            if desc_match:
                desc = desc_match.group(1).strip()
            duty_match = _re.search(r'(\d+(?:\.\d+)?)\s*%', text)
            if duty_match:
                duty = duty_match.group(0)
            if desc or duty:
                return {
                    "found": True,
                    "commodityCode": hs6,
                    "description": sanitize_external_text(desc, max_length=500),
                    "dutyRate": duty,
                    "source": "eu_taric",
                    "query": hs6,
                }
            return {"found": False, "query": hs6, "message": "No TARIC data parsed"}

        return self._cached_external_lookup(f"taric_{hs6}", "eu_taric_cache", 30, _fetch, _ALLOWED)

    # ------------------------------------------------------------------
    # Tool #24: lookup_usitc
    # ------------------------------------------------------------------

    def _lookup_usitc(self, inp):
        """Look up US HTS data for cross-reference validation. FREE, cached 30 days.
        Input: 6-digit HS code. Returns HTS number + description + duty rate."""
        hs_code = str(inp.get("hs_code", "")).replace(".", "").replace("/", "").replace(" ", "").strip()
        if not hs_code or len(hs_code) < 6:
            return {"found": False, "error": "Need at least 6-digit HS code"}
        hs6 = hs_code[:6]

        _ALLOWED = {"found", "source", "query", "htsno", "description",
                     "general", "special"}

        def _fetch():
            resp = _safe_get(
                f"https://dataweb.usitc.gov/api/tariff-schedule",
                params={"hts": hs6},
                timeout=15,
            )
            if not resp:
                return {"found": False, "query": hs6, "message": "USITC API unavailable"}
            try:
                data = resp.json()
                records = data if isinstance(data, list) else data.get("data", [])
                if not records:
                    return {"found": False, "query": hs6, "message": "No US HTS data found"}
                r = records[0] if isinstance(records, list) else records
                return {
                    "found": True,
                    "htsno": str(r.get("htsno", hs6)),
                    "description": sanitize_external_text(
                        str(r.get("description", "")), max_length=400
                    ),
                    "general": str(r.get("general", "")),
                    "special": str(r.get("special", "")),
                    "source": "usitc_api",
                    "query": hs6,
                }
            except (ValueError, KeyError):
                return {"found": False, "query": hs6, "message": "USITC parse error"}

        return self._cached_external_lookup(f"usitc_{hs6}", "usitc_cache", 30, _fetch, _ALLOWED)

    # ------------------------------------------------------------------
    # Tool #25: israel_cbs_trade
    # ------------------------------------------------------------------

    def _israel_cbs_trade(self, inp):
        """Query Israeli CBS trade statistics. FREE, cached 30 days.
        OVERNIGHT ONLY — too slow for real-time."""
        if not self._overnight_mode:
            return {"available": False, "message": "CBS trade data available in overnight mode only"}

        hs_code = str(inp.get("hs_code", "")).replace(".", "").replace("/", "").replace(" ", "").strip()
        if not hs_code or len(hs_code) < 4:
            return {"found": False, "error": "HS code too short"}

        _ALLOWED = {"found", "source", "query", "code", "description",
                     "importValue", "importVolume", "topOrigins", "year"}

        def _fetch():
            resp = _safe_get(
                "https://api.cbs.gov.il/Index/GetCategoriesNodes",
                params={"code": hs_code[:8]},
                timeout=20,
            )
            if not resp:
                return {"found": False, "query": hs_code, "message": "CBS API unavailable"}
            try:
                data = resp.json()
                if not data:
                    return {"found": False, "query": hs_code, "message": "No CBS data"}
                node = data[0] if isinstance(data, list) else data
                return {
                    "found": True,
                    "code": str(node.get("code", hs_code)),
                    "description": sanitize_external_text(
                        str(node.get("name", "")), max_length=300
                    ),
                    "importValue": node.get("importValue", 0),
                    "importVolume": node.get("importVolume", 0),
                    "topOrigins": node.get("topOrigins", []),
                    "year": node.get("year", ""),
                    "source": "cbs_api",
                    "query": hs_code,
                }
            except (ValueError, KeyError):
                return {"found": False, "query": hs_code, "message": "CBS parse error"}

        return self._cached_external_lookup(f"cbs_{hs_code}", "cbs_trade_cache", 30, _fetch, _ALLOWED)

    # ------------------------------------------------------------------
    # Tool #26: lookup_gs1_barcode
    # ------------------------------------------------------------------

    def _lookup_gs1_barcode(self, inp):
        """Look up product by EAN/UPC barcode. FREE, cached 60 days.
        Only call if barcode found in documents."""
        barcode = str(inp.get("barcode", "")).strip()
        if not barcode or len(barcode) < 8:
            return {"found": False, "error": "Invalid barcode (need 8+ digits)"}

        _ALLOWED = {"found", "source", "query", "product_name", "brands",
                     "categories", "countries_tags", "quantity"}

        def _fetch():
            resp = _safe_get(
                f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json",
                timeout=10,
            )
            if not resp:
                return {"found": False, "query": barcode, "message": "Barcode lookup failed"}
            try:
                data = resp.json()
                product = data.get("product", {})
                if not product or data.get("status") == 0:
                    return {"found": False, "query": barcode, "message": "Barcode not found"}
                return {
                    "found": True,
                    "product_name": sanitize_external_text(
                        product.get("product_name", ""), max_length=200
                    ),
                    "brands": sanitize_external_text(
                        product.get("brands", ""), max_length=200
                    ),
                    "categories": sanitize_external_text(
                        product.get("categories", ""), max_length=300
                    ),
                    "countries_tags": product.get("countries_tags", [])[:10],
                    "quantity": product.get("quantity", ""),
                    "source": "openfoodfacts_barcode",
                    "query": barcode,
                }
            except (ValueError, KeyError):
                return {"found": False, "query": barcode, "message": "Barcode parse error"}

        return self._cached_external_lookup(f"barcode_{barcode}", "barcode_cache", 60, _fetch, _ALLOWED)

    # ------------------------------------------------------------------
    # Tool #27: search_wco_notes
    # ------------------------------------------------------------------

    def _search_wco_notes(self, inp):
        """Fetch WCO explanatory notes for an HS chapter. FREE, cached 180 days.
        Gold standard for classification — feeds elimination engine + Agent 2."""
        chapter = str(inp.get("chapter", "")).strip().zfill(2)
        if not chapter or not chapter.isdigit() or int(chapter) < 1 or int(chapter) > 99:
            return {"found": False, "error": "Invalid chapter number (1-99)"}

        _ALLOWED = {"found", "source", "query", "chapter", "title",
                     "notes_text", "section"}

        def _fetch():
            resp = _safe_get(
                f"https://www.wcoomd.org/en/topics/nomenclature/instrument-and-tools/"
                f"hs-nomenclature-2022-edition/chapter-{chapter}.aspx",
                timeout=20,
            )
            if not resp:
                return {"found": False, "query": chapter, "message": "WCO notes unavailable"}
            text = resp.text[:10000]
            # Extract content from HTML
            import re as _re
            # Try to find main content area
            content_match = _re.search(
                r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
                text, _re.DOTALL | _re.IGNORECASE
            )
            notes_text = ""
            if content_match:
                raw = content_match.group(1)
                notes_text = _re.sub(r'<[^>]+>', ' ', raw).strip()
            else:
                # Fallback: strip all tags
                notes_text = _re.sub(r'<[^>]+>', ' ', text).strip()
            notes_text = _re.sub(r'\s+', ' ', notes_text)
            if len(notes_text) < 50:
                return {"found": False, "query": chapter, "message": "No WCO notes parsed"}
            return {
                "found": True,
                "chapter": chapter,
                "notes_text": sanitize_external_text(notes_text, max_length=800),
                "source": "wco_website",
                "query": chapter,
            }

        return self._cached_external_lookup(
            f"wco_ch_{chapter}", "wco_notes_cache", 180, _fetch, _ALLOWED
        )

    # ------------------------------------------------------------------
    # Tool #28: lookup_unctad_gsp
    # ------------------------------------------------------------------

    def _lookup_unctad_gsp(self, inp):
        """Look up country GSP/development status from UNCTAD. FREE, cached 90 days.
        Used to determine preferential duty eligibility."""
        country_code = str(inp.get("country_code", "")).strip().upper()
        if not country_code or len(country_code) != 2:
            return {"found": False, "error": "Need ISO 2-letter country code"}

        _ALLOWED = {"found", "source", "query", "countryCode", "countryName",
                     "gspStatus", "ldcStatus", "developmentStatus", "region"}

        def _fetch():
            resp = _safe_get(
                "https://unctadstat.unctad.org/api/",
                params={"country": country_code},
                timeout=15,
            )
            if not resp:
                return {"found": False, "query": country_code, "message": "UNCTAD API unavailable"}
            try:
                data = resp.json()
                if not data:
                    return {"found": False, "query": country_code, "message": "No UNCTAD data"}
                node = data[0] if isinstance(data, list) else data
                return {
                    "found": True,
                    "countryCode": country_code,
                    "countryName": sanitize_external_text(
                        str(node.get("countryName", "")), max_length=100
                    ),
                    "gspStatus": str(node.get("gspStatus", "")),
                    "ldcStatus": str(node.get("ldcStatus", "")),
                    "developmentStatus": str(node.get("developmentStatus", "")),
                    "region": str(node.get("region", "")),
                    "source": "unctad_api",
                    "query": country_code,
                }
            except (ValueError, KeyError):
                return {"found": False, "query": country_code, "message": "UNCTAD parse error"}

        return self._cached_external_lookup(
            f"unctad_{country_code}", "unctad_country_cache", 90, _fetch, _ALLOWED
        )

    # ------------------------------------------------------------------
    # Tool #29: search_open_beauty
    # ------------------------------------------------------------------

    def _search_open_beauty(self, inp):
        """Search Open Beauty Facts for cosmetics product data. FREE, cached 30 days.
        Use for HS chapter 33 — ingredients determine correct sub-heading."""
        query = str(inp.get("query", "")).strip()
        barcode = str(inp.get("barcode", "")).strip()
        if not query and not barcode:
            return {"found": False, "error": "Need query or barcode"}

        _ALLOWED = {"found", "source", "query", "product_name", "categories",
                     "ingredients_text", "brands", "countries"}

        def _fetch():
            if barcode and len(barcode) >= 8:
                resp = _safe_get(
                    f"https://world.openbeautyfacts.org/api/v2/product/{barcode}",
                    timeout=10,
                )
            else:
                resp = _safe_get(
                    "https://world.openbeautyfacts.org/cgi/search.pl",
                    params={"search_terms": query, "json": "1", "page_size": "3"},
                    timeout=10,
                )
            if not resp:
                return {"found": False, "query": query or barcode, "message": "Open Beauty Facts unavailable"}
            try:
                data = resp.json()
                product = data.get("product")
                if not product:
                    products = data.get("products", [])
                    if not products:
                        return {"found": False, "query": query or barcode, "message": "No beauty product found"}
                    product = products[0]
                return {
                    "found": True,
                    "product_name": sanitize_external_text(
                        product.get("product_name", ""), max_length=200
                    ),
                    "categories": sanitize_external_text(
                        product.get("categories", ""), max_length=300
                    ),
                    "ingredients_text": sanitize_external_text(
                        product.get("ingredients_text", ""), max_length=600
                    ),
                    "brands": sanitize_external_text(
                        product.get("brands", ""), max_length=200
                    ),
                    "countries": product.get("countries", ""),
                    "source": "openbeautyfacts_api",
                    "query": query or barcode,
                }
            except (ValueError, KeyError):
                return {"found": False, "query": query or barcode, "message": "Beauty facts parse error"}

        return self._cached_external_lookup(
            (query or barcode).lower(), "beauty_products_cache", 30, _fetch, _ALLOWED
        )

    # ------------------------------------------------------------------
    # Tool #30: crossref_technical
    # ------------------------------------------------------------------

    def _crossref_technical(self, inp):
        """Search CrossRef for academic papers about a product. FREE, cached 90 days.
        OVERNIGHT ONLY — builds knowledge for rare/technical imports."""
        if not self._overnight_mode:
            return {"available": False, "message": "CrossRef search available in overnight mode only"}

        query = str(inp.get("query", "")).strip()
        if not query or len(query) < 3:
            return {"found": False, "error": "Query too short"}

        _ALLOWED = {"found", "source", "query", "title", "abstract",
                     "subject", "type"}

        def _fetch():
            resp = _safe_get(
                "https://api.crossref.org/works",
                params={"query": query, "filter": "type:journal-article", "rows": "2"},
                headers={
                    "User-Agent": "RCB-RPA-PORT/1.0 (mailto:rcb@rpa-port.co.il)"
                },
                timeout=20,
            )
            if not resp:
                return {"found": False, "query": query, "message": "CrossRef API unavailable"}
            try:
                data = resp.json()
                items = data.get("message", {}).get("items", [])
                if not items:
                    return {"found": False, "query": query, "message": "No articles found"}
                results = []
                for item in items[:2]:
                    title_list = item.get("title", [])
                    title = title_list[0] if title_list else ""
                    abstract = item.get("abstract", "")
                    results.append({
                        "title": sanitize_external_text(title, max_length=200),
                        "abstract": sanitize_external_text(abstract, max_length=400),
                        "subject": item.get("subject", [])[:5],
                        "type": item.get("type", ""),
                    })
                return {
                    "found": True,
                    "articles": results,
                    "source": "crossref_api",
                    "query": query,
                }
            except (ValueError, KeyError):
                return {"found": False, "query": query, "message": "CrossRef parse error"}

        return self._cached_external_lookup(query.lower(), "crossref_cache", 90, _fetch, _ALLOWED)

    # ------------------------------------------------------------------
    # Tool #31: check_opensanctions
    # ------------------------------------------------------------------

    def _check_opensanctions(self, inp):
        """Screen entity against OpenSanctions. FREE tier (10k/month), cached 24 hours.
        IMPORTANT: Run on shipper + consignee names for every shipment.
        Compliance requirement — flag only, never block."""
        query = str(inp.get("query", "")).strip()
        if not query or len(query) < 2:
            return {"found": False, "error": "Entity name too short"}

        _ALLOWED = {"found", "source", "query", "hit", "results",
                     "id", "caption", "schema", "score", "datasets", "properties"}

        def _fetch():
            all_hits = []
            any_response = False
            for schema_type in ("Company", "Person"):
                resp = _safe_get(
                    f"https://api.opensanctions.org/search/{requests.utils.quote(query)}",
                    params={"schema": schema_type},
                    timeout=15,
                )
                if not resp:
                    continue
                any_response = True
                try:
                    data = resp.json()
                    results = data.get("results", [])
                    for r in results[:5]:
                        score = r.get("score", 0)
                        if score >= 0.7:
                            all_hits.append({
                                "id": str(r.get("id", "")),
                                "caption": sanitize_external_text(
                                    str(r.get("caption", "")), max_length=200
                                ),
                                "schema": str(r.get("schema", "")),
                                "score": score,
                                "datasets": r.get("datasets", [])[:5],
                            })
                except (ValueError, KeyError):
                    continue
            if not any_response:
                return {"found": True, "hit": False, "query": query,
                        "message": "Sanctions API unavailable — manual check required",
                        "source": "opensanctions_api"}
            return {
                "found": True,
                "hit": len(all_hits) > 0,
                "results": all_hits,
                "source": "opensanctions_api",
                "query": query,
            }

        return self._cached_external_lookup(query.lower(), "sanctions_cache", 1, _fetch, _ALLOWED)

    # ------------------------------------------------------------------
    # Tool #32: get_israel_vat_rates
    # ------------------------------------------------------------------

    def _get_israel_vat_rates(self, inp):
        """Get Israeli purchase tax + VAT rates for an HS code. FREE, cached 7 days.
        Completes the customs cost picture: duty + purchase tax + VAT."""
        hs_code = str(inp.get("hs_code", "")).replace(".", "").replace("/", "").replace(" ", "").strip()
        if not hs_code or len(hs_code) < 4:
            return {"found": False, "error": "HS code too short"}

        _ALLOWED = {"found", "source", "query", "hsCode", "purchaseTaxRate",
                     "vatRate", "exemptions"}

        def _fetch():
            resp = _safe_get(
                "https://www.gov.il/api/DataGovProxy/GetDynamicDataByQuery",
                params={"hs_code": hs_code[:10]},
                timeout=15,
            )
            if not resp:
                # Fallback: return standard Israeli VAT (18%) with no purchase tax
                return {
                    "found": True,
                    "hsCode": hs_code,
                    "purchaseTaxRate": "",
                    "vatRate": "18%",
                    "exemptions": "",
                    "source": "default_israel_vat",
                    "query": hs_code,
                    "note": "Using standard 18% VAT — specific rate unavailable",
                }
            try:
                data = resp.json()
                records = data.get("data", data.get("results", []))
                if not records:
                    return {
                        "found": True,
                        "hsCode": hs_code,
                        "purchaseTaxRate": "",
                        "vatRate": "18%",
                        "exemptions": "",
                        "source": "default_israel_vat",
                        "query": hs_code,
                    }
                r = records[0] if isinstance(records, list) else records
                return {
                    "found": True,
                    "hsCode": hs_code,
                    "purchaseTaxRate": str(r.get("purchaseTaxRate", r.get("purchase_tax", ""))),
                    "vatRate": str(r.get("vatRate", r.get("vat", "18%"))),
                    "exemptions": sanitize_external_text(
                        str(r.get("exemptions", "")), max_length=300
                    ),
                    "source": "gov_il_api",
                    "query": hs_code,
                }
            except (ValueError, KeyError):
                return {
                    "found": True,
                    "hsCode": hs_code,
                    "purchaseTaxRate": "",
                    "vatRate": "18%",
                    "exemptions": "",
                    "source": "default_israel_vat",
                    "query": hs_code,
                }

        return self._cached_external_lookup(
            f"vat_{hs_code}", "israel_tax_cache", 7, _fetch, _ALLOWED
        )

    def _fetch_seller_website(self, inp):
        """Fetch seller website to confirm products they sell. FREE, cached 30 days.

        Session 47: Infers domain from seller name, fetches homepage,
        extracts product keywords via BeautifulSoup. Reuses _safe_get()
        and _cached_external_lookup() infrastructure.
        """
        seller_name = str(inp.get("seller_name", "")).strip()
        seller_domain = str(inp.get("seller_domain", "")).strip()
        product_hint = str(inp.get("product_hint", "")).strip()

        if not seller_name:
            return {"found": False, "error": "seller_name required"}

        # Infer domain if not provided
        if not seller_domain:
            seller_domain = self._infer_seller_domain(seller_name)

        if not seller_domain:
            return {
                "found": False,
                "seller_name": seller_name,
                "note": "Could not infer domain from seller name",
            }

        _ALLOWED = {"found", "seller_name", "domain", "products_mentioned",
                     "business_type", "raw_excerpt", "source", "note"}

        def _fetch():
            url = f"https://{seller_domain}"
            # Direct request — seller domains are dynamic, not in static allowlist
            try:
                resp = requests.get(url, timeout=10, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                })
                if resp.status_code != 200:
                    resp = None
            except Exception:
                resp = None
            if not resp:
                return {
                    "found": False,
                    "seller_name": seller_name,
                    "domain": seller_domain,
                    "note": "Website unreachable",
                    "source": "seller_website",
                }
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text[:100000], "html.parser")
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()
                page_text = soup.get_text(separator=" ", strip=True)[:5000]
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
            except Exception:
                page_text = resp.text[:5000]
                title = ""

            return {
                "found": True,
                "seller_name": seller_name,
                "domain": seller_domain,
                "products_mentioned": sanitize_external_text(page_text, max_length=1500),
                "business_type": sanitize_external_text(title, max_length=200),
                "raw_excerpt": sanitize_external_text(page_text[:500], max_length=500),
                "source": "seller_website",
            }

        return self._cached_external_lookup(
            f"seller_{seller_domain}", "web_search_cache", 30, _fetch, _ALLOWED
        )

    @staticmethod
    def _infer_seller_domain(seller_name):
        """Infer seller website domain from company name. Simple heuristic."""
        import re as _re
        name = seller_name.lower().strip()
        # Remove legal suffixes
        for suffix in ("ltd", "llc", "inc", "corp", "co.", "gmbh", "s.a.",
                       "b.v.", "s.r.l.", "sp. z o.o.", "jsc", "ojsc", "oao"):
            name = name.replace(suffix, "")
        # Keep only alphanumeric
        name = _re.sub(r"[^a-z0-9]", "", name).strip()
        if not name or len(name) < 3:
            return ""
        # Try common TLDs
        for tld in (".com", ".by", ".cn", ".de", ".co.uk", ".ru", ".fr",
                     ".it", ".es", ".nl", ".pl", ".kr", ".jp", ".in"):
            candidate = f"{name}{tld}"
            if len(candidate) > 6:
                return candidate
        return f"{name}.com"

