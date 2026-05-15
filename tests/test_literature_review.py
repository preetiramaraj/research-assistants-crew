"""
Tests for literature review utility.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

from research_assistants.utils.literature_review import (
    read_search_queries,
    run_literature_review
)
from research_assistants.utils.semantic_scholar_client import (
    deduplicate_papers,
    rank_papers,
    format_papers_markdown
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_search_queries(temp_dir):
    """Create a sample search_queries.md file."""
    queries_file = temp_dir / "search_queries.md"
    queries_file.write_text("robot explanation trust\nmental model human robot\nnatural language robot behavior")
    return str(queries_file)


@pytest.fixture
def sample_papers():
    """Sample paper data for testing."""
    return [
        {
            "paperId": "1",
            "title": "Paper 1",
            "authors": [{"name": "Author A"}],
            "year": 2020,
            "citationCount": 100,
            "url": "https://example.com/1",
            "externalIds": {"DOI": "10.1234/1", "ArXiv": "arxiv.1"},
            "openAccessPdf": {"url": "https://example.com/1.pdf"}
        },
        {
            "paperId": "2",
            "title": "Paper 2",
            "authors": [{"name": "Author B"}],
            "year": 2021,
            "citationCount": 50,
            "url": "https://example.com/2",
            "externalIds": {"DOI": "10.1234/2"},
            "openAccessPdf": {"url": "https://example.com/2.pdf"}
        },
        {
            "paperId": "1",  # Duplicate
            "title": "Paper 1",
            "authors": [{"name": "Author A"}],
            "year": 2020,
            "citationCount": 100,
            "url": "https://example.com/1",
            "externalIds": {"DOI": "10.1234/1"},
            "openAccessPdf": {"url": "https://example.com/1.pdf"}
        }
    ]


class TestReadSearchQueries:
    """Tests for read_search_queries function."""

    def test_read_search_queries_success(self, sample_search_queries):
        """Test successful reading of search queries."""
        queries = read_search_queries(sample_search_queries)
        assert len(queries) == 3
        assert queries == ["robot explanation trust", "mental model human robot", "natural language robot behavior"]

    def test_read_search_queries_file_not_found(self):
        """Test reading from non-existent file."""
        queries = read_search_queries("non_existent_file.md")
        assert queries == []

    def test_read_search_queries_empty_file(self, temp_dir):
        """Test reading from empty file."""
        empty_file = temp_dir / "empty.md"
        empty_file.write_text("")
        queries = read_search_queries(str(empty_file))
        assert queries == []

    def test_read_search_queries_with_blank_lines(self, temp_dir):
        """Test reading file with blank lines."""
        queries_file = temp_dir / "queries.md"
        queries_file.write_text("query 1\n\nquery 2\n   \nquery 3")
        queries = read_search_queries(str(queries_file))
        assert len(queries) == 3
        assert queries == ["query 1", "query 2", "query 3"]


class TestDeduplicatePapers:
    """Tests for deduplicate_papers function."""

    def test_deduplicate_papers_removes_duplicates(self, sample_papers):
        """Test that duplicate papers are removed."""
        deduped = deduplicate_papers(sample_papers)
        assert len(deduped) == 2
        paper_ids = [p.get("paperId") for p in deduped]
        assert "1" in paper_ids
        assert "2" in paper_ids

    def test_deduplicate_papers_empty_list(self):
        """Test deduplication with empty list."""
        deduped = deduplicate_papers([])
        assert deduped == []

    def test_deduplicate_papers_no_duplicates(self, sample_papers):
        """Test deduplication with no duplicates."""
        unique_papers = sample_papers[:2]
        deduped = deduplicate_papers(unique_papers)
        assert len(deduped) == 2


class TestRankPapers:
    """Tests for rank_papers function."""

    def test_rank_papers_by_citation_and_recency(self):
        """Test ranking by citation count and recency."""
        papers = [
            {"title": "Old high cited", "year": 2010, "citationCount": 100},
            {"title": "New low cited", "year": 2023, "citationCount": 10},
            {"title": "New high cited", "year": 2023, "citationCount": 100},
        ]
        ranked = rank_papers(papers)
        # New high cited should be first (high citation + recent)
        assert ranked[0]["title"] == "New high cited"
        # Old high cited should be second (high citation but old)
        assert ranked[1]["title"] == "Old high cited"
        # New low cited should be last (low citation)
        assert ranked[2]["title"] == "New low cited"

    def test_rank_papers_empty_list(self):
        """Test ranking with empty list."""
        ranked = rank_papers([])
        assert ranked == []

    def test_rank_papers_missing_year(self):
        """Test ranking with papers missing year."""
        papers = [
            {"title": "No year", "citationCount": 50},
            {"title": "With year", "year": 2020, "citationCount": 50},
        ]
        ranked = rank_papers(papers)
        assert len(ranked) == 2


class TestFormatPapersMarkdown:
    """Tests for format_papers_markdown function."""

    def test_format_papers_markdown_output(self, sample_papers):
        """Test markdown formatting output."""
        unique_papers = sample_papers[:2]
        formatted = format_papers_markdown(unique_papers)
        
        assert "### Paper 1" in formatted
        assert "### Paper 2" in formatted
        assert "Title: Paper 1" in formatted
        assert "Authors: Author A" in formatted
        assert "Year: 2020" in formatted
        assert "DOI: 10.1234/1" in formatted
        assert "Citation Count: 100" in formatted

    def test_format_papers_markdown_empty_list(self):
        """Test formatting with empty list."""
        formatted = format_papers_markdown([])
        assert formatted == ""


class TestRunLiteratureReview:
    """Tests for run_literature_review function."""

    @patch('research_assistants.utils.literature_review.SemanticScholarClient')
    def test_run_literature_review_success(self, mock_client_class, temp_dir, sample_search_queries):
        """Test successful literature review execution."""
        # Setup mock client
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock API responses for 3 queries
        mock_client.search_papers.side_effect = [
            {"data": [{"paperId": "1", "title": "Paper 1", "authors": [{"name": "A"}], "year": 2020, "citationCount": 100, "url": "url1", "externalIds": {"DOI": "doi1"}, "openAccessPdf": {"url": "pdf1"}}]},
            {"data": [{"paperId": "2", "title": "Paper 2", "authors": [{"name": "B"}], "year": 2021, "citationCount": 50, "url": "url2", "externalIds": {"DOI": "doi2"}, "openAccessPdf": {"url": "pdf2"}}]},
            {"data": [{"paperId": "3", "title": "Paper 3", "authors": [{"name": "C"}], "year": 2022, "citationCount": 75, "url": "url3", "externalIds": {"DOI": "doi3"}, "openAccessPdf": {"url": "pdf3"}}]},
        ]
        
        output_file = temp_dir / "literature_review.md"
        
        # Run literature review
        run_literature_review(
            search_queries_path=sample_search_queries,
            output_path=str(output_file)
        )
        
        # Verify API was called 3 times
        assert mock_client.search_papers.call_count == 3
        
        # Verify output file was created
        assert output_file.exists()
        
        # Verify output contains expected content
        content = output_file.read_text()
        assert "### Paper 1" in content
        assert "Paper 1" in content
        assert "Paper 2" in content
        assert "Paper 3" in content

    @patch('research_assistants.utils.literature_review.SemanticScholarClient')
    def test_run_literature_review_with_duplicates(self, mock_client_class, temp_dir, sample_search_queries):
        """Test that deduplication works across multiple queries."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Return same paper from multiple queries
        same_paper = {"paperId": "1", "title": "Paper 1", "authors": [{"name": "A"}], "year": 2020, "citationCount": 100, "url": "url1", "externalIds": {"DOI": "doi1"}, "openAccessPdf": {"url": "pdf1"}}
        mock_client.search_papers.side_effect = [
            {"data": [same_paper]},
            {"data": [same_paper]},
            {"data": [same_paper]},
        ]
        
        output_file = temp_dir / "literature_review.md"
        
        run_literature_review(
            search_queries_path=sample_search_queries,
            output_path=str(output_file)
        )
        
        content = output_file.read_text()
        # Should only have one paper after deduplication
        assert content.count("### Paper") == 1

    @patch('research_assistants.utils.literature_review.SemanticScholarClient')
    def test_run_literature_review_handles_query_errors(self, mock_client_class, temp_dir, sample_search_queries):
        """Test that errors in individual queries don't stop execution."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # First query fails, second succeeds, third succeeds
        mock_client.search_papers.side_effect = [
            Exception("API error"),
            {"data": [{"paperId": "2", "title": "Paper 2", "authors": [{"name": "B"}], "year": 2021, "citationCount": 50, "url": "url2", "externalIds": {"DOI": "doi2"}, "openAccessPdf": {"url": "pdf2"}}]},
            {"data": [{"paperId": "3", "title": "Paper 3", "authors": [{"name": "C"}], "year": 2022, "citationCount": 75, "url": "url3", "externalIds": {"DOI": "doi3"}, "openAccessPdf": {"url": "pdf3"}}]},
        ]
        
        output_file = temp_dir / "literature_review.md"
        
        # Should not raise exception
        run_literature_review(
            search_queries_path=sample_search_queries,
            output_path=str(output_file)
        )
        
        # Should have papers from successful queries
        content = output_file.read_text()
        assert "Paper 2" in content
        assert "Paper 3" in content

    @patch('research_assistants.utils.literature_review.SemanticScholarClient')
    def test_run_literature_review_no_papers_found(self, mock_client_class, temp_dir, sample_search_queries):
        """Test handling when no papers are found."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Return empty results
        mock_client.search_papers.side_effect = [
            {"data": []},
            {"data": []},
            {"data": []},
        ]
        
        output_file = temp_dir / "literature_review.md"
        
        run_literature_review(
            search_queries_path=sample_search_queries,
            output_path=str(output_file)
        )
        
        content = output_file.read_text()
        assert "No papers found" in content

    @patch('research_assistants.utils.literature_review.SemanticScholarClient')
    def test_run_literature_review_no_queries(self, mock_client_class, temp_dir):
        """Test handling when no queries are found."""
        empty_file = temp_dir / "empty.md"
        empty_file.write_text("")
        
        output_file = temp_dir / "literature_review.md"
        
        run_literature_review(
            search_queries_path=str(empty_file),
            output_path=str(output_file)
        )
        
        # Should not call API
        mock_client_class.assert_not_called()
