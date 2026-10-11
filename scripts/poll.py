"""Local testing without a public URL: long-poll Telegram and feed updates to the same handler the webhook uses."""
import sys, time, httpx
sys.path.insert(0, ".")
from app import config, telegram
base = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
httpx.post(base + "/deleteWebhook")
off = None
print("polling... Ctrl+C to stop", flush=True)
while True:
    r = httpx.get(base + "/getUpdates", params={"timeout": 25, "offset": off}, timeout=40).json()
    for u in r.get("result", []):
        off = u["update_id"] + 1
        try: telegram.handle_update(u)
        except Exception as e: print("error:", e, flush=True)
