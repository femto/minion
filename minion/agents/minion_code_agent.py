"""
MinionCodeAgent: Enhanced CodeAgent with coding-specific tools.

This agent extends CodeAgent by automatically including tools for:
- File reading and writing
- File editing
- Text searching (grep)
- File pattern matching (glob)
- Bash command execution

It's designed for coding tasks that require file system operations.
"""
from typing import List, Optional, Union
from dataclasses import dataclass, field

from .code_agent import CodeAgent
from ..tools.base_tool import BaseTool
from ..tools.coding_tools import (
    FileReadTool,
    FileWriteTool,
    FileEditTool,
    GrepTool,
    GlobTool,
    BashCommandTool,
)


@dataclass
class MinionCodeAgent(CodeAgent):
    """
    Enhanced CodeAgent with built-in coding tools.

    This agent automatically includes file operation tools:
    - file_read: Read file contents
    - file_write: Write content to files
    - file_edit: Edit files with search/replace
    - grep: Search for patterns in files
    - glob: Find files matching patterns
    - bash_command: Execute shell commands

    Example:
        ```python
        from minion.agents import MinionCodeAgent
        from minion.types.llm_types import ModelType

        # Create agent with automatic coding tools
        agent = MinionCodeAgent(
            name="coding_assistant",
            model="gpt-4o",  # or ModelType.GPT4O
        )

        # Setup and use
        await agent.setup()

        result = await agent.run_async(
            "Read the README.md file and count how many times 'Python' appears in it"
        )
        ```
    """

    name: str = "minion_code_agent"

    # Whether to include coding tools automatically
    include_coding_tools: bool = True

    # Which specific coding tools to include (None means all)
    coding_tools_to_include: Optional[List[str]] = None

    def __post_init__(self):
        """Initialize MinionCodeAgent with coding tools"""
        # Add coding tools before calling parent __post_init__
        if self.include_coding_tools:
            self._add_coding_tools()

        # Call parent initialization
        super().__post_init__()

    def _add_coding_tools(self):
        """Add coding-specific tools to the agent"""
        # Default: include all coding tools
        available_tools = {
            'file_read': FileReadTool(),
            'file_write': FileWriteTool(),
            'file_edit': FileEditTool(),
            'grep': GrepTool(),
            'glob': GlobTool(),
            'bash_command': BashCommandTool(),
        }

        # If specific tools are specified, only include those
        if self.coding_tools_to_include:
            tools_to_add = [
                tool for name, tool in available_tools.items()
                if name in self.coding_tools_to_include
            ]
        else:
            # Include all coding tools
            tools_to_add = list(available_tools.values())

        # Add to tools list (avoiding duplicates)
        existing_tool_names = {tool.name for tool in self.tools if hasattr(tool, 'name')}
        for tool in tools_to_add:
            if tool.name not in existing_tool_names:
                self.tools.append(tool)

    @classmethod
    async def create_with_tools(
        cls,
        name: str = "minion_code_agent",
        additional_tools: Optional[List[BaseTool]] = None,
        **kwargs
    ):
        """
        Factory method to create a MinionCodeAgent with additional tools.

        Args:
            name: Agent name
            additional_tools: Extra tools to add beyond the coding tools
            **kwargs: Other agent configuration parameters

        Returns:
            Configured and setup MinionCodeAgent instance
        """
        tools = additional_tools or []
        agent = cls(name=name, tools=tools, **kwargs)
        await agent.setup()
        return agent


# Convenience alias
CodeAgent = MinionCodeAgent


__all__ = ["MinionCodeAgent", "CodeAgent"]
