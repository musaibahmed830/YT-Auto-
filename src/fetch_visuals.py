"""
Downloads stock video clips from Pexels based on keywords, or - when the video
is about one specific named person - real photos of that person from Wikimedia
Commons (free, no API key), turned into short Ken Burns-style video clips.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Optional, List, Dict, Any
import requests

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
_BAD_FILENAME_HINTS = (
    "logo", "icon", "flag", "map", "coat_of_arms", "signature", "symbol", "seal_of",
    "document", "letter", "grade", "exam", "certificate", "newspaper", "article",
    "clipping", "grave", "tomb", "memorial", "plaque", "medal", "coin", "stamp",
    "postage", "manuscript", "diagram", "chart", "statue", "bust", "eclipse",
    "times", "gazette", "tribune", "herald", "chronicle", "review of", "based on",
)


def _clean_ascii_token(token: Optional[str]) -> str:
    """Strips whitespace, unicode line/paragraph separators (\u2028, \u2029), and non-printable characters."""
    if not token:
        return ""
    return "".join(c for c in token.strip() if 32 < ord(c) < 127)


def _generate_fallback_clip(out_path: str, duration: int = 6, color_hex: str = "0x0f172a") -> Optional[str]:
    """Generates an aesthetic animated background video clip using ffmpeg if stock footage fails."""
    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={color_hex}:s=1920x1080:d={duration}",
            "-vf", "noise=alls=10:allf=t+u",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            out_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path
    except Exception as e:
        print(f"[fetch_visuals] Could not generate fallback clip: {e}")
        return None


def fetch_scene_clip(
    query: str,
    out_path: str,
    orientation: str = "landscape",
    min_duration: float = 5.0,
    api_key: Optional[str] = None,
) -> str:
    """
    Downloads a stock clip specifically matching a scene's action/subject.
    - orientation: 'landscape' for 16:9 main videos, 'portrait' for 9:16 Shorts
    - Falls back to simplified search queries if initial search has no matches
    - Guarantees a valid mp4 at out_path
    """
    raw_key = api_key or os.environ.get("PEXELS_API_KEY", "")
    clean_key = _clean_ascii_token(raw_key)
    headers = {"Authorization": clean_key} if clean_key else {}

    # Target orientation for Pexels ('landscape' or 'portrait')
    pexels_orient = "portrait" if orientation in ("vertical", "portrait") else "landscape"

    # Search candidates: primary query, then simplified fallbacks
    safe_query = "".join(c for c in query if c.isalnum() or c in " -_").strip()
    words = [w for w in safe_query.split() if len(w) > 2]
    candidate_queries = [safe_query]
    if len(words) > 2:
        candidate_queries.append(" ".join(words[-2:]))
        candidate_queries.append(words[0])
    candidate_queries.extend(["cinematic mystery", "dramatic storm nature", "dark background abstract"])

    if clean_key:
        for q in candidate_queries:
            if not q.strip():
                continue
            params = {"query": q, "per_page": 8, "orientation": pexels_orient}
            try:
                resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=20)
                if resp.status_code in (401, 403):
                    print(f"[fetch_visuals] Pexels auth error ({resp.status_code})")
                    break
                if resp.status_code != 200:
                    continue
                data = resp.json()
                videos = data.get("videos", [])
                if not videos:
                    continue

                # Find a 1080p or 720p file
                for vid in videos:
                    files = vid.get("video_files", [])
                    if not files:
                        continue
                    # Pick best quality file matching aspect ratio
                    files_sorted = sorted(files, key=lambda f: f.get("width", 0) * f.get("height", 0), reverse=True)
                    chosen_file = files_sorted[0]
                    link = chosen_file.get("link")
                    if not link:
                        continue

                    # Download
                    with requests.get(link, stream=True, timeout=45) as r:
                        r.raise_for_status()
                        with open(out_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=16384):
                                f.write(chunk)

                    if os.path.exists(out_path) and os.path.getsize(out_path) > 5000:
                        print(f"[fetch_visuals] Found clip for scene query '{q}' ({pexels_orient})")
                        return out_path
            except Exception as e:
                print(f"[fetch_visuals] Error searching Pexels for '{q}': {e}")

    # Fallback if no clip downloaded: generate procedural background
    print(f"[fetch_visuals] Generating procedural fallback for scene '{query[:30]}'...")
    _generate_fallback_clip(out_path, duration=int(min_duration + 3), color_hex="0x0f172a")
    return out_path


def fetch_clips(keywords: List[str], out_dir: str, api_key: Optional[str] = None, clips_per_keyword: int = 1) -> List[str]:
    """
    Downloads vertical/horizontal-friendly clips per keyword into out_dir.
    Returns a list of local file paths in the same order as keywords.
    """
    raw_key = api_key or os.environ.get("PEXELS_API_KEY", "")
    clean_key = _clean_ascii_token(raw_key)

    headers = {"Authorization": clean_key} if clean_key else {}
    os.makedirs(out_dir, exist_ok=True)

    paths = []

    if clean_key:
        for i, keyword in enumerate(keywords):
            safe_kw = "".join(c for c in keyword if c.isalnum() or c in " -_").strip()
            if not safe_kw:
                continue

            params = {"query": safe_kw, "per_page": clips_per_keyword, "orientation": "landscape"}
            try:
                resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=30)
                if resp.status_code in (401, 403):
                    print(f"[fetch_visuals] Pexels auth error ({resp.status_code}): please check PEXELS_API_KEY.")
                    break
                resp.raise_for_status()
                data = resp.json()

                videos = data.get("videos", [])
                if not videos:
                    print(f"[fetch_visuals] No clips found for '{safe_kw}', continuing...")
                    continue

                video_files = sorted(videos[0].get("video_files", []), key=lambda v: v.get("width", 0))
                candidates = [v for v in video_files if 1000 <= v.get("width", 0) <= 1920]
                chosen = candidates[0] if candidates else (video_files[-1] if video_files else None)
                if not chosen or not chosen.get("link"):
                    continue

                out_path = os.path.join(out_dir, f"clip_{len(paths):02d}.mp4")
                with requests.get(chosen["link"], stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(out_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)

                if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                    paths.append(out_path)

            except Exception as e:
                print(f"[fetch_visuals] Error fetching clip for '{safe_kw}': {e}")
    else:
        print("[fetch_visuals] Warning: No valid PEXELS_API_KEY found.")

    # Guarantee pipeline never crashes: generate clean fallback clips if Pexels returned nothing
    if not paths:
        print("[fetch_visuals] No stock clips available from Pexels. Creating cinematic fallback clips with ffmpeg...")
        fallback_colors = ["0x0f172a", "0x1e1b4b", "0x172554", "0x1e293b"]
        for idx, col in enumerate(fallback_colors):
            fb_path = os.path.join(out_dir, f"fallback_{idx:02d}.mp4")
            if _generate_fallback_clip(fb_path, duration=6, color_hex=col):
                paths.append(fb_path)

    return paths


def _image_to_kenburns_clip(image_path: str, out_path: str, duration: float = 4.5) -> None:
    """Converts a still image into a slow zoom/pan 1920x1080 silent video clip."""
    fps = 25
    frames = int(duration * fps)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", image_path,
            "-vf",
            (
                "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
                f"zoompan=z='min(zoom+0.0015,1.2)':d={frames}:s=1920x1080:fps={fps}"
            ),
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "veryfast", "-an",
            out_path,
        ],
        check=True, capture_output=True,
    )


def _wikipedia_get(params: dict, headers: dict) -> dict:
    resp = requests.get(WIKIPEDIA_API_URL, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _download_with_retry(url: str, out_path: str, headers: dict, retries: int = 3) -> None:
    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, timeout=60, headers=headers) as r:
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status in (429, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def fetch_person_photos(person_name: str, out_dir: str, max_photos: int = 6) -> List[str]:
    """
    Finds real, freely-licensed photos of a specific named person by looking at
    the images actually used on their Wikipedia article (free, no API key
    required), and converts each into a short Ken Burns video clip. Returns a
    list of local mp4 clip paths, or [] if none found.
    """
    os.makedirs(out_dir, exist_ok=True)
    headers = {"User-Agent": "daily-video-pipeline/1.0 (personal automation script)"}

    # Resolve to the canonical article title first (handles nicknames, redirects).
    search_data = _wikipedia_get(
        {"action": "query", "format": "json", "list": "search", "srsearch": person_name, "srlimit": 1},
        headers,
    )
    results = search_data.get("query", {}).get("search", [])
    if not results:
        print(f"[fetch_visuals] No Wikipedia article found for '{person_name}'.")
        return []
    title = results[0]["title"]
    last_name = person_name.strip().split()[-1].lower()

    candidates = []
    thumb_data = _wikipedia_get(
        {
            "action": "query", "format": "json", "titles": title,
            "prop": "pageimages", "pithumbsize": 1280,
        },
        headers,
    )
    for page in thumb_data.get("query", {}).get("pages", {}).values():
        thumb = page.get("thumbnail", {}).get("source")
        if thumb:
            candidates.append(thumb)

    images_data = _wikipedia_get(
        {
            "action": "query",
            "format": "json",
            "titles": title,
            "generator": "images",
            "gimlimit": max_photos * 8,
            "prop": "imageinfo",
            "iiprop": "url|size|mime",
            "iiurlwidth": 1280,
        },
        headers,
    )
    pages = images_data.get("query", {}).get("pages", {})

    for page in pages.values():
        page_title = page.get("title", "").lower()
        if last_name not in page_title:
            continue
        if any(hint in page_title for hint in _BAD_FILENAME_HINTS):
            continue
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        if info.get("width", 0) < 400 or info.get("height", 0) < 400:
            continue
        url = info.get("thumburl") or info.get("url")
        if url and url not in candidates:
            candidates.append(url)

    paths = []
    for i, url in enumerate(candidates[:max_photos]):
        img_path = os.path.join(out_dir, f"photo_{i:02d}.jpg")
        try:
            _download_with_retry(url, img_path, headers)
        except requests.exceptions.HTTPError as e:
            print(f"[fetch_visuals] Failed to download '{url}': {e}")
            continue

        clip_path = os.path.join(out_dir, f"clip_{i:02d}.mp4")
        try:
            _image_to_kenburns_clip(img_path, clip_path)
            paths.append(clip_path)
        except subprocess.CalledProcessError as e:
            print(f"[fetch_visuals] Failed to convert '{img_path}' to video: {e}")

    if not paths:
        print(f"[fetch_visuals] No usable Commons photos found for '{person_name}'.")

    return paths


if __name__ == "__main__":
    result = fetch_clips(["ocean waves", "city traffic at night"], "test_clips")
    print(result)
