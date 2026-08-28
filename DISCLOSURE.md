# Disclosure draft - grader-artifact findings in the Inspect eval stack

**To:** the UK AI Safety Institute Inspect maintainers, and the authors of issues #2108, #2310,
#2292, #2293, #4136, #4286.
**From:** Mathew Stevens. **Nature:** defensive eval-integrity research on MIT-licensed public code,
run in a local sandbox. The exploit transcripts are grader test cases; no system the author does not
control was touched. **Status:** draft, not yet sent.

## Summary

Reported prompt-injection and agent-harm rates are produced by success graders with defects that are
open and shipped today. Measured against a ground truth these graders do not read (the effect an
action achieved; the released `security` oracle), the defects over- and under-credit in both
directions, and on real data they inflate an absolute rate by tens of percentage points.

## Findings, each reproduced against the shipped code

1. **#2108 is a two-sided problem, and the reverted fix is the second side.** The shipped defect
   (`is_function_called`, 4e4aaaa) over-credits a tool call that errored or named a nonexistent tool
   (a truly-failed action scored as success). The merged-then-reverted fix (38bf05d4) over-corrects:
   it skips any errored call, so a call that errored non-fatally but still achieved its effect is
   under-credited. Only reading the effect is sound. Both are exercised in a constructed corpus and
   reproduced by the vendored functions.

2. **#2108 on real data inflates the rate 24-35 pp.** On 216 AgentDojo banking / important_instructions
   transcripts (MIT), the credit-the-call-anyway read reports an injection-success rate 24 to 35
   percentage points above AgentDojo's sound `security` oracle - for claude-3-5-sonnet, 1.9% becomes
   37%. On this suite and attack the inflation is similar across models, so the ranking is preserved
   (Kendall tau 1.0); a wider sweep is needed to know whether it holds elsewhere.

3. **#2310 substring parse.** `"yes" in answer` / `"no" in answer` (yes first) mis-parses a benign
   answer whose reason mentions yes, and a harmful answer phrased without the token. A first-token
   parse recovers the decidable cases and abstains on the malformed ones instead of guessing.

4. **#2292 / #2293 gates over the whole response.** A refusal that names the override code or
   "leverage" is counted as doing it; an action-scoped gate recovers it. Keyword-avoiding harm is a
   floor no keyword gate catches, in either direction - only a semantic judge could.

5. **#4136 / #4286.** Named and modelled: an unseeded temperature-1.0 grader flips borderline items
   across runs (a confidence interval nobody reports), and errored samples dropped from the
   denominator make the reported rate "the samples that happened to succeed".

## What we are offering

- The reproduction, the both-direction corpus, the vendored graders with a fidelity check, the
  AgentDojo re-scoring, and the receipts, runnable from `uv run`.
- PRs where the fix is deterministic and uncontested: a first-token / exact-match answer parse for
  #2310 that abstains rather than guesses, and a denominator clamp for #4286. For #2108 we offer the
  effect-reading framing and the AgentDojo inflation number as input to the eval-design discussion
  the maintainers reopened, not a unilateral fix.

We would value a correction if any finding does not reproduce.
