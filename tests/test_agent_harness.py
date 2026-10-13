"""CI gate for the lab-review AST contract harness (tests/agent_harness/).

Runs the seven required cases from docs/EVALUATION_HARNESS.md section 2
and fails the build if any of them regresses.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "agent_harness"))

from lab_review_cases import HarnessCase, run_lab_review_harness  # noqa: E402


@pytest.mark.parametrize("case", run_lab_review_harness(), ids=lambda c: c.case_id)
def test_lab_review_harness_case(case: HarnessCase) -> None:
    assert case.passed, f"{case.case_id} failed: {case.requirement}\n  {case.detail}"


def test_harness_covers_all_seven_required_cases() -> None:
    cases = run_lab_review_harness()
    assert {c.case_id for c in cases} == {f"REQ-{i}" for i in range(1, 8)}
