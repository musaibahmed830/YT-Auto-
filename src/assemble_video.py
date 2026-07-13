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
    vertical: bool = False,
):
    """
    - Normalizes each clip to 1920x1080 (or 1080x1920 for Shorts), no audio
    - Loops/trims clips to cover the voiceover's total duration
    - Adds a simple title card overlay for the first 3 seconds
    - Muxes the voiceover as the audio track
    """
    os.makedirs(work_dir, exist_ok=True)
    voice_duration = _get_duration(voiceover_path)
    width, height = (1080, 1920) if vertical else (1920, 1080)

    if not clip_paths:
        raise ValueError("No clips provided to assemble_video")

    # Normalize clips first (scale/crop to target resolution, strip audio)
    normalized = []
    for i, clip in enumerate(clip_paths):
        norm_path = os.path.join(work_dir, f"norm_{i:02d}.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", clip,
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
                "-an", "-c:v", "libx264", "-preset", "veryfast",
                norm_path,
            ],
            check=True, capture_output=True,
        )
        normalized.append(norm_path)

    # Build concat list, repeating clips if needed to cover voice_duration
    per_clip_seconds = max(voice_duration / len(normalized), 3)
    concat_list_path = os.path.join(work_dir, "concat.txt")
    with open(concat_list_path, "w") as f:
        total = 0.0
        idx = 0
        while total < voice_duration:
            clip = normalized[idx % len(normalized)]
            f.write(f"file '{os.path.abspath(clip)}'\n")
            f.write(f"duration {per_clip_seconds}\n")
            total += per_clip_seconds
            idx += 1
        # ffmpeg concat demuxer requires the last file repeated without duration
        f.write(f"file '{os.path.abspath(normalized[(idx - 1) % len(normalized)])}'\n")

    concat_video_path = os.path.join(work_dir, "concat_video.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list_path,
            "-c:v", "libx264", "-preset", "veryfast",
            "-t", str(voice_duration),
            concat_video_path,
        ],
        check=True, capture_output=True,
    )

    # Escape text for ffmpeg's drawtext filter syntax. ffmpeg's own quoted-string
    # parser has no backslash-escape for a literal quote -- the documented
    # workaround is to close the quote, insert a backslash-escaped quote
    # *outside* it, then reopen the quote (the "'\''" idiom). A colon, on the
    # other hand, IS valid to backslash-escape directly within the quotes.
    safe_title = title_text.replace("'", "'\\''").replace(":", "\\:")

    # Add title overlay + mux voiceover audio
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", concat_video_path,
            "-i", voiceover_path,
            "-vf",
            (
                f"drawtext=text='{safe_title}':fontcolor=white:fontsize=54:"
                "box=1:boxcolor=black@0.5:boxborderw=20:"
                "x=(w-text_w)/2:y=h*0.08:"
                "enable='between(t,0,3.5)'"
            ),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "medium",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            out_path,
        ],
        check=True, capture_output=True,
    )

    return out_path


if __name__ == "__main__":
    print("Run via main.py with real clip/voiceover paths.")
