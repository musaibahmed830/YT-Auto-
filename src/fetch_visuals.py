"""
Downloads stock video clips from Pexels based on keywords.
"""

import os
import requests

from _sanitize import sanitize_credential

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"

# Used when a keyword (e.g. a proper noun the script model slipped in) matches
# nothing on Pexels, so one bad keyword doesn't just shrink the video by a clip.
FALLBACK_QUERY = "cinematic b-roll"


def fetch_clips(
    keywords: list[str],
    out_dir: str,
    api_key: str | None = None,
    clips_per_keyword: int = 1,
    orientation: str = "landscape",
):
    """
    Downloads one clip per keyword into out_dir.
    orientation: "landscape" for regular videos, "portrait" for Shorts.
    Returns a list of local file paths in the same order as keywords.
    """
    api_key = sanitize_credential(api_key or os.environ["PEXELS_API_KEY"])
    headers = {"Authorization": api_key}
    os.makedirs(out_dir, exist_ok=True)

    paths = []
    for i, keyword in enumerate(keywords):
        params = {"query": keyword, "per_page": clips_per_keyword, "orientation": orientation}
        resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        videos = resp.json().get("videos", [])

        if not videos:
            print(f"[fetch_visuals] No clips found for '{keyword}', retrying with fallback query.")
            params["query"] = FALLBACK_QUERY
            resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
            if not videos:
                print(f"[fetch_visuals] Fallback query also returned nothing, skipping clip {i}.")
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


if __name__ == "__main__":
    result = fetch_clips(["ocean waves", "city traffic at night"], "test_clips")
    print(result)
