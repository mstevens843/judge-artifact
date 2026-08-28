# 01 - The model, before any exploit

Working record. The model layer is complete and self-verifying. It was written and tested with no
grader running and no transcript on disk: it is a pure prediction, and the harness exists to try to
prove it wrong.

## What was built

`src/judge_artifact/model/` - four modules, zero third-party dependencies:
- `layers.py` - the vocabulary: `Verdict {SUCCESS, FAILURE, ABSTAIN}`, `Family {EXECUTION,
  PARSE_GATE}`, `DefectClass`, `Direction`.
- `graders.py` - six graders as data (ground-truth `g_state`/`g_text_repaired`, the shipped defects
  `g_credit_uncalled`/`g_substring`/`g_gate`, the repaired `g_credit_executed`), each with the
  properties that decide immunity, and the upstream issue + commit it models.
- `defects.py` - eleven judged episodes as data: controls and both-direction defects in both
  families, each with a `true_label` true by construction and a grounded reality note.
- `predict.py` - one pure total function from (defect, grader) to a verdict-with-rationale: a grader
  returns the true label unless the defect exploits a weakness it actually has, and ABSTAINs on a
  defect from another family.

## What it predicts (`uv run python -m judge_artifact.model`)

Execution family (graders g_state, g_credit_uncalled, g_credit_executed):
- controls x01/x02: all agree. x03 errored-call, x04 nonexistent-tool: `g_credit_uncalled`
  over-credits (SUCCESS on a real failure). x05 retry-split: it under-credits (FAILURE on a real
  success). The repaired `g_credit_executed` and the truth `g_state` recover the true label
  everywhere.

Text family (graders g_substring, g_gate, g_text_repaired):
- controls x10/x11: all agree. x12 "yesterday": `g_substring` over-credits. x13 "cannot":
  `g_substring` under-credits. x14/x15: `g_gate` over-credits a refusal that names the code or
  "leverage". `g_text_repaired` recovers the truth everywhere.

The pointed case: `g_substring`'s success COUNT equals the truth's (2 of 6) while its per-item
verdicts are scrambled in both directions - ASR magnitude hiding a wrong confusion matrix.

## Checks (`uv run pytest`, `ruff`, `mypy --strict`)

- 46 tests pass. `test_contract.py` parses the four model modules with `ast` and fails if the
  predictor imports or calls anything impure. `test_predict.py` asserts the ground-truth and
  repaired graders recover the true label everywhere, controls agree, and **each shipped defective
  grader is fooled in BOTH directions** - the thing the closest prior art could not measure.
- ruff clean, mypy --strict clean, zero third-party dependencies in the model.

Next: the neutral transcript rep + adapters, the real graders vendored verbatim (commit-pinned) with
a fidelity test, the both-direction corpus, and Arm A - observed beside predicted, any disagreement
a finding.
