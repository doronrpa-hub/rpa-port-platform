with open('main.py', 'r') as f:
    content = f.read()

# Extract get_secret function
get_secret_func = '''
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
'''

# Remove old get_secret at end of file
content = content.replace(get_secret_func.strip(), '')

# Add get_secret right after imports
import_marker = "from lib.rcb_helpers import"
if import_marker in content:
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        new_lines.append(line)
        if line.startswith(import_marker):
            new_lines.append(get_secret_func)
    content = '\n'.join(new_lines)

with open('main.py', 'w') as f:
    f.write(content)

print("✅ Moved get_secret to top")
