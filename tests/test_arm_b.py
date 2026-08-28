"""Arm B's invariants and its headline, asserted over the committed corpus in CI.

Arm B is fully deterministic - 3,986 released transcripts on disk, the vendored grader functions,
no network and no model - so its structure and its numbers can be pinned here rather than trusted.
Two things are checked: that the decomposition is a real partition (the finding is arithmetic, not
narrative), and that the ladder is monotone per run. Then the published numbers are pinned, so a
change to the matcher, the adapter or the corpus that moves a headline fails the suite instead of
quietly rewriting RESULTS.md.
"""

from __future__ import annotations

import pytest

from judge_artifact.harness import arm_b

pytestmark = pytest.mark.skipif(
    not arm_b.CORPUS.exists(),
    reason="normalised AgentDojo corpus absent; run scripts/fetch_agentdojo_runs.py",
)


@pytest.fixture(scope="module")
def judged() -> list[arm_b.Judged]:
    return [arm_b.judge_one(record) for record in arm_b.load()]


def test_corpus_shape(judged: list[arm_b.Judged]) -> None:
    assert len(judged) == 3986
    assert len({r.pipeline for r in judged}) == 28


def test_every_run_has_an_attacker_argument_to_match_on() -> None:
    # `args_match` with an empty spec matches everything, so a task that lost its attacker
    # arguments would silently turn the argument-checking judge back into the name-only judge.
    # `judge_one` refuses such a record; this asserts the corpus never contains one.
    for record in arm_b.load():
        assert record["attacker_args"], f"{record['id']} has no attacker arguments"


def test_the_ladder_is_monotone_on_every_single_run(judged: list[arm_b.Judged]) -> None:
    for row in judged:
        if row.verdicts["arg_match"]:
            assert row.verdicts["executed"], f"{row.id}: args matched but nothing executed"
        if row.verdicts["executed"]:
            assert row.verdicts["name_only"], f"{row.id}: executed but the name was never called"


def test_the_decomposition_is_a_partition(judged: list[arm_b.Judged]) -> None:
    over = [r for r in judged if r.verdicts["name_only"] and not r.sound]
    buckets = [r.bucket for r in over]
    assert all(buckets), "an over-credit landed in no bucket"
    assert {r.bucket for r in judged if not r.bucket} <= {""}
    counts = {b: buckets.count(b) for b in ("error_blind", "argument_blind", "effect_blind")}
    assert sum(counts.values()) == len(over), "buckets double-count or drop an over-credit"


def test_headline_numbers_are_pinned(judged: list[arm_b.Judged]) -> None:
    an = arm_b.analyze(judged)
    overall = an["overall"]
    assert overall["sound_asr"] == 0.2311
    assert overall["asr"] == {"name_only": 0.3971, "executed": 0.3758, "arg_match": 0.2594}
    assert an["over_credit"]["total"] == 672
    assert an["over_credit"]["buckets"] == {
        "error_blind": 83, "argument_blind": 464, "effect_blind": 125
    }
    # the argument check removes 464 false positives and adds ZERO false negatives: its misses are
    # exactly the ones the error check already had.
    under = an["under_credit"]
    assert under["executed"]["n"] == under["arg_match"]["n"] == 12
    assert under["name_only"]["n"] == 10
    assert set(under["executed"]["ids"]) == set(under["arg_match"]["ids"])
    # ...and the strict variant is the honest counter-example: it is far too strict to use
    assert under["arg_match_strict"]["n"] == 585


def test_error_blindness_is_nonzero_but_is_not_the_headline(judged: list[arm_b.Judged]) -> None:
    """The correction this project had to make to itself, kept as a test.

    An earlier version of Arm B attributed the whole gap to inspect_evals#2108. On a corpus that
    keeps arguments and errors, #2108's own mechanism is real but is the SMALLEST of the three
    buckets, and argument blindness dominates. If that ever flips, the prose must change too.
    """
    an = arm_b.analyze(judged)
    buckets = an["over_credit"]["buckets"]
    assert buckets["error_blind"] > 0, "no errored calls at all: the corpus lost its error field"
    assert buckets["argument_blind"] > buckets["error_blind"] + buckets["effect_blind"]
