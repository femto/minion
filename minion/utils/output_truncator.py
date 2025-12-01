#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Output truncation and size checking utilities for tools.

Handles:
- Built-in tool output truncation (400KB limit)
- MCP tool output checking (token limit)
- File size checking before read (with suggested tools for large files)
"""

from pathlib import Path
from typing import Optional

# Configuration constants
MAX_OUTPUT_SIZE = 400 * 1024      # 400KB - built-in tool output truncation threshold
MAX_FILE_SIZE = 1_000_000         # 1MB - file read size threshold
MAX_TOKEN_LIMIT = 100_000         # MCP tool token limit


# Exception classes
class OutputTooLargeError(Exception):
    """Built-in tool output too large"""
    pass


class MCPContentTooLargeError(Exception):
    """MCP tool content too large"""
    def __init__(self, message: str, token_count: Optional[int] = None):
        self.token_count = token_count
        super().__init__(message)


class FileTooLargeError(Exception):
    """File too large, suggest specialized tool"""
    def __init__(
        self,
        message: str,
        file_path: str,
        file_size: int,
        suggested_tool: Optional[str] = None
    ):
        self.file_path = file_path
        self.file_size = file_size
        self.suggested_tool = suggested_tool
        super().__init__(message)


# Pre-execution checks
def check_file_size_before_read(
    file_path: str,
    max_size: int = MAX_FILE_SIZE
) -> None:
    """
    Check file size before read operation.

    Args:
        file_path: File path
        max_size: Maximum allowed size (bytes)

    Raises:
        FileTooLargeError: When file is too large, includes suggested tool
    """
    path = Path(file_path)
    if not path.exists():
        return

    file_size = path.stat().st_size
    if file_size > max_size:
        size_mb = file_size / 1_000_000
        suffix = path.suffix.lower()

        # Suggest specialized tools based on file type
        tool_suggestions = {
            '.pdf': 'pdf tool',
            '.xlsx': 'xlsx tool',
            '.xls': 'xlsx tool',
            '.docx': 'docx tool',
            '.doc': 'docx tool',
            '.pptx': 'pptx tool',
        }
        suggested = tool_suggestions.get(suffix, 'paginated read (offset/limit parameters)')

        raise FileTooLargeError(
            f"File too large ({size_mb:.1f}MB > {max_size/1_000_000:.1f}MB), please use {suggested}",
            file_path=str(path),
            file_size=file_size,
            suggested_tool=suggested
        )


# Output truncation
def truncate_output(
    output: str,
    max_size: int = MAX_OUTPUT_SIZE,
    tool_name: str = "",
) -> str:
    """
    Truncate built-in tool output (automatically applied).

    Args:
        output: Original output
        max_size: Maximum bytes, default 400KB
        tool_name: Tool name, used for generating specific hints

    Returns:
        Truncated output (with hint if truncated)
    """
    output_bytes = output.encode('utf-8')
    if len(output_bytes) <= max_size:
        return output

    # Truncate to max_size bytes, ensure not truncating UTF-8 characters
    truncated_bytes = output_bytes[:max_size]
    truncated = truncated_bytes.decode('utf-8', errors='ignore')

    total_size = len(output_bytes)
    hint = _get_tool_hint(tool_name)

    truncated += f"\n\n---\n⚠️ Output truncated (showing {max_size/1024:.0f}KB / {total_size/1024:.0f}KB)\n{hint}"

    return truncated


def check_mcp_output(
    output: str,
    max_tokens: int = MAX_TOKEN_LIMIT
) -> str:
    """
    Check MCP tool output, raise exception if exceeds token limit.

    Args:
        output: MCP tool output
        max_tokens: Maximum token count

    Returns:
        Original output (if not exceeding limit)

    Raises:
        MCPContentTooLargeError: Output exceeds token limit
    """
    # Simple estimation: 1 token ≈ 4 characters
    estimated_tokens = len(output) // 4

    if estimated_tokens > max_tokens:
        raise MCPContentTooLargeError(
            f"MCP tool output too large (approx {estimated_tokens} tokens > {max_tokens} limit)",
            token_count=estimated_tokens
        )

    return output


def _get_tool_hint(tool_name: str) -> str:
    """Return hint for getting full content based on tool name"""
    hints = {
        'bash': "Hint: Use `| head -n N` or `| tail -n N` to limit output lines",
        'grep': "Hint: Use `head_limit` parameter, or more precise search pattern",
        'glob': "Hint: Use more specific pattern to narrow matches",
        'ls': "Hint: Avoid recursive mode, or specify more specific subdirectory",
        'file_read': "Hint: Use `offset` and `limit` parameters for paginated read",
        'python': "Hint: Control print output in your code",
    }
    return hints.get(tool_name, "Hint: Use more precise parameters to narrow output")
