"""
Fetches a trending topic to base today's video on.
Uses Google Trends (pytrends) daily trending searches as the primary source,
with a static fallback list so the pipeline never fails outright.
"""

import random
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


def get_trending_topic(country="united_states"):
    """
    Returns a single trending topic string.
    Falls back to a random topic from FALLBACK_TOPICS if Trends fails
    (e.g. rate-limited, network issue in CI).
    """
    try:
        pytrends = TrendReq(hl="en-US", tz=360)
        trending = pytrends.trending_searches(pn=country)
        topics = trending[0].tolist()
        if topics:
            # Pick the top trend; you could randomize among top N instead
            return topics[0]
    except Exception as e:
        print(f"[trend_fetch] Google Trends failed ({e}), using fallback topic.")

    return random.choice(FALLBACK_TOPICS)


if __name__ == "__main__":
    print(get_trending_topic())
