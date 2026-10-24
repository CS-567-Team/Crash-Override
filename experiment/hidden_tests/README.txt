RESEARCHER ONLY. Hidden tests are never shown to agents or participants.

One folder per task id (matching experiment/tasks/<id>.json). Each test file loads the
app under test from the APP_ROOT environment variable, so the same suite can score the
baseline and any cached agent implementation:

    python -m src.backend.main evaluate runtime/cache/response_01.json

Each suite has two kinds of tests:
  - feature tests: the new behavior, including edge cases agents tend to miss
  - preservation tests: behavior that already worked on the baseline. If one of these
    fails after an agent's change it is counted as a regression.

An implementation "passes" only when every hidden test passes. The correct participant
decision is accept if it passes, reject otherwise.
