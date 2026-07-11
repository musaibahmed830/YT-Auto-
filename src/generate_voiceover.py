"""
Converts narration text into a WAV voiceover using Piper -- a local,
open-source neural TTS engine. Synthesis runs entirely on the machine
executing this script (no network call to a paid API), so there's no
character limit, no API key, and no monthly quota: it's free and unlimited
because nothing is being metered.
"""

import os
import subprocess
import sys
import wave

from piper import PiperVoice

from _sanitize import sanitize_text

DEFAULT_VOICE = "en_US-lessac-medium"

# Repo root's voices/ dir (sibling of src/), cached across CI runs via
# actions/cache in the workflow so the ~60MB model isn't re-downloaded daily.
VOICES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voices")


def _ensure_voice(voice_name: str) -> str:
    """Downloads the voice model on first use. Returns the local .onnx path."""
    os.makedirs(VOICES_DIR, exist_ok=True)
    model_path = os.path.join(VOICES_DIR, f"{voice_name}.onnx")
    config_path = model_path + ".json"

    if not (os.path.exists(model_path) and os.path.exists(config_path)):
        print(f"[generate_voiceover] Downloading Piper voice '{voice_name}' (one-time, ~60MB)...")
        subprocess.run(
            [sys.executable, "-m", "piper.download_voices", voice_name, "--data-dir", VOICES_DIR],
            check=True,
        )

    return model_path


def generate_voiceover(text: str, out_path: str, voice: str | None = None):
    voice_name = voice or os.environ.get("PIPER_VOICE", DEFAULT_VOICE)
    model_path = _ensure_voice(voice_name)

    tts_voice = PiperVoice.load(model_path)
    with wave.open(out_path, "wb") as wav_file:
        tts_voice.synthesize_wav(sanitize_text(text), wav_file)

    return out_path


if __name__ == "__main__":
    generate_voiceover("This is a test of the automated voiceover pipeline.", "test_voice.wav")
    print("Saved test_voice.wav")
