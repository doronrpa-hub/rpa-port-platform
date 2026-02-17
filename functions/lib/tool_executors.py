"""
Tool Executors for RCB Tool-Calling Classification Engine
==========================================================
ToolExecutor class wraps existing module functions as tool handlers.
Each tool_name maps to a method that calls the real code.

No new logic — just routing + caching + error handling.
"""

import json
import time
import traceback

from lib.self_learning import SelfLearningEngine
from lib import intelligence
from lib import verification_loop
# NOTE: run_document_agent imported LAZILY inside _extract_invoice() to avoid circular import.
# classification_agents.py -> tool_calling_engine.py -> tool_executors.py -> classification_agents.py


# Dual-use HS chapters (require extra scrutiny)
_DUAL_USE_CHAPTERS = {"28", "29", "36", "84", "85", "87", "90", "93"}
# High-risk origins
_HIGH_RISK_ORIGINS = {"iran", "north korea", "syria", "cuba", "איראן", "צפון קוריאה", "סוריה", "קובה"}


class ToolExecutor:
    """Routes tool calls to existing module functions."""

    def __init__(self, db, api_key, gemini_key=None):
        self.db = db
        self.api_key = api_key
        self.gemini_key = gemini_key
        self._learning = SelfLearningEngine(db)
        # Caches to avoid duplicate API calls within one classification run
        self._fio_cache = {}       # hs_code -> free_import_order result
        self._ministry_cache = {}  # hs_code -> route_to_ministries result
        # Stats
        self._stats = {}

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
            "search_classification_directives": self._stub_not_available,
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

        # Ministry routing (cached per HS)
        if hs_code not in self._ministry_cache:
            self._ministry_cache[hs_code] = intelligence.route_to_ministries(self.db, hs_code, fio)
        ministry = self._ministry_cache[hs_code]

        return {
            "free_import_order": fio,
            "ministry_routing": ministry,
        }

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
        """Look up FTA clause from framework_order collection by country."""
        # Map common country names/codes to framework_order doc IDs
        _COUNTRY_MAP = {
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
        code = _COUNTRY_MAP.get(origin_country.lower())
        if not code:
            return None
        try:
            doc = self.db.collection("framework_order").document(f"fta_{code}").get()
            if doc.exists:
                data = doc.to_dict()
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
        except Exception:
            pass
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
        C5: Reads from framework_order collection seeded from knowledge doc + XML."""
        query = str(inp.get("query", "")).strip()
        if not query:
            return {"found": False, "error": "No query provided"}

        query_lower = query.lower()

        try:
            # Case 1: "definitions" — return all legal definitions
            if query_lower in ("definitions", "הגדרות", "all_definitions"):
                defs = []
                for doc in self.db.collection("framework_order").where("type", "==", "definition").stream():
                    data = doc.to_dict()
                    defs.append({
                        "term": data.get("term", ""),
                        "definition": data.get("definition", "")[:500],
                    })
                return {"found": bool(defs), "type": "definitions", "definitions": defs, "count": len(defs)}

            # Case 2: Specific definition term lookup
            if query_lower.startswith("def:") or query_lower.startswith("define:"):
                term = query.split(":", 1)[1].strip()
                # Search definitions for matching term
                matches = []
                for doc in self.db.collection("framework_order").where("type", "==", "definition").stream():
                    data = doc.to_dict()
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
                    # Return all FTA clauses
                    clauses = []
                    for doc in self.db.collection("framework_order").where("type", "==", "fta_clause").stream():
                        data = doc.to_dict()
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
                    # Single country FTA
                    fw_fta = self._lookup_fw_fta_clause(country)
                    if fw_fta:
                        return {"found": True, "type": "fta_clause", **fw_fta}
                    return {"found": False, "type": "fta_clause", "query": country,
                            "message": f"No FTA clause found for '{country}'"}

            # Case 4: "classification_rules" or "rules"
            if query_lower in ("classification_rules", "rules", "סיווג"):
                rules = []
                for doc in self.db.collection("framework_order").where("type", "==", "classification_rule").stream():
                    data = doc.to_dict()
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
                doc = self.db.collection("framework_order").document(f"addition_{add_match}").get()
                if doc.exists:
                    data = doc.to_dict()
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

            # Case 6: General text search across all framework_order docs
            matches = []
            for doc in self.db.collection("framework_order").stream():
                if doc.id.startswith("_"):
                    continue
                data = doc.to_dict()
                searchable = " ".join([
                    str(data.get("term", "")),
                    str(data.get("title", "")),
                    str(data.get("definition", "")),
                    str(data.get("country_en", "")),
                    str(data.get("country_he", "")),
                ]).lower()
                if query_lower in searchable:
                    matches.append({
                        "doc_id": doc.id,
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

    def _stub_not_available(self, inp):
        """Stub for tools whose data sources are not yet loaded."""
        return {"available": False, "message": "Data source not yet loaded"}
