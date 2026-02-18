"""
Tool-Calling Classification Engine for RCB
============================================
Replaces the 6-agent sequential pipeline with a single AI call
that uses tools to gather data on demand.

Entry point: tool_calling_classify(api_key, doc_text, db, gemini_key=None)
Returns the EXACT same dict format as run_full_classification().

Fallback: If this fails, classification_agents.py falls back to the old pipeline.
"""

import json
import time
import re
import requests

from lib.tool_definitions import CLAUDE_TOOLS, GEMINI_TOOLS, CLASSIFICATION_SYSTEM_PROMPT
from lib.tool_executors import ToolExecutor

# Optional modules — graceful degradation
try:
    from lib.document_parser import parse_all_documents
    _PARSER_OK = True
except ImportError:
    _PARSER_OK = False

try:
    from lib.document_tracker import (
        create_tracker, Document, DocumentType as TrackerDocType, feed_parsed_documents
    )
    _TRACKER_OK = True
except ImportError:
    _TRACKER_OK = False

try:
    from lib.smart_questions import should_ask_questions, generate_smart_questions
    _QUESTIONS_OK = True
except ImportError:
    _QUESTIONS_OK = False

try:
    from lib.language_tools import HebrewLanguageChecker
    _lang = HebrewLanguageChecker()
    _LANG_OK = True
except ImportError:
    _LANG_OK = False

try:
    from lib.intelligence import validate_documents
    _INTEL_OK = True
except ImportError:
    _INTEL_OK = False

from lib.librarian import validate_and_correct_classifications
from lib.verification_loop import verify_all_classifications, learn_from_verification

# NOTE: classification_agents imports are LAZY (inside function) to avoid circular import.
# classification_agents.py imports tool_calling_engine.py, so we can't import at module level.


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CLAUDE_MODEL = "claude-sonnet-4-20250514"
_GEMINI_MODEL = "gemini-2.5-flash"
_MAX_TOKENS = 4096
_MAX_ROUNDS = 8
_TIME_BUDGET_SEC = 120  # Hard ceiling — abort tool loop after this

# Cost optimization: Gemini Flash is ~20x cheaper than Claude Sonnet.
# Try Gemini first for tool-calling, fall back to Claude if Gemini fails.
_PREFER_GEMINI = True

# Pre-enrichment trigger keywords — auto-call food/medical tools if detected
_FOOD_TRIGGERS = {
    "food", "edible", "chocolate", "candy", "sugar", "flour", "rice", "wheat",
    "meat", "fish", "dairy", "milk", "cheese", "butter", "oil", "olive",
    "fruit", "vegetable", "nut", "spice", "tea", "coffee", "cocoa",
    "sauce", "jam", "honey", "cereal", "pasta", "bread", "snack",
    "beverage", "juice", "wine", "beer", "spirit", "vinegar",
    "מזון", "שוקולד", "סוכר", "קמח", "אורז", "חיטה", "בשר", "דג", "דגים",
    "חלב", "גבינה", "חמאה", "שמן", "זית", "פרי", "ירק", "תבלין",
    "תה", "קפה", "קקאו", "דבש", "יין", "בירה", "מיץ",
}
_MEDICAL_TRIGGERS = {
    "pharmaceutical", "drug", "medicine", "medical", "surgical", "implant",
    "prosthetic", "catheter", "syringe", "bandage", "gauze", "suture",
    "diagnostic", "reagent", "vaccine", "insulin", "antibiotic",
    "tablet", "capsule", "ointment", "inhaler", "stent",
    "תרופה", "רפואי", "כירורגי", "שתל", "מזרק", "תחבושת", "חיסון",
    "אנטיביוטיקה", "כדור", "קפסולה", "משחה",
}
_CHEMICAL_TRIGGERS = {
    "acid", "oxide", "chloride", "polymer", "resin", "compound",
    "formula", "cas", "solvent", "reagent", "chemical", "monomer",
    "catalyst", "sulfate", "hydroxide", "carbonate", "phosphate",
    "nitrate", "peroxide", "ether", "ester", "aldehyde", "ketone",
    "חומצה", "תחמוצת", "כלוריד", "פולימר", "שרף", "תרכובת",
    "ממס", "כימי", "מונומר", "קטליזטור",
}
_COSMETICS_TRIGGERS = {
    "cream", "lotion", "shampoo", "perfume", "cosmetic", "beauty",
    "skincare", "makeup", "serum", "moisturizer", "conditioner",
    "lipstick", "mascara", "foundation", "sunscreen", "deodorant",
    "nail polish", "fragrance", "soap", "cleanser",
    "קרם", "שמפו", "בושם", "קוסמטיקה", "יופי", "סרום", "לחות",
    "שפתון", "מסקרה", "סבון",
}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def tool_calling_classify(api_key, doc_text, db, gemini_key=None):
    """
    Classify using tool-calling architecture.

    Returns the EXACT same dict as run_full_classification() or None on failure.
    """
    t0 = time.time()
    print("  [TOOL ENGINE] Starting tool-calling classification...")

    # Lazy imports to avoid circular dependency with classification_agents.py
    from lib.classification_agents import (
        _link_invoice_to_classifications,
        _is_valid_hs,
        audit_before_send,
        query_tariff,
        query_classification_rules,
        run_synthesis_agent,
    )

    executor = ToolExecutor(db, api_key, gemini_key=gemini_key)

    # ── Step 1: Document parsing (same as old pipeline) ──
    parsed_documents = []
    if _PARSER_OK:
        try:
            parsed_documents = parse_all_documents(doc_text)
            if parsed_documents:
                types = [d["type_info"]["name_en"] for d in parsed_documents]
                print(f"  [TOOL ENGINE] Parsed {len(parsed_documents)} docs: {', '.join(types)}")
        except Exception as e:
            print(f"  [TOOL ENGINE] Document parser error: {e}")

    # ── Step 2: Extract invoice (always needed — uses Gemini Flash) ──
    print("  [TOOL ENGINE] Extracting invoice...")
    invoice = executor.execute("extract_invoice", {"document_text": doc_text})
    if not isinstance(invoice, dict) or invoice.get("error"):
        print(f"  [TOOL ENGINE] Invoice extraction failed, using fallback")
        invoice = {"items": [{"description": doc_text[:500]}]}

    items = invoice.get("items") or [{"description": doc_text[:500]}]
    if not isinstance(items, list):
        items = [{"description": doc_text[:500]}]
    origin = items[0].get("origin_country", "") if items and isinstance(items[0], dict) else ""

    print(f"  [TOOL ENGINE] Invoice: {len(items)} items, origin='{origin}'")

    # ── Step 3: Shipment tracker ──
    tracker_info = None
    if _TRACKER_OK and parsed_documents:
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
            if invoice.get("invoice_number") or invoice.get("seller"):
                tracker.add_document(Document(
                    doc_type=TrackerDocType.INVOICE,
                    doc_number=invoice.get("invoice_number", ""),
                ))
            tracker_info = tracker.to_dict()
        except Exception as e:
            print(f"  [TOOL ENGINE] Tracker error: {e}")

    # ── Step 4: Memory check for each item ──
    memory_hits = {}
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        desc = item.get("description", "")
        if not desc:
            continue
        mem = executor.execute("check_memory", {"product_description": desc})
        if mem.get("found") and mem.get("level") == "exact" and mem.get("confidence", 0) >= 0.9:
            memory_hits[desc[:50]] = mem
            print(f"  [TOOL ENGINE] Memory HIT (exact): {desc[:40]} → {mem.get('hs_code')}")

    # ── Step 4b: Pre-enrichment — deterministic external lookups ──
    enrichment = {}

    # Country lookup if origin known
    if origin and len(origin) >= 2:
        try:
            country_data = executor.execute("lookup_country", {"country": origin})
            if isinstance(country_data, dict) and country_data.get("found"):
                enrichment["country"] = country_data
                print(f"  [TOOL ENGINE] Pre-enriched: country '{origin}' → {country_data.get('cca2', '?')}")
        except Exception:
            pass

    # Currency lookup if non-ILS
    invoice_currency = (invoice.get("currency", "") or "").upper()
    if invoice_currency and invoice_currency not in ("ILS", "NIS", ""):
        try:
            currency_data = executor.execute("convert_currency",
                                             {"from_currency": invoice_currency, "to_currency": "ILS"})
            if isinstance(currency_data, dict) and currency_data.get("found"):
                enrichment["currency"] = currency_data
                rate = currency_data.get("target_rate", "?")
                print(f"  [TOOL ENGINE] Pre-enriched: {invoice_currency}/ILS = {rate}")
        except Exception:
            pass

    # Food product lookup if food keywords detected
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        desc_words = set(re.findall(r'\w+', (item.get("description", "") or "").lower()))
        if desc_words & _FOOD_TRIGGERS:
            try:
                food_data = executor.execute("lookup_food_product",
                                             {"query": item["description"][:100]})
                if isinstance(food_data, dict) and food_data.get("found"):
                    enrichment[f"food_{item['description'][:30]}"] = food_data
                    print(f"  [TOOL ENGINE] Pre-enriched: food product '{item['description'][:30]}'")
            except Exception:
                pass
            break  # Only one food lookup per classification run

    # FDA product lookup if medical keywords detected
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        desc_words = set(re.findall(r'\w+', (item.get("description", "") or "").lower()))
        if desc_words & _MEDICAL_TRIGGERS:
            try:
                fda_data = executor.execute("check_fda_product",
                                            {"query": item["description"][:100]})
                if isinstance(fda_data, dict) and fda_data.get("found"):
                    enrichment[f"fda_{item['description'][:30]}"] = fda_data
                    print(f"  [TOOL ENGINE] Pre-enriched: FDA product '{item['description'][:30]}'")
            except Exception:
                pass
            break  # Only one FDA lookup per classification run

    # Chemical compound lookup if chemical keywords detected (Tool #22)
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        desc_words = set(re.findall(r'\w+', (item.get("description", "") or "").lower()))
        if desc_words & _CHEMICAL_TRIGGERS:
            try:
                chem_data = executor.execute("search_pubchem",
                                              {"query": item["description"][:100]})
                if isinstance(chem_data, dict) and chem_data.get("found"):
                    enrichment[f"chemical_{item['description'][:30]}"] = chem_data
                    print(f"  [TOOL ENGINE] Pre-enriched: chemical '{item['description'][:30]}'")
            except Exception:
                pass
            break  # Only one chemical lookup per classification run

    # Cosmetics product lookup if cosmetics keywords detected (Tool #29)
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        desc_words = set(re.findall(r'\w+', (item.get("description", "") or "").lower()))
        if desc_words & _COSMETICS_TRIGGERS:
            try:
                beauty_data = executor.execute("search_open_beauty",
                                                {"query": item["description"][:100]})
                if isinstance(beauty_data, dict) and beauty_data.get("found"):
                    enrichment[f"cosmetics_{item['description'][:30]}"] = beauty_data
                    print(f"  [TOOL ENGINE] Pre-enriched: cosmetics '{item['description'][:30]}'")
            except Exception:
                pass
            break  # Only one cosmetics lookup per classification run

    # BOI official rate for customs valuation (Tool #21) — replaces open.er-api for legal purposes
    if invoice_currency and invoice_currency not in ("ILS", "NIS", ""):
        try:
            boi_data = executor.execute("bank_of_israel_rates",
                                         {"currency": invoice_currency})
            if isinstance(boi_data, dict) and boi_data.get("found"):
                enrichment["boi_rate"] = boi_data
                rate = boi_data.get("rate", "?")
                print(f"  [TOOL ENGINE] Pre-enriched: BOI {invoice_currency}/ILS = {rate}")
        except Exception:
            pass

    # ── Step 5: AI classification call (skip if ALL items hit memory) ──
    ai_response = None
    if len(memory_hits) < len(items):
        print(f"  [TOOL ENGINE] {len(memory_hits)} memory hits, {len(items) - len(memory_hits)} need AI")

        # Build user prompt with invoice data + pre-enrichment
        user_prompt = _build_user_prompt(items, origin, invoice, doc_text, enrichment=enrichment)

        # Multi-turn tool calling loop (Gemini primary, Claude fallback)
        ai_response = _run_tool_loop(api_key, user_prompt, executor, gemini_key=gemini_key)
    else:
        print(f"  [TOOL ENGINE] ALL {len(items)} items from memory — skipping AI")

    # ── Step 6: Parse AI response into classifications ──
    classifications, regulatory, fta, risk, synthesis = _parse_ai_response(
        ai_response, memory_hits, items
    )

    # ── Step 7: Post-processing (same as old pipeline) ──
    classification_dict = {"classifications": classifications}

    # 7a: Validate HS codes
    for c in classifications:
        hs = c.get("hs_code", "")
        if hs and not _is_valid_hs(hs):
            c["original_hs_code"] = hs
            c["hs_code"] = ""
            c["confidence"] = "נמוכה"

    validated = validate_and_correct_classifications(db, classifications)
    classification_dict["classifications"] = validated

    # 7b: Free Import Order for valid HS codes
    free_import_results = {}
    for c in validated[:3]:
        hs = c.get("hs_code", "")
        if hs and _is_valid_hs(hs):
            if hs in executor._fio_cache:
                fio = executor._fio_cache[hs]
            else:
                reg = executor.execute("check_regulatory", {"hs_code": hs})
                fio = reg.get("free_import_order", {})
            if fio.get("found"):
                free_import_results[hs] = fio

    # 7c: Ministry routing for valid HS codes
    ministry_routing = {}
    for c in validated[:3]:
        hs = c.get("hs_code", "")
        if hs and _is_valid_hs(hs):
            if hs in executor._ministry_cache:
                routing = executor._ministry_cache[hs]
            else:
                reg = executor.execute("check_regulatory", {"hs_code": hs})
                routing = reg.get("ministry_routing", {})
            if routing.get("ministries"):
                ministry_routing[hs] = routing

    # 7d: Verification loop
    try:
        validated = verify_all_classifications(
            db, validated, free_import_results=free_import_results
        )
        classification_dict["classifications"] = validated
        for c in validated:
            if c.get("verification_status") in ("official", "verified"):
                learn_from_verification(db, c)
    except Exception as e:
        print(f"  [TOOL ENGINE] Verification error: {e}")

    # 7d2: Cross-reference pipeline (EU TARIC + US HTS confidence adjustment)
    cross_ref_results = {}
    try:
        for c in validated[:3]:
            hs = c.get("hs_code", "")
            if not hs or not _is_valid_hs(hs):
                continue
            hs_clean = hs.replace(".", "").replace("/", "").replace(" ", "")
            if len(hs_clean) < 6:
                continue
            eu_agrees = False
            us_agrees = False
            eu_result = executor.execute("lookup_eu_taric", {"hs_code": hs_clean})
            if isinstance(eu_result, dict) and eu_result.get("found"):
                cross_ref_results[f"eu_{hs}"] = eu_result
                eu_desc = (eu_result.get("description", "") or "").lower()
                item_desc = (c.get("item_description", "") or c.get("item", "") or "").lower()
                if eu_desc and item_desc:
                    item_words = set(re.findall(r'\w{3,}', item_desc))
                    eu_words = set(re.findall(r'\w{3,}', eu_desc))
                    if item_words & eu_words:
                        eu_agrees = True
            us_result = executor.execute("lookup_usitc", {"hs_code": hs_clean})
            if isinstance(us_result, dict) and us_result.get("found"):
                cross_ref_results[f"us_{hs}"] = us_result
                us_desc = (us_result.get("description", "") or "").lower()
                item_desc = (c.get("item_description", "") or c.get("item", "") or "").lower()
                if us_desc and item_desc:
                    item_words = set(re.findall(r'\w{3,}', item_desc))
                    us_words = set(re.findall(r'\w{3,}', us_desc))
                    if item_words & us_words:
                        us_agrees = True
            # Confidence adjustment based on cross-reference agreement
            if eu_agrees and us_agrees:
                c["cross_ref_adjustment"] = 0.12
                c["cross_ref_note"] = "EU+US agree"
            elif eu_agrees or us_agrees:
                c["cross_ref_adjustment"] = 0.06
                src = "EU" if eu_agrees else "US"
                c["cross_ref_note"] = f"{src} agrees"
            elif eu_result.get("found") or us_result.get("found"):
                c["cross_ref_adjustment"] = -0.05
                c["cross_ref_note"] = "CROSS_REF_CONFLICT"
                print(f"  [TOOL ENGINE] CROSS_REF_CONFLICT for {hs}")
        if cross_ref_results:
            print(f"  [TOOL ENGINE] Cross-ref: {len(cross_ref_results)} lookups")
    except Exception as e:
        print(f"  [TOOL ENGINE] Cross-reference error (non-fatal): {e}")

    # 7e: Link invoice lines to classifications
    validated = _link_invoice_to_classifications(items, validated)
    classification_dict["classifications"] = validated

    # 7f: Smart questions
    smart_questions = []
    ambiguity_info = {}
    if _QUESTIONS_OK:
        try:
            ask, ambiguity_info = should_ask_questions(
                validated,
                intelligence_results={},
                free_import_results=free_import_results,
                ministry_routing=ministry_routing,
            )
            if ask:
                smart_questions = generate_smart_questions(
                    ambiguity_info, validated,
                    invoice_data=invoice,
                    free_import_results=free_import_results,
                    ministry_routing=ministry_routing,
                    parsed_documents=parsed_documents,
                )
        except Exception as e:
            print(f"  [TOOL ENGINE] Smart questions error: {e}")

    # 7g: Document validation
    doc_validation = None
    if _INTEL_OK:
        try:
            has_fta = any(f.get("eligible") for f in fta if isinstance(f, dict))
            doc_validation = validate_documents(doc_text, direction="import", has_fta=has_fta)
        except Exception as e:
            print(f"  [TOOL ENGINE] Doc validation error: {e}")

    # 7h: Audit before send
    all_results = {
        "invoice": invoice,
        "classification": classification_dict,
        "regulatory": {"regulatory": regulatory},
        "fta": {"fta": fta},
        "risk": {"risk": risk},
    }
    pre_send = {"agents": all_results, "invoice_data": invoice}

    tariff = query_tariff(db, [i.get("description", "")[:50] for i in items[:5] if isinstance(i, dict)])
    rules = query_classification_rules(db)

    audit = audit_before_send(
        pre_send, api_key=api_key, items=items,
        tariff=tariff, rules=rules, context="",
        gemini_key=gemini_key, db=db,
    )
    all_results["classification"]["classifications"] = audit["classifications"]

    # 7i: Synthesis (if AI didn't provide one)
    if not synthesis:
        synthesis = run_synthesis_agent(api_key, all_results, gemini_key=gemini_key)

    # 7j: Language cleanup
    if _LANG_OK and synthesis:
        try:
            synthesis = _lang.fix_all(synthesis)
        except Exception:
            pass

    # ── Step 8: Learn from this classification (FREE) ──
    try:
        from lib.self_learning import SelfLearningEngine
        learning = SelfLearningEngine(db)
        learned_count = 0
        for c in validated:
            hs = c.get("hs_code", "")
            desc = c.get("item_description", "") or c.get("item", "")
            if hs and desc and c.get("verification_status") in ("official", "verified"):
                learning.learn_classification(
                    product_description=desc,
                    hs_code=hs,
                    method="ai",
                    source="tool_calling",
                    confidence=0.85,
                )
                learned_count += 1
        if learned_count:
            print(f"  [TOOL ENGINE] Learned {learned_count} classifications → memory")
    except Exception as e:
        print(f"  [TOOL ENGINE] Learning error (non-fatal): {e}")

    # ── Build final result ──
    elapsed = time.time() - t0
    print(f"  [TOOL ENGINE] Done in {elapsed:.1f}s | Tools: {executor.get_stats()}")

    return {
        "success": True,
        "agents": all_results,
        "synthesis": synthesis,
        "invoice_data": invoice,
        "intelligence": {},  # tool engine uses tools directly, no pre-classify dict
        "document_validation": doc_validation,
        "free_import_order": free_import_results,
        "ministry_routing": ministry_routing,
        "parsed_documents": parsed_documents,
        "smart_questions": smart_questions,
        "ambiguity": ambiguity_info,
        "tracker": tracker_info,
        "audit": audit,
        "cross_reference": cross_ref_results if cross_ref_results else None,
        "_engine": "tool_calling",
    }


# ---------------------------------------------------------------------------
# Multi-turn tool calling loop (Claude API)
# ---------------------------------------------------------------------------

def _run_tool_loop(api_key, user_prompt, executor, gemini_key=None):
    """
    Send message to AI with tools, execute tool calls, repeat.
    Tries Gemini Flash first (20x cheaper), falls back to Claude if needed.

    Constraints:
        - Max 8 rounds
        - 120 second time budget
    """
    # Choose model: Gemini first if available and preferred
    use_gemini = _PREFER_GEMINI and gemini_key
    model_label = "Gemini" if use_gemini else "Claude"
    print(f"  [TOOL ENGINE] Using {model_label} for tool-calling loop")

    if use_gemini:
        return _run_gemini_tool_loop(gemini_key, user_prompt, executor, api_key)
    else:
        return _run_claude_tool_loop(api_key, user_prompt, executor)


def _run_claude_tool_loop(api_key, user_prompt, executor):
    """Claude tool-calling loop (fallback — more expensive)."""
    messages = [{"role": "user", "content": user_prompt}]
    t0 = time.time()
    text_parts = []

    for round_num in range(_MAX_ROUNDS):
        elapsed = time.time() - t0
        if elapsed > _TIME_BUDGET_SEC:
            print(f"  [TOOL ENGINE] Time budget exhausted ({elapsed:.0f}s) at round {round_num}")
            break

        print(f"  [TOOL ENGINE] Claude round {round_num + 1}...")
        response = _call_claude_with_tools(api_key, messages)
        if not response:
            print("  [TOOL ENGINE] Claude API returned None")
            return None

        stop_reason = response.get("stop_reason", "")
        content_blocks = response.get("content", [])

        # Collect text and tool_use blocks
        text_parts = []
        tool_uses = []
        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_uses.append(block)

        if stop_reason == "end_turn" or not tool_uses:
            final_text = "\n".join(text_parts)
            print(f"  [TOOL ENGINE] Claude finished in {round_num + 1} rounds")
            return final_text

        # Execute tool calls
        messages.append({"role": "assistant", "content": content_blocks})
        tool_results = []
        for tu in tool_uses:
            tool_name = tu.get("name", "")
            tool_input = tu.get("input", {})
            tool_id = tu.get("id", "")

            if time.time() - t0 > _TIME_BUDGET_SEC:
                print(f"  [TOOL ENGINE] Time budget hit during tool execution")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": json.dumps({"error": "Time budget exceeded"}, ensure_ascii=False),
                })
                continue

            result = executor.execute(tool_name, tool_input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

        messages.append({"role": "user", "content": tool_results})

    print(f"  [TOOL ENGINE] Max rounds reached, returning last text")
    return "\n".join(text_parts) if text_parts else None


def _run_gemini_tool_loop(gemini_key, user_prompt, executor, claude_api_key=None):
    """
    Gemini Flash tool-calling loop (PRIMARY — 20x cheaper than Claude).
    Falls back to Claude if Gemini fails completely.
    """
    t0 = time.time()

    # Gemini uses a different message format
    contents = [{"role": "user", "parts": [{"text": user_prompt}]}]
    text_parts = []

    for round_num in range(_MAX_ROUNDS):
        elapsed = time.time() - t0
        if elapsed > _TIME_BUDGET_SEC:
            print(f"  [TOOL ENGINE] Time budget exhausted ({elapsed:.0f}s) at round {round_num}")
            break

        print(f"  [TOOL ENGINE] Gemini round {round_num + 1}...")
        response = _call_gemini_with_tools(gemini_key, contents)
        if not response:
            print("  [TOOL ENGINE] Gemini API returned None — falling back to Claude")
            if claude_api_key:
                return _run_claude_tool_loop(claude_api_key, user_prompt, executor)
            return None

        # Parse Gemini response
        candidates = response.get("candidates", [])
        if not candidates:
            print("  [TOOL ENGINE] Gemini no candidates — falling back to Claude")
            if claude_api_key:
                return _run_claude_tool_loop(claude_api_key, user_prompt, executor)
            return None

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])

        # Collect text and function calls
        text_parts = []
        func_calls = []
        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])
            elif "functionCall" in part:
                func_calls.append(part["functionCall"])

        # Check finish reason
        finish_reason = candidates[0].get("finishReason", "")
        if not func_calls or finish_reason == "STOP":
            final_text = "\n".join(text_parts)
            print(f"  [TOOL ENGINE] Gemini finished in {round_num + 1} rounds")
            return final_text

        # Execute function calls and build response
        contents.append({"role": "model", "parts": parts})
        func_responses = []
        for fc in func_calls:
            tool_name = fc.get("name", "")
            tool_args = fc.get("args", {})

            if time.time() - t0 > _TIME_BUDGET_SEC:
                print(f"  [TOOL ENGINE] Time budget hit during tool execution")
                func_responses.append({
                    "functionResponse": {
                        "name": tool_name,
                        "response": {"error": "Time budget exceeded"},
                    }
                })
                continue

            result = executor.execute(tool_name, tool_args)
            func_responses.append({
                "functionResponse": {
                    "name": tool_name,
                    "response": result if isinstance(result, dict) else {"result": str(result)},
                }
            })

        contents.append({"role": "user", "parts": func_responses})

    print(f"  [TOOL ENGINE] Max rounds reached, returning last text")
    return "\n".join(text_parts) if text_parts else None


def _call_gemini_with_tools(gemini_key, contents):
    """Single Gemini API call with function declarations (tool calling)."""
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{_GEMINI_MODEL}:generateContent?key={gemini_key}",
            headers={"content-type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": CLASSIFICATION_SYSTEM_PROMPT}]},
                "contents": contents,
                "tools": GEMINI_TOOLS,
                "generationConfig": {
                    "maxOutputTokens": _MAX_TOKENS,
                    "temperature": 0.3,
                },
            },
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Cost tracking — Gemini Flash pricing
            usage = data.get("usageMetadata", {})
            inp_tok = usage.get("promptTokenCount", 0)
            out_tok = usage.get("candidatesTokenCount", 0)
            cost = (inp_tok * 0.15 + out_tok * 0.60) / 1_000_000
            print(f"    💰 Gemini (tool-call): {inp_tok}+{out_tok} tokens = ${cost:.4f}")
            try:
                from lib.classification_agents import _cost_tracker
                _cost_tracker.add("Gemini tool-call", cost)
            except ImportError:
                pass
            return data
        print(f"  [TOOL ENGINE] Gemini API error: {resp.status_code} - {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"  [TOOL ENGINE] Gemini API exception: {e}")
        return None


def _call_claude_with_tools(api_key, messages):
    """Single Claude API call with tool definitions (fallback — more expensive)."""
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": _CLAUDE_MODEL,
                "max_tokens": _MAX_TOKENS,
                "system": CLASSIFICATION_SYSTEM_PROMPT,
                "tools": CLAUDE_TOOLS,
                "messages": messages,
            },
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Cost tracking
            usage = data.get("usage", {})
            inp_tok = usage.get("input_tokens", 0)
            out_tok = usage.get("output_tokens", 0)
            cost = (inp_tok * 3.0 + out_tok * 15.0) / 1_000_000
            print(f"    💰 Claude (tool-call fallback): {inp_tok}+{out_tok} tokens = ${cost:.4f}")
            try:
                from lib.classification_agents import _cost_tracker
                _cost_tracker.add("Claude tool-call", cost)
            except ImportError:
                pass
            return data
        print(f"  [TOOL ENGINE] Claude API error: {resp.status_code} - {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"  [TOOL ENGINE] Claude API exception: {e}")
        return None


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_user_prompt(items, origin, invoice, doc_text, enrichment=None):
    """Build the user prompt with invoice data for the AI."""
    parts = ["Classify the following items from the invoice:\n"]

    for idx, item in enumerate(items[:10]):
        if not isinstance(item, dict):
            continue
        desc = item.get("description", "")
        qty = item.get("quantity", "")
        val = item.get("total", "") or item.get("unit_price", "")
        item_origin = item.get("origin_country", origin)
        parts.append(f"{idx+1}. {desc}")
        if qty:
            parts.append(f"   Quantity: {qty}")
        if val:
            parts.append(f"   Value: {val}")
        if item_origin:
            parts.append(f"   Origin: {item_origin}")
        parts.append("")

    if invoice.get("seller"):
        parts.append(f"Seller: {invoice['seller']}")
    if invoice.get("buyer"):
        parts.append(f"Buyer: {invoice['buyer']}")
    if invoice.get("currency"):
        parts.append(f"Currency: {invoice['currency']}")
    if invoice.get("incoterms"):
        parts.append(f"Incoterms: {invoice['incoterms']}")

    # Include pre-enrichment data if available
    if enrichment:
        parts.append("\n--- Pre-loaded external data (already fetched) ---")
        for key, data in enrichment.items():
            if isinstance(data, dict) and data.get("found"):
                summary = json.dumps(data, ensure_ascii=False, default=str)[:500]
                parts.append(f"{key}: {summary}")
        parts.append("")

    parts.append("\nClassify each item to the most specific Israeli HS code.")
    parts.append("Use the tools to check memory, search tariff DB, verify codes, and check regulatory requirements.")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_ai_response(ai_text, memory_hits, items):
    """
    Parse the AI's final text response into structured data.
    Also merges any memory hits.

    Returns: (classifications, regulatory, fta, risk, synthesis)
    """
    classifications = []
    regulatory = []
    fta = []
    risk = {"level": "נמוך", "items": []}
    synthesis = ""

    # Parse AI JSON response
    if ai_text:
        parsed = _extract_json(ai_text)
        if parsed:
            classifications = parsed.get("classifications", [])
            regulatory = parsed.get("regulatory", [])
            fta = parsed.get("fta", [])
            risk = parsed.get("risk", {"level": "נמוך", "items": []})
            synthesis = parsed.get("synthesis", "")

    # Merge memory hits for items not in AI response
    ai_described = {c.get("item_description", "").lower()[:50] for c in classifications}
    for desc_key, mem in memory_hits.items():
        if desc_key.lower() not in ai_described:
            classifications.append({
                "item": desc_key,
                "item_description": desc_key,
                "hs_code": mem.get("hs_code", ""),
                "confidence": "גבוהה",
                "reasoning": f"From memory ({mem.get('level', 'exact')})",
                "source": "memory",
            })

    # Normalize classification fields
    for c in classifications:
        if "item" not in c and "item_description" in c:
            c["item"] = c["item_description"]
        if "item_description" not in c and "item" in c:
            c["item_description"] = c["item"]

    return classifications, regulatory, fta, risk, synthesis


def _extract_json(text):
    """Extract JSON from AI response — handles code fences and mixed text."""
    if not text:
        return None

    # Try code-fenced JSON first
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try raw JSON object
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return None
