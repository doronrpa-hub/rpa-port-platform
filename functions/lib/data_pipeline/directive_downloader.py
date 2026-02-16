"""
Step 0: DOWNLOAD — Scrape classification directives from Shaarolami customs site.

Downloads all ~217 Israeli Customs classification directives (הנחיות סיווג)
from the official Shaarolami website and feeds them through the existing
ingest_source() pipeline.

Source URL pattern:
  https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb/he/CustomsBook/
  Import/ClassificationGuidanceDetails?customsItemId=0&classificationGuidanceId={id}

IDs range 1..~217 with some gaps (empty pages).

Assignment 17
"""

import logging
import re
import time

import requests

from .pipeline import ingest_source

logger = logging.getLogger("rcb.pipeline.directive_downloader")

BASE_URL = (
    "https://shaarolami-query.customs.mof.gov.il/CustomspilotWeb/he/CustomsBook/"
    "Import/ClassificationGuidanceDetails?customsItemId=0&classificationGuidanceId={id}"
)

# Markers that indicate the page contains a real directive (not an empty template)
_DIRECTIVE_MARKERS = [
    "מספר הנחיה",       # "Directive number"
    "תאריך פתיחה",      # "Opening date"
]

_DIRECTIVE_ID_PATTERN = re.compile(r"\d{1,3}/\d{2}")


def _is_valid_directive_page(html_text):
    """
    Check if HTML contains actual directive content vs empty template.

    A valid page has Hebrew directive markers AND a directive ID pattern (e.g. 001/02).

    Args:
        html_text: str — decoded HTML content

    Returns:
        bool — True if page contains real directive content
    """
    if not html_text or len(html_text) < 200:
        return False

    has_marker = any(marker in html_text for marker in _DIRECTIVE_MARKERS)
    has_id = bool(_DIRECTIVE_ID_PATTERN.search(html_text))

    return has_marker and has_id


def _get_existing_source_urls(db):
    """
    Fetch all source_url values already in classification_directives collection.

    Returns:
        set of str — existing source URLs
    """
    existing = set()
    try:
        docs = db.collection("classification_directives").select(["source_url"]).stream()
        for doc in docs:
            url = doc.to_dict().get("source_url", "")
            if url:
                existing.add(url)
    except Exception as e:
        logger.warning(f"Could not fetch existing directives: {e}")
    return existing


def download_single_directive(db, guidance_id, get_secret_func):
    """
    Download one directive by classificationGuidanceId.

    Args:
        db: Firestore client
        guidance_id: int — the classificationGuidanceId
        get_secret_func: callable — for Gemini API key

    Returns:
        dict: {status: "downloaded"|"skipped_empty"|"skipped_exists"|"failed",
               url: str, doc_id: str|None, error: str|None}
    """
    url = BASE_URL.format(id=guidance_id)
    result = {"status": "failed", "url": url, "doc_id": None, "error": None}

    # Check if already exists
    existing = _get_existing_source_urls(db)
    if url in existing:
        result["status"] = "skipped_exists"
        return result

    # Download
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        result["error"] = str(e)
        return result

    html_text = resp.text

    # Validate content
    if not _is_valid_directive_page(html_text):
        result["status"] = "skipped_empty"
        return result

    # Feed through pipeline
    try:
        html_bytes = resp.content
        filename = f"directive_guidance_{guidance_id}.html"
        pipeline_result = ingest_source(
            db=db,
            source_type="directive",
            content_type="text/html",
            raw_bytes=html_bytes,
            source_url=url,
            filename=filename,
            get_secret_func=get_secret_func,
        )
        result["doc_id"] = pipeline_result.get("doc_id")
        if pipeline_result.get("doc_id"):
            result["status"] = "downloaded"
        else:
            result["status"] = "failed"
            result["error"] = "; ".join(pipeline_result.get("issues", []))
    except Exception as e:
        result["error"] = str(e)

    return result


def download_all_directives(db, get_secret_func, max_id=250, delay=1.0):
    """
    Download all classification directives from Shaarolami.

    Iterates classificationGuidanceId from 1 to max_id, skips already-ingested
    directives, validates page content, and feeds valid ones through
    ingest_source().

    Args:
        db: Firestore client
        get_secret_func: callable — for Gemini API key
        max_id: int — highest ID to try (default 250)
        delay: float — seconds between requests (rate limiting)

    Returns:
        dict: {downloaded: int, skipped_empty: int, skipped_exists: int,
               failed: int, errors: list[str]}
    """
    stats = {
        "downloaded": 0,
        "skipped_empty": 0,
        "skipped_exists": 0,
        "failed": 0,
        "errors": [],
    }

    # Pre-fetch existing URLs for deduplication
    existing_urls = _get_existing_source_urls(db)
    logger.info(f"Found {len(existing_urls)} existing directives, scanning IDs 1..{max_id}")

    for guidance_id in range(1, max_id + 1):
        url = BASE_URL.format(id=guidance_id)

        # Skip if already ingested
        if url in existing_urls:
            stats["skipped_exists"] += 1
            continue

        # Download
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append(f"ID {guidance_id}: HTTP error — {e}")
            time.sleep(delay)
            continue

        html_text = resp.text

        # Validate
        if not _is_valid_directive_page(html_text):
            stats["skipped_empty"] += 1
            time.sleep(delay)
            continue

        # Ingest
        try:
            html_bytes = resp.content
            filename = f"directive_guidance_{guidance_id}.html"
            pipeline_result = ingest_source(
                db=db,
                source_type="directive",
                content_type="text/html",
                raw_bytes=html_bytes,
                source_url=url,
                filename=filename,
                get_secret_func=get_secret_func,
            )
            if pipeline_result.get("doc_id"):
                stats["downloaded"] += 1
            else:
                stats["failed"] += 1
                issues = "; ".join(pipeline_result.get("issues", []))
                stats["errors"].append(f"ID {guidance_id}: pipeline — {issues}")
        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append(f"ID {guidance_id}: ingest error — {e}")

        # Rate limit — be polite to government server
        time.sleep(delay)

    logger.info(
        f"Directive download complete: {stats['downloaded']} downloaded, "
        f"{stats['skipped_exists']} already existed, "
        f"{stats['skipped_empty']} empty, {stats['failed']} failed"
    )
    return stats
