"""
Runs the full YouTube automation pipeline end-to-end.
Supports:
1. Episodic Story Series Mode (Main 1-min video + 20-sec Shorts uploaded together)
2. Daily Trending Mode (fallback when no story series is active)
100% Free Stack: Gemini / Groq + Edge-TTS + Pexels + YouTube API
"""

from __future__ import annotations

import os
import sys
import traceback
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from trend_fetch import get_trending_topic
from seo_research import research_keywords
from generate_script import generate_script
from generate_voiceover import generate_voiceover
from fetch_visuals import fetch_clips, fetch_person_photos
from assemble_video import assemble_video, assemble_synced_video
from generate_thumbnail import generate_thumbnail
from upload_youtube import upload_video
from story_series import (
    get_next_pending_episode,
    mark_episode_completed,
    plan_series,
    load_series_state,
    ensure_scenes,
)

WORK_DIR = "work"
OUTPUT_DIR = "output"


def _process_video_package(package: dict, is_short: bool = False, episode_num: Optional[int] = None) -> str:
    """
    Renders and uploads a single video (either full 60s main video or 20s Shorts).
    Returns the uploaded YouTube video ID.
    """
    suffix = f"_short_ep{episode_num}" if (is_short and episode_num) else (f"_main_ep{episode_num}" if episode_num else ("_short" if is_short else "_main"))
    title = package["title"]
    if is_short and "#shorts" not in title.lower():
        title = f"{title[:50]} #shorts"

    print(f"\n--- Processing {'YouTube SHORT' if is_short else 'MAIN VIDEO'}: '{title}' ---")

    # 1. Prepare synchronized scene structure
    scenes = ensure_scenes(package)
    orientation = "vertical" if is_short else "horizontal"
    max_duration = 22.0 if is_short else 90.0
    video_out = os.path.join(OUTPUT_DIR, f"video{suffix}.mp4")
    sc_work_dir = os.path.join(WORK_DIR, f"sync{suffix}")

    print(f"[pipeline] Rendering 1:1 synchronized {orientation} video ({len(scenes)} scenes)...")
    assemble_synced_video(
        scenes=scenes,
        title_text=package["title"],
        out_path=video_out,
        work_dir=sc_work_dir,
        orientation=orientation,
        max_duration=max_duration,
    )

    # 2. Thumbnail (for main video)
    thumb_path = None
    if not is_short:
        thumb_path = os.path.join(OUTPUT_DIR, f"thumb{suffix}.jpg")
        generate_thumbnail(video_out, package["title"], thumb_path)

    # 5. YouTube Upload
    privacy = os.environ.get("YT_PRIVACY_STATUS", "public")
    tags = package.get("tags", [])
    if is_short and "shorts" not in [t.lower() for t in tags]:
        tags.append("shorts")

    print(f"[pipeline] Uploading to YouTube as {privacy}...")
    video_id = upload_video(
        video_path=video_out,
        title=title,
        description=package["description"],
        tags=tags,
        thumbnail_path=thumb_path,
        privacy_status=privacy,
    )
    print(f"[pipeline] Uploaded successfully: https://www.youtube.com/watch?v={video_id}")
    return video_id


def run():
    os.makedirs(WORK_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Check if a new story prompt was provided via environment variable
    story_prompt = os.environ.get("STORY_PROMPT", "").strip()
    if story_prompt:
        ep_count = int(os.environ.get("STORY_EPISODES", "5"))
        print(f"[main] New story prompt detected: '{story_prompt[:60]}...'")
        plan_series(story_prompt, total_episodes=ep_count)

    # 2. Check if there is an active episodic series with pending episodes
    pending_ep = get_next_pending_episode()
    if pending_ep:
        ep_num = pending_ep["episode_number"]
        print(f"\n========================================================")
        print(f"🎬 EXECUTING EPISODIC STORY: Episode {ep_num} - '{pending_ep.get('episode_title')}'")
        print(f"========================================================")

        # Upload Main Video (60s, 16:9)
        main_vid_id = _process_video_package(pending_ep["full_script"], is_short=False, episode_num=ep_num)

        # Upload YouTube Short (20s, 9:16)
        short_vid_id = _process_video_package(pending_ep["short_script"], is_short=True, episode_num=ep_num)

        # Mark completed in state
        mark_episode_completed(ep_num, main_video_id=main_vid_id, short_video_id=short_vid_id)
        print(f"\n🎉 Episode {ep_num} complete! Both Main Video and Short are live on YouTube.")
        return

    # 3. Fallback: Daily Trending Topic Mode (when no series is active)
    print("\n[main] No pending story episodes. Running Daily Trending Mode...")
    print("Step 1/6: Finding trending topic (RSS feed)...")
    topic = get_trending_topic()
    print(f"  -> Topic: {topic}")

    print("Step 2/6: Researching SEO keywords...")
    seo_keywords = research_keywords(topic)

    print("Step 3/6: Generating main video script...")
    main_package = generate_script(topic, seo_keywords=seo_keywords)

    # Main video upload
    _process_video_package(main_package, is_short=False)

    # Also generate a 20s Short from the same topic
    print("Step 4/6: Generating companion Short script...")
    short_package = {
        "title": f"{main_package['title'][:45]} #shorts",
        "description": f"{main_package['description']}\n\n#shorts #trending #facts",
        "tags": main_package.get("tags", []) + ["shorts", "trending"],
        "narration": main_package["narration"][:280],  # ~20s spoken cut
        "visual_keywords": main_package.get("visual_keywords", [])[:4],
        "is_specific_person": main_package.get("is_specific_person", False),
        "person_name": main_package.get("person_name"),
    }
    _process_video_package(short_package, is_short=True)
    print("\n🎉 Daily Trending run complete! Main video and Short uploaded.")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        print("Pipeline failed:")
        traceback.print_exc()
        sys.exit(1)
