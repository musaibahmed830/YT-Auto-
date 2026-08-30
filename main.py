"""
Runs the full daily pipeline end to end:
trending topic -> script -> voiceover -> stock clips -> assembled video
-> thumbnail -> YouTube upload.
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from trend_fetch import get_trending_topic
from seo_research import research_keywords
from generate_script import generate_script
from generate_voiceover import generate_voiceover
from fetch_visuals import fetch_clips, fetch_person_photos
from assemble_video import assemble_video
from generate_thumbnail import generate_thumbnail
from upload_youtube import upload_video

WORK_DIR = "work"
OUTPUT_DIR = "output"


def run():
    os.makedirs(WORK_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Step 1/7: Finding a trending topic...")
    topic = get_trending_topic()
    print(f"  -> Topic: {topic}")

    print("Step 2/7: Researching real search keywords (SEO)...")
    seo_keywords = research_keywords(topic)
    print(f"  -> Keywords: {seo_keywords[:5]}{'...' if len(seo_keywords) > 5 else ''}")

    print("Step 3/7: Generating script + SEO metadata...")
    package = generate_script(topic, seo_keywords=seo_keywords)
    print(f"  -> Title: {package['title']}")

    print("Step 4/7: Generating voiceover...")
    voiceover_path = os.path.join(WORK_DIR, "voiceover.mp3")
    generate_voiceover(package["narration"], voiceover_path)

    print("Step 5/7: Fetching visuals...")
    clip_paths = []
    if package.get("is_specific_person") and package.get("person_name"):
        print(f"  -> Topic is about {package['person_name']}, looking up real photos...")
        clip_paths = fetch_person_photos(package["person_name"], os.path.join(WORK_DIR, "clips"))
        if not clip_paths:
            print("  -> No real photos found, falling back to generic stock clips.")

    if not clip_paths:
        clip_paths = fetch_clips(package["visual_keywords"], os.path.join(WORK_DIR, "clips"))
    if not clip_paths:
        raise RuntimeError("No stock clips found for any keyword - aborting.")

    print("Step 6/7: Assembling video + thumbnail...")
    video_path = os.path.join(OUTPUT_DIR, "video.mp4")
    assemble_video(clip_paths, voiceover_path, package["title"], video_path, work_dir=WORK_DIR)

    thumbnail_path = os.path.join(OUTPUT_DIR, "thumbnail.jpg")
    generate_thumbnail(video_path, package["title"], thumbnail_path)

    print("Step 7/7: Uploading to YouTube...")
    video_id = upload_video(
        video_path=video_path,
        title=package["title"],
        description=package["description"],
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
