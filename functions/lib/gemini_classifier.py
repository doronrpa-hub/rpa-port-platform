"""
gemini_classifier.py — Bridge Module
=====================================
Agents (pupil, tracker, brain_commander) call:  _call_gemini(prompt)
classification_agents.py has:  call_gemini(gemini_key, system_prompt, user_prompt)

This module bridges the gap:
  1. Gets the Gemini API key from Secret Manager (cached after first call)
  2. Splits the single prompt into system_prompt + user_prompt
  3. Delegates to classification_agents.call_gemini()

No logic duplication — just signature bridging.
"""

from lib.classification_agents import call_gemini

# Module-level key cache (loaded once per Cloud Function cold start)
_gemini_key_cache = None


def _get_gemini_key():
    """Get Gemini API key from Secret Manager, cached after first call."""
    global _gemini_key_cache
    if _gemini_key_cache:
        return _gemini_key_cache

    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        secret_path = "projects/rpa-port-customs/secrets/GEMINI_API_KEY/versions/latest"
        response = client.access_secret_version(request={"name": secret_path})
        _gemini_key_cache = response.payload.data.decode("UTF-8")
        return _gemini_key_cache
    except Exception as e:
        print(f"gemini_classifier: Secret Manager error: {e}")
        # Fallback: check environment variable
        import os
        key = os.environ.get("GEMINI_API_KEY")
        if key:
            _gemini_key_cache = key
            return key
        print("gemini_classifier: No GEMINI_API_KEY found")
        return None


def _call_gemini(prompt, max_tokens=2000):
    """
    Simple Gemini call used by pupil.py, tracker.py, brain_commander.py.

    Args:
        prompt: Single string prompt (agents build the full prompt themselves)
        max_tokens: Max response tokens (default 2000)

    Returns:
        str: Gemini response text, or None on failure
    """
    key = _get_gemini_key()
    if not key:
        print("gemini_classifier: _call_gemini skipped — no API key")
        return None

    # Agents embed all context in one prompt string.
    # Split into a minimal system instruction + the prompt as user content.
    system_prompt = "You are an expert AI assistant for RCB, an Israeli customs brokerage system."

    result = call_gemini(key, system_prompt, prompt, max_tokens=max_tokens)
    return result
