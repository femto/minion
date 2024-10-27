from abc import ABC, abstractmethod
from typing import Any, Dict

from minion.providers.base_llm import BaseLLM


class ActionNode(ABC):
    @abstractmethod
    async def execute(self, *args, **kwargs):
        pass

    async def __call__(self, *args, **kwargs):
        return await self.execute(*args, **kwargs)


class LLMActionNode(ActionNode):
    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def execute(self, context: Dict[str, Any]) -> str:
        messages = context.get("messages", [])
        return await self.llm.generate(messages)


class ToolActionNode(ActionNode):
    def __init__(self, tool_function: callable):
        self.tool_function = tool_function

    async def execute(self, context: Dict[str, Any]) -> Any:
        args = context.get("args", {})
        return await self.tool_function(**args)


class EnvironmentActionNode(ActionNode):
    def __init__(self, env_interaction: callable):
        self.env_interaction = env_interaction

    async def execute(self, context: Dict[str, Any]) -> Any:
        return await self.env_interaction(context)
