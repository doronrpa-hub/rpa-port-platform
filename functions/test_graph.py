import requests
from google.cloud import secretmanager

def get_secret(name):
    client = secretmanager.SecretManagerServiceClient()
    path = f"projects/rpa-port-customs/secrets/{name}/versions/latest"
    return client.access_secret_version(request={"name": path}).payload.data.decode("UTF-8")

tenant = get_secret('RCB_GRAPH_TENANT_ID')
client_id = get_secret('RCB_GRAPH_CLIENT_ID')
client_secret = get_secret('RCB_GRAPH_CLIENT_SECRET')
email = get_secret('RCB_EMAIL')

print(f"Checking: {email}")

token_resp = requests.post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", data={'client_id': client_id, 'client_secret': client_secret, 'scope': 'https://graph.microsoft.com/.default', 'grant_type': 'client_credentials'})
token = token_resp.json().get('access_token')

url = f"https://graph.microsoft.com/v1.0/users/{email}/mailFolders/inbox/messages"
resp = requests.get(url, headers={'Authorization': f'Bearer {token}'}, params={'$top': 10, '$orderby': 'receivedDateTime desc'})

for msg in resp.json().get('value', []):
    status = "READ" if msg.get('isRead') else "UNREAD"
    subj = msg.get('subject', '?')[:50]
    print(f"{status} | {subj}")
