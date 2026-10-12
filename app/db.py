import sqlite3, time
from contextlib import contextmanager
from app import config

PG = config.DATABASE_URL.startswith("postgres")

SCHEMA = """
CREATE TABLE IF NOT EXISTS feeds (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT UNIQUE, kind TEXT DEFAULT 'rss', active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS articles (
  id INTEGER PRIMARY KEY AUTOINCREMENT, url_hash TEXT UNIQUE, url TEXT, title TEXT, source TEXT, snippet TEXT,
  published_at TEXT, fetched_at TEXT, week TEXT, fingerprint TEXT, topic TEXT,
  status TEXT DEFAULT 'new', dup_of INTEGER
);
CREATE TABLE IF NOT EXISTS issues (
  id INTEGER PRIMARY KEY AUTOINCREMENT, week TEXT UNIQUE, status TEXT DEFAULT 'collecting',
  intro TEXT, created_at TEXT, drafted_at TEXT, approved_at TEXT, sent_at TEXT, reminder_sent INTEGER DEFAULT 0,
  selection_notes TEXT
);
CREATE TABLE IF NOT EXISTS issue_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT, issue_id INTEGER, article_id INTEGER, position INTEGER,
  kind TEXT DEFAULT 'selected', commentary TEXT, topic TEXT, why TEXT, edited INTEGER DEFAULT 0, selection_filter TEXT, flags TEXT, draft_original TEXT, tg_message_id INTEGER, reviewed INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS subscribers (
  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, status TEXT DEFAULT 'active', token TEXT,
  created_at TEXT, status_changed_at TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS sends (
  id INTEGER PRIMARY KEY AUTOINCREMENT, issue_id INTEGER, subscriber_id INTEGER, provider_id TEXT, status TEXT, error TEXT, sent_at TEXT,
  UNIQUE(issue_id, subscriber_id)
);
CREATE TABLE IF NOT EXISTS style_guide (
  id INTEGER PRIMARY KEY AUTOINCREMENT, version INTEGER NOT NULL, rules TEXT NOT NULL, banned TEXT NOT NULL, examples TEXT NOT NULL,
  is_active INTEGER DEFAULT 0, created_at TEXT
);
CREATE TABLE IF NOT EXISTS edits (
  id INTEGER PRIMARY KEY AUTOINCREMENT, article_id INTEGER, gemini_draft TEXT, shreya_edit TEXT, created_at TEXT, promoted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS email_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, issue_id INTEGER, recipient_hash TEXT, link TEXT
);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, detail TEXT
);
"""
PG_SCHEMA = SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")

MIGRATIONS = [("articles", "signal", "INTEGER"), ("articles", "signal_filter", "TEXT"), ("issue_items", "entities", "TEXT"), ("subscribers", "unsub_reason", "TEXT"), ("subscribers", "name", "TEXT"), ("issue_items", "source_text", "TEXT"), ("issue_items", "quotes", "TEXT"),
              ("issue_items", "counter", "TEXT"), ("issue_items", "access", "TEXT"), ("issue_items", "alt_url", "TEXT"), ("issue_items", "alt_source", "TEXT"),
              ("issues", "subject_options", "TEXT"), ("issues", "subject", "TEXT"), ("issues", "preheader", "TEXT"), ("issues", "fusions", "TEXT")]   # columns added after first release
import threading
_SETUP_LOCK = threading.Lock()
_READY = False

_local = threading.local()
IDLE_PING_S = 15        # a reused connection idle longer than this is checked before use (Neon closes idle pooled connections)

def _connect():
    if PG:
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(config.DATABASE_URL, row_factory=dict_row)
    config.DB_PATH.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def _setup(c):
    global _READY
    if _READY:
        return
    with _SETUP_LOCK:               # one thread sets up the schema; the rest wait, then skip
        if _READY:
            return
        if PG:
            c.execute("SELECT pg_advisory_xact_lock(727201)")     # also serialises separate serverless instances
            c.execute(PG_SCHEMA)
        else:
            c.executescript(SCHEMA)
        for t, col, typ in MIGRATIONS:
            if PG:
                have = c.execute("SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s", (t, col)).fetchone()
                if not have:        # ALTER ... IF NOT EXISTS still takes a heavy lock even when it does nothing, so only run it when needed
                    c.execute(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS {col} {typ}")
            elif col not in {r[1] for r in c.execute(f"PRAGMA table_info({t})")}:
                c.execute(f"ALTER TABLE {t} ADD COLUMN {col} {typ}")
        c.commit()
        _READY = True

def _acquire():
    """Postgres: reuse this thread's connection (saves a TLS + auth handshake on every Telegram tap and page load). SQLite: a fresh one."""
    if not PG:
        c = _connect(); _setup(c); return c
    c = getattr(_local, "cached", None)
    if c is not None and not c.closed and not c.broken:
        if time.time() - getattr(_local, "used", 0) > IDLE_PING_S:
            try:
                c.execute("SELECT 1"); c.rollback()
            except Exception:
                _drop()
                c = None
        if c is not None:
            return c
    c = _connect(); _setup(c)
    _local.cached = c
    return c

def _drop():
    c = getattr(_local, "cached", None)
    _local.cached = None
    try:
        if c is not None:
            c.close()
    except Exception:
        pass

@contextmanager
def conn():
    if getattr(_local, "depth", 0):             # re-entrant: a nested block shares the outer connection and transaction
        _local.depth += 1
        try:
            yield _local.cur
        finally:
            _local.depth -= 1
        return
    c = _acquire()
    _local.depth, _local.cur = 1, c
    try:
        yield c
        c.commit()
    except BaseException:
        try:
            c.rollback()
        except Exception:
            _drop()
        raise
    finally:
        _local.depth, _local.cur, _local.used = 0, None, time.time()
        if not PG:
            c.close()

def _q(sql):
    return sql.replace("?", "%s") if PG else sql

def run(c, sql, args=()):
    return c.execute(_q(sql), args)

def all(c, sql, args=()):
    return [dict(r) for r in run(c, sql, args).fetchall()]

def many(c, sql, rows):
    """Batched write: one round trip per batch instead of one per row (matters on a remote Postgres)."""
    if not rows:
        return
    if PG:
        with c.cursor() as cur:
            cur.executemany(_q(sql), rows)
    else:
        c.executemany(sql, rows)

def one(c, sql, args=()):
    r = run(c, sql, args).fetchone()
    return dict(r) if r else None

def insert(c, sql, args=()):
    """INSERT returning the new id on both backends."""
    if PG:
        return c.execute(_q(sql) + " RETURNING id", args).fetchone()["id"]
    return c.execute(sql, args).lastrowid

def log(c, kind, detail=""):
    run(c, "INSERT INTO events (ts, kind, detail) VALUES (?,?,?)", (config.now_ist().isoformat(timespec="seconds"), kind, str(detail)[:2000]))

def kv_get(c, k, default=None):
    r = one(c, "SELECT v FROM kv WHERE k=?", (k,))
    return r["v"] if r else default

def kv_set(c, k, v):
    run(c, "INSERT INTO kv (k, v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))
