import re
MAX_AGE_DAYS = 8
def clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()[:600]

# ---- scope: The Dispatch covers the INDIAN STARTUP ECOSYSTEM only ----
GLOBAL_SOURCES = ("techcrunch", "rest of world", "hacker news", "gdelt")                      # worldwide feeds: kept only when the story itself is about India
NOT_PUBLISHERS = ("instagram", "facebook", "youtube", "twitter", "x.com", "reddit", "linkedin", "tiktok", "whatsapp", "telegram", "quora", "pinterest")   # social posts that leak through search aggregators
INDIA_WORDS = ("india", "indian", "bengaluru", "bangalore", "mumbai", "delhi", "hyderabad", "chennai", "pune", "gurugram", "gurgaon", "noida", "kolkata", "ahmedabad", "rbi", "sebi", "npci", "upi", "rs ", "rs.", "\u20b9", "crore", "lakh", "dpiit", "meity")

def in_scope(a):
    """Cheap, deterministic scope check applied at ingestion and again at selection, before any AI sees the article."""
    src = (a.get("source") or "").lower()
    if src == "added by shreya":
        return True                                                  # her hand-picks are her call
    if any(x in src for x in NOT_PUBLISHERS):
        return False                                                 # a social post, not reporting
    if any(x in src for x in GLOBAL_SOURCES):
        text = f'{a.get("title") or ""} {a.get("snippet") or ""}'.lower()
        return any(w in text for w in INDIA_WORDS)                   # a global outlet only counts when the story is about India
    return True
