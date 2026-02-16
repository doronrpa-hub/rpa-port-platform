"""
THE single function for all document reading in RCB.
Call ``read_document_reliable()`` instead of any direct extraction.

Pipeline:
1. Tries multiple extraction methods
2. Picks best result
3. Validates the extraction
4. If validation fails → tries harder (OCR, AI)
5. NEVER returns empty silently — always explains what was tried

Session 28C — Assignment 20.
NEW FILE — does not modify any existing code.
"""

import logging
from .smart_extractor import SmartExtractor
from .extraction_validator import ExtractionValidator
from .table_extractor import TableExtractor

logger = logging.getLogger("rcb.read_document")

_extractor = SmartExtractor()
_validator = ExtractionValidator()
_table_extractor = TableExtractor()


def read_document_reliable(
    file_bytes,
    filename,
    content_type,
    expected_type=None,
):
    """
    THE function to call for ALL document reading.

    Args:
        file_bytes: bytes — raw file content
        filename: str — original filename (e.g. "invoice.pdf")
        content_type: str — MIME type (e.g. "application/pdf")
        expected_type: str or None — "invoice", "bill_of_lading",
            "packing_list", "tariff_entry", "certificate_of_origin"

    Returns:
        dict with keys:
            text: str — extracted text
            tables: list — extracted tables (list of list-of-dicts)
            confidence: float — 0.0 to 1.0
            method_used: str — winning extraction method
            methods_tried: list[str] — all methods attempted
            valid: bool — passed validation
            warnings: list[str] — any issues found
            needs_review: bool — should a human look at this
    """
    # Step 1: Multi-method extraction
    result = _extractor.extract(file_bytes, filename, content_type)

    # Step 2: Validate
    validation = _validator.validate(result, expected_type)

    # Step 3: If failed, try harder
    if not validation.valid:
        ai_result = _extractor.try_ai_document_reading(
            file_bytes, filename, content_type,
        )
        if ai_result:
            ai_validation = _validator.validate(ai_result, expected_type)
            if (
                ai_validation.valid
                or ai_validation.confidence_adjustment > validation.confidence_adjustment
            ):
                result = ai_result
                validation = ai_validation

    # Step 4: Extract tables separately if the main pass missed them
    tables = result.tables or []
    if not tables and expected_type in ("invoice", "packing_list"):
        table_result = _table_extractor.extract_tables(file_bytes, content_type)
        tables = table_result.get("tables", [])
        if table_result.get("warnings"):
            result.warnings.extend(table_result["warnings"])

    # Step 5: Build output — NEVER return empty silently
    all_warnings = (result.warnings or []) + (validation.issues or [])
    adjusted_confidence = max(
        0.0, result.confidence + validation.confidence_adjustment,
    )

    output = {
        "text": result.text,
        "tables": tables,
        "confidence": round(adjusted_confidence, 3),
        "method_used": result.method,
        "methods_tried": getattr(result, "methods_tried", [result.method]),
        "valid": validation.valid,
        "warnings": all_warnings,
        "needs_review": (
            not validation.valid
            or result.needs_review
            or len(validation.issues) > 2
        ),
    }

    if not output["text"].strip():
        output["warnings"].append(
            f"FAILED: Could not extract text from '{filename}' ({content_type}). "
            f"Tried: {', '.join(output['methods_tried'])}. "
            f"Flagged for manual review."
        )
        output["needs_review"] = True

    logger.info(
        f"Extraction: {filename} | method={output['method_used']} "
        f"confidence={output['confidence']} valid={output['valid']} "
        f"chars={len(output['text'])} methods={output['methods_tried']}"
    )

    return output
