"""Fresh DuckDuckGo search and evidence extraction for MCP tools."""

import asyncio
import logging
import os
import re
from datetime import datetime
from urllib.parse import quote_plus, unquote

from bs4 import BeautifulSoup

from ..utils.http_client import fetch_url

logger = logging.getLogger(__name__)

_TIME_SENSITIVE_RE = re.compile(
    r"\b(latest|newest|current|currently|today|tonight|now|recent|recently|"
    r"breaking|news|upcoming|future|released?|release date|box office|"
    r"hit (?:theatres|theaters)|in cinemas|streaming|available now|"
    r"this (?:week|month|year)|next (?:week|month|year)|yesterday|ytd|as of)\b",
    re.IGNORECASE,
)
_DAY_LIMIT_RE = re.compile(r"\b(today|tonight|breaking|last 24 hours?)\b", re.IGNORECASE)
_WEEK_LIMIT_RE = re.compile(r"\b(news|recent|recently|this week)\b", re.IGNORECASE)
_SKIP_PAGE_RE = re.compile(r"\.(?:pdf|zip|exe)(?:$|[?#])|youtube\.com/watch|youtu\.be/", re.IGNORECASE)
_INTERNATIONAL_TEAMS = (
    "india", "new zealand", "australia", "england", "pakistan", "south africa",
    "sri lanka", "bangladesh", "west indies", "afghanistan", "ireland", "zimbabwe",
)
_COUNTRY_COMPARISON_RE = re.compile(
    r"\b(compare|comparison|population|geography|demographics?|econom(?:y|ic)|gdp|culture|history)\b",
    re.IGNORECASE,
)


def _query_with_date_context(query: str, now: datetime) -> str:
    """Add date context only for time-sensitive intent, preserving the topic."""
    as_of = now.strftime("%B %d, %Y")
    if _is_historical_query(query) or not _is_time_sensitive_query(query):
        return query
    return f"{query} as of {as_of}"


def _is_historical_query(query: str) -> bool:
    return bool(re.search(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b|\b(?:in|during|on|from)\s+(?:19|20)\d{2}\b|\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}?,?\s+(?:19|20)\d{2}\b|\b(?:history|historical|original|when did)\b", query, re.IGNORECASE))


def _is_time_sensitive_query(query: str) -> bool:
    # A bare named film/sequel is commonly a request for current release/status
    # information. Timeless general subjects remain untouched.
    return bool(_TIME_SENSITIVE_RE.search(query) or _event_status_query(query) or _is_sports_matchup(query))


def _is_sports_matchup(query: str) -> bool:
    """Treat a terse international team matchup as current sports intent."""
    if _COUNTRY_COMPARISON_RE.search(query) or not re.search(r"\b(?:vs\.?|versus)\b", query, re.IGNORECASE):
        return False
    teams = [name for name in _INTERNATIONAL_TEAMS if re.search(rf"\b{re.escape(name)}\b", query, re.IGNORECASE)]
    return len(teams) >= 2 and not _is_historical_query(query)


def _event_status_query(query: str) -> bool:
    event_terms = r"\b(?:season\s+\d+|sequel\b|launch\b|release\b|festival\b|tournament\b|concert\b|event\b|premiere\b|scheduled\b|planned\b|upcoming\b|box office\b|streaming\b)"
    numbered_title = r"\b[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)*\s+[2-9]\b"
    return bool(re.search(event_terms, query, re.IGNORECASE) or re.search(numbered_title, query)) and not _is_historical_query(query)


def _search_timestamp(now: datetime) -> str:
    return f"{now.isoformat(timespec='seconds')} (server retrieval time; UTC offset {now.strftime('%z')})"


def _time_filter_for_query(query: str, now: datetime | None = None) -> str | None:
    """Apply a narrow recency filter only when the wording asks for it."""
    # Upcoming schedules can be announced months or years in advance; a
    # one-month search window would hide the very evidence the user needs.
    if re.search(r"\b(upcoming|future|scheduled|expected|planned)\b", query, re.IGNORECASE):
        return None
    if _is_historical_query(query):
        return None
    year = re.search(r"\b(20\d{2})\b", query)
    if year and int(year.group(1)) > (now or datetime.now().astimezone()).year:
        return None
    if _DAY_LIMIT_RE.search(query):
        return "d"
    if _WEEK_LIMIT_RE.search(query):
        return "w"
    if re.search(r"\b(latest|newest|current|currently|now|recent|recently|released?|release date|box office|streaming|available now)\b", query, re.IGNORECASE):
        return "m"
    if _event_status_query(query) or _is_sports_matchup(query):
        return "m"
    return None


def extract_url_from_ddg_redirect(ddg_url: str) -> str:
    """Extract the target URL from a DuckDuckGo redirect link."""
    match = re.search(r"[?&]uddg=([^&]+)", ddg_url)
    return unquote(match.group(1)) if match else ddg_url


async def search_duckduckgo_html(query: str, num_results: int = 10, retries: int = 1) -> list[dict]:
    """Search DuckDuckGo's HTML interface and parse result titles, URLs, snippets."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    for attempt in range(retries):
        html = await fetch_url(url, timeout=8.0, retries=0)
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
            logger.warning("Unable to parse DuckDuckGo results (%s)", type(e).__name__)

        if attempt + 1 < retries:
            await asyncio.sleep(0.3 * (attempt + 1))

    return []


async def search_with_ddgs(
    query: str,
    num_results: int = 10,
    timelimit: str | None = None,
    region: str | None = None,
    safesearch: str = "moderate",
) -> list[dict]:
    """Search across several engines without blocking the event loop."""
    try:
        from ddgs import DDGS

        def do_search():
            selected_region = region or os.environ.get("MCP_SEARCH_REGION", "in-en")
            backends = os.environ.get("MCP_SEARCH_BACKENDS", "auto")
            return list(DDGS(timeout=7).text(
                query,
                region=selected_region,
                safesearch=safesearch,
                timelimit=timelimit,
                max_results=num_results,
                backend=backends,
            ))

        return await asyncio.wait_for(asyncio.to_thread(do_search), timeout=8.0)
    except Exception as e:
        logger.warning("DDGS fallback error (%s)", type(e).__name__)
        return []


async def _search(
    query: str,
    num_results: int,
    timelimit: str | None = None,
    region: str | None = None,
    safesearch: str = "moderate",
) -> list[dict]:
    results = await search_with_ddgs(
        query, num_results, timelimit=timelimit, region=region, safesearch=safesearch
    )
    if timelimit and results:
        results = [
            {**item, "_provenance": f"DDGS {timelimit} recency window requested; source publication time is not independently verified"}
            for item in results
        ]
    if not results:
        logger.info("Metasearch returned no results; trying DuckDuckGo HTML")
        results = await search_duckduckgo_html(query, num_results, retries=1)
        if timelimit:
            results = [{**item, "_provenance": "DuckDuckGo HTML fallback cannot honor requested date filter; freshness unverified"} for item in results]
    unique = []
    seen = set()
    for item in results:
        key = _canonical_url(item.get("href", item.get("link", "")))
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    results = unique[:num_results]
    return results


_TIME_RANGES = {"auto": None, "day": "d", "week": "w", "month": "m", "year": "y", "any": ""}
_DOMAIN_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$", re.IGNORECASE)


def _search_options(query: str, time_range: str, include_domains: list[str] | None,
                    exclude_domains: list[str] | None) -> tuple[str, str | None]:
    """Apply explicit date and domain filters using search-engine query syntax."""
    if not isinstance(time_range, str):
        raise ValueError("time_range must be a string")
    normalized_range = time_range.strip().lower()
    if normalized_range not in _TIME_RANGES:
        raise ValueError("time_range must be one of: auto, day, week, month, year, any")
    if (include_domains is not None and not isinstance(include_domains, list)) or (
        exclude_domains is not None and not isinstance(exclude_domains, list)
    ):
        raise ValueError("include_domains and exclude_domains must be lists of hostnames")
    domains = (include_domains or []) + (exclude_domains or [])
    if len(domains) > 10:
        raise ValueError("provide no more than 10 domain filters")
    if any(not isinstance(domain, str) or not _DOMAIN_RE.fullmatch(domain.strip()) for domain in domains):
        raise ValueError("domains must be hostnames such as example.com")
    normalized_includes = [domain.strip().lower() for domain in include_domains or []]
    if len(normalized_includes) == 1:
        query += f" site:{normalized_includes[0]}"
    elif normalized_includes:
        query += " (" + " OR ".join(f"site:{domain}" for domain in normalized_includes) + ")"
    for domain in exclude_domains or []:
        query += f" -site:{domain.strip().lower()}"
    return query, _TIME_RANGES[normalized_range]


def _effective_time_range(query: str, configured: str | None, now: datetime) -> str | None:
    return _time_filter_for_query(query, now) if configured is None else configured or None


def _canonical_url(url: str) -> str:
    if not url:
        return ""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    try:
        parsed = urlsplit(extract_url_from_ddg_redirect(url))
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return ""
        host = parsed.hostname.lower().removeprefix("www.")
        path = parsed.path.rstrip("/") or "/"
        query = urlencode(sorted((k, v) for k, v in parse_qsl(parsed.query) if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}))
        return urlunsplit((parsed.scheme.lower(), host, path, query, ""))
    except Exception:
        return ""


def _fallback_warning(results: list[dict]) -> str:
    warnings = []
    if any("broadened unfiltered" in item.get("_provenance", "") for item in results):
        warnings.append("Some results came from an unfiltered broadened fallback and are not verified as recent.")
    if any("cannot honor requested date filter" in item.get("_provenance", "") for item in results):
        warnings.append("DuckDuckGo HTML fallback cannot honor the requested date filter; those results are freshness-unverified.")
    return " ".join(warnings)


def _format_result_list(results: list[dict], limit: int) -> str:
    lines = []
    for index, result in enumerate(results[:limit], 1):
        title = result.get("title", "Untitled")
        url = result.get("href", result.get("link", ""))
        snippet = result.get("body", result.get("snippet", "No snippet available"))
        lines.append(f"{index}. {title}\nURL: {url}\nSnippet: {snippet}")
        if result.get("_provenance"):
            lines[-1] += f"\nEvidence window: {result['_provenance']}"
    return "\n\n".join(lines)


async def _extract_source(result: dict, max_chars: int = 1800) -> str:
    """Fetch one result and return both extracted metadata and readable text."""
    url = result.get("href", result.get("link", ""))
    title = result.get("title", "Untitled")
    if not url or not url.startswith(("http://", "https://")) or _SKIP_PAGE_RE.search(url):
        return ""

    try:
        html = await fetch_url(url, timeout=10.0, retries=0)
        if html:
            from ..utils.extractors import (
                extract_structured_data,
                format_extracted_data,
            )

            data = extract_structured_data(html, url)
            structured = format_extracted_data(data).strip()
            has_structured_evidence = any(
                value for key, value in data.items()
                if key not in {"source", "title", "type"}
            )
            from .webpage import clean_text, extract_main_content

            soup = BeautifulSoup(html, "lxml")
            content = clean_text(extract_main_content(soup, url))
            page_title = soup.title.get_text(" ", strip=True) if soup.title else title
            sections = [f"## {page_title}\nURL: {url}"]
            if has_structured_evidence and structured:
                sections.append("### Extracted metadata\n" + structured[:1000])
            if content:
                sections.append("### Page text\n" + content[:max_chars])
            if len(sections) > 1:
                return "\n\n".join(sections)
    except Exception as e:
        logger.warning("Unable to extract search result (%s)", type(e).__name__)

    return ""


async def search_web(
    query: str, num_results: int = 10, deep_search: bool = False,
    region: str = "", time_range: str = "auto", include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None, safesearch: str = "moderate",
) -> str:
    """Perform a fresh web search and return result links with snippets.

    Set ``deep_search`` to read and extract content from up to three results.
    This tool does not reuse cached search results.
    """
    if not query.strip() or len(query) > 1000:
        return "Error: Please provide a search query."

    if not isinstance(num_results, int) or isinstance(num_results, bool) or not 1 <= num_results <= 100:
        return "Error: num_results must be between 1 and 20."
    if safesearch not in {"off", "moderate", "strict"}:
        return "Error: safesearch must be off, moderate, or strict."
    if region and not re.fullmatch(r"[a-z]{2}-[a-z]{2}", region, re.IGNORECASE):
        return "Error: region must look like en-us or in-en."
    num_results = min(num_results, 20)
    now = datetime.now().astimezone()
    search_query = _query_with_date_context(query, now)
    try:
        search_query, configured_time = _search_options(search_query, time_range, include_domains, exclude_domains)
    except ValueError as exc:
        return f"Error: {exc}."
    event_query = _event_status_query(query)
    if event_query and not _is_historical_query(query):
        search_query += " reviews results release status after scheduled date"
    sports_matchup = _is_sports_matchup(query)
    if sports_matchup:
        search_query += " latest match results series schedule fixtures"
    results = await _search(search_query, num_results, _effective_time_range(query, configured_time, now), region or None, safesearch)
    retrieval_time = _search_timestamp(now)
    if not results:
        warning = " Event status is unverified because no evidence from after the scheduled date was found." if event_query else ""
        if sports_matchup:
            warning += " No current result or fixture was verified; do not infer a score or schedule."
        return f"Search attempted: {retrieval_time}\nNo results found for: {query}. Try a different query.{warning}"

    output = [f"Search attempted: {retrieval_time}", f"Search: {query}"]
    output.append(f"Search query with time context: {search_query}")
    output.append(_format_result_list(results, num_results))
    if event_query:
        output.append("Event status: unverified. Search results and old schedules alone do not establish that a scheduled event occurred; look for dated post-event evidence before claiming completion or that it remains upcoming.")
    if sports_matchup:
        output.append("Likely intent: current or most recent head-to-head sports results and upcoming fixtures. Answer that directly, cite the returned source URLs beside scores and dates, and do not invent a score or schedule. Do not pivot to a general country comparison unless asked.")
        output.append("Sports status: treat any score or fixture as unverified unless a returned source provides dated evidence.")
    if warning := _fallback_warning(results):
        output.append("Warning: " + warning)

    if deep_search:
        pages = await asyncio.gather(*(_extract_source(result) for result in results[:3]))
        pages = [page for page in pages if page]
        if pages:
            output.append("## Extracted source content\n" + "\n\n".join(pages))
    return "\n\n".join(output)


async def smart_search(query: str, max_sources: int = 2, region: str = "", time_range: str = "auto",
                       include_domains: list[str] | None = None, exclude_domains: list[str] | None = None,
                       safesearch: str = "moderate") -> str:
    """Search fresh sources, read them, and include the current clock context."""
    return await deep_search(query, num_sources=max_sources, region=region, time_range=time_range,
                             include_domains=include_domains, exclude_domains=exclude_domains,
                             safesearch=safesearch)


async def deep_search(query: str, num_sources: int = 5, region: str = "", time_range: str = "auto",
                      include_domains: list[str] | None = None, exclude_domains: list[str] | None = None,
                      safesearch: str = "moderate") -> str:
    """Fresh multi-source research with source URLs and extracted page content."""
    if not query.strip() or len(query) > 1000:
        return "Error: Please provide a search query."

    if not isinstance(num_sources, int) or isinstance(num_sources, bool) or not 1 <= num_sources <= 8:
        return "Error: num_sources must be between 1 and 8."
    if safesearch not in {"off", "moderate", "strict"}:
        return "Error: safesearch must be off, moderate, or strict."
    if region and not re.fullmatch(r"[a-z]{2}-[a-z]{2}", region, re.IGNORECASE):
        return "Error: region must look like en-us or in-en."
    now = datetime.now().astimezone()
    search_query = _query_with_date_context(query, now)
    try:
        search_query, configured_time = _search_options(search_query, time_range, include_domains, exclude_domains)
    except ValueError as exc:
        return f"Error: {exc}."
    event_query = _event_status_query(query)
    if event_query:
        search_query += " reviews results release status after scheduled date"
    sports_matchup = _is_sports_matchup(query)
    if sports_matchup:
        search_query += " latest match results series schedule fixtures"
    clock_context = _search_timestamp(now)

    results = await _search(
        search_query,
        min(12, max(num_sources * 2, 4)),
        _effective_time_range(query, configured_time, now),
        region or None,
        safesearch,
    )
    if not results:
        status = " Event status is unverified because no post-scheduled-date evidence was found." if event_query else ""
        if sports_matchup:
            status += " No current result or fixture was verified; do not infer a score or schedule."
        return f"No results found for: {query}. Search attempted at {clock_context}.{status}"

    # Skip duplicate domains so the extracted evidence is less likely to repeat
    # the same publisher's coverage several times.
    selected = []
    seen_domains = set()
    for result in results:
        url = result.get("href", result.get("link", ""))
        if not url or _SKIP_PAGE_RE.search(url):
            continue
        domain_match = re.match(r"https?://([^/]+)", url, re.IGNORECASE)
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
    sections.append(f"Search query with time context: {search_query}")
    sections.append("## Search results\n" + _format_result_list(results, min(len(results), 8)))
    if extracted:
        sections.append("## Read source pages\n" + "\n\n".join(extracted))
    else:
        sections.append("Source pages could not be opened; use the search snippets only as leads, not as verified evidence.")
    if event_query:
        sections.append("Event status: unverified unless a fetched source provides evidence dated after the scheduled occurrence. An old announcement is evidence of a plan only.")
    if sports_matchup:
        sections.append("Likely intent: current or most recent head-to-head sports results and upcoming fixtures. Answer that directly, cite the returned source URLs beside scores and dates, and do not invent a score or schedule. Do not pivot to a general country comparison unless asked.")
        sections.append("Sports status: treat any score or fixture as unverified unless a returned source provides dated evidence.")
    if warning := _fallback_warning(results):
        sections.append("Warning: " + warning)
    return "\n\n".join(sections)
