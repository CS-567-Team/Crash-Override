"""Score an implementation against visible and hidden tests (researcher-only results).

Hidden tests live in experiment/hidden_tests/<task_id>/ and import the app under test from
the APP_ROOT environment variable. They are never shown to agents or participants."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .repo import copy_baseline

RUNNER = Path(__file__).with_name("test_runner.py")
PROJECT_ROOT = Path(__file__).resolve().parents[3]
HIDDEN_TESTS = PROJECT_ROOT / "experiment" / "hidden_tests"


def run_tests(test_dir: Path, app_root: Path, timeout: float = 60) -> dict[str, str]:

    if not test_dir.is_dir():
        return {}

    env = {**os.environ, "APP_ROOT": str(app_root), "PYTHONDONTWRITEBYTECODE": "1"}

    try:
        completed = subprocess.run([sys.executable, str(RUNNER), str(test_dir)],
                                   capture_output=True, text=True, timeout=timeout, env=env)
        return json.loads(completed.stdout.strip().splitlines()[-1])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, IndexError):
        return {"<suite>": "error"}


def pass_rate(statuses: dict[str, str]) -> float | None:
    return sum(s == "passed" for s in statuses.values()) / len(statuses) if statuses else None


def evaluate(task_id: str, files: dict[str, str], *, baseline: Path,
             hidden_root: Path = HIDDEN_TESTS) -> dict:
    """Materialize the candidate files on a copy of the baseline and run every suite.

    A regression is a hidden test that passed on the baseline but fails on the candidate."""

    baseline = Path(baseline).resolve()
    hidden_dir = Path(hidden_root) / task_id

    with tempfile.TemporaryDirectory() as tmp:

        workspace = Path(tmp) / "repo"
        copy_baseline(baseline, workspace)

        for name, content in files.items():
            (workspace / name).write_text(content, encoding="utf-8")

        visible = run_tests(workspace / "tests", workspace)
        hidden = run_tests(hidden_dir, workspace)
        hidden_on_baseline = run_tests(hidden_dir, baseline)

    regressions = sorted(test for test, status in hidden.items()
                         if status != "passed" and hidden_on_baseline.get(test) == "passed")
    passes = bool(hidden) and all(s == "passed" for s in hidden.values())

    return {"visible": visible, "hidden": hidden,
            "visible_pass_rate": pass_rate(visible), "hidden_pass_rate": pass_rate(hidden),
            "regressions": regressions, "has_hidden_tests": bool(hidden),
            "passes_hidden_tests": passes,
            # Ground truth for decision accuracy: accept iff the hidden tests pass.
            "correct_decision": ("accept" if passes else "reject") if hidden else None}
