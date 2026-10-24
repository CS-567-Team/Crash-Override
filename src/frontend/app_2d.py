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
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

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


# Changed lines are tinted red-ish in the old code and green-ish in the new code.
HIGHLIGHT = {"before": "#fde2e1", "after": "#dcf3e2"}


def show_code(file: dict, side: str) -> None:
    """Syntax-highlighted code, one row per line, with changed lines tinted across the full width."""
    formatter = HtmlFormatter(nowrap=True, cssclass="code")
    lines = highlight(file["source"], PythonLexer(), formatter).rstrip("\n").split("\n")
    changed = set(file["highlight"])
    rows = "".join(
        f'<div class="row{" changed" if number in changed else ""}"><span class="num">{number}</span>'
        f'<span class="src">{line or " "}</span></div>'
        for number, line in enumerate(lines, 1))
    st.caption(file["name"])
    st.html(f"""<style>{formatter.get_style_defs(".code")}
        .code {{ font: 14px/1.55 ui-monospace, Menlo, Consolas, monospace; background: #f8f9fb;
                 border: 1px solid #e3e6eb; border-radius: 6px; padding: 10px 0; overflow-x: auto; }}
        .code .row {{ display: flex; white-space: pre; min-width: max-content; }}
        .code .row.changed {{ background: {HIGHLIGHT[side]}; }}
        .code .num {{ width: 3.5em; flex: none; padding-right: 1em; text-align: right; color: #9aa1ac; user-select: none; }}
        .code .src {{ padding-right: 16px; }}
        </style><div class="code">{rows}</div>""")


def show_section(section: dict) -> None:
    if section["kind"] == "code":
        st.markdown(text_to_markdown(section["note"]))
        for file in section["files"]:
            show_code(file, section["side"])
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


@st.fragment(run_every=3)
def wait_for_vr(participant: str) -> None:
    """Re-check every few seconds and move on once the VR trials are done."""
    upcoming = next_trial(session_plan(participant, RUNTIME))
    if upcoming is None or upcoming["display"] != "xr":
        st.rerun(scope="app")
    st.caption("This page moves on by itself when the VR part is finished.")


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
        laptop_done = any(trial["done"] for trial in plan if trial["display"] == "2d")
        remaining = sum(not trial["done"] for trial in plan if trial["display"] == "xr")
        if laptop_done:
            st.title("Laptop part complete")
            st.success("Nice work. The rest of the study is in the VR headset.")
        else:
            st.title("Part 1: VR headset")
        st.markdown(f"Please put on the headset and press the big blue **Enter VR** button in front of you. "
                    f"Your next {remaining} trials are in VR.\n\n"
                    "When the headset tells you the VR part is complete, take it off and come back here.")
        st.caption("Researcher: the headset should already show the VR page for participant "
                   f"{participant} (see README, 'Oculus setup').")
        wait_for_vr(participant)
    else:
        run_trial(participant, upcoming)
