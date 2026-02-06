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
- librarian: Knowledge base (Session 12: Central Brain)
- librarian_index: Document indexing & inventory
- librarian_tags: Auto-tagging system
- librarian_researcher: Enrichment & learning
- enrichment_agent: Background enrichment agent
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

# Librarian (Session 12: Enhanced Central Brain)
try:
    from .librarian import (
        full_knowledge_search,
        search_all_knowledge,
        search_extended_knowledge,
        build_classification_context,
        validate_hs_code,
        validate_and_correct_classifications,
        get_israeli_hs_format,
        normalize_hs_code,
        # Session 12: New functions
        find_by_hs_code,
        find_by_ministry,
        find_by_tags,
        smart_search,
        get_document_location,
        get_all_locations_for,
        scan_all_collections,
        rebuild_index,
        get_inventory_stats,
        get_enrichment_status,
        get_search_analytics,
    )
except ImportError:
    pass

# Librarian Index (Session 12: NEW)
try:
    from .librarian_index import (
        scan_all_collections,
        index_collection,
        rebuild_index,
        index_single_document,
        remove_from_index,
        get_inventory_stats,
    )
except ImportError:
    pass

# Librarian Tags (Session 12: NEW)
try:
    from .librarian_tags import (
        auto_tag_document,
        suggest_related_tags,
        get_tags_for_hs_code,
        add_tags,
        remove_tags,
        get_tag_stats,
        init_tag_definitions,
        DOCUMENT_TAGS,
        TAG_HIERARCHY,
    )
except ImportError:
    pass

# Librarian Researcher (Session 12: NEW)
try:
    from .librarian_researcher import (
        learn_from_classification,
        learn_from_correction,
        learn_from_email,
        check_for_updates,
        find_similar_classifications,
        get_enrichment_status,
        get_search_analytics,
        ENRICHMENT_TASKS,
    )
except ImportError:
    pass

# Enrichment Agent (Session 12: NEW)
try:
    from .enrichment_agent import (
        EnrichmentAgent,
        create_enrichment_agent,
    )
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

# PC Agent - Browser-based file downloads
from .pc_agent import (
    create_download_task,
    create_bulk_download_tasks,
    report_download_complete,
    report_upload_complete,
    report_task_failed,
    get_all_tasks_status as get_agent_status,
    get_download_queue_for_agent,
    get_agent_script,
)

# Knowledge Query Handler (Session 13: NEW)
try:
    from .knowledge_query import (
        detect_knowledge_query,
        handle_knowledge_query,
    )
except ImportError:
    pass

__version__ = '4.1.0'
__author__ = "RCB System"
