from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict, Union
import json

from tenacity import retry, stop_after_attempt, retry_if_exception_type

from minion.schema.message_types import Message
from minion.models.schemas import Answer
from minion.providers import BaseProvider
from minion.utils.utils import extract_json


class ActionNode(ABC):
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        pass

    async def __call__(self, *args, **kwargs):
        return await self.execute(*args, **kwargs)


class LLMActionNode(ActionNode):
    def __init__(self,
                 llm: BaseProvider,
                 input_parser: Optional[callable] = None,
                 output_parser: Optional[callable] = None):
        self.llm = llm
        self.input_parser = input_parser
        self.output_parser = output_parser

    async def execute(self, messages: List[Message], **kwargs) -> Any:
        if self.input_parser:
            messages = self.input_parser(messages)

        response = await self.llm.generate_stream(messages)

        if self.output_parser:
            return self.output_parser(response)

        return response

    def normalize_response(self, response: Union[str, dict], is_answer_format: bool = False) -> Union[str, dict]:
        """规范化响应格式"""
        response_is_str = False
        if isinstance(response, str):
            response_is_str = True
            # 使用更新后的 extract_json 函数处理响应
            response_str = extract_json(response)
            try:
              response = json.loads(response_str)
            except json.JSONDecodeError:
              return response_str

        # 处理 schema 格式
        if is_answer_format and isinstance(response, dict) and "properties" in response:
            if "answer" in response["properties"]:
                return {"answer": response["properties"]["answer"].get("default", "")}
        if response_is_str:
            return json.dumps(response)
        return response
    # @retry(
    #     stop=stop_after_attempt(3),
    #     retry=retry_if_exception_type(Exception),
    #     reraise=True
    # )
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
