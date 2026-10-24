import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Architecture(str, Enum):
    PROGRAMMER_ONLY = "programmer_only"
    PROGRAMMER_REVIEWER = "programmer_reviewer"
    PLANNER_PROGRAMMER_REVIEWER = "planner_programmer_reviewer"


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    prompt: str
    description: str = ""
    difficulty: str = "balanced"


@dataclass
class ModelResponse:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class AgentOutput:
    role: str
    data: dict[str, Any]
    system_prompt: str
    user_prompt: str
    response: ModelResponse
    elapsed_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowResult:
    cache_id: str
    task: dict[str, Any]
    architecture: str
    agents: list[dict[str, Any]]
    diff: str
    files: dict[str, str]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def participant_payload(self) -> dict[str, Any]:
        """The same display-independent material for 2D and XR panels."""
        return {
            "cache_id": self.cache_id,
            "task": self.task,
            "architecture": self.architecture,
            "agents": [{"role": a["role"], "data": a["data"]} for a in self.agents],
            "diff": self.diff,
            "original_files": self.original_files(),
            "files": self.files,
        }

    def original_files(self) -> dict[str, str]:
        """The first agent (planner or programmer) always receives the unmodified files."""
        return json.loads(self.agents[0]["user_prompt"])["files"]