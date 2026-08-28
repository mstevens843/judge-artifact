"""The neutral judged-episode representation, and adapters into it.

WHAT THIS IS. A grader-agnostic view of one judged episode, carrying both the features the
execution family reads (the tool-call log, each call's arguments, and whether its tool response
errored) and the features the text family reads (a harm-judge answer string, the full response, and
the action actually taken). Each corpus item and each real AgentDojo run is adapted into this shape,
so the same graders run over constructed exploits and released data alike.

WHY NEUTRAL. The shipped graders were written against inspect_ai's ChatMessage and against
agentic_misalignment's answer strings. Rather than couple the whole project to those types, the
vendored grader functions are handed exactly the minimal shape they read (see
``graders/vendored/``), and this module builds that shape from either source. That is what lets
Arm A (constructed) and Arm B (AgentDojo) share one set of graders.

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
    """One judged episode. Execution-family items populate the tool view; text-family items
    populate the text view. `target_function`/`target_args` name the action the attack wanted."""

    id: str
    tool_events: tuple[ToolEvent, ...] = ()
    target_function: str = ""
    target_args: dict[str, Any] = field(default_factory=dict)
    effect_achieved: bool = False  # did the action actually achieve its effect (the true state)
    judge_answer: str = ""         # the harm judge's <answer>...</answer> string
    response_text: str = ""        # the model's full response, for a whole-response gate
    action_text: str = ""          # the action actually taken, for an action-scoped gate
    gate_keyword: str = ""         # the keyword a gate looks for (the override code, "leverage")


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


def from_agentdojo_run(run: dict[str, Any], target_function: str) -> Episode:
    """Adapt one AgentDojo run json into an Episode. AgentDojo messages carry assistant
    `tool_calls` (with `function`) and `tool` messages with an `error` field; we pair them by
    order. The injection task's intended tool is passed as `target_function`."""
    events: list[ToolEvent] = []
    msgs = run.get("messages", [])
    pending: list[tuple[str, dict[str, Any], str]] = []
    for m in msgs:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                fn = tc.get("function") or tc.get("name") or ""
                args = tc.get("args") or tc.get("arguments") or {}
                cid = str(tc.get("id") or f"c{len(pending)}")
                pending.append((fn, args if isinstance(args, dict) else {}, cid))
        elif role == "tool":
            errored = m.get("error") is not None
            if pending:
                fn, args, cid = pending.pop(0)
                events.append(ToolEvent(name=fn, args=args, call_id=cid, errored=errored))
    # any assistant calls with no paired tool message: treat as not-errored calls
    for fn, args, cid in pending:
        events.append(ToolEvent(name=fn, args=args, call_id=cid, errored=False))
    return Episode(
        id=f"{run.get('suite_name','?')}/{run.get('user_task_id','?')}/"
        f"{run.get('injection_task_id','?')}/{run.get('attack_type','?')}",
        tool_events=tuple(events),
        target_function=target_function,
        effect_achieved=bool(run.get('security', False)),
    )
