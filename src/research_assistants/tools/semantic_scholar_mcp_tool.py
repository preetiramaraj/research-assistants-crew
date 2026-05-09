"""
CrewAI tool wrapper for Semantic Scholar MCP server.
This tool communicates with the MCP server to search and format papers.
"""

import asyncio
import subprocess
import json
from typing import Type, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
import logging

logger = logging.getLogger(__name__)


class SemanticScholarMCPToolInput(BaseModel):
    """Input schema for SemanticScholarMCPTool."""
    query: str = Field(..., description="Search query for Semantic Scholar (e.g., 'human mental model robot')")
    limit: int = Field(default=10, description="Maximum number of results to return (default: 10)")
    offset: int = Field(default=0, description="Offset for pagination (default: 0)")


class SemanticScholarMCPTool(BaseTool):
    name: str = "semantic_scholar_search"
    description: str = (
        "Search for papers on Semantic Scholar and return a ranked, deduplicated list "
        "formatted as markdown. Each paper includes title, authors, year, DOI, arXiv ID, "
        "link, citation count, and open access PDF URL. Papers are ranked by a combination "
        "of citation count and recency. Use this tool for literature review tasks."
    )
    args_schema: Type[BaseModel] = SemanticScholarMCPToolInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._mcp_process: Optional[subprocess.Popen] = None
        self._mcp_client = None
    
    def _run(self, query: str, limit: int = 10, offset: int = 0) -> str:
        """
        Execute the semantic scholar search by calling the MCP server.
        For simplicity, we'll directly use the semantic scholar client logic
        instead of spawning a separate MCP process, which is more reliable in CrewAI context.
        """
        from research_assistants.mcp_servers.semantic_scholar_server import (
            SemanticScholarClient,
            deduplicate_papers,
            rank_papers,
            format_papers_markdown,
            DEFAULT_YEAR_FILTER,
            DEFAULT_FIELDS
        )
        
        try:
            # Initialize client
            client = SemanticScholarClient()
            
            # Search papers
            logger.info(f"Searching Semantic Scholar with query: {query}")
            response = client.search_papers(
                query=query,
                year=DEFAULT_YEAR_FILTER,
                limit=limit,
                offset=offset,
                fields=DEFAULT_FIELDS
            )
            
            # Extract papers
            papers = response.get("data", [])
            
            if not papers:
                return f"No papers found for query: {query}"
            
            # Deduplicate
            deduped_papers = deduplicate_papers(papers)
            logger.info(f"Deduplicated {len(papers)} papers to {len(deduped_papers)}")
            
            # Rank
            ranked_papers = rank_papers(deduped_papers)
            logger.info(f"Ranked {len(ranked_papers)} papers")
            
            # Format output
            formatted_md = format_papers_markdown(ranked_papers)
            
            return formatted_md
            
        except Exception as e:
            logger.error(f"Error in semantic scholar search: {e}")
            return f"Error searching Semantic Scholar: {str(e)}"
    
    async def _arun(self, query: str, limit: int = 10, offset: int = 0) -> str:
        """Async version - not used in CrewAI but required by BaseTool."""
        return self._run(query, limit, offset)
