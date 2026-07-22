"""
Turns a topic + narration into a strict 6-scene storyboard for the
ComfyUI visual provider. Reuses the same Groq client/key handling as
generate_script.py -- no new paid API.
"""

from __future__ import annotations

import json
import os

from groq import Groq

from _sanitize import sanitize_credential

MODEL = "llama-3.3-70b-versatile"
SCENE_COUNT = 6
MAX_NARRATION_CHARS = 4000

POSITIVE_SUFFIX = (
    "photorealistic cinematic film still, natural skin texture, "
    "realistic fabric detail, cinematic lighting, shallow depth of field, "
    "vertical 9:16 composition, subject clearly framed, no text, no watermark"
)

NEGATIVE_DEFAULT = (
    "illustration, cartoon, anime, painting, drawing, plastic skin, "
    "deformed face, duplicate person, extra fingers, extra hands, "
    "malformed anatomy, blurry subject, low resolution, text, "
    "subtitles, logo, watermark, cropped head"
)

SYSTEM_PROMPT = f"""You are a cinematic storyboard artist for vertical short-form video. \
Given a topic and its finished narration, split it into EXACTLY {SCENE_COUNT} scenes for a \
photorealistic, live-action-style short film -- never illustration, cartoon, or anime.

Rules:
- Exactly {SCENE_COUNT} scenes, numbered 1 to {SCENE_COUNT}.
- Each scene shows ONE visible action -- not an abstract feeling.
- At most two main subjects on screen.
- If a character recurs, describe them with the EXACT SAME wording every time they appear \
(same clothing, same physical description) so the visual stays consistent across scenes.
- Vertical (9:16) composition, photorealistic cinematic imagery only.
- Never mention illustration, cartoon, anime, logos, subtitles, on-screen text, or watermarks --
  the renderer already excludes these, don't reference them.
- The first scene must be a strong visual hook.
- imagePrompt describes concrete, visible, filmable details (setting, subject, action, lighting) \
-- never abstract emotions like "a feeling of hope".
- cameraMotion is one of: slow_push_in, slow_zoom_out, pan_left, pan_right.
- transition is one of: hard_cut, fade.
- motionPrompt describes how imagePrompt's still frame should move for a real 3-4 second \
image-to-video animation of it. It MUST:
  - describe exactly ONE main physical action (not a sequence of multiple actions)
  - describe the subject's own movement (body, head, hands, clothing/hair in the wind, etc.)
  - describe one piece of environmental movement (rain, smoke, leaves, traffic, water, etc.)
  - describe exactly ONE camera movement (matching cameraMotion: a push-in, pull-back, or pan)
  - stay within the SAME scene/setting as imagePrompt -- never introduce a scene change, cut, \
or new location
  - avoid abstract emotional wording ("a feeling of triumph") -- only physically observable motion
  - remain physically realistic, not exaggerated or surreal
  - preserve the exact person/character and clothing already described in imagePrompt/characterBible \
-- motionPrompt animates that same frame, it does not redescribe or change who/what is in it
  - end with the phrase "Natural realistic body motion."
  Example: "The man slowly raises his head and looks toward the approaching car. Rain continues \
falling and his jacket moves subtly in the wind. The camera performs a gentle push-in. Natural \
realistic body motion."

Return ONLY valid JSON matching this exact shape, no markdown fences, no preamble:
{{
  "title": "string",
  "characterBible": "string describing any recurring character, or empty string if none",
  "visualStyle": "string, a short shared visual-style descriptor for the whole video",
  "scenes": [
    {{
      "sceneNumber": 1,
      "durationSeconds": 3,
      "narration": "the portion of the narration this scene covers",
      "imagePrompt": "string",
      "negativePrompt": "string",
      "motionPrompt": "string, see motionPrompt rules above",
      "cameraMotion": "slow_push_in",
      "transition": "hard_cut"
    }}
  ]
}}"""


class StoryboardError(Exception):
    pass


def _client(api_key: str | None) -> Groq:
    return Groq(api_key=sanitize_credential(api_key or os.environ["GROQ_API_KEY"]))


def _ask(client: Groq, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=2000,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    text = response.choices[0].message.content.strip()
    return text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()


def _validate(data: dict) -> dict:
    if not isinstance(data, dict):
        raise StoryboardError("Storyboard response is not a JSON object")
    for key in ("title", "characterBible", "visualStyle", "scenes"):
        if key not in data:
            raise StoryboardError(f"Storyboard missing required key: {key}")

    scenes = data["scenes"]
    if not isinstance(scenes, list) or len(scenes) != SCENE_COUNT:
        raise StoryboardError(f"Storyboard must have exactly {SCENE_COUNT} scenes, got {len(scenes) if isinstance(scenes, list) else 'non-list'}")

    required_scene_keys = {
        "sceneNumber", "durationSeconds", "narration", "imagePrompt",
        "negativePrompt", "motionPrompt", "cameraMotion", "transition",
    }
    valid_motions = {"slow_push_in", "slow_zoom_out", "pan_left", "pan_right"}
    valid_transitions = {"hard_cut", "fade"}

    for i, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise StoryboardError(f"Scene {i} is not an object")
        missing = required_scene_keys - scene.keys()
        if missing:
            raise StoryboardError(f"Scene {i} missing keys: {missing}")
        if not isinstance(scene["imagePrompt"], str) or not scene["imagePrompt"].strip():
            raise StoryboardError(f"Scene {i} has an empty imagePrompt")
        if not isinstance(scene["motionPrompt"], str) or not scene["motionPrompt"].strip():
            raise StoryboardError(f"Scene {i} has an empty motionPrompt")
        if scene.get("cameraMotion") not in valid_motions:
            scene["cameraMotion"] = "slow_push_in"
        if scene.get("transition") not in valid_transitions:
            scene["transition"] = "hard_cut"
        if not isinstance(scene.get("durationSeconds"), (int, float)) or not (2.5 <= scene["durationSeconds"] <= 3.5):
            scene["durationSeconds"] = 3.0

    return data


def _apply_suffixes(data: dict) -> dict:
    for scene in data["scenes"]:
        pos = scene["imagePrompt"].strip()
        if POSITIVE_SUFFIX.split(",")[0] not in pos:  # avoid duplicating if the model already included it
            scene["imagePrompt"] = f"{pos}, {POSITIVE_SUFFIX}"

        neg = (scene.get("negativePrompt") or "").strip()
        if not neg:
            scene["negativePrompt"] = NEGATIVE_DEFAULT
        elif NEGATIVE_DEFAULT.split(",")[0] not in neg:
            scene["negativePrompt"] = f"{neg}, {NEGATIVE_DEFAULT}"
    return data


def generate_storyboard(topic: str, narration: str, api_key: str | None = None) -> dict:
    """
    Returns a validated storyboard dict (see SYSTEM_PROMPT shape above).
    Raises StoryboardError if the model can't produce valid JSON even after
    one repair attempt.
    """
    client = _client(api_key)
    narration_for_prompt = narration[:MAX_NARRATION_CHARS]
    user_prompt = f"Topic: {topic}\n\nFinished narration to storyboard:\n{narration_for_prompt}"

    raw = _ask(client, user_prompt)
    try:
        data = _validate(json.loads(raw))
    except (json.JSONDecodeError, StoryboardError) as first_error:
        repair_prompt = (
            f"{user_prompt}\n\nYour previous response was invalid ({first_error}). "
            f"Here is what you returned:\n{raw}\n\n"
            f"Return ONLY corrected, valid JSON matching the exact required shape."
        )
        raw = _ask(client, repair_prompt)
        try:
            data = _validate(json.loads(raw))
        except (json.JSONDecodeError, StoryboardError) as second_error:
            raise StoryboardError(f"Storyboard generation failed after repair attempt: {second_error}") from second_error

    return _apply_suffixes(data)
