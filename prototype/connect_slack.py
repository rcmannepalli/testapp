#!/usr/bin/env python3
"""Live Slack connector — pull a channel via the Slack Web API → transcript.

This is the Phase-1 Slack connector (PRODUCT.md §8) talking to the real API,
the step up from ingest_slack.py (which reads a static export). It emits the
same transcript format, so it flows straight into the existing pipeline
(consent gate → score → store → mirror/dashboard).

Stdlib only (urllib) — no SDK dependency. Reuses ingest_slack.py for name
resolution and Slack-markup cleaning, so output matches the export path exactly.

------------------------------------------------------------------------------
You do NOT need a paid plan or the full OAuth web flow to use this.
------------------------------------------------------------------------------
1. Create a free Slack workspace.
2. api.slack.com/apps → Create New App → From scratch.
3. OAuth & Permissions → add Bot Token Scopes:
      channels:history, channels:read, users:read
   (add groups:history, groups:read for private channels).
4. Install to Workspace  ← this performs OAuth and gives you a bot token (xoxb-…).
5. Invite the bot to the channel:  /invite @your-app-name
6. export SLACK_TOKEN=xoxb-...

The "Install to Workspace" button *is* the OAuth handshake for your own
workspace. The full 3-legged OAuth (client_id/secret + redirect URL) is only
needed to let *other* organizations install your app — defer that until you're
multi-tenant.

Usage:
    export SLACK_TOKEN=xoxb-...
    python connect_slack.py --channel eng-standup
    python connect_slack.py --channel eng-standup -o eng.json
    python connect_slack.py --channel eng-standup | python score.py --require-consent -

    # Try it with NO workspace at all (reads bundled API-response fixtures):
    python connect_slack.py --channel eng-standup --mock sample_slack_api
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Reuse the export path's transforms so live + export output are identical.
from ingest_slack import names_from_users, transcript_from

SLACK_API = "https://slack.com/api/"


def slack_get(method: str, token: str, params: dict | None = None) -> dict:
    """Call one Slack Web API method; raise on transport or API-level error."""
    url = SLACK_API + method
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate limited — honor Retry-After and try again
                time.sleep(int(e.headers.get("Retry-After", "2")))
                continue
            raise SystemExit(f"Slack HTTP {e.code} on {method}: {e.reason}")
        except urllib.error.URLError as e:
            raise SystemExit(f"network error calling {method}: {e.reason}")
        if not data.get("ok"):
            raise SystemExit(_explain_error(method, data.get("error", "unknown")))
        return data
    raise SystemExit(f"Slack {method}: still rate-limited after retries")


def _explain_error(method: str, err: str) -> str:
    hints = {
        "invalid_auth": "SLACK_TOKEN is missing or wrong.",
        "not_authed": "no token sent — set SLACK_TOKEN.",
        "missing_scope": "the bot token lacks a required scope "
                         "(channels:history / channels:read / users:read).",
        "not_in_channel": "invite the app to the channel first: /invite @your-app.",
        "channel_not_found": "no such channel (wrong name, or the app can't see it).",
        "ratelimited": "rate limited — try again shortly.",
    }
    tip = hints.get(err, "")
    return f"Slack API error on {method}: {err}" + (f"\n  → {tip}" if tip else "")


def paged(method: str, token: str, params: dict, key: str, cap: int | None = None) -> list:
    """Collect a cursor-paginated list field across all pages (up to cap items)."""
    params = dict(params)
    items: list = []
    while True:
        data = slack_get(method, token, params)
        items.extend(data.get(key, []))
        if cap and len(items) >= cap:
            return items[:cap]
        cursor = (data.get("response_metadata") or {}).get("next_cursor", "")
        if not cursor:
            return items
        params["cursor"] = cursor


def resolve_channel(token: str, name: str) -> tuple[str, str]:
    """Map a channel name (or id) to (channel_id, channel_name)."""
    bare = name.lstrip("#")
    # Looks like a channel ID already (C…/G…): use as-is.
    if bare[:1] in ("C", "G") and bare.isupper() and bare.isalnum():
        return bare, bare
    channels = paged(
        "conversations.list", token,
        {"types": "public_channel,private_channel", "limit": 1000}, "channels",
    )
    for c in channels:
        if c.get("name") == bare:
            return c["id"], c["name"]
    raise SystemExit(
        f"channel #{bare} not found. The app must have channels:read and be able "
        f"to see the channel. Available: "
        + (", ".join(sorted(c.get("name", "?") for c in channels)) or "(none)")
    )


def fetch_live(token: str, channel: str, cap: int | None) -> tuple[list, dict, str]:
    channel_id, channel_name = resolve_channel(token, channel)
    members = paged("users.list", token, {"limit": 1000}, "members")
    messages = paged("conversations.history", token,
                     {"channel": channel_id, "limit": 200}, "messages", cap=cap)
    return messages, names_from_users(members), channel_name


def fetch_mock(mock_dir: str) -> tuple[list, dict]:
    """Read recorded users.list + conversations.history responses from a folder."""
    def load(fname):
        with open(os.path.join(mock_dir, fname), encoding="utf-8") as fh:
            return json.load(fh)
    users = load("users.list.json")
    history = load("conversations.history.json")
    return history.get("messages", []), names_from_users(users.get("members", []))


def main() -> None:
    args = sys.argv[1:]

    def take(flag):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(f"{flag} needs a value")
            val = args[i + 1]
            del args[i : i + 2]
            return val
        return None

    channel = take("--channel")
    out_path = take("-o") or take("--out")
    token = take("--token") or os.environ.get("SLACK_TOKEN")
    mock_dir = take("--mock")
    cap = take("--limit")
    cap = int(cap) if cap else None

    if not channel:
        sys.exit("--channel is required, e.g. --channel eng-standup\n\n" + __doc__)

    if mock_dir:
        messages, names = fetch_mock(mock_dir)
        channel_name = channel
    else:
        if not token:
            sys.exit("no Slack token. Set SLACK_TOKEN (or pass --token), or try "
                     "offline with --mock sample_slack_api.\n\n" + __doc__)
        messages, names, channel_name = fetch_live(token, channel, cap)

    messages.sort(key=lambda m: float(m.get("ts", 0)))  # oldest first
    transcript = transcript_from(messages, names, channel_name)
    payload = json.dumps(transcript, indent=2, ensure_ascii=False)

    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
        print(f"  wrote {out_path} — {len(transcript['messages'])} messages "
              f"from {transcript['channel']}", file=sys.stderr)
    else:
        print(payload)


if __name__ == "__main__":
    main()
