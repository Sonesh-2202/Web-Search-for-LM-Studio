# MCP Internet

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/protocol-MCP-green)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

An open-source Model Context Protocol server that gives LM Studio and other MCP clients tools for fresh web search, source-page reading, news, weather, and selected public data. It uses the local machine clock and includes a compact retrieval timestamp in research results, so a model can reason about “today” without a separate clock call on every question.

Search results are evidence leads, not guaranteed truth. The server returns source URLs and page content when a site allows access; the model should cite those sources and say when evidence is missing or contradictory. See the [LM Studio prompt template](LM_STUDIO_PROMPT.md) for recommended tool-use instructions.

## Features

- Fresh metasearch for each search request; search answers are not served from a local cache.
- `smart_search` and `deep_search` fetch selected pages in parallel and return their URLs, page content, available publication metadata, and retrieval time.
- Time-sensitive queries include the current month and year. Explicitly recent queries can use search-engine date filters; upcoming schedules avoid narrow date filters so older announcements remain discoverable.
- Generic extraction for page text, JSON-LD, OpenGraph metadata, publication/update dates, and HTML tables, with additional parsers for selected domains.
- Thirteen focused MCP tools, exposed over stdio for local clients.
- No search API key is required by default. Public search engines and websites can rate-limit or change their pages.

## Tools

| Tool | Use it for |
|---|---|
| `smart_search` | Fresh search plus reading a few sources; recommended for factual questions. |
| `deep_search` | Broader search and source reading. |
| `search_web` | Finding links and snippets; optionally extracts pages. |
| `read_webpage` | Reading a URL supplied by the user. |
| `read_pdf` | Extracting text from a PDF URL (install the `pdf` extra). |
| `get_news` | Current headlines for a topic. |
| `search_reddit` | Finding Reddit posts. |
| `search_youtube` | Finding YouTube videos. |
| `get_video_info` | Reading metadata for a YouTube URL or video ID. |
| `search_github` | Searching public GitHub repositories. |
| `get_repo_info` | Reading public GitHub repository details. |
| `get_weather` | Current forecast data for a location. |
| `get_current_datetime` | Local/system time or a supported city/IANA timezone. |

## Install

Requirements: Python 3.10 or later and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Sonesh-2202/mcp-internet.git
cd mcp-internet
uv sync
```

For PDF support:

```bash
uv sync --extra pdf
```

## Configure LM Studio

Add an entry to LM Studio's `mcp.json`, replacing the example path with the absolute path to this checkout. Keep the outer `mcpServers` object if the file already has other servers.

```json
{
  "mcpServers": {
    "mcp-internet": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "C:/path/to/mcp-internet",
        "mcp-internet"
      ],
      "cwd": "C:/path/to/mcp-internet"
    }
  }
}
```

Restart or refresh MCP servers in LM Studio. For platform-specific examples, see the [multi-platform guide](MULTI_PLATFORM_GUIDE.md).

## Search behavior and accuracy

For a current factual question, the model should call `smart_search` before answering. It searches using the current date context, reads selected pages, and returns a retrieval timestamp. The timestamp means “fetched at”; it does **not** mean that every result was published or updated then. When available, page publication and update dates are labeled separately.

For release dates, schedules, and other events that may have changed, use evidence published after the scheduled date to decide whether the event actually happened. If only older announcements are available, report what was scheduled at the time and say the outcome could not be verified. Prefer official announcements for plans and independent current reporting for what happened. Cite only URLs returned by the tools; never turn a search snippet or an old prediction into a confirmed fact.

Search uses the `ddgs` metasearch library with automatic backend selection by default, with DuckDuckGo HTML as a fallback. Set `MCP_SEARCH_REGION` (default `in-en`) to change the search region, for example `us-en` or `uk-en`. `MCP_SEARCH_BACKENDS` can override the DDGS backend, for example `bing,google`; backend availability depends on network and provider behavior.

No scraper can guarantee that a page is accessible or that a search engine ranks the best sources first. Some pages block automated requests, hide content behind scripts/paywalls, or omit publication dates. If source pages cannot be fetched, the result says to treat snippets as leads rather than verified evidence.

## System prompt

For LM Studio, copy the instructions from [LM_STUDIO_PROMPT.md](LM_STUDIO_PROMPT.md). It directs the model to search before factual answers, distinguish event dates from fetch dates, use post-event evidence for release status, and disclose uncertainty instead of guessing.

## Development

The MCP server runs over stdio. The command configured above is equivalent to:

```bash
uv run mcp-internet
```

Source code is under `src/mcp_internet/`. Tool registration is in `src/mcp_internet/server.py`; retrieval and extraction are under `tools/` and `utils/`.

## License

MIT. See [LICENSE](LICENSE).
