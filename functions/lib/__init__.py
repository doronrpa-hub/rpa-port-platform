"""
RCB Library Modules
===================
Complete library for RCB customs processing system.

Modules:
- clarification_generator (Module 4): Hebrew request emails
- invoice_validator (Module 5): Invoice field validation
- rcb_orchestrator (Module 6): Integration layer
- rcb_email_processor: Smart email processing
- classification_agents: AI classification
- librarian: Knowledge base
- document_tracker: Status tracking
- incoterms_calculator: CIF calculations
- product_classifier: HS code classification
- rcb_helpers: Utility functions
- pdf_creator: PDF generation
"""

# Module 4: Clarification Generator
try:
    from .clarification_generator import (
        generate_missing_docs_request,
        generate_classification_request,
        generate_cif_completion_request,
        generate_origin_verification_request,
        generate_origin_request,
        generate_generic_request,
        ClarificationRequest,
        DocumentType,
        UrgencyLevel,
        RequestType,
    )
except ImportError:
    pass

# Module 5: Invoice Validator
try:
    from .invoice_validator import (
        validate_invoice,
        quick_validate,
        InvoiceValidationResult,
        InvoiceField,
        FIELD_DEFINITIONS,
    )
except ImportError:
    pass

# Module 6: RCB Orchestrator
try:
    from .rcb_orchestrator import (
        RCBOrchestrator,
        create_orchestrator,
        process_and_respond,
        ShipmentStatus,
        ShipmentStage,
        ProcessingAction,
    )
except ImportError:
    pass

# Email Processor
try:
    from .rcb_email_processor import (
        RCBEmailProcessor,
        create_processor,
        build_ack_email,
        build_report_email,
    )
except ImportError:
    pass

# Classification Agents
try:
    from .classification_agents import (
        run_full_classification,
        build_classification_email,
        process_and_send_report,
    )
except ImportError:
    pass

# RCB Helpers
try:
    from .rcb_helpers import (
        helper_get_graph_token,
        helper_graph_messages,
        helper_graph_attachments,
        helper_graph_mark_read,
        helper_graph_send,
        to_hebrew_name,
        build_rcb_reply,
        get_rcb_secrets_internal,
        extract_text_from_attachments,
    )
except ImportError:
    pass

# Librarian
try:
    from .librarian import Librarian
except ImportError:
    pass

# Document Tracker
try:
    from .document_tracker import DocumentTracker
except ImportError:
    pass

# Incoterms Calculator
try:
    from .incoterms_calculator import calculate_cif
except ImportError:
    pass

# Product Classifier
try:
    from .product_classifier import classify_product
except ImportError:
    pass

# PDF Creator
try:
    from .pdf_creator import create_pdf
except ImportError:
    pass

__version__ = "2.0.0"
__author__ = "RCB System"
