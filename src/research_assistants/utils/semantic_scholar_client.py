#!/usr/bin/env python3
"""
Semantic Scholar API client with paper ranking and deduplication utilities.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
import backoff

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
API_KEY_ENV_VAR = "SEMANTIC_SCHOLAR_API_KEY"
DEFAULT_YEAR_FILTER = "2005-"
DEFAULT_LIMIT = 10
DEFAULT_FIELDS = "title,url,year,authors,abstract,citationCount,openAccessPdf,externalIds"
DEFAULT_MIN_CITATION_COUNT = 50


class SemanticScholarClient:
    """Client for Semantic Scholar API with retry logic."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv(API_KEY_ENV_VAR)
        if not self.api_key:
            logger.warning(f"{API_KEY_ENV_VAR} not set. API may be rate-limited.")
    
    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.RequestException, requests.exceptions.HTTPError),
        max_tries=3,
        giveup=lambda e: isinstance(e, requests.exceptions.HTTPError) and e.response.status_code not in [429, 500, 502, 503, 504]
    )
    def search_papers(
        self,
        query: str,
        year: str = DEFAULT_YEAR_FILTER,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
        fields: str = DEFAULT_FIELDS,
        min_citation_count: int = DEFAULT_MIN_CITATION_COUNT
    ) -> Dict[str, Any]:
        """Search for papers on Semantic Scholar."""
        params = {
            "query": query,
            "fields": fields,
            "year": year,
            "limit": limit,
            "offset": offset,
            "minCitationCount": min_citation_count
        }
        
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        
        response = requests.get(SEMANTIC_SCHOLAR_API_URL, params=params, headers=headers)
        response.raise_for_status()
        return response.json()


def deduplicate_papers(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate papers by paperId or DOI."""
    seen = set()
    deduped = []
    
    for paper in papers:
        # Use paperId as primary key, fallback to DOI
        paper_id = paper.get("paperId") or paper.get("externalIds", {}).get("DOI")
        if not paper_id:
            continue
        
        if paper_id not in seen:
            seen.add(paper_id)
            deduped.append(paper)
    
    return deduped


def rank_papers(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rank papers by combination of citation count and recency.
    Uses a weighted score: citation_count * recency_factor
    """
    current_year = datetime.now().year
    
    def calculate_score(paper: Dict[str, Any]) -> float:
        citation_count = paper.get("citationCount", 0)
        year = paper.get("year")
        
        if year:
            # Recency factor: exponential decay, more recent papers get higher factor
            years_old = current_year - year
            recency_factor = 0.97 ** years_old  # 3% decay per year (slower decay)
        else:
            recency_factor = 0.8  # Default for papers without year
        
        # Weighted score: favor citations heavily, with mild recency boost
        return citation_count * (1.0 + recency_factor)
    
    # Sort by score descending
    ranked = sorted(papers, key=calculate_score, reverse=True)
    return ranked


def format_paper_entry(paper: Dict[str, Any], index: int) -> str:
    """Format a single paper entry in the required markdown format."""
    # Extract authors
    authors = paper.get("authors", [])
    authors_str = ", ".join([a.get("name", "") for a in authors]) if authors else "N/A"
    
    # Extract DOI
    doi = paper.get("externalIds", {}).get("DOI", "N/A")
    
    # Extract arXiv ID if available
    arxiv_id = paper.get("externalIds", {}).get("ArXiv", "N/A")
    
    # Extract URL
    url = paper.get("url", "N/A")
    
    # Extract citation count
    citation_count = paper.get("citationCount", 0)
    
    # Extract open access PDF
    open_access_pdf = paper.get("openAccessPdf", {})
    pdf_url = open_access_pdf.get("url", "N/A") if open_access_pdf else "N/A"
    
    entry = f"""### Paper {index + 1}
Title: {paper.get("title", "N/A")}
Authors: {authors_str}
Abstract: {paper.get("abstract", "N/A")}
Year: {paper.get("year", "N/A")}
DOI: {doi}
arXiv: {arxiv_id}
Link: {url}
Citation Count: {citation_count}
Open Access PDF: {pdf_url}"""
    
    return entry


def format_papers_markdown(papers: List[Dict[str, Any]]) -> str:
    """Format all papers as a markdown list."""
    return "\n\n".join([format_paper_entry(paper, i) for i, paper in enumerate(papers)])
