"""Reader-accessibility diagnostic: tags each candidate link free / soft paywall / hard paywall / dead / unverified,
and for walled links looks for free coverage of the same story from another source this week. Heuristic, and labelled as such."""
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
import httpx
from app.ingest import similar, fingerprint

UA = {"User-Agent": "Mozilla/5.0 (compatible; TheDispatchAccessCheck/1.0)"}
HARD_HOSTS = ("the-ken.com",)
SOFT_HOSTS = ("business-standard.com", "thehindubusinessline.com", "thehindu.com")
SOFT_PHRASES = ("subscribe to continue reading", "sign in to continue reading", "to continue reading", "free article limit", "subscribe to read", "premium content", "already a subscriber")
LD_LOCKED = re.compile(r'"isaccessibleforfree"\s*:\s*(false|"false")', re.I)

def _host(url):
    return urlsplit(url).netloc.lower().removeprefix("www.") if hasattr(str, "removeprefix") else re.sub(r"^www\.", "", urlsplit(url).netloc.lower())

def tag_url(url):
    """-> 'free' | 'soft' | 'hard' | 'dead' | 'unknown'"""
    host, path = _host(url), urlsplit(url).path.lower()
    if "news.google.com" in host:
        return "unknown"            # a redirect page: the real publisher is not visible without a browser
    if any(host.endswith(h) for h in HARD_HOSTS) or "/prime/" in path:
        return "hard"
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True, headers=UA)
    except httpx.HTTPError:
        return "unknown"
    if r.status_code in (404, 410):
        return "dead"
    if r.status_code == 402:
        return "hard"
    if r.status_code in (401, 403):
        return "soft"
    html = r.text[:250000].lower()
    if LD_LOCKED.search(html):
        return "hard"
    if any(p in html for p in SOFT_PHRASES) or any(host.endswith(h) for h in SOFT_HOSTS):
        return "soft"
    return "free"

def find_free_alt(story, pool):
    """Same story, different publisher, directly linkable, and not itself on a walled host."""
    fp = fingerprint(story["title"])
    best = None
    for a in pool:
        if a["source"] == story["source"] or "news.google.com" in a["url"] or a["url"] == story["url"]:
            continue
        host = _host(a["url"])
        if any(host.endswith(h) for h in HARD_HOSTS + SOFT_HOSTS) or "/prime/" in a["url"]:
            continue
        if similar(fp, a["fingerprint"] or "", 0.4):
            best = a
            break
    return best

def diagnose_all(stories, pool):
    """{article_id: {access, alt_url, alt_source}} for stories carrying id/title/url/source."""
    def one(s):
        t = tag_url(s["url"])
        out = {"access": t, "alt_url": None, "alt_source": None}
        if t in ("soft", "hard", "dead"):
            alt = find_free_alt(s, pool)
            if alt:
                out["alt_url"], out["alt_source"] = alt["url"], alt["source"]
        return s["id"], out
    with ThreadPoolExecutor(8) as ex:
        return dict(ex.map(one, stories))
