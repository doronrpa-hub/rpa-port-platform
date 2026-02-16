"""
RCB PC Agent Task Runner
=========================
Executes pending pc_agent_tasks from Cloud Functions.

Tasks that require browser automation are left for the local PC Agent.
Tasks that can be resolved via direct HTTP are executed here.

Two task types handled:
1. Download tasks (requires_browser=False) — direct HTTP GET
2. Research gap tasks (from nightly enrichment) — search local data + try HTTP

Session 27 — Assignment 14: PC Agent Task Runner
R.P.A.PORT LTD - February 2026
"""

import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger("rcb.pc_runner")

# Maximum time for HTTP requests (seconds)
HTTP_TIMEOUT = 30


def run_pending_tasks(db, max_tasks=10):
    """
    Process pending pc_agent_tasks that can be executed from Cloud Functions.

    Tasks requiring browser automation are skipped (left for local PC Agent).
    Tasks that can be resolved via direct HTTP are executed here.

    Args:
        db: Firestore client
        max_tasks: Maximum tasks to process per run

    Returns:
        dict with execution results
    """
    results = {
        "processed": 0,
        "executed": 0,
        "skipped_browser": 0,
        "failed": 0,
        "details": [],
    }

    try:
        tasks = list(
            db.collection("pc_agent_tasks")
            .where("status", "in", ["pending", "retry"])
            .limit(max_tasks)
            .stream()
        )
    except Exception as e:
        logger.error(f"Failed to read pc_agent_tasks: {e}")
        return results

    logger.info(f"PC Agent Runner: {len(tasks)} pending tasks")
    print(f"  PC Agent Runner: {len(tasks)} pending tasks")

    for task_doc in tasks:
        task = task_doc.to_dict()
        task_id = task_doc.id
        task_type = task.get("type", "")
        results["processed"] += 1

        # Check retry limit
        attempts = task.get("attempts", 0)
        max_attempts = task.get("max_attempts", 3)
        if attempts >= max_attempts:
            _mark_failed(db, task_id, "Max attempts reached")
            results["failed"] += 1
            results["details"].append({
                "task_id": task_id,
                "action": "failed",
                "reason": "Max attempts reached",
            })
            continue

        try:
            if task_type == "research_gap":
                success = _execute_research_gap(db, task_id, task)
            elif task.get("requires_browser", True):
                # Cannot execute browser tasks in Cloud Functions
                results["skipped_browser"] += 1
                results["details"].append({
                    "task_id": task_id,
                    "action": "skipped_browser",
                    "reason": "Requires browser automation",
                })
                continue
            else:
                success = _execute_download(db, task_id, task)

            if success:
                results["executed"] += 1
                results["details"].append({
                    "task_id": task_id,
                    "action": "executed",
                    "type": task_type or "download",
                })
            else:
                results["failed"] += 1
                results["details"].append({
                    "task_id": task_id,
                    "action": "failed",
                    "type": task_type or "download",
                })
        except Exception as e:
            logger.error(f"Error executing task {task_id}: {e}")
            _increment_attempts(db, task_id, str(e))
            results["failed"] += 1
            results["details"].append({
                "task_id": task_id,
                "action": "error",
                "reason": str(e)[:100],
            })

    logger.info(
        f"PC Agent Runner done: {results['executed']} executed, "
        f"{results['skipped_browser']} skipped (browser), "
        f"{results['failed']} failed"
    )
    return results


# ═══════════════════════════════════════════
#  DOWNLOAD EXECUTOR
# ═══════════════════════════════════════════

def _execute_download(db, task_id, task):
    """Execute a direct HTTP download task (requires_browser=False)."""
    url = task.get("url", "")
    if not url:
        _mark_failed(db, task_id, "No URL provided")
        return False

    try:
        db.collection("pc_agent_tasks").document(task_id).update({
            "status": "downloading",
            "attempts": task.get("attempts", 0) + 1,
            "last_attempt_at": datetime.now(timezone.utc).isoformat(),
        })

        response = requests.get(url, timeout=HTTP_TIMEOUT, headers={
            "User-Agent": "RCB-Bot/1.0 (customs classification system)",
        })

        if response.status_code != 200:
            _increment_attempts(db, task_id, f"HTTP {response.status_code}")
            return False

        content = response.text
        content_type = response.headers.get("Content-Type", "")
        content_length = len(response.content)

        preview = content[:2000] if content else ""

        now = datetime.now(timezone.utc).isoformat()
        db.collection("pc_agent_tasks").document(task_id).update({
            "status": "downloaded",
            "content_preview": preview,
            "content_type_header": content_type,
            "content_length": content_length,
            "downloaded_at": now,
            "downloaded_by": "cloud_function_runner",
        })

        # For text-based content, store in Firestore directly
        if any(t in content_type for t in ("text", "html", "json")):
            _store_text_content(db, task_id, task, content)

        # Auto-tag
        _auto_tag_task(db, task_id, task, preview)

        # Mark complete
        db.collection("pc_agent_tasks").document(task_id).update({
            "status": "complete",
            "completed_at": now,
        })

        print(f"    Downloaded: {task.get('source_name', task_id)[:50]}")
        return True

    except requests.Timeout:
        _increment_attempts(db, task_id, "Request timeout")
        return False
    except requests.ConnectionError as e:
        _increment_attempts(db, task_id, f"Connection error: {str(e)[:100]}")
        return False
    except Exception as e:
        _increment_attempts(db, task_id, str(e)[:200])
        return False


# ═══════════════════════════════════════════
#  RESEARCH GAP EXECUTOR
# ═══════════════════════════════════════════

def _execute_research_gap(db, task_id, task):
    """
    Execute a research gap task created by nightly enrichment.

    Tries to resolve the gap using:
    1. Local Firestore data (tariff_chapters, chapter_notes, knowledge_base)
    2. Direct HTTP to known public endpoints (shaarolami)

    If neither works, leaves the task pending for the local PC Agent.
    """
    gap_type = task.get("gap_type", "")
    hs_code = task.get("hs_code", "")
    chapter = task.get("chapter", "")

    try:
        db.collection("pc_agent_tasks").document(task_id).update({
            "status": "downloading",
            "attempts": task.get("attempts", 0) + 1,
            "last_attempt_at": datetime.now(timezone.utc).isoformat(),
        })

        filled = False

        if gap_type == "missing_directive":
            filled = _search_directive(db, task_id, hs_code, chapter)
        elif gap_type == "missing_preruling":
            filled = _search_preruling(db, task_id, hs_code, chapter)
        else:
            filled = _search_tariff_data(db, task_id, hs_code or chapter)

        now = datetime.now(timezone.utc).isoformat()

        if filled:
            db.collection("pc_agent_tasks").document(task_id).update({
                "status": "complete",
                "completed_at": now,
                "resolved_by": "cloud_function_runner",
            })
            _try_resolve_knowledge_gap(db, task)
            print(f"    Resolved gap: {task.get('description', '')[:50]}")
            return True
        else:
            # Could not resolve via HTTP — leave for local PC Agent
            db.collection("pc_agent_tasks").document(task_id).update({
                "status": "pending",
                "runner_note": "Could not resolve via HTTP, needs browser",
                "last_attempt_at": now,
            })
            return False

    except Exception as e:
        _increment_attempts(db, task_id, str(e)[:200])
        return False


# ═══════════════════════════════════════════
#  RESEARCH HELPERS
# ═══════════════════════════════════════════

def _search_directive(db, task_id, hs_code, chapter):
    """Search for a missing classification directive."""
    ch = str(chapter).zfill(2) if chapter else ""
    search_term = hs_code or ch
    if not search_term:
        return False

    # 1. Check local tariff_chapters for directive data
    if ch:
        try:
            doc = db.collection("tariff_chapters").document(f"import_chapter_{ch}").get()
            if doc.exists:
                data = doc.to_dict()
                if data.get("directives") or data.get("classification_notes"):
                    db.collection("pc_agent_tasks").document(task_id).update({
                        "content_preview": str(data.get("directives", data.get("classification_notes", "")))[:2000],
                        "resolved_source": "tariff_chapters",
                    })
                    return True
        except Exception:
            pass

    # 2. Check chapter_notes
    if ch:
        try:
            doc = db.collection("chapter_notes").document(f"chapter_{ch}").get()
            if doc.exists:
                data = doc.to_dict()
                if data.get("notes") or data.get("preamble"):
                    db.collection("pc_agent_tasks").document(task_id).update({
                        "content_preview": str(data.get("notes", data.get("preamble", "")))[:2000],
                        "resolved_source": "chapter_notes",
                    })
                    return True
        except Exception:
            pass

    # 3. Try shaarolami public endpoint
    try:
        url = (
            f"https://www.shaarolami-query.customs.mof.gov.il"
            f"/CustomspilotWeb/he/CustomsBook/Import/{search_term}"
        )
        resp = requests.get(url, timeout=HTTP_TIMEOUT, headers={
            "User-Agent": "RCB-Bot/1.0",
        })
        if resp.status_code == 200 and len(resp.text) > 500:
            db.collection("pc_agent_tasks").document(task_id).update({
                "content_preview": resp.text[:2000],
                "resolved_source": "shaarolami_http",
            })
            return True
    except Exception:
        pass

    return False


def _search_preruling(db, task_id, hs_code, chapter):
    """Search for a missing pre-ruling."""
    search_term = hs_code or str(chapter).zfill(2) if chapter else hs_code
    if not search_term:
        return False

    # Check knowledge_base for pre-ruling data
    try:
        results = list(
            db.collection("knowledge_base")
            .where("category", "==", "pre_rulings")
            .limit(20)
            .stream()
        )
        for doc in results:
            data = doc.to_dict()
            content = data.get("content", {})
            if isinstance(content, dict) and search_term in str(content):
                db.collection("pc_agent_tasks").document(task_id).update({
                    "content_preview": str(content)[:2000],
                    "resolved_source": "knowledge_base",
                })
                return True
    except Exception:
        pass

    return False


def _search_tariff_data(db, task_id, search_term):
    """Generic tariff search as fallback for unknown gap types."""
    if not search_term:
        return False

    try:
        results = list(
            db.collection("tariff")
            .where("hs_code", ">=", search_term)
            .where("hs_code", "<=", search_term + "\uf8ff")
            .limit(5)
            .stream()
        )
        if results:
            data = results[0].to_dict()
            db.collection("pc_agent_tasks").document(task_id).update({
                "content_preview": str(data)[:2000],
                "resolved_source": "tariff_db",
            })
            return True
    except Exception:
        pass

    return False


def _try_resolve_knowledge_gap(db, task):
    """Try to mark the corresponding knowledge_gap as filled."""
    gap_type = task.get("gap_type", "")
    hs_code = task.get("hs_code", "")
    description = task.get("description", "")

    if not (description or hs_code):
        return

    try:
        query = db.collection("knowledge_gaps").where("status", "==", "open")
        if gap_type:
            query = query.where("type", "==", gap_type)

        gaps = list(query.limit(20).stream())

        for gap_doc in gaps:
            gap = gap_doc.to_dict()
            if (hs_code and gap.get("hs_code") == hs_code) or \
               (description and gap.get("description") == description):
                db.collection("knowledge_gaps").document(gap_doc.id).update({
                    "status": "filled",
                    "filled_at": datetime.now(timezone.utc).isoformat(),
                    "filled_by": "pc_agent_runner",
                })
                return
    except Exception as e:
        logger.warning(f"Failed to resolve knowledge gap: {e}")


# ═══════════════════════════════════════════
#  STORAGE & TAGGING
# ═══════════════════════════════════════════

def _store_text_content(db, task_id, task, content):
    """Store fetched text content in a Firestore document."""
    try:
        doc_data = {
            "task_id": task_id,
            "source_name": task.get("source_name", ""),
            "content": content[:50000],
            "content_length": len(content),
            "tags": task.get("auto_tags", []),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "fetched_by": "pc_agent_runner",
        }
        db.collection("pc_agent_downloads").document(task_id).set(doc_data)
    except Exception as e:
        logger.warning(f"Failed to store content for {task_id}: {e}")


def _auto_tag_task(db, task_id, task, content_preview):
    """Auto-tag a completed task using librarian."""
    try:
        from .librarian_tags import auto_tag_document

        if content_preview:
            tags = auto_tag_document({"content": content_preview})
            existing_tags = task.get("auto_tags", [])
            all_tags = sorted(list(set(existing_tags + tags)))
            db.collection("pc_agent_tasks").document(task_id).update({
                "tags": all_tags,
            })
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Auto-tag error for {task_id}: {e}")


# ═══════════════════════════════════════════
#  STATUS HELPERS
# ═══════════════════════════════════════════

def _mark_failed(db, task_id, reason):
    """Mark a task as permanently failed."""
    try:
        db.collection("pc_agent_tasks").document(task_id).update({
            "status": "failed",
            "last_error": reason,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


def _increment_attempts(db, task_id, error_msg):
    """Increment attempt count and set retry or failed status."""
    try:
        task_ref = db.collection("pc_agent_tasks").document(task_id)
        task_doc = task_ref.get()

        if task_doc.exists:
            data = task_doc.to_dict()
            attempts = data.get("attempts", 0) + 1
            max_attempts = data.get("max_attempts", 3)
            status = "retry" if attempts < max_attempts else "failed"

            task_ref.update({
                "status": status,
                "attempts": attempts,
                "last_error": error_msg[:500],
                "last_attempt_at": datetime.now(timezone.utc).isoformat(),
            })
    except Exception:
        pass
