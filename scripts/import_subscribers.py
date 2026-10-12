"""Import Shreya's existing subscriber list (one-off). Her current readers already opted in, so they go in as ACTIVE
(new sign-ups on the website still use the confirm-by-email step).

  ./venv/bin/python scripts/import_subscribers.py path/to/list.csv        # CSV with an 'email' column, or one address per line
  ./venv/bin/python scripts/import_subscribers.py list.csv --dry-run      # validate only
Uses whichever database DATABASE_URL points at (Neon in production)."""
import sys, csv, re
sys.path.insert(0, ".")
from app import mailer, db

path = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
if not path:
    sys.exit(__doc__)
raw = open(path, newline="", encoding="utf-8-sig").read()
emails = []
try:
    rows = list(csv.DictReader(raw.splitlines()))
    col = next((k for k in (rows[0] if rows else {}) if k and k.strip().lower() in ("email", "e-mail", "email address")), None)
    emails = [r[col] for r in rows if col and r.get(col)]
except Exception:
    pass
if not emails:
    emails = re.findall(r"[^\s,;\"']+@[^\s,;\"']+\.[^\s,;\"']+", raw)
emails = list(dict.fromkeys(e.strip().lower() for e in emails))
bad = [e for e in emails if not mailer.EMAIL_RE.match(e)]
print(f"{len(emails)} unique addresses found, {len(bad)} look invalid" + (f": {bad[:5]}" if bad else ""))
if "--dry-run" in sys.argv:
    sys.exit(0)
res = mailer.import_subscribers([e for e in emails if e not in bad])
with db.conn() as c:
    n = db.one(c, "SELECT COUNT(*) AS n FROM subscribers WHERE status='active'")["n"]
print(f"imported {res['imported']} (skipped {res['invalid']} invalid); active subscribers now: {n}")
