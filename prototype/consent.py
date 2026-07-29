#!/usr/bin/env python3
# SugApp — proprietary & confidential. © 2026 <Your Legal Name>. All rights reserved.
# Trade-secret methodology; not for distribution. See /LICENSE and /IP.md.
"""Manage opt-in consent — the gate that must exist before any real data flows.

PRODUCT.md §5 makes this non-negotiable: scoring is **opt-in**, with a real,
**penalty-free opt-out**. Only people who have opted in may be scored or stored
(see `score.py --require-consent`). Opting out is free and also **purges** what
was already collected about that person — withdrawing consent withdraws the data.

Consent is keyed by a stable **author_id** (the Slack user id), not a display
name — so it can't be defeated by a rename or a name collision. You can still
refer to people by name on the command line: names are resolved to ids via the
identities the scorer records (and `--import` below).

Usage:
    python consent.py --import eng.json          # learn who's in a transcript
    python consent.py --list                     # everyone's consent status
    python consent.py --status Dana              # one person (name or id)
    python consent.py --in Dana Sam              # opt in (by name or id)
    python consent.py --in U02SAM                # opt in by id directly
    python consent.py --out Dana                 # opt out AND purge stored data
    python consent.py --db team.db --in Dana

Absence of a decision means NOT consented — silence is never treated as consent.
Before anyone has been imported or scored, opt people in by their id.
"""
import json
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

    def values_after(flag: str) -> list[str]:
        i = args.index(flag)
        vals = []
        for a in args[i + 1 :]:
            if a.startswith("--"):
                break
            vals.append(a)
        if not vals:
            sys.exit(f"{flag} needs at least one value, e.g. {flag} Dana")
        return vals

    def resolve(token: str) -> str:
        try:
            aid = store.resolve_author(conn, token)
        except ValueError as e:
            conn.close()
            sys.exit(str(e))
        # A token that matches no known person becomes a brand-new id. That's the
        # bootstrap path (opting someone in by id before any data) — but if we DO
        # know other people and this matched none of them, it's almost certainly a
        # typo (e.g. "Priya" vs "Priya Shah"), so refuse rather than silently
        # protect the wrong id.
        known = store.all_identities(conn)
        if not store.is_known(conn, aid) and known:
            roster = ", ".join(f"{n} ({i})" for i, n in sorted(known.items(), key=lambda kv: kv[1]))
            conn.close()
            sys.exit(
                f"'{token}' matches no known person (it would create a new id "
                f"'{aid}').\n  Known people: {roster}\n"
                f"  Use an exact name or id above, or --import a transcript first."
            )
        return aid

    if "--import" in args:
        i = args.index("--import")
        if i + 1 >= len(args):
            sys.exit("--import needs a transcript path")
        with open(args[i + 1], encoding="utf-8") as fh:
            transcript = json.load(fh)
        mapping, verified = {}, {}
        for m in transcript.get("messages", []):
            name = m.get("author", "unknown")
            has_id = bool(m.get("author_id"))
            aid = m["author_id"] if has_id else name
            mapping[aid] = name
            verified[aid] = has_id
        # Register verified and unverified ids separately so verified wins.
        store.register_identities(conn, {k: v for k, v in mapping.items() if verified[k]}, verified=True)
        store.register_identities(conn, {k: v for k, v in mapping.items() if not verified[k]}, verified=False)
        print(f"  imported {len(mapping)} identities from {args[i + 1]}. Now opt people in:")
        for aid, name in sorted(mapping.items(), key=lambda kv: kv[1]):
            tag = "" if verified[aid] else "  (unverified id)"
            print(f"     {name:<16} {aid}{tag}")
        conn.close()
        return

    if "--list" in args:
        rows = store.consent_list(conn)
        if not rows:
            print("No consent decisions recorded yet. Scoring is opt-in, so no one "
                  "can be scored until they opt in:\n  python consent.py --in <name-or-id>")
        else:
            print("Consent decisions:")
            for r in rows:
                mark = "✅ in " if r["status"] == "in" else "🚫 out"
                print(f"  {mark}  {r['display_name']:<16} {r['author_id']:<12} "
                      f"(updated {r['updated_at']})")
        stragglers = store.unconsented_with_data(conn)
        if stragglers:
            print("\n⚠️  Stored findings exist for people NOT opted in "
                  "(opt them in, or `--out` to purge):")
            for s in stragglers:
                print(f"     {s['display_name']} ({s['author_id']})")
        conn.close()
        return

    if "--status" in args:
        i = args.index("--status")
        if i + 1 >= len(args):
            sys.exit("--status needs a name or id")
        aid = resolve(args[i + 1])
        status = store.get_consent(conn, aid)
        label = {"in": "opted IN", "out": "opted OUT",
                 None: "no decision (NOT consented)"}
        print(f"{store.display_name(conn, aid)} ({aid}): {label[status]}")
        conn.close()
        return

    if "--in" in args:
        for token in values_after("--in"):
            aid = resolve(token)
            store.set_consent(conn, aid, "in")
            print(f"  ✅ {store.display_name(conn, aid)} ({aid}) opted in — "
                  f"may now be scored and stored.")
        conn.close()
        return

    if "--out" in args:
        for token in values_after("--out"):
            aid = resolve(token)
            name = store.display_name(conn, aid)
            deleted = store.purge_person(conn, aid)
            store.set_consent(conn, aid, "out")
            print(f"  🚫 {name} ({aid}) opted out — withdrawal recorded; "
                  f"purged {deleted} stored finding(s) and any goal.")
        conn.close()
        return

    conn.close()
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
