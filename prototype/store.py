# SugApp — proprietary & confidential. © 2026 <Your Legal Name>. All rights reserved.
# Trade-secret methodology; not for distribution. See /LICENSE and /IP.md.
"""SQLite persistence for Respect & Listening findings.

The scorer is stateless — it scores a transcript and prints. To show *trends*
(the product's behavior-change loop: "interruptions down 30% this month"), the
findings have to live somewhere. This is that somewhere: a dependency-free
SQLite store (Python stdlib only).

Identity: every person is keyed by a stable **author_id**, not a display name.
For Slack that is the user id (e.g. U02SAM), which the connector carries through
from the authenticated API; a display name can change or collide, an id cannot.
The `identities` table maps author_id → the human-readable name for display. A
hand-written transcript with no id falls back to author_id == the name (an
"unverified" identity) so the samples still run.

Schema:

    runs        — one row per scoring run (when, which channel, how many people)
    findings    — one row per finding, linked to its run, keyed by author_id
    identities  — author_id → display name (so views show names, keys stay stable)
    consent     — opt-in registry, keyed by author_id
    goals       — one self-set goal per person, keyed by author_id

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
    author_id        TEXT    NOT NULL,   -- stable identity (Slack user id / fallback)
    author           TEXT    NOT NULL,   -- display name at scoring time (denormalized)
    behavior         TEXT    NOT NULL,
    polarity         TEXT    NOT NULL,
    evidence         TEXT    NOT NULL,
    coaching_rewrite TEXT    NOT NULL,
    rationale        TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_findings_run    ON findings(run_id);
CREATE INDEX IF NOT EXISTS idx_findings_author ON findings(author_id);

-- author_id → display name. `verified` is 1 when the id came from an
-- authenticated source (the Slack API), 0 when it fell back to the display name.
CREATE TABLE IF NOT EXISTS identities (
    author_id    TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    verified     INTEGER NOT NULL DEFAULT 0,
    updated_at   TEXT NOT NULL
);

-- One self-set goal per person (PRODUCT.md §6). Keyed by author_id.
CREATE TABLE IF NOT EXISTS goals (
    author_id TEXT PRIMARY KEY,
    goal      TEXT NOT NULL,
    set_at    TEXT NOT NULL   -- ISO-8601 UTC
);

-- Opt-in consent registry (PRODUCT.md §5: opt-in with a real, penalty-free
-- opt-out), keyed by author_id. Absence of a row means NOT consented — scoring
-- is opt-in, so silence is never consent. status 'out' records a withdrawal.
CREATE TABLE IF NOT EXISTS consent (
    author_id  TEXT PRIMARY KEY,
    status     TEXT NOT NULL CHECK (status IN ('in', 'out')),
    updated_at TEXT NOT NULL   -- ISO-8601 UTC
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str = DEFAULT_DB) -> sqlite3.Connection:
    """Open (creating if needed) the database and ensure the schema exists."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


# --- Identity -----------------------------------------------------------------
# author_id is the key everywhere; identities maps it to a human name for display.


def register_identities(conn: sqlite3.Connection, mapping: dict, verified: bool = False) -> None:
    """Upsert author_id → display_name for a set of people.

    Called on every save (for participants) and by `consent.py --import`, so you
    can opt people in by name before they have any findings. `verified` marks
    ids that came from an authenticated source; a later verified upsert wins.
    """
    now = _now()
    with conn:
        for author_id, name in mapping.items():
            conn.execute(
                "INSERT INTO identities (author_id, display_name, verified, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(author_id) DO UPDATE SET "
                "display_name = excluded.display_name, updated_at = excluded.updated_at, "
                "verified = MAX(identities.verified, excluded.verified)",
                (author_id, name, 1 if verified else 0, now),
            )


def all_identities(conn: sqlite3.Connection) -> dict:
    """Every known author_id → display name (from the identities table)."""
    rows = conn.execute("SELECT author_id, display_name FROM identities").fetchall()
    return {r["author_id"]: r["display_name"] for r in rows}


def is_known(conn: sqlite3.Connection, author_id: str) -> bool:
    """True if this id has an identity row or any stored finding — i.e. a real person."""
    if conn.execute("SELECT 1 FROM identities WHERE author_id = ?", (author_id,)).fetchone():
        return True
    return bool(
        conn.execute("SELECT 1 FROM findings WHERE author_id = ? LIMIT 1", (author_id,)).fetchone()
    )


def display_name(conn: sqlite3.Connection, author_id: str) -> str:
    """Human name for an author_id, falling back to a stored finding name / the id."""
    row = conn.execute(
        "SELECT display_name FROM identities WHERE author_id = ?", (author_id,)
    ).fetchone()
    if row:
        return row["display_name"]
    row = conn.execute(
        "SELECT author FROM findings WHERE author_id = ? LIMIT 1", (author_id,)
    ).fetchone()
    return row["author"] if row else author_id


def resolve_author(conn: sqlite3.Connection, token: str) -> str:
    """Map a CLI token (an author_id OR a display name) to an author_id.

    Exact id wins; otherwise match on display name (identities, then finding
    names). Raises ValueError if a name is ambiguous across several ids; returns
    the token unchanged if nothing matches (treat as a literal id).
    """
    if conn.execute("SELECT 1 FROM identities WHERE author_id = ?", (token,)).fetchone():
        return token
    if conn.execute("SELECT 1 FROM findings WHERE author_id = ? LIMIT 1", (token,)).fetchone():
        return token
    rows = conn.execute(
        "SELECT author_id FROM identities WHERE display_name = ?", (token,)
    ).fetchall()
    if not rows:
        rows = conn.execute(
            "SELECT DISTINCT author_id FROM findings WHERE author = ?", (token,)
        ).fetchall()
    ids = [r["author_id"] for r in rows]
    if len(ids) == 1:
        return ids[0]
    if len(ids) > 1:
        raise ValueError(
            f"'{token}' is ambiguous — it maps to several ids: {', '.join(ids)}. "
            f"Pass the id instead."
        )
    return token


def save_run(
    conn: sqlite3.Connection,
    channel: str,
    source: str,
    participant_count: int,
    findings: list[dict],
    identities: dict | None = None,
) -> int:
    """Persist one scoring run and its findings; return the new run id.

    Each finding must carry author_id + author. `identities` (author_id →
    display name for *all* participants, verified) is registered too, so even
    people with no findings are known to the consent/name-resolution layer.
    """
    if identities:
        register_identities(conn, identities, verified=True)
    created_at = _now()
    with conn:  # single transaction — run + all its findings commit together
        cur = conn.execute(
            "INSERT INTO runs (created_at, channel, source, participant_count) "
            "VALUES (?, ?, ?, ?)",
            (created_at, channel, source, participant_count),
        )
        run_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO findings (run_id, message_index, author_id, author, "
            "behavior, polarity, evidence, coaching_rewrite, rationale) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    run_id,
                    f["message_index"],
                    f["author_id"],
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
    """Per-person lifetime tallies across all runs — the personal-mirror view.

    Grouped by author_id (the stable key); display_name is for rendering.
    """
    rows = conn.execute(
        """
        SELECT
            f.author_id,
            COALESCE(i.display_name, MAX(f.author))  AS display_name,
            SUM(f.polarity = 'respectful')           AS respectful,
            SUM(f.polarity = 'disrespectful')        AS disrespectful
        FROM findings f
        LEFT JOIN identities i ON i.author_id = f.author_id
        GROUP BY f.author_id
        ORDER BY display_name
        """
    ).fetchall()
    return [dict(row) for row in rows]


def behavior_tally(conn: sqlite3.Connection, author_id: str | None = None,
                   channel: str | None = None) -> dict:
    """behavior → count, optionally scoped to one person and/or one channel.

    The building block for named signal ratios and per-person fingerprints: a
    plain map so callers combine behaviors however a signal or fingerprint needs.
    """
    where, params = [], []
    if author_id is not None:
        where.append("f.author_id = ?")
        params.append(author_id)
    if channel is not None:
        where.append("r.channel = ?")
        params.append(channel)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"""
        SELECT f.behavior AS behavior, COUNT(*) AS n
        FROM findings f
        JOIN runs r ON r.id = f.run_id
        {clause}
        GROUP BY f.behavior
        """,
        params,
    ).fetchall()
    return {row["behavior"]: row["n"] for row in rows}


def distinct_finding_authors(conn: sqlite3.Connection) -> int:
    """How many distinct people have at least one finding — a k-anonymity floor
    for the org-wide rollup (the true participant set across all runs isn't
    stored; this is a conservative lower bound)."""
    row = conn.execute(
        "SELECT COUNT(DISTINCT author_id) AS n FROM findings"
    ).fetchone()
    return row["n"] if row else 0


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


# --- Momentum: the same tallies, bucketed by time period ----------------------
# The behavior-change loop (PRODUCT.md §6) needs "is this getting better?", which
# means comparing periods. These queries bucket runs into day/week/month and roll
# up respectful/disrespectful per bucket; the ratio + period-over-period delta are
# computed by the caller (analytics.py), keeping the SQL to plain aggregation.
#
# created_at is ISO-8601 UTC; substr(...,1,19) trims the timezone offset to
# 'YYYY-MM-DDTHH:MM:SS' so strftime parses it on every SQLite version. The prefix
# is fixed-width and lexicographically ordered, so bucketing stays correct.
_PERIOD_FMT = {"day": "%Y-%m-%d", "week": "%Y-W%W", "month": "%Y-%m"}


def _period_expr(period: str) -> str:
    try:
        fmt = _PERIOD_FMT[period]
    except KeyError:
        raise ValueError(f"period must be one of {', '.join(_PERIOD_FMT)}; got {period!r}")
    return f"strftime('{fmt}', substr(r.created_at, 1, 19))"


def channel_momentum(conn: sqlite3.Connection, period: str = "month") -> list[dict]:
    """Per (channel, period): tallies + max participant count, oldest period first.

    `max_participants` is the largest single-run participant count in the bucket —
    a conservative proxy for k-anonymity suppression at the period level (the set
    of *all* participants across a period isn't stored; participant_count is
    per-run). The caller suppresses a channel-period whose max is below K_ANON.
    """
    period_expr = _period_expr(period)
    rows = conn.execute(
        f"""
        SELECT
            r.channel                                       AS channel,
            {period_expr}                                   AS period,
            COALESCE(SUM(f.polarity = 'respectful'), 0)     AS respectful,
            COALESCE(SUM(f.polarity = 'disrespectful'), 0)  AS disrespectful,
            MAX(r.participant_count)                        AS max_participants,
            COUNT(DISTINCT r.id)                            AS runs
        FROM runs r
        LEFT JOIN findings f ON f.run_id = r.id
        GROUP BY channel, period
        ORDER BY channel, period
        """
    ).fetchall()
    return [dict(row) for row in rows]


def person_momentum(conn: sqlite3.Connection, period: str = "month") -> list[dict]:
    """Per (person, period): respectful/disrespectful tallies, oldest period first.

    This is the personal-mirror trend (name-attached on purpose — the person's own
    data, never an org-facing per-individual rollup). No k-anonymity applies.
    """
    period_expr = _period_expr(period)
    rows = conn.execute(
        f"""
        SELECT
            f.author_id                              AS author_id,
            COALESCE(i.display_name, MAX(f.author))  AS display_name,
            {period_expr}                            AS period,
            SUM(f.polarity = 'respectful')           AS respectful,
            SUM(f.polarity = 'disrespectful')        AS disrespectful
        FROM findings f
        JOIN runs r ON r.id = f.run_id
        LEFT JOIN identities i ON i.author_id = f.author_id
        GROUP BY f.author_id, period
        ORDER BY display_name, period
        """
    ).fetchall()
    return [dict(row) for row in rows]


# --- Per-person read side: the personal mirror (PRODUCT.md §5) ----------------
# The mirror is the one place a name attaches to a score. The org never sees this.


def people(conn: sqlite3.Connection) -> list[dict]:
    """Distinct people (author_id + display_name) who have at least one finding."""
    rows = conn.execute(
        """
        SELECT f.author_id, COALESCE(i.display_name, MAX(f.author)) AS display_name
        FROM findings f
        LEFT JOIN identities i ON i.author_id = f.author_id
        GROUP BY f.author_id
        ORDER BY display_name
        """
    ).fetchall()
    return [dict(row) for row in rows]


def person_findings(conn: sqlite3.Connection, author_id: str) -> list[dict]:
    """Every finding for one person, newest run first — their quotes + rewrites."""
    rows = conn.execute(
        """
        SELECT f.behavior, f.polarity, f.evidence, f.coaching_rewrite,
               f.rationale, r.channel, r.created_at
        FROM findings f
        JOIN runs r ON r.id = f.run_id
        WHERE f.author_id = ?
        ORDER BY r.created_at DESC, f.id DESC
        """,
        (author_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def person_timeline(conn: sqlite3.Connection, author_id: str) -> list[dict]:
    """Per-run respectful/disrespectful tally for one person — their trend line."""
    rows = conn.execute(
        """
        SELECT r.id, r.created_at, r.channel,
               SUM(f.polarity = 'respectful')    AS respectful,
               SUM(f.polarity = 'disrespectful') AS disrespectful
        FROM findings f
        JOIN runs r ON r.id = f.run_id
        WHERE f.author_id = ?
        GROUP BY r.id
        ORDER BY r.created_at, r.id
        """,
        (author_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def set_goal(conn: sqlite3.Connection, author_id: str, goal: str) -> None:
    """Set (replacing any prior) this person's one self-chosen improvement goal."""
    with conn:
        conn.execute(
            "INSERT INTO goals (author_id, goal, set_at) VALUES (?, ?, ?) "
            "ON CONFLICT(author_id) DO UPDATE SET goal = excluded.goal, "
            "set_at = excluded.set_at",
            (author_id, goal, _now()),
        )


def get_goal(conn: sqlite3.Connection, author_id: str) -> dict | None:
    """This person's current goal, or None if they haven't set one."""
    row = conn.execute(
        "SELECT goal, set_at FROM goals WHERE author_id = ?", (author_id,)
    ).fetchone()
    return dict(row) if row else None


# --- Consent (PRODUCT.md §5: opt-in, with a real, penalty-free opt-out) -------
# Scoring is opt-in: only author_ids with status 'in' may be scored or stored.
# Withdrawing (opt-out) is penalty-free and also purges what was already stored.


def set_consent(conn: sqlite3.Connection, author_id: str, status: str) -> None:
    """Record an author_id's consent decision ('in' or 'out')."""
    if status not in ("in", "out"):
        raise ValueError("status must be 'in' or 'out'")
    with conn:
        conn.execute(
            "INSERT INTO consent (author_id, status, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(author_id) DO UPDATE SET status = excluded.status, "
            "updated_at = excluded.updated_at",
            (author_id, status, _now()),
        )


def get_consent(conn: sqlite3.Connection, author_id: str) -> str | None:
    """'in', 'out', or None if this author_id has never made a decision."""
    row = conn.execute(
        "SELECT status FROM consent WHERE author_id = ?", (author_id,)
    ).fetchone()
    return row["status"] if row else None


def consented_authors(conn: sqlite3.Connection) -> set:
    """The set of author_ids who have opted in — the only people who may be scored."""
    rows = conn.execute("SELECT author_id FROM consent WHERE status = 'in'").fetchall()
    return {row["author_id"] for row in rows}


def consent_list(conn: sqlite3.Connection) -> list[dict]:
    """All recorded consent decisions with display names, opted-in first."""
    rows = conn.execute(
        """
        SELECT c.author_id, c.status, c.updated_at,
               COALESCE(i.display_name, c.author_id) AS display_name
        FROM consent c
        LEFT JOIN identities i ON i.author_id = c.author_id
        ORDER BY c.status, display_name
        """
    ).fetchall()
    return [dict(row) for row in rows]


def purge_person(conn: sqlite3.Connection, author_id: str) -> int:
    """Delete everything stored about one person (findings + goal).

    Used when consent is withdrawn — the opt-out is not just "stop going
    forward" but also removes what was already collected. Returns the number of
    findings deleted. The identity row is kept (so a re-opt-in still resolves by
    name) and the consent row is left to the caller to set to 'out'.
    """
    with conn:
        cur = conn.execute("DELETE FROM findings WHERE author_id = ?", (author_id,))
        deleted = cur.rowcount
        conn.execute("DELETE FROM goals WHERE author_id = ?", (author_id,))
    return deleted


def unconsented_with_data(conn: sqlite3.Connection) -> list[dict]:
    """People (author_id + display_name) with stored findings but not opted in.

    Should be empty once the consent gate is in use; non-empty means data was
    stored before consent enforcement (e.g. demo data).
    """
    rows = conn.execute(
        """
        SELECT DISTINCT f.author_id,
               COALESCE(i.display_name, f.author) AS display_name
        FROM findings f
        LEFT JOIN consent c    ON c.author_id = f.author_id
        LEFT JOIN identities i ON i.author_id = f.author_id
        WHERE c.status IS NULL OR c.status = 'out'
        ORDER BY display_name
        """
    ).fetchall()
    return [dict(row) for row in rows]
