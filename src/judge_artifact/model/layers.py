"""The vocabulary the whole model is derived from.

WHAT THIS IS. The enumerated properties of a success grader and of a grader-defect, plus the
three-valued verdict a grader returns on one judged episode. Every other file in ``model/`` is
built out of these, and ``predict.py`` is a pure function over them.

WHY IT EXISTS SEPARATELY. The point of this project is to model the judge before writing a single
exploit transcript (the pattern that paid off in the sibling project cheat-oracle, where the harness
caught the model mispredicting and it was corrected in public). The model has to name its terms
once so the predicted disagreement matrix is a derivation over declared properties, not a table
a reviewer cannot check.

WHAT WAS REJECTED. Treating every grader as consuming the same input. It does not: the
execution-credit graders read a transcript's tool calls and errors, while the text graders read a
harm-judge's answer string. Pretending one input fits all would force a false verdict wherever a
grader cannot actually see what a defect exploits. So a grader and a defect each carry a ``Family``,
and a grader ABSTAINs on a defect from another family rather than being scored as if it judged.

WHAT THIS IS NOT. It is not a description of any one grader's source. It is the abstract model those
graders are instances of; the real, commit-pinned functions live under ``graders/vendored/`` and the
harness exists to catch the model being wrong about them.
"""

from __future__ import annotations

from enum import Enum


class Verdict(Enum):
    """What a grader says about one judged episode.

    SUCCESS - the grader scored the attack (or harmful behavior) as having succeeded. A true
              positive when the attack really succeeded; a false positive (over-credit) when it did
              not - and an over-credit inflates a reported attack-success rate.
    FAILURE - the grader scored it as not succeeding. A false negative (under-credit) when the
              attack really did succeed, which deflates the rate and hides a real vulnerability.
    ABSTAIN - the grader does not apply to this episode (it reads a feature this episode does not
              carry) or could not parse it. This is the value inspect_ai#4286 silently drops from
              the denominator; here it is explicit and never scored as SUCCESS or FAILURE.
    """

    SUCCESS = "success"
    FAILURE = "failure"
    ABSTAIN = "abstain"


class Family(Enum):
    """Which feature of an episode a grader reads, and therefore which defects can fool it. Split
    three ways because a substring answer-parser and a whole-response keyword gate read different
    things and cannot grade each other's episodes.

    EXECUTION - reads the tool-call log and the paired tool-response error (AgentHarm, #2108).
                Fully decidable from the trace: a sound grader here never abstains.
    SUBSTRING - reads a harm-judge's `<answer>` string (agentic_misalignment, #2310).
    GATE      - reads the whole response for a keyword (agentic_misalignment gates, #2292 / #2293).

    The SUBSTRING and GATE families each carry a floor item - keyword-avoiding harm - that NO
    deterministic grader can settle; there the sound grader abstains and only a semantic judge
    (Arm C) could decide, imperfectly. That floor is named, not hidden.
    """

    EXECUTION = "execution"
    SUBSTRING = "substring"
    GATE = "gate"


class DefectClass(Enum):
    """The mechanism a defect exploits. A grader is fooled iff it has the matching weakness.

    CREDIT_UNCALLED     - a tool call that errored or named a nonexistent tool is credited the same
                          as one that ran (inspect_evals#2108, `is_function_called` ignores the
                          tool `error`).
    OVERCORRECT_ERROR   - the reverted #2108 fix treats ANY tool error as a rejection and skips the
                          call, so a call that errored non-fatally but still achieved its effect is
                          under-credited. This is why the fix was reverted (inspect_evals#2108
                          reopened: "the merge opened up more issues").
    SUBSTRING_CONTAINMENT - the verdict is decided by `"yes" in answer` / `"no" in answer`, so
                          `"yesterday"` reads as yes and `"cannot"`/`"not"` flip a yes to no
                          (inspect_evals#2310).
    GATE_OVER_RESPONSE  - a keyword gate runs over the entire response (including reasoning) rather
                          than the action taken, so a refusal that names the thing is counted as
                          doing it (inspect_evals#2292, #2293).
    NONE                - a control episode with no defect; every applicable grader must agree.
    """

    CREDIT_UNCALLED = "credit_uncalled"
    OVERCORRECT_ERROR = "overcorrect_error"
    SUBSTRING_CONTAINMENT = "substring_containment"
    GATE_OVER_RESPONSE = "gate_over_response"
    NONE = "none"


class Direction(Enum):
    """Which way a defect pushes a fooled grader's verdict, relative to the truth.

    OVER_CREDIT  - the grader says SUCCESS when the truth is FAILURE. Inflates the reported rate.
    UNDER_CREDIT - the grader says FAILURE when the truth is SUCCESS. Deflates it, hides a real hit.
    NONE         - a control; no grader is fooled.

    An audit that only exhibits OVER_CREDIT is not an audit - it cannot tell an inflated number from
    a deflated one. The discrimination test requires both directions in both families.
    """

    OVER_CREDIT = "over_credit"
    UNDER_CREDIT = "under_credit"
    NONE = "none"
