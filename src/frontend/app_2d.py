"""2D condition of the study and the participant's session hub.

Run from the repository root (with the VR server running for the headset trials):
    streamlit run src/frontend/app_2d.py

Walks a participant through their six counterbalanced trials. 2D trials happen here;
for VR trials it asks them to put on the headset and waits. Content comes from the same
cached agent outputs and section builder as the VR view, and decisions go to the same log.
"""

import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.backend.experiment.plan import next_trial, session_plan  # noqa: E402
from src.backend.experiment.presentation import build_sections, load_context  # noqa: E402
from src.backend.experiment.session import TrialSession  # noqa: E402
from src.backend.pipelines.workflow import load_cached  # noqa: E402

RUNTIME = ROOT / "runtime"
DECISIONS = RUNTIME / "decisions.jsonl"

st.set_page_config(page_title="Code Review Study", layout="wide")
context = load_context()


def text_to_markdown(text: str) -> str:
    """Section text marks headings in capitals; show them as headings here."""
    lines = []
    for line in text.split("\n"):
        if line.isupper() and len(line) > 3:
            lines.append(f"\n#### {line.title()}\n")
        elif line.startswith("  "):
            lines.append(f"`{line.strip()}`  ")
        else:
            # Operators like * and ** would otherwise turn into italics/bold.
            lines.append(line.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_") + "  ")
    return "\n".join(lines)


def show_section(section: dict) -> None:
    if section["kind"] == "diff":
        st.markdown(f"**Programmer's summary:** {section['summary']}")
        st.caption("Lines starting with + were added; lines starting with - were removed.")
        st.code(section["text"], language="diff")
    elif section["kind"] == "code":
        st.code(section["text"], language="python", line_numbers=True)
    else:
        st.markdown(text_to_markdown(section["text"]))


def log_event(key: str, kind: str, target: str) -> None:
    trial = st.session_state[key]
    trial["events"].append({"t": round(time.time() - trial["start"], 3), "type": kind, "target": target})


def run_trial(participant: str, trial: dict, preview: bool = False) -> None:
    result = load_cached(RUNTIME / "cache" / f"{trial['cache_id']}.json")
    sections = build_sections(result.participant_payload(), context)
    key = f"trial:{participant}:{result.cache_id}"
    if key not in st.session_state:
        st.session_state[key] = {"start": time.time(), "events": [], "viewed": None}

    heading = "Preview (not recorded)" if preview else f"Trial {trial['position']} of 6"
    st.title(f"{heading}: {result.task['title']}")
    st.write("Read each section from left to right, then make your decision at the bottom of the page.")

    titles = [section["title"] for section in sections]
    choice = st.radio("Section", titles, horizontal=True, key=f"{key}:section", label_visibility="collapsed")
    section = sections[titles.index(choice)]
    if st.session_state[key]["viewed"] != section["id"]:
        st.session_state[key]["viewed"] = section["id"]
        log_event(key, "view", section["id"])

    with st.container(border=True):
        show_section(section)

    st.markdown("---")
    st.subheader("Your decision")
    st.info(context["decision_help"])
    with st.form(key=f"{key}:form"):
        responses = {}
        for question in context["questions"]:
            responses[question["id"]] = st.radio(
                f"{question['text']} (1 = {question['low']}, 7 = {question['high']})",
                list(range(1, 8)), index=None, horizontal=True, key=f"{key}:{question['id']}")
        decision = st.radio("Decision", ["Accept change", "Reject change"], index=None,
                            horizontal=True, key=f"{key}:decision")
        submitted = st.form_submit_button("Submit decision", type="primary", disabled=preview)

    if preview:
        st.caption("Preview mode: decisions are not recorded.")
        return

    if submitted:
        if decision is None or any(value is None for value in responses.values()):
            st.error("Please answer both questions and choose Accept or Reject.")
            return
        log_event(key, "choose", decision.split()[0].lower())
        session = TrialSession(participant, "2d", result)
        session.present()
        session.record_decision(decision.split()[0].lower(), DECISIONS,
                                decision_seconds=time.time() - st.session_state[key]["start"],
                                responses=responses, interactions=st.session_state[key]["events"])
        st.rerun()


# ---------------------------------------------------------------- sidebar

with st.sidebar:
    st.header("Session")
    participant = st.text_input("Participant ID", placeholder="p01").strip()
    plan = []
    if participant:
        try:
            plan = session_plan(participant, RUNTIME)
        except ValueError as error:
            st.error(str(error))
        for trial in plan:
            mark = "✅" if trial["done"] else "⬜"
            where = "VR headset" if trial["display"] == "xr" else "This screen"
            st.write(f"{mark} Trial {trial['position']}: {where}")

    with st.expander("Researcher preview"):
        caches = sorted((RUNTIME / "cache").glob("response_*.json"), key=lambda p: int(p.stem.split("_")[1]))
        labels = {}
        for path in caches:
            result = load_cached(path)
            labels[f"{result.cache_id}: {result.task['id']} / {result.architecture}"] = result.cache_id
        preview = st.selectbox("Show a trial without recording", ["(off)", *labels], key="preview")

# ---------------------------------------------------------------- main

if preview != "(off)":
    run_trial("preview", {"cache_id": labels[preview], "position": 0}, preview=True)
elif not participant:
    st.title("Code Review Study")
    st.write("Enter the participant ID in the sidebar to begin.")
elif plan:
    upcoming = next_trial(plan)
    intro_key = f"intro_seen:{participant}"

    if not any(trial["done"] for trial in plan) and not st.session_state.get(intro_key):
        st.title("Welcome")
        st.markdown(context["study_intro"])
        with st.expander("About the program you will be reviewing", expanded=True):
            st.markdown(text_to_markdown(context["app_description"]))
        if st.button("Begin", type="primary"):
            st.session_state[intro_key] = True
            st.rerun()
    elif upcoming is None:
        st.title("All trials complete")
        st.success("Thank you for taking part! Please let the researcher know you are finished.")
    elif upcoming["cache_id"] is None:
        st.error(f"Trial {upcoming['position']} has no generated agent output yet "
                 f"({upcoming['task']} / {upcoming['architecture']}). Run: "
                 "python -m src.backend.main generate --all")
    elif upcoming["display"] == "xr":
        st.title(f"Trial {upcoming['position']} of 6 is in VR")
        st.markdown("Please put on the headset. The trial will be waiting for you there.\n\n"
                    "When you have submitted your decision in VR and taken the headset off, click Continue.")
        st.caption("Researcher: the VR server must be running (python -m src.backend.main serve) and the headset "
                   f"should be on http://localhost:8000 with participant ID {participant}.")
        if st.button("Continue", type="primary"):
            st.rerun()
    else:
        run_trial(participant, upcoming)
