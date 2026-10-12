import os
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

def env(k, d=""):
    return os.getenv(k, d)

GEMINI_API_KEY = env("GEMINI_API_KEY")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-3.8-flash")
DATABASE_URL = env("DATABASE_URL")
NEWSAPI_KEY = env("NEWSAPI_KEY")
GNEWS_API_KEY = env("GNEWS_API_KEY")
NEWSDATA_API_KEY = env("NEWSDATA_API_KEY")
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID")
TELEGRAM_WEBHOOK_SECRET = env("TELEGRAM_WEBHOOK_SECRET")
RESEND_API_KEY = env("RESEND_API_KEY")
RESEND_FROM = env("RESEND_FROM", "The Dispatch <onboarding@resend.dev>")
RESEND_WEBHOOK_SECRET = env("RESEND_WEBHOOK_SECRET")
CRON_SECRET = env("CRON_SECRET")
# Vercel provides VERCEL_PROJECT_PRODUCTION_URL automatically, so no manual setting is needed in production
PUBLIC_URL = env("PUBLIC_URL") or (f"https://{env('VERCEL_PROJECT_PRODUCTION_URL')}" if env("VERCEL_PROJECT_PRODUCTION_URL") else "http://localhost:8000")

# Editorial rules from the brief
PICK_MIN, PICK_MAX = 8, 10
MIN_TOPICS = 3
LOOKBACK_ISSUES = 4
DB_PATH = ROOT / "data" / "dispatch.db"

def now_ist():
    """Vercel runs in UTC; India time as a naive datetime."""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def week_start(d=None):
    """Monday of the week (IST) that the issue belongs to, as YYYY-MM-DD."""
    d = d or now_ist()
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")
