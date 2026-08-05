#!/usr/bin/env python3
# SugApp — proprietary & confidential. © 2026 <Your Legal Name>. All rights reserved.
# Trade-secret methodology; not for distribution. See /LICENSE and /IP.md.
"""Momentum — is respect getting better or worse, and by how much?

`trends.py` shows the accumulated totals. This shows the *direction*: it buckets
the persisted history into periods (day / week / month) and reports each period's
Respect Index alongside the change from the period before it — the "interruptions
down 30% this month" signal the behavior-change loop is built on (PRODUCT.md §6).

Two views, matching the privacy split (PRODUCT.md §5):
  * Channel momentum — the org view. k-anonymity enforced: a channel-period is
    suppressed unless it clears the K_ANON participant threshold.
  * Personal momentum — the personal mirror. Name-attached on purpose: it is the
    person's own trend, never an org-facing per-individual rollup.

Usage:
    python momentum.py                       # month buckets, default sugapp.db
    python momentum.py --period week
    python momentum.py --channel '#eng-standup'
    python momentum.py --db mine.db --period day
"""
import os
import sys
from collections import OrderedDict

import store
from score import K_ANON, respect_index


def _index(pos: int, neg: int) -> int:
    """Respect Index (0-100) for a period's tallies, via the shared formula.

    Reuses score.respect_index so the number means the same thing everywhere; a
    period with no findings comes back neutral (75), same as a run with none.
    """
    return respect_index(
        [{"polarity": "respectful"}] * pos + [{"polarity": "disrespectful"}] * neg
    )


def group_by(rows: list[dict], key: str) -> "OrderedDict[str, list]":
    """Group period rows by an entity key, preserving the query's period order."""
    grouped: "OrderedDict[str, list]" = OrderedDict()
    for row in rows:
        grouped.setdefault(row[key], []).append(row)
    return grouped


def with_deltas(periods: list[dict]) -> list[dict]:
    """Annotate each period with its Respect Index and delta vs the prior period.

    `delta` is the change in index points from the previous period (None for the
    first period, which has nothing to compare against).
    """
    out, prev = [], None
    for p in periods:
        idx = _index(p["respectful"], p["disrespectful"])
        out.append({**p, "index": idx, "delta": None if prev is None else idx - prev})
        prev = idx
    return out


def arrow(delta) -> str:
    """A direction glyph for a delta: up / down / flat / (no prior period)."""
    if delta is None:
        return " "
    if delta > 0:
        return "▲"
    if delta < 0:
        return "▼"
    return "▬"


def _fmt_delta(delta) -> str:
    if delta is None:
        return ""
    return f"{arrow(delta)} {delta:+d}"


def _print_channel_momentum(conn, period: str, channel_filter: str | None) -> None:
    rows = store.channel_momentum(conn, period)
    if channel_filter:
        rows = [r for r in rows if r["channel"] == channel_filter]

    print("--- Channel momentum (team rollup, org view — k-anonymity enforced) ---")
    if not rows:
        print("  (no matching runs)\n")
        return

    for channel, periods in group_by(rows, "channel").items():
        print(f"  {channel}")
        for p in with_deltas(periods):
            if p["max_participants"] < K_ANON:
                print(f"    {p['period']:<10} suppressed "
                      f"(max {p['max_participants']} participants, k={K_ANON})")
            else:
                delta = _fmt_delta(p["delta"])
                print(f"    {p['period']:<10} {p['index']:>3}/100  {delta:<6} "
                      f"({p['respectful']} resp, {p['disrespectful']} disresp)")
    print()


def _print_person_momentum(conn, period: str) -> None:
    rows = store.person_momentum(conn, period)
    print("--- Personal momentum (personal-mirror view) ---")
    if not rows:
        print("  (no findings yet)\n")
        return

    for _author_id, periods in group_by(rows, "author_id").items():
        name = periods[0]["display_name"]
        annotated = with_deltas(periods)
        latest = annotated[-1]
        headline = _fmt_delta(latest["delta"]) or "(first period)"
        print(f"  {name}: {latest['index']}/100 latest  {headline}")
        for p in annotated:
            delta = _fmt_delta(p["delta"])
            print(f"    {p['period']:<10} {p['index']:>3}/100  {delta:<6} "
                  f"({p['respectful']} resp, {p['disrespectful']} disresp)")
    print()


def main() -> None:
    args = sys.argv[1:]

    def take(flag: str, default=None):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(f"{flag} needs a value")
            return args[i + 1]
        return default

    db_path = take("--db", store.DEFAULT_DB)
    period = take("--period", "month")
    channel_filter = take("--channel")

    if period not in store._PERIOD_FMT:
        sys.exit(f"--period must be one of {', '.join(store._PERIOD_FMT)}; got {period!r}")
    if not os.path.exists(db_path):
        sys.exit(f"no database at {db_path} — score something with "
                 f"`score.py --save` first.")

    conn = store.connect(db_path)
    if not store.run_history(conn):
        sys.exit("database has no runs yet — score something with "
                 "`score.py --save` first.")

    print(f"\n=== Respect momentum ({period} buckets) — {db_path} ===\n")
    _print_channel_momentum(conn, period, channel_filter)
    _print_person_momentum(conn, period)
    conn.close()


if __name__ == "__main__":
    main()
