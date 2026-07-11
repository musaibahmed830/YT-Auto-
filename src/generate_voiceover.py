"""
Converts narration text into an MP3 voiceover using ElevenLabs.
"""

import os
import unicodedata
from elevenlabs.client import ElevenLabs

# A default pre-made ElevenLabs voice ID (Adam). Swap for any voice ID
# from your ElevenLabs account (Voice Library) via the ELEVENLABS_VOICE_ID env var.
DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"

# Unicode categories to strip: Cc/Cf (control/format chars) and Zl/Zp
# (line/paragraph separators, e.g. U+2028, U+2029) that LLMs occasionally
# emit and that some HTTP client internals mis-handle as ASCII.
_STRIP_CATEGORIES = ("Cc", "Cf", "Zl", "Zp")


def _sanitize(text: str) -> str:
    return "".join(
        c for c in text
        if c in "\n\t" or unicodedata.category(c) not in _STRIP_CATEGORIES
    )


def generate_voiceover(text: str, out_path: str, api_key: str | None = None, voice_id: str | None = None):
    client = ElevenLabs(api_key=api_key or os.environ["ELEVENLABS_API_KEY"])
    voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)

    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        text=_sanitize(text),
    )

    with open(out_path, "wb") as f:
        for chunk in audio:
            if chunk:
                f.write(chunk)

    return out_path


if __name__ == "__main__":
    generate_voiceover("This is a test of the automated voiceover pipeline.", "test_voice.mp3")
    print("Saved test_voice.mp3")
