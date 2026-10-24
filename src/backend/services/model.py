import json
import os
from typing import Protocol

from ..models import ModelResponse

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
    """Offline fixture for demo_task. seeded=True returns a plausible but wrong
    implementation (truncates toward zero) that the reviewer still approves."""

    def __init__(self, seeded: bool = False):
        self.seeded = seeded
        self.model = "offline-fixture-seeded-v1" if seeded else "offline-fixture-v1"

    @property
    def cache_identity(self) -> dict:
        return {"provider": "demo", "model": self.model}

    def complete(self, *, role: str, system_prompt: str, user_prompt: str) -> ModelResponse:
        
        context = json.loads(user_prompt)
        
        if context["task"]["id"] != "demo_task":
            raise ValueError("Demo provider only supports experiment/tasks/demo_task.json.")
        
        if role == "planner":
            
            data = {"summary": "Add floor division to calculation and the console menu.",
                    "steps": ["Handle // and reject a zero divisor.", "Expose // in the menu."],
                    "edge_cases": ["Zero divisor", "Negative operands", "Decimals"]}
            
        elif role == "programmer":
            
            source = context["files"]["app/example_calculator.py"]
            anchor = '    if operator == "/":\n'
            
            if source.count(anchor) != 1:
                raise ValueError("Demo fixture expects the original calculator baseline.")
            
            source = source.replace(anchor,
                '    if operator == "//":\n'
                '        if right == 0:\n'
                '            raise ValueError("Cannot floor divide by zero.")\n'
                + ('        return float(int(left / right))\n' if self.seeded
                 else '        return left // right\n') + anchor)
            source = source.replace("Choose +, -, *, or /.",
                                    "Choose +, -, *, or /. You can also choose //.")
            source = source.replace("Calculator: +, -, *, / (", "Calculator: +, -, *, /, // (")
            source = source.replace('{"+", "-", "*", "/"}', '{"+", "-", "*", "/", "//"}')
            data = {"summary": "Added floor division with Python floor-division semantics.",
                    "files": {"app/example_calculator.py": source}}
            
        elif role == "reviewer":
            
            data = {"summary": "Floor division handling and console routing are present.",
                    "verdict": "approve", "issues": [],
                    "limitations": ["Static fixture review; no tests were executed by this agent."]}
            
        else:
            raise ValueError(f"Unknown role: {role}")
        
        return ModelResponse(json.dumps(data), self.model)