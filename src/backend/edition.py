"""Which copy of the app this is.

The researcher's repository is the full edition. `python -m src.backend.main export-participant`
builds a participant edition for remote sessions: it has no hidden tests, reference answers or
scores, and it contains a PARTICIPANT_EDITION marker file at its root."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MARKER = "PARTICIPANT_EDITION"

PARTICIPANT_EDITION = (PROJECT_ROOT / MARKER).is_file()
