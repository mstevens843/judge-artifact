# 04 - Arm C, judge nondeterminism measurement path

Working record. The default command makes no model calls and writes a receipted readiness record:

```
uv run python -m judge_artifact.harness.arm_c
```

To perform the real temperature-controlled measurement later, use an Inspect model API substrate
with credentials present and an explicit paid-call opt-in:

```
uv run --extra fidelity python -m judge_artifact.harness.arm_c \
  --provider inspect --model openai/gpt-4.1-mini --temperature 1.0 --n 30 --allow-paid-api
```

The local CLI smoke path is still available, but it is not the #4136 measurement:

```
uv run python -m judge_artifact.harness.arm_c --provider cli --n 4 --allow-paid-api
```

## What #4136 Requires

inspect_ai#4136 is about model-graded scorers calling the grader with no `GenerateConfig`, leaving
the provider default temperature (1.0) and no seed to decide identical judge prompts. The faithful
measurement therefore runs the same borderline judge prompt repeatedly at a specified temperature,
seed if supported, and model name, then records every verdict, flip rate, pooled ASR and Wilson
confidence interval.

That path is now implemented through `inspect_ai.model.get_model` with an explicit
`GenerateConfig(temperature=..., seed=..., max_tokens=...)`. The harness validates the config,
checks common provider credential environment variables, and refuses to make provider or CLI model
calls unless `--allow-paid-api` is present.

## What Was Measured Here

No real API measurement was performed on this machine. The current evidence record says:

```
status = implemented_not_measured
provider = none
temperature = 1.0
n_per_item = 30
prompt_case_ids = ["b1", "b2"]
reason = no provider selected; no model calls made
```

Receipt: `ja1_33bfcab40b1a58e99b91b04f22f165603c21f8468d66c61a947b93c3866679d5`.

The old local Claude CLI route remains useful as a substrate smoke test, but it exposes no
temperature control. A stable CLI result would not bound the raw temperature-1.0 condition, so this
note does not cite one.
