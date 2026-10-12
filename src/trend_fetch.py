"""
Fetches a trending topic to base today's video on.
Primary:   Google Trends RSS feed (reliable, lightweight, no API deprecation issues)
Secondary: pytrends daily trending searches
Fallback:  Curated static topic list so the pipeline never fails outright.
"""

import random
import xml.etree.ElementTree as ET
import requests
from pytrends.request import TrendReq

FALLBACK_TOPICS = [
    "surprising psychology facts",
    "space discoveries this year",
    "unexplained history mysteries",
    "productivity habits that actually work",
    "weird animal facts",
    "future technology predictions",
    "ancient civilizations mysteries",
    "money habits of self-made millionaires",
]


def _fetch_rss_trends(geo: str = "US") -> list[str]:
    """Fetches trending search queries directly from Google Trends RSS feed."""
    url = f"https://trends.google.com/trending/rss?geo={geo}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    titles = [item.findtext("title") for item in root.findall(".//item") if item.findtext("title")]
    return [t.strip() for t in titles if t and t.strip()]


def get_trending_topic(country="united_states", geo="US"):
    """
    Returns a single trending topic string.
    1. Tries Google Trends RSS feed first.
    2. Falls back to pytrends.
    3. Falls back to curated static list.
    """
    # 1. Try Google Trends RSS feed
    try:
        rss_topics = _fetch_rss_trends(geo=geo)
        if rss_topics:
            topic = rss_topics[0]
            print(f"[trend_fetch] Got trending topic from Google Trends RSS: '{topic}'")
            return topic
    except Exception as e:
        print(f"[trend_fetch] Google Trends RSS failed ({e}), trying pytrends...")

    # 2. Try pytrends
    try:
        pytrends = TrendReq(hl="en-US", tz=360)
        trending = pytrends.trending_searches(pn=country)
        topics = trending[0].tolist()
        if topics:
            topic = topics[0]
            print(f"[trend_fetch] Got trending topic from pytrends: '{topic}'")
            return topic
    except Exception as e:
        print(f"[trend_fetch] pytrends failed ({e}), using fallback topic list.")

    # 3. Static fallback
    chosen = random.choice(FALLBACK_TOPICS)
    print(f"[trend_fetch] Using static fallback topic: '{chosen}'")
    return chosen


if __name__ == "__main__":
    print("Result:", get_trending_topic())
