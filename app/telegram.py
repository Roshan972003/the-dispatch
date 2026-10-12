"""Telegram review loop. Shreya reviews the draft story by story (Keep / Swap / Edit), then confirms.
Only TELEGRAM_CHAT_ID is obeyed. Nothing is ever emailed from here without an explicit two-step confirmation."""
import json, re, threading
from datetime import datetime, timedelta
from html import escape as h
import httpx
from app import config, db, select_stories, styleguide

_ctx = threading.local()            # the message id of the card/message whose button was just tapped, so replies happen in place
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

def access_line(it):
    tag = {"free": "🟢 free access", "soft": "🟡 soft paywall", "hard": "🔴 hard paywall", "dead": "🔴 link looks dead"}.get(it.get("access"))
    if not tag:
        return ""
    alt = f" · free coverage: <a href=\"{h(it['alt_url'])}\">{h(it['alt_source'])}</a>" if it.get("alt_url") and it.get("access") in ("soft", "hard", "dead") else ""
    return f"\n{tag}{alt}"

def _ui(c, item_id):
    raw = db.kv_get(c, f"ui:{item_id}")
    return json.loads(raw) if raw else {}

def _ui_set(c, item_id, **kw):
    u = _ui(c, item_id); u.update(kw)
    u = {k: v for k, v in u.items() if v not in (None, False, "")}
    if u:
        db.kv_set(c, f"ui:{item_id}", json.dumps(u))
    else:
        db.run(c, "DELETE FROM kv WHERE k=?", (f"ui:{item_id}",))

def item_text(it, total, ui=None, fus=None):
    ui = ui or {}
    mark = "✅ " if it["reviewed"] else ""
    edited = " · ✏️ edited" if it["edited"] else ""
    warn = f"\n⚠️ <i>Auto-check: {h(it['flags'])}</i>" if it.get("flags") else ""
    t = (f"{mark}<b>{it['position']}/{total} · {h(it['topic'] or '')}</b> · <i>{h((it['selection_filter'] or '').lower())}</i>{edited}\n"
         f"<a href=\"{h(it['url'])}\">{h(it['title'])}</a> ({h(it['source'])}){access_line(it)}\n\n{h(it['commentary'] or '')}{warn}")
    if ui.get("heard"):
        t += f"\n\n🎙 <b>Heard:</b> <i>{h(ui['heard'])}</i>"
    if ui.get("angles"):
        bullets = json.loads(it.get("counter") or "[]")
        t += "\n\n🧠 <b>Angles</b> (things to check, not facts)\n" + ("\n".join(f"• {h(b)}" for b in bullets) or "• none were generated for this story")
        if fus:
            t += "\n🔗 <b>Connect it to</b>\n" + "\n".join(f"• story {f['b'] if f['a'] == it['position'] else f['a']}: {h(f['angle'])}" for f in fus)
    if ui.get("qa"):
        t += f"\n\n💬 <b>You asked:</b> {h(ui['qa']['q'])}\n🧠 {h(ui['qa']['a'])}"
    if ui.get("mode") == "edit":
        t += "\n\n✏️ <b>Reply to this card</b> with your version of the commentary (swipe the card right, or long-press → Reply)."
    elif ui.get("mode") == "voice":
        t += "\n\n🎙 <b>Reply to this card with a voice note</b>: say your raw take and I'll turn it into 2 to 3 sharp lines in your voice. (Swipe the card right, or long-press → Reply, then hold the mic.)"
    if ui.get("err"):
        t += f"\n\n⚠️ <i>{h(ui['err'])}</i>"
    if ui.get("busy"):
        t += f"\n\n⏳ <i>{h(ui['busy'])}</i>"
    return t[:4000]

def item_buttons(it, ui=None):
    ui = ui or {}
    rows = [[{"text": "✅ Keep", "callback_data": f"keep:{it['id']}"},
             {"text": "🔄 Swap", "callback_data": f"swap:{it['id']}"},
             {"text": "✏️ Edit", "callback_data": f"edit:{it['id']}"}],
            [{"text": "🎙 Voice", "callback_data": f"voice:{it['id']}"},
             {"text": "🧠 Hide angles" if ui.get("angles") else "🧠 Angles", "callback_data": f"ang:{it['id']}"}],
            [{"text": "🔥 Spicier", "callback_data": f"tune:{it['id']}:0"},
             {"text": "📊 Unit economics", "callback_data": f"tune:{it['id']}:1"},
             {"text": "✂️ Trim to 2 lines", "callback_data": f"tune:{it['id']}:2"}]]
    if it.get("draft_original") and it.get("commentary") != it.get("draft_original"):
        rows.append([{"text": "↩️ Back to Gemini's original", "callback_data": f"reset:{it['id']}"}])
    if ui.get("mode") or ui.get("qa") or ui.get("heard") or ui.get("err"):
        rows.append([{"text": "✖ Cancel" if ui.get("mode") else "✖ Clear", "callback_data": f"clear:{it['id']}"}])
    return {"inline_keyboard": rows}

def confirm_buttons(issue_id):
    return {"inline_keyboard": [[{"text": "📬 Confirm final draft", "callback_data": f"confirm:{issue_id}"}]]}

def _edit_here(text, kb=None, mid=None):
    """Change the message the user just tapped, in place. Falls back to a new message only if there is no message to edit."""
    mid = mid or getattr(_ctx, "mid", None)
    if not mid:
        return say(text, reply_markup=kb) if kb else say(text)
    api("editMessageText", chat_id=config.TELEGRAM_CHAT_ID, message_id=mid, text=text, parse_mode="HTML", disable_web_page_preview=True, **({"reply_markup": kb} if kb else {}))

CONFIRM_PROMPT = "When you are happy with the draft:"

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
        "\nReview each story below: <b>Keep</b> to tick it off, <b>Swap</b> to choose from 3 replacements, <b>Edit</b> or <b>🎙 Voice</b> to change the commentary, <b>🧠 Angles</b> for counter-arguments. "
        "Nothing is sent until you confirm at the bottom.")
    send_subject_options(issue)
    with db.conn() as c:
        for it in items:
            m = say(item_text(it, len(items)), reply_markup=item_buttons(it), disable_notification=True)
            db.run(c, "UPDATE issue_items SET tg_message_id=? WHERE id=?", (m["message_id"], it["id"]))
        db.run(c, "UPDATE issues SET status=CASE WHEN status='collecting' THEN 'drafted' ELSE status END WHERE id=?", (issue["id"],))
        db.log(c, "telegram_draft", f"issue {issue['id']} sent for review")
    cm = say(CONFIRM_PROMPT, reply_markup=confirm_buttons(issue["id"]), disable_notification=True)
    with db.conn() as c:
        db.kv_set(c, f"confirm_msg:{issue['id']}", str(cm["message_id"]))
        for it in items:
            db.run(c, "DELETE FROM kv WHERE k=?", (f"ui:{it['id']}",))     # a fresh draft starts with clean cards
    return {"issue_id": issue["id"], "stories": len(items)}

def reminder_buttons(issue_id):
    return {"inline_keyboard": [[{"text": "✅ Confirm current draft & schedule 8 AM send", "callback_data": f"confirm:{issue_id}"}],
                                [{"text": "⏭ Push deadline to Thursday 7 AM", "callback_data": f"push:{issue_id}"}]]}

def _unpin():
    with db.conn() as c:
        mid = db.kv_get(c, "pinned_reminder")
        if mid:
            db.run(c, "DELETE FROM kv WHERE k='pinned_reminder'")
    if mid:
        try:
            api("unpinChatMessage", chat_id=config.TELEGRAM_CHAT_ID, message_id=int(mid))
        except Exception:
            pass

def do_push(issue_id):
    """Quick action on the reminder: move the deadline to Thursday 7:00 AM IST. Nothing is sent in the meantime."""
    with db.conn() as c:
        iss = db.one(c, "SELECT * FROM issues WHERE id=?", (issue_id,))
        if iss["status"] != "drafted":
            return f"Issue is {iss['status']}."
        until = (datetime.strptime(iss["week"], "%Y-%m-%d") + timedelta(days=3, hours=7)).isoformat(timespec="minutes")
        db.kv_set(c, "snooze_until", until)
        db.run(c, "UPDATE issues SET reminder_sent=0 WHERE id=?", (issue_id,))
        db.log(c, "push", f"deadline pushed to {until}")
    _unpin()
    _edit_here("⏭ Deadline pushed to <b>Thursday 7:00 AM</b>. I'll nudge you again then. Nothing is sent until you confirm.")
    return "Deadline pushed to Thursday 7 AM."

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
    m = say("🚨 <b>The Dispatch is waiting on you.</b>\nThis week's draft is still unconfirmed. Nothing is emailed until you confirm.\n\n"
            "Tap <b>Confirm</b> to go to the final step, or push the deadline.", reply_markup=reminder_buttons(issue["id"]))
    try:        # escalation: the first message was silent; this one notifies and stays pinned until she acts
        api("pinChatMessage", chat_id=config.TELEGRAM_CHAT_ID, message_id=m["message_id"], disable_notification=False)
        with db.conn() as c:
            db.kv_set(c, "pinned_reminder", str(m["message_id"]))
    except Exception:
        pass
    return {"reminded": issue["id"]}

# ---------------- actions ----------------
def _refresh(it_id):
    with db.conn() as c:
        it = db.one(c, """SELECT i.*, a.title, a.url, a.source, a.snippet FROM issue_items i JOIN articles a ON a.id=i.article_id WHERE i.id=?""", (it_id,))
        total = db.one(c, "SELECT COUNT(*) AS n FROM issue_items WHERE issue_id=? AND kind='selected'", (it["issue_id"],))["n"]
        ui = _ui(c, it_id)
        fus = []
        if ui.get("angles"):
            fus = [f for f in json.loads(db.one(c, "SELECT fusions FROM issues WHERE id=?", (it["issue_id"],))["fusions"] or "[]") if it["position"] in (f["a"], f["b"])]
    if it["tg_message_id"]:
        api("editMessageText", chat_id=config.TELEGRAM_CHAT_ID, message_id=it["tg_message_id"], text=item_text(it, total, ui, fus),
            parse_mode="HTML", disable_web_page_preview=True, reply_markup=item_buttons(it, ui))

def _busy(item_id, msg):
    """Show 'working on it' on the card itself while Gemini runs."""
    with db.conn() as c:
        _ui_set(c, item_id, busy=msg)
    _refresh(item_id)

def _unbusy(item_id, **kw):
    with db.conn() as c:
        _ui_set(c, item_id, busy=None, **kw)

def _locked(c, issue_id):
    return db.one(c, "SELECT status FROM issues WHERE id=?", (issue_id,))["status"] in ("approved", "sending", "sent")

def _top_backups(c, issue_id, n=3):
    return db.all(c, """SELECT i.*, a.title, a.url, a.source, a.snippet FROM issue_items i JOIN articles a ON a.id=i.article_id
                        WHERE i.issue_id=? AND i.kind='backup' ORDER BY i.position LIMIT ?""", (issue_id, n))

def do_swap_menu(item_id):
    """Quick-swap carousel: the top 3 runner-ups with pre-drafted commentary, shown in place of the story. Pick one, or keep the original."""
    from concurrent.futures import ThreadPoolExecutor
    with db.conn() as c:
        old = db.one(c, "SELECT * FROM issue_items WHERE id=?", (item_id,))
        if not old or old["kind"] != "selected":
            return "That story is no longer in the draft."
        if _locked(c, old["issue_id"]):
            return "Draft is already confirmed. Reopen it first."
        bks = _top_backups(c, old["issue_id"])
        sg = styleguide.active(c)
    if not bks:
        return "No runner-ups left."
    need = [b for b in bks if not b["commentary"]]
    if need:        # older drafts, or runner-ups beyond the pre-drafted ones
        with ThreadPoolExecutor(3) as ex:
            got = list(ex.map(lambda b: select_stories.draft_one(sg, {"title": b["title"], "source": b["source"], "snippet": b["snippet"], "selection_filter": b["selection_filter"]}, fast=True), need))
        with db.conn() as c:
            for b, (t, _) in zip(need, got):
                db.run(c, "UPDATE issue_items SET commentary=?, draft_original=? WHERE id=?", (t, t, b["id"])); b["commentary"] = t
    L = "ABC"
    text = f"🔄 <b>Swap story {old['position']}</b>: choose a replacement\n\n" + "\n\n".join(
        f"<b>{L[i]})</b> <a href=\"{h(b['url'])}\">{h(b['title'])}</a> ({h(b['source'])}) · {h(b['topic'] or '')}{access_line(b)}\n{h(b['commentary'])}" for i, b in enumerate(bks))
    kb = [[{"text": f"Select {L[i]}", "callback_data": f"pick:{item_id}:{b['id']}"} for i, b in enumerate(bks)], [{"text": "↩️ Keep original", "callback_data": f"back:{item_id}"}]]
    api("editMessageText", chat_id=config.TELEGRAM_CHAT_ID, message_id=old["tg_message_id"], text=text, parse_mode="HTML", disable_web_page_preview=True, reply_markup={"inline_keyboard": kb})
    return "Pick a replacement."

def do_swap_pick(item_id, bid):
    with db.conn() as c:
        old = db.one(c, "SELECT * FROM issue_items WHERE id=?", (item_id,))
        bk = db.one(c, "SELECT * FROM issue_items WHERE id=? AND kind='backup'", (bid,))
        if not old or old["kind"] != "selected" or not bk or bk["issue_id"] != old["issue_id"]:
            return "That option is no longer available."
        if _locked(c, old["issue_id"]):
            return "Draft is already confirmed. Reopen it first."
        db.run(c, """UPDATE issue_items SET kind='selected', position=?, draft_original=commentary, flags=NULL, reviewed=0, tg_message_id=? WHERE id=?""",
               (old["position"], old["tg_message_id"], bk["id"]))
        db.run(c, "UPDATE issue_items SET kind='swapped_out', tg_message_id=NULL WHERE id=?", (old["id"],))
        db.run(c, "UPDATE articles SET status='new' WHERE id=?", (old["article_id"],))
        db.run(c, "UPDATE articles SET status='selected' WHERE id=?", (bk["article_id"],))
        db.log(c, "swap", f"item {old['id']} -> backup {bk['id']} (carousel)")
    _refresh(bk["id"])
    return "Swapped."

def do_back(item_id):
    _refresh(item_id)
    return "Kept the original."

def show_angles(item_id):
    """Devil's advocate prompts for one story, shown on the card itself and toggled by the same button."""
    with db.conn() as c:
        it = db.one(c, "SELECT counter, position FROM issue_items WHERE id=?", (item_id,))
        u = _ui(c, item_id)
        if not json.loads(it["counter"] or "[]") and not u.get("angles"):
            return "No angles were generated for this story."
        _ui_set(c, item_id, angles=not u.get("angles"))
    _refresh(item_id)
    return "Angles sent."

def _subject_view(issue):
    opts = json.loads(issue.get("subject_options") or "[]")
    L = "ABC"
    cur = issue.get("subject")
    text = "📨 <b>Subject line</b> (A is used unless you pick another)\n\n" + "\n\n".join(
        f"<b>{L[i]})</b> {h(o['subject'])} {'✅' if o['subject'] == cur else ''}\n<i>{h(o['preheader'])}</i> · {o['style'].lower()}" for i, o in enumerate(opts))
    kb = {"inline_keyboard": [[{"text": f"{'✅ ' if o['subject'] == cur else ''}Use {L[i]}", "callback_data": f"subj:{issue['id']}:{i}"} for i, o in enumerate(opts)]]}
    return text, kb

def send_subject_options(issue):
    if not json.loads(issue.get("subject_options") or "[]"):
        return
    text, kb = _subject_view(issue)
    say(text, reply_markup=kb, disable_notification=True)

def do_subject(issue_id, idx):
    with db.conn() as c:
        iss = db.one(c, "SELECT * FROM issues WHERE id=?", (issue_id,))
        if iss["status"] in ("approved", "sending", "sent"):
            return "Draft is already confirmed. Reopen it first."
        opts = json.loads(iss["subject_options"] or "[]")
        if idx >= len(opts):
            return "Unknown option."
        db.run(c, "UPDATE issues SET subject=?, preheader=? WHERE id=?", (opts[idx]["subject"], opts[idx]["preheader"], issue_id))
        db.log(c, "subject", opts[idx]["subject"])
        iss = db.one(c, "SELECT * FROM issues WHERE id=?", (issue_id,))
    text, kb = _subject_view(iss)
    _edit_here(text, kb)
    return f"Subject set: {opts[idx]['subject'][:60]}"

TUNES = {0: "Make it a notch spicier and more opinionated: a sharper claim and a dry edge. Stay inside the hard voice rules.",
         1: "Bring in the unit-economics angle (margins, cost to serve, working capital, CAC, cash burn). State ONLY economics that the article text itself states: its figures, ratios and named costs. If the text gives none, do not assert any: say which number would settle the question (for example the cost of acquiring a customer, or margin per order). Never claim a margin, cost or growth rate the article does not give.",
         2: "Rewrite in exactly 2 sentences, keeping the sharpest claim and the closer."}

def do_tune(item_id, kind):
    """One-tap micro-tuning of the current commentary. Gemini rewrites it; 'Back to Gemini's original' restores the first draft."""
    with db.conn() as c:
        it = db.one(c, "SELECT i.*, a.title, a.source, a.snippet FROM issue_items i JOIN articles a ON a.id=i.article_id WHERE i.id=?", (item_id,))
        if not it or it["kind"] != "selected":
            return "That story is no longer in the draft."
        if _locked(c, it["issue_id"]):
            return "Draft is already confirmed. Reopen it first."
        sg = styleguide.active(c)
    story = {"title": it["title"], "source": it["source"], "snippet": it["snippet"], "selection_filter": it["selection_filter"], "body": it.get("source_text") or ""}
    _busy(item_id, ("Making it spicier…", "Bringing in the unit economics…", "Trimming to 2 sentences…")[kind])
    try:
        text, errs = select_stories.draft_one(sg, story, instruction=f"Current version: \"{it['commentary']}\". {TUNES[kind]}", fast=True)
        with db.conn() as c:
            db.run(c, "UPDATE issue_items SET commentary=?, flags=? WHERE id=?", (text, "; ".join(errs), item_id))
            db.log(c, "tune", f"item {item_id} kind {kind}")
    finally:
        _unbusy(item_id)
    _refresh(item_id)
    return "Rewritten."

def do_reset(item_id):
    with db.conn() as c:
        it = db.one(c, "SELECT * FROM issue_items WHERE id=?", (item_id,))
        if _locked(c, it["issue_id"]):
            return "Draft is already confirmed. Reopen it first."
        db.run(c, "UPDATE issue_items SET commentary=draft_original, flags=NULL WHERE id=?", (item_id,))
    _refresh(item_id)
    return "Restored original."

def do_keep(item_id):
    with db.conn() as c:
        db.run(c, "UPDATE issue_items SET reviewed=1 WHERE id=?", (item_id,))
    _refresh(item_id)
    return "Kept."

def do_clear(item_id):
    with db.conn() as c:
        _ui_set(c, item_id, mode=None, qa=None, heard=None, busy=None, err=None)
    _refresh(item_id)
    return "Cleared."

def ask_edit(item_id):
    """The card itself asks for the edit: nothing new appears at the bottom of the chat."""
    with db.conn() as c:
        it = db.one(c, "SELECT * FROM issue_items WHERE id=?", (item_id,))
        if _locked(c, it["issue_id"]):
            return "Draft is already confirmed. Reopen it first."
        _ui_set(c, item_id, mode="edit", qa=None, heard=None)
    _refresh(item_id)
    return "Reply to the prompt below."

def apply_edit(item_id, text, source="edit"):
    """Writes Shreya's version of a story's commentary and records (draft, edit) so the voice can learn from it."""
    with db.conn() as c:
        it = db.one(c, "SELECT * FROM issue_items WHERE id=?", (item_id,))
        if _locked(c, it["issue_id"]):
            return False
        db.run(c, "INSERT INTO edits (article_id, gemini_draft, shreya_edit, created_at) VALUES (?,?,?,?)",
               (it["article_id"], it["draft_original"] or it["commentary"], text.strip(), config.now_ist().isoformat(timespec="seconds")))
        db.run(c, "UPDATE issue_items SET commentary=?, edited=1, reviewed=1, flags=NULL WHERE id=?", (text.strip(), it["id"]))
        db.log(c, source, f"item {it['id']}")
        _ui_set(c, item_id, mode=None, busy=None)
    _refresh(it["id"])
    return True

def _tidy(m):
    """Remove her reply from the chat so the whole exchange lives on the card."""
    try:
        api("deleteMessage", chat_id=config.TELEGRAM_CHAT_ID, message_id=m["message_id"])
    except Exception:
        pass

def _card_of(m):
    """The story card a message replies to, or None."""
    rep = (m.get("reply_to_message") or {}).get("message_id")
    if not rep:
        return None
    with db.conn() as c:
        return db.one(c, "SELECT i.id, i.issue_id FROM issue_items i WHERE i.tg_message_id=? AND i.kind='selected'", (rep,))

def ask_voice(item_id):
    with db.conn() as c:
        it = db.one(c, "SELECT * FROM issue_items WHERE id=?", (item_id,))
        if _locked(c, it["issue_id"]):
            return "Draft is already confirmed. Reopen it first."
        _ui_set(c, item_id, mode="voice", qa=None, heard=None, err=None)
    _refresh(item_id)
    return "Reply with a voice note."

def handle_voice(m):
    card = _card_of(m)
    if not card:
        say("To add a voice comment, tap <b>🎙 Voice</b> on a story, then reply <i>to that story card</i> with a voice note.", disable_notification=True)
        return
    v = m.get("voice") or m.get("audio")
    if (v.get("duration") or 0) > 90:
        say("That note is over 90 seconds. Try a shorter one, around 10 to 20 seconds.", disable_notification=True); return
    item_id = card["id"]
    with db.conn() as c:
        it = db.one(c, "SELECT i.*, a.title, a.source, a.snippet FROM issue_items i JOIN articles a ON a.id=i.article_id WHERE i.id=?", (item_id,))
        sg = styleguide.active(c)
        if _locked(c, it["issue_id"]):
            say("Draft is already confirmed. Reopen it first to edit.", disable_notification=True); return
    _busy(item_id, "Listening to your voice note…")
    try:
        fi = api("getFile", file_id=v["file_id"])
        audio = _client.get(f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/{fi['file_path']}").content
        text, transcript, errs = select_stories.voice_to_commentary(sg, it, audio, v.get("mime_type") or "audio/ogg")
    except Exception as e:
        with db.conn() as c:
            db.log(c, "tg_error", f"voice: {type(e).__name__}: {str(e)[:200]}")
        _unbusy(item_id, mode="voice", err="I couldn't process that voice note. Reply to this card with it again.")
        _refresh(item_id); return
    _tidy(m)
    if not text:
        _unbusy(item_id, mode="voice", err="I couldn't make out the voice note. Try again a little closer to the mic.")
        _refresh(item_id); return
    apply_edit(item_id, text, "voice")
    with db.conn() as c:
        _ui_set(c, item_id, heard=transcript, mode=None, busy=None, err=None)
    _refresh(item_id)

def ask_confirm(issue_id):
    with db.conn() as c:
        iss = db.one(c, "SELECT * FROM issues WHERE id=?", (issue_id,))
        if iss["status"] in ("approved", "sending", "sent"):
            return f"Already {iss['status']}."
        items = items_of(c, issue_id)
        subs = db.one(c, "SELECT COUNT(*) AS n FROM subscribers WHERE status='active'")["n"]
    pending = sum(1 for i in items if not i["reviewed"])
    _edit_here(f"Send this issue to <b>{subs}</b> subscribers on Thursday morning?\n"
               + (f"({pending} stories not yet ticked with Keep.)\n" if pending else "") + "This is the final confirmation.",
               {"inline_keyboard": [[{"text": "✅ Yes, send Thursday", "callback_data": f"yes:{issue_id}"}, {"text": "Cancel", "callback_data": f"no:{issue_id}"}]]})
    return "Please confirm below."

def do_cancel_confirm(issue_id):
    """Cancel on the final step: the same message goes back to what it was (the draft's confirm bar, or the reminder)."""
    mid = getattr(_ctx, "mid", None)
    with db.conn() as c:
        cm = db.kv_get(c, f"confirm_msg:{issue_id}")
    if cm and mid and int(cm) == int(mid):
        _edit_here(CONFIRM_PROMPT, confirm_buttons(issue_id))
    else:
        _edit_here("🚨 <b>The Dispatch is waiting on you.</b>\nThis week's draft is still unconfirmed. Nothing is emailed until you confirm.", reminder_buttons(issue_id))
    return "Cancelled. Nothing will be sent."

def do_confirm(issue_id):
    with db.conn() as c:
        iss = db.one(c, "SELECT * FROM issues WHERE id=?", (issue_id,))
        if iss["status"] != "drafted":
            return f"Issue is {iss['status']}."
        db.run(c, "UPDATE issues SET status='approved', approved_at=? WHERE id=?", (config.now_ist().isoformat(timespec="seconds"), issue_id))
        db.log(c, "approved", f"issue {issue_id}")
    _unpin()
    from app import pipeline
    msg = pipeline.on_approved(issue_id)
    _edit_here("✅ <b>Confirmed.</b> " + msg, {"inline_keyboard": [[{"text": "↩️ Reopen draft", "callback_data": f"reopen:{issue_id}"}]]})
    try:
        post_group_confirmed(issue_id)
    except Exception as e:
        with db.conn() as c:
            db.log(c, "tg_error", f"group post failed: {str(e)[:200]}")
    return "Confirmed."

def do_reopen(issue_id):
    with db.conn() as c:
        iss = db.one(c, "SELECT * FROM issues WHERE id=?", (issue_id,))
        if iss["status"] != "approved":
            return f"Cannot reopen, issue is {iss['status']}."
        db.run(c, "UPDATE issues SET status='drafted', approved_at=NULL WHERE id=?", (issue_id,))
    _edit_here("↩️ Draft reopened. Nothing will be sent until you confirm again.", confirm_buttons(issue_id))
    try:
        say_group("↩️ <b>Reopened for changes.</b> The confirmed draft above is withdrawn until it is confirmed again.", disable_notification=True)
    except Exception:
        pass
    return "Reopened."

# ---------------- the group: every confirmed edition, dated ----------------
def group_id():
    with db.conn() as c:
        return db.kv_get(c, "archive_chat_id")

def say_group(text, **kw):
    gid = group_id()
    if not gid:
        return None
    return api("sendMessage", chat_id=int(gid), text=text, parse_mode="HTML", disable_web_page_preview=True, **kw)

def post_group_confirmed(issue_id):
    """When the final draft is confirmed, post the whole edition in the group: a dated heading, then the stories with Shreya's take on each."""
    if not group_id():
        return {"skipped": "no group registered"}
    with db.conn() as c:
        iss = db.one(c, "SELECT * FROM issues WHERE id=?", (issue_id,))
        if db.kv_get(c, f"group_posted:{issue_id}") == iss["approved_at"]:
            return {"skipped": "already posted"}
        items = items_of(c, issue_id)
        subs = db.one(c, "SELECT COUNT(*) AS n FROM subscribers WHERE status='active'")["n"]
    from app.email_template import send_date
    when = send_date(iss["week"])
    appr = datetime.fromisoformat(iss["approved_at"])
    head = (f"📰 <b>The Dispatch · Edition of {when.strftime('%A %-d %B %Y')}</b>\n"
            f"✅ Confirmed · {appr.strftime('%a %-d %b, %-I:%M %p')} IST\n"
            f"📨 Subject: <b>{h(iss.get('subject') or 'The Dispatch')}</b>\n"
            f"🗓 Goes out {when.strftime('%a %-d %b, %-I:%M %p')} IST · {len(items)} stories · {subs} subscribers")
    m = say_group(head, disable_notification=False)
    try:
        api("pinChatMessage", chat_id=int(group_id()), message_id=m["message_id"], disable_notification=True)
    except Exception:
        pass
    blocks = [f"<b>{i['position']}. {h(i['topic'] or '')}</b>  ·  <a href=\"{h(i['url'])}\">{h(i['title'])}</a> ({h(i['source'])})\n<i>{h(i['commentary'] or '')}</i>" for i in items]
    chunk = ""
    for b in blocks:
        if len(chunk) + len(b) > 3700:
            say_group(chunk, disable_notification=True); chunk = ""
        chunk += ("\n\n" if chunk else "") + b
    if chunk:
        say_group(chunk, disable_notification=True)
    with db.conn() as c:
        db.kv_set(c, f"group_posted:{issue_id}", iss["approved_at"])
        db.log(c, "group_post", f"issue {issue_id} posted to the group")
    return {"posted": len(items)}

# ---------------- Ask Gemini: questions about a story, answered from her own archive ----------------
def ask_about_story(item_id, question):
    """Her question and Gemini's answer appear on the story card, not as new messages."""
    from app import gemini
    _busy(item_id, "Checking the archive…")
    try:
        with db.conn() as c:
            it = db.one(c, """SELECT i.*, a.title, a.source, a.snippet, a.url FROM issue_items i JOIN articles a ON a.id=i.article_id WHERE i.id=?""", (item_id,))
            past = db.all(c, """SELECT s.week, a.title, i.entities FROM issue_items i JOIN issues s ON s.id=i.issue_id JOIN articles a ON a.id=i.article_id
                                WHERE i.kind='selected' AND s.week IN (SELECT week FROM issues ORDER BY week DESC LIMIT 6) ORDER BY s.week DESC""")
            pool = db.all(c, "SELECT title, source FROM articles WHERE week=? ORDER BY published_at DESC LIMIT 600", (config.week_start(),))
        names = {e["name"] for e in json.loads(it["entities"] or "[]")} | set(re.findall(r"\b[A-Z][A-Za-z0-9&]{2,}\b", question))
        low = [n.lower() for n in names if len(n) > 2]
        hit = lambda t: any(n in t.lower() for n in low)
        arch = [f"- {p['week']}: {p['title']}" for p in past if hit(p["title"] + " " + (p["entities"] or ""))][:8]
        inpool = [f"- {p['title']} ({p['source']})" for p in pool if hit(p["title"])][:8]
        ctx = (f"THIS STORY: {it['title']} ({it['source']})\nSnippet: {it['snippet'] or '(none)'}\nArticle text: {(it['source_text'] or '')[:1500] or '(not extracted)'}\nHer commentary draft: {it['commentary']}\n\n"
               f"EARLIER ISSUES that mention these names or topics:\n" + ("\n".join(arch) or "(none found)") + "\n\nTHIS WEEK'S ARTICLE POOL mentioning them:\n" + ("\n".join(inpool) or "(none found)"))
        ans = gemini.generate("You are Shreya's research assistant for The Dispatch. Answer ONLY from the context given. Two sentences at most. "
                              "If the context does not contain the answer, say exactly what is missing instead of guessing; never invent figures, valuations or dates.",
                              f"{ctx}\n\nQUESTION: {question}", None, 0.2, True)
    finally:
        _unbusy(item_id)
    with db.conn() as c:
        _ui_set(c, item_id, qa={"q": question[:300], "a": ans.strip()}, angles=None)
    _refresh(item_id)

# ---------------- /add: a story she found, straight into this week's pool ----------------
URL_RE = re.compile(r"https?://[^\s<>]+")
ADD_SCHEMA = {"type": "OBJECT", "properties": {"signal": {"type": "INTEGER"}, "filter": {"type": "STRING", "enum": select_stories.FILTERS + ["NONE"]},
              "topic": {"type": "STRING", "enum": select_stories.TOPICS}, "in_scope": {"type": "BOOLEAN"}, "reason": {"type": "STRING"}}, "required": ["signal", "filter", "topic", "in_scope", "reason"]}

def add_url(url):
    from app import readable, ingest, gemini
    got = readable.extract(url)
    if not got or not (got["title"] or got["description"]):
        say(f"I couldn't read that page ({h(url[:60])}). It may be behind a login or paywall. Paste the headline and a line of context and I'll add it by hand."); return
    final = got["final_url"]
    title = (got["title"] or final)[:300]
    snippet = (got["description"] or got["text"])[:500]
    with db.conn() as c:
        if db.one(c, "SELECT id FROM articles WHERE url_hash=?", (ingest.url_hash(final),)):
            say("That story is already in the pool."); return
        sg = styleguide.active(c)
        issue = db.one(c, "SELECT status FROM issues WHERE week=?", (config.week_start(),))
    ev = gemini.generate("You are the editorial selector for The Dispatch.",
        f"FILTERS:\n{sg['filters']}\n\nRate this story that Shreya found herself. signal 0-100 (how strongly it passes at least one filter), the best filter or NONE, topic sector, "
        f"in_scope (is it about India's startup / tech / business ecosystem), and a one-sentence reason.\nTitle: {title}\nText: {got['text'][:1200] or snippet}", ADD_SCHEMA, 0.2, True)
    with db.conn() as c:
        db.insert(c, """INSERT INTO articles (url_hash, url, title, source, snippet, published_at, fetched_at, week, fingerprint, topic, status, signal, signal_filter)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (ingest.url_hash(final), ingest.canon(final), title, "Added by Shreya", snippet, config.now_ist().isoformat(timespec="seconds"),
                        config.now_ist().isoformat(timespec="seconds"), config.week_start(), ingest.fingerprint(title), ev["topic"], "new", max(0, min(100, int(ev["signal"]))), ev["filter"]))
        db.log(c, "quick_add", title[:120])
    warn = "" if ev["in_scope"] and ev["signal"] >= 50 else "\n⚠️ Gemini rates this lower than usual, but it is in the pool because you chose it."
    when = ("The draft already exists, so it will be considered if the editorial pass is re-run." if issue else "It is in Wednesday's candidate pool and will be preferred as a hand-picked story.")
    say(f"✅ <b>Added:</b> {h(title[:120])}\nSignal {ev['signal']}/100 · {h(ev['topic'])} · {h(ev['filter'].lower())}\n<i>{h(ev['reason'])}</i>{warn}\n\n{when}")

# ---------------- update router ----------------
SUCCESS_NOTES = {"Kept.", "Pick a replacement.", "Swapped.", "Kept the original.", "Rewritten.", "Restored original.", "Reply to the prompt below.", "Reply with a voice note.",
                 "Angles sent.", "Please confirm below.", "Confirmed.", "Reopened.", "Cancelled. Nothing will be sent.", "Deadline pushed to Thursday 7 AM.", "Cleared."}

def _first_delivery(uid):
    """Telegram re-delivers an update when a webhook is slow or errors. Each update_id is processed once."""
    import time
    with db.conn() as c:
        cur = db.run(c, "INSERT INTO kv (k, v) VALUES (?,?) ON CONFLICT(k) DO NOTHING", (f"upd:{uid}", str(int(time.time()))))
        if uid % 40 == 0:        # housekeeping: forget updates older than a day
            db.run(c, "DELETE FROM kv WHERE k LIKE ? AND CAST(v AS BIGINT) < ?", ("upd:%", int(time.time()) - 86400))
        return cur.rowcount == 1

def handle_update(u):
    """Never raises: a failure is logged and reported in the chat, and the webhook still answers 200 so Telegram does not retry."""
    uid = u.get("update_id")
    try:
        if isinstance(uid, int) and not _first_delivery(uid):
            return
        _handle(u)
    except Exception as e:
        try:
            with db.conn() as c:
                db.log(c, "tg_error", f"{type(e).__name__}: {str(e)[:300]}")
        except Exception:
            pass
        try:
            say(f"⚠️ Something went wrong with that tap ({h(type(e).__name__)}). Please try again.", disable_notification=True)
        except Exception:
            pass

def _handle(u):
    if "callback_query" in u:
        q = u["callback_query"]
        if str(q["message"]["chat"]["id"]) != str(config.TELEGRAM_CHAT_ID):
            return
        try:        # acknowledge immediately: the button stops spinning at once, whatever the work behind it takes
            api("answerCallbackQuery", callback_query_id=q["id"])
        except Exception:
            pass    # stale or duplicate tap: carry on, the action itself is still valid
        parts = q["data"].split(":")
        act, args = parts[0], [int(x) for x in parts[1:] if x.lstrip("-").isdigit()]
        fn = {"keep": do_keep, "tune": do_tune, "reset": do_reset, "swap": do_swap_menu, "pick": do_swap_pick, "back": do_back, "edit": ask_edit, "voice": ask_voice, "ang": show_angles, "subj": do_subject, "clear": do_clear,
              "confirm": ask_confirm, "push": do_push, "yes": do_confirm, "reopen": do_reopen, "no": do_cancel_confirm}.get(act)
        if act in ("keep", "tune", "reset", "swap", "pick", "back", "edit", "voice", "ang", "clear") and args:
            with db.conn() as c:
                alive = db.one(c, "SELECT id FROM issue_items WHERE id=? AND kind='selected'", (args[0],))
            if not alive:           # an old card whose draft was regenerated: say so instead of failing
                say("ℹ️ That card belongs to an older draft. Send /draft to get the current one.", disable_notification=True)
                return
        _ctx.mid = q["message"]["message_id"]
        note = fn(*args) if fn else "Unknown action."
        if note and note not in SUCCESS_NOTES and not note.startswith("Subject set"):
            say("ℹ️ " + h(note), disable_notification=True)         # the tap could not be applied: say why instead of failing silently
        return
    m = u.get("message")
    if not m:
        return
    chat = m["chat"]
    if chat.get("type") in ("group", "supergroup"):
        # The archive group. Only Shreya can register it, and only with /setgroup sent from inside the group.
        txt = (m.get("text") or "").strip()
        if txt.startswith("/setgroup") and str((m.get("from") or {}).get("id")) == str(config.TELEGRAM_CHAT_ID):
            with db.conn() as c:
                db.kv_set(c, "archive_chat_id", str(chat["id"]))
                db.log(c, "group_registered", str(chat.get("title", ""))[:80])
            api("sendMessage", chat_id=chat["id"], parse_mode="HTML",
                text="✅ <b>This group is now The Dispatch's archive.</b>\nEvery time you confirm a final draft, the whole edition is posted here with its date, then a note when it goes out.")
            with db.conn() as c:       # if a draft was already confirmed this week, post it now
                issue = db.one(c, "SELECT id, status FROM issues WHERE week=?", (config.week_start(),))
            if issue and issue["status"] in ("approved", "sending", "sent"):
                post_group_confirmed(issue["id"])
        return
    if str(chat["id"]) != str(config.TELEGRAM_CHAT_ID):
        return
    if m.get("voice") or m.get("audio"):
        try:
            handle_voice(m)
        except Exception as e:
            with db.conn() as c:
                db.log(c, "tg_error", f"voice: {type(e).__name__}: {str(e)[:200]}")
            say(f"Sorry, that voice note failed: {h(str(e)[:120])}", disable_notification=True)
        return
    text = (m.get("text") or "").strip()
    if m.get("reply_to_message") and text and not text.startswith("/"):
        card = _card_of(m)
        if card:
            with db.conn() as c:
                mode = _ui(c, card["id"]).get("mode")
            if mode == "edit":          # she tapped Edit on this card: her reply IS the new commentary
                ok = apply_edit(card["id"], text)
                _tidy(m)
                if not ok:
                    say("Draft is already confirmed. Reopen it first to edit.", disable_notification=True)
            else:                       # any other reply to a card is a question for Gemini; the answer lands on the card
                _tidy(m)
                try:
                    ask_about_story(card["id"], text)
                except Exception as e:
                    with db.conn() as c:
                        db.log(c, "tg_error", f"ask: {type(e).__name__}: {str(e)[:200]}")
                    say(f"Sorry, I couldn't answer that: {h(str(e)[:100])}", disable_notification=True)
            return
    if text.startswith("/add") or (URL_RE.fullmatch(text) if text else False):
        urls = URL_RE.findall(text)
        if not urls:
            say("Send <code>/add https://link</code>, or just share a link with me."); return
        for u in urls[:3]:
            try:
                add_url(u.rstrip(").,"))
            except Exception as e:
                say(f"Couldn't add that one: {h(str(e)[:100])}")
        return
    if text.startswith("/draft"):
        send_draft()
    elif text.startswith("/status"):
        with db.conn() as c:
            i = db.one(c, "SELECT * FROM issues ORDER BY week DESC LIMIT 1")
            n = db.one(c, "SELECT COUNT(*) AS n FROM articles WHERE week=?", (config.week_start(),))["n"]
        say(f"Week {config.week_start()}: {n} articles collected. Issue: <b>{i['status'] if i else 'not drafted yet'}</b>.")
    else:
        say("I'm The Dispatch bot. I send you the weekly draft on Wednesday evening.\n/draft resend the current draft\n/status pipeline status\n/add &lt;link&gt; add a story you found to this week's pool (or just share a link)\nReply to any story card with a question and I'll answer from the archive.")
