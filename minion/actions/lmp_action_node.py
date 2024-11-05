from typing import Any, Union, List, Optional, Type
from pydantic import BaseModel
import json

import ell
from tenacity import retry, stop_after_attempt, retry_if_exception_type

from minion.configs.config import config
from minion.message_types import Message
from minion.actions.action_node import LLMActionNode
from minion.messages import user
from minion.providers import create_llm_provider
from minion.models.schemas import Answer  # Import the Answer model

# @ell.complex(model="gpt-4o-mini")
# def ell_call(ret):
#     """You are a helpful assistant."""
#     return ret
class LmpActionNode(LLMActionNode):
    def __init__(self, llm, input_parser=None, output_parser=None):
        super().__init__(llm, input_parser, output_parser)
        ell.init(**config.ell, default_client=self.llm.client_ell)

    @ell.complex(model="gpt-4o-mini")
    def ell_call(self, ret):
        """You are a helpful assistant."""
        return ret

    async def execute(self, messages: Union[str, Message, List[Message]], response_format: Optional[Union[Type[BaseModel], dict]] = None, output_raw_parser=None, **kwargs) -> Any:
        # 添加 input_parser 处理
        if self.input_parser:
            messages = self.input_parser(messages)
            
        # 从 llm.config 获取配置
        api_params = {
            "temperature": self.llm.config.temperature,
            "model": self.llm.config.model,
        }
        
        # 将 kwargs 合并到 api_params 中，允许覆盖默认值
        api_params.update(kwargs)
        original_response_format = response_format

        if isinstance(response_format, type) and issubclass(response_format, BaseModel):
            # If response_format is a Pydantic model, convert it to JSON schema
            schema = response_format.model_json_schema()
            schema_with_indent = json.dumps(schema, indent=4)
            if isinstance(messages, str):
                messages = [user(messages)]
            elif isinstance(messages, Message):
                messages.content = [messages]

            messages.append(user(
                content=f"Please provide the response in JSON format as per the following schema:\n{schema_with_indent}"))

            api_params['response_format'] = { "type": "json_object" }
        elif isinstance(response_format, dict):
            # If response_format is a dictionary, pass it as is
            api_params['response_format'] = response_format

        response = self.ell_call(messages, client=self.llm.client_ell, api_params=api_params)
        response = response.text

        if output_raw_parser:
            response = output_raw_parser(response)
        if original_response_format and isinstance(original_response_format, type) and issubclass(original_response_format, BaseModel):
            response = original_response_format.model_validate_json(response)
            # 判断 response pydantic model 是否只有一个 field
            # if len(original_response_format.model_fields) == 1:
            #     field_name = list(original_response_format.model_fields.keys())[0]
            #     response = getattr(response, field_name)
            #判断 response pydantic model 是否只有一个 field
            # if original_response_format == Answer:
            #     response = response.answer

        if self.output_parser:
            response = self.output_parser(response)
        return response
