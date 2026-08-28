# Results

Verification record. Every number here was produced by running the command shown, on the toolchain
named below, and reading its output. Nothing is copied from an earlier run or from a summary of a
run. Where something is skipped, substrate-limited or unproven, it says so and says why. Where an
earlier version of this document was wrong, it says that too, and links to the note that corrects
it.

**Frozen:** 2026-08-28
**Toolchain:** Python 3.12.13, uv 0.11.26, pytest 9.1.1, ruff 0.16.5, mypy 2.3.1 (strict), all via
`uv run`. Fidelity checks against `inspect-evals 0.18.0` / `inspect-ai 0.3.260`.
**Graders:** the real shipped functions, vendored verbatim with their source and version, and
checked against the installed `inspect_evals` on every corpus episode.
**Corpus:** AgentDojo (MIT) at pinned commit `089ed468cf3ed0322acc66b0211f26d9d90dbf60`, normalised
by a committed producer, hashed in `data/agentdojo/MANIFEST.json`.
**Ground truth:** the effect an action achieved. For the constructed corpus that is true by
construction; for AgentDojo it is the released `security` oracle. Never the grader under test.

## Summary

| Gate | Result |
|---|---|
| `uv run pytest` | **94 passed** |
| `uv run ruff check .` / `uv run mypy` (strict, incl. `scripts/`) | clean |
| `uv run --extra fidelity pytest tests/test_graders_fidelity.py` | **16 passed** - vendored #2108, #2310 and #2292 reproduce the installed `inspect_evals` verdict on every episode |
| `uv run python -m judge_artifact.model` | 15 episodes x 8 graders, 3 families, pure derivation |
| Arm A - real graders over the constructed corpus | **0 predicted-vs-observed disagreements**; both directions in every family |
| Arm B - 3,986 released AgentDojo transcripts | a name-only success judge reports **+16.60 pp**; over-credit decomposes **12.4% error-blind / 69.0% argument-blind / 18.6% effect-blind** |
| Arm B defense axis - 28 pipelines | ranking **does** invert: Kendall tau **0.68**, 23 of 28 positions moved; adding the argument check restores it to **0.95** |
| Arm D - 33,119 attacked runs, denominator policy | corpus-wide **0.27 pp**; one published cell is **100%** crashed runs |
| Arm C - LLM judge nondeterminism | harness runs; local CLI judge stable (flip rate 0); this substrate cannot exercise #4136 |

## The headline, stated once

A reported prompt-injection rate is `mean(judge(transcript) == success)`. Arm B measures one
grader shape - **credit the attack if the target tool NAME appears in the call log** - against a
state oracle, on 3,986 released AgentDojo transcripts. It reports **39.7%** where the state says
**23.1%**.

**What that is and is not a claim about, stated before the number is used.** It is not what
AgentHarm reports end to end, and this project checked rather than assumed. In inspect_evals
`scorer.py` an AgentHarm task's score is `np.mean(list(score_dict.values()))` - the unweighted mean
of that task's grading components. All 52 harmful grading functions include a name-only,
error-blind term (`is_function_called`, usually as `all_target_functions_called`), and 49 of 52
*also* read arguments, through `get_args_of_function_call`. So the blindness measured here is one
equally-weighted term of every AgentHarm score, not the whole of it - and `get_args_of_function_call`
has its own half of #2108, returning only the last matching call and never reading the tool error.

The shape is worth measuring on its own because it is exactly what a single-signal injection-success
judge is: "did the agent call the tool the attacker wanted". Arm B is a counterfactual on
transcripts that happen to come with a state oracle - AgentDojo's own published numbers use that
oracle - and it says what that judge would report.

**The gap is not one defect.** It is 12.4% calls that never executed (inspect_evals#2108 as filed),
69.0% calls that executed with the *user's own* arguments, because in this suite the injection
target and the user's task are the same tool, and 18.6% calls that carried the attacker's own
arguments and still did not achieve the attacker's goal - which no grader reading only the trace
can ever see. Checking the attacker's arguments removes 464 false positives and adds **zero** false
negatives, moving agreement with the oracle from 82.9% to 96.6%.

On the defense axis that inflation is not uniform, and the ordering does not survive. A defense
that blocks the *call* looks good to a name-only grader; a defense that neutralises the attacker's
*arguments* looks like it did nothing. Meta-SecAlign, one of the safest pipelines by the oracle,
drops eight to twelve places under the released grader. Kendall tau against the oracle is 0.68; the
argument check brings it to 0.95.

## What each claim rests on

- **The model is a pure derivation, purity-checked.** `tests/test_contract.py` parses the four
  model modules with `ast` and fails on a clock, a random draw, a filesystem or a network call.
  Zero third-party dependencies in the model.
- **The graders are the real shipped code, and the version claim is pinned.**
  `tests/test_graders_fidelity.py` runs the vendored `is_function_called`, `times_function_called`
  and `get_args_of_function_call` against the installed ones over real `inspect_ai` ChatMessage
  objects; runs the vendored `<answer>` parser against the shipped one; and runs the vendored
  blackmail gate against `BlackmailClassifier.classify` itself. It also asserts the released
  package does **not** contain the #2108 fix, so the version wording in this repo cannot silently
  go stale.
- **The corpus has a committed producer.** `scripts/fetch_agentdojo_runs.py` rebuilds every data
  file from the pinned AgentDojo commit, keeping arguments, call ids and paired tool errors, and
  extracting the attacker's arguments from AgentDojo's own `injection_tasks.py` with `ast`.
  `data/agentdojo/MANIFEST.json` carries a SHA-256 of each output.
- **Arm B runs the vendored graders, not a re-implementation.** It builds an `Episode` through
  `transcript.from_agentdojo_run` and grades through `graders/registry.py` - the same path Arm A
  uses.
- **The decomposition is arithmetic, not narrative.** The three buckets are assigned in ladder
  order and are mutually exclusive; `tests/test_arm_b.py` asserts the partition, the per-run
  monotonicity of the ladder, and every headline number.
- **Every observed run is receipted.** Each arm writes a canonical-JSON SHA-256 receipt. Arm B also
  writes a per-run verdict ledger (`evidence/arm-b-ledger.jsonl`, 3,986 rows), records its
  SHA-256 and the corpus SHA-256, and stores the full transcript, arguments and verdicts of every
  run any document cites. The CI `arms` job regenerates all of it and fails on any diff.

## Two corrections this project made to itself

Both are recorded in `results/`, not smoothed over.

1. **Arm B's headline was attributed to the wrong defect.** The 216-run sample it used carried no
   tool-call arguments and, as it happens, no errored calls at all - so inspect_evals#2108, which
   is about calls that never executed, could not have produced any of the reported gap. The gap was
   argument blindness. Corpus rebuilt with a committed producer, gap decomposed, corrected in
   [results/05](./results/05-arm-b-corrected.md). The corrected result is stronger: it identifies a
   defect that is not any of the four filed issues.
2. **"The ranking does not invert" was an artifact of the sample.** Four models over 216 runs gave
   Kendall tau 1.0. All 28 released pipelines over 3,986 runs give 0.68, and the inversion has a
   mechanism. Corrected in [results/06](./results/06-agentdojo-defense-axis.md).

A third, smaller correction is in the code rather than the notes: AgentDojo's released tool calls
carry no `id`, and the adapter's fallback was not unique per call. Because the #2108 fix skips
*every* call sharing a rejected id, one errored call would have un-credited unrelated successful
ones. Found before it reached a number; the corrected Arm B reproduces an independent scratch
implementation exactly.

## What this does not prove

- **#4136 (temperature-1.0 judge nondeterminism).** This machine has no model API key and the local
  `claude` CLI has no temperature control, so Arm C's flip rate is a floor that does not bound the
  effect. The harness measures it directly on a substrate that has temperature control. Not faked
  with paid calls chasing the wrong condition.
- **Arm B and the defense axis are one suite and one attack.** Banking / important_instructions,
  across every pipeline AgentDojo publishes for it. Whether the decomposition's shape holds on
  workspace, travel or slack is open; the producer already normalises all four suites' run
  summaries for Arm D, so the extension is a scoping change, not new machinery.
- **Arm B measures a grader shape, not AgentHarm's reported score.** AgentHarm's per-task score is
  the unweighted mean of several components, only one of which is name-only. The +16.60 pp is what
  a single name-only success criterion costs; how much of an AgentHarm number it moves depends on
  how many components that task's score has. Not extrapolated here.
- **Arm D is not a measurement of Inspect.** It measures the denominator-policy defect #4286
  describes, on the corpus where the policy is verifiable at source. AgentDojo's policy is the
  opposite of the one #4286 reports (it charges a crashed run as an attack success rather than
  dropping it), and that is stated rather than elided.
- **`arg_match` is a repair, not a sound grader.** It is fooled in both directions - it
  under-credits a call that errored non-fatally and still succeeded (2 real runs), and it
  over-credits a call carrying the attacker's arguments whose goal was not met (125 real runs).
  Only post-execution state settles the execution family, and `tests/test_predict.py` fails if the
  model ever claims otherwise.
- **Semantic harm no trace settles.** The two floor items (keyword-avoiding harm) are decidable by
  no deterministic grader, only by a semantic judge, imperfectly.

## Reproducing this document

```
uv sync --group dev
uv run pytest && uv run ruff check . && uv run mypy
uv run --extra fidelity pytest tests/test_graders_fidelity.py   # needs inspect-evals

# rebuild the corpus from the pinned AgentDojo commit (~37 MB download into work/, then offline)
uv run python scripts/fetch_agentdojo_runs.py

uv run python -m judge_artifact.model                    # the predicted disagreement matrix
uv run python -m judge_artifact.harness.arm_a            # real graders over the constructed corpus
uv run python -m judge_artifact.harness.arm_b            # decomposition on 3,986 transcripts
uv run python -m judge_artifact.harness.arm_b_defense    # the defense axis and rank inversion
uv run python -m judge_artifact.harness.arm_d            # denominator policy over 33,119 runs
uv run python -m judge_artifact.harness.arm_c --n 4      # LLM judge nondeterminism (paid, bounded)
```

Everything above except the last line is deterministic and offline once the corpus is present, and
the corpus is committed. `.github/workflows/ci.yml` runs all of it and fails if `evidence/` moves.
