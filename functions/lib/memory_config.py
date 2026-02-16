"""
Recommended Cloud Function memory settings for RCB.

Session 28C — Assignment 20.
NEW FILE — does not modify any existing code.
"""

MEMORY_RECOMMENDATIONS = {
    # Standard email processing
    "process-email": {
        "memory": "512MB",
        "timeout": "120s",
        "notes": "Handles single email + attachments",
    },
    # Overnight enrichment (Assignment 19)
    "overnight-enrichment": {
        "memory": "1024MB",
        "timeout": "540s",
        "notes": (
            "Batch processes collections. "
            "If not enough time, split into phases or use Cloud Run."
        ),
    },
    # Heavy document processing
    "document-extraction": {
        "memory": "1024MB",
        "timeout": "300s",
        "notes": "OCR and multi-method extraction need RAM",
    },
    # Cloud Run alternative for long jobs
    "cloud-run-batch": {
        "memory": "2048MB",
        "timeout": "3600s",
        "notes": "For jobs that exceed 9-minute Cloud Functions limit",
    },
}
