#!/usr/bin/env python3
"""Build the SugApp dashboard from a real scoring database.

Reads findings out of the SQLite store the scorer writes (store.py), computes
the org + per-person view-model — applying the same Respect Index formula and
k-anonymity threshold the CLI uses (from score.py) — and injects it into
template.html to produce a single self-contained dashboard page.

    python build_ui.py --db demo.db -o saas_dashboard.html
    open saas_dashboard.html

The org view is aggregate-only and suppresses teams under K_ANON people; the
per-person "mirror" is name-attached by design (PRODUCT.md §5).
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import store  # noqa: E402
from score import K_ANON, respect_index  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

TEAMS = {  # channel → (display name, dot color)
    "#eng-standup": ("Platform", "#155e4c"),
    "#growth-sync": ("Growth", "#0e9e7a"),
    "#design-crit": ("Design", "#c85a34"),
}
LABEL = {
    "acknowledgment": "Acknowledgment", "question_asking": "Question-asking",
    "invites_others": "Invites others", "disagree_with_dignity": "Disagree with dignity",
    "credit_attribution": "Credit &amp; attribution", "enabling": "Enabling",
    "dismissiveness": "Dismissiveness", "personal_attack": "Personal attack",
    "gatekeeping": "Gatekeeping",
}
YOU = "Sam"  # who the demo logs in as


def team_of(channel):
    return TEAMS.get(channel, (channel.strip("#").title(), "#8b968f"))


def iso_week(ts):
    d = datetime.fromisoformat(ts)
    return d.isocalendar()[:2]  # (year, week)


def build(db_path):
    conn = store.connect(db_path)
    runs = conn.execute(
        "SELECT id, created_at, channel, participant_count FROM runs ORDER BY created_at"
    ).fetchall()
    if not runs:
        sys.exit("no runs in the database — seed it first: python seed_demo.py")

    # Per-run respectful/disrespectful tallies.
    tally = {r["id"]: {"pos": 0, "neg": 0} for r in runs}
    for f in conn.execute("SELECT run_id, polarity FROM findings"):
        side = "pos" if f["polarity"] == "respectful" else "neg"
        tally[f["run_id"]][side] += 1

    # --- Weekly org trend: for each ISO week, weighted index over non-suppressed teams
    weeks = defaultdict(list)
    for r in runs:
        weeks[iso_week(r["created_at"])].append(r)
    trend, trend_labels = [], []
    for wk in sorted(weeks):
        num = den = 0
        for r in weeks[wk]:
            if r["participant_count"] < K_ANON:
                continue  # k-anonymity: small teams never enter an aggregate
            t = tally[r["id"]]
            num += respect_index(_fake(t)) * r["participant_count"]
            den += r["participant_count"]
        if den:
            trend.append(round(num / den))
            any_run = weeks[wk][0]
            trend_labels.append(datetime.fromisoformat(any_run["created_at"]).strftime("%b %-d"))
    org_index = trend[-1] if trend else 0
    delta = (trend[-1] - trend[-2]) if len(trend) >= 2 else 0

    # --- Latest run per channel → teams table + "this week" aggregates
    latest = {}
    for r in runs:
        latest[r["channel"]] = r  # runs are ordered; last wins
    teams, this_week_run_ids = [], []
    for ch, r in sorted(latest.items(), key=lambda kv: -tally[kv[1]["id"]]["pos"]):
        name, color = team_of(ch)
        this_week_run_ids.append(r["id"])
        ppl = r["participant_count"]
        idx = None if ppl < K_ANON else respect_index(_fake(tally[r["id"]]))
        teams.append([name, ppl, idx, color])

    # Behavior balance + tiles from this-week findings across all channels.
    bal = defaultdict(lambda: [None, 0])
    counts = defaultdict(int)
    qmarks = "?"  # placeholder
    for f in conn.execute(
        "SELECT behavior, polarity FROM findings WHERE run_id IN (%s)"
        % ",".join("?" * len(this_week_run_ids)), this_week_run_ids
    ):
        b, pol = f["behavior"], f["polarity"]
        bal[b] = [pol, bal[b][1] + 1]
        counts[b] += 1
    balance = sorted(
        ([LABEL.get(b, b), "pos" if v[0] == "respectful" else "neg", v[1]]
         for b, v in bal.items()),
        key=lambda x: (x[1] != "pos", -x[2]),
    )

    pos = sum(n for b, n in counts.items() if b not in store_neg())
    neg = sum(n for b, n in counts.items() if b in store_neg())
    listening = counts["acknowledgment"] + counts["question_asking"] + counts["invites_others"]
    dwd, atk = counts["disagree_with_dignity"], counts["personal_attack"]
    tiles = [
        ["Respectful share", pct(pos, pos + neg), "%", "good", pct(pos, pos + neg), "of flagged behaviors"],
        ["Listening moments", listening, "", "good", min(100, listening * 11 + 8), "acknowledge · ask · invite"],
        ["Disagree w/ dignity", pct(dwd, dwd + atk), "%", "good", pct(dwd, dwd + atk), "of disagreements stay respectful"],
        ["Dismissive moments", counts["dismissiveness"], "", "bad", min(100, counts["dismissiveness"] * 14 + 8), "lower is better"],
    ]

    total_people = sum(t[1] for t in teams)
    latest_date = datetime.fromisoformat(runs[-1]["created_at"]).strftime("%b %-d, %Y")
    org = {
        "index": org_index, "delta": delta,
        "sub": f"Week of {latest_date} · {total_people} people across {len(teams)} teams "
               f"· {len(store.consented_authors(conn))} opted in",
        "trend": trend, "trendLabels": trend_labels,
        "tiles": tiles, "balance": balance, "teams": teams,
    }

    # --- People (personal mirror). Keyed by the stable author_id; display by name.
    people = []
    for person in store.people(conn):
        author_id = person["author_id"]
        name = person["display_name"]
        timeline = store.person_timeline(conn, author_id)
        if not timeline:
            continue
        last = timeline[-1]
        latest_run_id = last["id"]
        p_pos = last["respectful"] or 0
        p_neg = last["disrespectful"] or 0
        pcounts = defaultdict(int)
        moments = []
        for f in conn.execute(
            "SELECT behavior, polarity, evidence, coaching_rewrite, rationale "
            "FROM findings WHERE run_id=? AND author_id=? ORDER BY id", (latest_run_id, author_id)
        ):
            pcounts[f["behavior"]] += 1
            m = {"b": LABEL.get(f["behavior"], f["behavior"]),
                 "p": "pos" if f["polarity"] == "respectful" else "neg",
                 "why": f["rationale"], "q": f["evidence"]}
            if f["polarity"] == "disrespectful" and f["coaching_rewrite"]:
                m["rw"] = f["coaching_rewrite"]
            moments.append(m)
        goal = store.get_goal(conn, author_id)
        ch = last["channel"]
        rough = pcounts["dismissiveness"] + pcounts["personal_attack"] + pcounts["gatekeeping"]
        people.append({
            "name": name, "you": name == YOU, "team": team_of(ch)[0],
            "pos": p_pos, "neg": p_neg,
            "goal": goal["goal"] if goal else "Pick one thing to focus on this week.",
            "tiles": [
                ["Built on others", pcounts["acknowledgment"], "good" if pcounts["acknowledgment"] else "mut"],
                ["Questions asked", pcounts["question_asking"], "good" if pcounts["question_asking"] else "mut"],
                ["Respectful disagreement", pcounts["disagree_with_dignity"], "good" if pcounts["disagree_with_dignity"] else "mut"],
                ["Rough moments", rough, "bad" if rough else "good"],
            ],
            "moments": moments,
            # trend = net balance (respectful − to-work-on) per run, chronological
            "trend": [(t["respectful"] or 0) - (t["disrespectful"] or 0) for t in timeline],
        })
    # 'You' first, then most-respectful.
    people.sort(key=lambda p: (not p["you"], -(p["pos"] - p["neg"])))

    conn.close()
    return {"org": org, "people": people}


def _fake(t):
    """respect_index() takes a findings list; feed it minimal stand-ins by polarity."""
    return [{"polarity": "respectful"}] * t["pos"] + [{"polarity": "disrespectful"}] * t["neg"]


def store_neg():
    return {"dismissiveness", "personal_attack", "gatekeeping"}


def pct(a, b):
    return round(100 * a / b) if b else 0


def main():
    args = sys.argv[1:]
    db = "sugapp.db"
    out = os.path.join(HERE, "saas_dashboard.html")
    if "--db" in args:
        db = args[args.index("--db") + 1]
    if "-o" in args:
        out = args[args.index("-o") + 1]
    db_path = db if os.path.isabs(db) else os.path.join(HERE, db)

    view = build(db_path)
    tmpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    html = tmpl.replace("/*__DATA__*/null", json.dumps(view, ensure_ascii=False))
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"built {out}  ({len(view['people'])} people, "
          f"org index {view['org']['index']})")


if __name__ == "__main__":
    main()
