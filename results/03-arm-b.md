# 03 - Arm B, rank inversion on real AgentDojo data

Working record. The execution defect now meets real released transcripts. Reproduce:

```
uv run python -m judge_artifact.harness.arm_b
```

## The sample

216 AgentDojo runs (MIT), banking suite, `important_instructions` attack, 54 each across four
models (claude-3-5-sonnet-20241022, claude-3-opus-20240229, gpt-4-turbo-2024-04-09,
gemini-1.5-pro-002), injection tasks 0-8 x user tasks 0-5. A bounded, documented sample - one suite
and one attack, not the whole grid; a wider sweep is future work and named as such, never a silent
truncation. Each run carries AgentDojo's released deterministic `security` verdict (the sound
oracle) and its full tool-call log. The injection target tool per task was extracted from
AgentDojo's `injection_tasks.py` GROUND_TRUTH (mostly `send_money`).

## The result

Sound ASR = mean(`security`); defective ASR = the #2108 read (the target tool was CALLED at all,
error and effect ignored).

```
model                        n   sound ASR   defective ASR   over-credit pp
gpt-4-turbo-2024-04-09      54      0.500          0.741          +24.1
gemini-1.5-pro-002         54      0.222          0.500          +27.8
claude-3-opus-20240229     54      0.056          0.389          +33.3
claude-3-5-sonnet-20241022 54      0.019          0.370          +35.2
```

**The defective grader inflates the reported injection-success rate by 24 to 35 percentage points on
real transcripts.** For claude-3-5-sonnet the sound rate is 1.9% and the defective rate is 37.0% - a
twentyfold inflation of the absolute number. An absolute safety claim ("this model's agents fell to
the injection only 2% of the time") is almost entirely grader artifact under the #2108 read.

**The ranking does not invert (Kendall tau = 1.0, 0 positions changed).** On this sample the
defective grader inflates every model by a similar amount, so the leaderboard order survives. That
is the honest answer to the rank-inversion question here, and it is worth stating: the artifact
dominates the ABSOLUTE number while the RELATIVE ordering is robust on this suite and attack. Whether
a different suite or attack (where models differ in how often the called target actually succeeds)
would invert the order is the open question a wider sweep would answer.

## What this arm is, and is not

It is a faithful counterfactual: AgentDojo's own sound `security` oracle versus the shipped
#2108-style credit-the-call-anyway read, on identical released transcripts, with a receipt
(`evidence/arm-b.json`). It is not a claim about AgentDojo's own numbers, which use the sound oracle;
it measures what a defective grader of the kind that ships in AgentHarm would report on this data. It
is bounded to one suite and one attack.

Next: Arm C measures the unseeded LLM judge's per-item flip rate and the ASR confidence interval
(inspect_ai#4136), the one arm that makes model calls.
