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


def _sanitize_credential(value: str) -> str:
    # Credentials go straight into HTTP headers and must never contain any
    # whitespace or control/format/separator characters at all (unlike
    # narration text, where an embedded newline is fine).
    return "".join(c for c in value if c.isprintable() and c not in " \t").strip()


def generate_voiceover(text: str, out_path: str, api_key: str | None = None, voice_id: str | None = None):
    # API keys/voice IDs go straight into HTTP headers, so a stray invisible
    # character picked up from a copy-paste (extra whitespace, U+2028, etc.)
    # in the stored secret will crash the request the same way bad narration
    # text would. Sanitize these the same as narration text.
    raw_key = api_key or os.environ["ELEVENLABS_API_KEY"]
    client = ElevenLabs(api_key=_sanitize_credential(raw_key))
    raw_voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
    voice_id = _sanitize_credential(raw_voice_id)

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
