"""Run with: python -m src.backend.main --help (from the repository root)."""

import argparse
import json
from pathlib import Path
from dotenv import load_dotenv

from .experiment.session import TrialSession
from .experiment.task_loader import load_task
from .models import Architecture
from .pipelines.workflow import Workflow, load_cached
from .services.model import DemoProvider, OpenAIProvider
from .services.testing import evaluate

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    
    parser = argparse.ArgumentParser(description="CS567 Agent Workflow")
    commands = parser.add_subparsers(dest="command", required=True)
    
    # Creating all the arguments to use
    generate = commands.add_parser("generate", 
                                   help="Generate once and cache an output")
    generate.add_argument("--task", 
                          type=Path,
                          default=PROJECT_ROOT / "experiment/tasks/demo_task.json")
    generate.add_argument("--architecture", 
                          choices=[a.value for a in Architecture],
                          default=Architecture.PLANNER_PROGRAMMER_REVIEWER.value)
    generate.add_argument("--provider", 
                          choices=["demo", "demo-seeded", "openai"], 
                          default="demo")
    generate.add_argument("--model", 
                          help="Override OPENAI_MODEL for all three roles")
    generate.add_argument("--baseline", 
                          type=Path, 
                          default=PROJECT_ROOT / "baseline")
    generate.add_argument("--runtime", type=Path, 
                          default=PROJECT_ROOT / "runtime")
    
    replay = commands.add_parser("replay", 
                                 help="Display cached material")
    replay.add_argument("cache", 
                        type=Path)
    replay.add_argument("--display", 
                        choices=["2d", "xr"], 
                        default="2d")
    replay.add_argument("--participant", 
                        help="enables accept/reject prompt")
    replay.add_argument("--decisions", 
                        type=Path, 
                        default=PROJECT_ROOT / "runtime/decisions.jsonl")
    
    rescore = commands.add_parser("evaluate",
                                  help="Re-run visible and hidden tests on cached outputs")
    rescore.add_argument("caches",
                         type=Path,
                         nargs="+")
    rescore.add_argument("--baseline",
                         type=Path,
                         default=PROJECT_ROOT / "baseline")

    serve = commands.add_parser("serve",
                                help="Serve the 2D and WebXR participant interfaces")
    serve.add_argument("--host",
                       default="127.0.0.1",
                       help="Use 0.0.0.0 to reach it from a headset on the same network")
    serve.add_argument("--port",
                       type=int,
                       default=8000)
    serve.add_argument("--runtime",
                       type=Path,
                       default=PROJECT_ROOT / "runtime")

    args = parser.parse_args()
    
    try:
        if args.command == "generate":
            
            if args.provider == "openai":
                
                load_dotenv(PROJECT_ROOT / ".env")
                provider = OpenAIProvider(args.model)
                
            else:
                
                if args.model:
                    raise ValueError("--model only applies to AI model providers")
                
                provider = DemoProvider(seeded=args.provider == "demo-seeded")
                
            result = Workflow(provider, Architecture(args.architecture)).run(load_task(args.task), baseline=args.baseline, runtime=args.runtime)
            print(json.dumps(result.participant_payload(), indent=2))
            print(f"\nCached at: {args.runtime / 'cache' / (result.cache_id + '.json')}")
            
        elif args.command == "evaluate":

            for path in args.caches:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["metadata"]["evaluation"] = evaluate(data["task"]["id"], data["files"],
                                                          baseline=args.baseline)
                path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
                summary = {k: data["metadata"]["evaluation"][k] for k in
                           ("hidden_pass_rate", "regressions", "correct_decision")}
                print(f"{path.name}: {json.dumps(summary)}")

        elif args.command == "serve":

            from .server import serve as run_server
            run_server(args.host, args.port, args.runtime)

        else:
            
            result = load_cached(args.cache)
            session = TrialSession(args.participant or "preview", args.display, result)
            print(json.dumps(session.present(), indent=2))
            
            if args.participant:
                
                decision = input("Decision (accept/reject): ").strip().lower()
                session.record_decision(decision, args.decisions)
                print(f"Decision recorded in {args.decisions}")
                
    except (ValueError, RuntimeError, OSError, ImportError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()