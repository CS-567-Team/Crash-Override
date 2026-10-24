"""Helpers and preservation tests shared by every hidden suite. Not a test module itself."""

import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path

APP = Path(os.environ["APP_ROOT"]) / "app" / "example_calculator.py"
_spec = importlib.util.spec_from_file_location("calculator_under_test", APP)
calc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(calc)


def run_console(text):
    return subprocess.run([sys.executable, str(APP)], input=text, text=True,
                          capture_output=True, timeout=5)


class Preservation(unittest.TestCase):
    """Baseline behavior every task must keep. Failures here count as regressions."""

    def test_existing_operations(self):
        self.assertEqual(calc.calculate(2, "+", 3), 5)
        self.assertEqual(calc.calculate(-2, "-", 3), -5)
        self.assertEqual(calc.calculate(1.5, "*", 4), 6)
        self.assertEqual(calc.calculate(7, "/", 2), 3.5)

    def test_division_by_zero_still_rejected(self):
        with self.assertRaises(ValueError):
            calc.calculate(1, "/", 0)

    def test_unknown_operator_rejected(self):
        with self.assertRaises(ValueError):
            calc.calculate(1, "^", 2)

    def test_console_rejects_non_finite_input_and_quits(self):
        completed = run_console("+\nnan\ninf\nabc\n2\n3\nquit\n")
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout.count("Please enter a finite number."), 3)
        self.assertIn("Result: 5", completed.stdout)
        self.assertIn("Goodbye!", completed.stdout)

    def test_console_exits_on_end_of_input(self):
        completed = run_console("+\n")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Goodbye!", completed.stdout)
