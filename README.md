Agentic AI Project Collaboration

This repository is our central workspace for researching and developing our project for Professor Francisco.

Repository Structure

    Notebooks: Jupyter Notebooks for project communication, brainstorming, and laying out ideas.

    Research: Folder for academic papers and documentation on Agentic AI.

    Images: Folder for images that were found useful.

    Proposal: Drafts and notes for the upcoming project proposal.

    src: Source code for human centric agent models.

    test: Test cases

Immediate Action Items

    Gather research and papers on Agentic AI focused on human centric projects.

    Message Professor Francisco for specific direction on the project scope.

    Schedule meet with Professor.

    Review ideas in the communication notebook to select a final topic before the proposal deadline next week.

Running the Prototype

All commands run from the repository root with Python 3.10+.

    pip install -r requirements.txt

1. Generate and cache agent outputs (one per task x architecture). Each run is scored
   against the task's hidden tests; the scores stay researcher-only.

    python -m src.backend.main generate --provider demo --architecture programmer_only
    python -m src.backend.main generate --provider demo-seeded --architecture planner_programmer_reviewer
    python -m src.backend.main generate --provider openai --task experiment/tasks/modulo.json --architecture programmer_reviewer

   demo / demo-seeded are offline fixtures for demo_task (demo-seeded has a hidden bug
   the reviewer still approves). openai needs OPENAI_API_KEY in .env (copy .env.example).

2. Serve the participant UI and open http://localhost:8000

    python -m src.backend.main serve

   The launcher lists every cached trial with "Open 2D" (tabs) and "Open XR" (3D panels).
   Both views show identical content; decisions, 1-7 trust/confidence ratings, decision
   time, and which section was looked at when are appended to runtime/decisions.jsonl,
   scored against the hidden tests.

   Meta Quest: WebXR needs localhost or HTTPS. With the headset connected over USB:
       adb reverse tcp:8000 tcp:8000
   then open http://localhost:8000 in the Quest browser and press "Enter VR".
   Point a controller and pull the trigger to click; thumbstick scrolls a panel.

3. Counterbalanced trial order for 12 participants (Williams square):

    python -m src.backend.experiment.schedule --participants 12 > experiment/schedule.csv

Researcher tools

    python -m src.backend.main evaluate runtime/cache/response_*.json   # re-score caches
    python -m src.backend.experiment.check_suites                        # validate hidden tests
    python -m unittest discover -s tests -t .                            # system tests
    python -m unittest discover -s baseline/tests                        # baseline app tests

experiment/hidden_tests and experiment/reference_solutions are researcher-only: never show
them to agents or participants.
