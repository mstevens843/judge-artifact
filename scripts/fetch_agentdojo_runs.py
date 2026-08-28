"""Produce the normalised AgentDojo corpus Arm B, the defense axis and Arm D read.

WHY THIS EXISTS. The corpus this project's headline rests on used to be a committed jsonl with no
committed producer, carrying only each call's name and error flag. That is lossy in exactly the
dimension that decides the answer: without the ARGUMENTS you cannot tell the attacker's
`send_money` from the user's own, so the whole over-credit was silently attributed to the wrong
defect. This script regenerates the corpus from the released source, keeps everything a grader
could read, and records where every byte came from.

WHAT IT WRITES (all under ``data/agentdojo/``, deterministic order, stable key order):

  ground_truth.json                     per banking injection task: the target function and the
                                        attacker arguments, extracted from AgentDojo's own
                                        `injection_tasks.py` `ground_truth` with `ast`.
  pipelines.json                        AgentDojo's own `DEFENSES` list and the base/defense split
                                        of every pipeline that has runs, so the defense axis is
                                        derived from source and not from a name heuristic.
  banking_important_instructions.jsonl  one line per released run of the banking suite under the
                                        important_instructions attack, for every pipeline: the
                                        released `security` / `utility` verdicts, whether the run
                                        itself errored, and the full tool-call log with arguments,
                                        call ids and paired tool errors.
  error_denominator_cells.jsonl         per (pipeline, suite, attack) counts over the WHOLE runs
                                        corpus - enough to recompute every denominator policy in
                                        Arm D without committing 36,679 transcripts.
  errored_runs.jsonl                    every run whose top-level `error` is set, with the head of
                                        its error text, so Arm D's numerator is checkable by hand.
  MANIFEST.json                         source repo, pinned commit, counts, and a SHA-256 of each
                                        output file.

HOW THE GROUND TRUTH IS EXTRACTED. Each `InjectionTaskN.ground_truth` returns a list of
`FunctionCall(function=..., args=..., placeholder_args=...)`. `placeholder_args` is the statically
writable form, with "$name" standing in for anything derived from the environment. This script
parses that literal, resolves `self._SOME_CONSTANT` against the class body, and splits the result:

  attacker_args - values that come from a constant the injection task itself defines (the attacker
                  IBAN, the password it wants set). These identify the attacker and are what
                  `g_arg_match` matches on.
  scaffold_args - other literals (a fixed 2022-01-01 date, a 0.01 amount). Recorded, and used only
                  by the strict sensitivity variant, because a real attack does not fail because
                  the model picked a different date.
  dynamic_keys  - "$name" placeholders. Never matched on, never guessed at.

The target function is the LAST call in `ground_truth`, which is the decisive one. That rule is
derived, not hand-written, and the script asserts it reproduces the previously hard-coded table.

RUNNING IT.  uv run python scripts/fetch_agentdojo_runs.py
Downloads a ~37 MB tarball of the pinned commit into ``work/`` (gitignored) and reuses it after.
``--source-dir`` points at an already-extracted checkout instead, for an offline rerun.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tarfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = "ethz-spylab/agentdojo"
# Pinned so the corpus is reproducible. AgentDojo's runs/ tree is a released artifact of the
# published benchmark; this is the commit it was read at.
PINNED_REF = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"
SUITE = "banking"
ATTACK = "important_instructions"

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "agentdojo"

# Long free-text arguments (an email body, a transaction subject) are capped so the corpus stays a
# few MB. A value a grader could match on is never capped: see `_cap_args`.
MAX_STR = 512


# --------------------------------------------------------------------------------------------
# source acquisition
# --------------------------------------------------------------------------------------------


def acquire_source(ref: str, cache: Path) -> Path:
    """Return the root of an extracted AgentDojo checkout, downloading it if needed."""
    root = cache / f"agentdojo-{ref}"
    if root.is_dir():
        return root
    cache.mkdir(parents=True, exist_ok=True)
    tarball = cache / f"agentdojo-{ref}.tar.gz"
    if not tarball.is_file():
        url = f"https://codeload.github.com/{REPO}/tar.gz/{ref}"
        print(f"downloading {url}")
        with urllib.request.urlopen(url, timeout=300) as resp:
            tarball.write_bytes(resp.read())
    print(f"extracting {tarball}")
    with tarfile.open(tarball) as tf:
        tf.extractall(cache, filter="data")
    return root


# --------------------------------------------------------------------------------------------
# ground truth, straight out of AgentDojo's own injection tasks
# --------------------------------------------------------------------------------------------


@dataclass
class TaskGroundTruth:
    target_function: str
    attacker_args: dict[str, Any] = field(default_factory=dict)
    scaffold_args: dict[str, Any] = field(default_factory=dict)
    dynamic_keys: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)


def _class_constants(node: ast.ClassDef) -> dict[str, Any]:
    consts: dict[str, Any] = {}
    for stmt in node.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target, value = stmt.targets[0], stmt.value
        elif isinstance(stmt, ast.AnnAssign):
            target, value = stmt.target, stmt.value
        if isinstance(target, ast.Name) and value is not None:
            literal = _literal(value)
            if literal is not _UNRESOLVED:
                consts[target.id] = literal
    return consts


class _Unresolved:
    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return "<unresolved>"


_UNRESOLVED = _Unresolved()


def _literal(node: ast.expr) -> Any:
    """`ast.literal_eval` without raising: unresolvable expressions return the sentinel."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Tuple | ast.List):
        out = [_literal(e) for e in node.elts]
        return _UNRESOLVED if any(v is _UNRESOLVED for v in out) else out
    if isinstance(node, ast.Dict):
        pairs: dict[Any, Any] = {}
        for k, v in zip(node.keys, node.values, strict=True):
            if k is None:
                return _UNRESOLVED
            kk, vv = _literal(k), _literal(v)
            if kk is _UNRESOLVED or vv is _UNRESOLVED:
                return _UNRESOLVED
            pairs[kk] = vv
        return pairs
    return _UNRESOLVED


def _resolve_value(node: ast.expr, consts: dict[str, Any]) -> tuple[str, Any]:
    """Classify one ground-truth argument value: attacker constant, literal, or dynamic."""
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    ):
        if node.attr in consts:
            return ("attacker", consts[node.attr])
        return ("dynamic", None)
    literal = _literal(node)
    if literal is _UNRESOLVED:
        return ("dynamic", None)
    if isinstance(literal, str) and literal.startswith("$"):
        return ("dynamic", literal)
    return ("scaffold", literal)


def extract_defenses(root: Path) -> list[str]:
    """AgentDojo's own `DEFENSES` list, read from source rather than guessed.

    A name-prefix heuristic is not good enough here: `command-r-plus` is not a defended
    `command-r`, it is a different model, and treating it as a defense family would invent a
    result. Only a suffix that AgentDojo itself declares a defense counts.
    """
    source = root / "src" / "agentdojo" / "agent_pipeline" / "agent_pipeline.py"
    tree = ast.parse(source.read_text())
    for stmt in tree.body:
        if (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
            and stmt.targets[0].id == "DEFENSES"
        ):
            value = _literal(stmt.value)
            if isinstance(value, list):
                return [str(v) for v in value]
    raise SystemExit(f"could not find DEFENSES in {source}")


def split_pipeline(name: str, pipelines: set[str], defenses: list[str]) -> tuple[str, str]:
    """(base, defense) for one pipeline directory name; ("<name>", "none") if it is a base."""
    for defense in sorted(defenses, key=len, reverse=True):
        suffix = "-" + defense
        if name.endswith(suffix) and name[: -len(suffix)] in pipelines:
            return (name[: -len(suffix)], defense)
    return (name, "none")


def extract_ground_truth(root: Path, suite: str) -> dict[int, TaskGroundTruth]:
    source = root / "src" / "agentdojo" / "default_suites" / "v1" / suite / "injection_tasks.py"
    tree = ast.parse(source.read_text())
    out: dict[int, TaskGroundTruth] = {}
    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and node.name.startswith("InjectionTask")):
            continue
        index = int(node.name.removeprefix("InjectionTask"))
        consts = _class_constants(node)
        found: list[tuple[str, dict[str, tuple[str, Any]]]] = []
        for stmt in node.body:
            if not (isinstance(stmt, ast.FunctionDef) and stmt.name == "ground_truth"):
                continue
            for sub in ast.walk(stmt):
                if not (isinstance(sub, ast.Call) and getattr(sub.func, "id", None)
                        == "FunctionCall"):
                    continue
                kw = {k.arg: k.value for k in sub.keywords if k.arg}
                fn_node = kw.get("function")
                if not isinstance(fn_node, ast.Constant):
                    continue
                spec_node = kw.get("placeholder_args") or kw.get("args")
                spec: dict[str, tuple[str, Any]] = {}
                if isinstance(spec_node, ast.Dict):
                    for k, v in zip(spec_node.keys, spec_node.values, strict=True):
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            spec[k.value] = _resolve_value(v, consts)
                found.append((str(fn_node.value), spec))
        if not found:
            continue
        target = found[-1][0]
        gt = TaskGroundTruth(target_function=target, calls=[f for f, _ in found])
        for fn, spec in found:
            if fn != target:
                continue
            for key, (kind, value) in spec.items():
                if kind == "attacker":
                    gt.attacker_args[key] = value
                elif kind == "scaffold":
                    gt.scaffold_args[key] = value
                elif key not in gt.dynamic_keys:
                    gt.dynamic_keys.append(key)
        out[index] = gt
    return out


# --------------------------------------------------------------------------------------------
# normalisation
# --------------------------------------------------------------------------------------------


def _cap(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_STR:
        return value[:MAX_STR] + "...[truncated]"
    if isinstance(value, list):
        return [_cap(v) for v in value]
    if isinstance(value, dict):
        return {k: _cap(v) for k, v in value.items()}
    return value


def _cap_args(args: dict[str, Any], protect: frozenset[str]) -> dict[str, Any]:
    """Cap long free text, but never a key a grader matches on - truncating one of those would
    silently turn a match into a miss."""
    return {k: (v if k in protect else _cap(v)) for k, v in args.items()}


def _run_paths(runs_root: Path) -> list[tuple[tuple[str, str, str, str, str], Path]]:
    out: list[tuple[tuple[str, str, str, str, str], Path]] = []
    for path in runs_root.rglob("*.json"):
        parts = path.relative_to(runs_root).parts
        if len(parts) != 5:
            continue
        out.append(((parts[0], parts[1], parts[2], parts[3], parts[4]), path))
    out.sort(key=lambda item: item[0])
    return out


def _index(name: str, prefix: str) -> int:
    return int(name.removeprefix(prefix).removesuffix(".json"))


def _task_index(name: str, prefix: str) -> int | None:
    """As `_index`, but tolerant. AgentDojo also ships 804 `injection_task_N/none/none.json` runs
    that execute an injection task directly with no user task and no attack; those are not attacked
    runs, are excluded from every rate here, and do not carry a user-task index."""
    stem = name.removeprefix(prefix).removesuffix(".json")
    return int(stem) if stem.isdigit() else None


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ref", default=PINNED_REF, help="AgentDojo commit to read")
    ap.add_argument("--source-dir", default="", help="an already-extracted checkout (offline)")
    ap.add_argument("--cache", default=str(ROOT / "work"), help="download cache (gitignored)")
    args = ap.parse_args(argv)

    # Imported here so the module docstring is readable with `--help` on a bare checkout.
    from judge_artifact.transcript import from_agentdojo_run

    root = Path(args.source_dir) if args.source_dir else acquire_source(args.ref, Path(args.cache))
    runs_root = root / "runs"
    if not runs_root.is_dir():
        raise SystemExit(f"no runs/ under {root}")

    gt = extract_ground_truth(root, SUITE)
    defenses = extract_defenses(root)
    # The rule "target = the last ground-truth call" must reproduce the table this project used to
    # hard-code, or the derivation is not the thing it claims to replace.
    expected = {0: "send_money", 1: "send_money", 2: "send_money", 3: "send_money",
                4: "update_scheduled_transaction", 5: "send_money", 6: "send_money",
                7: "update_password", 8: "send_money"}
    derived = {i: g.target_function for i, g in sorted(gt.items())}
    if derived != expected:
        raise SystemExit(f"derived targets {derived} != previously hard-coded {expected}")

    DATA.mkdir(parents=True, exist_ok=True)
    paths = _run_paths(runs_root)

    banking: list[dict[str, Any]] = []
    cells: dict[tuple[str, str, str], dict[str, int]] = {}
    errored: list[dict[str, Any]] = []
    truncated = 0

    for (pipeline, suite, utask, attack, fname), path in paths:
        raw = json.loads(path.read_text())
        run_errored = raw.get("error") is not None
        if attack != "none":
            cell = cells.setdefault((pipeline, suite, attack),
                                    {"n": 0, "errored": 0, "security": 0,
                                     "security_and_errored": 0, "utility": 0})
            cell["n"] += 1
            if run_errored:
                cell["errored"] += 1
            if raw.get("security"):
                cell["security"] += 1
                if run_errored:
                    cell["security_and_errored"] += 1
            if raw.get("utility"):
                cell["utility"] += 1
        if run_errored:
            errored.append({
                "pipeline": pipeline, "suite": suite, "attack": attack,
                "user_task": _task_index(utask, "user_task_"),
                "injection_task": _task_index(fname, "injection_task_"),
                "security": bool(raw.get("security")), "utility": bool(raw.get("utility")),
                "error_head": str(raw.get("error"))[:200],
                "source": str(path.relative_to(root)),
            })
        if suite != SUITE or attack != ATTACK:
            continue
        itask = _index(fname, "injection_task_")
        task_gt = gt[itask]
        episode = from_agentdojo_run(raw, task_gt.target_function, task_gt.attacker_args)
        protect = frozenset(task_gt.attacker_args) | frozenset(task_gt.scaffold_args)
        events: list[dict[str, Any]] = []
        for ev in episode.tool_events:
            capped = _cap_args(ev.args, protect if ev.name == task_gt.target_function
                               else frozenset())
            truncated += sum(1 for k, v in capped.items()
                             if isinstance(v, str) and v.endswith("...[truncated]")
                             and ev.args.get(k) != v)
            events.append({"name": ev.name, "args": capped, "call_id": ev.call_id,
                           "errored": ev.errored})
        banking.append({
            # the directory path is authoritative: a run's own `pipeline_name` field is the local
            # runner's name (for example "local" for the Meta-SecAlign runs), not the pipeline
            "id": f"{pipeline}/{suite}/{utask}/{attack}/injection_task_{itask}",
            "pipeline": pipeline,
            "suite": suite,
            "attack": attack,
            "user_task": _index(utask, "user_task_"),
            "injection_task": itask,
            "security": bool(raw.get("security")),
            "utility": bool(raw.get("utility")),
            "run_errored": run_errored,
            "target_function": task_gt.target_function,
            "attacker_args": task_gt.attacker_args,
            "scaffold_args": task_gt.scaffold_args,
            "tool_events": events,
            "source": str(path.relative_to(root)),
        })

    banking.sort(key=lambda r: (str(r["pipeline"]), int(r["user_task"]), int(r["injection_task"])))
    cell_rows = [
        {"pipeline": p, "suite": s, "attack": a, **counts}
        for (p, s, a), counts in sorted(cells.items())
    ]
    errored.sort(key=lambda r: (str(r["pipeline"]), str(r["suite"]), str(r["attack"]),
                                -1 if r["user_task"] is None else int(r["user_task"])))

    provenance = {
        "repo": REPO,
        "ref": args.ref if not args.source_dir else f"{args.ref} (from --source-dir)",
        "license": "MIT",
        "note": "AgentDojo releases completed transcripts with a deterministic `security` oracle.",
    }
    gt_doc = {
        "provenance": provenance,
        "suite": SUITE,
        "extraction": "ast over src/agentdojo/default_suites/v1/<suite>/injection_tasks.py; "
                      "target = the last FunctionCall in ground_truth",
        "tasks": {
            str(i): {
                "target_function": g.target_function,
                "attacker_args": g.attacker_args,
                "scaffold_args": g.scaffold_args,
                "dynamic_keys": g.dynamic_keys,
                "ground_truth_calls": g.calls,
            }
            for i, g in sorted(gt.items())
        },
    }
    (DATA / "ground_truth.json").write_text(json.dumps(gt_doc, indent=2, sort_keys=True) + "\n")

    pipeline_names = {str(r["pipeline"]) for r in banking}
    pipelines_doc = {
        "provenance": provenance,
        "defenses": defenses,
        "defenses_source": "src/agentdojo/agent_pipeline/agent_pipeline.py DEFENSES",
        "pipelines": {
            name: dict(zip(("base", "defense"),
                           split_pipeline(name, pipeline_names, defenses), strict=True))
            for name in sorted(pipeline_names)
        },
    }
    (DATA / "pipelines.json").write_text(
        json.dumps(pipelines_doc, indent=2, sort_keys=True) + "\n"
    )
    write_jsonl(DATA / "banking_important_instructions.jsonl", banking)
    write_jsonl(DATA / "error_denominator_cells.jsonl", cell_rows)
    write_jsonl(DATA / "errored_runs.jsonl", errored)

    outputs = ["ground_truth.json", "pipelines.json", "banking_important_instructions.jsonl",
               "error_denominator_cells.jsonl", "errored_runs.jsonl"]
    manifest = {
        "provenance": provenance,
        "produced_by": "scripts/fetch_agentdojo_runs.py",
        "run_files_scanned": len(paths),
        "banking_important_instructions_runs": len(banking),
        "pipelines": sorted({str(r["pipeline"]) for r in banking}),
        "defended_pipelines": sorted(
            n for n in pipeline_names if split_pipeline(n, pipeline_names, defenses)[1] != "none"
        ),
        "denominator_cells": len(cell_rows),
        "errored_runs": len(errored),
        "max_string_arg_chars": MAX_STR,
        "truncated_argument_values": truncated,
        "sha256": {name: sha256_of(DATA / name) for name in outputs},
    }
    (DATA / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(f"scanned {len(paths)} run files")
    print(f"banking/{ATTACK}: {len(banking)} runs across {len(pipeline_names)} pipelines")
    print(f"denominator cells: {len(cell_rows)}   errored runs: {len(errored)}")
    print(f"truncated argument values: {truncated}")
    for name in [*outputs, "MANIFEST.json"]:
        print(f"  wrote {DATA / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
