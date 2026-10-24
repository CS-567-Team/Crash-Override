"""Counterbalanced trial order for the 3 x 2 within-subjects design.

Condition order follows a Williams (balanced Latin) square, so every condition appears in
every position and follows every other condition equally often. Tasks are rotated
separately so each task is paired with each condition across participants.

    python -m src.backend.experiment.schedule --participants 12 > experiment/schedule.csv
"""

import argparse
import csv
import sys
from itertools import product

from ..models import Architecture

DISPLAYS = ["2d", "xr"]
CONDITIONS = [(a.value, d) for a, d in product(Architecture, DISPLAYS)]
DEFAULT_TASKS = ["demo_task", "modulo", "exponent", "reuse_answer", "result_format", "overflow_guard"]


def williams_row(n: int, row: int) -> list[int]:
    first = [0]
    low, high = 1, n - 1
    while len(first) < n:
        first.append(low)
        low += 1
        if len(first) < n:
            first.append(high)
            high -= 1
    return [(value + row) % n for value in first]


def build_schedule(participants: int, tasks: list[str]) -> list[dict]:
    n = len(CONDITIONS)
    if len(tasks) != n:
        raise ValueError(f"Need exactly {n} tasks, got {len(tasks)}")

    rows = []
    for p in range(participants):
        # Every block of n participants shifts the task pairing by one more step.
        shift = p + p // n
        for position, condition in enumerate(williams_row(n, p)):
            architecture, display = CONDITIONS[condition]
            rows.append({"participant": f"p{p + 1:02d}", "position": position + 1,
                         "architecture": architecture, "display": display,
                         "task": tasks[(condition + shift) % n]})
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--participants", type=int, default=12)
    parser.add_argument("--tasks", nargs="+", default=DEFAULT_TASKS)
    args = parser.parse_args()

    writer = csv.DictWriter(sys.stdout, ["participant", "position", "architecture", "display", "task"])
    writer.writeheader()
    writer.writerows(build_schedule(args.participants, args.tasks))
