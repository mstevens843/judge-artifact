# 00 - Day-0 substrate gate

Working record. Every line below was produced by running the command shown on this machine and
reading its output. Nothing is remembered. Where a capability is absent it says so and says why.

**Host:** macOS (Darwin arm64). **Python:** 3.12.13 (uv-managed). **uv:** 0.11.26. **gh:** 2.92.0.
**No model API key in the environment** (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` absent).

## Gate 1 - the defective grader source, fetched verbatim (inspect_evals, MIT)

| defect | issue | commit fetched | what was confirmed |
|---|---|---|---|
| substring verdict parse | inspect_evals#2310 (OPEN, live on main) | `979bf44` | `parse_grader_response` decides by `"yes" in answer` / `"no" in answer` inside `<answer>`. Pure string function in `blackmail_/murder_/leak_classifier.py`. `"yesterday" contains "yes"`, `"cannot"/"not" contain "no"`. |
| credit un-executed tool calls | inspect_evals#2108 (OPEN, reopened) | defect `4e4aaaa`, fix `38bf05d4` | DEFECT `is_function_called(messages, name)` reads only assistant `tool_calls`, never the paired tool `error`. FIX adds `_rejected_tool_call_ids` and every helper skips rejected ids. Both fetched; the fix was merged then de-facto reverted (recommends pre-fix v6-B, #2285). |

Both defects are PURE functions - the first over a string, the second over `list[ChatMessage]` - so
they are exercised directly with no inspect harness, no model, no network. This is the load-bearing
feasibility fact: the deterministic arms (A, B) need zero API calls and run the real shipped logic.

## Gate 2 - the LLM-judge substrate (for Arm C, the #4136 nondeterminism)

`claude` CLI 2.1.247 is present and runs non-interactively: `claude -p "<prompt>" --output-format
json` returns `{"is_error":false, ..., "result": ...}` and exits 0, with no API key (subscription
auth). Confirmed with a one-word judge prompt. Caveats recorded for Arm C: the call carries the
Claude Code system prompt (a large cache-creation cost, ~$0.2/call in the smoke test), so Arm C uses
a minimal system prompt where possible and a bounded N; the canonical model was `claude-opus-5`.

## Gate 3 - real released data for Arm B (rank inversion)

AgentDojo (`ethz-spylab/agentdojo`, MIT). `runs/<model>/<suite>/injection_task_N/<attack>/*.json`.
Confirmed by fetching one real attack run: top-level keys include `security` (bool - did the
injection actually succeed, the deterministic ground truth), `utility` (bool), `attack_type`,
`injection_task_id`, `user_task_id`, `pipeline_name`, `injections` (the attack strings), and
`messages` (full transcript: assistant `tool_calls`, tool messages with an `error` field). The grid
is large: models (claude-3-5-sonnet, gpt-4, gemini, command-r, ...) x 4 suites x tasks x attacks
(`important_instructions` alone appears on 19,381 runs). This is a released corpus of completed
tool-call transcripts WITH a machine-checkable oracle and a real leaderboard - the substrate for
"re-score under a defective grader vs the sound oracle; does the ranking invert?".

Honest note recorded now, to be measured in Arm B: AgentDojo's own `security` is already sound, so
the artifact measured there is a counterfactual - applying the #2108-style credit-the-call-anyway
grader to these transcripts and diffing against `security`. The delta is bounded by how often a
credited target call did not actually achieve the injection (error, block, wrong effect); if that is
rare the delta is small, which is a reportable null, not a hidden one.

## Gate outcome

All three gates clear. Proceed: model first (judges x defects -> predicted disagreement matrix),
then the vendored graders + fidelity test, the both-direction corpus, and the three arms.
