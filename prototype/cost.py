# SugApp — proprietary & confidential. © 2026 <Your Legal Name>. All rights reserved.
# Trade-secret methodology; not for distribution. See /LICENSE and /IP.md.
"""Cost controls for the SugApp scorer.

Scoring a transcript is a paid Claude API call, and at scale (every channel,
every day) the bill is the product's dominant variable cost. This module gives
score.py three things:

  * accounting  — turn a response's token `usage` into dollars (cache-aware)
  * estimation  — project a run's worst-case cost *before* paying for it, from
                  a free token count
  * a price table — one place to keep per-model rates, easy to update

Prices are first-party Anthropic API rates in USD per 1M tokens; update them
from https://platform.claude.com/docs/en/pricing when they change. They are a
transparent placeholder for a real billing integration — the point is that the
scorer never spends money silently.
"""

# USD per 1,000,000 tokens (input, output). Keep in sync with the pricing page.
PRICING = {
    "claude-opus-5":    {"input": 5.00, "output": 25.00},
    "claude-opus-4-8":  {"input": 5.00, "output": 25.00},
    "claude-sonnet-5":  {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

# Cache token pricing, as multiples of the model's base input rate:
#   reads are ~0.1x input, a 5-minute ephemeral write is ~1.25x input.
CACHE_READ_MULT = 0.1
CACHE_WRITE_MULT = 1.25

_PER_TOKEN = 1_000_000


def price_for(model: str) -> dict:
    """Return {'input', 'output'} USD/1M rates, or raise with a helpful list."""
    try:
        return PRICING[model]
    except KeyError:
        known = ", ".join(sorted(PRICING))
        raise ValueError(f"no price on file for {model!r}; known models: {known}")


def _get(usage, name: str) -> int:
    """Read a token field off an SDK usage object (or dict), defaulting to 0."""
    if usage is None:
        return 0
    if isinstance(usage, dict):
        return int(usage.get(name) or 0)
    return int(getattr(usage, name, 0) or 0)


def cost_of_usage(usage, model: str) -> float:
    """Actual USD cost of a completed call, from its token `usage`.

    Accounts for cache reads (cheap) and cache writes (a small premium) as well
    as ordinary input/output tokens.
    """
    rate = price_for(model)
    in_rate = rate["input"] / _PER_TOKEN
    out_rate = rate["output"] / _PER_TOKEN
    return (
        _get(usage, "input_tokens") * in_rate
        + _get(usage, "output_tokens") * out_rate
        + _get(usage, "cache_read_input_tokens") * in_rate * CACHE_READ_MULT
        + _get(usage, "cache_creation_input_tokens") * in_rate * CACHE_WRITE_MULT
    )


def estimate_cost(input_tokens: int, model: str, max_output_tokens: int) -> float:
    """Worst-case USD for a run: all input at full price + a full `max_tokens`
    of output. Real cost is usually lower (the model rarely fills max_tokens),
    so this is a safe ceiling for a --max-cost gate."""
    rate = price_for(model)
    return (
        input_tokens * rate["input"] / _PER_TOKEN
        + max_output_tokens * rate["output"] / _PER_TOKEN
    )


def count_input_tokens(client, model: str, system, messages) -> int:
    """Free pre-flight token count for the exact request the scorer will send."""
    return client.messages.count_tokens(
        model=model, system=system, messages=messages
    ).input_tokens


def fmt_usd(amount: float) -> str:
    """Format a dollar amount, keeping sub-cent runs legible."""
    if amount and amount < 0.01:
        return f"${amount:.4f}"
    return f"${amount:.2f}"


def summarize(usage, model: str) -> str:
    """One-line cost + token breakdown for a completed call."""
    try:
        dollars = fmt_usd(cost_of_usage(usage, model))
    except ValueError:
        dollars = f"(no price on file for {model})"
    cached = _get(usage, "cache_read_input_tokens")
    return (
        f"{dollars}  "
        f"({_get(usage, 'input_tokens'):,} in / "
        f"{_get(usage, 'output_tokens'):,} out"
        + (f"; {cached:,} cached" if cached else "")
        + ")"
    )
