# Ready for user review and publication

The scoped comparison is complete and uncommitted in the isolated worktree
`judge-artifact-parser-2311-20260922`, branch `experiment/parser-2311-revision-comparison`,
base `5e7d379274ee7b4cff080a489e49c236d36e579d`. The main Judge-Artifact checkout is clean.

- **Original cohort: 32 unchanged completions.** Historical PR `4698d4b68dfa88bdaf849e591f3a46d6151219a2`
  → new target `361bb2ec1a06cc75b6914bda57f8f543d11062f9`: one no→yes, one unparsed→yes,
  one unparsed→no. 29 verdicts unchanged. Counts move from 11/9/12 to 13/9/10
  (yes/no/unparsed). All 19 tagged verdicts and the single-marker scope limitation persist.
- **Separate supplement: 3 constructed controls**, attributed to the exact target tests or
  helper docstring. One no→yes, one yes→no, one unchanged unparsed; both PR totals 1/1/1.
  The docstring's adjacent-markup example rejects under both actual methods.
- **Quality gates:** 239 focused passes; full suite 342 passes, 38 optional Inspect-related
  skips; Ruff and mypy pass (52 files). Mutation controls, independent full artifact replay,
  relocation with socket operations denied and v1/v2 byte reproduction pass.
- **Scope:** blackmail parser only; no model/scorer/classify/benchmark measurement. Constructed
  counts are not semantic error rates or prevalence. Strict exact is a comparison policy.

[Report](../../results/11-parser-revision-comparison.md) ·
[Primary evidence](../../evidence/parser-delta-revisions-constructed.json) ·
[Supplemental evidence](../../evidence/parser-delta-revisions-supplemental.json) ·
[Self-review](SELF-REVIEW.md) · [Commands](REPRODUCE.md) · [Reply draft](github-comment-draft.md).

Commit message: `Compare pinned Inspect #2311 parser revisions offline`.
`PUBLISH.sh` contains the exact explicit-file staging, review, commit and normal push commands.
Run it yourself after reviewing the changes, then run `format-comment.py` to print the
GitHub-formatted reply with links pinned to the actual published commit. Before that step,
publication URLs in the draft are clearly marked placeholders. Nothing has been posted.
