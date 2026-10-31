"""
Advanced High-CTR YouTube Thumbnail Generator.
Generates 1280x720 professional, high-converting thumbnails featuring:
1. Smart Frame Extraction: Analyzes multiple video timestamps, scoring contrast,
   luminance, and edge sharpness to select the most visually captivating frame.
2. Cinematic Color Grading: Boosts saturation, contrast, and adds smooth gradient
   scrims for 100% text legibility.
3. Punchy Hook Typography: Formats titles into 2-5 word high-impact phrases with
   bold YouTube fonts (Impact / Arial Bold), dual-tone word accents (Electric Yellow + White),
   heavy 3D drop shadows, and thick outlines.
4. Strategic Branding Badges: Stylish top-left pill badges for episode numbers or format tags.
"""

from __future__ import annotations

import os
import re
import json
import subprocess
from typing import Optional, List, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

FONT_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Impact.ttf",
    "/System/Library/Fonts/Supplemental/Trebuchet MS Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    # Linux (Ubuntu / Debian / Alpine)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    # Windows
    "C:\\Windows\\Fonts\\impact.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
]

# High-CTR emotional trigger words for yellow/red highlight
HIGHLIGHT_KEYWORDS = {
    "ROBOTS", "ROBOT", "AI", "JOB", "JOBS", "SURVIVE", "TRUTH", "DARK", "FUTURE",
    "WAR", "SHOCKING", "SECRET", "STOP", "NEVER", "DANGER", "EXPOSED", "MONEY",
    "HUMAN", "REVOLUTION", "DESTROY", "POWER", "WEALTH", "LOST", "INSANE", "WHY",
    "WORST", "BEST", "MIND", "UNREAL", "TERRIFYING", "KILL", "NEW"
}


def get_system_font(size: int) -> ImageFont.ImageFont:
    """Finds the best available bold headline font on the host system."""
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def extract_best_frame(video_path: str, out_frame_path: str) -> Optional[str]:
    """
    Samples multiple candidate timestamps across the video and selects the frame
    with the highest contrast, richness, and clarity (rejecting dark or blurry frames).
    """
    if not os.path.exists(video_path):
        return None

    duration = 10.0
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", video_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            info = json.loads(res.stdout)
            duration = float(info.get("format", {}).get("duration", 10.0))
    except Exception as e:
        print(f"[generate_thumbnail] ffprobe duration note: {e}")

    # Sample timestamps at 15%, 30%, 50%, 70%, 85% of duration
    sample_ratios = [0.15, 0.30, 0.50, 0.70, 0.85]
    if duration < 3.0:
        sample_ratios = [0.3, 0.6]

    temp_dir = os.path.join("work", "thumb_eval")
    os.makedirs(temp_dir, exist_ok=True)

    best_score = -1.0
    best_img = None

    for i, r in enumerate(sample_ratios):
        ts = max(0.5, duration * r)
        tmp_frame = os.path.join(temp_dir, f"candidate_{i}.jpg")
        cmd = [
            "ffmpeg", "-y", "-ss", f"{ts:.2f}", "-i", video_path,
            "-frames:v", "1", "-q:v", "2", tmp_frame
        ]
        subprocess.run(cmd, capture_output=True)

        if os.path.exists(tmp_frame) and os.path.getsize(tmp_frame) > 0:
            try:
                img = Image.open(tmp_frame).convert("RGB")
                arr = np.array(img, dtype=np.float32)

                # 1. Luminance & Variance
                mean_lum = float(np.mean(arr))
                std_dev = float(np.std(arr))

                # Penalize dark frames (< 45) or washed-out frames (> 235)
                lum_mult = 1.0
                if mean_lum < 45:
                    lum_mult = max(0.05, mean_lum / 45.0)
                elif mean_lum > 235:
                    lum_mult = max(0.05, (255.0 - mean_lum) / 20.0)

                # 2. Edge / Sharpness Score (horizontal gradient variance)
                diff = np.abs(arr[:, 1:, :] - arr[:, :-1, :])
                edge_score = float(np.mean(diff))

                score = (std_dev * 1.5 + edge_score * 2.0) * lum_mult
                if score > best_score:
                    best_score = score
                    best_img = img
            except Exception as e:
                print(f"[generate_thumbnail] Frame {i} eval error: {e}")

    # Clean up candidate files
    for i in range(len(sample_ratios)):
        f = os.path.join(temp_dir, f"candidate_{i}.jpg")
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass

    if best_img is not None:
        best_img.save(out_frame_path, quality=95)
        return out_frame_path
    return None


def clean_hook_text(title: str, max_words: int = 5) -> str:
    """
    Transforms a long YouTube title into a short, punchy 2-5 word thumbnail hook.
    E.g.: 'Will Robots Take Your Job? Part 1: The Factory Floor' -> 'WILL ROBOTS TAKE YOUR JOB?'
    """
    # Remove hashtags
    text = re.sub(r"#\w+", "", title)

    # Remove episode markers (e.g., 'Episode 1:', 'Part 1:', 'Ep. 2 -')
    text = re.sub(r"(?i)\b(episode|part|ep)\s*\d+[\s:\-–—]*", "", text)

    # Clean up whitespace
    text = text.strip()

    # Prioritize punchy clause before colons, dashes, or question mark
    if "?" in text:
        text = text.split("?")[0].strip() + "?"
    elif ":" in text:
        parts = [p.strip() for p in text.split(":") if len(p.strip()) > 3]
        text = parts[0] if parts else text
    elif " - " in text or " — " in text:
        parts = [p.strip() for p in re.split(r"\s+[-—–]\s+", text) if len(p.strip()) > 3]
        text = parts[0] if parts else text

    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words])

    return text.upper().strip()


def generate_thumbnail(
    video_path: str,
    title_text: str,
    out_path: str,
    badge_text: Optional[str] = None,
    custom_hook: Optional[str] = None,
    vertical: bool = False,
) -> str:
    """
    Renders an eye-catching, high-converting thumbnail (1280x720 standard for YouTube API).
    Also generates a companion 1080x1920 vertical cover if vertical is True.
    """
    target_w, target_h = (1280, 720)
    frame_path = out_path.replace(".jpg", "_frame.jpg").replace(".png", "_frame.png")

    # 1. Extract high-quality frame or fallback
    extracted = None
    if os.path.exists(video_path):
        if video_path.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            extracted = video_path
        else:
            extracted = extract_best_frame(video_path, frame_path)

    if extracted and os.path.exists(extracted):
        img = Image.open(extracted).convert("RGB")
        # Crop & scale to 16:9 1280x720
        src_w, src_h = img.size
        target_aspect = target_w / target_h
        src_aspect = src_w / src_h
        if src_aspect > target_aspect:
            new_w = int(src_h * target_aspect)
            left = (src_w - new_w) // 2
            img = img.crop((left, 0, left + new_w, src_h))
        else:
            new_h = int(src_w / target_aspect)
            top = (src_h - new_h) // 2
            img = img.crop((0, top, src_w, top + new_h))
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    else:
        # High-tech cinematic dark background
        img = Image.new("RGB", (target_w, target_h), (15, 23, 42))

    # 2. Cinematic Color Enhancement
    img = ImageEnhance.Color(img).enhance(1.35)       # +35% saturation pop
    img = ImageEnhance.Contrast(img).enhance(1.25)    # +25% rich contrast
    img = ImageEnhance.Sharpness(img).enhance(1.20)   # +20% edge sharpness

    # 3. Dual-Gradient Scrim (Left side and Bottom) for text readability
    overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)

    # Bottom gradient (from y=320 down to y=720)
    for y in range(300, target_h):
        progress = (y - 300) / (target_h - 300)
        alpha = int(220 * (progress ** 1.3))
        ov_draw.line([(0, y), (target_w, y)], fill=(0, 0, 0, alpha))

    # Left-side gradient (protects left-aligned text)
    for x in range(0, 650):
        progress = (650 - x) / 650.0
        alpha = int(140 * (progress ** 1.5))
        ov_draw.line([(x, 0), (x, target_h)], fill=(0, 0, 0, alpha))

    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # 4. Top-Left Pill Badge (e.g. 'EPISODE 01', 'SHORTS')
    if badge_text:
        b_text = badge_text.upper().strip()
        badge_font = get_system_font(26)
        bbox = draw.textbbox((0, 0), b_text, font=badge_font)
        bw = (bbox[2] - bbox[0]) + 36
        bh = (bbox[3] - bbox[1]) + 20
        bx, by = 48, 48

        # Badge shadow + crimson red fill
        draw.rounded_rectangle([bx + 3, by + 4, bx + bw + 3, by + bh + 4], radius=10, fill=(0, 0, 0, 180))
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=10, fill=(229, 9, 20), outline=(255, 255, 255), width=2)
        draw.text((bx + 18, by + 9), b_text, font=badge_font, fill="white")

    # 5. Punchy Hook Text Layout
    hook = custom_hook if custom_hook else clean_hook_text(title_text)
    words = hook.split()
    if not words:
        words = ["MUST", "WATCH"]

    # Break into 1, 2, or 3 short lines
    lines: List[str] = []
    if len(words) <= 3:
        lines = [" ".join(words)]
    elif len(words) <= 5:
        mid = len(words) // 2
        lines = [" ".join(words[:mid]), " ".join(words[mid:])]
    else:
        lines = [" ".join(words[:2]), " ".join(words[2:4]), " ".join(words[4:6])]

    # Dynamic font sizing
    font_size = 92 if len(lines) <= 2 else 76
    font = get_system_font(font_size)

    # Avoid YouTube's bottom-right timestamp badge by anchoring text bottom-left
    start_y = 660 - (len(lines) * (font_size + 16))

    for l_idx, line in enumerate(lines):
        line_words = line.split()
        cur_x = 48
        y = start_y + l_idx * (font_size + 16)

        # Scale down if line exceeds safe width
        line_len = draw.textlength(line, font=font)
        if line_len > 1150:
            scale = 1150 / line_len
            cur_font_size = max(50, int(font_size * scale))
            line_font = get_system_font(cur_font_size)
        else:
            line_font = font

        for w_idx, word in enumerate(line_words):
            clean_w = re.sub(r"[^\w]", "", word).upper()
            is_highlight = clean_w in HIGHLIGHT_KEYWORDS or (
                l_idx == len(lines) - 1 and w_idx == len(line_words) - 1 and len(lines) > 1
            )

            # Two-Tone: Electric Yellow (#FFE600) for focus words, White (#FFFFFF) for others
            fill_color = "#FFE600" if is_highlight else "#FFFFFF"

            # Deep 3D Shadow
            for ox, oy in [(5, 5), (6, 6), (7, 7), (8, 8)]:
                draw.text((cur_x + ox, y + oy), word, font=line_font, fill=(0, 0, 0, 200))

            # Thick Black Outline + Fill
            draw.text(
                (cur_x, y),
                word,
                font=line_font,
                fill=fill_color,
                stroke_width=7,
                stroke_fill="black",
            )

            word_len = draw.textlength(word + " ", font=line_font)
            cur_x += int(word_len)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, quality=95)
    print(f"[generate_thumbnail] ✓ Saved attractive thumbnail: {out_path} (1280x720)")

    # 6. Optional Vertical version for Shorts previews (1080x1920)
    if vertical:
        vert_path = out_path.replace(".jpg", "_vertical.jpg").replace(".png", "_vertical.png")
        _generate_vertical_thumbnail(
            video_path=video_path,
            title_text=title_text,
            out_path=vert_path,
            badge_text=badge_text,
            custom_hook=hook,
        )

    return out_path


def _generate_vertical_thumbnail(
    video_path: str,
    title_text: str,
    out_path: str,
    badge_text: Optional[str] = None,
    custom_hook: Optional[str] = None,
) -> str:
    """Renders a 1080x1920 vertical version of the thumbnail for mobile/Shorts previews."""
    target_w, target_h = (1080, 1920)
    frame_path = out_path.replace(".jpg", "_frame.jpg").replace(".png", "_frame.png")

    extracted = extract_best_frame(video_path, frame_path) if os.path.exists(video_path) else None
    if extracted and os.path.exists(extracted):
        img = Image.open(extracted).convert("RGB")
        src_w, src_h = img.size
        target_aspect = target_w / target_h
        src_aspect = src_w / src_h
        if src_aspect > target_aspect:
            new_w = int(src_h * target_aspect)
            left = (src_w - new_w) // 2
            img = img.crop((left, 0, left + new_w, src_h))
        else:
            new_h = int(src_w / target_aspect)
            top = (src_h - new_h) // 2
            img = img.crop((0, top, src_w, top + new_h))
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    else:
        img = Image.new("RGB", (target_w, target_h), (15, 23, 42))

    img = ImageEnhance.Color(img).enhance(1.35)
    img = ImageEnhance.Contrast(img).enhance(1.25)

    overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    # Bottom gradient
    for y in range(1100, target_h):
        alpha = int(220 * (((y - 1100) / (target_h - 1100)) ** 1.3))
        ov_draw.line([(0, y), (target_w, y)], fill=(0, 0, 0, alpha))

    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Badge
    if badge_text:
        b_text = badge_text.upper().strip()
        badge_font = get_system_font(34)
        bbox = draw.textbbox((0, 0), b_text, font=badge_font)
        bw = (bbox[2] - bbox[0]) + 44
        bh = (bbox[3] - bbox[1]) + 24
        draw.rounded_rectangle([60, 100, 60 + bw, 100 + bh], radius=14, fill=(229, 9, 20), outline=(255, 255, 255), width=2)
        draw.text((82, 112), b_text, font=badge_font, fill="white")

    # Hook Text
    hook = custom_hook if custom_hook else clean_hook_text(title_text)
    words = hook.split()
    lines = [" ".join(words[:2]), " ".join(words[2:4]), " ".join(words[4:6])] if len(words) > 3 else [" ".join(words)]
    lines = [l for l in lines if l]

    font = get_system_font(100)
    start_y = 1750 - (len(lines) * 125)

    for l_idx, line in enumerate(lines):
        line_words = line.split()
        cur_x = 60
        y = start_y + l_idx * 125
        for w_idx, word in enumerate(line_words):
            clean_w = re.sub(r"[^\w]", "", word).upper()
            is_highlight = clean_w in HIGHLIGHT_KEYWORDS or (l_idx == len(lines)-1 and w_idx == len(line_words)-1)
            fill_color = "#FFE600" if is_highlight else "#FFFFFF"
            for ox, oy in [(6, 6), (7, 7), (8, 8)]:
                draw.text((cur_x + ox, y + oy), word, font=font, fill=(0, 0, 0, 200))
            draw.text((cur_x, y), word, font=font, fill=fill_color, stroke_width=8, stroke_fill="black")
            cur_x += int(draw.textlength(word + " ", font=font))

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, quality=95)
    return out_path


if __name__ == "__main__":
    print("Testing generate_thumbnail...")
    if os.path.exists("output/ep1_main.mp4"):
        generate_thumbnail("output/ep1_main.mp4", "Will Robots Take Your Job? Part 1: The Factory Floor", "output/ep1_test_thumb.jpg", badge_text="EPISODE 01")
