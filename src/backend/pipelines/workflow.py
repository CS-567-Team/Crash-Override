import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from ..agents import PlannerAgent, ProgrammerAgent, ReviewerAgent
from ..models import Architecture, Task, WorkflowResult
from ..services.model import ModelProvider
from ..services.repo import apply_replacements, copy_baseline, read_app_files

PIPELINE_VERSION = 1

def load_cached(path: str | Path) -> WorkflowResult:
    return WorkflowResult(**json.loads(Path(path).read_text(encoding="utf-8")))

def next_response_id(runs_dir: Path) -> str:
    
    number = 1
    
    while (runs_dir / f"response_{number:02d}").exists():
        number += 1
        
    return f"response_{number:02d}"


class Workflow:
    
    def __init__(self, provider: ModelProvider, architecture: Architecture):
        self.provider = provider
        self.architecture = Architecture(architecture)

    def run(self, task: Task, *, baseline: Path, runtime: Path) -> WorkflowResult:
        
        baseline, runtime = Path(baseline).resolve(), Path(runtime).resolve()
        
        original_files = read_app_files(baseline)
        
        identity = {
            "version": PIPELINE_VERSION, "task": asdict(task), "files": original_files,
            "architecture": self.architecture.value, "provider": self.provider.cache_identity,
            "prompts": [PlannerAgent.system_prompt, ProgrammerAgent.system_prompt,
                        ReviewerAgent.system_prompt],
        }
        
        cache_id = next_response_id(runtime / "runs")
        cache_path = runtime / "cache" / f"{cache_id}.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        run_dir = runtime / "runs" / cache_id
        run_dir.mkdir(parents=True)
        
        workspace = run_dir / "repo"
        
        copy_baseline(baseline, workspace)
        outputs = []
        started = perf_counter()

        def log(event: dict) -> None:
            with (run_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(),
                                         **event}) + "\n")

        def invoke(agent, files, **extra):
            output = agent.run(task, files, **extra)
            outputs.append(output.to_dict())
            log({"event": "agent_completed", "output": output.to_dict()})
            return output.data

        log({"event": "workflow_started", "cache_id": cache_id, "identity": identity})
        
        try:
            
            plan = None
            
            if self.architecture == Architecture.PLANNER_PROGRAMMER_REVIEWER:
                plan = invoke(PlannerAgent(self.provider), original_files)
                
            extras = {"plan": plan} if plan is not None else {}
            implementation = invoke(ProgrammerAgent(self.provider), original_files, **extras)
            diff = apply_replacements(workspace, original_files, implementation["files"])
            changed_files = {**original_files, **implementation["files"]}
            
            if self.architecture != Architecture.PROGRAMMER_ONLY:
                invoke(ReviewerAgent(self.provider), changed_files,
                       original_files=original_files, diff=diff)
                
            result = WorkflowResult(
                
                cache_id=cache_id, task=asdict(task), architecture=self.architecture.value,
                agents=outputs, diff=diff, files=changed_files,
                metadata={"pipeline_version": PIPELINE_VERSION,
                          "provider": self.provider.cache_identity,
                          "created_at": datetime.now(timezone.utc).isoformat(),
                          "workspace": str(workspace), "model_calls": len(outputs),
                          "elapsed_seconds": perf_counter() - started,
                          "input_tokens": sum(a["response"]["input_tokens"] for a in outputs),
                          "output_tokens": sum(a["response"]["output_tokens"] for a in outputs)},
            )
            
            cache_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
            
            log({"event": "workflow_completed", "cache_id": cache_id})
            return result
        except Exception as error:
            log({"event": "workflow_failed", "error_type": type(error).__name__})
            raise
