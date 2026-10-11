"""Create fresh trial copies and restrict model writes to supplied app files."""

import difflib
import shutil
from pathlib import Path


def read_app_files(root: Path) -> dict[str, str]:
    
    app = root / "app"
    
    if not app.is_dir() or app.is_symlink():
        raise ValueError("Baseline must contain a real app directory")
    files = {}
    for path in sorted(app.rglob("*.py")):
        if path.is_symlink() or not path.resolve().is_relative_to(app.resolve()):
            raise ValueError("Application files must not traverse symlinks")
        files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    if not files:
        raise ValueError("Baseline has no Python application files")
    return files


def copy_baseline(baseline: Path, destination: Path) -> None:
    if destination.resolve().is_relative_to(baseline.resolve()):
        raise ValueError("Trial destination must be outside the baseline")
    if any(path.is_symlink() for path in baseline.rglob("*")):
        raise ValueError("Baseline must not contain symlinks")
    shutil.copytree(baseline, destination,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".env"))


def apply_replacements(root: Path, originals: dict[str, str], replacements: dict[str, str]) -> str:
    """Validate the entire edit set before writing; never execute generated code."""
    for name, content in replacements.items():
        if name not in originals:
            raise ValueError(f"Agent cannot modify unsupplied file: {name}")
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Unsafe replacement path: {name}")
        if not isinstance(content, str):
            raise ValueError(f"Replacement source must be text: {name}")
    diff = "".join(
        "".join(difflib.unified_diff(originals[name].splitlines(keepends=True),
                                     content.splitlines(keepends=True),
                                     fromfile=f"a/{name}", tofile=f"b/{name}"))
        for name, content in sorted(replacements.items())
    )
    for name, content in replacements.items():
        (root / name).write_text(content, encoding="utf-8")
    return diff