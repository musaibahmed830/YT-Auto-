"""
Generates a short narration script + metadata (title, description, tags)
for a faceless YouTube video based on a trending topic.
"""

import os
import json
import anthropic

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = """You write scripts for short, faceless narration-style YouTube videos \
(60-90 seconds spoken), and you are also an SEO copywriter for YouTube. Style: punchy hook \
in the first line, clear simple sentences, no fluff, no stage directions, no headers - just \
spoken narration text. Return ONLY valid JSON, no markdown fences, no preamble."""


def generate_script(topic: str, seo_keywords: list[str] | None = None, api_key: str | None = None):
    """
    Returns a dict:
    {
        "title": str,          # YouTube title
        "description": str,    # YouTube description
        "tags": [str, ...],
        "narration": str,      # full voiceover script
        "visual_keywords": [str, ...]  # keywords to search stock footage for
    }

    seo_keywords: real search phrases (e.g. from YouTube autocomplete / Google Trends
    related queries) that the title/description/tags should be built around, instead of
    guessing what people search for.
    """
    client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])

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
  "visual_keywords": ["keyword1", "keyword2", "keyword3", "..."]
}}

visual_keywords should be 5-8 concrete, filmable nouns/scenes (e.g. "ocean waves", "city traffic at night") \
that match the narration, suitable for searching stock footage."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = response.content[0].text.strip()
    # Defensive cleanup in case the model wraps in a code fence anyway
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    return json.loads(text)


if __name__ == "__main__":
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "space discoveries"
    result = generate_script(topic)
    print(json.dumps(result, indent=2))
