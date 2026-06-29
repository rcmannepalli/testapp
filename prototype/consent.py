#!/usr/bin/env python3
"""Manage opt-in consent — the gate that must exist before any real data flows.

PRODUCT.md §5 makes this non-negotiable: scoring is **opt-in**, with a real,
**penalty-free opt-out**. Only people who have opted in may be scored or stored
(see `score.py --require-consent`). Opting out is free and also **purges** what
was already collected about that person — withdrawing consent withdraws the data.

Usage:
    python consent.py --list                 # everyone's consent status
    python consent.py --status Dana          # one person's status
    python consent.py --in Dana              # opt Dana in
    python consent.py --in Dana Sam Priya    # opt several in at once
    python consent.py --out Dana             # opt out AND purge Dana's stored data
    python consent.py --db team.db --in Dana

The author identifier is whatever appears as `author` in transcripts (a
pseudonym in the samples). Absence of a decision means NOT consented — silence
is never treated as consent.
"""
import os
import sys

import store


def main() -> None:
    args = sys.argv[1:]

    db_path = store.DEFAULT_DB
    if "--db" in args:
        i = args.index("--db")
        if i + 1 >= len(args):
            sys.exit("--db needs a path")
        db_path = args[i + 1]
        args = args[:i] + args[i + 2 :]

    conn = store.connect(db_path)

    def names_after(flag: str) -> list[str]:
        i = args.index(flag)
        rest = args[i + 1 :]
        people = []
        for a in rest:
            if a.startswith("--"):
                break
            people.append(a)
        if not people:
            sys.exit(f"{flag} needs at least one name, e.g. {flag} Dana")
        return people

    if "--list" in args:
        rows = store.consent_list(conn)
        if not rows:
            print("No consent decisions recorded yet. Scoring is opt-in, so no one "
                  "can be scored until they opt in:\n  python consent.py --in <name>")
        else:
            print("Consent decisions:")
            for r in rows:
                mark = "✅ in " if r["status"] == "in" else "🚫 out"
                print(f"  {mark}  {r['author']:<16} (updated {r['updated_at']})")
        # Audit: anyone with stored data who is not opted in.
        stragglers = store.unconsented_with_data(conn)
        if stragglers:
            print("\n⚠️  Stored findings exist for people NOT opted in "
                  "(opt them in, or `--out` to purge):")
            for a in stragglers:
                print(f"     {a}")
        conn.close()
        return

    if "--status" in args:
        i = args.index("--status")
        if i + 1 >= len(args):
            sys.exit("--status needs a name")
        author = args[i + 1]
        status = store.get_consent(conn, author)
        label = {"in": "opted IN", "out": "opted OUT", None: "no decision (NOT consented)"}
        print(f"{author}: {label[status]}")
        conn.close()
        return

    if "--in" in args:
        for author in names_after("--in"):
            store.set_consent(conn, author, "in")
            print(f"  ✅ {author} opted in — may now be scored and stored.")
        conn.close()
        return

    if "--out" in args:
        for author in names_after("--out"):
            deleted = store.purge_person(conn, author)
            store.set_consent(conn, author, "out")
            print(f"  🚫 {author} opted out — withdrawal recorded; "
                  f"purged {deleted} stored finding(s) and any goal.")
        conn.close()
        return

    conn.close()
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
