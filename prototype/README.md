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

## Run

```bash
python score.py sample_transcripts/standup.json
```

or pipe your own transcript on stdin:

```bash
cat my_transcript.json | python score.py -
```

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

## What this is NOT

- Not production code (no retries/backoff hardening, no rate-limit queue, no persistence).
- Not the consent/opt-in layer — that's mandatory before any real data flows (design doc §5).
- Not a verdict engine — it surfaces evidence + a suggested rewrite for a human to reflect on.
