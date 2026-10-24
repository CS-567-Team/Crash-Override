import json
import os
from pathlib import Path
from typing import Protocol

from ..models import ModelResponse

EXPERIMENT = Path(__file__).resolve().parents[3] / "experiment"
FIXTURES = EXPERIMENT / "demo_fixtures"
REFERENCES = EXPERIMENT / "reference_solutions"
APP_FILE = "app/example_calculator.py"

class ModelProvider(Protocol):
    @property
    def cache_identity(self) -> dict: ...

    def complete(self, *, role: str, system_prompt: str, user_prompt: str) -> ModelResponse: ...
    

class OpenAIProvider:
    """Calls the OpenAI chat API with the same settings for every role."""

    def __init__(self, model: str | None = None):
        try:
            from openai import OpenAI
        except ImportError as error:
            raise ImportError("Install the openai package: pip install -r requirements.txt") from error

        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("Set OPENAI_API_KEY in .env (see .env.example)")

        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4")
        self.temperature = float(os.environ.get("OPENAI_TEMPERATURE", "0"))
        self.seed = int(os.environ.get("OPENAI_SEED", "567"))
        self.client = OpenAI()

    @property
    def cache_identity(self) -> dict:
        return {"provider": "openai", "model": self.model,
                "temperature": self.temperature, "seed": self.seed}

    def complete(self, *, role: str, system_prompt: str, user_prompt: str) -> ModelResponse:

        request = {"model": self.model, "temperature": self.temperature, "seed": self.seed,
                   "messages": [{"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}]}

        # JSON mode is not supported by every model (e.g. the original gpt-4), so fall back
        # to plain text and let the agent extract the JSON object.
        from openai import BadRequestError
        try:
            completion = self.client.chat.completions.create(
                response_format={"type": "json_object"}, **request)
        except BadRequestError:
            completion = self.client.chat.completions.create(**request)

        usage = completion.usage
        return ModelResponse(completion.choices[0].message.content or "", completion.model,
                             usage.prompt_tokens if usage else 0,
                             usage.completion_tokens if usage else 0)


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
