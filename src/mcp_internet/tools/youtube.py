"""YouTube public page search and video metadata extraction."""

import json
import logging
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from ..utils.http_client import fetch_url

logger = logging.getLogger(__name__)
_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")


def extract_video_id(url: str) -> str | None:
    match = re.search(
        r"(?:youtube\.com/(?:watch\?.*?v=|embed/|shorts/|live/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})",
        url,
    )
    return match.group(1) if match else None


def _balanced_json(html: str, marker: str):
    pos = html.find(marker)
    start = html.find("{", pos + len(marker)) if pos >= 0 else -1
    if start < 0:
        return None
    depth, quoted, escaped = 0, False, False
    for end in range(start, len(html)):
        char = html[end]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : end + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _video_renderers(value):
    if isinstance(value, dict):
        item = value.get("videoRenderer")
        if isinstance(item, dict):
            yield item
        for child in value.values():
            yield from _video_renderers(child)
    elif isinstance(value, list):
        for child in value:
            yield from _video_renderers(child)


async def search_youtube(query: str, num_results: int = 5) -> str:
    if (
        not query.strip()
        or len(query) > 500
        or not isinstance(num_results, int)
        or isinstance(num_results, bool)
        or num_results < 1
    ):
        return "❌ Error: query must be 1-500 characters and num_results must be 1-10."
    num_results = min(num_results, 10)
    html = await fetch_url(
        f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    )
    if not html:
        return f"❌ Error: Unable to search YouTube for '{query}'."
    data = _balanced_json(html, "ytInitialData =")
    results, seen = [], set()
    for renderer in _video_renderers(data) if data else []:
        video_id = renderer.get("videoId", "")
        if not _VIDEO_ID.fullmatch(video_id) or video_id in seen:
            continue
        seen.add(video_id)
        title_data = renderer.get("title", {})
        title = "".join(
            run.get("text", "") for run in title_data.get("runs", [])
        ) or title_data.get("simpleText", "Unknown title")
        uploaded = renderer.get("publishedTimeText", {}).get("simpleText", "")
        results.append((title, video_id, uploaded))
        if len(results) >= num_results:
            break
    if not results:
        return f"No paired video results could be parsed for: {query}. YouTube may have changed its page format; upload dates and result ordering cannot be verified from this response."
    lines = [
        f"YouTube search results for: {query}",
        "Upload time is supplied by YouTube when available; retrieval time is reported separately by the server.",
    ]
    for index, (title, video_id, uploaded) in enumerate(results, 1):
        lines.append(
            f"{index}. {title}\nURL: https://www.youtube.com/watch?v={video_id}\nUploaded: {uploaded or 'not provided'}"
        )
    return "\n\n".join(lines)


async def get_video_info(url: str) -> str:
    video_id = url if _VIDEO_ID.fullmatch(url) else extract_video_id(url)
    if not video_id:
        return "❌ Error: Invalid YouTube URL or video ID."
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    html = await fetch_url(video_url)
    if not html:
        return f"❌ Error: Unable to fetch video info for {video_id}."
    try:
        data = _balanced_json(html, "ytInitialPlayerResponse =")
        details = data.get("videoDetails", {}) if isinstance(data, dict) else {}
        soup = BeautifulSoup(html, "lxml")
        upload = ""
        for meta in soup.find_all("meta", attrs={"itemprop": "uploadDate"}):
            upload = meta.get("content", "")
            if upload:
                break
        title = details.get("title", "Unknown title")
        description = details.get("shortDescription", "No description")[:500]
        views = details.get("viewCount", "Unknown")
        if str(views).isdigit():
            views = f"{int(views):,}"
        return f"🎬 {title}\nURL: {video_url}\nChannel: {details.get('author', 'Unknown')}\nViews: {views}\nUploaded: {upload or 'not provided'}\n\n{description}"
    except Exception as exc:
        logger.warning("Unable to parse YouTube page (%s)", type(exc).__name__)
        return "❌ Error: Unable to parse video information."
