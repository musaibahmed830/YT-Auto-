"""
Story Series Planner and State Manager.
Plans multi-part episodic story series with both:
1. Full 60-second main videos (16:9 widescreen)
2. Fast 20-second teaser shorts (9:16 vertical)
Tracks status in 'series_state.json' so daily cron schedules can upload
episodes sequentially until all episodes are completed.
Uses only 100% free models (Gemini / Groq) with zero cost.
"""

import os
import sys
import json
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

STATE_FILE = "series_state.json"


def _get_llm_client():
    from openai import OpenAI
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()

    if gemini_key:
        return OpenAI(
            api_key=gemini_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        ), ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
    elif groq_key:
        return OpenAI(
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1",
        ), ["llama-3.1-8b-instant", "mixtral-8x7b-32768"]
    else:
        raise RuntimeError("Neither GEMINI_API_KEY nor GROQ_API_KEY is configured.")


def plan_series(story_prompt: str, total_episodes: int = 5) -> dict:
    """
    Plans an entire multi-episode story series from a single user prompt.
    Generates both full 60s narrative and 20s shorts for every episode.
    """
    client, models = _get_llm_client()

    system_prompt = (
        "You are an expert viral YouTube storyteller and episodic scriptwriter. "
        "You create gripping, binge-worthy multi-part narrative series (mysteries, sci-fi, "
        "thrillers, historical drama, true crime). Style: intense curiosity hooks, cinematic pacing, "
        "dramatic cliffhangers at the end of each episode ('Subscribe for Part X!'). "
        "Return ONLY pure JSON without markdown code fences."
    )

    user_prompt = f"""Story Concept: {story_prompt}
Total Episodes: {total_episodes}

Plan out a complete {total_episodes}-part YouTube series. For EVERY episode, provide:
1. "full_script": A complete 60-90 second spoken episode script (16:9 main video) with cliffhanger.
2. "short_script": A fast-paced, high-intensity 20-second teaser script (9:16 YouTube Shorts) with a cliffhanger hook ('Full episode on channel!').

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
        "title": "Episode Title under 70 chars with (Part 1)",
        "description": "Engaging description with keywords, episode summary, and subscribe CTA",
        "tags": ["tag1", "tag2", "tag3"],
        "narration": "Full 60-second spoken script. No stage directions or headers. Just spoken words.",
        "visual_keywords": ["cinematic ocean storm", "dark laboratory", "glowing artifact", "desert road night"]
      }},
      "short_script": {{
        "title": "Shocking Hook Title under 55 chars #shorts (Part 1)",
        "description": "Shorts description with hashtags #shorts #mystery",
        "tags": ["shorts", "mystery", "viral"],
        "narration": "Fast 20-second punchy narration ending with a cliffhanger CTA.",
        "visual_keywords": ["intense closeup", "lightning flash", "shadowy figure"]
      }}
    }}
  ]
}}"""

    response_text = None
    for model in models:
        try:
            print(f"[story_planner] Calling LLM with model '{model}'...")
            res = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=6000,
            )
            response_text = (res.choices[0].message.content or "").strip()
            break
        except Exception as e:
            print(f"[story_planner] Model '{model}' error: {e}")

    if not response_text:
        raise RuntimeError("Failed to generate story series plan across all models.")

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
    for ep in plan_data.get("episodes", []):
        ep["status"] = "pending"
        ep["uploaded_at"] = None

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, indent=2, ensure_ascii=False)

    print(f"[story_planner] Successfully planned series '{plan_data['series_title']}' with {len(plan_data['episodes'])} episodes!")
    print(f"[story_planner] Saved plan to {STATE_FILE}")
    return plan_data


def load_series_state() -> dict | None:
    """Loads the active series state from file, or returns None if no series exists."""
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[story_planner] Error reading {STATE_FILE}: {e}")
        return None


def get_next_pending_episode() -> dict | None:
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
