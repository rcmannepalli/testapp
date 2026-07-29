#!/usr/bin/env python3
# SugApp — proprietary & confidential. © 2026 <Your Legal Name>. All rights reserved.
# Trade-secret methodology; not for distribution. See /LICENSE and /IP.md.
"""Interactive REPL for the Respect & Listening scorer.

Type a message and press Enter; it's scored on its own against the rubric and the
findings (behavior, evidence, coaching rewrite, rationale) print underneath. This
is the fastest way to probe the model — try a dismissive line, then a blunt-but-
respectful disagreement, and see what it flags.

Each message is scored in ISOLATION — there is no conversation memory, so
context-dependent behaviors (e.g. acknowledgment that builds on an earlier
message) won't be detected here. Use score.py on a full transcript for that.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python chat.py
    python chat.py --author Dana    # label your messages with an author name

Commands inside the REPL:
    quit / exit     leave (Ctrl-D also works)
"""
import sys

# Reuse the model id and the live scoring call from score.py — single source of
# truth. Importing score.py is safe: its main() is guarded by __main__.
from score import score_transcript

MARK = {"respectful": "✅", "disrespectful": "⚠️ "}


def render(findings: list[dict]) -> None:
    if not findings:
        print("   • no findings — nothing flagged\n")
        return
    for f in findings:
        print(f"   {MARK.get(f['polarity'], '? ')}{f['behavior']} — {f['rationale']}")
        print(f"      evidence: “{f['evidence']}”")
        if f.get("coaching_rewrite", "").strip():
            print(f"      rewrite:  “{f['coaching_rewrite']}”")
    print()


def parse_author(args: list[str]) -> str:
    if "--author" in args:
        i = args.index("--author")
        if i + 1 < len(args):
            return args[i + 1]
    return "You"


def main() -> None:
    author = parse_author(sys.argv[1:])

    import anthropic  # only needed for a live run

    client = anthropic.Anthropic()

    print("Respect & Listening scorer — interactive REPL")
    print("Type a message to score it. Each message is scored on its own (no memory).")
    print("Ctrl-D or 'quit' to exit.\n")

    while True:
        try:
            text = input(f"{author}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() in {"quit", "exit"}:
            break

        transcript = {"channel": "#repl", "messages": [{"author": author, "text": text}]}
        try:
            findings = score_transcript(client, transcript)
        except Exception as e:  # auth, rate limit, transient API errors — keep the REPL alive
            print(f"   [error scoring this message: {e}]\n")
            continue
        render(findings)


if __name__ == "__main__":
    main()
