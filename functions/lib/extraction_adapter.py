"""
Compatibility adapter: wraps the NEW smart extraction engine behind
the OLD function signatures.

When Sessions A/B are ready to switch, the change is ONE LINE in each caller:
    # OLD:
    from lib.rcb_helpers import extract_text_from_attachments
    # NEW:
    from lib.extraction_adapter import extract_text_from_attachments

All old callers keep working unchanged. Internally the new engine runs,
multi-method extraction + validation + quality logging happen automatically.

Session 28C — Assignment 20.
NEW FILE — does not modify any existing code.
"""

import base64
import io
import json
import re
import logging

logger = logging.getLogger("rcb.extraction_adapter")


# ═══════════════════════════════════════════════════════════
#  Drop-in replacement for rcb_helpers.extract_text_from_pdf_bytes
# ═══════════════════════════════════════════════════════════

def extract_text_from_pdf_bytes(pdf_bytes):
    """
    Drop-in replacement for ``rcb_helpers.extract_text_from_pdf_bytes``.

    Old signature:  extract_text_from_pdf_bytes(pdf_bytes) -> str
    New behaviour:  multi-method extraction + validation under the hood.
    """
    from .read_document import read_document_reliable

    result = read_document_reliable(
        file_bytes=pdf_bytes,
        filename="document.pdf",
        content_type="application/pdf",
    )

    text = result.get("text", "")

    # Apply the same post-processing the old code applied
    text = _cleanup_hebrew_text(text)
    text = _tag_document_structure(text)
    return text


# ═══════════════════════════════════════════════════════════
#  Drop-in replacement for rcb_helpers.extract_text_from_attachments
# ═══════════════════════════════════════════════════════════

def extract_text_from_attachments(attachments_data, email_body=None,
                                   gemini_key=None, anthropic_key=None):
    """
    Drop-in replacement for ``rcb_helpers.extract_text_from_attachments``.

    Old signature:  extract_text_from_attachments(attachments_data, email_body=None) -> str
    New behaviour:  each attachment goes through the new smart extractor.
    Session 40a: Added gemini_key/anthropic_key for dual AI vision analysis on images.

    The return value is the same concatenated string the old code produced,
    so all downstream code keeps working.
    """
    from .read_document import read_document_reliable

    all_text = []

    # Handle email body (same as old code)
    if email_body:
        email_body = _extract_urls_from_text(email_body)
        all_text.append(f"=== Email Body ===\n{email_body}")

    for att in attachments_data:
        name = att.get("name", "file")
        content_bytes = att.get("contentBytes", "")

        if not content_bytes:
            continue

        try:
            file_bytes = base64.b64decode(content_bytes)
        except Exception:
            continue

        content_type = _guess_content_type(name)

        logger.info(f"Extracting: {name} ({content_type})")

        result = read_document_reliable(
            file_bytes=file_bytes,
            filename=name,
            content_type=content_type,
        )

        text = result.get("text", "")

        if text:
            text = _cleanup_hebrew_text(text)
            text = _tag_document_structure(text)
            text = _extract_urls_from_text(text)
            all_text.append(f"=== {name} ===\n{text}")
        else:
            warnings = result.get("warnings", [])
            warning_str = "; ".join(warnings[:3]) if warnings else "unknown reason"
            all_text.append(
                f"=== {name} ===\n"
                f"[No text could be extracted — {warning_str}]"
            )

        # Log quality info
        conf = result.get("confidence", 0)
        method = result.get("method_used", "?")
        logger.info(
            f"  -> {name}: {len(text)} chars, method={method}, "
            f"confidence={conf}, valid={result.get('valid')}"
        )

        # Session 40a: Dual AI vision analysis for image attachments
        if _is_image_file(name) and (gemini_key or anthropic_key):
            try:
                from .image_analyzer import analyze_image
                vision = analyze_image(file_bytes, name, gemini_key, anthropic_key)
                if vision:
                    all_text.append(
                        f"=== {name} [AI Vision Analysis] ===\n"
                        f"{json.dumps(vision, ensure_ascii=False, indent=2)}"
                    )
                    logger.info(f"  -> {name}: AI Vision analysis added (confidence={vision.get('confidence', '?')})")
            except Exception as e:
                logger.warning(f"  -> {name}: AI Vision analysis failed: {e}")

        # Session 47: AI Vision fallback for scanned/low-text PDFs
        # When text extraction yields < 200 chars from a PDF, it is likely
        # a scanned image-based document. Render page 1 to PNG and run the
        # same dual AI vision analysis used for image attachments.
        if _is_pdf_file(name) and len(text) < 200 and (gemini_key or anthropic_key):
            try:
                _pdf_image_bytes = _render_pdf_first_page(file_bytes)
                if _pdf_image_bytes:
                    from .image_analyzer import analyze_image
                    vision = analyze_image(
                        _pdf_image_bytes, name.replace(".pdf", ".png"),
                        gemini_key, anthropic_key,
                    )
                    if vision:
                        all_text.append(
                            f"=== {name} [AI Vision Analysis \u2014 Scanned PDF] ===\n"
                            f"{json.dumps(vision, ensure_ascii=False, indent=2)}"
                        )
                        logger.info(f"  -> {name}: Scanned PDF AI Vision analysis added")
            except Exception as e:
                logger.warning(f"  -> {name}: Scanned PDF AI Vision failed: {e}")

    return "\n\n".join(all_text)


# ═══════════════════════════════════════════════════════════
#  Drop-in replacement for data_pipeline.extractor.extract_text
# ═══════════════════════════════════════════════════════════

def extract_text(file_bytes, content_type, filename=""):
    """
    Drop-in replacement for ``data_pipeline.extractor.extract_text``.

    Old returns: dict with full_text, tables, language, extraction_method, char_count
    New behaviour: same dict shape, powered by the smart extractor.
    """
    from .read_document import read_document_reliable

    result = read_document_reliable(
        file_bytes=file_bytes,
        filename=filename or "file",
        content_type=content_type,
    )

    # Map to the old dict format expected by callers
    text = result.get("text", "")
    return {
        "full_text": text[:200000],
        "tables": result.get("tables", []),
        "language": _detect_language(text),
        "extraction_method": result.get("method_used", "unknown"),
        "char_count": len(text),
        # New fields (ignored by old callers, useful for new code)
        "confidence": result.get("confidence", 0),
        "valid": result.get("valid", False),
        "warnings": result.get("warnings", []),
        "needs_review": result.get("needs_review", False),
        "methods_tried": result.get("methods_tried", []),
    }


# ═══════════════════════════════════════════════════════════
#  Post-processing helpers (copied from rcb_helpers.py patterns
#  to avoid importing the old module — keeps the adapter self-contained)
# ═══════════════════════════════════════════════════════════

def _cleanup_hebrew_text(text):
    """Fix common Hebrew/RTL extraction issues."""
    if not text:
        return text
    text = re.sub(r" {3,}", "  ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    replacements = {
        "חשבוו": "חשבון",
        'מע"ט': 'מע"מ',
        "עמיל מכם": "עמיל מכס",
    }
    for wrong, right in replacements.items():
        text = text.replace(wrong, right)
    return text


def _tag_document_structure(text):
    """Tag document sections to help AI classification agent."""
    if not text:
        return text

    tags = []

    inv_match = re.search(
        r"(?:invoice|inv|חשבונית|חשבון)[\s#:]*(\S+)", text, re.IGNORECASE
    )
    if inv_match:
        tags.append(f"[INVOICE_NUMBER: {inv_match.group(1)}]")

    dates = re.findall(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}", text)
    if dates:
        tags.append(f"[DATES_FOUND: {', '.join(dates[:5])}]")

    amounts = re.findall(
        r"(?:USD|EUR|ILS|NIS|\$|€|₪)\s*[\d,.]+", text, re.IGNORECASE
    )
    if not amounts:
        amounts = re.findall(
            r"[\d,.]+\s*(?:USD|EUR|ILS|NIS|\$|€|₪)", text, re.IGNORECASE
        )
    if amounts:
        tags.append(f"[AMOUNTS: {', '.join(amounts[:10])}]")

    hs_codes = re.findall(r"\b\d{4}[.\s]\d{2}(?:[.\s]\d{2,6})?\b", text)
    if hs_codes:
        tags.append(f"[HS_CODE_CANDIDATES: {', '.join(set(hs_codes[:10]))}]")

    bl_match = re.search(
        r"(?:B/?L|bill\s*of\s*lading|שטר\s*מטען)[\s#:]*(\S+)",
        text, re.IGNORECASE,
    )
    if bl_match:
        tags.append(f"[BL_NUMBER: {bl_match.group(1)}]")

    awb_match = re.search(
        r"(?:AWB|air\s*waybill)[\s#:]*(\S+)", text, re.IGNORECASE
    )
    if awb_match:
        tags.append(f"[AWB_NUMBER: {awb_match.group(1)}]")

    if tags:
        return "\n".join(tags) + "\n\n" + text
    return text


def _extract_urls_from_text(text):
    """Detect URLs in text and append them as tagged section."""
    if not text:
        return text
    urls = re.findall(r"https?://[^\s<>\"')\]]+", text)
    if urls:
        unique_urls = list(dict.fromkeys(urls))[:20]
        url_section = "\n[URLS_FOUND]\n" + "\n".join(unique_urls) + "\n[/URLS_FOUND]"
        return text + url_section
    return text


def _detect_language(text):
    """Simple language detection for the pipeline result dict."""
    if not text:
        return "unknown"
    hebrew = len(re.findall(r"[\u0590-\u05FF]", text[:5000]))
    english = len(re.findall(r"[a-zA-Z]", text[:5000]))
    if hebrew > english * 2:
        return "he"
    if english > hebrew * 2:
        return "en"
    if hebrew + english > 0:
        return "mixed"
    return "unknown"


def _is_image_file(name):
    """Check if filename is an image (Session 40a)."""
    if not name or "." not in name:
        return False
    ext = name.rsplit(".", 1)[-1].lower()
    return ext in {"png", "jpg", "jpeg", "tiff", "tif", "bmp", "gif", "webp"}


def _is_pdf_file(name):
    """Check if filename is a PDF (Session 47)."""
    if not name or "." not in name:
        return False
    return name.rsplit(".", 1)[-1].lower() == "pdf"


def _render_pdf_first_page(file_bytes):
    """Render first page of a PDF to PNG bytes for AI Vision analysis (Session 47).

    Uses PyMuPDF (fitz) at 2x zoom (~144 DPI) for good OCR quality
    while keeping the image size manageable for AI vision APIs.
    Returns PNG bytes or None on failure.
    """
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        if len(doc) == 0:
            doc.close()
            return None
        page = doc[0]
        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom = ~144 DPI
        pix = page.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        doc.close()
        return png_bytes
    except Exception:
        return None


def _guess_content_type(filename):
    """Guess MIME type from filename extension."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    mapping = {
        "pdf": "application/pdf",
        "html": "text/html",
        "htm": "text/html",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "bmp": "image/bmp",
        "tiff": "image/tiff",
        "tif": "image/tiff",
        "csv": "text/csv",
        "tsv": "text/tab-separated-values",
        "txt": "text/plain",
        "eml": "message/rfc822",
        "msg": "application/vnd.ms-outlook",
    }
    return mapping.get(ext, "application/octet-stream")
