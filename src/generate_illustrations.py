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
    ", semi-realistic 3D animated movie style, cinematic lighting, detailed "
    "shading, consistent character design, no text, no watermark, no logo, "
    "no signature"
)


def _build_prompt(keyword: str) -> str:
    return f"{keyword}{STYLE_SUFFIX}"


def _download_image(
    keyword: str, out_path: str, width: int, height: int, seed: int, timeout: int = 60
) -> bool:
    prompt = quote(_build_prompt(keyword))
    url = POLLINATIONS_URL.format(prompt=prompt)
    # Reusing the same seed across every clip in a video (instead of a fresh
    # random one per image) keeps the color palette/rendering style visually
    # consistent from shot to shot -- the reference look this is styled after
    # uses one consistent illustration style throughout a video, not a
    # different random look per scene.
    params = {"width": width, "height": height, "nologo": "true", "seed": seed}
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[generate_illustrations] Image request failed for '{keyword}': {e}")
        return False

    with open(out_path, "wb") as f:
        f.write(resp.content)
    return True


# Each preset is a (zoom_expr, x_expr, y_expr) triple for ffmpeg's zoompan
# filter. Cycling through these per clip (instead of always the same
# zoom-in-center move) makes a video feel less like "the same still image
# every time" -- pan drift is clamped to min(desired_drift, available_margin)
# so it can never push the crop window out of bounds regardless of the
# current zoom level.
def _motion_presets(frames: int) -> list[tuple[str, str, str]]:
    zoom_in = "min(zoom+0.0015,1.2)"
    zoom_out = "if(eq(on,0),1.2,max(zoom-0.0015,1.0))"
    zoom_fixed = "1.15"

    x_center = "iw/2-(iw/zoom/2)"
    y_center = "ih/2-(ih/zoom/2)"

    def pan_x(sign: str, scale: float = 0.35) -> str:
        return f"{x_center}{sign}min((iw-iw/zoom)/2,(on/{frames})*(iw*{scale}))"

    def pan_y(sign: str, scale: float = 0.35) -> str:
        return f"{y_center}{sign}min((ih-ih/zoom)/2,(on/{frames})*(ih*{scale}))"

    return [
        (zoom_in, x_center, y_center),
        (zoom_in, pan_x("+"), y_center),
        (zoom_in, pan_x("-"), y_center),
        (zoom_out, x_center, y_center),
        (zoom_fixed, x_center, pan_y("+")),
        (zoom_fixed, x_center, pan_y("-")),
    ]


def _image_to_clip(
    img_path: str, out_path: str, width: int, height: int, duration: int = 5, fps: int = 25, motion_index: int = 0
) -> None:
    frames = duration * fps
    presets = _motion_presets(frames)
    zoom_expr, x_expr, y_expr = presets[motion_index % len(presets)]
    vf = (
        f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
        f"crop={width * 2}:{height * 2},"
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={width}x{height}:fps={fps}"
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
    vary_seed_per_clip: bool = False,
) -> list[str]:
    """
    Downloads one AI-illustrated image per keyword and converts each into a
    short pan/zoom video clip in out_dir. orientation: "landscape" for
    regular videos, "portrait" for Shorts. Returns local clip file paths in
    the same order as keywords (skipping any keyword whose image failed).

    vary_seed_per_clip: normally every clip in a video shares one seed so
    the rendering style stays visually consistent across different scenes.
    When the same exact prompt is repeated for every clip (a user-supplied
    custom visual prompt), reusing one seed would render the literal same
    image every time -- so each clip instead gets its own random seed,
    producing different takes on the same described scene.
    """
    width, height = (1080, 1920) if orientation == "portrait" else (1920, 1080)
    os.makedirs(out_dir, exist_ok=True)
    shared_seed = random.randint(0, 999_999)

    paths = []
    for i, keyword in enumerate(keywords):
        seed = random.randint(0, 999_999) if vary_seed_per_clip else shared_seed
        img_path = os.path.join(out_dir, f"illustration_{i:02d}.jpg")
        if not _download_image(keyword, img_path, width, height, seed):
            print(f"[generate_illustrations] Skipping clip {i} ('{keyword}') -- no image generated.")
            continue

        clip_path = os.path.join(out_dir, f"clip_{i:02d}.mp4")
        try:
            _image_to_clip(img_path, clip_path, width, height, duration=clip_seconds, motion_index=i)
        except subprocess.CalledProcessError as e:
            print(f"[generate_illustrations] ffmpeg failed to animate '{keyword}': {e}")
            continue

        paths.append(clip_path)

    return paths


if __name__ == "__main__":
    result = generate_illustrations(["a cozy coffee shop", "a mountain sunrise"], "test_illustrations")
    print(result)
