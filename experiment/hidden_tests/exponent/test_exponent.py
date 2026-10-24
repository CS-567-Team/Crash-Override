import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import Preservation, calc, run_console  # noqa: E402,F401


class ExponentFeature(unittest.TestCase):

    def test_basic_powers(self):
        self.assertEqual(calc.calculate(2, "**", 10), 1024)
        self.assertEqual(calc.calculate(2, "**", -1), 0.5)
        self.assertEqual(calc.calculate(-2, "**", 3), -8)
        self.assertEqual(calc.calculate(0, "**", 0), 1)

    def test_overflow_raises_value_error(self):
        with self.assertRaises(ValueError):
            calc.calculate(10.0, "**", 400.0)

    def test_complex_result_raises_value_error(self):
        with self.assertRaises(ValueError):
            calc.calculate(-8, "**", 0.5)

    def test_zero_to_negative_power_raises_value_error(self):
        with self.assertRaises(ValueError):
            calc.calculate(0, "**", -1)

    def test_console_supports_exponent_and_keeps_running(self):
        completed = run_console("**\n2\n3\n**\n10\n400\n**\n-8\n0.5\nq\n")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Result: 8", completed.stdout)
        results = [line for line in completed.stdout.splitlines() if "Result: " in line]
        self.assertFalse([line for line in results if line.endswith("j") or "inf" in line])
        self.assertIn("Goodbye!", completed.stdout)
