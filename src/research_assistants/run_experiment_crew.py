import sys
import warnings
import time
from datetime import datetime
from research_assistants.project_refiner_crew import ProjectRefiner
from research_assistants.utils.run_paths import latest_run_dir

run_dir = latest_run_dir()

with open(run_dir / "research_problem.md", "r", encoding='utf-8') as f:
    project_description = f.read()
with open(run_dir / "background_section.txt", "r", encoding='utf-8') as f:
    background_section = f.read()

inputs = {
        "domain": "Human-robot interaction",
        "research-question": "How do you improve mentals models of humans to improve their interaction with robots?",
        "project-description": project_description,
        "background-section": background_section,
        "run_dir": run_dir.as_posix()
}

try:
    ProjectRefiner().crew().kickoff(inputs=inputs)
except Exception as e:
    raise Exception(f"An error occurred while running the crew: {e}")