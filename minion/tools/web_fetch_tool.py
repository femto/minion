#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WebFetch Tool - Fetch web content and convert to markdown

Based on mcp-server-fetch (https://github.com/modelcontextprotocol/servers/tree/main/src/fetch)
"""

import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse, urlunparse

from .async_base_tool import AsyncBaseTool

# Default User-Agent
DEFAULT_USER_AGENT = "MinionWebFetch/1.0 (Autonomous; +https://github.com/femtozheng/minion)"


class WebFetchTool(AsyncBaseTool):
    """
    Tool for fetching web content and converting HTML to markdown.

    Features:
    - Fetches URL content using httpx
    - Converts HTML to clean markdown using markdownify
    - Supports robots.txt checking for autonomous fetching
    - Supports pagination with start_index and max_length
    - Supports proxy configuration
    """

    name = "web_fetch"
    description = """Fetch a URL and extract its contents as markdown.

This tool retrieves web page content, converts HTML to markdown for easier consumption.
Supports chunked reading for long pages via start_index parameter.

Args:
    url: The URL to fetch (required)
    max_length: Maximum number of characters to return (default: 5000)
    start_index: Character offset for pagination (default: 0)
    raw: If True, return raw HTML instead of markdown (default: False)
    check_robots: If True, check robots.txt before fetching (default: False)

Returns:
    Markdown content of the web page, or error message if fetch fails.
"""
    inputs = {
        "url": {
            "type": "string",
            "description": "URL to fetch"
        },
        "max_length": {
            "type": "integer",
            "description": "Maximum number of characters to return (default: 5000)",
            "default": 5000
        },
        "start_index": {
            "type": "integer",
            "description": "Character offset for pagination (default: 0)",
            "default": 0
        },
        "raw": {
            "type": "boolean",
            "description": "If True, return raw HTML instead of markdown",
            "default": False
        },
        "check_robots": {
            "type": "boolean",
            "description": "If True, check robots.txt before autonomous fetching",
            "default": False
        }
    }
    output_type = "string"
    readonly = True

    def __init__(
        self,
        user_agent: Optional[str] = None,
        proxy_url: Optional[str] = None,
        ignore_robots_txt: bool = False,
        timeout: int = 30
    ):
        """
        Initialize WebFetchTool.

        Args:
            user_agent: Custom User-Agent string
            proxy_url: Proxy URL for requests
            ignore_robots_txt: If True, ignore robots.txt restrictions
            timeout: Request timeout in seconds
        """
        super().__init__()
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.proxy_url = proxy_url
        self.ignore_robots_txt = ignore_robots_txt
        self.timeout = timeout

    async def forward(
        self,
        url: str,
        max_length: int = 5000,
        start_index: int = 0,
        raw: bool = False,
        check_robots: bool = False
    ) -> str:
        """
        Fetch URL content and convert to markdown.

        Args:
            url: URL to fetch
            max_length: Maximum characters to return
            start_index: Character offset for pagination
            raw: Return raw HTML if True
            check_robots: Check robots.txt if True

        Returns:
            Markdown content or error message
        """
        try:
            import httpx
        except ImportError:
            return "Error: httpx is required. Install with: pip install httpx"

        # Validate URL
        if not url:
            return "Error: URL is required"

        # Ensure URL has scheme
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            # Check robots.txt if required
            if check_robots and not self.ignore_robots_txt:
                can_fetch, reason = await self._check_robots_txt(url)
                if not can_fetch:
                    return f"Error: Cannot fetch URL - {reason}"

            # Fetch the URL
            content, content_type = await self._fetch_url(url, raw)

            # Apply pagination
            if start_index > 0:
                content = content[start_index:]

            if len(content) > max_length:
                content = content[:max_length]
                # Add continuation hint
                content += f"\n\n[Content truncated. Use start_index={start_index + max_length} to continue reading]"

            return content

        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} when fetching {url}"
        except httpx.RequestError as e:
            return f"Error: Failed to fetch {url} - {str(e)}"
        except Exception as e:
            return f"Error: {str(e)}"

    async def _fetch_url(self, url: str, raw: bool = False) -> Tuple[str, str]:
        """
        Fetch URL content.

        Args:
            url: URL to fetch
            raw: Return raw HTML if True

        Returns:
            Tuple of (content, content_type)
        """
        import httpx

        proxies = self.proxy_url if self.proxy_url else None

        async with httpx.AsyncClient(proxy=proxies) as client:
            response = await client.get(
                url,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout
            )
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            text = response.text

            # If raw mode or not HTML, return as-is
            if raw:
                return text, content_type

            # Convert HTML to markdown
            if "html" in content_type.lower():
                text = self._extract_content_from_html(text)

            return text, content_type

    def _extract_content_from_html(self, html: str) -> str:
        """
        Extract and convert HTML content to markdown.

        Uses readabilipy for content extraction if available,
        falls back to basic markdownify conversion.

        Args:
            html: Raw HTML content

        Returns:
            Markdown content
        """
        try:
            import markdownify
            from bs4 import BeautifulSoup
        except ImportError:
            # Fallback: basic HTML tag stripping
            return self._basic_html_to_text(html)

        # Try using readabilipy for better content extraction
        try:
            import readabilipy.simple_json

            result = readabilipy.simple_json.simple_json_from_html_string(
                html, use_readability=True
            )

            if result.get("content"):
                content = markdownify.markdownify(
                    result["content"],
                    heading_style=markdownify.ATX,
                    strip=['script', 'style']
                )

                # Clean up title if available
                title = result.get("title", "")
                if title:
                    content = f"# {title}\n\n{content}"

                return self._clean_markdown(content)
        except ImportError:
            pass
        except Exception:
            pass

        # Fallback: use BeautifulSoup to clean HTML first, then markdownify
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove unwanted elements
            for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'noscript', 'iframe']):
                tag.decompose()

            # Extract title
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)

            # Get main content - try to find body or main content area
            main_content = soup.find('main') or soup.find('article') or soup.find('body') or soup

            # Convert to markdown
            content = markdownify.markdownify(
                str(main_content),
                heading_style=markdownify.ATX
            )

            # Add title if available
            if title and title not in content[:100]:
                content = f"# {title}\n\n{content}"

            return self._clean_markdown(content)
        except Exception:
            return self._basic_html_to_text(html)

    def _basic_html_to_text(self, html: str) -> str:
        """
        Basic HTML to text conversion without dependencies.

        Args:
            html: Raw HTML content

        Returns:
            Plain text content
        """
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Replace common block elements with newlines
        html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</p>', '\n\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</div>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</h[1-6]>', '\n\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<h[1-6][^>]*>', '\n\n# ', html, flags=re.IGNORECASE)

        # Remove remaining tags
        html = re.sub(r'<[^>]+>', '', html)

        # Decode HTML entities
        html = self._decode_html_entities(html)

        # Clean up whitespace
        html = re.sub(r'\n\s*\n', '\n\n', html)
        html = re.sub(r'[ \t]+', ' ', html)

        return html.strip()

    def _decode_html_entities(self, text: str) -> str:
        """Decode common HTML entities."""
        import html
        return html.unescape(text)

    def _clean_markdown(self, content: str) -> str:
        """
        Clean up markdown content.

        Args:
            content: Raw markdown content

        Returns:
            Cleaned markdown
        """
        # Remove excessive newlines
        content = re.sub(r'\n{3,}', '\n\n', content)

        # Remove trailing whitespace on lines
        content = re.sub(r'[ \t]+\n', '\n', content)

        # Remove leading/trailing whitespace
        content = content.strip()

        return content

    async def _check_robots_txt(self, url: str) -> Tuple[bool, str]:
        """
        Check if URL can be fetched according to robots.txt.

        Args:
            url: URL to check

        Returns:
            Tuple of (can_fetch, reason)
        """
        import httpx

        robots_url = self._get_robots_txt_url(url)

        try:
            proxies = self.proxy_url if self.proxy_url else None

            async with httpx.AsyncClient(proxy=proxies) as client:
                response = await client.get(
                    robots_url,
                    follow_redirects=True,
                    headers={"User-Agent": self.user_agent},
                    timeout=10
                )

                if response.status_code == 404:
                    # No robots.txt, allow all
                    return True, ""

                if response.status_code >= 400:
                    # Can't access robots.txt, allow
                    return True, ""

                robots_content = response.text

                # Try using Protego for parsing
                try:
                    from protego import Protego

                    parser = Protego.parse(robots_content)
                    if parser.can_fetch(url, self.user_agent):
                        return True, ""
                    else:
                        return False, "robots.txt disallows autonomous fetching of this URL"
                except ImportError:
                    # Fallback: basic robots.txt parsing
                    return self._basic_robots_check(robots_content, url)

        except Exception as e:
            # On error, allow fetching
            return True, ""

    def _get_robots_txt_url(self, url: str) -> str:
        """
        Get robots.txt URL for a given URL.

        Args:
            url: Target URL

        Returns:
            robots.txt URL
        """
        parsed = urlparse(url)
        robots_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            '/robots.txt',
            '', '', ''
        ))
        return robots_url

    def _basic_robots_check(self, robots_content: str, url: str) -> Tuple[bool, str]:
        """
        Basic robots.txt parsing without Protego.

        Args:
            robots_content: robots.txt content
            url: URL to check

        Returns:
            Tuple of (can_fetch, reason)
        """
        parsed_url = urlparse(url)
        path = parsed_url.path or "/"

        lines = robots_content.split('\n')
        current_user_agent = None
        disallow_all = False

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if ':' not in line:
                continue

            key, _, value = line.partition(':')
            key = key.strip().lower()
            value = value.strip()

            if key == 'user-agent':
                current_user_agent = value
            elif key == 'disallow' and current_user_agent in ('*', self.user_agent):
                if value == '/' or path.startswith(value):
                    disallow_all = True
                    break

        if disallow_all:
            return False, "robots.txt disallows fetching this URL"

        return True, ""

    def format_for_observation(self, output: Any) -> str:
        """
        Format output for LLM observation.

        Args:
            output: Raw output from forward()

        Returns:
            Formatted string
        """
        if not isinstance(output, str):
            return str(output)
        return output


# Convenience function to create tool instance
def create_web_fetch_tool(
    user_agent: Optional[str] = None,
    proxy_url: Optional[str] = None,
    ignore_robots_txt: bool = False,
    timeout: int = 30
) -> WebFetchTool:
    """
    Create a WebFetchTool instance.

    Args:
        user_agent: Custom User-Agent string
        proxy_url: Proxy URL for requests
        ignore_robots_txt: If True, ignore robots.txt restrictions
        timeout: Request timeout in seconds

    Returns:
        WebFetchTool instance
    """
    return WebFetchTool(
        user_agent=user_agent,
        proxy_url=proxy_url,
        ignore_robots_txt=ignore_robots_txt,
        timeout=timeout
    )
