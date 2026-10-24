import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import Preservation, calc, run_console  # noqa: E402,F401


class ReuseAnswerFeature(unittest.TestCase):

    def test_ans_as_first_number(self):
        completed = run_console("+\n2\n3\n*\nans\n2\nq\n")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Result: 10", completed.stdout)

    def test_ans_as_second_number(self):
        completed = run_console("+\n4\n4\n-\n1\nans\nq\n")
        self.assertIn("Result: -7", completed.stdout)

    def test_ans_unavailable_before_first_result(self):
        completed = run_console("+\nans\n1\n2\nq\n")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Result: 3", completed.stdout)
        self.assertIn("Goodbye!", completed.stdout)

    def test_failed_calculation_keeps_previous_answer(self):
        completed = run_console("+\n2\n3\n/\n1\n0\n+\nans\n1\nq\n")
        self.assertIn("Result: 6", completed.stdout)
