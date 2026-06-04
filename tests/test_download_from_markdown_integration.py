from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from unittest.mock import patch

from pypdf import PdfWriter

from research_assistants.utils.pdf_downloader_service import download_pdfs_from_markdown


@dataclass
class _FakeResponse:
    """Minimal stand-in for `requests.Response` for resolver API calls.

    The resolver code only relies on `.ok` and `.json()`, so we keep this lightweight.
    """

    ok: bool
    _json: dict
    headers: dict = None
    _raw_content: bytes = b""

    def json(self):
        return self._json

    @property
    def raw(self):
        return _FakeRaw(self._raw_content)


class _FakeRaw:
    def __init__(self, content: bytes):
        self._content = content

    def read(self, n: int = -1):
        if n == -1:
            return self._content
        return self._content[:n]


class _FakeSession:
    """Minimal stand-in for `requests.Session`.

    Used to intercept Unpaywall/Semantic Scholar HTTP calls without hitting the network.
    """

    def __init__(self, routes: dict[str, _FakeResponse]):
        self._routes = routes

    def get(self, url: str, params=None, timeout=None, stream=None):
        # Match by URL prefix (good enough for resolver calls).
        for prefix, resp in self._routes.items():
            if url.startswith(prefix):
                return resp
        return _FakeResponse(ok=False, _json={})

    def head(self, url: str, timeout=None, allow_redirects=None):
        # Match by URL prefix (good enough for resolver calls).
        for prefix, resp in self._routes.items():
            if url.startswith(prefix):
                return resp
        return _FakeResponse(ok=False, _json={})


def _write_simple_pdf(out_path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        writer.write(f)


def test_download_pdfs_from_markdown_end_to_end(tmp_path: Path, monkeypatch):
    md_path = tmp_path / "literature_review.md"
    save_dir = tmp_path / "pdfs"

    md_path.write_text(
        """
# Literature review

### Paper 1
Title: Open Access PDF Paper
Authors: A
Year: 2024
DOI: 10.1000/oa123
arXiv: N/A
Link: https://example.org/paper
Open Access PDF: https://oa.example.org/paper.pdf

### Paper 2
Title: Arxiv Paper
Authors: B
Year: 2024
DOI: N/A
arXiv: 2401.01234
Link: https://arxiv.org/abs/2401.01234
Open Access PDF: N/A

### Paper 3
Title: Unpaywall DOI Paper
Authors: C
Year: 2023
DOI: 10.1000/unpaywall123
arXiv: N/A
Link: https://example.org/paper
Open Access PDF: N/A
""",
        encoding="utf-8",
    )

    # Enable Unpaywall branch in resolver.
    monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")

    sess = _FakeSession(
        {
            # Open Access PDF returns PDF content-type
            "https://oa.example.org/paper.pdf": _FakeResponse(
                ok=True,
                _json={},
                headers={"content-type": "application/pdf"},
            ),
            # Unpaywall returns a direct PDF URL.
            "https://api.unpaywall.org/v2/10.1000/unpaywall123": _FakeResponse(
                ok=True,
                _json={
                    "best_oa_location": {
                        "url_for_pdf": "https://oa.example.org/unpaywall.pdf"
                    }
                },
            ),
            # Validation response for Unpaywall PDF URL
            "https://oa.example.org/unpaywall.pdf": _FakeResponse(
                ok=True,
                _json={},
                headers={"content-type": "application/pdf"},
            ),
        }
    )

    def fake_download(pdf_url: str, out_path: Path, session):
        # We patch the real downloader so tests don't make network calls.
        _write_simple_pdf(out_path)

    with patch("research_assistants.utils.pdf_downloader_service.download_pdf", new=fake_download):
        results = download_pdfs_from_markdown(md_path=md_path, save_dir=save_dir, session=sess)

    assert len(results) == 3
    assert all(r.status == "downloaded" for r in results)

    # Explicitly verify the Open Access PDF paper uses the OA URL.
    oa_result = next(r for r in results if r.paper.open_access_pdf != 'N/A' and r.paper.open_access_pdf.startswith('https'))
    assert oa_result.pdf_url == "https://oa.example.org/paper.pdf"

    # Explicitly verify the arXiv paper resolves to the canonical arXiv PDF URL.
    arxiv_result = next(r for r in results if r.paper.arxiv != 'N/A')
    assert arxiv_result.pdf_url == "https://arxiv.org/pdf/2401.01234.pdf"

    # Ensure files were created.
    pdf_files = list(save_dir.glob("*.pdf"))
    assert len(pdf_files) == 3
    assert all(p.read_bytes().startswith(b"%PDF-") for p in pdf_files)


def test_download_pdfs_from_markdown_calls_add_metadata_to_pdf(tmp_path: Path, monkeypatch):
    md_path = tmp_path / "literature_review.md"
    save_dir = tmp_path / "pdfs"

    md_path.write_text(
        """
# Literature review

### Paper 1
Title: Test Metadata PDF
Authors: Jane Doe
Year: 2025
DOI: 10.1000/test123
arXiv: N/A
Link: https://example.org/paper
Open Access PDF: https://oa.example.org/paper.pdf
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")

    sess = _FakeSession(
        {
            "https://oa.example.org/paper.pdf": _FakeResponse(
                ok=True,
                _json={},
                headers={"content-type": "application/pdf"},
            )
        }
    )

    def fake_download(pdf_url: str, out_path: Path, session):
        _write_simple_pdf(out_path)

    with patch("research_assistants.utils.pdf_downloader_service.download_pdf", new=fake_download), \
        patch("research_assistants.utils.pdf_downloader_service.add_metadata_to_pdf") as mock_add_metadata:
        results = download_pdfs_from_markdown(md_path=md_path, save_dir=save_dir, session=sess)

    assert len(results) == 1
    assert results[0].status == "downloaded"
    assert mock_add_metadata.call_count == 1

    called_paper, called_path = mock_add_metadata.call_args.args
    assert called_paper.title == "Test Metadata PDF"
    assert called_path == save_dir / "Test Metadata PDF.pdf"
