#!/usr/bin/env python3
"""
AutoTube AI Studio - Local Dashboard Launcher
Run this script to start the web dashboard:
    python3 run_dashboard.py
"""

import os
import sys
import socket
import warnings
import webbrowser

# Silence deprecation warnings for clean terminal experience
warnings.filterwarnings("ignore", category=FutureWarning)


def find_available_port(preferred_port: int = 8000, max_attempts: int = 50) -> int:
    """Finds the first available TCP port starting from preferred_port."""
    for p in range(preferred_port, preferred_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("0.0.0.0", p))
                return p
        except OSError:
            continue
    return preferred_port


def main():
    # If current python is not in .venv and .venv exists, automatically re-execute via .venv
    venv_python = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python")
    if os.path.exists(venv_python) and os.path.abspath(sys.executable) != os.path.abspath(venv_python):
        try:
            import fastapi
            import uvicorn
        except ImportError:
            import subprocess
            sys.exit(subprocess.call([venv_python, __file__] + sys.argv[1:]))

    print("=" * 64)
    print("⚡ AutoTube AI - Multi-Channel Web Dashboard")
    print("=" * 64)

    # Check dependencies
    try:
        import fastapi
        import uvicorn
    except ImportError:
        print("[!] FastAPI and Uvicorn are required to run the Web Studio.")
        print("[*] Installing dependencies...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi>=0.110.0", "uvicorn>=0.28.0"])

    # Initialize SQLite channels database
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
    from channel_manager import init_db
    init_db()

    env_port = os.environ.get("PORT")
    if env_port:
        port = int(env_port)
    else:
        # Automatically find an available port if 8000 is occupied by Docker or other apps
        port = find_available_port(preferred_port=8000)

    url = f"http://localhost:{port}"

    print(f"\n🚀 Server starting on: {url}")
    print(f"👉 Open this URL in your browser to manage channels & plan series.")
    print("👉 Press Ctrl+C in this terminal to stop the server.\n")

    # Open browser automatically
    try:
        webbrowser.open(url)
    except Exception:
        pass

    import uvicorn
    uvicorn.run("dashboard_app:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    main()
