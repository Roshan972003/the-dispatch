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
from app.ingest_util import in_scope

DEFAULT_FEEDS = [
    ("Inc42", "https://inc42.com/feed/"),
    ("YourStory", "https://yourstory.com/feed"),
    ("Entrackr", "https://entrackr.com/rss"),
    ("Economic Times Startups", "https://economictimes.indiatimes.com/small-biz/startups/rssfeeds/11993050.cms"),
    ("Economic Times Tech", "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms"),
    ("Medianama", "https://www.medianama.com/feed/"),
    ("The Hindu BusinessLine", "https://www.thehindubusinessline.com/companies/feeder/default.rss"),
    ("Livemint Companies", "https://www.livemint.com/rss/companies"),
    ("Livemint Technology", "https://www.livemint.com/rss/technology"),
    ("The Ken", "https://the-ken.com/feed/"),
    ("The Arc", "https://thearcweb.com/rss"),
    ("Indian Express Tech", "https://indianexpress.com/section/technology/feed/"),
]
BROKEN_FEEDS = ["https://techcrunch.com/feed/", "https://restofworld.org/feed/",     # worldwide feeds switched off: the newsletter is India-only
                "https://entrackr.com/feed", "https://www.moneycontrol.com/rss/startup.xml", "https://www.business-standard.com/rss/companies-101.rss",
                "https://www.vccircle.com/feed", "https://analyticsindiamag.com/feed/", "https://tracxn.com/d/blog/rss.xml",
                "https://www.thehindubusinessline.com/companies/feeder/default.rss.OLD"]
STOP = set("a an the of in on at to for and or with as by from is are was were be its it this that new says say after over into amid".split())
TRACKING = ("utm_", "fbclid", "gclid", "ref", "source", "cmpid", "ocid")
from app.ingest_util import clean as _clean, MAX_AGE_DAYS

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

def seed_feeds(c):
    for url in BROKEN_FEEDS:
        db.run(c, "UPDATE feeds SET active=0 WHERE url=?", (url,))
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
    """Insert new items; returns counts. Near-duplicates are marked, not dropped, so the audit trail stays.
    All lookups are done in memory and all writes are batched: one round trip each, not one per article."""
    cutoff = datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)
    past = recent_issue_fingerprints(c, week)
    this_week = [(a["url_hash"], a["fingerprint"]) for a in db.all(c, "SELECT url_hash, fingerprint FROM articles WHERE week=? AND status!='dup'", (week,))]
    known = {r["url_hash"] for r in db.all(c, "SELECT url_hash FROM articles")}
    stats = {"seen": 0, "new": 0, "dup": 0, "old": 0, "exists": 0}
    rows, dup_links, now = [], [], config.now_ist().isoformat(timespec="seconds")
    for it in items:
        stats["seen"] += 1
        if it["published"] and it["published"] < cutoff:
            stats["old"] += 1; continue
        h = url_hash(it["url"])
        if h in known:
            stats["exists"] += 1; continue
        known.add(h)
        fp = fingerprint(it["title"])
        status, dup_hash = "new", None
        if any(similar(fp, p) for p in past):
            status = "dup"
        else:
            m = next((x for x in this_week if similar(fp, x[1])), None)
            if m:
                status, dup_hash = "dup", m[0]
        if status == "new":
            this_week.append((h, fp)); stats["new"] += 1
        else:
            stats["dup"] += 1
            if dup_hash:
                dup_links.append((dup_hash, h))
        pub = it["published"].isoformat(timespec="seconds") if it["published"] else None
        rows.append((h, canon(it["url"]), it["title"][:500], it["source"], it["snippet"], pub, now, week, fp, status))
    db.many(c, """INSERT INTO articles (url_hash, url, title, source, snippet, published_at, fetched_at, week, fingerprint, status)
                  VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(url_hash) DO NOTHING""", rows)
    db.many(c, "UPDATE articles SET dup_of=(SELECT id FROM (SELECT id FROM articles WHERE url_hash=?) t) WHERE url_hash=?", dup_links)
    return stats

def run_ingest():
    """Fetch every source in parallel (so it fits a serverless time limit), then dedupe and store."""
    from concurrent.futures import ThreadPoolExecutor
    from app import sources
    week = config.week_start()
    with db.conn() as c:
        seed_feeds(c)
        feeds = db.all(c, "SELECT name, url FROM feeds WHERE active=1")
    def job(j):
        label, fn, args = j
        try:
            return label, fn(*args), None
        except Exception as e:
            return label, [], (str(e)[:110] if isinstance(e, RuntimeError) else f"{type(e).__name__}: {str(e)[:60]}")
    items, report = [], {}
    with ThreadPoolExecutor(10) as ex:
        for label, got, err in ex.map(job, sources.plan(feeds)):
            items += got
            report[label] = err or len(got)
    result = {"week": week, "sources_total": len(report),
              "sources_failed": {k: v for k, v in report.items() if not isinstance(v, int)},
              "sources_empty": [k for k, v in report.items() if v == 0], "per_source": {k: v for k, v in report.items() if isinstance(v, int) and v}}
    result["sources_ok"] = len(result["per_source"])
    with db.conn() as c:
        n_all = len(items)
        items = [a for a in items if in_scope(a)]          # India startup ecosystem only: global feeds and social posts never enter the pool
        stats = store(c, items, week)
        stats["out_of_scope"] = n_all - len(items)
        result.update(stats)
        import json
        try:
            from app import select_stories
            result["scope"] = select_stories.mark_scope(c, week)
        except Exception as e:
            result["scope"] = {"error": str(e)[:80]}
        db.kv_set(c, "last_ingest", json.dumps({**result, "at": config.now_ist().isoformat(timespec="seconds")}))
        db.log(c, "ingest", f"{stats}")
    return result
