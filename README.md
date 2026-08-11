# Research Assistant Crew

### This is a AI agent system built with CrewAI, Python and LLMs set up to assist a researcher with defining research projects and hypotheses for a specific high-level research question. 

## Architecture Diagram 
The following is the proposed architecture of the system.

![Image](architecture_diagram.png)



## Current plan of implementation

The user provides a high-level research question and domain. From there, the system runs through four stages:
1. **Project Scoping** — A researcher agent proposes candidate research projects based on the input. The user selects one to pursue.

2. **Literature Search** — The agent generates targeted search queries for the selected project. These queries are run against Semantic Scholar's API to retrieve a list of relevant papers. The following pipeline then downloads any open-access versions of those papers via arXiv and Unpaywall. The user reviews the retrieved papers and selects which ones to carry forward to the next stage.

3. **Background Synthesis** — Downloaded papers are chunked and embedded into a ChromaDB vector store. Predefined queries probe the research space, and the retrieved context is passed to an LLM to synthesize a structured background section.

4. **Hypothesis Generation** — An experimenter agent proposes a research hypothesis or experimental design grounded in the generated background and the research project description. The user can iterate on this with feedback, prompting the agent to refine or regenerate its output.


## How to run

### 1. Prerequisites
Python 3.10-3.13.

### 2. Configure API keys
Create a `.env` file in the repo root with:
- `SEMANTIC_SCHOLAR_API_KEY`
- `UNPAYWALL_EMAIL`
- `GROQ_API_KEY`

### 3. Set up the two virtual environments
This repo uses two isolated virtual environments because of a dependency conflict between `crewai` and the embedding stack (see `CLAUDE.md` for details). Both must exist, with these exact names, at the repo root:

```
python -m venv .venv
.venv/Scripts/pip install -r requirements-venv.txt        # .venv/bin/pip on macOS/Linux

python -m venv .venv-embed
.venv-embed/Scripts/pip install -r requirements-venv-embed.txt   # .venv-embed/bin/pip on macOS/Linux
```

### 4. Run the pipeline
```
python run_pipeline.py
```
This runs the pipeline above end to end (5 scripts total — stage 3, Background Synthesis, is split across three of them). The run is interactive — it will pause for your input at several points (reviewing/selecting a candidate project, reviewing search queries, selecting a Chroma collection, refining the final hypothesis).

If a stage fails partway (e.g. an LLM rate limit), rerun from that stage instead of starting over:
```
python run_pipeline.py --from-stage 5
```

Use `--to-stage` to stop after a given stage, or combine both flags to run a single stage or sub-range:
```
python run_pipeline.py --from-stage 3 --to-stage 3
```



