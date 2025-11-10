#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Coding tools for file operations and code manipulation.
These tools are designed for CodeAgent to perform coding tasks.
"""
import os
import glob as glob_module
import re
import subprocess
from typing import Optional, List, Dict, Any
from pathlib import Path

from .base_tool import BaseTool
from .async_base_tool import AsyncBaseTool


class FileReadTool(BaseTool):
    """Tool for reading file contents"""

    name = "file_read"
    description = "Reads the entire contents of a file from the filesystem."
    inputs = {
        "file_path": {
            "type": "string",
            "description": "The absolute or relative path to the file to read."
        }
    }
    output_type = "string"
    readonly = True

    def forward(self, file_path: str) -> str:
        """
        Read the contents of a file.

        Args:
            file_path: Path to the file to read

        Returns:
            The file contents as a string
        """
        try:
            path = Path(file_path).expanduser()

            if not path.exists():
                return f"Error: File '{file_path}' does not exist."

            if not path.is_file():
                return f"Error: '{file_path}' is not a file."

            # Check file size to avoid reading huge files
            file_size = path.stat().st_size
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                return f"Error: File '{file_path}' is too large ({file_size} bytes). Maximum size is 10MB."

            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            return content

        except PermissionError:
            return f"Error: Permission denied reading '{file_path}'."
        except Exception as e:
            return f"Error reading file '{file_path}': {str(e)}"


class FileWriteTool(BaseTool):
    """Tool for writing contents to a file"""

    name = "file_write"
    description = "Writes content to a file, creating it if it doesn't exist or overwriting if it does."
    inputs = {
        "file_path": {
            "type": "string",
            "description": "The absolute or relative path to the file to write."
        },
        "content": {
            "type": "string",
            "description": "The content to write to the file."
        }
    }
    output_type = "string"
    readonly = False

    def forward(self, file_path: str, content: str) -> str:
        """
        Write content to a file.

        Args:
            file_path: Path to the file to write
            content: Content to write to the file

        Returns:
            Success or error message
        """
        try:
            path = Path(file_path).expanduser()

            # Create parent directories if they don't exist
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write the content
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

            return f"Successfully wrote {len(content)} characters to '{file_path}'."

        except PermissionError:
            return f"Error: Permission denied writing to '{file_path}'."
        except Exception as e:
            return f"Error writing file '{file_path}': {str(e)}"


class FileEditTool(BaseTool):
    """Tool for editing files with search and replace operations"""

    name = "file_edit"
    description = (
        "Edits a file by replacing all occurrences of a search string with a replacement string. "
        "This is useful for making targeted changes to existing files."
    )
    inputs = {
        "file_path": {
            "type": "string",
            "description": "The absolute or relative path to the file to edit."
        },
        "search": {
            "type": "string",
            "description": "The text to search for in the file."
        },
        "replace": {
            "type": "string",
            "description": "The text to replace the search string with."
        },
        "regex": {
            "type": "boolean",
            "description": "If True, treat search as a regular expression. Default is False.",
            "nullable": True
        }
    }
    output_type = "string"
    readonly = False

    def forward(self, file_path: str, search: str, replace: str, regex: bool = False) -> str:
        """
        Edit a file by replacing text.

        Args:
            file_path: Path to the file to edit
            search: Text to search for
            replace: Text to replace with
            regex: Whether to use regex matching

        Returns:
            Success message with number of replacements, or error message
        """
        try:
            path = Path(file_path).expanduser()

            if not path.exists():
                return f"Error: File '{file_path}' does not exist."

            if not path.is_file():
                return f"Error: '{file_path}' is not a file."

            # Read the file
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            # Perform replacement
            if regex:
                new_content, count = re.subn(search, replace, content)
            else:
                count = content.count(search)
                new_content = content.replace(search, replace)

            if count == 0:
                return f"No occurrences of '{search}' found in '{file_path}'."

            # Write back to the file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return f"Successfully replaced {count} occurrence(s) in '{file_path}'."

        except PermissionError:
            return f"Error: Permission denied accessing '{file_path}'."
        except re.error as e:
            return f"Error: Invalid regular expression: {str(e)}"
        except Exception as e:
            return f"Error editing file '{file_path}': {str(e)}"


class GrepTool(BaseTool):
    """Tool for searching text patterns in files"""

    name = "grep"
    description = (
        "Searches for a pattern in files. Returns matching lines with line numbers. "
        "Can search recursively in directories."
    )
    inputs = {
        "pattern": {
            "type": "string",
            "description": "The text pattern or regular expression to search for."
        },
        "path": {
            "type": "string",
            "description": "The file or directory path to search in."
        },
        "recursive": {
            "type": "boolean",
            "description": "If True, search recursively in subdirectories. Default is False.",
            "nullable": True
        },
        "case_sensitive": {
            "type": "boolean",
            "description": "If True, perform case-sensitive search. Default is True.",
            "nullable": True
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of matching lines to return. Default is 100.",
            "nullable": True
        }
    }
    output_type = "string"
    readonly = True

    def forward(
        self,
        pattern: str,
        path: str,
        recursive: bool = False,
        case_sensitive: bool = True,
        max_results: int = 100
    ) -> str:
        """
        Search for a pattern in files.

        Args:
            pattern: Pattern to search for
            path: File or directory path to search in
            recursive: Whether to search recursively
            case_sensitive: Whether to perform case-sensitive search
            max_results: Maximum number of results to return

        Returns:
            Matching lines with file paths and line numbers, or error message
        """
        try:
            search_path = Path(path).expanduser()

            if not search_path.exists():
                return f"Error: Path '{path}' does not exist."

            # Compile pattern
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                regex = re.compile(pattern, flags)
            except re.error as e:
                return f"Error: Invalid regex pattern: {str(e)}"

            results = []
            files_searched = 0

            # Get list of files to search
            if search_path.is_file():
                files = [search_path]
            else:
                if recursive:
                    files = list(search_path.rglob('*'))
                else:
                    files = list(search_path.glob('*'))
                # Filter to only regular files
                files = [f for f in files if f.is_file()]

            # Search each file
            for file_path in files:
                if len(results) >= max_results:
                    break

                try:
                    # Skip binary files and very large files
                    if file_path.stat().st_size > 1024 * 1024:  # 1MB
                        continue

                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            if len(results) >= max_results:
                                break

                            if regex.search(line):
                                # Format: filename:line_num:line_content
                                results.append(f"{file_path}:{line_num}:{line.rstrip()}")

                    files_searched += 1

                except (UnicodeDecodeError, PermissionError):
                    # Skip files that can't be read
                    continue

            if not results:
                return f"No matches found for pattern '{pattern}' in {files_searched} file(s)."

            header = f"Found {len(results)} match(es) in {files_searched} file(s):\n\n"
            return header + "\n".join(results)

        except Exception as e:
            return f"Error searching for pattern: {str(e)}"


class GlobTool(BaseTool):
    """Tool for finding files matching a pattern"""

    name = "glob"
    description = (
        "Finds all files matching a glob pattern. "
        "Supports wildcards like * (any characters) and ** (recursive directory search). "
        "Examples: '*.py' finds all Python files, 'src/**/*.py' finds all Python files recursively in src/."
    )
    inputs = {
        "pattern": {
            "type": "string",
            "description": "The glob pattern to match files. Use * for wildcard, ** for recursive."
        },
        "base_path": {
            "type": "string",
            "description": "The base directory to search from. Default is current directory.",
            "nullable": True
        }
    }
    output_type = "string"
    readonly = True

    def forward(self, pattern: str, base_path: Optional[str] = None) -> str:
        """
        Find files matching a glob pattern.

        Args:
            pattern: Glob pattern to match
            base_path: Base directory to search from

        Returns:
            List of matching file paths, or error message
        """
        try:
            if base_path is None:
                base_path = os.getcwd()

            search_path = Path(base_path).expanduser()

            if not search_path.exists():
                return f"Error: Base path '{base_path}' does not exist."

            if not search_path.is_dir():
                return f"Error: Base path '{base_path}' is not a directory."

            # Use Path.glob for recursive patterns (**) and regular glob for others
            if '**' in pattern:
                matches = list(search_path.glob(pattern))
            else:
                matches = list(search_path.glob(pattern))

            if not matches:
                return f"No files found matching pattern '{pattern}' in '{base_path}'."

            # Sort and format results
            matches = sorted(matches)
            results = [str(m.relative_to(search_path)) if m.is_relative_to(search_path) else str(m)
                      for m in matches]

            header = f"Found {len(results)} file(s) matching '{pattern}':\n\n"
            return header + "\n".join(results)

        except Exception as e:
            return f"Error finding files: {str(e)}"


class BashCommandTool(AsyncBaseTool):
    """Tool for executing bash commands (async version for safety)"""

    name = "bash_command"
    description = (
        "Executes a bash command and returns its output. "
        "Use this for running shell commands, compiling code, running tests, etc. "
        "Be careful with destructive commands."
    )
    inputs = {
        "command": {
            "type": "string",
            "description": "The bash command to execute."
        },
        "timeout": {
            "type": "integer",
            "description": "Maximum execution time in seconds. Default is 30.",
            "nullable": True
        }
    }
    output_type = "string"
    readonly = False

    async def forward(self, command: str, timeout: int = 30) -> str:
        """
        Execute a bash command asynchronously.

        Args:
            command: Command to execute
            timeout: Maximum execution time in seconds

        Returns:
            Command output (stdout and stderr), or error message
        """
        try:
            # Run the command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return f"Error: Command timed out after {timeout} seconds."

            # Decode output
            stdout_text = stdout.decode('utf-8', errors='replace')
            stderr_text = stderr.decode('utf-8', errors='replace')

            # Format output
            output_parts = []
            if stdout_text:
                output_parts.append(f"STDOUT:\n{stdout_text}")
            if stderr_text:
                output_parts.append(f"STDERR:\n{stderr_text}")

            output_parts.append(f"\nExit code: {process.returncode}")

            return "\n".join(output_parts) if output_parts else "Command executed with no output."

        except Exception as e:
            return f"Error executing command: {str(e)}"


# Need to import asyncio for BashCommandTool
import asyncio


__all__ = [
    "FileReadTool",
    "FileWriteTool",
    "FileEditTool",
    "GrepTool",
    "GlobTool",
    "BashCommandTool",
]
