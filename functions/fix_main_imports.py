with open('main.py', 'r') as f:
    content = f.read()

# Add import at top
import_line = "from rcb_helpers import get_rcb_secrets_internal, get_graph_access_token, graph_get_messages, graph_get_attachments, graph_mark_as_read, graph_send_email, to_hebrew_name, build_rcb_reply, get_anthropic_key"

# Find where to add import (after other imports)
if 'from rcb_helpers import' not in content:
    content = content.replace('import requests', f'import requests\n{import_line}')

# Create wrapper for get_rcb_secrets that uses get_secret
wrapper = '''
def get_rcb_secrets():
    return get_rcb_secrets_internal(get_secret)

def get_anthropic_api_key():
    return get_anthropic_key(get_secret)
'''

# Remove the rcbGetSecrets function and other helpers that are now in rcb_helpers.py
# Find and remove the helper functions section
import re

# Remove rcbGetSecrets and related helpers
patterns_to_remove = [
    r'def rcbGetSecrets\(\):[^@]*?(?=@|def [a-z])',
    r'HEBREW_NAMES = \{[^}]+\}',
    r'def to_hebrew_name\([^)]*\):[^@]*?(?=@|def [a-z])',
    r'def build_rcb_reply\([^)]*\):[^@]*?(?=@|def [a-z])',
]

# Just add the wrapper after imports if not there
if 'def get_rcb_secrets():' not in content or 'get_rcb_secrets_internal' not in content:
    # Find good place to add wrapper
    content = content.replace(import_line, import_line + '\n' + wrapper)

with open('main.py', 'w') as f:
    f.write(content)

print("✅ Imports updated")
