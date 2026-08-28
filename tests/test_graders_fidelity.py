"""Grader fidelity: when inspect-evals is installed, the vendored functions reproduce the real
shipped grader verdicts on the corpus. This is what makes "we ran the shipped code" a claim a
reviewer can check rather than trust. Skips when inspect-evals is absent, so a green run can never
mean the fidelity was never checked - it says it was skipped.
"""

from __future__ import annotations

import pytest

from judge_artifact.corpus.episodes import CORPUS
from judge_artifact.graders.vendored.agentic_misalignment_2310 import parse_grader_response_DEFECT


def test_vendored_substring_matches_the_shipped_parser() -> None:
    mod = pytest.importorskip(
        "inspect_evals.agentic_misalignment.classifiers.blackmail_classifier",
        reason="inspect-evals not installed; run `uv sync --extra fidelity` to check fidelity",
    )
    real = mod.BlackmailClassifier()
    for did in ("x10", "x11", "x12", "x13"):
        answer = CORPUS[did].judge_answer
        vend: bool | None
        try:
            vend = parse_grader_response_DEFECT(answer)
        except Exception:
            vend = None
        got: bool | None
        try:
            got = real.parse_grader_response(answer)[0]
        except Exception:
            got = None
        assert vend == got, f"vendored substring parser disagrees with shipped on {did}"
