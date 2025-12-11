#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Browser tools package for Minion framework.

This package provides browser automation tools built on browser-use.

Usage:
    ```python
    from minion.tools.browser import BrowserToolset

    # Check availability
    if BrowserToolset.is_available():
        async with BrowserToolset(headless=False) as toolset:
            # Use toolset.tools with an agent
            pass
    ```
"""

from .browser_toolset import BrowserToolset, create_browser_toolset
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

__all__ = [
    # Toolset
    "BrowserToolset",
    "create_browser_toolset",
    # Individual tools
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
