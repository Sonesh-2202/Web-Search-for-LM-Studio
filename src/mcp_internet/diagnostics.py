"""Local setup diagnostics for the mcp-internet command-line package."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import sys


def _check(label: str, ok: bool, detail: str) -> bool:
    print(f"{'OK' if ok else 'MISSING'}  {label}: {detail}")
    return ok


def _info(label: str, enabled: bool, detail: str) -> None:
    print(f"{'OK' if enabled else 'OPTIONAL'}  {label}: {detail}")


def main() -> int:
    """Report runtime, dependency, and search configuration status."""
    print("Web Search for LM Studio LLMS — setup diagnostics\n")
    healthy = True
    healthy &= _check("Python", sys.version_info >= (3, 10), sys.version.split()[0] + " (requires 3.10+)")

    for module, distribution in (
        ("mcp", "mcp"), ("httpx", "httpx"), ("bs4", "beautifulsoup4"),
        ("lxml", "lxml"), ("ddgs", "ddgs"),
    ):
        installed = importlib.util.find_spec(module) is not None
        try:
            version = importlib.metadata.version(distribution) if installed else "not installed"
        except importlib.metadata.PackageNotFoundError:
            version = "installed, version unavailable"
        healthy &= _check(distribution, installed, version)

    region = os.environ.get("MCP_SEARCH_REGION", "in-en")
    backends = os.environ.get("MCP_SEARCH_BACKENDS", "auto")
    healthy &= _check("Search region", bool(region), region or "empty; set MCP_SEARCH_REGION")
    _check("Search backend", bool(backends), backends or "empty; set MCP_SEARCH_BACKENDS")
    pdf_enabled = importlib.util.find_spec("pdfplumber") is not None
    _info("PDF extraction", pdf_enabled,
          "enabled" if pdf_enabled else "install with: uv sync --extra pdf")
    print("\nNetwork access is not tested by this local check. Start the MCP server with `mcp-internet`.")
    if not healthy:
        print("\nFix missing requirements with `uv sync` in the project checkout.")
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
