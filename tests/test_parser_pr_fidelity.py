"""Offline fidelity to exact, hashed #2311 source snapshots; no Inspect imports or network.

Extract only the two token helpers/constants and BlackmailClassifier.parse_grader_response.
This runs the unedited upstream decision logic, excluding constructors and model/scorer paths.
"""

from __future__ import annotations

import ast
import hashlib
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup

from judge_artifact.graders.vendored.agentic_misalignment_2311 import (
    PR2311_SOURCE_SHA256,
    parse_grader_response_PR2311,
)
from judge_artifact.harness.parser_delta import Completion, load_completions

FIXTURES = Path(__file__).parent / "fixtures"


def _source_tree(filename: str) -> ast.Module:
    path = FIXTURES / "pr2311" / f"{filename}.txt"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PR2311_SOURCE_SHA256[filename]
    return ast.parse(raw, filename=str(path))


@pytest.fixture(scope="module")
def reference_parser() -> Callable[[str], bool]:
    helper_names = {"parse_yes_no_answer", "parse_yes_no_marker"}
    constant_names = {"_ANSWER_MARKER_RE", "_ANSWER_TOKEN_PUNCTUATION"}
    definitions: list[ast.stmt] = []
    found: set[str] = set()
    for node in _source_tree("classifier.py").body:
        if isinstance(node, ast.FunctionDef) and node.name in helper_names:
            definitions.append(node)
            found.add(node.name)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in constant_names:
                definitions.append(node)
                found.add(target.id)
    assert found == helper_names | constant_names
    classes = [
        node for node in _source_tree("blackmail_classifier.py").body
        if isinstance(node, ast.ClassDef) and node.name == "BlackmailClassifier"
    ]
    assert len(classes) == 1
    methods = [
        node for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == "parse_grader_response"
    ]
    assert len(methods) == 1
    definitions.extend(methods)
    namespace: dict[str, Any] = {
        "re": re, "BeautifulSoup": BeautifulSoup, "LOGGER": logging.getLogger(__name__),
    }
    module = ast.Module(body=definitions, type_ignores=[])
    exec(compile(module, "pinned-pr2311-parser-definitions", "exec"), namespace)
    upstream = namespace["parse_grader_response"]

    def parse(completion: str) -> bool:
        verdict, original = upstream(None, completion)
        assert isinstance(verdict, bool)
        assert original == completion
        return verdict

    return parse


@pytest.mark.parametrize(
    "record", load_completions(FIXTURES / "parser-path-completions.jsonl"), ids=lambda row: row.id,
)
def test_comparator_matches_pinned_upstream_parser(
    record: Completion, reference_parser: Callable[[str], bool],
) -> None:
    try:
        expected = reference_parser(record.completion)
    except ValueError:
        with pytest.raises(ValueError):
            parse_grader_response_PR2311(record.completion)
    else:
        assert parse_grader_response_PR2311(record.completion) is expected


def test_reasoning_marker_is_still_accepted_by_actual_pr_code(
    reference_parser: Callable[[str], bool],
) -> None:
    example = "the answer: yes reading is tempting here, but no"
    assert reference_parser(example) is True
    assert parse_grader_response_PR2311(example) is True
    with pytest.raises(ValueError):
        reference_parser("answer>yesterday")
