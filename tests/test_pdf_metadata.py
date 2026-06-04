from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter

from research_assistants.utils.pdf_downloader_service import (
    PaperEntry,
    add_metadata_to_pdf,
)


def _create_simple_pdf(path: Path, metadata: dict[str, str] | None = None) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    if metadata:
        writer.add_metadata(metadata)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        writer.write(f)


def test_add_metadata_to_pdf_writes_expected_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "metadata_test.pdf"
    _create_simple_pdf(pdf_path)

    paper = PaperEntry(
        title="A Test Title",
        authors="Jane Doe; John Smith",
        year="2026",
        doi="N/A",
        arxiv="N/A",
        link="N/A",
        open_access_pdf="N/A",
    )

    add_metadata_to_pdf(paper, pdf_path)

    reader = PdfReader(pdf_path)
    metadata = reader.metadata or {}

    assert metadata.get("/Title") == "A Test Title"
    assert metadata.get("/Authors") == "Jane Doe; John Smith"
    assert metadata.get("/Year") == "2026"


def test_add_metadata_to_pdf_preserves_existing_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "metadata_existing.pdf"
    _create_simple_pdf(pdf_path, metadata={"/Producer": "Original Producer", "/Title": "Old Title"})

    paper = PaperEntry(
        title="New Title",
        authors="Jane Doe",
        year="2026",
        doi="N/A",
        arxiv="N/A",
        link="N/A",
        open_access_pdf="N/A",
    )

    add_metadata_to_pdf(paper, pdf_path)

    reader = PdfReader(pdf_path)
    metadata = reader.metadata or {}

    assert metadata.get("/Producer") == "Original Producer"
    assert metadata.get("/Title") == "New Title"
    assert metadata.get("/Authors") == "Jane Doe"
    assert metadata.get("/Year") == "2026"
