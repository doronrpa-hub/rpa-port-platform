import subprocess
# Get API key from secret manager using gcloud
result = subprocess.run(['gcloud', 'secrets', 'versions', 'access', 'latest', '--secret=ANTHROPIC_API_KEY', '--project=rpa-port-customs'], capture_output=True, text=True)
api_key = result.stdout.strip()

if not api_key:
    print("❌ Could not get API key")
    exit()

print(f"✅ Got API key: {api_key[:15]}...")

import requests
resp = requests.post(
    "https://api.anthropic.com/v1/messages",
    headers={"x-api-key": api_key, "content-type": "application/json", "anthropic-version": "2023-06-01"},
    json={"model": "claude-sonnet-4-20250514", "max_tokens": 50, "messages": [{"role": "user", "content": "Say OK"}]},
    timeout=30
)
print(f"API Status: {resp.status_code}")
if resp.status_code == 200:
    print(f"✅ Response: {resp.json()['content'][0]['text']}")
else:
    print(f"❌ Error: {resp.text[:200]}")
