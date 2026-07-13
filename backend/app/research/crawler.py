"""Async URL crawler for the research pipeline.

Validates URLs (http/https only, well-formed per RFC 3986),
crawls up to 20 URLs with max depth 2, and extracts text content
from HTML responses for LLM consumption.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin

import httpx

logger = logging.getLogger(__name__)

# Maximum number of URLs to crawl in a single batch
MAX_URLS = 20

# Maximum crawl depth
MAX_DEPTH = 2

# Per-URL timeout in seconds
DEFAULT_TIMEOUT = 30.0


@dataclass
class CrawlResult:
    """Result of crawling a single URL."""

    url: str
    content: str = ""
    status_code: int = 0
    success: bool = False
    error: str = ""


def validate_url(url: str) -> bool:
    """Validate that a URL uses http/https scheme and is well-formed.

    Accepts only URLs with:
    - http or https scheme
    - A non-empty netloc (hostname)
    - Well-formed structure per RFC 3986

    Args:
        url: The URL string to validate.

    Returns:
        True if the URL is valid, False otherwise.
    """
    if not url or not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return False

    # Must have http or https scheme
    if parsed.scheme not in ("http", "https"):
        return False

    # Must have a non-empty netloc (hostname)
    if not parsed.netloc:
        return False

    # Hostname must not be empty after stripping port
    hostname = parsed.hostname
    if not hostname:
        return False

    # Basic hostname validation: must contain at least one character
    # and not consist only of dots
    if hostname.strip(".") == "":
        return False

    return True


class HTMLTextExtractor(HTMLParser):
    """Extract text content from HTML, stripping all tags."""

    # Tags whose content should be completely skipped
    SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}

    def __init__(self) -> None:
        super().__init__()
        self._text_parts: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._text_parts.append(stripped)

    def get_text(self) -> str:
        """Return extracted text, joined with newlines."""
        return "\n".join(self._text_parts)


def extract_text_from_html(html: str) -> str:
    """Extract clean text content from HTML string.

    Removes all HTML tags, scripts, styles, and returns
    only the text content for LLM consumption.

    Args:
        html: Raw HTML string.

    Returns:
        Extracted text content.
    """
    if not html:
        return ""

    parser = HTMLTextExtractor()
    try:
        parser.feed(html)
    except Exception:
        # If HTML parsing fails, do a basic tag strip
        return re.sub(r"<[^>]+>", " ", html).strip()

    return parser.get_text()


def _extract_links_from_html(html: str, base_url: str) -> list[str]:
    """Extract valid links from HTML content for depth crawling.

    Args:
        html: Raw HTML string.
        base_url: Base URL for resolving relative links.

    Returns:
        List of absolute URLs found in the HTML.
    """
    links: list[str] = []
    # Simple regex to extract href values from anchor tags
    href_pattern = re.compile(r'<a\s[^>]*href=["\']([^"\']+)["\']', re.IGNORECASE)

    for match in href_pattern.finditer(html):
        href = match.group(1)
        # Resolve relative URLs
        absolute_url = urljoin(base_url, href)
        if validate_url(absolute_url):
            links.append(absolute_url)

    return links


async def _crawl_single_url(
    client: httpx.AsyncClient,
    url: str,
    timeout: float,
) -> CrawlResult:
    """Crawl a single URL and return the result.

    Args:
        client: httpx async client to use.
        url: URL to crawl.
        timeout: Timeout in seconds for this request.

    Returns:
        CrawlResult with content and status.
    """
    try:
        response = await client.get(
            url,
            timeout=timeout,
            follow_redirects=True,
        )
        content_type = response.headers.get("content-type", "")

        # Only process text/html and text/plain content
        if "text/html" in content_type or "text/plain" in content_type:
            raw_content = response.text
            text_content = extract_text_from_html(raw_content)
            return CrawlResult(
                url=url,
                content=text_content,
                status_code=response.status_code,
                success=True,
            )
        else:
            # Non-text content type — skip
            return CrawlResult(
                url=url,
                content="",
                status_code=response.status_code,
                success=False,
                error=f"Unsupported content type: {content_type}",
            )
    except httpx.TimeoutException:
        logger.warning("Timeout crawling URL: %s", url)
        return CrawlResult(
            url=url, success=False, error="Request timed out"
        )
    except httpx.ConnectError as e:
        logger.warning("Connection error crawling URL %s: %s", url, e)
        return CrawlResult(
            url=url, success=False, error=f"Connection error: {e}"
        )
    except httpx.HTTPError as e:
        logger.warning("HTTP error crawling URL %s: %s", url, e)
        return CrawlResult(
            url=url, success=False, error=f"HTTP error: {e}"
        )
    except Exception as e:
        logger.warning("Unexpected error crawling URL %s: %s", url, e)
        return CrawlResult(
            url=url, success=False, error=f"Unexpected error: {e}"
        )


async def crawl_urls(
    urls: list[str],
    max_urls: int = MAX_URLS,
    max_depth: int = MAX_DEPTH,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[CrawlResult]:
    """Asynchronously crawl a list of URLs up to a maximum count and depth.

    Validates each URL before crawling. Uses httpx.AsyncClient with
    per-URL timeouts. Crawls discovered links up to max_depth.

    Args:
        urls: Initial list of URLs to crawl.
        max_urls: Maximum number of URLs to crawl (capped at 20).
        max_depth: Maximum crawl depth (capped at 2).
        timeout: Per-URL timeout in seconds (default 30s).

    Returns:
        List of CrawlResult objects for all crawled URLs.
    """
    # Enforce caps
    max_urls = min(max_urls, MAX_URLS)
    max_depth = min(max_depth, MAX_DEPTH)

    # Filter to valid URLs only
    valid_urls = [url for url in urls if validate_url(url)]

    if not valid_urls:
        return []

    results: list[CrawlResult] = []
    visited: set[str] = set()

    # Queue items: (url, depth)
    queue: list[tuple[str, int]] = [(url, 0) for url in valid_urls]

    async with httpx.AsyncClient(
        headers={
            "User-Agent": "CompanyLens-Crawler/1.0",
            "Accept": "text/html,text/plain,application/xhtml+xml",
        },
    ) as client:
        while queue and len(results) < max_urls:
            # Process current batch (up to remaining capacity)
            batch_size = min(len(queue), max_urls - len(results), 5)
            batch = []

            for _ in range(batch_size):
                if not queue:
                    break
                url, depth = queue.pop(0)
                if url in visited:
                    continue
                visited.add(url)
                batch.append((url, depth))

            if not batch:
                break

            # Crawl batch concurrently
            tasks = [
                _crawl_single_url(client, url, timeout)
                for url, _ in batch
            ]
            batch_results = await asyncio.gather(*tasks)

            for (url, depth), result in zip(batch, batch_results):
                results.append(result)

                # If successful and within depth limit, extract links
                if result.success and depth < max_depth and len(results) < max_urls:
                    try:
                        # Re-fetch raw HTML for link extraction
                        # (we already have the text content extracted)
                        response = await client.get(
                            url, timeout=timeout, follow_redirects=True
                        )
                        if "text/html" in response.headers.get("content-type", ""):
                            links = _extract_links_from_html(response.text, url)
                            for link in links:
                                if link not in visited and len(queue) < max_urls:
                                    queue.append((link, depth + 1))
                    except Exception:
                        # If link extraction fails, just continue
                        pass

    return results
