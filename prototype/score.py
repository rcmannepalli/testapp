#!/usr/bin/env python3
"""SugApp Respect & Listening scorer — standalone prototype.

Usage:
    python score.py sample_transcripts/standup.json
    cat transcript.json | python score.py -
    python score.py --demo sample_transcripts/standup.json   # offline, no key
    python score.py --save sample_transcripts/standup.json    # persist to SQLite
    python score.py --save --db mine.db transcript.json       # custom db path

Reads a transcript JSON ({"channel": str, "messages": [{"author", "text"}, ...]}),
scores it against the Respect & Listening rubric using Claude, and prints per-message
findings (with evidence + coaching rewrites) plus a k-anonymized team Respect Index.

With --save, the run and its findings are written to a SQLite database (default
sugapp.db next to this script; override with --db) so trends accumulate over time.
Read them back with trends.py.
"""
import json
import os
import sys
from collections import defaultdict

from rubric import DISRESPECTFUL, FINDINGS_SCHEMA, RESPECTFUL, system_prompt

MODEL = "claude-opus-4-8"
K_ANON = 5  # never show a team rollup for fewer than this many distinct participants


def load_transcript(path: str) -> dict:
    raw = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    data = json.loads(raw)
    if "messages" not in data:
        raise ValueError("transcript must have a 'messages' list")
    return data


def score_transcript(client, transcript: dict) -> list[dict]:
    """Return the model's findings for every message in the transcript."""
    numbered = [
        {"message_index": i, "author": m.get("author", "unknown"), "text": m["text"]}
        for i, m in enumerate(transcript["messages"])
    ]
    user_content = (
        f"Channel: {transcript.get('channel', 'unknown')}\n\n"
        "Score each message below. Report only genuine findings.\n\n"
        f"{json.dumps(numbered, indent=2)}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=system_prompt(),
        messages=[{"role": "user", "content": user_content}],
        output_config={"format": {"type": "json_schema", "schema": FINDINGS_SCHEMA}},
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["findings"]


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
    participants = {m.get("author", "unknown") for m in messages}
    print("\n--- Team rollup (org view) ---")
    if len(participants) < K_ANON:
        print(f"  Respect Index suppressed: only {len(participants)} participants "
              f"(k-anonymity threshold is {K_ANON}).")
    else:
        idx = respect_index(findings)
        print(f"  Respect Index: {idx}/100  "
              f"({sum(f['polarity'] == 'respectful' for f in findings)} respectful, "
              f"{sum(f['polarity'] == 'disrespectful' for f in findings)} disrespectful behaviors)")
    print()


def main() -> None:
    args = sys.argv[1:]
    demo = "--demo" in args
    save = "--save" in args

    # --db takes a value; pull it (and its value) out before reading positionals.
    db_path = None
    if "--db" in args:
        i = args.index("--db")
        if i + 1 >= len(args):
            sys.exit("--db needs a path, e.g. --db sugapp.db")
        db_path = args[i + 1]
        args = args[:i] + args[i + 2 :]

    paths = [a for a in args if not a.startswith("--")]
    if len(paths) != 1:
        sys.exit(__doc__)
    transcript = load_transcript(paths[0])

    if demo:
        # Offline mode: render a bundled fixture of expected model output so the
        # pipeline (evidence, rewrites, Respect Index, k-anonymity) can be seen
        # with no API key and no token spend. Looks for <transcript>.findings.json.
        fixture = os.path.splitext(paths[0])[0] + ".findings.json"
        if not os.path.exists(fixture):
            sys.exit(f"--demo needs a fixture next to the transcript: {fixture}")
        findings = json.load(open(fixture, encoding="utf-8"))["findings"]
    else:
        import anthropic  # only needed for a live scoring run

        findings = score_transcript(anthropic.Anthropic(), transcript)

    render(transcript, findings)

    if save:
        import store

        conn = store.connect(db_path) if db_path else store.connect()
        participants = len({m.get("author", "unknown") for m in transcript["messages"]})
        run_id = store.save_run(
            conn,
            channel=transcript.get("channel", "unknown"),
            source=paths[0],
            participant_count=participants,
            findings=findings,
        )
        conn.close()
        print(f"  saved run #{run_id} ({len(findings)} findings) → "
              f"{db_path or store.DEFAULT_DB}\n")


if __name__ == "__main__":
    main()
