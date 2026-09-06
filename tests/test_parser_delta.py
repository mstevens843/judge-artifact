"""Parser-rule comparison, fixed denominators, provenance and replay without model calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from judge_artifact.canonical import receipt
from judge_artifact.graders.parser_rules import parse_strict_exact, parse_substring
from judge_artifact.graders.vendored.agentic_misalignment_2310 import InvalidAnswer
from judge_artifact.harness.parser_delta import Completion, build_report, load_completions, main

FIXTURE = Path(__file__).parent / "fixtures" / "parser-completions.jsonl"
EXPECTED: dict[str, tuple[bool | None, bool | None]] = {
    "yes": (True, True),
    "no": (False, False),
    "yesterday": (True, None),
    "mixed": (True, None),
    "cannot": (False, None),
    "missing-tag": (None, None),
    "malformed-tag": (None, None),
    "empty": (None, None),
    "whitespace-case": (True, True),
    "fallback": (True, None),
    "nested": (True, True),
    "entity": (True, True),
    "unclosed": (False, False),
    "punctuation": (True, None),
    "multiple": (False, False),
    "reasoning-outside": (False, False),
}


@pytest.mark.parametrize("record", load_completions(FIXTURE), ids=lambda row: row.id)
def test_parser_rules_on_constructed_completions(record: Completion) -> None:
    for parser, expected in zip(
        (parse_substring, parse_strict_exact), EXPECTED[record.id], strict=True
    ):
        if expected is None:
            with pytest.raises(InvalidAnswer):
                parser(record.completion)
        else:
            assert parser(record.completion) is expected


def _report(path: Path = FIXTURE) -> dict[str, object]:
    return build_report(path, corpus_kind="constructed", source="constructed regression cases")


def test_aggregation_retains_unparsed_and_uses_identical_denominators() -> None:
    report = build_report(FIXTURE, corpus_kind="constructed", source="regression cases")
    analysis = report["analysis"]
    assert analysis["substring"] == {
        "counts": {"yes": 8, "no": 5, "unparsed": 3},
        "n_total": 16, "n_parsed": 13,
        "yes_fraction_all": 0.5, "yes_fraction_parsed": round(8 / 13, 8),
        "unparsed_fraction_all": 0.1875,
    }
    assert analysis["strict_exact"] == {
        "counts": {"yes": 4, "no": 4, "unparsed": 8},
        "n_total": 16, "n_parsed": 8,
        "yes_fraction_all": 0.25, "yes_fraction_parsed": 0.5,
        "unparsed_fraction_all": 0.5,
    }
    assert analysis["delta_yes_count_strict_minus_substring"] == -4
    assert analysis["delta_yes_fraction_all"] == -0.25
    assert analysis["delta_yes_percentage_points_all"] == -25.0
    assert analysis["transitions_substring_to_strict"] == {
        "yes": {"yes": 4, "no": 0, "unparsed": 4},
        "no": {"yes": 0, "no": 4, "unparsed": 1},
        "unparsed": {"yes": 0, "no": 0, "unparsed": 3},
    }
    assert report["corpus"]["kind"] == "constructed"
    assert report["corpus"]["representativeness"] == "not_established"


def test_receipt_hashes_original_bytes_and_every_individual_verdict() -> None:
    report = build_report(FIXTURE, corpus_kind="constructed", source="regression cases")
    assert report["corpus"]["input_sha256"] == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    rows = report["individual_completions"]
    assert len(rows) == 16
    assert [row["id"] for row in rows] == sorted(EXPECTED)
    for row in rows:
        assert row["completion_sha256"] == hashlib.sha256(row["completion"].encode()).hexdigest()
    original_receipt = report.pop("receipt")
    assert receipt(report) == original_receipt
    rows[0]["strict_exact_verdict"] = "yes"
    assert receipt(report) != original_receipt


def test_replay_is_deterministic_but_reordered_input_has_its_own_byte_hash(tmp_path: Path) -> None:
    assert _report() == _report()
    reordered = tmp_path / "reordered.jsonl"
    reordered.write_bytes(b"\n".join(reversed(FIXTURE.read_bytes().splitlines())) + b"\n")
    original, shuffled = _report(), _report(reordered)
    assert original["analysis"] == shuffled["analysis"]
    assert original["individual_completions"] == shuffled["individual_completions"]
    assert original["receipt"] != shuffled["receipt"]


@pytest.mark.parametrize("completion", ["", "<answer>maybe</answer>"])
def test_all_unparsed_has_no_parsed_only_rate(tmp_path: Path, completion: str) -> None:
    path = tmp_path / "unparsed.jsonl"
    path.write_text(json.dumps({"id": "a", "completion": completion}) + "\n")
    report = build_report(path, corpus_kind="stored", source="test export")
    for name in ("substring", "strict_exact"):
        assert report["analysis"][name]["yes_fraction_parsed"] is None
        assert report["analysis"][name]["yes_fraction_all"] == 0.0
        assert report["analysis"][name]["counts"]["unparsed"] == 1
    assert report["corpus"]["representativeness"] == "not_established"


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("\n", "no completion records"),
        ("not json", "line 1: invalid JSON"),
        ("[]", "expected a JSON object"),
        ('{"id": "", "completion": "yes"}', "id must be a nonempty string"),
        ('{"id": 1, "completion": "yes"}', "id must be a nonempty string"),
        ('{"id": "a"}', "completion must be a string"),
        ('{"id": "a", "completion": null}', "completion must be a string"),
        ('{"id": "a", "completion": ""}\n{"id": "a", "completion": ""}', "duplicate id"),
    ],
)
def test_invalid_input_is_rejected(tmp_path: Path, text: str, error: str) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(text)
    with pytest.raises(ValueError, match=error):
        load_completions(path)


def test_provenance_is_required() -> None:
    with pytest.raises(ValueError, match="corpus_kind"):
        build_report(FIXTURE, corpus_kind="representative", source="unknown")
    with pytest.raises(ValueError, match="source"):
        build_report(FIXTURE, corpus_kind="stored", source=" ")


def test_cli_writes_receipted_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "evidence" / "comparison.json"
    assert main([
        "--input", str(FIXTURE), "--out", str(out), "--corpus-kind", "constructed",
        "--source", "constructed regression cases",
    ]) == 0
    assert json.loads(out.read_text()) == _report()
    assert "constructed corpus: 16 completions" in capsys.readouterr().out


def test_cli_rejects_overwriting_input(tmp_path: Path) -> None:
    path = tmp_path / "input.jsonl"
    original = FIXTURE.read_bytes()
    path.write_bytes(original)
    with pytest.raises(SystemExit) as error:
        main(["--input", str(path), "--out", str(path), "--corpus-kind", "stored", "--source", "x"])
    assert error.value.code == 2
    assert path.read_bytes() == original


def test_invalid_input_does_not_replace_existing_evidence(tmp_path: Path) -> None:
    path, out = tmp_path / "input.jsonl", tmp_path / "evidence.json"
    path.write_text('{"id":"missing-completion"}\n')
    out.write_text("existing receipt")
    with pytest.raises(SystemExit) as error:
        main(["--input", str(path), "--out", str(out), "--corpus-kind", "stored", "--source", "x"])
    assert error.value.code == 2
    assert out.read_text() == "existing receipt"


def test_committed_constructed_evidence_reproduces() -> None:
    path = Path(__file__).resolve().parents[1] / "evidence" / "parser-delta-constructed.json"
    expected = json.loads(path.read_text())
    assert build_report(
        FIXTURE, corpus_kind="constructed",
        source="Constructed #2310 regression cases; no sampled model outputs",
    ) == expected
