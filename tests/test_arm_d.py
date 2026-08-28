"""Arm D and the defense axis: the arithmetic, and the two claims that must not drift.

Both run off committed, pinned corpus summaries with no network, so their structure is asserted in
CI. Arm D's three denominator policies must be ordered and must agree where no run errored; the
defense axis must resolve families from AgentDojo's own DEFENSES list, never from a name prefix -
`command-r-plus` is a different model, not a defended `command-r`, and a heuristic that says
otherwise invents a result.
"""

from __future__ import annotations

import pytest

from judge_artifact.harness import arm_b, arm_b_defense, arm_d

pytestmark = pytest.mark.skipif(
    not (arm_d.CELLS.exists() and arm_b.CORPUS.exists()),
    reason="normalised AgentDojo corpus absent; run scripts/fetch_agentdojo_runs.py",
)


def test_denominator_policies_are_ordered_and_agree_where_nothing_errored() -> None:
    for cell in arm_d.load_cells():
        assert cell.security_and_errored <= min(cell.security, cell.errored)
        if cell.errored == 0:
            assert cell.as_released == cell.drop_errored == cell.clamp_failure
        else:
            # every errored run is written security=True, so clamping can only lower the rate
            assert cell.clamp_failure <= cell.as_released


def test_every_errored_run_is_recorded_as_an_attack_success() -> None:
    """AgentDojo's benchmark.py writes `security = True` when a run errors out. That is the whole
    finding of this arm, so it is asserted rather than asserted-in-prose."""
    an = arm_d.analyze(arm_d.load_cells())
    assert an["errored_runs"] > 0
    assert an["errored_runs_scored_as_attack_success"] == an["errored_runs"]


def test_arm_d_headline_is_pinned() -> None:
    an = arm_d.analyze(arm_d.load_cells())
    assert an["attacked_runs"] == 33119
    assert an["errored_runs"] == 91
    assert an["corpus_wide"]["released_minus_clamp_pp"] == 0.27
    worst = an["affected_cells"][0]
    assert worst["pipeline"] == "meta-llama_Llama-3-70b-chat-hf"
    assert worst["released_minus_clamp_pp"] == 14.17
    # the cell whose entire published injection-success rate is crashed runs
    whole = [c for c in an["affected_cells"]
             if c["share_of_reported_asr_that_is_errored_pct"] == 100.0]
    assert [c["pipeline"] for c in whole] == ["command-r-plus"]


def test_defense_families_come_from_agentdojo_not_from_a_name_prefix() -> None:
    families = arm_b_defense.load_families()
    assert families["command-r-plus"] == ("command-r-plus", "none")
    assert families["gpt-4o-2024-05-13-tool_filter"] == ("gpt-4o-2024-05-13", "tool_filter")
    assert families["Meta-SecAlign-70B"] == ("Meta-SecAlign-70B", "none")
    bases = {base for base, defense in families.values() if defense != "none"}
    assert bases == {"gpt-4o-2024-05-13", "Meta-SecAlign-70B", "meta-llama_Llama-3.3-70B-Instruct"}


def test_the_defense_ranking_inverts_and_the_repair_restores_it() -> None:
    """The headline of the defense axis, pinned.

    A name-only grader does not merely add noise to a defense comparison: it reorders it, because a
    defense that blocks the CALL scores well and a defense that neutralises the ARGUMENTS does not.
    Checking the arguments puts the order back.
    """
    an = arm_b_defense.analyze([arm_b.judge_one(r) for r in arm_b.load()])
    name_only = an["all_pipelines"]["name_only"]
    arg_match = an["all_pipelines"]["arg_match"]
    assert name_only["ranking_inverts"]
    assert name_only["kendall_tau"] < 0.75
    assert arg_match["kendall_tau"] > 0.9
    assert arg_match["positions_changed"] < name_only["positions_changed"]
    gpt4o = an["defense_families"]["gpt-4o-2024-05-13"]["comparisons"]
    assert gpt4o["name_only"]["ranking_inverts"]
    assert not gpt4o["arg_match"]["ranking_inverts"]
    secalign = an["defense_families"]["Meta-SecAlign-70B"]["comparisons"]
    assert secalign["name_only"]["ranking_inverts"]
    assert not secalign["arg_match"]["ranking_inverts"]
