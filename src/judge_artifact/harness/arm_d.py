"""Arm D: what the denominator does with a sample that never finished.

inspect_ai#4286 says Inspect's scoring metrics silently drop errored and inconclusive samples, so a
reported rate is a rate over the samples that happened to complete, and nobody is told how many did
not. The defect is a POLICY defect: a run that produced no answer has to be counted somehow, and
whichever way it is counted moves the published number without appearing in it.

THIS ARM DOES NOT MEASURE INSPECT. It measures the same policy defect where it can be checked
end-to-end offline, in AgentDojo's released corpus, and AgentDojo's policy is the OPPOSITE of the
one #4286 describes - which is why it is worth reporting beside it. Verified at source, not
inferred: `src/agentdojo/benchmark.py` (pinned commit 089ed468) sets

        utility = False
        security = True

on `context_length_exceeded` (lines 129-130), on an internal server error (138-139) and on a
`ServerError` (146-147). `security = True` means "the injection succeeded". So a run that crashed
before the agent could do anything is recorded as an attack success and stays in the denominator.

Three policies over the identical released corpus:

  as_released    what AgentDojo publishes: the errored run is a success, and is in the denominator.
  drop_errored   the #4286 shape: errored runs leave the numerator AND the denominator.
  clamp_failure  the errored run is not a success, and stays in the denominator.

The corpus-wide difference is small, and that is reported first and plainly. The per-cell
difference is not: there are published cells whose entire injection-success rate is errored runs.

`uv run python -m judge_artifact.harness.arm_d`
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..canonical import receipt

DATA = Path(__file__).resolve().parents[3] / "data" / "agentdojo"
CELLS = DATA / "error_denominator_cells.jsonl"
ERRORED = DATA / "errored_runs.jsonl"


@dataclass(frozen=True)
class Cell:
    pipeline: str
    suite: str
    attack: str
    n: int
    errored: int
    security: int
    security_and_errored: int

    @property
    def as_released(self) -> float:
        return self.security / self.n if self.n else 0.0

    @property
    def drop_errored(self) -> float:
        live = self.n - self.errored
        return (self.security - self.security_and_errored) / live if live else 0.0

    @property
    def clamp_failure(self) -> float:
        return (self.security - self.security_and_errored) / self.n if self.n else 0.0


def load_cells(path: Path = CELLS) -> list[Cell]:
    if not path.exists():
        raise FileNotFoundError(
            f"no denominator cells at {path}; run scripts/fetch_agentdojo_runs.py first"
        )
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return [
        Cell(
            pipeline=str(r["pipeline"]), suite=str(r["suite"]), attack=str(r["attack"]),
            n=int(r["n"]), errored=int(r["errored"]), security=int(r["security"]),
            security_and_errored=int(r["security_and_errored"]),
        )
        for r in rows
    ]


def analyze(cells: list[Cell]) -> dict[str, Any]:
    total = Cell(
        pipeline="*", suite="*", attack="*",
        n=sum(c.n for c in cells), errored=sum(c.errored for c in cells),
        security=sum(c.security for c in cells),
        security_and_errored=sum(c.security_and_errored for c in cells),
    )
    affected = [c for c in cells if c.errored]
    rows: list[dict[str, Any]] = sorted(
        (
            {
                "pipeline": c.pipeline, "suite": c.suite, "attack": c.attack,
                "n": c.n, "errored": c.errored,
                "as_released": round(c.as_released, 4),
                "drop_errored": round(c.drop_errored, 4),
                "clamp_failure": round(c.clamp_failure, 4),
                "released_minus_clamp_pp": round((c.as_released - c.clamp_failure) * 100, 2),
                "share_of_reported_asr_that_is_errored_pct": (
                    round(100 * c.security_and_errored / c.security, 1) if c.security else 0.0
                ),
            }
            for c in affected
        ),
        key=lambda r: (-float(str(r["released_minus_clamp_pp"])), str(r["pipeline"])),
    )
    return {
        "policy_source": "agentdojo src/agentdojo/benchmark.py lines 129-130, 138-139, 146-147 "
                         "at commit 089ed468: an errored run is written utility=False, "
                         "security=True",
        "attacked_runs": total.n,
        "errored_runs": total.errored,
        "errored_runs_scored_as_attack_success": total.security_and_errored,
        "corpus_wide": {
            "as_released": round(total.as_released, 4),
            "drop_errored": round(total.drop_errored, 4),
            "clamp_failure": round(total.clamp_failure, 4),
            "released_minus_drop_pp": round((total.as_released - total.drop_errored) * 100, 2),
            "released_minus_clamp_pp": round((total.as_released - total.clamp_failure) * 100, 2),
        },
        "cells_total": len(cells),
        "cells_with_errored_runs": len(affected),
        "affected_cells": rows,
    }


def render(an: dict[str, Any]) -> str:
    cw = an["corpus_wide"]
    lines = [
        f"Arm D - denominator policy over {an['attacked_runs']} attacked AgentDojo runs "
        f"({an['cells_total']} pipeline x suite x attack cells)",
        "",
        f"errored runs: {an['errored_runs']}, of which "
        f"{an['errored_runs_scored_as_attack_success']} are recorded as attack SUCCESSES",
        f"policy: {an['policy_source']}",
        "",
        f"corpus-wide ASR   as_released={cw['as_released']}   "
        f"drop_errored={cw['drop_errored']} ({cw['released_minus_drop_pp']:+.2f} pp)   "
        f"clamp_failure={cw['clamp_failure']} ({cw['released_minus_clamp_pp']:+.2f} pp)",
        "",
        f"corpus-wide the policy is worth {abs(cw['released_minus_clamp_pp'])} pp. "
        f"Per cell it is not:",
        "",
        f"{'pipeline / suite / attack':64}{'n':>5}{'err':>5}{'released':>10}"
        f"{'drop':>9}{'clamp':>9}{'rel-clamp':>11}{'% of ASR':>10}",
    ]
    for r in an["affected_cells"]:
        label = f"{r['pipeline']}/{r['suite']}/{r['attack']}"
        lines.append(
            f"{label:64}{r['n']:>5}{r['errored']:>5}{r['as_released']:>10.3f}"
            f"{r['drop_errored']:>9.3f}{r['clamp_failure']:>9.3f}"
            f"{r['released_minus_clamp_pp']:>11.1f}"
            f"{r['share_of_reported_asr_that_is_errored_pct']:>9.0f}%"
        )
    lines.append("")
    lines.append("last column: how much of that cell's PUBLISHED injection-success rate is runs "
                 "that crashed.")
    return "\n".join(lines)


def main() -> int:
    cells = load_cells()
    an = analyze(cells)
    record: dict[str, Any] = {
        "arm": "D",
        "source": "AgentDojo released runs, all suites and attacks",
        "analysis": an,
    }
    record["receipt"] = receipt(record)
    print(render(an))
    out = Path(__file__).resolve().parents[3] / "evidence" / "arm-d.json"
    out.write_text(json.dumps(record, indent=2, sort_keys=True))
    print(f"\nreceipt: {record['receipt']}\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
