#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bash command execution tool
"""

import os
import subprocess
from typing import Optional, Any
from minion.tools import BaseTool
from minion.utils.output_truncator import truncate_output


class BashTool(BaseTool):
    """Bash command execution tool"""

    name = "bash"
    description = "Execute bash commands"
    readonly = False  # Command execution may modify system state
    inputs = {
        "command": {"type": "string", "description": "Bash command to execute"},
        "timeout": {
            "type": "integer",
            "description": "Timeout in seconds",
            "nullable": True,
        },
    }
    output_type = "string"

    def forward(self, command: str, timeout: Optional[int] = 30) -> str:
        """Execute bash command"""
        try:
            # Security check: prohibit dangerous commands
            dangerous_commands = ["rm -rf", "sudo", "su", "chmod 777", "mkfs", "dd if="]
            if any(dangerous in command.lower() for dangerous in dangerous_commands):
                return f"Error: Dangerous command prohibited - {command}"

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )

            output = ""
            if result.stdout:
                output += f"Standard output:\n{result.stdout}\n"
            if result.stderr:
                output += f"Standard error:\n{result.stderr}\n"
            output += f"Exit code: {result.returncode}"

            return self.format_for_observation(output)

        except subprocess.TimeoutExpired:
            return f"Command execution timeout ({timeout} seconds)"
        except Exception as e:
            return f"Error executing command: {str(e)}"

    def format_for_observation(self, output: Any) -> str:
        """Format output, automatically truncate large content"""
        if isinstance(output, str):
            return truncate_output(output, tool_name=self.name)
        return str(output)
