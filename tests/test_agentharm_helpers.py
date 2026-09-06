"""Offline regression for #2108's different args/response traversal directions."""

from dataclasses import replace
from types import SimpleNamespace

from judge_artifact.graders.vendored.agentharm_2108 import (
    get_args_of_function_call_RELEASED,
    get_response_of_function_call_RELEASED,
)
from judge_artifact.transcript import Episode, ToolEvent, to_messages
from tests.regression_cases import PAIRING_EPISODE


def test_repeated_calls_return_arguments_and_response_from_different_attempts() -> None:
    messages = to_messages(PAIRING_EPISODE)
    first, second = PAIRING_EPISODE.tool_events
    assert first.call_id != second.call_id
    assert get_args_of_function_call_RELEASED(messages, "send_money") == second.args
    assert get_response_of_function_call_RELEASED(messages, "send_money") == first.response_text
    assert get_response_of_function_call_RELEASED(messages, "send_money") != second.response_text


def test_single_call_returns_its_own_args_and_response() -> None:
    event = PAIRING_EPISODE.tool_events[0]
    messages = to_messages(replace(PAIRING_EPISODE, tool_events=(event,)))
    assert get_args_of_function_call_RELEASED(messages, event.name) == event.args
    assert get_response_of_function_call_RELEASED(messages, event.name) == event.response_text


def test_response_lookup_skips_other_functions_and_returns_empty_when_absent() -> None:
    event = ToolEvent("other", response_text="unrelated response")
    messages = to_messages(Episode("other-call", tool_events=(event,)))
    assert get_response_of_function_call_RELEASED(messages, "send_money") == ""
    assert get_response_of_function_call_RELEASED([], "send_money") == ""
    messages.extend(to_messages(PAIRING_EPISODE))
    assert get_response_of_function_call_RELEASED(messages, "send_money") == "response A"


def test_released_response_lookup_does_not_skip_errored_response() -> None:
    first, second = PAIRING_EPISODE.tool_events
    episode = replace(PAIRING_EPISODE, tool_events=(replace(first, errored=True), second))
    messages = to_messages(episode)
    assert get_response_of_function_call_RELEASED(messages, "send_money") == "response A"


def test_response_content_is_returned_without_string_coercion() -> None:
    content = [{"type": "text", "text": "response A"}]
    message = SimpleNamespace(role="tool", function="send_money", content=content)
    assert get_response_of_function_call_RELEASED([message], "send_money") is content
