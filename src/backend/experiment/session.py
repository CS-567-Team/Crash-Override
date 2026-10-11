"""Record decisions against cached material without another model call."""

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from ..models import WorkflowResult


class TrialSession:
    def __init__(self, participant_id: str, display: str, result: WorkflowResult):
        if not participant_id.strip():
            raise ValueError("Use a nonempty pseudonymous participant ID")
        if display not in {"2d", "xr"}:
            raise ValueError("Display must be 2d or xr")
        self.participant_id = participant_id
        self.display = display
        self.result = result
        self.trial_id = uuid4().hex
        self.started_at = None
        self.decided = False

    def present(self) -> dict:
        """Call when the UI makes the material available; starts the decision clock."""
        if self.started_at is None:
            self.started_at = perf_counter()
        return self.result.participant_payload()

    def record_decision(self, decision: str, path: str | Path) -> dict:
        if decision not in {"accept", "reject"}:
            raise ValueError("Decision must be accept or reject")
        if self.started_at is None:
            raise ValueError("Present the trial before recording a decision")
        if self.decided:
            raise ValueError("This trial already has a decision")
        event = {"trial_id": self.trial_id, "participant_id": self.participant_id,
                 "display": self.display, "cache_id": self.result.cache_id,
                 "task_id": self.result.task["id"], "architecture": self.result.architecture,
                 "decision": decision, "decision_seconds": perf_counter() - self.started_at,
                 "timestamp": datetime.now(timezone.utc).isoformat()}
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")
        self.decided = True
        return event