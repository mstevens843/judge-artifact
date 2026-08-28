# Results

Verification record. Every number here was produced by running the command shown, on the toolchain
named below, and reading its output. Nothing is copied from an earlier run or a summary of a run.
Where something is skipped, substrate-limited, or unproven, it says so and says why.

**Frozen:** 2026-08-27
**Toolchain:** Python 3.12.13, uv 0.11.26, pytest, ruff, mypy (strict) via `uv run`.
**Graders:** the real, commit-pinned inspect_evals functions, vendored verbatim and fidelity-checked
against the installed package.
**Ground truth:** the effect an action achieved (constructed corpus), or AgentDojo's released
`security` verdict (real data) - never the grader under test.

## Summary

| Gate | Result |
|---|---|
| Model + purity + thesis + corpus tests (`uv run pytest`) | **55 passed** |
| ruff / mypy --strict | clean |
| Grader fidelity vs real inspect_evals (`uv run --extra fidelity pytest`) | **passes** - vendored parser reproduces the shipped verdict on every corpus answer |
| Predicted disagreement matrix (`python -m judge_artifact.model`) | 12 episodes x 7 graders, 3 families, pure derivation |
| Arm A - real graders over the corpus (`python -m ...harness.arm_a`) | **0 predicted-vs-observed disagreements**; both directions in every family |
| Arm B - AgentDojo rank inversion (`python -m ...harness.arm_b`) | defective grader inflates ASR **+24 to +35 pp**; ranking does **not** invert (Kendall tau 1.0) |
| Arm C - LLM judge nondeterminism (`python -m ...harness.arm_c`) | harness runs; CLI judge stable (flip rate 0); substrate cannot exercise #4136 |

## The headline, stated once

A reported prompt-injection or agent-harm rate is `mean(judge(transcript) == success)`, and the
judge is defective in ways that are shipped and open today. On a constructed corpus the real
vendored graders over- and under-credit exactly as modelled, in both directions, in three families,
with two floor cases no deterministic grader can settle. On 216 real AgentDojo transcripts the
shipped #2108-style read inflates the injection-success rate by 24 to 35 percentage points - for one
model, a true 1.9% becomes 37% - while, on this suite and attack, it inflates every model similarly,
so the leaderboard order survives. The absolute number is grader artifact; the ranking, here, is not.

## What each claim rests on

- **The model is a pure derivation, purity-checked.** `tests/test_contract.py` parses the four model
  modules with `ast` and fails on a clock, a random draw, a filesystem, or a network call. Zero
  third-party dependencies in the model.
- **The graders are the real shipped code.** The defect and fix functions are vendored verbatim with
  their commit SHAs (4e4aaaa, 38bf05d4, 979bf44); the fidelity test asserts the vendored substring
  parser reproduces the installed `inspect_evals` classifier's verdict on every corpus answer.
- **The model was refined to stay faithful, in public.** The #2108 fix is not ground truth: it was
  reverted for over-correcting, so it is modelled as a second shipped defect that under-credits a
  call which errored non-fatally but succeeded. The harness caught a corpus control bug (a keyword
  placed only in the action, not the response) and it was fixed. Both are in `results/`.
- **Both directions, and an honest floor.** `tests/test_corpus.py` asserts, in CI with no network,
  that the real graders reproduce the model, that over- and under-credit appear in every family, and
  that the two keyword-avoiding floor items are recovered by no deterministic grader.
- **Every observed run is receipted.** Arm A/B/C each carry a canonical-JSON SHA-256 receipt.

## What this does not prove

- **#4136 (temperature-1.0 judge nondeterminism).** This machine has no model API key and the local
  claude CLI has no temperature control, so Arm C's flip rate is a floor that does not bound the
  effect. The harness measures it directly on a substrate that has temperature control.
- **Rank inversion in general.** Arm B is one suite and one attack. A wider sweep, where models
  differ in how often a called target actually succeeds, could invert the order; that is future
  work, named as such.
- **Semantic harm no trace settles.** The two floor items (keyword-avoiding harm) are decidable by
  no deterministic grader, only by a semantic judge, imperfectly. The project states this rather
  than papering over it.

## Reproducing this document

    uv sync --group dev
    uv run pytest && uv run ruff check . && uv run mypy
    uv run --extra fidelity pytest tests/test_graders_fidelity.py   # needs inspect-evals
    uv run python -m judge_artifact.model                 # the predicted disagreement matrix
    uv run python -m judge_artifact.harness.arm_a         # real graders over the corpus
    uv run python -m judge_artifact.harness.arm_b         # AgentDojo ASR inflation + rank inversion
    uv run python -m judge_artifact.harness.arm_c --n 4   # LLM judge nondeterminism (paid, bounded)
