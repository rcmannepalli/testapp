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
- **Consent gate** — opt-in registry enforced in code; only opted-in people are
  scored or stored (`consent.py`, `score.py --require-consent`).

Still deliberately **not** here: a live Slack/Teams API connector and a web server —
those are production Phase-1 work. The consent *mechanism* now exists (opt-in gate +
penalty-free, data-purging opt-out); the production version still needs an
authenticated consent UX and the regional config from design doc §5.

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

### Cost controls (`cost.py`)

Live scoring is a paid API call, so the scorer never spends silently — every live run
prints what it cost. Three knobs keep spend predictable:

```bash
# Project the worst-case cost from a free token count, spend nothing:
python score.py --estimate my_transcript.json

# Abort before paying if the projection exceeds a cap:
python score.py --max-cost 0.50 my_transcript.json

# Run a cheaper tier for bulk scoring (default is claude-opus-4-8):
python score.py --model claude-haiku-4-5 my_transcript.json
```

The static rubric is sent as a cached system prompt, so repeated runs pay a reduced
rate on it. Prices live in one place (`cost.py`) — update them from the pricing page.

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
if it's not alongside). `sample_slack_export/` is a tiny example you can run as-is.

### Pulling live from Slack (the API connector)

`connect_slack.py` reads a channel from the live **Slack Web API** and emits the same
transcript format — stdlib `urllib` only, no SDK. Output is byte-identical to the
export path (it reuses the same name/markup logic).

**You don't need a paid plan or the full OAuth web flow.** For your own workspace,
Slack's "Install to Workspace" button *is* the OAuth step — it hands you a bot token:

1. Create a free Slack workspace.
2. **api.slack.com/apps** → Create New App → From scratch.
3. OAuth & Permissions → Bot Token Scopes: `channels:history`, `channels:read`,
   `users:read` (+ `groups:*` for private channels).
4. **Install to Workspace** → copy the bot token (`xoxb-…`).
5. Invite the app to the channel: `/invite @your-app`.
6. `export SLACK_TOKEN=xoxb-...`

```bash
# Try it with NO workspace at all — reads bundled API-response fixtures:
python connect_slack.py --channel eng-standup --mock sample_slack_api

# Live, once you have a token:
export SLACK_TOKEN=xoxb-...
python connect_slack.py --channel eng-standup
python connect_slack.py --channel eng-standup | python score.py --require-consent -
```

The full **3-legged OAuth** (client_id/secret + a public redirect URL) is only needed
to let *other* organizations install your app — defer it until you go multi-tenant.
**Teams/Outlook** is a separate connector (Microsoft Graph + a free M365 dev tenant);
that's Phase 2 in [`../docs/PRODUCT.md`](../docs/PRODUCT.md) §8.

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

### Momentum (is it getting better?)

`trends.py` shows the accumulated totals; `momentum.py` shows the **direction** —
it buckets the history into day/week/month periods and reports each period's Respect
Index with the change from the period before it (the "up 23 points this month"
signal the behavior-change loop is built on, PRODUCT.md §6):

```bash
python momentum.py                       # month buckets
python momentum.py --period week
python momentum.py --channel '#eng-standup'
```

Same privacy split as everything else: **channel momentum** is the org view
(k-anonymity enforced — a channel-period below `K_ANON` is suppressed), and
**personal momentum** is the name-attached personal mirror. The period rollups are
`store.channel_momentum` / `store.person_momentum`; the ratio + delta math is in
`momentum.py`, so the SQL stays plain aggregation.

### Named signals (`signals.py`)

Raw behavior counts become the plain-English metrics PRODUCT.md §4 describes.
Each **signal** is a balance between a respectful form and its disrespectful
counterpart, so it answers a question as a percentage — "when people disagree,
how often is it the idea that's challenged, not the person?"

```bash
python signals.py                 # org-wide + every person
python signals.py Dana            # one person's signals
```

The signal model (which behaviors compose each signal) lives in `rubric.py`
(`SIGNALS`), next to the behaviors it's built from. Org-wide is the aggregate
(k-anonymity enforced); per-person is the personal mirror. Signals without a
disrespectful counterpart (e.g. credit & attribution) are reported as a presence
count, never as an accusation.

### Behavior fingerprints (`fingerprint.py`)

The personal mirror's totals say "4 respectful, 2 disrespectful"; a fingerprint
says *which* behaviors — the distribution across the named behaviors, sorted by
frequency, each with a representative quote from that person's own messages.

```bash
python fingerprint.py             # every person
python fingerprint.py Priya       # one person
```

Evidence, not a verdict — always the exact quote (PRODUCT.md §4), name-attached
because it's the personal-mirror surface the org never sees (PRODUCT.md §5).

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

## Consent (opt-in, with a penalty-free opt-out)

PRODUCT.md §5 makes consent non-negotiable: scoring is **opt-in**, and only people
who have opted in may be scored or stored. `consent.py` manages the registry;
`score.py --require-consent` enforces it — non-consented people's messages are
dropped *before* anything is sent to the model, so their text is never scored,
stored, or even transmitted.

```bash
python consent.py --import eng.json        # learn who's in a channel (id ↔ name)
python consent.py --in Dana Sam Priya      # opt people in (by name or id)
python consent.py --list                   # everyone's status (+ audit)
python consent.py --status Marcus          # one person
python consent.py --out Dana               # withdraw: purges Dana's stored data too

# Only opted-in authors are scored/stored:
python score.py --demo --save --require-consent sample_transcripts/standup.json
```

Opting out is **penalty-free and retroactive**: it records the withdrawal and deletes
everything already stored about that person (findings + goal). Absence of a decision
is never treated as consent. Consent lives in the same SQLite database so the gate
and the data are colocated.

### Authenticated identity (why consent is reliable)

Consent, scores, and goals are keyed by a stable **`author_id`** — the Slack user id
(`U02SAM`) the connector carries through from the authenticated API — **not** a
display name. A name can be changed or shared; an id can't. This is what makes the
guarantees hold:

- **No impersonation** — identity comes from the authenticated transcript, never
  from the model or a typed name.
- **Reliable opt-out** — withdrawal purges by id, so two people who happen to share a
  display name are never collapsed (the code enforces this).
- **Typo-safe** — opting someone in by a name that matches nobody is refused with the
  known roster, instead of silently protecting the wrong id.

Hand-written transcripts with no `author_id` still run, but their identities are
marked **unverified** (id falls back to the name) — the report says so. Run through
`connect_slack.py` for verified ids. `consent.py --import <transcript>` registers the
id↔name map so you can then opt people in by name.

### Consent UI (the browser front-end, with Sign in with Slack)

`consent_server.py` is a tiny web app (stdlib `http.server` + `urllib`, no framework)
— the browser companion to `consent.py`. A person **signs in with Slack**, sees their
own status and **exactly what is stored about them** (informed consent), and can opt
in or opt out; opt-out deletes their stored data. It writes through the same id-keyed
store, so the CLI and UI are one source of truth.

**Authentication is real SSO** — "Sign in with Slack" (OpenID Connect on OAuth 2.0):
`/login` → Slack → `/oauth/callback` exchanges the code server-to-server and calls
Slack's userInfo endpoint (all JSON over TLS — no JWT/crypto dependency). The
**verified Slack user id it returns is the `author_id`** the registry keys on, so a
person can only ever see and act on their own record. Opt-in/opt-out act on the
**session** identity, ignoring anything the page submits — tamper-proof by design.

```bash
# Reuse your Slack app; add user scopes openid,email,profile + register the redirect.
export SLACK_CLIENT_ID=...           # api.slack.com/apps → Basic Information
export SLACK_CLIENT_SECRET=...
python consent_server.py --db sugapp.db          # → http://127.0.0.1:8000

# Offline / no Slack app — roster picker stands in for sign-in:
python consent.py --import eng.json
python consent_server.py --dev --db sugapp.db
```

Full 3-legged OAuth needs a registered redirect URL (use ngrok if not on
`localhost`). Without credentials the server auto-falls back to `--dev` roster mode.

## What this is NOT

- Not production code (no retries/backoff hardening, no rate-limit queue; persistence
  is a local SQLite file, not a real datastore).
- The consent *gate*, **authenticated identity** (id-keyed via Slack user ids), a
  consent UI, and **end-user SSO** (Sign in with Slack / OIDC) all exist — but not yet
  the rest of the §5 system: no enterprise IdP SSO (SAML/OIDC via Okta/Entra), no
  regional/works-council config, no enforced data-retention/minimization windows, and
  sessions are in-memory (a real deploy needs a signed-cookie / shared session store).
- Not a verdict engine — it surfaces evidence + a suggested rewrite for a human to reflect on.
