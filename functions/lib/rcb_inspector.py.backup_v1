"""
RCB Inspector Agent v1.0.0
==========================
Autonomous System Health, Intelligence & Session Planning Agent.

Two brains:
  - Rules handle known patterns (fast, cheap, deterministic)
  - Claude handles new discoveries (smart, creative)

Phases:
  1. Database Inspector  — Consult Librarian, audit all collections
  2. Process Inspector   — Check for clashes, race conditions, orphans
  3. Flow Inspector      — Verify email→detection→processing→reply flows
  4. Monitor Inspector   — Verify monitors, schedulers, self-healers
  5. Auto-Fixer          — Apply known fixes automatically
  6. Claude Consultant   — Ask Claude about NEW problems only
  7. Session Planner     — Generate next session mission files
  8. Report Generator    — Produce health report + daily email

Cloud Functions:
  - rcb_inspector        — HTTP trigger (manual run)
  - rcb_inspector_daily  — Scheduler: every day 15:00 Asia/Jerusalem

Author: RCB System
Session: 14.01
"""

import json
import hashlib
import traceback
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════
#  IMPORTS FROM EXISTING LIB MODULES
# ═══════════════════════════════════════════════════════════════════════════

try:
    from .librarian_tags import (
        DOCUMENT_TAGS,
        TAG_HIERARCHY,
        TAG_KEYWORDS,
        CUSTOMS_HANDBOOK_CHAPTERS,
        PC_AGENT_DOWNLOAD_SOURCES,
    )
except ImportError:
    from librarian_tags import (
        DOCUMENT_TAGS,
        TAG_HIERARCHY,
        TAG_KEYWORDS,
        CUSTOMS_HANDBOOK_CHAPTERS,
        PC_AGENT_DOWNLOAD_SOURCES,
    )

try:
    from .rcb_helpers import (
        helper_get_graph_token,
        helper_graph_send,
        get_rcb_secrets_internal,
    )
except ImportError:
    from rcb_helpers import (
        helper_get_graph_token,
        helper_graph_send,
        get_rcb_secrets_internal,
    )

try:
    from .classification_agents import call_claude
except ImportError:
    try:
        from classification_agents import call_claude
    except ImportError:
        call_claude = None  # Will skip Claude consultation if unavailable


# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

VERSION = "1.0.0"
MASTER_EMAIL = "doron@rpa-port.co.il"
RCB_EMAIL_DEFAULT = "rcb@rpa-port.co.il"

# Collections the inspector audits
EXPECTED_COLLECTIONS = {
    "classifications":          {"type": "core", "desc": "Active classifications"},
    "knowledge_base":           {"type": "core", "desc": "Learned knowledge (suppliers, products, web)"},
    "classification_knowledge": {"type": "core", "desc": "Past classification decisions"},
    "knowledge_queries":        {"type": "core", "desc": "Knowledge query logs (Session 13)"},
    "rcb_processed":            {"type": "operational", "desc": "Processed email tracking"},
    "rcb_test_reports":         {"type": "operational", "desc": "Self-test results"},
    "rcb_classifications":      {"type": "core", "desc": "Classification results"},
    "sessions_backup":          {"type": "meta", "desc": "Session backups"},
    "librarian_index":          {"type": "core", "desc": "Search index"},
    "librarian_search_log":     {"type": "analytics", "desc": "Search analytics"},
    "librarian_enrichment_log": {"type": "analytics", "desc": "Enrichment task history"},
    "tag_definitions":          {"type": "meta", "desc": "Tag metadata"},
    "enrichment_tasks":         {"type": "operational", "desc": "Scheduled enrichment"},
    "download_tasks":           {"type": "operational", "desc": "PC Agent downloads"},
    "system_status":            {"type": "operational", "desc": "System health status"},
    "monitor_errors":           {"type": "operational", "desc": "Monitor error log"},
    "tariff_chapters":          {"type": "data", "desc": "Tariff chapter data"},
    "tariff":                   {"type": "data", "desc": "Tariff line items"},
    "hs_code_index":            {"type": "data", "desc": "HS code index"},
    "ministry_index":           {"type": "data", "desc": "Ministry requirements"},
    "regulatory":               {"type": "data", "desc": "Regulatory data"},
    "regulatory_approvals":     {"type": "data", "desc": "Regulatory approvals"},
    "rcb_inspector_reports":    {"type": "meta", "desc": "Inspector history (self)"},
    "session_missions":         {"type": "meta", "desc": "Generated mission files"},
}

# Known schedulers and their expected intervals
KNOWN_SCHEDULERS = {
    "rcb_check_email":           {"schedule": "every 2 minutes", "max_gap_minutes": 5},
    "check_email_scheduled":     {"schedule": "every 5 minutes", "max_gap_minutes": 10},
    "monitor_agent":             {"schedule": "every 5 minutes", "max_gap_minutes": 10},
    "rcb_health_check":          {"schedule": "every 1 hours", "max_gap_minutes": 75},
    "enrich_knowledge":          {"schedule": "every 1 hours", "max_gap_minutes": 75},
    "rcb_retry_failed":          {"schedule": "every 6 hours", "max_gap_minutes": 390},
    "rcb_cleanup_old_processed": {"schedule": "every 24 hours", "max_gap_minutes": 1500},
    "monitor_fix_scheduled":     {"schedule": "every 15 minutes", "max_gap_minutes": 20},
    "rcb_inspector_daily":       {"schedule": "every day 15:00 Jerusalem", "max_gap_minutes": 1500},
}

# Priority scoring for session planning
PRIORITY_RULES = {
    "CRITICAL_fix":      100,
    "flow_broken":        90,
    "data_integrity":     80,
    "race_condition":     70,
    "performance_issue":  60,
    "new_capability":     40,
    "optimization":       20,
}


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 0: CONSULT THE LIBRARIAN
# ═══════════════════════════════════════════════════════════════════════════

def consult_librarian(db) -> Dict[str, Any]:
    """
    MANDATORY FIRST STEP — mirrors SESSION_PROTOCOL rule.
    Gather system state before any inspection.
    """
    print("📚 Phase 0: Consulting the Librarian...")
    state = {
        "version": VERSION,
        "consulted_at": datetime.now(timezone.utc).isoformat(),
        "tag_count": len(DOCUMENT_TAGS),
        "hierarchy_groups": len(TAG_HIERARCHY),
        "keyword_rules": len(TAG_KEYWORDS),
        "handbook_chapters": len(CUSTOMS_HANDBOOK_CHAPTERS),
        "pc_agent_sources": len(PC_AGENT_DOWNLOAD_SOURCES),
        "collections": {},
        "issues": [],
    }

    # Quick collection count
    for coll_name, meta in EXPECTED_COLLECTIONS.items():
        try:
            docs = list(db.collection(coll_name).limit(1).stream())
            state["collections"][coll_name] = {
                "exists": True,
                "type": meta["type"],
                "has_data": len(docs) > 0,
            }
        except Exception as e:
            state["collections"][coll_name] = {
                "exists": False,
                "type": meta["type"],
                "error": str(e),
            }
            state["issues"].append(f"Collection '{coll_name}' inaccessible: {e}")

    missing = [c for c, v in state["collections"].items() if not v.get("exists")]
    if missing:
        state["issues"].append(f"Missing collections: {missing}")

    print(f"  ✅ Librarian consulted: {len(state['collections'])} collections checked, "
          f"{state['tag_count']} tags, {len(state['issues'])} issues")
    return state


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 1: DATABASE INSPECTOR
# ═══════════════════════════════════════════════════════════════════════════

def inspect_database(db, librarian_state: Dict) -> Dict[str, Any]:
    """Phase 1: Deep audit of all Firestore collections."""
    print("🗄️ Phase 1: Database Inspection...")
    results = {
        "collection_stats": {},
        "tag_integrity": {},
        "knowledge_health": {},
        "issues": [],
        "warnings": [],
    }

    # ── 1A: Collection Inventory ──
    print("  📊 1A: Collection inventory...")
    total_docs = 0
    for coll_name in EXPECTED_COLLECTIONS:
        try:
            stats = _audit_collection(db, coll_name)
            results["collection_stats"][coll_name] = stats
            total_docs += stats.get("count", 0)
        except Exception as e:
            results["collection_stats"][coll_name] = {"error": str(e), "count": 0}
            results["issues"].append(f"Failed to audit {coll_name}: {e}")

    results["total_documents"] = total_docs
    print(f"  📊 Total documents: {total_docs}")

    # ── 1B: Tag Integrity Audit ──
    print("  🏷️ 1B: Tag integrity audit...")
    results["tag_integrity"] = _audit_tag_integrity()

    if results["tag_integrity"].get("broken_references"):
        results["issues"].append(
            f"Broken tag references: {results['tag_integrity']['broken_references']}"
        )

    # ── 1C: Knowledge Health ──
    print("  🧠 1C: Knowledge health...")
    results["knowledge_health"] = _audit_knowledge_health(db)

    print(f"  ✅ Phase 1 complete: {len(results['issues'])} issues, "
          f"{len(results['warnings'])} warnings")
    return results


def _audit_collection(db, coll_name: str, sample_limit: int = 200) -> Dict:
    """Audit a single Firestore collection."""
    stats = {"count": 0, "oldest": None, "newest": None, "sample_fields": set()}

    try:
        docs = list(db.collection(coll_name).limit(sample_limit).stream())
        stats["count"] = len(docs)

        timestamps = []
        for doc in docs:
            data = doc.to_dict()
            stats["sample_fields"].update(data.keys())

            # Look for timestamp fields
            for ts_field in ["timestamp", "created_at", "processed_at", "updated_at", "date"]:
                ts = data.get(ts_field)
                if ts and hasattr(ts, 'isoformat'):
                    timestamps.append(ts)

        if timestamps:
            stats["oldest"] = min(timestamps).isoformat()
            stats["newest"] = max(timestamps).isoformat()

        stats["sample_fields"] = list(stats["sample_fields"])[:20]  # Limit for report

        # Check if we hit the limit (collection may be larger)
        if stats["count"] >= sample_limit:
            stats["count_note"] = f">={sample_limit} (sampled)"

    except Exception as e:
        stats["error"] = str(e)

    return stats


def _audit_tag_integrity() -> Dict:
    """Verify tag system integrity (pure rule-based, no DB needed)."""
    results = {
        "total_tags": len(DOCUMENT_TAGS),
        "hierarchy_groups": len(TAG_HIERARCHY),
        "keyword_rules": len(TAG_KEYWORDS),
        "broken_references": [],
        "orphan_tags": [],
        "handbook_coverage": {},
        "pass": True,
    }

    # Check 1: Every TAG_HIERARCHY reference exists in DOCUMENT_TAGS
    all_hierarchy_tags = set()
    for group, tags in TAG_HIERARCHY.items():
        for tag in tags:
            all_hierarchy_tags.add(tag)
            if tag not in DOCUMENT_TAGS:
                results["broken_references"].append(
                    f"TAG_HIERARCHY[{group}] → '{tag}' not in DOCUMENT_TAGS"
                )

    # Check 2: Every TAG_KEYWORDS entry maps to a valid tag
    for tag in TAG_KEYWORDS:
        if tag not in DOCUMENT_TAGS:
            results["broken_references"].append(
                f"TAG_KEYWORDS['{tag}'] not in DOCUMENT_TAGS"
            )

    # Check 3: Every CUSTOMS_HANDBOOK_CHAPTERS tag exists in DOCUMENT_TAGS
    for ch_key, ch_data in CUSTOMS_HANDBOOK_CHAPTERS.items():
        tag = ch_data.get("tag", "")
        if tag and tag not in DOCUMENT_TAGS:
            results["broken_references"].append(
                f"CUSTOMS_HANDBOOK_CHAPTERS[{ch_key}] → '{tag}' not in DOCUMENT_TAGS"
            )
        # Also check sub_chapters
        for sub_key, sub_data in ch_data.get("sub_chapters", {}).items():
            sub_tag = sub_data.get("tag", "")
            if sub_tag and sub_tag not in DOCUMENT_TAGS:
                results["broken_references"].append(
                    f"CUSTOMS_HANDBOOK_CHAPTERS[{ch_key}].sub[{sub_key}] → "
                    f"'{sub_tag}' not in DOCUMENT_TAGS"
                )

    # Check 4: Every PC_AGENT_DOWNLOAD_SOURCES auto_tag exists in DOCUMENT_TAGS
    for source_key, source_data in PC_AGENT_DOWNLOAD_SOURCES.items():
        for tag in source_data.get("auto_tags", []):
            if tag not in DOCUMENT_TAGS:
                results["broken_references"].append(
                    f"PC_AGENT_DOWNLOAD_SOURCES[{source_key}].auto_tags → "
                    f"'{tag}' not in DOCUMENT_TAGS"
                )

    # Check 5: Orphan tags (in DOCUMENT_TAGS but never referenced anywhere)
    referenced_tags = set()
    referenced_tags.update(all_hierarchy_tags)
    referenced_tags.update(TAG_KEYWORDS.keys())
    for ch_data in CUSTOMS_HANDBOOK_CHAPTERS.values():
        if ch_data.get("tag"):
            referenced_tags.add(ch_data["tag"])
        for sub_data in ch_data.get("sub_chapters", {}).values():
            if sub_data.get("tag"):
                referenced_tags.add(sub_data["tag"])
    for source_data in PC_AGENT_DOWNLOAD_SOURCES.values():
        referenced_tags.update(source_data.get("auto_tags", []))

    for tag in DOCUMENT_TAGS:
        if tag not in referenced_tags:
            results["orphan_tags"].append(tag)

    # Handbook coverage (which HS chapters 1-99 have data)
    covered_chapters = set()
    for ch_key in CUSTOMS_HANDBOOK_CHAPTERS:
        if isinstance(ch_key, int):
            covered_chapters.add(ch_key)

    results["handbook_coverage"] = {
        "covered_chapters": sorted(covered_chapters),
        "total": len(covered_chapters),
    }

    if results["broken_references"]:
        results["pass"] = False

    return results


def _audit_knowledge_health(db) -> Dict:
    """Audit knowledge base coverage and health."""
    health = {
        "suppliers_known": 0,
        "products_cataloged": 0,
        "past_classifications": 0,
        "knowledge_queries_total": 0,
        "enrichment_status": [],
        "blind_spots": [],
    }

    try:
        # Count knowledge_base entries by type
        kb_docs = list(db.collection("knowledge_base").limit(500).stream())
        for doc in kb_docs:
            data = doc.to_dict()
            kb_type = data.get("type", "")
            if kb_type == "supplier":
                health["suppliers_known"] += 1
            elif kb_type == "product":
                health["products_cataloged"] += 1

        # Count past classifications
        ck_docs = list(db.collection("classification_knowledge").limit(500).stream())
        health["past_classifications"] = len(ck_docs)

        # Check which HS chapters have data
        hs_chapters_with_data = set()
        for doc in ck_docs:
            data = doc.to_dict()
            hs_code = str(data.get("hs_code", data.get("tariff_code", "")))
            if hs_code and len(hs_code) >= 2:
                try:
                    chapter = int(hs_code[:2])
                    hs_chapters_with_data.add(chapter)
                except ValueError:
                    pass

        # Identify blind spots (HS chapters 1-97 with no data)
        for ch in range(1, 98):
            if ch not in hs_chapters_with_data:
                health["blind_spots"].append(ch)

        health["hs_coverage_pct"] = round(
            len(hs_chapters_with_data) / 97 * 100, 1
        )

        # Count knowledge queries
        kq_docs = list(db.collection("knowledge_queries").limit(500).stream())
        health["knowledge_queries_total"] = len(kq_docs)

        # Check enrichment tasks
        try:
            et_docs = list(db.collection("enrichment_tasks").limit(100).stream())
            now = datetime.now(timezone.utc)
            for doc in et_docs:
                data = doc.to_dict()
                last_run = data.get("last_run")
                frequency_hours = data.get("frequency_hours", 24)
                overdue = False
                if last_run and hasattr(last_run, 'timestamp'):
                    expected_next = last_run + timedelta(hours=frequency_hours)
                    overdue = now > expected_next
                health["enrichment_status"].append({
                    "task": doc.id,
                    "last_run": last_run.isoformat() if last_run and hasattr(last_run, 'isoformat') else str(last_run),
                    "overdue": overdue,
                })
        except Exception:
            pass

    except Exception as e:
        health["error"] = str(e)

    return health


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 2: PROCESS INSPECTOR
# ═══════════════════════════════════════════════════════════════════════════

def inspect_processes(db) -> Dict[str, Any]:
    """Phase 2: Check for clashes, race conditions, orphan processes."""
    print("⚙️ Phase 2: Process Inspection...")
    results = {
        "scheduler_clashes": [],
        "race_conditions": [],
        "write_conflicts": [],
        "selftest_safety": {},
        "issues": [],
        "warnings": [],
    }

    # ── 2A: Scheduler Clash Detection ──
    print("  🕐 2A: Scheduler clash detection...")
    results["scheduler_clashes"] = _detect_scheduler_clashes()

    # ── 2B: Email Processing Race Conditions ──
    print("  🏃 2B: Race condition analysis...")
    results["race_conditions"] = _detect_race_conditions()

    # ── 2C: Firestore Write Conflicts ──
    print("  ✍️ 2C: Write conflict mapping...")
    results["write_conflicts"] = _map_write_conflicts()

    # ── 2D: Self-Test Interference ──
    print("  🧪 2D: Self-test safety check...")
    results["selftest_safety"] = _check_selftest_safety(db)

    # Promote findings to issues
    if results["scheduler_clashes"]:
        results["warnings"].extend(results["scheduler_clashes"])
    if results["race_conditions"]:
        results["issues"].extend([rc["description"] for rc in results["race_conditions"]])

    print(f"  ✅ Phase 2 complete: {len(results['issues'])} issues, "
          f"{len(results['warnings'])} warnings")
    return results


def _detect_scheduler_clashes() -> List[str]:
    """Detect potential scheduler overlaps."""
    clashes = []

    # Known clash: rcb_check_email (2min) + check_email_scheduled (5min)
    clashes.append(
        "⚠️ POTENTIAL DUPLICATE: rcb_check_email (every 2min) and "
        "check_email_scheduled (every 5min) both check inbox. "
        "Risk: same email processed twice if rcb_processed check has a gap."
    )

    # monitor_agent (5min) + monitor_fix_scheduled (15min) — both write system_status
    clashes.append(
        "ℹ️ monitor_agent (5min) and monitor_fix_scheduled (15min) "
        "both write to system_status — low risk, last-write-wins."
    )

    return clashes


def _detect_race_conditions() -> List[Dict]:
    """Detect potential email processing race conditions."""
    conditions = []

    conditions.append({
        "id": "RC-001",
        "severity": "MEDIUM",
        "description": (
            "rcb_check_email and check_email_scheduled can fire within "
            "seconds of each other. Both use rcb_processed to deduplicate, "
            "but there's a TOCTOU window: both read rcb_processed, "
            "neither finds the msg, both process it."
        ),
        "mitigation": (
            "Both functions check rcb_processed.document(safe_id).get().exists "
            "before processing. The md5-based safe_id is identical in both. "
            "Firestore read+write is NOT atomic, so a small window exists."
        ),
        "recommendation": "Consolidate into single email checker or add Firestore transaction.",
    })

    return conditions


def _map_write_conflicts() -> List[Dict]:
    """Map which functions write to which collections."""
    # Static analysis of known writers
    write_map = {
        "rcb_processed": {
            "writers": ["rcb_check_email", "check_email_scheduled", "monitor_self_heal"],
            "risk": "MEDIUM — multiple writers, dedup by safe_id",
        },
        "rcb_classifications": {
            "writers": ["rcb_check_email (via process_and_send_report)"],
            "risk": "LOW — single pipeline",
        },
        "system_status": {
            "writers": ["monitor_agent", "rcb_health_check", "monitor_fix_scheduled"],
            "risk": "LOW — status updates, last-write-wins acceptable",
        },
        "knowledge_queries": {
            "writers": ["rcb_check_email (via handle_knowledge_query)"],
            "risk": "LOW — single pipeline",
        },
        "knowledge_base": {
            "writers": ["enrich_knowledge", "handle_knowledge_query (learn_from_email)"],
            "risk": "LOW — different doc IDs, no conflicts",
        },
    }
    return [{"collection": k, **v} for k, v in write_map.items()]


def _check_selftest_safety(db) -> Dict:
    """Check for leaked self-test artifacts."""
    safety = {"clean": True, "leaked_artifacts": []}

    # Check for [RCB-SELFTEST] in rcb_processed
    try:
        for doc in db.collection("rcb_processed").limit(200).stream():
            data = doc.to_dict()
            subject = data.get("subject", "")
            if "[RCB-SELFTEST]" in subject:
                safety["clean"] = False
                safety["leaked_artifacts"].append({
                    "collection": "rcb_processed",
                    "doc_id": doc.id,
                    "subject": subject[:60],
                })
    except Exception:
        pass

    # Check knowledge_queries for test artifacts
    try:
        for doc in db.collection("knowledge_queries").limit(200).stream():
            data = doc.to_dict()
            subject = str(data.get("subject", data.get("question", "")))
            if "[RCB-SELFTEST]" in subject or "selftest" in subject.lower():
                safety["clean"] = False
                safety["leaked_artifacts"].append({
                    "collection": "knowledge_queries",
                    "doc_id": doc.id,
                })
    except Exception:
        pass

    return safety


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 3: FLOW INSPECTOR
# ═══════════════════════════════════════════════════════════════════════════

def inspect_flows(db) -> Dict[str, Any]:
    """Phase 3: Verify end-to-end processing flows."""
    print("🔄 Phase 3: Flow Inspection...")
    results = {
        "classification_flow": {},
        "knowledge_query_flow": {},
        "monitor_flow": {},
        "issues": [],
        "warnings": [],
    }

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    # ── 3A: Classification Flow ──
    print("  📋 3A: Classification flow...")
    results["classification_flow"] = _inspect_classification_flow(db, day_ago, week_ago)

    # ── 3B: Knowledge Query Flow ──
    print("  📚 3B: Knowledge query flow...")
    results["knowledge_query_flow"] = _inspect_knowledge_query_flow(db, day_ago, week_ago)

    # ── 3C: Monitor & Self-Heal Flow ──
    print("  🔧 3C: Monitor flow...")
    results["monitor_flow"] = _inspect_monitor_flow(db)

    # Collect issues
    cf = results["classification_flow"]
    if cf.get("last_24h_failures", 0) > 3:
        results["issues"].append(
            f"High classification failure rate: {cf['last_24h_failures']} failures in 24h"
        )
    if cf.get("orphan_classifications", 0) > 0:
        results["warnings"].append(
            f"{cf['orphan_classifications']} orphan classifications detected"
        )

    kqf = results["knowledge_query_flow"]
    if kqf.get("unreplied_queries", 0) > 0:
        results["warnings"].append(
            f"{kqf['unreplied_queries']} knowledge queries without reply"
        )

    print(f"  ✅ Phase 3 complete: {len(results['issues'])} issues, "
          f"{len(results['warnings'])} warnings")
    return results


def _inspect_classification_flow(db, day_ago, week_ago) -> Dict:
    """Inspect the classification pipeline."""
    flow = {
        "last_successful": None,
        "last_24h_total": 0,
        "last_24h_successes": 0,
        "last_24h_failures": 0,
        "last_7d_total": 0,
        "orphan_classifications": 0,
        "avg_fields": [],
    }

    try:
        # Recent classifications
        docs = list(db.collection("rcb_classifications").limit(200).stream())
        for doc in docs:
            data = doc.to_dict()
            ts = data.get("timestamp")
            if not ts:
                continue

            if ts > week_ago:
                flow["last_7d_total"] += 1
            if ts > day_ago:
                flow["last_24h_total"] += 1
                status = data.get("status", "")
                if status == "failed" or data.get("error"):
                    flow["last_24h_failures"] += 1
                else:
                    flow["last_24h_successes"] += 1

            if flow["last_successful"] is None or (ts and ts > datetime.fromisoformat(flow["last_successful"]) if isinstance(flow["last_successful"], str) else True):
                if not data.get("error"):
                    flow["last_successful"] = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)

    except Exception as e:
        flow["error"] = str(e)

    try:
        # Check for orphans: processed but no classification
        processed = {}
        for doc in db.collection("rcb_processed").limit(200).stream():
            data = doc.to_dict()
            ts = data.get("processed_at")
            if ts and ts > day_ago and data.get("type") != "knowledge_query":
                processed[data.get("subject", "")] = doc.id

        classified_subjects = set()
        for doc in db.collection("rcb_classifications").limit(200).stream():
            data = doc.to_dict()
            ts = data.get("timestamp")
            if ts and ts > day_ago:
                classified_subjects.add(data.get("subject", ""))

        orphans = set(processed.keys()) - classified_subjects
        flow["orphan_classifications"] = len(orphans)

    except Exception:
        pass

    return flow


def _inspect_knowledge_query_flow(db, day_ago, week_ago) -> Dict:
    """Inspect the knowledge query pipeline."""
    flow = {
        "last_successful": None,
        "last_24h_total": 0,
        "last_24h_replied": 0,
        "unreplied_queries": 0,
        "last_7d_total": 0,
    }

    try:
        docs = list(db.collection("knowledge_queries").limit(200).stream())
        for doc in docs:
            data = doc.to_dict()
            ts = data.get("timestamp", data.get("created_at"))
            if not ts:
                continue

            if ts > week_ago:
                flow["last_7d_total"] += 1
            if ts > day_ago:
                flow["last_24h_total"] += 1
                if data.get("reply_sent") or data.get("status") == "replied":
                    flow["last_24h_replied"] += 1
                elif ts < (datetime.now(timezone.utc) - timedelta(minutes=5)):
                    flow["unreplied_queries"] += 1

            if data.get("reply_sent") or data.get("status") == "replied":
                if flow["last_successful"] is None:
                    flow["last_successful"] = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)

    except Exception as e:
        flow["error"] = str(e)

    return flow


def _inspect_monitor_flow(db) -> Dict:
    """Inspect the monitoring and self-heal system."""
    flow = {
        "monitor_status": "unknown",
        "last_monitor_check": None,
        "last_fix_attempt": None,
        "active_issues": [],
    }

    try:
        # Check system_status documents
        for status_name in ["rcb", "rcb_monitor"]:
            doc = db.collection("system_status").document(status_name).get()
            if doc.exists:
                data = doc.to_dict()
                flow["monitor_status"] = data.get("status", "unknown")
                last_check = data.get("last_check")
                if last_check:
                    flow["last_monitor_check"] = (
                        last_check.isoformat() if hasattr(last_check, 'isoformat') else str(last_check)
                    )
                if data.get("issues"):
                    flow["active_issues"].extend(data["issues"])

    except Exception as e:
        flow["error"] = str(e)

    return flow


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 4: MONITOR INSPECTOR
# ═══════════════════════════════════════════════════════════════════════════

def inspect_monitors(db, get_secret_func) -> Dict[str, Any]:
    """Phase 4: Verify monitors, schedulers, and secrets."""
    print("📡 Phase 4: Monitor Inspection...")
    results = {
        "scheduler_health": {},
        "secret_availability": {},
        "issues": [],
        "warnings": [],
    }

    # ── 4A: Function Health via system_status ──
    print("  ⚡ 4A: Function health...")
    try:
        doc = db.collection("system_status").document("rcb").get()
        if doc.exists:
            data = doc.to_dict()
            results["scheduler_health"]["system_status"] = data.get("status", "unknown")
            results["scheduler_health"]["last_check"] = (
                data.get("last_check").isoformat()
                if data.get("last_check") and hasattr(data.get("last_check"), 'isoformat')
                else str(data.get("last_check", "never"))
            )
            results["scheduler_health"]["pending_count"] = data.get("pending_count", 0)
            results["scheduler_health"]["issues"] = data.get("issues", [])
        else:
            results["warnings"].append("system_status/rcb document not found")
    except Exception as e:
        results["issues"].append(f"Cannot read system_status: {e}")

    # ── 4B: Secret Availability ──
    print("  🔑 4B: Secret availability...")
    required_secrets = [
        "ANTHROPIC_API_KEY",
        "RCB_GRAPH_CLIENT_ID",
        "RCB_GRAPH_CLIENT_SECRET",
        "RCB_GRAPH_TENANT_ID",
        "RCB_EMAIL",
    ]
    for secret_name in required_secrets:
        try:
            val = get_secret_func(secret_name)
            results["secret_availability"][secret_name] = (
                "✅ available" if val else "❌ empty/null"
            )
            if not val:
                results["issues"].append(f"Secret '{secret_name}' is empty or null")
        except Exception as e:
            results["secret_availability"][secret_name] = f"❌ error: {e}"
            results["issues"].append(f"Secret '{secret_name}' inaccessible: {e}")

    print(f"  ✅ Phase 4 complete: {len(results['issues'])} issues")
    return results


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 5: AUTO-FIXER
# ═══════════════════════════════════════════════════════════════════════════

def run_auto_fixes(db, all_findings: Dict) -> Dict[str, Any]:
    """Phase 5: Apply known fixes automatically."""
    print("🔧 Phase 5: Auto-Fixer...")
    fixes = {
        "applied": [],
        "skipped": [],
        "failed": [],
    }

    # ── Playbook 1: Stuck Classification ──
    fixes = _fix_stuck_classifications(db, fixes)

    # ── Playbook 3: Stale rcb_processed ──
    fixes = _fix_stale_processed(db, fixes)

    # ── Playbook 5: Self-Test Artifacts ──
    selftest_data = all_findings.get("process_inspection", {}).get("selftest_safety", {})
    if not selftest_data.get("clean", True):
        fixes = _fix_selftest_artifacts(db, selftest_data, fixes)

    # ── Playbook 7: Broken Tag Reference ──
    tag_data = all_findings.get("database_inspection", {}).get("tag_integrity", {})
    if tag_data.get("broken_references"):
        fixes["skipped"].append({
            "playbook": "PB-7: Broken Tag Reference",
            "reason": "ALERT ONLY — never auto-fix tags. "
                      f"Found {len(tag_data['broken_references'])} broken references.",
            "details": tag_data["broken_references"][:5],
        })

    total = len(fixes["applied"]) + len(fixes["skipped"]) + len(fixes["failed"])
    print(f"  ✅ Phase 5 complete: {len(fixes['applied'])} applied, "
          f"{len(fixes['skipped'])} skipped, {len(fixes['failed'])} failed")
    return fixes


def _fix_stuck_classifications(db, fixes: Dict) -> Dict:
    """Playbook 1: Fix classifications stuck in 'processing' for >10min."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        stuck = []
        for doc in db.collection("classifications").limit(100).stream():
            data = doc.to_dict()
            if data.get("status") == "processing":
                ts = data.get("started_at", data.get("timestamp"))
                if ts and ts < cutoff:
                    stuck.append(doc)

        for doc in stuck:
            try:
                data = doc.to_dict()
                retry_count = data.get("retry_count", 0) + 1
                doc.reference.update({
                    "status": "failed",
                    "retry_count": retry_count,
                    "failed_at": datetime.now(timezone.utc),
                    "fail_reason": "auto-fix: stuck in processing >10min",
                })
                fixes["applied"].append({
                    "playbook": "PB-1: Stuck Classification",
                    "doc_id": doc.id,
                    "action": f"Set status=failed, retry_count={retry_count}",
                })
            except Exception as e:
                fixes["failed"].append({
                    "playbook": "PB-1",
                    "doc_id": doc.id,
                    "error": str(e),
                })

        if not stuck:
            fixes["skipped"].append({
                "playbook": "PB-1: Stuck Classification",
                "reason": "No stuck classifications found",
            })

    except Exception as e:
        fixes["failed"].append({"playbook": "PB-1", "error": str(e)})

    return fixes


def _fix_stale_processed(db, fixes: Dict) -> Dict:
    """Playbook 3: Clean up stale rcb_processed entries."""
    try:
        all_docs = list(db.collection("rcb_processed").limit(600).stream())
        count = len(all_docs)

        if count > 500:
            # Delete entries older than 7 days
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            deleted = 0
            for doc in all_docs:
                data = doc.to_dict()
                ts = data.get("processed_at")
                if ts and ts < cutoff:
                    doc.reference.delete()
                    deleted += 1

            if deleted > 0:
                fixes["applied"].append({
                    "playbook": "PB-3: Stale rcb_processed",
                    "action": f"Deleted {deleted} entries older than 7 days (was {count})",
                })
            else:
                fixes["skipped"].append({
                    "playbook": "PB-3: Stale rcb_processed",
                    "reason": f"Count={count} but no entries older than 7 days",
                })
        else:
            fixes["skipped"].append({
                "playbook": "PB-3: Stale rcb_processed",
                "reason": f"Count={count} (threshold: 500)",
            })

    except Exception as e:
        fixes["failed"].append({"playbook": "PB-3", "error": str(e)})

    return fixes


def _fix_selftest_artifacts(db, selftest_data: Dict, fixes: Dict) -> Dict:
    """Playbook 5: Clean up leaked self-test artifacts."""
    try:
        cleaned = 0
        for artifact in selftest_data.get("leaked_artifacts", []):
            coll = artifact.get("collection")
            doc_id = artifact.get("doc_id")
            if coll and doc_id:
                try:
                    db.collection(coll).document(doc_id).delete()
                    cleaned += 1
                except Exception:
                    pass

        if cleaned > 0:
            fixes["applied"].append({
                "playbook": "PB-5: Self-Test Artifacts",
                "action": f"Cleaned {cleaned} leaked test artifacts",
            })
    except Exception as e:
        fixes["failed"].append({"playbook": "PB-5", "error": str(e)})

    return fixes


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 6: CLAUDE CONSULTANT
# ═══════════════════════════════════════════════════════════════════════════

def consult_claude_if_needed(
    api_key: Optional[str],
    all_findings: Dict,
) -> Dict[str, Any]:
    """
    Phase 6: Ask Claude about problems the rule engine can't solve.
    Only called if there are unsolved issues.
    """
    print("🧠 Phase 6: Claude Consultant...")

    # Collect unsolved issues from all phases
    unsolved = []
    for phase_key, phase_data in all_findings.items():
        if isinstance(phase_data, dict):
            for issue in phase_data.get("issues", []):
                unsolved.append({"phase": phase_key, "issue": issue})

    # Also check for unusual patterns
    db_stats = all_findings.get("database_inspection", {}).get("collection_stats", {})
    for coll, stats in db_stats.items():
        if stats.get("error"):
            unsolved.append({
                "phase": "database",
                "issue": f"Collection {coll} error: {stats['error']}",
            })

    if not unsolved:
        print("  ✅ No unsolved problems — skipping Claude consultation")
        return {"consulted": False, "reason": "No unsolved problems"}

    if not api_key or call_claude is None:
        print("  ⚠️ Claude API unavailable — logging unsolved problems")
        return {
            "consulted": False,
            "reason": "API key or call_claude not available",
            "unsolved_count": len(unsolved),
            "unsolved_problems": unsolved[:10],
        }

    # Ask Claude ONE focused question
    print(f"  🤖 Consulting Claude about {len(unsolved)} unsolved problems...")

    system_prompt = """You are RCB's Inspector consultant. You receive a system health 
report with unsolved problems. Your job:
1. Analyze the unsolved problems
2. Suggest root causes
3. Recommend fixes (specific code changes or config)
4. Flag anything that needs a new Claude session

Be concise. Output JSON with: analysis, fixes, session_recommendations."""

    user_prompt = f"""RCB System Health Report — Unsolved Problems:
{json.dumps(unsolved, ensure_ascii=False, indent=2)}

System context:
- Version: {VERSION}
- Total collections: {len(EXPECTED_COLLECTIONS)}
- Tag count: {len(DOCUMENT_TAGS)}

These problems could not be resolved by rule-based fixes.
Analyze and recommend."""

    try:
        response = call_claude(api_key, system_prompt, user_prompt, max_tokens=2000)
        if response:
            # Try to parse as JSON
            try:
                claude_advice = json.loads(response)
            except json.JSONDecodeError:
                claude_advice = {"raw_response": response}

            print(f"  ✅ Claude consultation complete")
            return {
                "consulted": True,
                "unsolved_count": len(unsolved),
                "claude_advice": claude_advice,
            }
        else:
            return {
                "consulted": False,
                "reason": "Claude returned empty response",
                "unsolved_count": len(unsolved),
            }
    except Exception as e:
        return {
            "consulted": False,
            "reason": f"Claude call failed: {e}",
            "unsolved_count": len(unsolved),
        }


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 7: SESSION PLANNER
# ═══════════════════════════════════════════════════════════════════════════

def plan_next_session(
    db,
    all_findings: Dict,
    claude_advice: Dict,
) -> Dict[str, Any]:
    """Phase 7: Generate a ready-to-use mission file for the next Claude session."""
    print("📝 Phase 7: Session Planner...")

    # Determine next session ID
    session_id = _get_next_session_id(db)

    # Build priority task list
    tasks = _build_task_list(all_findings, claude_advice)

    if not tasks:
        print("  ✅ No tasks to plan — system is healthy")
        return {"session_id": session_id, "tasks": [], "priority": "NONE"}

    # Sort by priority
    tasks.sort(key=lambda t: t.get("priority_score", 0), reverse=True)

    # Determine overall priority
    max_score = tasks[0].get("priority_score", 0) if tasks else 0
    if max_score >= 90:
        overall_priority = "HIGH"
    elif max_score >= 60:
        overall_priority = "MEDIUM"
    else:
        overall_priority = "LOW"

    # Build title from top tasks
    top_titles = [t["title"] for t in tasks[:2]]
    title = " + ".join(top_titles)

    # Determine affected files
    all_affected = set()
    for t in tasks:
        all_affected.update(t.get("affected_files", []))

    mission = {
        "session_id": session_id,
        "generated_by": "rcb_inspector",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "priority": overall_priority,
        "title": title,
        "context": {
            "current_version": VERSION,
            "system_health": overall_priority,
            "relevant_modules": list(all_affected)[:10],
            "do_not_touch": ["librarian_tags.py"],
        },
        "tasks": [
            {
                "priority": i + 1,
                "title": t["title"],
                "description": t.get("description", ""),
                "affected_files": t.get("affected_files", []),
                "evidence": t.get("evidence", ""),
                "category": t.get("category", ""),
            }
            for i, t in enumerate(tasks[:8])  # Max 8 tasks per session
        ],
        "prerequisites": [
            "Upload lib_audit.zip (fresh from Cloud Shell)",
            "Upload SESSION_PROTOCOL_CONSULT_BEFORE_WORK.md",
            f"Upload SESSION_{session_id}_MISSION.md (this file)",
        ],
        "test_criteria": [
            "All existing self-tests still pass",
            "New tests added for fixed issues",
            "Inspector report shows improvement",
        ],
    }

    # Save to Firestore
    try:
        db.collection("session_missions").document(session_id).set(mission)
        print(f"  💾 Mission saved to session_missions/{session_id}")
    except Exception as e:
        print(f"  ⚠️ Failed to save mission to Firestore: {e}")

    # Generate markdown version
    mission["markdown"] = _generate_mission_markdown(mission)

    print(f"  ✅ Phase 7 complete: Session {session_id} — {overall_priority} — "
          f"{len(tasks)} tasks")
    return mission


def _get_next_session_id(db) -> str:
    """Determine the next session ID from sessions_backup."""
    try:
        docs = list(db.collection("sessions_backup").limit(50).stream())
        max_num = 14  # Current known max
        for doc in docs:
            # Try to parse session number from doc ID
            doc_id = doc.id
            for part in doc_id.replace("session_", "").replace("session", "").split("_"):
                try:
                    num = int(float(part))
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        return f"session_{max_num + 1}"
    except Exception:
        return "session_15"


def _build_task_list(all_findings: Dict, claude_advice: Dict) -> List[Dict]:
    """Build prioritized task list from all findings."""
    tasks = []

    # From database issues
    db_findings = all_findings.get("database_inspection", {})

    tag_integrity = db_findings.get("tag_integrity", {})
    if tag_integrity.get("broken_references"):
        tasks.append({
            "title": "Fix broken tag references",
            "description": f"{len(tag_integrity['broken_references'])} broken tag references found in librarian_tags.py",
            "affected_files": ["lib/librarian_tags.py"],
            "evidence": str(tag_integrity["broken_references"][:3]),
            "category": "data_integrity",
            "priority_score": PRIORITY_RULES["data_integrity"],
        })

    knowledge = db_findings.get("knowledge_health", {})
    if knowledge.get("blind_spots"):
        blind_count = len(knowledge["blind_spots"])
        tasks.append({
            "title": f"Enrich knowledge for {blind_count} blind-spot HS chapters",
            "description": f"HS chapters with zero classification data: {knowledge['blind_spots'][:10]}...",
            "affected_files": ["lib/enrichment_agent.py", "lib/librarian_researcher.py"],
            "evidence": f"{knowledge.get('hs_coverage_pct', 0)}% HS coverage",
            "category": "new_capability",
            "priority_score": PRIORITY_RULES["new_capability"],
        })

    # From process issues
    proc_findings = all_findings.get("process_inspection", {})
    if proc_findings.get("race_conditions"):
        for rc in proc_findings["race_conditions"]:
            tasks.append({
                "title": f"Fix race condition: {rc.get('id', 'unknown')}",
                "description": rc.get("description", ""),
                "affected_files": ["main.py"],
                "evidence": rc.get("mitigation", ""),
                "category": "race_condition",
                "priority_score": PRIORITY_RULES["race_condition"],
            })

    # From flow issues
    flow_findings = all_findings.get("flow_inspection", {})
    cf = flow_findings.get("classification_flow", {})
    if cf.get("last_24h_failures", 0) > 3:
        tasks.append({
            "title": "Fix high classification failure rate",
            "description": f"{cf['last_24h_failures']} failures in last 24h",
            "affected_files": ["lib/classification_agents.py", "main.py"],
            "evidence": json.dumps(cf, default=str),
            "category": "flow_broken",
            "priority_score": PRIORITY_RULES["flow_broken"],
        })

    # From Claude advice
    if claude_advice.get("consulted") and claude_advice.get("claude_advice"):
        advice = claude_advice["claude_advice"]
        session_recs = advice.get("session_recommendations", [])
        if isinstance(session_recs, list):
            for rec in session_recs[:3]:
                if isinstance(rec, str):
                    tasks.append({
                        "title": rec[:80],
                        "description": rec,
                        "affected_files": [],
                        "evidence": "Claude recommendation",
                        "category": "new_capability",
                        "priority_score": PRIORITY_RULES["new_capability"],
                    })
                elif isinstance(rec, dict):
                    tasks.append({
                        "title": rec.get("title", "Claude recommendation")[:80],
                        "description": rec.get("description", ""),
                        "affected_files": rec.get("files", []),
                        "evidence": "Claude recommendation",
                        "category": rec.get("category", "new_capability"),
                        "priority_score": PRIORITY_RULES.get(
                            rec.get("category", "new_capability"), 40
                        ),
                    })

    # Scheduler dedup recommendation (always present)
    tasks.append({
        "title": "Consolidate duplicate email schedulers",
        "description": (
            "rcb_check_email (2min) and check_email_scheduled (5min) "
            "are functionally similar. Consolidate into one."
        ),
        "affected_files": ["main.py"],
        "evidence": "Process inspection Phase 2A",
        "category": "optimization",
        "priority_score": PRIORITY_RULES["optimization"],
    })

    return tasks


def _generate_mission_markdown(mission: Dict) -> str:
    """Generate markdown version of the mission file."""
    lines = [
        f"# {mission['session_id'].upper().replace('_', ' ')} MISSION",
        f"## {mission['title']}",
        "",
        f"**Generated by:** RCB Inspector v{VERSION}",
        f"**Generated at:** {mission['generated_at']}",
        f"**Priority:** {mission['priority']}",
        "",
        "---",
        "",
        "## CONTEXT",
        "",
        f"- System Version: {mission['context']['current_version']}",
        f"- System Health: {mission['context']['system_health']}",
        f"- Relevant Modules: {', '.join(mission['context']['relevant_modules'])}",
        f"- Do Not Touch: {', '.join(mission['context']['do_not_touch'])}",
        "",
        "---",
        "",
        "## TASKS",
        "",
    ]

    for task in mission.get("tasks", []):
        lines.extend([
            f"### [{task['priority']}] {task['title']}",
            f"**Category:** {task.get('category', 'N/A')}",
            f"**Affected Files:** {', '.join(task.get('affected_files', ['N/A']))}",
            "",
            task.get("description", ""),
            "",
            f"**Evidence:** {task.get('evidence', 'N/A')}",
            "",
        ])

    lines.extend([
        "---",
        "",
        "## PREREQUISITES",
        "",
    ])
    for p in mission.get("prerequisites", []):
        lines.append(f"- {p}")

    lines.extend([
        "",
        "---",
        "",
        "## TEST CRITERIA",
        "",
    ])
    for t in mission.get("test_criteria", []):
        lines.append(f"- {t}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 8: REPORT GENERATOR + EMAIL
# ═══════════════════════════════════════════════════════════════════════════

def generate_report(all_findings: Dict, mission: Dict) -> Dict[str, Any]:
    """Phase 8: Generate the full inspection report."""
    print("📊 Phase 8: Report Generation...")

    # Calculate health score
    score = _calculate_health_score(all_findings)

    if score >= 90:
        health = "HEALTHY"
        emoji = "✅"
    elif score >= 70:
        health = "DEGRADED"
        emoji = "⚠️"
    else:
        health = "CRITICAL"
        emoji = "🚨"

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "health": health,
        "health_score": score,
        "summary": {
            "total_collections": len(all_findings.get("database_inspection", {}).get("collection_stats", {})),
            "total_documents": all_findings.get("database_inspection", {}).get("total_documents", 0),
            "tag_integrity": all_findings.get("database_inspection", {}).get("tag_integrity", {}).get("pass", False),
            "tag_count": all_findings.get("database_inspection", {}).get("tag_integrity", {}).get("total_tags", 0),
            "knowledge_coverage": all_findings.get("database_inspection", {}).get("knowledge_health", {}).get("hs_coverage_pct", 0),
        },
        "email_processing": {
            "classifications_24h": all_findings.get("flow_inspection", {}).get("classification_flow", {}).get("last_24h_total", 0),
            "classification_successes": all_findings.get("flow_inspection", {}).get("classification_flow", {}).get("last_24h_successes", 0),
            "knowledge_queries_24h": all_findings.get("flow_inspection", {}).get("knowledge_query_flow", {}).get("last_24h_total", 0),
        },
        "auto_fixes": all_findings.get("auto_fixes", {}),
        "issues": [],
        "warnings": [],
        "next_session": {
            "session_id": mission.get("session_id", ""),
            "priority": mission.get("priority", ""),
            "title": mission.get("title", ""),
            "task_count": len(mission.get("tasks", [])),
        },
        "claude_consultation": all_findings.get("claude_consultation", {}),
    }

    # Collect all issues and warnings
    for phase_key, phase_data in all_findings.items():
        if isinstance(phase_data, dict):
            for issue in phase_data.get("issues", []):
                report["issues"].append({"phase": phase_key, "issue": issue})
            for warning in phase_data.get("warnings", []):
                report["warnings"].append({"phase": phase_key, "warning": warning})

    print(f"  ✅ Report generated: {emoji} {health} (score: {score}/100)")
    return report


def _calculate_health_score(all_findings: Dict) -> int:
    """Calculate overall health score (0-100)."""
    score = 100
    deductions = []

    # Database issues
    db = all_findings.get("database_inspection", {})
    if not db.get("tag_integrity", {}).get("pass", True):
        score -= 15
        deductions.append("tag integrity failure: -15")
    if db.get("knowledge_health", {}).get("hs_coverage_pct", 100) < 50:
        score -= 5
        deductions.append("low HS coverage: -5")

    # Process issues
    proc = all_findings.get("process_inspection", {})
    if not proc.get("selftest_safety", {}).get("clean", True):
        score -= 10
        deductions.append("selftest leak: -10")
    if proc.get("race_conditions"):
        score -= 5
        deductions.append("race conditions: -5")

    # Flow issues
    flow = all_findings.get("flow_inspection", {})
    cf = flow.get("classification_flow", {})
    if cf.get("last_24h_failures", 0) > 3:
        score -= 20
        deductions.append("high failure rate: -20")
    elif cf.get("last_24h_failures", 0) > 0:
        score -= 5
        deductions.append("some failures: -5")

    kqf = flow.get("knowledge_query_flow", {})
    if kqf.get("unreplied_queries", 0) > 0:
        score -= 10
        deductions.append("unreplied queries: -10")

    # Monitor issues
    mon = all_findings.get("monitor_inspection", {})
    secret_issues = [
        k for k, v in mon.get("secret_availability", {}).items()
        if "❌" in str(v)
    ]
    if secret_issues:
        score -= 20
        deductions.append(f"missing secrets ({len(secret_issues)}): -20")

    # Per-issue deduction
    total_issues = sum(
        len(phase.get("issues", []))
        for phase in all_findings.values()
        if isinstance(phase, dict)
    )
    score -= min(total_issues * 2, 20)

    score = max(0, min(100, score))
    return score


def generate_email_html(report: Dict, mission: Dict) -> str:
    """Generate the HTML email body for the daily report."""
    health = report["health"]
    score = report["health_score"]
    summary = report.get("summary", {})
    email_proc = report.get("email_processing", {})
    auto_fixes = report.get("auto_fixes", {})
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if health == "HEALTHY":
        health_color = "#28a745"
    elif health == "DEGRADED":
        health_color = "#ffc107"
    else:
        health_color = "#dc3545"

    # Auto-fixes summary
    fixes_applied = auto_fixes.get("applied", [])
    fixes_html = ""
    if fixes_applied:
        fix_items = "".join(
            f"<li>{f.get('playbook', '')}: {f.get('action', '')}</li>"
            for f in fixes_applied
        )
        fixes_html = f"<ul>{fix_items}</ul>"
    else:
        fixes_html = "<p>No fixes needed ✅</p>"

    # Issues & warnings
    issues = report.get("issues", [])
    warnings = report.get("warnings", [])
    alerts_html = ""
    if issues:
        alert_items = "".join(
            f"<li style='color:#dc3545'>🚨 {i.get('issue', '')}</li>"
            for i in issues
        )
        alerts_html += f"<ul>{alert_items}</ul>"
    if warnings:
        warn_items = "".join(
            f"<li style='color:#856404'>⚠️ {w.get('warning', '')}</li>"
            for w in warnings
        )
        alerts_html += f"<ul>{warn_items}</ul>"
    if not issues and not warnings:
        alerts_html = "<p>No alerts ✅</p>"

    # Next session
    ns = report.get("next_session", {})
    tasks_html = ""
    for i, task in enumerate(mission.get("tasks", [])[:5]):
        tasks_html += f"<li>[P{task.get('priority', i+1)}] {task.get('title', '')}</li>"

    html = f'''<div dir="ltr" style="font-family:Consolas,monospace;max-width:700px;margin:0 auto;">

<div style="background:#1a1a2e;color:#fff;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
    <h1 style="margin:0;font-size:22px;">🔍 RCB DAILY INSPECTION REPORT</h1>
    <p style="margin:5px 0 0;opacity:0.8;">{now_str} 15:00 Jerusalem Time</p>
    <p style="margin:5px 0 0;">System Version: {VERSION}</p>
    <p style="margin:10px 0 0;">
        <span style="background:{health_color};padding:5px 15px;border-radius:4px;font-weight:bold;">
            {health} (score: {score}/100)
        </span>
    </p>
</div>

<div style="background:#f8f9fa;padding:20px;border:1px solid #dee2e6;">

    <h2 style="border-bottom:2px solid #1a1a2e;padding-bottom:8px;">📊 DATABASE STATUS</h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:15px;">
        <tr><td style="padding:4px 8px;">Collections</td><td style="padding:4px 8px;text-align:right;">{summary.get('total_collections', 0)}</td></tr>
        <tr><td style="padding:4px 8px;">Documents</td><td style="padding:4px 8px;text-align:right;">{summary.get('total_documents', 0):,}</td></tr>
        <tr><td style="padding:4px 8px;">Tag Integrity</td><td style="padding:4px 8px;text-align:right;">{"✅ PASS" if summary.get('tag_integrity') else "❌ FAIL"} ({summary.get('tag_count', 0)} tags)</td></tr>
        <tr><td style="padding:4px 8px;">Knowledge Coverage</td><td style="padding:4px 8px;text-align:right;">{summary.get('knowledge_coverage', 0)}% of HS chapters</td></tr>
    </table>

    <h2 style="border-bottom:2px solid #1a1a2e;padding-bottom:8px;">📧 EMAIL PROCESSING (last 24h)</h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:15px;">
        <tr><td style="padding:4px 8px;">Classifications</td><td style="padding:4px 8px;text-align:right;">{email_proc.get('classifications_24h', 0)} ({email_proc.get('classification_successes', 0)} success)</td></tr>
        <tr><td style="padding:4px 8px;">Knowledge queries</td><td style="padding:4px 8px;text-align:right;">{email_proc.get('knowledge_queries_24h', 0)}</td></tr>
    </table>

    <h2 style="border-bottom:2px solid #1a1a2e;padding-bottom:8px;">🔧 AUTO-FIXES APPLIED</h2>
    {fixes_html}

    <h2 style="border-bottom:2px solid #1a1a2e;padding-bottom:8px;">⚠️ ALERTS</h2>
    {alerts_html}

    <div style="background:#e8f4fd;padding:15px;border-radius:8px;border:1px solid #b8daff;margin-top:20px;">
        <h2 style="margin-top:0;border-bottom:2px solid #1a1a2e;padding-bottom:8px;">
            📋 NEXT SESSION RECOMMENDATION
        </h2>
        <p><strong>{ns.get('session_id', 'N/A')}</strong> — Priority: <strong>{ns.get('priority', 'N/A')}</strong></p>
        <p><em>{ns.get('title', 'No tasks planned')}</em></p>
        <h4>Tasks:</h4>
        <ol>{tasks_html}</ol>
        <p style="font-size:12px;color:#666;">
            Files to upload: SESSION_PROTOCOL, lib_audit.zip, mission file
        </p>
    </div>

</div>

<div style="background:#1a1a2e;color:#aaa;padding:15px;border-radius:0 0 8px 8px;text-align:center;font-size:12px;">
    <p>Generated by RCB Inspector v{VERSION}</p>
    <p>Claude consulted: {"Yes" if report.get("claude_consultation", {}).get("consulted") else "No"}</p>
</div>

</div>'''
    return html


# ═══════════════════════════════════════════════════════════════════════════
#  ORCHESTRATOR: Run Full Inspection
# ═══════════════════════════════════════════════════════════════════════════

def run_full_inspection(
    db,
    get_secret_func,
    send_email: bool = False,
) -> Dict[str, Any]:
    """
    Run the complete inspection pipeline.
    ALWAYS starts with Librarian consultation (Phase 0).
    """
    started = datetime.now(timezone.utc)
    print(f"{'='*60}")
    print(f"🔍 RCB INSPECTOR — Full Inspection Starting")
    print(f"   {started.isoformat()}")
    print(f"{'='*60}")

    all_findings = {}

    try:
        # ═══ PHASE 0: CONSULT THE LIBRARIAN (MANDATORY) ═══
        librarian_state = consult_librarian(db)
        all_findings["librarian_state"] = librarian_state

        # ═══ PHASE 1: DATABASE INSPECTION ═══
        all_findings["database_inspection"] = inspect_database(db, librarian_state)

        # ═══ PHASE 2: PROCESS INSPECTION ═══
        all_findings["process_inspection"] = inspect_processes(db)

        # ═══ PHASE 3: FLOW INSPECTION ═══
        all_findings["flow_inspection"] = inspect_flows(db)

        # ═══ PHASE 4: MONITOR INSPECTION ═══
        all_findings["monitor_inspection"] = inspect_monitors(db, get_secret_func)

        # ═══ PHASE 5: AUTO-FIXER ═══
        all_findings["auto_fixes"] = run_auto_fixes(db, all_findings)

        # ═══ PHASE 6: CLAUDE CONSULTANT ═══
        api_key = get_secret_func("ANTHROPIC_API_KEY")
        all_findings["claude_consultation"] = consult_claude_if_needed(
            api_key, all_findings
        )

        # ═══ PHASE 7: SESSION PLANNER ═══
        mission = plan_next_session(
            db, all_findings, all_findings["claude_consultation"]
        )
        all_findings["next_session_mission"] = mission

        # ═══ PHASE 8: REPORT GENERATION ═══
        report = generate_report(all_findings, mission)
        all_findings["report"] = report

        # Save report to Firestore
        report_id = f"report_{started.strftime('%Y%m%d_%H%M%S')}"
        try:
            # Firestore can't store some complex nested structures; simplify
            report_for_db = {
                "timestamp": started,
                "health": report["health"],
                "health_score": report["health_score"],
                "issue_count": len(report.get("issues", [])),
                "warning_count": len(report.get("warnings", [])),
                "fixes_applied": len(all_findings.get("auto_fixes", {}).get("applied", [])),
                "next_session": report.get("next_session", {}),
                "version": VERSION,
            }
            db.collection("rcb_inspector_reports").document(report_id).set(report_for_db)
            print(f"💾 Report saved to rcb_inspector_reports/{report_id}")
        except Exception as e:
            print(f"⚠️ Failed to save report to Firestore: {e}")

        # ═══ SEND EMAIL (if daily run) ═══
        if send_email:
            _send_daily_email(db, get_secret_func, report, mission)

    except Exception as e:
        print(f"❌ INSPECTOR CRITICAL ERROR: {e}")
        traceback.print_exc()
        all_findings["critical_error"] = str(e)

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    print(f"\n{'='*60}")
    print(f"🔍 RCB INSPECTOR — Complete ({elapsed:.1f}s)")
    print(f"{'='*60}")

    all_findings["elapsed_seconds"] = elapsed
    return all_findings


def _send_daily_email(db, get_secret_func, report: Dict, mission: Dict):
    """Send the daily inspection email to doron@."""
    print("📧 Sending daily email...")
    try:
        secrets = get_rcb_secrets_internal(get_secret_func)
        if not secrets:
            print("  ❌ No secrets available for email")
            return

        access_token = helper_get_graph_token(secrets)
        if not access_token:
            print("  ❌ Failed to get Graph token")
            return

        rcb_email = secrets.get("RCB_EMAIL", RCB_EMAIL_DEFAULT)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        health = report.get("health", "UNKNOWN")

        subject = f"🔍 RCB Daily Inspection — {now_str} — {health}"
        body_html = generate_email_html(report, mission)

        success = helper_graph_send(
            access_token, rcb_email, MASTER_EMAIL,
            subject, body_html,
            reply_to_id=None,
            attachments_data=None,
        )

        if success:
            print(f"  ✅ Daily email sent to {MASTER_EMAIL}")
        else:
            print(f"  ❌ Failed to send daily email")

    except Exception as e:
        print(f"  ❌ Email error: {e}")
        traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
#  CLOUD FUNCTION ENTRY POINTS
# ═══════════════════════════════════════════════════════════════════════════

def handle_inspector_http(req, db, get_secret_func):
    """
    HTTP trigger handler — manual inspection run.
    Called from Cloud Function: rcb_inspector
    """
    try:
        send = req.args.get("send_email", "false").lower() == "true"
        results = run_full_inspection(db, get_secret_func, send_email=send)

        # Return JSON summary
        report = results.get("report", {})
        return {
            "status": "ok",
            "health": report.get("health", "UNKNOWN"),
            "score": report.get("health_score", 0),
            "issues": len(report.get("issues", [])),
            "warnings": len(report.get("warnings", [])),
            "fixes_applied": len(results.get("auto_fixes", {}).get("applied", [])),
            "next_session": report.get("next_session", {}),
            "elapsed_seconds": results.get("elapsed_seconds", 0),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def handle_inspector_daily(db, get_secret_func):
    """
    Scheduler handler — daily 15:00 Jerusalem inspection + email.
    Called from Cloud Function: rcb_inspector_daily
    """
    try:
        results = run_full_inspection(db, get_secret_func, send_email=True)
        report = results.get("report", {})
        print(f"📊 Daily inspection complete: {report.get('health', 'UNKNOWN')} "
              f"(score: {report.get('health_score', 0)})")
    except Exception as e:
        print(f"❌ Daily inspection failed: {e}")
        traceback.print_exc()
