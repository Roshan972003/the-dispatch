"""Seed a sample subscriber list into whichever database .env points at. Safe to re-run.
Addresses use Resend's test inboxes (delivered+x@resend.dev, bounced+x@resend.dev, complained+x@resend.dev),
so test sends never reach real people and never hurt the sender's reputation. Rows are tagged note='sample'."""
import sys, csv, secrets
sys.path.insert(0, ".")
from app import db, config

NAMES = ["priya.sharma", "arjun.mehta", "ananya.iyer", "rohan.gupta", "sneha.reddy", "vikram.singh", "kavya.nair", "aditya.rao",
         "ishita.bose", "karthik.menon", "neha.kapoor", "rahul.verma", "divya.pillai", "siddharth.jain", "meera.krishnan",
         "aman.khanna", "pooja.desai", "nikhil.agarwal", "riya.malhotra", "varun.chopra", "tanvi.shah", "harsh.vyas",
         "aditi.joshi", "manish.tiwari", "sakshi.bhatt", "gaurav.saxena", "shreya.kulkarni", "deepak.nambiar", "lakshmi.venkat", "yash.thakur"]
rows = [(f"delivered+{n}@resend.dev", "active") for n in NAMES]
rows += [(f"delivered+pending{i}@resend.dev", "pending") for i in (1, 2, 3)]
rows += [(f"delivered+left{i}@resend.dev", "unsubscribed") for i in (1, 2, 3)]
rows += [("bounced+old1@resend.dev", "bounced"), ("bounced+old2@resend.dev", "bounced"), ("complained+old1@resend.dev", "complained")]
rows += [("bounced+live@resend.dev", "active")]   # active but will hard-bounce on the next send: exercises the bounce handler end to end

now = config.now_ist().isoformat(timespec="seconds")
added = 0
with db.conn() as c:
    for email, status in rows:
        if db.one(c, "SELECT id FROM subscribers WHERE email=?", (email,)):
            continue
        db.run(c, "INSERT INTO subscribers (email, status, token, created_at, status_changed_at, note) VALUES (?,?,?,?,?,'sample')",
               (email, status, secrets.token_urlsafe(24), now, now)); added += 1
    out = db.all(c, "SELECT status, COUNT(*) AS n FROM subscribers GROUP BY status ORDER BY status")
print(f"added {added}; totals by status: " + ", ".join(f"{r['status']}={r['n']}" for r in out))
with open("sample_subscribers.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["email", "status"]); w.writerows(rows)
