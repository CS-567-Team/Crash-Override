"""Run with: python -m src.backend.main --help (from the repository root)."""

import argparse
import json
from pathlib import Path
from dotenv import load_dotenv

from .experiment.schedule import DEFAULT_TASKS
from .experiment.session import TrialSession
from .experiment.task_loader import load_task
from .models import Architecture
from .pipelines.workflow import Workflow, load_cached
from .services.model import OpenAIProvider
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
    generate.add_argument("--all",
                          action="store_true",
                          help="Generate every study task with every architecture")
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
                       default=None,
                       help="Defaults to 127.0.0.1, or 0.0.0.0 with --https")
    serve.add_argument("--https",
                       action="store_true",
                       help="Serve over HTTPS on the local network so the Oculus can connect over Wi-Fi")
    serve.add_argument("--port",
                       type=int,
                       default=8000)
    serve.add_argument("--runtime",
                       type=Path,
                       default=PROJECT_ROOT / "runtime")

    analyze = commands.add_parser("analyze",
                                  help="Export decision metrics to CSV for analysis")
    analyze.add_argument("--runtime",
                         type=Path,
                         default=PROJECT_ROOT / "runtime")
    analyze.add_argument("--out",
                         type=Path,
                         help="Output folder (default: <runtime>/analysis)")

    export = commands.add_parser("export-participant",
                                 help="Build the participant edition (no hidden tests or scores) for remote sessions")
    export.add_argument("--runtime",
                        type=Path,
                        default=PROJECT_ROOT / "runtime")
    export.add_argument("--out",
                        type=Path,
                        default=PROJECT_ROOT / "dist")
    export.add_argument("--no-zip",
                        action="store_true")

    merge = commands.add_parser("merge",
                                help="Add a remote participant's decisions.jsonl to runtime/decisions.jsonl and score it")
    merge.add_argument("files",
                       type=Path,
                       nargs="+")
    merge.add_argument("--runtime",
                       type=Path,
                       default=PROJECT_ROOT / "runtime")
    merge.add_argument("--dry-run",
                       action="store_true",
                       help="Check and report without writing")

    args = parser.parse_args()
    
    try:
        if args.command == "generate":
            
            if args.provider == "openai":
                
                load_dotenv(PROJECT_ROOT / ".env")
                provider = OpenAIProvider(args.model)
                
            else:
                
                if args.model:
                    raise ValueError("--model only applies to AI model providers")
                
                from .services.demo_provider import DemoProvider
                provider = DemoProvider(seeded=args.provider == "demo-seeded")
                
            if args.all:
                jobs = [(PROJECT_ROOT / "experiment/tasks" / f"{task}.json", architecture)
                        for task in DEFAULT_TASKS for architecture in Architecture]
            else:
                jobs = [(args.task, Architecture(args.architecture))]

            for task_path, architecture in jobs:
                result = Workflow(provider, architecture).run(load_task(task_path), baseline=args.baseline, runtime=args.runtime)
                evaluation = result.metadata["evaluation"]
                print(f"{result.cache_id}: {result.task['id']} / {result.architecture} -> "
                      f"hidden tests {evaluation['hidden_pass_rate']:.0%}, should {evaluation['correct_decision']}")
            
        elif args.command == "evaluate":

            for path in args.caches:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["metadata"]["evaluation"] = evaluate(data["task"]["id"], data["files"],
                                                          baseline=args.baseline)
                path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
                summary = {k: data["metadata"]["evaluation"][k] for k in
                           ("hidden_pass_rate", "regressions", "correct_decision")}
                print(f"{path.name}: {json.dumps(summary)}")

        elif args.command == "analyze":

            from .experiment.metrics import analyze as export_metrics, print_summary
            out = args.out or args.runtime / "analysis"
            rows, summary = export_metrics(args.runtime, out)
            print(f"{len(rows)} decisions -> {out / 'trials.csv'} and {out / 'summary.csv'}\n")
            print_summary(summary)

        elif args.command == "export-participant":

            from .experiment.participant_export import export
            manifest = export(args.runtime, args.out, make_zip=not args.no_zip)
            print(f"Participant edition with {len(manifest['trials'])} cached trials:")
            print(f"  folder: {manifest['folder']}")
            if "zip" in manifest:
                print(f"  zip:    {manifest['zip']}   <- send this to participants")

        elif args.command == "merge":

            from .experiment.merge import merge as merge_decisions
            report = merge_decisions(args.files, args.runtime, dry_run=args.dry_run)
            verb = "Would add" if args.dry_run else "Added"
            print(f"{verb} {report['added']} decisions to {report['log']} "
                  f"(skipped {report['skipped']} already there).")
            for participant, stats in sorted(report["participants"].items()):
                print(f"  {participant}: {stats['trials']} trials, {stats['correct']} correct")

        elif args.command == "serve":

            from .server import serve as run_server
            host = args.host or ("0.0.0.0" if args.https else "127.0.0.1")
            run_server(host, args.port, args.runtime, https=args.https)

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