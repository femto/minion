from abc import ABC, abstractmethod
from typing import Any, Optional, List

from minion.message_types import Message
from minion.models.schemas import Answer
from minion.providers import BaseLLM


class ActionNode(ABC):
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        pass

    async def __call__(self, *args, **kwargs):
        return await self.execute(*args, **kwargs)


class LLMActionNode(ActionNode):
    def __init__(self,
                 llm: BaseLLM,
                 input_parser: Optional[callable] = None,
                 output_parser: Optional[callable] = None):
        self.llm = llm
        self.input_parser = input_parser
        self.output_parser = output_parser

    async def execute(self, messages: List[Message], **kwargs) -> Any:
        if self.input_parser:
            messages = self.input_parser(messages)

        response = await self.llm.generate(messages)

        if self.output_parser:
            return self.output_parser(response)

        return response

    async def execute_answer(self, messages, **kwargs):
        result = await self.execute(messages, response_format=Answer, **kwargs)
        return result.answer


class ToolActionNode(ActionNode):
    def __init__(self,
                 tool_function: callable,
                 input_parser: Optional[callable] = None,
                 output_parser: Optional[callable] = None):
        self.tool_function = tool_function
        self.input_parser = input_parser
        self.output_parser = output_parser

    async def execute(self, **kwargs) -> Any:
        if self.input_parser:
            kwargs = self.input_parser(kwargs)

        result = await self.tool_function(**kwargs)

        if self.output_parser:
            return self.output_parser(result)

        return result
