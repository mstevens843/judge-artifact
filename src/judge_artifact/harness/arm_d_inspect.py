"""Arm D, on Inspect itself: re-run inspect_ai#4286's own reproductions against the release.

WHY THIS EXISTS. Arm D measures the denominator-policy defect on AgentDojo, because that is where
the policy is one readable branch in `benchmark.py`. That made the finding real but analogical: the
issue is filed against Inspect, and this project had to say it could not measure Inspect's own
metric path end to end. It can. The four reproductions in inspect_ai#4286 need no API key, no
network and no judge - a passthrough solver and `mockllm/model` - so they run here as a fifth
deterministic arm, and the claim becomes first-hand.

WHAT IT REPORTS. The issue makes four separate claims. Each is re-run and given a verdict derived
from what was OBSERVED, never from a table of versions:

  errored_samples    #4286(1)  a sample that errored leaves the accuracy denominator
  abstained_samples  #4286(2)  a scorer that returns the NaN/unscored sentinel leaves it too
  metric_range       #4286(3)  `accuracy()` is not clamped, so a headline can exceed 1 or be inf
  metric_agreement   #4286(4)  `mean()` and `accuracy()` disagree; `mean()` raised on C/I/P labels

  FIXED    the behaviour the issue describes no longer occurs
  PARTIAL  the headline still moves, but the result now carries the counts that reveal it
  OPEN     reproduces as filed

A fifth probe reads the SCHEMA rather than a number, because that is the live design question on
the issue today: can a downstream consumer tell a model failure from a scorer's chosen abstention?

DRIFT IS THE SIGNAL, NOT A REGRESSION. Every other arm here pins its numbers so a change fails the
build. This one cannot: the point is to track a moving upstream. So the evidence records the
`inspect_ai` version it ran against, and `tests/test_arm_d_inspect.py` pins the numbers only while
the installed version matches the recorded one, and asks for a re-run when it does not.

`uv run --extra fidelity python -m judge_artifact.harness.arm_d_inspect`
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..canonical import receipt

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = ROOT / "evidence" / "arm-d-inspect.json"

FIXED, PARTIAL, OPEN = "FIXED", "PARTIAL", "OPEN"


@dataclass
class Probe:
    """One reproduction, its observed numbers, and the verdict those numbers imply."""

    id: str
    issue_item: str
    title: str
    verdict: str
    observed: dict[str, Any] = field(default_factory=dict)
    note: str = ""


# --------------------------------------------------------------------------------------------
# the eval scaffolding: a passthrough solver over mockllm, so nothing is generated or judged
# --------------------------------------------------------------------------------------------


def _run(dataset_size: int, scorer_fn: Any) -> Any:
    """Run one throwaway eval and return its log. Logs go to a temp dir, never the working tree."""
    from inspect_ai import Task, eval
    from inspect_ai.dataset import Sample
    from inspect_ai.solver import solver

    @solver
    def passthrough() -> Any:
        async def solve(state: Any, generate: Any) -> Any:
            return state

        return solve

    task = Task(
        dataset=[
            Sample(input=f"q{i}", target="x", metadata={"idx": i}) for i in range(dataset_size)
        ],
        solver=passthrough(),
        scorer=scorer_fn,
    )
    with tempfile.TemporaryDirectory() as log_dir:
        return eval(
            task, model="mockllm/model", fail_on_error=0.9, display="none", log_dir=log_dir
        )[0]


def _jsonable(value: Any) -> Any:
    """Record a metric value in a form that survives a canonical-JSON receipt.

    `canonical.py` refuses non-finite floats on purpose, and JSON has no literal for them - but
    "the headline came out as infinity" IS the finding of one of these probes, so it is recorded
    as the string "inf" rather than dropped. Verdicts are computed from the real float first.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return "nan" if math.isnan(value) else ("inf" if value > 0 else "-inf")
    return value


def _require(condition: bool, message: str) -> None:
    """Fail loudly when a probe did not set up the situation it claims to measure.

    This exists because of a real miss during development: the abstention probe first used
    `Score.unscored(reason=...)`, whose `reason` keyword only exists from 0.3.261. On the locked
    0.3.260 environment that raised inside the scorer, so all five samples ERRORED rather than
    abstained, and the probe reported a confident verdict about a situation it had never created.
    A probe that cannot construct its own premise must stop, not publish.
    """
    if not condition:
        raise RuntimeError(f"arm_d_inspect probe precondition failed: {message}")


def _coverage(log: Any) -> dict[str, Any]:
    """The counts a reader would use to notice that samples went missing.

    `coverage_counts` collects EVERY `*_samples` bucket the per-scorer result carries rather than
    the two this project happens to know about, so that a release which adds a third bucket (the
    `ScoreStatus` follow-up the issue is asking for) is detected by this arm instead of silently
    matching an assumption baked in here.
    """
    score = log.results.scores[0]
    dumped = score.model_dump()
    coverage_counts = {
        k: v
        for k, v in sorted(dumped.items())
        if k.endswith("_samples") and isinstance(v, int) and not isinstance(v, bool)
    }
    return {
        "status": str(log.status),
        "total_samples": log.results.total_samples,
        "completed_samples": log.results.completed_samples,
        "scored_samples": score.scored_samples,
        "unscored_samples": score.unscored_samples,
        "coverage_counts": coverage_counts,
        "metrics": {name: _jsonable(m.value) for name, m in score.metrics.items()},
    }


# --------------------------------------------------------------------------------------------
# the four reproductions from the issue body
# --------------------------------------------------------------------------------------------


def probe_errored_samples() -> Probe:
    """#4286(1). Five of ten samples raise in the scorer; `fail_on_error` tolerates it."""
    from inspect_ai.scorer import CORRECT, Score, accuracy, scorer

    @scorer(metrics=[accuracy()])
    def flaky() -> Any:
        async def score(state: Any, target: Any) -> Score:
            if int(state.metadata["idx"]) >= 5:
                raise RuntimeError("judge/parse/sandbox error")
            return Score(value=CORRECT)

        return score

    obs = _coverage(_run(10, flaky()))
    _require(
        obs["total_samples"] == 10 and obs["completed_samples"] == 5,
        "the errored probe needs exactly five of ten samples to error; "
        f"got completed={obs['completed_samples']} of total={obs['total_samples']}",
    )
    acc = obs["metrics"].get("accuracy")
    # Every sample that survived was correct, so a headline of 1.0 means the five that errored
    # were never in the denominator.
    headline_ignores_errors = acc == 1.0
    errors_visible = (
        obs["total_samples"] is not None
        and obs["completed_samples"] is not None
        and obs["total_samples"] > obs["completed_samples"]
    )
    if not headline_ignores_errors:
        verdict, note = FIXED, "the headline accounts for the errored samples"
    elif errors_visible:
        verdict, note = (
            PARTIAL,
            "headline unchanged, but total_samples vs completed_samples reveals the loss; "
            "the errored samples reach neither coverage field on the score",
        )
    else:
        verdict, note = OPEN, "reproduces as filed: the errored samples leave no trace"
    obs["headline_ignores_errored_samples"] = headline_ignores_errors
    obs["errored_samples_visible_in_results"] = errors_visible
    obs["errored_samples_counted_as_unscored"] = bool(obs["unscored_samples"])
    return Probe("errored_samples", "#4286(1)",
                 "a sample that errored leaves the accuracy denominator", verdict, obs, note)


def probe_abstained_samples() -> Probe:
    """#4286(2). Three correct, two incorrect, five abstentions via the unscored sentinel."""
    from inspect_ai.scorer import CORRECT, INCORRECT, Score, accuracy, scorer

    @scorer(metrics=[accuracy()])
    def abstaining() -> Any:
        async def score(state: Any, target: Any) -> Score:
            idx = int(state.metadata["idx"])
            if idx >= 5:
                # The issue's own wording: NaN is reachable from the public API and is the
                # natural way a judge says "I could not decide". `Score.unscored()` is sugar over
                # it, and its `reason` keyword does not exist before 0.3.261 - using it here would
                # make this probe measure the errored path on older releases instead.
                return Score(value=float("nan"))
            return Score(value=CORRECT if idx < 3 else INCORRECT)

        return score

    obs = _coverage(_run(10, abstaining()))
    _require(
        obs["completed_samples"] == obs["total_samples"] == 10,
        "the abstention probe needs all ten samples to complete; "
        f"got completed={obs['completed_samples']} of total={obs['total_samples']}, "
        "which means the scorer raised rather than abstaining",
    )
    acc = obs["metrics"].get("accuracy")
    over_all, over_scored = 3 / 10, 3 / 5
    headline_excludes_abstentions = acc is not None and math.isclose(float(acc), over_scored)
    coverage_reported = bool(obs["unscored_samples"])
    if acc is not None and math.isclose(float(acc), over_all):
        verdict, note = FIXED, "abstentions are counted in the denominator"
    elif headline_excludes_abstentions and coverage_reported:
        verdict, note = (
            PARTIAL,
            "headline is 3/5 rather than 3/10, but scored_samples / unscored_samples "
            "now report the coverage beside it",
        )
    else:
        verdict, note = OPEN, "reproduces as filed: abstentions vanish with nothing reported"
    obs["accuracy_over_all_samples"] = round(over_all, 4)
    obs["accuracy_over_scored_samples"] = round(over_scored, 4)
    obs["headline_excludes_abstentions"] = headline_excludes_abstentions
    obs["coverage_reported"] = coverage_reported
    return Probe("abstained_samples", "#4286(2)",
                 "a scorer that abstains leaves the denominator too", verdict, obs, note)


def probe_metric_range() -> Probe:
    """#4286(3). A rubric on a 0..10 scale, and a single infinity."""
    from inspect_ai.scorer import Score, accuracy, mean, scorer

    def rubric(values: list[float]) -> Any:
        @scorer(metrics=[accuracy(), mean()])
        def _rubric() -> Any:
            async def score(state: Any, target: Any) -> Score:
                return Score(value=values[int(state.metadata["idx"])])

            return score

        return _rubric()

    unbounded = _coverage(_run(3, rubric([8, 5, 10])))
    infinite = _coverage(_run(3, rubric([1.0, 0.0, float("inf")])))
    for obs in (unbounded, infinite):
        _require(obs["completed_samples"] == 3,
                 "the range probe needs all three samples to complete; "
                 f"got completed={obs['completed_samples']}")
    acc_unbounded = float(unbounded["metrics"].get("accuracy", 0.0))
    acc_infinite = float(infinite["metrics"].get("accuracy", 0.0))
    exceeds_one = acc_unbounded > 1.0
    non_finite = not math.isfinite(acc_infinite)
    verdict = OPEN if (exceeds_one or non_finite) else FIXED
    note = (
        "no clamp and no finiteness check; infinity is not NaN, so it passes the unscored "
        "filter and is counted as a SCORED sample"
        if verdict == OPEN
        else "the metric is bounded at its boundary"
    )
    return Probe(
        "metric_range", "#4286(3)",
        "accuracy() is not range-bounded, so a headline can exceed 1 or be infinite", verdict,
        {
            "rubric_0_to_10": {"values": [8, 5, 10], **unbounded},
            "with_infinity": {"values": [1.0, 0.0, "inf"], **infinite},
            "accuracy_exceeds_one": exceeds_one,
            "accuracy_non_finite": non_finite,
            "infinity_counted_as_scored": infinite["unscored_samples"] == 0,
        },
        note,
    )


def probe_metric_agreement() -> Probe:
    """#4286(4). `accuracy()` and `mean()` attached to a scorer emitting the framework's own
    CORRECT label - the case where `mean()` used to raise ValueError at metric time."""
    from inspect_ai.scorer import CORRECT, Score, accuracy, mean, scorer

    @scorer(metrics=[accuracy(), mean()])
    def labels() -> Any:
        async def score(state: Any, target: Any) -> Score:
            return Score(value=CORRECT)

        return score

    obs = _coverage(_run(3, labels()))
    _require(obs["completed_samples"] == 3,
             "the agreement probe needs all three samples to complete; "
             f"got completed={obs['completed_samples']}")
    metrics = obs["metrics"]
    both_present = "accuracy" in metrics and "mean" in metrics
    both_finite = both_present and all(
        math.isfinite(float(metrics[k])) for k in ("accuracy", "mean")
    )
    agree = both_finite and math.isclose(float(metrics["accuracy"]), float(metrics["mean"]))
    verdict = FIXED if (obs["status"] == "success" and agree) else OPEN
    obs["both_metrics_present"] = both_present
    obs["metrics_agree"] = agree
    return Probe(
        "metric_agreement", "#4286(4)",
        "mean() and accuracy() disagree on the framework's own C/I/P labels", verdict, obs,
        "mean() now routes through value_to_float(), so the label no longer raises"
        if verdict == FIXED
        else "reproduces as filed: the run's scores are lost at metric time",
    )


# --------------------------------------------------------------------------------------------
# the schema probe: the live design question on the issue
# --------------------------------------------------------------------------------------------


def probe_score_schema(errored: Probe, abstained: Probe) -> Probe:
    """Can a downstream consumer tell a model failure from a scorer's chosen abstention?

    This is what the issue is arguing about now. It has two halves and they have different
    answers, which is the whole point of measuring it rather than asserting it.
    """
    import typing

    from inspect_ai.log import EvalScore
    from inspect_ai.scorer import Score, _metric

    # Read the symbol off the module rather than importing it by name: a release that predates
    # the typed reason channel simply does not have it, and "absent" is an observation this arm
    # exists to record, not an error it should die on.
    score_reason = getattr(_metric, "ScoreReason", None)
    reason_field = "reason" in Score.model_fields
    reason_values = list(typing.get_args(score_reason)) if score_reason is not None else []
    coverage_fields = sorted(f for f in EvalScore.model_fields if f.endswith("_samples"))
    # The sharp half, MEASURED rather than assumed: in the errored run, do the per-scorer buckets
    # account for every sample? Today scored=5 + unscored=0 against a ten-sample dataset, so the
    # five that errored are in no bucket at all. A release that adds an errored bucket makes the
    # buckets sum to the dataset, and this flips - which is the whole point of the probe.
    errored_counts: dict[str, int] = dict(errored.observed.get("coverage_counts", {}))
    errored_total = int(errored.observed.get("total_samples") or 0)
    aggregate_separates = bool(errored_counts) and sum(errored_counts.values()) == errored_total
    abstentions_counted = bool(abstained.observed.get("unscored_samples"))
    errors_counted = bool(errored.observed.get("errored_samples_counted_as_unscored"))
    per_sample_separates = reason_field and len(reason_values) > 1
    if not per_sample_separates:
        note_half = ("this release has no typed reason channel on Score, so a consumer cannot "
                     "separate them at all")
    else:
        note_half = ("per sample the typed Score.reason separates them; in aggregate "
                     "unscored_samples is a single undifferentiated count and errored samples "
                     "are in neither coverage field")
    verdict = FIXED if (per_sample_separates and aggregate_separates) else (
        PARTIAL if per_sample_separates else OPEN
    )
    return Probe(
        "score_schema", "#4286 design",
        "distinguishing a model failure from a scorer's chosen abstention", verdict,
        {
            "Score.reason_is_a_typed_field": reason_field,
            "ScoreReason_values": reason_values,
            "EvalScore_coverage_fields": coverage_fields,
            "abstentions_counted_in_unscored_samples": abstentions_counted,
            "errored_samples_counted_in_unscored_samples": errors_counted,
            "errored_run_coverage_counts": errored_counts,
            "errored_run_total_samples": errored_total,
            "per_sample_channel_separates_them": per_sample_separates,
            "aggregate_channel_separates_them": aggregate_separates,
        },
        note_half,
    )


# --------------------------------------------------------------------------------------------


def inspect_ai_version() -> str:
    import importlib.metadata

    return importlib.metadata.version("inspect-ai")


def run_probes() -> list[Probe]:
    errored = probe_errored_samples()
    abstained = probe_abstained_samples()
    return [
        errored,
        abstained,
        probe_metric_range(),
        probe_metric_agreement(),
        probe_score_schema(errored, abstained),
    ]


def analyze(probes: list[Probe]) -> dict[str, Any]:
    counts = {v: sum(1 for p in probes if p.verdict == v) for v in (OPEN, PARTIAL, FIXED)}
    return {
        "inspect_ai_version": inspect_ai_version(),
        "substrate": "mockllm/model with a passthrough solver: no API key, no network, no judge",
        "verdict_counts": counts,
        "probes": [asdict(p) for p in probes],
    }


def render(an: dict[str, Any]) -> str:
    lines = [
        f"Arm D on Inspect - inspect_ai#4286 re-run against inspect-ai {an['inspect_ai_version']}",
        f"substrate: {an['substrate']}",
        "",
        f"{'probe':20}{'issue':14}{'verdict':10}what was observed",
        "-" * 100,
    ]
    for p in an["probes"]:
        lines.append(f"{p['id']:20}{p['issue_item']:14}{p['verdict']:10}{p['title']}")
        lines.append(f"{'':44}{p['note']}")
    counts = an["verdict_counts"]
    lines += [
        "",
        f"OPEN {counts[OPEN]}   PARTIAL {counts[PARTIAL]}   FIXED {counts[FIXED]}",
        "",
        "Verdicts are derived from the observed numbers, not from a version table: this arm "
        "tracks a moving upstream, so drift is the signal rather than a regression.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="re-run inspect_ai#4286 against the installed release")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="evidence path")
    args = ap.parse_args(argv)
    if importlib.util.find_spec("inspect_ai") is None:
        raise SystemExit(
            "this arm runs against inspect_ai itself; install the fidelity extra, e.g.\n"
            "  uv run --extra fidelity python -m judge_artifact.harness.arm_d_inspect"
        )
    an = analyze(run_probes())
    record: dict[str, Any] = {
        "arm": "D-inspect",
        "source": "inspect_ai#4286 reproductions, run against the installed inspect-ai",
        "analysis": an,
    }
    record["receipt"] = receipt(record)
    print(render(an))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, sort_keys=True))
    print(f"\nreceipt: {record['receipt']}\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
