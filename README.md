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

1. Generate the agent outputs for every task and workflow (18 trials). This works offline
   with the demo fixtures; each trial is scored against hidden tests (researcher-only).

    python -m src.backend.main generate --all --provider demo

   With OPENAI_API_KEY in .env (copy .env.example), use --provider openai instead.

2. Start both apps (two terminals):

    python -m src.backend.main serve          # VR server on http://localhost:8000
    streamlit run src/frontend/app_2d.py      # 2D app and session hub

3. Run a participant session. Enter the participant ID (p01 to p12) in the Streamlit
   sidebar. It walks them through their 6 counterbalanced trials, covering all three
   workflows on both displays. When a trial is in VR, Streamlit says so and waits.

   In the headset, open http://localhost:8000, enter the same ID, and press Enter VR.
   VR trials run back to back until the next one is on the laptop.

   VR controls: trigger = click, grip = grab and move a panel (thumbstick pushes it away
   or pulls it closer while held), left thumbstick = walk, right thumbstick = scroll the
   panel you point at (up/down) or turn (left/right). "Reset layout" puts everything back.

   Meta Quest over USB (WebXR needs localhost or HTTPS):
       adb reverse tcp:8000 tcp:8000

   Every decision (with trust/confidence ratings, decision time, which sections were
   viewed when, and whether it was correct) is appended to runtime/decisions.jsonl.
   To rerun a participant, use a new ID or remove their lines from that file.

Researcher tools

    Streamlit sidebar > Researcher preview: view any trial without recording
    python -m src.backend.experiment.schedule --participants 12   # full trial order
    python -m src.backend.main evaluate runtime/cache/response_*.json   # re-score caches
    python -m src.backend.experiment.check_suites                 # validate hidden tests
    python -m unittest discover -s tests -t .                     # system tests

Participant-facing text (study intro, program description, questions) is in
experiment/participant_context.json. experiment/hidden_tests, reference_solutions and
demo_fixtures are researcher-only: never show them to agents or participants.
