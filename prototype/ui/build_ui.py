#!/usr/bin/env python3
# SugApp — proprietary & confidential. © 2026 <Your Legal Name>. All rights reserved.
# Trade-secret methodology; not for distribution. See /LICENSE and /IP.md.
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
from rubric import BEHAVIORS  # noqa: E402

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

    def _pairs(behaviors):
        """[[display label, count], ...] for the behaviors that actually occurred."""
        return [[LABEL.get(b, b), counts[b]] for b in behaviors if counts.get(b)]

    # Each tile carries a `detail`: why the number is what it is, which behaviors
    # LIFTED it, and which LOST points — the aggregate breakdown for drill-down.
    # Driven by the rubric's behaviors, so it generalizes to any rubric.
    resp_share = pct(pos, pos + neg)
    dwd_pct = pct(dwd, dwd + atk)
    tiles = [
        ["Respectful share", resp_share, "%", "good", resp_share, "of flagged behaviors",
         {"why": f"{resp_share}% = {pos} respectful of {pos + neg} flagged behaviors this week.",
          "made": _pairs([b for b in BEHAVIORS if BEHAVIORS[b]["polarity"] == "respectful"]),
          "lost": _pairs([b for b in BEHAVIORS if BEHAVIORS[b]["polarity"] == "disrespectful"])}],
        ["Listening moments", listening, "", "good", min(100, listening * 11 + 8), "acknowledge · ask · invite",
         {"why": f"{listening} listening moments = acknowledgment + question-asking + inviting others.",
          "made": _pairs(["acknowledgment", "question_asking", "invites_others"]),
          "lost": _pairs(["dismissiveness"])}],
        ["Disagree w/ dignity", dwd_pct, "%", "good", dwd_pct, "of disagreements stay respectful",
         {"why": (f"{dwd_pct}% = {dwd} of {dwd + atk} disagreement moments stayed respectful."
                  if (dwd + atk) else "No disagreement moments flagged this week."),
          "made": _pairs(["disagree_with_dignity"]),
          "lost": _pairs(["personal_attack"])}],
        ["Dismissive moments", counts["dismissiveness"], "", "bad", min(100, counts["dismissiveness"] * 14 + 8), "lower is better",
         {"why": f"{counts['dismissiveness']} dismissive moments this week — these drag the rating down.",
          "made": [],
          "lost": _pairs(["dismissiveness"])}],
    ]

    # behavior label → plain-English definition, for behavior-balance drill-down.
    behavior_defs = {LABEL.get(b, b): BEHAVIORS[b]["definition"] for b in BEHAVIORS}

    total_people = sum(t[1] for t in teams)
    latest_date = datetime.fromisoformat(runs[-1]["created_at"]).strftime("%b %-d, %Y")
    org = {
        "index": org_index, "delta": delta,
        "sub": f"Week of {latest_date} · {total_people} people across {len(teams)} teams "
               f"· {len(store.consented_authors(conn))} opted in",
        "trend": trend, "trendLabels": trend_labels,
        "tiles": tiles, "balance": balance, "teams": teams,
        "behaviorDefs": behavior_defs,
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
        ch = last["channel"]
        p_pos = last["respectful"] or 0
        p_neg = last["disrespectful"] or 0
        pcounts = defaultdict(int)
        moments = []
        for f in conn.execute(
            "SELECT behavior, polarity, evidence, coaching_rewrite, rationale, message_index "
            "FROM findings WHERE run_id=? AND author_id=? ORDER BY message_index, id",
            (latest_run_id, author_id)
        ):
            pcounts[f["behavior"]] += 1
            m = {"b": LABEL.get(f["behavior"], f["behavior"]),
                 "p": "pos" if f["polarity"] == "respectful" else "neg",
                 "why": f["rationale"], "q": f["evidence"],
                 # where in the conversation this was caught — the channel + message position
                 "where": f'{ch} · message {(f["message_index"] or 0) + 1}'}
            if f["polarity"] == "disrespectful" and f["coaching_rewrite"]:
                m["rw"] = f["coaching_rewrite"]
            moments.append(m)
        goal = store.get_goal(conn, author_id)
        rough = pcounts["dismissiveness"] + pcounts["personal_attack"] + pcounts["gatekeeping"]
        people.append({
            "name": name, "you": name == YOU, "team": team_of(ch)[0],
            "pos": p_pos, "neg": p_neg,
            # Same 0–100 Respect Index the org/teams use — one scale everywhere.
            "index": respect_index(_fake({"pos": p_pos, "neg": p_neg})),
            "goal": goal["goal"] if goal else "Pick one thing to focus on this week.",
            "tiles": [
                ["Built on others", pcounts["acknowledgment"], "good" if pcounts["acknowledgment"] else "mut"],
                ["Questions asked", pcounts["question_asking"], "good" if pcounts["question_asking"] else "mut"],
                ["Respectful disagreement", pcounts["disagree_with_dignity"], "good" if pcounts["disagree_with_dignity"] else "mut"],
                ["Rough moments", rough, "bad" if rough else "good"],
            ],
            "moments": moments,
            "suggestions": _suggestions(pcounts),
            # Respect Index per run, chronological — same scale as the headline number.
            "indexTrend": [respect_index(_fake({"pos": t["respectful"] or 0,
                                                "neg": t["disrespectful"] or 0}))
                           for t in timeline],
        })
    # 'You' first, then most-respectful (by the shared index).
    people.sort(key=lambda p: (not p["you"], -p["index"]))

    conn.close()
    return {"org": org, "people": people}


def _fake(t):
    """respect_index() takes a findings list; feed it minimal stand-ins by polarity."""
    return [{"polarity": "respectful"}] * t["pos"] + [{"polarity": "disrespectful"}] * t["neg"]


def store_neg():
    return {"dismissiveness", "personal_attack", "gatekeeping"}


# Concrete, behavior-specific coaching. Each rule fires from the person's own
# behavior counts, so the advice points at what actually showed up (or what's
# missing). Negatives first (most actionable), then gaps, capped at 3.
def _suggestions(pcounts: dict) -> list[dict]:
    out = []
    if pcounts.get("dismissiveness"):
        out.append({"t": "Drop the minimizers",
                    "s": "Swap “obviously / as I said” for a plain restatement — assume good faith."})
    if pcounts.get("personal_attack"):
        out.append({"t": "Attack the idea, not the person",
                    "s": "Name the specific concern (“I don't think access is the bottleneck”), not the person."})
    if pcounts.get("gatekeeping"):
        out.append({"t": "Hand off with a next step",
                    "s": "When something isn't yours, point to the right owner instead of a wall."})
    if len(out) < 3 and not pcounts.get("question_asking"):
        out.append({"t": "Ask before asserting",
                    "s": "Ask one genuine question before pushing back — curiosity over a verdict."})
    if len(out) < 3 and not pcounts.get("acknowledgment"):
        out.append({"t": "Build on others",
                    "s": "Reference what someone said before adding your point."})
    if len(out) < 3 and not pcounts.get("invites_others"):
        out.append({"t": "Make room",
                    "s": "Invite a quieter voice in — “what does everyone think?”"})
    if not out:  # nothing to fix — reinforce, don't invent a problem
        out.append({"t": "Keep it up",
                    "s": "Your recent messages land well — keep crediting people and inviting others in."})
    return out[:3]


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
