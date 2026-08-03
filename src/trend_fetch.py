"""
Resolves today's video topic. Three modes:

  trending -> Google Trends daily trending searches, with a static fallback
              list so the pipeline never fails outright (Trends is flaky
              from cloud IPs / CI runners).
  category -> a random topic from a curated list for a chosen category.
  custom   -> exact topic text supplied by the caller (e.g. a manual
              workflow_dispatch run).
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

CATEGORY_TOPICS = {
    "facts": [
        "surprising psychology facts",
        "weird animal facts",
        "facts about the human body",
        "mind-blowing science facts",
        "facts most people don't know",
    ],
    "science": [
        "space discoveries this year",
        "future technology predictions",
        "strange physics phenomena explained simply",
        "how the human brain actually works",
        "breakthrough inventions changing the world",
    ],
    "history": [
        "unexplained history mysteries",
        "ancient civilizations mysteries",
        "historical events that changed the world",
        "lost cities and civilizations",
        "history's biggest unsolved mysteries",
    ],
    "motivation": [
        "productivity habits that actually work",
        "habits of highly successful people",
        "morning routines of high achievers",
        "how to build discipline that lasts",
        "mindset shifts that change your life",
        "why most people give up too early",
        "how to stop procrastinating for good",
        "the 5-second rule for building habits",
        "how to stay consistent when motivation fades",
        "signs you're stuck in your comfort zone",
        "how failure builds successful people",
        "the compound effect of small daily habits",
        "how to build unshakeable self-discipline",
        "why comparison kills your motivation",
        "how top performers handle setbacks",
        "the psychology of getting things done",
        "how to build confidence from scratch",
        "why hard work beats motivation",
        "how successful people handle failure",
        "the danger of overthinking every decision",
        "how to reset your mindset after a bad day",
        "why small wins matter more than big goals",
        "how to build mental toughness",
        "the habit that changes everything",
        "how to stop making excuses",
        "why discipline beats willpower",
        "how to turn setbacks into comebacks",
        "the one habit successful people share",
        "how to build a growth mindset",
        "why consistency beats intensity",
    ],
    "finance": [
        "money habits of self-made millionaires",
        "personal finance mistakes to avoid",
        "how compound interest actually works",
        "side hustles that actually make money",
        "investing basics for beginners",
    ],
    "animals": [
        "weird animal facts",
        "deadliest animals in the world",
        "smartest animals on earth",
        "strange deep sea creatures",
        "animal survival adaptations",
    ],
    "personality": [
        "zodiac sign personality traits explained",
        "MBTI personality types explained",
        "signs you're secretly an introvert",
        "dark personality traits to watch for",
        "what your personality type says about you",
    ],
    "sports": [
        "greatest comebacks in sports history",
        "weird rules in professional sports",
        "biggest underdog stories in sports",
        "biggest sports scandals ever",
        "sports records that may never be broken",
    ],
    "documentary": [
        "true crime cases that shocked the world",
        "unsolved mysteries explained",
        "disasters caught on camera explained",
        "cults that shocked the world",
        "conspiracy theories investigated",
    ],
    "islamic": [
        "amazing facts about Islamic history",
        "stories of the Prophets explained",
        "beautiful mosques around the world",
        "inventions from the Islamic golden age",
        "Ramadan traditions around the world",
    ],
    "music": [
        "surprising facts about music theory",
        "history of iconic music genres",
        "musical instruments from around the world explained",
        "why songs get stuck in your head explained",
        "how music production has evolved over time",
    ],
    "horror": [
        "scariest urban legends explained",
        "unsolved horror mysteries",
        "creepiest abandoned places in the world",
        "true ghost stories people still can't explain",
        "horror myths debunked",
    ],
    "cartoons": [
        "hidden secrets in classic animation explained",
        "how cartoon animation actually works",
        "history of Saturday morning cartoons",
        "banned cartoon episodes explained",
        "evolution of animation technology",
    ],
}


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


def get_topic_by_category(category: str) -> str:
    """Returns a random topic from a named category. 'any' picks from all categories."""
    if category == "any" or category not in CATEGORY_TOPICS:
        pool = [t for topics in CATEGORY_TOPICS.values() for t in topics]
    else:
        pool = CATEGORY_TOPICS[category]
    return random.choice(pool)


def resolve_topic(mode: str = "trending", category: str = "any", custom_topic: str = "") -> str:
    """
    Single entry point main.py calls. mode is one of:
      "custom"   -> use custom_topic verbatim (falls back to trending if blank)
      "category" -> random topic from the given category
      "trending" -> Google Trends (default)
    """
    if mode == "custom" and custom_topic.strip():
        return custom_topic.strip()
    if mode == "category":
        return get_topic_by_category(category)
    return get_trending_topic()


if __name__ == "__main__":
    print(get_trending_topic())
