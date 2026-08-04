#!/usr/bin/env python

import sys
import warnings
import time
from datetime import datetime
from research_assistants.crew import ResearchAssistants
from research_assistants.utils.literature_review import run_literature_review
from research_assistants.utils.pdf_downloader_service import run_pdf_download
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


inputs = {
        "domain": "Human-robot interaction",
        "research-question": "How do you improve mentals models of humans to improve their interaction with robots?"
    }

try:
    ResearchAssistants().crew().kickoff(inputs=inputs)
    # Inserting a sleep timer so that the next function runs only after the documents from the crew run are written
    time.sleep(3)
    run_literature_review()
    # Inserting a sleep timer so that the next function runs only after the documents from the function are written
    time.sleep(1)
    run_pdf_download()
except Exception as e:
    raise Exception(f"An error occurred while running the crew: {e}")
