"""Add a remote participant's decisions to the researcher's log and score them.

    python -m src.backend.main merge p03_decisions.jsonl [more.jsonl ...] [--dry-run]

Each line comes from the participant edition, which has no scores. For each decision this
looks up the same cache_id in the researcher's runtime/cache, checks that the task and
workflow match, fills in expected_decision and correct, gives it the next trial_id in the
researcher's log (keeping the participant's own as remote_trial_id), and appends it.
Decisions already in the log (same participant and cache_id) are skipped, so merging the
same file twice is safe."""

import json
from datetime import datetime, timezone
from pathlib import Path

from ..pipelines.workflow import load_cached
from .session import next_trial_id

REQUIRED = ["participant_id", "display", "cache_id", "task_id", "architecture", "decision"]


def read_lines(path: Path) -> list[dict]:
    records = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path} line {number} is not valid JSON ({error.msg})") from error
        missing = [key for key in REQUIRED if key not in record]
        if missing:
            raise ValueError(f"{path} line {number} is missing {missing}")
        if record["decision"] not in {"accept", "reject"}:
            raise ValueError(f"{path} line {number} has decision {record['decision']!r}")
        records.append(record)
    return records


def score(record: dict, cache_dir: Path) -> dict:
    cache = cache_dir / f"{record['cache_id']}.json"
    if not cache.is_file():
        raise ValueError(f"{record['participant_id']}: {record['cache_id']} is not in {cache_dir}")
    result = load_cached(cache)
    if (result.task["id"], result.architecture) != (record["task_id"], record["architecture"]):
        raise ValueError(f"{record['participant_id']}: {record['cache_id']} is "
                         f"{result.task['id']} / {result.architecture} here but "
                         f"{record['task_id']} / {record['architecture']} in their file. "
                         "Their copy was exported from different caches.")
    expected = result.metadata.get("evaluation", {}).get("correct_decision")
    return {**record, "expected_decision": expected,
            "correct": None if expected is None else record["decision"] == expected}


def merge(paths: list[Path], runtime: Path, *, dry_run: bool = False) -> dict:
    """Validate everything first, then append. Returns counts for the report."""
    runtime = Path(runtime)
    log = runtime / "decisions.jsonl"
    existing = ([json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
                if log.is_file() else [])
    seen = {(r.get("participant_id"), r.get("cache_id")) for r in existing}

    added, skipped = [], []
    for path in paths:
        for record in read_lines(path):
            key = (record["participant_id"], record["cache_id"])
            if key in seen:
                skipped.append(record)
                continue
            seen.add(key)
            scored = score(record, runtime / "cache")
            scored.update({"remote_trial_id": record.get("trial_id"), "source_file": Path(path).name,
                           "merged_at": datetime.now(timezone.utc).isoformat()})
            added.append(scored)

    if not dry_run and added:
        log.parent.mkdir(parents=True, exist_ok=True)
        for record in added:
            record["trial_id"] = next_trial_id(log)
            with log.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record) + "\n")

    participants: dict[str, dict] = {}
    for record in added:
        stats = participants.setdefault(record["participant_id"], {"trials": 0, "correct": 0})
        stats["trials"] += 1
        stats["correct"] += bool(record["correct"])
    return {"added": len(added), "skipped": len(skipped), "participants": participants, "log": str(log)}
