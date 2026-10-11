"""Record decisions against cached material without another model call."""

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from ..models import WorkflowResult

def next_trial_id(decisions_path: Path) -> str:
    count = 0
    
    if decisions_path.exists():
        count = len(decisions_path.read_text(encoding="utf-8").splitlines())
        
    return f"trial_{count + 1:02d}"


class TrialSession:
    
    def __init__(self, participant_id: str, display: str, result: WorkflowResult):
        
        if not participant_id.strip():
            raise ValueError("Use a nonempty participant ID")
        
        if display not in {"2d", "xr"}:
            raise ValueError("Display must be 2d or xr")
        
        self.participant_id = participant_id
        self.display = display
        self.result = result
        self.started_at = None

    def present(self) -> dict:
        
        if self.started_at is None:
            self.started_at = perf_counter()
            
        return self.result.participant_payload()

    def record_decision(self, decision: str, path: str | Path) -> dict:
        
        if decision not in {"accept", "reject"}:
            raise ValueError("Decision must be accept or reject")
        
        path = Path(path)
        trial_id = next_trial_id(path)
        
        event = {"trial_id": trial_id, "participant_id": self.participant_id,
                 "display": self.display, "cache_id": self.result.cache_id,
                 "task_id": self.result.task["id"], "architecture": self.result.architecture,
                 "decision": decision, "decision_seconds": perf_counter() - self.started_at,
                 "timestamp": datetime.now(timezone.utc).isoformat()}
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")

        return event