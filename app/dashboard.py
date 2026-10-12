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
    return HTMLResponse(PAGE, headers={"Cache-Control": "no-store"})

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

def fingerprint_of(t):
    from app.ingest import fingerprint
    return fingerprint(t)

def select_stories_topics():
    from app.select_stories import TOPICS
    return TOPICS

def mask(email):
    u, _, d = (email or "").partition("@")
    return (u[:1] + "***@" + d) if d else email

def _q_issue(week):
    with db.conn() as c:
        issue = db.one(c, "SELECT * FROM issues WHERE week=?", (week,))
        items = db.all(c, """SELECT i.id, i.position, i.kind, i.topic, i.selection_filter, i.commentary, i.draft_original, i.flags, i.reviewed, i.edited, i.why,
                             i.counter, i.access, i.alt_url, i.alt_source, i.entities, i.source_text, i.quotes, a.title, a.url, a.source, a.snippet, a.signal, a.signal_filter FROM issue_items i JOIN articles a ON a.id=i.article_id
                             WHERE i.issue_id=? AND i.kind IN ('selected','backup') ORDER BY i.kind DESC, i.position""", (issue["id"],)) if issue else []
        lc = db.kv_get(c, f"linkcheck:{issue['id']}") if issue else None
    return issue, items, (json.loads(lc) if lc else None)

def _q_articles(week):
    with db.conn() as c:
        arts = db.all(c, """SELECT a.id, a.title, a.url, a.source, a.status, a.topic, a.published_at, a.signal, a.signal_filter, a.fingerprint, d.title AS dup_title
                            FROM articles a LEFT JOIN articles d ON d.id=a.dup_of WHERE a.week=? ORDER BY a.published_at DESC LIMIT 1500""", (week,))
        counts = {r["status"]: r["n"] for r in db.all(c, "SELECT status, COUNT(*) AS n FROM articles WHERE week=? GROUP BY status", (week,))}
        total = db.one(c, "SELECT COUNT(*) AS n FROM articles")["n"]
        dd = db.one(c, "SELECT SUM(CASE WHEN dup_of IS NOT NULL THEN 1 ELSE 0 END) AS in_week, SUM(CASE WHEN dup_of IS NULL THEN 1 ELSE 0 END) AS past FROM articles WHERE week=? AND status='dup'", (week,))
        counts["_dup_in_week"], counts["_dup_past"] = dd["in_week"] or 0, dd["past"] or 0
        sc = db.one(c, "SELECT SUM(CASE WHEN signal IS NOT NULL THEN 1 ELSE 0 END) AS scored, SUM(CASE WHEN signal_filter IS NOT NULL THEN 1 ELSE 0 END) AS short, SUM(CASE WHEN signal_filter IS NOT NULL AND signal>=60 THEN 1 ELSE 0 END) AS strong FROM articles WHERE week=? AND status<>'dup'", (week,))
        counts["_scored"], counts["_strong"], counts["_short"] = sc["scored"] or 0, sc["strong"] or 0, sc["short"] or 0
    return arts, counts, total

def _q_subs():
    with db.conn() as c:
        sub_counts = {r["status"]: r["n"] for r in db.all(c, "SELECT status, COUNT(*) AS n FROM subscribers GROUP BY status")}
        subs = db.all(c, "SELECT email, status, created_at, status_changed_at, note FROM subscribers ORDER BY id DESC LIMIT 60")
        sent = db.one(c, "SELECT COUNT(*) AS n FROM issues WHERE status='sent'")["n"]
        joined = db.all(c, "SELECT substr(created_at,1,10) AS d, COUNT(*) AS n FROM subscribers GROUP BY substr(created_at,1,10) ORDER BY d DESC LIMIT 14")
        left = db.all(c, "SELECT substr(status_changed_at,1,10) AS d, status, COUNT(*) AS n FROM subscribers WHERE status IN ('unsubscribed','bounced','complained') GROUP BY substr(status_changed_at,1,10), status ORDER BY d DESC LIMIT 30")
        reasons = db.all(c, "SELECT COALESCE(unsub_reason, 'No reason given') AS r, COUNT(*) AS n FROM subscribers WHERE status='unsubscribed' GROUP BY COALESCE(unsub_reason, 'No reason given')")
    return sub_counts, subs, sent, {"joined": joined, "left": left, "reasons": reasons}

def _q_misc(week):
    from app import styleguide
    with db.conn() as c:
        sends = db.all(c, """SELECT s.week, s.status, s.sent_at, SUM(CASE WHEN x.status='sent' THEN 1 ELSE 0 END) AS sent,
                             SUM(CASE WHEN x.status='failed' THEN 1 ELSE 0 END) AS failed, SUM(CASE WHEN x.status='queued' THEN 1 ELSE 0 END) AS queued
                             FROM issues s LEFT JOIN sends x ON x.issue_id=s.id GROUP BY s.id, s.week, s.status, s.sent_at ORDER BY s.week DESC LIMIT 8""")
        events = db.all(c, "SELECT ts, kind, detail FROM events ORDER BY id DESC LIMIT 40")
        last = db.kv_get(c, "last_ingest")
        sg = styleguide.active(c)
        edits = db.one(c, "SELECT COUNT(*) AS n, SUM(CASE WHEN promoted=0 THEN 1 ELSE 0 END) AS pending FROM edits")
        from app.select_stories import get_tuner
        tr = db.kv_get(c, f"trends:{week}")
        all_weeks = [r["week"] for r in db.all(c, "SELECT week FROM issues ORDER BY week")]
        rd = db.kv_get(c, f"repeat_dropped:{week}")
        extras = {"tuner": get_tuner(c), "trends": json.loads(tr) if tr else None, "editions": {w: n + 1 for n, w in enumerate(all_weeks)}, "snooze": db.kv_get(c, "snooze_until"), "repeat_dropped": json.loads(rd) if rd else []}
    return sends, events, last, sg, edits, extras

def _q_memory(week):
    """Stories picked in this and the previous 4 issues, for the archive matrix and entity-overlap flags."""
    with db.conn() as c:
        return db.all(c, """SELECT s.week, s.status, i.topic, i.entities, a.title, a.url FROM issue_items i JOIN issues s ON s.id=i.issue_id JOIN articles a ON a.id=i.article_id
                           WHERE i.kind='selected' AND s.week IN (SELECT week FROM issues WHERE week <= ? ORDER BY week DESC LIMIT 5) ORDER BY s.week DESC, i.position""", (week,))

def _q_engagement():
    from app.ingest import canon
    with db.conn() as c:
        kinds = {r["kind"]: {"events": r["n"], "unique": r["u"]} for r in db.all(c, "SELECT kind, COUNT(*) AS n, COUNT(DISTINCT recipient_hash) AS u FROM email_events GROUP BY kind")}
        clicks = db.all(c, "SELECT link, COUNT(*) AS n FROM email_events WHERE kind='email.clicked' AND link IS NOT NULL GROUP BY link")
        topic_of = {r["url"]: r["topic"] for r in db.all(c, "SELECT a.url, i.topic FROM issue_items i JOIN articles a ON a.id=i.article_id WHERE i.kind='selected'")}
        sent = db.one(c, "SELECT COUNT(*) AS n FROM sends WHERE status='sent'")["n"]
    by_topic = {}
    for x in clicks:
        t = topic_of.get(canon(x["link"]))
        if t:
            by_topic[t] = by_topic.get(t, 0) + x["n"]
    delivered = kinds.get("email.delivered", {}).get("unique", 0)
    opened = kinds.get("email.opened", {}).get("unique", 0)
    return {"sent": sent, "delivered": delivered, "opened": opened, "clicked": kinds.get("email.clicked", {}).get("unique", 0),
            "open_rate": round(100 * opened / delivered, 1) if delivered else None, "clicks_by_topic": sorted(by_topic.items(), key=lambda x: -x[1]), "tracked": bool(kinds)}

def build_graph(mem, week, editions=None, now=None):
    """Entity knowledge graph over the last 5 issues. Nodes are entities; an edge means two entities were covered in the same story."""
    nodes, edges = {}, {}
    for m in mem:
        try:
            ents = json.loads(m.get("entities") or "[]")
        except Exception:
            ents = []
        names = []
        for e in ents:
            n = nodes.setdefault(e["name"], {"name": e["name"], "type": e["type"], "weeks": set(), "stories": [], "count": 0})
            n["weeks"].add(m["week"]); n["count"] += 1
            thursday = datetime.strptime(m["week"], "%Y-%m-%d") + timedelta(days=3)
            n["stories"].append({"week": m["week"], "title": m["title"], "topic": m["topic"], "url": m["url"], "status": m.get("status"), "edition": (editions or {}).get(m["week"]),
                                 "days_ago": max(0, (now - thursday).days) if now else None})
            names.append(e["name"])
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                k = tuple(sorted((a, b)))
                edges[k] = edges.get(k, 0) + 1
    top = sorted(nodes.values(), key=lambda n: (-len(n["weeks"]), -n["count"], n["name"]))[:70]
    keep = {n["name"] for n in top}
    for n in top:
        n["weeks"] = sorted(n["weeks"]); n["repeat"] = len(n["weeks"]) > 1
    return {"nodes": top, "edges": [[a, b, w] for (a, b), w in edges.items() if a in keep and b in keep],
            "repeats": [n["name"] for n in top if n["repeat"]]}

def reminder_info(week, issue, snooze):
    deadline = datetime.strptime(week, "%Y-%m-%d") + timedelta(days=2, hours=22)
    return {"deadline": deadline.isoformat(timespec="minutes"), "confirmed": bool(issue and issue.get("approved_at")),
            "reminder_sent": bool(issue and issue.get("reminder_sent")), "snooze_until": snooze, "has_draft": bool(issue and issue["status"] == "drafted")}

BUZZ_SWAPS = {"game-changer": "a real shift", "revolutionary": "a sharp break from the usual", "landscape": "market", "deep dive": "closer look",
              "paradigm shift": "change in the rules", "soaring": "climbing", "testament to": "proof of", "unprecedented": "unusual", "disrupt": "upend",
              "cutting-edge": "latest", "in today's fast-paced world": "right now", "unlock": "open up", "seamless": "smooth", "exciting": "notable",
              "poised to": "set to", "a win for": "good news for"}

STOPCAP = set("The A An In On At To For And Or With As By From Is Are Was Were Its It This That New Says After Over Into Amid India Indian Indias What Why How Who When Rs Cr FY Q1 Q2 Q3 Q4 IPO CEO CFO AI Govt Report Reports".split())
def ents_of(m):
    """Gemini-extracted entities for a story (names only); falls back to the capital-letter heuristic when none were stored."""
    try:
        names = {e["name"] for e in json.loads(m.get("entities") or "[]")}
    except Exception:
        names = set()
    return names or entities(m["title"])

def entities(title):
    """Capitalised words that are not sentence starters or generic terms: a cheap company/person detector."""
    words = re.findall(r"[A-Z][A-Za-z0-9&'’-]{2,}", title or "")
    return {w.strip("'’-") for w in words if w not in STOPCAP}

_cache = {"at": 0, "data": None}

def _view_week(week):
    """If the new week has not started yet (no issue, almost no articles), show the latest edition instead of an empty page."""
    with db.conn() as c:
        has_issue = db.one(c, "SELECT 1 AS x FROM issues WHERE week=?", (week,))
        n = db.one(c, "SELECT COUNT(*) AS n FROM articles WHERE week=?", (week,))["n"]
        last = None if has_issue or n >= 20 else db.one(c, "SELECT week FROM issues WHERE week < ? ORDER BY week DESC LIMIT 1", (week,))
    return (last["week"], True) if last else (week, False)

def state(fresh=False):
    """Four independent query groups run in parallel (each on its own connection); the result is cached for 15 s."""
    if not fresh and _cache["data"] and time.time() - _cache["at"] < 15:
        return _cache["data"]
    now = config.now_ist()
    week, viewing_past = _view_week(config.week_start())
    with ThreadPoolExecutor(6) as ex:
        f = [ex.submit(_q_issue, week), ex.submit(_q_articles, week), ex.submit(_q_subs), ex.submit(_q_misc, week), ex.submit(_q_memory, week), ex.submit(_q_engagement)]
        (issue, items, linkcheck), (arts, counts, total_articles), (sub_counts, subs, issues_sent, series), (sends, events, last, sg, edits, extras), mem, engagement = [x.result() for x in f]
    if linkcheck:        # a link check only counts for the draft it was run on: after a swap or re-draft it is stale, so show it as not run
        now_urls = {i["url"] for i in items if i["kind"] == "selected"}
        if {r["url"] for r in linkcheck.get("rows", [])} != now_urls:
            linkcheck = None
    dup_in_week, dup_past = counts.pop("_dup_in_week", 0), counts.pop("_dup_past", 0)
    n_scored, n_strong, n_short = counts.pop("_scored", 0), counts.pop("_strong", 0), counts.pop("_short", 0)
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
        {"key": "review", "label": "You review", "state": "done" if rank >= 2 else ("active" if rank == 1 else "todo"), "detail": f"{reviewed}/{len(sel)} stories ticked" if sel else "waiting"},
        {"key": "confirm", "label": "Confirmed", "state": "done" if rank >= 2 else "todo", "detail": (issue or {}).get("approved_at") or "waiting for you"},
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
    from app.select_stories import voice_checks
    for i in items:
        for k in ("counter", "entities", "quotes"):
            try:
                i[k] = json.loads(i.get(k) or "[]")
            except Exception:
                i[k] = []
    for i in items:
        i["checks"] = voice_checks(i["commentary"] or "", i["title"], (i["snippet"] or "") + " " + (i.get("source_text") or ""), sg["banned"]) if i["kind"] == "selected" else []
    # archive matrix: topic x week, plus entity overlap between this week's picks and the previous four issues
    weeks = sorted({m["week"] for m in mem}, reverse=True)
    matrix = {}
    for m in mem:
        matrix.setdefault(m["topic"], {}).setdefault(m["week"], 0)
        matrix[m["topic"]][m["week"]] += 1
    cur = [m for m in mem if m["week"] == week]
    ent_weeks = {}
    for m in mem:
        if m["week"] != week:
            for e in ents_of(m):
                ent_weeks.setdefault(e, set()).add(m["week"])
    overlaps = []
    for m in cur:
        hit = sorted(e for e in ents_of(m) if e in ent_weeks)
        if hit:
            overlaps.append({"title": m["title"], "entities": hit, "weeks": sorted({w for e in hit for w in ent_weeks[e]})})
    past_by_ent = {}
    for m in sorted((m for m in mem if m["week"] != week), key=lambda m: m["week"]):
        for e in ents_of(m):
            past_by_ent[e] = m            # most recent earlier edition wins
    backlinks = []
    for m in cur:
        hit = [e for e in ents_of(m) if e in past_by_ent]
        if hit:
            pm = past_by_ent[hit[0]]
            backlinks.append({"title": m["title"], "entity": hit[0], "week": pm["week"], "past_title": pm["title"], "url": pm["url"],
                              "text": f"We covered {hit[0]} in the {pm['week']} edition: \u201c{pm['title'][:90]}\u201d. Worth a line on how this new development ties back."})
    memory = {"backlinks": backlinks, "weeks": weeks, "topics": [t for t in select_stories_topics() if t in matrix], "matrix": matrix, "overlaps": overlaps,
              "stories": [{"week": m["week"], "topic": m["topic"], "title": m["title"], "url": m["url"]} for m in mem],
              "dup_in_week": dup_in_week, "dup_past": dup_past}
    topic_counts = dict(topics)
    balance = {"count": len(sel), "count_ok": 8 <= len(sel) <= 10, "topics": len(topic_counts), "topics_ok": len(topic_counts) >= 3,
               "axes": [{"topic": t, "n": topic_counts.get(t, 0)} for t in select_stories_topics()]}
    # approval tracker (real timestamps from the events table)
    ev = {}
    for e in events:
        ev.setdefault(e["kind"], e["ts"])
    approved = bool(issue and issue.get("approved_at"))
    approval = [
        {"key": "draft", "label": "DRAFT GENERATED", "state": "done" if issue and issue.get("drafted_at") else "pending", "ts": (issue or {}).get("drafted_at"), "note": "Gemini selection + commentary"},
        {"key": "telegram", "label": "TELEGRAM DISPATCHED", "state": "done" if ev.get("telegram_draft") else "pending", "ts": ev.get("telegram_draft"), "note": "story-by-story review buttons"},
        {"key": "reminder", "label": "REMINDER", "state": "done" if (issue or {}).get("reminder_sent") else ("skipped" if approved else "queued"),
         "ts": ev.get("reminder"), "note": "sent" if (issue or {}).get("reminder_sent") else ("not needed, confirmed in time" if approved else "queued for Wed 10:00 PM if unconfirmed")},
        {"key": "confirmed", "label": "EXPLICITLY CONFIRMED", "state": "done" if approved else "pending", "ts": (issue or {}).get("approved_at"), "note": "two-step confirmation in Telegram"},
    ]
    is_confirmed = bool(approved and status in ("approved", "sending", "sent"))
    active = sub_counts.get("active", 0)
    checks = [
        {"label": "You have explicitly confirmed (approved_at is set)", "ok": is_confirmed, "detail": "required, enforced in mailer.send_issue()"},
        {"label": "Active recipients on the list", "ok": active > 0, "detail": f"{active} active"},
        {"label": "Email provider key present", "ok": bool(config.RESEND_API_KEY), "detail": "Resend"},
        {"label": "Bounce and complaint webhook secured", "ok": bool(config.RESEND_WEBHOOK_SECRET), "detail": "signature verified"},
    ]
    if "resend.dev" in (config.RESEND_FROM or ""):
        checks.append({"label": "Send mode", "ok": True, "detail": "Test mode: delivers to the account owner plus 25 sample addresses until a domain is verified"})
    launchpad = {"armed": all(c["ok"] for c in checks), "confirmed": is_confirmed, "checks": checks,
                 "headline": ("ARMED: sends Thursday 8:00 AM IST" if status == "approved" else "SENT" if status == "sent" else "SENDING" if status == "sending" else "ARMED") if all(c["ok"] for c in checks)
                             else "SAFE: nothing can send until you confirm"}
    from app.ingest import similar as _sim
    past_pairs = [(m["title"], m["week"], fingerprint_of(m["title"])) for m in mem if m["week"] != week]
    dropped = {r["title"]: r["reason"] for r in extras.get("repeat_dropped", [])}
    runner = {i["title"]: i["position"] for i in items if i["kind"] == "backup"}
    for a in arts:
        sg_, fl = a.get("signal"), (a.get("signal_filter") or "NONE")
        if a["status"] == "dup":
            if a.get("dup_title"):
                a["reason"] = f"Duplicate of \u201c{a['dup_title'][:80]}\u201d. The first copy was kept."
            else:
                m = next((p for p in past_pairs if _sim(a.get("fingerprint") or "", p[2])), None)
                a["reason"] = f"Already covered: matches \u201c{m[0][:70]}\u201d from the {m[1]} issue." if m else "Matches a story from the last four issues."
        elif a["status"] == "selected":
            a["reason"] = "Picked for this issue."
        elif a["title"] in dropped:
            a["reason"] = "Dropped by a safeguard: it " + dropped[a["title"]] + "."
        elif a["title"] in runner:
            a["reason"] = f"Runner-up #{runner[a['title']]}: kept in reserve for the Swap carousel."
        elif a["source"] == "Added by Shreya":
            a["reason"] = "Hand-picked by you; in the pool for selection."
        elif sg_ is None:
            a["reason"] = "Not scored."
        elif fl == "NONE" and sg_ is not None and a.get("signal_filter") is None:
            a["reason"] = f"Pre-screen {sg_}/100: below the cut for the full editorial pass (the top 90 of the week go forward)."
        elif sg_ < 40:
            a["reason"] = f"Low signal ({sg_}/100): " + ("did not pass any of the three editorial filters." if fl == "NONE" else f"only weakly {fl.lower()}.")
        elif sg_ < 70:
            a["reason"] = f"Mid signal ({sg_}/100): not strong enough against this week\u2019s batch."
        else:
            a["reason"] = f"Strong signal ({sg_}/100) but outranked: the issue holds 8 to 10 stories across balanced sectors."
        a.pop("fingerprint", None)
    n_total = sum(counts.values())
    for row in list(arts) + list(items):          # shown as "you" on screen; the stored value stays "Added by Shreya" because the selector keys on it
        if row.get("source") == "Added by Shreya":
            row["source"] = "Added by you"
    uniq = n_total - counts.get("dup", 0)
    funnel = [{"label": "Articles collected", "n": n_total, "note": "Everything read this week from the RSS feeds and news APIs."},
              {"label": "After removing repeats", "n": uniq, "note": f"{counts.get('dup', 0)} repeats removed: {dup_in_week} were the same story as another this week, {dup_past} were already in the last four issues."},
              {"label": "Scored by Gemini", "n": n_scored, "note": "Each story gets a 0 to 100 score for how useful it is to your readers" + (f" ({uniq - n_scored} not scored: added after scoring or could not be rated)." if uniq > n_scored else ".")},
              {"label": "Shortlisted", "n": n_short, "note": f"The top {n_short} by score (at most 14 per source) go forward to the final pick. {n_strong} of them scored 60 or more."},
              {"label": "In this week\u2019s issue", "n": len(sel), "note": "Gemini picks the final stories across at least three topics" + (f"; the repeat guard swapped out {len(extras.get('repeat_dropped', []))} that were about companies covered recently." if extras.get("repeat_dropped") else ".")}]
    growth = {"active": active, "target": 2200, "series": series}
    deliv = []
    if issue and sel:
        try:
            from app.email_template import render as _render, deliverability
            sub_, html_, text_ = _render({**issue, "selection_notes": issue.get("selection_notes")}, sel)
            deliv = deliverability(sub_, html_, text_, config.RESEND_FROM)
        except Exception:
            deliv = []
    graph = build_graph(mem, week, extras.get("editions"), now)
    trends = extras["trends"]
    if trends:      # attach titles and sector overlap so the heatmap needs no further lookups
        by = {a["id"]: a for a in arts}
        for cl in trends["clusters"]:
            cl["articles"] = [{"title": by[i]["title"], "url": by[i]["url"], "source": by[i]["source"]} for i in cl["article_ids"] if i in by][:6]
            cl["size"] = len(cl["article_ids"]); cl["cross"] = len(cl["sectors"]) > 1
    data = {
        "now": now.isoformat(timespec="minutes"), "week": week, "mode": "postgres" if db.PG else "sqlite", "public_url": config.PUBLIC_URL,
        "issue": ({**{k: issue[k] for k in ("id", "week", "status", "approved_at", "sent_at", "drafted_at", "selection_notes", "subject", "preheader")},
                  "subject_options": json.loads(issue.get("subject_options") or "[]"), "fusions": json.loads(issue.get("fusions") or "[]")} if issue else None),
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
        "model": config.GEMINI_MODEL, "sender": config.RESEND_FROM, "viewing_past": viewing_past, "confirm_mode": "instant" if "resend.dev" in config.RESEND_FROM else "confirm",
        "memory": memory, "balance": balance, "approval": approval, "launchpad": launchpad, "growth": growth, "engagement": engagement, "benchmark_open_rate": 38,
        "deliverability": deliv, "funnel": funnel, "graph": graph, "trends": trends, "linkcheck": linkcheck, "tuner": extras["tuner"], "reminder": reminder_info(week, issue, extras["snooze"]),
        "buzz": BUZZ_SWAPS, "unsub_reasons": series.get("reasons", []),
        "scored": sum(1 for a in arts if a.get("signal") is not None), "bot": "https://t.me/Dispatch_Mesa_Bot",
    }
    _cache.update(at=time.time(), data=data)
    return data

@router.get("/api/admin/state")
def api_state(fresh: bool = False):
    return JSONResponse(state(fresh))

def _cooldown(step, secs=COOLDOWN_S):
    """Returns seconds left if this step ran recently, else records the run and returns 0."""
    with db.conn() as c:
        last = float(db.kv_get(c, f"cooldown:{step}", "0"))
        left = int(secs - (time.time() - last))
        if left > 0:
            return left
        db.kv_set(c, f"cooldown:{step}", str(time.time()))
    return 0

@router.post("/api/admin/run/{step}")
def run_step(step: str, request: Request):
    same_origin(request)
    from app import ingest, select_stories, telegram, styleguide
    if step not in ("ingest", "select", "draft", "promote", "ping", "linkcheck"):
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
    if step == "ping":
        r = telegram.send_reminder(force=True)
        return {"ok": "reminded" in r, "message": "Reminder ping sent to Telegram." if "reminded" in r else f"Nothing to ping: {r.get('skipped')}."}
    if step == "linkcheck":
        from app import linkcheck
        with db.conn() as c:
            issue = db.one(c, "SELECT id FROM issues WHERE week=?", (config.week_start(),))
        if not issue:
            return {"ok": False, "message": "No draft this week yet."}
        r = linkcheck.run(issue["id"])
        return {"ok": True, "message": f"Checked {len(r['rows'])} links: {r['problems']} need attention."}
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
    return {"ok": True, "added": sum(1 for r in res if r["ok"]), "invalid": sum(1 for r in res if not r["ok"]), "mode": next((r.get("mode") for r in res if r.get("mode")), "instant")}


@router.post("/api/admin/voice-check")
async def voice_check(request: Request):
    """Stateless, read-only: runs Shreya's voice rules over any text. Nothing is saved."""
    same_origin(request)
    from app import styleguide
    from app.select_stories import voice_checks
    b = await request.json()
    text = str(b.get("text", ""))[:1200]
    with db.conn() as c:
        banned = styleguide.active(c)["banned"]
    ck = voice_checks(text, str(b.get("title", ""))[:300], str(b.get("snippet", ""))[:800], banned)
    return {"checks": ck, "pass": all(x["ok"] for x in ck)}

@router.post("/api/admin/preview-commentary")
async def preview_commentary(request: Request):
    """Drafts commentary for a runner-up so Shreya can see it before swapping. Nothing is written to the draft."""
    same_origin(request)
    left = _cooldown("preview", 6)
    if left:
        return JSONResponse({"ok": False, "message": f"One moment, try again in {left}s."})
    from app import styleguide, select_stories
    item_id = int((await request.json()).get("item_id", 0))
    with db.conn() as c:
        it = db.one(c, """SELECT i.selection_filter, i.source_text, a.title, a.source, a.snippet FROM issue_items i JOIN articles a ON a.id=i.article_id
                          WHERE i.id=? AND i.kind='backup'""", (item_id,))
        sg = styleguide.active(c)
    if not it:
        raise HTTPException(404)
    text, errs = select_stories.draft_one(sg, it, fast=True)
    return {"ok": True, "commentary": text, "checks": select_stories.voice_checks(text, it["title"], (it["snippet"] or "") + " " + (it.get("source_text") or ""), sg["banned"])}

@router.get("/api/admin/email-preview", response_class=HTMLResponse)
def email_preview():
    """The exact HTML that subscribers would receive, rendered from the current draft."""
    from app import mailer
    week, _ = _view_week(config.week_start())
    with db.conn() as c:
        issue = db.one(c, "SELECT * FROM issues WHERE week=?", (week,))
        items = db.all(c, """SELECT i.position, i.topic, i.commentary, i.access, i.alt_url, i.alt_source, a.title, a.url, a.source FROM issue_items i JOIN articles a ON a.id=i.article_id
                             WHERE i.issue_id=? AND i.kind='selected' ORDER BY i.position""", (issue["id"],)) if issue else []
    if not items:
        return HTMLResponse("<body style='font:16px sans-serif;padding:40px'>No draft yet this week.</body>")
    return HTMLResponse(mailer.render(issue, items)[1], headers={"Cache-Control": "no-store"})


@router.post("/api/admin/tuner")
async def set_tuner(request: Request):
    """Voice micro-tuner: three 0-100 sliders that steer the next Gemini editorial pass. Clamped, rate-limited, style-only."""
    same_origin(request)
    left = _cooldown("tuner", 3)
    if left:
        return {"ok": False, "message": "One moment."}
    b = await request.json()
    t = {k: max(0, min(100, int(b.get(k, 50)))) for k in ("cynicism", "focus", "density")}
    with db.conn() as c:
        db.kv_set(c, "tuner", json.dumps(t))
        db.log(c, "tuner", json.dumps(t))
    _cache["data"] = None
    return {"ok": True, "tuner": t, "message": "Saved. It applies the next time Gemini runs the editorial pass."}

@router.post("/api/admin/revoice")
async def revoice(request: Request):
    """Instant re-voice: Gemini rewrites one story's commentary with an extra instruction. Preview only; saving a rewrite is done with Edit in Telegram."""
    same_origin(request)
    left = _cooldown("preview", 6)
    if left:
        return JSONResponse({"ok": False, "message": f"One moment, try again in {left}s."})
    from app import styleguide, select_stories
    b = await request.json()
    instruction = str(b.get("instruction", ""))[:200]
    with db.conn() as c:
        it = db.one(c, """SELECT i.selection_filter, i.source_text, a.title, a.source, a.snippet FROM issue_items i JOIN articles a ON a.id=i.article_id
                          WHERE i.id=? AND i.kind='selected'""", (int(b.get("item_id", 0)),))
        sg = styleguide.active(c)
    if not it:
        raise HTTPException(404)
    text, errs = select_stories.draft_one(sg, it, instruction=instruction, fast=True)
    return {"ok": True, "commentary": text, "checks": select_stories.voice_checks(text, it["title"], (it["snippet"] or "") + " " + (it.get("source_text") or ""), sg["banned"])}

@router.post("/api/admin/snooze")
async def snooze(request: Request):
    same_origin(request)
    left = _cooldown("snooze", 5)
    if left:
        return {"ok": False, "message": "One moment."}
    mins = int((await request.json()).get("minutes", 60))
    mins = mins if mins in (30, 60) else 60
    until = (config.now_ist() + timedelta(minutes=mins)).isoformat(timespec="minutes")
    with db.conn() as c:
        db.kv_set(c, "snooze_until", until)
        db.log(c, "snooze", f"reminder snoozed until {until}")
    _cache["data"] = None
    return {"ok": True, "message": f"Reminder snoozed until {until[11:]} IST."}


@router.post("/api/admin/fuse")
async def fuse(request: Request):
    """Trend-Fusion canvas: connect two of this week's stories into one commentary block. Preview only; nothing is saved to the draft."""
    same_origin(request)
    left = _cooldown("preview", 6)
    if left:
        return JSONResponse({"ok": False, "message": f"One moment, try again in {left}s."})
    from app import styleguide, select_stories
    b = await request.json()
    with db.conn() as c:
        rows = {r["id"]: r for r in db.all(c, """SELECT i.id, i.source_text, a.title, a.source, a.snippet FROM issue_items i JOIN articles a ON a.id=i.article_id
                                                 WHERE i.id IN (?, ?) AND i.kind IN ('selected','backup')""", (int(b.get("a", 0)), int(b.get("b", 0))))}
        sg = styleguide.active(c)
    if len(rows) != 2:
        raise HTTPException(404)
    x, y = rows[int(b["a"])], rows[int(b["b"])]
    text, errs = select_stories.fuse(sg, x, y)
    return {"ok": True, "commentary": text, "checks": select_stories.voice_checks(text, x["title"] + " " + y["title"], f"{x['snippet'] or ''} {y['snippet'] or ''} {x.get('source_text') or ''} {y.get('source_text') or ''}", sg["banned"])}
