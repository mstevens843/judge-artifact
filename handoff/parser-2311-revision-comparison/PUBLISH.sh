#!/usr/bin/env bash
# User-run only: review this explicit staging list before executing.
set -euo pipefail
cd -- "$(dirname -- "$0")/../.."
test "$(git branch --show-current)" = 'experiment/parser-2311-revision-comparison'
test "$(git remote get-url origin)" = 'https://github.com/mstevens843/judge-artifact.git'
test -z "$(git diff --cached --name-only)"
git add -- \
  .github/workflows/ci.yml \
  README.md \
  RESULTS.md \
  src/judge_artifact/harness/parser_delta.py \
  src/judge_artifact/harness/parser_revision_check.py \
  src/judge_artifact/graders/vendored/agentic_misalignment_2311_361bb2e.py \
  tests/test_parser_revisions.py \
  tests/fixtures/parser-revision-supplemental.jsonl \
  tests/fixtures/pr2311_361bb2e/SOURCE.json \
  tests/fixtures/pr2311_361bb2e/classifier.py.txt \
  tests/fixtures/pr2311_361bb2e/blackmail_classifier.py.txt \
  evidence/parser-delta-revisions-constructed.json \
  evidence/parser-delta-revisions-supplemental.json \
  results/11-parser-revision-comparison.md \
  handoff/parser-2311-revision-comparison/SUMMARY.md \
  handoff/parser-2311-revision-comparison/REPRODUCE.md \
  handoff/parser-2311-revision-comparison/SELF-REVIEW.md \
  handoff/parser-2311-revision-comparison/PUBLISH.sh \
  handoff/parser-2311-revision-comparison/github-comment-draft.md \
  handoff/parser-2311-revision-comparison/format-comment.py \
  handoff/parser-2311-revision-comparison/final-gates.txt \
  handoff/parser-2311-revision-comparison/focused-initial.txt \
  handoff/parser-2311-revision-comparison/marker-mutation.txt \
  handoff/parser-2311-revision-comparison/closeout.txt \
  handoff/parser-2311-revision-comparison/historical-sha256.json \
  handoff/parser-2311-revision-comparison/upstream-context.json \
  handoff/parser-2311-revision-comparison/superseded/initial-supplemental.jsonl \
  handoff/parser-2311-revision-comparison/superseded/initial-supplemental-report.json
git --no-pager diff --cached --stat
git diff --cached --check
git commit -m 'Compare pinned Inspect #2311 parser revisions offline'
git push --set-upstream origin experiment/parser-2311-revision-comparison
