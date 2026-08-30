"""Anonymous learner storage. One row per learner, state as JSON, and the last few chat turns.

The path is never stored. It is a pure function of state and catalog, so saving it would mean every
catalog rebuild quietly invalidates every saved plan.
"""

import json, sqlite3, threading, time
from pathlib import Path

DB = Path(__file__).resolve().parent / "data/learners.db"
TURNS_KEPT = 12

# FastAPI answers on a thread pool, and one sqlite connection shared across threads without
# serialising raises "bad parameter or other API misuse" under load. SQLite serialises writes anyway,
# and every call here takes microseconds, so a lock costs nothing and removes the whole class of bug.
_lock = threading.Lock()
_conn = sqlite3.connect(DB, check_same_thread=False)
_conn.execute("PRAGMA journal_mode=WAL")
_conn.executescript("""
CREATE TABLE IF NOT EXISTS learners (id TEXT PRIMARY KEY, state TEXT NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS turns (learner TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS turns_by_learner ON turns (learner, at);
""")
_conn.commit()


def load(learner):
    """Everything we know about them, or empty. Unknown ids are not an error, they are new people."""
    if not learner:
        return None, []
    with _lock:
        row = _conn.execute("SELECT state FROM learners WHERE id = ?", (learner,)).fetchone()
        turns = _conn.execute("SELECT role, content FROM turns WHERE learner = ? ORDER BY at", (learner,)).fetchall()
    return (json.loads(row[0]) if row else None), [{"role": r, "content": c} for r, c in turns]


def save(learner, state, turns=()):
    if not learner:
        return
    with _lock:
        _conn.execute("INSERT INTO learners (id, state, updated) VALUES (?, ?, ?) "
                      "ON CONFLICT(id) DO UPDATE SET state = excluded.state, updated = excluded.updated",
                      (learner, json.dumps(state), time.time()))
        now = time.time()
        _conn.executemany("INSERT INTO turns (learner, role, content, at) VALUES (?, ?, ?, ?)",
                          [(learner, t["role"], t["content"], now + i / 1000) for i, t in enumerate(turns)])
        # Keep the tail only. The transcript is context for the next turn, not an archive.
        _conn.execute("DELETE FROM turns WHERE learner = ? AND rowid NOT IN "
                      "(SELECT rowid FROM turns WHERE learner = ? ORDER BY at DESC LIMIT ?)",
                      (learner, learner, TURNS_KEPT))
        _conn.commit()


def forget(learner):
    if learner:
        with _lock:
            _conn.execute("DELETE FROM learners WHERE id = ?", (learner,))
            _conn.execute("DELETE FROM turns WHERE learner = ?", (learner,))
            _conn.commit()
