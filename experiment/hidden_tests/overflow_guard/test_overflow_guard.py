import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import Preservation, calc, run_console  # noqa: E402,F401


class OverflowGuardFeature(unittest.TestCase):

    def test_multiplication_overflow(self):
        with self.assertRaises(ValueError):
            calc.calculate(1e308, "*", 10)

    def test_addition_and_subtraction_overflow(self):
        with self.assertRaises(ValueError):
            calc.calculate(1e308, "+", 1e308)
        with self.assertRaises(ValueError):
            calc.calculate(-1e308, "-", 1e308)

    def test_division_overflow(self):
        with self.assertRaises(ValueError):
            calc.calculate(1e308, "/", 1e-308)

    def test_large_finite_results_still_allowed(self):
        self.assertEqual(calc.calculate(1e308, "+", 0), 1e308)

    def test_console_reports_overflow_and_keeps_running(self):
        completed = run_console("*\n1e308\n10\n+\n1\n1\nq\n")
        self.assertEqual(completed.returncode, 0)
        self.assertNotIn("inf", completed.stdout.replace("Please enter a finite number.", ""))
        self.assertIn("Result: 2", completed.stdout)
