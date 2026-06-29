#!/usr/bin/env python3
"""Team Respect Index dashboard — the org-view counterpart to the personal mirror.

This is the "org sees aggregates only" surface from PRODUCT.md §5: the headline
Respect Index, its trend over time, and the behavior mix — and **never a name or
a quote**. It is the visual equivalent of trends.py, generated as a single
self-contained HTML file (inline CSS, no JavaScript, no server, stdlib only).

k-anonymity is enforced here exactly as in the live report and trends.py: any
run with fewer than K_ANON participants is shown as "suppressed", never given a
number, and excluded from the headline aggregate.

Usage:
    python dashboard.py                  # default sugapp.db → team_dashboard.html
    python dashboard.py --db team.db --out team.html

By construction this view reads only run-level tallies and behavior counts — it
never touches per-person data, so no individual can be identified from it.
"""
import os
import sys

import store
from score import K_ANON, respect_index
# Reuse the mirror's palette + helpers so the two dashboards stay visually in sync.
from mirror import PALETTE, esc, fmt_date, balance_bar


def _index_from(pos: int, neg: int) -> int:
    return respect_index([{"polarity": "respectful"}] * pos
                         + [{"polarity": "disrespectful"}] * neg)


def headline_html(history: list[dict]) -> str:
    eligible = [r for r in history if r["participant_count"] >= K_ANON]
    pos = sum(r["respectful"] or 0 for r in eligible)
    neg = sum(r["disrespectful"] or 0 for r in eligible)
    suppressed = len(history) - len(eligible)
    note = (f" · {suppressed} run(s) suppressed for k-anonymity"
            if suppressed else "")
    if pos + neg == 0:
        return ('<div class="card headline"><div class="muted">Not enough '
                f'k-anonymous data yet to report a Respect Index.{esc(note)}</div></div>')
    idx = _index_from(pos, neg)
    return (
        '<div class="card headline">'
        f'<div class="bignum index">{idx}<small>/ 100 Respect Index</small></div>'
        f'<div style="flex:1; min-width:200px">{balance_bar(pos, neg)}'
        f'<div class="muted" style="margin-top:8px">across {len(eligible)} '
        f'run(s) · {pos} respectful, {neg} disrespectful behaviors{esc(note)}</div></div>'
        "</div>"
    )


def trend_html(history: list[dict]) -> str:
    if not history:
        return '<p class="muted">No runs recorded yet.</p>'
    out = ['<div class="timeline">']
    for r in history:
        pos, neg = r["respectful"] or 0, r["disrespectful"] or 0
        if r["participant_count"] < K_ANON:
            idx = (f'<span class="suppressed">suppressed · '
                   f'{r["participant_count"]} participants</span>')
            bar = '<div class="bar empty">k-anonymity</div>'
        else:
            idx = f'<b class="index">{_index_from(pos, neg)}</b>'
            bar = balance_bar(pos, neg)
        out.append(
            '<div class="trow">'
            f'<span class="tdate">{esc(fmt_date(r["created_at"]))}</span>'
            f'<span class="tchan">{esc(r["channel"])}</span>'
            f"{bar}"
            f'<span class="tnums">{idx}</span>'
            "</div>"
        )
    out.append("</div>")
    return "\n".join(out)


def behavior_html(counts: list[dict]) -> str:
    if not counts:
        return '<p class="muted">No behaviors recorded yet.</p>'
    top = max(c["n"] for c in counts)
    out = ['<div class="behaviors">']
    for c in counts:
        cls = "good" if c["polarity"] == "respectful" else "warn"
        pct = round(100 * c["n"] / top)
        out.append(
            '<div class="brow">'
            f'<span class="bname">{esc(c["behavior"])}</span>'
            f'<span class="bbar"><span class="seg {cls}" style="width:{pct}%"></span></span>'
            f'<span class="bn">{c["n"]}</span>'
            "</div>"
        )
    out.append("</div>")
    return "\n".join(out)


def render_page(history: list[dict], counts: list[dict]) -> str:
    channels = sorted({r["channel"] for r in history})
    runs = len(history)
    span = ""
    if history:
        span = (f"{fmt_date(history[0]['created_at'])} – "
                f"{fmt_date(history[-1]['created_at'])}")
    p = PALETTE
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Team Respect Index</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: {p['bg']}; color: {p['ink']};
    font: 16px/1.55 "Iowan Old Style", Georgia, "Times New Roman", serif; }}
  .wrap {{ max-width: 760px; margin: 0 auto; padding: 40px 24px 80px; }}
  h1 {{ font-size: 30px; margin: 0 0 4px; }}
  h2 {{ font-size: 18px; margin: 36px 0 12px; }}
  .sub {{ color: {p['muted']}; margin: 0 0 28px; font-style: italic; }}
  .privacy {{ background: {p['card']}; border: 1px solid {p['line']};
    border-left: 3px solid {p['accent']}; border-radius: 8px; padding: 12px 16px;
    font-size: 14px; color: {p['muted']}; margin-bottom: 28px; }}
  .card {{ background: {p['card']}; border: 1px solid {p['line']};
    border-radius: 12px; padding: 20px 22px; margin-bottom: 18px; }}
  .headline {{ display: flex; gap: 28px; align-items: center; flex-wrap: wrap; }}
  .bignum {{ font-size: 44px; font-weight: 700; line-height: 1; }}
  .bignum.index {{ color: {p['good']}; }}
  .bignum small {{ display: block; font-size: 13px; font-weight: 400;
    color: {p['muted']}; font-style: italic; margin-top: 4px; }}
  .bar {{ display: flex; height: 14px; border-radius: 7px; overflow: hidden;
    background: {p['line']}; }}
  .bar.empty {{ color: {p['muted']}; font-size: 11px; font-style: italic;
    background: none; height: auto; }}
  .seg.good {{ background: {p['good']}; }} .seg.warn {{ background: {p['warn']}; }}
  .timeline {{ display: flex; flex-direction: column; gap: 10px; }}
  .trow {{ display: flex; align-items: center; gap: 12px; font-size: 13px; }}
  .tdate {{ width: 104px; color: {p['muted']}; flex: none; }}
  .tchan {{ width: 120px; color: {p['muted']}; flex: none;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .trow .bar {{ flex: 1; min-width: 120px; }}
  .tnums {{ width: 84px; text-align: right; flex: none; }}
  b.index {{ color: {p['good']}; font-size: 15px; }}
  .suppressed {{ color: {p['muted']}; font-style: italic; font-size: 11px; }}
  .behaviors {{ display: flex; flex-direction: column; gap: 8px; }}
  .brow {{ display: flex; align-items: center; gap: 12px; font-size: 14px; }}
  .bname {{ width: 180px; flex: none; }}
  .bbar {{ flex: 1; height: 12px; background: {p['line']}; border-radius: 6px;
    overflow: hidden; display: flex; }}
  .bn {{ width: 34px; text-align: right; flex: none; color: {p['muted']}; }}
  .muted {{ color: {p['muted']}; }}
  footer {{ margin-top: 40px; font-size: 12px; color: {p['muted']};
    text-align: center; font-style: italic; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Team Respect Index</h1>
  <p class="sub">org view · {esc(str(runs))} run(s){' · ' + esc(span) if span else ''}
    {' · ' + esc(', '.join(channels)) if channels else ''}</p>

  <div class="privacy">
    Aggregates only. This view never shows an individual's name, score, or quotes —
    runs with fewer than {K_ANON} participants are suppressed entirely. Per-person
    feedback lives only in each person's private mirror.
  </div>

  {headline_html(history)}

  <h2>Respect Index over time</h2>
  <div class="card">{trend_html(history)}</div>

  <h2>Behavior mix (all runs)</h2>
  <div class="card">{behavior_html(counts)}</div>

  <footer>
    SugApp · "are people heard and treated with dignity here?" — the highest-respect
    number, not the highest-sentiment one.
  </footer>
</div>
</body>
</html>
"""


def main() -> None:
    args = sys.argv[1:]

    db_path = store.DEFAULT_DB
    if "--db" in args:
        i = args.index("--db")
        if i + 1 >= len(args):
            sys.exit("--db needs a path")
        db_path = args[i + 1]
        args = args[:i] + args[i + 2 :]

    out_path = "team_dashboard.html"
    if "--out" in args:
        i = args.index("--out")
        if i + 1 >= len(args):
            sys.exit("--out needs a path")
        out_path = args[i + 1]
        args = args[:i] + args[i + 2 :]

    if not os.path.exists(db_path):
        sys.exit(f"no database at {db_path} — score something with "
                 f"`score.py --save` first.")
    conn = store.connect(db_path)
    history = store.run_history(conn)
    counts = store.behavior_counts(conn)
    conn.close()

    if not history:
        sys.exit("database has no runs yet — score something with "
                 "`score.py --save` first.")

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render_page(history, counts))
    print(f"  wrote {out_path} — open it in a browser ({len(history)} runs)")


if __name__ == "__main__":
    main()
