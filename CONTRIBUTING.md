# Contributing

Thanks for helping improve Web Search for LM Studio LLMS. Small, focused pull requests are easiest to review.

## Before opening a pull request

1. Open an issue for substantial behavior changes so the expected behavior is clear.
2. Keep the default install local, key-free, and compatible with stdio MCP clients.
3. Add offline tests for search behavior, failures, bounds, or URL handling you change.
4. Update the README or technical documentation when user-visible behavior changes.
5. Run the same checks as CI:

   ```bash
   uv sync --extra dev
   uv run --extra dev pytest -q
   uv run --extra dev ruff check src tests scripts
   uv build
   ```

Do not include API keys, private URLs, fetched page contents, or personal data in logs, fixtures, or issue reports. See [SECURITY.md](SECURITY.md) to report a vulnerability privately.
