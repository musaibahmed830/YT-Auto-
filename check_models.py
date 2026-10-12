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


def check_elevenlabs():
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB").strip()
    print("\n" + "=" * 60)
    print("ELEVENLABS API CHECK")
    print("=" * 60)
    if not key:
        print("[!] ELEVENLABS_API_KEY is not set in environment or .env file.")
        return

    try:
        from elevenlabs.client import ElevenLabs
        client = ElevenLabs(api_key=key)
        voices = client.voices.get_all().voices
        print(f"[✓] Connection successful! Found {len(voices)} voices on account.")
        print(f"Configured ELEVENLABS_VOICE_ID: {repr(voice_id)}")
        print("Available voices:")
        voice_ids = []
        for v in voices:
            voice_ids.append(v.voice_id)
            match_marker = " <-- MATCHES YOUR VOICE_ID!" if v.voice_id == voice_id else ""
            print(f"  - ID: {repr(v.voice_id)} | Name: {v.name}{match_marker}")

        if voice_id in voice_ids:
            print(f"[✓] SUCCESS: Configured voice_id '{voice_id}' is available on your account!")
        else:
            print(f"[!] WARNING: Configured voice_id '{voice_id}' is NOT in your account voices.")
            if voices:
                print(f"    Recommended fix: change ELEVENLABS_VOICE_ID secret to '{voices[0].voice_id}' ({voices[0].name})")
    except Exception as e:
        print(f"[✗] ElevenLabs error: {e}")


def check_edge_tts():
    print("\n" + "=" * 60)
    print("EDGE-TTS (FREE VOICEOVER) CHECK")
    print("=" * 60)
    voice = os.environ.get("EDGE_TTS_VOICE", "en-US-ChristopherNeural").strip()
    print(f"Configured EDGE_TTS_VOICE: '{voice}' (No API key needed!)")
    print("Popular voices available:")
    print("  - en-US-ChristopherNeural (Documentary / Authority)")
    print("  - en-US-GuyNeural (Confident / Energetic)")
    print("  - en-US-AndrewNeural (Modern / Friendly)")
    print("  - en-US-JennyNeural (Natural Female Voice)")
    print("[✓] Ready for zero-cost voiceover generation.")


if __name__ == "__main__":
    check_gemini()
    check_groq()
    check_edge_tts()
    check_elevenlabs()
