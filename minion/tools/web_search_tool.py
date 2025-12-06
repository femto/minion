#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WebSearch Tool - Search the web using DuckDuckGo

"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlparse, parse_qs

from .async_base_tool import AsyncBaseTool

# Default User-Agent
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    snippet: str
    link: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "snippet": self.snippet,
            "link": self.link
        }


class WebSearchTool(AsyncBaseTool):
    """
    Tool for searching the web using DuckDuckGo.

    Features:
    - Uses DuckDuckGo HTML interface for searching
    - No API key required
    - Returns structured search results with title, snippet, and link
    - Supports multiple search providers (extensible)
    """

    name = "web_search"
    description = """Search the web and return relevant results.

This tool allows searching the web to get up-to-date information for current events,
recent data, or any information beyond the knowledge cutoff.

Args:
    query: The search query string (required)
    max_results: Maximum number of results to return (default: 10)
    provider: Search provider to use, currently supports 'duckduckgo' (default: 'duckduckgo')

Returns:
    Formatted search results with title, snippet, and link for each result.

Usage notes:
- Use when you need current information not in training data
- Effective for recent news, current events, product updates, or real-time data
- Search queries should be specific and well-targeted for best results
"""
    inputs = {
        "query": {
            "type": "string",
            "description": "The search query"
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return (default: 10)",
            "default": 10
        },
        "provider": {
            "type": "string",
            "description": "Search provider: 'duckduckgo' (default: 'duckduckgo')",
            "default": "duckduckgo"
        }
    }
    output_type = "string"
    readonly = True

    def __init__(
        self,
        user_agent: Optional[str] = None,
        proxy_url: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize WebSearchTool.

        Args:
            user_agent: Custom User-Agent string
            proxy_url: Proxy URL for requests
            timeout: Request timeout in seconds
        """
        super().__init__()
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.proxy_url = proxy_url
        self.timeout = timeout

    async def forward(
        self,
        query: str,
        max_results: int = 10,
        provider: str = "duckduckgo"
    ) -> str:
        """
        Search the web and return formatted results.

        Args:
            query: Search query
            max_results: Maximum number of results
            provider: Search provider to use

        Returns:
            Formatted search results as string
        """
        if not query:
            return "Error: Search query is required"

        try:
            if provider == "duckduckgo":
                results = await self._search_duckduckgo(query, max_results)
            else:
                return f"Error: Unknown search provider '{provider}'. Supported: duckduckgo"

            return self._format_results(results, provider)

        except Exception as e:
            return f"Error during web search: {str(e)}"

    async def _search_duckduckgo(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """
        Search using DuckDuckGo HTML interface.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of SearchResult objects
        """
        try:
            import httpx
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("httpx and beautifulsoup4 are required. Install with: pip install httpx beautifulsoup4")

        url = f"https://html.duckduckgo.com/html/?{urlencode({'q': query})}"

        proxies = self.proxy_url if self.proxy_url else None

        # Use browser-like headers to avoid 403
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

        async with httpx.AsyncClient(proxy=proxies) as client:
            response = await client.get(
                url,
                headers=headers,
                timeout=self.timeout,
                follow_redirects=True
            )
            response.raise_for_status()

            html = response.text

        # Parse HTML
        soup = BeautifulSoup(html, 'html.parser')
        results: List[SearchResult] = []

        # Find result nodes
        result_nodes = soup.select('.result.web-result')

        for node in result_nodes[:max_results]:
            title_node = node.select_one('.result__a')
            snippet_node = node.select_one('.result__snippet')

            if title_node and snippet_node:
                title = title_node.get_text(strip=True)
                link = title_node.get('href', '')
                snippet = snippet_node.get_text(strip=True)

                if title and link and snippet:
                    # Clean the link - DuckDuckGo uses uddg parameter for redirects
                    clean_link = self._clean_duckduckgo_link(link)
                    results.append(SearchResult(
                        title=title,
                        snippet=snippet,
                        link=clean_link
                    ))

        return results

    def _clean_duckduckgo_link(self, link: str) -> str:
        """
        Clean DuckDuckGo redirect links.

        Args:
            link: Original link from DuckDuckGo

        Returns:
            Clean direct link
        """
        if link.startswith('https://duckduckgo.com/l/?uddg='):
            try:
                parsed = urlparse(link)
                params = parse_qs(parsed.query)
                if 'uddg' in params:
                    return params['uddg'][0]
            except Exception:
                pass

        # Handle //duckduckgo.com/l/?uddg= format
        if '//duckduckgo.com/l/?uddg=' in link:
            try:
                parsed = urlparse(link if link.startswith('http') else 'https:' + link)
                params = parse_qs(parsed.query)
                if 'uddg' in params:
                    return params['uddg'][0]
            except Exception:
                pass

        return link

    def _format_results(self, results: List[SearchResult], provider: str) -> str:
        """
        Format search results for LLM consumption.

        Args:
            results: List of search results
            provider: Search provider used

        Returns:
            Formatted string
        """
        if not results:
            return f"No results found using {provider}."

        output = f"Found {len(results)} search results using {provider}:\n\n"

        for i, result in enumerate(results, 1):
            output += f"{i}. **{result.title}**\n"
            output += f"   {result.snippet}\n"
            output += f"   Link: {result.link}\n\n"

        output += "You can reference these results to provide current, accurate information."
        return output

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

    async def search_raw(
        self,
        query: str,
        max_results: int = 10,
        provider: str = "duckduckgo"
    ) -> List[SearchResult]:
        """
        Search and return raw SearchResult objects.

        Useful when you need structured data instead of formatted string.

        Args:
            query: Search query
            max_results: Maximum number of results
            provider: Search provider to use

        Returns:
            List of SearchResult objects
        """
        if provider == "duckduckgo":
            return await self._search_duckduckgo(query, max_results)
        else:
            raise ValueError(f"Unknown search provider '{provider}'")


# Convenience function to create tool instance
def create_web_search_tool(
    user_agent: Optional[str] = None,
    proxy_url: Optional[str] = None,
    timeout: int = 30
) -> WebSearchTool:
    """
    Create a WebSearchTool instance.

    Args:
        user_agent: Custom User-Agent string
        proxy_url: Proxy URL for requests
        timeout: Request timeout in seconds

    Returns:
        WebSearchTool instance
    """
    return WebSearchTool(
        user_agent=user_agent,
        proxy_url=proxy_url,
        timeout=timeout
    )
