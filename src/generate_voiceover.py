"""
Converts narration text into an MP3 voiceover using ElevenLabs.
"""

import os
from elevenlabs.client import ElevenLabs

from _sanitize import sanitize_credential, sanitize_text


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
    raw_key = api_key or os.environ["ELEVENLABS_API_KEY"]
    client = ElevenLabs(api_key=sanitize_credential(raw_key))

    raw_voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID")
    if raw_voice_id:
        voice_id = sanitize_credential(raw_voice_id)
    else:
        voice_id = _pick_account_voice_id(client)
        print(f"[generate_voiceover] No ELEVENLABS_VOICE_ID set - using account voice: {voice_id}")

    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        text=sanitize_text(text),
    )

    with open(out_path, "wb") as f:
        for chunk in audio:
            if chunk:
                f.write(chunk)

    return out_path


if __name__ == "__main__":
    generate_voiceover("This is a test of the automated voiceover pipeline.", "test_voice.mp3")
    print("Saved test_voice.mp3")
