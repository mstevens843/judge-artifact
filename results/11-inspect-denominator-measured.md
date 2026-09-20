# 11 - Arm D on Inspect: the #4286 limitation, removed

Working record, verified 2026-09-20. Until now this project said, in two places, that it could not measure Inspect's own
metric path end to end and so did not claim to. That was true when it was written and is no longer
true: the four reproductions in inspect_ai#4286 need a passthrough solver and `mockllm/model` - no
API key, no network, no judge - so they run here as a deterministic arm. Reproduce:

```
# against the locked fidelity environment (inspect-ai 0.3.260)
uv run --extra fidelity python -m judge_artifact.harness.arm_d_inspect \
  --out evidence/arm-d-inspect-locked.json

# against the current release (inspect-ai 0.3.266)
uv run --python 3.12 --isolated --with inspect-ai==0.3.266 --with-editable . \
  python -m judge_artifact.harness.arm_d_inspect --out evidence/arm-d-inspect.json
```

Receipts: `ja1_56462dcacd...` (0.3.260) and `ja1_8291962e64...` (0.3.266). The arm is deterministic -
two consecutive runs on the same release produce an identical receipt.

## The result

| probe | issue item | 0.3.260 | 0.3.266 |
|---|---|---|---|
| `errored_samples` | #4286(1) | PARTIAL | PARTIAL |
| `abstained_samples` | #4286(2) | PARTIAL | PARTIAL |
| `metric_range` | #4286(3) | **OPEN** | **OPEN** |
| `metric_agreement` | #4286(4) | FIXED | FIXED |
| `score_schema` | the live design question | **OPEN** | PARTIAL |

Verdicts are derived from what was observed, never from a table of versions, because this arm
tracks a moving upstream: a probe going OPEN -> FIXED is the result, not a regression.

**#4286(1), errored samples - PARTIAL.** Five of ten samples raise in the scorer; `fail_on_error`
tolerates it. The headline is still `status=success, accuracy=1.0`, exactly as filed. What has
changed is that the loss is now visible: `total_samples=10` against `completed_samples=5`. Note
where it is *not* visible - `scored_samples=5, unscored_samples=0`. An errored sample never
reaches the scorer, so it lands in neither coverage field; only the results-level pair reveals it.

**#4286(2), abstention - PARTIAL.** Three correct, two incorrect, five abstaining through the
public NaN sentinel. The headline is `0.6`, not `0.3`, still. Beside it now sit
`scored_samples=5, unscored_samples=5`, so a reader who looks can see the denominator is half the
dataset.

**#4286(3), no range bound - OPEN, reproduces exactly as filed.**

```
values [8, 5, 10]     -> accuracy 7.666666666666667   mean 7.666666666666667
values [1.0, 0.0, inf] -> accuracy inf                 mean inf
                          scored_samples 3   unscored_samples 0
```

The second line is the sharper half: `inf` is not `NaN`, so it passes the `math.isnan` unscored
filter and is counted as a **scored** sample contributing infinity to the headline.

Work has landed nearby without touching this: PR #4928 (merged 2026-08-31) made `value_to_float()`
map *custom numeric sentinels* to 1/0.5/0 instead of passing them through, and its own summary
notes that the old behaviour meant "accuracy can exceed 1". That closes the custom-sentinel route.
The general case above - a scorer on a rubric scale, or a single non-finite value - is untouched,
which is why it still reproduces. Searching open PRs for `clamp`, `value_to_float` and accuracy
bounds, and `docs/scorers.qmd` for a documented requirement that custom numeric scorers supply
their own metric, turned up nothing.

**#4286(4), `mean()` vs `accuracy()` - FIXED.** A scorer emitting the framework's own `CORRECT`
label with `[accuracy(), mean()]` attached now yields `accuracy 1.0, mean 1.0` and
`status=success`. `mean()` routes through `value_to_float()` instead of `Score.as_float()`, so
`float("C")` no longer raises at metric time.

## The probe that measures the argument, not a number

The fifth probe reads the schema, because that is what the issue is arguing about today: can a
downstream consumer tell a model failure from a scorer's chosen abstention? It has two halves with
two different answers, and the version contrast shows one of them moving.

On **0.3.260** the answer is no on both counts - there is no typed reason channel at all.

On **0.3.266** the per-sample half is solved:

```
Score.reason_is_a_typed_field: true
ScoreReason_values: ["invalid_response_format", "refusal", "no_response",
                     "grader_failed", "scoring_failed"]
```

That is a field on `Score`, not a metadata key, split exactly along model-under-test versus
measurement-instrument. It arrived in **PR #4629**, "First-class Score.reason and normalized
scorer failure policy" (MattFisher, merged 2026-08-26, closing #4567), and first shipped in
**0.3.261** - verified by running this arm against 0.3.260, which does not have it. The placement
question the issue debated in July is therefore settled, by the maintainer who proposed it, in the
direction the issue's author was still arguing for in September.

(An earlier draft of this note credited PR #4091. That is wrong: #4091 changed only `_math.py` and
its test, and *used* `Score.reason` rather than introducing it. The attribution was inferred from a
PR title and not checked against the diff until a later sweep - the same mistake class as the
probe bug below, caught the same way.)

The aggregate half is not:

```
EvalScore_coverage_fields: ["scored_samples", "unscored_samples"]
abstentions_counted_in_unscored_samples:   true
errored_samples_counted_in_unscored_samples: false
aggregate_channel_separates_them: false
```

The probe derives that last line rather than asserting it: in the errored run the per-scorer
buckets read `{scored_samples: 5, unscored_samples: 0}` against a ten-sample dataset, so five
samples are in no bucket at all. If a release adds a third bucket the sum reaches the dataset size
and the verdict flips - which is the only way an arm that watches a moving upstream can be trusted
to notice the movement. So
a consumer re-aggregating someone else's released results can recover the distinction per sample
and not from the summary - which is precisely the gap a three-bucket `ScoreStatus` would close. No
PR exists for it.

## A probe bug this caught, before it was published

The abstention probe was first written with `Score.unscored(reason="grader_failed")`. That keyword
does not exist before 0.3.261. On the locked 0.3.260 environment it raised *inside the scorer*, so
all five samples ERRORED rather than abstaining - and the probe reported a confident `OPEN` verdict
about a situation it had never constructed. The verdict was wrong in a way that looked entirely
plausible: a measurement of the errored path, labelled as a measurement of the abstention path.

Two changes followed. The probe now abstains with `Score(value=float("nan"))`, the public sentinel
the issue body itself names and which exists in every release. And every probe now asserts its own
premise through `_require()`: if the run did not produce the situation the probe claims to measure,
it raises instead of returning a verdict. `tests/test_arm_d_inspect.py` pins that guard.

The harness has corrected this project's own claims before - the gate corpus control in
[02](./02-model-and-arm-a.md), the Arm B attribution and the call-id collision in
[05](./05-arm-b-corrected.md), the rank-inversion null in [06](./06-agentdojo-defense-axis.md).
What is new here is where the wrong claim was heading: this one was written to be quoted in a
comment on the issue itself.

## What this does and does not claim

It claims: these five probes, on these two releases, observed exactly what is recorded above, and
`evidence/arm-d-inspect*.json` carries the numbers and the receipt.

It does not claim to be a survey of Inspect's metric layer. Five probes chosen to match one issue's
four reproductions plus its live design question is a narrow instrument, and a `PARTIAL` here means
"the specific behaviour the issue describes still occurs, with the counts now reported beside it" -
not a judgement that the maintainers chose wrongly. `--fail-on-error` and `--score-on-error` are
documented controls that bound item 1 for a user who sets them, as the maintainer noted on the
issue; this arm measures the default path.

Arm D on AgentDojo ([07](./07-error-denominator.md)) is unchanged and remains the measurement with
the larger corpus behind it. What this note adds is that the same defect no longer has to be argued
by analogy: it is now measured on the framework it was filed against.
