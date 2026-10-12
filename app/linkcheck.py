"""Pre-flight link health check: pings every selected story URL (dead links, 404s, sudden paywalls) before the Thursday send."""
import json, time
from concurrent.futures import ThreadPoolExecutor
import httpx
from app import config, db

UA = {"User-Agent": "Mozilla/5.0 (compatible; TheDispatchLinkCheck/1.0)"}

def check_url(url):
    t = time.time()
    try:
        r = httpx.get(url, timeout=12, follow_redirects=True, headers=UA)
        code = r.status_code
        state = "ok" if code < 400 else "paywall?" if code in (401, 402, 403, 451) else "dead"
        return {"status": code, "state": state, "ms": int((time.time() - t) * 1000), "final": str(r.url)[:200]}
    except httpx.HTTPError as e:
        return {"status": 0, "state": "unreachable", "ms": int((time.time() - t) * 1000), "final": "", "error": type(e).__name__}

def run(issue_id):
    with db.conn() as c:
        items = db.all(c, """SELECT i.id, i.position, a.title, a.url FROM issue_items i JOIN articles a ON a.id=i.article_id
                             WHERE i.issue_id=? AND i.kind='selected' ORDER BY i.position""", (issue_id,))
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda it: check_url(it["url"]), items))
    rows = [{"position": it["position"], "title": it["title"], "url": it["url"], **r} for it, r in zip(items, res)]
    out = {"issue_id": issue_id, "at": config.now_ist().isoformat(timespec="seconds"), "rows": rows,
           "problems": sum(1 for r in rows if r["state"] != "ok")}
    with db.conn() as c:
        db.kv_set(c, f"linkcheck:{issue_id}", json.dumps(out))
        db.log(c, "linkcheck", f"issue {issue_id}: {len(rows)} links, {out['problems']} problems")
    return out
