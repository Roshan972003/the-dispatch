"""Wednesday editorial pass (spec: style_guide.md sections 4-6).
Call 1 selects 8-10 stories; call 2 drafts commentary per story in Shreya's voice. Everything is validated in code."""
import re, json
from concurrent.futures import ThreadPoolExecutor
from app import config, db, gemini, styleguide
from app.ingest import tokens

TOPICS = ["Funding & Deals", "Policy & Regulation", "AI & Deep Tech", "Fintech", "Consumer & D2C",
          "SaaS & Enterprise", "Climate & Mobility", "Markets & IPOs", "Layoffs & Workforce", "Other"]
FILTERS = ["COUNTERINTUITIVE", "UNDER-REPORTED", "TREND-CONNECTING"]

def candidates(c, week, limit=90):
    rows = db.all(c, "SELECT id, source, title, snippet, published_at FROM articles WHERE week=? AND status='new' ORDER BY published_at DESC", (week,))
    per, out = {}, []
    for r in rows:                      # cap per source so one prolific feed cannot crowd out the rest
        if per.get(r["source"], 0) < 12:
            out.append(r); per[r["source"]] = per.get(r["source"], 0) + 1
    return out[:limit]

def recent_titles(c, week):
    rows = db.all(c, """SELECT a.title FROM issue_items i JOIN issues s ON s.id=i.issue_id JOIN articles a ON a.id=i.article_id
                        WHERE i.kind='selected' AND s.week IN (SELECT week FROM issues WHERE week < ? ORDER BY week DESC LIMIT ?)""",
                  (week, config.LOOKBACK_ISSUES))
    return [r["title"] for r in rows]

# ---------------- call 1: selection ----------------
_ITEM = {"type": "OBJECT", "properties": {"article_id": {"type": "INTEGER"}, "topic_area": {"type": "STRING", "enum": TOPICS},
         "selection_filter": {"type": "STRING", "enum": FILTERS}, "reason": {"type": "STRING"}},
         "required": ["article_id", "topic_area", "selection_filter", "reason"]}
PICK_SCHEMA = {"type": "OBJECT", "properties": {"selected": {"type": "ARRAY", "items": _ITEM},
               "backups": {"type": "ARRAY", "items": _ITEM}, "week_theme": {"type": "STRING"}}, "required": ["selected", "backups"]}

def _selection_errors(res, ids):
    sel = res.get("selected", []); picked = [s["article_id"] for s in sel]; errs = []
    if not config.PICK_MIN <= len(sel) <= config.PICK_MAX:
        errs.append(f"returned {len(sel)} stories, need {config.PICK_MIN} to {config.PICK_MAX}")
    if any(i not in ids for i in picked):
        errs.append("some article_ids are not in the candidate list")
    if len(set(picked)) != len(picked):
        errs.append("duplicate article_ids")
    if len({s["topic_area"] for s in sel}) < config.MIN_TOPICS:
        errs.append(f"fewer than {config.MIN_TOPICS} distinct topic_area values")
    seen = []
    for s in sel:                       # two picks describing the same event
        t = " ".join(sorted(tokens(ids.get(s["article_id"], {}).get("title", ""))))
        from app.ingest import similar
        if any(similar(t, o, 0.4) for o in seen):
            errs.append("two selected stories describe the same event")
        seen.append(t)
    return errs

def select(sg, cands, recent):
    ids = {a["id"]: a for a in cands}
    system = ("You are the editorial selector for The Dispatch, a weekly newsletter on the Indian startup ecosystem. "
              "You select; you do not write commentary in this step.")
    cj = "\n".join(json.dumps({"article_id": a["id"], "title": a["title"], "source": a["source"], "snippet": (a["snippet"] or "")[:240]}) for a in cands)
    base = (f"From the candidate list, choose {config.PICK_MIN} to {config.PICK_MAX} stories that:\n"
            "- each satisfy at least one filter: COUNTERINTUITIVE, UNDER-REPORTED, TREND-CONNECTING (definitions below)\n"
            f"- collectively cover at least {config.MIN_TOPICS} different topic areas\n"
            "- are not about a company-event already listed in RECENT_ISSUES\n"
            "- are high signal relative to this week's batch (reject press releases, pure funding announcements and restated headlines)\n"
            "- are not two stories about the same event\n\n"
            f"FILTERS:\n{sg['filters']}\n\nRECENT_ISSUES (do not repeat these stories or events):\n" + ("\n".join("- " + t for t in recent) or "(none yet)") +
            f"\n\nCANDIDATES:\n{cj}\n\nOrder 'selected' by editorial strength. 'backups': 6 ranked replacements for the Swap button, ideally from topics under-represented in 'selected'. "
            "'reason' is one sentence. 'week_theme' is one line.")
    errs, feedback, res = [], "", None
    for _ in range(2):                  # one retry with the failure reason appended (spec section 6)
        res = gemini.generate(system, base + feedback, PICK_SCHEMA, 0.3)
        errs = _selection_errors(res, ids)
        if not errs:
            break
        feedback = "\n\nYour previous answer failed validation: " + "; ".join(errs) + ". Fix this."
    flag = None
    if errs:                            # still failing: repair from backups and tell Shreya
        flag = "Selection failed validation twice (" + "; ".join(errs) + "); filled from backups."
        res = _repair(res, ids)
    used = {s["article_id"] for s in res["selected"]}
    res["backups"] = [b for b in res["backups"] if b["article_id"] in ids and b["article_id"] not in used]
    return res, flag

def _repair(res, ids):
    sel, seen = [], set()
    for s in res.get("selected", []):
        if s["article_id"] in ids and s["article_id"] not in seen:
            sel.append(s); seen.add(s["article_id"])
    pool = [b for b in res.get("backups", []) if b["article_id"] in ids and b["article_id"] not in seen]
    while pool and (len(sel) < config.PICK_MIN or len({s["topic_area"] for s in sel}) < config.MIN_TOPICS):
        known = {s["topic_area"] for s in sel}
        nxt = next((b for b in pool if b["topic_area"] not in known), pool[0]) if len({s["topic_area"] for s in sel}) < config.MIN_TOPICS else pool[0]
        sel.append(nxt); pool.remove(nxt)
    res["selected"] = sel[:config.PICK_MAX]
    return res

# ---------------- call 2: drafting ----------------
DRAFT_SCHEMA = {"type": "OBJECT", "properties": {"commentary": {"type": "STRING"}}, "required": ["commentary"]}
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿]")
NUM = re.compile(r"\d[\d,]*\.?\d*")

def validate_commentary(text, title, snippet, banned):
    errs = []
    words = text.split()
    sents = [s for s in re.split(r"(?<=[.?])\s+", text.strip()) if s]
    if not 2 <= len(sents) <= 3 or len(words) > 65:
        errs.append(f"length: {len(sents)} sentences, {len(words)} words (need 2-3 sentences, at most 65 words)")
    for b in banned:
        if b.lower() in text.lower():
            errs.append(f"contains banned phrase '{b}'")
    if "!" in text or EMOJI.search(text):
        errs.append("contains '!' or an emoji")
    ht = tokens(title)
    if ht and len(tokens(text) & ht) / len(ht) >= 0.6:
        errs.append("restates the headline (60%+ word overlap)")
    src = title + " " + snippet
    bad = [n for n in NUM.findall(text) if n.strip(",.") not in src.replace(",", "") and n.strip(",.") not in src]
    if bad:
        errs.append(f"numbers not in the snippet or headline: {', '.join(bad)}")
    return errs

def _system(sg):
    ex = "\n\n".join(f"Headline: {e['headline']}\nSnippet: {e['snippet']}\nCommentary: {e['commentary']}" for e in sg["examples"])
    return ("You are the ghostwriter for Shreya, author of The Dispatch.\n\nVOICE RULES:\n" + sg["rules"] +
            "\n\nBANNED PHRASES:\n" + ", ".join(sg["banned"]) + "\n\nEXAMPLES OF HER VOICE:\n" + ex)

def draft_one(sg, story):
    system = _system(sg)
    prompt = (f"Story:\n  Title: {story['title']}\n  Source: {story['source']}\n  Snippet: {story['snippet'] or '(none; reason from structure only)'}\n"
              f"  Selection filter: {story['selection_filter']}\n\nWrite the commentary. Use only facts in the snippet. Return ONLY JSON: {{\"commentary\": \"...\"}}")
    text, errs = "", []
    for attempt in range(2):
        extra = "" if not errs else "\n\nFailed: " + "; ".join(errs) + ". Rewrite."
        text = gemini.generate(system, prompt + extra, DRAFT_SCHEMA, 0.7)["commentary"].strip()
        errs = validate_commentary(text, story["title"], story["snippet"] or "", sg["banned"])
        if not errs:
            break
    return text, errs

def run_selection(force=False):
    week = config.week_start()
    with db.conn() as c:
        issue = db.one(c, "SELECT * FROM issues WHERE week=?", (week,))
        if issue and issue["status"] != "collecting" and not force:
            return {"week": week, "skipped": f"issue already {issue['status']}"}
        cands, recent, sg = candidates(c, week), recent_titles(c, week), styleguide.active(c)
    if len(cands) < config.PICK_MAX:
        return {"week": week, "error": f"only {len(cands)} candidates"}
    res, flag = select(sg, cands, recent)
    by_id = {a["id"]: a for a in cands}
    stories = [{**by_id[s["article_id"]], "selection_filter": s["selection_filter"], "topic": s["topic_area"], "why": s["reason"]} for s in res["selected"]]
    with ThreadPoolExecutor(5) as ex:
        drafts = list(ex.map(lambda s: draft_one(sg, s), stories))
    notes = (res.get("week_theme") or "") + (f"\nFLAG: {flag}" if flag else "")
    with db.conn() as c:
        if issue:
            db.run(c, "DELETE FROM issue_items WHERE issue_id=?", (issue["id"],)); iid = issue["id"]
            db.run(c, "UPDATE articles SET status='new' WHERE week=? AND status='selected'", (week,))
        else:
            iid = db.insert(c, "INSERT INTO issues (week, status, created_at) VALUES (?,?,?)", (week, "collecting", config.now_ist().isoformat(timespec="seconds")))
        for pos, (s, (text, errs)) in enumerate(zip(stories, drafts), 1):
            db.run(c, """INSERT INTO issue_items (issue_id, article_id, position, kind, commentary, draft_original, topic, why, selection_filter, flags)
                         VALUES (?,?,?,?,?,?,?,?,?,?)""", (iid, s["id"], pos, "selected", text, text, s["topic"], s["why"], s["selection_filter"], "; ".join(errs)))
            db.run(c, "UPDATE articles SET status='selected', topic=? WHERE id=?", (s["topic"], s["id"]))
        for pos, b in enumerate(res["backups"], 1):
            db.run(c, "INSERT INTO issue_items (issue_id, article_id, position, kind, topic, why, selection_filter) VALUES (?,?,?,?,?,?,?)",
                   (iid, b["article_id"], pos, "backup", b["topic_area"], b["reason"], b["selection_filter"]))
        db.run(c, "UPDATE issues SET status='drafted', drafted_at=?, selection_notes=? WHERE id=?", (config.now_ist().isoformat(timespec="seconds"), notes, iid))
        db.log(c, "select", f"issue {iid}: {len(stories)} picks, style v{sg['version']}, flag={flag}")
    return {"week": week, "issue_id": iid, "picks": len(stories), "topics": sorted({s["topic"] for s in stories}),
            "style_version": sg["version"], "selection_flag": flag, "comment_flags": sum(1 for _, e in drafts if e)}
