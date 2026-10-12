"""News sources. Each fetcher returns [{url, title, source, snippet, published(datetime|None)}].
Keyless: RSS feeds (feeds table), Google News search, Hacker News, GDELT. Keyed (activate when the env key is set): NewsAPI, GNews, NewsData.io."""
import calendar
from datetime import datetime, timedelta
import httpx, feedparser
from app import config
from app.ingest_util import clean, MAX_AGE_DAYS

UA = {"User-Agent": "Mozilla/5.0 (compatible; TheDispatchBot/1.0)"}

GOOGLE_QUERIES = [
    "India startup funding", "Indian startup layoffs", "Indian startup shutdown", "India fintech RBI regulation",
    "India quick commerce", "India D2C brand", "India SaaS startup", "India AI startup", "SEBI startup IPO India",
    "India EV startup", "India startup acquisition", "India startup policy government", "India startup unit economics profitability",
]
NEWS_QUERIES = ["India startup funding", "Indian startup layoffs OR shutdown", "SEBI startup IPO India",
                "India fintech regulation RBI", "India D2C quick commerce", "India AI startup", "India SaaS startup"]

def _ts(t):
    return datetime.utcfromtimestamp(calendar.timegm(t)) if t else None

def _iso(s):
    try:
        return datetime.strptime(s[:19].replace(" ", "T"), "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None

def rss(name, url):
    r = httpx.get(url, timeout=20, follow_redirects=True, headers=UA)
    r.raise_for_status()
    return [{"url": e["link"], "title": clean(e["title"]), "source": name, "snippet": clean(e.get("summary", "")),
             "published": _ts(e.get("published_parsed") or e.get("updated_parsed"))}
            for e in feedparser.parse(r.content).entries if e.get("link") and e.get("title")]

def google_news(query):
    r = httpx.get("https://news.google.com/rss/search", params={"q": f"{query} when:7d", "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
                  timeout=20, follow_redirects=True, headers=UA)
    r.raise_for_status()
    out = []
    for e in feedparser.parse(r.content).entries[:30]:
        pub = (e.get("source") or {}).get("title", "Google News")
        title = clean(e["title"])
        if title.endswith(" - " + pub):
            title = title[: -len(pub) - 3]
        out.append({"url": e["link"], "title": title, "source": pub, "snippet": "", "published": _ts(e.get("published_parsed"))})
    return out

def hacker_news(query="India startup"):
    r = httpx.get("https://hn.algolia.com/api/v1/search_by_date", params={"query": query, "tags": "story", "hitsPerPage": 40,
                  "numericFilters": f"points>10,created_at_i>{int((datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)).timestamp())}"}, timeout=20)
    r.raise_for_status()
    return [{"url": h["url"], "title": h["title"], "source": "Hacker News", "snippet": "",
             "published": datetime.utcfromtimestamp(h["created_at_i"])} for h in r.json()["hits"] if h.get("url")]

def gdelt(query='("Indian startup" OR "India startup")'):
    r = httpx.get("https://api.gdeltproject.org/api/v2/doc/doc", params={"query": f"{query} sourcelang:english", "mode": "artlist",
                  "maxrecords": 50, "format": "json", "timespan": "7d"}, timeout=25, headers=UA)
    return [{"url": a["url"], "title": clean(a["title"]), "source": a.get("domain", "GDELT"), "snippet": "",
             "published": _iso(a.get("seendate", "").replace("T", "T")[:4] + "-" + a.get("seendate", "")[4:6] + "-" + a.get("seendate", "")[6:8] + "T" +
                               a.get("seendate", "")[9:11] + ":" + a.get("seendate", "")[11:13] + ":" + a.get("seendate", "")[13:15]) if a.get("seendate") else None}
            for a in r.json().get("articles", [])]

def newsapi(query):
    if not config.NEWSAPI_KEY:
        return []
    r = httpx.get("https://newsapi.org/v2/everything", timeout=20, params={
        "q": query, "from": (datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)).strftime("%Y-%m-%d"), "language": "en",
        "sortBy": "publishedAt", "pageSize": 40, "apiKey": config.NEWSAPI_KEY})
    r.raise_for_status()
    return [{"url": a["url"], "title": a["title"], "source": (a.get("source") or {}).get("name", "NewsAPI"),
             "snippet": clean(a.get("description") or ""), "published": _iso(a.get("publishedAt") or "")}
            for a in r.json().get("articles", []) if a.get("url") and a.get("title")]

def gnews(query):
    if not config.GNEWS_API_KEY:
        return []
    r = httpx.get("https://gnews.io/api/v4/search", timeout=20, params={"q": query, "lang": "en", "country": "in", "max": 25,
                  "from": (datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ"), "apikey": config.GNEWS_API_KEY})
    r.raise_for_status()
    return [{"url": a["url"], "title": a["title"], "source": (a.get("source") or {}).get("name", "GNews"),
             "snippet": clean(a.get("description") or ""), "published": _iso(a.get("publishedAt") or "")} for a in r.json().get("articles", [])]

def newsdata(query):
    if not config.NEWSDATA_API_KEY:
        return []
    r = httpx.get("https://newsdata.io/api/1/news", timeout=20, params={"apikey": config.NEWSDATA_API_KEY, "q": query, "country": "in",
                  "language": "en", "category": "business,technology"})
    r.raise_for_status()
    return [{"url": a["link"], "title": a["title"], "source": a.get("source_name") or a.get("source_id") or "NewsData",
             "snippet": clean(a.get("description") or ""), "published": _iso(a.get("pubDate") or "")} for a in r.json().get("results", []) if a.get("link")]

def plan(feeds):
    """[(label, fn, args)] covering every configured source."""
    jobs = [(f"rss:{f['name']}", rss, (f["name"], f["url"])) for f in feeds]
    jobs += [(f"google:{q}", google_news, (q,)) for q in GOOGLE_QUERIES]
    jobs += [("hackernews", hacker_news, ()), ("gdelt", gdelt, ())]
    for q in NEWS_QUERIES:
        jobs += [(f"newsapi:{q}", newsapi, (q,))]
    for q in NEWS_QUERIES[:4]:              # keep keyed free tiers (GNews 100/day, NewsData 200/day) well under their limits
        jobs += [(f"gnews:{q}", gnews, (q,)), (f"newsdata:{q}", newsdata, (q,))]
    return jobs
