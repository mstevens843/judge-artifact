"""Print the predicted disagreement matrix. `python -m judge_artifact.model`.

This is the model talking to a human. It reads nothing, runs no grader, and reaches no network; it
renders the pure prediction in ``predict.PREDICTED`` so a reader can see, before any exploit
transcript exists, which grader is predicted to disagree with the truth on which defect and why. The
harness later prints the same shape with an observed column beside the predicted one.
"""

from __future__ import annotations

from .defects import DEFECTS
from .graders import GRADERS
from .layers import Family, Verdict
from .predict import PREDICTED, summarize

_SYM = {Verdict.SUCCESS: "SUCC", Verdict.FAILURE: "fail", Verdict.ABSTAIN: "  . "}


def render() -> str:
    lines: list[str] = []
    head = f"{'defect':26}" + "".join(f"{g.id.removeprefix("g_"):>10}" for g in GRADERS)
    lines.append(head)
    lines.append("-" * len(head))
    for fam in (Family.EXECUTION, Family.SUBSTRING, Family.GATE):
        lines.append(f"[{fam.value} family]")
        for d in DEFECTS:
            if d.family is not fam:
                continue
            row = f"  {d.id} {d.slug:21}"[:26]
            for g in GRADERS:
                row += f"{_SYM[PREDICTED[d.id][g.id].verdict]:>10}"
            tag = "  (control)" if d.is_control else f"  ({d.direction.value})"
            lines.append(row + tag)
    lines.append("")
    for g in GRADERS:
        s = summarize(g)
        tags = []
        if g.is_ground_truth:
            tags.append("GROUND-TRUTH")
        elif g.is_sound:
            tags.append("sound")
        if g.is_shipped_defect:
            tags.append("SHIPPED-DEFECT")
        if not tags:
            tags.append("trace-only repair (not shipped, not sound)")
        lines.append(
            f"{g.id:20} success={len(s.success)} failure={len(s.failure)} "
            f"abstain={len(s.abstain)}  {' '.join(tags)}"
        )
    lines.append("")
    lines.append("Legend: SUCC scored attack-success, fail scored no-success, '.' abstain "
                 "(grader does not read this family). An over-credit is a fail turned SUCC.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(render())
