"""Censor's grading sandbox.

Copies target/src into a temp dir, injects the hidden suite, runs pytest with a
JSON report, and returns per-AC results. The hidden_tests path is never exposed
to any agent — only this runner touches it, and the suite runs from a temp copy.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIDDEN = ROOT / "hidden_tests"
AC_RE = re.compile(r"test_ac(\d+)")


@dataclass
class GradeResult:
    passed: int = 0
    total: int = 0
    per_ac: dict[str, str] = field(default_factory=dict)  # "AC-07" -> passed|failed|error
    stderr_tail: str = ""

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def newly_passing(self, previous: "GradeResult | None") -> list[str]:
        prev = {ac for ac, s in (previous.per_ac if previous else {}).items() if s == "passed"}
        return sorted(ac for ac, s in self.per_ac.items() if s == "passed" and ac not in prev)


def grade(src_dir: Path | None = None, timeout: int = 120, wave: int = 1) -> GradeResult:
    """Grade a source tree (default: target/src) against the hidden suite."""
    from core.paths import target_src

    src = Path(src_dir) if src_dir else target_src()
    with tempfile.TemporaryDirectory(prefix="procurator-grade-") as tmp:
        tmpdir = Path(tmp)
        shutil.copytree(src, tmpdir / "src")
        (tmpdir / "tests").mkdir()
        for f in sorted(HIDDEN.glob("*.py")):
            if wave < 2 and "wave2" in f.name:
                continue
            shutil.copy(f, tmpdir / "tests" / f.name)
        report = tmpdir / "report.json"
        proc = subprocess.run(
            [
                sys.executable, "-m", "pytest", str(tmpdir / "tests"),
                "--json-report", f"--json-report-file={report}",
                "-q", "--no-header", "-p", "no:cacheprovider",
            ],
            capture_output=True, text=True, timeout=timeout,
            cwd=tmpdir,
            env={"PYTHONPATH": str(tmpdir / "src"), "PATH": "/usr/bin:/bin"},
        )
        result = GradeResult(stderr_tail=(proc.stderr or "")[-2000:])
        if not report.exists():
            return result  # collection crashed entirely: 0/0 with stderr for debugging
        data = json.loads(report.read_text())
        for test in data.get("tests", []):
            m = AC_RE.search(test.get("nodeid", ""))
            if not m:
                continue
            ac = f"AC-{int(m.group(1)):02d}"
            outcome = test.get("outcome", "error")
            result.per_ac[ac] = "passed" if outcome == "passed" else outcome
            result.total += 1
            if outcome == "passed":
                result.passed += 1
        return result


if __name__ == "__main__":
    r = grade(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    print(f"{r.passed}/{r.total} ({r.pass_rate:.0%})")
    for ac in sorted(r.per_ac):
        print(f"  {ac}: {r.per_ac[ac]}")
    if r.total == 0:
        print("--- stderr ---"); print(r.stderr_tail)
