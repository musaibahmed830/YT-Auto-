"""
Generates a short narration script + metadata (title, description, tags)
for a faceless YouTube video based on a trending topic.

Primary:  Google Gemini  (free via GEMINI_API_KEY)
Fallback: Groq           (free via GROQ_API_KEY)
"""

import os
import json
from openai import OpenAI

# ── Model config ────────────────────────────────────────────────────────────
GEMINI_MODEL    = "gemini-1.5-flash"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

GROQ_MODEL      = "llama3-70b-8192"
GROQ_BASE_URL   = "https://api.groq.com/openai/v1"

SYSTEM_PROMPT = """You write scripts for short, faceless narration-style YouTube videos \
(60-90 seconds spoken), and you are also an SEO copywriter for YouTube. Style: punchy hook \
in the first line, clear simple sentences, no fluff, no stage directions, no headers - just \
spoken narration text. Return ONLY valid JSON, no markdown fences, no preamble."""


def _call_llm(client: OpenAI, model: str, system: str, user: str) -> str:
    response = client.chat.completions.create(
        model=model,
        max_tokens=1500,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return response.choices[0].message.content.strip()


def generate_script(topic: str, seo_keywords: list[str] | None = None, api_key: str | None = None):
    """
    Returns a dict:
    {
        "title": str,          # YouTube title
        "description": str,    # YouTube description
        "tags": [str, ...],
        "narration": str,      # full voiceover script
        "visual_keywords": [str, ...],  # keywords to search stock footage for
        "is_specific_person": bool,  # true if the topic centers on one named real person
        "person_name": str | None,  # that person's full name, else None
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

Create a faceless YouTube short-form video package on this topic. Respond with ONLY this JSON structure:

{{
  "title": "catchy, SEO-optimized YouTube title, under 70 characters",
  "description": "4-5 sentence SEO-optimized YouTube description, keyword-rich opening, soft call to action to subscribe at the end",
  "tags": ["tag1", "tag2", "..."],
  "narration": "the full 60-90 second spoken script, first line is a hook",
  "visual_keywords": ["keyword1", "keyword2", "keyword3", "..."],
  "is_specific_person": true or false,
  "person_name": "full name of the person, or null"
}}

visual_keywords should be 5-8 concrete, filmable nouns/scenes (e.g. "ocean waves", "city traffic at night") \
that match the narration, suitable for searching stock footage.

is_specific_person is true only when the topic centers on one identifiable named real person \
(a celebrity, politician, athlete, historical figure, etc.) whose actual likeness matters to the video. \
If true, set person_name to that person's full name exactly as it would appear on Wikipedia, so it can be \
looked up for real photos. If the topic is generic (a trend, a concept, a place, an event with no single \
central figure), set is_specific_person to false and person_name to null."""

    # ── Try Gemini first, fall back to Groq ─────────────────────────────────
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    groq_key   = os.environ.get("GROQ_API_KEY", "")

    text = None

    if gemini_key:
        try:
            client = OpenAI(api_key=gemini_key, base_url=GEMINI_BASE_URL)
            text = _call_llm(client, GEMINI_MODEL, SYSTEM_PROMPT, user_prompt)
            print("[generate_script] Used Gemini.")
        except Exception as e:
            print(f"[generate_script] Gemini failed ({e}), trying Groq...")

    if text is None and groq_key:
        try:
            client = OpenAI(api_key=groq_key, base_url=GROQ_BASE_URL)
            text = _call_llm(client, GROQ_MODEL, SYSTEM_PROMPT, user_prompt)
            print("[generate_script] Used Groq.")
        except Exception as e:
            print(f"[generate_script] Groq failed ({e})")

    if text is None:
        raise RuntimeError(
            "Both Gemini and Groq failed. "
            "Ensure GEMINI_API_KEY and/or GROQ_API_KEY are set in GitHub secrets."
        )

    # Defensive cleanup in case the model wraps in a code fence anyway
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    return json.loads(text)


if __name__ == "__main__":
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "space discoveries"
    result = generate_script(topic)
    print(json.dumps(result, indent=2))
