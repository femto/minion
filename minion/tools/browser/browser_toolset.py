#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Browser toolset for Minion framework.

This module provides BrowserToolset, a collection of browser automation tools
built on top of browser-use library.
"""

from typing import Optional, List

from ..base_tool import Toolset
from ..browser_tool import BrowserTool
from .tools import (
    BrowserNavigateTool,
    BrowserClickTool,
    BrowserInputTextTool,
    BrowserGetTextTool,
    BrowserGetHtmlTool,
    BrowserScreenshotTool,
    BrowserScrollTool,
    BrowserExecuteJsTool,
    BrowserGetStateTool,
    BrowserReadLinksTool,
    BrowserNewTabTool,
    BrowserCloseTabTool,
    BrowserSwitchTabTool,
    BrowserRefreshTool,
)


class BrowserToolset(Toolset):
    """
    Browser automation toolset using browser-use.

    This toolset provides a collection of browser tools for web automation tasks.
    Each tool wraps a specific browser operation and can be used independently
    or as part of an agent's toolbox.

    Example:
        ```python
        from minion.tools.browser import BrowserToolset

        # Using context manager (recommended)
        async with BrowserToolset(headless=False) as toolset:
            agent = MinionToolCallingAgent(
                tools=toolset.tools,
                model="gpt-4o"
            )
            await agent.run_async(input_obj)

        # Manual management
        toolset = BrowserToolset(headless=True)
        try:
            navigate_tool = toolset.get_tool("browser_navigate")
            await navigate_tool("https://example.com")
        finally:
            toolset.cleanup()
        ```

    Attributes:
        tools: List of browser tools
        headless: Whether the browser runs in headless mode
    """

    def __init__(self, headless: bool = True):
        """
        Initialize the browser toolset.

        Args:
            headless: Whether to run the browser in headless mode.
                     Set to False to see the browser window.
        """
        self.headless = headless
        self._browser: Optional[BrowserTool] = None
        self._initialized = False

        # Lazy initialization - don't create browser until needed
        # This allows checking if browser-use is available before starting
        tools = self._create_tools()
        super().__init__(tools)

    def _ensure_browser(self) -> BrowserTool:
        """Ensure browser is initialized."""
        if self._browser is None:
            self._browser = BrowserTool(headless=self.headless)
            self._initialized = True
        return self._browser

    def _create_tools(self) -> List:
        """Create all browser tools."""
        # Use a lazy browser getter that ensures initialization
        browser_getter = lambda: self._ensure_browser()

        # Create tool instances with lazy browser access
        return [
            _LazyBrowserTool(BrowserNavigateTool, browser_getter),
            _LazyBrowserTool(BrowserClickTool, browser_getter),
            _LazyBrowserTool(BrowserInputTextTool, browser_getter),
            _LazyBrowserTool(BrowserGetTextTool, browser_getter),
            _LazyBrowserTool(BrowserGetHtmlTool, browser_getter),
            _LazyBrowserTool(BrowserScreenshotTool, browser_getter),
            _LazyBrowserTool(BrowserScrollTool, browser_getter),
            _LazyBrowserTool(BrowserExecuteJsTool, browser_getter),
            _LazyBrowserTool(BrowserGetStateTool, browser_getter),
            _LazyBrowserTool(BrowserReadLinksTool, browser_getter),
            _LazyBrowserTool(BrowserNewTabTool, browser_getter),
            _LazyBrowserTool(BrowserCloseTabTool, browser_getter),
            _LazyBrowserTool(BrowserSwitchTabTool, browser_getter),
            _LazyBrowserTool(BrowserRefreshTool, browser_getter),
        ]

    def get_tool(self, name: str):
        """
        Get a tool by name.

        Args:
            name: The name of the tool (e.g., "browser_navigate")

        Returns:
            The tool instance, or None if not found
        """
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def cleanup(self):
        """Clean up browser resources."""
        if self._browser is not None:
            self._browser.cleanup()
            self._browser = None
            self._initialized = False

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources."""
        self.cleanup()
        return False

    def __enter__(self):
        """Sync context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit - cleanup resources."""
        self.cleanup()
        return False

    @staticmethod
    def is_available() -> bool:
        """Check if browser-use is available."""
        return BrowserTool.is_browser_use_available()


class _LazyBrowserTool:
    """
    Lazy wrapper for browser tools that initializes the browser on first use.

    This allows creating the toolset without immediately starting a browser,
    which is useful for checking availability before starting.
    """

    def __init__(self, tool_class, browser_getter):
        """
        Initialize lazy browser tool.

        Args:
            tool_class: The tool class to instantiate
            browser_getter: Callable that returns the browser instance
        """
        self._tool_class = tool_class
        self._browser_getter = browser_getter
        self._tool_instance = None

        # Copy class attributes for tool discovery
        self.name = tool_class.name
        self.description = tool_class.description
        self.inputs = tool_class.inputs
        self.output_type = tool_class.output_type
        self.readonly = tool_class.readonly

    def _ensure_tool(self):
        """Ensure tool instance is created."""
        if self._tool_instance is None:
            browser = self._browser_getter()
            self._tool_instance = self._tool_class(browser)
        return self._tool_instance

    async def __call__(self, *args, **kwargs):
        """Call the tool."""
        tool = self._ensure_tool()
        return await tool(*args, **kwargs)

    async def forward(self, *args, **kwargs):
        """Forward to the underlying tool."""
        tool = self._ensure_tool()
        return await tool.forward(*args, **kwargs)

    def format_for_observation(self, output):
        """Format output for observation."""
        tool = self._ensure_tool()
        return tool.format_for_observation(output)


def create_browser_toolset(headless: bool = True) -> BrowserToolset:
    """
    Create a browser toolset.

    Args:
        headless: Whether to run browser in headless mode

    Returns:
        BrowserToolset instance

    Raises:
        ImportError: If browser-use is not available
    """
    if not BrowserToolset.is_available():
        raise ImportError(
            "browser-use package is not available. "
            "Please install it: pip install browser-use"
        )
    return BrowserToolset(headless=headless)


__all__ = ["BrowserToolset", "create_browser_toolset"]
