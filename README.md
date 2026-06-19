# SugApp

**A respect & listening culture-coaching platform for the enterprise.**

SugApp helps organizations build a culture of **respect and listening** across the
*entire* workforce — not just leaders, not just sales — by measuring and coaching the
everyday communication behaviors that make people feel **heard** or feel **small**.

## What it does

- Coaches **everyone**, including tenured ICs who drift bureaucratic and dismissive over time.
- Provides an **integrated** view across communication channels (Slack → Teams + Outlook → meetings).
- Measures **observable respect behaviors** — not traits or emotions — each with the evidence
  quote and a coaching rewrite, rolling up to a team-level **Respect Index**.

Built privacy-first: opt-in, personal-mirror-first, aggregate-only for the org, and designed
to comply with workplace privacy law and the EU AI Act.

## Status

Early stage. The product strategy, scoring model, privacy/legal architecture, and phased
plan live in the design doc:

📄 **[docs/PRODUCT.md](docs/PRODUCT.md)**

## Roadmap (high level)

1. **Phase 1 — MVP:** Slack connector → Claude-based Respect & Listening scorer → personal
   mirror + anonymized team Respect Index.
2. **Phase 2 — Integrated:** add Microsoft Teams + Outlook (Graph API) into one cross-channel profile.
3. **Phase 3 — Meetings:** consent-gated meeting transcripts for airtime/interruption signals.

See [docs/PRODUCT.md](docs/PRODUCT.md) for the full thesis, market positioning, differentiation,
behavior model, and guardrails.
