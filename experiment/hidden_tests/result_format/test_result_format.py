import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import Preservation, calc, run_console  # noqa: E402,F401


def results(text):
    return [line.split("Result: ", 1)[1] for line in run_console(text + "q\n").stdout.splitlines()
            if "Result: " in line]


class ResultFormatFeature(unittest.TestCase):

    def test_twelve_significant_digits(self):
        self.assertEqual(results("/\n2\n3\n+\n1234567\n1\n"), ["0.666666666667", "1234568"])

    def test_floating_point_noise_hidden(self):
        self.assertEqual(results("+\n0.1\n0.2\n/\n7\n2\n"), ["0.3", "3.5"])

    def test_negative_zero_displayed_as_zero(self):
        self.assertEqual(results("*\n-1\n0\n"), ["0"])

    def test_no_scientific_notation_below_1e15(self):
        self.assertEqual(results("*\n50000000\n10000000\n"), ["500000000000000"])
