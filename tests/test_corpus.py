"""THE MOST IMPORTANT EMPIRICAL TEST (and it runs in CI).

Arm A is fully deterministic - the real vendored graders over a constructed corpus, no network, no
model - so the observed matrix can be asserted against the prediction here, every run. This is the
judge-artifact analogue of cheat-oracle's discrimination test, except it needs no container: it runs
the shipped grader logic and requires that it reproduces the model, that both over- and under-credit
are exhibited in every family, that the controls all agree, and that the floor items are recovered
by no deterministic grader.
"""

from __future__ import annotations

from judge_artifact.corpus.episodes import CORPUS
from judge_artifact.graders.registry import grade
from judge_artifact.model.defects import DEFECTS
from judge_artifact.model.graders import GRADERS
from judge_artifact.model.layers import Direction, Family, Verdict
from judge_artifact.model.predict import PREDICTED


def _observe(defect_id: str, grader):  # type: ignore[no-untyped-def]
    d = next(x for x in DEFECTS if x.id == defect_id)
    if grader.family is not d.family:
        return Verdict.ABSTAIN
    return grade(grader.id, CORPUS[defect_id])


def test_every_defect_has_an_episode() -> None:
    assert set(CORPUS) == {d.id for d in DEFECTS}


def test_real_graders_reproduce_the_prediction() -> None:
    # The payoff of modelling first: the shipped grader logic matches the model on every cell.
    for d in DEFECTS:
        for g in GRADERS:
            observed = _observe(d.id, g)
            predicted = PREDICTED[d.id][g.id].verdict
            assert observed is predicted, (
                f"{g.id} on {d.id}: predicted {predicted.value}, observed {observed.value}"
            )


def test_controls_all_agree_empirically() -> None:
    for d in DEFECTS:
        if not d.is_control:
            continue
        for g in GRADERS:
            if g.family is d.family:
                assert _observe(d.id, g) is d.true_label


def test_both_directions_are_exhibited_in_every_family() -> None:
    # Over-credit AND under-credit are actually produced by the real graders in each family.
    for fam in (Family.EXECUTION, Family.SUBSTRING, Family.GATE):
        over = under = False
        for d in DEFECTS:
            if d.family is not fam:
                continue
            for g in GRADERS:
                if g.family is not fam:
                    continue
                got = _observe(d.id, g)
                if got is Verdict.SUCCESS and d.true_label is Verdict.FAILURE:
                    over = True
                if got is Verdict.FAILURE and d.true_label is Verdict.SUCCESS:
                    under = True
        assert over, f"{fam.value}: no over-credit observed"
        assert under, f"{fam.value}: no under-credit observed"


def test_floor_items_are_recovered_by_no_deterministic_grader() -> None:
    for d in DEFECTS:
        if d.decidable:
            continue
        assert d.direction is Direction.UNDER_CREDIT
        for g in GRADERS:
            if g.family is d.family:
                assert _observe(d.id, g) is not d.true_label, f"{g.id} recovered floor {d.id}"
