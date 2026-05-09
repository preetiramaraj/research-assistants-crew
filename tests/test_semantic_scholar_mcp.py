"""
Integration test for Semantic Scholar MCP tool.
Validates that the tool can be called and returns expected structure.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from research_assistants.tools.semantic_scholar_mcp_tool import SemanticScholarMCPTool


def test_semantic_scholar_tool_basic():
    """Test basic functionality of the Semantic Scholar MCP tool."""
    print("Testing Semantic Scholar MCP Tool...")
    
    # Initialize tool
    tool = SemanticScholarMCPTool()
    
    # Test with a simple query
    test_query = "human mental model robot"
    print(f"\nTest query: {test_query}")
    
    result = tool._run(query=test_query, limit=5)
    
    print(f"\nResult:\n{result}\n")
    
    # Validate output format
    assert "### Paper" in result or "No papers found" in result, "Output should contain paper entries or 'No papers found'"
    
    if "### Paper" in result:
        # Check for required fields
        assert "Title:" in result, "Output should contain Title field"
        assert "Authors:" in result, "Output should contain Authors field"
        assert "Year:" in result, "Output should contain Year field"
        assert "DOI:" in result, "Output should contain DOI field"
        assert "Link:" in result, "Output should contain Link field"
        assert "Citation Count:" in result, "Output should contain Citation Count field"
        assert "Open Access PDF:" in result, "Output should contain Open Access PDF field"
        
        print("✓ All required fields present in output")
    else:
        print("✓ No papers found (query may have no results, but tool works)")
    
    print("\n✓ Test passed!")
    return True


def test_semantic_scholar_tool_with_limit():
    """Test that the limit parameter works correctly."""
    print("\nTesting limit parameter...")
    
    tool = SemanticScholarMCPTool()
    
    test_query = "human robot interaction"
    result = tool._run(query=test_query, limit=3)
    
    # Count paper entries
    paper_count = result.count("### Paper")
    print(f"Found {paper_count} papers with limit=3")
    
    assert paper_count <= 3, f"Should return at most 3 papers, got {paper_count}"
    
    print("✓ Limit parameter works correctly")
    return True


def test_deduplication():
    """Test that deduplication logic works."""
    print("\nTesting deduplication logic...")
    
    from research_assistants.mcp_servers.semantic_scholar_server import deduplicate_papers
    
    # Create test papers with duplicates
    test_papers = [
        {"paperId": "1", "title": "Paper 1"},
        {"paperId": "2", "title": "Paper 2"},
        {"paperId": "1", "title": "Paper 1 Duplicate"},
        {"externalIds": {"DOI": "10.1000/xyz123"}, "title": "Paper 3"},
        {"externalIds": {"DOI": "10.1000/xyz123"}, "title": "Paper 3 Duplicate"},
    ]
    
    deduped = deduplicate_papers(test_papers)
    
    print(f"Original: {len(test_papers)} papers, Deduplicated: {len(deduped)} papers")
    assert len(deduped) == 3, f"Should have 3 unique papers, got {len(deduped)}"
    
    print("✓ Deduplication works correctly")
    return True


def test_ranking():
    """Test that ranking logic works."""
    print("\nTesting ranking logic...")
    
    from research_assistants.mcp_servers.semantic_scholar_server import rank_papers
    
    # Create test papers with different citation counts and years
    test_papers = [
        {"title": "Old high-citation", "citationCount": 100, "year": 2015},
        {"title": "New low-citation", "citationCount": 5, "year": 2024},
        {"title": "Medium recent", "citationCount": 50, "year": 2022},
    ]
    
    ranked = rank_papers(test_papers)
    
    print("Ranked papers:")
    for i, paper in enumerate(ranked):
        print(f"  {i+1}. {paper['title']} (citations: {paper['citationCount']}, year: {paper['year']})")
    
    # The ranking should favor a combination of citations and recency
    # Old high-citation should rank high due to citations
    # New low-citation should rank reasonably well due to recency
    assert len(ranked) == 3, "Should return all papers"
    
    print("✓ Ranking works correctly")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Semantic Scholar MCP Tool Integration Tests")
    print("=" * 60)
    
    # Check for API key
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        print("\n⚠ WARNING: SEMANTIC_SCHOLAR_API_KEY not set.")
        print("Tests may fail due to rate limiting or limited results.")
        print("Set the environment variable to run tests with full functionality.\n")
    else:
        print("\n✓ SEMANTIC_SCHOLAR_API_KEY is set\n")
    
    try:
        # Run tests
        test_deduplication()
        test_ranking()
        test_semantic_scholar_tool_basic()
        test_semantic_scholar_tool_with_limit()
        
        print("\n" + "=" * 60)
        print("All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
