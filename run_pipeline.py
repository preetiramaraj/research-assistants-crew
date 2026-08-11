#!/usr/bin/env python
"""Run the full research-assistants pipeline end to end.

Chains, in order: project scoping + search query generation (.venv),
PDF -> embeddings, background retrieval, background synthesis (.venv-embed),
and hypothesis generation (.venv). See CLAUDE.md for why two venvs are needed.

Several stages prompt for human input (reviewing a candidate project,
reviewing search queries, selecting a Chroma collection, refining the final
hypothesis) - this script inherits your terminal's stdin/stdout so you can
answer those prompts as they come up.
"""

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

VENV_SUBDIR = "Scripts" if sys.platform == "win32" else "bin"
PYTHON_NAME = "python.exe" if sys.platform == "win32" else "python"

MAIN_VENV_PYTHON = REPO_ROOT / ".venv" / VENV_SUBDIR / PYTHON_NAME
EMBED_VENV_PYTHON = REPO_ROOT / ".venv-embed" / VENV_SUBDIR / PYTHON_NAME

STAGES = [
    ("Project scoping + search queries", MAIN_VENV_PYTHON, REPO_ROOT / "src" / "research_assistants" / "run_crew.py"),
    ("PDF -> embeddings", EMBED_VENV_PYTHON, REPO_ROOT / "embedding_service" / "pdf_to_embeddings.py"),
    ("Retrieve background chunks", EMBED_VENV_PYTHON, REPO_ROOT / "embedding_service" / "retrieve_from_vectordb.py"),
    ("Generate background section", EMBED_VENV_PYTHON, REPO_ROOT / "embedding_service" / "generate_bg_section.py"),
    ("Hypothesis generation", MAIN_VENV_PYTHON, REPO_ROOT / "src" / "research_assistants" / "run_experiment_crew.py"),
]


def check_venvs():
    missing = []
    if not MAIN_VENV_PYTHON.exists():
        missing.append("  .venv is missing - run: python -m venv .venv && .venv/Scripts/pip install -r requirements.txt")
    if not EMBED_VENV_PYTHON.exists():
        missing.append("  .venv-embed is missing - run: python -m venv .venv-embed && .venv-embed/Scripts/pip install -r requirements-embeddings.txt")
    if missing:
        print("Cannot run pipeline - required virtual environment(s) not found:", file=sys.stderr)
        for line in missing:
            print(line, file=sys.stderr)
        sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-stage",
        type=int,
        default=1,
        metavar="N",
        help=f"Resume from stage N (1-{len(STAGES)}) instead of running the whole pipeline. "
             f"Useful after a stage fails partway (e.g. a rate limit) and you don't want to redo earlier stages.",
    )
    parser.add_argument(
        "--to-stage",
        type=int,
        default=len(STAGES),
        metavar="N",
        help=f"Stop after stage N (1-{len(STAGES)}) instead of running through the end. "
             f"Combine with --from-stage to run a single stage or a sub-range.",
    )
    args = parser.parse_args()
    if not 1 <= args.from_stage <= len(STAGES):
        parser.error(f"--from-stage must be between 1 and {len(STAGES)}")
    if not 1 <= args.to_stage <= len(STAGES):
        parser.error(f"--to-stage must be between 1 and {len(STAGES)}")
    if args.from_stage > args.to_stage:
        parser.error("--from-stage must be <= --to-stage")
    return args


def main():
    args = parse_args()
    check_venvs()

    for i, (label, python_exe, script_path) in enumerate(STAGES, start=1):
        if i < args.from_stage or i > args.to_stage:
            continue
        print(f"\n=== Stage {i}/{len(STAGES)}: {label} ===")
        try:
            subprocess.run([str(python_exe), str(script_path)], cwd=REPO_ROOT, check=True)
        except subprocess.CalledProcessError as e:
            print(f"\nPipeline stopped: stage {i}/{len(STAGES)} ({label}) failed with exit code {e.returncode}.", file=sys.stderr)
            sys.exit(e.returncode)

    if args.to_stage == len(STAGES):
        print("\nPipeline complete.")
    else:
        print(f"\nStages {args.from_stage}-{args.to_stage} complete.")


if __name__ == "__main__":
    main()
