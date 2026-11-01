# 🌐 MCP Internet Server v3.0

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Multi-Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#)
[![LM Studio](https://img.shields.io/badge/LM%20Studio-ready-purple.svg)](https://lmstudio.ai/)

> **Give your local LLMs the power of the internet — with real data extraction, not just links!** 🚀

An open-source Model Context Protocol (MCP) server providing **25 tools** for local Large Language Models. It combines DuckDuckGo search, page extraction, result caching, and structured output so your AI can work with page content as well as links.

Seamlessly deployable across **Windows, macOS, and Linux**. **No API keys required!**

---

## 🆕 What's New in v3.0

| Feature | Before (v2.0) | After (v3.0) |
|---------|---------------|--------------|
| **Search Results** | Links + snippets | Optional page extraction from search results |
| **Tool Calls Needed** | Multiple calls | One search-and-extract call for common queries |
| **Output Format** | Plain text | Structured text and extracted tables where available |
| **Caching** | None | SQLite with TTL (30min-24h) |
| **Rate Limiting** | None | Per-domain throttling |
| **Multi-Source** | Manual per source | Extraction from selected top results |
| **Content Extraction** | Generic text only | Domain-aware (Wikipedia, IMDb, LinkedIn) |

### New Tools
- **`smart_search`** — 🌟 Searches + scrapes + extracts + formats in one call
- **`deep_search`** — Like smart_search but examines more sources
- **`clear_cache`** — Manage the result cache

---

## ✨ Key Features

- **🧠 Smart Search:** One tool call returns extracted data — movie lists, profiles, technical docs — not just links.
- **🔄 Auto-Extraction:** Automatically scrapes top results and extracts structured data (JSON-LD, tables, meta tags).
- **📊 Structured Output:** Results come as markdown tables, bullet points, and organized sections.
- **⚡ Cached Results:** Repeated queries are served from SQLite cache in milliseconds.
- **🛡️ Rate Limiting:** Per-domain request throttling prevents IP bans.
- **🔀 UA Rotation:** Pool of 7 browser user-agents for stealth.
- **🌐 Domain-Aware:** Special extractors for Wikipedia, IMDb, LinkedIn, and more.
- **🔒 Zero Config:** No API keys, no external subscriptions, no setup hassle.

---

## 🛠️ Available Tools (25 Total)

| Category | Tools |
|----------|-------|
| 🌟 **Search + Extraction** | `smart_search`, `deep_search` |
| 🔍 **Search** | `search_web`, `quick_lookup`, `search_site` |
| 📄 **Reading** | `read_webpage`, `read_pdf` |
| 📰 **News/Social** | `get_news`, `search_reddit`, `search_twitter` |
| 🎬 **YouTube** | `search_youtube`, `get_video_info` |
| 💻 **GitHub** | `search_github`, `get_repo_info` |
| 🌤️ **Info / Utils** | `get_weather`, `get_current_time`, `translate_text`, `calculate` |
| 🔗 **URLs/IP** | `shorten_url`, `get_my_ip`, `geolocate_ip` |
| 📱 **Generation** | `generate_qr`, `generate_wifi_qr`, `send_email` |
| 🗄️ **Cache** | `clear_cache` |

---

## 🚀 Quick Start

### Prerequisites
- [Python 3.10+](https://www.python.org/downloads/)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Sonesh-2202/mcp-internet.git
cd mcp-internet

# 2. Install dependencies
uv sync
```

### LM Studio Configuration

Add to your LM Studio `mcp.json` (ensure you keep the top-level `{"mcpServers": { ... }}` wrapper):

#### Using `uv` (Recommended)
```json
{
  "mcpServers": {
    "mcp-internet": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/mcp-internet",
        "mcp-internet"
      ],
      "cwd": "/absolute/path/to/mcp-internet"
    }
  }
}
```

### 📖 Detailed OS Guides
For complete, step-by-step instructions for **Windows, macOS, and Linux**, see the 👉 **[Multi-Platform Usage Guide](MULTI_PLATFORM_GUIDE.md)**.

---

## 💡 How It Works: smart_search vs search_web

### Before (v2.0): Multiple tool calls, manual scraping
```
User: "What are the upcoming Bollywood movies in 2026?"

Tool call 1: search_web("upcoming Bollywood movies 2026")
→ Returns 10 links with snippets

Tool call 2: read_webpage("https://www.imdb.com/...")
→ Returns raw text

Tool call 3: read_webpage("https://www.wikipedia.org/...")
→ Returns raw text

AI must manually piece together the answer from raw text.
```

### After (v3.0): One tool call, structured data
```
User: "What are the upcoming Bollywood movies in 2026?"

Tool call 1: smart_search("upcoming Bollywood movies 2026")
→ Returns:
  - Extracted movie list with titles, dates, genres
  - Markdown tables with ratings
  - Data from multiple sources combined
  - All in one response, ready to present
```

---

## 🏗️ Architecture

```
mcp-internet/
├── pyproject.toml              # Dependencies & Config
├── README.md                   # This file
├── MULTI_PLATFORM_GUIDE.md     # OS-specific setup guide
└── src/mcp_internet/
    ├── server.py               # Entry point — 25 MCP tools
    ├── tools/
    │   ├── search.py           # DuckDuckGo search + extraction flows
    │   ├── webpage.py          # Page reader with structured extraction
    │   ├── news.py             # News headlines
    │   ├── youtube.py          # YouTube search & video info
    │   ├── github.py           # GitHub repos & users
    │   ├── reddit.py           # Reddit search
    │   ├── twitter.py          # Twitter/X via Nitter
    │   └── ...                 # weather, time, translate, math, etc.
    └── utils/
        ├── http_client.py      # Async HTTP with UA rotation & rate limiting
        ├── cache.py            # SQLite TTL cache
        └── extractors.py       # Domain-specific data extractors
```

### Data Flow

```
User Query → smart_search
    ├── 1. Check cache (return if fresh)
    ├── 2. Search DuckDuckGo (HTML scraping + ddgs fallback)
    ├── 3. Read up to the requested number of result pages
    ├── 4. Apply domain-specific extractors where available
    │       ├── Wikipedia → infobox, summary, key facts
    │       ├── IMDb → titles, ratings, cast, genres
    │       ├── LinkedIn → name, role, skills, experience
    │       └── Generic → JSON-LD, OpenGraph, tables
    ├── 5. Format search results and extracted content
    ├── 6. Cache result
    └── 7. Return the response
```

---

## 🔧 Supported Data Sources

| Source | What's Extracted | Extractor Type |
|--------|-----------------|----------------|
| **Wikipedia** | Infobox, summary, key facts | Domain-specific |
| **IMDb** | Movie/show details, ratings, cast, genres | Domain-specific (JSON-LD) |
| **LinkedIn** | Name, role, skills, experience, education | Domain-specific (Googlebot UA) |
| **GitHub** | Repos, stars, forks, languages, topics | API-based |
| **Reddit** | Posts, scores, comments, subreddit info | JSON API |
| **YouTube** | Video titles, channels, views, duration | HTML parsing |
| **Any website** | JSON-LD, OpenGraph, HTML tables, main text | Generic fallback |

---

## ⚡ Performance

| Metric | Value |
|--------|-------|
| **Cache hit** | < 50ms |
| **Simple search** | 1-3 seconds |
| **Smart search (3 sources)** | 3-8 seconds |
| **Deep search (5+ sources)** | 5-15 seconds |
| **Rate limiting** | 2 req/sec per domain |
| **UA rotation** | 7 browser user-agents |

---

## 🧪 Testing

```bash
# Run the integration test suite
uv run python test_v3.py
```

### Recommended LM Studio Test Queries:
1. **`"What are the upcoming Bollywood movies in 2026?"`** — Should return movie lists
2. **`"Search the web for Sundar Pichai"`** — Should return profile data
3. **`"Latest albums by Taylor Swift"`** — Should return music data
4. **`"Python asyncio tutorial"`** — Should return technical content

---

## 📄 License & Contributing
This project is licensed under the MIT License - See [LICENSE](LICENSE) for details.

Contributions, bug reports, and feature requests are highly welcome!

---
**Made with ❤️ for the Local Developer & LLM community**
