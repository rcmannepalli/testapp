#!/usr/bin/env python3
# SugApp — proprietary & confidential. © 2026 <Your Legal Name>. All rights reserved.
# Trade-secret methodology; not for distribution. See /LICENSE and /IP.md.
"""Personal mirror — a one-person dashboard generated as a standalone HTML file.

This is the "person sees their own data first and most" surface from
PRODUCT.md §5, and the reflect → choose loop from §6: your own quotes, what's
landing well vs. worth a second look, a trend over time, and one self-set goal.

It reads the SQLite store written by `score.py --save` and emits a single
self-contained HTML file (inline CSS, no JavaScript, no web framework, no
server) — open it in any browser. Zero dependencies beyond the Python stdlib.

Usage:
    python mirror.py Dana                       # → mirror_Dana.html
    python mirror.py Dana --set-goal "Ask one genuine question before pushing back"
    python mirror.py Dana --db team.db --out dana.html
    python mirror.py --list                     # who's in the database

The org never sees this view — it is name-attached on purpose and for the
person only. Team-level reporting stays anonymized (see trends.py).
"""
import html
import os
import sys

import store

PALETTE = {
    "bg": "#F4F1EA", "card": "#FFFFFF", "ink": "#2B2A26", "muted": "#7A756B",
    "good": "#3F7D5B", "good_bg": "#E7F0EA", "warn": "#C2703D", "warn_bg": "#F6E9DF",
    "line": "#E5E0D5", "accent": "#B5532A",
}


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def fmt_date(iso: str) -> str:
    return iso.replace("T", " ").replace("+00:00", "").strip()[:16]


def balance_bar(pos: int, neg: int) -> str:
    total = pos + neg
    if total == 0:
        return f'<div class="bar empty">no findings yet</div>'
    pg = round(100 * pos / total)
    ng = 100 - pg
    return (
        '<div class="bar">'
        f'<span class="seg good" style="width:{pg}%" title="{pos} respectful"></span>'
        f'<span class="seg warn" style="width:{ng}%" title="{neg} worth a look"></span>'
        "</div>"
    )


def timeline_html(rows: list[dict]) -> str:
    if not rows:
        return '<p class="muted">No runs recorded yet.</p>'
    out = ['<div class="timeline">']
    for r in rows:
        pos, neg = r["respectful"] or 0, r["disrespectful"] or 0
        out.append(
            '<div class="trow">'
            f'<span class="tdate">{esc(fmt_date(r["created_at"]))}</span>'
            f'<span class="tchan">{esc(r["channel"])}</span>'
            f'{balance_bar(pos, neg)}'
            f'<span class="tnums"><b class="good">{pos}</b> / '
            f'<b class="warn">{neg}</b></span>'
            "</div>"
        )
    out.append("</div>")
    return "\n".join(out)


def findings_html(findings: list[dict], polarity: str) -> str:
    items = [f for f in findings if f["polarity"] == polarity]
    if not items:
        none = ("Nothing flagged as worth a second look — nice."
                if polarity == "disrespectful"
                else "No respectful behaviors captured yet.")
        return f'<p class="muted">{none}</p>'
    cls = "good" if polarity == "respectful" else "warn"
    out = []
    for f in items:
        rewrite = ""
        if polarity == "disrespectful" and f.get("coaching_rewrite", "").strip():
            rewrite = (
                '<div class="rewrite"><span class="rlabel">a more respectful way</span>'
                f'“{esc(f["coaching_rewrite"])}”</div>'
            )
        out.append(
            f'<div class="finding {cls}">'
            f'<div class="fhead"><span class="behavior">{esc(f["behavior"])}</span>'
            f'<span class="chan">{esc(f["channel"])} · {esc(fmt_date(f["created_at"]))}</span></div>'
            f'<blockquote>“{esc(f["evidence"])}”</blockquote>'
            f'<div class="rationale">{esc(f["rationale"])}</div>'
            f"{rewrite}"
            "</div>"
        )
    return "\n".join(out)


def goal_html(goal: dict | None, author: str) -> str:
    if goal:
        return (
            '<div class="goalcard set">'
            '<span class="glabel">Your goal</span>'
            f'<p class="gtext">“{esc(goal["goal"])}”</p>'
            f'<span class="muted">set {esc(fmt_date(goal["set_at"]))}</span>'
            "</div>"
        )
    return (
        '<div class="goalcard unset">'
        '<span class="glabel">Pick one thing to work on</span>'
        '<p class="gtext muted">No goal set yet. Choose a single behavior to focus on:</p>'
        f'<code>python mirror.py {esc(author)} --set-goal "Ask one genuine '
        'question before pushing back"</code>'
        "</div>"
    )


def render_page(author: str, findings: list[dict], timeline: list[dict],
                goal: dict | None) -> str:
    pos = sum(1 for f in findings if f["polarity"] == "respectful")
    neg = sum(1 for f in findings if f["polarity"] == "disrespectful")
    p = PALETTE
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your communication mirror — {esc(author)}</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: {p['bg']}; color: {p['ink']};
    font: 16px/1.55 "Iowan Old Style", Georgia, "Times New Roman", serif; }}
  .wrap {{ max-width: 760px; margin: 0 auto; padding: 40px 24px 80px; }}
  h1 {{ font-size: 30px; margin: 0 0 4px; }}
  h2 {{ font-size: 18px; margin: 36px 0 12px; letter-spacing: .01em; }}
  .sub {{ color: {p['muted']}; margin: 0 0 28px; font-style: italic; }}
  .privacy {{ background: {p['card']}; border: 1px solid {p['line']};
    border-left: 3px solid {p['accent']}; border-radius: 8px; padding: 12px 16px;
    font-size: 14px; color: {p['muted']}; margin-bottom: 28px; }}
  .card {{ background: {p['card']}; border: 1px solid {p['line']};
    border-radius: 12px; padding: 20px 22px; margin-bottom: 18px; }}
  .summary {{ display: flex; gap: 28px; align-items: center; flex-wrap: wrap; }}
  .bignum {{ font-size: 40px; font-weight: 700; line-height: 1; }}
  .bignum.good {{ color: {p['good']}; }} .bignum.warn {{ color: {p['warn']}; }}
  .bignum small {{ display: block; font-size: 13px; font-weight: 400;
    color: {p['muted']}; font-style: italic; margin-top: 4px; }}
  .bar {{ display: flex; height: 14px; border-radius: 7px; overflow: hidden;
    background: {p['line']}; min-width: 160px; flex: 1; }}
  .bar.empty {{ color: {p['muted']}; font-size: 12px; font-style: italic;
    background: none; height: auto; }}
  .seg.good {{ background: {p['good']}; }} .seg.warn {{ background: {p['warn']}; }}
  .timeline {{ display: flex; flex-direction: column; gap: 10px; }}
  .trow {{ display: flex; align-items: center; gap: 12px; font-size: 13px; }}
  .tdate {{ width: 104px; color: {p['muted']}; flex: none; }}
  .tchan {{ width: 110px; color: {p['muted']}; flex: none;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .tnums {{ width: 56px; text-align: right; flex: none; }}
  b.good {{ color: {p['good']}; }} b.warn {{ color: {p['warn']}; }}
  .finding {{ border-left: 3px solid {p['line']}; padding: 4px 0 4px 16px;
    margin: 16px 0; }}
  .finding.good {{ border-color: {p['good']}; }}
  .finding.warn {{ border-color: {p['warn']}; }}
  .fhead {{ display: flex; justify-content: space-between; align-items: baseline;
    gap: 12px; }}
  .behavior {{ font-weight: 700; }}
  .chan {{ color: {p['muted']}; font-size: 12px; flex: none; }}
  blockquote {{ margin: 8px 0; font-style: italic; }}
  .rationale {{ font-size: 14px; color: {p['muted']}; }}
  .rewrite {{ background: {p['good_bg']}; border-radius: 8px; padding: 10px 14px;
    margin-top: 10px; font-size: 14px; font-style: italic; }}
  .rlabel {{ display: block; font-style: normal; font-size: 11px;
    text-transform: uppercase; letter-spacing: .06em; color: {p['good']};
    margin-bottom: 4px; }}
  .goalcard {{ background: {p['warn_bg']}; border-radius: 12px; padding: 18px 22px;
    margin-bottom: 18px; }}
  .glabel {{ font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
    color: {p['accent']}; }}
  .gtext {{ font-size: 19px; margin: 6px 0; }}
  code {{ display: block; background: {p['ink']}; color: #F4F1EA;
    padding: 10px 14px; border-radius: 8px; font-size: 12.5px; margin-top: 8px;
    font-family: "SF Mono", Menlo, monospace; white-space: pre-wrap; }}
  .muted {{ color: {p['muted']}; }}
  footer {{ margin-top: 40px; font-size: 12px; color: {p['muted']};
    text-align: center; font-style: italic; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Your communication mirror</h1>
  <p class="sub">{esc(author)} · how your words are landing</p>

  <div class="privacy">
    This view is yours. Your manager and your organization only ever see
    anonymized team aggregates — never your name, your quotes, or this page.
  </div>

  {goal_html(goal, author)}

  <div class="card summary">
    <div class="bignum good">{pos}<small>landing well</small></div>
    <div class="bignum warn">{neg}<small>worth a look</small></div>
    <div style="flex:1; min-width:160px">{balance_bar(pos, neg)}</div>
  </div>

  <h2>Your trend over time</h2>
  <div class="card">{timeline_html(timeline)}</div>

  <h2>What's landing well</h2>
  {findings_html(findings, "respectful")}

  <h2>Worth a second look</h2>
  {findings_html(findings, "disrespectful")}

  <footer>
    SugApp · behaviors, not traits — every flag carries the exact quote it came from.
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

    out_path = None
    if "--out" in args:
        i = args.index("--out")
        if i + 1 >= len(args):
            sys.exit("--out needs a path")
        out_path = args[i + 1]
        args = args[:i] + args[i + 2 :]

    set_goal_text = None
    if "--set-goal" in args:
        i = args.index("--set-goal")
        if i + 1 >= len(args):
            sys.exit('--set-goal needs text, e.g. --set-goal "ask more questions"')
        set_goal_text = args[i + 1]
        args = args[:i] + args[i + 2 :]

    if not os.path.exists(db_path):
        sys.exit(f"no database at {db_path} — score something with "
                 f"`score.py --save` first.")
    conn = store.connect(db_path)

    if "--list" in args:
        ppl = store.people(conn)
        print("People in the database:" if ppl else "No people scored yet.")
        for p in ppl:
            print(f"  {p['display_name']}  ({p['author_id']})")
        conn.close()
        return

    positionals = [a for a in args if not a.startswith("--")]
    if len(positionals) != 1:
        sys.exit(__doc__)
    # Accept a display name or an author_id; the mirror is keyed by the stable id.
    try:
        author_id = store.resolve_author(conn, positionals[0])
    except ValueError as e:
        conn.close()
        sys.exit(str(e))
    author = store.display_name(conn, author_id)

    if set_goal_text is not None:
        store.set_goal(conn, author_id, set_goal_text)
        print(f"  goal set for {author}: “{set_goal_text}”")

    findings = store.person_findings(conn, author_id)
    if not findings and set_goal_text is None:
        known = ", ".join(p["display_name"] for p in store.people(conn)) or "(none yet)"
        sys.exit(f"no findings for '{positionals[0]}'. People in the database: {known}")
    timeline = store.person_timeline(conn, author_id)
    goal = store.get_goal(conn, author_id)
    conn.close()

    out_path = out_path or f"mirror_{author}.html"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render_page(author, findings, timeline, goal))
    print(f"  wrote {out_path} — open it in a browser "
          f"({len(findings)} findings, {len(timeline)} runs)")


if __name__ == "__main__":
    main()
