"""Fresh DuckDuckGo search and evidence extraction for MCP tools."""

import asyncio
import logging
import os
import re
from datetime import datetime
from urllib.parse import quote_plus, unquote

from bs4 import BeautifulSoup

from ..utils.http_client import fetch_url
from .time import get_current_datetime

logger = logging.getLogger(__name__)

_TIME_SENSITIVE_RE = re.compile(
    r"\b(latest|newest|current|currently|today|tonight|now|recent|recently|"
    r"breaking|news|upcoming|future|released?|release date|box office|"
    r"hit (?:theatres|theaters)|in cinemas|streaming|available now|"
    r"this (?:week|month|year)|next (?:week|month|year)|yesterday|ytd|as of)\b",
    re.IGNORECASE,
)
_DAY_LIMIT_RE = re.compile(r"\b(today|tonight|breaking|last 24 hours?)\b", re.I)
_WEEK_LIMIT_RE = re.compile(r"\b(news|recent|recently|this week)\b", re.I)
_SKIP_PAGE_RE = re.compile(r"\.(?:pdf|zip|exe)(?:$|[?#])|youtube\.com/watch|youtu\.be/", re.I)


def _query_with_date_context(query: str, now: datetime) -> str:
    """Anchor explicitly time-sensitive searches to the current month/year."""
    if _TIME_SENSITIVE_RE.search(query):
        return f"{query} {now.strftime('%B %Y')}"
    return query


def _time_filter_for_query(query: str) -> str | None:
    """Apply a narrow recency filter only when the wording asks for it."""
    # Upcoming schedules can be announced months or years in advance; a
    # one-month search window would hide the very evidence the user needs.
    if re.search(r"\b(upcoming|future|scheduled|expected|planned)\b", query, re.I):
        return None
    if _DAY_LIMIT_RE.search(query):
        return "d"
    if _WEEK_LIMIT_RE.search(query):
        return "w"
    if re.search(r"\b(latest|newest|current|currently|now|recent|recently|released?|release date|box office|streaming|available now)\b", query, re.I):
        return "m"
    return None


def extract_url_from_ddg_redirect(ddg_url: str) -> str:
    """Extract the target URL from a DuckDuckGo redirect link."""
    match = re.search(r"[?&]uddg=([^&]+)", ddg_url)
    return unquote(match.group(1)) if match else ddg_url


async def search_duckduckgo_html(query: str, num_results: int = 10, retries: int = 3) -> list[dict]:
    """Search DuckDuckGo's HTML interface and parse result titles, URLs, snippets."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    for attempt in range(retries):
        html = await fetch_url(url, timeout=15.0, retries=1)
        if not html:
            if attempt + 1 < retries:
                await asyncio.sleep(0.3 * (attempt + 1))
            continue

        try:
            soup = BeautifulSoup(html, "lxml")
            results = []
            for result_div in soup.find_all("div", class_="result"):
                title_elem = result_div.find("a", class_="result__a")
                if not title_elem:
                    continue

                title = title_elem.get_text(" ", strip=True)
                result_url = extract_url_from_ddg_redirect(title_elem.get("href", ""))
                snippet_elem = result_div.find(class_="result__snippet")
                snippet = snippet_elem.get_text(" ", strip=True) if snippet_elem else ""
                if title and result_url.startswith(("http://", "https://")):
                    results.append({"title": title, "href": result_url, "body": snippet})
                    if len(results) >= num_results:
                        break

            if results:
                return results
        except Exception as e:
            logger.warning("Unable to parse DuckDuckGo results: %s", e)

        if attempt + 1 < retries:
            await asyncio.sleep(0.3 * (attempt + 1))

    return []


async def search_with_ddgs(
    query: str,
    num_results: int = 10,
    timelimit: str | None = None,
) -> list[dict]:
    """Search across several engines without blocking the event loop."""
    try:
        from ddgs import DDGS

        def do_search():
            region = os.environ.get("MCP_SEARCH_REGION", "in-en")
            backends = os.environ.get("MCP_SEARCH_BACKENDS", "auto")
            return list(DDGS(timeout=12).text(
                query,
                region=region,
                safesearch="moderate",
                timelimit=timelimit,
                max_results=num_results,
                backend=backends,
            ))

        return await asyncio.to_thread(do_search)
    except Exception as e:
        logger.warning("DDGS fallback error: %s", e)
        return []


async def _search(
    query: str,
    num_results: int,
    timelimit: str | None = None,
) -> list[dict]:
    results = await search_with_ddgs(query, num_results, timelimit=timelimit)
    if not results:
        logger.info("Metasearch returned no results; trying DuckDuckGo HTML")
        results = await search_duckduckgo_html(query, num_results, retries=3)

    # A recent-only search can be sparse for niche topics. Expand the window
    # while keeping the filtered matches first instead of returning nothing.
    if timelimit and len(results) < min(3, num_results):
        broader_results = await search_with_ddgs(query, num_results, timelimit=None)
        seen = {item.get("href", item.get("link", "")) for item in results}
        results.extend(
            item for item in broader_results
            if item.get("href", item.get("link", "")) not in seen
        )
        results = results[:num_results]
    return results


def _format_result_list(results: list[dict], limit: int) -> str:
    lines = []
    for index, result in enumerate(results[:limit], 1):
        title = result.get("title", "Untitled")
        url = result.get("href", result.get("link", ""))
        snippet = result.get("body", result.get("snippet", "No snippet available"))
        lines.append(f"{index}. {title}\nURL: {url}\nSnippet: {snippet}")
    return "\n\n".join(lines)


async def _extract_source(result: dict, max_chars: int = 2200) -> str:
    """Fetch one result and return structured data or readable page text."""
    url = result.get("href", result.get("link", ""))
    title = result.get("title", "Untitled")
    if not url or not url.startswith(("http://", "https://")) or _SKIP_PAGE_RE.search(url):
        return ""

    try:
        html = await fetch_url(url, timeout=15.0, retries=1)
        if html:
            from ..utils.extractors import extract_structured_data, format_extracted_data

            data = extract_structured_data(html, url)
            structured = format_extracted_data(data).strip()
            has_structured_evidence = any(
                value for key, value in data.items()
                if key not in {"source", "title", "type"}
            )
            if has_structured_evidence and structured:
                return f"## {title}\nURL: {url}\n{structured[:max_chars]}"
            from .webpage import clean_text, extract_main_content

            soup = BeautifulSoup(html, "lxml")
            content = clean_text(extract_main_content(soup, url))
            if content:
                page_title = soup.title.get_text(" ", strip=True) if soup.title else title
                return f"## {page_title}\nURL: {url}\n{content[:max_chars]}"
    except Exception as e:
        logger.warning("Unable to extract result %s: %s", url, e)

    return ""


async def search_web(query: str, num_results: int = 10, deep_search: bool = False) -> str:
    """Perform a fresh web search and return result links with snippets.

    Set ``deep_search`` to read and extract content from up to three results.
    This tool does not reuse cached search results.
    """
    if not query.strip():
        return "Error: Please provide a search query."

    num_results = max(1, min(num_results, 20))
    now = datetime.now().astimezone()
    search_query = _query_with_date_context(query, now)
    results = await _search(search_query, num_results, _time_filter_for_query(query))
    if not results:
        return f"No fresh results found for: {query}. Try a different query."

    output = [f"Search performed: {get_current_datetime()}", f"Search: {query}"]
    if search_query != query:
        output.append(f"Date-anchored query: {search_query}")
    output.append(_format_result_list(results, num_results))

    if deep_search:
        pages = await asyncio.gather(*(_extract_source(result) for result in results[:3]))
        pages = [page for page in pages if page]
        if pages:
            output.append("## Extracted source content\n" + "\n\n".join(pages))
    return "\n\n".join(output)


async def smart_search(query: str, max_sources: int = 3) -> str:
    """Search fresh sources, read them, and include the current clock context."""
    return await deep_search(query, num_sources=max_sources)


async def deep_search(query: str, num_sources: int = 5) -> str:
    """Fresh multi-source research with source URLs and extracted page content."""
    if not query.strip():
        return "Error: Please provide a search query."

    num_sources = max(1, min(num_sources, 8))
    now = datetime.now().astimezone()
    search_query = _query_with_date_context(query, now)
    clock_context = get_current_datetime()

    results = await _search(
        search_query,
        min(20, max(num_sources + 6, 12)),
        _time_filter_for_query(query),
    )
    if not results:
        return f"No fresh results found for: {query}. Search attempted at {clock_context}."

    # Skip duplicate domains so the extracted evidence is less likely to repeat
    # the same publisher's coverage several times.
    selected = []
    seen_domains = set()
    for result in results:
        url = result.get("href", result.get("link", ""))
        if not url or _SKIP_PAGE_RE.search(url):
            continue
        domain_match = re.match(r"https?://([^/]+)", url, re.I)
        domain = domain_match.group(1).lower().removeprefix("www.") if domain_match else url
        if domain in seen_domains:
            continue
        selected.append(result)
        seen_domains.add(domain)
        if len(selected) >= num_sources:
            break

    extracted = await asyncio.gather(*(_extract_source(result) for result in selected))
    extracted = [item for item in extracted if item]

    sections = [
        f"Fresh search performed at {clock_context}",
        f"Question: {query}",
    ]
    if search_query != query:
        sections.append(f"Search query anchored to the current month: {search_query}")
    sections.append("## Search results\n" + _format_result_list(results, min(len(results), 8)))
    if extracted:
        sections.append("## Read source pages\n" + "\n\n".join(extracted))
    else:
        sections.append("Source pages could not be opened; use the search snippets only as leads, not as verified evidence.")
    return "\n\n".join(sections)
