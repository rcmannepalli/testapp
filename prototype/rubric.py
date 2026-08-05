# SugApp — proprietary & confidential. © 2026 <Your Legal Name>. All rights reserved.
# Trade-secret methodology; not for distribution. See /LICENSE and /IP.md.
"""The Respect & Listening rubric — the product's core IP, in one place.

Every behavior here is an OBSERVABLE communication act, not an inferred trait or
emotion. This boundary is what keeps the product legal (EU AI Act) and effective.
See ../docs/PRODUCT.md §4.
"""

# Each behavior: the signal name, its polarity, and a plain-English definition the
# model uses to decide whether a message exhibits it.
BEHAVIORS = {
    # --- Listening signals -------------------------------------------------
    "acknowledgment": {
        "polarity": "respectful",
        "definition": "References or builds on what someone else said before responding "
        "('building on Dana's point...', 'good call, and...').",
    },
    "question_asking": {
        "polarity": "respectful",
        "definition": "Asks a genuine, curious question rather than only asserting.",
    },
    "invites_others": {
        "polarity": "respectful",
        "definition": "Explicitly makes room for others to speak or contribute "
        "('what does everyone think?', 'Sam, you were closer to this').",
    },
    # --- Respect-in-disagreement signals (signature) -----------------------
    "disagree_with_dignity": {
        "polarity": "respectful",
        "definition": "Pushes back on the IDEA, not the person "
        "('that won't work because X' rather than 'that's a naive take').",
    },
    "credit_attribution": {
        "polarity": "respectful",
        "definition": "Acknowledges whose idea or work it was.",
    },
    "dismissiveness": {
        "polarity": "disrespectful",
        "definition": "Minimizing or belittling language: 'obviously', 'as I already said', "
        "'that's not how it works', 'anyone knows that'. Makes the other person feel small.",
    },
    "personal_attack": {
        "polarity": "disrespectful",
        "definition": "Attacks the person rather than the idea ('that's a naive take', "
        "'you clearly didn't read it').",
    },
    # --- Bureaucratic-drift signals (the tenure problem) -------------------
    "gatekeeping": {
        "polarity": "disrespectful",
        "definition": "Blocks with process/territory instead of enabling "
        "('not my job', 'that's not the process', 'you'll have to file a ticket').",
    },
    "enabling": {
        "polarity": "respectful",
        "definition": "Offers a path forward ('here's how we can', 'let me unblock you').",
    },
}

RESPECTFUL = {b for b, v in BEHAVIORS.items() if v["polarity"] == "respectful"}
DISRESPECTFUL = {b for b, v in BEHAVIORS.items() if v["polarity"] == "disrespectful"}


# Named signals (PRODUCT.md §4) — the plain-English metrics an enterprise reads,
# built from the observable behaviors above. Each signal is a *balance* between a
# respectful form and its disrespectful counterpart: the value is
# positive / (positive + contrast), so it answers a real question ("when people
# disagree, how often do they attack the idea instead of the person?") rather than
# dumping raw counts. A signal with no `contrast` is a *presence* signal — reported
# as an occurrence count, never as an accusation (the legal framing of "credit").
# A behavior may inform more than one signal; these are distinct lenses, not a
# partition.
SIGNALS = [
    {
        "name": "Disagreeing with dignity",
        "question": "When pushing back, is it the idea that's challenged, or the person?",
        "positive": {"disagree_with_dignity"},
        "contrast": {"dismissiveness", "personal_attack"},
    },
    {
        "name": "Enabling over gatekeeping",
        "question": "When process or territory comes up, do people unblock or block?",
        "positive": {"enabling"},
        "contrast": {"gatekeeping"},
    },
    {
        "name": "Listening over dismissing",
        "question": "Do people build on what others said, or minimize it?",
        "positive": {"acknowledgment", "question_asking", "invites_others"},
        "contrast": {"dismissiveness"},
    },
    {
        "name": "Credit & attribution",
        "question": "Is whose idea it was acknowledged? (presence — never an accusation)",
        "positive": {"credit_attribution"},
        "contrast": set(),
    },
]

# Fail loudly if a signal ever references a behavior that isn't in the rubric —
# the two must not drift apart.
for _sig in SIGNALS:
    for _b in _sig["positive"] | _sig["contrast"]:
        assert _b in BEHAVIORS, f"signal {_sig['name']!r} references unknown behavior {_b!r}"


def system_prompt() -> str:
    lines = [
        "You are SugApp's Respect & Listening scorer. You analyze workplace chat messages "
        "for OBSERVABLE communication behaviors only.",
        "",
        "Hard rules:",
        "- Score only what was written. NEVER infer personality, intelligence, intent, or "
        "emotional state. No trait or emotion labels.",
        "- Every finding MUST quote the exact text it came from (the `evidence`).",
        "- A message may have zero, one, or several findings. Most ordinary messages have none.",
        "- For each disrespectful finding, give a concrete `coaching_rewrite`: the same point "
        "made respectfully. For respectful findings, `coaching_rewrite` may be an empty string.",
        "",
        "The behaviors you may report (use these exact keys):",
    ]
    for name, v in BEHAVIORS.items():
        lines.append(f"- {name} [{v['polarity']}]: {v['definition']}")
    return "\n".join(lines)


# JSON schema for structured output — guarantees parseable, on-rubric results.
FINDINGS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["findings"],
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "message_index",
                    "author",
                    "behavior",
                    "polarity",
                    "evidence",
                    "coaching_rewrite",
                    "rationale",
                ],
                "properties": {
                    "message_index": {"type": "integer"},
                    "author": {"type": "string"},
                    "behavior": {"type": "string", "enum": list(BEHAVIORS.keys())},
                    "polarity": {"type": "string", "enum": ["respectful", "disrespectful"]},
                    "evidence": {"type": "string"},
                    "coaching_rewrite": {"type": "string"},
                    "rationale": {"type": "string"},
                },
            },
        }
    },
}
