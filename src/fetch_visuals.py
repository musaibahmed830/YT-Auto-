"""
Downloads stock video clips from Pexels based on keywords.
"""

import os
import requests

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"


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


if __name__ == "__main__":
    result = fetch_clips(["ocean waves", "city traffic at night"], "test_clips")
    print(result)
