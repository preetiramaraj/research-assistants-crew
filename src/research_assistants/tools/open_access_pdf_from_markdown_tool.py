from __future__ import annotations

from pathlib import Path
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from research_assistants.tools.pdf_downloader_service import (
    download_pdfs_from_markdown,
    format_download_report_md,
)


class OpenAccessPdfFromMarkdownToolInput(BaseModel):
    # Optional overrides. When omitted, the tool uses defaults provided at construction time
    # (wired in crew.py), so the agent can call the tool with no arguments.
    md_path: Optional[str] = Field(
        default=None,
        description="Path to results/literature_review.md. If omitted, the tool default is used.",
    )
    save_dir: Optional[str] = Field(
        default=None,
        description="Directory to save PDFs. If omitted, the tool default is used.",
    )
    max_papers: Optional[int] = Field(
        default=None,
        description="Optional cap on number of papers to process.",
    )
    overwrite: bool = Field(
        default=False,
        description="If true, overwrite existing PDFs.",
    )
    dry_run: bool = Field(
        default=False,
        description="If true, do not download; only report what would be done.",
    )


class OpenAccessPdfFromMarkdownTool(BaseTool):
    # CrewAI tool wrapper around a deterministic downloader service.
    # The downloading logic lives in `pdf_downloader_service.py` to keep this tool thin and testable.
    name: str = "Download PDFs from literature_review.md"
    description: str = (
        "Reads results/literature_review.md (with labeled fields like Title/DOI/arXiv/Link) "
        "and downloads PDFs for the listed papers into a local folder. Supports arXiv, Unpaywall (requires UNPAYWALL_EMAIL), "
        "Semantic Scholar, and direct PDF links."
    )
    args_schema: Type[BaseModel] = OpenAccessPdfFromMarkdownToolInput

    def __init__(self, md_path: str, save_dir: str):
        super().__init__()
        # Store defaults so the agent doesn't need to pass file paths every time.
        self._default_md_path = md_path
        self._default_save_dir = save_dir

    def _run(
        self,
        md_path: Optional[str] = None,
        save_dir: Optional[str] = None,
        max_papers: Optional[int] = None,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> str:
        # Resolve optional runtime overrides.
        md = Path(md_path or self._default_md_path)
        out_dir = Path(save_dir or self._default_save_dir)

        results = download_pdfs_from_markdown(
            md_path=md,
            save_dir=out_dir,
            max_papers=max_papers,
            overwrite=overwrite,
            dry_run=dry_run,
        )
        # Return markdown so the calling CrewAI Task can write it to `results/download_report.md`.
        return format_download_report_md(results)
