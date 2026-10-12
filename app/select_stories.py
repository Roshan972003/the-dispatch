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
    rows = db.all(c, "SELECT id, source, title, snippet, url, published_at FROM articles WHERE week=? AND status='new' ORDER BY published_at DESC", (week,))
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

def voice_checks(text, title, snippet, banned):
    """Same rules as validate_commentary, as a list the dashboard can show: [{rule, ok, detail}]."""
    words = text.split()
    sents = [x for x in re.split(r"(?<=[.?])\s+", text.strip()) if x]
    hits = [b for b in banned if b.lower() in text.lower()]
    ht = tokens(title or "")
    overlap = len(tokens(text) & ht) / len(ht) if ht else 0
    src = (title or "") + " " + (snippet or "")
    bad = [n for n in NUM.findall(text) if n.strip(",.") not in src.replace(",", "") and n.strip(",.") not in src]
    return [
        {"rule": "2 to 3 sentences", "ok": 2 <= len(sents) <= 3, "detail": f"{len(sents)} sentences"},
        {"rule": "At most 65 words", "ok": len(words) <= 65, "detail": f"{len(words)} words"},
        {"rule": "No banned phrases", "ok": not hits, "detail": ", ".join(hits) or "clean"},
        {"rule": "No '!' or emoji", "ok": "!" not in text and not EMOJI.search(text), "detail": "clean" if "!" not in text and not EMOJI.search(text) else "found"},
        {"rule": "Does not restate headline", "ok": overlap < 0.6, "detail": f"{int(overlap * 100)}% word overlap"},
        {"rule": "Numbers come from the source", "ok": not bad, "detail": ", ".join(bad) or "all grounded"},
    ]

SCORE_SCHEMA = {"type": "OBJECT", "properties": {"scores": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "article_id": {"type": "INTEGER"}, "signal": {"type": "INTEGER"}, "filter": {"type": "STRING", "enum": FILTERS + ["NONE"]}},
    "required": ["article_id", "signal", "filter"]}}}, "required": ["scores"]}

def score_pool(sg, cands):
    """One Gemini call that rates every candidate 0-100 for editorial signal and names the filter it best satisfies (or NONE)."""
    cj = "\n".join(json.dumps({"article_id": a["id"], "title": a["title"], "snippet": (a["snippet"] or "")[:160]}) for a in cands)
    res = gemini.generate("You are the editorial selector for The Dispatch. Rate candidate stories for Shreya.",
        f"FILTERS:\n{sg['filters']}\n\nFor EVERY candidate give 'signal' 0-100 (how strongly it passes at least one filter; press releases, pure funding announcements and restated headlines score under 30) "
        f"and 'filter' (the best-fitting filter, or NONE). Candidates:\n{cj}", SCORE_SCHEMA, 0.2)
    ids = {a["id"] for a in cands}
    return {x["article_id"]: (max(0, min(100, int(x["signal"]))), x["filter"]) for x in res.get("scores", []) if x["article_id"] in ids}

def _system(sg):
    ex = "\n\n".join(f"Headline: {e['headline']}\nSnippet: {e['snippet']}\nCommentary: {e['commentary']}" for e in sg["examples"])
    return ("You are the ghostwriter for Shreya, author of The Dispatch.\n\nVOICE RULES:\n" + sg["rules"] +
            "\n\nBANNED PHRASES:\n" + ", ".join(sg["banned"]) + "\n\nEXAMPLES OF HER VOICE:\n" + ex)

# ---------------- voice micro-tuner ----------------
DEFAULT_TUNER = {"cynicism": 50, "focus": 50, "density": 50}

def get_tuner(c=None):
    def load(cn):
        v = db.kv_get(cn, "tuner")
        return {**DEFAULT_TUNER, **json.loads(v)} if v else dict(DEFAULT_TUNER)
    if c is not None:
        return load(c)
    with db.conn() as cn:
        return load(cn)

def tuner_text(t):
    """Turns the three 0-100 sliders into prompt instructions. They only steer style inside the hard voice rules."""
    c, f, d = t["cynicism"], t["focus"], t["density"]
    cyn = ("Tone: pragmatic operator. Plain, dry, no jokes." if c < 34 else "Tone: dry, with an occasional wry aside." if c < 67
           else "Tone: witty insider. Sharper edge, one dry joke allowed per comment (never an exclamation mark).")
    foc = ("Angle: lead with macro unit economics (margins, cost to serve, working capital)." if f < 34 else "Angle: balance economics with incentives." if f < 67
           else "Angle: lead with founder and investor incentives (who gets paid, cap-table and exit pressure).")
    den = ("Length: exactly 2 sentences." if d < 34 else "Length: 2 or 3 sentences, whichever the point needs." if d < 67
           else "Length: exactly 3 sentences, using the full claim, mechanism and closer structure.")
    return f"\n\nSHREYA'S TUNING FOR THIS RUN (stay inside the hard rules above):\n- {cyn}\n- {foc}\n- {den}"

def draft_one(sg, story, tuner=None, instruction=""):
    system = _system(sg) + tuner_text(tuner or get_tuner())
    prompt = (f"Story:\n  Title: {story['title']}\n  Source: {story['source']}\n  Snippet: {story['snippet'] or '(none; reason from structure only)'}\n"
              f"  Selection filter: {story['selection_filter']}\n\n"
              + (f"Extra instruction from Shreya for this rewrite: {instruction}\n\n" if instruction else "") +
              "Write the commentary. Use only facts in the snippet. Return ONLY JSON: {\"commentary\": \"...\"}")
    text, errs = "", []
    for attempt in range(2):
        extra = "" if not errs else "\n\nFailed: " + "; ".join(errs) + ". Rewrite."
        text = gemini.generate(system, prompt + extra, DRAFT_SCHEMA, 0.7)["commentary"].strip()
        errs = validate_commentary(text, story["title"], story["snippet"] or "", sg["banned"])
        if not errs:
            break
    return text, errs

# ---------------- entity memory + trend clusters ----------------
ENT_TYPES = ["STARTUP", "FOUNDER", "INVESTOR", "REGULATOR", "COMPANY", "OTHER"]
ENT_SCHEMA = {"type": "OBJECT", "properties": {"stories": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "id": {"type": "INTEGER"}, "entities": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "name": {"type": "STRING"}, "type": {"type": "STRING", "enum": ENT_TYPES}}, "required": ["name", "type"]}}},
    "required": ["id", "entities"]}}}, "required": ["stories"]}

def extract_entities(stories):
    """{article_id: [{name, type}]} for the anti-duplication entity graph. Only entities present in the title or snippet."""
    block = "\n".join(json.dumps({"id": s["id"], "title": s["title"], "snippet": (s.get("snippet") or "")[:240]}) for s in stories)
    res = gemini.generate("You extract named entities for a startup newsletter's anti-duplication memory.",
        "For each story list the named entities in its title or snippet: startups and companies, founders and executives, investors and VCs, government bodies and regulators (RBI, SEBI, TRAI...). "
        "Use the short canonical name ('Ola Electric', 'Bhavish Aggarwal'). At most 6 per story. Never add an entity that is not in the text.\n" + block, ENT_SCHEMA, 0.1)
    return {x["id"]: x["entities"][:6] for x in res.get("stories", [])}

TREND_SCHEMA = {"type": "OBJECT", "properties": {"clusters": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "name": {"type": "STRING"}, "sectors": {"type": "ARRAY", "items": {"type": "STRING", "enum": TOPICS}},
    "article_ids": {"type": "ARRAY", "items": {"type": "INTEGER"}}, "insight": {"type": "STRING"}},
    "required": ["name", "sectors", "article_ids", "insight"]}}}, "required": ["clusters"]}

def cluster_trends(cands):
    cj = "\n".join(json.dumps({"id": a["id"], "title": a["title"]}) for a in cands)
    res = gemini.generate("You find emerging trend clusters across a week of Indian startup news.",
        "Group these articles into 6 to 10 trend clusters (for example 'Quick-commerce dark stores' or 'RBI rules on prepaid instruments'). Each cluster needs at least 3 articles; ignore noise. "
        f"'sectors' lists which of these sectors the cluster touches: {', '.join(TOPICS)}. If a cluster connects two or more different sectors, 'insight' is one line naming the link nobody has stated; otherwise an empty string.\n" + cj, TREND_SCHEMA, 0.2)
    ids = {a["id"] for a in cands}
    out = []
    for cl in res.get("clusters", []):
        aids = [i for i in cl["article_ids"] if i in ids]
        if len(aids) >= 2:
            out.append({"name": cl["name"], "sectors": cl["sectors"][:4], "article_ids": aids, "insight": cl.get("insight", "")})
    return out

def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None

# ---------------- devil's advocate, trend fusion, subject lines, voice notes ----------------
ANGLE_SCHEMA = {"type": "OBJECT", "properties": {
    "stories": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"id": {"type": "INTEGER"}, "counter": {"type": "ARRAY", "items": {"type": "STRING"}}}, "required": ["id", "counter"]}},
    "fusions": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"a": {"type": "INTEGER"}, "b": {"type": "INTEGER"}, "angle": {"type": "STRING"}}, "required": ["a", "b", "angle"]}}},
    "required": ["stories", "fusions"]}

def angles(stories):
    """Per story: three counter-thesis prompts (what the press may be missing). Across stories: up to three trend fusions. Framed as things to check, never as facts."""
    block = "\n".join(json.dumps({"id": s["id"], "pos": s["pos"], "title": s["title"], "snippet": (s.get("snippet") or "")[:240]}) for s in stories)
    res = gemini.generate("You are a sceptical editor's research assistant for The Dispatch, a newsletter on Indian startups.",
        "For EACH story give exactly 3 short counter-thesis bullets: what the mainstream press may be ignoring (hidden terms, regulatory fine print, unit economics, second-order effects). "
        "Phrase each as something to CHECK or a question to ask, never as a fact. Do not invent numbers, names or clauses that are not in the text.\n"
        "Then suggest up to 3 'fusions': pairs of stories (by 'pos') that connect into one trend nobody has stated, with a one-sentence angle Shreya could write.\n" + block, ANGLE_SCHEMA, 0.5)
    by_id = {s["id"] for s in stories}
    return {"counter": {x["id"]: x["counter"][:3] for x in res.get("stories", []) if x["id"] in by_id},
            "fusions": [f for f in res.get("fusions", []) if f["a"] != f["b"]][:3]}

SUBJ_SCHEMA = {"type": "OBJECT", "properties": {"options": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "style": {"type": "STRING", "enum": ["CURIOSITY", "DATA", "PUNCHY"]}, "subject": {"type": "STRING"}, "preheader": {"type": "STRING"}}, "required": ["style", "subject", "preheader"]}}}, "required": ["options"]}

def subject_lines(stories, banned):
    block = "\n".join(f"{s['pos']}. {s['title']} [{s['topic']}]" for s in stories)
    res = gemini.generate("You write email subject lines for Shreya's weekly newsletter on the Indian startup ecosystem. Dry, direct, a little sceptical. Never clickbait that the issue cannot back up.",
        f"Write exactly 3 options, one each: CURIOSITY (an open loop the issue closes), DATA (a concrete number or mechanism taken from the stories), PUNCHY (a short list-style line naming 2-3 topics). "
        f"Subject max 60 characters, preheader max 90. No emojis, no exclamation marks, none of: {', '.join(banned)}. Only use facts present in these headlines. If a headline gives a range or an approximate figure, keep it exactly as written (for example '20,000-30,000'); never round it up or pick one end. If unsure, leave the number out.\n{block}", SUBJ_SCHEMA, 0.8)
    out = []
    for o in res.get("options", [])[:3]:
        if len(o["subject"]) <= 70 and "!" not in o["subject"] and not any(b.lower() in (o["subject"] + o["preheader"]).lower() for b in banned):
            out.append({"style": o["style"], "subject": o["subject"].strip(), "preheader": o["preheader"].strip()[:100]})
    return out

VOICE_SCHEMA = {"type": "OBJECT", "properties": {"transcript": {"type": "STRING"}, "commentary": {"type": "STRING"}}, "required": ["transcript", "commentary"]}

def voice_to_commentary(sg, story, audio, mime="audio/ogg", tuner=None):
    """Shreya's voice note -> transcript + commentary in her voice. Her spoken opinions are hers to assert, so numbers she says are allowed; nothing else is invented."""
    import base64
    system = _system(sg) + tuner_text(tuner or get_tuner())
    prompt = (f"Shreya recorded a voice note with her raw thoughts on this story.\nTitle: {story['title']}\nSource: {story['source']}\nSnippet: {story['snippet'] or '(none)'}\n\n"
              "1) Transcribe the voice note faithfully. 2) Turn her point into the commentary in her voice: it must express HER take (claim, mechanism, closer), "
              "using what she said. Do not add facts, numbers or names she did not say or that are not in the snippet. Return ONLY JSON: {\"transcript\": \"...\", \"commentary\": \"...\"}")
    parts = [{"inline_data": {"mime_type": mime, "data": base64.b64encode(audio).decode()}}, {"text": prompt}]
    out, errs = {"transcript": "", "commentary": ""}, []
    for _ in range(2):
        extra = [] if not errs else [{"text": "Failed: " + "; ".join(errs) + ". Rewrite the commentary."}]
        out = gemini.generate_parts(system, parts + extra, VOICE_SCHEMA, 0.6)
        errs = validate_commentary(out["commentary"].strip(), story["title"], (story["snippet"] or "") + " " + out["transcript"], sg["banned"])
        if not errs:
            break
    return out["commentary"].strip(), out["transcript"].strip(), errs

def run_selection(force=False):
    from app import access
    week = config.week_start()
    with db.conn() as c:
        issue = db.one(c, "SELECT * FROM issues WHERE week=?", (week,))
        if issue and issue["status"] != "collecting" and not force:
            return {"week": week, "skipped": f"issue already {issue['status']}"}
        cands, recent, sg, tuner = candidates(c, week), recent_titles(c, week), styleguide.active(c), get_tuner(c)
        pool_all = db.all(c, "SELECT title, url, source, fingerprint FROM articles WHERE week=?", (week,))
    if len(cands) < config.PICK_MAX:
        return {"week": week, "error": f"only {len(cands)} candidates"}
    res, flag = select(sg, cands, recent)
    by_id = {a["id"]: a for a in cands}
    stories = [{**by_id[s["article_id"]], "selection_filter": s["selection_filter"], "topic": s["topic_area"], "why": s["reason"], "pos": n}
               for n, s in enumerate(res["selected"], 1)]
    backs = [{**by_id[b["article_id"]], "selection_filter": b["selection_filter"], "topic": b["topic_area"], "why": b["reason"]} for b in res["backups"] if b["article_id"] in by_id]
    top3 = backs[:3]
    with ThreadPoolExecutor(12) as ex:   # independent Gemini jobs and link checks run together
        fd = [ex.submit(draft_one, sg, s, tuner) for s in stories]
        fb = [ex.submit(draft_one, sg, s, tuner) for s in top3]
        fs, ft, fe = ex.submit(_safe, score_pool, sg, cands), ex.submit(_safe, cluster_trends, cands), ex.submit(_safe, extract_entities, stories)
        fa, fj = ex.submit(_safe, angles, stories), ex.submit(_safe, subject_lines, stories, sg["banned"])
        fx = ex.submit(_safe, access.diagnose_all, stories + backs[:6], pool_all)
        drafts, bdrafts = [f.result() for f in fd], [f.result() for f in fb]
        scores, trends, ents = fs.result() or {}, ft.result() or [], fe.result() or {}
        ang, subjects, acc = fa.result() or {"counter": {}, "fusions": []}, fj.result() or [], fx.result() or {}
    notes = (res.get("week_theme") or "") + (f"\nFLAG: {flag}" if flag else "")
    now = config.now_ist().isoformat(timespec="seconds")
    with db.conn() as c:
        if issue:
            db.run(c, "DELETE FROM issue_items WHERE issue_id=?", (issue["id"],)); iid = issue["id"]
            db.run(c, "UPDATE articles SET status='new' WHERE week=? AND status='selected'", (week,))
        else:
            iid = db.insert(c, "INSERT INTO issues (week, status, created_at) VALUES (?,?,?)", (week, "collecting", now))
        for s, (text, errs) in zip(stories, drafts):
            a = acc.get(s["id"], {})
            db.run(c, """INSERT INTO issue_items (issue_id, article_id, position, kind, commentary, draft_original, topic, why, selection_filter, flags, entities, counter, access, alt_url, alt_source)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (iid, s["id"], s["pos"], "selected", text, text, s["topic"], s["why"], s["selection_filter"], "; ".join(errs),
                          json.dumps(ents.get(s["id"], [])), json.dumps(ang["counter"].get(s["id"], [])), a.get("access"), a.get("alt_url"), a.get("alt_source")))
            db.run(c, "UPDATE articles SET status='selected', topic=? WHERE id=?", (s["topic"], s["id"]))
        for pos, b in enumerate(backs, 1):
            text = bdrafts[pos - 1][0] if pos <= len(bdrafts) else None
            a = acc.get(b["id"], {})
            db.run(c, """INSERT INTO issue_items (issue_id, article_id, position, kind, commentary, draft_original, topic, why, selection_filter, access, alt_url, alt_source)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (iid, b["id"], pos, "backup", text, text, b["topic"], b["why"], b["selection_filter"], a.get("access"), a.get("alt_url"), a.get("alt_source")))
        db.many(c, "UPDATE articles SET signal=?, signal_filter=? WHERE id=?", [(v[0], v[1], k) for k, v in scores.items()])
        if trends:
            db.kv_set(c, f"trends:{week}", json.dumps({"week": week, "clusters": trends}))
        db.run(c, "UPDATE issues SET status='drafted', approved_at=NULL, reminder_sent=0, drafted_at=?, selection_notes=?, subject_options=?, subject=?, preheader=?, fusions=? WHERE id=?",
               (now, notes, json.dumps(subjects), subjects[0]["subject"] if subjects else None, subjects[0]["preheader"] if subjects else None, json.dumps(ang["fusions"]), iid))
        db.log(c, "select", f"issue {iid}: {len(stories)} picks, style v{sg['version']}, flag={flag}")
    return {"week": week, "issue_id": iid, "picks": len(stories), "topics": sorted({s["topic"] for s in stories}),
            "style_version": sg["version"], "selection_flag": flag, "comment_flags": sum(1 for _, e in drafts if e), "scored": len(scores), "trend_clusters": len(trends),
            "subjects": len(subjects), "access_checked": len(acc)}
