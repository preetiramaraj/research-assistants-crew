"""
Standalone literature review utility.
Reads search queries from search_queries.md, queries Semantic Scholar API,
deduplicates and ranks results, and writes to literature_review.md.
"""

from pathlib import Path
from typing import List, Dict, Any
from research_assistants.utils.logging_config import setup_file_logger

from research_assistants.utils.run_paths import latest_run_dir
from research_assistants.utils.semantic_scholar_client import (
    SemanticScholarClient,
    deduplicate_papers,
    rank_papers,
    format_papers_markdown,
    DEFAULT_YEAR_FILTER,
    DEFAULT_FIELDS,
    DEFAULT_LIMIT
)

logger = setup_file_logger(
    __name__,
    Path(__file__).resolve().parents[1] / "logs" / "literature_review.log"
)


def read_search_queries(file_path: str) -> List[str]:
    """Read search queries from a markdown file, one per line."""
    queries_path = Path(file_path)
    if not queries_path.exists():
        logger.error(f"Search queries file not found: {file_path}")
        return []
    
    with open(queries_path, 'r', encoding='utf-8') as f:
        queries = [line.strip() for line in f if line.strip()]
    
    logger.info(f"Read {len(queries)} search queries from {file_path}")
    return queries


def run_literature_review(
    search_queries_path: str = None,
    output_path: str = None
) -> None:
    """
    Run literature review by querying Semantic Scholar for all search queries,
    collecting all papers, deduplicating, ranking, and writing to markdown.
    
    Args:
        search_queries_path: Path to search_queries.md file
        output_path: Path to write literature_review.md
    """
    # Set default paths relative to the latest run folder
    if search_queries_path is None:
        search_queries_path = str(latest_run_dir() / "search_queries.md")
    if output_path is None:
        output_path = str(latest_run_dir() / "literature_review.md")
    
    # Read search queries
    queries = read_search_queries(search_queries_path)
    if not queries:
        logger.error("No search queries found. Exiting.")
        return
    
    # Initialize client
    client = SemanticScholarClient()
    
    # Collect all papers from all queries
    all_papers = []
    for i, query in enumerate(queries, 1):
        try:
            logger.info(f"Processing query {i}/{len(queries)}: {query}")
            response = client.search_papers(
                query=query,
                year=DEFAULT_YEAR_FILTER,
                limit=DEFAULT_LIMIT,
                offset=0,
                fields=DEFAULT_FIELDS
            )
            papers = response.get("data", [])
            all_papers.extend(papers)
            logger.info(f"Found {len(papers)} papers for query: {query}")
        except Exception as e:
            logger.error(f"Error processing query '{query}': {e}")
            continue
    
    if not all_papers:
        logger.warning("No papers found for any query. Writing empty output.")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# No papers found\n\nNo matching papers were found for the given search queries.\n")
        return
    
    logger.info(f"Total papers collected before deduplication: {len(all_papers)}")
    
    # Deduplicate papers
    deduped_papers = deduplicate_papers(all_papers)
    logger.info(f"Papers after deduplication: {len(deduped_papers)}")
    
    # Rank papers
    ranked_papers = rank_papers(deduped_papers)
    logger.info(f"Papers after ranking: {len(ranked_papers)}")
    
    # Format as markdown
    formatted_md = format_papers_markdown(ranked_papers)
    
    # Write to output file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(formatted_md)
    
    logger.info(f"Literature review written to {output_path}")


# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     run_literature_review()
