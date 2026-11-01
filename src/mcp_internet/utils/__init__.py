"""Utility modules for MCP Internet Server."""

from .http_client import fetch_url, fetch_json, fetch_multiple

__all__ = [
    "fetch_url",
    "fetch_json",
    "fetch_multiple",
]
