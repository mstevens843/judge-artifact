# Reproduce and publish the bounded parser comparison

Run from the prepared sibling worktree:

```bash
cd /Users/devlegacy/Desktop/projects/ai-gap-coverage-projects/third-party-systems/judge-artifact-parser-2311-20260922
```

Actual base: `5e7d379274ee7b4cff080a489e49c236d36e579d`.
Branch: `experiment/parser-2311-revision-comparison`.
Main checkout was clean at this base and remains untouched. No ancestor or local AGENTS.md
applied. Initial available disk space was 13 GiB. `origin` was verified as
`https://github.com/mstevens843/judge-artifact.git`; authenticated account `mstevens843` has
admin/push permission. No commit, push, PR, comment or reaction was made.

## Environment and independent replay

Setup executed `uv sync --locked --group dev --extra parser`, selecting Python 3.13.14.
It installed the lockfile's parser/dev dependencies in this worktree's own `.venv`.
BeautifulSoup is 4.15.0. No lockfile or dependency declarations changed.

```bash
set -eu
uv sync --locked --group dev --extra parser
uv run --offline --no-sync python -m judge_artifact.harness.parser_revision_check \
  --input tests/fixtures/parser-path-completions.jsonl \
  --report evidence/parser-delta-revisions-constructed.json \
  --corpus-kind constructed \
  --source 'Constructed blackmail parser path regressions; unchanged historical 32-case cohort; no sampled model outputs'
uv run --offline --no-sync python -m judge_artifact.harness.parser_revision_check \
  --input tests/fixtures/parser-revision-supplemental.jsonl \
  --report evidence/parser-delta-revisions-supplemental.json \
  --corpus-kind constructed \
  --source 'Three separately attributed constructed marker-order controls; see fixture attribution fields; no sampled model outputs'
uv run --offline --no-sync pytest tests/test_parser_delta.py tests/test_parser_paths.py tests/test_parser_pr_fidelity.py tests/test_parser_revisions.py -q
uv run --offline --no-sync pytest -q
uv run --offline --no-sync ruff check .
uv run --offline --no-sync mypy
```

`--offline` restricts uv's package activity; it is not claimed as a general network sandbox.
`test_relocation_and_network_denied_generation_and_oracle` separately copies source, fixtures
and evidence, then generates and checks both new reports in fresh isolated Python processes
with all Python socket audit events denied. A positive socket-denial probe verifies the guard.
Those subprocesses import only relocated project source and installed dependencies, not Inspect.

Generate all four reports into a new temporary directory and compare bytes without overwriting
canonical evidence. The first two retain the historical documented provenance and flags:

```bash
set -eu
parser_replay_dir=$(mktemp -d /tmp/judge-artifact-parser-replay.XXXXXX)
uv run --offline --no-sync python -m judge_artifact.harness.parser_delta \
  --input tests/fixtures/parser-completions.jsonl \
  --out "$parser_replay_dir/v1.json" --corpus-kind constructed \
  --source 'Constructed #2310 regression cases; no sampled model outputs'
cmp "$parser_replay_dir/v1.json" evidence/parser-delta-constructed.json
uv run --offline --no-sync python -m judge_artifact.harness.parser_delta \
  --input tests/fixtures/parser-path-completions.jsonl \
  --out "$parser_replay_dir/v2.json" --corpus-kind constructed \
  --source 'Constructed blackmail parser path regressions; no sampled model outputs' \
  --compare-pr-2311
cmp "$parser_replay_dir/v2.json" evidence/parser-delta-paths-constructed.json
uv run --offline --no-sync python -m judge_artifact.harness.parser_delta \
  --input tests/fixtures/parser-path-completions.jsonl \
  --out "$parser_replay_dir/v3.json" --corpus-kind constructed \
  --source 'Constructed blackmail parser path regressions; unchanged historical 32-case cohort; no sampled model outputs' \
  --compare-pr-2311-revisions
cmp "$parser_replay_dir/v3.json" evidence/parser-delta-revisions-constructed.json
uv run --offline --no-sync python -m judge_artifact.harness.parser_delta \
  --input tests/fixtures/parser-revision-supplemental.jsonl \
  --out "$parser_replay_dir/supplemental.json" --corpus-kind constructed \
  --source 'Three separately attributed constructed marker-order controls; see fixture attribution fields; no sampled model outputs' \
  --compare-pr-2311-revisions
cmp "$parser_replay_dir/supplemental.json" evidence/parser-delta-revisions-supplemental.json
```

The full retained source is sufficient after relocation. Acquisition does not repeat during
replay. The acquisition commands used `gh api repos/UKGovernmentBEIS/inspect_evals/contents/<path>?ref=361bb2ec1a06cc75b6914bda57f8f543d11062f9`, decoded its base64 `content`, checked Python AST
parsing, calculated `sha1(b'blob ' + ascii_length + b'\0' + raw)`, matched the API's `sha`, and
compared the bytes with the exact `raw.githubusercontent.com` URL. See SOURCE.json for every
full endpoint, SHA-256, byte length and blob. The commit response is retained in upstream-context.json.

Recheck every pre-edit retained evidence/result/data/fixture/dependency hash:

```bash
python3 - <<'PY'
import hashlib, json
from pathlib import Path
p = Path('handoff/parser-2311-revision-comparison/historical-sha256.json')
for name, digest in json.loads(p.read_text()).items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, name
print('All historical hashes unchanged')
PY
```

## User-run publication only

Publication links in `github-comment-draft.md` are explicit `{{REPORT_URL}}`,
`{{EVIDENCE_URL}}`, and `{{SUPPLEMENT_URL}}` placeholders. The new files are not online yet.
The formatter below reads the committed draft and verifies the pushed branch's actual SHA.
It prints the reply; it does not post it. Reply destination:
https://github.com/UKGovernmentBEIS/inspect_evals/issues/2310#issuecomment-5778420456.

The exact explicit staging and commit/push commands are in [PUBLISH.sh](PUBLISH.sh).
Review that file and the proposed changes, then run:

```bash
bash handoff/parser-2311-revision-comparison/PUBLISH.sh
python3 handoff/parser-2311-revision-comparison/format-comment.py
```

The publication script checks the current branch and remote, stages only the listed task files,
prints the staged stat, checks whitespace, commits with the factual message
`Compare pinned Inspect #2311 parser revisions offline`, and pushes that branch normally.
It does not create a branch, fork, force-push or send the GitHub reply.
