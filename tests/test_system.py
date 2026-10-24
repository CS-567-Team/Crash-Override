"""Tests for the agentic system itself. Run from the repository root:

    python -m unittest discover -s tests -t .
"""

import json
import tempfile
import threading
import unittest
import urllib.request
from collections import Counter
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from src.backend.agents import ProgrammerAgent, ReviewerAgent
from src.backend.experiment.schedule import build_schedule
from src.backend.experiment.task_loader import load_task
from src.backend.models import Architecture
from src.backend.pipelines.workflow import Workflow, load_cached
from src.backend.server import Handler
from src.backend.services.model import DemoProvider

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "experiment" / "tasks" / "demo_task.json"
BASELINE = ROOT / "baseline"


def generate(runtime, architecture, seeded=False):
    workflow = Workflow(DemoProvider(seeded=seeded), architecture)
    return workflow.run(load_task(TASK), baseline=BASELINE, runtime=runtime)


class WorkflowTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_agent_layers_run_in_order(self):
        expected = {
            Architecture.PROGRAMMER_ONLY: ["programmer"],
            Architecture.PROGRAMMER_REVIEWER: ["programmer", "reviewer"],
            Architecture.PLANNER_PROGRAMMER_REVIEWER: ["planner", "programmer", "reviewer"],
        }
        for architecture, roles in expected.items():
            with self.subTest(architecture=architecture.value):
                result = generate(self.runtime, architecture)
                self.assertEqual([a["role"] for a in result.agents], roles)

    def test_correct_implementation_should_be_accepted(self):
        evaluation = generate(self.runtime, Architecture.PROGRAMMER_ONLY).metadata["evaluation"]
        self.assertEqual(evaluation["hidden_pass_rate"], 1.0)
        self.assertEqual(evaluation["correct_decision"], "accept")

    def test_seeded_failure_passes_visible_but_fails_hidden_tests(self):
        evaluation = generate(self.runtime, Architecture.PROGRAMMER_ONLY, seeded=True).metadata["evaluation"]
        self.assertEqual(evaluation["visible_pass_rate"], 1.0)
        self.assertLess(evaluation["hidden_pass_rate"], 1.0)
        self.assertEqual(evaluation["correct_decision"], "reject")

    def test_participant_payload_hides_ground_truth(self):
        result = generate(self.runtime, Architecture.PROGRAMMER_REVIEWER)
        payload = json.dumps(result.participant_payload())
        self.assertNotIn("evaluation", payload)
        self.assertNotIn("hidden", payload)

    def test_cache_round_trip(self):
        result = generate(self.runtime, Architecture.PROGRAMMER_ONLY)
        cached = load_cached(self.runtime / "cache" / f"{result.cache_id}.json")
        self.assertEqual(cached.diff, result.diff)


class AgentOutputTests(unittest.TestCase):

    def test_accepts_fenced_json(self):
        agent = ReviewerAgent(DemoProvider())
        data = agent.parse('```json\n{"summary": "ok", "verdict": "approve", "issues": [], "limitations": []}\n```')
        self.assertEqual(data["verdict"], "approve")

    def test_rejects_missing_fields(self):
        with self.assertRaises(ValueError):
            ProgrammerAgent(DemoProvider()).parse('{"summary": "no files"}')

    def test_rejects_non_json(self):
        with self.assertRaises(ValueError):
            ProgrammerAgent(DemoProvider()).parse("Sure! Here is the code.")


class TaskLoaderTests(unittest.TestCase):

    def test_every_task_loads(self):
        for path in (ROOT / "experiment" / "tasks").glob("*.json"):
            with self.subTest(task=path.name):
                load_task(path)

    def test_rejects_researcher_only_fields(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump({"id": "x", "title": "x", "prompt": "x", "hidden_tests": "secret"}, handle)
        with self.assertRaises(ValueError):
            load_task(handle.name)
        Path(handle.name).unlink()


class ScheduleTests(unittest.TestCase):

    def test_twelve_participants_fully_counterbalanced(self):
        rows = build_schedule(12, list("abcdef"))
        by_participant = Counter(row["participant"] for row in rows)
        self.assertEqual(set(by_participant.values()), {6})
        pairs = Counter((row["task"], row["architecture"], row["display"]) for row in rows)
        self.assertEqual(len(pairs), 36)
        positions = Counter((row["position"], row["architecture"], row["display"]) for row in rows)
        self.assertEqual(set(positions.values()), {2})


class ServerTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.runtime = Path(cls.tmp.name)
        cls.seeded = generate(cls.runtime, Architecture.PROGRAMMER_REVIEWER, seeded=True)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, runtime=cls.runtime))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def request(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_lists_and_serves_trials_without_ground_truth(self):
        status, trials = self.request("/api/trials")
        self.assertEqual(status, 200)
        self.assertEqual(trials[0]["cache_id"], self.seeded.cache_id)
        status, payload = self.request(f"/api/trials/{self.seeded.cache_id}")
        self.assertEqual(status, 200)
        self.assertNotIn("metadata", payload)

    def test_rejects_path_traversal(self):
        status, _ = self.request("/api/trials/..%2F..%2Fsecrets")
        self.assertEqual(status, 404)

    def test_scores_decision_against_hidden_tests(self):
        status, _ = self.request("/api/decisions", {
            "cache_id": self.seeded.cache_id, "participant_id": "p99", "display": "xr",
            "decision": "accept", "decision_seconds": 12.5,
            "responses": {"trust": 6, "confidence": 5},
            "interactions": [{"t": 1.0, "type": "view", "target": "diff"}]})
        self.assertEqual(status, 200)
        record = json.loads((self.runtime / "decisions.jsonl").read_text().splitlines()[-1])
        self.assertEqual(record["expected_decision"], "reject")
        self.assertFalse(record["correct"])
        self.assertEqual(record["decision_seconds"], 12.5)

    def test_rejects_invalid_decision(self):
        status, body = self.request("/api/decisions", {
            "cache_id": self.seeded.cache_id, "participant_id": "p99", "display": "xr", "decision": "maybe"})
        self.assertEqual(status, 400)
        self.assertIn("accept or reject", body["error"])


if __name__ == "__main__":
    unittest.main()
