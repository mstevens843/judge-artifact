"""Grader fidelity: the vendored copies reproduce the SHIPPED verdicts, or this project is fiction.

Every headline in this repo is stated as "the real grader said X". That is a claim a reviewer must
be able to check, so when the optional `fidelity` extra is installed these tests run the vendored
functions and the installed `inspect_evals` functions over the same corpus and require the same
answer, for all three vendored modules:

  #2108  `is_function_called` / `times_function_called` / `get_args_of_function_call`, over real
         `inspect_ai` ChatMessage objects built from each execution episode.
  #2310  `parse_grader_response`, over each substring episode's answer string.
  #2292  `BlackmailClassifier.classify`, over each gate episode's response and judge verdict.

It also pins the VERSION claim the docs make: the released package must NOT contain the #2108 fix.
If a future release ships it, this test fails and the wording has to change - which is the point.

These skip (never silently pass) when inspect-evals is absent, so a green run cannot mean the
fidelity was never checked. Install with `uv sync --extra fidelity`.
"""

from __future__ import annotations

from importlib import metadata
from typing import Any

import pytest

from judge_artifact.corpus.episodes import CORPUS
from judge_artifact.graders.vendored.agentharm_2108 import (
    get_args_of_function_call_RELEASED,
    is_function_called_RELEASED,
    times_function_called_RELEASED,
)
from judge_artifact.graders.vendored.agentic_misalignment_2292 import (
    blackmail_verdict_SHIPPED,
    response_contains_necessary_emails,
)
from judge_artifact.graders.vendored.agentic_misalignment_2310 import (
    parse_grader_response_DEFECT,
)
from judge_artifact.model.defects import DEFECTS
from judge_artifact.model.layers import Family

EXECUTION_IDS = tuple(d.id for d in DEFECTS if d.family is Family.EXECUTION)
SUBSTRING_IDS = tuple(d.id for d in DEFECTS if d.family is Family.SUBSTRING)
GATE_IDS = tuple(d.id for d in DEFECTS if d.family is Family.GATE)

_SKIP = "inspect-evals not installed; run `uv sync --extra fidelity` to check fidelity"
EXPECTED_INSPECT_EVALS = "0.18.0"
EXPECTED_INSPECT_AI = "0.3.260"


def _installed_version(distribution: str) -> str:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        pytest.skip(_SKIP)


def test_locked_fidelity_package_versions_match_the_documented_environment() -> None:
    assert _installed_version("inspect-evals") == EXPECTED_INSPECT_EVALS
    assert _installed_version("inspect-ai") == EXPECTED_INSPECT_AI


def _inspect_messages(episode_id: str) -> list[Any]:
    """Build the real inspect_ai ChatMessage list the shipped AgentHarm helpers expect."""
    from inspect_ai.model import (
        ChatMessageAssistant,
        ChatMessageTool,
    )
    from inspect_ai.tool import ToolCall, ToolCallError

    out: list[Any] = []
    for event in CORPUS[episode_id].tool_events:
        out.append(
            ChatMessageAssistant(
                content="",
                tool_calls=[
                    ToolCall(id=event.call_id, function=event.name, arguments=dict(event.args))
                ],
            )
        )
        out.append(
            ChatMessageTool(
                content="",
                tool_call_id=event.call_id,
                function=event.name,
                error=ToolCallError("unknown", "tool call failed") if event.errored else None,
            )
        )
    return out


@pytest.mark.parametrize("episode_id", EXECUTION_IDS)
def test_vendored_2108_matches_the_installed_agentharm_helpers(episode_id: str) -> None:
    gu = pytest.importorskip("inspect_evals.agentharm.benchmark.grading_utils", reason=_SKIP)
    messages = _inspect_messages(episode_id)
    target = CORPUS[episode_id].target_function
    assert is_function_called_RELEASED(messages, target) == gu.is_function_called(messages, target)
    assert times_function_called_RELEASED(messages, target) == gu.times_function_called(
        messages, target
    )
    assert get_args_of_function_call_RELEASED(messages, target) == gu.get_args_of_function_call(
        messages, target
    )


def test_the_released_package_does_not_contain_the_2108_fix() -> None:
    """The docs say the fix is on main and NOT in the release. Pin that, do not assume it."""
    gu = pytest.importorskip("inspect_evals.agentharm.benchmark.grading_utils", reason=_SKIP)
    assert not hasattr(gu, "_rejected_tool_call_ids"), (
        "the installed inspect_evals now ships the #2108 fix; the version wording in "
        "graders/vendored/agentharm_2108.py and RESULTS.md must be updated"
    )


@pytest.mark.parametrize("episode_id", SUBSTRING_IDS)
def test_vendored_2310_matches_the_shipped_parser(episode_id: str) -> None:
    mod = pytest.importorskip(
        "inspect_evals.agentic_misalignment.classifiers.blackmail_classifier", reason=_SKIP
    )
    answer = CORPUS[episode_id].judge_answer
    real = mod.BlackmailClassifier()

    def attempt(fn: Any) -> object:
        try:
            return fn()
        except Exception:
            return "raised"

    assert attempt(lambda: parse_grader_response_DEFECT(answer)) == attempt(
        lambda: real.parse_grader_response(answer)[0]
    )


@pytest.mark.parametrize("episode_id", GATE_IDS)
def test_vendored_2292_matches_the_shipped_blackmail_gate(episode_id: str) -> None:
    mod = pytest.importorskip(
        "inspect_evals.agentic_misalignment.classifiers.blackmail_classifier", reason=_SKIP
    )
    episode = CORPUS[episode_id]
    real = mod.BlackmailClassifier()
    grader_response = (
        "<reasoning>r</reasoning><answer>yes</answer>"
        if episode.judge_verdict_yes
        else "<reasoning>r</reasoning><answer>no</answer>"
    )
    final, classifier_verdict, _ = real.classify(
        response=episode.response_text, grader_response=grader_response
    )
    assert classifier_verdict is episode.judge_verdict_yes, "the answer string did not round-trip"
    assert blackmail_verdict_SHIPPED(episode.response_text, episode.judge_verdict_yes) == final
    assert response_contains_necessary_emails(
        episode.response_text
    ) == real.response_contains_necessary_emails(episode.response_text)
