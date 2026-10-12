from fastapi import FastAPI, Request, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app import config, db

app = FastAPI(title="The Dispatch: Newsletter Intelligence Engine")
from app.dashboard import router as dashboard_router
app.include_router(dashboard_router)

def cron_auth(request: Request):
    """Vercel sends 'Authorization: Bearer $CRON_SECRET' to cron routes when CRON_SECRET is set."""
    if not config.CRON_SECRET or request.headers.get("authorization") != f"Bearer {config.CRON_SECRET}":
        raise HTTPException(401)

@app.get("/api/health")
def health():
    with db.conn() as c:
        n = db.one(c, "SELECT COUNT(*) AS n FROM articles")["n"]
    keys = ["GEMINI_API_KEY", "DATABASE_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_WEBHOOK_SECRET", "RESEND_API_KEY",
            "RESEND_WEBHOOK_SECRET", "CRON_SECRET", "NEWSAPI_KEY", "GNEWS_API_KEY", "NEWSDATA_API_KEY"]
    return {"ok": True, "articles": n, "public_url": config.PUBLIC_URL, "db": "postgres" if db.PG else "sqlite",
            "configured": {k: bool(config.env(k)) for k in keys}}   # booleans only, never values

# ---------------- cron ----------------
@app.get("/api/cron/ingest", dependencies=[Depends(cron_auth)])
def cron_ingest():
    from app import ingest
    return ingest.run_ingest()

@app.get("/api/cron/select", dependencies=[Depends(cron_auth)])
def cron_select(force: bool = False):
    from app import select_stories, telegram
    res = select_stories.run_selection(force)
    if res.get("issue_id"):
        res["telegram"] = telegram.send_draft(res["issue_id"])
    return res

@app.get("/api/cron/reminder", dependencies=[Depends(cron_auth)])
def cron_reminder():
    from app import telegram
    return telegram.send_reminder()

@app.get("/api/cron/send", dependencies=[Depends(cron_auth)])
def cron_send():
    from app import pipeline
    return pipeline.thursday_send()

@app.get("/api/cron/voice", dependencies=[Depends(cron_auth)])
def cron_voice():
    """Monthly: fold Shreya's edits (and her voice notes) into a NEW style-guide version as few-shot examples. Older versions are kept."""
    from app import styleguide, telegram
    with db.conn() as c:
        n = db.one(c, "SELECT COUNT(*) AS n FROM edits WHERE promoted=0")["n"]
        v = styleguide.promote_edits(c, n=12)
        db.log(c, "voice_evolution", f"style guide -> v{v}" if v else "no new edits")
    if v:
        telegram.say(f"🧬 <b>Your voice guide just learned from your edits.</b> Style guide is now v{v} ({n} new edit(s) added as examples). Older versions are kept.")
    return {"promoted": v, "edits_considered": n}

# ---------------- Telegram ----------------
@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    from app import telegram
    if request.headers.get("x-telegram-bot-api-secret-token") != config.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(403)
    from fastapi.concurrency import run_in_threadpool
    await run_in_threadpool(telegram.handle_update, await request.json())     # blocking work must not stall the event loop (the next tap would queue behind it)
    return {"ok": True}

# ---------------- subscribers ----------------
from app import pages

@app.get("/", response_class=HTMLResponse)
def landing():
    return pages.landing()

@app.post("/api/subscribe")
async def api_subscribe(request: Request):
    from app import mailer
    return mailer.subscribe((await request.json()).get("email", ""))

@app.get("/confirm", response_class=HTMLResponse)
def confirm(t: str):
    from app import mailer
    return pages.confirmed() if mailer.set_status_by_token(t, "active") else HTMLResponse(pages.bad_link())

@app.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_page(t: str):
    return pages.unsub_form(t)

@app.post("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(t: str, reason: str = Form(None)):
    """Handles both the confirm button and the mail client's one-click List-Unsubscribe POST."""
    from app import mailer
    s = mailer.set_status_by_token(t, "unsubscribed", (reason or None) and reason[:60])
    return pages.unsubscribed(t if s else None)        # an unknown or preview token still ends on a friendly confirmation, never an error

@app.get("/resubscribe", response_class=HTMLResponse)
def resubscribe(t: str):
    from app import mailer
    with db.conn() as c:
        s = db.one(c, "SELECT status FROM subscribers WHERE token=?", (t,))
    if not s:
        return RedirectResponse("/", status_code=302)
    if s["status"] == "unsubscribed":
        mailer.set_status_by_token(t, "active")
    return pages.resubscribed()

@app.get("/sample", response_class=HTMLResponse)
def sample():
    """A sample issue for people deciding whether to subscribe: the latest edition that went out, else the current draft."""
    from app import mailer
    with db.conn() as c:
        issue = db.one(c, "SELECT * FROM issues WHERE status IN ('sending','sent') ORDER BY week DESC LIMIT 1") or db.one(c, "SELECT * FROM issues ORDER BY week DESC LIMIT 1")
        items = db.all(c, """SELECT i.position, i.topic, i.commentary, i.access, i.alt_url, i.alt_source, a.title, a.url, a.source FROM issue_items i JOIN articles a ON a.id=i.article_id
                             WHERE i.issue_id=? AND i.kind='selected' ORDER BY i.position""", (issue["id"],)) if issue else []
    if not items:
        raise HTTPException(404)
    return HTMLResponse(mailer.render(issue, items)[1])

# ---------------- Resend webhook (bounces, complaints) ----------------
@app.post("/api/resend/webhook")
async def resend_webhook(request: Request):
    from app import mailer
    body = await request.body()
    if not mailer.verify_webhook(request.headers, body):
        raise HTTPException(403)
    import json
    return mailer.handle_webhook(json.loads(body))


@app.get("/archive/{week}", response_class=HTMLResponse)
def archive(week: str):
    """Public web version of an edition. Only editions that were actually emailed are shown."""
    from app import mailer
    with db.conn() as c:
        issue = db.one(c, "SELECT * FROM issues WHERE week=? AND status IN ('sending','sent')", (week,))
        items = db.all(c, """SELECT i.position, i.topic, i.commentary, i.access, i.alt_url, i.alt_source, a.title, a.url, a.source FROM issue_items i JOIN articles a ON a.id=i.article_id
                             WHERE i.issue_id=? AND i.kind='selected' ORDER BY i.position""", (issue["id"],)) if issue else []
    if not issue:
        return RedirectResponse("/sample", status_code=302)      # not sent yet (or unknown week): show the sample issue, not an error
    return HTMLResponse(mailer.render(issue, items)[1])
