"""Telegram review loop. Shreya reviews the draft story by story (Keep / Swap / Edit), then confirms.
Only TELEGRAM_CHAT_ID is obeyed. Nothing is ever emailed from here without an explicit two-step confirmation."""
import json
from html import escape as h
import httpx
from app import config, db, select_stories, styleguide

_client = httpx.Client(timeout=20)   # reused connection: avoids a TLS handshake on every Telegram call

def api(method, **payload):
    r = _client.post(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{method}", json=payload)
    data = r.json()
    if not data.get("ok") and "not modified" not in str(data.get("description", "")):
        raise RuntimeError(f"Telegram {method}: {data.get('description')}")
    return data.get("result")

def say(text, **kw):
    return api("sendMessage", chat_id=config.TELEGRAM_CHAT_ID, text=text, parse_mode="HTML", disable_web_page_preview=True, **kw)

# ---------------- rendering ----------------
def items_of(c, issue_id):
    return db.all(c, """SELECT i.*, a.title, a.url, a.source, a.snippet FROM issue_items i JOIN articles a ON a.id=i.article_id
                        WHERE i.issue_id=? AND i.kind='selected' ORDER BY i.position""", (issue_id,))

def item_text(it, total):
    mark = "✅ " if it["reviewed"] else ""
    edited = " · ✏️ edited" if it["edited"] else ""
    warn = f"\n⚠️ <i>Auto-check: {h(it['flags'])}</i>" if it.get("flags") else ""
    return (f"{mark}<b>{it['position']}/{total} · {h(it['topic'] or '')}</b> · <i>{h((it['selection_filter'] or '').lower())}</i>{edited}\n"
            f"<a href=\"{h(it['url'])}\">{h(it['title'])}</a> ({h(it['source'])})\n\n{h(it['commentary'] or '')}{warn}")

def item_buttons(it):
    return {"inline_keyboard": [[{"text": "✅ Keep", "callback_data": f"keep:{it['id']}"},
                                 {"text": "🔄 Swap", "callback_data": f"swap:{it['id']}"},
                                 {"text": "✏️ Edit", "callback_data": f"edit:{it['id']}"}]]}

def confirm_buttons(issue_id):
    return {"inline_keyboard": [[{"text": "📬 Confirm final draft", "callback_data": f"confirm:{issue_id}"}]]}

def send_draft(issue_id=None):
    with db.conn() as c:
        issue = db.one(c, "SELECT * FROM issues WHERE id=?", (issue_id,)) if issue_id else db.one(c, "SELECT * FROM issues ORDER BY week DESC LIMIT 1")
        if not issue:
            return {"error": "no issue"}
        items = items_of(c, issue["id"])
        subs = db.one(c, "SELECT COUNT(*) AS n FROM subscribers WHERE status='active'")["n"]
    flag = ""
    if "FLAG:" in (issue["selection_notes"] or ""):
        flag = "\n⚠️ " + h(issue["selection_notes"].split("FLAG:", 1)[1].strip())
    theme = (issue["selection_notes"] or "").split("\nFLAG:")[0].strip()
    say(f"<b>The Dispatch · draft for week of {issue['week']}</b>\n{len(items)} stories · {subs} active subscribers\n"
        + (f"<i>{h(theme)}</i>\n" if theme else "") + flag +
        "\nReview each story below: <b>Keep</b> to tick it off, <b>Swap</b> for the next-best story, <b>Edit</b> to rewrite the commentary. "
        "Nothing is sent until you confirm at the bottom.")
    with db.conn() as c:
        for it in items:
            m = say(item_text(it, len(items)), reply_markup=item_buttons(it))
            db.run(c, "UPDATE issue_items SET tg_message_id=? WHERE id=?", (m["message_id"], it["id"]))
        db.run(c, "UPDATE issues SET status=CASE WHEN status='collecting' THEN 'drafted' ELSE status END WHERE id=?", (issue["id"],))
        db.log(c, "telegram_draft", f"issue {issue['id']} sent for review")
    say("When you are happy with the draft:", reply_markup=confirm_buttons(issue["id"]))
    return {"issue_id": issue["id"], "stories": len(items)}

def send_reminder(force=False):
    """Wed 10 PM IST: nudge if the draft is still unconfirmed. Honours a dashboard snooze; force=True is the manual ping."""
    from datetime import datetime
    with db.conn() as c:
        issue = db.one(c, "SELECT * FROM issues WHERE week=?", (config.week_start(),))
        if not issue or issue["status"] != "drafted":
            return {"skipped": issue["status"] if issue else "no issue"}
        if not force:
            if issue["reminder_sent"]:
                return {"skipped": "already reminded"}
            snooze = db.kv_get(c, "snooze_until")
            if snooze and datetime.fromisoformat(snooze) > config.now_ist():
                return {"skipped": f"snoozed until {snooze}"}
        db.run(c, "UPDATE issues SET reminder_sent=1 WHERE id=?", (issue["id"],))
        db.run(c, "DELETE FROM kv WHERE k='snooze_until'")
        db.log(c, "reminder", f"issue {issue['id']}" + (" (manual ping)" if force else ""))
    say("⏰ <b>Reminder:</b> this week's Dispatch draft is still waiting for your confirmation. "
        "Nothing will be sent until you confirm.", reply_markup=confirm_buttons(issue["id"]))
    return {"reminded": issue["id"]}

# ---------------- actions ----------------
def _refresh(it_id):
    with db.conn() as c:
        it = db.one(c, """SELECT i.*, a.title, a.url, a.source, a.snippet FROM issue_items i JOIN articles a ON a.id=i.article_id WHERE i.id=?""", (it_id,))
        total = db.one(c, "SELECT COUNT(*) AS n FROM issue_items WHERE issue_id=? AND kind='selected'", (it["issue_id"],))["n"]
    if it["tg_message_id"]:
        api("editMessageText", chat_id=config.TELEGRAM_CHAT_ID, message_id=it["tg_message_id"], text=item_text(it, total),
            parse_mode="HTML", disable_web_page_preview=True, reply_markup=item_buttons(it))

def _locked(c, issue_id):
    return db.one(c, "SELECT status FROM issues WHERE id=?", (issue_id,))["status"] in ("approved", "sending", "sent")

def do_swap(item_id):
    with db.conn() as c:
        old = db.one(c, "SELECT * FROM issue_items WHERE id=?", (item_id,))
        if not old or old["kind"] != "selected":
            return "That story is no longer in the draft."
        if _locked(c, old["issue_id"]):
            return "Draft is already confirmed. Reopen it first."
        bk = db.one(c, "SELECT i.*, a.title, a.source, a.snippet FROM issue_items i JOIN articles a ON a.id=i.article_id "
                       "WHERE i.issue_id=? AND i.kind='backup' ORDER BY i.position LIMIT 1", (old["issue_id"],))
        if not bk:
            return "No backup stories left."
        sg = styleguide.active(c)
    text, errs = select_stories.draft_one(sg, {"title": bk["title"], "source": bk["source"], "snippet": bk["snippet"], "selection_filter": bk["selection_filter"]})
    with db.conn() as c:
        db.run(c, """UPDATE issue_items SET kind='selected', position=?, commentary=?, draft_original=?, flags=?, reviewed=0, tg_message_id=? WHERE id=?""",
               (old["position"], text, text, "; ".join(errs), old["tg_message_id"], bk["id"]))
        db.run(c, "UPDATE issue_items SET kind='swapped_out', tg_message_id=NULL WHERE id=?", (old["id"],))
        db.run(c, "UPDATE articles SET status='new' WHERE id=?", (old["article_id"],))
        db.run(c, "UPDATE articles SET status='selected' WHERE id=?", (bk["article_id"],))
        db.log(c, "swap", f"item {old['id']} -> backup {bk['id']}")
    _refresh(bk["id"])
    return "Swapped for the next-best story."

def do_keep(item_id):
    with db.conn() as c:
        db.run(c, "UPDATE issue_items SET reviewed=1 WHERE id=?", (item_id,))
    _refresh(item_id)
    return "Kept."

def ask_edit(item_id):
    with db.conn() as c:
        it = db.one(c, "SELECT * FROM issue_items WHERE id=?", (item_id,))
        if _locked(c, it["issue_id"]):
            return "Draft is already confirmed. Reopen it first."
    m = say(f"✏️ Reply to <i>this message</i> with your version of the commentary for story {it['position']}.\n\nCurrent:\n{h(it['commentary'])}",
            reply_markup={"force_reply": True, "input_field_placeholder": "Your commentary"})
    with db.conn() as c:
        db.kv_set(c, f"edit_prompt:{m['message_id']}", str(item_id))
    return "Reply to the prompt below."

def save_edit(prompt_msg_id, text):
    with db.conn() as c:
        raw = db.kv_get(c, f"edit_prompt:{prompt_msg_id}")
        if not raw:
            return False
        it = db.one(c, "SELECT * FROM issue_items WHERE id=?", (int(raw),))
        if _locked(c, it["issue_id"]):
            say("Draft is already confirmed. Reopen it first to edit."); return True
        db.run(c, "INSERT INTO edits (article_id, gemini_draft, shreya_edit, created_at) VALUES (?,?,?,?)",
               (it["article_id"], it["draft_original"] or it["commentary"], text.strip(), config.now_ist().isoformat(timespec="seconds")))
        db.run(c, "UPDATE issue_items SET commentary=?, edited=1, reviewed=1, flags=NULL WHERE id=?", (text.strip(), it["id"]))
        db.run(c, "DELETE FROM kv WHERE k=?", (f"edit_prompt:{prompt_msg_id}",))
        db.log(c, "edit", f"item {it['id']}")
    _refresh(it["id"])
    say("Saved. I'll learn from this edit.")
    return True

def ask_confirm(issue_id):
    with db.conn() as c:
        iss = db.one(c, "SELECT * FROM issues WHERE id=?", (issue_id,))
        if iss["status"] in ("approved", "sending", "sent"):
            return f"Already {iss['status']}."
        items = items_of(c, issue_id)
        subs = db.one(c, "SELECT COUNT(*) AS n FROM subscribers WHERE status='active'")["n"]
    pending = sum(1 for i in items if not i["reviewed"])
    say(f"Send this issue to <b>{subs}</b> subscribers on Thursday morning?\n"
        + (f"({pending} stories not yet ticked with Keep.)\n" if pending else "") + "This is the final confirmation.",
        reply_markup={"inline_keyboard": [[{"text": "✅ Yes, send Thursday", "callback_data": f"yes:{issue_id}"},
                                           {"text": "Cancel", "callback_data": f"no:{issue_id}"}]]})
    return "Please confirm below."

def do_confirm(issue_id):
    with db.conn() as c:
        iss = db.one(c, "SELECT * FROM issues WHERE id=?", (issue_id,))
        if iss["status"] != "drafted":
            return f"Issue is {iss['status']}."
        db.run(c, "UPDATE issues SET status='approved', approved_at=? WHERE id=?", (config.now_ist().isoformat(timespec="seconds"), issue_id))
        db.log(c, "approved", f"issue {issue_id}")
    from app import pipeline
    msg = pipeline.on_approved(issue_id)
    say("✅ <b>Confirmed.</b> " + msg, reply_markup={"inline_keyboard": [[{"text": "↩️ Reopen draft", "callback_data": f"reopen:{issue_id}"}]]})
    return "Confirmed."

def do_reopen(issue_id):
    with db.conn() as c:
        iss = db.one(c, "SELECT * FROM issues WHERE id=?", (issue_id,))
        if iss["status"] != "approved":
            return f"Cannot reopen, issue is {iss['status']}."
        db.run(c, "UPDATE issues SET status='drafted', approved_at=NULL WHERE id=?", (issue_id,))
    say("Draft reopened. Nothing will be sent until you confirm again.", reply_markup=confirm_buttons(issue_id))
    return "Reopened."

# ---------------- update router ----------------
def handle_update(u):
    if "callback_query" in u:
        q = u["callback_query"]
        if str(q["message"]["chat"]["id"]) != str(config.TELEGRAM_CHAT_ID):
            return
        act, _, arg = q["data"].partition(":")
        fn = {"keep": do_keep, "swap": do_swap, "edit": ask_edit, "confirm": ask_confirm, "yes": do_confirm, "reopen": do_reopen,
              "no": lambda a: "Cancelled. Nothing will be sent."}.get(act)
        slow = act == "swap"            # Gemini call: acknowledge the tap first so the button stops spinning
        if slow:
            api("answerCallbackQuery", callback_query_id=q["id"], text="Finding a replacement...")
        try:
            note = fn(int(arg)) if fn else "Unknown action."
        except Exception as e:
            note = f"Error: {str(e)[:150]}"
        if not slow:
            api("answerCallbackQuery", callback_query_id=q["id"], text=note)
        elif not note.startswith("Swapped"):
            say(note)
        return
    m = u.get("message")
    if not m or str(m["chat"]["id"]) != str(config.TELEGRAM_CHAT_ID):
        return
    text = (m.get("text") or "").strip()
    if m.get("reply_to_message") and text and not text.startswith("/"):
        if save_edit(m["reply_to_message"]["message_id"], text):
            return
    if text.startswith("/draft"):
        send_draft()
    elif text.startswith("/status"):
        with db.conn() as c:
            i = db.one(c, "SELECT * FROM issues ORDER BY week DESC LIMIT 1")
            n = db.one(c, "SELECT COUNT(*) AS n FROM articles WHERE week=?", (config.week_start(),))["n"]
        say(f"Week {config.week_start()}: {n} articles collected. Issue: <b>{i['status'] if i else 'not drafted yet'}</b>.")
    else:
        say("I'm The Dispatch bot. I send you the weekly draft on Wednesday evening.\n/draft resend the current draft\n/status pipeline status")
