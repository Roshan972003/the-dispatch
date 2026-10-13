# The Dispatch: Newsletter Intelligence Engine

MESA C4 · AI and its Applications · Section 1 final examination · Problem Statement 17.

An automated pipeline for **The Dispatch**, Shreya's weekly newsletter on the Indian startup ecosystem. It reads the news Monday to Wednesday, picks and drafts the issue with **Gemini Flash**, sends it to Shreya on **Telegram** for review, and emails the subscriber list on Thursday morning **only after she confirms**.

| | |
|---|---|
| **Live app** | https://the-dispatch-ruby.vercel.app |
| **Dashboard** | https://the-dispatch-ruby.vercel.app/dashboard (no login) |
| **Sample issue** | https://the-dispatch-ruby.vercel.app/sample |
| **Components Map** | https://the-dispatch-ruby.vercel.app/components-map (source: [`components-map.html`](components-map.html)) |
| **Telegram bot** | [@Dispatch_Mesa_Bot](https://t.me/Dispatch_Mesa_Bot) |
| **Code** | https://github.com/Roshan972003/the-dispatch |

## The weekly flow

```
Mon-Wed 8:00 AM IST   ingest 14 live RSS feeds + 13 Google News searches + NewsAPI, GNews and NewsData queries (+ GDELT), keep only Indian-startup-ecosystem news, de-duplicate, store in Neon
Wed     2:00 PM IST   Gemini pre-screens every headline, picks 10 stories across 3+ sectors, drafts each take in Shreya's voice
Wed     afternoon     the draft lands in Telegram: Keep / Swap / Edit / Voice / Angles on every story card
Wed    10:00 PM IST   still unconfirmed? a loud, pinned reminder with "Confirm" and "Push deadline" buttons
Thu     8:00 AM IST   link check, then the email goes to active subscribers, but only if Shreya confirmed
```

Nothing is ever emailed without her explicit, two-step confirmation (see *Safeguards*).

## The problem statement, requirement by requirement

| The brief says | Where it lives |
|---|---|
| Runs Monday to Wednesday, ingesting multiple RSS feeds and news API queries | [`vercel.json`](vercel.json) cron `30 2 * * 1-3` (08:00 IST) → [`app/ingest.py`](app/ingest.py), [`app/sources.py`](app/sources.py) |
| Stores each article; no duplicates within a week or across the previous four weeks' newsletters | URL hash unique; headline similarity within the week and against the last four issues ([`ingest.store`](app/ingest.py)); a company/founder repeat guard at selection ([`select_stories.repeat_guard`](app/select_stories.py)) |
| **Scope: only Indian startup ecosystem news** (the newsletter's subject) | Four layers: global feeds (TechCrunch, Rest of World, Hacker News) removed and social posts dropped at ingestion ([`ingest_util.in_scope`](app/ingest_util.py)); a stricter pre-screen; a stricter pick prompt (8 of 10 squarely about startups); an ingestion-time Gemini scope check that sets aside anything not squarely about Indian startups (status `out_of_scope`, visible in the Articles tab with the reason); and an independent two-pass scope check that swaps any off-topic pick for the next in-scope runner-up ([`scope_guard`](app/select_stories.py)) |
| Wednesday afternoon, Gemini picks 8 to 10 stories: high signal vs this week's batch, not in the last four newsletters, spanning at least three topics | [`select_stories.py`](app/select_stories.py): whole-week pre-screen, shortlist, selection with code-level validation (count, topic spread, real ids, no duplicates), retry then repair |
| Commentary in Shreya's documented editorial voice, stored as a style guide | [`style_guide.md`](style_guide.md) → versioned `style_guide` table ([`app/styleguide.py`](app/styleguide.py)); every draft is checked against her hard rules |
| Draft delivered via Telegram by Wednesday evening; she reviews, edits, approves or swaps stories individually | [`app/telegram.py`](app/telegram.py): per-story Keep, Swap (3 pre-drafted options), Edit, Voice, Angles |
| On confirmation, assemble a formatted email and send on Thursday morning | [`app/email_template.py`](app/email_template.py), [`app/mailer.py`](app/mailer.py), [`app/pipeline.py`](app/pipeline.py); cron `30 2 * * 4` |
| **Never send autonomously**; wait for explicit confirmation | Three independent locks: Telegram's two-step confirm, `mailer.send_issue()` refuses unless `approved_at` is set, and the Thursday job checks status |
| No confirmation by Wednesday 10 PM → send a reminder | cron `30 16 * * 3` (22:00 IST) → `telegram.send_reminder` |
| Unsubscribes and bounces handled gracefully | One-click unsubscribe (page + `List-Unsubscribe` header), hard bounces and spam complaints switch addresses off via a signed Resend webhook, temporary bounces don't; unknown or preview links end on a friendly page, never an error |
| All AI tasks use Gemini Flash, not Claude | [`app/gemini.py`](app/gemini.py): `gemini-3.8-flash` only; no other AI provider anywhere in the code |
| Live external data; works with data at submission | 41 live source jobs per run (14 active RSS feeds, Google News searches and news APIs); the Neon database holds a real week of articles and a drafted issue |
| Deployed on Vercel | FastAPI on Vercel ([`index.py`](index.py)), Vercel Cron for the schedule |

## What the dashboard shows

Open `/dashboard`. **Overview** (plain-English status, approval timeline, the signal funnel), **Review the draft** (voice tuner, voice-check editor, reasoning cards with source text, trend-fusion canvas), **Insights** (entity graph, trend heatmap, 4-week archive matrix), **Telegram** (a simulator of the review chat), **Email & send** (fail-safe launchpad, email preview, link and deliverability checks, social export), **Subscribers**, **All articles** (every article with the reason it was kept or dropped) and **Sources**. Press **⌘K / Ctrl+K** for the command palette.

It is open so it can be shown to anyone. It can preview and rate-limited-run the pipeline, but it can **never** approve or send an issue: that only happens in Telegram.

## Safeguards

- **Confirmation lock** (above). A forced re-draft clears any earlier confirmation.
- **Only Shreya's chat is obeyed** on Telegram (chat id plus webhook secret); every webhook update is processed once.
- **Cron routes** require the `CRON_SECRET` bearer token; the Resend and Telegram webhooks verify signatures or a secret.
- **Voice rules in code**, not just in the prompt: 2 to 3 sentences, at most 65 words, no banned phrases, no restated headline, numbers and proper names must come from the source article.
- **Paywalls:** each link is tagged free, soft or hard paywall. A hard-paywalled story is swapped for a free runner-up when one exists; otherwise the email says so plainly and offers free coverage when it finds some.
- **Pre-flight link check** before the Thursday send, with problems reported on Telegram.
- Subscriber addresses are masked on the public dashboard.

## Stack

FastAPI on Vercel · Gemini Flash (`gemini-3.8-flash`) · Neon Postgres · Telegram Bot API · Resend · Vercel Cron · feedparser, httpx, BeautifulSoup.

## Run it locally

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env            # fill in the keys; with no DATABASE_URL it uses a local SQLite file
./venv/bin/uvicorn app.main:app --port 8000
./venv/bin/python scripts/poll.py   # optional: drive the Telegram bot locally instead of the webhook
```

Environment variables are listed in [`.env.example`](.env.example). On Vercel, `VERCEL_PROJECT_PRODUCTION_URL` supplies the public URL automatically.

Useful scripts: `scripts/import_subscribers.py` (import Shreya's real list as active subscribers), `scripts/seed_sample_2200.py` (the generated demo list), `scripts/migrate_to_neon.py`.

## Honest limits

- **RSS feeds.** 20 feeds are registered; 14 are active. Six (Moneycontrol, Business Standard, VCCircle, Tracxn, Analytics India Magazine and a duplicate Entrackr address) block automated readers or are dead, so they are switched off. All 14 active feeds returned articles in the last live run.
- **Sample data.** The subscriber list in the demo is generated (2,200 active test addresses, tagged `sample`); Shreya's real list is imported with one command. Sample addresses are capped at 25 per send so a demo never burns the email quota.
- **Sending domain.** Mail is sent from Resend's shared test address, which can only deliver to the Resend account owner. Reaching real subscribers needs a domain verified in Resend. Until then, new sign-ups are added instantly instead of by confirmation email.
- **Vercel Hobby cron** runs each job at some point in the hour after its scheduled time, so "10 PM" is 10 to 11 PM and "Wednesday 2 PM" is 2 to 3 PM IST. Never early.
- **Open and click analytics** are wired to Resend webhooks but stay empty (nothing is estimated) until mail goes out from a verified domain.
- **GDELT** (one of the news APIs) allows one request per 5 seconds and often refuses Vercel's shared servers. The system retries, and if it is still refused it skips GDELT for that run and says so in the Sources tab. Every other source is unaffected.
- **Engagement panel:** shows a clearly labelled **projection** for the full list (based on the brief's 38% open rate; estimates, not measurements). Real deliveries, opens and clicks from Resend appear in a separate "Measured so far" block as they arrive.
- **Send mode:** while the sender is Resend's test address, a send goes to the account owner plus 25 sample addresses; the dashboard's launchpad and send log say so ("Test mode").
- Voice notes and button rewrites take a few seconds because they call Gemini.
