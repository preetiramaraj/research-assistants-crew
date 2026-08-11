# Deferred improvements

- `latest_run_dir()` (`src/research_assistants/utils/run_paths.py`, `embedding_service/run_paths.py`) raises an unhelpful `IndexError` if no `results/run_*` folder exists yet; add a clear error message at its call sites (e.g. `retrieve_from_vectordb.py`'s `retrieve_keywords()` and `select_collection()`) instead of letting it propagate raw.
- `embedding_service/` scripts (`pdf_to_embeddings.py`, `retrieve_from_vectordb.py`, `generate_bg_section.py`) have no `.env` loading mechanism at all — `CHROMADB_PATH`/`CHROMADB_COLLECTION`/`PDF_FOLDER` and `GROQ_API_KEY` (via `groq.Groq()`) only work if the shell/process env already has them set.
- `retrieve_from_vectordb.py`'s `select_collection()` blocks on `input()` with no way to skip it (e.g. an env var or CLI flag to accept the default collection) — fine for a human running `run_pipeline.py` interactively, but blocks any future fully-unattended/CI run of the pipeline.
