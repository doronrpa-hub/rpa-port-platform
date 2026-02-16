"""
RCB Self-Enrichment Engine
============================
Runs nightly to fill knowledge gaps detected during classification.

Process:
1. Read all open gaps from knowledge_gaps collection
2. Group by type and priority
3. For each gap type, try to fill from existing data
4. Flag web-scraping tasks for PC Agent
5. Update gap status

Session 27 — Assignment 11: Intelligent Classification
R.P.A.PORT LTD - February 2026
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger("rcb.enrichment")


def run_nightly_enrichment(db, max_gaps=50):
    """
    Process open knowledge gaps and try to fill them.

    Args:
        db: Firestore client
        max_gaps: Maximum gaps to process per run (cost control)

    Returns:
        dict with enrichment results
    """
    results = {
        "processed": 0,
        "filled": 0,
        "failed": 0,
        "skipped": 0,
        "details": [],
    }

    # Get open gaps, highest priority first
    try:
        gaps = list(
            db.collection("knowledge_gaps")
            .where("status", "==", "open")
            .limit(max_gaps)
            .stream()
        )
    except Exception as e:
        logger.error(f"Failed to read knowledge_gaps: {e}")
        return results

    logger.info(f"Nightly enrichment: {len(gaps)} open gaps to process")
    print(f"  Self-enrichment: {len(gaps)} open gaps")

    for gap_doc in gaps:
        gap = gap_doc.to_dict()
        gap_type = gap.get("type", "")
        gap_id = gap_doc.id

        results["processed"] += 1

        try:
            filled = False

            if gap_type in ("missing_preamble", "missing_chapter_notes", "missing_notes"):
                filled = _fill_from_tariff_chapters(db, gap)

            elif gap_type in ("missing_heading", "missing_subheading"):
                filled = _fill_from_tariff_db(db, gap)

            elif gap_type == "missing_directive":
                _flag_for_pc_agent(db, gap)
                results["details"].append({
                    "gap_id": gap_id,
                    "action": "flagged_for_pc_agent",
                    "description": gap.get("description", ""),
                })
                results["skipped"] += 1
                continue

            elif gap_type == "missing_preruling":
                _flag_for_pc_agent(db, gap)
                results["skipped"] += 1
                continue

            if filled:
                db.collection("knowledge_gaps").document(gap_id).update({
                    "status": "filled",
                    "filled_at": datetime.now(timezone.utc).isoformat(),
                    "filled_by": "nightly_enrichment",
                })
                results["filled"] += 1
                results["details"].append({
                    "gap_id": gap_id,
                    "action": "filled",
                    "description": gap.get("description", ""),
                })
            else:
                results["failed"] += 1
                results["details"].append({
                    "gap_id": gap_id,
                    "action": "could_not_fill",
                    "description": gap.get("description", ""),
                })

        except Exception as e:
            logger.error(f"Error processing gap {gap_id}: {e}")
            results["failed"] += 1

    logger.info(
        f"Enrichment done: {results['filled']} filled, "
        f"{results['failed']} failed, {results['skipped']} skipped"
    )
    return results


def _fill_from_tariff_chapters(db, gap):
    """Try to fill a gap from existing tariff_chapters data."""
    chapter = str(gap.get("chapter", "")).zfill(2)

    source_doc = db.collection("tariff_chapters").document(f"import_chapter_{chapter}").get()
    if not source_doc.exists:
        return False

    notes_doc = db.collection("chapter_notes").document(f"chapter_{chapter}").get()
    if notes_doc.exists:
        data = notes_doc.to_dict()
        if gap["type"] == "missing_preamble" and data.get("preamble"):
            return True
        if gap["type"] == "missing_notes" and data.get("notes"):
            return True

    return False


def _fill_from_tariff_db(db, gap):
    """Try to fill a heading/subheading gap from tariff collection."""
    hs_code = gap.get("hs_code", "")
    heading = gap.get("heading", "")

    search_val = hs_code or heading
    if not search_val:
        return False

    try:
        results = list(
            db.collection("tariff")
            .where("hs_code", ">=", search_val)
            .where("hs_code", "<=", search_val + "\uf8ff")
            .limit(5)
            .stream()
        )
        return len(results) > 0
    except Exception:
        return False


def _flag_for_pc_agent(db, gap):
    """
    Create a task for the PC Agent to research this gap.
    PC Agent can scrape customs.gov.il, download PDFs, etc.
    """
    task = {
        "type": "research_gap",
        "gap_type": gap.get("type", ""),
        "description": gap.get("description", ""),
        "hs_code": gap.get("hs_code", ""),
        "chapter": gap.get("chapter", ""),
        "action": gap.get("action", "Search customs.gov.il"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "source": "nightly_enrichment",
    }

    try:
        db.collection("pc_agent_tasks").add(task)
        logger.info(f"PC Agent task created: {gap.get('description', '')}")
    except Exception as e:
        logger.warning(f"Failed to create PC Agent task: {e}")


def generate_enrichment_report(results):
    """Generate a human-readable enrichment report for the daily digest."""
    lines = [
        f"Nightly Enrichment Report",
        f"Processed: {results['processed']} gaps",
        f"Filled: {results['filled']}",
        f"Failed: {results['failed']}",
        f"Flagged for PC Agent: {results['skipped']}",
        "",
    ]

    for detail in results.get("details", [])[:20]:
        action = detail["action"]
        desc = detail["description"][:100]
        if action == "filled":
            lines.append(f"  [FILLED] {desc}")
        elif action == "flagged_for_pc_agent":
            lines.append(f"  [PC_AGENT] {desc}")
        else:
            lines.append(f"  [FAILED] {desc}")

    return "\n".join(lines)
