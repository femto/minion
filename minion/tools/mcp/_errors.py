"""Shared formatting for MCP tool failures.

Every MCP tool failure is returned to the caller as a string starting with
``"Error:"``, which is what agents and examples check for.
"""

import json
from typing import Any, Optional

from minion.tools.mcp._compat import get_field


def format_mcp_tool_error(tool_name: str, detail: Any) -> str:
    """Format a failed MCP tool call (isError result, timeout or exception)."""
    return f"Error: MCP tool {tool_name} failed: {detail}"


def call_tool_error_text(result: Any) -> Optional[str]:
    """Return the error text of a CallToolResult flagged isError, or None if it succeeded.

    Tool execution errors come back as a normal result with ``isError``
    (``is_error`` on MCP 2.x) set, not as an exception. The text content
    carries the actionable message, so it takes precedence over
    ``structuredContent``.
    """
    if not get_field(result, "is_error", "isError", False):
        return None
    texts = [item.text if hasattr(item, "text") else str(item) for item in (getattr(result, "content", None) or [])]
    if texts:
        return "\n".join(texts)
    structured = get_field(result, "structured_content", "structuredContent")
    if structured is not None:
        return json.dumps(structured, ensure_ascii=False)
    return "the server reported an error without details"
