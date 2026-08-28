"""Arm A: run the real graders over the constructed corpus, beside the prediction.

Fills an observed verdict for every (defect, grader) pair, diffs it against ``predict.PREDICTED``,
and computes the both-direction confusion the whole project rests on: for each shipped defective
grader, how often it over-credits (SUCCESS where the truth is FAILURE) and under-credits (FAILURE
where the truth is SUCCESS). Writes evidence/arm-a.json with a canonical-JSON SHA-256 receipt so the
table is measured, not remembered.

`uv run python -m judge_artifact.harness.arm_a`
"""

from __future__ import annotations

import json
from pathlib import Path

from ..canonical import receipt
from ..corpus.episodes import CORPUS
from ..graders.registry import grade
from ..model.defects import DEFECTS
from ..model.graders import GRADERS
from ..model.layers import Verdict
from ..model.predict import PREDICTED

_SYM = {Verdict.SUCCESS: "SUCC", Verdict.FAILURE: "fail", Verdict.ABSTAIN: "  . "}


def observe() -> dict[str, dict[str, Verdict]]:
    obs: dict[str, dict[str, Verdict]] = {}
    for d in DEFECTS:
        ep = CORPUS[d.id]
        row: dict[str, Verdict] = {}
        for g in GRADERS:
            row[g.id] = grade(g.id, ep) if g.family is d.family else Verdict.ABSTAIN
        obs[d.id] = row
    return obs


def analyze(obs: dict[str, dict[str, Verdict]]) -> dict[str, object]:
    disagreements = []
    for d in DEFECTS:
        for g in GRADERS:
            pv = PREDICTED[d.id][g.id].verdict
            ov = obs[d.id][g.id]
            if pv is not ov:
                disagreements.append({"defect": d.id, "grader": g.id,
                                      "predicted": pv.value, "observed": ov.value})
    # both-direction confusion for each shipped defective grader
    confusion = {}
    for g in GRADERS:
        if not g.is_shipped_defect:
            continue
        over, under = [], []
        for d in DEFECTS:
            if d.family is not g.family:
                continue
            truth = d.true_label
            got = obs[d.id][g.id]
            if got is Verdict.SUCCESS and truth is Verdict.FAILURE:
                over.append(d.id)
            elif got is Verdict.FAILURE and truth is Verdict.SUCCESS:
                under.append(d.id)
        confusion[g.id] = {"over_credit": over, "under_credit": under}
    # the floor: items no grader in the family scores as the true SUCCESS
    floor = [d.id for d in DEFECTS if not d.decidable]
    return {"disagreements": disagreements, "confusion": confusion, "floor": floor}


def render(obs: dict[str, dict[str, Verdict]], an: dict[str, object]) -> str:
    lines = ["Arm A - constructed corpus, predicted(P) vs observed(O)",
             f"{'defect':26}" + "".join(f"{g.id.replace('g_',''):>12}" for g in GRADERS),
             "-" * (26 + 12 * len(GRADERS))]
    for d in DEFECTS:
        row = f"{d.id} {d.slug:21}"[:26]
        for g in GRADERS:
            pv = PREDICTED[d.id][g.id].verdict
            ov = obs[d.id][g.id]
            mark = _SYM[ov].strip() if pv is ov else f"{_SYM[pv].strip()}!{_SYM[ov].strip()}"
            row += f"{mark:>12}"
        lines.append(row)
    lines.append("")
    confusion = an["confusion"]
    assert isinstance(confusion, dict)
    for gid, c in confusion.items():
        lines.append(f"{gid}: over-credit={c['over_credit']} under-credit={c['under_credit']}")
    lines.append(f"floor (no deterministic grader recovers the truth): {an['floor']}")
    dis = an["disagreements"]
    lines.append(f"predicted-vs-observed disagreements: {dis}")
    return "\n".join(lines)


def main() -> int:
    obs = observe()
    an = analyze(obs)
    record: dict[str, object] = {
        "arm": "A",
        "observed": {d: {g: obs[d][g].value for g in obs[d]} for d in obs},
        "analysis": an,
    }
    record["receipt"] = receipt(record)
    print(render(obs, an))
    out = Path(__file__).resolve().parents[3] / "evidence" / "arm-a.json"
    out.write_text(json.dumps(record, indent=2, sort_keys=True))
    print(f"\nreceipt: {record['receipt']}\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
