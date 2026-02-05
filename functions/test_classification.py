from google.cloud import secretmanager

def get_secret(name):
    client = secretmanager.SecretManagerServiceClient()
    path = f"projects/rpa-port-customs/secrets/{name}/versions/latest"
    return client.access_secret_version(request={"name": path}).payload.data.decode("UTF-8")

# Test 1: Check if ANTHROPIC_API_KEY exists
try:
    key = get_secret('ANTHROPIC_API_KEY')
    print(f"✅ ANTHROPIC_API_KEY exists: {key[:20]}...")
except Exception as e:
    print(f"❌ ANTHROPIC_API_KEY error: {e}")

# Test 2: Quick Claude API test
import requests
try:
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "content-type": "application/json", "anthropic-version": "2023-06-01"},
        json={"model": "claude-sonnet-4-20250514", "max_tokens": 50, "messages": [{"role": "user", "content": "Say OK"}]},
        timeout=30
    )
    print(f"✅ Claude API response: {resp.status_code}")
    if resp.status_code == 200:
        print(f"   {resp.json()['content'][0]['text']}")
    else:
        print(f"   {resp.text[:200]}")
except Exception as e:
    print(f"❌ Claude API error: {e}")
