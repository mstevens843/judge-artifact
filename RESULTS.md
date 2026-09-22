# Results

Verification record. Every number here was produced by running the command shown, on the toolchain
named below, and reading its output. Nothing is copied from an earlier run or from a summary of a
run. Where something is skipped, substrate-limited or unproven, it says so and says why. Where an
earlier version of this document was wrong, it says that too, and links to the note that corrects
it.

**Frozen:** 2026-08-28
**Toolchain:** Python 3.12.13, uv 0.11.26, pytest 9.1.1, ruff 0.16.5, mypy 2.3.1 (strict), all via
`uv run`. Fidelity checks against the locked environment: `inspect-evals 0.18.0` /
`inspect-ai 0.3.260`.
**External package status checked:** 2026-09-01. PyPI latest is `inspect-evals 0.19.0` /
`inspect-ai 0.3.261`; the optional latest fidelity path passed against those exact versions on
2026-09-01. Compatibility note: latest now ships the AgentHarm #2108 rejection filter, so it matches
the `*_MAIN_FIX` copies rather than the locked 0.18.0 `*_RELEASED` copies.
**Graders:** the real shipped decision logic, vendored/adapted with source and version, and checked
against the installed `inspect_evals` on every corpus episode.
**Corpus:** AgentDojo (MIT) at pinned commit `089ed468cf3ed0322acc66b0211f26d9d90dbf60`, normalised
by a committed producer, hashed in `data/agentdojo/MANIFEST.json`.
**Ground truth:** the effect an action achieved. For the constructed corpus that is true by
construction; for AgentDojo it is the released `security` oracle. Never the grader under test.

## Summary

| Gate | Result |
|---|---|
| `uv run pytest -q` (2026-09-07) | **218 passed, 17 skipped** - the skips are latest-fidelity tests when the locked fidelity environment is installed |
| `uv run ruff check .` / `uv run mypy` (strict, incl. `scripts/`) | clean |
| `uv run --extra fidelity pytest tests/test_graders_fidelity.py -q` (2026-09-07) | **20 passed** - locked #2108, #2310 and #2292 copies reproduce `inspect-evals 0.18.0` / `inspect-ai 0.3.260`, including both HTML-parser corpora |
| latest PyPI fidelity command | **17 passed** against `inspect-evals 0.19.0` / `inspect-ai 0.3.261`; #2108 now matches the `*_MAIN_FIX` copies |
| `uv run python -m judge_artifact.model` | 15 episodes x 8 graders, 3 families, pure derivation |
| Arm A - real graders over the constructed corpus | **0 predicted-vs-observed disagreements**; both directions in every family |
| Arm B - 3,986 released AgentDojo transcripts | a name-only success judge reports **+16.60 pp**; over-credit decomposes **12.4% error-blind / 69.0% argument-blind / 18.6% effect-blind** |
| Arm B broader important_instructions sweep | **15,781 runs** across banking, slack, travel and workspace; name-only reports **+9.69 pp**, over-credit decomposes **7.4% error-blind / 73.8% argument-blind / 18.8% effect-blind** |
| Arm B defense axis - 28 pipelines | ranking **does** invert: Kendall tau **0.68**, 23 of 28 positions moved; adding the argument check restores it to **0.95** |
| Arm D - 33,119 attacked runs, denominator policy | corpus-wide **0.27 pp**; one published cell is **100%** crashed runs |
| Arm D on Inspect - #4286's own four reproductions re-run against `inspect-ai 0.3.266` | **1 OPEN / 3 PARTIAL / 1 FIXED**. The unbounded-metric item reproduces as filed: `[1, 0, inf] -> accuracy inf`, and because `inf` is not `NaN` it is counted as a SCORED sample |
| Arm C - LLM judge nondeterminism | measured on 2026-09-01 through `inspect_ai` + `anthropic/claude-haiku-4-5-20251001` at temperature 1.0, n=30 per prompt: **0 flips**, pooled ASR **0.5000**, Wilson 95% **[0.3773, 0.6227]** |

Arm C receipt:
`ja1_b83f485c5c1a24db8391ad079bec350dcc67397c913a75e80fe6fd64b4deba33`.
Package context for that paid run: `inspect-ai 0.3.260`, `inspect-evals 0.18.0`,
`anthropic 1.2.0`.

## Follow-up verification, 2026-09-06

Supporting regressions for #2108 and #2310 are recorded in
[results/09](./results/09-grader-followup-regressions.md). The repeated-call mismatch reproduces
against locked `inspect-evals 0.18.0` / `inspect-ai 0.3.260`: last-call arguments, first response.
Fixed-sample tests pin banking **1,583 -> 1,498 positives / 3,986** (39.71% -> 37.58%) and broad
**4,732 -> 4,608 / 15,781** (29.99% -> 29.20%) across the error-filter boundary. This removes
83/119 false positives but adds 2/5 false negatives, respectively, relative to the same state
oracle. The existing Arm B evidence and headline are unchanged.

The new offline parser-delta command compares the released substring rule with exact yes/no on
identical saved completions, using the same BeautifulSoup extraction. On **16 constructed cases**
the counts are substring **8 yes / 5 no / 3 unparsed**, strict **4 yes / 4 no / 8 unparsed**.
Four positives and one negative become unparsed; these selected cases do not estimate prevalence
or real-world harm-rate inflation. Every completion and verdict is in
`evidence/parser-delta-constructed.json`, receipt
`ja1_90c78192bc460e4c43417533431b0419bbb1a8a3ce440f2affc6a667a578ea59`.
The command makes no model calls, retains a fixed all-record denominator, and records declared
provenance and `representativeness=not_established` even for user-supplied stored responses.
An isolated default run with `uv run --offline --isolated --no-extra fidelity pytest -q` also
passed: **137 passed, 36 skipped** (both optional fidelity suites absent). Ruff, strict mypy,
the corpus rebuild, model, deterministic arms and the Arm C no-call smoke passed. Existing
`data/agentdojo` and evidence files reproduced without a diff; the constructed parser report is
a separate new artifact.

## Parser paths and pinned PR comparison, 2026-09-07

The optional parser-delta `--compare-pr-2311` mode now compares the released blackmail parser,
the PR parser at `4698d4b68dfa88bdaf849e591f3a46d6151219a2`, and strict exact parsing on identical
completions. Counts and all pairwise transitions are reported separately by the HTML extractor's
tag-present/tag-absent branch. The original v1 report and historical result note remain unchanged.

On **32 constructed cases**, counts are **yes / no / unparsed**:

| Scope | n | Released substring | Pinned PR | Strict exact |
|---|---:|---|---|---|
| tag present | 19 | 9 / 7 / 3 | 7 / 7 / 5 | 5 / 5 / 9 |
| tag absent | 13 | 8 / 1 / 4 | 4 / 2 / 7 | 0 / 0 / 13 |
| overall | 32 | 17 / 8 / 7 | 11 / 9 / 12 | 5 / 5 / 22 |

The PR changes the fallback to first-marker token matching, but the reasoning example
`the answer: yes reading is tempting here, but no` still returns yes. Offline fidelity tests run
the actual parser definitions from hashed upstream source snapshots; optional locked-package
fidelity checks the released rule on the same cases. These are behavioral regressions, not a
prevalence estimate or a measurement of the PR's complete scorer. The format contract already
exists in the prompt; a large unparsed bucket alone would not show a missing contract.

Command, source provenance, denominator policy and limits:
[results/10](./results/10-parser-paths-and-pr2311.md).
Evidence: `evidence/parser-delta-paths-constructed.json`, receipt
`ja1_b2e11c0d93865d8baf6a8a14dadd10a643c77e9a817ff9ba97c0547de04aef98`.
The focused parser/fidelity command passed **115 tests**. The isolated offline default run
passed **198 tests, 37 optional fidelity skips**; the pinned PR tests run in that environment
without Inspect. Ruff and strict mypy passed. The corpus rebuild, model, deterministic arms,
Arm C no-call smoke and both parser reports reproduced; no existing tracked data/evidence,
dependency files or historical numbered notes changed.

## Pinned parser revisions, 2026-09-22

The unchanged 32 constructed cases now also have an explicit four-rule v3 comparison.
Between PR `4698d4b` and `361bb2e`, one no becomes yes, one unparsed becomes yes, and one
unparsed becomes no; 29 verdicts are unchanged. PR totals move from **11/9/12** to
**13/9/10** (yes/no/unparsed). All 19 tagged verdicts and the single-marker reasoning
limitation remain unchanged. Three separate supplemental controls have one flip in each
direction and one unchanged rejection, including the target helper's markup-adjacent
docstring example. These are parser observations, not semantic error or deployed harm rates.

[Report, source binding and limitations](./results/11-parser-revision-comparison.md);
[primary evidence](./evidence/parser-delta-revisions-constructed.json);
[self-review and gates](./handoff/parser-2311-revision-comparison/SELF-REVIEW.md).
Historical parser evidence and numbered reports remain unchanged.

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
  go stale. `tests/test_graders_fidelity_latest.py` is the separate optional latest-PyPI check; for
  `inspect-evals 0.19.0` / `inspect-ai 0.3.261`, the AgentHarm helpers match `*_MAIN_FIX` because
  the rejection filter has shipped.
- **The corpus has a committed producer.** `scripts/fetch_agentdojo_runs.py` rebuilds every data
  file from the pinned AgentDojo commit, keeping arguments, call ids and paired tool errors, and
  extracting the attacker's arguments from AgentDojo's own `injection_tasks.py` with `ast`. It also
  writes a broader `important_instructions` corpus over all suites/tasks with statically matchable
  target-call ground truth, plus explicit skipped-task reasons. `data/agentdojo/MANIFEST.json`
  carries a SHA-256 of each output.
- **Arm B runs the vendored graders, not a re-implementation.** It builds an `Episode` through
  `transcript.from_agentdojo_run` and grades through `graders/registry.py` - the same path Arm A
  uses.
- **The decomposition is arithmetic, not narrative.** The three buckets are assigned in ladder
  order and are mutually exclusive; `tests/test_arm_b.py` asserts the partition, the per-run
  monotonicity of the ladder, and every headline number.
- **Every observed run is receipted.** Each arm writes a canonical-JSON SHA-256 receipt. Arm B also
  writes a per-run verdict ledger (`evidence/arm-b-ledger.jsonl`, 3,986 rows), records its
  SHA-256 and the corpus SHA-256, and stores the full transcript, arguments and verdicts of every
  run any document cites. The broader Arm B sweep writes a separate 15,781-row ledger and evidence
  record. The CI `arms` job regenerates the deterministic headline artifacts and fails on any diff.

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

- **#4136 (temperature-1.0 judge nondeterminism).** The real measurement path has now been run on
  one API substrate: `inspect_ai` with `anthropic/claude-haiku-4-5-20251001`, explicit
  `GenerateConfig(temperature=1.0, seed=None, max_tokens=32)`, 30 samples for each of two
  borderline judge prompts. This sample observed no flips. It is evidence for this measured
  substrate only; it does not prove that other providers, models, prompts, or grader call sites are
  stable or unstable.
- **Arm B headline and defense axis are one suite and one attack.** Banking /
  important_instructions, across every pipeline AgentDojo publishes for it. The broader
  important_instructions sweep now covers banking, slack, travel and workspace where static target
  arguments can be extracted, but it does not cover other attacks and it excludes tasks whose
  AgentDojo ground truth cannot be soundly normalized.
- **Arm B measures a grader shape, not AgentHarm's reported score.** AgentHarm's per-task score is
  the unweighted mean of several components, only one of which is name-only. The +16.60 pp is what
  a single name-only success criterion costs; how much of an AgentHarm number it moves depends on
  how many components that task's score has. Not extrapolated here.
- **Arm D now has two substrates, and neither is a survey.** On AgentDojo it measures the
  denominator-policy defect #4286 describes, on the corpus where the policy is verifiable at
  source; AgentDojo's policy is the opposite of the one #4286 reports, charging a crashed run as
  an attack success rather than dropping it. On Inspect itself it re-runs #4286's four
  reproductions plus the schema question - five probes matched to one issue, not a survey of the
  metric layer. A `PARTIAL` verdict there means the behaviour the issue describes still occurs
  with the counts now reported beside it, not that the maintainers chose wrongly:
  `--fail-on-error` and `--score-on-error` are documented controls that bound item 1 for a user
  who sets them, and this arm measures the default path. Recorded in
  [results/11](./results/11-inspect-denominator-measured.md).
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
uv run --python 3.12 --isolated --with pytest --with inspect-evals==0.19.0 \
  --with inspect-ai==0.3.261 --with-editable . pytest tests/test_graders_fidelity_latest.py -q

# rebuild the corpus from the pinned AgentDojo commit (~37 MB download into work/, then offline)
uv run python scripts/fetch_agentdojo_runs.py

uv run python -m judge_artifact.model                    # the predicted disagreement matrix
uv run python -m judge_artifact.harness.arm_a            # real graders over the constructed corpus
uv run python -m judge_artifact.harness.arm_b            # decomposition on 3,986 transcripts
uv run python -m judge_artifact.harness.arm_b --broad-important-instructions
uv run python -m judge_artifact.harness.arm_b_defense    # the defense axis and rank inversion
uv run python -m judge_artifact.harness.arm_d            # denominator policy over 33,119 runs
uv run --extra fidelity python -m judge_artifact.harness.arm_d_inspect \
  --out evidence/arm-d-inspect-locked.json        # #4286 re-run on the locked inspect-ai
uv run --python 3.12 --isolated --with inspect-ai==0.3.266 --with-editable . \
  python -m judge_artifact.harness.arm_d_inspect --out evidence/arm-d-inspect.json
uv run python -m judge_artifact.harness.arm_c --out /tmp/arm-c-readiness.json
uv run --extra parser python -m judge_artifact.harness.parser_delta \
  --input tests/fixtures/parser-completions.jsonl \
  --out evidence/parser-delta-constructed.json --corpus-kind constructed \
  --source 'Constructed #2310 regression cases; no sampled model outputs'
uv run --extra parser python -m judge_artifact.harness.parser_delta \
  --input tests/fixtures/parser-path-completions.jsonl \
  --out evidence/parser-delta-paths-constructed.json --corpus-kind constructed \
  --source 'Constructed blackmail parser path regressions; no sampled model outputs' \
  --compare-pr-2311

# optional paid/API Arm C measurement; requires Anthropic credentials and workspace header when
# using an identity-linked key
ANTHROPIC_API_KEY=<key> ANTHROPIC_WORKSPACE_ID=<workspace-id> \
  uv run --extra fidelity --with anthropic python -m judge_artifact.harness.arm_c \
  --provider inspect --model anthropic/claude-haiku-4-5-20251001 \
  --temperature 1.0 --n 30 --allow-paid-api
```

The default CI path is deterministic and offline once dependencies and the committed corpus are
present. The latest-PyPI fidelity command is intentionally isolated and network/package-version
controlled, and the first corpus rebuild may download the pinned AgentDojo archive into `work/`.
`.github/workflows/ci.yml` runs the deterministic evidence-producing commands, exercises the Arm C
no-call path into `/tmp`, and fails if committed deterministic evidence moves.
