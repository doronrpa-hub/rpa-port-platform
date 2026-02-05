with open('main.py', 'r') as f:
    content = f.read()

# Add backup endpoint to rcb_api - find the rcb_api function and add before the final return
backup_code = '''
    # Save session backup
    elif path == "backup" and method == "POST":
        try:
            data = req.get_json()
            session_id = data.get("session_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
            backup_content = data.get("content", "")
            
            # Save to Firestore
            db.collection("session_backups").document(session_id).set({
                "content": backup_content,
                "created_at": firestore.SERVER_TIMESTAMP,
                "session_id": session_id
            })
            
            # Also email to airpaort@gmail.com
            secrets = get_rcb_secrets()
            if secrets:
                access_token = get_graph_access_token(secrets)
                if access_token:
                    graph_send_email(
                        access_token,
                        secrets['RCB_EMAIL'],
                        secrets.get('RCB_FALLBACK_EMAIL', 'airpaort@gmail.com'),
                        f"[RCB Backup] Session {session_id}",
                        f"<pre style='font-family: monospace; white-space: pre-wrap;'>{backup_content}</pre>"
                    )
            
            return https_fn.Response(json.dumps({
                "ok": True,
                "session_id": session_id,
                "message": "Backup saved to Firestore and emailed"
            }), content_type="application/json")
        except Exception as e:
            return https_fn.Response(json.dumps({
                "ok": False,
                "error": str(e)
            }), status=500, content_type="application/json")
    
    # Get session backup
    elif path.startswith("backup/") and method == "GET":
        session_id = path.split("/")[1]
        doc = db.collection("session_backups").document(session_id).get()
        if doc.exists:
            return https_fn.Response(json.dumps(doc.to_dict(), default=str), content_type="application/json")
        return https_fn.Response(json.dumps({"error": "Backup not found"}), status=404, content_type="application/json")
    
    # List all backups
    elif path == "backups" and method == "GET":
        backups = []
        for doc in db.collection("session_backups").order_by("created_at", direction=firestore.Query.DESCENDING).limit(20).stream():
            d = doc.to_dict()
            d["id"] = doc.id
            backups.append({"id": d["id"], "session_id": d.get("session_id"), "created_at": str(d.get("created_at"))})
        return https_fn.Response(json.dumps(backups, default=str), content_type="application/json")

'''

# Find the last return in rcb_api and insert before it
old_end = '''    return https_fn.Response(json.dumps({"error": "Not found"}), status=404, content_type="application/json")


# ============================================================
# PDF REQUEST HELPER'''

new_end = backup_code + '''
    return https_fn.Response(json.dumps({"error": "Not found"}), status=404, content_type="application/json")


# ============================================================
# PDF REQUEST HELPER'''

content = content.replace(old_end, new_end)

with open('main.py', 'w') as f:
    f.write(content)

print("✅ Backup API added!")
