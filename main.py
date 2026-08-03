"""
Runs the full daily pipeline end to end:
trending topic -> script -> voiceover -> stock clips -> assembled video
-> thumbnail -> YouTube upload.
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from trend_fetch import resolve_topic
from seo_research import research_keywords
from generate_script import generate_script
from generate_voiceover import generate_voiceover
from fetch_visuals import fetch_clips
from generate_illustrations import generate_illustrations
from assemble_video import assemble_video
from generate_thumbnail import generate_thumbnail
from upload_youtube import upload_video
from languages import voice_for_language

WORK_DIR = "work"
OUTPUT_DIR = "output"

# Voiceover uses Piper (local, no API key needed) -- not in this list.
REQUIRED_ENV_VARS = [
    "GROQ_API_KEY",
    "PEXELS_API_KEY",
    "YT_CLIENT_ID",
    "YT_CLIENT_SECRET",
    "YT_REFRESH_TOKEN",
]


def _check_required_env_vars():
    # Fail fast with one clear message instead of burning steps 1-6 (and
    # their API usage) only to hit a cryptic error on the last step because
    # a GitHub secret was never added or is empty.
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError(
            "Missing required secret(s): " + ", ".join(missing) + ". "
            "Add them under repo Settings -> Secrets and variables -> Actions "
            "(or export them locally) before running."
        )


def run():
    _check_required_env_vars()
    os.makedirs(WORK_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    topic_mode = os.environ.get("TOPIC_MODE", "trending")
    topic_category = os.environ.get("TOPIC_CATEGORY", "any")
    custom_topic = os.environ.get("CUSTOM_TOPIC", "")
    print(f"Step 1/7: Finding a topic (mode={topic_mode!r}, category={topic_category!r}, custom_topic={custom_topic!r})...")
    if topic_mode == "custom" and not custom_topic.strip():
        print("  WARNING: mode is 'custom' but custom_topic is blank -- falling back to trending.")
    topic = resolve_topic(mode=topic_mode, category=topic_category, custom_topic=custom_topic)
    print(f"  -> Topic: {topic}")

    video_mode = os.environ.get("VIDEO_MODE", "video")
    is_shorts = video_mode == "shorts"

    print("Step 2/7: Researching real search keywords (SEO)...")
    seo_keywords = research_keywords(topic)
    print(f"  -> Keywords: {seo_keywords[:5]}{'...' if len(seo_keywords) > 5 else ''}")

    language = os.environ.get("LANGUAGE", "english")
    print(f"Step 3/7: Generating script + SEO metadata (language={language!r})...")
    package = generate_script(topic, seo_keywords=seo_keywords, language=language)
    print(f"  -> Title: {package['title']}")

    print(f"Step 4/7: Generating voiceover ({language})...")
    voiceover_path = os.path.join(WORK_DIR, "voiceover.wav")
    generate_voiceover(package["narration"], voiceover_path, voice=voice_for_language(language))

    # VisualProvider: "pexels" | "illustration"
    visual_style = os.environ.get("VISUAL_STYLE", "pexels")
    orientation = "portrait" if is_shorts else "landscape"

    if visual_style == "illustration":
        custom_visual_prompt = os.environ.get("CUSTOM_VISUAL_PROMPT", "").strip()
        if custom_visual_prompt:
            # An exact scene/image prompt drives the VISUALS only -- the
            # narration above is unaffected and keeps coming from the topic,
            # never from this prompt.
            print(f"Step 5/7: Generating AI illustration clips from a custom prompt ({orientation})...")
            illustration_prompts = [custom_visual_prompt] * len(package["visual_keywords"])
        else:
            print(f"Step 5/7: Generating AI illustration clips ({orientation})...")
            illustration_prompts = package["visual_keywords"]
        clip_paths = generate_illustrations(
            illustration_prompts,
            os.path.join(WORK_DIR, "clips"),
            orientation=orientation,
            vary_seed_per_clip=bool(custom_visual_prompt),
        )
    else:  # "pexels" (default)
        print(f"Step 5/7: Fetching stock clips ({orientation})...")
        clip_paths = fetch_clips(
            package["visual_keywords"],
            os.path.join(WORK_DIR, "clips"),
            orientation=orientation,
        )
    if not clip_paths:
        raise RuntimeError("No visual clips generated for any keyword - aborting.")

    print(f"Step 6/7: Assembling {'Shorts (1080x1920)' if is_shorts else 'video (1920x1080)'} + thumbnail...")
    video_path = os.path.join(OUTPUT_DIR, "video.mp4")
    assemble_video(
        clip_paths, voiceover_path, package["title"], video_path,
        work_dir=WORK_DIR, vertical=is_shorts, narration=package["narration"],
    )

    thumbnail_path = os.path.join(OUTPUT_DIR, "thumbnail.jpg")
    generate_thumbnail(video_path, package["title"], thumbnail_path, vertical=is_shorts)

    print("Step 7/7: Uploading to YouTube...")
    title = package["title"]
    description = package["description"]
    if is_shorts:
        # #Shorts is the reliable signal YouTube uses to route a video into
        # the Shorts shelf -- vertical + short duration alone isn't enough.
        # Reserve room in the 100-char title cap so it never gets truncated off.
        if "#shorts" not in title.lower():
            title = title[:92].rstrip() + " #Shorts"
        if "#shorts" not in description.lower():
            description = description.rstrip() + "\n\n#Shorts"

    video_id = upload_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=package["tags"],
        thumbnail_path=thumbnail_path,
        privacy_status=os.environ.get("YT_PRIVACY_STATUS", "public"),
    )

    print(f"\nDone! https://www.youtube.com/watch?v={video_id}")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        print("Pipeline failed:")
        traceback.print_exc()
        sys.exit(1)
