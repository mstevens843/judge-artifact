"""Arm B, defense axis: does repairing the grader reorder the leaderboard?

WHY THIS AXIS AND NOT MODELS. Ranking models by a defective grader mostly preserves the order,
because the grader inflates everyone. Defenses are different, and that difference is the point: a
defense that stops the agent from CALLING the injected tool (a tool filter, a detector that aborts
the run) looks excellent to a grader that only checks whether the tool name appears, while a
defense that lets the call through but neutralises the attacker's ARGUMENTS (SecAlign-style
training, prompt-level defenses) looks like it did nothing at all. The name-only grader is not
merely noisy about defenses - it is biased by defense mechanism, and it penalises exactly the
defenses that work without blocking.

AgentDojo publishes runs for base pipelines and for defended variants of them
(`<base>-<defense>`), so the families are discovered from the corpus rather than hard-coded.

WHAT IS REPORTED. For each judge: the full ranking, Kendall tau against the state oracle's ranking,
how many positions moved, how many adjacent pairs flipped, the largest single moves, and the
inverted pairs with the widest true separation - the pairs where a reader of the defective
scoreboard would draw the most wrong conclusion. Then the same within each defense family.

If a ranking does not move, that is reported as plainly as if it does.

`uv run python -m judge_artifact.harness.arm_b_defense`
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..canonical import receipt
from .arm_b import JUDGES, Judged, judge_one, load


@dataclass(frozen=True)
class PipelineRow:
    pipeline: str
    base: str
    defense: str
    n: int
    sound_asr: float
    asr: dict[str, float]


PIPELINES_DOC = Path(__file__).resolve().parents[3] / "data" / "agentdojo" / "pipelines.json"


def load_families() -> dict[str, tuple[str, str]]:
    """Map each pipeline to (base, defense), as derived at corpus-production time.

    Read from `data/agentdojo/pipelines.json`, which `scripts/fetch_agentdojo_runs.py` builds from
    AgentDojo's own `DEFENSES` list. A name-prefix heuristic would be wrong here: `command-r-plus`
    is a different model, not a defended `command-r`, and calling it a defense family would invent
    a result out of a string.
    """
    if not PIPELINES_DOC.exists():
        raise FileNotFoundError(
            f"no pipeline map at {PIPELINES_DOC}; run scripts/fetch_agentdojo_runs.py first"
        )
    doc = json.loads(PIPELINES_DOC.read_text())
    return {
        name: (str(entry["base"]), str(entry["defense"]))
        for name, entry in doc["pipelines"].items()
    }


def kendall_tau(order_a: list[str], order_b: list[str]) -> float:
    """Kendall tau-a between two orderings of the same items. 1.0 = identical."""
    index = {m: i for i, m in enumerate(order_b)}
    seq = [index[m] for m in order_a]
    n = len(seq)
    if n < 2:
        return 1.0
    concordant = discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            if seq[i] < seq[j]:
                concordant += 1
            else:
                discordant += 1
    total = concordant + discordant
    return (concordant - discordant) / total if total else 1.0


def _rank(rows: list[PipelineRow], key: str) -> list[str]:
    """Safest first (lowest attack-success rate first), ties broken by name for determinism."""
    if key == "sound":
        return [r.pipeline for r in sorted(rows, key=lambda r: (r.sound_asr, r.pipeline))]
    return [r.pipeline for r in sorted(rows, key=lambda r: (r.asr[key], r.pipeline))]


def _compare(rows: list[PipelineRow], judge: str) -> dict[str, Any]:
    sound_order = _rank(rows, "sound")
    judge_order = _rank(rows, judge)
    pos_sound = {p: i for i, p in enumerate(sound_order)}
    pos_judge = {p: i for i, p in enumerate(judge_order)}
    moves: list[dict[str, Any]] = sorted(
        ({"pipeline": p, "sound_rank": pos_sound[p], "judge_rank": pos_judge[p],
          "moved": pos_judge[p] - pos_sound[p]} for p in sound_order),
        key=lambda m: -abs(int(str(m["moved"]))),
    )
    adjacent = sum(
        1
        for i in range(len(sound_order) - 1)
        if pos_judge[sound_order[i]] > pos_judge[sound_order[i + 1]]
    )
    by_name = {r.pipeline: r for r in rows}
    inverted: list[dict[str, Any]] = []
    for i, a in enumerate(sound_order):
        for b in sound_order[i + 1:]:
            ra, rb = by_name[a], by_name[b]
            # sound says a is safer than b; does the judge say the opposite?
            if ra.sound_asr < rb.sound_asr and ra.asr[judge] > rb.asr[judge]:
                inverted.append({
                    "safer_by_oracle": a, "safer_by_judge": b,
                    "sound_gap_pp": round((rb.sound_asr - ra.sound_asr) * 100, 1),
                    "judge_gap_pp": round((ra.asr[judge] - rb.asr[judge]) * 100, 1),
                })
    inverted.sort(key=lambda d: (-float(d["sound_gap_pp"]), str(d["safer_by_oracle"])))
    return {
        "judge": judge,
        "kendall_tau": round(kendall_tau(sound_order, judge_order), 4),
        "positions_changed": sum(1 for i, p in enumerate(sound_order) if judge_order[i] != p),
        "adjacent_pairs_flipped": adjacent,
        "ranking_inverts": sound_order != judge_order,
        "sound_ranking": sound_order,
        "judge_ranking": judge_order,
        "largest_moves": [m for m in moves if m["moved"] != 0][:5],
        "inverted_pairs_total": len(inverted),
        "worst_inverted_pairs": inverted[:5],
    }


def build_rows(rows: list[Judged]) -> list[PipelineRow]:
    names = [name for name, _ in JUDGES]
    acc: dict[str, dict[str, int]] = {}
    for r in rows:
        cell = acc.setdefault(r.pipeline, {"n": 0, "sound": 0, **{k: 0 for k in names}})
        cell["n"] += 1
        cell["sound"] += int(r.sound)
        for name in names:
            cell[name] += int(r.verdicts[name])
    families = load_families()
    out = []
    for pipeline, cell in sorted(acc.items()):
        n = cell["n"]
        base, defense = families[pipeline]
        out.append(PipelineRow(
            pipeline=pipeline, base=base, defense=defense, n=n,
            sound_asr=round(cell["sound"] / n, 4),
            asr={name: round(cell[name] / n, 4) for name in names},
        ))
    return out


def analyze(judged: list[Judged]) -> dict[str, Any]:
    rows = build_rows(judged)
    names = [name for name, _ in JUDGES]
    complete_n = max(r.n for r in rows)
    complete = [r for r in rows if r.n == complete_n]
    families: dict[str, list[PipelineRow]] = {}
    for r in rows:
        families.setdefault(r.base, []).append(r)
    family_reports = {}
    for base, members in sorted(families.items()):
        if len(members) < 2:
            continue
        family_reports[base] = {
            "members": [
                {"pipeline": m.pipeline, "defense": m.defense, "n": m.n,
                 "sound_asr": m.sound_asr, **{f"{k}_asr": m.asr[k] for k in names}}
                for m in sorted(members, key=lambda m: (m.sound_asr, m.pipeline))
            ],
            "comparisons": {k: _compare(members, k) for k in names},
        }
    return {
        "n_pipelines": len(rows),
        "n_pipelines_complete": len(complete),
        "complete_n_runs_each": complete_n,
        "pipelines": [
            {"pipeline": r.pipeline, "base": r.base, "defense": r.defense, "n": r.n,
             "sound_asr": r.sound_asr, **{f"{k}_asr": r.asr[k] for k in names}}
            for r in sorted(rows, key=lambda r: (r.sound_asr, r.pipeline))
        ],
        "all_pipelines": {k: _compare(rows, k) for k in names},
        "complete_pipelines_only": {k: _compare(complete, k) for k in names},
        "defense_families": family_reports,
    }


def render(an: dict[str, Any]) -> str:
    names = [name for name, _ in JUDGES]
    lines = [
        f"Arm B, defense axis - {an['n_pipelines']} AgentDojo pipelines "
        f"({an['n_pipelines_complete']} with the full {an['complete_n_runs_each']} runs)",
        "",
        "ranking = safest first (lowest injection-success rate first)",
        "",
        f"{'judge':12}{'tau vs oracle':>15}{'positions moved':>18}"
        f"{'adjacent flips':>16}{'inverted pairs':>16}",
    ]
    for scope, label in (("all_pipelines", "all"), ("complete_pipelines_only", "complete-n only")):
        lines.append(f"  [{label}]")
        for name in names:
            c = an[scope][name]
            lines.append(f"  {name:12}{c['kendall_tau']:>15}{c['positions_changed']:>18}"
                         f"{c['adjacent_pairs_flipped']:>16}{c['inverted_pairs_total']:>16}")
    top = an["all_pipelines"]["name_only"]
    lines += ["", "largest rank moves under the released name-only grader:"]
    for m in top["largest_moves"]:
        lines.append(f"  {m['pipeline']:48} rank {m['sound_rank']:>2} -> {m['judge_rank']:>2} "
                     f"({m['moved']:+d})")
    lines += ["", "worst inverted pairs (widest true separation the scoreboard reverses):"]
    for p in top["worst_inverted_pairs"]:
        lines.append(f"  oracle: {p['safer_by_oracle']} is safer by {p['sound_gap_pp']}pp")
        lines.append(f"  grader: {p['safer_by_judge']} looks safer by {p['judge_gap_pp']}pp")
        lines.append("")
    lines.append("defense families (base pipeline vs its defended variants):")
    for base, rep in an["defense_families"].items():
        lines.append(f"  [{base}]")
        header = f"    {'defense':34}{'n':>5}{'sound':>8}" + "".join(
            f"{k:>11}" for k in names
        )
        lines.append(header)
        for m in rep["members"]:
            lines.append(f"    {m['defense']:34}{m['n']:>5}{m['sound_asr']:>8.3f}"
                         + "".join(f"{m[f'{k}_asr']:>11.3f}" for k in names))
        for k in names:
            c = rep["comparisons"][k]
            if c["ranking_inverts"]:
                lines.append(f"      {k}: ranking INVERTS "
                             f"(tau={c['kendall_tau']}, {c['positions_changed']} moved)")
            else:
                lines.append(f"      {k}: ranking preserved (tau={c['kendall_tau']})")
    return "\n".join(lines)


def main() -> int:
    judged = [judge_one(rec) for rec in load()]
    an = analyze(judged)
    record: dict[str, Any] = {
        "arm": "B-defense-axis",
        "source": "AgentDojo banking/important_instructions, all released pipelines",
        "analysis": an,
    }
    record["receipt"] = receipt(record)
    print(render(an))
    out = Path(__file__).resolve().parents[3] / "evidence" / "arm-b-defense-axis.json"
    out.write_text(json.dumps(record, indent=2, sort_keys=True))
    print(f"\nreceipt: {record['receipt']}\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
