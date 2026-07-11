"""
Generates a simple 1280x720 thumbnail: a frame from the video with
bold title text overlaid. Requires ffmpeg for frame extraction.
"""

import subprocess
from PIL import Image, ImageDraw, ImageFont


def _extract_frame(video_path: str, out_path: str, timestamp: float = 1.5):
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(timestamp), "-i", video_path, "-frames:v", "1", out_path],
        check=True, capture_output=True,
    )


def generate_thumbnail(video_path: str, title_text: str, out_path: str):
    frame_path = out_path.replace(".jpg", "_frame.jpg").replace(".png", "_frame.png")
    _extract_frame(video_path, frame_path)

    img = Image.open(frame_path).convert("RGB").resize((1280, 720))
    draw = ImageDraw.Draw(img)

    # Dark gradient band behind text for readability
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle([0, 480, 1280, 720], fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
    except OSError:
        font = ImageFont.load_default()

    # Simple word-wrap
    words = title_text.upper().split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) > 1150:
            lines.append(current)
            current = word
        else:
            current = test
    lines.append(current)

    y = 500
    for line in lines[:3]:
        draw.text((40, y), line, font=font, fill="white")
        y += 75

    img.save(out_path, quality=90)
    return out_path


if __name__ == "__main__":
    print("Run via main.py with a real video path.")
