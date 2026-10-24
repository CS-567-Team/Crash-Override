"""What a participant sees for one trial, as ordered sections.

Both displays render exactly these sections (2D in Streamlit, XR as panels), so the only
thing that differs between conditions is the presentation."""

import difflib
import json
from pathlib import Path

CONTEXT_PATH = Path(__file__).resolve().parents[3] / "experiment" / "participant_context.json"

ROLE_ORDER = ["planner", "programmer", "reviewer"]


def load_context() -> dict:
    return json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))


def bullets(items: list[str]) -> str:
    return "\n".join(f"• {item}" for item in items) if items else "(none)"


def changed_lines(before: str, after: str) -> tuple[list[int], list[int]]:
    """1-based line numbers that differ: (changed or removed in before, changed or added in after)."""
    old, new = [], []
    matcher = difflib.SequenceMatcher(None, before.splitlines(), after.splitlines(), autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            old.extend(range(i1 + 1, i2 + 1))
            new.extend(range(j1 + 1, j2 + 1))
    return old, new


def code_files(original: dict[str, str], updated: dict[str, str], side: str) -> list[dict]:
    files = []
    for name, before in original.items():
        after = updated.get(name, before)
        old, new = changed_lines(before, after)
        files.append({"name": name, "source": before if side == "before" else after,
                      "highlight": old if side == "before" else new})
    return files


def build_sections(payload: dict, context: dict | None = None) -> list[dict]:
    """Sections in workflow order: task, plan, code before, code after, review.

    Code is shown as two complete files (before and after) with the changed lines
    highlighted, rather than as a diff, so it reads like normal code."""

    context = context or load_context()
    agents = {agent["role"]: agent["data"] for agent in payload["agents"]}
    task = payload["task"]
    team = "\n".join(context["roles"][role] for role in ROLE_ORDER if role in agents)

    sections = [{
        "id": "task", "title": "Your task", "kind": "text",
        "text": f"FEATURE REQUEST\n{task['title']}: {task['description']}\n\n"
                f"Exact request given to the agents:\n{task['prompt']}\n\n"
                f"THE PROGRAM\n{context['app_description']}\n\n"
                f"WHO WORKED ON THIS CHANGE\n{team}\n\n"
                f"YOUR DECISION\n{context['decision_help']}",
    }]

    if "planner" in agents:
        plan = agents["planner"]
        steps = "\n".join(f"{i}. {step}" for i, step in enumerate(plan["steps"], 1))
        sections.append({
            "id": "plan", "title": "Planner: plan", "kind": "text",
            "text": f"{plan['summary']}\n\nSTEPS\n{steps}\n\nEDGE CASES TO HANDLE\n{bullets(plan['edge_cases'])}",
        })

    original, updated = payload["original_files"], payload["files"]
    sections.append({
        "id": "before", "title": "Code before the change", "kind": "code", "side": "before",
        "note": "The program as it was before the agents worked on it. "
                "Highlighted lines are the ones the programmer changed or removed.",
        "files": code_files(original, updated, "before"),
    })
    sections.append({
        "id": "after", "title": "Programmer: code after the change", "kind": "code", "side": "after",
        "note": f"Programmer's summary: {agents['programmer']['summary']}\n\n"
                "Highlighted lines are the ones the programmer added or changed.",
        "files": code_files(original, updated, "after"),
    })

    if "reviewer" in agents:
        review = agents["reviewer"]
        verdict = "APPROVE" if review["verdict"] == "approve" else "REQUEST CHANGES"
        sections.append({
            "id": "review", "title": "Reviewer: feedback", "kind": "text", "verdict": review["verdict"],
            "text": f"VERDICT: {verdict}\n\n{review['summary']}\n\nISSUES FOUND\n{bullets(review['issues'])}"
                    f"\n\nLIMITATIONS\n{bullets(review['limitations'])}",
        })

    return sections
