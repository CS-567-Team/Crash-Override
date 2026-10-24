"""Turn the decision log into tables for analysis.

    python -m src.backend.main analyze            # writes runtime/analysis/*.csv

trials.csv has one row per participant decision, joined with the trial's ground truth
and agent run metrics. summary.csv aggregates those rows by participant, architecture,
display, and architecture x display."""

import csv
import json
from pathlib import Path
from statistics import mean

from ..pipelines.workflow import load_cached

SECTIONS = ["task", "plan", "before", "after", "review"]

TRIAL_COLUMNS = [
    "participant_id", "trial_id", "timestamp", "display", "architecture", "task_id", "cache_id",
    "decision", "expected_decision", "correct", "seeded_failure", "decision_seconds",
    "trust", "confidence", *[f"first_view_{section}_seconds" for section in SECTIONS],
    "sections_viewed", "scrolls", "panel_moves", "hidden_pass_rate", "regressions",
    "reviewer_verdict", "model_calls", "agent_seconds", "input_tokens", "output_tokens",
]

SUMMARY_COLUMNS = [
    "group_by", "group", "trials", "accuracy", "seeded_failure_trials", "seeded_failure_caught",
    "correct_change_trials", "correct_change_accepted", "accept_rate", "mean_decision_seconds",
    "mean_trust", "mean_confidence",
]

GROUPINGS = {
    "participant": ("participant_id",),
    "architecture": ("architecture",),
    "display": ("display",),
    "architecture_x_display": ("architecture", "display"),
}


def read_decisions(path: Path) -> list[dict]:
    if not Path(path).is_file():
        return []
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def trial_row(record: dict, cache_dir: Path) -> dict:
    first_view = {}
    for event in record.get("interactions", []):
        if event.get("type") == "view":
            first_view.setdefault(event.get("target"), event.get("t"))
    count = lambda kind: sum(event.get("type") == kind for event in record.get("interactions", []))

    row = {
        **{key: record.get(key) for key in ("participant_id", "trial_id", "timestamp", "display", "architecture",
                                             "task_id", "cache_id", "decision", "expected_decision", "correct",
                                             "decision_seconds")},
        "seeded_failure": record.get("expected_decision") == "reject" if record.get("expected_decision") else None,
        "trust": record.get("responses", {}).get("trust"),
        "confidence": record.get("responses", {}).get("confidence"),
        **{f"first_view_{section}_seconds": first_view.get(section) for section in SECTIONS},
        "sections_viewed": len(first_view),
        "scrolls": count("scroll"),
        "panel_moves": count("grab"),
    }

    cache = cache_dir / f"{record.get('cache_id')}.json"
    if cache.is_file():
        result = load_cached(cache)
        evaluation = result.metadata.get("evaluation", {})
        reviewer = next((agent for agent in result.agents if agent["role"] == "reviewer"), None)
        row.update({
            "hidden_pass_rate": evaluation.get("hidden_pass_rate"),
            "regressions": len(evaluation.get("regressions", [])),
            "reviewer_verdict": reviewer["data"].get("verdict") if reviewer else None,
            "model_calls": result.metadata.get("model_calls"),
            "agent_seconds": result.metadata.get("elapsed_seconds"),
            "input_tokens": result.metadata.get("input_tokens"),
            "output_tokens": result.metadata.get("output_tokens"),
        })
    return row


def rate(rows: list[dict], key: str, value=True) -> float | None:
    known = [row for row in rows if row.get(key) is not None]
    return round(sum(row[key] == value for row in known) / len(known), 3) if known else None


def average(rows: list[dict], key: str) -> float | None:
    values = [row[key] for row in rows if isinstance(row.get(key), (int, float)) and not isinstance(row.get(key), bool)]
    return round(mean(values), 3) if values else None


def summarize(rows: list[dict]) -> list[dict]:
    summary = []
    for name, keys in GROUPINGS.items():
        groups: dict[str, list[dict]] = {}
        for row in rows:
            groups.setdefault(" / ".join(str(row.get(key)) for key in keys), []).append(row)
        for group, members in sorted(groups.items()):
            seeded = [row for row in members if row.get("seeded_failure") is True]
            correct_changes = [row for row in members if row.get("seeded_failure") is False]
            summary.append({
                "group_by": name, "group": group, "trials": len(members),
                "accuracy": rate(members, "correct"),
                "seeded_failure_trials": len(seeded),
                "seeded_failure_caught": rate(seeded, "decision", "reject"),
                "correct_change_trials": len(correct_changes),
                "correct_change_accepted": rate(correct_changes, "decision", "accept"),
                "accept_rate": rate(members, "decision", "accept"),
                "mean_decision_seconds": average(members, "decision_seconds"),
                "mean_trust": average(members, "trust"),
                "mean_confidence": average(members, "confidence"),
            })
    return summary


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, columns)
        writer.writeheader()
        writer.writerows(rows)


def analyze(runtime: Path, out_dir: Path) -> tuple[list[dict], list[dict]]:
    runtime = Path(runtime)
    rows = [trial_row(record, runtime / "cache") for record in read_decisions(runtime / "decisions.jsonl")]
    summary = summarize(rows)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "trials.csv", TRIAL_COLUMNS, rows)
    write_csv(out_dir / "summary.csv", SUMMARY_COLUMNS, summary)
    return rows, summary
