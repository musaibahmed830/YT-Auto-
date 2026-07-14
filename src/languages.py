"""
Shared language -> Piper voice / display-name mapping. Selecting a language
changes both what language the script is WRITTEN in (generate_script.py) and
which Piper voice narrates it (generate_voiceover.py) -- swapping only the
voice while leaving English text would mispronounce badly, since Piper's
phonemizer is language-specific.
"""

DEFAULT_LANGUAGE = "english"

# One curated, verified-to-exist Piper voice per supported language (see
# https://github.com/rhasspy/piper/blob/master/VOICES.md for the full list).
# Piper has no Urdu voice at all as of this writing -- Arabic, Farsi, or
# Hindi are the closest available options.
LANGUAGE_VOICES = {
    "english": "en_US-lessac-medium",
    "spanish": "es_ES-davefx-medium",
    "french": "fr_FR-siwis-medium",
    "german": "de_DE-thorsten-medium",
    "arabic": "ar_JO-kareem-medium",
    "hindi": "hi_IN-pratham-medium",
    "portuguese": "pt_BR-faber-medium",
    "russian": "ru_RU-irina-medium",
    "turkish": "tr_TR-fettah-medium",
    "chinese": "zh_CN-huayan-medium",
}

LANGUAGE_NAMES = {
    "english": "English",
    "spanish": "Spanish",
    "french": "French",
    "german": "German",
    "arabic": "Arabic",
    "hindi": "Hindi",
    "portuguese": "Portuguese",
    "russian": "Russian",
    "turkish": "Turkish",
    "chinese": "Chinese (Simplified)",
}


def voice_for_language(language: str) -> str:
    """Returns the Piper voice model name for a language key, defaulting to English."""
    return LANGUAGE_VOICES.get(language, LANGUAGE_VOICES[DEFAULT_LANGUAGE])


def name_for_language(language: str) -> str:
    """Returns the human-readable language name for a language key, defaulting to English."""
    return LANGUAGE_NAMES.get(language, LANGUAGE_NAMES[DEFAULT_LANGUAGE])
