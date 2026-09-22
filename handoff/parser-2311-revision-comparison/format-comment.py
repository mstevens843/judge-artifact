"""After the user pushes, print the committed comment with real pinned publication URLs."""

import subprocess


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


branch = "experiment/parser-2311-revision-comparison"
remote = "https://github.com/mstevens843/judge-artifact.git"
if git("branch", "--show-current") != branch or git("remote", "get-url", "origin") != remote:
    raise SystemExit("Use the prepared branch and verified Judge-Artifact origin")
sha = git("rev-parse", "HEAD")
remote_sha = git("ls-remote", "--exit-code", "origin", f"refs/heads/{branch}").split()[0]
if remote_sha != sha:
    raise SystemExit("Local HEAD is not the published branch head; finish the user-run push first")
base = f"https://github.com/mstevens843/judge-artifact/blob/{sha}"
draft = git("show", f"{sha}:handoff/parser-2311-revision-comparison/github-comment-draft.md")
for placeholder, path in {
    "REPORT_URL": "results/11-parser-revision-comparison.md",
    "EVIDENCE_URL": "evidence/parser-delta-revisions-constructed.json",
    "SUPPLEMENT_URL": "evidence/parser-delta-revisions-supplemental.json",
}.items():
    git("cat-file", "-e", f"{sha}:{path}")
    draft = draft.replace("{{" + placeholder + "}}", f"{base}/{path}")
print(draft)
