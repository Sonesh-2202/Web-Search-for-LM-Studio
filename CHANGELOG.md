# Changelog

## Unreleased

- Added `compare_sources` for bounded, side-by-side reading of webpages and PDFs.
- Added per-call search region, date-range, domain, and safe-search filters.
- Added `mcp-internet-doctor` for offline runtime and configuration diagnostics.

## [3.0.0] - 2026-11-02

This source version provides a local stdio MCP server with focused web research and public information tools.

- Added intent-aware search context and retrieval timestamps.
- Added compact and deeper source-reading search workflows.
- Added structured page metadata, publication/update dates when available, and bounded extraction.
- Added private-address URL checks with DNS-to-connection address pinning, redirect revalidation, response limits, timeouts, and per-domain rate limiting.
- Added offline tests, cross-platform CI, and contributor/security guidance.

Search backends and source sites can rate-limit requests or change their response formats. The server reports retrieval time and available source metadata; it does not guarantee that a source is current or correct.
