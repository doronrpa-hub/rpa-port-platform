"""
RCB Cost Tracker — Budget-aware AI call management.
=====================================================
HARD CAP: $3.50 per overnight run.
Every AI call must go through this tracker.
When budget is exhausted, all streams stop gracefully.

Session 28 — Assignment 19: Overnight Brain Explosion
R.P.A.PORT LTD - February 2026
"""

import json
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger("rcb.cost_tracker")


class CostTracker:
    """
    Hard-capped budget tracker for overnight enrichment runs.
    Tracks Gemini Flash AI costs and Firestore operation costs.
    """

    BUDGET_LIMIT = 3.50  # USD — HARD CAP
    SAFETY_MARGIN = 0.20  # Stop at $3.30 to leave room for final writes

    # Gemini Flash pricing (per 1M tokens)
    GEMINI_FLASH_INPUT = 0.15    # $/1M input tokens
    GEMINI_FLASH_OUTPUT = 0.60   # $/1M output tokens

    # Firestore pricing
    FIRESTORE_READ = 0.06 / 100_000    # $0.06 per 100K reads
    FIRESTORE_WRITE = 0.18 / 100_000   # $0.18 per 100K writes

    # Image analysis pricing (dual Gemini Flash vision call)
    IMAGE_ANALYSIS_COST = 0.002  # ~$0.002 per dual AI call

    def __init__(self):
        self.total_spent = 0.0
        self.breakdown = {
            "gemini_input_tokens": 0,
            "gemini_output_tokens": 0,
            "gemini_calls": 0,
            "firestore_reads": 0,
            "firestore_writes": 0,
            "ai_cost": 0.0,
            "firestore_cost": 0.0,
            "image_analyses": 0,
            "image_cache_hits": 0,
            "image_cache_misses": 0,
            "image_cost": 0.0,
        }
        self._stopped = False

    @property
    def budget_remaining(self):
        return self.BUDGET_LIMIT - self.SAFETY_MARGIN - self.total_spent

    @property
    def is_over_budget(self):
        return self.budget_remaining <= 0

    def record_ai_call(self, input_tokens, output_tokens):
        """Record an AI call's token usage and cost."""
        cost = (input_tokens / 1_000_000 * self.GEMINI_FLASH_INPUT) + \
               (output_tokens / 1_000_000 * self.GEMINI_FLASH_OUTPUT)
        self.breakdown["gemini_input_tokens"] += input_tokens
        self.breakdown["gemini_output_tokens"] += output_tokens
        self.breakdown["gemini_calls"] += 1
        self.breakdown["ai_cost"] += cost
        self.total_spent += cost
        if self.is_over_budget:
            self._stopped = True
            logger.warning(f"BUDGET EXHAUSTED: ${self.total_spent:.4f} / ${self.BUDGET_LIMIT}")
            print(f"BUDGET EXHAUSTED: ${self.total_spent:.4f} / ${self.BUDGET_LIMIT}")
        return not self.is_over_budget

    def record_firestore_ops(self, reads=0, writes=0):
        """Record Firestore read/write operations."""
        cost = (reads * self.FIRESTORE_READ) + (writes * self.FIRESTORE_WRITE)
        self.breakdown["firestore_reads"] += reads
        self.breakdown["firestore_writes"] += writes
        self.breakdown["firestore_cost"] += cost
        self.total_spent += cost
        return not self.is_over_budget

    def log_image_analysis(self, cost=None, cache_hit=False):
        """Record an image analysis event.

        Args:
            cost: float — actual cost (default IMAGE_ANALYSIS_COST for misses, 0 for hits)
            cache_hit: bool — True if result came from image_patterns cache
        """
        self.breakdown["image_analyses"] += 1
        if cache_hit:
            self.breakdown["image_cache_hits"] += 1
            # Cache hits are free — no cost added
        else:
            self.breakdown["image_cache_misses"] += 1
            actual_cost = cost if cost is not None else self.IMAGE_ANALYSIS_COST
            self.breakdown["image_cost"] += actual_cost
            self.breakdown["ai_cost"] += actual_cost
            self.total_spent += actual_cost
            if self.is_over_budget:
                self._stopped = True
                logger.warning(f"BUDGET EXHAUSTED after image analysis: ${self.total_spent:.4f} / ${self.BUDGET_LIMIT}")
        return not self.is_over_budget

    def can_afford(self, estimated_input_tokens, estimated_output_tokens):
        """Check if we can afford an estimated AI call."""
        estimated_cost = (estimated_input_tokens / 1_000_000 * self.GEMINI_FLASH_INPUT) + \
                         (estimated_output_tokens / 1_000_000 * self.GEMINI_FLASH_OUTPUT)
        return estimated_cost <= self.budget_remaining

    def summary(self):
        """Return a summary dict of all spending."""
        return {
            "total_spent": round(self.total_spent, 4),
            "budget_limit": self.BUDGET_LIMIT,
            "budget_remaining": round(self.budget_remaining, 4),
            "stopped_by_budget": self._stopped,
            **self.breakdown,
        }


def call_gemini_tracked(gemini_key, prompt, tracker, system_prompt=None,
                        max_tokens=2000):
    """
    Budget-aware Gemini Flash wrapper.
    Returns parsed JSON dict, raw string, or None if over budget / call failed.

    Uses the same Gemini REST API as classification_agents.call_gemini().
    """
    if not gemini_key:
        return None

    # Pre-check budget
    estimated_input = len(prompt) // 3
    estimated_output = estimated_input // 2
    if not tracker.can_afford(estimated_input, estimated_output):
        logger.info(f"Skipping Gemini call — budget remaining: ${tracker.budget_remaining:.4f}")
        return None

    if tracker.is_over_budget:
        return None

    sys_prompt = system_prompt or "You are an expert Israeli customs classification AI assistant for RCB."

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
            headers={"content-type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": sys_prompt}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": 0.3,
                },
            },
            timeout=120,
        )

        if response.status_code != 200:
            logger.warning(f"Gemini API error: {response.status_code} - {response.text[:200]}")
            return None

        data = response.json()

        # Track actual token usage
        usage = data.get("usageMetadata", {})
        actual_input = usage.get("promptTokenCount", estimated_input)
        actual_output = usage.get("candidatesTokenCount", estimated_output // 2)
        tracker.record_ai_call(actual_input, actual_output)

        # Extract text
        candidates = data.get("candidates", [])
        if not candidates:
            return None

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return None

        text = parts[0].get("text", "").strip()

        # Strip markdown code fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # Try to parse as JSON
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return text

    except requests.Timeout:
        logger.warning("Gemini call timed out")
        return None
    except Exception as e:
        logger.warning(f"Gemini call error: {e}")
        return None
