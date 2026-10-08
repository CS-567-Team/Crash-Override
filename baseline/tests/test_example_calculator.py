"""Arithmetic and console behavior tests for the baseline calculator."""

import subprocess
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app" / "example_calculator.py"
sys.path.insert(0, str(APP.parent))

from example_calculator import calculate


class CalculatorTests(unittest.TestCase):
    def test_operations(self):
        for left, operator, right, expected in [
            (2, "+", 3, 5),
            (-2, "-", 3, -5),
            (1.5, "*", 4, 6),
            (7, "/", 2, 3.5),
        ]:
            with self.subTest(operator=operator):
                self.assertEqual(calculate(left, operator, right), expected)

    def test_invalid_operations(self):
        with self.assertRaisesRegex(ValueError, "divide by zero"):
            calculate(1, "/", 0)
        with self.assertRaisesRegex(ValueError, "Choose"):
            calculate(1, "%", 2)

    def run_console(self, text):
        return subprocess.run(
            [sys.executable, str(APP)], input=text, text=True,
            capture_output=True, check=True, timeout=5,
        ).stdout

    def test_console_retries_and_multiple_operations(self):
        output = self.run_console("bad\n+\nabc\nnan\ninf\n2\n3\n/\n4\n0\n*\n-2\n1.5\nq\n")
        self.assertIn("Choose +, -, *, or /.", output)
        self.assertEqual(output.count("Please enter a finite number."), 3)
        self.assertIn("Result: 5", output)
        self.assertIn("Cannot divide by zero.", output)
        self.assertIn("Result: -3", output)
        self.assertIn("Goodbye!", output)

    def test_console_exits_on_end_of_input(self):
        self.assertIn("Goodbye!", self.run_console("+\n"))


if __name__ == "__main__":
    unittest.main()
