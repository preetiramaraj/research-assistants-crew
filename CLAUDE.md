# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A CrewAI-based multi-agent system that assists a researcher end-to-end: given a high-level research
question and domain, it proposes candidate research projects, searches Semantic Scholar for related
literature, downloads open-access PDFs, embeds them into a vector store, synthesizes a background
section via RAG, and finally proposes testable hypotheses/experiments. See `README.md` for the full
4-stage pipeline description and `architecture_diagram.png` for the system diagram.

The repo is split into **two isolated Python environments** because of a dependency conflict:

- **Main app** (`src/research_assistants/`) — CrewAI agents/tasks/tools, orchestration, literature
  search, PDF downloading. Managed with `uv` (`.venv`), dependencies pinned via `crewai==1.9.3`
  (which requires `tokenizers==0.20.3`).
- **Embedding service** (`embedding_service/`) — a separate FastAPI microservice for PDF → markdown →
  chunk → embed → ChromaDB, using `sentence-transformers`/`transformers`/`tokenizers>=0.22` (newer,
  incompatible versions). It must run in its own virtualenv or Docker container and is called over
  HTTP from the main app (not imported directly).


## Architecture

### Main crew (`src/research_assistants/crew.py`)
`ResearchAssistants` is a `@CrewBase` class wiring together agents and tasks declared in
`config/agents.yaml` and `config/tasks.yaml` (standard CrewAI YAML-config pattern — role/goal/backstory
per agent, description/expected_output/agent per task). LLMs are configured directly on the class
(currently Groq via `crewai.LLM`). Agents/tasks are added via the `@agent`/`@task` decorators and
collected automatically into `self.agents`/`self.tasks`; the `@crew` method assembles them into a
sequential `Crew`. Many agents/tasks in the YAML and in `crew.py` are commented out — they represent
pipeline stages that are being iterated on or run as separate scripts instead (see below), not dead
code to delete without checking.

A second, smaller crew, `ProjectRefiner` (`src/research_assistants/final_project_crew.py`), handles
just the hypothesis-generation stage, taking a project description and background section as input and
producing `results/final_hypothesis*.md`.

### Pipeline stages beyond the crew
Several stages are **not** CrewAI agents/tasks but standalone deterministic Python modules, invoked in
sequence from `run_crew.py` (with `time.sleep()` calls between them to let prior stages finish
writing files — later stages read the previous stage's output file from disk):

1. `research_assistants/crew.py` `ResearchAssistants().crew().kickoff(inputs=inputs)` — project scoping + search query generation (writes to `results/`).
2. `utils/literature_review.py` (`run_literature_review`) — reads `results/search_queries.md`, queries
   Semantic Scholar via `utils/semantic_scholar_client.py` (`SemanticScholarClient`, with `backoff`
   retry), dedupes/ranks papers, writes `results/literature_review.md` in a strict labeled-field
   markdown format (`### Paper N` headings with `Title:`/`Authors:`/`Year:`/`DOI:`/`arXiv:`/`Link:`/
   `Open Access PDF:` lines — this exact format is a contract other modules parse).
3. `utils/pdf_downloader_service.py` (`run_pdf_download`) — parses that markdown
   (`parse_literature_review_markdown`), resolves a PDF URL per paper with a fallback priority order
   (Semantic Scholar Open Access PDF → arXiv ID → DOI via Unpaywall, using `UNPAYWALL_EMAIL` env var),
   validates the response is actually a PDF (content-type or magic bytes, with HTML-scraping fallback
   to find a PDF link on landing pages), downloads to `lit_review_pdfs/`, and writes back paper
   metadata (title/authors/year) into each PDF's metadata via `pypdf` for later use in the RAG step.
   Produces `results/download_report.md`.
4. `embedding_service/pdf_to_embeddings.py` — convert downloaded PDFs to
   markdown (`pymupdf4llm`), chunk with `RecursiveCharacterTextSplitter` (token-length-aware via a nomic tokenizer, falling back to a char-count approximation if tokenization fails), embed with
   `nomic-ai/nomic-embed-text-v1.5` via `SentenceTransformerEmbeddingFunction`, and store in a
   persistent ChromaDB collection (metadata carries the title/authors/year written into the PDF in step
   3).
5. `embedding_service/retrieve_from_vectordb.py` / `generate_bg_section.py` — query the ChromaDB
   collection for chunks relevant to the research problem and synthesize the background section from
   retrieved chunks (currently via a direct Groq call, not through a CrewAI agent).
6. (Section in progress) `research_assistants/run_experiment_crew.py` `ProjectRefiner().crew().kickoff(inputs=inputs)` takes the inputs from all the prior stages with human_input=True and generates an experiment with testable hypotheses.

`run_crew.py` and `run_experiment_crew.py` and the .py files under `embedding_service` are ad hoc, non-packaged scripts used to manually run pieces of this pipeline against existing `results/*` files during development — check these first when trying to understand how a stage is invoked.

### Logging
File loggers are set up per-module via `utils/logging_config.py` (`setup_file_logger`), writing to
`src/research_assistants/logs/*.log` and `embedding_service/logs/*.log`. `semantic_scholar_client.py`
still uses stdlib `logging.basicConfig` directly (marked with a `TODO` to migrate to
`logging_config`).

### Tests
`tests/` uses plain `pytest` against the deterministic utility modules only (markdown parsing, PDF URL
resolution/validation, PDF metadata writing) — no tests exercise the CrewAI agents/LLM calls
themselves. Tests fake out HTTP responses with small dataclasses (see
`tests/test_pdf_resolvers.py::_FakeResponse`) rather than mocking `curl_cffi`/`requests` directly.

### Config/data flow contracts to preserve
- `results/search_queries.md`, `results/literature_review.md`, and `download_report.md` are plain-text
  contracts between pipeline stages — changing the markdown field format in `tasks.yaml`'s expected
  output or in `semantic_scholar_client.format_paper_entry` requires updating the corresponding parser
  in `pdf_downloader_service.parse_literature_review_markdown` (and vice versa).
- `.env` holds API keys (`SEMANTIC_SCHOLAR_API_KEY`, `UNPAYWALL_EMAIL`, Groq/LLM keys, etc.) — never
  committed (`.gitignore`d).
- `results/` and `lit_review_pdfs/` are `.gitignore`d output directories, regenerated by pipeline runs.

## Deferral rule
If you notice an improvement outside the current milestone (schemas/pydantic,
config management, logging, retries, retrieval quality, eval harness, Streamlit,
Docker), append one line to DEFERRED.md. Do NOT implement it.

## Working style
- Smallest possible diffs. One task per session.
- After any change, ask and then re-run the affected stage in isolation before moving on.
- Ask before restructuring folders or renaming beyond an explicitly agreed pass.
- Never run `uv` commands (e.g. `uv sync`, `uv add`) — only plain `python`/`pip` commands have been used
  to manage this project's environments. `uv sync` reconciles `.venv` to exactly match `uv.lock` and will
  silently uninstall any package present in `.venv` that isn't declared there, including packages the
  user installed manually outside of `uv`.
