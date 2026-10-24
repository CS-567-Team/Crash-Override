"""Sanity-check hidden test suites: the reference solution must pass every hidden and visible
test, and the unchanged baseline must fail at least one feature test without regressions.

    python -m src.backend.experiment.check_suites
"""

import sys
from pathlib import Path

from ..services.repo import read_app_files
from ..services.testing import HIDDEN_TESTS, PROJECT_ROOT, evaluate

BASELINE = PROJECT_ROOT / "baseline"
REFERENCES = PROJECT_ROOT / "experiment" / "reference_solutions"


def check(task_id: str) -> list[str]:
    problems = []
    reference = REFERENCES / task_id
    if not reference.is_dir():
        return [f"no reference solution in {reference}"]

    good = evaluate(task_id, read_app_files(reference), baseline=BASELINE)
    failing = [t for t, s in {**good["visible"], **good["hidden"]}.items() if s != "passed"]
    if failing:
        problems.append(f"reference fails: {failing}")

    untouched = evaluate(task_id, read_app_files(BASELINE), baseline=BASELINE)
    if untouched["passes_hidden_tests"]:
        problems.append("baseline already passes every hidden test")
    if untouched["regressions"]:
        problems.append(f"baseline fails preservation tests: {untouched['regressions']}")
    return problems


if __name__ == "__main__":
    ok = True
    for suite in sorted(p for p in HIDDEN_TESTS.iterdir() if p.is_dir() and not p.name.startswith("_")):
        problems = check(suite.name)
        ok &= not problems
        print(f"{'OK  ' if not problems else 'FAIL'} {suite.name}" + "".join(f"\n     {p}" for p in problems))
    sys.exit(0 if ok else 1)
