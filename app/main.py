from fastapi import FastAPI, Request, HTTPException
from app import config
from app import db

app = FastAPI(title="The Dispatch: Newsletter Intelligence Engine")

@app.get("/api/health")
def health():
    with db.conn() as c:
        n = db.one(c, "SELECT COUNT(*) AS n FROM articles")["n"]
    return {"ok": True, "articles": n}

@app.post("/api/cron/ingest")
@app.get("/api/cron/ingest")
def cron_ingest():
    from app import ingest
    return ingest.run_ingest()

@app.post("/api/cron/select")
@app.get("/api/cron/select")
def cron_select(force: bool = False):
    from app import select_stories
    return select_stories.run_selection(force)

@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    from app import telegram
    if request.headers.get("x-telegram-bot-api-secret-token") != config.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(403)
    telegram.handle_update(await request.json())
    return {"ok": True}

@app.post("/api/cron/reminder")
@app.get("/api/cron/reminder")
def cron_reminder():
    from app import telegram
    return telegram.send_reminder()
