from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict
import json

from tenacity import retry, stop_after_attempt, retry_if_exception_type

from minion.message_types import Message
from minion.models.schemas import Answer
from minion.providers import BaseLLM
from minion.utils.utils import extract_json


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

        response = await self.llm.generate_stream(messages)

        if self.output_parser:
            return self.output_parser(response)

        return response

    def normalize_response(self, response: Dict[Any, Any] | str) -> Dict[str, str]:
        """
        将复杂的JSON schema响应转换为简单的answer格式

        Args:
            response: LLM返回的响应字典或字符串

        Returns:
            标准化的answer格式字典
        """
        # 如果响应是字符串，尝试解析为JSON
        if isinstance(response, str):
            response_is_str = True
            response_str = extract_json(response)
            try:
                response = json.loads(response_str)
            except json.JSONDecodeError:
                # 如果解析失败，将字符串作为answer的值返回
                return response

        # 如果响应已经是简单格式
        if "answer" in response:
            if response_is_str:
                return response_str
            return response

        # 如果响应是schema格式
        if "properties" in response and "answer" in response["properties"]:
            answer_value = response["properties"]["answer"].get("default", "")
            if response_is_str:
                return json.dumps({"answer": answer_value})
            return {"answer": answer_value}

        # 如果是其他格式,返回空答案
        if response_is_str:
            return json.dumps({"answer": ""})
        return {"answer": ""}
    # @retry(
    #     stop=stop_after_attempt(3),
    #     retry=retry_if_exception_type(Exception),
    #     reraise=True
    # )
    async def execute_answer(self, messages, **kwargs):
        result = await self.execute(messages, response_format=Answer, output_raw_parser=self.normalize_response, **kwargs)
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
