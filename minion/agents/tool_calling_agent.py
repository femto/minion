from typing import Dict, Any, List, Optional, Union, AsyncGenerator
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import inspect
from dataclasses import dataclass, field

from .base_agent import BaseAgent, AgentState
from ..main.input import Input
from ..main.action_step import StreamChunk
from ..tools.base_tool import BaseTool
from ..schema.message_types import ToolCall
from ..providers import create_llm_provider
from .. import config
from ..exceptions import FinalAnswerException
from minion.types.agent_response import AgentResponse
from ..tools.default_tools import FinalAnswerTool

logger = logging.getLogger(__name__)


@dataclass
class ToolCallingAgent(BaseAgent):
    """
    Tool calling agent with automatic final_answer support.

    This agent automatically adds a FinalAnswerTool and detects when it is called
    to properly terminate execution, similar to smolagents' ToolCallingAgent.
    """

    async def setup(self):
        """Setup agent and add FinalAnswerTool if not present."""
        # Add FinalAnswerTool if not already present
        has_final_answer = any(
            getattr(tool, 'name', None) == 'final_answer'
            for tool in self.tools
        )
        if not has_final_answer:
            self.add_tool(FinalAnswerTool())
            logger.debug("Added FinalAnswerTool to ToolCallingAgent")

        await super().setup()

    def is_done(self, result: Any, state: AgentState) -> bool:
        """
        Check if task is completed by detecting final_answer tool call.

        Args:
            result: The result from the current step
            state: Current agent state

        Returns:
            bool: True if task is completed
        """
        # Check parent's is_done first
        if super().is_done(result, state):
            return True

        # Check if final_answer was called in this step
        if hasattr(result, 'answer') and result.answer:
            answer = str(result.answer)
            # Check for final_answer tool execution result
            if 'final_answer' in answer.lower() and 'execution result' in answer.lower():
                logger.debug("Detected final_answer tool call, marking task as done")
                return True
            # Check for FINAL_ANSWER marker
            if 'FINAL_ANSWER:' in answer:
                logger.debug("Detected FINAL_ANSWER marker, marking task as done")
                return True

        return False