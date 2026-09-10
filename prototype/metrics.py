# SugApp — proprietary & confidential. © 2026 <Your Legal Name>. All rights reserved.
# Trade-secret methodology; not for distribution. See /LICENSE and /IP.md.
"""Per-run observability for the scorer — the 'sensors on the machine'.

The findings + Respect Index are the *product* (saved by store.py). This is
separate: one health record per scoring run — how long it took, what it cost,
whether the model refused, whether the output was on-schema. It answers "is the
scorer working well?", not "how respectful was the chat?".

Each run is written to TWO sinks with the SAME record:
  * a run_metrics SQLite table — for local rollups (obs.py, dashboards)
  * an append-only run_metrics.jsonl file — one JSON object per line, the format
    every monitoring agent (Datadog, Fluent Bit, Vector, ...) can tail and ship.

Logging must never break scoring: the JSONL write is best-effort.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

import cost

DEFAULT_JSONL = os.path.join(os.path.dirname(__file__), "run_metrics.jsonl")

RUN_METRICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS run_metrics (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                    TEXT    NOT NULL,   -- when the run happened (ISO-8601 UTC)
    run_id                INTEGER,            -- links to runs.id when the run was saved
    channel               TEXT,
    model                 TEXT    NOT NULL,
    latency_ms            INTEGER,            -- wall time of the model call
    input_tokens          INTEGER,
    output_tokens         INTEGER,
    cache_read_tokens     INTEGER,
    cache_creation_tokens INTEGER,
    cost_usd              REAL,
    stop_reason           TEXT,               -- end_turn / refusal / max_tokens / error
    schema_ok             INTEGER,            -- 1 = valid on-schema JSON, 0 = not
    findings_count        INTEGER
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_run(conn: sqlite3.Connection, *, model: str, latency_ms: int,
               findings_count: int, usage=None, stop_reason: str = "end_turn",
               schema_ok: bool = True, run_id: int | None = None,
               channel: str | None = None,
               jsonl_path: str = DEFAULT_JSONL) -> dict:
    """Capture one run's health to SQLite + JSONL. Returns the record it wrote.

    `usage` is the SDK usage object (or None on refusal/error); token + cost
    fields default to 0 when it's absent, so a failed run still gets a record.
    """
    conn.execute(RUN_METRICS_SCHEMA)  # idempotent: ensure the table exists

    priced = usage is not None and model in cost.PRICING
    record = {
        "ts": _now(),
        "run_id": run_id,
        "channel": channel,
        "model": model,
        "latency_ms": latency_ms,
        "input_tokens": cost._get(usage, "input_tokens"),
        "output_tokens": cost._get(usage, "output_tokens"),
        "cache_read_tokens": cost._get(usage, "cache_read_input_tokens"),
        "cache_creation_tokens": cost._get(usage, "cache_creation_input_tokens"),
        "cost_usd": round(cost.cost_of_usage(usage, model), 6) if priced else 0.0,
        "stop_reason": stop_reason,
        "schema_ok": schema_ok,
        "findings_count": findings_count,
    }

    with conn:
        conn.execute(
            """INSERT INTO run_metrics
               (ts, run_id, channel, model, latency_ms, input_tokens,
                output_tokens, cache_read_tokens, cache_creation_tokens,
                cost_usd, stop_reason, schema_ok, findings_count)
               VALUES (:ts, :run_id, :channel, :model, :latency_ms, :input_tokens,
                :output_tokens, :cache_read_tokens, :cache_creation_tokens,
                :cost_usd, :stop_reason, :schema_ok, :findings_count)""",
            {**record, "schema_ok": int(record["schema_ok"])},
        )

    # Second sink: append one JSON line. Best-effort — a logging failure must not
    # take down a scoring run.
    try:
        with open(jsonl_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass

    return record
