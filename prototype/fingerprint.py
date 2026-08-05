#!/usr/bin/env python3
# SugApp — proprietary & confidential. © 2026 <Your Legal Name>. All rights reserved.
# Trade-secret methodology; not for distribution. See /LICENSE and /IP.md.
"""Behavior fingerprint — which behaviors a person leans on, with their own words.

The personal mirror's totals say "4 respectful, 2 disrespectful". A fingerprint
says *which* behaviors: the distribution across the rubric's named behaviors,
sorted by how often each fired, each with a representative quote pulled from that
person's own messages. It's the "here's how you actually land" view — evidence,
not a verdict (PRODUCT.md §4: always show the exact quote).

Name-attached on purpose: this is the personal-mirror surface (PRODUCT.md §5),
the one place a name attaches to behavior. The org never sees it.

Usage:
    python fingerprint.py                 # every person, default sugapp.db
    python fingerprint.py Dana            # one person
    python fingerprint.py --db team.db
"""
import os
import sys
from collections import OrderedDict

import store

MARK = {"respectful": "✅", "disrespectful": "⚠️ "}


def fingerprint(findings: list[dict]) -> list[tuple]:
    """From a person's findings (newest-run first), build their behavior profile.

    Returns [(behavior, {polarity, count, example, channels}), ...] sorted by
    count desc. `example` is the most recent quote for that behavior (findings
    arrive newest-first, so the first one seen wins).
    """
    by_behavior: "OrderedDict[str, dict]" = OrderedDict()
    for f in findings:
        b = by_behavior.setdefault(
            f["behavior"],
            {"polarity": f["polarity"], "count": 0, "example": None, "channels": set()},
        )
        b["count"] += 1
        b["channels"].add(f["channel"])
        if b["example"] is None:
            b["example"] = f["evidence"]
    return sorted(by_behavior.items(), key=lambda kv: (-kv[1]["count"], kv[0]))


def _leans_on(profile: list[tuple]) -> str:
    """One-line 'leans on' summary: the top respectful and top disrespectful behavior."""
    top_pos = next((b for b, v in profile if v["polarity"] == "respectful"), None)
    top_neg = next((b for b, v in profile if v["polarity"] == "disrespectful"), None)
    parts = []
    if top_pos:
        parts.append(f"{top_pos} (respectful)")
    if top_neg:
        parts.append(f"{top_neg} (disrespectful)")
    return ", ".join(parts) if parts else "—"


def _print_fingerprint(conn, author_id: str, name: str) -> None:
    findings = store.person_findings(conn, author_id)
    if not findings:
        print(f"  {name}: no findings yet.\n")
        return

    profile = fingerprint(findings)
    pos = sum(v["count"] for _, v in profile if v["polarity"] == "respectful")
    neg = sum(v["count"] for _, v in profile if v["polarity"] == "disrespectful")
    channels = {c for _, v in profile for c in v["channels"]}

    print(f"  {name}  —  {pos} respectful · {neg} disrespectful "
          f"({len(findings)} findings across {len(channels)} channel"
          f"{'s' if len(channels) != 1 else ''})")
    print(f"    leans on: {_leans_on(profile)}")
    width = max(len(b) for b, _ in profile)
    for behavior, v in profile:
        mark = MARK.get(v["polarity"], "? ")
        example = v["example"] or ""
        if len(example) > 60:
            example = example[:57] + "…"
        print(f"    {v['count']:>2}× {mark}{behavior.ljust(width)}  “{example}”")
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
    people = store.people(conn)
    if not people:
        sys.exit("database has no findings yet — score something with "
                 "`score.py --save` first.")

    print(f"\n=== Behavior fingerprints (personal-mirror view) — {db_path} ===\n")

    if who is not None:
        try:
            author_id = store.resolve_author(conn, who)
        except ValueError as e:
            sys.exit(str(e))
        if not store.is_known(conn, author_id):
            sys.exit(f"no one matching {who!r} in the data.")
        _print_fingerprint(conn, author_id, store.display_name(conn, author_id))
    else:
        for p in people:
            _print_fingerprint(conn, p["author_id"], p["display_name"])

    conn.close()


if __name__ == "__main__":
    main()
