"""
Batch generator and uploader for all video thumbnails.
Generates attractive thumbnails for all completed episodes (both main and shorts)
and uploads them to YouTube.
"""

from __future__ import annotations

import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from generate_thumbnail import generate_thumbnail
from upload_youtube import set_thumbnail

OUTPUT_DIR = "output"
STATE_FILE = "series_state.json"


def generate_all_thumbnails(upload: bool = False):
    if not os.path.exists(STATE_FILE):
        print(f"State file {STATE_FILE} not found.")
        return

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    episodes = state.get("episodes", [])
    print(f"\n========================================================")
    print(f"🎨 Generating Attractive Thumbnails for {len(episodes)} Episodes")
    print(f"========================================================\n")

    generated_records = []

    for ep in episodes:
        ep_num = ep.get("episode_number")
        status = ep.get("status")
        full_pkg = ep.get("full_script", {})
        short_pkg = ep.get("short_script", {})

        main_vid_id = ep.get("main_video_id")
        short_vid_id = ep.get("short_video_id")

        print(f"--- Episode {ep_num}: '{ep.get('episode_title')}' (Status: {status}) ---")

        # 1. Main Video Thumbnail
        main_vid_file = os.path.join(OUTPUT_DIR, f"ep{ep_num}_main.mp4")
        main_thumb_file = os.path.join(OUTPUT_DIR, f"ep{ep_num}_thumb.jpg")
        if os.path.exists(main_vid_file):
            print(f"  [Main] Generating attractive thumbnail for '{full_pkg.get('title')}'...")
            generate_thumbnail(
                video_path=main_vid_file,
                title_text=full_pkg.get("title", f"Episode {ep_num}"),
                out_path=main_thumb_file,
                badge_text=f"EPISODE {ep_num:02d}",
                vertical=False,
            )
            generated_records.append({
                "type": "main",
                "episode": ep_num,
                "video_id": main_vid_id,
                "thumb_path": main_thumb_file,
                "title": full_pkg.get("title"),
            })
        else:
            print(f"  [Main] Video file {main_vid_file} not found, skipping.")

        # 2. Short Video Thumbnail
        short_vid_file = os.path.join(OUTPUT_DIR, f"ep{ep_num}_short.mp4")
        short_thumb_file = os.path.join(OUTPUT_DIR, f"ep{ep_num}_short_thumb.jpg")
        if os.path.exists(short_vid_file):
            print(f"  [Short] Generating attractive thumbnail for '{short_pkg.get('title')}'...")
            short_title = short_pkg.get("title", f"Episode {ep_num} Short")
            generate_thumbnail(
                video_path=short_vid_file,
                title_text=short_title,
                out_path=short_thumb_file,
                badge_text=f"EPISODE {ep_num:02d}",
                vertical=True,
            )
            generated_records.append({
                "type": "short",
                "episode": ep_num,
                "video_id": short_vid_id,
                "thumb_path": short_thumb_file,
                "title": short_title,
            })
        else:
            print(f"  [Short] Video file {short_vid_file} not found, skipping.")

        print()

    print(f"\n✓ Generated {len(generated_records)} attractive thumbnails locally!\n")

    if upload:
        print(f"========================================================")
        print(f"🚀 Uploading Thumbnails to YouTube")
        print(f"========================================================\n")
        success_count = 0
        for rec in generated_records:
            vid_id = rec.get("video_id")
            thumb_path = rec.get("thumb_path")
            title = rec.get("title")
            ep_str = f"Ep {rec['episode']} ({rec['type'].upper()})"

            if not vid_id or vid_id == "local_rendered":
                print(f"  [{ep_str}] No valid YouTube video ID recorded (got: {vid_id}), skipping upload.")
                continue

            print(f"  [{ep_str}] Uploading thumbnail for '{title}' (ID: {vid_id})...")
            ok = set_thumbnail(video_id=vid_id, thumbnail_path=thumb_path)
            if ok:
                success_count += 1
            print()

        print(f"🎉 Upload complete: {success_count} thumbnails successfully uploaded to YouTube!\n")


if __name__ == "__main__":
    upload_flag = "--upload" in sys.argv
    generate_all_thumbnails(upload=upload_flag)

