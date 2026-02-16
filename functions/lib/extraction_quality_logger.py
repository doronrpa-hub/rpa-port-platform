"""
Track extraction quality over time. Feeds into daily digest.

Session 28C — Assignment 20.
NEW FILE — does not modify any existing code.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger("rcb.extraction_quality")


def log_extraction(db, filename, content_type, result):
    """
    Call after every extraction to track quality.

    Args:
        db: Firestore client
        filename: str
        content_type: str
        result: dict returned by ``read_document_reliable()``
    """
    try:
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP

        db.collection("extraction_quality_log").add({
            "filename": filename,
            "content_type": content_type,
            "method_used": result.get("method_used"),
            "methods_tried": result.get("methods_tried", []),
            "confidence": result.get("confidence", 0),
            "text_length": len(result.get("text", "")),
            "valid": result.get("valid", False),
            "needs_review": result.get("needs_review", False),
            "warning_count": len(result.get("warnings", [])),
            "timestamp": SERVER_TIMESTAMP,
        })
    except Exception as e:
        # Never let logging break the pipeline
        logger.warning(f"Failed to log extraction quality: {e}")


def extraction_quality_report(db, hours=24):
    """
    Generate quality report for daily digest.

    Returns:
        dict with total_extractions, valid_rate, needs_review_count,
        methods_distribution, avg_confidence.
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    try:
        docs = list(
            db.collection("extraction_quality_log")
            .where("timestamp", ">", cutoff)
            .get()
        )
    except Exception as e:
        logger.error(f"Quality report query failed: {e}")
        return {"total": 0, "message": f"Query error: {e}"}

    total = len(docs)
    if total == 0:
        return {"total": 0, "message": "No extractions in period"}

    data = [d.to_dict() for d in docs]
    valid = sum(1 for d in data if d.get("valid"))
    review = sum(1 for d in data if d.get("needs_review"))

    from collections import Counter
    methods = Counter(d.get("method_used") for d in data)

    confidences = [d.get("confidence", 0) for d in data]
    avg_conf = round(sum(confidences) / total, 2) if total else 0

    return {
        "total_extractions": total,
        "valid_rate": f"{valid / total * 100:.0f}%",
        "needs_review_count": review,
        "methods_distribution": dict(methods.most_common()),
        "avg_confidence": avg_conf,
    }
