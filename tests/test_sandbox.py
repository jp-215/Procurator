"""Offline tests for the grading sandbox — these run in CI (no Mongo, no keys)."""
from __future__ import annotations

from runner.sandbox import GradeResult, grade


def test_skeleton_grades_zero():
    """The seeded skeleton must score 0/25 — calibrates metric M1's floor."""
    from pathlib import Path

    skeleton = Path(__file__).resolve().parent.parent / "target" / "src"
    r = grade(skeleton)
    assert r.total == 25, f"expected 25 ACs, got {r.total}"
    assert r.passed == 0, f"skeleton should pass nothing, passed: {r.passed}"
    assert set(r.per_ac) == {f"AC-{i:02d}" for i in range(1, 26)}


def test_newly_passing_delta():
    prev = GradeResult(passed=2, total=25, per_ac={"AC-01": "passed", "AC-02": "passed", "AC-03": "failed"})
    curr = GradeResult(passed=3, total=25, per_ac={"AC-01": "passed", "AC-02": "failed", "AC-03": "passed", "AC-04": "passed"})
    assert curr.newly_passing(prev) == ["AC-03", "AC-04"]
    assert curr.newly_passing(None) == ["AC-01", "AC-03", "AC-04"]


def test_pass_rate():
    assert GradeResult(passed=5, total=25).pass_rate == 0.2
    assert GradeResult().pass_rate == 0.0


def test_errors_counted():
    r = GradeResult(passed=0, total=25, per_ac={"AC-01": "error", "AC-02": "failed", "AC-03": "passed"})
    assert r.errors == 1
