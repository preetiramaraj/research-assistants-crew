#!/usr/bin/env python

import sys
import warnings
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from research_assistants.crew import ResearchAssistants
from research_assistants.utils.literature_review import run_literature_review
from research_assistants.utils.pdf_downloader_service import run_pdf_download
from research_assistants.utils.run_paths import RESULTS_DIR
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

run_dir = RESULTS_DIR / f"run_{datetime.now():%Y-%m-%d_%H-%M-%S}"
run_dir.mkdir(parents=True)

inputs = {
        "domain": "Human-robot interaction",
        "research-question": "How do you improve mentals models of humans to improve their interaction with robots?",
        "run_dir": run_dir.as_posix(),
    }

try:
    ResearchAssistants().crew().kickoff(inputs=inputs)
    # Inserting a sleep timer so that the next function runs only after the documents from the crew run are written
    time.sleep(3)
    run_literature_review(
        search_queries_path=str(run_dir / "search_queries.md"),
        output_path=str(run_dir / "literature_review.md"),
    )
    # Inserting a sleep timer so that the next function runs only after the documents from the function are written
    time.sleep(1)
    run_pdf_download(
        md_path=str(run_dir / "literature_review.md"),
        save_dir=str(run_dir / "lit_review_pdfs"),
        output_report=str(run_dir / "download_report.md"),
    )
except Exception as e:
    raise Exception(f"An error occurred while running the crew: {e}")
