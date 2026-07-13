"""
Generates original AI-illustrated clips as an alternative to stock footage.

Uses Pollinations.ai's free, keyless image API to create an ORIGINAL
illustration per keyword (never a photo/likeness of a real person or a
copyrighted character -- the prompt template below deliberately steers
toward generic cartoon/illustration style), then turns each still image
into a short pan/zoom ("Ken Burns") video clip with ffmpeg so it drops
into assemble_video.py exactly like a stock clip would.
"""

import os
import random
import subprocess
from urllib.parse import quote

import requests

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"

STYLE_SUFFIX = (
    ", vibrant digital illustration, flat cartoon style, bold colors, "
    "no text, no watermark, no logo, no signature"
)


def _build_prompt(keyword: str) -> str:
    return f"{keyword}{STYLE_SUFFIX}"


def _download_image(keyword: str, out_path: str, width: int, height: int, timeout: int = 60) -> bool:
    prompt = quote(_build_prompt(keyword))
    url = POLLINATIONS_URL.format(prompt=prompt)
    params = {"width": width, "height": height, "nologo": "true", "seed": random.randint(0, 999_999)}
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[generate_illustrations] Image request failed for '{keyword}': {e}")
        return False

    with open(out_path, "wb") as f:
        f.write(resp.content)
    return True


def _image_to_clip(img_path: str, out_path: str, width: int, height: int, duration: int = 5, fps: int = 25) -> None:
    frames = duration * fps
    vf = (
        f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
        f"crop={width * 2}:{height * 2},"
        f"zoompan=z='min(zoom+0.0015,1.2)':d={frames}:s={width}x{height}:fps={fps}"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", img_path,
            "-vf", vf, "-t", str(duration), "-pix_fmt", "yuv420p",
            out_path,
        ],
        check=True, capture_output=True,
    )


def generate_illustrations(
    keywords: list[str],
    out_dir: str,
    orientation: str = "landscape",
    clip_seconds: int = 5,
) -> list[str]:
    """
    Downloads one AI-illustrated image per keyword and converts each into a
    short pan/zoom video clip in out_dir. orientation: "landscape" for
    regular videos, "portrait" for Shorts. Returns local clip file paths in
    the same order as keywords (skipping any keyword whose image failed).
    """
    width, height = (1080, 1920) if orientation == "portrait" else (1920, 1080)
    os.makedirs(out_dir, exist_ok=True)

    paths = []
    for i, keyword in enumerate(keywords):
        img_path = os.path.join(out_dir, f"illustration_{i:02d}.jpg")
        if not _download_image(keyword, img_path, width, height):
            print(f"[generate_illustrations] Skipping clip {i} ('{keyword}') -- no image generated.")
            continue

        clip_path = os.path.join(out_dir, f"clip_{i:02d}.mp4")
        try:
            _image_to_clip(img_path, clip_path, width, height, duration=clip_seconds)
        except subprocess.CalledProcessError as e:
            print(f"[generate_illustrations] ffmpeg failed to animate '{keyword}': {e}")
            continue

        paths.append(clip_path)

    return paths


if __name__ == "__main__":
    result = generate_illustrations(["a cozy coffee shop", "a mountain sunrise"], "test_illustrations")
    print(result)
