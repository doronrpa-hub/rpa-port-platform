"""
Dual AI Vision Analysis for Image Attachments.

Runs both Gemini Flash Vision and Claude Vision on image attachments,
compares outputs, and merges into structured customs-relevant data.

Session 40a — Image/Screenshot interpretation in email handler.
NEW FILE — does not modify any existing code.
"""

import base64
import json
import logging
import requests

logger = logging.getLogger("rcb.image_analyzer")

_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "tiff", "tif", "bmp", "gif", "webp"}

_VISION_PROMPT = """You are RCB customs assistant. Extract from this image:
- Product names or descriptions
- HS codes mentioned
- Invoice/BL/AWB numbers
- Quantities, weights, values
- Country of origin
- Any visible text relevant to customs/shipping
Return structured JSON only. Use this exact schema:
{
  "product_description": "string or null",
  "hs_codes": ["list of HS codes seen"],
  "document_numbers": {"invoice": "", "bl": "", "awb": ""},
  "quantities": [{"amount": "", "unit": ""}],
  "weights": [{"amount": "", "unit": ""}],
  "values": [{"amount": "", "currency": ""}],
  "country_of_origin": "string or null",
  "other_text": "any other customs-relevant text"
}
If a field is not visible, use null or empty list/string."""


_MIME_MAP = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "webp": "image/webp",
}


def is_image_attachment(name):
    """Check if filename has an image extension."""
    if not name or "." not in name:
        return False
    ext = name.rsplit(".", 1)[-1].lower()
    return ext in _IMAGE_EXTENSIONS


def _get_mime_type(filename):
    """Get MIME type from filename extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _MIME_MAP.get(ext, "application/octet-stream")


def analyze_image(file_bytes, filename, gemini_key=None, anthropic_key=None):
    """Run dual AI vision analysis on an image.

    Calls Gemini Flash Vision and Claude Vision independently,
    then merges results with confidence scoring.

    Args:
        file_bytes: Raw image bytes
        filename: Original filename (for MIME type detection)
        gemini_key: Google Gemini API key (optional)
        anthropic_key: Anthropic API key (optional)

    Returns:
        dict with merged analysis or {} if both fail
    """
    if not file_bytes:
        return {}

    if not gemini_key and not anthropic_key:
        return {}

    gemini_result = {}
    claude_result = {}

    if gemini_key:
        gemini_result = _analyze_with_gemini(file_bytes, filename, gemini_key)

    if anthropic_key:
        claude_result = _analyze_with_claude(file_bytes, filename, anthropic_key)

    if not gemini_result and not claude_result:
        return {}

    return _merge_results(gemini_result, claude_result)


def _analyze_with_gemini(file_bytes, filename, gemini_key):
    """Analyze image using Gemini Flash Vision API.

    Uses inlineData with base64 image in contents[].parts[].
    """
    try:
        b64_data = base64.b64encode(file_bytes).decode("utf-8")
        mime_type = _get_mime_type(filename)

        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
            headers={"content-type": "application/json"},
            json={
                "contents": [{
                    "parts": [
                        {"inlineData": {"mimeType": mime_type, "data": b64_data}},
                        {"text": _VISION_PROMPT},
                    ]
                }],
                "generationConfig": {
                    "maxOutputTokens": 2000,
                    "temperature": 0.2,
                },
            },
            timeout=60,
        )

        if response.status_code != 200:
            logger.warning(f"Gemini Vision API error: {response.status_code} - {response.text[:200]}")
            return {}

        data = response.json()
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not text:
            return {}

        return _parse_json_response(text, "Gemini")

    except Exception as e:
        logger.warning(f"Gemini Vision error for {filename}: {e}")
        return {}


def _analyze_with_claude(file_bytes, filename, anthropic_key):
    """Analyze image using Claude Vision API.

    Uses image content block with base64 source type.
    """
    try:
        b64_data = base64.b64encode(file_bytes).decode("utf-8")
        mime_type = _get_mime_type(filename)

        # Claude only supports specific media types for images
        supported_types = {"image/png", "image/jpeg", "image/gif", "image/webp"}
        if mime_type not in supported_types:
            # Convert TIFF/BMP to generic — Claude can't handle them directly
            logger.info(f"Skipping Claude Vision for {filename} (unsupported type: {mime_type})")
            return {}

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": anthropic_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": b64_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": _VISION_PROMPT,
                        },
                    ],
                }],
            },
            timeout=120,
        )

        if response.status_code != 200:
            logger.warning(f"Claude Vision API error: {response.status_code} - {response.text[:200]}")
            return {}

        data = response.json()
        text = data.get("content", [{}])[0].get("text", "")
        if not text:
            return {}

        return _parse_json_response(text, "Claude")

    except Exception as e:
        logger.warning(f"Claude Vision error for {filename}: {e}")
        return {}


def _parse_json_response(text, source_name):
    """Parse JSON from AI response text, handling markdown code blocks."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        logger.warning(f"{source_name} Vision returned non-JSON: {text[:200]}")
        return {}


def _merge_results(gemini_result, claude_result):
    """Compare and merge results from both AI models.

    Returns:
        dict with merged fields, confidence levels, and conflict info:
        {
            product_description, hs_codes, document_numbers,
            quantities, weights, values, country_of_origin, other_text,
            confidence, gemini_raw, claude_raw, conflicts, agreed_fields
        }
    """
    _FIELDS = [
        "product_description", "hs_codes", "document_numbers",
        "quantities", "weights", "values", "country_of_origin", "other_text",
    ]

    merged = {}
    conflicts = []
    agreed_fields = []

    for field in _FIELDS:
        g_val = gemini_result.get(field)
        c_val = claude_result.get(field)

        g_has = _has_value(g_val)
        c_has = _has_value(c_val)

        if g_has and c_has:
            if _values_agree(g_val, c_val, field):
                merged[field] = g_val  # Both agree — use either
                agreed_fields.append(field)
            else:
                # Contradiction — include both, mark conflict
                merged[field] = g_val  # Default to Gemini (faster/cheaper)
                conflicts.append({
                    "field": field,
                    "gemini": g_val,
                    "claude": c_val,
                })
        elif g_has:
            merged[field] = g_val
        elif c_has:
            merged[field] = c_val
        else:
            merged[field] = None

    # Overall confidence
    if conflicts:
        confidence = "LOW"
    elif len(agreed_fields) >= 3:
        confidence = "HIGH"
    elif agreed_fields or (gemini_result and claude_result):
        confidence = "MEDIUM"
    else:
        confidence = "MEDIUM"  # Single source

    merged["confidence"] = confidence
    merged["gemini_raw"] = gemini_result or None
    merged["claude_raw"] = claude_result or None
    merged["conflicts"] = conflicts
    merged["agreed_fields"] = agreed_fields

    return merged


def _has_value(val):
    """Check if a value is non-empty."""
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, (list, dict)):
        return bool(val)
    return True


def _values_agree(g_val, c_val, field):
    """Check if two values substantially agree."""
    # For string fields — check overlap
    if isinstance(g_val, str) and isinstance(c_val, str):
        g_lower = g_val.lower().strip()
        c_lower = c_val.lower().strip()
        if g_lower == c_lower:
            return True
        # Check significant word overlap
        g_words = set(g_lower.split())
        c_words = set(c_lower.split())
        if not g_words or not c_words:
            return g_lower == c_lower
        overlap = len(g_words & c_words) / max(len(g_words), len(c_words))
        return overlap >= 0.5

    # For list fields (hs_codes, quantities, etc.) — check any overlap
    if isinstance(g_val, list) and isinstance(c_val, list):
        if not g_val and not c_val:
            return True
        g_strs = {json.dumps(v, sort_keys=True) if isinstance(v, dict) else str(v) for v in g_val}
        c_strs = {json.dumps(v, sort_keys=True) if isinstance(v, dict) else str(v) for v in c_val}
        return bool(g_strs & c_strs)

    # For dict fields (document_numbers) — check key-value overlap
    if isinstance(g_val, dict) and isinstance(c_val, dict):
        shared_keys = set(g_val.keys()) & set(c_val.keys())
        if not shared_keys:
            return True  # No overlap means no contradiction
        agree_count = sum(1 for k in shared_keys if _has_value(g_val[k]) and _has_value(c_val[k]) and str(g_val[k]).strip() == str(c_val[k]).strip())
        filled_count = sum(1 for k in shared_keys if _has_value(g_val[k]) or _has_value(c_val[k]))
        return agree_count >= filled_count * 0.5 if filled_count else True

    return str(g_val) == str(c_val)
