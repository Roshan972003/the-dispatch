"""Email side: render the issue, send via Resend, subscriber lifecycle (confirm / unsubscribe / bounce / complaint).
send_issue() refuses to run unless Shreya has confirmed the issue (status approved/sending)."""
import re, time, hmac, hashlib, base64, secrets
from datetime import datetime, timedelta
from html import escape as h
import httpx
from app import config, db

RESEND = "https://api.resend.com"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_client = httpx.Client(timeout=30)

def _auth():
    return {"Authorization": f"Bearer {config.RESEND_API_KEY}"}

# ---------------- rendering ----------------
from app.email_template import render, send_date, unsub_url   # the design lives in email_template.py

def _payload(issue, items, sub):
    subject, html, text = render(issue, items, sub["token"])
    return {"from": config.RESEND_FROM, "to": [sub["email"]], "subject": subject, "html": html, "text": text,
            "headers": {"List-Unsubscribe": f"<{unsub_url(sub['token'])}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
            "tags": [{"name": "issue", "value": str(issue["id"])}]}

# ---------------- sending ----------------
SAMPLE_SEND_CAP = 25     # generated demo subscribers: only this many are emailed per issue (never burns the provider's daily quota)

def _eligible(c):
    """Ids of active subscribers who should receive an issue: every real subscriber, plus a capped slice of sample (test) addresses."""
    real = [r["id"] for r in db.all(c, "SELECT id FROM subscribers WHERE status='active' AND COALESCE(note,'')<>'sample'")]
    sample = [r["id"] for r in db.all(c, "SELECT id FROM subscribers WHERE status='active' AND note='sample' ORDER BY id")]
    keep = set(sample[:SAMPLE_SEND_CAP]) | {r["id"] for r in db.all(c, "SELECT id FROM subscribers WHERE status='active' AND email LIKE ?", ("bounced+live%",))}
    return set(real) | keep

def send_issue(issue_id, budget_s=50):
    """Send to every active subscriber not yet sent to. Idempotent and resumable: re-running only picks up the rest."""
    from app import telegram
    t0 = time.time()
    with db.conn() as c:
        issue = db.one(c, "SELECT * FROM issues WHERE id=?", (issue_id,))
        if not issue or issue["status"] not in ("approved", "sending") or not issue["approved_at"]:
            return {"refused": "issue is not confirmed by Shreya"}
        db.run(c, "UPDATE issues SET status='sending' WHERE id=?", (issue_id,))
        items = db.all(c, """SELECT i.position, i.topic, i.commentary, i.access, i.alt_url, i.alt_source, a.title, a.url, a.source FROM issue_items i JOIN articles a ON a.id=i.article_id
                             WHERE i.issue_id=? AND i.kind='selected' ORDER BY i.position""", (issue_id,))
        ok_ids = _eligible(c)
        todo = [r for r in db.all(c, """SELECT s.id, s.email, s.token FROM subscribers s LEFT JOIN sends x ON x.subscriber_id=s.id AND x.issue_id=?
                            WHERE s.status='active' AND (x.id IS NULL OR x.status='failed')""", (issue_id,)) if r["id"] in ok_ids]
    sent = failed = 0
    for i in range(0, len(todo), 50):
        if time.time() - t0 > budget_s:
            break
        chunk = todo[i:i + 50]
        with db.conn() as c:       # claim first: a crash mid-send can never cause a double send
            for s in chunk:
                db.run(c, """INSERT INTO sends (issue_id, subscriber_id, status, sent_at) VALUES (?,?,'queued',?)
                             ON CONFLICT(issue_id, subscriber_id) DO UPDATE SET status='queued'""", (issue_id, s["id"], config.now_ist().isoformat(timespec="seconds")))
        results = _send_chunk(issue, items, chunk)
        with db.conn() as c:
            for s, (pid, err) in zip(chunk, results):
                db.run(c, "UPDATE sends SET status=?, provider_id=?, error=? WHERE issue_id=? AND subscriber_id=?",
                       ("sent" if pid else "failed", pid, err, issue_id, s["id"]))
                if err and re.search(r"invalid|not valid|does not exist", err, re.I):
                    db.run(c, "UPDATE subscribers SET status='bounced', status_changed_at=?, note=? WHERE id=?", (config.now_ist().isoformat(timespec="seconds"), err[:200], s["id"]))
                sent += 1 if pid else 0; failed += 0 if pid else 1
    with db.conn() as c:
        left = len([r for r in db.all(c, """SELECT s.id FROM subscribers s LEFT JOIN sends x ON x.subscriber_id=s.id AND x.issue_id=?
                            WHERE s.status='active' AND (x.id IS NULL OR x.status!='sent')""", (issue_id,)) if r["id"] in _eligible(c)])
        if left == 0:
            db.run(c, "UPDATE issues SET status='sent', sent_at=? WHERE id=?", (config.now_ist().isoformat(timespec="seconds"), issue_id))
        db.log(c, "send", f"issue {issue_id}: sent={sent} failed={failed} remaining={left}")
    if left == 0:
        try:
            telegram.say(f"📬 <b>Sent.</b> The Dispatch went to {sent} subscribers" + (f" ({failed} failed)." if failed else "."))
            telegram.say_group(f"📬 <b>Sent.</b> This edition went out to {sent} subscribers at {config.now_ist().strftime('%-I:%M %p')} IST on {config.now_ist().strftime('%a %-d %b')}.", disable_notification=True)
        except Exception:
            pass
    return {"sent": sent, "failed": failed, "remaining": left}

def _send_chunk(issue, items, chunk):
    """Returns [(provider_id|None, error|None)] aligned with chunk. Batch API first, per-email fallback."""
    try:
        r = _client.post(RESEND + "/emails/batch", headers=_auth(), json=[_payload(issue, items, s) for s in chunk])
        if r.status_code == 200:
            return [(d["id"], None) for d in r.json()["data"]]
    except httpx.HTTPError:
        pass
    out = []
    for s in chunk:
        time.sleep(0.55)                 # Resend default rate limit is 2 requests/second
        try:
            r = _client.post(RESEND + "/emails", headers=_auth(), json=_payload(issue, items, s))
            out.append((r.json().get("id"), None) if r.status_code == 200 else (None, r.json().get("message", r.text)[:200]))
        except httpx.HTTPError as e:
            out.append((None, str(e)[:200]))
    return out

def send_plain(to, subject, html, text=""):
    r = _client.post(RESEND + "/emails", headers=_auth(), json={"from": config.RESEND_FROM, "to": [to], "subject": subject, "html": html, "text": text or subject})
    return r.status_code == 200, r.json().get("message", "")

# ---------------- subscriber lifecycle ----------------
def now():
    return config.now_ist().isoformat(timespec="seconds")

def subscribe(email, confirmed=False):
    """Double opt-in: new sign-ups are 'pending' until they click the link. Bulk imports pass confirmed=True."""
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        return {"ok": False, "error": "Please enter a valid email address."}
    with db.conn() as c:
        s = db.one(c, "SELECT * FROM subscribers WHERE email=?", (email,))
        if s and s["status"] in ("active",):
            return {"ok": True, "message": "You are already subscribed."}
        if s and s["status"] in ("bounced", "complained"):
            return {"ok": True, "message": "Check your inbox to confirm."}      # same answer: do not reveal state
        status = "active" if confirmed else "pending"
        if s:
            db.run(c, "UPDATE subscribers SET status=?, status_changed_at=? WHERE id=?", (status, now(), s["id"])); token = s["token"]
        else:
            token = secrets.token_urlsafe(24)
            db.run(c, "INSERT INTO subscribers (email, status, token, created_at, status_changed_at) VALUES (?,?,?,?,?)", (email, status, token, now(), now()))
    if not confirmed and config.RESEND_API_KEY:
        link = f"{config.PUBLIC_URL}/confirm?t={token}"
        S = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
        send_plain(email, "Confirm your subscription to The Dispatch",
                   f'<div style="background:#f4f0e6;padding:28px 12px"><div style="max-width:520px;margin:0 auto;background:#fff;border-radius:16px;padding:36px 32px;font-family:{S};color:#1c1917">'
                   f'<div style="font:700 34px Georgia,serif;text-align:center;margin-bottom:18px">The Dispatch</div>'
                   f'<p style="font:19px/1.55 Georgia,serif;margin:0 0 20px">One tap and you’re in. Every Thursday: eight to ten Indian startup stories, with Shreya’s sharp take on each.</p>'
                   f'<p style="text-align:center;margin:26px 0"><a href="{h(link)}" style="background:#1c1917;color:#fff;text-decoration:none;font-weight:600;padding:14px 26px;border-radius:12px;display:inline-block">Confirm my subscription</a></p>'
                   f'<p style="color:#78716c;font-size:13px;margin:0">If you didn’t ask for this, ignore this email and nothing happens.</p></div></div>',
                   f"Confirm your subscription to The Dispatch: {link}")
    return {"ok": True, "message": "Check your inbox to confirm." if not confirmed else "Added."}

def set_status_by_token(token, status, reason=None):
    with db.conn() as c:
        s = db.one(c, "SELECT * FROM subscribers WHERE token=?", (token,))
        if not s:
            return None
        if s["status"] in ("bounced", "complained") and status == "active":
            return s
        db.run(c, "UPDATE subscribers SET status=?, status_changed_at=?, unsub_reason=COALESCE(?, unsub_reason) WHERE id=?", (status, now(), reason, s["id"]))
        db.log(c, status, s["email"])
        return s

def set_status_by_email(email, status, note=""):
    with db.conn() as c:
        db.run(c, "UPDATE subscribers SET status=?, status_changed_at=?, note=? WHERE email=?", (status, now(), note[:200], email.lower()))
        db.log(c, status, f"{email} {note}")

def import_subscribers(emails):
    ok = bad = 0
    for e in emails:
        r = subscribe(e, confirmed=True); ok += r["ok"]; bad += not r["ok"]
    return {"imported": ok, "invalid": bad}

# ---------------- Resend webhook ----------------
def verify_webhook(headers, body: bytes):
    """Svix signature check (Resend signs webhooks with Svix)."""
    if not config.RESEND_WEBHOOK_SECRET:
        return False
    try:
        mid, ts, sigs = headers["svix-id"], headers["svix-timestamp"], headers["svix-signature"]
        if abs(time.time() - int(ts)) > 300:
            return False
        key = base64.b64decode(config.RESEND_WEBHOOK_SECRET.split("_", 1)[1])
        mine = base64.b64encode(hmac.new(key, f"{mid}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()
        return any(hmac.compare_digest(mine, s.split(",", 1)[1]) for s in sigs.split() if "," in s)
    except Exception:
        return False

def handle_webhook(evt):
    kind, data = evt.get("type", ""), evt.get("data", {})
    to = (data.get("to") or [""])[0]
    if kind == "email.bounced":
        # Permanent = address does not exist; Transient (full mailbox etc.) is left active so one bad day does not drop a reader
        if (data.get("bounce") or {}).get("type", "Permanent") == "Permanent":
            set_status_by_email(to, "bounced", (data.get("bounce") or {}).get("message", "hard bounce"))
    elif kind == "email.complained":
        set_status_by_email(to, "complained", "spam complaint")
    elif kind in ("email.delivered", "email.opened", "email.clicked"):
        tag = next((t.get("value") for t in (data.get("tags") or []) if isinstance(t, dict) and t.get("name") == "issue"), None) if isinstance(data.get("tags"), list) else (data.get("tags") or {}).get("issue")
        with db.conn() as c:
            db.run(c, "INSERT INTO email_events (ts, kind, issue_id, recipient_hash, link) VALUES (?,?,?,?,?)",
                   (now(), kind, int(tag) if str(tag or "").isdigit() else None, hashlib.sha256(to.lower().encode()).hexdigest()[:16], (data.get("click") or {}).get("link")))
    return {"ok": True}
