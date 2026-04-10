from __future__ import annotations

from dataclasses import dataclass

from research_assistants.tools.pdf_downloader_service import PaperEntry, resolve_pdf_url


@dataclass
class _FakeResponse:
    ok: bool
    _json: dict

    def json(self):
        return self._json


class _FakeSession:
    def __init__(self, routes: dict[str, _FakeResponse]):
        self._routes = routes

    def get(self, url: str, params=None, timeout=None):
        # For convenience, ignore params and match by URL prefix.
        for prefix, resp in self._routes.items():
            if url.startswith(prefix):
                return resp
        return _FakeResponse(ok=False, _json={})


def test_resolve_pdf_url_prefers_arxiv_when_present():
    paper = PaperEntry(
        title="T",
        authors="A",
        year="2024",
        doi="N/A",
        arxiv="2401.01234",
        link="N/A",
    )

    url = resolve_pdf_url(paper, _FakeSession({}))
    assert url == "https://arxiv.org/pdf/2401.01234.pdf"


def test_resolve_pdf_url_uses_unpaywall_when_email_provided():
    paper = PaperEntry(
        title="T",
        authors="A",
        year="2024",
        doi="10.1000/xyz123",
        arxiv="N/A",
        link="N/A",
    )

    sess = _FakeSession(
        {
            "https://api.unpaywall.org/v2/10.1000/xyz123": _FakeResponse(
                ok=True,
                _json={
                    "best_oa_location": {
                        "url_for_pdf": "https://oa.example.org/paper.pdf"
                    }
                },
            )
        }
    )

    url = resolve_pdf_url(paper, sess, unpaywall_email="x@example.com")
    assert url == "https://oa.example.org/paper.pdf"


def test_resolve_pdf_url_uses_semantic_scholar_when_unpaywall_not_used():
    paper = PaperEntry(
        title="T",
        authors="A",
        year="2024",
        doi="10.1000/xyz123",
        arxiv="N/A",
        link="N/A",
    )

    sess = _FakeSession(
        {
            "https://api.semanticscholar.org/graph/v1/paper/DOI:10.1000/xyz123": _FakeResponse(
                ok=True,
                _json={"openAccessPdf": {"url": "https://s2.example.org/p.pdf"}},
            )
        }
    )

    url = resolve_pdf_url(paper, sess)
    assert url == "https://s2.example.org/p.pdf"


def test_resolve_pdf_url_direct_pdf_link_fallback():
    paper = PaperEntry(
        title="T",
        authors="A",
        year="2024",
        doi="N/A",
        arxiv="N/A",
        link="https://example.org/file.pdf",
    )

    url = resolve_pdf_url(paper, _FakeSession({}))
    assert url == "https://example.org/file.pdf"
