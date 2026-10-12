"""Telegram review loop. Shreya reviews the draft story by story (Keep / Swap / Edit), then confirms.
Only TELEGRAM_CHAT_ID is obeyed. Nothing is ever emailed from here without an explicit two-step confirmation."""
import json, re
from datetime import datetime, timedelta
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

def access_line(it):
    tag = {"free": "🟢 free access", "soft": "🟡 soft paywall", "hard": "🔴 hard paywall", "dead": "🔴 link looks dead"}.get(it.get("access"))
    if not tag:
        return ""
    alt = f" · free coverage: <a href=\"{h(it['alt_url'])}\">{h(it['alt_source'])}</a>" if it.get("alt_url") and it.get("access") in ("soft", "hard", "dead") else ""
    return f"\n{tag}{alt}"

def item_text(it, total):
    mark = "✅ " if it["reviewed"] else ""
    edited = " · ✏️ edited" if it["edited"] else ""
    warn = f"\n⚠️ <i>Auto-check: {h(it['flags'])}</i>" if it.get("flags") else ""
    return (f"{mark}<b>{it['position']}/{total} · {h(it['topic'] or '')}</b> · <i>{h((it['selection_filter'] or '').lower())}</i>{edited}\n"
            f"<a href=\"{h(it['url'])}\">{h(it['title'])}</a> ({h(it['source'])}){access_line(it)}\n\n{h(it['commentary'] or '')}{warn}")

def item_buttons(it):
    return {"inline_keyboard": [[{"text": "✅ Keep", "callback_data": f"keep:{it['id']}"},
                                 {"text": "🔄 Swap", "callback_data": f"swap:{it['id']}"},
                                 {"text": "✏️ Edit", "callback_data": f"edit:{it['id']}"}],
                                [{"text": "🎙 Voice", "callback_data": f"voice:{it['id']}"},
                                 {"text": "🧠 Angles", "callback_data": f"ang:{it['id']}"}],
                                [{"text": "🔥 Spicier", "callback_data": f"tune:{it['id']}:0"},
                                 {"text": "📊 Unit economics", "callback_data": f"tune:{it['id']}:1"},
                                 {"text": "✂️ Trim to 2 lines", "callback_data": f"tune:{it['id']}:2"}]]
            + ([[{"text": "↩️ Back to Gemini's original", "callback_data": f"reset:{it['id']}"}]] if it.get("draft_original") and it.get("commentary") != it.get("draft_original") else [])}

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
        "\nReview each story below: <b>Keep</b> to tick it off, <b>Swap</b> to choose from 3 replacements, <b>Edit</b> or <b>🎙 Voice</b> to change the commentary, <b>🧠 Angles</b> for counter-arguments. "
        "Nothing is sent until you confirm at the bottom.")
    send_subject_options(issue)
    with db.conn() as c:
        for it in items:
            m = say(item_text(it, len(items)), reply_markup=item_buttons(it), disable_notification=True)
            db.run(c, "UPDATE issue_items SET tg_message_id=? WHERE id=?", (m["message_id"], it["id"]))
        db.run(c, "UPDATE issues SET status=CASE WHEN status='collecting' THEN 'drafted' ELSE status END WHERE id=?", (issue["id"],))
        db.log(c, "telegram_draft", f"issue {issue['id']} sent for review")
    say("When you are happy with the draft:", reply_markup=confirm_buttons(issue["id"]), disable_notification=True)
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
    say("⏭ Deadline pushed to <b>Thursday 7:00 AM</b>. I'll nudge you again then. Nothing is sent until you confirm.")
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
    if it["tg_message_id"]:
        api("editMessageText", chat_id=config.TELEGRAM_CHAT_ID, message_id=it["tg_message_id"], text=item_text(it, total),
            parse_mode="HTML", disable_web_page_preview=True, reply_markup=item_buttons(it))

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
            got = list(ex.map(lambda b: select_stories.draft_one(sg, {"title": b["title"], "source": b["source"], "snippet": b["snippet"], "selection_filter": b["selection_filter"]}), need))
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
    """Devil's advocate prompts for one story, plus any trend fusion that involves it. Framed as things to check, not facts."""
    with db.conn() as c:
        it = db.one(c, "SELECT i.*, a.title FROM issue_items i JOIN articles a ON a.id=i.article_id WHERE i.id=?", (item_id,))
        iss = db.one(c, "SELECT fusions FROM issues WHERE id=?", (it["issue_id"],))
    bullets = json.loads(it["counter"] or "[]")
    fus = [f for f in json.loads(iss["fusions"] or "[]") if it["position"] in (f["a"], f["b"])]
    if not bullets and not fus:
        return "No angles were generated for this story."
    text = f"🧠 <b>Angles for story {it['position']}</b>: things to check, not facts\n<i>{h(it['title'])}</i>\n\n" + "\n".join(f"• {h(b)}" for b in bullets)
    if fus:
        text += "\n\n🔗 <b>Connect it to</b>\n" + "\n".join(f"• story {f['b'] if f['a'] == it['position'] else f['a']}: {h(f['angle'])}" for f in fus)
    say(text)
    return "Angles sent."

def send_subject_options(issue):
    opts = json.loads(issue.get("subject_options") or "[]")
    if not opts:
        return
    L = "ABC"
    say("📨 <b>Subject line</b> (A is used unless you pick another)\n\n" + "\n\n".join(
        f"<b>{L[i]})</b> {h(o['subject'])}\n<i>{h(o['preheader'])}</i> · {o['style'].lower()}" for i, o in enumerate(opts)),
        reply_markup={"inline_keyboard": [[{"text": f"Use {L[i]}", "callback_data": f"subj:{issue['id']}:{i}"} for i in range(len(opts))]]}, disable_notification=True)

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
    return f"Subject set: {opts[idx]['subject'][:60]}"

TUNES = {0: "Make it a notch spicier and more opinionated: a sharper claim and a dry edge. Stay inside the hard voice rules.",
         1: "Bring in the unit-economics angle (margins, cost to serve, working capital, CAC). Use only numbers and facts present in the article text; if there are none, reason from structure and do not invent any.",
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
    text, errs = select_stories.draft_one(sg, story, instruction=f"Current version: \"{it['commentary']}\". {TUNES[kind]}")
    with db.conn() as c:
        db.run(c, "UPDATE issue_items SET commentary=?, flags=? WHERE id=?", (text, "; ".join(errs), item_id))
        db.log(c, "tune", f"item {item_id} kind {kind}")
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
    _refresh(it["id"])
    return True

def save_edit(prompt_msg_id, text):
    with db.conn() as c:
        raw = db.kv_get(c, f"edit_prompt:{prompt_msg_id}")
        if not raw:
            return False
        db.run(c, "DELETE FROM kv WHERE k=?", (f"edit_prompt:{prompt_msg_id}",))
    if not apply_edit(int(raw), text):
        say("Draft is already confirmed. Reopen it first to edit."); return True
    say("Saved. I'll learn from this edit.")
    return True

def ask_voice(item_id):
    with db.conn() as c:
        it = db.one(c, "SELECT * FROM issue_items WHERE id=?", (item_id,))
        if _locked(c, it["issue_id"]):
            return "Draft is already confirmed. Reopen it first."
    m = say(f"🎙 <b>Voice comment for story {it['position']}.</b> Reply to <i>this message</i> with a voice note: just say your raw take. "
            f"I'll turn it into 2 to 3 sharp lines in your voice.", reply_markup={"force_reply": True, "input_field_placeholder": "Hold the mic and speak"})
    with db.conn() as c:
        db.kv_set(c, f"voice_prompt:{m['message_id']}", str(item_id))
    return "Reply with a voice note."

def handle_voice(m):
    rep = (m.get("reply_to_message") or {}).get("message_id")
    with db.conn() as c:
        raw = db.kv_get(c, f"voice_prompt:{rep}") if rep else None
    if not raw:
        say("To add a voice comment, tap <b>🎙 Voice</b> under a story, then reply to my prompt with a voice note.")
        return
    v = m.get("voice") or m.get("audio")
    if (v.get("duration") or 0) > 90:
        say("That note is over 90 seconds. Try a shorter one, around 10 to 20 seconds."); return
    item_id = int(raw)
    with db.conn() as c:
        it = db.one(c, "SELECT i.*, a.title, a.source, a.snippet FROM issue_items i JOIN articles a ON a.id=i.article_id WHERE i.id=?", (item_id,))
        sg = styleguide.active(c)
        if _locked(c, it["issue_id"]):
            say("Draft is already confirmed. Reopen it first to edit."); return
        db.run(c, "DELETE FROM kv WHERE k=?", (f"voice_prompt:{rep}",))
    say("🎙 Got it. Turning your take into commentary…")
    fi = api("getFile", file_id=v["file_id"])
    audio = _client.get(f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/{fi['file_path']}").content
    text, transcript, errs = select_stories.voice_to_commentary(sg, it, audio, v.get("mime_type") or "audio/ogg")
    if not text:
        say("I could not make out the voice note. Try again a little closer to the mic."); return
    apply_edit(item_id, text, "voice")
    say(f"🎙 <b>Heard:</b> {h(transcript)}\n\n✍️ <b>Commentary saved:</b>\n{h(text)}" + (f"\n\n⚠️ <i>{h('; '.join(errs))}</i>" if errs else "") +
        "\n\nTap <b>🎙 Voice</b> again to redo it, or <b>Edit</b> to fine-tune.")

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
    _unpin()
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

# ---------------- Ask Gemini: questions about a story, answered from her own archive ----------------
def ask_about_story(item_id, question, reply_to):
    from app import gemini
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
                          f"{ctx}\n\nQUESTION: {question}", None, 0.2)
    say("🧠 " + h(ans.strip()), reply_to_message_id=reply_to)

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
        f"in_scope (is it about India's startup / tech / business ecosystem), and a one-sentence reason.\nTitle: {title}\nText: {got['text'][:1200] or snippet}", ADD_SCHEMA, 0.2)
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
                 "Angles sent.", "Please confirm below.", "Confirmed.", "Reopened.", "Cancelled. Nothing will be sent.", "Deadline pushed to Thursday 7 AM."}

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
        fn = {"keep": do_keep, "tune": do_tune, "reset": do_reset, "swap": do_swap_menu, "pick": do_swap_pick, "back": do_back, "edit": ask_edit, "voice": ask_voice, "ang": show_angles, "subj": do_subject,
              "confirm": ask_confirm, "push": do_push, "yes": do_confirm, "reopen": do_reopen, "no": lambda a: "Cancelled. Nothing will be sent."}.get(act)
        if act in ("keep", "tune", "reset", "swap", "pick", "back", "edit", "voice", "ang") and args:
            with db.conn() as c:
                alive = db.one(c, "SELECT id FROM issue_items WHERE id=? AND kind='selected'", (args[0],))
            if not alive:           # an old card whose draft was regenerated: say so instead of failing
                say("ℹ️ That card belongs to an older draft. Send /draft to get the current one.", disable_notification=True)
                return
        note = fn(*args) if fn else "Unknown action."
        if note and note not in SUCCESS_NOTES and not note.startswith("Subject set"):
            say("ℹ️ " + h(note), disable_notification=True)         # the tap could not be applied: say why instead of failing silently
        return
    m = u.get("message")
    if not m or str(m["chat"]["id"]) != str(config.TELEGRAM_CHAT_ID):
        return
    if m.get("voice") or m.get("audio"):
        try:
            handle_voice(m)
        except Exception as e:
            say(f"Sorry, that voice note failed: {h(str(e)[:120])}")
        return
    text = (m.get("text") or "").strip()
    if m.get("reply_to_message") and text and not text.startswith("/"):
        if save_edit(m["reply_to_message"]["message_id"], text):
            return
        with db.conn() as c:        # a reply to a story card that is not an edit prompt is a question for Gemini
            card = db.one(c, "SELECT id FROM issue_items WHERE tg_message_id=? AND kind='selected'", (m["reply_to_message"]["message_id"],))
        if card:
            try:
                ask_about_story(card["id"], text, m["message_id"])
            except Exception as e:
                say(f"Sorry, I couldn't answer that: {h(str(e)[:100])}")
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
