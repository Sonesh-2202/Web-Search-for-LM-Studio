"""
MCP Internet Server v3.0 - Main Entry Point

This server provides internet access tools for local LLMs in LM Studio.
Run with: uv run python -m mcp_internet.server

Features:
- Fresh search with multi-source page extraction
- Current time context included in search and news results
- Structured output with source URLs
- User-agent rotation and rate limiting
"""

import logging
import sys

from mcp.server.fastmcp import FastMCP

# Configure logging to stderr (important for MCP STDIO transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Fix Windows encoding for emojis
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Initialize FastMCP server
mcp = FastMCP("mcp-internet")


def _with_fetch_timestamp(label: str, result: str) -> str:
    """Attach the local/UTC retrieval time to live data without another tool call."""
    from .tools.time import get_current_datetime as _get_datetime
    return f"{label} at {_get_datetime()}\n\n{result}"


# =============================================================================
# SEARCH TOOLS
# =============================================================================
@mcp.tool()
async def search_web(query: str, num_results: int = 10, deep_search: bool = False) -> str:
    """Quickly find current web links and snippets from a fresh search.

    Use smart_search for an answer that needs evidence from page content.
    
    Args:
        query: The search query (person, topic, question, anything)
        num_results: Number of results (default: 10, max: 20)
        deep_search: Fetch and extract content from top results for details
    """
    from .tools.search import search_web as _search
    return await _search(query, min(num_results, 20), deep_search)


@mcp.tool()
async def smart_search(query: str, max_sources: int = 3) -> str:
    """Always use for real-world factual answers.

    Searches afresh, reads top source pages in parallel, and includes current
    local/UTC time context. Use deep_search when broader coverage is needed.
    """
    from .tools.search import smart_search as _smart_search
    return await _smart_search(query, max(1, min(max_sources, 8)))


@mcp.tool()
async def deep_search(query: str, num_sources: int = 5) -> str:
    """Do fresh, broader research and read multiple source pages in parallel.
    
    Args:
        query: Research topic or question
        num_sources: Number of pages to scrape and analyze (1-8, default: 5)
    """
    from .tools.search import deep_search as _deep
    return await _deep(query, min(num_sources, 8))


# =============================================================================
# CONTENT READING
# =============================================================================
@mcp.tool()
async def read_webpage(url: str, max_length: int = 5000) -> str:
    """
    Extract text content from a webpage.
    
    Automatically detects and extracts:
    - Main article/page content
    - Structured data (JSON-LD, Schema.org)  
    - HTML tables (converted to markdown)
    - Meta descriptions and OpenGraph data
    
    Args:
        url: The URL to read
        max_length: Maximum characters (default: 5000)
    """
    from .tools.webpage import read_webpage as _read
    return _with_fetch_timestamp("Page fetched", await _read(url, max_length))


@mcp.tool()
async def read_pdf(url: str, max_pages: int = 5) -> str:
    """
    Extract text from a PDF URL.
    
    Args:
        url: URL of the PDF file
        max_pages: Maximum pages to extract (default: 5)
    """
    from .tools.pdf_reader import read_pdf as _read_pdf
    return _with_fetch_timestamp("PDF fetched", await _read_pdf(url, max_pages, 5000))


# =============================================================================
# NEWS & SOCIAL
# =============================================================================
@mcp.tool()
async def get_news(topic: str = "world", count: int = 5) -> str:
    """Fetch fresh headlines and include the current local/UTC fetch time.
    
    Args:
        topic: 'world', 'technology', 'business', etc. or search query
        count: Number of headlines (default: 5)
    """
    from .tools.news import get_news as _news
    news = await _news(topic, min(count, 10))
    return _with_fetch_timestamp("News fetched", news)


@mcp.tool()
async def search_reddit(query: str, subreddit: str = "", num_results: int = 5) -> str:
    """
    Search Reddit for posts.
    
    Args:
        query: Search query
        subreddit: Optional subreddit to search within
        num_results: Number of results (default: 5)
    """
    from .tools.reddit import search_reddit as _search_reddit
    result = await _search_reddit(query, subreddit, min(num_results, 10), "relevance")
    return _with_fetch_timestamp("Reddit results fetched", result)


# =============================================================================
# YOUTUBE
# =============================================================================
@mcp.tool()
async def search_youtube(query: str, num_results: int = 5) -> str:
    """
    Search YouTube for videos.
    
    Args:
        query: Search query
        num_results: Number of results (default: 5)
    """
    from .tools.youtube import search_youtube as _search_yt
    result = await _search_yt(query, min(num_results, 10))
    return _with_fetch_timestamp("YouTube results fetched", result)


@mcp.tool()
async def get_video_info(url: str) -> str:
    """
    Get YouTube video information.
    
    Args:
        url: YouTube video URL or video ID
    """
    from .tools.youtube import get_video_info as _get_video
    return _with_fetch_timestamp("Video details fetched", await _get_video(url))


# =============================================================================
# GITHUB
# =============================================================================
@mcp.tool()
async def search_github(query: str, num_results: int = 5, language: str = "") -> str:
    """
    Search GitHub repositories.
    
    Args:
        query: Search query
        num_results: Number of results (default: 5)
        language: Filter by language (e.g., 'python')
    """
    from .tools.github import search_github as _search_gh
    result = await _search_gh(query, min(num_results, 10), language, "stars")
    return _with_fetch_timestamp("GitHub results fetched", result)


@mcp.tool()
async def get_repo_info(repo: str) -> str:
    """
    Get GitHub repository information.
    
    Args:
        repo: Repository as 'owner/repo' (e.g., 'microsoft/vscode')
    """
    from .tools.github import get_repo_info as _get_repo
    return _with_fetch_timestamp("Repository details fetched", await _get_repo(repo))


# =============================================================================
# WEATHER & TIME
# =============================================================================
@mcp.tool()
async def get_weather(location: str) -> str:
    """
    Get weather forecast for a location.
    
    Args:
        location: City name (e.g., "Tokyo", "New York")
    """
    from .tools.weather import get_weather as _weather
    return _with_fetch_timestamp("Forecast fetched", await _weather(location))


@mcp.tool()
async def get_current_datetime(location: str = "local") -> str:
    """Get the current local date/time and UTC timestamp from the system clock.

    Use for direct date/time questions. Fresh search and news results already
    include a timestamp. Defaults to the server's local timezone; pass a city
    or IANA timezone (such as Asia/Kolkata) for another location. No network call.
    """
    from .tools.time import get_current_datetime as _get_datetime
    return _get_datetime(location)


# =============================================================================
# Server Entry Point
# =============================================================================
def main():
    """Run the MCP server using STDIO transport."""
    logger.info("Starting MCP Internet Server v3.0...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
