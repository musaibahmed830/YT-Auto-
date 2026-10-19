"""
Story Series Planner and State Manager.
Plans multi-part episodic story series with both:
1. Full 60-second main videos (16:9 widescreen)
2. Fast 20-second teaser shorts (9:16 vertical)
Tracks status in 'series_state.json' so daily cron schedules can upload
episodes sequentially until all episodes are completed.
Uses only 100% free models (Gemini / Groq) with zero cost.
"""

from __future__ import annotations

import os
import sys
import json
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

STATE_FILE = "series_state.json"


def _call_story_llm(system_prompt: str, user_prompt: str) -> str:
    """
    Calls LLM with automatic multi-model failover:
    1. Tries Gemini models (gemini-3.8-flash, 3.7, 3.5, 1.5-flash, 1.5-pro) with 503 retry.
    2. Automatically falls back to Groq models (llama-3.3-70b, llama-3.1-8b, gpt-oss, mixtral)
       if Gemini fails or experiences service spikes.
    """
    from openai import OpenAI
    import time

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()

    gemini_models = [
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

    groq_models = [
        m.strip()
        for m in os.environ.get(
            "GROQ_MODELS",
            os.environ.get(
                "GROQ_MODEL",
                "llama-3.3-70b-versatile,llama-3.1-8b-instant,openai/gpt-oss-120b,openai/gpt-oss-20b,mixtral-8x7b-32768",
            ),
        ).split(",")
        if m.strip()
    ]

    # 1. Try Gemini
    if gemini_key:
        client = OpenAI(
            api_key=gemini_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        for model in gemini_models:
            for attempt in range(2):
                try:
                    print(f"[story_planner] Calling Gemini model '{model}' (attempt {attempt + 1})...")
                    res = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        max_tokens=6000,
                    )
                    content = (res.choices[0].message.content or "").strip()
                    if content:
                        print(f"[story_planner] ✓ Success with Gemini ({model})!")
                        return content
                except Exception as e:
                    err_str = str(e)
                    print(f"[story_planner] Gemini '{model}' error: {err_str}")
                    # If 503 high demand spike, brief sleep and retry once
                    if ("503" in err_str or "high demand" in err_str.lower() or "overloaded" in err_str.lower()) and attempt == 0:
                        print(f"[story_planner] Temporary 503 spike on '{model}'. Retrying in 2 seconds...")
                        time.sleep(2)
                        continue
                    break

    # 2. Fall back to Groq
    if groq_key:
        print("[story_planner] Gemini unavailable or exhausted. Falling back to Groq candidate models...")
        client = OpenAI(
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1",
        )
        for model in groq_models:
            try:
                print(f"[story_planner] Calling Groq model '{model}'...")
                try:
                    res = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        max_tokens=6000,
                    )
                except Exception as e:
                    err_lower = str(e).lower()
                    if "max_completion_tokens" in err_lower:
                        res = client.chat.completions.create(
                            model=model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            max_completion_tokens=6000,
                        )
                    elif "system" in err_lower and ("user" in err_lower or "role" in err_lower):
                        res = client.chat.completions.create(
                            model=model,
                            messages=[
                                {"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"},
                            ],
                            max_tokens=6000,
                        )
                    else:
                        raise e

                content = (res.choices[0].message.content or "").strip()
                if content:
                    print(f"[story_planner] ✓ Success with Groq ({model})!")
                    return content
            except Exception as e:
                print(f"[story_planner] Groq '{model}' error: {e}")

    raise RuntimeError(
        "Failed to generate story series plan across both Gemini and Groq candidate models. "
        "Please check your GEMINI_API_KEY and GROQ_API_KEY."
    )


def plan_series(story_prompt: str, total_episodes: int = 5) -> Dict[str, Any]:
    """
    Plans an entire multi-episode story series from a single user prompt.
    Generates both full 60s narrative and 20s shorts for every episode.
    """

    system_prompt = (
        "You are an expert viral YouTube storyteller and episodic director. "
        "You write thrilling, scene-by-scene narrative scripts where EACH SCENE'S visual "
        "directly matches the exact words spoken at that moment. "
        "Visual search queries MUST be concrete, filmable English stock footage nouns (e.g. 'airplane cockpit', "
        "'dark stormy ocean', 'old spinning compass', 'foggy forest road'). "
        "Return ONLY pure JSON without markdown code fences."
    )

    user_prompt = f"""Story Concept: {story_prompt}
Total Episodes: {total_episodes}

Plan out a complete {total_episodes}-part YouTube series.
For EVERY episode, break the story into SCENES so that the video footage visually matches the exact words being spoken.
- "full_script" (~60-90s): 6-8 sequential scenes.
- "short_script" (~20s): 3-4 fast-paced intense hook scenes ending with a cliffhanger.

Respond with ONLY this JSON structure:
{{
  "series_title": "Catchy overall series title",
  "series_synopsis": "2-3 sentence overview of the series arc",
  "total_episodes": {total_episodes},
  "episodes": [
    {{
      "episode_number": 1,
      "episode_title": "Episode 1 Subtitle",
      "full_script": {{
        "title": "Catchy Episode Title under 70 chars (Part 1)",
        "description": "Engaging description with keywords, episode summary, and subscribe CTA",
        "tags": ["tag1", "tag2", "tag3"],
        "narration": "Full combined spoken narration text.",
        "scenes": [
          {{
            "scene_num": 1,
            "text": "Exact spoken sentence(s) for scene 1.",
            "visual_search": "concrete stock footage search term (e.g. vintage airplane takeoff runway)"
          }},
          {{
            "scene_num": 2,
            "text": "Exact spoken sentence(s) for scene 2.",
            "visual_search": "airplane cockpit compass close up"
          }}
        ]
      }},
      "short_script": {{
        "title": "Shocking Hook Title under 55 chars #shorts (Part 1)",
        "description": "Shorts description with hashtags #shorts #mystery",
        "tags": ["shorts", "mystery", "viral"],
        "narration": "Full combined 20-second narration text.",
        "scenes": [
          {{
            "scene_num": 1,
            "text": "Hook sentence (0-7s).",
            "visual_search": "ocean storm dark waves"
          }},
          {{
            "scene_num": 2,
            "text": "Escalation sentence (7-14s).",
            "visual_search": "spinning compass needle"
          }},
          {{
            "scene_num": 3,
            "text": "Cliffhanger sentence (14-20s).",
            "visual_search": "military plane dark night sky"
          }}
        ]
      }}
    }}
  ]
}}"""

    response_text = _call_story_llm(system_prompt, user_prompt)

    # Clean JSON
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", response_text).strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned.strip(), flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned.strip()).strip()

    try:
        plan_data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\{[\s\S]*\})", cleaned)
        if match:
            plan_data = json.loads(match.group(1))
        else:
            raise ValueError(f"Could not parse story series JSON: {cleaned[:300]}")

    # Initialize tracking metadata
    plan_data["created_at"] = datetime.utcnow().isoformat()
    plan_data["current_episode_index"] = 0
    now = datetime.now()
    for idx, ep in enumerate(plan_data.get("episodes", [])):
        ep["status"] = "pending"
        ep["uploaded_at"] = None
        # Default schedule: tomorrow at 18:00, then +1 day for subsequent episodes
        default_sched = (now + timedelta(days=idx + 1)).replace(hour=18, minute=0, second=0, microsecond=0)
        ep["scheduled_at"] = default_sched.strftime("%Y-%m-%dT%H:%M")

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2, ensure_ascii=False)

    print(f"[story_planner] Successfully planned series '{plan_data['series_title']}' with {len(plan_data['episodes'])} episodes!")
    print(f"[story_planner] Saved plan to {STATE_FILE}")
    return plan_data


def ensure_scenes(script_dict: dict) -> List[Dict[str, Any]]:
    """
    Ensures a script package has structured scenes with text and visual search queries.
    If 'scenes' is already provided, returns it.
    Otherwise, intelligently segments narration sentences and pairs each with visual search terms.
    """
    existing = script_dict.get("scenes")
    if existing and isinstance(existing, list) and len(existing) > 0:
        return existing

    narration = script_dict.get("narration", "").strip()
    keywords = script_dict.get("visual_keywords", [])
    if not isinstance(keywords, list):
        keywords = []

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", narration) if s.strip()]
    if not sentences:
        return [{"scene_num": 1, "text": narration, "visual_search": "cinematic mystery background"}]

    scenes = []
    for idx, s in enumerate(sentences):
        vk = keywords[idx % len(keywords)] if keywords else "dramatic cinematic background"
        scenes.append({
            "scene_num": idx + 1,
            "text": s,
            "visual_search": vk,
        })
    return scenes


def load_series_state() -> Optional[Dict[str, Any]]:
    """Loads the active series state from file, or returns None if no series exists."""
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Backfill scheduled_at for any episodes that don't have it yet
        modified = False
        now = datetime.now()
        for idx, ep in enumerate(data.get("episodes", [])):
            if not ep.get("scheduled_at"):
                default_sched = (now + timedelta(days=idx + 1)).replace(hour=18, minute=0, second=0, microsecond=0)
                ep["scheduled_at"] = default_sched.strftime("%Y-%m-%dT%H:%M")
                modified = True
        if modified:
            try:
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

        return data
    except Exception as e:
        print(f"[story_planner] Error reading {STATE_FILE}: {e}")
        return None


def get_next_pending_episode() -> Optional[Dict[str, Any]]:
    """Finds the next unuploaded episode in the series."""
    state = load_series_state()
    if not state or not state.get("episodes"):
        return None

    for ep in state["episodes"]:
        if ep.get("status") == "pending":
            return ep
    return None


def mark_episode_completed(episode_number: int, main_video_id: str = "", short_video_id: str = ""):
    """Marks an episode as completed and records video IDs and timestamps."""
    state = load_series_state()
    if not state:
        return

    for ep in state.get("episodes", []):
        if ep.get("episode_number") == episode_number:
            ep["status"] = "completed"
            ep["uploaded_at"] = datetime.utcnow().isoformat()
            ep["main_video_id"] = main_video_id
            ep["short_video_id"] = short_video_id
            break

    # Update index
    completed_count = sum(1 for ep in state["episodes"] if ep.get("status") == "completed")
    state["current_episode_index"] = completed_count

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    print(f"[story_planner] Episode {episode_number} marked as completed! ({completed_count}/{len(state['episodes'])} uploaded)")


def get_series_status_summary() -> str:
    """Returns a readable status summary of the series."""
    state = load_series_state()
    if not state:
        return "No active story series found. Create one with `python src/story_series.py plan 'your topic'`."

    total = len(state.get("episodes", []))
    completed = sum(1 for ep in state.get("episodes", []) if ep.get("status") == "completed")
    pending = total - completed

    lines = [
        f"Series: {state.get('series_title', 'Untitled')}",
        f"Synopsis: {state.get('series_synopsis', '')}",
        f"Progress: {completed}/{total} episodes uploaded ({pending} remaining)",
        "-" * 50,
    ]
    for ep in state.get("episodes", []):
        st = "✓ UPLOADED" if ep.get("status") == "completed" else "⏳ PENDING"
        lines.append(f"Episode {ep.get('episode_number')}: {ep.get('episode_title')} [{st}]")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "plan" and len(sys.argv) > 2:
            prompt = sys.argv[2]
            count = int(sys.argv[3]) if len(sys.argv) > 3 else 5
            plan_series(prompt, total_episodes=count)
        elif cmd == "status":
            print(get_series_status_summary())
        elif cmd == "reset":
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
                print(f"[story_planner] Deleted {STATE_FILE}. Pipeline will revert to daily trending topics.")
            else:
                print("No series_state.json exists.")
        else:
            print("Usage:")
            print("  python src/story_series.py plan \"Your story idea\" [episode_count]")
            print("  python src/story_series.py status")
            print("  python src/story_series.py reset")
    else:
        print(get_series_status_summary())
