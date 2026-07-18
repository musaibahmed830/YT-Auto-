"""
Assembles the final video from stock clips + voiceover using ffmpeg.
Requires ffmpeg and ffprobe to be installed and on PATH.
"""

import math
import os
import re
import subprocess
import json

MAX_CAPTION_WORDS = 6
XFADE_DURATION = 0.6  # seconds -- crossfade dissolve length between scenes


def _get_duration(path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def _write_caption_file(text: str, path: str) -> str:
    # Sidesteps ffmpeg's drawtext filtergraph string-escaping entirely --
    # apostrophes, colons, and other punctuation in the caption text need no
    # special handling at all when read from a file via textfile=, unlike an
    # inline text='...' value (which turned out to mis-parse apostrophes in
    # this ffmpeg build, silently swallowing the rest of the filter chain as
    # literal on-screen text).
    with open(path, "w") as f:
        f.write(text)
    return path


def _chunk_narration_for_captions(narration: str, max_words: int = MAX_CAPTION_WORDS) -> list[str]:
    """
    Splits narration into short, punchy caption chunks (a handful of words
    each) instead of one long block of text -- mirrors the dramatic
    on-screen caption style common in this genre (e.g. "THEY CALL IT",
    "HIS NAME ECHOES ACROSS THE DESERT").
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", narration.strip()) if s.strip()]

    chunks = []
    for sentence in sentences:
        words = sentence.split()
        for i in range(0, len(words), max_words):
            chunk = " ".join(words[i : i + max_words]).strip(".,!?")
            if chunk:
                chunks.append(chunk.upper())

    return chunks


def assemble_video(
    clip_paths: list[str],
    voiceover_path: str,
    title_text: str,
    out_path: str,
    work_dir: str = "work",
    vertical: bool = False,
    narration: str | None = None,
):
    """
    - Normalizes each clip to 1920x1080 (or 1080x1920 for Shorts), no audio
    - Loops/trims clips to cover the voiceover's total duration
    - Adds a simple title card overlay for the first 3 seconds
    - If narration is given, burns in short dramatic captions (a handful of
      words at a time, evenly timed across the rest of the video) --
      matching the on-screen caption style common in this genre
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

    # Cross-dissolve between scenes instead of hard-cutting -- loops through
    # normalized clips (repeating as needed) to cover voice_duration, same as
    # before, but joins them with an xfade chain. Each slot is looped/trimmed
    # to an exact duration via -stream_loop so the xfade offset math is
    # deterministic regardless of the source clip's real length. +1 slot is
    # extra slack so the crossfade overlaps never leave the merged sequence
    # shorter than voice_duration (the final -t trims off any excess).
    per_clip_seconds = max(voice_duration / len(normalized), 3)
    n_slots = math.ceil(voice_duration / per_clip_seconds) + 1

    concat_video_path = os.path.join(work_dir, "concat_video.mp4")

    if n_slots == 1:
        subprocess.run(
            [
                "ffmpeg", "-y", "-stream_loop", "-1", "-t", str(voice_duration), "-i", normalized[0],
                "-c:v", "libx264", "-preset", "veryfast",
                concat_video_path,
            ],
            check=True, capture_output=True,
        )
    else:
        input_args = []
        for slot in range(n_slots):
            clip = normalized[slot % len(normalized)]
            input_args += ["-stream_loop", "-1", "-t", str(per_clip_seconds), "-i", clip]

        filters = []
        prev_label = "0:v"
        cumulative = per_clip_seconds
        for slot in range(1, n_slots):
            offset = cumulative - XFADE_DURATION
            out_label = f"xf{slot}"
            filters.append(
                f"[{prev_label}][{slot}:v]xfade=transition=fade:"
                f"duration={XFADE_DURATION}:offset={offset:.3f}[{out_label}]"
            )
            prev_label = out_label
            cumulative += per_clip_seconds - XFADE_DURATION

        subprocess.run(
            [
                "ffmpeg", "-y", *input_args,
                "-filter_complex", ";".join(filters),
                "-map", f"[{prev_label}]",
                "-c:v", "libx264", "-preset", "veryfast",
                "-t", str(voice_duration),
                concat_video_path,
            ],
            check=True, capture_output=True,
        )

    title_file = _write_caption_file(title_text, os.path.join(work_dir, "title.txt"))
    title_filter = (
        f"drawtext=textfile='{title_file}':fontcolor=white:fontsize=54:"
        "box=1:boxcolor=black@0.5:boxborderw=20:"
        "x=(w-text_w)/2:y=h*0.08:"
        "enable='between(t,0,3.5)'"
    )
    filters = [title_filter]

    # Dramatic short captions, timed evenly across the video after the
    # title fades -- e.g. "THEY CALL IT", "HIS NAME ECHOES ACROSS THE DESERT".
    if narration:
        caption_start = 3.5
        chunks = _chunk_narration_for_captions(narration)
        remaining = max(voice_duration - caption_start, 0)
        if chunks and remaining > 0:
            per_caption = remaining / len(chunks)
            for i, chunk in enumerate(chunks):
                start = caption_start + i * per_caption
                end = start + per_caption
                caption_file = _write_caption_file(
                    chunk, os.path.join(work_dir, f"caption_{i:02d}.txt")
                )
                filters.append(
                    f"drawtext=textfile='{caption_file}':fontcolor=white:fontsize=64:"
                    "box=1:boxcolor=black@0.55:boxborderw=18:"
                    "x=(w-text_w)/2:y=h*0.78:"
                    f"enable='between(t,{start:.2f},{end:.2f})'"
                )

    # Add title + caption overlays, then mux the voiceover audio.
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", concat_video_path,
            "-i", voiceover_path,
            "-vf", ",".join(filters),
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
