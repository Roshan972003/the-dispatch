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

def _clip(t, n):
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",;:-– ") + "…"

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
@media (max-width:620px){.wrap{padding:0 !important}.card{border-radius:0 !important}.pad{padding-left:22px !important;padding-right:22px !important}.mast{font-size:38px !important}.hd{font-size:23px !important}.take{font-size:17px !important}.num{font-size:34px !important}.btn{display:block !important;margin:0 0 8px !important;text-align:center !important}}
@media (prefers-color-scheme:dark){body,.bg{background:#0d0c0a !important}.card{background:#171512 !important}.ink{color:#f3efe6 !important}.mut{color:#a8a195 !important}.rule{border-color:#2c2923 !important}
.takebox{background:#211e18 !important}.lk{color:#e8b64c !important}.pill{border-color:#3a352c !important;color:#c9c2b3 !important}.btn{background:#211e18 !important;color:#f3efe6 !important;border-color:#3a352c !important}.edit{background:#1d1a15 !important}.head{background:#000 !important}.foot{background:#0f0e0c !important}}
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
    GOLD, GOLD2, INK, MUT = "#b8862b", "#8a5f12", "#1a1814", "#7a7366"

    toc = "".join(f'<tr><td style="padding:7px 0;font:700 13px {S};color:{GOLD2};width:34px;vertical-align:top;letter-spacing:.04em" class="lk">{i["position"]:02d}</td>'
                  f'<td style="padding:7px 0;font:16px/1.4 {F};vertical-align:top;color:{INK}" class="ink">{h(_clip(i["title"], 105))}</td></tr>' for i in items)
    stories = []
    for n, it in enumerate(items, 1):
        acc_ = it.get("access")
        walled = acc_ in ("soft", "hard", "dead")
        if walled and it.get("alt_url"):
            alt = (f'<div style="margin-top:8px;font:13px/1.5 {S};color:{MUT}" class="mut">🔒 {h(it["source"])} may ask for a subscription. '
                   f'<a href="{h(it["alt_url"])}" style="color:{GOLD2};font-weight:600" class="lk">Read the free coverage from {h(it["alt_source"])} →</a></div>')
        elif acc_ == "hard":
            alt = f'<div style="margin-top:8px;font:13px/1.5 {S};color:{MUT}" class="mut">🔒 Subscription needed: this story sits behind {h(it["source"])}’s paywall. The take above stands on its own.</div>'
        elif walled:
            alt = f'<div style="margin-top:8px;font:13px/1.5 {S};color:{MUT}" class="mut">🔒 May be limited to subscribers. The take above stands on its own.</div>'
        else:
            alt = ""
        stories.append(
            f'<tr><td class="pad rule" style="padding:34px 44px 6px;border-top:1px solid #ece5d4">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td width="58" valign="top" class="num lk" style="font:400 40px/1 {F};color:{GOLD};width:58px">{n:02d}</td>'
            f'<td valign="top" style="padding-top:6px"><span class="pill" style="display:inline-block;padding:4px 12px;border:1px solid #dccfae;border-radius:999px;font:700 10.5px {S};letter-spacing:.12em;text-transform:uppercase;color:{GOLD2}">{h(it["topic"] or "")}</span></td></tr></table>'
            f'<div style="padding:14px 0 16px"><a href="{h(it["url"])}" style="text-decoration:none;color:{INK};font:700 26px/1.25 {F};letter-spacing:-.01em" class="hd ink">{h(_clip(it["title"], 150))}</a></div>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td class="takebox" style="background:#faf5e8;border-radius:12px;padding:18px 22px 20px">'
            f'<div style="font:700 10.5px {S};letter-spacing:.16em;text-transform:uppercase;color:{GOLD2};margin-bottom:10px" class="lk"><span style="display:inline-block;width:22px;height:2px;background:{GOLD};vertical-align:middle;margin-right:8px"></span>Shreya’s take</div>'
            f'<div style="font:19px/1.65 {F};color:#2b2823" class="take ink">{h(it["commentary"] or "")}</div></td></tr></table>'
            f'<div style="padding:14px 0 0;font:14px/1.5 {S};color:{MUT}" class="mut">{h(it["source"])} &nbsp;·&nbsp; '
            f'<a href="{h(it["url"])}" style="color:{GOLD2};font-weight:700;text-decoration:none" class="lk">Read the full story →</a>{alt}</div></td></tr>')

    shares = "".join(f'<a href="{h(u)}" class="btn" style="display:inline-block;margin:0 8px 8px 0;padding:10px 18px;border:1px solid #dccfae;border-radius:999px;background:#fffdf8;color:{INK};text-decoration:none;font:600 13px {S}">{h(k)}</a>'
                     for k, u in share_links().items())
    html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark"><title>{h(subject)}</title>{CSS}</head>'
            f'<body class="bg" style="margin:0;padding:0;background:#ece7da"><span style="display:none;opacity:0;height:0;overflow:hidden;mso-hide:all">{h(pre)}</span>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="bg" style="background:#ece7da"><tr><td align="center" class="wrap" style="padding:30px 12px">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="card" style="max-width:660px;background:#fffdf8;border-radius:18px;overflow:hidden">'
            # masthead band
            f'<tr><td align="center" class="head pad" style="background:#14120f;padding:46px 36px 40px">'
            f'<div style="font:700 11px {S};letter-spacing:.32em;text-transform:uppercase;color:#d4a94a">Weekly &nbsp;·&nbsp; Thursday edition</div>'
            f'<div class="mast" style="font:700 50px/1.05 {F};letter-spacing:-.02em;color:#f6f0e1;margin-top:16px">The Dispatch</div>'
            f'<div style="width:44px;height:2px;background:#d4a94a;margin:20px auto 18px;line-height:2px;font-size:2px">&nbsp;</div>'
            f'<div style="font:italic 16px/1.5 {F};color:#cfc6b2">The Indian startup ecosystem, with commentary</div>'
            f'<div style="font:600 12px {S};letter-spacing:.1em;text-transform:uppercase;color:#8f8776;margin-top:18px">{h(date)} &nbsp;·&nbsp; {len(items)} stories &nbsp;·&nbsp; {mins} min read</div></td></tr>'
            + (f'<tr><td class="pad" style="padding:34px 44px 4px"><div class="edit" style="background:#fbf7ec;border-radius:12px;padding:20px 24px;font:italic 19px/1.6 {F};color:#3d3830"><span class="ink">{h(theme)}</span></div></td></tr>' if theme else "")
            # in this issue
            + f'<tr><td class="pad" style="padding:30px 44px 26px"><div style="font:700 10.5px {S};letter-spacing:.2em;text-transform:uppercase;color:{GOLD2};margin-bottom:8px" class="lk">In this issue</div>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{toc}</table></td></tr>'
            + "".join(stories)
            # sign-off + share
            + f'<tr><td class="pad" style="padding:38px 44px 10px;border-top:1px solid #ece5d4"><div class="ink" style="font:italic 22px/1.4 {F};color:#2b2823">That’s the week. See you Thursday.</div>'
            f'<div class="ink" style="font:700 17px {F};margin-top:10px;color:{INK}">Shreya</div></td></tr>'
            f'<tr><td class="pad" style="padding:22px 44px 34px"><div class="ink" style="font:700 17px {F};color:{INK};margin-bottom:4px">Know someone who’d like this?</div>'
            f'<div class="mut" style="font:14px/1.5 {S};color:{MUT};margin-bottom:14px">Forward this email, or share it. They can subscribe in one step.</div>{shares}</td></tr>'
            # footer
            f'<tr><td class="foot pad" style="background:#f3eee1;padding:26px 44px 30px;font:12.5px/1.75 {S};color:{MUT}">'
            f'<a href="{h(view)}" style="color:#5e584c;font-weight:600" class="mut">View in browser</a> &nbsp;·&nbsp; '
            f'<a href="{h(base)}" style="color:#5e584c;font-weight:600" class="mut">Subscribe</a> (got this forwarded?) &nbsp;·&nbsp; '
            f'<a href="{h(unsub)}" style="color:#5e584c;font-weight:600" class="mut">Unsubscribe</a><br>'
            f'You’re receiving The Dispatch because you subscribed at {h(config.PUBLIC_URL.replace("https://", ""))}. One click above ends it, no questions asked.</td></tr>'
            f'</table></td></tr></table></body></html>')

    text = [f"THE DISPATCH · {date}", "The Indian startup ecosystem, with commentary", ""]
    if theme:
        text += [theme, ""]
    text += ["IN THIS ISSUE"] + [f"{i['position']}. {i['title']}" for i in items] + [""]
    for n, it in enumerate(items, 1):
        text += [f"{n:02d} · {(it['topic'] or '').upper()}", it["title"], f"Shreya's take: {it['commentary']}", f"{it['source']} · {it['url']}"]
        if it.get("access") in ("soft", "hard", "dead"):
            text.append((f"{it['source']} may ask for a subscription. Free coverage ({it['alt_source']}): {it['alt_url']}" if it.get("alt_url")
                         else ("Subscription needed at " + it["source"] + ". The take above stands on its own." if it.get("access") == "hard" else "May be limited to subscribers. The take above stands on its own.")))
        text.append("")
    text += ["— Shreya", "", f"Share The Dispatch: {base}", f"View in browser: {view}", f"Unsubscribe: {unsub}"]
    return subject, html, "\n".join(text)


SPAMMY = ("free!!!", "act now", "winner", "guarantee", "click here", "100% free", "cash bonus", "buy now", "limited time", "no obligation", "risk-free", "urgent")
SHORTENERS = ("bit.ly", "tinyurl", "t.co/", "goo.gl", "ow.ly", "is.gd")

def deliverability(subject, html, text, sender):
    """Local spam-risk heuristics for the assembled email. Not a SpamAssassin run: it checks the things that actually move inbox placement for a text newsletter."""
    import re
    links = re.findall(r'href="(https?://[^"]+)"', html)
    low = (subject + " " + text).lower()
    caps = re.findall(r"\b[A-Z]{4,}\b", subject)
    checks = [
        ("Subject length 25 to 60 characters", 25 <= len(subject) <= 60, f"{len(subject)} characters"),
        ("No exclamation marks or all-caps words in the subject", "!" not in subject and not caps, "clean" if "!" not in subject and not caps else "found"),
        ("No spam-trigger phrases in the subject or preheader", not [w for w in SPAMMY if w in (subject + " " + (re.findall(r"display:none[^>]*>([^<]+)<", html) or [""])[0]).lower()],
         "clean" + (f" (body mentions: {', '.join(w for w in SPAMMY if w in low)})" if [w for w in SPAMMY if w in low] else "")),
        ("Plain-text version included", bool(text.strip()), f"{len(text)} characters"),
        ("One-click unsubscribe present", "/unsubscribe?t=" in html, "link in the footer + List-Unsubscribe header"),
        ("No images or tracking pixels", "<img" not in html.lower(), "text-only, loads instantly"),
        ("No link shorteners; https only", not any(x in l for l in links for x in SHORTENERS) and all(l.startswith("https://") or "localhost" in l for l in links), f"{len(links)} links"),
        ("Under Gmail's 102 KB clipping limit", len(html.encode()) < 102000, f"{len(html.encode()) // 1024} KB"),
        ("Preheader text set", "display:none" in html and len(re.findall(r"display:none[^>]*>([^<]+)<", html)[0].strip() if re.findall(r"display:none[^>]*>([^<]+)<", html) else "") > 10, "inbox preview line"),
        ("Sent from a verified domain", "resend.dev" not in sender, "using Resend's shared test sender" if "resend.dev" in sender else sender),
    ]
    return [{"rule": r, "ok": bool(ok), "detail": d} for r, ok, d in checks]
