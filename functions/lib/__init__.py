"""
RCB Library - Robotic Customs Bot
==================================

All modules for customs document processing.

Modules:
- clarification_generator: Generate Hebrew request emails (Module 4)
- invoice_validator: Validate invoice fields per תקנות (Module 5)
- rcb_orchestrator: Integration layer connecting all modules (Module 6)
- incoterms_calculator: Calculate CIF values
- product_classifier: Classify products with HS codes
- document_tracker: Track document status
- classification_agents: AI classification agents
- librarian: Knowledge base management
- rcb_helpers: Utility functions
- pdf_creator: Generate PDF reports

Usage:
    from lib.rcb_orchestrator import create_orchestrator, quick_check
    from lib.clarification_generator import generate_missing_docs_request
    from lib.invoice_validator import validate_invoice
"""

# Module 4: Clarification Generator
try:
    from .clarification_generator import (
        create_generator,
        generate_missing_docs_request,
        generate_origin_request,
        ClarificationGenerator,
        ShipmentInfo,
        ClassificationDilemma,
        UrgencyLevel,
        RequestType,
    )
except ImportError:
    pass

# Module 5: Invoice Validator
try:
    from .invoice_validator import (
        validate_invoice,
        get_missing_fields_request,
        create_validator,
        InvoiceValidator,
        InvoiceField,
        ValidationResult,
    )
except ImportError:
    pass

# Module 6: Orchestrator
try:
    from .rcb_orchestrator import (
        create_orchestrator,
        process_shipment,
        quick_check,
        RCBOrchestrator,
        ProcessingStage,
        ProcessingResult,
    )
except ImportError:
    pass

# Other modules
try:
    from .incoterms_calculator import calculate_cif, IncotermsCalculator
except ImportError:
    pass

try:
    from .product_classifier import classify_product, ProductClassifier
except ImportError:
    pass

try:
    from .document_tracker import DocumentTracker, track_document
except ImportError:
    pass

try:
    from .classification_agents import run_full_classification, build_classification_email
except ImportError:
    pass

try:
    from .librarian import Librarian
except ImportError:
    pass

try:
    from .rcb_helpers import extract_text_from_attachments, build_rcb_reply
except ImportError:
    pass

__version__ = "0.6.0"
__all__ = [
    # Module 4
    "create_generator",
    "generate_missing_docs_request", 
    "generate_origin_request",
    "ClarificationGenerator",
    "ShipmentInfo",
    "UrgencyLevel",
    # Module 5
    "validate_invoice",
    "get_missing_fields_request",
    "InvoiceValidator",
    "InvoiceField",
    # Module 6
    "create_orchestrator",
    "process_shipment",
    "quick_check",
    "RCBOrchestrator",
    "ProcessingStage",
    # Others
    "calculate_cif",
    "classify_product",
    "DocumentTracker",
    "run_full_classification",
]
