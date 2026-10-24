"""Run as a script: python test_runner.py <test_dir>. Prints {test_id: status} as JSON.

Executed in a subprocess so agent-written code cannot hang or crash the backend."""

import json
import sys
import unittest


class RecordingResult(unittest.TestResult):

    def __init__(self):
        super().__init__()
        self.statuses = {}

    def addSuccess(self, test):
        self.statuses.setdefault(test.id(), "passed")

    def addFailure(self, test, err):
        self.statuses[test.id()] = "failed"

    def addError(self, test, err):
        self.statuses[test.id()] = "error"

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.statuses[test.id()] = "failed"


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(sys.argv[1], top_level_dir=sys.argv[1])
    result = RecordingResult()
    suite.run(result)
    print(json.dumps(result.statuses, sort_keys=True))
