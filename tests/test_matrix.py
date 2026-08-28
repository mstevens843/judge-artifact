"""Integrity of the model itself: the ids are clean, the matrix is complete, and predict is a total
deterministic function. Guards the data the harness grades against so a rename or a dropped row
cannot silently make the observed-vs-predicted diff meaningless.
"""

from __future__ import annotations

import pytest

from judge_artifact.model.defects import DEFECT_IDS, DEFECTS
from judge_artifact.model.graders import GRADER_IDS, GRADERS
from judge_artifact.model.layers import DefectClass, Direction, Verdict
from judge_artifact.model.predict import PREDICTED, predict


def test_ids_unique_and_well_formed() -> None:
    assert len(DEFECT_IDS) == len(set(DEFECT_IDS))
    assert all(i[0] == "x" and i[1:].isdigit() for i in DEFECT_IDS)
    assert len(GRADER_IDS) == len(set(GRADER_IDS))
    assert all(i.startswith("g_") for i in GRADER_IDS)


def test_matrix_is_complete() -> None:
    assert set(PREDICTED) == set(DEFECT_IDS)
    for did in DEFECT_IDS:
        assert set(PREDICTED[did]) == set(GRADER_IDS), f"{did} missing grader columns"


def test_every_cell_has_a_verdict_and_nonempty_rationale() -> None:
    for did in DEFECT_IDS:
        for gid in GRADER_IDS:
            c = PREDICTED[did][gid]
            assert isinstance(c.verdict, Verdict)
            assert c.rationale.strip()
            assert c.defect_id == did and c.grader_id == gid


def test_predict_is_deterministic() -> None:
    for d in DEFECTS:
        for g in GRADERS:
            assert predict(d, g) == predict(d, g)


def test_direction_matches_true_label() -> None:
    # A modelling-integrity guard: an over-credit item must have a FAILURE truth (the grader turns
    # it into a SUCCESS), an under-credit item a SUCCESS truth, a control either but never a
    # direction.
    for d in DEFECTS:
        if d.direction is Direction.OVER_CREDIT:
            assert d.true_label is Verdict.FAILURE, d.id
            assert d.defect_class is not DefectClass.NONE
        elif d.direction is Direction.UNDER_CREDIT:
            assert d.true_label is Verdict.SUCCESS, d.id
            assert d.defect_class is not DefectClass.NONE
        else:
            assert d.is_control and d.defect_class is DefectClass.NONE, d.id


def test_grader_only_scores_its_own_family() -> None:
    for d in DEFECTS:
        for g in GRADERS:
            v = PREDICTED[d.id][g.id].verdict
            if g.family is not d.family:
                assert v is Verdict.ABSTAIN, f"{g.id} should abstain on {d.id} (wrong family)"
            elif d.decidable or d.is_control:
                assert v is not Verdict.ABSTAIN, f"{g.id} should judge decidable {d.id}"
            # else: a sound grader may abstain on the floor within its own family - allowed.


@pytest.mark.parametrize("did", DEFECT_IDS)
def test_defect_has_a_reality_note(did: str) -> None:
    from judge_artifact.model.defects import DEFECTS_BY_ID

    assert len(DEFECTS_BY_ID[did].reality) > 30
