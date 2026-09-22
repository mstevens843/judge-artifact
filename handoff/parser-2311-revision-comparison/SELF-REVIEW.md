# Executed self-review, 2026-09-22

Completed by the sole implementation agent; no delegation. No commits, pushes or provider
messages were sent. No model calls, Docker, crash experiments, dependency upgrades, broad
AgentDojo/AgentHarm reruns or upstream edits were performed.

## Gates

Environment: locked Python 3.13.14, BeautifulSoup 4.15.0; parser/dev extras only.
Exact commands, exits and skip reasons are in [final-gates.txt](final-gates.txt).

| Gate | Actual result |
|---|---|
| Focused parser, historical fidelity and revision tests | **239 passed**, 0 skipped, 0 failed |
| Ordinary full pytest | **342 passed, 38 skipped**, 0 failed |
| Ruff | Passed |
| Strict mypy | Passed, **52 source files** |
| Independent source replay of both new reports | Passed |
| v1/v2 historical generation to temporary outputs | Both byte-identical |
| v3 primary/supplemental generation after relocation | Both byte-identical; source replay passed with Python socket audit events denied |
| Pre-edit historical file hashes | All unchanged; see closeout.txt |
| Tracked diff whitespace plus new-file whitespace checks | Passed; see closeout.txt |
| Main checkout | Clean, unchanged base and branch; see closeout.txt |

The 38 skips comprise 20 optional installed locked-release fidelity cases, 17 latest-package
fidelity cases and one collection-time skip for the optional Inspect Arm D module. Inspect
was not installed in this worktree. This run does not claim to rerun installed release fidelity;
that retained historical result is unchanged. **All pinned-source PR checks ran**, with no
Inspect imports, and both real upstream methods were exercised on all 32 primary and three
supplemental completions (70 direct method/adapter checks).

## Negative controls and independent checks

1. The oracle has separate immutable pin/hash anchors and compiles only the exact upstream
   constants, helpers, real new `GraderParseError` class and blackmail method. It rejects missing
   or duplicate definitions and altered snapshot hashes. Success requires an actual Boolean
   and the original completion returned unchanged. Rejection messages are checked against the
   real method's expected tagged/fallback messages before mapping to canonical report reasons.
2. Old/new marker-order controls pass in both directions. The single-marker reasoning example
   remains yes. Invalid/empty tags with tempting reasoning fallback and `answer>yesterday`
   reject under both exact pins. Tagged answers override contradictory reasoning as recorded
   in both primary row replays. Formatting and strict-policy differences remain visible.
3. A disposable copy replaced `matches[-1]` with `matches[0]` in the new adapted helper.
   Running the real named regressions produced **1 failed, 1 passed**: the marker-order
   discriminator failed and the single-marker control passed. Restoration produced **2 passed**.
   Full output: [marker-mutation.txt](marker-mutation.txt). A permanent test-scoped mutation
   additionally proves that the untouched source oracle rejects a report from the mutated
   comparator; this is a semantic mismatch, not a source hash failure.
4. A copied new snapshot with one added comment was rejected by the actual `load_oracle` hash
   path. Missing the actual exception class failed extraction instead of becoming unparsed.
   The retained SOURCE.json hashes, blob IDs, sizes, commit and paths are also checked.
5. Fourteen report mutations, each with a freshly recomputed receipt, failed in the intended
   section: verdict, per-rule path, raw completion, completion digest, failure reason, omitted
   row, duplicate row, denominator, transition cell, revision pin, source hash, provenance,
   extractor version and changed-ID list. Unmodified primary and supplemental artifacts pass.
   Replay compares every top-level section and full row content, not only receipts.
6. Thirty-six injected adapter faults (nine return/exception cases across four rules) propagate:
   strings, integers and None fail Boolean validation; TypeError, NameError, OSError,
   RuntimeError and ordinary ValueError never become routine unparsed results. Invalid JSONL,
   duplicate IDs and non-string completions fail through the actual v3 CLI without replacing
   an existing output. Existing input tests cover additional malformed shapes.
7. Per-row counts, parsed/total denominators and transitions reconcile within each path and
   overall. Supplemental flips cancel in aggregate but remain visible per row. All-unparsed
   and empty-path inputs use zero counts and null undefined rates; stored provenance remains
   stored with representativeness not established. JSON serialization forbids nonfinite rates.
8. Historical v1 and v2 commands run through the actual CLI into temporary paths with the
   documented provenance, comparing bytes to the original artifacts. Historical snapshots,
   fixture bytes, receipts, numbered results, data, pyproject and lockfile are not rewritten.
9. The relocation test uses fresh `python -I` subprocesses, copied source/fixtures/evidence,
   installed dependencies and a socket-denying audit hook. A deliberate socket probe must fail.
   It generates and independently verifies both new reports without the original source path.
   `uv --offline` alone is not treated as proof of network isolation.
10. Report and draft were checked against the final rows: primary changed IDs and transitions,
    unchanged scope example, all 19 tagged outcomes, supplemental opposite flips, and the
    exact docstring rejection. The reply distinguishes extraction paths from compliance and
    parser observations from semantic error/prevalence or deployed benchmark measurements.

## Findings and corrections during this work

- The initial source checker omitted the typed AST Module `type_ignores` argument in one
  construction. Mypy caught it; it was supplied before final gates. Initial line-length and
  regex-pattern style diagnostics were corrected. There were no failing behavioral tests in
  the initial focused run (238 passed; [focused-initial.txt](focused-initial.txt)); adding the
  source manifest binding check brought the final count to 239.
- The exact new helper docstring example unexpectedly rejects under both actual source
  methods. Examination showed that `\S+` consumes the adjacent closing reasoning markup and
  later `Answer:`. This is retained as a limitation, not “fixed” in the comparator. An early
  exploratory supplemental fixture/report is preserved in [superseded/](superseded/); its
  redundant reverse-markup variant was replaced by exact upstream regression inputs in the
  final three-case supplement. It is not included in primary or final supplemental totals.
- No historical evidence or parser policy was adjusted to make comparisons pass. No unrelated
  failure is labeled pre-existing. No claim is made that the entire PR or its scorer is fixed.

A future permitted-answer-region policy still requires a declared rule and maintainer input.
That open policy question does not block this finite behavioral comparison.
