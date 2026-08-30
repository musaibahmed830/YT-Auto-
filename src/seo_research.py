"""
Real keyword research, not just a trending topic.

- YouTube autocomplete: what people actually type into YouTube's search box
  for this topic (free, no API key, uses YouTube's public suggestion endpoint)
- Google Trends "related queries": rising/top searches around the same topic

The combined keyword list gets handed to generate_script.py so the title,
description, and tags are built from real search phrases instead of guesses.
"""

import requests
from pytrends.request import TrendReq


def get_youtube_autocomplete(seed_topic: str, max_suggestions: int = 10):
    """
    Hits YouTube's public autocomplete endpoint (same one the search box uses).
    Returns a list of full search phrases containing the seed topic.
    """
    url = "https://suggestqueries.google.com/complete/search"
    params = {"client": "youtube", "ds": "yt", "q": seed_topic}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        # Response is JSONP-ish: window.google.ac.h(["query",[["suggestion",0],...]])
        import json
        import re
        match = re.search(r"\((.*)\)", resp.text)
        data = json.loads(match.group(1)) if match else []
        suggestions = [item[0] for item in data[1]] if len(data) > 1 else []
        return suggestions[:max_suggestions]
    except Exception as e:
        print(f"[seo_research] YouTube autocomplete failed ({e})")
        return []


def get_related_queries(seed_topic: str, max_queries: int = 10):
    """
    Google Trends related queries (top + rising) for the seed topic.
    """
    try:
        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload([seed_topic], timeframe="today 3-m")
        related = pytrends.related_queries()
        entry = related.get(seed_topic, {})

        results = []
        for key in ("top", "rising"):
            df = entry.get(key)
            if df is not None:
                results.extend(df["query"].tolist())
        # de-dupe, preserve order
        seen = set()
        deduped = [q for q in results if not (q in seen or seen.add(q))]
        return deduped[:max_queries]
    except Exception as e:
        print(f"[seo_research] Google Trends related queries failed ({e})")
        return []


def research_keywords(seed_topic: str):
    """
    Returns a combined, de-duplicated list of real search phrases for this topic,
    ready to hand to the script generator as SEO input.
    """
    autocomplete = get_youtube_autocomplete(seed_topic)
    related = get_related_queries(seed_topic)

    combined = autocomplete + related
    seen = set()
    deduped = [q for q in combined if not (q.lower() in seen or seen.add(q.lower()))]

    if not deduped:
        print("[seo_research] No keyword data found, falling back to seed topic only.")
        return [seed_topic]

    return deduped


if __name__ == "__main__":
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "space discoveries"
    print(research_keywords(topic))
