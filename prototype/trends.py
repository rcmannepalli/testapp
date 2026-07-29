#!/usr/bin/env python3
"""Read back the persisted Respect & Listening history.

Once you've scored a few transcripts with `score.py --save`, this prints what
accumulated: the Respect Index per run over time (k-anonymity enforced), each
person's lifetime mirror tally, and which behaviors fire most. It's the
text-only stand-in for the dashboards in PRODUCT.md §8 — same data, no UI yet.

Usage:
    python trends.py                 # read default sugapp.db
    python trends.py --db mine.db
"""
import os
import sys

import store
from score import K_ANON, respect_index


def main() -> None:
    args = sys.argv[1:]
    db_path = store.DEFAULT_DB
    if "--db" in args:
        i = args.index("--db")
        if i + 1 >= len(args):
            sys.exit("--db needs a path")
        db_path = args[i + 1]

    if not os.path.exists(db_path):
        sys.exit(f"no database at {db_path} — score something with "
                 f"`score.py --save` first.")

    conn = store.connect(db_path)
    history = store.run_history(conn)
    if not history:
        sys.exit("database has no runs yet — score something with "
                 "`score.py --save` first.")

    print(f"\n=== Respect & Listening trends — {db_path} ===\n")

    # Respect Index over time. respect_index() takes findings, but the per-run
    # respectful/disrespectful tallies are all it needs, so reconstruct a minimal
    # findings list of the right shape (cheaper than re-reading every finding).
    print("--- Respect Index over time (team rollup, org view) ---")
    for r in history:
        pos, neg = r["respectful"], r["disrespectful"]
        when = r["created_at"].replace("T", " ").replace("+00:00", "Z")
        if r["participant_count"] < K_ANON:
            idx = f"suppressed (only {r['participant_count']} participants, k={K_ANON})"
        else:
            synthetic = [{"polarity": "respectful"}] * pos + [{"polarity": "disrespectful"}] * neg
            idx = f"{respect_index(synthetic)}/100"
        print(f"  run #{r['id']:<3} {when}  {r['channel']:<16} "
              f"{idx}  ({pos} resp, {neg} disresp)")

    # Per-person mirror — name-attached on purpose (PRODUCT.md §5: the personal
    # mirror is the one place a name attaches to a score).
    print("\n--- Per-person (personal-mirror view, all runs) ---")
    for p in store.person_totals(conn):
        print(f"  {p['display_name']}: {p['respectful']} respectful, "
              f"{p['disrespectful']} disrespectful")

    # Which behaviors fire most — the rubric's signal mix in practice.
    print("\n--- Behavior frequency (all runs) ---")
    mark = {"respectful": "✅", "disrespectful": "⚠️ "}
    for b in store.behavior_counts(conn):
        print(f"  {b['n']:>3}× {mark.get(b['polarity'], '? ')}{b['behavior']}")
    print()

    conn.close()


if __name__ == "__main__":
    main()
