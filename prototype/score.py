#!/usr/bin/env python3
# SugApp — proprietary & confidential. © 2026 <Your Legal Name>. All rights reserved.
# Trade-secret methodology; not for distribution. See /LICENSE and /IP.md.
"""SugApp Respect & Listening scorer — standalone prototype.

Usage:
    python score.py sample_transcripts/standup.json
    cat transcript.json | python score.py -
    python score.py --demo sample_transcripts/standup.json   # offline, no key
    python score.py --save sample_transcripts/standup.json    # persist to SQLite
    python score.py --save --db mine.db transcript.json       # custom db path
    python score.py --save --require-consent transcript.json  # only opted-in people
    python score.py --estimate transcript.json                # project cost, no spend
    python score.py --max-cost 0.50 transcript.json           # abort if too pricey
    python score.py --model claude-haiku-4-5 transcript.json  # cheaper tier

Reads a transcript JSON ({"channel": str, "messages": [{"author", "text"}, ...]}),
scores it against the Respect & Listening rubric using Claude, and prints per-message
findings (with evidence + coaching rewrites) plus a k-anonymized team Respect Index.

With --save, the run and its findings are written to a SQLite database (default
sugapp.db next to this script; override with --db) so trends accumulate over time.
Read them back with trends.py.

With --require-consent, only authors who have opted in (see consent.py) are scored
or stored — non-consented people's messages are dropped before anything is sent to
the model. This is the PRODUCT.md §5 opt-in gate; turn it on for any real data.

Cost controls (see cost.py) — scoring is a paid API call, so the scorer never
spends silently. Every live run prints what it cost. --estimate projects the
worst-case cost from a free token count and spends nothing; --max-cost DOLLARS
aborts before paying if that projection exceeds the cap; --model runs a cheaper
tier (e.g. claude-haiku-4-5) for bulk scoring. The static rubric is sent as a
cached system prompt so repeated runs pay a reduced rate on it.
"""
import json
import os
import sys
from collections import defaultdict

from rubric import DISRESPECTFUL, FINDINGS_SCHEMA, RESPECTFUL, system_prompt

MODEL = "claude-opus-4-8"
MAX_TOKENS = 16000  # output ceiling per scoring call (also the cost-estimate ceiling)
K_ANON = 5  # never show a team rollup for fewer than this many distinct participants


def load_transcript(path: str) -> dict:
    raw = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    data = json.loads(raw)
    if "messages" not in data:
        raise ValueError("transcript must have a 'messages' list")
    normalize_identities(data)
    return data


def normalize_identities(transcript: dict) -> None:
    """Ensure every message has both a display `author` and a stable `author_id`.

    Authenticated sources (the Slack connector) supply `author_id`; a
    hand-written transcript without one falls back to author_id == the display
    name — an "unverified" identity that still runs, but can be spoofed.
    """
    for m in transcript["messages"]:
        name = m.get("author", "unknown")
        m["author"] = name
        m["verified"] = "author_id" in m and m["author_id"] not in (None, "")
        m["author_id"] = m["author_id"] if m.get("verified") else name


def identity_map(transcript: dict) -> dict:
    """author_id → display name for every participant in the transcript."""
    return {m["author_id"]: m["author"] for m in transcript["messages"]}


def attach_identity(transcript: dict, findings: list[dict]) -> None:
    """Stamp each finding with the authoritative author_id + name of its message.

    Identity comes from the (authenticated) transcript, never from the model —
    the scorer decides *what* a message shows, not *who* said it.
    """
    messages = transcript["messages"]
    for f in findings:
        m = messages[f["message_index"]]
        f["author"] = m["author"]
        f["author_id"] = m["author_id"]


def build_request(transcript: dict) -> tuple[list, list]:
    """Build the (system, messages) pair for scoring a transcript.

    Shared by the real call and the cost estimator so both price the exact same
    request. The rubric is the same on every run, so it's sent as a cached
    system block — repeated runs pay the reduced cache-read rate on it.
    """
    numbered = [
        {"message_index": i, "author": m.get("author", "unknown"), "text": m["text"]}
        for i, m in enumerate(transcript["messages"])
    ]
    user_content = (
        f"Channel: {transcript.get('channel', 'unknown')}\n\n"
        "Score each message below. Report only genuine findings.\n\n"
        f"{json.dumps(numbered, indent=2)}"
    )
    system = [
        {
            "type": "text",
            "text": system_prompt(),
            "cache_control": {"type": "ephemeral"},
        }
    ]
    messages = [{"role": "user", "content": user_content}]
    return system, messages


def score_transcript(client, transcript: dict, model: str = MODEL):
    """Score a transcript. Returns (findings, usage) — usage drives cost reporting."""
    system, messages = build_request(transcript)
    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=system,
        messages=messages,
        output_config={"format": {"type": "json_schema", "schema": FINDINGS_SCHEMA}},
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["findings"], response.usage


def respect_index(findings: list[dict]) -> int:
    """Team Respect Index, 0-100. Starts at a neutral 75 and moves with the balance
    of respectful vs. disrespectful behaviors. A transparent placeholder formula —
    the real product would calibrate this against outcome data."""
    pos = sum(1 for f in findings if f["polarity"] == "respectful")
    neg = sum(1 for f in findings if f["polarity"] == "disrespectful")
    total = pos + neg
    if total == 0:
        return 75
    score = 50 + 50 * (pos - neg) / total
    return round(max(0, min(100, score)))


def render(transcript: dict, findings: list[dict]) -> None:
    messages = transcript["messages"]
    by_msg: dict[int, list[dict]] = defaultdict(list)
    for f in findings:
        by_msg[f["message_index"]].append(f)

    print(f"\n=== Respect & Listening report — {transcript.get('channel', '?')} ===\n")
    mark = {"respectful": "✅", "disrespectful": "⚠️ "}
    for i, m in enumerate(messages):
        flags = by_msg.get(i, [])
        bullet = "•" if not flags else ("⚠️" if any(f["polarity"] == "disrespectful" for f in flags) else "✅")
        print(f"{bullet} [{i}] {m.get('author', '?')}: {m['text']}")
        for f in flags:
            print(f"      {mark[f['polarity']]}{f['behavior']} — {f['rationale']}")
            print(f"         evidence: “{f['evidence']}”")
            if f["coaching_rewrite"].strip():
                print(f"         rewrite:  “{f['coaching_rewrite']}”")
        print()

    # Per-person summary (this is the "personal mirror" data — name-attached).
    print("--- Per-person (personal-mirror view) ---")
    people: dict[str, dict[str, int]] = defaultdict(lambda: {"respectful": 0, "disrespectful": 0})
    for f in findings:
        people[f["author"]][f["polarity"]] += 1
    for person, c in sorted(people.items()):
        print(f"  {person}: {c['respectful']} respectful, {c['disrespectful']} disrespectful")

    # Team rollup (the "org sees aggregates only" view) — k-anonymity enforced.
    # Count distinct identities (author_id), so two people sharing a display name
    # can't be collapsed into one and slip under the k-anonymity threshold.
    participants = {m["author_id"] for m in messages}
    print("\n--- Team rollup (org view) ---")
    if any(not m.get("verified", False) for m in messages):
        print("  (note: some identities are unverified — this transcript had no "
              "authenticated author_id; run via connect_slack.py for verified ids)")
    if len(participants) < K_ANON:
        print(f"  Respect Index suppressed: only {len(participants)} participants "
              f"(k-anonymity threshold is {K_ANON}).")
    else:
        idx = respect_index(findings)
        print(f"  Respect Index: {idx}/100  "
              f"({sum(f['polarity'] == 'respectful' for f in findings)} respectful, "
              f"{sum(f['polarity'] == 'disrespectful' for f in findings)} disrespectful behaviors)")
    print()


def apply_consent(transcript: dict, findings: list[dict] | None, consented: set):
    """Drop everything about non-consented authors (PRODUCT.md §5).

    Keeps only messages whose author has opted in, reindexing message_index to
    the filtered list. When `findings` is given (demo mode), filters and
    reindexes them too; when it's None (live mode), the transcript is filtered
    *before* scoring so non-consented text is never sent to the API.
    """
    kept = [(i, m) for i, m in enumerate(transcript["messages"])
            if m["author_id"] in consented]
    remap = {old: new for new, (old, _) in enumerate(kept)}
    transcript = {**transcript, "messages": [m for _, m in kept]}
    if findings is not None:
        # A finding survives iff its message survived — identity is decided by the
        # message's author_id, not by anything on the finding.
        findings = [
            {**f, "message_index": remap[f["message_index"]]}
            for f in findings
            if f.get("message_index") in remap
        ]
    return transcript, findings


def main() -> None:
    args = sys.argv[1:]
    demo = "--demo" in args
    save = "--save" in args
    require_consent = "--require-consent" in args
    estimate = "--estimate" in args

    def take_value(flag: str, example: str) -> str | None:
        """Pull `--flag value` out of args, returning value (or None if absent)."""
        nonlocal args
        if flag not in args:
            return None
        i = args.index(flag)
        if i + 1 >= len(args) or args[i + 1].startswith("--"):
            sys.exit(f"{flag} needs a value, e.g. {flag} {example}")
        value = args[i + 1]
        args = args[:i] + args[i + 2 :]
        return value

    # Value-bearing flags (pull them out before reading positionals).
    db_path = take_value("--db", "sugapp.db")
    model = take_value("--model", "claude-haiku-4-5") or MODEL

    max_cost = None
    raw_max_cost = take_value("--max-cost", "0.50")
    if raw_max_cost is not None:
        try:
            max_cost = float(raw_max_cost)
        except ValueError:
            sys.exit(f"--max-cost needs a dollar amount, e.g. --max-cost 0.50 (got {raw_max_cost!r})")

    paths = [a for a in args if not a.startswith("--")]
    if len(paths) != 1:
        sys.exit(__doc__)
    transcript = load_transcript(paths[0])

    # Consent gate (PRODUCT.md §5): only opted-in authors may be scored or stored.
    consented = None
    if require_consent:
        import store

        cconn = store.connect(db_path) if db_path else store.connect()
        consented = store.consented_authors(cconn)
        present = {m["author_id"] for m in transcript["messages"]}
        if not (present & consented):
            names = ", ".join(sorted(m["author"] for m in transcript["messages"]))
            opted = ", ".join(sorted(store.display_name(cconn, a) for a in consented)) \
                or "(no one yet)"
            cconn.close()
            sys.exit(
                "--require-consent: no opted-in participants in this transcript.\n"
                f"  in transcript: {names}\n"
                f"  opted in:      {opted}\n"
                "  Opt people in first:  python consent.py --in <name-or-id>"
            )
        cconn.close()
        if not demo:
            # Filter BEFORE scoring so non-consented text never reaches the API.
            transcript, _ = apply_consent(transcript, None, consented)

    if demo:
        if estimate:
            sys.exit("--estimate is for live runs; --demo spends nothing to begin with.")
        # Offline mode: render a bundled fixture of expected model output so the
        # pipeline (evidence, rewrites, Respect Index, k-anonymity) can be seen
        # with no API key and no token spend. Looks for <transcript>.findings.json.
        fixture = os.path.splitext(paths[0])[0] + ".findings.json"
        if not os.path.exists(fixture):
            sys.exit(f"--demo needs a fixture next to the transcript: {fixture}")
        findings = json.load(open(fixture, encoding="utf-8"))["findings"]
        if consented is not None:
            transcript, findings = apply_consent(transcript, findings, consented)
    else:
        import anthropic  # only needed for a live scoring run
        import cost

        client = anthropic.Anthropic()

        # Cost pre-flight: --estimate (dry run) and --max-cost both need the
        # projected worst-case cost, from a free token count of the real request.
        if estimate or max_cost is not None:
            system, messages = build_request(transcript)
            try:
                n_in = cost.count_input_tokens(client, model, system, messages)
                projected = cost.estimate_cost(n_in, model, MAX_TOKENS)
            except ValueError as e:
                sys.exit(f"  cost pre-flight failed: {e}")
            print(f"  cost estimate: ~{cost.fmt_usd(projected)} worst case "
                  f"({n_in:,} input tokens + up to {MAX_TOKENS:,} output @ {model})")
            if max_cost is not None and projected > max_cost:
                sys.exit(f"  aborted: projected ~{cost.fmt_usd(projected)} exceeds "
                         f"--max-cost {cost.fmt_usd(max_cost)} (nothing was spent).")
            if estimate:
                return  # dry run: report the projection and stop before paying.

        findings, usage = score_transcript(client, transcript, model=model)
        print(f"  cost: {cost.summarize(usage, model)}")

    # Identity is authoritative from the transcript, not the model.
    attach_identity(transcript, findings)

    render(transcript, findings)

    if save:
        import store

        conn = store.connect(db_path) if db_path else store.connect()
        participants = len({m["author_id"] for m in transcript["messages"]})
        run_id = store.save_run(
            conn,
            channel=transcript.get("channel", "unknown"),
            source=paths[0],
            participant_count=participants,
            findings=findings,
            identities=identity_map(transcript),
        )
        conn.close()
        print(f"  saved run #{run_id} ({len(findings)} findings) → "
              f"{db_path or store.DEFAULT_DB}\n")


if __name__ == "__main__":
    main()
