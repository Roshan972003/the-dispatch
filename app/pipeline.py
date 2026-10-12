"""Glue between approval and sending."""
from app import config, mailer

def on_approved(issue_id):
    """Called when Shreya confirms. Send now only if Thursday's send time has already passed; otherwise the Thursday cron sends."""
    from app import db
    with db.conn() as c:
        issue = db.one(c, "SELECT * FROM issues WHERE id=?", (issue_id,))
    when = mailer.send_date(issue["week"])
    if config.now_ist() >= when:
        res = mailer.send_issue(issue_id)
        return f"Thursday's send time had passed, so it is going out now: {res}"
    return f"It will go out {when.strftime('%A %-d %b, %-I:%M %p')} IST."

def thursday_send():
    """Cron, Thursday 08:00 IST. Never sends unless the issue was confirmed."""
    from app import db, telegram
    with db.conn() as c:
        issue = db.one(c, "SELECT * FROM issues WHERE week=?", (config.week_start(),))
    if not issue:
        return {"skipped": "no issue this week"}
    if issue["status"] in ("approved", "sending"):
        from app import linkcheck
        try:        # pre-flight: tell Shreya about dead links or paywalls, then send what she confirmed
            lc = linkcheck.run(issue["id"])
            if lc["problems"]:
                bad = "\n".join(f"• #{r['position']} {r['state']} ({r['status']}): {r['title'][:70]}" for r in lc["rows"] if r["state"] != "ok")
                telegram.say(f"🔗 <b>Pre-flight link check:</b> {lc['problems']} of {len(lc['rows'])} links need a look.\n{bad}\nThe issue is still going out as confirmed.")
        except Exception:
            pass
        return mailer.send_issue(issue["id"])
    if issue["status"] == "drafted":
        telegram.say("⚠️ It's Thursday morning and the draft is <b>not confirmed</b>, so nothing was sent. "
                     "Confirm it and it will go out immediately.", reply_markup=telegram.confirm_buttons(issue["id"]))
    return {"skipped": f"issue is {issue['status']}"}
