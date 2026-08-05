#!/usr/bin/env python3
# SugApp — proprietary & confidential. © 2026 <Your Legal Name>. All rights reserved.
# Trade-secret methodology; not for distribution. See /LICENSE and /IP.md.
"""Named signals — the plain-English metrics, not raw counts.

`behavior_counts` (in trends.py) tells you *how often* each behavior fired.
This turns those behaviors into the PRODUCT.md §4 signals an enterprise actually
reads: each one is a balance between a respectful form and its disrespectful
counterpart, so it answers a question — "when people disagree, how often do they
challenge the idea instead of the person?" — as a percentage.

The signal model lives in rubric.py (SIGNALS); this computes and prints it.

Two views, matching the privacy split (PRODUCT.md §5):
  * Org-wide — the aggregate every team is bought on. k-anonymity enforced: the
    whole-org rollup is suppressed if fewer than K_ANON distinct people appear.
  * Per person — the personal mirror (name-attached, the person's own data).

Usage:
    python signals.py                 # org-wide + every person, default sugapp.db
    python signals.py Dana            # just one person's signals
    python signals.py --db team.db
"""
import os
import sys

import store
from rubric import SIGNALS
from score import K_ANON


def signal_value(tally: dict, signal: dict) -> dict:
    """Compute one signal from a behavior→count tally.

    Balance signals (with a `contrast` set) return `pct` = positive / (positive +
    contrast). Presence signals (empty contrast) return pct=None and just the
    count — a presence is reported, never turned into an accusation.
    """
    pos = sum(tally.get(b, 0) for b in signal["positive"])
    con = sum(tally.get(b, 0) for b in signal["contrast"])
    presence = not signal["contrast"]
    total = pos + con
    pct = None if presence or total == 0 else round(100 * pos / total)
    return {"pos": pos, "contrast": con, "total": total, "pct": pct, "presence": presence}


def _print_signals(tally: dict, indent: str = "  ") -> None:
    width = max(len(s["name"]) for s in SIGNALS)
    for sig in SIGNALS:
        v = signal_value(tally, sig)
        name = sig["name"].ljust(width)
        if v["presence"]:
            metric = f"{v['pos']}× present" if v["pos"] else "none seen "
            metric = metric.ljust(14)
        elif v["total"] == 0:
            metric = "no data".ljust(14)
        else:
            metric = f"{v['pct']:>3}%  ({v['pos']} of {v['total']})".ljust(14)
        print(f"{indent}{name}  {metric}  — {sig['question']}")


def _print_org(conn) -> None:
    print("--- Named signals (org-wide, aggregate view) ---")
    distinct = store.distinct_finding_authors(conn)
    if distinct < K_ANON:
        print(f"  suppressed: only {distinct} distinct people in the data "
              f"(k-anonymity threshold is {K_ANON}).\n")
        return
    _print_signals(store.behavior_tally(conn))
    print()


def _print_person(conn, author_id: str, name: str) -> None:
    print(f"  {name}")
    _print_signals(store.behavior_tally(conn, author_id=author_id), indent="    ")
    print()


def main() -> None:
    args = sys.argv[1:]
    db_path = store.DEFAULT_DB
    if "--db" in args:
        i = args.index("--db")
        if i + 1 >= len(args):
            sys.exit("--db needs a path")
        db_path = args[i + 1]
        args = args[:i] + args[i + 2 :]
    who = next((a for a in args if not a.startswith("--")), None)

    if not os.path.exists(db_path):
        sys.exit(f"no database at {db_path} — score something with "
                 f"`score.py --save` first.")

    conn = store.connect(db_path)
    if not store.run_history(conn):
        sys.exit("database has no runs yet — score something with "
                 "`score.py --save` first.")

    print(f"\n=== Named signals — {db_path} ===\n")

    if who is not None:
        try:
            author_id = store.resolve_author(conn, who)
        except ValueError as e:
            sys.exit(str(e))
        if not store.is_known(conn, author_id):
            sys.exit(f"no one matching {who!r} in the data.")
        print("--- Named signals (personal-mirror view) ---")
        _print_person(conn, author_id, store.display_name(conn, author_id))
    else:
        _print_org(conn)
        print("--- Named signals (personal-mirror view, per person) ---")
        for p in store.people(conn):
            _print_person(conn, p["author_id"], p["display_name"])

    conn.close()


if __name__ == "__main__":
    main()
