"""Arm D on Inspect: structure, preconditions, and version-matched pinning.

Every other arm here pins its numbers so that any drift fails the build. This one cannot, because
it deliberately tracks a moving upstream: a verdict changing from OPEN to FIXED is the result, not
a regression. So the pinning is conditional - each committed evidence file is checked only against
the `inspect-ai` release it was recorded on, and skips with an explicit "re-run the arm" message
otherwise. What IS pinned unconditionally is the shape: the probe set, the verdict vocabulary, and
that a probe which cannot construct its own premise raises instead of reporting.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip(
    "inspect_ai", reason="inspect-ai not installed; run `uv sync --extra fidelity`"
)

from judge_artifact.harness import arm_d_inspect as arm

EVIDENCE = [
    Path(__file__).resolve().parent.parent / "evidence" / name
    for name in ("arm-d-inspect.json", "arm-d-inspect-locked.json")
]

EXPECTED_PROBES = (
    "errored_samples",
    "abstained_samples",
    "metric_range",
    "metric_agreement",
    "score_schema",
)
VERDICTS = frozenset({arm.OPEN, arm.PARTIAL, arm.FIXED})


@pytest.fixture(scope="module")
def probes() -> list[arm.Probe]:
    return arm.run_probes()


def test_the_probe_set_is_the_four_issue_items_plus_the_schema(probes: list[arm.Probe]) -> None:
    assert tuple(p.id for p in probes) == EXPECTED_PROBES
    issue_items = {p.id: p.issue_item for p in probes}
    for n, pid in enumerate(EXPECTED_PROBES[:4], start=1):
        assert issue_items[pid] == f"#4286({n})", f"{pid} is not pinned to its issue item"


def test_every_probe_has_a_verdict_and_shows_its_working(probes: list[arm.Probe]) -> None:
    for p in probes:
        assert p.verdict in VERDICTS, f"{p.id} has verdict {p.verdict!r}"
        assert p.observed, f"{p.id} reports a verdict with nothing observed behind it"
        assert p.note.strip(), f"{p.id} has no note explaining the verdict"


def test_a_probe_that_cannot_build_its_premise_raises(probes: list[arm.Probe]) -> None:
    """The guard that caught a real mis-measurement during development.

    The abstention probe originally used `Score.unscored(reason=...)`, a keyword that only exists
    from 0.3.261. On the locked 0.3.260 environment it raised inside the scorer, so all five
    samples ERRORED rather than abstained and the probe published a confident verdict about a
    situation it had never created. `_require` makes that failure loud.
    """
    with pytest.raises(RuntimeError, match="precondition failed"):
        arm._require(False, "deliberate")
    arm._require(True, "must not raise")
    # and the premise really does hold in the run above
    abstained = next(p for p in probes if p.id == "abstained_samples")
    assert abstained.observed["completed_samples"] == abstained.observed["total_samples"] == 10


def test_the_range_probe_is_the_one_that_still_reproduces(probes: list[arm.Probe]) -> None:
    """#4286(3) has no clamp, no finiteness check, and no PR. If that changes, this fails and the
    comment made upstream has to be corrected."""
    rng = next(p for p in probes if p.id == "metric_range")
    assert rng.verdict == arm.OPEN, (
        "accuracy() is now range-bounded; RESULTS.md, results/11 and the #4286 comment all say "
        "it is not, and must be updated"
    )
    assert rng.observed["accuracy_exceeds_one"] and rng.observed["accuracy_non_finite"]


def test_the_aggregate_verdict_is_derived_from_the_result_not_hardcoded(
    probes: list[arm.Probe],
) -> None:
    """A drift-tracking arm must be able to notice the drift it is watching for.

    The schema probe first hardcoded `aggregate_separates = False` with a comment arguing that one
    count cannot carry two buckets. True of today's schema - but it made the probe unable to detect
    the three-bucket `ScoreStatus` follow-up the issue is asking for, which is the single change it
    exists to watch. It is now derived: do the per-scorer `*_samples` buckets account for every
    sample of the errored run? This pins that the derivation is real and reads live fields.
    """
    schema = next(p for p in probes if p.id == "score_schema")
    counts = schema.observed["errored_run_coverage_counts"]
    total = schema.observed["errored_run_total_samples"]
    assert counts, "no per-scorer sample buckets were read at all"
    assert total == 10, "the errored run should span the ten-sample dataset"
    expected = bool(counts) and sum(counts.values()) == total
    assert schema.observed["aggregate_channel_separates_them"] is expected
    # and the field list is read off the model, so a new bucket shows up here
    assert set(counts) <= set(schema.observed["EvalScore_coverage_fields"])


def test_receipts_quoted_in_the_lab_note_match_the_evidence() -> None:
    """A receipt written into prose is a number with no command behind it unless something checks.

    This note quoted two receipts that went stale the moment the arm's code changed, and nothing
    would have caught it: CI diffs `evidence/`, but no job reads the markdown. Every `ja1_` string
    in the note must now be a prefix of a receipt that is actually in an evidence file.
    """
    note = (Path(__file__).resolve().parent.parent / "results"
            / "11-inspect-denominator-measured.md").read_text()
    quoted = set(re.findall(r"ja1_[0-9a-f]+", note))
    assert quoted, "the note quotes no receipt at all"
    actual = [json.loads(path.read_text())["receipt"] for path in EVIDENCE if path.exists()]
    assert actual, "no evidence files to check against"
    for q in sorted(quoted):
        assert any(r.startswith(q) for r in actual), (
            f"{q} in results/11 matches no receipt in {[p.name for p in EVIDENCE]}; "
            "re-run the arm and update the note"
        )


@pytest.mark.parametrize("path", EVIDENCE, ids=[p.name for p in EVIDENCE])
def test_committed_evidence_matches_when_the_version_matches(
    path: Path, probes: list[arm.Probe]
) -> None:
    if not path.exists():
        pytest.skip(f"{path.name} not present")
    recorded: dict[str, Any] = json.loads(path.read_text())["analysis"]
    installed = arm.inspect_ai_version()
    if recorded["inspect_ai_version"] != installed:
        pytest.skip(
            f"{path.name} was recorded on inspect-ai {recorded['inspect_ai_version']}, "
            f"installed is {installed}; re-run "
            f"`python -m judge_artifact.harness.arm_d_inspect --out evidence/{path.name}`"
        )
    observed = arm.analyze(probes)
    assert observed["probes"] == recorded["probes"], (
        f"{path.name} no longer reproduces on the version it was recorded against"
    )
    assert observed["verdict_counts"] == recorded["verdict_counts"]
