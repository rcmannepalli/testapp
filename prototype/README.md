# SugApp — Respect & Listening Scorer (Prototype)

A standalone prototype of SugApp's core differentiator: scoring everyday workplace
messages for **observable respect & listening behaviors** — never traits or emotions —
and rolling them up into a team **Respect Index**.

This is the hardest, most novel piece of the product (see [`../docs/PRODUCT.md`](../docs/PRODUCT.md)
§4 "The Respect & Listening model"). It deliberately has **no Slack connector, no UI, and no
database** — you feed it sample transcripts (JSON) and it prints per-message scores with
evidence + coaching rewrites, plus a team-level Respect Index. The goal is to prove the
model works before building any plumbing.

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
sees it; team reporting stays anonymized (`trends.py`). Generated `mirror_*.html`
files are git-ignored.

## What this is NOT

- Not production code (no retries/backoff hardening, no rate-limit queue; persistence
  is a local SQLite file, not a real datastore).
- Not the consent/opt-in layer — that's mandatory before any real data flows (design doc §5).
- Not a verdict engine — it surfaces evidence + a suggested rewrite for a human to reflect on.
