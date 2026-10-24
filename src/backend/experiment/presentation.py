"""What a participant sees for one trial, as ordered sections.

Both displays render exactly these sections (2D in Streamlit, XR as panels), so the only
thing that differs between conditions is the presentation."""

import json
from pathlib import Path

CONTEXT_PATH = Path(__file__).resolve().parents[3] / "experiment" / "participant_context.json"

ROLE_ORDER = ["planner", "programmer", "reviewer"]


def load_context() -> dict:
    return json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))


def bullets(items: list[str]) -> str:
    return "\n".join(f"• {item}" for item in items) if items else "(none)"


def build_sections(payload: dict, context: dict | None = None) -> list[dict]:
    """Sections in workflow order: task, original code, plan, code changes, review."""

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

    sections.append({
        "id": "original", "title": "Original code (before the change)", "kind": "code",
        "text": "\n\n".join(f"# {name}\n{source}" for name, source in payload["original_files"].items()),
    })

    if "planner" in agents:
        plan = agents["planner"]
        steps = "\n".join(f"{i}. {step}" for i, step in enumerate(plan["steps"], 1))
        sections.append({
            "id": "plan", "title": "Planner: plan", "kind": "text",
            "text": f"{plan['summary']}\n\nSTEPS\n{steps}\n\nEDGE CASES TO HANDLE\n{bullets(plan['edge_cases'])}",
        })

    sections.append({
        "id": "diff", "title": "Programmer: code changes", "kind": "diff",
        "summary": agents["programmer"]["summary"],
        "text": payload["diff"] or "(no changes)",
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
