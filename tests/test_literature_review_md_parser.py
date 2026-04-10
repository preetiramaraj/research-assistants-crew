from research_assistants.tools.pdf_downloader_service import parse_literature_review_markdown


def test_parse_literature_review_markdown_extracts_entries():
    md = """
# Literature review

### Paper 1
Title: Example Paper One
Authors: A. Author; B. Author
Year: 2024
DOI: 10.1000/xyz123
arXiv: N/A
Link: https://example.org/paper
Summary: Something.
Relevance: Very.

### Paper 2
- Title: Example Paper Two
- Authors: C. Author
- Year: 2023
- DOI: N/A
- arXiv: 2401.01234
- Link: https://arxiv.org/abs/2401.01234
"""

    papers = parse_literature_review_markdown(md)

    assert len(papers) == 2
    assert papers[0].title == "Example Paper One"
    assert papers[0].doi == "10.1000/xyz123"
    assert papers[0].arxiv == "N/A"

    assert papers[1].title == "Example Paper Two"
    assert papers[1].arxiv == "2401.01234"
