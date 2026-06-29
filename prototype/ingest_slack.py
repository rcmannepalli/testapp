#!/usr/bin/env python3
"""Turn a Slack export into a transcript score.py can read.

This is the Phase-1 "Slack connector" (PRODUCT.md §8) in its lowest-risk form:
it reads a **Slack workspace export** (the JSON you download from
Settings → Import/Export Data → Export) — no OAuth, no API token, no live
access to anyone's messages. That live connector, and the opt-in/consent layer
it requires (§5), come later; this lets you score real conversations today.

It resolves user IDs to names (from users.json), turns Slack markup into plain
text (`<@U123>` → `@Dana`, `<#C1|general>` → `#general`, `<url|label>` → label,
`&amp;`/`&lt;`/`&gt;` → `& < >`), drops non-conversational events (joins, bot
messages, topic changes), and emits the transcript format:

    {"channel": "#eng-standup", "messages": [{"author": ..., "text": ...}, ...]}

Usage:
    # Export root (has users.json + per-channel folders) — pick a channel:
    python ingest_slack.py sample_slack_export --channel eng-standup
    python ingest_slack.py sample_slack_export --channel eng-standup -o eng.json

    # Pipe straight into the scorer (live run needs ANTHROPIC_API_KEY):
    python ingest_slack.py sample_slack_export --channel eng-standup | python score.py -

    # A single channel folder or a single day's .json file also work:
    python ingest_slack.py sample_slack_export/eng-standup --users sample_slack_export/users.json

With no --channel on a multi-channel export, the available channels are listed.
"""
import json
import os
import re
import sys

# Slack message subtypes that are real human conversation. Everything else
# (channel_join/leave, bot_message, channel_topic, …) is dropped.
HUMAN_SUBTYPES = {None, "", "thread_broadcast", "me_message"}

_MENTION = re.compile(r"<@([A-Z0-9]+)(?:\|([^>]+))?>")      # <@U123> or <@U123|dana>
_CHANNEL = re.compile(r"<#[A-Z0-9]+(?:\|([^>]+))?>")        # <#C123|general>
_SPECIAL = re.compile(r"<!(\w+)(?:\|[^>]+)?>")              # <!here>, <!channel>
_LINK = re.compile(r"<(https?://[^>|]+)(?:\|([^>]+))?>")    # <url> or <url|label>


def load_users(path: str) -> dict:
    """Map Slack user id → best available display name."""
    with open(path, encoding="utf-8") as fh:
        users = json.load(fh)
    names = {}
    for u in users:
        profile = u.get("profile") or {}
        name = (profile.get("display_name") or u.get("real_name")
                or u.get("name") or u["id"])
        names[u["id"]] = name
    return names


def clean_text(text: str, names: dict) -> str:
    """Resolve Slack markup and unescape entities → plain readable text."""
    # Markup first (operates on literal < >), then entity-unescape.
    text = _MENTION.sub(lambda m: "@" + (m.group(2) or names.get(m.group(1), m.group(1))), text)
    text = _CHANNEL.sub(lambda m: "#" + (m.group(1) or "channel"), text)
    text = _SPECIAL.sub(lambda m: "@" + m.group(1), text)
    text = _LINK.sub(lambda m: m.group(2) or m.group(1), text)
    # Slack escapes only these three; unescape &amp; last to avoid double-decode.
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return text.strip()


def is_human_message(msg: dict) -> bool:
    return (
        msg.get("type") == "message"
        and msg.get("subtype") in HUMAN_SUBTYPES
        and not msg.get("bot_id")
        and msg.get("user")
        and msg.get("text", "").strip()
    )


def read_channel_messages(channel_dir: str) -> list[dict]:
    """All messages from a channel folder's dated .json files, oldest first."""
    files = sorted(f for f in os.listdir(channel_dir) if f.endswith(".json"))
    messages: list[dict] = []
    for fname in files:
        with open(os.path.join(channel_dir, fname), encoding="utf-8") as fh:
            day = json.load(fh)
        if isinstance(day, list):
            messages.extend(day)
    # ts is a stringified float; sort numerically so threaded replies land in order.
    messages.sort(key=lambda m: float(m.get("ts", 0)))
    return messages


def channel_dirs(root: str) -> list[str]:
    """Sub-folders of an export root that contain channel .json files."""
    out = []
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if os.path.isdir(full) and any(f.endswith(".json") for f in os.listdir(full)):
            out.append(name)
    return out


def transcript_from(messages: list[dict], names: dict, channel_label: str) -> dict:
    out_msgs = []
    for m in messages:
        if not is_human_message(m):
            continue
        author = names.get(m["user"], m["user"])
        out_msgs.append({"author": author, "text": clean_text(m["text"], names)})
    label = channel_label if channel_label.startswith("#") else f"#{channel_label}"
    return {"channel": label, "messages": out_msgs}


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

    users_path = take("--users")
    channel = take("--channel")
    out_path = take("-o") or take("--out")

    positionals = [a for a in args if not a.startswith("-")]
    if len(positionals) != 1:
        sys.exit(__doc__)
    path = positionals[0]

    if not os.path.exists(path):
        sys.exit(f"no such path: {path}")

    # Resolve the users file: explicit --users, else users.json in the export root.
    if users_path is None:
        candidate = os.path.join(path if os.path.isdir(path) else os.path.dirname(path),
                                 "users.json")
        users_path = candidate if os.path.exists(candidate) else None
    names = load_users(users_path) if users_path else {}

    # Resolve which messages to read.
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            messages = json.load(fh)
        if not isinstance(messages, list):
            sys.exit("expected a JSON array of Slack messages in that file")
        messages.sort(key=lambda m: float(m.get("ts", 0)))
        label = channel or os.path.splitext(os.path.basename(path))[0]
    else:
        # A directory: an export root (channel sub-folders) or a single channel folder.
        has_own_json = any(f.endswith(".json") and f != "users.json"
                           for f in os.listdir(path))
        subchannels = channel_dirs(path)
        if subchannels and not has_own_json:
            if channel is None:
                sys.exit("multiple channels — pick one with --channel.\n  "
                         + "\n  ".join(subchannels))
            if channel not in subchannels:
                sys.exit(f"channel '{channel}' not found. Available:\n  "
                         + "\n  ".join(subchannels))
            messages = read_channel_messages(os.path.join(path, channel))
            label = channel
        else:
            messages = read_channel_messages(path)
            label = channel or os.path.basename(os.path.normpath(path))

    transcript = transcript_from(messages, names, label)
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
