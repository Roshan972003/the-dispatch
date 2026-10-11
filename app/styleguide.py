"""Versioned style guide loaded from style_guide.md (Shreya's voice spec). Older versions are never overwritten."""
import re, json
from app import config, db

def _parse(md):
    s1 = md.index("## 1. Editorial philosophy"); s3 = md.index("## 3. Few-shot examples"); s4 = md.index("## 4.")
    rules = md[s1:s3].strip()
    banned = re.findall(r"`([^`]+)`", md[md.index("### Banned phrases"):s3])
    examples = [{"filter": f, "headline": h.strip(), "snippet": sn.strip(), "commentary": cm.strip()} for f, h, sn, cm in re.findall(
        r"### Example \d+: ([A-Z-]+)\s+\*\*Headline:\*\* (.+?)\n\*\*Snippet:\*\* (.+?)\n\*\*Commentary:\*\* (.+?)\n", md[s3:s4], re.S)]
    filters = md[md.index("### The three selection filters"):md.index("## 2. Voice rules")].strip()
    return rules, banned, examples, filters

def active(c):
    row = db.one(c, "SELECT * FROM style_guide WHERE is_active=1 ORDER BY version DESC LIMIT 1")
    if not row:
        rules, banned, examples, _ = _parse((config.ROOT / "style_guide.md").read_text())
        db.run(c, "INSERT INTO style_guide (version, rules, banned, examples, is_active, created_at) VALUES (1,?,?,?,1,?)",
               (rules, json.dumps(banned), json.dumps(examples), config.now_ist().isoformat(timespec="seconds")))
        row = db.one(c, "SELECT * FROM style_guide WHERE is_active=1 ORDER BY version DESC LIMIT 1")
    row["banned"] = json.loads(row["banned"]); row["examples"] = json.loads(row["examples"])
    row["filters"] = _parse((config.ROOT / "style_guide.md").read_text())[3]
    return row

def promote_edits(c, n=3):
    """Promote Shreya's recent edits into a NEW style-guide version as extra examples (spec section 7). Returns new version or None."""
    pend = db.all(c, """SELECT e.id, e.shreya_edit, a.title, a.snippet FROM edits e JOIN articles a ON a.id=e.article_id
                        WHERE e.promoted=0 ORDER BY e.id DESC LIMIT ?""", (n,))
    if not pend:
        return None
    cur = active(c)
    ex = cur["examples"] + [{"filter": "SHREYA-EDIT", "headline": p["title"], "snippet": p["snippet"], "commentary": p["shreya_edit"]} for p in pend]
    v = cur["version"] + 1
    db.run(c, "UPDATE style_guide SET is_active=0")
    db.run(c, "INSERT INTO style_guide (version, rules, banned, examples, is_active, created_at) VALUES (?,?,?,?,1,?)",
           (v, cur["rules"], json.dumps(cur["banned"]), json.dumps(ex), config.now_ist().isoformat(timespec="seconds")))
    for p in pend:
        db.run(c, "UPDATE edits SET promoted=1 WHERE id=?", (p["id"],))
    return v
