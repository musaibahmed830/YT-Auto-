"""
Quick utility to test and list supported models for Gemini and Groq
using your configured API keys.
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()


def check_gemini():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    print("=" * 60)
    print("GOOGLE GEMINI API CHECK")
    print("=" * 60)
    if not key:
        print("[!] GEMINI_API_KEY is not set in environment or .env file.")
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            models = [m.get("name", "").replace("models/", "") for m in data.get("models", [])]
            flash_models = [m for m in models if "flash" in m]
            print(f"[✓] Connection successful! Found {len(models)} models.")
            print(f"Available 'flash' models: {flash_models}")
        else:
            print(f"[✗] Gemini request failed ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"[✗] Gemini error: {e}")


def check_groq():
    key = os.environ.get("GROQ_API_KEY", "").strip()
    print("\n" + "=" * 60)
    print("GROQ API CHECK")
    print("=" * 60)
    if not key:
        print("[!] GROQ_API_KEY is not set in environment or .env file.")
        return

    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            models = [m.get("id", "") for m in data.get("data", [])]
            print(f"[✓] Connection successful! Found {len(models)} models.")
            print("Available models:")
            for m in sorted(models):
                print(f"  - {m}")
        else:
            print(f"[✗] Groq request failed ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"[✗] Groq error: {e}")


if __name__ == "__main__":
    check_gemini()
    check_groq()
