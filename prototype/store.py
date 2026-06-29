"""SQLite persistence for Respect & Listening findings.

The scorer is stateless — it scores a transcript and prints. To show *trends*
(the product's behavior-change loop: "interruptions down 30% this month"), the
findings have to live somewhere. This is that somewhere: a dependency-free
SQLite store (Python stdlib only).

Schema is two tables:

    runs      — one row per scoring run (when, which channel, how many people)
    findings  — one row per finding, linked to its run

A run records `participant_count` because k-anonymity suppression depends on it
and it cannot be recovered from the findings alone (a transcript can have
participants who triggered no finding). Per-person history is the "personal
mirror" (name-attached on purpose); team rollups stay k-anonymized on read.
"""
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "sugapp.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TEXT    NOT NULL,   -- ISO-8601 UTC
    channel          TEXT    NOT NULL,
    source           TEXT    NOT NULL,   -- transcript path, "-" for stdin, "repl"
    participant_count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS findings (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    message_index    INTEGER NOT NULL,
    author           TEXT    NOT NULL,
    behavior         TEXT    NOT NULL,
    polarity         TEXT    NOT NULL,
    evidence         TEXT    NOT NULL,
    coaching_rewrite TEXT    NOT NULL,
    rationale        TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_findings_run    ON findings(run_id);
CREATE INDEX IF NOT EXISTS idx_findings_author ON findings(author);
"""


def connect(db_path: str = DEFAULT_DB) -> sqlite3.Connection:
    """Open (creating if needed) the database and ensure the schema exists."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def save_run(
    conn: sqlite3.Connection,
    channel: str,
    source: str,
    participant_count: int,
    findings: list[dict],
) -> int:
    """Persist one scoring run and its findings; return the new run id."""
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with conn:  # single transaction — run + all its findings commit together
        cur = conn.execute(
            "INSERT INTO runs (created_at, channel, source, participant_count) "
            "VALUES (?, ?, ?, ?)",
            (created_at, channel, source, participant_count),
        )
        run_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO findings (run_id, message_index, author, behavior, "
            "polarity, evidence, coaching_rewrite, rationale) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    run_id,
                    f["message_index"],
                    f["author"],
                    f["behavior"],
                    f["polarity"],
                    f["evidence"],
                    f.get("coaching_rewrite", ""),
                    f["rationale"],
                )
                for f in findings
            ],
        )
    return run_id


# --- Read side: the trend queries the dashboards will eventually call ---------


def run_history(conn: sqlite3.Connection) -> list[dict]:
    """Every run, oldest first, with respectful/disrespectful tallies.

    The Respect Index (and its k-anonymity suppression) is intentionally NOT
    computed here — callers apply `score.respect_index` / the K_ANON threshold,
    keeping that policy in one place.
    """
    rows = conn.execute(
        """
        SELECT
            r.id, r.created_at, r.channel, r.source, r.participant_count,
            COALESCE(SUM(f.polarity = 'respectful'), 0)    AS respectful,
            COALESCE(SUM(f.polarity = 'disrespectful'), 0) AS disrespectful
        FROM runs r
        LEFT JOIN findings f ON f.run_id = r.id
        GROUP BY r.id
        ORDER BY r.created_at, r.id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def person_totals(conn: sqlite3.Connection) -> list[dict]:
    """Per-person lifetime tallies across all runs — the personal-mirror view."""
    rows = conn.execute(
        """
        SELECT
            author,
            SUM(polarity = 'respectful')    AS respectful,
            SUM(polarity = 'disrespectful') AS disrespectful
        FROM findings
        GROUP BY author
        ORDER BY author
        """
    ).fetchall()
    return [dict(row) for row in rows]


def behavior_counts(conn: sqlite3.Connection) -> list[dict]:
    """How often each named behavior fired across all runs — most frequent first."""
    rows = conn.execute(
        """
        SELECT behavior, polarity, COUNT(*) AS n
        FROM findings
        GROUP BY behavior, polarity
        ORDER BY n DESC, behavior
        """
    ).fetchall()
    return [dict(row) for row in rows]
