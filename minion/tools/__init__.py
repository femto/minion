#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
工具模块
"""
from minion.tools.base_tool import BaseTool, ToolCollection, Toolset
from minion.tools.async_base_tool import AsyncBaseTool, async_tool, SyncToAsyncToolAdapter, AsyncToolCollection
from minion.tools.tool_decorator import tool

# Optional imports with fallbacks
try:
    from .browser_tool import BrowserTool
    HAS_BROWSER_TOOL = True
except ImportError:
    HAS_BROWSER_TOOL = False
    
    # Create a dummy BrowserTool class as fallback
    class BrowserTool:
        """Dummy BrowserTool when browser-use is not available."""
        
        @staticmethod
        def is_browser_use_available() -> bool:
            """Check if browser_use package is available."""
            return False
        
        def __init__(self, *args, **kwargs):
            """Initialize the dummy browser tool."""
            self._error_msg = "browser_use package is not available. Please install it to use BrowserTool."
        
        def _not_available(self, *args, **kwargs):
            """Return error message for all methods."""
            return {
                "success": False,
                "message": self._error_msg,
                "data": None
            }
        
        # Define all methods that would be available in the real implementation
        navigate = click = input_text = screenshot = get_html = _not_available
        get_text = read_links = execute_js = scroll = switch_tab = _not_available
        new_tab = close_tab = refresh = get_current_state = cleanup = _not_available

try:
    from .utcp.utcp_manual_toolset import UtcpManualToolset, create_utcp_toolset
    HAS_UTCP_TOOLSET = True
except ImportError:
    HAS_UTCP_TOOLSET = False
    
    # Create dummy classes as fallback
    class UtcpManualToolset:
        """Dummy UtcpManualToolset when UTCP is not available."""
        
        def __init__(self, *args, **kwargs):
            self._error_msg = "UTCP package is not available. Please install it to use UtcpManualToolset."
            raise ImportError(self._error_msg)
    
    def create_utcp_toolset(*args, **kwargs):
        """Dummy create_utcp_toolset function when UTCP is not available."""
        raise ImportError("UTCP package is not available. Please install it to use create_utcp_toolset.")

__all__ = [
    "BaseTool", 
    "tool", 
    "ToolCollection",
    "Toolset",
    "AsyncBaseTool", 
    "async_tool", 
    "SyncToAsyncToolAdapter", 
    "AsyncToolCollection",
    "BrowserTool",
    "HAS_BROWSER_TOOL",
    "UtcpManualToolset",
    "create_utcp_toolset",
    "HAS_UTCP_TOOLSET"
]