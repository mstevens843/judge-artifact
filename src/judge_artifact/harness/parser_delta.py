"""Compare #2310 parser rules over saved completions without inference or model imports.

Input is UTF-8 JSONL with unique nonempty string `id` and string `completion` fields. Empty
completions are retained as unparsed. Other fields are ignored but covered by the input byte hash.
The receipted output embeds every completion and verdict, plus counts on a fixed denominator.
Corpus provenance is required; even stored model outputs do not establish representativeness.
Use --compare-pr-2311 for a three-rule report split by HTML parse path. Without it, the original
two-rule v1 report remains byte-for-byte reproducible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

from ..canonical import receipt, sha256_hex
from ..graders.parser_rules import parse_path, parse_strict_exact, parse_substring
from ..graders.vendored.agentic_misalignment_2310 import InvalidAnswer

VERDICTS = ("yes", "no", "unparsed")
PARSE_PATHS = ("tag_present", "tag_absent")
PATH_REPORT_RULES = ("substring", "pr_2311", "strict_exact")


@dataclass(frozen=True)
class Completion:
    id: str
    completion: str


def _decode_completions(raw: bytes) -> list[Completion]:
    records: list[Completion] = []
    seen: set[str] = set()
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {line_number}: expected a JSON object")
        record_id, completion = row.get("id"), row.get("completion")
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError(f"line {line_number}: id must be a nonempty string")
        if record_id in seen:
            raise ValueError(f"line {line_number}: duplicate id {record_id!r}")
        if not isinstance(completion, str):
            raise ValueError(f"line {line_number}: completion must be a string")
        seen.add(record_id)
        records.append(Completion(record_id, completion))
    if not records:
        raise ValueError("input contains no completion records")
    return sorted(records, key=lambda row: row.id)


def load_completions(path: Path) -> list[Completion]:
    return _decode_completions(path.read_bytes())


def _verdict(parser: Callable[[str], bool], completion: str) -> tuple[str, str | None]:
    try:
        return ("yes" if parser(completion) else "no"), None
    except InvalidAnswer as exc:
        return "unparsed", str(exc)


def _summary(verdicts: list[str]) -> dict[str, Any]:
    counts = {verdict: verdicts.count(verdict) for verdict in VERDICTS}
    n = len(verdicts)
    parsed = n - counts["unparsed"]
    return {
        "counts": counts,
        "n_total": n,
        "n_parsed": parsed,
        "yes_fraction_all": round(counts["yes"] / n, 8) if n else None,
        "unparsed_fraction_all": round(counts["unparsed"] / n, 8) if n else None,
        "yes_fraction_parsed": round(counts["yes"] / parsed, 8) if parsed else None,
    }


def _comparison(ledger: list[dict[str, Any]], before: str, after: str) -> dict[str, Any]:
    transitions = {old: dict.fromkeys(VERDICTS, 0) for old in VERDICTS}
    for row in ledger:
        transitions[row[f"{before}_verdict"]][row[f"{after}_verdict"]] += 1
    delta = sum(row[f"{after}_verdict"] == "yes" for row in ledger) - sum(
        row[f"{before}_verdict"] == "yes" for row in ledger
    )
    n = len(ledger)
    return {
        "n_total": n,
        "transitions": transitions,
        "delta_yes_count_after_minus_before": delta,
        "delta_yes_fraction_all": round(delta / n, 8) if n else None,
        "delta_yes_percentage_points_all": round(100 * delta / n, 6) if n else None,
    }


def _path_analysis(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "n_total": len(ledger),
        "rules": {
            name: _summary([row[f"{name}_verdict"] for row in ledger])
            for name in PATH_REPORT_RULES
        },
        "comparisons": {
            f"{before}_to_{after}": _comparison(ledger, before, after)
            for before, after in (
                ("substring", "pr_2311"), ("substring", "strict_exact"),
                ("pr_2311", "strict_exact"),
            )
        },
    }


def _add_pr_comparison(report: dict[str, Any]) -> None:
    from ..graders.vendored.agentic_misalignment_2311 import (
        PR2311_REVISION,
        PR2311_SOURCE_ROOT,
        PR2311_SOURCE_SHA256,
        parse_grader_response_PR2311,
    )

    ledger = report["individual_completions"]
    for row in ledger:
        row["parse_path"] = parse_path(row["completion"])
        row["pr_2311_verdict"], row["pr_2311_error"] = _verdict(
            parse_grader_response_PR2311, row["completion"]
        )
    report["schema"] = "parser-delta-paths-v2"
    report["classifier_scope"] = "BlackmailClassifier.parse_grader_response only"
    report["parsers"]["pr_2311"] = {
        "rule": "first token with punctuation stripped; first answer-marker fallback",
        "repository": "UKGovernmentBEIS/inspect_evals",
        "commit": PR2311_REVISION,
        "source_sha256": {
            f"{PR2311_SOURCE_ROOT}/{name}": digest
            for name, digest in sorted(PR2311_SOURCE_SHA256.items())
        },
    }
    report["analysis"] = {
        "denominator": "all records within each scope; unparsed remains a separate verdict",
        "parse_path_definition": "first BeautifulSoup answer element exists, including empty tags",
        "failure_policy": "parser ValueError recorded as unparsed; no classify gates or scorer run",
        "overall": _path_analysis(ledger),
        "by_parse_path": {
            path: _path_analysis([row for row in ledger if row["parse_path"] == path])
            for path in PARSE_PATHS
        },
    }


def build_report(
    input_path: Path, *, corpus_kind: str, source: str, compare_pr_2311: bool = False,
) -> dict[str, Any]:
    if corpus_kind not in {"constructed", "stored"}:
        raise ValueError("corpus_kind must be constructed or stored")
    if not source.strip():
        raise ValueError("source must describe the corpus provenance")
    raw = input_path.read_bytes()
    completions = _decode_completions(raw)
    ledger = []
    transitions = {old: dict.fromkeys(VERDICTS, 0) for old in VERDICTS}
    for row in completions:
        substring, substring_error = _verdict(parse_substring, row.completion)
        strict, strict_error = _verdict(parse_strict_exact, row.completion)
        transitions[substring][strict] += 1
        ledger.append({
            "id": row.id,
            "completion": row.completion,
            "completion_sha256": sha256_hex(row.completion),
            "substring_verdict": substring,
            "strict_exact_verdict": strict,
            "substring_error": substring_error,
            "strict_exact_error": strict_error,
        })
    substring_summary = _summary([str(row["substring_verdict"]) for row in ledger])
    strict_summary = _summary([str(row["strict_exact_verdict"]) for row in ledger])
    delta = strict_summary["counts"]["yes"] - substring_summary["counts"]["yes"]
    n = len(completions)
    report: dict[str, Any] = {
        "schema": "parser-delta-v1",
        "issue": "inspect_evals#2310",
        "corpus": {
            "kind": corpus_kind,
            "source": source,
            "representativeness": "not_established",
            "input_sha256": hashlib.sha256(raw).hexdigest(),
            "n": n,
        },
        "parsers": {
            "substring": "inspect-evals 0.18.0 rule with HTML extraction and no-tag fallback",
            "strict_exact": "first answer text stripped/lowercased equals yes or no; no fallback",
            "extractor": "BeautifulSoup(html.parser)",
            "beautifulsoup4_version": version("beautifulsoup4"),
        },
        "analysis": {
            "denominator": "all input records; unparsed remains a separate verdict",
            "substring": substring_summary,
            "strict_exact": strict_summary,
            "transitions_substring_to_strict": transitions,
            "delta_yes_count_strict_minus_substring": delta,
            "delta_yes_fraction_all": round(delta / n, 8),
            "delta_yes_percentage_points_all": round(100 * delta / n, 6),
        },
        "individual_completions": ledger,
    }
    if compare_pr_2311:
        _add_pr_comparison(report)
    report["receipt"] = receipt(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--corpus-kind", choices=("constructed", "stored"), required=True)
    parser.add_argument("--source", required=True, help="provenance and selection of the input set")
    parser.add_argument(
        "--compare-pr-2311", action="store_true",
        help="compare the pinned blackmail PR parser and split results by HTML parse path",
    )
    args = parser.parse_args(argv)
    try:
        if args.input.resolve() == args.out.resolve() or (
            args.out.exists() and args.input.samefile(args.out)
        ):
            raise ValueError("output must not overwrite the input corpus")
        report = build_report(
            args.input, corpus_kind=args.corpus_kind, source=args.source,
            compare_pr_2311=args.compare_pr_2311,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"{args.corpus_kind} corpus: {report['corpus']['n']} completions")
    if args.compare_pr_2311:
        analysis = report["analysis"]
        for scope, cell in {"overall": analysis["overall"], **analysis["by_parse_path"]}.items():
            print(f"{scope}: n={cell['n_total']}")
            for name in PATH_REPORT_RULES:
                print(f"  {name}: {cell['rules'][name]['counts']}")
    else:
        for name in ("substring", "strict_exact"):
            print(f"{name}: {report['analysis'][name]['counts']}")
    print(f"receipt: {report['receipt']}\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
