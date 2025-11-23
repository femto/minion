#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File operation tools with observation formatting support
"""
from typing import Any
from .base_tool import BaseTool


class FileReadTool(BaseTool):
    """
    Tool for reading file contents.

    When used as observation (last item in code), returns content with line numbers
    for better LLM understanding. When used in code flow, returns raw content.
    """
    name = "file_read"
    description = "Read the contents of a file. Returns file content as a string."
    inputs = {
        "file_path": {
            "type": "string",
            "description": "Path to the file to read"
        }
    }
    output_type = "string"
    readonly = True

    def forward(self, file_path: str) -> str:
        """
        Read and return file contents.

        Args:
            file_path: Path to the file to read

        Returns:
            File contents as string
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except FileNotFoundError:
            return f"Error: File not found: {file_path}"
        except PermissionError:
            return f"Error: Permission denied: {file_path}"
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def format_for_observation(self, output: Any) -> str:
        """
        Format file content with line numbers for LLM observation.

        When tool output becomes an observation (last item in code),
        this method adds line numbers to make it easier for LLM to reference
        specific lines.

        Args:
            output: Raw file content from forward()

        Returns:
            File content with line numbers
        """
        if not isinstance(output, str):
            return str(output)

        # Check if this is an error message
        if output.startswith("Error:"):
            return output

        # Add line numbers to each line
        lines = output.split('\n')
        formatted_lines = []

        # Calculate padding for line numbers
        max_line_num = len(lines)
        padding = len(str(max_line_num))

        for i, line in enumerate(lines, start=1):
            line_num = str(i).rjust(padding)
            formatted_lines.append(f"{line_num} | {line}")

        return '\n'.join(formatted_lines)


class FileWriteTool(BaseTool):
    """
    Tool for writing content to a file.
    """
    name = "file_write"
    description = "Write content to a file. Creates the file if it doesn't exist, overwrites if it does."
    inputs = {
        "file_path": {
            "type": "string",
            "description": "Path to the file to write"
        },
        "content": {
            "type": "string",
            "description": "Content to write to the file"
        }
    }
    output_type = "string"
    readonly = False

    def forward(self, file_path: str, content: str) -> str:
        """
        Write content to a file.

        Args:
            file_path: Path to the file to write
            content: Content to write

        Returns:
            Success message or error
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to {file_path}"
        except PermissionError:
            return f"Error: Permission denied: {file_path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    def format_for_observation(self, output: Any) -> str:
        """
        Format write result for observation.

        For write operations, we just return the status message as-is
        since it's already concise and informative.
        """
        return str(output)


class FileAppendTool(BaseTool):
    """
    Tool for appending content to a file.
    """
    name = "file_append"
    description = "Append content to the end of a file. Creates the file if it doesn't exist."
    inputs = {
        "file_path": {
            "type": "string",
            "description": "Path to the file to append to"
        },
        "content": {
            "type": "string",
            "description": "Content to append to the file"
        }
    }
    output_type = "string"
    readonly = False

    def forward(self, file_path: str, content: str) -> str:
        """
        Append content to a file.

        Args:
            file_path: Path to the file to append to
            content: Content to append

        Returns:
            Success message or error
        """
        try:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully appended {len(content)} characters to {file_path}"
        except PermissionError:
            return f"Error: Permission denied: {file_path}"
        except Exception as e:
            return f"Error appending to file: {str(e)}"
