"""
MCP (Model Context Protocol) Integration for Minion

Simplified API for connecting to MCP servers and using their tools.
"""

from .mcp_toolset import (
    # Core classes
    AsyncMcpTool,
    format_mcp_result,
    
    # Google ADK-style simplified API
    MCPToolset,
    StdioServerParameters,
    SSEServerParameters,
    
    # Factory functions
    create_filesystem_toolset,
    create_brave_search_toolset
)

__all__ = [
    # Core classes
    "AsyncMcpTool",
    "format_mcp_result",
    
    # Google ADK-style simplified API
    "MCPToolset",
    "StdioServerParameters", 
    "SSEServerParameters",
    
    # Factory functions
    "create_filesystem_toolset",
    "create_brave_search_toolset"
] 