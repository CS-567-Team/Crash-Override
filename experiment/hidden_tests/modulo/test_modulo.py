import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import Preservation, calc, run_console  # noqa: E402,F401


class ModuloFeature(unittest.TestCase):

    def test_positive_operands(self):
        self.assertEqual(calc.calculate(7, "%", 3), 1)
        self.assertEqual(calc.calculate(5.5, "%", 2), 1.5)

    def test_result_takes_sign_of_divisor(self):
        self.assertEqual(calc.calculate(-7, "%", 3), 2)
        self.assertEqual(calc.calculate(7, "%", -3), -2)

    def test_modulo_by_zero_raises_value_error(self):
        with self.assertRaises(ValueError):
            calc.calculate(5, "%", 0)

    def test_console_supports_modulo_and_keeps_running(self):
        completed = run_console("%\n-7\n3\n%\n1\n0\n+\n1\n1\nq\n")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Result: 2", completed.stdout)
        self.assertIn("Goodbye!", completed.stdout)
