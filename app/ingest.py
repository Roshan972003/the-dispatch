"""Mon-Wed ingestion: RSS feeds + NewsAPI queries -> articles table, deduplicated.

Dedup layers:
  1. exact: canonical URL hash is unique, so a link is stored once, ever.
  2. this week: near-identical headlines (token Jaccard) are marked dup of the first one seen.
  3. past issues: headlines too close to a story in any of the last four issues are marked dup.
"""
import re, hashlib, calendar
from datetime import datetime, timedelta
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import httpx, feedparser
from app import config, db

DEFAULT_FEEDS = [
    ("Entrackr", "https://entrackr.com/feed"),
    ("Inc42", "https://inc42.com/feed/"),
    ("YourStory", "https://yourstory.com/feed"),
    ("Economic Times Startups", "https://economictimes.indiatimes.com/small-biz/startups/rssfeeds/11993050.cms"),
    ("Moneycontrol Startups", "https://www.moneycontrol.com/rss/startup.xml"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("Medianama", "https://www.medianama.com/feed/"),
    ("The Hindu BusinessLine Startups", "https://www.thehindubusinessline.com/companies/feeder/default.rss"),
    ("Livemint Companies", "https://www.livemint.com/rss/companies"),
    ("Business Standard Startups", "https://www.business-standard.com/rss/companies-101.rss"),
    ("VCCircle", "https://www.vccircle.com/feed"),
    ("Analytics India Magazine", "https://analyticsindiamag.com/feed/"),
    ("The Ken", "https://the-ken.com/feed/"),
    ("Tracxn Blog", "https://tracxn.com/d/blog/rss.xml"),
]
NEWS_QUERIES = [
    "India startup funding", "Indian startup layoffs OR shutdown", "SEBI startup IPO India",
    "India fintech regulation RBI", "India D2C quick commerce", "India AI startup", "India SaaS startup",
]
STOP = set("a an the of in on at to for and or with as by from is are was were be its it this that new says say after over into amid".split())
TRACKING = ("utm_", "fbclid", "gclid", "ref", "source", "cmpid", "ocid")
MAX_AGE_DAYS = 8

def canon(url):
    s = urlsplit(url.strip())
    q = [(k, v) for k, v in parse_qsl(s.query) if not k.lower().startswith(TRACKING)]
    host = s.netloc.lower().removeprefix("www.") if hasattr(str, "removeprefix") else re.sub(r"^www\.", "", s.netloc.lower())
    return urlunsplit((s.scheme or "https", host, s.path.rstrip("/"), urlencode(q), ""))

def url_hash(url):
    return hashlib.sha1(canon(url).encode()).hexdigest()

def tokens(title):
    t = re.sub(r"[^a-z0-9 ]", " ", title.lower())
    return {w for w in t.split() if w not in STOP and len(w) > 1}

def fingerprint(title):
    return " ".join(sorted(tokens(title)))

def similar(fp_a, fp_b, threshold=0.6):
    a, b = set(fp_a.split()), set(fp_b.split())
    if not a or not b:
        return False
    return len(a & b) / len(a | b) >= threshold

def _clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()[:600]

def _published(entry):
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    return datetime.utcfromtimestamp(calendar.timegm(t)) if t else None

def fetch_rss(name, url):
    r = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": "TheDispatchBot/1.0"})
    r.raise_for_status()
    out = []
    for e in feedparser.parse(r.content).entries:
        if e.get("link") and e.get("title"):
            out.append({"url": e["link"], "title": _clean(e["title"]), "source": name,
                        "snippet": _clean(e.get("summary", "")), "published": _published(e)})
    return out

def fetch_newsapi(query):
    if not config.NEWSAPI_KEY:
        return []
    frm = (datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)).strftime("%Y-%m-%d")
    r = httpx.get("https://newsapi.org/v2/everything", timeout=20, params={
        "q": query, "from": frm, "language": "en", "sortBy": "publishedAt", "pageSize": 40, "apiKey": config.NEWSAPI_KEY})
    r.raise_for_status()
    out = []
    for a in r.json().get("articles", []):
        if a.get("url") and a.get("title"):
            pub = None
            try:
                pub = datetime.strptime(a["publishedAt"][:19], "%Y-%m-%dT%H:%M:%S")
            except Exception:
                pass
            out.append({"url": a["url"], "title": a["title"], "source": (a.get("source") or {}).get("name", "NewsAPI"),
                        "snippet": _clean(a.get("description") or ""), "published": pub})
    return out

def seed_feeds(c):
    for name, url in DEFAULT_FEEDS:
        if not db.one(c, "SELECT id FROM feeds WHERE url=?", (url,)):
            db.run(c, "INSERT INTO feeds (name, url) VALUES (?,?)", (name, url))

def recent_issue_fingerprints(c, week):
    """Fingerprints of stories in the last four issues before this week's, for cross-week dedup."""
    rows = db.all(c, """SELECT a.fingerprint FROM issue_items i JOIN issues s ON s.id=i.issue_id
                        JOIN articles a ON a.id=i.article_id
                        WHERE i.kind='selected' AND s.week < ? AND s.week IN
                        (SELECT week FROM issues WHERE week < ? ORDER BY week DESC LIMIT ?)""",
                  (week, week, config.LOOKBACK_ISSUES))
    return [r["fingerprint"] for r in rows]

def store(c, items, week):
    """Insert new items; returns counts. Marks near-duplicates instead of dropping them, so the audit trail stays."""
    cutoff = datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)
    past = recent_issue_fingerprints(c, week)
    this_week = db.all(c, "SELECT id, fingerprint FROM articles WHERE week=? AND status!='dup'", (week,))
    stats = {"seen": 0, "new": 0, "dup": 0, "old": 0, "exists": 0}
    for it in items:
        stats["seen"] += 1
        if it["published"] and it["published"] < cutoff:
            stats["old"] += 1; continue
        h = url_hash(it["url"])
        if db.one(c, "SELECT id FROM articles WHERE url_hash=?", (h,)):
            stats["exists"] += 1; continue
        fp = fingerprint(it["title"])
        status, dup_of = "new", None
        if any(similar(fp, p) for p in past):
            status = "dup"
        else:
            m = next((a for a in this_week if similar(fp, a["fingerprint"])), None)
            if m:
                status, dup_of = "dup", m["id"]
        pub = it["published"].isoformat(timespec="seconds") if it["published"] else None
        aid = db.insert(c, """INSERT INTO articles (url_hash, url, title, source, snippet, published_at, fetched_at, week, fingerprint, status, dup_of)
                              VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (h, canon(it["url"]), it["title"], it["source"], it["snippet"], pub,
                         config.now_ist().isoformat(timespec="seconds"), week, fp, status, dup_of))
        if status == "new":
            this_week.append({"id": aid, "fingerprint": fp}); stats["new"] += 1
        else:
            stats["dup"] += 1
    return stats

def run_ingest():
    week = config.week_start()
    items, report = [], {}
    with db.conn() as c:
        seed_feeds(c)
        feeds = db.all(c, "SELECT name, url FROM feeds WHERE active=1")
    for f in feeds:
        try:
            got = fetch_rss(f["name"], f["url"]); items += got; report[f["name"]] = len(got)
        except Exception as e:
            report[f["name"]] = f"error: {str(e)[:80]}"
    for q in NEWS_QUERIES:
        try:
            got = fetch_newsapi(q); items += got; report[f"newsapi:{q}"] = len(got)
        except Exception as e:
            report[f"newsapi:{q}"] = f"error: {str(e)[:80]}"
    with db.conn() as c:
        stats = store(c, items, week)
        db.log(c, "ingest", f"{stats} sources={report}")
    return {"week": week, **stats, "sources": report}
