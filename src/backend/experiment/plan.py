"""A participant's session: their six counterbalanced trials, matched to cached outputs.

Participant IDs carry their schedule row number (p01 -> row 1, p13 -> row 13, ...).
Progress comes from the decisions log, so the 2D app and the headset share it."""

import json
import re
from pathlib import Path

from ..pipelines.workflow import load_cached
from .schedule import CONDITIONS, DEFAULT_TASKS, build_schedule


def participant_row(participant_id: str) -> int:
    digits = re.findall(r"\d+", participant_id)
    if not digits or int(digits[-1]) < 1:
        raise ValueError("Use a participant ID with a number, like p01")
    return int(digits[-1])


def find_caches(runtime: Path) -> dict[tuple[str, str], str]:
    """Newest cached output for each (task, architecture)."""
    caches = {}
    paths = sorted((Path(runtime) / "cache").glob("response_*.json"),
                   key=lambda path: int(path.stem.split("_")[1]))
    for path in paths:
        result = load_cached(path)
        caches[(result.task["id"], result.architecture)] = result.cache_id
    return caches


def completed(decisions_path: Path, participant_id: str) -> set[str]:
    if not Path(decisions_path).is_file():
        return set()
    done = set()
    for line in Path(decisions_path).read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("participant_id") == participant_id:
            done.add(record["cache_id"])
    return done


def session_plan(participant_id: str, runtime: Path) -> list[dict]:
    row = participant_row(participant_id)
    trials = build_schedule(row, DEFAULT_TASKS)[-len(CONDITIONS):]
    caches = find_caches(runtime)
    done = completed(Path(runtime) / "decisions.jsonl", participant_id)
    for trial in trials:
        trial["participant"] = participant_id
        trial["cache_id"] = caches.get((trial["task"], trial["architecture"]))
        trial["done"] = trial["cache_id"] in done
    return trials


def next_trial(plan: list[dict]) -> dict | None:
    return next((trial for trial in plan if not trial["done"]), None)
