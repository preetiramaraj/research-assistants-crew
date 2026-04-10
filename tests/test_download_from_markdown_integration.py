from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from unittest.mock import patch

from research_assistants.tools.pdf_downloader_service import download_pdfs_from_markdown


@dataclass
class _FakeResponse:
    """Minimal stand-in for `requests.Response` for resolver API calls.

    The resolver code only relies on `.ok` and `.json()`, so we keep this lightweight.
    """

    ok: bool
    _json: dict

    def json(self):
        return self._json


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


def test_download_pdfs_from_markdown_end_to_end(tmp_path: Path, monkeypatch):
    md_path = tmp_path / "literature_review.md"
    save_dir = tmp_path / "pdfs"

    md_path.write_text(
        """
# Literature review

### Paper 1
Title: Arxiv Paper
Authors: A
Year: 2024
DOI: N/A
arXiv: 2401.01234
Link: https://arxiv.org/abs/2401.01234
Summary: S
Relevance: R

### Paper 2
Title: Unpaywall DOI Paper
Authors: B
Year: 2023
DOI: 10.1000/unpaywall123
arXiv: N/A
Link: https://example.org/paper
Summary: S
Relevance: R

### Paper 3
Title: Semantic Scholar DOI Paper
Authors: C
Year: 2022
DOI: 10.1000/s2only456
arXiv: N/A
Link: https://example.org/paper2
Summary: S
Relevance: R

### Paper 4
Title: Direct PDF Link Paper
Authors: D
Year: 2021
DOI: N/A
arXiv: N/A
Link: https://example.org/file.pdf
Summary: S
Relevance: R
""",
        encoding="utf-8",
    )

    # Enable Unpaywall branch in resolver.
    monkeypatch.setenv("UNPAYWALL_EMAIL", "test@example.com")

    sess = _FakeSession(
        {
            # Unpaywall returns a direct PDF URL.
            "https://api.unpaywall.org/v2/10.1000/unpaywall123": _FakeResponse(
                ok=True,
                _json={
                    "best_oa_location": {
                        "url_for_pdf": "https://oa.example.org/unpaywall.pdf"
                    }
                },
            ),
            # Semantic Scholar only (Unpaywall not called for this DOI in this fake setup).
            "https://api.semanticscholar.org/graph/v1/paper/DOI:10.1000/s2only456": _FakeResponse(
                ok=True,
                _json={"openAccessPdf": {"url": "https://s2.example.org/paper.pdf"}},
            ),
        }
    )

    def fake_download(pdf_url: str, out_path: Path, session):
        # We patch the real downloader so tests don't make network calls.
        # A valid PDF starts with the magic bytes %PDF-.
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"%PDF-FAKE")

    with patch("research_assistants.tools.pdf_downloader_service.download_pdf", new=fake_download):
        results = download_pdfs_from_markdown(md_path=md_path, save_dir=save_dir, session=sess)

    assert len(results) == 4
    assert all(r.status == "downloaded" for r in results)

    # Explicitly verify the arXiv paper resolves to the canonical arXiv PDF URL.
    arxiv_result = next(r for r in results if r.paper.arxiv != 'N/A')
    assert arxiv_result.pdf_url == "https://arxiv.org/pdf/2401.01234.pdf"

    # Ensure files were created.
    pdf_files = list(save_dir.glob("*.pdf"))
    assert len(pdf_files) == 4
    assert all(p.read_bytes().startswith(b"%PDF-") for p in pdf_files)
