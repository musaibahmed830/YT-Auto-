"""
Generates a short narration script + metadata (title, description, tags)
for a faceless YouTube video based on a trending topic.

Primary:  Google Gemini  (free via GEMINI_API_KEY)
Fallback: Groq           (free via GROQ_API_KEY)
"""

from __future__ import annotations

import os
import json
import re
from typing import Optional, List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ── Model configuration with automatic fallbacks ─────────────────────────────
# Gemini models: tries in order from newest to stable fallbacks
GEMINI_MODELS = [
    m.strip()
    for m in os.environ.get(
        "GEMINI_MODELS",
        os.environ.get(
            "GEMINI_MODEL",
            "gemini-3.8-flash,gemini-3.7-flash,gemini-3.5-flash-lite,gemini-1.5-flash,gemini-1.5-flash-latest,gemini-1.5-pro",
        ),
    ).split(",")
    if m.strip()
]
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Groq models: reasoning models first (gpt-oss), then 70b/8b versatile fallbacks
GROQ_MODELS = [
    m.strip()
    for m in os.environ.get(
        "GROQ_MODELS",
        os.environ.get(
            "GROQ_MODEL",
            "openai/gpt-oss-120b,openai/gpt-oss-20b,llama-3.3-70b-versatile,llama-3.1-8b-instant,mixtral-8x7b-32768",
        ),
    ).split(",")
    if m.strip()
]
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

SYSTEM_PROMPT = """You write scripts for short, faceless narration-style YouTube videos \
(60-90 seconds spoken), and you are also an SEO copywriter for YouTube. Style: punchy hook \
in the first line, clear simple sentences, no fluff, no stage directions, no headers - just \
spoken narration text. Return ONLY valid JSON, no markdown fences, no preamble."""


def _call_llm(client: OpenAI, model: str, system: str, user: str, max_tokens: int = 4096) -> str:
    """
    Invokes the LLM with compatibility handling for standard vs reasoning models
    (max_tokens vs max_completion_tokens, system prompt support).
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ]

    # Attempt with max_tokens first, fallback to max_completion_tokens if requested
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        err_str = str(e).lower()

        # Some newer/reasoning models require max_completion_tokens instead of max_tokens
        if "max_completion_tokens" in err_str:
            response = client.chat.completions.create(
                model=model,
                max_completion_tokens=max_tokens,
                messages=messages,
            )
            return (response.choices[0].message.content or "").strip()

        # Some reasoning models do not allow system messages
        if "system" in err_str and ("developer" in err_str or "user" in err_str or "role" in err_str):
            combined_prompt = f"{system}\n\n{user}"
            response = client.chat.completions.create(
                model=model,
                max_completion_tokens=max_tokens,
                messages=[{"role": "user", "content": combined_prompt}],
            )
            return (response.choices[0].message.content or "").strip()

        raise


def _clean_and_parse_json(text: str) -> dict:
    """
    Extracts and parses JSON from LLM output, discarding reasoning tags (<think>...</think>),
    markdown fences, and any leading/trailing commentary.
    """
    if not text:
        raise ValueError("Empty response received from LLM")

    # Remove reasoning/thinking tags (e.g. from gpt-oss or DeepSeek models)
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    # Strip code block fences
    cleaned = re.sub(r"^```(?:json)?", "", cleaned.strip(), flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned.strip()).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Extract first outermost JSON object if model included extra commentary
        match = re.search(r"(\{[\s\S]*\})", cleaned)
        if match:
            return json.loads(match.group(1))
        raise


def generate_script(topic: str, seo_keywords: Optional[List[str]] = None, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns a dict:
    {
        "title": str,          # YouTube title
        "description": str,    # YouTube description
        "tags": [str, ...],
        "narration": str,      # full voiceover script
        "visual_keywords": [str, ...],  # keywords to search stock footage for
        "is_specific_person": bool,  # true if the topic centers on one named real person
        "person_name": Optional[str],  # that person's full name, else None
    }

    seo_keywords: real search phrases (e.g. from YouTube autocomplete / Google Trends
    related queries) that the title/description/tags should be built around, instead of
    guessing what people search for.
    """
    keyword_block = ""
    if seo_keywords:
        keyword_list = "\n".join(f"- {kw}" for kw in seo_keywords[:15])
        keyword_block = f"""

Here are REAL phrases people are currently searching for around this topic \
(from YouTube autocomplete and Google Trends related queries):
{keyword_list}

SEO requirements:
- The title MUST naturally include the highest-intent phrase from this list (the one \
that best matches the video's content), placed as early in the title as possible
- Weave 2-4 more of these phrases naturally into the description's first two sentences \
(YouTube weights the opening of the description heavily for search)
- Every tag should either be one of these phrases verbatim, or a close variant of one
- Do NOT keyword-stuff - it must still read naturally to a human"""

    user_prompt = f"""Topic: {topic}{keyword_block}

Create a faceless YouTube short-form video package on this topic. Break the narration into 6-8 sequential SCENES where each scene has concrete visual search terms matching the exact words spoken.

Respond with ONLY this JSON structure:

{{
  "title": "catchy, SEO-optimized YouTube title, under 70 characters",
  "description": "4-5 sentence SEO-optimized YouTube description, keyword-rich opening, soft call to action to subscribe at the end",
  "tags": ["tag1", "tag2", "..."],
  "narration": "the full 60-90 second spoken script, first line is a hook",
  "scenes": [
    {{
      "scene_num": 1,
      "text": "Spoken sentence(s) for scene 1.",
      "visual_search": "concrete filmable stock footage search term for this scene (e.g. vintage airplane cockpit, stormy ocean waves)"
    }},
    {{
      "scene_num": 2,
      "text": "Spoken sentence(s) for scene 2.",
      "visual_search": "concrete filmable stock footage search term for this scene"
    }}
  ],
  "visual_keywords": ["keyword1", "keyword2", "keyword3", "..."],
  "is_specific_person": true or false,
  "person_name": "full name of the person, or null"
}}

visual_search terms MUST be 2-4 concrete, searchable English nouns (e.g. 'ocean waves dark', 'city traffic night', 'hospital hallway') that directly illustrate what the narrator is saying at that exact moment.

is_specific_person is true only when the topic centers on one identifiable named real person \
(a celebrity, politician, athlete, historical figure, etc.) whose actual likeness matters to the video. \
If true, set person_name to that person's full name exactly as it would appear on Wikipedia, so it can be \
looked up for real photos. If the topic is generic (a trend, a concept, a place, an event with no single \
central figure), set is_specific_person to false and person_name to null."""

    # ── Try Gemini first, fall back to Groq ─────────────────────────────────
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    groq_key   = os.environ.get("GROQ_API_KEY", "")

    # Try Gemini candidate models
    if gemini_key:
        client = OpenAI(api_key=gemini_key, base_url=GEMINI_BASE_URL)
        for model in GEMINI_MODELS:
            try:
                print(f"[generate_script] Attempting Gemini with model '{model}'...")
                text = _call_llm(client, model, SYSTEM_PROMPT, user_prompt)
                parsed = _clean_and_parse_json(text)
                print(f"[generate_script] Success with Gemini ({model}).")
                return parsed
            except Exception as e:
                print(f"[generate_script] Gemini ({model}) failed ({e})")

    # Fall back to Groq candidate models
    if groq_key:
        print("[generate_script] Falling back to Groq...")
        client = OpenAI(api_key=groq_key, base_url=GROQ_BASE_URL)
        for model in GROQ_MODELS:
            try:
                print(f"[generate_script] Attempting Groq with model '{model}'...")
                text = _call_llm(client, model, SYSTEM_PROMPT, user_prompt)
                parsed = _clean_and_parse_json(text)
                print(f"[generate_script] Success with Groq ({model}).")
                return parsed
            except Exception as e:
                print(f"[generate_script] Groq ({model}) failed ({e})")

    raise RuntimeError(
        "Both Gemini and Groq failed across all candidate models. "
        "Check that GEMINI_API_KEY and/or GROQ_API_KEY are valid, or verify enabled models using curl."
    )


if __name__ == "__main__":
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "space discoveries"
    result = generate_script(topic)
    print(json.dumps(result, indent=2))
