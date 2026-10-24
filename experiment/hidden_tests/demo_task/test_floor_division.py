import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path

APP = Path(os.environ["APP_ROOT"]) / "app" / "example_calculator.py"
spec = importlib.util.spec_from_file_location("calculator_under_test", APP)
calc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calc)


def run_console(text):
    return subprocess.run([sys.executable, str(APP)], input=text, text=True,
                          capture_output=True, timeout=5)


class FloorDivisionFeature(unittest.TestCase):

    def test_positive_operands(self):
        self.assertEqual(calc.calculate(7, "//", 2), 3)
        self.assertEqual(calc.calculate(11.5, "//", 2), 5)

    def test_negative_operands_round_toward_negative_infinity(self):
        self.assertEqual(calc.calculate(-7, "//", 2), -4)
        self.assertEqual(calc.calculate(7, "//", -2), -4)
        self.assertEqual(calc.calculate(-7.5, "//", 2), -4)

    def test_floor_division_by_zero_raises_value_error(self):
        with self.assertRaises(ValueError):
            calc.calculate(5, "//", 0)

    def test_console_supports_floor_division_and_keeps_running(self):
        completed = run_console("//\n-7\n2\n//\n1\n0\n+\n1\n1\nq\n")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Result: -4", completed.stdout)
        self.assertIn("Result: 2", completed.stdout)
        self.assertIn("Goodbye!", completed.stdout)


class FloorDivisionPreservation(unittest.TestCase):

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
            calc.calculate(1, "%", 2)

    def test_console_rejects_non_finite_input_and_quits(self):
        completed = run_console("+\nnan\ninf\n2\n3\nquit\n")
        self.assertEqual(completed.stdout.count("Please enter a finite number."), 2)
        self.assertIn("Result: 5", completed.stdout)
        self.assertIn("Goodbye!", completed.stdout)
