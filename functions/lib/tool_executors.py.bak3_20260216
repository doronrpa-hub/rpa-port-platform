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
from lib.classification_agents import run_document_agent


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
