#!/usr/bin/env python3
"""
AutoTube AI Studio - Local Dashboard Launcher
Run this script to start the web dashboard:
    python run_dashboard.py
"""

import os
import sys
import webbrowser

def main():
    print("=" * 64)
    print("⚡ AutoTube AI - Multi-Channel Web Dashboard")
    print("=" * 64)

    # Check dependencies
    try:
        import fastapi
        import uvicorn
    except ImportError:
        print("[!] FastAPI and Uvicorn are required to run the Web Studio.")
        print("[*] Installing dependencies from requirements.txt...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi>=0.110.0", "uvicorn>=0.28.0"])

    # Initialize SQLite channels database
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
    from channel_manager import init_db
    init_db()

    port = int(os.environ.get("PORT", 8000))
    url = f"http://localhost:{port}"

    print(f"\n🚀 Server starting on: {url}")
    print("👉 Open this URL in your browser to manage channels & plan series.")
    print("👉 Press Ctrl+C in this terminal to stop the server.\n")

    # Optionally attempt to open browser automatically
    try:
        webbrowser.open(url)
    except Exception:
        pass

    import uvicorn
    uvicorn.run("dashboard_app:app", host="0.0.0.0", port=port, reload=True)

if __name__ == "__main__":
    main()
