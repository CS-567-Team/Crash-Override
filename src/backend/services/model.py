import json
import os
from typing import Protocol
#from openai import OpenAI

from ..models import ModelResponse

class ModelProvider(Protocol):
    @property
    def cache_identity(self) -> dict: ...

    def complete(self, *, role: str, system_prompt: str, user_prompt: str) -> ModelResponse: ...
    

""" 

TODO: Implement actual OpenAI API integration for the OpenAIProvider class.

"""
class OpenAIProvider:
    def __init__(self, model=None):
        raise RuntimeError("OpenAIProvider not implemented yet; use --provider demo")
    
    
class DemoProvider:

    @property
    def cache_identity(self) -> dict:
        return {"provider": "demo", "model": "offline-fixture-v1"}

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
                '        return left // right\n' + anchor)
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
        
        return ModelResponse(json.dumps(data), "offline-fixture-v1")