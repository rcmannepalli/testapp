# SugApp — Respect & Listening Scorer (Prototype)

A standalone prototype of SugApp's core differentiator: scoring everyday workplace
messages for **observable respect & listening behaviors** — never traits or emotions —
and rolling them up into a team **Respect Index**.

This is the hardest, most novel piece of the product (see [`../docs/PRODUCT.md`](../docs/PRODUCT.md)
§4 "The Respect & Listening model"). It started as just the scorer; it now also has
thin, dependency-free plumbing around it, all Python-stdlib only:

- **Score** a transcript → per-message findings with evidence + coaching rewrites + a
  team Respect Index (`score.py`).
- **Persist** runs to a local SQLite database so trends accumulate (`score.py --save`,
  read back with `trends.py`).
- **Personal mirror** — a one-person HTML dashboard, generated as a standalone file
  (`mirror.py`).
- **Ingest** a Slack *export* into the transcript format (`ingest_slack.py`).

Still deliberately **not** here: a live Slack/Teams API connector, a web server, and
the consent/opt-in layer — those are production Phase-1 work (and the consent layer is
mandatory before any real data flows; see design doc §5).

## What it does

For each message in a transcript, the scorer (Claude Opus 4.8) identifies any of the
named behaviors from the design doc and returns, for each one:

- the **behavior** (e.g. `dismissiveness`, `acknowledgment`, `gatekeeping`, `disagree_with_dignity`)
- a **polarity** (`respectful` or `disrespectful`)
- the **exact quote** that is the evidence (no black-box verdicts)
- a plain-English **coaching rewrite** ("here's a more respectful way to say this")
- a one-line **rationale**

Python then aggregates these into a per-person summary and a **team Respect Index (0–100)**.

### Guardrails baked in (matching the design doc)

- **Behaviors, not traits/emotions** — the rubric scores what was *said*, never personality
  or feelings (EU AI Act line).
- **Evidence always** — every score carries the quote it came from.
- **k-anonymity** — the team rollup is suppressed unless there are at least `K_ANON`
  (default 5) distinct participants, so the prototype never produces a small-group readout
  that could expose an individual.

## Setup

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
```

## Test it

There are two ways to run it, depending on whether you have an API key.

### 1. Offline demo (no key, no cost) — see the pipeline immediately

`--demo` renders a bundled fixture of expected model output (`<transcript>.findings.json`)
instead of calling the API, so you can see the whole flow — findings, evidence, coaching
rewrites, per-person mirror, Respect Index, k-anonymity — with zero spend:

```bash
python score.py --demo sample_transcripts/standup.json
```

This is the fastest way to sanity-check the output format and the aggregation logic.

### 2. Live scoring (needs a key) — the real test of the model

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python score.py sample_transcripts/standup.json
```

or pipe your own transcript on stdin:

```bash
cat my_transcript.json | python score.py -
```

The real validation is comparing live output to your own judgment on transcripts you know:
does it catch the dismissive line you'd have flagged? Does it avoid false positives on
blunt-but-respectful disagreement? Tune `rubric.py` from what you see.

### Transcript format

A JSON object with a `channel` label and a list of `messages`:

```json
{
  "channel": "#eng-standup",
  "messages": [
    {"author": "Dana",  "text": "I already explained this. It's obviously a config issue."},
    {"author": "Sam",   "text": "Good point — building on what Dana said, could we also check the cache?"}
  ]
}
```

Author names are pseudonyms in the samples; in the real product the personal mirror is the
only place a name is ever attached to a score (the org sees aggregates only).

### Ingesting from a Slack export

Hand-writing that JSON is fine for testing, but `ingest_slack.py` produces it from a
real **Slack workspace export** (Settings → Import/Export Data → Export) — no OAuth, no
API token, no live access. It resolves user IDs to names, turns Slack markup into plain
text (`<@U123>` → `@Dana`, `<url|label>` → label, `&amp;` → `&`), and drops
non-conversational events (joins, bot messages, topic changes).

```bash
# An export root has users.json + one folder per channel. Pick a channel:
python ingest_slack.py sample_slack_export --channel eng-standup

# Pipe straight into the scorer (live run needs ANTHROPIC_API_KEY):
python ingest_slack.py sample_slack_export --channel eng-standup | python score.py -

# Or save the transcript, then score + persist it:
python ingest_slack.py sample_slack_export --channel eng-standup -o eng.json
python score.py --save eng.json
```

A single channel folder or one day's `.json` file also work (pass `--users users.json`
if it's not alongside). `sample_slack_export/` is a tiny example you can run as-is. The
**live** Slack API connector and the consent/opt-in gate it requires are deliberately
out of scope here (design doc §5, §8).

## Persistence & trends

The scorer is stateless by default — it scores and prints. Add `--save` to also
write the run and its findings to a local SQLite database (Python stdlib, no extra
dependency), so trends accumulate over time. This is the data layer the dashboards
in [`../docs/PRODUCT.md`](../docs/PRODUCT.md) §8 will read from.

```bash
# Score and persist (works with --demo too, so no key needed to try it):
python score.py --demo --save sample_transcripts/standup.json
python score.py --save my_transcript.json            # live run, default sugapp.db
python score.py --save --db team.db my_transcript.json   # custom database path

# Read the accumulated history back:
python trends.py                 # default sugapp.db
python trends.py --db team.db
```

`trends.py` prints three views: the **Respect Index per run over time** (team rollup,
with the same k-anonymity suppression as the live report — runs with fewer than
`K_ANON` participants are never given a number), each person's lifetime
**personal-mirror** tally, and **behavior frequency** across all runs.

The database (`*.db`) is git-ignored — it holds scored content, so it never gets
committed. Schema lives in `store.py` (three tables: `runs`, `findings`, `goals`).

## Personal mirror (the "person sees their own data first" view)

`mirror.py` turns the stored history for **one person** into a self-contained HTML
dashboard — their own quotes, what's landing well vs. worth a second look, a trend
over time, and one self-set goal. It's the §5 personal mirror and the §6
reflect → choose loop. No web framework, no server: it writes a single `.html` file
(inline CSS, no JavaScript) you open in a browser.

```bash
python mirror.py --list                 # who's in the database
python mirror.py Dana                    # → mirror_Dana.html
python mirror.py Dana --set-goal "Ask one genuine question before pushing back"
python mirror.py Dana --db team.db --out dana.html
```

This view is **name-attached on purpose** — it's for the person only. The org never
sees it; team reporting stays anonymized (`trends.py`, `dashboard.py`). Generated
`mirror_*.html` files are git-ignored.

## Team dashboard (the "org sees aggregates only" view)

`dashboard.py` is the org-view counterpart to the personal mirror — the visual
version of `trends.py`. It writes a self-contained `team_dashboard.html`: the
headline **Respect Index**, its **trend over time**, and the **behavior mix** — and
by construction **never a name or a quote**. Runs with fewer than `K_ANON`
participants are suppressed (shown as "suppressed", excluded from the headline).

```bash
python dashboard.py                       # default sugapp.db → team_dashboard.html
python dashboard.py --db team.db --out team.html
```

It reads only run-level tallies and behavior counts (never per-person data), so no
individual can be identified from it. This is the §5 privacy boundary made literal:
the same database powers both the name-attached personal mirror and this fully
anonymized org view. Generated `team_dashboard.html` is git-ignored.

## What this is NOT

- Not production code (no retries/backoff hardening, no rate-limit queue; persistence
  is a local SQLite file, not a real datastore).
- Not the consent/opt-in layer — that's mandatory before any real data flows (design doc §5).
- Not a verdict engine — it surfaces evidence + a suggested rewrite for a human to reflect on.
