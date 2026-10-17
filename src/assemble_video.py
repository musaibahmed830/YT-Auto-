"""
Assembles the final video from stock clips + voiceover using ffmpeg.
Requires ffmpeg and ffprobe to be installed and on PATH.
"""

from __future__ import annotations

import os
import subprocess
import json
from typing import Optional, List, Dict, Any


def _get_duration(path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def assemble_video(
    clip_paths: List[str],
    voiceover_path: str,
    title_text: str,
    out_path: str,
    work_dir: str = "work",
    orientation: str = "horizontal",
    max_duration: Optional[float] = None,
) -> str:
    """
    - Normalizes each clip to target resolution:
        horizontal -> 1920x1080 (16:9)
        vertical   -> 1080x1920 (9:16 for YouTube Shorts)
    - Loops/trims clips to cover target duration
    - Adds title overlay
    - Muxes voiceover audio
    """
    os.makedirs(work_dir, exist_ok=True)
    voice_duration = _get_duration(voiceover_path)
    target_duration = min(voice_duration, max_duration) if max_duration else voice_duration

    if not clip_paths:
        raise ValueError("No clips provided to assemble_video")

    is_vertical = orientation == "vertical"
    res_w, res_h = (1080, 1920) if is_vertical else (1920, 1080)
    scale_filter = f"scale={res_w}:{res_h}:force_original_aspect_ratio=increase,crop={res_w}:{res_h}"

    # Normalize clips
    normalized = []
    for i, clip in enumerate(clip_paths):
        if not os.path.exists(clip) or os.path.getsize(clip) < 500:
            continue
        norm_path = os.path.join(work_dir, f"norm_{orientation}_{i:02d}.mp4")
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", clip,
                    "-vf", scale_filter,
                    "-an", "-c:v", "libx264", "-preset", "ultrafast",
                    norm_path,
                ],
                check=True, capture_output=True, text=True,
            )
            normalized.append(norm_path)
        except subprocess.CalledProcessError as e:
            print(f"[assemble_video] Warning: skipping unreadable clip {clip}: {e.stderr[:200] if e.stderr else e}")

    if not normalized:
        print("[assemble_video] Generating emergency background clip...")
        emergency_clip = os.path.join(work_dir, f"emergency_{orientation}.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"color=c=0x0f172a:s={res_w}x{res_h}:d=10",
                "-vf", "noise=alls=10:allf=t+u",
                "-c:v", "libx264", "-preset", "ultrafast", emergency_clip,
            ],
            check=True, capture_output=True,
        )
        normalized.append(emergency_clip)

    # Build concat list to cover target_duration
    per_clip_seconds = max(target_duration / len(normalized), 2.5)
    concat_list_path = os.path.join(work_dir, f"concat_{orientation}.txt")
    with open(concat_list_path, "w") as f:
        total = 0.0
        idx = 0
        while total < target_duration:
            clip = normalized[idx % len(normalized)]
            f.write(f"file '{os.path.abspath(clip)}'\n")
            f.write(f"duration {per_clip_seconds}\n")
            total += per_clip_seconds
            idx += 1
        f.write(f"file '{os.path.abspath(normalized[(idx - 1) % len(normalized)])}'\n")

    concat_video_path = os.path.join(work_dir, f"concat_video_{orientation}.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list_path,
            "-c:v", "libx264", "-preset", "veryfast",
            "-t", str(target_duration),
            concat_video_path,
        ],
        check=True, capture_output=True,
    )

    clean_title = "".join(c for c in title_text if 32 <= ord(c) <= 126 and c not in "'%:[]\\")
    safe_title = clean_title.replace(":", "\\:").strip()
    fontsize = 62 if is_vertical else 54
    y_pos = "h*0.15" if is_vertical else "h*0.08"

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", concat_video_path,
                "-i", voiceover_path,
                "-vf",
                (
                    f"drawtext=text='{safe_title}':fontcolor=white:fontsize={fontsize}:"
                    "box=1:boxcolor=black@0.6:boxborderw=24:"
                    f"x=(w-text_w)/2:y={y_pos}:"
                    "enable='between(t,0,3.5)'"
                ),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-preset", "medium",
                "-c:a", "aac", "-b:a", "192k",
                "-t", str(target_duration),
                out_path,
            ],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"[assemble_video] Drawtext failed ({e.stderr[:200] if e.stderr else e}), assembling without overlay...")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", concat_video_path,
                "-i", voiceover_path,
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-preset", "medium",
                "-c:a", "aac", "-b:a", "192k",
                "-t", str(target_duration),
                out_path,
            ],
            check=True, capture_output=True,
        )

    return out_path


def assemble_synced_video(
    scenes: List[Dict[str, Any]],
    title_text: str,
    out_path: str,
    work_dir: str = "work",
    orientation: str = "horizontal",
    max_duration: Optional[float] = None,
) -> str:
    """
    Renders a video where every scene's visual clip matches the exact words spoken
    at that moment in the story.
    - Each scene provides:
        - 'text': the spoken narration sentence(s) for that scene
        - 'visual_search': concrete visual search keywords for Pexels
    - Generates audio for each scene, downloads matching clip, trims clip to match
      the exact audio duration, and stitches scenes into a seamless narrative video.
    """
    from generate_voiceover import generate_voiceover
    from fetch_visuals import fetch_scene_clip

    os.makedirs(work_dir, exist_ok=True)
    is_vertical = orientation in ("vertical", "portrait")
    res_w, res_h = (1080, 1920) if is_vertical else (1920, 1080)
    scale_filter = f"scale={res_w}:{res_h}:force_original_aspect_ratio=increase,crop={res_w}:{res_h}"

    rendered_scene_files = []
    total_elapsed = 0.0

    print(f"[assemble_video] Building synchronized video ({len(scenes)} scenes, {orientation})...")

    for idx, sc in enumerate(scenes):
        if max_duration and total_elapsed >= max_duration:
            break

        scene_text = sc.get("text", "").strip()
        if not scene_text:
            continue
        scene_query = sc.get("visual_search") or sc.get("visual_keywords") or "cinematic mystery"

        # 1. Generate Voiceover for this specific scene
        sc_audio = os.path.join(work_dir, f"sc_{idx:02d}_{orientation}_audio.mp3")
        generate_voiceover(scene_text, sc_audio)
        sc_dur = _get_duration(sc_audio)

        if max_duration and (total_elapsed + sc_dur) > max_duration:
            sc_dur = max(max_duration - total_elapsed, 2.0)

        # 2. Fetch specific matching clip
        sc_raw_clip = os.path.join(work_dir, f"sc_{idx:02d}_{orientation}_raw.mp4")
        fetch_scene_clip(scene_query, sc_raw_clip, orientation=orientation, min_duration=sc_dur)

        # 3. Trim / loop clip to exactly match the scene's audio duration and mux together
        sc_rendered = os.path.join(work_dir, f"sc_{idx:02d}_{orientation}_rendered.mp4")
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-stream_loop", "-1", "-i", sc_raw_clip,
                    "-i", sc_audio,
                    "-vf", f"{scale_filter},fps=30,format=yuv420p",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                    "-t", str(sc_dur),
                    sc_rendered,
                ],
                check=True, capture_output=True, text=True,
            )
            rendered_scene_files.append(sc_rendered)
            total_elapsed += sc_dur
            print(f"[assemble_video] Scene {idx+1}/{len(scenes)} rendered: '{scene_query}' ({sc_dur:.1f}s)")
        except subprocess.CalledProcessError as e:
            print(f"[assemble_video] Error rendering scene {idx}: {e.stderr[:300] if e.stderr else e}")

    if not rendered_scene_files:
        raise RuntimeError("No scenes were rendered successfully.")

    # Concat all scene segments together
    concat_list = os.path.join(work_dir, f"scenes_concat_{orientation}.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for fpath in rendered_scene_files:
            abs_p = os.path.abspath(fpath).replace("'", "'\\''")
            f.write(f"file '{abs_p}'\n")

    unbranded_video = os.path.join(work_dir, f"unbranded_{orientation}.mp4")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-c", "copy",
                unbranded_video,
            ],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"[assemble_video] Direct concat failed ({e.stderr[:300] if e.stderr else e}), using filter_complex fallback...")
        filter_inputs = []
        for fpath in rendered_scene_files:
            filter_inputs.extend(["-i", fpath])
        n = len(rendered_scene_files)
        filter_complex = "".join(f"[{i}:v][{i}:a]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
        subprocess.run(
            ["ffmpeg", "-y"] + filter_inputs + [
                "-filter_complex", filter_complex,
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "veryfast",
                "-c:a", "aac", "-b:a", "192k",
                unbranded_video,
            ],
            check=True, capture_output=True, text=True,
        )

    # Title card overlay on first 3.5 seconds
    clean_title = "".join(c for c in title_text if 32 <= ord(c) <= 126 and c not in "'%:[]\\")
    safe_title = clean_title.replace(":", "\\:").strip()
    fontsize = 62 if is_vertical else 54
    y_pos = "h*0.15" if is_vertical else "h*0.08"

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", unbranded_video,
                "-vf",
                (
                    f"drawtext=text='{safe_title}':fontcolor=white:fontsize={fontsize}:"
                    "box=1:boxcolor=black@0.6:boxborderw=24:"
                    f"x=(w-text_w)/2:y={y_pos}:"
                    "enable='between(t,0,3.5)'"
                ),
                "-c:v", "libx264", "-preset", "medium",
                "-c:a", "copy",
                out_path,
            ],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"[assemble_video] Drawtext overlay skipped: {e.stderr[:200] if e.stderr else e}")
        subprocess.run(["ffmpeg", "-y", "-i", unbranded_video, "-c", "copy", out_path], check=True, capture_output=True)

    print(f"[assemble_video] Perfectly synchronized video created: {out_path} ({total_elapsed:.1f}s)")
    return out_path


if __name__ == "__main__":
    print("Run via main.py with real clip/voiceover paths.")
