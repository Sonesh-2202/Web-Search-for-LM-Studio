# Web Search for LM Studio LLMS: platform setup

The recommended setup is the same on Windows, macOS, and Linux: install Python 3.10+, Git, and `uv`; clone this repository; run `uv sync`; then configure LM Studio to launch the local stdio server. The server uses Python and `uv`; the LM Studio deeplink only adds configuration and does not install either runtime or this project.

For the full install, upgrade, uninstall, deeplink, and troubleshooting flow, follow the [README quick start](README.md#quick-start). For platform-specific executable paths, use forward slashes in `mcp.json`, including on Windows. For example, a Windows Python executable could be `C:/Users/you/mcp-internet/.venv/Scripts/python.exe`; macOS and Linux typically use `/path/to/mcp-internet/.venv/bin/python`.

The server runs over stdio and is launched and managed by LM Studio. Logs go to stderr. Do not start a second copy for the same LM Studio configuration.

## Optional PDF support

PDF extraction is optional. Install it in the checkout with:

```bash
uv sync --extra pdf
```

## Network and privacy

Search queries are sent to the configured DDGS search backend and may fall back to DuckDuckGo HTML. Search and reading tools fetch public result pages. Specialized tools contact Reddit, YouTube, GitHub, and Open-Meteo. The server does not intentionally log query strings or page contents. See the README for details and search limitations.
