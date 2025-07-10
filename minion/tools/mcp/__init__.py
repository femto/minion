"""
MCP (Model Context Protocol) Integration for Minion
"""

from .mcp_integration import (
    MCPBrainClient,
    BrainTool,
    format_mcp_result,
    create_final_answer_tool,
    create_calculator_tool,
    MCPToolConfig,
    add_filesystem_tool,
    create_filesystem_tool_factory
)

from .mcp_toolset import (
    MCPToolSet,
    create_filesystem_toolset_factory
)

__all__ = [
    # Legacy MCP integration (deprecated, use MCPToolSet instead)
    "MCPBrainClient",
    "BrainTool", 
    "format_mcp_result",
    "create_final_answer_tool",
    "create_calculator_tool",
    "MCPToolConfig",
    "add_filesystem_tool",
    "create_filesystem_tool_factory",
    
    # New ToolSet-based API (recommended)
    "MCPToolSet",
    "create_filesystem_toolset_factory"
] 