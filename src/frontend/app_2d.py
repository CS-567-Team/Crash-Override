import streamlit as st
import json
import sys
import os
import csv 
from datetime import datetime

# Point to backend so we can use DemoProvider
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.services.model import DemoProvider

st.title("Task: Add Floor Division Feature")
st.write("Review the agent's output and decide if you want to accept this code.")

# Initialize AI provider placeholder
provider = DemoProvider()
fake_user_prompt = json.dumps({
    "task": {"id": "demo_task"},
    "files": {"app/example_calculator.py": '    if operator == "/":\n'}
})

# Let the presenter swap between three required workflows
workflow = st.radio("Active Workflow (Demo purposes):",
                    ["Programmer Only", "Programmer + Reviewer", "Planner + Programmer + Reviewer"])
st.markdown("---")

# Get the Programmer's code 
prog_response = provider.complete(role="programmer", system_prompt="", user_prompt=fake_user_prompt)
prog_data = json.loads(prog_response.text)
code_diff = prog_data["files"]["app/example_calculator.py"]

# Dynamically show tabs based on the active condition
if workflow == "Programmer Only":
    tab1, = st.tabs(["Code Diff"])
    with tab1:
        st.code(code_diff, language="python")

elif workflow == "Programmer + Reviewer":
    tab1, tab2 = st.tabs(["Code Diff", "Reviewer Feedback"])
    with tab1:
        st.code(code_diff, language="python")
    with tab2:
        rev_response = provider.complete(role="reviewer", system_prompt="", user_prompt=fake_user_prompt)
        rev_data = json.loads(rev_response.text)
        st.info(rev_data["summary"] + "\n\nVerdict: " + rev_data["verdict"])

elif workflow == "Planner + Programmer + Reviewer":
    tab1, tab2, tab3 = st.tabs(["Implementation Plan", "Code Diff", "Reviewer Feedback"])
    with tab1:
        plan_response = provider.complete(role="planner", system_prompt="", user_prompt=fake_user_prompt)
        plan_data = json.loads(plan_response.text)
        st.write(plan_data["summary"])
        for step in plan_data["steps"]:
            st.write(f"- {step}")
    with tab2:
        st.code(code_diff, language="python")
    with tab3:
        rev_response = provider.complete(role="reviewer", system_prompt="", user_prompt=fake_user_prompt)
        rev_data = json.loads(rev_response.text)
        st.info(rev_data["summary"] + "\n\nVerdict: " + rev_data["verdict"])

st.markdown("---")
decision = st.radio("Final Decision:", ["Accept", "Reject"])

if st.button("Submit Decision"):
    # The Telemetry Logger: Append the participant's actions to a CSV file
    log_file = "telemetry_log.csv"
    file_exists = os.path.isfile(log_file)
    
    with open(log_file, "a", newline="") as f:
        writer = csv.writer(f)
        # Write the column headers if this is the very first click
        if not file_exists:
            writer.writerow(["timestamp", "workflow_condition", "task_id", "decision"])
        
        # Log the actual data for this specific trial
        writer.writerow([datetime.now().isoformat(), workflow, "demo_task", decision])
        
    st.success(f"Data logged! Participant chose: '{decision}' under the '{workflow}' condition.")