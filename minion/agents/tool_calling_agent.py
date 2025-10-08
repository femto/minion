from typing import Dict, Any, List, Optional, Union, AsyncGenerator
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import inspect
from dataclasses import dataclass, field

from .base_agent import BaseAgent
from ..main.input import Input
from ..main.action_step import StreamChunk
from ..tools.base_tool import BaseTool
from ..schema.message_types import ToolCall
from ..providers import create_llm_provider
from .. import config
from ..exceptions import FinalAnswerException
from minion.types.agent_response import AgentResponse

logger = logging.getLogger(__name__)


@dataclass
class ToolCallingAgent(BaseAgent):
    #ToolCallingAgent is the same as  BaseAgent now
    pass