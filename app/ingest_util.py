import re
MAX_AGE_DAYS = 8
def clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()[:600]
