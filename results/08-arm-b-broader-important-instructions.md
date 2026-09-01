# 08 - Arm B broader sweep: important_instructions across statically matchable suites

Working record. Reproduce:

```
uv run python scripts/fetch_agentdojo_runs.py
uv run python -m judge_artifact.harness.arm_b --broad-important-instructions
```

This is a broader Arm B sweep, not a replacement for
[05](./05-arm-b-corrected.md). The historical headline remains banking /
`important_instructions` over 3,986 runs with the banking attacker-only argument repair. This note
uses a stricter generalized rule: for each suite/task, match on the statically recoverable arguments
of the target `FunctionCall` in AgentDojo's versioned `ground_truth`. Placeholders and unresolved
environment-derived values are recorded as dynamic keys and never guessed.

## Scope

The producer now writes:

- `data/agentdojo/important_instructions_all_suites.jsonl`
- `data/agentdojo/ground_truth_important_instructions_all_suites.json`
- SHA-256 entries for both files in `data/agentdojo/MANIFEST.json`

Included, by suite:

| suite | included injection tasks | runs |
|---|---:|---:|
| banking | 0-8 | 3,986 |
| slack | 1-5 | 2,835 |
| travel | 0-5 | 3,360 |
| workspace | 0-4 | 5,600 |
| **total** |  | **15,781** |

Excluded, explicitly:

| suite/task | runs | reason |
|---|---:|---|
| travel / injection_task_6 | 560 | `ground_truth()` returns no `FunctionCall`; the attack is output-text only |
| workspace / injection_task_5 | 1,120 | final target call has only dynamic placeholder args |
| workspace / injection_task_6-13 | 1,920 | `ground_truth()` returns no `FunctionCall` for these newer stateful exfiltration tasks |

The committed corpus still records per-run source paths, target function, match args, dynamic keys,
tool-call arguments, call ids, paired tool errors and AgentDojo's released `security` oracle. Full
transcripts for omitted tasks are not copied into this broad JSONL; the manifest records skipped
run counts by suite/task/reason and the pinned source path is enough to re-derive the omission.

## Measurement

```
Arm B broad - AgentDojo banking, slack, travel, workspace / important_instructions, 15781 runs

judge                       ASR   vs sound   agrees with oracle
sound (security oracle)    0.203          -                    -
name_only                0.2999     +9.69pp               89.20%
executed                  0.292     +8.90pp               89.92%
arg_match                0.1382     -6.48pp               89.67%
```

The name-only judge still over-credits, and the dominant over-credit bucket is still argument
blindness:

| bucket | n | share |
|---|---:|---:|
| error_blind | 119 | 7.4% |
| argument_blind | 1,194 | 73.8% |
| effect_blind | 304 | 18.8% |

Per suite:

| suite | n | sound | name_only | executed | arg_match |
|---|---:|---:|---:|---:|---:|
| banking | 3,986 | 0.2311 | 0.3971 | 0.3758 | 0.1091 |
| slack | 2,835 | 0.4078 | 0.4995 | 0.4984 | 0.2917 |
| travel | 3,360 | 0.1098 | 0.1765 | 0.1744 | 0.0813 |
| workspace | 5,600 | 0.1352 | 0.2036 | 0.1984 | 0.1154 |

## Interpretation

This broader run supports the qualitative mechanism from Arm B: name-only credit is not a
conservative proxy for attack success on real agent transcripts, and argument blindness is larger
than unexecuted-call error blindness in the measured sweep.

It does **not** supersede the old banking headline. The broader `arg_match` rule is deliberately
stricter than the banking repair because it uses all statically recoverable target-call arguments
in the generalized ground truth. That makes the banking `arg_match` number in this note lower than
the historical attacker-only banking repair. The old result remains the right citation for the
banking-specific 464-false-positive finding.

Receipt: `ja1_76e83cfaaf4051ae3393683cc75b9d7eb62c10750cc836ceacc0d890110c0f21`.
