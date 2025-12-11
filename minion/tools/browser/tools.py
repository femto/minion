#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Browser tools for Minion framework.

This module provides individual browser tools that wrap browser-use functionality.
Each tool inherits from AsyncBaseTool for consistent interface.
"""

import asyncio
from typing import Any, Dict, List, Optional

from ..async_base_tool import AsyncBaseTool


class BrowserNavigateTool(AsyncBaseTool):
    """Tool for navigating to a URL."""

    name = "browser_navigate"
    description = "Navigate the browser to a specified URL"
    inputs = {
        "url": {
            "type": "string",
            "description": "The URL to navigate to"
        }
    }
    output_type = "string"
    readonly = False

    def __init__(self, browser):
        super().__init__()
        self._browser = browser

    async def forward(self, url: str) -> str:
        """Navigate to the specified URL."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self._browser.navigate(url))
            if result.get("success"):
                return f"Successfully navigated to {url}"
            return f"Failed to navigate: {result.get('message', 'Unknown error')}"
        except Exception as e:
            return f"Error navigating to {url}: {str(e)}"


class BrowserClickTool(AsyncBaseTool):
    """Tool for clicking an element by index."""

    name = "browser_click"
    description = "Click an element on the page by its index"
    inputs = {
        "index": {
            "type": "integer",
            "description": "The index of the element to click"
        }
    }
    output_type = "string"
    readonly = False

    def __init__(self, browser):
        super().__init__()
        self._browser = browser

    async def forward(self, index: int) -> str:
        """Click the element at the specified index."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self._browser.click(index))
            if result.get("success"):
                return f"Successfully clicked element at index {index}"
            return f"Failed to click: {result.get('message', 'Unknown error')}"
        except Exception as e:
            return f"Error clicking element: {str(e)}"


class BrowserInputTextTool(AsyncBaseTool):
    """Tool for inputting text into an element."""

    name = "browser_input_text"
    description = "Input text into an element on the page by its index"
    inputs = {
        "index": {
            "type": "integer",
            "description": "The index of the element to input text into"
        },
        "text": {
            "type": "string",
            "description": "The text to input"
        }
    }
    output_type = "string"
    readonly = False

    def __init__(self, browser):
        super().__init__()
        self._browser = browser

    async def forward(self, index: int, text: str) -> str:
        """Input text into the element at the specified index."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self._browser.input_text(index, text))
            if result.get("success"):
                return f"Successfully input text into element at index {index}"
            return f"Failed to input text: {result.get('message', 'Unknown error')}"
        except Exception as e:
            return f"Error inputting text: {str(e)}"


class BrowserGetTextTool(AsyncBaseTool):
    """Tool for getting page text content."""

    name = "browser_get_text"
    description = "Get the text content of the current page"
    inputs = {}
    output_type = "string"
    readonly = True

    def __init__(self, browser):
        super().__init__()
        self._browser = browser

    async def forward(self) -> str:
        """Get the text content of the current page."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._browser.get_text)
            if result.get("success"):
                text = result.get("data", {}).get("text", "")
                # Truncate if too long
                if len(text) > 15000:
                    text = text[:15000] + "\n... (truncated)"
                return text
            return f"Failed to get text: {result.get('message', 'Unknown error')}"
        except Exception as e:
            return f"Error getting text: {str(e)}"


class BrowserGetHtmlTool(AsyncBaseTool):
    """Tool for getting page HTML content."""

    name = "browser_get_html"
    description = "Get the HTML content of the current page"
    inputs = {}
    output_type = "string"
    readonly = True

    def __init__(self, browser):
        super().__init__()
        self._browser = browser

    async def forward(self) -> str:
        """Get the HTML content of the current page."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._browser.get_html)
            if result.get("success"):
                html = result.get("data", {}).get("html", "")
                # Truncate if too long
                if len(html) > 20000:
                    html = html[:20000] + "\n... (truncated)"
                return html
            return f"Failed to get HTML: {result.get('message', 'Unknown error')}"
        except Exception as e:
            return f"Error getting HTML: {str(e)}"


class BrowserScreenshotTool(AsyncBaseTool):
    """Tool for capturing a screenshot."""

    name = "browser_screenshot"
    description = "Capture a screenshot of the current page"
    inputs = {}
    output_type = "object"
    readonly = True

    def __init__(self, browser):
        super().__init__()
        self._browser = browser

    async def forward(self) -> Dict[str, Any]:
        """Capture a screenshot of the current page."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._browser.screenshot)
            if result.get("success"):
                return {
                    "success": True,
                    "message": "Screenshot captured",
                    "screenshot": result.get("data", {}).get("screenshot")
                }
            return {
                "success": False,
                "message": result.get("message", "Failed to capture screenshot")
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error capturing screenshot: {str(e)}"
            }


class BrowserScrollTool(AsyncBaseTool):
    """Tool for scrolling the page."""

    name = "browser_scroll"
    description = "Scroll the page by a specified amount in pixels"
    inputs = {
        "scroll_amount": {
            "type": "integer",
            "description": "Number of pixels to scroll (positive for down, negative for up)"
        }
    }
    output_type = "string"
    readonly = False

    def __init__(self, browser):
        super().__init__()
        self._browser = browser

    async def forward(self, scroll_amount: int) -> str:
        """Scroll the page by the specified amount."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self._browser.scroll(scroll_amount))
            if result.get("success"):
                direction = "down" if scroll_amount > 0 else "up"
                return f"Successfully scrolled {direction} by {abs(scroll_amount)} pixels"
            return f"Failed to scroll: {result.get('message', 'Unknown error')}"
        except Exception as e:
            return f"Error scrolling: {str(e)}"


class BrowserExecuteJsTool(AsyncBaseTool):
    """Tool for executing JavaScript code."""

    name = "browser_execute_js"
    description = "Execute JavaScript code on the current page"
    inputs = {
        "script": {
            "type": "string",
            "description": "JavaScript code to execute (use arrow function syntax: () => {})"
        }
    }
    output_type = "object"
    readonly = False

    def __init__(self, browser):
        super().__init__()
        self._browser = browser

    async def forward(self, script: str) -> Dict[str, Any]:
        """Execute JavaScript code on the current page."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self._browser.execute_js(script))
            if result.get("success"):
                return {
                    "success": True,
                    "message": "JavaScript executed",
                    "result": result.get("data", {}).get("result")
                }
            return {
                "success": False,
                "message": result.get("message", "Failed to execute JavaScript")
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error executing JavaScript: {str(e)}"
            }


class BrowserGetStateTool(AsyncBaseTool):
    """Tool for getting current browser state."""

    name = "browser_get_state"
    description = "Get the current browser state (URL and title)"
    inputs = {}
    output_type = "object"
    readonly = True

    def __init__(self, browser):
        super().__init__()
        self._browser = browser

    async def forward(self) -> Dict[str, Any]:
        """Get the current browser state."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._browser.get_current_state)
            if result.get("success"):
                data = result.get("data", {})
                return {
                    "success": True,
                    "url": data.get("url", ""),
                    "title": data.get("title", "")
                }
            return {
                "success": False,
                "message": result.get("message", "Failed to get browser state")
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error getting browser state: {str(e)}"
            }


class BrowserReadLinksTool(AsyncBaseTool):
    """Tool for reading all links on the page."""

    name = "browser_read_links"
    description = "Get all links on the current page"
    inputs = {}
    output_type = "object"
    readonly = True

    def __init__(self, browser):
        super().__init__()
        self._browser = browser

    async def forward(self) -> Dict[str, Any]:
        """Get all links on the current page."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._browser.read_links)
            if result.get("success"):
                links = result.get("data", {}).get("links", [])
                return {
                    "success": True,
                    "count": len(links),
                    "links": links
                }
            return {
                "success": False,
                "message": result.get("message", "Failed to read links")
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error reading links: {str(e)}"
            }


class BrowserNewTabTool(AsyncBaseTool):
    """Tool for opening a new tab."""

    name = "browser_new_tab"
    description = "Open a new browser tab with a specified URL"
    inputs = {
        "url": {
            "type": "string",
            "description": "The URL to open in the new tab"
        }
    }
    output_type = "string"
    readonly = False

    def __init__(self, browser):
        super().__init__()
        self._browser = browser

    async def forward(self, url: str) -> str:
        """Open a new tab with the specified URL."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self._browser.new_tab(url))
            if result.get("success"):
                return f"Successfully opened new tab with URL: {url}"
            return f"Failed to open new tab: {result.get('message', 'Unknown error')}"
        except Exception as e:
            return f"Error opening new tab: {str(e)}"


class BrowserCloseTabTool(AsyncBaseTool):
    """Tool for closing the current tab."""

    name = "browser_close_tab"
    description = "Close the current browser tab"
    inputs = {}
    output_type = "string"
    readonly = False

    def __init__(self, browser):
        super().__init__()
        self._browser = browser

    async def forward(self) -> str:
        """Close the current tab."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._browser.close_tab)
            if result.get("success"):
                return "Successfully closed current tab"
            return f"Failed to close tab: {result.get('message', 'Unknown error')}"
        except Exception as e:
            return f"Error closing tab: {str(e)}"


class BrowserSwitchTabTool(AsyncBaseTool):
    """Tool for switching to a specific tab."""

    name = "browser_switch_tab"
    description = "Switch to a specific browser tab by its ID"
    inputs = {
        "tab_id": {
            "type": "integer",
            "description": "The ID of the tab to switch to"
        }
    }
    output_type = "string"
    readonly = False

    def __init__(self, browser):
        super().__init__()
        self._browser = browser

    async def forward(self, tab_id: int) -> str:
        """Switch to the specified tab."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self._browser.switch_tab(tab_id))
            if result.get("success"):
                return f"Successfully switched to tab {tab_id}"
            return f"Failed to switch tab: {result.get('message', 'Unknown error')}"
        except Exception as e:
            return f"Error switching tab: {str(e)}"


class BrowserRefreshTool(AsyncBaseTool):
    """Tool for refreshing the current page."""

    name = "browser_refresh"
    description = "Refresh the current page"
    inputs = {}
    output_type = "string"
    readonly = False

    def __init__(self, browser):
        super().__init__()
        self._browser = browser

    async def forward(self) -> str:
        """Refresh the current page."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._browser.refresh)
            if result.get("success"):
                return "Successfully refreshed the page"
            return f"Failed to refresh: {result.get('message', 'Unknown error')}"
        except Exception as e:
            return f"Error refreshing page: {str(e)}"


# Export all tool classes
__all__ = [
    "BrowserNavigateTool",
    "BrowserClickTool",
    "BrowserInputTextTool",
    "BrowserGetTextTool",
    "BrowserGetHtmlTool",
    "BrowserScreenshotTool",
    "BrowserScrollTool",
    "BrowserExecuteJsTool",
    "BrowserGetStateTool",
    "BrowserReadLinksTool",
    "BrowserNewTabTool",
    "BrowserCloseTabTool",
    "BrowserSwitchTabTool",
    "BrowserRefreshTool",
]
