"""Latest PyPI grader fidelity.

This is intentionally separate from ``test_graders_fidelity.py``. The locked path proves the
historical release claim against ``inspect-evals 0.18.0`` / ``inspect-ai 0.3.260``. This file checks
the current latest packages named in the docs and asserts the compatibility shape observed there:
the AgentHarm #2108 rejection filter is now shipped, while the #2310/#2292 copies still reproduce
the installed package behavior.
"""

from __future__ import annotations

from importlib import metadata
from typing import Any

import pytest

from judge_artifact.corpus.episodes import CORPUS
from judge_artifact.graders.vendored.agentharm_2108 import (
    get_args_of_function_call_MAIN_FIX,
    is_function_called_MAIN_FIX,
    times_function_called_MAIN_FIX,
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

EXPECTED_INSPECT_EVALS = "0.19.0"
EXPECTED_INSPECT_AI = "0.3.261"
_SKIP = (
    "latest fidelity requires `inspect-evals==0.19.0` and `inspect-ai==0.3.261`; "
    "run the documented isolated latest command"
)

EXECUTION_IDS = tuple(d.id for d in DEFECTS if d.family is Family.EXECUTION)
SUBSTRING_IDS = tuple(d.id for d in DEFECTS if d.family is Family.SUBSTRING)
GATE_IDS = tuple(d.id for d in DEFECTS if d.family is Family.GATE)


def _installed_version(distribution: str) -> str:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        pytest.skip(_SKIP)


def _require_latest_versions() -> None:
    inspect_evals = _installed_version("inspect-evals")
    inspect_ai = _installed_version("inspect-ai")
    if (inspect_evals, inspect_ai) != (EXPECTED_INSPECT_EVALS, EXPECTED_INSPECT_AI):
        pytest.skip(
            f"{_SKIP}; installed inspect-evals=={inspect_evals}, inspect-ai=={inspect_ai}"
        )


@pytest.fixture(autouse=True)
def latest_fidelity_versions() -> None:
    _require_latest_versions()


def _inspect_messages(episode_id: str) -> list[Any]:
    from inspect_ai.model import ChatMessageAssistant, ChatMessageTool
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


def test_latest_fidelity_package_versions_match_the_documented_environment() -> None:
    assert _installed_version("inspect-evals") == EXPECTED_INSPECT_EVALS
    assert _installed_version("inspect-ai") == EXPECTED_INSPECT_AI


@pytest.mark.parametrize("episode_id", EXECUTION_IDS)
def test_latest_agentharm_helpers_match_the_main_fix_copy(episode_id: str) -> None:
    gu = pytest.importorskip("inspect_evals.agentharm.benchmark.grading_utils", reason=_SKIP)
    messages = _inspect_messages(episode_id)
    target = CORPUS[episode_id].target_function
    assert is_function_called_MAIN_FIX(messages, target) == gu.is_function_called(messages, target)
    assert times_function_called_MAIN_FIX(messages, target) == gu.times_function_called(
        messages, target
    )
    assert get_args_of_function_call_MAIN_FIX(messages, target) == gu.get_args_of_function_call(
        messages, target
    )


def test_latest_package_contains_the_2108_fix() -> None:
    gu = pytest.importorskip("inspect_evals.agentharm.benchmark.grading_utils", reason=_SKIP)
    assert hasattr(gu, "_rejected_tool_call_ids")


@pytest.mark.parametrize("episode_id", SUBSTRING_IDS)
def test_latest_2310_matches_the_shipped_parser(episode_id: str) -> None:
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
def test_latest_2292_matches_the_shipped_blackmail_gate(episode_id: str) -> None:
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
