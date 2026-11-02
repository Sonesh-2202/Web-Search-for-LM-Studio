from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from bs4 import BeautifulSoup

from mcp_internet.tools import search
from mcp_internet.tools.webpage import clean_text, read_webpage
from mcp_internet.utils import extractors, http_client


class FixedDateTime:
    @classmethod
    def now(cls, tz=None):
        value = datetime(2026, 11, 1, 12, 30, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value


def test_query_intent_date_context():
    now = FixedDateTime.now()
    assert "as of November 01, 2026" in search._query_with_date_context("Jailer 2", now)
    assert search._time_filter_for_query("latest Jailer 2") == "m"
    assert search._time_filter_for_query("Jailer 2") == "m"
    assert search._query_with_date_context("What is Windows 11?", now) == "What is Windows 11?"
    assert not search._event_status_query("What is Windows 11?")
    assert search._time_filter_for_query("upcoming film release") is None
    assert search._time_filter_for_query("Jailer 3 2028 release") is None
    historical = "What happened to Jailer 2 in 2023?"
    assert search._query_with_date_context(historical, now) == historical
    assert search._time_filter_for_query(historical) is None
    matchup = "Tell me about India vs New Zealand"
    assert search._is_sports_matchup(matchup)
    assert "as of November 01, 2026" in search._query_with_date_context(matchup, now)
    assert search._time_filter_for_query(matchup, now) == "m"
    assert not search._is_sports_matchup("Compare India vs New Zealand population")
    assert (
        search._query_with_date_context("How does photosynthesis work?", now)
        == "How does photosynthesis work?"
    )


@pytest.mark.asyncio
async def test_sports_matchup_search_is_direct_and_bounded(monkeypatch):
    monkeypatch.setattr(search, "datetime", FixedDateTime)
    captured = {}

    async def fake_search(query, count, timelimit=None):
        captured.update(query=query, count=count, timelimit=timelimit)
        return [
            {"title": f"Source {i}", "href": f"https://source{i}.example/story", "body": "Result"}
            for i in range(4)
        ]

    async def fake_extract(result, max_chars=1800):
        return f"Title {result['title']}\nURL: {result['href']}\nPage date: 2026-10-31\nResult reported."

    monkeypatch.setattr(search, "_search", fake_search)
    monkeypatch.setattr(search, "_extract_source", fake_extract)
    result = await search.smart_search("Tell me about India vs New Zealand")
    assert captured["timelimit"] == "m"
    assert captured["count"] == 4
    assert "latest match results series schedule fixtures" in captured["query"]
    assert "Likely intent: current or most recent head-to-head sports results" in result
    assert "cite the returned source URLs" in result
    assert result.count("Page date:") == 2


@pytest.mark.asyncio
async def test_sports_matchup_without_results_says_unverified(monkeypatch):
    monkeypatch.setattr(search, "datetime", FixedDateTime)

    async def no_results(*args, **kwargs):
        return []

    monkeypatch.setattr(search, "_search", no_results)
    result = await search.smart_search("India vs New Zealand")
    assert "No results found" in result
    assert "No current result or fixture was verified" in result


@pytest.mark.asyncio
async def test_jailer_event_status_unverified_without_post_date_evidence(monkeypatch):
    monkeypatch.setattr(search, "datetime", FixedDateTime)

    async def old_announcement_only(*args, **kwargs):
        return [{
            "title": "Jailer 2 release planned for July 2025",
            "href": "https://example.test/announcement",
            "body": "The film was scheduled to release in July 2025.",
        }]

    monkeypatch.setattr(search, "_search", old_announcement_only)
    result = await search.search_web("Search the web about Jailer 2 and tell me", 5)
    assert "2026-11-01T18:00:00+05:30" in result
    assert "event status: unverified" in result.lower()
    assert "july 2025" in result.lower()
    assert "it is upcoming" not in result.lower()


def test_canonical_url_strips_tracking_and_redirect():
    url = "https://www.example.com/story/?utm_source=x&b=2#section"
    assert search._canonical_url(url) == "https://example.com/story?b=2"
    assert search._canonical_url("") == ""


@pytest.mark.asyncio
async def test_recent_hits_avoid_slower_broadened_fallback(monkeypatch):
    calls = []

    async def ddgs(query, count, timelimit=None):
        calls.append(timelimit)
        if timelimit:
            return [{"title": "Fresh", "href": "https://x.test/a?utm_source=1"}]
        raise AssertionError("Do not fetch a broad search when recent hits exist")

    monkeypatch.setattr(search, "search_with_ddgs", ddgs)
    results = await search._search("topic", 5, "m")
    assert calls == ["m"]
    assert len(results) == 1
    assert "recency window requested" in results[0]["_provenance"]


@pytest.mark.asyncio
async def test_html_fallback_says_date_filter_is_unavailable(monkeypatch):
    async def no_ddgs(*args, **kwargs):
        return []

    async def html_results(*args, **kwargs):
        return [{"title": "Candidate", "href": "https://candidate.example/"}]

    monkeypatch.setattr(search, "search_with_ddgs", no_ddgs)
    monkeypatch.setattr(search, "search_duckduckgo_html", html_results)
    results = await search._search("latest candidate", 3, "m")
    assert "cannot honor requested date filter" in results[0]["_provenance"]


@pytest.mark.asyncio
async def test_rate_limiter_sleeps_concurrently_for_separate_hosts(monkeypatch):
    import asyncio

    limiter = http_client.DomainRateLimiter(10)
    limiter._last_request = {"a.example": 1.0, "b.example": 1.0}
    monkeypatch.setattr(http_client.time, "monotonic", lambda: 1.05)
    active = 0
    max_active = 0
    original_sleep = asyncio.sleep

    async def fake_sleep(delay):
        nonlocal active, max_active
        active += 1
        max_active = max(active, max_active)
        await original_sleep(0)
        active -= 1

    monkeypatch.setattr(http_client.asyncio, "sleep", fake_sleep)
    await asyncio.gather(
        limiter.wait("https://a.example"), limiter.wait("https://b.example")
    )
    assert max_active == 2


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://127.0.0.1/a",
        "http://10.0.0.2/",
        "http://169.254.1.1/",
        "http://[::1]/",
        "http://[fc00::1]/",
        "http://user:pass@example.com/",
        "http://localhost/",
    ],
)
def test_unsafe_urls_rejected(url):
    with pytest.raises(http_client.UnsafeURLError):
        http_client._validate_url(url)


def test_public_https_url_passes_validation():
    assert http_client._validate_url("https://example.com/path")[1] == "example.com"


@pytest.mark.asyncio
async def test_hostname_resolving_private_rejected(monkeypatch):
    def resolve(*args, **kwargs):
        return [(2, 1, 6, "", ("192.168.1.9", 443))]

    monkeypatch.setattr(http_client.socket, "getaddrinfo", resolve)
    with pytest.raises(http_client.UnsafeURLError, match="non-public"):
        await http_client._validate_destination("public-looking.example", 443)


@pytest.mark.asyncio
async def test_hostname_with_any_private_answer_is_rejected(monkeypatch):
    def resolve(*args, **kwargs):
        return [
            (2, 1, 6, "", ("93.184.216.34", 443)),
            (2, 1, 6, "", ("10.0.0.8", 443)),
        ]

    monkeypatch.setattr(http_client.socket, "getaddrinfo", resolve)
    with pytest.raises(http_client.UnsafeURLError, match="non-public"):
        await http_client._validate_destination("mixed.example", 443)


@pytest.mark.asyncio
async def test_pinned_backend_connects_to_validated_ip(monkeypatch):
    backend = http_client._PinnedNetworkBackend()
    backend.pin("public.example", 443, ("93.184.216.34",))
    observed = {}

    async def connect(_self, host, port, **kwargs):
        observed.update(host=host, port=port)
        return "connected"

    monkeypatch.setattr(http_client.AnyIOBackend, "connect_tcp", connect)
    result = await backend.connect_tcp("public.example", 443)
    assert result == "connected"
    assert observed == {"host": "93.184.216.34", "port": 443}


@pytest.mark.asyncio
async def test_pinned_backend_falls_back_only_to_validated_addresses(monkeypatch):
    backend = http_client._PinnedNetworkBackend()
    backend.pin("public.example", 443, ("93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"))
    attempted = []

    async def connect(_self, host, port, **kwargs):
        attempted.append(host)
        if len(attempted) == 1:
            raise http_client.httpcore.ConnectError("unreachable")
        return "connected"

    monkeypatch.setattr(http_client.AnyIOBackend, "connect_tcp", connect)
    assert await backend.connect_tcp("public.example", 443) == "connected"
    assert attempted == ["93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"]


@pytest.mark.asyncio
async def test_redirect_revalidates_private_target(monkeypatch):
    seen = []

    async def validate(host, port):
        seen.append(host)
        if host == "private-redirect.example":
            raise http_client.UnsafeURLError("private redirect destination")

    monkeypatch.setattr(http_client, "_validate_destination", validate)
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(
        302, headers={"location": "http://private-redirect.example/secret"}, request=request
    )

    class FakeClient:
        def stream(self, *args, **kwargs):
            class Context:
                async def __aenter__(self):
                    return response

                async def __aexit__(self, *args):
                    pass

            return Context()

    monkeypatch.setattr(http_client, "get_client", AsyncMock(return_value=FakeClient()))
    with pytest.raises(http_client.UnsafeURLError):
        await http_client._request_bytes(
            "https://example.com",
            headers=None,
            timeout=1,
            limit=100,
            accepted_types=("text/html",),
            retries=0,
            rate_limit=False,
        )
    assert seen == ["example.com", "private-redirect.example"]


@pytest.mark.asyncio
async def test_request_pins_validated_destination_before_connect(monkeypatch):
    pins = []

    async def validate(host, port):
        return ("93.184.216.34",)

    class FakeClient:
        def pin_destination(self, host, port, addresses):
            pins.append((host, port, addresses))

        def stream(self, *args, **kwargs):
            response = httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b"<p>ok</p>",
                request=httpx.Request("GET", "https://example.com"),
            )

            class Context:
                async def __aenter__(self):
                    return response

                async def __aexit__(self, *args):
                    pass

            return Context()

    monkeypatch.setattr(http_client, "_validate_destination", validate)
    monkeypatch.setattr(http_client, "get_client", AsyncMock(return_value=FakeClient()))
    await http_client._request_bytes(
        "https://example.com",
        headers=None,
        timeout=1,
        limit=100,
        accepted_types=("text/html",),
        retries=0,
        rate_limit=False,
    )
    assert pins == [("example.com", 443, ("93.184.216.34",))]


@pytest.mark.asyncio
async def test_stream_size_limit(monkeypatch):
    async def validate(host, port):
        pass

    monkeypatch.setattr(http_client, "_validate_destination", validate)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/html"}, content=b"x" * 20
        )
    )
    client = httpx.AsyncClient(transport=transport)
    monkeypatch.setattr(http_client, "get_client", AsyncMock(return_value=client))
    assert (
        await http_client.fetch_url(
            "https://example.com", max_bytes=10, retries=0, rate_limit=False
        )
        is None
    )
    await client.aclose()


def test_jsonld_graph_arrays_and_article_dates():
    html = """<script type="application/ld+json">bad json</script><script type="application/ld+json">{"@graph":[{"@type":["NewsArticle"],"headline":"Story","datePublished":"2026-10-30","dateModified":"2026-10-31"},{"@type":"WebPage","name":"Page"}]}</script>"""
    soup = BeautifulSoup(html, "lxml")
    items = extractors.extract_json_ld(soup)
    assert len(items) == 2
    assert extractors.extract_page_dates(soup) == ("2026-10-30", "2026-10-31")


def test_film_release_date_not_page_publication_date():
    html = """<script type="application/ld+json">{"@type":"Movie","name":"Film","datePublished":"2020-01-01"}</script>"""
    data = extractors.extract_structured_data(
        html, "https://www.imdb.com/title/tt0000001/"
    )
    assert data.get("date_published") == "2020-01-01"
    assert "publication_date" not in data


def test_nested_article_time_and_host_matching():
    soup = BeautifulSoup(
        '<article><div itemtype="https://schema.org/NewsArticle"><time datetime="2026-10-31"></time></div></article>',
        "lxml",
    )
    assert extractors.extract_page_dates(soup)[0] == "2026-10-31"
    assert (
        extractors.get_extractor("https://notimdb.com/title/")
        is extractors.extract_generic
    )
    assert (
        extractors.get_extractor("https://m.imdb.com/title/") is extractors.extract_imdb
    )


def test_clean_text_preserves_paragraphs():
    assert (
        clean_text("Heading\n\nFirst paragraph\nline two\n\nSecond paragraph")
        == "Heading\n\nFirst paragraph\nline two\n\nSecond paragraph"
    )


@pytest.mark.asyncio
async def test_read_webpage_strict_output_limit(monkeypatch):
    html = (
        "<html><head><title>Example</title><meta name='description' content='desc'></head><body><main><h1>Heading</h1><p>"
        + "words " * 500
        + "</p></main></body></html>"
    )
    monkeypatch.setattr(
        "mcp_internet.tools.webpage.fetch_url", AsyncMock(return_value=html)
    )
    assert len(await read_webpage("https://example.com", 100)) <= 100


def test_youtube_pairs_title_and_upload_metadata():
    from mcp_internet.tools.youtube import _video_renderers, extract_video_id

    data = {
        "videoRenderer": {
            "videoId": "abcdefghijk",
            "title": {"runs": [{"text": "Correct title"}]},
            "publishedTimeText": {"simpleText": "2 days ago"},
        }
    }
    renderer = list(_video_renderers(data))[0]
    assert renderer["title"]["runs"][0]["text"] == "Correct title"
    for path in (
        "watch?v=abcdefghijk",
        "shorts/abcdefghijk",
        "embed/abcdefghijk",
        "live/abcdefghijk",
    ):
        assert extract_video_id("https://www.youtube.com/" + path) == "abcdefghijk"
    assert extract_video_id("https://youtu.be/abcdefghijk") == "abcdefghijk"


@pytest.mark.asyncio
async def test_timezone_iana_support():
    from mcp_internet.tools.time import find_timezone, get_current_datetime

    assert find_timezone("Asia/Kolkata") == "Asia/Kolkata"
    assert "UTC:" in get_current_datetime("Asia/Kolkata")


@pytest.mark.asyncio
async def test_reddit_latest_mode_has_content_timestamp(monkeypatch):
    from mcp_internet.tools import reddit

    captured = {}

    async def fake_fetch(url):
        captured["url"] = url
        return {
            "data": {
                "children": [
                    {
                        "data": {
                            "title": "Post",
                            "created_utc": 1793534400,
                            "permalink": "/r/python/a",
                        }
                    }
                ]
            }
        }

    monkeypatch.setattr(reddit, "fetch_json", fake_fetch)
    text = await reddit.search_reddit("latest python", num_results=2, sort="new")
    assert "sort=new" in captured["url"]
    assert "Created:" in text and "UTC" in text


@pytest.mark.asyncio
async def test_github_updated_sort_timestamp(monkeypatch):
    from mcp_internet.tools import github

    captured = {}

    async def fake_fetch(url):
        captured["url"] = url
        return {"items": [{"full_name": "a/b", "updated_at": "2026-10-31T08:00:00Z"}]}

    monkeypatch.setattr(github, "fetch_json", fake_fetch)
    text = await github.search_github("latest python", sort="updated")
    assert "sort=updated" in captured["url"]
    assert "2026-10-31T08:00:00Z" in text


@pytest.mark.asyncio
async def test_news_rss_fallback_uses_search_locale(monkeypatch):
    from mcp_internet.tools import news

    captured = {}
    monkeypatch.setenv("MCP_SEARCH_REGION", "uk-en")

    async def fake_fetch(url):
        captured["url"] = url
        return """<rss><channel><item><title>Headline</title><link>https://news.example/story</link><pubDate>Sat, 31 Oct 2026 10:00:00 GMT</pubDate><source>Publisher</source></item></channel></rss>"""

    monkeypatch.setattr(news, "fetch_url", fake_fetch)
    text = await news.get_news_rss("local topic", 1)
    assert (
        "hl=en-uk" in captured["url"]
        and "gl=UK" in captured["url"]
        and "ceid=UK:en" in captured["url"]
    )
    assert "Publisher" in text and "https://news.example/story" in text


def test_table_extraction_has_hard_row_cap():
    rows = "".join(f"<tr><td>row{i}</td></tr>" for i in range(100))
    soup = BeautifulSoup(f"<table><tr><th>Header</th></tr>{rows}", "lxml")
    tables = extractors.extract_html_tables(soup, max_rows=5)
    assert len(tables[0]["rows"]) == 5


def test_mcp_startup_registers_expected_tools_and_product_name():
    from mcp_internet import PRODUCT_NAME
    from mcp_internet.server import mcp

    assert PRODUCT_NAME == "Web Search for LM Studio LLMS"
    assert mcp.name == PRODUCT_NAME
    assert {tool.name for tool in mcp._tool_manager.list_tools()} == {
        "search_web", "smart_search", "deep_search", "read_webpage", "read_pdf",
        "get_news", "search_reddit", "search_youtube", "get_video_info",
        "search_github", "get_repo_info", "get_weather", "get_current_datetime",
    }


@pytest.mark.asyncio
async def test_search_source_count_bounds_are_reported(monkeypatch):
    async def unexpected_search(*args, **kwargs):
        raise AssertionError("invalid bounds should be rejected before searching")

    monkeypatch.setattr(search, "_search", unexpected_search)
    assert "between 1 and 8" in await search.deep_search("topic", 9)
    assert "between 1 and 8" in await search.smart_search("topic", 0)
