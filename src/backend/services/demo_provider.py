"""Offline agent outputs for running and demoing the study without an API key.

Researcher-only: reads experiment/demo_fixtures and reference_solutions, and is left out of
the participant edition."""

import json
from pathlib import Path

from ..models import ModelResponse

EXPERIMENT = Path(__file__).resolve().parents[3] / "experiment"
FIXTURES = EXPERIMENT / "demo_fixtures"
REFERENCES = EXPERIMENT / "reference_solutions"
APP_FILE = "app/example_calculator.py"


class DemoProvider:
    """Offline agent outputs from experiment/demo_fixtures/<task_id>.json, so the whole study
    runs without an API key. Tasks marked use_seeded get their seeded bug; seeded=True
    forces the seeded bug for any task that has one."""

    def __init__(self, seeded: bool = False):
        self.seeded = seeded
        self.model = "offline-fixture-seeded-v2" if seeded else "offline-fixture-v2"

    @property
    def cache_identity(self) -> dict:
        return {"provider": "demo", "model": self.model}

    def complete(self, *, role: str, system_prompt: str, user_prompt: str) -> ModelResponse:

        context = json.loads(user_prompt)
        task_id = context["task"]["id"]
        path = FIXTURES / f"{task_id}.json"

        if not path.is_file():
            raise ValueError(f"No demo fixture for task {task_id!r} in {FIXTURES}")

        fixture = json.loads(path.read_text(encoding="utf-8"))

        if role == "planner":
            data = fixture["planner"]

        elif role == "programmer":

            if self.seeded and "seeded_file" not in fixture:
                raise ValueError(f"Task {task_id!r} has no seeded variant")

            if self.seeded or fixture.get("use_seeded"):
                source = (FIXTURES / fixture["seeded_file"]).read_text(encoding="utf-8")
            else:
                source = (REFERENCES / task_id / APP_FILE).read_text(encoding="utf-8")

            data = {"summary": fixture["programmer_summary"], "files": {APP_FILE: source}}

        elif role == "reviewer":
            data = fixture["reviewer"]

        else:
            raise ValueError(f"Unknown role: {role}")

        return ModelResponse(json.dumps(data), self.model)
