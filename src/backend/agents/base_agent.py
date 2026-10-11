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
        
            
        data = json.loads(response.text)   
 
        return AgentOutput(self.role, data, self.system_prompt, user_prompt, response, elapsed)

