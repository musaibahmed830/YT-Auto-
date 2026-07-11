"""
Converts narration text into an MP3 voiceover using ElevenLabs.
"""

import os
from elevenlabs.client import ElevenLabs

# A default pre-made ElevenLabs voice ID (Adam). Swap for any voice ID
# from your ElevenLabs account (Voice Library) via the ELEVENLABS_VOICE_ID env var.
DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"


def generate_voiceover(text: str, out_path: str, api_key: str | None = None, voice_id: str | None = None):
    client = ElevenLabs(api_key=api_key or os.environ["ELEVENLABS_API_KEY"])
    voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)

    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        text=text,
    )

    with open(out_path, "wb") as f:
        for chunk in audio:
            if chunk:
                f.write(chunk)

    return out_path


if __name__ == "__main__":
    generate_voiceover("This is a test of the automated voiceover pipeline.", "test_voice.mp3")
    print("Saved test_voice.mp3")
