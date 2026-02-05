with open('main.py', 'r') as f:
    content = f.read()

old_test = '''    # Test connection
    if path == "test":
        try:
            secrets = get_rcb_secrets_internal(get_secret)
            if not secrets:
                return https_fn.Response(json.dumps({"ok": False, "error": "No secrets"}), content_type="application/json")
            access_token = get_graph_access_token(secrets)
            if access_token:
                return https_fn.Response(json.dumps({
                    "ok": True,
                    "email": secrets.get('RCB_EMAIL'),
                    "method": "Microsoft Graph API",
                    "message": "Connection successful"
                }), content_type="application/json")
            return https_fn.Response(json.dumps({"ok": False, "error": "Token failed"}), content_type="application/json")
        except Exception as e:
            return https_fn.Response(json.dumps({"ok": False, "error": str(e)}), content_type="application/json")'''

new_test = '''    # Test connection
    if path == "test":
        try:
            secrets = get_rcb_secrets_internal(get_secret)
        except Exception as e1:
            return https_fn.Response(json.dumps({"ok": False, "error": f"secrets error: {e1}"}), content_type="application/json")
        if not secrets:
            return https_fn.Response(json.dumps({"ok": False, "error": "No secrets returned"}), content_type="application/json")
        try:
            access_token = get_graph_access_token(secrets)
        except Exception as e2:
            return https_fn.Response(json.dumps({"ok": False, "error": f"token error: {e2}"}), content_type="application/json")
        if access_token:
            return https_fn.Response(json.dumps({"ok": True, "email": secrets.get('RCB_EMAIL'), "method": "Graph API"}), content_type="application/json")
        return https_fn.Response(json.dumps({"ok": False, "error": "No token"}), content_type="application/json")'''

content = content.replace(old_test, new_test)

with open('main.py', 'w') as f:
    f.write(content)

print("✅ Fixed test endpoint")
