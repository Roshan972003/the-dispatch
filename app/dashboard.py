"""Open dashboard (no login, so it can be shown to anyone): one JSON state endpoint and rate-limited manual pipeline controls.
There is deliberately NO 'send newsletter' control: sending is only ever triggered by Shreya's confirmation in Telegram.
Subscriber addresses are masked, and subscribers added here go through the normal confirmation email."""
import json, time, re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from app import config, db, mailer
from app.dashboard_html import PAGE

router = APIRouter()
COOLDOWN_S = 90     # no password, so every action that changes something is rate-limited

def same_origin(request):
    """CSRF guard for POSTs: must come from this site's own pages."""
    origin, host = request.headers.get("origin", ""), request.headers.get("host", "")
    if origin and not origin.endswith("//" + host):
        raise HTTPException(403)

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return PAGE

# ---------------- state ----------------
def _next_runs(now):
    """Next firing of each cron in IST (mirrors vercel.json: ingest Mon-Wed 08:00, select Wed 14:00, reminder Wed 22:00, send Thu 08:00)."""
    sched = [("Ingest articles", [0, 1, 2], 8, 0), ("Gemini selection and Telegram draft", [2], 14, 0),
             ("Reminder if unconfirmed", [2], 22, 0), ("Send (only if confirmed)", [3], 8, 0)]
    out = []
    for label, days, h, m in sched:
        for add in range(0, 8):
            d = (now + timedelta(days=add)).replace(hour=h, minute=m, second=0, microsecond=0)
            if d.weekday() in days and d > now:
                out.append({"label": label, "at": d.isoformat(timespec="minutes")}); break
    return sorted(out, key=lambda x: x["at"])

def mask(email):
    u, _, d = (email or "").partition("@")
    return (u[:1] + "***@" + d) if d else email

def _q_issue(week):
    with db.conn() as c:
        issue = db.one(c, "SELECT * FROM issues WHERE week=?", (week,))
        items = db.all(c, """SELECT i.id, i.position, i.kind, i.topic, i.selection_filter, i.commentary, i.draft_original, i.flags, i.reviewed, i.edited, i.why,
                             a.title, a.url, a.source FROM issue_items i JOIN articles a ON a.id=i.article_id
                             WHERE i.issue_id=? AND i.kind IN ('selected','backup') ORDER BY i.kind DESC, i.position""", (issue["id"],)) if issue else []
    return issue, items

def _q_articles(week):
    with db.conn() as c:
        arts = db.all(c, """SELECT a.id, a.title, a.url, a.source, a.status, a.topic, a.published_at, d.title AS dup_title
                            FROM articles a LEFT JOIN articles d ON d.id=a.dup_of WHERE a.week=? ORDER BY a.published_at DESC LIMIT 600""", (week,))
        counts = {r["status"]: r["n"] for r in db.all(c, "SELECT status, COUNT(*) AS n FROM articles WHERE week=? GROUP BY status", (week,))}
        total = db.one(c, "SELECT COUNT(*) AS n FROM articles")["n"]
    return arts, counts, total

def _q_subs():
    with db.conn() as c:
        sub_counts = {r["status"]: r["n"] for r in db.all(c, "SELECT status, COUNT(*) AS n FROM subscribers GROUP BY status")}
        subs = db.all(c, "SELECT email, status, created_at, status_changed_at, note FROM subscribers ORDER BY id DESC LIMIT 60")
        sent = db.one(c, "SELECT COUNT(*) AS n FROM issues WHERE status='sent'")["n"]
    return sub_counts, subs, sent

def _q_misc():
    from app import styleguide
    with db.conn() as c:
        sends = db.all(c, """SELECT s.week, s.status, s.sent_at, SUM(CASE WHEN x.status='sent' THEN 1 ELSE 0 END) AS sent,
                             SUM(CASE WHEN x.status='failed' THEN 1 ELSE 0 END) AS failed, SUM(CASE WHEN x.status='queued' THEN 1 ELSE 0 END) AS queued
                             FROM issues s LEFT JOIN sends x ON x.issue_id=s.id GROUP BY s.id, s.week, s.status, s.sent_at ORDER BY s.week DESC LIMIT 8""")
        events = db.all(c, "SELECT ts, kind, detail FROM events ORDER BY id DESC LIMIT 40")
        last = db.kv_get(c, "last_ingest")
        sg = styleguide.active(c)
        edits = db.one(c, "SELECT COUNT(*) AS n, SUM(CASE WHEN promoted=0 THEN 1 ELSE 0 END) AS pending FROM edits")
    return sends, events, last, sg, edits

_cache = {"at": 0, "data": None}

def state(fresh=False):
    """Four independent query groups run in parallel (each on its own connection); the result is cached for 15 s."""
    if not fresh and _cache["data"] and time.time() - _cache["at"] < 15:
        return _cache["data"]
    now, week = config.now_ist(), config.week_start()
    with ThreadPoolExecutor(4) as ex:
        f = [ex.submit(_q_issue, week), ex.submit(_q_articles, week), ex.submit(_q_subs), ex.submit(_q_misc)]
        (issue, items), (arts, counts, total_articles), (sub_counts, subs, issues_sent), (sends, events, last, sg, edits) = [x.result() for x in f]
    for x in subs:                      # subscriber addresses are never shown in full
        x["email"] = mask(x["email"])
    for e in events:
        e["detail"] = re.sub(r"[\w.+-]+@[\w.-]+", lambda m: mask(m.group(0)), e["detail"] or "")
    sel = [i for i in items if i["kind"] == "selected"]
    status = issue["status"] if issue else "collecting"
    reviewed = sum(1 for i in sel if i["reviewed"])
    order = ["collecting", "drafted", "approved", "sending", "sent"]
    rank = order.index(status) if status in order else 0
    ing = json.loads(last) if last else None
    stages = [
        {"key": "ingest", "label": "Ingest", "state": "done" if counts else "todo",
         "detail": f"{sum(counts.values())} articles from {ing['sources_ok'] if ing else 0} sources"},
        {"key": "dedupe", "label": "Dedupe", "state": "done" if counts else "todo", "detail": f"{counts.get('dup', 0)} duplicates caught"},
        {"key": "select", "label": "Gemini picks", "state": "done" if sel else "todo", "detail": f"{len(sel)} stories, {len({i['topic'] for i in sel})} topics" if sel else "Wednesday 2:00 PM"},
        {"key": "draft", "label": "Draft to Telegram", "state": "done" if rank >= 1 else "todo", "detail": "sent for review" if rank >= 1 else "after selection"},
        {"key": "review", "label": "Shreya reviews", "state": "done" if rank >= 2 else ("active" if rank == 1 else "todo"), "detail": f"{reviewed}/{len(sel)} stories ticked" if sel else "waiting"},
        {"key": "confirm", "label": "Confirmed", "state": "done" if rank >= 2 else "todo", "detail": (issue or {}).get("approved_at") or "waiting for Shreya"},
        {"key": "send", "label": "Emailed", "state": "done" if status == "sent" else ("active" if status in ("approved", "sending") else "todo"),
         "detail": (issue or {}).get("sent_at") or ("queued for Thursday 8:00 AM" if status == "approved" else "Thursday")},
    ]
    first_open = next((i for i, st in enumerate(stages) if st["state"] != "done"), None)
    if first_open is not None and stages[first_open]["state"] == "todo":
        stages[first_open]["state"] = "active"
    by_src, topics = {}, {}
    for a in arts:
        by_src[a["source"]] = by_src.get(a["source"], 0) + 1
    for i in sel:
        topics[i["topic"]] = topics.get(i["topic"], 0) + 1
    data = {
        "now": now.isoformat(timespec="minutes"), "week": week, "mode": "postgres" if db.PG else "sqlite", "public_url": config.PUBLIC_URL,
        "issue": ({k: issue[k] for k in ("id", "week", "status", "approved_at", "sent_at", "drafted_at", "selection_notes")} if issue else None),
        "stages": stages, "next_runs": _next_runs(now),
        "kpis": {"articles_week": sum(counts.values()), "articles_total": total_articles, "candidates": counts.get("new", 0) + counts.get("selected", 0),
                 "duplicates": counts.get("dup", 0), "sources_ok": ing["sources_ok"] if ing else 0, "sources_total": ing["sources_total"] if ing else 0,
                 "subscribers": sub_counts.get("active", 0), "issues_sent": issues_sent, "selected": len(sel), "reviewed": reviewed,
                 "edited": sum(1 for i in sel if i["edited"]), "backups": sum(1 for i in items if i["kind"] == "backup")},
        "items": items, "articles": arts, "sources": sorted(by_src.items(), key=lambda x: -x[1]), "topics": sorted(topics.items(), key=lambda x: -x[1]),
        "ingest": ing, "sub_counts": sub_counts, "subscribers": subs, "sends": sends, "events": events,
        "style": {"version": sg["version"], "banned": len(sg["banned"]), "examples": len(sg["examples"]),
                  "edits_total": edits["n"] or 0, "edits_pending": edits["pending"] or 0},
        "keys": {k: bool(config.env(k)) for k in ["GEMINI_API_KEY", "DATABASE_URL", "TELEGRAM_BOT_TOKEN", "RESEND_API_KEY", "RESEND_WEBHOOK_SECRET", "NEWSAPI_KEY", "GNEWS_API_KEY", "NEWSDATA_API_KEY"]},
        "model": config.GEMINI_MODEL, "sender": config.RESEND_FROM,
    }
    _cache.update(at=time.time(), data=data)
    return data

@router.get("/api/admin/state")
def api_state(fresh: bool = False):
    return JSONResponse(state(fresh))

def _cooldown(step):
    """Returns seconds left if this step ran recently, else records the run and returns 0."""
    with db.conn() as c:
        last = float(db.kv_get(c, f"cooldown:{step}", "0"))
        left = int(COOLDOWN_S - (time.time() - last))
        if left > 0:
            return left
        db.kv_set(c, f"cooldown:{step}", str(time.time()))
    return 0

@router.post("/api/admin/run/{step}")
def run_step(step: str, request: Request):
    same_origin(request)
    from app import ingest, select_stories, telegram, styleguide
    if step not in ("ingest", "select", "draft", "promote"):
        raise HTTPException(404)
    left = _cooldown(step)
    if left:
        return {"ok": False, "message": f"That step just ran. Try again in {left}s."}
    _cache["data"] = None
    if step == "ingest":
        r = ingest.run_ingest(); return {"ok": True, "message": f"Ingested: {r['new']} new, {r['dup']} duplicates, {r['sources_ok']} sources responded."}
    if step == "select":
        r = select_stories.run_selection(force=True)
        if r.get("issue_id"):
            telegram.send_draft(r["issue_id"])
            return {"ok": True, "message": f"Gemini picked {r['picks']} stories across {len(r['topics'])} topics; draft sent to Telegram."}
        return {"ok": False, "message": str(r)}
    if step == "draft":
        r = telegram.send_draft(); return {"ok": "error" not in r, "message": "Draft re-sent to Telegram." if "error" not in r else r["error"]}
    with db.conn() as c:
        v = styleguide.promote_edits(c)
    return {"ok": True, "message": f"Style guide updated to v{v}." if v else "No new edits to learn from."}

@router.post("/api/admin/subscribers")
async def add_subscribers(request: Request):
    """Open endpoint, so it behaves like the public sign-up: addresses start 'pending' and get a confirmation email."""
    same_origin(request)
    from app import mailer
    left = _cooldown("subscribe")
    if left:
        return {"ok": False, "message": f"Please wait {left}s before adding more."}
    emails = [e for e in re.split(r"[\s,;]+", (await request.json()).get("emails", "")) if e][:10]
    res = [mailer.subscribe(e) for e in emails]
    _cache["data"] = None
    return {"ok": True, "added": sum(1 for r in res if r["ok"]), "invalid": sum(1 for r in res if not r["ok"])}
