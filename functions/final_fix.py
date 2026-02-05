with open('main.py', 'r') as f:
    lines = f.readlines()

# Remove rcbsecretshelper function entirely
new_lines = []
skip_until_next_def = False
for line in lines:
    if 'def rcbsecretshelper():' in line:
        skip_until_next_def = True
        continue
    if skip_until_next_def:
        if line.startswith('def ') or line.startswith('@') or line.startswith('# ==='):
            skip_until_next_def = False
            new_lines.append(line)
        continue
    new_lines.append(line)

content = ''.join(new_lines)

# Replace rcbsecretshelper() calls with get_rcb_secrets_internal(get_secret)
content = content.replace('rcbsecretshelper()', 'get_rcb_secrets_internal(get_secret)')

# Make sure import exists
if 'from rcb_helpers import' not in content:
    content = content.replace('import requests', 'import requests\nfrom rcb_helpers import get_rcb_secrets_internal, get_graph_access_token, graph_get_messages, graph_get_attachments, graph_mark_as_read, graph_send_email, to_hebrew_name, build_rcb_reply')

with open('main.py', 'w') as f:
    f.write(content)

print("✅ Fixed - using rcb_helpers.py")
