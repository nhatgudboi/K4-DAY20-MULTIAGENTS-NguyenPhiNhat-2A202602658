#!/usr/bin/env python3
"""PROVIDED. Check the freeze protocol (students: self-check before submitting; instructors: grading).

    python scripts/verify_freeze.py

For every run of the condition `skills-auto` in results/ it verifies that
  1. the git tag `freeze` exists and `skills/` has not changed since the tag,
  2. `skills_sha256` in run.json equals the hash of the frozen skills folder (the run used exactly the frozen skills),
  3. the run started after the tag was created, and `skills_modified` is false,
  4. a commit whose message starts with `hypotheses` exists before the tag, and report/REPORT.md in that commit
     has the three hypotheses H1-H3 filled in.
Exit code 0 = everything fine.
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from lab.tasks import ROOT, hash_skills

SOURCES = {"skills-auto": ROOT / "skills" / "auto"}


def git(*args) -> subprocess.CompletedProcess:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    out = out.decode("utf-8", errors="replace") if isinstance(out := r.stdout, bytes) else out
    err = err.decode("utf-8", errors="replace") if isinstance(err := r.stderr, bytes) else err
    return subprocess.CompletedProcess(r.args, r.returncode, out, err)


def main() -> int:
    problems = []
    tag = git("log", "-1", "--format=%cI", "freeze")
    if tag.returncode != 0:
        print("FAIL: git tag `freeze` not found")
        return 1
    tag_time = datetime.fromisoformat(tag.stdout.strip())
    if git("diff", "--quiet", "freeze", "--", "skills/").returncode != 0:
        problems.append("skills/ differs from the `freeze` tag")
    tag_commit = git("rev-parse", "freeze^{commit}").stdout.strip()
    hyp = [h for h in git("log", "freeze", "--format=%H", "--grep=^hypotheses").stdout.split() if h != tag_commit]
    print("DEBUG hyp:", hyp)
    if not hyp:
        problems.append("no `hypotheses` commit before the freeze tag")
    else:
        report = git("show", f"{hyp[0]}:report/REPORT.md").stdout
        print("DEBUG report length:", len(report) if report else "None")
        filled = [ln for ln in report.splitlines() if ln.lstrip("- ").startswith(("H1", "H2", "H3"))
                  and ln.split(":", 1)[-1].strip() and ":" in ln]
        print("DEBUG filled:", len(filled))
        if len(filled) < 3:
            problems.append("report/REPORT.md in the `hypotheses` commit has fewer than 3 filled hypotheses")
    n = 0
    for condition, src in SOURCES.items():
        frozen = hash_skills(src)
        for f in sorted((ROOT / "results" / condition).glob("*/run.json")):
            r = json.loads(f.read_text(encoding="utf-8"))
            n += 1
            if r.get("skills_sha256") != frozen:
                problems.append(f"{condition}/{r['task']}: skills differ from the frozen skills")
            if r.get("skills_modified"):
                problems.append(f"{condition}/{r['task']}: skills_modified is true")
            started = datetime.fromisoformat(r["timestamp"])
            if started.astimezone() < tag_time.astimezone():
                problems.append(f"{condition}/{r['task']}: run started before the freeze tag")
    for p in problems:
        print("FAIL:", p)
    print(f"checked {n} runs of skill conditions: {'OK' if not problems else str(len(problems)) + ' problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
