from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"


def latest_run_dir() -> Path:
    return sorted(RESULTS_DIR.glob("run_*"))[-1]
