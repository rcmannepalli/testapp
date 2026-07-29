#!/usr/bin/env python3
"""Seed a demo SQLite DB with multi-week, multi-team runs — no API key needed.

The scorer + store are real; the only thing missing to drive a data-backed
dashboard is data. In production that arrives from live scoring runs over weeks.
For a self-contained demo we synthesize a plausible history here, using the SAME
store.py schema the live scorer writes to, so the export/build steps read exactly
what a real deployment would produce.

    python seed_demo.py            # writes ui/demo.db (overwrites)

Then:  python build_ui.py --db demo.db -o saas_dashboard.html

Data:
  #eng-standup (Platform, 5 people)  — 4 weekly runs, from the real fixture,
      with an improving trend (past weeks carry extra dismissiveness).
  #growth-sync (Growth, 6 people)    — 1 recent run, respectful-heavy.
  #design-crit (Design, 3 people)    — 1 recent run; SUPPRESSED (<5) in the org view.
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import store  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "demo.db")
FIXTURE = os.path.join(HERE, "..", "sample_transcripts", "standup.findings.json")


def insert_run(conn, created_at, channel, source, participant_count, findings):
    with conn:
        cur = conn.execute(
            "INSERT INTO runs (created_at, channel, source, participant_count) "
            "VALUES (?, ?, ?, ?)",
            (created_at, channel, source, participant_count),
        )
        rid = cur.lastrowid
        # Demo identities are unverified: author_id == the display name. Register
        # them so name-resolution and the identities join behave like real data.
        store.register_identities(conn, {f["author"]: f["author"] for f in findings})
        conn.executemany(
            "INSERT INTO findings (run_id, message_index, author_id, author, behavior, "
            "polarity, evidence, coaching_rewrite, rationale) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (rid, f.get("message_index", 0), f["author"], f["author"], f["behavior"],
                 f["polarity"], f["evidence"], f.get("coaching_rewrite", ""),
                 f["rationale"])
                for f in findings
            ],
        )
    return rid


def dismiss(author, n):
    """A generic dismissiveness finding — used to make past weeks rougher."""
    return {
        "message_index": 90 + n, "author": author, "behavior": "dismissiveness",
        "polarity": "disrespectful",
        "evidence": "we've been over this, it's not complicated.",
        "coaching_rewrite": "Happy to walk through it again — where did it get unclear?",
        "rationale": "'we've been over this' dismisses the question.",
    }


GROWTH = [
    ("Ivy", "acknowledgment", "respectful", "Love where Theo's going with this — to build on it,"),
    ("Theo", "question_asking", "respectful", "what would make this easier for the on-call folks?"),
    ("Ivy", "invites_others", "respectful", "Rae, you shipped the last one — how would you approach it?"),
    ("Rae", "disagree_with_dignity", "respectful", "I'd push back on the timeline — the data migration alone is a week."),
    ("Noor", "enabling", "respectful", "Here's a template so nobody has to start from scratch."),
    ("Cole", "credit_attribution", "respectful", "That was Noor's idea originally — worth crediting."),
    ("Theo", "acknowledgment", "respectful", "Good call Rae, hadn't thought of the migration."),
    ("Cole", "dismissiveness", "disrespectful", "obviously we ship Tuesday, that's the whole point."),
]
DESIGN = [
    ("Mira", "disagree_with_dignity", "respectful", "This layout buries the primary action — can we test it?"),
    ("Jun", "acknowledgment", "respectful", "Fair, building on Mira's point about hierarchy,"),
    ("Ada", "personal_attack", "disrespectful", "that's a lazy crit, did you even open the file?"),
]


def to_findings(rows):
    out = []
    for i, (author, behavior, polarity, evidence) in enumerate(rows):
        out.append({
            "message_index": i, "author": author, "behavior": behavior,
            "polarity": polarity, "evidence": evidence,
            "coaching_rewrite": (
                "" if polarity == "respectful"
                else "Try naming the specific issue instead of the person."),
            "rationale": f"{behavior} ({polarity}).",
        })
    return out


def main():
    if os.path.exists(DB):
        os.remove(DB)
    conn = store.connect(DB)

    base = json.load(open(FIXTURE, encoding="utf-8"))["findings"]

    # Opt everyone in (scoring is opt-in; the store enforces it on --require-consent).
    for name in ["Dana", "Sam", "Priya", "Marcus", "Lena",
                 "Ivy", "Theo", "Rae", "Noor", "Cole", "Mira", "Jun", "Ada"]:
        store.set_consent(conn, name, "in")

    now = datetime.now(timezone.utc).replace(microsecond=0)

    # Platform: 4 weekly runs. Older weeks carry extra dismissiveness (Dana, then
    # Marcus) so the Respect Index visibly improves toward the present.
    for weeks_ago in (3, 2, 1, 0):
        ts = (now - timedelta(weeks=weeks_ago)).isoformat()
        extra = []
        for k in range(weeks_ago):
            extra.append(dismiss("Dana" if k % 2 == 0 else "Marcus", k))
        insert_run(conn, ts, "#eng-standup", "seed", 5, base + extra)

    # Growth + Design: one recent run each.
    insert_run(conn, now.isoformat(), "#growth-sync", "seed", 6, to_findings(GROWTH))
    insert_run(conn, now.isoformat(), "#design-crit", "seed", 3, to_findings(DESIGN))

    # A couple of self-set goals (the "pick one thing" loop).
    store.set_goal(conn, "Dana", "Swap “obviously / as I said” for a plain restatement.")
    store.set_goal(conn, "Marcus", "Hand off with a next step instead of a wall.")
    store.set_goal(conn, "Sam", "Keep crediting teammates by name before building on their idea.")

    conn.close()
    print(f"seeded {DB}")


if __name__ == "__main__":
    main()
