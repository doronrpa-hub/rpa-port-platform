"""
Master Pipeline: ingest_source()
================================
One function that does everything:
  Download (raw bytes) → Extract → Structure → Store → Index → Validate

Call this from ANY agent (HTTP downloader, browser agent, AI-guided).

Session 27 — Assignment 14C
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger("rcb.pipeline")


# ═══════════════════════════════════════════
#  SOURCE TYPE → COLLECTION MAPPING
# ═══════════════════════════════════════════

SOURCE_TYPE_TO_COLLECTION = {
    "directive":            "classification_directives",
    "pre_ruling":           "pre_rulings",
    "customs_decision":     "customs_decisions",
    "court_precedent":      "court_precedents",
    "customs_ordinance":    "customs_ordinance",
    "procedure":            "customs_procedures",
    "fta":                  "fta_agreements",
    "tariff_uk":            "tariff_uk",
    "tariff_usa":           "tariff_usa",
    "tariff_eu":            "tariff_eu",
    "cbp_ruling":           "cbp_rulings",
    "bti_decision":         "bti_decisions",
    "chapter_note":         "chapter_notes",
}


def ingest_source(
    db,
    source_type,
    content_type="",
    raw_bytes=None,
    source_url="",
    filename="",
    metadata=None,
    get_secret_func=None,
    storage_path="",
):
    """
    Complete ingestion pipeline. Call from any agent.

    Args:
        db: Firestore client
        source_type: str — "directive", "pre_ruling", etc.
        content_type: str — MIME type ("application/pdf", "text/html", etc.)
        raw_bytes: bytes — file content (required)
        source_url: str — original URL
        filename: str — original filename
        metadata: dict — additional context
        get_secret_func: callable — for GEMINI_API_KEY
        storage_path: str — Cloud Storage path (if already stored)

    Returns:
        dict: {
            doc_id: str or None,
            collection: str,
            valid: bool,
            issues: list,
            extraction: dict (char_count, method, language),
            indexing: dict (librarian_indexed, keywords_indexed),
        }
    """
    metadata = metadata or {}
    now = datetime.now(timezone.utc).isoformat()

    result = {
        "doc_id": None,
        "collection": SOURCE_TYPE_TO_COLLECTION.get(source_type, f"pipeline_{source_type}"),
        "valid": False,
        "issues": [],
        "extraction": {},
        "indexing": {},
    }

    collection = result["collection"]

    # ── Step 1: Validate input ──
    if not raw_bytes:
        result["issues"].append("No raw_bytes provided")
        return result

    if source_type not in SOURCE_TYPE_TO_COLLECTION:
        result["issues"].append(f"Unknown source_type: {source_type}")
        # Still proceed with generic collection

    # ── Step 2: EXTRACT text ──
    from .extractor import extract_text

    extracted = extract_text(raw_bytes, content_type, filename)
    result["extraction"] = {
        "char_count": extracted.get("char_count", 0),
        "method": extracted.get("extraction_method", ""),
        "language": extracted.get("language", ""),
    }

    full_text = extracted.get("full_text", "")
    if not full_text or len(full_text.strip()) < 50:
        result["issues"].append(
            f"Extraction produced too little text ({len(full_text)} chars)"
        )
        _log_ingestion(db, source_type, source_url, result)
        return result

    # ── Step 3: STRUCTURE with LLM ──
    from .structurer import structure_with_llm

    structured = structure_with_llm(
        full_text=full_text,
        source_type=source_type,
        metadata=metadata,
        get_secret_func=get_secret_func,
    )

    # Merge: structured fields + full_text + source tracking
    doc_data = {**structured}
    doc_data["full_text"] = full_text[:100000]  # Cap at 100K for Firestore
    doc_data["source_url"] = source_url
    doc_data["storage_path"] = storage_path
    doc_data["filename"] = filename
    doc_data["downloaded_at"] = metadata.get("downloaded_at", now)
    doc_data["extracted_at"] = now
    doc_data["extraction_method"] = extracted.get("extraction_method", "")
    doc_data["language"] = extracted.get("language", "")
    doc_data["ingested_by"] = "data_pipeline"

    # Add tables if extracted
    tables = extracted.get("tables", [])
    if tables:
        doc_data["tables"] = tables[:100]  # Cap at 100 rows

    # ── Step 4: Generate document ID ──
    doc_id = _generate_doc_id(structured, source_type, source_url, filename)
    result["doc_id"] = doc_id

    # ── Step 5: STORE in Firestore ──
    try:
        db.collection(collection).document(doc_id).set(doc_data, merge=True)
    except Exception as e:
        result["issues"].append(f"Firestore write failed: {e}")
        _log_ingestion(db, source_type, source_url, result)
        return result

    # ── Step 6: INDEX ──
    from .indexer import index_document

    try:
        indexing_result = index_document(db, collection, doc_id, doc_data)
        result["indexing"] = indexing_result
    except Exception as e:
        result["issues"].append(f"Indexing failed: {e}")

    # ── Step 7: VALIDATE ──
    validation = _validate(doc_data, collection, doc_id)
    result["issues"].extend(validation.get("issues", []))
    result["valid"] = len(result["issues"]) == 0

    # ── Log ingestion ──
    _log_ingestion(db, source_type, source_url, result)

    if result["valid"]:
        logger.info(f"Ingested {source_type} → {collection}/{doc_id} ({extracted['char_count']} chars)")
        print(f"    Pipeline: {source_type} → {collection}/{doc_id}")
    else:
        logger.warning(f"Ingested with issues: {collection}/{doc_id}: {result['issues']}")

    return result


# ═══════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════

def _validate(doc_data, collection, doc_id):
    """Validate a stored document is usable by the brain."""
    issues = []

    full_text = doc_data.get("full_text", "")
    if not full_text or len(full_text.strip()) < 100:
        issues.append("full_text is empty or too short — extraction likely failed")

    key_terms = doc_data.get("key_terms", [])
    if not key_terms:
        issues.append("no key_terms — document won't be findable by search")

    # Check language consistency
    language = doc_data.get("language", "")
    source_url = doc_data.get("source_url", "")
    if language == "en" and any(d in source_url for d in [".gov.il", "customs.mof"]):
        # Israeli source should have Hebrew
        issues.append("Israeli source but no Hebrew detected — may be extraction issue")

    return {"valid": len(issues) == 0, "issues": issues}


# ═══════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════

def _generate_doc_id(structured, source_type, source_url, filename):
    """Generate a deterministic document ID."""
    import hashlib

    # Try to use structured ID fields
    for field in ("directive_id", "ruling_id", "decision_id", "case_id",
                  "section_number", "uk_code", "hts_code", "taric_code"):
        val = structured.get(field, "")
        if val:
            safe = val.replace("/", "_").replace(".", "_").replace(" ", "_")
            return f"{source_type}_{safe}"[:100]

    # Fallback: hash of URL or filename
    seed = source_url or filename or str(structured)[:200]
    hash_suffix = hashlib.md5(seed.encode()).hexdigest()[:10]
    return f"{source_type}_{hash_suffix}"


def _log_ingestion(db, source_type, source_url, result):
    """Log ingestion attempt for monitoring."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        db.collection("pipeline_ingestion_log").add({
            "source_type": source_type,
            "source_url": source_url[:500] if source_url else "",
            "doc_id": result.get("doc_id", ""),
            "collection": result.get("collection", ""),
            "valid": result.get("valid", False),
            "issues": result.get("issues", []),
            "char_count": result.get("extraction", {}).get("char_count", 0),
            "ingested_at": now,
        })
    except Exception:
        pass  # Non-critical
