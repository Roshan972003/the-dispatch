"""One-off: copy the local SQLite data into Neon, keeping ids, then fix the id sequences."""
import sys, sqlite3
sys.path.insert(0, ".")
import psycopg
from app import config, db

assert db.PG, "DATABASE_URL must point at Postgres"
src = sqlite3.connect(config.DB_PATH); src.row_factory = sqlite3.Row
TABLES = ["feeds", "articles", "issues", "issue_items", "style_guide", "edits", "subscribers", "sends", "events"]
with db.conn() as c:                       # also creates the schema on Neon
    for t in TABLES:
        rows = [dict(r) for r in src.execute(f"SELECT * FROM {t}")]
        c.execute(f"DELETE FROM {t}")
        for r in rows:
            cols = ", ".join(r); ph = ", ".join(["%s"] * len(r))
            c.execute(f"INSERT INTO {t} ({cols}) VALUES ({ph})", list(r.values()))
        c.execute(f"SELECT setval(pg_get_serial_sequence('{t}','id'), COALESCE((SELECT MAX(id) FROM {t}), 1), (SELECT COUNT(*) > 0 FROM {t}))")
        print(f"{t}: {len(rows)} rows")
