"""
Three-Way AI Cross-Check for RCB Classification
================================================
Sends product descriptions to Claude, Gemini, and ChatGPT independently.
Compares HS code results. Returns consensus + escalation tier.

Session 27: Initial implementation.

Escalation tiers:
  1. FULL_MATCH    - All 3 agree on HS code (6+ digits) -> highest confidence
  2. HEADING_MATCH - All 3 agree on heading (4 digits), differ on subheading -> good confidence
  3. MAJORITY      - 2/3 agree on heading -> use majority, flag minority
  4. DISAGREEMENT  - All differ at heading level -> flag for human review

Learning feedback:
  - Stores every cross-check in Firestore `cross_check_log` collection
  - Disagreements are flagged for future training / rule creation
"""

import json
import re
import time
import traceback


# Cross-check system prompt (shared by all 3 models)
_CROSS_CHECK_SYSTEM = (
    "You are an expert Israeli customs classification AI. "
    "Given a product description, return ONLY the most appropriate HS code "
    "in the Israeli 10-digit format (e.g., 8471.30.0000). "
    "Respond with a JSON object: {\"hs_code\": \"XXXX.XX.XXXX\", \"confidence\": 0.0-1.0, \"reason\": \"brief reason\"}\n"
    "RULES:\n"
    "- Use the Harmonized System (HS) / Israeli Customs Tariff.\n"
    "- Be as specific as possible (8-10 digits).\n"
    "- If unsure, classify to the most likely 4-digit heading.\n"
    "- Return ONLY valid JSON, no markdown fences."
)

# HS code extraction regex
_HS_PATTERN = re.compile(r'\b(\d{4})[\.\s]?(\d{2})[\.\s]?(\d{2,4})\b')
_HS_SHORT = re.compile(r'\b(\d{4})[\.\s]?(\d{2})\b')
_HS_HEADING = re.compile(r'\b(\d{4})\b')


def cross_check_classification(
    primary_hs,
    item_description,
    origin_country,
    api_key,
    gemini_key,
    openai_key,
    db=None,
):
    """
    Run 3-way classification cross-check.

    Args:
        primary_hs: str - HS code from the primary classification engine
        item_description: str - product description
        origin_country: str - country of origin
        api_key: str - Anthropic API key (for Claude)
        gemini_key: str - Google Gemini API key
        openai_key: str - OpenAI API key
        db: Firestore client (optional, for logging)

    Returns:
        dict with:
            tier: int (1-4)
            tier_name: str
            primary_hs: str
            models: dict of {model_name: {hs_code, confidence, reason, raw}}
            consensus_hs: str or None
            confidence_adjustment: float (-0.2 to +0.1)
            learning_note: str (Hebrew)
    """
    start = time.time()
    print(f"  [CROSS-CHECK] Starting 3-way verification for HS {primary_hs}...")

    # Build the user prompt
    user_prompt = _build_user_prompt(item_description, origin_country)

    # Call all 3 models (synchronous, sequential)
    models = {}

    # 1. Claude (Sonnet 4.5)
    claude_result = _call_claude_check(api_key, user_prompt)
    models["claude"] = claude_result

    # 2. Gemini (Flash)
    gemini_result = _call_gemini_check(gemini_key, user_prompt)
    models["gemini"] = gemini_result

    # 3. ChatGPT (4o-mini)
    chatgpt_result = _call_chatgpt_check(openai_key, user_prompt)
    models["chatgpt"] = chatgpt_result

    # Compare results
    result = _compare_results(primary_hs, models)

    elapsed = time.time() - start
    print(f"  [CROSS-CHECK] Tier {result['tier']} ({result['tier_name']}) in {elapsed:.1f}s")
    for name, m in models.items():
        hs = m.get("hs_code", "N/A")
        print(f"    {name}: {hs}")

    # Log to Firestore
    if db:
        _log_cross_check(db, result, item_description, origin_country, elapsed)

    return result


def cross_check_all_items(classifications, item_descriptions, origin_country,
                          api_key, gemini_key, openai_key, db=None):
    """
    Cross-check multiple classified items. Returns list of cross-check results.
    Only checks the first 3 items to limit cost.
    """
    results = []
    for i, cls in enumerate(classifications[:3]):
        hs_code = cls.get("hs_code", "")
        desc = ""
        if i < len(item_descriptions):
            desc = item_descriptions[i]
        if not desc:
            desc = cls.get("item_description", "") or cls.get("item", "")
        if not desc or not hs_code:
            continue

        result = cross_check_classification(
            primary_hs=hs_code,
            item_description=desc,
            origin_country=origin_country,
            api_key=api_key,
            gemini_key=gemini_key,
            openai_key=openai_key,
            db=db,
        )
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_user_prompt(item_description, origin_country):
    """Build the classification prompt for cross-check."""
    prompt = f"Classify this product for Israeli customs import:\n\nProduct: {item_description}"
    if origin_country:
        prompt += f"\nOrigin country: {origin_country}"
    prompt += "\n\nReturn ONLY JSON: {\"hs_code\": \"XXXX.XX.XXXX\", \"confidence\": 0.0-1.0, \"reason\": \"...\"}"
    return prompt


def _call_claude_check(api_key, user_prompt):
    """Call Claude for cross-check. Returns parsed result dict."""
    if not api_key:
        return {"hs_code": None, "error": "no_key"}
    try:
        from lib.classification_agents import call_claude
        raw = call_claude(api_key, _CROSS_CHECK_SYSTEM, user_prompt, max_tokens=500)
        if raw:
            return _parse_model_response(raw, "claude")
        return {"hs_code": None, "error": "empty_response"}
    except Exception as e:
        print(f"    [CROSS-CHECK] Claude error: {e}")
        return {"hs_code": None, "error": str(e)}


def _call_gemini_check(gemini_key, user_prompt):
    """Call Gemini Flash for cross-check. Returns parsed result dict."""
    if not gemini_key:
        return {"hs_code": None, "error": "no_key"}
    try:
        from lib.classification_agents import call_gemini_fast
        raw = call_gemini_fast(gemini_key, _CROSS_CHECK_SYSTEM, user_prompt, max_tokens=500)
        if raw:
            return _parse_model_response(raw, "gemini")
        return {"hs_code": None, "error": "empty_response"}
    except Exception as e:
        print(f"    [CROSS-CHECK] Gemini error: {e}")
        return {"hs_code": None, "error": str(e)}


def _call_chatgpt_check(openai_key, user_prompt):
    """Call ChatGPT for cross-check. Returns parsed result dict."""
    if not openai_key:
        return {"hs_code": None, "error": "no_key"}
    try:
        from lib.classification_agents import call_chatgpt
        raw = call_chatgpt(openai_key, _CROSS_CHECK_SYSTEM, user_prompt, max_tokens=500)
        if raw:
            return _parse_model_response(raw, "chatgpt")
        return {"hs_code": None, "error": "empty_response"}
    except Exception as e:
        print(f"    [CROSS-CHECK] ChatGPT error: {e}")
        return {"hs_code": None, "error": str(e)}


def _parse_model_response(raw_text, model_name):
    """Parse model response to extract HS code, confidence, reason."""
    result = {"raw": raw_text[:300], "hs_code": None, "confidence": 0, "reason": ""}

    # Try JSON parse first
    try:
        # Strip markdown fences
        text = raw_text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            hs = str(data.get("hs_code", "")).strip()
            if hs:
                result["hs_code"] = _normalize_hs(hs)
                result["confidence"] = float(data.get("confidence", 0))
                result["reason"] = str(data.get("reason", ""))[:200]
                return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: regex extract HS code from text
    hs = _extract_hs_regex(raw_text)
    if hs:
        result["hs_code"] = hs
        result["reason"] = f"Extracted via regex from {model_name} response"
    return result


def _normalize_hs(code):
    """Normalize HS code to digits only (remove dots, slashes, spaces)."""
    clean = str(code).replace(".", "").replace("/", "").replace(" ", "").strip()
    # Must be 4-10 digits
    if re.match(r'^\d{4,10}$', clean):
        return clean
    return None


def _extract_hs_regex(text):
    """Extract HS code from free text using regex."""
    # Try full 8-10 digit match
    m = _HS_PATTERN.search(text)
    if m:
        return m.group(1) + m.group(2) + m.group(3)
    # Try 6-digit match
    m = _HS_SHORT.search(text)
    if m:
        return m.group(1) + m.group(2)
    # Try 4-digit heading
    m = _HS_HEADING.search(text)
    if m:
        return m.group(1)
    return None


def _compare_results(primary_hs, models):
    """
    Compare primary HS with 3 model results.
    Returns dict with tier, consensus, and confidence adjustment.
    """
    primary_clean = _normalize_hs(primary_hs) or ""
    primary_heading = primary_clean[:4] if len(primary_clean) >= 4 else ""
    primary_6 = primary_clean[:6] if len(primary_clean) >= 6 else ""

    # Collect all valid HS codes (including primary)
    all_codes = {"primary": primary_clean}
    for name, m in models.items():
        hs = m.get("hs_code")
        if hs:
            all_codes[name] = hs

    responding_models = {k: v for k, v in all_codes.items() if v and k != "primary"}

    if not responding_models:
        return {
            "tier": 4,
            "tier_name": "NO_RESPONSE",
            "primary_hs": primary_hs,
            "models": models,
            "consensus_hs": primary_clean or None,
            "confidence_adjustment": 0.0,
            "learning_note": "לא התקבלה תשובה ממודלים חיצוניים — אין אפשרות לאמת",
        }

    # Check agreement levels
    headings = {}  # heading -> list of model names
    six_digit = {}  # 6-digit -> list of model names

    for name, code in all_codes.items():
        if not code:
            continue
        h = code[:4] if len(code) >= 4 else code
        s = code[:6] if len(code) >= 6 else h
        headings.setdefault(h, []).append(name)
        six_digit.setdefault(s, []).append(name)

    total_voters = len(all_codes)  # primary + responding models

    # Tier 1: FULL_MATCH — all agree on 6+ digits
    for code, voters in six_digit.items():
        if len(voters) >= total_voters and total_voters >= 3:
            return {
                "tier": 1,
                "tier_name": "FULL_MATCH",
                "primary_hs": primary_hs,
                "models": models,
                "consensus_hs": code,
                "confidence_adjustment": +0.10,
                "learning_note": f"✅ כל 3 המודלים הסכימו: {_format_hs(code)}",
            }

    # Tier 2: HEADING_MATCH — all agree on 4-digit heading
    for heading, voters in headings.items():
        if len(voters) >= total_voters and total_voters >= 3:
            return {
                "tier": 2,
                "tier_name": "HEADING_MATCH",
                "primary_hs": primary_hs,
                "models": models,
                "consensus_hs": heading,
                "confidence_adjustment": +0.05,
                "learning_note": f"פרק {heading} — כל המודלים מסכימים על הפרק, שוני בתת-סיווג",
            }

    # Tier 3: MAJORITY — 2/3+ agree on heading
    for heading, voters in headings.items():
        if len(voters) >= 2 and len(voters) < total_voters:
            minority = [n for n in all_codes if n not in voters and all_codes[n]]
            minority_codes = {n: all_codes[n] for n in minority}
            return {
                "tier": 3,
                "tier_name": "MAJORITY",
                "primary_hs": primary_hs,
                "models": models,
                "consensus_hs": heading,
                "confidence_adjustment": -0.05,
                "majority": voters,
                "minority": minority_codes,
                "learning_note": (
                    f"⚠️ רוב ({len(voters)}/{total_voters}) הסכימו על פרק {heading}. "
                    f"מיעוט: {', '.join(f'{n}={c[:4]}' for n, c in minority_codes.items())}"
                ),
            }

    # Tier 4: DISAGREEMENT — all differ at heading level
    all_hs_display = ", ".join(f"{n}={_format_hs(c)}" for n, c in all_codes.items() if c)
    return {
        "tier": 4,
        "tier_name": "DISAGREEMENT",
        "primary_hs": primary_hs,
        "models": models,
        "consensus_hs": None,
        "confidence_adjustment": -0.15,
        "learning_note": f"❌ חילוקי דעות מלאים: {all_hs_display}. מומלץ בדיקה ידנית.",
    }


def _format_hs(code):
    """Format HS code for display: XXXX.XX.XXXX"""
    if not code:
        return "N/A"
    c = str(code).replace(".", "").replace("/", "")
    if len(c) >= 8:
        return f"{c[:4]}.{c[4:6]}.{c[6:]}"
    elif len(c) >= 6:
        return f"{c[:4]}.{c[4:6]}"
    return c


def _log_cross_check(db, result, item_description, origin_country, elapsed):
    """Store cross-check result in Firestore for learning feedback."""
    try:
        log_entry = {
            "timestamp": time.time(),
            "tier": result["tier"],
            "tier_name": result["tier_name"],
            "primary_hs": result["primary_hs"],
            "consensus_hs": result.get("consensus_hs"),
            "confidence_adjustment": result["confidence_adjustment"],
            "item_description": item_description[:200],
            "origin_country": origin_country or "",
            "elapsed_seconds": round(elapsed, 1),
            "model_codes": {
                name: m.get("hs_code", "")
                for name, m in result.get("models", {}).items()
            },
            "learning_note": result.get("learning_note", ""),
        }
        db.collection("cross_check_log").add(log_entry)
    except Exception as e:
        print(f"    [CROSS-CHECK] Firestore log error: {e}")


def get_cross_check_summary(results):
    """
    Build a Hebrew summary string from a list of cross-check results.
    Used in the classification report / email.
    """
    if not results:
        return ""

    lines = ["🔍 בדיקת צולבת (3 מודלים):"]
    for i, r in enumerate(results):
        tier = r.get("tier", 0)
        tier_name = r.get("tier_name", "")
        primary = _format_hs(r.get("primary_hs", ""))
        note = r.get("learning_note", "")

        tier_icons = {1: "✅", 2: "🟡", 3: "⚠️", 4: "❌"}
        icon = tier_icons.get(tier, "❓")

        lines.append(f"  {icon} פריט {i+1} (HS {primary}): {note}")

    # Overall summary
    tiers = [r.get("tier", 4) for r in results]
    avg_tier = sum(tiers) / len(tiers) if tiers else 4
    if avg_tier <= 1.5:
        lines.append("  סיכום: אמינות גבוהה — כל המודלים מסכימים.")
    elif avg_tier <= 2.5:
        lines.append("  סיכום: אמינות טובה — הסכמה ברמת הפרק.")
    elif avg_tier <= 3.5:
        lines.append("  סיכום: אמינות בינונית — רוב המודלים מסכימים.")
    else:
        lines.append("  סיכום: אמינות נמוכה — מומלץ בדיקה ידנית.")

    return "\n".join(lines)


def estimate_cross_check_cost(num_items=1):
    """Estimate cost of running cross-check on N items.
    Uses cheapest models: Claude Sonnet ($3/$15), Gemini Flash ($0.15/$0.60), GPT-4o-mini ($0.15/$0.60).
    ~500 input + ~200 output tokens per model per item.
    """
    per_item = (
        (500 * 3.0 + 200 * 15.0) / 1_000_000  # Claude Sonnet
        + (500 * 0.15 + 200 * 0.60) / 1_000_000  # Gemini Flash
        + (500 * 0.15 + 200 * 0.60) / 1_000_000  # GPT-4o-mini
    )
    return round(per_item * min(num_items, 3), 4)
