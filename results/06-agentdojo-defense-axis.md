# 06 - The defense axis: the ranking does invert, and it inverts against the defenses that work

Working record. Reproduce:

```
uv run python -m judge_artifact.harness.arm_b_defense
```

## The question note 03 got a null on, and why the null was an artifact

Note 03 asked whether swapping the sound oracle for a defective grader reorders the leaderboard,
and answered no: Kendall tau 1.0, zero positions changed. That answer came from four models on a
216-run sample. On the full grid - **28 pipelines, 3,986 runs**, every pipeline AgentDojo publishes
banking / important_instructions runs for - it is wrong.

```
judge         tau vs oracle   positions moved  adjacent flips  inverted pairs
  [all 28 pipelines]
  name_only            0.6825                23              13              59
  executed             0.6825                24              13              57
  arg_match            0.9524                13               7               7
  [27 pipelines with the full 144 runs each]
  name_only            0.7094                24              12              50
  executed              0.6980                22              12              50
  arg_match            0.9487                13               7               7
```

Ranking is safest-first. One pipeline (`meta-llama_Llama-3.3-70B-Instruct-repeat_user_prompt`) has
98 runs rather than 144, so the comparison is reported twice, with and without it; the conclusion
does not depend on which you read.

**The released name-only grader moves 23 of 28 pipelines and reverses 59 pairwise judgements.
Checking the attacker's arguments puts almost all of it back (tau 0.68 -> 0.95, 59 inverted pairs
-> 7).**

## Why defenses and not models

Because the bias has a mechanism, and the mechanism is about how a defense works:

- A defense that stops the agent from **calling** the injected tool - a tool filter, a detector that
  aborts the run - removes the call from the log, so a name-only grader sees the improvement.
- A defense that lets the call through but neutralises the attacker's **arguments** - SecAlign-style
  training, prompt-level defenses - leaves the call in the log, so a name-only grader sees nothing.

So the defective grader does not merely add noise to a defense comparison. It systematically
under-credits the second kind of defense. Largest moves:

```
Meta-SecAlign-70B-repeat_user_prompt                  rank  7 -> 19  (+12)
meta-llama_Llama-3.3-70B-Instruct-repeat_user_prompt  rank 17 ->  8   (-9)
Meta-SecAlign-70B                                     rank  8 -> 16   (+8)
gemini-2.0-flash-exp                                  rank 14 ->  6   (-8)
command-r                                             rank  9 -> 15   (+6)
```

Meta-SecAlign is a prompt-injection-robust model. By the state oracle it is one of the safest
pipelines in the grid (`sound` 0.090 / 0.097). By the released grader it looks middling (0.438 /
0.410), because the agent still calls `send_money` - with the user's arguments. Checking the
arguments restores it (0.111 / 0.125).

The pair whose reversal is most misleading:

```
oracle: Meta-SecAlign-70B-repeat_user_prompt is safer by 22.2pp
grader: claude-3-sonnet-20240229            looks safer by  2.8pp
```

## Within a defense family

Families are resolved from AgentDojo's own `DEFENSES` list, extracted from
`src/agentdojo/agent_pipeline/agent_pipeline.py` by the fetch script and committed to
`data/agentdojo/pipelines.json` - not from a name prefix. `command-r-plus` is a different model,
not a defended `command-r`, and a prefix heuristic that said otherwise would have invented a
family; `tests/test_arm_d.py` pins that it does not.

```
[gpt-4o-2024-05-13]
  defense                          n   sound  name_only  executed  arg_match
  transformers_pi_detector       144   0.007      0.042     0.042      0.021
  tool_filter                    144   0.111      0.312     0.299      0.160
  repeat_user_prompt             144   0.465      0.646     0.632      0.486
  spotlighting_with_delimiting   144   0.618      0.736     0.722      0.639
  none                           144   0.625      0.722     0.715      0.646
    name_only: ranking INVERTS (tau=0.8)   executed: INVERTS (tau=0.8)   arg_match: preserved

[Meta-SecAlign-70B]
  repeat_user_prompt             144   0.090      0.438     0.438      0.111
  none                           144   0.097      0.410     0.410      0.125
    name_only: ranking INVERTS (tau=-1.0)  executed: INVERTS (tau=-1.0)  arg_match: preserved

[meta-llama_Llama-3.3-70B-Instruct]
  repeat_user_prompt              98   0.255      0.276     0.265      0.265
  none                           144   0.507      0.611     0.611      0.562
    ranking preserved under every judge
```

In the gpt-4o family the oracle says `spotlighting_with_delimiting` is very slightly safer than no
defense at all (0.618 vs 0.625) and the released grader says the opposite (0.736 vs 0.722): a
reader of the defective scoreboard would conclude that adding spotlighting made things worse. In
the Meta-SecAlign family the released grader reverses the two-way comparison outright. In both, the
argument check restores the oracle's order.

## Stated plainly

This is one suite and one attack, on released runs whose pipelines were not all produced under
identical conditions - the numbers are AgentDojo's, and the counterfactual is what an Inspect-style
grader would report over them. Within that scope, the claim is narrow and measured: **the absolute
rate is mostly grader artifact, and on the defense axis so is the ordering** - and the specific
repair that fixes the absolute number also fixes most of the ordering.
