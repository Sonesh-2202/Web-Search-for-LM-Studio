# MCP Internet Server: Technical Overview

This document describes the current implementation in `src/mcp_internet`. For platform-specific setup, see [MULTI_PLATFORM_GUIDE.md](MULTI_PLATFORM_GUIDE.md).

## Purpose

MCP Internet Server is a local Python MCP server for LM Studio and other MCP clients. It exposes 13 focused tools for fresh web research, page reading, news, community/video/developer sources, weather, and time. The server uses stdio transport; logs go to stderr.

## Tool list

| Group | Tools |
|---|---|
| Search | `smart_search`, `deep_search`, `search_web` |
| Reading | `read_webpage`, `read_pdf` |
| News and community | `get_news`, `search_reddit` |
| YouTube | `search_youtube`, `get_video_info` |
| GitHub | `search_github`, `get_repo_info` |
| Weather and time | `get_weather`, `get_current_datetime` |

The server no longer registers the previous email, QR, IP, URL-shortening, translation, calculator, Twitter/Nitter, or cache-management tools.

## Search and freshness

- Use **`smart_search`** for factual answers. It performs a fresh DuckDuckGo search, fetches selected source pages concurrently, extracts page content, and returns source URLs plus the current local and UTC time.
- Use **`deep_search`** when a question needs broader source coverage. It also performs a fresh search and includes clock context.
- Use **`search_web`** for link discovery. Its snippets are leads; use `smart_search` to ground an answer in page content.
- Time-sensitive queries include the current month and year. Explicit recency requests can use a search-engine date filter. Upcoming schedules avoid narrow date filters so older announcements can still be found. Search results are not served from a cache.
- The shared `get_current_datetime` function reads the local system clock. It supports the system timezone, common city names, and IANA timezones, and returns local and UTC timestamps. Search results include this automatically, so the model need not make a second clock call for ordinary research.
- Source pages are read in parallel, with duplicate publisher domains skipped where possible. Page publication dates are included only when found in page data; the fetch timestamp is not a publication date.

The `ddgs` metasearch package is primary, with DuckDuckGo HTML as a fallback. Search ranking is provided by the search backend; the server does not independently verify ranking or claim that snippets prove a fact. If source pages cannot be opened, the response says to treat snippets as leads only.

## Other sources

- `get_news` fetches current headlines and includes the local/UTC fetch timestamp.
- `search_reddit` searches Reddit posts.
- `search_youtube` and `get_video_info` search video results and retrieve a video's metadata.
- `search_github` and `get_repo_info` use GitHub's public API.
- `get_weather` uses Open-Meteo geocoding and weather endpoints.
- `get_current_datetime(location)` reads the system clock for the local timezone, a common city, or an IANA timezone. It makes no network request.
- `read_webpage` and `read_pdf` fetch user-specified URLs and return extracted text.

Network sources are public services; their availability and response formats can change. A search timestamp records when this server fetched results, not when every source published or last updated its information.

## Implementation map

```text
LM Studio / MCP client
        │ JSON-RPC over stdio
        ▼
src/mcp_internet/server.py      FastMCP tool registry
        ├── tools/search.py       Fresh search, date anchoring, parallel extraction
        ├── tools/webpage.py      HTML reading and structured extraction
        ├── tools/news.py         News headlines
        ├── tools/reddit.py       Reddit search
        ├── tools/youtube.py      YouTube search and metadata
        ├── tools/github.py       GitHub search and repository details
        ├── tools/weather.py     Open-Meteo
        ├── tools/time.py         Local clock and timezone handling
        └── utils/
            ├── http_client.py   Shared async HTTP, retries, rate limits
            └── extractors.py    JSON-LD, OpenGraph, tables, domain parsers
```

## Run from LM Studio

Install with `uv sync`, then use the project directory in `mcp.json`:

```json
{
  "mcpServers": {
    "mcp-internet": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "D:/path/to/MCP-Internet",
        "mcp-internet"
      ],
      "cwd": "D:/path/to/MCP-Internet"
    }
  }
}
```

The project requires Python 3.10+, `mcp[cli]`, `httpx[http2]`, BeautifulSoup, lxml, and `ddgs`. PDF reading uses the optional `pdfplumber` dependency; install it with `uv sync --extra pdf`.

## LM Studio model instructions

Use [LM_STUDIO_PROMPT.md](LM_STUDIO_PROMPT.md) as the system prompt. It tells the model to search before factual answers, distinguish fetched time from publication time, cite only returned URLs, and state when the available evidence is incomplete.
