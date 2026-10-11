"""Load participant-visible requirements, rejecting researcher-only fields."""

import json
from dataclasses import fields
from pathlib import Path

from ..models import Task


def load_task(path: str | Path) -> Task:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Task must be a JSON object")
    allowed = {f.name for f in fields(Task)}
    if set(data) - allowed:
        raise ValueError("Keep hidden tests, answers, and seed metadata outside public task JSON")
    for key in ("id", "title", "prompt"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"Task requires nonempty {key}")
    if not all(isinstance(value, str) for value in data.values()):
        raise ValueError("Task fields must be strings")
    return Task(**data)