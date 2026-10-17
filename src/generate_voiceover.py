"""
Converts narration text into an MP3 voiceover.
Primary:   Microsoft Edge-TTS (100% free, natural neural AI voice, no API key needed).
Fallback:  ElevenLabs (if ELEVENLABS_API_KEY is configured).
"""

from __future__ import annotations

import os
import asyncio
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Top neural voices available in Edge-TTS for YouTube storytelling:
# - en-US-ChristopherNeural (Authoritative, narrative, documentary style)
# - en-US-GuyNeural (Confident, clear, energetic)
# - en-US-AndrewNeural (Casual, modern, engaging)
# - en-US-JennyNeural (Expressive, natural female voice)
DEFAULT_EDGE_VOICE = "en-US-ChristopherNeural"


async def _generate_with_edge_tts(text: str, out_path: str, voice: str):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)


def generate_voiceover(
    text: str,
    out_path: str,
    api_key: Optional[str] = None,
    voice_id: Optional[str] = None,
    model_id: Optional[str] = None,
) -> str:
    """
    Generates an MP3 voiceover file.
    Uses free Edge-TTS by default without needing any API key or subscription.
    Falls back to ElevenLabs if Edge-TTS fails and an ElevenLabs key is available.
    """
    edge_voice = os.environ.get("EDGE_TTS_VOICE", DEFAULT_EDGE_VOICE).strip()

    # 1. Primary: Edge-TTS (free, high quality, no API key)
    try:
        print(f"[generate_voiceover] Generating voiceover using Edge-TTS (voice: '{edge_voice}')...")
        asyncio.run(_generate_with_edge_tts(text, out_path, edge_voice))
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            print(f"[generate_voiceover] Successfully generated voiceover with Edge-TTS at {out_path}")
            return out_path
    except Exception as e:
        print(f"[generate_voiceover] Edge-TTS failed ({e}). Checking ElevenLabs fallback...")

    # 2. Fallback: ElevenLabs (if user has configured it)
    eleven_key = (api_key or os.environ.get("ELEVENLABS_API_KEY", "")).strip()
    if eleven_key:
        try:
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=eleven_key)
            eleven_voice = (voice_id or os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")).strip()
            eleven_model = (model_id or os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")).strip()

            print(f"[generate_voiceover] Attempting ElevenLabs with voice '{eleven_voice}'...")
            audio = client.text_to_speech.convert(
                voice_id=eleven_voice,
                model_id=eleven_model,
                text=text,
            )
            with open(out_path, "wb") as f:
                for chunk in audio:
                    if chunk:
                        f.write(chunk)
            print(f"[generate_voiceover] Successfully generated voiceover with ElevenLabs at {out_path}")
            return out_path
        except Exception as e:
            print(f"[generate_voiceover] ElevenLabs fallback also failed: {e}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        raise RuntimeError(
            "Failed to generate voiceover. Edge-TTS failed, and no working ElevenLabs fallback was available."
        )

    return out_path


if __name__ == "__main__":
    generate_voiceover(
        "This is an automated test of the Edge-TTS voiceover pipeline. No API key needed!",
        "test_voice.mp3",
    )
    print("Saved test_voice.mp3")
