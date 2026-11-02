#!/usr/bin/env python3
"""
One-click YouTube Refresh Token Generator.
Reads YT_CLIENT_ID and YT_CLIENT_SECRET from .env, opens your browser to sign in,
and automatically writes YT_REFRESH_TOKEN back into your .env file!
"""

import os
import sys

# Auto-switch to workspace .venv if running with system python
venv_python = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python")
if os.path.exists(venv_python) and os.path.abspath(sys.executable) != os.path.abspath(venv_python):
    import subprocess
    sys.exit(subprocess.call([venv_python, __file__] + sys.argv[1:]))

import re
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

# Read .env (with fallback if python-dotenv is absent)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

def main():
    print("=" * 64)
    print("🔑 YouTube Refresh Token Generator")
    print("=" * 64)

    client_id = os.environ.get("YT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YT_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        if os.path.exists("client_secret.json"):
            flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
        else:
            print("\n❌ Error: YT_CLIENT_ID or YT_CLIENT_SECRET not found in .env!")
            print("Please ensure lines in .env have your Client ID and Client Secret.\n")
            return
    else:
        # Use credentials directly from .env
        client_config = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8080/", "http://127.0.0.1:8080/"],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

    print("\n👉 Opening your browser to authorize your YouTube channel...")
    print("👉 If prompted, choose your YouTube Google account and allow permissions.\n")

    creds = flow.run_local_server(port=8080, prompt="consent", access_type="offline")

    refresh_token = creds.refresh_token
    if not refresh_token:
        print("❌ Warning: No refresh token returned. Did you approve offline access?")
        return

    print("\n" + "=" * 64)
    print("🎉 SUCCESS! Got Refresh Token:")
    print(f"YT_REFRESH_TOKEN={refresh_token}")
    print("=" * 64)

    # Automatically save it into .env!
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()

        if "YT_REFRESH_TOKEN=" in content:
            content = re.sub(r"YT_REFRESH_TOKEN=.*", f"YT_REFRESH_TOKEN={refresh_token}", content)
        else:
            content += f"\nYT_REFRESH_TOKEN={refresh_token}\n"

        with open(env_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"\n✅ Automatically saved YT_REFRESH_TOKEN to your .env file!")

    print("You can now connect and upload videos directly!\n")

if __name__ == "__main__":
    main()
