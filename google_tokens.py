from google_auth_oauthlib.flow import InstalledAppFlow
import json

# SCOPES: adjust as needed — this one allows sending Gmail
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# Launch the browser to authorize
flow = InstalledAppFlow.from_client_secrets_file(
    'client_secrets.json', SCOPES)
creds = flow.run_local_server(port=0)

# Print or save tokens
print("Access Token:", creds.token)
print("Refresh Token:", creds.refresh_token)

# Save to file (optional)
with open('tokens.json', 'w') as token_file:
    token_data = {
        'access_token': creds.token,
        'refresh_token': creds.refresh_token,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'token_uri': creds.token_uri
    }
    json.dump(token_data, token_file, indent=2)