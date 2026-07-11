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


def generate_thumbnail(video_path: str, title_text: str, out_path: str, vertical: bool = False):
    width, height = (720, 1280) if vertical else (1280, 720)
    frame_path = out_path.replace(".jpg", "_frame.jpg").replace(".png", "_frame.png")
    _extract_frame(video_path, frame_path)

    img = Image.open(frame_path).convert("RGB").resize((width, height))
    draw = ImageDraw.Draw(img)

    # Dark gradient band behind text for readability (bottom third of frame)
    band_top = int(height * 0.667)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle([0, band_top, width, height], fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    font_size = max(36, width // 20)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    # Simple word-wrap
    max_text_width = width - 130
    words = title_text.upper().split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) > max_text_width:
            lines.append(current)
            current = word
        else:
            current = test
    lines.append(current)

    line_height = int(font_size * 1.17)
    y = band_top + int(line_height * 0.3)
    for line in lines[:3]:
        draw.text((40, y), line, font=font, fill="white")
        y += line_height

    img.save(out_path, quality=90)
    return out_path


if __name__ == "__main__":
    print("Run via main.py with a real video path.")
