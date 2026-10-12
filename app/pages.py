"""Public pages (subscribe, confirm, unsubscribe, resubscribe): one shared look that matches the email."""
from html import escape as h
from app import config
from app.email_template import share_links

SHELL = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%(title)s</title>
<meta name="description" content="A weekly read on the Indian startup ecosystem, with sharp commentary on every story."><meta name="color-scheme" content="light dark">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Newsreader:ital,wght@0,400;0,600;0,700;1,400&display=swap" rel="stylesheet">
<style>
:root{--bg:#f4f0e6;--card:#fff;--ink:#1c1917;--mut:#78716c;--line:#e8e2d4;--acc:#b45309;--accbg:#fbf6ea;--btn:#1c1917;--btnink:#fff}
@media(prefers-color-scheme:dark){:root{--bg:#12110f;--card:#1b1915;--ink:#f3efe6;--mut:#aaa397;--line:#33302a;--acc:#fbbf24;--accbg:#26221b;--btn:#f59e0b;--btnink:#1a1100}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 Inter,-apple-system,sans-serif;-webkit-font-smoothing:antialiased}
main{max-width:620px;margin:0 auto;padding:7vh 16px 60px}.card{background:var(--card);border-radius:18px;padding:44px 40px;border:1px solid var(--line)}
@media(max-width:560px){.card{padding:30px 22px}}
.brand{font:700 44px/1 Newsreader,Georgia,serif;letter-spacing:-.02em;text-align:center}.tag{text-align:center;color:var(--mut);font-size:14px;margin:10px 0 28px}
h1{font:700 30px/1.2 Newsreader,Georgia,serif;margin:0 0 10px;letter-spacing:-.01em}p{color:var(--mut);margin:0 0 16px}.lead{font:19px/1.6 Newsreader,Georgia,serif;color:var(--ink)}
ul.pts{list-style:none;padding:0;margin:22px 0}ul.pts li{display:flex;gap:12px;padding:10px 0;border-top:1px solid var(--line);color:var(--ink);font-size:15.5px}ul.pts b{color:var(--acc);font-family:Newsreader,serif;font-size:18px;min-width:22px}
form.sub{display:flex;gap:8px;flex-wrap:wrap;margin:24px 0 8px}form.sub input{flex:1;min-width:210px;padding:14px 16px;font:16px Inter,sans-serif;border:1px solid var(--line);border-radius:12px;background:transparent;color:var(--ink)}
.btn,button.btn{padding:14px 22px;font:600 16px Inter,sans-serif;border:0;border-radius:12px;background:var(--btn);color:var(--btnink);cursor:pointer;text-decoration:none;display:inline-block}
.btn.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}#m{min-height:24px;font-size:14.5px;margin-top:6px;color:var(--acc)}
.share{margin-top:30px;padding-top:22px;border-top:1px solid var(--line)}.share b{display:block;font:700 17px Newsreader,serif;margin-bottom:4px}.share a{display:inline-block;margin:8px 8px 0 0;padding:9px 15px;border:1px solid var(--line);border-radius:999px;color:var(--ink);text-decoration:none;font:600 13px Inter,sans-serif}
.note{background:var(--accbg);border-left:4px solid #f59e0b;border-radius:0 10px 10px 0;padding:14px 16px;margin:20px 0;font:17px/1.55 Newsreader,serif;color:var(--ink)}
.foot{text-align:center;color:var(--mut);font-size:12.5px;margin-top:22px}.foot a{color:var(--mut)}label.r{display:flex;gap:10px;align-items:center;padding:11px 14px;border:1px solid var(--line);border-radius:10px;margin:8px 0;cursor:pointer;color:var(--ink);font-size:15px}
</style></head><body><main><div class="card"><div class="brand">The Dispatch</div><div class="tag">The Indian startup ecosystem, with commentary</div>%(body)s</div><div class="foot">&copy; The Dispatch · <a href="/">Subscribe</a></div></main></body></html>"""

def page(title, body):
    return SHELL % {"title": h(title), "body": body}

def share_row(heading="Know someone who would like this?"):
    return f'<div class="share"><b>{h(heading)}</b><span style="color:var(--mut);font-size:14px">Share it. They can subscribe in one step.</span><br>' + "".join(
        f'<a href="{h(u)}" target="_blank" rel="noopener">{h(k)}</a>' for k, u in share_links().items()) + "</div>"

def landing():
    return page("The Dispatch · Subscribe", f'''<h1>Eight to ten stories. One sharp take on each.</h1>
<p class="lead">Every Thursday morning: the Indian startup stories worth your time, and Shreya’s two or three lines on what the headline leaves out.</p>
<ul class="pts"><li><b>1</b><span><strong>Curated, not aggregated.</strong> Counterintuitive, under-reported, or connecting two trends nobody has linked.</span></li>
<li><b>2</b><span><strong>Never repeats itself.</strong> Every story is checked against the last four issues.</span></li>
<li><b>3</b><span><strong>Read in five minutes.</strong> Built to be read on your phone, with a free link when a story is paywalled.</span></li></ul>
<form class="sub" id="f"><input type="email" name="email" placeholder="you@company.com" required autocomplete="email"><button class="btn">Subscribe</button></form><div id="m"></div>
<p style="font-size:13px;margin-top:6px">Free. One email a week. Unsubscribe in one click, any time.</p>
<p style="margin-top:18px"><a class="btn ghost" href="/sample" style="padding:10px 16px;font-size:14px">See a sample issue →</a></p>{share_row()}
<script>f.onsubmit=async e=>{{e.preventDefault();m.textContent='…';const r=await fetch('/api/subscribe',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{email:f.email.value}})}});
const j=await r.json();m.textContent=j.message||j.error||'Something went wrong.'}}</script>''')

def confirmed():
    return page("You're in · The Dispatch", f'<h1>You’re in. Welcome.</h1><p class="lead">Your first issue lands Thursday morning. Add this sender to your contacts so it never hides in a promotions tab.</p>'
                f'<p><a class="btn ghost" href="/sample">See what a Thursday issue looks like →</a></p>{share_row("Bring a friend")}')

def bad_link():
    return page("The Dispatch", '<h1>This link is no longer active.</h1><p class="lead">It may already have been used, or it came from a preview. Nothing is wrong, and you can always join (or rejoin) in one step.</p><p><a class="btn" href="/">Go to The Dispatch</a></p>')

def unsub_form(token):
    opts = "".join(f'<label class="r"><input type="radio" name="reason" value="{h(v)}"> {h(v)}</label>' for v in ["Too many emails", "Not relevant to me", "I never signed up", "Other"])
    return page("Unsubscribe · The Dispatch", f'<h1>Sorry to see you go.</h1><p>One click and you’re off the list. If you have a second, tell us why (optional).</p>'
                f'<form method="post" action="/unsubscribe?t={h(token)}">{opts}<p style="margin-top:20px"><button class="btn">Unsubscribe me</button> &nbsp; <a class="btn ghost" href="/">Keep me subscribed</a></p></form>')

def unsubscribed(token=None):
    """Shown after any unsubscribe click. A real token also gets a one-click Resubscribe; a preview or unknown link simply confirms, with no error."""
    again = (f'<div class="note">Clicked by mistake? You can rejoin in one click.</div><p><a class="btn" href="/resubscribe?t={h(token)}">Resubscribe</a></p>' if token
             else '<div class="note">Changed your mind? You can rejoin any time.</div><p><a class="btn" href="/">Subscribe again</a></p>')
    return page("Unsubscribed · The Dispatch", '<h1>You’re unsubscribed.</h1><p class="lead">You won’t get another email from The Dispatch. Thanks for reading.</p>' + again)

def resubscribed():
    return page("Welcome back · The Dispatch", '<h1>Welcome back.</h1><p class="lead">You’re on the list again. See you Thursday.</p>')
