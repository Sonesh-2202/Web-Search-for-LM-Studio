# Web Search for LM Studio LLMS

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/protocol-MCP-green)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

An open-source Model Context Protocol server that gives LM Studio and other MCP clients tools for fresh web search, source-page reading, news, weather, and selected public data. The package and executable remain `mcp-internet`. It uses the local machine clock and includes a compact retrieval timestamp in research results, so a model can reason about “today” without a separate clock call on every question.

Search results are evidence leads, not guaranteed truth. The server returns source URLs and page content when a site allows access; the model should cite those sources and say when evidence is missing or contradictory. See the [LM Studio prompt template](LM_STUDIO_PROMPT.md) for recommended tool-use instructions.

## Features

- Fresh metasearch for each search request; search answers are not served from a local cache.
- `smart_search` reads up to two sources by default for a faster evidence-backed answer; `deep_search` fetches a broader set. Both return source URLs, page content when available, publication metadata, and retrieval time.
- Time-sensitive queries receive the server's current local date; timeless and explicitly historical queries are left intact. Search results include a server retrieval timestamp with UTC offset. Explicit recency requests can use search-engine date filters; upcoming schedules avoid narrow date filters so older announcements remain discoverable.
- Source results include readable page text alongside extracted JSON-LD, OpenGraph metadata, publication/update dates, and HTML tables when available, with additional parsers for selected domains.
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

## Quick start

Requirements: Python 3.10 or later, Git, and [`uv`](https://docs.astral.sh/uv/). LM Studio does not install these prerequisites when you add an MCP entry. This project currently recommends running from a local source checkout; no PyPI installation command is advertised.

```bash
git clone https://github.com/Sonesh-2202/mcp-internet.git
cd mcp-internet
uv sync
```

For PDF support:

```bash
uv sync --extra pdf
```

To upgrade an existing checkout, run `git pull` and then `uv sync`. To uninstall, remove the `mcp-internet` entry from LM Studio's `mcp.json` and delete the checkout. If you enabled PDF support, `uv sync` without `--extra pdf` removes that optional dependency from the project environment.

## Configure LM Studio

LM Studio 0.3.17 or newer supports an “Add to LM Studio” deeplink. [Add Web Search for LM Studio LLMS](lmstudio://add_mcp?name=mcp-internet&config=eyJjb21tYW5kIjoidXYiLCJhcmdzIjpbInJ1biIsIi0tZGlyZWN0b3J5IiwiQzovcGF0aC90by9tY3AtaW50ZXJuZXQiLCJtY3AtaW50ZXJuZXQiXSwiY3dkIjoiQzovcGF0aC90by9tY3AtaW50ZXJuZXQifQ%3D%3D) adds a template entry. After adding it, edit both path values to your checkout path. The deeplink only configures LM Studio; Python, `uv`, and the project dependencies must already be installed as described above.

You can also add the following entry to LM Studio's `mcp.json`, replacing the example path with the absolute path to this checkout. Keep the existing outer `mcpServers` object and other entries if the file already has other servers.

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

For a factual question, the model should call `smart_search` before answering. Time-sensitive queries include date context, selected pages are read, and the result includes a retrieval timestamp. The timestamp means “fetched at”; it does **not** mean that every result was published or updated then. When available, page publication and update dates are labeled separately.

For release dates, schedules, and other events that may have changed, use evidence published after the scheduled date to decide whether the event actually happened. If only older announcements are available, report what was scheduled at the time and say the outcome could not be verified. Prefer official announcements for plans and independent current reporting for what happened. Cite only URLs returned by the tools; never turn a search snippet or an old prediction into a confirmed fact.

Search uses the `ddgs` metasearch library with automatic backend selection by default. If it fails or yields no results, DuckDuckGo HTML is tried. When a requested date filter cannot be honored by that HTML fallback, the result is explicitly marked freshness-unverified. Set `MCP_SEARCH_REGION` (default `in-en`) to change the search region, for example `us-en` or `uk-en`. `MCP_SEARCH_BACKENDS` can override the DDGS backend, for example `bing,google`; backend availability depends on network and provider behavior.

Search requests go to the configured DDGS search backend and may fall back to DuckDuckGo HTML. Source reading contacts the result pages; specialized tools also contact Reddit, YouTube, GitHub, and Open-Meteo. Queries and URLs are sent to those external services as needed. The server does not intentionally log query strings or fetched page contents; diagnostic logs go to stderr and identify hosts or error types.

No scraper can guarantee that a page is accessible or that a search engine ranks the best sources first. Some pages block automated requests, hide content behind scripts/paywalls, or omit publication dates. If source pages cannot be fetched, the result says to treat snippets as leads rather than verified evidence.

The server cannot edit LM Studio's original prompt before generation. It supplies date and source context only after the model calls an MCP tool, so the client's system instructions must direct the model to call search before answering current factual questions. Search ranking can be stale, and a retrieval timestamp does not prove result freshness. For scheduled events whose dates have passed, the server asks for post-event evidence and labels status unverified when that evidence is absent; it cannot guarantee that hallucinations are impossible.

## System prompt

For LM Studio, copy the instructions from [LM_STUDIO_PROMPT.md](LM_STUDIO_PROMPT.md). It directs the model to search before factual answers, distinguish event dates from fetch dates, use post-event evidence for release status, and disclose uncertainty instead of guessing.

## Development

The MCP server runs over stdio. The command configured above is equivalent to:

```bash
uv run mcp-internet
```

Source code is under `src/mcp_internet/`. Tool registration is in `src/mcp_internet/server.py`; retrieval and extraction are under `tools/` and `utils/`.

Run the offline test suite and configured lint checks with:

```bash
uv run --extra dev pytest
uv run --extra dev ruff check src tests
```

The normal test suite uses mocked responses and does not require network access or credentials.

Common startup failures: if LM Studio reports that `uv` cannot be found, install `uv` or set `command` to its absolute executable path. If the server exits immediately, confirm Python 3.10+, run `uv sync` in the checkout, and verify both `--directory` and `cwd` point to the folder containing `pyproject.toml`. MCP stdio must remain attached to LM Studio; do not launch the command in a terminal and redirect its output into the MCP connection.

## License

MIT. See [LICENSE](LICENSE).
