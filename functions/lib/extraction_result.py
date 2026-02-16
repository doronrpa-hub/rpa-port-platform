"""
Extraction result data classes for RCB Smart Extraction Engine.

Session 28C — Assignment 20: Smart Multi-Method Document Extraction.
NEW FILE — does not modify any existing code.
"""

from dataclasses import dataclass, field


@dataclass
class ExtractionResult:
    """Result from a single extraction method."""
    text: str
    confidence: float              # 0.0 to 1.0
    method: str                    # e.g. "pdfplumber", "vision_ocr", "beautifulsoup"
    tables: list = field(default_factory=list)   # Extracted tables as list-of-dicts
    warnings: list = field(default_factory=list)
    is_empty: bool = False
    needs_review: bool = False
    methods_tried: list = field(default_factory=list)
    all_results_summary: list = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result from validating an extraction."""
    valid: bool
    issues: list = field(default_factory=list)
    confidence_adjustment: float = 0.0
