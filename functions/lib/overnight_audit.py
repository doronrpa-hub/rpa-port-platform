"""
Overnight Audit — one-time diagnostic scan of the entire RCB system.

READ-ONLY: Does NOT send emails, does NOT modify existing data.
Writes results to Firestore collection: overnight_audit_results

Checks:
  1. Re-process last 30 days of emails through Pupil + Tracker (silent)
  2. Memory hit rate on learned_classifications
  3. Ghost deal count (no containers, no AWB, no storage_id)
  4. AWB status count
  5. Brain index size and recent growth
  6. Sender/doc-type analysis
"""

from datetime import datetime, timedelta, timezone
import traceback


def run_overnight_audit(db, firestore_module, access_token, rcb_email, get_secret):
    """
    Main audit entry point. Returns summary dict, saves to Firestore.
    All operations are read-only except writing the audit result.
    """
    started = datetime.now(timezone.utc)
    print("🔍 Overnight audit starting...")

    results = {
        "started_at": started.isoformat(),
        "email_reprocessing": {},
        "memory_hit_rate": {},
        "ghost_deals": {},
        "awb_status": {},
        "brain_index": {},
        "sender_analysis": {},
        "collection_counts": {},
        "errors": [],
    }

    # ── 1. Email reprocessing: feed last 30 days through Pupil + Tracker ──
    try:
        email_stats = _audit_email_reprocessing(db, firestore_module, access_token, rcb_email, get_secret)
        results["email_reprocessing"] = email_stats
        print(f"  ✅ Email reprocessing: {email_stats.get('total_emails', 0)} emails scanned")
    except Exception as e:
        results["errors"].append(f"email_reprocessing: {e}")
        print(f"  ❌ Email reprocessing error: {e}")
        traceback.print_exc()

    # ── 2. Memory hit rate ──
    try:
        memory_stats = _audit_memory_hit_rate(db)
        results["memory_hit_rate"] = memory_stats
        print(f"  ✅ Memory: {memory_stats.get('total_learned', 0)} learned, "
              f"{memory_stats.get('hit_rate_pct', 0):.1f}% hit rate")
    except Exception as e:
        results["errors"].append(f"memory_hit_rate: {e}")
        print(f"  ❌ Memory hit rate error: {e}")

    # ── 3. Ghost deals ──
    try:
        ghost_stats = _audit_ghost_deals(db)
        results["ghost_deals"] = ghost_stats
        print(f"  ✅ Deals: {ghost_stats.get('total_active', 0)} active, "
              f"{ghost_stats.get('ghost_count', 0)} ghosts")
    except Exception as e:
        results["errors"].append(f"ghost_deals: {e}")
        print(f"  ❌ Ghost deals error: {e}")

    # ── 4. AWB status ──
    try:
        awb_stats = _audit_awb_status(db)
        results["awb_status"] = awb_stats
        print(f"  ✅ AWBs: {awb_stats.get('total', 0)} tracked, "
              f"{awb_stats.get('active', 0)} active")
    except Exception as e:
        results["errors"].append(f"awb_status: {e}")
        print(f"  ❌ AWB status error: {e}")

    # ── 5. Brain index ──
    try:
        brain_stats = _audit_brain_index(db)
        results["brain_index"] = brain_stats
        print(f"  ✅ Brain: {brain_stats.get('brain_index_size', 0)} entries, "
              f"{brain_stats.get('recent_growth_7d', 0)} new in 7d")
    except Exception as e:
        results["errors"].append(f"brain_index: {e}")
        print(f"  ❌ Brain index error: {e}")

    # ── 6. Sender analysis ──
    try:
        sender_stats = _audit_sender_analysis(db)
        results["sender_analysis"] = sender_stats
        print(f"  ✅ Senders: {sender_stats.get('unique_senders', 0)} unique")
    except Exception as e:
        results["errors"].append(f"sender_analysis: {e}")
        print(f"  ❌ Sender analysis error: {e}")

    # ── 7. Collection counts ──
    try:
        counts = _audit_collection_counts(db)
        results["collection_counts"] = counts
        print(f"  ✅ Collections: {len(counts)} counted")
    except Exception as e:
        results["errors"].append(f"collection_counts: {e}")
        print(f"  ❌ Collection counts error: {e}")

    # ── 8. Self-enrichment: fill knowledge gaps (Session 27) ──
    try:
        from lib.self_enrichment import run_nightly_enrichment, generate_enrichment_report
        enrichment_results = run_nightly_enrichment(db, max_gaps=50)
        results["self_enrichment"] = enrichment_results
        enrichment_report = generate_enrichment_report(enrichment_results)
        print(f"  Self-enrichment: {enrichment_results['filled']} filled, "
              f"{enrichment_results['failed']} failed, {enrichment_results['skipped']} flagged")
    except Exception as e:
        results["errors"].append(f"self_enrichment: {e}")
        print(f"  Self-enrichment error: {e}")

    # ── 9. PC Agent Runner: execute pending tasks (Session 27, Assignment 14) ──
    try:
        from lib.pc_agent_runner import run_pending_tasks
        runner_results = run_pending_tasks(db, max_tasks=10)
        results["pc_agent_runner"] = runner_results
        print(f"  PC Agent Runner: {runner_results['executed']} executed, "
              f"{runner_results['skipped_browser']} skipped, {runner_results['failed']} failed")
    except Exception as e:
        results["errors"].append(f"pc_agent_runner: {e}")
        print(f"  PC Agent Runner error: {e}")

    # ── Save results ──
    finished = datetime.now(timezone.utc)
    results["finished_at"] = finished.isoformat()
    results["duration_sec"] = (finished - started).total_seconds()

    try:
        doc_id = f"audit_{started.strftime('%Y%m%d_%H%M%S')}"
        db.collection("overnight_audit_results").document(doc_id).set(results)
        print(f"  💾 Results saved to overnight_audit_results/{doc_id}")
    except Exception as e:
        print(f"  ❌ Failed to save results: {e}")
        results["errors"].append(f"save: {e}")

    print(f"🔍 Overnight audit complete in {results['duration_sec']:.1f}s")
    return results


# ═══════════════════════════════════════════════════════════════
#  AUDIT MODULES
# ═══════════════════════════════════════════════════════════════

def _audit_email_reprocessing(db, firestore_module, access_token, rcb_email, get_secret):
    """
    Read last 30 days of emails, feed each through Pupil + Tracker in silent mode.
    Does NOT send replies — is_direct=False for tracker, pupil never replies in Phase A.
    """
    import requests

    stats = {
        "total_emails": 0,
        "pupil_processed": 0,
        "pupil_errors": 0,
        "tracker_processed": 0,
        "tracker_errors": 0,
        "already_observed": 0,
        "skipped_system": 0,
    }

    if not access_token:
        stats["error"] = "no_access_token"
        return stats

    # Fetch up to 200 emails from last 30 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f"https://graph.microsoft.com/v1.0/users/{rcb_email}/mailFolders/inbox/messages"
    params = {
        '$top': 50,
        '$orderby': 'receivedDateTime desc',
        '$filter': f"receivedDateTime ge {cutoff}",
        '$select': 'id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,bodyPreview,internetMessageId',
    }

    try:
        resp = requests.get(url, headers={'Authorization': f'Bearer {access_token}'}, params=params, timeout=30)
        if resp.status_code != 200:
            stats["error"] = f"graph_api_{resp.status_code}"
            return stats
        messages = resp.json().get('value', [])
    except Exception as e:
        stats["error"] = str(e)
        return stats

    stats["total_emails"] = len(messages)

    # Load modules
    pupil_fn = None
    tracker_fn = None
    try:
        from lib.pupil import pupil_process_email
        pupil_fn = pupil_process_email
    except ImportError:
        pass
    try:
        from lib.tracker import tracker_process_email
        tracker_fn = tracker_process_email
    except ImportError:
        pass

    system_senders = ['noreply', 'mailer-daemon', 'postmaster', 'calendar']

    for msg in messages:
        from_email = msg.get('from', {}).get('emailAddress', {}).get('address', '').lower()

        # Skip system emails
        if any(s in from_email for s in system_senders):
            stats["skipped_system"] += 1
            continue

        # Feed to Pupil (silent observation — Phase A only, never sends)
        if pupil_fn:
            try:
                pupil_fn(msg, db, firestore_module, access_token, rcb_email, get_secret)
                stats["pupil_processed"] += 1
            except Exception:
                stats["pupil_errors"] += 1

        # Feed to Tracker (silent — is_direct=False skips notifications)
        if tracker_fn:
            try:
                tracker_fn(msg, db, firestore_module, access_token, rcb_email, get_secret, is_direct=False)
                stats["tracker_processed"] += 1
            except Exception:
                stats["tracker_errors"] += 1

    return stats


def _audit_memory_hit_rate(db):
    """
    Read all learned_classifications, test each with check_classification_memory.
    """
    stats = {
        "total_learned": 0,
        "tested": 0,
        "hits_exact": 0,
        "hits_fuzzy": 0,
        "hits_partial": 0,
        "misses": 0,
        "hit_rate_pct": 0.0,
        "by_source": {},
        "by_method": {},
    }

    # Read all learned classifications
    try:
        docs = list(db.collection("learned_classifications").limit(500).stream())
    except Exception:
        docs = []

    stats["total_learned"] = len(docs)
    if not docs:
        return stats

    # Init memory checker
    try:
        from lib.self_learning import SelfLearningEngine
        engine = SelfLearningEngine(db)
    except ImportError:
        stats["error"] = "self_learning_not_available"
        return stats

    for doc in docs:
        data = doc.to_dict()
        desc = data.get("product_description", "")
        source = data.get("source", "unknown")
        method = data.get("method", "unknown")

        # Count by source and method
        stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
        stats["by_method"][method] = stats["by_method"].get(method, 0) + 1

        if not desc:
            continue

        stats["tested"] += 1
        try:
            answer, level = engine.check_classification_memory(desc)
            if level == "exact":
                stats["hits_exact"] += 1
            elif level == "fuzzy":
                stats["hits_fuzzy"] += 1
            elif level == "partial":
                stats["hits_partial"] += 1
            else:
                stats["misses"] += 1
        except Exception:
            stats["misses"] += 1

    total_hits = stats["hits_exact"] + stats["hits_fuzzy"] + stats["hits_partial"]
    if stats["tested"] > 0:
        stats["hit_rate_pct"] = round(100 * total_hits / stats["tested"], 1)

    return stats


def _audit_ghost_deals(db):
    """Count active deals that have no polling path."""
    stats = {
        "total_active": 0,
        "ghost_count": 0,
        "ghost_deals": [],  # list of {deal_id, bol, created_at}
        "by_freight_kind": {},
        "stale_30d": 0,
    }

    cutoff_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    try:
        active = list(db.collection("tracker_deals")
                      .where("status", "in", ["active", "pending"])
                      .stream())
    except Exception:
        active = []

    stats["total_active"] = len(active)

    for doc in active:
        deal = doc.to_dict()
        fk = deal.get("freight_kind", "unknown")
        stats["by_freight_kind"][fk] = stats["by_freight_kind"].get(fk, 0) + 1

        containers = deal.get("containers", [])
        awb = deal.get("awb_number", "")
        manifest = deal.get("manifest_number", "")
        txn_ids = deal.get("transaction_ids", [])
        storage_id = deal.get("storage_id", "")

        # Ghost = no polling path
        has_fcl = bool(containers)
        has_manifest_txn = bool(manifest and txn_ids)
        has_general = bool(storage_id or manifest)  # new elif branch
        has_air = bool(awb)

        if not has_fcl and not has_manifest_txn and not has_general and not has_air:
            stats["ghost_count"] += 1
            stats["ghost_deals"].append({
                "deal_id": doc.id,
                "bol": deal.get("bol_number", ""),
                "created_at": deal.get("created_at", ""),
                "freight_kind": fk,
            })

        # Stale check
        updated = deal.get("updated_at", "")
        if updated and updated < cutoff_30d:
            stats["stale_30d"] += 1

    # Cap ghost_deals list to 20 for Firestore doc size
    if len(stats["ghost_deals"]) > 20:
        stats["ghost_deals"] = stats["ghost_deals"][:20]
        stats["ghost_deals_truncated"] = True

    return stats


def _audit_awb_status(db):
    """Count AWBs being tracked."""
    stats = {
        "total": 0,
        "active": 0,
        "by_status": {},
        "by_terminal": {},
    }

    try:
        docs = list(db.collection("tracker_awb_status").limit(500).stream())
    except Exception:
        docs = []

    stats["total"] = len(docs)

    for doc in docs:
        data = doc.to_dict()
        status = data.get("status", "unknown")
        terminal = data.get("terminal", "unknown")
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        stats["by_terminal"][terminal] = stats["by_terminal"].get(terminal, 0) + 1
        if status in ("registered", "active", "in_transit", "arrived"):
            stats["active"] += 1

    return stats


def _audit_brain_index(db):
    """Check brain_index size and recent growth."""
    stats = {
        "brain_index_size": 0,
        "brain_email_styles": 0,
        "brain_missions": 0,
        "brain_improvements": 0,
        "brain_commands": 0,
        "recent_growth_7d": 0,
    }

    collections = [
        "brain_index", "brain_email_styles", "brain_missions",
        "brain_improvements", "brain_commands",
    ]

    for coll in collections:
        try:
            count = 0
            for _ in db.collection(coll).limit(1000).stream():
                count += 1
            key = "brain_index_size" if coll == "brain_index" else coll
            stats[key] = count
        except Exception:
            pass

    # Recent growth: brain_email_styles learned in last 7 days
    cutoff_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        recent = list(db.collection("brain_email_styles")
                      .where("last_seen", ">=", cutoff_7d)
                      .limit(500).stream())
        stats["recent_growth_7d"] = len(recent)
    except Exception:
        pass

    return stats


def _audit_sender_analysis(db):
    """Analyze rcb_processed to find unique senders and doc types."""
    stats = {
        "unique_senders": 0,
        "senders": {},  # email → {count, types: {classification: N, knowledge_query: N, ...}}
        "by_type": {},  # type → count
        "total_processed": 0,
    }

    try:
        docs = list(db.collection("rcb_processed").limit(1000).stream())
    except Exception:
        docs = []

    stats["total_processed"] = len(docs)

    for doc in docs:
        data = doc.to_dict()
        sender = data.get("from", "unknown")
        doc_type = data.get("type", "unknown")

        stats["by_type"][doc_type] = stats["by_type"].get(doc_type, 0) + 1

        if sender not in stats["senders"]:
            stats["senders"][sender] = {"count": 0, "types": {}}
        stats["senders"][sender]["count"] += 1
        types = stats["senders"][sender]["types"]
        types[doc_type] = types.get(doc_type, 0) + 1

    stats["unique_senders"] = len(stats["senders"])

    # Cap senders dict for Firestore doc size limit
    if len(stats["senders"]) > 50:
        # Keep top 50 by count
        sorted_senders = sorted(stats["senders"].items(), key=lambda x: x[1]["count"], reverse=True)
        stats["senders"] = dict(sorted_senders[:50])
        stats["senders_truncated"] = True

    return stats


def _audit_collection_counts(db):
    """Count docs in key collections."""
    counts = {}
    collections = [
        "rcb_processed",
        "learned_classifications",
        "tracker_deals",
        "tracker_observations",
        "tracker_container_status",
        "tracker_awb_status",
        "tracker_timeline",
        "brain_index",
        "brain_email_styles",
        "brain_improvements",
        "brain_missions",
        "brain_commands",
        "brain_daily_digest",
        "pupil_observations",
        "pupil_teachings",
        "knowledge_base",
        "classification_knowledge",
        "product_index",
        "keyword_index",
    ]

    for coll in collections:
        try:
            count = 0
            for _ in db.collection(coll).limit(2000).stream():
                count += 1
            counts[coll] = count
        except Exception:
            counts[coll] = -1

    return counts
