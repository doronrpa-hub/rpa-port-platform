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
        Caches both to avoid repeat API calls for same HS code."""
        hs_code = inp.get("hs_code", "")

        # Free Import Order (cached per HS)
        if hs_code not in self._fio_cache:
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

    def _lookup_fta(self, inp):
        """Wraps intelligence.lookup_fta()."""
        return intelligence.lookup_fta(
            self.db,
            inp.get("hs_code", ""),
            inp.get("origin_country", ""),
        )

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
                    "notes": data.get("notes", []),
                    "exclusions": data.get("exclusions", []),
                    "inclusions": data.get("inclusions", []),
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

    def _stub_not_available(self, inp):
        """Stub for tools whose data sources are not yet loaded."""
        return {"available": False, "message": "Data source not yet loaded"}
