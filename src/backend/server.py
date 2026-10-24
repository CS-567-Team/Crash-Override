"""Local web server for the 2D and WebXR participant interfaces (stdlib only).

    python -m src.backend.main serve            # then open http://localhost:8000

The headset fetches its sections from /api/trials/<cache_id>; the Streamlit 2D app builds
the same sections in-process, so the only thing that differs is presentation. Hidden-test results stay on
the server and are only used to score decisions."""

import json
import re
import ssl
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .experiment.plan import next_trial, session_plan
from .experiment.presentation import build_sections, load_context
from .experiment.session import TrialSession
from .services.certs import ensure_certificate, lan_address
from .pipelines.workflow import load_cached

WEB_ROOT = Path(__file__).resolve().parents[1] / "frontend" / "web"
CACHE_ID = re.compile(r"^response_\d+$")
MAX_BODY = 1_000_000


class Handler(SimpleHTTPRequestHandler):

    runtime: Path

    def __init__(self, *args, runtime: Path, **kwargs):
        self.runtime = runtime
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, format, *args):
        pass

    def end_headers(self):
        # Always serve fresh files while iterating on the prototype.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def cache_path(self, cache_id: str) -> Path:
        path = self.runtime / "cache" / f"{cache_id}.json"
        if not CACHE_ID.match(cache_id) or not path.is_file():
            raise FileNotFoundError(cache_id)
        return path

    def do_GET(self):
        route = urlparse(self.path).path

        if route == "/api/trials":
            trials = []
            for path in sorted((self.runtime / "cache").glob("response_*.json")):
                result = load_cached(path)
                trials.append({"cache_id": result.cache_id, "task": result.task["title"],
                               "architecture": result.architecture})
            return self.send_json(trials)

        if route.startswith("/api/trials/"):
            try:
                result = load_cached(self.cache_path(route.removeprefix("/api/trials/")))
            except FileNotFoundError:
                return self.send_json({"error": "Unknown trial"}, HTTPStatus.NOT_FOUND)
            payload = result.participant_payload()
            context = load_context()
            return self.send_json({"cache_id": result.cache_id, "task": payload["task"],
                                   "sections": build_sections(payload, context),
                                   "decision_help": context["decision_help"],
                                   "questions": context["questions"]})

        if route.startswith("/api/session/"):
            try:
                plan = session_plan(unquote(route.removeprefix("/api/session/")), self.runtime)
            except ValueError as error:
                return self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return self.send_json({"trials": plan, "next": next_trial(plan)})

        if route.startswith("/api/"):
            return self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

        return super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != "/api/decisions":
            return self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_BODY:
                raise ValueError("Request too large")
            body = json.loads(self.rfile.read(length))
            result = load_cached(self.cache_path(str(body.get("cache_id", ""))))
            session = TrialSession(str(body.get("participant_id", "")),
                                   str(body.get("display", "")), result)
            session.present()
            seconds = body.get("decision_seconds")
            event = session.record_decision(
                str(body.get("decision", "")), self.runtime / "decisions.jsonl",
                decision_seconds=float(seconds) if seconds is not None else None,
                responses=body.get("responses") if isinstance(body.get("responses"), dict) else {},
                interactions=body.get("interactions") if isinstance(body.get("interactions"), list) else [])
        except FileNotFoundError:
            return self.send_json({"error": "Unknown trial"}, HTTPStatus.NOT_FOUND)
        except (ValueError, TypeError) as error:
            return self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

        # Participants only learn that the decision was saved, not whether it was correct.
        return self.send_json({"trial_id": event["trial_id"]})


def serve(host: str, port: int, runtime: Path, https: bool = False) -> None:
    runtime = Path(runtime).resolve()
    server = ThreadingHTTPServer((host, port), partial(Handler, runtime=runtime))

    if https:
        address = lan_address()
        cert, key = ensure_certificate(runtime / "certs", address)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        print(f"Serving over HTTPS. In the Oculus browser open:  https://{address}:{port}")
        print("The first time, the headset warns the connection is not private: "
              "choose Advanced, then Proceed. This is expected for your own laptop.")
    else:
        print(f"Serving participant VR page at http://localhost:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
