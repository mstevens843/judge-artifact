"""The neutral judged-episode representation, and adapters into it.

WHAT THIS IS. A grader-agnostic view of one judged episode carrying, in one shape, everything the
three grader families read: the tool-call log with each call's arguments and whether its tool
response errored (execution family), a harm-judge answer string (substring family), and the model's
full response together with the semantic classifier's verdict that the shipped gate ANDs against
(gate family).

WHY NEUTRAL. The shipped graders were written against inspect_ai's `ChatMessage` and against
agentic_misalignment's raw response strings. Rather than couple this project to those types, the
vendored grader functions are handed exactly the minimal shape they read (see ``graders/vendored/``)
and this module builds that shape from either source. That is what lets Arm A (constructed
episodes) and Arm B (4,000 released AgentDojo transcripts) run the SAME grader functions.

TWO ADAPTERS, ONE SHAPE. ``from_agentdojo_run`` reads a raw AgentDojo run json and is what
``scripts/fetch_agentdojo_runs.py`` uses to normalise the corpus; ``episode_from_record`` reads one
line of that normalised corpus back. Arm B goes through both, so the headline number is produced by
the vendored grader functions over this representation and not by a re-implementation.

WHAT THIS IS NOT. It is not the pure model - it is allowed the standard library and is not covered
by the model purity contract. It performs no grading; it only represents and adapts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolEvent:
    """One tool call and the fate of its response."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""
    errored: bool = False          # the paired tool response carried an error
    response_text: str = ""


@dataclass(frozen=True)
class Episode:
    """One judged episode.

    Execution-family items populate the tool view; substring-family items populate `judge_answer`;
    gate-family items populate `response_text` and `judge_verdict_yes`.

    `target_function` names the tool the attacker needed, and `attacker_args` the arguments
    AgentDojo's own injection-task `ground_truth` says the attacker wanted it called with. Keys
    whose ground-truth value is a "$name" placeholder are omitted, never guessed.
    """

    id: str
    tool_events: tuple[ToolEvent, ...] = ()
    target_function: str = ""
    attacker_args: dict[str, Any] = field(default_factory=dict)
    effect_achieved: bool = False  # did the action actually achieve its effect (the true state)
    judge_answer: str = ""         # the harm judge's <answer>...</answer> string
    response_text: str = ""        # the model's full response, incl. its <tool_use:...> blocks
    judge_verdict_yes: bool = False  # the semantic classifier's verdict the shipped gate ANDs with


# --- adapters into the minimal message shape the vendored #2108 functions read ------------------


@dataclass(frozen=True)
class Call:
    function: str
    id: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class AssistantMsg:
    tool_calls: list[Call]
    role: str = "assistant"


@dataclass(frozen=True)
class ToolMsg:
    tool_call_id: str
    function: str
    error: object | None
    role: str = "tool"


Message = AssistantMsg | ToolMsg


def to_messages(ep: Episode) -> list[Message]:
    """Build the assistant/tool message list the vendored AgentHarm helpers iterate. Each tool
    event becomes an assistant call followed by its tool response, whose `error` is set iff the
    call errored - exactly the pairing inspect_evals#2108 is about."""
    out: list[Message] = []
    for i, ev in enumerate(ep.tool_events):
        cid = ev.call_id or f"call_{i}"
        out.append(AssistantMsg(tool_calls=[Call(function=ev.name, id=cid, arguments=ev.args)]))
        out.append(ToolMsg(tool_call_id=cid, function=ev.name,
                           error=object() if ev.errored else None))
    return out


def tool_events_from_agentdojo_messages(msgs: list[dict[str, Any]]) -> tuple[ToolEvent, ...]:
    """Pair AgentDojo assistant `tool_calls` with the `tool` messages that answered them.

    AgentDojo emits an assistant message carrying N tool calls followed by N tool messages, in
    order, so a FIFO queue reproduces the pairing exactly. An assistant call with no tool message
    after it (a truncated or errored-out run) is kept as a call that did not error, because the
    transcript does not say that it did - the same conservative reading the shipped
    `_rejected_tool_call_ids` takes.
    """
    events: list[ToolEvent] = []
    pending: list[tuple[str, dict[str, Any], str]] = []
    # AgentDojo's released tool calls carry no `id`, so one is synthesised. It MUST be unique per
    # call: `_rejected_tool_call_ids` knocks out every call sharing an id, so a repeated fallback
    # id would let one errored call silently un-credit an unrelated successful one.
    seq = 0
    for m in msgs:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                fn = tc.get("function") or tc.get("name") or ""
                args = tc.get("args") or tc.get("arguments") or {}
                cid = str(tc.get("id") or f"c{seq}")
                seq += 1
                pending.append((str(fn), args if isinstance(args, dict) else {}, cid))
        elif role == "tool" and pending:
            fn, args, cid = pending.pop(0)
            events.append(ToolEvent(name=fn, args=args, call_id=cid,
                                    errored=m.get("error") is not None))
    for fn, args, cid in pending:
        events.append(ToolEvent(name=fn, args=args, call_id=cid, errored=False))
    return tuple(events)


def from_agentdojo_run(
    run: dict[str, Any],
    target_function: str,
    attacker_args: dict[str, Any] | None = None,
) -> Episode:
    """Adapt one raw AgentDojo run json into an Episode.

    `target_function` and `attacker_args` come from the injection task's own `ground_truth`,
    extracted by `scripts/fetch_agentdojo_runs.py`. `effect_achieved` is AgentDojo's released
    `security` verdict - the state oracle, which no grader under test is allowed to read.
    """
    return Episode(
        id=f"{run.get('pipeline_name', '?')}/{run.get('suite_name', '?')}/"
        f"{run.get('user_task_id', '?')}/{run.get('attack_type', '?')}/"
        f"{run.get('injection_task_id', '?')}",
        tool_events=tool_events_from_agentdojo_messages(run.get("messages", [])),
        target_function=target_function,
        attacker_args=dict(attacker_args or {}),
        effect_achieved=bool(run.get("security", False)),
    )


def episode_from_record(
    record: dict[str, Any], attacker_args: dict[str, Any] | None = None
) -> Episode:
    """Rebuild an Episode from one line of the normalised corpus written by the fetch script."""
    events = tuple(
        ToolEvent(
            name=str(e["name"]),
            args=dict(e.get("args") or {}),
            call_id=str(e.get("call_id") or ""),
            errored=bool(e.get("errored")),
        )
        for e in record.get("tool_events", [])
    )
    return Episode(
        id=str(record["id"]),
        tool_events=events,
        target_function=str(record.get("target_function") or ""),
        attacker_args=dict(attacker_args or record.get("attacker_args") or {}),
        effect_achieved=bool(record.get("security", False)),
    )
