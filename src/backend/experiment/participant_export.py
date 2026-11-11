"""Build the participant edition: a copy of the study app that remote participants run on
their own laptop and headset.

    python -m src.backend.main export-participant        # -> dist/crash-override-participant.zip

The copy has the full app and the exact cached agent outputs the study uses, but nothing that
reveals the answers: no hidden tests, reference solutions, demo fixtures, test suite, research
notes, or scores. Each cached output keeps its cache_id, so `merge` can score the participant's
decisions against the researcher's cache later."""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ..edition import MARKER
from ..models import Architecture
from .plan import find_caches
from .schedule import DEFAULT_TASKS

PROJECT_ROOT = Path(__file__).resolve().parents[3]
NAME = "crash-override-participant"

# Only these paths are copied (allowlist, so new researcher files never leak by accident).
INCLUDE = ["src", "experiment/participant_context.json", "requirements.txt", ".gitignore"]
INCLUDE_TASKS = DEFAULT_TASKS
# Researcher-only code inside src/.
EXCLUDE = {"src/backend/experiment/check_suites.py", "src/backend/experiment/participant_export.py",
           "src/backend/experiment/merge.py", "src/backend/experiment/metrics.py",
           "src/backend/services/demo_provider.py"}
SKIP_DIRS = {"__pycache__", ".ipynb_checkpoints"}

# Words that must not appear anywhere in the exported caches.
FORBIDDEN = ["correct_decision", "hidden_pass_rate", "passes_hidden_tests", "has_hidden_tests",
             "seeded", "reference_solution", "hidden_test", "demo_fixture", "offline-fixture"]

SETUP_GUIDE = PROJECT_ROOT / "PARTICIPANT_SETUP.md"


def sanitize(data: dict) -> dict:
    """Keep only what the participant apps read; drop scores, provider identity and paths."""
    agents = [{
        "role": agent["role"], "data": agent["data"],
        "system_prompt": agent["system_prompt"], "user_prompt": agent["user_prompt"],
        "response": {"text": agent["response"]["text"], "model": "cached",
                     "input_tokens": agent["response"].get("input_tokens", 0),
                     "output_tokens": agent["response"].get("output_tokens", 0)},
        "elapsed_seconds": agent.get("elapsed_seconds", 0),
    } for agent in data["agents"]]
    return {"cache_id": data["cache_id"], "task": data["task"], "architecture": data["architecture"],
            "agents": agents, "diff": data["diff"], "files": data["files"],
            "metadata": {"pipeline_version": data["metadata"].get("pipeline_version"),
                         "model_calls": len(agents), "participant_edition": True}}


def leaks(text: str) -> list[str]:
    lowered = text.lower()
    return [word for word in FORBIDDEN if word in lowered]


def copy_tree(source: Path, target: Path, relative: str) -> None:
    if source.is_file():
        if relative not in EXCLUDE:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return
    for child in sorted(source.iterdir()):
        if child.name in SKIP_DIRS or child.suffix in {".pyc", ".pyo"}:
            continue
        copy_tree(child, target / child.name, f"{relative}/{child.name}")


def export(runtime: Path, out_dir: Path, *, make_zip: bool = True) -> dict:
    """Write <out_dir>/crash-override-participant/ (and .zip). Returns the manifest."""
    runtime, out_dir = Path(runtime).resolve(), Path(out_dir).resolve()
    caches = find_caches(runtime)
    needed = [(task, architecture.value) for task in DEFAULT_TASKS for architecture in Architecture]
    missing = [f"{task} / {architecture}" for task, architecture in needed if (task, architecture) not in caches]
    if missing:
        raise ValueError("No cached output for: " + ", ".join(missing) +
                         ". Generate them first (python -m src.backend.main generate --all ...).")

    target = out_dir / NAME
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    for relative in INCLUDE:
        copy_tree(PROJECT_ROOT / relative, target / relative, relative)
    for task in INCLUDE_TASKS:
        copy_tree(PROJECT_ROOT / "experiment/tasks" / f"{task}.json",
                  target / "experiment/tasks" / f"{task}.json", f"experiment/tasks/{task}.json")
    (target / "runtime").mkdir()
    (target / "runtime" / ".gitkeep").touch()
    if SETUP_GUIDE.is_file():
        shutil.copy2(SETUP_GUIDE, target / "README.md")

    manifest = {"exported_at": datetime.now(timezone.utc).isoformat(), "trials": []}
    (target / "runtime" / "cache").mkdir()
    for task, architecture in needed:
        cache_id = caches[(task, architecture)]
        data = json.loads((runtime / "cache" / f"{cache_id}.json").read_text(encoding="utf-8"))
        text = json.dumps(sanitize(data), indent=2) + "\n"
        found = leaks(text)
        if found:
            raise ValueError(f"{cache_id} would reveal {found}; not exporting")
        (target / "runtime" / "cache" / f"{cache_id}.json").write_text(text, encoding="utf-8")
        manifest["trials"].append({"cache_id": cache_id, "task_id": task, "architecture": architecture,
                                   "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})

    # Safety net: none of the researcher-only folders may exist in the copy.
    for forbidden in ["experiment/hidden_tests", "experiment/reference_solutions",
                      "experiment/demo_fixtures", "tests", "baseline"]:
        if (target / forbidden).exists():
            raise RuntimeError(f"{forbidden} ended up in the participant copy")

    (target / MARKER).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    # The researcher keeps a copy so `merge` can confirm a participant used the same trials.
    (runtime / "participant_edition_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                                                encoding="utf-8")
    if make_zip:
        zip_path = shutil.make_archive(str(out_dir / NAME), "zip", root_dir=out_dir, base_dir=NAME)
        manifest["zip"] = zip_path
    manifest["folder"] = str(target)
    return manifest
