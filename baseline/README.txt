Contains the original small application that the AI agents will modify during the study.
This version should remain untouched during experiments.

Console calculator (Python 3; no third-party dependencies)

Run from the repository root:
    python baseline/app/example_calculator.py

Choose +, -, *, or /, then enter two numbers. Negative numbers and decimals
are supported. Invalid input can be retried, and division by zero is reported
without terminating the app. Enter q, quit, or exit at the operation prompt
to quit. Ctrl+C or end-of-input also exits cleanly.

Run the tests from the repository root:
    python -m unittest discover -s baseline/tests -v
