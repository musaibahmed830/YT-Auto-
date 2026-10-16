"""
Assembles the final video from stock clips + voiceover using ffmpeg.
Requires ffmpeg and ffprobe to be installed and on PATH.
"""

import os
import subprocess
import json


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
    clip_paths: list[str],
    voiceover_path: str,
    title_text: str,
    out_path: str,
    work_dir: str = "work",
    orientation: str = "horizontal",
    max_duration: float | None = None,
):
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


if __name__ == "__main__":
    print("Run via main.py with real clip/voiceover paths.")
