# SugApp — Respect & Listening Platform — Product Design Doc

> Status: Draft v0.1 — strategy north star. Not yet implemented.
> Product name: **SugApp**
> Last updated: 2026-06-18

## 1. One-sentence thesis

A communication-coaching platform that builds a culture of **respect and listening**
across the *entire* organization — not just leaders, not just sales — by measuring
and coaching the everyday behaviors that make people feel **heard** or feel **small**.

The three words we own: **respect, listening, dignity** — and especially
**"holding respect even when you disagree."**

## 2. The problem

Enterprises lack a mirror for how people actually treat each other in everyday
communication. Specifically:

- People drift **bureaucratic** and dismissive the longer they're at a company —
  gatekeeping ("not my job / not the process"), not listening, making others feel small.
- This calcification happens to **individual contributors**, not just leaders, so
  leader-only coaching tools miss most of the org.
- There are **no controls and no reflection** — people don't see how they land, so
  nothing changes.

## 3. Positioning vs. the market

This is a validated, legal, sellable category — but the incumbents aim at the wrong target.

| Incumbent | Their limit | Our edge |
|---|---|---|
| **Gong** | Sales calls only | Every employee, every channel |
| **Microsoft Viva Insights** | M365-locked, generic "wellbeing," aggregate-only | Cross-platform + a specific *values* model + personal mirror |
| **Cultivate** (acq. Perceptyx) | Leaders only | The whole org — including the IC who's drifted bureaucratic |
| **All of them** | Single-channel silos; vague metrics | **Integrated** profile + **named, measurable respect behaviors** |

### Our three stacked differentiators (the moat)

1. **Everyone** — coaches the whole org, including tenured ICs who calcify, not just leaders/sales.
2. **Integrated** — one behavior profile across Slack + Teams + Outlook + meetings, not four siloed tools.
3. **A values model, not a metrics dump** — measures *respect and listening*, which is what people actually feel.

The category of **"respectful disagreement and dignity at work"** is wide open.

## 4. The Respect & Listening model (our IP)

The core design rule that keeps the product **both legal and effective**: measure
**observable behaviors**, never inferred **traits** or **emotions**. Behaviors are
fair, observable, coachable, and not prohibited; trait/emotion inference is biased
and banned in the workplace under the EU AI Act.

### Listening signals
- **Acknowledgment rate** — do you reference/build on what others said before responding?
- **Question-asking ratio** — curiosity vs. pure assertion.
- **Airtime equity** — do you let others speak, or dominate?
- **Interruption / talk-over rate** (meetings).

### Respect-in-disagreement signals (signature)
- **Disagree-with-dignity** — when pushing back, attack the *idea* not the *person*
  ("That won't work because X" vs. "That's a naive take").
- **Dismissiveness / minimizing language** ("obviously," "as I already said," "that's not how it works").
- **Credit & attribution** — acknowledging whose idea it was. (The fair, legal version of
  the "idea-stealing" concern: measure *acknowledgment*, never accuse.)

### Bureaucratic-drift signals (the tenure problem)
- **Gatekeeping vs. enabling language** ("not my job / not the process" vs. "here's how we can").
- **Openness trend over time** — a personal trend so someone can catch their own calcification early.

### Output contract
Every signal returns: **score + the exact quote (evidence) + a plain-English coaching
rewrite** ("here's a more respectful way to say this"). No black-box verdicts.

### The headline metric
A team-level **Respect Index** — *"are people heard and treated with dignity here?"* —
becomes the single number an enterprise buys the product for. Not "highest sentiment" —
**highest respect.**

## 5. Privacy & legal architecture (non-negotiable, build it in from line 1)

These safeguards are what make the product pass procurement *and* what make it actually
change behavior (surveillance makes people hide; agency makes people change).

1. **Opt-in, with a real, penalty-free opt-out** — this is what makes consent legally valid.
2. **The person sees their own data first and most** — personal mirror, their quotes.
3. **The org sees aggregates only** — k-anonymity threshold enforced *in code* (never report
   on groups smaller than ~5; never expose named individuals to management).
4. **Always show evidence + rationale** — trust and legal defensibility.
5. **Behaviors, not traits/emotions/biometrics** — EU AI Act compliance.
6. **Data minimization** — store the signal (e.g. "question-asking ratio"), short-retain or
   discard raw content.
7. **No disciplinary pipe** — architecturally and contractually separate from HR/comp/discipline.
8. **Regional config** — works-council mode; disable individual features where law requires.

Benchmark: Microsoft Viva ships differential privacy. We match that bar, not bolt it on later.

## 6. Behavior-change loop (how culture actually changes)

**reflect → choose → nudge → progress → repeat**, pulled by the person, not pushed onto them:

- **Awareness** — just showing people their patterns (with quotes) moves many on its own.
- **Specific + in-context** — "Tuesday's review: you spoke 70%, asked 0 questions."
- **Self-set goals** — the person picks one thing to improve.
- **Tiny opt-in nudges** — "this reads as blunt — want a softer version?" at the point of action.
- **Visible progress** — "interruptions down 30% this month."
- **Aggregate norms** — "the healthiest teams ask 3x more questions."

## 7. Open decisions (defaults in **bold**, change anytime)

- **Primary buyer:** **HR / People / Culture leaders** (alt: C-suite; or bottoms-up team managers).
- **First channel:** **Slack** (text-only, simplest, lowest legal risk).
- **Platform:** prototype on the current repo; note: it is on **Ruby 2.6 (EOL)** — upgrade
  to current Ruby/Rails before production.

## 8. Phased plan

### Phase 1 — MVP (prove the model)
- **Slack connector** (opt-in per user) → pull messages from consented channels.
- **Behavior scorer** using Claude with the Respect & Listening rubric → score + evidence + rewrite.
- **Personal mirror dashboard** — your trends, your quotes, pick one goal.
- **Aggregate team view** — anonymized, k-anonymity enforced; the Respect Index.

### Phase 2 — Integrated
- Add **Microsoft Teams + Outlook** (Graph API) → unify into one cross-channel respect profile.
- Opt-in nudges at point of action.

### Phase 3 — Meetings
- Meeting transcripts (consent-gated recording) for airtime/interruption signals.
- Highest signal, highest legal complexity — recording-consent flows required per jurisdiction.

## 9. Scope guardrails (explicitly out of scope)

To protect the product's legality and credibility, the following are **out of scope**:

- ❌ Covert or non-consensual monitoring of anyone.
- ❌ Trait, personality, or emotion inference about individuals.
- ❌ Per-individual scoring exposed to management, ranking, or any HR/disciplinary use.
- ❌ Recording or analyzing people who have not consented (the consent boundary is absolute).

### Possible future line (consumer) — only in the legal form
A **personal communication coach** that works on *the user's own outgoing words only*
("re-read this before you send — here's a calmer version"), or **consensual two-party**
conflict coaching where *everyone* opts in. Explicitly **excludes** covert monitoring of
family members, spouses, children, or any third party — that scope is illegal (wiretapping),
bannable from app stores (stalkerware), and an abuse vector. Not pursued without a dedicated
legal and safety review.
