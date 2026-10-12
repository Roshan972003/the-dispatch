from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
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

# ---------------- Telegram ----------------
@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    from app import telegram
    if request.headers.get("x-telegram-bot-api-secret-token") != config.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(403)
    telegram.handle_update(await request.json())
    return {"ok": True}

# ---------------- subscribers ----------------
PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>The Dispatch</title>
<style>body{margin:0;background:#fafaf9;color:#1c1917;font:17px/1.6 Georgia,serif}main{max-width:560px;margin:0 auto;padding:12vh 20px}h1{font-size:42px;margin:0 0 8px}
p{color:#44403c}form{display:flex;gap:8px;flex-wrap:wrap;margin-top:24px}input{flex:1;min-width:220px;padding:12px;font:16px sans-serif;border:1px solid #d6d3d1;border-radius:6px}
button{padding:12px 20px;font:600 16px sans-serif;background:#1c1917;color:#fff;border:0;border-radius:6px;cursor:pointer}#m{margin-top:14px;font:15px sans-serif}</style></head><body><main>%s</main></body></html>"""

@app.get("/", response_class=HTMLResponse)
def landing():
    return PAGE % ("""<h1>The Dispatch</h1><p>Eight to ten stories on the Indian startup ecosystem, every Thursday, with commentary on what the headline leaves out.</p>
<form id="f"><input type="email" name="email" placeholder="you@company.com" required><button>Subscribe</button></form><div id="m"></div>
<script>f.onsubmit=async e=>{e.preventDefault();const r=await fetch('/api/subscribe',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email:f.email.value})});
const j=await r.json();m.textContent=j.message||j.error||'Something went wrong.'}</script>""")

@app.post("/api/subscribe")
async def api_subscribe(request: Request):
    from app import mailer
    return mailer.subscribe((await request.json()).get("email", ""))

@app.get("/confirm", response_class=HTMLResponse)
def confirm(t: str):
    from app import mailer
    s = mailer.set_status_by_token(t, "active")
    return PAGE % ("<h1>You're in.</h1><p>Welcome to The Dispatch. The next issue lands on Thursday.</p>" if s else "<h1>Link not recognised.</h1>")

@app.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_page(t: str):
    return PAGE % (f'<h1>Unsubscribe?</h1><p>You will stop receiving The Dispatch.</p><form method="post" action="/unsubscribe?t={t}"><button>Yes, unsubscribe</button></form>')

@app.post("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(t: str):
    """Handles both the confirm button and the mail client's one-click List-Unsubscribe POST."""
    from app import mailer
    s = mailer.set_status_by_token(t, "unsubscribed")
    return PAGE % ("<h1>You're unsubscribed.</h1><p>Sorry to see you go.</p>" if s else "<h1>Link not recognised.</h1>")

# ---------------- Resend webhook (bounces, complaints) ----------------
@app.post("/api/resend/webhook")
async def resend_webhook(request: Request):
    from app import mailer
    body = await request.body()
    if not mailer.verify_webhook(request.headers, body):
        raise HTTPException(403)
    import json
    return mailer.handle_webhook(json.loads(body))
