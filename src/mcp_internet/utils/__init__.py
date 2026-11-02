"""Shared utility modules for Web Search for LM Studio LLMS."""

from .http_client import fetch_json, fetch_multiple, fetch_url

__all__ = [
    "fetch_json",
    "fetch_multiple",
    "fetch_url",
]
