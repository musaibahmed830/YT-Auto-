"""
Downloads stock video clips from Pexels based on keywords, or - when the video
is about one specific named person - real photos of that person from Wikimedia
Commons (free, no API key), turned into short Ken Burns-style video clips.
"""

import os
import subprocess
import time
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


def fetch_clips(keywords: list[str], out_dir: str, api_key: str | None = None, clips_per_keyword: int = 1):
    """
    Downloads one vertical-friendly clip per keyword into out_dir.
    Returns a list of local file paths in the same order as keywords.
    """
    api_key = api_key or os.environ["PEXELS_API_KEY"]
    headers = {"Authorization": api_key}
    os.makedirs(out_dir, exist_ok=True)

    paths = []
    for i, keyword in enumerate(keywords):
        params = {"query": keyword, "per_page": clips_per_keyword, "orientation": "landscape"}
        resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        videos = data.get("videos", [])
        if not videos:
            print(f"[fetch_visuals] No clips found for '{keyword}', skipping.")
            continue

        # Pick a mid-quality HD file to keep download size reasonable
        video_files = sorted(videos[0]["video_files"], key=lambda v: v.get("width", 0))
        candidates = [v for v in video_files if 1000 <= v.get("width", 0) <= 1920]
        chosen = candidates[0] if candidates else video_files[-1]

        out_path = os.path.join(out_dir, f"clip_{i:02d}.mp4")
        with requests.get(chosen["link"], stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        paths.append(out_path)

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


def fetch_person_photos(person_name: str, out_dir: str, max_photos: int = 6) -> list[str]:
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

    # The infobox lead photo (Wikipedia's canonical "main image" for the
    # article) is almost always an actual portrait - always take it first.
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

    # Supplement with other images used on the article, but only ones whose
    # filename actually names the person - otherwise we pick up unrelated
    # diagrams/documents/events that merely appear somewhere in the article.
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
