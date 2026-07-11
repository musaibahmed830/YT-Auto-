"""
RUN THIS ONCE, LOCALLY ON YOUR OWN COMPUTER (not in CI).

It opens a browser for you to log into the Google account that owns your
YouTube channel, then prints a refresh token. Save that token as the
YT_REFRESH_TOKEN secret in your GitHub repo - the daily pipeline reuses it
forever (until you revoke access), so this step only happens once.

Prerequisites:
1. Go to https://console.cloud.google.com/ -> create a project
2. Enable the "YouTube Data API v3"
3. Create OAuth 2.0 credentials (type: Desktop app)
4. Download the client secret JSON and save it as client_secret.json
   in this same folder
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0)

print("\n=== SAVE THESE AS GITHUB SECRETS ===")
print(f"YT_CLIENT_ID={creds.client_id}")
print(f"YT_CLIENT_SECRET={creds.client_secret}")
print(f"YT_REFRESH_TOKEN={creds.refresh_token}")
