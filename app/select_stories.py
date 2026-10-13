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

from app.ingest_util import in_scope

def candidates_all(c, week):
    """Every non-duplicate, in-scope article of the week (Monday to Wednesday), newest first. No recency cut: Monday's stories compete with Wednesday's."""
    rows = db.all(c, "SELECT id, source, title, snippet, url, published_at FROM articles WHERE week=? AND status='new' ORDER BY published_at DESC", (week,))
    return [a for a in rows if in_scope(a)]

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

PRESCREEN_SCHEMA = {"type": "OBJECT", "properties": {"scores": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "id": {"type": "INTEGER"}, "s": {"type": "INTEGER"}}, "required": ["id", "s"]}}}, "required": ["scores"]}
SHORTLIST = 90

def prescreen(sg, cands):
    """One compact Gemini pass over EVERY candidate headline (chunks run in parallel): editorial signal 0-100 against the three filters."""
    def chunk(items):
        cj = "\n".join(f'{a["id"]}|{a["source"]}|{a["title"]}|{(a["snippet"] or "")[:90]}' for a in items)
        res = gemini.generate("You are the editorial selector for The Dispatch. Triage fast.",
            f"FILTERS:\n{sg['filters']}\n\nScore each candidate 0-100 for how strongly it passes at least one filter (counterintuitive, under-reported, trend-connecting). "
            f"SCOPE: the newsletter covers the INDIAN STARTUP ECOSYSTEM: startups and their founders, venture and private-equity funding, startup IPOs, new-age tech and consumer-internet companies, and regulation or policy that directly affects startups (SEBI, RBI, DPIIT, MeitY, tax or labour rules aimed at them). Stories about large legacy conglomerates (Reliance, Tata, Adani and similar), general economy, GST or tax news with no startup angle, retail or auto results, big-tech moves abroad, and anything outside India score under 25. Press releases, routine funding announcements, listicles and restated headlines score under 30. "
            f"Lines are id|source|headline|snippet. Return every id.\n{cj}", PRESCREEN_SCHEMA, 0.1)
        return {x["id"]: max(0, min(100, int(x["s"]))) for x in res.get("scores", [])}
    parts = [cands[i::10] for i in range(10)]        # ~60 headlines per call: small enough to answer fast and reliably
    out = {}
    with ThreadPoolExecutor(10) as ex:
        for r in ex.map(lambda p: _safe(chunk, p) or {}, parts):
            out.update(r)
    return out

def shortlist(cands, pre):
    """Top SHORTLIST by pre-screen score with a per-source cap for variety. Hand-picked stories always go through."""
    ranked = sorted(cands, key=lambda a: (a["source"] == "Added by Shreya", pre.get(a["id"], -1)), reverse=True)
    per, out = {}, []
    for a in ranked:
        if a["source"] == "Added by Shreya" or per.get(a["source"], 0) < 14:
            out.append(a); per[a["source"]] = per.get(a["source"], 0) + 1
        if len(out) >= SHORTLIST:
            break
    return out

def select(sg, cands, recent):
    ids = {a["id"]: a for a in cands}
    system = ("You are the editorial selector for The Dispatch, a weekly newsletter on the Indian startup ecosystem. "
              "You select; you do not write commentary in this step.")
    cj = "\n".join(json.dumps({"article_id": a["id"], "title": a["title"], "source": a["source"], "snippet": (a["snippet"] or "")[:240]}) for a in cands)
    base = (f"From the candidate list, choose exactly {config.PICK_TARGET} stories (never fewer than {config.PICK_MIN}) that:\n"
            "- each satisfy at least one filter: COUNTERINTUITIVE, UNDER-REPORTED, TREND-CONNECTING (definitions below)\n"
            f"- collectively cover at least {config.MIN_TOPICS} different topic areas\n"
            "- are not about a company-event already listed in RECENT_ISSUES\n"
            "- are high signal relative to this week's batch (reject press releases, pure funding announcements and restated headlines)\n"
            "- are not two stories about the same event\n"
            "- are about the INDIAN STARTUP ECOSYSTEM: startups, founders, venture/PE funding, startup IPOs, new-age tech companies, or policy that directly affects startups. "
            "Reject stories about large legacy conglomerates, general economy or tax news with no startup angle, and anything outside India. At least 8 of the stories must be squarely about startups or startup funding/policy\n"
            "- candidates whose source is 'Added by Shreya' were hand-picked by her this week: include them unless they break these rules (already covered recently, or not about India's startup ecosystem)\n\n"
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

KNOWN = set("""India Indian Indians Indias Rs Cr FY RBI SEBI NPCI UPI IPO EV AI GST FDI NBFC NBFCs ED CEO CFO UK US USA UAE EU IIT IIM Q1 Q2 Q3 Q4 ESOP OFS DRHP RHP
              Diwali Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August September October November December
              Google Meta Amazon Microsoft Apple Reliance Tata Paytm Flipkart Swiggy Zomato
              SaaS NPA NPAs CAC LTV GMV AUM ARR MRR KYC PPI QR SME MSME VC VCs PE B2B B2C D2C Series Combinator YC Nasdaq NSE BSE SEZ MDR AA OTT GPU GPUs LLM LLMs API APIs OEM OEMs""".split())

def ungrounded_names(text, source):
    """Capitalised names in the commentary that appear nowhere in the story's own text: a sign Gemini embellished. Sentence-initial words are ignored."""
    src = source.lower()
    out = []
    for sent in re.split(r"(?<=[.?])\s+", text):
        for w in re.findall(r"\b[A-Z][A-Za-z&]{2,}\b", sent)[1:] if sent[:1].isupper() else re.findall(r"\b[A-Z][A-Za-z&]{2,}\b", sent):
            if w not in KNOWN and w.lower() not in src and w not in out:
                out.append(w)
    return out

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
    ug = ungrounded_names(text, src)
    if ug:
        errs.append(f"names not in the source: {', '.join(ug[:3])}")
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
        {"rule": "Names come from the source", "ok": not ungrounded_names(text, src), "detail": ", ".join(ungrounded_names(text, src)[:3]) or "all grounded"},
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

def draft_one(sg, story, tuner=None, instruction="", fast=False, temperature=0.7):
    system = _system(sg) + tuner_text(tuner or get_tuner())
    body = (story.get("body") or "")[:1800]
    prompt = (f"Story:\n  Title: {story['title']}\n  Source: {story['source']}\n  Snippet: {story['snippet'] or '(none; reason from structure only)'}\n"
              + (f"  Article text (extract): {body}\n" if body else "") + f"  Selection filter: {story['selection_filter']}\n\n"
              + (f"Extra instruction from Shreya for this rewrite: {instruction}\n\n" if instruction else "") +
              "Write the commentary. Use only facts in the snippet. Return ONLY JSON: {\"commentary\": \"...\"}")
    text, errs = "", []
    for attempt in range(2):
        extra = "" if not errs else "\n\nFailed: " + "; ".join(errs) + ". Rewrite."
        text = gemini.generate(system, prompt + extra, DRAFT_SCHEMA, temperature, fast)["commentary"].strip()
        errs = validate_commentary(text, story["title"], (story["snippet"] or "") + " " + body, sg["banned"])
        if not errs:
            break
    return text, errs

JUDGE_SCHEMA = {"type": "OBJECT", "properties": {"best": {"type": "INTEGER"}, "why": {"type": "STRING"}}, "required": ["best", "why"]}

def judge(sg, story, cands):
    """An editor's pass: which of several valid drafts would Shreya be proudest to publish? Returns the index."""
    block = "\n".join(f"[{i}] {c}" for i, c in enumerate(cands))
    res = gemini.generate("You are the editor-in-chief of the sharpest newsletter on the Indian startup ecosystem. You pick the best commentary, not the safest.",
        f"Story: {story['title']}\nSnippet: {story['snippet'] or '(none)'}\nArticle text: {(story.get('body') or '')[:900]}\n\nCandidate commentaries:\n{block}\n\n"
        "Pick the one a founder or investor would learn the most from. Prefer: a claim that stands without the headline; a concrete mechanism or number taken from the text; "
        "the incentive behind the move; a closer that is testable (what to watch) rather than a moral; a dry, sceptical, never-hyped voice; varied rhythm. "
        "Reject anything that could sit under any other story, restates the headline, hedges, or asserts a fact the text does not give. Return the index in 'best'.",
        JUDGE_SCHEMA, 0.1)
    b = res.get("best", 0)
    return b if isinstance(b, int) and 0 <= b < len(cands) else 0

def draft_best(sg, story, tuner=None, n=3):
    """Several drafts, validated against every hard rule, then the editor's pick. Used for the Wednesday pass; taps stay single and fast."""
    pool = []
    for _ in range(n):
        try:
            text, errs = draft_one(sg, story, tuner, fast=True, temperature=0.95)
        except Exception:
            continue
        if not errs and text and text not in [t for t, _ in pool]:
            pool.append((text, errs))
    if not pool:                                    # nothing passed the rules: fall back to the careful single draft
        return draft_one(sg, story, tuner)
    if len(pool) == 1:
        return pool[0]
    try:
        return pool[judge(sg, story, [t for t, _ in pool])]
    except Exception:
        return pool[0]

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

KEY_TYPES = ("STARTUP", "COMPANY", "FOUNDER", "INVESTOR")

def recent_entity_keys(c, week):
    """Companies, founders and investors named in the last four issues' stories (lower-case), for the repeat guard."""
    rows = db.all(c, """SELECT i.entities FROM issue_items i JOIN issues s ON s.id=i.issue_id
                        WHERE i.kind='selected' AND s.week IN (SELECT week FROM issues WHERE week < ? ORDER BY week DESC LIMIT ?)""", (week, config.LOOKBACK_ISSUES))
    out = set()
    for r in rows:
        try:
            out |= {e["name"].strip().lower() for e in json.loads(r["entities"] or "[]") if e["type"] in KEY_TYPES}
        except Exception:
            pass
    return out

def repeat_guard(stories, backs, ents, past_keys):
    """Swap out any pick that names a company/person already in this issue or in the last four issues, using the best runner-up that does not.
    Returns (final_stories, remaining_backups, replaced) where replaced is [{title, reason}]. Keeps the sector spread; if it cannot, it leaves the original picks alone."""
    keys = lambda sid: {e["name"].strip().lower() for e in ents.get(sid, []) if e["type"] in KEY_TYPES}
    pool, final, used, replaced = list(backs), [], set(), []
    for st in stories:
        ks = keys(st["id"])
        if ks & used or ks & past_keys:
            alt = next((b for b in pool if not (keys(b["id"]) & (used | past_keys))), None)
            if alt:
                clash = sorted((ks & used) | (ks & past_keys))
                pool.remove(alt); final.append(alt); used |= keys(alt["id"])
                replaced.append({"title": st["title"], "reason": ("repeats " + ", ".join(clash) + (" (already in this issue)" if ks & used else " (covered in the last four issues)")) if clash else "repeat"}); continue
        final.append(st); used |= ks
    if len({x["topic"] for x in final}) < config.MIN_TOPICS or len(final) < config.PICK_MIN:
        return stories, backs, []
    pool = [b for b in pool if not (keys(b["id"]) & (used | past_keys))]      # runner-ups must not be repeats either
    for n, st in enumerate(final, 1):
        st["pos"] = n
    return final, pool, replaced

def fuse(sg, a, b, tuner=None, fast=True):
    """Trend-Connecting commentary for two stories: one block that names the link between them. Preview only."""
    system = _system(sg) + tuner_text(tuner or get_tuner())
    block = "\n\n".join(f"Story {n}: {x['title']} ({x['source']})\nSnippet: {x['snippet'] or '(none)'}\nArticle text: {(x.get('source_text') or '')[:900]}" for n, x in ((1, a), (2, b)))
    prompt = (f"{block}\n\nWrite ONE commentary block in Shreya's voice that connects these two stories into a trend nobody has stated yet (TREND-CONNECTING). "
              "Name both developments, state the link as the claim, give the mechanism, close with what to watch. Use only facts present above; never invent figures. "
              "Return ONLY JSON: {\"commentary\": \"...\"}")
    text, errs = "", []
    for _ in range(2):
        extra = "" if not errs else "\n\nFailed: " + "; ".join(errs) + ". Rewrite."
        text = gemini.generate(system, prompt + extra, DRAFT_SCHEMA, 0.7, fast)["commentary"].strip()
        errs = validate_commentary(text, a["title"] + " " + b["title"], f"{a['snippet'] or ''} {b['snippet'] or ''} {a.get('source_text') or ''} {b.get('source_text') or ''}", sg["banned"])
        if not errs:
            break
    return text, errs

SCOPE_SCHEMA = {"type": "OBJECT", "properties": {"verdicts": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "id": {"type": "INTEGER"}, "ok": {"type": "BOOLEAN"}, "why": {"type": "STRING"}}, "required": ["id", "ok"]}}}, "required": ["verdicts"]}

def scope_check(items):
    """Independent Gemini check: is each story squarely about the Indian startup ecosystem? -> {id: bool}. Fails open (an outage must not block a draft)."""
    cj = "\n".join(f'{a["id"]}|{a["source"]}|{a["title"]}|{(a.get("snippet") or "")[:200]}' for a in items)
    res = _safe(gemini.generate, "You are a strict scope editor for The Dispatch, a newsletter on the Indian startup ecosystem.",
        "A story is IN SCOPE only if it is about Indian startups and founders, venture or private-equity funding of Indian companies, startup IPOs, new-age tech or consumer-internet "
        "companies in India, or policy that directly affects startups. It is OUT of scope if it is mainly about a large legacy conglomerate, general economy, GST or tax news with no startup angle, "
        "listed-company quarterly results, big tech abroad, or a company outside India. Lines are id|source|headline|snippet. Return a verdict for every id.\n" + cj, SCOPE_SCHEMA, 0.0)
    return {v["id"]: bool(v["ok"]) for v in (res or {}).get("verdicts", [])}

def mark_scope(c, week, limit=900):
    """Ingestion-time scope check: every newly stored article is classified once; anything not squarely about the Indian startup ecosystem is set aside
    (status 'out_of_scope') so it never reaches scoring, the shortlist, the runner-ups or the headline counts. Fails open per chunk."""
    from concurrent.futures import ThreadPoolExecutor
    rows = [dict(r) for r in db.all(c, "SELECT id, source, title, snippet FROM articles WHERE week=? AND status='new' AND COALESCE(scope_checked,0)=0 LIMIT ?", (week, limit))]
    if not rows:
        return {"checked": 0, "out_of_scope": 0}
    chunks = [rows[i:i + 60] for i in range(0, len(rows), 60)]
    with ThreadPoolExecutor(6) as ex:
        results = list(ex.map(lambda ch: (ch, scope_check(ch)), chunks))
    drop, keep = [], []
    for ch, verdict in results:
        if not verdict:
            continue                                               # a failed chunk stays unchecked and is retried next run
        for a in ch:
            (drop if (a["source"] != "Added by Shreya" and verdict.get(a["id"], True) is False) else keep).append(a["id"])
    for ids, sql in ((drop, "UPDATE articles SET status='out_of_scope', scope_checked=1 WHERE id IN ({})"), (keep, "UPDATE articles SET scope_checked=1 WHERE id IN ({})")):
        for i in range(0, len(ids), 200):                           # a few batched statements, not one round trip per article
            part = ids[i:i + 200]
            db.run(c, sql.format(",".join("?" * len(part))), tuple(part))
    out, checked = len(drop), len(drop) + len(keep)
    return {"checked": checked, "out_of_scope": out}

def scope_guard(stories, backs):
    """Swap any pick that is not squarely Indian startup ecosystem for the next runner-up that is. Keeps count and the 3-topic spread. -> (stories, backs, swapped)."""
    items = stories + backs[:10]
    v1, v2 = scope_check(items), scope_check(list(reversed(items)))          # two independent passes in different order: a story stays only if BOTH say it is in scope
    if not v1 and not v2:
        return stories, backs, []
    verdict = {a["id"]: v1.get(a["id"], True) and v2.get(a["id"], True) for a in items}
    pool, out, swapped = [b for b in backs if verdict.get(b["id"], True)], [], []
    spare = [b for b in backs if not verdict.get(b["id"], True)]
    for st in stories:
        if verdict.get(st["id"], True):
            out.append(st); continue
        alt = pool.pop(0) if pool else None
        if alt:
            out.append(alt); swapped.append({"title": st["title"], "reason": "is not squarely about the Indian startup ecosystem"})
        else:
            out.append(st)
    if len({x["topic"] for x in out}) < config.MIN_TOPICS:
        return stories, backs, []
    for n, st in enumerate(out, 1):
        st["pos"] = n
    return out, (pool if len(pool) >= 3 else pool + spare), swapped

def paywall_guard(stories, backs, acc, ents, past_keys):
    """Subscribers hate clicking into a wall. Swap out any pick behind a HARD paywall that has no free coverage for the best free runner-up
    (one that does not repeat a company), keeping the count and the 3-sector spread. Returns (stories, backs, swapped=[{title, reason}])."""
    keys = lambda sid: {e["name"].strip().lower() for e in ents.get(sid, []) if e["type"] in KEY_TYPES}
    used = set().union(*[keys(x["id"]) for x in stories]) if stories else set()
    pool, out, swapped = list(backs), [], []
    for st in stories:
        a = acc.get(st["id"], {})
        if a.get("access") == "hard" and not a.get("alt_url"):
            others = used - keys(st["id"])
            alt = next((b for b in pool if acc.get(b["id"], {}).get("access") == "free" and not (keys(b["id"]) & (others | past_keys))), None)
            if alt:
                pool.remove(alt); out.append(alt); used = others | keys(alt["id"])
                swapped.append({"title": st["title"], "reason": "is behind a hard paywall with no free coverage"})
                continue
        out.append(st)
    if len({x["topic"] for x in out}) < config.MIN_TOPICS:
        return stories, backs, []
    for n, st in enumerate(out, 1):
        st["pos"] = n
    return out, pool, swapped

def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None

# ---------------- devil's advocate, trend fusion, subject lines, voice notes ----------------
ANGLE_SCHEMA = {"type": "OBJECT", "properties": {
    "stories": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"id": {"type": "INTEGER"}, "counter": {"type": "ARRAY", "items": {"type": "STRING"}},
                "quotes": {"type": "ARRAY", "items": {"type": "STRING"}}}, "required": ["id", "counter", "quotes"]}},
    "fusions": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"a": {"type": "INTEGER"}, "b": {"type": "INTEGER"}, "angle": {"type": "STRING"}}, "required": ["a", "b", "angle"]}}},
    "required": ["stories", "fusions"]}

def _angles_once(stories):
    """Per story: three counter-thesis prompts (what the press may be missing). Across stories: up to three trend fusions. Framed as things to check, never as facts."""
    block = "\n".join(json.dumps({"id": s["id"], "pos": s["pos"], "title": s["title"], "snippet": (s.get("snippet") or "")[:240], "article_text": (s.get("body") or "")[:1500]}) for s in stories)
    res = gemini.generate("You are a sceptical editor's research assistant for The Dispatch, a newsletter on Indian startups.",
        "For EACH story give exactly 3 short counter-thesis bullets: what the mainstream press may be ignoring (hidden terms, regulatory fine print, unit economics, second-order effects). "
        "Phrase each as something to CHECK or a question to ask, never as a fact. Do not invent numbers, names or clauses that are not in the text.\n"
        "Then suggest up to 3 'fusions': pairs of stories (by 'pos') that connect into one trend nobody has stated, with a one-sentence angle Shreya could write.\n" + block, ANGLE_SCHEMA, 0.5)
    by_id = {s["id"] for s in stories}
    body = {s["id"]: s.get("body") or "" for s in stories}
    quotes = {x["id"]: [q.strip() for q in x.get("quotes", []) if q.strip() and q.strip() in body.get(x["id"], "")][:2] for x in res.get("stories", []) if x["id"] in by_id}   # verbatim only
    return {"quotes": quotes, "counter": {x["id"]: x["counter"][:3] for x in res.get("stories", []) if x["id"] in by_id},
            "fusions": [f for f in res.get("fusions", []) if f["a"] != f["b"]][:3]}

def angles(stories):
    """Counter-thesis prompts for every story. If Gemini skips a story, ask again for just those, so no card is left without them."""
    out = _angles_once(stories)
    missing = [x for x in stories if not out["counter"].get(x["id"])]
    if missing:
        try:
            more = _angles_once(missing)
            out["counter"].update({k: v for k, v in more["counter"].items() if v})
            out["quotes"].update({k: v for k, v in more.get("quotes", {}).items() if v})
        except Exception:
            pass
    return out

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

def voice_to_commentary(sg, story, audio, mime="audio/ogg", tuner=None, fast=True):
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
        out = gemini.generate_parts(system, parts + extra, VOICE_SCHEMA, 0.6, fast)
        errs = validate_commentary(out["commentary"].strip(), story["title"], (story["snippet"] or "") + " " + out["transcript"], sg["banned"])
        if not errs:
            break
    return out["commentary"].strip(), out["transcript"].strip(), errs

def run_selection(force=False):
    import time
    from app import access
    T0 = time.time(); tm = {}
    lap = lambda k: tm.__setitem__(k, round(time.time() - T0)) 
    week = config.week_start()
    with db.conn() as c:
        issue = db.one(c, "SELECT * FROM issues WHERE week=?", (week,))
        if issue and issue["status"] != "collecting" and not force:
            return {"week": week, "skipped": f"issue already {issue['status']}"}
        all_cands, recent, sg, tuner = candidates_all(c, week), recent_titles(c, week), styleguide.active(c), get_tuner(c)
        pool_all = db.all(c, "SELECT title, url, source, fingerprint FROM articles WHERE week=?", (week,))
    if len(all_cands) < config.PICK_MAX:
        return {"week": week, "error": f"only {len(all_cands)} candidates"}
    pre = prescreen(sg, all_cands); lap('prescreen')
    cands = shortlist(all_cands, pre) if len(pre) > SHORTLIST // 2 else all_cands[:SHORTLIST]      # if the pre-screen failed, fall back to the newest
    res, flag = select(sg, cands, recent); lap('select')
    by_id = {a["id"]: a for a in cands}
    stories = [{**by_id[s["article_id"]], "selection_filter": s["selection_filter"], "topic": s["topic_area"], "why": s["reason"], "pos": n}
               for n, s in enumerate(res["selected"], 1)]
    backs = [{**by_id[b["article_id"]], "selection_filter": b["selection_filter"], "topic": b["topic_area"], "why": b["reason"]} for b in res["backups"] if b["article_id"] in by_id]
    ents = _safe(extract_entities, stories + backs[:10]) or {}; lap('entities')
    with db.conn() as c:
        past_keys = recent_entity_keys(c, week)
    stories, backs, off_scope = scope_guard(stories, backs)
    if off_scope:
        ents = _safe(extract_entities, stories + backs[:10]) or ents
    stories, backs, replaced = repeat_guard(stories, backs, ents, past_keys)
    replaced = off_scope + replaced
    acc = _safe(access.diagnose_all, stories + backs[:8], pool_all) or {}        # which links open freely? done before the final pick so a wall can be avoided
    stories, backs, walled = paywall_guard(stories, backs, acc, ents, past_keys)
    replaced = replaced + walled
    top3 = backs[:3]
    from app import readable
    with ThreadPoolExecutor(10) as ex:         # real article text for the source pane, key quotes and richer commentary (Google News links cannot be read)
        for st, got in zip(stories + top3, ex.map(lambda x: _safe(readable.extract, x["url"]), stories + top3)):
            st["body"] = (got or {}).get("text") or ""
    lap('article_text')
    with ThreadPoolExecutor(12) as ex:   # independent Gemini jobs and link checks run together
        fd = [ex.submit(draft_best, sg, s, tuner, 3) for s in stories]      # best of three, picked by an editor's judge
        fb = [ex.submit(draft_best, sg, s, tuner, 2) for s in top3]
        fs, ft = ex.submit(_safe, score_pool, sg, cands), ex.submit(_safe, cluster_trends, cands)
        fa, fj = ex.submit(_safe, angles, stories), ex.submit(_safe, subject_lines, stories, sg["banned"])
        drafts, bdrafts = [f.result() for f in fd], [f.result() for f in fb]
        scores, trends = fs.result() or {}, ft.result() or []
        ang, subjects = fa.result() or {"counter": {}, "fusions": []}, fj.result() or []
        missing = [x for x in stories + backs[:6] if x["id"] not in acc]
        if missing:
            acc.update(_safe(access.diagnose_all, missing, pool_all) or {})
    lap('parallel_jobs')
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
            db.run(c, """INSERT INTO issue_items (issue_id, article_id, position, kind, commentary, draft_original, topic, why, selection_filter, flags, entities, counter, access, alt_url, alt_source, source_text, quotes)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (iid, s["id"], s["pos"], "selected", text, text, s["topic"], s["why"], s["selection_filter"], "; ".join(errs),
                          json.dumps(ents.get(s["id"], [])), json.dumps(ang["counter"].get(s["id"], [])), a.get("access"), a.get("alt_url"), a.get("alt_source"),
                          s.get("body") or None, json.dumps(ang.get("quotes", {}).get(s["id"], []))))
            db.run(c, "UPDATE articles SET status='selected', topic=? WHERE id=?", (s["topic"], s["id"]))
        for pos, b in enumerate(backs, 1):
            text = bdrafts[pos - 1][0] if pos <= len(bdrafts) else None
            a = acc.get(b["id"], {})
            db.run(c, """INSERT INTO issue_items (issue_id, article_id, position, kind, commentary, draft_original, topic, why, selection_filter, access, alt_url, alt_source)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (iid, b["id"], pos, "backup", text, text, b["topic"], b["why"], b["selection_filter"], a.get("access"), a.get("alt_url"), a.get("alt_source")))
        db.run(c, "UPDATE articles SET signal=NULL, signal_filter=NULL WHERE week=?", (week,))      # drop scores from earlier runs so the funnel is honest
        db.many(c, "UPDATE articles SET signal=? WHERE id=? AND signal_filter IS NULL", [(v, k) for k, v in pre.items()])      # everyone gets a pre-screen score
        db.many(c, "UPDATE articles SET signal=?, signal_filter=? WHERE id=?", [(v[0], v[1], k) for k, v in scores.items()])      # the shortlist gets the detailed score
        if trends:
            db.kv_set(c, f"trends:{week}", json.dumps({"week": week, "clusters": trends}))
        db.kv_set(c, f"repeat_dropped:{week}", json.dumps(replaced))
        db.run(c, "UPDATE issues SET status='drafted', approved_at=NULL, reminder_sent=0, drafted_at=?, selection_notes=?, subject_options=?, subject=?, preheader=?, fusions=? WHERE id=?",
               (now, notes, json.dumps(subjects), subjects[0]["subject"] if subjects else None, subjects[0]["preheader"] if subjects else None, json.dumps(ang["fusions"]), iid))
        db.log(c, "select", f"issue {iid}: {len(stories)} picks, style v{sg['version']}, flag={flag}")
    return {"week": week, "issue_id": iid, "picks": len(stories), "topics": sorted({s["topic"] for s in stories}),
            "style_version": sg["version"], "selection_flag": flag, "comment_flags": sum(1 for _, e in drafts if e), "scored": len(scores), "trend_clusters": len(trends),
            "subjects": len(subjects), "access_checked": len(acc), "repeats_replaced": [r["title"] for r in replaced], "prescreened": len(pre), "shortlisted": len(cands), "seconds": round(time.time() - T0), "timings": tm}
