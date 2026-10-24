"""Counterbalanced trial order for the 3 x 2 within-subjects design.

Trials are blocked by display so each participant switches device only once: three trials
on the laptop, then three in the headset (or the reverse). Across every 12 participants:
  - half start with the laptop and half with the headset
  - each of the 6 orders of the three workflows is used once with each block order
    (the same workflow order is used in both blocks)
  - tasks rotate so each task is paired with each workflow x display condition twice

    python -m src.backend.experiment.schedule --participants 12 > experiment/schedule.csv
"""

import argparse
import csv
import sys
from itertools import permutations, product

from ..models import Architecture

DISPLAYS = ["2d", "xr"]
CONDITIONS = [(a.value, d) for a, d in product(Architecture, DISPLAYS)]
WORKFLOW_ORDERS = list(permutations(a.value for a in Architecture))
# The seeded-bug tasks (modulo, overflow_guard) sit at one odd and one even index, so every
# participant gets one seeded trial in each display block.
DEFAULT_TASKS = ["demo_task", "modulo", "exponent", "reuse_answer", "overflow_guard", "result_format"]
SEEDED_TASKS = {"modulo", "overflow_guard"}


def build_schedule(participants: int, tasks: list[str]) -> list[dict]:
    n = len(CONDITIONS)
    if len(tasks) != n:
        raise ValueError(f"Need exactly {n} tasks, got {len(tasks)}")

    rows = []
    for p in range(participants):
        blocks = DISPLAYS if p % 2 == 0 else DISPLAYS[::-1]
        workflows = WORKFLOW_ORDERS[(p // 2) % len(WORKFLOW_ORDERS)]
        order = [(architecture, display) for display in blocks for architecture in workflows]
        for position, (architecture, display) in enumerate(order, 1):
            condition = CONDITIONS.index((architecture, display))
            rows.append({"participant": f"p{p + 1:02d}", "position": position,
                         "architecture": architecture, "display": display,
                         "task": tasks[(condition + p) % n]})
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--participants", type=int, default=12)
    parser.add_argument("--tasks", nargs="+", default=DEFAULT_TASKS)
    args = parser.parse_args()

    writer = csv.DictWriter(sys.stdout, ["participant", "position", "architecture", "display", "task"])
    writer.writeheader()
    writer.writerows(build_schedule(args.participants, args.tasks))
