"""
Converts narration text into an MP3 voiceover using ElevenLabs.
"""

import os
import unicodedata
from elevenlabs.client import ElevenLabs

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


def _pick_account_voice_id(client: ElevenLabs) -> str:
    # Voice Library voices require a paid plan to use via the API (free
    # accounts get a 402 payment_required error) -- "premade" voices are the
    # ones bundled with every account, including free, and always API-usable.
    # Ask the account directly instead of hardcoding a voice ID that may not
    # exist or may not be usable on this plan.
    voices = client.voices.get_all(show_legacy=True).voices
    premade = [v for v in voices if v.category == "premade"]
    candidates = premade or voices
    if not candidates:
        raise RuntimeError(
            "No usable ElevenLabs voices found on this account. "
            "Set ELEVENLABS_VOICE_ID explicitly, or add a voice in the ElevenLabs dashboard."
        )
    return candidates[0].voice_id


def generate_voiceover(text: str, out_path: str, api_key: str | None = None, voice_id: str | None = None):
    # API keys/voice IDs go straight into HTTP headers, so a stray invisible
    # character picked up from a copy-paste (extra whitespace, U+2028, etc.)
    # in the stored secret will crash the request the same way bad narration
    # text would. Sanitize these the same as narration text.
    raw_key = api_key or os.environ["ELEVENLABS_API_KEY"]
    client = ElevenLabs(api_key=_sanitize_credential(raw_key))

    raw_voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID")
    if raw_voice_id:
        voice_id = _sanitize_credential(raw_voice_id)
    else:
        voice_id = _pick_account_voice_id(client)
        print(f"[generate_voiceover] No ELEVENLABS_VOICE_ID set - using account voice: {voice_id}")

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
