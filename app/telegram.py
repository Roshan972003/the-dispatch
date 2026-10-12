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
                                 {"text": "🧠 Angles", "callback_data": f"ang:{it['id']}"}]]}

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
        reply_markup={"inline_keyboard": [[{"text": f"Use {L[i]}", "callback_data": f"subj:{issue['id']}:{i}"} for i in range(len(opts))]]})

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
        parts = q["data"].split(":")
        act, args = parts[0], [int(x) for x in parts[1:] if x.lstrip("-").isdigit()]
        fn = {"keep": do_keep, "swap": do_swap_menu, "pick": do_swap_pick, "back": do_back, "edit": ask_edit, "voice": ask_voice, "ang": show_angles, "subj": do_subject,
              "confirm": ask_confirm, "yes": do_confirm, "reopen": do_reopen, "no": lambda a: "Cancelled. Nothing will be sent."}.get(act)
        slow = act in ("swap", "voice")     # may call Gemini or Telegram files: acknowledge the tap first so the button stops spinning
        if slow:
            api("answerCallbackQuery", callback_query_id=q["id"], text="One moment…")
        try:
            note = fn(*args) if fn else "Unknown action."
        except Exception as e:
            note = f"Error: {str(e)[:150]}"
        if not slow:
            api("answerCallbackQuery", callback_query_id=q["id"], text=note)
        elif note not in ("Pick a replacement.", "Reply with a voice note."):
            say(note)
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
    if text.startswith("/draft"):
        send_draft()
    elif text.startswith("/status"):
        with db.conn() as c:
            i = db.one(c, "SELECT * FROM issues ORDER BY week DESC LIMIT 1")
            n = db.one(c, "SELECT COUNT(*) AS n FROM articles WHERE week=?", (config.week_start(),))["n"]
        say(f"Week {config.week_start()}: {n} articles collected. Issue: <b>{i['status'] if i else 'not drafted yet'}</b>.")
    else:
        say("I'm The Dispatch bot. I send you the weekly draft on Wednesday evening.\n/draft resend the current draft\n/status pipeline status")
