with open('main.py', 'r') as f:
    content = f.read()

import_line = "from lib.rcb_helpers import get_rcb_secrets_internal, get_graph_access_token, graph_get_messages, graph_get_attachments, graph_mark_as_read, graph_send_email, to_hebrew_name, build_rcb_reply\n"

if 'from lib.rcb_helpers' not in content:
    # Add after first import line
    content = content.replace('import requests\n', 'import requests\n' + import_line)
    with open('main.py', 'w') as f:
        f.write(content)
    print("✅ Import added")
else:
    print("Import already exists")
