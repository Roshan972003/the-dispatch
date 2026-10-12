"""Generate a realistic SAMPLE list: 2,200 active subscribers plus a small, realistic tail of unsubscribed / bounced / complained.
Names and join dates are invented; every address is a Resend test inbox (delivered+name@resend.dev), so nothing can reach a real person.
All rows are tagged note='sample'. Re-runnable: it only tops the list up to the target.   ./venv/bin/python scripts/seed_sample_2200.py"""
import sys, random, secrets
from datetime import datetime, timedelta
sys.path.insert(0, ".")
from app import db, config

TARGET_ACTIVE = 2200
random.seed(2200)
FIRST = ("Aarav Aditi Aditya Akash Ananya Anika Anil Anjali Arjun Aryan Bhavna Chirag Deepak Devika Divya Gaurav Harsh Isha Ishaan Jaya Karan Kavya Kiran Krishna "
         "Lakshmi Manish Meera Mohan Neha Nikhil Nisha Pooja Pranav Priya Rahul Raj Rhea Rohan Sakshi Sanjay Sara Shreya Siddharth Sneha Suresh Tanvi Uday Varun Vikram Vishal Yash Zoya").split()
LAST = ("Agarwal Bansal Bhatt Bose Chopra Desai Gupta Iyer Jain Joshi Kapoor Khanna Krishnan Kulkarni Malhotra Mehta Menon Nair Pillai Rao Reddy Saxena Shah Sharma "
        "Singh Sinha Thakur Tiwari Varma Venkat Verma Vyas").split()
NOW = datetime.utcnow() + timedelta(hours=5, minutes=30)
iso = lambda d: d.isoformat(timespec="seconds")

with db.conn() as c:
    have = {r["email"] for r in db.all(c, "SELECT email FROM subscribers")}
    active = db.one(c, "SELECT COUNT(*) AS n FROM subscribers WHERE status='active'")["n"]
    extra_exists = db.one(c, "SELECT COUNT(*) AS n FROM subscribers WHERE note='sample' AND name IS NOT NULL")["n"]
    need = max(0, TARGET_ACTIVE - active)
    plan = [("active", need)]
    if not extra_exists:        # the realistic tail, added once
        plan += [("unsubscribed", 38), ("bounced", 14), ("complained", 3), ("pending", 6)]
    rows, k = [], 0
    for status, n in plan:
        made = 0
        while made < n:
            k += 1
            f, l = random.choice(FIRST), random.choice(LAST)
            email = f"delivered+{f.lower()}.{l.lower()}.{k}@resend.dev" if status in ("active", "pending", "unsubscribed") else f"{status[:-1] if status == 'bounced' else 'complained'}+{f.lower()}.{l.lower()}.{k}@resend.dev"
            if email in have:
                continue
            have.add(email); made += 1
            joined = NOW - timedelta(days=random.triangular(1, 730, 500), hours=random.randint(0, 23))      # more recent joins than old ones
            changed = joined if status in ("active", "pending") else min(NOW, joined + timedelta(days=random.randint(5, 300)))
            reason = random.choices(["Too many emails", "Not relevant to me", "I never signed up", "Other"], [28, 38, 14, 20])[0] if status == "unsubscribed" else None
            note = "sample" if status in ("active", "pending", "unsubscribed") else "sample"
            rows.append((email, status, secrets.token_urlsafe(24), iso(joined), iso(changed), note, f"{f} {l}", reason))
    db.many(c, "INSERT INTO subscribers (email, status, token, created_at, status_changed_at, note, name, unsub_reason) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(email) DO NOTHING", rows)
    counts = db.all(c, "SELECT status, COUNT(*) AS n FROM subscribers GROUP BY status ORDER BY status")
print(f"added {len(rows)} sample subscribers. totals: " + ", ".join(f"{r['status']}={r['n']}" for r in counts))
