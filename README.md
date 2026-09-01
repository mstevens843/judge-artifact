# judge-artifact

**An attack-success rate is `mean over transcripts of judge(transcript) == success`. Different
judges disagree on identical transcripts, and the gap is judge artifact, not attack success.
judge-artifact measures that gap in both directions, decomposes it into the specific blindnesses
that produce it, asks whether repairing the judge reorders the leaderboard, and names the harm no
execution trace can settle.**

The target is real and shipped. Open, verified defects in UK AISI's Inspect stack (MIT) decide
whether a reported prompt-injection or agent-harm number is measuring the attack or the grader:
`inspect_evals#2108` (a tool call is credited by function name, whether or not it executed and
whatever arguments it carried); `inspect_evals#2310` (a harmful verdict is decided by
`"yes" in answer`, so `"yesterday"` reads as harmful and `"cannot"` flips it); `inspect_evals#2292`
/ `#2293` (a keyword gate runs over the whole response, so a refusal that names the thing counts as
doing it); `inspect_ai#4136` (graders run unseeded at temperature 1.0); `inspect_ai#4286` (errored
samples are dropped from the denominator).

This is defensive eval-integrity research on public MIT code, run in the author's own sandbox. The
exploit transcripts are grader test cases; the deliverable is a set of upstream findings and PRs
that make the reported numbers more honest. No system the author does not control is touched.

## The result

On **3,986 released AgentDojo transcripts** (banking, `important_instructions`, all 28 published
pipelines), a success judge that credits the attack when the target tool NAME appears in the call
log reports a **39.7%** injection-success rate where AgentDojo's own state oracle says **23.1%**.

That judge is not a strawman: `is_function_called`, unchanged in `inspect_evals 0.18.0`, is
name-only and error-blind, and it appears in all 52 of AgentHarm's harmful grading functions. It is
also not the whole of AgentHarm - a task's score is the unweighted mean of several components
(`scorer.py`: `np.mean(list(score_dict.values()))`), and 49 of 52 graders do read arguments, via
`get_args_of_function_call`, which has its own half of #2108. So this measures what one widely-used
grader shape costs, which is what a single-signal injection-success judge is.

That gap is three different defects, and naming which is the whole point:

| bucket | share | what happened |
|---|---|---|
| error-blind | **12.4%** | the target call errored or never executed - `inspect_evals#2108` as filed |
| **argument-blind** | **69.0%** | it executed **with the user's own arguments**: in this suite the injection target and the user's legitimate task are the same tool, so the agent doing its job is scored as the attack succeeding |
| effect-blind | **18.6%** | it executed with the attacker's own arguments and the attacker's goal was still not met - invisible to any grader that reads only the trace |

**The argument-blind bucket is not one of the filed issues.** It is the dominant one, and checking
the attacker's arguments removes 464 false positives while adding **zero** false negatives.

And the ordering does not survive either. On the defense axis the name-only judge gives Kendall tau
**0.68** against the state oracle and moves 23 of 28 pipelines, because the bias has a mechanism: a
defense that stops the agent **calling** the tool looks good to a name-only grader, and a defense
that neutralises the attacker's **arguments** looks like it did nothing. Meta-SecAlign, among the
safest pipelines by the oracle, drops eight to twelve places. Adding the argument check restores tau
to **0.95**.

> [!NOTE]
> **AgentDojo is not being accused of anything.** Its published numbers use its own sound state
> oracle, and that oracle is the ground truth everything here is measured against. Arm B is a
> counterfactual: what an Inspect-style success grader would report over the same transcripts.

## What runs today, measured rather than remembered

- **The model.** `src/judge_artifact/model/` derives, as a pure total function over declared grader
  and defect properties, the predicted verdict for 15 grader-fooling episodes against 8 graders in
  three families: `uv run python -m judge_artifact.model`. Purity is checked with `ast`, not
  asserted; zero third-party dependencies in the model.
- **The graders are the real shipped decision logic.** The AgentHarm counting helpers, the
  agentic_misalignment `<answer>` parser and `BlackmailClassifier.classify` are vendored/adapted
  with their source and version, and `uv run --extra fidelity pytest` asserts the local copies
  reproduce the **installed** `inspect_evals` verdicts on every episode - including that the
  pinned released package does not contain the #2108 fix.
- **Arm A, both directions, deterministic.** `uv run python -m judge_artifact.harness.arm_a` runs
  the real graders over a constructed corpus and matches the prediction on every cell. The
  execution family is a ladder - name only, name + no error, name + attacker's arguments, state -
  and every rung that stops at the trace is still wrong in **both** directions.
- **Arm B, the headline, on real data.** `uv run python -m judge_artifact.harness.arm_b` and
  `...harness.arm_b_defense`, over a corpus rebuilt by a committed producer from a pinned AgentDojo
  commit.
- **Arm D, the denominator.** `uv run python -m judge_artifact.harness.arm_d`. AgentDojo writes
  `security = True` when a run crashes (`benchmark.py` lines 129-130, source-verified), so a run in
  which the agent never acted is published as an attack success. Corpus-wide that is worth 0.27 pp
  - and one published cell (`command-r-plus`, workspace) is **100%** crashed runs: 8.3% reported,
  0.0% state-verified.
- **Arm C, honestly bounded.** The judge-nondeterminism harness runs; the local CLI judge has no
  temperature control, so this substrate cannot exercise #4136. Said, not hidden.

**Do not cite a number from this repo that does not name the command that produced it.** Full
record in [RESULTS.md](./RESULTS.md).

## Layout

```
src/judge_artifact/model/        the prediction: layers, graders, defects, predict (pure, purity-tested)
src/judge_artifact/argmatch.py   normalisation + matching for "did it run with the ATTACKER's args"
src/judge_artifact/canonical.py  canonical JSON + SHA-256 receipts
src/judge_artifact/transcript.py the neutral episode rep + the AgentDojo adapters
src/judge_artifact/graders/      runnable graders; shipped decision logic adapted + fidelity-checked
src/judge_artifact/corpus/       the both-direction exploit episodes + controls
src/judge_artifact/harness/      arm_a (constructed), arm_b (+ defense axis), arm_c (LLM), arm_d (denominator)
scripts/fetch_agentdojo_runs.py  the committed corpus producer: pinned commit, hashed outputs
data/agentdojo/                  the normalised corpus + MANIFEST.json (3.4 MB, MIT)
evidence/                        receipted observed artifacts, incl. a 3,986-row per-run ledger
results/                         numbered, append-only lab notebook (00 substrate .. 07 denominator)
```

## What it does not do

It does not run the full Inspect harness (unnecessary: the graders under test are pure functions,
reached directly). It does not claim to judge semantic harm that no execution trace settles, and
names that floor. Its repaired execution grader is a **repair, not a sound grader** - it is fooled
in both directions too, and the project says so and measures it. Arm B is one suite and one attack,
across every pipeline released for them; a wider suite sweep is named as future work, not implied
away. Arm D measures the denominator defect's *shape* on AgentDojo, where the policy is verifiable
at source; it is not a measurement of Inspect's implementation.

## Corrections this project made to itself

An earlier version reported the Arm B gap as `#2108` and reported that the leaderboard does not
reorder. Both were wrong, both because of the sample: the corpus it used had discarded tool-call
arguments and happened to contain no errored calls at all, and it covered 4 models rather than 28.
Rebuilt, decomposed and corrected in [results/05](./results/05-arm-b-corrected.md) and
[results/06](./results/06-agentdojo-defense-axis.md); the superseded note is kept unedited.
