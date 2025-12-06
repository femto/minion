#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
工具模块 - 使用懒加载避免不必要的依赖加载
"""
from minion.tools.base_tool import BaseTool, ToolCollection, Toolset
from minion.tools.async_base_tool import AsyncBaseTool
from minion.tools.tool_decorator import tool

# 懒加载的模块缓存
_lazy_imports = {}


def __getattr__(name):
    """懒加载机制，按需导入工具"""

    # BrowserTool
    if name == "BrowserTool":
        if "BrowserTool" not in _lazy_imports:
            try:
                from .browser_tool import BrowserTool
                _lazy_imports["BrowserTool"] = BrowserTool
                _lazy_imports["HAS_BROWSER_TOOL"] = True
            except ImportError:
                # Create a dummy BrowserTool class as fallback
                class BrowserTool:
                    """Dummy BrowserTool when browser-use is not available."""

                    @staticmethod
                    def is_browser_use_available() -> bool:
                        return False

                    def __init__(self, *args, **kwargs):
                        self._error_msg = "browser_use package is not available."

                    def _not_available(self, *args, **kwargs):
                        return {"success": False, "message": self._error_msg, "data": None}

                    navigate = click = input_text = screenshot = get_html = _not_available
                    get_text = read_links = execute_js = scroll = switch_tab = _not_available
                    new_tab = close_tab = refresh = get_current_state = cleanup = _not_available

                _lazy_imports["BrowserTool"] = BrowserTool
                _lazy_imports["HAS_BROWSER_TOOL"] = False
        return _lazy_imports["BrowserTool"]

    if name == "HAS_BROWSER_TOOL":
        # Trigger BrowserTool loading to set HAS_BROWSER_TOOL
        __getattr__("BrowserTool")
        return _lazy_imports.get("HAS_BROWSER_TOOL", False)

    # UTCP Toolset
    if name == "UtcpManualToolset":
        if "UtcpManualToolset" not in _lazy_imports:
            try:
                from .utcp.utcp_manual_toolset import UtcpManualToolset
                _lazy_imports["UtcpManualToolset"] = UtcpManualToolset
                _lazy_imports["HAS_UTCP_TOOLSET"] = True
            except ImportError:
                class UtcpManualToolset:
                    def __init__(self, *args, **kwargs):
                        raise ImportError("UTCP package is not available.")
                _lazy_imports["UtcpManualToolset"] = UtcpManualToolset
                _lazy_imports["HAS_UTCP_TOOLSET"] = False
        return _lazy_imports["UtcpManualToolset"]

    if name == "create_utcp_toolset":
        if "create_utcp_toolset" not in _lazy_imports:
            try:
                from .utcp.utcp_manual_toolset import create_utcp_toolset
                _lazy_imports["create_utcp_toolset"] = create_utcp_toolset
            except ImportError:
                def create_utcp_toolset(*args, **kwargs):
                    raise ImportError("UTCP package is not available.")
                _lazy_imports["create_utcp_toolset"] = create_utcp_toolset
        return _lazy_imports["create_utcp_toolset"]

    if name == "HAS_UTCP_TOOLSET":
        __getattr__("UtcpManualToolset")
        return _lazy_imports.get("HAS_UTCP_TOOLSET", False)

    # Tool Search Tools
    if name in ("ToolInfo", "ToolRegistry", "ToolSearchTool", "LoadToolTool",
                "ToolSearchStrategy", "KeywordSearchStrategy", "RegexSearchStrategy",
                "BM25SearchStrategy", "HAS_BM25"):
        if "ToolSearchTool" not in _lazy_imports:
            from .tool_search import (
                ToolInfo, ToolRegistry, ToolSearchTool, LoadToolTool,
                ToolSearchStrategy, KeywordSearchStrategy, RegexSearchStrategy,
                BM25SearchStrategy, HAS_BM25
            )
            _lazy_imports["ToolInfo"] = ToolInfo
            _lazy_imports["ToolRegistry"] = ToolRegistry
            _lazy_imports["ToolSearchTool"] = ToolSearchTool
            _lazy_imports["LoadToolTool"] = LoadToolTool
            _lazy_imports["ToolSearchStrategy"] = ToolSearchStrategy
            _lazy_imports["KeywordSearchStrategy"] = KeywordSearchStrategy
            _lazy_imports["RegexSearchStrategy"] = RegexSearchStrategy
            _lazy_imports["BM25SearchStrategy"] = BM25SearchStrategy
            _lazy_imports["HAS_BM25"] = HAS_BM25
        return _lazy_imports[name]

    # Skill Tool
    if name in ("SkillTool", "generate_skill_tool_prompt"):
        if "SkillTool" not in _lazy_imports:
            from .skill_tool import SkillTool, generate_skill_tool_prompt
            _lazy_imports["SkillTool"] = SkillTool
            _lazy_imports["generate_skill_tool_prompt"] = generate_skill_tool_prompt
        return _lazy_imports[name]

    # Bash Tool
    if name == "BashTool":
        if "BashTool" not in _lazy_imports:
            from .bash_tool import BashTool
            _lazy_imports["BashTool"] = BashTool
        return _lazy_imports["BashTool"]

    # Web Fetch Tool
    if name in ("WebFetchTool", "create_web_fetch_tool"):
        if "WebFetchTool" not in _lazy_imports:
            from .web_fetch_tool import WebFetchTool, create_web_fetch_tool
            _lazy_imports["WebFetchTool"] = WebFetchTool
            _lazy_imports["create_web_fetch_tool"] = create_web_fetch_tool
        return _lazy_imports[name]

    # Web Search Tool
    if name in ("WebSearchTool", "create_web_search_tool", "SearchResult"):
        if "WebSearchTool" not in _lazy_imports:
            from .web_search_tool import WebSearchTool, create_web_search_tool, SearchResult
            _lazy_imports["WebSearchTool"] = WebSearchTool
            _lazy_imports["create_web_search_tool"] = create_web_search_tool
            _lazy_imports["SearchResult"] = SearchResult
        return _lazy_imports[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # 基础工具 - 直接导入
    "BaseTool",
    "tool",
    "ToolCollection",
    "Toolset",
    "AsyncBaseTool",
    # 懒加载工具
    # Tool Search Tool exports
    "ToolInfo",
    "ToolRegistry",
    "ToolSearchTool",
    "LoadToolTool",
    "ToolSearchStrategy",
    "KeywordSearchStrategy",
    "RegexSearchStrategy",
    "BM25SearchStrategy",
    "HAS_BM25",
    # Skill Tool exports
    "SkillTool",
    "generate_skill_tool_prompt",
    # Bash Tool exports
    "BashTool",
    # Web Fetch Tool exports
    "WebFetchTool",
    "create_web_fetch_tool",
    # Web Search Tool exports
    "WebSearchTool",
    "create_web_search_tool",
    "SearchResult",
]
