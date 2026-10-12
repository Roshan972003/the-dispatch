"""The Dispatch email: designed to be read, not skimmed past. Warm paper look, serif body, Shreya's take set apart on every story,
share / subscribe / unsubscribe / view-in-browser in the footer, a dark-mode variant, a phone layout and a plain-text twin."""
from datetime import datetime, timedelta
from html import escape as h
from urllib.parse import quote
from app import config
from app.ingest import similar, fingerprint

def send_date(week):
    """Thursday 08:00 IST of the issue's week."""
    return datetime.strptime(week, "%Y-%m-%d") + timedelta(days=3, hours=8)

def unsub_url(token):
    return f"{config.PUBLIC_URL}/unsubscribe?t={token}"

def share_links(week=None):
    base = config.PUBLIC_URL
    msg = "The Dispatch: a weekly read on the Indian startup ecosystem, with sharp commentary on each story. Worth a subscribe:"
    return {"WhatsApp": f"https://wa.me/?text={quote(msg + ' ' + base)}", "X": f"https://twitter.com/intent/tweet?text={quote(msg)}&url={quote(base)}",
            "LinkedIn": f"https://www.linkedin.com/sharing/share-offsite/?url={quote(base)}",
            "Email a friend": f"mailto:?subject={quote('Worth a read: The Dispatch')}&body={quote(msg + chr(10) + chr(10) + base)}"}

def _unique(items):
    """Safety net: an edition never shows the same story twice (same link, or near-identical headline)."""
    out, seen_urls, fps = [], set(), []
    for it in items:
        fp = fingerprint(it["title"])
        if it["url"] in seen_urls or any(similar(fp, f, 0.6) for f in fps):
            continue
        seen_urls.add(it["url"]); fps.append(fp); out.append(it)
    return out

CSS = """<style>
body,table,td{-webkit-text-size-adjust:100%}a{color:inherit}
@media (max-width:620px){.wrap{padding:0 !important}.card{padding:26px 20px !important;border-radius:0 !important}.mast{font-size:36px !important}.hd{font-size:22px !important}.take{font-size:17px !important}.btn{display:block !important;margin:0 0 8px !important;text-align:center !important}}
@media (prefers-color-scheme:dark){body,.bg{background:#12110f !important}.card{background:#1b1915 !important}.ink{color:#f3efe6 !important}.mut{color:#aaa397 !important}.rule{border-color:#33302a !important}
.takebox{background:#26221b !important;border-color:#f59e0b !important}.lk{color:#fbbf24 !important}.chip{background:#2d2820 !important;color:#fbbf24 !important}.btn{background:#26221b !important;color:#f3efe6 !important;border-color:#3b362d !important}}
</style>"""

def render(issue, items, token="preview"):
    """-> (subject, html, text)"""
    items = _unique(items)
    date = send_date(issue["week"]).strftime("%A %-d %B %Y")
    subject = issue.get("subject") or f"The Dispatch · {send_date(issue['week']).strftime('%-d %b %Y')}"
    pre = issue.get("preheader") or "This week's startup stories, with the part the headline leaves out."
    words = sum(len((i["commentary"] or "").split()) + len(i["title"].split()) for i in items)
    mins = max(2, round(words / 180))
    theme = (issue.get("selection_notes") or "").split("\nFLAG:")[0].strip()
    base, unsub, view = config.PUBLIC_URL, unsub_url(token), f"{config.PUBLIC_URL}/archive/{issue['week']}"
    F = "Georgia,'Times New Roman',serif"; S = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"

    toc = "".join(f'<tr><td style="padding:5px 0;font:600 14px {S};color:#b45309;width:26px;vertical-align:top" class="lk">{i["position"]}</td>'
                  f'<td style="padding:5px 0;font:15px/1.4 {F};vertical-align:top" class="ink">{h(i["title"])}</td></tr>' for i in items)
    stories = []
    for n, it in enumerate(items, 1):
        walled = it.get("access") in ("soft", "hard", "dead")
        alt = (f'<div style="margin-top:6px;font:13px {S}" class="mut">🔒 This one may be paywalled. '
               + (f'<a href="{h(it["alt_url"])}" style="color:#b45309;font-weight:600" class="lk">Free coverage from {h(it["alt_source"])} →</a>' if it.get("alt_url") else "A free version wasn't found this week.") + "</div>") if walled else ""
        stories.append(
            f'<tr><td style="padding:30px 0 6px;border-top:1px solid #e8e2d4" class="rule">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="font:700 13px {S};letter-spacing:.08em;text-transform:uppercase;color:#b45309" class="lk">'
            f'{n:02d} &nbsp;·&nbsp; {h(it["topic"] or "")}</td></tr>'
            f'<tr><td style="padding:8px 0 14px"><a href="{h(it["url"])}" style="text-decoration:none;color:#1c1917;font:700 26px/1.25 {F}" class="hd ink">{h(it["title"])}</a></td></tr>'
            f'<tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td class="takebox" style="background:#fbf6ea;border-left:4px solid #f59e0b;border-radius:0 10px 10px 0;padding:16px 18px">'
            f'<div style="font:700 11px {S};letter-spacing:.1em;text-transform:uppercase;color:#92400e;margin-bottom:6px" class="lk">Shreya’s take</div>'
            f'<div style="font:19px/1.6 {F};color:#292524" class="take ink">{h(it["commentary"] or "")}</div></td></tr></table></td></tr>'
            f'<tr><td style="padding:12px 0 0;font:14px {S};color:#78716c" class="mut">{h(it["source"])} &nbsp;·&nbsp; '
            f'<a href="{h(it["url"])}" style="color:#b45309;font-weight:600;text-decoration:none" class="lk">Read the full story →</a>{alt}</td></tr></table></td></tr>')

    shares = "".join(f'<a href="{h(u)}" class="btn" style="display:inline-block;margin:0 6px 8px 0;padding:10px 16px;border:1px solid #e2dccb;border-radius:999px;background:#fff;color:#1c1917;text-decoration:none;font:600 13px {S}">{h(k)}</a>'
                     for k, u in share_links().items())
    html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark"><title>{h(subject)}</title>{CSS}</head>'
            f'<body class="bg" style="margin:0;padding:0;background:#f4f0e6"><span style="display:none;opacity:0;height:0;overflow:hidden;mso-hide:all">{h(pre)}</span>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="bg" style="background:#f4f0e6"><tr><td align="center" class="wrap" style="padding:28px 12px">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="card" style="max-width:640px;background:#ffffff;border-radius:16px;padding:40px 38px">'
            # masthead
            f'<tr><td align="center" style="padding-bottom:6px"><div class="mast ink" style="font:700 46px/1 {F};letter-spacing:-.02em;color:#1c1917">The Dispatch</div>'
            f'<div class="mut" style="font:14px {S};color:#78716c;margin-top:10px">The Indian startup ecosystem, with commentary</div>'
            f'<div class="mut" style="font:600 12px {S};letter-spacing:.08em;text-transform:uppercase;color:#a8a29e;margin-top:14px">{h(date)} &nbsp;·&nbsp; {len(items)} stories &nbsp;·&nbsp; {mins} min read</div></td></tr>'
            + (f'<tr><td align="center" style="padding:22px 8px 6px"><div class="ink" style="font:italic 19px/1.55 {F};color:#44403c">{h(theme)}</div></td></tr>' if theme else "")
            # in this issue
            + f'<tr><td style="padding:26px 0 8px"><div style="font:700 11px {S};letter-spacing:.1em;text-transform:uppercase;color:#a8a29e;margin-bottom:6px" class="mut">In this issue</div>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{toc}</table></td></tr>'
            + "".join(stories)
            # sign-off + share
            + f'<tr><td style="padding:30px 0 10px;border-top:1px solid #e8e2d4" class="rule"><div class="ink" style="font:italic 20px {F};color:#292524">That’s the week. See you Thursday.</div>'
            f'<div class="ink" style="font:600 16px {S};margin-top:8px;color:#1c1917">— Shreya</div></td></tr>'
            f'<tr><td style="padding:22px 0 8px"><div class="ink" style="font:700 16px {F};color:#1c1917;margin-bottom:4px">Know someone who’d like this?</div>'
            f'<div class="mut" style="font:14px/1.5 {S};color:#78716c;margin-bottom:14px">Forward this email, or share it. They can subscribe in one step.</div>{shares}</td></tr>'
            # footer
            f'<tr><td style="padding:22px 0 0;border-top:1px solid #e8e2d4;font:12.5px/1.7 {S};color:#a8a29e" class="rule mut">'
            f'<a href="{h(view)}" style="color:#78716c" class="mut">View in browser</a> &nbsp;·&nbsp; '
            f'<a href="{h(base)}" style="color:#78716c" class="mut">Subscribe</a> (got this forwarded?) &nbsp;·&nbsp; '
            f'<a href="{h(unsub)}" style="color:#78716c" class="mut">Unsubscribe</a><br>'
            f'You’re receiving The Dispatch because you subscribed at {h(config.PUBLIC_URL.replace("https://", ""))}. One click above ends it, no questions asked.</td></tr>'
            f'</table></td></tr></table></body></html>')

    text = [f"THE DISPATCH · {date}", "The Indian startup ecosystem, with commentary", ""]
    if theme:
        text += [theme, ""]
    text += ["IN THIS ISSUE"] + [f"{i['position']}. {i['title']}" for i in items] + [""]
    for n, it in enumerate(items, 1):
        text += [f"{n:02d} · {(it['topic'] or '').upper()}", it["title"], f"Shreya's take: {it['commentary']}", f"{it['source']} · {it['url']}"]
        if it.get("access") in ("soft", "hard", "dead"):
            text.append("May be paywalled." + (f" Free coverage ({it['alt_source']}): {it['alt_url']}" if it.get("alt_url") else ""))
        text.append("")
    text += ["— Shreya", "", f"Share The Dispatch: {base}", f"View in browser: {view}", f"Unsubscribe: {unsub}"]
    return subject, html, "\n".join(text)
