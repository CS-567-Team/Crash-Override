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

2. Start both apps on the laptop (two terminals):

    python -m src.backend.main serve --https      # VR page for the Oculus (prints its address)
    streamlit run src/frontend/app_2d.py           # laptop app: http://localhost:8501

3. Run a participant (IDs p01 to p12). Each participant does 3 trials on the laptop and
   3 in the headset, switching device once. Odd IDs start on the laptop, even IDs start
   in VR. Across 12 participants every workflow, display and task is balanced, and each
   participant gets one seeded-bug trial in each part.

   Before the participant arrives, set up the headset (see Oculus setup) on the VR page
   with their ID. Then enter the same ID in the Streamlit sidebar. Both screens move on
   by themselves: the headset says when it is the participant's turn in VR, and the
   laptop continues once the VR part is done.

   Every decision (with trust/confidence ratings, decision time, which sections were
   viewed when, and whether it was correct) is appended to runtime/decisions.jsonl.
   To rerun a participant, use a new ID or remove their lines from that file.

Oculus setup (Quest 1/2/3/Pro)

VR in a browser only works on https:// pages, so the laptop serves the VR page over
HTTPS on your Wi-Fi. No cable or developer mode needed.

1. Put the laptop and the Oculus on the same Wi-Fi network. Campus Wi-Fi often blocks
   devices from talking to each other; if the headset cannot load the page, use a phone
   hotspot for both.
2. On the laptop run:  python -m src.backend.main serve --https
   It prints an address like https://192.168.1.23:8000. On Windows, if a firewall
   prompt appears, allow Python on private networks.
3. In the headset, open the Browser app (from the app library) and type that address.
4. The first time, it warns "Your connection is not private". Choose Advanced, then
   Proceed. This is expected: the certificate was made by your own laptop.
5. Enter the participant ID and press Start VR session. The headset waits until it is
   the participant's turn, then shows the trial.
6. The participant presses the big blue Enter VR button.

Controls in VR: trigger = click. Grip (hold) = grab and move a panel; while holding,
the thumbstick pushes it away or pulls it closer. Left thumbstick = walk. Right thumbstick
= scroll the panel you point at (up/down) or turn (left/right). "Reset layout" puts
everything back.

Alternative with a USB cable (needs developer mode and adb): run the server without
--https, then  adb reverse tcp:8000 tcp:8000  and open http://localhost:8000.

Researcher tools

    Streamlit sidebar > Researcher preview: view any trial without recording
    http://localhost:8000/xr.html?participant=p02 on the laptop: VR preview (drag, WASD)
    python -m src.backend.experiment.schedule --participants 12   # full trial order
    python -m src.backend.main evaluate runtime/cache/response_*.json   # re-score caches
    python -m src.backend.experiment.check_suites                 # validate hidden tests
    python -m unittest discover -s tests -t .                     # system tests

Participant-facing text (study intro, program description, questions) is in
experiment/participant_context.json. experiment/hidden_tests, reference_solutions and
demo_fixtures are researcher-only: never show them to agents or participants.
