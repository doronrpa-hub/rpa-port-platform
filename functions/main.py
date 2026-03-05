"""
RPA-PORT Cloud Functions
========================
Serverless functions that run automatically - no server needed.

Functions:
1. check_email_scheduled - Runs every 5 min, checks Gmail inbox
2. classify_document - Triggered when new document arrives in Firestore
3. enrich_knowledge - Runs every hour, fills knowledge gaps
4. on_classification_correction - Learns when user corrects a classification
5. api - HTTP API for web app
"""

import firebase_admin
from firebase_admin import credentials, firestore, storage
from firebase_functions import scheduler_fn, firestore_fn, https_fn, options
import json
import os
import re
from lib.classification_agents import run_full_classification, build_classification_email, process_and_send_report
from lib.knowledge_query import detect_knowledge_query, handle_knowledge_query
from lib.rcb_id import generate_rcb_id, RCBType
from lib.extraction_adapter import extract_text_from_attachments
from lib.rcb_helpers import helper_get_graph_token, helper_graph_messages, helper_graph_attachments, helper_graph_mark_read, helper_graph_send, to_hebrew_name, build_rcb_reply, get_rcb_secrets_internal, is_direct_recipient

# ── Optional agent imports (fail gracefully if modules have issues) ──
try:
    from lib.brain_commander import brain_commander_check, auto_learn_email_style
    BRAIN_COMMANDER_AVAILABLE = True
except ImportError as e:
    print(f"Brain Commander not available: {e}")
    BRAIN_COMMANDER_AVAILABLE = False

try:
    from lib.tracker import tracker_process_email, tracker_poll_active_deals, check_gate_cutoff_alerts
    TRACKER_AVAILABLE = True
except ImportError as e:
    print(f"Tracker not available: {e}")
    TRACKER_AVAILABLE = False

try:
    from lib.port_intelligence import (
        check_port_intelligence_alerts, build_port_alert_subject,
        build_port_alert_html, build_morning_digest, link_deal_to_schedule,
    )
    PORT_INTELLIGENCE_AVAILABLE = True
except ImportError as e:
    print(f"Port intelligence not available: {e}")
    PORT_INTELLIGENCE_AVAILABLE = False

try:
    from lib.pupil import pupil_process_email
    PUPIL_AVAILABLE = True
except ImportError as e:
    print(f"Pupil not available: {e}")
    PUPIL_AVAILABLE = False

try:
    from lib.schedule_il_ports import (
        build_all_port_schedules, is_schedule_email, process_schedule_email
    )
    SCHEDULE_AVAILABLE = True
except ImportError as e:
    print(f"Port schedule module not available: {e}")
    SCHEDULE_AVAILABLE = False

try:
    from lib.email_intent import process_email_intent
    EMAIL_INTENT_AVAILABLE = True
except ImportError as e:
    print(f"Email Intent not available: {e}")
    EMAIL_INTENT_AVAILABLE = False

try:
    from lib.email_triage import triage_email
    from lib.casual_handler import handle_casual
    EMAIL_TRIAGE_AVAILABLE = True
except ImportError as e:
    print(f"Email Triage not available: {e}")
    EMAIL_TRIAGE_AVAILABLE = False

try:
    from lib.consultation_handler import handle_consultation
    CONSULTATION_HANDLER_AVAILABLE = True
except ImportError as e:
    print(f"Consultation Handler not available: {e}")
    CONSULTATION_HANDLER_AVAILABLE = False

def get_secret(name):
    """Get secret from Google Cloud Secret Manager"""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        project_id = "rpa-port-customs"
        secret_path = f"projects/{project_id}/secrets/{name}/versions/latest"
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Secret {name} error: {e}")
        return None

from datetime import datetime, timedelta, timezone


# Initialize Firebase
firebase_admin.initialize_app()
db = None
bucket = None

def get_db():
    global db
    if db is None:
        db = firestore.client()
    return db

def get_bucket():
    global bucket
    if bucket is None:
        bucket = storage.bucket()
    return bucket




# ============================================================
# FUNCTION 2: AUTO-CLASSIFY ON NEW DOCUMENT
# ============================================================
@firestore_fn.on_document_created(document="classifications/{classId}")
def on_new_classification(event: firestore_fn.Event) -> None:
    """When a new classification is created, try to auto-classify using knowledge base"""
    try:
        data = event.data.to_dict()
        if data.get("status") != "pending_classification":
            return

        class_id = event.params["classId"]
        product = data.get("product_description", "")
        seller = data.get("seller", "")
        supplier_hs = data.get("supplier_hs", "")

        # Step 1: Check if we've seen this seller + product before
        suggested_hs = None
        confidence = 0

        # Check seller history
        if seller:
            seller_id = re.sub(r'[^a-zA-Z0-9]', '_', seller.lower())[:50]
            seller_doc = get_db().collection("sellers").document(seller_id).get()
            if seller_doc.exists:
                seller_data = seller_doc.to_dict()
                known_hs = seller_data.get("known_hs_codes", [])
                if len(known_hs) == 1:
                    suggested_hs = known_hs[0]
                    confidence = 70
                    print(f"Seller match: {seller} -> {suggested_hs}")

        # Check knowledge base for product match
        if product:
            kb_docs = get_db().collection("knowledge_base").where("category", "==", "hs_classifications").stream()
            for doc in kb_docs:
                kb = doc.to_dict()
                content = kb.get("content", {})
                products_seen = content.get("products", [])
                for p in products_seen:
                    if any(word.lower() in product.lower() for word in p.split() if len(word) > 3):
                        suggested_hs = content.get("hs", "")
                        confidence = max(confidence, 60)
                        print(f"Product match: {product} -> {suggested_hs}")
                        break

        # If supplier provided an HS code, validate it
        if supplier_hs:
            # Check if supplier HS matches our knowledge
            kb_match = get_db().collection("knowledge_base").where("category", "==", "hs_classifications").stream()
            for doc in kb_match:
                kb = doc.to_dict()
                if kb.get("content", {}).get("hs", "").replace(".", "") == supplier_hs.replace(".", ""):
                    suggested_hs = supplier_hs
                    confidence = 80
                    print(f"Supplier HS confirmed: {supplier_hs}")
                    break

        # Update classification with suggestion
        if suggested_hs and confidence >= 60:
            get_db().collection("classifications").document(class_id).update({
                "suggested_hs": suggested_hs,
                "suggestion_confidence": confidence,
                "suggestion_source": "auto_knowledge_base",
                "status": "pending_review"
            })
            print(f"Auto-suggested {suggested_hs} (confidence: {confidence}%) for {class_id}")
        else:
            # Need Claude AI for complex classification
            get_db().collection("agent_tasks").add({
                "type": "ai_classification",
                "classification_id": class_id,
                "product_description": product,
                "seller": seller,
                "supplier_hs": supplier_hs,
                "status": "pending",
                "created_at": firestore.SERVER_TIMESTAMP
            })
            print(f"Created AI classification task for {class_id}")
    except Exception as e:
        print(f"on_new_classification error (non-fatal, suppressed to prevent retry storm): {e}")
        import traceback; traceback.print_exc()


# ============================================================
# FUNCTION 3: LEARN FROM CORRECTIONS
# ============================================================
@firestore_fn.on_document_updated(document="classifications/{classId}")
def on_classification_correction(event: firestore_fn.Event) -> None:
    """When user corrects a classification, learn from it"""
    try:
        before = event.data.before.to_dict()
        after = event.data.after.to_dict()

        # Check if this is a correction (status changed to confirmed/corrected)
        if after.get("status") not in ("confirmed", "corrected"):
            return
        if before.get("status") == after.get("status"):
            return

        class_id = event.params["classId"]
        final_hs = after.get("our_hs_code", "")
        product = after.get("product_description", "")
        seller = after.get("seller", "")
        suggested_hs = before.get("suggested_hs", "")

        if not final_hs:
            return

        print(f"Learning from correction: {class_id}")
        print(f"  Product: {product}")
        print(f"  Final HS: {final_hs}")
        if suggested_hs and suggested_hs != final_hs:
            print(f"  Was suggested: {suggested_hs} (WRONG)")

        # Update seller knowledge
        if seller:
            seller_id = re.sub(r'[^a-zA-Z0-9]', '_', seller.lower())[:50]
            seller_ref = get_db().collection("sellers").document(seller_id)
            seller_doc = seller_ref.get()
            if seller_doc.exists:
                existing = seller_doc.to_dict()
                known_hs = existing.get("known_hs_codes", [])
                if final_hs not in known_hs:
                    known_hs.append(final_hs)
                seller_ref.update({"known_hs_codes": known_hs, "last_classification": datetime.now().isoformat()})
            else:
                seller_ref.set({
                    "name": seller,
                    "known_hs_codes": [final_hs],
                    "last_classification": datetime.now().isoformat()
                })

        # Update HS knowledge base
        hs_id = f"hs_{final_hs.replace('.', '_')}"
        hs_ref = get_db().collection("knowledge_base").document(hs_id)
        hs_doc = hs_ref.get()
        if hs_doc.exists:
            existing = hs_doc.to_dict()
            content = existing.get("content", {})
            products = content.get("products", [])
            sellers_list = content.get("sellers", [])
            if product and product not in products:
                products.append(product[:200])
            if seller and seller not in sellers_list:
                sellers_list.append(seller)
            content["products"] = products
            content["sellers"] = sellers_list
            hs_ref.update({"content": content, "last_updated": datetime.now().isoformat()})
        else:
            hs_ref.set({
                "title": f"HS {final_hs} - Learned from classification",
                "category": "hs_classifications",
                "content": {
                    "hs": final_hs,
                    "products": [product[:200]] if product else [],
                    "sellers": [seller] if seller else [],
                    "learned_from": [class_id]
                },
                "source": "classification_learning",
                "created_at": firestore.SERVER_TIMESTAMP
            })

        # ── Write to learned_corrections (Level -1 override for future classifications) ──
        if product:
            corr_id = re.sub(r'[^a-zA-Z0-9]', '_', product.lower()[:80])
            corr_doc = {
                "product": product[:200],
                "corrected_code": final_hs,
                "original_code": suggested_hs or "",
                "source": "human_correction",
                "reason": f"Manual correction by user on classification {class_id}",
                "learned_at": datetime.now().isoformat(),
                "seller": seller or "",
                "classification_id": class_id,
            }
            get_db().collection("learned_corrections").document(f"hc_{corr_id}").set(corr_doc, merge=True)
            print(f"  Written to learned_corrections: {product[:50]} -> {final_hs}")

        # Log the learning event
        get_db().collection("learning_log").add({
            "type": "classification_correction",
            "classification_id": class_id,
            "final_hs": final_hs,
            "suggested_hs": suggested_hs,
            "was_correct": suggested_hs == final_hs,
            "product": product,
            "seller": seller,
            "learned_at": firestore.SERVER_TIMESTAMP
        })

        print(f"  Learned: {product[:50]} -> {final_hs}")
    except Exception as e:
        print(f"on_classification_correction error (non-fatal, suppressed to prevent retry storm): {e}")
        import traceback; traceback.print_exc()


# ============================================================
# FUNCTION 4: ENRICHMENT (runs every hour)
# ============================================================
@scheduler_fn.on_schedule(schedule="every 1 hours", memory=options.MemoryOption.MB_256)
def enrich_knowledge(event: scheduler_fn.ScheduledEvent) -> None:
    """Periodically enrich knowledge base — Phase 3"""
    try:
        from lib.enrichment_agent import create_enrichment_agent
        from lib.librarian_index import rebuild_index

        enrichment = create_enrichment_agent(get_db())

        # 1. Check and tag any completed PC Agent downloads
        tagged = enrichment.check_and_tag_completed_downloads()
        print(f" Tagged {len(tagged)} completed downloads")

        # 2. Run scheduled enrichment tasks (checks 23 task types)
        summary = enrichment.run_scheduled_enrichments()
        print(f" Enrichment: checked {summary['tasks_checked']}, ran {summary['tasks_run']}")

        # 3. Get status for logging
        stats = enrichment.get_learning_stats()
        print(f" Knowledge: {stats['total_learned']} learned, "
              f"{stats['corrections']} corrections, "
              f"{stats['pc_agent_downloads']} downloads")

    except Exception as e:
        print(f" Enrichment error: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# FUNCTION 5: HTTP API FOR WEB APP
# ============================================================
def _check_api_auth(req) -> bool:
    """Verify Bearer token matches RCB_API_SECRET from Secret Manager."""
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth[7:]
    if not token:
        return False
    try:
        import hmac
        expected = get_secret("RCB_API_SECRET")
        if not expected:
            return False
        return hmac.compare_digest(token, expected)
    except Exception:
        return False


@https_fn.on_request(cors=options.CorsOptions(cors_origins="*", cors_methods=["GET", "POST"]))
def api(req: https_fn.Request) -> https_fn.Response:
    """REST API for the web application"""
    if not _check_api_auth(req):
        return https_fn.Response(json.dumps({"error": "Unauthorized"}), status=401, content_type="application/json")

    path = req.path.strip("/").replace("api/", "")

    method = req.method

    # Dashboard stats
    if path in ("stats", "") and method == "GET":
        def _count(query):
            """Firestore aggregation count — single RPC, no doc download."""
            return query.count().get()[0][0].value

        db = get_db()
        stats = {
            "knowledge_count": _count(db.collection("knowledge_base")),
            "inbox_count": _count(db.collection("inbox")),
            "classifications_pending": _count(db.collection("classifications").where("status", "==", "pending_classification")),
            "classifications_total": _count(db.collection("classifications")),
            "sellers_count": _count(db.collection("sellers")),
            "pending_tasks": _count(db.collection("pending_tasks").where("status", "==", "pending")),
            "learning_events": _count(db.collection("learning_log"))
        }
        return https_fn.Response(json.dumps(stats), content_type="application/json")

    # Get classifications
    elif path == "classifications" and method == "GET":
        result = []
        for doc in get_db().collection("classifications").order_by("created_at", direction=firestore.Query.DESCENDING).limit(50).stream():
            d = doc.to_dict()
            d["id"] = doc.id
            d.pop("extracted_text", None)  # Don't send large text
            result.append(d)
        return https_fn.Response(json.dumps(result, default=str), content_type="application/json")

    # Correct a classification (triggers learning)
    elif path.startswith("classifications/") and method == "POST":
        class_id = path.split("/")[1]
        data = req.get_json()
        get_db().collection("classifications").document(class_id).update({
            "our_hs_code": data.get("hs_code"),
            "status": "corrected" if data.get("is_correction") else "confirmed",
            "corrected_by": data.get("user", "admin"),
            "corrected_at": firestore.SERVER_TIMESTAMP
        })
        return https_fn.Response(json.dumps({"ok": True}), content_type="application/json")

    # Get knowledge base
    elif path == "knowledge" and method == "GET":
        result = []
        for doc in get_db().collection("knowledge_base").stream():
            d = doc.to_dict()
            d["id"] = doc.id
            result.append(d)
        return https_fn.Response(json.dumps(result, default=str), content_type="application/json")

    # Get inbox
    elif path == "inbox" and method == "GET":
        result = []
        for doc in get_db().collection("inbox").order_by("processed_at", direction=firestore.Query.DESCENDING).limit(50).stream():
            d = doc.to_dict()
            d["id"] = doc.id
            d.pop("body", None)
            result.append(d)
        return https_fn.Response(json.dumps(result, default=str), content_type="application/json")

    # Get sellers
    elif path == "sellers" and method == "GET":
        result = []
        for doc in get_db().collection("sellers").stream():
            d = doc.to_dict()
            d["id"] = doc.id
            result.append(d)
        return https_fn.Response(json.dumps(result, default=str), content_type="application/json")

    # Get learning log
    elif path == "learning" and method == "GET":
        result = []
        for doc in get_db().collection("learning_log").order_by("learned_at", direction=firestore.Query.DESCENDING).limit(50).stream():
            d = doc.to_dict()
            d["id"] = doc.id
            result.append(d)
        return https_fn.Response(json.dumps(result, default=str), content_type="application/json")

    return https_fn.Response(json.dumps({"error": "Not found"}), status=404, content_type="application/json")



# ============================================================
# RCB HELPER FUNCTIONS
# ============================================================

def graph_forward_email(access_token, user_email, message_id, to_email, comment):
    """Forward email"""
    import requests
    try:
        url = f"https://graph.microsoft.com/v1.0/users/{user_email}/messages/{message_id}/forward"
        requests.post(url, headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
                     json={'comment': comment, 'toRecipients': [{'emailAddress': {'address': to_email}}]})
        return True
    except Exception as e:
        print(f"Graph forward error: {e}")
        return False

def get_anthropic_key():
    """Get Anthropic API key"""
    return get_secret('ANTHROPIC_API_KEY')

# Hebrew name translations
@https_fn.on_request(cors=options.CorsOptions(cors_origins="*", cors_methods=["GET", "POST"]))
def rcb_api(req: https_fn.Request) -> https_fn.Response:
    """RCB API endpoints"""
    path = req.path.strip("/").split("/")[-1] if req.path else ""

    # Health check is public; everything else requires auth
    if path not in ("", "health") and not _check_api_auth(req):
        return https_fn.Response(json.dumps({"error": "Unauthorized"}), status=401, content_type="application/json")

    method = req.method

    # Health check
    if path == "" or path == "health":
        return https_fn.Response(json.dumps({"status": "ok", "service": "RCB API"}), content_type="application/json")
    
    # Get logs
    if path == "logs":
        logs = []
        for doc in get_db().collection("rcb_logs").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(50).stream():
            d = doc.to_dict()
            d["id"] = doc.id
            logs.append(d)
        return https_fn.Response(json.dumps(logs, default=str), content_type="application/json")
    
    # Test connection
    if path == "test":
        try:
            secrets = get_rcb_secrets_internal(get_secret)
        except Exception as e1:
            return https_fn.Response(json.dumps({"ok": False, "error": f"secrets error: {e1}"}), content_type="application/json")
        if not secrets:
            return https_fn.Response(json.dumps({"ok": False, "error": "No secrets returned"}), content_type="application/json")
        try:
            access_token = helper_get_graph_token(secrets)
        except Exception as e2:
            return https_fn.Response(json.dumps({"ok": False, "error": f"token error: {e2}"}), content_type="application/json")
        if access_token:
            return https_fn.Response(json.dumps({"ok": True, "email": secrets.get('RCB_EMAIL'), "method": "Graph API"}), content_type="application/json")
        return https_fn.Response(json.dumps({"ok": False, "error": "No token"}), content_type="application/json")
    
    # Save backup
    if path == "backup" and method == "POST":
        try:
            data = req.get_json()
            session_id = data.get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
            backup_content = data.get("content", "")
            get_db().collection("session_backups").document(session_id).set({
                "content": backup_content,
                "created_at": firestore.SERVER_TIMESTAMP,
                "session_id": session_id
            })
            # Email backup
            secrets = get_rcb_secrets_internal(get_secret)
            if secrets:
                access_token = helper_get_graph_token(secrets)
                if access_token:
                    helper_graph_send(access_token, secrets['RCB_EMAIL'],
                        secrets.get('RCB_FALLBACK_EMAIL', 'doron@rpa-port.co.il'),
                        f"[RCB Backup] Session {session_id}",
                        f"<pre>{backup_content}</pre>")
            return https_fn.Response(json.dumps({"ok": True, "session_id": session_id, "message": "Backup saved to Firestore and emailed"}), content_type="application/json")
        except Exception as e:
            return https_fn.Response(json.dumps({"ok": False, "error": str(e)}), status=500, content_type="application/json")
    
    # List backups
    if path == "backups":
        backups = []
        for doc in get_db().collection("session_backups").order_by("created_at", direction=firestore.Query.DESCENDING).limit(20).stream():
            d = doc.to_dict()
            backups.append({"id": doc.id, "session_id": d.get("session_id"), "created_at": str(d.get("created_at"))})
        return https_fn.Response(json.dumps(backups, default=str), content_type="application/json")
    
    # Get backup by ID
    if path.startswith("backup/"):
        bid = path.split("/")[1] if "/" in path else path.replace("backup", "")
        doc = get_db().collection("session_backups").document(bid).get()
        if doc.exists:
            return https_fn.Response(json.dumps(doc.to_dict(), default=str), content_type="application/json")
        return https_fn.Response(json.dumps({"error": "Not found"}), status=404, content_type="application/json")
    
    return https_fn.Response(json.dumps({"error": "Unknown endpoint"}), status=404, content_type="application/json")


# ============================================================
# FUNCTION 6: RCB EMAIL HANDLER - GRAPH API
# ============================================================

# ============================================================
# CLASSIFICATION PROCESSING (called after acknowledgment)
# ============================================================

def _aggregate_deal_text(db, deal_id):
    """Aggregate document text from all tracker observations for a deal."""
    deal = db.collection("tracker_deals").document(deal_id).get()
    if not deal.exists:
        return ""
    obs_ids = deal.to_dict().get('source_emails', [])
    if not obs_ids:
        return ""
    # Batch read — single RPC instead of N+1 individual gets
    obs_refs = [db.collection("tracker_observations").document(oid) for oid in obs_ids]
    docs = db.get_all(obs_refs)
    texts = []
    for doc in docs:
        if doc.exists:
            preview = doc.to_dict().get('doc_text_preview', '')
            if preview:
                texts.append(preview)
    return "\n\n---\n\n".join(texts)


def _run_gap2_silent_classification(db, firestore_module, deal_id, doc_text, get_secret_func):
    """Gap 2: Classify silently and store result on deal. No email sent.

    Called from CC path when a deal accumulates invoice + shipping doc.
    Returns dict with 'success' and 'classification_id' on success.
    """
    api_key = get_secret_func('ANTHROPIC_API_KEY')
    if not api_key:
        print(f"    Gap 2: No API key available — skipping")
        return {"success": False, "error": "no_api_key"}

    gemini_key = None
    openai_key = None
    try:
        gemini_key = get_secret_func('GEMINI_API_KEY')
    except Exception:
        pass
    try:
        openai_key = get_secret_func('OPENAI_API_KEY')
    except Exception:
        pass

    print(f"    Gap 2: {len(doc_text)} chars, classifying silently...")
    result = run_full_classification(
        api_key.strip(), doc_text, db,
        gemini_key=(gemini_key or '').strip() or None,
        openai_key=(openai_key or '').strip() or None,
    )

    update = {
        "classification_auto_triggered": True,
        "classification_auto_triggered_at": firestore_module.SERVER_TIMESTAMP,
        "classification_auto_triggered_via": "gap2_cc_silent",
        "classification_report_sent": False,  # Tracker poll will send and flip to True
    }

    if result and result.get("success"):
        hs_codes = []
        try:
            for c in (result.get("agents", {})
                      .get("classification", {})
                      .get("classifications", [])):
                hs = c.get("hs_code", "")
                if hs:
                    hs_codes.append({
                        "hs_code": hs,
                        "description": c.get("item", "")[:100],
                        "confidence": c.get("confidence", ""),
                    })
        except Exception:
            pass

        update["gap2_classification"] = {
            "success": True,
            "hs_codes": hs_codes,
            "synthesis": (result.get("synthesis") or "")[:2000],
        }

        # Store in rcb_classifications collection
        cls_id = ""
        try:
            ref = db.collection("rcb_classifications").add({
                "source": "gap2_cc_silent",
                "deal_id": deal_id,
                "classifications": hs_codes,
                "synthesis": (result.get("synthesis") or "")[:5000],
                "timestamp": firestore_module.SERVER_TIMESTAMP,
            })
            cls_id = ref[1].id if isinstance(ref, tuple) else getattr(ref, 'id', '')
            update["rcb_classification_id"] = cls_id
        except Exception as e:
            print(f"    Gap 2: rcb_classifications save error: {e}")

        db.collection("tracker_deals").document(deal_id).update(update)
        print(f"    Gap 2: Silent classification stored for deal {deal_id} ({len(hs_codes)} HS codes)")
        return {"success": True, "classification_id": cls_id, "hs_count": len(hs_codes)}
    else:
        update["gap2_classification"] = {
            "success": False,
            "error": (result or {}).get("error", "unknown"),
        }
        db.collection("tracker_deals").document(deal_id).update(update)
        print(f"    Gap 2: Classification failed — stored failure on deal {deal_id}")
        return {"success": False, "error": (result or {}).get("error", "unknown")}


def _build_gap2_report_html(deal_id, deal_data):
    """Build compact HTML notification for a Gap 2 silent classification result."""
    cls = deal_data.get("gap2_classification", {})
    hs_codes = cls.get("hs_codes", [])
    synthesis = cls.get("synthesis", "")
    bol = deal_data.get("bol_number", "")
    direction = deal_data.get("direction", "import")
    shipper = deal_data.get("shipper", "")

    hs_rows = ""
    for h in hs_codes[:10]:
        hs_rows += (
            f'<tr><td style="padding:6px 10px;border:1px solid #e0e0e0;font-family:monospace;font-size:14px">'
            f'{h.get("hs_code","")}</td>'
            f'<td style="padding:6px 10px;border:1px solid #e0e0e0;font-size:13px">'
            f'{h.get("description","")[:80]}</td>'
            f'<td style="padding:6px 10px;border:1px solid #e0e0e0;font-size:13px;text-align:center">'
            f'{h.get("confidence","")}</td></tr>'
        )

    html = (
        '<div style="font-family:Segoe UI,Arial,sans-serif;max-width:680px;margin:0 auto;direction:rtl">'
        '<div style="background:linear-gradient(135deg,#0f2439,#245a8a);color:#fff;padding:20px 24px;border-radius:10px 10px 0 0">'
        '<h2 style="margin:0;font-size:18px">RCB | סיווג אוטומטי (Gap 2)</h2>'
        f'<p style="margin:4px 0 0;font-size:12px;opacity:0.8">Deal: {deal_id} | B/L: {bol or "N/A"} | {direction}</p>'
        '</div>'
        '<div style="background:#fff;padding:20px 24px;border:1px solid #e0e0e0">'
        f'<p style="font-size:13px;color:#555">שוגר: {shipper or "לא ידוע"}</p>'
    )
    if synthesis:
        html += (
            '<div style="background:#f0f8ff;border-right:4px solid #245a8a;padding:12px;margin:12px 0;font-size:13px">'
            f'{synthesis[:1500]}</div>'
        )
    if hs_rows:
        html += (
            '<table style="width:100%;border-collapse:collapse;margin:12px 0">'
            '<tr style="background:#f5f5f5"><th style="padding:8px;border:1px solid #e0e0e0;text-align:right">קוד HS</th>'
            '<th style="padding:8px;border:1px solid #e0e0e0;text-align:right">תיאור</th>'
            '<th style="padding:8px;border:1px solid #e0e0e0;text-align:center">ביטחון</th></tr>'
            f'{hs_rows}</table>'
        )
    html += (
        '<p style="font-size:11px;color:#999;margin-top:16px">'
        'סיווג זה בוצע אוטומטית ממסמכים שהצטברו בתיק. נא לבדוק ולאשר.</p>'
        '</div>'
        '<div style="background:#f8faff;padding:12px 24px;border-radius:0 0 10px 10px;border:1px solid #e0e0e0;border-top:0">'
        '<p style="font-size:10px;color:#aaa;margin:0">RCB — Robot Customs Broker | R.P.A.PORT LTD</p>'
        '</div></div>'
    )
    return html


def _screen_deal_parties(db, deal_id, get_secret_func, access_token=None, rcb_email=None):
    """Screen shipper/consignee/notify party against OpenSanctions.
    Flag-only — never block. Logs to security_log on hit."""
    deal_doc = db.collection("tracker_deals").document(deal_id).get()
    if not deal_doc.exists:
        return
    deal = deal_doc.to_dict()
    # Skip if already screened recently
    if deal.get("sanctions_screened"):
        return
    # Collect party names to screen
    parties = []
    for field in ("shipper", "consignee", "notify_party"):
        name = (deal.get(field) or "").strip()
        if name and len(name) > 2:
            parties.append((field, name))
    if not parties:
        return
    from lib.tool_executors import ToolExecutor, sanitize_external_text
    api_key = ""
    try:
        api_key = get_secret_func("ANTHROPIC_API_KEY")
    except Exception:
        pass
    executor = ToolExecutor(db, api_key)
    any_hit = False
    hit_details = []
    for role, name in parties:
        try:
            result = executor.execute("check_opensanctions", {"query": name})
            if isinstance(result, dict) and result.get("hit"):
                any_hit = True
                hit_details.append({
                    "role": role,
                    "name": name,
                    "results": result.get("results", []),
                })
                print(f"  🚨 SANCTIONS HIT: {role}='{name}' in deal {deal_id}")
        except Exception:
            pass
    # Mark deal as screened
    try:
        update = {"sanctions_screened": True, "sanctions_screened_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat()}
        if any_hit:
            update["sanctions_hit"] = True
            update["sanctions_details"] = hit_details
        db.collection("tracker_deals").document(deal_id).update(update)
    except Exception:
        pass
    # If hit: log to security_log + send alert
    if any_hit:
        try:
            from datetime import datetime, timezone
            db.collection("security_log").add({
                "type": "SANCTIONS_HIT",
                "deal_id": deal_id,
                "details": hit_details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        # Send alert email
        try:
            from lib.rcb_helpers import helper_graph_send
            if access_token and rcb_email:
                names_str = ", ".join(f"{d['role']}: {d['name']}" for d in hit_details)
                helper_graph_send(
                    access_token, rcb_email,
                    "doron@rpa-port.co.il",
                    f"🚨 SANCTIONS HIT — Deal {deal_id}",
                    f"<p>Sanctions screening found matches:</p>"
                    f"<p><b>{names_str}</b></p>"
                    f"<p>Deal ID: {deal_id}</p>"
                    f"<p>Action required: Manual review.</p>"
                    f"<p>Details: {len(hit_details)} hit(s)</p>",
                )
                print(f"  📧 Sanctions alert sent to doron@rpa-port.co.il")
        except Exception as e:
            print(f"  ⚠️ Sanctions alert email failed: {e}")


def _run_port_intelligence_alerts(db, firestore_module, access_token, rcb_email):
    """I3: Check all active deals for port intelligence alerts and send emails to CC.

    Dedup via deal.port_alerts_sent[] — each alert type sent once per deal.
    Sends to cc@rpa-port.co.il (the CC group, NOT a reply).
    """
    if not PORT_INTELLIGENCE_AVAILABLE:
        return {"status": "skipped", "reason": "port_intelligence not available"}

    cc_email = "cc@rpa-port.co.il"
    alerts_sent = 0
    deals_checked = 0

    try:
        deal_snaps = list(
            db.collection("tracker_deals")
            .where("status", "in", ["active", "pending"])
            .stream()
        )
    except Exception as e:
        print(f"  ⚠️ I3 alert query failed: {e}")
        return {"status": "error", "error": str(e)}

    for snap in deal_snaps:
        deal = snap.to_dict()
        deal_id = snap.id
        deals_checked += 1

        # Load container statuses (batch query)
        try:
            cs_snaps = list(
                db.collection("tracker_container_status")
                .where("deal_id", "==", deal_id)
                .stream()
            )
            container_statuses = [c.to_dict() for c in cs_snaps]
        except Exception:
            container_statuses = []

        # Check alerts (pure function — no side effects)
        try:
            alerts = check_port_intelligence_alerts(
                deal_id, deal, container_statuses
            )
        except Exception as ae:
            print(f"  ⚠️ I3 alert check error for {deal_id}: {ae}")
            continue

        if not alerts:
            continue

        # Dedup: filter out already-sent alert types
        already_sent = set(deal.get("port_alerts_sent", []))
        new_alerts = [a for a in alerts if a["type"] not in already_sent]
        if not new_alerts:
            continue

        # Send each new alert
        sent_types = []
        for alert in new_alerts:
            try:
                subject = build_port_alert_subject(alert)
                body_html = build_port_alert_html(alert)
                ok = helper_graph_send(
                    access_token, rcb_email, cc_email, subject, body_html
                )
                if ok:
                    sent_types.append(alert["type"])
                    alerts_sent += 1
                    print(f"  🚨 I3 alert sent: {subject}")
            except Exception as se:
                print(f"  ⚠️ I3 alert send error: {se}")

        # Update deal with sent alert types
        if sent_types:
            try:
                new_sent = list(already_sent | set(sent_types))
                db.collection("tracker_deals").document(deal_id).update({
                    "port_alerts_sent": new_sent,
                })
            except Exception as ue:
                print(f"  ⚠️ I3 dedup update failed for {deal_id}: {ue}")

    return {
        "status": "ok",
        "deals_checked": deals_checked,
        "alerts_sent": alerts_sent,
    }


@scheduler_fn.on_schedule(schedule="every 2 minutes", memory=options.MemoryOption.GB_1, timeout_sec=540)
def rcb_check_email(event: scheduler_fn.ScheduledEvent) -> None:
    """Check rcb@rpa-port.co.il inbox - process emails from last 2 days"""
    try:
        _rcb_check_email_inner(event)
    except Exception as e:
        import traceback
        print(f"❌ rcb_check_email top-level error: {e}")
        traceback.print_exc()


def _rcb_check_email_inner(event) -> None:
    """Inner implementation — called by rcb_check_email with top-level guard."""
    print("🤖 RCB checking email via Graph API...")
    
    secrets = get_rcb_secrets_internal(get_secret)
    if not secrets:
        print("❌ No secrets configured")
        return
    
    rcb_email = secrets.get('RCB_EMAIL', 'rcb@rpa-port.co.il')
    
    access_token = helper_get_graph_token(secrets)
    if not access_token:
        print("❌ Failed to get access token")
        return
    
    # Get ALL messages from last 2 days (ignore read/unread)
    from datetime import datetime, timedelta, timezone
    # Session 47: Restored 2-day lookback (was temporarily 2h after hash fix)
    two_days_ago = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    url = f"https://graph.microsoft.com/v1.0/users/{rcb_email}/mailFolders/inbox/messages"
    params = {
        '$top': 50,
        '$orderby': 'receivedDateTime desc',
        '$filter': f"receivedDateTime ge {two_days_ago}"
    }
    
    import requests
    response = requests.get(url, headers={'Authorization': f'Bearer {access_token}'}, params=params)
    messages = response.json().get('value', []) if response.status_code == 200 else []
    
    if not messages:
        print("📭 No messages in last 2 days")
        return
    
    print(f"📬 Found {len(messages)} messages in last 2 days")
    
    for msg in messages:
        msg_id = msg.get('id')
        internet_msg_id = msg.get('internetMessageId', '')  # RFC 2822 Message-ID for threading
        subject = msg.get('subject', 'No Subject')
        from_data = msg.get('from', {}).get('emailAddress', {})
        from_email = from_data.get('address', '')
        from_name = from_data.get('name', '')
        to_recipients = msg.get('toRecipients', [])
        
        # Check if sent TO rcb@ (not CC)
        is_direct = any(rcb_email.lower() in r.get('emailAddress', {}).get('address', '').lower() 
                       for r in to_recipients)
        
        print(f"    DEBUG: {subject[:30]} from={from_email} is_direct={is_direct}")

        # Skip system emails for all paths
        if from_email.lower() == rcb_email.lower():
            continue  # Never process our own outgoing emails (prevents feedback loop)
        if from_email.lower() == 'cc@rpa-port.co.il':
            continue  # Session 47: Digest group — read only, never process as sender
        if 'undeliverable' in subject.lower() or 'backup' in subject.lower():
            continue
        if '[RCB-SELFTEST]' in subject:
            continue

        # Session 73: Skip auto-replies / out-of-office (prevents reply loops)
        _subj_lower = subject.lower()
        if any(s in _subj_lower for s in ('אני לא נמצא', 'automatic reply', 'out of office', 'שליחה אוטומטית')):
            helper_graph_mark_read(access_token, rcb_email, msg_id)
            continue
        # Check X-Auto-Response-Suppress header (Graph exposes as internetMessageHeaders)
        _msg_headers = msg.get('internetMessageHeaders') or []
        if any(h.get('name', '').lower() == 'x-auto-response-suppress' for h in _msg_headers):
            helper_graph_mark_read(access_token, rcb_email, msg_id)
            continue
        # OOO from doron@ with "אשוב" in body
        if from_email.lower() == 'doron@rpa-port.co.il':
            _body_preview = (msg.get('bodyPreview') or msg.get('body', {}).get('content', '') or '')[:500]
            if 'אשוב' in _body_preview:
                helper_graph_mark_read(access_token, rcb_email, msg_id)
                continue

        # ── Block A2: Customs declarations forwarded from airpaport@gmail ──
        if '[DECL]' in subject.upper():
            import hashlib as _hl_decl
            safe_id_decl = _hl_decl.md5(msg_id.encode()).hexdigest()
            if get_db().collection("rcb_processed").document(safe_id_decl).get().exists:
                continue
            print(f"  📜 Declaration received: {subject[:50]} from {from_email}")
            try:
                decl_attachments = helper_graph_attachments(access_token, rcb_email, msg_id)
                decl_body = msg.get('body', {}).get('content', '') or msg.get('bodyPreview', '')
                decl_doc = {
                    "received_at": firestore.SERVER_TIMESTAMP,
                    "subject": subject,
                    "from": from_email,
                    "from_name": from_name,
                    "msg_id": msg_id,
                    "internet_message_id": internet_msg_id,
                    "body": decl_body[:50000],  # Cap at 50k chars
                    "attachment_count": len(decl_attachments),
                    "attachments": [
                        {"name": a.get("name", ""), "size": a.get("size", 0),
                         "contentType": a.get("contentType", "")}
                        for a in decl_attachments
                        if a.get("@odata.type") == "#microsoft.graph.fileAttachment"
                    ],
                    "status": "pending_parse",  # Block G will process
                }
                get_db().collection("declarations_raw").add(decl_doc)
                print(f"  ✅ Declaration saved ({len(decl_attachments)} attachments)")
            except Exception as decl_err:
                print(f"  ⚠️ Declaration save error (non-fatal): {decl_err}")
            helper_graph_mark_read(access_token, rcb_email, msg_id)
            get_db().collection("rcb_processed").document(safe_id_decl).set({
                "processed_at": firestore.SERVER_TIMESTAMP,
                "subject": subject,
                "from": from_email,
                "type": "declaration_received",
            })
            continue

        # ── CC emails: silent learning from ALL senders, no reply ──
        if not is_direct:
            import hashlib as _hl
            safe_id_cc = _hl.md5(msg_id.encode()).hexdigest()
            if get_db().collection("rcb_processed").document(safe_id_cc).get().exists:
                continue

            print(f"  👁️ CC observation: {subject[:50]} from {from_email}")

            # Pupil: silent observation (FREE — Firestore only, no replies)
            if PUPIL_AVAILABLE:
                try:
                    pupil_process_email(
                        msg, get_db(), firestore, access_token, rcb_email, get_secret
                    )
                except Exception as pe:
                    print(f"    ⚠️ Pupil CC error (non-fatal): {pe}")

            # Tracker: observe shipping updates (FREE — no notifications when is_direct=False)
            tracker_result = None
            if TRACKER_AVAILABLE:
                try:
                    tracker_result = tracker_process_email(
                        msg, get_db(), firestore, access_token, rcb_email, get_secret,
                        is_direct=False
                    )
                except Exception as te:
                    print(f"    ⚠️ Tracker CC error (non-fatal): {te}")

            # Sanctions screening: check shipper/consignee from tracker deal
            if tracker_result and tracker_result.get("deal_id"):
                try:
                    _screen_deal_parties(get_db(), tracker_result["deal_id"],
                                         get_secret, access_token, rcb_email)
                except Exception as san_err:
                    print(f"    ⚠️ Sanctions screening error (non-fatal): {san_err}")

            # Schedule: detect vessel schedule emails (FREE — Firestore only)
            if SCHEDULE_AVAILABLE:
                try:
                    _sched_body = msg.get('body', {}).get('content', '') or msg.get('bodyPreview', '')
                    if is_schedule_email(subject, _sched_body, from_email):
                        print(f"  🚢 Schedule email detected: {subject[:50]}")
                        process_schedule_email(
                            get_db(), subject, _sched_body, from_email, msg_id
                        )
                except Exception as se:
                    print(f"    ⚠️ Schedule CC error (non-fatal): {se}")

            # Session 79: CC path = process/learn/prepare silently, NEVER send.
            # Gap 2: When deal accumulates invoice + shipping doc → classify silently,
            # store result on deal. Email send happens in tracker poll.
            if (tracker_result and tracker_result.get("classification_ready")
                    and tracker_result.get("deal_id")):
                try:
                    _gap2_deal_id = tracker_result["deal_id"]
                    print(f"  📋 Gap 2: Deal {_gap2_deal_id} ready for classification")
                    _gap2_text = _aggregate_deal_text(get_db(), _gap2_deal_id)
                    if _gap2_text and len(_gap2_text) > 50:
                        _run_gap2_silent_classification(
                            get_db(), firestore, _gap2_deal_id, _gap2_text, get_secret)
                    else:
                        print(f"    Gap 2: text too short ({len(_gap2_text or '')} chars)")
                except Exception as gap2_err:
                    print(f"    ⚠️ Gap 2 auto-trigger error (non-fatal): {gap2_err}")

            get_db().collection("rcb_processed").document(safe_id_cc).set({
                "processed_at": firestore.SERVER_TIMESTAMP,
                "subject": subject,
                "from": from_email,
                "type": "cc_observation",
            })
            continue

        # ── Direct TO emails: full pipeline from ANY sender ──
        # Session 79: RCB replies ONLY when rcb@ is SOLE TO recipient.
        # Reply goes to sender if @rpa-port.co.il, or to team member in CC chain.
        _reply_to = None
        _is_sole_to = is_direct_recipient(msg, rcb_email, sole=True)
        if _is_sole_to:
            _sender_lower = from_email.lower()
            if (_sender_lower.endswith('@rpa-port.co.il')
                    and _sender_lower != 'cc@rpa-port.co.il'
                    and _sender_lower != rcb_email.lower()):
                _reply_to = from_email  # Team sender — reply directly
                print(f"    📬 Sole-TO from {from_email} → will reply")
            else:
                # External sender or system address — find team member in CC chain
                for _r in msg.get('ccRecipients', []):
                    _addr = (_r.get('emailAddress', {}).get('address', '') or '').lower()
                    if (_addr.endswith('@rpa-port.co.il')
                            and _addr != rcb_email.lower()
                            and _addr != 'cc@rpa-port.co.il'):
                        _reply_to = _r.get('emailAddress', {}).get('address', '')
                        break
                if _reply_to:
                    print(f"    📬 External sender {from_email} → reply to CC team member {_reply_to}")
                else:
                    print(f"    📬 External sender {from_email} → no team in chain, classify only")
        else:
            print(f"    📬 rcb@ not sole TO recipient — classify only, no reply")

        # Check if already processed
        import hashlib; safe_id = hashlib.md5(msg_id.encode()).hexdigest()
        if get_db().collection("rcb_processed").document(safe_id).get().exists:
            continue
        
        print(f"  📧 Processing: {subject[:50]} from {from_email}")
        
        # Get attachments
        raw_attachments = helper_graph_attachments(access_token, rcb_email, msg_id)
        attachments = []
        for att in raw_attachments:
            if att.get('@odata.type') == '#microsoft.graph.fileAttachment':
                name = att.get('name', 'file')
                ext = os.path.splitext(name)[1].lower()
                attachments.append({'filename': name, 'type': ext})
        
        print(f"    📎 {len(attachments)} attachments")

        # ── Brain Commander: Father channel check ──
        # If doron@ sends a brain command, handle it and skip classification
        if BRAIN_COMMANDER_AVAILABLE:
            try:
                brain_result = brain_commander_check(msg, get_db(), access_token, rcb_email, get_secret)
                if brain_result and brain_result.get('handled'):
                    print(f"    🧠 Brain Commander handled: {brain_result.get('command', {}).get('type', 'unknown')}")
                    helper_graph_mark_read(access_token, rcb_email, msg_id)
                    get_db().collection("rcb_processed").document(safe_id).set({
                        "processed_at": firestore.SERVER_TIMESTAMP,
                        "subject": subject,
                        "from": from_email,
                        "type": "brain_command",
                    })
                    continue
            except Exception as bc_err:
                print(f"    ⚠️ Brain Commander error (continuing normally): {bc_err}")

        # ── Three-Layer Email Triage (Session 74) ──
        # Sits ON TOP of legacy flow. If triage handles it → continue.
        # If not → legacy flow runs exactly as before.
        _triage_handled = False
        if EMAIL_TRIAGE_AVAILABLE:
            try:
                triage_result = triage_email(msg, rcb_email, db=get_db(), get_secret_func=get_secret)

                # Log triage decision to rcb_debug
                try:
                    get_db().collection("rcb_debug").add({
                        "type": "triage",
                        "category": triage_result.category,
                        "confidence": triage_result.confidence,
                        "source": triage_result.source,
                        "skip_reason": triage_result.skip_reason,
                        "subject": subject,
                        "sender": from_email,
                        "timestamp": firestore.SERVER_TIMESTAMP,
                    })
                except Exception:
                    pass  # debug logging should never break flow

                if triage_result.category == "SKIP":
                    print(f"    ⏭️ Triage SKIP: {triage_result.skip_reason} | {subject[:40]}")
                    helper_graph_mark_read(access_token, rcb_email, msg_id)
                    get_db().collection("rcb_processed").document(safe_id).set({
                        "processed_at": firestore.SERVER_TIMESTAMP,
                        "subject": subject,
                        "from": from_email,
                        "type": f"triage_skip_{triage_result.skip_reason or 'generic'}",
                    })
                    _triage_handled = True

                elif triage_result.category == "CASUAL":
                    print(f"    💬 Triage CASUAL ({triage_result.confidence:.2f} via {triage_result.source})")
                    casual_result = handle_casual(msg, access_token, rcb_email, get_secret, db=get_db())
                    if casual_result.get("status", "").startswith("replied"):
                        helper_graph_mark_read(access_token, rcb_email, msg_id)
                        get_db().collection("rcb_processed").document(safe_id).set({
                            "processed_at": firestore.SERVER_TIMESTAMP,
                            "subject": subject,
                            "from": from_email,
                            "type": "triage_casual",
                            "tracking_code": casual_result.get("tracking_code", ""),
                        })
                        _triage_handled = True

                elif triage_result.category == "REPLY_THREAD":
                    pass  # Session 75: thread_manager will handle this — falls through to legacy

                elif triage_result.category == "LIVE_SHIPMENT":
                    if CONSULTATION_HANDLER_AVAILABLE:
                        try:
                            ship_result = handle_consultation(
                                msg, get_db(), firestore, access_token, rcb_email,
                                get_secret, triage_result=triage_result,
                                template_type="live_shipment")
                            if ship_result.get("status") in ("replied", "delegated"):
                                helper_graph_mark_read(access_token, rcb_email, msg_id)
                                get_db().collection("rcb_processed").document(safe_id).set({
                                    "processed_at": firestore.SERVER_TIMESTAMP,
                                    "subject": subject,
                                    "from": from_email,
                                    "type": "triage_live_shipment",
                                    "level": ship_result.get("level", 0),
                                    "model": ship_result.get("model", ""),
                                })
                                _triage_handled = True
                        except Exception as ship_err:
                            print(f"    ⚠️ Live shipment handler error (falling through): {ship_err}")

                elif triage_result.category == "CONSULTATION":
                    if CONSULTATION_HANDLER_AVAILABLE:
                        try:
                            cons_result = handle_consultation(
                                msg, get_db(), firestore, access_token, rcb_email,
                                get_secret, triage_result=triage_result)
                            if cons_result.get("status") in ("replied", "delegated"):
                                helper_graph_mark_read(access_token, rcb_email, msg_id)
                                get_db().collection("rcb_processed").document(safe_id).set({
                                    "processed_at": firestore.SERVER_TIMESTAMP,
                                    "subject": subject,
                                    "from": from_email,
                                    "type": "triage_consultation",
                                    "level": cons_result.get("level", 0),
                                    "model": cons_result.get("model", ""),
                                })
                                _triage_handled = True
                        except Exception as cons_err:
                            print(f"    ⚠️ Consultation handler error (falling through): {cons_err}")
                            try:
                                get_db().collection("rcb_debug").add({
                                    "type": "consultation_error",
                                    "error": str(cons_err),
                                    "subject": subject,
                                    "timestamp": firestore.SERVER_TIMESTAMP,
                                })
                            except Exception:
                                pass
                    # If not available or failed, falls through to legacy flow

            except Exception as triage_err:
                # Log error but NEVER break email processing
                print(f"    ⚠️ Triage error (non-fatal): {triage_err}")
                try:
                    get_db().collection("rcb_debug").add({
                        "type": "triage_error",
                        "error": str(triage_err),
                        "subject": subject,
                        "sender": from_email,
                        "timestamp": firestore.SERVER_TIMESTAMP,
                    })
                except Exception:
                    pass

        if _triage_handled:
            continue

        # ── Email Intent: smart routing for direct emails ──
        if EMAIL_INTENT_AVAILABLE:
            try:
                intent_result = process_email_intent(
                    msg, get_db(), firestore, access_token, rcb_email, get_secret
                )
                _intent_name = intent_result.get('intent', 'NONE')
                _intent_status = intent_result.get('status', '')
                # If a real intent was detected AND it's not a classify instruction
                if _intent_name not in ('NONE', '') and not (
                    _intent_name == 'INSTRUCTION' and intent_result.get('action') == 'classify'
                ):
                    # BUG #2 FIX: Only consume email if send actually succeeded.
                    # If send_failed → do NOT mark as read, do NOT continue.
                    # Let email fall through to knowledge_query / classification.
                    if _intent_status in ('replied', 'cache_hit', 'clarification_sent'):
                        print(f"  🧠 Email intent handled: {_intent_name} (status={_intent_status})")
                        helper_graph_mark_read(access_token, rcb_email, msg_id)
                        get_db().collection("rcb_processed").document(safe_id).set({
                            "processed_at": firestore.SERVER_TIMESTAMP,
                            "subject": subject,
                            "from": from_email,
                            "type": f"intent_{_intent_name}",
                        })
                        # Debug logging for every processed intent
                        try:
                            get_db().collection("rcb_debug").add({
                                "timestamp": firestore.SERVER_TIMESTAMP,
                                "event": "email_processed",
                                "intent": _intent_name,
                                "status": _intent_status,
                                "subject": subject,
                                "from": from_email,
                                "msg_id": msg_id,
                                "product_description": intent_result.get("entities", {}).get("product_description", "") if isinstance(intent_result.get("entities"), dict) else "",
                                "tariff_results": str(intent_result.get("answer_sources", []))[:500],
                                "html_composed": bool(intent_result.get("answer_html")),
                                "send_status": _intent_status,
                                "failure_reason": None,
                            })
                        except Exception:
                            pass
                        continue
                    else:
                        # send_failed or other non-success status — log to debug, fall through
                        print(f"  ⚠️ Email intent detected: {_intent_name} but status={_intent_status} — NOT consuming email, falling through")
                        try:
                            get_db().collection("rcb_debug").add({
                                "timestamp": firestore.SERVER_TIMESTAMP,
                                "event": "intent_send_failed",
                                "intent": _intent_name,
                                "status": _intent_status,
                                "subject": subject,
                                "from": from_email,
                                "msg_id": msg_id,
                                "product_description": intent_result.get("entities", {}).get("product_description", "") if isinstance(intent_result.get("entities"), dict) else "",
                                "tariff_results": str(intent_result.get("answer_sources", []))[:500],
                                "html_composed": bool(intent_result.get("answer_html")),
                                "send_status": _intent_status,
                                "failure_reason": intent_result.get('failure_reason', _intent_status),
                            })
                        except Exception:
                            pass
                # INSTRUCTION intent with action='classify' → fall through to classification
            except Exception as ei_err:
                print(f"  ⚠️ Email intent error (non-fatal): {ei_err}")

        # ── Session 13 v4.1.0: Knowledge Query Detection ──
        # If team member asks a question (no commercial docs), answer it
        # and skip the classification pipeline entirely.
        try:
            msg["attachments"] = raw_attachments
            if detect_knowledge_query(msg):
                try:
                    rcb_id = generate_rcb_id(get_db(), firestore, RCBType.KNOWLEDGE_QUERY)
                except Exception:
                    rcb_id = "RCB-UNKNOWN-KQ"
                print(f"  📚 [{rcb_id}] Knowledge query detected from {from_email}")
                kq_result = handle_knowledge_query(
                    msg=msg,
                    db=get_db(),
                    firestore_module=firestore,
                    access_token=access_token,
                    rcb_email=rcb_email,
                    get_secret_func=get_secret,
                )
                print(f"  📚 [{rcb_id}] Knowledge query result: {kq_result.get('status')}")
                helper_graph_mark_read(access_token, rcb_email, msg_id)
                get_db().collection("rcb_processed").document(safe_id).set({
                    "processed_at": firestore.SERVER_TIMESTAMP,
                    "subject": subject,
                    "from": from_email,
                    "type": "knowledge_query",
                    "rcb_id": rcb_id,
                })
                continue
        except Exception as kq_err:
            print(f"  ⚠️ Knowledge query detection error: {kq_err}")

        # ── Shipping-only routing: BL/AWB/booking without invoice → tracker ──
        if attachments:
            _invoice_kw = ['invoice', 'חשבונית', 'proforma', 'ci_']
            _shipping_kw = [
                'bill of lading', 'bl_', 'bol_', 'bol ', 'b_l', 'b/l',
                'שטר מטען', 'שטר',
                'awb', 'air waybill', 'airwaybill',
                'booking', 'הזמנה',
                'delivery order', 'פקודת מסירה', 'do_',
                'air delivery order', 'ado_', 'cargo release', 'שחרור מטען אווירי',
                'packing', 'רשימת אריזה', 'pl_',
            ]
            _cls_intent = ['סיווג', 'classify', 'classification', 'קוד מכס', 'hs code', 'לסווג']

            _has_inv = False
            _has_ship = False
            for att in attachments:
                fn = att.get('filename', '').lower()
                if any(kw in fn for kw in _invoice_kw):
                    _has_inv = True
                if any(kw in fn for kw in _shipping_kw):
                    _has_ship = True

            if _has_ship and not _has_inv:
                # Check body for classification intent — "please classify" overrides
                _body_text = msg.get('body', {}).get('content', '') or msg.get('bodyPreview', '')
                _combined = f"{subject} {_body_text}".lower()
                if not any(kw in _combined for kw in _cls_intent):
                    print(f"  📦 Shipping docs only (no invoice) — routing to tracker, skipping classification")
                    if TRACKER_AVAILABLE:
                        try:
                            tracker_process_email(msg, get_db(), firestore, access_token, rcb_email, get_secret, is_direct=is_direct)
                        except Exception as te:
                            print(f"    ⚠️ Tracker error: {te}")
                    if PUPIL_AVAILABLE:
                        try:
                            pupil_process_email(msg, get_db(), firestore, access_token, rcb_email, get_secret)
                        except Exception as pe:
                            print(f"    ⚠️ Pupil error: {pe}")
                    helper_graph_mark_read(access_token, rcb_email, msg_id)
                    get_db().collection("rcb_processed").document(safe_id).set({
                        "processed_at": firestore.SERVER_TIMESTAMP,
                        "subject": subject,
                        "from": from_email,
                        "type": "shipping_tracker",
                    })
                    continue

        # ── External sender rate limiting (before expensive classification) ──
        if not from_email.lower().endswith('@rpa-port.co.il'):
            try:
                _cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
                _recent = list(
                    get_db().collection("rcb_processed")
                    .where("from", "==", from_email.lower())
                    .where("processed_at", ">=", _cutoff)
                    .limit(5)
                    .stream()
                )
                if len(_recent) >= 5:
                    print(f"  🚫 Rate limited external sender {from_email}: {len(_recent)} classifications in last hour")
                    get_db().collection("security_log").add({
                        "type": "EXTERNAL_RATE_LIMITED",
                        "from_email": from_email,
                        "count": len(_recent),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    helper_graph_mark_read(access_token, rcb_email, msg_id)
                    continue
            except Exception as rl_err:
                print(f"    ⚠️ Rate limit check error (proceeding): {rl_err}")

        # Consolidated: ONE email with ack + classification + clarification
        try:
            rcb_id = generate_rcb_id(get_db(), firestore, RCBType.CLASSIFICATION)
        except Exception:
            rcb_id = "RCB-UNKNOWN-CLS"
        print(f"  🏷️ [{rcb_id}] Processing classification")

        # Mark as processed immediately to prevent double-processing
        get_db().collection("rcb_processed").document(safe_id).set({
            "processed_at": firestore.SERVER_TIMESTAMP,
            "subject": subject,
            "from": from_email,
            "rcb_id": rcb_id,
        })

        try:
            # Extract email body for URL detection and context
            email_body = msg.get('body', {}).get('content', '') or msg.get('bodyPreview', '')
            if msg.get('body', {}).get('contentType', '') == 'html' and email_body:
                import re as _re
                email_body = _re.sub(r'<[^>]+>', ' ', email_body)
                email_body = _re.sub(r'\s+', ' ', email_body).strip()

            # Session 47: Reply routing — reply_to is @rpa-port.co.il or None
            process_and_send_report(
                access_token, rcb_email, _reply_to, subject,
                from_name, raw_attachments, msg_id, get_secret,
                get_db(), firestore, helper_graph_send, extract_text_from_attachments,
                email_body=email_body,
                internet_message_id=internet_msg_id,
            )
        except Exception as ce:
            print(f"    ⚠️ Classification error: {ce}")

        # ── Tracker: Feed email as observation for deal tracking ──
        if TRACKER_AVAILABLE:
            try:
                tracker_process_email(
                    msg, get_db(), firestore, access_token, rcb_email, get_secret,
                    is_direct=is_direct
                )
            except Exception as te:
                print(f"    ⚠️ Tracker error (non-fatal): {te}")

        # ── Pupil: Passive learning from every email ──
        if PUPIL_AVAILABLE:
            try:
                pupil_process_email(
                    msg, get_db(), firestore, access_token, rcb_email, get_secret
                )
            except Exception as pe:
                print(f"    ⚠️ Pupil error (non-fatal): {pe}")

    print("✅ RCB check complete")



# ============================================================================
# MONITOR AGENT

# ============================================================================
# MONITOR AGENT
# ============================================================================

@scheduler_fn.on_schedule(
    schedule="every 5 minutes",
    region="us-central1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=180
)
def monitor_agent(event: scheduler_fn.ScheduledEvent) -> None:
    """RCB System Monitor - runs every 5 minutes, auto-fixes known issues"""
    print("🤖 Monitor Agent starting...")
    
    errors_fixed = 0
    errors_escalated = 0
    
    try:
        # CRIT-4: Checks 1+2 DISABLED — they deleted rcb_processed dedup markers,
        # causing re-processing storms for CC/tracker/brain emails that don't produce
        # rcb_classifications. rcb_ttl_cleanup (03:30 daily) handles housekeeping
        # with backup guards. See AUDIT_2202_1457.md CRIT-4.

        from datetime import datetime, timezone
        processed_count = len(list(get_db().collection("rcb_processed").limit(25).stream()))

        # Check 3: System status update (read-only, no deletions)
        get_db().collection("system_status").document("rcb_monitor").set({
            "last_check": datetime.now(timezone.utc),
            "status": "healthy",
            "queue_size": processed_count,
            "errors_fixed": 0,
            "pending_retries": 0,
        })

        print(f"✅ Monitor complete: queue_size={processed_count}, no destructive actions")
        
    except Exception as e:
        print(f"❌ Monitor error: {e}")
        import traceback
        traceback.print_exc()

@https_fn.on_request(region="us-central1")
def monitor_agent_manual(req: https_fn.Request) -> https_fn.Response:
    """Manual trigger for testing"""
    print("🤖 Manual monitor trigger...")
    return https_fn.Response("Monitor OK", status=200)

# ============================================================
# AUTO-CLEANUP: Remove old rcb_processed docs (older than 7 days)
# ============================================================
@scheduler_fn.on_schedule(schedule="every 24 hours")
def rcb_cleanup_old_processed(event: scheduler_fn.ScheduledEvent) -> None:
    """Delete rcb_processed documents older than 7 days"""
    print("🧹 Starting cleanup of old processed records...")
    
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    
    deleted = 0
    try:
        docs = get_db().collection("rcb_processed").stream()
        for doc in docs:
            data = doc.to_dict()
            processed_at = data.get("processed_at")
            if processed_at and processed_at < cutoff:
                doc.reference.delete()
                deleted += 1
                print(f"  🗑️ Deleted: {data.get('subject', 'unknown')[:30]}")
    except Exception as e:
        print(f"❌ Cleanup error: {e}")
    
    print(f"✅ Cleanup complete: {deleted} old records deleted")


# ============================================================
# TTL CLEANUP: scanner_logs + log collections (Assignment 16)
# Runs daily at 03:30 Jerusalem time — after nightly jobs finish
# ============================================================
@scheduler_fn.on_schedule(
    schedule="every day 03:30",
    timezone=scheduler_fn.Timezone("Asia/Jerusalem"),
    memory=options.MemoryOption.GB_1,
    timeout_sec=540,
)
def rcb_ttl_cleanup(event: scheduler_fn.ScheduledEvent) -> None:
    """Daily TTL cleanup for large/growing collections.

    Safety: verifies today's backup exists in GCS before deleting anything.
    If backup is missing, skips all deletions and sends an alert.
    """
    print("🧹 TTL Cleanup starting...")

    # ── Backup guard: verify today's backup exists before deleting anything ──
    from datetime import datetime, timezone as tz
    date_str = datetime.now(tz.utc).strftime("%Y-%m-%d")
    try:
        bucket_inst = get_bucket()
        backup_ok = _check_backup_exists(bucket_inst, "learned_classifications", date_str)
        if not backup_ok:
            alert_msg = f"TTL cleanup ABORTED — no backup found for {date_str}"
            print(f"    🛑 {alert_msg}")
            # Log to security_log
            try:
                get_db().collection("security_log").add({
                    "event": "ttl_cleanup_aborted",
                    "reason": "backup_missing",
                    "date": date_str,
                    "timestamp": firestore.SERVER_TIMESTAMP,
                })
            except Exception:
                pass
            # Send alert email
            try:
                secrets = get_rcb_secrets_internal(get_secret)
                if secrets:
                    access_token = helper_get_graph_token(secrets)
                    rcb_email = secrets.get("RCB_EMAIL", "rcb@rpa-port.co.il")
                    if access_token:
                        helper_graph_send(
                            access_token, rcb_email, _BACKUP_ALERT_EMAIL,
                            f"🛑 RCB TTL Cleanup ABORTED — {date_str} — No backup found",
                            f'<div dir="rtl" style="font-family:Arial"><h2 style="color:#991b1b">'
                            f'🛑 מחיקת TTL בוטלה</h2><p>לא נמצא גיבוי ל-{date_str}. '
                            f'המחיקה בוטלה כדי למנוע אובדן נתונים.</p>'
                            f'<p>יש לבדוק את rcb_daily_backup בלוגים.</p></div>'
                        )
            except Exception:
                pass
            print("🛑 TTL Cleanup ABORTED — no backup for today")
            return
        print(f"    ✅ Backup verified for {date_str}")
    except Exception as guard_err:
        print(f"    ⚠️ Backup guard check failed: {guard_err} — proceeding with cleanup")

    from lib.ttl_cleanup import cleanup_scanner_logs, cleanup_collection_by_field

    # 1. scanner_logs — 76K+ docs, 30-day TTL (batched via collection_streamer)
    try:
        result = cleanup_scanner_logs(get_db(), max_age_days=30)
        print(f"  scanner_logs: deleted={result['deleted']} skipped={result['skipped']} "
              f"errors={result['errors']} batches={result['batches_committed']}")
    except Exception as e:
        print(f"  ❌ scanner_logs error: {e}")

    # 2. rcb_logs — 90-day TTL
    try:
        result = cleanup_collection_by_field(
            get_db(), "rcb_logs", "timestamp", max_age_days=90)
        print(f"  rcb_logs: deleted={result['deleted']} skipped={result['skipped']}")
    except Exception as e:
        print(f"  ❌ rcb_logs error: {e}")

    # 3. learning_log — 90-day TTL
    try:
        result = cleanup_collection_by_field(
            get_db(), "learning_log", "learned_at", max_age_days=90)
        print(f"  learning_log: deleted={result['deleted']} skipped={result['skipped']}")
    except Exception as e:
        print(f"  ❌ learning_log error: {e}")

    # 4. inbox — 90-day TTL
    try:
        result = cleanup_collection_by_field(
            get_db(), "inbox", "received_at", max_age_days=90)
        print(f"  inbox: deleted={result['deleted']} skipped={result['skipped']}")
    except Exception as e:
        print(f"  ❌ inbox error: {e}")

    print("✅ TTL Cleanup complete")


# ============================================================
# FAILED CLASSIFICATIONS RETRY
# ============================================================
@scheduler_fn.on_schedule(schedule="every 6 hours")
def rcb_retry_failed(event: scheduler_fn.ScheduledEvent) -> None:
    """Retry failed classifications from last 24 hours"""
    print("🔄 Checking for failed classifications to retry...")
    
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    
    import hashlib as _hl
    _MAX_RETRIES = 3
    retried = 0
    skipped_max = 0
    try:
        # Load retry counts (single doc tracks all subjects by hash)
        retry_doc_ref = get_db().collection("rcb_processed").document("_retry_counts")
        retry_counts = {}
        try:
            rd = retry_doc_ref.get()
            if rd.exists:
                retry_counts = rd.to_dict() or {}
        except Exception:
            pass

        # Find processed emails without classification
        processed_docs = get_db().collection("rcb_processed").stream()
        processed_subjects = {}
        for doc in processed_docs:
            if doc.id == "_retry_counts":
                continue
            data = doc.to_dict()
            if data.get("processed_at") and data.get("processed_at") > cutoff:
                processed_subjects[data.get("subject", "")] = doc.id

        # Find classifications
        classified_subjects = set()
        class_docs = get_db().collection("rcb_classifications").stream()
        for doc in class_docs:
            data = doc.to_dict()
            if data.get("timestamp") and data.get("timestamp") > cutoff:
                classified_subjects.add(data.get("subject", ""))

        # Find failed (processed but not classified)
        failed = set(processed_subjects.keys()) - classified_subjects
        updates = {}

        for subject in failed:
            doc_id = processed_subjects[subject]
            subj_hash = _hl.md5(subject.encode("utf-8", errors="replace")).hexdigest()[:12]
            count = retry_counts.get(subj_hash, 0)
            if count >= _MAX_RETRIES:
                skipped_max += 1
                print(f"  ⏭️ Max retries ({_MAX_RETRIES}) reached: {subject[:40]}")
                continue
            updates[subj_hash] = count + 1
            get_db().collection("rcb_processed").document(doc_id).delete()
            retried += 1
            print(f"  🔄 Retry {count + 1}/{_MAX_RETRIES}: {subject[:40]}")

        # Persist updated retry counts
        if updates:
            retry_doc_ref.set(updates, merge=True)

    except Exception as e:
        print(f"❌ Retry check error: {e}")

    print(f"✅ Retry check complete: {retried} queued, {skipped_max} hit max retries")


# ============================================================
# HEALTH CHECK & EMAIL ALERTS
# ============================================================
@scheduler_fn.on_schedule(schedule="every 1 hours")
def rcb_health_check(event: scheduler_fn.ScheduledEvent) -> None:
    """Check system health and alert if stuck"""
    print("🏥 Running health check...")
    
    from datetime import datetime, timedelta, timezone
    import requests
    
    now = datetime.now(timezone.utc)
    issues = []
    
    try:
        # Check 1: Any classifications in last 6 hours?
        six_hours_ago = now - timedelta(hours=6)
        recent_classifications = list(get_db().collection("rcb_classifications")
            .order_by("timestamp", direction="DESCENDING")
            .limit(1).stream())
        
        if recent_classifications:
            last_class = recent_classifications[0].to_dict()
            last_time = last_class.get("timestamp")
            if last_time and last_time < six_hours_ago:
                issues.append("No classifications in last 6 hours")
        
        # Check 2: Any errors in monitor_errors?
        recent_errors = list(get_db().collection("monitor_errors")
            .order_by("timestamp", direction="DESCENDING")
            .limit(5).stream())
        
        error_count = len([e for e in recent_errors if e.to_dict().get("timestamp", now) > six_hours_ago])
        if error_count >= 3:
            issues.append(f"{error_count} errors in last 6 hours")
        
        # Check 3: Queue stuck? (processed but pending > 5)
        pending = 0
        processed_docs = get_db().collection("rcb_processed").stream()
        for doc in processed_docs:
            data = doc.to_dict()
            if data.get("processed_at") and data.get("processed_at") > six_hours_ago:
                pending += 1
        
        if pending > 10:
            issues.append(f"Queue may be stuck: {pending} processed in 6 hours")
        
        # Check 4: Pipeline health — ingestion activity
        try:
            from lib.data_pipeline.pipeline import SOURCE_TYPE_TO_COLLECTION
            pipeline_stats = {}
            for stype, coll in SOURCE_TYPE_TO_COLLECTION.items():
                try:
                    docs = list(get_db().collection(coll).limit(1).stream())
                    pipeline_stats[coll] = len(docs)
                except Exception:
                    pipeline_stats[coll] = 0
            populated = sum(1 for v in pipeline_stats.values() if v > 0)
            pipeline_stats["populated_collections"] = populated
        except Exception:
            pipeline_stats = {}

        # Update system status
        status = "healthy" if not issues else "degraded"
        get_db().collection("system_status").document("rcb").set({
            "last_check": now,
            "status": status,
            "issues": issues,
            "pending_count": pending,
            "error_count": error_count if 'error_count' in dir() else 0,
            "pipeline": pipeline_stats,
        })
        
        # Send alert email if issues (disabled — Doron requested no system alert emails)
        if issues:
            print(f"⚠️ Issues detected (email alerts disabled): {issues}")
        else:
            print("✅ System healthy")
            
    except Exception as e:
        print(f"❌ Health check error: {e}")


def _send_alert_email(issues):
    """Send alert email to master"""
    try:
        secrets = get_rcb_secrets_internal(get_secret)
        access_token = helper_get_graph_token(secrets)
        if not access_token:
            return
        
        rcb_email = secrets.get('RCB_EMAIL', 'rcb@rpa-port.co.il')
        master_email = "doron@rpa-port.co.il"
        
        issues_html = "<br>".join([f"⚠️ {issue}" for issue in issues])
        body = f'''<div dir="rtl" style="font-family:Arial">
            <h2>🚨 RCB System Alert</h2>
            <p>זוהו בעיות במערכת:</p>
            <div style="background:#fff3cd;padding:15px;border-radius:8px">
                {issues_html}
            </div>
            <p>אנא בדוק את הלוגים:</p>
            <a href="https://console.cloud.google.com/logs?project=rpa-port-customs">Cloud Console Logs</a>
            <hr>
            <small>RCB Health Monitor</small>
        </div>'''
        
        helper_graph_send(access_token, rcb_email, master_email, 
                         "🚨 RCB Alert: System Issues Detected", body, None, None)
        print(f"📧 Alert sent to {master_email}")
        
    except Exception as e:
        print(f"❌ Failed to send alert: {e}")





@https_fn.on_request(memory=options.MemoryOption.GB_1, timeout_sec=120)
def test_pdf_ocr(req: https_fn.Request) -> https_fn.Response:
    """Test PDF extraction with OCR - call via browser or curl"""
    from lib.rcb_helpers import extract_text_from_pdf_bytes, helper_get_graph_token, helper_graph_messages, helper_graph_attachments
    import base64
    
    results = {"status": "starting", "steps": []}
    
    try:
        # Step 1: Get Graph token
        secrets = {
            'RCB_GRAPH_CLIENT_ID': get_secret('RCB_GRAPH_CLIENT_ID'),
            'RCB_GRAPH_CLIENT_SECRET': get_secret('RCB_GRAPH_CLIENT_SECRET'),
            'RCB_GRAPH_TENANT_ID': get_secret('RCB_GRAPH_TENANT_ID')
        }
        token = helper_get_graph_token(secrets)
        if not token:
            return https_fn.Response(json.dumps({"error": "Failed to get Graph token"}), status=500)
        results["steps"].append("✅ Got Graph token")
        
        # Step 2: Get recent emails
        user_email = "rcb@rpa-port.co.il"
        messages = helper_graph_messages(token, user_email, unread_only=False, max_results=5)
        results["steps"].append(f"✅ Found {len(messages)} recent emails")
        
        # Step 3: Find first email with PDF attachment
        pdf_found = False
        for msg in messages:
            msg_id = msg.get('id')
            subject = msg.get('subject', 'No subject')
            
            attachments = helper_graph_attachments(token, user_email, msg_id)
            pdf_attachments = [a for a in attachments if a.get('name', '').lower().endswith('.pdf')]
            
            if pdf_attachments:
                results["steps"].append(f"✅ Found email with PDF: {subject}")
                
                # Step 4: Extract text from first PDF
                att = pdf_attachments[0]
                pdf_name = att.get('name', 'unknown.pdf')
                content_bytes = att.get('contentBytes', '')
                
                if content_bytes:
                    pdf_bytes = base64.b64decode(content_bytes)
                    results["steps"].append(f"✅ Loaded PDF: {pdf_name} ({len(pdf_bytes)} bytes)")
                    
                    # Step 5: Run extraction with OCR
                    text = extract_text_from_pdf_bytes(pdf_bytes)
                    
                    results["pdf_name"] = pdf_name
                    results["pdf_size"] = len(pdf_bytes)
                    results["extracted_chars"] = len(text)
                    results["extracted_preview"] = text[:500] if text else "[No text extracted]"
                    results["status"] = "success" if len(text) > 50 else "extraction_failed"
                    pdf_found = True
                    break
        
        if not pdf_found:
            results["status"] = "no_pdf_found"
            results["steps"].append("⚠️ No PDF attachments found in recent emails")
        
    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)
    
    return https_fn.Response(
        json.dumps(results, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8"
    )
# Add this to main.py to test PDF generation

# ============================================================
# TEST: PDF REPORT GENERATION
# ============================================================
@https_fn.on_request(memory=options.MemoryOption.GB_1, timeout_sec=60)
def test_pdf_report(req: https_fn.Request) -> https_fn.Response:
    """Test PDF report generation - creates a sample classification PDF"""
    from lib.pdf_creator import create_classification_pdf
    import base64
    from datetime import datetime
    
    try:
        # Sample classification data
        test_data = {
            'sender_name': 'דורון טסט',
            'email_subject': 'בקשת סיווג - מייבש שיער',
            'classification_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'items': [
                {
                    'description': 'מייבש שיער חשמלי 2000W',
                    'hs_code': '8516.31.00.00',
                    'hs_description_he': 'מייבשי שיער',
                    'hs_description_en': 'Hair dryers',
                    'duty_rate': '12%',
                    'vat_rate': '18%',
                    'purchase_tax': 'לא חל',
                    'ministry_requirements': [
                        {'ministry': 'משרד הכלכלה', 'requirement': 'תקן ישראלי', 'status': 'נדרש'},
                        {'ministry': 'מכון התקנים', 'requirement': 'בדיקת בטיחות חשמל', 'status': 'נדרש'}
                    ],
                    'notes': 'יש לוודא תאימות מתח 220V',
                    'confidence': 'גבוהה (95%)'
                },
                {
                    'description': 'כבל USB-C לטעינה',
                    'hs_code': '8544.42.00.00',
                    'hs_description_he': 'מוליכים חשמליים מצוידים במחברים',
                    'hs_description_en': 'Electric conductors with connectors',
                    'duty_rate': '0%',
                    'vat_rate': '18%',
                    'purchase_tax': 'לא חל',
                    'ministry_requirements': [],
                    'confidence': 'גבוהה (92%)'
                }
            ]
        }
        
        # Create PDF
        pdf_path = create_classification_pdf(test_data, '/tmp/test_report.pdf')
        
        # Read PDF and return as base64 (for download)
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
        
        # Check if browser request (return PDF) or API request (return JSON)
        accept = req.headers.get('Accept', '')
        if 'text/html' in accept:
            # Return PDF directly for browser viewing
            return https_fn.Response(
                pdf_bytes,
                headers={
                    'Content-Type': 'application/pdf',
                    'Content-Disposition': 'inline; filename="classification_report.pdf"'
                }
            )
        else:
            # Return JSON with base64 PDF
            return https_fn.Response(
                json.dumps({
                    'status': 'success',
                    'message': 'PDF created successfully',
                    'pdf_size': len(pdf_bytes),
                    'pdf_base64': base64.b64encode(pdf_bytes).decode()
                }),
                content_type='application/json'
            )
            
    except Exception as e:
        return https_fn.Response(
            json.dumps({'status': 'error', 'error': str(e)}),
            status=500,
            content_type='application/json'
        )

# ============================================================
# SELF-TEST: RCB tests itself (Session 13)
# ============================================================
@https_fn.on_request(region="us-central1", memory=options.MemoryOption.GB_1, timeout_sec=300)
def rcb_self_test(req: https_fn.Request) -> https_fn.Response:
    """RCB Self-Test — sends test emails to itself, verifies, cleans up."""
    from lib.rcb_self_test import run_all_tests
    try:
        secrets = get_rcb_secrets_internal(get_secret)
        if not secrets:
            return https_fn.Response(json.dumps({"error": "No secrets"}), status=500)
        report = run_all_tests(
            db=get_db(), firestore_module=firestore,
            secrets=secrets, get_secret_func=get_secret,
        )
        status_code = 200 if report.get("all_passed") else 500
        return https_fn.Response(
            json.dumps(report, ensure_ascii=False, indent=2),
            status=status_code,
            headers={"Content-Type": "application/json"}
        )
    except Exception as e:
        return https_fn.Response(json.dumps({"error": str(e)}), status=500)
"""
═══════════════════════════════════════════════════════════════
  INSPECTOR AGENT — Add these to the END of main.py
  Session 14.01
═══════════════════════════════════════════════════════════════
"""

# --- Add this import near the top of main.py ---
# from lib.rcb_inspector import handle_inspector_http, handle_inspector_daily


# ============================================================
# INSPECTOR AGENT — Manual HTTP Trigger
# ============================================================
@https_fn.on_request(region="us-central1", memory=options.MemoryOption.GB_1, timeout_sec=300)
def rcb_inspector(req: https_fn.Request) -> https_fn.Response:
    """
    Full system inspection — manual trigger.
    
    Usage:
        curl https://us-central1-rpa-port-customs.cloudfunctions.net/rcb_inspector | python3 -m json.tool
    """
    print("🔍 RCB Inspector — Manual trigger")
    
    from lib.rcb_inspector import handle_inspector_http
    
    result = handle_inspector_http(req, get_db(), get_secret)
    
    return https_fn.Response(
        json.dumps(result, ensure_ascii=False, default=str, indent=2),
        status=200,
        headers={"Content-Type": "application/json"}
    )


# ============================================================
# INSPECTOR AGENT — Daily 15:00 Jerusalem Scheduler
# ============================================================
@scheduler_fn.on_schedule(
    schedule="every day 15:00",
    timezone=scheduler_fn.Timezone("Asia/Jerusalem"),
    region="us-central1",
    memory=options.MemoryOption.GB_1,
    timeout_sec=300,
)
def rcb_inspector_daily(event: scheduler_fn.ScheduledEvent) -> None:
    """
    Daily inspection + email report to doron@rpa-port.co.il
    Runs at 15:00 Jerusalem time every day.
    """
    print("🔍 RCB Inspector — Daily 15:00 scheduled run")
    
    from lib.rcb_inspector import handle_inspector_daily
    
    handle_inspector_daily(get_db(), get_secret)
    
    print("✅ RCB Inspector daily run complete")


# ============================================================
# NIGHTLY LEARNING — Build knowledge indexes automatically
# ============================================================
@scheduler_fn.on_schedule(
    schedule="every day 02:00",
    timezone=scheduler_fn.Timezone("Asia/Jerusalem"),
    region="us-central1",
    memory=options.MemoryOption.GB_1,
    timeout_sec=540,
)
def rcb_nightly_learn(event: scheduler_fn.ScheduledEvent) -> None:
    """
    Nightly learning pipeline — reads source data, builds indexes.
    Runs at 02:00 Jerusalem time every night.

    READS: tariff, knowledge_base, declarations, classification_knowledge,
           rcb_classifications, sellers, and 20+ other collections
    BUILDS: keyword_index, product_index, supplier_index, brain_index

    Source data is NEVER modified. Only derived indexes are written.
    No AI calls — pure text parsing. $0 cost.
    """
    print("NIGHTLY LEARN — Starting automated learning pipeline")

    from lib.nightly_learn import run_pipeline

    results = run_pipeline()

    success = all(r.get("status") == "success" for r in results.values())
    print(f"NIGHTLY LEARN — {'All steps succeeded' if success else 'Some steps failed'}")


# ============================================================
# TRACKER: Poll active deals via TaskYam (every 30 minutes)
# ============================================================
@scheduler_fn.on_schedule(
    schedule="every 30 minutes",
    region="us-central1",
    memory=options.MemoryOption.MB_512,
    timeout_sec=300,
)
def rcb_tracker_poll(event: scheduler_fn.ScheduledEvent) -> None:
    """Poll TaskYam for active deal updates. Sends status emails when steps change."""
    if not TRACKER_AVAILABLE:
        print("⏸️ Tracker not available — skipping poll")
        return

    print("📦 Tracker polling active deals...")
    try:
        secrets = get_rcb_secrets_internal(get_secret)
        access_token = helper_get_graph_token(secrets) if secrets else None
        rcb_email = secrets.get('RCB_EMAIL', 'rcb@rpa-port.co.il') if secrets else 'rcb@rpa-port.co.il'

        result = tracker_poll_active_deals(
            get_db(), firestore, get_secret,
            access_token=access_token, rcb_email=rcb_email
        )
        print(f"📦 Tracker poll complete: {result}")
    except Exception as e:
        print(f"❌ Tracker poll error: {e}")
        import traceback
        traceback.print_exc()

    # ── Air cargo: Poll AWBs via Maman API ──
    try:
        from lib.air_cargo_tracker import poll_air_cargo_for_tracker
        air_result = poll_air_cargo_for_tracker(get_db(), firestore, get_secret)
        print(f"✈️ Air cargo poll complete: {air_result}")
    except ImportError:
        print("✈️ Air cargo tracker not available")
    except Exception as ae:
        print(f"✈️ Air cargo poll error: {ae}")

    # ── Land transport: Gate cutoff ETA alerts ──
    try:
        cutoff_result = check_gate_cutoff_alerts(
            get_db(), firestore, get_secret,
            access_token=access_token, rcb_email=rcb_email
        )
        print(f"🚛 Gate cutoff check complete: {cutoff_result}")
    except Exception as ge:
        print(f"🚛 Gate cutoff check error: {ge}")

    # ── I3: Port intelligence alerts (D/O missing, physical exam, storage, cutoffs) ──
    try:
        pi_result = _run_port_intelligence_alerts(
            get_db(), firestore, access_token, rcb_email
        )
        print(f"🚨 I3 port intelligence alerts: {pi_result}")
    except Exception as pie:
        print(f"🚨 I3 alert engine error: {pie}")

    # ── Gap 2: Send classification reports for silently-classified deals ──
    # CC path classifies silently and stores results. Here we email them to doron@.
    try:
        _gap2_sent = 0
        _gap2_deals = list(get_db().collection("tracker_deals")
                           .where("classification_auto_triggered", "==", True)
                           .where("classification_report_sent", "==", False)
                           .limit(10).stream())
        for _g2d in _gap2_deals:
            if _gap2_sent >= 3:
                break  # Max 3 per poll cycle
            _g2data = _g2d.to_dict()
            if not _g2data.get("gap2_classification", {}).get("success"):
                continue  # Classification didn't succeed
            _g2_deal_id = _g2d.id
            _g2_bol = _g2data.get("bol_number", "")
            _g2_html = _build_gap2_report_html(_g2_deal_id, _g2data)
            _g2_subj = f"RCB | סיווג אוטומטי | {_g2_bol or _g2_deal_id[:8]}"
            if helper_graph_send(access_token, rcb_email, 'doron@rpa-port.co.il',
                                  _g2_subj, _g2_html, deal_id=_g2_deal_id,
                                  alert_type="gap2_report", db=get_db()):
                get_db().collection("tracker_deals").document(_g2_deal_id).update({
                    "classification_report_sent": True,
                    "classification_report_sent_at": firestore.SERVER_TIMESTAMP,
                })
                _gap2_sent += 1
                _g2_hs_count = len(_g2data.get("gap2_classification", {}).get("hs_codes", []))
                print(f"  📋 Gap 2 report sent for deal {_g2_deal_id} ({_g2_hs_count} HS codes)")
        if _gap2_sent > 0:
            print(f"📋 Gap 2: {_gap2_sent} classification reports sent to doron@")
    except Exception as gap2_poll_err:
        print(f"📋 Gap 2 report send error (non-fatal): {gap2_poll_err}")


# ============================================================
# PORT SCHEDULE: Daily vessel schedule aggregation
# ============================================================
@scheduler_fn.on_schedule(
    schedule="every 12 hours",
    region="us-central1",
    memory=options.MemoryOption.MB_512,
    timeout_sec=300,
)
def rcb_port_schedule(event: scheduler_fn.ScheduledEvent) -> None:
    """Build daily vessel schedules for all Israeli ports (Haifa, Ashdod, Eilat)."""
    if not SCHEDULE_AVAILABLE:
        print("⏸️ Port schedule module not available — skipping")
        return

    print("🚢 Building daily port schedules...")
    try:
        results = build_all_port_schedules(get_db(), get_secret_func=get_secret)
        total = sum(r.get("vessel_count", 0) for r in results.values() if isinstance(r, dict))
        print(f"🚢 Port schedules complete: {total} vessels across {len(results)} ports")
    except Exception as e:
        print(f"❌ Port schedule error: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# PUPIL: Batch learning cycle (every 6 hours)
# ============================================================
@scheduler_fn.on_schedule(
    schedule="every 6 hours",
    region="us-central1",
    memory=options.MemoryOption.GB_1,
    timeout_sec=540,
)
def rcb_pupil_learn(event: scheduler_fn.ScheduledEvent) -> None:
    """
    Pupil batch learning: verify observations, challenge brain, learn gaps.
    Phase B+C run here (not in email loop) to avoid slowing down email processing.
    """
    if not PUPIL_AVAILABLE:
        print("⏸️ Pupil not available — skipping learning cycle")
        return

    print("🎓 Pupil learning cycle starting...")
    try:
        from lib.pupil import (
            pupil_learn, pupil_verify_scan, pupil_challenge,
            pupil_send_reviews, pupil_find_corrections, pupil_audit,
            pupil_escalate_to_claude, pupil_research_contacts,
        )

        secrets = get_rcb_secrets_internal(get_secret)
        access_token = helper_get_graph_token(secrets) if secrets else None
        rcb_email = secrets.get('RCB_EMAIL', 'rcb@rpa-port.co.il') if secrets else 'rcb@rpa-port.co.il'

        # Phase B: Verify unverified observations
        try:
            pupil_verify_scan(get_db(), get_secret)
            print("  ✅ Pupil verify scan done")
        except Exception as e:
            print(f"  ⚠️ Pupil verify error: {e}")

        # Phase B2: Research contacts with unknown roles
        try:
            contacts = pupil_research_contacts(get_db(), get_secret)
            print(f"  ✅ Pupil contacts researched: {contacts}")
        except Exception as e:
            print(f"  ⚠️ Pupil contact research error: {e}")

        # Phase B: Learn from gaps (uses Gemini/Claude when needed)
        try:
            pupil_learn(get_db(), get_secret)
            print("  ✅ Pupil learning done")
        except Exception as e:
            print(f"  ⚠️ Pupil learn error: {e}")

        # Phase C: Find corrections in past classifications
        try:
            pupil_find_corrections(get_db(), access_token, rcb_email, get_secret)
            print("  ✅ Pupil corrections scan done")
        except Exception as e:
            print(f"  ⚠️ Pupil corrections error: {e}")

        # Phase C2: Escalate complex tasks to Claude (tier 2)
        try:
            escalated = pupil_escalate_to_claude(get_db(), get_secret)
            print(f"  ✅ Pupil escalated to Claude: {escalated}")
        except Exception as e:
            print(f"  ⚠️ Pupil escalation error: {e}")

        # Phase C: Send review cases to doron@
        try:
            pupil_send_reviews(get_db(), access_token, rcb_email, get_secret)
            print("  ✅ Pupil reviews sent")
        except Exception as e:
            print(f"  ⚠️ Pupil reviews error: {e}")

        # Audit: Analyze patterns and summarize
        try:
            pupil_audit(get_db(), get_secret)
            print("  ✅ Pupil audit done")
        except Exception as e:
            print(f"  ⚠️ Pupil audit error: {e}")

        print("🎓 Pupil learning cycle complete")

    except Exception as e:
        print(f"❌ Pupil learning error: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# I4: Digest to cc@ (07:00 + 14:00 Israel time)
# ============================================================

def _send_digest(label):
    """Shared I4 digest builder — called by both 07:00 and 14:00 triggers."""
    print(f"📬 {label} digest starting...")
    secrets = get_rcb_secrets_internal(get_secret)
    access_token = helper_get_graph_token(secrets) if secrets else None
    rcb_email = secrets.get('RCB_EMAIL', 'rcb@rpa-port.co.il') if secrets else 'rcb@rpa-port.co.il'

    if not access_token:
        print("❌ No access token — cannot send digest")
        return

    cc_email = "cc@rpa-port.co.il"

    if PORT_INTELLIGENCE_AVAILABLE:
        digest_html = build_morning_digest(get_db())
        if digest_html:
            from datetime import datetime, timezone as tz
            try:
                from zoneinfo import ZoneInfo
                now_il = datetime.now(ZoneInfo("Asia/Jerusalem"))
            except ImportError:
                now_il = datetime.now(tz.utc)
            date_str = now_il.strftime("%d.%m.%Y")
            time_str = now_il.strftime("%H:%M")
            subject = f"RCB | דוח בוקר | {date_str} {time_str}"
            ok = helper_graph_send(access_token, rcb_email, cc_email, subject, digest_html)
            if ok:
                print(f"📬 {label} digest sent to {cc_email}")
            else:
                print(f"⚠️ {label} digest send failed")
            return
        else:
            print(f"  ℹ️ No active deals — skipping {label} digest")
    else:
        print("  ⚠️ Port intelligence not available — falling back to brain digest")

    # Fallback: old brain_daily_digest
    try:
        from lib.brain_commander import brain_daily_digest
        result = brain_daily_digest(get_db(), access_token, rcb_email)
        print(f"🧠 Fallback daily digest result: {result}")
    except ImportError:
        print("  ⚠️ brain_commander not available either — no digest sent")


@scheduler_fn.on_schedule(
    schedule="every day 07:00",
    timezone=scheduler_fn.Timezone("Asia/Jerusalem"),
    region="us-central1",
    memory=options.MemoryOption.MB_512,
    timeout_sec=300,
)
def rcb_daily_digest(event: scheduler_fn.ScheduledEvent) -> None:
    """I4: Morning digest — all active shipments + port status, sent to cc@rpa-port.co.il."""
    try:
        _send_digest("Morning 07:00")
    except Exception as e:
        print(f"❌ Morning digest error: {e}")
        import traceback
        traceback.print_exc()


@scheduler_fn.on_schedule(
    schedule="every day 14:00",
    timezone=scheduler_fn.Timezone("Asia/Jerusalem"),
    region="us-central1",
    memory=options.MemoryOption.MB_512,
    timeout_sec=300,
)
def rcb_afternoon_digest(event: scheduler_fn.ScheduledEvent) -> None:
    """I4: Afternoon digest — same format as morning, sent to cc@rpa-port.co.il at 14:00 IL."""
    try:
        _send_digest("Afternoon 14:00")
    except Exception as e:
        print(f"❌ Afternoon digest error: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# AUDIT: One-time overnight diagnostic scan
# ============================================================
@scheduler_fn.on_schedule(
    schedule="every day 02:00",
    timezone=scheduler_fn.Timezone("Asia/Jerusalem"),
    region="us-central1",
    memory=options.MemoryOption.GB_2,
    timeout_sec=900,
)
def rcb_overnight_audit(event: scheduler_fn.ScheduledEvent) -> None:
    """Diagnostic scan: reprocess emails, check memory, find ghost deals, count everything."""
    print("🔍 Overnight audit triggered...")
    try:
        from lib.overnight_audit import run_overnight_audit

        secrets = get_rcb_secrets_internal(get_secret)
        access_token = helper_get_graph_token(secrets) if secrets else None
        rcb_email = secrets.get('RCB_EMAIL', 'rcb@rpa-port.co.il') if secrets else 'rcb@rpa-port.co.il'

        result = run_overnight_audit(get_db(), firestore, access_token, rcb_email, get_secret)
        print(f"🔍 Audit complete: {result.get('duration_sec', 0):.1f}s, "
              f"{len(result.get('errors', []))} errors")

    except Exception as e:
        print(f"❌ Overnight audit error: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# PC AGENT RUNNER: Execute pending tasks (every 30 minutes)
# ============================================================
@scheduler_fn.on_schedule(
    schedule="every 30 minutes",
    region="us-central1",
    memory=options.MemoryOption.MB_512,
    timeout_sec=300,
)
def rcb_pc_agent_runner(event: scheduler_fn.ScheduledEvent) -> None:
    """Execute pending PC Agent tasks that don't require browser automation."""
    print("PC Agent Runner starting...")
    try:
        from lib.pc_agent_runner import run_pending_tasks
        result = run_pending_tasks(get_db(), max_tasks=10)
        print(f"PC Agent Runner: {result['executed']} executed, "
              f"{result['skipped_browser']} skipped, {result['failed']} failed")
    except Exception as e:
        print(f"PC Agent Runner error: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# OVERNIGHT BRAIN EXPLOSION: Know everything by morning
# Session 28 — Assignment 19
# ============================================================
@scheduler_fn.on_schedule(
    schedule="every day 20:00",
    timezone=scheduler_fn.Timezone("Asia/Jerusalem"),
    region="us-central1",
    memory=options.MemoryOption.GB_2,
    timeout_sec=900,
)
def rcb_overnight_brain(event: scheduler_fn.ScheduledEvent) -> None:
    """
    Overnight Brain Explosion — 8 enrichment streams mine ALL internal data.
    Runs at 20:00 Jerusalem (well before 02:00 nightly_learn — no conflict).
    HARD CAP: $3.50 per run.
    """
    print("Overnight Brain Explosion starting...")
    try:
        from lib.overnight_brain import run_overnight_brain

        result = run_overnight_brain(get_db(), get_secret)
        cost = result.get("cost", {})
        print(f"Overnight Brain complete: ${cost.get('total_spent', 0):.4f} / "
              f"${cost.get('budget_limit', 3.50)}, "
              f"{cost.get('gemini_calls', 0)} AI calls")

    except Exception as e:
        print(f"Overnight Brain error: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# DOWNLOAD CLASSIFICATION DIRECTIVES from Shaarolami
# Assignment 17
# ============================================================
@scheduler_fn.on_schedule(
    schedule="every day 04:00",
    timezone=scheduler_fn.Timezone("Asia/Jerusalem"),
    region="us-central1",
    memory=options.MemoryOption.GB_1,
    timeout_sec=540,
)
def rcb_download_directives(event: scheduler_fn.ScheduledEvent) -> None:
    """
    Download Israeli Customs classification directives from Shaarolami.
    Runs daily at 04:00 Jerusalem time (after TTL cleanup at 03:30).
    First run: downloads all ~217 directives (~4 min at 1/sec).
    Subsequent runs: skips existing, only picks up new ones.
    """
    print("Classification directives download starting...")
    try:
        from lib.data_pipeline.directive_downloader import download_all_directives

        stats = download_all_directives(get_db(), get_secret)
        print(
            f"Directives complete: {stats['downloaded']} downloaded, "
            f"{stats['skipped_exists']} already existed, "
            f"{stats['skipped_empty']} empty, {stats['failed']} failed"
        )
        if stats["errors"]:
            for err in stats["errors"][:10]:
                print(f"  Error: {err}")

    except Exception as e:
        print(f"Directives download error: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# DAILY BACKUP — Exports critical collections to Cloud Storage
# ============================================================
_BACKUP_COLLECTIONS = [
    "learned_classifications",
    "classification_directives",
    "legal_knowledge",
    "chapter_notes",
]
_BACKUP_PREFIX = "backups"
_BACKUP_ALERT_EMAIL = "doron@rpa-port.co.il"


def _export_collection_to_gcs(db_inst, bucket_inst, collection_name, date_str):
    """Export a Firestore collection to GCS as NDJSON. Returns doc count."""
    import io
    blob_path = f"{_BACKUP_PREFIX}/{collection_name}/{date_str}.ndjson"
    blob = bucket_inst.blob(blob_path)

    buf = io.BytesIO()
    count = 0
    for doc in db_inst.collection(collection_name).stream():
        data = doc.to_dict()
        data["_doc_id"] = doc.id
        # Convert non-serializable types
        line = json.dumps(data, ensure_ascii=False, default=str) + "\n"
        buf.write(line.encode("utf-8"))
        count += 1

    buf.seek(0)
    blob.upload_from_file(buf, content_type="application/x-ndjson")
    print(f"    {collection_name}: {count} docs → gs://{bucket_inst.name}/{blob_path}")
    return count


def _check_backup_exists(bucket_inst, collection_name, date_str):
    """Check if today's backup blob exists in GCS."""
    blob_path = f"{_BACKUP_PREFIX}/{collection_name}/{date_str}.ndjson"
    blob = bucket_inst.blob(blob_path)
    return blob.exists()


@scheduler_fn.on_schedule(
    schedule="every day 02:00",
    timezone=scheduler_fn.Timezone("Asia/Jerusalem"),
    memory=options.MemoryOption.GB_1,
    timeout_sec=540,
)
def rcb_daily_backup(event: scheduler_fn.ScheduledEvent) -> None:
    """Daily backup of critical Firestore collections to Cloud Storage as NDJSON.

    Runs at 02:00 Israel time (before TTL cleanup at 03:30).
    Exports: learned_classifications, classification_directives,
             legal_knowledge, chapter_notes.
    Sends confirmation email on success, alert email on failure.
    """
    print("💾 Daily backup starting...")
    from datetime import datetime, timezone as tz
    date_str = datetime.now(tz.utc).strftime("%Y-%m-%d")
    db_inst = get_db()
    bucket_inst = get_bucket()

    results = {}
    errors = []

    for coll in _BACKUP_COLLECTIONS:
        try:
            count = _export_collection_to_gcs(db_inst, bucket_inst, coll, date_str)
            results[coll] = count
        except Exception as e:
            error_msg = f"{coll}: {e}"
            errors.append(error_msg)
            print(f"    ❌ Backup failed for {coll}: {e}")

    # Build summary
    total_docs = sum(results.values())
    total_collections = len(results)
    failed_collections = len(errors)

    # Send email notification
    try:
        secrets = get_rcb_secrets_internal(get_secret)
        if secrets:
            access_token = helper_get_graph_token(secrets)
            rcb_email = secrets.get("RCB_EMAIL", "rcb@rpa-port.co.il")

            if errors:
                # Alert email — some backups failed
                subject = f"⚠️ RCB Backup PARTIAL — {date_str} — {failed_collections} failed"
                body = f"""<div dir="rtl" style="font-family:Arial,sans-serif">
<h2 style="color:#991b1b">⚠️ גיבוי יומי — כשלון חלקי</h2>
<p><b>תאריך:</b> {date_str}</p>
<h3>הצליחו ({total_collections}):</h3>
<ul>{''.join(f'<li>{c}: {n} docs</li>' for c, n in results.items())}</ul>
<h3 style="color:#991b1b">נכשלו ({failed_collections}):</h3>
<ul>{''.join(f'<li style="color:#991b1b">{e}</li>' for e in errors)}</ul>
</div>"""
            else:
                # Success email
                subject = f"✅ RCB Backup OK — {date_str} — {total_docs} docs"
                body = f"""<div dir="rtl" style="font-family:Arial,sans-serif">
<h2 style="color:#166534">✅ גיבוי יומי הושלם בהצלחה</h2>
<p><b>תאריך:</b> {date_str}</p>
<p><b>סה"כ:</b> {total_docs} מסמכים ב-{total_collections} אוספים</p>
<ul>{''.join(f'<li>{c}: {n} docs</li>' for c, n in results.items())}</ul>
<p style="color:#6b7280;font-size:12px">GCS: gs://{bucket_inst.name}/{_BACKUP_PREFIX}/</p>
</div>"""

            if access_token:
                helper_graph_send(access_token, rcb_email, _BACKUP_ALERT_EMAIL, subject, body)
                print(f"    📧 Backup notification sent to {_BACKUP_ALERT_EMAIL}")
    except Exception as email_err:
        print(f"    ❌ Failed to send backup notification email: {email_err}")

    if errors:
        print(f"⚠️ Daily backup PARTIAL: {total_collections} OK, {failed_collections} failed")
    else:
        print(f"✅ Daily backup complete: {total_docs} docs across {total_collections} collections")
