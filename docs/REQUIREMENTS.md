# SugApp — Requirements Specification

> Status: Draft v1.0 · Last updated: 2026-09-21 · Author: Suguna Mannepalli
> Proprietary & confidential. See /LICENSE and /IP.md.
> Companion to `docs/PRODUCT.md` (the vision/north-star). This doc is the
> testable requirements: what the system must do (functional) and how well
> (non-functional), each with acceptance criteria and a pointer to the module
> that satisfies it.

---

## 1. Purpose & scope

SugApp measures and coaches **respect and listening** in everyday workplace
communication by scoring chat transcripts against a rubric of *observable
behaviors*, then surfacing the results as a personal mirror (to the individual)
and anonymized aggregates (to the org).

**In scope (this release — Phase 1 MVP):** Slack text ingestion, consent-gated
scoring via Claude, SQLite persistence, analytics (trends, momentum, named
signals, behavior fingerprints), cost controls, per-run observability, and HTML
dashboards.
**Out of scope:** see §9.

**Requirement key:** `FR` = functional, `NFR` = non-functional. Each requirement
lists a status — **Done** (implemented), **Partial**, or **Planned**.

---

## 2. Stakeholders & user roles

| Role | Description | Primary interest |
|---|---|---|
| **Individual contributor (data subject)** | Anyone whose messages may be scored | Consent, seeing their *own* data first, coaching not surveillance |
| **People / HR / Culture leader (buyer)** | Buys and administers the product | Team-level Respect Index; legal defensibility |
| **Team manager** | Reads anonymized team trends | Is my team healthy; is it improving |
| **Workspace admin** | Connects Slack, manages rollout | Setup, consent coverage, data handling |
| **Operator / on-call** | Runs the scorer at scale | Cost, reliability, observability |

---

## 3. Assumptions & dependencies

- **A-1** Chat content is available via Slack (Web API or export) or a JSON transcript.
- **A-2** An Anthropic API key is available for live scoring (`ANTHROPIC_API_KEY`).
- **A-3** Python 3.10+ runtime; SQLite available (stdlib).
- **A-4** Identity for real data comes from an authenticated source (Slack user id).
- **D-1** External dependency: Anthropic Claude API (the only runtime dependency for scoring).
- **D-2** Legal posture assumes EU AI Act constraints on workplace inference (see §6.1).

---

## 4. Functional requirements

### 4.1 Ingestion & connectors
| ID | Requirement | Acceptance criteria | Status | Module |
|---|---|---|---|---|
| FR-ING-1 | Ingest a Slack channel via the Slack Web API into the canonical transcript format | Given a channel + token, produce `{channel, messages:[{author, author_id, text}]}` with verified ids; a mock mode runs with no live token | Done | `connect_slack.py` |
| FR-ING-2 | Convert a Slack export into a transcript | Given an export directory, emit a valid transcript on stdout | Done | `ingest_slack.py` |
| FR-ING-3 | Accept a hand-written transcript (file or stdin) | `score.py <file>` and `… | score.py -` both work | Done | `score.py` |
| FR-ING-4 | Interactive REPL for ad-hoc scoring | Typed messages are scored live | Done | `chat.py` |
| FR-ING-5 | Canonical transcript format is source-agnostic | All connectors emit the identical schema; the scorer needs no source-specific logic | Done | all connectors |

### 4.2 Consent & identity
| ID | Requirement | Acceptance criteria | Status | Module |
|---|---|---|---|---|
| FR-CON-1 | Maintain an opt-in consent registry keyed by `author_id` | Add/remove/list opt-ins; persisted | Done | `consent.py`, `store.py` |
| FR-CON-2 | Browser-based opt-in/opt-out with authenticated identity (Slack OIDC SSO) | User signs in with Slack and sets their own consent | Done | `consent_server.py` |
| FR-CON-3 | Consent gate drops non-opted-in authors **before** any API call | With `--require-consent`, no non-consented message text is sent to the model or stored | Done | `score.apply_consent` |
| FR-CON-4 | Every message carries a stable `author_id` and a `verified` flag | Authenticated ids marked verified; hand-written ids fall back to display name marked unverified | Done | `score.normalize_identities` |
| FR-CON-5 | Identity is authoritative from the transcript, never the model | Findings are stamped with transcript-derived identity after scoring | Done | `score.attach_identity` |

### 4.3 Scoring engine
| ID | Requirement | Acceptance criteria | Status | Module |
|---|---|---|---|---|
| FR-SCORE-1 | Score each message against a fixed rubric of observable behaviors | Output is a list of findings, one enum behavior each, from the 9 defined behaviors | Done | `rubric.py`, `score.py` |
| FR-SCORE-2 | Every finding must quote the exact evidence text | `evidence` is non-empty and present verbatim in the source message | Done | `rubric.FINDINGS_SCHEMA` |
| FR-SCORE-3 | Each disrespectful finding includes a coaching rewrite | `coaching_rewrite` populated for disrespectful polarity | Done | `rubric`, model contract |
| FR-SCORE-4 | Enforce a machine-readable output contract | Response validated against a JSON schema; behavior is an enum (no invented categories) | Done | `output_config.format` |
| FR-SCORE-5 | Compute a team Respect Index (0–100) from findings | Deterministic formula; 75 neutral when no findings | Done | `score.respect_index` |
| FR-SCORE-6 | Offline demo mode with no API spend | `--demo` scores from a bundled fixture; whole pipeline runs with no key | Done | `score.py --demo` |
| FR-SCORE-7 | Allow model tier selection | `--model` overrides the default; runs on a cheaper tier for bulk | Done | `score.py`, `cost.py` |

### 4.4 Cost controls
| ID | Requirement | Acceptance criteria | Status | Module |
|---|---|---|---|---|
| FR-COST-1 | Report the cost of every live run | A cost line prints after each live scoring run | Done | `score.py`, `cost.py` |
| FR-COST-2 | Project cost before spending (dry run) | `--estimate` prints worst-case cost from a free token count and spends nothing | Done | `cost.py` |
| FR-COST-3 | Abort if projected cost exceeds a cap | `--max-cost N` exits before the paid call when projection > N | Done | `score.py` |
| FR-COST-4 | Reduce repeat cost via prompt caching | The static rubric is sent as a cached system block | Done | `score.build_request` |

### 4.5 Persistence
| ID | Requirement | Acceptance criteria | Status | Module |
|---|---|---|---|---|
| FR-DATA-1 | Persist runs and findings for trend analysis | `--save` writes a run + its findings to SQLite | Done | `store.save_run` |
| FR-DATA-2 | Key all per-person data on stable `author_id` | Display-name changes do not break history | Done | `store.py` |
| FR-DATA-3 | Store consent, identities, and self-set goals | Dedicated tables; read/write APIs | Done | `store.py` |
| FR-DATA-4 | Read side exposes trend queries as functions | Analytics call functions, never write SQL | Done | `store.py` |

### 4.6 Analytics
| ID | Requirement | Acceptance criteria | Status | Module |
|---|---|---|---|---|
| FR-AN-1 | Accumulated totals: index over time, per-person tallies, behavior frequency | `trends.py` prints all three | Done | `trends.py` |
| FR-AN-2 | Momentum: respect trend by period with deltas | Per-channel and per-person, day/week/month buckets, period-over-period delta | Done | `momentum.py` |
| FR-AN-3 | Named signals: PRODUCT.md §4 metrics as balances | disagree-with-dignity, enabling-vs-gatekeeping, listening-vs-dismissing, credit presence; org-wide + per-person | Done | `signals.py`, `rubric.SIGNALS` |
| FR-AN-4 | Behavior fingerprint: per-person behavior distribution + quotes | Behaviors sorted by frequency, each with a representative quote | Done | `fingerprint.py` |

### 4.7 Observability
| ID | Requirement | Acceptance criteria | Status | Module |
|---|---|---|---|---|
| FR-OBS-1 | Capture a per-run health record | latency, tokens, cost, `stop_reason`, `schema_ok`, findings count | Done (module) | `metrics.py` |
| FR-OBS-2 | Write metrics to two sinks | SQLite `run_metrics` table + append-only JSONL | Done | `metrics.record_run` |
| FR-OBS-3 | Logging must never break scoring | JSONL write is best-effort; failure is swallowed | Done | `metrics.py` |
| FR-OBS-4 | Auto-emit metrics on every live run | `score.py` calls `record_run` for each run | Planned | `score.py` |
| FR-OBS-5 | Roll up metrics into an operational view | Cost trend, cache-hit %, latency percentiles, refusal/error rate | Planned | `obs.py` |

### 4.8 Presentation
| ID | Requirement | Acceptance criteria | Status | Module |
|---|---|---|---|---|
| FR-UI-1 | Personal mirror: one person's own dashboard | Standalone HTML; their quotes, trend, goal | Done | `mirror.py` |
| FR-UI-2 | Team dashboard: anonymized org view | k-anonymized aggregates only; no named individuals | Done | `dashboard.py`, `ui/` |

---

## 5. Behavior model (reference)

The rubric defines **9 observable behaviors** (the scoring vocabulary):
respectful — `acknowledgment`, `question_asking`, `invites_others`,
`disagree_with_dignity`, `credit_attribution`, `enabling`; disrespectful —
`dismissiveness`, `personal_attack`, `gatekeeping`. Named **signals** are
balances built from these (see `rubric.SIGNALS`). Changing the vocabulary is a
change to `rubric.py` only.

---

## 6. Non-functional requirements

### 6.1 Privacy & compliance *(non-negotiable — PRODUCT.md §5)*
| ID | Requirement | Acceptance criteria | Status |
|---|---|---|---|
| NFR-PRIV-1 | Opt-in with a real, penalty-free opt-out | No scoring/storage of non-consented people | Done |
| NFR-PRIV-2 | The person sees their own data first and most | Personal mirror is name-attached and individual-facing | Done |
| NFR-PRIV-3 | Org sees aggregates only — k-anonymity in code | No rollup for < 5 distinct participants (`K_ANON=5`), enforced in aggregation | Done |
| NFR-PRIV-4 | Always show evidence + rationale | Every finding carries the exact quote and a rationale | Done |
| NFR-PRIV-5 | Behaviors only — no trait/emotion/biometric inference | Rubric hard-rules forbid it; behavior enum is closed | Done |
| NFR-PRIV-6 | Data minimization | Store the signal; short-retain or discard raw content | Partial |
| NFR-PRIV-7 | No disciplinary pipe | No per-individual score is exposed to management | Done (by design) |
| NFR-PRIV-8 | Regional configurability (works-council mode) | Features disable-able per jurisdiction | Planned |

### 6.2 Security
| ID | Requirement | Acceptance criteria | Status |
|---|---|---|---|
| NFR-SEC-1 | Authenticated identity for real data | Slack OIDC SSO for consent; verified `author_id` | Done |
| NFR-SEC-2 | Secrets via environment, never in code | API key/token read from env | Done |
| NFR-SEC-3 | Non-consented content never leaves the process | Consent filter precedes egress | Done |

### 6.3 Cost & efficiency
| ID | Requirement | Acceptance criteria | Status |
|---|---|---|---|
| NFR-COST-1 | No silent spend | Every live run reports cost | Done |
| NFR-COST-2 | Pre-flight cost cap available | `--max-cost` gate | Done |
| NFR-COST-3 | Repeated-run cost reduced by caching | Cached rubric; cache-hit observable | Done |

### 6.4 Reliability & observability
| ID | Requirement | Acceptance criteria | Status |
|---|---|---|---|
| NFR-REL-1 | Refusals and malformed output are handled, not crashes | `stop_reason=="refusal"` and schema failure captured, not fatal | Planned |
| NFR-REL-2 | Per-inference telemetry emitted | One structured record per run (see FR-OBS) | Partial |
| NFR-REL-3 | Deterministic, testable aggregation | Respect Index / signals / momentum computed by pure functions | Done |

### 6.5 Performance
| ID | Requirement | Acceptance criteria | Status |
|---|---|---|---|
| NFR-PERF-1 | Analytics run offline against SQLite | No API needed for any read/dashboard | Done |
| NFR-PERF-2 | Latency observable per run | `latency_ms` captured | Done (module) |

### 6.6 Maintainability & portability
| ID | Requirement | Acceptance criteria | Status |
|---|---|---|---|
| NFR-MAINT-1 | One capability per module, shared store | Each analytic is an independent CLI over `store.py` | Done |
| NFR-MAINT-2 | Model is a swappable, isolated dependency | Only `score_transcript` touches the API; typed contract at the boundary | Done |
| NFR-MAINT-3 | Dependency-light | Stdlib-only data layer; Anthropic SDK the sole runtime dep | Done |

### 6.7 Legal / IP
| ID | Requirement | Acceptance criteria | Status |
|---|---|---|---|
| NFR-IP-1 | Proprietary licensing + provenance | LICENSE, IP.md, copyright headers present | Done |

---

## 7. Data requirements (model)

```
runs(id, created_at, channel, source, participant_count)
findings(id, run_id→runs, message_index, author_id, author, behavior, polarity,
         evidence, coaching_rewrite, rationale)
identities(author_id, display_name, verified)
consent(author_id, opted_in, …)
goals(author_id, goal, set_at)
run_metrics(id, ts, run_id, channel, model, latency_ms, tokens…, cost_usd,
            stop_reason, schema_ok, findings_count)
```
Retention: raw message text is stored on findings as `evidence` today
(NFR-PRIV-6 targets minimizing this). The database file is git-ignored.

---

## 8. Constraints

- **C-1** Scoring requires network access to the Anthropic API (offline only in `--demo`).
- **C-2** k-anonymity threshold is fixed at 5; period-level suppression uses the
  max per-run participant count as a proxy (the full participant set per period
  is not stored).
- **C-3** Prototype persistence is single-file SQLite (not concurrent-write scale).

---

## 9. Out of scope *(explicitly, per PRODUCT.md §9)*

- Covert or non-consensual monitoring of anyone.
- Trait, personality, or emotion inference about individuals.
- Per-individual scoring exposed to management, ranking, or HR/disciplinary use.
- Recording or analyzing people who have not consented.

---

## 10. Success metrics (how "done well" is measured)

| Axis | Metric |
|---|---|
| Quality | precision / recall / F1 per behavior, Cohen's κ vs human labels (needs a gold set — Planned) |
| Reliability | schema-valid rate, refusal rate, error rate, latency p95 |
| Cost | cost per run, cache-hit rate, tokens per run |
| Consistency | reproducibility across repeated runs; behavior-distribution drift (PSI) |
| Product impact | opt-in rate; personal-mirror engagement; **respect-trend improvement over time** (the North Star) |
| Trust | consent coverage %; k-anonymity invariant holds |

---

## 11. Roadmap *(PRODUCT.md §8)*

- **Phase 1 — MVP (current):** Slack connector, scorer, personal mirror, anonymized team view. *Largely Done.*
- **Phase 2 — Integrated:** add Teams + Outlook (Graph API) into one cross-channel profile; opt-in nudges at point of action. *Planned.*
- **Phase 3 — Meetings:** consent-gated meeting transcripts for airtime/interruption signals. *Planned.*

---

## 12. Requirement → module traceability (summary)

| Area | Requirements | Implemented in |
|---|---|---|
| Ingestion | FR-ING-1..5 | `connect_slack.py`, `ingest_slack.py`, `chat.py`, `score.py` |
| Consent/identity | FR-CON-1..5, NFR-SEC-* | `consent.py`, `consent_server.py`, `score.py` |
| Scoring | FR-SCORE-1..7 | `rubric.py`, `score.py`, `cost.py` |
| Cost | FR-COST-1..4 | `cost.py`, `score.py` |
| Persistence | FR-DATA-1..4 | `store.py` |
| Analytics | FR-AN-1..4 | `trends.py`, `momentum.py`, `signals.py`, `fingerprint.py` |
| Observability | FR-OBS-1..5 | `metrics.py` (+ `score.py`, `obs.py` planned) |
| Presentation | FR-UI-1..2 | `mirror.py`, `dashboard.py`, `ui/` |
