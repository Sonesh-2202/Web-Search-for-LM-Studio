# MCP Internet Server: Technical Overview

This document describes the current implementation in `src/mcp_internet`. For installation and operating-system-specific LM Studio setup, see [MULTI_PLATFORM_GUIDE.md](MULTI_PLATFORM_GUIDE.md).

## What it does

MCP Internet Server is a Python MCP server intended to run as a local process alongside an MCP client such as LM Studio. It registers 25 tools. Search, page reading, and service-specific tools make network requests; calculation and QR generation can operate locally. Email sending is available when SMTP credentials are configured.

## Architecture

```text
LM Studio (MCP client)
        │ JSON-RPC over stdio
        ▼
src/mcp_internet/server.py  — FastMCP tool registry and entry point
        │
        ├── tools/search.py       — DuckDuckGo search and extraction flows
        ├── tools/webpage.py      — HTML page extraction
        ├── tools/*.py            — News, social, video, GitHub, weather, etc.
        └── utils/
            ├── http_client.py    — Shared async HTTP requests
            ├── extractors.py     — JSON-LD, OpenGraph, tables, domain parsers
            └── cache.py          — SQLite TTL cache with memory fallback
```

The MCP wrappers in `server.py` import tool implementations when called. Most network tools use the shared `httpx.AsyncClient` helpers. HTML tools parse responses with BeautifulSoup and lxml. Search and page results use the SQLite cache where implemented.

### Search flows

- **`smart_search`** calls the multi-source extraction flow with a default of three sources. Set `max_sources` from 1 to 8.
- **`deep_search`** uses the same flow with a default of five sources. Set `num_sources` from 1 to 8.
- Both search DuckDuckGo, using its HTML results page first and the `ddgs` package as a fallback, then read selected results and return snippets with extracted page content.
- **`search_web`** returns search results and snippets. Its `deep_search` option also fetches content from up to three results.
- **`quick_lookup`** reads the top result; **`search_site`** adds a DuckDuckGo `site:` filter.

The current deep-search implementation reads result pages sequentially. Search result order is not re-ranked by a separate authority score.

## Registered tools

| Group | Tools |
|---|---|
| Search | `smart_search`, `deep_search`, `search_web`, `quick_lookup`, `search_site` |
| Reading | `read_webpage`, `read_pdf` |
| News and social | `get_news`, `search_reddit`, `search_twitter` |
| YouTube | `search_youtube`, `get_video_info` |
| GitHub | `search_github`, `get_repo_info` |
| Weather and time | `get_weather`, `get_current_time` |
| Translation and math | `translate_text`, `calculate` |
| URL and IP | `shorten_url`, `get_my_ip`, `geolocate_ip` |
| QR codes | `generate_qr`, `generate_wifi_qr` |
| Email | `send_email` |
| Cache | `clear_cache` |

## Shared services

### HTTP client

`utils/http_client.py` provides `fetch_url`, `fetch_json`, and `fetch_multiple`. Requests use `httpx`, a shared async client, timeouts, retry handling, redirects, rotating browser-style user-agent headers, and a basic per-domain rate limiter. The functions return `None` on request failures and log details to stderr.

### Extraction

`utils/extractors.py` handles JSON-LD, OpenGraph metadata, HTML tables, and generic page metadata. It also includes Wikipedia, IMDb, and LinkedIn-specific extraction functions. `tools/webpage.py` removes common non-content elements and extracts readable page text.

### Cache

`utils/cache.py` stores string results in SQLite with category-based TTL values and falls back to a process-local memory cache if SQLite is unavailable. `clear_cache` clears all entries or a selected category when using SQLite.

## Tool data sources

Network-backed tools use public endpoints or website pages; availability and response formats can change. The principal integrations in the source include:

- DuckDuckGo search HTML and the `ddgs` fallback library
- Google News RSS, Reddit JSON endpoints, and Nitter instances for Twitter/X
- YouTube pages and public GitHub API endpoints
- Open-Meteo geocoding and weather endpoints
- Time zone lookup through Python's `zoneinfo`, with a WorldTimeAPI fallback
- A public translation endpoint in `tools/translator.py`
- Configured SMTP for `send_email`

Most tools do not need API keys. Email requires SMTP credentials supplied through `MCP_SMTP_SERVER`, `MCP_SMTP_PORT`, `MCP_SMTP_EMAIL`, and `MCP_SMTP_PASSWORD`.

## Running the server

Install the project dependencies with `uv sync`, then configure the MCP client to start the `mcp-internet` command from the project directory. A typical LM Studio entry is:

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

The server uses stdio transport. Logs go to stderr so they do not corrupt MCP messages on stdout. The console entry point is defined in `pyproject.toml`; direct module execution is also supported with `python -m mcp_internet.server` from an environment where the package is installed.

## Dependencies

The core dependencies declared in `pyproject.toml` are Python 3.10+, `mcp[cli]`, `httpx[http2]`, BeautifulSoup, lxml, `ddgs`, and `aiosqlite`. PDF extraction uses the optional `pdfplumber` dependency; install it with `uv sync --extra pdf` when needed.

## Source map

- `src/mcp_internet/server.py` — MCP tool registration and process entry point
- `src/mcp_internet/tools/` — Individual tool implementations
- `src/mcp_internet/utils/http_client.py` — Shared HTTP behavior
- `src/mcp_internet/utils/extractors.py` — Page extraction helpers
- `src/mcp_internet/utils/cache.py` — TTL cache
- `pyproject.toml` — Dependencies and `mcp-internet` command
- `LM_STUDIO_PROMPT.md` — Optional LM Studio system-prompt template
