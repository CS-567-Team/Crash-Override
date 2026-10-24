"""Tests for the agentic system itself. Run from the repository root:

    python -m unittest discover -s tests -t .
"""

import json
import ssl
import tempfile
import threading
import unittest
import urllib.request
from collections import Counter
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from src.backend.agents import ProgrammerAgent, ReviewerAgent
from src.backend.experiment.plan import next_trial, session_plan
from src.backend.experiment.presentation import build_sections
from src.backend.experiment.schedule import DEFAULT_TASKS, SEEDED_TASKS, build_schedule
from src.backend.experiment.task_loader import load_task
from src.backend.models import Architecture
from src.backend.pipelines.workflow import Workflow, load_cached
from src.backend.server import Handler
from src.backend.services.certs import ensure_certificate
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

    def test_one_device_switch_and_one_seeded_task_per_block(self):
        rows = build_schedule(12, DEFAULT_TASKS)
        for participant in {row["participant"] for row in rows}:
            mine = [row for row in rows if row["participant"] == participant]
            displays = [row["display"] for row in mine]
            self.assertEqual(sum(a != b for a, b in zip(displays, displays[1:])), 1)
            seeded = Counter(row["display"] for row in mine if row["task"] in SEEDED_TASKS)
            self.assertEqual(seeded, {"2d": 1, "xr": 1})
        self.assertEqual(Counter(row["display"] for row in rows if row["position"] == 1), {"2d": 6, "xr": 6})


class DemoFixtureTests(unittest.TestCase):

    def test_every_study_task_has_offline_outputs_with_expected_ground_truth(self):
        seeded = {"modulo", "overflow_guard"}
        with tempfile.TemporaryDirectory() as tmp:
            for task_id in DEFAULT_TASKS:
                with self.subTest(task=task_id):
                    task = load_task(ROOT / "experiment" / "tasks" / f"{task_id}.json")
                    result = Workflow(DemoProvider(), Architecture.PLANNER_PROGRAMMER_REVIEWER).run(
                        task, baseline=BASELINE, runtime=Path(tmp))
                    evaluation = result.metadata["evaluation"]
                    self.assertEqual(evaluation["visible_pass_rate"], 1.0)
                    self.assertEqual(evaluation["correct_decision"],
                                     "reject" if task_id in seeded else "accept")


class PresentationTests(unittest.TestCase):

    def test_sections_follow_workflow_and_include_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            only = generate(Path(tmp), Architecture.PROGRAMMER_ONLY).participant_payload()
            full = generate(Path(tmp), Architecture.PLANNER_PROGRAMMER_REVIEWER).participant_payload()
        self.assertEqual([s["id"] for s in build_sections(only)], ["task", "before", "after"])
        sections = build_sections(full)
        self.assertEqual([s["id"] for s in sections], ["task", "plan", "before", "after", "review"])
        self.assertIn("console calculator", sections[0]["text"])
        self.assertIn("Planner:", sections[0]["text"])

    def test_code_is_shown_as_full_files_with_changed_lines_highlighted(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = generate(Path(tmp), Architecture.PROGRAMMER_ONLY).participant_payload()
        sections = {s["id"]: s for s in build_sections(payload)}
        before, after = sections["before"]["files"][0], sections["after"]["files"][0]
        self.assertEqual(before["source"], payload["original_files"]["app/example_calculator.py"])
        self.assertIn('if operator == "//":', after["source"])
        self.assertNotIn("@@", after["source"])
        lines = after["source"].splitlines()
        self.assertIn('    if operator == "//":', [lines[n - 1] for n in after["highlight"]])
        self.assertNotIn("def calculate(left: float, operator: str, right: float) -> float:",
                         [lines[n - 1] for n in after["highlight"]])
        self.assertTrue(before["highlight"])


class SessionPlanTests(unittest.TestCase):

    def test_plan_covers_every_condition_and_tracks_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            for architecture in Architecture:
                generate(runtime, architecture)
            plan = session_plan("p01", runtime)
            self.assertEqual(len(plan), 6)
            self.assertEqual({(t["architecture"], t["display"]) for t in plan},
                             {(a.value, d) for a in Architecture for d in ("2d", "xr")})
            demo = [t for t in plan if t["task"] == "demo_task"][0]
            self.assertIsNotNone(demo["cache_id"])
            (runtime / "decisions.jsonl").write_text(json.dumps(
                {"participant_id": "p01", "cache_id": demo["cache_id"]}) + "\n")
            self.assertTrue([t for t in session_plan("p01", runtime) if t["task"] == "demo_task"][0]["done"])
            self.assertFalse(any(t["done"] for t in session_plan("p02", runtime)))

    def test_participant_rows_differ(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = [(t["architecture"], t["display"]) for t in session_plan("p01", Path(tmp))]
            second = [(t["architecture"], t["display"]) for t in session_plan("p02", Path(tmp))]
        self.assertNotEqual(first, second)
        self.assertIsNotNone(next_trial(session_plan("p01", Path(tmp))))

    def test_rejects_id_without_number(self):
        with self.assertRaises(ValueError):
            session_plan("amber", Path("."))


class CertificateTests(unittest.TestCase):

    def test_certificate_is_reused_for_the_same_address(self):
        with tempfile.TemporaryDirectory() as tmp:
            cert, key = ensure_certificate(Path(tmp), "192.168.1.20")
            first = cert.read_bytes()
            self.assertEqual(ensure_certificate(Path(tmp), "192.168.1.20")[0].read_bytes(), first)
            self.assertNotEqual(ensure_certificate(Path(tmp), "192.168.1.21")[0].read_bytes(), first)
            ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(cert, key)


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
        self.assertNotIn("evaluation", json.dumps(payload))
        self.assertEqual([s["id"] for s in payload["sections"]], ["task", "before", "after", "review"])
        self.assertEqual(len(payload["questions"]), 2)

    def test_session_endpoint(self):
        status, session = self.request("/api/session/p05")
        self.assertEqual(status, 200)
        self.assertEqual(len(session["trials"]), 6)
        self.assertEqual(session["next"]["position"], 1)
        status, _ = self.request("/api/session/nobody")
        self.assertEqual(status, 400)

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

    def test_records_headset_diagnostics(self):
        status, _ = self.request("/api/debug", {"event": "page_loaded", "immersiveVr": True})
        self.assertEqual(status, 200)
        record = json.loads((self.runtime / "xr_debug.jsonl").read_text().splitlines()[-1])
        self.assertEqual(record["event"], "page_loaded")

    def test_rejects_invalid_decision(self):
        status, body = self.request("/api/decisions", {
            "cache_id": self.seeded.cache_id, "participant_id": "p99", "display": "xr", "decision": "maybe"})
        self.assertEqual(status, 400)
        self.assertIn("accept or reject", body["error"])


if __name__ == "__main__":
    unittest.main()
