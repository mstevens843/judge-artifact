# judge-artifact

**An attack-success rate is `mean over transcripts of judge(transcript) == success`. Different
judges disagree on identical transcripts, and the gap is judge artifact, not attack success.
judge-artifact measures that gap in both directions, asks whether repairing the judge reorders the
leaderboard, and names the harm no execution trace can settle.**

The target is real and shipped. Four open, verified defects in UK AISI's Inspect stack (MIT) decide
whether a reported prompt-injection or agent-harm number is measuring the attack or the grader:
`inspect_evals#2310` (a harmful verdict is decided by `"yes" in answer`, so `"yesterday"` reads as
harmful and `"cannot"` flips it, still live on main); `inspect_evals#2108` (a tool call that errored
or named a nonexistent tool is credited the same as one that ran; its fix was merged then de-facto
reverted); `inspect_ai#4136` (graders run unseeded at temperature 1.0); `inspect_ai#4286` (errored
samples are dropped from the denominator).

This is defensive eval-integrity research on public MIT code, run in the author's own sandbox. The
exploit transcripts are grader test cases; the deliverable is a set of upstream findings and PRs
that make the reported numbers more honest. No system the author does not control is touched.

> [!WARNING]
> **Pre-1.0, nothing published.** What is true is stated with the command that reproduces it; what
> is not done is listed as not done. Full record in [RESULTS.md](./RESULTS.md).
>
> **What runs today, measured rather than remembered:**
>
> - **The model.** `src/judge_artifact/model/` derives, as a pure total function over declared
>   grader and defect properties, the predicted verdict for 12 grader-fooling episodes against 7
>   graders in three families: `uv run python -m judge_artifact.model`. Purity is checked, not
>   asserted; zero third-party dependencies in the model.
> - **The graders are the real shipped code.** The #2108 defect and its reverted fix, and the #2310
>   substring parser, are vendored verbatim with commit SHAs; a fidelity test asserts the vendored
>   copies reproduce the installed `inspect_evals` verdicts (`uv run --extra fidelity pytest`).
> - **Arm A, both directions, deterministic.** The real graders over the constructed corpus match
>   the prediction on every cell, over- and under-crediting in all three families, with two floor
>   cases no deterministic grader settles: `uv run python -m judge_artifact.harness.arm_a`.
> - **Arm B, the headline, on real data.** On 216 AgentDojo transcripts the #2108-style read inflates
>   the injection-success rate by **24 to 35 pp** (a true 1.9% becomes 37% for one model); the
>   ranking does not invert on this suite (Kendall tau 1.0):
>   `uv run python -m judge_artifact.harness.arm_b`.
> - **Arm C, honestly bounded.** The LLM-judge nondeterminism harness runs; the local CLI judge is
>   stable, and this substrate cannot exercise #4136's temperature-1.0 condition. Said, not hidden.
>
> **Do not cite a number from this repo that does not name the command that produced it.**

## Layout

```
src/judge_artifact/model/     the prediction: layers, graders, defects, predict (pure, purity-tested)
src/judge_artifact/canonical.py  canonical JSON + SHA-256 receipts (reused from cheat-oracle)
src/judge_artifact/transcript.py the neutral episode rep + adapters (inspect ChatMessage, AgentDojo)
src/judge_artifact/graders/   runnable graders over the neutral rep; real functions vendored verbatim
src/judge_artifact/corpus/    the both-direction exploit episodes + controls
src/judge_artifact/harness/   arm_a (constructed), arm_b (AgentDojo rank inversion), arm_c (LLM)
data/agentdojo/               a bounded, documented AgentDojo runs sample (MIT)
evidence/                     receipted observed artifacts (arm-a/b/c)
results/                      numbered, append-only lab notebook (00 substrate .. 04 arm-c)
```

## What it does not do

It does not run the full Inspect harness (unnecessary: both headline defects are pure functions
reached directly). It does not claim to judge semantic harm that no execution trace settles, and
names that floor. Arm B is a bounded, documented sample of AgentDojo runs, never a silent
truncation.
