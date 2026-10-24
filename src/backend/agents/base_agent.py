"""Shared execution and strict output validation for the three roles."""

import json
from dataclasses import asdict
from time import perf_counter
from typing import Any

from ..models import AgentOutput, Task
from ..services.model import ModelProvider


class BaseAgent:
    
    role: str
    system_prompt: str
    required: dict[str, type] = {}

    def __init__(self, provider: ModelProvider):
        self.provider = provider

    def run(self, task: Task, files: dict[str, str], **extra: Any) -> AgentOutput:
        
        user_prompt = json.dumps({"task": asdict(task), 
                                  "files": files, 
                                  **extra}, 
                                sort_keys=True)
        
        started = perf_counter()
        
        response = self.provider.complete(role=self.role, 
                                          system_prompt=self.system_prompt,
                                          user_prompt=user_prompt)
        
        elapsed = perf_counter() - started
        
        data = self.parse(response.text)

        return AgentOutput(self.role, data, self.system_prompt, user_prompt, response, elapsed)

    def parse(self, text: str) -> dict[str, Any]:
        """Extract the JSON object from a reply (models sometimes wrap it in ``` fences)."""

        start, end = text.find("{"), text.rfind("}")

        if start == -1 or end < start:
            raise ValueError(f"{self.role} did not return a JSON object")

        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError as error:
            raise ValueError(f"{self.role} returned invalid JSON: {error}") from error

        for key, kind in self.required.items():
            if not isinstance(data.get(key), kind):
                raise ValueError(f"{self.role} output needs {key!r} as {kind.__name__}")

        return data
