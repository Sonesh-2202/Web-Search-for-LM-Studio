"""
Webpage Reader Tool - Extract clean text content from any URL.

Uses BeautifulSoup to parse HTML and extract the main readable content,
stripping navigation, ads, scripts, and other non-content elements.

Features:
- JSON-LD structured data extraction
- HTML table → markdown table conversion
- Domain-aware extraction using extractor registry
- OpenGraph meta tag extraction
"""

import logging
import re

from bs4 import BeautifulSoup

from ..utils.http_client import fetch_url

logger = logging.getLogger(__name__)

# Elements to remove (navigation, ads, scripts, etc.)
REMOVE_TAGS = [
    "script", "style", "nav", "header", "footer", "aside",
    "form", "button", "iframe", "noscript", "svg", "canvas",
    "advertisement", "ad", "sidebar", "menu", "popup",
]

# Classes/IDs that typically contain non-content
REMOVE_PATTERNS = [
    r"nav", r"menu", r"sidebar", r"footer", r"header", r"ad[-_]?",
    r"advertisement", r"social", r"share", r"comment", r"related",
    r"popup", r"modal", r"cookie", r"banner", r"promo",
]


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.splitlines()]
    output = []
    for line in lines:
        if line:
            output.append(line)
        elif output and output[-1] != "":
            output.append("")
    return "\n".join(output).strip()


def extract_main_content(soup: BeautifulSoup, url: str = "") -> str:
    """Extract the main readable content from parsed HTML."""
    
    from urllib.parse import urlsplit
    host = (urlsplit(url).hostname or "").lower()
    is_linkedin = host == "linkedin.com" or host.endswith(".linkedin.com")

    if is_linkedin:
        # LinkedIn public profiles have a <main> tag containing the entire profile
        main_content = soup.find("main")
        if main_content:
            for tag in ["script", "style", "nav", "svg", "button", "iframe", "noscript"]:
                for element in main_content.find_all(tag):
                    try:
                        element.decompose()
                    except Exception:
                        pass
            return main_content.get_text(separator='\n', strip=True)

    # Remove unwanted elements
    for tag in REMOVE_TAGS:
        for element in soup.find_all(tag):
            element.decompose()
    
    # Remove elements with common non-content classes/IDs
    pattern = re.compile('|'.join(REMOVE_PATTERNS), re.IGNORECASE)
    for element in soup.find_all(class_=pattern):
        element.decompose()
    for element in soup.find_all(id=pattern):
        element.decompose()
    
    # Try to find main content containers
    main_content = None
    for tag in ["main", "article", '[role="main"]']:
        main_content = soup.find(tag) if not tag.startswith('[') else soup.select_one(tag)
        if main_content:
            break
    
    # If no main container found, try content divs
    if not main_content:
        for class_name in ["content", "post", "entry", "article", "body"]:
            main_content = soup.find(class_=re.compile(class_name, re.IGNORECASE))
            if main_content:
                break
    
    # Fall back to body
    if not main_content:
        main_content = soup.find("body") or soup
    
    return main_content.get_text(separator='\n', strip=True)


async def read_webpage(url: str, max_length: int = 5000) -> str:
    """
    Read and extract text content from a webpage.
    
    Automatically extracts structured data (JSON-LD, tables, meta tags)
    when available, in addition to the main text content.
    
    Args:
        url: The URL to read
        max_length: Maximum characters to return
        
    Returns:
        Extracted text content with any structured data found
    """
    if not url.strip():
        return "❌ Error: Please provide a URL."
    if not isinstance(max_length, int) or isinstance(max_length, bool):
        return "❌ Error: max_length must be an integer from 1 to 20000."
    max_length = max(1, min(max_length, 20000))
    
    # Add protocol if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    html = await fetch_url(url)
    if not html:
        return f"❌ Error: Unable to fetch content from {url}. The page may be unavailable or blocking requests."
    
    try:
        soup = BeautifulSoup(html, "lxml")
        
        # Get title
        title = soup.find("title")
        title_text = title.get_text(strip=True) if title else "Unknown Page"
        
        # Get meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc.get("content", "") if meta_desc else ""
        
        # Try structured extraction first
        structured_section = ""
        try:
            from ..utils.extractors import (
                extract_structured_data,
                format_extracted_data,
            )
            data = extract_structured_data(html, url)
            formatted = format_extracted_data(data)
            if formatted.strip() and len(formatted) > 50:
                structured_section = f"\n📊 **Structured Data:**\n{formatted}\n"
        except Exception as e:
            logger.debug("Structured extraction failed (%s)", type(e).__name__)
        
        # Extract HTML tables as markdown
        tables_section = ""
        try:
            from ..utils.extractors import extract_html_tables, tables_to_markdown
            tables = extract_html_tables(soup)
            if tables:
                md_tables = tables_to_markdown(tables)
                if md_tables.strip():
                    tables_section = f"\n📋 **Tables Found:**\n{md_tables}\n"
        except Exception:
            pass
        
        # Extract main content
        content = extract_main_content(soup, url)
        content = clean_text(content)
        
        # Format output
        output = f"""📄 **{title_text}**
🔗 {url}
"""
        if description:
            output += f"📝 {description}\n"
        
        if structured_section:
            output += structured_section
        
        if tables_section:
            output += tables_section
        
        output += f"""
{'=' * 50}

{content}
"""
        if len(output) > max_length:
            marker = "\n[Output truncated]"
            output = output[:max(0, max_length - len(marker))] + marker[:max_length]
        return output
        
    except Exception as e:
        logger.error("Error parsing webpage (%s)", type(e).__name__)
        return f"❌ Error: Unable to parse content from {url}. The page format may not be supported."
